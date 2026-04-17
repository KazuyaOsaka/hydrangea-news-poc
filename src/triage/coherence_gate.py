"""coherence_gate.py — Semantic Coherence Gate for JP↔Global candidate validation (Pass 2B/2C).

Purpose:
  Before final slot-1 generation, ensure that linked_jp_global and blind_spot_global
  candidates are about the same or meaningfully related real-world story.
  This prevents editorially incoherent selections where a domestic-routine JP article
  (e.g., PM daily schedule) is paired with unrelated overseas sources.

Algorithm (deterministic, LLM-free):
  Signals combined into a 0.0–1.0 score:
    - Title keyword overlap (JP↔EN entity matching via known translation pairs)
    - Named entity overlap (katakana words → topic keywords)
    - Number / year overlap
    - Topic bucket consistency
    - Japan-vs-overseas source compatibility
  Additional modifiers:
    - Domestic-routine blacklist penalty (halves score when JP title matches)
    - Diary-style hard-raise of threshold when a dated schedule item is detected
    - Contradiction penalty for obviously mismatched topic domains

Gate thresholds:
  COHERENCE_GATE_THRESHOLD        = 0.25 — minimum for non-blacklisted items
  BLACKLIST_COHERENCE_THRESHOLD   = 0.50 — minimum for domestic-routine items (raised from 0.45)
  DIARY_COHERENCE_THRESHOLD       = 0.65 — minimum for dated diary/schedule items (新規)

Domestic-routine blacklist (Pass 2C hardening):
  Matches patterns in the JP article title AND in individual JP source titles.
  Items on this list are NOT forbidden globally — they can still appear as jp_only
  or investigate_more.  They are only blocked from linked_jp_global / blind_spot_global
  if the overseas evidence does not clearly reference the same core event.

Diary-style detection (Pass 2C hardening):
  A "diary-style" item is one where:
    - A domestic-routine pattern matches, AND
    - A specific date (YYYY年M月D日) appears in the JP title or a JP source title.
  These items require a significantly higher coherence score because the connection
  between a daily-schedule item and overseas sources almost never constitutes a
  genuine editorial blind-spot story.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.shared.logger import get_logger

if TYPE_CHECKING:
    from src.shared.models import ScoredEvent

logger = get_logger(__name__)

# ── Gate Thresholds ────────────────────────────────────────────────────────────

COHERENCE_GATE_THRESHOLD: float = 0.25
BLACKLIST_COHERENCE_THRESHOLD: float = 0.50   # raised from 0.45 in Pass 2C
DIARY_COHERENCE_THRESHOLD: float = 0.65       # new in Pass 2C: dated schedule items

# ── Domestic Routine Blacklist ─────────────────────────────────────────────────
# JP article title patterns that strongly suggest a domestic-routine article.
# Checked against BOTH the event title and individual JP source article titles.

DOMESTIC_ROUTINE_PATTERNS: dict[str, re.Pattern[str]] = {
    "首相動静": re.compile(r"首相動静|官房長官動静|大臣動静|副大臣動静"),
    "首相日程": re.compile(r"首相日程|首相会見定例|首相(?:定例|臨時)会見|官房長官(?:定例|臨時)会見"),
    "人事異動": re.compile(
        r"(?:役員|幹部|社長|専務|常務|部長|局長|次長|課長|支店長)(?:人事|就任|退任|辞任|異動)|人事異動"
    ),
    "決算短信": re.compile(
        r"決算短信|四半期(?:報告|決算)|業績(?:予想の修正|修正のお知らせ)|有価証券報告書"
    ),
    "定例開示": re.compile(
        r"(?:定例|月次|週次)(?:開示|報告|データ|統計)|開示のお知らせ"
    ),
    "スポーツ結果": re.compile(
        r"(?:試合|ゲーム|戦|マッチ|レース).*(?:結果|スコア|得点|勝利|敗北|引き分け)|"
        r"(?:結果|スコア|得点|勝利|敗北|引き分け).*(?:試合|ゲーム|戦|マッチ)|"
        r"\d+[-–]\d+(?:で|の)(?:勝|敗|分|完封)"
    ),
    "事故速報": re.compile(
        r"(?:交通)?事故.*(?:速報|第一報)|火災.*(?:速報|発生)|速報.*(?:事故|火災|崩落|落下)"
    ),
    "訃報": re.compile(r"訃報|(?:氏|さん|先生)?が(?:死去|逝去|ご逝去)|享年\s*\d+"),
    "市況": re.compile(
        r"(?:日経平均|TOPIX|東証).*(?:終値|前日比)|今日の(?:株式市況|為替|外為)|市況.*(?:終値|引け値)"
    ),
}

# ── Diary-style date detector ─────────────────────────────────────────────────
# Matches a specific calendar date in JP text (YYYY年M月D日 or similar).
# Presence of this pattern in a blacklisted title indicates a dated diary entry
# (e.g., "高市首相動静 2026年4月14日") rather than a genuinely newsworthy event.

_DIARY_DATE_PATTERN: re.Pattern[str] = re.compile(r'(?:19|20)\d{2}年\d{1,2}月\d{1,2}日')

# ── JP → EN Translation Map ────────────────────────────────────────────────────

_JP_EN_MAP: dict[str, frozenset[str]] = {
    # Countries / regions
    "中国": frozenset({"china", "chinese", "beijing"}),
    "米国": frozenset({"us", "usa", "america", "american", "united states", "washington"}),
    "アメリカ": frozenset({"us", "usa", "america", "american", "united states", "washington"}),
    "日本": frozenset({"japan", "japanese", "tokyo"}),
    "ロシア": frozenset({"russia", "russian", "moscow", "kremlin"}),
    "ウクライナ": frozenset({"ukraine", "ukrainian", "kyiv"}),
    "台湾": frozenset({"taiwan", "taiwanese"}),
    "韓国": frozenset({"korea", "korean", "south korea", "seoul"}),
    "北朝鮮": frozenset({"north korea", "north korean", "pyongyang", "kim"}),
    "フランス": frozenset({"france", "french", "paris"}),
    "ドイツ": frozenset({"germany", "german", "berlin"}),
    "イギリス": frozenset({"uk", "britain", "british", "england", "london"}),
    "イスラエル": frozenset({"israel", "israeli"}),
    "イラン": frozenset({"iran", "iranian", "tehran"}),
    "インド": frozenset({"india", "indian", "modi", "delhi"}),
    "サウジ": frozenset({"saudi", "riyadh", "aramco"}),
    "トルコ": frozenset({"turkey", "turkish", "ankara", "erdogan"}),
    "ブラジル": frozenset({"brazil", "brazilian"}),
    "欧州": frozenset({"europe", "european", "eu", "brussels"}),
    "中東": frozenset({"middle east"}),
    # Economic topics
    "経済": frozenset({"economy", "economic", "economics", "gdp", "growth"}),
    "貿易": frozenset({"trade", "import", "export", "tariff"}),
    "関税": frozenset({"tariff", "tariffs", "trade", "duty"}),
    "半導体": frozenset({"semiconductor", "chip", "chips", "wafer"}),
    "エネルギー": frozenset({"energy", "power", "oil", "gas"}),
    "石油": frozenset({"oil", "petroleum", "opec", "crude"}),
    "ガス": frozenset({"gas", "lng", "natural gas"}),
    "株式": frozenset({"stock", "stocks", "shares", "equity", "market"}),
    "為替": frozenset({"currency", "exchange rate", "forex", "yen", "dollar"}),
    "円": frozenset({"yen", "jpy"}),
    "インフレ": frozenset({"inflation", "prices", "cpi"}),
    "金利": frozenset({"interest rate", "rates", "fed", "boj"}),
    "日銀": frozenset({"boj", "bank of japan", "ueda"}),
    "連邦準備": frozenset({"fed", "federal reserve", "powell"}),
    # Political topics
    "首相": frozenset({"prime minister", "premier", "pm"}),
    "大統領": frozenset({"president", "presidential"}),
    "議会": frozenset({"congress", "parliament", "senate", "legislature"}),
    "選挙": frozenset({"election", "vote", "ballot", "poll"}),
    "外交": frozenset({"diplomacy", "diplomatic", "foreign policy"}),
    "制裁": frozenset({"sanctions", "sanction"}),
    "軍事": frozenset({"military", "army", "defense", "troops", "forces"}),
    "核": frozenset({"nuclear", "nuke"}),
    "ミサイル": frozenset({"missile", "rocket", "icbm"}),
    # Technology / AI
    "人工知能": frozenset({"ai", "artificial intelligence", "machine learning"}),
    "AI": frozenset({"ai", "artificial intelligence"}),
    "技術": frozenset({"technology", "tech"}),
    "宇宙": frozenset({"space", "nasa", "rocket", "satellite"}),
    # Climate / environment
    "気候": frozenset({"climate", "warming", "emission", "carbon"}),
    "地震": frozenset({"earthquake", "quake", "seismic", "tremor"}),
    "台風": frozenset({"typhoon", "cyclone", "storm", "hurricane"}),
    # Corporate / finance
    "合併": frozenset({"merger", "acquisition", "deal", "takeover"}),
    "買収": frozenset({"acquisition", "takeover", "buyout"}),
    "破綻": frozenset({"bankrupt", "bankruptcy", "collapse", "default"}),
    "上場": frozenset({"ipo", "listing", "public"}),
    "投資": frozenset({"investment", "invest", "investor"}),
}

# ── Generic token lists ────────────────────────────────────────────────────────

_GENERIC_EN = frozenset({
    "the", "a", "an", "and", "or", "in", "on", "at", "of", "to", "for",
    "is", "was", "are", "were", "has", "have", "had", "says", "said",
    "news", "report", "update", "latest", "new", "japan", "japanese",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "january", "february", "march", "april",
    "may", "june", "july", "august", "september", "october", "november",
    "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug",
    "sep", "oct", "nov", "dec", "amid", "after", "over", "from",
    "with", "as", "by", "be", "will", "could", "would", "should",
    "amid", "says", "say", "its", "their", "they", "it", "he", "she",
    "his", "her", "we", "our", "amid", "amid",
})

_GENERIC_JP_PATTERNS = re.compile(
    r"^(?:の|は|が|を|に|で|と|も|や|か|より|から|まで|など|について|として|による|において|"
    r"における|にとって|に関して|に関する|にあたって|ニュース|速報|報道|国内|国際|今日|本日)$"
)


# ── Data class for coherence result ───────────────────────────────────────────

@dataclass
class CoherenceResult:
    """Output of the semantic coherence gate check."""
    score: float                          # 0.0–1.0 final coherence score
    blacklist_flags: list[str] = field(default_factory=list)   # matched domestic-routine patterns
    block_reason: str | None = None       # None = gate passed; str = reason for blocking
    score_breakdown: dict[str, float] = field(default_factory=dict)
    # ── Pass 2C: human-readable explanation ───────────────────────────────────
    jp_entities: list[str] = field(default_factory=list)       # extracted JP keywords/entities
    overseas_entities: list[str] = field(default_factory=list) # extracted EN keywords/entities
    overlap_signals: list[str] = field(default_factory=list)   # what actually matched
    is_diary_style: bool = False           # True = dated schedule item
    # ── Pass 2D-1: input quality counters ─────────────────────────────────────
    jp_titles_present_count: int = 0       # JP sources with non-null title
    overseas_titles_present_count: int = 0 # overseas sources with non-null title
    missing_title_sources_count: int = 0   # sources with null title (all locales)


# ── Private helpers ────────────────────────────────────────────────────────────

def _collect_jp_source_titles(se: "ScoredEvent") -> list[str]:
    """Return non-empty titles from all JP source articles."""
    titles: list[str] = []
    for src in se.event.sources_jp:
        if src.title:
            titles.append(src.title)
    if se.event.sources_by_locale:
        for ref in se.event.sources_by_locale.get("japan", []):
            if ref.title and ref.title not in titles:
                titles.append(ref.title)
    return titles


def _detect_domestic_routine(jp_title: str) -> list[str]:
    """Return list of DOMESTIC_ROUTINE_PATTERNS keys that match the JP title."""
    flags: list[str] = []
    for key, pattern in DOMESTIC_ROUTINE_PATTERNS.items():
        if pattern.search(jp_title):
            flags.append(key)
    return flags


def _detect_domestic_routine_extended(
    jp_title: str, jp_source_titles: list[str]
) -> list[str]:
    """Check the event title AND individual JP source article titles.

    Returns deduplicated list of matched blacklist keys.  Checking source-level
    titles catches cases where the cluster/event title is a merged English title
    but the underlying JP article is still a daily-schedule item.
    """
    all_flags: set[str] = set(_detect_domestic_routine(jp_title))
    for src_title in jp_source_titles:
        if src_title:
            all_flags.update(_detect_domestic_routine(src_title))
    return sorted(all_flags)


def _detect_diary_style(
    jp_title: str, jp_source_titles: list[str], blacklist_flags: list[str]
) -> bool:
    """Return True when a dated schedule/diary item is detected.

    Criteria (both must hold):
      1. At least one domestic-routine blacklist flag is set.
      2. A specific calendar date (YYYY年M月D日) appears in the event title
         OR in any JP source article title.
    """
    if not blacklist_flags:
        return False
    all_titles = [jp_title] + jp_source_titles
    return any(_DIARY_DATE_PATTERN.search(t) for t in all_titles if t)


def _extract_jp_keywords(title: str) -> set[str]:
    """Extract meaningful tokens from a JP title."""
    tokens: set[str] = set()
    for m in re.finditer(r'[一-龯々]{2,}', title):
        compound = m.group()
        if not _GENERIC_JP_PATTERNS.match(compound):
            tokens.add(compound)
        for map_key in _JP_EN_MAP:
            if map_key in compound and len(map_key) < len(compound):
                tokens.add(map_key)
    for m in re.finditer(r'[ァ-ヶー]{2,}', title):
        tokens.add(m.group())
    for m in re.finditer(r'[A-Za-z]{2,}', title):
        tokens.add(m.group().lower())
    for m in re.finditer(r'(?:19|20)\d{2}', title):
        tokens.add(m.group())
    return tokens


def _extract_en_keywords(text: str) -> set[str]:
    """Extract meaningful tokens from one or more EN titles."""
    tokens: set[str] = set()
    for m in re.finditer(r'[a-z]{3,}', text.lower()):
        w = m.group()
        if w not in _GENERIC_EN:
            tokens.add(w)
    for m in re.finditer(r'(?:19|20)\d{2}', text):
        tokens.add(m.group())
    return tokens


def _translation_overlap(jp_keywords: set[str], en_keywords: set[str]) -> float:
    """Score based on JP→EN translation matches."""
    if not jp_keywords:
        return 0.0
    matched = 0
    checked = 0
    for jp_tok in jp_keywords:
        en_equivalents = _JP_EN_MAP.get(jp_tok)
        if en_equivalents is None:
            continue
        checked += 1
        if en_keywords & en_equivalents:
            matched += 1
    if checked == 0:
        return 0.0
    return matched / checked


def _direct_keyword_overlap(jp_keywords: set[str], en_keywords: set[str]) -> float:
    """Jaccard-like overlap between JP Latin/ASCII/year tokens and EN keywords."""
    jp_matchable = {t for t in jp_keywords if re.match(r'^[a-z0-9]+$', t)}
    if not jp_matchable:
        return 0.0
    intersection = jp_matchable & en_keywords
    union = jp_matchable | en_keywords
    return len(intersection) / max(1, len(union))


def _year_number_overlap(jp_title: str, en_text: str) -> float:
    """Fraction of 4-digit years in JP title that also appear in EN text."""
    jp_years = set(re.findall(r'(?:19|20)\d{2}', jp_title))
    if not jp_years:
        return 0.5  # neutral: no years to compare
    en_years = set(re.findall(r'(?:19|20)\d{2}', en_text))
    overlap = len(jp_years & en_years)
    return overlap / len(jp_years)


def _bucket_topic_match(primary_bucket: str, en_text_lower: str) -> float:
    """Score topic consistency between the event's primary_bucket and EN source content."""
    bucket_en_signals: dict[str, list[str]] = {
        "politics_economy": ["economy", "politic", "trade", "election", "government", "congress",
                             "finance", "minister", "president", "sanctions",
                             "profit", "revenue", "earnings", "gdp", "market",
                             "semiconductor", "chip", "tech", "tariff", "investment",
                             "monetary", "fiscal", "inflation", "interest", "bank"],
        "breaking_shock":   ["breaking", "emergency", "urgent", "disaster", "attack", "explosion"],
        "japan_abroad":     ["japan", "tokyo", "abe", "kishida", "takaichi", "japanese",
                             "prime minister", "boj", "yen"],
        "coverage_gap":     [],  # generic
        "sports":           ["sport", "game", "match", "tournament", "championship", "player",
                             "goal", "score", "team", "olympic", "world cup", "cup"],
        "general":          [],
    }

    bucket_key = primary_bucket.lower().replace("-", "_")
    signals = bucket_en_signals.get(bucket_key, [])

    if not signals:
        return 0.4  # neutral bucket

    hit = any(sig in en_text_lower for sig in signals)
    return 1.0 if hit else 0.2


