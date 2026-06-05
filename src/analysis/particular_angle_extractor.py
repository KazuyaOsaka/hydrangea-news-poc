"""F-particular-angle-metadata-production-wire (X1): 特定角度メタデータの本番抽出。

★ 不変原則 4 例外条件適用 (カズヤ承認済): 本ファイル新規作成は src/analysis/
配下への新規追加に当たる。F-script-writer-target-enemy-fix-investigate
(2026-05-26) CP-1 で target_enemy 解消の唯一の sanctioned 経路と確定済。
例外条件 5 点充足:
  (a) target_enemy 解消 + particular_angle 起動の機能追加が目的
  (b) src/analysis/ 既存ファイル (analysis_engine.py 等) は一切変更しない
  (c) ParticularAngleMetadata の新規データ追加のみ
  (d) baseline 1432 passed 維持
  (e) カズヤ事前承認 (X1 プロンプト時点 + CP-1)

正典: docs/PARTICULAR_ANGLE_DEFINITION.md セクション 3.6-3.7。

3 つのスクリプト (extract_particular_angle / reclassify_annotations /
add_sontaku_signals、2026-05-07〜08) のロジックを 1 つの新プロンプト
(configs/prompts/analysis/geo_lens/particular_angle_extract.md) に統合し、
1 LLM call で particular_angle 3 要素 + 4 分類 stream_classification +
sontaku_signals を一括抽出する (単一パス α、CP-1 カズヤ判断)。

呼出元: src/main.py 分析ブロック (run_analysis_layer 完了直後)。本 extractor を
呼び、_analysis_result.model_copy(update={particular_angle_metadata=...}) で
AnalysisResult に metadata を付与する。失敗時は None を返し、
particular_angle_metadata=None のまま AnalysisResult を保存する (既存挙動維持)。
"""
from __future__ import annotations

import json
import re
from typing import Optional

from src.analysis.prompt_loader import load_prompt
from src.llm.base import LLMClient
from src.llm.factory import get_analysis_llm_client
from src.shared.logger import get_logger
from src.shared.models import (
    NewsEvent,
    ParticularAngleMetadata,
    ScoredEvent,
    SontakuSignals,
)

logger = get_logger(__name__)

_VALID_STREAMS = {
    "stream_1_silence_gap",
    "stream_2_perspective_gap",
    "stream_3_framing_inversion",
    "out_of_scope",
}
_VALID_LEVELS = {"high", "medium", "low", "none"}
_VALID_TYPES = {"diplomatic", "domestic", "media_industry"}
_VALID_CONFIDENCES = {"high", "medium", "low"}


def _format_sources(event: NewsEvent) -> str:
    """NewsEvent から sources 文字列 (重複排除済) を組み立てる。

    sources_by_locale (新形式) を優先し、後方互換 sources_jp / sources_en、
    最終フォールバックとして event.source を使う。
    """
    names: list[str] = []
    seen: set[str] = set()
    for refs in event.sources_by_locale.values():
        for ref in refs:
            name = getattr(ref, "name", None)
            if name and name not in seen:
                names.append(name)
                seen.add(name)
    if not names:
        for ref in list(event.sources_jp) + list(event.sources_en):
            name = getattr(ref, "name", None)
            if name and name not in seen:
                names.append(name)
                seen.add(name)
    if not names and event.source:
        names.append(event.source)
    return ", ".join(names) if names else "(no sources)"


def _escape_unescaped_newlines_in_strings(s: str) -> str:
    """JSON 文字列値中の生の改行を \\n にエスケープする最小修復。

    extract_particular_angle.py:_escape_unescaped_newlines_in_strings (2026-05-07)
    から流用。LLM が複数行に分けて文字列値を出力した場合の救済。
    """
    out: list[str] = []
    in_string = False
    escape = False
    for ch in s:
        if escape:
            out.append(ch)
            escape = False
            continue
        if ch == "\\":
            out.append(ch)
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            out.append(ch)
            continue
        if in_string and ch == "\n":
            out.append("\\n")
            continue
        if in_string and ch == "\r":
            out.append("\\r")
            continue
        if in_string and ch == "\t":
            out.append("\\t")
            continue
        out.append(ch)
    return "".join(out)


