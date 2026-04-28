"""
Hydrangea News PoC — エントリポイント

Usage:
    # サンプルイベントモード (デフォルト)
    python -m src.main --mode sample [--input PATH]

    # 実ニュースモード (batch-based success archive)
    python -m src.main --mode normalized [--normalized-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.budget import BudgetTracker
from src.generation.article_writer import write_article
from src.generation.evidence_writer import write_evidence
from src.generation.script_writer import generate_script_with_analysis, write_script
from src.generation.video_payload_writer import write_video_payload
from src.ingestion.debug_reports import (
    write_cross_lang_merge_report,
    write_pool_upgrade_report,
    write_quality_floor_report,
    write_source_load_report,
)
from src.ingestion.discovery_audit import write_discovery_audit
from src.ingestion.event_builder import build_events_from_normalized
from src.ingestion.loader import load_events
from src.ingestion.source_profiles import load_source_profiles, select_authority_pair
from src.llm.factory import get_cluster_llm_client, get_garbage_filter_client, get_judge_llm_client
from src.llm.judge import evaluate_cluster_buzz
from src.llm.schemas import EditorScore
from src.llm.model_registry import (
    ModelResolution,
    get_judge_model_resolution,
    get_generation_model_resolution,
    get_merge_batch_model_resolution,
)
from src.shared.config import (
    ARCHIVE_DIR,
    AUDIO_RENDER_ENABLED,
    DB_PATH,
    GEMINI_API_KEY,
    GEMINI_JUDGE_FALLBACK_MODELS,
    INPUT_DIR,
    JUDGE_CANDIDATE_LIMIT,
    JUDGE_ENABLED,
    JUDGE_MODEL,
    GENERATION_PROVIDER,
    GENERATION_MODEL,
    MERGE_BATCH_PROVIDER,
    MERGE_BATCH_MODEL,
    LLM_CALL_BUDGET_PER_DAY,
    LLM_CALL_BUDGET_PER_RUN,
    MAX_PUBLISHES_PER_DAY,
    NORMALIZED_DIR,
    OUTPUT_DIR,
    PUBLISH_RESERVE_CALLS,
    RUN_MODE,
    TTS_FRAMERATE,
    TTS_TIMEOUT_SEC,
    TTS_VOICE,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_RENDER_ENABLED,
    VIDEO_WIDTH,
    ELITE_JUDGE_CANDIDATE_LIMIT,
    ELITE_JUDGE_ENABLED,
    GARBAGE_FILTER_ENABLED,
    EDITORIAL_MISSION_FILTER_ENABLED,
    MISSION_LLM_ENABLED,
    MISSION_PRESCORE_TOP_N,
    MISSION_SCORE_THRESHOLD,
)
from src.shared.logger import get_logger
from src.shared.models import DailySchedule, GeminiJudgeResult, JobRecord, ScoredEvent
from src.storage.db import (
    bulk_save_seen_urls,
    expire_old_pool_events,
    get_daily_stats,
    get_oldest_pending_batch,
    get_published_story_fingerprints,
    get_recent_pool_events,
    get_seen_urls_excluding_batch,
    increment_daily_publish_count,
    increment_daily_run_count,
    init_db,
    mark_batch_status,
    mark_pool_event_published,
    save_job,
    upsert_recent_event_pool,
)
from src.triage.appraisal import APPRAISAL_CANDIDATE_LIMIT, apply_editorial_appraisal, final_review
from src.triage.editorial_mission_filter import apply_editorial_mission_filter, build_why_slot1_won_editorially
from src.triage.engine import pick_top, rank_events
from src.triage.freshness import (
    DEFAULT_WINDOW_HOURS,
    MAX_WINDOW_HOURS,
    compute_freshness_decay,
    effective_score,
)
from src.triage.scheduler import _passes_flagship_gate, _passes_quality_floor, build_daily_schedule, get_flagship_class, get_next_unpublished, mark_published, scored_event_to_schedule_entry
from src.triage.story_fingerprint import compute_story_fingerprint

logger = get_logger(__name__)


def _save_run_summary(
    output_dir: Path,
    job_id: str,
    build_stats: dict,
    record,
    budget,
    triage_source_counts: dict | None = None,
    daily_schedule: "DailySchedule | None" = None,
    batch_info: dict | None = None,
    schedule_tracking: "dict | None" = None,
    rolling_window_stats: "dict | None" = None,
    judge_summary: "dict | None" = None,
    editorial_mission_summary: "dict | None" = None,
    av_render_summary: "dict | None" = None,
) -> None:
    """run_summary.json を output_dir に保存する。"""
    normalized_counts = build_stats.get("source_normalized_counts", {})
    adopted_counts = build_stats.get("source_adopted_counts", {})
    cross_lang_counts = build_stats.get("cross_lang_source_counts", {})

    # sources.yaml からメタデータをロードして source_inventory を構築
    # （旧: _JP_SOURCES ハードコードから多地域対応メタデータへ移行）
    _source_meta_map: dict[str, dict] = {}
    try:
        import yaml
        _sources_path = Path("configs/sources.yaml")
        if _sources_path.exists():
            with open(_sources_path, encoding="utf-8") as _f:
                _sources_cfg = yaml.safe_load(_f)
            for _s in _sources_cfg.get("sources", []):
                _source_meta_map[_s["name"]] = {
                    "language": _s.get("language", "en"),
                    "region": _s.get("region", "global"),
                    "country": _s.get("country", ""),
                    "source_type": _s.get("source_type", "news"),
                    "bridge_source": _s.get("bridge_source", False),
                }
    except Exception:
        pass  # メタデータ読み込み失敗時はデフォルト値にフォールバック

    all_source_names = (
        set(normalized_counts.keys())
        | set(adopted_counts.keys())
        | set(cross_lang_counts.keys())
        | set((triage_source_counts or {}).keys())
    )
    source_inventory = {}
    for src in sorted(all_source_names):
        meta = _source_meta_map.get(src, {})
        source_inventory[src] = {
            "language": meta.get("language", "en"),
            "region": meta.get("region", "global"),
            "country": meta.get("country", ""),
            "source_type": meta.get("source_type", "news"),
            "bridge_source": meta.get("bridge_source", False),
            "normalized_count": normalized_counts.get(src, 0),
            "adopted_count": adopted_counts.get(src, 0),
            "cross_lang_candidate_count": cross_lang_counts.get(src, 0),
            "triage_event_count": (triage_source_counts or {}).get(src, 0),
        }

    summary = {
        "job_id": job_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": record.status,
        "event_id": record.event_id,
        # ── Batch 情報 ──────────────────────────────────────────
        "batch": batch_info or {},
        # ── Source inventory ───────────────────────────────────
        "source_inventory": source_inventory,
        "ingestion": {
            "source_normalized_counts": normalized_counts,
            "source_adopted_counts": adopted_counts,
            "jp_article_count": build_stats.get("jp_article_count", 0),
            "en_article_count": build_stats.get("en_article_count", 0),
            "total_article_count": build_stats.get("total_article_count", 0),
            "region_article_counts": build_stats.get("region_article_counts", {}),
            "garbage_filter": {
                "enabled": build_stats.get("garbage_filter_before") is not None,
                "before": build_stats.get("garbage_filter_before", 0),
                "after": build_stats.get("garbage_filter_after", 0),
                "removed": build_stats.get("garbage_filter_removed", 0),
            },
        },
        "clustering": {
            "clusters_before_llm": build_stats.get("clusters_before_llm", 0),
            "clusters_after_llm": build_stats.get("clusters_after_llm", 0),
            "cross_lang_bfs_edges": build_stats.get("cross_lang_bfs_edges", 0),
            "cross_lang_cluster_count": build_stats.get("cross_lang_cluster_count", 0),
            "cross_lang_source_counts": cross_lang_counts,
            "cluster_size_distribution": build_stats.get("cluster_size_distribution", {}),
            "cluster_size_distribution_bfs": build_stats.get("cluster_size_distribution_bfs", {}),
            "max_cluster_size_bfs": build_stats.get("max_cluster_size_bfs", 0),
            "max_cluster_size_after_split": build_stats.get("max_cluster_size_after_split", 0),
            "giant_clusters_detected": build_stats.get("giant_clusters_detected", 0),
            "giant_clusters_split": build_stats.get("giant_clusters_split", 0),
            "giant_cluster_warnings": build_stats.get("giant_cluster_warnings", []),
            "llm_pairs_total": build_stats.get("llm_pairs_total", 0),
            "llm_pairs_filtered": build_stats.get("llm_pairs_filtered", 0),
            "llm_pairs_sent_to_llm": build_stats.get("llm_pairs_sent", 0),
            "llm_pairs_merged": build_stats.get("llm_pairs_merged", 0),
            "events_built": build_stats.get("events_built", 0),
        },
        "merge_summary": {
            "pairs_considered": build_stats.get("pairs_considered", 0),
            "pairs_rejected_by_predicate_guard": build_stats.get("pairs_rejected_by_predicate_guard", 0),
            "pairs_sent_to_batch_llm": build_stats.get("pairs_sent_to_batch_llm", 0),
            "same_event_count": build_stats.get("same_event_count", 0),
            "related_but_distinct_count": build_stats.get("related_but_distinct_count", 0),
            "different_event_count": build_stats.get("different_event_count", 0),
            "parse_error_count": build_stats.get("parse_error_count", 0),
            "budget_cut_count": build_stats.get("budget_cut_count", 0),
            "same_event_examples": build_stats.get("same_event_examples", []),
            "related_but_distinct_examples": build_stats.get("related_but_distinct_examples", []),
            "different_event_examples": build_stats.get("different_event_examples", []),
        },
        "budget": {
            "run_llm_calls": budget.run_calls,
            "run_budget": budget.run_budget,
            "day_llm_calls": budget.day_calls,
            "day_budget": budget.day_budget,
            "reserved_for_script": budget.RESERVED_FOR_SCRIPT,
            "reserved_for_article": budget.RESERVED_FOR_ARTICLE,
            "remaining_before_script": budget._phase_snapshots.get("before_script"),
            "remaining_before_article": budget._phase_snapshots.get("before_article"),
            "retry_counts": budget.retry_counts,
            # ── Publish-mode budget partition observability ─────────────────
            "run_mode": budget.mode,
            "daily_budget_total": budget.day_budget,
            "exploration_budget_used": budget.exploration_budget_used,
            "publish_reserve_budget": budget.publish_reserve_calls,
            "publish_reserve_preserved": budget.publish_reserve_preserved,
            "stopped_exploration_due_to_publish_reserve": budget.stopped_exploration_due_to_publish_reserve,
            "slot1_budget_guaranteed": budget.slot1_budget_guaranteed,
        },
        "model_roles": {
            "merge_batch": {
                "provider": MERGE_BATCH_PROVIDER,
                "requested": MERGE_BATCH_MODEL,
                "resolved": MERGE_BATCH_MODEL,
                "resolution_reason": "role_config_direct",
            },
            "judge": {
                "provider": "gemini",
                "requested": JUDGE_MODEL,
                "resolved": (judge_summary or {}).get("judge_model_resolved", JUDGE_MODEL),
                "resolution_reason": (judge_summary or {}).get(
                    "judge_model_resolution_reason", "not_resolved"
                ),
            },
            "generation": {
                "provider": GENERATION_PROVIDER,
                "requested": GENERATION_MODEL,
                "resolved": GENERATION_MODEL,
                "resolution_reason": "role_config_direct",
            },
        },
        "generation_outcomes": {
            "script": budget.generation_log.get("script", {}),
            "article": budget.generation_log.get("article", {}),
        },
        "daily_schedule": {
            "date": daily_schedule.date if daily_schedule else None,
            "selected_slots": len(daily_schedule.selected) if daily_schedule else 0,
            "open_slots": daily_schedule.open_slots if daily_schedule else 0,
            "held_back_count": len(daily_schedule.held_back) if daily_schedule else 0,
            "published_count": sum(1 for e in daily_schedule.selected if e.published) if daily_schedule else 0,
            "coverage_summary": daily_schedule.coverage_summary if daily_schedule else {},
            "diversity_rules": daily_schedule.diversity_rules_applied if daily_schedule else [],
        } if daily_schedule else None,
        "generation_tracking": {
            "scheduled_event_id": (schedule_tracking or {}).get("scheduled_event_id"),
            "generated_event_id": record.event_id,
            "schedule_snapshot_used": (schedule_tracking or {}).get("schedule_snapshot_used", False),
            "schedule_mismatch_resolved": (schedule_tracking or {}).get("schedule_mismatch_resolved", False),
            "ids_match": (schedule_tracking or {}).get("scheduled_event_id") == record.event_id
                         or record.event_id in ("none",),
            "no_publishable_candidates": (schedule_tracking or {}).get("no_publishable_candidates", False),
            "all_selected_published": (schedule_tracking or {}).get("all_selected_published", False),
            "fallback_blocked_by_quality_floor": (schedule_tracking or {}).get(
                "fallback_blocked_by_quality_floor", False
            ),
            # ── Slot-1 selection audit (Pass 1) ─────────────────────────────
            "scheduled_slot1_id": (schedule_tracking or {}).get("scheduled_slot1_id"),
            "reranked_top_id": (schedule_tracking or {}).get("reranked_top_id"),
            "final_selected_slot1_id": (schedule_tracking or {}).get("final_selected_slot1_id"),
            "slot1_selection_source": (schedule_tracking or {}).get("slot1_selection_source", "unknown"),
            "slot1_is_judged": (schedule_tracking or {}).get("slot1_is_judged", False),
            "slot1_publishability_class": (schedule_tracking or {}).get("slot1_publishability_class"),
            "slot1_jp_source_count": (schedule_tracking or {}).get("slot1_jp_source_count"),
            "slot1_en_source_count": (schedule_tracking or {}).get("slot1_en_source_count"),
            "slot1_block_reason": (schedule_tracking or {}).get("slot1_block_reason"),
            "slot1_source_titles_present_jp": (schedule_tracking or {}).get("slot1_source_titles_present_jp"),
            "slot1_source_titles_present_en": (schedule_tracking or {}).get("slot1_source_titles_present_en"),
            "slot1_coherence_input_quality": (schedule_tracking or {}).get("slot1_coherence_input_quality"),
            "slot1_overlap_signals": (schedule_tracking or {}).get("slot1_overlap_signals"),
            "slot1_semantic_coherence_score": (schedule_tracking or {}).get("slot1_semantic_coherence_score"),
            "slot1_coherence_gate_passed": (schedule_tracking or {}).get("slot1_coherence_gate_passed"),
            # ── Publish identity (Pass 1.5) ──────────────────────────────────
            "published_event_id": (schedule_tracking or {}).get("published_event_id"),
            "publish_mark_target": (schedule_tracking or {}).get("publish_mark_target"),
            "selection_override_applied": (schedule_tracking or {}).get("selection_override_applied", False),
        },
        "rolling_window": rolling_window_stats or {
            "comparison_window_hours": DEFAULT_WINDOW_HOURS,
            "max_window_hours": MAX_WINDOW_HOURS,
            "current_batch_candidates": 0,
            "carried_over_recent_candidates": 0,
            "expired_candidate_count": 0,
            "duplicate_suppressed_count": 0,
            "upgraded_from_recent_pool_count": 0,
        },
        "judge_summary": judge_summary or {"judge_enabled": False, "judged_count": 0},
        "editorial_mission_filter": editorial_mission_summary or {"editorial_mission_filter_applied": False},
        "av_render": av_render_summary or {
            "audio_render_enabled": AUDIO_RENDER_ENABLED,
            "video_render_enabled": VIDEO_RENDER_ENABLED,
            "audio_generated": False,
            "video_generated": False,
        },
    }
    summary_path = output_dir / "run_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Run summary saved: {summary_path}")


def _schedule_path(output_dir: Path) -> Path:
    return output_dir / "daily_schedule.json"


def _load_daily_schedule(output_dir: Path) -> DailySchedule | None:
    from datetime import date
    path = _schedule_path(output_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        schedule = DailySchedule.model_validate(data)
        if schedule.date != date.today().isoformat():
            logger.info("[Scheduler] Existing schedule is for a different date — will rebuild.")
            return None
        return schedule
    except Exception as e:
        logger.warning(f"[Scheduler] Failed to load schedule: {e}")
        return None


def _save_daily_schedule(schedule: DailySchedule, output_dir: Path) -> None:
    path = _schedule_path(output_dir)
    path.write_text(
        json.dumps(schedule.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"[Scheduler] Schedule saved: {path} ({len(schedule.selected)} slots)")


def _find_scored_event(all_ranked: list[ScoredEvent], event_id: str) -> ScoredEvent | None:
    return next((se for se in all_ranked if se.event.id == event_id), None)


def _maybe_upgrade_unpublished_slots(
    schedule: DailySchedule,
    all_ranked: list[ScoredEvent],
) -> tuple[DailySchedule, list[str]]:
    """既存スケジュールの未配信枠を新 batch の高スコア/breaking_shock 記事で差し替える。

    差し替え条件:
    - 新 batch のトップが breaking_shock バケット、または
    - スコアが未配信枠のスコアより 20% 以上高い

    配信済み枠は固定。diversity 制約の再確認は行わない（簡易実装）。

    Returns:
        (更新後スケジュール, 差し替えられたイベントIDリスト)
    """
    replacements: list[str] = []
    used_ids = {e.event_id for e in schedule.selected if e.published}

    # 全 ranked イベントの順位を事前計算（1-indexed）
    rank_by_id = {se.event.id: idx + 1 for idx, se in enumerate(all_ranked)}

    # 差し替え候補: 既存選択に含まれない ranked イベント
    candidates = [se for se in all_ranked if se.event.id not in used_ids]

    for i, entry in enumerate(schedule.selected):
        if entry.published:
            continue  # 配信済みは固定
        if not candidates:
            break

        best = candidates[0]
        is_breaking = best.primary_bucket == "breaking_shock"
        score_much_better = best.score > entry.score * 1.20

        if (is_breaking or score_much_better) and _passes_quality_floor(best):
            reason = "breaking_shock" if is_breaking else f"score {best.score:.1f} vs {entry.score:.1f}"
            logger.info(
                f"[Scheduler] Replacing unpublished slot {i} "
                f"({entry.event_id[:20]}→{best.event.id[:20]}) reason={reason}"
            )
            schedule.selected[i] = scored_event_to_schedule_entry(
                best,
                rank_in_candidates=rank_by_id.get(best.event.id, 0),
                selection_reason=f"replacement:{reason}",
            )
            replacements.append(best.event.id)
            candidates = [se for se in candidates if se.event.id != best.event.id]

    return schedule, replacements


def _archive_batch(
    batch: dict,
    archive_base: Path,
) -> int:
    """batch の raw / normalized ファイルを archive 配下へ移動する。

    archive 構造:
        data/archive/YYYYMMDD/<batch_id>/raw/
        data/archive/YYYYMMDD/<batch_id>/normalized/

    Returns:
        移動に成功したファイル数。
    """
    batch_id: str = batch["batch_id"]
    created_at: str = batch["created_at"]

    # YYYYMMDD をバッチの created_at から取得
    try:
        date_part = created_at[:10].replace("-", "")  # "20260410"
    except Exception:
        date_part = datetime.now(timezone.utc).strftime("%Y%m%d")

    raw_archive = archive_base / date_part / batch_id / "raw"
    norm_archive = archive_base / date_part / batch_id / "normalized"
    raw_archive.mkdir(parents=True, exist_ok=True)
    norm_archive.mkdir(parents=True, exist_ok=True)

    moved = 0
    for src_str in batch.get("raw_files", []):
        src = Path(src_str)
        if src.exists():
            shutil.move(str(src), str(raw_archive / src.name))
            moved += 1
        else:
            logger.warning(f"[Archive] Raw file not found (already moved?): {src}")

    for src_str in batch.get("normalized_files", []):
        src = Path(src_str)
        if src.exists():
            shutil.move(str(src), str(norm_archive / src.name))
            moved += 1
        else:
            logger.warning(f"[Archive] Normalized file not found (already moved?): {src}")

    logger.info(
        f"[Archive] batch={batch_id} → {archive_base / date_part / batch_id} "
        f"({moved} files moved)"
    )
    return moved


import re as _re


def _patch_null_source_titles_from_views(se: "ScoredEvent") -> int:
    """Back-fill null SourceRef titles from japan_view / global_view for pool-restored events.

    Pool snapshots stored before the title-propagation fix have title=None on every SourceRef.
    The japan_view / global_view fields were always populated and contain the same article titles
    in the format "[source_name] title　summary".  Parsing these back fills in the missing titles
    so that the CoherenceGate and evidence.json see real text.

    Returns the number of SourceRef objects whose title was patched.
    """
    def _parse_view(view: str | None) -> dict[str, str]:
        if not view:
            return {}
        result: dict[str, str] = {}
        for line in view.split("\n"):
            m = _re.match(r"^\[(.+?)\]\s*(.+)$", line)
            if m:
                name = m.group(1).strip()
                text = m.group(2).strip()
                # Strip summary appended after ideographic space (全角スペース)
                title = text.split("\u3000")[0].strip()
                if name and title and name not in result:
                    result[name] = title
        return result

    ev = se.event
    jp_map = _parse_view(ev.japan_view)
    en_map = _parse_view(ev.global_view)
    patched = 0

    for src in ev.sources_jp:
        if not src.title and src.name in jp_map:
            src.title = jp_map[src.name]
            patched += 1
    for src in ev.sources_en:
        if not src.title and src.name in en_map:
            src.title = en_map[src.name]
            patched += 1
    if ev.sources_by_locale:
        for locale, refs in ev.sources_by_locale.items():
            view_map = jp_map if locale == "japan" else en_map
            for ref in refs:
                if not ref.title and ref.name in view_map:
                    ref.title = view_map[ref.name]
                    patched += 1

    return patched


def _save_events_to_pool(
    db_path: Path,
    scored_events: "list[ScoredEvent]",
    batch_id: str,
) -> None:
    """現在 batch のスコア済みイベントを recent_event_pool に保存する。

    archived raw/normalized の再読み込みなしに、次回 run でイベントを候補として
    再利用できるようにする。
    """
    now = datetime.now(timezone.utc).isoformat()
    entries: list[dict] = []
    for se in scored_events:
        entries.append({
            "event_id": se.event.id,
            "batch_id": batch_id,
            "created_at": now,
            "event_snapshot": json.dumps(se.model_dump(mode="json"), ensure_ascii=False),
            "source_regions": json.dumps(
                sorted(se.event.sources_by_locale.keys()) if se.event.sources_by_locale else [],
                ensure_ascii=False,
            ),
            "source_languages": json.dumps(
                sorted({
                    ref.language
                    for refs in se.event.sources_by_locale.values()
                    for ref in refs
                    if ref.language
                }),
                ensure_ascii=False,
            ),
            "primary_bucket": se.primary_bucket,
            "appraisal_type": se.appraisal_type,
            "score": round(se.score, 4),
            "story_fingerprint": se.story_fingerprint,
        })
    upsert_recent_event_pool(db_path, entries)


def _write_debug_artifacts(
    output_dir: Path,
    run_stats: dict,
    schedule: "DailySchedule | None",
    pool_stats: dict,
) -> None:
    """debug/ 配下へ 4 つの observability アーティファクトを書き出す。

    どのパス（no_publishable / normal / no_events）からでも呼べるよう、
    schedule=None を許容する。
    """
    try:
        write_source_load_report(run_stats, output_dir)
        write_cross_lang_merge_report(run_stats, output_dir)
        write_quality_floor_report(schedule, output_dir)
        write_pool_upgrade_report(pool_stats, output_dir)
        logger.info(
            f"[Debug] Artifacts written to {output_dir / 'debug'}/ "
            "(source_load_report, cross_lang_merge_report, quality_floor_report, pool_upgrade_report)"
        )
    except Exception as exc:
        logger.warning(f"[Debug] Failed to write debug artifacts: {exc}")


def _write_discovery_audit_safe(
    all_ranked: "list[ScoredEvent]",
    run_stats: dict,
    output_dir: Path,
    schedule: "DailySchedule | None",
) -> None:
    """Discovery Audit を安全に書き出す（失敗してもメインパイプラインに影響しない）。"""
    try:
        write_discovery_audit(all_ranked, run_stats, output_dir, schedule)
    except Exception as exc:
        logger.warning(f"[DiscoveryAudit] Failed to write discovery audit: {exc}")


# ── Gemini Judge helpers ───────────────────────────────────────────────────────

def _run_judge_pass(
    all_ranked: "list[ScoredEvent]",
    budget: "BudgetTracker",
) -> "tuple[dict[str, GeminiJudgeResult], ModelResolution | None]":
    """appraisal 済み候補の上位 JUDGE_CANDIDATE_LIMIT 件に Gemini Judge を適用する。

    Returns:
        (results, resolution)
          results   : event_id → GeminiJudgeResult の dict
                      （ジャッジ無効 or 予算不足の場合は空 dict）
          resolution: ModelResolution（API キー未設定 / ジャッジ無効の場合は None）
    """
    if not JUDGE_ENABLED:
        logger.info("[GeminiJudge] Judge disabled via JUDGE_ENABLED=false — skipping.")
        return {}, None

    judge_client = get_judge_llm_client()
    if judge_client is None:
        logger.info("[GeminiJudge] No Gemini API key — judge pass skipped.")
        return {}, None

    # Retrieve (and log) the model resolution that was performed by get_judge_llm_client().
    resolution: ModelResolution | None = None
    if GEMINI_API_KEY:
        resolution = get_judge_model_resolution(
            GEMINI_API_KEY, JUDGE_MODEL, GEMINI_JUDGE_FALLBACK_MODELS
        )
        logger.info(
            f"[GeminiJudge] Model resolution: "
            f"requested={resolution.requested_model!r}, "
            f"resolved={resolution.resolved_model!r}, "
            f"reason={resolution.resolution_reason!r}"
        )

    from src.triage.gemini_judge import run_gemini_judge, judge_rerank_score

    results: dict[str, GeminiJudgeResult] = {}
    candidates = all_ranked[:JUDGE_CANDIDATE_LIMIT]

    for se in candidates:
        if not budget.can_afford_judge():
            _stop_reason = (
                "publish_reserve_threshold_reached"
                if budget.stopped_exploration_due_to_publish_reserve
                else "script_article_run_reserve_reached"
            )
            logger.warning(
                f"[GeminiJudge] Budget stopped judge after {len(results)} calls "
                f"(reason={_stop_reason}, "
                f"day_remaining={budget.day_remaining}, "
                f"publish_reserve={budget.publish_reserve_calls})"
            )
            break
        jr = run_gemini_judge(se, judge_client)
        se.judge_result = jr
        results[se.event.id] = jr
        budget.record_call("judge")
        budget.record_retry("judge", jr.llm_retry_count)

        # publish_mode early exit: once a viable slot-1 candidate is found,
        # stop spending budget on remaining judge candidates.
        if (
            budget.mode == "publish_mode"
            and jr.judge_error is None
            and jr.publishability_class in _ELIGIBLE_PUBLISHABILITY
        ):
            logger.info(
                f"[GeminiJudge] Viable slot-1 found in publish_mode "
                f"({se.event.id[:20]} class={jr.publishability_class}) — "
                "stopping early to preserve publish reserve."
            )
            break

    if results:
        logger.info(
            f"[GeminiJudge] Judged {len(results)} candidates: "
            + ", ".join(
                f"{eid[:12]}→{jr.publishability_class}(div={jr.divergence_score:.1f})"
                for eid, jr in results.items()
            )
        )
    return results, resolution


def _apply_judge_reranking(
    all_ranked: "list[ScoredEvent]",
) -> "list[ScoredEvent]":
    """judge_result が設定済みの候補にブーストを加えて再ソートする。

    ブーストは最大 ±8pt（tie-breaker 程度の影響）。
    judge_result がない候補は boost=0 で変化なし。
    """
    from src.triage.gemini_judge import judge_rerank_score

    def _sort_key(se: ScoredEvent) -> float:
        from src.triage.freshness import effective_score
        base = effective_score(se.score, se.freshness_decay)
        boost = judge_rerank_score(se)
        return base + boost

    reranked = sorted(all_ranked, key=_sort_key, reverse=True)
    # ログ: 順位変動を確認
    old_ids = [se.event.id for se in all_ranked[:5]]
    new_ids = [se.event.id for se in reranked[:5]]
    if old_ids != new_ids:
        logger.info(
            f"[GeminiJudge] Reranking changed top-5: "
            f"{[i[:12] for i in old_ids]} → {[i[:12] for i in new_ids]}"
        )
    return reranked


def _write_judge_rescue(
    candidate: "ScoredEvent",
    judge_result: "GeminiJudgeResult",
    output_dir: Path,
) -> None:
    """judge が investigate_more と判定した候補のレスキューファイルを出力する。

    出力ファイル:
      data/output/judge_report.json     — 候補の詳細 + ジャッジ理由
      data/output/followup_queries.json — 追加調査クエリリスト
      data/output/followup_queries.md   — 人間可読の追加調査ガイド
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # judge_report.json
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rescue_trigger": "requires_more_evidence + high_potential",
        "candidate": {
            "event_id": candidate.event.id,
            "title": candidate.event.title,
            "score": round(candidate.score, 2),
            "primary_bucket": candidate.primary_bucket,
            "appraisal_type": candidate.appraisal_type,
            "sources_jp_count": len(candidate.event.sources_jp),
            "sources_en_count": len(candidate.event.sources_en),
        },
        "judge": {
            "publishability_class": judge_result.publishability_class,
            "divergence_score": judge_result.divergence_score,
            "blind_spot_global_score": judge_result.blind_spot_global_score,
            "indirect_japan_impact_score_judge": judge_result.indirect_japan_impact_score_judge,
            "authority_signal_score": judge_result.authority_signal_score,
            "why_this_matters_to_japan": judge_result.why_this_matters_to_japan,
            "strongest_perspective_gap": judge_result.strongest_perspective_gap,
            "confidence": judge_result.confidence,
            "hard_claims_supported": judge_result.hard_claims_supported,
            "requires_more_evidence": judge_result.requires_more_evidence,
        },
    }
    report_path = output_dir / "judge_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # followup_queries.json
    followup = {
        "generated_at": report["generated_at"],
        "event_id": candidate.event.id,
        "event_title": candidate.event.title,
        "recommended_followup_queries": judge_result.recommended_followup_queries,
        "recommended_followup_source_types": judge_result.recommended_followup_source_types,
        "judge_why_this_matters": judge_result.why_this_matters_to_japan,
        "judge_perspective_gap": judge_result.strongest_perspective_gap,
    }
    fq_path = output_dir / "followup_queries.json"
    fq_path.write_text(json.dumps(followup, ensure_ascii=False, indent=2), encoding="utf-8")

    # followup_queries.md
    lines = [
        "# Hydrangea News — 追加調査ガイド",
        "",
        f"**候補:** {candidate.event.title}",
        f"**イベントID:** `{candidate.event.id}`",
        f"**生成日時:** {report['generated_at']}",
        "",
        "## なぜ Hydrangea ストーリーかもしれないか",
        f"> {judge_result.why_this_matters_to_japan}",
        "",
        "## 最も鮮明な視点差",
        f"> {judge_result.strongest_perspective_gap}",
        "",
        f"## ジャッジスコア",
        f"- divergence_score: {judge_result.divergence_score:.1f}/10",
        f"- blind_spot_global_score: {judge_result.blind_spot_global_score:.1f}/10",
        f"- indirect_japan_impact: {judge_result.indirect_japan_impact_score_judge:.1f}/10",
        f"- confidence: {judge_result.confidence:.2f}",
        "",
        "## 追加調査クエリ（推奨）",
    ]
    for i, q in enumerate(judge_result.recommended_followup_queries, 1):
        lines.append(f"{i}. {q}")
    lines += [
        "",
        "## 追加取得を推奨するソース種別",
    ]
    for t in judge_result.recommended_followup_source_types:
        lines.append(f"- {t}")
    lines += [
        "",
        "---",
        "*このファイルは Hydrangea Judge パスが自動生成しました。*",
        "*hard_claims_supported=false のため、自動スクリプト生成はスキップされました。*",
    ]
    md_path = output_dir / "followup_queries.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    logger.info(
        f"[GeminiJudge] Rescue files written: "
        f"judge_report.json, followup_queries.json, followup_queries.md "
        f"(candidate={candidate.event.id[:20]}, "
        f"class={judge_result.publishability_class})"
    )


