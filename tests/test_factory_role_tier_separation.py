"""E-3': 役割別 Tier 階層の分離を検証する。

LIGHTWEIGHT_ROLES (garbage_filter 等) と QUALITY_ROLES (script 等) で
異なる Tier 階層・MAX_ATTEMPTS が使われることをテスト。
"""
import os
from unittest.mock import patch

import pytest

from src.llm.factory import (
    LIGHTWEIGHT_ROLES,
    QUALITY_ROLES,
    _get_tier_models_for_role,
    _get_max_attempts_for_role,
)


class TestRoleClassification:
    """E-3': 役割分類が想定通りであることを確認。"""

    def test_lightweight_roles_contains_expected(self):
        """軽量タスクが LIGHTWEIGHT_ROLES に含まれている。"""
        assert "garbage_filter" in LIGHTWEIGHT_ROLES
        assert "merge_batch" in LIGHTWEIGHT_ROLES
        assert "viral_filter" in LIGHTWEIGHT_ROLES
        assert "editorial_mission_filter" in LIGHTWEIGHT_ROLES

    def test_quality_roles_contains_expected(self):
        """性能タスクが QUALITY_ROLES に含まれている。"""
        assert "judge" in QUALITY_ROLES
        assert "script" in QUALITY_ROLES
        assert "article" in QUALITY_ROLES
        assert "title" in QUALITY_ROLES
        assert "analysis" in QUALITY_ROLES

    def test_no_overlap_between_roles(self):
        """LIGHTWEIGHT_ROLES と QUALITY_ROLES は重複しない。"""
        assert LIGHTWEIGHT_ROLES.isdisjoint(QUALITY_ROLES)


class TestTierModelsForRole:
    """E-3': 役割別 Tier モデルリストの取得を検証。"""

    def test_lightweight_role_uses_ga_primary(self, monkeypatch):
        """LIGHTWEIGHT_ROLES は TIER1 が GA (gemini-2.5-flash デフォルト)。"""
        # env をリセット (デフォルト値テスト)
        for key in ["GEMINI_LIGHTWEIGHT_TIER1", "GEMINI_LIGHTWEIGHT_TIER2",
                    "GEMINI_LIGHTWEIGHT_TIER3", "GEMINI_LIGHTWEIGHT_TIER4"]:
            monkeypatch.delenv(key, raising=False)

        models = _get_tier_models_for_role("garbage_filter")
        assert len(models) == 4
        assert models[0] == "gemini-2.5-flash"
        assert models[1] == "gemini-2.5-flash-lite"
        assert models[2] == "gemini-3.1-flash-lite-preview"
        assert models[3] == "gemini-3-flash-preview"

    def test_quality_role_uses_preview_primary(self, monkeypatch):
        """QUALITY_ROLES は TIER1 が最高性能 Preview (gemini-3-flash-preview デフォルト)。"""
        for key in ["GEMINI_MODEL_TIER1", "GEMINI_MODEL_TIER2",
                    "GEMINI_MODEL_TIER3", "GEMINI_MODEL_TIER4"]:
            monkeypatch.delenv(key, raising=False)

        models = _get_tier_models_for_role("script")
        assert len(models) == 4
        assert models[0] == "gemini-3-flash-preview"
        assert models[1] == "gemini-2.5-flash"
        assert models[2] == "gemini-3.1-flash-lite-preview"
        assert models[3] == "gemini-2.5-flash-lite"

    def test_unknown_role_falls_back_to_quality(self, monkeypatch):
        """未分類の role は QUALITY_ROLES と同じ Tier 階層を使う (後方互換)。"""
        for key in ["GEMINI_MODEL_TIER1"]:
            monkeypatch.delenv(key, raising=False)

        models = _get_tier_models_for_role("unknown_role_xyz")
        # QUALITY のデフォルト値 gemini-3-flash-preview が返るはず
        assert models[0] == "gemini-3-flash-preview"

    def test_env_variable_override_for_lightweight(self, monkeypatch):
        """LIGHTWEIGHT 用 env で上書き可能。"""
        monkeypatch.setenv("GEMINI_LIGHTWEIGHT_TIER1", "custom-model-x")
        models = _get_tier_models_for_role("garbage_filter")
        assert models[0] == "custom-model-x"

    def test_env_variable_override_for_quality(self, monkeypatch):
        """QUALITY 用 env で上書き可能。"""
        monkeypatch.setenv("GEMINI_MODEL_TIER1", "custom-quality-y")
        models = _get_tier_models_for_role("analysis")
        assert models[0] == "custom-quality-y"


class TestMaxAttemptsForRole:
    """E-3': 役割別 MAX_ATTEMPTS の取得を検証。"""

    def test_lightweight_default_max_attempts(self, monkeypatch):
        """LIGHTWEIGHT のデフォルト MAX_ATTEMPTS は 2。"""
        monkeypatch.delenv("GEMINI_LIGHTWEIGHT_MAX_ATTEMPTS", raising=False)
        assert _get_max_attempts_for_role("garbage_filter") == 2

    def test_quality_default_max_attempts(self, monkeypatch):
        """QUALITY のデフォルト MAX_ATTEMPTS は 2。"""
        monkeypatch.delenv("GEMINI_QUALITY_MAX_ATTEMPTS", raising=False)
        assert _get_max_attempts_for_role("script") == 2

    def test_lightweight_max_attempts_override(self, monkeypatch):
        """LIGHTWEIGHT の MAX_ATTEMPTS を env で上書き可能。"""
        monkeypatch.setenv("GEMINI_LIGHTWEIGHT_MAX_ATTEMPTS", "5")
        assert _get_max_attempts_for_role("garbage_filter") == 5

    def test_quality_max_attempts_override(self, monkeypatch):
        """QUALITY の MAX_ATTEMPTS を env で上書き可能。"""
        monkeypatch.setenv("GEMINI_QUALITY_MAX_ATTEMPTS", "4")
        assert _get_max_attempts_for_role("script") == 4


class TestRoleSeparationIntegration:
    """E-3': 役割分離が実際の挙動に反映されることを統合的に検証。"""

    def test_lightweight_and_quality_have_different_tier1(self, monkeypatch):
        """LIGHTWEIGHT TIER1 と QUALITY TIER1 が異なるモデルを指す (デフォルト値)。"""
        for key in ["GEMINI_LIGHTWEIGHT_TIER1", "GEMINI_MODEL_TIER1"]:
            monkeypatch.delenv(key, raising=False)

        lightweight_tier1 = _get_tier_models_for_role("garbage_filter")[0]
        quality_tier1 = _get_tier_models_for_role("script")[0]

        assert lightweight_tier1 != quality_tier1
        assert lightweight_tier1 == "gemini-2.5-flash"
        assert quality_tier1 == "gemini-3-flash-preview"
