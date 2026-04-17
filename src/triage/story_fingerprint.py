"""Story Fingerprint — cross-batch story identity key.

Computes a stable fingerprint for a NewsEvent that remains consistent
across batches when the same story is covered by different sources or
at slightly different times (time-lag arbitrage).

Design goals:
- Same story from different URLs → same fingerprint
- JP and EN coverage of the same event → ideally same fingerprint
- Resistant to minor title wording differences

Formula:
    SHA256(sorted_key_terms + "|" + category)[:16]

Where key_terms = top 5 distinctive, normalized tokens from the title,
sorted alphabetically for order-independence.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

from src.shared.models import NewsEvent

# ── Stopwords (EN + JP function words) ────────────────────────────────────────
_STOP_WORDS: frozenset[str] = frozenset({
    # English common function words
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or", "but",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "with", "by", "from", "this", "that", "these", "those", "its", "it",
    "over", "after", "amid", "as", "up", "down", "out", "off", "not", "new",
    "says", "said", "amid", "after", "before", "about", "into", "than",
    "also", "more", "most", "no", "can", "now", "how", "why", "when", "where",
    # Japanese particles and auxiliary verbs
    "が", "の", "は", "を", "に", "で", "と", "も", "な", "か",
    "へ", "から", "まで", "より", "など", "という", "として",
    "した", "する", "している", "された", "される", "している",
    "ない", "ある", "いる", "なる", "れる", "られる",
})

# Minimum token character length (EN: 3, JP/CJK: 2)
_MIN_LEN_EN: int = 3
_MIN_LEN_JA: int = 2

# Number of key terms to use in fingerprint
_TERM_COUNT: int = 5

# Regex to detect CJK characters
_CJK_RE = re.compile(r"[\u3000-\u9FFF\uF900-\uFAFF\uAC00-\uD7FF\u30A0-\u30FF\u3040-\u309F]")

# Split pattern: whitespace + ASCII punctuation + Japanese punctuation
_SPLIT_RE = re.compile(r"[\s\-_/,;:!?\"'()\[\]{}<>。、「」『』【】（）…・＿／]+")


def _has_cjk(token: str) -> bool:
    return bool(_CJK_RE.search(token))


def _extract_key_terms(title: str) -> list[str]:
    """Extract distinctive terms from a title for fingerprinting.

    Steps:
    1. NFKC normalize + lowercase
    2. Split on whitespace and punctuation
    3. Filter stopwords and short tokens
    4. Sort by length desc (longer = more distinctive), then alpha
    5. Return top _TERM_COUNT unique terms
    """
    normalized = unicodedata.normalize("NFKC", title).lower()
    raw_tokens = _SPLIT_RE.split(normalized)

    terms: list[str] = []
    for token in raw_tokens:
        token = token.strip()
        if not token:
            continue
        is_cjk = _has_cjk(token)
        min_len = _MIN_LEN_JA if is_cjk else _MIN_LEN_EN
        if len(token) >= min_len and token not in _STOP_WORDS:
            terms.append(token)

    # Sort: longer terms first (more distinctive), then alphabetical for stability
    terms.sort(key=lambda t: (-len(t), t))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    return unique[:_TERM_COUNT]


def compute_story_fingerprint(event: NewsEvent) -> str:
    """Compute a stable 16-char story fingerprint for cross-batch deduplication.

    The fingerprint is based on:
    - Top 5 distinctive terms from the title (alphabetically sorted)
    - Event category

    Date is intentionally excluded so the same story covered first by
    Reuters last night and then by NHK this morning can potentially share
    the same fingerprint and trigger duplicate suppression / upgrade logic.

    Returns:
        16-character lowercase hex string (SHA-256 prefix)
    """
    terms = _extract_key_terms(event.title)
    # Sort alphabetically for order-independence across title variants
    key_parts = sorted(terms) + [event.category.lower()]
    key_str = "|".join(key_parts)
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()[:16]
