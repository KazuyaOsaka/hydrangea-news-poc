"""F-verify-jp-coverage-measure: F-13.B JpCoverageVerifier の精度実測スクリプト。

ゴールデンセット (docs/runs/F-verify-jp-coverage/golden_set.json v1.1) を真値として
F-13.B を実行し、TP/FP/TN/FN・Precision/Recall/F1 を算出する。

Usage:
    python scripts/verify_jp_coverage_measure.py [--cache-mode=fresh|reuse|warm-then-reuse]

実行モード (--cache-mode):
    fresh: 一時 DB を毎回新規作成、19 件全て実 API 呼び出し (デフォルト)
    reuse: 一時 DB を再利用 (前回キャッシュがあれば使用、開発時用)
    warm-then-reuse: 19 件を 2 周実行 (1 周目: 実 API、2 周目: キャッシュ動作検証)

出力:
    docs/runs/F-verify-jp-coverage/measurement_result.json (機械読み詳細)
    docs/runs/F-verify-jp-coverage/REPORT.md (人間読みレポート)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# プロジェクトルートを sys.path に追加 (scripts/ から src/ をインポートするため)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.shared.config import (  # noqa: E402
    GEMINI_API_KEY,
    JP_COVERAGE_GROUNDING_MODEL,
)
from src.shared.logger import get_logger  # noqa: E402
from src.triage.jp_coverage_verifier import JpCoverageVerifier  # noqa: E402

logger = get_logger("verify_jp_coverage_measure")

GOLDEN_SET_PATH = _PROJECT_ROOT / "docs/runs/F-verify-jp-coverage/golden_set.json"
RESULT_JSON_PATH = _PROJECT_ROOT / "docs/runs/F-verify-jp-coverage/measurement_result.json"
REPORT_MD_PATH = _PROJECT_ROOT / "docs/runs/F-verify-jp-coverage/REPORT.md"
TEMP_DB_PATH = Path("/tmp/jp_coverage_measure.db")

# F-13.B が触る jp_coverage_cache テーブルのスキーマ。
# 本番 DB を汚染しないよう一時 DB に同一スキーマを再現する。
# (src/storage/db.py 102-112 と一致)
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

# 合格基準
_THRESHOLDS = {
    "recall_covered": 0.90,
    "precision_blind": 0.80,
    "f1_covered": 0.85,
    "tier_accuracy": 0.70,
}


def setup_temp_db(db_path: Path) -> None:
    """一時 DB に jp_coverage_cache テーブルを作成 (本番 DB を汚染しない)。"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(_TEMP_DB_SCHEMA)
        conn.commit()
    logger.info(f"Temp DB ready at {db_path}")


def load_golden_set(path: Path) -> dict:
    """golden_set.json をロード。"""
    return json.loads(path.read_text(encoding="utf-8"))


def get_gemini_client():
    """Grounding 検索用の google.genai.Client を構築する。

    F-13.B は LLMClient 抽象ではなく、google.genai.Client を直接受け取り
    `.models.generate_content(..., tools=[GoogleSearch()])` を呼ぶ仕様。
    本スクリプトは src/main.py:3179-3180 の本番パターンに合わせて
    `google.genai.Client(api_key=...)` を直接生成する。
    """
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. .env or shell に設定してください。"
        )
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY)


