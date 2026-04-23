"""Audio renderer: TTS voiceover from VideoScript using macOS `say`.

Pass D-2 MVP — local, deterministic, no cloud dependencies.

Produces per-run:
  <event_id>_voiceover.wav          — concatenated full voiceover (PCM WAV, mono 22050 Hz)
  <event_id>_voiceover_segments.json — per-segment timing manifest

TTS backend: macOS `say` command (available on macOS 10.7+).
Fallback: silent padding when `say` is unavailable or times out.

Usage:
    from src.generation.audio_renderer import render_voiceover
    wav_path, segments, manifest = render_voiceover(script, output_dir)
"""
from __future__ import annotations

import io
import json
import subprocess
import tempfile
import wave
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from src.shared.logger import get_logger

if TYPE_CHECKING:
    from src.shared.models import VideoScript

logger = get_logger(__name__)

# WAV parameters (LEI16 = little-endian signed 16-bit PCM)
_WAV_CHANNELS: int = 1
_WAV_SAMPWIDTH: int = 2  # bytes per sample (16-bit)
_DEFAULT_FRAMERATE: int = 22050
_DEFAULT_VOICE: str = "Kyoko"
_DEFAULT_TTS_TIMEOUT: int = 60

# Silence between segments (short pause for natural delivery)
_INTER_SEGMENT_SILENCE_SEC: float = 0.15


@dataclass
class AudioSegment:
    """Per-scene audio metadata."""
    scene_index: int
    scene_id: str
    heading: str
    narration_text: str
    target_duration_sec: float
    actual_duration_sec: float
    timing_mismatch_sec: float   # actual - target; positive = audio longer than video slot
    placeholder: bool            # True if TTS failed; segment is silent padding

    def to_dict(self) -> dict:
        return asdict(self)


def _make_silence(duration_sec: float, framerate: int) -> bytes:
    """Return a PCM WAV bytes object containing `duration_sec` of silence."""
    nframes = max(1, int(duration_sec * framerate))
    buf = io.BytesIO()
    with wave.open(buf, "w") as wf:
        wf.setnchannels(_WAV_CHANNELS)
        wf.setsampwidth(_WAV_SAMPWIDTH)
        wf.setframerate(framerate)
        wf.writeframes(b"\x00\x00" * nframes)
    return buf.getvalue()


def _wav_duration(wav_bytes: bytes) -> float:
    """Return duration in seconds of a WAV bytes object."""
    with wave.open(io.BytesIO(wav_bytes)) as wf:
        return wf.getnframes() / wf.getframerate()


def _concat_wavs(wav_bytes_list: list[bytes]) -> bytes:
    """Concatenate a list of mono PCM WAV byte strings into a single WAV."""
    if not wav_bytes_list:
        return _make_silence(0.01, _DEFAULT_FRAMERATE)

    # Read params from first segment
    with wave.open(io.BytesIO(wav_bytes_list[0])) as first:
        ch = first.getnchannels()
        sw = first.getsampwidth()
        fr = first.getframerate()

    out = io.BytesIO()
    with wave.open(out, "w") as wout:
        wout.setnchannels(ch)
        wout.setsampwidth(sw)
        wout.setframerate(fr)
        for data in wav_bytes_list:
            with wave.open(io.BytesIO(data)) as win:
                wout.writeframes(win.readframes(win.getnframes()))
    return out.getvalue()


def render_segment_tts(
    text: str,
    voice: str = _DEFAULT_VOICE,
    framerate: int = _DEFAULT_FRAMERATE,
    timeout: int = _DEFAULT_TTS_TIMEOUT,
) -> tuple[bytes, bool]:
    """Render `text` to WAV bytes using macOS `say`. Returns (wav_bytes, is_placeholder).

    Falls back to silence on any error (TTS unavailable, timeout, etc.).
    The placeholder flag is True when silence is used instead of real TTS.
    """
    if not text.strip():
        return _make_silence(0.01, framerate), True

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [
                "say",
                "-v", voice,
                "-o", tmp_path,
                f"--data-format=LEI16@{framerate}",
                text,
            ],
            capture_output=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            logger.warning(
                f"[AudioRenderer] say returned {result.returncode} for "
                f"text={text[:40]!r}: {result.stderr[:100]}"
            )
            return _make_silence(len(text) * 0.06, framerate), True

        wav_data = Path(tmp_path).read_bytes()
        if len(wav_data) < 44:  # WAV header minimum
            logger.warning(f"[AudioRenderer] say output too small ({len(wav_data)} bytes)")
            return _make_silence(len(text) * 0.06, framerate), True
        return wav_data, False

    except FileNotFoundError:
        logger.info("[AudioRenderer] `say` command not found — using silent placeholder.")
        return _make_silence(len(text) * 0.06, framerate), True
    except subprocess.TimeoutExpired:
        logger.warning(f"[AudioRenderer] TTS timeout after {timeout}s for text={text[:40]!r}")
        return _make_silence(len(text) * 0.06, framerate), True
    except Exception as exc:
        logger.warning(f"[AudioRenderer] TTS error: {exc}")
        return _make_silence(len(text) * 0.06, framerate), True
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


