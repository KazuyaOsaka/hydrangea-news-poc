"""Tests for Daily Programming Scheduler (src/triage/scheduler.py)"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.shared.models import NewsEvent, ScoredEvent, SourceRef
from src.triage.scheduler import (
    SLOT_COUNT,
    _detect_entities,
    _passes_quality_floor,
    _publish_priority,
    build_daily_schedule,
    get_next_unpublished,
    mark_published,
    scored_event_to_schedule_entry,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_event(event_id: str, title: str, category: str = "economy", **kwargs) -> NewsEvent:
    return NewsEvent(
        id=event_id,
        title=title,
        summary=f"Summary for {title}",
        category=category,
        source="TestSource",
        published_at=datetime(2026, 4, 8, 10, 0, 0),
        **kwargs,
    )


def _make_scored(
    event_id: str,
    title: str,
    score: float,
    primary_bucket: str,
    editorial_tags: list[str] | None = None,
    category: str = "economy",
    **event_kwargs,
) -> ScoredEvent:
    event = _make_event(event_id, title, category=category, **event_kwargs)
    return ScoredEvent(
        event=event,
        score=score,
        primary_bucket=primary_bucket,
        editorial_tags=editorial_tags or [],
        primary_tier="Tier 2",
    )


# ── entity detection tests ────────────────────────────────────────────────────

def test_detect_entities_iran():
    entities = _detect_entities("Iran ceasefire deal reached")
    assert "iran" in entities


def test_detect_entities_ohtani():
    entities = _detect_entities("Ohtani hits home run, Japan celebrates")
    assert "ohtani" in entities


def test_detect_entities_multiple():
    entities = _detect_entities("Trump sanctions on Russia amid Ukraine conflict")
    assert "russia" in entities or "ukraine" in entities


def test_detect_entities_none():
    entities = _detect_entities("General stock market update")
    assert len(entities) == 0


# ── build_daily_schedule tests ────────────────────────────────────────────────

def test_schedule_empty_candidates():
    schedule = build_daily_schedule([])
    assert schedule.selected == []
    assert "no_candidates" in schedule.diversity_rules_applied


def test_schedule_respects_max_slots():
    candidates = [
        _make_scored(f"e{i}", f"Event {i}", score=100 - i, primary_bucket="politics_economy")
        for i in range(20)
    ]
    schedule = build_daily_schedule(candidates, max_slots=5)
    assert len(schedule.selected) <= 5


def test_schedule_fills_mandatory_japan_focus():
    """japan_abroad か japanese_person_abroad を必ず1本入れる。"""
    candidates = [
        _make_scored("e1", "Iran sanctions shock", 95.0, "geopolitics"),
        _make_scored("e2", "Fed rate decision", 90.0, "politics_economy"),
        _make_scored("e3", "Ohtani wins MVP abroad", 85.0, "japanese_person_abroad"),
        _make_scored("e4", "AI chip war escalates", 80.0, "tech_geopolitics"),
        _make_scored("e5", "NBA playoffs update", 75.0, "sports"),
        _make_scored("e6", "Oil market shock", 70.0, "breaking_shock"),
    ]
    schedule = build_daily_schedule(candidates)
    buckets = [e.primary_bucket for e in schedule.selected]
    assert any(b in ("japanese_person_abroad", "japan_abroad") for b in buckets), \
        f"Japan focus missing from schedule: {buckets}"


def test_schedule_fills_mandatory_geo_politics():
    """politics_economy / geopolitics / breaking_shock を必ず1本入れる。"""
    candidates = [
        _make_scored("e1", "Ohtani hits 50 HRs", 95.0, "japanese_person_abroad"),
        _make_scored("e2", "Japan economy abroad view", 90.0, "japan_abroad"),
        _make_scored("e3", "Iran ceasefire collapse", 85.0, "geopolitics"),
        _make_scored("e4", "AI investment news", 80.0, "tech_geopolitics"),
        _make_scored("e5", "Entertainment awards", 70.0, "entertainment"),
    ]
    schedule = build_daily_schedule(candidates)
    buckets = [e.primary_bucket for e in schedule.selected]
    assert any(b in ("politics_economy", "geopolitics", "breaking_shock") for b in buckets), \
        f"Geo/politics missing from schedule: {buckets}"


def test_schedule_max_same_bucket():
    """多様な候補がある場合、同じ primary_bucket は最大2本まで。"""
    # 多様なバケットの候補を用意: geopolitics 多数 + 他バケットも少数
    candidates = [
        _make_scored("g1", "Geopolitics event 1", 99.0, "geopolitics"),
        _make_scored("g2", "Geopolitics event 2", 98.0, "geopolitics"),
        _make_scored("g3", "Geopolitics event 3", 97.0, "geopolitics"),
        _make_scored("g4", "Geopolitics event 4", 96.0, "geopolitics"),
        _make_scored("j1", "Japan abroad coverage", 85.0, "japan_abroad"),
        _make_scored("t1", "Tech geopolitics news", 80.0, "tech_geopolitics"),
        _make_scored("p1", "Politics economy update", 75.0, "politics_economy"),
        _make_scored("s1", "Sports event", 70.0, "sports"),
    ]
    schedule = build_daily_schedule(candidates)
    bucket_counts: dict[str, int] = {}
    for e in schedule.selected:
        bucket_counts[e.primary_bucket] = bucket_counts.get(e.primary_bucket, 0) + 1
    # 多様な候補がある場合は geopolitics が 2本以下に抑えられているはず
    assert bucket_counts.get("geopolitics", 0) <= 2, \
        f"geopolitics appears {bucket_counts.get('geopolitics', 0)} times (max 2 with diverse candidates)"


def test_schedule_avoids_entity_overload():
    """同じエンティティ（例: Iran）は最大2本まで。"""
    candidates = [
        _make_scored("e1", "Iran nuclear deal", 99.0, "geopolitics"),
        _make_scored("e2", "Iran sanctions target", 98.0, "breaking_shock"),
        _make_scored("e3", "Iran oil embargo", 97.0, "politics_economy"),  # 3rd Iran → should be blocked
        _make_scored("e4", "Ohtani wins abroad", 85.0, "japanese_person_abroad"),
        _make_scored("e5", "Japan economy review", 80.0, "japan_abroad"),
        _make_scored("e6", "AI chip competition", 75.0, "tech_geopolitics"),
    ]
    schedule = build_daily_schedule(candidates)
    iran_count = sum(
        1 for e in schedule.selected if "iran" in e.title.lower()
    )
    assert iran_count <= 2, f"Iran appears {iran_count} times in schedule"


def test_schedule_diversity_with_mixed_buckets():
    """多様なバケットから選ばれ、coverage_summary に複数バケットが入る。"""
    candidates = [
        _make_scored("e1", "US-Japan summit covered abroad", 95.0, "japan_abroad"),
        _make_scored("e2", "Ukraine conflict update", 90.0, "geopolitics"),
        _make_scored("e3", "Ohtani grand slam", 85.0, "japanese_person_abroad"),
        _make_scored("e4", "AI export controls", 80.0, "tech_geopolitics"),
        _make_scored("e5", "Hollywood award season", 75.0, "entertainment"),
        _make_scored("e6", "Fed rate decision", 70.0, "politics_economy"),
    ]
    schedule = build_daily_schedule(candidates)
    assert len(schedule.coverage_summary) >= 3, \
        f"Expected >= 3 different buckets, got {schedule.coverage_summary}"


def test_schedule_rejected_entries_present():
    """非採用候補が rejected リストに入っている。"""
    candidates = [
        _make_scored(f"e{i}", f"Event {i}", score=100 - i, primary_bucket="geopolitics")
        for i in range(15)
    ]
    schedule = build_daily_schedule(candidates)
    assert len(schedule.rejected) > 0


def test_schedule_date_is_today():
    from datetime import date
    schedule = build_daily_schedule([
        _make_scored("e1", "Test event", 90.0, "general"),
    ])
    assert schedule.date == date.today().isoformat()


# ── get_next_unpublished / mark_published tests ───────────────────────────────

def test_get_next_unpublished_returns_first():
    candidates = [
        _make_scored("e1", "Event 1", 95.0, "geopolitics"),
        _make_scored("e2", "Event 2", 90.0, "japan_abroad"),
    ]
    schedule = build_daily_schedule(candidates, max_slots=2)
    next_entry = get_next_unpublished(schedule)
    assert next_entry is not None
    assert not next_entry.published


def test_mark_published_updates_entry():
    candidates = [
        _make_scored("e1", "Event 1", 95.0, "geopolitics"),
        _make_scored("e2", "Event 2", 90.0, "japan_abroad"),
    ]
    schedule = build_daily_schedule(candidates, max_slots=2)
    first_id = schedule.selected[0].event_id

    updated = mark_published(schedule, first_id)
    assert updated.selected[0].published is True
    assert updated.selected[0].published_at is not None
    assert updated.selected[0].slot_status == "published"
    # 他のエントリは変わっていない
    if len(updated.selected) > 1:
        assert updated.selected[1].published is False
        assert updated.selected[1].slot_status == "selected"


def test_get_next_unpublished_returns_none_when_all_published():
    candidates = [_make_scored("e1", "Only Event", 90.0, "geopolitics")]
    schedule = build_daily_schedule(candidates, max_slots=1)
    schedule = mark_published(schedule, "e1")
    assert get_next_unpublished(schedule) is None


# ── scoring integration: primary_bucket assignment ────────────────────────────

def test_primary_bucket_assigned_in_scoring():
    """compute_score_full が primary_bucket を breakdown に含む。"""
    from src.triage.scoring import compute_score_full

    event = _make_event(
        "test-bucket",
        "Ohtani leads Japan in World Baseball Classic, covered abroad",
        category="sports",
        japan_view="大谷が海外で活躍",
        global_view="Ohtani dominates WBC, Japan celebrates",
    )
    _, breakdown, _, tags, _ = compute_score_full(event)
    assert "primary_bucket" in breakdown
    assert isinstance(breakdown["primary_bucket"], str)


def test_japan_abroad_score_for_jp_politics():
    """日本首相・日本経済が EN メディアで取り上げられると japan_abroad_score が高くなる。"""
    from src.triage.scoring import compute_score_full

    event = _make_event(
        "ja-test",
        "Japanese prime minister visits US amid trade talks",
        category="politics",
        global_view="Japan's PM meets Biden to discuss trade deficit.",
    )
    _, breakdown, _, tags, _ = compute_score_full(event)
    ja = breakdown.get("editorial:japan_abroad_score", 0.0)
    assert ja >= 5.0, f"Expected japan_abroad_score >= 5.0, got {ja}"
    assert "japan_abroad" in tags


def test_japanese_person_abroad_score_for_ohtani():
    """大谷が EN メディアで取り上げられると japanese_person_abroad_score が高くなる。"""
    from src.triage.scoring import compute_score_full

    event = _make_event(
        "jpa-test",
        "Shohei Ohtani wins MVP award, becomes global icon",
        category="sports",
        global_view="Ohtani wins AL MVP for third time, praised globally.",
    )
    _, breakdown, _, tags, _ = compute_score_full(event)
    jpa = breakdown.get("editorial:japanese_person_abroad_score", 0.0)
    assert jpa >= 5.0, f"Expected jpa_score >= 5.0, got {jpa}"
    assert "japanese_person_abroad" in tags


# ── New: appraisal_type diversity constraint tests ────────────────────────────

def test_schedule_max_same_appraisal_type():
    """同じ appraisal_type は最大2本まで（多様な候補がある場合）。"""
    from src.triage.scheduler import MAX_SAME_APPRAISAL_TYPE

    def _make_appraised(event_id, title, score, primary_bucket, appraisal_type=None):
        se = _make_scored(event_id, title, score, primary_bucket)
        return se.model_copy(update={"appraisal_type": appraisal_type})

    candidates = [
        _make_appraised("e1", "Iran sanctions news", 98.0, "geopolitics", "Perspective Inversion"),
        _make_appraised("e2", "Japan economy abroad", 95.0, "japan_abroad", "Perspective Inversion"),
        _make_appraised("e3", "AI chip war coverage gap", 92.0, "tech_geopolitics", "Perspective Inversion"),
        _make_appraised("e4", "Ohtani MLB coverage", 88.0, "japanese_person_abroad", "Media Blind Spot"),
        _make_appraised("e5", "Fed rate personal impact", 85.0, "mass_appeal", "Personal Stakes"),
        _make_appraised("e6", "Politics economy update", 80.0, "politics_economy", "Structural Why"),
        _make_appraised("e7", "Tech geopolitics background", 75.0, "tech_geopolitics", "Structural Why"),
    ]
    schedule = build_daily_schedule(candidates)
    appraisal_counts: dict[str, int] = {}
    for entry in schedule.selected:
        if entry.appraisal_type:
            at = entry.appraisal_type
            appraisal_counts[at] = appraisal_counts.get(at, 0) + 1
    for at, cnt in appraisal_counts.items():
        assert cnt <= MAX_SAME_APPRAISAL_TYPE, \
            f"appraisal_type '{at}' appears {cnt} times (max {MAX_SAME_APPRAISAL_TYPE})"


# ── New: personal_stakes_mass mandatory group tests ───────────────────────────

def test_schedule_fills_personal_stakes_from_tags_multi():
    """personal_stakes タグが tags_multi にある候補を personal_stakes_mass 枠に選べる。"""
    def _with_tags_multi(se, tags):
        return se.model_copy(update={"tags_multi": tags})

    candidates = [
        _with_tags_multi(
            _make_scored("e1", "Iran ceasefire news", 95.0, "geopolitics"),
            ["geopolitics"],
        ),
        _with_tags_multi(
            _make_scored("e2", "Japan PM visit abroad", 90.0, "japan_abroad"),
            ["japan_abroad"],
        ),
        _with_tags_multi(
            _make_scored("e3", "Fed rate hike household impact", 85.0, "politics_economy"),
            ["politics_economy", "personal_stakes"],  # personal_stakes tag!
        ),
        _with_tags_multi(
            _make_scored("e4", "AI chip export control", 80.0, "tech_geopolitics"),
            ["tech_geopolitics"],
        ),
        _with_tags_multi(
            _make_scored("e5", "Ohtani World Series", 75.0, "japanese_person_abroad"),
            ["japanese_person_abroad"],
        ),
    ]
    schedule = build_daily_schedule(candidates)
    # personal_stakes_mass 枠が埋まっているか:
    # mass_appeal bucket OR personal_stakes in tags_multi
    all_tags_multi = []
    for entry in schedule.selected:
        all_tags_multi.extend(entry.tags_multi)
    has_personal_or_mass = (
        any(e.primary_bucket == "mass_appeal" for e in schedule.selected)
        or "personal_stakes" in all_tags_multi
    )
    assert has_personal_or_mass, \
        f"personal_stakes_mass mandatory not filled. selected={[(e.primary_bucket, e.tags_multi) for e in schedule.selected]}"


def test_schedule_fills_personal_stakes_from_mass_appeal_bucket():
    """mass_appeal が primary_bucket の候補で personal_stakes_mass 枠が埋まる。"""
    candidates = [
        _make_scored("e1", "Iran ceasefire", 95.0, "geopolitics"),
        _make_scored("e2", "Japan abroad news", 90.0, "japan_abroad"),
        _make_scored("e3", "Mass appeal story", 85.0, "mass_appeal"),   # mass_appeal bucket
        _make_scored("e4", "AI chip war", 80.0, "tech_geopolitics"),
        _make_scored("e5", "Ohtani wins", 75.0, "japanese_person_abroad"),
    ]
    schedule = build_daily_schedule(candidates)
    buckets = [e.primary_bucket for e in schedule.selected]
    assert "mass_appeal" in buckets, f"mass_appeal missing: {buckets}"


# ── New: appraisal fields stored in DailyScheduleEntry ───────────────────────

def test_schedule_entry_stores_appraisal_fields():
    """DailyScheduleEntry に appraisal フィールドが保存される。"""
    se = _make_scored("e1", "Test appraisal event", 90.0, "geopolitics")
    se = se.model_copy(update={
        "appraisal_type": "Perspective Inversion",
        "appraisal_hook": "日本と海外で全く違う切り口",
        "appraisal_reason": "pg=8.0（日英視点差大）",
        "appraisal_cautions": "gap_reasoning なし: 仮説段階",
        "editorial_appraisal_score": 3.5,
        "tags_multi": ["geopolitics", "politics_economy"],
    })
    schedule = build_daily_schedule([se])
    entry = schedule.selected[0]
    assert entry.appraisal_type == "Perspective Inversion"
    assert entry.appraisal_hook == "日本と海外で全く違う切り口"
    assert entry.editorial_appraisal_score == 3.5
    assert "geopolitics" in entry.tags_multi


# ── New: quality floor tests ──────────────────────────────────────────────────

def test_passes_quality_floor_default():
    """デフォルト候補（抑制なし・low_japan_relevance なし）は通過する。"""
    se = _make_scored("e1", "Normal news", 80.0, "geopolitics")
    assert _passes_quality_floor(se) is True


def test_quality_floor_rejects_suppressed():
    """safety gate 抑制候補（[抑制] cautions + appraisal_type=None + score=0）は通過しない。"""
    se = _make_scored("e1", "EN-only low relevance news", 73.0, "japan_abroad")
    se = se.model_copy(update={
        "appraisal_cautions": "[抑制] safety gate: en_only + low_jr=3",
        "appraisal_type": None,
        "editorial_appraisal_score": 0.0,
    })
    assert _passes_quality_floor(se) is False


def test_quality_floor_passes_low_japan_relevance_without_suppression():
    """low_japan_relevance があっても safety gate 抑制がなければ通過する（narrow floor）。"""
    se = _make_scored("e1", "Low relevance EN story", 70.0, "japan_abroad",
                      editorial_tags=["japan_abroad", "low_japan_relevance"])
    se = se.model_copy(update={"appraisal_type": None, "editorial_appraisal_score": 0.0,
                                "appraisal_cautions": None})  # no [抑制]
    assert _passes_quality_floor(se) is True


def test_quality_floor_passes_suppressed_but_has_appraisal():
    """[抑制] cautions があっても appraisal_type が設定されていれば通過する。"""
    se = _make_scored("e1", "Edge case news", 75.0, "japan_abroad")
    se = se.model_copy(update={
        "appraisal_cautions": "[抑制] safety gate: en_only + low_jr=3",
        "appraisal_type": "Media Blind Spot",  # appraisal あり → 通過
        "editorial_appraisal_score": 2.0,
    })
    assert _passes_quality_floor(se) is True


def test_mandatory_quality_floor_excludes_suppressed_candidate():
    """safety gate 抑制候補は mandatory 枠に入らず held_back へ。より強い候補が selected に入る。"""
    # 抑制済み（quality floor 未達）の japan_abroad 候補
    suppressed = _make_scored("suppressed", "Arm chief low relevance", 73.0, "japan_abroad",
                               editorial_tags=["japan_abroad", "low_japan_relevance"])
    suppressed = suppressed.model_copy(update={
        "appraisal_cautions": "[抑制] safety gate: en_only + low_jr=3",
        "appraisal_type": None,
        "editorial_appraisal_score": 0.0,
    })
    # quality floor を通過する japan_abroad 候補（スコアは低いが quality は高い）
    strong = _make_scored("strong", "Japan PM visits UN with global coverage", 60.0, "japan_abroad")
    strong = strong.model_copy(update={
        "appraisal_type": "Media Blind Spot",
        "appraisal_hook": "海外注目、日本ではほぼ無報道",
        "editorial_appraisal_score": 2.5,
    })
    candidates = [
        suppressed,  # rank 1 by score but fails quality floor
        _make_scored("e2", "Iran ceasefire", 90.0, "geopolitics"),
        _make_scored("e3", "Tech chip war", 85.0, "tech_geopolitics"),
        _make_scored("e4", "FRB household", 80.0, "mass_appeal"),
        strong,      # rank 5 by score but passes quality floor
    ]
    schedule = build_daily_schedule(candidates)
    selected_ids = [e.event_id for e in schedule.selected]
    held_back_ids = [e.event_id for e in schedule.held_back]

    # global quality floor により suppressed は selected に入らない
    assert "suppressed" not in selected_ids, \
        f"Suppressed candidate must not be in selected: {selected_ids}"
    # suppressed は held_back に入っている
    assert "suppressed" in held_back_ids, \
        f"Suppressed candidate must be in held_back: {held_back_ids}"
    # strong は selected に入っている
    assert "strong" in selected_ids, \
        f"Quality candidate must be in selected: {selected_ids}"


# ── New: publish order tests ──────────────────────────────────────────────────

def test_publish_priority_appraisal_before_filler():
    """appraisal あり候補は filler（抑制・no appraisal）より高い優先度を持つ。"""
    from src.shared.models import DailyScheduleEntry

    appraised_entry = DailyScheduleEntry(
        rank_in_candidates=2,
        event_id="appraised",
        title="OpenAI media buy",
        score=92.0,
        primary_bucket="politics_economy",
        appraisal_type="Structural Why",
        appraisal_hook="なぜ？背景にある構造",
        editorial_appraisal_score=3.3,
    )
    filler_entry = DailyScheduleEntry(
        rank_in_candidates=1,
        event_id="filler",
        title="Low relevance EN story",
        score=73.0,
        primary_bucket="japan_abroad",
        appraisal_cautions="[抑制] safety gate: en_only + low_jr=3",
        appraisal_type=None,
        editorial_appraisal_score=0.0,
    )
    assert _publish_priority(appraised_entry) > _publish_priority(filler_entry), \
        "Appraised entry should have higher publish priority than suppressed filler"


def test_publish_order_strong_before_filler_in_schedule():
    """global quality floor により suppressed filler は selected に入らず held_back へ。"""
    filler = _make_scored("filler", "Low rel EN news", 73.0, "japan_abroad",
                           editorial_tags=["japan_abroad", "low_japan_relevance"])
    filler = filler.model_copy(update={
        "appraisal_cautions": "[抑制] safety gate: en_only + low_jr=3",
        "appraisal_type": None,
        "editorial_appraisal_score": 0.0,
    })
    strong = _make_scored("strong", "OpenAI media acquisition", 92.0, "politics_economy")
    strong = strong.model_copy(update={
        "appraisal_type": "Structural Why",
        "appraisal_hook": "背景にある構造的理由",
        "editorial_appraisal_score": 3.3,
    })
    candidates = [
        filler,   # fails quality floor → held_back
        strong,   # passes quality floor → selected
        _make_scored("e3", "Iran conflict", 88.0, "geopolitics"),
        _make_scored("e4", "AI chip war", 85.0, "tech_geopolitics"),
        _make_scored("e5", "Household rates", 80.0, "mass_appeal"),
    ]
    schedule = build_daily_schedule(candidates)
    selected_ids = [e.event_id for e in schedule.selected]
    held_back_ids = [e.event_id for e in schedule.held_back]

    # filler は selected に入らない
    assert "filler" not in selected_ids, \
        f"Suppressed filler must not be in selected: {selected_ids}"
    # filler は held_back に入っている
    assert "filler" in held_back_ids, \
        f"Suppressed filler must be in held_back: {held_back_ids}"
    # strong は selected に入っている
    assert "strong" in selected_ids, \
        f"Quality candidate must be in selected: {selected_ids}"


def test_rejected_entry_stores_appraisal_fields():
    """rejected の DailyScheduleEntry にも appraisal フィールドが保存される。"""
    candidates = [
        _make_scored(f"e{i}", f"Event {i}", score=100 - i, primary_bucket="geopolitics").model_copy(
            update={"appraisal_type": "Structural Why", "appraisal_hook": f"Hook {i}"}
        )
        for i in range(15)
    ]
    schedule = build_daily_schedule(candidates)
    # rejected が存在する
    assert len(schedule.rejected) > 0
    # rejected にも appraisal_type が保存されている
    for entry in schedule.rejected:
        assert entry.appraisal_type == "Structural Why"


# ── event_snapshot tests ──────────────────────────────────────────────────────

def test_selected_entries_have_event_snapshot():
    """build_daily_schedule の selected エントリに event_snapshot が保存される。"""
    candidates = [
        _make_scored(f"e{i}", f"Event {i}", score=100 - i, primary_bucket="geopolitics")
        for i in range(10)
    ]
    schedule = build_daily_schedule(candidates)
    assert len(schedule.selected) > 0
    for entry in schedule.selected:
        assert entry.event_snapshot is not None, (
            f"Selected entry {entry.event_id} must have event_snapshot"
        )


def test_event_snapshot_is_json_serializable():
    """event_snapshot は datetime を含まず JSON シリアライズ可能な dict。"""
    import json
    candidates = [
        _make_scored(f"e{i}", f"Event {i}", score=100 - i, primary_bucket="geopolitics")
        for i in range(5)
    ]
    schedule = build_daily_schedule(candidates)
    for entry in schedule.selected:
        # Should not raise
        serialized = json.dumps(entry.event_snapshot)
        assert len(serialized) > 0


def test_event_snapshot_can_restore_scored_event():
    """event_snapshot から ScoredEvent を復元できる。"""
    se = _make_scored("snap-001", "Snapshot test event", 90.0, "japan_abroad",
                      editorial_tags=["japan_abroad"])
    se = se.model_copy(update={
        "appraisal_type": "Structural Why",
        "appraisal_hook": "テストフック",
        "editorial_appraisal_score": 3.5,
    })
    candidates = [se] + [
        _make_scored(f"fill-{i}", f"Filler {i}", score=80 - i, primary_bucket="geopolitics")
        for i in range(9)
    ]
    schedule = build_daily_schedule(candidates)

    snap_entry = next((e for e in schedule.selected if e.event_id == "snap-001"), None)
    assert snap_entry is not None, "snap-001 should be selected"
    assert snap_entry.event_snapshot is not None

    # Restore
    restored = ScoredEvent.model_validate(snap_entry.event_snapshot)
    assert restored.event.id == "snap-001"
    assert restored.appraisal_type == "Structural Why"
    assert restored.appraisal_hook == "テストフック"
    assert restored.primary_bucket == "japan_abroad"


def test_snapshot_restore_works_when_event_absent_from_ranked():
    """scheduled event が current batch の all_ranked にない場合、snapshot から復元できる。"""
    # This simulates what run_from_normalized does when the scheduled event
    # came from a previous batch and is no longer in the new batch's all_ranked.
    se_old = _make_scored("old-batch-evt", "Old batch event", 92.0, "japan_abroad")
    se_old = se_old.model_copy(update={
        "appraisal_type": "Media Blind Spot",
        "appraisal_hook": "古いバッチのイベント",
    })

    # Build schedule with the old event
    candidates_old = [se_old] + [
        _make_scored(f"fill-{i}", f"Filler {i}", score=80 - i, primary_bucket="geopolitics")
        for i in range(9)
    ]
    schedule = build_daily_schedule(candidates_old)
    snap_entry = next((e for e in schedule.selected if e.event_id == "old-batch-evt"), None)
    assert snap_entry is not None

    # New batch has completely different events — old-batch-evt is NOT present
    new_batch_ranked = [
        _make_scored(f"new-{i}", f"New event {i}", score=75 - i, primary_bucket="tech_geopolitics")
        for i in range(10)
    ]
    # Confirm old event is absent from new batch
    assert not any(se.event.id == "old-batch-evt" for se in new_batch_ranked)

    # Simulate the restore logic from main.py
    from src.triage.scheduler import get_next_unpublished
    next_entry = get_next_unpublished(schedule)
    assert next_entry is not None
    assert next_entry.event_id == "old-batch-evt"

    # _find_scored_event equivalent: not found in new batch
    found_in_new = next((se for se in new_batch_ranked if se.event.id == next_entry.event_id), None)
    assert found_in_new is None, "Should not be found in new batch"

    # Snapshot restore
    assert next_entry.event_snapshot is not None
    restored = ScoredEvent.model_validate(next_entry.event_snapshot)
    assert restored.event.id == "old-batch-evt"
    assert restored.appraisal_type == "Media Blind Spot"


# ── scored_event_to_schedule_entry helper tests ───────────────────────────────

def test_scored_event_to_schedule_entry_all_fields():
    """scored_event_to_schedule_entry が必須フィールドをすべて埋める。"""
    se = _make_scored(
        "helper-001", "Test helper event", 88.5, "geopolitics",
        sources_by_locale={
            "japan": [SourceRef(name="NHK", url="https://nhk.or.jp", language="ja", region="japan")],
            "global": [SourceRef(name="Reuters", url="https://reuters.com", language="en", region="global")],
        },
    )
    se = se.model_copy(update={
        "appraisal_type": "Perspective Inversion",
        "appraisal_hook": "日本と海外で全く逆の評価",
        "appraisal_reason": "視点差が大きい",
        "appraisal_cautions": "事実確認中",
        "editorial_appraisal_score": 4.2,
        "tags_multi": ["geopolitics", "personal_stakes"],
        "score_breakdown": {
            "why_this_region_mix": "JP + global contrast",
            "regional_contrast_reason": "東西で逆評価",
        },
    })

    entry = scored_event_to_schedule_entry(
        se,
        rank_in_candidates=3,
        selection_reason="mandatory:geo_politics",
    )

    assert entry.rank_in_candidates == 3
    assert entry.event_id == "helper-001"
    assert entry.title == "Test helper event"
    assert entry.score == round(88.5, 2)
    assert entry.primary_bucket == "geopolitics"
    assert entry.selection_reason == "mandatory:geo_politics"
    assert entry.rejection_reason is None
    assert entry.published is False
    assert entry.published_at is None
    assert entry.appraisal_type == "Perspective Inversion"
    assert entry.appraisal_hook == "日本と海外で全く逆の評価"
    assert entry.appraisal_reason == "視点差が大きい"
    assert entry.appraisal_cautions == "事実確認中"
    assert entry.editorial_appraisal_score == round(4.2, 3)
    assert "ja" in entry.source_languages
    assert "en" in entry.source_languages
    assert "japan" in entry.source_regions
    assert "global" in entry.source_regions
    assert entry.why_this_region_mix == "JP + global contrast"
    assert entry.regional_contrast_reason == "東西で逆評価"
    assert entry.event_snapshot is not None
    assert entry.tags_multi == ["geopolitics", "personal_stakes"]


def test_scored_event_to_schedule_entry_rejection():
    """rejected エントリでも全フィールドが正しく埋まる。"""
    se = _make_scored("helper-rej", "Rejected event", 70.0, "entertainment")
    se = se.model_copy(update={"appraisal_type": "Media Blind Spot"})

    entry = scored_event_to_schedule_entry(
        se,
        rank_in_candidates=7,
        rejection_reason="bucket_limit:entertainment(2/2)",
    )

    assert entry.rank_in_candidates == 7
    assert entry.rejection_reason == "bucket_limit:entertainment(2/2)"
    assert entry.selection_reason == ""
    assert entry.appraisal_type == "Media Blind Spot"
    assert entry.event_snapshot is not None


# ── _maybe_upgrade_unpublished_slots regression tests ─────────────────────────

def _make_scored_with_locale(
    event_id: str,
    title: str,
    score: float,
    primary_bucket: str,
    **se_kwargs,
) -> ScoredEvent:
    """sources_by_locale 付きの ScoredEvent を作るヘルパー。"""
    event = _make_event(
        event_id, title,
        sources_by_locale={
            "japan": [SourceRef(name="NHK", url="https://nhk.or.jp", language="ja", region="japan")],
            "global": [SourceRef(name="BBC", url="https://bbc.com", language="en", region="global")],
        },
    )
    return ScoredEvent(
        event=event,
        score=score,
        primary_bucket=primary_bucket,
        primary_tier="Tier 2",
        **se_kwargs,
    )


def test_replacement_produces_valid_schedule_entry():
    """unpublished slot replacement 後の DailyScheduleEntry に ValidationError が出ない。

    Regression test for: _maybe_upgrade_unpublished_slots が rank_in_candidates を
    含む全必須フィールドを埋めずに DailyScheduleEntry を構築していた問題。
    """
    from src.shared.models import DailySchedule
    from src.main import _maybe_upgrade_unpublished_slots

    # 既存スケジュール: 低スコアの unpublished 枠
    old_se = _make_scored("old-evt", "Old low score event", 60.0, "general")
    existing_schedule = build_daily_schedule([old_se], max_slots=1)
    assert len(existing_schedule.selected) == 1
    assert existing_schedule.selected[0].published is False

    # 新バッチ: スコアが 20% 以上高い候補
    new_se = _make_scored_with_locale(
        "new-evt", "New high score event", 80.0, "geopolitics",
        appraisal_type="Structural Why",
        appraisal_hook="背景構造を解説",
        appraisal_reason="なぜこの候補か",
        appraisal_cautions="仮説段階",
        editorial_appraisal_score=3.5,
        tags_multi=["geopolitics", "personal_stakes"],
        score_breakdown={
            "why_this_region_mix": "JP + global",
            "regional_contrast_reason": "逆評価あり",
        },
    )
    all_ranked = [new_se]

    # Should NOT raise ValidationError
    updated_schedule, replacements = _maybe_upgrade_unpublished_slots(existing_schedule, all_ranked)

    assert "new-evt" in replacements
    replaced = updated_schedule.selected[0]

    # 必須フィールドの確認
    assert replaced.rank_in_candidates == 1  # new_se は all_ranked の1番目
    assert replaced.event_id == "new-evt"
    assert replaced.score == round(80.0, 2)
    assert replaced.primary_bucket == "geopolitics"
    assert replaced.published is False
    assert replaced.published_at is None

    # appraisal フィールドが落ちていないこと
    assert replaced.appraisal_type == "Structural Why"
    assert replaced.appraisal_hook == "背景構造を解説"
    assert replaced.appraisal_reason == "なぜこの候補か"
    assert replaced.appraisal_cautions == "仮説段階"
    assert replaced.editorial_appraisal_score == round(3.5, 3)

    # region フィールドが落ちていないこと
    assert "japan" in replaced.source_regions
    assert "global" in replaced.source_regions
    assert "ja" in replaced.source_languages
    assert "en" in replaced.source_languages
    assert replaced.why_this_region_mix == "JP + global"
    assert replaced.regional_contrast_reason == "逆評価あり"

    # event_snapshot が保存されていること
    assert replaced.event_snapshot is not None
    restored = ScoredEvent.model_validate(replaced.event_snapshot)
    assert restored.event.id == "new-evt"


def test_replacement_preserves_published_slots():
    """published 枠は replacement 対象にならない。"""
    from src.main import _maybe_upgrade_unpublished_slots

    se1 = _make_scored("evt-pub", "Published event", 60.0, "japan_abroad")
    se2 = _make_scored("evt-unpub", "Unpublished event", 55.0, "geopolitics")
    schedule = build_daily_schedule([se1, se2], max_slots=2)
    # evt-pub を published にする
    schedule = mark_published(schedule, "evt-pub")
    assert schedule.selected[0].published or schedule.selected[1].published

    # 高スコア候補で差し替え試みる
    new_se = _make_scored("evt-new", "New high score event", 99.0, "breaking_shock")
    updated, replacements = _maybe_upgrade_unpublished_slots(schedule, [new_se])

    # published 枠は残っている
    published_ids = {e.event_id for e in updated.selected if e.published}
    assert "evt-pub" in published_ids

    # new event が入っている（unpublished 枠に）
    all_ids = {e.event_id for e in updated.selected}
    assert "evt-new" in all_ids


def test_replacement_breaking_shock_always_replaces():
    """breaking_shock バケットは score 差に関わらず unpublished 枠を差し替える。"""
    from src.main import _maybe_upgrade_unpublished_slots

    se_existing = _make_scored("existing", "Existing event", 90.0, "geopolitics")
    schedule = build_daily_schedule([se_existing], max_slots=1)
    assert not schedule.selected[0].published

    # breaking_shock は score が低くても差し替え
    breaking = _make_scored("breaking-evt", "Breaking news event", 70.0, "breaking_shock")
    updated, replacements = _maybe_upgrade_unpublished_slots(schedule, [breaking])

    assert "breaking-evt" in replacements
    assert updated.selected[0].event_id == "breaking-evt"
    assert updated.selected[0].rank_in_candidates == 1  # all_ranked の1番目


def test_replacement_rank_in_candidates_uses_all_ranked_position():
    """replacement 後の rank_in_candidates は all_ranked 内の実際の順位を反映する。"""
    from src.main import _maybe_upgrade_unpublished_slots

    se_existing = _make_scored("existing", "Existing low score", 50.0, "general")
    schedule = build_daily_schedule([se_existing], max_slots=1)

    # all_ranked に複数候補、差し替えに使われるのは rank 3 の候補
    rank1 = _make_scored("r1", "Rank 1 event", 95.0, "japan_abroad")
    rank2 = _make_scored("r2", "Rank 2 event", 90.0, "geopolitics")
    rank3 = _make_scored("r3", "Rank 3 event", 85.0, "tech_geopolitics")  # score >> existing * 1.20

    all_ranked = [rank1, rank2, rank3]

    # rank1, rank2 が既存スケジュールの selected に含まれているとして used_ids から除外
    # ただし今回は existing のみが schedule.selected なので全3つが candidates に入る
    # best = candidates[0] = rank1 → rank_in_candidates = 1
    updated, replacements = _maybe_upgrade_unpublished_slots(schedule, all_ranked)

    assert "r1" in replacements
    assert updated.selected[0].rank_in_candidates == 1  # rank1 は all_ranked の1番目


# ── New: global quality floor / held_back / open_slots / slot_status tests ──────

def _make_suppressed(event_id: str, title: str, score: float, primary_bucket: str) -> ScoredEvent:
    """[抑制] safety gate 付きの quality floor 未達候補を作るヘルパー。"""
    se = _make_scored(event_id, title, score, primary_bucket)
    return se.model_copy(update={
        "appraisal_cautions": "[抑制] safety gate: sources_en=empty, no_en_view",
        "appraisal_type": None,
        "editorial_appraisal_score": 0.0,
    })


def test_global_quality_floor_in_phase2_sends_to_held_back():
    """Phase 2 でも quality floor 未達候補は selected ではなく held_back に入る。"""
    suppressed = _make_suppressed("sup", "Suppressed EN-only news", 95.0, "coverage_gap")
    quality = _make_scored("qual", "Strong geopolitics story", 80.0, "geopolitics")
    quality = quality.model_copy(update={
        "appraisal_type": "Structural Why",
        "appraisal_hook": "背景構造あり",
        "editorial_appraisal_score": 2.5,
    })
    schedule = build_daily_schedule([suppressed, quality])
    selected_ids = {e.event_id for e in schedule.selected}
    held_ids = {e.event_id for e in schedule.held_back}

    assert "sup" not in selected_ids, f"Suppressed must not be in selected: {selected_ids}"
    assert "sup" in held_ids, f"Suppressed must be in held_back: {held_ids}"
    assert "qual" in selected_ids, f"Quality candidate must be in selected: {selected_ids}"


def test_open_slots_when_all_candidates_fail_quality():
    """全候補が quality floor 未達の場合、selected は空で open_slots = max_slots。"""
    candidates = [_make_suppressed(f"sup{i}", f"Suppressed {i}", 80.0 - i, "coverage_gap")
                  for i in range(5)]
    schedule = build_daily_schedule(candidates, max_slots=3)

    assert len(schedule.selected) == 0, \
        f"Selected should be empty when all candidates fail floor: {[e.event_id for e in schedule.selected]}"
    assert schedule.open_slots == 3, f"Expected open_slots=3, got {schedule.open_slots}"
    assert len(schedule.held_back) > 0, "held_back must have the rejected candidates"


def test_open_slots_partial_quality():
    """quality 候補が max_slots より少ない場合、差分が open_slots になる。"""
    good = _make_scored("g1", "Good story", 90.0, "geopolitics")
    good = good.model_copy(update={"appraisal_type": "Structural Why", "editorial_appraisal_score": 2.5})
    bad1 = _make_suppressed("b1", "Bad story 1", 85.0, "coverage_gap")
    bad2 = _make_suppressed("b2", "Bad story 2", 80.0, "coverage_gap")

    schedule = build_daily_schedule([good, bad1, bad2], max_slots=3)

    assert len(schedule.selected) == 1, f"Only 1 quality candidate: {[e.event_id for e in schedule.selected]}"
    assert schedule.open_slots == 2, f"Expected open_slots=2, got {schedule.open_slots}"
    assert "g1" in {e.event_id for e in schedule.selected}
    assert len(schedule.held_back) == 2


def test_slot_status_default_is_selected():
    """新規選択エントリの slot_status はデフォルトで 'selected'。"""
    se = _make_scored("e1", "Test event", 90.0, "geopolitics")
    se = se.model_copy(update={"appraisal_type": "Structural Why", "editorial_appraisal_score": 2.5})
    schedule = build_daily_schedule([se])

    assert len(schedule.selected) > 0
    for entry in schedule.selected:
        assert entry.slot_status == "selected", \
            f"Unpublished entry should have slot_status='selected', got {entry.slot_status!r}"


def test_mark_published_updates_slot_status():
    """mark_published は slot_status を 'published' に更新する。"""
    se = _make_scored("e1", "Event", 90.0, "geopolitics")
    schedule = build_daily_schedule([se])
    first_id = schedule.selected[0].event_id

    updated = mark_published(schedule, first_id)

    assert updated.selected[0].slot_status == "published"
    assert updated.selected[0].published is True


def test_held_back_slot_status():
    """held_back エントリの slot_status は 'held_back'。"""
    suppressed = _make_suppressed("sup", "Suppressed story", 85.0, "coverage_gap")
    schedule = build_daily_schedule([suppressed])

    assert len(schedule.held_back) > 0
    for entry in schedule.held_back:
        assert entry.slot_status == "held_back", \
            f"held_back entry should have slot_status='held_back', got {entry.slot_status!r}"


def test_held_back_has_rejection_reason():
    """held_back エントリには quality_floor rejection_reason が付いている。"""
    suppressed = _make_suppressed("sup", "Suppressed story", 85.0, "coverage_gap")
    schedule = build_daily_schedule([suppressed])

    assert len(schedule.held_back) > 0
    for entry in schedule.held_back:
        assert entry.rejection_reason is not None, "held_back entry must have rejection_reason"
        assert "quality_floor" in entry.rejection_reason, \
            f"rejection_reason should contain 'quality_floor': {entry.rejection_reason!r}"


def test_held_back_not_in_selected_or_rejected():
    """held_back の候補は selected にも rejected にも重複して入らない。"""
    suppressed = _make_suppressed("sup", "Suppressed story", 95.0, "coverage_gap")
    good = _make_scored("good", "Good story", 80.0, "geopolitics")
    good = good.model_copy(update={"appraisal_type": "Structural Why", "editorial_appraisal_score": 2.5})

    schedule = build_daily_schedule([suppressed, good])
    selected_ids = {e.event_id for e in schedule.selected}
    rejected_ids = {e.event_id for e in schedule.rejected}
    held_ids = {e.event_id for e in schedule.held_back}

    # held_back と他リストに重複なし
    assert not (held_ids & selected_ids), f"Overlap between held_back and selected: {held_ids & selected_ids}"
    assert not (held_ids & rejected_ids), f"Overlap between held_back and rejected: {held_ids & rejected_ids}"


def test_replacement_does_not_introduce_weak_candidate():
    """_maybe_upgrade_unpublished_slots は quality floor 未達の候補で差し替えない。"""
    from src.main import _maybe_upgrade_unpublished_slots

    existing = _make_scored("existing", "Existing quality event", 70.0, "geopolitics")
    existing = existing.model_copy(update={
        "appraisal_type": "Structural Why",
        "editorial_appraisal_score": 2.0,
    })
    schedule = build_daily_schedule([existing], max_slots=1)

    # 差し替え候補は score が 20% 以上高いが quality floor 未達
    weak_replacement = _make_suppressed("weak", "High score but weak evidence", 100.0, "coverage_gap")
    # weak_replacement.score >> existing.score * 1.20 なので通常は差し替えられるが、
    # quality floor により差し替えをブロックするべき
    updated, replacements = _maybe_upgrade_unpublished_slots(schedule, [weak_replacement])

    assert "weak" not in replacements, \
        "Quality-floor-failing candidate must not replace an existing quality slot"
    assert updated.selected[0].event_id == "existing", \
        f"Original quality entry should be preserved, got {updated.selected[0].event_id}"


# ── Regression tests: quality floor bypass via main.py fallback ───────────────
#
# These tests verify the Case A / Case B distinction in run_from_normalized:
#   Case A: schedule.selected non-empty, all published, open_slots==0 → truly done
#   Case B: selected==0 or open_slots>0 → quality floor blocked all candidates
#
# All three tests operate directly on the scheduler output without invoking
# the full run_from_normalized pipeline.

def test_selected_zero_open_slots_positive_is_case_b():
    """selected=0, open_slots>0, held_back>0 の場合は Case B: no publishable candidates.

    Regression test: この状態で get_next_unpublished が None を返したとき、
    main.py は triage top へ fallback してはならない。
    ここではスケジューラの出力を直接確認し、Case B の条件を検証する。
    """
    # 全候補が quality floor 未達 → selected=0, open_slots>0, held_back>0 になるはず
    all_suppressed = [
        _make_suppressed(f"s{i}", f"Suppressed story {i}", 90.0 - i, "coverage_gap")
        for i in range(10)
    ]
    schedule = build_daily_schedule(all_suppressed)

    # スケジューラが正しく Case B 状態を作っていることを確認
    assert len(schedule.selected) == 0, \
        f"All suppressed candidates must result in selected=0, got {len(schedule.selected)}"
    assert schedule.open_slots > 0, \
        f"open_slots must be > 0 when no publishable candidates, got {schedule.open_slots}"
    assert len(schedule.held_back) > 0, \
        f"Suppressed candidates must be held_back, got {len(schedule.held_back)}"

    # get_next_unpublished は None を返す（selected が空なので）
    next_entry = get_next_unpublished(schedule)
    assert next_entry is None, \
        "get_next_unpublished must return None when selected=0"

    # Case B の判定ロジック（main.py の _no_pub_candidates 相当）
    _all_slots_published = (
        len(schedule.selected) > 0
        and all(e.published for e in schedule.selected)
        and schedule.open_slots == 0
    )
    _no_pub_candidates = not _all_slots_published

    assert _no_pub_candidates is True, \
        "selected=0 / open_slots>0 must be classified as Case B (no publishable candidates)"
    assert _all_slots_published is False, \
        "selected=0 must NOT be classified as Case A (all selected published)"


def test_all_selected_published_open_slots_zero_is_case_a():
    """selected>0, all published, open_slots==0 の場合は Case A: truly all done.

    Regression test: この状態のみが本物の「全スロット配信済み」であり、
    Case A として扱われるべきである。
    """
    candidates = [
        _make_scored(f"e{i}", f"Quality event {i}", 90.0 - i, "geopolitics")
        for i in range(5)
    ]
    schedule = build_daily_schedule(candidates)
    # 全エントリを published に設定
    from src.shared.models import DailyScheduleEntry
    published_selected = [
        e.model_copy(update={"published": True, "slot_status": "published"})
        for e in schedule.selected
    ]
    schedule = schedule.model_copy(update={"selected": published_selected, "open_slots": 0})

    assert len(schedule.selected) > 0
    assert all(e.published for e in schedule.selected)
    assert schedule.open_slots == 0

    next_entry = get_next_unpublished(schedule)
    assert next_entry is None, "All published → get_next_unpublished must return None"

    # Case A の判定ロジック（main.py 相当）
    _all_slots_published = (
        len(schedule.selected) > 0
        and all(e.published for e in schedule.selected)
        and schedule.open_slots == 0
    )
    _no_pub_candidates = not _all_slots_published

    assert _all_slots_published is True, \
        "All published + open_slots==0 must be classified as Case A"
    assert _no_pub_candidates is False, \
        "Case A must NOT trigger no_publishable_candidates path"


def test_quality_floor_miss_candidate_raises_in_script_writer():
    """quality_floor_miss 候補が script_writer まで到達したら ValueError を送出する。

    Regression test: main.py の fallback bypass 修正の最終防波堤として、
    write_script は [抑制] 候補に対して生成を中断しなければならない。
    """
    from src.generation.script_writer import write_script
    from src.shared.models import NewsEvent
    from datetime import datetime

    suppressed_se = _make_suppressed("qf-miss-001", "EN-only low relevance story", 75.0, "japan_abroad")
    event = NewsEvent(
        id="qf-miss-001",
        title="EN-only low relevance story",
        summary="This should never reach script generation.",
        category="world",
        source="ForeignSource",
        published_at=datetime(2026, 4, 13, 10, 0, 0),
    )

    with pytest.raises(ValueError, match="quality_floor_miss"):
        write_script(event, triage_result=suppressed_se)
