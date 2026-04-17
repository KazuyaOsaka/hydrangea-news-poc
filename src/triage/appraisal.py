"""Stage B: Editorial Appraisal

triage 後の上位候補（15本前後）に対して、ルールベースの編集査定を行う。

目的:
  「根拠のある候補の切り口を言語化する」ための補助層。
  evidence を上書きするためのものではなく、
  根拠のある候補の中から切れ味のあるものを見つけるための補助。

4大フィルター:
  - Perspective Inversion : 日英で切り口・評価軸が大きく異なる
  - Media Blind Spot      : 海外重要・日本での報道量が薄い
  - Structural Why        : 報道差から背景仮説を立てる余地がある
  - Personal Stakes       : 視聴者の財布・キャリア・生活に直結する

安全条件（strong appraisal を抑制する条件）:
  - sources_en が空で比較根拠が弱い
  - perspective_gap_score == 0 （perspective_conflict = absent）
  - background_inference_potential == 0
  - EN-only + low_japan_relevance
  - 全編集軸が弱い（evidence 全般弱）

editorial_appraisal_score は大幅加点ではなく上限付き補助加点（最大 5.0）。
triage score を覆すほど強くせず、tie-breaker / 最終微調整に近い役割。
"""
from __future__ import annotations

from src.shared.logger import get_logger
from src.shared.models import ScoredEvent

logger = get_logger(__name__)

# ── 上限値 ────────────────────────────────────────────────────────────────────
_APPRAISAL_SCORE_MAX = 5.0   # editorial_appraisal_score の絶対上限
APPRAISAL_SCORE_MAX  = _APPRAISAL_SCORE_MAX   # public alias for tests / external use
_APPRAISAL_SCORE_HIGH = 4.0  # 高確信 appraisal の加点
_APPRAISAL_SCORE_MID  = 2.5  # 中確信 appraisal の加点
_APPRAISAL_SCORE_LOW  = 1.0  # 低確信（safety 条件ギリギリ）の加点

# 上位何本に対して appraisal を行うか
APPRAISAL_CANDIDATE_LIMIT = 15

# ── Personal Stakes キーワード ────────────────────────────────────────────────
_PERSONAL_STAKES_KW = [
    # 日本語
    "家計", "財布", "年金", "給与", "賃金", "物価", "家賃", "消費税",
    "増税", "減税", "社会保険", "雇用", "失業", "就職", "転職", "キャリア",
    "生活費", "光熱費", "電気代", "ガス代", "食料品", "住宅ローン",
    "金利", "インフレ", "円安", "円高", "節税", "投資", "老後", "退職",
    # 英語
    "household", "paycheck", "salary", "wage", "inflation", "cost of living",
    "mortgage", "rent", "tax hike", "tax cut", "pension", "retirement",
    "layoff", "unemployment", "job loss", "career", "interest rate",
    "grocery", "energy bill", "purchasing power",
]

# ── Structural Why キーワード（背景仮説を立てやすいシグナル） ─────────────────
_STRUCTURAL_WHY_CONTEXT_KW = [
    "文化", "歴史", "制度", "宗教", "地政学", "経済構造", "法制度",
    "tradition", "history", "institution", "geopolitics", "economic structure",
    "regulatory", "cultural", "legal framework", "systemic",
]


# ────────────────────────────────────────────────────────────────────────────
# 安全条件チェック
# ────────────────────────────────────────────────────────────────────────────

def _is_evidence_weak(se: ScoredEvent) -> bool:
    """evidence が弱く、仮説が飛躍しやすい候補かどうか判定。"""
    bd = se.score_breakdown
    has_en_src = bool(se.event.sources_en)
    has_gap    = bool(se.event.gap_reasoning)
    pg  = bd.get("editorial:perspective_gap_score", 0.0)
    bip = bd.get("editorial:background_inference_potential", 0.0)
    jr  = bd.get("editorial:japan_relevance_score", 0.0)
    has_jp_v = bd.get("editorial:has_jp_view", 0.0) > 0
    has_en_v = bd.get("editorial:has_en_view", 0.0) > 0

    # EN-only + low_japan_relevance → evidence 弱
    if not has_jp_v and jr < 4:
        return True
    # sources_en なし + gap_reasoning なし + EN view すらない → 比較根拠が皆無
    # EN view がある場合は構造化ソースがなくても最低限の根拠はある
    if not has_en_src and not has_gap and not has_en_v:
        return True
    # 全軸が弱い
    if pg == 0.0 and bip == 0.0:
        return True
    return False


