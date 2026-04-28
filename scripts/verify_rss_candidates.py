"""
F-8-PRE: RSS 候補媒体の取得確認スクリプト。

各媒体の RSS URL 候補を順番に試行し、取得可能性を検証する。
結果を docs/MEDIA_RSS_CANDIDATES.md (人間可読) と
docs/MEDIA_RSS_CANDIDATES_RESULT.json (機械可読) に書き出す。

Usage:
    python -m scripts.verify_rss_candidates

このスクリプトは scripts/ 配下に配置されており、本番ロジック (src/) には影響しない。
configs/sources.yaml も変更しない (検証のみ)。
"""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import feedparser


CANDIDATES_INPUT = Path("docs/MEDIA_RSS_CANDIDATES_INPUT.yaml")
CANDIDATES_OUTPUT_MD = Path("docs/MEDIA_RSS_CANDIDATES.md")
CANDIDATES_OUTPUT_JSON = Path("docs/MEDIA_RSS_CANDIDATES_RESULT.json")
TIMEOUT_SEC = 30


@dataclass
class VerificationResult:
    name: str
    tier: str
    candidates: list[str]
    notes: Optional[str] = None
    warning: Optional[str] = None
    successful_url: Optional[str] = None
    entry_count: int = 0
    latest_entry_date: Optional[str] = None
    feed_title: Optional[str] = None
    error: Optional[str] = None
    elapsed_sec: float = 0.0

    @property
    def status(self) -> str:
        if self.successful_url:
            if self.entry_count >= 5:
                return "OK"
            elif self.entry_count >= 1:
                return "LOW_VOLUME"
            else:
                return "EMPTY"
        return "FAILED"


def verify_single_url(url: str) -> tuple[bool, dict]:
    """1つの URL を検証し、(成功, 詳細) を返す。"""
    try:
        start = time.time()
        feed = feedparser.parse(
            url,
            request_headers={"User-Agent": "Mozilla/5.0 (Hydrangea-RSS-Verifier/0.1)"},
        )
        elapsed = time.time() - start

        if feed.bozo and not feed.entries:
            err = "parse_failed"
            if hasattr(feed, "bozo_exception"):
                err = str(feed.bozo_exception)[:200]
            return False, {"error": err, "elapsed_sec": elapsed}

        return True, {
            "entry_count": len(feed.entries),
            "latest_entry": feed.entries[0].get("published", "unknown") if feed.entries else None,
            "feed_title": feed.feed.get("title", "unknown") if feed.entries else "unknown",
            "elapsed_sec": elapsed,
        }
    except Exception as exc:
        return False, {"error": str(exc)[:200], "elapsed_sec": 0.0}


def verify_candidate(
    name: str,
    tier: str,
    candidates: list[str],
    notes: Optional[str] = None,
    warning: Optional[str] = None,
) -> VerificationResult:
    """1媒体の候補 URL リストを順次試行し、最初に成功した URL を採用。"""
    result = VerificationResult(
        name=name, tier=tier, candidates=candidates, notes=notes, warning=warning
    )

    for url in candidates:
        print(f"  [{name}] Trying: {url}")
        success, detail = verify_single_url(url)
        result.elapsed_sec += detail.get("elapsed_sec", 0.0)

        if success:
            result.successful_url = url
            result.entry_count = detail["entry_count"]
            result.latest_entry_date = detail.get("latest_entry")
            result.feed_title = detail.get("feed_title", "unknown")[:80]
            print(f"    -> OK ({result.entry_count} entries, '{result.feed_title}')")
            return result
        else:
            print(f"    -> FAILED: {detail.get('error', 'unknown')[:80]}")

    result.error = "all_candidates_failed"
    return result


