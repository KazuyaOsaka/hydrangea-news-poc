"""観点軸 4 種のルールベース抽出。

設計書 Section 5 の仕様に従う。LLM 呼び出しは行わない（Step 3 で別途 LLM が選定+検証する）。

4 軸:
    - silence_gap         : 海外で大ニュース、日本未報道
    - framing_inversion   : 日本と海外で「誰が悪者か」が真逆
    - hidden_stakes       : 日本の生活・経済に直結するが、報道で繋げられていない
    - cultural_blindspot  : 日本の常識では理解できない海外の論理

スコアと成立条件は既存の score_breakdown フィールド + sources_jp/sources_en を参照する。
ChannelConfig.perspective_axes に含まれない軸は最終フィルタで除外する。

設計上の判断:
    - cultural_uniqueness_score は既存のスコアリングに存在しない。
      設計書 Section 5.2 軸4 に「既存になければ仮実装、後で改善」とあるため、
      cultural_blindspot のスコアはトピック・タグの軽量シグナルから推定する仮実装とする。
"""
from __future__ import annotations

from typing import Optional

from src.shared.models import ChannelConfig, PerspectiveCandidate, ScoredEvent


# ---------- 共通ヘルパ ----------

def _sources_jp_count(event: ScoredEvent) -> int:
    """日本ソースの件数（sources_by_locale の "japan" を最優先、なければ sources_jp）。"""
    ev = event.event
    if ev.sources_by_locale and "japan" in ev.sources_by_locale:
        return len(ev.sources_by_locale["japan"])
    return len(ev.sources_jp)


def _sources_en_count(event: ScoredEvent) -> int:
    """海外ソース（日本以外）の件数。

    sources_by_locale が空でない場合は japan 以外の全 region 合計を採用。
    なければ sources_en の長さで代替。
    """
    ev = event.event
    if ev.sources_by_locale:
        total = 0
        for region, refs in ev.sources_by_locale.items():
            if region == "japan":
                continue
            total += len(refs)
        if total > 0 or ev.sources_by_locale:
            return total
    return len(ev.sources_en)


def _axis_score(event: ScoredEvent, key: str, default: float = 0.0) -> float:
    """score_breakdown から数値を取り出す（無ければ default）。"""
    val = (event.score_breakdown or {}).get(key, default)
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, value))


def _collect_evidence_refs(event: ScoredEvent, axis: str) -> list[str]:
    """軸ごとに参照する evidence の URL を収集する（簡易: 全ソース URL）。"""
    refs: list[str] = []
    seen: set[str] = set()
    ev = event.event
    if ev.sources_by_locale:
        for region, source_refs in ev.sources_by_locale.items():
            for s in source_refs:
                if s.url and s.url not in seen:
                    seen.add(s.url)
                    refs.append(s.url)
    else:
        for s in (*ev.sources_jp, *ev.sources_en):
            if s.url and s.url not in seen:
                seen.add(s.url)
                refs.append(s.url)
    return refs


# ---------- 軸1: Silence Gap ----------

def _meets_silence_gap_conditions(event: ScoredEvent) -> bool:
    """成立条件: sources_en >= 3 AND sources_jp == 0 かつ
    global_attention >= 6.0 かつ indirect_japan_impact >= 4.0。
    """
    if _sources_en_count(event) < 3:
        return False
    if _sources_jp_count(event) != 0:
        return False
    if _axis_score(event, "global_attention_score") < 6.0:
        return False
    if _axis_score(event, "indirect_japan_impact_score") < 4.0:
        return False
    return True


def _calculate_silence_gap_score(event: ScoredEvent) -> tuple[float, str]:
    """設計書 Section 5.2 軸1 の式に従う。"""
    en = _sources_en_count(event)
    jp = _sources_jp_count(event)
    ga = _axis_score(event, "global_attention_score")
    ijai = _axis_score(event, "indirect_japan_impact_score")
    raw = (en * 1.5) + ga - (jp * 5.0) + ijai
    score = _clamp(raw)
    reasoning = (
        f"sources_en={en}, sources_jp={jp}, "
        f"global_attention={ga:.1f}, indirect_japan_impact={ijai:.1f} → score={score:.2f}"
    )
    return score, reasoning


# ---------- 軸2: Framing Inversion ----------

