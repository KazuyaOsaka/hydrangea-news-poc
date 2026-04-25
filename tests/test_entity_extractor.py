"""src/analysis/entity_extractor.py のテスト。LLM 呼び出しなし。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest
import yaml

from src.analysis import entity_extractor
from src.analysis.entity_extractor import (
    _normalize_entity,
    extract_primary_entities,
    extract_primary_topics,
)
from src.shared.models import NewsEvent, ScoredEvent, SourceRef


# ---------- helpers ----------

def _make_scored(
    *,
    title: str = "",
    summary: str = "",
    background: str | None = None,
    impact_on_japan: str | None = None,
    tags: list[str] | None = None,
    editorial_tags: list[str] | None = None,
) -> ScoredEvent:
    ev = NewsEvent(
        id="evt-1",
        title=title,
        summary=summary,
        category="politics",
        source="Reuters",
        published_at=datetime.now(),
        background=background,
        impact_on_japan=impact_on_japan,
        tags=tags or [],
    )
    return ScoredEvent(
        event=ev,
        score=1.0,
        editorial_tags=editorial_tags or [],
    )


@pytest.fixture(autouse=True)
def _clear_entity_cache():
    """各テスト前に辞書キャッシュをリセットする（テスト間隔離）。"""
    entity_extractor._reset_cache_for_tests()
    yield
    entity_extractor._reset_cache_for_tests()


# ---------- _normalize_entity ----------

def test_normalize_lowercases_ascii():
    assert _normalize_entity("Trump") == "trump"
    assert _normalize_entity("  TSMC  ") == "tsmc"


def test_normalize_compresses_whitespace():
    assert _normalize_entity("Donald   Trump") == "donald trump"


def test_normalize_empty_string():
    assert _normalize_entity("") == ""


# ---------- 辞書照合 ----------

def test_extract_entity_simple_english():
    se = _make_scored(title="Trump announces new tariffs on China")
    ents = extract_primary_entities(se)
    assert "trump" in ents
    assert "china" in ents


def test_extract_entity_japanese_alias():
    se = _make_scored(title="トランプが中国に関税を発動", summary="")
    ents = extract_primary_entities(se)
    assert "trump" in ents
    assert "china" in ents


def test_extract_entity_word_boundary_no_false_match():
    """trump が trumpet（架空）にマッチしないこと。"""
    # "trumpet" は単語境界外なので trump としてマッチしないはず
    se = _make_scored(title="A trumpet was heard at noon", summary="")
    ents = extract_primary_entities(se)
    assert "trump" not in ents


def test_extract_entity_full_form_donald_trump():
    se = _make_scored(title="", summary="Donald Trump returns to Washington")
    ents = extract_primary_entities(se)
    assert "trump" in ents


def test_extract_entity_searches_summary_and_background():
    se = _make_scored(
        title="Election update",
        summary="The campaign continues",
        background="Joe Biden criticized rivals",
    )
    ents = extract_primary_entities(se)
    assert "biden" in ents


def test_extract_topic_trade_war():
    se = _make_scored(title="The new trade war is escalating", summary="")
    topics = extract_primary_topics(se)
    assert "trade_war" in topics


def test_extract_topic_japanese():
    se = _make_scored(title="", summary="関税の発動でインフレ懸念", tags=["インフレ"])
    topics = extract_primary_topics(se)
    assert "trade_war" in topics
    assert "inflation" in topics


def test_extract_topic_uses_editorial_tags():
    se = _make_scored(title="OPEC decision", summary="", editorial_tags=["energy crisis"])
    topics = extract_primary_topics(se)
    assert "energy_crisis" in topics


def test_extract_returns_empty_when_no_match():
    se = _make_scored(title="Local cat won fishing contest", summary="")
    assert extract_primary_entities(se) == []
    assert extract_primary_topics(se) == []


def test_extract_dedupes_canonicals():
    se = _make_scored(
        title="Trump met Trump's advisors",
        summary="Donald Trump spoke about Trump policies",
    )
    ents = extract_primary_entities(se)
    assert ents.count("trump") == 1


# ---------- LLM 呼び出ししないこと ----------

def test_no_llm_invocation_in_entity_extraction():
    """エンティティ抽出は決定的・ルールベース。既存の LLM ファクトリ関数を呼び出さないこと。"""
    se = _make_scored(title="Trump on tariffs", summary="")
    with mock.patch("src.llm.factory.get_llm_client") as factory_mock, \
         mock.patch("src.llm.factory.get_judge_llm_client") as judge_mock, \
         mock.patch("src.llm.factory.get_script_llm_client") as script_mock:
        extract_primary_entities(se)
        extract_primary_topics(se)
    factory_mock.assert_not_called()
    judge_mock.assert_not_called()
    script_mock.assert_not_called()


def test_entity_extractor_does_not_import_gemini_module():
    """src.analysis.entity_extractor が google.generativeai を直接 import していないこと。"""
    import src.analysis.entity_extractor as ee
    src_text = Path(ee.__file__).read_text(encoding="utf-8")
    assert "google.generativeai" not in src_text
    assert "import google" not in src_text


# ---------- 明示パスでの辞書ロード ----------

def test_extract_with_custom_dictionary(tmp_path: Path):
    custom = {
        "people": {"alice": ["Alice", "アリス"]},
        "topics": {"adventure": ["adventure"]},
    }
    p = tmp_path / "ed.yaml"
    p.write_text(yaml.safe_dump(custom), encoding="utf-8")

    # _load_dictionary は path 渡しでキャッシュ無視
    d = entity_extractor._load_dictionary(p)
    se = _make_scored(title="Alice goes on an adventure", summary="")
    ents = extract_primary_entities(se, dictionary=d)
    topics = extract_primary_topics(se, dictionary=d)
    assert ents == ["alice"]
    assert topics == ["adventure"]
