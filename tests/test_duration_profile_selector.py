"""src/analysis/duration_profile_selector.py のテスト（LLM なし、ルールベース）。"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.analysis.duration_profile_selector import (
    PROFILE_ANTI_SONTAKU_90S,
    PROFILE_BREAKING_SHOCK_60S,
    PROFILE_CULTURAL_DIVIDE_100S,
    PROFILE_GEOPOLITICS_120S,
    PROFILE_MEDIA_CRITIQUE_80S,
    PROFILE_PARADIGM_SHIFT_100S,
    _is_breaking_news,
    generate_visual_mood_tags,
    select_duration_profile,
)
from src.shared.models import (
    ChannelConfig,
    Insight,
    MultiAngleAnalysis,
    NewsEvent,
    PerspectiveCandidate,
    ScoredEvent,
)


def _channel(profiles: list[str] = None) -> ChannelConfig:
    """テスト用 ChannelConfig（geo_lens の 6 プロファイル全部、または指定リスト）。"""
    if profiles is None:
        profiles = [
            PROFILE_BREAKING_SHOCK_60S,
            PROFILE_MEDIA_CRITIQUE_80S,
            PROFILE_ANTI_SONTAKU_90S,
            PROFILE_PARADIGM_SHIFT_100S,
            PROFILE_CULTURAL_DIVIDE_100S,
            PROFILE_GEOPOLITICS_120S,
        ]
    return ChannelConfig(
        channel_id="geo_lens",
        display_name="Geopolitical Lens",
        enabled=True,
        source_regions=["global"],
        perspective_axes=[
            "silence_gap",
            "framing_inversion",
            "hidden_stakes",
            "cultural_blindspot",
        ],
        duration_profiles=profiles,
        prompt_variant="geo_lens_v1",
        posts_per_day=3,
    )


def _perspective(axis: str) -> PerspectiveCandidate:
    return PerspectiveCandidate(axis=axis, score=8.0, reasoning="r", evidence_refs=[])


def _insights(n: int) -> list[Insight]:
    return [
        Insight(text=f"i{i}", importance=0.5 + i * 0.05, evidence_refs=[])
        for i in range(n)
    ]


def _ma(geopolitical: str = None) -> MultiAngleAnalysis:
    return MultiAngleAnalysis(geopolitical=geopolitical)


def _scored_event(*, breaking: bool = False, breaking_score: float = 0.0) -> ScoredEvent:
    ev = NewsEvent(
        id="evt-dur-1",
        title="t",
        summary="s",
        category="politics",
        source="Reuters",
        published_at=datetime.now(timezone.utc),
    )
    return ScoredEvent(
        event=ev,
        score=10.0,
        primary_bucket="breaking_shock" if breaking else "general",
        score_breakdown={"editorial:breaking_shock_score": breaking_score},
    )


# ---------- silence_gap ----------

def test_silence_gap_breaking_picks_60s():
    profile = select_duration_profile(
        _perspective("silence_gap"),
        _insights(3),
        _ma(),
        _channel(),
        scored_event=_scored_event(breaking=True),
    )
    assert profile == PROFILE_BREAKING_SHOCK_60S


def test_silence_gap_non_breaking_picks_anti_sontaku_90s():
    profile = select_duration_profile(
        _perspective("silence_gap"),
        _insights(3),
        _ma(),
        _channel(),
        scored_event=_scored_event(breaking=False),
    )
    assert profile == PROFILE_ANTI_SONTAKU_90S


def test_silence_gap_breaking_score_threshold():
    """primary_bucket が breaking_shock でなくても editorial:breaking_shock_score >= 2.0 で速報扱い。"""
    profile = select_duration_profile(
        _perspective("silence_gap"),
        _insights(3),
        _ma(),
        _channel(),
        scored_event=_scored_event(breaking=False, breaking_score=2.5),
    )
    assert profile == PROFILE_BREAKING_SHOCK_60S


def test_silence_gap_breaking_with_60s_disabled_falls_to_next():
    """breaking_shock_60s が ChannelConfig にない場合、次点 (media_critique_80s) を選ぶ。"""
    ch = _channel([PROFILE_MEDIA_CRITIQUE_80S, PROFILE_ANTI_SONTAKU_90S])
    profile = select_duration_profile(
        _perspective("silence_gap"),
        _insights(3),
        _ma(),
        ch,
        scored_event=_scored_event(breaking=True),
    )
    assert profile == PROFILE_MEDIA_CRITIQUE_80S


# ---------- framing_inversion ----------

def test_framing_inversion_picks_media_critique_80s():
    profile = select_duration_profile(
        _perspective("framing_inversion"),
        _insights(3),
        _ma(),
        _channel(),
    )
    assert profile == PROFILE_MEDIA_CRITIQUE_80S


def test_framing_inversion_with_80s_disabled_falls_back():
    ch = _channel([PROFILE_ANTI_SONTAKU_90S, PROFILE_PARADIGM_SHIFT_100S])
    profile = select_duration_profile(
        _perspective("framing_inversion"),
        _insights(3),
        _ma(),
        ch,
    )
    assert profile == PROFILE_ANTI_SONTAKU_90S


# ---------- hidden_stakes ----------

def test_hidden_stakes_with_geopolitical_picks_120s():
    profile = select_duration_profile(
        _perspective("hidden_stakes"),
        _insights(3),
        _ma(geopolitical="米中の構造的緊張..."),
        _channel(),
    )
    assert profile == PROFILE_GEOPOLITICS_120S


def test_hidden_stakes_without_geopolitical_picks_anti_sontaku_90s():
    profile = select_duration_profile(
        _perspective("hidden_stakes"),
        _insights(3),
        _ma(geopolitical=None),
        _channel(),
    )
    assert profile == PROFILE_ANTI_SONTAKU_90S


def test_hidden_stakes_with_geopolitics_disabled_falls_back():
    ch = _channel([PROFILE_ANTI_SONTAKU_90S, PROFILE_MEDIA_CRITIQUE_80S])
    profile = select_duration_profile(
        _perspective("hidden_stakes"),
        _insights(3),
        _ma(geopolitical="深い地政学..."),
        ch,
    )
    assert profile == PROFILE_ANTI_SONTAKU_90S


# ---------- cultural_blindspot ----------

def test_cultural_blindspot_low_insights_picks_cultural_divide_100s():
    profile = select_duration_profile(
        _perspective("cultural_blindspot"),
        _insights(3),
        _ma(),
        _channel(),
    )
    assert profile == PROFILE_CULTURAL_DIVIDE_100S


def test_cultural_blindspot_high_insights_picks_paradigm_shift_100s():
    profile = select_duration_profile(
        _perspective("cultural_blindspot"),
        _insights(4),
        _ma(),
        _channel(),
    )
    assert profile == PROFILE_PARADIGM_SHIFT_100S


def test_cultural_blindspot_high_insights_5plus_still_paradigm():
    profile = select_duration_profile(
        _perspective("cultural_blindspot"),
        _insights(5),
        _ma(),
        _channel(),
    )
    assert profile == PROFILE_PARADIGM_SHIFT_100S


def test_cultural_blindspot_high_with_paradigm_disabled_falls_back():
    ch = _channel([PROFILE_CULTURAL_DIVIDE_100S, PROFILE_ANTI_SONTAKU_90S])
    profile = select_duration_profile(
        _perspective("cultural_blindspot"),
        _insights(5),
        _ma(),
        ch,
    )
    assert profile == PROFILE_CULTURAL_DIVIDE_100S


# ---------- channel_config edge cases ----------

def test_empty_channel_profiles_returns_anti_sontaku_default():
    """ChannelConfig.duration_profiles が空（Phase 2 用 japan_athletes 等）でも壊れない。"""
    ch = _channel([])
    profile = select_duration_profile(
        _perspective("silence_gap"),
        _insights(3),
        _ma(),
        ch,
    )
    assert profile == PROFILE_ANTI_SONTAKU_90S


def test_channel_with_only_one_profile_always_returns_it():
    ch = _channel([PROFILE_BREAKING_SHOCK_60S])
    # framing_inversion でも 60s しか許されていなければそれを返す
    profile = select_duration_profile(
        _perspective("framing_inversion"),
        _insights(3),
        _ma(),
        ch,
    )
    assert profile == PROFILE_BREAKING_SHOCK_60S


def test_unknown_axis_falls_back_to_anti_sontaku():
    # axis 文字列が未知 → デフォルトは anti_sontaku_90s
    profile = select_duration_profile(
        _perspective("nonexistent_axis"),
        _insights(3),
        _ma(),
        _channel(),
    )
    assert profile == PROFILE_ANTI_SONTAKU_90S


# ---------- _is_breaking_news ----------

def test_is_breaking_none_returns_false():
    assert _is_breaking_news(None) is False


def test_is_breaking_primary_bucket_breaking_shock():
    assert _is_breaking_news(_scored_event(breaking=True)) is True


def test_is_breaking_low_score_returns_false():
    assert _is_breaking_news(_scored_event(breaking=False, breaking_score=1.5)) is False


def test_is_breaking_high_score_returns_true():
    assert _is_breaking_news(_scored_event(breaking=False, breaking_score=2.0)) is True


def test_is_breaking_invalid_score_returns_false():
    se = _scored_event(breaking=False)
    se.score_breakdown = {"editorial:breaking_shock_score": "not a number"}
    assert _is_breaking_news(se) is False


# ---------- generate_visual_mood_tags ----------

def test_visual_tags_silence_gap():
    tags = generate_visual_mood_tags(_perspective("silence_gap"))
    assert "void_imagery" in tags
    assert "silenced_media" in tags
    assert "spotlight_absence" in tags


def test_visual_tags_framing_inversion():
    tags = generate_visual_mood_tags(_perspective("framing_inversion"))
    assert tags == ["split_contrast", "mirror_opposition", "dual_perspective"]


def test_visual_tags_hidden_stakes():
    tags = generate_visual_mood_tags(_perspective("hidden_stakes"))
    assert tags == ["causal_chain", "domino_effect", "interconnected_systems"]


def test_visual_tags_cultural_blindspot():
    tags = generate_visual_mood_tags(_perspective("cultural_blindspot"))
    assert tags == ["cultural_icon_contrast", "civilizational_divide"]


def test_visual_tags_unknown_axis_returns_empty():
    tags = generate_visual_mood_tags(_perspective("unknown_axis"))
    assert tags == []


def test_visual_tags_returns_independent_list_each_call():
    """呼び出し側が mutate しても辞書が汚染されない。"""
    t1 = generate_visual_mood_tags(_perspective("silence_gap"))
    t1.append("custom_tag")
    t2 = generate_visual_mood_tags(_perspective("silence_gap"))
    assert "custom_tag" not in t2
