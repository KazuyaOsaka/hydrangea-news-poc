"""F-editorial-guardian-corroboration (1-T.2): 公開前検証 第2段 — 真実性検証
(grounding による複数ソース突合) + レポート enrichment。

1-T.1 (editorial_guardian.py) の第1層・忠実性は「生成器が見た入力に合っている」
までしか保証しない。元ソース自体の正しさ (例: TeleSUR = ベネズエラ政府系の党派性)
と not_in_source 主張の真偽は、独立ソースとの突合でしか検証できない。
ADR-0003「複数ソース突合 (TeleSUR + Al Jazeera + MEE 等)」の機械化。

★ アーキテクチャ: 検索と判定の分離
  - 証拠収集 (GroundingSearchClient): raw `genai.Client` + google_search tool
    (F-13.B 実証済みパターン) を軽量モデル (GUARDIAN_GROUNDING_MODEL env、
    default gemini-2.5-flash) で実行。claim ごとに 1-T.1 生成済みの
    verification_queries を全て実行し、証拠 (実ドメイン・タイトル・grounded
    応答テキスト・解決済み URL) を収集する。検索モデルは**証拠の運搬係**で
    あって検証者ではない。
  - 判定 (corroborate_report): 複数クエリ分の証拠を束ね、1-T.1 配線済みの
    Guardian クライアント (get_guardian_llm_client、gemini-3.1-pro-preview、
    tools 不要) が claim 単位で corroborated / contradicted / uncorroborated を
    判定する。沈黙的劣化の禁止は**判定層**で維持 (Guardian 不可時は下位モデルへ
    フォールバックせず unverified = 検証未完を明示する)。
  - 設計根拠: ① 3.1-pro の google_search tool サポートに非依存 ② grounding
    run 間分散 (F-grounding-determinism-audit) へ複数クエリ証拠の集約判定で対処
    ③ 検索を $2/$12 モデルで回さずコスト最適。

★ truthfulness の語彙 (第1層と平行構造、語彙定義は editorial_guardian.py 正本):
  - corroborated:   元ソースのドメイン以外の独立ソースが主張を支持
  - contradicted:   外部ソースが明示的に矛盾 (B-3' 哲学: 明示的矛盾のみ。
                    見つからないことを矛盾と読み替えない)
  - uncorroborated: 検索は成功したが独立した支持が見つからない (≠ 虚偽、人間レビュー行き)
  - unverified:     検索 or 判定が完了しなかった (harness 値、検証未完)

★ 独立性の最小定義: 元ソースドメイン (event.source_urls / sources_by_locale 由来)
  の除外のみ。提携メディア DB 等の作り込みはしない (誤り6 回避)。発見ドメインは
  evidence に全列挙して人間監査に委ねる。独立性ルールはプロンプトと deterministic
  チェックの両方で担保 (LLM が元ソースのみ / 証拠に無いドメインを根拠に
  corroborated を返したら harness が uncorroborated に倒す安全網)。

★ 第2層の対象選別: faithfulness_status が supported / not_in_source の claim のみ。
  contradicted (第1層 flag 済み = 人間が直す主張) と unverified は skip し、
  truthfulness_status=pending のまま skip 理由を notes に記録する
  (修正後に手動ランナー再実行で検証するのが運用ループ)。

★ 公開可否の最終バー: claim が flag されないのは **supported かつ corroborated**
  の場合のみ。それ以外 (いずれかの層で contradicted / uncorroborated /
  not_in_source / unverified / pending) は全て flagged_claims に載せ人間レビュー
  行き。**flag のみ。自動修正・公開ブロックなし。公開判断はカズヤ。**

★ enrichment 設計: 1-T.1 のレポート JSON を入力にレポートを返す (入力レポートは
  変更しない deep copy)。schema_version は 2 に昇格する。

呼出例 (production 配線は本バッチ範囲外、第一作は手動ランナー):
    grounding = GroundingSearchClient(genai_client)  # main.py 同様の注入パターン
    enriched = corroborate_report(
        report, source_domains=["middleeasteye.net"], grounding_client=grounding
    )
"""
from __future__ import annotations

import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Sequence

