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


def test_select_falls_back_to_top_score_when_fallback_axis_not_in_candidates():
    """F-3 改修後: fallback_axis_if_failed が Top3 にない場合、Step2 で最高スコア候補を採用。

    旧挙動 (F-2 まで): None を返していた → analysis_result=None で動画化失敗。
    新挙動 (F-3 から): Top3 内の最高スコア候補（ここでは silence_gap）にフォールバック。
    """
    se = _scored_with_jp()
    cands = _candidates_silence_only()  # silence のみ — fallback="framing_inversion" は不在
    ctx = build_analysis_context(se, cands)
    stub = StubLLMClient(_load_fixture("perspective_select_and_verify_failed_fallback"))

    chosen = select_perspective(se, cands, ctx, client=stub)
    assert chosen is not None
    assert chosen.axis == "silence_gap"


def test_select_falls_back_to_top_score_on_invalid_axis_and_no_fallback():
    """F-3 改修後: selected_axis が無効 + fallback=None でも Step2 で最高スコア採用。

    旧挙動 (F-2 まで): None を返していた。
    新挙動 (F-3 から): candidates の最高スコア (silence_gap) にフォールバック。
    """
    se = _scored()
    cands = _candidates_silence_only()
    ctx = build_analysis_context(se, cands)
    stub = StubLLMClient(json.dumps({
        "selected_axis": "nonexistent_axis",
        "verification": {"actually_holds": True, "notes": "", "confidence": 0.5},
        "fallback_axis_if_failed": None,
    }))

    chosen = select_perspective(se, cands, ctx, client=stub)
    assert chosen is not None
    assert chosen.axis == "silence_gap"


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


def test_select_falls_back_to_top_score_on_llm_exception():
    """F-3 改修後: LLM 呼び出しが例外で失敗しても Step2 で最高スコア候補を採用。

    旧挙動 (F-2 まで): None を返していた。
    新挙動 (F-3 から): candidates が残っているなら必ず採用する（quota/transient 失敗時の救済）。
    """
    class FailingClient(LLMClient):
        def generate(self, prompt: str) -> str:
            raise RuntimeError("transient quota issue")

    se = _scored()
    cands = _candidates_silence_only()
    ctx = build_analysis_context(se, cands)
    chosen = select_perspective(se, cands, ctx, client=FailingClient())
    assert chosen is not None
    assert chosen.axis == "silence_gap"


def test_select_returns_none_for_empty_candidates():
    """F-3 改修後も candidates が空のときだけは None を返す（最終安全網 Step3）。"""
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


# ---------- F-3: 3段階フォールバックチェーンのテスト ----------
#
# F-2 試運転で Slot-2 / Slot-3 の analysis_result が None になり動画化失敗した問題を受け、
# select_perspective() に Step2 フォールバック (Top3 内最高スコア候補採用) を追加した。
# candidates が 1 件以上あれば必ず PerspectiveCandidate を返すようになる。


def _candidates_three_axes() -> list[PerspectiveCandidate]:
    return [
        PerspectiveCandidate(
            axis="framing_inversion",
            score=8.0,  # Top1
            reasoning="JP says cooperation; foreign says conflict.",
            evidence_refs=["https://en.example.com/0"],
        ),
        PerspectiveCandidate(
            axis="silence_gap",
            score=6.0,
            reasoning="JP=0, EN=3.",
            evidence_refs=["https://en.example.com/1"],
        ),
        PerspectiveCandidate(
            axis="cultural_blindspot",
            score=4.0,
            reasoning="cultural reading gap",
            evidence_refs=["https://en.example.com/2"],
        ),
    ]


