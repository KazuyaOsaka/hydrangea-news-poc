"""gemini_judge.py — Gemini 根拠付き編集審判パス (Stage D)

目的:
  evidence（フェッチ済み記事）のみを根拠として、候補の報道乖離・ブラインドスポット・
  日本への間接インパクトを評価する。

重要な設計制約（Guardrails）:
  1. Gemini は evidence.json / sources_jp / sources_en に存在するソースのみを参照できる。
  2. Gemini はプロンプト内で提示されていない媒体名を新たに主張してはならない。
  3. hard_claims_supported=false の候補を Gemini だけの判断で publishable にしてはならない。
  4. 証拠が弱い場合は investigate_more / insufficient_evidence を返すこと。
  5. ジャッジ失敗（APIエラー・JSON解析失敗）は judge_error に記録し、
     デフォルト値の GeminiJudgeResult を返す（パイプラインはブロックしない）。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from src.shared.logger import get_logger
from src.shared.models import GeminiJudgeResult, ScoredEvent

if TYPE_CHECKING:
    from src.llm.base import LLMClient

logger = get_logger(__name__)

# ── 定数 ──────────────────────────────────────────────────────────────────────

# Gemini に渡すソーススニペットの最大文字数（トークン節約）
_MAX_SNIPPET_CHARS = 300
# 1候補あたりのソース最大件数（JP / 海外それぞれ）
_MAX_SOURCES_PER_SIDE = 5

# publishability_class として有効な値
_VALID_PUBLISHABILITY = frozenset({
    "linked_jp_global",
    "blind_spot_global",
    "jp_only",
    "insufficient_evidence",
    "investigate_more",
})

# ── プロンプト ──────────────────────────────────────────────────────────────────

_JUDGE_PROMPT = """\
あなたはニュースメディアの上級編集者です。
以下に提供された「証拠データ」（実際に取得された記事のタイトル・スニペット）のみを根拠として、
この候補が Hydrangea News の動画コンテンツとして成立するかを評価してください。

## 絶対的なルール
1. プロンプト内で明示された媒体名・ソース名以外を NEW に主張・追加しないこと。
2. 証拠データに存在しない事実を補完・推測・创作しないこと。
3. 「日本が軽視している」という判断は、JP ソースと 海外ソースの実際の報道差を根拠とする場合のみ。
4. 証拠が不十分な場合は requires_more_evidence=true、publishability_class="investigate_more" または "insufficient_evidence" を返すこと。
5. hard_claims_supported は JP/EN 両ソースに実際の記事が存在し、かつスニペットが一致する場合のみ true。

## 評価対象の証拠データ
{{EVIDENCE_JSON}}

## 出力形式
必ず以下の JSON のみを返してください。前置き・説明・コードブロックは不要です。

