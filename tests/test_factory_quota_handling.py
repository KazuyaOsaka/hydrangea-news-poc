"""TieredGeminiClient の 429 即フォールバック挙動を検証する。

Google 公式仕様では 429 (RESOURCE_EXHAUSTED) で失敗したリクエストもクォータ
消費に計上されるため、同一モデルでのリトライは無意味かつ有害。
このテストは「429 では同一モデルにリトライせず即座に次の Tier へ進む」ことを
モックで検証する。一方 503 等の一時的エラーでは従来通り
_MAX_ATTEMPTS_PER_TIER 回までリトライされること、および全 Tier が 429 で
失敗した場合に RuntimeError が投げられることも合わせて確認する。

実 LLM は呼ばない — google.genai.Client を全置換する。
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.llm import factory
from src.llm.factory import TieredGeminiClient


_TIERS = ["model-tier1", "model-tier2", "model-tier3", "model-tier4"]


class _FakeQuotaError(Exception):
    """Gemini 429 エラーを模した例外。is_quota_error がメッセージ判定するので
    str(exc) に "429" / "RESOURCE_EXHAUSTED" が含まれていれば良い。"""


class _FakeUnavailableError(Exception):
    """Gemini 503 エラーを模した例外。"""


def _patch_throttle_and_sleep(monkeypatch):
    """_throttle / _wait_for_rpm_slot / time.sleep を no-op 化してテスト時間をゼロにする。"""
    monkeypatch.setattr(TieredGeminiClient, "_throttle", lambda self, model: None)
    monkeypatch.setattr(TieredGeminiClient, "_wait_for_rpm_slot", lambda self, model: None)
    monkeypatch.setattr(factory.time, "sleep", lambda *_a, **_kw: None)


def _install_fake_genai_client(generate_side_effects: list):
    """google.genai.Client を、generate_content が指定 side_effects を順に消費する
    フェイクで差し替える contextmanager を返す。

    factory.generate() は内部で `from google import genai` してから
    `genai.Client(...)` を呼ぶので、google.genai.Client をパッチすれば足りる。"""
    fake_models = MagicMock()
    fake_models.generate_content.side_effect = generate_side_effects

    fake_client = MagicMock()
    fake_client.models = fake_models

    from google import genai as real_genai
    return patch.object(real_genai, "Client", return_value=fake_client), fake_models


def _ok_response(text: str = "OK") -> SimpleNamespace:
    return SimpleNamespace(text=text)


# ── 429: 同一モデルでリトライせず即フォールバック ─────────────────────────────

def test_429_skips_same_model_retries_and_advances_to_next_tier(monkeypatch):
    """tier1 が 429 を返した時、tier1 では1回しか呼ばれず、tier2 で成功すること。"""
    _patch_throttle_and_sleep(monkeypatch)

    side_effects = [
        _FakeQuotaError("429 RESOURCE_EXHAUSTED. Quota exceeded for tier1."),
        _ok_response("tier2 success"),
    ]
    cm, fake_models = _install_fake_genai_client(side_effects)

    with cm:
        client = TieredGeminiClient(api_key="dummy", tiers=_TIERS)
        result = client.generate("test prompt")

    assert result == "tier2 success"
    # 重要: tier1 は1回だけ呼ばれた (attempt=2/3, 3/3 が走っていない) こと
    assert fake_models.generate_content.call_count == 2
    models_called = [call.kwargs["model"] for call in fake_models.generate_content.call_args_list]
    assert models_called == ["model-tier1", "model-tier2"]


def test_429_on_every_tier_calls_each_model_only_once(monkeypatch):
    """全 Tier が 429 を返したら、各モデルは1回だけ呼ばれて RuntimeError になる。"""
    _patch_throttle_and_sleep(monkeypatch)

    side_effects = [
        _FakeQuotaError("429 RESOURCE_EXHAUSTED tier1"),
        _FakeQuotaError("429 RESOURCE_EXHAUSTED tier2"),
        _FakeQuotaError("429 RESOURCE_EXHAUSTED tier3"),
        _FakeQuotaError("429 RESOURCE_EXHAUSTED tier4"),
    ]
    cm, fake_models = _install_fake_genai_client(side_effects)

    with cm:
        client = TieredGeminiClient(api_key="dummy", tiers=_TIERS)
        with pytest.raises(RuntimeError, match="All 4 Gemini tier"):
            client.generate("test prompt")

    # 各モデルは1回ずつ、計4回しか呼ばれない (4 Tier × 3 attempts = 12 回ではない)
    assert fake_models.generate_content.call_count == 4
    models_called = [call.kwargs["model"] for call in fake_models.generate_content.call_args_list]
    assert models_called == _TIERS


def test_429_on_single_tier_list_does_not_retry(monkeypatch):
    """tiers が 1 要素 (lightweight クライアント等) でも 429 でリトライしない。"""
    _patch_throttle_and_sleep(monkeypatch)

    side_effects = [_FakeQuotaError("429 RESOURCE_EXHAUSTED single tier")]
    cm, fake_models = _install_fake_genai_client(side_effects)

    with cm:
        client = TieredGeminiClient(api_key="dummy", tiers=["lone-model"])
        with pytest.raises(RuntimeError):
            client.generate("test prompt")

    # 1回だけ呼ばれて諦めること (3 回リトライしないこと)
    assert fake_models.generate_content.call_count == 1


# ── 503: 従来通りの指数バックオフリトライ ────────────────────────────────────

def test_503_retries_three_times_within_same_tier(monkeypatch):
    """503 はクォータ消費しないので、同一 Tier 内で 3 回までリトライする。"""
    _patch_throttle_and_sleep(monkeypatch)

    # tier1: 503, 503, 成功
    side_effects = [
        _FakeUnavailableError("503 UNAVAILABLE temporary"),
        _FakeUnavailableError("503 UNAVAILABLE still down"),
        _ok_response("tier1 finally ok"),
    ]
    cm, fake_models = _install_fake_genai_client(side_effects)

    with cm:
        client = TieredGeminiClient(api_key="dummy", tiers=_TIERS)
        result = client.generate("test prompt")

    assert result == "tier1 finally ok"
    # tier1 で 3 回呼ばれ、tier2 以降は呼ばれていないこと
    assert fake_models.generate_content.call_count == 3
    models_called = [call.kwargs["model"] for call in fake_models.generate_content.call_args_list]
    assert models_called == ["model-tier1", "model-tier1", "model-tier1"]


def test_503_exhausted_advances_to_next_tier(monkeypatch):
    """tier1 が 503 で 3 回連続失敗したら tier2 へフォールバックする。"""
    _patch_throttle_and_sleep(monkeypatch)

    side_effects = [
        _FakeUnavailableError("503 UNAVAILABLE 1"),
        _FakeUnavailableError("503 UNAVAILABLE 2"),
        _FakeUnavailableError("503 UNAVAILABLE 3"),
        _ok_response("tier2 ok"),
    ]
    cm, fake_models = _install_fake_genai_client(side_effects)

    with cm:
        client = TieredGeminiClient(api_key="dummy", tiers=_TIERS)
        result = client.generate("test prompt")

    assert result == "tier2 ok"
    assert fake_models.generate_content.call_count == 4
    models_called = [call.kwargs["model"] for call in fake_models.generate_content.call_args_list]
    assert models_called == ["model-tier1", "model-tier1", "model-tier1", "model-tier2"]


# ── 混在シナリオ: 429 と 503 が同居する場合 ─────────────────────────────────

def test_429_then_503_then_success(monkeypatch):
    """tier1=429 (即降格) → tier2=503 (リトライ) → tier2 成功。"""
    _patch_throttle_and_sleep(monkeypatch)

    side_effects = [
        _FakeQuotaError("429 RESOURCE_EXHAUSTED tier1"),
        _FakeUnavailableError("503 UNAVAILABLE tier2"),
        _ok_response("tier2 recovered"),
    ]
    cm, fake_models = _install_fake_genai_client(side_effects)

    with cm:
        client = TieredGeminiClient(api_key="dummy", tiers=_TIERS)
        result = client.generate("test prompt")

    assert result == "tier2 recovered"
    assert fake_models.generate_content.call_count == 3
    models_called = [call.kwargs["model"] for call in fake_models.generate_content.call_args_list]
    assert models_called == ["model-tier1", "model-tier2", "model-tier2"]


# ── ログメッセージ確認 ────────────────────────────────────────────────────

def test_429_logs_skip_retries_message(monkeypatch, caplog):
    """429 検出時に '429 RESOURCE_EXHAUSTED → skip retries' を INFO で出すこと。"""
    import logging

    _patch_throttle_and_sleep(monkeypatch)

    side_effects = [
        _FakeQuotaError("429 RESOURCE_EXHAUSTED first"),
        _ok_response("tier2 ok"),
    ]
    cm, _ = _install_fake_genai_client(side_effects)

    with cm:
        client = TieredGeminiClient(api_key="dummy", tiers=_TIERS)
        with caplog.at_level(logging.INFO, logger="src.llm.factory"):
            client.generate("test prompt")

    skip_logs = [r for r in caplog.records if "skip retries" in r.getMessage()]
    assert len(skip_logs) == 1, f"Expected 1 'skip retries' log, got {[r.getMessage() for r in skip_logs]}"
    assert skip_logs[0].levelname == "INFO"


def test_503_logs_warning_with_retry(monkeypatch, caplog):
    """503 リトライ時には従来通り WARNING ログが出る (旧挙動の互換性確認)。"""
    import logging

    _patch_throttle_and_sleep(monkeypatch)

    side_effects = [
        _FakeUnavailableError("503 UNAVAILABLE first"),
        _ok_response("tier1 ok"),
    ]
    cm, _ = _install_fake_genai_client(side_effects)

    with cm:
        client = TieredGeminiClient(api_key="dummy", tiers=_TIERS)
        with caplog.at_level(logging.WARNING, logger="src.llm.factory"):
            client.generate("test prompt")

    retry_logs = [r for r in caplog.records if "transient error" in r.getMessage()]
    assert len(retry_logs) >= 1
    assert all(r.levelname == "WARNING" for r in retry_logs)
