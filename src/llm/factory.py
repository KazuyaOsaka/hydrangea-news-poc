"""factory.py — Role-based LLM client factory.

Business logic must call get_llm_client(role) with one of:
  "merge_batch"  — cluster post-merge LLM (lightweight)
  "judge"        — editorial judgment (always Gemini)
  "generation"   — script + article generation

The backward-compat wrappers (get_script_llm_client, etc.) delegate to
get_llm_client() so existing callers need no changes.

Resolution path: .env → config.py → factory.py (→ model_registry.py for judge)
No hardcoded model strings in business logic.
"""
from __future__ import annotations

from typing import Optional

from src.llm.base import LLMClient
from src.shared.config import (
    GEMINI_API_KEY,
    GEMINI_JUDGE_FALLBACK_MODELS,
    GEMINI_JUDGE_MODEL,
    GENERATION_MODEL,
    GENERATION_PROVIDER,
    GROQ_API_KEY,
    JUDGE_MODEL,
    MERGE_BATCH_MODEL,
    MERGE_BATCH_PROVIDER,
    OLLAMA_BASE_URL,
)


def _make_client(provider: str, model: str) -> Optional[LLMClient]:
    """Construct an LLMClient for the given provider + model pair."""
    if provider == "gemini":
        if not GEMINI_API_KEY:
            return None
        from src.llm.gemini import GeminiClient
        return GeminiClient(GEMINI_API_KEY, model)

    if provider == "groq":
        from src.llm.groq import GroqClient
        return GroqClient(GROQ_API_KEY, model)

    if provider == "ollama":
        from src.llm.ollama import OllamaClient
        return OllamaClient(OLLAMA_BASE_URL, model)

    return None


def get_llm_client(role: str) -> Optional[LLMClient]:
    """Get an LLM client by role name.

    Args:
        role: One of "merge_batch", "judge", or "generation".

    Returns:
        Configured LLMClient, or None if the provider is not configured
        (e.g. GEMINI_API_KEY missing for gemini roles).

    Raises:
        ValueError: If role is not recognised.
    """
    if role == "merge_batch":
        return _make_client(MERGE_BATCH_PROVIDER, MERGE_BATCH_MODEL)

    if role == "judge":
        # Judge always uses Gemini regardless of LLM_PROVIDER.
        # Model is resolved via model_registry (models.list + fallback chain).
        return get_judge_llm_client()

    if role == "generation":
        return _make_client(GENERATION_PROVIDER, GENERATION_MODEL)

    raise ValueError(f"Unknown LLM role: {role!r}. Must be 'merge_batch', 'judge', or 'generation'.")


# ── Backward-compat wrappers ─────────────────────────────────────────────────
# Keep these so existing callers (script_writer, article_writer, main.py) need
# no changes.  They simply delegate to get_llm_client().

def get_script_llm_client() -> Optional[LLMClient]:
    """台本生成用クライアント (generation role)."""
    return get_llm_client("generation")


def get_article_llm_client() -> Optional[LLMClient]:
    """記事生成用クライアント (generation role)."""
    return get_llm_client("generation")


def get_cluster_llm_client() -> Optional[LLMClient]:
    """クラスタリング判定用クライアント (merge_batch role)."""
    return get_llm_client("merge_batch")


def get_judge_llm_client() -> Optional[LLMClient]:
    """Gemini 編集審判用クライアント (judge role).

    Always uses Gemini API regardless of LLM_PROVIDER.
    Model is resolved via model_registry: models.list → fallback chain.
    Returns None if GEMINI_API_KEY is not set.
    """
    if not GEMINI_API_KEY:
        return None
    from src.llm.gemini import GeminiClient
    from src.llm.model_registry import get_judge_model_resolution
    resolution = get_judge_model_resolution(
        GEMINI_API_KEY, JUDGE_MODEL, GEMINI_JUDGE_FALLBACK_MODELS
    )
    return GeminiClient(GEMINI_API_KEY, resolution.resolved_model)
