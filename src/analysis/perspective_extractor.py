"""観点軸 4 種のルールベース抽出。

設計書 Section 5 の仕様をベースとしつつ、Phase 1 の実 LLM 試運転で
「観点が 1 つも成立せず分析レイヤーがスキップされる」事故が発生したため、
silence_gap / hidden_stakes / cultural_blindspot を「失敗しない作り」に再設計する
（framing_inversion は別バッチで LLM ベース化するため本ファイルでは旧実装のまま）。

4 軸の意味（混同注意）:
    - silence_gap         : 日本側の報道「量・露出」が薄い（情報量で判定）
    - framing_inversion   : 同一事象に対する「論調・評価方向」の差（LLM 判定に委ねる）
    - hidden_stakes       : 日本にとっての「隠れた利害」がある（直接影響は薄いが波及大）
    - cultural_blindspot  : 西側視点と非西側視点の差（地域偏向で判定）

スコアと成立条件は既存の score_breakdown フィールド + sources_by_locale を参照する。
ChannelConfig.perspective_axes に含まれない軸は最終フィルタで除外する。
"""
from __future__ import annotations

from typing import Optional

from src.shared.models import ChannelConfig, PerspectiveCandidate, ScoredEvent
from src.triage.scoring import _INDIRECT_JAPAN_IMPACT_KW


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


def _jp_text_volume(event: ScoredEvent) -> int:
    """日本側の情報量プロキシ: japan_view 文字数 + 日本ソースの title 文字数合計。

    SourceRef は本文を保持しないため、各ソースに紐付く title 長を加算する。
    日本語は 1 文字で 2 バイト程度の情報量を持つが、桁オーダー比較には
    生の文字数で十分（厳密な対称性は不要）。
    """
    ev = event.event
    total = len(ev.japan_view or "")
    if ev.sources_by_locale and "japan" in ev.sources_by_locale:
        for s in ev.sources_by_locale["japan"]:
            total += len(s.title or "")
    else:
        for s in ev.sources_jp:
            total += len(s.title or "")
    return total


def _en_text_volume(event: ScoredEvent) -> int:
    """海外側の情報量プロキシ: global_view 文字数 + 海外ソースの title 文字数合計。"""
    ev = event.event
    total = len(ev.global_view or "")
    if ev.sources_by_locale:
        for region, refs in ev.sources_by_locale.items():
            if region == "japan":
                continue
            for s in refs:
                total += len(s.title or "")
    else:
        for s in ev.sources_en:
            total += len(s.title or "")
    return total


# ---------- 軸1: Silence Gap ----------

# 「日本側の報道量・露出が薄い」の数値判定で使う閾値群。
# 設計書 v1.1 の絶対条件 (en >= 3 AND jp == 0 AND ga >= 6.0 AND ijai >= 4.0) は
# 厳しすぎて jp >= 1 の事例を全滅させていたため、複数条件の OR で柔軟化する。
_SILENCE_GAP_MIN_EN_SOURCES = 2          # 海外ソースの最小件数（旧 3 → 2 に緩和）
_SILENCE_GAP_INTEREST_GA_THRESHOLD = 4.0  # global_attention の関心度フィルタ
_SILENCE_GAP_INTEREST_IJAI_THRESHOLD = 4.0  # indirect_japan_impact の関心度フィルタ
_SILENCE_GAP_RATIO_DENOMINATOR = 2       # jp:en 比 1:2 以上の差で「量的差」とみなす
_SILENCE_GAP_TEXT_RATIO_DENOMINATOR = 2  # jp_wc:en_wc 比 1:2 以上の差で「情報量差」


def _silence_gap_is_topic_interesting(event: ScoredEvent) -> bool:
    """global_attention OR indirect_japan_impact が一定以上 → 注目価値ありと判定。

    OR にする理由: 海外で大注目 (ga 高) でも ijai が低いケース、逆に ga が
    そこまでなくても日本影響大 (ijai 高) のケース、どちらも silence_gap として
    意味があるため。AND だと両方高い珍しい組み合わせしか拾えない。
    """
    ga = _axis_score(event, "global_attention_score")
    ijai = _axis_score(event, "indirect_japan_impact_score")
    return ga >= _SILENCE_GAP_INTEREST_GA_THRESHOLD or ijai >= _SILENCE_GAP_INTEREST_IJAI_THRESHOLD