def _get_safety_gate(se: ScoredEvent) -> tuple[bool, str]:
    """
    安全条件を評価して (suppressed: bool, reason: str) を返す。
    suppressed=True の場合、strong appraisal を付けない。
    """
    bd = se.score_breakdown
    has_en_src = bool(se.event.sources_en)
    has_gap    = bool(se.event.gap_reasoning)
    pg  = bd.get("editorial:perspective_gap_score", 0.0)
    bip = bd.get("editorial:background_inference_potential", 0.0)
    jr  = bd.get("editorial:japan_relevance_score", 0.0)
    cg  = bd.get("editorial:coverage_gap_score", 0.0)
    has_jp_v = bd.get("editorial:has_jp_view", 0.0) > 0
    has_en_v = bd.get("editorial:has_en_view", 0.0) > 0

    # sources_en が空で比較根拠が弱い（EN ビューもなければ完全に抑制）
    if not has_en_src and not has_en_v:
        return True, "sources_en=empty, no_en_view"
    # EN-only + low_japan_relevance — ただし間接的日本インパクトが強い場合は免除
    if not has_jp_v and jr < 4:
        ijai = bd.get("editorial:indirect_japan_impact_score", 0.0)
        ga   = bd.get("editorial:global_attention_score", 0.0)
        # blind_spot_global 候補として免除: 間接インパクト強 + 国際注目高 + EN sources あり
        # bip は pool events では旧スコアが残る場合があるため条件から除外
        if ijai >= 3.0 and ga >= 4.0 and has_en_src:
            return False, ""
        return True, f"en_only + low_jr={jr:.0f}"
    # perspective_gap = 0 かつ coverage_gap も弱い かつ bip = 0
    if pg == 0.0 and cg < 3.0 and bip == 0.0:
        return True, "all_axes_weak (pg=0, cg<3, bip=0)"
    return False, ""


# ────────────────────────────────────────────────────────────────────────────
# 4大フィルター スコアリング
# ────────────────────────────────────────────────────────────────────────────

def _score_perspective_inversion(se: ScoredEvent) -> float:
    """
    Perspective Inversion: 日英で切り口・評価軸が大きく異なる。
    例: 日本では英雄視、海外ではビジネス・法務・経済合理性で語られる。
    安全条件: perspective_gap_score == 0 は抑制。
    """
    bd = se.score_breakdown
    pg  = bd.get("editorial:perspective_gap_score", 0.0)
    bip = bd.get("editorial:background_inference_potential", 0.0)
    has_jp_v = bd.get("editorial:has_jp_view", 0.0) > 0
    has_en_v = bd.get("editorial:has_en_view", 0.0) > 0
    has_gap  = bool(se.event.gap_reasoning)

    # 必須: perspective_gap が存在 + 両言語ビュー
    if pg == 0.0 or not (has_jp_v and has_en_v):
        return 0.0

    rcs = bd.get("editorial:regional_contrast_score", 0.0)

    score = 0.0
    score += min(pg * 0.4, 3.0)    # pg に比例（最大 3.0）
    if has_gap:
        score += 1.5               # gap_reasoning あり → 根拠が言語化されている
    if bip >= 5:
        score += 0.5               # 背景推論余地が高い
    # JP vs 非西側の地域コントラストが強い場合に小さく加点
    if rcs >= 5.0:
        score += min(rcs * 0.12, 0.8)  # up to 0.8: 中東・東アジア視点の差
    return min(score, _APPRAISAL_SCORE_MAX)