from src.analysis.prompt_loader import load_prompt
from src.llm.base import LLMClient
from src.llm.factory import get_guardian_llm_client
from src.shared.logger import get_logger

# スキーマ正本は editorial_guardian.py (1-T.1)。本モジュールは同一機能
# (Editorial Guardian、カズヤ確定 2 バッチ構成) の第2段であり、語彙・モデル・
# retry 意味論 (沈黙的劣化の禁止) を共有するため、重複再実装ではなく import する
# (src/triage/ のような保護領域ではない自前モジュール間の共有)。
from src.generation.editorial_guardian import (
    FAITHFULNESS_NOT_IN_SOURCE,
    FAITHFULNESS_SUPPORTED,
    TRUTHFULNESS_CONTRADICTED,
    TRUTHFULNESS_CORROBORATED,
    TRUTHFULNESS_PENDING,
    TRUTHFULNESS_UNCORROBORATED,
    TRUTHFULNESS_UNVERIFIED,
    ClaimVerification,
    CorroborationEvidence,
    EditorialGuardianReport,
    TruthfulnessSummary,
    VerificationQuery,
    _generate_with_retry,
    _resolve_model_id,
)

logger = get_logger(__name__)

# enriched レポートの schema_version (1-T.1 素のレポート = 1)。
ENRICHED_SCHEMA_VERSION = 2

# 第2層の対象 (skip 対象 = contradicted / unverified は pending のまま)。
_CORROBORATION_TARGETS = {FAITHFULNESS_SUPPORTED, FAITHFULNESS_NOT_IN_SOURCE}

# LLM judge の語彙 (unverified は harness 値であり judge の語彙ではない)。
_VALID_TRUTHFULNESS = {
    TRUTHFULNESS_CORROBORATED,
    TRUTHFULNESS_CONTRADICTED,
    TRUTHFULNESS_UNCORROBORATED,
}

_DEFAULT_GROUNDING_TIMEOUT_SECONDS = 90.0  # F-13.B two_stage と同値
_DEFAULT_RESOLVE_TIMEOUT_SECONDS = 8.0
_DEFAULT_MAX_RESOLVES_PER_QUERY = 5


# ── ドメインヘルパ (jp_coverage_verifier.py の同形再実装) ────────────────────
# ★ 意識的な重複: src/triage/jp_coverage_verifier.py は不変原則 3 の保護領域で、
#   以下は module-private 関数のため import は慣例違反。F-13.B 実証済みロジックを
#   同形で写す (写し元行番号を各 docstring に記録)。挙動を変えないこと。

_DOMAIN_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9\-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]*[a-z0-9])?)+$")


def _looks_like_domain(s: str) -> bool:
    """文字列がドメイン形式かを判定 (jp_coverage_verifier.py L55-70 同形)。"""
    if not s:
        return False
    return bool(_DOMAIN_PATTERN.match(s.strip().lower()))


def _normalize_domain(s: str) -> str:
    """ドメイン文字列を正規化 (jp_coverage_verifier.py L73-87 同形)。"""
    s = s.strip().lower()
    s = re.sub(r"^https?://", "", s)
    s = s.split("/", 1)[0]
    return s


def _domain_matches_hierarchy(host: str, wl_domain: str) -> bool:
    """ドメイン階層 (祖先/子孫) マッチ (jp_coverage_verifier.py L90-121 同形)。

    独立性チェックでは「www.aljazeera.com vs aljazeera.com」のような
    サブドメイン差を吸収するために使う。
    """
    if not host or not wl_domain:
        return False
    h = host.strip().lower().lstrip(".")
    w = wl_domain.strip().lower().lstrip(".")
    if not h or not w:
        return False
    if h == w:
        return True
    if h.endswith("." + w):
        return True
    if w.endswith("." + h):
        return True
    return False


