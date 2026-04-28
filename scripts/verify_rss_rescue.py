"""
F-8-PRE-2: F-8-PRE で FAILED した媒体の代替 URL 検証スクリプト。

Google News RSS 経由など代替手段で再検証する。
結果を docs/MEDIA_RSS_RESCUE.md (人間可読) と
docs/MEDIA_RSS_RESCUE_RESULT.json (機械可読) に書き出す。

Usage:
    python -m scripts.verify_rss_rescue
"""
from __future__ import annotations
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import feedparser


CANDIDATES_INPUT = Path("docs/MEDIA_RSS_CANDIDATES_RESCUE_INPUT.yaml")
RESCUE_OUTPUT_MD = Path("docs/MEDIA_RSS_RESCUE.md")
RESCUE_OUTPUT_JSON = Path("docs/MEDIA_RSS_RESCUE_RESULT.json")
TIMEOUT_SEC = 30


@dataclass
class RescueResult:
    name: str
    candidates: list[str]
    notes: Optional[str] = None
    original_url: Optional[str] = None
    failure_reason: Optional[str] = None
    successful_url: Optional[str] = None
    entry_count: int = 0
    latest_entry_date: Optional[str] = None
    feed_title: Optional[str] = None
    error: Optional[str] = None
    elapsed_sec: float = 0.0
    is_google_news_proxy: bool = False

    @property
    def status(self) -> str:
        if self.successful_url:
            if self.entry_count >= 5:
                return "RESCUED"
            elif self.entry_count >= 1:
                return "RESCUED_LOW_VOLUME"
            else:
                return "EMPTY"
        return "STILL_FAILED"