# ── Final Selection constants ──────────────────────────────────────────────────
# EN-only (JP sources==0) blind_spot_global candidates require this judge score
# to qualify for slot-1.
_FINAL_SELECTION_INDIRECT_JAPAN_THRESHOLD: float = 5.0

# Valid publishability classes that may occupy slot-1
_ELIGIBLE_PUBLISHABILITY = frozenset({"linked_jp_global", "blind_spot_global"})

# F-5: Hydrangea コンセプト整合の救済経路（FinalSelection フォールバック）
# publishability_class=investigate_more / insufficient_evidence でも、
# blind_spot / ijai が高ければ flagship 認定する。
# 試運転7-C (2026-04-28) で blind_spot=7.0 / ijai=9.0 にも関わらず
# investigate_more のため reject された案件への対処。
# Hydrangea コンセプト「日本で報じられない海外ニュースを届ける」を
# FinalSelection まで貫徹するため、F-2 (FlagshipGate 緩和) と整合させる。
F5_FLAGSHIP_FALLBACK_CLASSES = frozenset({"investigate_more", "insufficient_evidence"})
F5_BLIND_SPOT_THRESHOLD: float = 5.0
F5_IJAI_THRESHOLD: float = 5.0
F5_MIN_EDITORIAL_MISSION_SCORE: float = 45.0  # F-1 の Editorial Mission Filter 通過済みであること

# Appraisal types that are eligible for quota fallback pre-judge selection
_QUOTA_FALLBACK_ELIGIBLE_APPRAISALS = frozenset({
    "Structural Why",
    "Perspective Inversion",
    "Media Blind Spot",
    "Blind Spot Global",
})

# Judge error types that trigger quota-aware fallback.
# model_not_found is included so that a model-registry failure (models.list
# unavailable at startup + invalid requested model) does not hard-block
# content generation.  It is still reported as a distinct error type in logs
# and run_summary so the root cause is visible.
_QUOTA_FALLBACK_ERROR_TYPES = frozenset({
    "quota_exhausted",
    "temporary_unavailable",
    "model_not_found",
})


def _is_f5_flagship_eligible(se: "ScoredEvent") -> bool:
    """F-5 フォールバック: Hydrangea コンセプトに基づく flagship 認定。

    publishability_class=investigate_more / insufficient_evidence でも、
    blind_spot_global_score または indirect_japan_impact_score_judge が
    閾値以上であれば flagship 認定する。

    前提: editorial_mission_score >= F5_MIN_EDITORIAL_MISSION_SCORE
          (F-1 の EditorialMissionFilter 通過済みでないと救済しない)。
    """
    jr = se.judge_result
    if jr is None or jr.judge_error is not None:
        return False

    # editorial_mission_filter を通過していること（低品質候補の救済を防ぐ）
    if (se.editorial_mission_score or 0.0) < F5_MIN_EDITORIAL_MISSION_SCORE:
        return False

    # publishability_class が F-5 の救済対象であること
    if jr.publishability_class not in F5_FLAGSHIP_FALLBACK_CLASSES:
        return False

    # blind_spot または ijai (indirect_japan_impact) が閾値以上であること
    return (
        jr.blind_spot_global_score >= F5_BLIND_SPOT_THRESHOLD
        or jr.indirect_japan_impact_score_judge >= F5_IJAI_THRESHOLD
    )


