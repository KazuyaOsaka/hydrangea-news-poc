"""F-15: AnalysisLayer 対象選定を Top-3 台本生成ループと一致させる構造的解決のテスト。

試運転 7-H' (2026-04-29 21:20) で動画化率 1/3 (33%) で頭打ちになる構造的問題が発覚した:
- AnalysisLayer 対象選定: `all_ranked` のスコア降順 (Tier 1 score)
- Top-3 台本生成対象選定: `_elite_judge_results` の total_score 降順
両者の Top-3 は偶然 1 件しか一致せず、一致しない Slot は
「analysis_result is None, skipping」で skip されていた。

F-15 では AnalysisLayer の対象選定を Top-3 台本生成ループと完全一致させる。
本テストはその選定ロジックの不変性を担保する。
"""
from __future__ import annotations

import inspect
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.llm.schemas import EditorScore
from src.shared.models import NewsEvent, ScoredEvent


def _make_event(event_id: str, title: str = "title") -> NewsEvent:
    return NewsEvent(
        id=event_id,
        title=title,
        summary="summary",
        category="general",
        source="test",
        published_at=datetime.now(timezone.utc),
    )


def _make_scored(event_id: str, score: float) -> ScoredEvent:
    return ScoredEvent(event=_make_event(event_id), score=score)


def _make_editor_score(total: int) -> EditorScore:
    """`total` を 5 軸に均等分配して total_score を満たす EditorScore を作る。"""
    base = total // 5
    rem = total - base * 5
    parts = [base] * 5
    parts[0] += rem
    parts = [max(0, min(10, p)) for p in parts]
    actual_total = sum(parts)
    return EditorScore(
        score_anti_sontaku=parts[0],
        score_multipolar=parts[1],
        score_outside_in=parts[2],
        score_insight=parts[3],
        score_fandom_fast=parts[4],
        total_score=actual_total,
        editor_comment="test",
    )


def _select_analysis_targets(
    all_ranked: list[ScoredEvent],
    elite_judge_results: dict[str, EditorScore],
    top_n: int,
) -> list[ScoredEvent]:
    """src/main.py F-15 修正後の AnalysisLayer 対象選定ロジックを再現。

    実コードと同一の sort key / reverse / slice を使う。実装が変わったら
    ここも更新する必要があるが、test_main_f15_source_alignment で本物の
    main.py から該当行が抜けていないことも検証する。
    """
    return sorted(
        all_ranked,
        key=lambda se: (
            elite_judge_results[se.event.id].total_score
            if se.event.id in elite_judge_results
            else 0
        ),
        reverse=True,
    )[:top_n]


def _select_top_3_candidates(
    all_ranked: list[ScoredEvent],
    elite_judge_results: dict[str, EditorScore],
    top_n: int,
) -> list[ScoredEvent]:
    """src/main.py の Top-3 台本生成対象選定ロジックを再現 (F-4 以来不変)。"""
    return sorted(
        all_ranked,
        key=lambda se: (
            elite_judge_results[se.event.id].total_score
            if se.event.id in elite_judge_results
            else 0
        ),
        reverse=True,
    )[:top_n]


