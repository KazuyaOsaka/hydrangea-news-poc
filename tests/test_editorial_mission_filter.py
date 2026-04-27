"""Tests for Pass C: Editorial Mission Filter (src/triage/editorial_mission_filter.py)

Hydrangea 編集ミッション (= 日本で報じられないニュース、視点が偏ったニュースを
地政学・歴史・文化・政治・経済的背景の解説付きで日本人に届ける) への適合度を
7軸で評価するフィルタのテスト。
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.shared.models import NewsEvent, ScoredEvent, SourceRef
from src.triage.editorial_mission_filter import (
    MISSION_SCORE_THRESHOLD,
    _editorial_mission_prescore,
    apply_editorial_mission_filter,
    build_why_slot1_won_editorially,
)
from src.triage.scoring import compute_score_full


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_event(**kwargs) -> NewsEvent:
    defaults = dict(
        id="test-evt-001",
        title="Test event",
        summary="Test summary",
        category="economy",
        source="test-source",
        published_at=datetime(2026, 4, 27, 9, 0, 0),
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


def _make_scored_event_with_axes(**axes) -> ScoredEvent:
    """既知の axis 値を直接埋めた ScoredEvent を生成する（prescore 計算式の検証用）。"""
    event = _make_event()
    breakdown: dict = {}
    for k, v in axes.items():
        breakdown[f"editorial:{k}"] = float(v)
    return ScoredEvent(
        event=event,
        score=0.0,
        score_breakdown=breakdown,
    )


def _make_budget(run_remaining: int = 10) -> MagicMock:
    budget = MagicMock()
    budget.can_afford_editorial_mission_filter.return_value = run_remaining > 0
    budget.record_call = MagicMock()
    return budget


# ── Tests: Step-1 prescore axis math (per-axis caps) ─────────────────────────

class TestPrescoreAxisCaps:
    """各軸が個別に最大点を超えないことを検証する。"""

    def test_perspective_gap_axis_capped_at_25(self):
        se = _make_scored_event_with_axes(
            perspective_gap_score=100.0,  # 過大入力
            coverage_gap_score=100.0,
        )
        score, bd = _editorial_mission_prescore(se)
        assert bd["perspective_gap"] == 25.0

    def test_geopolitical_axis_capped_at_20(self):
        se = _make_scored_event_with_axes(
            geopolitics_depth_score=100.0,
            breaking_shock_score=100.0,
        )
        score, bd = _editorial_mission_prescore(se)
        assert bd["geopolitical_significance"] == 20.0

    def test_blindspot_axis_capped_at_15(self):
        se = _make_scored_event_with_axes(
            has_jp_view=0.0,
            has_en_view=1.0,
        )
        score, bd = _editorial_mission_prescore(se)
        # has_en and not has_jp → 15.0
        assert bd["blindspot_severity"] == 15.0

    def test_political_intent_axis_capped_at_10(self):
        se = _make_scored_event_with_axes(
            geopolitics_depth_score=100.0,
            breaking_shock_score=100.0,
        )
        _, bd = _editorial_mission_prescore(se)
        assert bd["political_intent"] == 10.0

    def test_hidden_power_axis_capped_at_10(self):
        se = _make_scored_event_with_axes(
            tech_geopolitics_score=100.0,
            geopolitics_depth_score=100.0,
        )
        _, bd = _editorial_mission_prescore(se)
        assert bd["hidden_power_dynamics"] == 10.0

    def test_economic_interests_axis_capped_at_10(self):
        se = _make_scored_event_with_axes(
            big_event_score=100.0,
            indirect_japan_impact_score=100.0,
        )
        _, bd = _editorial_mission_prescore(se)
        assert bd["economic_interests"] == 10.0

    def test_discussion_axis_capped_at_10(self):
        se = _make_scored_event_with_axes(
            mass_appeal_score=100.0,
            breaking_shock_score=100.0,
        )
        _, bd = _editorial_mission_prescore(se)
        assert bd["discussion_potential"] == 10.0


class TestPrescoreFormula:
    """prescore の計算式が設計通りであることを既知入力で検証する。"""

    def test_zero_axes_yield_zero_score(self):
        se = _make_scored_event_with_axes()
        score, bd = _editorial_mission_prescore(se)
        assert score == 0.0
        assert bd["perspective_gap"] == 0.0

    def test_perspective_gap_formula(self):
        """perspective_gap = pg*1.5 + cg*1.0, capped at 25."""
        se = _make_scored_event_with_axes(
            perspective_gap_score=4.0,
            coverage_gap_score=2.0,
        )
        _, bd = _editorial_mission_prescore(se)
        # 4 * 1.5 + 2 * 1.0 = 8.0
        assert bd["perspective_gap"] == 8.0

    def test_geopolitical_formula(self):
        """geopolitical = gd*2.0 + bs*1.0, capped at 20."""
        se = _make_scored_event_with_axes(
            geopolitics_depth_score=3.0,
            breaking_shock_score=2.0,
        )
        _, bd = _editorial_mission_prescore(se)
        # 3 * 2.0 + 2 * 1.0 = 8.0
        assert bd["geopolitical_significance"] == 8.0

    def test_blindspot_jp_view_only_zero(self):
        """日本語視点だけある記事は blindspot=0（海外で報道されてない）。"""
        se = _make_scored_event_with_axes(
            has_jp_view=1.0,
            has_en_view=0.0,
        )
        _, bd = _editorial_mission_prescore(se)
        assert bd["blindspot_severity"] == 0.0

    def test_blindspot_intermediate_tiers(self):
        """has_en_count >= 3, jp_count <= 1 → 12.0"""
        event = _make_event(
            sources_by_locale={
                "en": [
                    SourceRef(name="A", url="http://a"),
                    SourceRef(name="B", url="http://b"),
                    SourceRef(name="C", url="http://c"),
                ],
                "jp": [SourceRef(name="J", url="http://j")],
            }
        )
        se = ScoredEvent(
            event=event, score=0.0,
            score_breakdown={"editorial:has_jp_view": 1.0, "editorial:has_en_view": 1.0},
        )
        _, bd = _editorial_mission_prescore(se)
        assert bd["blindspot_severity"] == 12.0

    def test_total_capped_at_100(self):
        """raw 合計が 100 を超えても score は 100 で頭打ちになる。"""
        se = _make_scored_event_with_axes(
            perspective_gap_score=100.0,
            coverage_gap_score=100.0,
            geopolitics_depth_score=100.0,
            breaking_shock_score=100.0,
            tech_geopolitics_score=100.0,
            big_event_score=100.0,
            mass_appeal_score=100.0,
            indirect_japan_impact_score=100.0,
            has_jp_view=0.0,
            has_en_view=1.0,
        )
        score, _ = _editorial_mission_prescore(se)
        assert score == 100.0

    def test_breakdown_includes_all_seven_axes(self):
        se = _make_scored_event_with_axes()
        _, bd = _editorial_mission_prescore(se)
        for axis in [
            "perspective_gap",
            "geopolitical_significance",
            "blindspot_severity",
            "political_intent",
            "hidden_power_dynamics",
            "economic_interests",
            "discussion_potential",
        ]:
            assert axis in bd
        assert bd["step"] == "prescore"


# ── Tests: integration with apply_editorial_mission_filter ────────────────────

class TestApplyMissionFilterPrescore:

    def test_score_stored_in_score_breakdown(self):
        """editorial_mission_score が score_breakdown に保存される。"""
        event = _make_event(title="Japan economy BOJ", summary="日本経済")
        se = _make_scored_event(event)
        budget = _make_budget(run_remaining=0)
        [se], _ = apply_editorial_mission_filter([se], budget, llm_enabled=False)
        assert "editorial_mission_score" in se.score_breakdown
        assert se.score_breakdown["editorial_mission_score"] == se.editorial_mission_score
        assert "mission_prescore" in se.score_breakdown
        assert "mission_prescore_breakdown" in se.score_breakdown

    def test_score_capped_at_100(self):
        event = _make_event(
            title="日本 Japan BOJ rate hike ceasefire airstrike collapse Ohtani",
            summary="利上げ 円安 inflation tariff sanctions military operation",
            japan_view="日本視点",
            global_view="Global view",
            impact_on_japan="大きな影響",
        )
        se = _make_scored_event(event)
        budget = _make_budget(run_remaining=0)
        [se], _ = apply_editorial_mission_filter([se], budget, llm_enabled=False)
        assert se.editorial_mission_score is not None
        assert se.editorial_mission_score <= 100.0

    def test_higher_perspective_gap_yields_higher_mission_score(self):
        """視点ギャップが大きい記事ほど editorial_mission_score が高くなる。"""
        gap_event = _make_event(
            title="Gaza ceasefire collapse airstrike sanctions",
            summary="Trade war tariff military operation perspective contrast",
            japan_view="日本では経済的影響として報道",
            global_view="Western media frames it as humanitarian crisis",
        )
        plain_event = _make_event(
            id="plain",
            title="Routine company quarterly results",
            summary="Earnings report shows moderate growth",
        )
        gap_se = _make_scored_event(gap_event)
        plain_se = _make_scored_event(plain_event)
        budget = _make_budget(run_remaining=0)
        [gap_se, plain_se], _ = apply_editorial_mission_filter(
            [gap_se, plain_se], budget, llm_enabled=False
        )
        assert gap_se.editorial_mission_score > plain_se.editorial_mission_score


# ── Tests: Threshold gate ──────────────────────────────────────────────────────

class TestThresholdGate:
    def test_below_threshold_sets_rejection_reason(self):
        weak_event = _make_event(
            title="Local small story",
            summary="Some minor event with no relevance",
        )
        se = _make_scored_event(weak_event)
        budget = _make_budget(run_remaining=0)
        # Force a very high threshold so the weak event is always rejected
        [se], _ = apply_editorial_mission_filter(
            [se], budget, score_threshold=200.0, llm_enabled=False
        )
        assert se.why_rejected_before_generation is not None
        assert "editorial_mission_score" in se.why_rejected_before_generation
        assert "threshold" in se.why_rejected_before_generation

    def test_above_threshold_clears_rejection_reason(self):
        strong_event = _make_event(
            title="Gaza Ukraine BRICS sanctions perspective gap",
            summary="Geopolitics breaking ceasefire collapse",
            japan_view="日本語視点",
            global_view="English view",
            impact_on_japan="significant",
        )
        se = _make_scored_event(strong_event)
        budget = _make_budget(run_remaining=0)
        [se], _ = apply_editorial_mission_filter(
            [se], budget, score_threshold=0.0, llm_enabled=False
        )
        assert se.why_rejected_before_generation is None

    def test_summary_counts_correct(self):
        events = [
            _make_event(id=f"e{i}", title=f"Event {i}", summary="summary")
            for i in range(4)
        ]
        scored = [_make_scored_event(e) for e in events]
        budget = _make_budget(run_remaining=0)
        _, summary = apply_editorial_mission_filter(
            scored, budget, score_threshold=200.0, llm_enabled=False
        )
        assert summary["rejected_before_generation"] == 4
        assert summary["passed_threshold"] == 0
        assert summary["total_candidates"] == 4

    def test_empty_input_returns_empty(self):
        budget = _make_budget()
        result, summary = apply_editorial_mission_filter([], budget)
        assert result == []
        assert summary["editorial_mission_filter_applied"] is False

    def test_default_threshold_is_45(self):
        """暫定 threshold が 45.0 であることをロックする。"""
        assert MISSION_SCORE_THRESHOLD == 45.0


# ── Tests: LLM mission scoring ────────────────────────────────────────────────

class TestLLMMissionScoring:
    def _make_mock_llm(self, response_json: str) -> MagicMock:
        client = MagicMock()
        client.generate.return_value = response_json
        return client

    def test_llm_score_replaces_prescore(self):
        """LLM 成功時、editorial_mission_score は LLM 合計値 (0-100) になる。"""
        event = _make_event(
            title="Japan trade tariff", summary="summary",
            japan_view="jp", global_view="en",
        )
        se = _make_scored_event(event)
        budget = _make_budget(run_remaining=5)

        llm = self._make_mock_llm(
            '{"perspective_gap": 20, "geopolitical_significance": 15, '
            '"blindspot_severity": 10, "political_intent": 8, '
            '"hidden_power_dynamics": 7, "economic_interests": 6, '
            '"discussion_potential": 5, "reason": "test"}'
        )
        [se], _ = apply_editorial_mission_filter(
            [se], budget, llm_client=llm, prescore_top_n=5, llm_enabled=True
        )
        # LLM total = 20+15+10+8+7+6+5 = 71
        assert se.editorial_mission_score == pytest.approx(71.0)
        assert se.editorial_mission_breakdown.get("step") == "llm"
        assert se.editorial_mission_breakdown.get("perspective_gap") == 20.0

    def test_llm_failure_falls_back_to_prescore(self):
        """LLM が壊れた JSON を返したら prescore を保持する。"""
        event = _make_event(
            title="Japan trade tariff", summary="summary",
            japan_view="jp", global_view="en",
        )
        # Compute prescore baseline first
        baseline_se = _make_scored_event(event)
        budget0 = _make_budget(run_remaining=0)
        [baseline_se], _ = apply_editorial_mission_filter(
            [baseline_se], budget0, llm_enabled=False
        )
        expected_ps = baseline_se.editorial_mission_score

        # Now run with a broken LLM
        se = _make_scored_event(event)
        llm = self._make_mock_llm("NOT VALID JSON {{{")
        budget2 = _make_budget(run_remaining=5)
        [se], summary = apply_editorial_mission_filter(
            [se], budget2, llm_client=llm, prescore_top_n=5, llm_enabled=True
        )
        assert se.editorial_mission_score == pytest.approx(expected_ps)
        assert summary["llm_failed_count"] == 1
        assert "llm_error" in se.editorial_mission_breakdown

    def test_llm_sub_scores_clamped_to_per_axis_max(self):
        """LLM が各軸の最大点を超えた値を返したらクランプされる。"""
        event = _make_event(title="test", summary="summary")
        se = _make_scored_event(event)
        budget = _make_budget(run_remaining=5)

        llm = self._make_mock_llm(
            '{"perspective_gap": 100, "geopolitical_significance": 100, '
            '"blindspot_severity": 100, "political_intent": 100, '
            '"hidden_power_dynamics": 100, "economic_interests": 100, '
            '"discussion_potential": 100, "reason": "x"}'
        )
        [se], _ = apply_editorial_mission_filter(
            [se], budget, llm_client=llm, prescore_top_n=5, llm_enabled=True
        )
        # 全軸が最大値 = 25+20+15+10+10+10+10 = 100
        assert se.editorial_mission_score == pytest.approx(100.0)
        bd = se.editorial_mission_breakdown
        assert bd["perspective_gap"] == 25.0
        assert bd["geopolitical_significance"] == 20.0
        assert bd["blindspot_severity"] == 15.0
        assert bd["political_intent"] == 10.0
        assert bd["hidden_power_dynamics"] == 10.0
        assert bd["economic_interests"] == 10.0
        assert bd["discussion_potential"] == 10.0

    def test_llm_markdown_fenced_response_parsed(self):
        """```json で囲まれた応答も解釈できる。"""
        event = _make_event(title="Japan trade", summary="s")
        se = _make_scored_event(event)
        budget = _make_budget(run_remaining=5)

        llm = self._make_mock_llm(
            '```json\n'
            '{"perspective_gap": 10, "geopolitical_significance": 5, '
            '"blindspot_severity": 3, "political_intent": 2, '
            '"hidden_power_dynamics": 1, "economic_interests": 1, '
            '"discussion_potential": 1, "reason": "fenced"}\n'
            '```'
        )
        [se], _ = apply_editorial_mission_filter(
            [se], budget, llm_client=llm, prescore_top_n=5, llm_enabled=True
        )
        # 10 + 5 + 3 + 2 + 1 + 1 + 1 = 23
        assert se.editorial_mission_score == pytest.approx(23.0)

    def test_budget_exhausted_stops_llm_early(self):
        """予算が尽きたら残候補は prescore のみになる。"""
        events = [
            _make_event(id=f"e{i}", title=f"Japan event {i}", summary="s")
            for i in range(5)
        ]
        scored = [_make_scored_event(e) for e in events]

        # Budget allows only 1 LLM call
        call_count = 0

        def mock_can_afford():
            nonlocal call_count
            allowed = call_count < 1
            call_count += 1
            return allowed

        budget = MagicMock()
        budget.can_afford_editorial_mission_filter.side_effect = mock_can_afford
        budget.record_call = MagicMock(side_effect=lambda _: None)

        llm = self._make_mock_llm(
            '{"perspective_gap": 10, "geopolitical_significance": 5, '
            '"blindspot_severity": 3, "political_intent": 2, '
            '"hidden_power_dynamics": 1, "economic_interests": 1, '
            '"discussion_potential": 1, "reason": "ok"}'
        )
        _, summary = apply_editorial_mission_filter(
            scored, budget, llm_client=llm, prescore_top_n=10, llm_enabled=True
        )
        assert summary["llm_scored_count"] == 1

    def test_llm_disabled_uses_only_prescore(self):
        event = _make_event(title="test", summary="summary")
        se = _make_scored_event(event)
        llm = MagicMock()
        budget = _make_budget(run_remaining=10)

        [se], summary = apply_editorial_mission_filter(
            [se], budget, llm_client=llm, llm_enabled=False
        )
        llm.generate.assert_not_called()
        assert summary["llm_ran"] is False
        assert summary["llm_scored_count"] == 0


