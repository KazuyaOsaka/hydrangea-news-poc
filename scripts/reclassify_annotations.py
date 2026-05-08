"""F-particular-angle-redesign: 3 分類 → 4 分類化 LLM 再判定スクリプト。

入力 annotations.json (3 分類版、25 件) の `particular_angle` を保持し、
`stream_classification_estimate` のみを **4 分類版** で LLM 再判定する。
旧 3 分類の判定値は `legacy_stream_classification_v1` フィールドにバックアップ
する。`kazuya_review` フィールドは 4 分類版で初めてレビューするためリセット。

判定基準は docs/PARTICULAR_ANGLE_DEFINITION.md セクション 3 (4 分類版、命名 1/2/3、
Step 0-4 論理フロー、★ F-particular-angle-redesign-extension で Step 3-4 を改良)
に従う。

★ F-particular-angle-redesign-extension (2026-05-08) で系統名 1/1.5/2 → 1/2/3 に
リネーム済み。`_VALID_STREAMS_V2` および LLM プロンプト内の系統名は新命名で
記述されている (`stream_2_perspective_gap` = 旧 `stream_1_5_perspective_gap`、
`stream_3_framing_inversion` = 旧 `stream_2_framing_inversion`)。

Usage:
    python scripts/reclassify_annotations.py \\
        --input docs/runs/F-particular-angle-design/annotations.json \\
        --backup docs/runs/F-particular-angle-design/annotations_v1_3class.json \\
        --output docs/runs/F-particular-angle-design/annotations.json \\
        --diff-output docs/runs/F-particular-angle-redesign/reclassification_diff.json \\
        --log-output docs/runs/F-particular-angle-redesign/reclassification_log.json \\
        --llm-model gemini-analysis-tier-extended

実装方針:
- LLM クライアントは `extract_particular_angle.py` で確立した
  `_build_extract_client()` 方式 (max_output_tokens=4096) を流用
- LLM 失敗時は最大 3 回リトライ、それでも失敗した event は LLM 出力を
  維持しつつ `extraction_error` に記録して継続
- `particular_angle` は LLM プロンプトに含めて context として与え、判定
  だけ 4 分類で出させる (= particular_angle 自体は不変、判定だけ更新)
- 5 件ごとに進捗ログを出力
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.llm.factory import (  # noqa: E402
    TieredGeminiClient,
    _get_max_attempts_for_role,
    _get_tier_models_for_role,
)
from src.shared.config import GEMINI_API_KEY  # noqa: E402
from src.shared.logger import get_logger  # noqa: E402

logger = get_logger("reclassify_annotations")

_VALID_STREAMS_V2 = {
    "stream_1_silence_gap",
    "stream_2_perspective_gap",
    "stream_3_framing_inversion",
    "out_of_scope",
}

_PROMPT_TEMPLATE = """\
あなたは Hydrangea (海外ニュース解説メディア) の編集判断を支援する LLM です。
入力された海外ニュース 1 件について、既に抽出済みの「特定角度」(particular_angle)
を踏まえて、Hydrangea コアミッション (2 系統並立) における **4 分類** での
系統判定を行ってください。

# 「特定角度」とは
海外メディアが当該事象に対して **独自に掘った視点・問題意識・分析切り口** のこと。
事象そのもの (= 広範事件) ではなく、その事象内で海外メディアが強調している
構造分析角度の 1 ピース。

# 4 分類の定義 (★ 命名 1/2/3、F-particular-angle-redesign-extension で命名整理)
- **stream_1_silence_gap**: 広範事件も特定角度も両方、日本主要メディアで未報道。
  完全な情報空白。
- **stream_2_perspective_gap**: 広範事件は日本主要メディアで報道済み
  だが、特定角度については日本メディアが何も語っていない / 触れていない。
  事件本体は取り上げられたが構造分析角度が欠落 (旧 stream_1_5)。
