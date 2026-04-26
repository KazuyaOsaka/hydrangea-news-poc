"""factory.py — Role-based LLM client factory with purpose-driven routing.

Routing strategy:
  Lightweight (high-throughput): garbage_filter, event_builder (cluster)
    → TIER4 (gemini-2.5-flash-lite) fixed; same-model retry only (no upward fallback).
    Rationale: already the cheapest tier — escalating would waste the premium quota.

  Quality (high-reasoning): elite_judge, script_writer, article_writer
    → TIER1 → TIER2 → TIER3 → TIER4 full 4-tier fallback.
    Rationale: accuracy matters; escalate only after per-tier retries are exhausted.

Fallback priority (quality path) — RPM 上限の高い順に降格:
  [1] gemini-3.1-flash-lite-preview  (TIER1, RPM=15)
  [2] gemini-2.5-flash-lite          (TIER2, RPM=10)
  [3] gemini-3-flash-preview         (TIER3, RPM=5)
  [4] gemini-2.5-flash               (TIER4, RPM=5)

Per-tier call interval: GEMINI_CALL_INTERVAL_SEC_TIER{1..4} で各モデルの
RPM を尊重した待機を強制する (TieredGeminiClient._throttle 参照)。

Per-tier policy: up to _MAX_ATTEMPTS_PER_TIER retries with exponential backoff
(1s→2s→4s) on 429/RESOURCE_EXHAUSTED or 503/UNAVAILABLE, then next tier.
If all tiers are exhausted, RuntimeError is raised — no silent degradation.

Resolution path: .env → config.py → factory.py
No hardcoded model strings in business logic.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from src.llm.base import LLMClient
from src.llm.retry import is_retryable
from src.shared.config import (
    GEMINI_API_KEY,
    GEMINI_CALL_INTERVAL_SEC,
    GEMINI_INTERVAL_SEC_BY_MODEL,
    GEMINI_MODEL_TIER1,
    GEMINI_MODEL_TIER2,
    GEMINI_MODEL_TIER3,
    GEMINI_MODEL_TIER4,
    GEMINI_MODEL_TIERS,
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


class TieredGeminiClient(LLMClient):
    """GeminiClient that walks through a provided tier list on quota exhaustion.

    Per-tier policy: up to _MAX_ATTEMPTS_PER_TIER retries with exponential
    backoff on 429/RESOURCE_EXHAUSTED or 503/UNAVAILABLE errors.
    After all attempts for a tier fail, the next tier is tried.
    If all tiers are exhausted, RuntimeError is raised.

    Single-element tier list → same-model retry only (no fallback).
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
                    if attempt < _MAX_ATTEMPTS_PER_TIER - 1:
                        logger.warning(
                            f"[TieredGemini] tier={tier_idx} model={model} "
                            f"attempt={attempt + 1}/{_MAX_ATTEMPTS_PER_TIER} quota error — "
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

def _make_lightweight_client() -> Optional[LLMClient]:
    """大量処理用クライアント: TIER4 (gemini-2.5-flash-lite) 固定。

    Garbage Filter / Event Builder 等の高スループット工程専用。
    フォールバックなし — TIER4 で最大 _MAX_ATTEMPTS_PER_TIER 回リトライ後に失敗。
    既に最廉価 Tier のため上位へのエスカレーションは不要。
    """
    if not GEMINI_API_KEY:
        return None
    return TieredGeminiClient(GEMINI_API_KEY, [GEMINI_MODEL_TIER4])


def _make_quality_client() -> Optional[LLMClient]:
    """高品質推論用クライアント: TIER1→TIER2→TIER3→TIER4 完全4段フォールバック。

    Elite Judge / Script Writer / Article Writer 等の高精度工程専用。
    TIER1 から順に試行し、429/503 が規定回数を超えた段階で次の Tier へ降格。
    """
    if not GEMINI_API_KEY:
        return None
    return TieredGeminiClient(
        GEMINI_API_KEY,
        [GEMINI_MODEL_TIER1, GEMINI_MODEL_TIER2, GEMINI_MODEL_TIER3, GEMINI_MODEL_TIER4],
    )


def _make_client(provider: str, model: str, quality: bool = False) -> Optional[LLMClient]:
    """Construct an LLMClient for the given provider + model pair.

    For Gemini, `model` is ignored — routing is determined by `quality`:
      quality=True  → _make_quality_client()  (TIER1→TIER4 full fallback)
      quality=False → _make_lightweight_client() (TIER4 retry-only)
    """
    if provider == "gemini":
        return _make_quality_client() if quality else _make_lightweight_client()

    if provider == "groq":
        from src.llm.groq import GroqClient
        return GroqClient(GROQ_API_KEY, model)

    if provider == "ollama":
        from src.llm.ollama import OllamaClient
        return OllamaClient(OLLAMA_BASE_URL, model)

    return None


def get_llm_client(role: str) -> Optional[LLMClient]:
    """Get an LLM client by role name.

    Args:
        role: One of "merge_batch", "judge", or "generation".

    Returns:
        Configured LLMClient, or None if the provider is not configured.

    Raises:
        ValueError: If role is not recognised.
    """
    if role == "merge_batch":
        # Event Builder / cluster: lightweight (TIER4 retry-only)
        return _make_client(MERGE_BATCH_PROVIDER, MERGE_BATCH_MODEL, quality=False)

    if role == "judge":
        return get_judge_llm_client()

    if role == "generation":
        # Script / Article Writer: quality (TIER1→TIER4 full fallback)
        return _make_client(GENERATION_PROVIDER, GENERATION_MODEL, quality=True)

    raise ValueError(
        f"Unknown LLM role: {role!r}. Must be 'merge_batch', 'judge', or 'generation'."
    )


# ── Named client accessors (called by business logic) ───────────────────────

def get_garbage_filter_client() -> Optional[LLMClient]:
    """Gate 1 Garbage Filter 用クライアント — 大量処理ルート。

    TIER4 (gemini-2.5-flash-lite) 固定、同一モデルでリトライのみ。
    フォールバック不要（既に最廉価 Tier）。
    """
    return _make_lightweight_client()


def get_cluster_llm_client() -> Optional[LLMClient]:
    """Event Builder / cluster post-merge 用クライアント — 大量処理ルート。

    TIER4 (gemini-2.5-flash-lite) 固定、同一モデルでリトライのみ。
    """
    return get_llm_client("merge_batch")


def get_judge_llm_client() -> Optional[LLMClient]:
    """Elite Judge / Gemini Judge 用クライアント — 高品質推論ルート。

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
    """Script Writer 用クライアント — 高品質推論ルート (role=generation)。

    GENERATION_PROVIDER=gemini の場合: TIER1→TIER4 完全4段フォールバック。
    GENERATION_PROVIDER=groq/ollama の場合: 該当プロバイダの単一クライアント。
    未知プロバイダ / APIキー未設定の場合: None。
    """
    return get_llm_client("generation")


def get_article_llm_client() -> Optional[LLMClient]:
    """Article Writer 用クライアント — 高品質推論ルート (role=generation)。"""
    return get_llm_client("generation")


def get_analysis_llm_client() -> Optional[LLMClient]:
    """分析レイヤー（Step 3〜5）用クライアント — 高品質推論ルート + 事実重視設定。

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
        return _make_client(GENERATION_PROVIDER, GENERATION_MODEL, quality=True)

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