def _score_media_blind_spot(se: ScoredEvent) -> float:
    """
    Media Blind Spot: 海外では重要・日本では報道量が薄い。
    安全条件: sources_en が空で比較根拠なし は抑制。
    """
    bd = se.score_breakdown
    cg       = bd.get("editorial:coverage_gap_score", 0.0)
    ga       = bd.get("editorial:global_attention_score", 0.0)
    jr       = bd.get("editorial:japan_relevance_score", 0.0)
    has_jp_v = bd.get("editorial:has_jp_view", 0.0) > 0
    has_en_v = bd.get("editorial:has_en_view", 0.0) > 0
    has_en_src = bool(se.event.sources_en)

    # EN ビューまたは sources_en が必要
    if not has_en_v and not has_en_src:
        return 0.0
    # coverage_gap が弱すぎる
    if cg < 3.0:
        return 0.0

    mrs = bd.get("editorial:multi_region_score", 0.0)

    score = 0.0
    score += min(cg * 0.3, 2.5)    # cg に比例（最大 2.5）
    score += min(ga * 0.15, 1.0)   # global attention ボーナス
    # JP+EN 両方あるが EN が圧倒的に長い場合（比較可能）
    if has_jp_v and has_en_v:
        score += 0.5
    # EN-only かつ jr が低い場合は少し抑制
    if not has_jp_v and jr < 5:
        score -= 0.5
    # 複数地域が報じていて日本が薄い場合 → blind spot 強調
    if mrs >= 5.0 and cg >= 3.0:
        score += min((mrs - 3.0) * 0.1, 0.4)  # up to 0.4: multi-region coverage
    return max(0.0, min(score, _APPRAISAL_SCORE_MAX))


def _score_structural_why(se: ScoredEvent) -> float:
    """
    Structural Why: 報道差から文化・制度・歴史などの背景仮説を立てる余地がある。
    安全条件: background_inference_potential == 0 は抑制。
    """
    bd = se.score_breakdown
    bip = bd.get("editorial:background_inference_potential", 0.0)
    pg  = bd.get("editorial:perspective_gap_score", 0.0)
    tg  = bd.get("editorial:tech_geopolitics_score", 0.0)
    gd  = bd.get("editorial:geopolitics_depth_score", 0.0)
    be  = bd.get("editorial:big_event_score", 0.0)
    has_gap = bool(se.event.gap_reasoning)
    has_bg  = bool(se.event.background)

    # bip が必要最低限
    if bip == 0.0:
        return 0.0

    text = f"{se.event.title} {se.event.summary}".lower()
    structural_context = any(kw in text for kw in _STRUCTURAL_WHY_CONTEXT_KW)

    score = 0.0
    score += min(bip * 0.3, 2.0)    # bip に比例（最大 2.0）
    if pg >= 4:
        score += 0.8               # 視点差が背景仮説の素地になる
    if tg >= 5 or gd >= 5 or be >= 5:
        score += 0.7               # 戦略的文脈あり → 仮説が意味を持つ
    if has_gap:
        score += 1.0               # gap_reasoning が仮説の根拠になる
    if has_bg:
        score += 0.3               # 既存背景情報
    if structural_context:
        score += 0.5               # 構造的文脈キーワード
    return min(score, _APPRAISAL_SCORE_MAX)


