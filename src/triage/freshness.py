"""Freshness decay for rolling comparison window candidates.

Events from previous batches are gently penalized to prefer fresh content
while still allowing strong older stories to compete in the candidate pool.

Decay schedule (age of event since it entered the pool):
    current batch (set explicitly, not time-based) : 1.00
    < 24 h                                          : 0.90
    24 h ≤ age < 36 h                               : 0.80
    36 h ≤ age < 48 h                               : 0.65
    ≥ 48 h                                          : 0.00  (expired)

The decay is applied as a *tie-breaker additive adjustment*:
    effective_score = base_score + (decay - 1.0) * DECAY_PENALTY_SCALE

With DECAY_PENALTY_SCALE = 5.0 the max penalty is −1.75 points (48 h event),
which is large enough to prefer fresher peers at equal base score but small
enough not to bury a strong older story behind a weak fresh one.
"""
from __future__ import annotations

from datetime import datetime, timezone

# ── Freshness tier thresholds (age_hours → decay) ────────────────────────────
# Checked in ascending order; first match wins.
_TIERS: list[tuple[float, float]] = [
    (24.0, 0.90),   # age < 24 h
    (36.0, 0.80),   # 24 h ≤ age < 36 h
    (48.0, 0.65),   # 36 h ≤ age < 48 h
]

# Events older than this are expired and excluded from the candidate pool.
EXPIRED_HOURS: float = 48.0

# Scale factor for converting decay into an additive score adjustment.
# Keep small so decay acts as a tie-breaker, not a hard gate.
DECAY_PENALTY_SCALE: float = 5.0

# Default comparison window for pool queries (hours)
DEFAULT_WINDOW_HOURS: int = 36

# Maximum comparison window (hard cap for pool queries)
MAX_WINDOW_HOURS: int = 48


def compute_freshness_decay(created_at: datetime, now: datetime | None = None) -> float:
    """Return a freshness decay multiplier in [0.0, 0.90] for pool events.

    Notes:
        - Current-batch events get decay = 1.0 explicitly (not via this function).
        - This function is for *pool* events loaded from previous batches.
        - Returns 0.0 if the event is expired (age ≥ EXPIRED_HOURS).

    Args:
        created_at: Timestamp when the event was first inserted into the pool.
        now:        Reference time (defaults to UTC now).

    Returns:
        float in {0.0, 0.65, 0.80, 0.90}.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Ensure timezone-aware comparison
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    age_hours = (now - created_at).total_seconds() / 3600.0

    if age_hours >= EXPIRED_HOURS:
        return 0.0

    for threshold, decay in _TIERS:
        if age_hours < threshold:
            return decay

    # Fallback — covers floating-point edge cases just under EXPIRED_HOURS
    return 0.65


def is_expired(created_at: datetime, now: datetime | None = None) -> bool:
    """Return True if the event is too old for the comparison window."""
    return compute_freshness_decay(created_at, now) == 0.0


def effective_score(base_score: float, decay: float) -> float:
    """Compute effective score for ranking after freshness adjustment.

    Keeps base_score intact for transparency; applies a small additive
    penalty so that fresher events win ties against older peers.

        effective = base_score + (decay - 1.0) * DECAY_PENALTY_SCALE

    Examples:
        decay 1.00 → +0.00 (current batch, no change)
        decay 0.90 → −0.50 (< 24 h pool event)
        decay 0.80 → −1.00 (< 36 h pool event)
        decay 0.65 → −1.75 (< 48 h pool event)
    """
    return base_score + (decay - 1.0) * DECAY_PENALTY_SCALE
