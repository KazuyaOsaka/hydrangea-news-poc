#!/usr/bin/env python
"""F-editorial-guardian-claim-extraction (1-T.1): Editorial Guardian 手動ランナー。

保存済みの生成成果物 ({cls}_script.json + {cls}_article.md + {cls}_analysis.json)
と recent_event_pool.event_snapshot (生成器が見たイベントデータ) に対して
Editorial Guardian を実行し、2層検証レポート (EditorialGuardianReport) を
JSON で出力する。

第一作 (1-S) は手動運用のため、本ランナーで article / script / title の
高リスク事実主張 (ADR-0003) を公開前に抽出 + 忠実性検証する。検出は flag のみ
(自動修正・再生成・公開ブロックはしない、公開判断はカズヤ)。
Guardian モデル (gemini-3.1-pro-preview、paid-only) を呼ぶため GEMINI_API_KEY +
課金設定が必要。primary 不可時は guardian_unavailable (検証未完) と明示される。

使い方:
    python scripts/run_editorial_guardian.py \
        --cls cls-c8876d474612 \
        --dir data/output \
        --out docs/runs/F-editorial-guardian-claim-extraction/x1_slot1_guardian_report.json

デフォルトは X1 Slot-1 (高リスク主張の実証ケース: 死者数 3,371 人 / 10,129 人 /
兵士死亡 25 人 / スモトリッチ発言引用が production 未検証のまま出力された)。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# プロジェクトルートを sys.path に追加 (scripts/ から src/ をインポートするため、
# extract_particular_angle.py 前例踏襲)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.generation.editorial_guardian import run_editorial_guardian
from src.shared.models import AnalysisResult, ScoredEvent, VideoScript

_DEFAULT_DIR = "data/output"
_DEFAULT_CLS = "cls-c8876d474612"
_DEFAULT_DB = "data/db/hydrangea.db"


def _load_scored_event(
    db_path: Path, event_id: str, analysis_path: Path
) -> tuple[ScoredEvent, bool]:
    """生成器が見たイベントデータを再構成して (ScoredEvent, snapshot_found) を返す。

    recent_event_pool.event_snapshot (ScoredEvent JSON、ab_article_model_upgrade.py
    前例踏襲) を読み、{cls}_analysis.json の AnalysisResult を合成する
    (CP-1 実測: pool snapshot は分析前保存のため analysis_result=None)。
    snapshot 不在の場合は analysis.json のみから最小構成で組む (scope の
    has_event=False が照合素材の欠落をレポートに明示する)。
    """
    analysis = AnalysisResult.model_validate_json(
        analysis_path.read_text(encoding="utf-8")
    )

    snapshot_found = False
    scored_event: ScoredEvent | None = None
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT event_snapshot FROM recent_event_pool WHERE event_id = ?",
                (event_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is not None:
            scored_event = ScoredEvent.model_validate(json.loads(row[0]))
            snapshot_found = True

    if scored_event is None:
        print(
            f"[run_editorial_guardian] WARNING: event_id={event_id} not found in "
            f"recent_event_pool ({db_path}); source material will lack event data."
        )
        from datetime import datetime, timezone

        from src.shared.models import NewsEvent

        scored_event = ScoredEvent(
            event=NewsEvent(
                id=analysis.event_id,
                title="",
                summary="",
                category="geopolitics",
                source="",
                published_at=datetime.now(timezone.utc),
            ),
            score=0.0,
            channel_id=analysis.channel_id or "geo_lens",
        )
        # has_event=False を scope に反映するため event を外す手段が無いので、
        # 最小 event のまま進める (summary/global_view 0 chars が scope に出る)。

    return (
        scored_event.model_copy(update={"analysis_result": analysis}),
        snapshot_found,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=_DEFAULT_DIR, help="成果物ディレクトリ")
    parser.add_argument("--cls", default=_DEFAULT_CLS, help="cls id (ファイル接頭辞)")
    parser.add_argument("--db", default=_DEFAULT_DB, help="hydrangea.db パス")
    parser.add_argument("--out", default=None, help="レポート JSON の保存先 (省略時は stdout のみ)")
    args = parser.parse_args()

    base = Path(args.dir)
    script_path = base / f"{args.cls}_script.json"
    article_path = base / f"{args.cls}_article.md"
    analysis_path = base / f"{args.cls}_analysis.json"
    for p in (script_path, article_path, analysis_path):
        if not p.exists():
            print(f"[run_editorial_guardian] missing artifact: {p}")
            return 1

    video_script = VideoScript.model_validate_json(
        script_path.read_text(encoding="utf-8")
    )
    article_markdown = article_path.read_text(encoding="utf-8")
    scored_event, snapshot_found = _load_scored_event(
        Path(args.db), args.cls, analysis_path
    )
    print(
        f"[run_editorial_guardian] cls={args.cls} snapshot_found={snapshot_found} "
        f"summary_chars={len(scored_event.event.summary or '')}"
    )

    report = run_editorial_guardian(scored_event, video_script, article_markdown)

    report_json = json.dumps(
        json.loads(report.model_dump_json()), ensure_ascii=False, indent=2
    )
    print(report_json)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report_json + "\n", encoding="utf-8")
        print(f"\n[run_editorial_guardian] report saved: {out_path}")

    if report.guardian_unavailable:
        print(
            f"\n[GUARDIAN UNAVAILABLE] 検証未完: {report.unavailable_reason} "
            f"(model={report.guardian_model_used})"
        )
        return 2
    if report.flagged_claims:
        print(
            f"\n[FLAGGED] {len(report.flagged_claims)} claim(s) require human review "
            f"(contradicted={report.n_contradicted} "
            f"not_in_source={report.n_not_in_source} "
            f"unverified={report.n_unverified})"
        )
    else:
        print(
            f"\n[OK] all {report.n_supported} high-risk claim(s) supported by "
            f"generator input (truthfulness layer = pending, 1-T.2)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
