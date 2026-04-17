"""Tests for Editorial Appraisal (src/triage/appraisal.py)"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.shared.models import NewsEvent, ScoredEvent, SourceRef
from src.triage.appraisal import (
    _get_safety_gate,
    _is_evidence_weak,
    _score_media_blind_spot,
    _score_personal_stakes,
    _score_perspective_inversion,
    _score_structural_why,
    _assign_tags_multi,
    apply_editorial_appraisal,
    final_review,
    APPRAISAL_SCORE_MAX,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_event(event_id: str = "test-001", **kwargs) -> NewsEvent:
    defaults = dict(
        title="テストニュース",
        summary="テスト用の要約文です。",
        category="economy",
        source="TestSource",
        published_at=datetime(2026, 4, 9, 10, 0, 0),
        tags=[],
    )
    defaults.update(kwargs)
    return NewsEvent(id=event_id, **defaults)


def _make_scored(
    event_id: str = "s-001",
    score: float = 70.0,
    primary_bucket: str = "politics_economy",
    primary_tier: str = "Tier 2",
    score_breakdown: dict | None = None,
    editorial_tags: list[str] | None = None,
    **event_kwargs,
) -> ScoredEvent:
    event = _make_event(event_id, **event_kwargs)
    bd = score_breakdown or {}
    return ScoredEvent(
        event=event,
        score=score,
        score_breakdown=bd,
        primary_tier=primary_tier,
        editorial_tags=editorial_tags or [],
        primary_bucket=primary_bucket,
    )


def _scored_with_axes(
    event_id: str = "s-001",
    score: float = 70.0,
    primary_bucket: str = "politics_economy",
    axes: dict | None = None,
    **event_kwargs,
) -> ScoredEvent:
    """editorial axes を score_breakdown に埋め込んだ ScoredEvent を生成。"""
    base_axes = {
        "editorial:perspective_gap_score": 0.0,
        "editorial:coverage_gap_score": 0.0,
        "editorial:tech_geopolitics_score": 0.0,
        "editorial:big_event_score": 0.0,
        "editorial:geopolitics_depth_score": 0.0,
        "editorial:mass_appeal_score": 0.0,
        "editorial:japan_relevance_score": 5.0,
        "editorial:global_attention_score": 3.0,
        "editorial:crime_local_indicator": 0.0,
        "editorial:background_inference_potential": 0.0,
        "editorial:breaking_shock_score": 0.0,
        "editorial:japan_abroad_score": 0.0,
        "editorial:japanese_person_abroad_score": 0.0,
        "editorial:has_jp_view": 1.0,
        "editorial:has_en_view": 1.0,
        "editorial:_has_sports": 0.0,
        "editorial:_has_ent": 0.0,
    }
    if axes:
        base_axes.update(axes)
    return _make_scored(
        event_id=event_id,
        score=score,
        primary_bucket=primary_bucket,
        score_breakdown=base_axes,
        **event_kwargs,
    )


# ── Safety gate tests ─────────────────────────────────────────────────────────

def test_safety_gate_en_only_low_jr():
    """EN-only + low japan_relevance は抑制される。"""
    se = _scored_with_axes(
        axes={
            "editorial:has_jp_view": 0.0,
            "editorial:has_en_view": 1.0,
            "editorial:japan_relevance_score": 2.0,
        },
        global_view="Some English content",
    )
    suppressed, reason = _get_safety_gate(se)
    assert suppressed is True
    assert "en_only" in reason or "low_jr" in reason


def test_safety_gate_no_en_view_no_en_src():
    """EN ビューも sources_en もない場合は抑制される。"""
    se = _scored_with_axes(
        axes={
            "editorial:has_en_view": 0.0,
        },
    )
    # sources_en はデフォルト空、global_view もなし
    suppressed, reason = _get_safety_gate(se)
    assert suppressed is True


def test_safety_gate_all_axes_weak():
    """pg=0, cg<3, bip=0 のとき抑制される。"""
    se = _scored_with_axes(
        axes={
            "editorial:perspective_gap_score": 0.0,
            "editorial:coverage_gap_score": 1.0,
            "editorial:background_inference_potential": 0.0,
            "editorial:has_jp_view": 1.0,
            "editorial:has_en_view": 1.0,
            "editorial:japan_relevance_score": 6.0,
        },
        japan_view="日本の視点",
        global_view="Global view",
    )
    suppressed, reason = _get_safety_gate(se)
    assert suppressed is True


def test_safety_gate_passes_with_strong_evidence():
    """十分な evidence（pg>=4, has_both, gap_reasoning）があれば通過。"""
    se = _scored_with_axes(
        axes={
            "editorial:perspective_gap_score": 6.0,
            "editorial:background_inference_potential": 5.0,
            "editorial:has_jp_view": 1.0,
            "editorial:has_en_view": 1.0,
            "editorial:japan_relevance_score": 6.0,
        },
        japan_view="日本の視点",
        global_view="Global view",
        gap_reasoning="日本では英雄、海外ではビジネス合理性で評価",
        sources_en=[SourceRef(name="Reuters", url="https://reuters.com/test")],
    )
    suppressed, _ = _get_safety_gate(se)
    assert suppressed is False


# ── Perspective Inversion tests ───────────────────────────────────────────────

def test_perspective_inversion_requires_both_views():
    """JP/EN 両ビューがない場合は 0.0。"""
    se = _scored_with_axes(
        axes={
            "editorial:perspective_gap_score": 7.0,
            "editorial:has_jp_view": 0.0,
            "editorial:has_en_view": 1.0,
        },
    )
    score = _score_perspective_inversion(se)
    assert score == 0.0


def test_perspective_inversion_zero_pg():
    """perspective_gap_score=0 のとき 0.0。"""
    se = _scored_with_axes(
        axes={
            "editorial:perspective_gap_score": 0.0,
            "editorial:has_jp_view": 1.0,
            "editorial:has_en_view": 1.0,
        },
        japan_view="JP view",
        global_view="EN view",
    )
    score = _score_perspective_inversion(se)
    assert score == 0.0


def test_perspective_inversion_high_pg_with_gap_reasoning():
    """pg>=6 + gap_reasoning あり → 高スコア。"""
    se = _scored_with_axes(
        axes={
            "editorial:perspective_gap_score": 9.0,
            "editorial:background_inference_potential": 7.0,
            "editorial:has_jp_view": 1.0,
            "editorial:has_en_view": 1.0,
        },
        japan_view="日本側の視点",
        global_view="Global perspective",
        gap_reasoning="日本では英雄視、海外では法的責任の観点",
    )
    score = _score_perspective_inversion(se)
    assert score >= 3.0
    assert score <= APPRAISAL_SCORE_MAX


# ── Media Blind Spot tests ────────────────────────────────────────────────────

def test_media_blind_spot_requires_en_view_or_src():
    """EN ビューも sources_en もない場合は 0.0。"""
    se = _scored_with_axes(
        axes={
            "editorial:coverage_gap_score": 7.0,
            "editorial:has_en_view": 0.0,
        },
    )
    score = _score_media_blind_spot(se)
    assert score == 0.0


def test_media_blind_spot_low_cg():
    """coverage_gap < 3 のとき 0.0。"""
    se = _scored_with_axes(
        axes={
            "editorial:coverage_gap_score": 2.0,
            "editorial:has_en_view": 1.0,
        },
        global_view="English content",
    )
    score = _score_media_blind_spot(se)
    assert score == 0.0


def test_media_blind_spot_high_cg():
    """coverage_gap >= 6 → スコアあり。"""
    se = _scored_with_axes(
        axes={
            "editorial:coverage_gap_score": 8.0,
            "editorial:global_attention_score": 6.0,
            "editorial:has_en_view": 1.0,
            "editorial:japan_relevance_score": 6.0,
        },
        global_view="Very important overseas news",
        sources_en=[SourceRef(name="FT", url="https://ft.com/test")],
    )
    score = _score_media_blind_spot(se)
    assert score > 0.5
    assert score <= APPRAISAL_SCORE_MAX


# ── Structural Why tests ──────────────────────────────────────────────────────

def test_structural_why_requires_nonzero_bip():
    """background_inference_potential=0 のとき 0.0。"""
    se = _scored_with_axes(
        axes={"editorial:background_inference_potential": 0.0},
    )
    score = _score_structural_why(se)
    assert score == 0.0


def test_structural_why_high_bip_with_context():
    """bip>=7 + gap_reasoning + 戦略文脈 → 高スコア。"""
    se = _scored_with_axes(
        axes={
            "editorial:background_inference_potential": 8.0,
            "editorial:perspective_gap_score": 6.0,
            "editorial:geopolitics_depth_score": 6.0,
        },
        gap_reasoning="制度的背景から説明できる",
        background="歴史的文脈...",
        title="文化と制度の違いが生んだ格差",
        summary="歴史的な経緯と地政学的な観点から...",
    )
    score = _score_structural_why(se)
    assert score >= 3.0
    assert score <= APPRAISAL_SCORE_MAX


# ── Personal Stakes tests ─────────────────────────────────────────────────────

def test_personal_stakes_no_keywords_low_jr():
    """personal stakes キーワードなし + jr < 5 → 0.0。"""
    se = _scored_with_axes(
        axes={"editorial:japan_relevance_score": 3.0},
        title="Geopolitical summit in Europe",
        summary="European leaders discuss defense policy.",
    )
    score = _score_personal_stakes(se)
    assert score == 0.0


def test_personal_stakes_with_household_keywords():
    """家計・増税キーワードあり + jr >= 5 → スコアあり。"""
    se = _scored_with_axes(
        axes={
            "editorial:japan_relevance_score": 7.0,
            "editorial:big_event_score": 5.0,
        },
        title="家計への直撃、増税と物価上昇が同時進行",
        summary="家賃と光熱費が急騰、年金生活者の生活費を直撃している。",
        impact_on_japan="家計への直接的な打撃が予想される",
    )
    score = _score_personal_stakes(se)
    assert score >= 2.0
    assert score <= APPRAISAL_SCORE_MAX


def test_personal_stakes_english_keywords():
    """英語の personal stakes キーワードでも検出できる。"""
    se = _scored_with_axes(
        axes={
            "editorial:japan_relevance_score": 6.0,
            "editorial:breaking_shock_score": 5.0,
        },
        title="Fed rate hike hits household mortgage payments",
        summary="Rising interest rates affect household budgets and salary growth.",
    )
    score = _score_personal_stakes(se)
    assert score >= 1.0


# ── Appraisal score cap test ──────────────────────────────────────────────────

def test_appraisal_score_never_exceeds_max():
    """editorial_appraisal_score は APPRAISAL_SCORE_MAX を超えない。"""
    # 最強の候補: 全軸が高い
    se = _scored_with_axes(
        score=95.0,
        axes={
            "editorial:perspective_gap_score": 10.0,
            "editorial:background_inference_potential": 10.0,
            "editorial:coverage_gap_score": 8.0,
            "editorial:geopolitics_depth_score": 8.0,
            "editorial:big_event_score": 8.0,
            "editorial:japan_relevance_score": 8.0,
            "editorial:global_attention_score": 8.0,
            "editorial:has_jp_view": 1.0,
            "editorial:has_en_view": 1.0,
        },
        japan_view="日本側の視点",
        global_view="Global perspective",
        gap_reasoning="根拠ある差",
        sources_en=[SourceRef(name="Reuters", url="https://reuters.com/test")],
    )
    ranked = apply_editorial_appraisal([se])
    assert ranked[0].editorial_appraisal_score <= APPRAISAL_SCORE_MAX


# ── tags_multi tests ──────────────────────────────────────────────────────────

def test_tags_multi_includes_primary_bucket():
    """primary_bucket が tags_multi に含まれる。"""
    se = _scored_with_axes(primary_bucket="geopolitics")
    tags = _assign_tags_multi(se)
    assert "geopolitics" in tags


def test_tags_multi_personal_stakes_keyword():
    """personal stakes キーワードがあると personal_stakes タグが付く。"""
    se = _scored_with_axes(
        axes={"editorial:japan_relevance_score": 6.0},
        title="増税と家計への影響",
        summary="消費税の増税が家計と年金に直撃する。",
    )
    tags = _assign_tags_multi(se)
    assert "personal_stakes" in tags


def test_tags_multi_multi_bucket():
    """複数バケットに属する候補は複数 tags_multi を持つ。"""
    se = _scored_with_axes(
        primary_bucket="geopolitics",
        axes={
            "editorial:tech_geopolitics_score": 7.0,
            "editorial:geopolitics_depth_score": 6.0,
            "editorial:big_event_score": 5.0,
        },
    )
    tags = _assign_tags_multi(se)
    assert "geopolitics" in tags or "tech_geopolitics" in tags
    assert "politics_economy" in tags


# ── apply_editorial_appraisal integration tests ───────────────────────────────

def test_apply_appraisal_returns_same_count():
    """候補数は変わらない。"""
    candidates = [_scored_with_axes(f"e{i}") for i in range(20)]
    result = apply_editorial_appraisal(candidates)
    assert len(result) == 20


def test_apply_appraisal_suppressed_candidate_has_no_appraisal_type():
    """safety gate で抑制された候補は appraisal_type=None。"""
    # EN-only + low_jr → 抑制
    se = _scored_with_axes(
        axes={
            "editorial:has_jp_view": 0.0,
            "editorial:has_en_view": 1.0,
            "editorial:japan_relevance_score": 2.0,
        },
        global_view="Some English news",
    )
    result = apply_editorial_appraisal([se])
    assert result[0].appraisal_type is None


def test_apply_appraisal_strong_candidate_gets_type():
    """十分な evidence の候補は appraisal_type が設定される。"""
    se = _scored_with_axes(
        score=85.0,
        axes={
            "editorial:perspective_gap_score": 8.0,
            "editorial:background_inference_potential": 6.0,
            "editorial:has_jp_view": 1.0,
            "editorial:has_en_view": 1.0,
            "editorial:japan_relevance_score": 7.0,
        },
        japan_view="日本側の視点",
        global_view="Global perspective",
        gap_reasoning="根拠ある差",
        sources_en=[SourceRef(name="Reuters", url="https://reuters.com/test")],
    )
    result = apply_editorial_appraisal([se])
    assert result[0].appraisal_type is not None
    assert result[0].appraisal_hook is not None
    assert result[0].appraisal_cautions is not None


def test_apply_appraisal_beyond_limit_no_appraisal():
    """APPRAISAL_CANDIDATE_LIMIT 以降の候補は appraisal なし、tags_multi のみ。"""
    # 16本候補、limit=15
    candidates = [_scored_with_axes(f"e{i}") for i in range(16)]
    result = apply_editorial_appraisal(candidates, max_candidates=15)
    # 16番目（index=15）は appraisal なし
    assert result[15].appraisal_type is None
    # だが tags_multi は付与されている
    assert isinstance(result[15].tags_multi, list)


def test_apply_appraisal_does_not_alter_triage_score():
    """appraisal は triage score（score フィールド）を変えない。"""
    original_score = 75.5
    se = _scored_with_axes(score=original_score)
    result = apply_editorial_appraisal([se])
    assert result[0].score == original_score


# ── final_review tests ────────────────────────────────────────────────────────

def test_final_review_ok_when_clean():
    """問題のない5本には OK メッセージ（バラエティのある候補）。"""
    good_axes = {
        "editorial:perspective_gap_score": 5.0,
        "editorial:background_inference_potential": 4.0,
        "editorial:has_jp_view": 1.0,
        "editorial:has_en_view": 1.0,
        "editorial:japan_relevance_score": 6.0,
        "editorial:global_attention_score": 4.0,
    }
    buckets = ["geopolitics", "japan_abroad", "sports", "tech_geopolitics", "politics_economy"]
    appraisal_types = [
        "Perspective Inversion", "Media Blind Spot",
        "Personal Stakes", "Structural Why", "Perspective Inversion",
    ]
    candidates = []
    for i, (b, at) in enumerate(zip(buckets, appraisal_types)):
        se = _scored_with_axes(f"e{i}", score=80.0 - i, primary_bucket=b, axes=good_axes)
        # 直接 appraisal_type を設定して final_review のバリエーション要件を満たす
        se = se.model_copy(update={
            "appraisal_type": at,
            "appraisal_hook": f"Hook for {b}",
        })
        candidates.append(se)
    warnings = final_review(candidates)
    assert any("OK" in w for w in warnings)


def test_final_review_warns_on_bucket_overload():
    """同 primary_bucket 3本以上で警告。"""
    candidates = [
        _scored_with_axes(f"e{i}", primary_bucket="geopolitics")
        for i in range(5)
    ]
    appraised = apply_editorial_appraisal(candidates)
    warnings = final_review(appraised)
    assert any("primary_bucket" in w or "偏り" in w for w in warnings)


def test_final_review_warns_on_weak_evidence():
    """evidence 弱い候補が含まれると警告。"""
    # EN-only + low jr → evidence weak
    weak_se = _scored_with_axes(
        "weak-001",
        score=65.0,
        axes={
            "editorial:has_jp_view": 0.0,
            "editorial:has_en_view": 1.0,
            "editorial:japan_relevance_score": 2.0,
            "editorial:perspective_gap_score": 0.0,
            "editorial:background_inference_potential": 0.0,
        },
        global_view="English only",
    )
    warnings = final_review([weak_se])
    assert any("evidence" in w or "弱い" in w for w in warnings)