- **stream_3_framing_inversion**: 広範事件も報道済み + 日本メディアもこの
  特定角度について何かを語っているが、解釈・フレーミング・優先順位が
  日本/西側 vs 海外/東側で対立 (旧 stream_2)。
- **out_of_scope**: 報道差なし、または 4 軸該当性なし、または評価フレーム
  対立はあるが忖度シグナルが弱く解説価値が薄い (動画化対象外)。

# 系統判定の論理フロー (★ Step 0-4、F-particular-angle-redesign-extension で Step 3-4 改良)
- **Step 0**: 特定角度を抽出 (本スクリプトでは `particular_angle` として
  既に抽出済み)
- **Step 1**: 特定角度が Hydrangea 4 軸 (制度・システム / 外交・経済・利害関係 /
  個人・権力者 / 関心領域・地政学的死角) のいずれかに該当するか?
  - No → out_of_scope
  - Yes ↓
- **Step 2**: **広範事件** (= 事象そのもの) が日本主要メディアで報道済みか?
  - No (両方未報道) → stream_1_silence_gap
  - Yes ↓
- **Step 3 (改)**: 日本メディアはこの **特定角度** について何かを語っているか?
  - No (角度の不在 = 触れていない / 言及なし) → stream_2_perspective_gap
  - Yes (語られている) ↓
- **Step 4 (改)**: 日本メディアと海外メディアの **評価フレームが対立**、かつ
  「忖度・報道規制・黙殺」の構造的シグナルがあるか?
  - No → out_of_scope (報道済み + 解釈差なし、または忖度シグナルなしで
    単発の専門解釈差に留まる)
  - Yes → stream_3_framing_inversion

# MECE 判別の核心 (★ F-particular-angle-redesign-extension で明示)
- 系統 2 vs 系統 3 の判別: 「日本メディアはこの特定角度について何かを語って
  いるか?」がコア。
  - 何も語っていない / 触れていない → 系統 2 (perspective_gap)
  - 語っているが評価が海外と対立 → 系統 3 (framing_inversion)
- 中立報道の境界事例: 判定者の解釈に依存するため、迷ったら系統 2 にデフォルト
  し、忖度シグナル level (別軸メタデータ、本スクリプトでは推定しない) で
  間接的に区別する設計とする (level 高 = 系統 3 寄り、低 = 系統 2 寄り)。

# 入力
event_id: {event_id}
title: {title}
summary: {summary}
sources: {sources}

# 既に抽出済みの「特定角度」(参考、変更不要)
core_question: {core_question}
differentiation_from_mainstream: {differentiation_from_mainstream}
hydrangea_axis_alignment: {hydrangea_axis_alignment}

# 旧 3 分類版の判定値 (参考、再評価対象)
legacy_estimated_stream: {legacy_estimated_stream}
legacy_reasoning: {legacy_reasoning}

# 出力 (必ず以下の JSON 形式で、それ以外の文字を一切含めない)
```json
{{
  "stream_classification_estimate": {{
    "estimated_stream": "stream_1_silence_gap / stream_2_perspective_gap / stream_3_framing_inversion / out_of_scope のいずれか",
    "reasoning": "判定根拠 (★ 必須: 広範事件報道状態 + 特定角度報道状態の両方を明記、3-4 文)",
    "confidence": "high / medium / low",
    "broad_event_jp_coverage": "reported / unreported / unknown (広範事件の日本主要メディア報道状態)",
    "particular_angle_jp_coverage": "reported / unreported / unknown (特定角度の日本主要メディア報道状態)"
  }}
}}
```

