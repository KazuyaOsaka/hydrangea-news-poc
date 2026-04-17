"""Debug artifact generation for pipeline observability.

実行ごとに data/output/debug/ 配下へ 4 つの JSON を書き出す:
  - source_load_report.json   : ソース別 normalized/loaded/dropped/reasons
  - cross_lang_merge_report.json : JP/EN マージの各段階通過件数
  - quality_floor_report.json    : quality floor で held_back された理由集計
  - pool_upgrade_report.json     : recent_event_pool の upgrade 理由集計

各 JSON は人間がそのまま読める形式（ensure_ascii=False, indent=2）で出力する。
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.shared.models import DailySchedule

_DEBUG_SUBDIR = "debug"


def _debug_dir(output_dir: Path) -> Path:
    d = output_dir / _DEBUG_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_source_load_report(run_stats: dict, output_dir: Path) -> Path:
    """source_load_report.json を書き出す。

    NHK_Politics / NHK_Economy が Loaded=0 になっているとき、
    「バグ」か「重複/フィルタ起因」かを診断できるようにする。

    diagnosis フィールド:
      ok                        — 全件ロード成功
      expected_dedup            — 重複 URL による drop（通常運用として想定内）
      expected_dedup_full_batch — 全記事が duplicate_url で drop（直近バッチ処理済み、想定内）
      bug_suspected             — normalized > 0 かつ duplicate_url 以外の理由で loaded = 0（調査が必要）
    """
    debug = _debug_dir(output_dir)
    source_load_report: dict = run_stats.get("source_load_report", {})

    total_normalized = sum(v.get("normalized_count", 0) for v in source_load_report.values())
    total_loaded = sum(v.get("loaded_count", 0) for v in source_load_report.values())
    total_dropped = sum(v.get("dropped_count", 0) for v in source_load_report.values())
    sources_with_drops = sum(1 for v in source_load_report.values() if v.get("dropped_count", 0) > 0)
    # bug_suspected: loaded=0 かつ duplicate_url 以外の理由がある場合のみ（expected_dedup_full_batch は除外）
    bug_suspected = [
        src for src, v in source_load_report.items()
        if v.get("normalized_count", 0) > 0
        and v.get("loaded_count", 0) == 0
        and not (set(v.get("drop_reasons", {}).keys()) <= {"duplicate_url"})
    ]
    # expected_dedup_full_batch: 全記事が duplicate_url で drop（想定内 — RSS 更新待ち）
    full_dedup_sources = [
        src for src, v in source_load_report.items()
        if v.get("normalized_count", 0) > 0
        and v.get("loaded_count", 0) == 0
        and set(v.get("drop_reasons", {}).keys()) <= {"duplicate_url"}
    ]

    by_source: dict[str, dict] = {}
    for src, data in sorted(source_load_report.items()):
        norm = data.get("normalized_count", 0)
        loaded = data.get("loaded_count", 0)
        dropped = data.get("dropped_count", 0)
        reasons = data.get("drop_reasons", {})
        drop_ratio = round(dropped / norm, 3) if norm > 0 else 0.0

        if norm > 0 and loaded == 0:
            # 全件が duplicate_url で drop されている場合は想定内（直近バッチ処理済み RSS）
            if set(reasons.keys()) <= {"duplicate_url"}:
                diagnosis = "expected_dedup_full_batch"
                explanation = (
                    "全記事が直近バッチで処理済み（duplicate_url）のため loaded=0。"
                    "RSS が更新されるまで新規記事なし。バグではなく想定内の動作。"
                )
            else:
                diagnosis = "bug_suspected"
                explanation = (
                    f"duplicate_url 以外の理由（{list(reasons.keys())}）で loaded=0。"
                    "パイプラインの異常の可能性あり。調査が必要。"
                )
        elif dropped > 0:
            # 全部 duplicate_url なら expected_dedup
            if set(reasons.keys()) <= {"duplicate_url"}:
                diagnosis = "expected_dedup"
                explanation = "一部記事が duplicate_url で drop されたが、新規記事あり。通常運用。"
            else:
                diagnosis = "unexpected_drop"
                explanation = (
                    f"duplicate_url 以外の理由（{list(reasons.keys())}）で drop あり。確認推奨。"
                )
        else:
            diagnosis = "ok"
            explanation = "全記事がロード済み。問題なし。"

        by_source[src] = {
            "normalized_count": norm,
            "loaded_count": loaded,
            "dropped_count": dropped,
            "drop_ratio": drop_ratio,
            "drop_reasons": reasons,
            "diagnosis": diagnosis,
            "explanation": explanation,
        }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_normalized": total_normalized,
            "total_loaded": total_loaded,
            "total_dropped": total_dropped,
            "sources_with_drops": sources_with_drops,
            "bug_suspected_sources": bug_suspected,
            "full_dedup_sources": full_dedup_sources,
        },
        "by_source": by_source,
    }

    path = debug / "source_load_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_cross_lang_merge_report(run_stats: dict, output_dir: Path) -> Path:
    """cross_lang_merge_report.json を書き出す。

    各段階で何件落ちたかを記録する:
      bfs_phase       : アンカートークン条件で除外された JP↔EN ペア数
      llm_post_merge  : pre-filter / budget / LLM 判定の各段階
      per_jp_cluster  : JP クラスタごとの EN 候補通過数
    """
    debug = _debug_dir(output_dir)

    bfs_edges = run_stats.get("cross_lang_bfs_edges", 0)
    bfs_rejects = run_stats.get("cross_lang_bfs_reject_reasons", {})
    jp_count_bfs = run_stats.get("jp_clusters_count_before_llm", 0)
    en_count_bfs = run_stats.get("en_clusters_count_before_llm", 0)

    llm_jp = run_stats.get("jp_clusters_count", 0)
    llm_en = run_stats.get("en_clusters_count", 0)
    llm_total = run_stats.get("llm_pairs_total", 0)
    llm_filtered = run_stats.get("llm_pairs_filtered", 0)
    llm_sent = run_stats.get("llm_pairs_sent", 0)
    llm_merged = run_stats.get("llm_pairs_merged", 0)
    skip_reasons = run_stats.get("llm_skip_reasons", {})
    jp_cluster_stats = run_stats.get("jp_cluster_stats", [])

    same_event_count = run_stats.get("same_event_count", 0)
    related_but_distinct_count = run_stats.get("related_but_distinct_count", 0)
    different_event_count = run_stats.get("different_event_count", 0)
    parse_error_count = run_stats.get("parse_error_count", 0)
    budget_cut_count = run_stats.get("budget_cut_count", 0)
    pairs_considered = run_stats.get("pairs_considered", 0)
    pairs_rejected_by_predicate_guard = run_stats.get("pairs_rejected_by_predicate_guard", 0)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "cross_lang_bfs_edges": bfs_edges,
            "llm_pairs_merged": llm_merged,
            "total_cross_lang_clusters": run_stats.get("cross_lang_cluster_count", 0),
        },
        "bfs_phase": {
            "jp_clusters_count": jp_count_bfs,
            "en_clusters_count": en_count_bfs,
            "cross_lang_edges_formed": bfs_edges,
            "reject_reason_histogram": bfs_rejects,
            "notes": (
                "insufficient_anchor_hits: strong anchor present but count < 1 (unlikely). "
                "weak_only_insufficient: no strong anchor AND total anchors < 3."
            ),
        },
        "llm_post_merge_phase": {
            "jp_clusters_count": llm_jp,
            "en_clusters_count": llm_en,
            "cross_lang_pairs_total": llm_total,
            "after_cheap_score_filter": llm_filtered,
            "pairs_considered": pairs_considered,
            "pairs_rejected_by_predicate_guard": pairs_rejected_by_predicate_guard,
            "llm_pairs_submitted": llm_sent,
            "llm_pairs_merged": llm_merged,
            "skip_reason_histogram": skip_reasons,
        },
        "batch_merge_verdicts": {
            "same_event_count": same_event_count,
            "related_but_distinct_count": related_but_distinct_count,
            "different_event_count": different_event_count,
            "parse_error_count": parse_error_count,
            "budget_cut_count": budget_cut_count,
        },
        "batch_merge_examples": {
            "same_event": run_stats.get("same_event_examples", []),
            "related_but_distinct": run_stats.get("related_but_distinct_examples", []),
            "different_event": run_stats.get("different_event_examples", []),
        },
        "per_jp_cluster": jp_cluster_stats,
    }

    path = debug / "cross_lang_merge_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_quality_floor_report(schedule: "DailySchedule | None", output_dir: Path) -> Path:
    """quality_floor_report.json を書き出す。

    no_publishable_candidates の場合でも、held_back された各イベントの理由を
    人間が読める形式で確認できるようにする。
    """
    debug = _debug_dir(output_dir)

    held_back = schedule.held_back if schedule else []
    selected_count = len(schedule.selected) if schedule else 0
    open_slots = schedule.open_slots if schedule else 0

    reason_counts: Counter = Counter()
    per_event: list[dict] = []

    for entry in held_back:
        reason = entry.rejection_reason or "unknown"
        reason_counts[reason] += 1
        per_event.append({
            "event_id": entry.event_id,
            "title": entry.title,
            "score": entry.score,
            "primary_bucket": entry.primary_bucket,
            "hold_back_reason": reason,
            "appraisal_cautions": entry.appraisal_cautions,
            "appraisal_type": entry.appraisal_type,
            "editorial_appraisal_score": entry.editorial_appraisal_score,
            "from_recent_pool": entry.from_recent_pool,
        })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "selected_count": selected_count,
            "open_slots": open_slots,
            "total_held_back": len(held_back),
            "reason_frequency": dict(reason_counts.most_common()),
        },
        "per_event": per_event,
    }

    path = debug / "quality_floor_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_pool_upgrade_report(pool_stats: dict, output_dir: Path) -> Path:
    """pool_upgrade_report.json を書き出す。

    recent_event_pool の upgrade=0 のとき、なぜゼロかを説明できるようにする。
    """
    debug = _debug_dir(output_dir)

    current = pool_stats.get("current_batch_candidates", 0)
    carried = pool_stats.get("carried_over_recent_candidates", 0)
    expired = pool_stats.get("expired_candidate_count", 0)
    suppressed = pool_stats.get("duplicate_suppressed_count", 0)
    upgraded = pool_stats.get("upgraded_from_recent_pool_count", 0)
    window_h = pool_stats.get("comparison_window_hours", 0)

    if carried == 0:
        upgrade_zero_reason = "no_pool_events_in_window"
    elif upgraded == 0 and suppressed == carried:
        upgrade_zero_reason = "all_suppressed_already_published"
    elif upgraded == 0 and expired > 0 and expired >= carried:
        upgrade_zero_reason = "all_expired_beyond_window"
    elif upgraded == 0:
        upgrade_zero_reason = "no_upgrade_condition_met"
    else:
        upgrade_zero_reason = "n/a"

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pool_stats": {
            "comparison_window_hours": window_h,
            "current_batch_candidates": current,
            "carried_over_recent_candidates": carried,
            "expired_candidate_count": expired,
            "duplicate_suppressed_count": suppressed,
            "upgraded_from_recent_pool_count": upgraded,
        },
        "diagnosis": {
            "upgraded_count": upgraded,
            "upgrade_zero_reason": upgrade_zero_reason,
            "notes": (
                "no_pool_events_in_window: pool is empty or all events older than window. "
                "all_suppressed_already_published: story fingerprint matched published content. "
                "no_upgrade_condition_met: pool has events but none met upgrade criteria "
                "(new region / +10 score / null→appraisal / breaking_shock)."
            ),
        },
    }

    path = debug / "pool_upgrade_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
