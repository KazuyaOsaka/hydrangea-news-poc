"""garbage_filter.py — Gate 1: Garbage Filter（ハイブリッド: 静的ルール + LLM）

Phase 1.5 batch E-1 でハイブリッド構成に変更:
- ステージ1: 言語非依存の静的ルールで明確なゴミを除外
  （タイトル長・合計文字数・カテゴリ・公開日）
- ステージ2: 残りを LLM で判定
  （Hydrangea のメディア理念に基づく文脈的判定）

完全静的ルール化を試みたが、情報密度チェック（_has_proper_noun）が
日本語/英語の正規表現のみで多言語（ハングル・アラビア語・キリル文字等）に
破綻するため断念。Hydrangea は geo_lens / japan_athletes / k_pulse の
3 チャンネル展開で多言語前提のため、言語非依存の3項目のみ静的、
文脈判定は LLM に委ねる方式に統合した。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

from src.llm.schemas import GarbageFilterResult
from src.shared.logger import get_logger

if TYPE_CHECKING:
    from src.llm.base import LLMClient

logger = get_logger(__name__)

# ── ステージ1: 言語非依存の静的ルール ─────────────────────────────────────────

_MIN_TITLE_LENGTH = 5
_MIN_TOTAL_TEXT_LENGTH = 30
_MAX_AGE_HOURS = 48

# カテゴリは RSS feed の <category> や normalizer が付与するタグで
# 明確に「ゴミ」に分類できるもの。言語に依存しない（カテゴリ名は英語固定）。
BLOCKED_CATEGORIES: frozenset[str] = frozenset({
    "advertisement",
    "advertorial",
    "promotion",
    "sponsored",
    "horoscope",
    "fortune",
    "fortune-telling",
    "lottery",
})


def _title_too_short(article: dict) -> bool:
    title = article.get("title") or article.get("normalized_title") or ""
    return len(title.strip()) < _MIN_TITLE_LENGTH


def _total_text_too_short(article: dict) -> bool:
    title = article.get("title") or article.get("normalized_title") or ""
    summary = article.get("summary") or article.get("description") or ""
    return len(title.strip()) + len(summary.strip()) < _MIN_TOTAL_TEXT_LENGTH


def _is_too_old(article: dict, *, now: Optional[datetime] = None) -> bool:
    """published_at が _MAX_AGE_HOURS より古ければ True。

    published_at が無い／パースできない場合は False（除外しない）。
    フィードによって日付欠落があるため保守的に通過させる。
    """
    raw = article.get("published_at") or article.get("published") or article.get("pubDate")
    if not raw:
        return False

    if isinstance(raw, datetime):
        published = raw
    else:
        published = _parse_datetime(str(raw))
        if published is None:
            return False

    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    return reference - published > timedelta(hours=_MAX_AGE_HOURS)


def _parse_datetime(s: str) -> Optional[datetime]:
    """ISO 8601 系の日時文字列をベストエフォートでパース。失敗したら None。"""
    s = s.strip()
    if not s:
        return None
    # `Z` (UTC) は datetime.fromisoformat が 3.11 から扱える
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _category_blocked(article: dict) -> bool:
    cats = article.get("categories") or article.get("category") or []
    if isinstance(cats, str):
        cats = [cats]
    for c in cats:
        if not c:
            continue
        if str(c).strip().lower() in BLOCKED_CATEGORIES:
            return True
    return False


def _static_classify(article: dict, *, now: Optional[datetime] = None) -> Optional[str]:
    """言語非依存の静的ルールで除外理由を返す。問題なしなら None。

    判定順は length → category → date（処理コストの軽い順）。
    """
    if _title_too_short(article) or _total_text_too_short(article):
        return "length"
    if _category_blocked(article):
        return "category"
    if _is_too_old(article, now=now):
        return "date"
    return None


# ── ステージ2: LLM 判定 ──────────────────────────────────────────────────────

_BATCH_SIZE = 30

_SYSTEM_PROMPT = """\
あなたは独立メディア「Hydrangea」のニュース編集アシスタントです。
以下のルールに従い、入力された記事リストを高速スクリーニングしてください。

【除外すべき記事（is_valuable: false）】
- 株価・為替の微増減（「〇〇株が2%上昇」「円がわずかに動いた」等）
- 地元・地方の天気予報・気象情報
- 一般的な交通事故・火事（死者・重傷なし、または地域的な軽微な事故）
- 企業の定例プレスリリース（決算発表の定型報告、製品の軽微なアップデート等）
- 芸能人の日常的な活動報告（コンサートスケジュール、軽微な近況報告）
- スポーツの試合結果（コメント・分析なし、単なるスコア速報）
- 政府機関・地方自治体の定例業務報告
- 個人の軽微な逮捕・事件（地域的なもの、社会的影響なし）

【採用すべき記事（is_valuable: true）】
- 国際政治・地政学的な動き
- 日本のメディアが報じていない海外の重要ニュース
- 経済・金融の構造的変化（政策転換、大規模経済危機等）
- 科学・技術の革新・ブレークスルー
- 社会的・文化的に重要なインパクトがある出来事
- 軍事・安全保障の動き
- 歴史的・制度的な変化
- グローバルサウス・新興国の重要な動向
- 日本では報じられていない海外の熱狂・反応

各記事について item_id, is_valuable, reason をJSON配列で出力してください。
reasonは必ず日本語で、20字以内で簡潔に書いてください。

