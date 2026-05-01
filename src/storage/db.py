from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from src.shared.logger import get_logger
from src.shared.models import JobRecord, RecencyRecord

logger = get_logger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
    id                 TEXT PRIMARY KEY,
    event_id           TEXT NOT NULL,
    status             TEXT NOT NULL,
    script_path        TEXT,
    article_path       TEXT,
    video_payload_path TEXT,
    created_at         TEXT NOT NULL,
    error              TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    category     TEXT NOT NULL,
    source       TEXT NOT NULL,
    published_at TEXT NOT NULL,
    summary      TEXT,
    tags         TEXT
);

CREATE TABLE IF NOT EXISTS daily_stats (
    date          TEXT PRIMARY KEY,
    llm_calls     INTEGER NOT NULL DEFAULT 0,
    run_count     INTEGER NOT NULL DEFAULT 0,
    publish_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ingestion_batches (
    batch_id         TEXT PRIMARY KEY,
    created_at       TEXT NOT NULL,
    raw_files        TEXT NOT NULL DEFAULT '[]',
    normalized_files TEXT NOT NULL DEFAULT '[]',
    status           TEXT NOT NULL DEFAULT 'pending',
    processed_at     TEXT,
    archived_at      TEXT
);

CREATE TABLE IF NOT EXISTS seen_article_urls (
    url         TEXT PRIMARY KEY,
    article_id  TEXT NOT NULL,
    batch_id    TEXT NOT NULL,
    ingested_at TEXT NOT NULL
);

-- Rolling comparison window: short-term event pool for time-lag arbitrage.
-- Stores scored-event snapshots from recent batches so that unpublished
-- events from previous batches can compete with current-batch events.
-- Entries expire after 48 h and are cleaned up by expire_old_pool_events().
CREATE TABLE IF NOT EXISTS recent_event_pool (
    event_id          TEXT PRIMARY KEY,
    batch_id          TEXT NOT NULL,
    created_at        TEXT NOT NULL,       -- ISO 8601 UTC; used for freshness decay
    event_snapshot    TEXT NOT NULL,       -- JSON-serialised ScoredEvent
    source_regions    TEXT NOT NULL DEFAULT '[]',   -- JSON list[str]
    source_languages  TEXT NOT NULL DEFAULT '[]',   -- JSON list[str]
    primary_bucket    TEXT NOT NULL DEFAULT 'general',
    appraisal_type    TEXT,
    score             REAL NOT NULL DEFAULT 0.0,
    story_fingerprint TEXT NOT NULL DEFAULT '',
    published         INTEGER NOT NULL DEFAULT 0,   -- 1 = published
    consumed          INTEGER NOT NULL DEFAULT 0,   -- 1 = consumed (selected for schedule)
    expired           INTEGER NOT NULL DEFAULT 0,   -- 1 = expired (> 48 h)
    published_at      TEXT
);

-- 分析レイヤー Recency Guard 用: 投稿成功時の primary_entities/topics を記録。
-- 直近 24h 内に同じ entity/topic を含む候補は -50% 降格される。
CREATE TABLE IF NOT EXISTS recency_records (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id          TEXT NOT NULL,
    channel_id        TEXT NOT NULL,
    primary_entities  TEXT NOT NULL,          -- JSON 配列
    primary_topics    TEXT NOT NULL,          -- JSON 配列
    published_at      TEXT NOT NULL,          -- ISO 8601
    created_at        TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_recency_channel_published
    ON recency_records(channel_id, published_at);

-- F-13.B: 日本の大手メディアでの報道有無 Web 検証結果のキャッシュテーブル。
-- JP ソース 0 件の候補に対して Gemini Grounding (Google Search) を呼び、
-- ホワイトリスト (新聞・テレビ・通信社・主要ビジネスメディア 27 ドメイン) と
-- 除外リスト (Yahoo!ニュース・SNS・個人ブログ等) で照合する。
-- has_jp_coverage = True  → 大手メディア報道あり (divergence パターンで生成)
-- has_jp_coverage = False → 真の blind_spot_global (Hydrangea ミッション本丸)
-- 24h キャッシュで重複検証を抑制する。
CREATE TABLE IF NOT EXISTS jp_coverage_cache (
    event_id         TEXT PRIMARY KEY,
    has_jp_coverage  INTEGER NOT NULL,
    matched_tier     TEXT,
    matched_urls     TEXT,           -- JSON 配列
    matched_domains  TEXT,           -- JSON 配列
    excluded_urls    TEXT,           -- JSON 配列
    search_query     TEXT,
    cached_at        TEXT NOT NULL,  -- ISO 8601
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection configured for concurrent use.

    - journal_mode=WAL: ライターが増えても読み取りが止まらない。
    - busy_timeout=5000: 他接続のロック中は最大5秒 OS レベルで待つ。
      read-modify-write レース（daily_stats increment の多重実行）での
      "database is locked" 例外発生率を下げる。
    - synchronous=NORMAL: WAL と併用して安全かつ高速。
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None にはしない（既存コードは with 文の暗黙 commit に依存）。
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    # PRAGMA 設定は接続ごとに必要（WAL はファイル全体で共有されるが、busy_timeout は接続属性）。
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
    except sqlite3.Error as exc:  # pragma: no cover — WAL 未対応環境向け
        logger.warning(f"[DB] PRAGMA setup failed ({exc}); falling back to default mode.")
    return conn


def init_db(db_path: Path) -> None:
    """テーブルを初期化する。"""
    with _connect(db_path) as conn:
        conn.executescript(_DDL)
    logger.info(f"DB initialized at {db_path}")


def save_job(db_path: Path, record: JobRecord) -> None:
    """JobRecordをDBに保存（upsert）する。"""
    sql = """
    INSERT INTO jobs (id, event_id, status, script_path, article_path,
                      video_payload_path, created_at, error)
    VALUES (:id, :event_id, :status, :script_path, :article_path,
            :video_payload_path, :created_at, :error)
    ON CONFLICT(id) DO UPDATE SET
        status             = excluded.status,
        script_path        = excluded.script_path,
        article_path       = excluded.article_path,
        video_payload_path = excluded.video_payload_path,
        error              = excluded.error
    """
    row = record.model_dump()
    row["created_at"] = record.created_at.isoformat()
    with _connect(db_path) as conn:
        conn.execute(sql, row)
    logger.info(f"Job [{record.id}] saved to DB (status={record.status})")


def list_jobs(db_path: Path) -> list[dict]:
    """保存済みジョブ一覧を返す。"""
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


# ── 日次統計 (daily_stats) ────────────────────────────────────────────────────

def _today() -> str:
    return date.today().isoformat()


def _ensure_daily_row(conn: sqlite3.Connection, today: str) -> None:
    """daily_stats に当日行がなければ INSERT する。"""
    conn.execute(
        "INSERT OR IGNORE INTO daily_stats (date, llm_calls, run_count, publish_count) "
        "VALUES (?, 0, 0, 0)",
        (today,),
    )


def get_daily_stats(db_path: Path, today: str | None = None) -> dict:
    """当日の統計を dict で返す。行がなければ 0 を返す。"""
    if today is None:
        today = _today()
    with _connect(db_path) as conn:
        _ensure_daily_row(conn, today)
        row = conn.execute(
            "SELECT llm_calls, run_count, publish_count FROM daily_stats WHERE date = ?",
            (today,),
        ).fetchone()
    return {
        "date": today,
        "llm_calls": row["llm_calls"],
        "run_count": row["run_count"],
        "publish_count": row["publish_count"],
    }


def increment_daily_llm_calls(db_path: Path, n: int = 1, today: str | None = None) -> None:
    """当日の LLM 呼び出しカウントを n 増やす。"""
    if today is None:
        today = _today()
    with _connect(db_path) as conn:
        _ensure_daily_row(conn, today)
        conn.execute(
            "UPDATE daily_stats SET llm_calls = llm_calls + ? WHERE date = ?",
            (n, today),
        )


def increment_daily_run_count(db_path: Path, today: str | None = None) -> None:
    """当日の実行回数カウントを 1 増やす。"""
    if today is None:
        today = _today()
    with _connect(db_path) as conn:
        _ensure_daily_row(conn, today)
        conn.execute(
            "UPDATE daily_stats SET run_count = run_count + 1 WHERE date = ?",
            (today,),
        )


def increment_daily_publish_count(db_path: Path, today: str | None = None) -> None:
    """当日の公開件数カウントを 1 増やす。"""
    if today is None:
        today = _today()
    with _connect(db_path) as conn:
        _ensure_daily_row(conn, today)
        conn.execute(
            "UPDATE daily_stats SET publish_count = publish_count + 1 WHERE date = ?",
            (today,),
        )


# ── Ingestion Batch 管理 ──────────────────────────────────────────────────────

def save_batch(
    db_path: Path,
    batch_id: str,
    raw_files: list[str],
    normalized_files: list[str],
) -> None:
    """新しい ingestion batch を DB に登録する（status=pending）。"""
    now = datetime.now(timezone.utc).isoformat()
    sql = """
    INSERT INTO ingestion_batches
        (batch_id, created_at, raw_files, normalized_files, status)
    VALUES (?, ?, ?, ?, 'pending')
    ON CONFLICT(batch_id) DO NOTHING
    """
    with _connect(db_path) as conn:
        conn.execute(
            sql,
            (
                batch_id,
                now,
                json.dumps(raw_files, ensure_ascii=False),
                json.dumps(normalized_files, ensure_ascii=False),
            ),
        )
    logger.info(
        f"[Batch] Registered batch {batch_id}: "
        f"{len(raw_files)} raw, {len(normalized_files)} normalized"
    )


def get_oldest_pending_batch(db_path: Path) -> dict | None:
    """最も古い pending または failed batch を返す。なければ None。"""
    sql = """
    SELECT batch_id, created_at, raw_files, normalized_files, status
    FROM ingestion_batches
    WHERE status IN ('pending', 'failed')
    ORDER BY created_at ASC
    LIMIT 1
    """
    with _connect(db_path) as conn:
        row = conn.execute(sql).fetchone()
    if row is None:
        return None
    return {
        "batch_id": row["batch_id"],
        "created_at": row["created_at"],
        "raw_files": json.loads(row["raw_files"]),
        "normalized_files": json.loads(row["normalized_files"]),
        "status": row["status"],
    }


def mark_batch_status(
    db_path: Path,
    batch_id: str,
    status: str,
    *,
    processed_at: str | None = None,
    archived_at: str | None = None,
) -> None:
    """batch のステータスを更新する。"""
    updates = ["status = ?"]
    params: list = [status]
    if processed_at is not None:
        updates.append("processed_at = ?")
        params.append(processed_at)
    if archived_at is not None:
        updates.append("archived_at = ?")
        params.append(archived_at)
    params.append(batch_id)
    sql = f"UPDATE ingestion_batches SET {', '.join(updates)} WHERE batch_id = ?"
    with _connect(db_path) as conn:
        conn.execute(sql, params)
    logger.info(f"[Batch] {batch_id} → status={status}")


# ── URL 重複排除 (seen_article_urls) ─────────────────────────────────────────

def get_seen_urls(db_path: Path) -> set[str]:
    """過去に取り込み済みの URL セットを返す。"""
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT url FROM seen_article_urls").fetchall()
    return {row["url"] for row in rows}


def get_seen_urls_excluding_batch(db_path: Path, exclude_batch_id: str) -> set[str]:
    """指定 batch_id を除いた seen URL セットを返す。

    batch 処理時に「自分自身の batch の URL を除外して」クロスバッチ重複排除するために使う。
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT url FROM seen_article_urls WHERE batch_id != ?",
            (exclude_batch_id,),
        ).fetchall()
    return {row["url"] for row in rows}


def bulk_save_seen_urls(
    db_path: Path,
    records: list[tuple[str, str, str]],
) -> None:
    """(url, article_id, batch_id) のリストを seen_article_urls に保存する（重複は無視）。"""
    if not records:
        return
    now = datetime.now(timezone.utc).isoformat()
    sql = """
    INSERT OR IGNORE INTO seen_article_urls (url, article_id, batch_id, ingested_at)
    VALUES (?, ?, ?, ?)
    """
    rows = [(url, art_id, batch_id, now) for url, art_id, batch_id in records]
    with _connect(db_path) as conn:
        conn.executemany(sql, rows)
    logger.info(f"[Dedup] Saved {len(rows)} seen URLs to DB")


# ── Rolling Comparison Window (recent_event_pool) ─────────────────────────────

def upsert_recent_event_pool(
    db_path: Path,
    entries: list[dict],
) -> None:
    """ScoredEvent スナップショットを recent_event_pool に upsert する。

    Args:
        entries: dicts with keys:
            event_id, batch_id, event_snapshot (JSON str), source_regions (JSON str),
            source_languages (JSON str), primary_bucket, appraisal_type, score,
            story_fingerprint
    """
    if not entries:
        return
    now = datetime.now(timezone.utc).isoformat()
    sql = """
    INSERT INTO recent_event_pool
        (event_id, batch_id, created_at, event_snapshot, source_regions,
         source_languages, primary_bucket, appraisal_type, score,
         story_fingerprint)
    VALUES
        (:event_id, :batch_id, :created_at, :event_snapshot, :source_regions,
         :source_languages, :primary_bucket, :appraisal_type, :score,
         :story_fingerprint)
    ON CONFLICT(event_id) DO UPDATE SET
        event_snapshot    = excluded.event_snapshot,
        source_regions    = excluded.source_regions,
        source_languages  = excluded.source_languages,
        primary_bucket    = excluded.primary_bucket,
        appraisal_type    = excluded.appraisal_type,
        score             = excluded.score,
        story_fingerprint = excluded.story_fingerprint
    """
    rows = [
        {**e, "created_at": e.get("created_at", now)}
        for e in entries
    ]
    with _connect(db_path) as conn:
        conn.executemany(sql, rows)
    logger.info(f"[Pool] Upserted {len(rows)} events into recent_event_pool")


def get_recent_pool_events(
    db_path: Path,
    window_hours: int = 36,
    exclude_batch_id: str | None = None,
) -> list[dict]:
    """直近 window_hours 時間内の未配信・未消化・未期限切れのプールイベントを返す。

    Args:
        window_hours:      取得対象の時間窓（デフォルト 36 h）
        exclude_batch_id:  除外する batch_id（現在の batch を除外するため）

    Returns:
        list of dicts with all pool table columns

    Note:
        Python で cutoff を計算して渡す（SQLite の datetime() は
        ISO 8601 文字列フォーマットと一致しないため）。
    """
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()

    params: list = [cutoff]
    exclude_clause = ""
    if exclude_batch_id:
        exclude_clause = "AND batch_id != ?"
        params.append(exclude_batch_id)

    sql = f"""
    SELECT event_id, batch_id, created_at, event_snapshot,
           source_regions, source_languages, primary_bucket,
           appraisal_type, score, story_fingerprint,
           published, consumed, expired, published_at
    FROM recent_event_pool
    WHERE published = 0
      AND expired   = 0
      AND created_at >= ?
      {exclude_clause}
    ORDER BY score DESC
    """
    with _connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_published_story_fingerprints(
    db_path: Path,
    within_hours: int = 72,
) -> dict[str, dict]:
    """直近 within_hours 時間内に配信済みのストーリーフィンガープリントを返す。

    重複投稿抑制と upgrade 条件チェックに使う。

    Returns:
        {story_fingerprint: {"score": float, "source_regions": list[str],
                             "appraisal_type": str | None}}
    """
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=within_hours)).isoformat()

    sql = """
    SELECT story_fingerprint, score, source_regions, appraisal_type
    FROM recent_event_pool
    WHERE published = 1
      AND story_fingerprint != ''
      AND published_at >= ?
    ORDER BY score DESC
    """
    result: dict[str, dict] = {}
    with _connect(db_path) as conn:
        rows = conn.execute(sql, (cutoff,)).fetchall()
    for row in rows:
        fp = row["story_fingerprint"]
        if fp and fp not in result:
            result[fp] = {
                "score": row["score"],
                "source_regions": json.loads(row["source_regions"] or "[]"),
                "appraisal_type": row["appraisal_type"],
            }
    return result


def mark_pool_event_published(db_path: Path, event_id: str) -> None:
    """recent_event_pool のイベントを配信済みにマークする。

    story_fingerprint が同じ他エントリもまとめて consumed にする。
    """
    now = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        # Mark the specific event as published
        conn.execute(
            "UPDATE recent_event_pool SET published = 1, published_at = ? WHERE event_id = ?",
            (now, event_id),
        )
        # Also mark other entries with the same story_fingerprint as consumed
        conn.execute(
            """
            UPDATE recent_event_pool
            SET consumed = 1
            WHERE event_id != ?
              AND story_fingerprint = (
                  SELECT story_fingerprint FROM recent_event_pool WHERE event_id = ?
              )
              AND story_fingerprint != ''
            """,
            (event_id, event_id),
        )
    logger.info(f"[Pool] Event {event_id} marked published; sibling fingerprints consumed")


def mark_pool_event_consumed(db_path: Path, event_id: str) -> None:
    """recent_event_pool のイベントを消化済み（選択済み）にマークする。"""
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE recent_event_pool SET consumed = 1 WHERE event_id = ?",
            (event_id,),
        )


def expire_old_pool_events(db_path: Path, max_hours: int = 48) -> int:
    """max_hours より古いプールイベントを expired にマークする。

    Returns:
        期限切れにしたイベント数
    """
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_hours)).isoformat()

    sql = """
    UPDATE recent_event_pool
    SET expired = 1
    WHERE expired = 0
      AND created_at < ?
    """
    with _connect(db_path) as conn:
        cursor = conn.execute(sql, (cutoff,))
        count = cursor.rowcount
    if count > 0:
        logger.info(f"[Pool] Expired {count} pool events older than {max_hours} h")
    return count


# ── Recency Guard (recency_records) ───────────────────────────────────────────

def save_recency_record(db_path: Path, record: RecencyRecord) -> None:
    """投稿成功時の RecencyRecord を保存する。

    primary_entities / primary_topics は JSON 配列文字列として永続化する。
    """
    sql = """
    INSERT INTO recency_records
        (event_id, channel_id, primary_entities, primary_topics, published_at)
    VALUES (?, ?, ?, ?, ?)
    """
    with _connect(db_path) as conn:
        conn.execute(
            sql,
            (
                record.event_id,
                record.channel_id,
                json.dumps(record.primary_entities, ensure_ascii=False),
                json.dumps(record.primary_topics, ensure_ascii=False),
                record.published_at,
            ),
        )
    logger.info(
        f"[Recency] Saved record event_id={record.event_id} channel={record.channel_id} "
        f"entities={len(record.primary_entities)} topics={len(record.primary_topics)}"
    )


def get_recency_records(
    db_path: Path,
    channel_id: str,
    within_hours: int = 24,
) -> list[RecencyRecord]:
    """指定チャンネルで直近 within_hours 時間以内の RecencyRecord を返す。"""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=within_hours)).isoformat()

    sql = """
    SELECT event_id, channel_id, primary_entities, primary_topics, published_at
    FROM recency_records
    WHERE channel_id = ?
      AND published_at >= ?
    ORDER BY published_at DESC
    """
    with _connect(db_path) as conn:
        rows = conn.execute(sql, (channel_id, cutoff)).fetchall()

    records: list[RecencyRecord] = []
    for row in rows:
        records.append(
            RecencyRecord(
                event_id=row["event_id"],
                channel_id=row["channel_id"],
                primary_entities=json.loads(row["primary_entities"] or "[]"),
                primary_topics=json.loads(row["primary_topics"] or "[]"),
                published_at=row["published_at"],
            )
        )
    return records