def run_measurement(
    verifier: JpCoverageVerifier, entries: list[dict]
) -> list[dict]:
    """各 entry に対して F-13.B を実行し結果を収集。

    エラーは個別記録で継続実行 (1 件失敗で全体停止しない)。
    """
    results: list[dict] = []
    total = len(entries)
    for i, entry in enumerate(entries, 1):
        logger.info(
            f"[{i}/{total}] Verifying {entry['id']} (event_id={entry['event_id']}): "
            f"{entry['title'][:60]}..."
        )
        start = time.time()
        error_field: Optional[str] = None
        actual_has_jp_coverage: Optional[bool] = None
        actual_matched_tier: Optional[str] = None
        matched_urls: list[str] = []
        matched_domains: list[str] = []
        excluded_urls: list[str] = []
        search_query = ""
        cached_flag = False

        try:
            result = verifier.verify(
                event_id=entry["event_id"],
                title=entry["title"],
                summary=entry.get("summary", ""),
            )
            # F-13.B 内部の API エラーは has_jp_coverage=True (安全側) +
            # error フィールド non-null として返す。これは精度測定の文脈では
            # 「測定エラー」として True/False 判定から外したいので、
            # result.error が non-null の場合は actual_has_jp_coverage=None に変換。
            if result.error:
                error_field = result.error
                actual_has_jp_coverage = None
            else:
                actual_has_jp_coverage = bool(result.has_jp_coverage)
            actual_matched_tier = result.matched_tier
            matched_urls = list(result.matched_urls)
            matched_domains = list(result.matched_domains)
            excluded_urls = list(result.excluded_urls)
            search_query = result.search_query or ""
            cached_flag = bool(result.cached)
        except Exception as exc:
            error_field = f"{type(exc).__name__}: {exc}"
            actual_has_jp_coverage = None
            logger.error(f"  Exception: {error_field}")

        elapsed = time.time() - start

        log_status = (
            "OK"
            if error_field is None
            else f"ERROR ({error_field[:80]})"
        )
        logger.info(
            f"  -> expected={entry['expected_has_jp_coverage']} "
            f"actual={actual_has_jp_coverage} "
            f"tier={actual_matched_tier} "
            f"matched_n={len(matched_urls)} "
            f"elapsed={elapsed:.2f}s {log_status}"
        )

        results.append(
            {
                "id": entry["id"],
                "event_id": entry["event_id"],
                "title": entry["title"],
                "expected_has_jp_coverage": entry["expected_has_jp_coverage"],
                "expected_tier": entry.get("expected_tier"),
                "actual_has_jp_coverage": actual_has_jp_coverage,
                "actual_matched_tier": actual_matched_tier,
                "matched_urls": matched_urls,
                "matched_domains": matched_domains,
                "excluded_urls": excluded_urls,
                "search_query": search_query,
                "error": error_field,
                "cached": cached_flag,
                "elapsed_seconds": round(elapsed, 3),
                "stream_2_candidate": entry.get("stream_2_candidate"),
                "manual_verification_note": entry.get("manual_verification_note"),
                "manual_verification_urls": entry.get("manual_verification_urls", []),
            }
        )
    return results


def compute_metrics(results: list[dict]) -> dict:
    """TP/FP/TN/FN・Precision/Recall/F1 を集計。"""
    tp = sum(
        1
        for r in results
        if r["expected_has_jp_coverage"] is True
        and r["actual_has_jp_coverage"] is True
    )
    tn = sum(
        1
        for r in results
        if r["expected_has_jp_coverage"] is False
        and r["actual_has_jp_coverage"] is False
    )
    fp = sum(
        1
        for r in results
        if r["expected_has_jp_coverage"] is False
        and r["actual_has_jp_coverage"] is True
    )
    fn = sum(
        1
        for r in results
        if r["expected_has_jp_coverage"] is True
        and r["actual_has_jp_coverage"] is False
    )
    error = sum(1 for r in results if r["actual_has_jp_coverage"] is None)

    def _safe_div(numer: float, denom: float) -> float:
        return numer / denom if denom > 0 else 0.0

    precision_covered = _safe_div(tp, tp + fp)
    recall_covered = _safe_div(tp, tp + fn)
    f1_covered = _safe_div(
        2 * precision_covered * recall_covered,
        precision_covered + recall_covered,
    )
    precision_blind = _safe_div(tn, tn + fn)
    recall_blind = _safe_div(tn, tn + fp)

    # Tier 一致率: True 期待値かつ TP のうち、expected_tier と actual_matched_tier が一致した割合。
    tier_eligible = [
        r
        for r in results
        if r["expected_has_jp_coverage"] is True
        and r["actual_has_jp_coverage"] is True
        and r.get("expected_tier")
    ]
    tier_matched = sum(
        1 for r in tier_eligible if r["expected_tier"] == r["actual_matched_tier"]
    )
    tier_accuracy = _safe_div(tier_matched, len(tier_eligible))

    # stream_2_candidate メタ集計 (blind_002 / 004 / 005 / 009、いずれも True 期待)
    stream_2_entries = [r for r in results if r.get("stream_2_candidate")]
    stream_2_caught_as_true = sum(
        1 for r in stream_2_entries if r["actual_has_jp_coverage"] is True
    )

    return {
        "total": len(results),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "error": error,
        "precision_covered": precision_covered,
        "recall_covered": recall_covered,
        "f1_covered": f1_covered,
        "precision_blind": precision_blind,
        "recall_blind": recall_blind,
        "tier_accuracy": tier_accuracy,
        "tier_eligible": len(tier_eligible),
        "tier_matched": tier_matched,
        "stream_2_total": len(stream_2_entries),
        "stream_2_f13b_caught_as_true": stream_2_caught_as_true,
    }


