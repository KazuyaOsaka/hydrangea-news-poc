"""分析レイヤー Step 3: 観点選定 + 検証（LLM 1 回呼び出しで完結）。

設計書 Section 4.2 Step 3, Section 5.3 の仕様に従う。

Top3 観点候補を LLM に渡し、最も「視聴者が賢くなる体験」を提供できる軸を
1 つ選ばせ、同じ呼び出しで成立を検証する（Select & Verify in one call）。

検証で当該軸が成立しない場合は、LLM が提示する fallback_axis_if_failed を
Top3 内の候補から選択し直して返す。fallback も成立しない / 候補にない場合は None。

framing_inversion が成立した場合は framing_divergence_bonus +2.0 を後加算する
（設計書 Section 5.2 軸2、Batch 2 の TODO として引き継がれた要件）。
"""
from __future__ import annotations

import json
import re
from typing import Optional

from src.analysis.context_builder import AnalysisContext
from src.analysis.prompt_loader import load_prompt
from src.llm.base import LLMClient
from src.llm.factory import get_analysis_llm_client
from src.shared.logger import get_logger
from src.shared.models import PerspectiveCandidate, ScoredEvent

logger = get_logger(__name__)

# framing_inversion が LLM で「成立」と検証されたときの加点（設計書 5.2 軸2）。
_FRAMING_DIVERGENCE_BONUS = 2.0

_VALID_AXES = {
    "silence_gap",
    "framing_inversion",
    "hidden_stakes",
    "cultural_blindspot",
}


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


