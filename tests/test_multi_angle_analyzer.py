"""src/analysis/multi_angle_analyzer.py のテスト（LLM はモック）。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.analysis.context_builder import build_analysis_context
from src.analysis.multi_angle_analyzer import (
    perform_multi_angle_analysis,
    _coerce_to_str,
)
from src.llm.base import LLMClient
from src.shared.models import (
    NewsEvent,
    PerspectiveCandidate,
    ScoredEvent,
    SourceRef,
)


_FIXTURES = Path(__file__).parent / "fixtures" / "llm_responses"


def _load_fixture(name: str) -> str:
    return (_FIXTURES / f"{name}.json").read_text(encoding="utf-8")


class StubLLMClient(LLMClient):
    """固定文字列を返す LLM スタブ。受け取ったプロンプトを記録する。"""

    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def _scored_event() -> ScoredEvent:
    ev = NewsEvent(
        id="evt-mga-1",
        title="Iran threatens to close Strait of Hormuz",
        summary="Tehran signaled possible closure amid renewed sanctions; world oil markets reacted.",
        category="geopolitics",
        source="Reuters",
        published_at=datetime.now(timezone.utc),
        sources_jp=[
            SourceRef(name="Nikkei", url="https://jp.example.com/0", region="japan"),
        ],
        sources_en=[
            SourceRef(name="Reuters", url="https://en.example.com/0", region="global"),
            SourceRef(name="BBC", url="https://en.example.com/1", region="global"),
            SourceRef(name="AlJazeera", url="https://en.example.com/2", region="middle_east"),
        ],
    )
    return ScoredEvent(event=ev, score=10.0)


def _selected_perspective() -> PerspectiveCandidate:
    return PerspectiveCandidate(
        axis="hidden_stakes",
        score=8.0,
        reasoning="日本の原油輸入の80%超が同海峡経由で、間接的影響が極めて大きい。",
        evidence_refs=["https://en.example.com/0", "https://jp.example.com/0"],
    )


# ---------- happy path ----------

def test_perform_returns_all_5_fields_from_fixture():
    se = _scored_event()
    pc = _selected_perspective()
    ctx = build_analysis_context(se, [pc])
    stub = StubLLMClient(_load_fixture("multi_angle_analysis_geopolitics"))

    result = perform_multi_angle_analysis(se, pc, ctx, client=stub)
    assert result.geopolitical and "イラン" in result.geopolitical
    assert result.political_intent and "ライシ" in result.political_intent
    assert result.economic_impact and "INPEX" in result.economic_impact
    assert result.cultural_context and "湾岸" in result.cultural_context
    assert result.media_divergence and "Al Jazeera" in result.media_divergence


def test_perform_uses_provided_client_only_once():
    se = _scored_event()
    pc = _selected_perspective()
    ctx = build_analysis_context(se, [pc])
    stub = StubLLMClient(_load_fixture("multi_angle_analysis_minimal"))

    perform_multi_angle_analysis(se, pc, ctx, client=stub)
    # LLM は 1 回のみ
    assert len(stub.prompts) == 1


def test_perform_prompt_includes_selected_axis_and_event_metadata():
    se = _scored_event()
    pc = _selected_perspective()
    ctx = build_analysis_context(se, [pc])
    stub = StubLLMClient(_load_fixture("multi_angle_analysis_minimal"))

    perform_multi_angle_analysis(se, pc, ctx, client=stub)
    prompt = stub.prompts[0]
    assert "hidden_stakes" in prompt
    assert "Strait of Hormuz" in prompt  # event_title
    assert "Tehran" in prompt or "原油" in prompt or "sanctions" in prompt  # event_summary
    # 記事スニペットの URL が渡されていること
    assert "https://en.example.com/0" in prompt


# ---------- robustness ----------

def test_perform_handles_code_fenced_response():
    se = _scored_event()
    pc = _selected_perspective()
    ctx = build_analysis_context(se, [pc])
    fenced = "```json\n" + _load_fixture("multi_angle_analysis_minimal") + "\n```"
    stub = StubLLMClient(fenced)

    result = perform_multi_angle_analysis(se, pc, ctx, client=stub)
    assert result.geopolitical == "Brief geopolitical analysis."


def test_perform_fills_none_for_missing_keys(caplog):
    se = _scored_event()
    pc = _selected_perspective()
    ctx = build_analysis_context(se, [pc])
    # geopolitical / cultural_context だけ返す不完全レスポンス
    partial = json.dumps({
        "geopolitical": "only g",
        "cultural_context": "only c",
    })
    stub = StubLLMClient(partial)

    with caplog.at_level("WARNING"):
        result = perform_multi_angle_analysis(se, pc, ctx, client=stub)
    assert result.geopolitical == "only g"
    assert result.cultural_context == "only c"
    assert result.political_intent is None
    assert result.economic_impact is None
    assert result.media_divergence is None


def test_perform_coerces_dict_value_to_json_string():
    """LLM が誤って dict を返したケースでも文字列化して保持する。"""
    se = _scored_event()
    pc = _selected_perspective()
    ctx = build_analysis_context(se, [pc])
    weird = json.dumps({
        "geopolitical": {"unexpected": "structure"},
        "political_intent": "ok",
        "economic_impact": "ok",
        "cultural_context": "ok",
        "media_divergence": "ok",
    })
    stub = StubLLMClient(weird)

    result = perform_multi_angle_analysis(se, pc, ctx, client=stub)
    assert result.geopolitical is not None
    assert "unexpected" in result.geopolitical


def test_perform_raises_on_invalid_json():
    se = _scored_event()
    pc = _selected_perspective()
    ctx = build_analysis_context(se, [pc])
    stub = StubLLMClient("not even a brace here")

    with pytest.raises(json.JSONDecodeError):
        perform_multi_angle_analysis(se, pc, ctx, client=stub)


def test_perform_raises_when_response_is_not_object():
    se = _scored_event()
    pc = _selected_perspective()
    ctx = build_analysis_context(se, [pc])
    # JSON 配列は dict ではないため弾かれる
    stub = StubLLMClient('["not", "a", "dict"]')

    with pytest.raises(ValueError):
        perform_multi_angle_analysis(se, pc, ctx, client=stub)


def test_perform_raises_when_no_client_available(monkeypatch):
    se = _scored_event()
    pc = _selected_perspective()
    ctx = build_analysis_context(se, [pc])

    # get_analysis_llm_client が None を返す状況をシミュレート
    monkeypatch.setattr(
        "src.analysis.multi_angle_analyzer.get_analysis_llm_client",
        lambda: None,
    )
    with pytest.raises(RuntimeError):
        perform_multi_angle_analysis(se, pc, ctx, client=None)


# ---------- _coerce_to_str ----------

def test_coerce_none_returns_none():
    assert _coerce_to_str(None) is None


def test_coerce_empty_string_returns_none():
    assert _coerce_to_str("   ") is None


def test_coerce_str_strips_and_returns_str():
    assert _coerce_to_str(" hello ") == "hello"


def test_coerce_dict_returns_json_string():
    out = _coerce_to_str({"a": 1})
    assert isinstance(out, str)
    assert "a" in out and "1" in out
