"""Regression tests for src/render/run_render.py — Pass D-3.

Coverage:
  - render_existing with explicit event_id
  - render_existing with missing files fails clearly
  - --latest-completed picks the newest completed candidate
  - render_report.md is written
  - run_summary is NOT required for manual render mode
"""
from __future__ import annotations

import json
import sys
import wave
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.render.run_render import (
    find_completed_candidates,
    load_render_inputs,
    render_existing,
    resolve_event_id,
    write_render_report,
)
from src.shared.models import ScriptSection, VideoPayload, VideoScene, VideoScript


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_script(event_id: str = "cls-test0001") -> VideoScript:
    return VideoScript(
        event_id=event_id,
        title="テスト: 日本の財政政策",
        intro="本日のニュースです。",
        sections=[
            ScriptSection(heading="背景", body="日本政府は新たな財政措置を発表。", duration_sec=10),
            ScriptSection(heading="影響", body="市場への影響が注目されています。", duration_sec=15),
        ],
        outro="以上、速報でした。",
        total_duration_sec=30,
    )


def _make_payload(event_id: str = "cls-test0001") -> VideoPayload:
    return VideoPayload(
        event_id=event_id,
        title="日本財政政策の最新動向",
        scenes=[
            VideoScene(
                index=0,
                narration="日本政府は新たな財政措置を発表。",
                visual_hint="news desk",
                duration_sec=10,
                scene_id=f"{event_id}_s00_背景",
                heading="背景",
                visual_mode="anchor_style",
            ),
            VideoScene(
                index=1,
                narration="市場への影響が注目されています。",
                visual_hint="market graphic",
                duration_sec=15,
                scene_id=f"{event_id}_s01_影響",
                heading="影響",
                visual_mode="market_graphic",
            ),
        ],
        total_duration_sec=25,
        metadata={"source": "NHK_Economy", "platform_profile": "shared"},
    )


def _write_script(tmp_path: Path, event_id: str) -> Path:
    script = _make_script(event_id)
    p = tmp_path / f"{event_id}_script.json"
    p.write_text(script.model_dump_json(), encoding="utf-8")
    return p


def _write_payload(tmp_path: Path, event_id: str) -> Path:
    payload = _make_payload(event_id)
    p = tmp_path / f"{event_id}_video_payload.json"
    p.write_text(payload.model_dump_json(), encoding="utf-8")
    return p


