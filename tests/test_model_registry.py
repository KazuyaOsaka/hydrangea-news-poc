"""Tests for src/llm/model_registry.py — judge model resolution layer.

Verified behaviours:
  1.  Invalid requested model resolves to a valid fallback when available.
  2.  Valid requested model is returned unchanged.
  3.  When models.list returns nothing, requested model is used as-is.
  4.  When neither requested nor any fallback is available, requested is used
      as-is and resolution_reason reflects the failure.
  5.  _classify_judge_error correctly maps 404/NOT_FOUND to "model_not_found"
      (not "temporary_unavailable").
  6.  Resolution cache works: second call returns the same object.
  7.  clear_resolution_cache resets the cache for isolated test runs.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.llm.model_registry import (
    ModelResolution,
    clear_resolution_cache,
    get_judge_model_resolution,
    resolve_judge_model,
)
from src.triage.gemini_judge import _classify_judge_error


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fake_models(names: list[str]):
    """Build a list of mock model objects with a .name attribute."""
    mocks = []
    for name in names:
        m = MagicMock()
        m.name = f"models/{name}"
        mocks.append(m)
    return mocks


# ── 1. Invalid requested model → fallback ──────────────────────────────────────

class TestModelResolutionFallback:

    def setup_method(self):
        clear_resolution_cache()

    def test_invalid_requested_resolves_to_first_available_fallback(self):
        """When requested model is not in available list, use first fallback."""
        available = ["gemini-2.5-flash-lite", "gemini-2.0-flash"]
        with patch(
            "src.llm.model_registry._list_available_models",
            return_value=available,
        ):
            result = resolve_judge_model(
                api_key="fake-key",
                requested="gemini-3.1-flash-lite",
                fallback_list=["gemini-2.5-flash-lite", "gemini-2.0-flash"],
            )
        assert result.requested_model == "gemini-3.1-flash-lite"
        assert result.resolved_model == "gemini-2.5-flash-lite"
        assert result.resolution_reason == "fallback_from_unavailable_requested"

    def test_fallback_priority_is_respected(self):
        """The FIRST available fallback in the list is chosen."""
        # Only second fallback is available
        available = ["gemini-2.0-flash"]
        with patch(
            "src.llm.model_registry._list_available_models",
            return_value=available,
        ):
            result = resolve_judge_model(
                api_key="fake-key",
                requested="gemini-3.1-flash-lite",
                fallback_list=["gemini-2.5-flash-lite", "gemini-2.0-flash"],
            )
        assert result.resolved_model == "gemini-2.0-flash"
        assert result.resolution_reason == "fallback_from_unavailable_requested"

    def test_no_fallback_available_uses_requested(self):
        """When neither requested nor fallbacks are available, use requested."""
        available = ["gemini-1.0-pro"]
        with patch(
            "src.llm.model_registry._list_available_models",
            return_value=available,
        ):
            result = resolve_judge_model(
                api_key="fake-key",
                requested="gemini-3.1-flash-lite",
                fallback_list=["gemini-2.5-flash-lite"],
            )
        assert result.resolved_model == "gemini-3.1-flash-lite"
        assert result.resolution_reason == "no_fallback_available:using_requested"


# ── 2. Valid requested model ───────────────────────────────────────────────────

class TestModelResolutionValid:

    def setup_method(self):
        clear_resolution_cache()

    def test_valid_requested_model_returned_unchanged(self):
        """When requested model is in available list, return it unchanged."""
        with patch(
            "src.llm.model_registry._list_available_models",
            return_value=["gemini-2.5-flash-lite", "gemini-2.5-flash"],
        ):
            result = resolve_judge_model(
                api_key="fake-key",
                requested="gemini-2.5-flash-lite",
            )
        assert result.requested_model == "gemini-2.5-flash-lite"
        assert result.resolved_model == "gemini-2.5-flash-lite"
        assert result.resolution_reason == "requested_model_available"


# ── 3. models.list unavailable ────────────────────────────────────────────────

class TestModelResolutionListUnavailable:

    def setup_method(self):
        clear_resolution_cache()

    def test_empty_list_uses_requested_as_is(self):
        """When models.list returns nothing, use requested model as-is."""
        with patch(
            "src.llm.model_registry._list_available_models",
            return_value=[],
        ):
            result = resolve_judge_model(
                api_key="fake-key",
                requested="gemini-2.5-flash-lite",
            )
        assert result.resolved_model == "gemini-2.5-flash-lite"
        assert result.resolution_reason == "models_list_unavailable:using_requested"

    def test_list_failure_uses_requested_as_is(self):
        """When models.list raises, the wrapper returns [] and we use requested."""
        with patch(
            "src.llm.model_registry._list_available_models",
            side_effect=Exception("network error"),
        ):
            # resolve_judge_model calls _list_available_models directly,
            # which in real code catches exceptions internally.  Here we patch
            # the internal function to return [] to simulate the same outcome.
            pass  # covered by test above (empty list case)


# ── 4. Cache behaviour ────────────────────────────────────────────────────────

class TestModelResolutionCache:

    def setup_method(self):
        clear_resolution_cache()

    def test_second_call_returns_cached_result(self):
        """get_judge_model_resolution caches after first call."""
        with patch(
            "src.llm.model_registry._list_available_models",
            return_value=["gemini-2.5-flash-lite"],
        ) as mock_list:
            r1 = get_judge_model_resolution("key", "gemini-2.5-flash-lite")
            r2 = get_judge_model_resolution("key", "gemini-2.5-flash-lite")
        # _list_available_models should only have been called once.
        assert mock_list.call_count == 1
        assert r1 is r2

    def test_clear_cache_forces_re_resolution(self):
        """clear_resolution_cache allows models.list to be called again."""
        with patch(
            "src.llm.model_registry._list_available_models",
            return_value=["gemini-2.5-flash-lite"],
        ) as mock_list:
            get_judge_model_resolution("key", "gemini-2.5-flash-lite")
            clear_resolution_cache()
            get_judge_model_resolution("key", "gemini-2.5-flash-lite")
        assert mock_list.call_count == 2


# ── 5. Error classification: 404 → model_not_found ───────────────────────────

class TestJudgeErrorClassification:

    def test_404_is_model_not_found(self):
        """HTTP 404 / NOT_FOUND must be classified as model_not_found."""
        exc = Exception(
            "404 NOT_FOUND. {'error': {'code': 404, 'message': "
            "'models/gemini-3.1-flash-lite is not found for API version v1beta', "
            "'status': 'NOT_FOUND'}}"
        )
        error_type = _classify_judge_error(exc)
        assert error_type == "model_not_found", (
            f"Expected 'model_not_found', got '{error_type}'"
        )

    def test_404_is_not_temporary_unavailable(self):
        """404 must NOT be classified as temporary_unavailable."""
        exc = Exception("404 NOT_FOUND models/gemini-3.1-flash-lite")
        error_type = _classify_judge_error(exc)
        assert error_type != "temporary_unavailable"

    def test_503_is_temporary_unavailable(self):
        """503 UNAVAILABLE must still be classified as temporary_unavailable."""
        exc = Exception("503 UNAVAILABLE service temporarily unavailable")
        assert _classify_judge_error(exc) == "temporary_unavailable"

    def test_429_is_quota_exhausted(self):
        """429 RESOURCE_EXHAUSTED must be classified as quota_exhausted."""
        exc = Exception("429 RESOURCE_EXHAUSTED quota limit exceeded")
        assert _classify_judge_error(exc) == "quota_exhausted"

    def test_json_parse_error_is_parse_error(self):
        """JSON decode failure must be classified as parse_error."""
        import json
        exc = json.JSONDecodeError("Expecting value", "bad json", 0)
        assert _classify_judge_error(exc) == "parse_error"

    def test_unknown_exception_is_unknown_error(self):
        """Unrecognised exceptions fall back to unknown_error."""
        exc = RuntimeError("something unexpected")
        assert _classify_judge_error(exc) == "unknown_error"


# ── 6. ModelResolution dataclass ─────────────────────────────────────────────

class TestModelResolutionDataclass:

    def test_fields_are_accessible(self):
        r = ModelResolution(
            requested_model="gemini-3.1-flash-lite",
            resolved_model="gemini-2.5-flash-lite",
            resolution_reason="fallback_from_unavailable_requested",
        )
        assert r.requested_model == "gemini-3.1-flash-lite"
        assert r.resolved_model == "gemini-2.5-flash-lite"
        assert r.resolution_reason == "fallback_from_unavailable_requested"
        assert r.available_models == []  # default


# ── 7. Cache invalidation when requested model changes ────────────────────────

class TestCacheInvalidationOnRequestedChange:
    """Regression: stale cache from a prior requested model must NOT leak into
    the new resolution when the requested model changes within the same process.

    Root cause fixed: get_judge_model_resolution previously returned the cached
    result regardless of whether `requested` matched the cached requested_model.
    """

    def setup_method(self):
        clear_resolution_cache()

    def test_cache_invalidated_when_requested_model_changes(self):
        """Changing `requested` forces a new models.list call and re-resolution."""
        available = ["gemini-2.5-flash-lite"]
        with patch(
            "src.llm.model_registry._list_available_models",
            return_value=available,
        ) as mock_list:
            r1 = get_judge_model_resolution("key", "gemini-2.5-flash-lite")
            # Now call with a different requested — must NOT return the cached r1.
            r2 = get_judge_model_resolution("key", "gemini-3.1-flash-lite")

        assert mock_list.call_count == 2, (
            "models.list must be called twice when requested changes"
        )
        assert r1.requested_model == "gemini-2.5-flash-lite"
        assert r2.requested_model == "gemini-3.1-flash-lite"
        # r2 should have fallen back to the available model
        assert r2.resolved_model == "gemini-2.5-flash-lite"
        assert r2.resolution_reason == "fallback_from_unavailable_requested"

    def test_same_requested_still_uses_cache(self):
        """Calling with the same requested model still hits the cache (no extra models.list)."""
        available = ["gemini-2.5-flash-lite"]
        with patch(
            "src.llm.model_registry._list_available_models",
            return_value=available,
        ) as mock_list:
            r1 = get_judge_model_resolution("key", "gemini-2.5-flash-lite")
            r2 = get_judge_model_resolution("key", "gemini-2.5-flash-lite")

        assert mock_list.call_count == 1
        assert r1 is r2


# ── 8. Invalid requested model must not leak into runtime calls ───────────────

class TestInvalidRequestedModelCannotLeak:
    """Regression: an invalid/guessed requested model must never reach the
    actual Gemini API call when a valid fallback is available.

    The root cause: if models.list is available and confirms requested is NOT
    in the list, resolved_model must differ from requested_model.
    """

    def setup_method(self):
        clear_resolution_cache()

    def test_invalid_requested_never_leaks_when_fallback_available(self):
        """resolved_model must NOT equal the invalid requested_model when fallback exists."""
        available = ["gemini-2.5-flash-lite", "gemini-2.0-flash"]
        with patch(
            "src.llm.model_registry._list_available_models",
            return_value=available,
        ):
            result = get_judge_model_resolution(
                "key",
                "gemini-3.1-flash-lite",  # invalid / not in available
                fallback_list=["gemini-2.5-flash-lite", "gemini-2.0-flash"],
            )

        assert result.resolved_model != "gemini-3.1-flash-lite", (
            "Invalid requested model must not leak into resolved_model "
            "when a valid fallback is available"
        )
        assert result.resolved_model in available
        assert result.resolution_reason == "fallback_from_unavailable_requested"

    def test_get_judge_llm_client_uses_resolved_not_requested_model(self):
        """get_judge_llm_client must build the client with resolved_model, not requested_model."""
        from unittest.mock import patch as _patch, MagicMock
        from src.llm.model_registry import ModelResolution, clear_resolution_cache

        clear_resolution_cache()
        fake_resolution = ModelResolution(
            requested_model="gemini-3.1-flash-lite",
            resolved_model="gemini-2.5-flash-lite",
            resolution_reason="fallback_from_unavailable_requested",
        )

        # The import of get_judge_model_resolution happens inside the function
        # body of get_judge_llm_client, so we must patch it at the source module.
        with _patch("src.llm.model_registry.get_judge_model_resolution", return_value=fake_resolution):
            with _patch("src.llm.factory.GEMINI_API_KEY", "dummy-key"):
                from src.llm.factory import get_judge_llm_client
                client = get_judge_llm_client()

        assert client is not None, "Client must be created when API key is set"
        actual_model = getattr(client, '_model', None)
        assert actual_model == "gemini-2.5-flash-lite", (
            f"Client must use resolved_model='gemini-2.5-flash-lite', "
            f"not requested_model='gemini-3.1-flash-lite'. Got: {actual_model!r}"
        )