def _format_candidates_for_prompt(candidates: list[PerspectiveCandidate]) -> str:
    """LLM に渡しやすい JSON-like テキストへ整形する。"""
    lines: list[str] = []
    for i, c in enumerate(candidates, start=1):
        lines.append(
            json.dumps(
                {
                    "rank": i,
                    "axis": c.axis,
                    "score": round(c.score, 2),
                    "reasoning": c.reasoning,
                    "evidence_refs": c.evidence_refs[:5],
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines)


def _format_snippets_for_prompt(snippets: list[dict]) -> str:
    """記事スニペットを 1 行 JSON で整形（LLM コンテキストを節約）。"""
    return "\n".join(json.dumps(s, ensure_ascii=False) for s in snippets[:20])


def _format_questions_for_prompt(questions: list[str]) -> str:
    return "\n".join(questions)


def _build_prompt(
    candidates: list[PerspectiveCandidate],
    context: AnalysisContext,
    channel_id: str = "geo_lens",
) -> str:
    template = load_prompt(channel_id, "perspective_select_and_verify")
    return template.format(
        perspective_candidates=_format_candidates_for_prompt(candidates),
        article_snippets=_format_snippets_for_prompt(context.article_snippets),
        background_questions=_format_questions_for_prompt(context.background_questions),
    )


def llm_select_and_verify_perspective(
    scored_event: ScoredEvent,
    candidates: list[PerspectiveCandidate],
    context: AnalysisContext,
    *,
    client: Optional[LLMClient] = None,
    channel_id: Optional[str] = None,
) -> dict:
    """1 回の LLM 呼び出しで観点選定 + 検証を行う。

    Returns:
        パース済み dict。最低限以下のキーを含む（LLM 出力に依存）:
            selected_axis, reasoning, evidence_for_selection,
            verification: {actually_holds, notes, confidence},
            fallback_axis_if_failed
    """
    if not candidates:
        raise ValueError("perspective candidates must be non-empty")
    used_channel = channel_id or context.channel_id or scored_event.channel_id or "geo_lens"
    llm_client = client if client is not None else get_analysis_llm_client()
    if llm_client is None:
        raise RuntimeError(
            "Analysis LLM client is unavailable (GEMINI_API_KEY 未設定 or プロバイダ未対応)."
        )

    prompt = _build_prompt(candidates, context, channel_id=used_channel)
    raw = llm_client.generate(prompt)
    return parse_json_response(raw)


def _find_candidate(
    candidates: list[PerspectiveCandidate], axis: str
) -> Optional[PerspectiveCandidate]:
    for c in candidates:
        if c.axis == axis:
            return c
    return None


def _apply_framing_bonus_if_needed(candidate: PerspectiveCandidate) -> PerspectiveCandidate:
    """framing_inversion が成立と判定された場合に +bonus を加える。

    上限 10.0 を超えないようにクランプする。score 以外のフィールドは新しい
    PerspectiveCandidate に転記し、reasoning に加点した旨を追記する。
    """
    if candidate.axis != "framing_inversion":
        return candidate
    new_score = min(10.0, candidate.score + _FRAMING_DIVERGENCE_BONUS)
    if new_score == candidate.score:
        return candidate
    return PerspectiveCandidate(
        axis=candidate.axis,
        score=new_score,
        reasoning=(
            f"{candidate.reasoning} [+framing_divergence_bonus "
            f"+{_FRAMING_DIVERGENCE_BONUS:.1f} (LLM verified)]"
        ),
        evidence_refs=list(candidate.evidence_refs),
    )


def select_perspective(
    scored_event: ScoredEvent,
    perspective_candidates: list[PerspectiveCandidate],
    context: AnalysisContext,
    *,
    client: Optional[LLMClient] = None,
) -> Optional[PerspectiveCandidate]:
    """設計書 Section 5.3 のフロー。

    Top3 → LLM Select & Verify → 必要時 fallback 適用。

    フロー:
        1. LLM に Top3 を渡し選定+検証を 1 回で実行
        2. selected_axis が Top3 にあり verification.actually_holds=True ならその候補を採用
        3. actually_holds=False の場合、fallback_axis_if_failed を Top3 から探して採用
        4. どちらも見つからない場合は None を返す（呼び出し側で None 扱い）

    framing_inversion が成立と判定された候補には framing_divergence_bonus +2.0 を加算。

    Returns:
        採用された PerspectiveCandidate、または None（採用できる候補なし）。
    """
    if not perspective_candidates:
        return None

    try:
        result = llm_select_and_verify_perspective(
            scored_event,
            perspective_candidates,
            context,
            client=client,
        )
    except Exception as exc:
        logger.warning(
            f"[PerspectiveSelector] LLM select+verify failed for "
            f"event={scored_event.event.id}: {exc}"
        )
        return None

    selected_axis = str(result.get("selected_axis", ""))
    verification = result.get("verification") or {}
    actually_holds = bool(verification.get("actually_holds", False))
    fallback_axis = result.get("fallback_axis_if_failed")

    if selected_axis not in _VALID_AXES:
        logger.warning(
            f"[PerspectiveSelector] LLM returned invalid axis "
            f"{selected_axis!r} for event={scored_event.event.id}"
        )
        # selected_axis が無効でも fallback が有効なら使う
        if fallback_axis in _VALID_AXES:
            cand = _find_candidate(perspective_candidates, str(fallback_axis))
            return _apply_framing_bonus_if_needed(cand) if cand else None
        return None

    selected = _find_candidate(perspective_candidates, selected_axis)
    if selected is None:
        # LLM が Top3 にない軸を返したケース
        logger.warning(
            f"[PerspectiveSelector] LLM selected axis {selected_axis!r} not in Top3 "
            f"for event={scored_event.event.id}"
        )
        if fallback_axis in _VALID_AXES:
            cand = _find_candidate(perspective_candidates, str(fallback_axis))
            return _apply_framing_bonus_if_needed(cand) if cand else None
        return None

    if actually_holds:
        return _apply_framing_bonus_if_needed(selected)

    # 成立しない → fallback_axis を Top3 から採用
    if fallback_axis and fallback_axis in _VALID_AXES and fallback_axis != selected_axis:
        fb = _find_candidate(perspective_candidates, str(fallback_axis))
        if fb is not None:
            logger.info(
                f"[PerspectiveSelector] LLM rejected {selected_axis!r} for "
                f"event={scored_event.event.id}; falling back to {fallback_axis!r}"
            )
            return _apply_framing_bonus_if_needed(fb)

    logger.info(
        f"[PerspectiveSelector] No viable perspective for event={scored_event.event.id} "
        f"(selected={selected_axis!r} verified=False, fallback={fallback_axis!r})"
    )
    return None
