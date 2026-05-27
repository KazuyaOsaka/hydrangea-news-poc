"""F-gemini-quality-tier-poc: Gemini 3 系への temperature 非送出を検証する。

公式 docs (gemini-api/docs/gemini-3) は Gemini 3 系について temperature default 1.0 を
強く推奨し、1.0 未満では looping / degraded performance のリスクを警告する。
get_analysis_llm_client() は analysis primary tier が Gemini 3 系なら temperature を
generation_config に含めない (default 1.0 維持)。Gemini 2 系は従来通り temperature を渡す。

実 LLM は呼び出さない (GEMINI_API_KEY ダミーで client 構築し generation_config を検査)。
"""
import importlib
from unittest.mock import patch

from src.llm.factory import _is_gemini_3_series


class TestIsGemini3Series:
    """_is_gemini_3_series の判定ロジック。"""

    def test_gemini_3_series_true(self):
        assert _is_gemini_3_series("gemini-3.5-flash") is True
        assert _is_gemini_3_series("gemini-3.1-flash-lite") is True
        assert _is_gemini_3_series("gemini-3.1-pro") is True
        assert _is_gemini_3_series("gemini-3.1-pro-preview") is True
        assert _is_gemini_3_series("gemini-3-flash-preview") is True

    def test_gemini_2_and_others_false(self):
        assert _is_gemini_3_series("gemini-2.5-flash") is False
        assert _is_gemini_3_series("gemini-2.5-flash-lite") is False
        assert _is_gemini_3_series("gemini-2.0-flash") is False
        assert _is_gemini_3_series("gemini-1.5-flash") is False
        assert _is_gemini_3_series("") is False
        # 紛らわしいケース: "gemini-30..." は startswith("gemini-3") だが
        # 現行 Gemini 命名では gemini-3.x / gemini-3- のみが 3 系。実在命名で False の例:
        assert _is_gemini_3_series("gemini-2.5-flash-preview") is False


class TestAnalysisClientTemperatureGuard:
    """get_analysis_llm_client の generation_config に temperature が条件付きで含まれる。"""

    def _build_analysis_client(self, env: dict):
        import src.shared.config as cfg
        import src.llm.factory as factory
        with patch.dict("os.environ", env):
            importlib.reload(cfg)
            importlib.reload(factory)
            client = factory.get_analysis_llm_client()
            # 検査に必要な値をローカルへコピー
            cfg_obj = dict(client._generation_config) if client._generation_config else None
            tiers = list(client._tiers)
        # patch.dict 退出 → os.environ は復元済。モジュールを素の env で再ロードし状態を戻す。
        importlib.reload(cfg)
        importlib.reload(factory)
        return cfg_obj, tiers

    def test_gemini3_primary_omits_temperature(self):
        """analysis primary が Gemini 3 系 (gemini-3.5-flash) なら temperature を渡さない。"""
        env = {
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": "dummy-key",
            "GEMINI_MODEL_TIER1": "gemini-3.5-flash",
            "ANALYSIS_LLM_TEMPERATURE": "0.3",
            "ANALYSIS_LLM_MAX_TOKENS": "2000",
        }
        cfg_obj, tiers = self._build_analysis_client(env)
        assert tiers[0] == "gemini-3.5-flash"
        assert cfg_obj is not None
        assert "temperature" not in cfg_obj
        assert cfg_obj["max_output_tokens"] == 2000

    def test_gemini2_primary_keeps_temperature(self):
        """analysis primary が Gemini 2 系 (gemini-2.5-flash) なら temperature を従来通り渡す。"""
        env = {
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": "dummy-key",
            "GEMINI_MODEL_TIER1": "gemini-2.5-flash",
            "ANALYSIS_LLM_TEMPERATURE": "0.3",
            "ANALYSIS_LLM_MAX_TOKENS": "2000",
        }
        cfg_obj, tiers = self._build_analysis_client(env)
        assert tiers[0] == "gemini-2.5-flash"
        assert cfg_obj is not None
        assert cfg_obj["temperature"] == 0.3
        assert cfg_obj["max_output_tokens"] == 2000
