"""F-5: GeminiJudge の publishability_class=investigate_more でも、
blind_spot/ijai が高ければ flagship 認定される。

Hydrangea のコンセプト「日本で報じられない海外ニュースを届ける」を
最終判定まで貫徹するため、divergence ベースだけで reject しない設計に変更。

試運転7-C (2026-04-28) で観測されたケース:
  cls-3165c4e2: class=investigate_more, blind_spot=7.0, ijai=9.0
  → 旧設計では reject されていた（動画化ゼロの真因）
  → F-5 で flagship 認定されるべき
"""
from __future__ import annotations

from datetime import datetime

from src.shared.models import GeminiJudgeResult, NewsEvent, ScoredEvent


def _make_scored_event_with_judge(
    *,
    publishability_class: str = "investigate_more",
    blind_spot: float = 7.0,
    ijai: float = 9.0,
    editorial_mission_score: float | None = 50.0,
    divergence: float = 0.0,
    judge_error: str | None = None,
) -> ScoredEvent:
    """F-5 テスト用のヘルパ。"""
    event = NewsEvent(
        id="cls-test123456",
        title="Test Iran Hormuz Strait Deal",
        summary="Strategic deal not covered by Japanese media.",
        category="politics",
        source="straitstimes",
        published_at=datetime(2026, 4, 28, 10, 0, 0),
        tags=[],
    )
    judge = GeminiJudgeResult(
        publishability_class=publishability_class,
        divergence_score=divergence,
        blind_spot_global_score=blind_spot,
        indirect_japan_impact_score_judge=ijai,
        authority_signal_score=5.0,
        confidence=0.7,
        requires_more_evidence=True,
        hard_claims_supported=False,
        judge_error=judge_error,
    )
    se = ScoredEvent(
        event=event,
        score=50.0,
        score_breakdown={},
        primary_tier="Tier 2",
        editorial_tags=[],
        primary_bucket="coverage_gap",
        judge_result=judge,
    )
    se.editorial_mission_score = editorial_mission_score
    return se


class TestF5FlagshipFallback:
    """F-5: investigate_more でも blind_spot/ijai 高ければ flagship 認定される。"""

    def test_high_blind_spot_qualifies_via_f5(self):
        """blind_spot=7.0 で flagship 認定される（試運転7-C cls-3165c4e2 ケース）。"""
        from src.main import _is_f5_flagship_eligible

        se = _make_scored_event_with_judge(
            publishability_class="investigate_more",
            blind_spot=7.0,
            ijai=9.0,
        )
        assert _is_f5_flagship_eligible(se) is True

    def test_high_ijai_alone_qualifies_via_f5(self):
        """blind_spot=2.0 でも ijai=8.0 なら flagship 認定される。"""
        from src.main import _is_f5_flagship_eligible

        se = _make_scored_event_with_judge(
            publishability_class="investigate_more",
            blind_spot=2.0,
            ijai=8.0,
        )
        assert _is_f5_flagship_eligible(se) is True

    def test_low_blind_spot_and_ijai_does_not_qualify(self):
        """blind_spot=2.0 / ijai=3.0 だと F-5 フォールバック発動しない。"""
        from src.main import _is_f5_flagship_eligible

        se = _make_scored_event_with_judge(
            publishability_class="investigate_more",
            blind_spot=2.0,
            ijai=3.0,
        )
        assert _is_f5_flagship_eligible(se) is False

    def test_editorial_mission_below_threshold_blocks_f5(self):
        """editorial_mission_score < 45.0 だと F-5 救済が発動しない。"""
        from src.main import _is_f5_flagship_eligible

        se = _make_scored_event_with_judge(
            publishability_class="investigate_more",
            blind_spot=8.0,
            ijai=9.0,
            editorial_mission_score=30.0,  # 閾値未満
        )
        assert _is_f5_flagship_eligible(se) is False

    def test_jp_only_class_does_not_qualify_via_f5(self):
        """publishability_class=jp_only は F-5 救済対象外。"""
        from src.main import _is_f5_flagship_eligible

        se = _make_scored_event_with_judge(
            publishability_class="jp_only",
            blind_spot=8.0,
            ijai=9.0,
        )
        assert _is_f5_flagship_eligible(se) is False

    def test_insufficient_evidence_qualifies_if_blind_spot_high(self):
        """publishability_class=insufficient_evidence でも blind_spot 高ければ救済。"""
        from src.main import _is_f5_flagship_eligible

        se = _make_scored_event_with_judge(
            publishability_class="insufficient_evidence",
            blind_spot=7.0,
            ijai=4.0,
        )
        assert _is_f5_flagship_eligible(se) is True


