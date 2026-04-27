"""factory.py — Role-based LLM client factory with unified Tier hierarchy.

Routing strategy (Phase 1.5 batch E-2 以降):
  全 Gemini 経由の LLM 呼び出しは、TIER1 → TIER2 → TIER3 → TIER4 の統一
  4 段フォールバックに乗る。役割（garbage_filter / cluster_merge / judge /
  generation / analysis）による経路分岐はなく、すべて TieredGeminiClient で
  同一の Tier 階層を共有する。

  旧 lightweight 経路（専用モデル env 固定、フォールバックなし）は E-2 で廃止された。
  背景は実 LLM 試運転 (2026-04-27) で gemini-2.5-flash-lite が無料枠 RPD=20 を
  超過した一方、TIER1 の gemini-3.1-flash-lite-preview (RPD=500) には大きな
  余裕があったこと。全呼び出しを統一階層に乗せて RPD=500 を主軸として使う。

Per-tier retry policy:
  - 429 / RESOURCE_EXHAUSTED → skip same-model retries, advance to next tier
    immediately. Gemini counts failed 429s against quota, so retrying the same
    model after a quota refusal just burns the daily allowance for nothing.
  - 503 / UNAVAILABLE / other retryables → exponential backoff up to
    _MAX_ATTEMPTS_PER_TIER attempts, then advance.

Fallback priority — RPM 上限の高い順に降格:
  [1] gemini-3.1-flash-lite-preview  (TIER1, RPM=15, RPD=500)
  [2] gemini-2.5-flash-lite          (TIER2, RPM=10, RPD=20)
  [3] gemini-3-flash-preview         (TIER3, RPM=5,  RPD=20)
  [4] gemini-2.5-flash               (TIER4, RPM=5,  RPD=20)

Rate limiting (二段構え):
  - 動的レートリミッタ (TieredGeminiClient._wait_for_rpm_slot): 直近60秒の
    呼び出し履歴をモデル別に保持し、上限の安全率 (_RPM_SAFETY_RATIO=0.7) を
    超えそうな場合に sleep する。並行呼び出しのバーストを抑止。
  - 静的最低間隔 (TieredGeminiClient._throttle): GEMINI_CALL_INTERVAL_SEC_TIER{1..4}
    で前回同一モデル呼び出しからの最低間隔を保証。単一スレッドの連続呼び出しを抑止。
  両者は generate() 内で「動的 → 静的」の順に併用される。

Resolution path: .env → config.py → factory.py
No hardcoded model strings in business logic.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from src.llm.base import LLMClient
from src.llm.retry import is_quota_error, is_retryable
from src.shared.config import (
    GEMINI_API_KEY,
    GEMINI_CALL_INTERVAL_SEC,
    GEMINI_INTERVAL_SEC_BY_MODEL,
    GEMINI_MODEL_TIER1,
    GEMINI_MODEL_TIER2,
    GEMINI_MODEL_TIER3,
    GEMINI_MODEL_TIER4,
    GEMINI_MODEL_TIERS,
    GEMINI_RPM_LIMIT_BY_MODEL,
    GENERATION_MODEL,
    GENERATION_PROVIDER,
    GROQ_API_KEY,
    MERGE_BATCH_MODEL,
    MERGE_BATCH_PROVIDER,
    OLLAMA_BASE_URL,
)
from src.shared.logger import get_logger

logger = get_logger(__name__)

_MAX_ATTEMPTS_PER_TIER = 3
_INITIAL_DELAY_SEC = 15.0
_MAX_DELAY_SEC = 120.0

# 429対策: 最大同時API呼び出し数を3に制限 (15 RPM制限を安全に回避)
_API_SEMAPHORE = threading.Semaphore(3)

# 動的レートリミッタの安全率: RPM 上限の何割まで使うか。
# 70% に設定: gemini-3.1-flash-lite-preview (RPM=15) の場合 60秒で 10 件まで許可。
_RPM_SAFETY_RATIO = 0.7

# RPM 不明モデル（GEMINI_RPM_LIMIT_BY_MODEL に未登録）の保守的なデフォルト。
# 無料枠で最も低い RPM=5 を採用し、未知モデルでも上限超過しないようにする。
_RPM_DEFAULT_LIMIT = 5


class TieredGeminiClient(LLMClient):
    """GeminiClient that walks through a provided tier list on quota exhaustion.

    Per-tier policy:
      - 429 / RESOURCE_EXHAUSTED: skip same-model retries, advance to next tier
        immediately. Failed 429 requests still count against Gemini quota, so
        retrying the same model is wasted budget.
      - 503 / UNAVAILABLE (and other retryables): up to _MAX_ATTEMPTS_PER_TIER
        retries with exponential backoff before advancing.
    If all tiers are exhausted, RuntimeError is raised.

    Single-element tier list → same-model retry only (on 503), no fallback.
    On 429 with a single-element list, the loop exits after one attempt and
    raises RuntimeError without burning the rest of the day's quota.
    """

    def __init__(
        self,
        api_key: str,
        tiers: list[str],
        generation_config: Optional[dict] = None,
    ) -> None:
        self._api_key = api_key
        self._tiers = tiers
        # モデル単位の最終呼び出し時刻を保持し、各モデルの RPM 上限に応じた
        # インターバル制御を行う。Gemini の RPM はモデル毎に独立してカウント
        # されるため、tier_idx ではなく実モデル名で追跡する。
        self._last_call_time_by_model: dict[str, float] = {}
        # モデル別の呼び出し履歴（直近60秒分の time.time() タイムスタンプ列）。
        # _wait_for_rpm_slot が「過去60秒の呼び出しが上限の安全率を超えたら待つ」
        # を判定するために使う。複数スレッドからアクセスされる可能性があるため
        # ロックで保護する。
        self._call_history_by_model: dict[str, list[float]] = {}
        self._history_lock = threading.Lock()
        # Optional per-call generation config (temperature, max_output_tokens, etc.).
        # 既存呼び出し元は None のまま — 従来挙動そのまま。
        # 分析レイヤーのように temperature/トークン上限を明示したいクライアントだけ設定する。
        self._generation_config: Optional[dict] = generation_config or None

    @property
    def _model(self) -> str:
        """The primary (tier 1) model this client will attempt first.

        Kept as a property (not a stored attribute) so it always reflects the
        current tier list if that is ever reassigned. Down-stream code and tests
        expecting a single-model GeminiClient-style `_model` attribute keep
        working without caring whether the underlying client does tiered fallback.
        """
        return self._tiers[0] if self._tiers else ""

    def _throttle(self, model: str) -> None:
        """Enforce per-model minimum interval between API calls.

        各モデルの RPM 上限に対応した GEMINI_CALL_INTERVAL_SEC_TIER{n} を引き、
        前回同一モデル呼び出しからの経過時間が不足する場合は差分だけ sleep する。
        マッピングに無いモデルは後方互換用の GEMINI_CALL_INTERVAL_SEC を使用。
        """
        interval = GEMINI_INTERVAL_SEC_BY_MODEL.get(model, GEMINI_CALL_INTERVAL_SEC)
        last = self._last_call_time_by_model.get(model, 0.0)
        elapsed = time.time() - last
        wait = interval - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_call_time_by_model[model] = time.time()

    def _wait_for_rpm_slot(self, model: str) -> None:
        """Sliding-window 60秒の呼び出し履歴を見て RPM 上限近くなら待機する。

        静的な _throttle (前回呼び出しからの最低間隔) は単一スレッドの連続呼び出しは
        防げるが、複数経路から並行で短時間に呼ばれた場合のバーストには対処できない。
        本メソッドは直近 60 秒の履歴件数が `RPM 上限 × _RPM_SAFETY_RATIO` を超える
        場合、最古エントリから 60 秒経過するまで sleep して RPM 超過を防ぐ。

        - GEMINI_RPM_LIMIT_BY_MODEL に未登録のモデルは保守的に _RPM_DEFAULT_LIMIT を採用。
        - 履歴の管理は self._history_lock で保護し、複数スレッドからの同時更新を防ぐ。
        - sleep は lock 解放後に実施し、待機中も他スレッドの履歴判定をブロックしない。
        """
        rpm_limit = GEMINI_RPM_LIMIT_BY_MODEL.get(model, _RPM_DEFAULT_LIMIT)
        threshold = max(1, int(rpm_limit * _RPM_SAFETY_RATIO))

        wait = 0.0
        with self._history_lock:
            now = time.time()
            history = self._call_history_by_model.setdefault(model, [])
            # 60 秒より古いエントリは破棄
            history[:] = [t for t in history if now - t < 60.0]
            if len(history) >= threshold:
                sleep_until = history[0] + 60.0
                wait = max(0.0, sleep_until - now)

        if wait > 0:
            logger.info(
                f"[TieredGemini] RPM throttle: model={model} "
                f"recent_calls>={threshold}/{rpm_limit} → wait {wait:.1f}s"
            )
            time.sleep(wait)
            with self._history_lock:
                # 待機後にもう一度ウィンドウを掃除しておく
                now2 = time.time()
                history = self._call_history_by_model.setdefault(model, [])
                history[:] = [t for t in history if now2 - t < 60.0]

        with self._history_lock:
            self._call_history_by_model.setdefault(model, []).append(time.time())

    def generate(self, prompt: str) -> str:
        from google import genai
        from google.genai import types as genai_types

        client = genai.Client(api_key=self._api_key)
        last_exc: Exception | None = None

        config_obj = (
            genai_types.GenerateContentConfig(**self._generation_config)
            if self._generation_config
            else None
        )

        for tier_idx, model in enumerate(self._tiers, start=1):
            delay = _INITIAL_DELAY_SEC
            for attempt in range(_MAX_ATTEMPTS_PER_TIER):
                try:
                    with _API_SEMAPHORE:
                        # 動的レートリミッタ（直近60秒履歴）→ 静的最低間隔の二段構え。
                        # 並行呼び出しのバーストは前者が、単一スレッドの連続呼び出しは
                        # 後者が抑止する。順序は「履歴で待機 → 最低間隔で待機」を維持。
                        self._wait_for_rpm_slot(model)
                        self._throttle(model)
                        gen_kwargs: dict = {"model": model, "contents": prompt}
                        if config_obj is not None:
                            gen_kwargs["config"] = config_obj
                        response = client.models.generate_content(**gen_kwargs)
                    if tier_idx > 1 or attempt > 0:
                        logger.info(
                            f"[TieredGemini] Success: tier={tier_idx} model={model} "
                            f"attempt={attempt + 1}/{_MAX_ATTEMPTS_PER_TIER}"
                        )
                    return response.text.strip()
                except Exception as exc:
                    if not is_retryable(exc):
                        raise
                    last_exc = exc

                    # 429 (RESOURCE_EXHAUSTED) は同一モデルへのリトライがクォータを更に消費するだけなので
                    # 即座に次の Tier へフォールバックする。Gemini は失敗した 429 リクエストもクォータ
                    # カウントに含めるため、リトライしても回復は期待できない。
                    if is_quota_error(exc):
                        if tier_idx < len(self._tiers):
                            next_model = self._tiers[tier_idx]
                            next_label = f"tier {tier_idx + 1} ({next_model})"
                        else:
                            next_label = "none (all tiers exhausted)"
                        logger.info(
                            f"[TieredGemini] tier={tier_idx} model={model} "
                            f"429 RESOURCE_EXHAUSTED → skip retries, advance to {next_label}. "
                            f"Error: {str(exc)[:120]}"
                        )
                        break

                    # 503 / UNAVAILABLE 等の一時的エラーは従来通り指数バックオフで再試行する。
                    if attempt < _MAX_ATTEMPTS_PER_TIER - 1:
                        logger.warning(
                            f"[TieredGemini] tier={tier_idx} model={model} "
                            f"attempt={attempt + 1}/{_MAX_ATTEMPTS_PER_TIER} transient error — "
                            f"retrying in {delay:.0f}s: {str(exc)[:120]}"
                        )
                        time.sleep(delay)
                        delay = min(delay * 2, _MAX_DELAY_SEC)
                    else:
                        if tier_idx < len(self._tiers):
                            next_model = self._tiers[tier_idx]
                            next_label = f"tier {tier_idx + 1} ({next_model})"
                        else:
                            next_label = "none (all tiers exhausted)"
                        logger.warning(
                            f"[TieredGemini] FAIL tier={tier_idx} model={model} — "
                            f"all {_MAX_ATTEMPTS_PER_TIER} attempts exhausted. "
                            f"Next: {next_label}. Error: {str(exc)[:120]}"
                        )

        assert last_exc is not None
        raise RuntimeError(
            f"All {len(self._tiers)} Gemini tier(s) exhausted. "
            f"Models tried: {self._tiers}. "
            f"Last error: {last_exc}"
        ) from last_exc


# ── Internal factory helpers ─────────────────────────────────────────────────

def _make_tiered_gemini_client() -> Optional[LLMClient]:
    """統一 Tier 階層クライアント: TIER1→TIER2→TIER3→TIER4 完全4段フォールバック。

    Phase 1.5 batch E-2 以降、garbage_filter / cluster_merge / judge / generation /
    analysis すべてのロールがこの統一階層を共有する。専用 lightweight ルート
    （単一モデル固定 env による経路）は廃止された。
    """
    if not GEMINI_API_KEY:
        return None
    return TieredGeminiClient(
        GEMINI_API_KEY,
        [GEMINI_MODEL_TIER1, GEMINI_MODEL_TIER2, GEMINI_MODEL_TIER3, GEMINI_MODEL_TIER4],
    )


def _make_client(provider: str, model: str) -> Optional[LLMClient]:
    """Construct an LLMClient for the given provider + model pair.

    For Gemini, `model` is ignored — all roles share the unified Tier hierarchy
    (TIER1→TIER4). The previous `quality` flag was removed in batch E-2 along
    with the lightweight bypass.
    """
    if provider == "gemini":
        return _make_tiered_gemini_client()

    if provider == "groq":
        from src.llm.groq import GroqClient
        return GroqClient(GROQ_API_KEY, model)

    if provider == "ollama":
        from src.llm.ollama import OllamaClient
        return OllamaClient(OLLAMA_BASE_URL, model)

    return None


def get_llm_client(role: str) -> Optional[LLMClient]:
    """Get an LLM client by role name.

    All Gemini roles share the unified Tier hierarchy (TIER1→TIER4); the role
    only switches provider/model resolution for non-Gemini providers.

    Args:
        role: One of "merge_batch", "judge", or "generation".

    Returns:
        Configured LLMClient, or None if the provider is not configured.

    Raises:
        ValueError: If role is not recognised.
    """
    if role == "merge_batch":
        return _make_client(MERGE_BATCH_PROVIDER, MERGE_BATCH_MODEL)

    if role == "judge":
        return get_judge_llm_client()

    if role == "generation":
        return _make_client(GENERATION_PROVIDER, GENERATION_MODEL)

    raise ValueError(
        f"Unknown LLM role: {role!r}. Must be 'merge_batch', 'judge', or 'generation'."
    )


# ── Named client accessors (called by business logic) ───────────────────────

def get_garbage_filter_client() -> Optional[LLMClient]:
    """Gate 1 Garbage Filter 用クライアント — 統一 Tier 階層 (TIER1→TIER4)。

    E-2 までは専用モデル固定で同一モデル retry-only だったが、無料枠 RPD=20 を
    超過する事故が発生したため統一 Tier 階層に統合した。高 RPD (=500) の
    TIER1 を主軸に走り、quota 切れ時は TIER2→4 へフォールバック。
    """
    return get_llm_client("merge_batch")


def get_cluster_llm_client() -> Optional[LLMClient]:
    """Event Builder / cluster post-merge 用クライアント — 統一 Tier 階層。

    挙動は get_garbage_filter_client と同一。role="merge_batch" 経由で
    TIER1→TIER4 完全フォールバックを使う。
    """
    return get_llm_client("merge_batch")


def get_judge_llm_client() -> Optional[LLMClient]:
    """Elite Judge / Gemini Judge 用クライアント — 統一 Tier 階層。

    model_registry.get_judge_model_resolution() が models.list で解決した
    resolved_model を primary tier として採用し、残りの TIER2〜TIER4 を
    フォールバックに連結する（重複除去済み）。
    GEMINI_API_KEY 未設定 or models.list が使えない場合は従来通り
    [TIER1, TIER2, TIER3, TIER4] で構築する。
    """
    if not GEMINI_API_KEY:
        return None

    # Import here to keep the module import graph light (model_registry imports
    # google.genai at call time).
    # JUDGE_MODEL は role-based で config が単一解決; GEMINI_JUDGE_MODEL は back-compat alias。
    from src.shared.config import GEMINI_JUDGE_FALLBACK_MODELS, JUDGE_MODEL
    from src.llm.model_registry import get_judge_model_resolution

    try:
        resolution = get_judge_model_resolution(
            GEMINI_API_KEY, JUDGE_MODEL, GEMINI_JUDGE_FALLBACK_MODELS
        )
        resolved = resolution.resolved_model
    except Exception as exc:
        logger.warning(
            f"[Factory] Judge model resolution failed ({exc}); "
            f"falling back to full TIER1→TIER4 list."
        )
        resolved = ""

    if not resolved:
        return TieredGeminiClient(
            GEMINI_API_KEY,
            [GEMINI_MODEL_TIER1, GEMINI_MODEL_TIER2, GEMINI_MODEL_TIER3, GEMINI_MODEL_TIER4],
        )

    # resolved を primary に置き、残り Tier を重複除去して後続に連結する。
    # dict.fromkeys で順序を保ったまま重複除去。
    tiers = list(dict.fromkeys(
        [resolved, GEMINI_MODEL_TIER1, GEMINI_MODEL_TIER2, GEMINI_MODEL_TIER3, GEMINI_MODEL_TIER4]
    ))
    return TieredGeminiClient(GEMINI_API_KEY, tiers)


def get_script_llm_client() -> Optional[LLMClient]:
    """Script Writer 用クライアント — 統一 Tier 階層 (role=generation)。

    GENERATION_PROVIDER=gemini の場合: TIER1→TIER4 完全4段フォールバック。
    GENERATION_PROVIDER=groq/ollama の場合: 該当プロバイダの単一クライアント。
    未知プロバイダ / APIキー未設定の場合: None。
    """
    return get_llm_client("generation")


def get_article_llm_client() -> Optional[LLMClient]:
    """Article Writer 用クライアント — 統一 Tier 階層 (role=generation)。"""
    return get_llm_client("generation")


def get_analysis_llm_client() -> Optional[LLMClient]:
    """分析レイヤー（Step 3〜5）用クライアント — 統一 Tier 階層 + 事実重視設定。

    観点選定+検証 / 多角的分析 / 洞察抽出 で共通利用される。
    GENERATION_PROVIDER=gemini の場合: TIER1→TIER2→TIER3→TIER4 完全4段フォールバック
    （TIER4 は最終フォールバックとしてのみ使用）。
    temperature と max_output_tokens は環境変数 ANALYSIS_LLM_TEMPERATURE /
    ANALYSIS_LLM_MAX_TOKENS で上書き可能（デフォルト 0.3 / 2000）。

    Gemini 以外のプロバイダ / API キー未設定時は既存のスクリプト用クライアントに委譲し、
    プロバイダ固有のフォールバックに任せる（現状 Groq/Ollama は temperature 制御なし）。
    """
    import os

    if not GEMINI_API_KEY or GENERATION_PROVIDER != "gemini":
        return _make_client(GENERATION_PROVIDER, GENERATION_MODEL)

    try:
        temperature = float(os.getenv("ANALYSIS_LLM_TEMPERATURE", "0.3"))
    except ValueError:
        temperature = 0.3
    try:
        max_tokens = int(os.getenv("ANALYSIS_LLM_MAX_TOKENS", "2000"))
    except ValueError:
        max_tokens = 2000

    return TieredGeminiClient(
        GEMINI_API_KEY,
        [GEMINI_MODEL_TIER1, GEMINI_MODEL_TIER2, GEMINI_MODEL_TIER3, GEMINI_MODEL_TIER4],
        generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
    )


# ── Tier connectivity verification ──────────────────────────────────────────

def verify_tier_connectivity(probe_prompt: str = "Reply with the single word OK.") -> dict:
    """Verify that GEMINI_API_KEY can reach each tier model.

    Sends `probe_prompt` to each tier in GEMINI_MODEL_TIERS and records
    success/failure.  Does NOT use the tiered fallback — each tier is tested
    independently so failures are individually visible.

    Returns:
        dict mapping model name → {"ok": bool, "response": str | None, "error": str | None}

    Raises:
        RuntimeError: If GEMINI_API_KEY is not set.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set — cannot verify connectivity.")

    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)
    results: dict = {}

    for tier_idx, model in enumerate(GEMINI_MODEL_TIERS, start=1):
        logger.info(f"[VerifyTier] Probing TIER{tier_idx}: {model}")
        try:
            response = client.models.generate_content(
                model=model,
                contents=probe_prompt,
            )
            text = response.text.strip()
            results[model] = {"tier": tier_idx, "ok": True, "response": text, "error": None}
            logger.info(f"[VerifyTier] TIER{tier_idx} {model}: OK → {text!r}")
        except Exception as exc:
            results[model] = {"tier": tier_idx, "ok": False, "response": None, "error": str(exc)}
            logger.error(f"[VerifyTier] TIER{tier_idx} {model}: FAILED → {exc}")

    ok_count = sum(1 for v in results.values() if v["ok"])
    logger.info(
        f"[VerifyTier] Result: {ok_count}/{len(GEMINI_MODEL_TIERS)} tiers reachable. "
        f"Models: {GEMINI_MODEL_TIERS}"
    )
    return results


if __name__ == "__main__":
    import json
    results = verify_tier_connectivity()
    print(json.dumps(results, ensure_ascii=False, indent=2))
