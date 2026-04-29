"""F-14: parse_json_response の末尾修復ロジック検証。

試運転 7-G で発生した「LLM 出力の途中切れで analysis_result=None」を救済する
ため、_json_utils.parse_json_response に追加した修復ロジックを検証する。

カバレッジ方針:
  - 正常 JSON: 既存挙動を維持 (regex extraction / コードフェンス除去)
  - 修復対象: Unterminated string / 閉じカッコ不足 / 末尾カンマ / 不完全 pair
  - 修復不可: HTML / plain text / 完全空文字列 → 例外
  - allow_repair=False: 従来通り厳格パース
  - 修復成功時に F-14 WARNING ログが出る
"""
from __future__ import annotations

import json
import logging

import pytest

from src.analysis._json_utils import parse_json_response


# ---------- 正常系: 既存挙動を維持 ----------

def test_complete_json_parses_normally():
    """正常な JSON はそのままパース (修復ロジックを通らない)。"""
    parsed = parse_json_response('{"a": 1, "b": "ok"}')
    assert parsed == {"a": 1, "b": "ok"}


def test_code_fenced_json_still_parses():
    """既存挙動: ```json ... ``` フェンスは除去される。"""
    parsed = parse_json_response('```json\n{"x": 42}\n```')
    assert parsed == {"x": 42}


def test_surrounding_text_extracts_json_block():
    """既存挙動: 周辺テキストから最初の {...} を抽出。"""
    parsed = parse_json_response('Sure, here: {"selected_axis": "silence_gap"} done.')
    assert parsed["selected_axis"] == "silence_gap"


# ---------- 修復対象: Unterminated string ----------

def test_unterminated_string_truncated_and_repaired():
    """末尾の未閉鎖文字列は文字列開始位置以降を削除して修復。"""
    # `"b": "incomp` の `"incomp` が未閉鎖 → `"b":` ごと削除して `{"a": 1}` になる想定
    parsed = parse_json_response('{"a": 1, "b": "incomp')
    assert parsed == {"a": 1}


def test_unterminated_string_inside_array_repaired():
    """配列内の未閉鎖文字列も修復できる。"""
    parsed = parse_json_response('{"items": ["x", "y", "z')
    # "z は未閉鎖 → 切り詰めて閉じ補完 → {"items": ["x", "y"]} 程度を期待
    assert isinstance(parsed, dict)
    assert "items" in parsed
    assert parsed["items"][:2] == ["x", "y"]


# ---------- 修復対象: 閉じカッコ不足 ----------

def test_missing_closing_brace_repaired():
    """} 不足を補完して dict として読める。"""
    parsed = parse_json_response('{"a": 1, "b": 2')
    assert parsed == {"a": 1, "b": 2}


def test_missing_closing_bracket_repaired():
    """] 不足を補完して array をパースできる。"""
    parsed = parse_json_response('{"a": [1, 2, 3')
    assert parsed == {"a": [1, 2, 3]}


def test_nested_missing_brackets_repaired():
    """ネストした閉じ忘れも補完される。"""
    parsed = parse_json_response('{"outer": {"inner": [1, 2')
    assert parsed == {"outer": {"inner": [1, 2]}}


# ---------- 修復対象: 末尾カンマ / 不完全 pair ----------

def test_trailing_comma_in_object_removed():
    """オブジェクト末尾の余分なカンマを削除して修復。"""
    parsed = parse_json_response('{"a": 1, "b": 2,}')
    assert parsed == {"a": 1, "b": 2}


def test_trailing_comma_in_array_removed():
    """配列末尾の余分なカンマを削除して修復。"""
    parsed = parse_json_response('{"a": [1, 2, 3,]}')
    assert parsed == {"a": [1, 2, 3]}


def test_incomplete_key_value_pair_removed():
    """末尾の `"key":` (値なし) を削除して残りで修復。"""
    parsed = parse_json_response('{"a": 1, "b":')
    assert parsed == {"a": 1}


def test_incomplete_key_only_pair_removed():
    """末尾の `"key"` (コロンも値もない) を削除して修復。"""
    parsed = parse_json_response('{"a": 1, "b"')
    assert parsed == {"a": 1}


def test_incomplete_pair_inside_empty_object_repaired():
    """先頭直後の不完全 pair `{"key":` も補完できる。"""
    parsed = parse_json_response('{"a":')
    assert parsed == {}


# ---------- 修復不可ケース: 例外を伝播 ----------

def test_completely_invalid_text_raises():
    """JSON でない文字列は修復対象外。例外が伝播する。"""
    with pytest.raises(json.JSONDecodeError):
        parse_json_response("not json at all")


def test_html_like_text_raises():
    """HTML / プレーンテキストは修復対象外。"""
    with pytest.raises(json.JSONDecodeError):
        parse_json_response("<html><body>error</body></html>")


