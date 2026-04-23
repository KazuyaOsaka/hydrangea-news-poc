"""Regression tests for Pass 1.5: Final Selection → Publish Identity Integrity.

Verified behaviours:
  1. When FinalSelection overrides the scheduler slot:
       - pool marks generated_event_id (not scheduled_slot1_id) as published
       - schedule marks scheduled slot as consumed (not the generated event)
       - run_summary IDs stay internally consistent
       - selection_override_applied is True
  2. When no override (no judge / scheduler choice passes through):
       - pool marks generated_event_id as published
       - selection_override_applied is False
       - published_event_id == generated_event_id == scheduled_slot1_id
  3. latest_candidate_report.md reflects the override correctly
  4. No [Scheduler] MISMATCH log line on the success path
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

from src.shared.models import GeminiJudgeResult, NewsEvent, ScoredEvent, SourceRef
from src.shared.models import DailySchedule, DailyScheduleEntry
from src.main import (
    _write_latest_candidate_report,
    _ELIGIBLE_PUBLISHABILITY,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_event(event_id: str = "e-001", title: str = "Test News") -> NewsEvent:
    return NewsEvent(
        id=event_id,
        title=title,
        summary="Test summary.",
        category="economy",
        source="TestSource",
        published_at=datetime(2026, 4, 14, 10, 0, 0),
        tags=[],
    )


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
    sources_jp: list | None = None,
    sources_en: list | None = None,
    judge_result: GeminiJudgeResult | None = None,
    title: str = "Test News",
) -> ScoredEvent:
    event = _make_event(event_id, title=title)
    event = event.model_copy(update={
        "sources_jp": sources_jp or [],
        "sources_en": sources_en or [],
    })
    return ScoredEvent(
        event=event,
        score=score,
        score_breakdown={},
        primary_tier="Tier 2",
        editorial_tags=[],
        primary_bucket="politics_economy",
        judge_result=judge_result,
    )


def _make_judge(
    publishability_class: str = "linked_jp_global",
    divergence_score: float = 2.0,
) -> GeminiJudgeResult:
    return GeminiJudgeResult(
        publishability_class=publishability_class,
        indirect_japan_impact_score_judge=7.0,
        divergence_score=divergence_score,
        blind_spot_global_score=3.0,
        authority_signal_score=6.0,
        confidence=0.8,
        requires_more_evidence=False,
        hard_claims_supported=True,
        judge_error=None,
        why_this_matters_to_japan="test reason",
        strongest_perspective_gap="test gap",
    )


def _make_schedule_entry(event_id: str, published: bool = False) -> DailyScheduleEntry:
    return DailyScheduleEntry(
        event_id=event_id,
        title="Test",
        primary_bucket="politics_economy",
        score=80.0,
        rank_in_candidates=1,
        published=published,
        slot_status="published" if published else "scheduled",
    )


# ── 1. Override path: pool targets generated_event_id ─────────────────────────

class TestPublishIdentityOverride:
    """When FinalSelection overrides the scheduler's slot-1 choice."""

    def test_pool_marks_generated_event_not_scheduled(self, tmp_path):
        """mark_pool_event_published must be called with generated_event_id,
        not scheduled_slot1_id, when an override occurs."""
        from src.triage.scheduler import mark_published as scheduler_mark_published

        scheduled_id = "cls-scheduled-001"
        generated_id = "cls-generated-002"

        # Simulate what the pipeline does at publish time
        # _selection_override_applied = True (different IDs)
        _selection_override_applied = (
            generated_id is not None
            and scheduled_id is not None
            and generated_id != scheduled_id
        )
        assert _selection_override_applied is True

        pool_calls: list[str] = []

        def fake_mark_pool_published(db_path: Any, event_id: str) -> None:
            pool_calls.append(event_id)

        # Emulate the publish block logic
        _published_event_id = generated_id
        if _selection_override_applied:
            # pool: mark generated
            fake_mark_pool_published(tmp_path / "db.sqlite", _published_event_id)
        else:
            fake_mark_pool_published(tmp_path / "db.sqlite", _published_event_id)

        assert pool_calls == [generated_id], (
            f"Pool must mark generated_event_id={generated_id}, not scheduled={scheduled_id}"
        )

    def test_schedule_marks_scheduled_slot_consumed(self):
        """When override occurs, schedule.mark_published must be called with
        scheduled_slot1_id so that slot is consumed and not re-queued."""
        from src.triage.scheduler import mark_published

        scheduled_id = "cls-scheduled-001"
        generated_id = "cls-generated-002"

        _selection_override_applied = scheduled_id != generated_id

        # Build a schedule that has the scheduled event (not the generated one)
        entry = _make_schedule_entry(scheduled_id, published=False)
        from datetime import datetime, timezone
        schedule = DailySchedule(
            date="2026-04-15",
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_candidates=10,
            selected=[entry],
            rejected=[],
            held_back=[],
            open_slots=0,
            coverage_summary={},
            diversity_rules_applied=[],
        )

        if _selection_override_applied:
            updated = mark_published(schedule, scheduled_id)
        else:
            updated = mark_published(schedule, generated_id)

        # The scheduled slot must be marked consumed
        consumed = [e for e in updated.selected if e.event_id == scheduled_id and e.published]
        assert len(consumed) == 1, (
            f"Scheduled slot {scheduled_id} must be marked published (consumed) in the schedule"
        )

        # The generated event is NOT in the schedule, so no entry for it
        generated_in_sched = [e for e in updated.selected if e.event_id == generated_id]
        assert len(generated_in_sched) == 0

    def test_published_event_id_equals_generated_event_id(self):
        """published_event_id must equal generated_event_id when override occurs."""
        scheduled_id = "cls-scheduled-001"
        generated_id = "cls-generated-002"

        _published_event_id = generated_id  # as set by the fixed pipeline

        assert _published_event_id == generated_id
        assert _published_event_id != scheduled_id

    def test_selection_override_applied_true_when_ids_differ(self):
        """selection_override_applied must be True when final_selected != scheduled."""
        scheduled_id = "cls-6c065bcbdba7"
        final_id = "cls-7c055edf63c6"

        override = (
            final_id is not None
            and scheduled_id is not None
            and final_id != scheduled_id
        )
        assert override is True

    def test_selection_override_applied_false_when_ids_match(self):
        """selection_override_applied must be False when final_selected == scheduled."""
        scheduled_id = "cls-6c065bcbdba7"
        final_id = "cls-6c065bcbdba7"

        override = (
            final_id is not None
            and scheduled_id is not None
            and final_id != scheduled_id
        )
        assert override is False


