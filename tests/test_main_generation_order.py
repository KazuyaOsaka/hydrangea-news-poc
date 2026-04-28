"""F-12-A: src/main.py の生成順序逆転（article → script）テスト。

_generate_outputs() 内で article_writer が script_writer より先に呼ばれること、
script_writer に article.markdown が article_text として渡されることを検証する。

write_article / write_script / generate_script_with_analysis / write_video_payload /
write_evidence をモック化し、呼び出し順と引数を捕捉する。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.budget import BudgetTracker
from src.main import _generate_outputs
from src.shared.models import (
    AnalysisResult,
    JobRecord,
    MultiAngleAnalysis,
    NewsEvent,
    PerspectiveCandidate,
    ScoredEvent,
    ScriptSection,
    SourceRef,
    VideoPayload,
    VideoScript,
    WebArticle,
)
from src.storage.db import init_db


# ---------- Fixtures ----------

@pytest.fixture()
def tmp_dirs(tmp_path: Path):
    output = tmp_path / "output"
    output.mkdir(parents=True, exist_ok=True)
    db = tmp_path / "db" / "test.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    init_db(db)
    return output, db


def _scored_event(event_id: str = "evt-f12a-order", with_analysis: bool = False) -> ScoredEvent:
    ev = NewsEvent(
        id=event_id,
        title="移動する主権領土の出現",
        summary="海洋プラットフォームが新しい主権主張を伴って移動している。",
        category="geopolitics",
        source="FT",
        published_at=datetime.now(timezone.utc),
        sources_jp=[SourceRef(name="Nikkei", url="https://jp.example.com/n1", region="japan")],
        sources_en=[SourceRef(name="FT", url="https://en.example.com/ft1", region="global")],
    )
    se = ScoredEvent(event=ev, score=10.0, channel_id="geo_lens")
    if with_analysis:
        se.analysis_result = AnalysisResult(
            event_id=event_id,
            channel_id="geo_lens",
            selected_perspective=PerspectiveCandidate(
                axis="hidden_stakes",
                score=8.0,
                reasoning="海洋構造物の主権主張は新領域。",
                evidence_refs=["art_0"],
            ),
            rejected_perspectives=[],
            perspective_verified=True,
            verification_notes="test",
            multi_angle=MultiAngleAnalysis(
                geopolitical="g", political_intent="p", economic_impact="e",
                cultural_context="c", media_divergence="m",
            ),
            insights=[],
            selected_duration_profile="geopolitics_120s",
            visual_mood_tags=["causal_chain"],
            analysis_version="v1.0",
            generated_at=datetime.now(timezone.utc).isoformat(),
            llm_calls_used=3,
        )
    return se


_ARTICLE_MD = (
    "# 移動する主権領土\n\n"
    "## TL;DR\n- 観測史上類のない移動する主権領土の出現\n\n"
    "## 事実：日本と世界の報道差\n"
    "FT は「移動する主権領土」と表現しており、日経の構造的整理とは語彙が異なる。\n"
)


def _stub_article(event_id: str) -> WebArticle:
    return WebArticle(
        event_id=event_id,
        title="移動する主権領土",
        markdown=_ARTICLE_MD,
        word_count=200,
    )


def _stub_script(event_id: str) -> VideoScript:
    return VideoScript(
        event_id=event_id,
        title="移動する主権領土",
        intro="",
        sections=[
            ScriptSection(heading="hook", body="海洋秩序が動いた瞬間です。", duration_sec=4),
            ScriptSection(heading="setup", body="プラットフォームが移動を開始した。" * 3, duration_sec=16),
            ScriptSection(heading="twist", body="従来の領土概念が揺らいでいる。" * 6, duration_sec=40),
            ScriptSection(heading="punchline", body="主権の輪郭を疑ってみてください。" * 3, duration_sec=20),
        ],
        outro="",
        total_duration_sec=80,
        target_duration_sec=80,
        estimated_duration_sec=80,
        platform_profile="shared",
    )


def _stub_video_payload(event_id: str) -> VideoPayload:
    return VideoPayload(
        event_id=event_id,
        title="移動する主権領土",
        scenes=[],
        total_duration_sec=80,
    )


def _make_budget(db_path: Path) -> BudgetTracker:
    """十分な予算を持つ BudgetTracker を生成する。"""
    return BudgetTracker(
        run_budget=100,
        day_budget=100,
        day_calls_so_far=0,
        db_path=db_path,
        mode="publish_mode",
        publish_reserve_calls=10,
    )


# ---------- 順序逆転テスト ----------

def test_generation_order_article_before_script(tmp_dirs, monkeypatch):
    """F-12-A: write_article が generate_script_with_analysis / write_script より先に呼ばれる。"""
    output, db = tmp_dirs
    se = _scored_event(with_analysis=True)
    call_order: list[str] = []

    def mock_write_article(event, triage_result=None, video_script=None, budget=None):
        call_order.append("article")
        return _stub_article(event.id)

    def mock_generate_script_with_analysis(
        scored_event, analysis_result, channel_config=None,
        *, budget=None, authority_pair=None, article_text=None,
    ):
        call_order.append("script")
        return _stub_script(scored_event.event.id)

    def mock_write_script(event, triage_result=None, budget=None, authority_pair=None, article_text=None):
        call_order.append("script")
        return _stub_script(event.id)

    def mock_write_video_payload(event, script, analysis_result=None):
        call_order.append("video_payload")
        return _stub_video_payload(event.id)

    def mock_write_evidence(event, top, script, article, output_dir):
        call_order.append("evidence")

    monkeypatch.setattr("src.main.write_article", mock_write_article)
    monkeypatch.setattr("src.main.generate_script_with_analysis", mock_generate_script_with_analysis)
    monkeypatch.setattr("src.main.write_script", mock_write_script)
    monkeypatch.setattr("src.main.write_video_payload", mock_write_video_payload)
    monkeypatch.setattr("src.main.write_evidence", mock_write_evidence)

    budget = _make_budget(db)
    record = _generate_outputs(
        events=[],
        output_dir=output,
        db_path=db,
        job_id="job-f12a-order-1",
        budget=budget,
        day_publishes=0,
        max_publishes=10,
        override_top=se,
        all_ranked=[se],
        write_triage_scores=False,
    )

    assert isinstance(record, JobRecord)
    assert record.status == "completed"
    # F-12-A: article が script より先
    assert call_order.index("article") < call_order.index("script"), (
        f"article が script より先に呼ばれていない: {call_order}"
    )
    # video_payload と evidence は script より後
    assert call_order.index("script") < call_order.index("video_payload")
    assert call_order.index("script") < call_order.index("evidence")


def test_script_writer_receives_article_text(tmp_dirs, monkeypatch):
    """F-12-A: 新ルート（generate_script_with_analysis）に article.markdown が article_text として渡る。"""
    output, db = tmp_dirs
    se = _scored_event(with_analysis=True)
    captured: dict = {}

    def mock_write_article(event, triage_result=None, video_script=None, budget=None):
        # F-12-A 不変原則 2: video_script は渡されないこと
        captured["article_video_script_arg"] = video_script
        return _stub_article(event.id)

    def mock_generate_script_with_analysis(
        scored_event, analysis_result, channel_config=None,
        *, budget=None, authority_pair=None, article_text=None,
    ):
        captured["script_article_text"] = article_text
        return _stub_script(scored_event.event.id)

    def mock_write_video_payload(event, script, analysis_result=None):
        return _stub_video_payload(event.id)

    def mock_write_evidence(event, top, script, article, output_dir):
        return None

    monkeypatch.setattr("src.main.write_article", mock_write_article)
    monkeypatch.setattr("src.main.generate_script_with_analysis", mock_generate_script_with_analysis)
    monkeypatch.setattr("src.main.write_video_payload", mock_write_video_payload)
    monkeypatch.setattr("src.main.write_evidence", mock_write_evidence)

    budget = _make_budget(db)
    record = _generate_outputs(
        events=[],
        output_dir=output,
        db_path=db,
        job_id="job-f12a-order-2",
        budget=budget,
        day_publishes=0,
        max_publishes=10,
        override_top=se,
        all_ranked=[se],
        write_triage_scores=False,
    )

    assert record.status == "completed"
    # script_writer は article.markdown を受け取る
    assert captured["script_article_text"] == _ARTICLE_MD
    # F-12-A 不変原則 2: write_article は video_script を受け取らない
    assert captured["article_video_script_arg"] is None


def test_script_writer_receives_article_text_legacy_route(tmp_dirs, monkeypatch):
    """F-12-A: 旧ルート（write_script: analysis_result=None）にも article.markdown が article_text として渡る。"""
    output, db = tmp_dirs
    se = _scored_event(with_analysis=False)  # analysis_result=None → write_script ルート
    # ANALYSIS_LAYER_ENABLED=false（既定）の場合のみ write_script に到達する
    monkeypatch.delenv("ANALYSIS_LAYER_ENABLED", raising=False)

    captured: dict = {}

    def mock_write_article(event, triage_result=None, video_script=None, budget=None):
        return _stub_article(event.id)

    def mock_write_script(event, triage_result=None, budget=None, authority_pair=None, article_text=None):
        captured["script_article_text"] = article_text
        return _stub_script(event.id)

    def mock_write_video_payload(event, script, analysis_result=None):
        return _stub_video_payload(event.id)

    def mock_write_evidence(event, top, script, article, output_dir):
        return None

    monkeypatch.setattr("src.main.write_article", mock_write_article)
    monkeypatch.setattr("src.main.write_script", mock_write_script)
    monkeypatch.setattr("src.main.write_video_payload", mock_write_video_payload)
    monkeypatch.setattr("src.main.write_evidence", mock_write_evidence)

    budget = _make_budget(db)
    record = _generate_outputs(
        events=[],
        output_dir=output,
        db_path=db,
        job_id="job-f12a-order-3",
        budget=budget,
        day_publishes=0,
        max_publishes=10,
        override_top=se,
        all_ranked=[se],
        write_triage_scores=False,
    )

    assert record.status == "completed"
    assert captured["script_article_text"] == _ARTICLE_MD
