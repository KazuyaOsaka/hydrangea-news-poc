"""CLI エントリポイント: RSS 取得 → 正規化 JSON 書き出し。

Batch-based ingestion: 1 回の実行ごとに一意の batch_id を発行し、
その回で取得した raw / normalized ファイルのみを対象にする。
過去の raw 全体を毎回スキャンしない。

使い方:
    python -m src.ingestion.run_ingestion
    python -m src.ingestion.run_ingestion --sources configs/sources.yaml
    python -m src.ingestion.run_ingestion --raw-dir data/raw --normalized-dir data/normalized
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.ingestion.normalizer import normalize_batch
from src.ingestion.rss_fetcher import fetch_all
from src.shared.config import DB_PATH
from src.shared.logger import get_logger
from src.storage.db import (
    bulk_save_seen_urls,
    get_seen_urls,
    init_db,
    save_batch,
)

logger = get_logger(__name__)


def _build_source_stats(raw_paths: list[Path], norm_paths: list[Path]) -> dict[str, dict]:
    """raw / normalized ファイルから source 別の件数を集計する。"""
    source_stats: dict[str, dict] = {}

    for p in raw_paths:
        try:
            d = json.loads(Path(p).read_text(encoding="utf-8"))
            name = d.get("source_name", p.stem)
            source_stats[name] = {
                "fetched": len(d.get("entries", [])),
                "normalized": 0,
            }
        except Exception:
            pass

    for p in norm_paths:
        try:
            items = json.loads(Path(p).read_text(encoding="utf-8"))
            if items:
                name = items[0].get("source_name", "")
                if name not in source_stats:
                    source_stats[name] = {"fetched": 0, "normalized": 0}
                source_stats[name]["normalized"] += len(items)
        except Exception:
            pass

    return source_stats


def run(
    sources_path: str = "configs/sources.yaml",
    raw_dir: str = "data/raw",
    normalized_dir: str = "data/normalized",
    db_path: Path | None = None,
) -> dict:
    if db_path is None:
        db_path = DB_PATH
    db_path = Path(db_path)

    # DB 初期化（ingestion_batches / seen_article_urls テーブルを含む）
    init_db(db_path)

    # batch_id: YYYYMMDD_HHMMSS
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    logger.info(f"[Batch] Starting ingestion batch_id={batch_id}")

    # 1. RSS 取得 (この実行分だけ)
    raw_paths = fetch_all(sources_path, Path(raw_dir))
    logger.info(f"[Batch] Fetched {len(raw_paths)} source file(s)")

    if not raw_paths:
        logger.warning("[Batch] No raw files fetched. Skipping normalization.")
        return {
            "batch_id": batch_id,
            "raw": [],
            "normalized": [],
            "source_stats": {},
            "new_articles": 0,
            "skipped_duplicates": 0,
        }

    # 2. この batch の raw ファイルだけを正規化
    norm_paths = normalize_batch(
        raw_paths=[Path(p) for p in raw_paths],
        normalized_dir=Path(normalized_dir),
        batch_id=batch_id,
    )
    logger.info(f"[Batch] Normalized {len(norm_paths)} file(s)")

    # 3. URL 重複ガード: DB の seen_urls と照合
    seen_urls = get_seen_urls(db_path)
    new_url_records: list[tuple[str, str, str]] = []
    new_article_count = 0
    skipped_count = 0

    for p in norm_paths:
        try:
            items = json.loads(Path(p).read_text(encoding="utf-8"))
            for item in items:
                url = item.get("url", "")
                art_id = item.get("id", "")
                if not url:
                    new_article_count += 1
                    continue
                if url in seen_urls:
                    skipped_count += 1
                    logger.debug(f"[Dedup] Skipping already-seen URL: {url[:80]}")
                else:
                    seen_urls.add(url)
                    new_url_records.append((url, art_id, batch_id))
                    new_article_count += 1
        except Exception as exc:
            logger.warning(f"[Dedup] Failed to read {p} for dedup: {exc}")

    logger.info(
        f"[Batch] Articles: {new_article_count} new, {skipped_count} duplicate(s) skipped"
    )

    # 4. batch を DB に登録
    save_batch(
        db_path=db_path,
        batch_id=batch_id,
        raw_files=[str(p) for p in raw_paths],
        normalized_files=[str(p) for p in norm_paths],
    )

    # 5. 新着 URL を seen_article_urls に保存（次回以降の重複排除用）
    bulk_save_seen_urls(db_path, new_url_records)

    # Source 別取得・正規化件数サマリ
    source_stats = _build_source_stats(raw_paths, norm_paths)
    logger.info("=== Source Ingestion Summary ===")
    for name in sorted(source_stats):
        fc = source_stats[name]["fetched"]
        nc = source_stats[name]["normalized"]
        status = "EMPTY" if fc == 0 else "OK"
        if fc == 0:
            logger.warning(f"  {name:20}  fetched={fc:3}  normalized={nc:3}  [{status}]")
        else:
            logger.info(f"  {name:20}  fetched={fc:3}  normalized={nc:3}  [{status}]")

    return {
        "batch_id": batch_id,
        "raw": raw_paths,
        "normalized": norm_paths,
        "source_stats": source_stats,
        "new_articles": new_article_count,
        "skipped_duplicates": skipped_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch RSS and normalize to JSON (batch-based)")
    parser.add_argument("--sources", default="configs/sources.yaml", help="sources.yaml のパス")
    parser.add_argument("--raw-dir", default="data/raw", help="raw JSON 保存先")
    parser.add_argument("--normalized-dir", default="data/normalized", help="正規化 JSON 保存先")
    parser.add_argument("--db", default=None, help="SQLite DB パス (省略時はデフォルト)")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else None
    result = run(args.sources, args.raw_dir, args.normalized_dir, db_path=db_path)
    print(
        f"\n完了: batch_id={result['batch_id']}, "
        f"raw={len(result['raw'])} files, "
        f"normalized={len(result['normalized'])} files, "
        f"new={result['new_articles']}, "
        f"skipped_duplicates={result['skipped_duplicates']}"
    )


if __name__ == "__main__":
    main()
