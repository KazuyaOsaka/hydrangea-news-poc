from __future__ import annotations

from datetime import datetime

import pytest

from src.shared.models import NewsEvent, SourceRef
from src.triage.scoring import compute_score, compute_score_full


def _make_event(**kwargs) -> NewsEvent:
    defaults = dict(
        id="test-001",
        title="テストニュース",
        summary="テスト用の要約文です。",
        category="economy",
        source="テストソース",
        published_at=datetime(2026, 3, 31, 10, 0, 0),
        tags=[],
    )
    defaults.update(kwargs)
    return NewsEvent(**defaults)


def test_economy_base_score():
    event = _make_event(category="economy")
    score, breakdown = compute_score(event)
    # category_base は常に 85.0
    assert breakdown["category_base"] == 85.0
    # 品質ペナルティ・editorial 調整後のスコアは 85 より低くなる
    assert score > 0.0
    assert score < 85.0


def test_keyword_bonus_applied():
    event = _make_event(title="日銀が利上げを決定", summary="政策金利を引き上げた。")
    score, breakdown = compute_score(event)
    assert "kw:利上げ" in breakdown
    assert breakdown["kw:利上げ"] == 10.0


def test_score_capped_at_100():
    event = _make_event(
        category="economy",
        title="利上げ 利下げ 増税 減税 解散",
        summary="利上げ 利下げ 増税 減税",
        tags=["a", "b", "c", "d"],
    )
    score, _ = compute_score(event)
    assert score <= 100.0


def test_tag_bonus():
    event_no_tags = _make_event(tags=[])
    event_with_tags = _make_event(tags=["a", "b", "c"])
    score_no, bd_no = compute_score(event_no_tags)
    score_with, bd_with = compute_score(event_with_tags)
    assert bd_with["tag_bonus"] > bd_no["tag_bonus"]
    assert score_with > score_no


def test_unknown_category_defaults():
    event = _make_event(category="unknown_category")
    score, breakdown = compute_score(event)
    assert breakdown["category_base"] == 50.0


def test_sports_lower_than_economy():
    economy = _make_event(category="economy")
    sports = _make_event(category="sports")
    score_e, _ = compute_score(economy)
    score_s, _ = compute_score(sports)
    assert score_e > score_s


def test_cross_lang_bonus_applied():
    # gap_reasoning + sources_jp が揃うと FULL ボーナス(5.0)が適用される
    event = _make_event(
        japan_view="[NHK] 日銀が利上げを決定",
        global_view="[Reuters] Bank of Japan raises rates",
        gap_reasoning="日本では金融政策の影響を中心に報じられているが、海外では円安・グローバル市場への影響が主軸",
        sources_jp=[SourceRef(name="NHK", url="https://nhk.or.jp")],
    )
    score, breakdown = compute_score(event)
    assert "cross_lang_bonus" in breakdown
    assert breakdown["cross_lang_bonus"] == 5.0


def test_cross_lang_bonus_not_applied_when_views_identical():
    same = "[NHK] テスト記事"
    event = _make_event(japan_view=same, global_view=same)
    _, breakdown = compute_score(event)
    assert "cross_lang_bonus" not in breakdown


def test_cross_lang_bonus_not_applied_when_view_missing():
    event = _make_event(japan_view="[NHK] テスト記事", global_view=None)
    _, breakdown = compute_score(event)
    assert "cross_lang_bonus" not in breakdown


def test_cross_lang_bonus_increases_score():
    base_event = _make_event()
    cross_event = _make_event(
        japan_view="[NHK] 日本語ビュー",
        global_view="[Reuters] English view",
    )
    score_base, _ = compute_score(base_event)
    score_cross, _ = compute_score(cross_event)
    assert score_cross > score_base


# ── breaking_shock_score テスト ─────────────────────────────────────────────