# 注意事項
- 必ず JSON 形式のみで応答してください。Markdown コードブロック (```json) は付けても
  付けなくても構いません。スクリプト側で除去します。
- ★ 重要: 各文字列値 (reasoning 等) は **1 行に収め、生の改行を含めない**
  でください。複数文を入れる場合はスペースで連結してください。
- ★ 重要: `reasoning` には **広範事件の日本主要メディア報道状態** と
  **特定角度の日本主要メディア報道状態** の両方を必ず明記してください。
  これは F-jp-coverage-tune の二段階クエリ生成設計の基準データになります。
- 旧 3 分類版の判定値は参考であり、必ずしもそれに沿う必要はありません。
  4 分類化に伴って分類が変わるケース (特に旧 stream_1 → 新
  stream_2_perspective_gap、旧 stream_2_framing_inversion → out_of_scope)
  を積極的に検討してください。
- confidence は厳密に判定してください。広範事件 / 特定角度の報道状態の判断が
  困難な場合は medium / low を返してください。
"""


def build_prompt(annotation: dict) -> str:
    """1 件の annotation から再分類用 LLM プロンプトを組み立てる。"""
    pa = annotation.get("particular_angle") or {}
    legacy_sce = annotation.get("stream_classification_estimate") or {}
    sources = annotation.get("sources")
    if isinstance(sources, list) and sources:
        sources_str = ", ".join(s if isinstance(s, str) else str(s) for s in sources)
    elif isinstance(sources, str) and sources:
        sources_str = sources
    else:
        # annotations.json (3-class snapshot) には sources フィールドが無いので
        # source_origin (golden_set_v1.1 / trial_run_7K_2026-05-01 等) で代替する。
        sources_str = annotation.get("source_origin") or ""
    return _PROMPT_TEMPLATE.format(
        event_id=annotation.get("event_id", "(unknown)"),
        title=annotation.get("title", "(no title)"),
        summary=annotation.get("summary_excerpt") or annotation.get("summary") or "(no summary)",
        sources=sources_str or "(no sources)",
        core_question=pa.get("core_question") or "(none)",
        differentiation_from_mainstream=pa.get("differentiation_from_mainstream") or "(none)",
        hydrangea_axis_alignment=pa.get("hydrangea_axis_alignment") or "(none)",
        legacy_estimated_stream=legacy_sce.get("estimated_stream") or "(unknown)",
        legacy_reasoning=legacy_sce.get("reasoning") or "(none)",
    )


def _escape_unescaped_newlines_in_strings(s: str) -> str:
    """JSON 文字列値の中に生の改行が混じっている場合に \\n / \\r / \\t に
    エスケープする最小修復 (extract_particular_angle.py の同名関数を流用)。
    """
    out: list[str] = []
    in_string = False
    escape = False
    for ch in s:
        if escape:
            out.append(ch)
            escape = False
            continue
        if ch == "\\":
            out.append(ch)
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            out.append(ch)
            continue
        if in_string and ch == "\n":
            out.append("\\n")
            continue
        if in_string and ch == "\r":
            out.append("\\r")
            continue
        if in_string and ch == "\t":
            out.append("\\t")
            continue
        out.append(ch)
    return "".join(out)


def parse_llm_response(text: str) -> dict:
    """LLM 応答テキストから JSON を抽出してパースする。"""
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()
    else:
        candidate = text.strip()

    if not candidate.startswith("{"):
        first_brace = candidate.find("{")
        if first_brace >= 0:
            candidate = candidate[first_brace:]
    if not candidate.endswith("}"):
        last_brace = candidate.rfind("}")
        if last_brace >= 0:
            candidate = candidate[: last_brace + 1]

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        fixed = _escape_unescaped_newlines_in_strings(candidate)
        return json.loads(fixed)


_PER_CALL_TIMEOUT_SEC = 90


def _generate_with_timeout(client, prompt: str, timeout_sec: int = _PER_CALL_TIMEOUT_SEC) -> str:
    """client.generate(prompt) を timeout 付きで呼び出す。

    Tier フォールバックで本当に応答が無いケース (API ハング) を avoid するため、
    プロセス全体で 1 件あたり最大 `timeout_sec` 秒待つ。タイムアウトしたら
    TimeoutError を raise して上位リトライに任せる。
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(client.generate, prompt)
        try:
            return future.result(timeout=timeout_sec)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise TimeoutError(
                f"client.generate() exceeded {timeout_sec}s — likely Gemini API hang"
            ) from exc


def reclassify_one(client, annotation: dict, max_retries: int = 3) -> dict:
    """1 件分の系統判定を 4 分類版で LLM 再分類する。"""
    prompt = build_prompt(annotation)
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            response_text = _generate_with_timeout(client, prompt)
            parsed = parse_llm_response(response_text)
            sce = parsed.get("stream_classification_estimate") or {}
            stream = sce.get("estimated_stream")
            if stream not in _VALID_STREAMS_V2:
                raise ValueError(
                    f"estimated_stream '{stream}' not in valid 4-class set: "
                    f"{sorted(_VALID_STREAMS_V2)}"
                )
            _ = sce["reasoning"]
            return sce
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            last_error = exc
            logger.warning(
                f"[{annotation.get('event_id', 'unknown')}] attempt {attempt}/{max_retries} "
                f"failed (parse/validate): {str(exc)[:120]}"
            )
        except TimeoutError as exc:
            last_error = exc
            logger.warning(
                f"[{annotation.get('event_id', 'unknown')}] attempt {attempt}/{max_retries} "
                f"failed (timeout): {str(exc)[:120]}"
            )
            # Brief backoff before retry — timeouts often clear quickly when the API
            # stabilises again.
            if attempt < max_retries:
                time.sleep(2)
        except Exception as exc:
            last_error = exc
            logger.warning(
                f"[{annotation.get('event_id', 'unknown')}] attempt {attempt}/{max_retries} "
                f"failed (api): {str(exc)[:120]}"
            )
            if attempt < max_retries:
                time.sleep(2 * attempt)

    raise RuntimeError(
        f"All {max_retries} attempts failed for event_id={annotation.get('event_id')}: "
        f"{last_error}"
    )


def _build_extract_client():
    """専用 Tier クライアント (analysis Tier 階層 + max_output_tokens=4096)。

    extract_particular_angle.py:_build_extract_client() と同じ構成。
    既定の analysis client (max=2000) はこの種のプロンプトで JSON 途中切断
    リスクがあるため拡張版を使う。
    """
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set — cannot run reclassification. "
            "GEMINI_API_KEY を .env または shell 環境変数に設定してください。"
        )
    return TieredGeminiClient(
        GEMINI_API_KEY,
        _get_tier_models_for_role("analysis"),
        generation_config={"temperature": 0.3, "max_output_tokens": 4096},
        max_attempts_per_tier=_get_max_attempts_for_role("analysis"),
    )


def _is_already_reclassified(ann: dict) -> bool:
    """この annotation は既に 4 分類で再分類済みか判定する (resume 判定用)。

    判定: `legacy_stream_classification_v1` が既に設定されており、かつ
    現在の `stream_classification_estimate.estimated_stream` が 4 分類セットの
    いずれかなら 'reclassified' とみなす。
    """
    legacy = ann.get("legacy_stream_classification_v1")
    if not legacy:
        return False
    sce = ann.get("stream_classification_estimate") or {}
    stream = sce.get("estimated_stream")
    return stream in _VALID_STREAMS_V2


def _write_partial(
    output_path: Path,
    payload_template: dict,
    annotations: list[dict],
) -> None:
    """incremental write 用に annotations を出力ファイルに書く。"""
    payload = dict(payload_template)
    payload["events"] = annotations
    payload["summary"] = summarize_after(annotations)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def reclassify_all(
    annotations: list[dict],
    output_path: Path | None = None,
    payload_template: dict | None = None,
    incremental_save_every: int = 1,
    skip_already_reclassified: bool = True,
) -> tuple[list[dict], list[dict]]:
    """全 annotation を 4 分類で再分類する。

    Args:
        annotations: 入力 (3 分類版または部分的に 4 分類化済み)
        output_path: incremental save 先 (None なら incremental save しない)
        payload_template: 出力 JSON のメタ部分 (events を除く)
        incremental_save_every: 何件ごとに incremental save するか
        skip_already_reclassified: True なら legacy_stream_classification_v1 が
            設定済み + estimated_stream が 4 分類のものはスキップ (resume 用)

    Returns:
        (updated_annotations, log_entries)
        updated_annotations: 4 分類版の annotation リスト (旧判定は
            legacy_stream_classification_v1 にバックアップ済み、kazuya_review はリセット)
        log_entries: 1 件ごとの実行ログ (event_id / before / after / success / error)
    """
    client = _build_extract_client()

    updated: list[dict] = []
    log_entries: list[dict] = []
    n = len(annotations)
    success = 0
    error = 0
    skipped = 0

    for i, ann in enumerate(annotations, start=1):
        event_id = ann.get("event_id", f"unknown_{i}")

        if skip_already_reclassified and _is_already_reclassified(ann):
            # already done in a prior run, keep as-is
            new_ann = dict(ann)
            sce = new_ann.get("stream_classification_estimate") or {}
            legacy = new_ann.get("legacy_stream_classification_v1") or {}
            log_entry = {
                "event_id": event_id,
                "title": ann.get("title"),
                "before_stream": legacy.get("estimated_stream"),
                "after_stream": sce.get("estimated_stream"),
                "stream_changed": (
                    legacy.get("estimated_stream") != sce.get("estimated_stream")
                ),
                "success": True,
                "error": None,
                "resumed_from_prior_run": True,
            }
            updated.append(new_ann)
            log_entries.append(log_entry)
            skipped += 1
            success += 1
            if i % 5 == 0 or i == n:
                logger.info(
                    f"Progress: {i}/{n} (success={success}, error={error}, skipped={skipped})"
                )
            continue

        new_ann = dict(ann)
        old_sce = ann.get("stream_classification_estimate") or {}
        old_stream = old_sce.get("estimated_stream")

        # Always backup the 3-class version into legacy_stream_classification_v1
        # so we can audit the diff later. If the field already exists from a prior
        # partial run, keep the original.
        if "legacy_stream_classification_v1" not in new_ann or not new_ann.get(
            "legacy_stream_classification_v1"
        ):
            new_ann["legacy_stream_classification_v1"] = old_sce

        log_entry = {
            "event_id": event_id,
            "title": ann.get("title"),
            "before_stream": old_stream,
            "after_stream": None,
            "stream_changed": False,
            "success": False,
            "error": None,
        }

        try:
            new_sce = reclassify_one(client, ann)
            new_ann["stream_classification_estimate"] = new_sce
            # Reset kazuya_review for 4-class re-review (per batch spec).
            new_ann["kazuya_review"] = {
                "particular_angle_revised": None,
                "stream_classification_revised": None,
                "review_note": None,
                "reviewed_at": None,
            }
            # Clear any stale extraction_error from prior batch.
            new_ann["extraction_error"] = None
            log_entry["after_stream"] = new_sce.get("estimated_stream")
            log_entry["stream_changed"] = log_entry["after_stream"] != old_stream
            log_entry["success"] = True
            success += 1
        except Exception as exc:
            new_ann["extraction_error"] = (
                f"reclassify (4-class) failed: {str(exc)[:400]}"
            )
            log_entry["error"] = str(exc)[:400]
            error += 1
            logger.error(f"[{event_id}] reclassification error: {str(exc)[:200]}")

        updated.append(new_ann)
        log_entries.append(log_entry)

        # Incremental save so that a kill mid-run preserves the work done so far.
        if (
            output_path is not None
            and payload_template is not None
            and i % max(1, incremental_save_every) == 0
        ):
            try:
                _write_partial(output_path, payload_template, updated + list(annotations[i:]))
            except Exception as save_exc:
                logger.warning(f"incremental save failed: {save_exc}")

        if i % 5 == 0 or i == n:
            logger.info(
                f"Progress: {i}/{n} (success={success}, error={error}, skipped={skipped})"
            )

    return updated, log_entries


def summarize_after(annotations: list[dict]) -> dict:
    """4 分類後の分布サマリ。"""
    stream_dist = {k: 0 for k in _VALID_STREAMS_V2}
    stream_dist["unknown"] = 0
    error_count = 0
    for ann in annotations:
        if ann.get("extraction_error"):
            error_count += 1
        sce = ann.get("stream_classification_estimate") or {}
        s = sce.get("estimated_stream") or "unknown"
        if s not in stream_dist:
            s = "unknown"
        stream_dist[s] += 1
    return {
        "total": len(annotations),
        "stream_classification_estimate_distribution": stream_dist,
        "reclassification_errors": error_count,
    }


def build_diff(log_entries: list[dict]) -> dict:
    """旧 3 分類 → 新 4 分類の差分集計。"""
    transitions: dict[str, int] = {}
    changed: list[dict] = []
    unchanged_count = 0
    for entry in log_entries:
        before = entry.get("before_stream") or "unknown"
        after = entry.get("after_stream") or "unknown"
        key = f"{before} -> {after}"
        transitions[key] = transitions.get(key, 0) + 1
        if entry.get("stream_changed"):
            changed.append({
                "event_id": entry["event_id"],
                "title": entry.get("title"),
                "before": before,
                "after": after,
            })
        else:
            unchanged_count += 1

    return {
        "version": "1.0",
        "batch": "F-particular-angle-redesign",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_events": len(log_entries),
        "summary": {
            "changed_count": len(changed),
            "unchanged_count": unchanged_count,
            "transitions": transitions,
        },
        "changed_events": changed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reclassify F-particular-angle annotations from 3-class to 4-class (F-particular-angle-redesign)"
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="入力 annotations.json のパス (3 分類版)",
    )
    parser.add_argument(
        "--backup",
        required=True,
        type=Path,
        help="3 分類版バックアップの出力先 (annotations_v1_3class.json)",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="出力 annotations.json のパス (4 分類版で上書き、入力と同じパスでも OK)",
    )
    parser.add_argument(
        "--diff-output",
        required=True,
        type=Path,
        help="reclassification_diff.json の出力先",
    )
    parser.add_argument(
        "--log-output",
        required=True,
        type=Path,
        help="reclassification_log.json の出力先",
    )
    parser.add_argument(
        "--llm-model",
        default="gemini-analysis-tier-extended",
        help="LLM モデルラベル (記録用)",
    )
    args = parser.parse_args()

    args.input = args.input.resolve()
    args.backup = args.backup.resolve()
    args.output = args.output.resolve()
    args.diff_output = args.diff_output.resolve()
    args.log_output = args.log_output.resolve()

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        return 2

    # Backup the 3-class file before any modification (idempotent: if backup exists,
    # we don't overwrite it — we treat the existing backup as the canonical 3-class).
    if args.backup.exists():
        logger.info(
            f"Backup already exists at {args.backup} — keeping the existing 3-class snapshot, "
            "not overwriting."
        )
    else:
        args.backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.input, args.backup)
        logger.info(f"Backed up 3-class annotations to {args.backup}")

    # Resume support: if the output path already contains a partial reclassification
    # (schema_version=2.0), prefer reading from there so we can resume. Otherwise read
    # from the input (3-class).
    resume_payload = None
    if args.output.exists() and args.output != args.backup:
        try:
            cand = json.loads(args.output.read_text(encoding="utf-8"))
            if cand.get("schema_version") == "2.0":
                resume_payload = cand
        except Exception:
            resume_payload = None

    if resume_payload is not None:
        payload = resume_payload
        annotations = payload.get("events", [])
        already_done = sum(1 for a in annotations if _is_already_reclassified(a))
        logger.info(
            f"Resuming from prior partial reclassification at {args.output} "
            f"({already_done}/{len(annotations)} already done)"
        )
    else:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        annotations = payload.get("events", [])
        logger.info(f"Loaded {len(annotations)} annotations from {args.input}")

    if not annotations:
        logger.error("No events found in input")
        return 2

    started_at = datetime.now(timezone.utc).isoformat()

    # Build the payload template to use for incremental writes.
    payload_template_for_save = {
        "version": "2.0",
        "schema_version": "2.0",
        "batch": "F-particular-angle-redesign",
        "reclassified_at": "(in progress)",
        "started_at": started_at,
        "previous_version": payload.get("previous_version", payload.get("version", "1.0")),
        "previous_extracted_at": payload.get(
            "previous_extracted_at", payload.get("extracted_at")
        ),
        "llm_model": args.llm_model,
        "input_file": payload.get("input_file"),
        "input_total_events": len(annotations),
        "previous_summary_v1": payload.get(
            "previous_summary_v1", payload.get("summary")
        ),
    }

    updated_annotations, log_entries = reclassify_all(
        annotations,
        output_path=args.output,
        payload_template=payload_template_for_save,
        incremental_save_every=1,
        skip_already_reclassified=True,
    )
    completed_at = datetime.now(timezone.utc).isoformat()

    summary_after = summarize_after(updated_annotations)

    output_payload = {
        "version": "2.0",
        "schema_version": "2.0",
        "batch": "F-particular-angle-redesign",
        "reclassified_at": completed_at,
        "started_at": started_at,
        "previous_version": payload.get("version", "1.0"),
        "previous_extracted_at": payload.get("extracted_at"),
        "llm_model": args.llm_model,
        "input_file": payload.get("input_file"),
        "input_total_events": len(annotations),
        "summary": summary_after,
        "previous_summary_v1": payload.get("summary"),
        "events": updated_annotations,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(
        f"Wrote {len(updated_annotations)} 4-class annotations to {args.output} "
        f"(distribution={summary_after['stream_classification_estimate_distribution']})"
    )

    diff = build_diff(log_entries)
    args.diff_output.parent.mkdir(parents=True, exist_ok=True)
    args.diff_output.write_text(
        json.dumps(diff, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(
        f"Wrote diff to {args.diff_output} "
        f"(changed={diff['summary']['changed_count']}, unchanged={diff['summary']['unchanged_count']})"
    )

    log_payload = {
        "version": "1.0",
        "batch": "F-particular-angle-redesign",
        "generated_at": completed_at,
        "started_at": started_at,
        "llm_model": args.llm_model,
        "total_events": len(log_entries),
        "entries": log_entries,
    }
    args.log_output.parent.mkdir(parents=True, exist_ok=True)
    args.log_output.write_text(
        json.dumps(log_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Wrote reclassification log to {args.log_output}")

    # 異常検知 (記録のみ、勝手に再実行しない)
    streams = summary_after["stream_classification_estimate_distribution"]
    if streams.get("stream_2_perspective_gap", 0) == 0 and len(annotations) >= 5:
        logger.warning(
            "⚠ stream_2_perspective_gap が 0 件: 4 分類化が機能していない可能性。"
            "本バッチでは記録のみ、prompt 再調整は行いません。"
        )
    if streams.get("stream_2_perspective_gap", 0) >= 15:
        logger.warning(
            "⚠ stream_2_perspective_gap が 15 件以上: 過剰判定の可能性。"
            "本バッチでは記録のみ、prompt 再調整は行いません。"
        )
    if diff["summary"]["changed_count"] == 0 and len(annotations) >= 5:
        logger.warning(
            "⚠ 全 25 件で 3 分類 → 4 分類への変更が無い: LLM が新分類を理解していない可能性。"
            "本バッチでは記録のみ、prompt 再調整は行いません。"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