def _extract_domain_from_chunk(chunk: Any) -> Optional[str]:
    """Grounding chunk から実ソースドメインを抽出 (jp_coverage_verifier.py L124-153 同形)。

    chunk.web.uri は Vertex AI の redirect URL を返す仕様のため使わず、
    実ドメインは chunk.web.domain (将来 SDK) → chunk.web.title (現行) の順で取る
    (F-jp-coverage-improve / 2026-05-07 知見。1-T.2 CP-1 仮説2 で現 API でも
    成立することを実測確認済み: web.domain=None / web.title='middleeasteye.net')。
    """
    web = getattr(chunk, "web", None)
    if web is None:
        return None
    domain = getattr(web, "domain", None)
    if isinstance(domain, str) and domain.strip():
        return _normalize_domain(domain)
    title = getattr(web, "title", None)
    if isinstance(title, str) and _looks_like_domain(title):
        return _normalize_domain(title)
    return None


def _extract_response_text(response: Any) -> str:
    """response.candidates[0].content.parts[*].text を結合 (jp_coverage_verifier.py L201-226 同形)。"""
    try:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return ""
        content = getattr(candidates[0], "content", None)
        if content is None:
            return ""
        parts = getattr(content, "parts", None)
        if parts is None:
            return ""
        text_parts: list[str] = []
        for p in parts:
            t = getattr(p, "text", None)
            if isinstance(t, str):
                text_parts.append(t)
        return "".join(text_parts)
    except (TypeError, AttributeError):
        return ""


def _call_with_timeout(callable_: Callable[[], Any], timeout_seconds: float) -> Any:
    """per-call timeout 付き同期実行 (jp_coverage_verifier.py L1186-1202 同形)。"""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(callable_)
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeoutError as exc:
            future.cancel()
            raise TimeoutError(
                f"call exceeded timeout={timeout_seconds}s"
            ) from exc


# ── 証拠収集 (検索層 = 証拠の運搬係) ─────────────────────────────────────────