def _make_wav_bytes(duration_sec: float = 0.5, framerate: int = 22050) -> bytes:
    nframes = max(1, int(duration_sec * framerate))
    buf = io.BytesIO()
    with wave.open(buf, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(b"\x00\x00" * nframes)
    return buf.getvalue()


# ── find_completed_candidates ──────────────────────────────────────────────────

class TestFindCompletedCandidates:
    def test_returns_event_ids_with_both_files(self, tmp_path):
        _write_script(tmp_path, "cls-aaa")
        _write_payload(tmp_path, "cls-aaa")
        result = find_completed_candidates(tmp_path)
        assert "cls-aaa" in result

    def test_excludes_events_missing_payload(self, tmp_path):
        _write_script(tmp_path, "cls-bbb")
        # no payload
        result = find_completed_candidates(tmp_path)
        assert "cls-bbb" not in result

    def test_excludes_events_missing_script(self, tmp_path):
        _write_payload(tmp_path, "cls-ccc")
        # no script
        result = find_completed_candidates(tmp_path)
        assert "cls-ccc" not in result

    def test_empty_directory(self, tmp_path):
        result = find_completed_candidates(tmp_path)
        assert result == []

    def test_newest_first_ordering(self, tmp_path):
        import time
        _write_script(tmp_path, "cls-old")
        _write_payload(tmp_path, "cls-old")
        time.sleep(0.05)
        _write_script(tmp_path, "cls-new")
        _write_payload(tmp_path, "cls-new")
        result = find_completed_candidates(tmp_path)
        assert result[0] == "cls-new"
        assert result[1] == "cls-old"


# ── resolve_event_id ──────────────────────────────────────────────────────────

class TestResolveEventId:
    def test_explicit_event_id_returned_as_is(self, tmp_path):
        result = resolve_event_id("cls-explicit", False, tmp_path)
        assert result == "cls-explicit"

    def test_latest_completed_picks_newest(self, tmp_path):
        import time
        _write_script(tmp_path, "cls-older")
        _write_payload(tmp_path, "cls-older")
        time.sleep(0.05)
        _write_script(tmp_path, "cls-newer")
        _write_payload(tmp_path, "cls-newer")
        result = resolve_event_id(None, True, tmp_path)
        assert result == "cls-newer"

    def test_latest_completed_exits_when_no_candidates(self, tmp_path):
        with pytest.raises(SystemExit):
            resolve_event_id(None, True, tmp_path)

    def test_no_event_id_no_flag_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            resolve_event_id(None, False, tmp_path)


# ── load_render_inputs ────────────────────────────────────────────────────────

class TestLoadRenderInputs:
    def test_loads_script_and_payload(self, tmp_path):
        event_id = "cls-load01"
        _write_script(tmp_path, event_id)
        _write_payload(tmp_path, event_id)
        script, payload, evidence = load_render_inputs(event_id, tmp_path)
        assert script.event_id == event_id
        assert payload.event_id == event_id
        assert evidence is None

    def test_loads_evidence_when_present(self, tmp_path):
        event_id = "cls-load02"
        _write_script(tmp_path, event_id)
        _write_payload(tmp_path, event_id)
        ev_path = tmp_path / f"{event_id}_evidence.json"
        ev_path.write_text(json.dumps({"sources": ["NHK"]}), encoding="utf-8")
        _, _, evidence = load_render_inputs(event_id, tmp_path)
        assert evidence == {"sources": ["NHK"]}

    def test_missing_script_exits(self, tmp_path):
        event_id = "cls-missing-script"
        _write_payload(tmp_path, event_id)
        with pytest.raises(SystemExit):
            load_render_inputs(event_id, tmp_path)

    def test_missing_payload_exits(self, tmp_path):
        event_id = "cls-missing-payload"
        _write_script(tmp_path, event_id)
        with pytest.raises(SystemExit):
            load_render_inputs(event_id, tmp_path)

    def test_both_files_missing_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            load_render_inputs("cls-nonexistent", tmp_path)

    def test_invalid_script_json_exits(self, tmp_path):
        event_id = "cls-bad-script"
        (tmp_path / f"{event_id}_script.json").write_text("not json", encoding="utf-8")
        _write_payload(tmp_path, event_id)
        with pytest.raises(SystemExit):
            load_render_inputs(event_id, tmp_path)

    def test_invalid_payload_json_exits(self, tmp_path):
        event_id = "cls-bad-payload"
        _write_script(tmp_path, event_id)
        (tmp_path / f"{event_id}_video_payload.json").write_text("{}", encoding="utf-8")
        with pytest.raises(SystemExit):
            load_render_inputs(event_id, tmp_path)


# ── write_render_report ───────────────────────────────────────────────────────

class TestWriteRenderReport:
    def _summary(self, **overrides) -> dict:
        base = {
            "event_id": "cls-rpt01",
            "audio_generated": True,
            "video_generated": True,
            "voiceover_path": "/tmp/cls-rpt01_voiceover.wav",
            "review_mp4_path": "/tmp/cls-rpt01_review.mp4",
            "render_manifest_path": "/tmp/cls-rpt01_render_manifest.json",
            "placeholder_count": 0,
            "total_duration_sec": 28.5,
            "timing_mismatches": [],
            "error": None,
        }
        base.update(overrides)
        return base

    def test_report_file_is_written(self, tmp_path):
        from datetime import datetime, timezone
        event_id = "cls-rpt01"
        script = _make_script(event_id)
        payload = _make_payload(event_id)
        now = datetime.now(timezone.utc)
        report_path = write_render_report(event_id, tmp_path, script, payload, self._summary(), now, now)
        assert report_path.exists()
        assert report_path.name == f"{event_id}_render_report.md"

    def test_report_contains_event_id(self, tmp_path):
        from datetime import datetime, timezone
        event_id = "cls-rpt02"
        script = _make_script(event_id)
        payload = _make_payload(event_id)
        now = datetime.now(timezone.utc)
        report_path = write_render_report(event_id, tmp_path, script, payload, self._summary(event_id=event_id), now, now)
        content = report_path.read_text(encoding="utf-8")
        assert event_id in content

    def test_report_contains_canonical_title(self, tmp_path):
        from datetime import datetime, timezone
        event_id = "cls-rpt03"
        script = _make_script(event_id)
        payload = _make_payload(event_id)
        now = datetime.now(timezone.utc)
        report_path = write_render_report(event_id, tmp_path, script, payload, self._summary(), now, now)
        content = report_path.read_text(encoding="utf-8")
        assert script.title in content

    def test_report_contains_platform_title(self, tmp_path):
        from datetime import datetime, timezone
        event_id = "cls-rpt04"
        script = _make_script(event_id)
        payload = _make_payload(event_id)
        now = datetime.now(timezone.utc)
        report_path = write_render_report(event_id, tmp_path, script, payload, self._summary(), now, now)
        content = report_path.read_text(encoding="utf-8")
        assert payload.title in content

    def test_report_shows_timing_mismatches(self, tmp_path):
        from datetime import datetime, timezone
        event_id = "cls-rpt05"
        script = _make_script(event_id)
        payload = _make_payload(event_id)
        now = datetime.now(timezone.utc)
        summary = self._summary(timing_mismatches=[{"scene_id": "s00_背景", "mismatch_sec": 3.1}])
        report_path = write_render_report(event_id, tmp_path, script, payload, summary, now, now)
        content = report_path.read_text(encoding="utf-8")
        assert "s00_背景" in content

    def test_report_shows_render_error(self, tmp_path):
        from datetime import datetime, timezone
        event_id = "cls-rpt06"
        script = _make_script(event_id)
        payload = _make_payload(event_id)
        now = datetime.now(timezone.utc)
        summary = self._summary(audio_generated=False, error="audio_render_error:TTS timeout")
        report_path = write_render_report(event_id, tmp_path, script, payload, summary, now, now)
        content = report_path.read_text(encoding="utf-8")
        assert "audio_render_error" in content


# ── render_existing (integration, mocked renderers) ───────────────────────────

def _mock_render_voiceover(script, output_dir, **kwargs):
    """Minimal mock: write a real WAV, return (path, [segment], manifest)."""
    from src.generation.audio_renderer import AudioSegment
    wav_path = output_dir / f"{script.event_id}_voiceover.wav"
    wav_path.write_bytes(_make_wav_bytes(5.0))
    seg = AudioSegment(
        scene_index=0,
        scene_id="intro",
        heading="intro",
        narration_text="テスト",
        target_duration_sec=3.0,
        actual_duration_sec=5.0,
        timing_mismatch_sec=2.0,
        placeholder=False,
    )
    manifest = {
        "event_id": script.event_id,
        "total_duration_sec": 5.0,
        "placeholder_count": 0,
        "timing_mismatches": [],
        "output_path": str(wav_path),
        "segments": [seg.to_dict()],
    }
    segs_path = output_dir / f"{script.event_id}_voiceover_segments.json"
    import json
    segs_path.write_text(json.dumps(manifest), encoding="utf-8")
    return wav_path, [seg], manifest


def _mock_render_video(payload, audio_segments, output_dir, **kwargs):
    mp4_path = output_dir / f"{payload.event_id}_review.mp4"
    mp4_path.write_bytes(b"FAKEVIDEO")
    manifest = {
        "event_id": payload.event_id,
        "audio": {"generated": True},
        "video": {"generated": True, "output_path": str(mp4_path)},
        "render_error": None,
    }
    manifest_path = output_dir / f"{payload.event_id}_render_manifest.json"
    import json
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return mp4_path, manifest


class TestRenderExisting:
    def test_render_existing_explicit_event_id(self, tmp_path):
        event_id = "cls-render01"
        _write_script(tmp_path, event_id)
        _write_payload(tmp_path, event_id)
        with (
            patch("src.render.run_render.render_voiceover", side_effect=_mock_render_voiceover),
            patch("src.render.run_render.render_video", side_effect=_mock_render_video),
        ):
            summary = render_existing(event_id, tmp_path)
        assert summary["audio_generated"] is True
        assert summary["video_generated"] is True
        assert summary["error"] is None

    def test_render_existing_writes_render_report(self, tmp_path):
        event_id = "cls-render02"
        _write_script(tmp_path, event_id)
        _write_payload(tmp_path, event_id)
        with (
            patch("src.render.run_render.render_voiceover", side_effect=_mock_render_voiceover),
            patch("src.render.run_render.render_video", side_effect=_mock_render_video),
        ):
            summary = render_existing(event_id, tmp_path)
        report_path = tmp_path / f"{event_id}_render_report.md"
        assert report_path.exists()
        assert summary.get("render_report_path") == str(report_path)

    def test_render_existing_missing_files_exits_clearly(self, tmp_path):
        with pytest.raises(SystemExit):
            render_existing("cls-nonexistent", tmp_path)

    def test_render_existing_missing_script_exits(self, tmp_path):
        event_id = "cls-no-script"
        _write_payload(tmp_path, event_id)
        with pytest.raises(SystemExit):
            render_existing(event_id, tmp_path)

    def test_render_existing_missing_payload_exits(self, tmp_path):
        event_id = "cls-no-payload"
        _write_script(tmp_path, event_id)
        with pytest.raises(SystemExit):
            render_existing(event_id, tmp_path)

    def test_render_existing_audio_error_still_writes_report(self, tmp_path):
        event_id = "cls-audio-err"
        _write_script(tmp_path, event_id)
        _write_payload(tmp_path, event_id)
        with patch("src.render.run_render.render_voiceover", side_effect=RuntimeError("TTS failed")):
            summary = render_existing(event_id, tmp_path)
        assert summary["audio_generated"] is False
        assert "audio_render_error" in (summary.get("error") or "")
        report_path = tmp_path / f"{event_id}_render_report.md"
        assert report_path.exists()

    def test_render_existing_video_error_still_writes_report(self, tmp_path):
        event_id = "cls-video-err"
        _write_script(tmp_path, event_id)
        _write_payload(tmp_path, event_id)
        with (
            patch("src.render.run_render.render_voiceover", side_effect=_mock_render_voiceover),
            patch("src.render.run_render.render_video", side_effect=RuntimeError("ffmpeg crashed")),
        ):
            summary = render_existing(event_id, tmp_path)
        assert summary["audio_generated"] is True
        assert summary["video_generated"] is False
        assert "video_render_error" in (summary.get("error") or "")
        report_path = tmp_path / f"{event_id}_render_report.md"
        assert report_path.exists()

    def test_render_existing_does_not_require_run_summary(self, tmp_path):
        """Manual render must succeed even when no run_summary.json exists."""
        event_id = "cls-no-summary"
        _write_script(tmp_path, event_id)
        _write_payload(tmp_path, event_id)
        assert not (tmp_path / "run_summary.json").exists()
        with (
            patch("src.render.run_render.render_voiceover", side_effect=_mock_render_voiceover),
            patch("src.render.run_render.render_video", side_effect=_mock_render_video),
        ):
            summary = render_existing(event_id, tmp_path)
        assert summary["audio_generated"] is True

    def test_render_existing_with_latest_completed(self, tmp_path):
        """resolve_event_id + render_existing end-to-end via --latest-completed."""
        import time
        _write_script(tmp_path, "cls-older")
        _write_payload(tmp_path, "cls-older")
        time.sleep(0.05)
        _write_script(tmp_path, "cls-newest")
        _write_payload(tmp_path, "cls-newest")

        event_id = resolve_event_id(None, True, tmp_path)
        assert event_id == "cls-newest"

        with (
            patch("src.render.run_render.render_voiceover", side_effect=_mock_render_voiceover),
            patch("src.render.run_render.render_video", side_effect=_mock_render_video),
        ):
            summary = render_existing(event_id, tmp_path)
        assert summary["audio_generated"] is True
        assert summary["video_generated"] is True

    def test_render_existing_with_evidence_json(self, tmp_path):
        """evidence.json is optional — its presence should not break anything."""
        event_id = "cls-with-evidence"
        _write_script(tmp_path, event_id)
        _write_payload(tmp_path, event_id)
        ev_path = tmp_path / f"{event_id}_evidence.json"
        ev_path.write_text(json.dumps({"sources": ["Reuters", "NHK"]}), encoding="utf-8")
        with (
            patch("src.render.run_render.render_voiceover", side_effect=_mock_render_voiceover),
            patch("src.render.run_render.render_video", side_effect=_mock_render_video),
        ):
            summary = render_existing(event_id, tmp_path)
        assert summary["audio_generated"] is True

    def test_render_existing_output_paths_in_summary(self, tmp_path):
        event_id = "cls-paths"
        _write_script(tmp_path, event_id)
        _write_payload(tmp_path, event_id)
        with (
            patch("src.render.run_render.render_voiceover", side_effect=_mock_render_voiceover),
            patch("src.render.run_render.render_video", side_effect=_mock_render_video),
        ):
            summary = render_existing(event_id, tmp_path)
        assert summary["voiceover_path"] is not None
        assert event_id in summary["voiceover_path"]
        assert summary["review_mp4_path"] is not None
        assert event_id in summary["review_mp4_path"]
        assert summary["render_manifest_path"] is not None

    def test_render_existing_independent_from_ingestion(self, tmp_path):
        """render_existing must not import or call any ingestion/selection code."""
        import src.render.run_render as m
        source = Path(m.__file__).read_text(encoding="utf-8")
        for forbidden in [
            "from src.ingestion",
            "from src.triage",
            "from src.storage",
            "run_from_normalized",
            "build_daily_schedule",
            "apply_viral_filter",
            "gemini_judge",
        ]:
            assert forbidden not in source, (
                f"run_render.py must not reference '{forbidden}' (ingestion/selection independence)"
            )
