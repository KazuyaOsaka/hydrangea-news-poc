"""分析レイヤー Step 3: 観点選定 + 検証（LLM 1 回呼び出しで完結）。

設計書 Section 4.2 Step 3, Section 5.3 の仕様に従う。

Top3 観点候補を LLM に渡し、最も「視聴者が賢くなる体験」を提供できる軸を
1 つ選ばせ、同じ呼び出しで成立を検証する（Select & Verify in one call）。

検証で当該軸が成立しない場合は段階的フォールバックを適用する（F-3 で強化）:
    Step 1: LLM 提示の fallback_axis_if_failed を Top3 から探して採用
    Step 2: ★F-3 NEW: Top3 内の最高スコア候補を採用 (fallback の fallback)
    Step 3: candidates が空の場合のみ None を返す（最終安全網）

これにより candidates が 1 件以上あれば必ず PerspectiveCandidate を返し、
analysis_result が None になるケースを排除する。

framing_inversion が成立した場合は framing_divergence_bonus +2.0 を後加算する
（設計書 Section 5.2 軸2、Batch 2 の TODO として引き継がれた要件）。
"""
from __future__ import annotations

import json
from typing import Optional

from src.analysis._json_utils import parse_json_response as _parse_json_response
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


def parse_json_response(raw: str) -> dict:
    """LLM 応答から JSON 本体を抽出して dict にする。

    実装は src/analysis/_json_utils.py に移動済み。後方互換のため
    （既存テストや他モジュールが本モジュールから import しているため）
    薄いプロキシとして残している。
    """
    return _parse_json_response(raw)


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
        why_now=candidate.why_now,
    )


def _top_score_candidate(
    candidates: list[PerspectiveCandidate],
) -> Optional[PerspectiveCandidate]:
    """候補リスト内で最高スコアの候補を返す（同点なら最初に出現したもの）。"""
    if not candidates:
        return None
    return max(candidates, key=lambda c: c.score)


def select_perspective(
    scored_event: ScoredEvent,
    perspective_candidates: list[PerspectiveCandidate],
    context: AnalysisContext,
    *,
    client: Optional[LLMClient] = None,
) -> Optional[PerspectiveCandidate]:
    """設計書 Section 5.3 のフロー (F-3 改修版)。

    Top3 → LLM Select & Verify → 段階的 fallback 適用。

    フォールバック順序:
        Step 1: LLM 提示の fallback_axis_if_failed を Top3 から探して採用 (既存)
        Step 2: ★F-3 NEW: Top3 内の最高スコア候補を採用 (fallback の fallback)
        Step 3: candidates が空の場合のみ None (最終安全網)

    各段階で fallback が発動した場合、警告ログを出して可視化する。
    LLM 呼び出しが例外で失敗した場合も Step 2 にフォールバックして
    candidates が 1 件以上あれば必ず採用する（analysis_result=None を回避）。

    framing_inversion が成立と判定された候補には framing_divergence_bonus +2.0 を加算。

    Returns:
        採用された PerspectiveCandidate、または None（candidates 空のときのみ）。
    """
    if not perspective_candidates:
        logger.error(
            f"[PerspectiveSelector] Step3 critical: perspective_candidates is empty "
            f"for event={scored_event.event.id[:16]}. Returning None."
        )
        return None

    event_id_short = scored_event.event.id[:16]

    try:
        result = llm_select_and_verify_perspective(
            scored_event,
            perspective_candidates,
            context,
            client=client,
        )
    except Exception as exc:
        # LLM 失敗時も Step 2 へフォールバック（candidates が残っているなら採用する）
        top = _top_score_candidate(perspective_candidates)
        logger.warning(
            f"[PerspectiveSelector] Step2 fallback (F-3): LLM select+verify failed for "
            f"event={event_id_short}: {exc}. "
            f"Using highest-scoring candidate: axis={top.axis} (score={top.score:.2f})"
        )
        return _apply_framing_bonus_if_needed(top)

    selected_axis = str(result.get("selected_axis", ""))
    verification = result.get("verification") or {}
    actually_holds = bool(verification.get("actually_holds", False))
    fallback_axis_raw = result.get("fallback_axis_if_failed")
    fallback_axis = str(fallback_axis_raw) if fallback_axis_raw else None

    selected_candidate = (
        _find_candidate(perspective_candidates, selected_axis)
        if selected_axis in _VALID_AXES
        else None
    )

    # Step 1a: LLM 結果から selected_axis 採用 (既存)
    if selected_candidate is not None and actually_holds:
        logger.info(
            f"[PerspectiveSelector] Step1 selected: axis={selected_axis} "
            f"for event={event_id_short}"
        )
        return _apply_framing_bonus_if_needed(selected_candidate)

    # Step 1b: LLM 提示の fallback_axis_if_failed を Top3 から探す (既存)
    fallback_candidate = (
        _find_candidate(perspective_candidates, fallback_axis)
        if fallback_axis and fallback_axis in _VALID_AXES and fallback_axis != selected_axis
        else None
    )
    if fallback_candidate is not None:
        logger.warning(
            f"[PerspectiveSelector] Step1 fallback: selected_axis={selected_axis!r} not held "
            f"(in_top3={selected_candidate is not None}, actually_holds={actually_holds}), "
            f"using fallback_axis_if_failed={fallback_axis!r} for event={event_id_short}"
        )
        return _apply_framing_bonus_if_needed(fallback_candidate)

    # Step 2: ★F-3 NEW: Top3 内の最高スコア候補を採用
    # LLM の selected_axis も fallback_axis_if_failed も Top3 にない場合の救済
    top = _top_score_candidate(perspective_candidates)
    logger.warning(
        f"[PerspectiveSelector] Step2 fallback (F-3): "
        f"LLM selected_axis={selected_axis!r} not viable "
        f"(in_top3={selected_candidate is not None}, actually_holds={actually_holds}), "
        f"fallback_axis_if_failed={fallback_axis!r} also missing. "
        f"Using highest-scoring candidate: axis={top.axis} (score={top.score:.2f}) "
        f"for event={event_id_short}"
    )
    return _apply_framing_bonus_if_needed(top)
