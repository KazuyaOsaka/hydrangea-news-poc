"""F-particular-angle-design / F-particular-angle-redesign:
カズヤレビュー後の annotations.json 最終化スクリプト。

annotations.json の `kazuya_review.*_revised` フィールドを LLM 出力に優先適用し、
以下 3 ファイルを生成・更新する:

1. annotation_diff.json — LLM 出力と カズヤレビュー後の差分集計
2. stream_classification.json — 25 件の最終系統分類
3. golden_set.json — 19 件に `particular_angle` + `stream_classification` を付与
   - schema 1.0: golden_set v1.1 → v1.2 (3 分類)
   - schema 2.0: golden_set v1.x → v1.3 (4 分類、F-particular-angle-redesign)

★ 試運転 6 件 (7-K 3 + 2026-05-07 3) は golden_set には統合しない。これらは
stream_classification.json で全 25 件まとめて管理する (golden_set は計測精度の
真値セットとして 19 件構成を維持する責務分離)。

Usage:
    # 4 分類版 (F-particular-angle-redesign 以降のデフォルト)
    python scripts/finalize_annotations.py \\
        --input docs/runs/F-particular-angle-design/annotations.json \\
        --output-diff docs/runs/F-particular-angle-design/annotation_diff.json \\
        --output-classification docs/runs/F-particular-angle-design/stream_classification.json \\
        --update-golden-set docs/runs/F-verify-jp-coverage/golden_set.json \\
        --schema-version 2.0

    # 3 分類版 (F-particular-angle-design 互換、下位互換のため保持)
    python scripts/finalize_annotations.py \\
        --input docs/runs/F-particular-angle-design/annotations.json \\
        --output-diff docs/runs/F-particular-angle-design/annotation_diff.json \\
        --output-classification docs/runs/F-particular-angle-design/stream_classification.json \\
        --update-golden-set docs/runs/F-verify-jp-coverage/golden_set.json \\
        --schema-version 1.0

このスクリプトはカズヤレビュー完了後にのみ実行する想定。レビュー前 (即ち
すべての kazuya_review.*_revised が None) でも動作するが、その場合は LLM 出力が
そのまま最終値として採用される (差分ゼロ)。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.shared.logger import get_logger  # noqa: E402

logger = get_logger("finalize_annotations")

_VALID_STREAMS_V1 = (
    "stream_1_silence_gap",
    "stream_3_framing_inversion",
    "out_of_scope",
)
_VALID_STREAMS_V2 = (
    "stream_1_silence_gap",
    "stream_2_perspective_gap",
    "stream_3_framing_inversion",
    "out_of_scope",
)


def _resolve_final(annotation: dict) -> dict:
    """annotation 1 件分から最終値 (LLM 出力 ∪ カズヤレビュー上書き) を解決する。

    schema_version に依存しない (同じ kazuya_review 構造を扱う)。
    """
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


def build_stream_classification(
    annotations: list[dict],
    schema_version: str,
) -> dict:
    """25 件の最終系統分類を構築する (schema_version に応じて 3 or 4 分類)。"""
    if schema_version == "2.0":
        valid_streams = _VALID_STREAMS_V2
        batch_label = "F-particular-angle-redesign"
    else:
        valid_streams = _VALID_STREAMS_V1
        batch_label = "F-particular-angle-design"

    classified: dict[str, list[dict]] = {s: [] for s in valid_streams}
    classified["unknown"] = []

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
        "version": "2.0" if schema_version == "2.0" else "1.0",
        "schema_version": schema_version,
        "batch": batch_label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_events": len(annotations),
        "counts": {k: len(v) for k, v in classified.items()},
        "events_by_stream": classified,
    }


def update_golden_set(
    golden_set_path: Path,
    annotations: list[dict],
    schema_version: str,
) -> dict:
    """golden_set を更新する。

    schema_version 1.0 (3 分類): golden_set → v1.2
    schema_version 2.0 (4 分類): golden_set → v1.3 (旧版 v1.2 がある場合は v1.2 として
        バックアップ、無ければ v1.1 のまま入力扱い)
    """
    payload = json.loads(golden_set_path.read_text(encoding="utf-8"))
    existing_version = payload.get("version", "unknown")
    annotations_by_id: dict[str, dict] = {ann["event_id"]: ann for ann in annotations}

    if schema_version == "2.0":
        target_version = "1.3"
        batch_label = "F-particular-angle-redesign"
        backup_suffix_for_existing = (
            "v1.2" if existing_version == "1.2" else f"v{existing_version}"
        )
    else:
        target_version = "1.2"
        batch_label = "F-particular-angle-design"
        backup_suffix_for_existing = f"v{existing_version}"

    # Backup the existing version if it differs from the target.
    if existing_version != target_version:
        backup_path = golden_set_path.parent / (
            golden_set_path.stem + f"_{backup_suffix_for_existing}.json"
        )
        if not backup_path.exists():
            shutil.copy2(golden_set_path, backup_path)
            logger.info(
                f"Backed up existing golden_set ({existing_version}) to {backup_path}"
            )
        else:
            logger.info(
                f"Backup {backup_path} already exists — keeping existing snapshot, not overwriting."
            )

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
                "source": batch_label,
                "schema_version": schema_version,
                "final_stream_source": resolved["final_stream_source"],
                "review_note": resolved["review_note"],
                "applied_at": datetime.now(timezone.utc).isoformat(),
            }
            updated += 1
        else:
            not_found_in_annotations.append(eid)

    payload["version"] = target_version
    payload["last_updated_at"] = datetime.now(timezone.utc).date().isoformat()
    payload["last_update_batch"] = batch_label

    changelog_summary = (
        "F-particular-angle-redesign (2026-05-07): 3 分類 → 4 分類化に伴い、"
        "各 entry の stream_classification を 4 分類対応 (stream_1_silence_gap / "
        "stream_2_perspective_gap / stream_3_framing_inversion / out_of_scope) に更新。"
        "particular_angle_meta.schema_version=2.0 を付与。"
        "試運転 6 件は本ファイルに統合せず stream_classification.json で全 25 件管理する責務分離は維持。"
        if schema_version == "2.0"
        else (
            "F-particular-angle-design (2026-05-07): 各 entry に particular_angle "
            "(LLM 抽出 + カズヤレビュー後) + stream_classification (系統 1 / 系統 2 / 対象外) "
            "+ particular_angle_meta フィールドを追加。試運転 6 件は本ファイルに統合せず "
            "stream_classification.json で全 25 件まとめて管理する責務分離。"
        )
    )

    changelog_key = (
        "v1_3_changelog" if schema_version == "2.0" else "v1_2_changelog"
    )
    payload[changelog_key] = {
        "summary": changelog_summary,
        "schema_version": schema_version,
        "entries_updated_count": updated,
        "not_found_in_annotations": not_found_in_annotations,
        "previous_version": existing_version,
    }

    golden_set_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "previous_version": existing_version,
        "new_version": target_version,
        "updated_count": updated,
        "not_found_in_annotations": not_found_in_annotations,
    }


def _validate_schema_streams(
    annotations: list[dict], schema_version: str
) -> list[str]:
    """4 分類スキーマで入力 annotations を検証し、不適合 event_id を返す。"""
    if schema_version == "2.0":
        valid = set(_VALID_STREAMS_V2)
    else:
        valid = set(_VALID_STREAMS_V1)
    invalid: list[str] = []
    for ann in annotations:
        sce = ann.get("stream_classification_estimate") or {}
        review = ann.get("kazuya_review") or {}
        # Resolved stream is what we'll write out — validate that.
        sc_revised = review.get("stream_classification_revised")
        if isinstance(sc_revised, str) and sc_revised.strip():
            stream = sc_revised
        else:
            stream = sce.get("estimated_stream")
        if stream and stream not in valid:
            invalid.append(f"{ann.get('event_id')} (stream={stream})")
    return invalid


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Finalize annotations after kazuya review "
            "(F-particular-angle-design schema 1.0 / F-particular-angle-redesign schema 2.0)"
        )
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
        help="golden_set.json のパス",
    )
    parser.add_argument(
        "--schema-version",
        default="2.0",
        choices=["1.0", "2.0"],
        help=(
            "出力スキーマのバージョン。"
            "1.0 = 3 分類 (F-particular-angle-design 互換)、"
            "2.0 = 4 分類 (F-particular-angle-redesign 以降のデフォルト)。"
        ),
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

    invalid = _validate_schema_streams(annotations, args.schema_version)
    if invalid:
        logger.error(
            f"⚠ schema_version={args.schema_version} と不整合な stream_classification "
            f"が {len(invalid)} 件: {invalid[:5]}{' ...' if len(invalid) > 5 else ''}"
        )
        if args.schema_version == "2.0":
            logger.error(
                "schema 2.0 (4 分類) を選択していますが、入力に 3 分類のみ含まれる "
                "可能性があります。reclassify_annotations.py を先に実行するか、"
                "--schema-version 1.0 を指定してください。"
            )
        else:
            logger.error(
                "schema 1.0 (3 分類) を選択していますが、入力に 4 分類が含まれる "
                "可能性があります。--schema-version 2.0 を指定してください。"
            )
        return 3

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

    classification = build_stream_classification(annotations, args.schema_version)
    args.output_classification.parent.mkdir(parents=True, exist_ok=True)
    args.output_classification.write_text(
        json.dumps(classification, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(
        f"Wrote {args.output_classification} (counts={classification['counts']})"
    )

    update_result = update_golden_set(
        args.update_golden_set, annotations, args.schema_version
    )
    logger.info(
        f"Updated {args.update_golden_set} "
        f"(previous_version={update_result['previous_version']}, "
        f"new_version={update_result['new_version']}, "
        f"updated_count={update_result['updated_count']}, "
        f"not_found_in_annotations={update_result['not_found_in_annotations']})"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