def _resolve_redirect_url(url: str, timeout_seconds: float) -> Optional[str]:
    """Vertex AI redirect URL を HTTP HEAD で記事実体 URL に解決する (best effort)。

    CP-1 仮説3 実測: UA 付き HEAD で status 200 + 実体 URL に解決できる。
    失敗してもバッチは止めない (監査可能性の向上が目的、None を返すのみ)。
    """
    try:
        req = urllib.request.Request(
            url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            resolved = resp.geturl()
            return resolved if resolved and resolved != url else None
    except Exception as exc:  # noqa: BLE001 — 解決失敗は証拠欠落であってエラーではない
        logger.debug(
            f"[GuardianCorroboration] redirect resolve failed: "
            f"{type(exc).__name__}: {str(exc)[:120]}"
        )
        return None


class GroundingSearchClient:
    """grounded 検索 (google_search tool) の薄いラッパ — 証拠の運搬係。

    raw `google.genai.Client` を注入される (F-13.B が main.py でやる形を踏襲、
    LLMClient 抽象は tools 注入経路を持たないため。テストは fake client を DI)。
    モデルは軽量 (GUARDIAN_GROUNDING_MODEL env、default gemini-2.5-flash =
    F-13.B と同じ実績モデル)。判定はしない (判定は Guardian = corroborate_report)。
    """

    def __init__(
        self,
        genai_client: Any,
        *,
        model: Optional[str] = None,
        timeout_seconds: float = _DEFAULT_GROUNDING_TIMEOUT_SECONDS,
        resolve_redirects: bool = True,
        max_resolves_per_query: int = _DEFAULT_MAX_RESOLVES_PER_QUERY,
        resolve_timeout_seconds: float = _DEFAULT_RESOLVE_TIMEOUT_SECONDS,
    ) -> None:
        from src.shared.config import GUARDIAN_GROUNDING_MODEL

        self.genai_client = genai_client
        self.model = model or GUARDIAN_GROUNDING_MODEL
        self.timeout_seconds = timeout_seconds
        self.resolve_redirects = resolve_redirects
        self.max_resolves_per_query = max_resolves_per_query
        self.resolve_timeout_seconds = resolve_timeout_seconds
        # コスト実測用 (usage_metadata がある場合のみ加算)
        self.usage: dict[str, int] = {
            "calls": 0,
            "prompt_tokens": 0,
            "candidates_tokens": 0,
            "total_tokens": 0,
        }

    def _build_search_prompt(self, query: VerificationQuery, claim_text: str) -> str:
        """証拠収集プロンプト。検証判定はさせない (運搬係の規律)。"""
        return (
            f"次の主張について Web 検索を行い、見つかった報道内容を整理して"
            f"報告してください。\n\n"
            f"検証対象の主張: {claim_text}\n"
            f"検索クエリ: {query.query}\n\n"
            f"# 報告形式\n"
            f"- どの報道機関・ソースが、この主張 (または密接に関連する事実) について"
            f"何と報じているかを、ソースごとに整理して記述してください\n"
            f"- 主張と明示的に矛盾する報道があれば、その内容を明確に記述してください\n"
            f"- 関連する報道が見つからなかった場合: 文中に「関連する報道は見つかり"
            f"ませんでした」と明示してください\n"
            f"- 主張が真実かどうかの判定はしないでください。検索で確認できた報道内容"
            f"の報告のみを行ってください"
        )

    def search(self, query: VerificationQuery, claim_text: str) -> CorroborationEvidence:
        """1 クエリ分の grounded 検索を実行し証拠を返す。失敗は error に記録する。"""
        evidence = CorroborationEvidence(
            query=query.query, locale=query.locale, purpose=query.purpose
        )
        if self.genai_client is None:
            evidence.error = "genai client is not configured"
            return evidence

        from google.genai import types

        prompt = self._build_search_prompt(query, claim_text)

        def _do_call() -> Any:
            return self.genai_client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )

        try:
            response = _call_with_timeout(_do_call, self.timeout_seconds)
        except Exception as exc:  # noqa: BLE001 — クエリ単位で記録し集約判定に委ねる
            evidence.error = f"{type(exc).__name__}: {str(exc)[:200]}"
            logger.warning(
                f"[GuardianCorroboration] grounded search failed "
                f"(query={query.query!r}): {evidence.error}"
            )
            return evidence

        self.usage["calls"] += 1
        um = getattr(response, "usage_metadata", None)
        if um is not None:
            for attr, key in (
                ("prompt_token_count", "prompt_tokens"),
                ("candidates_token_count", "candidates_tokens"),
                ("total_token_count", "total_tokens"),
            ):
                v = getattr(um, attr, None)
                if isinstance(v, int):
                    self.usage[key] += v

        redirect_urls: list[str] = []
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            metadata = getattr(candidates[0], "grounding_metadata", None)
            if metadata is not None:
                chunks = getattr(metadata, "grounding_chunks", None) or []
                for chunk in chunks:
                    domain = _extract_domain_from_chunk(chunk)
                    if domain and domain not in evidence.domains:
                        evidence.domains.append(domain)
                    web = getattr(chunk, "web", None)
                    if web is not None:
                        title = getattr(web, "title", None)
                        if isinstance(title, str) and title and title not in evidence.titles:
                            evidence.titles.append(title)
                        uri = getattr(web, "uri", None)
                        if uri:
                            redirect_urls.append(uri)

        evidence.response_text = _extract_response_text(response)

        if self.resolve_redirects and redirect_urls:
            seen: set[str] = set()
            for uri in redirect_urls[: self.max_resolves_per_query]:
                resolved = _resolve_redirect_url(uri, self.resolve_timeout_seconds)
                if resolved and resolved not in seen:
                    seen.add(resolved)
                    evidence.resolved_urls.append(resolved)

        logger.debug(
            f"[GuardianCorroboration] grounded search ok (query={query.query!r}, "
            f"domains={len(evidence.domains)}, resolved={len(evidence.resolved_urls)}, "
            f"response_text_len={len(evidence.response_text)})"
        )
        return evidence


# ── 判定層 (Guardian、沈黙的劣化の禁止) ──────────────────────────────────────

def _coerce_truthfulness(v: object) -> str:
    """judge の status を3値に正規化。語彙外は unverified (検証未完 = flag) に倒す。"""
    s = str(v or "").strip().lower()
    return s if s in _VALID_TRUTHFULNESS else TRUTHFULNESS_UNVERIFIED


