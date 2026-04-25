"""分析レイヤー Step 6 (Step 8 in instructions): 動画尺プロファイル選定。

設計書 Section 6.3 のロジックに従い、観点軸 × 洞察の量 × 分析の深さから
最適なプロファイル ID を 1 つ選ぶ。LLM 呼び出しは行わない。

ChannelConfig.duration_profiles に列挙されたプロファイルだけを候補にする。
プロファイルが空、または最終的に選ばれた候補が ChannelConfig に含まれない場合は
ChannelConfig.duration_profiles の先頭をフォールバックに使う（geo_lens では
breaking_shock_60s）。

加えて Section 15.1.2 のマッピングに従いビジュアルムードタグを生成する。
"""
from __future__ import annotations

from typing import Optional

from src.shared.logger import get_logger
from src.shared.models import (
    ChannelConfig,
    Insight,
    MultiAngleAnalysis,
    PerspectiveCandidate,
    ScoredEvent,
)

logger = get_logger(__name__)

# 設計書 Section 6.2 の 6 プロファイル ID。
PROFILE_BREAKING_SHOCK_60S = "breaking_shock_60s"
PROFILE_MEDIA_CRITIQUE_80S = "media_critique_80s"
PROFILE_ANTI_SONTAKU_90S = "anti_sontaku_90s"
PROFILE_PARADIGM_SHIFT_100S = "paradigm_shift_100s"
PROFILE_CULTURAL_DIVIDE_100S = "cultural_divide_100s"
PROFILE_GEOPOLITICS_120S = "geopolitics_120s"

# cultural_blindspot で paradigm_shift に振り替える insight 数の閾値。
_PARADIGM_SHIFT_INSIGHT_THRESHOLD = 4

# Section 15.1.2: 観点軸 → ビジュアルムードタグのマッピング。
_AXIS_TO_VISUAL_TAGS: dict[str, list[str]] = {
    "silence_gap": ["void_imagery", "silenced_media", "spotlight_absence"],
    "framing_inversion": ["split_contrast", "mirror_opposition", "dual_perspective"],
    "hidden_stakes": ["causal_chain", "domino_effect", "interconnected_systems"],
    "cultural_blindspot": ["cultural_icon_contrast", "civilizational_divide"],
}


def _is_breaking_news(scored_event: Optional[ScoredEvent]) -> bool:
    """ScoredEvent が「速報衝撃型」に該当するか判定する。

    既存パイプラインの ScoredEvent.primary_bucket == "breaking_shock" を一次シグナルに、
    score_breakdown["editorial:breaking_shock_score"] が高い場合（>=2.0）も拾う。
    ScoredEvent が渡されない場合（テスト等）は False。
    """
    if scored_event is None:
        return False
    if scored_event.primary_bucket == "breaking_shock":
        return True
    bd = scored_event.score_breakdown or {}
    bs_score = bd.get("editorial:breaking_shock_score", 0.0)
    try:
        return float(bs_score) >= 2.0
    except (TypeError, ValueError):
        return False


def _pick_first_allowed(
    candidates: list[str], allowed: list[str], fallback: str
) -> str:
    """candidates の先頭から allowed に含まれる最初のものを返す。

    一つも一致しなければ fallback を返す（fallback は allowed 内にある前提）。
    """
    allowed_set = set(allowed)
    for c in candidates:
        if c in allowed_set:
            return c
    return fallback


def select_duration_profile(
    perspective: PerspectiveCandidate,
    insights: list[Insight],
    multi_angle: MultiAngleAnalysis,
    channel_config: ChannelConfig,
    *,
    scored_event: Optional[ScoredEvent] = None,
) -> str:
    """観点軸 × 洞察の量 × 分析の深さから最適プロファイルを選定する。

    設計書 Section 6.3 のロジックに従う:

    - silence_gap + breaking → breaking_shock_60s
    - silence_gap (非 breaking) → anti_sontaku_90s（「忖度暴露」と同じ尺感）
    - framing_inversion → media_critique_80s
    - hidden_stakes + multi_angle.geopolitical あり → geopolitics_120s
    - hidden_stakes（地政学薄め）→ anti_sontaku_90s
    - cultural_blindspot + insights >= 4 → paradigm_shift_100s
    - cultural_blindspot → cultural_divide_100s
    - default → anti_sontaku_90s

    ChannelConfig.duration_profiles に含まれないプロファイルが選ばれた場合は、
    候補リストの順に許可されたものを探し、最終的に
    ChannelConfig.duration_profiles[0] にフォールバックする。
    """
    allowed = list(channel_config.duration_profiles or [])
    if not allowed:
        # ChannelConfig が空（japan_athletes など Phase 2 用の雛形）でも壊れない。
        return PROFILE_ANTI_SONTAKU_90S

    fallback = allowed[0]
    insights_count = len(insights)
    axis = perspective.axis

    # 軸別の優先順リストを構築（先頭から allowed にあるものを採用）。
    if axis == "silence_gap":
        if _is_breaking_news(scored_event):
            ranked = [
                PROFILE_BREAKING_SHOCK_60S,
                PROFILE_MEDIA_CRITIQUE_80S,
                PROFILE_ANTI_SONTAKU_90S,
            ]
        else:
            ranked = [
                PROFILE_ANTI_SONTAKU_90S,
                PROFILE_MEDIA_CRITIQUE_80S,
                PROFILE_BREAKING_SHOCK_60S,
            ]

    elif axis == "framing_inversion":
        ranked = [
            PROFILE_MEDIA_CRITIQUE_80S,
            PROFILE_ANTI_SONTAKU_90S,
            PROFILE_PARADIGM_SHIFT_100S,
        ]

    elif axis == "hidden_stakes":
        if multi_angle.geopolitical:
            ranked = [
                PROFILE_GEOPOLITICS_120S,
                PROFILE_ANTI_SONTAKU_90S,
                PROFILE_MEDIA_CRITIQUE_80S,
            ]
        else:
            ranked = [
                PROFILE_ANTI_SONTAKU_90S,
                PROFILE_GEOPOLITICS_120S,
                PROFILE_MEDIA_CRITIQUE_80S,
            ]

    elif axis == "cultural_blindspot":
        if insights_count >= _PARADIGM_SHIFT_INSIGHT_THRESHOLD:
            ranked = [
                PROFILE_PARADIGM_SHIFT_100S,
                PROFILE_CULTURAL_DIVIDE_100S,
                PROFILE_ANTI_SONTAKU_90S,
            ]
        else:
            ranked = [
                PROFILE_CULTURAL_DIVIDE_100S,
                PROFILE_PARADIGM_SHIFT_100S,
                PROFILE_ANTI_SONTAKU_90S,
            ]

    else:
        # 未知の軸（将来拡張）はデフォルトのみ。
        logger.info(
            f"[DurationProfileSelector] Unknown axis {axis!r}; "
            f"falling back to {PROFILE_ANTI_SONTAKU_90S}."
        )
        ranked = [PROFILE_ANTI_SONTAKU_90S]

    return _pick_first_allowed(ranked, allowed, fallback)


def generate_visual_mood_tags(perspective: PerspectiveCandidate) -> list[str]:
    """観点軸からビジュアル方針タグを生成する（Phase 2 以降の画像生成用）。

    設計書 Section 15.1.2 のマッピングに従う。未知の軸は空リスト。
    """
    return list(_AXIS_TO_VISUAL_TAGS.get(perspective.axis, []))
