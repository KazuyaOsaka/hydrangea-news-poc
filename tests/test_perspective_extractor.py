"""src/analysis/perspective_extractor.py のテスト。

silence_gap / hidden_stakes / cultural_blindspot の 3 軸はルールベースで
LLM 不要だが、framing_inversion 軸のみ LLM 判定 (Tier1 軽量) に委ねるため、
本ファイルでは `get_analysis_llm_client` を autouse fixture で常時モック化し、
実 LLM への到達を遮断する。各テストは必要に応じてフェイクの返答を上書きする。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pytest

from src.analysis import perspective_extractor as pe
from src.analysis.perspective_extractor import (
    _calculate_cultural_blindspot_score,
    _calculate_framing_inversion_score,
    _calculate_hidden_stakes_score,
    _calculate_silence_gap_score,
    _meets_cultural_blindspot_conditions,
    _meets_framing_inversion_conditions,
    _meets_hidden_stakes_conditions,
    _meets_silence_gap_conditions,
    extract_perspectives,
)
from src.shared.models import (
    ChannelConfig,
    NewsEvent,
    PerspectiveCandidate,
    ScoredEvent,
    SourceRef,
)


# ---------- LLM モック基盤 ----------
#
# framing_inversion は LLM ベースに置き換わったため、各テストの実 LLM 呼び出しを
# 遮断するフィクスチャを autouse で適用する。デフォルトでは
# `get_analysis_llm_client` を None 返却に差し替え、framing_inversion 判定が
# 必ず False (フェイルセーフ) になるようにする。LLM レスポンスの中身を
# 検証したい個別テストは `set_framing_llm` で上書きする。

class _FakeLLMClient:
    """generate(prompt) の戻り値だけ差し替えられる軽量モック。

    - `response` が文字列なら `generate` でその文字列を返す。
    - `response` が Exception インスタンスなら `generate` で raise する。
    - `response` が callable なら呼び出して結果を返す（prompt を渡す）。
    呼び出し履歴は self.calls に prompt 文字列で保存。
    """

    def __init__(self, response):
        self._response = response
        self.calls: list[str] = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        if isinstance(self._response, BaseException):
            raise self._response
        if callable(self._response):
            return self._response(prompt)
        return self._response


@pytest.fixture(autouse=True)
def _reset_framing_inversion_state(monkeypatch):
    """framing_inversion 用の internal cache を毎テスト初期化し、
    `get_analysis_llm_client` を None 返却に差し替えて実 LLM 到達を防ぐ。
    """
    pe._FRAMING_RESULTS.clear()
    monkeypatch.setattr(pe, "get_analysis_llm_client", lambda: None)
    yield
    pe._FRAMING_RESULTS.clear()


def set_framing_llm(monkeypatch, response) -> _FakeLLMClient:
    """framing_inversion 判定で使われる LLM クライアントをモック化する。

    `response` の解釈は `_FakeLLMClient` 参照。返した client を後続で
    呼び出し回数や prompt の検査に使える。
    """
    client = _FakeLLMClient(response)
    monkeypatch.setattr(pe, "get_analysis_llm_client", lambda: client)
    return client


# ---------- helpers ----------

def _en_sources(n: int) -> list[SourceRef]:
    return [
        SourceRef(name=f"S{i}", url=f"https://en.example.com/{i}", region="global")
        for i in range(n)
    ]


def _jp_sources(n: int) -> list[SourceRef]:
    return [
        SourceRef(name=f"J{i}", url=f"https://jp.example.com/{i}", region="japan",
                  language="ja", country="JP")
        for i in range(n)
    ]


def _scored(
    *,
    title: str = "",
    summary: str = "",
    sources_jp: int = 0,
    sources_en: int = 0,
    breakdown: Optional[dict] = None,
    background: Optional[str] = None,
    impact_on_japan: Optional[str] = None,
    japan_view: Optional[str] = None,
    global_view: Optional[str] = None,
    tags: Optional[list[str]] = None,
    editorial_tags: Optional[list[str]] = None,
    sources_by_locale: Optional[dict[str, list[SourceRef]]] = None,
) -> ScoredEvent:
    ev_kwargs: dict = dict(
        id="evt-1",
        title=title,
        summary=summary,
        category="politics",
        source="Reuters",
        published_at=datetime.now(timezone.utc),
        sources_jp=_jp_sources(sources_jp),
        sources_en=_en_sources(sources_en),
        background=background,
        impact_on_japan=impact_on_japan,
        japan_view=japan_view,
        global_view=global_view,
        tags=tags or [],
    )
    if sources_by_locale is not None:
        ev_kwargs["sources_by_locale"] = sources_by_locale
    ev = NewsEvent(**ev_kwargs)
    return ScoredEvent(
        event=ev,
        score=10.0,
        score_breakdown=breakdown or {},
        editorial_tags=editorial_tags or [],
    )


# ---------- silence_gap ----------

def test_silence_gap_meets_when_all_conditions_satisfied():
    se = _scored(
        sources_en=3,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is True


def test_silence_gap_meets_when_jp_count_is_minor_share():
    """新ルール: jp/en 比 1/2 以下なら silence_gap 成立 (jp=1, en=3 → 1*2 ≤ 3)。

    旧ルールでは jp >= 1 で即不成立だったが、本来 silence_gap は
    「日本側の報道量が薄い」を判定する軸であり、"jp が少数でも en が多い"
    なら成立とみなすほうが正しい。
    """
    se = _scored(
        sources_en=3,
        sources_jp=1,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is True


def test_silence_gap_fails_when_jp_share_is_majority():
    """jp が en と同数以上なら「日本側の量が薄い」とは言えない。"""
    se = _scored(
        sources_en=2,
        sources_jp=3,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is False


def test_silence_gap_meets_when_en_minimum_two_and_jp_zero():
    """新ルール: en >= 2 (旧 3 から緩和) AND jp == 0 → 成立。"""
    se = _scored(
        sources_en=2,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is True


def test_silence_gap_fails_when_below_min_en_threshold():
    """en < 2 はどんな条件でも silence_gap 不成立 (海外側の母数不足)。"""
    se = _scored(
        sources_en=1,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is False


def test_silence_gap_meets_when_only_ijai_passes_interest_filter():
    """新ルール: ga と ijai は OR (旧 AND) → 片方 4.0 以上でトピック関心度通過。"""
    se = _scored(
        sources_en=3,
        sources_jp=0,
        breakdown={"global_attention_score": 3.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is True


def test_silence_gap_fails_when_both_interest_signals_low():
    """ga と ijai が両方 4.0 未満ならトピック関心度フィルタを通過せず不成立。"""
    se = _scored(
        sources_en=5,
        sources_jp=0,
        breakdown={"global_attention_score": 2.0, "indirect_japan_impact_score": 2.0},
    )
    assert _meets_silence_gap_conditions(se) is False


def test_silence_gap_meets_when_jp_text_volume_much_smaller():
    """新ルール: jp:en 件数が同数でも、テキスト量が大幅に少なければ成立。

    sources_jp=2, sources_en=2 だが jp_view が短く en_view が長い → 情報量比で成立。
    """
    se = _scored(
        sources_en=2,
        sources_jp=2,
        japan_view="短い",  # 2 chars
        global_view="A much longer global view text spanning many words and sentences." * 3,
        breakdown={"global_attention_score": 5.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is True


def test_silence_gap_fails_when_text_volume_balanced():
    """件数同数 + テキスト量も同程度 → silence_gap は成立しない。"""
    se = _scored(
        sources_en=2,
        sources_jp=2,
        japan_view="日本側の論評が十分にある長文の記述例。" * 5,
        global_view="Global side commentary of similar length." * 3,
        breakdown={"global_attention_score": 5.0, "indirect_japan_impact_score": 5.0},
    )
    assert _meets_silence_gap_conditions(se) is False


def test_silence_gap_score_is_clamped_to_10():
    se = _scored(
        sources_en=10,
        sources_jp=0,
        breakdown={"global_attention_score": 10.0, "indirect_japan_impact_score": 10.0},
    )
    score, _ = _calculate_silence_gap_score(se)
    assert score == 10.0


def test_silence_gap_score_jp_penalty_drives_below_zero_clamped_to_zero():
    se = _scored(
        sources_en=1,
        sources_jp=5,
        breakdown={"global_attention_score": 0.0, "indirect_japan_impact_score": 0.0},
    )
    score, _ = _calculate_silence_gap_score(se)
    assert score == 0.0


# ---------- framing_inversion (LLM ベース) ----------
#
# 旧ルールベース実装 (sources_jp >= 1 AND sources_en >= 2 AND
# perspective_gap_score >= 6.0) を撤去し、LLM 判定に置き換えた。
# テストはすべて _FakeLLMClient を介して実 LLM に到達しないように設計する。
# 早期リターン (jp=0 / en=0 / total<2) では LLM が呼ばれないことを別途確認。

import json as _json


def _framing_response_json(
    *,
    is_inversion: bool,
    confidence: str,
    jp_framing: str = "positive",
    en_framing: str = "negative",
    inversion_meaning: str = "視聴者は片方の論調しか知らない可能性が高い。",
) -> str:
    """テスト用の LLM JSON レスポンス文字列を生成する。"""
    payload = {
        "jp_framing": jp_framing,
        "jp_rationale": "test rationale (jp)",
        "en_framing": en_framing,
        "en_rationale": "test rationale (en)",
        "is_inversion": is_inversion,
        "inversion_meaning": inversion_meaning if is_inversion else "",
        "confidence": confidence,
        "unclear_reason": "" if is_inversion else "test unclear reason",
    }
    return _json.dumps(payload, ensure_ascii=False)


def test_framing_inversion_meets_when_llm_returns_inversion_high(monkeypatch):
    """LLM が is_inversion=True / confidence=high を返せば成立。"""
    set_framing_llm(
        monkeypatch,
        _framing_response_json(is_inversion=True, confidence="high"),
    )
    se = _scored(sources_en=2, sources_jp=1, breakdown={"perspective_gap_score": 2.0})
    assert _meets_framing_inversion_conditions(se) is True


def test_framing_inversion_meets_when_llm_returns_inversion_medium(monkeypatch):
    """confidence=medium も成立 (low のみが弾かれる)。"""
    set_framing_llm(
        monkeypatch,
        _framing_response_json(is_inversion=True, confidence="medium"),
    )
    se = _scored(sources_en=2, sources_jp=1, breakdown={"perspective_gap_score": 0.0})
    assert _meets_framing_inversion_conditions(se) is True


def test_framing_inversion_fails_when_llm_returns_low_confidence(monkeypatch):
    """confidence=low は無理に判定しない方針 → 不成立。"""
    set_framing_llm(
        monkeypatch,
        _framing_response_json(is_inversion=True, confidence="low"),
    )
    se = _scored(sources_en=2, sources_jp=1, breakdown={"perspective_gap_score": 8.0})
    assert _meets_framing_inversion_conditions(se) is False


def test_framing_inversion_fails_when_llm_returns_no_inversion(monkeypatch):
    """is_inversion=False は不成立。"""
    set_framing_llm(
        monkeypatch,
        _framing_response_json(is_inversion=False, confidence="high"),
    )
    se = _scored(sources_en=3, sources_jp=2, breakdown={"perspective_gap_score": 7.0})
    assert _meets_framing_inversion_conditions(se) is False


def test_framing_inversion_fails_when_llm_raises(monkeypatch):
    """LLM 呼び出しが例外を投げた場合はフェイルセーフで False。"""
    set_framing_llm(monkeypatch, RuntimeError("simulated 429 RESOURCE_EXHAUSTED"))
    se = _scored(sources_en=2, sources_jp=1, breakdown={"perspective_gap_score": 7.0})
    assert _meets_framing_inversion_conditions(se) is False


def test_framing_inversion_fails_when_llm_returns_unparseable_json(monkeypatch):
    """JSON でない応答が返ったらフェイルセーフで False。"""
    set_framing_llm(monkeypatch, "this is not json at all -- just plain prose")
    se = _scored(sources_en=2, sources_jp=1, breakdown={"perspective_gap_score": 7.0})
    assert _meets_framing_inversion_conditions(se) is False


def test_framing_inversion_handles_code_fenced_json(monkeypatch):
    """```json ... ``` でラップされた応答も _json_utils.parse_json_response が剥がす。"""
    payload = _framing_response_json(is_inversion=True, confidence="high")
    fenced = f"```json\n{payload}\n```"
    set_framing_llm(monkeypatch, fenced)
    se = _scored(sources_en=2, sources_jp=1, breakdown={"perspective_gap_score": 0.0})
    assert _meets_framing_inversion_conditions(se) is True


def test_framing_inversion_does_not_call_llm_when_no_jp_sources(monkeypatch):
    """jp_count == 0 は LLM を呼ばずに早期 False。"""
    fake = set_framing_llm(
        monkeypatch,
        _framing_response_json(is_inversion=True, confidence="high"),
    )
    se = _scored(sources_en=3, sources_jp=0, breakdown={"perspective_gap_score": 8.0})
    assert _meets_framing_inversion_conditions(se) is False
    assert fake.calls == []  # LLM が呼ばれていないこと


def test_framing_inversion_does_not_call_llm_when_no_en_sources(monkeypatch):
    """en_count == 0 は LLM を呼ばずに早期 False。"""
    fake = set_framing_llm(
        monkeypatch,
        _framing_response_json(is_inversion=True, confidence="high"),
    )
    se = _scored(sources_en=0, sources_jp=2, breakdown={"perspective_gap_score": 8.0})
    assert _meets_framing_inversion_conditions(se) is False
    assert fake.calls == []


def test_framing_inversion_does_not_call_llm_when_total_below_two(monkeypatch):
    """sources_total < 2 (jp+en の合計) も早期 False。

    jp=1, en=0 のような片側成立かつ合計 1 のケースを救う。
    """
    fake = set_framing_llm(
        monkeypatch,
        _framing_response_json(is_inversion=True, confidence="high"),
    )
    se = _scored(sources_en=0, sources_jp=1, breakdown={"perspective_gap_score": 8.0})
    assert _meets_framing_inversion_conditions(se) is False
    assert fake.calls == []


def test_framing_inversion_fails_when_llm_client_unavailable(monkeypatch):
    """get_analysis_llm_client() が None を返すケース (autouse 状態) でも安全に False。"""
    se = _scored(sources_en=2, sources_jp=1, breakdown={"perspective_gap_score": 8.0})
    assert _meets_framing_inversion_conditions(se) is False


def test_framing_inversion_score_uses_llm_confidence_high(monkeypatch):
    """confidence=high は score=9.0、reasoning に jp/en の framing と meaning を含む。"""
    set_framing_llm(
        monkeypatch,
        _framing_response_json(
            is_inversion=True,
            confidence="high",
            jp_framing="positive",
            en_framing="negative",
            inversion_meaning="日本では成功と報じられた合意が海外では譲歩として懸念されている。",
        ),
    )
    se = _scored(
        title="Trade deal headlines diverge",
        sources_en=2, sources_jp=1, breakdown={"perspective_gap_score": 0.0},
    )
    score, reason = _calculate_framing_inversion_score(se)
    assert score == pytest.approx(9.0)
    assert "jp=positive" in reason
    assert "en=negative" in reason
    assert "high" in reason


def test_framing_inversion_score_uses_llm_confidence_medium(monkeypatch):
    """confidence=medium は score=7.0。"""
    set_framing_llm(
        monkeypatch,
        _framing_response_json(is_inversion=True, confidence="medium"),
    )
    se = _scored(sources_en=2, sources_jp=1, breakdown={"perspective_gap_score": 0.0})
    score, _ = _calculate_framing_inversion_score(se)
    assert score == pytest.approx(7.0)


def test_framing_inversion_score_zero_when_classifier_fails(monkeypatch):
    """LLM 失敗 → score=0.0 (reasoning に「判定不能」が含まれる)。"""
    set_framing_llm(monkeypatch, RuntimeError("simulated LLM outage"))
    se = _scored(sources_en=2, sources_jp=1, breakdown={"perspective_gap_score": 0.0})
    score, reason = _calculate_framing_inversion_score(se)
    assert score == 0.0
    assert "判定不能" in reason or "unavailable" in reason.lower()


def test_framing_inversion_meets_and_calculate_share_single_llm_call(monkeypatch):
    """_meets と _calculate を続けて呼んでも LLM は 1 回だけ叩かれる
    (event.id ベースの内部キャッシュ _FRAMING_RESULTS で再利用)。
    """
    fake = set_framing_llm(
        monkeypatch,
        _framing_response_json(is_inversion=True, confidence="high"),
    )
    se = _scored(sources_en=2, sources_jp=1, breakdown={"perspective_gap_score": 0.0})
    assert _meets_framing_inversion_conditions(se) is True
    score, _ = _calculate_framing_inversion_score(se)
    assert score == pytest.approx(9.0)
    assert len(fake.calls) == 1, f"LLM が {len(fake.calls)} 回呼ばれた (期待: 1)"


# ---------- hidden_stakes ----------

def test_hidden_stakes_meets_when_impact_high_and_kw_present():
    se = _scored(
        title="TSMC fab decision affects Toyota supply chain",
        breakdown={"indirect_japan_impact_score": 6.0},
    )
    assert _meets_hidden_stakes_conditions(se) is True


def test_hidden_stakes_meets_when_ijai_alone_is_strong():
    """新ルール: ijai >= 7.0 (STRONG) 単独で成立 (企業キーワード不要)。

    メキシコ → 日本原油輸出 (ijai=9.0) のような事例を救済する経路。
    """
    se = _scored(
        title="Eurozone monetary policy review",
        breakdown={"indirect_japan_impact_score": 8.0},
    )
    assert _meets_hidden_stakes_conditions(se) is True


def test_hidden_stakes_fails_without_japan_industry_keyword_at_mid_ijai():
    """ijai 中程度 (4.0 ≤ ijai < 7.0) で企業キーワードも間接影響キーワードも
    無ければ不成立。旧テストの代替: ijai=6.0, "Eurozone monetary policy review"
    は間接影響キーワードを含まない (monetary policy / eurozone は両方 KW 外)。
    """
    se = _scored(
        title="Eurozone monetary policy review",
        breakdown={"indirect_japan_impact_score": 5.0},  # < STRONG
    )
    assert _meets_hidden_stakes_conditions(se) is False


def test_hidden_stakes_meets_at_mid_ijai_with_indirect_keyword():
    """新ルール: ijai 中程度でも indirect_japan_impact_keywords (oil supply 等)
    があれば成立。企業名キーワードがないケースを救済する経路。
    """
    se = _scored(
        title="Mexico oil supply route opens to Japan",
        breakdown={"indirect_japan_impact_score": 5.0},
    )
    assert _meets_hidden_stakes_conditions(se) is True


def test_hidden_stakes_fails_when_ijai_below_minimum():
    """ijai < 3.0 はどんなキーワードがあっても問答無用で不成立。"""
    se = _scored(
        title="Toyota wins regional design award",
        breakdown={"indirect_japan_impact_score": 2.5},
    )
    assert _meets_hidden_stakes_conditions(se) is False


def test_hidden_stakes_fails_with_zero_ijai():
    """ijai が 0 (score_breakdown 未設定) なら不成立。"""
    se = _scored(title="Toyota recall affects Asia", breakdown={})
    assert _meets_hidden_stakes_conditions(se) is False


def test_hidden_stakes_score_includes_impact_unmentioned_bonus():
    """JP ソースありで impact_on_japan が空 → +2 ボーナス。"""
    se = _scored(
        title="Toyota faces new chip restrictions",
        sources_jp=1,
        breakdown={"indirect_japan_impact_score": 5.0},
    )
    score, reason = _calculate_hidden_stakes_score(se)
    # 5.0 (impact) + 1 (Toyota) + 2.0 (unmentioned) = 8.0
    assert score == pytest.approx(8.0)
    assert "impact_unmentioned_bonus=2.0" in reason


def test_hidden_stakes_no_unmentioned_bonus_when_no_jp_sources():
    se = _scored(
        title="Toyota faces new chip restrictions",
        sources_jp=0,
        breakdown={"indirect_japan_impact_score": 5.0},
    )
    score, _ = _calculate_hidden_stakes_score(se)
    # 5 + 1 + 0 = 6
    assert score == pytest.approx(6.0)


# ---------- cultural_blindspot ----------

def test_cultural_blindspot_meets_with_cultural_signals():
    se = _scored(
        title="Saudi religious tradition complicates new reform",
        summary="The monarchy's role under Islamic tradition is changing",
        breakdown={"geopolitics_depth_score": 5.0},
    )
    assert _meets_cultural_blindspot_conditions(se) is True


def test_cultural_blindspot_fails_without_signals():
    se = _scored(title="Stock market closes flat", summary="")
    assert _meets_cultural_blindspot_conditions(se) is False


def test_cultural_blindspot_score_clamped():
    se = _scored(
        title="religion tradition monarchy ritual caste gender feminism",
        editorial_tags=["religion", "tradition"],
        breakdown={"geopolitics_depth_score": 10.0},
    )
    score, _ = _calculate_cultural_blindspot_score(se)
    assert score <= 10.0


def test_cultural_blindspot_meets_with_non_western_region_and_source():
    """新ルール: 文化キーワードが無くても、event の region に non_western 系を含み
    かつ非西側媒体ソースがあれば成立 (region+source パターン)。
    """
    sources_by_locale = {
        "japan": _jp_sources(1),
        "global_south": [
            SourceRef(
                name="BuenosAiresTimes",
                url="https://batimes.com.ar/x",
                region="global_south",
                language="en",
                country="AR",
            ),
        ],
    }
    se = _scored(
        title="Argentine economic policy shift sparks regional debate",
        sources_jp=1,
        sources_en=1,
        sources_by_locale=sources_by_locale,
        breakdown={"geopolitics_depth_score": 0.0},
    )
    assert _meets_cultural_blindspot_conditions(se) is True


def test_cultural_blindspot_fails_with_only_western_sources():
    """西側 region (global / europe) のみのソース構成 → region+source パターン不成立、
    かつ文化キーワードも無いなら全体不成立。"""
    sources_by_locale = {
        "japan": _jp_sources(1),
        "global": _en_sources(2),
        "europe": [
            SourceRef(name="LeMonde", url="https://lemonde.fr/x", region="europe",
                      language="en", country="FR"),
        ],
    }
    se = _scored(
        title="EU summit on trade policy concludes",
        sources_jp=1,
        sources_en=2,
        sources_by_locale=sources_by_locale,
        breakdown={"geopolitics_depth_score": 0.0},
    )
    assert _meets_cultural_blindspot_conditions(se) is False


def test_cultural_blindspot_meets_via_source_name_when_region_unset():
    """非西側媒体名は region 未設定でも検出される (古いデータの救済)。"""
    sources_by_locale = {
        "japan": _jp_sources(1),
        "middle_east": [
            SourceRef(name="AlJazeera", url="https://aljazeera.com/x",
                      region="middle_east", language="en", country="QA"),
        ],
    }
    se = _scored(
        title="Gulf states reshape energy strategy",
        sources_jp=1,
        sources_en=1,
        sources_by_locale=sources_by_locale,
    )
    assert _meets_cultural_blindspot_conditions(se) is True


def test_cultural_blindspot_score_gets_non_western_bonus():
    """region+source 経路成立時は uniqueness に +2.0 のボーナス。"""
    sources_by_locale = {
        "japan": _jp_sources(1),
        "global_south": [
            SourceRef(name="FolhaDeSPaulo", url="https://folha.com.br/x",
                      region="global_south", language="en", country="BR"),
        ],
    }
    se = _scored(
        title="Brazil moves on land reform",
        sources_jp=1,
        sources_en=1,
        sources_by_locale=sources_by_locale,
        breakdown={"geopolitics_depth_score": 0.0},
    )
    score, reason = _calculate_cultural_blindspot_score(se)
    # uniqueness=0 (no cultural kw, no gd) + 2.0 bonus → 2.0
    assert score == pytest.approx(2.0)
    assert "non_western_bonus=2.0" in reason


# ---------- extract_perspectives ----------

def test_extract_returns_only_viable_axes():
    se = _scored(
        sources_en=3,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    candidates = extract_perspectives(se)
    axes = {c.axis for c in candidates}
    assert "silence_gap" in axes
    # framing_inversion は jp source が 0 なので除外
    assert "framing_inversion" not in axes


def test_extract_sorted_by_score_descending():
    se = _scored(
        title="Toyota chip restrictions trade war religion tradition",
        sources_en=4,
        sources_jp=1,
        breakdown={
            "global_attention_score": 7.0,
            "indirect_japan_impact_score": 5.0,
            "perspective_gap_score": 7.0,
            "geopolitics_depth_score": 6.0,
        },
    )
    candidates = extract_perspectives(se)
    scores = [c.score for c in candidates]
    assert scores == sorted(scores, reverse=True)


def test_extract_filters_by_channel_config_perspective_axes():
    se = _scored(
        sources_en=3,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    cfg = ChannelConfig(
        channel_id="restricted",
        display_name="Restricted",
        enabled=True,
        source_regions=["global"],
        perspective_axes=["framing_inversion"],
        duration_profiles=["breaking_shock_60s"],
        prompt_variant="r_v1",
        posts_per_day=1,
    )
    candidates = extract_perspectives(se, channel_config=cfg)
    axes = {c.axis for c in candidates}
    assert "silence_gap" not in axes  # 軸が許可リストに含まれない


def test_extract_geo_lens_allows_all_four_axes():
    se = _scored(
        title="Toyota chip restrictions amid Saudi religion tradition",
        sources_en=3,
        sources_jp=1,
        breakdown={
            "global_attention_score": 7.0,
            "indirect_japan_impact_score": 6.0,
            "perspective_gap_score": 7.0,
            "geopolitics_depth_score": 5.0,
        },
    )
    cfg = ChannelConfig.load("geo_lens")
    candidates = extract_perspectives(se, channel_config=cfg)
    # 4軸の少なくとも複数が成立しうる
    axes = {c.axis for c in candidates}
    assert axes.issubset(
        {"silence_gap", "framing_inversion", "hidden_stakes", "cultural_blindspot"}
    )


def test_extract_returns_empty_when_no_axis_meets_conditions():
    se = _scored(title="Local news", summary="A small town story")
    candidates = extract_perspectives(se)
    assert candidates == []


def test_perspective_candidate_has_evidence_refs():
    se = _scored(
        sources_en=3,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    candidates = extract_perspectives(se)
    sg = next(c for c in candidates if c.axis == "silence_gap")
    assert all(ref.startswith("https://") for ref in sg.evidence_refs)
    assert len(sg.evidence_refs) == 3


def test_perspective_candidate_pydantic_model_returned():
    se = _scored(
        sources_en=3,
        sources_jp=0,
        breakdown={"global_attention_score": 7.0, "indirect_japan_impact_score": 5.0},
    )
    candidates = extract_perspectives(se)
    assert all(isinstance(c, PerspectiveCandidate) for c in candidates)


# ---------- メキシコ原油事例リアル再現フィクスチャ ----------
#
# 実 LLM 試運転 (2026-04-26 01:14〜) で観点不成立スキップが発生した
# cls-ccdac99d90dc 相当のイベント。本ファイル修正 (rule-based perspective
# rebuild) 後は最低 hidden_stakes が確実に成立すべき。

def _make_mexico_oil_event_fixture() -> ScoredEvent:
    """メキシコ→日本 100 万バレル原油輸出事例の再現フィクスチャ。

    再現する事実: sources_jp=2, sources_en=2 (うち global_south 系を含む),
    ijai≈9.0, regions={japan, global_south}。
    """
    sources_by_locale = {
        "japan": [
            SourceRef(
                name="Nikkei", url="https://nikkei.com/mexico-oil",
                title="メキシコから日本へ100万バレル原油輸出",
                region="japan", language="ja", country="JP",
            ),
            SourceRef(
                name="NHK", url="https://nhk.or.jp/mexico-oil",
                title="メキシコ原油の対日輸出が再開",
                region="japan", language="ja", country="JP",
            ),
        ],
        "global_south": [
            SourceRef(
                name="BuenosAiresTimes", url="https://batimes.com.ar/mexico-oil",
                title="Mexico ships one million barrels of crude oil to Japan in landmark export deal",
                region="global_south", language="en", country="AR",
            ),
            SourceRef(
                name="FolhaDeSPaulo", url="https://folha.com.br/mexico-oil",
                title="Mexican crude oil supply to Japan signals shift away from Middle East dependence",
                region="global_south", language="en", country="BR",
            ),
        ],
    }
    ev = NewsEvent(
        id="cls-ccdac99d90dc",
        title="Mexico ships 1M barrels of crude oil to Japan",
        summary=(
            "Mexico has resumed oil supply to Japan with a one million barrel export. "
            "The deal eases Japan's reliance on Middle East crude oil and adds a new "
            "energy supply route across the Pacific."
        ),
        category="energy",
        source="BuenosAiresTimes",
        published_at=datetime.now(timezone.utc),
        japan_view="メキシコ産原油100万バレルが日本に輸出された。",  # 短い JP 論評
        global_view=(
            "Mexico's one million barrel crude oil export to Japan is widely covered "
            "across Latin American media as a strategic shift in Pacific energy trade. "
            "Coverage emphasizes the diversification away from Middle East oil supply, "
            "the implications for Mexico's state oil firm Pemex, and the renewed trans-Pacific "
            "shipping lane that is expected to reshape regional energy logistics."
        ),
        sources_by_locale=sources_by_locale,
    )
    return ScoredEvent(
        event=ev,
        score=8.5,
        score_breakdown={
            "indirect_japan_impact_score": 9.0,
            "global_attention_score": 5.0,
            "perspective_gap_score": 2.0,
            "geopolitics_depth_score": 6.0,
        },
    )


def test_mexico_oil_event_triggers_hidden_stakes():
    """本バッチ最重要: メキシコ原油事例で hidden_stakes が確実に成立する。

    旧実装ではこの事例で 4 軸全部不成立 → 分析レイヤースキップ → 動画生成スキップ
    が発生したため、本テストは「観点不成立スキップ事故」のリグレッション検出。
    """
    se = _make_mexico_oil_event_fixture()
    assert _meets_hidden_stakes_conditions(se) is True


def test_mexico_oil_event_extract_returns_at_least_one_candidate():
    """4 軸どれか 1 つでも成立すれば extract_perspectives は非空リストを返す。

    ここでは hidden_stakes と cultural_blindspot の両方が成立する想定。
    """
    se = _make_mexico_oil_event_fixture()
    candidates = extract_perspectives(se)
    assert len(candidates) >= 1
    axes = {c.axis for c in candidates}
    # hidden_stakes は必達
    assert "hidden_stakes" in axes
    # cultural_blindspot も region+source パターンで成立すべき
    assert "cultural_blindspot" in axes


# ---------- フォールバック観点 + why_now ----------
#
# Hydrangea のコンセプト「世界視点で日本ニュースを再解釈する」を守るため、
# 4 軸全部不成立でも最低品質ゲートを通過したイベントはフォールバック観点で
# 動画生成パスに乗せる。並行して、全観点候補に why_now を必須化する。

def _make_low_signal_but_passable_event() -> ScoredEvent:
    """4 軸全部不成立だが sources_total >= 2 のイベント（フォールバック対象）。"""
    sources_by_locale = {
        "japan": _jp_sources(1),
        "global": [
            SourceRef(
                name="Reuters", url="https://reuters.com/x", region="global",
                language="en", country="US",
            ),
        ],
    }
    ev = NewsEvent(
        id="evt-low-signal",
        title="Tokyo metropolitan policy debate continues at city hall",
        summary="A routine policy discussion in Tokyo on local administrative matters.",
        category="domestic",
        source="NHK",
        published_at=datetime.now(timezone.utc),
        sources_by_locale=sources_by_locale,
    )
    return ScoredEvent(
        event=ev,
        score=3.0,
        score_breakdown={
            "indirect_japan_impact_score": 1.0,
            "global_attention_score": 1.0,
            "perspective_gap_score": 0.0,
            "geopolitics_depth_score": 0.0,
        },
    )


def _make_extremely_low_quality_event() -> ScoredEvent:
    """sources_total < 2 のイベント（フォールバックも発動しない品質ゲート未通過）。"""
    ev = NewsEvent(
        id="evt-extremely-low",
        title="Bad event",
        summary="",
        category="other",
        source="X",
        published_at=datetime.now(timezone.utc),
        sources_jp=[],
        sources_en=[
            SourceRef(name="X", url="https://x.example.com/x", region="global"),
        ],
    )
    return ScoredEvent(event=ev, score=0.0, score_breakdown={})


def test_fallback_perspective_triggers_when_all_axes_fail():
    """4軸全部不成立だが品質ゲート通過のイベント → フォールバックが成立する。"""
    se = _make_low_signal_but_passable_event()
    # まず 4 軸が全て不成立であることを確認 (テスト前提のサニティチェック)
    assert _meets_silence_gap_conditions(se) is False
    assert _meets_framing_inversion_conditions(se) is False
    assert _meets_hidden_stakes_conditions(se) is False
    assert _meets_cultural_blindspot_conditions(se) is False

    candidates = extract_perspectives(se)
    assert len(candidates) == 1
    assert candidates[0].axis == "hidden_stakes"  # フォールバックは hidden_stakes
    assert candidates[0].why_now  # 必ず非空
    assert len(candidates[0].why_now) > 20  # 単なる定型文じゃない


def test_fallback_blocked_by_quality_gate():
    """sources_total < 2 のイベントはフォールバックも発動せず空リスト。"""
    se = _make_extremely_low_quality_event()
    candidates = extract_perspectives(se)
    assert candidates == []


def test_why_now_present_in_all_axis_candidates():
    """B-1 の3軸 + フォールバックすべてで why_now が生成されること。

    メキシコ原油フィクスチャは hidden_stakes / cultural_blindspot が成立する想定。
    フォールバック発動ケースは別テストで検査済み。
    """
    se = _make_mexico_oil_event_fixture()
    candidates = extract_perspectives(se)
    assert len(candidates) >= 1
    for c in candidates:
        assert c.why_now, f"axis={c.axis} の why_now が空"
        assert len(c.why_now) > 10, f"axis={c.axis} の why_now が短すぎる"


def test_why_now_reflects_event_specifics():
    """why_now が event 固有の情報（タイトルや keyword）を反映していること。"""
    se = _make_mexico_oil_event_fixture()
    candidates = extract_perspectives(se)
    # メキシコ or 原油 or エネルギー のような固有情報が why_now に含まれるはず
    contains_specifics = any(
        any(kw in c.why_now for kw in ["メキシコ", "原油", "エネルギー", "Mexico", "oil"])
        for c in candidates
    )
    assert contains_specifics


def test_why_now_present_in_fallback_candidate():
    """フォールバック観点でも why_now が event 固有情報を反映すること。"""
    se = _make_low_signal_but_passable_event()
    candidates = extract_perspectives(se)
    assert len(candidates) == 1
    fallback = candidates[0]
    assert fallback.why_now
    # title (Tokyo) を反映していること
    assert "Tokyo" in fallback.why_now or "metropolitan" in fallback.why_now