# ── Tests: why_slot1_won_editorially ──────────────────────────────────────────

class TestWhySlot1Won:
    def test_builds_explanation_with_all_fields(self):
        from src.shared.models import GeminiJudgeResult
        event = _make_event(
            title="Gaza Ukraine BRICS",
            summary="Geopolitics impact",
            japan_view="jp view",
            global_view="global view",
            impact_on_japan="large",
        )
        se = _make_scored_event(event)
        se.appraisal_type = "Perspective Inversion"
        se.editorial_appraisal_score = 4.5
        se.editorial_mission_score = 72.0
        se.editorial_mission_breakdown = {
            "step": "prescore",
            "perspective_gap": 20.0,
            "geopolitical_significance": 18.0,
            "blindspot_severity": 12.0,
        }
        se.judge_result = GeminiJudgeResult(
            publishability_class="linked_jp_global",
            divergence_score=8.0,
            blind_spot_global_score=5.0,
            judged_event_id=se.event.id,
            judged_at="2026-04-27T10:00:00Z",
        )

        rationale = build_why_slot1_won_editorially(se)
        assert "Perspective Inversion" in rationale
        assert "72.0" in rationale
        assert "linked_jp_global" in rationale

    def test_returns_na_for_empty_event(self):
        event = _make_event(title="unknown", summary="")
        se = _make_scored_event(event)
        result = build_why_slot1_won_editorially(se)
        # editorial_reason は空でも何かしら入る挙動なので非空
        assert result

    def test_llm_breakdown_included_when_step_is_llm(self):
        event = _make_event(title="test", summary="summary")
        se = _make_scored_event(event)
        se.editorial_mission_score = 55.0
        se.editorial_mission_breakdown = {
            "step": "llm",
            "perspective_gap": 18.0,
            "geopolitical_significance": 15.0,
            "blindspot_severity": 10.0,
            "political_intent": 5.0,
            "hidden_power_dynamics": 3.0,
            "economic_interests": 2.0,
            "discussion_potential": 2.0,
        }
        result = build_why_slot1_won_editorially(se)
        assert "55.0" in result
        assert "pg=" in result
        assert "geo=" in result
