"""実ニュースから EventCandidate (NewsEvent) を生成するモジュール。

data/normalized/ 配下の正規化 JSON を読み込み、タイトルのキーワード重複を使って
同じ話題の記事を簡易グルーピングし、NewsEvent に変換する。

グルーピング方針:
  - 日本語タイトル: 3 文字以上の CJK シーケンスを 3/4 文字サブストリングとして抽出
  - 英語タイトル  : 5 文字以上の単語 (ストップワード除外)
  - 言語非依存アンカートークン (country:/entity:/kw:/num:) をクロスランゲージ対応に使用
  - 同言語ペア: 高頻度汎用アンカーのみで結合するケースにはペナルティを設ける
  - クロスランゲージ (JP ↔ EN): アンカートークン ≥ 2 件で接続
  - 巨大クラスタ検出: しきい値超えで再分割または警告を出力
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from src.ingestion.cross_lang_matcher import extract_anchor_tokens
from src.shared.config import EN_CANDIDATES_PER_JP_CLUSTER
from src.shared.logger import get_logger
from src.shared.models import NewsEvent, SourceRef

if TYPE_CHECKING:
    from src.budget import BudgetTracker
    from src.llm.base import LLMClient

logger = get_logger(__name__)

DEFAULT_NORMALIZED_DIR = Path("data/normalized")

# クロスランゲージ (JP ↔ EN) のBFSエッジ許可に必要な最低アンカートークン一致数（旧仕様・参考値）。
# NOTE: 現在は _MIN_CROSS_LANG_STRONG_ANCHOR_HITS / _MIN_CROSS_LANG_WEAK_ONLY_ANCHOR_HITS で制御。
_MIN_CROSS_LANG_ANCHOR_HITS: int = 2  # 後方互換のため定義を残す（主ロジックでは使用しない）

# 強いアンカー（combined_high_freq外: entity:boj, entity:tsmc, num:0.25% 等）が
# 1件以上ある場合のクロスランゲージ接続に必要な最低アンカー数。
# 固有名詞・具体数値が1つでも一致すれば同一イベントの十分な証拠となる。
_MIN_CROSS_LANG_STRONG_ANCHOR_HITS: int = 1

# クロスランゲージペアで「強いアンカーなし（全て combined_high_freq）」の場合に必要な最低アンカー数。
# - 強いアンカー: BOJ/FED/TSMC/num: など combined_high_freq 外のアンカー
# - 弱アンカーのみ (entity:trump + country:iran 等) では接続するのに 3 件以上必要
_MIN_CROSS_LANG_WEAK_ONLY_ANCHOR_HITS: int = 3

# 同言語ペアで「強いシグナルなし・高頻度アンカーのみ」の場合に必要な最低高頻度アンカー数。
_MIN_HIGH_FREQ_ONLY_SAME_LANG: int = 3

# 巨大クラスタ検出しきい値: この記事数を超えるクラスタは再分割を試みる
_GIANT_CLUSTER_THRESHOLD: int = 10

# 巨大クラスタ再分割時の min_shared 段階的引き上げ
_GIANT_CLUSTER_SPLIT_LEVELS: tuple[int, ...] = (3, 5, 8)

# 巨大クラスタ分割時のクロスランゲージ弱アンカーのみペアに必要な最低アンカー数（段階別）。
# L1: 3 (初期BFSと同じ), L2: 4 (より厳しく), L3: 5 (最も厳しく)
# 強いアンカーが1件以上あれば _MIN_CROSS_LANG_ANCHOR_HITS (=2) が適用される。
_GIANT_CLUSTER_SPLIT_CROSS_LANG_WEAK_HITS: tuple[int, ...] = (3, 4, 5)

# 英語ストップワード（対応するアンカートークンで代替済みの高頻度語を含む）
_EN_STOP: frozenset[str] = frozenset(
    {
        "about", "after", "again", "their", "there", "these", "those", "which",
        "would", "could", "should", "might", "where", "while", "other", "with",
        "from", "into", "have", "been", "will", "also", "that", "this", "than",
        "when", "were", "they", "over", "more", "said", "says", "japan",
        # 高頻度すぎる語（entity:/country:/kw: アンカーで代替済み、通常KWとしては不要）
        "trump", "tariff", "tariffs", "trade", "china", "russia", "korea",
        "biden", "putin", "ukraine", "israel", "sanctions", "inflation",
        "taiwan", "india", "france", "germany",
    }
)

# 高頻度の日本語CJK n-gram（対応するアンカートークンが存在するため「強い」シグナルとみなさない）
# BFSで生成される3文字・4文字サブストリングを網羅しておく（固有名詞の部分一致を防ぐ）。
_HIGH_FREQ_JP_NGRAMS: frozenset[str] = frozenset({
    # トランプ (Trump) → entity:trump
    "トランプ", "トラン", "ランプ",
    # バイデン (Biden) → entity:biden
    "バイデン", "バイデ", "イデン",
    # プーチン (Putin) → entity:putin
    "プーチン", "プーチ", "ーチン",
    # 習近平 (Xi Jinping) → entity:xijinping
    "習近平",
    # ゼレンスキー (Zelensky) → entity:zelensky
    "ゼレンス", "ゼレン", "レンス",
    # マクロン (Macron) → entity:macron
    "マクロン", "マクロ", "クロン",
    # ネタニヤフ (Netanyahu) → entity:netanyahu
    "ネタニヤ", "タニヤフ", "ニヤフ",
    # モディ (Modi) → entity:modi  ※3文字以上のみ
    # ショルツ (Scholz)
    "ショルツ", "ショル", "ョルツ",
})

# 静的な高頻度汎用アンカートークン
# 強いアンカー（entity:boj, entity:fed, entity:tsmc, num:* など）はこのセットに含めない。
# 動的高頻度（バッチ内頻出キーワード）と組み合わせて同言語エッジ判定に使用する。
_HIGH_FREQ_ANCHORS: frozenset[str] = frozenset({
    # 汎用的すぎる貿易・安全保障キーワード
    "kw:tariff",
    "kw:trade",
    "kw:tradewar",
    "kw:tradetension",
    "kw:war",
    "kw:ceasefire",
    "kw:sanction",
    "kw:retaliation",
    "kw:exportcontrol",
    "kw:importrestriction",
    # 汎用的すぎる経済指標
    "kw:inflation",
    "kw:stock",
    "kw:stockprice",
    "kw:stockdown",
    "kw:stockup",
    "kw:recession",
    "kw:forex",
    # 役職名（具体的な人物特定にならない）
    "kw:president",
    "kw:primeminister",
    "kw:election",
    # 多くの記事に登場する超高頻度人物エンティティ
    "entity:trump",
    "entity:biden",
    "entity:musk",
    # 超高頻度国名（JP/ENニュースの大多数に登場）
    "country:usa",
    "country:japan",
    "country:china",
    # 紛争報道で過剰登場する国名（単独では cross-lang の強いシグナルにならない）
    # これらの国の記事同士は entity:netanyahu, entity:zelensky 等の具体的アンカーで接続する
    "country:iran",
    "country:israel",
    "country:russia",
    "country:ukraine",
})

# 各 JP クラスタにつき LLM に渡す EN 候補の上限 (EN_CANDIDATES_PER_JP_CLUSTER で上書き可能)
_TOP_EN_PER_JP: int = EN_CANDIDATES_PER_JP_CLUSTER

# ── Predicate Family Pre-blocking Guard ────────────────────────────────────────
# Detects the topic "predicate family" of a cluster from anchor tokens and raw text.
# Pairs with incompatible families are rejected before any LLM call.
#
# Tuple format: (anchor_token_frozenset, raw_substring_frozenset)
# anchor tokens match against _extract_keywords() output.
# raw substrings match against the lowercased article title.

_PREDICATE_FAMILY_SIGNALS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "tax_fiscal": (
        frozenset({"kw:taxhike", "kw:taxcut", "kw:fiscaldeficit", "kw:govbond"}),
        frozenset({
            "gasoline tax", "fuel tax", "excise tax", "tax pause", "tax freeze",
            "tax suspension", "tax cut", "tax hike", "tax relief", "gst",
            "carbon tax", "levy",
            "減税", "増税", "ガソリン税", "消費税", "税率",
        }),
    ),
    "conflict_military": (
        frozenset({
            "kw:ceasefire", "kw:war", "kw:missile", "kw:nuclearweapon",
            "kw:groundinvasion", "kw:missilestrike", "kw:peacetalks",
            "kw:ceaseagreement", "kw:hostagerelease", "kw:territorial",
        }),
        frozenset({
            "ceasefire", "cease-fire", "airstrike", "air strike", "bombing",
            "hostilities", "blockade", "troops", "military operation",
            "ground offensive", "ground invasion", "armed conflict", "attack on",
            "停戦", "攻撃", "軍事作戦", "停戦合意", "空爆",
        }),
    ),
    "finance_earnings": (
        frozenset({
            "kw:merger", "kw:acquisition", "kw:bankruptcy", "kw:layoff",
            "kw:masslayoff",
        }),
        frozenset({
            "earnings", "quarterly earnings", "quarterly profit", "revenue",
            " q1 ", " q2 ", " q3 ", " q4 ", "fiscal quarter", "beats expectations",
            "profit warning", "layoff", "restructuring", "annual report",
            "決算", "利益", "収益", "四半期決算",
        }),
    ),
    "humanitarian": (
        frozenset({"kw:humanrights"}),
        frozenset({
            "refugee", "asylum seeker", "humanitarian aid", "healthcare access",
            "medical care for", "migrant health", "refugee health",
            "health coverage", "health insurance", "patient care",
            "難民", "難民医療", "亡命",
        }),
    ),
    "telecom_space": (
        frozenset(),
        frozenset({
            "satellite contract", "telecom contract", "defense satellite",
            "starlink", "broadband satellite", "spectrum auction",
            "telecommunications deal", "defense telecom",
            "衛星通信", "防衛契約",
        }),
    ),
    "energy_supply": (
        frozenset({"kw:oilprice", "kw:energy", "kw:renewables"}),
        frozenset({
            "oil supply", "crude oil", "natural gas", "lng", "opec",
            "petroleum", "energy supply", "pipeline", "liquefied",
            "原油", "天然ガス", "エネルギー供給", "液化天然ガス",
        }),
    ),
}

# Predicate family pairs that are allowed to merge (e.g. tax policy → corporate earnings impact)
_COMPATIBLE_FAMILY_PAIRS: frozenset[frozenset] = frozenset({
    frozenset({"tax_fiscal", "finance_earnings"}),     # tax cuts affect corporate earnings
    frozenset({"energy_supply", "finance_earnings"}),  # energy company financials
    frozenset({"telecom_space", "finance_earnings"}),  # telecom/satellite company earnings
})

# Pairs per batch LLM request (10–20 is the recommended range)
_BATCH_LLM_SIZE: int = 15


def _classify_predicate_family(articles: list[dict]) -> str | None:
    """Classify a cluster into its dominant predicate family.

    Checks each article's title against anchor tokens and raw substrings.
    Returns the most-voted family if it appears in ≥ half the articles,
    otherwise None (unknown / ambiguous).
    """
    family_votes: dict[str, int] = {}

    for article in articles:
        title_raw = article.get("title") or ""
        title_lower = title_raw.lower()
        anchors = _extract_keywords(title_raw)

        for family, (anchor_set, raw_set) in _PREDICATE_FAMILY_SIGNALS.items():
            anchor_hit = bool(anchor_set and anchors & anchor_set)
            raw_hit = any(kw in title_lower for kw in raw_set)
            if anchor_hit or raw_hit:
                family_votes[family] = family_votes.get(family, 0) + 1

    if not family_votes:
        return None

    sorted_fams = sorted(family_votes.items(), key=lambda x: -x[1])
    top_family, top_count = sorted_fams[0]
    # Only declare a dominant family when it covers at least half the articles
    if top_count >= max(1, len(articles) // 2):
        return top_family
    return None


def _predicate_families_incompatible(fam_a: str | None, fam_b: str | None) -> bool:
    """Return True when two predicate families should NOT be merged without LLM.

    Unknown (None) families are passed through to LLM.
    Same family is always compatible.
    Pairs in _COMPATIBLE_FAMILY_PAIRS are explicitly allowed.
    All other different-family pairs are incompatible.
    """
    if fam_a is None or fam_b is None:
        return False  # Unknown → let LLM decide
    if fam_a == fam_b:
        return False
    if frozenset({fam_a, fam_b}) in _COMPATIBLE_FAMILY_PAIRS:
        return False
    return True


def _extract_keywords(title: str) -> set[str]:
    """タイトルからマッチング用キーワードセットを抽出する。

    Japanese: 3 文字以上の CJK/かな/カナ連続から 3〜4 文字サブストリングを生成。
    English : 5 文字以上の単語 (ストップワード除く)。
    Anchors : 言語非依存アンカートークン (country:/entity:/kw:/num:) を追加。
    """
    keywords: set[str] = set()

    # CJK + ひらがな + カタカナ の 3 文字以上連続
    for m in re.finditer(r"[\u3040-\u9fff\uf900-\ufaff]{3,}", title):
        text = m.group()
        for length in (3, 4):
            for start in range(len(text) - length + 1):
                keywords.add(text[start : start + length])

    # 英語: 5 文字以上の単語
    for m in re.finditer(r"[a-zA-Z]{5,}", title):
        word = m.group().lower()
        if word not in _EN_STOP:
            keywords.add(word)

    # 言語非依存アンカートークン (country:/entity:/kw:/num:)
    keywords |= extract_anchor_tokens(title)

    return keywords


def _score_pair(jp_cluster: list[dict], en_cluster: list[dict]) -> float:
    """JP/EN クラスタペアの候補スコアを計算する（LLM 前処理フィルタ用）。

    スコアが高いほど同一イベントの可能性が高い:
    - 強いアンカートークン (機関名・数値・固有名詞) の共通数: 重み 3
    - 弱い汎用アンカートークンのみの場合: ペナルティ (-1.5/件)
    - 通常キーワードの共通数: 重み 1
    - カテゴリ一致（general 以外）: +2
    - 公開日時の近さ 24h 以内: +1、6h 以内: さらに +1
    """
    jp_kws: set[str] = set()
    for a in jp_cluster:
        jp_kws |= _extract_keywords(a.get("title", ""))
    en_kws: set[str] = set()
    for a in en_cluster:
        en_kws |= _extract_keywords(a.get("title", ""))

    common = jp_kws & en_kws
    anchor_hits = sum(1 for k in common if ":" in k)
    regular_hits = len(common) - anchor_hits

    # 強いアンカーと弱い（高頻度汎用）アンカーを区別
    strong_anchor_hits = sum(1 for k in common if ":" in k and k not in _HIGH_FREQ_ANCHORS)
    weak_anchor_hits = anchor_hits - strong_anchor_hits

    score = anchor_hits * 3.0 + regular_hits * 1.0

    # 弱いアンカーのみで構成される場合はペナルティ（過検出を防ぐ）
    if anchor_hits > 0 and strong_anchor_hits == 0:
        score -= weak_anchor_hits * 1.5

    # カテゴリ一致ボーナス（general を除く）
    jp_cats = {a.get("category", "general") for a in jp_cluster}
    en_cats = {a.get("category", "general") for a in en_cluster}
    if (jp_cats & en_cats) - {"general"}:
        score += 2.0

    # 公開日時の近さ
    def _parse_dates(cluster: list[dict]) -> list[datetime]:
        result = []
        for a in cluster:
            try:
                dt = datetime.fromisoformat(a.get("published_at", ""))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                result.append(dt)
            except Exception:
                pass
        return result

    jp_dates = _parse_dates(jp_cluster)
    en_dates = _parse_dates(en_cluster)
    if jp_dates and en_dates:
        min_gap_h = min(
            abs((jd - ed).total_seconds()) / 3600
            for jd in jp_dates
            for ed in en_dates
        )
        if min_gap_h <= 24:
            score += 1.0
        if min_gap_h <= 6:
            score += 1.0

    return score


def _bfs_cluster(
    articles: list[dict],
    min_shared_keywords: int = 1,
    min_cross_lang_weak_only_hits: int = _MIN_CROSS_LANG_WEAK_ONLY_ANCHOR_HITS,
) -> tuple[list[list[dict]], int, dict[str, int]]:
    """純粋なBFSクラスタリング（巨大クラスタ分割・LLM後処理なし）。

    エッジ形成ルール:
      - クロスランゲージ (JP ↔ EN):
          強いアンカー（combined_high_freq 外）が1件以上 → anchor_hits ≥ _MIN_CROSS_LANG_STRONG_ANCHOR_HITS (1)
          強いアンカーなし（全て弱/高頻度）           → anchor_hits ≥ min_cross_lang_weak_only_hits (3)
      - 同言語ペア: 「強いシグナル」が1件以上、または高頻度アンカーが ≥ _MIN_HIGH_FREQ_ONLY_SAME_LANG 件
        強いシグナル = 静的高頻度アンカーでも動的高頻度KWでもないキーワード
        動的高頻度 = このバッチ内で ≥ 15% の記事に登場するキーワード (最低3件)

    Returns:
        (clusters, cross_lang_bfs_edges, cross_lang_reject_reasons)
    """
    if not articles:
        return [], 0, {}

    n = len(articles)
    article_keywords = [_extract_keywords(a.get("title", "")) for a in articles]
    article_is_jp = [a.get("country") == "JP" for a in articles]

    # 逆引きインデックス: キーワード → そのキーワードを持つ記事インデックス一覧
    kw_to_indices: dict[str, list[int]] = defaultdict(list)
    for i, kw_set in enumerate(article_keywords):
        for k in kw_set:
            kw_to_indices[k].append(i)

    # 動的高頻度キーワード: このバッチで 15% 以上の記事に登場するキーワード
    # (最低3件) → 同言語エッジでは「強いシグナル」扱いしない
    _DYNAMIC_HIGH_FREQ_RATIO = 0.15
    _DYNAMIC_HIGH_FREQ_MIN = 3
    dynamic_threshold = max(_DYNAMIC_HIGH_FREQ_MIN, int(n * _DYNAMIC_HIGH_FREQ_RATIO))
    dynamic_high_freq: frozenset[str] = frozenset(
        k for k, idx_list in kw_to_indices.items() if len(idx_list) >= dynamic_threshold
    )
    combined_high_freq = _HIGH_FREQ_ANCHORS | dynamic_high_freq

    # 隣接セット構築
    adjacent: list[set[int]] = [set() for _ in range(n)]
    cross_lang_edges = 0
    cross_lang_reject_reasons: dict[str, int] = {}

    for indices in kw_to_indices.values():
        if len(indices) < 2:
            continue
        for x in range(len(indices)):
            for y in range(x + 1, len(indices)):
                a, b = indices[x], indices[y]
                if a in adjacent[b]:
                    continue  # 既接続

                is_cross = article_is_jp[a] != article_is_jp[b]
                if is_cross:
                    # クロスランゲージ: アンカートークン一致数チェックのみ
                    # (min_shared_keywords は同言語ペアのみ適用; JP↔EN は anchor_hits で判定)
                    common = article_keywords[a] & article_keywords[b]
                    anchor_hits = sum(1 for k in common if ":" in k)
                    strong_cross = sum(1 for k in common if ":" in k and k not in combined_high_freq)
                    # 強いアンカー（combined_high_freq 外）が1件以上あれば1件で十分。
                    # entity:boj, entity:tsmc, num:0.25% など固有名詞・具体数値は
                    # 1つでも同一イベントの強い証拠となる。
                    # 強いアンカーなし（全て弱/高頻度）の場合は min_cross_lang_weak_only_hits が必要。
                    if strong_cross >= 1:
                        if anchor_hits < _MIN_CROSS_LANG_STRONG_ANCHOR_HITS:
                            cross_lang_reject_reasons["insufficient_anchor_hits"] = (
                                cross_lang_reject_reasons.get("insufficient_anchor_hits", 0) + 1
                            )
                            logger.debug(
                                f"Cross-lang edge rejected (strong={strong_cross}, "
                                f"anchor_hits={anchor_hits}"
                                f"<{_MIN_CROSS_LANG_STRONG_ANCHOR_HITS}): "
                                f"'{articles[a].get('title','')[:30]}' ↔ "
                                f"'{articles[b].get('title','')[:30]}'"
                            )
                            continue
                    else:
                        if anchor_hits < min_cross_lang_weak_only_hits:
                            cross_lang_reject_reasons["weak_only_insufficient"] = (
                                cross_lang_reject_reasons.get("weak_only_insufficient", 0) + 1
                            )
                            logger.debug(
                                f"Cross-lang edge rejected (weak-only, anchor_hits={anchor_hits}"
                                f"<{min_cross_lang_weak_only_hits}): "
                                f"'{articles[a].get('title','')[:30]}' ↔ "
                                f"'{articles[b].get('title','')[:30]}'"
                            )
                            continue
                    cross_lang_edges += 1
                else:
                    shared = len(article_keywords[a] & article_keywords[b])
                    if shared < min_shared_keywords:
                        continue
                    # 同言語ペア: 高頻度アンカーのみによる結合を抑制
                    common = article_keywords[a] & article_keywords[b]
                    # 強いシグナル: combined_high_freq でも _HIGH_FREQ_JP_NGRAMS でもないキーワード
                    strong_shared = {
                        k for k in common
                        if k not in combined_high_freq and k not in _HIGH_FREQ_JP_NGRAMS
                    }
                    if not strong_shared:
                        # 強いシグナルなし: 高頻度アンカー（":"あり）が _MIN_HIGH_FREQ_ONLY_SAME_LANG 個以上必要
                        high_freq_anchors_shared = {
                            k for k in common
                            if ":" in k and k in combined_high_freq
                        }
                        if len(high_freq_anchors_shared) < _MIN_HIGH_FREQ_ONLY_SAME_LANG:
                            logger.debug(
                                f"Same-lang edge rejected (weak-only, "
                                f"hf_anchors={len(high_freq_anchors_shared)}"
                                f"<{_MIN_HIGH_FREQ_ONLY_SAME_LANG}): "
                                f"'{articles[a].get('title','')[:30]}' ↔ "
                                f"'{articles[b].get('title','')[:30]}'"
                            )
                            continue

                adjacent[a].add(b)
                adjacent[b].add(a)

    # BFS でクラスタを形成
    visited = [False] * n
    clusters: list[list[dict]] = []
    for start in range(n):
        if visited[start]:
            continue
        cluster_indices: list[int] = []
        queue = [start]
        visited[start] = True
        while queue:
            node = queue.pop(0)
            cluster_indices.append(node)
            for neighbor in adjacent[node]:
                if not visited[neighbor]:
                    visited[neighbor] = True
                    queue.append(neighbor)
        clusters.append([articles[i] for i in cluster_indices])

    return clusters, cross_lang_edges, cross_lang_reject_reasons


def _analyze_giant_cluster(cluster: list[dict]) -> dict:
    """Giant cluster の共有トークン・エンティティ・ソースパターンを分析する。

    Returns:
        cluster_size, top_shared_tokens, top_entities, top_keywords, top_source_patterns
    """
    all_kw_lists = [_extract_keywords(a.get("title", "")) for a in cluster]
    token_counts: Counter = Counter()
    for kw_set in all_kw_lists:
        for token in kw_set:
            token_counts[token] += 1

    # 50%以上の記事に出現するトークンを「共有トークン」とみなす
    threshold = max(2, len(cluster) // 2)
    shared = [(t, c) for t, c in token_counts.most_common(30) if c >= threshold]

    top_entities = [(t, c) for t, c in shared if t.startswith("entity:")][:5]
    top_countries = [(t, c) for t, c in shared if t.startswith("country:")][:5]
    top_keywords = [(t, c) for t, c in shared if t.startswith("kw:")][:5]
    top_regular = [(t, c) for t, c in shared if ":" not in t][:5]

    source_counts: Counter = Counter(a.get("source_name", "unknown") for a in cluster)

    return {
        "cluster_size": len(cluster),
        "top_shared_tokens": shared[:10],
        "top_entities": top_entities,
        "top_countries": top_countries,
        "top_keywords": top_keywords,
        "top_regular_tokens": top_regular,
        "top_source_patterns": source_counts.most_common(5),
    }


def _split_giant_clusters(
    clusters: list[list[dict]],
) -> tuple[list[list[dict]], dict]:
    """巨大クラスタ（> _GIANT_CLUSTER_THRESHOLD 記事）を多段階で再分割する。

    _GIANT_CLUSTER_SPLIT_LEVELS の min_shared 値を順番に試み、分割できれば採用する。
    各段階の結果をさらに次の段階で分割する（再帰的に縮小）。
    最終段階でも分割できない場合は警告を記録して元クラスタを維持する。

    Returns:
        (updated_clusters, split_stats)
        split_stats keys: giant_detected, giant_split, warnings, giant_cluster_analyses
    """
    result: list[list[dict]] = []
    split_stats: dict = {
        "giant_detected": 0,
        "giant_split": 0,
        "warnings": [],
        "giant_cluster_analyses": [],
    }

    for cluster in clusters:
        if len(cluster) <= _GIANT_CLUSTER_THRESHOLD:
            result.append(cluster)
            continue

        split_stats["giant_detected"] += 1
        rep_title = cluster[0].get("title", "")[:50]

        # 分割前の giant cluster を分析して記録
        analysis = _analyze_giant_cluster(cluster)
        split_stats["giant_cluster_analyses"].append(analysis)
        logger.info(
            f"Giant cluster detected: size={analysis['cluster_size']}, "
            f"top_entities={analysis['top_entities'][:3]}, "
            f"top_keywords={analysis['top_keywords'][:3]}, "
            f"top_tokens={analysis['top_regular_tokens'][:3]}"
        )

        # 多段階分割: min_shared と cross-lang 弱アンカー閾値を段階的に引き上げる
        current = [cluster]
        for level, (min_shared, cl_weak_hits) in enumerate(
            zip(_GIANT_CLUSTER_SPLIT_LEVELS, _GIANT_CLUSTER_SPLIT_CROSS_LANG_WEAK_HITS)
        ):
            next_round: list[list[dict]] = []
            split_happened = False
            for c in current:
                if len(c) <= _GIANT_CLUSTER_THRESHOLD:
                    next_round.append(c)
                    continue
                sub, _, _ = _bfs_cluster(
                    c,
                    min_shared_keywords=min_shared,
                    min_cross_lang_weak_only_hits=cl_weak_hits,
                )
                if len(sub) > 1:
                    split_happened = True
                    split_stats["giant_split"] += 1
                    sub_sizes = sorted([len(s) for s in sub], reverse=True)
                    logger.info(
                        f"Giant split L{level+1} (min_shared={min_shared}): "
                        f"{len(c)} → {len(sub)} sub-clusters (sizes: {sub_sizes[:5]})"
                    )
                    next_round.extend(sub)
                else:
                    next_round.append(c)
            current = next_round
            if not split_happened:
                break  # これ以上の分割は見込めない

        # 最終的にまだ giant が残っていれば警告
        still_giant = [c for c in current if len(c) > _GIANT_CLUSTER_THRESHOLD]
        if still_giant:
            for g in still_giant:
                warning = (
                    f"Giant cluster ({len(g)} articles) could not be fully split "
                    f"(levels={_GIANT_CLUSTER_SPLIT_LEVELS}): '{rep_title}'"
                )
                logger.warning(warning)
                split_stats["warnings"].append(warning)
        else:
            logger.info(
                f"Giant cluster resolved: '{rep_title[:40]}' → "
                f"{len(current)} sub-clusters (max={max(len(c) for c in current)})"
            )

        result.extend(current)

    return result, split_stats


def load_articles_from_files(
    normalized_files: list[str | Path],
    already_seen_urls: set[str] | None = None,
    stats: dict | None = None,
) -> list[dict]:
    """指定されたファイルリストのみから記事を読み込む（batch 単位処理用）。

    Args:
        normalized_files: 読み込む normalized JSON ファイルのパスリスト。
        already_seen_urls: DB から取得済みの seen URL セット。含まれる URL はスキップ。
        stats: 指定した場合、source別記事数・load/drop診断を書き込む。

    Returns:
        重複排除済みの記事リスト。
    """
    articles: list[dict] = []
    seen_urls: set[str] = set(already_seen_urls or set())
    source_counts: dict[str, int] = {}
    # per-source: normalized_count (ファイル内件数), drop_reasons
    source_file_counts: dict[str, int] = {}
    source_drop_reasons: dict[str, dict[str, int]] = {}

    for file_path in normalized_files:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"[Batch] Normalized file not found: {path}")
            continue
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
            new_count = 0
            for item in items:
                src = item.get("source_name", "unknown")
                # ファイル内での件数を記録
                source_file_counts[src] = source_file_counts.get(src, 0) + 1

                url = item.get("url", "")
                # drop_reason の判定
                drop_reason: str | None = None
                if not item.get("title"):
                    drop_reason = "missing_required_fields"
                elif url and url in seen_urls:
                    drop_reason = "duplicate_url"

                if drop_reason is not None:
                    if src not in source_drop_reasons:
                        source_drop_reasons[src] = {}
                    source_drop_reasons[src][drop_reason] = (
                        source_drop_reasons[src].get(drop_reason, 0) + 1
                    )
                    if drop_reason == "duplicate_url":
                        logger.debug(f"[Dedup] Skipping seen URL: {url[:80]}")
                    continue

                if url:
                    seen_urls.add(url)
                articles.append(item)
                new_count += 1
                source_counts[src] = source_counts.get(src, 0) + 1
            logger.info(f"[Batch] Loaded {new_count} articles from {path.name}")
        except Exception as exc:
            logger.warning(f"Failed to load {path}: {exc}")

    logger.info(f"[Batch] Total articles loaded for this batch: {len(articles)}")

    # per-source load/drop サマリを構築
    all_sources = set(list(source_file_counts.keys()) + list(source_drop_reasons.keys()))
    source_load_report: dict[str, dict] = {}
    for src in sorted(all_sources):
        total = source_file_counts.get(src, 0)
        loaded = source_counts.get(src, 0)
        reasons = source_drop_reasons.get(src, {})
        dropped = sum(reasons.values())
        source_load_report[src] = {
            "normalized_count": total,
            "loaded_count": loaded,
            "dropped_count": dropped,
            "drop_reasons": reasons,
        }
        if dropped > 0:
            logger.info(
                f"[SourceLoad] {src}: normalized={total} loaded={loaded} "
                f"dropped={dropped} reasons={reasons}"
            )

    if source_counts:
        logger.info(
            "Articles by source: "
            + ", ".join(f"{k}={v}" for k, v in sorted(source_counts.items()))
        )

    if stats is not None:
        stats["source_counts"] = source_counts
        stats["source_load_report"] = source_load_report

    return articles


def load_normalized_articles(
    normalized_dir: Path = DEFAULT_NORMALIZED_DIR,
    max_age_hours: int | None = 24,
    stats: dict | None = None,
) -> list[dict]:
    """data/normalized/ 配下の *_normalized.json を読み込んで記事リストを返す。

    後方互換のために残す。新規コードは load_articles_from_files を使うこと。

    Args:
        normalized_dir: 正規化済みJSONが格納されたディレクトリ。
        max_age_hours: ファイルの更新時刻がこの時間以内のものだけ読み込む。
                       None を指定すると全ファイルを読み込む（無制限）。
        stats: 指定した場合、source別記事数を {"source_counts": {...}} として書き込む。
    """
    normalized_dir = Path(normalized_dir)
    articles: list[dict] = []
    if not normalized_dir.exists():
        logger.warning(f"normalized_dir not found: {normalized_dir}")
        return articles

    now = datetime.now(timezone.utc).timestamp()
    seen_urls: set[str] = set()
    source_counts: dict[str, int] = {}

    for path in sorted(normalized_dir.glob("*_normalized.json")):
        # 時間フィルタ: ファイルの更新時刻が max_age_hours 以内のものだけ処理
        if max_age_hours is not None:
            age_hours = (now - path.stat().st_mtime) / 3600
            if age_hours > max_age_hours:
                logger.debug(f"Skipping old file: {path.name} ({age_hours:.1f}h old)")
                continue

        try:
            items = json.loads(path.read_text(encoding="utf-8"))
            new_count = 0
            for item in items:
                url = item.get("url", "")
                if url:
                    if url in seen_urls:
                        continue  # 同一URLの重複除外
                    seen_urls.add(url)
                articles.append(item)
                new_count += 1
                src = item.get("source_name", "unknown")
                source_counts[src] = source_counts.get(src, 0) + 1
            logger.info(f"Loaded {new_count} articles from {path.name}")
        except Exception as exc:
            logger.warning(f"Failed to load {path}: {exc}")

    logger.info(f"Total articles loaded: {len(articles)}")
    if source_counts:
        logger.info(
            "Articles by source: "
            + ", ".join(f"{k}={v}" for k, v in sorted(source_counts.items()))
        )

    if stats is not None:
        stats["source_counts"] = source_counts

    return articles


def _llm_post_merge(
    clusters: list[list[dict]],
    llm_client: "LLMClient",
    budget: "BudgetTracker | None" = None,
    stats: dict | None = None,
) -> list[list[dict]]:
    """LLM を使って JP-only / EN-only クラスタのペアをさらにマージする (Pass B).

    Pass B improvements vs prior version:
      1. Predicate family guard — pairs with incompatible topic families
         (e.g. tax_fiscal vs conflict_military) are rejected BEFORE any LLM call.
      2. Batch LLM — up to _BATCH_LLM_SIZE pairs per request; strict JSON response
         with 3-way verdict: same_event | related_but_distinct | different_event.
         Only same_event verdicts result in a merge.
      3. Role-based LLM — llm_client is resolved by the caller via
         factory.get_llm_client("merge_batch"). No model strings here.
      4. Observability — pairs_considered, pairs_rejected_by_predicate_guard,
         pairs_sent_to_batch_llm, same_event_count, related_but_distinct_count,
         different_event_count, sample_rejected_reasons written into stats.

    budget が指定されている場合、バッチ単位で予算を消費・チェックする。
    """
    from src.ingestion.cross_lang_matcher import llm_batch_merge

    if not clusters:
        return clusters

    def _is_jp_only(c: list[dict]) -> bool:
        return bool(c) and all(a.get("country") == "JP" for a in c)

    def _is_en_only(c: list[dict]) -> bool:
        return bool(c) and all(a.get("country") != "JP" for a in c)

    jp_idx = [i for i, c in enumerate(clusters) if _is_jp_only(c)]
    en_idx = [i for i, c in enumerate(clusters) if _is_en_only(c)]

    if not jp_idx or not en_idx:
        if stats is not None:
            stats.setdefault("pairs_considered", 0)
            stats.setdefault("pairs_rejected_by_predicate_guard", 0)
            stats.setdefault("pairs_sent_to_batch_llm", 0)
            stats.setdefault("same_event_count", 0)
            stats.setdefault("related_but_distinct_count", 0)
            stats.setdefault("different_event_count", 0)
            stats.setdefault("parse_error_count", 0)
            stats.setdefault("budget_cut_count", 0)
            stats.setdefault("sample_rejected_reasons", [])
            stats.setdefault("same_event_examples", [])
            stats.setdefault("related_but_distinct_examples", [])
            stats.setdefault("different_event_examples", [])
        return clusters

    total_pairs = len(jp_idx) * len(en_idx)

    # ── Phase A: Similarity score pre-filter ─────────────────────────────────
    _MIN_PAIR_SCORE = 3.0
    score_filtered_pairs: list[tuple[int, int]] = []
    skip_reasons: dict[str, int] = {}
    jp_cluster_stats: list[dict] = []

    for i in jp_idx:
        jp_rep = clusters[i][0].get("title", "")[:60]
        scored_en = sorted(
            [(j, _score_pair(clusters[i], clusters[j])) for j in en_idx],
            key=lambda x: x[1],
            reverse=True,
        )
        top_en = scored_en[:_TOP_EN_PER_JP]
        rest_en = scored_en[_TOP_EN_PER_JP:]

        not_top_k_count = len(rest_en)
        skip_reasons["not_top_k"] = skip_reasons.get("not_top_k", 0) + not_top_k_count

        low_sim_count = 0
        passed_count = 0
        for j, pair_score in top_en:
            if pair_score < _MIN_PAIR_SCORE:
                skip_reasons["low_similarity"] = skip_reasons.get("low_similarity", 0) + 1
                low_sim_count += 1
                logger.debug(
                    f"LLM post-merge pair skipped (score={pair_score:.1f}<{_MIN_PAIR_SCORE}): "
                    f"'{clusters[i][0].get('title','')[:30]}' ↔ "
                    f"'{clusters[j][0].get('title','')[:30]}'"
                )
                continue
            score_filtered_pairs.append((i, j))
            passed_count += 1

        jp_cluster_stats.append({
            "jp_title": jp_rep,
            "en_candidates_total": len(en_idx),
            "not_top_k": not_top_k_count,
            "low_similarity": low_sim_count,
            "passed_to_llm": passed_count,
        })

    pairs_considered = len(score_filtered_pairs)
    logger.info(
        f"LLM post-merge: {len(jp_idx)} JP × {len(en_idx)} EN = {total_pairs} pairs "
        f"→ {pairs_considered} after similarity pre-filter "
        f"(top {_TOP_EN_PER_JP} per JP, skip_reasons={skip_reasons})"
    )

    # ── Phase B: Predicate family guard (pre-LLM hard block) ─────────────────
    # Pre-compute predicate family for each cluster involved
    all_involved: set[int] = (
        {i for i, _ in score_filtered_pairs} | {j for _, j in score_filtered_pairs}
    )
    cluster_families: dict[int, str | None] = {
        idx: _classify_predicate_family(clusters[idx]) for idx in all_involved
    }

    llm_candidate_pairs: list[tuple[int, int]] = []
    sample_rejected_reasons: list[str] = []
    predicate_rejected_count = 0

    for i, j in score_filtered_pairs:
        fam_i = cluster_families.get(i)
        fam_j = cluster_families.get(j)
        if _predicate_families_incompatible(fam_i, fam_j):
            predicate_rejected_count += 1
            skip_reasons["predicate_family_guard"] = (
                skip_reasons.get("predicate_family_guard", 0) + 1
            )
            reason_str = (
                f"'{clusters[i][0].get('title','')[:40]}' [{fam_i}] ↔ "
                f"'{clusters[j][0].get('title','')[:40]}' [{fam_j}]"
            )
            if len(sample_rejected_reasons) < 10:
                sample_rejected_reasons.append(reason_str)
            logger.debug(f"[PredicateGuard] Rejected: {reason_str}")
        else:
            llm_candidate_pairs.append((i, j))

    logger.info(
        f"[PredicateGuard] {predicate_rejected_count} pairs rejected, "
        f"{len(llm_candidate_pairs)} pairs → batch LLM"
    )

    # ── Union-Find ────────────────────────────────────────────────────────────
    parent = list(range(len(clusters)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    # ── Phase C: Batch LLM merge ──────────────────────────────────────────────
    pairs_sent = 0
    pairs_merged = 0
    same_event_count = 0
    related_but_distinct_count = 0
    different_event_count = 0
    parse_error_count = 0
    budget_exhausted = False
    same_event_examples: list[dict] = []
    related_but_distinct_examples: list[dict] = []
    different_event_examples: list[dict] = []

    # Build batch input list (skip already-merged pairs and budget-exhausted runs)
    llm_batch_input: list[dict] = []
    pair_index_map: dict[int, tuple[int, int]] = {}  # pair_id → (cluster_i, cluster_j)

    for i, j in llm_candidate_pairs:
        if find(i) == find(j):
            skip_reasons["already_covered"] = skip_reasons.get("already_covered", 0) + 1
            continue
        if budget_exhausted:
            skip_reasons["budget_cut"] = skip_reasons.get("budget_cut", 0) + 1
            continue
        pair_id = len(llm_batch_input)
        pair_index_map[pair_id] = (i, j)
        llm_batch_input.append({
            "pair_id": pair_id,
            "title_a": clusters[i][0].get("title", ""),
            "title_b": clusters[j][0].get("title", ""),
        })

    # Execute batches, one budget unit per batch
    if llm_batch_input:
        # Check if we can afford at least one batch
        if budget is not None and not budget.can_afford_cluster_pair():
            skip_reasons["budget_cut"] = (
                skip_reasons.get("budget_cut", 0) + len(llm_batch_input)
            )
            budget.skip("cluster_post_merge_batch (budget exhausted before start)")
            llm_batch_input = []  # skip all

    if llm_batch_input:
        batch_results = llm_batch_merge(
            llm_batch_input, llm_client, batch_size=_BATCH_LLM_SIZE
        )
        pairs_sent = len(llm_batch_input)

        # Record one budget call per actual LLM batch issued
        n_batches = (len(llm_batch_input) + _BATCH_LLM_SIZE - 1) // _BATCH_LLM_SIZE
        for batch_num in range(n_batches):
            if budget is not None:
                if budget.can_afford_cluster_pair():
                    budget.record_call("cluster_post_merge_batch")
                else:
                    budget.skip(f"cluster_post_merge_batch #{batch_num + 1}")

        # Process verdicts
        for result in batch_results:
            pair_id = result.get("pair_id")
            verdict = result.get("verdict", "different_event")
            reason = result.get("reason", "")
            cluster_pair = pair_index_map.get(pair_id)
            if cluster_pair is None:
                continue
            ci, cj = cluster_pair
            rep_a = clusters[ci][0].get("title", "")
            rep_b = clusters[cj][0].get("title", "")
            # Detect parse-error fallback results from llm_batch_merge
            if reason.startswith("llm_batch_error:"):
                parse_error_count += 1
            if verdict == "same_event":
                logger.info(
                    f"[BatchMerge] same_event: '{rep_a[:40]}' ↔ '{rep_b[:40]}'"
                    f" | {reason}"
                )
                union(ci, cj)
                pairs_merged += 1
                same_event_count += 1
                if len(same_event_examples) < 10:
                    same_event_examples.append({
                        "jp_title": rep_a,
                        "en_title": rep_b,
                        "verdict": verdict,
                        "reason": reason,
                    })
            elif verdict == "related_but_distinct":
                logger.debug(
                    f"[BatchMerge] related_but_distinct: '{rep_a[:40]}' ↔ '{rep_b[:40]}'"
                    f" | {reason}"
                )
                related_but_distinct_count += 1
                if len(related_but_distinct_examples) < 10:
                    related_but_distinct_examples.append({
                        "jp_title": rep_a,
                        "en_title": rep_b,
                        "verdict": verdict,
                        "reason": reason,
                    })
            else:
                logger.debug(
                    f"[BatchMerge] different_event: '{rep_a[:40]}' ↔ '{rep_b[:40]}'"
                    f" | {reason}"
                )
                different_event_count += 1
                if len(different_event_examples) < 10:
                    different_event_examples.append({
                        "jp_title": rep_a,
                        "en_title": rep_b,
                        "verdict": verdict,
                        "reason": reason,
                    })

        logger.info(
            f"[BatchMerge] same_event={same_event_count} "
            f"related_but_distinct={related_but_distinct_count} "
            f"different_event={different_event_count}"
        )

    if stats is not None:
        stats["llm_pairs_total"] = total_pairs
        stats["llm_pairs_filtered"] = pairs_considered
        stats["llm_pairs_sent"] = pairs_sent
        stats["llm_pairs_merged"] = pairs_merged
        stats["llm_skip_reasons"] = skip_reasons
        stats["jp_clusters_count"] = len(jp_idx)
        stats["en_clusters_count"] = len(en_idx)
        stats["jp_cluster_stats"] = jp_cluster_stats
        # Pass B: batch merge observability
        stats["pairs_considered"] = pairs_considered
        stats["pairs_rejected_by_predicate_guard"] = predicate_rejected_count
        stats["pairs_sent_to_batch_llm"] = pairs_sent
        stats["same_event_count"] = same_event_count
        stats["related_but_distinct_count"] = related_but_distinct_count
        stats["different_event_count"] = different_event_count
        stats["parse_error_count"] = parse_error_count
        stats["budget_cut_count"] = skip_reasons.get("budget_cut", 0)
        stats["sample_rejected_reasons"] = sample_rejected_reasons
        stats["same_event_examples"] = same_event_examples
        stats["related_but_distinct_examples"] = related_but_distinct_examples
        stats["different_event_examples"] = different_event_examples

    merged_clusters: dict[int, list[dict]] = defaultdict(list)
    for i, cluster in enumerate(clusters):
        merged_clusters[find(i)].extend(cluster)

    return list(merged_clusters.values())


def cluster_articles(
    articles: list[dict],
    min_shared_keywords: int = 1,
    llm_client: "LLMClient | None" = None,
    budget: "BudgetTracker | None" = None,
    stats: dict | None = None,
) -> list[list[dict]]:
    """タイトルのキーワード重複で記事を簡易グルーピングする (BFS クラスタリング)。

    処理フロー:
      Phase 1: _bfs_cluster() — 高頻度アンカーペナルティ付き BFS
      Phase 2: _split_giant_clusters() — 巨大クラスタ検出・再分割
      Phase 3: _llm_post_merge() — JP/EN 残存ペアを LLM で追加マージ (任意)
      Phase 4: クロスランゲージクラスタ集計

    Args:
        articles: 正規化済み記事 dict のリスト。
        min_shared_keywords: 同一クラスタとみなすための最低共通キーワード数。

    Returns:
        クラスタ (記事 dict のリスト) のリスト。
    """
    if not articles:
        return []

    n = len(articles)

    # Phase 1: BFS クラスタリング
    clusters, cross_lang_edges, cross_lang_reject_reasons = _bfs_cluster(articles, min_shared_keywords)
    clusters_after_bfs = len(clusters)
    logger.info(
        f"BFS: {n} articles → {clusters_after_bfs} clusters "
        f"(cross-lang edges: {cross_lang_edges}, "
        f"rejected: {cross_lang_reject_reasons})"
    )

    # Phase 2: クラスタサイズ分布の集計・巨大クラスタ検出と再分割
    size_dist_bfs = Counter(len(c) for c in clusters)
    max_size_bfs = max(size_dist_bfs, default=0) if size_dist_bfs else 0

    split_stats: dict = {"giant_detected": 0, "giant_split": 0, "warnings": []}
    if max_size_bfs > _GIANT_CLUSTER_THRESHOLD:
        clusters, split_stats = _split_giant_clusters(clusters)
        logger.info(
            f"After split: {len(clusters)} clusters "
            f"(detected={split_stats['giant_detected']}, "
            f"split={split_stats['giant_split']})"
        )

    clusters_before_llm = len(clusters)
    max_size_after_split = max((len(c) for c in clusters), default=0)
    size_dist_after_split = Counter(len(c) for c in clusters)

    # Phase 3: LLM による追加マージ (JP-only ↔ EN-only の未結合ペアを検証)
    llm_stats: dict = {}
    if llm_client is not None:
        clusters = _llm_post_merge(clusters, llm_client, budget=budget, stats=llm_stats)
        logger.info(f"After LLM post-merge: {len(clusters)} clusters")

    # Phase 4: クロスランゲージクラスタに含まれる記事の source 別集計
    cross_lang_source_counts: dict[str, int] = {}
    cross_lang_cluster_count = 0
    for cluster in clusters:
        jp_arts = [a for a in cluster if a.get("country") == "JP"]
        en_arts = [a for a in cluster if a.get("country") != "JP"]
        if jp_arts and en_arts:
            cross_lang_cluster_count += 1
            for art in cluster:
                src = art.get("source_name", "unknown")
                cross_lang_source_counts[src] = cross_lang_source_counts.get(src, 0) + 1

    if cross_lang_cluster_count:
        logger.info(
            f"Cross-lang clusters: {cross_lang_cluster_count} (JP+EN) → sources: "
            + ", ".join(f"{k}={v}" for k, v in sorted(cross_lang_source_counts.items()))
        )

    if stats is not None:
        stats["clusters_before_llm"] = clusters_before_llm
        stats["clusters_after_llm"] = len(clusters)
        stats["cross_lang_bfs_edges"] = cross_lang_edges
        stats["cross_lang_bfs_reject_reasons"] = cross_lang_reject_reasons
        stats["cross_lang_cluster_count"] = cross_lang_cluster_count
        stats["cross_lang_source_counts"] = cross_lang_source_counts
        # JP/EN クラスタ数（LLM post-merge 前）
        stats["jp_clusters_count_before_llm"] = sum(
            1 for c in clusters if all(a.get("country") == "JP" for a in c)
        )
        stats["en_clusters_count_before_llm"] = sum(
            1 for c in clusters if all(a.get("country") != "JP" for a in c)
        )
        # 巨大クラスタ関連: split後の分布をメインに、BFS分布も参考用に残す
        stats["cluster_size_distribution"] = dict(sorted(size_dist_after_split.items()))
        stats["cluster_size_distribution_bfs"] = dict(sorted(size_dist_bfs.items()))
        stats["max_cluster_size_bfs"] = max_size_bfs
        stats["max_cluster_size_after_split"] = max_size_after_split
        stats["giant_clusters_detected"] = split_stats["giant_detected"]
        stats["giant_clusters_split"] = split_stats["giant_split"]
        stats["giant_cluster_warnings"] = split_stats["warnings"]
        stats["giant_cluster_analyses"] = split_stats.get("giant_cluster_analyses", [])
        stats.update(llm_stats)

    return clusters


def cluster_to_event(cluster: list[dict]) -> NewsEvent:
    """記事クラスタを NewsEvent に変換する。

    - 日本記事 (country == "JP")  → japan_view に集約
    - 海外記事 (country != "JP")  → global_view に集約
    - 最も新しい published_at を代表日時として使用
    - JP 記事のタイトルを優先、なければ先頭記事
    """
    # 代表日時
    pub_dates: list[datetime] = []
    for a in cluster:
        try:
            dt = datetime.fromisoformat(a.get("published_at", ""))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            pub_dates.append(dt)
        except Exception:
            pass
    published_at = max(pub_dates) if pub_dates else datetime.now(timezone.utc)

    # 日本記事 / 海外記事に分類
    jp_articles = [a for a in cluster if a.get("country") == "JP"]
    global_articles = [a for a in cluster if a.get("country") != "JP"]

    # 代表記事: JP 優先
    primary = jp_articles[0] if jp_articles else cluster[0]
    title = primary.get("title", "")
    summary = primary.get("summary") or title

    # カテゴリ: "general" 以外で最頻出、全部 general なら general
    cat_counts = Counter(a.get("category", "general") for a in cluster)
    non_general = {k: v for k, v in cat_counts.items() if k != "general"}
    category = max(non_general, key=non_general.__getitem__) if non_general else "general"

    # ソース名 (重複除去)
    source_names = sorted({a.get("source_name", "") for a in cluster if a.get("source_name")})
    source = ", ".join(source_names)

    # タグ (順序保持・重複除去)
    seen_tags: set[str] = set()
    tags: list[str] = []
    for a in cluster:
        for t in a.get("tags", []):
            if t and t not in seen_tags:
                seen_tags.add(t)
                tags.append(t)

    # URL 一覧
    source_urls = [a["url"] for a in cluster if a.get("url")]

    # japan_view / global_view テキスト生成
    def _summarize(articles: list[dict]) -> str | None:
        parts = []
        for a in articles:
            t = a.get("title", "")
            s = a.get("summary", "")
            line = t + ("　" + s if s and s != t else "")
            if line.strip():
                parts.append(f"[{a.get('source_name', '')}] {line.strip()}")
        return "\n".join(parts) if parts else None

    japan_view = _summarize(jp_articles)
    global_view = _summarize(global_articles)

    # 後方互換: sources_jp / sources_en（name + url ペア）
    sources_jp = [
        SourceRef(
            name=a.get("source_name", ""),
            url=a.get("url", ""),
            title=a.get("title") or None,
            language=a.get("language", "ja"),
            country=a.get("country", "JP"),
            region=a.get("region", "japan"),
        )
        for a in jp_articles if a.get("source_name") or a.get("url")
    ]
    sources_en = [
        SourceRef(
            name=a.get("source_name", ""),
            url=a.get("url", ""),
            title=a.get("title") or None,
            language=a.get("language", "en"),
            country=a.get("country"),
            region=a.get("region", "global"),
        )
        for a in global_articles if a.get("source_name") or a.get("url")
    ]

    # 多地域対応: region → SourceRef のグルーピング
    _locale_groups: dict[str, list[dict]] = defaultdict(list)
    for a in cluster:
        # region が明示されていればそれを使う。なければ country==JP → japan、それ以外 → global
        r = a.get("region") or ("japan" if a.get("country") == "JP" else "global")
        _locale_groups[r].append(a)

    sources_by_locale: dict[str, list[SourceRef]] = {}
    for region_key, arts in _locale_groups.items():
        srefs = [
            SourceRef(
                name=a.get("source_name", ""),
                url=a.get("url", ""),
                title=a.get("title") or None,
                language=a.get("language"),
                country=a.get("country"),
                region=region_key,
            )
            for a in arts if a.get("source_name") or a.get("url")
        ]
        if srefs:
            sources_by_locale[region_key] = srefs

    # クラスタ ID: 代表 URL の SHA-256 先頭 12 文字
    rep_url = primary.get("url") or title
    cluster_id = "cls-" + hashlib.sha256(rep_url.encode()).hexdigest()[:12]

    return NewsEvent(
        id=cluster_id,
        title=title,
        summary=summary,
        category=category,
        source=source,
        published_at=published_at,
        tags=tags,
        japan_view=japan_view,
        global_view=global_view,
        source_urls=source_urls,
        cluster_size=len(cluster),
        sources_jp=sources_jp,
        sources_en=sources_en,
        sources_by_locale=sources_by_locale,
    )


def build_events_from_normalized(
    normalized_dir: Path = DEFAULT_NORMALIZED_DIR,
    min_shared_keywords: int = 1,
    min_cluster_size: int = 1,
    max_age_hours: int | None = 24,
    llm_client: "LLMClient | None" = None,
    budget: "BudgetTracker | None" = None,
    run_stats: dict | None = None,
    normalized_files: list[str | Path] | None = None,
    already_seen_urls: set[str] | None = None,
    garbage_filter_client: "LLMClient | None" = None,
) -> list[NewsEvent]:
    """data/normalized/ の実ニュースを読み込み、クラスタリングして NewsEvent リストを返す。

    Args:
        normalized_dir: 正規化済み JSON が格納されたディレクトリ（normalized_files 未指定時に使用）。
        min_shared_keywords: クラスタ化に必要な最低共通キーワード数。
        min_cluster_size: 何記事以上のクラスタのみを対象とするか。
        max_age_hours: この時間以内のファイルだけ読み込む (None=無制限、normalized_files 未指定時のみ有効)。
        llm_client: 提供時は LLM による JP/EN クロスランゲージ追加マージを実施。
        run_stats: 指定した場合、source別件数・JP/EN件数・クラスタリング統計を書き込む。
        normalized_files: 指定するとこのファイルリストのみを読み込む（batch モード）。
                          未指定時は normalized_dir を max_age_hours でスキャンする。
        already_seen_urls: batch モード時に DB から渡す既出 URL セット（重複排除用）。

    Returns:
        NewsEvent のリスト。スコアリング以降の処理に渡せる。
    """
    load_stats: dict = {}
    if normalized_files is not None:
        # batch モード: 指定ファイルのみ処理
        articles = load_articles_from_files(
            normalized_files,
            already_seen_urls=already_seen_urls,
            stats=load_stats,
        )
    else:
        articles = load_normalized_articles(
            normalized_dir, max_age_hours=max_age_hours, stats=load_stats
        )
    if not articles:
        logger.warning("No articles found; returning empty event list.")
        return []

    # ── Gate 1: Garbage Filter（高速スクリーニング）──────────────────────────
    # Tier 2 Lite モデルで 50件単位バッチ判定し、ノイズ記事を除去する。
    # クラスタリング（Gate 2）に渡す前に不要な記事を間引くことで
    # Semantic Merge の品質と API コストを同時に改善する。
    if garbage_filter_client is not None:
        from src.triage.garbage_filter import apply_garbage_filter
        _before_filter = len(articles)
        articles = apply_garbage_filter(articles, garbage_filter_client)
        if run_stats is not None:
            run_stats["garbage_filter_before"] = _before_filter
            run_stats["garbage_filter_after"] = len(articles)
            run_stats["garbage_filter_removed"] = _before_filter - len(articles)
        if not articles:
            logger.warning("[GarbageFilter] 全記事が除外されました。空のイベントリストを返します。")
            return []

    jp_count = sum(1 for a in articles if a.get("country") == "JP")
    en_count = len(articles) - jp_count

    # 地域別記事数（透明性）
    region_article_counts: dict[str, int] = {}
    for a in articles:
        r = a.get("region") or ("japan" if a.get("country") == "JP" else "global")
        region_article_counts[r] = region_article_counts.get(r, 0) + 1

    cluster_stats: dict = {}
    clusters = cluster_articles(
        articles,
        min_shared_keywords=min_shared_keywords,
        llm_client=llm_client,
        budget=budget,
        stats=cluster_stats,
    )

    events: list[NewsEvent] = []
    source_adopted: dict[str, int] = {}
    for cluster in clusters:
        if len(cluster) < min_cluster_size:
            continue
        try:
            events.append(cluster_to_event(cluster))
            for art in cluster:
                src = art.get("source_name", "unknown")
                source_adopted[src] = source_adopted.get(src, 0) + 1
        except Exception as exc:
            logger.warning(f"Failed to convert cluster to event: {exc}")

    logger.info(f"Built {len(events)} events from normalized articles")

    # Title presence audit: count SourceRef objects with non-null title across all events.
    _jp_with_title = sum(1 for ev in events for s in ev.sources_jp if s.title)
    _jp_total = sum(len(ev.sources_jp) for ev in events)
    _en_with_title = sum(1 for ev in events for s in ev.sources_en if s.title)
    _en_total = sum(len(ev.sources_en) for ev in events)
    logger.info(
        f"[TitleAudit] normalized→event: "
        f"JP sources {_jp_with_title}/{_jp_total} with title, "
        f"EN sources {_en_with_title}/{_en_total} with title"
    )

    if source_adopted:
        logger.info(
            "Articles adopted (in events) by source: "
            + ", ".join(f"{k}={v}" for k, v in sorted(source_adopted.items()))
        )

    if run_stats is not None:
        run_stats["source_normalized_counts"] = load_stats.get("source_counts", {})
        run_stats["source_load_report"] = load_stats.get("source_load_report", {})
        run_stats["source_adopted_counts"] = source_adopted
        run_stats["jp_article_count"] = jp_count
        run_stats["en_article_count"] = en_count
        run_stats["total_article_count"] = len(articles)
        run_stats["region_article_counts"] = region_article_counts
        run_stats["clusters_before_llm"] = cluster_stats.get("clusters_before_llm", len(clusters))
        run_stats["clusters_after_llm"] = cluster_stats.get("clusters_after_llm", len(clusters))
        run_stats["cross_lang_bfs_edges"] = cluster_stats.get("cross_lang_bfs_edges", 0)
        run_stats["cross_lang_bfs_reject_reasons"] = cluster_stats.get("cross_lang_bfs_reject_reasons", {})
        run_stats["cross_lang_cluster_count"] = cluster_stats.get("cross_lang_cluster_count", 0)
        run_stats["cross_lang_source_counts"] = cluster_stats.get("cross_lang_source_counts", {})
        run_stats["jp_clusters_count_before_llm"] = cluster_stats.get("jp_clusters_count_before_llm", 0)
        run_stats["en_clusters_count_before_llm"] = cluster_stats.get("en_clusters_count_before_llm", 0)
        # 巨大クラスタ関連
        run_stats["cluster_size_distribution"] = cluster_stats.get("cluster_size_distribution", {})
        run_stats["max_cluster_size_bfs"] = cluster_stats.get("max_cluster_size_bfs", 0)
        run_stats["max_cluster_size_after_split"] = cluster_stats.get("max_cluster_size_after_split", 0)
        run_stats["giant_clusters_detected"] = cluster_stats.get("giant_clusters_detected", 0)
        run_stats["giant_clusters_split"] = cluster_stats.get("giant_clusters_split", 0)
        run_stats["giant_cluster_warnings"] = cluster_stats.get("giant_cluster_warnings", [])
        run_stats["giant_cluster_analyses"] = cluster_stats.get("giant_cluster_analyses", [])
        # LLM 統計
        run_stats["llm_pairs_total"] = cluster_stats.get("llm_pairs_total", 0)
        run_stats["llm_pairs_filtered"] = cluster_stats.get("llm_pairs_filtered", 0)
        run_stats["llm_pairs_sent"] = cluster_stats.get("llm_pairs_sent", 0)
        run_stats["llm_pairs_merged"] = cluster_stats.get("llm_pairs_merged", 0)
        run_stats["llm_skip_reasons"] = cluster_stats.get("llm_skip_reasons", {})
        run_stats["jp_clusters_count"] = cluster_stats.get("jp_clusters_count", 0)
        run_stats["en_clusters_count"] = cluster_stats.get("en_clusters_count", 0)
        run_stats["jp_cluster_stats"] = cluster_stats.get("jp_cluster_stats", [])
        # Pass B: batch semantic merge observability
        run_stats["pairs_considered"] = cluster_stats.get("pairs_considered", 0)
        run_stats["pairs_rejected_by_predicate_guard"] = cluster_stats.get(
            "pairs_rejected_by_predicate_guard", 0
        )
        run_stats["pairs_sent_to_batch_llm"] = cluster_stats.get("pairs_sent_to_batch_llm", 0)
        run_stats["same_event_count"] = cluster_stats.get("same_event_count", 0)
        run_stats["related_but_distinct_count"] = cluster_stats.get("related_but_distinct_count", 0)
        run_stats["different_event_count"] = cluster_stats.get("different_event_count", 0)
        run_stats["parse_error_count"] = cluster_stats.get("parse_error_count", 0)
        run_stats["budget_cut_count"] = cluster_stats.get("budget_cut_count", 0)
        run_stats["sample_rejected_reasons"] = cluster_stats.get("sample_rejected_reasons", [])
        run_stats["same_event_examples"] = cluster_stats.get("same_event_examples", [])
        run_stats["related_but_distinct_examples"] = cluster_stats.get("related_but_distinct_examples", [])
        run_stats["different_event_examples"] = cluster_stats.get("different_event_examples", [])
        run_stats["events_built"] = len(events)

    return events
