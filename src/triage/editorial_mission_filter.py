"""editorial_mission_filter.py — Hydrangea Editorial Mission Filter (two-step pre-generation gate)

Pass C — runs after Editorial Appraisal, before the Gemini Judge pass.

Purpose:
  「日本市場でバズるニュース」を選ぶ旧 ViralFilter を全面置換した、
  Hydrangea の編集ミッション (= 日本で報じられないニュース、視点が偏った
  ニュースを地政学・歴史・文化・政治・経済的背景の解説付きで日本人に届ける)
  への適合度を 7 軸で評価するフィルタ。

Step 1: Cheap deterministic pre-score (no LLM, always runs)
  Uses editorial axes already computed in score_breakdown by triage/scoring.py.
  7 axes (each capped, sum capped at 100):
    - perspective_gap          (0-25): 日本 vs 海外の報道フレーム差
    - geopolitical_significance (0-20): 地政学・歴史的潮流への影響
    - blindspot_severity       (0-15): 日本では報じられていない / 軽視されている度合い
    - political_intent         (0-10): 政治的意図の読み解き余地（Step1 では粗い近似）
    - hidden_power_dynamics    (0-10): 力関係の不可視性（Step1 では粗い近似）
    - economic_interests       (0-10): 経済的利害の解説余地
    - discussion_potential     (0-10): 議論誘発力

Step 2: LLM mission scoring (optional, budget-guarded)
  Top MISSION_PRESCORE_TOP_N candidates are re-scored by the judge LLM
  using the 7-axis prompt (see _MISSION_SCORE_PROMPT below). LLM スコアが
  成功した場合のみ prescore を上書きする。

Threshold gate:
  If editorial_mission_score < MISSION_SCORE_THRESHOLD:
    → se.why_rejected_before_generation is set
    → candidate is excluded from generation (judge + script + article)
  Threshold and sub-scores are visible in triage_scores.json and run_summary.

設計詳細は docs/EDITORIAL_MISSION_FILTER_DESIGN.md を参照。
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
MISSION_PRESCORE_TOP_N: int = 20
# Minimum editorial_mission_score to proceed to generation (暫定値)
MISSION_SCORE_THRESHOLD: float = 45.0

_MAX_VIEW_CHARS = 300  # Truncate long views to save tokens

# ── Prompt for Step-2 LLM scoring ─────────────────────────────────────────────
_MISSION_SCORE_PROMPT = """\
あなたは独立メディア「Hydrangea」の編集長です。
Hydrangea のミッションは「日本で報じられないニュース、視点が偏ったニュースを、地政学・歴史・文化・政治・経済的背景の解説付きで日本人に届ける」ことです。

以下のニュース候補について、Hydrangea の編集ミッションへの適合度を7軸で評価してください。

## 候補
タイトル: {title}
要約: {summary}
日本語視点: {japan_view}
海外視点: {global_view}

## 評価軸（各軸の最高点を厳格に守ること）

1. perspective_gap (0-25点) — 視点ギャップ
   日本メディアと海外メディアの間で、報道フレーム・解釈・強調点がどれだけ違うか。
   - 日本では「経済問題」、海外では「人権問題」と報じられる → 高得点
   - 同じ事実を異なる文脈で語る差 → 高得点
   - 単に翻訳されてないだけ → 低得点

2. geopolitical_significance (0-20点) — 地政学・歴史的重要性
   この出来事が国際秩序・大国関係・歴史的潮流にどれだけ影響するか。
   - BRICS拡大・米中半導体戦争・中央アジアの再編 → 高得点
   - 局地的な事件・国内ゴシップ → 低得点

3. blindspot_severity (0-15点) — ブラインドスポット
   日本では報じられていない、または不当に小さく扱われている度合い。
   - 海外で1面トップ、日本で記事すら見当たらない → 最高得点
   - 海外多数報道、日本は通信社配信のみ → 高得点
   - 日本でも普通に報じられている → 低得点

4. political_intent (0-10点) — 政治的意図
   この報道・出来事の裏にある政治的・経済的・組織的意図を読み解く価値。
   - 「中国脅威論」の裏にある軍事予算狙い、特定派閥の動き → 高得点
   - スキャンダル報道のタイミングの不自然さ → 高得点
   - 純粋な事実報道で意図が見えない → 低得点

5. hidden_power_dynamics (0-10点) — 力関係の不可視性
   表に出ていない権力構造・利害関係・癒着を解説する価値。
   - エネルギー会社と政治家の関係、メディアとスポンサーの利害 → 高得点
   - 業界団体・財団・諮問機関の影響力 → 高得点
   - 表面的な事実のみで構造が見えない → 低得点