def _source_language_compatibility(se: "ScoredEvent") -> float:
    """Returns 1.0 if JP + overseas sources are both present, else lower."""
    has_jp = bool(se.event.sources_jp) or bool(
        (se.event.sources_by_locale or {}).get("japan")
    )
    has_overseas = bool(se.event.sources_en) or any(
        loc != "japan" for loc in (se.event.sources_by_locale or {})
    )
    if has_jp and has_overseas:
        return 1.0
    if has_overseas and not has_jp:
        return 0.6  # EN-only blind_spot — less JP-anchored
    return 0.2  # JP-only


def _build_overlap_signals(
    trans_score: float,
    direct_score: float,
    year_score: float,
    bucket_score: float,
    jp_kw: set[str],
    en_kw: set[str],
    jp_title: str,
    en_combined: str,
) -> list[str]:
    """Build human-readable list of overlap signals for explanation."""
    signals: list[str] = []
    if trans_score > 0:
        matched_pairs = [
            f"{jp_tok}→{en_eq}"
            for jp_tok in jp_kw
            for en_eq_set in [_JP_EN_MAP.get(jp_tok)]
            if en_eq_set is not None
            for en_eq in sorted(en_eq_set & en_kw)
        ]
        if matched_pairs:
            signals.append(f"translation:{','.join(matched_pairs[:4])}")
        else:
            signals.append(f"translation_score:{trans_score:.2f}")
    if direct_score > 0:
        jp_matchable = {t for t in jp_kw if re.match(r'^[a-z0-9]+$', t)}
        direct_hits = sorted(jp_matchable & en_kw)[:4]
        if direct_hits:
            signals.append(f"direct_keyword:{','.join(direct_hits)}")
    jp_years = set(re.findall(r'(?:19|20)\d{2}', jp_title))
    en_years = set(re.findall(r'(?:19|20)\d{2}', en_combined))
    if jp_years & en_years:
        signals.append(f"year_match:{','.join(sorted(jp_years & en_years))}")
    elif not jp_years:
        signals.append("year_neutral")
    if bucket_score == 1.0:
        signals.append("bucket_topic_match")
    return signals