class TestPerspectiveSelectorFallbackChain:
    """F-3: 3段階フォールバックチェーンのテスト。"""

    def test_step1_normal_selection(self):
        """通常: LLM の selected_axis が Top3 にあり actually_holds=True なら採用。"""
        se = _scored_with_jp()
        cands = _candidates_three_axes()
        ctx = build_analysis_context(se, cands)
        stub = StubLLMClient(json.dumps({
            "selected_axis": "framing_inversion",
            "reasoning": "test",
            "evidence_for_selection": ["https://en.example.com/0"],
            "verification": {"actually_holds": True, "notes": "ok", "confidence": 0.9},
            "fallback_axis_if_failed": "silence_gap",
        }))

        chosen = select_perspective(se, cands, ctx, client=stub)
        assert chosen is not None
        assert chosen.axis == "framing_inversion"

    def test_step1_fallback_to_axis_if_failed(self):
        """LLM 検証失敗時、fallback_axis_if_failed が Top3 にあれば採用。"""
        se = _scored_with_jp()
        cands = _candidates_three_axes()
        ctx = build_analysis_context(se, cands)
        stub = StubLLMClient(json.dumps({
            "selected_axis": "framing_inversion",
            "reasoning": "test",
            "evidence_for_selection": ["https://en.example.com/0"],
            "verification": {"actually_holds": False, "notes": "failed", "confidence": 0.3},
            "fallback_axis_if_failed": "silence_gap",
        }))

        chosen = select_perspective(se, cands, ctx, client=stub)
        assert chosen is not None
        assert chosen.axis == "silence_gap"

    def test_step2_fallback_to_top_score_when_invalid_axis(self):
        """★F-3: LLM が Top3 外の axis (hidden_stakes) を選び、fallback_axis_if_failed も
        Top3 にない場合、Top3 内最高スコア候補 (framing_inversion=8.0) を採用する。

        試運転4 で実際に発生したケース:
            [PerspectiveSelector] LLM selected axis 'hidden_stakes' not in Top3
        """
        se = _scored_with_jp()
        cands = _candidates_three_axes()
        ctx = build_analysis_context(se, cands)
        stub = StubLLMClient(json.dumps({
            "selected_axis": "hidden_stakes",  # Top3 外
            "reasoning": "test",
            "evidence_for_selection": ["https://en.example.com/0"],
            "verification": {"actually_holds": True, "notes": "ok", "confidence": 0.9},
            "fallback_axis_if_failed": "hidden_stakes",  # こちらも Top3 外
        }))

        chosen = select_perspective(se, cands, ctx, client=stub)

        # F-3: Top3 内の最高スコア候補が採用される
        assert chosen is not None
        assert chosen.axis == "framing_inversion"  # スコア最高 (8.0)
        # framing_divergence_bonus +2.0 が後段で加算される
        assert chosen.score == pytest.approx(10.0)

    def test_step2_fallback_when_both_axis_and_fallback_invalid(self):
        """LLM の selected_axis も fallback_axis_if_failed も Top3 にない場合、Top1 採用。"""
        se = _scored()
        cands = [
            PerspectiveCandidate(
                axis="silence_gap", score=7.5, reasoning="r", evidence_refs=[]
            ),
            PerspectiveCandidate(
                axis="framing_inversion", score=5.0, reasoning="r", evidence_refs=[]
            ),
        ]
        ctx = build_analysis_context(se, cands)
        stub = StubLLMClient(json.dumps({
            "selected_axis": "hidden_stakes",
            "reasoning": "test",
            "evidence_for_selection": [],
            "verification": {"actually_holds": False, "notes": "failed", "confidence": 0.3},
            "fallback_axis_if_failed": "unknown_axis_2",
        }))

        chosen = select_perspective(se, cands, ctx, client=stub)
        assert chosen is not None
        assert chosen.axis == "silence_gap"  # スコア 7.5 で最高

    def test_step2_fallback_when_fallback_axis_is_none(self):
        """LLM の fallback_axis_if_failed が None でも Step2 で Top3 最高スコアにフォールバック。"""
        se = _scored()
        cands = [
            PerspectiveCandidate(
                axis="framing_inversion", score=6.0, reasoning="r", evidence_refs=[]
            ),
            PerspectiveCandidate(
                axis="silence_gap", score=4.0, reasoning="r", evidence_refs=[]
            ),
        ]
        ctx = build_analysis_context(se, cands)
        stub = StubLLMClient(json.dumps({
            "selected_axis": "hidden_stakes",
            "reasoning": "test",
            "evidence_for_selection": [],
            "verification": {"actually_holds": False, "notes": "failed", "confidence": 0.3},
            "fallback_axis_if_failed": None,
        }))

        chosen = select_perspective(se, cands, ctx, client=stub)
        assert chosen is not None
        assert chosen.axis == "framing_inversion"

    def test_step3_returns_none_only_when_candidates_empty(self):
        """★F-3: candidates が空の場合のみ None を返す（最終安全網 Step3）。

        この経路では LLM 呼び出しは行われない（候補が無いと前段で判定）。
        """
        se = _scored()
        ctx = AnalysisContext(event_id=se.event.id, channel_id="geo_lens")
        stub = StubLLMClient("{}")

        chosen = select_perspective(se, [], ctx, client=stub)
        assert chosen is None
        # LLM は呼ばれていないこと
        assert stub.prompts == []
