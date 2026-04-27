"""観点軸 4 種の抽出（silence_gap / hidden_stakes / cultural_blindspot は
ルールベース、framing_inversion のみ LLM ベース）。

4 軸の意味（混同注意）:
    - silence_gap         : 日本側の報道「量・露出」が薄い（情報量で判定）
    - framing_inversion   : 同一事象に対する「論調・評価方向」の差（LLM 判定）
    - hidden_stakes       : 日本にとっての「隠れた利害」がある（直接影響は薄いが波及大）
    - cultural_blindspot  : 西側視点と非西側視点の差（地域偏向で判定）

ルールベース 3 軸は score_breakdown + sources_by_locale を参照する。
framing_inversion は「論調・皮肉・暗喩」の文脈解釈をルールでは判定困難なため、
configs/prompts/analysis/geo_lens/framing_inversion_classifier.md を用いた
LLM 判定に委ねる（Tier1 軽量モデル想定 / フェイルセーフは False 返却）。

ChannelConfig.perspective_axes に含まれない軸は最終フィルタで除外する。
"""
from __future__ import annotations

import json
from typing import Optional

from src.analysis._json_utils import parse_json_response
from src.analysis.prompt_loader import load_prompt
from src.llm.factory import get_analysis_llm_client
from src.shared.logger import get_logger
from src.shared.models import ChannelConfig, PerspectiveCandidate, ScoredEvent
from src.triage.scoring import _INDIRECT_JAPAN_IMPACT_KW

logger = get_logger(__name__)


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


# ---------- 軸2: Framing Inversion (LLM ベース) ----------
#
# 「論調・皮肉・暗喩」の解釈はルールベースでは破綻するため、
# 上位観点候補に絞った上で LLM (Tier1 軽量モデル) に委ねる。
# プロンプトは configs/prompts/analysis/geo_lens/framing_inversion_classifier.md。
#
# _meets / _calculate の二段呼び出しで LLM 二重発火しないよう、
# event.id をキーとした内部キャッシュ _FRAMING_RESULTS で分類結果を共有する。

# 1 ソースあたり title を最大何文字まで載せるか（LLM コンテキスト節約）
_FRAMING_SOURCE_TEXT_MAX_LEN = 500
# プロンプトに載せる片側最大ソース数（観点抽出は上位候補のみ対象なので過剰列挙は不要）
_FRAMING_SOURCE_MAX_COUNT = 5
# LLM 判定結果の event.id ベースキャッシュ。_meets で書き込み、_calculate で読み出す。
# 観点抽出は event ごとに 1 回のみ走る前提（CLAUDE.md / instructions より）。
_FRAMING_RESULTS: dict[str, Optional[dict]] = {}
# is_inversion=True 時の信頼度に応じたスコア表（_calculate のスコア決定で使用）。
_FRAMING_SCORE_BY_CONFIDENCE = {"high": 9.0, "medium": 7.0}
_FRAMING_DEFAULT_SCORE = 5.0


def _format_framing_source_block(event: ScoredEvent, japan_side: bool) -> str:
    """日本側 / 海外側のソース群を LLM プロンプト用にテキスト整形する。

    - 各ソースは title をそのまま採用（500 字でカット）し、name とともに 1 行で出力。
    - 上位 _FRAMING_SOURCE_MAX_COUNT 件まで。
    - 該当ソースが空の場合は "(該当なし)" を返す。
    """
    ev = event.event
    sources: list = []
    if ev.sources_by_locale:
        for region, refs in ev.sources_by_locale.items():
            if japan_side and region == "japan":
                sources.extend(refs)
            elif not japan_side and region != "japan":
                sources.extend(refs)
    else:
        sources = list(ev.sources_jp if japan_side else ev.sources_en)

    if not sources:
        return "(該当なし)"

    lines: list[str] = []
    for s in sources[:_FRAMING_SOURCE_MAX_COUNT]:
        title = (s.title or "").strip()
        if len(title) > _FRAMING_SOURCE_TEXT_MAX_LEN:
            title = title[:_FRAMING_SOURCE_TEXT_MAX_LEN].rstrip() + "…"
        if not title:
            title = "(タイトル不明)"
        lines.append(f"- [{s.name}] {title}")

    # 補助情報として日本側は japan_view、海外側は global_view を末尾に添える。
    extra = ev.japan_view if japan_side else ev.global_view
    if extra:
        snippet = extra.strip()
        if len(snippet) > _FRAMING_SOURCE_TEXT_MAX_LEN:
            snippet = snippet[:_FRAMING_SOURCE_TEXT_MAX_LEN].rstrip() + "…"
        lines.append(f"  ({'JP' if japan_side else 'GLOBAL'} view: {snippet})")

    return "\n".join(lines)