def _find_eligible_judged_slot1(
    all_ranked: "list[ScoredEvent]",
    judge_results: "dict[str, GeminiJudgeResult]",
    indirect_japan_threshold: float = _FINAL_SELECTION_INDIRECT_JAPAN_THRESHOLD,
) -> tuple["ScoredEvent | None", str]:
    """Judge が評価した候補の中から、slot-1 に適格な最上位候補を返す。

    all_ranked は judge reranking 後の effective_score 降順リスト。
    judge_results が空の場合は (None, "judge_not_run") を返す（呼び出し元で分岐する）。

    Eligibility conditions:
      Primary path (publishability_class ベース):
        1. se.judge_result is not None (judged by Gemini judge)
        2. publishability_class in {linked_jp_global, blind_spot_global}
        3. If JP sources == 0 (EN-only): must be blind_spot_global
           AND indirect_japan_impact_score_judge >= indirect_japan_threshold

      F-5 fallback path (Hydrangea コンセプト整合の救済):
        publishability_class が investigate_more / insufficient_evidence でも、
        blind_spot_global_score または indirect_japan_impact_score_judge が
        閾値以上、かつ editorial_mission_score >= 45.0 ならば flagship 認定。
        (詳細: _is_f5_flagship_eligible)

    Returns:
        (best_eligible_se, reason_str)  — reason_str explains why it was chosen.
        (None, block_reason_str)        — if no eligible candidate found.
    """
    if not judge_results:
        return None, "judge_not_run"

    from src.triage.coherence_gate import apply_coherence_gate

    eligible: list[ScoredEvent] = []
    f5_fallback_event_ids: set[str] = set()
    for se in all_ranked:
        jr = se.judge_result
        if jr is None or jr.judge_error is not None:
            continue
        cls = jr.publishability_class

        # Primary path: publishability_class ∈ {linked_jp_global, blind_spot_global}
        flagship_eligible = cls in _ELIGIBLE_PUBLISHABILITY
        if flagship_eligible:
            jp_count = len(se.event.sources_jp)
            if jp_count == 0:
                # EN-only: only blind_spot_global with strong indirect impact qualifies
                if cls != "blind_spot_global":
                    flagship_eligible = False
                elif jr.indirect_japan_impact_score_judge < indirect_japan_threshold:
                    flagship_eligible = False

        # F-5 fallback path: Hydrangea コンセプト整合の救済
        flagship_eligible_by_f5 = (
            (not flagship_eligible) and _is_f5_flagship_eligible(se)
        )

        if not (flagship_eligible or flagship_eligible_by_f5):
            continue

        # Coherence gate: ensure JP↔overseas sources are about the same story
        # (適用クラスは判定時点の publishability_class を使う)
        _coh_passed, _coh_block = apply_coherence_gate(se, cls)
        if not _coh_passed:
            logger.warning(
                f"[FinalSelection] Coherence gate blocked {se.event.id[:20]} "
                f"(class={cls}): {_coh_block}"
            )
            continue

        # F-5 経路で eligible になった場合は WARNING ログで可視化
        if flagship_eligible_by_f5:
            logger.warning(
                f"[FinalSelection] F-5 fallback applied: event={se.event.id[:16]} "
                f"class={cls} "
                f"blind_spot={jr.blind_spot_global_score:.1f} "
                f"ijai={jr.indirect_japan_impact_score_judge:.1f} "
                f"editorial_mission={(se.editorial_mission_score or 0.0):.1f} "
                f"→ flagship 認定 (Hydrangea concept alignment)"
            )
            f5_fallback_event_ids.add(se.event.id)

        eligible.append(se)

    if not eligible:
        return None, "no_eligible_judged_flagship"

    # all_ranked is already sorted by effective_score (judge boost applied),
    # so the first eligible candidate is the best.
    best = eligible[0]
    jr_best = best.judge_result  # guaranteed non-None by loop above
    via_f5 = best.event.id in f5_fallback_event_ids
    reason = (
        f"judged_flagship{'_f5' if via_f5 else ''}:{jr_best.publishability_class}"  # type: ignore[union-attr]
        f":score={best.score:.1f}"
        f":divergence={jr_best.divergence_score:.1f}"  # type: ignore[union-attr]
    )
    return best, reason


def _find_quota_fallback_slot1(
    all_ranked: "list[ScoredEvent]",
    judge_results: "dict[str, GeminiJudgeResult]",
) -> "tuple[ScoredEvent | None, str]":
    """Judge が quota エラーで失敗した場合の保守的 fallback 候補を探す。

    条件:
      1. judge_results 内に quota_exhausted / temporary_unavailable エラーが存在する
      2. 以下を全て満たす最上位の未審判候補を返す:
         - JP sources >= 1
         - overseas sources >= 1
         - cross-lang support あり（score_breakdown の cross_lang_bonus > 0、
           または sources_by_locale に japan + 非 japan キーが存在）
         - appraisal_type ∈ _QUOTA_FALLBACK_ELIGIBLE_APPRAISALS
         - primary_bucket != "sports"

    Returns:
        (fallback_se, reason_str)   — 条件を満たす最上位候補
        (None, rejection_reason)    — 条件を満たす候補が存在しない
    """
    # 1. quota / unavailable エラーが実際に存在するか確認
    quota_error_count = sum(
        1 for jr in judge_results.values()
        if jr.judge_error_type in _QUOTA_FALLBACK_ERROR_TYPES
    )
    if quota_error_count == 0:
        return None, "no_quota_errors_in_judge_results"

    # 2. all_ranked はすでに effective_score 降順 → 最初に条件を満たした候補が最強
    for se in all_ranked:
        # quota/unavailable エラーで失敗した候補は fallback 対象（証拠は揃っている）
        # 成功した審判済み候補はスキップ（eligible ならすでに _find_eligible_judged_slot1 で選ばれるはず）
        jr = se.judge_result
        if jr is not None:
            if jr.judge_error_type not in _QUOTA_FALLBACK_ERROR_TYPES:
                # 成功または非 quota エラー → fallback 対象外
                continue

        # JP sources >= 1
        jp_count = len(se.event.sources_jp)
        if jp_count == 0 and se.event.sources_by_locale:
            jp_count = len(se.event.sources_by_locale.get("japan", []))
        if jp_count < 1:
            continue

        # overseas sources >= 1
        if se.event.sources_by_locale:
            overseas_count = sum(
                len(refs) for loc, refs in se.event.sources_by_locale.items()
                if loc != "japan"
            )
        else:
            overseas_count = len(se.event.sources_en)
        if overseas_count < 1:
            continue

        # cross-lang support
        has_cross_lang = bool(se.score_breakdown.get("cross_lang_bonus", 0))
        if not has_cross_lang and se.event.sources_by_locale:
            has_cross_lang = (
                "japan" in se.event.sources_by_locale
                and any(loc != "japan" for loc in se.event.sources_by_locale)
            )
        if not has_cross_lang:
            continue

        # appraisal_type check
        if se.appraisal_type not in _QUOTA_FALLBACK_ELIGIBLE_APPRAISALS:
            continue

        # not sports
        if se.primary_bucket == "sports":
            continue

        # Coherence gate: same semantic check applied to judged flagship candidates
        from src.triage.coherence_gate import apply_coherence_gate
        _coh_passed, _coh_block = apply_coherence_gate(se, "quota_fallback_prejudge")
        if not _coh_passed:
            logger.warning(
                f"[QuotaFallback] Coherence gate blocked {se.event.id[:20]} "
                f"(appraisal={se.appraisal_type}): {_coh_block}"
            )
            continue

        reason = (
            f"quota_fallback_prejudge"
            f":appraisal={se.appraisal_type}"
            f":jp_sources={jp_count}"
            f":overseas_sources={overseas_count}"
            f":score={se.score:.1f}"
            f":quota_errors={quota_error_count}"
        )
        return se, reason

    return None, "no_safe_fallback_candidate_with_jp_overseas_crosslang_appraisal"