def _score_personal_stakes(se: ScoredEvent) -> float:
    """
    Personal Stakes: 視聴者の財布・キャリア・生活・将来に直結。
    """
    bd = se.score_breakdown
    jr  = bd.get("editorial:japan_relevance_score", 0.0)
    be  = bd.get("editorial:big_event_score", 0.0)
    bs  = bd.get("editorial:breaking_shock_score", 0.0)
    ma  = bd.get("editorial:mass_appeal_score", 0.0)
    has_impact = bool(se.event.impact_on_japan)

    text = f"{se.event.title} {se.event.summary}".lower()
    personal_hits = sum(1 for kw in _PERSONAL_STAKES_KW if kw in text)

    if personal_hits == 0 and jr < 5:
        return 0.0

    score = 0.0
    score += min(personal_hits * 0.6, 2.5)  # キーワードに比例（最大 2.5）
    if jr >= 6:
        score += 0.8               # 日本関連性高 → 視聴者直結
    elif jr >= 4:
        score += 0.4
    if has_impact:
        score += 0.7               # impact_on_japan が明示されている
    if be >= 5:
        score += 0.4               # 大型イベント（金利・選挙など）
    if bs >= 5:
        score += 0.3               # 速報ショック → 直近の生活影響
    if ma >= 4:
        score += 0.2               # 大衆的関心とも重なる
    return min(score, _APPRAISAL_SCORE_MAX)


def _score_blind_spot_global(se: ScoredEvent) -> float:
    """
    Blind Spot Global: 日本語記事が存在しないが、日本に強い間接的影響を持つグローバル重要案件。
    例: ホルムズ海峡封鎖（LNG輸入リスク）, TSMC業績（半導体サプライチェーン）, OPECカット（原油高）
    条件: EN-only / JP記事なし + 間接的日本インパクト高 + グローバル注目高
    """
    bd   = se.score_breakdown
    ijai = bd.get("editorial:indirect_japan_impact_score", 0.0)
    ga   = bd.get("editorial:global_attention_score", 0.0)
    cg   = bd.get("editorial:coverage_gap_score", 0.0)
    bip  = bd.get("editorial:background_inference_potential", 0.0)
    has_jp_v   = bd.get("editorial:has_jp_view", 0.0) > 0
    has_en_src = bool(se.event.sources_en)

    # EN sources が必要
    if not has_en_src:
        return 0.0
    # 間接インパクト + グローバル注目の組み合わせが必要
    if ijai < 3.0 or ga < 5.0:
        return 0.0
    # 日本語記事がある場合は他の appraisal type を優先（このタイプは EN-only 特化）
    if has_jp_v:
        return 0.0

    score = 0.0
    score += min(ijai * 0.35, 3.0)   # 間接インパクトに比例（最大 3.0）
    score += min(ga   * 0.2,  1.5)   # グローバル注目に比例（最大 1.5）
    if cg >= 5.0:
        score += 0.5                  # 日本での報道が薄い → まさに blind spot
    if bip > 0:
        score += 0.3                  # 背景推論余地あり
    return min(score, _APPRAISAL_SCORE_MAX)


# ────────────────────────────────────────────────────────────────────────────
# フック・理由・注意の生成（テンプレートベース）
# ────────────────────────────────────────────────────────────────────────────

def _generate_hook(appraisal_type: str, se: ScoredEvent) -> str:
    """動画冒頭3秒で使える一行フックを生成する。"""
    title = se.event.title[:40]

    _REGION_JP_LABEL: dict[str, str] = {
        "middle_east": "中東", "east_asia": "東アジア",
        "europe": "欧州", "global": "欧米英語圏",
    }

    if appraisal_type == "Perspective Inversion":
        bd = se.score_breakdown
        rcs = bd.get("editorial:regional_contrast_score", 0.0)
        regions = bd.get("source_regions", [])
        non_western = [r for r in regions if r in ("middle_east", "east_asia")]
        if rcs >= 5.0 and non_western:
            region_label = _REGION_JP_LABEL.get(non_western[0], non_western[0])
            return f"日本と{region_label}では、{title}の見方がまるで違う"
        gap = se.event.gap_reasoning
        if gap:
            # gap_reasoning の先頭文を短縮
            gap_short = gap.split("。")[0][:30] if "。" in gap else gap[:30]
            return f"日本と海外、{title}への見方がまるで違う——{gap_short}"
        return f"日本では語られない、{title}のもう一つの側面"

    if appraisal_type == "Media Blind Spot":
        bd = se.score_breakdown
        regions = bd.get("source_regions", [])
        non_jp_regions = [r for r in regions if r not in ("japan",)]
        if len(non_jp_regions) >= 2:
            labels = [_REGION_JP_LABEL.get(r, r) for r in non_jp_regions[:2]]
            return f"{'/'.join(labels)}では注目されているが、日本ではほぼ無報道——{title}"
        return f"日本ではほぼ無報道だが、海外では大きな注目を集めている——{title}"

    if appraisal_type == "Structural Why":
        return f"なぜこうなったのか？{title}の背景にある構造的理由"

    if appraisal_type == "Personal Stakes":
        return f"{title}——あなたの生活・家計への影響を読み解く"

    if appraisal_type == "Blind Spot Global":
        return f"日本のメディアが報じていない——{title}が日本経済に与える間接的な衝撃"

    return title


