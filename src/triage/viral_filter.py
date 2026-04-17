"""viral_filter.py — Viral & Interest Filter (two-step pre-generation gate)

Pass C — runs after Editorial Appraisal, before the Gemini Judge pass.

Purpose:
  Filter out low-probability Japan-market stories before the expensive
  generation stage (LLM judge + script + article).

Step 1: Cheap deterministic pre-score (no LLM, always runs)
  Uses editorial axes already computed in score_breakdown.
  Components (each capped, sum capped at 100):
    - japan_impact       (0-40): japan_relevance × 3 + indirect_japan_impact × 1
    - topic_affinity     (0-25): best of tech/events/mass_appeal × 1.5
    - discussion_trigger (0-20): max(breaking_shock, geopolitics) × 2
    - contrast_potential (0-15): perspective_gap × 1 + coverage_gap × 0.5
    - both_lang_bonus    (0-3):  bonus for having both JP and EN views

Step 2: LLM viral scoring (optional, budget-guarded)
  Uses the judge LLM client (Gemini) to score the top VIRAL_PRESCORE_TOP_N
  candidates from Step 1 on four sub-dimensions:
    - curiosity_gap        (0-25)
    - stakeholder_impact   (0-25)
    - topic_affinity       (0-25)
    - discussion_potential (0-25)
  Total: 0-100.

Threshold gate:
  If viral_filter_score < VIRAL_SCORE_THRESHOLD:
    → se.why_rejected_before_generation is set
    → candidate is excluded from generation (judge + script + article)
  Threshold and sub-scores are visible in triage_scores.json and run_summary.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

from src.shared.logger import get_logger
from src.shared.models import ScoredEvent

if TYPE_CHECKING:
    from src.llm.base import LLMClient
    from src.budget import BudgetTracker

logger = get_logger(__name__)

# ── Config (overridable by caller / imported from shared.config) ──────────────
# Number of top Step-1 candidates sent to LLM for Step-2 scoring
VIRAL_PRESCORE_TOP_N: int = 20
# Minimum viral_filter_score to proceed to generation
VIRAL_SCORE_THRESHOLD: float = 40.0

# ── Prompt for Step-2 LLM scoring ─────────────────────────────────────────────
_VIRAL_SCORE_PROMPT = """\
あなたは日本語動画ニュースコンテンツの上級編集者です。
以下のニュース候補について、日本市場での視聴者エンゲージメント・拡散ポテンシャルを評価してください。

## 候補
タイトル: {title}
要約: {summary}
日本語視点: {japan_view}
海外視点: {global_view}

## 評価基準（各0〜25点）
- curiosity_gap: タイトル・内容が「もっと知りたい」という好奇心のギャップをどれだけ生み出すか
- stakeholder_impact: 視聴者の日常生活・家計・仕事・将来にどれだけ直接的に影響するか
- topic_affinity: 日本の視聴者がこのトピック（テーマ・登場人物・場所）をどれだけ強く気にかけているか
- discussion_potential: 感情的反応・友人との話題・SNSシェアをどれだけ引き起こしやすいか

## 出力
必ず以下のJSONのみを返してください。前置き・説明・コードブロックは不要です。

