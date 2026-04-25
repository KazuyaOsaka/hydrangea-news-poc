"""configs/channels.yaml ロードと ChannelConfig の Pydantic 検証。"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.shared.models import ChannelConfig


def test_load_geo_lens_returns_enabled_channel():
    cfg = ChannelConfig.load("geo_lens")
    assert cfg.channel_id == "geo_lens"
    assert cfg.enabled is True
    assert cfg.posts_per_day == 3
    assert "silence_gap" in cfg.perspective_axes
    assert "geopolitics_120s" in cfg.duration_profiles


def test_load_japan_athletes_disabled_phase1():
    cfg = ChannelConfig.load("japan_athletes")
    assert cfg.enabled is False
    assert cfg.posts_per_day == 0
    assert cfg.perspective_axes == []


def test_load_k_pulse_disabled_phase1():
    cfg = ChannelConfig.load("k_pulse")
    assert cfg.enabled is False


def test_load_unknown_channel_raises():
    with pytest.raises(ValueError):
        ChannelConfig.load("nonexistent_channel_id")


def test_load_all_returns_three_channels():
    channels = ChannelConfig.load_all()
    ids = {c.channel_id for c in channels}
    assert ids == {"geo_lens", "japan_athletes", "k_pulse"}


def test_load_with_explicit_path(tmp_path: Path):
    custom_yaml = tmp_path / "channels.yaml"
    custom_yaml.write_text(
        yaml.safe_dump({
            "channels": [{
                "channel_id": "test_ch",
                "display_name": "Test",
                "enabled": True,
                "source_regions": ["global"],
                "perspective_axes": ["silence_gap"],
                "duration_profiles": ["breaking_shock_60s"],
                "prompt_variant": "test_v1",
                "posts_per_day": 1,
            }]
        }),
        encoding="utf-8",
    )
    cfg = ChannelConfig.load("test_ch", config_path=custom_yaml)
    assert cfg.display_name == "Test"
    assert cfg.posts_per_day == 1


def test_geo_lens_has_4_perspective_axes():
    cfg = ChannelConfig.load("geo_lens")
    assert set(cfg.perspective_axes) == {
        "silence_gap",
        "framing_inversion",
        "hidden_stakes",
        "cultural_blindspot",
    }


def test_geo_lens_has_6_duration_profiles():
    cfg = ChannelConfig.load("geo_lens")
    assert len(cfg.duration_profiles) == 6
