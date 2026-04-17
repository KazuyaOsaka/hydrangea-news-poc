"""Regression tests for:
  - indirect_japan_impact_score (scoring.py)
  - Blind Spot Global appraisal type (appraisal.py)
  - Flagship gate (scheduler.py)
  - expected_dedup_full_batch diagnosis (debug_reports.py)
"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.shared.models import NewsEvent, ScoredEvent, SourceRef
from src.triage.scoring import _score_editorial_axes
from src.triage.appraisal import (
    _get_safety_gate,
    _score_blind_spot_global,
    apply_editorial_appraisal,
    APPRAISAL_SCORE_MAX,
)
from src.triage.scheduler import (
    FLAGSHIP_LINKED_JP_GLOBAL,
    FLAGSHIP_BLIND_SPOT_GLOBAL,
    get_flagship_class,
    _passes_flagship_gate,
)
from src.ingestion.debug_reports import write_source_load_report


# ── helpers ───────────────────────────────────────────────────────────────────

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


def _en_src(name: str = "Reuters") -> SourceRef:
    return SourceRef(name=name, url=f"https://{name.lower()}.com/1", title="x", language="en", country="US", region="global")


def _jp_src(name: str = "NHK") -> SourceRef:
    return SourceRef(name=name, url=f"https://{name.lower()}.or.jp/1", title="x", language="ja", country="JP", region="japan")


def _make_scored(
    event_id: str = "s-001",
    score: float = 70.0,
    primary_bucket: str = "coverage_gap",
    score_breakdown: dict | None = None,
    appraisal_type: str | None = None,
    appraisal_cautions: str | None = None,
    editorial_appraisal_score: float = 0.0,
    **event_kwargs,
) -> ScoredEvent:
    event = _make_event(event_id, **event_kwargs)
    bd = score_breakdown or {}
    return ScoredEvent(
        event=event,
        score=score,
        score_breakdown=bd,
        primary_tier="Tier 2",
        editorial_tags=[],
        primary_bucket=primary_bucket,
        appraisal_type=appraisal_type,
        appraisal_cautions=appraisal_cautions,
        editorial_appraisal_score=editorial_appraisal_score,
    )


def _scored_with_axes(
    event_id: str = "s-001",
    score: float = 70.0,
    primary_bucket: str = "coverage_gap",
    axes: dict | None = None,
    **event_kwargs,
) -> ScoredEvent:
    """Helper: build ScoredEvent with editorial:* axes in score_breakdown."""
    bd = {f"editorial:{k}": v for k, v in (axes or {}).items()}
    return _make_scored(
        event_id=event_id,
        score=score,
        primary_bucket=primary_bucket,
        score_breakdown=bd,
        **event_kwargs,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. indirect_japan_impact_score — scoring.py
# ─────────────────────────────────────────────────────────────────────────────

class TestIndirectJapanImpactScore:
    def test_hormuz_title_scores_high(self):
        """'Strait of Hormuz blockade' in title → high indirect Japan impact."""
        event = _make_event(
            title="Trump plans Strait of Hormuz blockade targeting Iran",
            summary="President threatens to close key shipping lane.",
            global_view="The Hormuz strait carries a third of the world's LNG.",
        )
        axes = _score_editorial_axes(event)
        ijai = axes["indirect_japan_impact_score"]
        assert ijai >= 5.0, f"Expected ijai >= 5.0 for Hormuz story, got {ijai}"

    def test_lng_keyword_scores(self):
        """LNG keyword in summary → indirect Japan impact > 0."""
        event = _make_event(
            title="OPEC cuts oil output by 2 million barrels",
            summary="Global LNG supply tightens as OPEC announces production cuts.",
        )
        axes = _score_editorial_axes(event)
        ijai = axes["indirect_japan_impact_score"]
        assert ijai >= 3.0, f"Expected ijai >= 3.0 for LNG/OPEC story, got {ijai}"

    def test_tsmc_semiconductor_scores(self):
        """TSMC in title → indirect Japan impact > 0."""
        event = _make_event(
            title="TSMC likely to book fourth straight quarter of record profit on AI demand",
            summary="Taiwan's TSMC reports strong earnings on insatiable semiconductor demand.",
        )
        axes = _score_editorial_axes(event)
        ijai = axes["indirect_japan_impact_score"]
        assert ijai >= 4.0, f"Expected ijai >= 4.0 for TSMC story, got {ijai}"

    def test_unrelated_story_scores_zero_or_low(self):
        """Sports story unrelated to energy/finance → indirect Japan impact = 0."""
        event = _make_event(
            title="Ohtani hits grand slam in World Series",
            summary="Shohei Ohtani starred in last night's game.",
        )
        axes = _score_editorial_axes(event)
        ijai = axes["indirect_japan_impact_score"]
        assert ijai == 0.0, f"Expected ijai=0 for sports story, got {ijai}"

    def test_score_capped_at_10(self):
        """Multiple energy/finance keywords should not push score above 10."""
        event = _make_event(
            title="Hormuz blockade OPEC LNG supply chain sanctions export control yen BOJ",
            summary="lng hormuz opec tsmc usdjpy boj export control supply disruption sanctions",
        )
        axes = _score_editorial_axes(event)
        assert axes["indirect_japan_impact_score"] <= 10.0

    def test_uses_global_view_not_only_title(self):
        """Score should pick up keywords from global_view, not only title+summary."""
        event = _make_event(
            title="Oil markets react to geopolitical tensions",
            summary="Markets are volatile.",
            global_view="The Hormuz strait is critical for Japan's LNG imports.",
        )
        axes = _score_editorial_axes(event)
        ijai = axes["indirect_japan_impact_score"]
        assert ijai >= 4.0, f"Expected ijai >= 4 when keywords in global_view, got {ijai}"

    def test_key_returned_in_axes_dict(self):
        """indirect_japan_impact_score must be present in the returned dict."""
        event = _make_event()
        axes = _score_editorial_axes(event)
        assert "indirect_japan_impact_score" in axes


# ─────────────────────────────────────────────────────────────────────────────
# 2. Blind Spot Global — appraisal.py
# ─────────────────────────────────────────────────────────────────────────────

class TestBlindSpotGlobalAppraisal:
    def _bsg_axes(
        self,
        ijai: float = 5.0,
        ga: float = 6.0,
        cg: float = 6.0,
        bip: float = 1.0,
        has_jp_view: float = 0.0,
        jr: float = 0.0,
    ) -> dict:
        return {
            "editorial:indirect_japan_impact_score": ijai,
            "editorial:global_attention_score":      ga,
            "editorial:coverage_gap_score":          cg,
            "editorial:background_inference_potential": bip,
            "editorial:has_jp_view": has_jp_view,
            "editorial:has_en_view": 1.0,
            "editorial:japan_relevance_score": jr,
            "editorial:perspective_gap_score": 0.0,
        }

    def test_safety_gate_lifted_for_high_ijai(self):
        """EN-only + low_jr story with high ijai+ga should NOT be suppressed (bip not required)."""
        # bip=0 to test that the exemption works even for pool events with stale bip=0
        bd = self._bsg_axes(ijai=5.0, ga=6.0, bip=0.0, jr=0.0)
        se = _make_scored(
            score_breakdown=bd,
            sources_en=[_en_src()],
        )
        suppressed, reason = _get_safety_gate(se)
        assert not suppressed, (
            f"Expected safety gate to lift for high ijai story, got suppressed=True ({reason})"
        )

    def test_safety_gate_still_suppresses_low_ijai(self):
        """EN-only + low_jr + low ijai → still suppressed."""
        bd = self._bsg_axes(ijai=0.0, ga=3.0, bip=0.0, jr=0.0)
        se = _make_scored(score_breakdown=bd)
        suppressed, reason = _get_safety_gate(se)
        assert suppressed
        assert "en_only" in reason

    def test_safety_gate_suppresses_when_no_en_src(self):
        """no EN sources → always suppressed regardless of ijai."""
        bd = self._bsg_axes(ijai=8.0, ga=8.0, bip=3.0, jr=0.0)
        # No sources_en
        se = _make_scored(score_breakdown=bd)
        suppressed, reason = _get_safety_gate(se)
        assert suppressed

    def test_score_blind_spot_global_returns_positive(self):
        """_score_blind_spot_global returns > 0 for strong EN-only ijai+ga story."""
        bd = self._bsg_axes(ijai=5.0, ga=7.0, cg=6.0, bip=2.0, has_jp_view=0.0)
        se = _make_scored(score_breakdown=bd, sources_en=[_en_src()])
        score = _score_blind_spot_global(se)
        assert score > 0.0
        assert score <= APPRAISAL_SCORE_MAX

    def test_score_blind_spot_global_zero_if_jp_view_present(self):
        """If JP view is present, blind_spot_global should return 0 (not EN-only)."""
        bd = self._bsg_axes(ijai=5.0, ga=7.0, bip=2.0, has_jp_view=1.0)
        se = _make_scored(score_breakdown=bd, sources_en=[_en_src()])
        score = _score_blind_spot_global(se)
        assert score == 0.0

    def test_score_blind_spot_global_zero_if_no_en_src(self):
        """No EN sources → blind_spot_global returns 0."""
        bd = self._bsg_axes(ijai=5.0, ga=7.0, bip=2.0, has_jp_view=0.0)
        se = _make_scored(score_breakdown=bd)  # no sources_en
        score = _score_blind_spot_global(se)
        assert score == 0.0

    def test_score_blind_spot_global_zero_if_low_ijai(self):
        """Low ijai → blind_spot_global returns 0."""
        bd = self._bsg_axes(ijai=1.0, ga=8.0, bip=3.0, has_jp_view=0.0)
        se = _make_scored(score_breakdown=bd, sources_en=[_en_src()])
        score = _score_blind_spot_global(se)
        assert score == 0.0

    def test_apply_editorial_appraisal_assigns_blind_spot_global(self):
        """Full appraisal pipeline assigns 'Blind Spot Global' to qualifying EN-only story."""
        bd = self._bsg_axes(ijai=5.0, ga=7.0, cg=6.0, bip=2.0, has_jp_view=0.0, jr=0.0)
        se = _make_scored(
            score_breakdown=bd,
            sources_en=[_en_src("Bloomberg"), _en_src("Reuters")],
        )
        result = apply_editorial_appraisal([se])
        top = result[0]
        assert top.appraisal_type == "Blind Spot Global", (
            f"Expected 'Blind Spot Global', got {top.appraisal_type!r}"
        )
        assert top.editorial_appraisal_score > 0.0

    def test_blind_spot_global_not_assigned_when_jp_view_present(self):
        """JP view present → 'Blind Spot Global' must not be assigned."""
        bd = self._bsg_axes(ijai=5.0, ga=7.0, cg=6.0, bip=2.0, has_jp_view=1.0, jr=5.0)
        se = _make_scored(
            score_breakdown=bd,
            sources_en=[_en_src()],
        )
        result = apply_editorial_appraisal([se])
        top = result[0]
        assert top.appraisal_type != "Blind Spot Global"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Flagship Gate — scheduler.py
# ─────────────────────────────────────────────────────────────────────────────

class TestFlagshipGate:
    def _axes_bd(self, **kv) -> dict:
        """Build score_breakdown with editorial:* prefix."""
        return {f"editorial:{k}": v for k, v in kv.items()}

    def test_jp_only_no_en_src_blocked(self):
        """JP-only story (no EN sources) → flagship gate blocks."""
        bd = self._axes_bd(
            japan_relevance_score=8.0,
            global_attention_score=2.0,
            perspective_gap_score=0.0,
            background_inference_potential=0.0,
            indirect_japan_impact_score=0.0,
        )
        se = _make_scored(
            score_breakdown=bd,
            sources_jp=[_jp_src()],
            # No sources_en
        )
        passes, reason = _passes_flagship_gate(se)
        assert not passes
        assert "no_en_sources" in reason or "no_depth" in reason or "below_flagship" in reason or "weak_japan" in reason

    def test_linked_jp_global_passes(self):
        """JP+EN with high perspective_gap → flagship_linked_jp_global."""
        bd = self._axes_bd(
            japan_relevance_score=7.0,
            global_attention_score=6.0,
            perspective_gap_score=5.0,
            background_inference_potential=4.0,
            indirect_japan_impact_score=0.0,
        )
        se = _make_scored(
            score_breakdown=bd,
            sources_jp=[_jp_src()],
            sources_en=[_en_src()],
        )
        passes, reason = _passes_flagship_gate(se)
        assert passes
        assert reason == FLAGSHIP_LINKED_JP_GLOBAL

    def test_blind_spot_global_passes(self):
        """EN-only with Blind Spot Global appraisal + high ijai + high ga → flagship_blind_spot_global."""
        bd = self._axes_bd(
            japan_relevance_score=0.0,
            global_attention_score=7.0,
            perspective_gap_score=0.0,
            background_inference_potential=2.0,
            indirect_japan_impact_score=5.0,
        )
        se = _make_scored(
            score_breakdown=bd,
            appraisal_type="Blind Spot Global",
            sources_en=[_en_src()],
        )
        passes, reason = _passes_flagship_gate(se)
        assert passes
        assert reason == FLAGSHIP_BLIND_SPOT_GLOBAL

    def test_get_flagship_class_linked_jp_global(self):
        """get_flagship_class returns FLAGSHIP_LINKED_JP_GLOBAL for JP+EN+high_pg."""
        bd = self._axes_bd(
            japan_relevance_score=6.0,
            global_attention_score=5.0,
            perspective_gap_score=4.5,
            background_inference_potential=3.0,
            indirect_japan_impact_score=0.0,
        )
        se = _make_scored(
            score_breakdown=bd,
            sources_jp=[_jp_src()],
            sources_en=[_en_src()],
        )
        cls = get_flagship_class(se)
        assert cls == FLAGSHIP_LINKED_JP_GLOBAL

    def test_get_flagship_class_blind_spot_global(self):
        """get_flagship_class returns FLAGSHIP_BLIND_SPOT_GLOBAL for qualifying EN-only story."""
        bd = self._axes_bd(
            japan_relevance_score=0.0,
            global_attention_score=6.0,
            perspective_gap_score=0.0,
            background_inference_potential=1.0,
            indirect_japan_impact_score=4.5,
        )
        se = _make_scored(
            score_breakdown=bd,
            appraisal_type="Blind Spot Global",
            sources_en=[_en_src()],
        )
        cls = get_flagship_class(se)
        assert cls == FLAGSHIP_BLIND_SPOT_GLOBAL

    def test_get_flagship_class_none_for_weak_story(self):
        """Weak story returns None (no flagship class)."""
        bd = self._axes_bd(
            japan_relevance_score=2.0,
            global_attention_score=2.0,
            perspective_gap_score=0.0,
            background_inference_potential=0.0,
            indirect_japan_impact_score=0.0,
        )
        se = _make_scored(
            score_breakdown=bd,
            sources_en=[_en_src()],
        )
        cls = get_flagship_class(se)
        assert cls is None

    def test_passes_flagship_gate_returns_reason_string(self):
        """_passes_flagship_gate always returns (bool, str) — reason is non-empty on block."""
        bd = self._axes_bd(
            japan_relevance_score=1.0,
            global_attention_score=2.0,
            perspective_gap_score=0.0,
            background_inference_potential=0.0,
            indirect_japan_impact_score=1.0,
        )
        se = _make_scored(score_breakdown=bd, sources_en=[_en_src()])
        passes, reason = _passes_flagship_gate(se)
        assert isinstance(passes, bool)
        assert isinstance(reason, str)
        if not passes:
            assert len(reason) > 0


# ─────────────────────────────────────────────────────────────────────────────
# 4. expected_dedup_full_batch diagnosis — debug_reports.py
# ─────────────────────────────────────────────────────────────────────────────

class TestSourceLoadDiagnosis:
    def test_all_dedup_is_expected_not_bug(self, tmp_path):
        """loaded=0 with all duplicate_url drops → expected_dedup_full_batch, not bug_suspected."""
        run_stats = {
            "source_load_report": {
                "NHK_Politics": {
                    "normalized_count": 100,
                    "loaded_count": 0,
                    "dropped_count": 100,
                    "drop_reasons": {"duplicate_url": 100},
                }
            }
        }
        path = write_source_load_report(run_stats, tmp_path)
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["by_source"]["NHK_Politics"]["diagnosis"] == "expected_dedup_full_batch"
        assert data["summary"]["bug_suspected_sources"] == []
        assert "NHK_Politics" in data["summary"]["full_dedup_sources"]

    def test_mixed_drop_reasons_is_bug_suspected(self, tmp_path):
        """loaded=0 with non-duplicate reasons → bug_suspected."""
        run_stats = {
            "source_load_report": {
                "Nikkei": {
                    "normalized_count": 10,
                    "loaded_count": 0,
                    "dropped_count": 10,
                    "drop_reasons": {"duplicate_url": 5, "parse_error": 5},
                }
            }
        }
        path = write_source_load_report(run_stats, tmp_path)
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["by_source"]["Nikkei"]["diagnosis"] == "bug_suspected"
        assert "Nikkei" in data["summary"]["bug_suspected_sources"]
        assert "Nikkei" not in data["summary"]["full_dedup_sources"]

    def test_partial_dedup_with_some_loaded_is_expected_dedup(self, tmp_path):
        """Some loaded, some duplicate_url drops → expected_dedup (not full_batch)."""
        run_stats = {
            "source_load_report": {
                "Reuters": {
                    "normalized_count": 10,
                    "loaded_count": 5,
                    "dropped_count": 5,
                    "drop_reasons": {"duplicate_url": 5},
                }
            }
        }
        path = write_source_load_report(run_stats, tmp_path)
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["by_source"]["Reuters"]["diagnosis"] == "expected_dedup"

    def test_all_loaded_is_ok(self, tmp_path):
        """No drops → diagnosis=ok."""
        run_stats = {
            "source_load_report": {
                "BBC": {
                    "normalized_count": 20,
                    "loaded_count": 20,
                    "dropped_count": 0,
                    "drop_reasons": {},
                }
            }
        }
        path = write_source_load_report(run_stats, tmp_path)
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["by_source"]["BBC"]["diagnosis"] == "ok"

    def test_explanation_field_present(self, tmp_path):
        """Each source entry must include an 'explanation' field."""
        run_stats = {
            "source_load_report": {
                "TestSource": {
                    "normalized_count": 5,
                    "loaded_count": 5,
                    "dropped_count": 0,
                    "drop_reasons": {},
                }
            }
        }
        path = write_source_load_report(run_stats, tmp_path)
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "explanation" in data["by_source"]["TestSource"]

    def test_multiple_sources_mixed_diagnoses(self, tmp_path):
        """Multiple sources with different situations each get correct diagnosis."""
        run_stats = {
            "source_load_report": {
                "NHK_Politics": {
                    "normalized_count": 50, "loaded_count": 0,
                    "dropped_count": 50, "drop_reasons": {"duplicate_url": 50},
                },
                "FT": {
                    "normalized_count": 10, "loaded_count": 0,
                    "dropped_count": 10, "drop_reasons": {"parse_error": 5, "duplicate_url": 5},
                },
                "Reuters": {
                    "normalized_count": 20, "loaded_count": 15,
                    "dropped_count": 5, "drop_reasons": {"duplicate_url": 5},
                },
            }
        }
        path = write_source_load_report(run_stats, tmp_path)
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["by_source"]["NHK_Politics"]["diagnosis"] == "expected_dedup_full_batch"
        assert data["by_source"]["FT"]["diagnosis"] == "bug_suspected"
        assert data["by_source"]["Reuters"]["diagnosis"] == "expected_dedup"
        assert data["summary"]["bug_suspected_sources"] == ["FT"]
        assert data["summary"]["full_dedup_sources"] == ["NHK_Politics"]
