"""src/analysis/recency_guard.py + 関連 DB 操作のテスト。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.analysis.recency_guard import apply_recency_guard, record_publication
from src.shared.models import NewsEvent, RecencyRecord, ScoredEvent, SourceRef
from src.storage.db import get_recency_records, init_db, save_recency_record


# ---------- helpers ----------

def _make_event(eid: str, title: str, summary: str = "") -> ScoredEvent:
    ev = NewsEvent(
        id=eid,
        title=title,
        summary=summary,
        category="politics",
        source="Reuters",
        published_at=datetime.now(timezone.utc),
        sources_en=[
            SourceRef(name="Reuters", url=f"https://r.com/{eid}", region="global"),
            SourceRef(name="BBC", url=f"https://b.com/{eid}", region="global"),
            SourceRef(name="WSJ", url=f"https://w.com/{eid}", region="global"),
        ],
    )
    return ScoredEvent(
        event=ev,
        score=10.0,
        score_breakdown={
            "global_attention_score": 8.0,
            "indirect_japan_impact_score": 5.0,
            "perspective_gap_score": 6.0,
        },
    )


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "test.db"
    init_db(p)
    return p


# ---------- DB CRUD ----------

def test_save_and_get_recency_record(db_path: Path):
    rec = RecencyRecord(
        event_id="e1",
        channel_id="geo_lens",
        primary_entities=["trump", "china"],
        primary_topics=["trade_war"],
        published_at=datetime.now(timezone.utc).isoformat(),
    )
    save_recency_record(db_path, rec)

    fetched = get_recency_records(db_path, channel_id="geo_lens", within_hours=24)
    assert len(fetched) == 1
    assert fetched[0].event_id == "e1"
    assert fetched[0].primary_entities == ["trump", "china"]
    assert fetched[0].primary_topics == ["trade_war"]


def test_get_recency_records_filters_by_channel(db_path: Path):
    now = datetime.now(timezone.utc).isoformat()
    save_recency_record(
        db_path,
        RecencyRecord(
            event_id="e1", channel_id="geo_lens",
            primary_entities=["trump"], primary_topics=[], published_at=now,
        ),
    )
    save_recency_record(
        db_path,
        RecencyRecord(
            event_id="e2", channel_id="japan_athletes",
            primary_entities=["modi"], primary_topics=[], published_at=now,
        ),
    )
    geo = get_recency_records(db_path, "geo_lens", within_hours=24)
    ja = get_recency_records(db_path, "japan_athletes", within_hours=24)
    assert {r.event_id for r in geo} == {"e1"}
    assert {r.event_id for r in ja} == {"e2"}


def test_get_recency_records_window_excludes_old(db_path: Path):
    old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    save_recency_record(
        db_path,
        RecencyRecord(
            event_id="old", channel_id="geo_lens",
            primary_entities=["trump"], primary_topics=[], published_at=old,
        ),
    )
    fetched = get_recency_records(db_path, "geo_lens", within_hours=24)
    assert fetched == []


# ---------- apply_recency_guard ----------

def test_apply_recency_guard_demotes_overlapping_candidate(db_path: Path):
    # 直近に Trump 投稿あり
    save_recency_record(
        db_path,
        RecencyRecord(
            event_id="prev",
            channel_id="geo_lens",
            primary_entities=["trump"],
            primary_topics=[],
            published_at=datetime.now(timezone.utc).isoformat(),
        ),
    )

    overlapping = _make_event("e1", "Trump signs new executive order")
    different = _make_event("e2", "Modi visits Indonesia")

    result = apply_recency_guard(
        [overlapping, different],
        channel_id="geo_lens",
        db_path=db_path,
        within_hours=24,
        penalty=0.5,
    )
    # スコア順に並ぶ：different（10.0）→ overlapping（5.0）
    assert result[0].event.id == "e2"
    assert result[1].event.id == "e1"
    assert result[1].recency_guard_applied is True
    assert "trump" in result[1].recency_overlap
    assert result[1].score == pytest.approx(5.0)
    # 重複なしの方は降格されない
    assert result[0].recency_guard_applied is False
    assert result[0].score == pytest.approx(10.0)


def test_apply_recency_guard_topic_overlap(db_path: Path):
    save_recency_record(
        db_path,
        RecencyRecord(
            event_id="prev",
            channel_id="geo_lens",
            primary_entities=[],
            primary_topics=["trade_war"],
            published_at=datetime.now(timezone.utc).isoformat(),
        ),
    )
    cand = _make_event("e1", "New trade war escalation in Asia")
    result = apply_recency_guard(
        [cand], channel_id="geo_lens", db_path=db_path, within_hours=24, penalty=0.5
    )
    assert result[0].recency_guard_applied is True
    assert "trade_war" in result[0].recency_overlap


def test_apply_recency_guard_no_records_no_change(db_path: Path):
    cand = _make_event("e1", "Trump tariffs announcement")
    result = apply_recency_guard(
        [cand], channel_id="geo_lens", db_path=db_path, within_hours=24, penalty=0.5
    )
    assert result[0].score == pytest.approx(10.0)
    assert result[0].recency_guard_applied is False


def test_apply_recency_guard_isolated_per_channel(db_path: Path):
    """別チャンネルの履歴は影響しない。"""
    save_recency_record(
        db_path,
        RecencyRecord(
            event_id="prev",
            channel_id="japan_athletes",
            primary_entities=["trump"],
            primary_topics=[],
            published_at=datetime.now(timezone.utc).isoformat(),
        ),
    )
    cand = _make_event("e1", "Trump announces tariffs")
    result = apply_recency_guard(
        [cand], channel_id="geo_lens", db_path=db_path, within_hours=24, penalty=0.5
    )
    assert result[0].recency_guard_applied is False
    assert result[0].score == pytest.approx(10.0)


def test_apply_recency_guard_empty_input(db_path: Path):
    result = apply_recency_guard(
        [], channel_id="geo_lens", db_path=db_path, within_hours=24, penalty=0.5
    )
    assert result == []


def test_apply_recency_guard_uses_env_defaults(db_path: Path, monkeypatch):
    """RECENCY_GUARD_PENALTY と RECENCY_GUARD_HOURS 環境変数が反映されること。"""
    save_recency_record(
        db_path,
        RecencyRecord(
            event_id="prev", channel_id="geo_lens",
            primary_entities=["trump"], primary_topics=[],
            published_at=datetime.now(timezone.utc).isoformat(),
        ),
    )
    monkeypatch.setenv("RECENCY_GUARD_PENALTY", "0.25")
    monkeypatch.setenv("RECENCY_GUARD_HOURS", "12")
    cand = _make_event("e1", "Trump speech today")
    result = apply_recency_guard([cand], channel_id="geo_lens", db_path=db_path)
    assert result[0].score == pytest.approx(10.0 * 0.25)


# ---------- record_publication ----------

def test_record_publication_persists_extracted_signals(db_path: Path):
    cand = _make_event("e1", "Trump tariffs hit China trade war")
    rec = record_publication(cand, channel_id="geo_lens", db_path=db_path)
    assert "trump" in rec.primary_entities
    assert "china" in rec.primary_entities
    assert "trade_war" in rec.primary_topics
    fetched = get_recency_records(db_path, "geo_lens", within_hours=24)
    assert any(r.event_id == "e1" for r in fetched)