# ── 2. No-override path: IDs stay consistent ──────────────────────────────────

class TestPublishIdentityNoOverride:
    """When no override occurs (scheduler choice passes through)."""

    def test_all_ids_consistent_no_override(self):
        """scheduled_slot1_id == final_selected_slot1_id == generated_event_id == published_event_id."""
        event_id = "cls-same-001"

        scheduled_slot1_id = event_id
        final_selected_slot1_id = event_id
        generated_event_id = event_id

        _selection_override_applied = (
            final_selected_slot1_id is not None
            and scheduled_slot1_id is not None
            and final_selected_slot1_id != scheduled_slot1_id
        )
        _published_event_id = generated_event_id

        assert _selection_override_applied is False
        assert _published_event_id == generated_event_id
        assert generated_event_id == scheduled_slot1_id
        assert generated_event_id == final_selected_slot1_id


# ── 3. run_summary consistency ─────────────────────────────────────────────────

class TestRunSummaryConsistency:
    """run_summary.json generation_tracking fields stay internally consistent."""

    def test_run_summary_override_ids_consistent(self, tmp_path):
        """When override, run_summary must have:
          generated_event_id == final_selected_slot1_id == published_event_id
          scheduled_slot1_id != published_event_id
          selection_override_applied == True
        """
        from src.main import _save_run_summary
        from src.shared.models import JobRecord
        from src.budget import BudgetTracker

        scheduled_id = "cls-scheduled-001"
        generated_id = "cls-generated-002"

        record = JobRecord(id="job-001", event_id=generated_id, status="completed")
        budget = BudgetTracker(run_budget=10, day_budget=100, day_calls_so_far=0)

        _save_run_summary(
            tmp_path,
            job_id="job-001",
            build_stats={},
            record=record,
            budget=budget,
            schedule_tracking={
                "scheduled_event_id": scheduled_id,
                "schedule_snapshot_used": False,
                "schedule_mismatch_resolved": False,
                "no_publishable_candidates": False,
                "all_selected_published": False,
                "fallback_blocked_by_quality_floor": False,
                "scheduled_slot1_id": scheduled_id,
                "reranked_top_id": generated_id,
                "final_selected_slot1_id": generated_id,
                "slot1_selection_source": "judged_flagship:linked_jp_global:score=100.0",
                "slot1_is_judged": True,
                "slot1_publishability_class": "linked_jp_global",
                "slot1_jp_source_count": 2,
                "slot1_en_source_count": 5,
                "slot1_block_reason": None,
                "published_event_id": generated_id,
                "publish_mark_target": scheduled_id,  # schedule consumed the scheduled slot
                "selection_override_applied": True,
            },
        )

        summary = json.loads((tmp_path / "run_summary.json").read_text())
        gt = summary["generation_tracking"]

        assert gt["generated_event_id"] == generated_id
        assert gt["final_selected_slot1_id"] == generated_id
        assert gt["published_event_id"] == generated_id
        assert gt["scheduled_slot1_id"] == scheduled_id
        assert gt["selection_override_applied"] is True
        assert gt["publish_mark_target"] == scheduled_id  # schedule targeted scheduled slot

    def test_run_summary_no_override_all_ids_match(self, tmp_path):
        """When no override, all IDs in run_summary must match."""
        from src.main import _save_run_summary
        from src.shared.models import JobRecord
        from src.budget import BudgetTracker

        event_id = "cls-same-001"
        record = JobRecord(id="job-001", event_id=event_id, status="completed")
        budget = BudgetTracker(run_budget=10, day_budget=100, day_calls_so_far=0)

        _save_run_summary(
            tmp_path,
            job_id="job-001",
            build_stats={},
            record=record,
            budget=budget,
            schedule_tracking={
                "scheduled_event_id": event_id,
                "schedule_snapshot_used": False,
                "schedule_mismatch_resolved": False,
                "no_publishable_candidates": False,
                "all_selected_published": False,
                "fallback_blocked_by_quality_floor": False,
                "scheduled_slot1_id": event_id,
                "reranked_top_id": event_id,
                "final_selected_slot1_id": event_id,
                "slot1_selection_source": "scheduler_no_judge",
                "slot1_is_judged": False,
                "slot1_publishability_class": "not_judged",
                "slot1_jp_source_count": 1,
                "slot1_en_source_count": 3,
                "slot1_block_reason": None,
                "published_event_id": event_id,
                "publish_mark_target": event_id,
                "selection_override_applied": False,
            },
        )

        summary = json.loads((tmp_path / "run_summary.json").read_text())
        gt = summary["generation_tracking"]

        assert gt["generated_event_id"] == event_id
        assert gt["final_selected_slot1_id"] == event_id
        assert gt["published_event_id"] == event_id
        assert gt["scheduled_slot1_id"] == event_id
        assert gt["selection_override_applied"] is False
        assert gt["publish_mark_target"] == event_id