def _normalize_source_domains(source_domains: Sequence[str]) -> list[str]:
    """独立性ルールの除外基準 (元ソースドメイン) を正規化・重複排除する。"""
    out: list[str] = []
    for s in source_domains:
        d = _normalize_domain(str(s or ""))
        if d and _looks_like_domain(d) and d not in out:
            out.append(d)
    return out


def _validated_independent_domains(
    cited: object,
    evidence_domains: Sequence[str],
    source_domains: Sequence[str],
) -> list[str]:
    """judge が根拠に挙げたドメインを deterministic に検証する (安全網)。

    残すのは「実際に証拠 chunk に現れた」かつ「元ソースと階層独立」のドメインのみ。
    証拠に無いドメインの引用 (judge の幻覚) も、元ソース自身による自己支持も
    corroborated の根拠にしない。
    """
    if not isinstance(cited, list):
        return []
    out: list[str] = []
    for raw in cited:
        d = _normalize_domain(str(raw or ""))
        if not d or not _looks_like_domain(d):
            continue
        if not any(_domain_matches_hierarchy(d, e) for e in evidence_domains):
            continue
        if any(_domain_matches_hierarchy(d, s) for s in source_domains):
            continue
        if d not in out:
            out.append(d)
    return out


def _build_evidence_block(evidence_list: Sequence[CorroborationEvidence]) -> str:
    """複数クエリ分の証拠を judge プロンプト用に整形する。"""
    blocks: list[str] = []
    for i, ev in enumerate(evidence_list, start=1):
        lines = [f"### 証拠 {i} (クエリ: {ev.query} / locale: {ev.locale})"]
        if ev.purpose:
            lines.append(f"クエリ目的: {ev.purpose}")
        if ev.error:
            lines.append(f"★ この検索は失敗した (理由: {ev.error})。証拠なし。")
        else:
            lines.append(
                "発見ドメイン: " + (", ".join(ev.domains) if ev.domains else "(なし)")
            )
            if ev.resolved_urls:
                lines.append("解決済み記事 URL:")
                lines.extend(f"- {u}" for u in ev.resolved_urls)
            lines.append("grounded 応答テキスト:")
            lines.append(ev.response_text or "(空)")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) if blocks else "(証拠なし)"


def _build_skip_note(status: str) -> str:
    """第2層 skip の理由 (修正後に手動ランナー再実行で検証する運用ループ)。"""
    return (
        f"skipped by corroboration (1-T.2): faithfulness_status={status} — "
        f"fix the claim / re-run the faithfulness layer, then re-run "
        f"corroboration manually."
    )