# ── Public API ─────────────────────────────────────────────────────────────────

def compute_semantic_coherence(se: "ScoredEvent") -> CoherenceResult:
    """Compute a deterministic semantic coherence score for a candidate.

    Pass 2C changes vs Pass 2B:
      - Blacklist check now covers JP source article titles, not only event title.
      - Added DIARY_COHERENCE_THRESHOLD for dated schedule items.
      - BLACKLIST_COHERENCE_THRESHOLD raised from 0.45 → 0.50.
      - CoherenceResult now includes jp_entities, overseas_entities, overlap_signals,
        is_diary_style for human-readable explanation.
    """
    jp_title: str = se.event.title or ""

    # Collect JP source titles for extended blacklist detection.
    jp_source_titles = _collect_jp_source_titles(se)

    # ── Input quality counters (Pass 2D-1) ───────────────────────────────────
    # Count JP source title presence
    _jp_sources_all: list = list(se.event.sources_jp)
    if se.event.sources_by_locale:
        for _ref in se.event.sources_by_locale.get("japan", []):
            if all(_ref.url != _s.url for _s in _jp_sources_all):
                _jp_sources_all.append(_ref)
    jp_titles_present_count = sum(1 for s in _jp_sources_all if s.title)

    # Count overseas source title presence (deduplicated by URL)
    _overseas_sources_all: list = []
    _seen_os_urls: set[str] = set()
    for src in se.event.sources_en:
        if src.url not in _seen_os_urls:
            _overseas_sources_all.append(src)
            _seen_os_urls.add(src.url)
    if se.event.sources_by_locale:
        for locale, refs in se.event.sources_by_locale.items():
            if locale != "japan":
                for ref in refs:
                    if ref.url not in _seen_os_urls:
                        _overseas_sources_all.append(ref)
                        _seen_os_urls.add(ref.url)
    overseas_titles_present_count = sum(1 for s in _overseas_sources_all if s.title)
    missing_title_sources_count = (
        sum(1 for s in _jp_sources_all if not s.title)
        + sum(1 for s in _overseas_sources_all if not s.title)
    )

    # Collect overseas source titles (deduplicated).
    overseas_title_parts: list[str] = []
    seen_urls: set[str] = set()
    for src in se.event.sources_en:
        if src.url not in seen_urls and src.title:
            overseas_title_parts.append(src.title)
            seen_urls.add(src.url)
    if se.event.sources_by_locale:
        for locale, refs in se.event.sources_by_locale.items():
            if locale != "japan":
                for ref in refs:
                    if ref.url not in seen_urls and ref.title:
                        overseas_title_parts.append(ref.title)
                        seen_urls.add(ref.url)

    # Fallback: if all overseas source titles are null (e.g. stale pool snapshots stored
    # before the title-propagation fix), use global_view which contains the same content
    # in "[source_name] title　summary" format.  This is strictly better than a neutral
    # 0.5 pass because it lets the actual topic overlap be evaluated.
    _used_global_view_fallback = False
    if not overseas_title_parts and se.event.global_view:
        overseas_title_parts = [se.event.global_view]
        _used_global_view_fallback = True
        logger.debug(
            f"[CoherenceGate] Using global_view fallback for overseas text "
            f"(event={se.event.id[:20]}, overseas_sources="
            f"{len(se.event.sources_en) + sum(len(refs) for loc, refs in (se.event.sources_by_locale or {}).items() if loc != 'japan')})"
        )

    # Also include event-level text fields as JP context.
    jp_context = " ".join(filter(None, [
        jp_title,
        " ".join(jp_source_titles),
        se.event.japan_view or "",
        se.event.gap_reasoning or "",
    ]))

    # ── 1. Domestic routine detection (extended: event title + source titles) ──
    blacklist_flags = _detect_domestic_routine_extended(jp_title, jp_source_titles)

    # ── 2. Diary-style detection ──────────────────────────────────────────────
    diary_style = _detect_diary_style(jp_title, jp_source_titles, blacklist_flags)

    # If no overseas titles AND no global_view fallback, we can't check coherence.
    if not overseas_title_parts:
        jp_kw_preview = _extract_jp_keywords(jp_context)
        return CoherenceResult(
            score=0.5,
            blacklist_flags=blacklist_flags,
            block_reason=None,
            score_breakdown={"no_overseas_titles": 1.0},
            jp_entities=sorted(jp_kw_preview)[:10],
            overseas_entities=[],
            overlap_signals=["no_overseas_titles"],
            is_diary_style=diary_style,
            jp_titles_present_count=jp_titles_present_count,
            overseas_titles_present_count=overseas_titles_present_count,
            missing_title_sources_count=missing_title_sources_count,
        )

    en_combined = " ".join(overseas_title_parts)
    en_combined_lower = en_combined.lower()

    # ── Early exit: insufficient EN keyword data ───────────────────────────
    _en_kw_preview = _extract_en_keywords(en_combined_lower)
    if len(_en_kw_preview) < 2:
        jp_kw_preview = _extract_jp_keywords(jp_context)
        return CoherenceResult(
            score=0.5,
            blacklist_flags=blacklist_flags,
            block_reason=None,
            score_breakdown={"insufficient_en_keywords": 1.0, "en_kw_count": len(_en_kw_preview)},
            jp_entities=sorted(jp_kw_preview)[:10],
            overseas_entities=sorted(_en_kw_preview)[:10],
            overlap_signals=["insufficient_en_keywords"],
            is_diary_style=diary_style,
            jp_titles_present_count=jp_titles_present_count,
            overseas_titles_present_count=overseas_titles_present_count,
            missing_title_sources_count=missing_title_sources_count,
        )

    # ── 3. Keyword extraction ─────────────────────────────────────────────────
    jp_kw = _extract_jp_keywords(jp_context)
    en_kw = _extract_en_keywords(en_combined_lower)

    # ── 4. Component scores ───────────────────────────────────────────────────
    trans_score = _translation_overlap(jp_kw, en_kw)
    direct_score = _direct_keyword_overlap(jp_kw, en_kw)
    year_score = _year_number_overlap(jp_title, en_combined)
    bucket_score = _bucket_topic_match(se.primary_bucket, en_combined_lower)
    lang_score = _source_language_compatibility(se)

    # ── 5. Weighted combination ───────────────────────────────────────────────
    raw = (
        0.35 * trans_score
        + 0.20 * direct_score
        + 0.15 * year_score
        + 0.20 * bucket_score
        + 0.10 * lang_score
    )

    # ── 6. Blacklist penalty — halve the score for domestic-routine articles ──
    if blacklist_flags:
        raw *= 0.5

    final_score = max(0.0, min(1.0, raw))

    breakdown = {
        "translation_overlap": round(trans_score, 3),
        "direct_keyword_overlap": round(direct_score, 3),
        "year_number_overlap": round(year_score, 3),
        "bucket_topic_match": round(bucket_score, 3),
        "source_lang_compatibility": round(lang_score, 3),
        "blacklist_penalty_applied": 1.0 if blacklist_flags else 0.0,
        "diary_style_detected": 1.0 if diary_style else 0.0,
        "raw_pre_clamp": round(raw, 3),
        "used_global_view_fallback": 1.0 if _used_global_view_fallback else 0.0,
    }

    # ── 7. Explanation signals ────────────────────────────────────────────────
    overlap_signals = _build_overlap_signals(
        trans_score, direct_score, year_score, bucket_score,
        jp_kw, en_kw, jp_title, en_combined,
    )
    if _used_global_view_fallback:
        overlap_signals.append("global_view_fallback_used")
    if blacklist_flags:
        overlap_signals.append(f"blacklist:{','.join(blacklist_flags)}")
    if diary_style:
        overlap_signals.append("diary_style_detected")

    # ── 8. Gate decision ──────────────────────────────────────────────────────
    if diary_style:
        threshold = DIARY_COHERENCE_THRESHOLD
    elif blacklist_flags:
        threshold = BLACKLIST_COHERENCE_THRESHOLD
    else:
        threshold = COHERENCE_GATE_THRESHOLD

    block_reason: str | None = None
    if final_score < threshold:
        flag_str = ",".join(blacklist_flags) if blacklist_flags else "none"
        block_reason = (
            f"coherence_gate_failed:score={final_score:.3f}<threshold={threshold}"
            f":blacklist=[{flag_str}]"
            + (":diary_style=true" if diary_style else "")
        )

    return CoherenceResult(
        score=final_score,
        blacklist_flags=blacklist_flags,
        block_reason=block_reason,
        score_breakdown=breakdown,
        jp_entities=sorted(jp_kw)[:15],
        overseas_entities=sorted(en_kw)[:15],
        overlap_signals=overlap_signals,
        is_diary_style=diary_style,
        jp_titles_present_count=jp_titles_present_count,
        overseas_titles_present_count=overseas_titles_present_count,
        missing_title_sources_count=missing_title_sources_count,
    )