def _meets_framing_inversion_conditions(event: ScoredEvent) -> bool:
    """成立条件: sources_jp >= 1 AND sources_en >= 2 AND perspective_gap_score >= 6.0。
    主体・述語の差異判定は LLM の役割（Step 3）に委ねる。
    """
    if _sources_jp_count(event) < 1:
        return False
    if _sources_en_count(event) < 2:
        return False
    if _axis_score(event, "perspective_gap_score") < 6.0:
        return False
    return True


def _calculate_framing_inversion_score(event: ScoredEvent) -> tuple[float, str]:
    """設計書 Section 5.2 軸2 の式に従う（framing_divergence_bonus は LLM 判定後の加点なので未加算）。"""
    pg = _axis_score(event, "perspective_gap_score")
    en = _sources_en_count(event)
    raw = pg + (en * 0.5)
    score = _clamp(raw)
    reasoning = (
        f"perspective_gap={pg:.1f}, sources_en={en} → score={score:.2f} "
        f"(LLM 判定で framing_divergence_bonus +2 が乗る可能性あり)"
    )
    return score, reasoning


# ---------- 軸3: Hidden Stakes ----------

# 日本企業・産業を示す軽量キーワード（ASCII / 日本語）
_JAPAN_INDUSTRY_KEYWORDS = [
    "Toyota", "Honda", "Nissan", "Sony", "Panasonic", "Hitachi",
    "Mitsubishi", "Sumitomo", "Mitsui", "Marubeni", "Itochu",
    "TDK", "Renesas", "Murata", "Kioxia", "Tokyo Electron",
    "Nippon Steel", "JFE", "Asahi Kasei", "Shin-Etsu",
    "Nintendo", "SoftBank",
    "トヨタ", "ホンダ", "日産", "ソニー", "三菱", "住友", "三井",
    "日立", "パナソニック", "任天堂", "ソフトバンク",
    "半導体", "自動車", "素材", "商社", "電機", "鉄鋼",
    "yen", "円安", "円高",
]


def _japan_industry_keyword_count(event: ScoredEvent) -> int:
    """title/summary/tags 等から日本企業・産業キーワードの出現数を数える。"""
    parts: list[str] = []
    ev = event.event
    if ev.title:
        parts.append(ev.title)
    if ev.summary:
        parts.append(ev.summary)
    if ev.background:
        parts.append(ev.background)
    if ev.impact_on_japan:
        parts.append(ev.impact_on_japan)
    if ev.tags:
        parts.extend(ev.tags)
    if event.tags_multi:
        parts.extend(event.tags_multi)
    haystack = " ".join(parts)
    haystack_lower = haystack.lower()
    count = 0
    seen: set[str] = set()
    for kw in _JAPAN_INDUSTRY_KEYWORDS:
        if kw in seen:
            continue
        if kw.isascii():
            if kw.lower() in haystack_lower:
                count += 1
                seen.add(kw)
        else:
            if kw in haystack:
                count += 1
                seen.add(kw)
    return count


def _impact_unmentioned_in_jp(event: ScoredEvent) -> bool:
    """日本ソースが存在し、かつ impact_on_japan / japan_view が未記入なら True。

    日本ソースが 1 件もない場合は「未言及」とは言えない（そもそも報道がない）ので False。
    """
    if _sources_jp_count(event) < 1:
        return False
    ev = event.event
    return not (ev.impact_on_japan or ev.japan_view)


def _meets_hidden_stakes_conditions(event: ScoredEvent) -> bool:
    """成立条件: indirect_japan_impact_score >= 5.0 AND 日本企業/業界キーワードあり。"""
    if _axis_score(event, "indirect_japan_impact_score") < 5.0:
        return False
    if _japan_industry_keyword_count(event) < 1:
        return False
    return True


def _calculate_hidden_stakes_score(event: ScoredEvent) -> tuple[float, str]:
    """設計書 Section 5.2 軸3 の式に従う。"""
    ijai = _axis_score(event, "indirect_japan_impact_score")
    kw_count = _japan_industry_keyword_count(event)
    bonus = 2.0 if _impact_unmentioned_in_jp(event) else 0.0
    raw = ijai + kw_count + bonus
    score = _clamp(raw)
    reasoning = (
        f"indirect_japan_impact={ijai:.1f}, japan_industry_keywords={kw_count}, "
        f"impact_unmentioned_bonus={bonus:.1f} → score={score:.2f}"
    )
    return score, reasoning


