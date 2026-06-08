"""F-title-guard-coverage-claim-policy (1-Q.5): coverage claim 事実整合 guard 検証。

src/generation/coverage_claim_guard.py を LLM mock で決定的に検証する:
  - 真値 stream_classification の解決
  - silence_gap / out_of_scope の短絡 (LLM 非呼出 + flag なし)
  - perspective_gap / framing_inversion での contradiction flag
  - ★ B-3' 原則 (uncertain / 沈黙を矛盾と読み替えない)
  - LLM 逸脱カテゴリの安全網 (系統に無い forbidden_category は不採用)
  - flag のみ (自動置換・再生成はしない) = 結果は検出記録のみ

正典: docs/PARTICULAR_ANGLE_DEFINITION.md セクション 3.7 + configs/coverage_claim_policy.yaml。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.generation.coverage_claim_guard import (
    CoverageClaimGuardResult,
    resolve_stream_classification,
    run_coverage_claim_guard,
)
from src.shared.models import (
    AnalysisResult,
    MultiAngleAnalysis,
    NewsEvent,
    ParticularAngleMetadata,
    PerspectiveCandidate,
    ScoredEvent,
    ScriptSection,
    SontakuSignals,
    SourceRef,
    TitleLayer,
    VideoScript,
)


# ---------- スタブ LLM ----------

class _StubClient:
    """固定応答を返す LLM mock (LLMClient duck-typing)。"""

    def __init__(self, response):
        self._response = response
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class _ExplodingClient:
    """呼ばれたら失敗する mock (短絡経路で LLM が呼ばれないことの検証用)。"""

    def __init__(self):
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        raise AssertionError("LLM must not be called on short-circuit path")


# ---------- フィクスチャ ----------

def _scored_event(stream: str | None = "stream_2_perspective_gap") -> ScoredEvent:
    ev = NewsEvent(
        id="evt-guard-1",
        title="Israel seizes strategic castle in Lebanon",
        summary="A 900-year-old castle seized; diplomatic fallout.",
        category="geopolitics",
        source="MEE",
        published_at=datetime.now(timezone.utc),
        sources_jp=[SourceRef(name="Nikkei", url="https://jp.example/n", region="japan")],
        sources_en=[SourceRef(name="MEE", url="https://en.example/m", region="global")],
    )
    se = ScoredEvent(event=ev, score=10.0, channel_id="geo_lens")
    if stream is None:
        return se  # analysis_result=None → 真値不明
    pam = ParticularAngleMetadata(
        stream_classification=stream,
        core_question="占領の構造的意味",
        differentiation_from_mainstream="日本は事件本体を報道、角度は未報道",
        hydrangea_axis_alignment="第 2 軸",
        sontaku_signals=SontakuSignals(level="high", type="diplomatic", reasoning="米イスラエル忖度"),
    )
    ar = AnalysisResult(
        event_id="evt-guard-1",
        channel_id="geo_lens",
        selected_perspective=PerspectiveCandidate(
            axis="hidden_stakes", score=8.0, reasoning="r", evidence_refs=["a0"]
        ),
        perspective_verified=True,
        multi_angle=MultiAngleAnalysis(
            geopolitical="g", political_intent="p", economic_impact="e",
            cultural_context="c", media_divergence="m",
        ),
        selected_duration_profile="geopolitics_120s",
        generated_at=datetime.now(timezone.utc).isoformat(),
        particular_angle_metadata=pam,
    )
    return se.model_copy(update={"analysis_result": ar})


def _video_script(platform_title: str = "日本では報道されないIsraelの視点") -> VideoScript:
    return VideoScript(
        event_id="evt-guard-1",
        title="Israel の城塞占領",
        intro="intro",
        sections=[ScriptSection(heading="h", body="b", duration_sec=75)],
        outro="outro",
        total_duration_sec=75,
        title_layer=TitleLayer(
            canonical_title="Israel seizes strategic castle in Lebanon",
            platform_title=platform_title,
            hook_line="海外の見方、日本とは違う。",
            thumbnail_text="日本 vs 海外",
        ),
    )


def _verdict(status, claims=None):
    return {"status": status, "flagged_claims": claims or []}


def _response(title_verdict, article_verdict):
    return json.dumps({"title_verdict": title_verdict, "article_verdict": article_verdict})


# ---------- resolve_stream_classification ----------

def test_resolve_stream_from_metadata():
    se = _scored_event("stream_2_perspective_gap")
    assert resolve_stream_classification(se) == "stream_2_perspective_gap"


def test_resolve_stream_none_analysis_is_out_of_scope():
    se = _scored_event(stream=None)
    assert resolve_stream_classification(se) == "out_of_scope"


# ---------- 短絡経路 (LLM 非呼出 + flag なし) ----------

def test_silence_gap_short_circuits_without_llm():
    """silence_gap = 未報道断定が事実整合 → LLM を呼ばず skip。"""
    client = _ExplodingClient()
    result = run_coverage_claim_guard(
        _scored_event("stream_1_silence_gap"),
        _video_script("日本では報道されなかった事件"),
        "日本では一切報じられなかった。",
        client=client,
    )
    assert result.skipped is True
    assert result.flagged is False
    assert client.calls == 0


def test_out_of_scope_short_circuits_without_llm():
    client = _ExplodingClient()
    result = run_coverage_claim_guard(
        _scored_event(stream=None),
        _video_script(),
        "本文",
        client=client,
    )
    assert result.skipped is True
    assert result.flagged is False
    assert client.calls == 0


# ---------- perspective_gap / framing_inversion での判定 ----------

def test_perspective_gap_title_contradiction_flagged():
    """事件本体は報道済なのに title が event_total_silence を主張 → flag。"""
    client = _StubClient(_response(
        _verdict("contradiction", [{
            "span": "日本では報道されないIsraelの視点",
            "forbidden_category": "event_total_silence",
            "reasoning": "事件本体は日本でも報道済みのため未報道断定は事実に反する",
        }]),
        _verdict("consistent"),
    ))
    result = run_coverage_claim_guard(
        _scored_event("stream_2_perspective_gap"),
        _video_script(),
        "イスラエルが城塞を占領した。日本でも報じられたが、占領の構造的意味には触れられていない。",
        client=client,
    )
    assert result.flagged is True
    assert len(result.flags) == 1
    assert result.flags[0].artifact == "title"
    assert result.flags[0].forbidden_category == "event_total_silence"
    assert result.title_status == "contradiction"
    assert result.article_status == "consistent"


def test_perspective_gap_consistent_not_flagged():
    client = _StubClient(_response(_verdict("consistent"), _verdict("consistent")))
    result = run_coverage_claim_guard(
        _scored_event("stream_2_perspective_gap"),
        _video_script("日本でも報じられた城塞占領、その先の角度"),
        "事件は報じられたが、占領の構造には触れられていない。",
        client=client,
    )
    assert result.flagged is False
    assert result.flags == []
    assert result.skipped is False


def test_article_contradiction_flagged():
    client = _StubClient(_response(
        _verdict("consistent"),
        _verdict("contradiction", [{
            "span": "この事件は日本では完全に黙殺されている",
            "forbidden_category": "event_total_silence",
            "reasoning": "事件本体は報道済み",
        }]),
    ))
    result = run_coverage_claim_guard(
        _scored_event("stream_2_perspective_gap"),
        _video_script(),
        "この事件は日本では完全に黙殺されている。",
        client=client,
    )
    assert result.flagged is True
    assert result.flags[0].artifact == "article"
    assert result.article_status == "contradiction"


def test_framing_inversion_angle_silence_flagged():
    """framing_inversion = 角度も報道済 → angle_total_silence も flag 対象。"""
    client = _StubClient(_response(
        _verdict("contradiction", [{
            "span": "この角度は日本では一切報じられていない",
            "forbidden_category": "angle_total_silence",
            "reasoning": "framing_inversion では角度も報道済み",
        }]),
        _verdict("consistent"),
    ))
    result = run_coverage_claim_guard(
        _scored_event("stream_3_framing_inversion"),
        _video_script("この角度は日本では一切報じられていない"),
        "解釈差の記事本文。",
        client=client,
    )
    assert result.flagged is True
    assert result.flags[0].forbidden_category == "angle_total_silence"


# ---------- B-3' 原則 (沈黙を矛盾と読み替えない) ----------

def test_uncertain_is_not_flagged():
    """LLM が uncertain → flag しない (B-3')。"""
    client = _StubClient(_response(_verdict("uncertain"), _verdict("uncertain")))
    result = run_coverage_claim_guard(
        _scored_event("stream_2_perspective_gap"),
        _video_script(),
        "曖昧で報道状態に言及しない本文。",
        client=client,
    )
    assert result.flagged is False
    assert result.title_status == "uncertain"
    assert result.article_status == "uncertain"


def test_contradiction_with_out_of_policy_category_ignored():
    """perspective_gap で angle_total_silence (許容外) を返しても採用しない安全網。"""
    client = _StubClient(_response(
        _verdict("contradiction", [{
            "span": "角度が未報道",
            "forbidden_category": "angle_total_silence",  # perspective_gap の許容外
            "reasoning": "...",
        }]),
        _verdict("consistent"),
    ))
    result = run_coverage_claim_guard(
        _scored_event("stream_2_perspective_gap"),
        _video_script(),
        "本文",
        client=client,
    )
    # 許容外カテゴリは不採用 → flag なし → consistent に倒す。
    assert result.flagged is False
    assert result.title_status == "consistent"


def test_contradiction_declared_but_empty_claims_falls_consistent():
    client = _StubClient(_response(_verdict("contradiction", []), _verdict("consistent")))
    result = run_coverage_claim_guard(
        _scored_event("stream_2_perspective_gap"),
        _video_script(),
        "本文",
        client=client,
    )
    assert result.flagged is False
    assert result.title_status == "consistent"


# ---------- 失敗時の安全側挙動 (skip, flag しない) ----------

def test_llm_failure_returns_skipped_no_flag():
    client = _StubClient(RuntimeError("api down"))
    result = run_coverage_claim_guard(
        _scored_event("stream_2_perspective_gap"),
        _video_script(),
        "本文",
        client=client,
        max_retries=2,
    )
    assert result.skipped is True
    assert result.flagged is False
    assert client.calls == 2  # max_retries 回試行


def test_no_client_returns_skipped(monkeypatch):
    """client=None かつ get_analysis_llm_client が None → skip。"""
    monkeypatch.setattr(
        "src.generation.coverage_claim_guard.get_analysis_llm_client", lambda: None
    )
    result = run_coverage_claim_guard(
        _scored_event("stream_2_perspective_gap"),
        _video_script(),
        "本文",
    )
    assert result.skipped is True
    assert result.flagged is False


def test_result_is_serializable():
    """flag 結果が JSON 化可能 (レポート / ログ用)。"""
    client = _StubClient(_response(
        _verdict("contradiction", [{
            "span": "日本では報道されないIsraelの視点",
            "forbidden_category": "event_total_silence",
            "reasoning": "事件本体は報道済み",
        }]),
        _verdict("consistent"),
    ))
    result = run_coverage_claim_guard(
        _scored_event("stream_2_perspective_gap"),
        _video_script(),
        "本文",
        client=client,
    )
    dumped = json.loads(result.model_dump_json())
    assert dumped["flagged"] is True
    assert dumped["flags"][0]["span"] == "日本では報道されないIsraelの視点"
    assert isinstance(result, CoverageClaimGuardResult)
