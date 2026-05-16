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
import re
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

from src.shared.logger import get_logger

logger = get_logger(__name__)


# F-jp-coverage-improve (2026-05-07): ドメイン形式判定 (簡易ヒューリスティック)。
# Gemini Grounding API の chunk.web.title はドメイン形式 (例: "jiji.com") で
# 返るため、ここで「ドメインっぽい文字列」かを判定して表示名 ("Jiji News" 等) を弾く。
_DOMAIN_PATTERN = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,}$")


def _looks_like_domain(s: str) -> bool:
    """文字列がドメイン形式かを判定 (簡易ヒューリスティック)。

    Examples:
        >>> _looks_like_domain("jiji.com")
        True
        >>> _looks_like_domain("jetro.go.jp")
        True
        >>> _looks_like_domain("Jiji News")
        False
        >>> _looks_like_domain("https://jiji.com/article/123")
        False
    """
    if not s:
        return False
    return bool(_DOMAIN_PATTERN.match(s.strip().lower()))


def _normalize_domain(s: str) -> str:
    """ドメイン文字列を正規化 (lowercase + プロトコル / パス除去)。

    Examples:
        >>> _normalize_domain("Jiji.com")
        'jiji.com'
        >>> _normalize_domain("https://jiji.com/article/123")
        'jiji.com'
        >>> _normalize_domain("  jetro.go.jp  ")
        'jetro.go.jp'
    """
    s = s.strip().lower()
    s = re.sub(r"^https?://", "", s)
    s = s.split("/", 1)[0]
    return s


def _domain_matches_hierarchy(host: str, wl_domain: str) -> bool:
    """ホストと WL 登録ドメインが「同 Tier ファミリー」かを階層判定する。

    F-jp-coverage-tune-followup (2026-05-09): WL サブドメイン不一致対処。
    Grounding API が返すドメイン (例: "fnn.jp") が WL 登録ドメイン
    (例: "news.fnn.jp") と完全一致しない場合でも、ドメイン階層関係 (祖先 /
    子孫) にあれば同 Tier 扱いとする。

    マッチ条件 (どれか 1 つ満たせば True):
        - 完全一致: host == wl_domain
        - host が wl_domain のサブドメイン: host.endswith("." + wl_domain)
        - wl_domain が host のサブドメイン: wl_domain.endswith("." + host)

    過剰マッチ回避:
        - TLD 共通だけのマッチ (例: 別ドメイン同士の "co.jp" 一致) は上記 3
          条件に該当しないため False
        - 文字列部分一致 (例: "not-nikkei.com" vs "nikkei.com") も "." 区切り
          境界が無いため False
    """
    if not host or not wl_domain:
        return False
    h = host.strip().lower().lstrip(".")
    w = wl_domain.strip().lower().lstrip(".")
    if not h or not w:
        return False
    if h == w:
        return True
    if h.endswith("." + w):
        return True
    if w.endswith("." + h):
        return True
    return False


def _extract_domain_from_chunk(chunk: Any) -> Optional[str]:
    """Grounding chunk から実ソースドメインを抽出する。

    Gemini SDK のバージョンや API 仕様変更に対する防御層として、複数のフィールドを
    フォールバック順に試す。Gemini Grounding API は実ソースドメインを `chunk.web.uri`
    ではなく Vertex AI の redirect URL で返す仕様 (vertexaisearch.cloud.google.com/
    grounding-api-redirect/...)。実ドメインは現状 `chunk.web.title` に格納されている。

    戦略:
        1. chunk.web.domain (SDK 将来バージョンで実装される想定の正式 API)
        2. chunk.web.title (SDK 現行版でドメイン形式が入っている、要妥当性検証)

    Returns:
        正規化されたドメイン文字列 (例: "jiji.com")、抽出不能なら None。
    """
    web = getattr(chunk, "web", None)
    if web is None:
        return None

    # 戦略 1: 公式の domain フィールド (SDK 将来バージョンで実値を返す想定)
    domain = getattr(web, "domain", None)
    if isinstance(domain, str) and domain.strip():
        return _normalize_domain(domain)

    # 戦略 2: title フィールド (SDK 現行版でドメイン形式が格納されている)
    title = getattr(web, "title", None)
    if isinstance(title, str) and _looks_like_domain(title):
        return _normalize_domain(title)

    return None