def test_breaking_shock_ceasefire_oil():
    """停戦 + 原油 + 暴落キーワードで breaking_shock_score >= 5.0 かつ market_shock タグ。"""
    event = _make_event(
        # ceasefire (1 breaking hit) + crude oil, plunge, crash (3 market hits → +2.5) = 5.0
        title="Iran ceasefire deal reached, crude oil plunges and crash",
        summary="Ceasefire agreement reached. Crude oil prices crash and plunge sharply.",
        category="politics",
    )
    _, breakdown, tier, tags, _ = compute_score_full(event)
    bs = breakdown["editorial:breaking_shock_score"]
    assert bs >= 5.0, f"Expected bs>=5.0, got {bs}"
    assert "breaking_shock" in tags or "market_shock" in tags


def test_breaking_shock_sanction_market():
    """制裁+関税+Ukraine衝突+S&P暴落で Tier 1 になる（bs>=7 + gd>=3）。"""
    event = _make_event(
        # sanction + tariff (2 breaking hits = 5.0) + S&P500, crash (2 market hits → +2.5) + combo → ~8.0
        # + Ukraine conflict → gd >= 3 → breaking_shock_t1 fires
        title="Emergency sanctions and tariff ban amid Ukraine conflict, S&P500 crash",
        summary="Ceasefire breakdown triggers emergency sanctions, tariff ban, S&P500 crash.",
        category="politics",
    )
    _, breakdown, tier, tags, _ = compute_score_full(event)
    bs = breakdown["editorial:breaking_shock_score"]
    assert bs >= 7.0, f"Expected bs>=7.0, got {bs}"
    assert tier == "Tier 1"
    assert "breaking_shock" in tags


def test_breaking_shock_boosts_score_vs_baseline():
    """breaking_shock キーワードありはなしより高スコアになる。"""
    base = _make_event(
        title="Global economic outlook update",
        summary="Analysts discuss long-term economic trends.",
        category="economy",
    )
    shock = _make_event(
        title="Emergency ceasefire collapse, sanctions imposed, oil crash",
        summary="Ceasefire breakdown triggers emergency sanctions and crude oil crash.",
        category="economy",
    )
    score_base, _ = compute_score(base)
    score_shock, _ = compute_score(shock)
    assert score_shock > score_base


def test_breaking_shock_score_zero_for_normal_news():
    """通常ニュースの breaking_shock_score はゼロ（またはそれに近い）。"""
    event = _make_event(
        title="新しいスマートフォンが発売",
        summary="大手メーカーが新型スマートフォンを発表した。",
        category="technology",
    )
    _, breakdown, _, _, _ = compute_score_full(event)
    bs = breakdown["editorial:breaking_shock_score"]
    assert bs == 0.0, f"Expected 0.0 for normal news, got {bs}"


# ── 疑惑警告テスト ─────────────────────────────────────────────────────────

def test_allegation_warning_triggered_without_auth_source():
    """疑惑キーワードあり + 権威ソースなしで allegation 警告が出る。"""
    from src.generation.script_writer import _evidence_warning_section
    event = _make_event(
        title="CEO faces insider trading allegation",
        summary="Alleged insider trading under investigation.",
        source="anonymous_blog",
    )
    warning = _evidence_warning_section(event)
    assert "allegation" in warning.lower() or "疑惑" in warning


def test_allegation_warning_suppressed_with_auth_source_and_evidence():
    """権威ソース + gap_reasoning がある場合は疑惑警告が出ない。"""
    from src.generation.script_writer import _evidence_warning_section
    event = _make_event(
        title="CEO charged with insider trading, Reuters reports",
        summary="Reuters confirmed insider trading charges.",
        source="Reuters",
        global_view="Reuters: Charges filed.",
        gap_reasoning="JP media focus on regulatory response; EN media focus on market impact.",
        sources_en=[SourceRef(name="Reuters", url="https://reuters.com/test")],
    )
    warning = _evidence_warning_section(event)
    # 疑惑警告部分が含まれないこと
    assert "allegation-unverified" not in warning