def main() -> int:
    """全候補を検証し、結果を出力。"""
    import yaml

    if not CANDIDATES_INPUT.exists():
        print(f"ERROR: {CANDIDATES_INPUT} が見つかりません")
        return 1

    with open(CANDIDATES_INPUT, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    results: list[VerificationResult] = []

    print("=== Tier 1 必須追加 ===")
    for entry in config.get("tier_1_essential", []):
        result = verify_candidate(
            name=entry["name"],
            tier="tier_1",
            candidates=entry["candidates"],
            notes=entry.get("notes"),
        )
        results.append(result)

    print("\n=== Tier 3 警告付き ===")
    for entry in config.get("tier_3_with_warning", []):
        result = verify_candidate(
            name=entry["name"],
            tier="tier_3",
            candidates=entry["candidates"],
            notes=entry.get("notes"),
            warning=entry.get("warning"),
        )
        results.append(result)

    # JSON 出力
    json_data = []
    for r in results:
        json_data.append({
            "name": r.name,
            "tier": r.tier,
            "status": r.status,
            "successful_url": r.successful_url,
            "entry_count": r.entry_count,
            "latest_entry_date": r.latest_entry_date,
            "feed_title": r.feed_title,
            "notes": r.notes,
            "warning": r.warning,
            "error": r.error,
            "elapsed_sec": round(r.elapsed_sec, 2),
        })

    CANDIDATES_OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(CANDIDATES_OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    # Markdown レポート出力
    write_markdown_report(results)

    # サマリ表示
    ok_count = sum(1 for r in results if r.status == "OK")
    low_count = sum(1 for r in results if r.status == "LOW_VOLUME")
    empty_count = sum(1 for r in results if r.status == "EMPTY")
    failed_count = sum(1 for r in results if r.status == "FAILED")

    print(f"\n=== Summary ===")
    print(f"  OK         : {ok_count}/{len(results)}")
    print(f"  LOW_VOLUME : {low_count}/{len(results)}")
    print(f"  EMPTY      : {empty_count}/{len(results)}")
    print(f"  FAILED     : {failed_count}/{len(results)}")
    print(f"\nReports:")
    print(f"  - {CANDIDATES_OUTPUT_MD}")
    print(f"  - {CANDIDATES_OUTPUT_JSON}")

    return 0


def write_markdown_report(results: list[VerificationResult]) -> None:
    """検証結果を Markdown で出力。"""
    lines = [
        "# Hydrangea — RSS Media Candidates Verification",
        "",
        "F-8-PRE で実施した RSS 取得検証の結果。",
        "Phase A.5-1 で本番 `configs/sources.yaml` に追加する候補を実測する。",
        "",
        f"検証日: {time.strftime('%Y-%m-%d')}",
        "",
        "## 凡例",
        "",
        "| Status | 意味 |",
        "|---|---|",
        "| OK | 5件以上のエントリ取得成功 → 本番投入推奨 |",
        "| LOW_VOLUME | 1〜4件取得 → 投入可能だが要監視 |",
        "| EMPTY | 接続成功だがエントリ0 → 要再調査 |",
        "| FAILED | 全候補 URL で接続失敗 → 別URL要調査 or 除外 |",
        "",
        "## Tier 1 必須追加",
        "",
        "| Name | Status | Entries | Latest | URL |",
        "|---|---|---|---|---|",
    ]

    tier_1 = [r for r in results if r.tier == "tier_1"]
    for r in tier_1:
        url = (r.successful_url or "—")[:80]
        latest = r.latest_entry_date[:10] if r.latest_entry_date else "—"
        lines.append(f"| {r.name} | {r.status} | {r.entry_count} | {latest} | {url} |")

    lines.extend([
        "",
        "## Tier 3 警告付き",
        "",
        "| Name | Status | Entries | Latest | Warning | URL |",
        "|---|---|---|---|---|---|",
    ])

    tier_3 = [r for r in results if r.tier == "tier_3"]
    for r in tier_3:
        url = (r.successful_url or "—")[:60]
        latest = r.latest_entry_date[:10] if r.latest_entry_date else "—"
        warning = r.warning or "—"
        lines.append(f"| {r.name} | {r.status} | {r.entry_count} | {latest} | {warning} | {url} |")

    lines.extend([
        "",
        "## 推奨アクション",
        "",
        "### F-8-1 (Phase A.5-1) で本番投入推奨 (OK)",
        "",
    ])
    ok_results = [r for r in results if r.status == "OK"]
    if not ok_results:
        lines.append("なし")
    else:
        for r in ok_results:
            tier_label = "Tier 1" if r.tier == "tier_1" else "Tier 3"
            warning_str = f" ⚠️ {r.warning}" if r.warning else ""
            lines.append(f"- **{r.name}** ({tier_label}){warning_str}")
            lines.append(f"  - URL: `{r.successful_url}`")
            lines.append(f"  - {r.entry_count} entries, latest: {r.latest_entry_date or '—'}")

    lines.extend([
        "",
        "### 要監視 (LOW_VOLUME)",
        "",
    ])
    low_vol = [r for r in results if r.status == "LOW_VOLUME"]
    if not low_vol:
        lines.append("なし")
    else:
        for r in low_vol:
            lines.append(f"- **{r.name}**: {r.entry_count} entries のみ ({r.successful_url})")

    lines.extend([
        "",
        "### 要再調査 (FAILED / EMPTY)",
        "",
    ])
    failed = [r for r in results if r.status in ("FAILED", "EMPTY")]
    if not failed:
        lines.append("なし")
    else:
        for r in failed:
            lines.append(f"- **{r.name}**: {r.error or 'empty feed'}")
            for url in r.candidates:
                lines.append(f"  - 試行 URL: `{url}`")

    lines.extend([
        "",
        "## 注目媒体の状況",
        "",
        "Hydrangea のコンセプト深化に重要な媒体:",
        "",
    ])
    critical_names = {"WION", "Middle_East_Eye", "TeleSUR", "Meduza", "Caixin_Global", "Mada_Masr", "The_Initium"}
    for name in critical_names:
        r = next((r for r in results if r.name == name), None)
        if r is None:
            continue
        status_icon = {"OK": "✅", "LOW_VOLUME": "⚠️", "EMPTY": "❓", "FAILED": "❌"}.get(r.status, "?")
        lines.append(f"- {status_icon} **{r.name}**: {r.status} ({r.entry_count} entries)")

    lines.extend([
        "",
        "## 次のアクション",
        "",
        "1. OK 媒体は F-8-1 で `configs/sources.yaml` に追加",
        "2. LOW_VOLUME 媒体は監視しつつ追加",
        "3. FAILED 媒体は別 URL を再調査するか除外",
        "4. configs/source_profiles.yaml で Tier / 警告フラグを定義",
        "",
        "---",
        f"*Generated by `scripts/verify_rss_candidates.py` at {time.strftime('%Y-%m-%d %H:%M:%S')}*",
    ])

    CANDIDATES_OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(CANDIDATES_OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main())
