"""ScoredEvent から primary_entities / primary_topics を抽出する。

設計書 Section 9.3 の仕様に従う。LLM 呼び出しは行わない（軽量・決定的）。

抽出ロジック:
    1. configs/entity_dictionary.yaml をプロセスごとに 1 回ロードしてキャッシュ。
    2. event の title / summary / 既存タグ等を結合した小文字テキストに対して、
       辞書の各エントリの aliases いずれかが部分一致すれば canonical key を返す。
    3. 完全一致ではなく substring + 単語境界（日本語は単純な部分一致）で判定。
"""
from __future__ import annotations

import re
from pathlib import Path
from threading import Lock
from typing import Optional

import yaml

from src.shared.logger import get_logger
from src.shared.models import ScoredEvent

logger = get_logger(__name__)


_DEFAULT_DICT_PATH = Path(__file__).resolve().parents[2] / "configs" / "entity_dictionary.yaml"

# プロセスごとに 1 回だけロードする辞書キャッシュ。
_DICT_CACHE: Optional[dict] = None
_DICT_LOCK = Lock()

# people / organizations / countries は entity 系、topics のみ topic 系として返す。
_ENTITY_CATEGORIES = ("people", "organizations", "countries")
_TOPIC_CATEGORIES = ("topics",)


def _load_dictionary(path: Optional[Path] = None) -> dict:
    """エンティティ辞書をロードする（プロセス内で一度だけ）。"""
    global _DICT_CACHE
    if path is not None:
        # テスト等で明示パス指定された場合はキャッシュをバイパスする
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    with _DICT_LOCK:
        if _DICT_CACHE is None:
            target = _DEFAULT_DICT_PATH
            if not target.exists():
                logger.warning(f"[EntityExtractor] dictionary not found at {target}")
                _DICT_CACHE = {}
            else:
                with open(target, "r", encoding="utf-8") as fh:
                    _DICT_CACHE = yaml.safe_load(fh) or {}
        return _DICT_CACHE


def _reset_cache_for_tests() -> None:
    """テスト用: 辞書キャッシュをクリアする。"""
    global _DICT_CACHE
    with _DICT_LOCK:
        _DICT_CACHE = None


def _normalize_entity(term: str) -> str:
    """辞書照合用の正規化。

    - 前後空白除去
    - 小文字化（ASCII のみ。日本語はそのまま）
    - 連続空白を 1 つに圧縮
    """
    if not term:
        return ""
    s = term.strip()
    s = re.sub(r"\s+", " ", s)
    return s.lower()


def _is_ascii(s: str) -> bool:
    return all(ord(c) < 128 for c in s)


def _alias_matches(alias: str, normalized_text: str, original_text: str) -> bool:
    """alias が text に含まれるかを判定する。

    - ASCII エイリアス: 小文字化したテキストに対する単語境界マッチ
      （Trump が "trumpet" にマッチしないように）
    - 非 ASCII（日本語等）: 原文に対する単純な substring マッチ
    """
    alias_norm = _normalize_entity(alias)
    if not alias_norm:
        return False
    if _is_ascii(alias_norm):
        # 単語境界で囲まれているか確認。alias 内のメタ文字はエスケープ。
        pattern = r"(?<![A-Za-z0-9])" + re.escape(alias_norm) + r"(?![A-Za-z0-9])"
        return re.search(pattern, normalized_text) is not None
    # 日本語は単純 substring。
    return alias in original_text


def _build_search_text(event: ScoredEvent) -> tuple[str, str]:
    """event から検索対象テキスト（原文 / 小文字化）を構築する。"""
    parts: list[str] = []
    ev = event.event
    if ev.title:
        parts.append(ev.title)
    if ev.summary:
        parts.append(ev.summary)
    if ev.japan_view:
        parts.append(ev.japan_view)
    if ev.global_view:
        parts.append(ev.global_view)
    if ev.background:
        parts.append(ev.background)
    if ev.impact_on_japan:
        parts.append(ev.impact_on_japan)
    if ev.tags:
        parts.extend(ev.tags)
    if event.editorial_tags:
        parts.extend(event.editorial_tags)
    if event.tags_multi:
        parts.extend(event.tags_multi)
    original = " \n ".join(p for p in parts if p)
    return original, original.lower()


def _extract_canonicals(
    event: ScoredEvent,
    categories: tuple[str, ...],
    dictionary: Optional[dict] = None,
) -> list[str]:
    """指定カテゴリ群について event から canonical key を抽出する（重複排除済み）。"""
    dictionary = dictionary if dictionary is not None else _load_dictionary()
    original, normalized = _build_search_text(event)
    if not original:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for category in categories:
        bucket = dictionary.get(category) or {}
        if not isinstance(bucket, dict):
            continue
        for canonical, aliases in bucket.items():
            if canonical in seen:
                continue
            if not aliases:
                continue
            for alias in aliases:
                if _alias_matches(str(alias), normalized, original):
                    found.append(canonical)
                    seen.add(canonical)
                    break
    return found


def extract_primary_entities(
    event: ScoredEvent,
    dictionary: Optional[dict] = None,
) -> list[str]:
    """主要エンティティ（人物・組織・国）を抽出する。

    Returns:
        canonical key のリスト。最大件数制限はかけない。
    """
    return _extract_canonicals(event, _ENTITY_CATEGORIES, dictionary=dictionary)


def extract_primary_topics(
    event: ScoredEvent,
    dictionary: Optional[dict] = None,
) -> list[str]:
    """主要トピック（trade_war / ukraine_war 等）を抽出する。"""
    return _extract_canonicals(event, _TOPIC_CATEGORIES, dictionary=dictionary)
