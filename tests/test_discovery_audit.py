"""Tests for the discovery audit layer.

Verifies:
  1. All 3 lanes are generated
  2. Each candidate has all required fields
  3. JSON and MD files are written
  4. blind_spot_score is in [0, 10]
  5. Lane filtering logic (A=cross-lang, B=EN-only, C=JP-only)
  6. Diagnosis correctly identifies dominant failure mode
  7. Runs cleanly with an empty candidate list
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.ingestion.discovery_audit import (
    _blind_spot_score,
    _en_source_count,
    _is_cross_lang_cluster,
    _japan_source_count,
    _non_west_source_count,
    write_discovery_audit,
)
from src.shared.models import NewsEvent, ScoredEvent, SourceRef


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_source(
    name: str,
    language: str = "en",
    region: str = "global",
    country: str = "US",
) -> SourceRef:
    return SourceRef(
        name=name,
        url=f"https://example.com/{name.lower().replace(' ', '-')}",
        title=f"{name} article",
        language=language,
        region=region,
        country=country,
    )


def _make_event(
    event_id: str,
    title: str,
    category: str = "economy",
    sources_jp: list[SourceRef] | None = None,
    sources_en: list[SourceRef] | None = None,
    japan_view: str | None = None,
    global_view: str | None = None,
    impact_on_japan: str | None = None,
    gap_reasoning: str | None = None,
) -> NewsEvent:
    return NewsEvent(
        id=event_id,
        title=title,
        summary=title,
        category=category,
        source=(sources_jp[0].name if sources_jp else (sources_en[0].name if sources_en else "Test")),
        published_at=datetime(2026, 4, 14, 10, 0, 0),
        sources_jp=sources_jp or [],
        sources_en=sources_en or [],
        japan_view=japan_view,
        global_view=global_view,
        impact_on_japan=impact_on_japan,
        gap_reasoning=gap_reasoning,
    )


def _make_scored(
    event: NewsEvent,
    score: float = 70.0,
    bucket: str = "politics_economy",
    score_breakdown: dict | None = None,
) -> ScoredEvent:
    return ScoredEvent(
        event=event,
        score=score,
        primary_bucket=bucket,
        editorial_tags=[],
        primary_tier="Tier 2",
        score_breakdown=score_breakdown or {
            "editorial:japan_relevance_score": 5.0,
            "editorial:global_attention_score": 4.0,
            "editorial:perspective_gap_score": 3.0,
            "editorial:coverage_gap_score": 2.0,
            "editorial:background_inference_potential": 2.0,
            "editorial:big_event_score": 3.0,
            "editorial:geopolitics_depth_score": 2.0,
            "editorial:tech_geopolitics_score": 1.0,
            "editorial:multi_region_score": 0.0,
            "editorial:regional_contrast_score": 0.0,
        },
    )


# ── Helpers: lane filtering ───────────────────────────────────────────────────

def _make_cross_lang_event() -> ScoredEvent:
    """Event with both JP and EN sources — Lane A candidate."""
    jp_src = _make_source("NHK", language="ja", region="japan", country="JP")
    en_src = _make_source("Reuters", language="en", region="global", country="US")
    event = _make_event(
        "cls-linked-001", "日銀が利上げ / BOJ raises rates",
        sources_jp=[jp_src],
        sources_en=[en_src],
        japan_view="日銀が追加利上げを決定",
        global_view="BOJ raises rates for second time",
        gap_reasoning="日本では慎重論が強いが、海外は積極評価",
    )
    return _make_scored(
        event, score=85.0,
        score_breakdown={
            "editorial:japan_relevance_score": 8.0,
            "editorial:global_attention_score": 6.0,
            "editorial:perspective_gap_score": 7.0,
            "editorial:coverage_gap_score": 3.0,
            "editorial:background_inference_potential": 6.0,
            "editorial:big_event_score": 5.0,
            "editorial:geopolitics_depth_score": 2.0,
            "editorial:tech_geopolitics_score": 0.0,
            "editorial:multi_region_score": 2.0,
            "editorial:regional_contrast_score": 0.0,
            "cross_lang_bonus": 5.0,
        },
    )


def _make_en_only_event() -> ScoredEvent:
    """EN-only event with high global attention — Lane B candidate."""
    en_src = _make_source("Bloomberg", language="en", region="global", country="US")
    event = _make_event(
        "cls-en-only-001", "US tariff hike impacts Asia supply chains",
        sources_en=[en_src],
        global_view="Major tariff escalation announced",
    )
    return _make_scored(
        event, score=72.0, bucket="politics_economy",
        score_breakdown={
            "editorial:japan_relevance_score": 2.0,
            "editorial:global_attention_score": 7.0,
            "editorial:perspective_gap_score": 0.0,
            "editorial:coverage_gap_score": 6.0,
            "editorial:background_inference_potential": 1.0,
            "editorial:big_event_score": 5.0,
            "editorial:geopolitics_depth_score": 3.0,
            "editorial:tech_geopolitics_score": 0.0,
            "editorial:multi_region_score": 0.0,
            "editorial:regional_contrast_score": 0.0,
        },
    )


def _make_jp_only_event() -> ScoredEvent:
    """JP-only event with strong signals — Lane C candidate."""
    jp_src = _make_source("Nikkei", language="ja", region="japan", country="JP")
    event = _make_event(
        "cls-jp-only-001", "日本政府が経済安保法を改正",
        sources_jp=[jp_src],
        japan_view="経済安保法の改正が閣議決定された",
    )
    return _make_scored(
        event, score=68.0, bucket="politics_economy",
        score_breakdown={
            "editorial:japan_relevance_score": 7.0,
            "editorial:global_attention_score": 1.0,
            "editorial:perspective_gap_score": 0.0,
            "editorial:coverage_gap_score": 0.0,
            "editorial:background_inference_potential": 1.0,
            "editorial:big_event_score": 4.0,
            "editorial:geopolitics_depth_score": 2.0,
            "editorial:tech_geopolitics_score": 3.0,
            "editorial:multi_region_score": 0.0,
            "editorial:regional_contrast_score": 0.0,
        },
    )


_SAMPLE_RUN_STATS = {
    "jp_article_count": 80,
    "en_article_count": 30,
    "cross_lang_bfs_edges": 0,
    "llm_pairs_merged": 1,
    "cross_lang_cluster_count": 1,
    "source_load_report": {
        "NHK_Politics": {"normalized_count": 10, "loaded_count": 10, "dropped_count": 0, "drop_reasons": {}},
        "Reuters": {"normalized_count": 5, "loaded_count": 5, "dropped_count": 0, "drop_reasons": {}},
    },
    "cross_lang_bfs_reject_reasons": {"weak_only_insufficient": 120},
}


# ── Test 1: Output files are written ─────────────────────────────────────────

def test_write_discovery_audit_creates_files(tmp_path: Path) -> None:
    """Both JSON and MD files are written."""
    ranked = [_make_cross_lang_event(), _make_en_only_event(), _make_jp_only_event()]
    write_discovery_audit(ranked, _SAMPLE_RUN_STATS, tmp_path)

    assert (tmp_path / "discovery_audit.json").exists()
    assert (tmp_path / "discovery_audit.md").exists()


# ── Test 2: JSON structure ────────────────────────────────────────────────────

def test_discovery_audit_json_has_required_keys(tmp_path: Path) -> None:
    """Audit JSON has generated_at, summary, lanes, diagnosis."""
    ranked = [_make_cross_lang_event(), _make_en_only_event(), _make_jp_only_event()]
    audit = write_discovery_audit(ranked, _SAMPLE_RUN_STATS, tmp_path)

    assert "generated_at" in audit
    assert "total_candidates" in audit
    assert audit["total_candidates"] == 3

    assert "summary" in audit
    s = audit["summary"]
    assert "linked_jp_global_count" in s
    assert "global_big_japan_missing_count" in s
    assert "jp_missing_global_link_count" in s
    assert "dominant_failure_mode" in s

    assert "lanes" in audit
    assert "A_linked_jp_global_top10" in audit["lanes"]
    assert "B_global_big_japan_missing_top10" in audit["lanes"]
    assert "C_jp_story_missing_global_link_top10" in audit["lanes"]

    assert "diagnosis" in audit


# ── Test 3: Lane A — cross-lang filtering ────────────────────────────────────

def test_lane_a_only_includes_cross_lang(tmp_path: Path) -> None:
    """Lane A only includes events with JP+EN linkage."""
    ranked = [_make_cross_lang_event(), _make_en_only_event(), _make_jp_only_event()]
    audit = write_discovery_audit(ranked, _SAMPLE_RUN_STATS, tmp_path)

    lane_a = audit["lanes"]["A_linked_jp_global_top10"]
    assert len(lane_a) >= 1
    for c in lane_a:
        assert c["cross_lang_cluster"] is True, (
            f"{c['event_id']} in Lane A but cross_lang_cluster=False"
        )


# ── Test 4: Lane B — EN-dominant filtering ───────────────────────────────────

def test_lane_b_includes_en_only_events(tmp_path: Path) -> None:
    """Lane B includes events with EN sources and no JP sources."""
    ranked = [_make_cross_lang_event(), _make_en_only_event(), _make_jp_only_event()]
    audit = write_discovery_audit(ranked, _SAMPLE_RUN_STATS, tmp_path)

    lane_b = audit["lanes"]["B_global_big_japan_missing_top10"]
    ids = {c["event_id"] for c in lane_b}
    assert "cls-en-only-001" in ids


# ── Test 5: Lane C — JP-only filtering ───────────────────────────────────────

def test_lane_c_includes_jp_only_events(tmp_path: Path) -> None:
    """Lane C includes JP-only events with no EN link."""
    ranked = [_make_cross_lang_event(), _make_en_only_event(), _make_jp_only_event()]
    audit = write_discovery_audit(ranked, _SAMPLE_RUN_STATS, tmp_path)

    lane_c = audit["lanes"]["C_jp_story_missing_global_link_top10"]
    ids = {c["event_id"] for c in lane_c}
    assert "cls-jp-only-001" in ids


# ── Test 6: Required fields per candidate ────────────────────────────────────

_REQUIRED_FIELDS = {
    "event_id", "title", "bucket", "score",
    "source_counts_by_region", "japan_source_count", "en_source_count",
    "non_west_source_count", "source_regions",
    "cross_lang_cluster", "merge_confidence",
    "japan_relevance_score", "global_attention_score",
    "perspective_gap_score", "coverage_gap_score", "background_inference_potential",
    "blind_spot_score", "hold_back_reason",
    "why_this_is_interesting", "why_not_publishable_yet",
}


def test_candidate_has_all_required_fields(tmp_path: Path) -> None:
    """Every candidate in every lane has the full required field set."""
    ranked = [_make_cross_lang_event(), _make_en_only_event(), _make_jp_only_event()]
    audit = write_discovery_audit(ranked, _SAMPLE_RUN_STATS, tmp_path)

    for lane_key in ("A_linked_jp_global_top10", "B_global_big_japan_missing_top10",
                     "C_jp_story_missing_global_link_top10"):
        for candidate in audit["lanes"][lane_key]:
            missing = _REQUIRED_FIELDS - candidate.keys()
            assert not missing, f"{lane_key}: {candidate['event_id']} missing fields: {missing}"


def test_lane_c_candidate_has_merge_failure_fields(tmp_path: Path) -> None:
    """Lane C candidates have merge_failure_reason and nearest_en_candidates."""
    ranked = [_make_cross_lang_event(), _make_en_only_event(), _make_jp_only_event()]
    audit = write_discovery_audit(ranked, _SAMPLE_RUN_STATS, tmp_path)

    for c in audit["lanes"]["C_jp_story_missing_global_link_top10"]:
        assert "merge_failure_reason" in c
        assert "nearest_en_candidates" in c
        assert isinstance(c["nearest_en_candidates"], list)


# ── Test 7: blind_spot_score range ───────────────────────────────────────────

def test_blind_spot_score_in_valid_range(tmp_path: Path) -> None:
    """blind_spot_score is always in [0, 10]."""
    ranked = [_make_cross_lang_event(), _make_en_only_event(), _make_jp_only_event()]
    audit = write_discovery_audit(ranked, _SAMPLE_RUN_STATS, tmp_path)

    for lane_key in ("A_linked_jp_global_top10", "B_global_big_japan_missing_top10",
                     "C_jp_story_missing_global_link_top10"):
        for c in audit["lanes"][lane_key]:
            assert 0.0 <= c["blind_spot_score"] <= 10.0, (
                f"blind_spot_score={c['blind_spot_score']} out of range for {c['event_id']}"
            )


# ── Test 8: Diagnosis — cross_lang_merge failure ─────────────────────────────

def test_diagnosis_detects_cross_lang_merge_failure(tmp_path: Path) -> None:
    """When JP+EN articles exist but 0 merges, dominant_failure=cross_lang_merge."""
    stats = {
        **_SAMPLE_RUN_STATS,
        "jp_article_count": 100,
        "en_article_count": 80,
        "cross_lang_bfs_edges": 0,
        "llm_pairs_merged": 0,
        "cross_lang_cluster_count": 0,
    }
    ranked = [_make_jp_only_event()]
    audit = write_discovery_audit(ranked, stats, tmp_path)

    assert audit["diagnosis"]["dominant_failure_mode"] == "cross_lang_merge"


def test_diagnosis_detects_source_intake_failure(tmp_path: Path) -> None:
    """When jp_article_count=0, dominant_failure=source_intake."""
    stats = {**_SAMPLE_RUN_STATS, "jp_article_count": 0}
    ranked = [_make_en_only_event()]
    audit = write_discovery_audit(ranked, stats, tmp_path)

    assert audit["diagnosis"]["dominant_failure_mode"] == "source_intake"


# ── Test 9: Empty candidate list ─────────────────────────────────────────────

def test_empty_ranked_list(tmp_path: Path) -> None:
    """Should not crash with zero candidates."""
    audit = write_discovery_audit([], _SAMPLE_RUN_STATS, tmp_path)

    assert audit["total_candidates"] == 0
    assert audit["lanes"]["A_linked_jp_global_top10"] == []
    assert audit["lanes"]["B_global_big_japan_missing_top10"] == []
    assert audit["lanes"]["C_jp_story_missing_global_link_top10"] == []
    assert (tmp_path / "discovery_audit.json").exists()
    assert (tmp_path / "discovery_audit.md").exists()


# ── Test 10: Source count helpers ────────────────────────────────────────────

def test_source_count_helpers() -> None:
    """Source count helpers return correct values."""
    jp_src = _make_source("NHK", language="ja", region="japan", country="JP")
    en_src = _make_source("Reuters", language="en", region="global", country="US")
    me_src = _make_source("AlJazeera", language="en", region="middle_east", country="QA")

    event = _make_event("e1", "Test", sources_jp=[jp_src], sources_en=[en_src, me_src])
    se = _make_scored(event)

    assert _japan_source_count(se) == 1
    assert _en_source_count(se) == 2
    assert _is_cross_lang_cluster(se) is True

    # middle_east is non-western
    me_event = _make_event("e2", "ME test", sources_jp=[jp_src])
    # manually add sources_by_locale for middle_east
    me_event.sources_by_locale["middle_east"] = [me_src]
    me_se = _make_scored(me_event)
    assert _non_west_source_count(me_se) == 1


# ── Test 11: MD file contains expected lane headers ──────────────────────────

def test_markdown_contains_lane_headers(tmp_path: Path) -> None:
    """Markdown report contains all 3 lane section headers."""
    ranked = [_make_cross_lang_event(), _make_en_only_event(), _make_jp_only_event()]
    write_discovery_audit(ranked, _SAMPLE_RUN_STATS, tmp_path)

    md = (tmp_path / "discovery_audit.md").read_text(encoding="utf-8")
    assert "Lane A" in md
    assert "Lane B" in md
    assert "Lane C" in md
    assert "Bottom-Line Diagnosis" in md
    assert "Pipeline Stats" in md


# ── Test 12: JSON round-trips correctly ──────────────────────────────────────

def test_json_round_trip(tmp_path: Path) -> None:
    """Written JSON can be parsed back without error."""
    ranked = [_make_cross_lang_event(), _make_en_only_event(), _make_jp_only_event()]
    write_discovery_audit(ranked, _SAMPLE_RUN_STATS, tmp_path)

    raw = (tmp_path / "discovery_audit.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    assert isinstance(data["lanes"]["A_linked_jp_global_top10"], list)
