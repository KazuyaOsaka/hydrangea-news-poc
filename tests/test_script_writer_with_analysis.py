"""src/generation/script_writer.py の新ルート (generate_script_with_analysis) テスト。

LLM はスタブで固定 JSON を返し、Pydantic スキーマ検証 / 文字数バリデーション /
情報密度型 4 パターン制限 / VideoScript 変換 / legacy フォールバック を検証する。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.generation.script_writer import (
    _ANALYSIS_DURATION_PROFILES,
    _AXIS_TO_PATTERN_HINT,
    _INFO_DENSITY_PATTERNS,
    ScriptWithAnalysisDraft,
    _format_insights_for_prompt,
    _resolve_duration_profile,
    generate_script_legacy,
    generate_script_with_analysis,
    write_script,
)
from src.llm.base import LLMClient
from src.shared.models import (
    AnalysisResult,
    ChannelConfig,
    Insight,
    MultiAngleAnalysis,
    NewsEvent,
    PerspectiveCandidate,
    ScoredEvent,
    SourceRef,
)


# ---------- スタブ LLM ----------

class _StubLLMClient(LLMClient):
    """固定文字列を返す LLM スタブ。複数応答に対応。"""

    def __init__(self, responses):
        if isinstance(responses, str):
            responses = [responses]
        self._responses = list(responses)
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if len(self._responses) == 1:
            return self._responses[0]
        return self._responses.pop(0)


# ---------- フィクスチャ ----------

def _scored_event(event_id: str = "evt-batch5-1") -> ScoredEvent:
    ev = NewsEvent(
        id=event_id,
        title="Strait of Hormuz tension reignites global oil concerns",
        summary="Iran signaled potential closure as new sanctions loom; tankers re-routing observed.",
        category="geopolitics",
        source="Reuters",
        published_at=datetime.now(timezone.utc),
        sources_jp=[
            SourceRef(name="Nikkei", url="https://jp.example.com/n0", region="japan"),
        ],
        sources_en=[
            SourceRef(name="Reuters", url="https://en.example.com/r0", region="global"),
            SourceRef(name="FT", url="https://en.example.com/ft0", region="global"),
        ],
    )
    return ScoredEvent(event=ev, score=10.0, channel_id="geo_lens")


def _analysis_result(
    event_id: str = "evt-batch5-1",
    *,
    axis: str = "hidden_stakes",
    duration_profile: str = "geopolitics_120s",
    insights_n: int = 3,
) -> AnalysisResult:
    insights = [
        Insight(
            text=f"Insight {i}: 日本の原油輸入の {80 - i}% がホルムズ経由という構造的依存。",
            importance=0.9 - 0.1 * i,
            evidence_refs=[f"art_{i}"],
        )
        for i in range(insights_n)
    ]
    return AnalysisResult(
        event_id=event_id,
        channel_id="geo_lens",
        selected_perspective=PerspectiveCandidate(
            axis=axis,
            score=8.5,
            reasoning="日本の原油輸入の 80% 超が同海峡経由で、間接的影響が極めて大きい。",
            evidence_refs=["art_0", "art_1"],
        ),
        rejected_perspectives=[],
        perspective_verified=True,
        verification_notes="test",
        multi_angle=MultiAngleAnalysis(
            geopolitical="米中対立の延長線上にイランの威嚇カードがある。",
            political_intent="イランは制裁緩和を引き出すため威嚇を周期的に使う。",
            economic_impact="日本の石油元売りは備蓄取り崩し圧力に直面する。",
            cultural_context="湾岸の駆け引きは儒教圏の合意形成と論理が異なる。",
            media_divergence="日本では航行影響、海外では地政学リスクが主軸で報じられる。",
        ),
        insights=insights,
        selected_duration_profile=duration_profile,
        visual_mood_tags=["causal_chain", "domino_effect"],
        analysis_version="v1.0",
        generated_at=datetime.now(timezone.utc).isoformat(),
        llm_calls_used=3,
    )


def _channel_config() -> ChannelConfig:
    return ChannelConfig.load("geo_lens")


def _good_llm_response(
    selected_pattern: str = "Geopolitics",
) -> str:
    """文字数バリデーションを通過する応答。"""
    return json.dumps(
        {
            "director_thought": (
                f"hidden_stakes 軸の insights を Twist 中核に配置し、{selected_pattern} で構造を解説する。"
                "数字と固有名詞で日本への因果連鎖を可視化する。"
            ),
            "selected_pattern": selected_pattern,
            "loop_mechanism": "loop-1",
            "seo_keywords": {
                "primary": "ホルムズ海峡",
                "secondary": ["原油価格", "地政学リスク"],
            },
            "thumbnail_text": {"main": "原油の生命線", "sub": "日本80%依存"},
            "hook_variants": [
                {"type": "A", "label": "数字ショック", "text": "8割。日本の原油は今ここで止まる"},
                {"type": "D", "label": "逆説宣言", "text": "ホルムズ封鎖は中国も困る"},
                {"type": "E", "label": "名指し暴露", "text": "イランが本当に狙うのは制裁解除です"},
            ],
            "setup": (
                "イランがホルムズ海峡の封鎖をちらつかせ始めました。"
                "現時点で実際の封鎖は確認されていません。"
                "ただ国際的なタンカーは航路の見直しを始めています。"
            ),
            "twist": (
                "ここで重要なのは日本の原油輸入の8割がこの海峡経由という事実です。"
                "イランは2019年にも同様の威嚇を行いましたが、実際の封鎖はしませんでした。"
                "なぜなら中国も逆方向から原油を輸入しており、封鎖した瞬間に中国の圧力で潰される。"
                "つまり封鎖カードは交渉用の脅しで、実行コストは極めて高い構造です。"
                "日本の石油元売り各社はすでに備蓄取り崩しの準備に入っています。"
            ),
            "punchline": (
                "つまり今動いているのは戦争ではなく、制裁解除を引き出すための高度な経済交渉です。"
                "次に「ホルムズ封鎖」という単語を聞いたら、その裏の構造を思い出してください。"
            ),
            "peaks": {
                "3s": "実は日本の原油の8割",
                "7s": "ホルムズ海峡 8割",
                "15s": "2019年も実行されなかった",
                "30s": "中国も困る構造",
            },
        },
        ensure_ascii=False,
    )


# ---------- 単体ユーティリティ ----------

def test_info_density_patterns_are_exactly_four_allowed_set():
    assert _INFO_DENSITY_PATTERNS == (
        "Breaking Shock",
        "Geopolitics",
        "Paradigm Shift",
        "Cultural Divide",
    )


def test_axis_to_pattern_hint_uses_only_info_density_patterns():
    for axis, hint in _AXIS_TO_PATTERN_HINT.items():
        assert hint in _INFO_DENSITY_PATTERNS, (
            f"axis {axis!r} maps to forbidden pattern {hint!r}"
        )


def test_resolve_duration_profile_known_id_returns_match():
    cc = _channel_config()
    pid, cfg = _resolve_duration_profile("geopolitics_120s", cc)
    assert pid == "geopolitics_120s"
    assert cfg["target_total_sec"] == 120


def test_resolve_duration_profile_unknown_falls_back_to_channel_head():
    cc = _channel_config()
    pid, cfg = _resolve_duration_profile("does_not_exist_999s", cc)
    # ChannelConfig.duration_profiles[0] が breaking_shock_60s（geo_lens の場合）
    assert pid in _ANALYSIS_DURATION_PROFILES


def test_resolve_duration_profile_no_channel_falls_back_to_default():
    pid, cfg = _resolve_duration_profile("does_not_exist_999s", None)
    assert pid == "anti_sontaku_90s"


def test_format_insights_for_prompt_is_descending_by_importance():
    insights = [
        Insight(text="low", importance=0.3, evidence_refs=["x"]),
        Insight(text="high", importance=0.9, evidence_refs=["y"]),
        Insight(text="mid", importance=0.6, evidence_refs=[]),
    ]
    block = _format_insights_for_prompt(insights)
    lines = block.splitlines()
    # 1 行目が importance 最大（high）
    assert "high" in lines[0]
    # 末尾が最小（low）
    assert "low" in lines[-1]


def test_format_insights_for_prompt_handles_empty():
    assert _format_insights_for_prompt([]) == "(no insights)"


# ---------- 後方互換エイリアス ----------

def test_generate_script_legacy_is_alias_for_write_script():
    """generate_script_legacy は write_script と同じ関数オブジェクトであること。"""
    assert generate_script_legacy is write_script


# ---------- 新ルート: 正常系 ----------

def test_generate_script_with_analysis_happy_path(monkeypatch):
    se = _scored_event()
    ar = _analysis_result()
    cc = _channel_config()

    stub = _StubLLMClient(_good_llm_response())
    monkeypatch.setattr(
        "src.generation.script_writer.get_script_llm_client", lambda: stub
    )
    # title_layer 生成は LLM 不要なテンプレ経路に流す（generate_title_layer は無視できる）
    script = generate_script_with_analysis(se, ar, cc)

    assert script.event_id == se.event.id
    assert len(script.sections) == 4
    headings = [s.heading for s in script.sections]
    assert headings == ["hook", "setup", "twist", "punchline"]
    # selected_pattern は情報密度型に限定
    assert script.selected_pattern in _INFO_DENSITY_PATTERNS
    # 仕様: target_enemy は新ルートでは付与しない
    assert script.target_enemy is None
    # title_layer は付く
    assert script.title_layer is not None
    # プロンプトに insights が展開されている
    assert "Insight 0" in stub.prompts[0]
    assert "duration_profile" not in stub.prompts[0] or "geopolitics_120s" in stub.prompts[0]


def test_generate_script_with_analysis_section_durations_match_profile(monkeypatch):
    """選ばれた duration_profile に応じた duration_sec が設定されること。"""
    se = _scored_event()
    ar = _analysis_result(duration_profile="breaking_shock_60s")
    cc = _channel_config()
    stub = _StubLLMClient(_good_llm_response("Breaking Shock"))
    monkeypatch.setattr(
        "src.generation.script_writer.get_script_llm_client", lambda: stub
    )

    script = generate_script_with_analysis(se, ar, cc)
    profile_cfg = _ANALYSIS_DURATION_PROFILES["breaking_shock_60s"]
    by_h = {s.heading: s.duration_sec for s in script.sections}
    assert by_h["hook"] == profile_cfg["hook"]
    assert by_h["setup"] == profile_cfg["setup"]
    assert by_h["twist"] == profile_cfg["twist"]
    assert by_h["punchline"] == profile_cfg["punchline"]


def test_generate_script_with_analysis_unknown_profile_falls_back(monkeypatch):
    se = _scored_event()
    ar = _analysis_result(duration_profile="bogus_999s")
    cc = _channel_config()
    stub = _StubLLMClient(_good_llm_response())
    monkeypatch.setattr(
        "src.generation.script_writer.get_script_llm_client", lambda: stub
    )
    # 例外で落ちず、デフォルトプロファイルで完走すること
    script = generate_script_with_analysis(se, ar, cc)
    assert len(script.sections) == 4


# ---------- 新ルート: 情報密度型以外を拒否 ----------

def test_generate_script_with_analysis_rejects_forbidden_pattern_then_recovers(monkeypatch):
    """LLM が Media Critique を返した場合、修正プロンプトで情報密度型を要求しリカバーする。"""
    se = _scored_event()
    ar = _analysis_result()
    cc = _channel_config()

    bad = json.loads(_good_llm_response())
    bad["selected_pattern"] = "Media Critique"
    good = _good_llm_response("Paradigm Shift")
    stub = _StubLLMClient([json.dumps(bad, ensure_ascii=False), good])
    monkeypatch.setattr(
        "src.generation.script_writer.get_script_llm_client", lambda: stub
    )

    script = generate_script_with_analysis(se, ar, cc)
    assert script.selected_pattern == "Paradigm Shift"
    # 2 回呼ばれていること（最初の禁止パターン → リトライ）
    assert len(stub.prompts) == 2
    # 修正プロンプトに情報密度型 4 種の指示が入る
    assert "Breaking Shock / Geopolitics / Paradigm Shift / Cultural Divide" in stub.prompts[1]


# ---------- 新ルート: フォールバック ----------

def test_generate_script_with_analysis_no_client_falls_back_to_legacy(monkeypatch):
    """get_script_llm_client が None の場合は legacy ルートに自動フォールバック。"""
    se = _scored_event()
    ar = _analysis_result()
    cc = _channel_config()
    monkeypatch.setattr(
        "src.generation.script_writer.get_script_llm_client", lambda: None
    )
    script = generate_script_with_analysis(se, ar, cc)
    # legacy のテンプレが返ってくる（4 セクション・空でない）
    assert len(script.sections) == 4
    assert all(s.body.strip() for s in script.sections)


def test_generate_script_with_analysis_llm_failure_falls_back(monkeypatch):
    """LLM が空文字を返し続けた場合は legacy にフォールバック。"""
    se = _scored_event()
    ar = _analysis_result()
    cc = _channel_config()
    stub = _StubLLMClient(["", "", "", ""])
    monkeypatch.setattr(
        "src.generation.script_writer.get_script_llm_client", lambda: stub
    )
    script = generate_script_with_analysis(se, ar, cc)
    assert len(script.sections) == 4


# ---------- ScriptWithAnalysisDraft Pydantic スキーマ ----------

def test_script_with_analysis_draft_required_fields():
    """target_enemy が無くてもスキーマ検証が通ること（仕様）。"""
    data = json.loads(_good_llm_response())
    draft = ScriptWithAnalysisDraft(**data)
    assert draft.selected_pattern in _INFO_DENSITY_PATTERNS
    assert len(draft.hook_variants) == 3
    # target_enemy フィールドはそもそもスキーマに存在しない
    assert not hasattr(draft, "target_enemy")
