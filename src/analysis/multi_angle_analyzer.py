"""分析レイヤー Step 4 (Step 6 in instructions): 多角的分析。

設計書 Section 7 の 5 観点（geopolitical / political_intent / economic_impact /
cultural_context / media_divergence）を **1 回の LLM 呼び出し** で生成する。

LLM クライアントは get_analysis_llm_client() を使う（Batch 2 と同じルート）。
プロンプトは configs/prompts/analysis/{channel_id}/multi_angle_analysis.md から
load_prompt() で読み込む。JSON パースは _json_utils.parse_json_response を再利用。
"""
from __future__ import annotations

import json
from typing import Optional

from src.analysis._json_utils import parse_json_response
from src.analysis.context_builder import AnalysisContext
from src.analysis.prompt_loader import load_prompt
from src.llm.base import LLMClient
from src.llm.factory import get_analysis_llm_client
from src.shared.logger import get_logger
from src.shared.models import (
    MultiAngleAnalysis,
    PerspectiveCandidate,
    ScoredEvent,
)

logger = get_logger(__name__)

_REQUIRED_KEYS = (
    "geopolitical",
    "political_intent",
    "economic_impact",
    "cultural_context",
    "media_divergence",
)


def _format_snippets_for_prompt(snippets: list[dict]) -> str:
    """記事スニペットを 1 行 JSON で整形（LLM コンテキストを節約）。"""
    return "\n".join(json.dumps(s, ensure_ascii=False) for s in snippets[:20])


def _format_questions_for_prompt(questions: list[str]) -> str:
    return "\n".join(questions)


def _build_prompt(
    perspective: PerspectiveCandidate,
    context: AnalysisContext,
    channel_id: str,
) -> str:
    template = load_prompt(channel_id, "multi_angle_analysis")
    return template.format(
        selected_axis=perspective.axis,
        selected_axis_reasoning=perspective.reasoning,
        event_title=context.event_title,
        event_summary=context.event_summary,
        article_snippets=_format_snippets_for_prompt(context.article_snippets),
        background_questions=_format_questions_for_prompt(context.background_questions),
    )


def _coerce_to_str(value: object) -> Optional[str]:
    """LLM 出力が dict / list / None / str いずれでも文字列に正規化する。

    LLM が "geopolitical": null を返したり、想定外の構造を返したケースでも
    MultiAngleAnalysis (Optional[str]) に格納できるようにするためのガード。
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    # dict / list 等は JSON 文字列化して保持（後段で人間が読めばよい）
    return json.dumps(value, ensure_ascii=False)


def perform_multi_angle_analysis(
    scored_event: ScoredEvent,
    perspective: PerspectiveCandidate,
    context: AnalysisContext,
    *,
    client: Optional[LLMClient] = None,
    channel_id: Optional[str] = None,
) -> MultiAngleAnalysis:
    """1 回の LLM 呼び出しで 5 観点すべて生成する。

    LLM 呼び出し / パース / フィールド欠落でも例外を握りつぶさず raise する。
    呼び出し側（analysis_engine）が try/except で Optional[AnalysisResult] にする
    フォールバック方針を採るため、ここでは欠損は例外で明示する方針。
    """
    if client is None:
        client = get_analysis_llm_client()
    if client is None:
        raise RuntimeError(
            "Analysis LLM client is unavailable (GEMINI_API_KEY 未設定 or プロバイダ未対応)."
        )

    used_channel = channel_id or context.channel_id or scored_event.channel_id or "geo_lens"
    prompt = _build_prompt(perspective, context, channel_id=used_channel)

    raw = client.generate(prompt)
    parsed = parse_json_response(raw)

    if not isinstance(parsed, dict):
        raise ValueError(
            f"multi_angle_analysis LLM response is not a JSON object: type={type(parsed)!r}"
        )

    missing = [k for k in _REQUIRED_KEYS if k not in parsed]
    if missing:
        logger.warning(
            f"[MultiAngleAnalyzer] LLM response missing keys {missing} for "
            f"event={scored_event.event.id}; filling with None."
        )

    return MultiAngleAnalysis(
        geopolitical=_coerce_to_str(parsed.get("geopolitical")),
        political_intent=_coerce_to_str(parsed.get("political_intent")),
        economic_impact=_coerce_to_str(parsed.get("economic_impact")),
        cultural_context=_coerce_to_str(parsed.get("cultural_context")),
        media_divergence=_coerce_to_str(parsed.get("media_divergence")),
    )