# F-jp-coverage-llm-judgement-extraction (2026-05-14): LLM response_text 判定抽出。
# F-wl-hit-quality-audit Task D で決定的に判明した LLM judgement bypass 問題の
# 根本治療。Gemini Grounding API の chunk.web は article 粒度の URL を返さない
# 構造的限界があるが、Gemini LLM 自身は response_text で「該当する記事はあり
# ません」「異なる内容」「日付も異なります」のような明確な判定を返す。本ヘルパ
# はその判定を機械側が読み取れる形式に変換し、verify() / verify_two_stage() の
# 最終判定 (B-3 表) に反映する。
#
# 設計仕様: docs/runs/F-jp-coverage-llm-judgement-extraction/design_spec.md
# Hydrangea カズヤ哲学: 「LLM の知性に委ねる」(F-task-e-finalize / 2026-05-08)

# 「該当記事なし」シグナル (Hydrangea 嘘をつかない設計、疑わしきは低く)
_NO_MATCH_KEYWORDS: tuple[str, ...] = (
    "該当する記事はありません",
    "該当する記事は見つかりませんでした",
    "見つかりませんでした",
    "見つかりません",
    "該当しません",
    "該当なし",
    "異なる内容",
    "異なる事象",
    "別の事象",
    "日付も異なります",
    "報道されていません",
    "報道は確認できませんでした",
    "見当たりません",
)

# 「該当記事あり」シグナル
_MATCH_KEYWORDS: tuple[str, ...] = (
    "該当する記事は以下",
    "該当する記事は次の",
    "以下のURL",
    "以下の記事",
    "次の記事",
    "報道されています",
    "報道されました",
    "報道済み",
    "確認できました",
)

# 転換接続詞 (否定の否定 = uncertain 寄り)
_TURN_PARTICLES: tuple[str, ...] = ("しかし", "ただし", "一方で", "に対し")


def _extract_response_text(response: Any) -> str:
    """Gemini response から response.candidates[0].content.parts[*].text を結合。

    Gemini SDK の content.parts[*].text にモデルの自然言語応答が格納されている。
    属性欠損 / 型不一致 / イテレーション失敗時は "" にフォールバックすることで、
    既存テスト (MagicMock で content/parts を未設定) との後方互換性を確保する
    (= response_text="" → llm_judgement=None → 後方互換パスへ)。
    """
    try:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return ""
        content = getattr(candidates[0], "content", None)
        if content is None:
            return ""
        parts = getattr(content, "parts", None)
        if parts is None:
            return ""
        text_parts: list[str] = []
        for p in parts:
            t = getattr(p, "text", None)
            if isinstance(t, str):
                text_parts.append(t)
        return "".join(text_parts)
    except (TypeError, AttributeError):
        return ""


def _parse_llm_judgement(
    response_text: str,
) -> tuple[Optional[str], Optional[str]]:
    """response_text からキーワード判定で LLM 判定を抽出する。

    戻り値:
        (label, matched_text)
        - label: "match" / "no_match" / "uncertain" / None
        - matched_text: 判定該当文 (デバッグ用) or None

    None の意味 (B-3.a 後方互換):
        response_text が空 / str でない場合は None を返す。これにより既存テスト
        (MagicMock で response_text が抽出できないケース) で「LLM 判定不在 →
        WL マッチのみで判定」の後方互換パスを通る。

    パース戦略 (design_spec B-2.b / B-2.c):
        1. response_text を文単位 (。 / \\n 区切り) に分割
        2. 各文で no_match / match キーワードを検出
        3. 転換接続詞 (しかし / ただし / 一方で / に対し) が同一文にある場合は弱化
        4. 全文 no_match のみヒット → "no_match"
        5. 全文 match のみヒット → "match"
        6. 混在 or キーワード不在 → "uncertain" (空入力は None)

    Hydrangea 嘘をつかない設計 (F-task-e-finalize / カズヤ哲学):
        報道済み判定 (= silence_gap でない判定) を出すには高いバーを要求。
        曖昧 / 混在は "uncertain" に倒し、verify() 側で False (= 未報道) に
        まとめる (B-3 表)。
    """
    if not isinstance(response_text, str):
        return (None, None)
    text = response_text.strip()
    if not text:
        return (None, None)

    sentences = [s for s in re.split(r"[。\n]", text) if s.strip()]
    no_match_hits: list[str] = []
    match_hits: list[str] = []
    for sent in sentences:
        is_after_turn = any(p in sent for p in _TURN_PARTICLES)
        nm_kw = next((k for k in _NO_MATCH_KEYWORDS if k in sent), None)
        mt_kw = next((k for k in _MATCH_KEYWORDS if k in sent), None)
        if nm_kw and not mt_kw and not is_after_turn:
            no_match_hits.append(sent.strip())
        elif mt_kw and not nm_kw and not is_after_turn:
            match_hits.append(sent.strip())
        # 混在 / 転換後は無視 (= uncertain 寄り)

    if no_match_hits and not match_hits:
        return ("no_match", no_match_hits[0])
    if match_hits and not no_match_hits:
        return ("match", match_hits[0])
    return ("uncertain", None)


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
        # F-jp-coverage-tune-followup (2026-05-09): AFP 通信日本版、独立した
        # 国際通信社の日本ローカライズ拠点
        "afpbb.com",
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
        # F-jp-coverage-tune-followup (2026-05-09): Forbes Japan (経済・国際
        # ニュース) と nippon.com (笹川平和財団系の国際政治・社会論評)。
        # 両者とも独立した日本メディアで取材リソース + 大手認知度あり。
        "forbesjapan.com",
        "nippon.com",
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
    # F-jp-coverage-llm-judgement-extraction (2026-05-14): LLM judgement bypass 根本治療。
    # response_text から抽出した LLM 判定 ("match"/"no_match"/"uncertain"/None)。
    # None = 抽出不能 (後方互換パス、WL マッチのみで判定)。
    llm_judgement: Optional[str] = None
    llm_judgement_text: Optional[str] = None


