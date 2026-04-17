"""Tests for rolling comparison window (recent_event_pool).

Coverage:
- story_fingerprint: stable across title variants, category-aware
- freshness: decay tiers, expiry
- DB CRUD: upsert, query, publish, expire
- duplicate suppression: fingerprint matching, upgrade conditions
- combined candidate pool: current + pool merge, sort order
- scheduler fingerprint dedup: same story not selected twice in 5 slots
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.shared.models import NewsEvent, ScoredEvent, SourceRef
from src.storage.db import (
    expire_old_pool_events,
    get_published_story_fingerprints,
    get_recent_pool_events,
    init_db,
    mark_pool_event_published,
    upsert_recent_event_pool,
)
from src.triage.freshness import (
    EXPIRED_HOURS,
    compute_freshness_decay,
    effective_score,
    is_expired,
)
from src.triage.story_fingerprint import compute_story_fingerprint


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def db(tmp_path: Path):
    db_path = tmp_path / "db" / "test.db"
    init_db(db_path)
    return db_path


def _make_event(
    event_id: str = "cls-test000001",
    title: str = "Ukraine ceasefire negotiations",
    category: str = "politics",
    sources_jp: list | None = None,
    sources_en: list | None = None,
) -> NewsEvent:
    return NewsEvent(
        id=event_id,
        title=title,
        summary="Test summary.",
        category=category,
        source="TestSource",
        published_at=datetime(2026, 4, 13, 8, 0, 0, tzinfo=timezone.utc),
        sources_jp=sources_jp or [],
        sources_en=sources_en or [
            SourceRef(name="Reuters", url="https://reuters.com/test", language="en", region="global")
        ],
    )


def _make_scored(
    event: NewsEvent | None = None,
    score: float = 80.0,
    primary_bucket: str = "geopolitics",
    appraisal_type: str | None = "Perspective Inversion",
    story_fingerprint: str = "",
) -> ScoredEvent:
    if event is None:
        event = _make_event()
    return ScoredEvent(
        event=event,
        score=score,
        primary_bucket=primary_bucket,
        appraisal_type=appraisal_type,
        story_fingerprint=story_fingerprint,
        freshness_decay=1.0,
        from_recent_pool=False,
    )


def _pool_entry(se: ScoredEvent, batch_id: str, created_at: str | None = None) -> dict:
    now = created_at or datetime.now(timezone.utc).isoformat()
    return {
        "event_id": se.event.id,
        "batch_id": batch_id,
        "created_at": now,
        "event_snapshot": json.dumps(se.model_dump(mode="json"), ensure_ascii=False),
        "source_regions": json.dumps(
            sorted(se.event.sources_by_locale.keys()) if se.event.sources_by_locale else []
        ),
        "source_languages": json.dumps(["en"]),
        "primary_bucket": se.primary_bucket,
        "appraisal_type": se.appraisal_type,
        "score": se.score,
        "story_fingerprint": se.story_fingerprint or compute_story_fingerprint(se.event),
    }


# ─────────────────────────────────────────────────────────────────────────────
# story_fingerprint tests
# ─────────────────────────────────────────────────────────────────────────────

class TestStoryFingerprint:
    def test_same_title_same_fingerprint(self):
        e1 = _make_event(event_id="cls-a", title="Trump tariff announcement on China")
        e2 = _make_event(event_id="cls-b", title="Trump tariff announcement on China")
        assert compute_story_fingerprint(e1) == compute_story_fingerprint(e2)

    def test_returns_16_char_hex(self):
        e = _make_event()
        fp = compute_story_fingerprint(e)
        assert len(fp) == 16
        assert all(c in "0123456789abcdef" for c in fp)

    def test_different_titles_different_fingerprints(self):
        e1 = _make_event(title="Ukraine ceasefire talks collapse")
        e2 = _make_event(title="Japan central bank raises interest rates")
        assert compute_story_fingerprint(e1) != compute_story_fingerprint(e2)

    def test_order_independent(self):
        """Fingerprint should not change based on word order after sorting."""
        e1 = _make_event(title="ceasefire ukraine negotiations peace")
        e2 = _make_event(title="ukraine peace ceasefire negotiations")
        # Both titles have the same key terms sorted → same fingerprint
        assert compute_story_fingerprint(e1) == compute_story_fingerprint(e2)

    def test_category_affects_fingerprint(self):
        """Same title but different category → different fingerprint."""
        e1 = _make_event(title="Election results announced", category="politics")
        e2 = _make_event(title="Election results announced", category="sports")
        assert compute_story_fingerprint(e1) != compute_story_fingerprint(e2)

    def test_japanese_title(self):
        """Japanese titles should produce valid fingerprints."""
        e = _make_event(title="ウクライナ停戦合意が成立", category="politics")
        fp = compute_story_fingerprint(e)
        assert len(fp) == 16

    def test_short_title(self):
        """Even short titles produce a valid fingerprint."""
        e = _make_event(title="AI", category="technology")
        fp = compute_story_fingerprint(e)
        assert len(fp) == 16

    def test_empty_title_fallback(self):
        """Empty title still produces a valid fingerprint."""
        e = _make_event(title="", category="politics")
        fp = compute_story_fingerprint(e)
        assert len(fp) == 16


# ─────────────────────────────────────────────────────────────────────────────
# freshness decay tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFreshnessDecay:
    NOW = datetime(2026, 4, 13, 12, 0, 0, tzinfo=timezone.utc)

    def _created(self, hours_ago: float) -> datetime:
        return self.NOW - timedelta(hours=hours_ago)

    def test_current_batch_handled_externally(self):
        """Freshness 1.0 is set manually for current-batch events, not by this function."""
        # Pool events that just entered (< 1h) still get 0.9 per spec
        decay = compute_freshness_decay(self._created(0.5), now=self.NOW)
        assert decay == 0.9

    def test_under_24h(self):
        decay = compute_freshness_decay(self._created(12.0), now=self.NOW)
        assert decay == 0.9

    def test_exactly_24h(self):
        decay = compute_freshness_decay(self._created(24.0), now=self.NOW)
        assert decay == 0.8

    def test_30h(self):
        decay = compute_freshness_decay(self._created(30.0), now=self.NOW)
        assert decay == 0.8

    def test_36h(self):
        decay = compute_freshness_decay(self._created(36.0), now=self.NOW)
        assert decay == 0.65

    def test_47h(self):
        decay = compute_freshness_decay(self._created(47.0), now=self.NOW)
        assert decay == 0.65

    def test_expired_at_48h(self):
        decay = compute_freshness_decay(self._created(EXPIRED_HOURS), now=self.NOW)
        assert decay == 0.0

    def test_expired_over_48h(self):
        decay = compute_freshness_decay(self._created(72.0), now=self.NOW)
        assert decay == 0.0

    def test_is_expired_true(self):
        assert is_expired(self._created(50.0), now=self.NOW)

    def test_is_expired_false(self):
        assert not is_expired(self._created(24.0), now=self.NOW)

    def test_naive_datetime_treated_as_utc(self):
        naive = datetime(2026, 4, 13, 0, 0, 0)  # no tzinfo
        aware_now = self.NOW
        decay = compute_freshness_decay(naive, now=aware_now)
        assert isinstance(decay, float)

    def test_effective_score_no_penalty_for_current(self):
        assert effective_score(80.0, 1.0) == 80.0

    def test_effective_score_small_penalty_24h(self):
        result = effective_score(80.0, 0.9)
        assert result == pytest.approx(79.5)  # 80 + (0.9-1.0)*5 = 79.5

    def test_effective_score_max_penalty_48h(self):
        result = effective_score(80.0, 0.65)
        assert result == pytest.approx(78.25)  # 80 + (0.65-1.0)*5 = 78.25


# ─────────────────────────────────────────────────────────────────────────────
# DB CRUD tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRecentEventPoolDB:
    def test_upsert_and_retrieve(self, db):
        se = _make_scored()
        fp = compute_story_fingerprint(se.event)
        entry = _pool_entry(se, "batch_01")
        entry["story_fingerprint"] = fp
        upsert_recent_event_pool(db, [entry])

        rows = get_recent_pool_events(db, window_hours=48)
        assert len(rows) == 1
        assert rows[0]["event_id"] == se.event.id

    def test_upsert_deduplicates_by_event_id(self, db):
        se = _make_scored(score=80.0)
        fp = compute_story_fingerprint(se.event)
        entry = _pool_entry(se, "batch_01")
        entry["story_fingerprint"] = fp

        # Insert twice; second upsert should update not duplicate
        upsert_recent_event_pool(db, [entry])
        entry["score"] = 90.0  # Simulate re-scoring
        upsert_recent_event_pool(db, [entry])

        rows = get_recent_pool_events(db, window_hours=48)
        assert len(rows) == 1

    def test_exclude_batch_id(self, db):
        se = _make_scored()
        entry = _pool_entry(se, "batch_01")
        upsert_recent_event_pool(db, [entry])

        # Exclude the same batch → nothing returned
        rows = get_recent_pool_events(db, window_hours=48, exclude_batch_id="batch_01")
        assert len(rows) == 0

    def test_exclude_batch_id_other_batch_returned(self, db):
        se1 = _make_scored(_make_event("cls-a"), score=80.0)
        se2 = _make_scored(_make_event("cls-b", title="Japan rate hike decision"), score=75.0)
        upsert_recent_event_pool(db, [_pool_entry(se1, "batch_01")])
        upsert_recent_event_pool(db, [_pool_entry(se2, "batch_02")])

        # Exclude batch_01 → only batch_02 entry returned
        rows = get_recent_pool_events(db, window_hours=48, exclude_batch_id="batch_01")
        assert len(rows) == 1
        assert rows[0]["event_id"] == "cls-b"

    def test_window_hours_filters_old_entries(self, db):
        se = _make_scored()
        # Insert with an old created_at (50h ago)
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=50)).isoformat()
        entry = _pool_entry(se, "batch_01", created_at=old_ts)
        upsert_recent_event_pool(db, [entry])

        # window_hours=36 should not return this entry
        rows = get_recent_pool_events(db, window_hours=36)
        assert len(rows) == 0

    def test_mark_pool_event_published(self, db):
        se = _make_scored()
        fp = compute_story_fingerprint(se.event)
        entry = _pool_entry(se, "batch_01")
        entry["story_fingerprint"] = fp
        upsert_recent_event_pool(db, [entry])

        mark_pool_event_published(db, se.event.id)

        # Should no longer appear in unpublished pool
        rows = get_recent_pool_events(db, window_hours=48)
        assert len(rows) == 0

    def test_published_fingerprints_returned(self, db):
        se = _make_scored()
        fp = compute_story_fingerprint(se.event)
        entry = _pool_entry(se, "batch_01")
        entry["story_fingerprint"] = fp
        upsert_recent_event_pool(db, [entry])
        mark_pool_event_published(db, se.event.id)

        fps = get_published_story_fingerprints(db, within_hours=72)
        assert fp in fps
        assert fps[fp]["score"] == se.score

    def test_expire_old_pool_events(self, db):
        se = _make_scored()
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=50)).isoformat()
        entry = _pool_entry(se, "batch_01", created_at=old_ts)
        upsert_recent_event_pool(db, [entry])

        count = expire_old_pool_events(db, max_hours=48)
        assert count == 1

        rows = get_recent_pool_events(db, window_hours=48)
        assert len(rows) == 0

    def test_expire_does_not_touch_fresh_entries(self, db):
        se = _make_scored()
        entry = _pool_entry(se, "batch_01")  # current timestamp
        upsert_recent_event_pool(db, [entry])

        count = expire_old_pool_events(db, max_hours=48)
        assert count == 0

        rows = get_recent_pool_events(db, window_hours=48)
        assert len(rows) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Duplicate suppression and upgrade conditions
# ─────────────────────────────────────────────────────────────────────────────

class TestDuplicateSuppression:
    def test_upgrade_new_region(self, db):
        """Re-publish eligible when a new region is added."""
        from src.main import _check_upgrade_eligible
        se = _make_scored(score=80.0)
        published_info = {
            "score": 80.0,
            "source_regions": ["global"],
            "appraisal_type": "Perspective Inversion",
        }
        pool_row = {
            "source_regions": json.dumps(["global", "middle_east"]),
            "primary_bucket": "geopolitics",
        }
        eligible, reason = _check_upgrade_eligible(se, published_info, pool_row)
        assert eligible
        assert "new_regions" in reason

    def test_upgrade_score_improvement(self, db):
        """Re-publish eligible when score improved by 10+."""
        from src.main import _check_upgrade_eligible
        se = _make_scored(score=95.0)
        published_info = {
            "score": 80.0,
            "source_regions": ["global"],
            "appraisal_type": "Perspective Inversion",
        }
        pool_row = {
            "source_regions": json.dumps(["global"]),
            "primary_bucket": "geopolitics",
        }
        eligible, reason = _check_upgrade_eligible(se, published_info, pool_row)
        assert eligible
        assert "score_improved" in reason

    def test_upgrade_score_below_threshold(self):
        """Score improved by less than 10 should NOT trigger upgrade."""
        from src.main import _check_upgrade_eligible
        se = _make_scored(score=85.0)
        published_info = {
            "score": 80.0,
            "source_regions": ["global"],
            "appraisal_type": "Perspective Inversion",
        }
        pool_row = {
            "source_regions": json.dumps(["global"]),
            "primary_bucket": "geopolitics",
        }
        eligible, _ = _check_upgrade_eligible(se, published_info, pool_row)
        assert not eligible

    def test_upgrade_appraisal_null_to_non_null(self):
        """Appraisal upgraded from None → type triggers upgrade."""
        from src.main import _check_upgrade_eligible
        se = _make_scored(score=80.0, appraisal_type="Media Blind Spot")
        published_info = {
            "score": 80.0,
            "source_regions": ["global"],
            "appraisal_type": None,
        }
        pool_row = {
            "source_regions": json.dumps(["global"]),
            "primary_bucket": "geopolitics",
        }
        eligible, reason = _check_upgrade_eligible(se, published_info, pool_row)
        assert eligible
        assert "appraisal_upgraded" in reason

    def test_upgrade_breaking_shock(self):
        """breaking_shock is always upgrade-eligible."""
        from src.main import _check_upgrade_eligible
        se = _make_scored(score=80.0, primary_bucket="breaking_shock")
        published_info = {
            "score": 80.0,
            "source_regions": ["global"],
            "appraisal_type": "Perspective Inversion",
        }
        pool_row = {
            "source_regions": json.dumps(["global"]),
            "primary_bucket": "breaking_shock",
        }
        eligible, reason = _check_upgrade_eligible(se, published_info, pool_row)
        assert eligible
        assert "breaking_shock" in reason

    def test_no_upgrade_same_story_same_everything(self):
        """No upgrade if same regions, similar score, same appraisal."""
        from src.main import _check_upgrade_eligible
        se = _make_scored(score=82.0, appraisal_type="Perspective Inversion")
        published_info = {
            "score": 80.0,
            "source_regions": ["global"],
            "appraisal_type": "Perspective Inversion",
        }
        pool_row = {
            "source_regions": json.dumps(["global"]),
            "primary_bucket": "geopolitics",
        }
        eligible, _ = _check_upgrade_eligible(se, published_info, pool_row)
        assert not eligible


# ─────────────────────────────────────────────────────────────────────────────
# Scheduler fingerprint dedup
# ─────────────────────────────────────────────────────────────────────────────

class TestSchedulerFingerprintDedup:
    def _make_ranked(self, count: int = 6) -> list[ScoredEvent]:
        """Create a list of ScoredEvents with distinct story_fingerprints.

        Titles deliberately differ from the 'Ukraine ceasefire' duplicate pair
        used in fingerprint tests to avoid accidental fingerprint collisions.
        Uses varied buckets and appraisal types to avoid diversity constraints.
        """
        events = []
        titles = [
            "Japan bank interest rate decision",
            "Saudi Arabia oil production cut",
            "Taiwan semiconductor export control",
            "Germany election results analysis",
            "India Pakistan border tensions escalate",
            "Federal Reserve monetary policy outlook",
        ]
        appraisal_types = [
            "Perspective Inversion",
            "Media Blind Spot",
            "Structural Why",
            "Personal Stakes",
            "Perspective Inversion",
            "Media Blind Spot",
        ]
        buckets = [
            "japan_abroad",
            "geopolitics",
            "tech_geopolitics",
            "geopolitics",
            "politics_economy",
            "coverage_gap",
        ]
        for i in range(count):
            e = _make_event(
                event_id=f"cls-filler{i:06d}",
                title=titles[i % len(titles)],
                category="politics",
            )
            se = _make_scored(e, score=90.0 - i * 5, primary_bucket=buckets[i % len(buckets)])
            se.story_fingerprint = compute_story_fingerprint(e)
            se.appraisal_type = appraisal_types[i % len(appraisal_types)]
            events.append(se)
        return events

    def test_same_fingerprint_not_selected_twice(self):
        """Two events with the same story_fingerprint → only one selected."""
        from src.triage.scheduler import build_daily_schedule

        e1 = _make_event("cls-a", title="Ukraine ceasefire talks collapse", category="politics")
        e2 = _make_event("cls-b", title="Ukraine ceasefire talks collapse", category="politics")
        se1 = _make_scored(e1, score=85.0, primary_bucket="geopolitics")
        se2 = _make_scored(e2, score=80.0, primary_bucket="geopolitics")
        fp = compute_story_fingerprint(e1)
        se1.story_fingerprint = fp
        se2.story_fingerprint = fp  # Same fingerprint, different event_id
        se1.appraisal_type = "Perspective Inversion"
        se2.appraisal_type = "Perspective Inversion"

        # Add variety to fill 5 slots
        ranked = [se1, se2] + self._make_ranked(4)
        # Assign distinct fingerprints to the filler events
        for se in ranked[2:]:
            se.story_fingerprint = compute_story_fingerprint(se.event)

        schedule = build_daily_schedule(ranked, max_slots=5)

        # Collect fingerprints in selected slots
        selected_fps = [e.story_fingerprint for e in schedule.selected if e.story_fingerprint]
        # No fingerprint should appear twice
        assert len(selected_fps) == len(set(selected_fps))

    def test_different_fingerprints_both_eligible(self):
        """Two events with different fingerprints can both be selected."""
        from src.triage.scheduler import build_daily_schedule

        ranked = self._make_ranked(6)
        schedule = build_daily_schedule(ranked, max_slots=5)
        assert len(schedule.selected) == 5
        fps = [e.story_fingerprint for e in schedule.selected if e.story_fingerprint]
        assert len(fps) == len(set(fps))

    def test_from_recent_pool_field_preserved_in_schedule(self):
        """from_recent_pool flag should be preserved in schedule entries."""
        from src.triage.scheduler import build_daily_schedule

        ranked = self._make_ranked(5)
        ranked[0].from_recent_pool = True
        ranked[0].freshness_decay = 0.9
        ranked[0].pool_created_at = "2026-04-12T10:00:00+00:00"

        schedule = build_daily_schedule(ranked, max_slots=5)
        pool_entries = [e for e in schedule.selected if e.from_recent_pool]
        assert len(pool_entries) >= 1
        assert pool_entries[0].freshness_decay == 0.9


# ─────────────────────────────────────────────────────────────────────────────
# Combined candidate pool construction (_build_combined_candidate_pool)
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildCombinedCandidatePool:
    def test_pool_events_carried_over(self, db):
        """Pool events from previous batches appear in combined list."""
        from src.main import _build_combined_candidate_pool, _save_events_to_pool

        # Batch A: create an event and save to pool
        se_old = _make_scored(_make_event("cls-old", title="Japan economy slowdown data"), score=70.0)
        se_old.story_fingerprint = compute_story_fingerprint(se_old.event)
        # Insert with a timestamp 6h ago
        entry = _pool_entry(se_old, "batch_A",
                            created_at=(datetime.now(timezone.utc) - timedelta(hours=6)).isoformat())
        entry["story_fingerprint"] = se_old.story_fingerprint
        upsert_recent_event_pool(db, [entry])

        # Current batch: different story
        se_new = _make_scored(_make_event("cls-new", title="Trump tariff announcement china"), score=85.0)
        se_new.story_fingerprint = compute_story_fingerprint(se_new.event)

        combined, stats = _build_combined_candidate_pool(
            db, [se_new], "batch_B", window_hours=36
        )

        assert stats["carried_over_recent_candidates"] == 1
        assert stats["current_batch_candidates"] == 1
        assert len(combined) == 2

    def test_current_batch_events_not_duplicated_from_pool(self, db):
        """Current batch events already in pool (same fingerprint) are not added twice."""
        from src.main import _build_combined_candidate_pool

        se = _make_scored(_make_event("cls-abc", title="Ukraine ceasefire talks"), score=85.0)
        fp = compute_story_fingerprint(se.event)
        se.story_fingerprint = fp

        # Save same event to pool under an old batch
        entry = _pool_entry(se, "batch_A",
                            created_at=(datetime.now(timezone.utc) - timedelta(hours=8)).isoformat())
        entry["story_fingerprint"] = fp
        upsert_recent_event_pool(db, [entry])

        combined, stats = _build_combined_candidate_pool(
            db, [se], "batch_B", window_hours=36
        )

        # Pool event has same fingerprint as current batch → skipped
        assert stats["carried_over_recent_candidates"] == 0
        assert len(combined) == 1

    def test_expired_pool_events_excluded(self, db):
        """Events older than MAX_WINDOW_HOURS are excluded."""
        from src.main import _build_combined_candidate_pool

        se_old = _make_scored(_make_event("cls-stale"), score=90.0)
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=60)).isoformat()
        entry = _pool_entry(se_old, "batch_A", created_at=old_ts)
        upsert_recent_event_pool(db, [entry])

        se_new = _make_scored(_make_event("cls-fresh", title="Fresh news today"), score=75.0)
        combined, stats = _build_combined_candidate_pool(
            db, [se_new], "batch_B", window_hours=36
        )

        assert stats["expired_candidate_count"] >= 1
        assert len(combined) == 1  # Only current batch event

    def test_duplicate_suppressed_if_published(self, db):
        """Pool events for published stories are suppressed (no upgrade condition)."""
        from src.main import _build_combined_candidate_pool

        se_published = _make_scored(
            _make_event("cls-pub", title="Ukraine ceasefire talks"),
            score=80.0,
            appraisal_type="Perspective Inversion",
        )
        fp = compute_story_fingerprint(se_published.event)
        se_published.story_fingerprint = fp

        # Insert into pool
        entry = _pool_entry(se_published, "batch_A",
                            created_at=(datetime.now(timezone.utc) - timedelta(hours=6)).isoformat())
        entry["story_fingerprint"] = fp
        upsert_recent_event_pool(db, [entry])
        # Mark as published
        mark_pool_event_published(db, se_published.event.id)

        se_current = _make_scored(
            _make_event("cls-cur", title="New breaking news event today"),
            score=75.0,
        )
        se_current.story_fingerprint = compute_story_fingerprint(se_current.event)

        combined, stats = _build_combined_candidate_pool(
            db, [se_current], "batch_B", window_hours=36
        )

        assert stats["duplicate_suppressed_count"] == 0  # Pool entry is published, not in get_recent
        assert len(combined) == 1

    def test_freshness_decay_applied_to_pool_events(self, db):
        """Pool events have freshness_decay < 1.0; current batch stays at 1.0."""
        from src.main import _build_combined_candidate_pool

        se_old = _make_scored(_make_event("cls-old", title="Japan economy data"), score=90.0)
        se_old.story_fingerprint = compute_story_fingerprint(se_old.event)
        entry = _pool_entry(se_old, "batch_A",
                            created_at=(datetime.now(timezone.utc) - timedelta(hours=12)).isoformat())
        entry["story_fingerprint"] = se_old.story_fingerprint
        upsert_recent_event_pool(db, [entry])

        se_new = _make_scored(_make_event("cls-new", title="Trump tariff china news"), score=75.0)
        se_new.story_fingerprint = compute_story_fingerprint(se_new.event)

        combined, _ = _build_combined_candidate_pool(
            db, [se_new], "batch_B", window_hours=36
        )

        pool_events = [s for s in combined if s.from_recent_pool]
        current_events = [s for s in combined if not s.from_recent_pool]

        assert all(s.freshness_decay == 1.0 for s in current_events)
        assert all(s.freshness_decay < 1.0 for s in pool_events)

    def test_sort_order_effective_score(self, db):
        """Combined list is sorted by effective_score; decay breaks ties."""
        from src.main import _build_combined_candidate_pool
        from src.triage.freshness import effective_score

        # Pool event with high base score but decay penalty
        se_old = _make_scored(_make_event("cls-old", title="Japan economy slowdown"), score=90.0)
        se_old.story_fingerprint = compute_story_fingerprint(se_old.event)
        entry = _pool_entry(se_old, "batch_A",
                            created_at=(datetime.now(timezone.utc) - timedelta(hours=36)).isoformat())
        entry["story_fingerprint"] = se_old.story_fingerprint
        upsert_recent_event_pool(db, [entry])

        # Current batch event with lower base score but no decay
        se_new = _make_scored(_make_event("cls-new", title="Trump tariff china news"), score=88.0)
        se_new.story_fingerprint = compute_story_fingerprint(se_new.event)

        combined, _ = _build_combined_candidate_pool(
            db, [se_new], "batch_B", window_hours=48
        )

        # Check sort order by effective_score
        eff_scores = [effective_score(s.score, s.freshness_decay) for s in combined]
        assert eff_scores == sorted(eff_scores, reverse=True)
