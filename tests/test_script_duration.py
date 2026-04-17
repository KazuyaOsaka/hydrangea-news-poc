"""Tests for video duration estimation and platform profile (src/generation/script_writer.py)"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.shared.models import NewsEvent, ScriptSection, VideoScript
from src.generation.script_writer import (
    PLATFORM_PROFILES,
    _estimate_duration_sec,
    _build_script_fallback,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_event(event_id: str = "test-evt", title: str = "Test title", **kwargs) -> NewsEvent:
    defaults = dict(
        summary="テスト用のサマリーです。日本と海外の報道差を示す。",
        category="economy",
        source="TestSource",
        published_at=datetime(2026, 4, 8, 10, 0, 0),
    )
    defaults.update(kwargs)
    return NewsEvent(id=event_id, title=title, **defaults)


# ── PLATFORM_PROFILES tests ───────────────────────────────────────────────────

def test_platform_profiles_shared_exists():
    assert "shared" in PLATFORM_PROFILES


def test_platform_profiles_shared_values():
    p = PLATFORM_PROFILES["shared"]
    assert p["target_sec"] == 75
    assert p["hard_min_sec"] == 60
    assert p["hard_max_sec"] == 100
    assert p["min_sec"] < p["max_sec"]


def test_platform_profiles_tiktok_exists():
    assert "tiktok" in PLATFORM_PROFILES
    p = PLATFORM_PROFILES["tiktok"]
    assert p["hard_min_sec"] == 60


def test_platform_profiles_youtube_shorts_exists():
    assert "youtube_shorts" in PLATFORM_PROFILES


# ── _estimate_duration_sec tests ──────────────────────────────────────────────

def test_estimate_duration_empty():
    assert _estimate_duration_sec("") == 0


def test_estimate_duration_short():
    # 14文字 ≈ 3秒
    text = "日本では報じられていない。"  # 13 chars (non-whitespace)
    est = _estimate_duration_sec(text)
    assert 1 <= est <= 5


def test_estimate_duration_75sec_target():
    # ~340字で75秒になるはず
    text = "あ" * 340
    est = _estimate_duration_sec(text)
    assert 70 <= est <= 80


def test_estimate_duration_ignores_whitespace():
    text_compact = "日本語のテスト文章です。"
    text_spaced  = "日本語の テスト 文章です。"
    # 空白を除いた文字数ベースで推定するので近似値になる
    assert abs(_estimate_duration_sec(text_compact) - _estimate_duration_sec(text_spaced)) <= 1


def test_estimate_duration_hard_min():
    # 60秒 = 270字
    text = "あ" * 270
    est = _estimate_duration_sec(text)
    assert est >= 58  # 丸め誤差を許容


def test_estimate_duration_hard_max():
    # 100秒 = 450字
    text = "あ" * 450
    est = _estimate_duration_sec(text)
    assert est >= 95


# ── VideoScript model tests ───────────────────────────────────────────────────

def test_videoscript_default_platform_fields():
    script = VideoScript(
        event_id="e1",
        title="Test",
        intro="",
        sections=[],
        outro="",
        total_duration_sec=75,
    )
    assert script.platform_profile == "shared"
    assert script.target_duration_sec == 75
    assert script.estimated_duration_sec is None


def test_videoscript_accepts_estimated_duration():
    script = VideoScript(
        event_id="e1",
        title="Test",
        intro="",
        sections=[],
        outro="",
        total_duration_sec=75,
        estimated_duration_sec=73,
        platform_profile="tiktok",
    )
    assert script.estimated_duration_sec == 73
    assert script.platform_profile == "tiktok"


# ── _build_script_fallback duration tests ────────────────────────────────────

def test_fallback_sets_target_duration_sec():
    event = _make_event()
    script = _build_script_fallback(event)
    assert script.target_duration_sec == 75


def test_fallback_sets_estimated_duration_sec():
    event = _make_event(
        summary="大谷翔平が海外のメジャーリーグでMVPを受賞した。日本国内のメディアも大きく報じた。",
    )
    script = _build_script_fallback(event)
    assert script.estimated_duration_sec is not None
    assert isinstance(script.estimated_duration_sec, int)
    assert script.estimated_duration_sec > 0


def test_fallback_sets_platform_profile_shared():
    event = _make_event()
    script = _build_script_fallback(event)
    assert script.platform_profile == "shared"


def test_fallback_estimated_within_reasonable_range():
    """フォールバック台本の推定尺が 30〜120秒の範囲内に収まる。"""
    event = _make_event(
        summary="日本と海外の報道差が顕著なニュースです。詳細は続報を待ちたい。",
        impact_on_japan="国内企業の株価に影響が及ぶ可能性がある。",
    )
    script = _build_script_fallback(event)
    assert 30 <= script.estimated_duration_sec <= 120


# ── video_payload_writer duration metadata tests ──────────────────────────────

def test_video_payload_includes_duration_metadata():
    from src.generation.video_payload_writer import write_video_payload

    event = _make_event()
    script = VideoScript(
        event_id=event.id,
        title=event.title,
        intro="",
        sections=[
            ScriptSection(heading="hook", body="掴みのテキスト。", duration_sec=3),
            ScriptSection(heading="fact", body="事実のテキスト。" * 5, duration_sec=12),
        ],
        outro="",
        total_duration_sec=75,
        target_duration_sec=75,
        estimated_duration_sec=68,
        platform_profile="shared",
    )
    payload = write_video_payload(event, script)
    assert payload.metadata["target_duration_sec"] == 75
    assert payload.metadata["estimated_duration_sec"] == 68
    assert payload.metadata["platform_profile"] == "shared"


def test_video_payload_duration_metadata_tiktok_profile():
    from src.generation.video_payload_writer import write_video_payload

    event = _make_event()
    script = VideoScript(
        event_id=event.id,
        title=event.title,
        intro="",
        sections=[],
        outro="",
        total_duration_sec=72,
        target_duration_sec=72,
        estimated_duration_sec=70,
        platform_profile="tiktok",
    )
    payload = write_video_payload(event, script)
    assert payload.metadata["platform_profile"] == "tiktok"
    assert payload.metadata["target_duration_sec"] == 72
