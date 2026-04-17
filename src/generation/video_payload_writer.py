from __future__ import annotations

from src.shared.logger import get_logger
from src.shared.models import NewsEvent, VideoPayload, VideoScene, VideoScript

logger = get_logger(__name__)

# 各セクションに対応するビジュアルヒント（後方互換）
_VISUAL_HINTS = {
    "hook": "インパクトのあるタイトルカードとBGM開始",
    "fact": "ニュースソースのロゴと本文テロップ",
    "arbitrage_gap": "インフォグラフィック: 構造変化の矢印図",
    "japan_impact": "日本地図 + 関連業界アイコン",
}

# セクションごとの visual_mode（evidence_strength → mode）
_VISUAL_MODES: dict[str, str | dict[str, str]] = {
    "hook": "anchor_style",
    "fact": {
        "strong": "grounded_broll",
        "partial": "document_style",
        "weak": "infographic",
    },
    "arbitrage_gap": "split_screen",
    "background": {
        "strong": "map_timeline",
        "partial": "structure_diagram",
        "weak": "symbolic",
    },
    "japan_impact": {
        "strong": "market_graphic",
        "partial": "infographic",
        "weak": "symbolic",
    },
}

_VISUAL_GOALS = {
    "hook": "視聴者の注意を引き、テーマを一言で提示する",
    "fact": "何が起きたかを正確に・ソース明示で伝える",
    "arbitrage_gap": "日本と海外の報道差・認識差を視覚化し、独自視点を示す",
    "background": "事件の背景・構造・文脈を図解で解説する",
    "japan_impact": "日本への具体的・潜在的影響を視聴者に実感させる",
}

_TRANSITION_HINTS = {
    "hook":          "cut → news headline graphic (0.3s)",
    "fact":          "wipe → split-screen infographic (0.5s)",
    "arbitrage_gap": "fade → map / structure diagram (0.8s)",
    "background":    "zoom → Japan region on map (0.6s)",
    "japan_impact":  "fade-out with lower-third title card (1.0s)",
}

# ベース negative_prompt（常に適用）
_BASE_NEGATIVE = (
    "photorealistic reenactment of real events, "
    "close-up of named individual's face, "
    "fabricated meeting or summit scene, "
    "combat or war footage, "
    "AI-generated likeness of real person, "
    "misleading documentary-style footage"
)

# weak evidence 時の追加制約
_WEAK_EVIDENCE_NEGATIVE_EXTRA = (
    ", stock footage of real event location, "
    "news archive footage implying factual certainty, "
    "confident establishing shot without source verification"
)

# 仮説・含意セクション追加制約（arbitrage_gap / background weak / japan_impact weak）
_HYPOTHESIS_NEGATIVE_EXTRA = (
    ", specific confirmed location B-roll, "
    "authoritative documentary narration visual"
)


def _get_evidence_strength(event: NewsEvent) -> str:
    """ソース地域数とフィールドの充足度からエビデンス強度を判定。"""
    regions = set(event.sources_by_locale.keys())
    has_jp = "japan" in regions
    has_non_jp = any(r != "japan" for r in regions)
    if has_jp and has_non_jp:
        return "strong"
    elif regions:
        return "partial"
    return "weak"


def _resolve_mode(heading: str, strength: str) -> str:
    mode = _VISUAL_MODES.get(heading, "infographic")
    if isinstance(mode, dict):
        return mode.get(strength, mode.get("partial", "infographic"))
    return mode


