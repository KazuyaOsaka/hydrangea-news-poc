"""分析レイヤー Step 5 (Step 7 in instructions): 洞察抽出。

設計書 Section 8 の仕様に従う。多角的分析の 5 観点を入力に
「視聴者が人に話したくなる核心情報」3〜5 個を **1 回の LLM 呼び出し** で抽出する。

LLM クライアントは get_analysis_llm_client() を共用（Batch 2 引継ぎ事項）。
プロンプトは configs/prompts/analysis/{channel_id}/insights_extract.md。
JSON パースは _json_utils.parse_json_response を再利用。
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
    Insight,
    MultiAngleAnalysis,
    PerspectiveCandidate,
)

logger = get_logger(__name__)

# 設計書 Section 8.1: 3〜5 個。
_MIN_INSIGHTS = 3
_MAX_INSIGHTS = 5


def _format_snippets_for_prompt(snippets: list[dict]) -> str:
    return "\n".join(json.dumps(s, ensure_ascii=False) for s in snippets[:20])


def _build_prompt(
    perspective: PerspectiveCandidate,
    multi_angle: MultiAngleAnalysis,
    context: AnalysisContext,
    channel_id: str,
) -> str:
    template = load_prompt(channel_id, "insights_extract")
    return template.format(
        selected_axis=perspective.axis,
        selected_axis_reasoning=perspective.reasoning,
        geopolitical=multi_angle.geopolitical or "(none)",
        political_intent=multi_angle.political_intent or "(none)",
        economic_impact=multi_angle.economic_impact or "(none)",
        cultural_context=multi_angle.cultural_context or "(none)",
        media_divergence=multi_angle.media_divergence or "(none)",
        article_snippets=_format_snippets_for_prompt(context.article_snippets),
    )


def _coerce_importance(value: object) -> float:
    """importance を 0.0〜1.0 にクランプする。

    LLM は「0.95」「95」「'high'」など雑多な形で返してくることがあるため、
    数値化できない場合は 0.5 にフォールバック。1.0 を超えていれば /100 を試す。
    """
    if isinstance(value, bool):
        return 0.5
    if isinstance(value, (int, float)):
        v = float(value)
    elif isinstance(value, str):
        try:
            v = float(value.strip())
        except ValueError:
            return 0.5
    else:
        return 0.5

    # v >= 2.0 は「90」のような 0〜100 スケールで返ってきたケースとみなして
    # /100 で再正規化する。1.0 < v < 2.0 は「ちょっと超えただけ」として 1.0 にクランプ。
    if v >= 2.0:
        v = v / 100.0
    if v < 0.0:
        v = 0.0
    if v > 1.0:
        v = 1.0
    return v


def _coerce_evidence_refs(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if x is not None]
    if isinstance(value, str):
        return [value] if value else []
    return [str(value)]


def _parse_insight_item(item: object) -> Optional[Insight]:
    if not isinstance(item, dict):
        return None
    text = item.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    return Insight(
        text=text.strip(),
        importance=_coerce_importance(item.get("importance")),
        evidence_refs=_coerce_evidence_refs(item.get("evidence_refs")),
    )


def extract_insights(
    multi_angle: MultiAngleAnalysis,
    perspective: PerspectiveCandidate,
    context: AnalysisContext,
    *,
    client: Optional[LLMClient] = None,
    channel_id: Optional[str] = None,
) -> list[Insight]:
    """LLM 呼び出し 1 回で 3〜5 個の Insight を抽出する。

    LLM が 5 個を超えて返した場合は importance 降順で上位 _MAX_INSIGHTS に絞る。
    3 個未満の場合は警告ログを出すが、得られた分だけ返す（呼び出し側で扱う）。
    """
    if client is None:
        client = get_analysis_llm_client()
    if client is None:
        raise RuntimeError(
            "Analysis LLM client is unavailable (GEMINI_API_KEY 未設定 or プロバイダ未対応)."
        )

    used_channel = channel_id or context.channel_id or "geo_lens"
    prompt = _build_prompt(perspective, multi_angle, context, channel_id=used_channel)

    raw = client.generate(prompt)
    parsed = parse_json_response(raw)

    if not isinstance(parsed, dict):
        raise ValueError(
            f"insights_extract LLM response is not a JSON object: type={type(parsed)!r}"
        )

    items_raw = parsed.get("insights")
    if not isinstance(items_raw, list):
        raise ValueError(
            f"insights_extract response missing 'insights' array: keys={list(parsed.keys())}"
        )

    insights: list[Insight] = []
    for item in items_raw:
        parsed_item = _parse_insight_item(item)
        if parsed_item is not None:
            insights.append(parsed_item)

    if len(insights) > _MAX_INSIGHTS:
        insights.sort(key=lambda i: i.importance, reverse=True)
        insights = insights[:_MAX_INSIGHTS]

    if len(insights) < _MIN_INSIGHTS:
        logger.warning(
            f"[InsightExtractor] Got only {len(insights)} insights "
            f"(min={_MIN_INSIGHTS}); returning what we have."
        )

    return insights
