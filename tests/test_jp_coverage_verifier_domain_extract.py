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

from src.storage.db import init_db
from src.triage.jp_coverage_verifier import (
    JP_MEDIA_WHITELIST,
    JpCoverageVerifier,
    _domain_matches_hierarchy,
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


# ─────────────────────────────────────────────────────────────────────────────
# F-jp-coverage-tune-followup (2026-05-09):
# Step A — _domain_matches_hierarchy ユニットテスト
# Step B — WL 拡張 + WL マッチングを通した end-to-end テスト
# ─────────────────────────────────────────────────────────────────────────────


class TestDomainMatchesHierarchy:
    """_domain_matches_hierarchy() のドメイン階層判定確認 (Step A)。"""

    def test_match_whitelist_subdomain_to_parent(self) -> None:
        """WL 登録 'news.fnn.jp' に対して抽出 'fnn.jp' でマッチすること。

        本バッチ起点の問題: blind_002 broad で fnn.jp (サブドメインなし) で
        返ってきていたが、WL マッチング側で別エントリ扱いされていた。
        """
        assert _domain_matches_hierarchy("fnn.jp", "news.fnn.jp") is True

    def test_match_whitelist_parent_to_subdomain(self) -> None:
        """WL 登録 'fnn.jp' に対して抽出 'news.fnn.jp' でもマッチすること
        (将来の WL 構成変更に備えた対称性確認)。"""
        assert _domain_matches_hierarchy("news.fnn.jp", "fnn.jp") is True

    def test_match_whitelist_exact(self) -> None:
        """完全一致でマッチ。"""
        assert _domain_matches_hierarchy("nikkei.com", "nikkei.com") is True
        assert _domain_matches_hierarchy("news.fnn.jp", "news.fnn.jp") is True

    def test_match_whitelist_deep_subdomain(self) -> None:
        """多段サブドメイン (www3.nhk.or.jp ⊂ nhk.or.jp) もマッチ。"""
        assert _domain_matches_hierarchy("www3.nhk.or.jp", "nhk.or.jp") is True

    def test_match_whitelist_no_overmatch_tld(self) -> None:
        """TLD 共通だけ (例: 'something.co.jp' vs 'nhk.or.jp') ではマッチしない。"""
        assert _domain_matches_hierarchy("something.co.jp", "nhk.or.jp") is False

    def test_match_whitelist_no_overmatch_partial(self) -> None:
        """文字列部分一致 ('not-nikkei.com' vs 'nikkei.com') ではマッチしない。

        旧実装の `domain in url_lower` 部分文字列マッチで暗黙的に拾っていた
        過剰一致を、ドメイン階層判定で排除する。
        """
        assert _domain_matches_hierarchy("not-nikkei.com", "nikkei.com") is False
        assert _domain_matches_hierarchy("xxnikkei.com", "nikkei.com") is False

    def test_match_whitelist_unrelated_tld(self) -> None:
        """関係ないドメインがマッチしない (祖先・子孫関係なし)。"""
        assert _domain_matches_hierarchy("asahi.com", "nikkei.com") is False
        assert _domain_matches_hierarchy("example.org", "example.com") is False

    def test_match_whitelist_empty_inputs(self) -> None:
        """空文字 / None 相当の入力で False。"""
        assert _domain_matches_hierarchy("", "nikkei.com") is False
        assert _domain_matches_hierarchy("nikkei.com", "") is False
        assert _domain_matches_hierarchy("", "") is False

    def test_match_whitelist_normalization(self) -> None:
        """大文字 / 余計な空白 / 先頭ドットを正規化してマッチ。"""
        assert _domain_matches_hierarchy("NEWS.FNN.JP", "fnn.jp") is True
        assert _domain_matches_hierarchy("  fnn.jp  ", "news.fnn.jp") is True
        assert _domain_matches_hierarchy(".news.fnn.jp", "fnn.jp") is True


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "test.db"
    init_db(p)
    return p


def _make_grounding_response(uris):
    """Gemini Grounding response を模した MagicMock を作る (test_f13b と同等)。"""
    from urllib.parse import urlparse

    chunks = []
    for uri in uris:
        host = urlparse(uri).hostname or ""
        web = MagicMock()
        web.uri = (
            f"https://vertexaisearch.cloud.google.com/grounding-api-redirect/{host}"
        )
        web.title = host
        web.domain = None
        chunk = MagicMock()
        chunk.web = web
        chunks.append(chunk)
    metadata = MagicMock()
    metadata.grounding_chunks = chunks
    candidate = MagicMock()
    candidate.grounding_metadata = metadata
    response = MagicMock()
    response.candidates = [candidate]
    return response


def _make_client(uris):
    client = MagicMock()
    client.models.generate_content.return_value = _make_grounding_response(uris)
    return client


class TestWhitelistMatchSubdomainAbsorption:
    """Step A: 実際の verify() フローで WL サブドメイン吸収が機能すること。"""

    def test_fnn_jp_matches_news_fnn_jp_tier(self, db_path):
        """blind_002 で観測された 'fnn.jp' が news.fnn.jp の Tier 3 に
        マッチすることを保証する (= 本バッチの主目的)。"""
        # Grounding が "fnn.jp" を返した想定
        client = _make_client(["https://fnn.jp/articles/x"])
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify("evt-fnn-parent", "title")
        assert result.has_jp_coverage is True
        assert result.matched_tier == "tier_3_broadcaster"
        assert "news.fnn.jp" in result.matched_domains

    @pytest.mark.parametrize("host", [
        "tbs.co.jp",       # WL: news.tbs.co.jp
        "ntv.co.jp",       # WL: news.ntv.co.jp
        "tv-asahi.co.jp",  # WL: news.tv-asahi.co.jp
        "tv-tokyo.co.jp",  # WL: news.tv-tokyo.co.jp
        "bs-tbs.co.jp",    # WL: news.bs-tbs.co.jp
    ])
    def test_tier3_parent_domains_match(self, db_path, host):
        """Tier 3 の親ドメインが返ってきても全て Tier 3 マッチすることを担保
        (同様のリスクが Tier 3 全部に潜在していた)。"""
        client = _make_client([f"https://{host}/news/x"])
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify(f"evt-{host}", "title")
        assert result.has_jp_coverage is True
        assert result.matched_tier == "tier_3_broadcaster"

    def test_unrelated_co_jp_not_matched(self, db_path):
        """無関係な co.jp ドメインがマッチしないこと (TLD 共通の過剰マッチ排除)。"""
        client = _make_client(["https://example.co.jp/x"])
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify("evt-cojp", "title")
        assert result.has_jp_coverage is False
        assert result.matched_tier is None

    def test_partial_string_does_not_match(self, db_path):
        """文字列部分一致 (例: not-nikkei.com) がマッチしないこと。"""
        client = _make_client(["https://not-nikkei.com/x"])
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify("evt-not-nikkei", "title")
        assert result.has_jp_coverage is False


class TestWhitelistExtension:
    """Step B: 確定追加 3 ドメインが正しい Tier にマッチすること。"""

    def test_afpbb_com_in_tier_2(self):
        assert "afpbb.com" in JP_MEDIA_WHITELIST["tier_2_wire_service"]

    def test_forbesjapan_com_in_tier_4(self):
        assert "forbesjapan.com" in JP_MEDIA_WHITELIST["tier_4_business"]

    def test_nippon_com_in_tier_4(self):
        assert "nippon.com" in JP_MEDIA_WHITELIST["tier_4_business"]

    @pytest.mark.parametrize("url,expected_tier,expected_domain", [
        ("https://www.afpbb.com/articles/x", "tier_2_wire_service", "afpbb.com"),
        ("https://forbesjapan.com/articles/y", "tier_4_business", "forbesjapan.com"),
        ("https://www.nippon.com/ja/in-depth/z", "tier_4_business", "nippon.com"),
    ])
    def test_added_domain_matches_via_verify(
        self, db_path, url, expected_tier, expected_domain
    ):
        client = _make_client([url])
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify(f"evt-add-{expected_domain}", "title")
        assert result.has_jp_coverage is True
        assert result.matched_tier == expected_tier
        assert expected_domain in result.matched_domains

    @pytest.mark.parametrize("url,expected_domain", [
        ("https://news.afpbb.com/articles/x", "afpbb.com"),
        ("https://www.forbesjapan.com/articles/y", "forbesjapan.com"),
        ("https://www.nippon.com/ja/in-depth/z", "nippon.com"),
    ])
    def test_added_domain_subdomain_match(self, db_path, url, expected_domain):
        """追加ドメインのサブドメインも Step A の階層判定で吸収されること。"""
        client = _make_client([url])
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify(f"evt-sub-{expected_domain}", "title")
        assert result.has_jp_coverage is True
        assert expected_domain in result.matched_domains
