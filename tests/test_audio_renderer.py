"""Tests for src/generation/audio_renderer.py — Pass D-2."""
from __future__ import annotations

import io
import json
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.generation.audio_renderer import (
    AudioSegment,
    _concat_wavs,
    _make_silence,
    _wav_duration,
    build_narration_segments,
    render_segment_tts,
    render_voiceover,
)
from src.shared.models import ScriptSection, VideoScript


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_wav_bytes(duration_sec: float = 0.5, framerate: int = 22050) -> bytes:
    """Return a minimal PCM WAV bytes object."""
    return _make_silence(duration_sec, framerate)


def _make_script(sections=None, intro="", outro="") -> VideoScript:
    if sections is None:
        sections = [
            ScriptSection(heading="Section1", body="日本のニュース", duration_sec=5),
            ScriptSection(heading="Section2", body="More details here.", duration_sec=8),
        ]
    return VideoScript(
        event_id="test_event_001",
        title="Test Title",
        intro=intro,
        sections=sections,
        outro=outro,
        total_duration_sec=30,
    )


# ── _make_silence / _wav_duration ─────────────────────────────────────────────

class TestSilenceAndDuration:
    def test_make_silence_returns_bytes(self):
        data = _make_silence(0.5, 22050)
        assert isinstance(data, bytes)
        assert len(data) > 44  # at least WAV header

    def test_make_silence_duration_approx(self):
        dur = _wav_duration(_make_silence(1.0, 22050))
        assert abs(dur - 1.0) < 0.01

    def test_make_silence_zero_duration_noop(self):
        data = _make_silence(0.0, 22050)
        dur = _wav_duration(data)
        assert dur >= 0.0  # at least 1 frame

    def test_wav_duration_consistent(self):
        for sec in (0.1, 0.5, 1.0, 2.0):
            dur = _wav_duration(_make_silence(sec, 22050))
            assert abs(dur - sec) < 0.02


# ── _concat_wavs ───────────────────────────────────────────────────────────────

class TestConcatWavs:
    def test_concat_empty_list_returns_silence(self):
        result = _concat_wavs([])
        dur = _wav_duration(result)
        assert dur >= 0.0

    def test_concat_two_segments(self):
        a = _make_silence(1.0, 22050)
        b = _make_silence(0.5, 22050)
        result = _concat_wavs([a, b])
        dur = _wav_duration(result)
        assert abs(dur - 1.5) < 0.05

    def test_concat_preserves_params(self):
        a = _make_silence(0.2, 22050)
        b = _make_silence(0.3, 22050)
        result = _concat_wavs([a, b])
        with wave.open(io.BytesIO(result)) as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 22050

    def test_concat_single_segment_passthrough(self):
        a = _make_silence(0.7, 22050)
        result = _concat_wavs([a])
        assert abs(_wav_duration(result) - 0.7) < 0.02


# ── build_narration_segments ──────────────────────────────────────────────────

class TestBuildNarrationSegments:
    def test_basic_sections_extracted(self):
        script = _make_script()
        items = build_narration_segments(script)
        assert len(items) == 2
        scene_ids = [i[0] for i in items]
        texts = [i[1] for i in items]
        assert "日本のニュース" in texts
        assert "More details here." in texts

    def test_intro_and_outro_included(self):
        script = _make_script(intro="Welcome!", outro="Goodbye.")
        items = build_narration_segments(script)
        texts = [i[1] for i in items]
        assert "Welcome!" in texts
        assert "Goodbye." in texts
        # intro first, outro last
        assert items[0][1] == "Welcome!"
        assert items[-1][1] == "Goodbye."

    def test_empty_sections_skipped(self):
        script = _make_script(
            sections=[
                ScriptSection(heading="H1", body="Real content", duration_sec=5),
                ScriptSection(heading="H2", body="   ", duration_sec=5),  # whitespace only
            ]
        )
        items = build_narration_segments(script)
        assert len(items) == 1
        assert items[0][1] == "Real content"

    def test_target_duration_matches_section(self):
        script = _make_script(
            sections=[
                ScriptSection(heading="H1", body="text", duration_sec=12),
            ]
        )
        items = build_narration_segments(script)
        assert items[0][2] == 12.0

    def test_intro_outro_default_duration(self):
        script = _make_script(intro="Hello", outro="Bye")
        items = build_narration_segments(script)
        # intro at index 0, outro at last
        assert items[0][2] == 3.0
        assert items[-1][2] == 3.0

    def test_scene_id_contains_event_id(self):
        script = _make_script()
        items = build_narration_segments(script)
        for scene_id, _, _ in items:
            if scene_id not in ("intro", "outro"):
                assert "test_event_001" in scene_id


# ── render_segment_tts ────────────────────────────────────────────────────────