def _generate_reason(appraisal_type: str, se: ScoredEvent) -> str:
    """なぜこの候補に切れ味があるかを記述する。"""
    bd = se.score_breakdown
    pg  = bd.get("editorial:perspective_gap_score", 0.0)
    cg  = bd.get("editorial:coverage_gap_score", 0.0)
    bip = bd.get("editorial:background_inference_potential", 0.0)
    jr  = bd.get("editorial:japan_relevance_score", 0.0)

    _REGION_LABELS_AP: dict[str, str] = {
        "japan": "日本", "global": "欧米英語圏",
        "middle_east": "中東", "europe": "欧州", "east_asia": "東アジア",
    }

    if appraisal_type == "Perspective Inversion":
        parts = [f"perspective_gap={pg:.1f}（日英で報道の切り口が大きく異なる）"]
        if se.event.gap_reasoning:
            parts.append("gap_reasoning あり（視点差の根拠が言語化済み）")
        if bip >= 5:
            parts.append(f"background_inference_potential={bip:.1f}（背景仮説の余地が大きい）")
        # Region contrast 情報
        rcs = bd.get("editorial:regional_contrast_score", 0.0)
        regions = bd.get("source_regions", [])
        non_jp = [_REGION_LABELS_AP.get(r, r) for r in regions if r not in ("japan",)]
        if rcs >= 3.0 and non_jp:
            parts.append(f"地域対比: {'/'.join(non_jp)}（regional_contrast={rcs:.1f}）")
        return "、".join(parts)

    if appraisal_type == "Media Blind Spot":
        parts = [f"coverage_gap={cg:.1f}（海外での注目度が高く、日本の報道量が相対的に薄い）"]
        # Multi-region coverage 情報を優先表示
        mrs = bd.get("editorial:multi_region_score", 0.0)
        regions = bd.get("source_regions", [])
        non_jp_labels = [_REGION_LABELS_AP.get(r, r) for r in regions if r != "japan"]
        if mrs >= 5.0 and non_jp_labels:
            parts.append(f"カバー地域: {', '.join(non_jp_labels)}（multi_region={mrs:.1f}）")
        elif se.event.sources_en:
            parts.append(f"EN sources={len(se.event.sources_en)}件（具体的な比較根拠あり）")
        return "、".join(parts)

    if appraisal_type == "Structural Why":
        parts = [f"background_inference_potential={bip:.1f}（報道差から構造的背景を推論できる余地がある）"]
        if se.event.gap_reasoning:
            parts.append("gap_reasoning あり（仮説の土台が整っている）")
        if se.event.background:
            parts.append("background あり（既存の背景情報で補強可能）")
        return "、".join(parts)

    if appraisal_type == "Personal Stakes":
        text = f"{se.event.title} {se.event.summary}".lower()
        matched = [kw for kw in _PERSONAL_STAKES_KW if kw in text][:3]
        parts = [f"japan_relevance={jr:.1f}（視聴者の生活圏と重なる）"]
        if matched:
            parts.append(f"personal stakes キーワード: {', '.join(matched)}")
        if se.event.impact_on_japan:
            parts.append("impact_on_japan 明示あり")
        return "、".join(parts)

    if appraisal_type == "Blind Spot Global":
        ijai = bd.get("editorial:indirect_japan_impact_score", 0.0)
        ga   = bd.get("editorial:global_attention_score", 0.0)
        parts = [
            f"indirect_japan_impact={ijai:.1f}（JP記事なしでも日本への波及が見込まれる）",
            f"global_attention={ga:.1f}（国際的に高い注目度）",
        ]
        if se.event.sources_en:
            parts.append(f"EN sources={len(se.event.sources_en)}件（グローバル報道の裏付けあり）")
        return "、".join(parts)

    return "特記事項なし"


