"""LLMファクトリのユニットテスト。実際のAPIは呼び出さない。"""
from __future__ import annotations

import importlib
from unittest.mock import patch

import pytest

from src.llm.base import LLMClient
from src.llm.factory import TieredGeminiClient
from src.llm.gemini import GeminiClient  # noqa: F401  # legacy re-export still valid
from src.llm.groq import GroqClient
from src.llm.ollama import OllamaClient


# --- GeminiClient ---

def test_gemini_client_returns_none_when_no_api_key():
    with patch.dict("os.environ", {"LLM_PROVIDER": "gemini", "GEMINI_API_KEY": ""}):
        import src.shared.config as cfg
        import src.llm.factory as factory
        importlib.reload(cfg)
        importlib.reload(factory)
        assert factory.get_script_llm_client() is None
        assert factory.get_article_llm_client() is None


def test_gemini_client_created_when_api_key_set():
    """Gemini provider: factory は階層フォールバック付きの TieredGeminiClient を返す。

    旧実装は単一モデル GeminiClient を返していたが、現在は 4 段 Tier フォールバック
    (TIER1→TIER4) を実現する TieredGeminiClient が標準。
    """
    with patch.dict("os.environ", {"LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "dummy-key"}):
        import src.shared.config as cfg
        import src.llm.factory as factory
        importlib.reload(cfg)
        importlib.reload(factory)
        client = factory.get_script_llm_client()
        assert isinstance(client, factory.TieredGeminiClient)
        assert isinstance(client, LLMClient)


# --- GroqClient ---

def test_groq_client_created_for_groq_provider():
    with patch.dict("os.environ", {"LLM_PROVIDER": "groq", "GROQ_API_KEY": "dummy-groq-key"}):
        import src.shared.config as cfg
        import src.llm.factory as factory
        importlib.reload(cfg)
        importlib.reload(factory)
        client = factory.get_script_llm_client()
        assert isinstance(client, GroqClient)


def test_groq_generate_raises_not_implemented():
    client = GroqClient(api_key="dummy", model="llama-3.3-70b-versatile")
    with pytest.raises(NotImplementedError):
        client.generate("test prompt")


# --- OllamaClient ---

def test_ollama_client_created_for_ollama_provider():
    with patch.dict("os.environ", {"LLM_PROVIDER": "ollama"}):
        import src.shared.config as cfg
        import src.llm.factory as factory
        importlib.reload(cfg)
        importlib.reload(factory)
        client = factory.get_script_llm_client()
        assert isinstance(client, OllamaClient)


def test_ollama_generate_raises_not_implemented():
    client = OllamaClient(base_url="http://localhost:11434", model="llama3.2")
    with pytest.raises(NotImplementedError):
        client.generate("test prompt")


# --- 未知プロバイダ ---

def test_unknown_provider_returns_none():
    with patch.dict("os.environ", {"LLM_PROVIDER": "unknown_provider"}):
        import src.shared.config as cfg
        import src.llm.factory as factory
        importlib.reload(cfg)
        importlib.reload(factory)
        assert factory.get_script_llm_client() is None
        assert factory.get_article_llm_client() is None


# --- LLMClient は抽象クラス ---

def test_llm_client_is_abstract():
    with pytest.raises(TypeError):
        LLMClient()  # type: ignore[abstract]
