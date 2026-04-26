"""TieredGeminiClient._wait_for_rpm_slot の動的レートリミッタ挙動を検証する。

GEMINI_RPM_LIMIT_BY_MODEL に登録されたモデルについて、直近60秒の呼び出し履歴が
上限の安全率（_RPM_SAFETY_RATIO=0.7）を超えそうな場合に sleep するか、
60秒経過後に履歴がクリアされて再び呼べるか、モデル別の履歴が独立して
管理されているかを time.sleep / time.time をモック化して検証する。

実 LLM は呼ばない — _wait_for_rpm_slot は HTTP 呼び出しを伴わないので、
factory.time モジュールの sleep / time をパッチするだけで十分。
"""
from __future__ import annotations

import pytest

from src.llm import factory
from src.llm.factory import TieredGeminiClient, _RPM_DEFAULT_LIMIT, _RPM_SAFETY_RATIO


class _FakeClock:
    """単調増加する time.time() / 経過記録する time.sleep の差し替え用フェイク。

    - now() を monkeypatch で factory.time.time に紐付ける。
    - sleep(sec) が呼ばれたら経過時間を進めつつ self.sleeps に記録する。
    """

    def __init__(self, start: float = 1_000_000.0) -> None:
        self._t = start
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self._t

    def sleep(self, sec: float) -> None:
        # 負値が来た場合はゼロに丸める（実 sleep と同じ振る舞い）
        sec = max(0.0, sec)
        self.sleeps.append(sec)
        self._t += sec

    def advance(self, sec: float) -> None:
        self._t += sec