{{
  "curiosity_gap": <0-25の整数>,
  "stakeholder_impact": <0-25の整数>,
  "topic_affinity": <0-25の整数>,
  "discussion_potential": <0-25の整数>,
  "reason": "<なぜこのスコアか、50字以内>"
}}
"""

_MAX_VIEW_CHARS = 300  # Truncate long views to save tokens


def _prescore(se: ScoredEvent) -> tuple[float, dict]:
    """Step 1: Deterministic pre-score using existing editorial axis values.

    Returns (score_0_to_100, breakdown_dict).
    All inputs are already in se.score_breakdown from compute_score_full().
    """
    bd = se.score_breakdown
    jr   = bd.get("editorial:japan_relevance_score", 0.0)
    ijai = bd.get("editorial:indirect_japan_impact_score", 0.0)
    tg   = bd.get("editorial:tech_geopolitics_score", 0.0)
    be   = bd.get("editorial:big_event_score", 0.0)
    ma   = bd.get("editorial:mass_appeal_score", 0.0)
    jpa  = bd.get("editorial:japanese_person_abroad_score", 0.0)
    ja   = bd.get("editorial:japan_abroad_score", 0.0)
    bs   = bd.get("editorial:breaking_shock_score", 0.0)
    gd   = bd.get("editorial:geopolitics_depth_score", 0.0)
    pg   = bd.get("editorial:perspective_gap_score", 0.0)
    cg   = bd.get("editorial:coverage_gap_score", 0.0)
    has_jp = bd.get("editorial:has_jp_view", 0.0) > 0
    has_en = bd.get("editorial:has_en_view", 0.0) > 0

    # (a) Japan impact: direct relevance + indirect supply-chain / energy / FX exposure
    japan_impact = min(jr * 3.0 + ijai * 1.0, 40.0)

    # (b) Topic affinity: tech geopolitics, big economic events, sports/ent, Japan person
    topic_affinity = min(
        max(tg, be, ma) * 1.5 + max(jpa, ja) * 0.5,
        25.0,
    )

    # (c) Discussion trigger: breaking geopolitical / macro shocks
    discussion = min(max(bs, gd) * 2.0, 20.0)

    # (d) Contrast potential: how much JP vs global framing differs
    contrast = min(pg * 1.0 + cg * 0.5, 15.0)

    # (e) Both-language bonus: JP+EN sources available → comparative angle possible
    both_bonus = 3.0 if (has_jp and has_en) else 0.0

    raw = japan_impact + topic_affinity + discussion + contrast + both_bonus
    score = min(raw, 100.0)

    breakdown: dict = {
        "step": "prescore",
        "japan_impact": round(japan_impact, 2),
        "topic_affinity": round(topic_affinity, 2),
        "discussion_trigger": round(discussion, 2),
        "contrast_potential": round(contrast, 2),
        "both_lang_bonus": both_bonus,
        "raw_total": round(raw, 2),
    }
    return score, breakdown


def _llm_viral_score(
    se: ScoredEvent,
    llm_client: "LLMClient",
) -> tuple[float, dict]:
    """Step 2: LLM-based viral scoring.

    Returns (score_0_to_100, breakdown_with_sub_scores).
    On any failure, returns (-1.0, {"error": reason}) — caller uses prescore.
    """
    ev = se.event
    prompt = _VIRAL_SCORE_PROMPT.format(
        title=ev.title[:120],
        summary=ev.summary[:400],
        japan_view=(ev.japan_view or "")[:_MAX_VIEW_CHARS],
        global_view=(ev.global_view or "")[:_MAX_VIEW_CHARS],
    )
    try:
        raw_text = llm_client.generate(prompt)
        # Strip markdown fences if present
        text = raw_text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.split("```")[0].strip()

        data = json.loads(text)
        curiosity    = float(data.get("curiosity_gap", 0))
        stakeholder  = float(data.get("stakeholder_impact", 0))
        affinity     = float(data.get("topic_affinity", 0))
        discussion   = float(data.get("discussion_potential", 0))

        # Clamp sub-scores
        curiosity   = max(0.0, min(curiosity, 25.0))
        stakeholder = max(0.0, min(stakeholder, 25.0))
        affinity    = max(0.0, min(affinity, 25.0))
        discussion  = max(0.0, min(discussion, 25.0))

        total = curiosity + stakeholder + affinity + discussion
        breakdown: dict = {
            "step": "llm",
            "curiosity_gap": curiosity,
            "stakeholder_impact": stakeholder,
            "topic_affinity": affinity,
            "discussion_potential": discussion,
            "llm_reason": str(data.get("reason", ""))[:100],
        }
        return total, breakdown

    except json.JSONDecodeError as exc:
        return -1.0, {"step": "llm", "error": f"json_parse_error:{exc}"}
    except Exception as exc:
        msg = str(exc)
        err_type = "quota_exhausted" if ("429" in msg or "RESOURCE_EXHAUSTED" in msg) else "llm_error"
        return -1.0, {"step": "llm", "error": f"{err_type}:{msg[:80]}"}


def apply_viral_filter(
    all_ranked: list[ScoredEvent],
    budget: "BudgetTracker",
    *,
    llm_client: Optional["LLMClient"] = None,
    prescore_top_n: int = VIRAL_PRESCORE_TOP_N,
    score_threshold: float = VIRAL_SCORE_THRESHOLD,
    llm_enabled: bool = True,
) -> tuple[list[ScoredEvent], dict]:
    """Apply two-step viral filter to all candidates.

    Step 1 (deterministic) runs on every candidate.
    Step 2 (LLM) runs on the top prescore_top_n candidates if budget allows.

    Candidates below score_threshold have why_rejected_before_generation set.
    Candidates above threshold have why_rejected_before_generation = None.

    Returns:
        (all_ranked_with_scores, summary_dict)
        all_ranked_with_scores: same list, with viral scores populated in-place
        summary_dict: stats for run_summary
    """
    if not all_ranked:
        return all_ranked, {"viral_filter_applied": False, "reason": "no_candidates"}

    # ── Step 1: Prescore all candidates ──────────────────────────────────────
    for se in all_ranked:
        ps, ps_bd = _prescore(se)
        # Store in score_breakdown for downstream observability
        se.score_breakdown["viral_prescore"] = round(ps, 2)
        se.score_breakdown["viral_prescore_breakdown"] = ps_bd
        # Initialize viral_filter_score with prescore (may be overwritten by LLM)
        se.viral_filter_score = round(ps, 2)
        se.viral_filter_breakdown = dict(ps_bd)

    prescore_stats = {
        "min": round(min(se.viral_filter_score for se in all_ranked), 2),
        "max": round(max(se.viral_filter_score for se in all_ranked), 2),
        "mean": round(sum(se.viral_filter_score for se in all_ranked) / len(all_ranked), 2),
    }

    # ── Step 2: LLM scoring for top-N ────────────────────────────────────────
    llm_scored_count = 0
    llm_failed_count = 0
    llm_ran = False

    if llm_enabled and llm_client is not None:
        # Sort by prescore to find top N
        top_n_by_prescore = sorted(
            all_ranked, key=lambda x: x.viral_filter_score, reverse=True
        )[:prescore_top_n]

        for se in top_n_by_prescore:
            if not budget.can_afford_viral_filter():
                logger.info(
                    f"[ViralFilter] Budget exhausted after {llm_scored_count} LLM scores — "
                    "remaining candidates use prescore only."
                )
                break

            llm_ran = True
            llm_score, llm_bd = _llm_viral_score(se, llm_client)
            budget.record_call("viral_filter")

            if llm_score < 0:
                # LLM failed → keep prescore
                llm_failed_count += 1
                se.viral_filter_breakdown["llm_error"] = llm_bd.get("error", "unknown")
                logger.debug(
                    f"[ViralFilter] LLM failed for {se.event.id[:12]}: {llm_bd.get('error')}"
                )
            else:
                # LLM succeeded → replace with LLM score
                se.viral_filter_score = round(llm_score, 2)
                se.viral_filter_breakdown.update(llm_bd)
                se.score_breakdown["viral_filter_score_llm"] = round(llm_score, 2)
                se.score_breakdown["viral_filter_breakdown_llm"] = llm_bd
                llm_scored_count += 1
                logger.debug(
                    f"[ViralFilter] LLM score={llm_score:.1f} for {se.event.id[:12]} "
                    f"({se.event.title[:40]})"
                )

    # ── Threshold gate: mark rejected candidates ──────────────────────────────
    passed_count = 0
    rejected_count = 0

    for se in all_ranked:
        vfs = se.viral_filter_score
        # Store final score in breakdown for triage_scores.json visibility
        se.score_breakdown["viral_filter_score"] = round(vfs, 2)
        se.score_breakdown["viral_filter_breakdown"] = se.viral_filter_breakdown

        if vfs < score_threshold:
            reason = (
                f"viral_filter_score={vfs:.1f} < threshold={score_threshold:.0f}"
                f" [japan_impact={se.viral_filter_breakdown.get('japan_impact', 0):.1f},"
                f" topic_affinity={se.viral_filter_breakdown.get('topic_affinity', 0):.1f},"
                f" discussion={se.viral_filter_breakdown.get('discussion_trigger', 0):.1f},"
                f" contrast={se.viral_filter_breakdown.get('contrast_potential', 0):.1f}]"
            )
            se.why_rejected_before_generation = reason
            rejected_count += 1
            logger.debug(
                f"[ViralFilter] REJECTED {se.event.id[:12]} ({se.event.title[:40]}): {reason}"
            )
        else:
            se.why_rejected_before_generation = None
            passed_count += 1

    logger.info(
        f"[ViralFilter] Step1 prescore stats: min={prescore_stats['min']}, "
        f"max={prescore_stats['max']}, mean={prescore_stats['mean']} | "
        f"LLM scored={llm_scored_count} (failed={llm_failed_count}) | "
        f"Passed threshold ({score_threshold}): {passed_count}/{len(all_ranked)}"
    )

    summary: dict = {
        "viral_filter_applied": True,
        "threshold": score_threshold,
        "prescore_top_n": prescore_top_n,
        "llm_enabled": llm_enabled,
        "llm_ran": llm_ran,
        "llm_scored_count": llm_scored_count,
        "llm_failed_count": llm_failed_count,
        "total_candidates": len(all_ranked),
        "passed_threshold": passed_count,
        "rejected_before_generation": rejected_count,
        "prescore_stats": prescore_stats,
    }
    return all_ranked, summary


def build_why_slot1_won_editorially(se: ScoredEvent) -> str:
    """Construct a human-readable explanation of why slot-1 won editorially.

    Combines: editorial_reason + appraisal + viral_filter_score + judge result.
    """
    parts: list[str] = []

    # Editorial tier + axes
    if se.editorial_reason:
        parts.append(se.editorial_reason)

    # Appraisal
    if se.appraisal_type:
        parts.append(
            f"Appraisal: {se.appraisal_type} (score={se.editorial_appraisal_score:.1f})"
        )

    # Viral filter
    vfs = getattr(se, "viral_filter_score", None)
    if vfs is not None:
        parts.append(f"Viral: {vfs:.1f}/100")
        vfb = getattr(se, "viral_filter_breakdown", {}) or {}
        if vfb.get("step") == "llm":
            parts.append(
                f"[cg={vfb.get('curiosity_gap', 0):.0f} "
                f"si={vfb.get('stakeholder_impact', 0):.0f} "
                f"ta={vfb.get('topic_affinity', 0):.0f} "
                f"dp={vfb.get('discussion_potential', 0):.0f}]"
            )

    # Judge
    jr = se.judge_result
    if jr is not None and jr.judge_error is None:
        parts.append(
            f"Judge: {jr.publishability_class} "
            f"(div={jr.divergence_score:.1f}, blind_spot={jr.blind_spot_global_score:.1f})"
        )

    return " | ".join(parts) if parts else "N/A"
