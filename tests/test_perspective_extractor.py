"""src/analysis/perspective_extractor.py のテスト（ルールベース、LLM 不要）。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pytest

from src.analysis.perspective_extractor import (
    _calculate_cultural_blindspot_score,
    _calculate_framing_inversion_score,
    _calculate_hidden_stakes_score,
    _calculate_silence_gap_score,
    _meets_cultural_blindspot_conditions,
    _meets_framing_inversion_conditions,
    _meets_hidden_stakes_conditions,
    _meets_silence_gap_conditions,
    extract_perspectives,
)
from src.shared.models import (
    ChannelConfig,
    NewsEvent,
    PerspectiveCandidate,
    ScoredEvent,
    SourceRef,
)


# ---------- helpers ----------

def _en_sources(n: int) -> list[SourceRef]:
    return [
        SourceRef(name=f"S{i}", url=f"https://en.example.com/{i}", region="global")
        for i in range(n)
    ]


def _jp_sources(n: int) -> list[SourceRef]:
    return [
        SourceRef(name=f"J{i}", url=f"https://jp.example.com/{i}", region="japan",
                  language="ja", country="JP")
        for i in range(n)
    ]


def _scored(
    *,
    title: str = "",
    summary: str = "",
    sources_jp: int = 0,
    sources_en: int = 0,
    breakdown: Optional[dict] = None,
    background: Optional[str] = None,
    impact_on_japan: Optional[str] = None,
    japan_view: Optional[str] = None,
    tags: Optional[list[str]] = None,
    editorial_tags: Optional[list[str]] = None,
) -> ScoredEvent:
    ev = NewsEvent(
        id="evt-1",
        title=title,
        summary=summary,
        category="politics",
        source="Reuters",
        published_at=datetime.now(timezone.utc),
        sources_jp=_jp_sources(sources_jp),
        sources_en=_en_sources(sources_en),
        background=background,
        impact_on_japan=impact_on_japan,
        japan_view=japan_view,
        tags=tags or [],
    )
    return ScoredEvent(
        event=ev,
        score=10.0,
        score_breakdown=breakdown or {},
        editorial_tags=editorial_tags or [],
    )


# ---------- silence_gap ----------

def test_silence_gap_meets_when_all_conditions_satisfied():
    se = _scored(
        sources_en=3,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is True


def test_silence_gap_fails_when_jp_sources_present():
    se = _scored(
        sources_en=3,
        sources_jp=1,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is False


def test_silence_gap_fails_when_too_few_en_sources():
    se = _scored(
        sources_en=2,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is False


def test_silence_gap_fails_when_global_attention_low():
    se = _scored(
        sources_en=3,
        sources_jp=0,
        breakdown={"global_attention_score": 3.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is False


def test_silence_gap_score_is_clamped_to_10():
    se = _scored(
        sources_en=10,
        sources_jp=0,
        breakdown={"global_attention_score": 10.0, "indirect_japan_impact_score": 10.0},
    )
    score, _ = _calculate_silence_gap_score(se)
    assert score == 10.0


def test_silence_gap_score_jp_penalty_drives_below_zero_clamped_to_zero():
    se = _scored(
        sources_en=1,
        sources_jp=5,
        breakdown={"global_attention_score": 0.0, "indirect_japan_impact_score": 0.0},
    )
    score, _ = _calculate_silence_gap_score(se)
    assert score == 0.0


# ---------- framing_inversion ----------

def test_framing_inversion_meets_when_jp_and_en_present_and_pg_high():
    se = _scored(
        sources_en=2,
        sources_jp=1,
        breakdown={"perspective_gap_score": 7.0},
    )
    assert _meets_framing_inversion_conditions(se) is True


def test_framing_inversion_fails_when_no_jp_source():
    se = _scored(sources_en=3, sources_jp=0, breakdown={"perspective_gap_score": 8.0})
    assert _meets_framing_inversion_conditions(se) is False


def test_framing_inversion_score_includes_en_count_bonus():
    se = _scored(
        sources_en=4,
        sources_jp=1,
        breakdown={"perspective_gap_score": 6.0},
    )
    score, reason = _calculate_framing_inversion_score(se)
    # 6 + 4*0.5 = 8
    assert score == pytest.approx(8.0)
    assert "perspective_gap" in reason


# ---------- hidden_stakes ----------

def test_hidden_stakes_meets_when_impact_high_and_kw_present():
    se = _scored(
        title="TSMC fab decision affects Toyota supply chain",
        breakdown={"indirect_japan_impact_score": 6.0},
    )
    assert _meets_hidden_stakes_conditions(se) is True


def test_hidden_stakes_fails_without_japan_industry_keyword():
    se = _scored(
        title="Eurozone monetary policy review",
        breakdown={"indirect_japan_impact_score": 6.0},
    )
    assert _meets_hidden_stakes_conditions(se) is False


def test_hidden_stakes_score_includes_impact_unmentioned_bonus():
    """JP ソースありで impact_on_japan が空 → +2 ボーナス。"""
    se = _scored(
        title="Toyota faces new chip restrictions",
        sources_jp=1,
        breakdown={"indirect_japan_impact_score": 5.0},
    )
    score, reason = _calculate_hidden_stakes_score(se)
    # 5.0 (impact) + 1 (Toyota) + 2.0 (unmentioned) = 8.0
    assert score == pytest.approx(8.0)
    assert "impact_unmentioned_bonus=2.0" in reason


def test_hidden_stakes_no_unmentioned_bonus_when_no_jp_sources():
    se = _scored(
        title="Toyota faces new chip restrictions",
        sources_jp=0,
        breakdown={"indirect_japan_impact_score": 5.0},
    )
    score, _ = _calculate_hidden_stakes_score(se)
    # 5 + 1 + 0 = 6
    assert score == pytest.approx(6.0)


# ---------- cultural_blindspot ----------

def test_cultural_blindspot_meets_with_cultural_signals():
    se = _scored(
        title="Saudi religious tradition complicates new reform",
        summary="The monarchy's role under Islamic tradition is changing",
        breakdown={"geopolitics_depth_score": 5.0},
    )
    assert _meets_cultural_blindspot_conditions(se) is True


def test_cultural_blindspot_fails_without_signals():
    se = _scored(title="Stock market closes flat", summary="")
    assert _meets_cultural_blindspot_conditions(se) is False


def test_cultural_blindspot_score_clamped():
    se = _scored(
        title="religion tradition monarchy ritual caste gender feminism",
        editorial_tags=["religion", "tradition"],
        breakdown={"geopolitics_depth_score": 10.0},
    )
    score, _ = _calculate_cultural_blindspot_score(se)
    assert score <= 10.0


# ---------- extract_perspectives ----------

def test_extract_returns_only_viable_axes():
    se = _scored(
        sources_en=3,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    candidates = extract_perspectives(se)
    axes = {c.axis for c in candidates}
    assert "silence_gap" in axes
    # framing_inversion は jp source が 0 なので除外
    assert "framing_inversion" not in axes


def test_extract_sorted_by_score_descending():
    se = _scored(
        title="Toyota chip restrictions trade war religion tradition",
        sources_en=4,
        sources_jp=1,
        breakdown={
            "global_attention_score": 7.0,
            "indirect_japan_impact_score": 5.0,
            "perspective_gap_score": 7.0,
            "geopolitics_depth_score": 6.0,
        },
    )
    candidates = extract_perspectives(se)
    scores = [c.score for c in candidates]
    assert scores == sorted(scores, reverse=True)


def test_extract_filters_by_channel_config_perspective_axes():
    se = _scored(
        sources_en=3,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    cfg = ChannelConfig(
        channel_id="restricted",
        display_name="Restricted",
        enabled=True,
        source_regions=["global"],
        perspective_axes=["framing_inversion"],
        duration_profiles=["breaking_shock_60s"],
        prompt_variant="r_v1",
        posts_per_day=1,
    )
    candidates = extract_perspectives(se, channel_config=cfg)
    axes = {c.axis for c in candidates}
    assert "silence_gap" not in axes  # 軸が許可リストに含まれない


def test_extract_geo_lens_allows_all_four_axes():
    se = _scored(
        title="Toyota chip restrictions amid Saudi religion tradition",
        sources_en=3,
        sources_jp=1,
        breakdown={
            "global_attention_score": 7.0,
            "indirect_japan_impact_score": 6.0,
            "perspective_gap_score": 7.0,
            "geopolitics_depth_score": 5.0,
        },
    )
    cfg = ChannelConfig.load("geo_lens")
    candidates = extract_perspectives(se, channel_config=cfg)
    # 4軸の少なくとも複数が成立しうる
    axes = {c.axis for c in candidates}
    assert axes.issubset(
        {"silence_gap", "framing_inversion", "hidden_stakes", "cultural_blindspot"}
    )


def test_extract_returns_empty_when_no_axis_meets_conditions():
    se = _scored(title="Local news", summary="A small town story")
    candidates = extract_perspectives(se)
    assert candidates == []


def test_perspective_candidate_has_evidence_refs():
    se = _scored(
        sources_en=3,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    candidates = extract_perspectives(se)
    sg = next(c for c in candidates if c.axis == "silence_gap")
    assert all(ref.startswith("https://") for ref in sg.evidence_refs)
    assert len(sg.evidence_refs) == 3


def test_perspective_candidate_pydantic_model_returned():
    se = _scored(
        sources_en=3,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    candidates = extract_perspectives(se)
    assert all(isinstance(c, PerspectiveCandidate) for c in candidates)
