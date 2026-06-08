#!/usr/bin/env python
"""F-title-guard-coverage-claim-policy (1-Q.5): coverage claim guard 手動ランナー。

保存済みの生成成果物 ({cls}_script.json + {cls}_article.md + {cls}_analysis.json)
に対して coverage claim 事実整合 guard を実行し、CoverageClaimGuardResult を
JSON で出力する。

第一作 (1-S) は手動運用のため、本ランナーで title / article の coverage claim が
系統判定 (stream_classification) と矛盾していないかを生成後に確認する。検出は flag のみ
(自動置換・再生成はしない)。LLM judge を呼ぶため GEMINI_API_KEY が必要。

使い方:
    python scripts/run_coverage_claim_guard.py \
        --dir docs/runs/F-particular-angle-metadata-production-wire/trial_outputs/fresh_run \
        --cls cls-c8876d474612

デフォルトは X1 Slot-1 (本バッチの動機ケース: platform_title="日本では報道されない
Israelの視点" が stream_2_perspective_gap に対し silence 絶対表現)。
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.generation.coverage_claim_guard import run_coverage_claim_guard
from src.shared.models import AnalysisResult, NewsEvent, ScoredEvent, VideoScript

_DEFAULT_DIR = (
    "docs/runs/F-particular-angle-metadata-production-wire/trial_outputs/fresh_run"
)
_DEFAULT_CLS = "cls-c8876d474612"


def _load_scored_event(analysis_path: Path, canonical_title: str) -> ScoredEvent:
    """保存済み analysis.json から AnalysisResult を復元し ScoredEvent を組む。

    guard は scored_event を真値 stream_classification の参照にのみ使う
    (event 本体は guard ロジックで直接参照しない) ため、NewsEvent は最小構成。
    """
    analysis = AnalysisResult.model_validate_json(analysis_path.read_text(encoding="utf-8"))
    event = NewsEvent(
        id=analysis.event_id,
        title=canonical_title or analysis.event_id,
        summary="",
        category="geopolitics",
        source="",
        published_at=datetime.now(timezone.utc),
    )
    return ScoredEvent(
        event=event,
        score=0.0,
        channel_id=analysis.channel_id or "geo_lens",
        analysis_result=analysis,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=_DEFAULT_DIR, help="成果物ディレクトリ")
    parser.add_argument("--cls", default=_DEFAULT_CLS, help="cls id (ファイル接頭辞)")
    args = parser.parse_args()

    base = Path(args.dir)
    script_path = base / f"{args.cls}_script.json"
    article_path = base / f"{args.cls}_article.md"
    analysis_path = base / f"{args.cls}_analysis.json"
    for p in (script_path, article_path, analysis_path):
        if not p.exists():
            print(f"[run_coverage_claim_guard] missing artifact: {p}")
            return 1

    video_script = VideoScript.model_validate_json(script_path.read_text(encoding="utf-8"))
    article_markdown = article_path.read_text(encoding="utf-8")
    canonical = ""
    if video_script.title_layer is not None:
        canonical = video_script.title_layer.canonical_title
    scored_event = _load_scored_event(analysis_path, canonical)

    result = run_coverage_claim_guard(scored_event, video_script, article_markdown)

    print(json.dumps(json.loads(result.model_dump_json()), ensure_ascii=False, indent=2))
    if result.flagged:
        print(f"\n[FLAGGED] {len(result.flags)} coverage-claim contradiction(s) detected.")
    elif result.skipped:
        print(f"\n[SKIPPED] {result.skip_reason}")
    else:
        print("\n[OK] no coverage-claim contradiction detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