def build_narration_segments(
    script: "VideoScript",
) -> list[tuple[str, str, float]]:
    """Extract (scene_id, narration_text, target_duration_sec) from script sections.

    Returns one entry per non-empty section (intro/outro included if non-empty).
    """
    items: list[tuple[str, str, float]] = []
    if script.intro and script.intro.strip():
        items.append(("intro", script.intro.strip(), 3.0))
    for i, section in enumerate(script.sections):
        if section.body.strip():
            scene_id = f"{script.event_id}_s{i:02d}_{section.heading}"
            items.append((scene_id, section.body.strip(), float(section.duration_sec)))
    if script.outro and script.outro.strip():
        items.append(("outro", script.outro.strip(), 3.0))
    return items


def render_voiceover(
    script: "VideoScript",
    output_dir: Path,
    voice: str = _DEFAULT_VOICE,
    framerate: int = _DEFAULT_FRAMERATE,
    tts_timeout: int = _DEFAULT_TTS_TIMEOUT,
) -> tuple[Path, list[AudioSegment], dict]:
    """Render full voiceover from VideoScript.

    1. Build narration segments from script sections.
    2. Render each segment via macOS `say` (fallback: silence).
    3. Insert short silence between segments for natural pacing.
    4. Concatenate all segment WAVs into one file.
    5. Save <event_id>_voiceover.wav and <event_id>_voiceover_segments.json.

    Returns:
        (wav_path, audio_segments, manifest_dict)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    narration_items = build_narration_segments(script)
    silence_between = _make_silence(_INTER_SEGMENT_SILENCE_SEC, framerate)

    audio_segments: list[AudioSegment] = []
    all_wav_bytes: list[bytes] = []
    placeholder_count = 0

    for i, (scene_id, text, target_dur) in enumerate(narration_items):
        heading = scene_id.split("_")[-1] if "_" in scene_id else scene_id
        logger.info(f"[AudioRenderer] Rendering segment {i}: {scene_id} ({target_dur:.0f}s)")

        wav_bytes, is_placeholder = render_segment_tts(text, voice=voice,
                                                        framerate=framerate,
                                                        timeout=tts_timeout)
        actual_dur = _wav_duration(wav_bytes)
        mismatch = round(actual_dur - target_dur, 3)

        if is_placeholder:
            placeholder_count += 1

        seg = AudioSegment(
            scene_index=i,
            scene_id=scene_id,
            heading=heading,
            narration_text=text,
            target_duration_sec=target_dur,
            actual_duration_sec=round(actual_dur, 3),
            timing_mismatch_sec=mismatch,
            placeholder=is_placeholder,
        )
        audio_segments.append(seg)

        all_wav_bytes.append(wav_bytes)
        if i < len(narration_items) - 1:
            all_wav_bytes.append(silence_between)

        if abs(mismatch) > 2.0:
            logger.info(
                f"[AudioRenderer] Timing mismatch: {scene_id} "
                f"target={target_dur:.1f}s actual={actual_dur:.1f}s "
                f"delta={mismatch:+.1f}s"
            )

    # Concatenate
    full_wav = _concat_wavs(all_wav_bytes) if all_wav_bytes else _make_silence(1.0, framerate)
    total_duration = _wav_duration(full_wav)

    # Save WAV
    wav_path = output_dir / f"{script.event_id}_voiceover.wav"
    wav_path.write_bytes(full_wav)
    logger.info(
        f"[AudioRenderer] Voiceover saved: {wav_path} "
        f"({total_duration:.1f}s, {len(audio_segments)} segments, "
        f"{placeholder_count} placeholder(s))"
    )

    # Save segments manifest
    timing_mismatches = [
        {"scene_id": s.scene_id, "mismatch_sec": s.timing_mismatch_sec}
        for s in audio_segments
        if abs(s.timing_mismatch_sec) > 0.5
    ]
    # target_duration_sec は sections の duration_sec 合計を直接計算する。
    # 基本的には script.total_duration_sec と一致するが、万一 drift があっても
    # マニフェストは実 section 値を正とする（model_validator で同期済みのはず）。
    _sections_total = float(sum(s.duration_sec for s in script.sections))
    manifest = {
        "event_id": script.event_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "voice": voice,
        "framerate": framerate,
        "total_duration_sec": round(total_duration, 3),
        "target_duration_sec": _sections_total or float(script.total_duration_sec),
        "segment_count": len(audio_segments),
        "placeholder_count": placeholder_count,
        "timing_mismatches": timing_mismatches,
        "output_path": str(wav_path),
        "segments": [s.to_dict() for s in audio_segments],
    }
    segments_path = output_dir / f"{script.event_id}_voiceover_segments.json"
    segments_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"[AudioRenderer] Segments manifest saved: {segments_path}")

    return wav_path, audio_segments, manifest