【出力フォーマット】
JSONの配列のみを出力してください（コードブロック、説明文不要）:
[
  {"item_id": 0, "is_valuable": true, "reason": "地政学的重要性あり"},
  {"item_id": 1, "is_valuable": false, "reason": "株価の微増減"},
  ...
]\
"""


def _llm_filter(articles: list[dict], llm_client: "LLMClient") -> list[dict]:
    """残った記事を 30件単位バッチで LLM 判定し、is_valuable=True のみ返す。"""
    total = len(articles)
    kept: list[dict] = []
    batch_count = (total + _BATCH_SIZE - 1) // _BATCH_SIZE

    for batch_idx, batch_start in enumerate(range(0, total, _BATCH_SIZE)):
        batch = articles[batch_start : batch_start + _BATCH_SIZE]
        batch_items: list[str] = []
        for i, art in enumerate(batch):
            title = art.get("title") or art.get("normalized_title") or "(タイトルなし)"
            summary = art.get("summary") or art.get("description") or ""
            entry = f"[{i}] タイトル: {title}\n     概要: {summary[:200]}"
            batch_items.append(entry)

        user_content = (
            f"以下の{len(batch)}件の記事をスクリーニングしてください:\n\n"
            + "\n\n".join(batch_items)
        )
        prompt = f"{_SYSTEM_PROMPT}\n\n{user_content}"

        logger.info(
            f"[GarbageFilter] LLM Batch {batch_idx + 1}/{batch_count}: "
            f"{len(batch)}件 → Tier 階層 LLM へ送信"
        )

        try:
            raw = llm_client.generate(prompt)
            results = _parse_filter_results(raw, len(batch))
        except Exception as exc:
            logger.warning(
                f"[GarbageFilter] バッチ {batch_idx + 1} LLMエラー: {exc}. "
                "このバッチは全件通過させます。"
            )
            kept.extend(batch)
            continue

        batch_kept = 0
        batch_removed = 0
        for i, art in enumerate(batch):
            result = results.get(i)
            if result is None or result.is_valuable:
                kept.append(art)
                batch_kept += 1
            else:
                batch_removed += 1
                logger.debug(
                    f"[GarbageFilter] LLM 除外: {art.get('title', '')[:60]} "
                    f"(理由: {result.reason})"
                )

        logger.info(
            f"[GarbageFilter] LLM Batch {batch_idx + 1}: "
            f"通過 {batch_kept} / 除外 {batch_removed}"
        )

    return kept


def _parse_filter_results(raw: str, batch_size: int) -> dict[int, GarbageFilterResult]:
    """LLM出力からGarbageFilterResultのdict(item_id → result)を生成する。"""
    json_match = re.search(r"\[[\s\S]*\]", raw)
    if not json_match:
        raise ValueError(f"LLM出力からJSON配列を抽出できませんでした: {raw[:200]}")

    items = json.loads(json_match.group())
    results: dict[int, GarbageFilterResult] = {}
    for item in items:
        try:
            r = GarbageFilterResult(**item)
            results[r.item_id] = r
        except Exception:
            pass
    return results


# ── 公開エントリ ─────────────────────────────────────────────────────────────


def apply_garbage_filter(
    articles: list[dict],
    llm_client: "LLMClient | None",
) -> list[dict]:
    """Gate 1: 静的ルール → LLM の二段でノイズ除去を実行。

    ステージ1 (言語非依存):
      - タイトルが _MIN_TITLE_LENGTH 文字未満
      - タイトル + 概要が _MIN_TOTAL_TEXT_LENGTH 文字未満
      - カテゴリが BLOCKED_CATEGORIES に該当
      - published_at が _MAX_AGE_HOURS より古い
      のいずれかに当てはまる記事を除外。

    ステージ2 (LLM):
      残った記事を 30 件単位で LLM に投入し、Hydrangea の編集方針に
      基づいて文脈的に is_valuable を判定する。llm_client が None の
      場合はステージ2 をスキップし、ステージ1 通過分をそのまま返す。

    Returns:
        is_valuable=True と判定された記事のみのリスト。
    """
    if not articles:
        return articles

    total = len(articles)

    # ── ステージ1: 静的ルール ────────────────────────────────────────────
    static_kept: list[dict] = []
    static_rejected_counts = {"length": 0, "category": 0, "date": 0}

    for art in articles:
        reason = _static_classify(art)
        if reason is None:
            static_kept.append(art)
        else:
            static_rejected_counts[reason] += 1
            logger.debug(
                f"[GarbageFilter] 静的除外 ({reason}): "
                f"{(art.get('title') or '')[:60]}"
            )

    static_removed = total - len(static_kept)
    breakdown = (
        f"length={static_rejected_counts['length']}, "
        f"category={static_rejected_counts['category']}, "
        f"date={static_rejected_counts['date']}"
    )
    logger.info(
        f"[GarbageFilter] ステージ1 (静的): {total}件 → {len(static_kept)}件 "
        f"(除外 {static_removed}件 / 内訳 {breakdown})"
    )

    # ── ステージ2: LLM ─────────────────────────────────────────────────
    if llm_client is None or not static_kept:
        if llm_client is None:
            logger.info(
                "[GarbageFilter] ステージ2 (LLM): llm_client=None のためスキップ"
            )
        logger.info(
            f"[GarbageFilter] 完了: {total}件 → {len(static_kept)}件 "
            f"(静的除外 {static_removed}件 / LLM除外 0件)"
        )
        return static_kept

    final_kept = _llm_filter(static_kept, llm_client)
    llm_removed = len(static_kept) - len(final_kept)

    logger.info(
        f"[GarbageFilter] ステージ2 (LLM): {len(static_kept)}件 → {len(final_kept)}件 "
        f"(除外 {llm_removed}件)"
    )
    logger.info(
        f"[GarbageFilter] 完了: {total}件 → {len(final_kept)}件 "
        f"(静的除外 {static_removed}件 / LLM除外 {llm_removed}件)"
    )
    return final_kept