def _make_video_prompt(heading: str, narration: str, event: NewsEvent, strength: str) -> str:
    category = event.category or "general"
    regions = list(event.sources_by_locale.keys()) or ["japan"]

    if heading == "hook":
        return (
            f"Title card animation: bold Japanese headline text on screen, "
            f"abstract {category}-themed background with motion graphics, "
            f"high-contrast color scheme, no human faces, no specific identifiable locations"
        )

    if heading == "fact":
        if strength == "strong":
            return (
                f"News broadcast graphic: clean lower-third text overlay showing key fact, "
                f"neutral official context (building exterior or abstract press setting, no faces), "
                f"professional news aesthetic, source attribution visible, "
                f"regions covered: {', '.join(regions)}"
            )
        elif strength == "partial":
            return (
                f"Document-style graphic: official statement text on neutral background, "
                f"source name visible as lower-third, typographic layout, "
                f"no reenactment footage, motion-graphic style"
            )
        else:
            return (
                f"Infographic animation: key fact as text card, "
                f"abstract {category} icons, single-source indicator graphic, "
                f"no photorealistic footage, clearly labeled as single-source report"
            )

    if heading == "arbitrage_gap":
        return (
            f"Split-screen infographic: two panels representing contrasting media perspectives, "
            f"newspaper-style typography on both sides, abstract globe or flag icons, "
            f"visual gap/asymmetry emphasized with arrow or question mark motif, "
            f"no real faces, no reenactment, clearly analytical framing"
        )

    if heading == "background":
        if strength in ("strong", "partial"):
            return (
                f"Map or timeline graphic: animated context visualization showing "
                f"historical or geographical relationships for {category}, "
                f"structure diagram with labeled arrows, no reenactment of events, "
                f"documentary infographic style"
            )
        else:
            return (
                f"Symbolic diagram: abstract structure visualization for {category} context, "
                f"icons and connecting lines, clearly labeled as background inference, "
                f"no photorealistic elements, question-mark motifs for uncertain relationships"
            )

    if heading == "japan_impact":
        if strength == "strong":
            return (
                f"Market or daily-life graphic: Japan map silhouette with data overlay, "
                f"industry sector icons, economic indicator as animated chart, "
                f"no identifiable people, clean data-visualization aesthetic"
            )
        elif strength == "partial":
            return (
                f"Infographic: Japan outline with connecting lines to affected sectors, "
                f"text-based impact summary cards, neutral color palette, "
                f"clearly labeled as potential impact"
            )
        else:
            return (
                f"Symbolic graphic: abstract Japan connection to global event, "
                f"map with dashed lines and question marks, "
                f"clearly labeled as speculative / inferred impact, "
                f"no photorealistic elements"
            )

    return (
        f"Infographic or text-card for section '{heading}': "
        f"abstract {category} visual, no photorealistic content"
    )


def _make_negative_prompt(heading: str, strength: str) -> str:
    result = _BASE_NEGATIVE
    if strength == "weak":
        result += _WEAK_EVIDENCE_NEGATIVE_EXTRA
    if heading in ("arbitrage_gap", "background", "japan_impact") and strength in ("weak", "partial"):
        result += _HYPOTHESIS_NEGATIVE_EXTRA
    return result


def _make_on_screen_text(narration: str, max_chars: int = 28) -> str:
    """ナレーション本文を字幕向けに圧縮する。最初の文または先頭 max_chars 文字。"""
    end = narration.find("。")
    if 0 < end <= max_chars:
        return narration[:end + 1]
    if len(narration) <= max_chars:
        return narration
    return narration[:max_chars] + "…"


def _make_must_include(heading: str, strength: str, regions: list[str]) -> list[str]:
    base: list[str] = []
    if heading == "fact":
        base.append("ソース名の明示（媒体名テロップ）")
        if strength == "weak":
            base.append("「単一ソース報道」の注記")
    elif heading == "arbitrage_gap":
        base.append("報道差・認識差の視覚的対比")
        base.append("どの地域・媒体の視点かを示すラベル")
    elif heading == "background":
        base.append("時系列または地理的文脈の図解")
    elif heading == "japan_impact":
        base.append("日本を示すビジュアル要素（地図・国旗アイコン等）")
        non_jp = [r for r in regions if r != "japan"]
        if non_jp:
            base.append(f"比較対象地域の明示: {', '.join(non_jp)}")
    return base


def _make_must_avoid(heading: str, strength: str) -> list[str]:
    avoid = [
        "実在人物の顔アップ・特定個人の肖像",
        "架空の会談・会議シーンの再現映像",
        "戦闘・暴力・兵器の描写",
    ]
    if strength == "weak":
        avoid.append("事実確認されていない場所・状況の写実的映像")
        avoid.append("単一ソース情報の断定的映像表現")
    if heading in ("arbitrage_gap", "background") and strength != "strong":
        avoid.append("仮説・推論パートでの写実的ドキュメンタリー映像")
    if heading == "japan_impact" and strength == "weak":
        avoid.append("日本経済・社会への影響を断定するグラフィック（エビデンス不十分）")
    return avoid


