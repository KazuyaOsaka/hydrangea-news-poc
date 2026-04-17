"""正規化モジュール。
data/raw/ の JSON を読み込み、共通スキーマに変換して data/normalized/ に保存する。

正規化後のスキーマ（1 記事 = 1 オブジェクト）:
  id           : "art-" + URL の SHA-256 先頭 12 文字
  title        : 記事タイトル
  summary      : 記事要約（HTML タグ除去済み）
  url          : 記事 URL
  source_name  : 媒体名（例: "NHK"）
  country      : 国コード（例: "JP", "Global"）
  category     : カテゴリ（例: "economy"）
  published_at : 公開日時（ISO 8601）
  fetched_at   : 取得日時（ISO 8601）
  tags         : タグ文字列のリスト
  raw_ref      : 元の raw ファイルパス（文字列）
  batch_id     : 取り込みバッチID（例: "20260410_120000"）省略時は空文字
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from src.shared.logger import get_logger

logger = get_logger(__name__)

DEFAULT_NORMALIZED_DIR = Path("data/normalized")


def _strip_html(text: str) -> str:
    """最低限の HTML タグ除去。"""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _parse_date(date_str: str | None) -> str:
    """RFC 2822 / ISO 8601 / 不明 → ISO 8601 文字列。失敗時は現在時刻。"""
    if not date_str:
        return datetime.now(timezone.utc).isoformat()
    # RFC 2822 (Mon, 31 Mar 2026 12:00:00 +0000)
    try:
        return parsedate_to_datetime(date_str).isoformat()
    except Exception:
        pass
    # ISO 8601
    try:
        return datetime.fromisoformat(date_str).isoformat()
    except Exception:
        pass
    return datetime.now(timezone.utc).isoformat()


def _make_id(url: str) -> str:
    return "art-" + hashlib.sha256(url.encode()).hexdigest()[:12]


def normalize_item(
    entry: dict,
    source_meta: dict,
    raw_ref: str = "",
    batch_id: str = "",
) -> dict:
    """feedparser エントリ 1 件を正規化スキーマに変換する。"""
    url = entry.get("link", "")
    uid = _make_id(url) if url else _make_id(entry.get("title", ""))
    return {
        "id": uid,
        "title": _strip_html(entry.get("title", "")),
        "summary": _strip_html(entry.get("summary", entry.get("description", ""))),
        "url": url,
        "source_name": source_meta["source_name"],
        "country": source_meta["country"],
        "category": source_meta["category"],
        "language": source_meta.get("language", "en"),
        "region": source_meta.get("region", "global"),
        "published_at": _parse_date(entry.get("published")),
        "fetched_at": source_meta["fetched_at"],
        "tags": [t.get("term", "") for t in entry.get("tags", [])],
        "raw_ref": raw_ref,
        "batch_id": batch_id,
    }


def normalize_raw_file(
    raw_path: Path,
    normalized_dir: Path = DEFAULT_NORMALIZED_DIR,
    batch_id: str = "",
) -> Path:
    """raw JSON 1 ファイルを正規化して normalized_dir に保存し、出力パスを返す。"""
    normalized_dir = Path(normalized_dir)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    with open(raw_path, encoding="utf-8") as f:
        raw_data = json.load(f)

    source_meta = {
        "source_name": raw_data["source_name"],
        "country": raw_data["country"],
        "category": raw_data["category"],
        "fetched_at": raw_data["fetched_at"],
        "language": raw_data.get("language", "en"),
        "region": raw_data.get("region", "global"),
    }

    items = [
        normalize_item(e, source_meta, raw_ref=str(raw_path), batch_id=batch_id)
        for e in raw_data.get("entries", [])
    ]

    out_name = raw_path.stem + "_normalized.json"
    out_path = normalized_dir / out_name
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    src_name = source_meta.get("source_name", raw_path.stem)
    logger.info(f"Normalized {len(items)} items [{src_name}] → {out_path}")
    return out_path


def normalize_batch(
    raw_paths: list[Path],
    normalized_dir: Path = DEFAULT_NORMALIZED_DIR,
    batch_id: str = "",
) -> list[Path]:
    """指定された raw ファイルのみを正規化する（batch 単位）。

    normalize_all() とは異なり、ディレクトリ全体をスキャンせず
    この batch で取得した raw_paths のみを処理する。
    """
    normalized_dir = Path(normalized_dir)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    results: list[Path] = []
    source_totals: dict[str, int] = {}

    for p in raw_paths:
        try:
            out = normalize_raw_file(p, normalized_dir, batch_id=batch_id)
            results.append(out)
            items = json.loads(out.read_text(encoding="utf-8"))
            if items:
                src = items[0].get("source_name", p.stem)
                source_totals[src] = source_totals.get(src, 0) + len(items)
        except Exception as exc:
            logger.warning(f"Failed to normalize {p}: {exc}")

    if source_totals:
        logger.info(f"=== Batch {batch_id} Normalization Summary ===")
        for src, cnt in sorted(source_totals.items()):
            logger.info(f"  {src:20} → {cnt:3} articles")

    return results


def normalize_all(
    raw_dir: Path = Path("data/raw"),
    normalized_dir: Path = DEFAULT_NORMALIZED_DIR,
) -> list[Path]:
    """raw_dir 内の全 JSON を正規化する（後方互換用。新規コードは normalize_batch を使うこと）。"""
    raw_dir = Path(raw_dir)
    if not raw_dir.exists():
        logger.warning(f"raw_dir not found: {raw_dir}")
        return []
    paths = sorted(raw_dir.glob("*.json"))
    results: list[Path] = []
    source_totals: dict[str, int] = {}
    for p in paths:
        try:
            out = normalize_raw_file(p, normalized_dir)
            results.append(out)
            # 出力ファイルから source 別件数を集計
            items = json.loads(out.read_text(encoding="utf-8"))
            if items:
                src = items[0].get("source_name", p.stem)
                source_totals[src] = source_totals.get(src, 0) + len(items)
        except Exception as exc:
            logger.warning(f"Failed to normalize {p}: {exc}")

    if source_totals:
        logger.info("=== Normalization Summary (source別) ===")
        for src, cnt in sorted(source_totals.items()):
            logger.info(f"  {src:20} → {cnt:3} articles")

    return results