def _generate_cautions(appraisal_type: str, se: ScoredEvent) -> str:
    """どこまでが事実で、どこからが仮説かを明記する。"""
    cautions = []

    # 共通注意
    if not se.event.sources_en:
        cautions.append("EN sources なし: 比較根拠は global_view テキストのみ（構造化ソース未確認）")
    if not se.event.gap_reasoning:
        cautions.append("gap_reasoning なし: 日英視点差の根拠は未言語化（仮説段階）")

    # タイプ別注意
    if appraisal_type == "Perspective Inversion":
        bd = se.score_breakdown
        pg = bd.get("editorial:perspective_gap_score", 0.0)
        if pg < 6:
            cautions.append(f"perspective_gap={pg:.1f}: 視点差は確認できるが決定的ではない（補強要）")
        cautions.append("事実: JP/EN 両ビューあり。仮説: 切り口の差が視聴者にとって意味があるかは検証が必要")

    elif appraisal_type == "Media Blind Spot":
        if not se.event.japan_view:
            cautions.append("JP ビューなし: 日本での報道量が本当に薄いかは独立確認が必要")
        cautions.append("事実: 海外メディアが取り上げている。仮説: 日本での報道不足が意図的かどうかは不明")

    elif appraisal_type == "Structural Why":
        cautions.append("事実: 報道差・背景情報あり。仮説: 文化・制度・歴史的原因の帰属は推論（権威ある裏付け要）")
        bd = se.score_breakdown
        bip = bd.get("editorial:background_inference_potential", 0.0)
        if bip < 5:
            cautions.append(f"background_inference_potential={bip:.1f}: 仮説を立てる素地が限定的（飛躍に注意）")

    elif appraisal_type == "Personal Stakes":
        cautions.append("事実: 生活関連キーワードあり。仮説: 視聴者個人への影響度は条件依存（一般化に注意）")
        if not se.event.impact_on_japan:
            cautions.append("impact_on_japan なし: 具体的な影響試算は未実施（数字の補強要）")

    elif appraisal_type == "Blind Spot Global":
        cautions.append("事実: グローバルメディアで大きく報道。仮説: 日本への間接インパクトはキーワード推論（実害額は要確認）")
        cautions.append("JP記事なし: 日本の視点は不在（独自取材・日本語専門家コメントの追加要）")

    return "。".join(cautions) if cautions else "特記なし（evidence 十分）"


# ────────────────────────────────────────────────────────────────────────────
# tags_multi アサイン
# ────────────────────────────────────────────────────────────────────────────

