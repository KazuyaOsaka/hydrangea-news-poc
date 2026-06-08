"""F-title-guard-coverage-claim-policy (1-Q.5): coverage claim 事実整合 guard。

生成済みの title (タイトル層) と article (記事本文) の coverage claim
(報道状態の主張) が、その素材の系統判定 (stream_classification) が示す事実と
整合しているかを **生成後** に検証する安全網。

★ 設計の核心 (クラウド誤り 9「各論コントロールへの誘惑」回避):
  本 guard は「どう書くべきか」を機械が決める各論コントロールではない。
  「自分の系統判定 (stream_classification) に反する coverage claim をしている」
  という **事実不整合だけ** を検出する事実整合検証である。表現・言い回しの良し悪しは
  一切評価しない。判定基準は configs/coverage_claim_policy.yaml (両層で共有)。

★ 判定方式 (キーワードマッチ不採用):
  未報道断定の検出は LLM judge で「意味」照合する。キーワードマッチは言い換えで
  漏れる脆さ + CLAUDE.md「Stream 3 過剰検出」の轍を踏むため不採用。

★ B-3' 原則 (沈黙を矛盾と読み替えない):
  LLM が「明示的に矛盾している」と判定した場合 (status=contradiction) のみ flag。
  uncertain / 沈黙 / 解釈の余地がある場合は flag しない。

★ アクション: 検出 → flag のみ。自動置換・自動再生成はしない (第一作は手動、
  表現の最終判断はカズヤ)。本 guard は article_writer.py / script_writer.py の
  既存ルートに一切触れず、生成成果物を **外から** 検証する (不変原則 1-2 厳守)。

呼出例 (production wiring は本バッチ範囲外、第一作 1-S / 観測後に判断):
    result = run_coverage_claim_guard(scored_event, video_script, article.markdown)
    if result.flagged:
        for flag in result.flags:
            logger.warning(f"[CoverageClaimGuard] {flag.artifact}: {flag.span!r} "
                           f"({flag.forbidden_category}) — {flag.reasoning}")
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field

from src.analysis.prompt_loader import load_prompt
from src.llm.base import LLMClient
from src.llm.factory import get_analysis_llm_client
from src.shared.logger import get_logger

if TYPE_CHECKING:
    from src.shared.models import ScoredEvent, VideoScript

logger = get_logger(__name__)

_POLICY_PATH = Path(__file__).resolve().parents[2] / "configs" / "coverage_claim_policy.yaml"

# guard 出力 status の語彙
_STATUS_CONTRADICTION = "contradiction"
_STATUS_CONSISTENT = "consistent"
_STATUS_UNCERTAIN = "uncertain"
_VALID_STATUSES = {_STATUS_CONTRADICTION, _STATUS_CONSISTENT, _STATUS_UNCERTAIN}


# ── Policy モデル + ローダ (Layer 2: configs/coverage_claim_policy.yaml) ─────────

class CoverageClaimStreamPolicy(BaseModel):
    """1 系統 (stream_classification) の coverage claim 整合ルール。"""

    label: str = ""
    broad_event_reported_in_jp: Optional[bool] = None
    particular_angle_reported_in_jp: Optional[bool] = None
    allowed_claim_level: str = "unknown"
    forbidden_claim_categories: list[str] = Field(default_factory=list)
    description: str = ""


class CoverageClaimPolicy(BaseModel):
    """coverage_claim_policy.yaml 全体。"""

    version: int = 1
    streams: dict[str, CoverageClaimStreamPolicy] = Field(default_factory=dict)
    forbidden_claim_categories: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def stream_policy(self, stream_classification: str) -> CoverageClaimStreamPolicy:
        """系統に対応するポリシーを返す。未知系統は out_of_scope にフォールバック。"""
        if stream_classification in self.streams:
            return self.streams[stream_classification]
        return self.streams.get("out_of_scope", CoverageClaimStreamPolicy())


@lru_cache(maxsize=2)
def load_coverage_claim_policy(path: Path = _POLICY_PATH) -> CoverageClaimPolicy:
    """configs/coverage_claim_policy.yaml をロードする。

    読み込み失敗時は空ポリシー (全系統 forbidden なし = guard が flag しない) を返す
    graceful fallback。これにより policy 欠損で production が壊れない (安全側に倒す)。
    """
    try:
        import yaml  # type: ignore[import]

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return CoverageClaimPolicy.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[CoverageClaimGuard] Failed to load coverage_claim_policy.yaml: {exc}")
        return CoverageClaimPolicy()


# ── Guard 結果モデル ─────────────────────────────────────────────────────────

class CoverageClaimFlag(BaseModel):
    """検出された 1 件の coverage claim 矛盾 (flag のみ、是正案は持たない)。"""

    artifact: str                  # "title" | "article"
    span: str                      # 矛盾している該当箇所 (LLM が引用)
    forbidden_category: str        # event_total_silence | angle_total_silence
    reasoning: str = ""            # なぜ系統判定と矛盾するか


class CoverageClaimGuardResult(BaseModel):
    """coverage claim guard の検証結果。"""

    stream_classification: str
    flagged: bool = False          # contradiction を 1 件以上検出したか
    flags: list[CoverageClaimFlag] = Field(default_factory=list)
    title_status: str = _STATUS_CONSISTENT      # consistent | contradiction | uncertain
    article_status: str = _STATUS_CONSISTENT
    skipped: bool = False          # 真値不明 / forbidden 空 / LLM 不在で判定スキップ
    skip_reason: Optional[str] = None


# ── 真値 (stream_classification) の解決 ─────────────────────────────────────────

def resolve_stream_classification(scored_event: "ScoredEvent") -> str:
    """ScoredEvent から真値 stream_classification を引く。

    AnalysisResult.particular_angle_metadata.stream_classification を参照する。
    metadata 不在 / 未設定の場合は "out_of_scope" を返す (guard は真値不明として
    flag を抑制する = B-3')。
    """
    ar = getattr(scored_event, "analysis_result", None)
    if ar is None:
        return "out_of_scope"
    pam = getattr(ar, "particular_angle_metadata", None)
    if pam is None:
        return "out_of_scope"
    return getattr(pam, "stream_classification", None) or "out_of_scope"


# ── title 層テキストの抽出 ─────────────────────────────────────────────────────

def _build_title_block(video_script: "VideoScript") -> str:
    """VideoScript の title 層を検証用テキストブロックに整形する。"""
    tl = getattr(video_script, "title_layer", None)
    lines: list[str] = []
    if tl is not None:
        lines.append(f"platform_title: {tl.platform_title or '(none)'}")
        lines.append(f"canonical_title: {tl.canonical_title or '(none)'}")
        lines.append(f"hook_line: {tl.hook_line or '(none)'}")
        if tl.thumbnail_text:
            lines.append(f"thumbnail_text: {tl.thumbnail_text}")
    else:
        # title_layer 不在時は VideoScript.title を最低限の検証対象にする。
        lines.append(f"title: {getattr(video_script, 'title', '') or '(none)'}")
    return "\n".join(lines)


# ── LLM 応答パース ─────────────────────────────────────────────────────────────

def _parse_llm_response(text: str) -> dict:
    """LLM 応答テキストから JSON を抽出してパース (extractor と同方針)。"""
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
    return json.loads(candidate)


def _coerce_status(v: object) -> str:
    """status を valid set に正規化 (不明値は uncertain = 安全側、flag しない)。"""
    s = str(v or "").strip().lower()
    return s if s in _VALID_STATUSES else _STATUS_UNCERTAIN


def _extract_flags(
    verdict: dict,
    artifact: str,
    allowed_categories: set[str],
) -> tuple[str, list[CoverageClaimFlag]]:
    """1 つの verdict (title or article) から status と flag 群を取り出す。

    ★ B-3': status=contradiction のときのみ flag を採用する。uncertain / consistent は
    flag しない。さらに forbidden_category が当該系統の許容外カテゴリの場合は無視する
    (LLM の逸脱に対する安全網)。
    """
    status = _coerce_status(verdict.get("status"))
    if status != _STATUS_CONTRADICTION:
        return status, []

    flags: list[CoverageClaimFlag] = []
    for raw in verdict.get("flagged_claims") or []:
        if not isinstance(raw, dict):
            continue
        category = str(raw.get("forbidden_category") or "").strip()
        # 系統ポリシーに無いカテゴリは採用しない (各論逸脱を弾く)。
        if allowed_categories and category not in allowed_categories:
            continue
        span = str(raw.get("span") or "").strip()
        if not span:
            continue
        flags.append(
            CoverageClaimFlag(
                artifact=artifact,
                span=span,
                forbidden_category=category,
                reasoning=str(raw.get("reasoning") or "").strip(),
            )
        )
    # contradiction を宣言したが採用可能な flag が無い場合は consistent 扱いに倒す。
    if not flags:
        return _STATUS_CONSISTENT, []
    return _STATUS_CONTRADICTION, flags


# ── 公開 API ──────────────────────────────────────────────────────────────────

def run_coverage_claim_guard(
    scored_event: "ScoredEvent",
    video_script: "VideoScript",
    article_markdown: str,
    *,
    channel_id: str = "geo_lens",
    client: Optional[LLMClient] = None,
    policy: Optional[CoverageClaimPolicy] = None,
    max_retries: int = 2,
) -> CoverageClaimGuardResult:
    """生成済み title + article の coverage claim を系統判定と事実整合検証する。

    Args:
        scored_event: 真値 stream_classification を持つ ScoredEvent。
        video_script: title 層 (platform_title 等) を持つ生成済み台本。
        article_markdown: 生成済み記事本文 (Markdown)。
        channel_id: guard プロンプト解決用 (default "geo_lens")。
        client: テスト/DI 用 LLM クライアント。None なら get_analysis_llm_client()
                (事実重視 temperature 0.3 + gemini-3.5-flash QUALITY、extractor と同方針)。
        policy: テスト/DI 用ポリシー。None なら configs/coverage_claim_policy.yaml をロード。
        max_retries: LLM 呼出失敗時のリトライ回数。

    Returns:
        CoverageClaimGuardResult。検出は flag のみ (自動置換・再生成はしない)。
        真値不明 / forbidden カテゴリ空 (silence_gap / out_of_scope) / LLM 不在の場合は
        skipped=True で flag せず返す (B-3' 安全側)。
    """
    stream = resolve_stream_classification(scored_event)
    pol = policy if policy is not None else load_coverage_claim_policy()
    stream_pol = pol.stream_policy(stream)
    allowed_categories = set(stream_pol.forbidden_claim_categories)

    # forbidden カテゴリが無い系統 (silence_gap = 未報道断定が事実整合 /
    # out_of_scope = 真値不明) は LLM を呼ばず flag しない。
    if not allowed_categories:
        return CoverageClaimGuardResult(
            stream_classification=stream,
            flagged=False,
            skipped=True,
            skip_reason=(
                "no forbidden coverage-claim categories for this stream "
                f"({stream}); silence/uncertain not flagged (B-3')"
            ),
        )

    llm = client if client is not None else get_analysis_llm_client()
    if llm is None:
        logger.warning(
            "[CoverageClaimGuard] no analysis LLM client available; "
            f"skipping guard for stream={stream}."
        )
        return CoverageClaimGuardResult(
            stream_classification=stream,
            flagged=False,
            skipped=True,
            skip_reason="no LLM client available",
        )

    try:
        template = load_prompt(channel_id, "coverage_claim_guard")
    except FileNotFoundError as exc:
        logger.error(f"[CoverageClaimGuard] prompt not found: {exc}")
        return CoverageClaimGuardResult(
            stream_classification=stream,
            flagged=False,
            skipped=True,
            skip_reason="guard prompt not found",
        )

    forbidden_block = _format_forbidden_categories(pol, allowed_categories)
    prompt = template.format(
        stream_classification=stream,
        stream_label=stream_pol.label or "(none)",
        broad_event_reported_in_jp=_fmt_tristate(stream_pol.broad_event_reported_in_jp),
        particular_angle_reported_in_jp=_fmt_tristate(stream_pol.particular_angle_reported_in_jp),
        allowed_claim_level=stream_pol.allowed_claim_level,
        stream_description=stream_pol.description.strip(),
        forbidden_categories_block=forbidden_block,
        title_block=_build_title_block(video_script),
        article_text=(article_markdown or "").strip() or "(none)",
    )

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            raw = llm.generate(prompt)
            if not raw or not raw.strip():
                raise ValueError("LLM returned empty response")
            payload = _parse_llm_response(raw)
            title_status, title_flags = _extract_flags(
                payload.get("title_verdict") or {}, "title", allowed_categories
            )
            article_status, article_flags = _extract_flags(
                payload.get("article_verdict") or {}, "article", allowed_categories
            )
            flags = title_flags + article_flags
            result = CoverageClaimGuardResult(
                stream_classification=stream,
                flagged=bool(flags),
                flags=flags,
                title_status=title_status,
                article_status=article_status,
            )
            logger.info(
                f"[CoverageClaimGuard] stream={stream} flagged={result.flagged} "
                f"title={title_status} article={article_status} "
                f"n_flags={len(flags)}"
            )
            return result
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            last_error = exc
            logger.warning(
                f"[CoverageClaimGuard] attempt {attempt}/{max_retries} parse error: "
                f"{str(exc)[:150]}"
            )
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(
                f"[CoverageClaimGuard] attempt {attempt}/{max_retries} api error: "
                f"{type(exc).__name__}: {str(exc)[:150]}"
            )

    logger.error(
        f"[CoverageClaimGuard] all {max_retries} attempts failed for stream={stream}; "
        f"returning skipped (no flag). last_error={last_error}"
    )
    return CoverageClaimGuardResult(
        stream_classification=stream,
        flagged=False,
        skipped=True,
        skip_reason=f"guard LLM failed: {last_error}",
    )


def _fmt_tristate(v: Optional[bool]) -> str:
    """True/False/None を日本語表記に変換 (プロンプト用)。"""
    if v is True:
        return "はい (報道済み)"
    if v is False:
        return "いいえ (未報道)"
    return "不明"


def _format_forbidden_categories(
    policy: CoverageClaimPolicy,
    allowed_categories: set[str],
) -> str:
    """系統の forbidden カテゴリ群を、意味カテゴリ定義つきでブロック整形する。"""
    lines: list[str] = []
    for cat in allowed_categories:
        meaning = ""
        defn = policy.forbidden_claim_categories.get(cat)
        if defn:
            meaning = str(defn.get("meaning") or "").strip()
        lines.append(f"- **{cat}**: {meaning}")
    return "\n".join(lines) if lines else "(なし)"
