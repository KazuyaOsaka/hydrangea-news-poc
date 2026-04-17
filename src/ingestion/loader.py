from __future__ import annotations

import json
from pathlib import Path

from src.shared.logger import get_logger
from src.shared.models import NewsEvent

logger = get_logger(__name__)


def load_events(path: Path) -> list[NewsEvent]:
    """JSONファイルからニュースイベント一覧を読み込む。"""
    logger.info(f"Loading events from {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    events = [NewsEvent.model_validate(item) for item in raw]
    logger.info(f"Loaded {len(events)} events")
    return events
