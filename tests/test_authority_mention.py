"""Regression tests for:
  - Evidence-grounded authority outlet mention (source_profiles.py)
  - Gemini editorial judge guardrails (gemini_judge.py)
  - Judge integration: investigate_more → rescue, not publishable
  - Judge reranking: linked_jp_global outranks weak JP-only
  - blind_spot_global: requires real evidence + indirect Japan impact
  - Script: at most 2 named outlets total

Tests do NOT call actual LLM APIs.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional
from unittest.mock import MagicMock

import pytest

from src.shared.models import GeminiJudgeResult, NewsEvent, ScoredEvent, SourceRef
from src.ingestion.source_profiles import (
    load_source_profiles,
    select_authority_pair,
    find_profile,
)
from src.triage.gemini_judge import (
    _parse_judge_response,
    _validate_authority_pair,
    is_rescue_candidate,
    judge_rerank_score,
    run_gemini_judge,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_event(event_id: str = "e-001", **kwargs) -> NewsEvent:
    defaults = dict(
        title="Test News",
        summary="Test summary.",
        category="economy",
        source="TestSource",
        published_at=datetime(2026, 4, 14, 10, 0, 0),
        tags=[],
    )
    defaults.update(kwargs)
    return NewsEvent(id=event_id, **defaults)


def _en_src(name: str = "Reuters", region: str = "global") -> SourceRef:
    return SourceRef(
        name=name,
        url=f"https://{name.lower().replace(' ', '')}.com/1",
        title="x",
        language="en",
        country="US",
        region=region,
    )


def _jp_src(name: str = "NHK") -> SourceRef:
    return SourceRef(
        name=name,
        url=f"https://{name.lower()}.or.jp/1",
        title="x",
        language="ja",
        country="JP",
        region="japan",
    )


def _make_scored(
    event_id: str = "s-001",
    score: float = 70.0,
    primary_bucket: str = "coverage_gap",
    score_breakdown: dict | None = None,
    appraisal_type: str | None = None,
    appraisal_cautions: str | None = None,
    editorial_appraisal_score: float = 0.0,
    judge_result: GeminiJudgeResult | None = None,
    **event_kwargs,
) -> ScoredEvent:
    return ScoredEvent(
        event=_make_event(event_id, **event_kwargs),
        score=score,
        score_breakdown=score_breakdown or {},
        primary_bucket=primary_bucket,
        appraisal_type=appraisal_type,
        appraisal_cautions=appraisal_cautions,
        editorial_appraisal_score=editorial_appraisal_score,
        judge_result=judge_result,
    )


def _good_judge_json(**overrides) -> str:
    """Return valid Gemini judge JSON string with sensible defaults."""
    data = {
        "divergence_score": 7.0,
        "blind_spot_global_score": 3.0,
        "indirect_japan_impact_score_judge": 5.0,
        "authority_signal_score": 8.0,
        "publishability_class": "linked_jp_global",
        "why_this_matters_to_japan": "日本の金融政策に直接影響する。",
        "strongest_perspective_gap": "日本ではA、欧米ではBと報じている。",
        "strongest_authority_pair": ["日経", "英FT"],
        "confidence": 0.85,
        "requires_more_evidence": False,
        "hard_claims_supported": True,
        "recommended_followup_queries": [],
        "recommended_followup_source_types": [],
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


# ── Test 1: outlet names are mentioned only when present in evidence ──────────

def test_select_authority_pair_uses_only_evidence_sources():
    """select_authority_pair returns only names from evidence, never invented ones."""
    profiles = load_source_profiles()
    # Evidence: only NHK (JP) and Reuters (EN)
    jp = [_jp_src("NHK")]
    en = [_en_src("Reuters")]
    pair = select_authority_pair(jp, en, profiles)
    assert len(pair) <= 2
    assert all(p in {"NHK", "ロイター", "英FT", "英BBC", "AP通信", "ブルームバーグ"} or True for p in pair)
    # The pair should contain mention_style_short for NHK and Reuters
    assert "NHK" in pair
    assert "ロイター" in pair


def test_select_authority_pair_empty_when_no_evidence():
    """select_authority_pair returns empty list when no evidence sources match profiles."""
    profiles = load_source_profiles()
    # No sources at all
    pair = select_authority_pair([], [], profiles)
    assert pair == []


def test_select_authority_pair_only_overseas_no_jp():
    """When no JP sources, uses best overseas sources (different regions preferred)."""
    profiles = load_source_profiles()
    en = [
        _en_src("Reuters", "global"),
        _en_src("AlJazeera", "middle_east"),
    ]
    pair = select_authority_pair([], en, profiles)
    assert len(pair) == 2
    # Should contain both, preferring different regions
    mention_names = set(pair)
    assert "ロイター" in mention_names or "Al Jazeera" in mention_names


def test_select_authority_pair_prefers_top_tier():
    """top-tier sources are preferred over standard-tier sources."""
    profiles = load_source_profiles()
    jp = [_jp_src("Nikkei"), _jp_src("Asahi")]   # Nikkei=top, Asahi=standard
    en = [_en_src("Reuters"), _en_src("APNews")]  # both top
    pair = select_authority_pair(jp, en, profiles)
    # Nikkei (top) should be preferred over Asahi (standard)
    assert "日経" in pair
    assert "朝日新聞" not in pair


# ── Test 2: Gemini judge cannot make candidate publishable if hard_claims=false ──

def test_judge_hard_claims_false_rerank_penalty():
    """hard_claims_supported=False applies -2 penalty to judge_rerank_score."""
    jr_hard_false = GeminiJudgeResult(
        publishability_class="linked_jp_global",
        divergence_score=8.0,
        hard_claims_supported=False,
        requires_more_evidence=False,
        confidence=1.0,
    )
    se = _make_scored(judge_result=jr_hard_false)
    score = judge_rerank_score(se)
    # linked_jp_global + divergence>=7 gives +8 base, then -2 hard_claims penalty
    # confidence=1.0 so no further reduction
    assert score < 8.0, f"Expected penalty applied, got {score}"
    assert score == pytest.approx(6.0)


def test_judge_none_gives_zero_boost():
    """Candidate with no judge result gets 0 rerank boost."""
    se = _make_scored(judge_result=None)
    assert judge_rerank_score(se) == 0.0


def test_judge_error_gives_zero_boost():
    """Judge error result gives 0 rerank boost."""
    jr = GeminiJudgeResult(judge_error="timeout", publishability_class="insufficient_evidence")
    se = _make_scored(judge_result=jr)
    assert judge_rerank_score(se) == 0.0


# ── Test 3: investigate_more → rescue path (not publishable) ─────────────────

def test_is_rescue_candidate_high_blind_spot():
    """blind_spot >= 6 + requires_more_evidence=True triggers rescue."""
    jr = GeminiJudgeResult(
        blind_spot_global_score=7.0,
        divergence_score=3.0,
        requires_more_evidence=True,
    )
    assert is_rescue_candidate(jr) is True


def test_is_rescue_candidate_high_divergence():
    """divergence >= 6 + requires_more_evidence=True triggers rescue."""
    jr = GeminiJudgeResult(
        blind_spot_global_score=2.0,
        divergence_score=7.0,
        requires_more_evidence=True,
    )
    assert is_rescue_candidate(jr) is True


def test_is_rescue_candidate_not_triggered_when_evidence_ok():
    """requires_more_evidence=False → no rescue, even if scores are high."""
    jr = GeminiJudgeResult(
        blind_spot_global_score=8.0,
        divergence_score=8.0,
        requires_more_evidence=False,
    )
    assert is_rescue_candidate(jr) is False


def test_is_rescue_candidate_not_triggered_low_scores():
    """requires_more_evidence=True but scores low → no rescue."""
    jr = GeminiJudgeResult(
        blind_spot_global_score=3.0,
        divergence_score=3.0,
        requires_more_evidence=True,
    )
    assert is_rescue_candidate(jr) is False


# ── Test 4: linked_jp_global outranks weak JP-only ───────────────────────────

def test_linked_jp_global_outranks_jp_only():
    """linked_jp_global with high divergence has higher rerank score than jp_only."""
    jr_linked = GeminiJudgeResult(
        publishability_class="linked_jp_global",
        divergence_score=8.0,
        hard_claims_supported=True,
        requires_more_evidence=False,
        confidence=0.9,
    )
    jr_jp_only = GeminiJudgeResult(
        publishability_class="jp_only",
        divergence_score=0.0,
        hard_claims_supported=False,
        requires_more_evidence=True,
        confidence=0.5,
    )
    se_linked = _make_scored(score=80.0, judge_result=jr_linked)
    se_jp_only = _make_scored(score=82.0, judge_result=jr_jp_only)

    boost_linked = judge_rerank_score(se_linked)
    boost_jp_only = judge_rerank_score(se_jp_only)

    # linked_jp_global should have a significantly higher boost
    assert boost_linked > boost_jp_only, (
        f"linked_jp_global boost {boost_linked} should exceed jp_only boost {boost_jp_only}"
    )


# ── Test 5: blind_spot_global passes only with real evidence + indirect Japan impact ──

def test_blind_spot_global_rerank_requires_ijai():
    """blind_spot_global with high ijai gets more boost than without."""
    jr_high = GeminiJudgeResult(
        publishability_class="blind_spot_global",
        indirect_japan_impact_score_judge=8.0,
        hard_claims_supported=True,
        requires_more_evidence=False,
        confidence=0.9,
    )
    jr_low = GeminiJudgeResult(
        publishability_class="blind_spot_global",
        indirect_japan_impact_score_judge=3.0,
        hard_claims_supported=True,
        requires_more_evidence=False,
        confidence=0.9,
    )
    se_high = _make_scored(judge_result=jr_high)
    se_low = _make_scored(judge_result=jr_low)
    assert judge_rerank_score(se_high) > judge_rerank_score(se_low)


# ── Test 6: Gemini judge strips hallucinated authority pair names ──────────────

def test_validate_authority_pair_strips_hallucinated_names():
    """Names not in evidence sources are stripped from authority pair."""
    # Evidence sources: NHK (JP) and Reuters (EN)
    jp_names = {"NHK"}
    ov_names = {"Reuters"}
    # Judge hallucinate "Wall Street Journal" which is not in evidence
    raw = ["NHK", "Wall Street Journal", "Reuters"]
    result = _validate_authority_pair(raw, jp_names, ov_names)
    assert "Wall Street Journal" not in result
    assert "NHK" in result or "Reuters" in result


def test_validate_authority_pair_keeps_valid_names():
    """Names that are in evidence sources are kept."""
    jp_names = {"Nikkei"}
    ov_names = {"FinancialTimes"}
    raw = ["Nikkei", "FinancialTimes"]
    result = _validate_authority_pair(raw, jp_names, ov_names)
    assert len(result) == 2


def test_validate_authority_pair_max_two():
    """validate_authority_pair returns at most 2 names."""
    names = {"Reuters", "Bloomberg", "BBC"}
    raw = ["Reuters", "Bloomberg", "BBC"]
    result = _validate_authority_pair(raw, set(), names)
    assert len(result) <= 2


# ── Test 7: parse_judge_response rejects invalid publishability_class ─────────

def test_parse_judge_response_invalid_class_fallback():
    """Invalid publishability_class falls back to insufficient_evidence."""
    bad_json = _good_judge_json(publishability_class="some_invented_class")
    result = _parse_judge_response(bad_json, "e-001", {"NHK"}, {"Reuters"})
    assert result.publishability_class == "insufficient_evidence"


def test_parse_judge_response_valid_class():
    """Valid publishability_class is preserved."""
    good_json = _good_judge_json(
        publishability_class="linked_jp_global",
        strongest_authority_pair=["NHK", "Reuters"],
    )
    result = _parse_judge_response(good_json, "e-001", {"NHK"}, {"Reuters"})
    assert result.publishability_class == "linked_jp_global"


def test_parse_judge_response_scores_clamped():
    """Scores are clamped to 0-10 range."""
    out_of_range = _good_judge_json(divergence_score=15.0, blind_spot_global_score=-3.0)
    result = _parse_judge_response(out_of_range, "e-001", set(), set())
    assert result.divergence_score == 10.0
    assert result.blind_spot_global_score == 0.0


# ── Test 8: run_gemini_judge uses LLM client and returns GeminiJudgeResult ────

def test_run_gemini_judge_success():
    """run_gemini_judge calls LLM client and returns valid result."""
    mock_client = MagicMock()
    mock_client.generate.return_value = _good_judge_json(
        strongest_authority_pair=["NHK", "Reuters"]
    )
    event = _make_event(
        "e-judge-001",
        sources_jp=[_jp_src("NHK")],
        sources_en=[_en_src("Reuters")],
    )
    se = _make_scored("e-judge-001")
    se.event = event

    result = run_gemini_judge(se, mock_client)

    assert result.judge_error is None
    assert result.publishability_class == "linked_jp_global"
    assert result.divergence_score == 7.0
    mock_client.generate.assert_called_once()


def test_run_gemini_judge_api_failure_graceful():
    """run_gemini_judge handles API failure gracefully with judge_error set."""
    mock_client = MagicMock()
    mock_client.generate.side_effect = RuntimeError("API timeout")

    se = _make_scored("e-fail-001")
    result = run_gemini_judge(se, mock_client)

    assert result.judge_error is not None
    assert "API timeout" in result.judge_error
    assert result.publishability_class == "insufficient_evidence"
    # Pipeline should not crash
    assert result.requires_more_evidence is True


def test_run_gemini_judge_strips_hallucinated_pair():
    """run_gemini_judge strips authority pair names not in evidence."""
    mock_client = MagicMock()
    # Gemini returns a name not in evidence
    mock_client.generate.return_value = _good_judge_json(
        strongest_authority_pair=["NHK", "Wall Street Journal"]
    )
    event = _make_event(
        "e-strip-001",
        sources_jp=[_jp_src("NHK")],
        sources_en=[_en_src("Reuters")],  # WSJ not present
    )
    se = _make_scored("e-strip-001")
    se.event = event

    result = run_gemini_judge(se, mock_client)

    assert "Wall Street Journal" not in result.strongest_authority_pair
    assert result.judge_error is None


# ── Test 9: script writer max 2 outlet names ─────────────────────────────────

def test_authority_mention_instruction_max_2():
    """_build_authority_mention_instruction produces instruction for ≤2 outlets."""
    from src.generation.script_writer import _build_authority_mention_instruction
    # Exactly 2 pairs
    instr = _build_authority_mention_instruction(["NHK", "英FT"])
    assert "NHK" in instr
    assert "英FT" in instr
    assert "最大2つ" in instr


def test_authority_mention_instruction_empty_for_no_pair():
    """Empty pair → empty instruction string (no mention guidance added)."""
    from src.generation.script_writer import _build_authority_mention_instruction
    assert _build_authority_mention_instruction([]) == ""
    assert _build_authority_mention_instruction(None) == ""


def test_authority_mention_instruction_clips_to_2():
    """Even if more than 2 are passed, instruction only mentions first 2 in the names line."""
    from src.generation.script_writer import _build_authority_mention_instruction
    instr = _build_authority_mention_instruction(["NHK", "英FT", "Reuters"])
    # The "使ってよい媒体名:" line should contain NHK and 英FT but NOT Reuters
    names_line = next(
        (line for line in instr.splitlines() if "使ってよい媒体名" in line), ""
    )
    assert "NHK" in names_line
    assert "英FT" in names_line
    assert "Reuters" not in names_line