class TestF15AnalysisTargetsByEliteJudge:
    """F-15: AnalysisLayer 対象が Elite Judge total_score 順になる。"""

    def test_targets_sorted_by_elite_judge_total_score(self):
        """all_ranked のスコア順と Elite Judge total_score 順が異なる場合、
        AnalysisLayer 対象は Elite Judge total_score 順になる。"""
        # all_ranked は Tier 1 score 降順 (試運転7-H' を再現)
        ranked = [
            _make_scored("cls-A", score=0.95),  # Tier 1 高、Elite Judge 低
            _make_scored("cls-B", score=0.90),
            _make_scored("cls-C", score=0.85),
            _make_scored("cls-D", score=0.80),
            _make_scored("cls-E", score=0.75),  # Tier 1 低、Elite Judge 高
        ]
        # Elite Judge は逆順に高得点
        elite = {
            "cls-A": _make_editor_score(15),
            "cls-B": _make_editor_score(20),
            "cls-C": _make_editor_score(25),
            "cls-D": _make_editor_score(30),
            "cls-E": _make_editor_score(40),
        }

        targets = _select_analysis_targets(ranked, elite, top_n=3)
        target_ids = [t.event.id for t in targets]

        # Elite Judge 上位 3 件 = E (40), D (30), C (25)
        assert target_ids == ["cls-E", "cls-D", "cls-C"], (
            f"Expected Elite Judge 順での Top-3 だが {target_ids} になった"
        )

    def test_events_missing_from_elite_judge_treated_as_zero(self):
        """_elite_judge_results に含まれない event は score=0 として末尾扱い。"""
        ranked = [
            _make_scored("cls-A", score=0.95),
            _make_scored("cls-B", score=0.90),  # Elite Judge 結果なし
            _make_scored("cls-C", score=0.85),
            _make_scored("cls-D", score=0.80),  # Elite Judge 結果なし
            _make_scored("cls-E", score=0.75),
        ]
        # B, D は含めない
        elite = {
            "cls-A": _make_editor_score(20),
            "cls-C": _make_editor_score(30),
            "cls-E": _make_editor_score(25),
        }

        targets = _select_analysis_targets(ranked, elite, top_n=3)
        target_ids = [t.event.id for t in targets]

        # 評価あり 3 件 (C=30, E=25, A=20) が選ばれ、B/D は含まれない
        assert target_ids == ["cls-C", "cls-E", "cls-A"], (
            f"Elite Judge 結果なしの event が選ばれてしまった: {target_ids}"
        )
        assert "cls-B" not in target_ids
        assert "cls-D" not in target_ids

    def test_all_events_missing_from_elite_judge_falls_back_to_stable_order(self):
        """全 event が Elite Judge 結果なしの場合、score=0 で安定ソート (元順序維持)。"""
        ranked = [
            _make_scored("cls-X", score=0.99),
            _make_scored("cls-Y", score=0.50),
            _make_scored("cls-Z", score=0.10),
        ]
        elite: dict[str, EditorScore] = {}

        targets = _select_analysis_targets(ranked, elite, top_n=3)
        target_ids = [t.event.id for t in targets]

        # 全件 score=0 → Python の sorted は安定ソートなので入力順を維持
        assert target_ids == ["cls-X", "cls-Y", "cls-Z"]


class TestF15AlignmentWithTop3GenerationLoop:
    """F-15: AnalysisLayer 対象と Top-3 台本生成対象が完全一致する (核心)。"""

    def test_targets_match_top3_candidates_exactly(self):
        """同じ all_ranked と _elite_judge_results に対し、両者の Top-3 が完全一致。

        F-15 の核心。Slot-event_id ズレを構造的に防ぐ不変条件。
        """
        # 試運転 7-H' に類似した分布: Tier 1 score と Elite Judge total_score が
        # 中程度に相関するが完全には一致しない。
        ranked = [
            _make_scored("cls-a382cd94530b", score=0.95),  # 試運転7-H' Slot-1
            _make_scored("cls-4045a389ba04", score=0.90),  # 試運転7-H' Slot-2 (★)
            _make_scored("cls-579833967531", score=0.85),  # 試運転7-H' Slot-3
            _make_scored("cls-469b65c3a9cc", score=0.80),
            _make_scored("cls-95d122984fa8", score=0.75),
        ]
        elite = {
            "cls-a382cd94530b": _make_editor_score(28),  # Top-3 台本生成 1 位
            "cls-4045a389ba04": _make_editor_score(30),  # Top-3 台本生成 2 位 → 一致
            "cls-579833967531": _make_editor_score(26),  # Top-3 台本生成 3 位
            "cls-469b65c3a9cc": _make_editor_score(20),
            "cls-95d122984fa8": _make_editor_score(15),
        }

        analysis_targets = _select_analysis_targets(ranked, elite, top_n=3)
        top3_candidates = _select_top_3_candidates(ranked, elite, top_n=3)

        analysis_ids = [t.event.id for t in analysis_targets]
        top3_ids = [c.event.id for c in top3_candidates]

        assert analysis_ids == top3_ids, (
            f"F-15 不変条件違反: AnalysisLayer 対象と Top-3 台本生成対象が一致しない\n"
            f"  AnalysisLayer: {analysis_ids}\n"
            f"  Top-3 generation: {top3_ids}"
        )

    def test_alignment_holds_under_random_distributions(self):
        """様々な (Tier 1 score, Elite Judge total_score) 分布で常に一致する。"""
        import random
        random.seed(42)

        for _trial in range(20):
            n_events = random.randint(3, 12)
            ranked = [
                _make_scored(f"cls-{i:03d}", score=random.random())
                for i in range(n_events)
            ]
            # Tier 1 score 降順にしておく (all_ranked の規約)
            ranked.sort(key=lambda se: se.score, reverse=True)

            # Elite Judge: 一部欠損あり
            elite = {}
            for se in ranked:
                if random.random() < 0.85:
                    elite[se.event.id] = _make_editor_score(random.randint(0, 50))

            top_n = random.randint(1, min(5, n_events))
            a_ids = [t.event.id for t in _select_analysis_targets(ranked, elite, top_n)]
            t_ids = [c.event.id for c in _select_top_3_candidates(ranked, elite, top_n)]
            assert a_ids == t_ids, (
                f"trial で不一致: analysis={a_ids} top3={t_ids}"
            )