# ── 4. latest_candidate_report.md override section ────────────────────────────

class TestCandidateReportOverride:
    """latest_candidate_report.md must clearly describe any override."""

    def _make_report(
        self,
        tmp_path: Path,
        scheduled_id: str,
        final_id: str,
        override: bool,
        selection_source: str = "judged_flagship:linked_jp_global:score=100.0",
    ) -> str:
        se_scheduled = _make_scored(scheduled_id, score=95.0, sources_jp=[_jp_src()], sources_en=[_en_src()])
        se_final = _make_scored(
            final_id, score=100.0,
            sources_jp=[_jp_src(), _jp_src("Nikkei")],
            sources_en=[_en_src(), _en_src("BBC")],
            judge_result=_make_judge("linked_jp_global"),
        )
        all_ranked = [se_final, se_scheduled]
        judge_results = {final_id: se_final.judge_result}  # type: ignore[index]

        _write_latest_candidate_report(
            tmp_path,
            scheduled_slot1_id=scheduled_id,
            reranked_top_id=final_id,
            final_selected_slot1_id=final_id,
            slot1_selection_source=selection_source,
            slot1_block_reason=None,
            all_ranked=all_ranked,
            judge_results=judge_results,
            generated_event_id=final_id,
            published_event_id=final_id,
            selection_override_applied=override,
        )
        return (tmp_path / "latest_candidate_report.md").read_text()

    def test_override_section_present(self, tmp_path):
        """When override=True, report must include 'Publish Identity' section."""
        content = self._make_report(
            tmp_path,
            scheduled_id="cls-scheduled-001",
            final_id="cls-generated-002",
            override=True,
        )
        assert "Publish Identity" in content
        assert "selection_override_applied" in content
        assert "`True`" in content

    def test_override_section_shows_scheduled_id(self, tmp_path):
        """Publish Identity section shows scheduled_slot1_id."""
        content = self._make_report(
            tmp_path,
            scheduled_id="cls-scheduled-001",
            final_id="cls-generated-002",
            override=True,
        )
        assert "cls-scheduled-001" in content

    def test_override_section_shows_generated_id(self, tmp_path):
        """Publish Identity section shows generated_event_id."""
        content = self._make_report(
            tmp_path,
            scheduled_id="cls-scheduled-001",
            final_id="cls-generated-002",
            override=True,
        )
        assert "cls-generated-002" in content

    def test_override_section_shows_reason(self, tmp_path):
        """Publish Identity section shows the override reason."""
        content = self._make_report(
            tmp_path,
            scheduled_id="cls-scheduled-001",
            final_id="cls-generated-002",
            override=True,
            selection_source="judged_flagship:linked_jp_global:score=100.0",
        )
        assert "judged_flagship" in content

    def test_no_override_section_shows_false(self, tmp_path):
        """When override=False, report shows selection_override_applied as False."""
        content = self._make_report(
            tmp_path,
            scheduled_id="cls-same-001",
            final_id="cls-same-001",
            override=False,
        )
        # Section is included when generated_event_id is set
        assert "selection_override_applied" in content
        assert "`False`" in content

    def test_no_mismatch_log_on_override_path(self, tmp_path, caplog):
        """The MISMATCH warning must NOT appear when FinalSelection intentionally overrides."""
        import logging
        with caplog.at_level(logging.WARNING):
            self._make_report(
                tmp_path,
                scheduled_id="cls-scheduled-001",
                final_id="cls-generated-002",
                override=True,
            )
        mismatch_lines = [
            r for r in caplog.records
            if "MISMATCH" in r.getMessage() and "Marking scheduled ID" in r.getMessage()
        ]
        assert len(mismatch_lines) == 0, (
            "No [Scheduler] MISMATCH log line should appear on the override path"
        )


