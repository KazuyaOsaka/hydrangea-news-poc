"""Video renderer: produces reviewable MP4 from VideoPayload + AudioSegments.

Pass D-2 MVP — local rendering with Pillow + imageio-ffmpeg. No cloud, no AI B-roll.

Visual design:
  - 720×1280 (9:16 vertical, YouTube Shorts / TikTok format)
  - 30 fps
  - Solid/gradient background per visual_mode
  - Text overlays: scene heading, narration (wrapped), source lower-third
  - Placeholder label when media is not yet available
  - Scene timing synced to voiceover actual_duration_sec

Produces per-run:
  <event_id>_review.mp4          — reviewable MP4 with muxed audio
  <event_id>_render_manifest.json — manifest with status, paths, timing

Usage:
    from src.generation.video_renderer import render_video
    mp4_path, manifest = render_video(payload, audio_segments, output_dir)
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.shared.logger import get_logger

if TYPE_CHECKING:
    from src.generation.audio_renderer import AudioSegment
    from src.shared.models import VideoPayload, VideoScene

logger = get_logger(__name__)

# ── Video constants ────────────────────────────────────────────────────────────
DEFAULT_WIDTH: int = 720
DEFAULT_HEIGHT: int = 1280
DEFAULT_FPS: int = 30

# ── Color palette per visual_mode ─────────────────────────────────────────────
# Each entry: (bg_color_top, bg_color_bottom, accent_color, text_color, label_color)
_THEME: dict[str, dict] = {
    "anchor_style": {
        "bg_top":    (14, 20, 42),
        "bg_bottom": (22, 35, 72),
        "accent":    (255, 220, 60),
        "text":      (240, 240, 240),
        "label_bg":  (255, 220, 60),
        "label_fg":  (14, 20, 42),
    },
    "grounded_broll": {
        "bg_top":    (245, 248, 252),
        "bg_bottom": (210, 225, 245),
        "accent":    (30, 90, 200),
        "text":      (20, 20, 30),
        "label_bg":  (30, 90, 200),
        "label_fg":  (255, 255, 255),
    },
    "split_screen": {
        "bg_top":    (20, 40, 70),
        "bg_bottom": (15, 30, 55),
        "accent":    (80, 200, 180),
        "text":      (230, 240, 250),
        "label_bg":  (80, 200, 180),
        "label_fg":  (14, 20, 42),
    },
    "map_timeline": {
        "bg_top":    (18, 55, 55),
        "bg_bottom": (10, 35, 35),
        "accent":    (100, 220, 160),
        "text":      (220, 245, 235),
        "label_bg":  (100, 220, 160),
        "label_fg":  (10, 35, 35),
    },
    "market_graphic": {
        "bg_top":    (252, 253, 255),
        "bg_bottom": (230, 238, 255),
        "accent":    (40, 120, 240),
        "text":      (15, 15, 30),
        "label_bg":  (40, 120, 240),
        "label_fg":  (255, 255, 255),
    },
    "document_style": {
        "bg_top":    (248, 246, 240),
        "bg_bottom": (235, 230, 218),
        "accent":    (150, 80, 30),
        "text":      (40, 30, 20),
        "label_bg":  (150, 80, 30),
        "label_fg":  (255, 255, 255),
    },
}
_DEFAULT_THEME = {
    "bg_top":    (20, 28, 48),
    "bg_bottom": (12, 18, 36),
    "accent":    (160, 180, 220),
    "text":      (220, 225, 235),
    "label_bg":  (160, 180, 220),
    "label_fg":  (20, 28, 48),
}

# ── Font discovery ─────────────────────────────────────────────────────────────
_JP_FONT_CANDIDATES: list[str] = [
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W2.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
]


def _find_font(size: int) -> ImageFont.FreeTypeFont:
    """Load the first available Japanese-capable font, or fall back to default."""
    for path in _JP_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size=size)
        except (OSError, IOError):
            continue
    logger.warning("[VideoRenderer] No Japanese font found — using default (may not render kanji)")
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _make_gradient_bg(w: int, h: int, top: tuple, bottom: tuple) -> Image.Image:
    """Create a vertical linear gradient background."""
    img = Image.new("RGB", (w, h))
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for c in range(3):
        arr[:, :, c] = np.linspace(top[c], bottom[c], h, dtype=np.uint8)[:, np.newaxis]
    return Image.fromarray(arr)


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Wrap `text` into lines that fit within `max_width` pixels."""
    if not text:
        return []
    lines: list[str] = []
    # Try character-by-character splitting (handles both CJK and Latin)
    current = ""
    for char in text:
        test = current + char
        bbox = font.getbbox(test)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = char
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    line_spacing: int = 8,
    max_lines: int = 8,
) -> int:
    """Draw wrapped text lines. Returns the y position after the last line."""
    for i, line in enumerate(lines[:max_lines]):
        draw.text((x, y), line, font=font, fill=fill)
        bbox = font.getbbox(line)
        y += (bbox[3] - bbox[1]) + line_spacing
    return y