def _meets_silence_gap_conditions(event: ScoredEvent) -> bool:
    """成立条件: 以下のいずれか (OR) を満たし、かつ注目価値フィルタを通過。

    1) 日本ソース不在パターン:
       sources_jp == 0 AND sources_en >= 2
    2) 件数比パターン:
       sources_en >= 2 AND sources_jp が海外件数の半分以下 (jp*2 <= en)
    3) 情報量比パターン:
       sources_en >= 2 AND jp_text_volume*2 <= en_text_volume （日本側テキスト量が半分未満）
    """
    if not _silence_gap_is_topic_interesting(event):
        return False

    en = _sources_en_count(event)
    jp = _sources_jp_count(event)

    if en < _SILENCE_GAP_MIN_EN_SOURCES:
        return False

    # 1) 日本ソース不在
    if jp == 0:
        return True

    # 2) 件数比が極端
    if jp * _SILENCE_GAP_RATIO_DENOMINATOR <= en:
        return True

    # 3) 情報量比が極端
    jp_wc = _jp_text_volume(event)
    en_wc = _en_text_volume(event)
    if en_wc > 0 and jp_wc * _SILENCE_GAP_TEXT_RATIO_DENOMINATOR <= en_wc:
        return True

    return False


def _calculate_silence_gap_score(event: ScoredEvent) -> tuple[float, str]:
    """設計書 Section 5.2 軸1 の式に従う（jp_count ペナルティは既存テスト互換のため維持）。"""
    en = _sources_en_count(event)
    jp = _sources_jp_count(event)
    ga = _axis_score(event, "global_attention_score")
    ijai = _axis_score(event, "indirect_japan_impact_score")
    raw = (en * 1.5) + ga - (jp * 5.0) + ijai
    score = _clamp(raw)
    jp_wc = _jp_text_volume(event)
    en_wc = _en_text_volume(event)
    reasoning = (
        f"sources_en={en}, sources_jp={jp}, "
        f"global_attention={ga:.1f}, indirect_japan_impact={ijai:.1f}, "
        f"jp_text_volume={jp_wc}, en_text_volume={en_wc} → score={score:.2f}"
    )
    return score, reasoning


# ---------- 軸2: Framing Inversion ----------
#
# 本軸は別バッチで LLM ベース化予定のため、既存実装をそのまま維持する。

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

# hidden_stakes の数値判定で使う閾値群。
# 旧実装は ijai >= 5.0 AND japan_industry_kw >= 1 の AND だったため、
# ijai が極めて高い (例: メキシコ原油 ijai=9.0) ケースでも企業名キーワードが
# なければ落ちる構造的欠陥があった。本実装は段階的閾値に置き換える:
#   - ijai が顕著 (>= STRONG): 単独で成立
#   - ijai が中程度 (>= MID): 企業キーワード or 間接影響キーワードのいずれかと合わせて成立
#   - ijai が低い (< MIN): 問答無用で不成立
_HIDDEN_STAKES_IJAI_STRONG = 7.0  # この値以上は ijai 単独で成立
_HIDDEN_STAKES_IJAI_MID = 4.0     # この値以上 + 補助シグナルで成立
_HIDDEN_STAKES_IJAI_MIN = 3.0     # この値未満は問答無用で不成立


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


def _has_indirect_japan_impact_keyword(event: ScoredEvent) -> bool:
    """scoring.py の _INDIRECT_JAPAN_IMPACT_KW のいずれかが title/summary/global_view に
    出現するか。日本影響を示す間接キーワード（エネルギー・サプライチェーン・為替等）
    の存在を補助シグナルとして使う。
    """
    ev = event.event
    parts: list[str] = []
    if ev.title:
        parts.append(ev.title.lower())
    if ev.summary:
        parts.append(ev.summary.lower())
    if ev.global_view:
        parts.append(ev.global_view.lower())
    haystack = " ".join(parts)
    if not haystack:
        return False
    for kw, _ in _INDIRECT_JAPAN_IMPACT_KW:
        if kw in haystack:
            return True
    return False


def _impact_unmentioned_in_jp(event: ScoredEvent) -> bool:
    """日本ソースが存在し、かつ impact_on_japan / japan_view が未記入なら True。

    日本ソースが 1 件もない場合は「未言及」とは言えない（そもそも報道がない）ので False。
    """
    if _sources_jp_count(event) < 1:
        return False
    ev = event.event
    return not (ev.impact_on_japan or ev.japan_view)


