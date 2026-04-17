"""tests/test_title_truth_path.py — Pass 2D-2A: Source title truth-path regression.

Verifies that article titles survive the full path:
  normalized article dict → cluster_to_event() → SourceRef.title
  pool-restored snapshot (stale null titles) → _patch_null_source_titles_from_views()
  coherence_gate → uses global_view fallback when source titles are null
  end-to-end: normalized fixture → event → evidence section
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.event_builder import cluster_to_event
from src.shared.models import NewsEvent, ScoredEvent, SourceRef


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_article(
    title: str = "Test headline",
    source_name: str = "TestSource",
    url: str = "https://example.com/1",
    country: str = "JP",
    language: str = "ja",
    region: str = "japan",
    category: str = "general",
    published_at: str = "2026-04-15T10:00:00+00:00",
) -> dict:
    return {
        "id": f"art-{url[-6:]}",
        "title": title,
        "summary": "",
        "url": url,
        "source_name": source_name,
        "country": country,
        "language": language,
        "region": region,
        "category": category,
        "published_at": published_at,
        "fetched_at": "2026-04-15T10:00:00+00:00",
        "tags": [],
        "raw_ref": "",
        "batch_id": "20260415_100000",
    }


def _make_scored_event(
    sources_jp: list[SourceRef] | None = None,
    sources_en: list[SourceRef] | None = None,
    japan_view: str | None = None,
    global_view: str | None = None,
) -> ScoredEvent:
    ev = NewsEvent(
        id="cls-test000001",
        title="テストイベント",
        summary="summary",
        category="general",
        source="TestSource",
        published_at="2026-04-15T10:00:00+00:00",
        sources_jp=sources_jp or [],
        sources_en=sources_en or [],
        japan_view=japan_view,
        global_view=global_view,
    )
    return ScoredEvent(event=ev, score=10.0, primary_bucket="politics_economy")


# ── 1. normalized → event: title flows through cluster_to_event ───────────

class TestNormalizedToEventTitleFlow:
    def test_jp_article_title_in_sources_jp(self):
        """JP article title from normalized dict appears in sources_jp SourceRef."""
        articles = [
            _make_article(
                title="日銀が金利を引き上げ",
                source_name="Nikkei",
                url="https://nikkei.com/a1",
                country="JP",
                region="japan",
            )
        ]
        ev = cluster_to_event(articles)
        assert len(ev.sources_jp) == 1
        assert ev.sources_jp[0].title == "日銀が金利を引き上げ"

    def test_en_article_title_in_sources_en(self):
        """EN article title from normalized dict appears in sources_en SourceRef."""
        articles = [
            _make_article(
                title="BOJ raises interest rates",
                source_name="Reuters",
                url="https://reuters.com/a2",
                country="Global",
                language="en",
                region="global",
            )
        ]
        ev = cluster_to_event(articles)
        assert len(ev.sources_en) == 1
        assert ev.sources_en[0].title == "BOJ raises interest rates"

    def test_both_languages_titles_preserved(self):
        """Cross-lang cluster: both JP and EN titles are set correctly."""
        articles = [
            _make_article(
                title="日銀が金利を引き上げ",
                source_name="Nikkei",
                url="https://nikkei.com/a1",
                country="JP",
                language="ja",
                region="japan",
            ),
            _make_article(
                title="BOJ raises rates amid inflation concerns",
                source_name="Reuters",
                url="https://reuters.com/a2",
                country="Global",
                language="en",
                region="global",
            ),
        ]
        ev = cluster_to_event(articles)
        assert any(s.title == "日銀が金利を引き上げ" for s in ev.sources_jp)
        assert any(s.title == "BOJ raises rates amid inflation concerns" for s in ev.sources_en)

    def test_sources_by_locale_titles_preserved(self):
        """sources_by_locale also carries titles from normalized articles."""
        articles = [
            _make_article(
                title="半導体規制の強化",
                source_name="Asahi",
                url="https://asahi.com/a3",
                country="JP",
                language="ja",
                region="japan",
            ),
        ]
        ev = cluster_to_event(articles)
        japan_refs = ev.sources_by_locale.get("japan", [])
        assert len(japan_refs) == 1
        assert japan_refs[0].title == "半導体規制の強化"

    def test_empty_title_becomes_none(self):
        """Empty string title in normalized dict → title=None in SourceRef."""
        articles = [
            _make_article(
                title="",
                source_name="TestSource",
                url="https://example.com/a4",
                country="JP",
            )
        ]
        ev = cluster_to_event(articles)
        # Empty string → `a.get("title") or None` → None
        if ev.sources_jp:
            assert ev.sources_jp[0].title is None

    def test_title_audit_counts_match(self):
        """Title presence count sanity check: 2 articles → 2 titled sources."""
        articles = [
            _make_article(
                title="日銀ニュース",
                source_name="Nikkei",
                url="https://nikkei.com/b1",
                country="JP",
            ),
            _make_article(
                title="BOJ news",
                source_name="Reuters",
                url="https://reuters.com/b2",
                country="Global",
                language="en",
                region="global",
            ),
        ]
        ev = cluster_to_event(articles)
        jp_with_title = sum(1 for s in ev.sources_jp if s.title)
        en_with_title = sum(1 for s in ev.sources_en if s.title)
        assert jp_with_title == 1
        assert en_with_title == 1


# ── 2. pool restore: _patch_null_source_titles_from_views ────────────────

class TestPatchNullSourceTitlesFromViews:
    """Verify that stale pool snapshots (title=None) get titles from view text."""

    def _get_patch_fn(self):
        from src.main import _patch_null_source_titles_from_views
        return _patch_null_source_titles_from_views

    def test_jp_title_patched_from_japan_view(self):
        """JP SourceRef with null title gets title from japan_view line (summary stripped)."""
        se = _make_scored_event(
            sources_jp=[SourceRef(name="Nikkei", url="https://nikkei.com/c1")],
            # japan_view format: "[source] title\u3000summary" — ideographic space separates
            japan_view="[Nikkei] 日銀が利上げを決定\u3000インフレ対応",
        )
        fn = self._get_patch_fn()
        patched = fn(se)
        assert patched >= 1
        # Summary after ideographic space is stripped; only the title part is captured
        assert se.event.sources_jp[0].title == "日銀が利上げを決定"

    def test_en_title_patched_from_global_view(self):
        """EN SourceRef with null title gets title from global_view line."""
        se = _make_scored_event(
            sources_en=[SourceRef(name="Reuters", url="https://reuters.com/c2", language="en", region="global")],
            global_view="[Reuters] BOJ raises rates for the third time this year",
        )
        fn = self._get_patch_fn()
        patched = fn(se)
        assert patched >= 1
        assert se.event.sources_en[0].title == "BOJ raises rates for the third time this year"

    def test_title_with_summary_stripped(self):
        """Summary appended after ideographic space is stripped from patched title."""
        se = _make_scored_event(
            sources_jp=[SourceRef(name="Asahi", url="https://asahi.com/c3")],
            japan_view="[Asahi] 関税引き上げの影響　輸出企業に打撃",
        )
        fn = self._get_patch_fn()
        fn(se)
        # Should get only the part before the ideographic space (全角スペース)
        title = se.event.sources_jp[0].title
        assert title is not None
        assert "　" not in title  # no ideographic space in title portion
        assert title == "関税引き上げの影響"

    def test_existing_title_not_overwritten(self):
        """SourceRef with non-null title is not overwritten by view parsing."""
        se = _make_scored_event(
            sources_jp=[SourceRef(name="Nikkei", url="https://nikkei.com/c4", title="既存タイトル")],
            japan_view="[Nikkei] 別のタイトル",
        )
        fn = self._get_patch_fn()
        patched = fn(se)
        assert patched == 0
        assert se.event.sources_jp[0].title == "既存タイトル"

    def test_no_view_text_returns_zero(self):
        """With no japan_view / global_view, patch returns 0."""
        se = _make_scored_event(
            sources_jp=[SourceRef(name="Nikkei", url="https://nikkei.com/c5")],
        )
        fn = self._get_patch_fn()
        patched = fn(se)
        assert patched == 0
        assert se.event.sources_jp[0].title is None

    def test_multiple_sources_same_outlet_first_only(self):
        """When two SourceRefs share the same outlet name, both null, first wins."""
        se = _make_scored_event(
            sources_jp=[
                SourceRef(name="Nikkei", url="https://nikkei.com/d1"),
                SourceRef(name="Nikkei", url="https://nikkei.com/d2"),
            ],
            japan_view="[Nikkei] 第一記事のタイトル",
        )
        fn = self._get_patch_fn()
        fn(se)
        # First Nikkei entry should be patched; second also gets the same title (same name key)
        assert se.event.sources_jp[0].title == "第一記事のタイトル"

    def test_sources_by_locale_patched(self):
        """sources_by_locale entries with null title are also patched."""
        from src.shared.models import NewsEvent
        ev = NewsEvent(
            id="cls-test000002",
            title="テスト",
            summary="",
            category="general",
            source="TestSource",
            published_at="2026-04-15T10:00:00+00:00",
            sources_by_locale={
                "global": [SourceRef(name="Reuters", url="https://reuters.com/e1", language="en", region="global")],
            },
            global_view="[Reuters] Global headline for Reuters",
        )
        se = ScoredEvent(event=ev, score=8.0, primary_bucket="general")
        fn = self._get_patch_fn()
        patched = fn(se)
        assert patched >= 1
        assert ev.sources_by_locale["global"][0].title == "Global headline for Reuters"


# ── 3. coherence gate: global_view fallback ────────────────────────────────

class TestCoherenceGateGlobalViewFallback:
    """Verify CoherenceGate uses global_view when all overseas source titles are null."""

    def test_fallback_to_global_view_on_null_titles(self):
        """When sources_en have null titles but global_view has matching content, score > 0.5 neutral."""
        from src.triage.coherence_gate import compute_semantic_coherence

        # Event: JP title mentions 半導体 (semiconductor), global_view mentions "semiconductor"
        se = _make_scored_event(
            sources_jp=[SourceRef(name="Nikkei", url="https://nikkei.com/f1", title="半導体規制強化でTSMCに影響")],
            sources_en=[SourceRef(name="Reuters", url="https://reuters.com/f2", title=None, language="en", region="global")],
            global_view="[Reuters] US tightens semiconductor export controls targeting TSMC chip supply chain",
        )
        result = compute_semantic_coherence(se)
        # Should NOT return no_overseas_titles because global_view is present
        assert "no_overseas_titles" not in result.overlap_signals, (
            "Should not return no_overseas_titles when global_view is present"
        )
        assert "global_view_fallback_used" in result.overlap_signals
        # Score should be based on real content, not neutral 0.5
        assert result.score_breakdown.get("used_global_view_fallback") == 1.0

    def test_no_fallback_needed_when_titles_present(self):
        """When overseas titles are present, global_view fallback is not used."""
        from src.triage.coherence_gate import compute_semantic_coherence

        se = _make_scored_event(
            sources_en=[SourceRef(
                name="Reuters", url="https://reuters.com/g1",
                title="BOJ raises interest rates", language="en", region="global",
            )],
            global_view="[Reuters] BOJ raises interest rates",
        )
        result = compute_semantic_coherence(se)
        assert result.score_breakdown.get("used_global_view_fallback", 0.0) == 0.0
        assert "global_view_fallback_used" not in result.overlap_signals

    def test_neutral_pass_only_when_both_absent(self):
        """no_overseas_titles fallback fires only when overseas sources AND global_view are absent."""
        from src.triage.coherence_gate import compute_semantic_coherence

        se = _make_scored_event(
            sources_en=[SourceRef(name="Reuters", url="https://reuters.com/h1", title=None)],
            global_view=None,  # no fallback available
        )
        result = compute_semantic_coherence(se)
        assert "no_overseas_titles" in result.overlap_signals
        assert result.score == 0.5

    def test_coarse_coherent_story_scores_above_gate(self):
        """With matching JP/EN content via global_view fallback, score exceeds 0.25 threshold."""
        from src.triage.coherence_gate import compute_semantic_coherence, COHERENCE_GATE_THRESHOLD

        se = _make_scored_event(
            sources_jp=[SourceRef(name="Nikkei", url="https://nikkei.com/i1", title="日銀が利上げを決定")],
            sources_en=[SourceRef(name="Reuters", url="https://reuters.com/i2", title=None, language="en", region="global")],
            global_view="[Reuters] Bank of Japan raises interest rates to 0.5 percent in surprise move",
        )
        result = compute_semantic_coherence(se)
        assert result.score > COHERENCE_GATE_THRESHOLD
        assert result.block_reason is None

    def test_incoherent_story_can_be_blocked_via_fallback(self):
        """With mismatched JP/EN content via global_view fallback, score can fall below threshold."""
        from src.triage.coherence_gate import compute_semantic_coherence, COHERENCE_GATE_THRESHOLD

        # JP: 首相動静 (PM schedule — domestic routine), EN: unrelated sport news
        se = _make_scored_event(
            sources_jp=[SourceRef(name="Asahi", url="https://asahi.com/j1", title="首相動静")],
            sources_en=[SourceRef(name="ESPN", url="https://espn.com/j2", title=None, language="en", region="global")],
            global_view="[ESPN] Lakers beat Celtics in overtime thriller NBA finals game three",
        )
        se.event.title = "首相動静"
        result = compute_semantic_coherence(se)
        # Blacklist + incoherent content → should be a low or blocked score
        assert "首相動静" in result.blacklist_flags or len(result.blacklist_flags) > 0


# ── 4. end-to-end: normalized fixture → event → evidence dict ────────────

class TestEndToEndTitleInEvidence:
    """Verify that titles flow through to the evidence dict produced by evidence_writer."""

    def test_evidence_sources_have_titles(self):
        """When a NewsEvent has SourceRefs with titles, the evidence dict preserves them."""
        from src.generation.evidence_writer import _sources_section

        ev = NewsEvent(
            id="cls-test000003",
            title="テストイベント",
            summary="summary",
            category="general",
            source="Nikkei",
            published_at="2026-04-15T10:00:00+00:00",
            sources_jp=[
                SourceRef(name="Nikkei", url="https://nikkei.com/k1", title="日銀が利上げ決定"),
            ],
            sources_en=[
                SourceRef(name="Reuters", url="https://reuters.com/k2", title="BOJ raises rates",
                          language="en", region="global"),
            ],
        )
        section = _sources_section(ev)
        jp_titles = [s.get("title") for s in section["jp"]]
        en_titles = [s.get("title") for s in section["en"]]
        assert "日銀が利上げ決定" in jp_titles, f"JP title missing from evidence sources: {jp_titles}"
        assert "BOJ raises rates" in en_titles, f"EN title missing from evidence sources: {en_titles}"

    def test_evidence_sources_null_title_when_not_set(self):
        """When SourceRefs have no titles, evidence dict shows title=null (not missing key)."""
        from src.generation.evidence_writer import _sources_section

        ev = NewsEvent(
            id="cls-test000004",
            title="テストイベント",
            summary="summary",
            category="general",
            source="Nikkei",
            published_at="2026-04-15T10:00:00+00:00",
            sources_jp=[
                SourceRef(name="Nikkei", url="https://nikkei.com/l1"),
            ],
            sources_en=[],
        )
        section = _sources_section(ev)
        assert "title" in section["jp"][0], "title key should always be present"
        assert section["jp"][0]["title"] is None

    def test_full_pipeline_normalized_to_event_to_evidence(self):
        """End-to-end: normalized dicts → cluster_to_event → evidence _sources_section."""
        from src.generation.evidence_writer import _sources_section

        articles = [
            _make_article(
                title="半導体制裁でサムスン打撃",
                source_name="Asahi",
                url="https://asahi.com/m1",
                country="JP",
            ),
            _make_article(
                title="US chip sanctions hit Samsung hard",
                source_name="CNA",
                url="https://cna.asia/m2",
                country="SG",
                language="en",
                region="east_asia",
            ),
        ]
        ev = cluster_to_event(articles)
        section = _sources_section(ev)

        # At least one source in JP or EN should have a non-null title
        all_titles = [
            s.get("title") for s in section.get("jp", []) + section.get("en", [])
        ]
        non_null = [t for t in all_titles if t]
        assert len(non_null) >= 1, (
            f"Expected at least 1 non-null title in evidence sources, got: {all_titles}"
        )
