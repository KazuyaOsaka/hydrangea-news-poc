"""F-jp-coverage-tune (2026-05-09): verify_two_stage() の精度測定スクリプト。

真値:
    - docs/runs/F-particular-angle-design/annotations.json (25 件)
        - stream_classification_estimate.broad_event_jp_coverage (reported / unreported)
        - stream_classification_estimate.particular_angle_jp_coverage (reported / unreported)
        - stream_classification_estimate.estimated_stream (stream_1/2/3/out_of_scope)
        - particular_angle.core_question (verify_two_stage の入力)
    - docs/runs/F-verify-jp-coverage/golden_set.json v1.3 (19 件)
        - expected_tier (Tier 一致率の真値)

重複除外 (DISCUSSION_NOTES「2026-05-08: 試運転と golden_set の重複サンプリング問題」):
    - cls-33b4f4960bf9_7K (= blind_005 の重複) を除外し blind_005 を採用
    - cls-204a683f73ee_7K (= blind_004 の重複) を除外し blind_004 を採用
    - 独立 23 件で精度評価

評価指標 (verdict 判定対象 4 つ + 1 つ informational):
    1. Recall covered (broad-level): truth.broad_event_jp_coverage="reported" のうち
       予測 broad_jp_coverage=True の率 (目標 90%)
    2. Precision blind (broad-level): 予測 broad_jp_coverage=False のうち
       truth.broad_event_jp_coverage="unreported" の率 (目標 80%)
    3. F1 (covered): Precision/Recall covered の調和平均 (目標 0.85)
    4. Tier 一致率: golden_set.json の expected_tier と broad_matched_tier の
       一致率 (報道済み TP のみ対象、目標 70%)
    5. 系統判別精度 (informational): predicted_stream vs truth.estimated_stream
       の一致率 (verdict には影響しない参考指標)

verdict:
    - 4 指標全達成 → pass
    - いずれか未達 → fail

出力:
    - measurement_result.json (機械読み詳細 + 4 指標 + verdict + 系統判別精度)
    - logs/<event_id>.log (per-event の検索クエリ + 結果サマリ)
    - 中間結果は <output>.tmp に incremental save、最終的に rename

Usage:
    python scripts/measure_two_stage_accuracy.py \\
        --annotations docs/runs/F-particular-angle-design/annotations.json \\
        --golden-set docs/runs/F-verify-jp-coverage/golden_set.json \\
        --output docs/runs/F-jp-coverage-tune/measurement_result.json \\
        --log-dir docs/runs/F-jp-coverage-tune/logs/

オプション:
    --resume: 既存の中間結果ファイルを継続 (未処理 event_id のみ実行)
    --max-events N: 先頭 N 件のみ実行 (デバッグ用)
    --timeout 90: per-call timeout 秒数
    --date-restrict 60: dateRestrict (過去 N 日)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.shared.config import GEMINI_API_KEY  # noqa: E402
from src.shared.logger import get_logger  # noqa: E402
from src.triage.jp_coverage_verifier import (  # noqa: E402
    JpCoverageVerifier,
    TwoStageVerifyResult,
)

logger = get_logger("measure_two_stage_accuracy")

# 重複サンプリング除外 ID (DISCUSSION_NOTES 2026-05-08 参照)
EXCLUDED_DUPLICATE_EVENT_IDS = {
    "cls-33b4f4960bf9_7K",  # = blind_005
    "cls-204a683f73ee_7K",  # = blind_004
}

# 合格基準 (verdict 判定対象 4 つ)
THRESHOLDS = {
    "recall_covered": 0.90,
    "precision_blind": 0.80,
    "f1_covered": 0.85,
    "tier_accuracy": 0.70,
}

# F-13.B キャッシュテーブルスキーマ (verify_jp_coverage_measure.py と同一)
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


def get_gemini_client() -> Any:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")
    from google import genai

    return genai.Client(api_key=GEMINI_API_KEY)


def load_truth_data(
    annotations_path: Path,
    golden_set_path: Path,
) -> list[dict]:
    """真値を構築する。

    annotations.json (25 件) を主軸とし、golden_set.json (19 件) の
    expected_tier を id-mapping で補完する。重複 2 件は除外し独立 23 件を返す。
    """
    annotations = json.loads(annotations_path.read_text(encoding="utf-8"))
    golden_set = json.loads(golden_set_path.read_text(encoding="utf-8"))

    # golden_set: id (e.g. "blind_001") をキーに expected_tier を取得
    gs_by_id = {e["id"]: e for e in golden_set["entries"]}

    truth_entries: list[dict] = []
    for event in annotations["events"]:
        event_id = event["event_id"]
        if event_id in EXCLUDED_DUPLICATE_EVENT_IDS:
            logger.info(
                f"Excluding duplicate event: {event_id} "
                f"(see DISCUSSION_NOTES 2026-05-08)"
            )
            continue

        sce = event.get("stream_classification_estimate") or {}
        pa = event.get("particular_angle") or {}

        gs_entry = gs_by_id.get(event_id)
        expected_tier = gs_entry.get("expected_tier") if gs_entry else None
        gs_expected_has_jp = (
            gs_entry.get("expected_has_jp_coverage") if gs_entry else None
        )

        truth_entries.append({
            "event_id": event_id,
            "title": event.get("title", ""),
            "summary_excerpt": event.get("summary_excerpt", ""),
            "particular_angle": pa,
            "expected_stream": sce.get("estimated_stream"),
            "expected_broad_jp_coverage": sce.get("broad_event_jp_coverage"),
            "expected_angle_jp_coverage": sce.get("particular_angle_jp_coverage"),
            "expected_tier": expected_tier,
            "expected_has_jp_coverage_golden": gs_expected_has_jp,
            "in_golden_set": gs_entry is not None,
        })

    return truth_entries


def write_event_log(
    log_dir: Path,
    event_id: str,
    truth: dict,
    result: TwoStageVerifyResult,
    elapsed: float,
) -> None:
    """per-event のログファイルを書き出す (デバッグ用)。"""
    log_path = log_dir / f"{event_id}.log"
    lines = [
        f"# {event_id}",
        f"timestamp: {datetime.now().isoformat()}",
        f"elapsed_seconds: {elapsed:.2f}",
        "",
        "## Truth",
        f"  expected_stream: {truth['expected_stream']}",
        f"  expected_broad_jp_coverage: {truth['expected_broad_jp_coverage']}",
        f"  expected_angle_jp_coverage: {truth['expected_angle_jp_coverage']}",
        f"  expected_tier: {truth['expected_tier']}",
        f"  in_golden_set: {truth['in_golden_set']}",
        "",
        "## Predicted",
        f"  stream: {result.stream}",
        f"  broad_jp_coverage: {result.broad_jp_coverage}",
        f"  angle_jp_coverage: {result.angle_jp_coverage}",
        f"  broad_matched_tier: {result.broad_matched_tier}",
        f"  angle_matched_tier: {result.angle_matched_tier}",
        f"  error_message: {result.error_message}",
        f"  angle_query_fallback_reason: {result.angle_query_fallback_reason}",
        "",
        "## Queries",
        f"  broad_query: {result.broad_query}",
        f"  angle_query: {result.angle_query}",
        "",
        "## Results",
        f"  broad: {json.dumps(result.broad_results, ensure_ascii=False) if result.broad_results else 'None'}",
        f"  angle: {json.dumps(result.angle_results, ensure_ascii=False) if result.angle_results else 'None'}",
        "",
        "## Hits",
        f"  jp_media_hits_broad: {result.jp_media_hits_broad}",
        f"  jp_media_hits_angle: {result.jp_media_hits_angle}",
        f"  excluded_count_broad: {result.excluded_count_broad}",
        f"  excluded_count_angle: {result.excluded_count_angle}",
    ]
    log_path.write_text("\n".join(lines), encoding="utf-8")


def result_to_dict(result: TwoStageVerifyResult) -> dict:
    """TwoStageVerifyResult を JSON 化可能な dict に変換。"""
    return {
        "stream": result.stream,
        "broad_query": result.broad_query,
        "broad_results": result.broad_results,
        "angle_query": result.angle_query,
        "angle_results": result.angle_results,
        "broad_jp_coverage": result.broad_jp_coverage,
        "angle_jp_coverage": result.angle_jp_coverage,
        "jp_media_hits_broad": result.jp_media_hits_broad,
        "jp_media_hits_angle": result.jp_media_hits_angle,
        "broad_matched_tier": result.broad_matched_tier,
        "angle_matched_tier": result.angle_matched_tier,
        "excluded_count_broad": result.excluded_count_broad,
        "excluded_count_angle": result.excluded_count_angle,
        "angle_query_fallback_reason": result.angle_query_fallback_reason,
        "error_message": result.error_message,
        "elapsed_seconds": result.elapsed_seconds,
        # F-jp-coverage-llm-judgement-extraction Task E-fix (2026-05-16):
        # scripts/ 例外条件適用。Task E では LLM judgement が serialize されず
        # measurement_run.log からの事後復元を強いられた (構造的事後検証不能)。
        # optional フィールドとして末尾追加 (既存呼び出し側影響なし)。
        "broad_llm_judgement": result.broad_llm_judgement,
        "broad_llm_judgement_text": result.broad_llm_judgement_text,
        "angle_llm_judgement": result.angle_llm_judgement,
        "angle_llm_judgement_text": result.angle_llm_judgement_text,
    }


def run_measurement(
    verifier: JpCoverageVerifier,
    truth_entries: list[dict],
    log_dir: Path,
    output_tmp_path: Path,
    timeout_seconds: float,
    date_restrict_days: int,
    completed_event_ids: set[str],
    existing_results: list[dict],
    analysis_llm_client: Any = None,
) -> list[dict]:
    """各 truth entry に対して verify_two_stage を実行し結果を収集 (incremental save)。"""
    results: list[dict] = list(existing_results)
    total = len(truth_entries)
    log_dir.mkdir(parents=True, exist_ok=True)

    for i, truth in enumerate(truth_entries, 1):
        event_id = truth["event_id"]
        if event_id in completed_event_ids:
            logger.info(f"[{i}/{total}] SKIP {event_id} (already completed)")
            continue

        logger.info(
            f"[{i}/{total}] Verifying {event_id}: {truth['title'][:60]!r}"
        )
        start = time.time()
        try:
            candidate = {
                "title": truth["title"],
                "summary": truth["summary_excerpt"],
            }
            result = verifier.verify_two_stage(
                candidate=candidate,
                particular_angle=truth["particular_angle"],
                timeout_seconds=timeout_seconds,
                date_restrict_days=date_restrict_days,
                analysis_llm_client=analysis_llm_client,
            )
            elapsed = time.time() - start
            write_event_log(log_dir, event_id, truth, result, elapsed)
            entry = {
                "event_id": event_id,
                "title": truth["title"],
                "truth": {
                    "expected_stream": truth["expected_stream"],
                    "expected_broad_jp_coverage": truth["expected_broad_jp_coverage"],
                    "expected_angle_jp_coverage": truth["expected_angle_jp_coverage"],
                    "expected_tier": truth["expected_tier"],
                    "in_golden_set": truth["in_golden_set"],
                },
                "predicted": result_to_dict(result),
                "elapsed_seconds": round(elapsed, 3),
            }
            results.append(entry)
            logger.info(
                f"  -> stream={result.stream} "
                f"broad_jp={result.broad_jp_coverage} "
                f"angle_jp={result.angle_jp_coverage} "
                f"broad_tier={result.broad_matched_tier} "
                f"elapsed={elapsed:.2f}s"
            )
        except Exception as exc:
            elapsed = time.time() - start
            error_msg = f"{type(exc).__name__}: {exc}"
            logger.error(f"  Exception: {error_msg}")
            entry = {
                "event_id": event_id,
                "title": truth["title"],
                "truth": {
                    "expected_stream": truth["expected_stream"],
                    "expected_broad_jp_coverage": truth["expected_broad_jp_coverage"],
                    "expected_angle_jp_coverage": truth["expected_angle_jp_coverage"],
                    "expected_tier": truth["expected_tier"],
                    "in_golden_set": truth["in_golden_set"],
                },
                "predicted": {
                    "stream": "unknown",
                    "error_message": f"script_level_exception: {error_msg}",
                },
                "elapsed_seconds": round(elapsed, 3),
            }
            results.append(entry)

        # incremental save
        save_intermediate(output_tmp_path, results)

    return results


def save_intermediate(tmp_path: Path, results: list[dict]) -> None:
    """中間結果を .tmp ファイルに保存 (resume 対応)。"""
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "version": "intermediate-1.0",
        "generated_at": datetime.now().isoformat(),
        "completed_event_ids": [r["event_id"] for r in results],
        "results": results,
    }
    tmp_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_intermediate(tmp_path: Path) -> tuple[set[str], list[dict]]:
    """中間結果を読み込み (--resume 用)。存在しなければ空。"""
    if not tmp_path.exists():
        return set(), []
    state = json.loads(tmp_path.read_text(encoding="utf-8"))
    completed = set(state.get("completed_event_ids", []))
    results = state.get("results", [])
    logger.info(
        f"Resuming from {tmp_path}: {len(completed)} events already completed"
    )
    return completed, results


def compute_metrics(results: list[dict]) -> dict:
    """4 指標 + 系統判別精度 + 補助統計を計算する。

    定義:
        truth_covered: truth.expected_broad_jp_coverage == "reported"
        truth_blind: truth.expected_broad_jp_coverage == "unreported"
        pred_covered: predicted.broad_jp_coverage == True
        pred_blind: predicted.broad_jp_coverage == False
        unknown: predicted.stream == "unknown" (graceful fallback、計算から除外)
    """
    eligible = [r for r in results if r["predicted"].get("stream") != "unknown"]
    unknowns = [r for r in results if r["predicted"].get("stream") == "unknown"]

    def _tc(r: dict) -> bool:
        return r["truth"]["expected_broad_jp_coverage"] == "reported"

    def _tb(r: dict) -> bool:
        return r["truth"]["expected_broad_jp_coverage"] == "unreported"

    def _pc(r: dict) -> bool:
        return r["predicted"].get("broad_jp_coverage") is True

    def _pb(r: dict) -> bool:
        return r["predicted"].get("broad_jp_coverage") is False

    tp = sum(1 for r in eligible if _tc(r) and _pc(r))   # covered → covered
    fn = sum(1 for r in eligible if _tc(r) and _pb(r))   # covered → blind
    fp = sum(1 for r in eligible if _tb(r) and _pc(r))   # blind   → covered
    tn = sum(1 for r in eligible if _tb(r) and _pb(r))   # blind   → blind

    def _safe_div(n: float, d: float) -> float:
        return n / d if d > 0 else 0.0

    precision_covered = _safe_div(tp, tp + fp)
    recall_covered = _safe_div(tp, tp + fn)
    f1_covered = _safe_div(
        2 * precision_covered * recall_covered,
        precision_covered + recall_covered,
    )
    precision_blind = _safe_div(tn, tn + fn)
    recall_blind = _safe_div(tn, tn + fp)

    # Tier 一致率: TP のうち expected_tier が non-null AND broad_matched_tier と一致
    tier_eligible = [
        r
        for r in eligible
        if _tc(r) and _pc(r) and r["truth"]["expected_tier"]
    ]
    tier_matched = sum(
        1
        for r in tier_eligible
        if r["truth"]["expected_tier"] == r["predicted"].get("broad_matched_tier")
    )
    tier_accuracy = _safe_div(tier_matched, len(tier_eligible))

    # 系統判別精度 (informational): predicted.stream vs truth.expected_stream
    # out_of_scope は集計対象外
    stream_eligible = [
        r
        for r in eligible
        if r["truth"]["expected_stream"] in {
            "stream_1_silence_gap",
            "stream_2_perspective_gap",
            "stream_3_framing_inversion",
        }
    ]
    # 真値 stream_3_framing_inversion ⇄ 予測 stream_3_candidate を一致扱い (命名差吸収)
    def _stream_match(truth_s: str, pred_s: str) -> bool:
        if truth_s == "stream_3_framing_inversion" and pred_s == "stream_3_candidate":
            return True
        return truth_s == pred_s

    stream_matched = sum(
        1
        for r in stream_eligible
        if _stream_match(
            r["truth"]["expected_stream"], r["predicted"].get("stream") or ""
        )
    )
    stream_accuracy = _safe_div(stream_matched, len(stream_eligible))

    # per-stream 内訳 (informational)
    per_stream_breakdown: dict[str, dict] = {}
    for s in {
        "stream_1_silence_gap",
        "stream_2_perspective_gap",
        "stream_3_framing_inversion",
    }:
        bucket = [r for r in stream_eligible if r["truth"]["expected_stream"] == s]
        if not bucket:
            per_stream_breakdown[s] = {"truth_count": 0}
            continue
        match_n = sum(
            1
            for r in bucket
            if _stream_match(s, r["predicted"].get("stream") or "")
        )
        per_stream_breakdown[s] = {
            "truth_count": len(bucket),
            "matched": match_n,
            "accuracy": round(_safe_div(match_n, len(bucket)), 4),
            "predicted_distribution": _count_predictions(bucket),
        }

    return {
        "total_events": len(results),
        "eligible_events": len(eligible),
        "unknown_events": len(unknowns),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision_covered": round(precision_covered, 4),
        "recall_covered": round(recall_covered, 4),
        "f1_covered": round(f1_covered, 4),
        "precision_blind": round(precision_blind, 4),
        "recall_blind": round(recall_blind, 4),
        "tier_accuracy": round(tier_accuracy, 4),
        "tier_eligible": len(tier_eligible),
        "tier_matched": tier_matched,
        "stream_accuracy": round(stream_accuracy, 4),
        "stream_eligible": len(stream_eligible),
        "stream_matched": stream_matched,
        "per_stream_breakdown": per_stream_breakdown,
    }


def _count_predictions(bucket: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in bucket:
        s = r["predicted"].get("stream") or "unknown"
        counts[s] = counts.get(s, 0) + 1
    return counts


def determine_verdict(metrics: dict) -> dict:
    """4 指標全達成で pass、それ以外は fail。"""
    criteria = {
        "recall_covered": (metrics["recall_covered"], THRESHOLDS["recall_covered"]),
        "precision_blind": (metrics["precision_blind"], THRESHOLDS["precision_blind"]),
        "f1_covered": (metrics["f1_covered"], THRESHOLDS["f1_covered"]),
        "tier_accuracy": (metrics["tier_accuracy"], THRESHOLDS["tier_accuracy"]),
    }
    passed = {k: v[0] >= v[1] for k, v in criteria.items()}
    verdict = "pass" if all(passed.values()) else "fail"

    return {
        "verdict": verdict,
        "criteria": {
            k: {
                "actual": v[0],
                "threshold": v[1],
                "passed": passed[k],
            }
            for k, v in criteria.items()
        },
        "all_passed": all(passed.values()),
    }


def save_final_result(
    output_path: Path,
    output_tmp_path: Path,
    results: list[dict],
    metrics: dict,
    verdict: dict,
    config: dict,
) -> None:
    """最終結果を保存 (.tmp → 本ファイルに rename)。"""
    output = {
        "version": "1.0",
        "batch": "F-jp-coverage-tune",
        "generated_at": datetime.now().isoformat(),
        "config": config,
        "thresholds": THRESHOLDS,
        "metrics": metrics,
        "verdict": verdict,
        "entries": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if output_tmp_path.exists():
        output_tmp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--annotations",
        type=Path,
        default=_PROJECT_ROOT / "docs/runs/F-particular-angle-design/annotations.json",
    )
    parser.add_argument(
        "--golden-set",
        type=Path,
        default=_PROJECT_ROOT / "docs/runs/F-verify-jp-coverage/golden_set.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_PROJECT_ROOT / "docs/runs/F-jp-coverage-tune/measurement_result.json",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=_PROJECT_ROOT / "docs/runs/F-jp-coverage-tune/logs/",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("/tmp/jp_coverage_two_stage.db"),
    )
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--date-restrict", type=int, default=60)
    parser.add_argument("--max-events", type=int, default=None,
                        help="先頭 N 件のみ実行 (デバッグ用)")
    parser.add_argument("--resume", action="store_true",
                        help="既存中間結果から再開")
    args = parser.parse_args()

    output_tmp_path = args.output.with_suffix(args.output.suffix + ".tmp")

    # 真値ロード
    truth_entries = load_truth_data(args.annotations, args.golden_set)
    logger.info(f"Loaded {len(truth_entries)} independent truth entries (excluding 2 duplicates)")
    if args.max_events:
        truth_entries = truth_entries[: args.max_events]
        logger.info(f"--max-events={args.max_events}: limited to {len(truth_entries)} entries")

    # resume
    completed_event_ids: set[str] = set()
    existing_results: list[dict] = []
    if args.resume:
        completed_event_ids, existing_results = load_intermediate(output_tmp_path)

    # クライアント
    setup_temp_db(args.db_path)
    gemini_client = get_gemini_client()
    verifier = JpCoverageVerifier(gemini_client=gemini_client, db_path=args.db_path)

    from src.llm.factory import get_analysis_llm_client
    analysis_llm_client = get_analysis_llm_client()
    if analysis_llm_client is None:
        logger.warning("get_analysis_llm_client() returned None — angle queries will use fallback")

    # 計測実行
    start_overall = time.time()
    results = run_measurement(
        verifier=verifier,
        truth_entries=truth_entries,
        log_dir=args.log_dir,
        output_tmp_path=output_tmp_path,
        timeout_seconds=args.timeout,
        date_restrict_days=args.date_restrict,
        completed_event_ids=completed_event_ids,
        existing_results=existing_results,
        analysis_llm_client=analysis_llm_client,
    )
    elapsed_overall = time.time() - start_overall
    logger.info(f"Total elapsed: {elapsed_overall:.1f}s for {len(results)} events")

    # 集計
    metrics = compute_metrics(results)
    verdict = determine_verdict(metrics)

    config = {
        "annotations_path": str(args.annotations.relative_to(_PROJECT_ROOT)) if args.annotations.is_relative_to(_PROJECT_ROOT) else str(args.annotations),
        "golden_set_path": str(args.golden_set.relative_to(_PROJECT_ROOT)) if args.golden_set.is_relative_to(_PROJECT_ROOT) else str(args.golden_set),
        "timeout_seconds": args.timeout,
        "date_restrict_days": args.date_restrict,
        "excluded_duplicate_event_ids": sorted(EXCLUDED_DUPLICATE_EVENT_IDS),
        "elapsed_seconds_total": round(elapsed_overall, 1),
    }

    save_final_result(args.output, output_tmp_path, results, metrics, verdict, config)
    logger.info(f"Saved final result to {args.output}")

    # コンソール出力
    print()
    print(f"=== F-jp-coverage-tune verify_two_stage 精度測定結果 ===")
    print(f"verdict: {verdict['verdict']}")
    print(f"events: total={metrics['total_events']} eligible={metrics['eligible_events']} unknown={metrics['unknown_events']}")
    print(f"confusion: TP={metrics['tp']} FP={metrics['fp']} TN={metrics['tn']} FN={metrics['fn']}")
    print()
    print(f"  Recall covered  : {metrics['recall_covered']:.4f}  (threshold {THRESHOLDS['recall_covered']:.2f})  {'✓' if verdict['criteria']['recall_covered']['passed'] else '✗'}")
    print(f"  Precision blind : {metrics['precision_blind']:.4f}  (threshold {THRESHOLDS['precision_blind']:.2f})  {'✓' if verdict['criteria']['precision_blind']['passed'] else '✗'}")
    print(f"  F1 covered      : {metrics['f1_covered']:.4f}  (threshold {THRESHOLDS['f1_covered']:.2f})  {'✓' if verdict['criteria']['f1_covered']['passed'] else '✗'}")
    print(f"  Tier accuracy   : {metrics['tier_accuracy']:.4f}  (threshold {THRESHOLDS['tier_accuracy']:.2f})  {'✓' if verdict['criteria']['tier_accuracy']['passed'] else '✗'}")
    print()
    print(f"  Stream accuracy (informational): {metrics['stream_accuracy']:.4f}  (matched={metrics['stream_matched']}/{metrics['stream_eligible']})")
    for s, b in metrics["per_stream_breakdown"].items():
        if b["truth_count"] == 0:
            continue
        print(f"    {s}: {b['matched']}/{b['truth_count']} = {b['accuracy']:.4f}, predicted_dist={b['predicted_distribution']}")

    return 0 if verdict["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
