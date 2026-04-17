"""Manual render path — generate voiceover + review MP4 from an existing candidate.

Pass D-3: Decouples audio/video rendering from the daily selection pipeline.

Usage:
    # Explicit event ID
    python -m src.render.run_render --event-id cls-034961e07746

    # Pick the newest completed candidate automatically
    python -m src.render.run_render --latest-completed

    # Override output directory
    python -m src.render.run_render --event-id cls-034961e07746 --output data/output

Input contract (all under --output directory):
    <event_id>_script.json          required
    <event_id>_video_payload.json   required
    <event_id>_evidence.json        optional (used for source labels in report)

Output contract:
    <event_id>_voiceover.wav
    <event_id>_voiceover_segments.json
    <event_id>_review.mp4
    <event_id>_render_manifest.json
    <event_id>_render_report.md
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.generation.audio_renderer import render_voiceover
from src.generation.video_renderer import render_video
from src.shared.config import (
    OUTPUT_DIR,
    TTS_FRAMERATE,
    TTS_TIMEOUT_SEC,
    TTS_VOICE,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
)
from src.shared.logger import get_logger

logger = get_logger(__name__)


# ── Candidate discovery ────────────────────────────────────────────────────────

def find_completed_candidates(output_dir: Path) -> list[str]:
    """Return event IDs that have both script.json and video_payload.json.

    Sorted by script.json mtime (newest first).
    """
    script_files = list(output_dir.glob("*_script.json"))
    completed: list[tuple[float, str]] = []
    for sf in script_files:
        event_id = sf.name.removesuffix("_script.json")
        payload_path = output_dir / f"{event_id}_video_payload.json"
        if payload_path.exists():
            completed.append((sf.stat().st_mtime, event_id))
    completed.sort(reverse=True)
    return [eid for _, eid in completed]


def resolve_event_id(
    event_id: str | None,
    latest_completed: bool,
    output_dir: Path,
) -> str:
    """Resolve which event_id to render.

    Raises SystemExit with a clear message when no candidate is found.
    """
    if event_id:
        return event_id

    if latest_completed:
        candidates = find_completed_candidates(output_dir)
        if not candidates:
            print(
                f"[RenderExisting] ERROR: No completed candidates found in {output_dir}\n"
                "  A completed candidate needs both _script.json and _video_payload.json.",
                file=sys.stderr,
            )
            sys.exit(1)
        chosen = candidates[0]
        logger.info(f"[RenderExisting] --latest-completed → {chosen} ({len(candidates)} total)")
        return chosen

    print(
        "[RenderExisting] ERROR: Specify --event-id <EVENT_ID> or --latest-completed.",
        file=sys.stderr,
    )
    sys.exit(1)


# ── Input loading ──────────────────────────────────────────────────────────────

def load_render_inputs(event_id: str, output_dir: Path) -> tuple:
    """Load script, payload, and (optional) evidence for event_id.

    Returns:
        (VideoScript, VideoPayload, evidence_dict | None)

    Raises SystemExit with a clear message if required files are missing or invalid.
    """
    from src.shared.models import VideoPayload, VideoScript

    script_path = output_dir / f"{event_id}_script.json"
    payload_path = output_dir / f"{event_id}_video_payload.json"
    evidence_path = output_dir / f"{event_id}_evidence.json"

    missing = []
    if not script_path.exists():
        missing.append(str(script_path))
    if not payload_path.exists():
        missing.append(str(payload_path))
    if missing:
        print(
            f"[RenderExisting] ERROR: Required file(s) not found:\n"
            + "\n".join(f"  {p}" for p in missing),
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        script = VideoScript.model_validate_json(script_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[RenderExisting] ERROR: Cannot parse {script_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        payload = VideoPayload.model_validate_json(payload_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[RenderExisting] ERROR: Cannot parse {payload_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    evidence: dict | None = None
    if evidence_path.exists():
        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning(f"[RenderExisting] evidence.json found but could not be parsed: {evidence_path}")

    return script, payload, evidence


# ── Report writing ─────────────────────────────────────────────────────────────

def write_render_report(
    event_id: str,
    output_dir: Path,
    script,
    payload,
    av_summary: dict,
    started_at: datetime,
    finished_at: datetime,
) -> Path:
    """Write a human-readable render report markdown file.

    Returns the path of the written report.
    """
    duration_sec = (finished_at - started_at).total_seconds()

    audio_generated = av_summary.get("audio_generated", False)
    video_generated = av_summary.get("video_generated", False)
    voiceover_path = av_summary.get("voiceover_path") or "—"
    review_mp4_path = av_summary.get("review_mp4_path") or "—"
    render_manifest_path = av_summary.get("render_manifest_path") or "—"
    segments_path = str(output_dir / f"{event_id}_voiceover_segments.json")
    total_duration = av_summary.get("total_duration_sec")
    placeholder_count = av_summary.get("placeholder_count", 0)
    timing_mismatches = av_summary.get("timing_mismatches", [])
    render_error = av_summary.get("error") or "none"

    # Source labels from payload metadata
    source_label = payload.metadata.get("source", "—")
    platform_profile = payload.metadata.get("platform_profile", "—")
    scene_count = len(payload.scenes)

    # Build mismatch table
    mismatch_lines: list[str] = []
    for mm in timing_mismatches:
        mismatch_lines.append(
            f"| {mm.get('scene_id', '—')} | {mm.get('mismatch_sec', 0):+.2f}s |"
        )

    mismatch_table = (
        "| scene_id | mismatch_sec |\n| --- | --- |\n" + "\n".join(mismatch_lines)
        if mismatch_lines
        else "_none_"
    )

    total_dur_str = f"{total_duration:.1f}s" if total_duration is not None else "—"

    lines = [
        f"# Render Report — `{event_id}`",
        "",
        f"Generated: {finished_at.strftime('%Y-%m-%d %H:%M:%S UTC')}  ",
        f"Render wall time: {duration_sec:.1f}s",
        "",
        "## Candidate",
        "",
        f"| Field | Value |",
        f"| --- | --- |",
        f"| event_id | `{event_id}` |",
        f"| canonical title | {script.title} |",
        f"| platform title | {payload.title} |",
        f"| platform profile | {platform_profile} |",
        f"| primary source | {source_label} |",
        f"| scene count | {scene_count} |",
        f"| script total_duration_sec | {script.total_duration_sec}s |",
        "",
        "## Render Status",
        "",
        f"| Step | Status |",
        f"| --- | --- |",
        f"| audio generated | {'✓' if audio_generated else '✗'} |",
        f"| video generated | {'✓' if video_generated else '✗'} |",
        f"| render error | `{render_error}` |",
        "",
        "## Output Files",
        "",
        f"| File | Path |",
        f"| --- | --- |",
        f"| voiceover WAV | `{voiceover_path}` |",
        f"| voiceover segments | `{segments_path}` |",
        f"| review MP4 | `{review_mp4_path}` |",
        f"| render manifest | `{render_manifest_path}` |",
        "",
        "## Audio Stats",
        "",
        f"| Metric | Value |",
        f"| --- | --- |",
        f"| total duration | {total_dur_str} |",
        f"| placeholder count | {placeholder_count} |",
        "",
        "## Timing Mismatches (>0.5s)",
        "",
        mismatch_table,
        "",
    ]

    report_path = output_dir / f"{event_id}_render_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"[RenderExisting] Render report written: {report_path}")
    return report_path


# ── Core render logic ──────────────────────────────────────────────────────────

def render_existing(
    event_id: str,
    output_dir: Path,
) -> dict:
    """Render audio + video for an existing completed candidate.

    This function is completely independent from ingestion, scheduling, judging,
    viral filter, and daily candidate-selection logic.

    Returns an av_summary dict (same schema as _render_av_outputs in main.py).
    """
    started_at = datetime.now(timezone.utc)
    logger.info(f"[RenderExisting] Starting render for event_id={event_id}")

    script, payload, _evidence = load_render_inputs(event_id, output_dir)

    summary: dict = {
        "event_id": event_id,
        "audio_generated": False,
        "video_generated": False,
        "voiceover_path": None,
        "review_mp4_path": None,
        "render_manifest_path": None,
        "placeholder_count": 0,
        "total_duration_sec": None,
        "timing_mismatches": [],
        "error": None,
    }

    # ── Audio ──────────────────────────────────────────────────────────────────
    try:
        wav_path, audio_segments, audio_manifest = render_voiceover(
            script, output_dir,
            voice=TTS_VOICE,
            framerate=TTS_FRAMERATE,
            tts_timeout=TTS_TIMEOUT_SEC,
        )
        summary["audio_generated"] = True
        summary["voiceover_path"] = str(wav_path)
        summary["placeholder_count"] = audio_manifest.get("placeholder_count", 0)
        summary["total_duration_sec"] = audio_manifest.get("total_duration_sec")
        summary["timing_mismatches"] = audio_manifest.get("timing_mismatches", [])
        logger.info(
            f"[RenderExisting] Audio done: {wav_path} "
            f"({summary['total_duration_sec']}s, "
            f"placeholders={summary['placeholder_count']})"
        )
    except Exception as exc:
        summary["error"] = f"audio_render_error:{exc}"
        logger.error(f"[RenderExisting] Audio render failed: {exc}")
        finished_at = datetime.now(timezone.utc)
        write_render_report(event_id, output_dir, script, payload, summary, started_at, finished_at)
        return summary

    # ── Video ──────────────────────────────────────────────────────────────────
    try:
        mp4_path, render_manifest = render_video(
            payload, audio_segments, output_dir,
            fps=VIDEO_FPS,
            width=VIDEO_WIDTH,
            height=VIDEO_HEIGHT,
        )
        summary["video_generated"] = True
        summary["review_mp4_path"] = str(mp4_path)
        manifest_path = output_dir / f"{event_id}_render_manifest.json"
        summary["render_manifest_path"] = str(manifest_path)
        logger.info(f"[RenderExisting] Video done: {mp4_path}")
    except Exception as exc:
        summary["error"] = f"video_render_error:{exc}"
        logger.error(f"[RenderExisting] Video render failed: {exc}")

    finished_at = datetime.now(timezone.utc)
    report_path = write_render_report(
        event_id, output_dir, script, payload, summary, started_at, finished_at
    )
    summary["render_report_path"] = str(report_path)
    return summary


# ── CLI entry point ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Hydrangea News — manual render from existing candidate.\n"
            "Renders voiceover + review MP4 without running ingestion, "
            "scheduling, or editorial selection."
        )
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--event-id",
        dest="event_id",
        metavar="EVENT_ID",
        help="Event ID to render (e.g. cls-034961e07746)",
    )
    group.add_argument(
        "--latest-completed",
        action="store_true",
        dest="latest_completed",
        help="Find and render the newest completed candidate in --output dir",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory containing candidate artifacts (default: {OUTPUT_DIR})",
    )
    args = parser.parse_args()

    output_dir: Path = args.output
    event_id = resolve_event_id(
        args.event_id,
        args.latest_completed,
        output_dir,
    )

    summary = render_existing(event_id, output_dir)

    print()
    print(f"=== Render complete: {event_id} ===")
    print(f"  audio generated : {summary['audio_generated']}")
    print(f"  video generated : {summary['video_generated']}")
    if summary.get("voiceover_path"):
        print(f"  voiceover       : {summary['voiceover_path']}")
    if summary.get("review_mp4_path"):
        print(f"  review MP4      : {summary['review_mp4_path']}")
    if summary.get("render_report_path"):
        print(f"  render report   : {summary['render_report_path']}")
    if summary.get("error"):
        print(f"  error           : {summary['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
