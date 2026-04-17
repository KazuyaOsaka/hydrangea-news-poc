"""映像設計書（Visual Brief）出力のテスト。"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.generation.video_payload_writer import (
    _get_evidence_strength,
    _make_must_avoid,
    _make_negative_prompt,
    _make_on_screen_text,
    _make_video_prompt,
    _resolve_mode,
    write_video_payload,
)
from src.shared.models import NewsEvent, ScriptSection, SourceRef, VideoScript


# ── ヘルパー ────────────────────────────────────────────────────────────────

def _src(name: str, url: str = "http://example.com", region: str = "japan") -> SourceRef:
    return SourceRef(name=name, url=url, region=region)


def _make_event(
    sources_by_locale: dict | None = None,
    category: str = "economy",
) -> NewsEvent:
    return NewsEvent(
        id="test-001",
        title="テストニュース",
        summary="テスト用サマリー",
        category=category,
        source="TestSource",
        published_at=datetime(2026, 4, 13, tzinfo=timezone.utc),
        sources_by_locale=sources_by_locale or {},
    )


def _make_script(event: NewsEvent) -> VideoScript:
    return VideoScript(
        event_id=event.id,
        title=event.title,
        intro="",
        sections=[
            ScriptSection(heading="hook",          body="これは大きなニュースです。",                   duration_sec=3),
            ScriptSection(heading="fact",          body="重大な事実が明らかになりました。詳細は以下の通りです。", duration_sec=12),
            ScriptSection(heading="arbitrage_gap", body="日本と海外の報道には大きな差があります。",       duration_sec=25),
            ScriptSection(heading="background",    body="この問題の背景には複雑な歴史があります。",       duration_sec=15),
            ScriptSection(heading="japan_impact",  body="日本経済への影響が懸念されます。",             duration_sec=20),
        ],
        outro="",
        total_duration_sec=75,
    )


# ── evidence strength ────────────────────────────────────────────────────────

def test_evidence_strength_strong_jp_and_global():
    event = _make_event(sources_by_locale={
        "japan":  [_src("NHK")],
        "global": [_src("Reuters", region="global")],
    })
    assert _get_evidence_strength(event) == "strong"


def test_evidence_strength_partial_japan_only():
    event = _make_event(sources_by_locale={"japan": [_src("NHK")]})
    assert _get_evidence_strength(event) == "partial"


def test_evidence_strength_partial_global_only():
    event = _make_event(sources_by_locale={"global": [_src("BBC", region="global")]})
    assert _get_evidence_strength(event) == "partial"


def test_evidence_strength_weak_no_sources():
    event = _make_event(sources_by_locale={})
    assert _get_evidence_strength(event) == "weak"


def test_evidence_strength_strong_multi_region():
    event = _make_event(sources_by_locale={
        "japan":       [_src("NHK")],
        "middle_east": [_src("AlJazeera", region="middle_east")],
        "global":      [_src("Reuters", region="global")],
    })
    assert _get_evidence_strength(event) == "strong"


# ── visual mode ──────────────────────────────────────────────────────────────

def test_visual_mode_hook_always_anchor_style():
    assert _resolve_mode("hook", "weak")   == "anchor_style"
    assert _resolve_mode("hook", "partial") == "anchor_style"
    assert _resolve_mode("hook", "strong") == "anchor_style"


def test_visual_mode_fact_strong_grounded_broll():
    assert _resolve_mode("fact", "strong") == "grounded_broll"


def test_visual_mode_fact_partial_document_style():
    assert _resolve_mode("fact", "partial") == "document_style"


def test_visual_mode_fact_weak_infographic():
    assert _resolve_mode("fact", "weak") == "infographic"


def test_visual_mode_arbitrage_gap_split_screen():
    for s in ("strong", "partial", "weak"):
        assert _resolve_mode("arbitrage_gap", s) == "split_screen"


def test_visual_mode_background_varies():
    assert _resolve_mode("background", "strong")  == "map_timeline"
    assert _resolve_mode("background", "partial") == "structure_diagram"
    assert _resolve_mode("background", "weak")    == "symbolic"


def test_visual_mode_japan_impact_varies():
    assert _resolve_mode("japan_impact", "strong")  == "market_graphic"
    assert _resolve_mode("japan_impact", "partial") == "infographic"
    assert _resolve_mode("japan_impact", "weak")    == "symbolic"


# ── negative_prompt ──────────────────────────────────────────────────────────

def test_negative_prompt_always_contains_base():
    for heading in ("hook", "fact", "arbitrage_gap", "background", "japan_impact"):
        for strength in ("strong", "partial", "weak"):
            np = _make_negative_prompt(heading, strength)
            assert "photorealistic reenactment" in np
            assert "named individual" in np


def test_negative_prompt_weak_fact_stricter_than_strong():
    np_strong = _make_negative_prompt("fact", "strong")
    np_weak   = _make_negative_prompt("fact", "weak")
    assert len(np_weak) > len(np_strong)
    assert "stock footage" in np_weak


def test_negative_prompt_hypothesis_section_adds_constraint():
    for heading in ("arbitrage_gap", "background", "japan_impact"):
        np = _make_negative_prompt(heading, "partial")
        assert "confirmed location" in np


def test_negative_prompt_strong_fact_no_hypothesis_extra():
    np = _make_negative_prompt("fact", "strong")
    assert "confirmed location" not in np


# ── on_screen_text ───────────────────────────────────────────────────────────

def test_on_screen_text_short_first_sentence():
    result = _make_on_screen_text("これは短い文です。もっと長い文章が続きます。")
    assert result == "これは短い文です。"


def test_on_screen_text_truncates_with_ellipsis():
    long = "あ" * 50
    result = _make_on_screen_text(long, max_chars=10)
    assert result.endswith("…")
    assert len(result) <= 11


def test_on_screen_text_short_narration_unchanged():
    short = "短い。"
    assert _make_on_screen_text(short) == short


def test_on_screen_text_long_first_sentence_truncates():
    # 句点が max_chars を超える位置にある場合は先頭 max_chars 文字 + "…"
    long_sentence = "あ" * 40 + "。続く。"
    result = _make_on_screen_text(long_sentence, max_chars=10)
    assert result.endswith("…")


# ── video_prompt ─────────────────────────────────────────────────────────────

def test_video_prompt_hook_no_faces():
    event = _make_event()
    prompt = _make_video_prompt("hook", "テスト", event, "weak")
    assert "no human faces" in prompt


def test_video_prompt_fact_weak_labeled_single_source():
    event = _make_event(category="economy")
    prompt = _make_video_prompt("fact", "テスト", event, "weak")
    assert "single-source" in prompt


def test_video_prompt_arbitrage_gap_split_screen():
    event = _make_event()
    prompt = _make_video_prompt("arbitrage_gap", "テスト", event, "partial")
    assert "Split-screen" in prompt
    assert "no real faces" in prompt


def test_video_prompt_japan_impact_weak_symbolic():
    event = _make_event()
    prompt = _make_video_prompt("japan_impact", "テスト", event, "weak")
    assert "dashed lines" in prompt
    assert "speculative" in prompt


# ── must_avoid stricter for weak ─────────────────────────────────────────────

def test_must_avoid_weak_more_items_than_strong():
    avoid_strong = _make_must_avoid("fact", "strong")
    avoid_weak   = _make_must_avoid("fact", "weak")
    assert len(avoid_weak) > len(avoid_strong)


def test_must_avoid_japan_impact_weak_has_speculation_warning():
    avoid = _make_must_avoid("japan_impact", "weak")
    assert any("断定" in a for a in avoid)


# ── write_video_payload (統合) ────────────────────────────────────────────────

def test_payload_has_visual_brief_fields_all_scenes():
    event = _make_event(sources_by_locale={"japan": [_src("NHK")]})
    script = _make_script(event)
    payload = write_video_payload(event, script)

    for scene in payload.scenes:
        assert scene.scene_id != "", f"scene {scene.index}: scene_id empty"
        assert scene.heading  != "", f"scene {scene.index}: heading empty"
        assert scene.visual_mode != "", f"scene {scene.index}: visual_mode empty"
        assert scene.video_prompt != "", f"scene {scene.index}: video_prompt empty"
        assert scene.negative_prompt != "", f"scene {scene.index}: negative_prompt empty"
        assert scene.on_screen_text != "", f"scene {scene.index}: on_screen_text empty"
        assert scene.visual_goal != "", f"scene {scene.index}: visual_goal empty"
        assert scene.transition_hint != "", f"scene {scene.index}: transition_hint empty"


def test_payload_metadata_visual_profile():
    event = _make_event(sources_by_locale={"japan": [_src("NHK")]})
    payload = write_video_payload(event, _make_script(event))
    assert payload.metadata["visual_profile"] == "news_explainer_shared"


def test_payload_metadata_visual_safety_level_partial():
    event = _make_event(sources_by_locale={"japan": [_src("NHK")]})
    payload = write_video_payload(event, _make_script(event))
    assert payload.metadata["visual_safety_level"] == "elevated"


def test_payload_metadata_visual_safety_level_strict_for_weak():
    event = _make_event(sources_by_locale={})
    payload = write_video_payload(event, _make_script(event))
    assert payload.metadata["visual_safety_level"] == "strict"


def test_payload_metadata_visual_safety_level_standard_for_strong():
    event = _make_event(sources_by_locale={
        "japan":  [_src("NHK")],
        "global": [_src("Reuters", region="global")],
    })
    payload = write_video_payload(event, _make_script(event))
    assert payload.metadata["visual_safety_level"] == "standard"


def test_payload_metadata_scene_count():
    event = _make_event()
    payload = write_video_payload(event, _make_script(event))
    assert payload.metadata["scene_count"] == 5


def test_payload_metadata_multi_region_true():
    event = _make_event(sources_by_locale={
        "japan":  [_src("NHK")],
        "global": [_src("Reuters", region="global")],
    })
    payload = write_video_payload(event, _make_script(event))
    assert payload.metadata["uses_multi_region_comparison"] is True


def test_payload_metadata_multi_region_false_single():
    event = _make_event(sources_by_locale={"japan": [_src("NHK")]})
    payload = write_video_payload(event, _make_script(event))
    assert payload.metadata["uses_multi_region_comparison"] is False


def test_payload_scene_ids_unique():
    event = _make_event()
    payload = write_video_payload(event, _make_script(event))
    ids = [s.scene_id for s in payload.scenes]
    assert len(ids) == len(set(ids))


def test_payload_narration_matches_script_body():
    """narration は script section body と一致すること。"""
    event = _make_event()
    script = _make_script(event)
    payload = write_video_payload(event, script)
    for scene, section in zip(payload.scenes, script.sections):
        assert scene.narration == section.body


def test_payload_backward_compat_existing_fields():
    """既存フィールド（index/narration/visual_hint/duration_sec）が壊れていないこと。"""
    event = _make_event()
    payload = write_video_payload(event, _make_script(event))
    assert payload.event_id == "test-001"
    assert len(payload.scenes) == 5
    assert payload.total_duration_sec == 75
    for scene in payload.scenes:
        assert scene.narration != ""
        assert scene.visual_hint != ""
        assert scene.duration_sec > 0


def test_payload_heading_matches_section_heading():
    event = _make_event()
    script = _make_script(event)
    payload = write_video_payload(event, script)
    for scene, section in zip(payload.scenes, script.sections):
        assert scene.heading == section.heading


def test_payload_source_grounding_contains_japan_for_japan_impact():
    event = _make_event(sources_by_locale={
        "global": [_src("Reuters", region="global")],
    })
    payload = write_video_payload(event, _make_script(event))
    japan_impact_scene = next(s for s in payload.scenes if s.heading == "japan_impact")
    assert "japan" in japan_impact_scene.source_grounding
