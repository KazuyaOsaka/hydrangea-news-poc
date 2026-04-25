"""Recency Guard — 同一人物・トピックの連続投稿を抑制する。

設計書 Section 9.2 / 9.4 の仕様に従う。

ロジック:
    1. 直近 RECENCY_GUARD_HOURS（デフォルト 24h）の RecencyRecord を DB から取得。
    2. 各候補について primary_entities / primary_topics を抽出し、
       直近の entity/topic と重複があれば score を RECENCY_GUARD_PENALTY 倍に降格。
    3. 降格適用後にスコア順で再ソートして返す。

設計上の判断:
    - 設計書では `candidate.total_score *= 0.5` と書かれているが、
      ScoredEvent には `total_score` フィールドはなく `score` フィールドが該当する
      （既存コード参照: src/triage/scoring.py, src/main.py）。
    - そのため本実装では `score` を降格する。score_breakdown には影響を与えない。
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.analysis.entity_extractor import (
    extract_primary_entities,
    extract_primary_topics,
)
from src.shared.logger import get_logger
from src.shared.models import RecencyRecord, ScoredEvent

logger = get_logger(__name__)


def _get_penalty() -> float:
    """RECENCY_GUARD_PENALTY を float で返す（無効値なら 0.5）。"""
    raw = os.getenv("RECENCY_GUARD_PENALTY", "0.5")
    try:
        val = float(raw)
        if val < 0.0 or val > 1.0:
            logger.warning(
                f"[Recency] RECENCY_GUARD_PENALTY={raw} out of range; using 0.5"
            )
            return 0.5
        return val
    except ValueError:
        logger.warning(f"[Recency] RECENCY_GUARD_PENALTY={raw} invalid; using 0.5")
        return 0.5


def _get_window_hours() -> int:
    raw = os.getenv("RECENCY_GUARD_HOURS", "24")
    try:
        val = int(raw)
        return val if val > 0 else 24
    except ValueError:
        logger.warning(f"[Recency] RECENCY_GUARD_HOURS={raw} invalid; using 24")
        return 24


def apply_recency_guard(
    candidates: list[ScoredEvent],
    channel_id: str,
    db_path: Path,
    *,
    within_hours: Optional[int] = None,
    penalty: Optional[float] = None,
) -> list[ScoredEvent]:
    """直近に投稿した entity/topic と重複する候補のスコアを降格する。

    Args:
        candidates: 候補リスト（既にスコア付け済みの ScoredEvent）。
        channel_id: 対象チャンネル（例: "geo_lens"）。
        db_path:    SQLite DB パス。
        within_hours: 降格対象の窓（None なら RECENCY_GUARD_HOURS）。
        penalty:    降格率（None なら RECENCY_GUARD_PENALTY、0.5 なら -50%）。

    Returns:
        新しいリスト（降格適用後にスコア降順でソート済み）。
        元の ScoredEvent の score / recency_guard_applied / recency_overlap が更新される。
    """
    if not candidates:
        return []

    # 動的 import（循環回避と main.py への影響最小化のため）
    from src.storage.db import get_recency_records

    win = within_hours if within_hours is not None else _get_window_hours()
    pen = penalty if penalty is not None else _get_penalty()

    records: list[RecencyRecord] = get_recency_records(
        db_path, channel_id=channel_id, within_hours=win
    )

    recent_entities: set[str] = set()
    recent_topics: set[str] = set()
    for rec in records:
        recent_entities.update(rec.primary_entities)
        recent_topics.update(rec.primary_topics)

    if not recent_entities and not recent_topics:
        # 何も降格しない。並び順は呼び出し側のものをそのまま返す。
        return list(candidates)

    for cand in candidates:
        cand_entities = set(extract_primary_entities(cand))
        cand_topics = set(extract_primary_topics(cand))
        entity_overlap = recent_entities & cand_entities
        topic_overlap = recent_topics & cand_topics
        overlap = entity_overlap | topic_overlap
        if overlap:
            cand.score = float(cand.score) * pen
            cand.recency_guard_applied = True
            cand.recency_overlap = sorted(overlap)
            logger.info(
                f"[Recency] event={cand.event.id} demoted x{pen} due to overlap={sorted(overlap)}"
            )

    return sorted(candidates, key=lambda c: c.score, reverse=True)


def record_publication(
    event: ScoredEvent,
    channel_id: str,
    db_path: Path,
    *,
    published_at: Optional[str] = None,
) -> RecencyRecord:
    """投稿成功時に RecencyRecord を保存して返す。"""
    from src.storage.db import save_recency_record

    record = RecencyRecord(
        event_id=event.event.id,
        channel_id=channel_id,
        primary_entities=extract_primary_entities(event),
        primary_topics=extract_primary_topics(event),
        published_at=published_at or datetime.now(timezone.utc).isoformat(),
    )
    save_recency_record(db_path, record)
    return record