@dataclass
class TwoStageVerifyResult:
    """F-jp-coverage-tune (2026-05-09): 二段階クエリ生成による系統判定結果。

    既存 JpCoverageResult とは別 dataclass にして責務分離。
    verify_two_stage() メソッド専用の戻り値型。

    stream の値:
        - "stream_1_silence_gap": 広範事件で日本未報道 (検索 2 はスキップ)
        - "stream_2_perspective_gap": 広範事件は日本報道済み + 特定角度は未報道
        - "stream_3_candidate": 両方とも日本報道済み (= F-stream-2-filter-design 行き)
        - "unknown": 検索失敗 (graceful fallback、error_message セット)
    """

    stream: str
    broad_query: str
    broad_results: Optional[dict] = None
    angle_query: Optional[str] = None
    angle_results: Optional[dict] = None
    broad_jp_coverage: bool = False
    angle_jp_coverage: Optional[bool] = None
    jp_media_hits_broad: list[str] = field(default_factory=list)
    jp_media_hits_angle: list[str] = field(default_factory=list)
    broad_matched_tier: Optional[str] = None
    angle_matched_tier: Optional[str] = None
    excluded_count_broad: int = 0
    excluded_count_angle: int = 0
    angle_query_fallback_reason: Optional[str] = None
    error_message: Optional[str] = None
    elapsed_seconds: float = 0.0
    # F-jp-coverage-llm-judgement-extraction (2026-05-14): LLM judgement bypass 根本治療。
    # broad / angle 各々の response_text から抽出した LLM 判定。
    # None = 抽出不能 (後方互換パス、WL マッチのみで判定)。
    broad_llm_judgement: Optional[str] = None
    broad_llm_judgement_text: Optional[str] = None
    angle_llm_judgement: Optional[str] = None
    angle_llm_judgement_text: Optional[str] = None


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
            urls, response_text = self._search_with_grounding(search_query)

            filtered_urls, excluded_urls = self._filter_excluded(urls)

            matched_urls, matched_domains, matched_tier = self._match_whitelist(filtered_urls)

            # F-jp-coverage-llm-judgement-extraction (2026-05-14 / Task E-fix
            # 2026-05-16): LLM judgement bypass 根本治療。response_text から LLM
            # 判定を抽出し、B-3' 表 (design_spec_v2.md) に従って WL マッチを
            # 上書きする。
            #
            # B-3' (Task E-fix で B-3 から修正):
            #   WL あり + no_match  → False (LLM 明確否定のみ安全装置として覆す)
            #   WL あり + match     → True
            #   WL あり + uncertain → True ★ (旧 B-3 は False = 過剰保守 →
            #                              Task E で Recall 崩壊。WL マッチを尊重)
            #   WL あり + None      → True (後方互換)
            #   WL なし + 不問      → False
            llm_judgement, llm_judgement_text = _parse_llm_judgement(response_text)

            wl_match = bool(matched_urls)
            if wl_match:
                if llm_judgement == "no_match":
                    # ★ LLM が明確に「該当しない」と言った時のみ覆す (安全装置)
                    has_jp_coverage = False
                else:
                    # "match" / "uncertain" / None: WL マッチを尊重 (True)
                    has_jp_coverage = True
            else:
                has_jp_coverage = False

            result = JpCoverageResult(
                event_id=event_id,
                title=title,
                has_jp_coverage=has_jp_coverage,
                matched_urls=matched_urls,
                matched_domains=matched_domains,
                matched_tier=matched_tier,
                excluded_urls=excluded_urls,
                search_query=search_query,
                llm_judgement=llm_judgement,
                llm_judgement_text=llm_judgement_text,
            )

            self._save_cache(result)

            logger.info(
                f"[JpCoverageVerifier] event={event_id} "
                f"has_jp_coverage={result.has_jp_coverage} "
                f"tier={result.matched_tier} "
                f"matched={len(result.matched_urls)} "
                f"excluded={len(result.excluded_urls)} "
                f"llm_judgement={llm_judgement}"
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

    def _search_with_grounding(self, query: str) -> tuple[list[str], str]:
        """Gemini Grounding で日本語検索し、(URL 一覧, response_text) を返す。

        F-jp-coverage-llm-judgement-extraction (2026-05-14): LLM judgement bypass
        根本治療。戻り値を `list[str]` → `tuple[list[str], str]` に拡張し、LLM の
        response_text を `_parse_llm_judgement` で読み取れるよう露出する。プロンプト
        にも回答形式指示 3 行を追加し、LLM が「該当する記事はありません」を明示
        するように促す。

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
            f"記事 URL を中心に確認してください。\n\n"
            f"# 回答形式\n"
            f"- 該当する記事が見つかった場合: 該当記事の URL を箇条書きで列挙してください\n"
            f"- 該当する記事が見つからなかった場合: 文中に「該当する記事はありません」と明示してください\n"
            f"- 検索結果に類似トピックの記事はあるが当該事象とは異なる場合: 「該当する記事はありません。類似トピック (○○) は報道されていますが、当該事象自体は報道されていません」と明示してください"
        )

        response = self.gemini_client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )

        urls: list[str] = []
        redirect_urls: list[str] = []
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            metadata = getattr(candidates[0], "grounding_metadata", None)
            if metadata is not None:
                chunks = getattr(metadata, "grounding_chunks", None) or []
                for chunk in chunks:
                    # F-jp-coverage-improve (2026-05-07): chunk.web.uri は Vertex AI
                    # の redirect URL を返す仕様のため WL マッチングには使わず、
                    # _extract_domain_from_chunk で実ドメインを取り出して urls に積む。
                    domain = _extract_domain_from_chunk(chunk)
                    if domain:
                        urls.append(f"https://{domain}")
                    web = getattr(chunk, "web", None)
                    if web is not None:
                        uri = getattr(web, "uri", None)
                        if uri:
                            redirect_urls.append(uri)

        response_text = _extract_response_text(response)

        logger.debug(
            f"[JpCoverageVerifier] Grounding returned {len(urls)} domains "
            f"(redirect_urls={len(redirect_urls)}, response_text_len={len(response_text)})"
        )
        return urls, response_text

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
        """ホワイトリストに一致する URL を抽出する。最高 Tier を判定。

        F-jp-coverage-tune-followup (2026-05-09): ドメイン階層判定に変更。
        Grounding API が返すドメイン (例: "fnn.jp") と WL 登録ドメイン
        (例: "news.fnn.jp") のサブドメイン不一致を `_domain_matches_hierarchy`
        で吸収する (= WL 側に別名を膨張させずにマッチング側で吸収)。
        """
        matched_urls: list[str] = []
        matched_domains: set[str] = set()
        highest_tier: Optional[str] = None

        for url in urls:
            host = _normalize_domain(url)
            if not host:
                continue
            url_matched = False
            for tier_name in _TIER_PRIORITY:
                domains = JP_MEDIA_WHITELIST[tier_name]
                for domain in domains:
                    if _domain_matches_hierarchy(host, domain):
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

    # ── F-jp-coverage-tune (2026-05-09): 二段階クエリ生成 ─────────────────────
    #
    # 既存 verify() / _build_search_query / _search_with_grounding /
    # _filter_excluded / _match_whitelist は完全維持。本セクションは
    # 不変原則 3 例外条件 4 つ全部 (バグ修正ではない設計拡張 / 既存メソッド完全
    # 維持 / baseline 1345 passed 維持 / カズヤ承認済) を満たす拡張。

    def verify_two_stage(
        self,
        candidate: dict[str, Any],
        particular_angle: dict[str, Any],
        *,
        timeout_seconds: float = 90.0,
        date_restrict_days: int = 60,
        analysis_llm_client: Any = None,
    ) -> TwoStageVerifyResult:
        """二段階クエリ生成による系統判別 (F-jp-coverage-tune / 2026-05-09)。

        F-13.B 既存 verify() は「広範事件のみ」を確認する設計のため、海外
        メディア独自の特定角度のみ未報道 (= 系統 2 perspective_gap) を全件
        「報道済み」と誤判定する構造的限界があった。本メソッドは **広範事件
        クエリ + 特定角度クエリ** の 2 段階で日本報道有無を機械判別する。

        Flow:
            Step 1: 広範事件クエリで日本報道確認 (大手メディア WL マッチング)
            Step 2 (Step 1 で報道済みのときのみ): 特定角度クエリで再確認

        判定:
            - Step 1 で日本未報道 → stream_1_silence_gap (Step 2 スキップ)
            - Step 1 で報道済み + Step 2 で未報道 → stream_2_perspective_gap
            - 両方とも報道済み → stream_3_candidate
            - 検索失敗 → unknown (graceful fallback、error_message セット)

        Args:
            candidate: 候補事象 dict (`title`, `summary` or `summary_excerpt`,
                       任意で `publish_date`)
            particular_angle: 特定角度 dict (`core_question` 必須)
            timeout_seconds: 各 LLM/検索呼び出しの per-call timeout (デフォルト 90s)
            date_restrict_days: 過去何日以内の報道を対象とするか (デフォルト 60)
            analysis_llm_client: 角度クエリ生成用 LLM クライアント。None なら
                                 `get_analysis_llm_client()` で遅延生成 (テスト
                                 では mock を注入)

        Returns:
            TwoStageVerifyResult
        """
        start = time.time()

        broad_query = self._build_broad_query(candidate)

        try:
            broad_urls, broad_response_text = self._search_with_grounding_two_stage(
                broad_query,
                date_restrict_days=date_restrict_days,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            logger.warning(
                f"[JpCoverageVerifier] verify_two_stage broad search failed: "
                f"{type(exc).__name__}: {exc}"
            )
            return TwoStageVerifyResult(
                stream="unknown",
                broad_query=broad_query,
                error_message=f"broad_search_error: {type(exc).__name__}: {exc}",
                elapsed_seconds=time.time() - start,
            )

        broad_filtered, broad_excluded = self._filter_excluded(broad_urls)
        broad_matched_urls, broad_matched_domains, broad_matched_tier = (
            self._match_whitelist(broad_filtered)
        )

        # F-jp-coverage-llm-judgement-extraction (2026-05-14 / Task E-fix
        # 2026-05-16): broad の LLM judgement を抽出し、B-3' 表
        # (design_spec_v2.md) に従って WL マッチを上書きする。
        # no_match のみ False で覆す (LLM 明確否定 = 安全装置)、
        # match/uncertain/None は WL マッチを尊重 (True)。
        broad_llm_judgement, broad_llm_judgement_text = _parse_llm_judgement(
            broad_response_text
        )
        broad_wl_match = bool(broad_matched_urls)
        if broad_wl_match:
            if broad_llm_judgement == "no_match":
                broad_jp_coverage = False  # ★ LLM 明確否定のみ安全装置で覆す
            else:
                # "match" / "uncertain" / None: WL マッチを尊重 (True)
                broad_jp_coverage = True
        else:
            broad_jp_coverage = False

        broad_results = {
            "urls": broad_urls,
            "matched_urls": broad_matched_urls,
            "excluded_urls": broad_excluded,
            "matched_tier": broad_matched_tier,
        }

        if not broad_jp_coverage:
            # 系統 1 確定。検索 2 はスキップ (= API コール削減)。
            logger.info(
                f"[JpCoverageVerifier] verify_two_stage stream=stream_1_silence_gap "
                f"(broad未報道、Step 2 skip、broad_llm_judgement={broad_llm_judgement})"
            )
            return TwoStageVerifyResult(
                stream="stream_1_silence_gap",
                broad_query=broad_query,
                broad_results=broad_results,
                broad_jp_coverage=False,
                jp_media_hits_broad=broad_matched_domains,
                broad_matched_tier=broad_matched_tier,
                excluded_count_broad=len(broad_excluded),
                elapsed_seconds=time.time() - start,
                broad_llm_judgement=broad_llm_judgement,
                broad_llm_judgement_text=broad_llm_judgement_text,
            )

        # Step 2: 特定角度クエリ生成 + 検索
        angle_query, fallback_reason = self._build_angle_query(
            candidate,
            particular_angle,
            analysis_llm_client=analysis_llm_client,
            timeout_seconds=timeout_seconds,
        )

        try:
            angle_urls, angle_response_text = self._search_with_grounding_two_stage(
                angle_query,
                date_restrict_days=date_restrict_days,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            logger.warning(
                f"[JpCoverageVerifier] verify_two_stage angle search failed: "
                f"{type(exc).__name__}: {exc}"
            )
            return TwoStageVerifyResult(
                stream="unknown",
                broad_query=broad_query,
                broad_results=broad_results,
                angle_query=angle_query,
                broad_jp_coverage=True,
                jp_media_hits_broad=broad_matched_domains,
                broad_matched_tier=broad_matched_tier,
                excluded_count_broad=len(broad_excluded),
                angle_query_fallback_reason=fallback_reason,
                error_message=f"angle_search_error: {type(exc).__name__}: {exc}",
                elapsed_seconds=time.time() - start,
                broad_llm_judgement=broad_llm_judgement,
                broad_llm_judgement_text=broad_llm_judgement_text,
            )

        angle_filtered, angle_excluded = self._filter_excluded(angle_urls)
        angle_matched_urls, angle_matched_domains, angle_matched_tier = (
            self._match_whitelist(angle_filtered)
        )

        # F-jp-coverage-llm-judgement-extraction (2026-05-14 / Task E-fix
        # 2026-05-16): angle の LLM judgement を抽出し、B-3' 表に従って WL
        # マッチを上書き。no_match のみ False で覆す、match/uncertain/None は
        # WL マッチを尊重 (True)。
        angle_llm_judgement, angle_llm_judgement_text = _parse_llm_judgement(
            angle_response_text
        )
        angle_wl_match = bool(angle_matched_urls)
        if angle_wl_match:
            if angle_llm_judgement == "no_match":
                angle_jp_coverage = False  # ★ LLM 明確否定のみ安全装置で覆す
            else:
                # "match" / "uncertain" / None: WL マッチを尊重 (True)
                angle_jp_coverage = True
        else:
            angle_jp_coverage = False

        stream = (
            "stream_3_candidate" if angle_jp_coverage else "stream_2_perspective_gap"
        )

        angle_results = {
            "urls": angle_urls,
            "matched_urls": angle_matched_urls,
            "excluded_urls": angle_excluded,
            "matched_tier": angle_matched_tier,
        }

        logger.info(
            f"[JpCoverageVerifier] verify_two_stage stream={stream} "
            f"(broad_jp={broad_jp_coverage}, angle_jp={angle_jp_coverage}, "
            f"broad_tier={broad_matched_tier}, angle_tier={angle_matched_tier}, "
            f"broad_llm={broad_llm_judgement}, angle_llm={angle_llm_judgement})"
        )

        return TwoStageVerifyResult(
            stream=stream,
            broad_query=broad_query,
            broad_results=broad_results,
            angle_query=angle_query,
            angle_results=angle_results,
            broad_jp_coverage=True,
            angle_jp_coverage=angle_jp_coverage,
            jp_media_hits_broad=broad_matched_domains,
            jp_media_hits_angle=angle_matched_domains,
            broad_matched_tier=broad_matched_tier,
            angle_matched_tier=angle_matched_tier,
            excluded_count_broad=len(broad_excluded),
            excluded_count_angle=len(angle_excluded),
            angle_query_fallback_reason=fallback_reason,
            elapsed_seconds=time.time() - start,
            broad_llm_judgement=broad_llm_judgement,
            broad_llm_judgement_text=broad_llm_judgement_text,
            angle_llm_judgement=angle_llm_judgement,
            angle_llm_judgement_text=angle_llm_judgement_text,
        )

    def _build_broad_query(self, candidate: dict[str, Any]) -> str:
        """広範事件クエリを生成 (既存 _build_search_query を candidate dict に
        対応させる薄いラッパ)。

        既存 verify() が使っている `_build_search_query(title, summary)` を
        そのまま流用する。`candidate` dict の `summary` / `summary_excerpt`
        どちらにも対応する。
        """
        title = candidate.get("title", "") or ""
        summary = (
            candidate.get("summary")
            or candidate.get("summary_excerpt")
            or ""
        )
        return self._build_search_query(title, summary)

    def _build_angle_query(
        self,
        candidate: dict[str, Any],
        particular_angle: dict[str, Any],
        *,
        analysis_llm_client: Any = None,
        timeout_seconds: float = 90.0,
    ) -> tuple[str, Optional[str]]:
        """`particular_angle.core_question` から日本語の特定角度検索クエリを
        LLM で生成する。

        プロンプト設計指針 (本実装で採用):
            - 6-15 単語程度の短いクエリ
            - 日本語キーワード中心 (英語タイトルそのまま使わない)
            - 固有名詞 + 角度キーワードの組み合わせ
            - 出力は単一行の検索クエリ文字列のみ (JSON / 説明文不可)

        Returns:
            (query_string, fallback_reason)
            - LLM 成功 → (LLM 出力, None)
            - LLM 失敗 / フォーマット違反 → (簡易フォールバッククエリ,
              "<理由>")
        """
        title = candidate.get("title", "") or ""
        core_question = particular_angle.get("core_question", "") or ""

        if not core_question:
            return self._fallback_angle_query(candidate, particular_angle), "no_core_question"

        if analysis_llm_client is None:
            try:
                from src.llm.factory import get_analysis_llm_client

                analysis_llm_client = get_analysis_llm_client()
            except Exception as exc:
                logger.warning(
                    f"[JpCoverageVerifier] _build_angle_query: failed to load "
                    f"analysis_llm_client ({type(exc).__name__}: {exc})"
                )
                analysis_llm_client = None

        if analysis_llm_client is None:
            return (
                self._fallback_angle_query(candidate, particular_angle),
                "no_llm_client",
            )

        prompt = (
            "あなたは日本のニュース報道を Google で検索する専門家です。\n"
            "以下のニュース事象と「特定角度」(海外メディアが独自に掘った構造分析\n"
            "の視点) について、その特定角度のみが日本のメディアで報道されている\n"
            "かを Google で確認するための短い日本語検索クエリを 1 つ作ってください。\n\n"
            f"# 元タイトル (英語可)\n{title}\n\n"
            f"# 特定角度 (core_question)\n{core_question}\n\n"
            "# 制約\n"
            "- 出力は単一行の検索クエリ文字列のみ (JSON も説明文も付けない)\n"
            "- 6-15 単語程度の日本語キーワードで構成する\n"
            "- 固有名詞 (人名 / 国名 / 組織名等) + 角度キーワードの組み合わせ\n"
            "- 広範な事件報道全般がヒットする粒度ではなく、その特定角度に絞った\n"
            "  検索結果が出る粒度にする\n"
            "- 「site:」演算子は使わない\n\n"
            "検索クエリ:"
        )

        try:
            raw_output = self._call_with_timeout(
                lambda: analysis_llm_client.generate(prompt),
                timeout_seconds,
            )
        except Exception as exc:
            logger.warning(
                f"[JpCoverageVerifier] _build_angle_query LLM failed, "
                f"using fallback: {type(exc).__name__}: {exc}"
            )
            return (
                self._fallback_angle_query(candidate, particular_angle),
                f"llm_error: {type(exc).__name__}",
            )

        if not isinstance(raw_output, str):
            return (
                self._fallback_angle_query(candidate, particular_angle),
                "llm_non_string_output",
            )

        # 単一行に正規化
        query = raw_output.strip().split("\n", 1)[0].strip()
        # 余計な接頭辞を除去 (`検索クエリ: xxx` で返ってくるケース対策)
        query = re.sub(r"^[「『\"\'`]?(検索クエリ|クエリ|Query|query)[:：]\s*", "", query)
        query = query.strip("「」『』\"' \t`")

        # フォーマットチェック: JSON / コードブロック / 空文字は fallback
        if not query or query.startswith("{") or query.startswith("```"):
            logger.warning(
                f"[JpCoverageVerifier] _build_angle_query bad format, "
                f"using fallback: raw={raw_output[:80]!r}"
            )
            return (
                self._fallback_angle_query(candidate, particular_angle),
                "bad_format",
            )

        return query, None

    def _fallback_angle_query(
        self,
        candidate: dict[str, Any],
        particular_angle: dict[str, Any],
    ) -> str:
        """LLM 失敗時の簡易フォールバッククエリ。

        candidate.title + particular_angle.core_question 先頭 20 文字 で構成。
        """
        title = (candidate.get("title", "") or "").strip()
        core = (particular_angle.get("core_question", "") or "").strip()
        snippet = core[:20]
        parts = [p for p in [title, snippet] if p]
        return " ".join(parts) if parts else (title or "")

    def _search_with_grounding_two_stage(
        self,
        query: str,
        *,
        date_restrict_days: int = 60,
        timeout_seconds: float = 90.0,
    ) -> tuple[list[str], str]:
        """二段階用 Grounding 検索 (per-call timeout)。

        既存 `_search_with_grounding` は変更せず、新規バリアントとして実装。

        F-jp-coverage-tune Step 4 (2026-05-09) で **dateRestrict プロンプト
        埋め込みを除去**: Gemini Grounding API は dateRestrict パラメータを
        直接サポートしないため、当初プロンプト本文に過去 N 日制約を埋め込んで
        いたが、Step 3 精度測定で broad search の under-recall (Recall covered
        31.58%) が dateRestrict プロンプト埋め込みの副作用 (= LLM が日付情報
        のない記事を一律弾く / 検索結果ゼロ多発) に起因する仮説を検証する目的で、
        プロンプトから日付制約を撤去。`date_restrict_days` パラメータ自体は
        後方互換のため残置 (Grounding API 公式サポート時の再導入を想定)。

        F-jp-coverage-llm-judgement-extraction (2026-05-14): LLM judgement bypass
        根本治療。戻り値を `list[str]` → `tuple[list[str], str]` に拡張し、LLM の
        response_text を呼び出し側 (verify_two_stage) で `_parse_llm_judgement`
        できるようにする。プロンプトにも回答形式指示 3 行を追加。
        """
        if self.gemini_client is None:
            raise RuntimeError("gemini_client is not configured")

        from google.genai import types

        # date_restrict_days は受け取るが、プロンプト本文には埋め込まない (副作用回避)
        _ = date_restrict_days  # noqa: F841 — back-compat 用、将来 API サポート時に再導入

        prompt = (
            f"次のニュースが日本のメディアで報道されているか、"
            f"日本語の Web 検索で確認してください。\n\n"
            f"検索クエリ: {query}\n\n"
            f"日本のメディア (新聞、テレビ局、通信社等) の記事 URL を中心に確認してください。\n\n"
            f"# 回答形式\n"
            f"- 該当する記事が見つかった場合: 該当記事の URL を箇条書きで列挙してください\n"
            f"- 該当する記事が見つからなかった場合: 文中に「該当する記事はありません」と明示してください\n"
            f"- 検索結果に類似トピックの記事はあるが当該事象とは異なる場合: 「該当する記事はありません。類似トピック (○○) は報道されていますが、当該事象自体は報道されていません」と明示してください"
        )

        def _do_call() -> tuple[list[str], str]:
            response = self.gemini_client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )

            urls: list[str] = []
            redirect_urls: list[str] = []
            candidates = getattr(response, "candidates", None) or []
            if candidates:
                metadata = getattr(candidates[0], "grounding_metadata", None)
                if metadata is not None:
                    chunks = getattr(metadata, "grounding_chunks", None) or []
                    for chunk in chunks:
                        domain = _extract_domain_from_chunk(chunk)
                        if domain:
                            urls.append(f"https://{domain}")
                        web = getattr(chunk, "web", None)
                        if web is not None:
                            uri = getattr(web, "uri", None)
                            if uri:
                                redirect_urls.append(uri)

            response_text = _extract_response_text(response)

            logger.debug(
                f"[JpCoverageVerifier] two_stage Grounding returned {len(urls)} domains "
                f"(redirect_urls={len(redirect_urls)}, response_text_len={len(response_text)}, "
                f"query={query!r})"
            )
            return urls, response_text

        return self._call_with_timeout(_do_call, timeout_seconds)

    @staticmethod
    def _call_with_timeout(callable_: Callable[[], Any], timeout_seconds: float) -> Any:
        """同期関数を per-call timeout 付きで実行する。

        ThreadPoolExecutor.future.result(timeout=N) で実装。timeout 超過時
        はワーカースレッドはバックグラウンドで動き続けるが (Python の
        GIL/協調キャンセルの制約)、メインフローは即座に TimeoutError として
        graceful fallback できる。
        """
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(callable_)
            try:
                return future.result(timeout=timeout_seconds)
            except FutureTimeoutError as exc:
                future.cancel()
                raise TimeoutError(
                    f"call exceeded timeout={timeout_seconds}s"
                ) from exc
