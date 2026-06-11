"""image_prompt レイヤー — AI 画像生成用ビジュアルプレートのプロンプト構築。

F-first-work-golden-master (1-S / 2026-06-11) で新設。F-image-prompt-spec
(ADR-0001/0002/0003、2026-05-18) の実装解。video_payload_writer.py と同じく
**決定論的** (LLM 非関与) に、script 4 ブロック (hook/setup/twist/punchline) の
各シーン用プレート 4 本 + フックカード用プレート 1 本 = 計 5 本を構築する。

設計正典 (2026-06-10 クラウド調査、DECISION_LOG 2026-06-11 エントリ参照):

- **分業原則**: 文字はコードで描く (Remotion タイポグラフィ)、絵は AI で描く。
  プレートは **文字なしのビジュアルプレート** (no text / no letters / no captions を
  positive 指示と negative prompt の両方で担保)。日本語描画品質へのモデル依存を
  構造的に排除する。
- **モデル非結合原則**: 正典は意味記述 (scene_intent + composition + style)。
  prompt_en はそこから組み立てた共通英語プロンプト 1 本 (複数モデルへ同文投入して
  公平比較するため、特定モデルの方言に分岐しない)。
- **ブランドトーン**: ADR-0001 (sober investigative documentary infographic /
  editorial / source-driven、5 色パレット強制、cinematic / thriller /
  photorealistic 系語彙は positive prompt に絶対含めない)。
- **コンテンツモラル**: ADR-0003 (実在人物・ICRC 標章・赤十字マーク・事件再現は
  禁止 → 抽象アイコン・図形・シルエットで代替)。
- **フックカード = 第1フレーム = サムネ統合**: hook card プレートは frame 0〜2 秒の
  フックカード背景・Shorts サムネフレーム・TikTok カバーの三役を兼ねる 9:16
  全画面プレート。thumbnail_text (Remotion で後乗せ) のための中央余白を確保する。
- **シーンプレートは 1:1**: 中央ビジュアル帯 (セーフゾーン設計) への配置 +
  Ken Burns パン・ズームの可動域を確保するため正方形で生成する。

画像生成 API の配線はしない (3 候補モデル比較は手動 PoC)。出力はプロンプト
構造データ (ImagePromptSet) のみ。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from src.shared.logger import get_logger
from src.shared.models import NewsEvent, VideoPayload, VideoScript

logger = get_logger(__name__)

# ── ブランド構造データ (ADR-0001) ──────────────────────────────────────────

_PALETTE_EN = (
    "strict color palette: near-black background (#0A0A0A), "
    "off-white graphic elements (#F5F5F0), hydrangea blue accent (#4A6FA5), "
    "grey secondary elements (#808080); muted red (#A04848) only for a single "
    "warning motif if essential, never dominant"
)

_STYLE_EN = (
    "sober investigative documentary infographic style, editorial lighting, "
    "source-driven layout, restrained, high-density, sharp, "
    "flat graphic design, vector-like clarity"
)

# 分業原則: 文字は Remotion レイヤーで描く。プレートには一切の文字を入れない。
_NO_TEXT_EN = (
    "absolutely no text, no letters, no words, no numbers, no captions, "
    "no typography, no labels, no logos, no watermarks anywhere in the image "
    "(all typography is rendered separately in code)"
)

# negative prompt: 文字排除 + ADR-0003 固定禁止事項 + ADR-0001 禁止トーン。
# (禁止語彙が negative 側に列挙されるのは ADR-0001 のスキーマ例と同形 = 正典通り)
_BASE_NEGATIVE_EN = (
    "text, letters, words, numbers, captions, typography, labels, logos, watermark, "
    "photorealistic reenactment of real events, photorealism, "
    "identifiable real person, real person likeness, human face, "
    "red cross emblem, red crescent emblem, ICRC logo, ICRC uniform, "
    "armband with emblem, combat footage, weapons, gore, blood, "
    "cinematic lighting, dark cinematic mood, thriller atmosphere, "
    "dramatic shadows, lens flare, film grain"
)

# ADR-0001 禁止語彙 (positive prompt に絶対含めない)。テストでも検証する。
BANNED_POSITIVE_VOCAB = (
    "cinematic",
    "thriller",
    "hyper-realistic",
    "photorealistic",
    "gore",
    "dramatic shadows",
)

# ADR-0003 視覚禁止事項 (must_avoid として全プレートに付与)
_ADR0003_MUST_AVOID = [
    "real faces or likenesses of real persons",
    "realistic depiction of real facilities",
    "reenactment of real events",
    "red cross / red crescent / red crystal emblems, ICRC marks or uniforms",
    "realistic war or violence imagery",
    "any text, letters or numbers baked into the image",
]

# シーンプレートのアスペクト比: 中央ビジュアル帯 + Ken Burns 可動域のため 1:1。
SCENE_PLATE_ASPECT_RATIO = "1:1"
# フックカードのアスペクト比: 第1フレーム = サムネ = カバーの三役のため 9:16 全画面。
HOOK_CARD_ASPECT_RATIO = "9:16"

# ── シーン意図 / 構図テンプレート (heading 別、英語の意味記述) ────────────────
# narration の翻訳はしない (決定論維持)。イベント固有のモチーフは motif_hints
# (英語) で呼び出し側から注入する (モデル非結合原則: 正典は意味記述)。

_SCENE_INTENT_EN = {
    "hook": (
        "a single strong abstract focal motif that condenses the scale and "
        "tension of a {category} news story at first glance"
    ),
    "setup": (
        "the official surface of the story: abstract document-style motifs "
        "(file folders, stacked papers, a podium silhouette with no person) "
        "that read as 'official statements and reported facts'"
    ),
    "twist": (
        "the hidden structure behind the story: an abstract diagram-like "
        "composition of actors, incentives and flows of power and money in "
        "{category}, with connector lines and arrow motifs"
    ),
    "punchline": (
        "a quiet, restrained closing motif that links the global structure "
        "back to everyday life, leaving a cynical but intelligent afterimage"
    ),
}

_SCENE_COMPOSITION_EN = {
    "hook": (
        "centered composition, one dominant abstract symbol, generous dark "
        "negative space around it"
    ),
    "setup": (
        "orderly grid-like arrangement of abstract document shapes, calm and "
        "institutional, slightly off-center focal point"
    ),
    "twist": (
        "network-diagram composition: abstract nodes connected by thin lines "
        "and arrows, asymmetric tension between two clusters"
    ),
    "punchline": (
        "minimal composition with a small isolated motif low in the frame, "
        "large breathing space above"
    ),
}

_HOOK_CARD_INTENT_EN = (
    "a full-frame vertical cover plate that works as the very first frame of "
    "a short news video, as its thumbnail and as its cover image: one striking "
    "abstract motif summarizing a {category} story, instantly readable at "
    "feed-scroll speed"
)

# thumbnail_text は Remotion で後乗せするため、中央帯に余白を予約する。
_HOOK_CARD_COMPOSITION_EN = (
    "9:16 vertical composition; keep the central horizontal band (roughly the "
    "middle third of the frame) visually calm and empty as reserved negative "
    "space for headline typography overlaid later in code; place the focal "
    "motif in the upper third, keep the bottom third dark and quiet"
)


class ImagePlatePrompt(BaseModel):
    """1 プレート分の画像生成プロンプト (意味記述 + 共通英語プロンプト)。"""

    plate_id: str
    role: str  # "scene_plate" | "hook_card"
    scene_block: str  # hook / setup / twist / punchline (hook_card は "hook")
    aspect_ratio: str
    # ── モデル非結合の正典 = 意味記述 3 要素 ──
    scene_intent: str
    composition: str
    style: str
    # ── 3 モデル同文投入用の共通プロンプト ──
    prompt_en: str
    negative_prompt_en: str
    must_avoid: list[str] = Field(default_factory=list)
    motif_hints: list[str] = Field(default_factory=list)
    notes: str = ""
    source_scene_id: str = ""


class ImagePromptSet(BaseModel):
    """イベント 1 件分のプレートプロンプト一式 (4 シーン + フックカード = 5 本)。"""

    event_id: str
    title: str
    generated_at: str
    aspect_ratio_policy: dict[str, str] = Field(default_factory=dict)
    plates: list[ImagePlatePrompt] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


def _validate_motif_hints(hints: list[str]) -> list[str]:
    """motif hints に禁止語彙が混入していないか検証する (混入は ValueError)。"""
    for hint in hints:
        lowered = hint.lower()
        for banned in BANNED_POSITIVE_VOCAB:
            if banned in lowered:
                raise ValueError(
                    f"motif hint contains banned vocabulary {banned!r}: {hint!r}"
                )
    return hints


def _assemble_prompt_en(
    scene_intent: str, composition: str, motif_hints: list[str]
) -> str:
    """意味記述 3 要素 + motif hints から共通英語プロンプトを組み立てる。"""
    parts = [
        f"Abstract editorial news graphic: {scene_intent}.",
    ]
    if motif_hints:
        parts.append(
            "Suggested abstract motifs (render as flat icons, silhouettes or "
            f"diagrams, never photorealistic): {', '.join(motif_hints)}."
        )
    parts.append(f"Composition: {composition}.")
    parts.append(f"Style: {_STYLE_EN}.")
    parts.append(f"Colors: {_PALETTE_EN}.")
    parts.append(f"Constraints: {_NO_TEXT_EN}.")
    return " ".join(parts)


def build_image_prompts(
    event: NewsEvent,
    script: VideoScript,
    payload: VideoPayload,
    *,
    motif_hints: Optional[dict[str, list[str]]] = None,
) -> ImagePromptSet:
    """video_payload の 4 シーン + フックカードのプレートプロンプト 5 本を構築する。

    Args:
        event:   対象イベント (category をシーン意図テンプレートに使う)。
        script:  生成済み台本 (シーン構成の正)。
        payload: 生成済み video_payload (scene_id / must_avoid /
                 visual_safety_level を引き継ぐ)。
        motif_hints: scene_block ("hook"/"setup"/"twist"/"punchline"/"hook_card")
                 → 英語モチーフ語句リスト。イベント固有の意味記述を呼び出し側が
                 注入する (省略時は heading 別の汎用プレート)。禁止語彙の混入は
                 ValueError。

    Returns:
        ImagePromptSet: plates は scene 順 (hook/setup/twist/punchline) +
        hook_card の計 5 本。
    """
    hints = motif_hints or {}
    category = event.category or "general"

    plates: list[ImagePlatePrompt] = []

    for scene in payload.scenes:
        heading = scene.heading or f"scene{scene.index}"
        intent = _SCENE_INTENT_EN.get(
            heading,
            f"an abstract editorial motif for the '{heading}' section of a "
            f"{{category}} news story",
        ).format(category=category)
        composition = _SCENE_COMPOSITION_EN.get(
            heading, "centered abstract composition with generous negative space"
        )
        scene_hints = _validate_motif_hints(list(hints.get(heading, [])))
        must_avoid = list(_ADR0003_MUST_AVOID)

        plates.append(
            ImagePlatePrompt(
                plate_id=f"{event.id}_plate_{heading}",
                role="scene_plate",
                scene_block=heading,
                aspect_ratio=SCENE_PLATE_ASPECT_RATIO,
                scene_intent=intent,
                composition=composition,
                style=_STYLE_EN,
                prompt_en=_assemble_prompt_en(intent, composition, scene_hints),
                negative_prompt_en=_BASE_NEGATIVE_EN,
                must_avoid=must_avoid,
                motif_hints=scene_hints,
                notes=(
                    "scene plate for the central visual band; generated square "
                    "(1:1) so the Remotion Ken Burns pan/zoom can move inside it"
                ),
                source_scene_id=scene.scene_id,
            )
        )

    # フックカード (第1フレーム = サムネフレーム = カバーの三役)
    hook_hints = _validate_motif_hints(
        list(hints.get("hook_card", hints.get("hook", [])))
    )
    hook_intent = _HOOK_CARD_INTENT_EN.format(category=category)
    plates.append(
        ImagePlatePrompt(
            plate_id=f"{event.id}_plate_hook_card",
            role="hook_card",
            scene_block="hook",
            aspect_ratio=HOOK_CARD_ASPECT_RATIO,
            scene_intent=hook_intent,
            composition=_HOOK_CARD_COMPOSITION_EN,
            style=_STYLE_EN,
            prompt_en=_assemble_prompt_en(
                hook_intent, _HOOK_CARD_COMPOSITION_EN, hook_hints
            ),
            negative_prompt_en=_BASE_NEGATIVE_EN,
            must_avoid=list(_ADR0003_MUST_AVOID),
            motif_hints=hook_hints,
            notes=(
                "hook card plate: serves as frame 0-2s background, the Shorts "
                "thumbnail frame and the TikTok cover. thumbnail_text (3-5 "
                "words) is overlaid later by the Remotion typography layer in "
                "the reserved central band"
            ),
            source_scene_id="",
        )
    )

    thumbnail_text = ""
    if script.thumbnail_text_variants:
        thumbnail_text = (script.thumbnail_text_variants.get("main") or "").strip()
    if not thumbnail_text and script.title_layer is not None:
        thumbnail_text = script.title_layer.thumbnail_text or ""

    result = ImagePromptSet(
        event_id=event.id,
        title=event.title,
        generated_at=datetime.now(timezone.utc).isoformat(),
        aspect_ratio_policy={
            "scene_plate": SCENE_PLATE_ASPECT_RATIO,
            "hook_card": HOOK_CARD_ASPECT_RATIO,
        },
        plates=plates,
        metadata={
            "design_canon": "F-first-work-golden-master 2026-06-11 (DECISION_LOG)",
            "division_of_labor": "text is drawn in code (Remotion), images carry no text",
            "model_agnostic": (
                "canonical source is the semantic description "
                "(scene_intent + composition + style); prompt_en is one shared "
                "prompt submitted identically to all candidate image models"
            ),
            "visual_safety_level": payload.metadata.get("visual_safety_level", ""),
            "thumbnail_text_for_hook_card": thumbnail_text,
            "adr_refs": ["ADR-0001", "ADR-0002", "ADR-0003"],
        },
    )
    logger.info(
        f"Image prompt set generated for event [{event.id}]: "
        f"{len(plates)} plates (4 scene + 1 hook card)"
    )
    return result
