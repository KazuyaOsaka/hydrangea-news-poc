"""F-12-A: script_writer の article_text 引数（先行生成された記事の参考素材化）テスト。

article_text が渡された場合のみプロンプト末尾に「【参考: 関連記事】」セクションが
含まれること、None の場合は従来通りセクションを含まないこと、引数を渡さない
既存呼び出しが後方互換で動作することを検証する。

LLM 呼び出しはスタブで置換し、実 API は使わない。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.generation.script_writer import (
    _REFERENCE_ARTICLE_HEADER,
    _build_reference_article_section,
    _build_script_with_analysis_prompt,
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
    """プロンプト捕捉用スタブ。1 つの応答を返し続ける。"""

    def __init__(self, response: str = "{}"):
        self._response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._response


# ---------- フィクスチャ ----------

_ARTICLE_BODY = (
    "# 記事タイトル\n\n"
    "## TL;DR\n- 観測史上類のない移動する主権領土の出現\n\n"
    "## 事実：日本と世界の報道差\n"
    "FT は「移動する主権領土」と表現しており、日経の構造的整理とは語彙が異なる。\n"
)


def _scored_event(event_id: str = "evt-f12a-1") -> ScoredEvent:
    ev = NewsEvent(
        id=event_id,
        title="移動する主権領土の出現と海洋秩序",
        summary="ある国家の海洋プラットフォームが新たな主権主張を伴って移動している。",
        category="geopolitics",
        source="FT",
        published_at=datetime.now(timezone.utc),
        sources_jp=[SourceRef(name="Nikkei", url="https://jp.example.com/n1", region="japan")],
        sources_en=[SourceRef(name="FT", url="https://en.example.com/ft1", region="global")],
    )
    return ScoredEvent(event=ev, score=10.0, channel_id="geo_lens")


def _analysis_result(event_id: str = "evt-f12a-1") -> AnalysisResult:
    return AnalysisResult(
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
        insights=[
            Insight(text="主権領土が物理的に移動する事例の重要性", importance=0.9, evidence_refs=["art_0"]),
        ],
        selected_duration_profile="geopolitics_120s",
        visual_mood_tags=["causal_chain"],
        analysis_version="v1.0",
        generated_at=datetime.now(timezone.utc).isoformat(),
        llm_calls_used=3,
    )


# ---------- Unit: _build_reference_article_section ----------

def test_reference_article_section_returns_empty_for_none():
    assert _build_reference_article_section(None) == ""


def test_reference_article_section_returns_empty_for_blank_string():
    assert _build_reference_article_section("") == ""
    assert _build_reference_article_section("   \n  \n") == ""


def test_reference_article_section_includes_header_and_body():
    section = _build_reference_article_section(_ARTICLE_BODY)
    assert _REFERENCE_ARTICLE_HEADER in section
    assert "移動する主権領土" in section
    # 4 ブロック制約への注意書きが含まれる
    assert "hook/setup/twist/punchline" in section


# ---------- 新ルート: _build_script_with_analysis_prompt ----------

def test_analysis_prompt_with_article_text_includes_reference_section():
    """article_text が渡された場合、新ルートのプロンプトに参考記事セクションが含まれる。"""
    se = _scored_event()
    ar = _analysis_result()
    cc = ChannelConfig.load("geo_lens")

    prompt, _profile_id, _profile_cfg = _build_script_with_analysis_prompt(
        se, ar, cc, article_text=_ARTICLE_BODY
    )
    assert _REFERENCE_ARTICLE_HEADER in prompt
    assert "移動する主権領土" in prompt


def test_analysis_prompt_without_article_text_excludes_reference_section():
    """article_text が None の場合、参考記事セクションは含まれない。"""
    se = _scored_event()
    ar = _analysis_result()
    cc = ChannelConfig.load("geo_lens")

    prompt, _profile_id, _profile_cfg = _build_script_with_analysis_prompt(
        se, ar, cc, article_text=None
    )
    assert _REFERENCE_ARTICLE_HEADER not in prompt


def test_analysis_prompt_backward_compatible_no_article_text_arg():
    """article_text 引数を渡さない呼び出しでも動作する（None 既定値）。"""
    se = _scored_event()
    ar = _analysis_result()
    cc = ChannelConfig.load("geo_lens")

    prompt, _profile_id, _profile_cfg = _build_script_with_analysis_prompt(se, ar, cc)
    assert _REFERENCE_ARTICLE_HEADER not in prompt


# ---------- 新ルート: generate_script_with_analysis ----------

def _good_analysis_response(selected_pattern: str = "Geopolitics") -> str:
    return json.dumps(
        {
            "director_thought": "hidden_stakes 軸を Twist 中核に。" * 3,
            "selected_pattern": selected_pattern,
            "loop_mechanism": "loop-1",
            "seo_keywords": {"primary": "主権領土", "secondary": ["海洋", "地政学"]},
            "thumbnail_text": {"main": "移動する領土", "sub": "海洋秩序の崩壊"},
            "hook_variants": [
                {"type": "A", "label": "数字ショック", "text": "8割。海洋秩序が今動きます"},
                {"type": "D", "label": "逆説宣言", "text": "領土は固定されたものではない"},
                {"type": "E", "label": "名指し暴露", "text": "FT が報じた移動する領土"},
            ],
            "setup": (
                "海洋プラットフォームが新たな主権主張を伴って移動を開始しました。"
                "現時点で国際的な合意はなく、各国は対応を協議しています。"
                "ここで重要なのは事実関係の整理です。"
            ),
            "twist": (
                "ここで重要なのはこれが従来の領土概念を覆す現象だという点です。"
                "FT は「移動する主権領土」と表現していますが、これは語彙の問題ではありません。"
                "海洋構造物の主権化はかつてない地政学的事件で、各国の対応は分裂しています。"
                "つまり海洋秩序の前提が静かに書き換えられているわけです。"
                "次の数年で日本の海洋政策にも影響が及ぶ構造があります。"
            ),
            "punchline": (
                "つまり領土の概念そのものが揺らいでいるという話です。"
                "次にニュースで「主権」と聞いたら、その輪郭を疑ってみてください。"
            ),
            "peaks": {
                "3s": "ここで重要なのは",
                "7s": "FT 移動する領土",
                "15s": "従来概念の崩壊",
                "30s": "日本への波及",
            },
        },
        ensure_ascii=False,
    )


def test_generate_script_with_analysis_passes_article_text_into_prompt(monkeypatch):
    """article_text を渡すと LLM に送信されるプロンプトにそれが含まれる。"""
    se = _scored_event()
    ar = _analysis_result()
    cc = ChannelConfig.load("geo_lens")

    stub = _StubLLMClient(_good_analysis_response())
    monkeypatch.setattr(
        "src.generation.script_writer.get_script_llm_client", lambda: stub
    )
    generate_script_with_analysis(se, ar, cc, article_text=_ARTICLE_BODY)

    assert len(stub.prompts) >= 1
    assert _REFERENCE_ARTICLE_HEADER in stub.prompts[0]
    assert "移動する主権領土" in stub.prompts[0]


def test_generate_script_with_analysis_no_article_text_excludes_reference(monkeypatch):
    """article_text を渡さない既存呼び出しはセクションを含まない。"""
    se = _scored_event()
    ar = _analysis_result()
    cc = ChannelConfig.load("geo_lens")

    stub = _StubLLMClient(_good_analysis_response())
    monkeypatch.setattr(
        "src.generation.script_writer.get_script_llm_client", lambda: stub
    )
    generate_script_with_analysis(se, ar, cc)  # article_text 引数なし

    assert len(stub.prompts) >= 1
    assert _REFERENCE_ARTICLE_HEADER not in stub.prompts[0]


# ---------- Legacy: write_script ----------

def _good_legacy_response() -> str:
    """legacy ScriptDraft スキーマに準拠した応答。"""
    return json.dumps(
        {
            "director_thought": "Media Critique で日本の沈黙を突く。" * 2,
            "target_enemy": "大手メディア",
            "selected_pattern": "Media Critique",
            "loop_mechanism": "loop-3",
            "seo_keywords": {"primary": "海洋秩序", "secondary": ["主権", "領土"]},
            "thumbnail_text": {"main": "海洋秩序", "sub": "崩れる前提"},
            "hook_variants": [
                {"type": "B", "label": "固有名詞否定", "text": "NHK が言わない海洋の真実"},
                {"type": "A", "label": "数字ショック", "text": "8割。日本のEEZが揺らぐ"},
                {"type": "D", "label": "逆説宣言", "text": "領土は実は移動するんです"},
            ],
            "setup": (
                "海洋プラットフォームが主権主張を伴って動き始めました。"
                "国際合意のないまま各国は対応を協議中です。"
                "ここで事実関係を整理します。"
            ),
            "twist": (
                "ここで重要なのは従来の領土概念が崩れている事実です。"
                "FT は移動する主権領土と表現し、日本のメディアは沈黙しています。"
                "なぜ日本の報道は触れないのか。空気が支配する報道空間の構造があります。"
                "つまり情報鎖国の中で、世界の海洋秩序は静かに書き換わっています。"
                "気づいた時には選択肢が消えている可能性があります。"
            ),
            "punchline": (
                "情報鎖国ニッポンで、海洋秩序の地殻変動を見落としています。"
                "次に主権と聞いたら、その揺らぎを思い出してください。"
            ),
            "peaks": {
                "3s": "ここで重要なのは",
                "7s": "FT 8割",
                "15s": "日本の沈黙",
                "30s": "情報鎖国",
            },
        },
        ensure_ascii=False,
    )


def test_write_script_legacy_passes_article_text_into_prompt(monkeypatch):
    se = _scored_event()
    stub = _StubLLMClient(_good_legacy_response())
    monkeypatch.setattr(
        "src.generation.script_writer.get_script_llm_client", lambda: stub
    )
    write_script(se.event, triage_result=se, article_text=_ARTICLE_BODY)

    assert len(stub.prompts) >= 1
    assert _REFERENCE_ARTICLE_HEADER in stub.prompts[0]
    assert "移動する主権領土" in stub.prompts[0]


def test_write_script_legacy_no_article_text_excludes_reference(monkeypatch):
    se = _scored_event()
    stub = _StubLLMClient(_good_legacy_response())
    monkeypatch.setattr(
        "src.generation.script_writer.get_script_llm_client", lambda: stub
    )
    write_script(se.event, triage_result=se, article_text=None)

    assert len(stub.prompts) >= 1
    assert _REFERENCE_ARTICLE_HEADER not in stub.prompts[0]


def test_write_script_legacy_backward_compatible_no_article_text_arg(monkeypatch):
    """article_text 引数を渡さない既存呼び出しが従来通り動く。"""
    se = _scored_event()
    stub = _StubLLMClient(_good_legacy_response())
    monkeypatch.setattr(
        "src.generation.script_writer.get_script_llm_client", lambda: stub
    )
    script = write_script(se.event, triage_result=se)

    assert len(stub.prompts) >= 1
    assert _REFERENCE_ARTICLE_HEADER not in stub.prompts[0]
    # 既存挙動: 4 ブロック構造の VideoScript が返る
    assert len(script.sections) == 4
