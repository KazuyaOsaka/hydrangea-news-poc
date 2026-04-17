"""タイトル・フック・見出しレイヤー生成モジュール。

4層タイトルを appraisal_type と evidence 強度に連動させて生成する。

出力層:
  - canonical_title  : 事実ベースの元タイトル（event.title をそのまま使用）
  - platform_title   : TikTok / Shorts 用キャッチーなタイトル（短く・すぐ意味が取れる）
  - hook_line        : 冒頭2秒で読み上げる一文（問い or 視点差）
  - thumbnail_text   : 短いテロップ用（4〜8文字程度を優先）
  - title_strength   : "strong" or "soft"（evidence 強度）
  - title_style      : appraisal_type or "default"

タイトル生成ルール:
  - platform_title / hook_line はそれぞれ 2〜3 案 / 2 案を内部生成し、最適な1案を採用する
  - is_strong=True の場合は証拠力を活かした強い言い回しを先頭候補に置き、必ず採用する
  - is_strong=False の場合は最短（最も明確）な候補を採用する

安全条件:
  強い言い回し（「日本では報道されない」「本当の理由」「誰も知らない」「隠された背景」）は
  evidence が十分な候補（_is_strong_evidence=True）にのみ使用する。
  evidence が弱い候補では控えめな表現にフォールバックする。

使用型:
  - Structural Why       : なぜ○○——背景・理由に迫る
  - Perspective Inversion: 日本と海外で見え方が違う
  - Media Blind Spot     : 海外では大きいのに日本で目立たない
  - Personal Stakes      : ○○があなたの生活に効く
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.shared.models import NewsEvent, TitleLayer

if TYPE_CHECKING:
    from src.shared.models import ScoredEvent


# ── evidence 判定 ─────────────────────────────────────────────────────────────

def _is_strong_evidence(event: NewsEvent, triage_result: "Optional[ScoredEvent]") -> bool:
    """タイトルで強い表現を使って良いほど evidence が揃っているか判定する。

    条件（全て必要ではなく、組み合わせで判定）:
      - sources_en が存在 OR has_en_view スコアあり
      - かつ gap_reasoning が存在 OR perspective_gap_score >= 3
    """
    has_en_src = bool(event.sources_en)
    has_gap = bool(event.gap_reasoning)

    bd: dict = {}
    if triage_result is not None:
        bd = triage_result.score_breakdown or {}

    has_en_v = bd.get("editorial:has_en_view", 0.0) > 0
    pg = bd.get("editorial:perspective_gap_score", 0.0)
    bip = bd.get("editorial:background_inference_potential", 0.0)

    has_en_signal = has_en_src or has_en_v
    has_depth = has_gap or pg >= 3.0 or bip >= 3.0

    return has_en_signal and has_depth


# ── 短縮トピック抽出 ──────────────────────────────────────────────────────────

def _short_topic(title: str, max_chars: int = 20) -> str:
    """タイトルから短いトピック文字列を抽出する。

    句読点・記号・括弧の前、または max_chars 文字で切り詰める。
    """
    for sep in ("、", "。", "——", "—", "：", ":", "「", "【", "（", "(", " "):
        idx = title.find(sep)
        if 0 < idx <= max_chars:
            return title[:idx]
    if len(title) <= max_chars:
        return title
    return title[:max_chars]


# ── 候補選択ユーティリティ ────────────────────────────────────────────────────

def _pick_best_title(candidates: list[str], is_strong: bool) -> str:
    """platform_title の最適候補を選ぶ。

    - is_strong=True : 先頭候補（強い言い回しが保証されている）を採用
    - is_strong=False: 最短候補（最もシンプルで意味がすぐ取れる）を採用
    """
    if is_strong:
        return candidates[0]
    return min(candidates, key=len)


def _pick_shortest(candidates: list[str]) -> str:
    """最短候補を選ぶ（hook_line 用）。"""
    return min(candidates, key=len)


# ── platform_title 候補生成 ───────────────────────────────────────────────────

def _platform_title_candidates(
    topic: str,
    appraisal_type: Optional[str],
    is_strong: bool,
) -> list[str]:
    """appraisal_type × evidence 強度ごとに 2〜3 案の platform_title 候補を返す。

    is_strong=True の場合は先頭候補に強い言い回しを含める。
    """
    if appraisal_type == "Structural Why":
        if is_strong:
            return [
                f"{topic}——隠された背景",       # "隠された背景" ← strong expression
                f"{topic}——本当の理由",           # "本当の理由" ← strong expression
                f"なぜ{topic}が起きたのか",
            ]
        return [
            f"なぜ{topic}なのか",
            f"{topic}の気になる背景",
            f"{topic}——背景を読む",
        ]

    if appraisal_type == "Perspective Inversion":
        if is_strong:
            return [
                f"日本では報道されない{topic}の視点",  # strong expression
                f"海外は{topic}をこう見ている",
                f"日本と海外で違う{topic}の見方",
            ]
        return [
            f"日本と海外で違う{topic}の見方",
            f"{topic}——海外との温度差",
            f"海外は{topic}をこう見る",
        ]

    if appraisal_type == "Media Blind Spot":
        if is_strong:
            return [
                f"日本では報道されない{topic}",    # strong expression
                f"海外で大きい{topic}の波紋",
                f"日本が見逃している{topic}",
            ]
        return [
            f"海外で注目される{topic}",
            f"{topic}——日本と海外の差",
            f"海外では話題の{topic}",
        ]

    if appraisal_type == "Personal Stakes":
        if is_strong:
            return [
                f"{topic}があなたの家計に効く",
                f"{topic}——生活に直結する理由",
                f"知らないと損する{topic}",
            ]
        return [
            f"{topic}があなたに関わる理由",
            f"{topic}——生活への影響",
            f"知っておきたい{topic}の話",
        ]

    # appraisal なし: 元タイトルを短く整形するデフォルト
    return []


# ── hook_line 候補生成 ────────────────────────────────────────────────────────

def _hook_line_candidates(
    short_topic: str,
    appraisal_type: Optional[str],
    is_strong: bool,
) -> list[str]:
    """appraisal_type に応じた hook_line 候補（2案）を返す。

    冒頭2秒で自然に読める長さ（目安20字以内）を優先する。
    """
    if appraisal_type == "Structural Why":
        return [
            f"なぜ{short_topic}？——背景がある。",
            f"なぜ{short_topic}が起きたのか。",
        ]

    if appraisal_type == "Perspective Inversion":
        if is_strong:
            return [
                "海外の見方、日本とは違う。",
                f"{short_topic}——海外では別の話。",
            ]
        return [
            "日本と海外で見え方が違う。",
            f"{short_topic}——見方が分かれている。",
        ]

    if appraisal_type == "Media Blind Spot":
        if is_strong:
            return [
                "海外では大きいが、日本では？",
                f"{short_topic}——日本では見えていない。",
            ]
        return [
            "海外で注目——日本では見えにくい。",
            f"海外で話題の{short_topic}。",
        ]

    if appraisal_type == "Personal Stakes":
        return [
            "これ、あなたに関係ある話です。",
            f"{short_topic}——生活に影響します。",
        ]

    # デフォルト
    return [
        f"「{short_topic}」——今知るべき話。",
        f"知っておきたい{short_topic}の話。",
    ]


# ── platform_title 生成 ───────────────────────────────────────────────────────

def _make_platform_title(
    event: NewsEvent,
    appraisal_type: Optional[str],
    is_strong: bool,
) -> str:
    """appraisal_type と evidence 強度に応じた platform_title を生成する。

    候補を 2〜3 案生成し、is_strong=True なら先頭案（強い言い回し保証）、
    is_strong=False なら最短案を採用する。
    """
    topic = _short_topic(event.title)
    candidates = _platform_title_candidates(topic, appraisal_type, is_strong)

    if not candidates:
        # appraisal_type=None のデフォルト処理
        if len(event.title) <= 30:
            return event.title
        return _short_topic(event.title, 28) + "の注目ポイント"

    return _pick_best_title(candidates, is_strong)


# ── hook_line 生成 ────────────────────────────────────────────────────────────

_HOOK_LINE_MAX_CHARS = 30  # 冒頭2秒で自然に読める上限（目安）


def _truncate_hook(text: str, max_chars: int = _HOOK_LINE_MAX_CHARS) -> str:
    """hook_line を自然な文区切りで max_chars 以内に切り詰める。

    句点（。）か読点（、）の直後で切る。それもなければ max_chars で強制切断。
    """
    if len(text) <= max_chars:
        return text
    # 句点で切る（max_chars 以内）
    kuten = text.rfind("。", 0, max_chars + 1)
    if kuten > 0:
        return text[:kuten + 1]
    # 読点で切る（末尾に句点を補う）
    touten = text.rfind("、", 0, max_chars)
    if touten > 0:
        return text[:touten] + "。"
    return text[:max_chars]


def _make_hook_line(
    event: NewsEvent,
    appraisal_type: Optional[str],
    appraisal_hook: Optional[str],
    is_strong: bool,
) -> str:
    """冒頭で読み上げる一文を生成する（冒頭2秒で読める長さ）。

    appraisal_hook が既に設定されていればそれを優先する（長すぎる場合は自然な区切りで切る）。
    なければ候補 2 案を生成し、最短を採用する。
    """
    if appraisal_hook and appraisal_hook.strip():
        return _truncate_hook(appraisal_hook.strip())

    short_topic = _short_topic(event.title, 12)
    candidates = _hook_line_candidates(short_topic, appraisal_type, is_strong)
    return _pick_shortest(candidates)


# ── thumbnail_text 生成 ───────────────────────────────────────────────────────

def _make_thumbnail_text(
    event: NewsEvent,
    appraisal_type: Optional[str],
    is_strong: bool,
) -> str:
    """サムネイル・冒頭テロップ用の超短テキスト（4〜8文字程度）を生成する。"""
    if appraisal_type == "Structural Why":
        return "本当の背景" if is_strong else "なぜ？背景解説"

    if appraisal_type == "Perspective Inversion":
        return "日本 vs 海外" if is_strong else "視点の違い"

    if appraisal_type == "Media Blind Spot":
        return "日本で無報道" if is_strong else "海外では注目"

    if appraisal_type == "Personal Stakes":
        return "生活への影響"

    # デフォルト: タイトル先頭8字
    return _short_topic(event.title, 8)


# ── 公開 API ──────────────────────────────────────────────────────────────────

def generate_title_layer(
    event: NewsEvent,
    triage_result: "Optional[ScoredEvent]" = None,
) -> TitleLayer:
    """4層タイトル + サムネイルテロップ + 強度メタを生成して TitleLayer として返す。

    appraisal_type と evidence 強度に連動し、
    強い言い回しは evidence が十分な候補にのみ使用する。
    platform_title は 2〜3 案、hook_line は 2 案を内部生成し、最適な1案を採用する。
    """
    appraisal_type: Optional[str] = None
    appraisal_hook: Optional[str] = None
    if triage_result is not None:
        appraisal_type = triage_result.appraisal_type
        appraisal_hook = triage_result.appraisal_hook

    is_strong = _is_strong_evidence(event, triage_result)

    canonical_title = event.title
    platform_title = _make_platform_title(event, appraisal_type, is_strong)
    hook_line = _make_hook_line(event, appraisal_type, appraisal_hook, is_strong)
    thumbnail_text = _make_thumbnail_text(event, appraisal_type, is_strong)

    return TitleLayer(
        canonical_title=canonical_title,
        platform_title=platform_title,
        hook_line=hook_line,
        thumbnail_text=thumbnail_text,
        title_strength="strong" if is_strong else "soft",
        title_style=appraisal_type or "default",
    )