@pytest.fixture
def fake_clock(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(factory.time, "time", clock.time)
    monkeypatch.setattr(factory.time, "sleep", clock.sleep)
    return clock


def _make_client_with_rpm(monkeypatch, model: str, rpm_limit: int) -> TieredGeminiClient:
    """テスト対象のモデルに rpm_limit を設定したクライアントを返す。

    GEMINI_RPM_LIMIT_BY_MODEL にエントリを追加することで、
    _wait_for_rpm_slot がそのモデルについて指定 RPM を見るようにする。
    """
    monkeypatch.setitem(factory.GEMINI_RPM_LIMIT_BY_MODEL, model, rpm_limit)
    return TieredGeminiClient(api_key="dummy", tiers=[model])


# ── 70%閾値到達時の自動待機 ─────────────────────────────────────────────────

def test_wait_for_rpm_slot_below_threshold_does_not_sleep(fake_clock, monkeypatch):
    """履歴が threshold 未満なら sleep せずに即時通過する。"""
    model = "test-model-rpm10"
    rpm_limit = 10
    threshold = max(1, int(rpm_limit * _RPM_SAFETY_RATIO))  # 7
    client = _make_client_with_rpm(monkeypatch, model, rpm_limit)

    # threshold - 1 回呼ぶ間は一切 sleep が発生しないこと
    for _ in range(threshold - 1):
        client._wait_for_rpm_slot(model)

    assert fake_clock.sleeps == []
    assert len(client._call_history_by_model[model]) == threshold - 1


def test_wait_for_rpm_slot_at_threshold_sleeps_until_oldest_expires(fake_clock, monkeypatch):
    """直近60秒で threshold 件の履歴があれば、次の呼び出しは最古エントリ + 60秒まで待つ。"""
    model = "test-model-rpm10"
    rpm_limit = 10
    threshold = max(1, int(rpm_limit * _RPM_SAFETY_RATIO))  # 7
    client = _make_client_with_rpm(monkeypatch, model, rpm_limit)

    # 0 秒目から 1 秒間隔で threshold 件呼ぶ
    start = fake_clock.time()
    for _ in range(threshold):
        client._wait_for_rpm_slot(model)
        fake_clock.advance(1.0)
    # 履歴は threshold 件積まれており、ここまで sleep は発生していない
    assert fake_clock.sleeps == []

    # threshold + 1 回目: 最古エントリ (start 時刻) + 60 秒まで待つ必要がある
    # 現在時刻は start + threshold (履歴 7 件 → 経過 7 秒)
    expected_wait = (start + 60.0) - fake_clock.time()
    client._wait_for_rpm_slot(model)

    assert len(fake_clock.sleeps) == 1
    assert fake_clock.sleeps[0] == pytest.approx(expected_wait, abs=0.01)


def test_wait_for_rpm_slot_high_rpm_threshold(fake_clock, monkeypatch):
    """RPM=15 のモデルでは threshold=10 (= 15*0.7) まで sleep せず、
    11件目で約60秒待つ（履歴が同時刻にバーストしているため）。"""
    model = "test-model-rpm15"
    rpm_limit = 15
    threshold = max(1, int(rpm_limit * _RPM_SAFETY_RATIO))  # 10
    client = _make_client_with_rpm(monkeypatch, model, rpm_limit)

    # 同時刻で threshold 件呼ぶ（履歴 0→10 まで append、いずれも閾値到達前なので sleep 無し）
    for _ in range(threshold):
        client._wait_for_rpm_slot(model)
    assert fake_clock.sleeps == []
    assert len(client._call_history_by_model[model]) == threshold

    # threshold + 1 件目: 履歴が threshold 件溜まっており、最古から60秒待つ必要がある
    client._wait_for_rpm_slot(model)
    assert len(fake_clock.sleeps) == 1
    assert fake_clock.sleeps[0] == pytest.approx(60.0, abs=0.01)


# ── 60秒経過後の履歴クリア ─────────────────────────────────────────────────

def test_wait_for_rpm_slot_history_clears_after_60s(fake_clock, monkeypatch):
    """60秒経過すると古い履歴は破棄され、再び閾値まで自由に呼べる。"""
    model = "test-model-rpm10"
    rpm_limit = 10
    threshold = max(1, int(rpm_limit * _RPM_SAFETY_RATIO))  # 7
    client = _make_client_with_rpm(monkeypatch, model, rpm_limit)

    # threshold 件、瞬時に呼ぶ（時刻は同じ）
    for _ in range(threshold):
        client._wait_for_rpm_slot(model)
    assert fake_clock.sleeps == []
    assert len(client._call_history_by_model[model]) == threshold

    # 61秒経過させる
    fake_clock.advance(61.0)

    # 履歴は次回呼び出し時にウィンドウ掃除されてクリアされる
    client._wait_for_rpm_slot(model)
    # sleep は発生していないこと
    assert fake_clock.sleeps == []
    # 履歴は新しい1件のみ
    assert len(client._call_history_by_model[model]) == 1


def test_wait_for_rpm_slot_partial_window_decay(fake_clock, monkeypatch):
    """60秒以内に古いエントリだけ抜けても、新しいエントリは保持される。"""
    model = "test-model-rpm10"
    rpm_limit = 10
    threshold = max(1, int(rpm_limit * _RPM_SAFETY_RATIO))  # 7
    client = _make_client_with_rpm(monkeypatch, model, rpm_limit)

    # 0秒, 1秒, ..., 6秒目に 7件呼ぶ
    for _ in range(threshold):
        client._wait_for_rpm_slot(model)
        fake_clock.advance(1.0)
    assert fake_clock.sleeps == []

    # 現在時刻 = 7秒。65秒経過させると最古は 0秒、現在 72秒 → 0秒のエントリだけ抜ける
    # しかし他のエントリ (1..6秒) はまだ 60 秒以内 (72 - 1 = 71 > 60) なので全部抜ける
    fake_clock.advance(65.0)  # 現在 = 72秒
    client._wait_for_rpm_slot(model)
    # 全件 60 秒以上経過 (72 - 6 = 66 > 60) なので履歴は新しい1件のみ
    assert len(client._call_history_by_model[model]) == 1
    assert fake_clock.sleeps == []


# ── モデル別履歴の独立性 ───────────────────────────────────────────────────

def test_wait_for_rpm_slot_history_is_per_model(fake_clock, monkeypatch):
    """異なるモデルの履歴は独立しており、片方の呼び出しが他方をブロックしない。"""
    model_a = "model-a-rpm10"
    model_b = "model-b-rpm15"
    monkeypatch.setitem(factory.GEMINI_RPM_LIMIT_BY_MODEL, model_a, 10)
    monkeypatch.setitem(factory.GEMINI_RPM_LIMIT_BY_MODEL, model_b, 15)
    client = TieredGeminiClient(api_key="dummy", tiers=[model_a, model_b])

    threshold_a = max(1, int(10 * _RPM_SAFETY_RATIO))  # 7
    threshold_b = max(1, int(15 * _RPM_SAFETY_RATIO))  # 10

    # model_a を threshold_a 件呼ぶ → sleep なし
    for _ in range(threshold_a):
        client._wait_for_rpm_slot(model_a)
    assert fake_clock.sleeps == []

    # model_b は履歴ゼロなので、threshold_b - 1 件まで自由に呼べる
    for _ in range(threshold_b - 1):
        client._wait_for_rpm_slot(model_b)
    # model_a の履歴で sleep が起きていないこと
    assert fake_clock.sleeps == []

    # 両モデルの履歴件数が独立して保持されていること
    assert len(client._call_history_by_model[model_a]) == threshold_a
    assert len(client._call_history_by_model[model_b]) == threshold_b - 1


# ── 未登録モデルの保守的なデフォルト ──────────────────────────────────────

def test_wait_for_rpm_slot_unknown_model_uses_default_limit(fake_clock, monkeypatch):
    """GEMINI_RPM_LIMIT_BY_MODEL に未登録のモデルは _RPM_DEFAULT_LIMIT で扱う。"""
    model = "unknown-model-not-in-map"
    # 念のためマップから除外しておく
    monkeypatch.setattr(
        factory,
        "GEMINI_RPM_LIMIT_BY_MODEL",
        {k: v for k, v in factory.GEMINI_RPM_LIMIT_BY_MODEL.items() if k != model},
    )
    client = TieredGeminiClient(api_key="dummy", tiers=[model])

    threshold = max(1, int(_RPM_DEFAULT_LIMIT * _RPM_SAFETY_RATIO))  # 5*0.7 = 3

    # threshold 件を瞬時に呼ぶ（同じ時刻）
    for _ in range(threshold):
        client._wait_for_rpm_slot(model)
    assert fake_clock.sleeps == []

    # 次の呼び出しで sleep が発生する（履歴がすべて同時刻なので約 60 秒待つ）
    client._wait_for_rpm_slot(model)
    assert len(fake_clock.sleeps) == 1
    assert fake_clock.sleeps[0] == pytest.approx(60.0, abs=0.01)
