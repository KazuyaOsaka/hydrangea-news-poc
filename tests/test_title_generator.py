"""TitleLayer 生成のテスト。

検証項目:
  - 各 appraisal_type × strong / weak evidence で正しいタイトル層が生成される
  - 強い言い回し（「日本では報道されない」「本当の理由」「誰も知らない」「隠された背景」）は
    evidence が強い候補にのみ現れる
  - evidence が弱い候補では強い言い回しが出ない
  - hook_line は appraisal_hook を優先する
  - thumbnail_text は短い（15字以内）
  - VideoScript に title_layer が付与される
  - video_payload の metadata に title fields が含まれる
  - hook シーンの on_screen_text が thumbnail_text で上書きされる
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.generation.title_generator import (
    _hook_line_candidates,
    _is_strong_evidence,
    _make_hook_line,
    _make_platform_title,
    _make_thumbnail_text,
    _pick_best_title,
    _pick_shortest,
    _platform_title_candidates,
    _short_topic,
    _truncate_hook,
    generate_title_layer,
)
from src.generation.video_payload_writer import write_video_payload
from src.shared.models import (
    NewsEvent,
    ScriptSection,
    ScoredEvent,
    SourceRef,
    TitleLayer,
    VideoScript,
)


# ── ヘルパー ─────────────────────────────────────────────────────────────────

def _src(name: str = "TestMedia", region: str = "japan") -> SourceRef:
    return SourceRef(name=name, url="http://example.com", region=region)


def _make_event(
    title: str = "テストニュース：重大な出来事が発生した",
    has_en_src: bool = False,
    gap_reasoning: str = "",
    impact_on_japan: str = "",
) -> NewsEvent:
    sources_jp = [_src("NHK", "japan")]
    sources_en = [_src("Reuters", "global")] if has_en_src else []
    return NewsEvent(
        id="test-001",
        title=title,
        summary="テスト用サマリー。重要な事実が含まれる。",
        category="economy",
        source="TestSource",
        published_at=datetime(2026, 4, 13, tzinfo=timezone.utc),
        sources_jp=sources_jp,
        sources_en=sources_en,
        gap_reasoning=gap_reasoning,
        impact_on_japan=impact_on_japan,
    )


def _make_scored_event(
    event: NewsEvent,
    appraisal_type: str | None = None,
    appraisal_hook: str | None = None,
    pg: float = 0.0,
    bip: float = 0.0,
    has_en_view: float = 0.0,
) -> ScoredEvent:
    return ScoredEvent(
        event=event,
        score=5.0,
        score_breakdown={
            "editorial:perspective_gap_score": pg,
            "editorial:background_inference_potential": bip,
            "editorial:has_jp_view": 1.0,
            "editorial:has_en_view": has_en_view,
        },
        appraisal_type=appraisal_type,
        appraisal_hook=appraisal_hook,
    )


def _make_script(event: NewsEvent, title_layer: TitleLayer | None = None) -> VideoScript:
    return VideoScript(
        event_id=event.id,
        title=event.title,
        intro="",
        sections=[
            ScriptSection(heading="hook",          body="これは大きなニュースです。",                     duration_sec=3),
            ScriptSection(heading="fact",          body="重大な事実が明らかになりました。",               duration_sec=12),
            ScriptSection(heading="arbitrage_gap", body="日本と海外の報道には大きな差があります。",         duration_sec=25),
            ScriptSection(heading="background",    body="この問題の背景には複雑な歴史があります。",         duration_sec=15),
            ScriptSection(heading="japan_impact",  body="日本経済への影響が懸念されます。",               duration_sec=20),
        ],
        outro="",
        total_duration_sec=75,
        title_layer=title_layer,
    )


# ── _is_strong_evidence ───────────────────────────────────────────────────────

class TestIsStrongEvidence:
    def test_strong_with_en_src_and_gap(self):
        event = _make_event(has_en_src=True, gap_reasoning="貿易摩擦が背景にある")
        se = _make_scored_event(event, pg=4.0, bip=3.0)
        assert _is_strong_evidence(event, se) is True

    def test_strong_with_en_view_and_high_pg(self):
        event = _make_event(has_en_src=False)
        se = _make_scored_event(event, pg=4.0, has_en_view=1.0)
        assert _is_strong_evidence(event, se) is True

    def test_weak_no_en_signal(self):
        event = _make_event(has_en_src=False)
        se = _make_scored_event(event, pg=5.0, bip=5.0, has_en_view=0.0)
        assert _is_strong_evidence(event, se) is False

    def test_weak_no_depth(self):
        event = _make_event(has_en_src=True)  # en src あるが gap なし / pg 低い
        se = _make_scored_event(event, pg=1.0, bip=1.0, has_en_view=0.0)
        assert _is_strong_evidence(event, se) is False

    def test_weak_triage_result_none(self):
        event = _make_event(has_en_src=False)
        assert _is_strong_evidence(event, None) is False

    def test_strong_bip_alone_with_en_view(self):
        event = _make_event(has_en_src=False)
        se = _make_scored_event(event, bip=4.0, has_en_view=1.0)
        assert _is_strong_evidence(event, se) is True


# ── _short_topic ──────────────────────────────────────────────────────────────

class TestShortTopic:
    def test_splits_on_japanese_comma(self):
        result = _short_topic("円安が加速、日本企業に打撃")
        assert result == "円安が加速"

    def test_splits_on_dash(self):
        result = _short_topic("米国の利上げ——市場への影響")
        assert result == "米国の利上げ"

    def test_truncates_long_title(self):
        long = "非常に長いタイトルで区切り文字が全く含まれていないケース"
        result = _short_topic(long, max_chars=10)
        assert len(result) <= 10

    def test_short_title_returned_as_is(self):
        result = _short_topic("円安")
        assert result == "円安"


# ── platform_title の強い言い回し安全条件 ───────────────────────────────────

_STRONG_EXPRESSIONS = ["日本では報道されない", "本当の理由", "誰も知らない", "隠された背景"]
_SOFT_EXPRESSIONS   = ["あまり知られていない", "気になる背景", "見逃しやすい", "注目すべき背景"]


class TestPlatformTitleSafety:
    """強い言い回しは is_strong=True のときだけ現れることを検証する。"""

    @pytest.mark.parametrize("appraisal_type", [
        "Structural Why", "Perspective Inversion", "Media Blind Spot", "Personal Stakes",
    ])
    def test_no_strong_expressions_when_weak(self, appraisal_type: str):
        event = _make_event()
        title = _make_platform_title(event, appraisal_type, is_strong=False)
        for expr in _STRONG_EXPRESSIONS:
            assert expr not in title, (
                f"Strong expression '{expr}' found in weak-evidence title: {title!r}"
            )

    @pytest.mark.parametrize("appraisal_type", [
        "Structural Why", "Perspective Inversion", "Media Blind Spot",
    ])
    def test_strong_expressions_present_when_strong(self, appraisal_type: str):
        """strong evidence のとき、少なくとも1つの強い言い回しが含まれる。"""
        event = _make_event()
        title = _make_platform_title(event, appraisal_type, is_strong=True)
        has_strong = any(expr in title for expr in _STRONG_EXPRESSIONS)
        assert has_strong, (
            f"No strong expression found in strong-evidence title for {appraisal_type}: {title!r}"
        )

    def test_personal_stakes_weak_no_strong_expressions(self):
        event = _make_event()
        title = _make_platform_title(event, "Personal Stakes", is_strong=False)
        for expr in _STRONG_EXPRESSIONS:
            assert expr not in title

    def test_none_appraisal_uses_original_or_short(self):
        short_event = _make_event(title="円安の動向")
        title = _make_platform_title(short_event, None, is_strong=False)
        assert "円安" in title

    def test_none_appraisal_long_title_appended_suffix(self):
        long_event = _make_event(title="これは非常に長いタイトルで三十字を超えるものです確認テスト用追加分")
        title = _make_platform_title(long_event, None, is_strong=False)
        assert "注目ポイント" in title


# ── thumbnail_text の長さ ─────────────────────────────────────────────────────

class TestThumbnailText:
    @pytest.mark.parametrize("appraisal_type,is_strong", [
        ("Structural Why", True),
        ("Structural Why", False),
        ("Perspective Inversion", True),
        ("Perspective Inversion", False),
        ("Media Blind Spot", True),
        ("Media Blind Spot", False),
        ("Personal Stakes", True),
        (None, True),
        (None, False),
    ])
    def test_thumbnail_text_length(self, appraisal_type, is_strong):
        event = _make_event()
        text = _make_thumbnail_text(event, appraisal_type, is_strong)
        assert len(text) <= 15, f"thumbnail_text too long ({len(text)}): {text!r}"
        assert len(text) > 0

    def test_media_blind_spot_strong_label(self):
        event = _make_event()
        text = _make_thumbnail_text(event, "Media Blind Spot", is_strong=True)
        assert text == "日本で無報道"

    def test_media_blind_spot_weak_label(self):
        event = _make_event()
        text = _make_thumbnail_text(event, "Media Blind Spot", is_strong=False)
        assert text == "海外では注目"


# ── generate_title_layer ──────────────────────────────────────────────────────

class TestGenerateTitleLayer:
    def test_canonical_title_equals_event_title(self):
        event = _make_event(title="円安が加速している")
        layer = generate_title_layer(event)
        assert layer.canonical_title == "円安が加速している"

    def test_hook_line_prefers_appraisal_hook(self):
        event = _make_event(has_en_src=True, gap_reasoning="構造的な要因がある")
        se = _make_scored_event(
            event,
            appraisal_type="Structural Why",
            appraisal_hook="これが本当の問題です。",
            pg=4.0, bip=4.0,
        )
        layer = generate_title_layer(event, se)
        assert layer.hook_line == "これが本当の問題です。"

    def test_hook_line_generated_when_no_appraisal_hook(self):
        event = _make_event(has_en_src=True, gap_reasoning="構造的な要因がある")
        se = _make_scored_event(
            event,
            appraisal_type="Structural Why",
            appraisal_hook=None,
            pg=4.0, bip=4.0,
        )
        layer = generate_title_layer(event, se)
        assert len(layer.hook_line) > 0

    def test_platform_title_differs_from_canonical(self):
        event = _make_event(has_en_src=True, gap_reasoning="要因あり")
        se = _make_scored_event(
            event,
            appraisal_type="Perspective Inversion",
            pg=4.0, has_en_view=1.0,
        )
        layer = generate_title_layer(event, se)
        # platform_title は canonical_title とは異なるキャッチーな表現
        assert layer.platform_title != layer.canonical_title

    def test_weak_evidence_no_strong_expressions_in_platform_title(self):
        event = _make_event(has_en_src=False)
        se = _make_scored_event(
            event,
            appraisal_type="Perspective Inversion",
            pg=1.0,
            has_en_view=0.0,
        )
        layer = generate_title_layer(event, se)
        for expr in _STRONG_EXPRESSIONS:
            assert expr not in layer.platform_title, (
                f"Strong expression '{expr}' in weak-evidence platform_title: {layer.platform_title!r}"
            )

    def test_strong_evidence_perspective_inversion_strong_expression(self):
        event = _make_event(has_en_src=True, gap_reasoning="視点差の根拠がある")
        se = _make_scored_event(
            event,
            appraisal_type="Perspective Inversion",
            pg=5.0, has_en_view=1.0,
        )
        layer = generate_title_layer(event, se)
        assert "日本では報道されない" in layer.platform_title

    def test_no_triage_result_returns_title_layer(self):
        event = _make_event()
        layer = generate_title_layer(event, None)
        assert isinstance(layer, TitleLayer)
        assert layer.canonical_title == event.title
        assert len(layer.platform_title) > 0
        assert len(layer.hook_line) > 0

    def test_returns_title_layer_instance(self):
        event = _make_event()
        result = generate_title_layer(event)
        assert isinstance(result, TitleLayer)


# ── VideoScript に title_layer が付与される ──────────────────────────────────

class TestVideoScriptTitleLayer:
    def test_title_layer_attached_to_script(self):
        event = _make_event(has_en_src=True, gap_reasoning="背景あり")
        se = _make_scored_event(event, appraisal_type="Structural Why", pg=4.0, bip=4.0)
        from src.generation.title_generator import generate_title_layer as gtl
        layer = gtl(event, se)
        script = _make_script(event, title_layer=layer)
        assert script.title_layer is not None
        assert isinstance(script.title_layer, TitleLayer)

    def test_title_layer_none_by_default(self):
        event = _make_event()
        script = _make_script(event)
        assert script.title_layer is None


# ── video_payload の metadata に title fields が含まれる ─────────────────────

class TestVideoPayloadTitleFields:
    def test_metadata_contains_title_fields_when_layer_present(self):
        event = _make_event(has_en_src=True, gap_reasoning="背景あり")
        se = _make_scored_event(event, appraisal_type="Structural Why", pg=4.0, bip=4.0)
        from src.generation.title_generator import generate_title_layer as gtl
        layer = gtl(event, se)
        script = _make_script(event, title_layer=layer)
        payload = write_video_payload(event, script)
        assert "canonical_title" in payload.metadata
        assert "platform_title" in payload.metadata
        assert "hook_line" in payload.metadata
        assert "thumbnail_text" in payload.metadata
        assert payload.metadata["canonical_title"] == event.title

    def test_metadata_no_title_fields_when_layer_absent(self):
        event = _make_event()
        script = _make_script(event, title_layer=None)
        payload = write_video_payload(event, script)
        assert "canonical_title" not in payload.metadata
        assert "platform_title" not in payload.metadata

    def test_hook_scene_on_screen_text_uses_thumbnail_text(self):
        event = _make_event(has_en_src=True, gap_reasoning="背景あり")
        from src.generation.title_generator import generate_title_layer as gtl
        layer = gtl(event, _make_scored_event(
            event, appraisal_type="Structural Why", pg=4.0, bip=4.0
        ))
        script = _make_script(event, title_layer=layer)
        payload = write_video_payload(event, script)
        hook_scene = next(s for s in payload.scenes if s.heading == "hook")
        assert hook_scene.on_screen_text == layer.thumbnail_text

    def test_non_hook_scene_on_screen_text_from_narration(self):
        event = _make_event(has_en_src=True, gap_reasoning="背景あり")
        from src.generation.title_generator import generate_title_layer as gtl
        layer = gtl(event, _make_scored_event(
            event, appraisal_type="Structural Why", pg=4.0, bip=4.0
        ))
        script = _make_script(event, title_layer=layer)
        payload = write_video_payload(event, script)
        fact_scene = next(s for s in payload.scenes if s.heading == "fact")
        # fact の on_screen_text は narration から生成されるべき
        assert fact_scene.on_screen_text != layer.thumbnail_text

    def test_hook_scene_fallback_to_narration_when_thumbnail_empty(self):
        event = _make_event()
        layer = TitleLayer(
            canonical_title=event.title,
            platform_title="テスト platform_title",
            hook_line="テスト hook_line",
            thumbnail_text="",  # 空の場合は narration から生成
        )
        script = _make_script(event, title_layer=layer)
        payload = write_video_payload(event, script)
        hook_scene = next(s for s in payload.scenes if s.heading == "hook")
        # thumbnail_text が空なので narration から生成される
        assert len(hook_scene.on_screen_text) > 0
        assert hook_scene.on_screen_text != ""


# ── platform_title の短さ ─────────────────────────────────────────────────────

class TestPlatformTitleLength:
    """platform_title は短く・意味がすぐ取れる形であることを検証する。"""

    @pytest.mark.parametrize("appraisal_type,is_strong", [
        ("Structural Why", True),
        ("Structural Why", False),
        ("Perspective Inversion", True),
        ("Perspective Inversion", False),
        ("Media Blind Spot", True),
        ("Media Blind Spot", False),
        ("Personal Stakes", True),
        ("Personal Stakes", False),
        (None, False),
    ])
    def test_platform_title_concise(self, appraisal_type, is_strong):
        """platform_title は35字以内であること。"""
        event = _make_event()
        title = _make_platform_title(event, appraisal_type, is_strong)
        assert len(title) <= 35, (
            f"platform_title too long ({len(title)}): {title!r}"
        )
        assert len(title) > 0

    def test_platform_title_candidates_count(self):
        """_platform_title_candidates は2〜3案を返すこと。"""
        topic = "テストニュース"
        for appraisal_type in ["Structural Why", "Perspective Inversion", "Media Blind Spot", "Personal Stakes"]:
            for is_strong in [True, False]:
                candidates = _platform_title_candidates(topic, appraisal_type, is_strong)
                assert 2 <= len(candidates) <= 3, (
                    f"{appraisal_type}/{is_strong}: expected 2-3 candidates, got {len(candidates)}"
                )

    def test_pick_best_title_strong_picks_first(self):
        """is_strong=True のとき、先頭候補を選ぶこと。"""
        candidates = ["先頭候補（長め）", "短い候補"]
        result = _pick_best_title(candidates, is_strong=True)
        assert result == "先頭候補（長め）"

    def test_pick_best_title_soft_picks_shortest(self):
        """is_strong=False のとき、最短候補を選ぶこと。"""
        candidates = ["長い候補名前", "短い"]
        result = _pick_best_title(candidates, is_strong=False)
        assert result == "短い"

    def test_pick_shortest_returns_min_len(self):
        candidates = ["aaa", "b", "cccc"]
        assert _pick_shortest(candidates) == "b"


# ── hook_line の短さ ──────────────────────────────────────────────────────────

class TestHookLineLength:
    """生成された hook_line は冒頭2秒で読める短さであることを検証する。"""

    @pytest.mark.parametrize("appraisal_type,is_strong", [
        ("Structural Why", True),
        ("Structural Why", False),
        ("Perspective Inversion", True),
        ("Perspective Inversion", False),
        ("Media Blind Spot", True),
        ("Media Blind Spot", False),
        ("Personal Stakes", True),
        ("Personal Stakes", False),
        (None, False),
    ])
    def test_hook_line_generated_short(self, appraisal_type, is_strong):
        """appraisal_hook なし時の hook_line は30字以内であること。"""
        event = _make_event()
        se = _make_scored_event(
            event, appraisal_type=appraisal_type, appraisal_hook=None,
            pg=4.0 if is_strong else 0.0,
            has_en_view=1.0 if is_strong else 0.0,
        )
        # is_strong が判定に影響するためイベント側でも合わせる
        if is_strong:
            event = _make_event(has_en_src=True, gap_reasoning="根拠あり")
            se = _make_scored_event(
                event, appraisal_type=appraisal_type, appraisal_hook=None,
                pg=4.0, bip=4.0,
            )
        layer = generate_title_layer(event, se)
        assert len(layer.hook_line) <= 30, (
            f"hook_line too long ({len(layer.hook_line)}): {layer.hook_line!r}"
        )

    def test_hook_line_candidates_count(self):
        """_hook_line_candidates は2案を返すこと。"""
        for appraisal_type in ["Structural Why", "Perspective Inversion", "Media Blind Spot", "Personal Stakes", None]:
            for is_strong in [True, False]:
                candidates = _hook_line_candidates("テスト", appraisal_type, is_strong)
                assert len(candidates) == 2, (
                    f"{appraisal_type}/{is_strong}: expected 2 candidates, got {len(candidates)}"
                )

    def test_hook_line_make_function_short(self):
        """_make_hook_line（appraisal_hook=None）は30字以内を返すこと。"""
        event = _make_event()
        for appraisal_type in ["Structural Why", "Perspective Inversion", "Media Blind Spot", "Personal Stakes", None]:
            result = _make_hook_line(event, appraisal_type, appraisal_hook=None, is_strong=False)
            assert len(result) <= 30, (
                f"{appraisal_type}: hook_line too long ({len(result)}): {result!r}"
            )

    def test_long_appraisal_hook_is_truncated(self):
        """appraisal_hook が30字超の場合、自然な区切りで切り詰められること。"""
        long_hook = "日本と海外で見方がまるで違う——日本では慎重な正常化として報道されているが、海外では政策転換の始まりと見られている。"
        result = _truncate_hook(long_hook)
        assert len(result) <= 30, f"truncated hook too long ({len(result)}): {result!r}"
        assert len(result) > 0

    def test_short_appraisal_hook_unchanged(self):
        """appraisal_hook が30字以内なら変更されないこと。"""
        short_hook = "なぜ世界がこれほど違う反応をしたのか。"
        result = _truncate_hook(short_hook)
        assert result == short_hook

    def test_truncate_hook_cuts_at_kuten(self):
        """句点（。）で自然に切ること。"""
        text = "これが第一の問題です。さらにもう一点ある。全部で三点ほどある。"
        result = _truncate_hook(text, max_chars=15)
        assert result.endswith("。")
        assert len(result) <= 16  # 句点込み


# ── title_strength / title_style フィールド ───────────────────────────────────

class TestTitleStrengthStyle:
    """TitleLayer の title_strength / title_style フィールドを検証する。"""

    def test_title_strength_strong(self):
        event = _make_event(has_en_src=True, gap_reasoning="根拠あり")
        se = _make_scored_event(event, appraisal_type="Structural Why", pg=4.0, bip=4.0)
        layer = generate_title_layer(event, se)
        assert layer.title_strength == "strong"

    def test_title_strength_soft(self):
        event = _make_event(has_en_src=False)
        se = _make_scored_event(event, appraisal_type="Structural Why", pg=1.0)
        layer = generate_title_layer(event, se)
        assert layer.title_strength == "soft"

    def test_title_style_matches_appraisal_type(self):
        for appraisal_type in ["Structural Why", "Perspective Inversion", "Media Blind Spot", "Personal Stakes"]:
            event = _make_event(has_en_src=True, gap_reasoning="根拠あり")
            se = _make_scored_event(event, appraisal_type=appraisal_type, pg=4.0, bip=4.0)
            layer = generate_title_layer(event, se)
            assert layer.title_style == appraisal_type, (
                f"title_style={layer.title_style!r}, expected {appraisal_type!r}"
            )

    def test_title_style_default_when_no_appraisal(self):
        event = _make_event()
        layer = generate_title_layer(event, None)
        assert layer.title_style == "default"

    def test_title_strength_none_when_no_triage(self):
        event = _make_event(has_en_src=False)
        layer = generate_title_layer(event, None)
        assert layer.title_strength == "soft"

    def test_title_layer_has_strength_style_fields(self):
        """TitleLayer インスタンスが title_strength / title_style を持つこと。"""
        event = _make_event()
        layer = generate_title_layer(event, None)
        assert hasattr(layer, "title_strength")
        assert hasattr(layer, "title_style")
        assert layer.title_strength in ("strong", "soft")
        assert isinstance(layer.title_style, str)


# ── video_payload の metadata に title_strength / title_style が含まれる ───────

class TestVideoPayloadTitleStrengthStyle:
    def test_metadata_contains_title_strength_style_when_layer_present(self):
        event = _make_event(has_en_src=True, gap_reasoning="背景あり")
        se = _make_scored_event(event, appraisal_type="Structural Why", pg=4.0, bip=4.0)
        from src.generation.title_generator import generate_title_layer as gtl
        layer = gtl(event, se)
        script = _make_script(event, title_layer=layer)
        payload = write_video_payload(event, script)
        assert "title_strength" in payload.metadata
        assert "title_style" in payload.metadata
        assert payload.metadata["title_strength"] == "strong"
        assert payload.metadata["title_style"] == "Structural Why"

    def test_metadata_title_strength_soft_for_weak_evidence(self):
        event = _make_event(has_en_src=False)
        se = _make_scored_event(event, appraisal_type="Media Blind Spot", pg=1.0)
        from src.generation.title_generator import generate_title_layer as gtl
        layer = gtl(event, se)
        script = _make_script(event, title_layer=layer)
        payload = write_video_payload(event, script)
        assert payload.metadata["title_strength"] == "soft"
        assert payload.metadata["title_style"] == "Media Blind Spot"