6. economic_interests (0-10点) — 経済的利害
   この出来事の裏で、誰がどう経済的に得失するかを解説する価値。
   - 政策決定の裏にある業界ロビーの動き → 高得点
   - 制裁・規制の真の受益者・被害者 → 高得点
   - 企業合併・買収の戦略的意図 → 高得点
   - 単純な株価動向 → 低得点

7. discussion_potential (0-10点) — 議論誘発力
   日本人視聴者の価値観や常識を揺さぶり、議論を呼ぶ力。
   - 「自分の生活に直結」「常識が覆る」「感情的反応」 → 高得点
   - 専門的すぎて一般視聴者に響かない → 低得点

## 重要な指示

- 「日本人がバズらせるか」ではなく「日本人に届けるべきか」で評価する
- 派手さ・感情的扇動ではなく、知的に重要かどうか
- 陰謀論ではなく、事実に基づいた構造的解説の余地があるか
- ReHacQ・東洋経済レベルの知的水準を基準にする

## 出力

以下のJSONのみを返してください。前置き・コードブロック・説明文不要。

{{
  "perspective_gap": <0-25の整数>,
  "geopolitical_significance": <0-20の整数>,
  "blindspot_severity": <0-15の整数>,
  "political_intent": <0-10の整数>,
  "hidden_power_dynamics": <0-10の整数>,
  "economic_interests": <0-10の整数>,
  "discussion_potential": <0-10の整数>,
  "reason": "<このスコアの根拠を80字以内で>"
}}
"""


# ── Step 1: Deterministic prescore using existing editorial axes ──────────────

def _editorial_mission_prescore(se: ScoredEvent) -> tuple[float, dict]:
    """Step 1: 既存 score_breakdown 上の editorial axes から 7 軸スコアを近似計算する。

    Returns (score_0_to_100, breakdown_dict)。

    political_intent / hidden_power_dynamics / economic_interests は scoring.py が
    直接の axis を持たないため Step1 では粗い近似のみ行う（Step2 LLM が主体評価）。
    """
    bd = se.score_breakdown

    pg   = bd.get("editorial:perspective_gap_score", 0.0)
    cg   = bd.get("editorial:coverage_gap_score", 0.0)
    gd   = bd.get("editorial:geopolitics_depth_score", 0.0)
    bs   = bd.get("editorial:breaking_shock_score", 0.0)
    tg   = bd.get("editorial:tech_geopolitics_score", 0.0)
    be   = bd.get("editorial:big_event_score", 0.0)
    ma   = bd.get("editorial:mass_appeal_score", 0.0)
    ijai = bd.get("editorial:indirect_japan_impact_score", 0.0)
    has_jp = bd.get("editorial:has_jp_view", 0.0) > 0
    has_en = bd.get("editorial:has_en_view", 0.0) > 0

    # ソース数（ブラインドスポット計算用）
    en_count = len(se.event.sources_by_locale.get("en", []))
    jp_count = len(se.event.sources_by_locale.get("jp", []))

    # 軸1: 視点ギャップ (25点) — 最重要
    perspective_gap = min(pg * 1.5 + cg * 1.0, 25.0)

    # 軸2: 地政学・歴史的重要性 (20点)
    geopolitical = min(gd * 2.0 + bs * 1.0, 20.0)

    # 軸3: ブラインドスポット (15点)
    # 「日本で報じられず、海外で大きく扱われている」度合い
    if has_en and not has_jp:
        blindspot = 15.0
    elif en_count >= 3 and jp_count <= 1:
        blindspot = 12.0
    elif en_count >= 2 and jp_count == 0:
        blindspot = 10.0
    elif en_count >= 2 and jp_count <= 1:
        blindspot = 8.0
    else:
        blindspot = 0.0

    # 軸4: 政治的意図 (10点) — Step1 では粗い近似
    # 既存 axis に直接対応するものがないため、geopolitics + breaking で近似
    political_intent = min(gd * 1.0 + bs * 0.5, 10.0)

    # 軸5: 力関係の不可視性 (10点) — Step1 では粗い近似
    # tech_geopolitics（半導体・経済安保等の構造的話題）と相関
    hidden_power = min(tg * 1.2 + gd * 0.3, 10.0)

    # 軸6: 経済的利害 (10点)
    # big_event（金融政策・大型M&A等）と indirect_japan_impact で近似
    economic_interests = min(be * 1.0 + ijai * 0.3, 10.0)

    # 軸7: 議論誘発力 (10点)
    # mass_appeal（大衆関心）と breaking_shock の組み合わせ
    discussion = min(ma * 0.7 + bs * 0.5, 10.0)

    raw = (
        perspective_gap
        + geopolitical
        + blindspot
        + political_intent
        + hidden_power
        + economic_interests
        + discussion
    )
    score = min(raw, 100.0)

    breakdown: dict = {
        "step": "prescore",
        "perspective_gap": round(perspective_gap, 2),
        "geopolitical_significance": round(geopolitical, 2),
        "blindspot_severity": round(blindspot, 2),
        "political_intent": round(political_intent, 2),
        "hidden_power_dynamics": round(hidden_power, 2),
        "economic_interests": round(economic_interests, 2),
        "discussion_potential": round(discussion, 2),
        "raw_total": round(raw, 2),
    }
    return score, breakdown


# ── Step 2: LLM mission scoring ───────────────────────────────────────────────

def _llm_mission_score(
    se: ScoredEvent,
    llm_client: "LLMClient",
) -> tuple[float, dict]:
    """Step 2: LLM ベースの 7 軸スコアリング。

    Returns (score_0_to_100, breakdown_with_sub_scores)。
    失敗時は (-1.0, {"error": reason}) を返し、呼び出し側は prescore を保持する。
    """
    ev = se.event
    prompt = _MISSION_SCORE_PROMPT.format(
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
        perspective_gap   = float(data.get("perspective_gap", 0))
        geopolitical      = float(data.get("geopolitical_significance", 0))
        blindspot         = float(data.get("blindspot_severity", 0))
        political_intent  = float(data.get("political_intent", 0))
        hidden_power      = float(data.get("hidden_power_dynamics", 0))
        economic_interests = float(data.get("economic_interests", 0))
        discussion        = float(data.get("discussion_potential", 0))

        # Clamp sub-scores to per-axis maxima
        perspective_gap    = max(0.0, min(perspective_gap,    25.0))
        geopolitical       = max(0.0, min(geopolitical,       20.0))
        blindspot          = max(0.0, min(blindspot,          15.0))
        political_intent   = max(0.0, min(political_intent,   10.0))
        hidden_power       = max(0.0, min(hidden_power,       10.0))
        economic_interests = max(0.0, min(economic_interests, 10.0))
        discussion         = max(0.0, min(discussion,         10.0))

        total = (
            perspective_gap
            + geopolitical
            + blindspot
            + political_intent
            + hidden_power
            + economic_interests
            + discussion
        )
        breakdown: dict = {
            "step": "llm",
            "perspective_gap": perspective_gap,
            "geopolitical_significance": geopolitical,
            "blindspot_severity": blindspot,
            "political_intent": political_intent,
            "hidden_power_dynamics": hidden_power,
            "economic_interests": economic_interests,
            "discussion_potential": discussion,
            "llm_reason": str(data.get("reason", ""))[:120],
        }
        return total, breakdown

    except json.JSONDecodeError as exc:
        return -1.0, {"step": "llm", "error": f"json_parse_error:{exc}"}
    except Exception as exc:
        msg = str(exc)
        err_type = "quota_exhausted" if ("429" in msg or "RESOURCE_EXHAUSTED" in msg) else "llm_error"
        return -1.0, {"step": "llm", "error": f"{err_type}:{msg[:80]}"}


# ── Main entry point ──────────────────────────────────────────────────────────

def apply_editorial_mission_filter(
    all_ranked: list[ScoredEvent],
    budget: "BudgetTracker",
    *,
    llm_client: Optional["LLMClient"] = None,
    prescore_top_n: int = MISSION_PRESCORE_TOP_N,
    score_threshold: float = MISSION_SCORE_THRESHOLD,
    llm_enabled: bool = True,
) -> tuple[list[ScoredEvent], dict]:
    """全候補に 2 段階の Editorial Mission Filter を適用する。

    Step 1 (deterministic) は全候補に対して必ず実行する。
    Step 2 (LLM) は予算が許せば prescore 上位 prescore_top_n 件に対して実行する。

    score_threshold 未満の候補には why_rejected_before_generation を設定し、
    生成パイプライン (judge + script + article) から除外する。

    Returns:
        (all_ranked_with_scores, summary_dict)
        all_ranked_with_scores: 入力リストと同じ参照（in-place 更新）
        summary_dict: run_summary 用の集計値
    """
    if not all_ranked:
        return all_ranked, {
            "editorial_mission_filter_applied": False,
            "reason": "no_candidates",
        }

    # ── Step 1: Prescore all candidates ──────────────────────────────────────
    for se in all_ranked:
        ps, ps_bd = _editorial_mission_prescore(se)
        # Store in score_breakdown for downstream observability
        se.score_breakdown["mission_prescore"] = round(ps, 2)
        se.score_breakdown["mission_prescore_breakdown"] = ps_bd
        # Initialize editorial_mission_score with prescore (may be overwritten by LLM)
        se.editorial_mission_score = round(ps, 2)
        se.editorial_mission_breakdown = dict(ps_bd)

    prescore_stats = {
        "min": round(min(se.editorial_mission_score for se in all_ranked), 2),
        "max": round(max(se.editorial_mission_score for se in all_ranked), 2),
        "mean": round(
            sum(se.editorial_mission_score for se in all_ranked) / len(all_ranked), 2
        ),
    }

    # ── Step 2: LLM scoring for top-N ────────────────────────────────────────
    llm_scored_count = 0
    llm_failed_count = 0
    llm_ran = False

    if llm_enabled and llm_client is not None:
        # Sort by prescore to find top N
        top_n_by_prescore = sorted(
            all_ranked, key=lambda x: x.editorial_mission_score, reverse=True
        )[:prescore_top_n]

        for se in top_n_by_prescore:
            if not budget.can_afford_editorial_mission_filter():
                logger.info(
                    f"[EditorialMissionFilter] Budget exhausted after {llm_scored_count} LLM scores — "
                    "remaining candidates use prescore only."
                )
                break

            llm_ran = True
            llm_score, llm_bd = _llm_mission_score(se, llm_client)
            budget.record_call("editorial_mission_filter")

            if llm_score < 0:
                # LLM failed → keep prescore
                llm_failed_count += 1
                se.editorial_mission_breakdown["llm_error"] = llm_bd.get("error", "unknown")
                logger.debug(
                    f"[EditorialMissionFilter] LLM failed for {se.event.id[:12]}: {llm_bd.get('error')}"
                )
            else:
                # LLM succeeded → replace with LLM score
                se.editorial_mission_score = round(llm_score, 2)
                se.editorial_mission_breakdown.update(llm_bd)
                se.score_breakdown["editorial_mission_score_llm"] = round(llm_score, 2)
                se.score_breakdown["editorial_mission_breakdown_llm"] = llm_bd
                llm_scored_count += 1
                logger.debug(
                    f"[EditorialMissionFilter] LLM score={llm_score:.1f} for {se.event.id[:12]} "
                    f"({se.event.title[:40]})"
                )

    # ── Threshold gate: mark rejected candidates ──────────────────────────────
    passed_count = 0
    rejected_count = 0

    for se in all_ranked:
        ems = se.editorial_mission_score
        # Store final score in breakdown for triage_scores.json visibility
        se.score_breakdown["editorial_mission_score"] = round(ems, 2)
        se.score_breakdown["editorial_mission_breakdown"] = se.editorial_mission_breakdown

        if ems < score_threshold:
            bd = se.editorial_mission_breakdown
            reason = (
                f"editorial_mission_score={ems:.1f} < threshold={score_threshold:.1f}"
                f" [perspective_gap={bd.get('perspective_gap', 0):.1f},"
                f" geopolitical={bd.get('geopolitical_significance', 0):.1f},"
                f" blindspot={bd.get('blindspot_severity', 0):.1f},"
                f" discussion={bd.get('discussion_potential', 0):.1f}]"
            )
            se.why_rejected_before_generation = reason
            rejected_count += 1
            logger.debug(
                f"[EditorialMissionFilter] REJECTED {se.event.id[:12]} "
                f"({se.event.title[:40]}): {reason}"
            )
        else:
            se.why_rejected_before_generation = None
            passed_count += 1

    logger.info(
        f"[EditorialMissionFilter] Step1 prescore stats: min={prescore_stats['min']}, "
        f"max={prescore_stats['max']}, mean={prescore_stats['mean']} | "
        f"LLM scored={llm_scored_count} (failed={llm_failed_count}) | "
        f"Passed threshold ({score_threshold}): {passed_count}/{len(all_ranked)}"
    )

    summary: dict = {
        "editorial_mission_filter_applied": True,
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
    """slot-1 が編集的に選ばれた理由を人間可読な 1 行で構築する。

    Combines: editorial_reason + appraisal + editorial_mission_score + judge result.
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

    # Editorial mission filter
    ems = getattr(se, "editorial_mission_score", None)
    if ems is not None:
        parts.append(f"Mission: {ems:.1f}/100")
        emb = getattr(se, "editorial_mission_breakdown", {}) or {}
        if emb.get("step") == "llm":
            parts.append(
                f"[pg={emb.get('perspective_gap', 0):.0f} "
                f"geo={emb.get('geopolitical_significance', 0):.0f} "
                f"blind={emb.get('blindspot_severity', 0):.0f} "
                f"disc={emb.get('discussion_potential', 0):.0f}]"
            )

    # Judge
    jr = se.judge_result
    if jr is not None and jr.judge_error is None:
        parts.append(
            f"Judge: {jr.publishability_class} "
            f"(div={jr.divergence_score:.1f}, blind_spot={jr.blind_spot_global_score:.1f})"
        )

    return " | ".join(parts) if parts else "N/A"