def _assign_tags_multi(se: ScoredEvent) -> list[str]:
    """
    候補ごとに複数タグを持てるようにする（排他的でない）。

    タグ種別:
        politics_economy, geopolitics, japan_abroad, japanese_person_abroad,
        sports, entertainment, tech_geopolitics, coverage_gap, mass_appeal,
        personal_stakes
    """
    bd = se.score_breakdown
    tg  = bd.get("editorial:tech_geopolitics_score", 0.0)
    gd  = bd.get("editorial:geopolitics_depth_score", 0.0)
    be  = bd.get("editorial:big_event_score", 0.0)
    cg  = bd.get("editorial:coverage_gap_score", 0.0)
    ma  = bd.get("editorial:mass_appeal_score", 0.0)
    ja  = bd.get("editorial:japan_abroad_score", 0.0)
    jpa = bd.get("editorial:japanese_person_abroad_score", 0.0)
    jr  = bd.get("editorial:japan_relevance_score", 0.0)

    tags: list[str] = []

    # primary_bucket をそのまま追加
    if se.primary_bucket not in ("general",):
        tags.append(se.primary_bucket)

    # 複数タグアサイン（排他的でない）
    if tg >= 4:
        _append_once(tags, "tech_geopolitics")
    if gd >= 3 or be >= 3:
        _append_once(tags, "geopolitics" if gd >= 3 else "politics_economy")
    if be >= 5:
        _append_once(tags, "politics_economy")
    if gd >= 5:
        _append_once(tags, "geopolitics")
    if ja >= 5:
        _append_once(tags, "japan_abroad")
    if jpa >= 5:
        _append_once(tags, "japanese_person_abroad")
    if cg >= 5:
        _append_once(tags, "coverage_gap")
    if ma >= 3:
        _append_once(tags, "mass_appeal")
    if bd.get("editorial:_has_sports", 0.0) > 0:
        _append_once(tags, "sports")
    if bd.get("editorial:_has_ent", 0.0) > 0:
        _append_once(tags, "entertainment")

    # personal_stakes: Personal Stakes スコアが閾値以上
    text = f"{se.event.title} {se.event.summary}".lower()
    personal_hits = sum(1 for kw in _PERSONAL_STAKES_KW if kw in text)
    if personal_hits >= 1 and jr >= 4:
        _append_once(tags, "personal_stakes")
    elif personal_hits >= 2:
        _append_once(tags, "personal_stakes")

    return tags


def _append_once(lst: list[str], val: str) -> None:
    if val not in lst:
        lst.append(val)


# ────────────────────────────────────────────────────────────────────────────
# メイン API
# ────────────────────────────────────────────────────────────────────────────

def apply_editorial_appraisal(
    ranked: list[ScoredEvent],
    max_candidates: int = APPRAISAL_CANDIDATE_LIMIT,
) -> list[ScoredEvent]:
    """
    triage 後の上位候補に Editorial Appraisal を適用して返す。

    - 上位 max_candidates 本に対してのみ査定を行う
    - safety gate を通過しない候補は appraisal を抑制
    - editorial_appraisal_score は最大 _APPRAISAL_SCORE_MAX
    - tags_multi を全候補に付与
    - appraisal 適用後の score の再ソートは行わない
      （tie-breaker として上位では有意だが、全体ランキングは triage score を維持）
    """
    result: list[ScoredEvent] = []

    for i, se in enumerate(ranked):
        # tags_multi は全候補に付与（appraisal 抑制とは独立）
        tags_multi = _assign_tags_multi(se)

        if i >= max_candidates:
            # 上位 N 本以外は appraisal なし・tags_multi のみ付与
            result.append(se.model_copy(update={"tags_multi": tags_multi}))
            continue

        suppressed, gate_reason = _get_safety_gate(se)

        if suppressed:
            logger.debug(
                f"[Appraisal] #{i+1} suppressed ({gate_reason}): {se.event.title[:40]}"
            )
            result.append(se.model_copy(update={
                "tags_multi": tags_multi,
                "appraisal_cautions": f"[抑制] safety gate: {gate_reason}",
            }))
            continue

        # 5大フィルターのスコアリング（Blind Spot Global を追加）
        scores = {
            "Perspective Inversion": _score_perspective_inversion(se),
            "Media Blind Spot":      _score_media_blind_spot(se),
            "Structural Why":        _score_structural_why(se),
            "Personal Stakes":       _score_personal_stakes(se),
            "Blind Spot Global":     _score_blind_spot_global(se),
        }

        best_type = max(scores, key=lambda k: scores[k])
        best_score = scores[best_type]

        # スコアが低すぎる場合は appraisal なし
        if best_score < 0.5:
            logger.debug(
                f"[Appraisal] #{i+1} no appraisal (all scores < 0.5): {se.event.title[:40]}"
            )
            result.append(se.model_copy(update={"tags_multi": tags_multi}))
            continue

        # スコアを _APPRAISAL_SCORE_MAX でキャップ
        capped_score = min(best_score, _APPRAISAL_SCORE_MAX)

        hook     = _generate_hook(best_type, se)
        reason   = _generate_reason(best_type, se)
        cautions = _generate_cautions(best_type, se)

        # personal_stakes タグ: Personal Stakes で強いスコアなら確実に付与
        if best_type == "Personal Stakes" and best_score >= 1.5:
            _append_once(tags_multi, "personal_stakes")

        logger.info(
            f"[Appraisal] #{i+1} {best_type} score={capped_score:.2f} "
            f"(pi={scores['Perspective Inversion']:.1f} "
            f"mbs={scores['Media Blind Spot']:.1f} "
            f"sw={scores['Structural Why']:.1f} "
            f"ps={scores['Personal Stakes']:.1f} "
            f"bsg={scores['Blind Spot Global']:.1f}): "
            f"{se.event.title[:40]}"
        )

        result.append(se.model_copy(update={
            "tags_multi":               tags_multi,
            "appraisal_type":           best_type,
            "appraisal_hook":           hook,
            "appraisal_reason":         reason,
            "appraisal_cautions":       cautions,
            "editorial_appraisal_score": capped_score,
        }))

    return result


