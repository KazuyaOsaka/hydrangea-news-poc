"""image_prompt レイヤー (image_prompt_writer) のテスト。

F-first-work-golden-master (1-S) で新設。決定論ビルダー (LLM 非関与) のため
mock 不要で完全に決定的。設計正典 (分業原則 / モデル非結合 / ADR-0001 ブランド /
ADR-0003 モラル / フックカード三役) の構造的担保を検証する。
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.generation.image_prompt_writer import (
    BANNED_POSITIVE_VOCAB,
    HOOK_CARD_ASPECT_RATIO,
    SCENE_PLATE_ASPECT_RATIO,
    ImagePromptSet,
    build_image_prompts,
)
from src.generation.video_payload_writer import write_video_payload
from src.shared.models import NewsEvent, ScriptSection, TitleLayer, VideoScript


# ── ヘルパー ────────────────────────────────────────────────────────────────

def _make_event(category: str = "politics") -> NewsEvent:
    return NewsEvent(
        id="test-img-001",
        title="テストニュース",
        summary="テスト用サマリー",
        category=category,
        source="TestSource",
        published_at=datetime(2026, 6, 11, tzinfo=timezone.utc),
        sources_by_locale={"latin_america": [{"name": "TestSource", "url": "http://example.com", "region": "latin_america"}]},
    )


def _make_script(event: NewsEvent) -> VideoScript:
    return VideoScript(
        event_id=event.id,
        title=event.title,
        intro="",
        sections=[
            ScriptSection(heading="hook",      body="数字で始まる導入です。",     duration_sec=4),
            ScriptSection(heading="setup",     body="公式発表はこうなっています。建前の説明が続きます。", duration_sec=16),
            ScriptSection(heading="twist",     body="しかし構造で見ると別の文脈が見えます。" * 4, duration_sec=40),
            ScriptSection(heading="punchline", body="その代償は生活実感に返ってきます。締めの一文です。", duration_sec=20),
        ],
        outro="",
        total_duration_sec=80,
        title_layer=TitleLayer(
            canonical_title="Canonical Title",
            platform_title="プラットフォームタイトル",
            hook_line="フック行",
            thumbnail_text="テンプレ由来",
        ),
        thumbnail_text_variants={"main": "サムネ主文字", "sub": "サムネ副文字"},
    )


def _build_set(motif_hints=None) -> ImagePromptSet:
    event = _make_event()
    script = _make_script(event)
    payload = write_video_payload(event, script)
    return build_image_prompts(event, script, payload, motif_hints=motif_hints)


# ── プレート構成 (4 シーン + フックカード = 5 本) ───────────────────────────

def test_five_plates_four_scene_one_hook_card():
    result = _build_set()
    assert len(result.plates) == 5
    roles = [p.role for p in result.plates]
    assert roles.count("scene_plate") == 4
    assert roles.count("hook_card") == 1
    scene_blocks = [p.scene_block for p in result.plates if p.role == "scene_plate"]
    assert scene_blocks == ["hook", "setup", "twist", "punchline"]


def test_plate_ids_are_unique_and_event_scoped():
    result = _build_set()
    ids = [p.plate_id for p in result.plates]
    assert len(set(ids)) == 5
    assert all(pid.startswith("test-img-001_plate_") for pid in ids)


def test_scene_plates_link_to_payload_scene_ids():
    result = _build_set()
    scene_plates = [p for p in result.plates if p.role == "scene_plate"]
    assert all(p.source_scene_id for p in scene_plates)
    assert scene_plates[0].source_scene_id == "test-img-001_s00_hook"


# ── アスペクト比 (シーン = 1:1 / フックカード = 9:16) ───────────────────────

def test_aspect_ratios():
    result = _build_set()
    for p in result.plates:
        if p.role == "hook_card":
            assert p.aspect_ratio == HOOK_CARD_ASPECT_RATIO == "9:16"
        else:
            assert p.aspect_ratio == SCENE_PLATE_ASPECT_RATIO == "1:1"
    assert result.aspect_ratio_policy == {
        "scene_plate": "1:1",
        "hook_card": "9:16",
    }


# ── 分業原則: 文字なしを positive / negative 両方で担保 ─────────────────────

def test_no_text_directive_in_positive_prompt():
    result = _build_set()
    for p in result.plates:
        assert "no text" in p.prompt_en
        assert "no letters" in p.prompt_en


def test_no_text_terms_in_negative_prompt():
    result = _build_set()
    for p in result.plates:
        for term in ("text", "letters", "numbers", "captions", "typography", "watermark"):
            assert term in p.negative_prompt_en


# ── ADR-0001: ブランドトーン (禁止語彙は positive に出さない、5 色パレット) ──

def test_banned_vocab_not_in_positive_prompt():
    result = _build_set()
    for p in result.plates:
        lowered = p.prompt_en.lower()
        for banned in BANNED_POSITIVE_VOCAB:
            assert banned not in lowered, f"{p.plate_id}: banned vocab {banned!r}"


def test_brand_palette_and_editorial_style_present():
    result = _build_set()
    for p in result.plates:
        assert "#0A0A0A" in p.prompt_en
        assert "#4A6FA5" in p.prompt_en
        assert "documentary infographic" in p.prompt_en
        assert "editorial" in p.prompt_en


# ── ADR-0003: モラル (ICRC / 実在人物 / 再現映像の禁止) ─────────────────────

def test_adr0003_negatives_present():
    result = _build_set()
    for p in result.plates:
        for term in ("red cross emblem", "ICRC", "real person", "combat"):
            assert term in p.negative_prompt_en, f"{p.plate_id}: missing {term!r}"


def test_adr0003_must_avoid_attached_to_all_plates():
    result = _build_set()
    for p in result.plates:
        joined = " / ".join(p.must_avoid)
        assert "ICRC" in joined
        assert "real persons" in joined
        assert "text" in joined


# ── モデル非結合原則: 意味記述 3 要素が正典として保持される ─────────────────

def test_semantic_description_fields_populated():
    result = _build_set()
    for p in result.plates:
        assert p.scene_intent
        assert p.composition
        assert p.style
        # prompt_en は意味記述から組み立てられている
        assert p.scene_intent.split(".")[0][:40] in p.prompt_en


# ── フックカード: 三役 + thumbnail_text 余白指示 ────────────────────────────

def test_hook_card_reserves_typography_margin():
    result = _build_set()
    hook_card = next(p for p in result.plates if p.role == "hook_card")
    assert "reserved negative space" in p_text(hook_card)
    assert "9:16" in hook_card.composition
    assert "thumbnail" in hook_card.notes


def p_text(plate) -> str:
    return plate.prompt_en + " " + plate.composition


def test_thumbnail_text_recorded_in_metadata():
    result = _build_set()
    assert result.metadata["thumbnail_text_for_hook_card"] == "サムネ主文字"


# ── motif hints (イベント固有の意味記述注入) ────────────────────────────────

def test_motif_hints_injected_into_prompt():
    hints = {
        "twist": ["abstract monitoring eye over a checklist clipboard"],
        "hook_card": ["prison gate silhouette with barbed wire"],
    }
    result = _build_set(motif_hints=hints)
    twist = next(p for p in result.plates if p.scene_block == "twist" and p.role == "scene_plate")
    assert "monitoring eye" in twist.prompt_en
    assert twist.motif_hints == hints["twist"]
    hook_card = next(p for p in result.plates if p.role == "hook_card")
    assert "prison gate silhouette" in hook_card.prompt_en


def test_motif_hints_with_banned_vocab_rejected():
    with pytest.raises(ValueError, match="banned vocabulary"):
        _build_set(motif_hints={"hook": ["cinematic prison corridor"]})


def test_hook_card_falls_back_to_hook_hints():
    result = _build_set(motif_hints={"hook": ["abstract scale-of-justice icon"]})
    hook_card = next(p for p in result.plates if p.role == "hook_card")
    assert "scale-of-justice" in hook_card.prompt_en


# ── 決定論 (同入力 → 同出力、generated_at を除く) ───────────────────────────

def test_deterministic_output():
    a = _build_set()
    b = _build_set()
    for pa, pb in zip(a.plates, b.plates):
        assert pa.model_dump() == pb.model_dump()


# ── JSON round-trip ─────────────────────────────────────────────────────────

def test_round_trip():
    result = _build_set()
    restored = ImagePromptSet.model_validate_json(result.model_dump_json())
    assert restored.event_id == result.event_id
    assert len(restored.plates) == 5
