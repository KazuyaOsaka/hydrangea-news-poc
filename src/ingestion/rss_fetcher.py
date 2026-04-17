"""RSS フィード取得モジュール。
sources.yaml を読み込み、有効なソースの RSS を取得して data/raw/ に保存する。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from time import mktime
from typing import Any

import feedparser
import yaml

from src.shared.logger import get_logger

logger = get_logger(__name__)

DEFAULT_SOURCES = Path("configs/sources.yaml")
DEFAULT_RAW_DIR = Path("data/raw")


def load_sources(sources_path: str | Path = DEFAULT_SOURCES) -> list[dict]:
    """sources.yaml を読み込み、enabled なソースのみ返す。"""
    with open(sources_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [s for s in data["sources"] if s.get("enabled", True)]


def _serialize_entry(entry: Any) -> dict:
    """feedparser エントリを JSON シリアライズ可能な dict に変換する。"""
    # published_parsed (struct_time) があれば ISO 文字列に変換
    published = ""
    if entry.get("published_parsed"):
        try:
            dt = datetime.fromtimestamp(mktime(entry["published_parsed"]), tz=timezone.utc)
            published = dt.isoformat()
        except Exception:
            published = entry.get("published", "")
    else:
        published = entry.get("published", entry.get("updated", ""))

    return {
        "title": entry.get("title", ""),
        "summary": entry.get("summary", entry.get("description", "")),
        "link": entry.get("link", ""),
        "published": published,
        "tags": [{"term": t.get("term", "")} for t in entry.get("tags", [])],
    }


def fetch_source(source: dict) -> dict:
    """単一ソースの RSS を取得してデータを返す。失敗時は entries=[] で返す。"""
    name = source["name"]
    url = source["rss_url"]
    logger.info(f"Fetching {name} ({url})")
    try:
        feed = feedparser.parse(url)
        entries = [_serialize_entry(e) for e in feed.entries]
        http_status = getattr(feed, "status", "N/A")
        if not entries:
            logger.warning(
                f"  → {name}: 0 entries (HTTP status={http_status}) — "
                "feed URL が無効・廃止済みの可能性があります。sources.yaml を確認してください。"
            )
        else:
            logger.info(f"  → {name}: {len(entries)} entries (HTTP status={http_status})")
        if feed.get("bozo"):
            bozo_exc = str(feed.get("bozo_exception", ""))
            logger.debug(f"  → {name}: bozo flag (parse warning): {bozo_exc[:120]}")
    except Exception as exc:
        logger.warning(f"  → Failed to fetch {name}: {exc}")
        entries = []

    return {
        "source_name": source["name"],
        "country": source["country"],
        "category": source["category"],
        "language": source.get("language", "en"),
        "region": source.get("region", "global"),
        "source_type": source.get("source_type", "news"),
        "bridge_source": source.get("bridge_source", False),
        "rss_url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "feed_title": "",
        "entries": entries,
    }


def fetch_all(
    sources_path: str | Path = DEFAULT_SOURCES,
    raw_dir: Path = DEFAULT_RAW_DIR,
) -> list[Path]:
    """有効な全ソースを取得し、raw_dir に JSON で保存。保存したパスの一覧を返す。"""
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    sources = load_sources(sources_path)
    saved: list[Path] = []
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    for source in sources:
        raw_data = fetch_source(source)
        fname = f"{source['name'].lower()}_{timestamp}.json"
        path = raw_dir / fname
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved raw: {path}")
        saved.append(path)

    return saved