def apply_coherence_gate(
    se: "ScoredEvent",
    publishability_class: str,
) -> tuple[bool, str | None]:
    """Check whether a candidate passes the coherence gate for linked_jp_global / blind_spot_global.

    Computes the coherence score, stores results on se, and returns
    (gate_passed, block_reason).  The block_reason is None when passing.

    Side effects:
        - Sets se.semantic_coherence_score
        - Sets se.coherence_gate_passed
        - Sets se.coherence_block_reason
        - Sets se.candidate_blacklist_flags

    Args:
        se:                    ScoredEvent to evaluate.
        publishability_class:  judge's publishability_class (for logging context).

    Returns:
        (True, None)   — candidate passes the coherence gate.
        (False, str)   — candidate blocked; str is the block reason.
    """
    result = compute_semantic_coherence(se)

    se.semantic_coherence_score = round(result.score, 4)
    se.candidate_blacklist_flags = result.blacklist_flags
    se.coherence_gate_passed = result.block_reason is None
    se.coherence_block_reason = result.block_reason
    se.coherence_overlap_signals = result.overlap_signals
    se.coherence_input_quality = {
        "jp_titles_present_count": result.jp_titles_present_count,
        "overseas_titles_present_count": result.overseas_titles_present_count,
        "missing_title_sources_count": result.missing_title_sources_count,
    }

    if result.block_reason is not None:
        logger.warning(
            f"[CoherenceGate] BLOCKED {se.event.id[:20]} "
            f"(class={publishability_class}, title={se.event.title[:50]!r}): "
            f"{result.block_reason} | "
            f"jp_entities={result.jp_entities[:5]} | "
            f"overseas_entities={result.overseas_entities[:5]} | "
            f"overlap_signals={result.overlap_signals} | "
            f"breakdown={result.score_breakdown}"
        )
    else:
        logger.info(
            f"[CoherenceGate] PASSED {se.event.id[:20]} "
            f"(class={publishability_class}, score={result.score:.3f}, "
            f"blacklist={result.blacklist_flags}, diary={result.is_diary_style}, "
            f"overlap={result.overlap_signals})"
        )

    return se.coherence_gate_passed, result.block_reason
