"""分析レイヤー内で共通利用する LLM 応答 JSON パーサ。

perspective_selector.parse_json_response を Batch 3 の multi_angle_analyzer /
insight_extractor からも再利用できるよう、純粋関数として切り出した。

挙動 (F-14 拡張版):
  - ```json ... ``` のコードフェンスを除去
  - 全文として JSON 解釈に失敗した場合は最初の `{...}` ブロックを抽出
  - 上記でも失敗した場合 (F-14): 末尾修復ロジックを試行
        - Unterminated string (末尾の " 不足) → 文字列開始位置から後を切り詰め
        - 末尾の不完全な key:value ペア → 削除
        - 末尾の余分なカンマ → 削除
        - 閉じカッコ不足 (} or ]) → コンテナのスタック順に補完
  - 修復成功時は WARNING ログ ("[F-14] JSON repaired ...") を出力
  - 修復も失敗した場合は最初の json.JSONDecodeError を伝播 (既存挙動互換)

allow_repair=False を指定すると修復を行わず、従来の厳格パース挙動になる。
既存呼び出しは無変更でも修復が有効になる (デフォルト True)。
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from src.shared.logger import get_logger

logger = get_logger(__name__)


def _strip_code_fence(raw: str) -> str:
    """```json ... ``` のフェンスを除去する。"""
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
        text = text.strip()
    return text


def parse_json_response(raw: str, *, allow_repair: bool = True) -> Any:
    """LLM 応答から JSON 本体を抽出して dict / list にする。

    Args:
        raw: LLM の出力文字列。
        allow_repair: True (default) なら F-14 末尾修復を試みる。False なら
            修復をスキップして従来通り厳格にパース。

    Returns:
        パース成功時の dict / list。

    Raises:
        json.JSONDecodeError: 直接パース・正規表現抽出・修復のいずれも失敗した場合。
            既存挙動と同じく「最初に失敗した直接パース」のエラーを伝播する。
    """
    text = _strip_code_fence(raw)

    # 試行 1: 全文をそのままパース (既存挙動)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        original_error = e

    # 試行 2: 最初の `{...}` ブロックを抽出 (既存挙動)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # 試行 3 (F-14): 末尾修復を試みる
    if allow_repair:
        repaired = _attempt_json_repair(text)
        if repaired is not None:
            try:
                result = json.loads(repaired)
                logger.warning(
                    "[F-14] JSON repaired successfully "
                    "(orig_length=%d, repaired_length=%d)",
                    len(text),
                    len(repaired),
                )
                return result
            except json.JSONDecodeError:
                pass

    # 全試行失敗 → 最初のエラーを伝播 (既存挙動互換)
    raise original_error


def _attempt_json_repair(text: str) -> Optional[str]:
    """LLM 出力 JSON の末尾を修復する (F-14)。

    対応パターン:
      - Unterminated string (末尾の " 不足) → 文字列開始位置以降を削除
      - 末尾の不完全な key:value ペア (`"key":` のみ等) → 削除
      - 末尾の余分なカンマ → 削除
      - 閉じカッコ不足 (} or ]) → コンテナスタックの順に補完

    修復対象は `{` または `[` で始まる入力に限定する (HTML / プレーンテキスト等を弾く)。
    修復後の文字列が json.loads できるかも本関数内で検証し、できないなら None を返す。

    Returns:
        json.loads 可能な修復後の文字列。修復不可なら None。
    """
    if not text or not text.strip():
        return None

    s = text.strip()

    # 修復は { または [ で始まる入力にのみ適用
    if not (s.startswith("{") or s.startswith("[")):
        return None

    # Step 1: 末尾の未閉鎖文字列を切り詰め
    truncated = _truncate_unterminated_string(s)
    if truncated is None:
        return None
    s = truncated

    # Step 2: 末尾の不完全な要素を削除 (object 内のみ "key" 単独を削除)
    s = _strip_incomplete_tail(s)

    # Step 3: ダングリングカンマ (`,]` `,}`) を削除
    s = re.sub(r",\s*([}\]])", r"\1", s)

    # Step 4: 閉じカッコをスタック順 (LIFO) で補完
    s = _balance_brackets(s)

    if not s:
        return None

    # 検証: 修復後にパースできなければ修復失敗
    try:
        json.loads(s)
    except json.JSONDecodeError:
        return None
    return s


def _truncate_unterminated_string(s: str) -> Optional[str]:
    """末尾に未閉鎖の文字列がある場合、その文字列の開始 " 以降を削除する。

    文字列が閉じている場合は元の文字列をそのまま返す。
    開始 " が見つからない異常ケースのみ None を返す。
    """
    in_string = False
    escape = False
    last_string_open: Optional[int] = None

    for i, ch in enumerate(s):
        if escape:
            escape = False
            continue
        if ch == "\\":
            if in_string:
                escape = True
            continue
        if ch == '"':
            if in_string:
                in_string = False
                last_string_open = None
            else:
                in_string = True
                last_string_open = i

    if not in_string:
        return s

    if last_string_open is None:
        return None

    return s[:last_string_open].rstrip()


def _current_container_type(s: str) -> Optional[str]:
    """直近で未閉鎖のコンテナ (`{` か `[`) を返す。

    文字列リテラル / エスケープを考慮してスタックを構築する。
    どちらも閉じている場合 None を返す。
    """
    stack: list[str] = []
    in_string = False
    escape = False
    for ch in s:
        if escape:
            escape = False
            continue
        if ch == "\\":
            if in_string:
                escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
    return stack[-1] if stack else None


def _strip_incomplete_tail(s: str) -> str:
    """末尾に残った不完全な要素を反復的に削除する。

    対応パターン:
      - `, "key":`            → カンマ毎削除 (object 内の不完全 pair)
      - `{ "key":`            → `{` だけ残す (object 先頭の不完全 pair)
      - `, "key"`             → object 内の場合のみ削除 (array 内では完結値)
      - 末尾の単独カンマ       → 削除

    array 内の `, "value"` は完結した値なので削除しない (コンテナ判定で区別)。
    """
    prev: Optional[str] = None
    while s != prev:
        prev = s
        s = s.rstrip()

        # `, "key":` (コロンの後に値なし) → 常に不完全 pair
        m = re.search(r',\s*"[^"\\]*(?:\\.[^"\\]*)*"\s*:\s*$', s)
        if m:
            s = s[: m.start()]
            continue

        # コンテナ先頭直後の `{ "key":` または `[ "key":` (`[` は通常ありえないが念のため)
        m = re.search(r'([\{\[])\s*"[^"\\]*(?:\\.[^"\\]*)*"\s*:\s*$', s)
        if m:
            s = s[: m.end(1)]
            continue

        # `, "key"` (コロンも値もない孤立 key) → object 内のときだけ削除
        m = re.search(r',\s*"[^"\\]*(?:\\.[^"\\]*)*"\s*$', s)
        if m:
            container = _current_container_type(s[: m.start()])
            if container == "{":
                s = s[: m.start()]
                continue

        # 末尾の単独カンマ
        if s.endswith(","):
            s = s[:-1]
            continue

    return s


def _balance_brackets(s: str) -> str:
    """閉じカッコ `}` `]` をスタック順 (LIFO) で補完する。

    文字列リテラル内のカッコは無視する。負のバランス (閉じすぎ) は
    補完しない (= そのまま json.loads に渡して失敗させる)。
    """
    stack: list[str] = []
    in_string = False
    escape = False

    for ch in s:
        if escape:
            escape = False
            continue
        if ch == "\\":
            if in_string:
                escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch in "}]":
            if stack and stack[-1] == ch:
                stack.pop()

    s = s.rstrip().rstrip(",").rstrip()
    while stack:
        s += stack.pop()
    return s