class TestF15TopNEnvControl:
    """F-15: TOP_N_GENERATION env 変数で対象件数が変わる。"""

    def test_top_n_default_is_3(self, monkeypatch):
        monkeypatch.delenv("TOP_N_GENERATION", raising=False)
        n = max(1, int(os.getenv("TOP_N_GENERATION", "3")))
        assert n == 3

    def test_top_n_2_yields_2_targets(self):
        ranked = [_make_scored(f"cls-{i}", score=1.0 - i * 0.1) for i in range(5)]
        elite = {se.event.id: _make_editor_score(50 - i * 5) for i, se in enumerate(ranked)}

        targets = _select_analysis_targets(ranked, elite, top_n=2)
        assert len(targets) == 2

    def test_top_n_3_yields_3_targets(self):
        ranked = [_make_scored(f"cls-{i}", score=1.0 - i * 0.1) for i in range(5)]
        elite = {se.event.id: _make_editor_score(50 - i * 5) for i, se in enumerate(ranked)}

        targets = _select_analysis_targets(ranked, elite, top_n=3)
        assert len(targets) == 3

    def test_top_n_larger_than_ranked_returns_all(self):
        """all_ranked の件数より大きい top_n を指定しても、全件数で止まる。"""
        ranked = [_make_scored(f"cls-{i}", score=1.0 - i * 0.1) for i in range(2)]
        elite = {se.event.id: _make_editor_score(20) for se in ranked}

        targets = _select_analysis_targets(ranked, elite, top_n=10)
        assert len(targets) == 2


class TestF15SourceAlignment:
    """F-15: src/main.py 本体に Elite Judge total_score sort のロジックが
    実在することを検証する (テストヘルパだけ正しく実コードが旧実装、を防ぐ)。"""

    def test_main_py_uses_elite_judge_total_score_for_analysis_targets(self):
        """src/main.py の AnalysisLayer 対象選定が Elite Judge total_score 順 sort を
        使っていることを inspect で確認。"""
        from src import main as main_mod
        source = inspect.getsource(main_mod)

        # F-15 のマーカー: ログメッセージと sort パターンの両方を確認
        assert "F-15: aligned with Top-3 generation loop" in source, (
            "F-15 のログメッセージが main.py に見つからない"
        )

        # _analysis_targets が sorted(...) ベースで構築されていること
        assert "_analysis_targets = sorted(" in source, (
            "F-15 修正後は _analysis_targets が sorted で構築されているはず"
        )

        # all_ranked[:_top_n_for_analysis] という旧パターンが残っていない
        assert "_analysis_targets = all_ranked[:_top_n_for_analysis]" not in source, (
            "F-15 修正前の旧パターンが残存している"
        )

    def test_main_py_preserves_per_slot_try_except(self):
        """F-4 で導入された per-slot try/except が F-15 でも維持されている。"""
        from src import main as main_mod
        source = inspect.getsource(main_mod)

        # F-4 の構造マーカー
        assert "[AnalysisLayer] Slot-" in source, (
            "F-4 で導入された Slot 単位ログが消失している"
        )
        assert "for _idx, _target in enumerate(_analysis_targets)" in source, (
            "F-4 で導入された per-slot ループが消失している"
        )
