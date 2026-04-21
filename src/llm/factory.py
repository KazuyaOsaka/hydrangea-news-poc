"""factory.py — Role-based LLM client factory with purpose-driven routing.

Routing strategy:
  Lightweight (high-throughput): garbage_filter, event_builder (cluster)
    → TIER4 (gemini-2.5-flash-lite) fixed; same-model retry only (no upward fallback).
    Rationale: already the cheapest tier — escalating would waste the premium quota.

  Quality (high-reasoning): elite_judge, script_writer, article_writer
    → TIER1 → TIER2 → TIER3 → TIER4 full 4-tier fallback.
    Rationale: accuracy matters; escalate only after per-tier retries are exhausted.

Fallback priority (quality path):
  [1] gemini-3.1-flash-lite-preview  (TIER1)
  [2] gemini-3-flash-preview         (TIER2)
  [3] gemini-2.5-flash               (TIER3)
  [4] gemini-2.5-flash-lite          (TIER4)

Per-tier policy: up to _MAX_ATTEMPTS_PER_TIER retries with exponential backoff
(1s→2s→4s) on 429/RESOURCE_EXHAUSTED or 503/UNAVAILABLE, then next tier.
If all tiers are exhausted, RuntimeError is raised — no silent degradation.

Resolution path: .env → config.py → factory.py
No hardcoded model strings in business logic.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from src.llm.base import LLMClient
from src.llm.retry import is_retryable
from src.shared.config import (
    GEMINI_API_KEY,
    GEMINI_CALL_INTERVAL_SEC,
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
_INITIAL_DELAY_SEC = 15.0
_MAX_DELAY_SEC = 120.0

# 429対策: 最大同時API呼び出し数を3に制限 (15 RPM制限を安全に回避)
_API_SEMAPHORE = threading.Semaphore(3)


class TieredGeminiClient(LLMClient):
    """GeminiClient that walks through a provided tier list on quota exhaustion.

    Per-tier policy: up to _MAX_ATTEMPTS_PER_TIER retries with exponential
    backoff on 429/RESOURCE_EXHAUSTED or 503/UNAVAILABLE errors.
    After all attempts for a tier fail, the next tier is tried.
    If all tiers are exhausted, RuntimeError is raised.

    Single-element tier list → same-model retry only (no fallback).
    """

    def __init__(self, api_key: str, tiers: list[str]) -> None:
        self._api_key = api_key
        self._tiers = tiers
        self._last_call_time: float = 0.0

    def _throttle(self) -> None:
        """Enforce GEMINI_CALL_INTERVAL_SEC between consecutive API calls."""
        elapsed = time.time() - self._last_call_time
        wait = GEMINI_CALL_INTERVAL_SEC - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_call_time = time.time()

    def generate(self, prompt: str) -> str:
        from google import genai

        client = genai.Client(api_key=self._api_key)
        last_exc: Exception | None = None

        for tier_idx, model in enumerate(self._tiers, start=1):
            delay = _INITIAL_DELAY_SEC
            for attempt in range(_MAX_ATTEMPTS_PER_TIER):
                try:
                    with _API_SEMAPHORE:
                        self._throttle()
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
                        delay = min(delay * 2, _MAX_DELAY_SEC)
                    else:
                        if tier_idx < len(self._tiers):
                            next_model = self._tiers[tier_idx]
                            next_label = f"tier {tier_idx + 1} ({next_model})"
                        else:
                            next_label = "none (all tiers exhausted)"
                        logger.warning(
                            f"[TieredGemini] FAIL tier={tier_idx} model={model} — "
                            f"all {_MAX_ATTEMPTS_PER_TIER} attempts exhausted. "
                            f"Next: {next_label}. Error: {str(exc)[:120]}"
                        )

        assert last_exc is not None
        raise RuntimeError(
            f"All {len(self._tiers)} Gemini tier(s) exhausted. "
            f"Models tried: {self._tiers}. "
            f"Last error: {last_exc}"
        ) from last_exc


# ── Internal factory helpers ─────────────────────────────────────────────────

def _make_lightweight_client() -> Optional[LLMClient]:
    """大量処理用クライアント: TIER4 (gemini-2.5-flash-lite) 固定。

    Garbage Filter / Event Builder 等の高スループット工程専用。
    フォールバックなし — TIER4 で最大 _MAX_ATTEMPTS_PER_TIER 回リトライ後に失敗。
    既に最廉価 Tier のため上位へのエスカレーションは不要。
    """
    if not GEMINI_API_KEY:
        return None
    return TieredGeminiClient(GEMINI_API_KEY, [GEMINI_MODEL_TIER4])


def _make_quality_client() -> Optional[LLMClient]:
    """高品質推論用クライアント: TIER1→TIER2→TIER3→TIER4 完全4段フォールバック。

    Elite Judge / Script Writer / Article Writer 等の高精度工程専用。
    TIER1 から順に試行し、429/503 が規定回数を超えた段階で次の Tier へ降格。
    """
    if not GEMINI_API_KEY:
        return None
    return TieredGeminiClient(
        GEMINI_API_KEY,
        [GEMINI_MODEL_TIER1, GEMINI_MODEL_TIER2, GEMINI_MODEL_TIER3, GEMINI_MODEL_TIER4],
    )


def _make_client(provider: str, model: str, quality: bool = False) -> Optional[LLMClient]:
    """Construct an LLMClient for the given provider + model pair.

    For Gemini, `model` is ignored — routing is determined by `quality`:
      quality=True  → _make_quality_client()  (TIER1→TIER4 full fallback)
      quality=False → _make_lightweight_client() (TIER4 retry-only)
    """
    if provider == "gemini":
        return _make_quality_client() if quality else _make_lightweight_client()

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
        Configured LLMClient, or None if the provider is not configured.

    Raises:
        ValueError: If role is not recognised.
    """
    if role == "merge_batch":
        # Event Builder / cluster: lightweight (TIER4 retry-only)
        return _make_client(MERGE_BATCH_PROVIDER, MERGE_BATCH_MODEL, quality=False)

    if role == "judge":
        return get_judge_llm_client()

    if role == "generation":
        # Script / Article Writer: quality (TIER1→TIER4 full fallback)
        return _make_client(GENERATION_PROVIDER, GENERATION_MODEL, quality=True)

    raise ValueError(
        f"Unknown LLM role: {role!r}. Must be 'merge_batch', 'judge', or 'generation'."
    )


