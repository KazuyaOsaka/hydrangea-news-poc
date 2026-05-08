"""F-particular-angle-redesign-extension: 忖度シグナル (sontaku_signals)
LLM 推定スクリプト。

入力 annotations.json (4 分類版、命名 1/2/3、25 件) の各 event に対して、
**系統判定とは独立な別軸メタデータ** として `sontaku_signals` フィールドを
LLM で推定付与する。

判定基準は docs/PARTICULAR_ANGLE_DEFINITION.md セクション 3.6 (sontaku_signals
独立軸メタデータ、F-particular-angle-redesign-extension で正典化) に従う。

Usage:
    python scripts/add_sontaku_signals.py \\
        --input docs/runs/F-particular-angle-design/annotations.json \\
        --output docs/runs/F-particular-angle-design/annotations.json \\
        --log-output docs/runs/F-particular-angle-redesign/extension_log.json \\
        --llm-model gemini-analysis-tier-extended

入力と出力が同じパスでも上書き可能 (一時ファイル経由で安全に保存、resume 対応)。

実装方針:
- LLM クライアントは `extract_particular_angle.py` /
  `reclassify_annotations.py` で確立した `_build_extract_client()` 方式
  (max_output_tokens=4096) を流用
- per-call timeout 90 秒 + incremental save 1 件ごと + resume (既に
  sontaku_signals が付与されている event はスキップ) を流用 (Gemini API
  高負荷耐性)
- LLM 失敗時は最大 3 回リトライ、それでも失敗した event は extraction_error
  に記録して継続 (記録のみ、勝手に再実行しない)
- 既存 fields (particular_angle / stream_classification_estimate /
  legacy_stream_classification_v1 / kazuya_review 等) は完全に保持
- kazuya_review に新規フィールド `sontaku_signals_revised` を追加 (None で
  初期化、カズヤレビュー対象)
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
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

logger = get_logger("add_sontaku_signals")

_VALID_LEVELS = {"high", "medium", "low", "none"}
_VALID_TYPES = {"diplomatic", "domestic", "media_industry", None}
_VALID_CONFIDENCES = {"high", "medium", "low"}

_PROMPT_TEMPLATE = """\
あなたは Hydrangea (海外ニュース解説メディア) の編集判断を支援する LLM です。
入力された海外ニュース 1 件について、既に抽出済みの「特定角度」と系統判定を
踏まえて、**忖度シグナル (sontaku_signals)** を推定してください。

# 忖度シグナルとは
日本主要メディアが当該事象 (または特定角度) について報じない / 触れない /
ソフトに扱う背景にある **構造的な忖度・報道規制・黙殺** の有無と性質を表す
独立軸メタデータです。系統判定 (stream_1/2/3/out_of_scope) とは独立して
評価します。

# 出力フィールド
- **level**: "high" | "medium" | "low" | "none"
  - high: 明確な忖度・報道規制・黙殺の構造あり
    (例: 米国忖度で日本政府を批判できない、ジャニーズ問題の長年放置等)
  - medium: 構造的バイアスはあるが明確な忖度とは言えない
    (例: 業界記者クラブの慣行的偏向、スポンサー配慮による触れ方のソフト化)
  - low: 部分的な構造的バイアスのみ (例: 一部メディアの編集方針差)
  - none: 忖度シグナルなし
    (例: 単にローカルすぎる事象、専門ニッチ、海外でも大きく扱われていない)
- **type**: "diplomatic" | "domestic" | "media_industry" | null
  - diplomatic: 外交的忖度
    (米国・中国・韓国・イスラエル・サウジ・ロシア・北朝鮮等)
  - domestic: 国内権力者忖度
    (政治家・上級官僚・財界要人・司法関係者・メディアオーナー一族・
    芸能スポーツ界権力者等の「上級国民」層)
  - media_industry: メディア業界忖度
    (記者クラブ制度・クロスオーナーシップ等)
  - null: type 該当なし (level=none の場合、または 3 type のいずれにも
    該当しない場合)
- **reasoning**: 忖度の構造的説明 (1-2 文、生の改行を含めない)
- **extraction_confidence**: "high" | "medium" | "low"
  - 推定の自信度。情報不足や判断困難な場合は medium / low

# 入力
event_id: {event_id}
title: {title}
summary: {summary}
sources: {sources}

# 既に抽出済みの「特定角度」(参考)
core_question: {core_question}
differentiation_from_mainstream: {differentiation_from_mainstream}
hydrangea_axis_alignment: {hydrangea_axis_alignment}