def _parse_llm_response(text: str) -> dict:
    """LLM 応答テキストから JSON を抽出してパース。

    Markdown コードブロック (```json ... ```) 有無、生の改行混入の両方に対応。
    """
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    candidate = fenced.group(1).strip() if fenced else text.strip()
    if not candidate.startswith("{"):
        i = candidate.find("{")
        if i >= 0:
            candidate = candidate[i:]
    if not candidate.endswith("}"):
        j = candidate.rfind("}")
        if j >= 0:
            candidate = candidate[: j + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        fixed = _escape_unescaped_newlines_in_strings(candidate)
        return json.loads(fixed)


def _coerce_confidence(v: object) -> str:
    """confidence / extraction_confidence を valid set に正規化 (不明値は medium)。"""
    s = str(v or "").strip().lower()
    return s if s in _VALID_CONFIDENCES else "medium"


def _coerce_stream(v: object) -> str:
    """stream_classification を valid set に正規化 (不明値は out_of_scope)。"""
    s = str(v or "").strip()
    return s if s in _VALID_STREAMS else "out_of_scope"


def _coerce_level(v: object) -> str:
    """sontaku level を valid set に正規化 (不明値は none)。"""
    s = str(v or "").strip().lower()
    return s if s in _VALID_LEVELS else "none"


def _coerce_type(v: object, level: str) -> Optional[str]:
    """sontaku type を valid set に正規化。level=none なら強制 None。

    add_sontaku_signals.py:_validate (2026-05-08) の coerce ロジックを踏襲。
    """
    if level == "none":
        return None
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in {"null", "none", ""}:
        return None
    return s if s in _VALID_TYPES else None


def _build_particular_angle_metadata(payload: dict) -> ParticularAngleMetadata:
    """LLM 出力 dict から ParticularAngleMetadata を構築する (coercion 込)。"""
    pa = payload.get("particular_angle") or {}
    sc = payload.get("stream_classification") or {}
    ss = payload.get("sontaku_signals") or {}

    level = _coerce_level(ss.get("level"))
    sontaku = SontakuSignals(
        level=level,
        type=_coerce_type(ss.get("type"), level),
        reasoning=str(ss.get("reasoning") or "").strip(),
        extraction_confidence=_coerce_confidence(ss.get("extraction_confidence")),
    )
    return ParticularAngleMetadata(
        stream_classification=_coerce_stream(sc.get("estimated_stream")),
        core_question=str(pa.get("core_question") or "").strip(),
        differentiation_from_mainstream=str(
            pa.get("differentiation_from_mainstream") or ""
        ).strip(),
        hydrangea_axis_alignment=str(pa.get("hydrangea_axis_alignment") or "").strip(),
        extraction_confidence=_coerce_confidence(pa.get("extraction_confidence")),
        sontaku_signals=sontaku,
    )


def extract_particular_angle_metadata(
    event: NewsEvent,
    *,
    channel_id: str = "geo_lens",
    client: Optional[LLMClient] = None,
    max_retries: int = 2,
) -> Optional[ParticularAngleMetadata]:
    """1 件の NewsEvent から particular_angle_metadata を一括抽出する。

    単一パス α (CP-1 カズヤ判断): 1 LLM call で 3 要素 (core_question /
    differentiation_from_mainstream / hydrangea_axis_alignment) + 4 分類
    stream_classification + sontaku_signals を抽出する。

    LLM クライアントは get_analysis_llm_client() 経由 (Gemini 3 系 temperature
    ガード + ANALYSIS_LLM_MAX_TOKENS env が自動適用、F-gemini-quality-tier-poc
    整合)。プロンプトは
    configs/prompts/analysis/{channel_id}/particular_angle_extract.md。

    Args:
        event: 対象 NewsEvent。
        channel_id: プロンプト解決用 (default "geo_lens")。
        client: テスト時の依存注入用。None なら get_analysis_llm_client()。
        max_retries: LLM 呼出失敗時のリトライ回数 (default 2)。

    Returns:
        ParticularAngleMetadata or None (LLM 失敗 / クライアント未取得 /
        パース失敗時)。None の場合は呼出側 (main.py) で
        analysis_result.particular_angle_metadata=None のまま保存し、
        script_writer は metadata 不在で進む (後方互換、既存挙動)。
    """
    llm = client if client is not None else get_analysis_llm_client()
    if llm is None:
        logger.warning(
            f"[ParticularAngleExtractor] no analysis LLM client available for "
            f"event_id={event.id}; returning None."
        )
        return None

    try:
        template = load_prompt(channel_id, "particular_angle_extract")
    except FileNotFoundError as exc:
        logger.error(f"[ParticularAngleExtractor] prompt not found: {exc}")
        return None

    summary = (event.summary or "").replace("\n", " ")
    title = event.title or ""
    sources = _format_sources(event)
    prompt = template.format(
        event_id=event.id,
        title=title,
        summary=summary,
        sources=sources,
    )

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            raw = llm.generate(prompt)
            if not raw or not raw.strip():
                raise ValueError("LLM returned empty response")
            payload = _parse_llm_response(raw)
            metadata = _build_particular_angle_metadata(payload)
            logger.info(
                f"[ParticularAngleExtractor] event_id={event.id} "
                f"stream={metadata.stream_classification} "
                f"sontaku_level="
                f"{metadata.sontaku_signals.level if metadata.sontaku_signals else 'none'} "
                f"confidence={metadata.extraction_confidence}"
            )
            return metadata
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            last_error = exc
            logger.warning(
                f"[ParticularAngleExtractor] event_id={event.id} attempt "
                f"{attempt}/{max_retries} parse error: {str(exc)[:150]}"
            )
        except Exception as exc:
            last_error = exc
            logger.warning(
                f"[ParticularAngleExtractor] event_id={event.id} attempt "
                f"{attempt}/{max_retries} api error: "
                f"{type(exc).__name__}: {str(exc)[:150]}"
            )

    logger.error(
        f"[ParticularAngleExtractor] event_id={event.id} all {max_retries} attempts "
        f"failed; returning None. last_error={last_error}"
    )
    return None


def extract_for_scored_event(
    scored_event: ScoredEvent,
    *,
    channel_id: str = "geo_lens",
    client: Optional[LLMClient] = None,
) -> Optional[ParticularAngleMetadata]:
    """ScoredEvent ラッパー — main.py の呼出をシンプルに保つ。"""
    return extract_particular_angle_metadata(
        scored_event.event, channel_id=channel_id, client=client
    )
