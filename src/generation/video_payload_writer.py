from __future__ import annotations

from src.shared.logger import get_logger
from src.shared.models import (
    AnalysisResult,
    NewsEvent,
    VideoPayload,
    VideoScene,
    VideoScript,
)

logger = get_logger(__name__)

# 各セクションに対応するビジュアルヒント。
# 新 heading（hook/setup/twist/punchline）が正。旧 heading（fact/arbitrage_gap/
# background/japan_impact）は過去出力・テスト互換のために残す。
_VISUAL_HINTS = {
    # 新 heading（script_writer の 4 ブロック構成）
    "hook":       "インパクトのあるタイトルカードとBGM開始",
    "setup":      "建前・公式発表のテロップと媒体ロゴの提示",
    "twist":      "構造図・対立軸インフォグラフィックで裏の文脈を可視化",
    "punchline":  "シニカルな余韻を残すロワーサード + ループ回帰テロップ",
    # 旧 heading（後方互換）
    "fact":          "ニュースソースのロゴと本文テロップ",
    "arbitrage_gap": "インフォグラフィック: 構造変化の矢印図",
    "background":    "背景・構造の図解",
    "japan_impact":  "日本地図 + 関連業界アイコン",
}

# セクションごとの visual_mode（evidence_strength → mode）
_VISUAL_MODES: dict[str, str | dict[str, str]] = {
    # 新 heading
    "hook": "anchor_style",
    "setup": {
        "strong": "document_style",
        "partial": "document_style",
        "weak":    "infographic",
    },
    "twist": {
        "strong": "split_screen",
        "partial": "structure_diagram",
        "weak":    "symbolic",
    },
    "punchline": {
        "strong": "market_graphic",
        "partial": "infographic",
        "weak":    "symbolic",
    },
    # 旧 heading（後方互換）
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
    # 新 heading
    "hook":      "視聴者の注意を引き、テーマを一言で提示する",
    "setup":     "公式発表・建前を『建前』として名指しで提示する",
    "twist":     "裏の構造・仮想敵・地政学/カネ/権力の文脈を図解で暴く",
    "punchline": "価値観を揺さぶる結末と loop 機構をテロップで定着させる",
    # 旧 heading（後方互換）
    "fact":          "何が起きたかを正確に・ソース明示で伝える",
    "arbitrage_gap": "日本と海外の報道差・認識差を視覚化し、独自視点を示す",
    "background":    "事件の背景・構造・文脈を図解で解説する",
    "japan_impact":  "日本への具体的・潜在的影響を視聴者に実感させる",
}

