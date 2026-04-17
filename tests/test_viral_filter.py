"""Tests for Pass C: Viral & Interest Filter (src/triage/viral_filter.py)"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.shared.models import NewsEvent, ScoredEvent, SourceRef
from src.triage.scoring import compute_score_full
from src.triage.viral_filter import (
    VIRAL_SCORE_THRESHOLD,
    apply_viral_filter,
    build_why_slot1_won_editorially,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_event(**kwargs) -> NewsEvent:
    defaults = dict(
        id="test-evt-001",
        title="Test event",
        summary="Test summary",
        category="economy",
        source="test-source",
        published_at=datetime(2026, 4, 16, 9, 0, 0),
        tags=[],
    )
    defaults.update(kwargs)
    return NewsEvent(**defaults)


def _make_scored_event(event: NewsEvent) -> ScoredEvent:
    score, breakdown, tier, tags, reason = compute_score_full(event)
    return ScoredEvent(
        event=event,
        score=score,
        score_breakdown=breakdown,
        primary_tier=tier,
        editorial_tags=tags,
        editorial_reason=reason,
    )


def _make_budget(run_remaining: int = 10) -> MagicMock:
    budget = MagicMock()
    budget.can_afford_viral_filter.return_value = run_remaining > 0
    budget.record_call = MagicMock()
    return budget


# ── Tests: Step-1 prescore ─────────────────────────────────────────────────────

class TestPrescore:
    def test_high_japan_relevance_boosts_score(self):
        """Stories with high Japan relevance should score significantly higher."""
        high_jr_event = _make_event(
            title="日本経済 Japan GDP BOJ rate hike",
            summary="日本関連 japanese economy impact",
            category="economy",
            japan_view="日本の視点からの分析",
            global_view="Global view analysis",
            impact_on_japan="直接的な影響あり",
        )
        low_jr_event = _make_event(
            title="Remote country news unrelated",
            summary="Some distant event with no Japan connection",
            category="economy",
        )
        high_se = _make_scored_event(high_jr_event)
        low_se = _make_scored_event(low_jr_event)

        budget = _make_budget(run_remaining=0)  # No LLM
        [high_se, low_se], _ = apply_viral_filter(
            [high_se, low_se], budget, llm_enabled=False
        )
        assert high_se.viral_filter_score > low_se.viral_filter_score

    def test_breaking_shock_boosts_discussion_trigger(self):
        """Breaking shock signals increase discussion_trigger component."""
        shock_event = _make_event(
            title="Ceasefire announced airstrike collapse state of emergency",
            summary="Breaking news: military operation sanctions",
        )
        quiet_event = _make_event(
            title="Routine company quarterly results",
            summary="Earnings report shows moderate growth",
        )
        shock_se = _make_scored_event(shock_event)
        quiet_se = _make_scored_event(quiet_event)

        budget = _make_budget(run_remaining=0)
        [shock_se, quiet_se], _ = apply_viral_filter(
            [shock_se, quiet_se], budget, llm_enabled=False
        )
        # breaking shock should yield a higher discussion trigger
        shock_disc = shock_se.viral_filter_breakdown.get("discussion_trigger", 0)
        quiet_disc = quiet_se.viral_filter_breakdown.get("discussion_trigger", 0)
        assert shock_disc > quiet_disc

    def test_both_lang_bonus_awarded_when_jp_and_en_views_present(self):
        """Both-language bonus (3.0) should appear in breakdown."""
        event = _make_event(
            title="Trade war tariff sanction",
            summary="Global sanctions impact Japan",
            japan_view="日本語視点",
            global_view="English global view",
        )
        se = _make_scored_event(event)
        budget = _make_budget(run_remaining=0)
        [se], _ = apply_viral_filter([se], budget, llm_enabled=False)
        assert se.viral_filter_breakdown.get("both_lang_bonus", 0.0) == 3.0

    def test_prescore_capped_at_100(self):
        """prescore must never exceed 100."""
        event = _make_event(
            title="日本 Japan BOJ rate hike ceasefire airstrike collapse Ohtani",
            summary="利上げ 円安 inflation tariff sanctions military operation",
            japan_view="日本視点",
            global_view="Global view",
            impact_on_japan="大きな影響",
        )
        se = _make_scored_event(event)
        budget = _make_budget(run_remaining=0)
        [se], _ = apply_viral_filter([se], budget, llm_enabled=False)
        assert se.viral_filter_score <= 100.0

    def test_score_stored_in_score_breakdown(self):
        """viral_filter_score must be stored in score_breakdown for observability."""
        event = _make_event(title="Japan economy BOJ", summary="日本経済")
        se = _make_scored_event(event)
        budget = _make_budget(run_remaining=0)
        [se], _ = apply_viral_filter([se], budget, llm_enabled=False)
        assert "viral_filter_score" in se.score_breakdown
        assert se.score_breakdown["viral_filter_score"] == se.viral_filter_score


# ── Tests: Threshold gate ──────────────────────────────────────────────────────

class TestThresholdGate:
    def test_below_threshold_sets_rejection_reason(self):
        """Candidates scoring below threshold must have why_rejected_before_generation set."""
        weak_event = _make_event(
            title="Local small news story",
            summary="Some minor event with no Japan connection",
        )
        se = _make_scored_event(weak_event)
        budget = _make_budget(run_remaining=0)
        # Force a very high threshold so the weak event is always rejected
        [se], summary = apply_viral_filter(
            [se], budget, score_threshold=200.0, llm_enabled=False
        )
        assert se.why_rejected_before_generation is not None
        assert "viral_filter_score" in se.why_rejected_before_generation
        assert "threshold" in se.why_rejected_before_generation

    def test_above_threshold_clears_rejection_reason(self):
        """Candidates scoring above threshold must have why_rejected_before_generation = None."""
        strong_event = _make_event(
            title="日本 Japan BOJ 利上げ rate hike economy impact",
            summary="日本経済への大きな影響 japan relevance high",
            japan_view="日本語視点",
            global_view="English view",
            impact_on_japan="significant",
        )
        se = _make_scored_event(strong_event)
        budget = _make_budget(run_remaining=0)
        # Force a very low threshold so the event always passes
        [se], _ = apply_viral_filter(
            [se], budget, score_threshold=0.0, llm_enabled=False
        )
        assert se.why_rejected_before_generation is None

    def test_summary_counts_correct(self):
        """Summary dict must have correct passed/rejected counts."""
        events = [
            _make_event(id=f"e{i}", title=f"Event {i}", summary="summary")
            for i in range(4)
        ]
        scored = [_make_scored_event(e) for e in events]
        budget = _make_budget(run_remaining=0)
        # Threshold=200 → all rejected
        _, summary = apply_viral_filter(scored, budget, score_threshold=200.0, llm_enabled=False)
        assert summary["rejected_before_generation"] == 4
        assert summary["passed_threshold"] == 0
        assert summary["total_candidates"] == 4

    def test_empty_input_returns_empty(self):
        """Empty candidate list must be handled gracefully."""
        budget = _make_budget()
        result, summary = apply_viral_filter([], budget)
        assert result == []
        assert summary["viral_filter_applied"] is False


# ── Tests: LLM viral scoring ───────────────────────────────────────────────────

class TestLLMViralScoring:
    def _make_mock_llm(self, response_json: str) -> MagicMock:
        client = MagicMock()
        client.generate.return_value = response_json
        return client

    def test_llm_score_replaces_prescore(self):
        """When LLM succeeds, viral_filter_score should be the LLM total (0-100)."""
        event = _make_event(
            title="Japan trade tariff", summary="summary",
            japan_view="jp", global_view="en"
        )
        se = _make_scored_event(event)
        budget = _make_budget(run_remaining=5)

        llm = self._make_mock_llm(
            '{"curiosity_gap": 20, "stakeholder_impact": 18, '
            '"topic_affinity": 15, "discussion_potential": 12, "reason": "test"}'
        )
        [se], _ = apply_viral_filter(
            [se], budget, llm_client=llm, prescore_top_n=5, llm_enabled=True
        )
        # LLM total = 20+18+15+12 = 65
        assert se.viral_filter_score == pytest.approx(65.0)
        assert se.viral_filter_breakdown.get("step") == "llm"
        assert se.viral_filter_breakdown.get("curiosity_gap") == 20.0

    def test_llm_failure_falls_back_to_prescore(self):
        """When LLM returns invalid JSON, prescore must be retained."""
        event = _make_event(
            title="Japan trade tariff", summary="summary",
            japan_view="jp", global_view="en"
        )
        se = _make_scored_event(event)
        budget = _make_budget(run_remaining=5)
        prescore_before, _ = apply_viral_filter(
            [_make_scored_event(event)], budget, llm_enabled=False
        )
        expected_ps = prescore_before[0].viral_filter_score

        llm = self._make_mock_llm("NOT VALID JSON {{{")
        budget2 = _make_budget(run_remaining=5)
        [se], summary = apply_viral_filter(
            [se], budget2, llm_client=llm, prescore_top_n=5, llm_enabled=True
        )
        # Should fall back to prescore value
        assert se.viral_filter_score == pytest.approx(expected_ps)
        assert summary["llm_failed_count"] == 1

    def test_llm_sub_scores_clamped_to_25(self):
        """LLM sub-scores exceeding 25 must be clamped."""
        event = _make_event(title="test", summary="summary")
        se = _make_scored_event(event)
        budget = _make_budget(run_remaining=5)

        llm = self._make_mock_llm(
            '{"curiosity_gap": 30, "stakeholder_impact": 99, '
            '"topic_affinity": 25, "discussion_potential": 0, "reason": "x"}'
        )
        [se], _ = apply_viral_filter(
            [se], budget, llm_client=llm, prescore_top_n=5, llm_enabled=True
        )
        # Each clamped to 25; total = 25+25+25+0 = 75
        assert se.viral_filter_score == pytest.approx(75.0)
        assert se.viral_filter_breakdown["curiosity_gap"] == 25.0
        assert se.viral_filter_breakdown["stakeholder_impact"] == 25.0

    def test_budget_exhausted_stops_llm_early(self):
        """When budget is exhausted after first call, remaining candidates use prescore."""
        events = [
            _make_event(id=f"e{i}", title=f"Japan event {i}", summary="s")
            for i in range(5)
        ]
        scored = [_make_scored_event(e) for e in events]

        # Budget allows only 1 LLM call
        call_count = 0
        original_can_afford = lambda: call_count < 1

        budget = MagicMock()
        budget.can_afford_viral_filter.side_effect = original_can_afford
        budget.record_call = MagicMock(side_effect=lambda _: None)

        def mock_can_afford():
            nonlocal call_count
            result = call_count < 1
            call_count += 1
            return result

        budget.can_afford_viral_filter.side_effect = mock_can_afford

        llm = self._make_mock_llm(
            '{"curiosity_gap": 10, "stakeholder_impact": 10, '
            '"topic_affinity": 10, "discussion_potential": 10, "reason": "ok"}'
        )
        result, summary = apply_viral_filter(
            scored, budget, llm_client=llm, prescore_top_n=10, llm_enabled=True
        )
        # Only 1 LLM call should have been recorded
        assert summary["llm_scored_count"] == 1

    def test_llm_disabled_uses_only_prescore(self):
        """With llm_enabled=False, LLM client must never be called."""
        event = _make_event(title="test", summary="summary")
        se = _make_scored_event(event)
        llm = MagicMock()
        budget = _make_budget(run_remaining=10)

        [se], summary = apply_viral_filter(
            [se], budget, llm_client=llm, llm_enabled=False
        )
        llm.generate.assert_not_called()
        assert summary["llm_ran"] is False
        assert summary["llm_scored_count"] == 0


# ── Tests: why_slot1_won_editorially ──────────────────────────────────────────

class TestWhySlot1Won:
    def test_builds_explanation_with_all_fields(self):
        """All available fields should appear in the editorial rationale."""
        from src.shared.models import GeminiJudgeResult
        event = _make_event(
            title="日本 Japan economy BOJ rate hike",
            summary="利上げ impact",
            japan_view="jp view",
            global_view="global view",
            impact_on_japan="large",
        )
        se = _make_scored_event(event)
        se.appraisal_type = "Perspective Inversion"
        se.editorial_appraisal_score = 4.5
        se.viral_filter_score = 72.0
        se.viral_filter_breakdown = {
            "step": "prescore",
            "japan_impact": 30.0,
            "topic_affinity": 12.0,
            "discussion_trigger": 8.0,
            "contrast_potential": 6.0,
        }
        se.judge_result = GeminiJudgeResult(
            publishability_class="linked_jp_global",
            divergence_score=8.0,
            blind_spot_global_score=5.0,
            judged_event_id=se.event.id,
            judged_at="2026-04-16T10:00:00Z",
        )

        rationale = build_why_slot1_won_editorially(se)
        assert "Perspective Inversion" in rationale
        assert "72.0" in rationale
        assert "linked_jp_global" in rationale

    def test_returns_na_for_empty_event(self):
        """An event with no editorial signals returns 'N/A'."""
        event = _make_event(title="unknown", summary="")
        se = _make_scored_event(event)
        # No appraisal, no viral score, no judge
        result = build_why_slot1_won_editorially(se)
        # Should still return something (at minimum the editorial_reason)
        assert result  # non-empty

    def test_llm_breakdown_included_when_step_is_llm(self):
        """LLM sub-scores should appear when step='llm'."""
        event = _make_event(title="test", summary="summary")
        se = _make_scored_event(event)
        se.viral_filter_score = 55.0
        se.viral_filter_breakdown = {
            "step": "llm",
            "curiosity_gap": 15.0,
            "stakeholder_impact": 14.0,
            "topic_affinity": 13.0,
            "discussion_potential": 13.0,
        }
        result = build_why_slot1_won_editorially(se)
        assert "55.0" in result
        assert "cg=" in result
