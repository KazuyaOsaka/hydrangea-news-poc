"""factory.py — Role-based LLM client factory with 4-tier Gemini fallback.

Business logic must call get_llm_client(role) with one of:
  "merge_batch"  — cluster post-merge LLM (lightweight)
  "judge"        — editorial judgment (always Gemini)
  "generation"   — script + article generation

Gemini roles use a 4-tier model hierarchy defined in .env (GEMINI_MODEL_TIER1-4).
Each tier is retried up to 3 times with exponential backoff (1s→2s→4s) on
429/RESOURCE_EXHAUSTED or 503/UNAVAILABLE errors before falling to the next tier.
If all tiers are exhausted, RuntimeError is raised — no silent degradation.

Resolution path: .env → config.py → factory.py
No hardcoded model strings in business logic.
"""
from __future__ import annotations

import time
from typing import Optional

from src.llm.base import LLMClient
from src.llm.retry import is_retryable
from src.shared.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL_TIER1,
    GEMINI_MODEL_TIER2,
    GEMINI_MODEL_TIER3,
    GEMINI_MODEL_TIER4,
    GEMINI_MODEL_TIERS,
    GENERATION_MODEL,
    GENERATION_PROVIDER,
    GROQ_API_KEY,
    MERGE_BATCH_MODEL,
    MERGE_BATCH_PROVIDER,
    OLLAMA_BASE_URL,
)
from src.shared.logger import get_logger

logger = get_logger(__name__)

_MAX_ATTEMPTS_PER_TIER = 3
_INITIAL_DELAY_SEC = 1.0


class TieredGeminiClient(LLMClient):
    """GeminiClient that walks TIER1→TIER4 on quota exhaustion.

    Per-tier policy: up to _MAX_ATTEMPTS_PER_TIER retries with exponential
    backoff on 429/RESOURCE_EXHAUSTED or 503/UNAVAILABLE errors.
    After all attempts for a tier fail, the next tier is tried.
    If all tiers are exhausted, RuntimeError is raised.
    """

    def __init__(self, api_key: str, tiers: list[str]) -> None:
        self._api_key = api_key
        self._tiers = tiers

    def generate(self, prompt: str) -> str:
        from google import genai

        client = genai.Client(api_key=self._api_key)
        last_exc: Exception | None = None

        for tier_idx, model in enumerate(self._tiers, start=1):
            delay = _INITIAL_DELAY_SEC
            for attempt in range(_MAX_ATTEMPTS_PER_TIER):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                    )
                    if tier_idx > 1 or attempt > 0:
                        logger.info(
                            f"[TieredGemini] Success: tier={tier_idx} model={model} "
                            f"attempt={attempt + 1}/{_MAX_ATTEMPTS_PER_TIER}"
                        )
                    return response.text.strip()
                except Exception as exc:
                    if not is_retryable(exc):
                        raise
                    last_exc = exc
                    if attempt < _MAX_ATTEMPTS_PER_TIER - 1:
                        logger.warning(
                            f"[TieredGemini] tier={tier_idx} model={model} "
                            f"attempt={attempt + 1}/{_MAX_ATTEMPTS_PER_TIER} quota error — "
                            f"retrying in {delay:.0f}s: {str(exc)[:120]}"
                        )
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.warning(
                            f"[TieredGemini] tier={tier_idx} model={model} all "
                            f"{_MAX_ATTEMPTS_PER_TIER} attempts exhausted — "
                            f"falling to tier {tier_idx + 1}: {str(exc)[:120]}"
                        )

        assert last_exc is not None
        raise RuntimeError(
            f"All {len(self._tiers)} Gemini tiers exhausted. "
            f"Models tried: {self._tiers}. "
            f"Last error: {last_exc}"
        ) from last_exc


def _make_triage_client() -> Optional[LLMClient]:
    """Gate 1/2/3・選別工程専用クライアント (TIER2=3-flash-preview を物理除外).

    TIER1 (3.1-flash-lite, RPD 500) → TIER3 → TIER4 の順でフォールバックする。
    TIER2 (3-flash-preview, RPD 20) は write_script 専用枠として絶対に呼ばない。
    """
    if not GEMINI_API_KEY:
        return None
    return TieredGeminiClient(
        GEMINI_API_KEY,
        [GEMINI_MODEL_TIER1, GEMINI_MODEL_TIER3, GEMINI_MODEL_TIER4],
    )