def corroborate_report(
    report: EditorialGuardianReport,
    *,
    source_domains: Sequence[str],
    grounding_client: GroundingSearchClient,
    guardian_client: Optional[LLMClient] = None,
    channel_id: str = "geo_lens",
    max_retries: int = 2,
) -> EditorialGuardianReport:
    """1-T.1 レポートに第2層・真実性検証を enrich した新レポートを返す。

    Args:
        report: 1-T.1 の EditorialGuardianReport (入力は変更しない)。
        source_domains: 元ソースドメイン群 (独立性ルールの除外基準。
            event.source_urls / sources_by_locale から呼出側が導出する)。
        grounding_client: 証拠収集クライアント (raw genai.Client 注入済み)。
        guardian_client: テスト/DI 用。None なら get_guardian_llm_client()
            (gemini-3.1-pro-preview 単一モデル、fallback chain なし)。
        channel_id: プロンプト解決用 (default "geo_lens")。
        max_retries: judge 呼出失敗時のリトライ回数 (同一モデルのみ)。

    Returns:
        enriched EditorialGuardianReport (schema_version=2)。公開可否バー適用済み:
        flag されないのは supported かつ corroborated の claim のみ。
        **flag のみ。自動修正・公開ブロックなし。公開判断はカズヤ。**
    """
    enriched = report.model_copy(deep=True)
    summary = TruthfulnessSummary(
        grounding_model_used=getattr(grounding_client, "model", None),
        source_domains=_normalize_source_domains(source_domains),
    )

    llm = guardian_client if guardian_client is not None else get_guardian_llm_client()
    if llm is None:
        # 沈黙的劣化の禁止: 下位モデルで判定を続行せず、検証未完を明示する。
        logger.warning(
            "[GuardianCorroboration] no guardian LLM client available; "
            "truthfulness layer is unverified (検証未完)."
        )
        summary.judge_unavailable = True
        summary.unavailable_reason = (
            "no guardian LLM client (GEMINI_API_KEY missing or non-gemini "
            "provider); corroboration NOT performed"
        )
        for cv in enriched.claims:
            if cv.faithfulness_status in _CORROBORATION_TARGETS:
                cv.truthfulness_status = TRUTHFULNESS_UNVERIFIED
                cv.truthfulness_notes = summary.unavailable_reason
            else:
                cv.truthfulness_notes = _build_skip_note(cv.faithfulness_status)
        return _finalize_enriched(enriched, summary)

    summary.judge_model_used = _resolve_model_id(llm)

    try:
        judge_template = load_prompt(channel_id, "editorial_guardian_corroboration")
    except FileNotFoundError as exc:
        logger.error(f"[GuardianCorroboration] prompt not found: {exc}")
        summary.judge_unavailable = True
        summary.unavailable_reason = f"corroboration prompt not found: {exc}"
        for cv in enriched.claims:
            if cv.faithfulness_status in _CORROBORATION_TARGETS:
                cv.truthfulness_status = TRUTHFULNESS_UNVERIFIED
                cv.truthfulness_notes = summary.unavailable_reason
            else:
                cv.truthfulness_notes = _build_skip_note(cv.faithfulness_status)
        return _finalize_enriched(enriched, summary)

    for cv in enriched.claims:
        if cv.faithfulness_status not in _CORROBORATION_TARGETS:
            # 第1層 contradicted (人間が直す) / unverified (第1層未完) は skip。
            cv.truthfulness_status = TRUTHFULNESS_PENDING
            cv.truthfulness_notes = _build_skip_note(cv.faithfulness_status)
            continue
        _corroborate_claim(
            cv,
            judge_template=judge_template,
            llm=llm,
            grounding_client=grounding_client,
            source_domains=summary.source_domains,
            max_retries=max_retries,
        )

    enriched = _finalize_enriched(enriched, summary)
    logger.info(
        f"[GuardianCorroboration] event_id={enriched.event_id} "
        f"grounding_model={summary.grounding_model_used} "
        f"judge_model={summary.judge_model_used} "
        f"corroborated={summary.n_corroborated} contradicted={summary.n_contradicted} "
        f"uncorroborated={summary.n_uncorroborated} unverified={summary.n_unverified} "
        f"pending={summary.n_pending} flagged={len(enriched.flagged_claims)}"
    )
    return enriched


