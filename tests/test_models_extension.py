"""分析レイヤー導入で追加・拡張された Pydantic モデルのテスト。"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.shared.models import (
    AnalysisResult,
    Insight,
    MultiAngleAnalysis,
    NewsEvent,
    PerspectiveCandidate,
    RecencyRecord,
    ScoredEvent,
)


def _make_event() -> NewsEvent:
    return NewsEvent(
        id="evt-1",
        title="t",
        summary="s",
        category="economy",
        source="src",
        published_at=datetime.now(),
    )


def test_scored_event_default_channel_id_is_geo_lens():
    se = ScoredEvent(event=_make_event(), score=1.0)
    assert se.channel_id == "geo_lens"


def test_scored_event_analysis_result_defaults_none():
    se = ScoredEvent(event=_make_event(), score=1.0)
    assert se.analysis_result is None
    assert se.recency_guard_applied is False
    assert se.recency_overlap == []


def test_scored_event_existing_fields_unchanged():
    se = ScoredEvent(event=_make_event(), score=1.0)
    # 既存フィールドが破壊されていないこと
    assert se.score_breakdown == {}
    assert se.primary_tier == "Tier 3"
    assert se.editorial_tags == []
    assert se.from_recent_pool is False


def test_perspective_candidate_construction():
    p = PerspectiveCandidate(
        axis="silence_gap",
        score=8.5,
        reasoning="ok",
        evidence_refs=["http://a", "http://b"],
    )
    assert p.axis == "silence_gap"
    assert p.score == 8.5
    assert len(p.evidence_refs) == 2


def test_multi_angle_analysis_all_optional():
    m = MultiAngleAnalysis()
    assert m.geopolitical is None
    m2 = MultiAngleAnalysis(geopolitical="geo content")
    assert m2.geopolitical == "geo content"


def test_insight_construction():
    i = Insight(text="hello", importance=0.7, evidence_refs=["http://a"])
    assert i.text == "hello"
    assert i.importance == 0.7


def test_recency_record_serialization():
    rec = RecencyRecord(
        event_id="e1",
        channel_id="geo_lens",
        primary_entities=["trump"],
        primary_topics=["trade_war"],
        published_at="2026-04-25T00:00:00Z",
    )
    dumped = rec.model_dump()
    assert dumped["event_id"] == "e1"
    assert dumped["primary_entities"] == ["trump"]


def test_analysis_result_full_construction():
    p = PerspectiveCandidate(axis="silence_gap", score=9.0, reasoning="r", evidence_refs=[])
    result = AnalysisResult(
        event_id="e1",
        channel_id="geo_lens",
        selected_perspective=p,
        rejected_perspectives=[],
        perspective_verified=True,
        verification_notes="all good",
        multi_angle=MultiAngleAnalysis(geopolitical="x"),
        insights=[Insight(text="i1", importance=0.9, evidence_refs=[])],
        selected_duration_profile="breaking_shock_60s",
        generated_at="2026-04-25T00:00:00Z",
        llm_calls_used=3,
    )
    assert result.analysis_version == "v1.0"
    assert result.selected_duration_profile == "breaking_shock_60s"
    assert result.llm_calls_used == 3
    # 既存 ScoredEvent に組み込めることを確認
    se = ScoredEvent(event=_make_event(), score=1.0, analysis_result=result)
    assert se.analysis_result is not None
    assert se.analysis_result.event_id == "e1"


def test_analysis_result_round_trip_json():
    p = PerspectiveCandidate(axis="silence_gap", score=9.0, reasoning="r", evidence_refs=[])
    result = AnalysisResult(
        event_id="e1",
        channel_id="geo_lens",
        selected_perspective=p,
        perspective_verified=True,
        multi_angle=MultiAngleAnalysis(),
        selected_duration_profile="anti_sontaku_90s",
        generated_at="2026-04-25T00:00:00Z",
        llm_calls_used=2,
    )
    s = result.model_dump_json()
    rebuilt = AnalysisResult.model_validate_json(s)
    assert rebuilt.event_id == result.event_id
    assert rebuilt.selected_duration_profile == result.selected_duration_profile