def verify_single_url(url: str) -> tuple[bool, dict]:
    """1つの URL を検証し、(成功, 詳細) を返す。"""
    try:
        start = time.time()
        feed = feedparser.parse(
            url,
            request_headers={"User-Agent": "Mozilla/5.0 (Hydrangea-RSS-Rescue/0.1)"},
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


def verify_rescue_candidate(
    name: str,
    candidates: list[str],
    notes: Optional[str] = None,
    original_url: Optional[str] = None,
    failure_reason: Optional[str] = None,
) -> RescueResult:
    """1媒体の救済候補 URL リストを順次試行。"""
    result = RescueResult(
        name=name,
        candidates=candidates,
        notes=notes,
        original_url=original_url,
        failure_reason=failure_reason,
    )

    for url in candidates:
        is_google_news = "news.google.com" in url
        proxy_label = " (Google News)" if is_google_news else ""
        print(f"  [{name}]{proxy_label} Trying: {url[:100]}")
        success, detail = verify_single_url(url)
        result.elapsed_sec += detail.get("elapsed_sec", 0.0)

        if success:
            result.successful_url = url
            result.entry_count = detail["entry_count"]
            result.latest_entry_date = detail.get("latest_entry")
            result.feed_title = detail.get("feed_title", "unknown")[:80]
            result.is_google_news_proxy = is_google_news
            print(f"    -> RESCUED ({result.entry_count} entries, '{result.feed_title}')")
            return result
        else:
            print(f"    -> FAILED: {detail.get('error', 'unknown')[:80]}")

    result.error = "all_rescue_candidates_failed"
    return result


def main() -> int:
    """救済対象を全検証し、結果を出力。"""
    import yaml

    if not CANDIDATES_INPUT.exists():
        print(f"ERROR: {CANDIDATES_INPUT} が見つかりません")
        return 1

    with open(CANDIDATES_INPUT, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    results: list[RescueResult] = []

    print("=== F-8-PRE-2: 救済対象の再検証 ===")
    for entry in config.get("rescue_candidates", []):
        result = verify_rescue_candidate(
            name=entry["name"],
            candidates=entry["candidates"],
            notes=entry.get("notes"),
            original_url=entry.get("original_url"),
            failure_reason=entry.get("failure_reason"),
        )
        results.append(result)

    # JSON 出力
    json_data = []
    for r in results:
        json_data.append({
            "name": r.name,
            "status": r.status,
            "successful_url": r.successful_url,
            "is_google_news_proxy": r.is_google_news_proxy,
            "entry_count": r.entry_count,
            "latest_entry_date": r.latest_entry_date,
            "feed_title": r.feed_title,
            "notes": r.notes,
            "original_url": r.original_url,
            "failure_reason": r.failure_reason,
            "error": r.error,
            "elapsed_sec": round(r.elapsed_sec, 2),
        })

    RESCUE_OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(RESCUE_OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    # Markdown レポート出力
    write_markdown_report(results)

    # サマリ表示
    rescued = sum(1 for r in results if r.status == "RESCUED")
    rescued_low = sum(1 for r in results if r.status == "RESCUED_LOW_VOLUME")
    empty = sum(1 for r in results if r.status == "EMPTY")
    still_failed = sum(1 for r in results if r.status == "STILL_FAILED")

    print(f"\n=== Summary ===")
    print(f"  RESCUED            : {rescued}/{len(results)}")
    print(f"  RESCUED_LOW_VOLUME : {rescued_low}/{len(results)}")
    print(f"  EMPTY              : {empty}/{len(results)}")
    print(f"  STILL_FAILED       : {still_failed}/{len(results)}")
    print(f"\nReports:")
    print(f"  - {RESCUE_OUTPUT_MD}")
    print(f"  - {RESCUE_OUTPUT_JSON}")

    return 0


def write_markdown_report(results: list[RescueResult]) -> None:
    """救済結果を Markdown で出力。"""
    lines = [
        "# Hydrangea — RSS Media Rescue Verification (F-8-PRE-2)",
        "",
        "F-8-PRE で FAILED した媒体の代替 URL を検証した結果。",
        "Google News RSS 経由を中心に救済を試みた。",
        "",
        f"検証日: {time.strftime('%Y-%m-%d')}",
        "",
        "## 凡例",
        "",
        "| Status | 意味 |",
        "|---|---|",
        "| RESCUED | 5件以上のエントリ取得成功 → 本番投入推奨 |",
        "| RESCUED_LOW_VOLUME | 1〜4件取得 → 投入可能だが要監視 |",
        "| EMPTY | 接続成功だがエントリ0 → 要再調査 |",
        "| STILL_FAILED | 代替 URL でも全失敗 → 一旦除外 |",
        "",
        "## 救済結果",
        "",
        "| Name | Status | Entries | URL Type | URL |",
        "|---|---|---|---|---|",
    ]

    for r in results:
        url = (r.successful_url or "—")[:60]
        url_type = "Google News" if r.is_google_news_proxy else ("Direct" if r.successful_url else "—")
        lines.append(f"| {r.name} | {r.status} | {r.entry_count} | {url_type} | {url} |")

    lines.extend([
        "",
        "## 救済成功 (RESCUED)",
        "",
    ])
    rescued = [r for r in results if r.status in ("RESCUED", "RESCUED_LOW_VOLUME")]
    if not rescued:
        lines.append("なし")
    else:
        for r in rescued:
            lines.append(f"### {r.name}")
            lines.append(f"- **Original URL** (FAILED): `{r.original_url}`")
            lines.append(f"  - Failure reason: {r.failure_reason or '—'}")
            lines.append(f"- **Rescued URL** ({r.status}): `{r.successful_url}`")
            lines.append(f"  - Type: {'Google News proxy' if r.is_google_news_proxy else 'Direct RSS'}")
            lines.append(f"  - Entries: {r.entry_count}, Latest: {r.latest_entry_date or '—'}")
            lines.append(f"  - Notes: {r.notes or '—'}")
            lines.append("")

    lines.extend([
        "",
        "## 依然失敗 (STILL_FAILED)",
        "",
    ])
    still_failed = [r for r in results if r.status == "STILL_FAILED"]
    if not still_failed:
        lines.append("なし — 全媒体救済成功！")
    else:
        for r in still_failed:
            lines.append(f"### {r.name}")
            lines.append(f"- **Original URL** (FAILED): `{r.original_url}`")
            lines.append(f"- 試行した代替 URL:")
            for url in r.candidates:
                lines.append(f"  - `{url}`")
            lines.append(f"- 結論: F-8-1 では除外、別媒体で代替検討")
            lines.append("")

    lines.extend([
        "",
        "## F-8-1 (本番投入) への引継ぎ",
        "",
        "### 救済成功で F-8-1 に追加する媒体",
        "",
    ])
    for r in rescued:
        proxy_note = " (via Google News)" if r.is_google_news_proxy else ""
        lines.append(f"- {r.name}{proxy_note}: `{r.successful_url}`")

    lines.extend([
        "",
        "### F-8-1 で除外する媒体 (依然失敗)",
        "",
    ])
    if not still_failed:
        lines.append("なし")
    else:
        for r in still_failed:
            lines.append(f"- {r.name}: 別媒体で代替検討、または将来の F-8-PRE-3 で再調査")

    lines.extend([
        "",
        "---",
        f"*Generated by `scripts/verify_rss_rescue.py` at {time.strftime('%Y-%m-%d %H:%M:%S')}*",
    ])

    RESCUE_OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(RESCUE_OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main())