def _render_split_divider(
    draw: ImageDraw.ImageDraw,
    w: int,
    h: int,
    accent: tuple,
) -> None:
    """Draw a vertical divider line for split_screen mode."""
    mid = w // 2
    draw.line([(mid, h // 4), (mid, 3 * h // 4)], fill=accent, width=3)


def _draw_lower_third(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    source_text: str,
    w: int,
    h: int,
    theme: dict,
    font_small: ImageFont.FreeTypeFont,
) -> None:
    """Draw a news-style source lower-third strip at the bottom."""
    strip_h = 72
    strip_y = h - strip_h - 40
    draw.rectangle([(0, strip_y), (w, strip_y + strip_h)], fill=theme["label_bg"])
    label = f"情報源: {source_text[:60]}"
    draw.text((20, strip_y + 18), label, font=font_small, fill=theme["label_fg"])


def _render_scene_frame(
    scene: "VideoScene",
    video_title: str,
    source_line: str,
    fonts: dict,
    w: int,
    h: int,
) -> np.ndarray:
    """Render one Pillow frame for a scene. Returns numpy HxWx3 uint8 array.

    fonts dict keys: "heading", "body", "small"
    """
    theme = _THEME.get(scene.visual_mode, _DEFAULT_THEME)

    img = _make_gradient_bg(w, h, theme["bg_top"], theme["bg_bottom"])
    draw = ImageDraw.Draw(img)

    margin = 40
    usable_w = w - 2 * margin

    # ── Top title strip ───────────────────────────────────────────────────────
    title_lines = _wrap_text(video_title, fonts["small"], usable_w)
    y = margin
    y = _draw_text_block(draw, title_lines[:2], margin, y, fonts["small"],
                         fill=theme["accent"], max_lines=2)
    y += 12

    # ── Accent rule ───────────────────────────────────────────────────────────
    draw.rectangle([(margin, y), (margin + 80, y + 3)], fill=theme["accent"])
    y += 18

    # ── Scene heading badge ───────────────────────────────────────────────────
    badge_text = scene.heading.upper().replace("_", " ")
    bbox = fonts["heading"].getbbox(badge_text)
    bw = bbox[2] - bbox[0] + 24
    bh = bbox[3] - bbox[1] + 12
    draw.rectangle([(margin, y), (margin + bw, y + bh)], fill=theme["label_bg"])
    draw.text((margin + 12, y + 6), badge_text, font=fonts["heading"], fill=theme["label_fg"])
    y += bh + 20

    # ── Split-screen divider (if applicable) ─────────────────────────────────
    if scene.visual_mode == "split_screen":
        _render_split_divider(draw, w, h, theme["accent"])

    # ── Main narration text ───────────────────────────────────────────────────
    narration = scene.narration
    body_font = fonts["body"]
    body_lines = _wrap_text(narration, body_font, usable_w)
    y = _draw_text_block(draw, body_lines, margin, y, body_font,
                         fill=theme["text"], line_spacing=10, max_lines=10)
    y += 20

    # ── on_screen_text (subtitle / pull-quote) ────────────────────────────────
    if scene.on_screen_text and scene.on_screen_text.strip():
        ost = scene.on_screen_text.rstrip("…").strip()
        ost_lines = _wrap_text(ost, fonts["small"], usable_w)
        draw.rectangle(
            [(margin - 6, y - 4), (w - margin + 6, y + len(ost_lines[:3]) * 32 + 8)],
            fill=(*theme["accent"][:3], 30) if len(theme["accent"]) == 3 else theme["accent"],
        )
        y = _draw_text_block(draw, ost_lines[:3], margin, y, fonts["small"],
                             fill=theme["accent"], max_lines=3)

    # ── Placeholder label ─────────────────────────────────────────────────────
    ph_text = f"[Placeholder — {scene.visual_mode}]"
    ph_font = fonts["small"]
    ph_bbox = ph_font.getbbox(ph_text)
    ph_x = w - margin - (ph_bbox[2] - ph_bbox[0])
    ph_y = h - 130
    draw.text((ph_x, ph_y), ph_text, font=ph_font,
              fill=(*[max(0, c - 50) for c in theme["text"][:3]],))

    # ── Source lower-third ────────────────────────────────────────────────────
    _draw_lower_third(img, draw, source_line, w, h, theme, fonts["small"])

    return np.array(img)


def render_video(
    payload: "VideoPayload",
    audio_segments: "list[AudioSegment]",
    output_dir: Path,
    fps: int = DEFAULT_FPS,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> tuple[Path, dict]:
    """Render a reviewable MP4 from VideoPayload + AudioSegments.

    Scene timing is driven by AudioSegment.actual_duration_sec (voiceover truth),
    falling back to VideoScene.duration_sec when no matching audio segment exists.

    Steps:
      1. Load fonts.
      2. For each scene, render static frame + repeat for duration × fps frames.
      3. Encode video-only MP4 with imageio-ffmpeg.
      4. Mux with WAV audio via bundled ffmpeg subprocess.
      5. Save render_manifest.json.

    Returns:
        (mp4_path, manifest_dict)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    event_id = payload.event_id

    # Load fonts
    fonts = {
        "heading": _find_font(28),
        "body":    _find_font(38),
        "small":   _find_font(24),
    }

    # Build a scene-id → AudioSegment lookup for timing
    seg_by_index: dict[int, "AudioSegment"] = {}
    for seg in audio_segments:
        seg_by_index[seg.scene_index] = seg

    source_line = payload.metadata.get("source", "Hydrangea News")

    # Gather per-scene info
    scene_timing: list[dict] = []
    total_video_frames = 0
    placeholder_scenes = []

    for scene in payload.scenes:
        seg = seg_by_index.get(scene.index)
        if seg is not None:
            dur = seg.actual_duration_sec
            audio_driven = True
        else:
            dur = float(scene.duration_sec)
            audio_driven = False
        n_frames = max(1, round(dur * fps))
        total_video_frames += n_frames
        scene_timing.append({
            "scene_index": scene.index,
            "scene_id": scene.scene_id,
            "heading": scene.heading,
            "visual_mode": scene.visual_mode,
            "target_duration_sec": float(scene.duration_sec),
            "actual_duration_sec": round(dur, 3),
            "audio_driven": audio_driven,
            "frame_count": n_frames,
            "placeholder": True,  # all scenes are static placeholder in MVP
        })
        placeholder_scenes.append(scene.heading)

    total_duration_sec = round(total_video_frames / fps, 3)

    # ── Encode video-only MP4 ─────────────────────────────────────────────────
    video_only_path = output_dir / f"{event_id}_video_only.mp4"
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    logger.info(
        f"[VideoRenderer] Encoding {len(payload.scenes)} scenes, "
        f"{total_video_frames} frames @ {fps}fps → {total_duration_sec:.1f}s"
    )

    try:
        writer = imageio.get_writer(
            str(video_only_path),
            fps=fps,
            codec="libx264",
            quality=7,
            ffmpeg_log_level="quiet",
        )
        for scene in payload.scenes:
            frame = _render_scene_frame(
                scene, payload.title, source_line, fonts, width, height
            )
            seg = seg_by_index.get(scene.index)
            dur = seg.actual_duration_sec if seg else float(scene.duration_sec)
            n_frames = max(1, round(dur * fps))
            for _ in range(n_frames):
                writer.append_data(frame)
        writer.close()
        logger.info(f"[VideoRenderer] Video-only MP4 encoded: {video_only_path}")
    except Exception as exc:
        logger.error(f"[VideoRenderer] Encoding error: {exc}")
        # Return a manifest with failure status
        manifest = _build_manifest(
            event_id, output_dir, None, scene_timing,
            total_duration_sec, placeholder_scenes,
            error=str(exc),
        )
        manifest_path = output_dir / f"{event_id}_render_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return output_dir / f"{event_id}_review.mp4", manifest

    # ── Mux audio with video ─────────────────────────────────────────────────
    wav_path = output_dir / f"{event_id}_voiceover.wav"
    mp4_path = output_dir / f"{event_id}_review.mp4"

    mux_ok = False
    mux_error: str | None = None

    if wav_path.exists():
        try:
            result = subprocess.run(
                [
                    ffmpeg_exe,
                    "-y",                    # overwrite
                    "-i", str(video_only_path),
                    "-i", str(wav_path),
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-shortest",             # trim to shorter of video/audio
                    "-loglevel", "error",
                    str(mp4_path),
                ],
                capture_output=True,
                timeout=120,
            )
            if result.returncode == 0:
                mux_ok = True
                logger.info(f"[VideoRenderer] Audio muxed: {mp4_path}")
            else:
                mux_error = result.stderr.decode(errors="replace")[:200]
                logger.warning(f"[VideoRenderer] ffmpeg mux failed: {mux_error}")
        except Exception as exc:
            mux_error = str(exc)
            logger.warning(f"[VideoRenderer] Mux error: {exc}")
    else:
        logger.info("[VideoRenderer] No voiceover WAV found — video-only (no audio mux)")
        # Copy video-only as the review file
        import shutil
        shutil.copy2(str(video_only_path), str(mp4_path))
        mux_ok = True

    if not mux_ok:
        # Fall back to video-only as the review file
        import shutil
        shutil.copy2(str(video_only_path), str(mp4_path))

    # Clean up video-only temp file
    try:
        video_only_path.unlink(missing_ok=True)
    except Exception:
        pass

    # ── Build and save manifest ────────────────────────────────────────────────
    manifest = _build_manifest(
        event_id, output_dir, mp4_path, scene_timing,
        total_duration_sec, placeholder_scenes,
        mux_ok=mux_ok, mux_error=mux_error,
    )
    manifest_path = output_dir / f"{event_id}_render_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(f"[VideoRenderer] Render manifest: {manifest_path}")

    return mp4_path, manifest


def _build_manifest(
    event_id: str,
    output_dir: Path,
    mp4_path: "Path | None",
    scene_timing: list[dict],
    total_duration_sec: float,
    placeholder_scenes: list[str],
    mux_ok: bool = False,
    mux_error: "str | None" = None,
    error: "str | None" = None,
) -> dict:
    """Assemble the render_manifest dict."""
    wav_path = output_dir / f"{event_id}_voiceover.wav"
    segments_path = output_dir / f"{event_id}_voiceover_segments.json"

    audio_info: dict = {
        "generated": wav_path.exists(),
        "output_path": str(wav_path) if wav_path.exists() else None,
        "segments_path": str(segments_path) if segments_path.exists() else None,
    }
    if segments_path.exists():
        try:
            seg_data = json.loads(segments_path.read_text(encoding="utf-8"))
            audio_info["total_duration_sec"] = seg_data.get("total_duration_sec")
            audio_info["placeholder_count"] = seg_data.get("placeholder_count", 0)
            audio_info["timing_mismatches"] = seg_data.get("timing_mismatches", [])
        except Exception:
            pass

    return {
        "event_id": event_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "render_error": error,
        "audio": audio_info,
        "video": {
            "generated": mp4_path is not None and (mp4_path.exists() if mp4_path else False),
            "output_path": str(mp4_path) if mp4_path else None,
            "resolution": f"{DEFAULT_WIDTH}x{DEFAULT_HEIGHT}",
            "fps": DEFAULT_FPS,
            "total_duration_sec": total_duration_sec,
            "scene_count": len(scene_timing),
            "placeholder_count": len(placeholder_scenes),
            "placeholder_scenes": placeholder_scenes,
            "audio_muxed": mux_ok,
            "mux_error": mux_error,
            "scene_timing": scene_timing,
        },
    }


def build_render_manifest_from_paths(
    event_id: str,
    output_dir: Path,
    mp4_path: "Path | None" = None,
    scene_timing: "list[dict] | None" = None,
    total_duration_sec: float = 0.0,
    placeholder_scenes: "list[str] | None" = None,
) -> dict:
    """Public helper to build a render manifest dict without full rendering.

    Useful for populating manifest fields in tests or dry-run scenarios.
    """
    return _build_manifest(
        event_id, output_dir, mp4_path,
        scene_timing or [],
        total_duration_sec,
        placeholder_scenes or [],
    )