def _make_source_grounding(event: NewsEvent, heading: str) -> list[str]:
    regions = list(event.sources_by_locale.keys())
    if not regions:
        # fallback to legacy fields
        if event.sources_jp:
            regions.append("japan")
        if event.sources_en:
            regions.append("global")
    # japan_impact は必ず japan を含む
    if heading == "japan_impact" and "japan" not in regions:
        regions = ["japan"] + regions
    return regions or ["japan"]


def write_video_payload(event: NewsEvent, script: VideoScript) -> VideoPayload:
    """
    動画制作用JSONペイロードを生成する（映像設計書付き）。
    各ScriptSectionをVideoSceneにマッピングし、visual brief を付与する。
    """
    logger.info(f"Generating video payload for event [{event.id}]")

    strength = _get_evidence_strength(event)
    source_regions_all = list(event.sources_by_locale.keys()) or ["japan"]
    uses_multi_region = len(source_regions_all) > 1

    scenes: list[VideoScene] = []

    title_layer = script.title_layer

    for i, section in enumerate(script.sections):
        heading = section.heading
        narration = section.body

        visual_hint = _VISUAL_HINTS.get(heading, f"テロップ: {heading} / 関連画像を挿入")
        visual_mode = _resolve_mode(heading, strength)
        video_prompt = _make_video_prompt(heading, narration, event, strength)
        negative_prompt = _make_negative_prompt(heading, strength)
        # hook シーンは thumbnail_text を優先して on_screen_text に使う（platform_title と整合）
        if heading == "hook" and title_layer and title_layer.thumbnail_text:
            on_screen_text = title_layer.thumbnail_text
        else:
            on_screen_text = _make_on_screen_text(narration)
        must_include = _make_must_include(heading, strength, source_regions_all)
        must_avoid = _make_must_avoid(heading, strength)
        source_grounding = _make_source_grounding(event, heading)
        scene_id = f"{event.id}_s{i:02d}_{heading}"
        transition_hint = _TRANSITION_HINTS.get(heading, "cut (0.3s)")
        visual_goal = _VISUAL_GOALS.get(heading, f"section '{heading}' の内容を映像で補完する")

        scenes.append(
            VideoScene(
                index=i,
                narration=narration,
                visual_hint=visual_hint,
                duration_sec=section.duration_sec,
                # Visual Brief
                scene_id=scene_id,
                heading=heading,
                visual_goal=visual_goal,
                visual_mode=visual_mode,
                video_prompt=video_prompt,
                negative_prompt=negative_prompt,
                on_screen_text=on_screen_text,
                must_include=must_include,
                must_avoid=must_avoid,
                source_grounding=source_grounding,
                transition_hint=transition_hint,
            )
        )

    total = sum(s.duration_sec for s in scenes)

    safety_level = {"strong": "standard", "partial": "elevated", "weak": "strict"}[strength]

    # title_layer フィールドを metadata に展開する
    title_meta: dict = {}
    if title_layer is not None:
        title_meta = {
            "canonical_title":  title_layer.canonical_title,
            "platform_title":   title_layer.platform_title,
            "hook_line":        title_layer.hook_line,
            "thumbnail_text":   title_layer.thumbnail_text,
            "title_strength":   title_layer.title_strength,
            "title_style":      title_layer.title_style,
        }

    payload = VideoPayload(
        event_id=event.id,
        title=event.title,
        scenes=scenes,
        total_duration_sec=total,
        metadata={
            "category": event.category,
            "source": event.source,
            "tags": event.tags,
            "published_at": event.published_at.isoformat(),
            "target_duration_sec": script.target_duration_sec,
            "estimated_duration_sec": script.estimated_duration_sec,
            "platform_profile": script.platform_profile,
            # Visual brief metadata
            "visual_profile": "news_explainer_shared",
            "visual_safety_level": safety_level,
            "evidence_strength": strength,
            "scene_count": len(scenes),
            "uses_multi_region_comparison": uses_multi_region,
            "source_regions": source_regions_all,
            # Title layer
            **title_meta,
        },
    )
    logger.info(
        f"Video payload generated: {len(scenes)} scenes, {total}s total, "
        f"evidence={strength}, safety={safety_level}"
    )
    return payload