def _meets_hidden_stakes_conditions(event: ScoredEvent) -> bool:
    """成立条件 (段階的):

    1) ijai >= 7.0 (STRONG): 単独で成立。間接影響スコアが顕著であれば、
       企業名キーワードがなくても日本にとっての利害は成立する。
       メキシコ → 日本原油輸出 (ijai=9.0) のような事例を救済する。
    2) ijai >= 4.0 (MID) AND (japan_industry_kw >= 1 OR indirect_jp_kw 一致):
       中程度の ijai に補助シグナル（企業名 or エネルギー/サプライチェーン語彙）が
       揃えば成立。
    3) ijai < 3.0 (MIN): 問答無用で不成立（騒音抑制）。
    """
    ijai = _axis_score(event, "indirect_japan_impact_score")
    if ijai < _HIDDEN_STAKES_IJAI_MIN:
        return False
    if ijai >= _HIDDEN_STAKES_IJAI_STRONG:
        return True
    if ijai >= _HIDDEN_STAKES_IJAI_MID:
        if _japan_industry_keyword_count(event) >= 1:
            return True
        if _has_indirect_japan_impact_keyword(event):
            return True
    return False


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

# 「西側視点と非西側視点の差」を判定するための region/source ホワイトリスト。
# scoring.py の _NON_WESTERN_REGIONS と整合させる:
#   middle_east / east_asia / global_south
# global_south には latin_america / africa / south_asia 系媒体が入る
# (configs/source_profiles.yaml の region 設定に準拠)。
_NON_WESTERN_REGIONS = frozenset({
    "middle_east", "east_asia", "global_south",
})

# 上記 region に属する非西側媒体の白リスト (source_profiles.yaml ベース)。
# region メタデータが正しく載っていれば region 判定で十分だが、
# 古いデータや region 未設定の SourceRef を救済するために名前ベース判定を併用する。
_NON_WESTERN_SOURCE_NAMES = frozenset({
    # middle_east
    "AlJazeera", "ArabNews",
    # east_asia (非日本)
    "SCMP", "GlobalTimes", "Yonhap", "StraitsTimes", "CNA",
    # global_south
    "TimesOfIndia", "FolhaDeSPaulo", "BuenosAiresTimes", "News24",
})

# cultural_blindspot のキーワード経路の閾値（既存挙動維持のため 3.0）
_CULTURAL_UNIQUENESS_KEYWORD_THRESHOLD = 3.0
# region+source 経路成立時に uniqueness に加える bonus
_CULTURAL_NON_WESTERN_BONUS = 2.0


def _has_non_western_region(event: ScoredEvent) -> bool:
    """event の sources_by_locale に非西側 region が含まれるか。"""
    ev = event.event
    if not ev.sources_by_locale:
        return False
    return bool(set(ev.sources_by_locale.keys()) & _NON_WESTERN_REGIONS)


def _has_non_western_source(event: ScoredEvent) -> bool:
    """ソース群に非西側媒体（region or 名前ベース）が 1 つ以上含まれるか。"""
    ev = event.event
    sources = []
    if ev.sources_by_locale:
        for refs in ev.sources_by_locale.values():
            sources.extend(refs)
    else:
        sources.extend(ev.sources_jp)
        sources.extend(ev.sources_en)
    for s in sources:
        if s.region in _NON_WESTERN_REGIONS:
            return True
        if s.name in _NON_WESTERN_SOURCE_NAMES:
            return True
    return False


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
    """成立条件 (OR):

    1) 地域パターン: event regions に non_western 系を含む AND
       sources に非西側媒体 (region or 名前) が 1 つ以上ある。
       → 例: メキシコ原油 (regions={japan, global_south}, sources に
         BuenosAiresTimes / FolhaDeSPaulo) → 成立。
    2) キーワードパターン: 文化系シグナル経路の uniqueness >= 3.0。
       → 後方互換: 旧テスト (Saudi religious tradition 等) を維持する経路。
    """
    if _has_non_western_region(event) and _has_non_western_source(event):
        return True
    if _cultural_uniqueness_score(event) >= _CULTURAL_UNIQUENESS_KEYWORD_THRESHOLD:
        return True
    return False


def _calculate_cultural_blindspot_score(event: ScoredEvent) -> tuple[float, str]:
    """設計書 Section 5.2 軸4 の式に従う（uniqueness + non-western bonus で近似）。"""
    cu = _cultural_uniqueness_score(event)
    bonus = _CULTURAL_NON_WESTERN_BONUS if (
        _has_non_western_region(event) and _has_non_western_source(event)
    ) else 0.0
    score = _clamp(cu + bonus)
    reasoning = (
        f"cultural_uniqueness(仮)={cu:.2f}, non_western_bonus={bonus:.1f} "
        f"→ score={score:.2f} (LLM 判定で違和感度の加点が乗る可能性あり)"
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
