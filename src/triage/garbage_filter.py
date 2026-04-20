"""garbage_filter.py — Gate 1: Garbage Filter（高速スクリーニング）

30件単位のバッチで Tier 2 Lite モデルに投入し、
Hydrangea のメディア理念に合致しないノイズを is_valuable=False として排除する。
"""
from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from src.llm.schemas import GarbageFilterResult
from src.shared.logger import get_logger

if TYPE_CHECKING:
    from src.llm.base import LLMClient

logger = get_logger(__name__)

_BATCH_SIZE = 50

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


def apply_garbage_filter(
    articles: list[dict],
    llm_client: "LLMClient",
) -> list[dict]:
    """Gate 1: 30件単位バッチで Tier 2 Lite モデルによるノイズ除去を実行。

    Returns:
        is_valuable=True と判定された記事のみのリスト。
    """
    if not articles:
        return articles

    total = len(articles)
    kept: list[dict] = []
    removed = 0
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
            f"[GarbageFilter] Batch {batch_idx + 1}/{batch_count}: "
            f"{len(batch)}件 → Tier 2 LLM へ送信"
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
                removed += 1
                batch_removed += 1
                logger.debug(
                    f"[GarbageFilter] 除外: {art.get('title', '')[:60]} "
                    f"(理由: {result.reason})"
                )

        logger.info(
            f"[GarbageFilter] Batch {batch_idx + 1}: "
            f"通過 {batch_kept} / 除外 {batch_removed}"
        )

    logger.info(
        f"[GarbageFilter] 完了: {total}件 → {len(kept)}件 "
        f"(除外 {removed}件 / {total}件)"
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