def test_empty_string_raises():
    """空文字列は例外。"""
    with pytest.raises(json.JSONDecodeError):
        parse_json_response("")


def test_whitespace_only_raises():
    """空白のみも例外。"""
    with pytest.raises(json.JSONDecodeError):
        parse_json_response("   \n\t  ")


# ---------- allow_repair=False: 厳格モード ----------

def test_allow_repair_false_strict_unterminated_raises():
    """allow_repair=False なら未閉鎖文字列も修復せず例外。"""
    with pytest.raises(json.JSONDecodeError):
        parse_json_response('{"a": 1, "b": "incomp', allow_repair=False)


def test_allow_repair_false_still_parses_valid_json():
    """allow_repair=False でも正常 JSON はパースできる (既存挙動互換)。"""
    parsed = parse_json_response('{"a": 1}', allow_repair=False)
    assert parsed == {"a": 1}


# ---------- ログ確認 ----------

def test_repair_emits_f14_warning_log(caplog):
    """修復成功時に [F-14] WARNING ログが出ることを保証する (試運転可視化用)。"""
    with caplog.at_level(logging.WARNING, logger="src.analysis._json_utils"):
        parse_json_response('{"a": 1, "b": 2')
    assert any("[F-14] JSON repaired" in rec.getMessage() for rec in caplog.records), (
        f"Expected [F-14] warning log; got records: "
        f"{[rec.getMessage() for rec in caplog.records]}"
    )


def test_no_repair_log_when_json_is_valid(caplog):
    """正常 JSON では F-14 ログが出ないことを保証 (誤検知防止)。"""
    with caplog.at_level(logging.WARNING, logger="src.analysis._json_utils"):
        parse_json_response('{"a": 1}')
    assert not any("[F-14]" in rec.getMessage() for rec in caplog.records)


# ---------- 試運転 7-G の実例再現 ----------

def test_real_world_unterminated_multiangle_response():
    """試運転 7-G で multi_angle_analyzer が遭遇したパターンを再現。

    LLM が長文の cultural_context を生成中に max_tokens で打ち切られ、
    `"cultural_context": "...日本では` の途中で切れたケースを想定。
    修復後に geopolitical / political_intent / economic_impact だけでも
    取得できることを確認する。
    """
    raw = (
        '{\n'
        '  "geopolitical": "OPEC 減産延長で原油価格に上昇圧力。",\n'
        '  "political_intent": "サウジは王制安定化のための歳入確保が狙い。",\n'
        '  "economic_impact": "日本のガソリン価格上昇とインフレ再燃リスク。",\n'
        '  "cultural_context": "日本では石油ショックの記憶が根強く残ってお'
    )
    parsed = parse_json_response(raw)
    assert isinstance(parsed, dict)
    assert parsed["geopolitical"] == "OPEC 減産延長で原油価格に上昇圧力。"
    assert parsed["political_intent"] == "サウジは王制安定化のための歳入確保が狙い。"
    assert parsed["economic_impact"] == "日本のガソリン価格上昇とインフレ再燃リスク。"
    # cultural_context は途中切れで削除されている想定
    assert "cultural_context" not in parsed


def test_real_world_truncated_inside_nested_array():
    """ネストした配列の中で切れた実例パターン。

    途中切れした 3 番目のオブジェクトは部分的に復元される (`content` 欠落) が、
    最初の 2 件は完全に取り出せることが重要。下流バリデーションが部分要素を
    弾く想定なので、F-14 の責務は「壊さず取れるだけ取る」こと。
    """
    raw = (
        '{"insights": ['
        '{"angle": "geopolitical", "content": "OK1"},'
        '{"angle": "political_intent", "content": "OK2"},'
        '{"angle": "economic_impact", "content": "途中で'
    )
    parsed = parse_json_response(raw)
    assert isinstance(parsed, dict)
    assert "insights" in parsed
    items = parsed["insights"]
    assert len(items) >= 2
    assert items[0] == {"angle": "geopolitical", "content": "OK1"}
    assert items[1] == {"angle": "political_intent", "content": "OK2"}


# ---------- 後方互換: 既存呼び出しが無変更で動作 ----------

def test_existing_callers_signature_unchanged():
    """既存の `parse_json_response(raw)` 呼び出しが無変更で動作する。

    これは parse_json_response の呼び出し元 (perspective_extractor /
    perspective_selector / multi_angle_analyzer / insight_extractor) が
    F-14 改修後も signature 変更なしで動くことを保証する。
    """
    # キーワード引数なしで呼べる
    assert parse_json_response('{"x": 1}') == {"x": 1}
    # 既存テストに合わせた挙動: 完全に無効な入力は例外
    with pytest.raises(json.JSONDecodeError):
        parse_json_response("not even a brace here")
