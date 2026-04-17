"""cross_lang_matcher モジュールのテスト。LLM / ネットワーク呼び出しなし。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.ingestion.cross_lang_matcher import extract_anchor_tokens, llm_same_event


# ── extract_anchor_tokens: 国名 ───────────────────────────────────────────────

def test_country_japan_jp_title():
    tokens = extract_anchor_tokens("日本銀行が利上げを決定")
    assert "country:japan" in tokens


def test_country_japan_en_title():
    tokens = extract_anchor_tokens("Japan raises interest rates")
    assert "country:japan" in tokens


def test_country_usa_en_title():
    tokens = extract_anchor_tokens("United States imposes new tariffs")
    assert "country:usa" in tokens


def test_country_usa_jp_title():
    tokens = extract_anchor_tokens("米国が追加関税を発表")
    assert "country:usa" in tokens


def test_country_no_match():
    tokens = extract_anchor_tokens("プロ野球：甲子園でサヨナラ勝ち")
    assert not any(t.startswith("country:") for t in tokens)


def test_country_prefix_namespace():
    """country: トークンが kw: や entity: と混在しないこと。"""
    tokens = extract_anchor_tokens("日本が関税を引き上げ")
    country_tokens = {t for t in tokens if t.startswith("country:")}
    assert "country:japan" in country_tokens
    # kw: prefix は別途存在するが country: と混在しない
    for t in country_tokens:
        assert t.startswith("country:"), f"unexpected prefix in country tokens: {t}"


# ── extract_anchor_tokens: 企業・機関名 ──────────────────────────────────────

def test_entity_boj_jp():
    tokens = extract_anchor_tokens("日本銀行が政策決定会合を開催")
    assert "entity:boj" in tokens


def test_entity_boj_jp_abbrev():
    tokens = extract_anchor_tokens("日銀が利上げを決定")
    assert "entity:boj" in tokens


def test_entity_boj_en():
    tokens = extract_anchor_tokens("Bank of Japan decides on rate hike")
    assert "entity:boj" in tokens


def test_entity_fed_en():
    tokens = extract_anchor_tokens("Federal Reserve raises rates by 25bp")
    assert "entity:fed" in tokens


def test_entity_fed_jp():
    tokens = extract_anchor_tokens("FRBが追加利上げを決定")
    assert "entity:fed" in tokens


def test_entity_acronym_fallback():
    """ENTITY_EN に未登録の大文字アクロニムもフォールバックで拾う。"""
    tokens = extract_anchor_tokens("IMF warns of global recession")
    assert "entity:imf" in tokens


def test_entity_acronym_fallback_nato():
    tokens = extract_anchor_tokens("NATO summit held in Brussels")
    assert "entity:nato" in tokens


def test_entity_no_false_positive_lowercase():
    """小文字のみ単語はアクロニムフォールバックに引っかからない。"""
    tokens = extract_anchor_tokens("local farmers market opens today")
    # 大文字アクロニムは存在しない
    entity_tokens = {t for t in tokens if t.startswith("entity:")}
    assert len(entity_tokens) == 0


# ── extract_anchor_tokens: キーワード対訳 ────────────────────────────────────

def test_kw_ratehike_jp():
    tokens = extract_anchor_tokens("追加利上げを決定した")
    assert "kw:ratehike" in tokens


def test_kw_ratehike_en():
    tokens = extract_anchor_tokens("rate hike announced by central bank")
    assert "kw:ratehike" in tokens


def test_kw_ratecut_jp():
    tokens = extract_anchor_tokens("金融緩和と利下げを同時実施")
    assert "kw:ratecut" in tokens


def test_kw_tariff_jp():
    tokens = extract_anchor_tokens("米国への関税引き上げを検討")
    assert "kw:tariff" in tokens


def test_kw_tariff_en():
    tokens = extract_anchor_tokens("tariffs imposed on chinese goods")
    assert "kw:tariff" in tokens


def test_kw_yen_jp():
    tokens = extract_anchor_tokens("円安が急速に進行")
    assert "kw:yenweaken" in tokens


def test_kw_no_match():
    tokens = extract_anchor_tokens("local community festival event")
    assert not any(t.startswith("kw:") for t in tokens)


# ── extract_anchor_tokens: 年号・数字 ────────────────────────────────────────

def test_num_year_jp():
    tokens = extract_anchor_tokens("2024年の日銀政策を振り返る")
    assert "num:2024" in tokens


def test_num_year_en():
    tokens = extract_anchor_tokens("Fed decision in 2025 affects markets")
    assert "num:2025" in tokens


def test_num_multiple_years():
    tokens = extract_anchor_tokens("comparing 2024 and 2025 rate policies")
    assert "num:2024" in tokens
    assert "num:2025" in tokens


def test_num_non_year_excluded():
    """4桁でも 19xx/20xx 以外の数字は num: トークンにならない。"""
    tokens = extract_anchor_tokens("model 9000 was released today")
    assert "num:9000" not in tokens


# ── extract_anchor_tokens: エッジケース ──────────────────────────────────────

def test_empty_string():
    assert extract_anchor_tokens("") == set()


def test_no_tokens_matched():
    tokens = extract_anchor_tokens("cat sat on the mat")
    # 短い単語のみ・辞書に無い → トークンなし (大文字アクロニムも無い)
    assert len(tokens) == 0


def test_bilingual_title():
    """日英混在タイトルで両方のアンカーが取れること。"""
    tokens = extract_anchor_tokens("日銀（Bank of Japan）が利上げ")
    assert "entity:boj" in tokens
    assert "kw:ratehike" in tokens


def test_cross_lang_boj_and_ratehike_shared():
    """JP タイトルと EN タイトルが同じアンカートークンを持つこと。"""
    jp_tokens = extract_anchor_tokens("日本銀行が利上げを決定")
    en_tokens = extract_anchor_tokens("Bank of Japan raises rates")
    shared = jp_tokens & en_tokens
    assert "entity:boj" in shared
    # 利上げ / "rate" keyword は辞書依存だが、少なくとも entity:boj は共通
    assert len(shared) >= 1


# ── llm_same_event ────────────────────────────────────────────────────────────

def _mock_llm(response: str) -> MagicMock:
    client = MagicMock()
    client.generate.return_value = response
    return client


def test_llm_same_event_yes():
    assert llm_same_event("日銀が利上げ", "Bank of Japan raises rates", _mock_llm("YES")) is True


def test_llm_same_event_yes_lowercase():
    assert llm_same_event("A", "B", _mock_llm("yes")) is True


def test_llm_same_event_yes_with_explanation():
    assert llm_same_event("A", "B", _mock_llm("YES, they cover the same event.")) is True


def test_llm_same_event_no():
    assert llm_same_event("日銀が利上げ", "プロ野球結果", _mock_llm("NO")) is False


def test_llm_same_event_maybe_returns_false():
    assert llm_same_event("A", "B", _mock_llm("MAYBE")) is False


def test_llm_same_event_exception_returns_false():
    client = MagicMock()
    client.generate.side_effect = Exception("API error")
    assert llm_same_event("A", "B", client) is False


def test_llm_same_event_prompt_contains_both_titles():
    """generate() に渡されるプロンプトに両タイトルが含まれること。"""
    client = _mock_llm("YES")
    llm_same_event("日銀が利上げ", "Bank of Japan raises rates", client)
    prompt = client.generate.call_args[0][0]
    assert "日銀が利上げ" in prompt
    assert "Bank of Japan raises rates" in prompt
