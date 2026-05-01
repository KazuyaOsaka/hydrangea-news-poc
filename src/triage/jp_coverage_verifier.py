"""F-13.B: 日本の大手メディアでの報道有無を Web 検証する。

Hydrangea のミッション:
  「大手メディアが報じない海外の重要事実を日本人に届ける」

このため、Web 検証では「大手メディア (新聞・テレビ・通信社・主要ビジネスメディア)」
の報道有無のみを判定する。個人ブログ・SNS・アグリゲータは判定対象外。

判定基準:
  含める:
    - 編集部が独立している
    - 一次情報を取材できる規模
    - 誤報時の責任を取る組織
    - 国民への情報浸透力がある (大手認知)

  除外:
    - Yahoo!ニュース等のアグリゲータ
    - 個人ブログ・SNS
    - ハフポスト等の個人寄稿中心メディア
    - ゴシップ・タブロイド誌
    - 専門誌 (ナショジオ等、報道とは性質が違う)

利用方法:
    >>> from src.triage.jp_coverage_verifier import JpCoverageVerifier
    >>> verifier = JpCoverageVerifier(gemini_client=client, db_path=db_path)
    >>> result = verifier.verify(event_id, title, summary)
    >>> if result.has_jp_coverage:
    ...     # 大手メディアで報道済み → divergence パターンで生成
    ... else:
    ...     # 大手メディア未報道 → blind_spot_global として動画化
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.shared.logger import get_logger

logger = get_logger(__name__)


# 大手メディアホワイトリスト (Web 検証用)
JP_MEDIA_WHITELIST: dict[str, list[str]] = {
    # Tier 1: 全国紙・公共放送
    "tier_1_newspaper": [
        "nhk.or.jp", "nhk.jp",
        "nikkei.com",
        "asahi.com",
        "yomiuri.co.jp",
        "sankei.com",
        "mainichi.jp",
        "tokyo-np.co.jp",
    ],
    # Tier 2: 通信社・国際メディア日本版
    "tier_2_wire_service": [
        "47news.jp",
        "nordot.app",
        "kyodonews.jp", "kyodonews.net",
        "jiji.com",
        "bloomberg.co.jp",
        "jp.reuters.com",
    ],
    # Tier 3: 大手テレビ局・ニュース番組
    "tier_3_broadcaster": [
        "news.tv-asahi.co.jp",
        "news.tbs.co.jp",
        "news.fnn.jp",
        "news.ntv.co.jp",
        "news.tv-tokyo.co.jp",
        "news.bs-tbs.co.jp",
        "bs-tvtokyo.co.jp",
    ],
    # Tier 4: 大手ビジネス・国際情勢メディア
    "tier_4_business": [
        "newsweekjapan.jp",
        "toyokeizai.net",
        "diamond.jp",
        "president.jp",
        "bunshun.jp",
        "business.nikkei.com",
        "globe.asahi.com",
    ],
}

# 明示的に除外するドメイン (誤判定防止)
# これらに含まれる URL は「大手メディア報道」と判定しない。
JP_MEDIA_EXCLUDED: list[str] = [
    "news.yahoo.co.jp",      # アグリゲータ
    "huffingtonpost.jp",     # 個人寄稿中心
    "biz-journal.jp",        # タブロイド寄り
    "gendai.media",          # 雑誌寄り、コラム主体
    "wedge.ismedia.jp",      # オピニオン主体
    "smart-flash.jp",        # ゴシップ誌
    "natgeo.nikkeibp.co.jp", # 専門誌 (科学・地理)
    "note.com",              # 個人ブログプラットフォーム
    "ameblo.jp",             # 個人ブログ
    "hatena.ne.jp",          # 個人ブログ
    "blog.livedoor.jp",      # 個人ブログ
    "twitter.com", "x.com",  # SNS
    "facebook.com",          # SNS
    "instagram.com",         # SNS
    "youtube.com",           # 動画 (個人投稿が多い)
]


# Tier 順序 (上が優先 = 高 Tier)
_TIER_PRIORITY: list[str] = [
    "tier_1_newspaper",
    "tier_2_wire_service",
    "tier_3_broadcaster",
    "tier_4_business",
]


@dataclass
class JpCoverageResult:
    """Web 検証の結果。"""

    event_id: str
    title: str
    has_jp_coverage: bool
    matched_urls: list[str] = field(default_factory=list)
    matched_domains: list[str] = field(default_factory=list)
    matched_tier: Optional[str] = None  # "tier_1_newspaper" / ... / None
    excluded_urls: list[str] = field(default_factory=list)
    search_query: str = ""
    raw_grounding_response: Optional[str] = None
    error: Optional[str] = None
    cached: bool = False
    cached_at: Optional[str] = None


class JpCoverageVerifier:
    """日本の大手メディアでの報道有無を Web 検索で検証する。

    Gemini Grounding (Google Search 連携) を呼び、戻ってきた URL を
    ホワイトリスト (大手 27 ドメイン) と除外リスト (アグリゲータ・SNS 等)
    に照らし合わせて「大手メディア報道有無」を判定する。

    24h キャッシュで重複検証を抑制する (SQLite jp_coverage_cache テーブル)。
    """

    CACHE_TTL_HOURS_DEFAULT = 24

    def __init__(
        self,
        gemini_client,
        db_path: Path,
        cache_ttl_hours: int = CACHE_TTL_HOURS_DEFAULT,
        model: str = "gemini-2.5-flash",
    ) -> None:
        """
        Args:
            gemini_client: Gemini クライアント (google.genai.Client 互換)。
                None の場合は API 呼び出し時にエラーとして扱う。
            db_path: SQLite DB パス (キャッシュ用)
            cache_ttl_hours: キャッシュ有効時間
            model: Grounding 検索に使うモデル名
        """
        self.gemini_client = gemini_client
        self.db_path = db_path
        self.cache_ttl_hours = cache_ttl_hours
        self.model = model

    def verify(self, event_id: str, title: str, summary: str = "") -> JpCoverageResult:
        """日本の大手メディアでの報道有無を検証する。

        Flow:
            1. キャッシュ確認 (24 時間以内なら使用)
            2. Gemini Grounding で日本語検索
            3. URL 抽出
            4. 除外ドメイン除去 (Yahoo!ニュース等)
            5. ホワイトリストマッチング
            6. Tier 判定
            7. キャッシュに保存
        """
        # キャッシュ確認
        cached = self._get_cached(event_id)
        if cached is not None:
            cached.title = cached.title or title
            logger.info(
                f"[JpCoverageVerifier] Cache hit for event={event_id} "
                f"(has_jp_coverage={cached.has_jp_coverage}, tier={cached.matched_tier})"
            )
            return cached

        # 検索クエリ構築
        search_query = self._build_search_query(title, summary)

        try:
            urls = self._search_with_grounding(search_query)

            filtered_urls, excluded_urls = self._filter_excluded(urls)

            matched_urls, matched_domains, matched_tier = self._match_whitelist(filtered_urls)

            result = JpCoverageResult(
                event_id=event_id,
                title=title,
                has_jp_coverage=bool(matched_urls),
                matched_urls=matched_urls,
                matched_domains=matched_domains,
                matched_tier=matched_tier,
                excluded_urls=excluded_urls,
                search_query=search_query,
            )

            self._save_cache(result)

            logger.info(
                f"[JpCoverageVerifier] event={event_id} "
                f"has_jp_coverage={result.has_jp_coverage} "
                f"tier={result.matched_tier} "
                f"matched={len(result.matched_urls)} "
                f"excluded={len(result.excluded_urls)}"
            )
            return result

        except Exception as exc:
            logger.error(
                f"[JpCoverageVerifier] Failed for event={event_id}: "
                f"{type(exc).__name__}: {exc}"
            )
            # エラー時は「報道あり」として安全側に倒す
            # (誤って blind_spot 判定して誤情報を出すリスクを避ける)
            return JpCoverageResult(
                event_id=event_id,
                title=title,
                has_jp_coverage=True,
                search_query=search_query,
                error=f"{type(exc).__name__}: {exc}",
            )

    def _build_search_query(self, title: str, summary: str) -> str:
        """日本語検索クエリを構築する。"""
        # シンプル実装: タイトル + "日本 報道" で検索。
        # Gemini Grounding は日本語ページを優先取得するため、これで十分。
        return f"{title} 日本 報道"

    def _search_with_grounding(self, query: str) -> list[str]:
        """Gemini Grounding で日本語検索し、URL 一覧を返す。

        Gemini API Grounding 公式ドキュメント:
          https://ai.google.dev/gemini-api/docs/google-search
        """
        if self.gemini_client is None:
            raise RuntimeError("gemini_client is not configured")

        from google.genai import types

        prompt = (
            f"次のニュースが日本のメディアで報道されているか、"
            f"日本語の Web 検索で確認してください。\n\n"
            f"検索クエリ: {query}\n\n"
            f"検索結果から、日本のメディア (新聞、テレビ局、通信社等) の "
            f"記事 URL を中心に確認してください。"
        )

        response = self.gemini_client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )

        urls: list[str] = []
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            metadata = getattr(candidates[0], "grounding_metadata", None)
            if metadata is not None:
                chunks = getattr(metadata, "grounding_chunks", None) or []
                for chunk in chunks:
                    web = getattr(chunk, "web", None)
                    if web is not None:
                        uri = getattr(web, "uri", None)
                        if uri:
                            urls.append(uri)

        logger.debug(f"[JpCoverageVerifier] Grounding returned {len(urls)} URLs")
        return urls

    def _filter_excluded(self, urls: list[str]) -> tuple[list[str], list[str]]:
        """除外ドメインを除去する。"""
        filtered: list[str] = []
        excluded: list[str] = []
        for url in urls:
            url_lower = url.lower()
            if any(domain in url_lower for domain in JP_MEDIA_EXCLUDED):
                excluded.append(url)
            else:
                filtered.append(url)
        return filtered, excluded

    def _match_whitelist(
        self, urls: list[str]
    ) -> tuple[list[str], list[str], Optional[str]]:
        """ホワイトリストに一致する URL を抽出する。最高 Tier を判定。"""
        matched_urls: list[str] = []
        matched_domains: set[str] = set()
        highest_tier: Optional[str] = None

        for url in urls:
            url_lower = url.lower()
            url_matched = False
            for tier_name in _TIER_PRIORITY:
                domains = JP_MEDIA_WHITELIST[tier_name]
                for domain in domains:
                    if domain in url_lower:
                        if not url_matched:
                            matched_urls.append(url)
                            url_matched = True
                        matched_domains.add(domain)
                        if highest_tier is None or _TIER_PRIORITY.index(tier_name) < _TIER_PRIORITY.index(highest_tier):
                            highest_tier = tier_name
                        break  # 同じ URL を同 Tier 内で重複カウントしない
                if url_matched:
                    break  # この URL は最初に当たった Tier で確定

        return matched_urls, sorted(matched_domains), highest_tier

    def _get_cached(self, event_id: str) -> Optional[JpCoverageResult]:
        """24h キャッシュから結果を取得する。"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute(
                    """
                    SELECT
                        has_jp_coverage, matched_tier, matched_urls, matched_domains,
                        excluded_urls, search_query, cached_at
                    FROM jp_coverage_cache
                    WHERE event_id = ?
                    """,
                    (event_id,),
                )
                row = cursor.fetchone()
        except sqlite3.OperationalError as exc:
            # テーブル未作成等で読み出しに失敗してもキャッシュミス扱いにする
            logger.warning(f"[JpCoverageVerifier] cache read failed: {exc}")
            return None

        if row is None:
            return None

        cached_at_str = row[6]
        try:
            cached_at = datetime.fromisoformat(cached_at_str)
        except (TypeError, ValueError):
            return None

        if datetime.now() - cached_at > timedelta(hours=self.cache_ttl_hours):
            return None

        return JpCoverageResult(
            event_id=event_id,
            title="",
            has_jp_coverage=bool(row[0]),
            matched_tier=row[1],
            matched_urls=json.loads(row[2]) if row[2] else [],
            matched_domains=json.loads(row[3]) if row[3] else [],
            excluded_urls=json.loads(row[4]) if row[4] else [],
            search_query=row[5] or "",
            cached=True,
            cached_at=cached_at_str,
        )

    def _save_cache(self, result: JpCoverageResult) -> None:
        """検証結果をキャッシュに保存する。"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO jp_coverage_cache (
                        event_id, has_jp_coverage, matched_tier, matched_urls,
                        matched_domains, excluded_urls, search_query, cached_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result.event_id,
                        int(result.has_jp_coverage),
                        result.matched_tier,
                        json.dumps(result.matched_urls, ensure_ascii=False),
                        json.dumps(result.matched_domains, ensure_ascii=False),
                        json.dumps(result.excluded_urls, ensure_ascii=False),
                        result.search_query,
                        datetime.now().isoformat(),
                    ),
                )
                conn.commit()
        except sqlite3.OperationalError as exc:
            logger.warning(f"[JpCoverageVerifier] cache save failed: {exc}")
