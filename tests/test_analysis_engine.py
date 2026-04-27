"""src/analysis/analysis_engine.py のテスト（LLM はモック）。

orchestrator が Step 1〜7 を順に呼び出し、いずれかの失敗で None を返すことと、
save_analysis_json が {event_id}_analysis.json を書き出すことを検証する。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.analysis.analysis_engine import run_analysis_layer, save_analysis_json
from src.llm.base import LLMClient
from src.shared.models import (
    AnalysisResult,
    ChannelConfig,
    MultiAngleAnalysis,
    NewsEvent,
    PerspectiveCandidate,
    ScoredEvent,
    SourceRef,
)


_FIXTURES = Path(__file__).parent / "fixtures" / "llm_responses"


def _load_fixture(name: str) -> str:
    return (_FIXTURES / f"{name}.json").read_text(encoding="utf-8")


class _ScriptedClient(LLMClient):
    """Step 3/4/5 で順に違う応答を返すスタブ（呼び出し回数を記録）。"""

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.call_count = 0
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.call_count >= len(self.responses):
            raise AssertionError(
                f"Unexpected extra LLM call (#{self.call_count + 1}); "
                f"only {len(self.responses)} responses scripted."
            )
        out = self.responses[self.call_count]
        self.call_count += 1
        return out


class _AlwaysFailClient(LLMClient):
    def __init__(self) -> None:
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        raise RuntimeError("simulated quota error")


# ── ファクトリ ─────────────────────────────────────────────────────────────

def _channel_config_geo_lens() -> ChannelConfig:
    """tests に通用する最小の ChannelConfig（Phase 1 設定相当）。"""
    return ChannelConfig(
        channel_id="geo_lens",
        display_name="Geopolitical Lens",
        enabled=True,
        source_regions=["global", "middle_east", "japan"],
        perspective_axes=[
            "silence_gap",
            "framing_inversion",
            "hidden_stakes",
            "cultural_blindspot",
        ],
        duration_profiles=[
            "breaking_shock_60s",
            "media_critique_80s",
            "anti_sontaku_90s",
            "paradigm_shift_100s",
            "cultural_divide_100s",
            "geopolitics_120s",
        ],
        prompt_variant="geo_lens_v1",
        posts_per_day=3,
    )


def _silence_gap_event() -> ScoredEvent:
    """silence_gap 成立条件を満たすイベント (sources_jp=0, en=3, global_attention>=6, japan_impact>=4)。"""
    ev = NewsEvent(
        id="evt-engine-1",
        title="Severe humanitarian crisis under-reported in Japan",
        summary="Three foreign outlets covered scale; Japanese media is silent.",
        category="geopolitics",
        source="Reuters",
        published_at=datetime.now(timezone.utc),
        sources_jp=[],
        sources_en=[
            SourceRef(name="Reuters", url="https://en.example.com/0", region="global"),
            SourceRef(name="BBC", url="https://en.example.com/1", region="global"),
            SourceRef(name="AlJazeera", url="https://en.example.com/2", region="middle_east"),
        ],
    )
    return ScoredEvent(
        event=ev,
        score=10.0,
        score_breakdown={
            "global_attention_score": 7.0,
            "indirect_japan_impact_score": 5.0,
            "perspective_gap_score": 3.0,
        },
    )


def _no_perspective_event() -> ScoredEvent:
    """4 軸どの成立条件も満たさないイベント（全スコア 0、ソースもほぼなし）。"""
    ev = NewsEvent(
        id="evt-engine-empty",
        title="Routine local news",
        summary="Mundane domestic article.",
        category="local",
        source="Local",
        published_at=datetime.now(timezone.utc),
        sources_jp=[
            SourceRef(name="Local", url="https://jp.example.com/local", region="japan"),
        ],
        sources_en=[],
    )
    return ScoredEvent(event=ev, score=1.0, score_breakdown={})


# ── happy path ─────────────────────────────────────────────────────────────

def test_run_returns_analysis_result_with_all_three_llm_calls(tmp_path: Path):
    se = _silence_gap_event()
    cc = _channel_config_geo_lens()
    client = _ScriptedClient(
        [
            _load_fixture("perspective_select_and_verify_silence_gap"),
            _load_fixture("multi_angle_analysis_geopolitics"),
            _load_fixture("insights_extract_3items"),
        ]
    )

    result = run_analysis_layer(se, cc, tmp_path / "no.db", llm_client=client)

    assert result is not None
    assert isinstance(result, AnalysisResult)
    assert result.event_id == se.event.id
    assert result.channel_id == "geo_lens"
    assert result.selected_perspective.axis == "silence_gap"
    assert result.perspective_verified is True
    assert result.llm_calls_used == 3
    assert client.call_count == 3
    # 多角的分析の 5 観点すべてが埋まっている
    assert result.multi_angle.geopolitical
    assert result.multi_angle.economic_impact
    # 洞察が 3 個（fixture）
    assert len(result.insights) == 3
    # ビジュアルムードタグは silence_gap のマッピング由来
    assert "void_imagery" in result.visual_mood_tags
    # duration_profile は ChannelConfig.duration_profiles のいずれか
    assert result.selected_duration_profile in cc.duration_profiles
    # rejected_perspectives は selected を含まない
    assert all(c.axis != "silence_gap" for c in result.rejected_perspectives)
    # 生成日時は ISO 8601 形式（fromisoformat で読めること）
    datetime.fromisoformat(result.generated_at)


def test_run_returns_none_when_no_perspective_candidates(tmp_path: Path):
    se = _no_perspective_event()
    cc = _channel_config_geo_lens()
    # LLM は呼ばれないはず
    client = _ScriptedClient([])
    result = run_analysis_layer(se, cc, tmp_path / "no.db", llm_client=client)

    assert result is None
    assert client.call_count == 0


def test_run_returns_none_when_select_perspective_fails(tmp_path: Path):
    """Step 3 が None を返すと Step 4/5 は呼ばれず、全体も None。"""
    se = _silence_gap_event()
    cc = _channel_config_geo_lens()
    # invalid な axis を返すレスポンス → select_perspective が None を返す
    bad_select = json.dumps({
        "selected_axis": "nonexistent_axis",
        "verification": {"actually_holds": True, "notes": "", "confidence": 0.5},
        "fallback_axis_if_failed": None,
    })
    client = _ScriptedClient([bad_select])

    result = run_analysis_layer(se, cc, tmp_path / "no.db", llm_client=client)
    assert result is None
    # Step 3 の 1 回しか呼ばれない（Step 4/5 はスキップ）
    assert client.call_count == 1


def test_run_returns_none_when_step4_raises(tmp_path: Path):
    """Step 4 (perform_multi_angle_analysis) の例外で全体が None になる。"""
    se = _silence_gap_event()
    cc = _channel_config_geo_lens()
    client = _ScriptedClient(
        [
            _load_fixture("perspective_select_and_verify_silence_gap"),
            "not even a brace here",  # Step 4 で json.JSONDecodeError
        ]
    )
    result = run_analysis_layer(se, cc, tmp_path / "no.db", llm_client=client)
    assert result is None
    assert client.call_count == 2


def test_run_returns_none_when_step5_raises(tmp_path: Path):
    """Step 5 (extract_insights) の例外で全体が None になる。"""
    se = _silence_gap_event()
    cc = _channel_config_geo_lens()
    client = _ScriptedClient(
        [
            _load_fixture("perspective_select_and_verify_silence_gap"),
            _load_fixture("multi_angle_analysis_minimal"),
            json.dumps({"foo": "bar"}),  # Step 5 で ValueError (insights キー欠落)
        ]
    )
    result = run_analysis_layer(se, cc, tmp_path / "no.db", llm_client=client)
    assert result is None
    assert client.call_count == 3


def test_run_handles_failing_llm_at_step3(tmp_path: Path):
    """Step 3 で LLM が失敗するケース (F-3 改修後)。

    F-3 の Step2 フォールバックにより select_perspective は LLM 失敗時も
    candidates が残っていれば最高スコア候補を返す（None ではない）。
    そのため Step 3 を通過し、Step 4 (multi_angle) で再度 LLM を呼ぼうとして失敗、
    そこで例外が伝搬し run_analysis_layer の外側 except が None を返す。

    結果: result=None は維持されるが、call_count は 2 (Step3 + Step4) に増える。
    旧挙動 (F-2 まで): Step3 で 1 回呼ばれて失敗、即 None。
    """
    se = _silence_gap_event()
    cc = _channel_config_geo_lens()
    client = _AlwaysFailClient()

    result = run_analysis_layer(se, cc, tmp_path / "no.db", llm_client=client)
    assert result is None
    # F-3: Step3 で fallback 採用後 Step4 でも LLM 失敗 → call_count==2
    assert client.call_count == 2


# ── duration_profile 選定の引継ぎ事項検証 ─────────────────────────────────

def test_run_passes_scored_event_to_duration_selector(tmp_path: Path, monkeypatch):
    """select_duration_profile に scored_event がキーワード引数で渡されること。

    Batch 3 引継ぎ事項: select_duration_profile(... , scored_event=slot_1_event)。
    """
    captured: dict = {}

    from src.analysis import analysis_engine as ae

    real_select = ae.select_duration_profile

    def _spy(perspective, insights, multi_angle, channel_config, *, scored_event=None):
        captured["scored_event_id"] = scored_event.event.id if scored_event else None
        return real_select(
            perspective,
            insights,
            multi_angle,
            channel_config,
            scored_event=scored_event,
        )

    monkeypatch.setattr(ae, "select_duration_profile", _spy)

    se = _silence_gap_event()
    cc = _channel_config_geo_lens()
    client = _ScriptedClient(
        [
            _load_fixture("perspective_select_and_verify_silence_gap"),
            _load_fixture("multi_angle_analysis_geopolitics"),
            _load_fixture("insights_extract_3items"),
        ]
    )
    result = run_analysis_layer(se, cc, tmp_path / "no.db", llm_client=client)
    assert result is not None
    assert captured["scored_event_id"] == se.event.id


# ── save_analysis_json ──────────────────────────────────────────────────────

def _build_minimal_analysis_result(event_id: str = "evt-save-1") -> AnalysisResult:
    return AnalysisResult(
        event_id=event_id,
        channel_id="geo_lens",
        selected_perspective=PerspectiveCandidate(
            axis="silence_gap", score=8.0, reasoning="r", evidence_refs=["u1"]
        ),
        rejected_perspectives=[],
        perspective_verified=True,
        verification_notes="notes",
        multi_angle=MultiAngleAnalysis(
            geopolitical="g", political_intent="p", economic_impact="e",
            cultural_context="c", media_divergence="m",
        ),
        insights=[],
        selected_duration_profile="anti_sontaku_90s",
        visual_mood_tags=["void_imagery"],
        analysis_version="v1.0",
        generated_at=datetime.now(timezone.utc).isoformat(),
        llm_calls_used=3,
    )


def test_save_analysis_json_writes_event_id_named_file(tmp_path: Path):
    out_dir = tmp_path / "output"
    ar = _build_minimal_analysis_result(event_id="evt-X")
    written = save_analysis_json(ar, out_dir)

    assert written == out_dir / "evt-X_analysis.json"
    assert written.exists()
    parsed = json.loads(written.read_text(encoding="utf-8"))
    assert parsed["event_id"] == "evt-X"
    assert parsed["channel_id"] == "geo_lens"
    assert parsed["selected_perspective"]["axis"] == "silence_gap"


def test_save_analysis_json_creates_output_dir_if_missing(tmp_path: Path):
    out_dir = tmp_path / "does" / "not" / "exist"
    ar = _build_minimal_analysis_result()
    written = save_analysis_json(ar, out_dir)
    assert written.exists()
    assert out_dir.is_dir()


def test_save_analysis_json_overwrites_existing(tmp_path: Path):
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    ar1 = _build_minimal_analysis_result(event_id="evt-O")
    save_analysis_json(ar1, out_dir)

    ar2 = _build_minimal_analysis_result(event_id="evt-O")
    ar2.verification_notes = "updated"
    save_analysis_json(ar2, out_dir)

    parsed = json.loads((out_dir / "evt-O_analysis.json").read_text(encoding="utf-8"))
    assert parsed["verification_notes"] == "updated"


# ── perspective_axes filter (channel_config 連携) ──────────────────────────

def test_run_returns_none_when_channel_disallows_all_perspectives(tmp_path: Path):
    """ChannelConfig.perspective_axes が空なら 4 軸全部除外され None を返す。"""
    se = _silence_gap_event()
    cc = ChannelConfig(
        channel_id="geo_lens",
        display_name="GL",
        enabled=True,
        perspective_axes=[],  # 全軸除外
        duration_profiles=["anti_sontaku_90s"],
        prompt_variant="geo_lens_v1",
        posts_per_day=1,
    )
    result = run_analysis_layer(se, cc, tmp_path / "no.db", llm_client=_ScriptedClient([]))
    assert result is None