# ---------- 軸4: Cultural Blindspot ----------

# 文化・社会・制度系のシグナル（軽量仮実装）
_CULTURAL_SIGNAL_KEYWORDS = [
    "religion", "religious", "tradition", "ritual", "caste",
    "gender", "feminism", "monarchy", "royal", "ramadan",
    "halal", "kosher", "diaspora", "indigenous", "sharia",
    "宗教", "伝統", "王室", "王族", "民族", "カースト", "ジェンダー",
    "難民", "イスラム", "ヒンドゥー", "仏教", "儒教",
]


def _cultural_uniqueness_score(event: ScoredEvent) -> float:
    """軽量な仮実装: 文化系キーワードと editorial_tags から 0〜10 のスコアを算出。

    cultural_uniqueness_score は既存スコアリングに存在しないため、後で
    LLM 判定や辞書拡張で改善する前提のフォールバック実装。
    """
    parts: list[str] = []
    ev = event.event
    if ev.title:
        parts.append(ev.title)
    if ev.summary:
        parts.append(ev.summary)
    if ev.background:
        parts.append(ev.background)
    if ev.tags:
        parts.extend(ev.tags)
    if event.tags_multi:
        parts.extend(event.tags_multi)
    if event.editorial_tags:
        parts.extend(event.editorial_tags)
    haystack = " ".join(parts)
    haystack_lower = haystack.lower()
    matches = 0
    for kw in _CULTURAL_SIGNAL_KEYWORDS:
        if kw.isascii():
            if kw.lower() in haystack_lower:
                matches += 1
        elif kw in haystack:
            matches += 1
    # geopolitics_depth_score を文化軸の補助指標として使う（軽い加点）。
    gd = _axis_score(event, "geopolitics_depth_score")
    raw = matches * 1.5 + (gd * 0.3)
    return _clamp(raw)


def _meets_cultural_blindspot_conditions(event: ScoredEvent) -> bool:
    """成立条件（仮実装）: 文化系シグナルが 1 つ以上 AND uniqueness >= 3.0。"""
    if _cultural_uniqueness_score(event) < 3.0:
        return False
    return True


def _calculate_cultural_blindspot_score(event: ScoredEvent) -> tuple[float, str]:
    """設計書 Section 5.2 軸4 の式に従う（uniqueness のみで近似）。"""
    cu = _cultural_uniqueness_score(event)
    score = _clamp(cu)
    reasoning = (
        f"cultural_uniqueness(仮)={cu:.2f} → score={score:.2f} "
        f"(LLM 判定で違和感度の加点が乗る可能性あり)"
    )
    return score, reasoning


# ---------- ディスパッチ ----------

_AXIS_HANDLERS = {
    "silence_gap": (_meets_silence_gap_conditions, _calculate_silence_gap_score),
    "framing_inversion": (
        _meets_framing_inversion_conditions,
        _calculate_framing_inversion_score,
    ),
    "hidden_stakes": (_meets_hidden_stakes_conditions, _calculate_hidden_stakes_score),
    "cultural_blindspot": (
        _meets_cultural_blindspot_conditions,
        _calculate_cultural_blindspot_score,
    ),
}


def extract_perspectives(
    scored_event: ScoredEvent,
    channel_config: Optional[ChannelConfig] = None,
) -> list[PerspectiveCandidate]:
    """4 軸のスコアと成立条件を計算し、PerspectiveCandidate のリストを返す。

    channel_config が与えられた場合は perspective_axes に含まれる軸のみを返す。
    成立条件を満たさない軸は除外する。
    """
    allowed_axes: Optional[set[str]] = None
    if channel_config is not None:
        allowed_axes = set(channel_config.perspective_axes or [])

    out: list[PerspectiveCandidate] = []
    for axis, (meets_fn, score_fn) in _AXIS_HANDLERS.items():
        if allowed_axes is not None and axis not in allowed_axes:
            continue
        if not meets_fn(scored_event):
            continue
        score, reasoning = score_fn(scored_event)
        out.append(
            PerspectiveCandidate(
                axis=axis,
                score=score,
                reasoning=reasoning,
                evidence_refs=_collect_evidence_refs(scored_event, axis),
            )
        )
    # スコア降順に整列して返す（呼び出し側で Top3 を取る）
    out.sort(key=lambda c: c.score, reverse=True)
    return out