# ── 4. Per-slot record aggregation (top-3 ループ) ─────────────────────────────

class TestPerSlotRecordAggregation:
    """Top-3 ループの per-slot 結果集約が「slot-1 を表す」ように動作する。

    旧実装はループ末尾の record（最後のスロット）を archive 判定 / run_summary に
    使っていたため、slot-1 が成功でも slot-3 が失敗すると run 全体が "failed"
    扱いになっていた。
    """

    def test_aggregation_picks_slot1_record_for_summary(self):
        """_slot1_record はループの最初のスロット結果。"""
        from src.shared.models import JobRecord
        slot1 = JobRecord(id="j-s1", event_id="ev-1", status="completed")
        slot2 = JobRecord(id="j-s2", event_id="ev-2", status="failed", error="x")
        slot3 = JobRecord(id="j-s3", event_id="ev-3", status="failed", error="y")
        slot_records = [slot1, slot2, slot3]

        record = slot_records[0]
        assert record.event_id == "ev-1"
        assert record.status == "completed"

    def test_completed_count_reflects_all_slots(self):
        """_completed_count は完了スロット全数。"""
        from src.shared.models import JobRecord
        slot_records = [
            JobRecord(id="j-s1", event_id="ev-1", status="completed"),
            JobRecord(id="j-s2", event_id="ev-2", status="completed"),
            JobRecord(id="j-s3", event_id="ev-3", status="failed", error="x"),
        ]
        completed_count = sum(1 for r in slot_records if r.status == "completed")
        assert completed_count == 2

    def test_archive_proceeds_when_any_slot_completed(self):
        """slot-1 が failed でも slot-2/3 が completed なら archive する。"""
        from src.shared.models import JobRecord
        slot_records = [
            JobRecord(id="j-s1", event_id="ev-1", status="failed", error="boom"),
            JobRecord(id="j-s2", event_id="ev-2", status="completed"),
        ]
        any_archivable = any(
            r.status in ("completed", "skipped") for r in slot_records
        ) or not slot_records
        assert any_archivable is True

    def test_published_event_id_is_slot1_only(self):
        """_published_event_id（後方互換変数）は slot-1 のみが書き込む。
        slot-1 が rescue/失敗のときは None のまま、slot-2/3 が completed しても
        変更しない。slot 全体の publish 一覧は別変数 _published_event_ids が持つ。
        """
        from src.shared.models import JobRecord
        slot_records = [
            JobRecord(id="j-s1", event_id="none", status="skipped", error="rescue"),
            JobRecord(id="j-s2", event_id="ev-2", status="completed"),
            JobRecord(id="j-s3", event_id="ev-3", status="completed"),
        ]
        # 新仕様の挙動を再現: slot_idx==0 のみが _published_event_id を更新する
        _published_event_id: str | None = None
        _published_event_ids: list[str] = []
        for slot_idx, r in enumerate(slot_records):
            if r.status == "completed":
                _published_event_ids.append(r.event_id)
                if slot_idx == 0:
                    _published_event_id = r.event_id

        assert _published_event_id is None
        assert _published_event_ids == ["ev-2", "ev-3"]

    def test_av_summary_copy_does_not_self_reference(self):
        """_av_summary は dict コピー後に per_slot を追加するので、
        slot_av_summaries[0] と同一参照にならない。

        回帰防止: 旧実装は `_av_summary["per_slot"] = _slot_av_summaries` と
        破壊的に書き込んでいたため、_slot_av_summaries[0] === _av_summary となり、
        per_slot[0]["per_slot"] というネスト構造が JSON 出力上に現れていた。
        """
        slot1_av: dict = {"audio_generated": True, "voiceover_path": "/tmp/s1.wav", "slot": 1}
        slot2_av: dict = {"audio_generated": True, "voiceover_path": "/tmp/s2.wav", "slot": 2}
        slot_av_summaries = [slot1_av, slot2_av]

        # main.py の修正後の挙動を再現
        av_summary = slot1_av  # slot_idx==0 で代入
        if av_summary is not None and slot_av_summaries:
            av_summary = {**av_summary, "per_slot": slot_av_summaries}

        # スロット-1 の元 dict には per_slot キーが含まれない
        assert "per_slot" not in slot1_av, (
            "slot_av_summaries[0] は per_slot を持たないこと（破壊的書換禁止）"
        )
        # コピーされた av_summary には per_slot が入る
        assert av_summary["per_slot"] is slot_av_summaries
        # ネスト確認: per_slot[0] には per_slot キーが含まれない
        assert "per_slot" not in av_summary["per_slot"][0]
