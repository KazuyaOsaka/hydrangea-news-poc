"""src/analysis/insight_extractor.py のテスト（LLM はモック）。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.analysis.context_builder import build_analysis_context
from src.analysis.insight_extractor import (
    _coerce_evidence_refs,
    _coerce_importance,
    _parse_insight_item,
    extract_insights,
)
from src.llm.base import LLMClient
from src.shared.models import (
    MultiAngleAnalysis,
    NewsEvent,
    PerspectiveCandidate,
    ScoredEvent,
    SourceRef,
)


_FIXTURES = Path(__file__).parent / "fixtures" / "llm_responses"


def _load_fixture(name: str) -> str:
    return (_FIXTURES / f"{name}.json").read_text(encoding="utf-8")


class StubLLMClient(LLMClient):
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def _scored_event() -> ScoredEvent:
    ev = NewsEvent(
        id="evt-ins-1",
        title="Iran threatens to close Strait of Hormuz",
        summary="Tehran signaled possible closure amid renewed sanctions.",
        category="geopolitics",
        source="Reuters",
        published_at=datetime.now(timezone.utc),
        sources_en=[
            SourceRef(name="Reuters", url="https://en.example.com/0", region="global"),
            SourceRef(name="BBC", url="https://en.example.com/1", region="global"),
        ],
    )
    return ScoredEvent(event=ev, score=10.0)


def _perspective() -> PerspectiveCandidate:
    return PerspectiveCandidate(
        axis="hidden_stakes",
        score=8.0,
        reasoning="日本の原油輸入80%超が同海峡経由で因果連鎖が直接的。",
        evidence_refs=["https://en.example.com/0"],
    )


def _multi_angle() -> MultiAngleAnalysis:
    return MultiAngleAnalysis(
        geopolitical="米イランの構造的緊張を背景に...",
        political_intent="イランは制裁緩和の交渉カードを再構築している...",
        economic_impact="日本の原油輸入80%超が同海峡経由...",
        cultural_context="湾岸地域の意思決定構造はトライバル...",
        media_divergence="Reuters は冷静、Al Jazeera は当事国寄り...",
    )


# ---------- happy path ----------

def test_extract_returns_three_insights_from_fixture():
    se = _scored_event()
    pc = _perspective()
    ma = _multi_angle()
    ctx = build_analysis_context(se, [pc])
    stub = StubLLMClient(_load_fixture("insights_extract_3items"))

    insights = extract_insights(ma, pc, ctx, client=stub)
    assert len(insights) == 3
    assert all(0.0 <= i.importance <= 1.0 for i in insights)
    # importance の値が保たれていること
    assert insights[0].importance == pytest.approx(0.95)
    assert "ホルムズ海峡" in insights[0].text
    # evidence_refs がリストで保持されている
    assert insights[0].evidence_refs == [
        "https://en.example.com/0",
        "https://en.example.com/2",
    ]


def test_extract_calls_llm_once():
    se = _scored_event()
    pc = _perspective()
    ma = _multi_angle()
    ctx = build_analysis_context(se, [pc])
    stub = StubLLMClient(_load_fixture("insights_extract_3items"))

    extract_insights(ma, pc, ctx, client=stub)
    assert len(stub.prompts) == 1


def test_extract_prompt_includes_multi_angle_text():
    se = _scored_event()
    pc = _perspective()
    ma = _multi_angle()
    ctx = build_analysis_context(se, [pc])
    stub = StubLLMClient(_load_fixture("insights_extract_3items"))

    extract_insights(ma, pc, ctx, client=stub)
    prompt = stub.prompts[0]
    assert "hidden_stakes" in prompt
    assert "米イラン" in prompt  # geopolitical
    assert "湾岸" in prompt       # cultural_context


# ---------- truncation / clamping ----------

def test_extract_truncates_to_max_5_by_importance():
    """LLM が 6 個返したとき、importance 上位 5 個だけ残る。"""
    payload = {
        "insights": [
            {"text": f"insight #{i}", "importance": 0.5 + i * 0.05, "evidence_refs": []}
            for i in range(6)
        ],
    }
    stub = StubLLMClient(json.dumps(payload))
    se = _scored_event()
    pc = _perspective()
    ma = _multi_angle()
    ctx = build_analysis_context(se, [pc])

    insights = extract_insights(ma, pc, ctx, client=stub)
    assert len(insights) == 5
    # 上位 importance が残ること
    assert insights[0].importance >= insights[-1].importance


def test_extract_warns_when_fewer_than_3_insights(caplog):
    payload = {
        "insights": [
            {"text": "only one insight", "importance": 0.7, "evidence_refs": []},
        ],
    }
    stub = StubLLMClient(json.dumps(payload))
    se = _scored_event()
    pc = _perspective()
    ma = _multi_angle()
    ctx = build_analysis_context(se, [pc])

    with caplog.at_level("WARNING"):
        insights = extract_insights(ma, pc, ctx, client=stub)
    assert len(insights) == 1


def test_extract_handles_code_fenced_response():
    fenced = "```json\n" + _load_fixture("insights_extract_3items") + "\n```"
    stub = StubLLMClient(fenced)
    se = _scored_event()
    pc = _perspective()
    ma = _multi_angle()
    ctx = build_analysis_context(se, [pc])

    insights = extract_insights(ma, pc, ctx, client=stub)
    assert len(insights) == 3


# ---------- error paths ----------

def test_extract_raises_when_response_not_object():
    stub = StubLLMClient('["not", "a", "dict"]')
    se = _scored_event()
    pc = _perspective()
    ma = _multi_angle()
    ctx = build_analysis_context(se, [pc])
    with pytest.raises(ValueError):
        extract_insights(ma, pc, ctx, client=stub)


def test_extract_raises_when_insights_key_missing():
    stub = StubLLMClient(json.dumps({"foo": "bar"}))
    se = _scored_event()
    pc = _perspective()
    ma = _multi_angle()
    ctx = build_analysis_context(se, [pc])
    with pytest.raises(ValueError):
        extract_insights(ma, pc, ctx, client=stub)


def test_extract_skips_invalid_items_but_keeps_valid():
    payload = {
        "insights": [
            {"text": "valid", "importance": 0.7, "evidence_refs": ["a"]},
            {"text": ""},                  # 空 text → skip
            {"importance": 0.9},            # text 欠落 → skip
            "not even a dict",              # skip
            {"text": "another valid", "importance": 0.8, "evidence_refs": []},
        ],
    }
    stub = StubLLMClient(json.dumps(payload))
    se = _scored_event()
    pc = _perspective()
    ma = _multi_angle()
    ctx = build_analysis_context(se, [pc])

    insights = extract_insights(ma, pc, ctx, client=stub)
    assert len(insights) == 2
    assert insights[0].text == "valid"
    assert insights[1].text == "another valid"


def test_extract_raises_when_no_client_available(monkeypatch):
    monkeypatch.setattr(
        "src.analysis.insight_extractor.get_analysis_llm_client",
        lambda: None,
    )
    se = _scored_event()
    pc = _perspective()
    ma = _multi_angle()
    ctx = build_analysis_context(se, [pc])
    with pytest.raises(RuntimeError):
        extract_insights(ma, pc, ctx, client=None)


# ---------- helpers ----------

def test_coerce_importance_float_preserved():
    assert _coerce_importance(0.85) == pytest.approx(0.85)


def test_coerce_importance_clamps_negative():
    assert _coerce_importance(-0.3) == 0.0


def test_coerce_importance_clamps_above_one_when_already_normalized():
    assert _coerce_importance(1.4) == 1.0


def test_coerce_importance_rescales_percentage_style():
    # 0〜100 で返すケース
    assert _coerce_importance(90) == pytest.approx(0.9)


def test_coerce_importance_str_numeric():
    assert _coerce_importance("0.7") == pytest.approx(0.7)


def test_coerce_importance_non_numeric_falls_back_to_half():
    assert _coerce_importance("high") == 0.5
    assert _coerce_importance(None) == 0.5


def test_coerce_importance_bool_falls_back():
    assert _coerce_importance(True) == 0.5


def test_coerce_evidence_refs_handles_various_inputs():
    assert _coerce_evidence_refs(None) == []
    assert _coerce_evidence_refs(["a", "b"]) == ["a", "b"]
    assert _coerce_evidence_refs("only") == ["only"]
    assert _coerce_evidence_refs("") == []
    assert _coerce_evidence_refs([1, None, "x"]) == ["1", "x"]


def test_parse_insight_item_returns_none_for_invalid():
    assert _parse_insight_item("not a dict") is None
    assert _parse_insight_item({}) is None
    assert _parse_insight_item({"text": "   "}) is None
