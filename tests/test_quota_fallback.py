"""Regression tests for Pass 2A: Gemini Judge Quota Resilience / Quota-Aware Final Selection.

Verified behaviours:
  1. One judged success + one quota_exhausted candidate: success candidate wins normally.
  2. All judge calls quota_exhausted: quota fallback selects best JP+overseas pre-judge candidate.
  3. Quota fallback selects strongest JP+overseas pre-judge candidate (highest score).
  4. JP-only candidate cannot slip through quota fallback.
  5. run_summary judge_summary shows quota fallback fields correctly.
  6. 429 is recorded as quota_exhausted, not ordinary insufficient_evidence.
  7. Candidate failed by quota error is eligible for fallback (it IS the pre-judge candidate).
  8. Candidate with parse_error does NOT trigger quota fallback.
  9. Cross-lang support required — candidate without it is rejected.
 10. Appraisal eligibility required — candidate without eligible appraisal is rejected.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.shared.models import GeminiJudgeResult, NewsEvent, ScoredEvent, SourceRef
from src.main import (
    _find_eligible_judged_slot1,
    _find_quota_fallback_slot1,
    _build_judge_summary,
    _QUOTA_FALLBACK_ELIGIBLE_APPRAISALS,
    _QUOTA_FALLBACK_ERROR_TYPES,
)
from src.triage.gemini_judge import _classify_judge_error


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
    primary_bucket: str = "politics_economy",
    appraisal_type: str | None = "Structural Why",
    sources_jp: list[SourceRef] | None = None,
    sources_en: list[SourceRef] | None = None,
    judge_result: GeminiJudgeResult | None = None,
    cross_lang_bonus: float = 3.0,
    **event_kwargs,
) -> ScoredEvent:
    jp = sources_jp if sources_jp is not None else [_jp_src()]
    en = sources_en if sources_en is not None else [_en_src()]
    event = _make_event(event_id, sources_jp=jp, sources_en=en, **event_kwargs)
    se = ScoredEvent(
        event=event,
        score=score,
        score_breakdown={"cross_lang_bonus": cross_lang_bonus} if cross_lang_bonus else {},
        primary_tier="Tier 2",
        editorial_tags=[],
        primary_bucket=primary_bucket,
        appraisal_type=appraisal_type,
        judge_result=judge_result,
    )
    return se


def _make_judge_result(
    publishability_class: str = "linked_jp_global",
    judge_error: str | None = None,
    judge_error_type: str | None = None,
) -> GeminiJudgeResult:
    return GeminiJudgeResult(
        publishability_class=publishability_class,
        indirect_japan_impact_score_judge=7.0,
        divergence_score=6.0,
        blind_spot_global_score=5.0,
        authority_signal_score=6.0,
        confidence=0.8,
        requires_more_evidence=False,
        hard_claims_supported=True,
        judge_error=judge_error,
        judge_error_type=judge_error_type,
    )


def _quota_error_result(event_id: str = "quota-e-001") -> GeminiJudgeResult:
    return GeminiJudgeResult(
        judged_event_id=event_id,
        judged_at="2026-04-15T04:00:00+00:00",
        judge_error="429 RESOURCE_EXHAUSTED",
        judge_error_type="quota_exhausted",
        publishability_class="insufficient_evidence",
        requires_more_evidence=True,
        hard_claims_supported=False,
    )


# ── Test class ────────────────────────────────────────────────────────────────

class TestQuotaErrorClassification:
    """Task 1: 429 is classified as quota_exhausted, not ordinary insufficient_evidence."""

    def test_429_resource_exhausted_classified_as_quota_exhausted(self):
        """A 429 RESOURCE_EXHAUSTED exception must produce judge_error_type='quota_exhausted'."""
        class FakeExc(Exception):
            pass

        exc = FakeExc("429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'status': 'RESOURCE_EXHAUSTED'}}")
        assert _classify_judge_error(exc) == "quota_exhausted"

    def test_503_unavailable_classified_as_temporary_unavailable(self):
        class FakeExc(Exception):
            pass
        exc = FakeExc("503 UNAVAILABLE. The model is temporarily unavailable.")
        assert _classify_judge_error(exc) == "temporary_unavailable"

    def test_json_decode_error_classified_as_parse_error(self):
        import json
        exc = json.JSONDecodeError("Expecting value", "", 0)
        assert _classify_judge_error(exc) == "parse_error"

    def test_unknown_error_classified_as_unknown(self):
        exc = RuntimeError("Something completely unexpected happened")
        assert _classify_judge_error(exc) == "unknown_error"

    def test_quota_error_type_stored_in_judge_result(self):
        """judge_result.judge_error_type must be 'quota_exhausted' on 429 errors."""
        jr = _quota_error_result()
        assert jr.judge_error_type == "quota_exhausted"
        assert jr.publishability_class == "insufficient_evidence"
        assert jr.judge_error is not None


class TestQuotaFallbackSelection:
    """Task 3: Quota fallback selects strongest JP+overseas pre-judge candidate."""

    def test_no_quota_errors_returns_none(self):
        """If no quota errors in judge_results, fallback is not triggered."""
        se = _make_scored("e-001", score=80.0)
        jr = _make_judge_result("insufficient_evidence")
        se.judge_result = jr
        judge_results = {"e-001": jr}

        result, reason = _find_quota_fallback_slot1([se], judge_results)

        assert result is None
        assert "no_quota_errors" in reason

    def test_quota_fallback_selects_candidate_that_failed_with_quota(self):
        """A candidate that failed with quota_exhausted can be selected as fallback."""
        jr = _quota_error_result("e-001")
        se = _make_scored("e-001", score=80.0, appraisal_type="Structural Why")
        se.judge_result = jr

        judge_results = {"e-001": jr}
        result, reason = _find_quota_fallback_slot1([se], judge_results)

        assert result is not None
        assert result.event.id == "e-001"
        assert "quota_fallback" in reason

    def test_quota_fallback_picks_highest_scoring_eligible_candidate(self):
        """When multiple candidates qualify, the highest-scoring one wins."""
        jr_quota = _quota_error_result("quota-e")

        low = _make_scored("low-001", score=60.0)
        low.judge_result = _quota_error_result("low-001")

        high = _make_scored("high-001", score=90.0)
        high.judge_result = _quota_error_result("high-001")

        # Also add a not-judged candidate with mid score
        mid_not_judged = _make_scored("mid-nj", score=75.0)

        all_ranked = [high, mid_not_judged, low]
        judge_results = {
            "high-001": high.judge_result,
            "low-001": low.judge_result,
        }

        result, reason = _find_quota_fallback_slot1(all_ranked, judge_results)

        assert result is not None
        assert result.event.id == "high-001", (
            "Should select highest-scoring eligible candidate"
        )

    def test_quota_fallback_not_triggered_by_non_quota_error(self):
        """A candidate with parse_error does NOT trigger quota fallback."""
        jr = _make_judge_result(
            publishability_class="insufficient_evidence",
            judge_error="JSONDecodeError: bad json",
            judge_error_type="parse_error",
        )
        se = _make_scored("parse-err", score=80.0)
        se.judge_result = jr
        judge_results = {"parse-err": jr}

        result, reason = _find_quota_fallback_slot1([se], judge_results)

        assert result is None
        assert "no_quota_errors" in reason


class TestQuotaFallbackGuardrails:
    """Task 3 guardrails: JP-only and weak candidates cannot slip through."""

    def test_jp_only_candidate_cannot_win_via_quota_fallback(self):
        """A JP-only candidate (no overseas sources) must NOT win via quota fallback."""
        jr = _quota_error_result("jp-only")
        se = _make_scored(
            "jp-only",
            score=90.0,
            sources_jp=[_jp_src()],
            sources_en=[],  # no overseas sources
            appraisal_type="Structural Why",
            cross_lang_bonus=0.0,
        )
        se.judge_result = jr
        judge_results = {"jp-only": jr}

        result, reason = _find_quota_fallback_slot1([se], judge_results)

        assert result is None, (
            "JP-only candidate (no overseas sources) must NEVER win via quota fallback"
        )

    def test_sports_candidate_cannot_win_via_quota_fallback(self):
        """A sports-bucket candidate must be rejected by quota fallback."""
        jr = _quota_error_result("sports-e")
        se = _make_scored(
            "sports-e",
            score=90.0,
            primary_bucket="sports",
            appraisal_type="Structural Why",
        )
        se.judge_result = jr
        judge_results = {"sports-e": jr}

        result, reason = _find_quota_fallback_slot1([se], judge_results)

        assert result is None, "Sports candidates must be excluded from quota fallback"

    def test_no_appraisal_type_candidate_cannot_win_via_quota_fallback(self):
        """A candidate with appraisal_type=None is rejected by quota fallback."""
        jr = _quota_error_result("no-appr")
        se = _make_scored("no-appr", score=90.0, appraisal_type=None)
        se.judge_result = jr
        judge_results = {"no-appr": jr}

        result, reason = _find_quota_fallback_slot1([se], judge_results)

        assert result is None, (
            "Candidate without eligible appraisal type must be rejected"
        )

    def test_ineligible_appraisal_type_rejected(self):
        """A candidate with Personal Stakes appraisal (not in eligible set) is rejected."""
        jr = _quota_error_result("personal-stakes")
        se = _make_scored(
            "personal-stakes", score=90.0, appraisal_type="Personal Stakes"
        )
        se.judge_result = jr
        judge_results = {"personal-stakes": jr}

        result, reason = _find_quota_fallback_slot1([se], judge_results)

        assert result is None

    def test_no_cross_lang_candidate_rejected(self):
        """A candidate without cross-lang support (no cross_lang_bonus, no bilingual sources)."""
        jr = _quota_error_result("no-xl")
        se = _make_scored(
            "no-xl",
            score=90.0,
            appraisal_type="Structural Why",
            cross_lang_bonus=0.0,
        )
        # Force single-locale sources_by_locale
        se.event.sources_by_locale = {
            "japan": se.event.sources_jp,
        }
        se.judge_result = jr
        judge_results = {"no-xl": jr}

        result, reason = _find_quota_fallback_slot1([se], judge_results)

        assert result is None, (
            "Candidate without cross-lang support must be rejected"
        )

    def test_quota_fallback_eligible_appraisals_set(self):
        """_QUOTA_FALLBACK_ELIGIBLE_APPRAISALS contains exactly the required types."""
        assert _QUOTA_FALLBACK_ELIGIBLE_APPRAISALS == frozenset({
            "Structural Why",
            "Perspective Inversion",
            "Media Blind Spot",
            "Blind Spot Global",
        })

    def test_quota_fallback_error_types_set(self):
        """_QUOTA_FALLBACK_ERROR_TYPES contains quota_exhausted, temporary_unavailable, model_not_found.

        Pass 2C: model_not_found added so that a model-registry failure (models.list
        unavailable at startup + invalid requested model) does not hard-block generation.
        """
        assert _QUOTA_FALLBACK_ERROR_TYPES == frozenset({
            "quota_exhausted",
            "temporary_unavailable",
            "model_not_found",
        })


class TestMixedJudgeResults:
    """Task 1 & 2: Mixed scenarios with both success and quota errors."""

    def test_one_judged_success_wins_over_quota_fallback(self):
        """When one candidate succeeds judge, it wins via normal path — fallback not needed."""
        # Successful judge candidate
        jr_success = _make_judge_result("linked_jp_global")
        success_se = _make_scored(
            "success-001", score=85.0,
            sources_jp=[_jp_src()], sources_en=[_en_src()],
        )
        success_se.judge_result = jr_success

        # Quota-failed candidate (higher base score but should not win)
        jr_quota = _quota_error_result("quota-001")
        quota_se = _make_scored(
            "quota-001", score=95.0,
            sources_jp=[_jp_src()], sources_en=[_en_src()],
        )
        quota_se.judge_result = jr_quota

        all_ranked = [quota_se, success_se]
        judge_results = {
            "success-001": jr_success,
            "quota-001": jr_quota,
        }

        # Normal path: should find the successful candidate
        eligible, reason = _find_eligible_judged_slot1(all_ranked, judge_results)
        assert eligible is not None
        assert eligible.event.id == "success-001"
        assert "linked_jp_global" in reason

    def test_all_quota_exhausted_triggers_fallback_if_safe_candidate_exists(self):
        """When all judge calls fail with quota, fallback selects the strong candidate."""
        jr1 = _quota_error_result("q1")
        jr2 = _quota_error_result("q2")

        se1 = _make_scored("q1", score=90.0, appraisal_type="Structural Why")
        se1.judge_result = jr1

        se2 = _make_scored("q2", score=75.0, appraisal_type="Perspective Inversion")
        se2.judge_result = jr2

        all_ranked = [se1, se2]
        judge_results = {"q1": jr1, "q2": jr2}

        # Normal path: no eligible judged flagship
        eligible, reason = _find_eligible_judged_slot1(all_ranked, judge_results)
        assert eligible is None

        # Quota fallback: should find the highest-scoring eligible
        fallback, fb_reason = _find_quota_fallback_slot1(all_ranked, judge_results)
        assert fallback is not None
        assert fallback.event.id == "q1"
        assert "quota_fallback" in fb_reason


class TestRunSummaryObservability:
    """Task 4: run_summary shows quota fallback fields correctly."""

    def test_judge_summary_includes_error_type_counts(self):
        """_build_judge_summary includes judge_error_type_counts."""
        jr_quota = _quota_error_result("q1")
        jr_unavail = _make_judge_result(
            judge_error="503 UNAVAILABLE",
            judge_error_type="temporary_unavailable",
        )

        se1 = _make_scored("q1")
        se1.judge_result = jr_quota
        se2 = _make_scored("q2")
        se2.judge_result = jr_unavail

        judge_results = {"q1": jr_quota, "q2": jr_unavail}
        summary = _build_judge_summary(judge_results, [se1, se2], None, [])

        assert "judge_error_type_counts" in summary
        assert summary["judge_quota_exhausted_count"] == 1
        assert summary["judge_temporary_unavailable_count"] == 1
        assert summary["judge_error_type_counts"].get("quota_exhausted") == 1
        assert summary["judge_error_type_counts"].get("temporary_unavailable") == 1

    def test_judge_summary_fallback_fields_when_fallback_used(self):
        """_build_judge_summary includes fallback fields when fallback was used."""
        jr_quota = _quota_error_result("q1")
        se1 = _make_scored("q1")
        se1.judge_result = jr_quota
        judge_results = {"q1": jr_quota}

        summary = _build_judge_summary(
            judge_results, [se1], se1, [],
            final_selection_fallback_used=True,
            final_selection_fallback_reason="quota_fallback_prejudge:appraisal=Structural Why",
            quota_fallback_candidate_id="q1",
            quota_fallback_candidate_title="Test headline",
        )

        assert summary["final_selection_fallback_used"] is True
        assert summary["final_selection_fallback_reason"] is not None
        assert summary["quota_fallback_candidate_id"] == "q1"
        assert summary["quota_fallback_candidate_title"] == "Test headline"

    def test_judge_summary_fallback_fields_when_no_fallback(self):
        """When fallback not used, fallback fields are False/None."""
        jr = _make_judge_result("linked_jp_global")
        se = _make_scored("normal")
        se.judge_result = jr
        judge_results = {"normal": jr}

        summary = _build_judge_summary(judge_results, [se], se, [])

        assert summary["final_selection_fallback_used"] is False
        assert summary["final_selection_fallback_reason"] is None
        assert summary["quota_fallback_candidate_id"] is None

    def test_judge_summary_no_judge_results_includes_error_fields(self):
        """Even when judge_results is empty, error count fields are present."""
        summary = _build_judge_summary({}, [], None, [])

        assert "judge_error_type_counts" in summary
        assert summary["judge_quota_exhausted_count"] == 0
        assert summary["judge_temporary_unavailable_count"] == 0
        assert summary["final_selection_fallback_used"] is False

    def test_quota_error_not_counted_as_successful_publishability_class(self):
        """Quota errors show as insufficient_evidence in publishability_counts
        but the error_type_counts clearly distinguish the cause."""
        jr = _quota_error_result("q1")
        se = _make_scored("q1")
        se.judge_result = jr
        judge_results = {"q1": jr}

        summary = _build_judge_summary(judge_results, [se], None, [])

        # publishability_class is "insufficient_evidence" (default for error cases)
        # but judge_error_type_counts shows the real cause
        assert "insufficient_evidence" in summary["publishability_class_counts"]
        assert summary["judge_error_type_counts"].get("quota_exhausted") == 1, (
            "429 quota error must be visible in judge_error_type_counts, "
            "not silently merged into insufficient_evidence"
        )


# ── Helpers for coherence gate tests ─────────────────────────────────────────

def _jp_src_titled(title: str, name: str = "NHK") -> SourceRef:
    return SourceRef(
        name=name, url=f"https://{name.lower()}.or.jp/{abs(hash(title)) % 9999}",
        title=title, language="ja", country="JP", region="japan",
    )


def _en_src_titled(title: str, name: str = "Reuters") -> SourceRef:
    return SourceRef(
        name=name, url=f"https://{name.lower()}.com/{abs(hash(title)) % 9999}",
        title=title, language="en", country="US", region="global",
    )


class TestQuotaFallbackCoherenceGate:
    """Pass 2D-2B: coherence gate must also apply on the quota_fallback_prejudge path."""

    def test_good_coherence_fallback_candidate_passes(self):
        """A quota fallback candidate whose JP↔EN content is coherent should be selected."""
        jr = _quota_error_result("e-good-coh")
        se = _make_scored(
            "e-good-coh",
            score=80.0,
            appraisal_type="Structural Why",
            sources_jp=[_jp_src_titled("中国と米国の貿易関税交渉が再開")],
            sources_en=[_en_src_titled("China US trade tariff negotiations resume")],
            title="中国と米国の貿易関税交渉が再開",
        )
        se.judge_result = jr
        judge_results = {"e-good-coh": jr}

        result, reason = _find_quota_fallback_slot1([se], judge_results)

        assert result is not None, (
            "Coherent quota fallback candidate (China/US trade) should be selected"
        )
        assert result.event.id == "e-good-coh"
        assert "quota_fallback" in reason
        # Coherence side effects must be populated
        assert se.coherence_gate_passed is True
        assert se.semantic_coherence_score is not None

    def test_bad_coherence_fallback_candidate_is_blocked(self):
        """A quota fallback candidate that fails coherence gate must NOT be selected."""
        jr = _quota_error_result("e-bad-coh")
        se = _make_scored(
            "e-bad-coh",
            score=90.0,
            appraisal_type="Structural Why",
            # 首相動静 is on the domestic-routine blacklist; EN is about unrelated sports
            sources_jp=[_jp_src_titled("首相動静 2026年4月16日")],
            sources_en=[_en_src_titled("Local sports team wins championship game tournament")],
            title="首相動静 2026年4月16日",
        )
        se.judge_result = jr
        judge_results = {"e-bad-coh": jr}

        result, reason = _find_quota_fallback_slot1([se], judge_results)

        assert result is None, (
            "Incoherent quota fallback candidate (PM schedule vs sports) must be blocked"
        )
        # Coherence side effects prove the gate ran
        assert se.coherence_gate_passed is False
        assert se.semantic_coherence_score is not None
        assert se.coherence_block_reason is not None
        assert "coherence_gate_failed" in se.coherence_block_reason

    def test_run_summary_coherence_fields_populated_on_fallback_path(self):
        """After selecting a quota fallback candidate, slot1 coherence fields must be non-null."""
        from src.main import _build_judge_summary

        jr = _quota_error_result("e-coh-fields")
        se = _make_scored(
            "e-coh-fields",
            score=75.0,
            appraisal_type="Structural Why",
            sources_jp=[_jp_src_titled("中国と米国の貿易関税交渉が再開")],
            sources_en=[_en_src_titled("China US trade tariff negotiations resume")],
            title="中国と米国の貿易関税交渉が再開",
        )
        se.judge_result = jr
        judge_results = {"e-coh-fields": jr}

        # Select the fallback — this runs apply_coherence_gate as a side effect
        result, _ = _find_quota_fallback_slot1([se], judge_results)
        assert result is not None, "Pre-condition: candidate should have been selected"

        # Build judge_summary as _save_run_summary would
        summary = _build_judge_summary(
            judge_results, [se], se, [],
            final_selection_fallback_used=True,
            final_selection_fallback_reason="quota_fallback_prejudge:appraisal=Structural Why",
            quota_fallback_candidate_id="e-coh-fields",
            quota_fallback_candidate_title=se.event.title,
        )

        slot1 = summary["slot1"]
        assert slot1["semantic_coherence_score"] is not None, (
            "slot1.semantic_coherence_score must be set on fallback path"
        )
        assert slot1["coherence_gate_passed"] is True, (
            "slot1.coherence_gate_passed must be True for a selected fallback candidate"
        )
        assert slot1["coherence_block_reason"] is None, (
            "slot1.coherence_block_reason must be None when gate passed"
        )