def determine_pass_fail(metrics: dict) -> dict:
    """合格基準に基づいて pass / conditional_pass / fail を判定。

    合格基準:
        Recall (covered) >= 90%   ★ 致命的 FN 抑制が最重要
        Precision (blind) >= 80%
        F1 (covered) >= 0.85
        Tier 一致率 >= 70%

    判定ロジック:
        - 全 4 指標達成 → pass
        - Recall (covered) のみ達成 → conditional_pass
        - Recall (covered) 未達 → fail
        - その他 (Recall 達成 + 他 1 つ以上失敗) → fail
    """
    criteria = {
        "recall_covered": (metrics["recall_covered"], _THRESHOLDS["recall_covered"]),
        "precision_blind": (metrics["precision_blind"], _THRESHOLDS["precision_blind"]),
        "f1_covered": (metrics["f1_covered"], _THRESHOLDS["f1_covered"]),
        "tier_accuracy": (metrics["tier_accuracy"], _THRESHOLDS["tier_accuracy"]),
    }
    passed = {k: v[0] >= v[1] for k, v in criteria.items()}
    all_passed = all(passed.values())
    recall_passed = passed["recall_covered"]
    only_recall_passed = recall_passed and not all_passed

    if all_passed:
        verdict = "pass"
    elif only_recall_passed and sum(passed.values()) == 1:
        verdict = "conditional_pass"
    elif not recall_passed:
        verdict = "fail"
    else:
        # Recall 達成 + 他 1-2 つ失敗 → conditional_pass 寄り扱いだが本仕様では fail
        # (BATCH プロンプト「全 4 指標達成 → pass、Recall (covered) のみ達成 →
        #  conditional_pass、Recall (covered) 未達 → fail、その他のケースも fail」)
        verdict = "fail"

    return {
        "verdict": verdict,
        "criteria": {
            k: {
                "actual": round(v[0], 4),
                "threshold": v[1],
                "passed": passed[k],
            }
            for k, v in criteria.items()
        },
        "all_passed": all_passed,
    }


def save_result_json(
    results: list[dict],
    metrics: dict,
    judgement: dict,
    golden_meta: dict,
    f13b_source_commit: str,
    cache_mode: str,
    second_pass_cache_hits: Optional[int],
    path: Path,
) -> None:
    """機械読み JSON を保存。"""
    output = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "batch": "F-verify-jp-coverage-measure",
        "golden_set_version": golden_meta.get("version"),
        "golden_set_path": str(GOLDEN_SET_PATH.relative_to(_PROJECT_ROOT)),
        "f13b_source_path": "src/triage/jp_coverage_verifier.py",
        "f13b_source_commit": f13b_source_commit,
        "grounding_model": JP_COVERAGE_GROUNDING_MODEL,
        "cache_mode": cache_mode,
        "second_pass_cache_hits": second_pass_cache_hits,
        "thresholds": _THRESHOLDS,
        "metrics": metrics,
        "judgement": judgement,
        "entries": results,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Result JSON saved: {path}")


def _format_pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _check(passed: bool) -> str:
    return "✅" if passed else "❌"


