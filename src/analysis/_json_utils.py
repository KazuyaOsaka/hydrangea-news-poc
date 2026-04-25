"""分析レイヤー内で共通利用する LLM 応答 JSON パーサ。

perspective_selector.parse_json_response を Batch 3 の multi_angle_analyzer /
insight_extractor からも再利用できるよう、純粋関数として切り出した。

挙動は perspective_selector.parse_json_response と完全に同じ:
  - ```json ... ``` のコードフェンスを除去
  - 全文として JSON 解釈に失敗した場合は最初の `{...}` ブロックを抽出
  - 最終的に json.loads でパースし、失敗時は json.JSONDecodeError を伝播
"""
from __future__ import annotations

import json
import re


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


def parse_json_response(raw: str) -> dict:
    """LLM 応答から JSON 本体を抽出して dict にする。

    - コードフェンスを除去
    - 全文として JSON 解釈に失敗した場合は最初の `{...}` ブロックを試す
    """
    text = _strip_code_fence(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group())