def _write_latest_candidate_report(
    output_dir: Path,
    scheduled_slot1_id: "str | None",
    reranked_top_id: "str | None",
    final_selected_slot1_id: "str | None",
    slot1_selection_source: str,
    slot1_block_reason: "str | None",
    all_ranked: "list[ScoredEvent]",
    judge_results: "dict[str, GeminiJudgeResult]",
    generated_event_id: "str | None" = None,
    published_event_id: "str | None" = None,
    selection_override_applied: bool = False,
    final_selection_fallback_used: bool = False,
    final_selection_fallback_reason: "str | None" = None,
    quota_fallback_candidate_id: "str | None" = None,
    model_resolution: "ModelResolution | None" = None,
    budget_mode_summary: "dict | None" = None,
    av_render_summary: "dict | None" = None,
) -> None:
    """data/output/latest_candidate_report.md を書き出す。

    内容:
      - scheduled slot (scheduler が選んだ slot-1)
      - reranked best candidate (judge reranking 後のトップ)
      - final slot-1 (実際に生成に使う候補)
      - なぜ final slot-1 が選ばれたか
      - なぜ強い候補がスキップされたか、またはなぜ generation がブロックされたか
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    def _se_for(eid: "str | None") -> "ScoredEvent | None":
        if not eid:
            return None
        return next((se for se in all_ranked if se.event.id == eid), None)

    def _judge_info(se: "ScoredEvent | None") -> str:
        if se is None:
            return "N/A"
        jr = se.judge_result
        if jr is None:
            return "not_judged"
        if jr.judge_error:
            return f"judge_error: {jr.judge_error}"
        return (
            f"`{jr.publishability_class}` "
            f"(div={jr.divergence_score:.1f}, "
            f"blind_spot={jr.blind_spot_global_score:.1f}, "
            f"indirect_jp={jr.indirect_japan_impact_score_judge:.1f})"
        )

    def _src_info(se: "ScoredEvent | None") -> str:
        if se is None:
            return "N/A"
        return f"JP={len(se.event.sources_jp)}, EN={len(se.event.sources_en)}"

    def _title(se: "ScoredEvent | None", eid: "str | None" = None) -> str:
        if se:
            return f"`{se.event.id[:20]}` — {se.event.title[:70]}"
        return f"`{eid or 'N/A'}` (not in current ranked list)"

    sched_se  = _se_for(scheduled_slot1_id)
    rerank_se = _se_for(reranked_top_id)
    final_se  = _se_for(final_selected_slot1_id)

    judged_ids = set(judge_results.keys())
    judged_eligible = [
        se for se in all_ranked
        if se.judge_result is not None
        and se.judge_result.judge_error is None
        and se.judge_result.publishability_class in _ELIGIBLE_PUBLISHABILITY
    ]

    _mr_req = model_resolution.requested_model if model_resolution else JUDGE_MODEL
    _mr_res = model_resolution.resolved_model if model_resolution else JUDGE_MODEL
    _mr_reason = model_resolution.resolution_reason if model_resolution else "not_resolved"

    lines: list[str] = [
        "# Hydrangea News — Latest Candidate Report",
        "",
        f"*Generated: {datetime.now(timezone.utc).isoformat()}*",
        "",
        "---",
        "",
        "## 0. Judge Model Resolution",
        "",
        f"- **requested:** `{_mr_req}`",
        f"- **resolved:**  `{_mr_res}`",
        f"- **reason:**    `{_mr_reason}`",
        "",
        "---",
        "",
        "## 1. Scheduled Slot-1 (scheduler output)",
        "",
        f"**ID:** {_title(sched_se, scheduled_slot1_id)}",
        f"**Score:** {sched_se.score:.1f}" if sched_se else "**Score:** N/A",
        f"**Bucket:** `{sched_se.primary_bucket}`" if sched_se else "",
        f"**Sources:** {_src_info(sched_se)}",
        f"**Judge result:** {_judge_info(sched_se)}",
        "",
        "## 2. Reranked Top Candidate (after judge boost)",
        "",
        f"**ID:** {_title(rerank_se, reranked_top_id)}",
        f"**Score:** {rerank_se.score:.1f}" if rerank_se else "**Score:** N/A",
        f"**Bucket:** `{rerank_se.primary_bucket}`" if rerank_se else "",
        f"**Sources:** {_src_info(rerank_se)}",
        f"**Judge result:** {_judge_info(rerank_se)}",
        "",
        "## 3. Final Slot-1 (used for generation)",
        "",
    ]

    if slot1_block_reason:
        lines += [
            f"**GENERATION BLOCKED** — reason: `{slot1_block_reason}`",
            "",
            "Generation was blocked because no judged candidate satisfied the slot-1 eligibility",
            "criteria (publishability_class ∈ {linked_jp_global, blind_spot_global}, "
            "and for EN-only stories: blind_spot_global with "
            f"indirect_japan_impact_score_judge ≥ {_FINAL_SELECTION_INDIRECT_JAPAN_THRESHOLD}).",
            "",
        ]
    else:
        lines += [
            f"**ID:** {_title(final_se, final_selected_slot1_id)}",
            f"**Score:** {final_se.score:.1f}" if final_se else "**Score:** N/A",
            f"**Bucket:** `{final_se.primary_bucket}`" if final_se else "",
            f"**Sources:** {_src_info(final_se)}",
            f"**Judge result:** {_judge_info(final_se)}",
            f"**Selection source:** `{slot1_selection_source}`",
            "",
        ]

    # ── Publish identity summary (Pass 1.5) ──────────────────────────────────
    if generated_event_id or published_event_id or selection_override_applied:
        lines += [
            "## 4. Publish Identity",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| scheduled_slot1_id | `{scheduled_slot1_id or 'N/A'}` |",
            f"| final_selected_slot1_id | `{final_selected_slot1_id or 'N/A'}` |",
            f"| generated_event_id | `{generated_event_id or 'N/A'}` |",
            f"| published_event_id | `{published_event_id or 'N/A'}` |",
            f"| selection_override_applied | `{selection_override_applied}` |",
        ]
        if selection_override_applied:
            lines += [
                f"| override_reason | `{slot1_selection_source}` |",
                "",
                f"> **Override**: scheduler nominated `{scheduled_slot1_id}` "
                f"but FinalSelection promoted `{final_selected_slot1_id}` "
                f"({slot1_selection_source}). "
                "The scheduled slot was marked consumed; "
                "the pool marks the generated event as published.",
            ]
        else:
            lines += [""]

    lines += [
        "## 5. Why Final Slot-1 Won",
        "",
    ]

    if slot1_block_reason:
        lines += [
            "No generation occurred. See block reason above.",
            "",
        ]
    elif final_se and final_se.judge_result and final_se.judge_result.judge_error is None:
        jr = final_se.judge_result
        _ciq = final_se.coherence_input_quality or {}
        lines += [
            f"- Judged by Gemini with `publishability_class={jr.publishability_class}`",
            f"- divergence_score={jr.divergence_score:.1f}, "
            f"blind_spot_global_score={jr.blind_spot_global_score:.1f}, "
            f"indirect_japan_impact_score_judge={jr.indirect_japan_impact_score_judge:.1f}",
            f"- Why it matters: {jr.why_this_matters_to_japan or '(not provided)'}",
            f"- Perspective gap: {jr.strongest_perspective_gap or '(not provided)'}",
            f"- Selection source: {slot1_selection_source}",
            f"- semantic_coherence_score: {final_se.semantic_coherence_score}",
            f"- coherence_gate_passed: {final_se.coherence_gate_passed}",
            f"- candidate_blacklist_flags: {final_se.candidate_blacklist_flags}",
            f"- slot1_source_titles_present_jp: {sum(1 for s in final_se.event.sources_jp if s.title)}"
            f" / {len(final_se.event.sources_jp)}",
            f"- slot1_source_titles_present_en: {sum(1 for s in final_se.event.sources_en if s.title)}"
            f" / {len(final_se.event.sources_en)}",
            f"- slot1_coherence_input_quality: {_ciq}",
            f"- slot1_overlap_signals: {final_se.coherence_overlap_signals}",
            "",
        ]
    else:
        lines += [
            f"- Selected by `{slot1_selection_source}` (no judge result — judge did not run or candidate not judged).",
            "",
        ]

    # ── Coherence Gate summary ────────────────────────────────────────────────
    coherence_blocked_in_report = [
        se for se in all_ranked if se.coherence_gate_passed is False
    ]
    if coherence_blocked_in_report:
        lines += [
            "## 5b. Coherence Gate — Blocked Candidates",
            "",
            "These candidates were blocked by the semantic coherence gate before slot-1 selection:",
            "",
        ]
        for se_c in coherence_blocked_in_report:
            lines.append(
                f"- `{se_c.event.id[:20]}` — {se_c.event.title[:60]} "
                f"[score={se_c.semantic_coherence_score}, "
                f"blacklist={se_c.candidate_blacklist_flags}, "
                f"reason={se_c.coherence_block_reason}]"
            )
        lines.append("")

    lines += [
        "## 6. Skipped / Blocked Candidates",
        "",
    ]

    if judged_ids:
        lines.append(f"**Judged candidates ({len(judged_ids)} total):**")
        lines.append("")
        for se in all_ranked:
            jr = se.judge_result
            if jr is None:
                continue
            is_final = (se.event.id == final_selected_slot1_id)
            marker = " ← **SELECTED**" if is_final else ""
            skip_reason = ""
            if not is_final:
                cls = jr.publishability_class if jr.judge_error is None else "judge_error"
                if cls not in _ELIGIBLE_PUBLISHABILITY:
                    skip_reason = f"skipped: publishability_class=`{cls}` not eligible"
                elif len(se.event.sources_jp) == 0 and cls != "blind_spot_global":
                    skip_reason = f"skipped: EN-only + class=`{cls}` (must be blind_spot_global)"
                elif (len(se.event.sources_jp) == 0
                      and cls == "blind_spot_global"
                      and jr.indirect_japan_impact_score_judge < _FINAL_SELECTION_INDIRECT_JAPAN_THRESHOLD):
                    skip_reason = (
                        f"skipped: EN-only blind_spot_global but "
                        f"indirect_japan_impact={jr.indirect_japan_impact_score_judge:.1f} "
                        f"< threshold={_FINAL_SELECTION_INDIRECT_JAPAN_THRESHOLD}"
                    )
                elif jr.judge_error:
                    skip_reason = f"skipped: judge_error={jr.judge_error}"
                else:
                    skip_reason = "eligible but lower score than final selection"
            lines.append(
                f"- `{se.event.id[:20]}` score={se.score:.1f} "
                f"class={jr.publishability_class if jr.judge_error is None else 'judge_error'}"
                f"{marker}"
                + (f" — {skip_reason}" if skip_reason else "")
            )
        lines.append("")

        not_judged = [se for se in all_ranked if se.judge_result is None]
        if not_judged:
            lines.append(
                f"**Not-judged candidates ({len(not_judged)} — excluded from slot-1 when judge ran):**"
            )
            lines.append("")
            for se in not_judged[:5]:
                is_sched = (se.event.id == scheduled_slot1_id)
                note = " ← was scheduler's slot-1 choice" if is_sched else ""
                lines.append(
                    f"- `{se.event.id[:20]}` score={se.score:.1f} "
                    f"bucket=`{se.primary_bucket}`{note}"
                )
            if len(not_judged) > 5:
                lines.append(f"- ... and {len(not_judged) - 5} more")
            lines.append("")
    else:
        lines += [
            "Judge did not run (JUDGE_ENABLED=false or no API key/budget). "
            "Slot-1 determined by scheduler + flagship gate only.",
            "",
        ]

    # ── Quota Fallback Status (Pass 2A) ──────────────────────────────────────
    # Show quota error breakdown and fallback decision
    quota_errors = [
        (eid, jr) for eid, jr in judge_results.items()
        if jr.judge_error_type in _QUOTA_FALLBACK_ERROR_TYPES
    ]
    if quota_errors or final_selection_fallback_used:
        lines += ["## 7. Quota Fallback Status", ""]
        if quota_errors:
            lines.append(f"**Judge quota/unavailable errors ({len(quota_errors)} candidate(s) affected):**")
            lines.append("")
            for eid, jr in quota_errors:
                se_q = next((s for s in all_ranked if s.event.id == eid), None)
                title_q = se_q.event.title[:60] if se_q else eid
                lines.append(
                    f"- `{eid[:20]}` — {title_q} "
                    f"[error_type=`{jr.judge_error_type}`]"
                )
            lines.append("")

        if final_selection_fallback_used and quota_fallback_candidate_id:
            fb_se = next(
                (s for s in all_ranked if s.event.id == quota_fallback_candidate_id), None
            )
            lines += [
                "**Quota fallback ACTIVATED** — generation proceeded with pre-judge candidate.",
                "",
                f"**Fallback candidate:** `{quota_fallback_candidate_id[:20]}`"
                + (f" — {fb_se.event.title[:60]}" if fb_se else ""),
                f"**Fallback reason:** `{final_selection_fallback_reason}`",
                "",
                "**Why this fallback is considered safe:**",
                "- JP sources ≥ 1 (Japanese perspective present)",
                "- Overseas sources ≥ 1 (cross-border story)",
                "- Cross-lang support confirmed (BFS cluster or bilingual sources)",
                "- Appraisal type is editorially eligible",
                "- Not sports / not JP-only",
                "",
            ]
        elif quota_errors and not final_selection_fallback_used and slot1_block_reason:
            lines += [
                "**Quota fallback NOT activated** — no safe pre-judge candidate satisfied "
                "all criteria (JP sources ≥ 1, overseas sources ≥ 1, cross-lang, eligible appraisal).",
                f"**Block reason:** `{slot1_block_reason}`",
                "",
            ]

    # ── Editorial Mission Filter summary ──────────────────────────────────────
    mission_rejected = [se for se in all_ranked if se.why_rejected_before_generation]
    if mission_rejected:
        lines += [
            "## 8. Editorial Mission Filter — Rejected Before Generation",
            "",
            f"**{len(mission_rejected)} candidate(s) rejected by editorial mission filter "
            f"(below threshold):**",
            "",
        ]
        for se_v in mission_rejected[:10]:
            ems = se_v.editorial_mission_score
            ems_str = f"{ems:.1f}" if ems is not None else "N/A"
            lines.append(
                f"- `{se_v.event.id[:20]}` score={se_v.score:.1f} "
                f"mission={ems_str} — "
                f"{se_v.event.title[:60]}"
            )
            lines.append(
                f"  *why_rejected:* `{se_v.why_rejected_before_generation}`"
            )
        if len(mission_rejected) > 10:
            lines.append(f"  *(and {len(mission_rejected) - 10} more)*")
        lines.append("")

    # ── Slot-1 editorial rationale ───────────────────────────────────────────
    if final_se and final_se.why_slot1_won_editorially:
        lines += [
            "## 9. Why Slot-1 Won Editorially",
            "",
            final_se.why_slot1_won_editorially,
            "",
        ]

    # ── Budget Mode & Publish Reserve ────────────────────────────────────────
    if budget_mode_summary:
        _bm = budget_mode_summary
        _reserve_ok = _bm.get("publish_reserve_preserved", True)
        _slot1_ok = _bm.get("slot1_budget_guaranteed", True)
        _stopped = _bm.get("stopped_exploration_due_to_publish_reserve", False)
        _reserve_status = "**PRESERVED** ✓" if _reserve_ok else "**NOT PRESERVED** ✗"
        _slot1_status = "**GUARANTEED** ✓" if _slot1_ok else "**NOT GUARANTEED** ✗"

        lines += [
            "## 10. Budget Mode & Publish Reserve",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| run_mode | `{_bm.get('run_mode', 'N/A')}` |",
            f"| daily_budget_total | {_bm.get('daily_budget_total', 'N/A')} |",
            f"| exploration_budget_used | {_bm.get('exploration_budget_used', 'N/A')} |",
            f"| publish_reserve_budget | {_bm.get('publish_reserve_budget', 'N/A')} |",
            f"| publish_reserve_preserved | {_reserve_ok} |",
            f"| stopped_exploration_due_to_publish_reserve | {_stopped} |",
            f"| slot1_budget_guaranteed | {_slot1_ok} |",
            "",
            f"**Publish reserve:** {_reserve_status}",
            f"**Slot-1 production budget:** {_slot1_status}",
            "",
        ]

        # Classify "no generation" reason
        if slot1_block_reason or not final_selected_slot1_id:
            lines += ["**No generation occurred. Reason classification:**", ""]
            if _stopped and not _reserve_ok:
                lines.append(
                    "- **(b) Daily budget exhausted before reserve** — "
                    "exploration consumed the day budget before the publish reserve "
                    "threshold was established."
                )
            elif slot1_block_reason and (
                "no_eligible" in (slot1_block_reason or "")
                or "flagship_gate" in (slot1_block_reason or "")
                or "no_publishable" in (slot1_block_reason or "")
                or "editorial_mission_filter" in (slot1_block_reason or "")
            ):
                if _reserve_ok:
                    lines.append(
                        "- **(c) Reserve preserved but no eligible slot-1** — "
                        f"publish reserve was intact but no candidate passed the gates "
                        f"(block_reason=`{slot1_block_reason}`)."
                    )
                else:
                    lines.append(
                        "- **(a) No candidate passed gates** — "
                        f"`{slot1_block_reason}`"
                    )
            else:
                lines.append(
                    f"- **(a) No candidate passed gates** — "
                    f"`{slot1_block_reason or 'unknown'}`"
                )
            lines.append("")

    # ── Audio & Video Render ─────────────────────────────────────────────────
    if av_render_summary is not None:
        _av = av_render_summary
        _audio_ok = _av.get("audio_generated", False)
        _video_ok = _av.get("video_generated", False)
        _av_status = "GENERATED" if _audio_ok else "SKIPPED"
        _mp4_status = "GENERATED" if _video_ok else "SKIPPED"
        lines += [
            "## 11. Audio & Video Render",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| audio_render_enabled | `{_av.get('audio_render_enabled', False)}` |",
            f"| video_render_enabled | `{_av.get('video_render_enabled', False)}` |",
            f"| audio_status | **{_av_status}** |",
            f"| video_status | **{_mp4_status}** |",
            f"| voiceover_path | `{_av.get('voiceover_path') or 'N/A'}` |",
            f"| review_mp4_path | `{_av.get('review_mp4_path') or 'N/A'}` |",
            f"| render_manifest_path | `{_av.get('render_manifest_path') or 'N/A'}` |",
            f"| total_duration_sec | {_av.get('total_duration_sec') or 'N/A'} |",
            f"| placeholder_count | {_av.get('placeholder_count', 0)} |",
        ]
        _mismatches = _av.get("timing_mismatches", [])
        if _mismatches:
            lines += [
                f"| timing_mismatches | {len(_mismatches)} segment(s) with >0.5s mismatch |",
            ]
            lines.append("")
            lines.append("**Timing mismatches (actual vs target >0.5s):**")
            lines.append("")
            for m in _mismatches:
                lines.append(
                    f"- `{m.get('scene_id', '?')}` — "
                    f"delta={m.get('mismatch_sec', '?'):+.2f}s"
                    if isinstance(m.get("mismatch_sec"), (int, float))
                    else f"- `{m.get('scene_id', '?')}` — {m}"
                )
        else:
            lines.append(f"| timing_mismatches | 0 |")
        if _av.get("error"):
            lines += [
                "",
                f"> **Render error:** `{_av['error']}`",
            ]
        lines.append("")

    lines += [
        "---",
        "",
        "*This report is generated automatically by the Hydrangea News pipeline.*",
    ]

    report_path = output_dir / "latest_candidate_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"[FinalSelection] Candidate report written: {report_path}")


def _build_judge_summary(
    judge_results: "dict[str, GeminiJudgeResult]",
    all_ranked: "list[ScoredEvent]",
    slot1_se: "ScoredEvent | None",
    slot1_authority_pair: list[str],
    final_selection_fallback_used: bool = False,
    final_selection_fallback_reason: "str | None" = None,
    quota_fallback_candidate_id: "str | None" = None,
    quota_fallback_candidate_title: "str | None" = None,
    model_resolution: "ModelResolution | None" = None,
) -> dict:
    """run_summary に含める judge サマリを構築する。"""
    # Resolve requested/resolved model names for observability.
    # JUDGE_MODEL は config で role-based に解決済み (GEMINI_JUDGE_MODEL と同値)。
    _req = model_resolution.requested_model if model_resolution else JUDGE_MODEL
    _res = model_resolution.resolved_model if model_resolution else JUDGE_MODEL
    _res_reason = model_resolution.resolution_reason if model_resolution else "not_resolved"

    if not judge_results:
        return {
            "judge_enabled": False,
            "judge_model_requested": _req,
            "judge_model_resolved": _res,
            "judge_model_resolution_reason": _res_reason,
            "judge_model_used": _res,
            "judged_count": 0,
            "judge_error_type_counts": {},
            "judge_quota_exhausted_count": 0,
            "judge_temporary_unavailable_count": 0,
            "judge_model_not_found_count": 0,
            "final_selection_fallback_used": False,
            "final_selection_fallback_reason": None,
            "quota_fallback_candidate_id": None,
            "quota_fallback_candidate_title": None,
        }

    publishability_counts: dict[str, int] = {}
    error_type_counts: dict[str, int] = {}
    for jr in judge_results.values():
        c = jr.publishability_class
        publishability_counts[c] = publishability_counts.get(c, 0) + 1
        if jr.judge_error_type:
            error_type_counts[jr.judge_error_type] = (
                error_type_counts.get(jr.judge_error_type, 0) + 1
            )

    top_blind_spot = [
        {"event_id": se.event.id[:20], "title": se.event.title[:60],
         "blind_spot_score": se.judge_result.blind_spot_global_score}  # type: ignore[union-attr]
        for se in all_ranked
        if se.judge_result and se.judge_result.publishability_class == "blind_spot_global"
    ][:3]

    top_divergence = [
        {"event_id": se.event.id[:20], "title": se.event.title[:60],
         "divergence_score": se.judge_result.divergence_score}  # type: ignore[union-attr]
        for se in all_ranked
        if se.judge_result and se.judge_result.divergence_score >= 5.0
    ][:3]

    slot1_info: dict = {"event_id": None}
    if slot1_se:
        jr1 = slot1_se.judge_result
        slot1_info = {
            "event_id": slot1_se.event.id[:20],
            "publishability_class": jr1.publishability_class if jr1 else "not_judged",
            "authority_pair_used": slot1_authority_pair,
            "grounded_by_evidence_only": True,  # guardrail により常に true
            "semantic_coherence_score": slot1_se.semantic_coherence_score,
            "coherence_gate_passed": slot1_se.coherence_gate_passed,
            "coherence_block_reason": slot1_se.coherence_block_reason,
            "candidate_blacklist_flags": slot1_se.candidate_blacklist_flags,
        }

    # Coherence stats across all judged candidates
    coherence_blocked = [
        {"event_id": se.event.id[:20], "title": se.event.title[:60],
         "coherence_score": se.semantic_coherence_score,
         "block_reason": se.coherence_block_reason,
         "blacklist_flags": se.candidate_blacklist_flags}
        for se in all_ranked
        if se.coherence_gate_passed is False
    ][:5]

    return {
        "judge_enabled": True,
        "judge_model_requested": _req,
        "judge_model_resolved": _res,
        "judge_model_resolution_reason": _res_reason,
        "judge_model_used": _res,
        "judged_count": len(judge_results),
        "publishability_class_counts": publishability_counts,
        "judge_error_type_counts": error_type_counts,
        "judge_quota_exhausted_count": error_type_counts.get("quota_exhausted", 0),
        "judge_temporary_unavailable_count": error_type_counts.get("temporary_unavailable", 0),
        "judge_model_not_found_count": error_type_counts.get("model_not_found", 0),
        "top_blind_spot_global": top_blind_spot,
        "top_divergence_candidates": top_divergence,
        "slot1": slot1_info,
        "coherence_blocked_candidates": coherence_blocked,
        "final_selection_fallback_used": final_selection_fallback_used,
        "final_selection_fallback_reason": final_selection_fallback_reason,
        "quota_fallback_candidate_id": quota_fallback_candidate_id,
        "quota_fallback_candidate_title": quota_fallback_candidate_title,
    }


def _check_upgrade_eligible(
    pool_se: "ScoredEvent",
    published_info: dict,
    pool_row: dict,
) -> tuple[bool, str]:
    """配信済みストーリーへの upgrade 条件を検証する。

    Returns:
        (eligible: bool, reason: str)
    """
    old_score: float = published_info.get("score", 0.0)
    old_regions: set[str] = set(published_info.get("source_regions", []))
    old_appraisal: str | None = published_info.get("appraisal_type")

    new_regions: set[str] = set(json.loads(pool_row.get("source_regions", "[]")))
    new_appraisal: str | None = pool_se.appraisal_type
    new_score: float = pool_se.score

    # 新しい地域が増えた
    added_regions = new_regions - old_regions
    if added_regions:
        return True, f"new_regions:{sorted(added_regions)}"

    # スコアが 10+ 以上改善した
    if new_score >= old_score + 10.0:
        return True, f"score_improved:{old_score:.1f}→{new_score:.1f}"

    # appraisal_type が null → meaningful に変わった
    if old_appraisal is None and new_appraisal is not None:
        return True, f"appraisal_upgraded:null→{new_appraisal}"

    # breaking_shock は常に upgrade 対象
    if pool_row.get("primary_bucket") == "breaking_shock":
        return True, "breaking_shock_upgrade"

    return False, ""


def _build_combined_candidate_pool(
    db_path: Path,
    current_ranked: "list[ScoredEvent]",
    batch_id: str,
    window_hours: int = DEFAULT_WINDOW_HOURS,
) -> tuple["list[ScoredEvent]", dict]:
    """現在 batch + 直近プールの和集合から候補リストを構築する。

    Steps:
    1. current_ranked の story_fingerprint を確定
    2. 期限切れプールイベントを expire
    3. プールから直近 window_hours 以内の未配信イベントをロード
    4. freshness decay を適用
    5. 配信済み fingerprint との重複抑制（upgrade 条件チェック）
    6. 現在 batch の fingerprint と重複するプールイベントをスキップ
    7. effective_score でソートして結合リストを返す

    Returns:
        (combined_ranked, pool_stats_dict)
    """
    # Step 1: Ensure current events have fingerprints
    for se in current_ranked:
        if not se.story_fingerprint:
            se.story_fingerprint = compute_story_fingerprint(se.event)
        se.freshness_decay = 1.0
        se.from_recent_pool = False

    current_fps: set[str] = {se.story_fingerprint for se in current_ranked if se.story_fingerprint}

    # Step 2: Expire old pool events; capture count for stats
    db_expired_count = expire_old_pool_events(db_path, max_hours=MAX_WINDOW_HOURS)

    # Step 3: Load pool events (other batches, unpublished, within window)
    pool_rows = get_recent_pool_events(
        db_path, window_hours=window_hours, exclude_batch_id=batch_id
    )

    # Step 4+5+6: Restore, apply decay, dedup
    published_fps = get_published_story_fingerprints(db_path, within_hours=72)
    now = datetime.now(timezone.utc)

    pool_events: list[ScoredEvent] = []
    expired_count = 0
    duplicate_suppressed_count = 0
    upgraded_count = 0

    for row in pool_rows:
        try:
            se = ScoredEvent.model_validate(json.loads(row["event_snapshot"]))
        except Exception as exc:
            logger.warning(f"[Pool] Failed to restore event {row['event_id']}: {exc}")
            continue

        # Freshness decay based on wall-clock age
        created_at_str: str = row["created_at"]
        try:
            created_at = datetime.fromisoformat(created_at_str)
        except ValueError:
            logger.warning(f"[Pool] Bad created_at for {row['event_id']}: {created_at_str!r}")
            continue

        decay = compute_freshness_decay(created_at, now)
        if decay == 0.0:
            expired_count += 1
            continue

        fp: str = row.get("story_fingerprint", "") or ""

        # Skip if same fingerprint already present in current batch
        if fp and fp in current_fps:
            logger.debug(
                f"[Pool] Skipping {row['event_id'][:12]} — fingerprint {fp[:8]} "
                "already covered by current batch"
            )
            continue

        # Duplicate suppression: story already published within 72h
        if fp and fp in published_fps:
            eligible, upgrade_reason = _check_upgrade_eligible(se, published_fps[fp], row)
            if not eligible:
                duplicate_suppressed_count += 1
                logger.debug(
                    f"[Pool] Suppressed {row['event_id'][:12]} (fp={fp[:8]}): "
                    "already published, no upgrade condition met"
                )
                continue
            else:
                upgraded_count += 1
                logger.info(
                    f"[Pool] Upgraded {row['event_id'][:12]} (fp={fp[:8]}): "
                    f"re-admitted despite prior publish — {upgrade_reason}"
                )

        se.story_fingerprint = fp
        se.freshness_decay = decay
        se.from_recent_pool = True
        se.pool_created_at = created_at_str

        # Back-fill null source titles from japan_view / global_view.
        # Pool snapshots stored before the title-propagation fix have title=None on
        # every SourceRef. Patching here ensures CoherenceGate sees real title text.
        _n_patched = _patch_null_source_titles_from_views(se)
        if _n_patched:
            jp_with = sum(1 for s in se.event.sources_jp if s.title)
            en_with = sum(1 for s in se.event.sources_en if s.title)
            logger.debug(
                f"[Pool] Patched {_n_patched} null titles for {se.event.id[:20]} "
                f"from views (JP titles: {jp_with}/{len(se.event.sources_jp)}, "
                f"EN titles: {en_with}/{len(se.event.sources_en)})"
            )

        pool_events.append(se)

    # Title audit after pool restore + patching
    _pool_jp_with = sum(1 for se in pool_events for s in se.event.sources_jp if s.title)
    _pool_jp_tot = sum(len(se.event.sources_jp) for se in pool_events)
    _pool_en_with = sum(1 for se in pool_events for s in se.event.sources_en if s.title)
    _pool_en_tot = sum(len(se.event.sources_en) for se in pool_events)
    logger.info(
        f"[TitleAudit] pool→restored: {len(pool_events)} pool events — "
        f"JP sources {_pool_jp_with}/{_pool_jp_tot} with title, "
        f"EN sources {_pool_en_with}/{_pool_en_tot} with title"
    )

    # Step 7: Merge + sort by effective_score (base_score adjusted by freshness)
    combined = current_ranked + pool_events
    combined.sort(
        key=lambda s: effective_score(s.score, s.freshness_decay),
        reverse=True,
    )

    stats = {
        "comparison_window_hours": window_hours,
        "max_window_hours": MAX_WINDOW_HOURS,
        "current_batch_candidates": len(current_ranked),
        "carried_over_recent_candidates": len(pool_events),
        # expired_count: freshness decay=0.0 in pool query results (edge case)
        # db_expired_count: events expired by the DB mark-expired pass
        "expired_candidate_count": expired_count + db_expired_count,
        "duplicate_suppressed_count": duplicate_suppressed_count,
        "upgraded_from_recent_pool_count": upgraded_count,
    }
    logger.info(
        f"[Pool] Combined candidate pool: current={len(current_ranked)}, "
        f"pool={len(pool_events)}, total={len(combined)}, "
        f"expired={expired_count}, suppressed={duplicate_suppressed_count}, "
        f"upgraded={upgraded_count}"
    )
    return combined, stats


def _generate_outputs(
    events,
    output_dir: Path,
    db_path: Path,
    job_id: str,
    budget: BudgetTracker,
    day_publishes: int,
    max_publishes: int,
    override_top: "ScoredEvent | None" = None,
    all_ranked: "list[ScoredEvent] | None" = None,
    authority_pair: "list[str] | None" = None,
    write_triage_scores: bool = True,
) -> JobRecord:
    """トリアージ〜生成〜保存の共通処理。

    all_ranked が渡された場合は rank_events + apply_editorial_appraisal を再実行しない。
    run_from_normalized では呼び出し元で1回だけ計算して渡すこと。

    write_triage_scores=False の場合は triage_scores.json を書き出さない。
    top-3 ループの slot-2/3 で渡すと、slot-1 が書いた選定根拠を上書きしない。
    """

    # 1. トリアージ（スコアリング & 選択）: publish スキップ時も常に実行・保存
    if all_ranked is None:
        all_ranked_raw = rank_events(events)
        all_ranked = apply_editorial_appraisal(
            all_ranked_raw, max_candidates=APPRAISAL_CANDIDATE_LIMIT
        )
    if override_top is not None:
        # Prefer the freshest-scored version from the current batch.
        # If it's not present (snapshot-restored event), use override_top as-is.
        scheduled = _find_scored_event(all_ranked, override_top.event.id)
        if scheduled is not None:
            top = scheduled
        else:
            top = override_top
            logger.info(
                f"[Scheduler] Using scheduled event (not in current batch): {override_top.event.id}"
            )
    else:
        top = all_ranked[0]
    event = top.event

    # source 別 triage 残留イベント数
    triage_source_counts: dict[str, int] = {}
    for se in all_ranked:
        for src_name in se.event.source.split(","):
            s = src_name.strip()
            if s:
                triage_source_counts[s] = triage_source_counts.get(s, 0) + 1

    # 2. スコアリング結果保存（slot-1 のみ書き出す。slot-2/3 では skip）
    if write_triage_scores:
        score_path = output_dir / "triage_scores.json"
        score_path.write_text(
            json.dumps(
                {
                    "selected": top.event.id,
                    "score": top.score,
                    "primary_tier": top.primary_tier,
                    "primary_bucket": top.primary_bucket,
                    "editorial_tags": top.editorial_tags,
                    "editorial_reason": top.editorial_reason,
                    "appraisal_type": top.appraisal_type,
                    "appraisal_hook": top.appraisal_hook,
                    "appraisal_reason": top.appraisal_reason,
                    "appraisal_cautions": top.appraisal_cautions,
                    "editorial_appraisal_score": top.editorial_appraisal_score,
                    "tags_multi": top.tags_multi,
                    "editorial_mission_score": top.editorial_mission_score,
                    "editorial_mission_breakdown": top.editorial_mission_breakdown or {},
                    "why_slot1_won_editorially": top.why_slot1_won_editorially,
                    "breakdown": top.score_breakdown,
                    "all_candidates": [
                        {
                            "rank": i + 1,
                            "id": s.event.id,
                            "title": s.event.title[:60],
                            "category": s.event.category,
                            "score": s.score,
                            "cluster_size": s.event.cluster_size,
                            "has_japan_view": s.event.japan_view is not None,
                            "has_global_view": s.event.global_view is not None,
                            "source": s.event.source,
                            "primary_tier": s.primary_tier,
                            "primary_bucket": s.primary_bucket,
                            "editorial_tags": s.editorial_tags,
                            "editorial_reason": s.editorial_reason,
                            "tags_multi": s.tags_multi,
                            "appraisal_type": s.appraisal_type,
                            "appraisal_hook": s.appraisal_hook,
                            "appraisal_reason": s.appraisal_reason,
                            "appraisal_cautions": s.appraisal_cautions,
                            "editorial_appraisal_score": s.editorial_appraisal_score,
                            # Rolling window transparency
                            "story_fingerprint": s.story_fingerprint,
                            "freshness_decay": s.freshness_decay,
                            "from_recent_pool": s.from_recent_pool,
                            "pool_created_at": s.pool_created_at,
                            # Pass C: Editorial Mission Filter
                            "editorial_mission_score": s.editorial_mission_score,
                            "editorial_mission_breakdown": s.editorial_mission_breakdown or {},
                            "why_rejected_before_generation": s.why_rejected_before_generation,
                            "why_slot1_won_editorially": s.why_slot1_won_editorially,
                            **(
                                {"triage_explanation": s.score_breakdown.get("triage_explanation", [])}
                                if i < 10 else {}
                            ),
                            "breakdown": {
                                k: v for k, v in s.score_breakdown.items()
                                if k != "triage_explanation"
                            },
                        }
                        for i, s in enumerate(all_ranked)
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    # 当日公開済み件数チェック
    if day_publishes >= max_publishes:
        logger.warning(
            f"[Budget] Daily publish limit reached ({day_publishes}/{max_publishes}). "
            "Skipping publish."
        )
        budget.skip("publish (daily limit reached)")
        record = JobRecord(
            id=job_id,
            event_id="none",
            status="skipped",
            error=f"daily publish limit reached ({day_publishes}/{max_publishes})",
        )
        save_job(db_path, record)
        record._triage_source_counts = triage_source_counts  # type: ignore[attr-defined]
        return record

    # 3. 生成フェーズ前バジェットチェック
    # F-12-A: 生成順序を逆転（article → script）。article_writer は完成記事を
    # script_writer の参考素材として渡すため先に走らせる。
    # article_writer.py 自体は touch しない（不変原則 1）。
    # script.json を article_writer に渡さない（不変原則 2）— 順序逆転後は
    # script.json はまだ存在しない。
    budget.record_phase("before_article")
    # ── Final Editor Gate: explicit budget reservation check ──────────────────
    # Verify budget before entering the expensive generation stage.
    # If insufficient, return a clean skipped record — no broken output files.
    if not budget.can_afford_generation():
        logger.warning(
            f"[FinalEditor] Budget exhausted before script generation "
            f"(run_remaining={budget.run_remaining}, day_remaining={budget.day_remaining}). "
            "Skipping generation to avoid emitting broken files."
        )
        record = JobRecord(
            id=job_id,
            event_id=event.id,
            status="skipped",
            error="final_editor_budget_insufficient",
        )
        save_job(db_path, record)
        record._triage_source_counts = triage_source_counts  # type: ignore[attr-defined]
        return record
    # ── Legacy fallback deprecation gate ──────────────────────────────────────
    # ANALYSIS_LAYER_ENABLED=true で analysis_result が None（観点不成立 or 分析失敗）
    # の場合、旧ルート（write_script）に落とすと扇動的台本（ホルムズ海峡問題）が
    # 再発するためスキップする。ANALYSIS_LAYER_ENABLED=false の場合は従来通り
    # write_script を使う（後方互換）。
    _analysis_layer_enabled = os.getenv("ANALYSIS_LAYER_ENABLED", "false").lower() == "true"
    if _analysis_layer_enabled and top.analysis_result is None:
        logger.warning(
            f"event_id={event.id}: analysis_result is None, skipping generation. "
            "Old legacy fallback route is deprecated to prevent inflammatory output."
        )
        record = JobRecord(
            id=job_id,
            event_id=event.id,
            status="skipped",
            error="analysis_layer_returned_none",
        )
        save_job(db_path, record)
        record._triage_source_counts = triage_source_counts  # type: ignore[attr-defined]
        return record

    # 4. Web記事生成（F-12-A: 台本より先に生成）
    try:
        article = write_article(event, triage_result=top, budget=budget)
    except Exception as _article_err:
        logger.error(f"event_id={event.id}: Article generation failed — {type(_article_err).__name__}: {_article_err}")
        record = JobRecord(
            id=job_id,
            event_id=event.id,
            status="failed",
            error=str(_article_err),
        )
        save_job(db_path, record)
        record._triage_source_counts = triage_source_counts  # type: ignore[attr-defined]
        return record
    article_path = output_dir / f"{event.id}_article.md"
    article_path.write_text(article.markdown, encoding="utf-8")
    logger.info(f"Article saved: {article_path}")

    # 5. 動画台本生成（F-12-A: 完成済み article.markdown を参考素材として渡す）
    budget.record_phase("before_script")
    try:
        # 分析レイヤー有効時は AnalysisResult を入力に新ルートで台本生成。
        # ANALYSIS_LAYER_ENABLED=false の場合のみ従来ルート（write_script）を使う。
        if top.analysis_result is not None:
            try:
                from src.shared.models import ChannelConfig as _ChannelConfig
                _cc = _ChannelConfig.load(top.channel_id or "geo_lens")
            except Exception as _cc_err:
                logger.warning(
                    f"[ScriptWithAnalysis] ChannelConfig load failed for "
                    f"channel_id={top.channel_id!r}: {_cc_err}; passing None."
                )
                _cc = None
            script = generate_script_with_analysis(
                top,
                top.analysis_result,
                _cc,
                budget=budget,
                authority_pair=authority_pair,
                article_text=article.markdown,
            )
        else:
            script = write_script(
                event,
                triage_result=top,
                budget=budget,
                authority_pair=authority_pair,
                article_text=article.markdown,
            )
    except Exception as _script_err:
        logger.error(f"event_id={event.id}: Script generation failed — {type(_script_err).__name__}: {_script_err}")
        record = JobRecord(
            id=job_id,
            event_id=event.id,
            status="failed",
            error=str(_script_err),
        )
        save_job(db_path, record)
        record._triage_source_counts = triage_source_counts  # type: ignore[attr-defined]
        return record
    script_path = output_dir / f"{event.id}_script.json"
    script_path.write_text(script.model_dump_json(indent=2), encoding="utf-8")
    logger.info(f"Script saved: {script_path}")

    # 6. 動画制作用JSON生成
    try:
        payload = write_video_payload(event, script, analysis_result=top.analysis_result)
        payload_path = output_dir / f"{event.id}_video_payload.json"
        payload_path.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
        logger.info(f"Video payload saved: {payload_path}")
    except Exception as _payload_err:
        logger.error(f"event_id={event.id}: Video payload generation failed — {type(_payload_err).__name__}: {_payload_err}")
        record = JobRecord(
            id=job_id,
            event_id=event.id,
            status="failed",
            error=str(_payload_err),
        )
        save_job(db_path, record)
        record._triage_source_counts = triage_source_counts  # type: ignore[attr-defined]
        return record

    # 7. 根拠ファイル保存
    try:
        write_evidence(event, top, script, article, output_dir)
    except Exception as _evidence_err:
        logger.warning(f"event_id={event.id}: Evidence saving failed (non-fatal) — {type(_evidence_err).__name__}: {_evidence_err}")

    # 8. DB保存 & 公開カウント加算
    record = JobRecord(
        id=job_id,
        event_id=event.id,
        status="completed",
        script_path=str(script_path),
        article_path=str(article_path),
        video_payload_path=str(payload_path),
    )
    save_job(db_path, record)
    increment_daily_publish_count(db_path)

    logger.info(f"=== Job completed: {job_id} ===")
    record._triage_source_counts = triage_source_counts  # type: ignore[attr-defined]
    return record


def _render_av_outputs(record: JobRecord, output_dir: Path) -> dict:
    """Render voiceover WAV + review MP4 for a completed job record.

    Requires AUDIO_RENDER_ENABLED=True.  VIDEO_RENDER_ENABLED=True additionally
    assembles the review MP4.  Both are no-ops when the respective flag is off.

    Returns an av_render_summary dict suitable for inclusion in run_summary.json
    and latest_candidate_report.md.
    """
    summary: dict = {
        "audio_render_enabled": AUDIO_RENDER_ENABLED,
        "video_render_enabled": VIDEO_RENDER_ENABLED,
        "audio_generated": False,
        "video_generated": False,
        "voiceover_path": None,
        "review_mp4_path": None,
        "render_manifest_path": None,
        "placeholder_count": 0,
        "total_duration_sec": None,
        "timing_mismatches": [],
        "error": None,
    }

    if not AUDIO_RENDER_ENABLED:
        return summary

    if not record.script_path:
        summary["error"] = "no_script_path"
        return summary

    script_path = Path(record.script_path)
    if not script_path.exists():
        summary["error"] = f"script_not_found:{script_path}"
        return summary

    try:
        from src.shared.models import VideoScript
        script = VideoScript.model_validate_json(script_path.read_text(encoding="utf-8"))
    except Exception as e:
        summary["error"] = f"script_parse_error:{e}"
        return summary

    try:
        from src.generation.audio_renderer import render_voiceover
        wav_path, audio_segments, audio_manifest = render_voiceover(
            script, output_dir,
            voice=TTS_VOICE,
            framerate=TTS_FRAMERATE,
            tts_timeout=TTS_TIMEOUT_SEC,
        )
        summary["audio_generated"] = True
        summary["voiceover_path"] = str(wav_path)
        summary["placeholder_count"] = audio_manifest.get("placeholder_count", 0)
        summary["total_duration_sec"] = audio_manifest.get("total_duration_sec")
        summary["timing_mismatches"] = audio_manifest.get("timing_mismatches", [])
        record.voiceover_path = str(wav_path)
        logger.info(
            f"[AV] Voiceover rendered: {wav_path} "
            f"({summary['total_duration_sec']:.1f}s, "
            f"placeholders={summary['placeholder_count']})"
        )
    except Exception as e:
        logger.warning(f"[AV] Audio render failed: {e}")
        summary["error"] = f"audio_render_error:{e}"
        return summary

    # 全 segment が silent placeholder だった場合は TTS が機能していない環境。
    # MP4 組み立てに進むと「無音動画」が成功扱いで保存されてしまうため、
    # ここで明示的にエラーフラグを立て、video_generated=False のまま返す。
    # （audio_segments が空 = そもそも生成スクリプトが空 の場合は別バグなので除外）
    _seg_total = len(audio_segments) if audio_segments else 0
    _ph = summary.get("placeholder_count", 0) or 0
    if _seg_total > 0 and _ph >= _seg_total:
        logger.error(
            f"[AV] All {_seg_total} segment(s) are silent placeholders — "
            "TTS is unavailable (macOS `say` not found or failing). "
            "Aborting MP4 assembly to avoid emitting a silent video."
        )
        summary["error"] = (
            f"tts_unavailable_all_silent:{_ph}/{_seg_total}_segments_were_placeholder"
        )
        return summary

    if not VIDEO_RENDER_ENABLED:
        return summary

    if not record.video_payload_path:
        summary["error"] = "no_video_payload_path"
        return summary

    payload_path = Path(record.video_payload_path)
    if not payload_path.exists():
        summary["error"] = f"payload_not_found:{payload_path}"
        return summary

    try:
        from src.shared.models import VideoPayload
        payload = VideoPayload.model_validate_json(payload_path.read_text(encoding="utf-8"))
    except Exception as e:
        summary["error"] = f"payload_parse_error:{e}"
        return summary

    try:
        from src.generation.video_renderer import render_video
        mp4_path, render_manifest = render_video(
            payload, audio_segments, output_dir,
            fps=VIDEO_FPS,
            width=VIDEO_WIDTH,
            height=VIDEO_HEIGHT,
        )
        summary["video_generated"] = True
        summary["review_mp4_path"] = str(mp4_path)
        manifest_path = output_dir / f"{record.event_id}_render_manifest.json"
        summary["render_manifest_path"] = str(manifest_path)
        record.review_mp4_path = str(mp4_path)
        logger.info(f"[AV] Review MP4 rendered: {mp4_path}")
    except Exception as e:
        logger.warning(f"[AV] Video render failed: {e}")
        summary["error"] = f"video_render_error:{e}"

    return summary


def _make_budget(
    db_path: Path,
    run_mode: str | None = None,
) -> tuple[BudgetTracker, dict]:
    stats = get_daily_stats(db_path)
    mode = run_mode if run_mode is not None else RUN_MODE
    budget = BudgetTracker(
        run_budget=LLM_CALL_BUDGET_PER_RUN,
        day_budget=LLM_CALL_BUDGET_PER_DAY,
        day_calls_so_far=stats["llm_calls"],
        db_path=db_path,
        mode=mode,
        publish_reserve_calls=PUBLISH_RESERVE_CALLS,
    )
    logger.info(
        f"[Budget] Initialized: mode={mode}, "
        f"run_budget={LLM_CALL_BUDGET_PER_RUN}, "
        f"day_budget={LLM_CALL_BUDGET_PER_DAY}, "
        f"day_calls_so_far={stats['llm_calls']}, "
        f"day_remaining={budget.day_remaining}, "
        f"publish_reserve_calls={PUBLISH_RESERVE_CALLS}"
    )
    return budget, stats


def run(
    input_path: Path,
    output_dir: Path,
    db_path: Path,
    run_mode: str | None = None,
) -> JobRecord:
    """サンプルイベントモード: JSON ファイルから NewsEvent を読み込んで処理する。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    init_db(db_path)

    job_id = str(uuid.uuid4())
    logger.info(f"=== Job started (sample mode): {job_id} ===")

    budget, stats = _make_budget(db_path, run_mode=run_mode)
    increment_daily_run_count(db_path)
    stats_after = get_daily_stats(db_path)

    events = load_events(input_path)
    record = _generate_outputs(
        events, output_dir, db_path, job_id,
        budget=budget,
        day_publishes=stats["publish_count"],
        max_publishes=MAX_PUBLISHES_PER_DAY,
    )

    _av_summary: dict | None = None
    if record.status == "completed":
        _av_summary = _render_av_outputs(record, output_dir)
        if _av_summary.get("audio_generated") or _av_summary.get("error"):
            save_job(db_path, record)

    budget.log_summary(
        day_runs=stats_after["run_count"],
        day_publishes=stats_after["publish_count"] + (1 if record.status == "completed" else 0),
    )
    return record