_TRANSITION_HINTS = {
    # 新 heading
    "hook":      "cut → news headline graphic (0.3s)",
    "setup":     "wipe → document / press statement graphic (0.5s)",
    "twist":     "fade → structure diagram / split-screen contrast (0.8s)",
    "punchline": "fade-out with cynical lower-third title card (1.0s)",
    # 旧 heading（後方互換）
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

    # ── 新 heading: setup（建前・公式発表） ──────────────────────────────────
    if heading == "setup":
        if strength == "weak":
            return (
                f"Document-style infographic: official announcement text card on neutral background, "
                f"single-source label visible, typographic motion-graphic, "
                f"no photorealistic footage, clearly marked as preliminary report"
            )
        return (
            f"Document-style graphic: clean lower-third for the official statement, "
            f"press-conference podium silhouette without identifiable faces, "
            f"newspaper headline overlays from {', '.join(regions)} as supporting context, "
            f"typographic emphasis on the 'official' framing — no reenactment"
        )

    # ── 新 heading: twist（裏の構造・地政学・カネ・権力） ────────────────────
    if heading == "twist":
        if strength == "strong":
            return (
                f"Split-screen analytical infographic: contrasting national/sector perspectives, "
                f"flag icons + arrow diagrams showing structural incentives ({category}), "
                f"explicit labels for actors (governments, regulators, industries), "
                f"no real faces, no reenactment, clearly framed as structural analysis"
            )
        if strength == "partial":
            return (
                f"Structure diagram: animated arrows linking actors and incentives in {category}, "
                f"abstract icons for involved governments/industries, "
                f"side-callouts pointing to underlying drivers, "
                f"clearly labeled as analytical hypothesis, no reenactment footage"
            )
        return (
            f"Symbolic structure motif: abstract diagram of competing interests in {category}, "
            f"question-mark connectors for uncertain links, neutral palette, "
            f"text-based callouts for hypothesis framing, no photorealistic footage"
        )

    # ── 新 heading: punchline（loop 機構 + 余韻） ────────────────────────────
    if heading == "punchline":
        return (
            f"Closing lower-third title card: cynical takeaway phrasing in bold Japanese type, "
            f"loop-mechanism callback motif (matching the hook's keyword/visual), "
            f"muted background, single accent color, no human faces, "
            f"clearly framed as editorial conclusion (not a confirmed prediction)"
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
    # 仮説・分析パートは新旧 heading の両方で写実的映像を抑制する
    _hypothesis_headings = (
        "arbitrage_gap", "background", "japan_impact",  # 旧
        "twist", "punchline",                           # 新
    )
    if heading in _hypothesis_headings and strength in ("weak", "partial"):
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
    # ── 新 heading ───────────────────────────────────────────────────────────
    if heading == "setup":
        base.append("『公式発表 / 建前』であることを示すロワーサード")
        base.append("ソース名の明示（媒体名テロップ）")
        if strength == "weak":
            base.append("「単一ソース報道」の注記")
    elif heading == "twist":
        base.append("対立軸・構造を示す矢印 / split-screen / フローチャート")
        base.append("関与アクター（政府・業界・媒体）のラベル")
        non_jp = [r for r in regions if r != "japan"]
        if non_jp:
            base.append(f"比較対象地域の明示: {', '.join(non_jp)}")
    elif heading == "punchline":
        base.append("loop_mechanism を示す視覚要素（hookで使った語/図の再登場）")
        base.append("シニカルな余韻を示す閉じテロップ")
    # ── 旧 heading（後方互換） ───────────────────────────────────────────────
    elif heading == "fact":
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
    # 仮説パート（旧 arbitrage_gap/background, 新 twist）の写実的描写を抑制
    if heading in ("arbitrage_gap", "background", "twist") and strength != "strong":
        avoid.append("仮説・推論パートでの写実的ドキュメンタリー映像")
    if heading in ("japan_impact", "punchline") and strength == "weak":
        avoid.append("結論・影響を断定するグラフィック（エビデンス不十分）")
    return avoid


def _make_source_grounding(event: NewsEvent, heading: str) -> list[str]:
    regions = list(event.sources_by_locale.keys())
    if not regions:
        # fallback to legacy fields
        if event.sources_jp:
            regions.append("japan")
        if event.sources_en:
            regions.append("global")
    # japan_impact / punchline は日本視聴者向けの結論部のため必ず japan を含める
    if heading in ("japan_impact", "punchline") and "japan" not in regions:
        regions = ["japan"] + regions
    return regions or ["japan"]


def write_video_payload(
    event: NewsEvent,
    script: VideoScript,
    *,
    analysis_result: "AnalysisResult | None" = None,
) -> VideoPayload:
    """
    動画制作用JSONペイロードを生成する（映像設計書付き）。
    各ScriptSectionをVideoSceneにマッピングし、visual brief を付与する。

    analysis_result が渡された場合は visual_mood_tags / selected_perspective /
    selected_duration_profile を metadata に転送する（Phase 2 で具体的な
    ビジュアル選定に利用される情報の前段転送のみ。具体ビジュアル選定は手動 PoC で行う）。
    """
    logger.info(f"Generating video payload for event [{event.id}]")

    strength = _get_evidence_strength(event)
    source_regions_all = list(event.sources_by_locale.keys()) or ["japan"]
    uses_multi_region = len(source_regions_all) > 1

    scenes: list[VideoScene] = []

    title_layer = script.title_layer

    # LLM 生成のサムネ主文字（thumbnail_text_variants.main）があれば優先し、
    # 無ければテンプレ由来の title_layer.thumbnail_text にフォールバック。
    llm_thumb_main = ""
    if script.thumbnail_text_variants:
        llm_thumb_main = (script.thumbnail_text_variants.get("main") or "").strip()
    template_thumb = (title_layer.thumbnail_text if title_layer else "") or ""
    hook_thumbnail = llm_thumb_main or template_thumb

    for i, section in enumerate(script.sections):
        heading = section.heading
        narration = section.body

        visual_hint = _VISUAL_HINTS.get(heading, f"テロップ: {heading} / 関連画像を挿入")
        visual_mode = _resolve_mode(heading, strength)
        video_prompt = _make_video_prompt(heading, narration, event, strength)
        negative_prompt = _make_negative_prompt(heading, strength)
        # hook シーンはサムネ用テキスト（LLM優先 / テンプレfallback）を on_screen_text に使う
        if heading == "hook" and hook_thumbnail:
            on_screen_text = hook_thumbnail
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
    # thumbnail_text は LLM 側（hook_thumbnail）を正、テンプレを fallback として保存。
    # 解析時にどちら由来かが追えるよう両方残す。
    title_meta: dict = {}
    if title_layer is not None:
        title_meta = {
            "canonical_title":   title_layer.canonical_title,
            "platform_title":    title_layer.platform_title,
            "hook_line":         title_layer.hook_line,
            "thumbnail_text":    hook_thumbnail,                          # 実際に使われるテキスト
            "thumbnail_text_template": title_layer.thumbnail_text,       # テンプレ由来（常時保存）
            "thumbnail_text_llm":      llm_thumb_main or None,           # LLM 由来（ある時だけ）
            "thumbnail_text_sub":      (script.thumbnail_text_variants or {}).get("sub") or None,
            "thumbnail_source":  "llm" if llm_thumb_main else "template",
            "title_strength":    title_layer.title_strength,
            "title_style":       title_layer.title_style,
        }

    # LLM 由来の配信メタ（director の意思決定・SEO・loop 機構）を payload にも露出する。
    # YouTube/TikTok description / キーワード設定 / A/B 分析などの下流で利用可能。
    director_meta: dict = {}
    if script.director_thought:
        director_meta["director_thought"] = script.director_thought
    if script.selected_pattern:
        director_meta["selected_pattern"] = script.selected_pattern
    if script.target_enemy:
        director_meta["target_enemy"] = script.target_enemy
    if script.loop_mechanism:
        director_meta["loop_mechanism"] = script.loop_mechanism
    if script.seo_keywords:
        director_meta["seo_primary"] = (script.seo_keywords or {}).get("primary")
        secondary = (script.seo_keywords or {}).get("secondary") or []
        director_meta["seo_secondary"] = list(secondary) if isinstance(secondary, (list, tuple)) else []
    if script.hook_variants:
        director_meta["hook_variants"] = script.hook_variants

    # ── 分析レイヤー由来のメタデータ転送（Phase 1 はタグ転送のみ） ───────────────
    # 具体的なビジュアル選定は Phase 2 の手動 PoC で詰めるため、ここでは
    # AnalysisResult 由来の情報をそのまま metadata に乗せる（破壊変更なし）。
    analysis_meta: dict = {}
    if analysis_result is not None:
        analysis_meta["analysis_layer_enabled"] = True
        analysis_meta["selected_perspective"] = analysis_result.selected_perspective.axis
        analysis_meta["selected_duration_profile"] = analysis_result.selected_duration_profile
        analysis_meta["visual_mood_tags"] = list(analysis_result.visual_mood_tags or [])
        analysis_meta["analysis_version"] = analysis_result.analysis_version

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
            # Director メタデータ（SEO / pattern / loop）
            **director_meta,
            # 分析レイヤー由来（Phase 1 はタグ転送のみ）
            **analysis_meta,
        },
    )
    logger.info(
        f"Video payload generated: {len(scenes)} scenes, {total}s total, "
        f"evidence={strength}, safety={safety_level}"
    )
    return payload