def save_report_md(
    results: list[dict],
    metrics: dict,
    judgement: dict,
    golden_meta: dict,
    f13b_source_commit: str,
    cache_mode: str,
    second_pass_cache_hits: Optional[int],
    path: Path,
) -> None:
    """人間読み Markdown レポートを保存。"""
    lines: list[str] = []
    verdict = judgement["verdict"]
    crit = judgement["criteria"]

    lines.append("# F-verify-jp-coverage-measure 実行レポート")
    lines.append("")
    lines.append(f"- 実行日時: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- F-13.B コミット: `{f13b_source_commit}`")
    lines.append(
        f"- ゴールデンセット: v{golden_meta.get('version', '?')} "
        f"({len(results)} entries)"
    )
    lines.append(f"- Grounding モデル: `{JP_COVERAGE_GROUNDING_MODEL}`")
    lines.append(f"- Cache mode: `{cache_mode}`")
    if second_pass_cache_hits is not None:
        lines.append(
            f"- Second pass cache hits: {second_pass_cache_hits}/{len(results)}"
        )
    lines.append("")

    lines.append("## 1. 判定")
    lines.append("")
    verdict_label = {
        "pass": "✅ **pass** (合格)",
        "conditional_pass": "⚠️ **conditional_pass** (条件付き合格)",
        "fail": "❌ **fail** (不合格)",
    }.get(verdict, verdict)
    lines.append(f"**Verdict: {verdict_label}**")
    lines.append("")
    lines.append("判定根拠:")
    lines.append("")
    lines.append(_row(["指標", "実測値", "合格基準", "達成"]))
    lines.append(_row(["---"] * 4))
    lines.append(
        _row(
            [
                "Recall (covered)",
                _format_pct(crit["recall_covered"]["actual"]),
                f">= {_format_pct(crit['recall_covered']['threshold'])}",
                _check(crit["recall_covered"]["passed"]),
            ]
        )
    )
    lines.append(
        _row(
            [
                "Precision (blind)",
                _format_pct(crit["precision_blind"]["actual"]),
                f">= {_format_pct(crit['precision_blind']['threshold'])}",
                _check(crit["precision_blind"]["passed"]),
            ]
        )
    )
    lines.append(
        _row(
            [
                "F1 (covered)",
                f"{crit['f1_covered']['actual']:.3f}",
                f">= {crit['f1_covered']['threshold']:.2f}",
                _check(crit["f1_covered"]["passed"]),
            ]
        )
    )
    lines.append(
        _row(
            [
                "Tier 一致率",
                _format_pct(crit["tier_accuracy"]["actual"]),
                f">= {_format_pct(crit['tier_accuracy']['threshold'])}",
                _check(crit["tier_accuracy"]["passed"]),
            ]
        )
    )
    lines.append("")

    lines.append("## 2. 集計指標")
    lines.append("")
    lines.append(_row(["指標", "値"]))
    lines.append(_row(["---", "---"]))
    lines.append(_row(["Total", str(metrics["total"])]))
    lines.append(_row(["TP (covered, 一致)", str(metrics["tp"])]))
    lines.append(_row(["TN (blind, 一致)", str(metrics["tn"])]))
    lines.append(_row(["FP (未報道→True 誤判定)", str(metrics["fp"])]))
    lines.append(_row(["FN (報道済→False 誤判定)", str(metrics["fn"])]))
    lines.append(_row(["Error (測定不能)", str(metrics["error"])]))
    lines.append(_row(["Precision (covered)", _format_pct(metrics["precision_covered"])]))
    lines.append(_row(["Recall (covered)", _format_pct(metrics["recall_covered"])]))
    lines.append(_row(["F1 (covered)", f"{metrics['f1_covered']:.3f}"]))
    lines.append(_row(["Precision (blind)", _format_pct(metrics["precision_blind"])]))
    lines.append(_row(["Recall (blind)", _format_pct(metrics["recall_blind"])]))
    lines.append(
        _row(
            [
                "Tier 一致率",
                f"{_format_pct(metrics['tier_accuracy'])} "
                f"({metrics['tier_matched']}/{metrics['tier_eligible']})",
            ]
        )
    )
    lines.append(
        _row(
            [
                "stream_2_candidate F-13.B True",
                f"{metrics['stream_2_f13b_caught_as_true']}/{metrics['stream_2_total']}",
            ]
        )
    )
    lines.append("")

    lines.append("### 混同行列")
    lines.append("")
    lines.append(_row(["", "Actual True", "Actual False", "Error"]))
    lines.append(_row(["---"] * 4))
    expected_true_total = sum(
        1 for r in results if r["expected_has_jp_coverage"] is True
    )
    expected_false_total = sum(
        1 for r in results if r["expected_has_jp_coverage"] is False
    )
    expected_true_error = sum(
        1
        for r in results
        if r["expected_has_jp_coverage"] is True
        and r["actual_has_jp_coverage"] is None
    )
    expected_false_error = sum(
        1
        for r in results
        if r["expected_has_jp_coverage"] is False
        and r["actual_has_jp_coverage"] is None
    )
    lines.append(
        _row(
            [
                f"Expected True ({expected_true_total} 件)",
                str(metrics["tp"]),
                str(metrics["fn"]),
                str(expected_true_error),
            ]
        )
    )
    lines.append(
        _row(
            [
                f"Expected False ({expected_false_total} 件)",
                str(metrics["fp"]),
                str(metrics["tn"]),
                str(expected_false_error),
            ]
        )
    )
    lines.append("")

    # 3. 誤判定詳細
    fn_entries = [
        r
        for r in results
        if r["expected_has_jp_coverage"] is True
        and r["actual_has_jp_coverage"] is False
    ]
    fp_entries = [
        r
        for r in results
        if r["expected_has_jp_coverage"] is False
        and r["actual_has_jp_coverage"] is True
    ]
    error_entries = [r for r in results if r["actual_has_jp_coverage"] is None]

    lines.append("## 3. 誤判定詳細")
    lines.append("")
    lines.append("### 3.1 False Negative (致命的、報道済み → 未報道判定)")
    lines.append("")
    if fn_entries:
        lines.append(
            _row(["id", "title", "expected_tier", "matched_urls", "search_query"])
        )
        lines.append(_row(["---"] * 5))
        for r in fn_entries:
            lines.append(
                _row(
                    [
                        r["id"],
                        r["title"][:50].replace("|", "\\|"),
                        str(r.get("expected_tier")),
                        f"{len(r['matched_urls'])} urls",
                        r.get("search_query", "")[:60].replace("|", "\\|"),
                    ]
                )
            )
    else:
        lines.append("- なし ✅")
    lines.append("")

    lines.append("### 3.2 False Positive (機会損失、未報道 → 報道済み判定)")
    lines.append("")
    if fp_entries:
        lines.append(
            _row(
                [
                    "id",
                    "title",
                    "actual_matched_tier",
                    "matched_domains",
                    "search_query",
                ]
            )
        )
        lines.append(_row(["---"] * 5))
        for r in fp_entries:
            lines.append(
                _row(
                    [
                        r["id"],
                        r["title"][:50].replace("|", "\\|"),
                        str(r.get("actual_matched_tier")),
                        ", ".join(r["matched_domains"][:3]).replace("|", "\\|"),
                        r.get("search_query", "")[:60].replace("|", "\\|"),
                    ]
                )
            )
    else:
        lines.append("- なし ✅")
    lines.append("")

    lines.append("### 3.3 Error (測定不能)")
    lines.append("")
    if error_entries:
        lines.append(_row(["id", "title", "error"]))
        lines.append(_row(["---"] * 3))
        for r in error_entries:
            lines.append(
                _row(
                    [
                        r["id"],
                        r["title"][:50].replace("|", "\\|"),
                        (r.get("error") or "")[:80].replace("|", "\\|"),
                    ]
                )
            )
    else:
        lines.append("- なし ✅")
    lines.append("")

    # 4. Tier 判定の精度
    lines.append("## 4. Tier 判定の精度")
    lines.append("")
    tier_eligible = [
        r
        for r in results
        if r["expected_has_jp_coverage"] is True
        and r["actual_has_jp_coverage"] is True
        and r.get("expected_tier")
    ]
    if tier_eligible:
        lines.append(
            _row(["id", "expected_tier", "actual_matched_tier", "一致"])
        )
        lines.append(_row(["---"] * 4))
        for r in tier_eligible:
            ok = r["expected_tier"] == r["actual_matched_tier"]
            lines.append(
                _row(
                    [
                        r["id"],
                        str(r["expected_tier"]),
                        str(r.get("actual_matched_tier")),
                        _check(ok),
                    ]
                )
            )
    else:
        lines.append("- Tier 判定対象 0 件 (TP かつ expected_tier 指定あり)")
    lines.append("")

    # 5. stream_2_candidate
    stream_2_entries = [r for r in results if r.get("stream_2_candidate")]
    lines.append("## 5. stream_2_candidate 4 件の F-13.B 出力")
    lines.append("")
    lines.append(
        "stream_2_candidate メタ付きエントリ (blind_002/004/005/009) は "
        "「広範な事件は Tier 1-2 で報道済み (True 期待)、特定角度は系統 2 候補」"
        "というパターン。F-stream-2-filter-design 実装時に系統 2 ターゲット候補と"
        "して再評価される。"
    )
    lines.append("")
    if stream_2_entries:
        lines.append(
            _row(
                [
                    "id",
                    "actual",
                    "actual_matched_tier",
                    "matched_domains",
                    "系統 2 角度 (要約)",
                ]
            )
        )
        lines.append(_row(["---"] * 5))
        for r in stream_2_entries:
            angle = (
                r.get("stream_2_candidate", {}).get("specific_angle_unreported_in_jp", "")
                or ""
            )
            lines.append(
                _row(
                    [
                        r["id"],
                        str(r["actual_has_jp_coverage"]),
                        str(r.get("actual_matched_tier")),
                        ", ".join(r["matched_domains"][:3]).replace("|", "\\|"),
                        angle[:80].replace("|", "\\|"),
                    ]
                )
            )
    else:
        lines.append("- なし")
    lines.append("")

    # 6. 全件詳細
    lines.append("## 6. 全件詳細")
    lines.append("")
    lines.append(
        _row(
            [
                "id",
                "expected",
                "actual",
                "expected_tier",
                "actual_tier",
                "matched_n",
                "elapsed",
                "cached",
            ]
        )
    )
    lines.append(_row(["---"] * 8))
    for r in results:
        lines.append(
            _row(
                [
                    r["id"],
                    str(r["expected_has_jp_coverage"]),
                    str(r["actual_has_jp_coverage"]),
                    str(r.get("expected_tier")),
                    str(r.get("actual_matched_tier")),
                    str(len(r["matched_urls"])),
                    f"{r['elapsed_seconds']:.2f}s",
                    "yes" if r.get("cached") else "no",
                ]
            )
        )
    lines.append("")

    # 7. 改善提案 (verdict 別)
    lines.append("## 7. 改善提案")
    lines.append("")
    if verdict == "pass":
        lines.append("- 改善提案なし、現仕様で運用継続。")
    else:
        lines.append("### 未達指標と該当エントリの傾向")
        lines.append("")
        for k, v in crit.items():
            if not v["passed"]:
                lines.append(
                    f"- **{k}**: 実測 "
                    f"{v['actual']:.3f} < 閾値 {v['threshold']:.2f} (未達)"
                )
        lines.append("")
        if fn_entries:
            lines.append(
                f"### FN ({len(fn_entries)} 件) — 報道済みなのに未報道判定"
            )
            lines.append("")
            lines.append(
                "Recall 未達の主因。検索クエリ改善 / WL ドメイン拡張 / "
                "Tier 別重み付け等で対処要検討。"
            )
            lines.append("")
            for r in fn_entries:
                manual_urls = r.get("manual_verification_urls") or []
                lines.append(f"- `{r['id']}` ({r['title'][:60]})")
                lines.append(
                    f"  - search_query: `{r.get('search_query', '')}`"
                )
                lines.append(
                    f"  - F-13.B が拾った WL ドメイン: "
                    f"{r['matched_domains'] or '(なし)'}"
                )
                lines.append(
                    f"  - 真値で確認済み URL (manual): "
                    f"{len(manual_urls)} 件"
                )
            lines.append("")
        if fp_entries:
            lines.append(
                f"### FP ({len(fp_entries)} 件) — 未報道なのに報道済み判定"
            )
            lines.append("")
            lines.append(
                "Precision (blind) 未達の主因。F-13.B が WL ドメイン以外を WL "
                "扱いしていないか、または擬似マッチング (URL 部分文字列衝突) "
                "が発生していないか確認要。"
            )
            lines.append("")
            for r in fp_entries:
                lines.append(f"- `{r['id']}` ({r['title'][:60]})")
                lines.append(
                    f"  - matched_domains: {r['matched_domains']}"
                )
                lines.append(
                    f"  - matched_urls (先頭): "
                    f"{r['matched_urls'][:2] if r['matched_urls'] else []}"
                )
            lines.append("")
        if error_entries:
            lines.append(
                f"### Error ({len(error_entries)} 件) — 測定不能"
            )
            lines.append("")
            lines.append(
                "API クォータ・ネットワーク問題の可能性。"
                "再実行 (--cache-mode=reuse) で残存分のみ再測定するのが効率的。"
            )
            lines.append("")
        lines.append("### 推奨アクション")
        lines.append("")
        if verdict == "fail":
            lines.append(
                "- F-jp-coverage-improve バッチを起動 "
                "(緊急度 高に登録)。F-stream-2-filter-design 着手は **保留**。"
            )
        elif verdict == "conditional_pass":
            lines.append(
                "- 未達指標の改善を中緊急度に登録、"
                "F-stream-2-filter-design 着手は OK。"
            )

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "*このレポートは scripts/verify_jp_coverage_measure.py が自動生成。"
        "ゴールデンセット v1.1 (19 entries) を真値として F-13.B の精度を実測。*"
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Report MD saved: {path}")


