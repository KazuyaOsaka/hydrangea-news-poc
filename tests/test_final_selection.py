"""Regression tests for the final_selection stage (Pass 1: Slot-1 Selection Integrity).

Verified behaviours:
  1. Judged flagship wins over a scheduler-chosen not_judged candidate.
  2. Generation is blocked when judge ran but no eligible judged candidate exists.
  3. When judge did NOT run, the scheduler's choice passes through unchanged.
  4. EN-only blind_spot_global with low indirect_japan_impact_score is ineligible.
  5. EN-only blind_spot_global with high indirect_japan_impact_score IS eligible.
  6. linked_jp_global with JP+EN sources is eligible regardless of ijai.
  7. publishability_class not in {linked_jp_global, blind_spot_global} is ineligible.
  8. Judge error (judge_error set) is treated as not-judged — ineligible.
  9. First eligible candidate in effective-score order is selected.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.shared.models import GeminiJudgeResult, NewsEvent, ScoredEvent, SourceRef
from src.main import (
    _find_eligible_judged_slot1,
    _FINAL_SELECTION_INDIRECT_JAPAN_THRESHOLD,
    _ELIGIBLE_PUBLISHABILITY,
)


# ── helpers ───────────────────────────────────────────────────────────────────

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


def _en_src(name: str = "Reuters") -> SourceRef:
    return SourceRef(
        name=name, url=f"https://{name.lower()}.com/1", title="x",
        language="en", country="US", region="global",
    )


def _jp_src(name: str = "NHK") -> SourceRef:
    return SourceRef(
        name=name, url=f"https://{name.lower()}.or.jp/1", title="x",
        language="ja", country="JP", region="japan",
    )


def _make_scored(
    event_id: str = "s-001",
    score: float = 70.0,
    primary_bucket: str = "coverage_gap",
    sources_jp: list[SourceRef] | None = None,
    sources_en: list[SourceRef] | None = None,
    judge_result: GeminiJudgeResult | None = None,
    **event_kwargs,
) -> ScoredEvent:
    event = _make_event(
        event_id,
        sources_jp=sources_jp or [],
        sources_en=sources_en or [],
        **event_kwargs,
    )
    return ScoredEvent(
        event=event,
        score=score,
        score_breakdown={},
        primary_tier="Tier 2",
        editorial_tags=[],
        primary_bucket=primary_bucket,
        judge_result=judge_result,
    )


def _make_judge(
    publishability_class: str = "linked_jp_global",
    indirect_japan_impact_score_judge: float = 7.0,
    divergence_score: float = 6.0,
    judge_error: str | None = None,
) -> GeminiJudgeResult:
    return GeminiJudgeResult(
        publishability_class=publishability_class,
        indirect_japan_impact_score_judge=indirect_japan_impact_score_judge,
        divergence_score=divergence_score,
        blind_spot_global_score=5.0,
        authority_signal_score=6.0,
        confidence=0.8,
        requires_more_evidence=False,
        hard_claims_supported=True,
        judge_error=judge_error,
    )


# ── Test class ────────────────────────────────────────────────────────────────

class TestFindEligibleJudgedSlot1:

    # ── 1. Judged flagship beats not_judged scheduler choice ─────────────────

    def test_judged_flagship_selected_over_not_judged(self):
        """A judged linked_jp_global candidate should win over a not_judged candidate."""
        not_judged = _make_scored(
            event_id="not-judged-001",
            score=90.0,
            sources_en=[_en_src()],
        )
        judged_flagship = _make_scored(
            event_id="judged-001",
            score=80.0,
            sources_jp=[_jp_src()],
            sources_en=[_en_src()],
            judge_result=_make_judge("linked_jp_global"),
        )
        all_ranked = [not_judged, judged_flagship]
        judge_results = {"judged-001": judged_flagship.judge_result}  # type: ignore[index]

        selected, reason = _find_eligible_judged_slot1(all_ranked, judge_results)

        assert selected is not None
        assert selected.event.id == "judged-001"
        assert "linked_jp_global" in reason

    # ── 2. Block when judge ran but no eligible candidate ────────────────────

    def test_blocks_when_no_eligible_judged_candidate(self):
        """If judge ran but all judged candidates are ineligible, return (None, block_reason)."""
        # Only insufficient_evidence judged candidate
        ineligible = _make_scored(
            event_id="ineligible-001",
            score=80.0,
            sources_en=[_en_src()],
            judge_result=_make_judge("insufficient_evidence"),
        )
        judge_results = {"ineligible-001": ineligible.judge_result}  # type: ignore[index]
        all_ranked = [ineligible]

        selected, reason = _find_eligible_judged_slot1(all_ranked, judge_results)

        assert selected is None
        assert "no_eligible_judged_flagship" in reason

    # ── 3. No-judge flow: returns (None, "judge_not_run") ───────────────────

    def test_no_judge_returns_judge_not_run(self):
        """When judge_results is empty, signal judge_not_run without touching ranked list."""
        candidate = _make_scored("e-001", score=85.0, sources_en=[_en_src()])
        selected, reason = _find_eligible_judged_slot1([candidate], judge_results={})

        assert selected is None
        assert reason == "judge_not_run"

    # ── 4. EN-only blind_spot_global with low ijai is ineligible ────────────

    def test_en_only_blind_spot_low_ijai_ineligible(self):
        """EN-only blind_spot_global with indirect_japan_impact_score_judge < threshold → blocked."""
        low_ijai = _FINAL_SELECTION_INDIRECT_JAPAN_THRESHOLD - 0.1
        candidate = _make_scored(
            event_id="bsg-low-ijai",
            score=80.0,
            sources_en=[_en_src()],
            judge_result=_make_judge("blind_spot_global", indirect_japan_impact_score_judge=low_ijai),
        )
        judge_results = {"bsg-low-ijai": candidate.judge_result}  # type: ignore[index]

        selected, reason = _find_eligible_judged_slot1([candidate], judge_results)

        assert selected is None, (
            f"Expected None (low ijai={low_ijai} < threshold={_FINAL_SELECTION_INDIRECT_JAPAN_THRESHOLD}), "
            f"got {selected}"
        )

    # ── 5. EN-only blind_spot_global with high ijai IS eligible ─────────────

    def test_en_only_blind_spot_high_ijai_eligible(self):
        """EN-only blind_spot_global with indirect_japan_impact_score_judge >= threshold → eligible."""
        high_ijai = _FINAL_SELECTION_INDIRECT_JAPAN_THRESHOLD
        candidate = _make_scored(
            event_id="bsg-high-ijai",
            score=80.0,
            sources_en=[_en_src()],
            judge_result=_make_judge("blind_spot_global", indirect_japan_impact_score_judge=high_ijai),
        )
        judge_results = {"bsg-high-ijai": candidate.judge_result}  # type: ignore[index]

        selected, reason = _find_eligible_judged_slot1([candidate], judge_results)

        assert selected is not None
        assert selected.event.id == "bsg-high-ijai"

    # ── 6. linked_jp_global with JP+EN sources is eligible ──────────────────

    def test_linked_jp_global_with_jp_sources_eligible(self):
        """linked_jp_global candidate with JP+EN sources is always eligible."""
        candidate = _make_scored(
            event_id="ljg-001",
            score=85.0,
            sources_jp=[_jp_src()],
            sources_en=[_en_src()],
            judge_result=_make_judge("linked_jp_global", indirect_japan_impact_score_judge=0.0),
        )
        judge_results = {"ljg-001": candidate.judge_result}  # type: ignore[index]

        selected, reason = _find_eligible_judged_slot1([candidate], judge_results)

        assert selected is not None
        assert selected.event.id == "ljg-001"

    # ── 7. investigate_more / jp_only not in eligible set ───────────────────

    @pytest.mark.parametrize("pub_class", ["investigate_more", "jp_only", "insufficient_evidence"])
    def test_ineligible_publishability_classes_blocked(self, pub_class: str):
        """publishability_class not in {linked_jp_global, blind_spot_global} → ineligible."""
        candidate = _make_scored(
            event_id=f"cls-{pub_class}",
            score=75.0,
            sources_en=[_en_src()],
            judge_result=_make_judge(pub_class),
        )
        judge_results = {candidate.event.id: candidate.judge_result}  # type: ignore[index]

        selected, reason = _find_eligible_judged_slot1([candidate], judge_results)

        assert selected is None

    # ── 8. judge_error → treated as not eligible ────────────────────────────

    def test_judge_error_candidate_is_ineligible(self):
        """A candidate whose judge_result has judge_error set is ineligible."""
        errored = _make_scored(
            event_id="judge-error-001",
            score=90.0,
            sources_en=[_en_src()],
            judge_result=_make_judge("linked_jp_global", judge_error="gemini_503"),
        )
        judge_results = {"judge-error-001": errored.judge_result}  # type: ignore[index]

        selected, reason = _find_eligible_judged_slot1([errored], judge_results)

        assert selected is None

    # ── 9. Picks first eligible in effective-score order ────────────────────

    def test_picks_highest_scoring_eligible_candidate(self):
        """When multiple eligible judged candidates exist, the highest-score one wins."""
        lower = _make_scored(
            event_id="lower-001",
            score=70.0,
            sources_jp=[_jp_src()],
            sources_en=[_en_src()],
            judge_result=_make_judge("linked_jp_global"),
        )
        higher = _make_scored(
            event_id="higher-001",
            score=85.0,
            sources_jp=[_jp_src()],
            sources_en=[_en_src()],
            judge_result=_make_judge("linked_jp_global"),
        )
        # all_ranked is sorted by effective_score desc
        all_ranked = [higher, lower]
        judge_results = {
            "lower-001": lower.judge_result,  # type: ignore[index]
            "higher-001": higher.judge_result,  # type: ignore[index]
        }

        selected, reason = _find_eligible_judged_slot1(all_ranked, judge_results)

        assert selected is not None
        assert selected.event.id == "higher-001", (
            "Should select the highest-score eligible candidate first in the list"
        )

    # ── 10. Eligible PUBLISHABILITY constant matches spec ────────────────────

    def test_eligible_publishability_set(self):
        """_ELIGIBLE_PUBLISHABILITY contains exactly {linked_jp_global, blind_spot_global}."""
        assert _ELIGIBLE_PUBLISHABILITY == frozenset({"linked_jp_global", "blind_spot_global"})

    # ── 11. Threshold is at least 5.0 (spec guard) ──────────────────────────

    def test_indirect_japan_threshold_is_at_least_5(self):
        """The indirect Japan threshold for EN-only blind_spot must be >= 5.0 per spec."""
        assert _FINAL_SELECTION_INDIRECT_JAPAN_THRESHOLD >= 5.0

    # ── 12. EN-only linked_jp_global (no JP sources) is ineligible ──────────

    def test_en_only_linked_jp_global_ineligible(self):
        """EN-only candidate with linked_jp_global (no JP sources) cannot be slot-1
        because the spec requires blind_spot_global for JP-source-count==0."""
        candidate = _make_scored(
            event_id="en-only-ljg",
            score=90.0,
            sources_en=[_en_src()],  # no JP sources
            judge_result=_make_judge("linked_jp_global", indirect_japan_impact_score_judge=9.0),
        )
        judge_results = {"en-only-ljg": candidate.judge_result}  # type: ignore[index]

        selected, reason = _find_eligible_judged_slot1([candidate], judge_results)

        assert selected is None, (
            "EN-only linked_jp_global should be ineligible "
            "(JP sources=0 requires blind_spot_global)"
        )

    # ── 13. Skips not_judged candidates in all_ranked ───────────────────────

    def test_skips_not_judged_candidates(self):
        """Candidates without judge_result must not be selected."""
        not_judged_top = _make_scored(
            event_id="not-judged-top",
            score=100.0,
            sources_jp=[_jp_src()],
            sources_en=[_en_src()],
        )
        judged_lower = _make_scored(
            event_id="judged-lower",
            score=80.0,
            sources_jp=[_jp_src()],
            sources_en=[_en_src()],
            judge_result=_make_judge("linked_jp_global"),
        )
        all_ranked = [not_judged_top, judged_lower]
        judge_results = {"judged-lower": judged_lower.judge_result}  # type: ignore[index]

        selected, reason = _find_eligible_judged_slot1(all_ranked, judge_results)

        assert selected is not None
        assert selected.event.id == "judged-lower", (
            "Should skip not_judged top candidate and select the judged one"
        )
