"""Pass D-1: Publish Mode Budget Partition tests.

Guarantees:
  1. publish_mode stops exploratory LLM calls when day_remaining <= publish_reserve_calls
  2. research_mode can spend the full day budget without reserve
  3. slot-1 candidate in publish_mode still gets judge/script/article budget
  4. run_summary / BudgetTracker observability fields are populated correctly
"""
from __future__ import annotations

import pytest

from src.budget import BudgetTracker


# ── helpers ───────────────────────────────────────────────────────────────────

def _tracker(
    *,
    run_budget: int = 12,
    day_budget: int = 20,
    day_calls_so_far: int = 0,
    mode: str = "publish_mode",
    publish_reserve_calls: int = 6,
) -> BudgetTracker:
    return BudgetTracker(
        run_budget=run_budget,
        day_budget=day_budget,
        day_calls_so_far=day_calls_so_far,
        mode=mode,
        publish_reserve_calls=publish_reserve_calls,
    )


# ── 1. publish_mode stops exploration at reserve threshold ───────────────────

class TestPublishModeStopsExploration:
    """Exploration calls must stop before eating into the publish reserve."""

    def test_can_afford_exploration_true_above_threshold(self):
        """day_remaining > publish_reserve → exploration allowed."""
        b = _tracker(day_budget=10, day_calls_so_far=0, publish_reserve_calls=6)
        # day_remaining = 10 > 6
        assert b.can_afford_exploration() is True

    def test_can_afford_exploration_false_at_threshold(self):
        """day_remaining == publish_reserve → exploration NOT allowed (strict >)."""
        b = _tracker(day_budget=10, day_calls_so_far=4, publish_reserve_calls=6)
        # day_remaining = 6 == 6 → not strictly greater
        assert b.can_afford_exploration() is False

    def test_can_afford_exploration_false_below_threshold(self):
        """day_remaining < publish_reserve → exploration NOT allowed."""
        b = _tracker(day_budget=10, day_calls_so_far=6, publish_reserve_calls=6)
        # day_remaining = 4 < 6
        assert b.can_afford_exploration() is False

    def test_can_afford_judge_blocked_at_threshold(self):
        """can_afford_judge returns False and sets stopped flag when reserve reached."""
        b = _tracker(day_budget=10, day_calls_so_far=4, publish_reserve_calls=6)
        assert b.can_afford_judge() is False
        assert b.stopped_exploration_due_to_publish_reserve is True

    def test_can_afford_viral_filter_blocked_at_threshold(self):
        """can_afford_viral_filter returns False when reserve reached."""
        b = _tracker(day_budget=10, day_calls_so_far=4, publish_reserve_calls=6)
        assert b.can_afford_viral_filter() is False
        assert b.stopped_exploration_due_to_publish_reserve is True

    def test_can_afford_cluster_pair_blocked_at_threshold(self):
        """can_afford_cluster_pair returns False when reserve reached."""
        b = _tracker(day_budget=10, day_calls_so_far=4, publish_reserve_calls=6)
        assert b.can_afford_cluster_pair() is False
        assert b.stopped_exploration_due_to_publish_reserve is True

    def test_can_use_cluster_merge_blocked_at_threshold(self):
        """can_use_cluster_merge delegates to can_afford_cluster_pair."""
        b = _tracker(day_budget=10, day_calls_so_far=4, publish_reserve_calls=6)
        assert b.can_use_cluster_merge() is False

    def test_stopped_flag_not_set_before_threshold(self):
        """Flag must not be set when budget is still above reserve."""
        b = _tracker(day_budget=10, day_calls_so_far=0, publish_reserve_calls=6)
        _ = b.can_afford_judge()
        assert b.stopped_exploration_due_to_publish_reserve is False

    def test_stopped_flag_set_on_first_blocked_call(self):
        """Flag is set the first time an exploration call is blocked by reserve."""
        b = _tracker(day_budget=10, day_calls_so_far=5, publish_reserve_calls=6)
        # day_remaining = 5 < 6 — judge should be blocked
        b.can_afford_judge()
        assert b.stopped_exploration_due_to_publish_reserve is True

    def test_exploration_stops_mid_session(self):
        """Simulate a run: 3 exploration calls consume budget, 4th is blocked."""
        b = _tracker(day_budget=10, day_calls_so_far=0, publish_reserve_calls=6)
        # Spend down to 7 remaining (3 exploration calls)
        for _ in range(3):
            assert b.can_afford_judge() is True
            b.record_call("judge")
        # day_remaining = 7, still > 6 — one more is borderline
        assert b.can_afford_judge() is True
        b.record_call("judge")
        # day_remaining = 6 == 6 → next call blocked
        assert b.can_afford_judge() is False
        assert b.stopped_exploration_due_to_publish_reserve is True

    def test_publish_reserve_preserved_property(self):
        """publish_reserve_preserved True while day_remaining >= reserve."""
        b = _tracker(day_budget=10, day_calls_so_far=0, publish_reserve_calls=6)
        assert b.publish_reserve_preserved is True
        # Spend until day_remaining = 6
        for _ in range(4):
            b.record_call("judge")
        assert b.publish_reserve_preserved is True
        # Spend one more → day_remaining = 5 < 6
        b.record_call("script")
        assert b.publish_reserve_preserved is False


