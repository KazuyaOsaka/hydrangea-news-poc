"""Discovery Audit Layer — blind spot detection for Hydrangea News.

Generates 3 ranked discovery lanes without triggering content generation.
Writes:
  data/output/discovery_audit.json
  data/output/discovery_audit.md

Called after rank + appraisal in run_from_normalized().

Guardrails:
  - Does NOT auto-generate script/article/video
  - Does NOT relax quality floor
  - Does NOT expand sources
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.shared.models import DailySchedule, ScoredEvent

_NON_WESTERN_REGIONS = frozenset({"middle_east", "east_asia"})
_SPORTS_BUCKETS = frozenset({"sports", "japanese_person_abroad"})
_LOCAL_BUCKETS = frozenset({"general", "mass_appeal"})


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_axis(se: "ScoredEvent", axis: str) -> float:
    return float(se.score_breakdown.get(f"editorial:{axis}", 0.0))


def _japan_source_count(se: "ScoredEvent") -> int:
    if se.event.sources_by_locale and "japan" in se.event.sources_by_locale:
        return len(se.event.sources_by_locale["japan"])
    return len(se.event.sources_jp)


def _en_source_count(se: "ScoredEvent") -> int:
    if se.event.sources_en:
        return len(se.event.sources_en)
    if se.event.sources_by_locale:
        return sum(
            1 for refs in se.event.sources_by_locale.values()
            for ref in refs
            if ref.language == "en"
        )
    return 0


def _non_west_source_count(se: "ScoredEvent") -> int:
    if not se.event.sources_by_locale:
        return 0
    return sum(
        len(refs) for region, refs in se.event.sources_by_locale.items()
        if region in _NON_WESTERN_REGIONS
    )


def _source_counts_by_region(se: "ScoredEvent") -> dict[str, int]:
    if not se.event.sources_by_locale:
        return {}
    return {region: len(refs) for region, refs in se.event.sources_by_locale.items()}


def _is_cross_lang_cluster(se: "ScoredEvent") -> bool:
    """True if both JP and EN sources are present OR cross_lang_bonus > 0."""
    if _japan_source_count(se) > 0 and _en_source_count(se) > 0:
        return True
    return float(se.score_breakdown.get("cross_lang_bonus", 0.0)) > 0.0


def _merge_confidence_label(se: "ScoredEvent") -> str:
    bonus = float(se.score_breakdown.get("cross_lang_bonus", 0.0))
    if bonus >= 5.0:
        return "full"     # gap_reasoning + structured sources
    if bonus >= 3.0:
        return "medium"   # gap_reasoning only
    if bonus >= 2.0:
        return "low"      # sources only
    if bonus > 0.0:
        return "cluster"  # BFS cluster mode
    return "none"


def _extract_hold_back_reason(rejection_reason: str | None) -> str | None:
    """Extract structured reason from 'quality_floor:no_cross_lang_support:...' format."""
    if not rejection_reason:
        return None
    if rejection_reason.startswith("quality_floor:"):
        parts = rejection_reason.split(":", 2)
        return parts[1] if len(parts) >= 2 else rejection_reason
    return rejection_reason


# ── Scoring per lane ─────────────────────────────────────────────────────────

def _lane_a_score(se: "ScoredEvent") -> float:
    """linked_jp_global: reward true JP+global linkage, multi-region, non-West+Japan."""
    pg = _get_axis(se, "perspective_gap_score")
    ga = _get_axis(se, "global_attention_score")
    jr = _get_axis(se, "japan_relevance_score")
    mrs = _get_axis(se, "multi_region_score")
    rcs = _get_axis(se, "regional_contrast_score")
    bip = _get_axis(se, "background_inference_potential")

    score = pg * 1.5 + ga + jr + mrs * 0.5 + rcs * 0.5 + bip * 0.3
    if se.primary_bucket in _SPORTS_BUCKETS:
        score -= 5.0
    if se.primary_bucket in _LOCAL_BUCKETS:
        score -= 3.0
    return score


def _lane_b_score(se: "ScoredEvent") -> float:
    """global_big_japan_missing: high global attention + low JP coverage + indirect Japan impact."""
    ga   = _get_axis(se, "global_attention_score")
    cg   = _get_axis(se, "coverage_gap_score")
    gd   = _get_axis(se, "geopolitics_depth_score")
    be   = _get_axis(se, "big_event_score")
    tg   = _get_axis(se, "tech_geopolitics_score")
    ijai = _get_axis(se, "indirect_japan_impact_score")
    jp_count = _japan_source_count(se)

    score = ga * 2.0 + cg * 1.5 + max(gd, be, tg) * 0.5 + ijai * 0.8
    score -= jp_count * 1.0
    return score


def _lane_c_score(se: "ScoredEvent") -> float:
    """jp_missing_global_link: JP stories likely to have EN counterparts."""
    be = _get_axis(se, "big_event_score")
    gd = _get_axis(se, "geopolitics_depth_score")
    tg = _get_axis(se, "tech_geopolitics_score")
    jr = _get_axis(se, "japan_relevance_score")
    jp_count = _japan_source_count(se)

    score = be + gd + tg + jr * 0.5 + min(jp_count * 0.5, 2.0)
    return score


def _blind_spot_score(se: "ScoredEvent", jp_count: int, nw_count: int) -> float:
    """
    Rewards: high global attention, low JP coverage, non-West present, indirect Japan impact.
    Range: 0-10
    """
    ga   = _get_axis(se, "global_attention_score")
    cg   = _get_axis(se, "coverage_gap_score")
    jr   = _get_axis(se, "japan_relevance_score")
    be   = _get_axis(se, "big_event_score")
    gd   = _get_axis(se, "geopolitics_depth_score")
    ijai = _get_axis(se, "indirect_japan_impact_score")

    score = (ga / 8.0) * 3.0        # 0-3: global attention
    score += (cg / 8.0) * 2.5       # 0-2.5: coverage gap
    score += (ijai / 10.0) * 3.0    # 0-3: indirect Japan impact (new)
    if nw_count > 0:
        score += 1.0                 # non-West present
    if jr >= 3 or be >= 4 or gd >= 4:
        score += 0.5                 # additional Japan signal
    return round(min(10.0, max(0.0, score)), 2)


# ── Sentence generation ───────────────────────────────────────────────────────

def _why_interesting(se: "ScoredEvent", lane: str) -> str:
    pg = _get_axis(se, "perspective_gap_score")
    cg = _get_axis(se, "coverage_gap_score")
    jr = _get_axis(se, "japan_relevance_score")
    ga = _get_axis(se, "global_attention_score")
    tg = _get_axis(se, "tech_geopolitics_score")
    gd = _get_axis(se, "geopolitics_depth_score")
    be = _get_axis(se, "big_event_score")
    rcs = _get_axis(se, "regional_contrast_score")

    if lane == "linked_jp_global":
        if pg >= 5:
            return "JP and global press cover this from opposing angles — strong perspective gap."
        if rcs >= 5:
            return "Japan vs non-Western perspectives create a rare multi-angle contrast story."
        if jr >= 6 and ga >= 4:
            return "High Japan relevance meets high global attention — bilateral significance confirmed."
        return "Both JP and global sources present; linked story with cross-cultural angle."

    if lane == "global_big_japan_missing":
        if cg >= 6:
            return "Major global story with near-zero Japanese press coverage — textbook blind spot."
        if ga >= 6:
            return "Top-tier global attention but Japan is barely watching."
        if gd >= 5 or be >= 5:
            return "Significant geopolitical/economic event with real Japan impact potential, yet uncovered."
        return "Globally covered story that Japan appears to be under-reporting."

    # lane == "jp_missing_global_link"
    if be >= 5:
        return "High-signal JP story (major event) but no English counterpart was merged."
    if tg >= 5:
        return "Tech/geopolitics JP story likely has global coverage — merge failed to connect."
    if gd >= 4:
        return "JP geopolitics story with suspected global counterpart that wasn't linked."
    return "Strong JP story that likely has EN coverage but cross-language merge didn't connect them."


def _why_not_publishable(se: "ScoredEvent", hold_back_reason: str | None, rank: int) -> str:
    if rank > 15:
        return "Ranked outside top 15 — not appraised; quality floor not yet applied."
    if hold_back_reason == "no_cross_lang_support":
        return "No English source in cluster — JP↔global comparison is impossible without it."
    if hold_back_reason == "weak_japan_angle":
        return "Japan angle is too weak; no clear path to a Japan-focused story."
    if hold_back_reason == "low_evidence":
        return "All editorial axes weak — no strong hook, gap, or strategic angle found."
    if hold_back_reason == "weak_structural_insight":
        return "No background inference potential; story lacks structural depth."
    if hold_back_reason == "pool_story_already_better":
        return "A stronger version of this story is already in the candidate pool."

    # Infer from fields
    if not se.event.sources_en and not _en_source_count(se):
        return "No English sources — cross-language comparison unavailable."
    if not se.event.impact_on_japan:
        return "Impact on Japan not established — quality floor requires this field."
    jr = _get_axis(se, "japan_relevance_score")
    if jr < 3:
        return "Japan relevance is too low to justify a JP-audience story."
    if se.appraisal_type:
        return "Passed quality floor — publishable if schedule has an open slot."
    return "Did not pass quality floor; appraisal found insufficient editorial angle."


# ── Candidate record builder ──────────────────────────────────────────────────

def _extract_candidate(
    se: "ScoredEvent",
    rank: int,
    held_back_ids: set[str],
    held_back_reasons: dict[str, str],
    lane: str,
) -> dict:
    jp_count = _japan_source_count(se)
    en_count = _en_source_count(se)
    nw_count = _non_west_source_count(se)
    regions = sorted(se.event.sources_by_locale.keys()) if se.event.sources_by_locale else []
    cross_lang = _is_cross_lang_cluster(se)
    conf = _merge_confidence_label(se)
    hold_back_reason = (
        _extract_hold_back_reason(held_back_reasons.get(se.event.id))
        if se.event.id in held_back_ids else None
    )

    return {
        "event_id": se.event.id,
        "title": se.event.title,
        "bucket": se.primary_bucket,
        "score": round(se.score, 2),
        "source_counts_by_region": _source_counts_by_region(se),
        "japan_source_count": jp_count,
        "en_source_count": en_count,
        "non_west_source_count": nw_count,
        "source_regions": regions,
        "cross_lang_cluster": cross_lang,
        "merge_confidence": conf,
        "japan_relevance_score": round(_get_axis(se, "japan_relevance_score"), 1),
        "global_attention_score": round(_get_axis(se, "global_attention_score"), 1),
        "perspective_gap_score": round(_get_axis(se, "perspective_gap_score"), 1),
        "coverage_gap_score": round(_get_axis(se, "coverage_gap_score"), 1),
        "background_inference_potential": round(_get_axis(se, "background_inference_potential"), 1),
        "indirect_japan_impact_score": round(_get_axis(se, "indirect_japan_impact_score"), 1),
        "blind_spot_score": _blind_spot_score(se, jp_count, nw_count),
        "hold_back_reason": hold_back_reason,
        "why_this_is_interesting": _why_interesting(se, lane),
        "why_not_publishable_yet": _why_not_publishable(se, hold_back_reason, rank),
    }


# ── Merge failure inference ───────────────────────────────────────────────────

def _infer_pair_merge_failure(
    jp_se: "ScoredEvent", en_se: "ScoredEvent", run_stats: dict
) -> str:
    bfs_edges = run_stats.get("cross_lang_bfs_edges", 0)
    if bfs_edges == 0:
        return "no_bfs_edges_formed: no anchor token overlap between any JP/EN pair this run"
    if jp_se.primary_bucket != en_se.primary_bucket:
        return f"topic_mismatch: JP bucket={jp_se.primary_bucket} vs EN bucket={en_se.primary_bucket}"
    return "anchor_token_mismatch: shared anchor count below BFS threshold"


def _infer_self_merge_failure(se: "ScoredEvent", run_stats: dict) -> str:
    bfs_edges = run_stats.get("cross_lang_bfs_edges", 0)
    reject_reasons: dict = run_stats.get("cross_lang_bfs_reject_reasons", {})
    if bfs_edges == 0 and reject_reasons:
        top_reason = max(reject_reasons, key=lambda k: reject_reasons[k])
        return f"bfs_reject_{top_reason}: no EN cluster had sufficient shared anchor tokens"
    if bfs_edges == 0:
        return "no_cross_lang_merges_occurred: all JP-EN pairs failed anchor token matching this run"
    return "no_en_cluster_matched: no English article cluster found with enough anchor overlap"


# ── Diagnosis ─────────────────────────────────────────────────────────────────

def _diagnose_failure_mode(
    all_ranked: "list[ScoredEvent]",
    run_stats: dict,
    lane_a: list[dict],
    schedule: "DailySchedule | None",
) -> dict:
    jp_articles = run_stats.get("jp_article_count", 0)
    en_articles = run_stats.get("en_article_count", 0)
    bfs_edges = run_stats.get("cross_lang_bfs_edges", 0)
    llm_merged = run_stats.get("llm_pairs_merged", 0)
    cross_lang_clusters = run_stats.get("cross_lang_cluster_count", 0)

    held_back_count = len(schedule.held_back) if schedule else 0
    selected_count = len(schedule.selected) if schedule else 0

    held_back_reason_counts: dict[str, int] = {}
    if schedule:
        for entry in schedule.held_back:
            raw = entry.rejection_reason or "unknown"
            structured = _extract_hold_back_reason(raw) or raw
            held_back_reason_counts[structured] = held_back_reason_counts.get(structured, 0) + 1

    source_load_report = run_stats.get("source_load_report", {})
    bug_sources = [
        src for src, v in source_load_report.items()
        if v.get("normalized_count", 0) > 0 and v.get("loaded_count", 0) == 0
    ]

    issues: list[str] = []
    dominant_failure = "unknown"

    # Source intake
    if jp_articles == 0:
        issues.append("source_intake: JP articles loaded = 0")
        dominant_failure = "source_intake"
    elif bug_sources:
        issues.append(f"source_intake: bug_suspected in {bug_sources}")
        dominant_failure = "source_intake"

    # Cross-lang merge
    if jp_articles > 0 and en_articles > 0 and bfs_edges == 0 and llm_merged == 0:
        issues.append(
            f"cross_lang_merge: jp={jp_articles} en={en_articles} articles loaded "
            "but 0 BFS edges and 0 LLM merges"
        )
        if dominant_failure == "unknown":
            dominant_failure = "cross_lang_merge"
    elif cross_lang_clusters == 0 and jp_articles > 0 and en_articles > 0:
        issues.append("cross_lang_merge: no cross-lang clusters formed despite JP+EN articles")
        if dominant_failure == "unknown":
            dominant_failure = "cross_lang_merge"

    # Japan-angle inference
    weak_ja_count = (
        held_back_reason_counts.get("weak_japan_angle", 0)
        + held_back_reason_counts.get("no_cross_lang_support", 0)
    )
    if weak_ja_count > 1 and dominant_failure == "unknown":
        issues.append(
            f"japan_angle_inference: {weak_ja_count} candidates held_back for "
            "weak_japan_angle / no_cross_lang_support"
        )
        dominant_failure = "japan_angle_inference"

    # Scheduler / gating
    if len(lane_a) > 0 and selected_count == 0 and held_back_count > 0:
        issues.append(
            f"scheduler_gating: {held_back_count} candidates held_back, 0 selected"
        )
        if dominant_failure == "unknown":
            dominant_failure = "scheduler_gating"

    if not issues:
        issues.append("No obvious failure mode detected — pipeline appears healthy.")
        dominant_failure = "none"

    return {
        "dominant_failure_mode": dominant_failure,
        "issues": issues,
        "details": {
            "jp_articles_loaded": jp_articles,
            "en_articles_loaded": en_articles,
            "cross_lang_bfs_edges": bfs_edges,
            "llm_merged": llm_merged,
            "cross_lang_clusters": cross_lang_clusters,
            "held_back_count": held_back_count,
            "held_back_reason_counts": held_back_reason_counts,
            "selected_count": selected_count,
            "bug_suspected_sources": bug_sources,
        },
    }


# ── Markdown renderer ─────────────────────────────────────────────────────────

def _render_markdown(audit: dict, run_stats: dict) -> str:
    lines: list[str] = []
    ts = audit["generated_at"]
    total = audit["total_candidates"]
    diag = audit["diagnosis"]
    dom = diag["dominant_failure_mode"]
    d = diag["details"]

    lines.append("# Hydrangea Discovery Audit\n")
    lines.append(f"Generated: {ts}  |  Total candidates this batch: {total}\n")
    lines.append(f"**Dominant failure mode: `{dom}`**\n")
    for issue in diag["issues"]:
        lines.append(f"- {issue}")
    lines.append("")

    # Pipeline stats table
    lines.append("## Pipeline Stats\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| JP articles loaded | {d['jp_articles_loaded']} |")
    lines.append(f"| EN articles loaded | {d['en_articles_loaded']} |")
    lines.append(f"| Cross-lang BFS edges | {d['cross_lang_bfs_edges']} |")
    lines.append(f"| LLM merges | {d['llm_merged']} |")
    lines.append(f"| Cross-lang clusters | {d['cross_lang_clusters']} |")
    lines.append(f"| Candidates selected | {d['selected_count']} |")
    lines.append(f"| Candidates held-back | {d['held_back_count']} |")
    if d["bug_suspected_sources"]:
        lines.append(f"| Bug-suspected sources | {', '.join(d['bug_suspected_sources'])} |")
    lines.append("")

    def _render_lane(candidates: list[dict], limit: int = 5) -> list[str]:
        out: list[str] = []
        for i, c in enumerate(candidates[:limit], 1):
            out.append(f"### {i}. {c['title'][:72]}")
            out.append(
                f"- **event_id**: `{c['event_id']}` | **bucket**: {c['bucket']} | "
                f"**score**: {c['score']}"
            )
            regions_str = ", ".join(c["source_regions"]) or "n/a"
            out.append(f"- **regions**: {regions_str}")
            out.append(
                f"- JP={c['japan_source_count']} EN={c['en_source_count']} "
                f"non-West={c['non_west_source_count']} | "
                f"cross_lang={c['cross_lang_cluster']} merge_conf={c['merge_confidence']}"
            )
            out.append(
                f"- JR={c['japan_relevance_score']} GA={c['global_attention_score']} "
                f"PG={c['perspective_gap_score']} CG={c['coverage_gap_score']} "
                f"BIP={c['background_inference_potential']} "
                f"**blind_spot={c['blind_spot_score']}**"
            )
            if c.get("hold_back_reason"):
                out.append(f"- **hold_back_reason**: `{c['hold_back_reason']}`")
            out.append(f"- **Why interesting**: {c['why_this_is_interesting']}")
            out.append(f"- **Why not yet**: {c['why_not_publishable_yet']}")
            if c.get("nearest_en_candidates"):
                out.append("- **Nearest EN candidates** (potential missed partners):")
                for en_c in c["nearest_en_candidates"]:
                    out.append(
                        f"  - `{en_c['event_id'][:20]}` {en_c['title'][:55]}  "
                        f"_fail: {en_c['merge_failure_reason'][:65]}_"
                    )
            if c.get("merge_failure_reason") and "nearest_en_candidates" not in c:
                out.append(f"- **merge_failure_reason**: {c['merge_failure_reason']}")
            out.append("")
        return out

    # Lane A
    lane_a = audit["lanes"]["A_linked_jp_global_top10"]
    lines.append(
        f"## Lane A — Linked JP↔Global  "
        f"(showing top {min(5, len(lane_a))} of {len(lane_a)})\n"
    )
    lines.append(
        "> Stories with confirmed JP+global source linkage. "
        "Primary Hydrangea candidate pool.\n"
    )
    if lane_a:
        lines.extend(_render_lane(lane_a))
    else:
        lines.append("_No cross-lang linked stories found in this batch._\n")

    # Lane B
    lane_b = audit["lanes"]["B_global_big_japan_missing_top10"]
    lines.append(
        f"## Lane B — Global Big, Japan Missing  "
        f"(showing top {min(5, len(lane_b))} of {len(lane_b)})\n"
    )
    lines.append(
        "> Globally significant stories Japan is under-covering. "
        "Watch for future JP angle.\n"
    )
    if lane_b:
        lines.extend(_render_lane(lane_b))
    else:
        lines.append("_No globally important / JP-missing stories found._\n")

    # Lane C
    lane_c = audit["lanes"]["C_jp_story_missing_global_link_top10"]
    lines.append(
        f"## Lane C — JP Story, Missing Global Link  "
        f"(showing top {min(5, len(lane_c))} of {len(lane_c)})\n"
    )
    lines.append(
        "> Strong JP stories that likely have EN counterparts "
        "but cross-language merge failed.\n"
    )
    if lane_c:
        lines.extend(_render_lane(lane_c))
    else:
        lines.append("_No JP-only stories with suspected missed EN links._\n")

    # Bottom-line diagnosis
    _labels = {
        "source_intake": (
            "**Source Intake** — JP or EN articles are not loading. "
            "Check `source_load_report.json` for bug-suspected sources."
        ),
        "cross_lang_merge": (
            "**Cross-Lang Merge** — JP+EN articles exist but aren't linking. "
            "BFS anchor token overlap too low or entity mapping gap."
        ),
        "japan_angle_inference": (
            "**Japan-Angle Inference** — Merges happen but stories are held back as "
            "weak_japan_angle / no_cross_lang_support. "
            "Need stronger JP perspective or impact_on_japan signal."
        ),
        "scheduler_gating": (
            "**Scheduler / Gating** — Good stories exist but quality floor or "
            "diversity constraints prevent selection."
        ),
        "none": "**No dominant failure** — Pipeline is producing discovery candidates normally.",
        "unknown": "**Unknown** — Check pipeline logs for unusual behavior.",
    }
    lines.append("## Bottom-Line Diagnosis\n")
    lines.append(_labels.get(dom, f"**{dom}**"))
    lines.append("")

    if d["held_back_reason_counts"]:
        lines.append("### Held-Back Reason Breakdown\n")
        for reason, count in sorted(
            d["held_back_reason_counts"].items(), key=lambda x: -x[1]
        ):
            lines.append(f"- `{reason}`: {count}")
        lines.append("")

    return "\n".join(lines)


# ── Public API ────────────────────────────────────────────────────────────────

def write_discovery_audit(
    all_ranked: "list[ScoredEvent]",
    run_stats: dict,
    output_dir: Path,
    schedule: "DailySchedule | None" = None,
) -> dict:
    """Build and write discovery_audit.json and discovery_audit.md.

    Args:
        all_ranked:  Scored events for this batch (post-appraisal).
        run_stats:   Build stats dict from build_events_from_normalized().
        output_dir:  Where to write the output files.
        schedule:    Today's DailySchedule (for hold_back_reason lookup).

    Returns:
        The audit dict (for testing).
    """
    from src.shared.logger import get_logger
    logger = get_logger(__name__)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Build held_back lookup from schedule
    held_back_ids: set[str] = set()
    held_back_reasons: dict[str, str] = {}  # event_id → rejection_reason string
    if schedule:
        for entry in schedule.held_back:
            held_back_ids.add(entry.event_id)
            if entry.rejection_reason:
                held_back_reasons[entry.event_id] = entry.rejection_reason

    # rank map (1-indexed) for why_not_publishable threshold
    rank_map = {se.event.id: i + 1 for i, se in enumerate(all_ranked)}

    # ── Lane A: linked_jp_global ───────────────────────────────────────────
    lane_a_pool = [se for se in all_ranked if _is_cross_lang_cluster(se)]
    lane_a_pool.sort(key=_lane_a_score, reverse=True)
    linked_jp_global = [
        _extract_candidate(
            se, rank_map.get(se.event.id, 99),
            held_back_ids, held_back_reasons, "linked_jp_global"
        )
        for se in lane_a_pool[:10]
    ]

    # ── Lane B: global_big_japan_missing ──────────────────────────────────
    # Primary filter: EN sources present, JP sources absent
    lane_b_pool = [
        se for se in all_ranked
        if _en_source_count(se) > 0 and _japan_source_count(se) == 0
    ]
    # Fallback: any event with high global attention and coverage_gap
    if not lane_b_pool:
        lane_b_pool = [
            se for se in all_ranked
            if _get_axis(se, "global_attention_score") >= 2.0
            and _get_axis(se, "coverage_gap_score") >= 3.0
        ]
    lane_b_pool.sort(key=_lane_b_score, reverse=True)
    global_big_japan_missing = [
        _extract_candidate(
            se, rank_map.get(se.event.id, 99),
            held_back_ids, held_back_reasons, "global_big_japan_missing"
        )
        for se in lane_b_pool[:10]
    ]

    # ── Lane C: jp_story_missing_global_link ──────────────────────────────
    lane_c_pool = [
        se for se in all_ranked
        if _japan_source_count(se) > 0
        and _en_source_count(se) == 0
        and not _is_cross_lang_cluster(se)
    ]
    lane_c_pool.sort(key=_lane_c_score, reverse=True)

    # EN-dominant pool for nearest-partner lookup
    en_dominant_pool = [
        se for se in all_ranked
        if _en_source_count(se) > 0 and _japan_source_count(se) == 0
    ]

    jp_missing_global_link: list[dict] = []
    for se in lane_c_pool[:10]:
        candidate = _extract_candidate(
            se, rank_map.get(se.event.id, 99),
            held_back_ids, held_back_reasons, "jp_missing_global_link"
        )
        candidate["merge_failure_reason"] = _infer_self_merge_failure(se, run_stats)

        # Nearest EN candidates by bucket/category overlap
        nearest_en = [
            {
                "event_id": en_se.event.id,
                "title": en_se.event.title[:80],
                "bucket": en_se.primary_bucket,
                "score": round(en_se.score, 2),
                "en_source_count": _en_source_count(en_se),
                "merge_failure_reason": _infer_pair_merge_failure(se, en_se, run_stats),
            }
            for en_se in en_dominant_pool
            if en_se.primary_bucket == se.primary_bucket
            or en_se.event.category == se.event.category
        ][:3]
        candidate["nearest_en_candidates"] = nearest_en
        jp_missing_global_link.append(candidate)

    # ── Diagnosis ─────────────────────────────────────────────────────────
    diagnosis = _diagnose_failure_mode(
        all_ranked, run_stats, linked_jp_global, schedule
    )

    # ── Assemble ──────────────────────────────────────────────────────────
    audit: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_candidates": len(all_ranked),
        "summary": {
            "linked_jp_global_count": len(linked_jp_global),
            "global_big_japan_missing_count": len(global_big_japan_missing),
            "jp_missing_global_link_count": len(jp_missing_global_link),
            "dominant_failure_mode": diagnosis["dominant_failure_mode"],
        },
        "lanes": {
            "A_linked_jp_global_top10": linked_jp_global,
            "B_global_big_japan_missing_top10": global_big_japan_missing,
            "C_jp_story_missing_global_link_top10": jp_missing_global_link,
        },
        "diagnosis": diagnosis,
    }

    json_path = output_dir / "discovery_audit.json"
    json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = output_dir / "discovery_audit.md"
    md_path.write_text(_render_markdown(audit, run_stats), encoding="utf-8")

    logger.info(
        f"[DiscoveryAudit] Written: A={len(linked_jp_global)} "
        f"B={len(global_big_japan_missing)} C={len(jp_missing_global_link)} "
        f"dominant_failure={diagnosis['dominant_failure_mode']}"
    )
    return audit
