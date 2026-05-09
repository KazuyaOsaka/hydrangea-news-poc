"""F-jp-coverage-tune (2026-05-09): verify_two_stage() のユニットテスト。

二段階クエリ生成 + 系統 1/2/3/unknown 機械判別の検証。

テスト方針:
    - LLM クライアントはモック差し替え (実 API は呼ばない)
    - Grounding API もモック差し替え (実 API は呼ばない)
    - WL マッチングは既存実装を実際に呼ぶ
    - 既存 verify() の挙動には一切影響しないことを担保

設計書 (バッチプロンプト S2-1) で指定された 7 ケース:
    1. test_verify_two_stage_stream_1
    2. test_verify_two_stage_stream_2
    3. test_verify_two_stage_stream_3_candidate
    4. test_verify_two_stage_unknown_on_search_error
    5. test_verify_two_stage_skip_step2_when_step1_not_covered
    6. test_verify_two_stage_llm_query_fallback
    7. test_build_angle_query_format
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.triage.jp_coverage_verifier import (
    JpCoverageVerifier,
    TwoStageVerifyResult,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_chunk(domain: str) -> MagicMock:
    """Grounding chunk のモック (chunk.web.title にドメインを格納)。

    F-jp-coverage-improve で確立した仕様: Gemini Grounding API は実ソース
    ドメインを chunk.web.title に格納する。`_extract_domain_from_chunk` は
    これを正規化して返す。
    """
    chunk = MagicMock()
    chunk.web.domain = None  # SDK 現行版では domain は常に None
    chunk.web.title = domain
    chunk.web.uri = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/X"
    return chunk


def _make_grounding_response(domains: list[str]) -> MagicMock:
    """Grounding API response のモック (指定ドメインの chunk リスト)。"""
    response = MagicMock()
    response.candidates = [MagicMock()]
    response.candidates[0].grounding_metadata = MagicMock()
    response.candidates[0].grounding_metadata.grounding_chunks = [
        _make_chunk(d) for d in domains
    ]
    return response


def _make_verifier(
    *,
    grounding_responses: list[list[str]] | None = None,
    grounding_side_effect: Exception | None = None,
    db_path: Path | None = None,
) -> JpCoverageVerifier:
    """JpCoverageVerifier インスタンス + モック gemini_client を作る。

    grounding_responses を渡すと、generate_content の連続呼び出しごとに
    順番にドメインリストを返す。grounding_side_effect が指定されたら
    例外を発生させる。
    """
    gemini_client = MagicMock()
    if grounding_side_effect is not None:
        gemini_client.models.generate_content.side_effect = grounding_side_effect
    elif grounding_responses is not None:
        gemini_client.models.generate_content.side_effect = [
            _make_grounding_response(domains) for domains in grounding_responses
        ]
    if db_path is None:
        db_path = Path("/tmp/test_jp_coverage_two_stage.db")
    return JpCoverageVerifier(gemini_client=gemini_client, db_path=db_path)


def _candidate(title: str = "Test Event", summary: str = "Test summary") -> dict:
    return {"title": title, "summary": summary}


def _angle(core_question: str = "テストの特定角度") -> dict:
    return {"core_question": core_question}


# ── 1. stream_1_silence_gap (broad で WL ヒットなし) ─────────────────────


class TestVerifyTwoStageStream1:
    """広範事件で大手メディア WL ヒット 0 件 → stream_1_silence_gap。"""

    def test_verify_two_stage_stream_1(self) -> None:
        # Step 1 (broad) のみ呼ばれる、結果は WL 外ドメイン
        verifier = _make_verifier(grounding_responses=[["example.com", "globalvoices.org"]])

        result = verifier.verify_two_stage(
            candidate=_candidate(),
            particular_angle=_angle(),
            analysis_llm_client=MagicMock(generate=MagicMock(return_value="特定角度クエリ")),
        )

        assert isinstance(result, TwoStageVerifyResult)
        assert result.stream == "stream_1_silence_gap"
        assert result.broad_jp_coverage is False
        assert result.angle_jp_coverage is None
        assert result.angle_query is None  # Step 2 はスキップ
        assert result.angle_results is None
        assert result.error_message is None
        assert result.broad_matched_tier is None
        # angle_query 生成のための LLM 呼び出しもしないはず
        # (短絡: broad 未報道なら angle 生成自体スキップ)
        assert result.elapsed_seconds >= 0.0

    def test_stream_1_excluded_only(self) -> None:
        """除外ドメイン (Yahoo!ニュース等) のみの場合も WL ヒット 0 → stream_1。"""
        verifier = _make_verifier(grounding_responses=[["news.yahoo.co.jp", "huffingtonpost.jp"]])
        result = verifier.verify_two_stage(
            candidate=_candidate(),
            particular_angle=_angle(),
            analysis_llm_client=MagicMock(),
        )
        assert result.stream == "stream_1_silence_gap"
        assert result.excluded_count_broad == 2
        assert result.broad_jp_coverage is False


# ── 2. stream_2_perspective_gap (broad: 報道済み、angle: 未報道) ─────────


class TestVerifyTwoStageStream2:
    """広範事件で WL ヒットあり + 特定角度で WL ヒットなし → stream_2_perspective_gap。"""

    def test_verify_two_stage_stream_2(self) -> None:
        verifier = _make_verifier(grounding_responses=[
            ["nhk.or.jp", "asahi.com"],  # broad: WL ヒット (Tier 1)
            ["example.com", "foreign.org"],  # angle: WL ヒットなし
        ])
        analysis_client = MagicMock()
        analysis_client.generate.return_value = "イスラエル ラビ庁 非難 拒否 軍宗教融合"

        result = verifier.verify_two_stage(
            candidate=_candidate(title="Israel rabbinate refuses to condemn Jesus statue smash"),
            particular_angle=_angle(core_question="イスラエル最高宗教権威が兵士の聖像破壊非難を拒否した構造"),
            analysis_llm_client=analysis_client,
        )

        assert result.stream == "stream_2_perspective_gap"
        assert result.broad_jp_coverage is True
        assert result.angle_jp_coverage is False
        assert result.broad_matched_tier == "tier_1_newspaper"
        assert result.angle_matched_tier is None
        assert result.angle_query == "イスラエル ラビ庁 非難 拒否 軍宗教融合"
        assert "nhk.or.jp" in result.jp_media_hits_broad
        assert "asahi.com" in result.jp_media_hits_broad
        assert result.jp_media_hits_angle == []
        assert result.error_message is None
        assert result.angle_query_fallback_reason is None


# ── 3. stream_3_candidate (broad / angle 両方で WL ヒット) ──────────────


class TestVerifyTwoStageStream3Candidate:
    """両方で WL ヒット → stream_3_candidate (= F-stream-2-filter-design 行き)。"""

    def test_verify_two_stage_stream_3_candidate(self) -> None:
        verifier = _make_verifier(grounding_responses=[
            ["nhk.or.jp"],          # broad: Tier 1 ヒット
            ["nikkei.com", "jp.reuters.com"],  # angle: Tier 1 + Tier 2 ヒット
        ])
        analysis_client = MagicMock()
        analysis_client.generate.return_value = "テスト特定角度クエリ"

        result = verifier.verify_two_stage(
            candidate=_candidate(),
            particular_angle=_angle(),
            analysis_llm_client=analysis_client,
        )

        assert result.stream == "stream_3_candidate"
        assert result.broad_jp_coverage is True
        assert result.angle_jp_coverage is True
        assert result.broad_matched_tier == "tier_1_newspaper"
        assert result.angle_matched_tier == "tier_1_newspaper"
        assert "nikkei.com" in result.jp_media_hits_angle
        assert "jp.reuters.com" in result.jp_media_hits_angle
        assert result.error_message is None


# ── 4. unknown (検索 API 例外) ──────────────────────────────────────────


class TestVerifyTwoStageUnknownOnSearchError:
    """検索 API 例外 → graceful fallback で stream=unknown。"""

    def test_verify_two_stage_unknown_on_search_error(self) -> None:
        verifier = _make_verifier(grounding_side_effect=RuntimeError("503 UNAVAILABLE"))

        result = verifier.verify_two_stage(
            candidate=_candidate(),
            particular_angle=_angle(),
            analysis_llm_client=MagicMock(),
        )

        assert result.stream == "unknown"
        assert result.error_message is not None
        assert "broad_search_error" in result.error_message
        assert "503" in result.error_message or "RuntimeError" in result.error_message
        # broad 失敗時は angle へ進まない
        assert result.angle_query is None

    def test_unknown_on_angle_search_error(self) -> None:
        """broad は成功、angle で例外 → unknown (broad 結果は保持)。"""
        gemini_client = MagicMock()
        gemini_client.models.generate_content.side_effect = [
            _make_grounding_response(["nhk.or.jp"]),
            RuntimeError("angle search failed"),
        ]
        verifier = JpCoverageVerifier(
            gemini_client=gemini_client,
            db_path=Path("/tmp/test_jp_coverage_two_stage.db"),
        )

        result = verifier.verify_two_stage(
            candidate=_candidate(),
            particular_angle=_angle(),
            analysis_llm_client=MagicMock(generate=MagicMock(return_value="クエリ")),
        )

        assert result.stream == "unknown"
        assert "angle_search_error" in result.error_message
        # broad の結果は維持されている
        assert result.broad_jp_coverage is True
        assert "nhk.or.jp" in result.jp_media_hits_broad
        # angle_query も生成されている (失敗したのは angle の検索 API のみ)
        assert result.angle_query == "クエリ"


# ── 5. skip Step 2 when Step 1 is not covered ──────────────────────────


class TestVerifyTwoStageSkipStep2:
    """広範未報道時に Step 2 がスキップされる (= API コール削減)。"""

    def test_verify_two_stage_skip_step2_when_step1_not_covered(self) -> None:
        gemini_client = MagicMock()
        # broad だけ返す (angle は呼ばれないはず)
        gemini_client.models.generate_content.side_effect = [
            _make_grounding_response(["foreign.org"]),  # WL 外
        ]
        verifier = JpCoverageVerifier(
            gemini_client=gemini_client,
            db_path=Path("/tmp/test_jp_coverage_two_stage.db"),
        )
        analysis_client = MagicMock()

        result = verifier.verify_two_stage(
            candidate=_candidate(),
            particular_angle=_angle(),
            analysis_llm_client=analysis_client,
        )

        # 系統 1 確定
        assert result.stream == "stream_1_silence_gap"
        # generate_content は 1 回しか呼ばれない (= Step 2 スキップ)
        assert gemini_client.models.generate_content.call_count == 1
        # angle_query 生成 LLM も呼ばれていない
        assert analysis_client.generate.call_count == 0


# ── 6. LLM query fallback ──────────────────────────────────────────────


class TestVerifyTwoStageLlmQueryFallback:
    """LLM 角度クエリ生成失敗時にフォールバッククエリが使われる。"""

    def test_verify_two_stage_llm_query_fallback(self) -> None:
        # broad は WL ヒット → Step 2 へ進む
        # angle 検索もモックで返す (= フォールバックで何かしらの検索は実行される)
        verifier = _make_verifier(grounding_responses=[
            ["nhk.or.jp"],
            ["foreign.org"],  # angle WL ヒットなし
        ])
        # LLM 失敗
        analysis_client = MagicMock()
        analysis_client.generate.side_effect = RuntimeError("API 503 UNAVAILABLE")

        result = verifier.verify_two_stage(
            candidate=_candidate(title="Sample Title"),
            particular_angle=_angle(core_question="特定角度の核心的な問いを長めに書いて 20 文字超えにしておく"),
            analysis_llm_client=analysis_client,
        )

        # フォールバッククエリは title + core_question 先頭 20 文字
        assert result.stream == "stream_2_perspective_gap"
        assert result.angle_query_fallback_reason is not None
        assert "llm_error" in result.angle_query_fallback_reason
        assert result.angle_query is not None
        assert "Sample Title" in result.angle_query
        # core_question 先頭 20 文字を含む (= "特定角度の核心的な問いを長めに書いて 2")
        # (空白も 1 文字としてカウント、20 文字目で切り詰め)
        core_question = "特定角度の核心的な問いを長めに書いて 20 文字超えにしておく"
        assert result.angle_query.endswith(core_question[:20])

    def test_no_llm_client_uses_fallback(self) -> None:
        """analysis_llm_client=None かつ get_analysis_llm_client が None を返す場合
        も fallback。"""
        verifier = _make_verifier(grounding_responses=[
            ["nhk.or.jp"],
            ["foreign.org"],
        ])

        with patch(
            "src.llm.factory.get_analysis_llm_client",
            return_value=None,
        ):
            result = verifier.verify_two_stage(
                candidate=_candidate(title="X"),
                particular_angle=_angle(core_question="Y"),
                analysis_llm_client=None,
            )

        assert result.angle_query_fallback_reason == "no_llm_client"
        assert result.angle_query == "X Y"  # title + core_question 全部

    def test_no_core_question_uses_fallback(self) -> None:
        """particular_angle.core_question が空の場合は fallback (LLM 呼び出しスキップ)。"""
        verifier = _make_verifier(grounding_responses=[
            ["nhk.or.jp"],
            ["foreign.org"],
        ])
        analysis_client = MagicMock()

        result = verifier.verify_two_stage(
            candidate=_candidate(title="Some Title"),
            particular_angle={"core_question": ""},
            analysis_llm_client=analysis_client,
        )

        assert result.angle_query_fallback_reason == "no_core_question"
        # LLM は呼ばれない
        assert analysis_client.generate.call_count == 0
        # フォールバッククエリは title のみ (core_question 空)
        assert result.angle_query == "Some Title"


# ── 7. _build_angle_query format handling ──────────────────────────────


class TestBuildAngleQueryFormat:
    """LLM 出力フォーマットの正規化と異常検知。"""

    def test_build_angle_query_format_normal(self) -> None:
        """通常出力 (単一行クエリ) → そのまま返る。"""
        verifier = _make_verifier()
        client = MagicMock()
        client.generate.return_value = "イスラエル ラビ庁 非難拒否 軍宗教融合"

        query, reason = verifier._build_angle_query(
            candidate=_candidate(),
            particular_angle=_angle(),
            analysis_llm_client=client,
        )

        assert query == "イスラエル ラビ庁 非難拒否 軍宗教融合"
        assert reason is None

    def test_build_angle_query_strips_label_prefix(self) -> None:
        """LLM が「検索クエリ: xxx」形式で返した場合、ラベルを除去。"""
        verifier = _make_verifier()
        client = MagicMock()
        client.generate.return_value = "検索クエリ: テスト 検索 クエリ 例"

        query, reason = verifier._build_angle_query(
            candidate=_candidate(),
            particular_angle=_angle(),
            analysis_llm_client=client,
        )

        assert query == "テスト 検索 クエリ 例"
        assert reason is None

    def test_build_angle_query_takes_first_line_only(self) -> None:
        """複数行返された場合、最初の行のみ採用。"""
        verifier = _make_verifier()
        client = MagicMock()
        client.generate.return_value = "イスラエル ラビ庁 非難 拒否\n説明: これは...\n他にも..."

        query, reason = verifier._build_angle_query(
            candidate=_candidate(),
            particular_angle=_angle(),
            analysis_llm_client=client,
        )

        assert query == "イスラエル ラビ庁 非難 拒否"
        assert reason is None

    def test_build_angle_query_json_output_falls_back(self) -> None:
        """JSON 形式は bad_format で fallback。"""
        verifier = _make_verifier()
        client = MagicMock()
        client.generate.return_value = '{"query": "テスト"}'

        query, reason = verifier._build_angle_query(
            candidate=_candidate(title="T"),
            particular_angle=_angle(core_question="C" * 30),
            analysis_llm_client=client,
        )

        assert reason == "bad_format"
        assert query == "T " + "C" * 20  # fallback クエリ

    def test_build_angle_query_codeblock_falls_back(self) -> None:
        """コードブロック開始 (```) は bad_format で fallback。"""
        verifier = _make_verifier()
        client = MagicMock()
        client.generate.return_value = "```\nテストクエリ\n```"

        query, reason = verifier._build_angle_query(
            candidate=_candidate(title="X"),
            particular_angle=_angle(core_question="Y"),
            analysis_llm_client=client,
        )

        assert reason == "bad_format"

    def test_build_angle_query_empty_output_falls_back(self) -> None:
        """空文字 / 空白のみは bad_format で fallback。"""
        verifier = _make_verifier()
        client = MagicMock()
        client.generate.return_value = "   \n  "

        query, reason = verifier._build_angle_query(
            candidate=_candidate(title="X"),
            particular_angle=_angle(core_question="Y"),
            analysis_llm_client=client,
        )

        assert reason == "bad_format"

    def test_build_angle_query_quote_strip(self) -> None:
        """両端の引用符 / 角括弧は除去。"""
        verifier = _make_verifier()
        client = MagicMock()
        client.generate.return_value = "「テスト 検索 クエリ」"

        query, reason = verifier._build_angle_query(
            candidate=_candidate(),
            particular_angle=_angle(),
            analysis_llm_client=client,
        )

        assert query == "テスト 検索 クエリ"
        assert reason is None


# ── 既存 verify() の不変性確認 ────────────────────────────────────────────


class TestExistingVerifyUnchanged:
    """verify_two_stage の追加で既存 verify() が壊れていないこと。"""

    def test_existing_verify_signature_unchanged(self) -> None:
        """verify() のシグネチャが変わっていない (event_id, title, summary)。"""
        import inspect
        sig = inspect.signature(JpCoverageVerifier.verify)
        params = list(sig.parameters.keys())
        # self は含まれる
        assert params == ["self", "event_id", "title", "summary"]
        assert sig.parameters["summary"].default == ""

    def test_existing_verify_returns_jp_coverage_result(self) -> None:
        """verify() の戻り値型が JpCoverageResult のまま。"""
        from src.triage.jp_coverage_verifier import JpCoverageResult
        verifier = _make_verifier(grounding_responses=[["nhk.or.jp"]])
        # キャッシュバイパスのため一意の event_id
        result = verifier.verify(event_id="test_unchanged_unique_xyz", title="T", summary="S")
        assert isinstance(result, JpCoverageResult)