# ── 2. research_mode can spend the full budget without reserve ───────────────

class TestResearchModeFullBudget:
    """research_mode must never block exploration due to publish reserve."""

    def test_research_mode_allows_exploration_below_reserve(self):
        """day_remaining < publish_reserve still allows exploration in research_mode."""
        b = _tracker(
            day_budget=10, day_calls_so_far=6,
            mode="research_mode", publish_reserve_calls=6,
        )
        # day_remaining = 4 < 6, but research_mode only requires >= 1
        assert b.can_afford_exploration() is True

    def test_research_mode_allows_judge_below_reserve(self):
        b = _tracker(
            run_budget=12, day_budget=10, day_calls_so_far=6,
            mode="research_mode", publish_reserve_calls=6,
        )
        assert b.can_afford_judge() is True

    def test_research_mode_allows_viral_filter_below_reserve(self):
        b = _tracker(
            run_budget=12, day_budget=10, day_calls_so_far=6,
            mode="research_mode", publish_reserve_calls=6,
        )
        assert b.can_afford_viral_filter() is True

    def test_research_mode_allows_cluster_pair_below_reserve(self):
        b = _tracker(
            run_budget=12, day_budget=10, day_calls_so_far=6,
            mode="research_mode", publish_reserve_calls=6,
        )
        assert b.can_afford_cluster_pair() is True

    def test_research_mode_stops_only_on_zero_day_remaining(self):
        """In research_mode, exploration stops only when day budget is exhausted."""
        b = _tracker(
            run_budget=12, day_budget=5, day_calls_so_far=4,
            mode="research_mode", publish_reserve_calls=6,
        )
        # day_remaining = 1 → still allowed
        assert b.can_afford_exploration() is True
        b.record_call("judge")
        # day_remaining = 0 → blocked
        assert b.can_afford_exploration() is False

    def test_research_mode_never_sets_stopped_flag(self):
        """stopped_exploration_due_to_publish_reserve must not be set in research_mode."""
        b = _tracker(
            run_budget=12, day_budget=10, day_calls_so_far=9,
            mode="research_mode", publish_reserve_calls=6,
        )
        # day_remaining = 1, below reserve — check exploration
        b.can_afford_judge()
        assert b.stopped_exploration_due_to_publish_reserve is False

    def test_research_mode_can_spend_all_day_budget(self):
        """Simulation: research_mode drains full day budget exploration calls."""
        b = _tracker(
            run_budget=50, day_budget=10, day_calls_so_far=0,
            mode="research_mode", publish_reserve_calls=6,
        )
        for i in range(10):
            assert b.can_afford_exploration() is True, f"iteration {i}"
            b.record_call("judge")
        # Exhausted
        assert b.can_afford_exploration() is False


# ── 3. slot-1 candidate in publish_mode still gets production budget ─────────

class TestSlot1ProductionBudgetPreserved:
    """Generation (script/article) must remain possible while publish reserve is intact."""

    def test_can_afford_generation_while_reserve_intact(self):
        """can_afford_generation succeeds even when exploration is blocked by reserve."""
        b = _tracker(day_budget=10, day_calls_so_far=4, publish_reserve_calls=6)
        # day_remaining = 6 — exploration blocked, but generation OK
        assert b.can_afford_exploration() is False
        assert b.can_afford_generation() is True

    def test_can_use_script_llm_while_reserve_intact(self):
        b = _tracker(day_budget=10, day_calls_so_far=4, publish_reserve_calls=6)
        assert b.can_use_script_llm() is True

    def test_can_use_article_llm_while_reserve_intact(self):
        b = _tracker(day_budget=10, day_calls_so_far=4, publish_reserve_calls=6)
        assert b.can_use_article_llm() is True

    def test_generation_not_blocked_at_reserve_threshold(self):
        """Script + article can still execute when day_remaining == publish_reserve."""
        b = _tracker(day_budget=6, day_calls_so_far=0, publish_reserve_calls=6)
        # day_remaining == 6 == publish_reserve; exploration blocked but generation OK
        assert b.can_afford_exploration() is False
        assert b.can_afford_generation() is True
        b.record_call("script")
        assert b.can_afford_generation() is True
        b.record_call("article")
        # day_remaining = 4 — still enough
        assert b.can_afford_generation() is True

    def test_slot1_budget_guaranteed_with_reserve_intact(self):
        """slot1_budget_guaranteed True when day_remaining >= 4 and run_remaining >= 1."""
        b = _tracker(run_budget=6, day_budget=10, day_calls_so_far=4, publish_reserve_calls=6)
        # day_remaining = 6 >= 4, run_remaining = 6 >= 1
        assert b.slot1_budget_guaranteed is True

    def test_slot1_budget_not_guaranteed_when_day_exhausted(self):
        """slot1_budget_guaranteed False when day_remaining < 4."""
        b = _tracker(run_budget=6, day_budget=10, day_calls_so_far=8, publish_reserve_calls=6)
        # day_remaining = 2 < 4
        assert b.slot1_budget_guaranteed is False

    def test_reserve_still_protects_after_partial_exploration(self):
        """After valid exploration, reserve boundary is enforced and generation succeeds."""
        b = _tracker(
            run_budget=12, day_budget=12, day_calls_so_far=0, publish_reserve_calls=6
        )
        # Exploration phase: 6 calls bring day_remaining to 6 (= reserve)
        for _ in range(6):
            assert b.can_afford_judge() is True
            b.record_call("judge")
        # Next exploration call is blocked
        assert b.can_afford_judge() is False
        # But generation proceeds
        assert b.can_afford_generation() is True
        b.record_call("script")
        assert b.can_afford_generation() is True
        b.record_call("article")
        # After production: day_remaining = 4 (still usable)
        assert b.day_remaining == 4