def _corroborate_claim(
    cv: ClaimVerification,
    *,
    judge_template: str,
    llm: LLMClient,
    grounding_client: GroundingSearchClient,
    source_domains: Sequence[str],
    max_retries: int,
) -> None:
    """claim 1 件の証拠収集 + corroboration 判定 (cv を in-place で enrich)。"""
    cv.truthfulness_verified_at = datetime.now(timezone.utc).isoformat()

    if not cv.verification_queries:
        cv.truthfulness_status = TRUTHFULNESS_UNVERIFIED
        cv.truthfulness_notes = (
            "no verification queries available (1-T.1 report did not provide any)"
        )
        return

    # ── 証拠収集: verification_queries を全て実行 (run 間分散への緩和策 =
    #    複数クエリ証拠の集約判定、F-grounding-determinism-audit 観点) ─────────
    cv.truthfulness_evidence = [
        grounding_client.search(q, cv.claim.claim_text)
        for q in cv.verification_queries
    ]
    succeeded = [ev for ev in cv.truthfulness_evidence if not ev.error]
    if not succeeded:
        cv.truthfulness_status = TRUTHFULNESS_UNVERIFIED
        cv.truthfulness_notes = (
            f"all {len(cv.truthfulness_evidence)} grounded search(es) failed; "
            "corroboration judgement not performed"
        )
        return

    # ── 判定: 全クエリ分の証拠を束ねて Guardian が claim 単位で判定 ──────────
    evidence_domains: list[str] = []
    for ev in succeeded:
        for d in ev.domains:
            if d not in evidence_domains:
                evidence_domains.append(d)

    judge_prompt = judge_template.format(
        claim_json=json.dumps(cv.claim.model_dump(), ensure_ascii=False, indent=2),
        faithfulness_status=cv.faithfulness_status,
        faithfulness_reasoning=cv.faithfulness_reasoning or "(なし)",
        source_domains=", ".join(source_domains) if source_domains else "(不明)",
        evidence_block=_build_evidence_block(cv.truthfulness_evidence),
    )

    try:
        payload = _generate_with_retry(
            llm, judge_prompt, stage="corroboration", max_retries=max_retries
        )
    except Exception as exc:  # noqa: BLE001
        # 沈黙的劣化の禁止: 判定が完了しなかった claim は unverified (検証未完)。
        cv.truthfulness_status = TRUTHFULNESS_UNVERIFIED
        cv.truthfulness_notes = (
            f"corroboration judgement failed after {max_retries} attempts: "
            f"{type(exc).__name__}: {str(exc)[:200]}"
        )
        logger.error(
            f"[GuardianCorroboration] claim={cv.claim.claim_id} {cv.truthfulness_notes}"
        )
        return

    status = _coerce_truthfulness(payload.get("status"))
    cv.truthfulness_reasoning = str(payload.get("reasoning") or "").strip()
    if status == TRUTHFULNESS_UNVERIFIED:
        cv.truthfulness_status = status
        cv.truthfulness_notes = (
            f"judge returned out-of-vocabulary status "
            f"{str(payload.get('status'))!r}; treated as unverified"
        )
        return

    # ── deterministic 独立性チェック (安全網): corroborated は証拠に現れた
    #    独立ドメインが 1 つ以上残る場合のみ維持する ───────────────────────────
    validated = _validated_independent_domains(
        payload.get("corroborating_domains"), evidence_domains, source_domains
    )
    if status == TRUTHFULNESS_CORROBORATED and not validated:
        cv.truthfulness_status = TRUTHFULNESS_UNCORROBORATED
        cv.truthfulness_notes = (
            "harness override: judge returned corroborated but no cited domain "
            "is both present in the evidence and independent of the original "
            f"source domains (cited={payload.get('corroborating_domains')!r})"
        )
        logger.warning(
            f"[GuardianCorroboration] claim={cv.claim.claim_id} {cv.truthfulness_notes}"
        )
        return

    cv.truthfulness_status = status
    cv.corroborating_domains = validated


def _finalize_enriched(
    report: EditorialGuardianReport, summary: TruthfulnessSummary
) -> EditorialGuardianReport:
    """件数サマリ + 公開可否バー (最終 flag) を適用して enriched レポートを確定する。"""
    counts = {
        TRUTHFULNESS_CORROBORATED: 0,
        TRUTHFULNESS_CONTRADICTED: 0,
        TRUTHFULNESS_UNCORROBORATED: 0,
        TRUTHFULNESS_UNVERIFIED: 0,
        TRUTHFULNESS_PENDING: 0,
    }
    flagged: list[str] = []
    for cv in report.claims:
        counts[cv.truthfulness_status] = counts.get(cv.truthfulness_status, 0) + 1
        # 公開可否の最終バー: supported かつ corroborated のみ非 flag。
        if not (
            cv.faithfulness_status == FAITHFULNESS_SUPPORTED
            and cv.truthfulness_status == TRUTHFULNESS_CORROBORATED
        ):
            flagged.append(cv.claim.claim_id)

    summary.n_corroborated = counts[TRUTHFULNESS_CORROBORATED]
    summary.n_contradicted = counts[TRUTHFULNESS_CONTRADICTED]
    summary.n_uncorroborated = counts[TRUTHFULNESS_UNCORROBORATED]
    summary.n_unverified = counts[TRUTHFULNESS_UNVERIFIED]
    summary.n_pending = counts[TRUTHFULNESS_PENDING]
    summary.completed_at = datetime.now(timezone.utc).isoformat()

    report.truthfulness_summary = summary
    report.flagged_claims = flagged
    report.schema_version = ENRICHED_SCHEMA_VERSION
    return report