def _build_framing_inversion_prompt(event: ScoredEvent) -> str:
    """framing_inversion_classifier.md を読み込み、テンプレ変数を埋める。"""
    template = load_prompt("geo_lens", "framing_inversion_classifier")
    jp_count = _sources_jp_count(event)
    en_count = _sources_en_count(event)
    return template.format(
        jp_count=jp_count,
        en_count=en_count,
        jp_sources=_format_framing_source_block(event, japan_side=True),
        en_sources=_format_framing_source_block(event, japan_side=False),
    )


def _run_framing_inversion_classifier(event: ScoredEvent) -> Optional[dict]:
    """LLM を呼び出して論調逆転判定を返す。

    - 早期リターン: jp_count==0 / en_count==0 / sources_total<2 → None
    - LLM 未取得 / 例外 / JSON パース失敗 → None（フェイルセーフ）
    - 成功時はパース済み dict を返す。
    結果は event.id キーで _FRAMING_RESULTS にキャッシュされる
    （_meets と _calculate での二重呼び出し防止）。
    """
    cache_key = event.event.id
    if cache_key in _FRAMING_RESULTS:
        return _FRAMING_RESULTS[cache_key]

    jp_count = _sources_jp_count(event)
    en_count = _sources_en_count(event)
    if jp_count == 0 or en_count == 0 or (jp_count + en_count) < 2:
        _FRAMING_RESULTS[cache_key] = None
        return None

    client = get_analysis_llm_client()
    if client is None:
        logger.warning(
            "[FramingInversion] analysis LLM client unavailable for event=%s "
            "(GEMINI_API_KEY 未設定か、provider 未対応)。判定をスキップ (False)。",
            cache_key,
        )
        _FRAMING_RESULTS[cache_key] = None
        return None

    try:
        prompt = _build_framing_inversion_prompt(event)
        raw = client.generate(prompt)
    except Exception as exc:
        logger.warning(
            "[FramingInversion] LLM 呼び出し失敗 event=%s: %s → 不成立として扱う。",
            cache_key,
            exc,
        )
        _FRAMING_RESULTS[cache_key] = None
        return None

    try:
        parsed = parse_json_response(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "[FramingInversion] LLM 応答 JSON パース失敗 event=%s: %s → 不成立。raw=%r",
            cache_key,
            exc,
            raw[:200] if isinstance(raw, str) else raw,
        )
        _FRAMING_RESULTS[cache_key] = None
        return None

    if not isinstance(parsed, dict):
        logger.warning(
            "[FramingInversion] LLM 応答が dict でない event=%s: type=%s → 不成立。",
            cache_key,
            type(parsed).__name__,
        )
        _FRAMING_RESULTS[cache_key] = None
        return None

    _FRAMING_RESULTS[cache_key] = parsed
    return parsed


def _meets_framing_inversion_conditions(event: ScoredEvent) -> bool:
    """LLM ベース判定: is_inversion=True かつ confidence != "low" のときのみ成立。

    早期リターン (LLM 呼び出し前):
        - jp_count == 0 / en_count == 0 / sources_total < 2
    LLM 失敗・例外・パース不能・confidence=low はすべて False（フェイルセーフ）。
    """
    result = _run_framing_inversion_classifier(event)
    if result is None:
        return False

    confidence = str(result.get("confidence", "")).strip().lower()
    if confidence == "low":
        return False

    return bool(result.get("is_inversion") is True)


