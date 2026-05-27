"""F-gemini-quality-tier-poc: 最終布陣 v2 の role 別モデル ID 解決を検証する。

実際に factory に dispatch される role 文字列 (merge_batch / judge / generation /
analysis / article) が、最終布陣 v2 の Tier 階層・MAX_ATTEMPTS に解決されることを
確認する。env 上書き優先 (env > inline default) も検証する。

実 LLM は呼び出さない (Tier リスト解決 = 純関数 + GEMINI_API_KEY ダミーでの client 構築)。
"""
import importlib
from unittest.mock import patch

from src.llm.factory import (
    _get_tier_models_for_role,
    _get_max_attempts_for_role,
)


# 最終布陣 v2 の inline default 期待値 (env 未設定時)。
# ★ 実際に dispatch される role 文字列でキーする (lineup の 10 role 名ではなく)。
_LINEUP_V2_TIERS = {
    # merge_batch = garbage_filter / cluster_merge 共用 (LIGHTWEIGHT)
    "merge_batch": ["gemini-3.1-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite"],
    # generation = script (QUALITY、未分類 else 分岐)
    "generation": ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"],
    # analysis = perspective/insight/jp_coverage angle query 共用 (QUALITY)
    "analysis": ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"],
    # judge = editorial_mission_filter / elite_judge 共用 (QUALITY 階層。primary は別途 JUDGE_MODEL prepend)
    "judge": ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"],
    # article = output コスト最適化 (ARTICLE)
    "article": ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"],
}

_LINEUP_V2_MAX_ATTEMPTS = {
    "merge_batch": 1,
    "generation": 2,
    "analysis": 2,
    "judge": 2,
    "article": 1,
}

_TIER_ENV_KEYS = [
    "GEMINI_MODEL_TIER1", "GEMINI_MODEL_TIER2", "GEMINI_MODEL_TIER3", "GEMINI_MODEL_TIER4",
    "GEMINI_LIGHTWEIGHT_TIER1", "GEMINI_LIGHTWEIGHT_TIER2", "GEMINI_LIGHTWEIGHT_TIER3", "GEMINI_LIGHTWEIGHT_TIER4",
    "GEMINI_ARTICLE_TIER1", "GEMINI_ARTICLE_TIER2", "GEMINI_ARTICLE_TIER3", "GEMINI_ARTICLE_TIER4",
]
_MAX_ATTEMPTS_ENV_KEYS = [
    "GEMINI_QUALITY_MAX_ATTEMPTS", "GEMINI_LIGHTWEIGHT_MAX_ATTEMPTS", "GEMINI_ARTICLE_MAX_ATTEMPTS",
]


class TestLineupV2InlineDefaults:
    """env 未設定時、inline default が最終布陣 v2 に一致することを確認。"""

    def _reset_env(self, monkeypatch):
        for key in _TIER_ENV_KEYS + _MAX_ATTEMPTS_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)

    def test_dispatched_roles_resolve_to_lineup_v2_tiers(self, monkeypatch):
        self._reset_env(monkeypatch)
        for role, expected in _LINEUP_V2_TIERS.items():
            assert _get_tier_models_for_role(role) == expected, f"role={role}"

    def test_dispatched_roles_resolve_to_lineup_v2_max_attempts(self, monkeypatch):
        self._reset_env(monkeypatch)
        for role, expected in _LINEUP_V2_MAX_ATTEMPTS.items():
            assert _get_max_attempts_for_role(role) == expected, f"role={role}"

    def test_quality_and_article_primary_differ(self, monkeypatch):
        """QUALITY (script/judge/analysis) = 3.5-flash、ARTICLE = 2.5-flash で primary が分かれる。"""
        self._reset_env(monkeypatch)
        assert _get_tier_models_for_role("generation")[0] == "gemini-3.5-flash"
        assert _get_tier_models_for_role("article")[0] == "gemini-2.5-flash"
        assert _get_tier_models_for_role("merge_batch")[0] == "gemini-3.1-flash-lite"


class TestEnvOverridePrecedence:
    """env 上書きが inline default より優先されることを確認 (env > factory default)。"""

    def test_quality_tier1_env_override(self, monkeypatch):
        monkeypatch.setenv("GEMINI_MODEL_TIER1", "env-quality-model")
        assert _get_tier_models_for_role("generation")[0] == "env-quality-model"
        assert _get_tier_models_for_role("judge")[0] == "env-quality-model"

    def test_article_tier1_env_override(self, monkeypatch):
        monkeypatch.setenv("GEMINI_ARTICLE_TIER1", "env-article-model")
        assert _get_tier_models_for_role("article")[0] == "env-article-model"

    def test_lightweight_tier1_env_override(self, monkeypatch):
        monkeypatch.setenv("GEMINI_LIGHTWEIGHT_TIER1", "env-light-model")
        assert _get_tier_models_for_role("merge_batch")[0] == "env-light-model"

    def test_max_attempts_env_override(self, monkeypatch):
        monkeypatch.setenv("GEMINI_QUALITY_MAX_ATTEMPTS", "7")
        monkeypatch.setenv("GEMINI_ARTICLE_MAX_ATTEMPTS", "3")
        monkeypatch.setenv("GEMINI_LIGHTWEIGHT_MAX_ATTEMPTS", "9")
        assert _get_max_attempts_for_role("generation") == 7
        assert _get_max_attempts_for_role("article") == 3
        assert _get_max_attempts_for_role("merge_batch") == 9


class TestArticleScriptClientSeparation:
    """get_article_llm_client が role='article' に分離され、script (generation) と
    primary が異なることを確認 (article_writer.py 不変での分離検証)。"""

    def test_article_client_uses_article_tier_distinct_from_script(self):
        env = {
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": "dummy-key",
            "GEMINI_MODEL_TIER1": "gemini-3.5-flash",
            "GEMINI_ARTICLE_TIER1": "gemini-2.5-flash",
        }
        import src.shared.config as cfg
        import src.llm.factory as factory
        with patch.dict("os.environ", env):
            importlib.reload(cfg)
            importlib.reload(factory)
            article_client = factory.get_article_llm_client()
            script_client = factory.get_script_llm_client()
            assert isinstance(article_client, factory.TieredGeminiClient)
            assert isinstance(script_client, factory.TieredGeminiClient)
            # article primary = 2.5-flash, script primary = 3.5-flash
            assert article_client._tiers[0] == "gemini-2.5-flash"
            assert script_client._tiers[0] == "gemini-3.5-flash"
            assert article_client._tiers[0] != script_client._tiers[0]
            # article は MAX_ATTEMPTS=1 (デフォルト)
            assert article_client._max_attempts_per_tier == 1
        # patch.dict 退出 → os.environ は復元済。後続テストへの影響を避け素の状態に戻す。
        importlib.reload(cfg)
        importlib.reload(factory)
