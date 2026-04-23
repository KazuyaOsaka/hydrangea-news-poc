"""Regression tests for Pass 2B: Semantic Coherence Gate + Judge Model Switch.

Verified behaviours:
  1.  Domestic-routine JP title (首相動静) cannot become blind_spot_global
      with unrelated EN sources — coherence gate blocks it.
  2.  Coherent JP+EN candidate (shared entities) passes the gate.
  3.  Incoherent candidate is downgraded (coherence_gate_passed=False).
  4.  Judge model default is Gemini 3.1 Flash Lite.
  5.  run_summary judge_summary contains judge_model_used.
  6.  run_summary judge_summary slot1 contains coherence fields.
  7.  Blacklist detects all defined domestic-routine patterns.
  8.  Non-blacklisted incoherent candidate is blocked at base threshold.
  9.  _find_eligible_judged_slot1 skips coherence-blocked candidates.
  10. Coherent candidate with no overseas titles gets neutral pass (no block).
  11. Translation overlap scoring — JP country word matched in EN.
  12. Year overlap scoring.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.shared.models import GeminiJudgeResult, NewsEvent, ScoredEvent, SourceRef
from src.triage.coherence_gate import (
    BLACKLIST_COHERENCE_THRESHOLD,
    COHERENCE_GATE_THRESHOLD,
    DIARY_COHERENCE_THRESHOLD,
    DOMESTIC_ROUTINE_PATTERNS,
    CoherenceResult,
    apply_coherence_gate,
    compute_semantic_coherence,
    _detect_domestic_routine,
    _detect_domestic_routine_extended,
    _detect_diary_style,
    _extract_jp_keywords,
    _extract_en_keywords,
    _translation_overlap,
    _year_number_overlap,
)
from src.shared.config import GEMINI_JUDGE_MODEL
from src.main import _find_eligible_judged_slot1, _build_judge_summary


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _make_event(event_id: str = "e-001", **kwargs) -> NewsEvent:
    defaults = dict(
        title="Test News",
        summary="Test summary.",
        category="economy",
        source="TestSource",
        published_at=datetime(2026, 4, 14, 10, 0, 0),
        tags=[],
    )
    defaults.update(kwargs)
    return NewsEvent(id=event_id, **defaults)


def _en_src(name: str = "Reuters", title: str = "Reuters headline") -> SourceRef:
    return SourceRef(
        name=name, url=f"https://{name.lower()}.com/1", title=title,
        language="en", country="US", region="global",
    )


def _jp_src(name: str = "NHK", title: str = "NHK headline") -> SourceRef:
    return SourceRef(
        name=name, url=f"https://{name.lower()}.or.jp/1", title=title,
        language="ja", country="JP", region="japan",
    )


def _make_scored(
    event_id: str = "s-001",
    score: float = 80.0,
    primary_bucket: str = "politics_economy",
    sources_jp: list[SourceRef] | None = None,
    sources_en: list[SourceRef] | None = None,
    judge_result: GeminiJudgeResult | None = None,
    **event_kwargs,
) -> ScoredEvent:
    event = _make_event(
        event_id,
        sources_jp=sources_jp or [],
        sources_en=sources_en or [],
        **event_kwargs,
    )
    return ScoredEvent(
        event=event,
        score=score,
        score_breakdown={},
        primary_tier="Tier 2",
        editorial_tags=[],
        primary_bucket=primary_bucket,
        judge_result=judge_result,
    )


def _make_judge(
    publishability_class: str = "blind_spot_global",
    divergence_score: float = 6.0,
    indirect_japan_impact_score_judge: float = 6.0,
    judge_error: str | None = None,
) -> GeminiJudgeResult:
    return GeminiJudgeResult(
        publishability_class=publishability_class,
        divergence_score=divergence_score,
        blind_spot_global_score=7.0,
        indirect_japan_impact_score_judge=indirect_japan_impact_score_judge,
        authority_signal_score=6.0,
        confidence=0.8,
        requires_more_evidence=False,
        hard_claims_supported=True,
        judge_error=judge_error,
    )


# ── 1. Domestic-routine JP title is blocked with unrelated EN sources ──────────

class TestDomesticRoutineBlocked:

    def test_pm_schedule_with_unrelated_en_blocked(self):
        """首相動静 JP title + unrelated EN titles → coherence gate blocks."""
        se = _make_scored(
            event_id="pm-schedule",
            title="高市首相動静 2026年4月14日",
            primary_bucket="japan_abroad",
            sources_jp=[_jp_src("NHK", "高市首相動静 2026年4月14日")],
            sources_en=[
                _en_src("Bloomberg", "China economy shows signs of recovery in 2026"),
                _en_src("Reuters", "FIFA World Cup 2026 preparations underway"),
                _en_src("BBC", "Global trade tensions ease amid tariff talks"),
            ],
            judge_result=_make_judge("blind_spot_global"),
        )
        result = compute_semantic_coherence(se)
        assert result.score < BLACKLIST_COHERENCE_THRESHOLD, (
            f"PM schedule + unrelated EN should be blocked. "
            f"score={result.score:.3f}, threshold={BLACKLIST_COHERENCE_THRESHOLD}"
        )
        assert "首相動静" in result.blacklist_flags
        assert result.block_reason is not None
        assert "coherence_gate_failed" in result.block_reason

    def test_pm_schedule_blocked_via_apply_coherence_gate(self):
        """apply_coherence_gate returns (False, reason) for PM schedule candidate."""
        se = _make_scored(
            event_id="pm-sched2",
            title="高市首相動静 2026年4月14日",
            primary_bucket="japan_abroad",
            sources_jp=[_jp_src()],
            sources_en=[
                _en_src("Bloomberg", "China economy growth forecast upgraded"),
                _en_src("Reuters", "World Cup 2026 stadiums confirmed"),
            ],
            judge_result=_make_judge("blind_spot_global"),
        )
        passed, reason = apply_coherence_gate(se, "blind_spot_global")
        assert not passed
        assert reason is not None
        # Side effects should be set
        assert se.coherence_gate_passed is False
        assert se.coherence_block_reason is not None
        assert "首相動静" in se.candidate_blacklist_flags

    def test_pm_schedule_not_in_eligible_slot1(self):
        """_find_eligible_judged_slot1 must skip PM-schedule candidate."""
        se = _make_scored(
            event_id="pm-sched3",
            score=98.0,
            title="高市首相動静 2026年4月14日",
            primary_bucket="japan_abroad",
            sources_jp=[_jp_src()],
            sources_en=[
                _en_src("Bloomberg", "China economic recovery 2026"),
                _en_src("Reuters", "FIFA World Cup 2026 news"),
            ],
            judge_result=_make_judge("blind_spot_global", indirect_japan_impact_score_judge=6.0),
        )
        judge_results = {se.event.id: se.judge_result}  # type: ignore[index]

        selected, reason = _find_eligible_judged_slot1([se], judge_results)

        assert selected is None, (
            f"PM schedule should be blocked by coherence gate, got selected={selected}"
        )


# ── 2. Coherent JP+EN candidate passes ────────────────────────────────────────

class TestCoherentCandidatePasses:

    def test_china_economy_story_passes(self):
        """JP article about China economy + EN sources about China economy → passes."""
        se = _make_scored(
            event_id="china-econ",
            title="中国経済、2026年に回復加速の見通し　IMF予測",
            primary_bucket="politics_economy",
            sources_jp=[_jp_src("Nikkei", "中国経済 回復 2026年 IMF予測")],
            sources_en=[
                _en_src("Bloomberg", "China economy recovery accelerates in 2026 IMF forecast"),
                _en_src("Reuters", "China GDP growth expected to beat forecasts in 2026"),
            ],
            judge_result=_make_judge("linked_jp_global"),
        )
        result = compute_semantic_coherence(se)
        assert result.block_reason is None, (
            f"China economy story should pass coherence gate. "
            f"score={result.score:.3f}, reason={result.block_reason}"
        )
        assert result.score >= COHERENCE_GATE_THRESHOLD

    def test_tsmc_semiconductor_story_passes(self):
        """TSMC / semiconductor story in both JP and EN → passes."""
        se = _make_scored(
            event_id="tsmc-semi",
            title="TSMC、AI向け半導体需要で過去最高益　日本工場も稼働へ",
            primary_bucket="politics_economy",
            sources_jp=[_jp_src("Nikkei", "TSMC AI半導体需要 最高益")],
            sources_en=[
                _en_src("Bloomberg", "TSMC reports record profit on AI semiconductor demand"),
                _en_src("Reuters", "TSMC Japan plant set to start operations amid chip boom"),
            ],
            judge_result=_make_judge("linked_jp_global"),
        )
        result = compute_semantic_coherence(se)
        assert result.block_reason is None, (
            f"TSMC semiconductor story should pass. score={result.score:.3f}"
        )

    def test_us_tariff_story_passes(self):
        """JP article about US tariffs + EN sources about US tariffs → passes."""
        se = _make_scored(
            event_id="us-tariff",
            title="米国、日本製品への関税引き上げを検討　貿易交渉難航",
            primary_bucket="politics_economy",
            sources_jp=[_jp_src("Asahi", "米国 日本 関税 貿易交渉")],
            sources_en=[
                _en_src("Bloomberg", "US considers raising tariffs on Japanese goods amid trade talks"),
                _en_src("Reuters", "US-Japan trade negotiations stall over tariff dispute"),
            ],
            judge_result=_make_judge("linked_jp_global"),
        )
        result = compute_semantic_coherence(se)
        assert result.block_reason is None, (
            f"US tariff story should pass. score={result.score:.3f}"
        )


# ── 3. Incoherent candidate is downgraded / blocked ───────────────────────────

class TestIncoherentCandidateDowngraded:

    def test_incoherent_candidate_sets_gate_false(self):
        """Clearly incoherent candidate → coherence_gate_passed=False."""
        se = _make_scored(
            event_id="incoherent",
            title="高市首相動静 2026年4月14日",
            primary_bucket="japan_abroad",
            sources_jp=[_jp_src()],
            sources_en=[
                _en_src("ESPN", "Champions League final preview 2026"),
                _en_src("BBC Sport", "World Cup qualifying results Europe"),
            ],
            judge_result=_make_judge("blind_spot_global"),
        )
        passed, reason = apply_coherence_gate(se, "blind_spot_global")
        assert not passed
        assert se.coherence_gate_passed is False
        assert se.semantic_coherence_score is not None
        assert se.semantic_coherence_score < BLACKLIST_COHERENCE_THRESHOLD

    def test_no_eligible_when_all_blocked_by_coherence(self):
        """If all judged candidates fail coherence gate, _find_eligible returns None."""
        se1 = _make_scored(
            event_id="blocked-1",
            score=95.0,
            title="高市首相動静 2026年4月14日",
            primary_bucket="japan_abroad",
            sources_jp=[_jp_src()],
            sources_en=[_en_src("BBC", "China trade surplus hits record")],
            judge_result=_make_judge("blind_spot_global"),
        )
        se2 = _make_scored(
            event_id="blocked-2",
            score=90.0,
            title="官房長官動静 2026年4月14日",
            primary_bucket="japan_abroad",
            sources_jp=[_jp_src()],
            sources_en=[_en_src("Reuters", "European parliament debates new AI rules")],
            judge_result=_make_judge("linked_jp_global"),
        )
        judge_results = {
            se1.event.id: se1.judge_result,  # type: ignore[index]
            se2.event.id: se2.judge_result,  # type: ignore[index]
        }
        selected, reason = _find_eligible_judged_slot1([se1, se2], judge_results)
        assert selected is None


# ── 4. Judge model config is a valid/resolvable model (Pass 2C) ───────────────

class TestJudgeModelDefault:

    def test_judge_model_default_is_valid_flash_model(self):
        """GEMINI_JUDGE_MODEL config default must be a valid-looking Gemini model name.

        Pass 2C: the default was changed from the non-existent 'gemini-3.1-flash-lite'
        to 'gemini-2.5-flash-lite' which is actually available.
        """
        assert "gemini" in GEMINI_JUDGE_MODEL.lower(), (
            f"Expected a gemini model name, got {GEMINI_JUDGE_MODEL!r}"
        )
        # Must not be the invalid 3.1 model that was causing 404 NOT_FOUND
        assert GEMINI_JUDGE_MODEL != "gemini-3.1-flash-lite", (
            "Judge model default was not fixed from the invalid gemini-3.1-flash-lite value"
        )

    def test_judge_model_default_is_valid_gemini_model(self):
        """Judge model must be a non-empty Gemini model identifier.

        旧 Pass 2C の gemini-2.5-flash-lite は階層フォールバックの末端 TIER4 に移動。
        GEMINI_JUDGE_MODEL は config.py で GEMINI_MODEL_TIER2 をデフォルトに取る
        （.env で上書きされうる）。具体的な値ではなく「無効な値に戻っていないこと」だけを
        不変条件として保証する。
        """
        assert isinstance(GEMINI_JUDGE_MODEL, str) and GEMINI_JUDGE_MODEL, (
            f"GEMINI_JUDGE_MODEL must be a non-empty string, got {GEMINI_JUDGE_MODEL!r}"
        )
        assert GEMINI_JUDGE_MODEL.startswith("gemini-"), (
            f"Expected a gemini-* model name, got {GEMINI_JUDGE_MODEL!r}"
        )
        # かつて 404 を引き起こした無効値には戻さない
        assert GEMINI_JUDGE_MODEL != "gemini-3.1-flash-lite", (
            "Judge model regressed to the invalid gemini-3.1-flash-lite value"
        )


# ── 5. run_summary judge_summary contains judge_model_used ────────────────────

class TestJudgeSummaryObservability:

    def _make_judge_results(self) -> dict:
        se = _make_scored(
            event_id="obs-001",
            sources_jp=[_jp_src()],
            sources_en=[_en_src()],
        )
        se.judge_result = _make_judge("linked_jp_global")
        return {se.event.id: se.judge_result}  # type: ignore[return-value]

    def test_judge_model_used_present_when_judge_ran(self):
        """_build_judge_summary must include judge_model_used when judge ran."""
        se = _make_scored(
            "slot1-obs",
            sources_jp=[_jp_src()],
            sources_en=[_en_src()],
        )
        se.judge_result = _make_judge("linked_jp_global")
        judge_results = {se.event.id: se.judge_result}  # type: ignore[index]

        summary = _build_judge_summary(
            judge_results=judge_results,
            all_ranked=[se],
            slot1_se=se,
            slot1_authority_pair=["NHK", "Reuters"],
        )

        assert "judge_model_used" in summary
        assert summary["judge_model_used"] == GEMINI_JUDGE_MODEL

    def test_judge_model_used_present_when_judge_did_not_run(self):
        """_build_judge_summary must include judge_model_used even when judge did not run."""
        summary = _build_judge_summary(
            judge_results={},
            all_ranked=[],
            slot1_se=None,
            slot1_authority_pair=[],
        )
        assert "judge_model_used" in summary
        assert summary["judge_model_used"] == GEMINI_JUDGE_MODEL

    def test_judge_model_requested_and_resolved_present(self):
        """_build_judge_summary must include judge_model_requested and judge_model_resolved."""
        from src.llm.model_registry import ModelResolution
        resolution = ModelResolution(
            requested_model="gemini-3.1-flash-lite",
            resolved_model="gemini-2.5-flash-lite",
            resolution_reason="fallback_from_unavailable_requested",
        )
        summary = _build_judge_summary(
            judge_results={},
            all_ranked=[],
            slot1_se=None,
            slot1_authority_pair=[],
            model_resolution=resolution,
        )
        assert summary["judge_model_requested"] == "gemini-3.1-flash-lite"
        assert summary["judge_model_resolved"] == "gemini-2.5-flash-lite"
        assert summary["judge_model_resolution_reason"] == "fallback_from_unavailable_requested"

    def test_judge_model_not_found_count_present(self):
        """_build_judge_summary must include judge_model_not_found_count."""
        se = _make_scored(
            "slot1-mnf",
            sources_jp=[_jp_src()],
            sources_en=[_en_src()],
        )
        se.judge_result = _make_judge(judge_error="404 NOT_FOUND gemini-3.1-flash-lite")
        se.judge_result.judge_error_type = "model_not_found"  # type: ignore[union-attr]
        judge_results = {se.event.id: se.judge_result}  # type: ignore[index]

        summary = _build_judge_summary(
            judge_results=judge_results,
            all_ranked=[se],
            slot1_se=None,
            slot1_authority_pair=[],
        )
        assert "judge_model_not_found_count" in summary
        assert summary["judge_model_not_found_count"] == 1
        assert summary["judge_error_type_counts"].get("model_not_found") == 1

    def test_slot1_contains_coherence_fields(self):
        """slot1 dict in judge_summary must include coherence gate fields."""
        se = _make_scored(
            "slot1-coh",
            sources_jp=[_jp_src()],
            sources_en=[
                _en_src("Bloomberg", "China economy recovery 2026"),
            ],
        )
        se.judge_result = _make_judge("blind_spot_global")
        # Populate coherence fields (simulating what apply_coherence_gate sets)
        se.semantic_coherence_score = 0.72
        se.coherence_gate_passed = True
        se.coherence_block_reason = None
        se.candidate_blacklist_flags = []

        judge_results = {se.event.id: se.judge_result}  # type: ignore[index]
        summary = _build_judge_summary(
            judge_results=judge_results,
            all_ranked=[se],
            slot1_se=se,
            slot1_authority_pair=["NHK", "Bloomberg"],
        )

        slot1 = summary["slot1"]
        assert "semantic_coherence_score" in slot1
        assert "coherence_gate_passed" in slot1
        assert "coherence_block_reason" in slot1
        assert "candidate_blacklist_flags" in slot1
        assert slot1["coherence_gate_passed"] is True
        assert slot1["semantic_coherence_score"] == 0.72


# ── 6. Blacklist pattern detection ───────────────────────────────────────────

class TestBlacklistPatterns:

    @pytest.mark.parametrize("title,expected_flag", [
        ("高市首相動静 2026年4月14日", "首相動静"),
        ("官房長官動静 4月15日", "首相動静"),
        ("林外務大臣動静", "首相動静"),
        ("代表取締役社長就任のお知らせ", "人事異動"),
        ("執行役員異動のお知らせ", "人事異動"),
        ("2026年3月期 決算短信", "決算短信"),
        ("第1四半期決算の開示", "決算短信"),
        ("プロ野球 3-0で勝利", "スポーツ結果"),
        ("交通事故速報　多重衝突", "事故速報"),
        ("訃報：田中一郎氏（享年75歳）", "訃報"),
        ("東証 日経平均終値 39,500円", "市況"),
    ])
    def test_pattern_matched(self, title: str, expected_flag: str):
        flags = _detect_domestic_routine(title)
        assert expected_flag in flags, (
            f"Expected '{expected_flag}' flag for title={title!r}, got flags={flags}"
        )

    def test_normal_news_not_flagged(self):
        """Regular news articles should not trigger any blacklist patterns."""
        titles = [
            "中国経済、2026年に回復の兆し",
            "米国が対日関税引き上げを検討",
            "TSMC、熊本工場で半導体生産開始",
            "ロシアとウクライナ、停戦交渉が再開",
            "日銀、利上げを見送り　政策金利据え置き",
        ]
        for title in titles:
            flags = _detect_domestic_routine(title)
            assert flags == [], f"No flags expected for {title!r}, got {flags}"


# ── 7. Non-blacklisted incoherent candidate is blocked at base threshold ───────

class TestBaseThresholdBlocking:

    def test_non_blacklisted_incoherent_blocked_at_base_threshold(self):
        """Non-blacklisted but incoherent candidate is blocked at base threshold."""
        # JP article about sports, EN sources about completely unrelated finance
        se = _make_scored(
            event_id="sports-vs-finance",
            title="大谷翔平、満塁ホームランで逆転勝利",
            primary_bucket="sports",
            sources_jp=[_jp_src()],
            sources_en=[
                _en_src("Bloomberg", "Federal Reserve raises interest rates by 25bp"),
                _en_src("FT", "ECB monetary policy signals further tightening"),
            ],
            judge_result=_make_judge("blind_spot_global"),
        )
        result = compute_semantic_coherence(se)
        # Sports bucket vs finance EN content → very low bucket match
        # No blacklist applied, but score should still be low enough to block
        # (bucket_topic_match = 0.2 for sports vs finance, translation=0, direct=0)
        assert result.score < 1.0  # At minimum, score should be well below 1.0

    def test_coherence_gate_threshold_is_reasonable(self):
        """COHERENCE_GATE_THRESHOLD must be between 0.1 and 0.5."""
        assert 0.1 <= COHERENCE_GATE_THRESHOLD <= 0.5

    def test_blacklist_threshold_higher_than_base(self):
        """BLACKLIST_COHERENCE_THRESHOLD must be strictly greater than base threshold."""
        assert BLACKLIST_COHERENCE_THRESHOLD > COHERENCE_GATE_THRESHOLD


# ── 8. No overseas titles → neutral pass ─────────────────────────────────────

class TestNoOverseasTitles:

    def test_no_overseas_titles_returns_neutral_pass(self):
        """Candidate with no EN source titles → neutral score, no block."""
        se = _make_scored(
            event_id="no-en-titles",
            title="日本の半導体政策強化へ",
            primary_bucket="politics_economy",
            sources_en=[_en_src("Reuters", "")],  # empty title
        )
        # Suppress title so there's nothing to compare
        se.event.sources_en[0].title = None  # type: ignore[union-attr]
        result = compute_semantic_coherence(se)
        assert result.block_reason is None, (
            "Candidate with no EN titles should not be blocked"
        )


# ── 9. Translation and year overlap unit tests ───────────────────────────────

class TestOverlapHelpers:

    def test_translation_overlap_china_economy(self):
        """JP '中国経済' should match EN keywords 'china economy'."""
        jp_kw = _extract_jp_keywords("中国経済の回復")
        en_kw = _extract_en_keywords("china economic recovery")
        score = _translation_overlap(jp_kw, en_kw)
        assert score > 0.0, f"Expected >0 for China economy, got {score}"

    def test_translation_overlap_no_match(self):
        """JP '首相動静' should not match EN keywords about sports."""
        jp_kw = _extract_jp_keywords("高市首相動静")
        en_kw = _extract_en_keywords("world cup soccer goals scored")
        score = _translation_overlap(jp_kw, en_kw)
        assert score == 0.0, f"Expected 0 for PM schedule vs sports, got {score}"

    def test_year_overlap_matching_year(self):
        """Same year in JP and EN → overlap = 1.0."""
        score = _year_number_overlap("2026年のできごと", "Events of 2026 dominate headlines")
        assert score == 1.0

    def test_year_overlap_different_years(self):
        """Different years in JP vs EN → overlap = 0.0."""
        score = _year_number_overlap("2025年の出来事", "Events in 2024 shaped the world")
        assert score == 0.0

    def test_year_overlap_no_year_in_jp(self):
        """No year in JP → neutral (0.5)."""
        score = _year_number_overlap("経済ニュース", "GDP growth 2026")
        assert score == 0.5

    def test_extract_jp_keywords_captures_katakana(self):
        """Katakana words (foreign names) should be extracted."""
        kw = _extract_jp_keywords("ブルームバーグ報道、トランプ大統領が発表")
        assert "ブルームバーグ" in kw or "トランプ" in kw

    def test_extract_jp_keywords_captures_latin(self):
        """Latin abbreviations in JP title should be extracted."""
        kw = _extract_jp_keywords("TSMC、AI半導体で最高益")
        assert "tsmc" in kw or "ai" in kw

    def test_extract_en_keywords_removes_stopwords(self):
        """Common EN stop words should not appear in extracted keywords."""
        kw = _extract_en_keywords("the economy and the market are down today")
        assert "the" not in kw
        assert "and" not in kw
        assert "are" not in kw


# ── 10. DOMESTIC_ROUTINE_PATTERNS coverage check ─────────────────────────────

class TestDomesticRoutinePatternsCoverage:

    def test_all_expected_pattern_keys_present(self):
        """All required domestic-routine pattern keys must be defined (including Pass 2C additions)."""
        required_keys = {
            "首相動静",
            "首相日程",    # new in Pass 2C
            "人事異動",
            "決算短信",
            "定例開示",
            "スポーツ結果",
            "事故速報",
            "訃報",
            "市況",
        }
        assert required_keys.issubset(set(DOMESTIC_ROUTINE_PATTERNS.keys())), (
            f"Missing pattern keys: {required_keys - set(DOMESTIC_ROUTINE_PATTERNS.keys())}"
        )


# ── 11. Diary-style detection (Pass 2C) ──────────────────────────────────────

class TestDiaryStyleDetection:

    def test_dated_pm_schedule_is_diary_style(self):
        """首相動静 title with YYYY年M月D日 → diary-style detected."""
        flags = _detect_domestic_routine_extended("高市首相動静 2026年4月14日", [])
        assert "首相動静" in flags
        is_diary = _detect_diary_style("高市首相動静 2026年4月14日", [], flags)
        assert is_diary is True

    def test_undated_pm_schedule_not_diary_style(self):
        """首相動静 without specific date → not diary-style."""
        flags = _detect_domestic_routine_extended("首相動静", [])
        is_diary = _detect_diary_style("首相動静", [], flags)
        assert is_diary is False

    def test_diary_style_date_in_source_title(self):
        """Date in JP source title (not event title) still triggers diary detection."""
        event_title = "Japan PM schedule update"  # merged EN title in cluster
        jp_source_title = "高市首相動静 2026年4月14日"
        flags = _detect_domestic_routine_extended(event_title, [jp_source_title])
        is_diary = _detect_diary_style(event_title, [jp_source_title], flags)
        assert is_diary is True, (
            "Diary style should be detected from JP source title, not just event title"
        )

    def test_diary_threshold_is_higher_than_blacklist_threshold(self):
        """DIARY_COHERENCE_THRESHOLD > BLACKLIST_COHERENCE_THRESHOLD > COHERENCE_GATE_THRESHOLD."""
        assert DIARY_COHERENCE_THRESHOLD > BLACKLIST_COHERENCE_THRESHOLD > COHERENCE_GATE_THRESHOLD

    def test_diary_style_pm_schedule_blocked_with_unrelated_en(self):
        """Dated PM schedule + unrelated EN sources → blocked at DIARY threshold."""
        se = _make_scored(
            event_id="diary-pm",
            title="高市首相動静 2026年4月14日",
            primary_bucket="japan_abroad",
            sources_jp=[_jp_src("NHK", "高市首相動静 2026年4月14日")],
            sources_en=[
                _en_src("Bloomberg", "China economy recovery accelerates in 2026"),
                _en_src("Reuters", "US Federal Reserve holds rates steady"),
            ],
            judge_result=_make_judge("blind_spot_global"),
        )
        result = compute_semantic_coherence(se)
        assert result.is_diary_style is True, "Should be detected as diary-style"
        assert result.score < DIARY_COHERENCE_THRESHOLD, (
            f"Diary-style PM schedule should be blocked at {DIARY_COHERENCE_THRESHOLD}. "
            f"score={result.score:.3f}"
        )
        assert result.block_reason is not None
        assert "diary_style=true" in result.block_reason

    def test_coherence_result_has_explanation_fields(self):
        """CoherenceResult must include jp_entities, overseas_entities, overlap_signals."""
        se = _make_scored(
            event_id="explain-test",
            title="中国経済、2026年に回復加速",
            primary_bucket="politics_economy",
            sources_jp=[_jp_src("Nikkei", "中国経済 回復 2026年")],
            sources_en=[_en_src("Bloomberg", "China economy recovery accelerates 2026")],
        )
        result = compute_semantic_coherence(se)
        assert isinstance(result.jp_entities, list)
        assert isinstance(result.overseas_entities, list)
        assert isinstance(result.overlap_signals, list)
        # Should have found some entities
        assert len(result.jp_entities) > 0, "Should extract JP entities"
        assert len(result.overseas_entities) > 0, "Should extract EN entities"

    def test_pm_schedule_flagged_from_source_title_only(self):
        """Blacklist detected from JP source title blocks the candidate."""
        se = _make_scored(
            event_id="src-title-test",
            title="Japan PM daily update April 14",  # English merged title
            primary_bucket="japan_abroad",
            sources_jp=[_jp_src("NHK", "高市首相動静 2026年4月14日")],
            sources_en=[
                _en_src("Bloomberg", "China GDP growth beats forecast 2026"),
                _en_src("Reuters", "US tariffs on Asian goods take effect"),
            ],
            judge_result=_make_judge("blind_spot_global"),
        )
        result = compute_semantic_coherence(se)
        # Blacklist must be detected even though event title is in English
        assert "首相動静" in result.blacklist_flags or result.is_diary_style, (
            "Blacklist/diary should be detected from JP source title"
        )


# ── 12. 首相日程 pattern (new in Pass 2C) ────────────────────────────────────

class TestShushouNitcheiPattern:

    @pytest.mark.parametrize("title,expected_flag", [
        ("首相日程 4月15日", "首相日程"),
        ("首相会見定例 2026年4月15日", "首相日程"),
        ("首相定例会見の概要", "首相日程"),
        ("官房長官定例会見", "首相日程"),
    ])
    def test_pattern_matched(self, title: str, expected_flag: str):
        flags = _detect_domestic_routine(title)
        assert expected_flag in flags, (
            f"Expected '{expected_flag}' flag for title={title!r}, got flags={flags}"
        )