def _get_git_commit() -> str:
    """現在の HEAD コミット (短縮 SHA) を取得。失敗時は 'unknown'。"""
    try:
        import subprocess
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-mode",
        choices=["fresh", "reuse", "warm-then-reuse"],
        default="fresh",
        help="fresh: 一時 DB を毎回新規 / reuse: 既存キャッシュ再利用 / "
        "warm-then-reuse: 1 周目実 API + 2 周目キャッシュ動作確認",
    )
    args = parser.parse_args()

    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not set in .env or shell. Aborting.")
        return 1

    f13b_commit = _get_git_commit()
    logger.info(f"F-13.B source commit (HEAD): {f13b_commit}")

    # 1. ゴールデンセットロード
    if not GOLDEN_SET_PATH.exists():
        logger.error(f"Golden set not found: {GOLDEN_SET_PATH}")
        return 1
    golden = load_golden_set(GOLDEN_SET_PATH)
    entries = golden["entries"]
    logger.info(
        f"Loaded {len(entries)} entries from golden set v{golden.get('version')}"
    )

    # 2. 一時 DB セットアップ
    if args.cache_mode == "fresh" and TEMP_DB_PATH.exists():
        TEMP_DB_PATH.unlink()
        logger.info(f"Removed existing temp DB: {TEMP_DB_PATH}")
    setup_temp_db(TEMP_DB_PATH)

    # 3. Gemini クライアント取得
    client = get_gemini_client()

    # 4. F-13.B 初期化
    verifier = JpCoverageVerifier(
        gemini_client=client,
        db_path=TEMP_DB_PATH,
        model=JP_COVERAGE_GROUNDING_MODEL,
    )

    # 5. 測定実行
    logger.info("=" * 80)
    logger.info(f"First pass: F-13.B 実行 (cache_mode={args.cache_mode})")
    logger.info("=" * 80)
    pass_start = time.time()
    results = run_measurement(verifier, entries)
    pass_elapsed = time.time() - pass_start
    logger.info(f"First pass elapsed: {pass_elapsed:.1f}s")

    # 5b. warm-then-reuse モード: 2 周目実行
    second_pass_cache_hits: Optional[int] = None
    if args.cache_mode == "warm-then-reuse":
        logger.info("=" * 80)
        logger.info("Second pass: キャッシュ動作確認 (実 API 呼ばないはず)")
        logger.info("=" * 80)
        results_2nd = run_measurement(verifier, entries)
        second_pass_cache_hits = sum(1 for r in results_2nd if r.get("cached"))
        logger.info(
            f"Second pass cache hits: {second_pass_cache_hits}/{len(entries)}"
        )

    # 6. 集計 + 判定
    metrics = compute_metrics(results)
    judgement = determine_pass_fail(metrics)

    # 7. 結果出力
    save_result_json(
        results,
        metrics,
        judgement,
        golden,
        f13b_commit,
        args.cache_mode,
        second_pass_cache_hits,
        RESULT_JSON_PATH,
    )
    save_report_md(
        results,
        metrics,
        judgement,
        golden,
        f13b_commit,
        args.cache_mode,
        second_pass_cache_hits,
        REPORT_MD_PATH,
    )

    # 8. サマリ表示
    logger.info("=" * 80)
    logger.info(f"Verdict: {judgement['verdict']}")
    logger.info(f"Recall  (covered): {metrics['recall_covered']:.2%}")
    logger.info(f"Precision (blind): {metrics['precision_blind']:.2%}")
    logger.info(f"F1      (covered): {metrics['f1_covered']:.3f}")
    logger.info(
        f"Tier accuracy:     {metrics['tier_accuracy']:.2%} "
        f"({metrics['tier_matched']}/{metrics['tier_eligible']})"
    )
    logger.info(
        f"TP={metrics['tp']} TN={metrics['tn']} "
        f"FP={metrics['fp']} FN={metrics['fn']} "
        f"Error={metrics['error']}"
    )
    logger.info("=" * 80)
    logger.info(f"Result JSON: {RESULT_JSON_PATH}")
    logger.info(f"Report MD:   {REPORT_MD_PATH}")

    # 合格判定の最終判断は人間 + docs レビュー。exit code 0 で終了。
    return 0


if __name__ == "__main__":
    sys.exit(main())