class TestF5FallbackEdgeCases:
    """F-5 のエッジケース確認 (helper への入力 robustness)。"""

    def test_judge_error_blocks_f5(self):
        """judge_error が非 None の場合は F-5 救済対象外（信頼できない判定）。"""
        from src.main import _is_f5_flagship_eligible

        se = _make_scored_event_with_judge(
            publishability_class="investigate_more",
            blind_spot=8.0,
            ijai=9.0,
            judge_error="parse_error",
        )
        assert _is_f5_flagship_eligible(se) is False

    def test_no_judge_result_blocks_f5(self):
        """judge_result が None の場合は F-5 救済対象外。"""
        from src.main import _is_f5_flagship_eligible

        se = _make_scored_event_with_judge(
            publishability_class="investigate_more",
            blind_spot=8.0,
            ijai=9.0,
        )
        se.judge_result = None
        assert _is_f5_flagship_eligible(se) is False

    def test_editorial_mission_none_blocks_f5(self):
        """editorial_mission_score が None の場合は F-5 救済対象外（filter 未適用扱い）。"""
        from src.main import _is_f5_flagship_eligible

        se = _make_scored_event_with_judge(
            publishability_class="investigate_more",
            blind_spot=8.0,
            ijai=9.0,
            editorial_mission_score=None,
        )
        assert _is_f5_flagship_eligible(se) is False

    def test_linked_jp_global_not_processed_by_f5(self):
        """publishability_class=linked_jp_global は F-5 経路を通らない（primary 経路で eligible）。"""
        from src.main import _is_f5_flagship_eligible

        se = _make_scored_event_with_judge(
            publishability_class="linked_jp_global",
            blind_spot=8.0,
            ijai=9.0,
        )
        # primary path で eligible になるため、F-5 helper は False を返す（対象外）
        assert _is_f5_flagship_eligible(se) is False


class TestF5IntegrationWithFinalSelection:
    """F-5 が _find_eligible_judged_slot1 経由で動作することを統合確認。"""

    def test_f5_candidate_selected_when_no_primary_eligible(self):
        """primary 経路で eligible 候補がない場合、F-5 候補が選ばれる。"""
        from src.main import _find_eligible_judged_slot1

        f5_candidate = _make_scored_event_with_judge(
            publishability_class="investigate_more",
            blind_spot=7.0,
            ijai=9.0,
            editorial_mission_score=50.0,
        )
        # judge_results dict（呼び出し側が non-empty を要件としているため）
        judge_results = {f5_candidate.event.id: f5_candidate.judge_result}

        selected, reason = _find_eligible_judged_slot1([f5_candidate], judge_results)
        assert selected is not None
        assert selected.event.id == f5_candidate.event.id
        assert "f5" in reason  # F-5 経路を通った事実が reason に含まれる

    def test_no_f5_candidate_returns_block_reason(self):
        """F-5 閾値も満たさない candidate しかなければ no_eligible_judged_flagship を返す。"""
        from src.main import _find_eligible_judged_slot1

        candidate = _make_scored_event_with_judge(
            publishability_class="investigate_more",
            blind_spot=2.0,
            ijai=3.0,
            editorial_mission_score=50.0,
        )
        judge_results = {candidate.event.id: candidate.judge_result}

        selected, reason = _find_eligible_judged_slot1([candidate], judge_results)
        assert selected is None
        assert reason == "no_eligible_judged_flagship"
