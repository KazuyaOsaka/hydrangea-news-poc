"""F-2 で導入した EditorialMissionFilter 通過 → flagship 認定ロジックを検証する。
"""
from datetime import datetime

import pytest

from src.shared.models import NewsEvent, ScoredEvent, SourceRef
from src.triage.scheduler import _passes_flagship_gate


def _make_scored_event(
    *,
    title: str = "Test Event",
    editorial_mission_score: float | None = None,
    score_breakdown: dict | None = None,
    sources_en: list | None = None,
) -> ScoredEvent:
    """テスト用の ScoredEvent を作成する。"""
    en_refs: list[SourceRef] = []
    if sources_en:
        for s in sources_en:
            if isinstance(s, SourceRef):
                en_refs.append(s)
            else:
                en_refs.append(
                    SourceRef(
                        name=s.get("name", "TestSource"),
                        url=s.get("url", "https://example.com/article"),
                        title=s.get("title"),
                        language=s.get("language", "en"),
                        country=s.get("country", "US"),
                        region=s.get("region", "global"),
                    )
                )
    event = NewsEvent(
        id="evt-test",
        title=title,
        summary="test summary",
        category="politics",
        source="test",
        published_at=datetime(2026, 4, 14, 10, 0, 0),
        sources_en=en_refs,
    )
    se = ScoredEvent(
        event=event,
        score=50.0,
        score_breakdown=score_breakdown or {},
    )
    if editorial_mission_score is not None:
        se.editorial_mission_score = editorial_mission_score
    return se


class TestFlagshipGateEditorialMissionRoute:
    """F-2: EditorialMissionFilter 通過なら flagship 認定されるルートのテスト。"""

    def test_editorial_mission_score_above_threshold_passes(self):
        """editorial_mission_score >= 45.0 で flagship 認定されることを確認。"""
        se = _make_scored_event(
            editorial_mission_score=45.0,
            score_breakdown={
                "editorial:japan_relevance_score": 0.0,
                "editorial:indirect_japan_impact_score": 0.0,
            },
            sources_en=[{"name": "TestSource"}],
        )
        passes, reason = _passes_flagship_gate(se)
        assert passes is True
        assert "flagship_editorial_mission" in reason
        assert "score=45.0" in reason

    def test_editorial_mission_score_high_passes(self):
        """editorial_mission_score=80.0 で flagship 認定。"""
        se = _make_scored_event(
            editorial_mission_score=80.0,
            score_breakdown={
                "editorial:japan_relevance_score": 0.0,
                "editorial:indirect_japan_impact_score": 0.0,
            },
            sources_en=[{"name": "TestSource"}],
        )
        passes, reason = _passes_flagship_gate(se)
        assert passes is True
        assert "score=80.0" in reason

    def test_editorial_mission_score_below_threshold_blocked(self):
        """editorial_mission_score < 45.0 は既存ロジックで判定（落ちるはず）。"""
        se = _make_scored_event(
            editorial_mission_score=30.0,
            score_breakdown={
                "editorial:japan_relevance_score": 0.0,
                "editorial:indirect_japan_impact_score": 0.0,
                "editorial:perspective_gap_score": 0.0,
                "editorial:global_attention_score": 0.0,
                "editorial:background_inference_potential": 0.0,
            },
            sources_en=[{"name": "TestSource"}],
        )
        passes, reason = _passes_flagship_gate(se)
        assert passes is False
        # 既存の weak_japan or no_depth or below_flagship のいずれかになる
        assert "flagship_editorial_mission" not in reason

    def test_editorial_mission_score_none_falls_to_existing_logic(self):
        """editorial_mission_score=None（フィルタ未適用）は既存ロジックで判定。"""
        se = _make_scored_event(
            editorial_mission_score=None,
            score_breakdown={
                "editorial:japan_relevance_score": 0.0,
                "editorial:indirect_japan_impact_score": 0.0,
                "editorial:perspective_gap_score": 0.0,
                "editorial:global_attention_score": 0.0,
                "editorial:background_inference_potential": 0.0,
            },
            sources_en=[{"name": "TestSource"}],
        )
        passes, reason = _passes_flagship_gate(se)
        # 既存 flagship_class 判定で落ちるはず（軸が全部 0 なので）
        assert passes is False
        assert "flagship_editorial_mission" not in reason

    def test_existing_flagship_class_takes_precedence(self):
        """既存の flagship_class 判定が成立するなら、そちらが優先される。"""
        # flagship_macro_paradigm 条件を満たす（pg>=6, ga>=6）
        se = _make_scored_event(
            editorial_mission_score=50.0,  # これでも flagship 通過するが
            score_breakdown={
                "editorial:perspective_gap_score": 7.0,
                "editorial:global_attention_score": 7.0,  # macro_paradigm 条件成立
                "editorial:japan_relevance_score": 0.0,
                "editorial:indirect_japan_impact_score": 0.0,
                "editorial:background_inference_potential": 5.0,
            },
            sources_en=[{"name": "TestSource"}],
        )
        passes, reason = _passes_flagship_gate(se)
        assert passes is True
        # 既存ロジックの flagship_macro_paradigm が優先される（順序: get_flagship_class → editorial_mission）
        assert "flagship_macro_paradigm" in reason
