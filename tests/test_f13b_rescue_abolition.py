"""F-13.B: rescue path 廃止 + JP 大手メディア Web 検証テスト。

試運転 7-J (2026-04-30) で動画化率 0%。Slot-1 候補が JP 13 媒体に拡張後も
JP=0 件 → rescue 発動 → script skip。これは Hydrangea ミッション
(「日本で封殺されている海外ニュース」=blind_spot_global) と矛盾するため、
F-13.B で rescue path を完全廃止し、Web 検証で大手メディア報道有無を確認する
設計に移行した。

本テストは以下を担保する:
  1. rescue path 関連コード (judge_report.json / followup_queries.*) が
     書き出されないこと
  2. JpCoverageVerifier の基本動作 (has_jp_coverage True/False 分岐)
  3. ホワイトリストマッチング (Tier 1/2/3/4)
  4. 除外リスト動作 (Yahoo!ニュース等)
  5. Tier 優先度判定 (Tier 1 > Tier 4)
  6. 24h キャッシュ動作
  7. Grounding API エラー時の安全側挙動 (has_jp_coverage=True)
  8. F-15 / F-16-A との整合性
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.storage.db import init_db
from src.triage.jp_coverage_verifier import (
    JP_MEDIA_EXCLUDED,
    JP_MEDIA_WHITELIST,
    JpCoverageResult,
    JpCoverageVerifier,
)


# ─────────────────────────────────────────────────────────────────────────────
# 共通フィクスチャ
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "test.db"
    init_db(p)
    return p


def _make_grounding_response(uris: list[str]) -> MagicMock:
    """Gemini Grounding response を模した MagicMock を作る。"""
    chunks = []
    for uri in uris:
        web = MagicMock()
        web.uri = uri
        web.title = "mocked"
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


def _make_client(uris: list[str]) -> MagicMock:
    """generate_content が grounding response を返すモッククライアント。"""
    client = MagicMock()
    client.models.generate_content.return_value = _make_grounding_response(uris)
    return client


# ─────────────────────────────────────────────────────────────────────────────
# テスト 1: rescue path 廃止確認
# ─────────────────────────────────────────────────────────────────────────────


class TestRescuePathAbolition:
    """rescue 関連の書き出しが完全に廃止されていることを担保する。"""

    def test_write_judge_rescue_function_removed(self):
        """src.main から _write_judge_rescue 関数が削除されていること。"""
        import src.main as main_mod
        assert not hasattr(main_mod, "_write_judge_rescue"), (
            "F-13.B で _write_judge_rescue は撤去されているはず"
        )

    def test_main_source_does_not_write_judge_report_json(self):
        """src/main.py のソースに judge_report.json への書き出しが無いこと。"""
        main_path = Path(__file__).resolve().parents[1] / "src" / "main.py"
        text = main_path.read_text(encoding="utf-8")
        # コメントとしての言及は許可するが、実際の書き出しコードは無いこと
        assert 'output_dir / "judge_report.json"' not in text, (
            "judge_report.json の書き出しコードが残っている"
        )
        assert 'output_dir / "followup_queries.json"' not in text, (
            "followup_queries.json の書き出しコードが残っている"
        )
        assert 'output_dir / "followup_queries.md"' not in text, (
            "followup_queries.md の書き出しコードが残っている"
        )

    def test_is_rescue_candidate_no_longer_imported_in_main(self):
        """src/main.py が is_rescue_candidate を import していないこと。

        rescue path 完全廃止により、main.py 側で is_rescue_candidate を
        呼ぶコードは無くなったはず (gemini_judge.py 側の関数定義は触らない)。
        """
        main_path = Path(__file__).resolve().parents[1] / "src" / "main.py"
        text = main_path.read_text(encoding="utf-8")
        assert "import is_rescue_candidate" not in text, (
            "main.py が is_rescue_candidate を import している"
        )
        assert "is_rescue_candidate(" not in text, (
            "main.py が is_rescue_candidate を呼んでいる"
        )


# ─────────────────────────────────────────────────────────────────────────────
# テスト 2: JpCoverageVerifier 基本動作
# ─────────────────────────────────────────────────────────────────────────────


class TestVerifierBasic:
    """has_jp_coverage の True/False 分岐を担保する。"""

    def test_major_media_match_yields_true(self, db_path):
        client = _make_client(["https://www.asahi.com/articles/XYZ"])
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify("evt-1", "Gaza power crisis")
        assert result.has_jp_coverage is True
        assert result.matched_tier == "tier_1_newspaper"
        assert "asahi.com" in result.matched_domains

    def test_no_match_yields_false(self, db_path):
        client = _make_client(["https://example.com/foo", "https://blogspot.com/bar"])
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify("evt-2", "obscure event")
        assert result.has_jp_coverage is False
        assert result.matched_tier is None
        assert result.matched_domains == []


# ─────────────────────────────────────────────────────────────────────────────
# テスト 3: ホワイトリストマッチング (大手メディア)
# ─────────────────────────────────────────────────────────────────────────────


class TestWhitelistMatching:
    """Tier 1/2/3/4 全体のホワイトリストマッチングを担保する。"""

    @pytest.mark.parametrize("url,expected_tier,expected_domain", [
        ("https://www.asahi.com/articles/x", "tier_1_newspaper", "asahi.com"),
        ("https://www3.nhk.or.jp/news/y", "tier_1_newspaper", "nhk.or.jp"),
        ("https://jp.reuters.com/article/z", "tier_2_wire_service", "jp.reuters.com"),
        ("https://www.jiji.com/jc/a", "tier_2_wire_service", "jiji.com"),
        ("https://news.tv-asahi.co.jp/news_int/b", "tier_3_broadcaster", "news.tv-asahi.co.jp"),
        ("https://news.tbs.co.jp/newseye/c", "tier_3_broadcaster", "news.tbs.co.jp"),
        ("https://toyokeizai.net/articles/d", "tier_4_business", "toyokeizai.net"),
        ("https://newsweekjapan.jp/stories/e", "tier_4_business", "newsweekjapan.jp"),
    ])
    def test_each_tier_matches_correct_domain(self, db_path, url, expected_tier, expected_domain):
        client = _make_client([url])
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify("evt-tier", "title")
        assert result.has_jp_coverage is True
        assert result.matched_tier == expected_tier
        assert expected_domain in result.matched_domains

    def test_unknown_domain_yields_no_match(self, db_path):
        client = _make_client(["https://random-blog.example/article"])
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify("evt-unk", "title")
        assert result.has_jp_coverage is False
        assert result.matched_tier is None


# ─────────────────────────────────────────────────────────────────────────────
# テスト 4: 除外リスト動作
# ─────────────────────────────────────────────────────────────────────────────


class TestExclusionList:
    """Yahoo!ニュース等のアグリゲータが除外リストで弾かれることを担保。"""

    @pytest.mark.parametrize("excluded_url", [
        "https://news.yahoo.co.jp/articles/abc",
        "https://note.com/individual_user/n/foo",
        "https://twitter.com/user/status/123",
        "https://www.facebook.com/post/456",
        "https://huffingtonpost.jp/entry/xyz",
        "https://gendai.media/articles/p",
    ])
    def test_excluded_url_not_in_matched(self, db_path, excluded_url):
        client = _make_client([excluded_url])
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify("evt-excl", "title")
        assert result.has_jp_coverage is False, (
            f"除外 URL が matched に入っている: {excluded_url}"
        )
        assert excluded_url in result.excluded_urls
        assert result.matched_urls == []

    def test_mixed_urls_only_major_media_counted(self, db_path):
        """大手メディア URL と除外 URL の混在で大手だけが採用されること。"""
        urls = [
            "https://news.yahoo.co.jp/articles/abc",  # 除外
            "https://www.asahi.com/articles/xyz",     # Tier 1
            "https://twitter.com/user/123",           # 除外
        ]
        client = _make_client(urls)
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify("evt-mix", "title")
        assert result.has_jp_coverage is True
        assert result.matched_tier == "tier_1_newspaper"
        assert len(result.excluded_urls) == 2
        assert len(result.matched_urls) == 1


# ─────────────────────────────────────────────────────────────────────────────
# テスト 5: Tier 優先度判定
# ─────────────────────────────────────────────────────────────────────────────


class TestTierPriority:
    """複数 Tier がマッチした場合に最高 Tier が記録されること。"""

    def test_tier1_and_tier4_yields_tier1(self, db_path):
        urls = [
            "https://toyokeizai.net/articles/biz",   # Tier 4
            "https://www.asahi.com/articles/news",   # Tier 1
        ]
        client = _make_client(urls)
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify("evt-prio1", "title")
        assert result.matched_tier == "tier_1_newspaper"
        assert "asahi.com" in result.matched_domains
        assert "toyokeizai.net" in result.matched_domains

    def test_tier3_and_tier4_yields_tier3(self, db_path):
        urls = [
            "https://diamond.jp/articles/a",                # Tier 4
            "https://news.tv-asahi.co.jp/news_int/b",       # Tier 3
        ]
        client = _make_client(urls)
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify("evt-prio2", "title")
        assert result.matched_tier == "tier_3_broadcaster"

    def test_tier2_only_yields_tier2(self, db_path):
        client = _make_client(["https://jp.reuters.com/article/z"])
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify("evt-prio3", "title")
        assert result.matched_tier == "tier_2_wire_service"


# ─────────────────────────────────────────────────────────────────────────────
# テスト 6: キャッシュ動作
# ─────────────────────────────────────────────────────────────────────────────


class TestCache:
    """24h キャッシュが API 呼び出しを抑制することを担保。"""

    def test_first_call_invokes_api_then_cached(self, db_path):
        client = _make_client(["https://www.asahi.com/x"])
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)

        r1 = v.verify("evt-cache-1", "title")
        assert r1.cached is False
        assert client.models.generate_content.call_count == 1

        r2 = v.verify("evt-cache-1", "title")
        assert r2.cached is True
        assert client.models.generate_content.call_count == 1, (
            "2 回目はキャッシュ使用で API 呼び出しは増えないはず"
        )
        assert r2.has_jp_coverage is True
        assert r2.matched_tier == "tier_1_newspaper"

    def test_expired_cache_triggers_recall(self, db_path):
        client = _make_client(["https://www.asahi.com/x"])
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path, cache_ttl_hours=24)
        v.verify("evt-cache-2", "title")
        assert client.models.generate_content.call_count == 1

        # キャッシュ時刻を 25h 前に書き換える
        old_iso = (datetime.now() - timedelta(hours=25)).isoformat()
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "UPDATE jp_coverage_cache SET cached_at = ? WHERE event_id = ?",
                (old_iso, "evt-cache-2"),
            )
            conn.commit()

        v.verify("evt-cache-2", "title")
        assert client.models.generate_content.call_count == 2, (
            "TTL 経過後は再度 API 呼び出しが走るはず"
        )

    def test_different_event_id_does_not_share_cache(self, db_path):
        client = _make_client(["https://www.asahi.com/x"])
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        v.verify("evt-A", "title-A")
        v.verify("evt-B", "title-B")
        assert client.models.generate_content.call_count == 2


# ─────────────────────────────────────────────────────────────────────────────
# テスト 7: エラーハンドリング (安全側)
# ─────────────────────────────────────────────────────────────────────────────


class TestErrorHandling:
    """Grounding API エラー時に has_jp_coverage=True を返すこと。"""

    def test_api_exception_returns_safe_default(self, db_path):
        client = MagicMock()
        client.models.generate_content.side_effect = RuntimeError("API failed")
        v = JpCoverageVerifier(gemini_client=client, db_path=db_path)
        result = v.verify("evt-err", "title")
        assert result.has_jp_coverage is True, (
            "エラー時は安全側 (has_jp_coverage=True) に倒す"
        )
        assert result.error is not None
        assert "RuntimeError" in result.error

    def test_no_client_returns_safe_default(self, db_path):
        v = JpCoverageVerifier(gemini_client=None, db_path=db_path)
        result = v.verify("evt-noclient", "title")
        assert result.has_jp_coverage is True
        assert result.error is not None


# ─────────────────────────────────────────────────────────────────────────────
# テスト 8: F-15 / F-16-A 整合性
# ─────────────────────────────────────────────────────────────────────────────


class TestF15F16ACompatibility:
    """既存の F-15 / F-16-A コード経路が破壊されていないことを確認。"""

    def test_top_n_articles_per_run_still_imported(self):
        """F-16-A: TOP_N_ARTICLES_PER_RUN が config から import 可能なこと。"""
        from src.shared.config import TOP_N_ARTICLES_PER_RUN, TOP_N_VIDEOS_PER_RUN
        assert isinstance(TOP_N_ARTICLES_PER_RUN, int)
        assert isinstance(TOP_N_VIDEOS_PER_RUN, int)
        assert TOP_N_ARTICLES_PER_RUN >= 1
        assert TOP_N_VIDEOS_PER_RUN >= 1

    def test_main_still_runs_analysis_layer_for_top_n_targets(self):
        """F-15: AnalysisLayer の Top-N 対象選定ロジックが残存すること。"""
        main_path = Path(__file__).resolve().parents[1] / "src" / "main.py"
        text = main_path.read_text(encoding="utf-8")
        # F-15 の Elite Judge total_score 整列が残っているか
        assert "_elite_judge_results" in text
        assert "Top-3 generation loop" in text or "_top_n_for_analysis" in text

    def test_jp_coverage_config_loaded(self):
        """F-13.B: 環境変数 3 種が config に存在すること。"""
        from src.shared import config as cfg
        assert hasattr(cfg, "JP_COVERAGE_VERIFIER_ENABLED")
        assert hasattr(cfg, "JP_COVERAGE_CACHE_HOURS")
        assert hasattr(cfg, "JP_COVERAGE_GROUNDING_MODEL")
        assert isinstance(cfg.JP_COVERAGE_CACHE_HOURS, int)


# ─────────────────────────────────────────────────────────────────────────────
# 補助テスト: ホワイトリスト/除外リストの不変条件
# ─────────────────────────────────────────────────────────────────────────────


class TestWhitelistInvariants:
    def test_whitelist_has_4_tiers(self):
        assert set(JP_MEDIA_WHITELIST.keys()) == {
            "tier_1_newspaper",
            "tier_2_wire_service",
            "tier_3_broadcaster",
            "tier_4_business",
        }

    def test_whitelist_has_at_least_27_domains(self):
        total = sum(len(v) for v in JP_MEDIA_WHITELIST.values())
        # 仕様: 27 ドメイン (Tier1: 8, Tier2: 6, Tier3: 7, Tier4: 6) + nhk.jp 別名等
        assert total >= 27, f"想定 27 以上のはずが {total}"

    def test_excluded_list_includes_aggregators_and_sns(self):
        for needed in ["news.yahoo.co.jp", "twitter.com", "x.com", "note.com"]:
            assert needed in JP_MEDIA_EXCLUDED, f"{needed} が除外リストに無い"

    def test_jp_coverage_result_dataclass_defaults(self):
        r = JpCoverageResult(event_id="x", title="t", has_jp_coverage=False)
        assert r.matched_urls == []
        assert r.matched_domains == []
        assert r.matched_tier is None
        assert r.cached is False
