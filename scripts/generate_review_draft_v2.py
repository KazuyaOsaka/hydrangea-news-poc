"""F-particular-angle-redesign: 4 分類版 review_draft_v2.md 生成スクリプト。

入力 annotations.json (4 分類版、stream_classification_estimate に 4 分類値が入って
いる + legacy_stream_classification_v1 に 3 分類版がバックアップされている) を読み、
カズヤレビュー用の人間読み Markdown を生成する。

特徴:
- 各 event 冒頭に **3 分類版 → 4 分類版** の表示で変更が一目でわかる構造
- 冒頭に「★ 重点レビュー」セクション (3 分類 → 4 分類で変更があった events を別出し)
- カズヤレビュー欄に「4 分類版判定の妥当性」確認チェックボックス追加

Usage:
    python scripts/generate_review_draft_v2.py \\
        --input docs/runs/F-particular-angle-design/annotations.json \\
        --output docs/runs/F-particular-angle-redesign/review_draft_v2.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _stream_label(stream: str | None) -> str:
    if not stream:
        return "(unknown)"
    mapping = {
        "stream_1_silence_gap": "系統 1 (silence_gap)",
        "stream_2_perspective_gap": "系統 2 (perspective_gap、★ 旧名: 系統 1.5)",
        "stream_3_framing_inversion": "系統 3 (framing_inversion、★ 旧名: 系統 2)",
        "out_of_scope": "動画化対象外",
    }
    return mapping.get(stream, stream)


def render_event(idx: int, ann: dict) -> str:
    pa = ann.get("particular_angle") or {}
    new_sce = ann.get("stream_classification_estimate") or {}
    old_sce = ann.get("legacy_stream_classification_v1") or {}

    old_stream = old_sce.get("estimated_stream") or "(unknown)"
    new_stream = new_sce.get("estimated_stream") or "(unknown)"
    changed_marker = " **★ 変更あり**" if old_stream != new_stream else ""

    lines: list[str] = []
    lines.append(f"### Event {idx}: {ann.get('event_id')} ({ann.get('source_origin')})")
    lines.append("")
    lines.append(f"**タイトル**: {ann.get('title')}")
    lines.append("")
    summary = ann.get("summary_excerpt") or ann.get("summary") or ""
    lines.append(f"**要約**: {summary}")
    lines.append("")
    lines.append(
        f"**3 分類版 → 4 分類版判定**: `{old_stream}` → `{new_stream}`{changed_marker}"
    )
    lines.append("")
    lines.append("**特定角度 (LLM 抽出、本バッチでは不変)**:")
    lines.append("")
    lines.append(f"- core_question: {pa.get('core_question') or '(none)'}")
    lines.append(
        f"- differentiation: {pa.get('differentiation_from_mainstream') or '(none)'}"
    )
    lines.append(
        f"- hydrangea_axis: {pa.get('hydrangea_axis_alignment') or '(none)'}"
    )
    lines.append(
        f"- extraction_confidence: {pa.get('extraction_confidence') or '(unknown)'}"
    )
    lines.append("")
    lines.append(
        f"**4 分類版 LLM 判定**: {_stream_label(new_stream)} "
        f"(confidence: {new_sce.get('confidence') or '(unknown)'})"
    )
    lines.append("")
    lines.append("**判定根拠**:")
    lines.append("")
    lines.append(f"- reasoning: {new_sce.get('reasoning') or '(none)'}")
    lines.append(
        f"- broad_event_jp_coverage: "
        f"{new_sce.get('broad_event_jp_coverage') or '(unknown)'}"
    )
    lines.append(
        f"- particular_angle_jp_coverage: "
        f"{new_sce.get('particular_angle_jp_coverage') or '(unknown)'}"
    )
    lines.append("")
    if old_sce:
        lines.append("**3 分類版 LLM 判定 (参考、再分類前)**:")
        lines.append("")
        lines.append(f"- estimated_stream: {old_stream}")
        lines.append(f"- reasoning: {old_sce.get('reasoning') or '(none)'}")
        lines.append(f"- confidence: {old_sce.get('confidence') or '(unknown)'}")
        lines.append("")
    if ann.get("extraction_error"):
        lines.append(f"**⚠ extraction_error**: {ann.get('extraction_error')}")
        lines.append("")
    lines.append("**カズヤレビュー欄 (4 分類版での再評価)**:")
    lines.append("")
    lines.append("- [ ] 4 分類版判定 OK / 修正必要 (修正は `kazuya_review.stream_classification_revised`)")
    lines.append("- [ ] 特定角度 OK / 修正必要 (修正は `kazuya_review.particular_angle_revised`)")
    lines.append("- 3 分類 → 4 分類への変更妥当性: ___________")
    lines.append("- コメント: ___________")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate review_draft_v2.md from 4-class annotations.json"
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    args.input = args.input.resolve()
    args.output = args.output.resolve()
    if not args.input.exists():
        print(f"Input file not found: {args.input}", file=sys.stderr)
        return 2

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    annotations = payload.get("events", [])
    summary = payload.get("summary", {})
    schema_version = payload.get("schema_version", payload.get("version", "unknown"))
    reclassified_at = payload.get("reclassified_at", payload.get("extracted_at", "unknown"))

    # Build "重点レビュー" section: events whose stream changed in 3→4 reclassification.
    spotlight_changed: list[tuple[int, dict]] = []
    spotlight_into_1_5: list[tuple[int, dict]] = []
    for i, ann in enumerate(annotations, start=1):
        old = (ann.get("legacy_stream_classification_v1") or {}).get("estimated_stream")
        new = (ann.get("stream_classification_estimate") or {}).get("estimated_stream")
        if old and new and old != new:
            spotlight_changed.append((i, ann))
            if new == "stream_2_perspective_gap":
                spotlight_into_1_5.append((i, ann))

    out: list[str] = []
    out.append("# F-particular-angle-redesign レビュードラフト v2 (4 分類化)")
    out.append("")
    out.append(f"生成元 annotations.json: schema_version={schema_version}")
    out.append(f"再分類実施日時: {reclassified_at}")
    out.append(f"対象 events: {len(annotations)} 件")
    out.append("")
    out.append(
        "本ドラフトは F-particular-angle-redesign で 3 分類 → 4 分類化を実施した結果の"
        "カズヤレビュー用です。"
    )
    out.append("")
    out.append("## 4 分類化サマリ")
    out.append("")
    dist = summary.get("stream_classification_estimate_distribution", {})
    out.append(f"- stream_1_silence_gap: {dist.get('stream_1_silence_gap', 0)} 件")
    out.append(
        f"- stream_2_perspective_gap (★ NEW): "
        f"{dist.get('stream_2_perspective_gap', 0)} 件"
    )
    out.append(
        f"- stream_3_framing_inversion: "
        f"{dist.get('stream_3_framing_inversion', 0)} 件"
    )
    out.append(f"- out_of_scope: {dist.get('out_of_scope', 0)} 件")
    out.append(f"- unknown: {dist.get('unknown', 0)} 件")
    out.append(f"- 再分類エラー: {summary.get('reclassification_errors', 0)} 件")
    out.append(f"- 3 → 4 分類への変更件数: {len(spotlight_changed)} 件")
    out.append("")
    out.append("## レビュー手順")
    out.append("")
    out.append("各 event について以下を確認してください:")
    out.append("")
    out.append("1. `stream_classification_estimate` (4 分類版) が妥当か")
    out.append("   - 系統 1 (両方未報道) / 系統 2 (広範のみ報道、★ 旧 1.5) / 系統 3 (解釈差、★ 旧 2) / 対象外")
    out.append("2. 3 分類版からの変更がある場合、その変更が妥当か")
    out.append("3. 必要に応じて `particular_angle` も再評価 (4 分類化に伴う改訂が必要なら)")
    out.append("")
    out.append(
        "修正があれば該当 event の `kazuya_review.*_revised` フィールドに修正値を、"
        "`review_note` にコメントを記入してください (annotations.json を直接編集)。"
        "修正完了後、scripts/finalize_annotations.py --schema-version 2.0 を実行してください。"
    )
    out.append("")
    out.append("---")
    out.append("")
    out.append("## ★ 重点レビュー: 3 分類 → 4 分類で変更があった events")
    out.append("")
    if not spotlight_changed:
        out.append("(変更なし)")
        out.append("")
    else:
        out.append("以下の events は再分類で系統が変わりました。判定の妥当性を重点確認してください。")
        out.append("")
        if spotlight_into_1_5:
            out.append(
                f"### 系統 2 (perspective_gap、★ 旧 1.5) への移動: {len(spotlight_into_1_5)} 件"
            )
            out.append("")
            for i, ann in spotlight_into_1_5:
                old = (
                    ann.get("legacy_stream_classification_v1") or {}
                ).get("estimated_stream")
                out.append(
                    f"- Event {i}: `{ann.get('event_id')}` ({ann.get('title')})"
                    f" — `{old}` → `stream_2_perspective_gap`"
                )
            out.append("")

        other_transitions = [
            (i, a)
            for i, a in spotlight_changed
            if (a.get("stream_classification_estimate") or {}).get("estimated_stream")
            != "stream_2_perspective_gap"
        ]
        if other_transitions:
            out.append(f"### その他の変更: {len(other_transitions)} 件")
            out.append("")
            for i, ann in other_transitions:
                old = (
                    ann.get("legacy_stream_classification_v1") or {}
                ).get("estimated_stream")
                new = (
                    ann.get("stream_classification_estimate") or {}
                ).get("estimated_stream")
                out.append(
                    f"- Event {i}: `{ann.get('event_id')}` ({ann.get('title')})"
                    f" — `{old}` → `{new}`"
                )
            out.append("")
    out.append("---")
    out.append("")
    out.append("## Event 一覧 (全 25 件、event_id 順)")
    out.append("")

    for i, ann in enumerate(annotations, start=1):
        out.append(render_event(i, ann))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {args.output} ({len(annotations)} events)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