# ── 4. run_summary / report fields populated ─────────────────────────────────

class TestObservabilityFields:
    """BudgetTracker must populate all fields required for run_summary and report."""

    def test_mode_property(self):
        b = _tracker(mode="publish_mode")
        assert b.mode == "publish_mode"

        b2 = _tracker(mode="research_mode")
        assert b2.mode == "research_mode"

    def test_publish_reserve_calls_property(self):
        b = _tracker(publish_reserve_calls=8)
        assert b.publish_reserve_calls == 8

    def test_exploration_budget_used_tracks_exploration_calls(self):
        b = _tracker()
        b.record_call("judge")
        b.record_call("viral_filter")
        b.record_call("cluster_post_merge")
        b.record_call("script")   # not exploration
        b.record_call("article")  # not exploration
        assert b.exploration_budget_used == 3

    def test_exploration_budget_used_excludes_generation_calls(self):
        b = _tracker()
        b.record_call("script")
        b.record_call("article")
        assert b.exploration_budget_used == 0

    def test_to_publish_mode_summary_keys(self):
        """to_publish_mode_summary must contain all 7 required keys."""
        b = _tracker(
            day_budget=20, day_calls_so_far=0,
            mode="publish_mode", publish_reserve_calls=6,
        )
        summary = b.to_publish_mode_summary()
        required_keys = {
            "run_mode",
            "daily_budget_total",
            "exploration_budget_used",
            "publish_reserve_budget",
            "publish_reserve_preserved",
            "stopped_exploration_due_to_publish_reserve",
            "slot1_budget_guaranteed",
        }
        assert required_keys <= summary.keys(), (
            f"Missing keys: {required_keys - summary.keys()}"
        )

    def test_to_publish_mode_summary_values_correct(self):
        b = _tracker(
            run_budget=12, day_budget=20, day_calls_so_far=5,
            mode="publish_mode", publish_reserve_calls=6,
        )
        b.record_call("judge")   # exploration
        b.record_call("judge")   # exploration
        # day_remaining = 20 - 5 - 2 = 13; publish_reserve_preserved = (13 >= 6) = True
        summary = b.to_publish_mode_summary()
        assert summary["run_mode"] == "publish_mode"
        assert summary["daily_budget_total"] == 20
        assert summary["exploration_budget_used"] == 2
        assert summary["publish_reserve_budget"] == 6
        assert summary["publish_reserve_preserved"] is True
        assert summary["stopped_exploration_due_to_publish_reserve"] is False

    def test_to_publish_mode_summary_stopped_flag_reflected(self):
        b = _tracker(day_budget=10, day_calls_so_far=4, publish_reserve_calls=6)
        # Trigger the stop
        b.can_afford_judge()
        summary = b.to_publish_mode_summary()
        assert summary["stopped_exploration_due_to_publish_reserve"] is True
        assert summary["publish_reserve_preserved"] is True  # reserve is still intact (6 remaining)

    def test_default_publish_reserve_calls_is_6(self):
        """Default publish_reserve_calls must equal DEFAULT_PUBLISH_RESERVE_CALLS = 6."""
        b = BudgetTracker(run_budget=12, day_budget=120, day_calls_so_far=0)
        assert b.publish_reserve_calls == BudgetTracker.DEFAULT_PUBLISH_RESERVE_CALLS
        assert b.publish_reserve_calls == 6

    def test_default_mode_is_publish_mode(self):
        """Default mode must be publish_mode."""
        b = BudgetTracker(run_budget=12, day_budget=120, day_calls_so_far=0)
        assert b.mode == "publish_mode"