def _calculate_framing_inversion_score(event: ScoredEvent) -> tuple[float, str]:
    """LLM 判定の confidence に応じてスコアを返す。

    結果は _meets で書き込まれた _FRAMING_RESULTS を再利用する（LLM 二重呼び出し防止）。
    キャッシュ未設定（_meets を経由せずに直接呼ばれた場合）は再度 LLM を呼ぶ。
    """
    result = _run_framing_inversion_classifier(event)
    if result is None:
        # _meets と整合（_meets が False を返した直後は基本ここに来ない）。
        return 0.0, "framing_inversion: LLM 判定不能 → score=0.0"

    confidence = str(result.get("confidence", "")).strip().lower()
    score = _FRAMING_SCORE_BY_CONFIDENCE.get(confidence, _FRAMING_DEFAULT_SCORE)
    score = _clamp(score)

    jp_framing = result.get("jp_framing", "?")
    en_framing = result.get("en_framing", "?")
    meaning = (result.get("inversion_meaning") or "").strip()
    meaning_excerpt = meaning[:60] + ("…" if len(meaning) > 60 else "")
    reasoning = (
        f"LLM framing_inversion: jp={jp_framing} vs en={en_framing}, "
        f"confidence={confidence or '?'} → score={score:.2f}"
        + (f" / meaning: {meaning_excerpt}" if meaning_excerpt else "")
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


# ---------- why_now 生成 ----------
#
# why_now は「なぜ今このニュースを日本人視聴者にとって重要なのか」を 1〜2 文で
# 持つ観点候補必須フィールド。台本生成側 (Twist セクション等) が「日本人視聴者に
# とっての意味」を構造化して引けるようにするため、軸ごとに event 固有情報
# (title / ijai / sources 件数等) を反映させる。
#
# LLM 呼び出しは行わない（高速・決定的を優先）。textual specificity は
# 「event.title / summary をそのまま why_now の中に取り込む」ことで担保する
# (test_why_now_reflects_event_specifics は why_now にメキシコ・原油等の
# event 固有キーワードが含まれることを検査する)。

_TOPIC_PHRASE_MAX_LEN = 80


def _topic_phrase(event: ScoredEvent) -> str:
    """why_now 文に埋め込むトピックフレーズ。

    title 優先、無ければ summary の冒頭、いずれも無ければ id。
    タイトルが長すぎる場合は文字単位で切り詰めるが、80 字程度なら
    実データのほぼ全件を切らずに済む。
    """
    ev = event.event
    base = (ev.title or "").strip()
    if not base:
        base = (ev.summary or "").strip().splitlines()[0] if ev.summary else ""
    if not base:
        base = ev.id
    if len(base) > _TOPIC_PHRASE_MAX_LEN:
        base = base[:_TOPIC_PHRASE_MAX_LEN].rstrip() + "…"
    return base


def _build_why_now(event: ScoredEvent, axis: str) -> str:
    """軸ごとに event 固有情報を織り込んだ why_now 文を生成する。

    - silence_gap: 海外/日本の報道量差をベースに認知ギャップを訴求。
    - framing_inversion: 論調逆転を「判断が変わる転換点」として訴求。
    - hidden_stakes: ijai を構造的影響度として明示し、見落とされやすい論点として訴求。
    - cultural_blindspot: 西側フレームでは捉えきれない論点として訴求。

    どの分岐でも `_topic_phrase(event)` を本文に取り込むため、event 固有の
    キーワード (人名・地名・産業) が必ず why_now に含まれる。
    """
    topic = _topic_phrase(event)
    ijai = _axis_score(event, "indirect_japan_impact_score")
    ga = _axis_score(event, "global_attention_score")
    en = _sources_en_count(event)
    jp = _sources_jp_count(event)

    if axis == "silence_gap":
        return (
            f"「{topic}」は海外で {en} 媒体が報じる一方、日本側の報道量は "
            f"{jp} 媒体に留まる。視聴者の認知ギャップが大きく、"
            f"世界では既に常識化している論点を埋める意味がある。"
        )
    if axis == "framing_inversion":
        return (
            f"「{topic}」をめぐり、日本と海外で評価軸が逆転している。"
            f"どちらの解釈を採るかで日本人視聴者の判断が大きく変わる転換点。"
        )
    if axis == "hidden_stakes":
        if ijai >= _HIDDEN_STAKES_IJAI_STRONG:
            return (
                f"「{topic}」は一見日本に直接関係ないように見えるが、"
                f"日本への間接インパクト ({ijai:.1f}/10) が高く、"
                f"エネルギー・サプライチェーン・通商経路に及ぶ構造的転換点を含む。"
            )
        return (
            f"「{topic}」が日本のサプライチェーン・通商・産業に及ぼす連鎖は、"
            f"国内では十分に議論されていない。間接インパクト {ijai:.1f}/10。"
        )
    if axis == "cultural_blindspot":
        return (
            f"「{topic}」は西側の常識からはずれた文脈で起きており、"
            f"日本の主流メディアが採用する西側フレームでは捉えきれない論点。"
        )
    # 万一未知の軸が来た場合の保険
    return (
        f"「{topic}」を世界視点から再解釈する意味がある "
        f"(ga={ga:.1f}, ijai={ijai:.1f})。"
    )


# ---------- 軸ごとの候補ビルダー ----------
#
# 「成立判定」と「スコア計算」と「PerspectiveCandidate への組み立て」を分離する
# (旧 _AXIS_HANDLERS の dict-driven dispatch を、explicit builder に置き換える)。
# why_now / evidence_refs を必ず埋める運用をビルダー側で担保する。


def _build_silence_gap_candidate(event: ScoredEvent) -> PerspectiveCandidate:
    score, reasoning = _calculate_silence_gap_score(event)
    return PerspectiveCandidate(
        axis="silence_gap",
        score=score,
        reasoning=reasoning,
        evidence_refs=_collect_evidence_refs(event, "silence_gap"),
        why_now=_build_why_now(event, "silence_gap"),
    )


def _build_framing_inversion_candidate(event: ScoredEvent) -> PerspectiveCandidate:
    score, reasoning = _calculate_framing_inversion_score(event)
    return PerspectiveCandidate(
        axis="framing_inversion",
        score=score,
        reasoning=reasoning,
        evidence_refs=_collect_evidence_refs(event, "framing_inversion"),
        why_now=_build_why_now(event, "framing_inversion"),
    )


def _build_hidden_stakes_candidate(event: ScoredEvent) -> PerspectiveCandidate:
    score, reasoning = _calculate_hidden_stakes_score(event)
    return PerspectiveCandidate(
        axis="hidden_stakes",
        score=score,
        reasoning=reasoning,
        evidence_refs=_collect_evidence_refs(event, "hidden_stakes"),
        why_now=_build_why_now(event, "hidden_stakes"),
    )


def _build_cultural_blindspot_candidate(event: ScoredEvent) -> PerspectiveCandidate:
    score, reasoning = _calculate_cultural_blindspot_score(event)
    return PerspectiveCandidate(
        axis="cultural_blindspot",
        score=score,
        reasoning=reasoning,
        evidence_refs=_collect_evidence_refs(event, "cultural_blindspot"),
        why_now=_build_why_now(event, "cultural_blindspot"),
    )


# ---------- フォールバック観点 ----------
#
# 4 軸全部不成立だが「最低品質ゲート」を通過したイベントは、Hydrangea の
# 「世界視点で日本ニュースを再解釈する」コンセプトに照らして動画生成パスに
# 乗せたい。フォールバックは hidden_stakes 軸として登録する (最も汎用的な
# 「日本にとっての意味」軸)。
#
# 最低品質ゲート:
#   - sources_total (jp + en) >= 2: 単一ソースのイベントは検証性が低すぎる
#   - title または summary のいずれかが非空: 観点を語るためのテキスト要件
#
# フォールバックの score は 0〜5 の範囲に抑える (本道の 4 軸が成立した
# イベントより常に下位に来るよう保守的に設定)。

_FALLBACK_MIN_SOURCES_TOTAL = 2
_FALLBACK_SCORE_MAX = 5.0


def _build_fallback_perspective(event: ScoredEvent) -> Optional[PerspectiveCandidate]:
    """4 軸全部不成立時のフォールバック観点。

    最低品質ゲート未通過の場合は None を返す。呼び出し側はその場合
    空リストを返すことで「分析レイヤースキップ」相当の挙動になる。
    """
    en = _sources_en_count(event)
    jp = _sources_jp_count(event)
    sources_total = en + jp
    if sources_total < _FALLBACK_MIN_SOURCES_TOTAL:
        return None

    ev = event.event
    if not (ev.title or ev.summary):
        return None

    ijai = _axis_score(event, "indirect_japan_impact_score")
    ga = _axis_score(event, "global_attention_score")

    raw = ijai * 0.5 + ga * 0.3
    score = _clamp(raw, lo=0.0, hi=_FALLBACK_SCORE_MAX)

    topic = _topic_phrase(event)
    metric_parts = [f"間接インパクト {ijai:.1f}/10", f"海外関心度 {ga:.1f}/10"]
    metric_str = "、".join(metric_parts)
    why_now = (
        f"「{topic}」は 4 軸の典型成立条件には乗らないが、"
        f"({metric_str}; 海外 {en} 件 / 日本 {jp} 件) の構成で日本人視聴者にとっての"
        f"隠れた利害を世界視点から再解釈する余地がある。"
    )

    reasoning = (
        f"fallback (4軸全部不成立だが品質ゲート通過): sources_total={sources_total}, "
        f"ijai={ijai:.1f}, ga={ga:.1f} → score={score:.2f}"
    )

    return PerspectiveCandidate(
        axis="hidden_stakes",
        score=score,
        reasoning=reasoning,
        evidence_refs=_collect_evidence_refs(event, "hidden_stakes"),
        why_now=why_now,
    )


# ---------- ディスパッチ ----------


def extract_perspectives(
    scored_event: ScoredEvent,
    channel_config: Optional[ChannelConfig] = None,
) -> list[PerspectiveCandidate]:
    """4 軸のスコアと成立条件を計算し、PerspectiveCandidate のリストを返す。

    channel_config が与えられた場合は perspective_axes に含まれる軸のみを返す。
    4 軸全部不成立の場合は最低品質ゲート (sources_total >= 2) を通過したイベント
    に限ってフォールバック観点 (hidden_stakes 軸) を 1 件返す。
    品質ゲート未通過なら空リスト。
    """
    allowed_axes: Optional[set[str]] = None
    if channel_config is not None:
        allowed_axes = set(channel_config.perspective_axes or [])

    def _allowed(axis: str) -> bool:
        return allowed_axes is None or axis in allowed_axes

    candidates: list[PerspectiveCandidate] = []

    if _allowed("silence_gap") and _meets_silence_gap_conditions(scored_event):
        candidates.append(_build_silence_gap_candidate(scored_event))
    if _allowed("framing_inversion") and _meets_framing_inversion_conditions(scored_event):
        candidates.append(_build_framing_inversion_candidate(scored_event))
    if _allowed("hidden_stakes") and _meets_hidden_stakes_conditions(scored_event):
        candidates.append(_build_hidden_stakes_candidate(scored_event))
    if _allowed("cultural_blindspot") and _meets_cultural_blindspot_conditions(scored_event):
        candidates.append(_build_cultural_blindspot_candidate(scored_event))

    if candidates:
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    # フォールバック観点 (hidden_stakes 軸)。
    # チャンネル設定が hidden_stakes を許可していなければフォールバックも発動しない。
    if not _allowed("hidden_stakes"):
        return []

    fallback = _build_fallback_perspective(scored_event)
    if fallback is None:
        return []

    logger.info(
        "[PerspectiveExtractor] fallback perspective triggered for "
        "event=%s: 4軸全部不成立だが品質ゲート通過 → axis=%s, score=%.2f",
        scored_event.event.id,
        fallback.axis,
        fallback.score,
    )
    return [fallback]
