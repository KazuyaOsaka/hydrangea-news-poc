"""X1 (F-particular-angle-metadata-production-wire): extractor 単体テスト。

src/analysis/particular_angle_extractor.py の coerce / parse / 失敗時 None 動作を
LLM mock で決定的に検証する。

正典: docs/PARTICULAR_ANGLE_DEFINITION.md セクション 3.6-3.7。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.analysis.particular_angle_extractor import (
    _build_particular_angle_metadata,
    _coerce_confidence,
    _coerce_level,
    _coerce_stream,
    _coerce_type,
    _format_sources,
    _parse_llm_response,
    extract_particular_angle_metadata,
)
from src.shared.models import NewsEvent, ParticularAngleMetadata, SourceRef


# ---------- helpers ----------

class _FakeClient:
    """生成内容を制御できる LLM client mock (LLMClient interface の最小実装)。"""

    def __init__(self, responses):
        # responses は str または list[str]。list の場合は呼ぶたびに 1 つずつ取り出す。
        if isinstance(responses, str):
            self._queue = [responses]
        else:
            self._queue = list(responses)
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        if not self._queue:
            raise RuntimeError("FakeClient: no more responses queued")
        nxt = self._queue.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def _make_event(**overrides) -> NewsEvent:
    base = dict(
        id="evt_x1",
        title="米イラン和平交渉合意進展",
        summary="MEE オピニオン: 外交情報の金融商品化と国家規模のインサイダー取引。",
        category="geopolitics",
        source="MEE",
        published_at=datetime.now(timezone.utc),
        sources_by_locale={
            "global": [SourceRef(name="Middle East Eye", url="https://mee.example/a")],
            "japan": [SourceRef(name="日本経済新聞", url="https://nikkei.example/b")],
        },
    )
    base.update(overrides)
    return NewsEvent(**base)


_HAPPY_RESPONSE = json.dumps({
    "particular_angle": {
        "core_question": "市場参加者が外交情報の金融商品化を問題視している",
        "differentiation_from_mainstream": "日本主要紙は合意本体を報道、MEE は約 9.2 億ドルの原油ショートを問題視",
        "hydrangea_axis_alignment": "第 2 軸 (外交・経済・利害関係面、米国忖度)",
        "extraction_confidence": "high",
    },
    "stream_classification": {
        "estimated_stream": "stream_2_perspective_gap",
        "reasoning": "広範事件 (米イラン和平) は日本で報道済、特定角度 (インサイダー疑惑) は未報道",
        "confidence": "high",
    },
    "sontaku_signals": {
        "level": "high",
        "type": "diplomatic",
        "reasoning": "米国政府中枢への外交的忖度",
        "extraction_confidence": "high",
    },
})


# ---------- _coerce helpers ----------

def test_coerce_confidence_valid_and_invalid():
    assert _coerce_confidence("high") == "high"
    assert _coerce_confidence("HIGH") == "high"
    assert _coerce_confidence("medium") == "medium"
    assert _coerce_confidence("low") == "low"
    assert _coerce_confidence("unknown") == "medium"
    assert _coerce_confidence(None) == "medium"
    assert _coerce_confidence("") == "medium"


def test_coerce_stream_valid_and_invalid():
    assert _coerce_stream("stream_1_silence_gap") == "stream_1_silence_gap"
    assert _coerce_stream("stream_2_perspective_gap") == "stream_2_perspective_gap"
    assert _coerce_stream("stream_3_framing_inversion") == "stream_3_framing_inversion"
    assert _coerce_stream("out_of_scope") == "out_of_scope"
    # 不明値は out_of_scope (最も保守的 = 動画化対象外)
    assert _coerce_stream("stream_2_framing_inversion") == "out_of_scope"  # 旧 3 分類名
    assert _coerce_stream("garbage") == "out_of_scope"
    assert _coerce_stream(None) == "out_of_scope"


def test_coerce_level_valid_and_invalid():
    for v in ("high", "medium", "low", "none"):
        assert _coerce_level(v) == v
    assert _coerce_level("HIGH") == "high"
    assert _coerce_level("unknown") == "none"
    assert _coerce_level(None) == "none"


def test_coerce_type_none_when_level_is_none():
    """level=none 時は type 強制 None (正典 3.6.3、add_sontaku_signals._validate 踏襲)。"""
    assert _coerce_type("diplomatic", "none") is None
    assert _coerce_type("domestic", "none") is None
    assert _coerce_type(None, "none") is None


def test_coerce_type_valid_when_level_nonzero():
    for v in ("diplomatic", "domestic", "media_industry"):
        assert _coerce_type(v, "high") == v
    # null / empty / unknown はすべて None
    assert _coerce_type("null", "high") is None
    assert _coerce_type("", "medium") is None
    assert _coerce_type("garbage", "high") is None
    assert _coerce_type(None, "high") is None


# ---------- _parse_llm_response ----------

def test_parse_llm_response_raw_json():
    text = '{"particular_angle": {"core_question": "x"}}'
    d = _parse_llm_response(text)
    assert d["particular_angle"]["core_question"] == "x"


def test_parse_llm_response_fenced_json():
    text = '```json\n{"a": 1}\n```'
    assert _parse_llm_response(text) == {"a": 1}


def test_parse_llm_response_with_leading_trailing_noise():
    text = 'Sure! Here you go:\n{"a": 2}\nLet me know if you need more.'
    assert _parse_llm_response(text) == {"a": 2}


def test_parse_llm_response_handles_unescaped_newlines_in_strings():
    """文字列値中の生改行を救済する (extract_particular_angle.py 由来の修復)。"""
    text = '{"k": "line1\nline2"}'
    d = _parse_llm_response(text)
    assert "line1" in d["k"] and "line2" in d["k"]


# ---------- _build_particular_angle_metadata ----------

def test_build_metadata_happy():
    pam = _build_particular_angle_metadata(json.loads(_HAPPY_RESPONSE))
    assert isinstance(pam, ParticularAngleMetadata)
    assert pam.stream_classification == "stream_2_perspective_gap"
    assert pam.extraction_confidence == "high"
    assert pam.core_question.startswith("市場参加者")
    assert pam.sontaku_signals is not None
    assert pam.sontaku_signals.level == "high"
    assert pam.sontaku_signals.type == "diplomatic"


def test_build_metadata_coerces_level_none_type_to_null():
    """level=none + type=diplomatic が来ても type=None に矯正。"""
    payload = {
        "particular_angle": {},
        "stream_classification": {"estimated_stream": "out_of_scope"},
        "sontaku_signals": {
            "level": "none",
            "type": "diplomatic",  # 違反: spec では null 必須
            "reasoning": "",
            "extraction_confidence": "low",
        },
    }
    pam = _build_particular_angle_metadata(payload)
    assert pam.sontaku_signals.level == "none"
    assert pam.sontaku_signals.type is None


def test_build_metadata_coerces_unknown_stream_to_out_of_scope():
    payload = {
        "particular_angle": {"core_question": "x"},
        "stream_classification": {"estimated_stream": "stream_2_framing_inversion"},  # 旧名
        "sontaku_signals": {"level": "low"},
    }
    pam = _build_particular_angle_metadata(payload)
    assert pam.stream_classification == "out_of_scope"


def test_build_metadata_handles_missing_sections():
    """欠落セクションでもデフォルト値で安全に構築できる。"""
    pam = _build_particular_angle_metadata({})
    assert pam.stream_classification == "out_of_scope"
    assert pam.core_question == ""
    assert pam.sontaku_signals is not None
    assert pam.sontaku_signals.level == "none"
    assert pam.sontaku_signals.type is None


# ---------- _format_sources ----------

def test_format_sources_dedupes_by_locale():
    ev = _make_event(
        sources_by_locale={
            "global": [
                SourceRef(name="MEE", url="https://a"),
                SourceRef(name="MEE", url="https://b"),
            ],
            "japan": [SourceRef(name="日経", url="https://c")],
        }
    )
    s = _format_sources(ev)
    assert "MEE" in s and "日経" in s
    # 重複は 1 回だけ
    assert s.count("MEE") == 1


def test_format_sources_falls_back_to_source_when_empty():
    ev = _make_event(sources_by_locale={}, sources_jp=[], sources_en=[], source="FallbackFeed")
    assert _format_sources(ev) == "FallbackFeed"


# ---------- extract_particular_angle_metadata ----------

def test_extract_happy_path():
    ev = _make_event()
    client = _FakeClient(_HAPPY_RESPONSE)
    pam = extract_particular_angle_metadata(ev, client=client)
    assert pam is not None
    assert pam.stream_classification == "stream_2_perspective_gap"
    assert pam.sontaku_signals.level == "high"
    assert client.calls == 1


def test_extract_retries_on_parse_error_then_succeeds():
    ev = _make_event()
    client = _FakeClient(["not json at all", _HAPPY_RESPONSE])
    pam = extract_particular_angle_metadata(ev, client=client, max_retries=2)
    assert pam is not None
    assert pam.stream_classification == "stream_2_perspective_gap"
    assert client.calls == 2


def test_extract_returns_none_when_all_attempts_fail():
    ev = _make_event()
    client = _FakeClient(["garbage1", "garbage2"])
    pam = extract_particular_angle_metadata(ev, client=client, max_retries=2)
    assert pam is None
    assert client.calls == 2


def test_extract_returns_none_when_no_client(monkeypatch):
    ev = _make_event()
    # client=None かつ get_analysis_llm_client() も None を返す状況
    monkeypatch.setattr(
        "src.analysis.particular_angle_extractor.get_analysis_llm_client",
        lambda: None,
    )
    pam = extract_particular_angle_metadata(ev, client=None)
    assert pam is None


def test_extract_returns_none_on_empty_response():
    ev = _make_event()
    client = _FakeClient(["", ""])  # 空文字応答
    pam = extract_particular_angle_metadata(ev, client=client, max_retries=2)
    assert pam is None


def test_extract_returns_none_when_prompt_missing(monkeypatch):
    """プロンプト .md が無い場合は None (本番では起きないが防御)。"""
    ev = _make_event()
    client = _FakeClient(_HAPPY_RESPONSE)

    def _raise(*a, **kw):
        raise FileNotFoundError("missing")

    monkeypatch.setattr(
        "src.analysis.particular_angle_extractor.load_prompt", _raise
    )
    assert extract_particular_angle_metadata(ev, client=client) is None