def final_review(selected: list[ScoredEvent]) -> list[str]:
    """
    Stage D: 選ばれた5本に対する軽い最終確認。

    チェック項目:
      - 似た話題が多すぎないか（同エンティティ2本以上）
      - hook が弱すぎるものが紛れていないか
      - evidence の弱い候補が無理に上がっていないか

    Returns:
        list[str] — 警告メッセージのリスト（空なら問題なし）
    """
    warnings: list[str] = []

    # 0. selected が空 → publishable candidates が存在しない
    if not selected:
        return [
            "[Final Review] WARNING — publishable candidates not found: "
            "all top candidates held_back by quality floor (selected=0)"
        ]

    # 1. hook が設定されていない（appraisal スキップ）候補が多すぎないか
    no_hook_count = sum(1 for se in selected if not se.appraisal_hook)
    if no_hook_count >= 3:
        warnings.append(
            f"[Final Review] hook 未設定の候補が {no_hook_count}/5 本（appraisal が効いていない可能性）"
        )

    # 2. evidence が弱い候補が選ばれていないか
    weak_evidence = [
        se for se in selected if _is_evidence_weak(se)
    ]
    if weak_evidence:
        for se in weak_evidence:
            warnings.append(
                f"[Final Review] evidence 弱い候補が選択された: {se.event.title[:40]} "
                f"(bucket={se.primary_bucket})"
            )

    # 3. 同 primary_bucket が 3 本以上
    bucket_count: dict[str, int] = {}
    for se in selected:
        b = se.primary_bucket
        bucket_count[b] = bucket_count.get(b, 0) + 1
    for bucket, cnt in bucket_count.items():
        if cnt >= 3:
            warnings.append(
                f"[Final Review] 同 primary_bucket '{bucket}' が {cnt}/5 本（偏り注意）"
            )

    # 4. 同 appraisal_type が 3 本以上
    appraisal_count: dict[str, int] = {}
    for se in selected:
        if se.appraisal_type:
            at = se.appraisal_type
            appraisal_count[at] = appraisal_count.get(at, 0) + 1
    for at, cnt in appraisal_count.items():
        if cnt >= 3:
            warnings.append(
                f"[Final Review] 同 appraisal_type '{at}' が {cnt}/5 本（切り口が偏っている）"
            )

    # 5. editorial_appraisal_score が triage score より大きい候補（evidence 逆転警告）
    for se in selected:
        if se.editorial_appraisal_score > 0 and se.score < 50.0:
            warnings.append(
                f"[Final Review] 低 triage score ({se.score:.1f}) の候補に appraisal が付いている: "
                f"{se.event.title[:40]}（evidence 逆転の可能性）"
            )

    if not warnings:
        warnings.append(f"[Final Review] OK — {len(selected)}本の選定に明確な問題なし")

    return warnings
