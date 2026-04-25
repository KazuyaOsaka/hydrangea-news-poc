"""src/analysis/perspective_selector.py のテスト（LLM はモック）。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pytest

from src.analysis.context_builder import AnalysisContext, build_analysis_context
from src.analysis.perspective_selector import (
    _apply_framing_bonus_if_needed,
    llm_select_and_verify_perspective,
    parse_json_response,
    select_perspective,
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


def _scored() -> ScoredEvent:
    ev = NewsEvent(
        id="evt-sel-1",
        title="Global crisis under-reported in Japan",
        summary="Three foreign outlets cover; Japanese media is silent.",
        category="politics",
        source="Reuters",
        published_at=datetime.now(timezone.utc),
        sources_jp=[],
        sources_en=[
            SourceRef(name="Reuters", url="https://en.example.com/0", region="global"),
            SourceRef(name="BBC", url="https://en.example.com/1", region="global"),
            SourceRef(name="AlJazeera", url="https://en.example.com/2", region="middle_east"),
        ],
    )
    return ScoredEvent(event=ev, score=10.0)


def _scored_with_jp() -> ScoredEvent:
    ev = NewsEvent(
        id="evt-sel-2",
        title="Disputed framing event",
        summary="JP says cooperation; foreign says conflict.",
        category="politics",
        source="Reuters",
        published_at=datetime.now(timezone.utc),
        sources_jp=[
            SourceRef(name="Nikkei", url="https://jp.example.com/0", region="japan"),
        ],
        sources_en=[
            SourceRef(name="Reuters", url="https://en.example.com/0", region="global"),
            SourceRef(name="BBC", url="https://en.example.com/1", region="global"),
        ],
    )
    return ScoredEvent(event=ev, score=10.0)


def _candidates_silence_only() -> list[PerspectiveCandidate]:
    return [
        PerspectiveCandidate(
            axis="silence_gap",
            score=9.0,
            reasoning="3 EN sources, 0 JP",
            evidence_refs=["https://en.example.com/0"],
        ),
    ]


def _candidates_silence_and_framing() -> list[PerspectiveCandidate]:
    return [
        PerspectiveCandidate(
            axis="silence_gap",
            score=8.0,
            reasoning="JP=0",
            evidence_refs=["https://en.example.com/0"],
        ),
        PerspectiveCandidate(
            axis="framing_inversion",
            score=7.0,
            reasoning="High perspective gap",
            evidence_refs=["https://en.example.com/0", "https://jp.example.com/0"],
        ),
    ]


# ---------- parse_json_response ----------

def test_parse_strips_code_fence():
    raw = '```json\n{"selected_axis": "silence_gap", "verification": {"actually_holds": true}}\n```'
    parsed = parse_json_response(raw)
    assert parsed["selected_axis"] == "silence_gap"


def test_parse_handles_plain_json():
    raw = '{"selected_axis": "silence_gap"}'
    parsed = parse_json_response(raw)
    assert parsed["selected_axis"] == "silence_gap"


def test_parse_extracts_first_json_block_when_surrounded_by_text():
    raw = 'Sure, here is the JSON: {"selected_axis": "framing_inversion"} (end)'
    parsed = parse_json_response(raw)
    assert parsed["selected_axis"] == "framing_inversion"


def test_parse_raises_on_invalid_json():
    with pytest.raises(json.JSONDecodeError):
        parse_json_response("not even a brace here")


# ---------- llm_select_and_verify_perspective ----------

def test_llm_select_uses_provided_client_and_returns_parsed_dict():
    se = _scored()
    cands = _candidates_silence_only()
    ctx = build_analysis_context(se, cands)
    stub = StubLLMClient(_load_fixture("perspective_select_and_verify_silence_gap"))

    result = llm_select_and_verify_perspective(se, cands, ctx, client=stub)
    assert result["selected_axis"] == "silence_gap"
    assert result["verification"]["actually_holds"] is True
    # プロンプトに候補と背景質問が含まれていることを確認
    assert len(stub.prompts) == 1
    prompt = stub.prompts[0]
    assert "silence_gap" in prompt
    assert "[silence_gap]" in prompt  # background_questions header


def test_llm_select_raises_when_no_candidates():
    se = _scored()
    ctx = AnalysisContext(event_id=se.event.id, channel_id="geo_lens")
    stub = StubLLMClient("{}")
    with pytest.raises(ValueError):
        llm_select_and_verify_perspective(se, [], ctx, client=stub)


# ---------- select_perspective: success path ----------

def test_select_returns_candidate_when_verification_holds():
    se = _scored()
    cands = _candidates_silence_only()
    ctx = build_analysis_context(se, cands)
    stub = StubLLMClient(_load_fixture("perspective_select_and_verify_silence_gap"))

    chosen = select_perspective(se, cands, ctx, client=stub)
    assert chosen is not None
    assert chosen.axis == "silence_gap"
    assert chosen.score == 9.0  # silence_gap には bonus 加算なし


# ---------- select_perspective: fallback path ----------

def test_select_falls_back_when_verification_fails():
    se = _scored_with_jp()
    cands = _candidates_silence_and_framing()
    ctx = build_analysis_context(se, cands)
    stub = StubLLMClient(_load_fixture("perspective_select_and_verify_failed_fallback"))

    chosen = select_perspective(se, cands, ctx, client=stub)
    assert chosen is not None
    assert chosen.axis == "framing_inversion"
    # framing_divergence_bonus +2.0 が加算される
    assert chosen.score == pytest.approx(9.0)
    assert "framing_divergence_bonus" in chosen.reasoning


def test_select_returns_none_when_fallback_axis_not_in_candidates():
    se = _scored_with_jp()
    cands = _candidates_silence_only()  # silence のみ — fallback="framing_inversion" は不在
    ctx = build_analysis_context(se, cands)
    stub = StubLLMClient(_load_fixture("perspective_select_and_verify_failed_fallback"))

    chosen = select_perspective(se, cands, ctx, client=stub)
    assert chosen is None


def test_select_returns_none_on_invalid_axis_and_no_fallback():
    se = _scored()
    cands = _candidates_silence_only()
    ctx = build_analysis_context(se, cands)
    stub = StubLLMClient(json.dumps({
        "selected_axis": "nonexistent_axis",
        "verification": {"actually_holds": True, "notes": "", "confidence": 0.5},
        "fallback_axis_if_failed": None,
    }))

    chosen = select_perspective(se, cands, ctx, client=stub)
    assert chosen is None


def test_select_uses_fallback_when_selected_axis_invalid():
    se = _scored_with_jp()
    cands = _candidates_silence_and_framing()
    ctx = build_analysis_context(se, cands)
    stub = StubLLMClient(json.dumps({
        "selected_axis": "garbage_axis",
        "verification": {"actually_holds": True, "notes": "", "confidence": 0.5},
        "fallback_axis_if_failed": "framing_inversion",
    }))

    chosen = select_perspective(se, cands, ctx, client=stub)
    assert chosen is not None
    assert chosen.axis == "framing_inversion"


def test_select_returns_none_on_llm_exception():
    class FailingClient(LLMClient):
        def generate(self, prompt: str) -> str:
            raise RuntimeError("transient quota issue")

    se = _scored()
    cands = _candidates_silence_only()
    ctx = build_analysis_context(se, cands)
    chosen = select_perspective(se, cands, ctx, client=FailingClient())
    assert chosen is None


def test_select_returns_none_for_empty_candidates():
    se = _scored()
    ctx = AnalysisContext(event_id=se.event.id, channel_id="geo_lens")
    chosen = select_perspective(se, [], ctx, client=StubLLMClient("{}"))
    assert chosen is None


# ---------- framing_divergence_bonus ----------

def test_framing_bonus_applied_to_framing_inversion_only():
    fr = PerspectiveCandidate(
        axis="framing_inversion", score=6.0, reasoning="r", evidence_refs=[]
    )
    boosted = _apply_framing_bonus_if_needed(fr)
    assert boosted.score == pytest.approx(8.0)
    assert "framing_divergence_bonus" in boosted.reasoning


def test_framing_bonus_clamped_to_10():
    fr = PerspectiveCandidate(
        axis="framing_inversion", score=9.5, reasoning="r", evidence_refs=[]
    )
    boosted = _apply_framing_bonus_if_needed(fr)
    assert boosted.score == 10.0


def test_framing_bonus_not_applied_to_other_axes():
    sg = PerspectiveCandidate(
        axis="silence_gap", score=7.0, reasoning="r", evidence_refs=[]
    )
    same = _apply_framing_bonus_if_needed(sg)
    assert same.score == 7.0
    assert same is sg or same.score == sg.score  # 同一 or score 不変
