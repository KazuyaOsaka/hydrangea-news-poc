"""F-editorial-guardian-claim-extraction (1-T.1): 公開前検証 — 高リスク事実主張の
抽出 + 元ソース忠実性検証 + 2層検証レポート骨格。

ADR-0003「公開前検証 (高リスク事実主張) = 必須工程」の機械化第一歩。
X1 試運転で article 内の死者数 (3,371 人 / 10,129 人) / 兵士死亡 25 人 /
スモトリッチ発言引用が production 未検証のまま出力されることが実証された。

★ 検証の2層モデル (設計の核):
  - 第1層・忠実性 (本バッチ): 生成器 (article/script) が見た入力 = 保存済み
    イベントデータ (NewsEvent + AnalysisResult) に対し、出力中の事実主張が
    支持されるかを判定する。supported / contradicted / not_in_source の3値。
    not_in_source = 生成器が入力に無いことを書いた (ハルシネーション疑い or
    LLM の世界知識) → 未検証 flag。
  - 第2層・真実性 (1-T.2 = F-editorial-guardian-corroboration): 主張そのものが
    独立ソースで裏取りできるか (元ソース自体の正しさを含む)。本バッチでは
    スキーマ上 truthfulness_status="pending" で確保のみ。verification_queries
    (突合クエリ) は本バッチで生成まで行う。

★ flag の意味論 (1-Q.5 coverage_claim_guard の B-3' と安全方向が逆):
  公開前検証では unverified (裏が取れない = not_in_source) も人間レビュー行きの
  flag。ただし unverified は「虚偽」ではなく「検証未完」として contradicted と
  明確に区別する (LLM の沈黙を否定と読み替えない精神は維持)。
  flagged_claims = contradicted + not_in_source + unverified (判定不能)。

★ 検証の沈黙的劣化の禁止 (設計原則):
  Guardian の判定モデル (gemini-3.1-pro-preview) が落ちたとき、軽量モデルへ
  静かに fallback して「検証済み」スタンプを出すことは絶対にしない。弱いモデルの
  検証印は無検証より悪い。get_guardian_llm_client() は単一要素 tier list
  (fallback chain なし) を使い、primary 不可なら本モジュールがレポートに
  guardian_unavailable=True / 実使用モデル ID を明記して検証未完として扱う。

★ 忠実性照合の対象は「生成器が見たイベントデータ」のみ:
  生成成果物どうしの相互参照 (script 生成器は article 本文を参照する) は
  照合対象に含めない。生成物は自分の保証人になれない — article にしか無い主張が
  script に出た場合、それは not_in_source として人間レビューに回るのが安全方向。

★ アクション: 検出 → flag のみ。自動修正・再生成・公開ブロックはしない
  (公開判断はカズヤ)。article_writer.py / script_writer.py には一切触れず、
  生成成果物を外から検証する (不変原則 1-2 厳守)。

呼出例 (production 配線は本バッチ範囲外、第一作は scripts/run_editorial_guardian.py):
    report = run_editorial_guardian(scored_event, video_script, article.markdown)
    if report.flagged_claims:
        for cid in report.flagged_claims:
            ...  # 人間レビューへ
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, Field

from src.analysis.prompt_loader import load_prompt
from src.llm.base import LLMClient
from src.llm.factory import get_guardian_llm_client
from src.shared.logger import get_logger

if TYPE_CHECKING:
    from src.shared.models import ScoredEvent, VideoScript

logger = get_logger(__name__)

# ── 語彙 (第1層・忠実性) ─────────────────────────────────────────────────────
# LLM judge が返す3値。unverified は LLM の判定語彙ではなく、判定が完了しなかった
# 主張に本モジュールが付与する「検証未完」値 (contradicted と明確に区別する)。
FAITHFULNESS_SUPPORTED = "supported"
FAITHFULNESS_CONTRADICTED = "contradicted"
FAITHFULNESS_NOT_IN_SOURCE = "not_in_source"
FAITHFULNESS_UNVERIFIED = "unverified"
_VALID_FAITHFULNESS = {
    FAITHFULNESS_SUPPORTED,
    FAITHFULNESS_CONTRADICTED,
    FAITHFULNESS_NOT_IN_SOURCE,
}
# flag 対象 = supported 以外すべて (1-Q.5 B-3' と安全方向が逆:
# 「裏が取れない」も人間レビュー行き)。
_FLAGGED_STATUSES = {
    FAITHFULNESS_CONTRADICTED,
    FAITHFULNESS_NOT_IN_SOURCE,
    FAITHFULNESS_UNVERIFIED,
}

# 第2層・真実性。1-T.1 (本モジュール) は常に pending を出力し、1-T.2
# (editorial_guardian_corroboration.py) が grounding 複数ソース突合で埋める。
# 語彙 (1-T.2 = F-editorial-guardian-corroboration で確定、第1層と平行構造):
#   - corroborated:   元ソースのドメイン以外の独立ソースが主張を支持
#   - contradicted:   外部ソースが明示的に矛盾 (B-3' 哲学: 明示的矛盾のみ。
#                     見つからないことを矛盾と読み替えない)
#   - uncorroborated: 検索は成功したが独立した支持が見つからない (≠ 虚偽)
#   - unverified:     検索 or 判定が完了しなかった (harness 値、検証未完)
TRUTHFULNESS_PENDING = "pending"
TRUTHFULNESS_CORROBORATED = "corroborated"
TRUTHFULNESS_CONTRADICTED = "contradicted"
TRUTHFULNESS_UNCORROBORATED = "uncorroborated"
TRUTHFULNESS_UNVERIFIED = "unverified"

# 抽出語彙
_VALID_ARTIFACTS = {"article", "script", "title"}
_VALID_RISK_CATEGORIES = {
    "figure",               # 数字を含む事実主張 (死者数・負傷者数・金額等)
    "named_entity_fact",    # 実在の人物・組織・国家に関する事実主張
    "attributed_statement", # 実在人物の発言・声明の引用/要約
    "rights_violation",     # 人権侵害・戦争犯罪・武力行使・拘束に関する主張
    "assertive_fact",       # その他の断定的事実主張
}

_SCHEMA_VERSION = 1


# ── レポートモデル (2層検証レポート骨格) ─────────────────────────────────────

class VerificationQuery(BaseModel):
    """第2層 (1-T.2) / 人間監査用の突合クエリ 1 件。"""

    query: str
    locale: str = "en"      # 検索言語ヒント ("ja" | "en" 等)
    purpose: str = ""       # 何を確かめるためのクエリか


class CorroborationEvidence(BaseModel):
    """grounded 検索 1 クエリ分の証拠 (1-T.2 が収集、人間監査の正本)。

    検索モデルは「証拠の運搬係」であって検証者ではない (判定は Guardian が行う)。
    domains は chunk.web.title 由来の実ドメイン (redirect URL は使わない、
    F-jp-coverage-improve 知見)。resolved_urls は redirect URL の HTTP 解決で
    得た記事実体 URL (best effort、解決失敗してもバッチは止めない)。
    """

    query: str
    locale: str = "en"
    purpose: str = ""
    domains: list[str] = Field(default_factory=list)        # 実ドメイン (正規化済、全列挙)
    titles: list[str] = Field(default_factory=list)         # chunk.web.title の生値 (監査用)
    resolved_urls: list[str] = Field(default_factory=list)  # 記事実体 URL (解決できた分のみ)
    response_text: str = ""                                  # grounded 応答テキスト
    error: str = ""                                          # クエリ失敗理由 (成功時は空)


class TruthfulnessSummary(BaseModel):
    """第2層・真実性検証 (1-T.2) のレポートレベルサマリ。

    None (未設定) = 第2層未実行 (1-T.1 のみのレポート)。
    judge_unavailable=True は第2層の「検証済み」を一切意味しない (検証未完)。
    沈黙的劣化の禁止は判定層で維持: judge は Guardian 単一モデルのみ。
    """

    grounding_model_used: Optional[str] = None  # 証拠収集 (検索) モデル
    judge_model_used: Optional[str] = None      # corroboration 判定モデル (Guardian)
    judge_unavailable: bool = False
    unavailable_reason: Optional[str] = None
    source_domains: list[str] = Field(default_factory=list)  # 独立性ルールの除外基準 (元ソース)
    n_corroborated: int = 0
    n_contradicted: int = 0
    n_uncorroborated: int = 0
    n_unverified: int = 0
    n_pending: int = 0      # 第2層 skip (第1層 contradicted / unverified、修正後に再実行)
    completed_at: str = ""


class HighRiskClaim(BaseModel):
    """抽出された高リスク事実主張 1 件 (ADR-0003 公開前検証の対象)。"""

    claim_id: str           # "c1", "c2", ... (レポート内で一意)
    claim_text: str         # 正規化された主張内容
    artifact: str           # "article" | "script" | "title" | "unknown"
    risk_category: str      # _VALID_RISK_CATEGORIES のいずれか
    quote_span: str = ""    # 成果物中の該当箇所の引用


class ClaimVerification(BaseModel):
    """主張 1 件の 2 層検証状態。

    faithfulness (第1層) は本バッチで確定。truthfulness (第2層) は 1-T.2 =
    F-editorial-guardian-corroboration が埋めるまで pending で確保。
    """

    claim: HighRiskClaim
    faithfulness_status: str = FAITHFULNESS_UNVERIFIED
    faithfulness_reasoning: str = ""
    source_evidence: str = ""   # 入力素材中の支持/矛盾箇所の引用 (judge が抜粋)
    truthfulness_status: str = TRUTHFULNESS_PENDING
    truthfulness_notes: str = ""  # skip 理由 / harness 安全網の記録等 (1-T.2 が埋める)
    verification_queries: list[VerificationQuery] = Field(default_factory=list)
    # ── 以下は 1-T.2 (editorial_guardian_corroboration.py) が埋める ──────────
    truthfulness_reasoning: str = ""  # corroboration 判定理由 (根拠ドメイン明示)
    corroborating_domains: list[str] = Field(default_factory=list)  # 独立支持ドメイン (検証済)
    truthfulness_evidence: list[CorroborationEvidence] = Field(default_factory=list)
    truthfulness_verified_at: str = ""  # claim 単位の検証時刻 (ISO 8601)


class SourceMaterialScope(BaseModel):
    """忠実性照合に使った素材の範囲 (仮説1: 何と照合したかを必ず記録する)。

    元ソース「全文」は NewsEvent に専用フィールドが無く、ingestion が
    event.summary / global_view に raw テキストを埋め込んだ範囲でのみ存在する。
    生成器もそれ以上を見ていないため第1層はこの範囲で成立するが、その事実を
    本モデルで明示する (1-T.2 の真実性検証は外部ソースで補完する)。
    """

    has_event: bool = False
    has_analysis: bool = False
    event_summary_chars: int = 0
    event_global_view_chars: int = 0
    notes: str = ""


class EditorialGuardianReport(BaseModel):
    """Editorial Guardian の 2 層検証レポート。

    guardian_unavailable=True のレポートは「検証済み」を一切意味しない
    (検証未完)。guardian_model_used は実際に判定に使ったモデル ID
    (単一モデル運用のため常に primary、失敗時も試行したモデルを記録)。
    """

    schema_version: int = _SCHEMA_VERSION
    event_id: str
    generated_at: str = ""
    guardian_model_used: Optional[str] = None
    guardian_unavailable: bool = False
    unavailable_reason: Optional[str] = None
    source_material_scope: SourceMaterialScope = Field(
        default_factory=SourceMaterialScope
    )
    claims: list[ClaimVerification] = Field(default_factory=list)
    flagged_claims: list[str] = Field(default_factory=list)  # claim_id 群
    n_supported: int = 0
    n_contradicted: int = 0
    n_not_in_source: int = 0
    n_unverified: int = 0
    # ── 1-T.2 (corroboration) が enrichment 時に設定 (None = 第2層未実行) ────
    truthfulness_summary: Optional[TruthfulnessSummary] = None


# ── 入力ブロック整形 ─────────────────────────────────────────────────────────

def _build_title_block(video_script: "VideoScript") -> str:
    """VideoScript の title 層を抽出入力ブロックに整形 (coverage_claim_guard と同方針)。"""
    tl = getattr(video_script, "title_layer", None)
    lines: list[str] = []
    if tl is not None:
        lines.append(f"platform_title: {tl.platform_title or '(none)'}")
        lines.append(f"canonical_title: {tl.canonical_title or '(none)'}")
        lines.append(f"hook_line: {tl.hook_line or '(none)'}")
        if tl.thumbnail_text:
            lines.append(f"thumbnail_text: {tl.thumbnail_text}")
    else:
        lines.append(f"title: {getattr(video_script, 'title', '') or '(none)'}")
    return "\n".join(lines)


def _build_script_block(video_script: "VideoScript") -> str:
    """台本ナレーション (intro + sections + outro) を抽出入力ブロックに整形。

    新ルートでは intro/outro は空文字列だが、旧形式 script.json との互換のため
    非空なら含める (仮説2: 高リスク主張はナレーション全体に分布しうる)。
    """
    lines: list[str] = []
    intro = (getattr(video_script, "intro", "") or "").strip()
    if intro:
        lines.append(f"[intro] {intro}")
    for section in getattr(video_script, "sections", None) or []:
        body = (getattr(section, "body", "") or "").strip()
        if body:
            lines.append(f"[{section.heading}] {body}")
    outro = (getattr(video_script, "outro", "") or "").strip()
    if outro:
        lines.append(f"[outro] {outro}")
    return "\n".join(lines) if lines else "(none)"


def _build_source_material(scored_event: "ScoredEvent") -> tuple[str, SourceMaterialScope]:
    """忠実性照合用の「生成器が見たイベントデータ」ブロックと scope を返す。

    含めるもの: NewsEvent 全フィールド (article 生成器が JSON 全文を見る、
    script 新ルートは title/summary を見る) + AnalysisResult 全フィールド
    (script 新ルートが perspective/multi_angle/insights/particular_angle を見る、
    article 生成器も ScoredEvent JSON 経由で見る)。

    含めないもの (scope.notes に記録):
      - 生成成果物どうしの相互参照 (script が見た article 本文等) — 生成物は
        自分の保証人になれない。
      - 生成時 ScoredEvent の judge_result / editorial_mission_* 等の wrapper
        フィールド — recent_event_pool.event_snapshot は分析・審判前に保存される
        ため再構成不能 (CP-1 実測: X1 Slot-1 snapshot は analysis_result=None)。
    """
    notes = [
        "faithfulness layer compares against event data only; "
        "generated artifacts are excluded from source material "
        "(a generated artifact cannot vouch for another).",
        "generation-time ScoredEvent wrapper fields (judge_result / "
        "editorial_mission_*) are not reconstructable from the pool snapshot "
        "and are excluded.",
    ]
    scope = SourceMaterialScope(notes=" ".join(notes))
    blocks: list[str] = []

    event = getattr(scored_event, "event", None)
    if event is not None:
        scope.has_event = True
        scope.event_summary_chars = len(event.summary or "")
        scope.event_global_view_chars = len(event.global_view or "")
        blocks.append("### イベントデータ (NewsEvent、生成器入力)\n" + event.model_dump_json(indent=2))
    else:
        blocks.append("### イベントデータ\n(missing)")

    analysis = getattr(scored_event, "analysis_result", None)
    if analysis is not None:
        scope.has_analysis = True
        blocks.append(
            "### 分析レイヤー出力 (AnalysisResult、生成器入力)\n"
            + analysis.model_dump_json(indent=2)
        )
    else:
        blocks.append("### 分析レイヤー出力\n(missing)")

    return "\n\n".join(blocks), scope


# ── LLM 応答パース (extractor / guard と同方針) ─────────────────────────────

def _parse_llm_response(text: str) -> dict:
    """LLM 応答テキストから JSON を抽出してパース。"""
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


def _coerce_artifact(v: object) -> str:
    s = str(v or "").strip().lower()
    return s if s in _VALID_ARTIFACTS else "unknown"


def _coerce_risk_category(v: object) -> str:
    s = str(v or "").strip().lower()
    return s if s in _VALID_RISK_CATEGORIES else "assertive_fact"


def _coerce_faithfulness(v: object) -> str:
    """judge の status を3値に正規化。不明値は unverified (検証未完 = flag、
    contradicted とは区別) に倒す。"""
    s = str(v or "").strip().lower()
    return s if s in _VALID_FAITHFULNESS else FAITHFULNESS_UNVERIFIED


def _build_claims(payload: dict) -> list[HighRiskClaim]:
    """抽出 LLM の出力 dict から HighRiskClaim 群を構築する (coercion 込)。"""
    claims: list[HighRiskClaim] = []
    seen_ids: set[str] = set()
    for idx, raw in enumerate(payload.get("claims") or [], start=1):
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("claim_text") or "").strip()
        if not text:
            continue
        cid = str(raw.get("claim_id") or "").strip() or f"c{idx}"
        if cid in seen_ids:
            cid = f"c{idx}"
        seen_ids.add(cid)
        claims.append(
            HighRiskClaim(
                claim_id=cid,
                claim_text=text,
                artifact=_coerce_artifact(raw.get("artifact")),
                risk_category=_coerce_risk_category(raw.get("risk_category")),
                quote_span=str(raw.get("quote_span") or "").strip(),
            )
        )
    return claims


def _build_queries(raw_queries: object) -> list[VerificationQuery]:
    """judge 出力の verification_queries を構築する。"""
    queries: list[VerificationQuery] = []
    if not isinstance(raw_queries, list):
        return queries
    for raw in raw_queries:
        if not isinstance(raw, dict):
            continue
        q = str(raw.get("query") or "").strip()
        if not q:
            continue
        locale = str(raw.get("locale") or "en").strip().lower() or "en"
        queries.append(
            VerificationQuery(
                query=q,
                locale=locale,
                purpose=str(raw.get("purpose") or "").strip(),
            )
        )
    return queries


def _resolve_model_id(llm: LLMClient) -> str:
    """実使用モデル ID を取り出す (単一モデル運用のため primary = 実使用)。

    TieredGeminiClient は `_model` property (= tiers[0]) を持つ。DI された
    テスト用クライアントが持たない場合は "(injected)" を記録する。
    """
    model = getattr(llm, "_model", None)
    return str(model) if model else "(injected)"


def _generate_with_retry(
    llm: LLMClient,
    prompt: str,
    *,
    stage: str,
    max_retries: int,
) -> dict:
    """LLM 呼出 + JSON パース (リトライ込)。失敗し尽くしたら例外を再送出する。

    ★ ここで例外を握りつぶして部分結果を返すことはしない (沈黙的劣化の禁止)。
    呼出側 (run_editorial_guardian) が guardian_unavailable として明示する。
    """
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            raw = llm.generate(prompt)
            if not raw or not raw.strip():
                raise ValueError("LLM returned empty response")
            return _parse_llm_response(raw)
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            last_error = exc
            logger.warning(
                f"[EditorialGuardian] {stage} attempt {attempt}/{max_retries} "
                f"parse error: {str(exc)[:150]}"
            )
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(
                f"[EditorialGuardian] {stage} attempt {attempt}/{max_retries} "
                f"api error: {type(exc).__name__}: {str(exc)[:150]}"
            )
    assert last_error is not None
    raise last_error


def _finalize_report(report: EditorialGuardianReport) -> EditorialGuardianReport:
    """flagged_claims と件数サマリを claims から導出して埋める。"""
    flagged: list[str] = []
    counts = {
        FAITHFULNESS_SUPPORTED: 0,
        FAITHFULNESS_CONTRADICTED: 0,
        FAITHFULNESS_NOT_IN_SOURCE: 0,
        FAITHFULNESS_UNVERIFIED: 0,
    }
    for cv in report.claims:
        counts[cv.faithfulness_status] = counts.get(cv.faithfulness_status, 0) + 1
        if cv.faithfulness_status in _FLAGGED_STATUSES:
            flagged.append(cv.claim.claim_id)
    report.flagged_claims = flagged
    report.n_supported = counts[FAITHFULNESS_SUPPORTED]
    report.n_contradicted = counts[FAITHFULNESS_CONTRADICTED]
    report.n_not_in_source = counts[FAITHFULNESS_NOT_IN_SOURCE]
    report.n_unverified = counts[FAITHFULNESS_UNVERIFIED]
    return report


# ── 公開 API ─────────────────────────────────────────────────────────────────

def run_editorial_guardian(
    scored_event: "ScoredEvent",
    video_script: "VideoScript",
    article_markdown: str,
    *,
    channel_id: str = "geo_lens",
    client: Optional[LLMClient] = None,
    max_retries: int = 2,
) -> EditorialGuardianReport:
    """生成済み成果物の高リスク事実主張を抽出し、第1層・忠実性を検証する。

    Args:
        scored_event: 生成器が見たイベントデータの再構成 (event + analysis_result)。
        video_script: 生成済み台本 (title_layer + ナレーション)。
        article_markdown: 生成済み記事本文 (Markdown)。
        channel_id: プロンプト解決用 (default "geo_lens")。
        client: テスト/DI 用 LLM クライアント。None なら get_guardian_llm_client()
                (gemini-3.1-pro-preview 単一モデル、fallback chain なし)。
        max_retries: LLM 呼出失敗時のリトライ回数 (同一モデルのみ)。

    Returns:
        EditorialGuardianReport (2層検証レポート)。検出は flag のみ
        (自動修正・再生成・公開ブロックはしない、公開判断はカズヤ)。
        Guardian モデル不可時は guardian_unavailable=True で検証未完を明示する
        (下位モデルで検証を続行しない = 沈黙的劣化の禁止)。
    """
    event_id = getattr(getattr(scored_event, "event", None), "id", "") or ""
    generated_at = datetime.now(timezone.utc).isoformat()
    source_material, scope = _build_source_material(scored_event)

    report = EditorialGuardianReport(
        event_id=event_id,
        generated_at=generated_at,
        source_material_scope=scope,
    )

    llm = client if client is not None else get_guardian_llm_client()
    if llm is None:
        logger.warning(
            "[EditorialGuardian] no guardian LLM client available; "
            "report is guardian_unavailable (検証未完)."
        )
        report.guardian_unavailable = True
        report.unavailable_reason = (
            "no guardian LLM client (GEMINI_API_KEY missing or non-gemini provider); "
            "verification NOT performed"
        )
        return report

    report.guardian_model_used = _resolve_model_id(llm)

    # プロンプトロード失敗も検証未完として明示する (静かな skip にしない)。
    try:
        extract_template = load_prompt(channel_id, "editorial_guardian_extract")
        judge_template = load_prompt(channel_id, "editorial_guardian_faithfulness")
    except FileNotFoundError as exc:
        logger.error(f"[EditorialGuardian] prompt not found: {exc}")
        report.guardian_unavailable = True
        report.unavailable_reason = f"guardian prompt not found: {exc}"
        return report

    # ── Stage 1: 高リスク主張の抽出 (Guardian モデル) ────────────────────────
    extract_prompt = extract_template.format(
        event_id=event_id,
        title_block=_build_title_block(video_script),
        script_block=_build_script_block(video_script),
        article_text=(article_markdown or "").strip() or "(none)",
    )
    try:
        extract_payload = _generate_with_retry(
            llm, extract_prompt, stage="extract", max_retries=max_retries
        )
    except Exception as exc:  # noqa: BLE001
        report.guardian_unavailable = True
        report.unavailable_reason = (
            f"claim extraction failed after {max_retries} attempts: "
            f"{type(exc).__name__}: {str(exc)[:200]}"
        )
        logger.error(f"[EditorialGuardian] {report.unavailable_reason}")
        return report

    claims = _build_claims(extract_payload)
    if not claims:
        logger.info(
            f"[EditorialGuardian] event_id={event_id} no high-risk claims extracted "
            f"(model={report.guardian_model_used})"
        )
        return _finalize_report(report)

    # ── Stage 2: 第1層・忠実性判定 + 突合クエリ生成 (Guardian モデル) ─────────
    claims_json = json.dumps(
        [c.model_dump() for c in claims], ensure_ascii=False, indent=2
    )
    judge_prompt = judge_template.format(
        event_id=event_id,
        source_material=source_material,
        claims_json=claims_json,
    )
    try:
        judge_payload = _generate_with_retry(
            llm, judge_prompt, stage="faithfulness", max_retries=max_retries
        )
        verdicts_by_id: dict[str, dict] = {}
        for raw in judge_payload.get("verdicts") or []:
            if isinstance(raw, dict) and raw.get("claim_id"):
                verdicts_by_id[str(raw["claim_id"]).strip()] = raw
    except Exception as exc:  # noqa: BLE001
        # 判定が走らなかった主張は unverified (検証未完) として全件 flag する。
        report.guardian_unavailable = True
        report.unavailable_reason = (
            f"faithfulness judgement failed after {max_retries} attempts: "
            f"{type(exc).__name__}: {str(exc)[:200]}"
        )
        logger.error(f"[EditorialGuardian] {report.unavailable_reason}")
        report.claims = [
            ClaimVerification(
                claim=c,
                faithfulness_status=FAITHFULNESS_UNVERIFIED,
                faithfulness_reasoning="guardian unavailable; judgement not performed",
            )
            for c in claims
        ]
        return _finalize_report(report)

    verifications: list[ClaimVerification] = []
    for c in claims:
        verdict = verdicts_by_id.get(c.claim_id)
        if verdict is None:
            # judge が当該主張の判定を返さなかった → 検証未完 (flag)。
            verifications.append(
                ClaimVerification(
                    claim=c,
                    faithfulness_status=FAITHFULNESS_UNVERIFIED,
                    faithfulness_reasoning="no verdict returned for this claim",
                )
            )
            continue
        verifications.append(
            ClaimVerification(
                claim=c,
                faithfulness_status=_coerce_faithfulness(verdict.get("status")),
                faithfulness_reasoning=str(verdict.get("reasoning") or "").strip(),
                source_evidence=str(verdict.get("source_evidence") or "").strip(),
                verification_queries=_build_queries(verdict.get("verification_queries")),
            )
        )

    report.claims = verifications
    report = _finalize_report(report)
    logger.info(
        f"[EditorialGuardian] event_id={event_id} model={report.guardian_model_used} "
        f"claims={len(report.claims)} supported={report.n_supported} "
        f"contradicted={report.n_contradicted} not_in_source={report.n_not_in_source} "
        f"unverified={report.n_unverified} flagged={len(report.flagged_claims)}"
    )
    return report