def run_from_normalized(
    normalized_dir: Path,
    output_dir: Path,
    db_path: Path,
    min_shared_keywords: int = 1,
    min_cluster_size: int = 1,
    archive_dir: Path | None = None,
    run_mode: str | None = None,
) -> JobRecord:
    """実ニュースモード: Batch-based Success Archive。

    1. DB から最古の pending/failed batch を取得
    2. その batch の normalized ファイルのみを処理
    3. job 成功後に batch ごと archive へ移動
    4. 新着 batch がない場合は no-op で正常終了
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    init_db(db_path)

    if archive_dir is None:
        archive_dir = ARCHIVE_DIR

    job_id = str(uuid.uuid4())
    logger.info(f"=== Job started (normalized/batch mode): {job_id} ===")

    # 当日統計読み込み & 実行カウント加算
    budget, stats = _make_budget(db_path, run_mode=run_mode)
    increment_daily_run_count(db_path)
    stats_after = get_daily_stats(db_path)

    # ── 未処理 batch を取得 ──────────────────────────────────────────────────
    batch = get_oldest_pending_batch(db_path)

    if batch is None:
        logger.info("[Batch] No pending batch found — no-op, exiting normally.")
        record = JobRecord(
            id=job_id,
            event_id="none",
            status="skipped",
            error="no pending batch",
        )
        save_job(db_path, record)
        batch_info = {
            "batch_id": None,
            "reason": "no_pending_batch",
            "batch_raw_count": 0,
            "batch_normalized_count": 0,
            "total_articles_loaded": 0,
            "schedule_action": "none",
            "archived_file_count": 0,
        }
        budget.log_summary(
            day_runs=stats_after["run_count"],
            day_publishes=stats_after["publish_count"],
        )
        _save_run_summary(
            output_dir, job_id, {}, record, budget, batch_info=batch_info
        )
        return record

    batch_id: str = batch["batch_id"]
    normalized_files: list[str] = batch["normalized_files"]
    logger.info(
        f"[Batch] Processing batch_id={batch_id} "
        f"({len(batch['raw_files'])} raw, {len(normalized_files)} normalized)"
    )

    # batch を processing に移行（失敗時も状態が分かるよう）
    mark_batch_status(
        db_path, batch_id, "processing",
        processed_at=datetime.now(timezone.utc).isoformat(),
    )

    batch_info: dict = {
        "batch_id": batch_id,
        "batch_raw_count": len(batch["raw_files"]),
        "batch_normalized_count": len(normalized_files),
        "total_articles_loaded": 0,
        "schedule_action": "unknown",
        "archived_file_count": 0,
    }
    rolling_window_stats: dict = {
        "comparison_window_hours": DEFAULT_WINDOW_HOURS,
        "max_window_hours": MAX_WINDOW_HOURS,
        "current_batch_candidates": 0,
        "carried_over_recent_candidates": 0,
        "expired_candidate_count": 0,
        "duplicate_suppressed_count": 0,
        "upgraded_from_recent_pool_count": 0,
    }

    try:
        # ── DB seen_urls で重複排除 (他 batch の既処理 URL のみ) ─────────────
        # 自分自身の batch の URL は除外しない（それが今回処理すべき記事）
        seen_urls = get_seen_urls_excluding_batch(db_path, batch_id)

        # ── cluster post-merge LLM 使用可否 ─────────────────────────────────
        allow_cluster_merge = budget.can_use_cluster_merge()
        if not allow_cluster_merge:
            budget.skip("cluster_post_merge (budget before run)")
            cluster_llm = None
        else:
            cluster_llm = get_cluster_llm_client()

        # ── Gate 1 クライアント (Tier 2 Lite) ────────────────────────────────
        _garbage_filter_client = get_garbage_filter_client() if GARBAGE_FILTER_ENABLED else None
        if GARBAGE_FILTER_ENABLED and _garbage_filter_client is None:
            logger.warning("[GarbageFilter] GARBAGE_FILTER_ENABLED=true だが API キー未設定のためスキップ")

        run_stats: dict = {}
        _editorial_mission_summary: dict = {"editorial_mission_filter_applied": False}
        events = build_events_from_normalized(
            normalized_dir=normalized_dir,
            min_shared_keywords=min_shared_keywords,
            min_cluster_size=min_cluster_size,
            llm_client=cluster_llm,
            budget=budget if allow_cluster_merge else None,
            run_stats=run_stats,
            normalized_files=normalized_files,
            already_seen_urls=seen_urls,
            garbage_filter_client=_garbage_filter_client,
        )

        batch_info["total_articles_loaded"] = run_stats.get("total_article_count", 0)

        if not events:
            logger.info(
                f"[Batch] batch_id={batch_id}: No events built "
                "(all articles may be duplicates or empty). "
                "Marking batch completed and no-op."
            )
            mark_batch_status(db_path, batch_id, "completed")
            record = JobRecord(
                id=job_id,
                event_id="none",
                status="skipped",
                error=f"no events from batch {batch_id}",
            )
            save_job(db_path, record)
            batch_info["schedule_action"] = "noop_no_events"
            _write_debug_artifacts(output_dir, run_stats, None, rolling_window_stats)
            _save_run_summary(
                output_dir, job_id, run_stats, record, budget,
                batch_info=batch_info,
            )
            budget.log_summary(
                day_runs=stats_after["run_count"],
                day_publishes=stats_after["publish_count"],
            )
            return record

        # ── Stage A+B: Rank + Appraisal（run あたり1回のみ）────────────────
        all_ranked_raw = rank_events(events)
        all_ranked_appraised = apply_editorial_appraisal(
            all_ranked_raw, max_candidates=APPRAISAL_CANDIDATE_LIMIT
        )
        logger.info(
            f"[Appraisal] Applied once for this run: top {APPRAISAL_CANDIDATE_LIMIT} appraised "
            f"(total candidates={len(all_ranked_appraised)})"
        )

        # ── Stage C: Rolling Comparison Window ───────────────────────────────
        # 1. Assign fingerprints to current-batch events
        for se in all_ranked_appraised:
            se.story_fingerprint = compute_story_fingerprint(se.event)
            se.freshness_decay = 1.0
            se.from_recent_pool = False

        # 2. Persist current-batch events into the pool (for future runs)
        _save_events_to_pool(db_path, all_ranked_appraised, batch_id)

        # 3. Build combined candidate pool (current + recent unpublished from pool)
        all_ranked, rolling_window_stats = _build_combined_candidate_pool(
            db_path, all_ranked_appraised, batch_id, window_hours=DEFAULT_WINDOW_HOURS
        )

        batch_info["rolling_window"] = rolling_window_stats

        # ── Stage C2: Editorial Mission Filter (Pass C) ──────────────────────
        # Scores all candidates on Hydrangea editorial mission fit (0-100, 7 axes).
        # Step 1: deterministic prescore using editorial axes (free, always runs).
        # Step 2: optional LLM scoring for top MISSION_PRESCORE_TOP_N candidates.
        # Candidates below MISSION_SCORE_THRESHOLD get why_rejected_before_generation set.
        _editorial_mission_summary: dict = {"editorial_mission_filter_applied": False}
        if EDITORIAL_MISSION_FILTER_ENABLED:
            _mission_llm_client = get_judge_llm_client() if MISSION_LLM_ENABLED else None
            all_ranked, _editorial_mission_summary = apply_editorial_mission_filter(
                all_ranked,
                budget,
                llm_client=_mission_llm_client,
                prescore_top_n=MISSION_PRESCORE_TOP_N,
                score_threshold=MISSION_SCORE_THRESHOLD,
                llm_enabled=MISSION_LLM_ENABLED,
            )
            logger.info(
                f"[EditorialMissionFilter] Applied: "
                f"passed={_editorial_mission_summary.get('passed_threshold', 0)}/"
                f"{_editorial_mission_summary.get('total_candidates', 0)}, "
                f"rejected={_editorial_mission_summary.get('rejected_before_generation', 0)}, "
                f"llm_scored={_editorial_mission_summary.get('llm_scored_count', 0)}"
            )

        # ── Gate 3: Elite Judge（編集長・一点突破判定）──────────────────────────
        # evaluate_cluster_buzz (TIER1: gemini-3.1-flash-lite-preview) で最終採用判定。
        # is_adopted=False のクラスタは即座に破棄し、台本生成には絶対進行させない。
        # TIER1 (RPD 500) に余裕があるため全マージ済みクラスタに適用する。
        _elite_judge_results: dict[str, EditorScore] = {}
        if ELITE_JUDGE_ENABLED and GEMINI_API_KEY:
            _elite_judge_client = get_judge_llm_client()
            if _elite_judge_client is not None:
                _elite_adopted: list[ScoredEvent] = []
                # EditorialMissionFilter で却下された候補を除外。
                # apply_editorial_mission_filter() は why_rejected_before_generation をセットするだけで
                # all_ranked から除外しない設計。Elite Judge には通過候補のみを流す必要がある。
                _passed_candidates = [
                    se for se in all_ranked
                    if not se.why_rejected_before_generation
                ]
                logger.info(
                    f"[EliteJudge] Filtered all_ranked: {len(all_ranked)} → {len(_passed_candidates)} "
                    f"(removed {len(all_ranked) - len(_passed_candidates)} rejected by EditorialMissionFilter)"
                )

                # ELITE_JUDGE_CANDIDATE_LIMIT 件に絞る。_passed_candidates は Editorial Mission Filter 通過後の
                # effective_score 降順なので、上位から LIMIT 件を Elite Judge にかける。
                # 残りは elite_judge 未評価のまま除外（= 棄却扱い）する。
                _elite_candidates = _passed_candidates[:ELITE_JUDGE_CANDIDATE_LIMIT]
                if len(_passed_candidates) > ELITE_JUDGE_CANDIDATE_LIMIT:
                    logger.info(
                        f"[EliteJudge] Capping candidates to top {ELITE_JUDGE_CANDIDATE_LIMIT} "
                        f"of {len(_passed_candidates)} (ELITE_JUDGE_CANDIDATE_LIMIT)"
                    )

                for _se in _elite_candidates:
                    if not budget.can_afford_elite_judge():
                        logger.warning(
                            "[EliteJudge] 予算上限に達しました。残候補を破棄し処理を安全停止します。"
                        )
                        break

                    # Elite Judge のプロンプトは「グローバルサウス/中東/東南アジア等」の
                    # 非欧米視点を高く評価する。sources_en だけを渡すと
                    # sources_by_locale = {japan, middle_east, global_south, ...}
                    # 形式のイベントで多地域ソース名が Elite Judge に届かず、
                    # "multipolar" / "outside_in" 軸のスコアが不当に低く出る。
                    # sources_by_locale がある場合はそれを優先し、後方互換で
                    # sources_jp + sources_en にフォールバックする。
                    if _se.event.sources_by_locale:
                        _src_names: list[str] = []
                        _seen: set[str] = set()
                        for _loc, _refs in _se.event.sources_by_locale.items():
                            for _ref in _refs:
                                if _ref.name and _ref.name not in _seen:
                                    _src_names.append(_ref.name)
                                    _seen.add(_ref.name)
                    else:
                        _src_names = [
                            s.name for s in (_se.event.sources_jp + _se.event.sources_en)
                        ]
                    _cluster_data = {
                        "title": _se.event.title,
                        "summary": _se.event.summary,
                        "sources": _src_names,
                    }
                    try:
                        _editor_score = evaluate_cluster_buzz(_cluster_data)
                        budget.record_call("elite_judge")
                        _elite_judge_results[_se.event.id] = _editor_score

                        if _editor_score.is_adopted:
                            _axis_map = {
                                "アンチ忖度": _editor_score.score_anti_sontaku,
                                "多極的視点": _editor_score.score_multipolar,
                                "アウトサイド・イン": _editor_score.score_outside_in,
                                "知的優越感": _editor_score.score_insight,
                                "ファンダム最速": _editor_score.score_fandom_fast,
                            }
                            _top_axis = max(_axis_map, key=lambda k: _axis_map[k])
                            _top_score = _axis_map[_top_axis]
                            logger.info(
                                f"[EliteJudge] ✦ Adopted: 一点突破 "
                                f"({_top_axis}: {_top_score}点) / "
                                f"Total: {_editor_score.total_score}点 "
                                f"— {_se.event.title[:50]}"
                            )
                            _elite_adopted.append(_se)
                        else:
                            logger.info(
                                f"[EliteJudge] ✗ Skipped: 基準未達 "
                                f"(Total: {_editor_score.total_score}点) "
                                f"— {_se.event.title[:50]}"
                            )
                    except Exception as _exc:
                        logger.warning(
                            f"[EliteJudge] {_se.event.id} 評価エラー: {_exc}. 通過させます。"
                        )
                        _elite_adopted.append(_se)

                _before_elite = len(all_ranked)
                all_ranked = _elite_adopted
                logger.info(
                    f"[EliteJudge] Gate 3 完了: "
                    f"{len(_elite_candidates)}件評価 → "
                    f"採用 {len(_elite_adopted)} / 棄却 {len(_elite_candidates) - len(_elite_adopted)} "
                    f"(total ranked: {_before_elite} → {len(all_ranked)})"
                )

        # ── Stage D: Gemini 編集審判パス（evidence-grounded judge）──────────────
        # appraisal 済み候補の上位 JUDGE_CANDIDATE_LIMIT 件を Gemini で評価し、
        # judge スコアを reranking ブーストとして適用する。
        # ジャッジは常にオプション。API キー未設定・予算不足の場合はスキップ。
        judge_results, _judge_model_resolution = _run_judge_pass(all_ranked, budget)
        if judge_results:
            all_ranked = _apply_judge_reranking(all_ranked)

        # ── Slot-1 Selection: Elite Judge 直結モード ─────────────────────────────
        # Scheduler 廃止。Elite Judge (Gate 3) で is_adopted=True の候補のみが対象。
        # total_score 最高値を Slot-1 に直接選出。採用0件の場合はフォールバックせず終了。
        override_top: ScoredEvent | None = None
        schedule_action = "elite_judge_direct"
        replaced_slots: list[str] = []
        scheduled_event_id: str | None = None
        schedule_snapshot_used = False
        schedule_mismatch_resolved = False

        if not all_ranked:
            logger.warning(
                "[EliteJudge] Elite Judge に採用されたニュースが0件。"
                "フォールバックは禁止されているため、本日の採用ニュースなしとして終了します。"
            )
            _skip_record = JobRecord(
                id=job_id,
                event_id="none",
                status="skipped",
                error="no_elite_adopted: Elite Judge の採用候補が0件（予算切れ含む）",
            )
            save_job(db_path, _skip_record)
            _dummy_schedule = DailySchedule(
                date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                generated_at=datetime.now(timezone.utc).isoformat(),
                total_candidates=0,
                selected=[],
                rejected=[],
                held_back=[],
                open_slots=1,
                diversity_rules_applied=["elite_judge_direct"],
                coverage_summary={},
                region_coverage={},
            )
            batch_info["schedule_action"] = "skipped_no_elite_adopted"
            archived_count = 0
            try:
                archived_count = _archive_batch(batch, archive_dir)
                mark_batch_status(
                    db_path, batch_id, "archived",
                    archived_at=datetime.now(timezone.utc).isoformat(),
                )
                logger.info(
                    f"[Archive] batch={batch_id} archived "
                    f"(no_elite_adopted, {archived_count} files)"
                )
            except Exception as arc_err:
                logger.error(
                    f"[Archive] Failed to archive batch={batch_id}: {arc_err}. "
                    "Batch will remain as 'processing' for manual cleanup."
                )
            batch_info["archived_file_count"] = archived_count
            _write_debug_artifacts(output_dir, run_stats, _dummy_schedule, rolling_window_stats)
            _write_discovery_audit_safe(all_ranked_appraised, run_stats, output_dir, _dummy_schedule)
            _save_run_summary(
                output_dir, job_id, run_stats, _skip_record, budget,
                daily_schedule=_dummy_schedule,
                batch_info=batch_info,
                schedule_tracking={
                    "scheduled_event_id": None,
                    "schedule_snapshot_used": False,
                    "schedule_mismatch_resolved": False,
                    "no_publishable_candidates": True,
                    "all_selected_published": False,
                    "fallback_blocked_by_quality_floor": False,
                },
                rolling_window_stats=rolling_window_stats,
                judge_summary=_build_judge_summary(judge_results, [], None, [], model_resolution=_judge_model_resolution),
                editorial_mission_summary=_editorial_mission_summary,
            )
            budget.log_summary(
                day_runs=stats_after["run_count"],
                day_publishes=stats_after["publish_count"],
            )
            return _skip_record

        # Elite Judge 採用候補の中から total_score 最高を Slot-1 に選出
        override_top = max(
            all_ranked,
            key=lambda se: (
                _elite_judge_results[se.event.id].total_score
                if se.event.id in _elite_judge_results else 0
            ),
        )
        scheduled_event_id = override_top.event.id
        _top_ej = _elite_judge_results.get(override_top.event.id)
        logger.info(
            f"[EliteJudge→Slot1] Slot-1 決定 "
            f"(total_score={_top_ej.total_score if _top_ej else 'N/A'}): "
            f"{override_top.event.title[:60]}"
        )
        schedule = DailySchedule(
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_candidates=len(all_ranked),
            selected=[scored_event_to_schedule_entry(override_top, 1)],
            rejected=[],
            held_back=[],
            open_slots=0,
            diversity_rules_applied=["elite_judge_direct"],
            coverage_summary={"elite_judge": 1},
            region_coverage={},
        )
        batch_info["schedule_action"] = schedule_action

        # ── Final Selection Stage: slot-1 integrity enforcement ─────────────────
        # Judge が評価した場合、slot-1 は judged flagship 候補から選ばなければならない。
        # not_judged や弱い EN-only 候補が scheduler によって選ばれていても、
        # eligible な judged 候補が存在すれば差し替える。
        # eligible な judged 候補が存在しない（かつ judge が実行された）場合は generation をブロック。
        _scheduled_slot1_id: str | None = (
            override_top.event.id if override_top is not None
            else (all_ranked[0].event.id if all_ranked else None)
        )
        _reranked_top_id: str | None = all_ranked[0].event.id if all_ranked else None
        _final_selected_slot1_id: str | None = None
        _slot1_selection_source: str = "scheduler_no_judge"
        _slot1_block_reason: str | None = None
        _final_selection_fallback_used: bool = False
        _final_selection_fallback_reason: str | None = None
        _quota_fallback_candidate_id: str | None = None
        _quota_fallback_candidate_title: str | None = None

        if judge_results:
            _eligible_se, _sel_reason = _find_eligible_judged_slot1(all_ranked, judge_results)
            if _eligible_se is not None:
                _old_id = override_top.event.id if override_top else None
                if _old_id != _eligible_se.event.id:
                    logger.info(
                        f"[FinalSelection] slot-1 corrected by judge: "
                        f"{_old_id} → {_eligible_se.event.id} "
                        f"({_sel_reason})"
                    )
                override_top = _eligible_se
                _final_selected_slot1_id = _eligible_se.event.id
                _slot1_selection_source = _sel_reason
            else:
                # No eligible judged flagship — try quota-aware fallback before hard-blocking.
                # If all judge failures were quota/unavailable, a strong pre-judge candidate
                # with JP + overseas + cross-lang evidence may proceed conservatively.
                _fallback_se, _fallback_reason = _find_quota_fallback_slot1(
                    all_ranked, judge_results
                )
                if _fallback_se is not None:
                    logger.info(
                        f"[FinalSelection] Quota fallback activated: "
                        f"{_fallback_se.event.id} "
                        f"(appraisal={_fallback_se.appraisal_type}, "
                        f"score={_fallback_se.score:.1f}, "
                        f"reason={_fallback_reason})"
                    )
                    override_top = _fallback_se
                    _final_selected_slot1_id = _fallback_se.event.id
                    _slot1_selection_source = "quota_fallback_prejudge"
                    _final_selection_fallback_used = True
                    _final_selection_fallback_reason = _fallback_reason
                    _quota_fallback_candidate_id = _fallback_se.event.id
                    _quota_fallback_candidate_title = _fallback_se.event.title
                else:
                    # Hard block: no eligible judged flagship AND no safe quota fallback
                    _quota_errors = sum(
                        1 for jr in judge_results.values()
                        if jr.judge_error_type in _QUOTA_FALLBACK_ERROR_TYPES
                    )
                    if _quota_errors > 0:
                        _slot1_block_reason = (
                            f"quota_exhausted_no_safe_fallback_candidate"
                            f"(quota_errors={_quota_errors},{_fallback_reason})"
                        )
                    else:
                        _slot1_block_reason = "no_eligible_judged_flagship_when_judge_ran"
                    logger.warning(
                        f"[FinalSelection] Blocking generation: judge ran "
                        f"(judged_count={len(judge_results)}) but no eligible judged flagship "
                        f"and no safe quota fallback. reason={_slot1_block_reason}"
                    )
                    _fs_block_record = JobRecord(
                        id=job_id,
                        event_id="none",
                        status="skipped",
                        error=f"final_selection_blocked:{_slot1_block_reason}",
                    )
                    save_job(db_path, _fs_block_record)
                    batch_info["schedule_action"] = "skipped_final_selection_blocked"
                    _archived_count = 0
                    try:
                        _archived_count = _archive_batch(batch, archive_dir)
                        mark_batch_status(
                            db_path, batch_id, "archived",
                            archived_at=datetime.now(timezone.utc).isoformat(),
                        )
                    except Exception as _arc_err:
                        logger.error(f"[Archive] Failed to archive batch={batch_id}: {_arc_err}")
                    batch_info["archived_file_count"] = _archived_count
                    _fs_tracking = {
                        "scheduled_event_id": scheduled_event_id,
                        "schedule_snapshot_used": schedule_snapshot_used,
                        "schedule_mismatch_resolved": schedule_mismatch_resolved,
                        "no_publishable_candidates": False,
                        "all_selected_published": False,
                        "fallback_blocked_by_quality_floor": False,
                        "scheduled_slot1_id": _scheduled_slot1_id,
                        "reranked_top_id": _reranked_top_id,
                        "final_selected_slot1_id": None,
                        "slot1_selection_source": "blocked",
                        "slot1_is_judged": False,
                        "slot1_publishability_class": None,
                        "slot1_jp_source_count": None,
                        "slot1_en_source_count": None,
                        "slot1_block_reason": _slot1_block_reason,
                    }
                    _write_debug_artifacts(output_dir, run_stats, schedule, rolling_window_stats)
                    _write_discovery_audit_safe(all_ranked_appraised, run_stats, output_dir, schedule)
                    _write_latest_candidate_report(
                        output_dir,
                        scheduled_slot1_id=_scheduled_slot1_id,
                        reranked_top_id=_reranked_top_id,
                        final_selected_slot1_id=None,
                        slot1_selection_source="blocked",
                        slot1_block_reason=_slot1_block_reason,
                        all_ranked=all_ranked,
                        judge_results=judge_results,
                        model_resolution=_judge_model_resolution,
                        budget_mode_summary=budget.to_publish_mode_summary(),
                    )
                    _save_run_summary(
                        output_dir, job_id, run_stats, _fs_block_record, budget,
                        daily_schedule=schedule,
                        batch_info=batch_info,
                        schedule_tracking=_fs_tracking,
                        rolling_window_stats=rolling_window_stats,
                        judge_summary=_build_judge_summary(
                            judge_results, all_ranked, None, [],
                            model_resolution=_judge_model_resolution,
                        ),
                        editorial_mission_summary=_editorial_mission_summary,
                    )
                    budget.log_summary(
                        day_runs=stats_after["run_count"],
                        day_publishes=stats_after["publish_count"],
                    )
                    return _fs_block_record
        else:
            # Judge did not run — use scheduler's choice unchanged
            _final_selected_slot1_id = _scheduled_slot1_id
            _slot1_selection_source = "scheduler_no_judge"

        # Build slot-1 audit fields (used in all downstream schedule_tracking dicts)
        def _slot1_audit(candidate: "ScoredEvent | None") -> dict:
            if candidate is None:
                return {
                    "scheduled_slot1_id": _scheduled_slot1_id,
                    "reranked_top_id": _reranked_top_id,
                    "final_selected_slot1_id": _final_selected_slot1_id,
                    "slot1_selection_source": _slot1_selection_source,
                    "slot1_is_judged": False,
                    "slot1_publishability_class": None,
                    "slot1_jp_source_count": None,
                    "slot1_en_source_count": None,
                    "slot1_block_reason": _slot1_block_reason,
                    "slot1_source_titles_present_jp": None,
                    "slot1_source_titles_present_en": None,
                    "slot1_coherence_input_quality": None,
                    "slot1_overlap_signals": None,
                    "slot1_semantic_coherence_score": None,
                    "slot1_coherence_gate_passed": None,
                }
            jr = candidate.judge_result
            _is_judged = jr is not None and jr.judge_error is None
            if _final_selection_fallback_used and jr is None:
                _pub_class = "quota_fallback_prejudge"
            elif jr and jr.judge_error is None:
                _pub_class = jr.publishability_class
            else:
                _pub_class = "not_judged"
            return {
                "scheduled_slot1_id": _scheduled_slot1_id,
                "reranked_top_id": _reranked_top_id,
                "final_selected_slot1_id": _final_selected_slot1_id,
                "slot1_selection_source": _slot1_selection_source,
                "slot1_is_judged": _is_judged,
                "slot1_publishability_class": _pub_class,
                "slot1_jp_source_count": len(candidate.event.sources_jp),
                "slot1_en_source_count": len(candidate.event.sources_en),
                "slot1_block_reason": _slot1_block_reason,
                "slot1_source_titles_present_jp": sum(
                    1 for s in candidate.event.sources_jp if s.title
                ),
                "slot1_source_titles_present_en": sum(
                    1 for s in candidate.event.sources_en if s.title
                ),
                "slot1_coherence_input_quality": candidate.coherence_input_quality or None,
                "slot1_overlap_signals": candidate.coherence_overlap_signals or None,
                "slot1_semantic_coherence_score": candidate.semantic_coherence_score,
                "slot1_coherence_gate_passed": candidate.coherence_gate_passed,
            }

        # ── Flagship Gate: auto-generation のみ flagship 水準に達した候補に限定 ──
        # 番組表スケジューリングとは独立。生成直前の最終ゲート。
        _rescue_triggered = False
        authority_pair: list[str] = []
        _candidate_to_generate = override_top if override_top is not None else (
            all_ranked[0] if all_ranked else None
        )
        if _candidate_to_generate is not None:
            _fg_passes, _fg_reason = _passes_flagship_gate(_candidate_to_generate)
            if not _fg_passes:
                logger.warning(
                    f"[FlagshipGate] Blocked auto-generation: "
                    f"'{_candidate_to_generate.event.title[:50]}' "
                    f"(reason={_fg_reason}, score={_candidate_to_generate.score:.1f}, "
                    f"bucket={_candidate_to_generate.primary_bucket})"
                )
                _fg_skip = JobRecord(
                    id=job_id,
                    event_id="none",
                    status="skipped",
                    error=f"flagship_gate_blocked:{_fg_reason}",
                )
                archived_count = 0
                try:
                    archived_count = _archive_batch(batch, archive_dir)
                    mark_batch_status(
                        db_path, batch_id, "archived",
                        archived_at=datetime.now(timezone.utc).isoformat(),
                    )
                except Exception as arc_err:
                    logger.error(f"[Archive] Failed to archive batch={batch_id}: {arc_err}")
                batch_info["archived_file_count"] = archived_count
                _write_debug_artifacts(output_dir, run_stats, schedule, rolling_window_stats)
                _write_discovery_audit_safe(all_ranked_appraised, run_stats, output_dir, schedule)
                _write_latest_candidate_report(
                    output_dir,
                    scheduled_slot1_id=_scheduled_slot1_id,
                    reranked_top_id=_reranked_top_id,
                    final_selected_slot1_id=_final_selected_slot1_id,
                    slot1_selection_source=_slot1_selection_source,
                    slot1_block_reason=f"flagship_gate_blocked:{_fg_reason}",
                    all_ranked=all_ranked,
                    judge_results=judge_results,
                    model_resolution=_judge_model_resolution,
                    budget_mode_summary=budget.to_publish_mode_summary(),
                )
                _save_run_summary(
                    output_dir, job_id, run_stats, _fg_skip, budget,
                    daily_schedule=schedule,
                    batch_info=batch_info,
                    schedule_tracking={
                        "scheduled_event_id": scheduled_event_id,
                        "schedule_snapshot_used": schedule_snapshot_used,
                        "schedule_mismatch_resolved": schedule_mismatch_resolved,
                        "no_publishable_candidates": False,
                        "all_selected_published": False,
                        "fallback_blocked_by_quality_floor": False,
                        "flagship_gate_blocked": True,
                        "flagship_gate_reason": _fg_reason,
                        **_slot1_audit(_candidate_to_generate),
                    },
                    rolling_window_stats=rolling_window_stats,
                    judge_summary=_build_judge_summary(
                        judge_results, all_ranked, _candidate_to_generate, [],
                        model_resolution=_judge_model_resolution,
                    ),
                    editorial_mission_summary=_editorial_mission_summary,
                )
                budget.log_summary(
                    day_runs=stats_after["run_count"],
                    day_publishes=stats_after["publish_count"],
                )
                return _fg_skip

        # ── 分析レイヤー（ANALYSIS_LAYER_ENABLED=true 時のみ） ──────────────────
        # 設計書 Section 4.2 のフロー: Recency Guard → 観点抽出 → LLM 観点選定/検証
        # → 多角的分析 → 洞察抽出 → 動画尺プロファイル選定。
        # 失敗時は analysis_result=None のまま既存ルートにフォールバックする。
        # ANALYSIS_LAYER_ENABLED=false 時はこのブロックを丸ごとスキップし、
        # 従来の Top-3 ループ挙動を完全に維持する。
        _analysis_channel_id: str | None = None
        if os.getenv("ANALYSIS_LAYER_ENABLED", "false").lower() == "true":
            try:
                from src.analysis.analysis_engine import (
                    run_analysis_layer,
                    save_analysis_json,
                )
                from src.analysis.recency_guard import apply_recency_guard
                from src.shared.models import ChannelConfig as _ChannelConfig

                _analysis_channel_id = os.getenv("DEFAULT_CHANNEL_ID", "geo_lens")
                _channel_config = _ChannelConfig.load(_analysis_channel_id)

                # Recency Guard: 直近 24h 内の重複 entity/topic を持つ候補を降格。
                all_ranked = apply_recency_guard(
                    all_ranked, _analysis_channel_id, db_path
                )

                # Recency Guard 後のスコア順で slot-1 を再決定。
                if all_ranked:
                    _new_slot1 = all_ranked[0]
                    _prev_slot1_id = override_top.event.id if override_top else None
                    if _prev_slot1_id and _prev_slot1_id != _new_slot1.event.id:
                        logger.info(
                            f"[AnalysisLayer] Recency Guard reordered slot-1: "
                            f"{_prev_slot1_id} → {_new_slot1.event.id}"
                        )
                    override_top = _new_slot1

                    # ── F-4: AnalysisLayer を Top-N 全 Slot で実行 ──────────────
                    # 旧実装は all_ranked[0] (= slot-1) のみで run_analysis_layer
                    # を呼び、Slot-2 / Slot-3 の analysis_result は None のまま
                    # 後続の台本生成ループで skip されていた。試運転7-A で
                    # 「3 本中 1 本しか動画化できない」問題が発覚。
                    # F-4 では TOP_N_GENERATION (default 3) で指定された全候補で
                    # AnalysisLayer を実行する。1 Slot の失敗は当該 Slot に閉じ込め、
                    # 他 Slot は処理を継続する (per-slot try/except)。
                    _top_n_for_analysis = max(
                        1, int(os.getenv("TOP_N_GENERATION", "3"))
                    )
                    _analysis_targets = all_ranked[:_top_n_for_analysis]

                    logger.info(
                        f"[AnalysisLayer] Running for top {len(_analysis_targets)} "
                        f"candidates (F-4: extended from slot-1 only)"
                    )

                    for _idx, _target in enumerate(_analysis_targets):
                        try:
                            _target.channel_id = _analysis_channel_id
                            _analysis_result = run_analysis_layer(
                                _target, _channel_config, db_path
                            )
                            if _analysis_result is not None:
                                _target.analysis_result = _analysis_result
                                save_analysis_json(_analysis_result, output_dir)
                                logger.info(
                                    f"[AnalysisLayer] Slot-{_idx+1} completed for "
                                    f"event={_analysis_result.event_id} "
                                    f"(perspective={_analysis_result.selected_perspective.axis}, "
                                    f"insights={len(_analysis_result.insights)})"
                                )
                            else:
                                logger.warning(
                                    f"[AnalysisLayer] Slot-{_idx+1} returned None for "
                                    f"event={_target.event.id}; this slot will be "
                                    f"skipped during script generation."
                                )
                        except Exception as _slot_exc:
                            logger.error(
                                f"[AnalysisLayer] Slot-{_idx+1} integration failed for "
                                f"event={_target.event.id}; this slot will be skipped: "
                                f"{type(_slot_exc).__name__}: {_slot_exc}",
                                exc_info=True,
                            )
            except Exception as _al_exc:
                logger.error(
                    f"[AnalysisLayer] Integration failed; falling back to legacy: "
                    f"{type(_al_exc).__name__}: {_al_exc}",
                    exc_info=True,
                )

        # ── Top-3 台本生成ループ: Elite Judge 採用済みリスト上位3件を順次処理 ────
        # EditorialMissionFilter による生成ブロックは廃止。Elite Judge (Gate 3) の決定を最終とする。
        # TOP_N_GENERATION で絞り込み件数を上書き可能（デフォルト 3 = 既存挙動）。
        # 分析レイヤー設計（Section 6）では 1 本フォーカスを推奨するが、ここでは
        # 既存挙動を壊さないため env 未指定時は 3 のまま。
        _top_n = max(1, int(os.getenv("TOP_N_GENERATION", "3")))
        _top_3_candidates: list[ScoredEvent] = sorted(
            all_ranked,
            key=lambda se: (
                _elite_judge_results[se.event.id].total_score
                if se.event.id in _elite_judge_results else 0
            ),
            reverse=True,
        )[:_top_n]

        # schedule.selected には slot-1 のみ入っているので、slot-2/3 を追記する。
        # こうすることで mark_published(schedule, ev_id) が全スロットで効く。
        # slot-1 (override_top) と top-3 が同一 ID の場合は重複させない。
        # rank_in_candidates は「全候補中のスコア順位」を表すフィールドなので、
        # slot 番号ではなく all_ranked 内の本来順位を使う（順位不明時は末尾扱い）。
        _existing_ids = {e.event_id for e in schedule.selected}
        _ranked_index = {se.event.id: i for i, se in enumerate(all_ranked)}
        for _slot_idx, _se in enumerate(_top_3_candidates):
            if _se.event.id in _existing_ids:
                continue
            _orig_rank = _ranked_index.get(_se.event.id, len(all_ranked)) + 1
            schedule.selected.append(
                scored_event_to_schedule_entry(_se, _orig_rank)
            )
            _existing_ids.add(_se.event.id)

        # Per-slot 結果はすべて _slot_records に集約する。
        # ループ後の集約変数:
        #   _slot1_record       — slot-1 の結果（archive 判定 / run_summary の基底）
        #   _completed_count    — 完了スロット数（publish カウンタ更新に使う）
        #   _published_event_ids — 完了したスロットの event_id 一覧（追加観測用）
        # 旧実装は record / _published_event_id / _av_summary を「最後に完了したスロット」
        # で上書きしていたため、slot-1 が rescue されると slot-2/3 の値が混ざり、
        # レポートの「slot-1 の状態」が崩れていた。
        _slot_records: list[JobRecord] = []
        _published_event_id: str | None = None  # slot-1 のみが書き込む
        _published_event_ids: list[str] = []
        _rescue_triggered = False
        authority_pair: list[str] = []
        # AV render: slot-1 の結果を _av_summary に固定し、全スロット分は _slot_av_summaries。
        _av_summary: dict | None = None
        _slot_av_summaries: list[dict] = []

        for _slot_idx, _slot_candidate in enumerate(_top_3_candidates):
            _slot_num = _slot_idx + 1
            _slot_job_id = job_id if _slot_idx == 0 else f"{job_id}-s{_slot_num}"
            _slot_ej_score = (
                _elite_judge_results[_slot_candidate.event.id].total_score
                if _slot_candidate.event.id in _elite_judge_results else "N/A"
            )
            logger.info(
                f"[Slot-{_slot_num}] 台本生成開始 "
                f"(total_score={_slot_ej_score}): "
                f"{_slot_candidate.event.title[:60]}"
            )

            # ── why_slot_won_editorially ─────────────────────────────────────
            _slot_candidate.why_slot1_won_editorially = (
                build_why_slot1_won_editorially(_slot_candidate)
            )

            # ── Judge Rescue Path ─────────────────────────────────────────────
            _slot_judge = _slot_candidate.judge_result
            if _slot_judge is not None:
                from src.triage.gemini_judge import is_rescue_candidate
                if is_rescue_candidate(_slot_judge):
                    logger.warning(
                        f"[GeminiJudge] Slot-{_slot_num} rescue path triggered for "
                        f"'{_slot_candidate.event.title[:50]}': "
                        f"requires_more_evidence=True, "
                        f"blind_spot={_slot_judge.blind_spot_global_score:.1f}, "
                        f"divergence={_slot_judge.divergence_score:.1f}. "
                        "Skipping script generation."
                    )
                    if _slot_idx == 0:
                        _write_judge_rescue(_slot_candidate, _slot_judge, output_dir)
                        _rescue_triggered = True
                    _rescue_record = JobRecord(
                        id=_slot_job_id,
                        event_id="none",
                        status="skipped",
                        error=(
                            f"judge_rescue:requires_more_evidence "
                            f"blind_spot={_slot_judge.blind_spot_global_score:.1f} "
                            f"divergence={_slot_judge.divergence_score:.1f}"
                        ),
                    )
                    save_job(db_path, _rescue_record)
                    _slot_records.append(_rescue_record)
                    continue

            # ── Authority Pair ────────────────────────────────────────────────
            _slot_authority_pair: list[str] = []
            try:
                _profiles = load_source_profiles()
                ev = _slot_candidate.event
                overseas = list(ev.sources_en)
                if ev.sources_by_locale:
                    for loc, refs in ev.sources_by_locale.items():
                        if loc != "japan":
                            overseas.extend(refs)
                _cj = _slot_candidate.judge_result
                if _cj and _cj.judge_error is None and _cj.strongest_authority_pair:
                    from src.ingestion.source_profiles import find_profile
                    converted: list[str] = []
                    for raw_name in _cj.strongest_authority_pair[:2]:
                        p = find_profile(_profiles, raw_name)
                        if p and p.get("can_authority_mention", False):
                            speech = p.get("display_name_speech", "") or p.get("mention_style_short", raw_name)
                            converted.append(speech or raw_name)
                        else:
                            converted.append(raw_name)
                    _slot_authority_pair = converted
                    logger.info(f"[AuthorityMention] Slot-{_slot_num} judge pair: {_slot_authority_pair}")
                else:
                    _slot_authority_pair = select_authority_pair(
                        ev.sources_jp, overseas, _profiles,
                        name_field="display_name_speech",
                    )
                    if _slot_authority_pair:
                        logger.info(f"[AuthorityMention] Slot-{_slot_num} computed pair: {_slot_authority_pair}")
            except Exception as ap_err:
                logger.warning(f"[AuthorityMention] Slot-{_slot_num} failed: {ap_err}")
            if _slot_idx == 0:
                authority_pair = _slot_authority_pair

            # ── 台本生成 (all_ranked を渡して再計算を防ぐ) ───────────────────
            # day_publishes は per-slot で DB から再取得する。
            # ループ前にキャプチャした stats を使い回すと、slot-1 で
            # increment_daily_publish_count しても slot-2/3 の MAX_PUBLISHES_PER_DAY
            # チェックに反映されず、上限を超えて公開してしまうため。
            _live_publishes = get_daily_stats(db_path)["publish_count"]
            # slot-1 のみが triage_scores.json を書き出す。後続スロットでは
            # slot-1 の選定根拠ファイルを上書きしないよう抑制する。
            _slot_record = _generate_outputs(
                events, output_dir, db_path, _slot_job_id,
                budget=budget,
                day_publishes=_live_publishes,
                max_publishes=MAX_PUBLISHES_PER_DAY,
                override_top=_slot_candidate,
                all_ranked=all_ranked,
                authority_pair=_slot_authority_pair,
                write_triage_scores=(_slot_idx == 0),
            )
            _slot_records.append(_slot_record)

            # ── 配信済みマーク ────────────────────────────────────────────────
            if _slot_record.status == "completed":
                _ev_id = _slot_record.event_id
                _published_event_ids.append(_ev_id)
                if _slot_idx == 0:
                    _published_event_id = _ev_id
                schedule = mark_published(schedule, _ev_id)
                _save_daily_schedule(schedule, output_dir)
                try:
                    mark_pool_event_published(db_path, _ev_id)
                    logger.info(f"[Pool] Slot-{_slot_num} event {_ev_id} marked published.")
                except Exception as pool_err:
                    logger.warning(f"[Pool] Slot-{_slot_num} failed to mark {_ev_id} published: {pool_err}")

                # ── Recency Guard 投稿記録 (ANALYSIS_LAYER_ENABLED=true 時のみ) ─
                # 同一 entity/topic を直近 24h 内に再投稿しないための痕跡を残す。
                # 失敗しても後段に影響を与えない（warn にとどめる）。
                if (
                    _analysis_channel_id is not None
                    and os.getenv("ANALYSIS_LAYER_ENABLED", "false").lower() == "true"
                ):
                    try:
                        from src.analysis.recency_guard import record_publication
                        record_publication(_slot_candidate, _analysis_channel_id, db_path)
                    except Exception as _rec_err:
                        logger.warning(
                            f"[AnalysisLayer] record_publication failed for "
                            f"event={_ev_id}: {_rec_err}"
                        )

                # ── AV レンダリング (per-slot) ─────────────────────────────
                # slot-1〜3 すべて WAV / review MP4 を作成する。
                # AUDIO_RENDER_ENABLED=False の場合 _render_av_outputs は no-op
                # （summary に audio_generated=False を返す）。
                _slot_av = _render_av_outputs(_slot_record, output_dir)
                _slot_av["slot"] = _slot_num
                _slot_av["event_id"] = _ev_id
                _slot_av_summaries.append(_slot_av)
                if _slot_av.get("audio_generated") or _slot_av.get("error"):
                    save_job(db_path, _slot_record)
                # _av_summary は slot-1 の結果のみを表す（旧実装は最初に completed
                # したスロットだったが、slot-1 が rescue/失敗のときに slot-2/3 の
                # 値が混じり、レポートが「slot-1 の AV」と一致しなくなっていた）。
                if _slot_idx == 0:
                    _av_summary = _slot_av

        # Slot-1 候補を downstream の報告・監査変数として保持
        _candidate_to_generate = _top_3_candidates[0] if _top_3_candidates else _candidate_to_generate
        _selection_override_applied: bool = (
            _final_selected_slot1_id is not None
            and _scheduled_slot1_id is not None
            and _final_selected_slot1_id != _scheduled_slot1_id
        )

        # ── Per-slot 結果の集約 ────────────────────────────────────────────
        # record 変数は「slot-1 の結果」を表すように固定する。
        # 旧実装はループ末尾の値（最後のスロット）を使っていたため、slot-1 が
        # 成功でも slot-3 が失敗すると run_summary 全体が failed 扱いになっていた。
        record: JobRecord
        if _slot_records:
            record = _slot_records[0]
        else:
            record = JobRecord(
                id=job_id, event_id="none", status="skipped", error="no_slots_attempted"
            )
        _completed_count = sum(1 for r in _slot_records if r.status == "completed")
        # archive 判定: 全スロット中に1件でも処理完了相当があれば archive する。
        # （slot-1 が失敗でも slot-2/3 が completed なら成果物は残っている）
        _any_archivable = any(
            r.status in ("completed", "skipped") for r in _slot_records
        ) or not _slot_records  # スロット未到達も archive 対象（既存挙動を維持）

        # ── Job 成功後: batch を archive へ移動 ─────────────────────────────
        archived_count = 0
        if _any_archivable:
            # skipped (daily limit) も archive 済み = 処理完了とみなす
            try:
                archived_count = _archive_batch(batch, archive_dir)
                mark_batch_status(
                    db_path, batch_id, "archived",
                    archived_at=datetime.now(timezone.utc).isoformat(),
                )
                logger.info(
                    f"[Archive] batch={batch_id} archived successfully "
                    f"({archived_count} files)"
                )
            except Exception as arc_err:
                logger.error(
                    f"[Archive] Failed to archive batch={batch_id}: {arc_err}. "
                    "Batch will remain as 'processing' for manual cleanup."
                )
        else:
            # failed: ファイルを残して再試行可能にする
            mark_batch_status(db_path, batch_id, "failed")
            logger.warning(
                f"[Batch] batch={batch_id} marked as FAILED. "
                "Files remain in place for retry."
            )

        batch_info["archived_file_count"] = archived_count

        triage_src = getattr(record, "_triage_source_counts", {})
        _all_sel_pub = (
            len(schedule.selected) > 0
            and all(e.published for e in schedule.selected)
            and schedule.open_slots == 0
        )
        _slot1_se = _candidate_to_generate
        _slot1_ap = authority_pair if not _rescue_triggered else []
        _judge_summary = _build_judge_summary(
            judge_results, all_ranked, _slot1_se, _slot1_ap,
            final_selection_fallback_used=_final_selection_fallback_used,
            final_selection_fallback_reason=_final_selection_fallback_reason,
            quota_fallback_candidate_id=_quota_fallback_candidate_id,
            quota_fallback_candidate_title=_quota_fallback_candidate_title,
            model_resolution=_judge_model_resolution,
        )
        # ── Audio & Video Render ────────────────────────────────────────────
        # NOTE: per-slot AV レンダリングはループ内で完了済み（_slot_av_summaries）。
        # _av_summary は slot-1 由来。下流レポートには slot-1 の AV を表示しつつ、
        # per_slot に全スロット分を添える。元の _av_summary dict を破壊的に
        # 書き換えると、_slot_av_summaries[0] と同一参照のままで JSON が紛らわしく
        # なるため、新しい dict にコピーして per_slot を追加する。
        if _av_summary is not None and _slot_av_summaries:
            _av_summary = {**_av_summary, "per_slot": _slot_av_summaries}

        _write_debug_artifacts(output_dir, run_stats, schedule, rolling_window_stats)
        _write_discovery_audit_safe(all_ranked_appraised, run_stats, output_dir, schedule)
        _write_latest_candidate_report(
            output_dir,
            scheduled_slot1_id=_scheduled_slot1_id,
            reranked_top_id=_reranked_top_id,
            final_selected_slot1_id=_final_selected_slot1_id,
            slot1_selection_source=_slot1_selection_source,
            slot1_block_reason=_slot1_block_reason,
            all_ranked=all_ranked,
            judge_results=judge_results,
            generated_event_id=_published_event_id,
            published_event_id=_published_event_id,
            selection_override_applied=_selection_override_applied,
            final_selection_fallback_used=_final_selection_fallback_used,
            final_selection_fallback_reason=_final_selection_fallback_reason,
            quota_fallback_candidate_id=_quota_fallback_candidate_id,
            model_resolution=_judge_model_resolution,
            budget_mode_summary=budget.to_publish_mode_summary(),
            av_render_summary=_av_summary,
        )
        _save_run_summary(
            output_dir, job_id, run_stats, record, budget,
            triage_source_counts=triage_src,
            daily_schedule=schedule,
            batch_info=batch_info,
            schedule_tracking={
                "scheduled_event_id": scheduled_event_id,
                "schedule_snapshot_used": schedule_snapshot_used,
                "schedule_mismatch_resolved": schedule_mismatch_resolved,
                "no_publishable_candidates": False,
                "all_selected_published": _all_sel_pub,
                "fallback_blocked_by_quality_floor": False,
                "published_event_id": _published_event_id,
                "publish_mark_target": (
                    _scheduled_slot1_id if _selection_override_applied else _published_event_id
                ),
                "selection_override_applied": _selection_override_applied,
                **_slot1_audit(_slot1_se),
            },
            rolling_window_stats=rolling_window_stats,
            judge_summary=_judge_summary,
            editorial_mission_summary=_editorial_mission_summary,
            av_render_summary=_av_summary,
        )

        # publish カウンタは完了スロット数で集計する。
        # 旧実装は record (= 最後のスロット) のみ +1 だったため、3件公開しても
        # ログ上は +1 しかカウントされず観測値が不正確だった。
        budget.log_summary(
            day_runs=stats_after["run_count"],
            day_publishes=stats_after["publish_count"] + _completed_count,
        )
        return record

    except Exception as exc:
        # 予期しない例外: batch を failed にして再試行可能にする
        logger.error(f"[Batch] Unexpected error for batch={batch_id}: {exc}", exc_info=True)
        mark_batch_status(db_path, batch_id, "failed")
        logger.warning(
            f"[Batch] batch={batch_id} marked as FAILED. "
            "Files remain in place for retry."
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Hydrangea News PoC")
    parser.add_argument(
        "--mode",
        choices=["sample", "normalized", "render_existing"],
        default="sample",
        help=(
            "入力モード: sample=サンプルJSON / normalized=実ニュース (batch-based) / "
            "render_existing=既存候補から音声+動画を生成（選択パイプライン不要）"
        ),
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=INPUT_DIR / "sample_events.json",
        help="[sample モード] ニュースイベントJSONのパス",
    )
    parser.add_argument(
        "--normalized-dir",
        type=Path,
        default=NORMALIZED_DIR,
        dest="normalized_dir",
        help="[normalized モード] 正規化済みJSONのディレクトリ（batch manifest の参照用）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR,
        help="成果物の出力ディレクトリ",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DB_PATH,
        help="SQLiteデータベースのパス",
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=ARCHIVE_DIR,
        dest="archive_dir",
        help="[normalized モード] archive 先ディレクトリ",
    )
    parser.add_argument(
        "--run-mode",
        choices=["publish_mode", "research_mode"],
        default=None,
        dest="run_mode",
        help=(
            "実行モード: publish_mode (default) = production 予算を保護する / "
            "research_mode = 全予算を探索に使用可能（実験用）。"
            f"未指定時は RUN_MODE 環境変数 (現在: {RUN_MODE}) を使用。"
        ),
    )
    # render_existing mode args
    parser.add_argument(
        "--event-id",
        dest="event_id",
        metavar="EVENT_ID",
        default=None,
        help="[render_existing モード] レンダリングする event_id",
    )
    parser.add_argument(
        "--latest-completed",
        action="store_true",
        dest="latest_completed",
        default=False,
        help="[render_existing モード] --output 内の最新完了候補を自動選択してレンダリング",
    )
    args = parser.parse_args()

    if args.mode == "render_existing":
        from src.render.run_render import render_existing, resolve_event_id
        event_id = resolve_event_id(args.event_id, args.latest_completed, args.output)
        summary = render_existing(event_id, args.output)
        print(f"\n完了 (render_existing): event_id={event_id}")
        print(f"  audio generated : {summary['audio_generated']}")
        print(f"  video generated : {summary['video_generated']}")
        if summary.get("voiceover_path"):
            print(f"  voiceover       : {summary['voiceover_path']}")
        if summary.get("review_mp4_path"):
            print(f"  review MP4      : {summary['review_mp4_path']}")
        if summary.get("render_report_path"):
            print(f"  render report   : {summary['render_report_path']}")
        if summary.get("error"):
            print(f"  error           : {summary['error']}")
            raise SystemExit(1)
    elif args.mode == "normalized":
        record = run_from_normalized(
            args.normalized_dir, args.output, args.db,
            archive_dir=args.archive_dir,
            run_mode=args.run_mode,
        )
        print(f"\n完了: event_id={record.event_id}, job_id={record.id}, status={record.status}")
        print(f"  出力先: {args.output}")
    else:
        record = run(args.input, args.output, args.db, run_mode=args.run_mode)
        print(f"\n完了: event_id={record.event_id}, job_id={record.id}, status={record.status}")
        print(f"  出力先: {args.output}")


if __name__ == "__main__":
    main()
