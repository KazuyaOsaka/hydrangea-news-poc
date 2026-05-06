"""F-jp-coverage-improve: F-13.B のドメイン抽出ロジック検証。

Gemini Grounding API の chunk.web.title からドメインを抽出する関数の動作確認。

背景: F-13.B `_search_with_grounding()` は元々 chunk.web.uri を WL マッチング
に使っていたが、Gemini は実ソースドメインではなく Vertex AI の redirect URL
(vertexaisearch.cloud.google.com/...) を返す仕様。実ドメインは chunk.web.title
に格納されている (web.domain は SDK 現行版で常に None)。

本テストは「ドメイン抽出レイヤー」(_extract_domain_from_chunk /
_looks_like_domain / _normalize_domain) を SDK 変更耐性のある防御層として
検証する。
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.triage.jp_coverage_verifier import (
    _extract_domain_from_chunk,
    _looks_like_domain,
    _normalize_domain,
)


class TestLooksLikeDomain:
    """_looks_like_domain() の判定確認。"""

    @pytest.mark.parametrize("s,expected", [
        ("jiji.com", True),
        ("jetro.go.jp", True),
        ("recordchina.co.jp", True),
        ("nhk.or.jp", True),
        ("nikkei.com", True),
        ("Jiji News", False),
        ("", False),
        ("just-a-word", False),
        ("https://jiji.com/article", False),
        ("a.b", False),
        ("a.bc", True),
    ])
    def test_judgment(self, s: str, expected: bool) -> None:
        assert _looks_like_domain(s) is expected

    def test_uppercase_normalized_before_match(self) -> None:
        """大文字含みでも判定が成立する (内部で lowercase されるため)。"""
        assert _looks_like_domain("JIJI.com") is True


class TestNormalizeDomain:
    """_normalize_domain() の正規化確認。"""

    @pytest.mark.parametrize("input_str,expected", [
        ("jiji.com", "jiji.com"),
        ("Jiji.com", "jiji.com"),
        ("  jetro.go.jp  ", "jetro.go.jp"),
        ("https://jiji.com", "jiji.com"),
        ("https://jiji.com/article/123", "jiji.com"),
        ("http://www.example.com", "www.example.com"),
        ("HTTPS://Jiji.COM/x", "jiji.com"),
    ])
    def test_normalization(self, input_str: str, expected: str) -> None:
        assert _normalize_domain(input_str) == expected


class TestExtractDomainFromChunk:
    """_extract_domain_from_chunk() のフォールバック戦略確認。"""

    def test_strategy_1_domain_field_present(self) -> None:
        """戦略 1: chunk.web.domain が値を返す場合、それを使う。"""
        chunk = MagicMock()
        chunk.web.domain = "jiji.com"
        chunk.web.title = "should-not-be-used"
        assert _extract_domain_from_chunk(chunk) == "jiji.com"

    def test_strategy_1_takes_precedence_over_title(self) -> None:
        """戦略 1 が title 戦略 2 より優先される。"""
        chunk = MagicMock()
        chunk.web.domain = "asahi.com"
        chunk.web.title = "nikkei.com"  # 別ドメイン形式
        assert _extract_domain_from_chunk(chunk) == "asahi.com"

    def test_strategy_2_title_field_when_domain_none(self) -> None:
        """戦略 2: domain が None なら title を使う (ドメイン形式の場合のみ)。"""
        chunk = MagicMock()
        chunk.web.domain = None
        chunk.web.title = "jiji.com"
        assert _extract_domain_from_chunk(chunk) == "jiji.com"

    def test_strategy_2_title_not_domain_format(self) -> None:
        """title がドメイン形式でない場合は None。"""
        chunk = MagicMock()
        chunk.web.domain = None
        chunk.web.title = "Jiji News Article"
        assert _extract_domain_from_chunk(chunk) is None

    def test_strategy_2_title_with_path_returns_none(self) -> None:
        """title がパス付き URL の場合、_looks_like_domain が弾く。"""
        chunk = MagicMock()
        chunk.web.domain = None
        chunk.web.title = "https://jiji.com/article"
        assert _extract_domain_from_chunk(chunk) is None

    def test_no_web_attribute(self) -> None:
        """chunk.web が None の場合は None。"""
        chunk = MagicMock()
        chunk.web = None
        assert _extract_domain_from_chunk(chunk) is None

    def test_chunk_without_web(self) -> None:
        """chunk オブジェクトに web 属性自体がない場合は None。"""
        chunk = MagicMock(spec=[])
        assert _extract_domain_from_chunk(chunk) is None

    def test_domain_field_is_not_string_falls_through(self) -> None:
        """domain が str でない (MagicMock 等) 場合は戦略 2 にフォールバック。

        MagicMock を素で読むと domain 属性は MagicMock オブジェクトを返すため、
        isinstance(domain, str) で弾かれて戦略 2 に進む必要がある。
        """
        chunk = MagicMock()
        # chunk.web.domain は MagicMock のまま (str ではない)
        chunk.web.title = "jiji.com"
        # MagicMock オブジェクトは str ではないので戦略 1 では拾わず
        # 戦略 2 で title を読み取る
        assert _extract_domain_from_chunk(chunk) == "jiji.com"

    def test_domain_field_empty_string_falls_through(self) -> None:
        """domain が空文字の場合は戦略 2 にフォールバック。"""
        chunk = MagicMock()
        chunk.web.domain = "   "
        chunk.web.title = "asahi.com"
        assert _extract_domain_from_chunk(chunk) == "asahi.com"

    def test_real_world_examples(self) -> None:
        """実 Grounding API レスポンスで観測された title 値で検証。"""
        examples = [
            "jiji.com",
            "jp.net",
            "dir.co.jp",
            "jetro.go.jp",
            "recordchina.co.jp",
            "nippon.com",
        ]
        for title in examples:
            chunk = MagicMock()
            chunk.web.domain = None
            chunk.web.title = title
            assert _extract_domain_from_chunk(chunk) == title.lower(), (
                f"failed for title={title!r}"
            )

    def test_uri_alone_is_ignored(self) -> None:
        """uri のみ存在 (title/domain なし) の chunk は None を返す。

        Gemini Grounding API の uri は redirect URL のため、明示的に無視する。
        """
        chunk = MagicMock()
        chunk.web.domain = None
        chunk.web.title = None
        chunk.web.uri = (
            "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE"
        )
        assert _extract_domain_from_chunk(chunk) is None
