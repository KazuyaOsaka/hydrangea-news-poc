"""分析レイヤー Step 9: オーケストレータ。

設計書 Section 4.2 のフロー全体を 1 関数で束ねる。

ステップ構成:
    Step 1: 観点候補ルールベース抽出 (LLM なし)
    Step 2: コンテキスト構築           (LLM なし)
    Step 3: 観点選定 + 検証            (LLM 1 回、fallback 時最大 +0)
    Step 4: 多角的分析                 (LLM 1 回)
    Step 5: 洞察抽出                   (LLM 1 回)
    Step 6: 動画尺プロファイル選定     (LLM なし)
    Step 7: ビジュアルムードタグ生成   (LLM なし、ルールベース)

Recency Guard (Step 0) は本関数の責務外。呼び出し側（main.py）が
apply_recency_guard を先に適用してから本関数を呼ぶ前提。

設計書 Section 4.4 のフォールバック方針:
    各 Step の失敗 (RuntimeError / ValueError / json.JSONDecodeError 等) は
    広く try/except Exception で捕捉して None を返す。呼び出し側は None
    を受け取ったら既存の台本生成ルートにフォールバックする。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.analysis.context_builder import build_analysis_context
from src.analysis.duration_profile_selector import (
    generate_visual_mood_tags,
    select_duration_profile,
)
from src.analysis.insight_extractor import extract_insights
from src.analysis.multi_angle_analyzer import perform_multi_angle_analysis
from src.analysis.perspective_extractor import extract_perspectives
from src.analysis.perspective_selector import select_perspective
from src.llm.base import LLMClient
from src.shared.logger import get_logger
from src.shared.models import (
    AnalysisResult,
    ChannelConfig,
    PerspectiveCandidate,
    ScoredEvent,
)

logger = get_logger(__name__)

_TOP_N_CANDIDATES = 3


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_verification_notes(selected: PerspectiveCandidate) -> str:
    """selected_perspective.reasoning を verification_notes の起点にする。

    perspective_selector がスコアと（必要なら）framing_divergence_bonus 情報を
    reasoning に折り込んでくれているので、それを再利用する。
    """
    return f"axis={selected.axis} score={selected.score:.2f} | {selected.reasoning}"


def run_analysis_layer(
    scored_event: ScoredEvent,
    channel_config: ChannelConfig,
    db_path: Path,
    *,
    llm_client: Optional[LLMClient] = None,
) -> Optional[AnalysisResult]:
    """設計書 Section 4.2 のフローをオーケストレートする。

    Args:
        scored_event:    分析対象のイベント（Recency Guard 通過済み想定）。
        channel_config:  チャンネル設定（perspective_axes / duration_profiles を参照）。
        db_path:         SQLite DB パス（Step 0 の Recency Guard 用に予約。本関数内では未使用）。
        llm_client:      テスト用に LLM クライアントを差し込む。None なら各 Step が
                         get_analysis_llm_client() を使用。

    Returns:
        AnalysisResult: 全 Step が成功した場合の構造化分析結果。
        None:           いずれかの Step が失敗した、または 4 軸全部不成立の場合。
                        呼び出し側は既存の台本生成ルートにフォールバックする。
    """
    started_at = _now_iso()
    llm_calls = 0

    try:
        # Step 1: 観点候補抽出（ルールベース）
        candidates = extract_perspectives(scored_event, channel_config)
        if not candidates:
            logger.info(
                f"[AnalysisEngine] event={scored_event.event.id}: "
                f"no perspective candidates met conditions; skipping analysis layer."
            )
            return None

        top_n = candidates[:_TOP_N_CANDIDATES]

        # Step 2: コンテキスト構築（LLM なし）
        context = build_analysis_context(scored_event, top_n, channel_config)

        # Step 3: 観点選定 + 検証（LLM 1 回）
        selected = select_perspective(scored_event, top_n, context, client=llm_client)
        llm_calls += 1
        if selected is None:
            logger.info(
                f"[AnalysisEngine] event={scored_event.event.id}: "
                f"perspective selection failed; falling back to legacy route."
            )
            return None

        # Step 4: 多角的分析（LLM 1 回）
        multi_angle = perform_multi_angle_analysis(
            scored_event, selected, context, client=llm_client
        )
        llm_calls += 1

        # Step 5: 洞察抽出（LLM 1 回）
        insights = extract_insights(multi_angle, selected, context, client=llm_client)
        llm_calls += 1

        # Step 6: 動画尺プロファイル選定（ルールベース）
        # Batch 3 引継ぎ事項: scored_event はキーワード引数で渡す。
        duration_profile = select_duration_profile(
            selected,
            insights,
            multi_angle,
            channel_config,
            scored_event=scored_event,
        )

        # Step 7: ビジュアルムードタグ生成（ルールベース）
        visual_tags = generate_visual_mood_tags(selected)

        # rejected_perspectives は Top-N のうち selected 以外を保持
        rejected = [c for c in top_n if c.axis != selected.axis]

        return AnalysisResult(
            event_id=scored_event.event.id,
            channel_id=channel_config.channel_id,
            selected_perspective=selected,
            rejected_perspectives=rejected,
            perspective_verified=True,
            verification_notes=_build_verification_notes(selected),
            multi_angle=multi_angle,
            insights=insights,
            selected_duration_profile=duration_profile,
            expanded_sources=[],
            visual_mood_tags=visual_tags,
            analysis_version="v1.0",
            generated_at=started_at,
            llm_calls_used=llm_calls,
        )

    except Exception as exc:
        # Batch 3 引継ぎ事項: 各 Step は RuntimeError / ValueError /
        # json.JSONDecodeError 等を raise する。広く Exception で捕捉して None。
        logger.error(
            f"[AnalysisEngine] Analysis layer failed for event={scored_event.event.id} "
            f"(channel={channel_config.channel_id}, llm_calls={llm_calls}): "
            f"{type(exc).__name__}: {exc}",
            exc_info=True,
        )
        return None


def save_analysis_json(
    analysis_result: AnalysisResult,
    output_dir: Path,
) -> Path:
    """{event_id}_analysis.json として保存する。

    Args:
        analysis_result: 保存対象。
        output_dir:      出力ディレクトリ（存在しなければ作成）。

    Returns:
        書き出したファイルのパス。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{analysis_result.event_id}_analysis.json"
    output_path.write_text(
        analysis_result.model_dump_json(indent=2),
        encoding="utf-8",
    )
    logger.info(
        f"[AnalysisEngine] Saved analysis JSON: {output_path} "
        f"(perspective={analysis_result.selected_perspective.axis}, "
        f"insights={len(analysis_result.insights)}, "
        f"profile={analysis_result.selected_duration_profile})"
    )
    return output_path