# 既に判定済みの系統 (参考、本タスクでは系統判定は変更しない)
estimated_stream: {estimated_stream}
stream_reasoning: {stream_reasoning}

# 出力 (必ず以下の JSON 形式で、それ以外の文字を一切含めない)
```json
{{
  "sontaku_signals": {{
    "level": "high / medium / low / none のいずれか",
    "type": "diplomatic / domestic / media_industry / null のいずれか (level=none の場合は null)",
    "reasoning": "忖度の構造的説明 (1-2 文、生の改行を含めない)",
    "extraction_confidence": "high / medium / low"
  }}
}}
```

# 注意事項
- 必ず JSON 形式のみで応答してください。Markdown コードブロック (```json) は付けても
  付けなくても構いません。スクリプト側で除去します。
- ★ 重要: 各文字列値 (reasoning 等) は **1 行に収め、生の改行を含めない**
  でください。複数文を入れる場合はスペースで連結してください。
- ★ 重要: type は level=none の場合は null を返してください
  (JSON では null、Python の None と等価)。それ以外の場合は 3 type のうち
  最も核心的な 1 つを選んでください (複数該当の場合は 1 つに絞る)。
- 系統判定 (estimated_stream) と忖度シグナルは独立軸です。系統 1 でも level=none
  になり得る (= 単にローカルすぎる事象だが、4 軸該当性で動画化対象には残る) し、
  逆に系統 3 でも level=high になり得る (= 評価フレーム対立 + 強い忖度)。
- extraction_confidence は推定の自信度を厳密に判定してください。情報不足や
  判断困難な場合は medium / low を返してください。
"""


def build_prompt(annotation: dict) -> str:
    """1 件の annotation から sontaku_signals 推定用 LLM プロンプトを組み立てる。"""
    pa = annotation.get("particular_angle") or {}
    sce = annotation.get("stream_classification_estimate") or {}
    sources = annotation.get("sources")
    if isinstance(sources, list) and sources:
        sources_str = ", ".join(s if isinstance(s, str) else str(s) for s in sources)
    elif isinstance(sources, str) and sources:
        sources_str = sources
    else:
        sources_str = annotation.get("source_origin") or ""
    return _PROMPT_TEMPLATE.format(
        event_id=annotation.get("event_id", "(unknown)"),
        title=annotation.get("title", "(no title)"),
        summary=annotation.get("summary_excerpt") or annotation.get("summary") or "(no summary)",
        sources=sources_str or "(no sources)",
        core_question=pa.get("core_question") or "(none)",
        differentiation_from_mainstream=pa.get("differentiation_from_mainstream") or "(none)",
        hydrangea_axis_alignment=pa.get("hydrangea_axis_alignment") or "(none)",
        estimated_stream=sce.get("estimated_stream") or "(unknown)",
        stream_reasoning=sce.get("reasoning") or "(none)",
    )


def _escape_unescaped_newlines_in_strings(s: str) -> str:
    """JSON 文字列値の中に生の改行が混じっている場合に \\n / \\r / \\t に
    エスケープする最小修復 (reclassify_annotations.py の同名関数を流用)。
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
    """client.generate(prompt) を timeout 付きで呼び出す。"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(client.generate, prompt)
        try:
            return future.result(timeout=timeout_sec)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise TimeoutError(
                f"client.generate() exceeded {timeout_sec}s — likely Gemini API hang"
            ) from exc


def _validate_sontaku_signals(signals: dict) -> dict:
    """sontaku_signals 構造を検証して正規化する。"""
    level = signals.get("level")
    if level not in _VALID_LEVELS:
        raise ValueError(f"invalid level: {level}")
    typ = signals.get("type")
    # JSON null comes through as None; LLM may also return string "null"
    if isinstance(typ, str) and typ.strip().lower() in {"null", "none", ""}:
        typ = None
    if typ not in _VALID_TYPES:
        raise ValueError(f"invalid type: {typ}")
    if level == "none" and typ is not None:
        # Coerce: when level=none, type must be null per spec.
        typ = None
    reasoning = signals.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        raise ValueError("reasoning missing or empty")
    confidence = signals.get("extraction_confidence")
    if confidence not in _VALID_CONFIDENCES:
        raise ValueError(f"invalid extraction_confidence: {confidence}")
    return {
        "level": level,
        "type": typ,
        "reasoning": reasoning.strip(),
        "extraction_confidence": confidence,
    }


def estimate_one(client, annotation: dict, max_retries: int = 3) -> dict:
    """1 件分の sontaku_signals を LLM で推定する。"""
    prompt = build_prompt(annotation)
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            response_text = _generate_with_timeout(client, prompt)
            parsed = parse_llm_response(response_text)
            signals = parsed.get("sontaku_signals") or {}
            return _validate_sontaku_signals(signals)
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

    extract_particular_angle.py / reclassify_annotations.py の
    `_build_extract_client()` と同じ構成。
    """
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set — cannot run sontaku_signals estimation. "
            "GEMINI_API_KEY を .env または shell 環境変数に設定してください。"
        )
    return TieredGeminiClient(
        GEMINI_API_KEY,
        _get_tier_models_for_role("analysis"),
        generation_config={"temperature": 0.3, "max_output_tokens": 4096},
        max_attempts_per_tier=_get_max_attempts_for_role("analysis"),
    )


def _is_already_estimated(ann: dict) -> bool:
    """この annotation は既に sontaku_signals 推定済みか判定する (resume 用)。"""
    signals = ann.get("sontaku_signals")
    if not isinstance(signals, dict):
        return False
    return signals.get("level") in _VALID_LEVELS and "extraction_confidence" in signals


def _write_partial(output_path: Path, payload: dict) -> None:
    """incremental save 用に payload を出力ファイルに書く (一時ファイル経由)。"""
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(output_path)


def estimate_all(
    annotations: list[dict],
    output_path: Path | None = None,
    payload_for_save: dict | None = None,
    incremental_save_every: int = 1,
    skip_already_estimated: bool = True,
) -> tuple[list[dict], list[dict]]:
    """全 annotation に sontaku_signals を付与する (resume + incremental save)。"""
    client = _build_extract_client()

    updated: list[dict] = []
    log_entries: list[dict] = []
    n = len(annotations)
    success = 0
    error = 0
    skipped = 0

    for i, ann in enumerate(annotations, start=1):
        event_id = ann.get("event_id", f"unknown_{i}")
        new_ann = dict(ann)

        if skip_already_estimated and _is_already_estimated(ann):
            log_entries.append({
                "event_id": event_id,
                "title": ann.get("title"),
                "level": ann.get("sontaku_signals", {}).get("level"),
                "type": ann.get("sontaku_signals", {}).get("type"),
                "extraction_confidence": ann.get("sontaku_signals", {}).get(
                    "extraction_confidence"
                ),
                "success": True,
                "error": None,
                "resumed_from_prior_run": True,
            })
            updated.append(new_ann)
            skipped += 1
            success += 1
            if i % 5 == 0 or i == n:
                logger.info(
                    f"Progress: {i}/{n} (success={success}, error={error}, skipped={skipped})"
                )
            continue

        log_entry = {
            "event_id": event_id,
            "title": ann.get("title"),
            "level": None,
            "type": None,
            "extraction_confidence": None,
            "success": False,
            "error": None,
        }

        try:
            signals = estimate_one(client, ann)
            new_ann["sontaku_signals"] = signals
            # Add sontaku_signals_revised slot for kazuya review
            review = dict(new_ann.get("kazuya_review") or {})
            if "sontaku_signals_revised" not in review:
                review["sontaku_signals_revised"] = None
            new_ann["kazuya_review"] = review
            log_entry["level"] = signals["level"]
            log_entry["type"] = signals["type"]
            log_entry["extraction_confidence"] = signals["extraction_confidence"]
            log_entry["success"] = True
            success += 1
        except Exception as exc:
            existing_err = new_ann.get("extraction_error") or ""
            sep = " | " if existing_err else ""
            new_ann["extraction_error"] = (
                f"{existing_err}{sep}sontaku_signals estimation failed: {str(exc)[:300]}"
            )
            log_entry["error"] = str(exc)[:400]
            error += 1
            logger.error(f"[{event_id}] sontaku_signals error: {str(exc)[:200]}")

        updated.append(new_ann)
        log_entries.append(log_entry)

        # Incremental save preserving the rest of the events untouched.
        if (
            output_path is not None
            and payload_for_save is not None
            and i % max(1, incremental_save_every) == 0
        ):
            try:
                payload_snapshot = dict(payload_for_save)
                payload_snapshot["events"] = updated + list(annotations[i:])
                _write_partial(output_path, payload_snapshot)
            except Exception as save_exc:
                logger.warning(f"incremental save failed: {save_exc}")

        if i % 5 == 0 or i == n:
            logger.info(
                f"Progress: {i}/{n} (success={success}, error={error}, skipped={skipped})"
            )

    return updated, log_entries


def summarize_signals(annotations: list[dict]) -> dict:
    """level / type / extraction_confidence の分布サマリ。"""
    level_dist = {k: 0 for k in _VALID_LEVELS}
    level_dist["unknown"] = 0
    type_dist: dict[str, int] = {"diplomatic": 0, "domestic": 0, "media_industry": 0, "null": 0, "unknown": 0}
    conf_dist = {k: 0 for k in _VALID_CONFIDENCES}
    conf_dist["unknown"] = 0
    for ann in annotations:
        signals = ann.get("sontaku_signals") or {}
        level = signals.get("level") or "unknown"
        if level not in level_dist:
            level = "unknown"
        level_dist[level] += 1
        typ = signals.get("type")
        if typ is None:
            type_dist["null"] += 1
        elif isinstance(typ, str) and typ in {"diplomatic", "domestic", "media_industry"}:
            type_dist[typ] += 1
        else:
            type_dist["unknown"] += 1
        conf = signals.get("extraction_confidence") or "unknown"
        if conf not in conf_dist:
            conf = "unknown"
        conf_dist[conf] += 1
    return {
        "total": len(annotations),
        "level_distribution": level_dist,
        "type_distribution": type_dist,
        "extraction_confidence_distribution": conf_dist,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Estimate sontaku_signals for annotations.json events "
            "(F-particular-angle-redesign-extension)"
        )
    )
    parser.add_argument("--input", required=True, type=Path, help="入力 annotations.json のパス")
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="出力 annotations.json のパス (入力と同じパスでも OK、resume 対応)",
    )
    parser.add_argument(
        "--log-output",
        required=True,
        type=Path,
        help="拡張作業ログの出力先 (extension_log.json)",
    )
    parser.add_argument(
        "--llm-model",
        default="gemini-analysis-tier-extended",
        help="LLM モデルラベル (記録用)",
    )
    args = parser.parse_args()

    args.input = args.input.resolve()
    args.output = args.output.resolve()
    args.log_output = args.log_output.resolve()

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        return 2

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    annotations = payload.get("events") or []
    if not annotations:
        logger.error("No events found in input")
        return 2

    started_at = datetime.now(timezone.utc).isoformat()
    payload_for_save = dict(payload)
    payload_for_save["sontaku_signals_estimation_started_at"] = started_at
    payload_for_save["sontaku_signals_estimation_status"] = "in_progress"

    logger.info(
        f"Loaded {len(annotations)} annotations from {args.input} "
        f"(schema_version={payload.get('schema_version')})"
    )

    updated_annotations, log_entries = estimate_all(
        annotations,
        output_path=args.output,
        payload_for_save=payload_for_save,
        incremental_save_every=1,
        skip_already_estimated=True,
    )
    completed_at = datetime.now(timezone.utc).isoformat()

    summary = summarize_signals(updated_annotations)

    output_payload = dict(payload)
    output_payload["events"] = updated_annotations
    output_payload["sontaku_signals_estimation_started_at"] = started_at
    output_payload["sontaku_signals_estimation_completed_at"] = completed_at
    output_payload["sontaku_signals_estimation_status"] = "completed"
    output_payload["sontaku_signals_estimation_llm_model"] = args.llm_model
    output_payload["sontaku_signals_summary"] = summary

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(
        f"Wrote {len(updated_annotations)} annotations with sontaku_signals to {args.output} "
        f"(level_dist={summary['level_distribution']}, type_dist={summary['type_distribution']})"
    )

    log_payload = {
        "version": "1.0",
        "batch": "F-particular-angle-redesign-extension",
        "task": "Task D: add_sontaku_signals",
        "generated_at": completed_at,
        "started_at": started_at,
        "llm_model": args.llm_model,
        "total_events": len(log_entries),
        "summary": summary,
        "entries": log_entries,
    }
    args.log_output.parent.mkdir(parents=True, exist_ok=True)
    args.log_output.write_text(
        json.dumps(log_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Wrote sontaku_signals log to {args.log_output}")

    # 異常検知 (記録のみ、勝手に再実行しない、バッチ仕様 D-5 に従う)
    levels = summary["level_distribution"]
    confs = summary["extraction_confidence_distribution"]
    n = len(updated_annotations)
    distinct_levels = sum(1 for v in levels.values() if v > 0)
    if distinct_levels <= 1 and n >= 5:
        logger.warning(
            "⚠ 全件が同じ level に分類: プロンプト問題の可能性。"
            "本バッチでは記録のみ、prompt 再調整は行いません。"
        )
    if confs.get("low", 0) >= 5:
        logger.warning(
            "⚠ 5 件以上が extraction_confidence=low: プロンプト問題の可能性。"
            "本バッチでは記録のみ、prompt 再調整は行いません。"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
