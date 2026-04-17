"""Regression tests for Pass B: Batch Semantic Merge guard.

Covers:
  - _classify_predicate_family: correct family detection
  - _predicate_families_incompatible: correct incompatibility logic
  - Predicate guard integration: same-country / different-sector pairs blocked before LLM
  - llm_batch_merge: mock-LLM batch call with 3-way verdict
  - cluster_articles integration: incompatible predicate family pairs NOT merged
  - same-event detection via batch LLM (same company / same policy)
  - related_but_distinct: not merged
  - observability: stats keys present and correct

Regression cases:
  1. Canada gas tax vs Lebanon ceasefire → different_event (predicate guard blocks)
  2. Same company / same policy → same_event (LLM returns same_event)
  3. Same country, different sector → different_event (predicate guard blocks)
  4. Related macro context, different concrete event → related_but_distinct (not merged)
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from src.ingestion.cross_lang_matcher import llm_batch_merge
from src.ingestion.event_builder import (
    _classify_predicate_family,
    _predicate_families_incompatible,
    cluster_articles,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _art(title: str, country: str = "EN", source: str = "BBC") -> dict:
    return {
        "id": title[:8],
        "title": title,
        "url": f"http://example.com/{abs(hash(title)) % 999999}",
        "country": country,
        "source_name": source,
        "category": "general",
        "published_at": "2026-04-16T10:00:00+00:00",
        "summary": "",
        "tags": [],
        "fetched_at": "2026-04-16T11:00:00+00:00",
        "raw_ref": "",
    }


def _mock_llm(batch_json: list[dict]) -> MagicMock:
    """Return a mock LLM whose generate() yields the given batch JSON."""
    client = MagicMock()
    client.generate.return_value = json.dumps(batch_json)
    return client


# ── _classify_predicate_family ────────────────────────────────────────────────


def test_classify_tax_fiscal_from_raw_text():
    arts = [_art("Canada pauses gasoline excise tax until June")]
    assert _classify_predicate_family(arts) == "tax_fiscal"


def test_classify_conflict_military_ceasefire():
    arts = [_art("Lebanon ceasefire talks stall as fighting resumes")]
    assert _classify_predicate_family(arts) == "conflict_military"


def test_classify_conflict_military_anchor_token():
    # kw:ceasefire anchor token from "ceasefire" in English title
    arts = [_art("Gaza ceasefire agreement reached after days of negotiations")]
    assert _classify_predicate_family(arts) == "conflict_military"


def test_classify_humanitarian():
    arts = [_art("Canada expands refugee healthcare access in border communities")]
    assert _classify_predicate_family(arts) == "humanitarian"


def test_classify_telecom_space():
    arts = [_art("Telesat wins defense satellite contract from Canadian government")]
    assert _classify_predicate_family(arts) == "telecom_space"


def test_classify_finance_earnings():
    arts = [_art("Apple quarterly earnings beat expectations on services revenue")]
    assert _classify_predicate_family(arts) == "finance_earnings"


def test_classify_returns_none_for_generic():
    arts = [_art("Latest news from around the world")]
    assert _classify_predicate_family(arts) is None


def test_classify_empty_cluster_returns_none():
    assert _classify_predicate_family([]) is None


# ── _predicate_families_incompatible ─────────────────────────────────────────


def test_incompatible_tax_vs_conflict():
    assert _predicate_families_incompatible("tax_fiscal", "conflict_military") is True


def test_incompatible_humanitarian_vs_finance():
    assert _predicate_families_incompatible("humanitarian", "finance_earnings") is True


def test_incompatible_telecom_vs_conflict():
    assert _predicate_families_incompatible("telecom_space", "conflict_military") is True


def test_compatible_same_family():
    assert _predicate_families_incompatible("tax_fiscal", "tax_fiscal") is False


def test_compatible_none_left():
    assert _predicate_families_incompatible(None, "conflict_military") is False


def test_compatible_none_right():
    assert _predicate_families_incompatible("tax_fiscal", None) is False


def test_compatible_both_none():
    assert _predicate_families_incompatible(None, None) is False


def test_compatible_tax_and_finance():
    # Tax cuts → corporate earnings impact: explicitly allowed pair
    assert _predicate_families_incompatible("tax_fiscal", "finance_earnings") is False


def test_compatible_energy_and_finance():
    assert _predicate_families_incompatible("energy_supply", "finance_earnings") is False


# ── Regression: Canada gas tax vs Lebanon ceasefire ──────────────────────────


def test_canada_gas_tax_vs_lebanon_ceasefire_different_families():
    """Regression: Canada gasoline tax pause and Lebanon ceasefire have incompatible
    predicate families; the pair must be rejected before any LLM call."""
    gas_tax_cluster = [_art("Canada pauses gasoline excise tax until June")]
    ceasefire_cluster = [_art("Lebanon ceasefire talks stall as fighting resumes")]

    fam_a = _classify_predicate_family(gas_tax_cluster)
    fam_b = _classify_predicate_family(ceasefire_cluster)

    assert fam_a == "tax_fiscal", f"Expected tax_fiscal, got {fam_a}"
    assert fam_b == "conflict_military", f"Expected conflict_military, got {fam_b}"
    assert _predicate_families_incompatible(fam_a, fam_b) is True


def test_canada_gas_tax_vs_lebanon_ceasefire_not_merged_in_cluster_articles():
    """Regression: even with a mock LLM that says YES for everything, the predicate
    guard must prevent Canada gas tax and Lebanon ceasefire from merging."""
    # JP cluster about Canada gas tax
    # EN cluster about Lebanon ceasefire
    # With a lying LLM (always YES), the predicate guard still blocks the pair.
    articles = [
        _art("カナダがガソリン税を一時停止", country="JP", source="NHK"),
        _art("Lebanon ceasefire talks stall as fighting resumes", country="EN", source="BBC"),
    ]
    # Force LLM to claim same_event for everything — guard must still reject
    mock_llm = MagicMock()
    mock_llm.generate.return_value = json.dumps([
        {"pair_id": 0, "verdict": "same_event", "reason": "test override"}
    ])
    clusters = cluster_articles(articles, llm_client=mock_llm)
    # The two articles should remain in separate clusters
    assert len(clusters) == 2, (
        f"Expected 2 separate clusters, got {len(clusters)}: "
        f"{[c[0]['title'] for c in clusters]}"
    )


# ── Regression: same country different sector ────────────────────────────────


def test_same_country_different_sector_blocked():
    """Same country (Canada) but different sectors → incompatible predicate families."""
    energy_cluster = [_art("Canada increases natural gas export capacity to Asia")]
    healthcare_cluster = [_art("Canada expands refugee healthcare access in border communities")]

    fam_e = _classify_predicate_family(energy_cluster)
    fam_h = _classify_predicate_family(healthcare_cluster)

    assert fam_e == "energy_supply", f"Expected energy_supply, got {fam_e}"
    assert fam_h == "humanitarian", f"Expected humanitarian, got {fam_h}"
    # energy_supply vs humanitarian are incompatible
    assert _predicate_families_incompatible(fam_e, fam_h) is True


# ── llm_batch_merge: mock LLM tests ──────────────────────────────────────────


def test_llm_batch_merge_same_event_verdict():
    pairs = [
        {"pair_id": 0, "title_a": "Apple Q2 profit beats expectations", "title_b": "Apple reports strong quarterly earnings"},
        {"pair_id": 1, "title_a": "Canada gas tax pause", "title_b": "Lebanon ceasefire"},
    ]
    mock_llm = _mock_llm([
        {"pair_id": 0, "verdict": "same_event", "reason": "same earnings event"},
        {"pair_id": 1, "verdict": "different_event", "reason": "unrelated events"},
    ])
    results = llm_batch_merge(pairs, mock_llm)
    assert len(results) == 2
    by_id = {r["pair_id"]: r for r in results}
    assert by_id[0]["verdict"] == "same_event"
    assert by_id[1]["verdict"] == "different_event"


def test_llm_batch_merge_related_but_distinct():
    pairs = [
        {"pair_id": 0, "title_a": "US tariffs on Chinese goods rise", "title_b": "China retaliates with counter-tariffs on US products"},
    ]
    mock_llm = _mock_llm([
        {"pair_id": 0, "verdict": "related_but_distinct", "reason": "same trade war context but distinct actions"},
    ])
    results = llm_batch_merge(pairs, mock_llm)
    assert results[0]["verdict"] == "related_but_distinct"


def test_llm_batch_merge_parse_error_defaults_to_different_event():
    pairs = [{"pair_id": 0, "title_a": "A", "title_b": "B"}]
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "NOT VALID JSON !!!"
    results = llm_batch_merge(pairs, mock_llm)
    assert len(results) == 1
    assert results[0]["verdict"] == "different_event"
    assert "pair_id" in results[0]


def test_llm_batch_merge_batches_correctly():
    """Verify that large pair lists are split into batches of the requested size."""
    n_pairs = 32
    batch_size = 10
    pairs = [
        {"pair_id": i, "title_a": f"Title A {i}", "title_b": f"Title B {i}"}
        for i in range(n_pairs)
    ]

    call_count = 0

    def _generate(prompt: str) -> str:
        nonlocal call_count
        call_count += 1
        # Parse the pair_ids from prompt lines and echo back different_event for each
        import re
        ids = [int(m.group(1)) for m in re.finditer(r"^\[(\d+)\]", prompt, re.MULTILINE)]
        return json.dumps([
            {"pair_id": pid, "verdict": "different_event", "reason": "test"} for pid in ids
        ])

    mock_llm = MagicMock()
    mock_llm.generate.side_effect = _generate

    results = llm_batch_merge(pairs, mock_llm, batch_size=batch_size)

    expected_batches = (n_pairs + batch_size - 1) // batch_size
    assert mock_llm.generate.call_count == expected_batches
    assert len(results) == n_pairs


def test_llm_batch_merge_empty_returns_empty():
    mock_llm = MagicMock()
    results = llm_batch_merge([], mock_llm)
    assert results == []
    mock_llm.generate.assert_not_called()


def test_llm_batch_merge_invalid_verdict_sanitized():
    """Unknown verdict values are sanitized to different_event."""
    pairs = [{"pair_id": 0, "title_a": "A", "title_b": "B"}]
    mock_llm = _mock_llm([{"pair_id": 0, "verdict": "MAYBE", "reason": "unsure"}])
    results = llm_batch_merge(pairs, mock_llm)
    assert results[0]["verdict"] == "different_event"


# ── Integration: same-event merges correctly ─────────────────────────────────


def test_same_company_same_event_merges_via_batch_llm():
    """Same company / same earnings event: batch LLM same_event → merged cluster."""
    articles = [
        _art("アップルQ2決算が市場予想を上回る", country="JP", source="NHK"),
        _art("Apple Q2 earnings beat expectations on services revenue", country="EN", source="Reuters"),
    ]
    mock_llm = MagicMock()
    mock_llm.generate.return_value = json.dumps([
        {"pair_id": 0, "verdict": "same_event", "reason": "same earnings report"}
    ])
    clusters = cluster_articles(articles, llm_client=mock_llm)
    assert len(clusters) == 1
    titles = {a["title"] for a in clusters[0]}
    assert "Apple Q2 earnings beat expectations on services revenue" in titles


def test_related_but_distinct_not_merged():
    """related_but_distinct verdict keeps clusters separate."""
    articles = [
        _art("米中貿易摩擦が激化", country="JP", source="NHK"),
        _art("US imposes new chip export restrictions targeting China", country="EN", source="Reuters"),
    ]
    mock_llm = MagicMock()
    mock_llm.generate.return_value = json.dumps([
        {"pair_id": 0, "verdict": "related_but_distinct", "reason": "same trade war context but distinct policy action"}
    ])
    clusters = cluster_articles(articles, llm_client=mock_llm)
    # related_but_distinct must NOT merge
    assert len(clusters) == 2


# ── Observability: stats keys ─────────────────────────────────────────────────


def test_batch_merge_stats_keys_present():
    """After cluster_articles with an LLM client, all Pass B stats keys are in stats."""
    articles = [
        _art("カナダがガソリン税を一時停止", country="JP", source="NHK"),
        _art("Canada pauses gasoline excise tax until June", country="EN", source="CBC"),
        _art("Lebanon ceasefire talks stall", country="EN", source="BBC"),
    ]
    mock_llm = MagicMock()
    # Return empty list (no merge decisions) — just need stats to be populated
    mock_llm.generate.return_value = json.dumps([])

    stats: dict = {}
    cluster_articles(articles, llm_client=mock_llm, stats=stats)

    required_keys = [
        "pairs_considered",
        "pairs_rejected_by_predicate_guard",
        "pairs_sent_to_batch_llm",
        "same_event_count",
        "related_but_distinct_count",
        "different_event_count",
        "sample_rejected_reasons",
    ]
    for key in required_keys:
        assert key in stats, f"Missing stats key: {key}"


def test_predicate_guard_rejection_counted_in_stats():
    """pairs_rejected_by_predicate_guard is > 0 when incompatible pairs exist.

    Construction: both articles share kw:primeminister (a weak/HIGH_FREQ anchor) plus
    non-general category and close publication date — enough to push score above
    _MIN_PAIR_SCORE (3.0) without triggering a BFS cross-lang edge (which requires
    either a strong non-HIGH_FREQ anchor or ≥3 weak anchors).

    JP = conflict_military (kw:ceasefire via 停戦)
    EN = tax_fiscal (kw:taxcut via "tax cut")
    → incompatible predicate families → predicate guard rejects the pair.
    """
    articles = [
        # JP: 首相 → kw:primeminister (HIGH_FREQ), 停戦 → kw:ceasefire → conflict_military
        _art(
            "首相が停戦仲介に乗り出す方針を表明",
            country="JP",
            source="NHK",
        ),
        # EN: prime minister → kw:primeminister (HIGH_FREQ), tax cut → kw:taxcut → tax_fiscal
        _art(
            "Prime Minister announces gasoline tax cut to ease inflation",
            country="EN",
            source="BBC",
        ),
    ]

    # Verify families before integration test (fail fast with clear messages)
    from src.ingestion.event_builder import _classify_predicate_family, _predicate_families_incompatible
    fam_jp = _classify_predicate_family([articles[0]])
    fam_en = _classify_predicate_family([articles[1]])
    assert fam_jp == "conflict_military", f"JP family should be conflict_military, got {fam_jp}"
    assert fam_en == "tax_fiscal", f"EN family should be tax_fiscal, got {fam_en}"
    assert _predicate_families_incompatible(fam_jp, fam_en), "Should be incompatible"

    mock_llm = MagicMock()
    mock_llm.generate.return_value = json.dumps([])
    stats: dict = {}
    cluster_articles(articles, llm_client=mock_llm, stats=stats)

    assert stats.get("pairs_rejected_by_predicate_guard", 0) > 0, (
        "Expected predicate guard to reject at least one pair. "
        f"stats={stats}"
    )


# ── Verdict count observability ───────────────────────────────────────────────


def _articles_that_reach_llm() -> list[dict]:
    """JP/EN pair that shares exactly 2 HIGH_FREQ anchors (kw:president, kw:stockprice)
    but no strong cross-lang anchor.

    BFS requires ≥3 weak-only anchors for a cross-lang edge, so these 2 articles stay
    in separate JP-only / EN-only clusters after BFS.  Their similarity score (5.0) still
    clears the _MIN_PAIR_SCORE (3.0) gate, so the pair is passed to the batch LLM.

    Breakdown:
      JP: 大統領 → kw:president (HIGH_FREQ), 株価 → kw:stockprice (HIGH_FREQ)
      EN: "president" → kw:president (HIGH_FREQ), "stock price" → kw:stockprice (HIGH_FREQ)
      Shared strong anchors: 0  →  BFS rejects (2 < 3 required weak-only)
      Score: 2×3.0 − 2×1.5 + 2.0 (same-day date bonus) = 5.0  ≥  3.0  ✓
      Predicate families: both None → no predicate-guard block
    """
    return [
        _art("大統領が株価について発言", country="JP", source="NHK"),
        _art("President comments on stock price", country="EN", source="Reuters"),
    ]


def test_same_event_verdict_increments_count_and_merges():
    """same_event verdict must increment same_event_count and merge the clusters."""
    articles = _articles_that_reach_llm()
    mock_llm = _mock_llm([{"pair_id": 0, "verdict": "same_event", "reason": "same earnings"}])
    stats: dict = {}
    clusters = cluster_articles(articles, llm_client=mock_llm, stats=stats)
    assert stats.get("same_event_count", 0) == 1, f"same_event_count should be 1, got {stats}"
    assert len(clusters) == 1, "same_event should merge into one cluster"


def test_related_but_distinct_verdict_increments_count_and_does_not_merge():
    """related_but_distinct verdict must increment count and keep clusters separate."""
    articles = _articles_that_reach_llm()
    mock_llm = _mock_llm([
        {"pair_id": 0, "verdict": "related_but_distinct", "reason": "same company diff quarter"}
    ])
    stats: dict = {}
    clusters = cluster_articles(articles, llm_client=mock_llm, stats=stats)
    assert stats.get("related_but_distinct_count", 0) == 1, (
        f"related_but_distinct_count should be 1, got {stats}"
    )
    assert len(clusters) == 2, "related_but_distinct must NOT merge"


def test_different_event_verdict_increments_count_and_does_not_merge():
    """different_event verdict must increment count and keep clusters separate."""
    articles = _articles_that_reach_llm()
    mock_llm = _mock_llm([{"pair_id": 0, "verdict": "different_event", "reason": "unrelated"}])
    stats: dict = {}
    clusters = cluster_articles(articles, llm_client=mock_llm, stats=stats)
    assert stats.get("different_event_count", 0) == 1, (
        f"different_event_count should be 1, got {stats}"
    )
    assert len(clusters) == 2, "different_event must NOT merge"


def test_merge_summary_non_empty_when_batch_llm_runs():
    """When the batch LLM runs, verdict counts must be non-zero in aggregate."""
    articles = _articles_that_reach_llm()
    mock_llm = _mock_llm([{"pair_id": 0, "verdict": "same_event", "reason": "same report"}])
    stats: dict = {}
    cluster_articles(articles, llm_client=mock_llm, stats=stats)
    total_verdicts = (
        stats.get("same_event_count", 0)
        + stats.get("related_but_distinct_count", 0)
        + stats.get("different_event_count", 0)
    )
    assert total_verdicts > 0, (
        f"merge_summary counts must be non-zero when batch LLM runs. stats={stats}"
    )
    assert stats.get("pairs_sent_to_batch_llm", 0) > 0, (
        f"pairs_sent_to_batch_llm should be > 0. stats={stats}"
    )


def test_same_event_examples_populated():
    """same_event_examples must contain title pair when same_event verdict is returned."""
    articles = _articles_that_reach_llm()
    mock_llm = _mock_llm([{"pair_id": 0, "verdict": "same_event", "reason": "identical story"}])
    stats: dict = {}
    cluster_articles(articles, llm_client=mock_llm, stats=stats)
    examples = stats.get("same_event_examples", [])
    assert len(examples) == 1, f"Expected 1 same_event example, got {examples}"
    ex = examples[0]
    assert ex["verdict"] == "same_event"
    assert ex["reason"] == "identical story"
    assert "jp_title" in ex and "en_title" in ex
