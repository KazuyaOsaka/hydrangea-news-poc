"""retry.py — LLM call retry with exponential backoff.

Policy: 3s → 9s → 27s → 60s → 60s (×3 per retry, capped at 60s), max 5 attempts.
Retryable: 429 / RESOURCE_EXHAUSTED, 503 / UNAVAILABLE.
Non-retryable: 404 / NOT_FOUND, JSON parse errors, unknown errors.
"""
from __future__ import annotations

import time
from typing import Callable, TypeVar

from src.shared.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

_RETRYABLE_MARKERS = ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")


def is_retryable(exc: Exception) -> bool:
    """Return True if the exception represents a transient quota/service error."""
    msg = str(exc)
    return any(marker in msg for marker in _RETRYABLE_MARKERS)


def call_with_retry(
    fn: Callable[[], T],
    role: str,
    max_attempts: int = 5,
    initial_delay: float = 3.0,
    delay_multiplier: float = 3.0,
    max_delay: float = 60.0,
) -> tuple[T, int]:
    """Call fn with exponential backoff on retryable errors.

    Args:
        fn:               Zero-argument callable to invoke.
        role:             Role label for logging ("judge", "generation", "merge_batch").
        max_attempts:     Maximum total attempts (default 5).
        initial_delay:    Seconds before first retry (default 3s).
        delay_multiplier: Backoff multiplier per retry (default 3 → 3s, 9s, 27s, 60s…).
        max_delay:        Cap on wait time in seconds (default 60s).

    Returns:
        (result, retry_count) — retry_count is 0 on first-try success.

    Raises:
        Last exception if all retryable attempts fail, or immediately for
        non-retryable errors.
    """
    delay = initial_delay
    last_exc: Exception | None = None

    for attempt in range(max_attempts):
        try:
            result = fn()
            if attempt > 0:
                logger.info(
                    f"[Retry:{role}] Succeeded on attempt {attempt + 1}/{max_attempts}"
                )
            return result, attempt
        except Exception as exc:
            if not is_retryable(exc):
                raise
            last_exc = exc
            if attempt < max_attempts - 1:
                logger.warning(
                    f"[Retry:{role}] Attempt {attempt + 1}/{max_attempts} failed "
                    f"({type(exc).__name__}: {str(exc)[:120]}). "
                    f"Retrying in {delay:.0f}s"
                )
                time.sleep(delay)
                delay = min(delay * delay_multiplier, max_delay)
            else:
                logger.warning(
                    f"[Retry:{role}] All {max_attempts} attempts exhausted. "
                    f"Last error: {str(exc)[:200]}"
                )

    assert last_exc is not None
    raise last_exc
