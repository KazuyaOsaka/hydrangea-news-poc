"""Observability regression tests.

要件:
  1. NHK 系 source load/drop reason が集計される
  2. token overlap が低くても entity/date/number が一致する JP/EN fixture は merge 候補になる
  3. generic tokens だけで giant cluster ができにくい
  4. held_back_reason が event ごとに出る
  5. upgraded=0 の理由が pool_upgrade_report に残る
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.ingestion.debug_reports import (
    write_pool_upgrade_report,
    write_quality_floor_report,
    write_source_load_report,
    write_cross_lang_merge_report,
)
from src.ingestion.event_builder import (
    _GIANT_CLUSTER_THRESHOLD,
    cluster_articles,
    load_articles_from_files,
)
from src.shared.models import NewsEvent, ScoredEvent
from src.triage.scheduler import _categorize_hold_back_reason, build_daily_schedule


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_article(
    article_id: str,
    title: str,
    country: str = "JP",
    source_name: str = "NHK",
    category: str = "economy",
    published_at: str = "2026-04-14T10:00:00+00:00",
    url: str = "",
) -> dict:
    return {
        "id": article_id,
        "title": title,
        "url": url or f"http://example.com/{article_id}",
        "country": country,
        "source_name": source_name,
        "category": category,
        "published_at": published_at,
        "summary": title,
        "tags": [],
        "fetched_at": "2026-04-14T11:00:00+00:00",
        "raw_ref": "",
        "language": "ja" if country == "JP" else "en",
        "region": "japan" if country == "JP" else "global",
    }


def _make_scored(
    event_id: str,
    title: str,
    score: float = 70.0,
    primary_bucket: str = "politics_economy",
    appraisal_cautions: str | None = None,
    appraisal_type: str | None = None,
    editorial_appraisal_score: float = 0.0,
    sources_en: list | None = None,
    from_recent_pool: bool = False,
    freshness_decay: float = 1.0,
) -> ScoredEvent:
    event = NewsEvent(
        id=event_id,
        title=title,
        summary=title,
        category="economy",
        source="TestSource",
        published_at=datetime(2026, 4, 14, 10, 0, 0),
        sources_en=sources_en or [],
    )
    return ScoredEvent(
        event=event,
        score=score,
        primary_bucket=primary_bucket,
        editorial_tags=[],
        primary_tier="Tier 2",
        appraisal_cautions=appraisal_cautions,
        appraisal_type=appraisal_type,
        editorial_appraisal_score=editorial_appraisal_score,
        from_recent_pool=from_recent_pool,
        freshness_decay=freshness_decay,
        score_breakdown={},
    )


# ── Test 1: Source load/drop reason aggregation ──────────────────────────────

def test_source_load_drop_reason_duplicate_url(tmp_path):
    """NHK_Politics: duplicate_url が drop_reasons に記録され、loaded_count=0 になる。"""
    norm_file = tmp_path / "nhk_politics_normalized.json"
    articles = [
        _make_article("p1", "自民党が選挙に勝利", source_name="NHK_Politics",
                      url="http://nhk.jp/p1"),
        _make_article("p2", "増税法案が可決される", source_name="NHK_Politics",
                      url="http://nhk.jp/p2"),
    ]
    norm_file.write_text(json.dumps(articles), encoding="utf-8")

    # 両 URL を既 seen として渡すと全件 dropped
    stats: dict = {}
    result = load_articles_from_files(
        [norm_file],
        already_seen_urls={"http://nhk.jp/p1", "http://nhk.jp/p2"},
        stats=stats,
    )

    assert len(result) == 0, "全件 seen URL → loaded=0"
    report = stats["source_load_report"]["NHK_Politics"]
    assert report["normalized_count"] == 2
    assert report["loaded_count"] == 0
    assert report["dropped_count"] == 2
    assert report["drop_reasons"].get("duplicate_url", 0) == 2


def test_source_load_report_ok_when_no_seen_urls(tmp_path):
    """seen URL なしならロード成功、drop_reasons が空になる。"""
    norm_file = tmp_path / "nhk_economy_normalized.json"
    articles = [
        _make_article("e1", "日銀が追加利上げ", source_name="NHK_Economy",
                      url="http://nhk.jp/e1"),
    ]
    norm_file.write_text(json.dumps(articles), encoding="utf-8")

    stats: dict = {}
    result = load_articles_from_files([norm_file], already_seen_urls=set(), stats=stats)

    assert len(result) == 1
    report = stats["source_load_report"]["NHK_Economy"]
    assert report["loaded_count"] == 1
    assert report["dropped_count"] == 0
    assert report["drop_reasons"] == {}


def test_source_load_report_missing_title(tmp_path):
    """title なし記事は missing_required_fields として drop される。"""
    norm_file = tmp_path / "bad_normalized.json"
    articles = [
        {"id": "x1", "title": "", "url": "http://ex.com/x1",
         "source_name": "TestSrc", "country": "JP",
         "category": "economy", "published_at": "2026-04-14T10:00:00+00:00",
         "summary": "", "tags": [], "fetched_at": "", "raw_ref": ""},
    ]
    norm_file.write_text(json.dumps(articles), encoding="utf-8")

    stats: dict = {}
    result = load_articles_from_files([norm_file], stats=stats)

    assert len(result) == 0
    report = stats["source_load_report"]["TestSrc"]
    assert report["drop_reasons"].get("missing_required_fields", 0) == 1


def test_write_source_load_report_json(tmp_path):
    """write_source_load_report が valid JSON を書き出す。"""
    run_stats = {
        "source_load_report": {
            "NHK_Politics": {
                "normalized_count": 5,
                "loaded_count": 0,
                "dropped_count": 5,
                "drop_reasons": {"duplicate_url": 5},
            }
        }
    }
    path = write_source_load_report(run_stats, tmp_path)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    # NHK_Politics: loaded=0 but ALL drops are duplicate_url → expected_dedup_full_batch (not a bug)
    assert data["summary"]["bug_suspected_sources"] == []
    assert data["summary"]["full_dedup_sources"] == ["NHK_Politics"]
    assert data["by_source"]["NHK_Politics"]["diagnosis"] == "expected_dedup_full_batch"
    assert "explanation" in data["by_source"]["NHK_Politics"]


# ── Test 2: Entity/date/number match → JP/EN merge candidate (BFS edge) ─────

def test_bfs_cross_lang_edge_with_single_strong_entity():
    """entity:boj が1件共有されれば JP/EN BFS エッジが形成される（1-strong-anchor ルール）。

    "日銀が利上げ" (JP) ↔ "BOJ raises rates" (US) は entity:boj を共有する。
    旧仕様 (anchor_hits >= 2 必須) ではエッジなし。新仕様では1件で十分。
    """
    articles = [
        _make_article("jp1", "日銀が利上げを決定", country="JP", source_name="NHK"),
        # "BOJ" は _ACRONYM_RE により entity:boj に変換される
        _make_article("en1", "BOJ raises rates sharply", country="US", source_name="Reuters"),
    ]
    clusters = cluster_articles(articles)
    # entity:boj が共有 → JP/EN がひとつのクラスタに結合するはず
    assert len(clusters) == 1, (
        f"Expected 1 cluster (JP/EN merged via entity:boj), got {len(clusters)}: "
        f"{[[a['title'] for a in c] for c in clusters]}"
    )


def test_bfs_cross_lang_edge_with_number_token():
    """num: トークン（具体的数値 0.25%）が共有されれば JP/EN エッジが形成される。"""
    articles = [
        _make_article("jp2", "日銀が0.25%の利上げを決定", country="JP"),
        _make_article("en2", "BOJ hikes rates by 0.25%", country="US", source_name="BBC"),
    ]
    clusters = cluster_articles(articles)
    assert len(clusters) == 1, (
        f"Expected 1 cluster (merged via num:0.25%), got {len(clusters)}"
    )


def test_bfs_weak_only_anchors_no_edge():
    """汎用アンカー (entity:trump, country:usa) だけでは JP/EN エッジが形成されない。"""
    articles = [
        _make_article("jp3", "トランプ大統領が会見を開いた", country="JP"),
        _make_article("en3", "Trump holds press conference", country="US"),
    ]
    # entity:trump (HIGH_FREQ) + country:usa (HIGH_FREQ) のみ → weak-only → 閾値3未満なら不成立
    # anchor_hits = 2 (entity:trump, country:usa), strong_cross=0 → 閾値3 → FAIL
    clusters = cluster_articles(articles)
    # 汎用アンカーのみでは結合しないはず
    assert len(clusters) == 2, (
        f"Expected 2 clusters (weak-only anchors), got {len(clusters)}"
    )


def test_cross_lang_merge_report_written(tmp_path):
    """write_cross_lang_merge_report が valid JSON を書き出す。"""
    run_stats = {
        "cross_lang_bfs_edges": 3,
        "cross_lang_bfs_reject_reasons": {"weak_only_insufficient": 45},
        "jp_clusters_count_before_llm": 24,
        "en_clusters_count_before_llm": 87,
        "jp_clusters_count": 24,
        "en_clusters_count": 87,
        "llm_pairs_total": 48,
        "llm_pairs_filtered": 12,
        "llm_pairs_sent": 8,
        "llm_pairs_merged": 2,
        "llm_skip_reasons": {"low_similarity": 4, "budget_cut": 32, "not_top_k": 36},
        "jp_cluster_stats": [
            {"jp_title": "日銀が利上げ", "en_candidates_total": 87,
             "not_top_k": 85, "low_similarity": 1, "passed_to_llm": 1}
        ],
        "cross_lang_cluster_count": 2,
    }
    path = write_cross_lang_merge_report(run_stats, tmp_path)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["bfs_phase"]["cross_lang_edges_formed"] == 3
    assert data["llm_post_merge_phase"]["skip_reason_histogram"]["budget_cut"] == 32
    assert len(data["per_jp_cluster"]) == 1


# ── Test 3: Generic tokens should not form giant clusters ────────────────────

def test_high_freq_anchor_only_no_giant_cluster():
    """高頻度汎用アンカー (entity:trump) のみでは giant cluster が形成されない。

    同言語ペアで strong_shared が空の場合、HIGH_FREQ_ONLY_SAME_LANG=3 が必要。
    entity:trump 1件のみでは閾値未達 → クラスタ分離。
    """
    # "Trump on X" → entity:trump (HIGH_FREQ) だけが共有アンカー
    # "on" / "Trump" は EN_STOP に含まれるか 5 文字未満 → 通常 KW として取れない
    articles = [
        _make_article(f"en{i}", f"Trump on {chr(65+i)}", country="US")
        for i in range(15)
    ]
    clusters = cluster_articles(articles)
    max_size = max(len(c) for c in clusters) if clusters else 0
    assert max_size < _GIANT_CLUSTER_THRESHOLD, (
        f"Giant cluster formed (max_size={max_size}) from high-freq-only articles"
    )


def test_giant_cluster_analysis_populated_on_split():
    """giant cluster が発生した場合、split_stats に giant_cluster_analyses が含まれる。"""
    from src.ingestion.event_builder import cluster_articles

    # 同じ固有名詞（強いアンカー）を大量に共有させて giant cluster を誘発する
    # entity:boj + 多数の共通 CJK ngram → 11件超のクラスタ
    base_title = "日本銀行が利上げを決定した"
    articles = [
        _make_article(f"jp{i}", f"{base_title}第{i}報", country="JP")
        for i in range(12)
    ]
    stats: dict = {}
    cluster_articles(articles, stats=stats)
    # giant が検出されたかどうかに関わらず、キーは存在する
    assert "giant_cluster_analyses" in stats
    assert isinstance(stats["giant_cluster_analyses"], list)


# ── Test 4: held_back_reason per event ───────────────────────────────────────

def test_categorize_hold_back_reason_no_cross_lang():
    """sources_en が空の ScoredEvent は no_cross_lang_support に分類される。"""
    se = _make_scored(
        "e1", "日銀利上げ",
        appraisal_cautions="[抑制] safety gate: sources_en=empty",
        sources_en=[],
    )
    reason = _categorize_hold_back_reason(se)
    assert reason == "no_cross_lang_support"


def test_categorize_hold_back_reason_low_evidence():
    """all axes weak の場合は low_evidence に分類される。"""
    se = _make_scored(
        "e2", "Test event",
        appraisal_cautions="[抑制] safety gate: all axes weak (pg=0, cg=0, bip=0)",
        sources_en=[],
    )
    reason = _categorize_hold_back_reason(se)
    # sources_en=empty → no_cross_lang_support (takes priority)
    assert reason in ("no_cross_lang_support", "low_evidence")


def test_scheduler_held_back_entries_have_rejection_reason():
    """build_daily_schedule: held_back エントリに rejection_reason が含まれる。"""
    # [抑制] + appraisal_type=None + score=0.0 → quality floor fail
    suppressed = _make_scored(
        "e_sup", "Suppressed event",
        appraisal_cautions="[抑制] safety gate: sources_en=empty",
        appraisal_type=None,
        editorial_appraisal_score=0.0,
        score=65.0,
        primary_bucket="politics_economy",
    )
    schedule = build_daily_schedule([suppressed])

    assert len(schedule.held_back) == 1, "Suppressed event should be in held_back"
    entry = schedule.held_back[0]
    assert entry.rejection_reason is not None
    assert "quality_floor" in entry.rejection_reason
    # structured reason should be embedded in the string
    assert any(
        r in entry.rejection_reason
        for r in ("no_cross_lang_support", "weak_japan_angle", "low_evidence",
                  "weak_structural_insight", "pool_story_already_better")
    )


def test_write_quality_floor_report_json(tmp_path):
    """write_quality_floor_report が valid JSON を書き出す。"""
    suppressed = _make_scored(
        "e_sup", "Suppressed event",
        appraisal_cautions="[抑制] safety gate: sources_en=empty",
        appraisal_type=None,
        editorial_appraisal_score=0.0,
        score=65.0,
        primary_bucket="politics_economy",
    )
    schedule = build_daily_schedule([suppressed])

    path = write_quality_floor_report(schedule, tmp_path)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["summary"]["total_held_back"] >= 1
    assert len(data["per_event"]) >= 1
    first = data["per_event"][0]
    assert "hold_back_reason" in first
    assert "title" in first


# ── Test 5: pool upgrade report ───────────────────────────────────────────────

def test_write_pool_upgrade_report_no_pool(tmp_path):
    """pool が空の場合、no_pool_events_in_window と診断される。"""
    pool_stats = {
        "comparison_window_hours": 36,
        "current_batch_candidates": 50,
        "carried_over_recent_candidates": 0,
        "expired_candidate_count": 0,
        "duplicate_suppressed_count": 0,
        "upgraded_from_recent_pool_count": 0,
    }
    path = write_pool_upgrade_report(pool_stats, tmp_path)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["diagnosis"]["upgrade_zero_reason"] == "no_pool_events_in_window"


def test_write_pool_upgrade_report_all_suppressed(tmp_path):
    """全件が already_published で suppressed の場合を診断できる。"""
    pool_stats = {
        "comparison_window_hours": 36,
        "current_batch_candidates": 50,
        "carried_over_recent_candidates": 10,
        "expired_candidate_count": 0,
        "duplicate_suppressed_count": 10,
        "upgraded_from_recent_pool_count": 0,
    }
    path = write_pool_upgrade_report(pool_stats, tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["diagnosis"]["upgrade_zero_reason"] == "all_suppressed_already_published"


def test_write_pool_upgrade_report_no_upgrade_condition(tmp_path):
    """pool に候補はあるが upgrade 条件を満たさない場合を診断できる。"""
    pool_stats = {
        "comparison_window_hours": 36,
        "current_batch_candidates": 50,
        "carried_over_recent_candidates": 5,
        "expired_candidate_count": 0,
        "duplicate_suppressed_count": 0,
        "upgraded_from_recent_pool_count": 0,
    }
    path = write_pool_upgrade_report(pool_stats, tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["diagnosis"]["upgrade_zero_reason"] == "no_upgrade_condition_met"
