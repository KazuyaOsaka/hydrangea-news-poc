"""F-13: quality_floor_miss ガード再設計 (Hydrangea コンセプト準拠) テスト。

旧ガード:
    cautions.startswith("[抑制]") + appraisal_type=None + editorial_appraisal_score=0.0
    → ValueError 一律発動

新ガード:
    上記条件に加え、以下のいずれも満たさない場合のみブロック:
    - editorial_mission_score >= 45.0
    - judge_class in {"blind_spot_global", "linked_jp_global"}
    - analysis_result is not None

LLM 呼び出しはスタブで置換し、実 API は使わない。
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

import pytest

from src.generation.script_writer import write_script
from src.llm.base import LLMClient
from src.shared.models import (
    AnalysisResult,
    GeminiJudgeResult,
    Insight,
    MultiAngleAnalysis,
    NewsEvent,
    PerspectiveCandidate,
    ScoredEvent,
    SourceRef,
)


# ---------- スタブ LLM ----------

class _StubLLMClient(LLMClient):
    """quality_floor_miss ガードを通過した場合に呼ばれる LLM のスタブ。"""

    def __init__(self, response: str = "{}"):
        self._response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._response


def _legacy_response() -> str:
    """legacy ScriptDraft スキーマに準拠したダミー応答。"""
    return json.dumps(
        {
            "director_thought": (
                "Media Critique で日本の沈黙を突き、海外発の構造的事実を提示する。"
                "視聴者に1つの違和感を残し、次の判断材料を渡す。"
            ),
            "target_enemy": "大手メディア",
            "selected_pattern": "Media Critique",
            "loop_mechanism": "loop-3",
            "seo_keywords": {"primary": "海外ニュース", "secondary": ["地政学"]},
            "thumbnail_text": {"main": "海外発", "sub": "未報道"},
            "hook_variants": [
                {"type": "B", "label": "固有名詞否定", "text": "NHKが言わない海外の真実"},
                {"type": "A", "label": "数字ショック", "text": "8割。日本は知らない"},
                {"type": "D", "label": "逆説宣言", "text": "実は世界の見え方は違う"},
            ],
            "setup": (
                "海外メディアが取り上げた事実が日本では未報道です。"
                "国際合意のないまま事態は進行しています。"
                "ここで事実関係を整理します。"
            ),
            "twist": (
                "ここで重要なのは構造の変化です。"
                "海外発のニュースは日本のメディアでは沈黙しています。"
                "なぜ報道は触れないのか。空気が支配する構造があります。"
                "つまり情報鎖国の中で世界の秩序は静かに書き換わっています。"
                "気づいた時には選択肢が消えている可能性があります。"
            ),
            "punchline": (
                "情報鎖国ニッポンで、海外発の地殻変動を見落としています。"
                "次にニュースを見たら、その揺らぎを思い出してください。"
            ),
            "peaks": {
                "3s": "ここで重要なのは",
                "7s": "海外発8割",
                "15s": "日本の沈黙",
                "30s": "情報鎖国",
            },
        },
        ensure_ascii=False,
    )


# ---------- フィクスチャ ----------

def _suppressed_event(event_id: str = "f13-evt") -> NewsEvent:
    return NewsEvent(
        id=event_id,
        title="Venezuela sanctions and the geopolitical chess",
        summary="A foreign-only signal that Hydrangea is built to surface.",
        category="geopolitics",
        source="FT",
        published_at=datetime.now(timezone.utc),
        sources_jp=[],
        sources_en=[SourceRef(name="FT", url="https://en.example.com/ft1", region="global")],
    )


def _suppressed_scored(
    *,
    event_id: str = "f13-evt",
    editorial_mission_score: float | None = None,
    publishability_class: str | None = None,
    analysis_result: AnalysisResult | None = None,
) -> ScoredEvent:
    """[抑制] safety gate 付き候補。Hydrangea-legitimate 条件はパラメータで切替。"""
    ev = _suppressed_event(event_id)
    judge_result = (
        GeminiJudgeResult(
            judged_event_id=event_id,
            publishability_class=publishability_class,
        )
        if publishability_class is not None
        else None
    )
    return ScoredEvent(
        event=ev,
        score=10.0,
        channel_id="geo_lens",
        appraisal_cautions="[抑制] safety gate: en_only + low_jr=0",
        appraisal_type=None,
        editorial_appraisal_score=0.0,
        editorial_mission_score=editorial_mission_score,
        judge_result=judge_result,
        analysis_result=analysis_result,
    )


def _make_analysis_result(event_id: str = "f13-evt") -> AnalysisResult:
    return AnalysisResult(
        event_id=event_id,
        channel_id="geo_lens",
        selected_perspective=PerspectiveCandidate(
            axis="hidden_stakes",
            score=8.0,
            reasoning="海外発の構造的事実。",
            evidence_refs=["art_0"],
        ),
        rejected_perspectives=[],
        perspective_verified=True,
        verification_notes="test",
        multi_angle=MultiAngleAnalysis(
            geopolitical="g", political_intent="p", economic_impact="e",
            cultural_context="c", media_divergence="m",
        ),
        insights=[Insight(text="海外発の重要性", importance=0.9, evidence_refs=["art_0"])],
        selected_duration_profile="geopolitics_120s",
        visual_mood_tags=["causal_chain"],
        analysis_version="v1.0",
        generated_at=datetime.now(timezone.utc).isoformat(),
        llm_calls_used=3,
    )


# ---------- Hydrangea-legitimate 通過テスト ----------

def test_hydrangea_legitimate_with_high_editorial_mission_score(monkeypatch, caplog):
    """editorial_mission_score >= 45.0 なら [抑制] でも通過する。"""
    se = _suppressed_scored(editorial_mission_score=72.5)
    stub = _StubLLMClient(_legacy_response())
    monkeypatch.setattr(
        "src.generation.script_writer.get_script_llm_client", lambda: stub
    )

    with caplog.at_level("WARNING"):
        script = write_script(se.event, triage_result=se)

    assert script is not None
    assert len(stub.prompts) >= 1, "LLM must be called when guard is bypassed"
    assert any(
        "[F-13] quality_floor_miss bypass" in r.message
        and "editorial_mission_score=72.5" in r.message
        for r in caplog.records
    ), "F-13 bypass WARNING log expected"


def test_hydrangea_legitimate_with_blind_spot_global(monkeypatch, caplog):
    """judge_class=blind_spot_global なら [抑制] でも通過する。"""
    se = _suppressed_scored(publishability_class="blind_spot_global")
    stub = _StubLLMClient(_legacy_response())
    monkeypatch.setattr(
        "src.generation.script_writer.get_script_llm_client", lambda: stub
    )

    with caplog.at_level("WARNING"):
        script = write_script(se.event, triage_result=se)

    assert script is not None
    assert len(stub.prompts) >= 1
    assert any(
        "[F-13] quality_floor_miss bypass" in r.message
        and "judge_class=blind_spot_global" in r.message
        for r in caplog.records
    )


def test_hydrangea_legitimate_with_linked_jp_global(monkeypatch, caplog):
    """judge_class=linked_jp_global なら [抑制] でも通過する。"""
    se = _suppressed_scored(publishability_class="linked_jp_global")
    stub = _StubLLMClient(_legacy_response())
    monkeypatch.setattr(
        "src.generation.script_writer.get_script_llm_client", lambda: stub
    )

    with caplog.at_level("WARNING"):
        script = write_script(se.event, triage_result=se)

    assert script is not None
    assert len(stub.prompts) >= 1
    assert any(
        "[F-13] quality_floor_miss bypass" in r.message
        and "judge_class=linked_jp_global" in r.message
        for r in caplog.records
    )


def test_hydrangea_legitimate_with_analysis_result(monkeypatch, caplog):
    """analysis_result is not None なら [抑制] でも通過する。"""
    ar = _make_analysis_result()
    se = _suppressed_scored(analysis_result=ar)
    stub = _StubLLMClient(_legacy_response())
    monkeypatch.setattr(
        "src.generation.script_writer.get_script_llm_client", lambda: stub
    )

    with caplog.at_level("WARNING"):
        script = write_script(se.event, triage_result=se)

    assert script is not None
    assert len(stub.prompts) >= 1
    assert any(
        "[F-13] quality_floor_miss bypass" in r.message
        and "analysis_result=present" in r.message
        for r in caplog.records
    )


# ---------- 真のノイズはブロック ----------

def test_pure_noise_blocked():
    """全ての Hydrangea-legitimate 条件を満たさない真のノイズは引き続きブロックされる。

    - editorial_mission_score=20.0 (< 45.0)
    - publishability_class="insufficient_evidence" (Hydrangea 通過 class でない)
    - analysis_result=None
    - cautions=[抑制] / appraisal_type=None / editorial_appraisal_score=0.0
    """
    se = _suppressed_scored(
        editorial_mission_score=20.0,
        publishability_class="insufficient_evidence",
        analysis_result=None,
    )

    with pytest.raises(ValueError, match="quality_floor_miss"):
        write_script(se.event, triage_result=se)


def test_pure_noise_with_no_upstream_signals_blocked():
    """上流値が全て None の場合 (旧来挙動) もブロックされる。"""
    se = _suppressed_scored(
        editorial_mission_score=None,
        publishability_class=None,
        analysis_result=None,
    )

    with pytest.raises(ValueError, match="quality_floor_miss"):
        write_script(se.event, triage_result=se)


# ---------- safety gate 未発動なら何もしない (既存挙動維持) ----------

def test_no_safety_gate_no_block(monkeypatch):
    """cautions に [抑制] が含まれない場合は通過 (旧来挙動)。"""
    ev = _suppressed_event("f13-evt-pass")
    se = ScoredEvent(
        event=ev,
        score=10.0,
        channel_id="geo_lens",
        appraisal_cautions="gap_reasoning なし: 仮説段階",
        appraisal_type="Blind Spot Global",
        editorial_appraisal_score=2.5,
    )
    stub = _StubLLMClient(_legacy_response())
    monkeypatch.setattr(
        "src.generation.script_writer.get_script_llm_client", lambda: stub
    )

    script = write_script(se.event, triage_result=se)
    assert script is not None
    assert len(stub.prompts) >= 1


# ---------- 不変原則 1: article_writer.py のソース変更ゼロ ----------

def test_article_writer_untouched():
    """F-13 不変原則 1: article_writer.py の git diff は空。"""
    result = subprocess.run(
        ["git", "diff", "src/generation/article_writer.py"],
        capture_output=True, text=True, cwd="/Users/kazuy/Desktop/hydrangea-news-poc",
    )
    assert result.returncode == 0
    assert result.stdout == "", (
        f"article_writer.py was modified! diff:\n{result.stdout}"
    )


# ---------- リグレッション: Slot-2 Iraq パターン ----------

def test_regression_slot2_iraq_pattern(monkeypatch, caplog):
    """試運転 7-F の Slot-2 Iraq パターン (既に通過していた候補) は引き続き通過。

    appraisal が抑制されていなくても、judge_class=blind_spot_global +
    高い mission score を持つ典型的な Hydrangea 本領記事の通過を保証する。
    """
    ev = _suppressed_event("f13-iraq")
    se = ScoredEvent(
        event=ev,
        score=85.0,
        channel_id="geo_lens",
        appraisal_cautions="",  # safety gate 未発動
        appraisal_type="Blind Spot Global",
        editorial_appraisal_score=4.2,
        editorial_mission_score=70.0,
        judge_result=GeminiJudgeResult(
            judged_event_id="f13-iraq",
            publishability_class="blind_spot_global",
        ),
    )
    stub = _StubLLMClient(_legacy_response())
    monkeypatch.setattr(
        "src.generation.script_writer.get_script_llm_client", lambda: stub
    )

    script = write_script(se.event, triage_result=se)
    assert script is not None
    # safety gate 未発動なので F-13 bypass ログは出ないはず
    bypass_logs = [r for r in caplog.records if "[F-13] quality_floor_miss bypass" in r.message]
    assert bypass_logs == [], (
        "safety gate が発動していないので F-13 bypass ログは出ないはず"
    )
