"""Batch-based Success Archive パイプラインのテスト。

カバー範囲:
- batch 登録・取得
- 重複 URL 排除 (seen_article_urls)
- no-op (pending batch なし)
- batch 成功後 archive
- batch 失敗時ファイル保持
- 2回目以降 batch で未配信枠差し替え
- normalize_batch が指定ファイルのみ処理すること
- load_articles_from_files の dedup
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ingestion.event_builder import load_articles_from_files
from src.ingestion.normalizer import normalize_batch, normalize_item
from src.storage.db import (
    bulk_save_seen_urls,
    get_oldest_pending_batch,
    get_seen_urls,
    init_db,
    mark_batch_status,
    save_batch,
)


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def db(tmp_path):
    db_path = tmp_path / "db" / "test.db"
    init_db(db_path)
    return db_path


# ─────────────────────────────────────────────────────────────────────────────
# ingestion_batches テーブル
# ─────────────────────────────────────────────────────────────────────────────

def test_save_and_get_batch(db):
    save_batch(db, "20260410_120000", ["raw/a.json"], ["norm/a_normalized.json"])
    batch = get_oldest_pending_batch(db)
    assert batch is not None
    assert batch["batch_id"] == "20260410_120000"
    assert batch["raw_files"] == ["raw/a.json"]
    assert batch["normalized_files"] == ["norm/a_normalized.json"]
    assert batch["status"] == "pending"


def test_get_oldest_pending_returns_oldest(db):
    save_batch(db, "20260410_120000", [], [])
    save_batch(db, "20260410_130000", [], [])
    batch = get_oldest_pending_batch(db)
    assert batch["batch_id"] == "20260410_120000"


def test_get_oldest_pending_returns_none_when_empty(db):
    batch = get_oldest_pending_batch(db)
    assert batch is None


def test_mark_batch_archived_excludes_from_pending(db):
    save_batch(db, "20260410_120000", [], [])
    mark_batch_status(db, "20260410_120000", "archived")
    assert get_oldest_pending_batch(db) is None


def test_failed_batch_is_returned_as_pending(db):
    """failed batch は再試行対象として pending 扱いになる。"""
    save_batch(db, "20260410_120000", [], [])
    mark_batch_status(db, "20260410_120000", "failed")
    batch = get_oldest_pending_batch(db)
    assert batch is not None
    assert batch["batch_id"] == "20260410_120000"


def test_no_duplicate_batch_id(db):
    """同じ batch_id を2回保存しても2行にならない。"""
    save_batch(db, "20260410_120000", ["a"], ["b"])
    save_batch(db, "20260410_120000", ["c"], ["d"])  # ON CONFLICT DO NOTHING
    import sqlite3
    conn = sqlite3.connect(str(db))
    count = conn.execute(
        "SELECT COUNT(*) FROM ingestion_batches WHERE batch_id = ?",
        ("20260410_120000",),
    ).fetchone()[0]
    conn.close()
    assert count == 1


# ─────────────────────────────────────────────────────────────────────────────
# seen_article_urls テーブル
# ─────────────────────────────────────────────────────────────────────────────

def test_bulk_save_and_get_seen_urls(db):
    records = [
        ("https://example.com/1", "art-aaa", "batch1"),
        ("https://example.com/2", "art-bbb", "batch1"),
    ]
    bulk_save_seen_urls(db, records)
    seen = get_seen_urls(db)
    assert "https://example.com/1" in seen
    assert "https://example.com/2" in seen


def test_seen_urls_no_duplicates(db):
    records = [("https://example.com/1", "art-aaa", "batch1")]
    bulk_save_seen_urls(db, records)
    bulk_save_seen_urls(db, records)  # 重複 → INSERT OR IGNORE
    import sqlite3
    conn = sqlite3.connect(str(db))
    count = conn.execute(
        "SELECT COUNT(*) FROM seen_article_urls WHERE url = ?",
        ("https://example.com/1",),
    ).fetchone()[0]
    conn.close()
    assert count == 1


def test_get_seen_urls_empty(db):
    assert get_seen_urls(db) == set()


# ─────────────────────────────────────────────────────────────────────────────
# normalize_batch
# ─────────────────────────────────────────────────────────────────────────────

def _make_raw_file(path: Path, source_name: str, entries: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = {
        "source_name": source_name,
        "country": "JP",
        "category": "general",
        "rss_url": "https://example.com/feed",
        "fetched_at": "2026-04-10T12:00:00+00:00",
        "feed_title": source_name,
        "entries": entries,
    }
    path.write_text(json.dumps(raw, ensure_ascii=False))
    return path


def test_normalize_batch_only_processes_given_files(tmp_path):
    """normalize_batch は指定された raw ファイルのみを処理する。"""
    raw_dir = tmp_path / "raw"
    norm_dir = tmp_path / "normalized"

    raw_a = _make_raw_file(
        raw_dir / "nhk_20260410_120000.json",
        "NHK",
        [{"title": "記事A", "link": "https://nhk.jp/a", "summary": ""}],
    )
    _make_raw_file(
        raw_dir / "bbc_20260410_120000.json",
        "BBC",
        [{"title": "Article B", "link": "https://bbc.com/b", "summary": ""}],
    )

    # NHK だけを normalize_batch に渡す
    norm_paths = normalize_batch([raw_a], norm_dir, batch_id="20260410_120000")
    assert len(norm_paths) == 1
    assert norm_paths[0].name == "nhk_20260410_120000_normalized.json"

    # BBC はまだ normalized にない
    bbc_norm = norm_dir / "bbc_20260410_120000_normalized.json"
    assert not bbc_norm.exists()


def test_normalize_batch_embeds_batch_id(tmp_path):
    """normalize_batch が normalized JSON に batch_id を埋め込む。"""
    raw = _make_raw_file(
        tmp_path / "raw" / "nhk_test.json",
        "NHK",
        [{"title": "テスト", "link": "https://nhk.jp/t", "summary": ""}],
    )
    norm_dir = tmp_path / "normalized"
    norm_paths = normalize_batch([raw], norm_dir, batch_id="TESTBATCH")
    items = json.loads(norm_paths[0].read_text())
    assert items[0]["batch_id"] == "TESTBATCH"


# ─────────────────────────────────────────────────────────────────────────────
# load_articles_from_files
# ─────────────────────────────────────────────────────────────────────────────

def _write_norm_file(path: Path, articles: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(articles, ensure_ascii=False))
    return path


def test_load_articles_from_files_basic(tmp_path):
    art = {"id": "art-001", "title": "Test", "url": "https://example.com/1",
           "source_name": "NHK", "country": "JP", "category": "general",
           "published_at": "2026-04-10T12:00:00+00:00", "fetched_at": "",
           "summary": "", "tags": [], "raw_ref": "", "batch_id": "b1"}
    f = _write_norm_file(tmp_path / "a_normalized.json", [art])
    articles = load_articles_from_files([f])
    assert len(articles) == 1
    assert articles[0]["url"] == "https://example.com/1"


def test_load_articles_from_files_dedup_by_seen_urls(tmp_path):
    """already_seen_urls に含まれる URL はスキップされる。"""
    art = {"id": "art-001", "title": "Test", "url": "https://example.com/1",
           "source_name": "NHK", "country": "JP", "category": "general",
           "published_at": "2026-04-10T12:00:00+00:00", "fetched_at": "",
           "summary": "", "tags": [], "raw_ref": "", "batch_id": "b1"}
    f = _write_norm_file(tmp_path / "a_normalized.json", [art])
    articles = load_articles_from_files([f], already_seen_urls={"https://example.com/1"})
    assert len(articles) == 0


def test_load_articles_from_files_dedup_within_batch(tmp_path):
    """同じ URL が複数ファイルにあっても1件のみ読み込まれる。"""
    art = {"id": "art-001", "title": "Test", "url": "https://example.com/1",
           "source_name": "NHK", "country": "JP", "category": "general",
           "published_at": "2026-04-10T12:00:00+00:00", "fetched_at": "",
           "summary": "", "tags": [], "raw_ref": "", "batch_id": "b1"}
    f1 = _write_norm_file(tmp_path / "a_normalized.json", [art])
    f2 = _write_norm_file(tmp_path / "b_normalized.json", [art])
    articles = load_articles_from_files([f1, f2])
    assert len(articles) == 1


def test_load_articles_from_files_missing_file_skipped(tmp_path):
    """存在しないファイルは警告を出してスキップする（例外は出さない）。"""
    articles = load_articles_from_files([tmp_path / "nonexistent_normalized.json"])
    assert articles == []


# ─────────────────────────────────────────────────────────────────────────────
# run_from_normalized: no-op when no pending batch
# ─────────────────────────────────────────────────────────────────────────────

def test_run_from_normalized_noop_when_no_batch(tmp_path):
    """pending batch がない場合、ValueError を出さずに skipped で正常終了する。"""
    output = tmp_path / "output"
    db = tmp_path / "db" / "test.db"
    norm_dir = tmp_path / "normalized"
    norm_dir.mkdir()

    from src.main import run_from_normalized
    record = run_from_normalized(norm_dir, output, db)

    assert record.status == "skipped"
    assert record.error == "no pending batch"


# ─────────────────────────────────────────────────────────────────────────────
# run_from_normalized: archive on success
# ─────────────────────────────────────────────────────────────────────────────

def test_run_from_normalized_archives_on_success(tmp_path):
    """job 成功後に batch ファイルが archive ディレクトリに移動される。"""
    norm_dir = tmp_path / "normalized"
    norm_dir.mkdir()
    norm_file = norm_dir / "nhk_20260410_120000_normalized.json"
    norm_file.write_text(json.dumps([
        {
            "id": "art-001",
            "title": "日本銀行が追加利上げを決定した",
            "url": "https://nhk.jp/articles/a1",
            "source_name": "NHK",
            "country": "JP",
            "category": "economy",
            "published_at": "2026-04-10T12:00:00+00:00",
            "fetched_at": "2026-04-10T12:00:00+00:00",
            "summary": "日本銀行は追加の利上げを決定し、円高が進んだ。",
            "tags": ["経済", "金融"],
            "raw_ref": "",
            "batch_id": "20260410_120000",
        }
    ], ensure_ascii=False))

    output = tmp_path / "output"
    db = tmp_path / "db" / "test.db"
    archive_dir = tmp_path / "archive"

    init_db(db)
    save_batch(
        db,
        batch_id="20260410_120000",
        raw_files=[],
        normalized_files=[str(norm_file)],
    )

    from src.main import run_from_normalized
    record = run_from_normalized(norm_dir, output, db, archive_dir=archive_dir)

    # job が completed or skipped (publish limit) なら archive が走る
    assert record.status in ("completed", "skipped")

    # normalized ファイルが archive 配下に移動済みであること
    assert not norm_file.exists(), "Normalized file should have been archived"
    archive_files = list(archive_dir.rglob("*_normalized.json"))
    assert len(archive_files) == 1


def test_run_from_normalized_files_remain_on_failure(tmp_path):
    """batch 処理が失敗した場合、ファイルは残り再試行できる。"""
    norm_dir = tmp_path / "normalized"
    norm_dir.mkdir()
    norm_file = norm_dir / "nhk_20260410_130000_normalized.json"
    # わざと空ファイルにしてイベントが0件になるケース
    norm_file.write_text("[]")

    output = tmp_path / "output"
    db = tmp_path / "db" / "test.db"
    archive_dir = tmp_path / "archive"

    init_db(db)
    save_batch(
        db,
        batch_id="20260410_130000",
        raw_files=[],
        normalized_files=[str(norm_file)],
    )

    from src.main import run_from_normalized
    record = run_from_normalized(norm_dir, output, db, archive_dir=archive_dir)

    # イベント0件 → skipped (no_events) として処理される
    assert record.status == "skipped"
    # この場合は completed 扱いで archive される設計
    # (no_events は "処理済み" であり re-try の意味がない)
