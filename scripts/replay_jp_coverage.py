"""F-trial-run-post-fix: 過去試運転データの修正後 F-13.B 再判定スクリプト。

試運転 7-K (2026-05-01) で動画化された 3 件 (FIFA + Gaza×2) を、
F-jp-coverage-improve (2026-05-07) で構造的不具合を修正した F-13.B で
再判定し、過去判定との差分を出力する。

入力: docs/runs/F-trial-run-post-fix/trial_7k_events.json
      (event_id, title, summary, old_judgment を持つエントリ配列)
出力: docs/runs/F-trial-run-post-fix/past_runs_replay.json

一時 DB (/tmp/jp_coverage_replay.db) を使い本番 DB を汚染しない。

Usage:
    python scripts/replay_jp_coverage.py \\
        --input docs/runs/F-trial-run-post-fix/trial_7k_events.json \\
        --output docs/runs/F-trial-run-post-fix/past_runs_replay.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.shared.config import (  # noqa: E402
    GEMINI_API_KEY,
    JP_COVERAGE_GROUNDING_MODEL,
)
from src.shared.logger import get_logger  # noqa: E402
from src.triage.jp_coverage_verifier import JpCoverageVerifier  # noqa: E402

logger = get_logger("replay_jp_coverage")

TEMP_DB_PATH = Path("/tmp/jp_coverage_replay.db")

_TEMP_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS jp_coverage_cache (
    event_id         TEXT PRIMARY KEY,
    has_jp_coverage  INTEGER NOT NULL,
    matched_tier     TEXT,
    matched_urls     TEXT,
    matched_domains  TEXT,
    excluded_urls    TEXT,
    search_query     TEXT,
    cached_at        TEXT NOT NULL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def setup_temp_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(_TEMP_DB_SCHEMA)
        conn.commit()
    logger.info(f"Temp DB ready at {db_path}")


def get_gemini_client():
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY)


def _get_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def _classify_diff(old_has: bool, new_has: Optional[bool], error: Optional[str]) -> str:
    if error:
        return f"{old_has} → Error ({error[:60]})"
    if new_has is None:
        return f"{old_has} → None"
    if old_has == new_has:
        return f"{old_has} → {new_has} (判定不変)"
    return f"{old_has} → {new_has} (判定変化)"


def replay(input_path: Path, output_path: Path) -> int:
    if not input_path.exists():
        logger.error(f"Input not found: {input_path}")
        return 1

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    entries: list[dict] = payload.get("events") or payload.get("entries") or []
    if not entries:
        logger.error("No events/entries found in input file")
        return 1

    if TEMP_DB_PATH.exists():
        TEMP_DB_PATH.unlink()
    setup_temp_db(TEMP_DB_PATH)

    client = get_gemini_client()
    verifier = JpCoverageVerifier(
        gemini_client=client,
        db_path=TEMP_DB_PATH,
        model=JP_COVERAGE_GROUNDING_MODEL,
    )

    new_commit = _get_git_commit()
    old_commit = payload.get("f13b_old_commit", "b950813 (F-13.B 初実装、構造的不具合あり)")

    out_events: list[dict] = []
    summary = {"judgment_changed": 0, "judgment_unchanged": 0, "errors": 0}

    for i, ent in enumerate(entries, 1):
        event_id = ent["event_id"]
        title = ent["title"]
        summary_text = ent.get("summary", "")
        old = ent.get("old_judgment", {"has_jp_coverage": False, "matched_tier": None, "matched_domains": []})
        old_has = bool(old.get("has_jp_coverage", False))

        logger.info(f"[{i}/{len(entries)}] Replaying {event_id}: {title[:60]}...")
        start = time.time()
        error_field: Optional[str] = None
        new_has: Optional[bool] = None
        new_tier: Optional[str] = None
        new_domains: list[str] = []
        new_urls: list[str] = []
        excluded_urls: list[str] = []
        search_query = ""

        try:
            result = verifier.verify(event_id=event_id, title=title, summary=summary_text)
            if result.error:
                error_field = result.error
                new_has = None
            else:
                new_has = bool(result.has_jp_coverage)
            new_tier = result.matched_tier
            new_domains = list(result.matched_domains)
            new_urls = list(result.matched_urls)
            excluded_urls = list(result.excluded_urls)
            search_query = result.search_query or ""
        except Exception as exc:
            error_field = f"{type(exc).__name__}: {exc}"
            new_has = None
            logger.error(f"  Exception: {error_field}")

        elapsed = time.time() - start
        diff_label = _classify_diff(old_has, new_has, error_field)

        if error_field:
            summary["errors"] += 1
        elif new_has == old_has:
            summary["judgment_unchanged"] += 1
        else:
            summary["judgment_changed"] += 1

        logger.info(
            f"  -> old={old_has} new={new_has} tier={new_tier} "
            f"matched_n={len(new_urls)} elapsed={elapsed:.2f}s diff={diff_label}"
        )

        out_events.append(
            {
                "event_id": event_id,
                "title": title,
                "summary": summary_text,
                "slot_index": ent.get("slot_index"),
                "old_judgment": old,
                "new_judgment": {
                    "has_jp_coverage": new_has,
                    "matched_tier": new_tier,
                    "matched_domains": new_domains,
                    "matched_urls_count": len(new_urls),
                    "excluded_urls_count": len(excluded_urls),
                    "search_query": search_query,
                    "error": error_field,
                },
                "diff": diff_label,
                "elapsed_seconds": round(elapsed, 3),
            }
        )

    output = {
        "version": "1.0",
        "batch": "F-trial-run-post-fix",
        "generated_at": datetime.now().isoformat(),
        "f13b_old_commit": old_commit,
        "f13b_new_commit": new_commit,
        "trial_run_reference": payload.get(
            "trial_run_reference", "試運転 7-K (2026-05-01)"
        ),
        "grounding_model": JP_COVERAGE_GROUNDING_MODEL,
        "events": out_events,
        "summary": {
            **summary,
            "total": len(entries),
            "overall_pattern": _summarize_pattern(out_events),
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Result saved: {output_path}")

    print(f"\n=== Replay Summary ===")
    print(f"Total: {len(entries)}")
    print(f"Judgment changed: {summary['judgment_changed']}")
    print(f"Judgment unchanged: {summary['judgment_unchanged']}")
    print(f"Errors: {summary['errors']}")
    return 0


def _summarize_pattern(events: list[dict]) -> str:
    if not events:
        return "no entries"
    transitions: dict[str, int] = {}
    for e in events:
        key = e["diff"].split(" (")[0]
        transitions[key] = transitions.get(key, 0) + 1
    parts = [f"{k}: {v}" for k, v in sorted(transitions.items())]
    return ", ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="入力 JSON (events 配列を含む)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="出力 JSON パス",
    )
    args = parser.parse_args()
    return replay(args.input, args.output)


if __name__ == "__main__":
    sys.exit(main())
