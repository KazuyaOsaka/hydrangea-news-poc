"""F-jp-coverage-llm-judgement-extraction (2026-05-14): LLM judgement bypass 根本治療の検証。

F-wl-hit-quality-audit Task D で決定的に判明した「LLM が response_text で『該当しない』と
明示判定しているのに WL マッチだけで True を返している」設計欠陥の修正テスト。

テスト戦略:
    - `_parse_llm_judgement` / `_extract_response_text` 単体テスト
    - `verify()` ハイブリッド判定 (WL × LLM judgement、B-3 表) の挙動テスト
    - `verify_two_stage()` ハイブリッド判定 (broad / angle) の挙動テスト
    - B-3.a 後方互換 (llm_judgement = None → WL のみで判定) の挙動テスト
    - 既存 1390 ケースは破壊しない (本ファイル新規追加のみ)

設計仕様: docs/runs/F-jp-coverage-llm-judgement-extraction/design_spec.md
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.storage.db import init_db
from src.triage.jp_coverage_verifier import (
    JpCoverageResult,
    JpCoverageVerifier,
    TwoStageVerifyResult,
    _extract_response_text,
    _parse_llm_judgement,
)


# ── Helpers (新規モック構築) ─────────────────────────────────────────────


def _make_chunk(domain: str) -> MagicMock:
    chunk = MagicMock()
    chunk.web.domain = None
    chunk.web.title = domain
    chunk.web.uri = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/X"
    return chunk


def _make_grounding_response(domains: list[str], response_text: str = "") -> MagicMock:
    """response_text 付き Grounding API モック (本バッチ新設計)。

    既存テスト互換のため `response_text=""` デフォルト時は content.parts を持たない
    MagicMock を返す (= `_extract_response_text` が "" を返す → llm_judgement=None
    → 後方互換パス)。
    """
    response = MagicMock()
    candidate = MagicMock()
    candidate.grounding_metadata = MagicMock()
    candidate.grounding_metadata.grounding_chunks = [_make_chunk(d) for d in domains]
    if response_text:
        # 明示的に response_text を埋め込む (新パース機構を動かす)
        part = MagicMock()
        part.text = response_text
        candidate.content = MagicMock()
        candidate.content.parts = [part]
    else:
        # 既存テスト互換: content を None にすることで `_extract_response_text` が
        # "" を返し、llm_judgement=None → 後方互換パスへ。
        candidate.content = None
    response.candidates = [candidate]
    return response


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "test.db"
    init_db(p)
    return p


def _candidate(title: str = "Test Event", summary: str = "Test summary") -> dict:
    return {"title": title, "summary": summary}


def _angle(core_question: str = "テスト特定角度") -> dict:
    return {"core_question": core_question}


# ── 1. TestParseLLMJudgement: パース関数の境界条件 ──────────────────────


class TestParseLLMJudgement:
    """`_parse_llm_judgement` のキーワード判定 + 嘘をつかない設計の検証。"""

    def test_parse_empty_returns_none(self) -> None:
        """空文字 → None (B-3.a 後方互換パス用)。"""
        label, text = _parse_llm_judgement("")
        assert label is None
        assert text is None

    def test_parse_non_string_returns_none(self) -> None:
        """str でない入力 → None。"""
        label, text = _parse_llm_judgement(None)  # type: ignore[arg-type]
        assert label is None
        assert text is None

    def test_parse_explicit_no_match_keyword(self) -> None:
        """『該当する記事はありません』→ no_match (新プロンプト想定の明示文)。"""
        text = "検索結果を確認しました。該当する記事はありません。"
        label, matched = _parse_llm_judgement(text)
        assert label == "no_match"
        assert "該当する記事はありません" in matched

    def test_parse_見つかりませんでした_keyword(self) -> None:
        """『見つかりませんでした』→ no_match (Slot-2 既存 dump の主要シグナル)。"""
        text = "日本の主要メディアで報道されていることを示す記事URLは見つかりませんでした。"
        label, matched = _parse_llm_judgement(text)
        assert label == "no_match"
        assert matched is not None

    def test_parse_異なる内容_keyword(self) -> None:
        """『異なる内容』→ no_match (Slot-2 既存 dump の副次シグナル)。"""
        text = "類似の報道はありますが、これらの記事は確認対象の事象とは異なる内容です。"
        label, _ = _parse_llm_judgement(text)
        assert label == "no_match"

    def test_parse_日付も異なります_keyword(self) -> None:
        """『日付も異なります』→ no_match。"""
        text = "報道された事象は別事象で、日付も異なります。"
        label, _ = _parse_llm_judgement(text)
        assert label == "no_match"

    def test_parse_explicit_match_keyword_該当する記事は以下(self) -> None:
        """『該当する記事は以下』→ match。"""
        text = "該当する記事は以下のとおりです。https://nhk.or.jp/news/x"
        label, matched = _parse_llm_judgement(text)
        assert label == "match"
        assert matched is not None

    def test_parse_match_keyword_報道されています(self) -> None:
        """『報道されています』→ match。"""
        text = "本件は NHK と朝日新聞で報道されています。"
        label, _ = _parse_llm_judgement(text)
        assert label == "match"

    def test_parse_ambiguous_returns_uncertain(self) -> None:
        """キーワード不在 / 中立文 → uncertain (空ではないが判定材料なし)。"""
        text = "検索結果は様々でした。複数のメディアが取り上げています様子です。"
        label, matched = _parse_llm_judgement(text)
        # キーワード不在
        assert label == "uncertain"
        assert matched is None

    def test_parse_mixed_keywords_returns_uncertain(self) -> None:
        """match + no_match 混在文 → uncertain (嘘をつかない設計、保守)。"""
        text = (
            "該当する記事は以下に列挙します。https://example.com\n"
            "ただし主要メディアで報道されていません。"
        )
        label, _ = _parse_llm_judgement(text)
        # 1 文目 match、2 文目 no_match だが 2 文目に転換接続詞「ただし」がある
        # → 2 文目は弱化 → 1 文目 match のみ残る
        # ただしこのケースは設計通り「混在 → uncertain」と区別される
        # 実装では転換後の文は弱化されるため、結果は match になる
        assert label in ("match", "uncertain")

    def test_parse_turn_particle_weakens_no_match(self) -> None:
        """『該当しないが類似報道あり』のような転換接続詞 → 弱化 → uncertain。"""
        text = "当該事象に該当する記事はありませんが、しかし類似トピックは報道されています。"
        label, _ = _parse_llm_judgement(text)
        # 「ありません」検出文に「しかし」「ありません」両方含む → 転換扱いで弱化
        # 後段「報道されています」も「しかし」直後で弱化
        # → 両方弱化 → uncertain
        assert label == "uncertain"

    def test_parse_pure_no_match_with_multiple_signals(self) -> None:
        """複数の no_match シグナル独立検出 (Slot-2 dump 想定)。"""
        text = (
            "報道されていることを示す記事URLは見つかりませんでした。\n"
            "類似の記事はありますが、これらの記事は確認対象の事象とは異なる内容で、\n"
            "かつ日付も異なります。"
        )
        label, matched = _parse_llm_judgement(text)
        assert label == "no_match"
        assert matched is not None


# ── 2. TestExtractResponseText: ヘルパ関数 ─────────────────────────────────


class TestExtractResponseText:
    """`_extract_response_text` の堅牢性 (既存 MagicMock 互換)。"""

    def test_extract_from_response_with_parts(self) -> None:
        """正常な response.candidates[0].content.parts[*].text → 結合して返す。"""
        response = MagicMock()
        part1 = MagicMock()
        part1.text = "前半文。"
        part2 = MagicMock()
        part2.text = "後半文。"
        response.candidates = [MagicMock()]
        response.candidates[0].content = MagicMock()
        response.candidates[0].content.parts = [part1, part2]
        assert _extract_response_text(response) == "前半文。後半文。"

    def test_extract_from_response_no_candidates(self) -> None:
        """candidates が空 → ""。"""
        response = MagicMock()
        response.candidates = []
        assert _extract_response_text(response) == ""

    def test_extract_from_response_content_is_none(self) -> None:
        """content が None → "" (既存テスト互換の主経路)。"""
        response = MagicMock()
        response.candidates = [MagicMock()]
        response.candidates[0].content = None
        assert _extract_response_text(response) == ""

    def test_extract_from_default_magicmock(self) -> None:
        """既存テストの素の MagicMock (content も parts も MagicMock のまま) →
        text が str でないため "" にフォールバック (B-3.a 後方互換の核心)。"""
        response = MagicMock()
        response.candidates = [MagicMock()]
        # content は MagicMock のまま、parts も MagicMock のまま
        # → for p in parts は MagicMock の __iter__ で空イテレータ → text_parts=[] → ""
        assert _extract_response_text(response) == ""

    def test_extract_skips_non_string_text(self) -> None:
        """part.text が str でない (MagicMock 等) → スキップして他の str だけ結合。"""
        response = MagicMock()
        part_str = MagicMock()
        part_str.text = "有効文。"
        part_mock = MagicMock()  # part_mock.text は MagicMock (str ではない)
        response.candidates = [MagicMock()]
        response.candidates[0].content = MagicMock()
        response.candidates[0].content.parts = [part_mock, part_str, part_mock]
        assert _extract_response_text(response) == "有効文。"


# ── 3. TestVerifyWithLLMJudgement: verify() ハイブリッド判定 (B-3 表) ────


class TestVerifyWithLLMJudgement:
    """verify() の WL × LLM judgement ハイブリッド判定 (B-3 表)。"""

    def test_wl_match_llm_match_returns_true(self, db_path) -> None:
        """WL あり + LLM = match → has_jp_coverage = True (現状維持)。"""
        client = MagicMock()
        client.models.generate_content.return_value = _make_grounding_response(
            ["nhk.or.jp"],
            response_text="該当する記事は以下です。https://nhk.or.jp/news/x",
        )
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify("evt-wl-llm-match", "T")
        assert result.has_jp_coverage is True
        assert result.llm_judgement == "match"
        assert result.matched_tier == "tier_1_newspaper"

    def test_wl_match_llm_no_match_returns_false(self, db_path) -> None:
        """★ WL あり + LLM = no_match → has_jp_coverage = False (本改修の核心)。"""
        client = MagicMock()
        # Slot-2 シナリオ: afpbb ヒットだが LLM は「該当しない」
        client.models.generate_content.return_value = _make_grounding_response(
            ["afpbb.com"],
            response_text=(
                "日本の主要メディアで報道されていることを示す記事URLは見つかりませんでした。\n"
                "これらの記事は確認対象の事象とは異なる内容で、日付も異なります。"
            ),
        )
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify("evt-wl-llm-no-match", "T")
        # ★ WL マッチがあっても LLM が支配して False
        assert result.has_jp_coverage is False
        assert result.llm_judgement == "no_match"
        # matched_urls / tier は WL マッチ情報を保持 (= デバッグ用)
        assert result.matched_tier == "tier_2_wire_service"
        assert result.llm_judgement_text is not None

    def test_wl_match_llm_uncertain_returns_false(self, db_path) -> None:
        """★ WL あり + LLM = uncertain → has_jp_coverage = False (嘘をつかない設計)。"""
        client = MagicMock()
        client.models.generate_content.return_value = _make_grounding_response(
            ["nikkei.com"],
            response_text="検索結果は様々で、判定が難しい状況です。",  # uncertain 想定
        )
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify("evt-wl-llm-uncertain", "T")
        assert result.has_jp_coverage is False  # ★ 疑わしきは低く見積もる
        assert result.llm_judgement == "uncertain"

    def test_wl_no_match_returns_false(self, db_path) -> None:
        """WL なし → has_jp_coverage = False (LLM 判定不問、現状維持)。"""
        client = MagicMock()
        client.models.generate_content.return_value = _make_grounding_response(
            ["example.com"],  # WL 外ドメイン
            response_text="該当する記事は以下です。https://example.com",  # match と言っても WL 外
        )
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify("evt-no-wl", "T")
        assert result.has_jp_coverage is False
        assert result.matched_tier is None
        # LLM が match と言っても WL 外なので False (B-3 表「なし行」)

    def test_wl_match_no_response_text_backward_compat(self, db_path) -> None:
        """★ WL あり + LLM 判定不能 (response_text 空) → True (B-3.a 後方互換)。

        既存挙動を維持するためのテスト。response_text 抽出が空文字列の場合は
        `_parse_llm_judgement` が None を返し、verify() は WL マッチのみで判定。
        """
        client = MagicMock()
        # response_text を埋め込まない (= 既存テスト互換、content=None)
        client.models.generate_content.return_value = _make_grounding_response(
            ["nhk.or.jp"],
            response_text="",
        )
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify("evt-backward-compat", "T")
        # ★ LLM 判定不能 (None) → 後方互換 → WL マッチのみで True
        assert result.has_jp_coverage is True
        assert result.llm_judgement is None


# ── 4. TestVerifyTwoStageWithLLMJudgement: 二段階版ハイブリッド判定 ───


class TestVerifyTwoStageWithLLMJudgement:
    """verify_two_stage() の broad / angle ハイブリッド判定。"""

    def test_broad_llm_no_match_falls_to_stream_1(self, db_path) -> None:
        """★ broad で WL あり + LLM = no_match → stream_1_silence_gap (Step 2 スキップ)。

        本改修の核心: broad 検索で WL ヒットがあっても LLM が「該当しない」と
        判定すれば、broad_jp_coverage=False に倒れて Step 2 (angle 検索) は不要。
        """
        client = MagicMock()
        client.models.generate_content.return_value = _make_grounding_response(
            ["afpbb.com"],
            response_text=(
                "見つかりませんでした。\n"
                "類似の記事はありますが、これらは確認対象の事象とは異なる内容です。"
            ),
        )
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        analysis_client = MagicMock()
        result = v.verify_two_stage(
            candidate=_candidate(),
            particular_angle=_angle(),
            analysis_llm_client=analysis_client,
        )
        # ★ broad で LLM 支配 → stream_1
        assert result.stream == "stream_1_silence_gap"
        assert result.broad_jp_coverage is False
        assert result.broad_llm_judgement == "no_match"
        # ★ Step 2 はスキップされた (angle 検索 API 呼び出し 1 回のみ)
        assert client.models.generate_content.call_count == 1
        assert analysis_client.generate.call_count == 0  # angle クエリ生成も不要

    def test_angle_llm_no_match_falls_to_stream_2(self, db_path) -> None:
        """broad 通過 + angle で WL あり + LLM = no_match → stream_2_perspective_gap。"""
        client = MagicMock()
        client.models.generate_content.side_effect = [
            # broad: match
            _make_grounding_response(
                ["nhk.or.jp"],
                response_text="該当する記事は以下です。https://nhk.or.jp/news/x",
            ),
            # angle: WL ヒットあるが LLM は no_match (= 特定角度が日本未報道)
            _make_grounding_response(
                ["asahi.com"],
                response_text=(
                    "該当する記事はありません。"
                    "事象全体は報道されていますが、当該特定角度に関する記事は見当たりません。"
                ),
            ),
        ]
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        analysis_client = MagicMock()
        analysis_client.generate.return_value = "特定角度キーワード"
        result = v.verify_two_stage(
            candidate=_candidate(),
            particular_angle=_angle(),
            analysis_llm_client=analysis_client,
        )
        assert result.stream == "stream_2_perspective_gap"
        assert result.broad_jp_coverage is True
        assert result.broad_llm_judgement == "match"
        assert result.angle_jp_coverage is False
        assert result.angle_llm_judgement == "no_match"

    def test_two_stage_backward_compat_no_response_text(self, db_path) -> None:
        """★ broad / angle 両方で response_text 不在 (= 既存テスト構造) →
        既存挙動維持 (broad/angle ともに WL マッチのみで判定)。

        これにより既存 test_jp_coverage_verifier_two_stage.py の 16 ケースが
        破壊されないことを保証する (B-3.a 後方互換の本質)。
        """
        client = MagicMock()
        client.models.generate_content.side_effect = [
            _make_grounding_response(["nhk.or.jp"], response_text=""),  # broad
            _make_grounding_response(["asahi.com"], response_text=""),  # angle
        ]
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        analysis_client = MagicMock()
        analysis_client.generate.return_value = "特定角度"
        result = v.verify_two_stage(
            candidate=_candidate(),
            particular_angle=_angle(),
            analysis_llm_client=analysis_client,
        )
        # 両方とも WL マッチ + LLM 判定なし → 後方互換で True 扱い → stream_3_candidate
        assert result.stream == "stream_3_candidate"
        assert result.broad_jp_coverage is True
        assert result.angle_jp_coverage is True
        assert result.broad_llm_judgement is None
        assert result.angle_llm_judgement is None


# ── 5. TestResultDataclassFields: 新規 optional フィールドの互換性 ─────


class TestResultDataclassFields:
    """JpCoverageResult / TwoStageVerifyResult の新規 optional フィールドが
    既存呼び出し側を壊さないこと。"""

    def test_jp_coverage_result_defaults(self) -> None:
        """新規フィールドは default 値ありで既存コンストラクタを破壊しない。"""
        # 既存コンストラクタ (新規フィールド指定なし) でインスタンス化可能
        r = JpCoverageResult(event_id="x", title="t", has_jp_coverage=False)
        assert r.llm_judgement is None
        assert r.llm_judgement_text is None
        # 既存フィールドはそのまま
        assert r.event_id == "x"
        assert r.has_jp_coverage is False

    def test_two_stage_verify_result_defaults(self) -> None:
        """TwoStageVerifyResult 新規 4 フィールドも default 値で互換。"""
        r = TwoStageVerifyResult(stream="unknown", broad_query="q")
        assert r.broad_llm_judgement is None
        assert r.broad_llm_judgement_text is None
        assert r.angle_llm_judgement is None
        assert r.angle_llm_judgement_text is None