def _make_tiered_gemini_client() -> Optional[LLMClient]:
    return _make_triage_client()


def _make_client(provider: str, model: str) -> Optional[LLMClient]:
    """Construct an LLMClient for the given provider + model pair.

    For the Gemini provider, `model` is ignored — TieredGeminiClient uses
    GEMINI_MODEL_TIERS from config instead.
    """
    if provider == "gemini":
        return _make_tiered_gemini_client()

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
        (e.g. GEMINI_API_KEY missing).

    Raises:
        ValueError: If role is not recognised.
    """
    if role == "merge_batch":
        return _make_client(MERGE_BATCH_PROVIDER, MERGE_BATCH_MODEL)

    if role == "judge":
        return get_judge_llm_client()

    if role == "generation":
        return _make_client(GENERATION_PROVIDER, GENERATION_MODEL)

    raise ValueError(
        f"Unknown LLM role: {role!r}. Must be 'merge_batch', 'judge', or 'generation'."
    )


# ── Backward-compat wrappers ─────────────────────────────────────────────────

def get_script_llm_client() -> Optional[LLMClient]:
    """台本執筆専用クライアント (TIER2=3-flash-preview を優先使用)."""
    if not GEMINI_API_KEY:
        return None
    return TieredGeminiClient(
        GEMINI_API_KEY,
        [GEMINI_MODEL_TIER2, GEMINI_MODEL_TIER3, GEMINI_MODEL_TIER4],
    )


def get_article_llm_client() -> Optional[LLMClient]:
    return get_llm_client("generation")


def get_cluster_llm_client() -> Optional[LLMClient]:
    return get_llm_client("merge_batch")


def get_judge_llm_client() -> Optional[LLMClient]:
    """Gemini 編集審判用クライアント (TIER2=3-flash 除外).

    Always uses Gemini _make_triage_client regardless of LLM_PROVIDER.
    Returns None if GEMINI_API_KEY is not set.
    """
    return _make_triage_client()


def get_garbage_filter_client() -> Optional[LLMClient]:
    """Gate 1 Garbage Filter 用クライアント (TIER2=3-flash 除外).

    TIER1 (3.1-flash-lite, RPD 500) → TIER3 → TIER4 の順でフォールバック。
    Returns None if GEMINI_API_KEY is not set.
    """
    return _make_triage_client()


# ── Tier connectivity verification ──────────────────────────────────────────

def verify_tier_connectivity(probe_prompt: str = "Reply with the single word OK.") -> dict:
    """Verify that GEMINI_API_KEY can reach each tier model.

    Sends `probe_prompt` to each tier in GEMINI_MODEL_TIERS and records
    success/failure.  Does NOT use the tiered fallback — each tier is tested
    independently so failures are individually visible.

    Returns:
        dict mapping model name → {"ok": bool, "response": str | None, "error": str | None}

    Raises:
        RuntimeError: If GEMINI_API_KEY is not set.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set — cannot verify connectivity.")

    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)
    results: dict = {}

    for tier_idx, model in enumerate(GEMINI_MODEL_TIERS, start=1):
        logger.info(f"[VerifyTier] Probing TIER{tier_idx}: {model}")
        try:
            response = client.models.generate_content(
                model=model,
                contents=probe_prompt,
            )
            text = response.text.strip()
            results[model] = {"tier": tier_idx, "ok": True, "response": text, "error": None}
            logger.info(f"[VerifyTier] TIER{tier_idx} {model}: OK → {text!r}")
        except Exception as exc:
            results[model] = {"tier": tier_idx, "ok": False, "response": None, "error": str(exc)}
            logger.error(f"[VerifyTier] TIER{tier_idx} {model}: FAILED → {exc}")

    ok_count = sum(1 for v in results.values() if v["ok"])
    logger.info(
        f"[VerifyTier] Result: {ok_count}/{len(GEMINI_MODEL_TIERS)} tiers reachable. "
        f"Models: {GEMINI_MODEL_TIERS}"
    )
    return results


if __name__ == "__main__":
    import json
    results = verify_tier_connectivity()
    print(json.dumps(results, ensure_ascii=False, indent=2))
