#!/usr/bin/env python
"""F-editorial-guardian-corroboration (1-T.2): 真実性検証 (corroboration) 手動ランナー。

1-T.1 (scripts/run_editorial_guardian.py) が出力した EditorialGuardianReport JSON を
入力に、第2層・真実性検証 (grounding による複数ソース突合) で enrich した
レポート JSON を出力する。

- 証拠収集: GUARDIAN_GROUNDING_MODEL (default gemini-2.5-flash) の grounded 検索で
  claim ごとの verification_queries を全実行 (検索は証拠の運搬係)。
- 判定: GUARDIAN role (gemini-3.1-pro-preview、単一モデル・fallback なし) が
  corroborated / contradicted / uncorroborated を claim 単位で判定。
  判定不可は unverified (検証未完、沈黙的劣化の禁止)。
- 公開可否バー: flag されないのは supported かつ corroborated のみ。
  **flag のみ。自動修正・公開ブロックなし。公開判断はカズヤ。**
- 運用ループ: 第1層 contradicted の claim は skip (pending のまま)。人間が成果物を
  直したら 1-T.1 ランナー → 本ランナーを再実行して再検証する。

独立性ルールの除外基準 (元ソースドメイン) は recent_event_pool.event_snapshot の
source_urls / sources_by_locale から導出する (--source-domains で追加・上書き可)。

使い方:
    python scripts/run_editorial_guardian_corroboration.py \
        --report docs/runs/F-editorial-guardian-claim-extraction/x1_slot1_guardian_report.json \
        --out docs/runs/F-editorial-guardian-corroboration/x1_slot1_guardian_report_enriched.json

GEMINI_API_KEY + 課金設定が必要 (judge は paid-only)。exit 2 = judge unavailable。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# プロジェクトルートを sys.path に追加 (run_editorial_guardian.py 前例踏襲)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.generation.editorial_guardian import EditorialGuardianReport
from src.generation.editorial_guardian_corroboration import (
    GroundingSearchClient,
    _normalize_domain,
    corroborate_report,
)

_DEFAULT_REPORT = (
    "docs/runs/F-editorial-guardian-claim-extraction/x1_slot1_guardian_report.json"
)
_DEFAULT_DB = "data/db/hydrangea.db"


def _derive_source_domains(db_path: Path, event_id: str) -> list[str]:
    """event snapshot から元ソースドメイン群を導出する (独立性ルールの除外基準)。

    source_urls + sources_by_locale[*].url + sources_jp/en[*].url の全ドメインを
    集める (cluster event は複数の元ソースを持つ。X1 Slot-1 実測 =
    middleeasteye.net + aljazeera.com の 2 ドメイン)。
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT event_snapshot FROM recent_event_pool WHERE event_id = ?",
            (event_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return []
    event = (json.loads(row[0]) or {}).get("event") or {}

    urls: list[str] = list(event.get("source_urls") or [])
    for refs in (event.get("sources_by_locale") or {}).values():
        urls.extend(r.get("url") or "" for r in refs or [])
    for key in ("sources_jp", "sources_en"):
        urls.extend(r.get("url") or "" for r in event.get(key) or [])

    domains: list[str] = []
    for u in urls:
        d = _normalize_domain(str(u or ""))
        d = d.removeprefix("www.")
        if d and d not in domains:
            domains.append(d)
    return domains


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report", default=_DEFAULT_REPORT, help="1-T.1 レポート JSON のパス"
    )
    parser.add_argument("--db", default=_DEFAULT_DB, help="hydrangea.db パス")
    parser.add_argument(
        "--out", default=None, help="enriched レポート JSON の保存先 (省略時は stdout のみ)"
    )
    parser.add_argument(
        "--source-domains",
        default="",
        help="元ソースドメインの追加指定 (comma 区切り、snapshot 導出分に加算)",
    )
    parser.add_argument(
        "--grounding-model", default=None, help="証拠収集モデルの上書き (default: env)"
    )
    parser.add_argument(
        "--no-resolve-redirects",
        action="store_true",
        help="redirect URL の記事実体解決 (HTTP HEAD) をスキップする",
    )
    args = parser.parse_args()

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"[run_corroboration] missing report: {report_path}")
        return 1
    report = EditorialGuardianReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    if report.guardian_unavailable:
        print(
            "[run_corroboration] input report is guardian_unavailable (第1層検証未完); "
            "run scripts/run_editorial_guardian.py first."
        )
        return 1

    source_domains = _derive_source_domains(Path(args.db), report.event_id)
    extra = [d.strip() for d in args.source_domains.split(",") if d.strip()]
    for d in extra:
        if d not in source_domains:
            source_domains.append(d)
    if not source_domains:
        print(
            "[run_corroboration] WARNING: no source domains derived "
            "(event not in recent_event_pool and --source-domains empty); "
            "independence rule will not exclude anything."
        )
    print(
        f"[run_corroboration] event_id={report.event_id} claims={len(report.claims)} "
        f"source_domains={source_domains}"
    )

    # raw genai.Client は main.py / F-13.B 同様にここで生成して注入する
    # (LLMClient 抽象は tools 注入経路を持たないため)。
    from google import genai

    from src.shared.config import GEMINI_API_KEY

    if not GEMINI_API_KEY:
        print("[run_corroboration] GEMINI_API_KEY is not set")
        return 1
    grounding = GroundingSearchClient(
        genai.Client(api_key=GEMINI_API_KEY),
        model=args.grounding_model,
        resolve_redirects=not args.no_resolve_redirects,
    )

    enriched = corroborate_report(
        report, source_domains=source_domains, grounding_client=grounding
    )

    report_json = json.dumps(
        json.loads(enriched.model_dump_json()), ensure_ascii=False, indent=2
    )
    print(report_json)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report_json + "\n", encoding="utf-8")
        print(f"\n[run_corroboration] enriched report saved: {out_path}")

    summary = enriched.truthfulness_summary
    assert summary is not None  # corroborate_report は必ず設定する
    print(
        f"\n[run_corroboration] grounding_model={summary.grounding_model_used} "
        f"judge_model={summary.judge_model_used} "
        f"grounding_usage={grounding.usage}"
    )
    if summary.judge_unavailable:
        print(
            f"\n[JUDGE UNAVAILABLE] 検証未完: {summary.unavailable_reason}"
        )
        return 2
    if enriched.flagged_claims:
        print(
            f"\n[FLAGGED] {len(enriched.flagged_claims)} claim(s) require human review "
            f"(公開可否バー: supported × corroborated のみ非 flag。"
            f"corroborated={summary.n_corroborated} "
            f"contradicted={summary.n_contradicted} "
            f"uncorroborated={summary.n_uncorroborated} "
            f"unverified={summary.n_unverified} pending={summary.n_pending})"
        )
    else:
        print(
            f"\n[OK] all {summary.n_corroborated} claim(s) supported × corroborated "
            f"(公開可否バー通過。公開判断はカズヤ)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
