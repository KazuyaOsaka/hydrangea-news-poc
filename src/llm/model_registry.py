"""model_registry.py — Gemini judge model resolution and startup health check.

Resolves the requested judge model against the list of actually-available Gemini
models at startup.  Records requested_model, resolved_model, and resolution_reason
so the full resolution chain is visible in run_summary.json.

Design:
  1. At startup (or first judge call) call models.list once.
  2. If requested model is available → use it unchanged.
  3. If not available → walk a configurable fallback priority list and use the
     first available fallback.
  4. If models.list itself fails (network error, bad key) → use the requested
     model as-is and surface the uncertainty in resolution_reason.
  5. Resolution result is cached for the lifetime of the process so models.list
     is never called more than once per run.

Error types raised during judge calls are classified in gemini_judge.py, not here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.shared.logger import get_logger

logger = get_logger(__name__)

# Priority-ordered fallback list: newest lite → stable lite → flash
_DEFAULT_FALLBACK_PRIORITY: list[str] = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.5-flash",
]


@dataclass
class ModelResolution:
    """Result of judge model resolution.

    Attributes:
        requested_model:      The model name from env / config before resolution.
        resolved_model:       The actual model name that will be used.
        resolution_reason:    Short token explaining why resolved_model was chosen.
        available_models:     Snapshot of models returned by models.list (excluded
                              from repr to avoid log noise).
    """
    requested_model: str
    resolved_model: str
    resolution_reason: str
    available_models: list[str] = field(default_factory=list, repr=False)


def _list_available_models(api_key: str) -> list[str]:
    """Call Gemini models.list and return bare model names (without 'models/' prefix)."""
    try:
        from google import genai  # type: ignore[import]
        client = genai.Client(api_key=api_key)
        raw_models = client.models.list()
        names: list[str] = []
        for m in raw_models:
            name: str = getattr(m, "name", "") or ""
            if name.startswith("models/"):
                name = name[len("models/"):]
            if name:
                names.append(name)
        logger.info(
            f"[ModelRegistry] models.list returned {len(names)} models."
        )
        return names
    except Exception as exc:
        logger.warning(
            f"[ModelRegistry] models.list call failed — "
            f"cannot verify model availability: {exc}"
        )
        return []


def resolve_judge_model(
    api_key: str,
    requested: str,
    fallback_list: list[str] | None = None,
) -> ModelResolution:
    """Resolve the requested judge model name against actually-available models.

    Args:
        api_key:       Gemini API key used to call models.list.
        requested:     Model name from config / env.
        fallback_list: Priority-ordered candidate fallback names.  Uses
                       _DEFAULT_FALLBACK_PRIORITY when None.

    Returns:
        ModelResolution with requested_model, resolved_model, resolution_reason.
    """
    fallbacks = fallback_list if fallback_list is not None else _DEFAULT_FALLBACK_PRIORITY
    available = _list_available_models(api_key)

    if not available:
        # models.list unavailable — cannot verify; use requested as-is.
        logger.warning(
            f"[ModelRegistry] models.list returned no results. "
            f"Using requested model '{requested}' without verification."
        )
        return ModelResolution(
            requested_model=requested,
            resolved_model=requested,
            resolution_reason="models_list_unavailable:using_requested",
            available_models=[],
        )

    # Requested model is available — best case.
    if requested in available:
        logger.info(
            f"[ModelRegistry] Requested judge model '{requested}' confirmed available."
        )
        return ModelResolution(
            requested_model=requested,
            resolved_model=requested,
            resolution_reason="requested_model_available",
            available_models=available,
        )

    logger.warning(
        f"[ModelRegistry] Requested judge model '{requested}' NOT found in "
        f"available models ({len(available)} total). "
        f"Trying fallback list: {fallbacks}"
    )

    # Walk fallback priority list.
    for fb in fallbacks:
        if fb in available:
            logger.info(
                f"[ModelRegistry] Resolved judge model: "
                f"'{requested}' → '{fb}' (fallback_from_unavailable_requested)"
            )
            return ModelResolution(
                requested_model=requested,
                resolved_model=fb,
                resolution_reason="fallback_from_unavailable_requested",
                available_models=available,
            )

    # No fallback found either — use requested and let the call fail with
    # a clear model_not_found error.
    logger.error(
        f"[ModelRegistry] Neither '{requested}' nor any fallback "
        f"({fallbacks}) found in available models. "
        f"Will attempt with '{requested}' — expect model_not_found errors."
    )
    return ModelResolution(
        requested_model=requested,
        resolved_model=requested,
        resolution_reason="no_fallback_available:using_requested",
        available_models=available,
    )


# ── Module-level cache ─────────────────────────────────────────────────────────
# Populated on first call to get_judge_model_resolution().
# Cleared by clear_resolution_cache() in tests.

_cached_resolution: ModelResolution | None = None


def get_judge_model_resolution(
    api_key: str,
    requested: str,
    fallback_list: list[str] | None = None,
) -> ModelResolution:
    """Return cached model resolution, resolving on first call.

    The cache is keyed on ``requested``: if the requested model changes (e.g.
    after an env reload or between test runs) the cache is invalidated and
    models.list is called again.  This prevents a stale resolution from a
    prior session silently mapping to the wrong model.
    """
    global _cached_resolution
    if _cached_resolution is not None and _cached_resolution.requested_model == requested:
        return _cached_resolution
    if _cached_resolution is not None:
        logger.info(
            f"[ModelRegistry] Requested model changed "
            f"(cached={_cached_resolution.requested_model!r}, new={requested!r}): "
            f"invalidating resolution cache."
        )
    _cached_resolution = resolve_judge_model(api_key, requested, fallback_list)
    logger.info(
        f"[ModelRegistry] Judge model resolution cached: "
        f"requested={_cached_resolution.requested_model!r}, "
        f"resolved={_cached_resolution.resolved_model!r}, "
        f"reason={_cached_resolution.resolution_reason!r}"
    )
    return _cached_resolution


def clear_resolution_cache() -> None:
    """Clear the cached resolution.  Use in tests to force re-resolution."""
    global _cached_resolution
    _cached_resolution = None


# ── Trivial role resolutions (no models.list call needed) ─────────────────────
# For non-judge roles the model is taken directly from config — no API check.

def get_generation_model_resolution() -> ModelResolution:
    """Return the configured generation role model as a trivial ModelResolution."""
    from src.shared.config import GENERATION_MODEL, GENERATION_PROVIDER
    label = f"generation:{GENERATION_PROVIDER}"
    return ModelResolution(
        requested_model=GENERATION_MODEL,
        resolved_model=GENERATION_MODEL,
        resolution_reason="role_config_direct",
        available_models=[],
    )


def get_merge_batch_model_resolution() -> ModelResolution:
    """Return the configured merge_batch role model as a trivial ModelResolution."""
    from src.shared.config import MERGE_BATCH_MODEL, MERGE_BATCH_PROVIDER
    label = f"merge_batch:{MERGE_BATCH_PROVIDER}"
    return ModelResolution(
        requested_model=MERGE_BATCH_MODEL,
        resolved_model=MERGE_BATCH_MODEL,
        resolution_reason="role_config_direct",
        available_models=[],
    )