class TestRenderSegmentTts:
    def test_empty_text_returns_placeholder(self):
        wav, is_placeholder = render_segment_tts("")
        assert is_placeholder is True
        assert _wav_duration(wav) > 0.0

    def test_whitespace_text_returns_placeholder(self):
        wav, is_placeholder = render_segment_tts("   ")
        assert is_placeholder is True

    def test_say_unavailable_returns_placeholder(self):
        """When `say` is not found, fall back to silence."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            wav, is_placeholder = render_segment_tts("hello world")
        assert is_placeholder is True
        assert _wav_duration(wav) > 0.0

    def test_say_timeout_returns_placeholder(self):
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("say", 5)):
            wav, is_placeholder = render_segment_tts("test text", timeout=1)
        assert is_placeholder is True

    def test_say_nonzero_returncode_returns_placeholder(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = b"error"
        with patch("subprocess.run", return_value=mock_result):
            wav, is_placeholder = render_segment_tts("hello")
        assert is_placeholder is True

    def test_placeholder_duration_scales_with_text_length(self):
        short = "Hi."
        long_text = "This is a much longer text that should produce a longer silence placeholder."
        wav_short, _ = render_segment_tts.__wrapped__(short) if hasattr(render_segment_tts, "__wrapped__") else (None, None)
        # Just verify render_segment_tts succeeds for both, using the fallback path
        with patch("subprocess.run", side_effect=FileNotFoundError):
            wav_s, _ = render_segment_tts(short)
            wav_l, _ = render_segment_tts(long_text)
        dur_s = _wav_duration(wav_s)
        dur_l = _wav_duration(wav_l)
        assert dur_l > dur_s  # longer text → longer placeholder


# ── render_voiceover ──────────────────────────────────────────────────────────

class TestRenderVoiceover:
    def test_manifest_structure(self, tmp_path):
        """render_voiceover returns a manifest with all expected keys."""
        script = _make_script()
        with patch("src.generation.audio_renderer.render_segment_tts") as mock_tts:
            mock_tts.return_value = (_make_silence(2.0, 22050), True)
            wav_path, segments, manifest = render_voiceover(script, tmp_path)

        required_keys = {
            "event_id", "generated_at", "voice", "framerate",
            "total_duration_sec", "target_duration_sec",
            "segment_count", "placeholder_count", "timing_mismatches",
            "output_path", "segments",
        }
        assert required_keys.issubset(manifest.keys())

    def test_wav_file_created(self, tmp_path):
        script = _make_script()
        with patch("src.generation.audio_renderer.render_segment_tts") as mock_tts:
            mock_tts.return_value = (_make_silence(1.0, 22050), False)
            wav_path, _, _ = render_voiceover(script, tmp_path)
        assert wav_path.exists()
        assert wav_path.suffix == ".wav"

    def test_segments_json_created(self, tmp_path):
        script = _make_script()
        with patch("src.generation.audio_renderer.render_segment_tts") as mock_tts:
            mock_tts.return_value = (_make_silence(1.0, 22050), False)
            _, _, manifest = render_voiceover(script, tmp_path)
        seg_path = tmp_path / "test_event_001_voiceover_segments.json"
        assert seg_path.exists()
        data = json.loads(seg_path.read_text())
        assert data["event_id"] == "test_event_001"

    def test_segment_count_matches_script(self, tmp_path):
        script = _make_script()  # 2 sections
        with patch("src.generation.audio_renderer.render_segment_tts") as mock_tts:
            mock_tts.return_value = (_make_silence(1.0, 22050), False)
            _, segments, manifest = render_voiceover(script, tmp_path)
        assert len(segments) == 2
        assert manifest["segment_count"] == 2

    def test_placeholder_count_tracked(self, tmp_path):
        script = _make_script()
        with patch("src.generation.audio_renderer.render_segment_tts") as mock_tts:
            mock_tts.return_value = (_make_silence(1.0, 22050), True)  # always placeholder
            _, _, manifest = render_voiceover(script, tmp_path)
        assert manifest["placeholder_count"] == 2

    def test_timing_mismatch_recorded(self, tmp_path):
        """Segments where |actual - target| > 0.5s appear in timing_mismatches."""
        script = _make_script(
            sections=[
                ScriptSection(heading="H1", body="text", duration_sec=10),
            ]
        )
        # actual = 1.0s, target = 10s → mismatch = -9s
        with patch("src.generation.audio_renderer.render_segment_tts") as mock_tts:
            mock_tts.return_value = (_make_silence(1.0, 22050), False)
            _, _, manifest = render_voiceover(script, tmp_path)
        assert len(manifest["timing_mismatches"]) == 1
        mismatch = manifest["timing_mismatches"][0]
        assert abs(mismatch["mismatch_sec"]) > 0.5

    def test_audio_segment_fields(self, tmp_path):
        script = _make_script()
        with patch("src.generation.audio_renderer.render_segment_tts") as mock_tts:
            mock_tts.return_value = (_make_silence(5.0, 22050), False)
            _, segments, _ = render_voiceover(script, tmp_path)
        seg = segments[0]
        assert isinstance(seg, AudioSegment)
        assert seg.scene_index == 0
        assert seg.actual_duration_sec > 0.0
        assert isinstance(seg.placeholder, bool)

    def test_total_duration_positive(self, tmp_path):
        script = _make_script()
        with patch("src.generation.audio_renderer.render_segment_tts") as mock_tts:
            mock_tts.return_value = (_make_silence(2.0, 22050), False)
            _, _, manifest = render_voiceover(script, tmp_path)
        assert manifest["total_duration_sec"] > 0.0
