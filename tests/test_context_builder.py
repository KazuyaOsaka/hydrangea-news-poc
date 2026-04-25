"""src/analysis/context_builder.py のテスト。

build_analysis_context は LLM 呼び出しを一切行わない。article_snippets と
background_questions が観点候補から正しく構築されることを検証する。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from unittest.mock import patch

import pytest

from src.analysis.context_builder import (
    AnalysisContext,
    build_analysis_context,
)
from src.shared.models import (
    ChannelConfig,
    NewsEvent,
    PerspectiveCandidate,
    ScoredEvent,
    SourceRef,
)


def _make_event(
    *,
    sources_jp: list[SourceRef] = None,
    sources_en: list[SourceRef] = None,
    sources_by_locale: Optional[dict] = None,
    title: str = "Headline",
    summary: str = "Summary",
) -> NewsEvent:
    return NewsEvent(
        id="evt-ctx-1",
        title=title,
        summary=summary,
        category="politics",
        source="Reuters",
        published_at=datetime.now(timezone.utc),
        sources_jp=sources_jp or [],
        sources_en=sources_en or [],
        sources_by_locale=sources_by_locale or {},
    )


def _scored(event: NewsEvent) -> ScoredEvent:
    return ScoredEvent(event=event, score=10.0)


def _candidate(axis: str, score: float = 7.0) -> PerspectiveCandidate:
    return PerspectiveCandidate(
        axis=axis,
        score=score,
        reasoning=f"reason for {axis}",
        evidence_refs=["https://en.example.com/0"],
    )


# ---------- LLM-free 性質 ----------

def test_build_context_does_not_call_llm():
    """LLMClient が一切インスタンス化されないことを確認する。"""
    se = _scored(_make_event(
        sources_en=[SourceRef(name="Reuters", url="https://r.example/1", region="global")],
    ))
    candidates = [_candidate("silence_gap")]

    # factory のクライアント生成関数群が呼ばれないことを確認。
    with patch("src.llm.factory.get_analysis_llm_client") as get_analysis, \
         patch("src.llm.factory.get_script_llm_client") as get_script, \
         patch("src.llm.factory.get_judge_llm_client") as get_judge:
        ctx = build_analysis_context(se, candidates)

    get_analysis.assert_not_called()
    get_script.assert_not_called()
    get_judge.assert_not_called()
    assert isinstance(ctx, AnalysisContext)


# ---------- article_snippets 抽出 ----------

def test_snippets_extracted_from_sources_by_locale():
    refs_jp = [SourceRef(name="Nikkei", url="https://nk.example/1", region="japan",
                         language="ja", country="JP", title="日経の見出し")]
    refs_global = [SourceRef(name="Reuters", url="https://r.example/1", region="global",
                              language="en", country="US", title="Reuters headline")]
    se = _scored(_make_event(sources_by_locale={"japan": refs_jp, "global": refs_global}))
    ctx = build_analysis_context(se, [_candidate("silence_gap")])
    regions = {s["region"] for s in ctx.article_snippets}
    assert {"japan", "global"} <= regions
    titles = {s["title"] for s in ctx.article_snippets}
    assert "日経の見出し" in titles
    assert "Reuters headline" in titles


def test_snippets_fallback_to_sources_jp_en_when_no_locale_map():
    se = _scored(_make_event(
        sources_jp=[SourceRef(name="Asahi", url="https://a.example/1")],
        sources_en=[SourceRef(name="BBC", url="https://b.example/1")],
    ))
    ctx = build_analysis_context(se, [_candidate("silence_gap")])
    names = [s["name"] for s in ctx.article_snippets]
    assert "Asahi" in names
    assert "BBC" in names


def test_snippets_dedup_by_url():
    """sources_by_locale で同じ URL が複数 region に出てきても重複しない。"""
    same = SourceRef(name="Wire", url="https://w.example/1", region="global")
    se = _scored(_make_event(sources_by_locale={
        "global": [same],
        "europe": [SourceRef(name="WireEU", url="https://w.example/1", region="europe")],
    }))
    ctx = build_analysis_context(se, [_candidate("silence_gap")])
    urls = [s["url"] for s in ctx.article_snippets]
    assert urls.count("https://w.example/1") == 1


def test_event_summary_and_title_passed_through():
    se = _scored(_make_event(title="T", summary="S"))
    ctx = build_analysis_context(se, [_candidate("silence_gap")])
    assert ctx.event_title == "T"
    assert ctx.event_summary == "S"


# ---------- background_questions 構築 ----------

def test_background_questions_per_axis_emitted():
    candidates = [
        _candidate("silence_gap"),
        _candidate("framing_inversion"),
    ]
    se = _scored(_make_event())
    ctx = build_analysis_context(se, candidates)
    text = "\n".join(ctx.background_questions)
    assert "[silence_gap]" in text
    assert "[framing_inversion]" in text


def test_background_questions_skip_duplicates():
    """同じ axis の候補が複数あっても背景質問は 1 度しか出さない。"""
    candidates = [_candidate("silence_gap", 8.0), _candidate("silence_gap", 6.0)]
    se = _scored(_make_event())
    ctx = build_analysis_context(se, candidates)
    text = "\n".join(ctx.background_questions)
    assert text.count("[silence_gap]") == 1


def test_background_questions_empty_when_no_candidates():
    se = _scored(_make_event())
    ctx = build_analysis_context(se, [])
    assert ctx.background_questions == []


# ---------- channel_id 解決 ----------

def test_channel_id_taken_from_channel_config_when_provided():
    se = _scored(_make_event())
    cfg = ChannelConfig(
        channel_id="custom_ch",
        display_name="Custom",
        enabled=True,
        prompt_variant="custom_v1",
        posts_per_day=1,
    )
    ctx = build_analysis_context(se, [_candidate("silence_gap")], channel_config=cfg)
    assert ctx.channel_id == "custom_ch"


def test_channel_id_falls_back_to_scored_event_default():
    se = _scored(_make_event())
    # ScoredEvent のデフォルトは "geo_lens"
    ctx = build_analysis_context(se, [_candidate("silence_gap")])
    assert ctx.channel_id == "geo_lens"


def test_perspective_candidates_preserved_in_context():
    cands = [_candidate("silence_gap", 9.0), _candidate("framing_inversion", 7.0)]
    se = _scored(_make_event())
    ctx = build_analysis_context(se, cands)
    assert [c.axis for c in ctx.perspective_candidates] == ["silence_gap", "framing_inversion"]
    assert all(isinstance(c, PerspectiveCandidate) for c in ctx.perspective_candidates)
