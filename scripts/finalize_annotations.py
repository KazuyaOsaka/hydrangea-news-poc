"""F-particular-angle-design: カズヤレビュー後の annotations.json 最終化スクリプト。

annotations.json の `kazuya_review.*_revised` フィールドを LLM 出力に優先適用し、
以下 3 ファイルを生成・更新する:

1. annotation_diff.json — LLM 出力と カズヤレビュー後の差分集計
2. stream_classification.json — 25 件の最終系統分類
3. golden_set.json v1.2 — 既存 golden_set v1.1 の 19 件に
   `particular_angle` + `stream_classification` フィールドを追加

★ 試運転 6 件 (7-K 3 + 2026-05-07 3) は golden_set には統合しない。これらは
stream_classification.json で全 25 件まとめて管理する (golden_set は計測精度の
真値セットとして 19 件構成を維持する責務分離)。

Usage:
    python scripts/finalize_annotations.py \\
        --input docs/runs/F-particular-angle-design/annotations.json \\
        --output-diff docs/runs/F-particular-angle-design/annotation_diff.json \\
        --output-classification docs/runs/F-particular-angle-design/stream_classification.json \\
        --update-golden-set docs/runs/F-verify-jp-coverage/golden_set.json

このスクリプトはカズヤレビュー完了後にのみ実行する想定。レビュー前 (即ち
すべての kazuya_review.*_revised が None) でも動作するが、その場合は LLM 出力が
そのまま最終値として採用される (差分ゼロ)。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.shared.logger import get_logger  # noqa: E402

logger = get_logger("finalize_annotations")


def _resolve_final(annotation: dict) -> dict:
    """annotation 1 件分から最終値 (LLM 出力 ∪ カズヤレビュー上書き) を解決する。"""
    pa = annotation.get("particular_angle") or {}
    sce = annotation.get("stream_classification_estimate") or {}
    review = annotation.get("kazuya_review") or {}

    pa_revised = review.get("particular_angle_revised")
    sc_revised = review.get("stream_classification_revised")

    final_pa = pa_revised if pa_revised is not None else pa
    if isinstance(sc_revised, str) and sc_revised.strip():
        final_stream = sc_revised
        final_stream_source = "kazuya_review"
    else:
        final_stream = sce.get("estimated_stream")
        final_stream_source = "llm_estimate"

    return {
        "final_particular_angle": final_pa,
        "final_stream_classification": final_stream,
        "final_stream_source": final_stream_source,
        "review_note": review.get("review_note"),
    }


def build_annotation_diff(annotations: list[dict]) -> dict:
    """LLM 出力 vs カズヤレビュー後の差分集計を構築する。"""
    pa_revised_count = 0
    stream_revised_count = 0
    review_notes_count = 0
    diffs: list[dict] = []

    for ann in annotations:
        review = ann.get("kazuya_review") or {}
        pa_revised = review.get("particular_angle_revised") is not None
        stream_revised = (
            isinstance(review.get("stream_classification_revised"), str)
            and review["stream_classification_revised"].strip()
        )
        note = review.get("review_note")

        if pa_revised:
            pa_revised_count += 1
        if stream_revised:
            stream_revised_count += 1
        if note:
            review_notes_count += 1

        if pa_revised or stream_revised or note:
            diffs.append({
                "event_id": ann.get("event_id"),
                "title": ann.get("title"),
                "particular_angle_revised": pa_revised,
                "stream_classification_revised": stream_revised,
                "review_note": note,
                "llm_stream": (ann.get("stream_classification_estimate") or {}).get(
                    "estimated_stream"
                ),
                "kazuya_stream": review.get("stream_classification_revised"),
            })

    return {
        "version": "1.0",
        "batch": "F-particular-angle-design",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_events": len(annotations),
        "summary": {
            "particular_angle_revised_count": pa_revised_count,
            "stream_classification_revised_count": stream_revised_count,
            "review_notes_count": review_notes_count,
            "fully_unmodified_count": len(annotations)
            - sum(
                1
                for ann in annotations
                if (ann.get("kazuya_review") or {}).get("particular_angle_revised") is not None
                or (
                    isinstance(
                        (ann.get("kazuya_review") or {}).get("stream_classification_revised"),
                        str,
                    )
                    and (ann.get("kazuya_review") or {})["stream_classification_revised"].strip()
                )
                or (ann.get("kazuya_review") or {}).get("review_note")
            ),
        },
        "diffs": diffs,
    }


def build_stream_classification(annotations: list[dict]) -> dict:
    """25 件の最終系統分類を構築する。"""
    classified: dict[str, list[dict]] = {
        "stream_1_silence_gap": [],
        "stream_2_framing_inversion": [],
        "out_of_scope": [],
        "unknown": [],
    }
    for ann in annotations:
        resolved = _resolve_final(ann)
        stream = resolved["final_stream_classification"] or "unknown"
        if stream not in classified:
            stream = "unknown"
        classified[stream].append({
            "event_id": ann.get("event_id"),
            "title": ann.get("title"),
            "source_origin": ann.get("source_origin"),
            "particular_angle": resolved["final_particular_angle"],
            "final_stream_source": resolved["final_stream_source"],
            "review_note": resolved["review_note"],
        })

    return {
        "version": "1.0",
        "batch": "F-particular-angle-design",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_events": len(annotations),
        "counts": {k: len(v) for k, v in classified.items()},
        "events_by_stream": classified,
    }


def update_golden_set(golden_set_path: Path, annotations: list[dict]) -> dict:
    """golden_set v1.1 → v1.2 に更新する (各 event に particular_angle +
    stream_classification を追加)。試運転 6 件は統合しない。
    """
    payload = json.loads(golden_set_path.read_text(encoding="utf-8"))
    annotations_by_id: dict[str, dict] = {ann["event_id"]: ann for ann in annotations}

    updated = 0
    not_found_in_annotations: list[str] = []
    for entry in payload.get("entries", []):
        eid = entry.get("id")
        if eid in annotations_by_id:
            ann = annotations_by_id[eid]
            resolved = _resolve_final(ann)
            entry["particular_angle"] = resolved["final_particular_angle"]
            entry["stream_classification"] = resolved["final_stream_classification"]
            entry["particular_angle_meta"] = {
                "source": "F-particular-angle-design",
                "final_stream_source": resolved["final_stream_source"],
                "review_note": resolved["review_note"],
                "applied_at": datetime.now(timezone.utc).isoformat(),
            }
            updated += 1
        else:
            not_found_in_annotations.append(eid)

    payload["version"] = "1.2"
    payload["last_updated_at"] = datetime.now(timezone.utc).date().isoformat()
    payload["last_update_batch"] = "F-particular-angle-design"
    existing_changelog = payload.get("v1_1_changelog")
    payload["v1_2_changelog"] = {
        "summary": (
            "F-particular-angle-design (2026-05-07): 各 entry に particular_angle "
            "(LLM 抽出 + カズヤレビュー後) + stream_classification (系統 1 / 系統 2 / 対象外) "
            "+ particular_angle_meta フィールドを追加。試運転 6 件は本ファイルに統合せず "
            "stream_classification.json で全 25 件まとめて管理する責務分離。"
        ),
        "entries_updated_count": updated,
        "not_found_in_annotations": not_found_in_annotations,
        "kept_v1_1_changelog": bool(existing_changelog),
    }

    golden_set_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "updated_count": updated,
        "not_found_in_annotations": not_found_in_annotations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Finalize F-particular-angle-design annotations after kazuya review"
    )
    parser.add_argument("--input", required=True, type=Path, help="annotations.json のパス")
    parser.add_argument(
        "--output-diff",
        required=True,
        type=Path,
        help="annotation_diff.json の出力先",
    )
    parser.add_argument(
        "--output-classification",
        required=True,
        type=Path,
        help="stream_classification.json の出力先",
    )
    parser.add_argument(
        "--update-golden-set",
        required=True,
        type=Path,
        help="golden_set.json のパス (v1.1 を v1.2 に更新)",
    )
    args = parser.parse_args()

    args.input = args.input.resolve()
    args.output_diff = args.output_diff.resolve()
    args.output_classification = args.output_classification.resolve()
    args.update_golden_set = args.update_golden_set.resolve()

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        return 2
    if not args.update_golden_set.exists():
        logger.error(f"Golden set not found: {args.update_golden_set}")
        return 2

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    annotations = payload.get("events", [])
    if not annotations:
        logger.error("No annotations found in input")
        return 2

    diff = build_annotation_diff(annotations)
    args.output_diff.parent.mkdir(parents=True, exist_ok=True)
    args.output_diff.write_text(
        json.dumps(diff, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(
        f"Wrote {args.output_diff} "
        f"(pa_revised={diff['summary']['particular_angle_revised_count']}, "
        f"stream_revised={diff['summary']['stream_classification_revised_count']})"
    )

    classification = build_stream_classification(annotations)
    args.output_classification.parent.mkdir(parents=True, exist_ok=True)
    args.output_classification.write_text(
        json.dumps(classification, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(
        f"Wrote {args.output_classification} (counts={classification['counts']})"
    )

    update_result = update_golden_set(args.update_golden_set, annotations)
    logger.info(
        f"Updated {args.update_golden_set} (updated_count={update_result['updated_count']}, "
        f"not_found_in_annotations={update_result['not_found_in_annotations']})"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