# ── Named client accessors (called by business logic) ───────────────────────

def get_garbage_filter_client() -> Optional[LLMClient]:
    """Gate 1 Garbage Filter 用クライアント — 大量処理ルート。

    TIER4 (gemini-2.5-flash-lite) 固定、同一モデルでリトライのみ。
    フォールバック不要（既に最廉価 Tier）。
    """
    return _make_lightweight_client()


def get_cluster_llm_client() -> Optional[LLMClient]:
    """Event Builder / cluster post-merge 用クライアント — 大量処理ルート。

    TIER4 (gemini-2.5-flash-lite) 固定、同一モデルでリトライのみ。
    """
    return get_llm_client("merge_batch")


def get_judge_llm_client() -> Optional[LLMClient]:
    """Elite Judge 用クライアント — 高品質推論ルート。

    TIER1 (gemini-3.1-flash-lite-preview) から開始し、
    TIER1→TIER2→TIER3→TIER4 の完全4段フォールバック。
    """
    return _make_quality_client()


def get_script_llm_client() -> Optional[LLMClient]:
    """Script Writer 用クライアント — 高品質推論ルート。

    TIER1 (gemini-3.1-flash-lite-preview) から開始し、
    TIER1→TIER2→TIER3→TIER4 の完全4段フォールバック。
    """
    return _make_quality_client()


def get_article_llm_client() -> Optional[LLMClient]:
    """Article Writer 用クライアント — 高品質推論ルート。"""
    return get_llm_client("generation")


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
