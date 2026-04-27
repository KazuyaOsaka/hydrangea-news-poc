"""src/analysis/perspective_extractor.py のテスト（ルールベース、LLM 不要）。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pytest

from src.analysis.perspective_extractor import (
    _calculate_cultural_blindspot_score,
    _calculate_framing_inversion_score,
    _calculate_hidden_stakes_score,
    _calculate_silence_gap_score,
    _meets_cultural_blindspot_conditions,
    _meets_framing_inversion_conditions,
    _meets_hidden_stakes_conditions,
    _meets_silence_gap_conditions,
    extract_perspectives,
)
from src.shared.models import (
    ChannelConfig,
    NewsEvent,
    PerspectiveCandidate,
    ScoredEvent,
    SourceRef,
)


# ---------- helpers ----------

def _en_sources(n: int) -> list[SourceRef]:
    return [
        SourceRef(name=f"S{i}", url=f"https://en.example.com/{i}", region="global")
        for i in range(n)
    ]


def _jp_sources(n: int) -> list[SourceRef]:
    return [
        SourceRef(name=f"J{i}", url=f"https://jp.example.com/{i}", region="japan",
                  language="ja", country="JP")
        for i in range(n)
    ]


def _scored(
    *,
    title: str = "",
    summary: str = "",
    sources_jp: int = 0,
    sources_en: int = 0,
    breakdown: Optional[dict] = None,
    background: Optional[str] = None,
    impact_on_japan: Optional[str] = None,
    japan_view: Optional[str] = None,
    global_view: Optional[str] = None,
    tags: Optional[list[str]] = None,
    editorial_tags: Optional[list[str]] = None,
    sources_by_locale: Optional[dict[str, list[SourceRef]]] = None,
) -> ScoredEvent:
    ev_kwargs: dict = dict(
        id="evt-1",
        title=title,
        summary=summary,
        category="politics",
        source="Reuters",
        published_at=datetime.now(timezone.utc),
        sources_jp=_jp_sources(sources_jp),
        sources_en=_en_sources(sources_en),
        background=background,
        impact_on_japan=impact_on_japan,
        japan_view=japan_view,
        global_view=global_view,
        tags=tags or [],
    )
    if sources_by_locale is not None:
        ev_kwargs["sources_by_locale"] = sources_by_locale
    ev = NewsEvent(**ev_kwargs)
    return ScoredEvent(
        event=ev,
        score=10.0,
        score_breakdown=breakdown or {},
        editorial_tags=editorial_tags or [],
    )


# ---------- silence_gap ----------

def test_silence_gap_meets_when_all_conditions_satisfied():
    se = _scored(
        sources_en=3,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is True


def test_silence_gap_meets_when_jp_count_is_minor_share():
    """新ルール: jp/en 比 1/2 以下なら silence_gap 成立 (jp=1, en=3 → 1*2 ≤ 3)。

    旧ルールでは jp >= 1 で即不成立だったが、本来 silence_gap は
    「日本側の報道量が薄い」を判定する軸であり、"jp が少数でも en が多い"
    なら成立とみなすほうが正しい。
    """
    se = _scored(
        sources_en=3,
        sources_jp=1,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is True


def test_silence_gap_fails_when_jp_share_is_majority():
    """jp が en と同数以上なら「日本側の量が薄い」とは言えない。"""
    se = _scored(
        sources_en=2,
        sources_jp=3,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is False


def test_silence_gap_meets_when_en_minimum_two_and_jp_zero():
    """新ルール: en >= 2 (旧 3 から緩和) AND jp == 0 → 成立。"""
    se = _scored(
        sources_en=2,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is True


def test_silence_gap_fails_when_below_min_en_threshold():
    """en < 2 はどんな条件でも silence_gap 不成立 (海外側の母数不足)。"""
    se = _scored(
        sources_en=1,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is False


def test_silence_gap_meets_when_only_ijai_passes_interest_filter():
    """新ルール: ga と ijai は OR (旧 AND) → 片方 4.0 以上でトピック関心度通過。"""
    se = _scored(
        sources_en=3,
        sources_jp=0,
        breakdown={"global_attention_score": 3.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is True


def test_silence_gap_fails_when_both_interest_signals_low():
    """ga と ijai が両方 4.0 未満ならトピック関心度フィルタを通過せず不成立。"""
    se = _scored(
        sources_en=5,
        sources_jp=0,
        breakdown={"global_attention_score": 2.0, "indirect_japan_impact_score": 2.0},
    )
    assert _meets_silence_gap_conditions(se) is False


def test_silence_gap_meets_when_jp_text_volume_much_smaller():
    """新ルール: jp:en 件数が同数でも、テキスト量が大幅に少なければ成立。

    sources_jp=2, sources_en=2 だが jp_view が短く en_view が長い → 情報量比で成立。
    """
    se = _scored(
        sources_en=2,
        sources_jp=2,
        japan_view="短い",  # 2 chars
        global_view="A much longer global view text spanning many words and sentences." * 3,
        breakdown={"global_attention_score": 5.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is True


def test_silence_gap_fails_when_text_volume_balanced():
    """件数同数 + テキスト量も同程度 → silence_gap は成立しない。"""
    se = _scored(
        sources_en=2,
        sources_jp=2,
        japan_view="日本側の論評が十分にある長文の記述例。" * 5,
        global_view="Global side commentary of similar length." * 3,
        breakdown={"global_attention_score": 5.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is False


def test_silence_gap_score_is_clamped_to_10():
    se = _scored(
        sources_en=10,
        sources_jp=0,
        breakdown={"global_attention_score": 10.0, "indirect_japan_impact_score": 10.0},
    )
    score, _ = _calculate_silence_gap_score(se)
    assert score == 10.0


def test_silence_gap_score_jp_penalty_drives_below_zero_clamped_to_zero():
    se = _scored(
        sources_en=1,
        sources_jp=5,
        breakdown={"global_attention_score": 0.0, "indirect_japan_impact_score": 0.0},
    )
    score, _ = _calculate_silence_gap_score(se)
    assert score == 0.0


# ---------- framing_inversion ----------

def test_framing_inversion_meets_when_jp_and_en_present_and_pg_high():
    se = _scored(
        sources_en=2,
        sources_jp=1,
        breakdown={"perspective_gap_score": 7.0},
    )
    assert _meets_framing_inversion_conditions(se) is True


def test_framing_inversion_fails_when_no_jp_source():
    se = _scored(sources_en=3, sources_jp=0, breakdown={"perspective_gap_score": 8.0})
    assert _meets_framing_inversion_conditions(se) is False


def test_framing_inversion_score_includes_en_count_bonus():
    se = _scored(
        sources_en=4,
        sources_jp=1,
        breakdown={"perspective_gap_score": 6.0},
    )
    score, reason = _calculate_framing_inversion_score(se)
    # 6 + 4*0.5 = 8
    assert score == pytest.approx(8.0)
    assert "perspective_gap" in reason


# ---------- hidden_stakes ----------

def test_hidden_stakes_meets_when_impact_high_and_kw_present():
    se = _scored(
        title="TSMC fab decision affects Toyota supply chain",
        breakdown={"indirect_japan_impact_score": 6.0},
    )
    assert _meets_hidden_stakes_conditions(se) is True


def test_hidden_stakes_meets_when_ijai_alone_is_strong():
    """新ルール: ijai >= 7.0 (STRONG) 単独で成立 (企業キーワード不要)。

    メキシコ → 日本原油輸出 (ijai=9.0) のような事例を救済する経路。
    """
    se = _scored(
        title="Eurozone monetary policy review",
        breakdown={"indirect_japan_impact_score": 8.0},
    )
    assert _meets_hidden_stakes_conditions(se) is True


def test_hidden_stakes_fails_without_japan_industry_keyword_at_mid_ijai():
    """ijai 中程度 (4.0 ≤ ijai < 7.0) で企業キーワードも間接影響キーワードも
    無ければ不成立。旧テストの代替: ijai=6.0, "Eurozone monetary policy review"
    は間接影響キーワードを含まない (monetary policy / eurozone は両方 KW 外)。
    """
    se = _scored(
        title="Eurozone monetary policy review",
        breakdown={"indirect_japan_impact_score": 5.0},  # < STRONG
    )
    assert _meets_hidden_stakes_conditions(se) is False


def test_hidden_stakes_meets_at_mid_ijai_with_indirect_keyword():
    """新ルール: ijai 中程度でも indirect_japan_impact_keywords (oil supply 等)
    があれば成立。企業名キーワードがないケースを救済する経路。
    """
    se = _scored(
        title="Mexico oil supply route opens to Japan",
        breakdown={"indirect_japan_impact_score": 5.0},
    )
    assert _meets_hidden_stakes_conditions(se) is True


def test_hidden_stakes_fails_when_ijai_below_minimum():
    """ijai < 3.0 はどんなキーワードがあっても問答無用で不成立。"""
    se = _scored(
        title="Toyota wins regional design award",
        breakdown={"indirect_japan_impact_score": 2.5},
    )
    assert _meets_hidden_stakes_conditions(se) is False


def test_hidden_stakes_fails_with_zero_ijai():
    """ijai が 0 (score_breakdown 未設定) なら不成立。"""
    se = _scored(title="Toyota recall affects Asia", breakdown={})
    assert _meets_hidden_stakes_conditions(se) is False


def test_hidden_stakes_score_includes_impact_unmentioned_bonus():
    """JP ソースありで impact_on_japan が空 → +2 ボーナス。"""
    se = _scored(
        title="Toyota faces new chip restrictions",
        sources_jp=1,
        breakdown={"indirect_japan_impact_score": 5.0},
    )
    score, reason = _calculate_hidden_stakes_score(se)
    # 5.0 (impact) + 1 (Toyota) + 2.0 (unmentioned) = 8.0
    assert score == pytest.approx(8.0)
    assert "impact_unmentioned_bonus=2.0" in reason


def test_hidden_stakes_no_unmentioned_bonus_when_no_jp_sources():
    se = _scored(
        title="Toyota faces new chip restrictions",
        sources_jp=0,
        breakdown={"indirect_japan_impact_score": 5.0},
    )
    score, _ = _calculate_hidden_stakes_score(se)
    # 5 + 1 + 0 = 6
    assert score == pytest.approx(6.0)


# ---------- cultural_blindspot ----------

def test_cultural_blindspot_meets_with_cultural_signals():
    se = _scored(
        title="Saudi religious tradition complicates new reform",
        summary="The monarchy's role under Islamic tradition is changing",
        breakdown={"geopolitics_depth_score": 5.0},
    )
    assert _meets_cultural_blindspot_conditions(se) is True


def test_cultural_blindspot_fails_without_signals():
    se = _scored(title="Stock market closes flat", summary="")
    assert _meets_cultural_blindspot_conditions(se) is False


def test_cultural_blindspot_score_clamped():
    se = _scored(
        title="religion tradition monarchy ritual caste gender feminism",
        editorial_tags=["religion", "tradition"],
        breakdown={"geopolitics_depth_score": 10.0},
    )
    score, _ = _calculate_cultural_blindspot_score(se)
    assert score <= 10.0


def test_cultural_blindspot_meets_with_non_western_region_and_source():
    """新ルール: 文化キーワードが無くても、event の region に non_western 系を含み
    かつ非西側媒体ソースがあれば成立 (region+source パターン)。
    """
    sources_by_locale = {
        "japan": _jp_sources(1),
        "global_south": [
            SourceRef(
                name="BuenosAiresTimes",
                url="https://batimes.com.ar/x",
                region="global_south",
                language="en",
                country="AR",
            ),
        ],
    }
    se = _scored(
        title="Argentine economic policy shift sparks regional debate",
        sources_jp=1,
        sources_en=1,
        sources_by_locale=sources_by_locale,
        breakdown={"geopolitics_depth_score": 0.0},
    )
    assert _meets_cultural_blindspot_conditions(se) is True


def test_cultural_blindspot_fails_with_only_western_sources():
    """西側 region (global / europe) のみのソース構成 → region+source パターン不成立、
    かつ文化キーワードも無いなら全体不成立。"""
    sources_by_locale = {
        "japan": _jp_sources(1),
        "global": _en_sources(2),
        "europe": [
            SourceRef(name="LeMonde", url="https://lemonde.fr/x", region="europe",
                      language="en", country="FR"),
        ],
    }
    se = _scored(
        title="EU summit on trade policy concludes",
        sources_jp=1,
        sources_en=2,
        sources_by_locale=sources_by_locale,
        breakdown={"geopolitics_depth_score": 0.0},
    )
    assert _meets_cultural_blindspot_conditions(se) is False


def test_cultural_blindspot_meets_via_source_name_when_region_unset():
    """非西側媒体名は region 未設定でも検出される (古いデータの救済)。"""
    sources_by_locale = {
        "japan": _jp_sources(1),
        "middle_east": [
            SourceRef(name="AlJazeera", url="https://aljazeera.com/x",
                      region="middle_east", language="en", country="QA"),
        ],
    }
    se = _scored(
        title="Gulf states reshape energy strategy",
        sources_jp=1,
        sources_en=1,
        sources_by_locale=sources_by_locale,
    )
    assert _meets_cultural_blindspot_conditions(se) is True


def test_cultural_blindspot_score_gets_non_western_bonus():
    """region+source 経路成立時は uniqueness に +2.0 のボーナス。"""
    sources_by_locale = {
        "japan": _jp_sources(1),
        "global_south": [
            SourceRef(name="FolhaDeSPaulo", url="https://folha.com.br/x",
                      region="global_south", language="en", country="BR"),
        ],
    }
    se = _scored(
        title="Brazil moves on land reform",
        sources_jp=1,
        sources_en=1,
        sources_by_locale=sources_by_locale,
        breakdown={"geopolitics_depth_score": 0.0},
    )
    score, reason = _calculate_cultural_blindspot_score(se)
    # uniqueness=0 (no cultural kw, no gd) + 2.0 bonus → 2.0
    assert score == pytest.approx(2.0)
    assert "non_western_bonus=2.0" in reason


# ---------- extract_perspectives ----------

def test_extract_returns_only_viable_axes():
    se = _scored(
        sources_en=3,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    candidates = extract_perspectives(se)
    axes = {c.axis for c in candidates}
    assert "silence_gap" in axes
    # framing_inversion は jp source が 0 なので除外
    assert "framing_inversion" not in axes


def test_extract_sorted_by_score_descending():
    se = _scored(
        title="Toyota chip restrictions trade war religion tradition",
        sources_en=4,
        sources_jp=1,
        breakdown={
            "global_attention_score": 7.0,
            "indirect_japan_impact_score": 5.0,
            "perspective_gap_score": 7.0,
            "geopolitics_depth_score": 6.0,
        },
    )
    candidates = extract_perspectives(se)
    scores = [c.score for c in candidates]
    assert scores == sorted(scores, reverse=True)


def test_extract_filters_by_channel_config_perspective_axes():
    se = _scored(
        sources_en=3,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    cfg = ChannelConfig(
        channel_id="restricted",
        display_name="Restricted",
        enabled=True,
        source_regions=["global"],
        perspective_axes=["framing_inversion"],
        duration_profiles=["breaking_shock_60s"],
        prompt_variant="r_v1",
        posts_per_day=1,
    )
    candidates = extract_perspectives(se, channel_config=cfg)
    axes = {c.axis for c in candidates}
    assert "silence_gap" not in axes  # 軸が許可リストに含まれない


def test_extract_geo_lens_allows_all_four_axes():
    se = _scored(
        title="Toyota chip restrictions amid Saudi religion tradition",
        sources_en=3,
        sources_jp=1,
        breakdown={
            "global_attention_score": 7.0,
            "indirect_japan_impact_score": 6.0,
            "perspective_gap_score": 7.0,
            "geopolitics_depth_score": 5.0,
        },
    )
    cfg = ChannelConfig.load("geo_lens")
    candidates = extract_perspectives(se, channel_config=cfg)
    # 4軸の少なくとも複数が成立しうる
    axes = {c.axis for c in candidates}
    assert axes.issubset(
        {"silence_gap", "framing_inversion", "hidden_stakes", "cultural_blindspot"}
    )


def test_extract_returns_empty_when_no_axis_meets_conditions():
    se = _scored(title="Local news", summary="A small town story")
    candidates = extract_perspectives(se)
    assert candidates == []


def test_perspective_candidate_has_evidence_refs():
    se = _scored(
        sources_en=3,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    candidates = extract_perspectives(se)
    sg = next(c for c in candidates if c.axis == "silence_gap")
    assert all(ref.startswith("https://") for ref in sg.evidence_refs)
    assert len(sg.evidence_refs) == 3


def test_perspective_candidate_pydantic_model_returned():
    se = _scored(
        sources_en=3,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    candidates = extract_perspectives(se)
    assert all(isinstance(c, PerspectiveCandidate) for c in candidates)


# ---------- メキシコ原油事例リアル再現フィクスチャ ----------
#
# 実 LLM 試運転 (2026-04-26 01:14〜) で観点不成立スキップが発生した
# cls-ccdac99d90dc 相当のイベント。本ファイル修正 (rule-based perspective
# rebuild) 後は最低 hidden_stakes が確実に成立すべき。

def _make_mexico_oil_event_fixture() -> ScoredEvent:
    """メキシコ→日本 100 万バレル原油輸出事例の再現フィクスチャ。

    再現する事実: sources_jp=2, sources_en=2 (うち global_south 系を含む),
    ijai≈9.0, regions={japan, global_south}。
    """
    sources_by_locale = {
        "japan": [
            SourceRef(
                name="Nikkei", url="https://nikkei.com/mexico-oil",
                title="メキシコから日本へ100万バレル原油輸出",
                region="japan", language="ja", country="JP",
            ),
            SourceRef(
                name="NHK", url="https://nhk.or.jp/mexico-oil",
                title="メキシコ原油の対日輸出が再開",
                region="japan", language="ja", country="JP",
            ),
        ],
        "global_south": [
            SourceRef(
                name="BuenosAiresTimes", url="https://batimes.com.ar/mexico-oil",
                title="Mexico ships one million barrels of crude oil to Japan in landmark export deal",
                region="global_south", language="en", country="AR",
            ),
            SourceRef(
                name="FolhaDeSPaulo", url="https://folha.com.br/mexico-oil",
                title="Mexican crude oil supply to Japan signals shift away from Middle East dependence",
                region="global_south", language="en", country="BR",
            ),
        ],
    }
    ev = NewsEvent(
        id="cls-ccdac99d90dc",
        title="Mexico ships 1M barrels of crude oil to Japan",
        summary=(
            "Mexico has resumed oil supply to Japan with a one million barrel export. "
            "The deal eases Japan's reliance on Middle East crude oil and adds a new "
            "energy supply route across the Pacific."
        ),
        category="energy",
        source="BuenosAiresTimes",
        published_at=datetime.now(timezone.utc),
        japan_view="メキシコ産原油100万バレルが日本に輸出された。",  # 短い JP 論評
        global_view=(
            "Mexico's one million barrel crude oil export to Japan is widely covered "
            "across Latin American media as a strategic shift in Pacific energy trade. "
            "Coverage emphasizes the diversification away from Middle East oil supply, "
            "the implications for Mexico's state oil firm Pemex, and the renewed trans-Pacific "
            "shipping lane that is expected to reshape regional energy logistics."
        ),
        sources_by_locale=sources_by_locale,
    )
    return ScoredEvent(
        event=ev,
        score=8.5,
        score_breakdown={
            "indirect_japan_impact_score": 9.0,
            "global_attention_score": 5.0,
            "perspective_gap_score": 2.0,
            "geopolitics_depth_score": 6.0,
        },
    )


def test_mexico_oil_event_triggers_hidden_stakes():
    """本バッチ最重要: メキシコ原油事例で hidden_stakes が確実に成立する。

    旧実装ではこの事例で 4 軸全部不成立 → 分析レイヤースキップ → 動画生成スキップ
    が発生したため、本テストは「観点不成立スキップ事故」のリグレッション検出。
    """
    se = _make_mexico_oil_event_fixture()
    assert _meets_hidden_stakes_conditions(se) is True


def test_mexico_oil_event_extract_returns_at_least_one_candidate():
    """4 軸どれか 1 つでも成立すれば extract_perspectives は非空リストを返す。

    ここでは hidden_stakes と cultural_blindspot の両方が成立する想定。
    """
    se = _make_mexico_oil_event_fixture()
    candidates = extract_perspectives(se)
    assert len(candidates) >= 1
    axes = {c.axis for c in candidates}
    # hidden_stakes は必達
    assert "hidden_stakes" in axes
    # cultural_blindspot も region+source パターンで成立すべき
    assert "cultural_blindspot" in axes
