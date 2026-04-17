from __future__ import annotations

from src.shared.logger import get_logger
from src.shared.models import NewsEvent, ScoredEvent
from src.triage.scoring import compute_score_full

logger = get_logger(__name__)


def rank_events(events: list[NewsEvent]) -> list[ScoredEvent]:
    """全イベントをスコアリングして降順ソートして返す。"""
    scored: list[ScoredEvent] = []
    for event in events:
        score, breakdown, tier, tags, reason = compute_score_full(event)
        primary_bucket = str(breakdown.get("primary_bucket", "general"))
        scored.append(ScoredEvent(
            event=event,
            score=score,
            score_breakdown=breakdown,
            primary_tier=tier,
            editorial_tags=tags,
            editorial_reason=reason,
            primary_bucket=primary_bucket,
        ))
        logger.debug(f"[{event.id}] score={score:.1f} tier={tier} title={event.title[:30]}")

    scored.sort(key=lambda s: s.score, reverse=True)
    return scored


def pick_top(events: list[NewsEvent]) -> ScoredEvent:
    """最高スコアのイベントを1件返す。"""
    ranked = rank_events(events)
    top = ranked[0]
    logger.info(
        f"Selected event [{top.event.id}] score={top.score:.1f}: {top.event.title}"
    )
    return top