{
  "divergence_score": <0-10: JP と海外の報道視点・フレーミングの乖離度>,
  "blind_spot_global_score": <0-10: 日本が見落としているグローバル重要性>,
  "indirect_japan_impact_score_judge": <0-10: 日本への間接的インパクトの強さ。日本企業・日本人が直接関与していなくても、(1)グローバルなパワーバランス変動（欧米対立・BRICS台頭）(2)世界経済・サプライチェーンの前提を変えるマクロ事象(3)日本のビジネスパーソンが教養・リスクシナリオとして知るべきパラダイムシフト に該当する場合は高得点（7〜10点）を与えること。逆に、他国のローカル事件・局地的事故・芸能ゴシップなど日本への波及が皆無のニュースは低得点（0〜2点）とすること>,
  "authority_signal_score": <0-10: top/major 権威ソースの証拠強度>,
  "publishability_class": "<linked_jp_global|blind_spot_global|jp_only|insufficient_evidence|investigate_more>",
  "why_this_matters_to_japan": "<日本にとってなぜ重要か。1文で。>",
  "strongest_perspective_gap": "<最も鮮明な視点差。1文で。>",
  "strongest_authority_pair": ["<証拠に存在する媒体名1>", "<証拠に存在する媒体名2>"],
  "confidence": <0-1: ジャッジの確信度>,
  "requires_more_evidence": <true|false>,
  "hard_claims_supported": <true|false>,
  "recommended_followup_queries": ["<クエリ1>", ...],
  "recommended_followup_source_types": ["<ソース種別1>", ...]
}
"""


# ── エラー分類 ────────────────────────────────────────────────────────────────

def _classify_judge_error(exc: Exception) -> str:
    """例外を judge_error_type 文字列に分類する。

    - 429 / RESOURCE_EXHAUSTED → "quota_exhausted"
    - 503 / UNAVAILABLE        → "temporary_unavailable"
    - JSON 解析失敗             → "parse_error"
    - その他                   → "unknown_error"
    """
    msg = str(exc)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        return "quota_exhausted"
    if "503" in msg or "UNAVAILABLE" in msg:
        return "temporary_unavailable"
    if "404" in msg or "NOT_FOUND" in msg:
        # Model not found — the requested model name is invalid or unavailable
        # in this API tier.  Distinct from temporary_unavailable (503).
        # The model registry should prevent this at startup; if it still occurs,
        # it is treated as a hard model configuration error, not a quota event.
        return "model_not_found"
    if isinstance(exc, (json.JSONDecodeError, ValueError)) and (
        "json" in type(exc).__name__.lower() or "json" in msg.lower()
    ):
        return "parse_error"
    return "unknown_error"


# ── 内部ヘルパ ──────────────────────────────────────────────────────────────────

def _truncate(text: str, max_chars: int = _MAX_SNIPPET_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"


def _build_source_list(sources: list, label: str) -> list[dict]:
    """SourceRef リストを judge プロンプト向け辞書リストに変換する。"""
    result = []
    for src in sources[:_MAX_SOURCES_PER_SIDE]:
        entry: dict = {"source_name": src.name, "url": src.url}
        if src.title:
            entry["title"] = _truncate(src.title)
        result.append(entry)
    return result


def _collect_all_overseas_sources(event_sources_by_locale: dict) -> list:
    """sources_by_locale から japan 以外の全SourceRef を返す。"""
    result = []
    for locale, refs in event_sources_by_locale.items():
        if locale != "japan":
            result.extend(refs)
    return result


def _build_evidence_payload(se: ScoredEvent) -> dict:
    """ScoredEvent から judge プロンプト用 evidence dict を構築する。

    Gemini に渡す情報は evidence に実在するソースのみ。
    """
    event = se.event
    bd = se.score_breakdown

    # JP ソース
    jp_sources = _build_source_list(event.sources_jp, "jp")
    if not jp_sources and event.sources_by_locale:
        jp_sources = _build_source_list(event.sources_by_locale.get("japan", []), "jp")

    # 海外ソース（sources_en + sources_by_locale の japan 以外）
    overseas_set: list = list(event.sources_en)
    if event.sources_by_locale:
        for locale, refs in event.sources_by_locale.items():
            if locale != "japan":
                overseas_set.extend(refs)
    # URL で重複排除
    seen_urls: set[str] = set()
    unique_overseas: list = []
    for s in overseas_set:
        if s.url not in seen_urls:
            seen_urls.add(s.url)
            unique_overseas.append(s)
    en_sources = _build_source_list(unique_overseas, "overseas")

    # score breakdown から関連する数値だけ抽出（トークン節約）
    score_context = {
        "total_score": round(se.score, 2),
        "perspective_gap": bd.get("editorial:perspective_gap_score", 0.0),
        "japan_relevance": bd.get("editorial:japan_relevance_score", 0.0),
        "global_attention": bd.get("editorial:global_attention_score", 0.0),
        "indirect_japan_impact": bd.get("editorial:indirect_japan_impact_score", 0.0),
        "background_inference_potential": bd.get("editorial:background_inference_potential", 0.0),
        "appraisal_type": se.appraisal_type,
        "primary_bucket": se.primary_bucket,
    }

    return {
        "event_id": event.id,
        "title": event.title,
        "summary": _truncate(event.summary, 400) if event.summary else "",
        "category": event.category,
        "japan_view": _truncate(event.japan_view, 300) if event.japan_view else None,
        "global_view": _truncate(event.global_view, 300) if event.global_view else None,
        "gap_reasoning": _truncate(event.gap_reasoning, 300) if event.gap_reasoning else None,
        "jp_sources": jp_sources,
        "overseas_sources": en_sources,
        "source_count_jp": len(jp_sources),
        "source_count_overseas": len(en_sources),
        "score_context": score_context,
    }


def _validate_authority_pair(
    raw_pair: list,
    jp_source_names: set[str],
    overseas_source_names: set[str],
) -> list[str]:
    """strongest_authority_pair の検証: evidence に存在しない媒体名を除去する。

    Gemini が捏造した媒体名がスクリプトに混入することを防ぐ guardrail。
    """
    all_known = jp_source_names | overseas_source_names
    validated = []
    for name in raw_pair:
        if not isinstance(name, str):
            continue
        # 完全一致 or 部分マッチ（大文字小文字無視）で evidence 在否確認
        name_lower = name.lower().strip()
        matched = any(name_lower in k.lower() or k.lower() in name_lower for k in all_known)
        if matched:
            validated.append(name)
        else:
            logger.warning(
                f"[GeminiJudge] Stripped hallucinated authority pair name: '{name}' "
                f"(not found in evidence sources: {sorted(all_known)[:6]})"
            )
    return validated[:2]


def _parse_judge_response(
    raw: str,
    event_id: str,
    jp_source_names: set[str],
    overseas_source_names: set[str],
) -> GeminiJudgeResult:
    """Gemini の raw 出力を GeminiJudgeResult に変換する。

    - コードブロック除去
    - publishability_class のバリデーション
    - strongest_authority_pair の hallucination 検証
    """
    # コードブロックで囲まれていれば除去
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    data = json.loads(text)

    # publishability_class バリデーション
    pub_class = data.get("publishability_class", "insufficient_evidence")
    if pub_class not in _VALID_PUBLISHABILITY:
        logger.warning(
            f"[GeminiJudge] Invalid publishability_class '{pub_class}' — "
            "falling back to 'insufficient_evidence'"
        )
        pub_class = "insufficient_evidence"

    # strongest_authority_pair: evidence に存在しない名前を除去
    raw_pair = data.get("strongest_authority_pair", [])
    if not isinstance(raw_pair, list):
        raw_pair = []
    authority_pair = _validate_authority_pair(raw_pair, jp_source_names, overseas_source_names)

    # followup リストを最大5件にトリム
    followup_queries = data.get("recommended_followup_queries", [])
    if not isinstance(followup_queries, list):
        followup_queries = []
    followup_queries = [str(q) for q in followup_queries[:5]]

    followup_types = data.get("recommended_followup_source_types", [])
    if not isinstance(followup_types, list):
        followup_types = []
    followup_types = [str(t) for t in followup_types[:5]]

    # スコアを 0-10 にクリップ
    def _clamp(val: float) -> float:
        return max(0.0, min(10.0, float(val)))

    def _clamp01(val: float) -> float:
        return max(0.0, min(1.0, float(val)))

    return GeminiJudgeResult(
        divergence_score=_clamp(data.get("divergence_score", 0.0)),
        blind_spot_global_score=_clamp(data.get("blind_spot_global_score", 0.0)),
        indirect_japan_impact_score_judge=_clamp(data.get("indirect_japan_impact_score_judge", 0.0)),
        authority_signal_score=_clamp(data.get("authority_signal_score", 0.0)),
        publishability_class=pub_class,
        why_this_matters_to_japan=str(data.get("why_this_matters_to_japan", ""))[:200],
        strongest_perspective_gap=str(data.get("strongest_perspective_gap", ""))[:200],
        strongest_authority_pair=authority_pair,
        confidence=_clamp01(data.get("confidence", 0.0)),
        requires_more_evidence=bool(data.get("requires_more_evidence", True)),
        hard_claims_supported=bool(data.get("hard_claims_supported", False)),
        recommended_followup_queries=followup_queries,
        recommended_followup_source_types=followup_types,
        judged_event_id=event_id,
        judged_at=datetime.now(timezone.utc).isoformat(),
    )


# ── 公開 API ───────────────────────────────────────────────────────────────────

def run_gemini_judge(
    se: ScoredEvent,
    llm_client: "LLMClient",
) -> GeminiJudgeResult:
    """Gemini 編集審判を実行し、GeminiJudgeResult を返す。

    APIエラー・JSON解析失敗の場合は judge_error を設定したデフォルト値を返す。
    パイプラインはブロックしない（graceful degradation）。

    Args:
        se         : 評価対象の ScoredEvent（evidence が入った状態）
        llm_client : Gemini LLMClient インスタンス

    Returns:
        GeminiJudgeResult（失敗時は judge_error が非 None）
    """
    event_id = se.event.id
    evidence = _build_evidence_payload(se)

    # evidence に存在するソース名セット（hallucination 検証用）
    jp_source_names: set[str] = {s.name for s in se.event.sources_jp}
    if se.event.sources_by_locale:
        for ref in se.event.sources_by_locale.get("japan", []):
            jp_source_names.add(ref.name)

    overseas_source_names: set[str] = {s.name for s in se.event.sources_en}
    if se.event.sources_by_locale:
        for locale, refs in se.event.sources_by_locale.items():
            if locale != "japan":
                for ref in refs:
                    overseas_source_names.add(ref.name)

    prompt = _JUDGE_PROMPT.replace(
        "{{EVIDENCE_JSON}}",
        json.dumps(evidence, ensure_ascii=False, indent=2),
    )

    _using_model = getattr(llm_client, '_model', 'unknown')
    logger.info(
        f"[GeminiJudge] Using resolved model: {_using_model!r}"
    )
    logger.info(
        f"[GeminiJudge] Running judge for {event_id} "
        f"(jp_sources={len(jp_source_names)}, overseas_sources={len(overseas_source_names)})"
    )

    from src.llm.retry import call_with_retry

    _retry_count = 0
    try:
        raw, _retry_count = call_with_retry(
            lambda: llm_client.generate(prompt),
            role="judge",
        )
        result = _parse_judge_response(raw, event_id, jp_source_names, overseas_source_names)
        logger.info(
            f"[GeminiJudge] {event_id}: "
            f"class={result.publishability_class}, "
            f"divergence={result.divergence_score:.1f}, "
            f"blind_spot={result.blind_spot_global_score:.1f}, "
            f"ijai={result.indirect_japan_impact_score_judge:.1f}, "
            f"requires_more={result.requires_more_evidence}, "
            f"hard_claims={result.hard_claims_supported}, "
            f"authority_pair={result.strongest_authority_pair}, "
            f"retries={_retry_count}"
        )
        return result.model_copy(update={"llm_retry_count": _retry_count})

    except Exception as exc:
        _error_type = _classify_judge_error(exc)
        # 長大なエラー文字列（Gemini の JSON エラーボディ等）を安全に截断
        _error_summary = str(exc)[:500]
        logger.warning(
            f"[GeminiJudge] Failed for {event_id} "
            f"[error_type={_error_type}, retries={_retry_count}]: {_error_summary}"
        )
        return GeminiJudgeResult(
            judged_event_id=event_id,
            judged_at=datetime.now(timezone.utc).isoformat(),
            judge_error=_error_summary,
            judge_error_type=_error_type,
            publishability_class="insufficient_evidence",
            requires_more_evidence=True,
            hard_claims_supported=False,
            llm_retry_count=_retry_count,
        )


def judge_rerank_score(se: ScoredEvent) -> float:
    """ジャッジ結果を reranking ブーストスコアに変換する。

    ジャッジなし / 失敗の場合は 0.0 を返す。
    ブーストは最大 +8.0pt（弱候補の逆転防止のため、tie-breaker 程度の影響に留める）。

    スコアリング:
      - publishability_class=linked_jp_global + divergence>=7 : +8.0
      - publishability_class=linked_jp_global               : +5.0
      - publishability_class=blind_spot_global + ijai>=7    : +6.0
      - publishability_class=blind_spot_global               : +4.0
      - publishability_class=jp_only                         : -3.0（ペナルティ）
      - publishability_class=insufficient_evidence           : -5.0
      - publishability_class=investigate_more                : +1.0（潜在価値あり）
      - hard_claims_supported=false                          : -2.0 追加ペナルティ
      - requires_more_evidence=true                          : -1.0 追加ペナルティ
    """
    jr = se.judge_result
    if jr is None or jr.judge_error is not None:
        return 0.0

    pub = jr.publishability_class
    boost = 0.0

    if pub == "linked_jp_global":
        boost = 8.0 if jr.divergence_score >= 7.0 else 5.0
    elif pub == "blind_spot_global":
        boost = 6.0 if jr.indirect_japan_impact_score_judge >= 7.0 else 4.0
    elif pub == "jp_only":
        boost = -3.0
    elif pub == "insufficient_evidence":
        boost = -5.0
    elif pub == "investigate_more":
        boost = 1.0

    if not jr.hard_claims_supported:
        boost -= 2.0
    if jr.requires_more_evidence:
        boost -= 1.0

    # 信頼度で減衰
    boost *= max(0.3, jr.confidence)

    return round(boost, 2)


def is_rescue_candidate(judge_result: GeminiJudgeResult) -> bool:
    """investigate_more パスに回すべきか判定する。

    条件: requires_more_evidence=True かつ（blind_spot_global_score または
    divergence_score が高い）。この場合はスクリプト自動生成をスキップし、
    judge_report.json + followup_queries.json を出力する。
    """
    if not judge_result.requires_more_evidence:
        return False
    return (
        judge_result.blind_spot_global_score >= 6.0
        or judge_result.divergence_score >= 6.0
    )
