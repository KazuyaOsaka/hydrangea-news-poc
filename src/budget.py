"""LLM 呼び出しの予算管理モジュール。

1回の実行あたりと1日あたりの LLM 呼び出し数を追跡・制御する。

優先度順（低い方からスキップ）:
  1. cluster_post_merge  — 最初にスキップ (script/article の予約枠を残す)
  2. article_llm         — script 予約枠のみ残す
  3. script_llm          — できるだけ残す

予約ルール:
  RESERVED_FOR_SCRIPT  = 1  (必須: script は原則 LLM を使う)
  RESERVED_FOR_ARTICLE = 1  (任意: article は余裕があれば LLM を使う)
  cluster が使える最大呼び出し数 = run_budget - RESERVED_FOR_SCRIPT - RESERVED_FOR_ARTICLE

Publish-mode budget partition:
  publish_mode (default):
    day_budget を exploration / publish_reserve に分割する。
    day_remaining が publish_reserve_calls 以下になると探索的 LLM 呼び出し
    (cluster, viral_filter, judge) を停止し、production ステージ用の予算を保護する。
  research_mode:
    publish reserve チェックを無効化し、全 LLM 呼び出しを許可する（実験用）。
"""
from __future__ import annotations

from pathlib import Path

from src.shared.logger import get_logger

logger = get_logger(__name__)

# Exploration-phase LLM call feature names (exact match; elite_judge is mandatory — not exploration)
_EXPLORATION_FEATURES: frozenset[str] = frozenset({"cluster_post_merge_batch", "viral_filter", "judge"})


class BudgetTracker:
    """1回実行 + 1日あたりの LLM 呼び出し予算を管理する。"""

    # script / article のために cluster が食わないよう予約する呼び出し数
    RESERVED_FOR_SCRIPT: int = 1
    RESERVED_FOR_ARTICLE: int = 1

    # publish_mode のデフォルト publish_reserve_calls
    DEFAULT_PUBLISH_RESERVE_CALLS: int = 15  # 3本分の台本生成+リトライ余裕

    def __init__(
        self,
        run_budget: int,
        day_budget: int,
        day_calls_so_far: int,
        db_path: Path | None = None,
        mode: str = "publish_mode",
        publish_reserve_calls: int = DEFAULT_PUBLISH_RESERVE_CALLS,
    ) -> None:
        self.run_budget = run_budget
        self.day_budget = day_budget
        self._run_calls: int = 0
        self._day_calls: int = day_calls_so_far
        self._db_path = db_path
        self._skipped: list[str] = []
        self._cluster_calls: int = 0
        self._phase_snapshots: dict[str, int] = {}
        # Per-role retry counts (accumulated across all calls in this run)
        self._retry_counts: dict[str, int] = {}
        # Generation outcome log: role → {used_fallback, fallback_reason, retry_count}
        self._generation_log: dict[str, dict] = {}
        # ── Publish-mode budget partition ─────────────────────────────────────
        self._mode: str = mode
        self._publish_reserve_calls: int = publish_reserve_calls
        # Exploration calls in this run (cluster + viral + judge)
        self._exploration_calls: int = 0
        # Set to True if exploration was halted due to publish reserve protection
        self._stopped_exploration_due_to_publish_reserve: bool = False

    # ── 残量プロパティ ─────────────────────────────────────────────────────────

    @property
    def run_calls(self) -> int:
        return self._run_calls

    @property
    def day_calls(self) -> int:
        return self._day_calls

    @property
    def run_remaining(self) -> int:
        return max(0, self.run_budget - self._run_calls)

    @property
    def day_remaining(self) -> int:
        return max(0, self.day_budget - self._day_calls)

    @property
    def cluster_budget_available(self) -> int:
        """cluster が使える残り枠 (script/article の予約を差し引いた値)。"""
        return max(0, self.run_remaining - self.RESERVED_FOR_SCRIPT - self.RESERVED_FOR_ARTICLE)

    # ── Publish-mode プロパティ ───────────────────────────────────────────────

    @property
    def mode(self) -> str:
        """実行モード: "publish_mode" | "research_mode"。"""
        return self._mode

    @property
    def publish_reserve_calls(self) -> int:
        """publish_mode で production ステージ用に確保する最小 day_budget 呼び出し数。"""
        return self._publish_reserve_calls

    @property
    def exploration_budget_used(self) -> int:
        """このランで探索フェーズ (cluster/viral/judge) に使った LLM 呼び出し数。"""
        return self._exploration_calls

    @property
    def publish_reserve_preserved(self) -> bool:
        """publish_reserve_calls 分の day_budget が現在も保護されているか。"""
        return self.day_remaining >= self._publish_reserve_calls

    @property
    def stopped_exploration_due_to_publish_reserve(self) -> bool:
        """publish reserve 保護のために探索を打ち切ったか。"""
        return self._stopped_exploration_due_to_publish_reserve

    @property
    def slot1_budget_guaranteed(self) -> bool:
        """slot-1 生成に必要な最小 day_budget (4 呼び出し) が残っているか。

        最小 production = viral(1) + judge(1) + script(1) + article(1) = 4 呼び出し。
        """
        return self.day_remaining >= 4 and self.run_remaining >= 1

    # ── 使用可否判定 ──────────────────────────────────────────────────────────

    def can_afford(self, cost: int = 1) -> bool:
        """run と day の両方で cost 回分の残量があるか。"""
        return self.run_remaining >= cost and self.day_remaining >= cost

    def can_afford_exploration(self) -> bool:
        """探索的 LLM 呼び出し (cluster/viral/judge) を1回行えるか。

        publish_mode: day_remaining > publish_reserve_calls の場合のみ True。
          （strict greater-than により reserve は侵食されない）
        research_mode: day_remaining >= 1 であれば True（reserve チェックなし）。
        """
        if self._mode == "research_mode":
            return self.day_remaining >= 1
        return self.day_remaining > self._publish_reserve_calls

    def can_afford_elite_judge(self) -> bool:
        """Elite Judge (Gate 3) を実行できるか。

        Elite Judge は必須の門番であるため publish_reserve チェックをバイパスする。
        基本的な run/day 残量のみ確認する。
        """
        return self.run_remaining >= 1 and self.day_remaining >= 1

    def can_afford_judge(self) -> bool:
        """Judge LLM を実行できるか。

        publish_mode では publish reserve が保護されている場合のみ True。
        run-level reservation (script+article) も同時に確認する。
        """
        if not self.can_afford_exploration():
            if self._mode == "publish_mode":
                self._stopped_exploration_due_to_publish_reserve = True
                logger.info(
                    f"[Budget] Publish reserve reached — stopping judge "
                    f"(day_remaining={self.day_remaining}, "
                    f"publish_reserve={self._publish_reserve_calls})"
                )
            return False
        return self.cluster_budget_available >= 1

    def can_afford_viral_filter(self) -> bool:
        """Viral filter LLM (Step 2) を実行できるか。

        publish_mode では publish reserve が保護されている場合のみ True。
        """
        if not self.can_afford_exploration():
            if self._mode == "publish_mode":
                self._stopped_exploration_due_to_publish_reserve = True
                logger.info(
                    f"[Budget] Publish reserve reached — stopping viral filter LLM "
                    f"(day_remaining={self.day_remaining}, "
                    f"publish_reserve={self._publish_reserve_calls})"
                )
            return False
        return self.cluster_budget_available >= 1

    def can_afford_generation(self) -> bool:
        """script 生成のために少なくとも1回の LLM 呼び出しが残っているか。

        publish reserve ガードを意図的にバイパスする。
        publish reserve が用意されているのはまさにこの呼び出しのためであるため。
        """
        return self.run_remaining >= 1 and self.day_remaining >= 1

    def can_afford_cluster_pair(self) -> bool:
        """cluster post-merge の1ペア分の予算があるか。

        publish_mode では publish reserve が保護されている場合のみ True。
        """
        if not self.can_afford_exploration():
            if self._mode == "publish_mode":
                self._stopped_exploration_due_to_publish_reserve = True
                logger.info(
                    f"[Budget] Publish reserve reached — stopping cluster merge "
                    f"(day_remaining={self.day_remaining}, "
                    f"publish_reserve={self._publish_reserve_calls})"
                )
            return False
        return self.cluster_budget_available >= 1

    def can_use_cluster_merge(self) -> bool:
        """cluster post-merge LLM を許可するか (ループ開始前の事前チェック)。"""
        return self.can_afford_cluster_pair()

    def can_use_article_llm(self) -> bool:
        """article 生成 LLM を許可するか。"""
        return self.can_afford(1)

    def can_use_script_llm(self) -> bool:
        """script 生成 LLM を許可するか。"""
        return self.can_afford(1)

    # ── Retry / generation observability ─────────────────────────────────────

    def record_retry(self, role: str, count: int) -> None:
        """Accumulate retry count for a role across all calls in this run."""
        self._retry_counts[role] = self._retry_counts.get(role, 0) + count

    def record_generation_outcome(
        self,
        role: str,
        used_fallback: bool,
        fallback_reason: str | None,
        retry_count: int = 0,
    ) -> None:
        """Record script/article generation outcome for run_summary observability."""
        self._generation_log[role] = {
            "used_fallback": used_fallback,
            "fallback_reason": fallback_reason,
            "retry_count": retry_count,
        }

    @property
    def retry_counts(self) -> dict:
        return dict(self._retry_counts)

    @property
    def generation_log(self) -> dict:
        return dict(self._generation_log)

    # ── フェーズスナップショット ──────────────────────────────────────────────

    def record_phase(self, phase: str) -> None:
        """フェーズ開始時点の run_remaining をスナップショットとして記録する。"""
        self._phase_snapshots[phase] = self.run_remaining

    # ── 記録 ─────────────────────────────────────────────────────────────────

    def record_call(self, feature: str) -> None:
        """LLM 呼び出し 1 回を記録し DB にも反映する。"""
        self._run_calls += 1
        self._day_calls += 1
        if "cluster" in feature:
            self._cluster_calls += 1
        # Track exploration calls (cluster/viral/judge); elite_judge is mandatory and excluded
        if feature in _EXPLORATION_FEATURES:
            self._exploration_calls += 1
        logger.debug(
            f"[Budget] LLM call ({feature}): "
            f"run={self._run_calls}/{self.run_budget}, "
            f"day={self._day_calls}/{self.day_budget}"
        )
        if self._db_path is not None:
            try:
                from src.storage.db import increment_daily_llm_calls
                increment_daily_llm_calls(self._db_path)
            except Exception as exc:
                logger.warning(f"[Budget] Failed to persist LLM call count: {exc}")

    def skip(self, feature: str) -> None:
        """予算超過でスキップした処理を記録する。"""
        self._skipped.append(feature)
        logger.info(f"[Budget] Skipped (budget exceeded): {feature}")

    # ── Publish-mode summary ──────────────────────────────────────────────────

    def to_publish_mode_summary(self) -> dict:
        """run_summary / candidate_report 用の publish-mode 状態スナップショットを返す。"""
        return {
            "run_mode": self._mode,
            "daily_budget_total": self.day_budget,
            "exploration_budget_used": self._exploration_calls,
            "publish_reserve_budget": self._publish_reserve_calls,
            "publish_reserve_preserved": self.publish_reserve_preserved,
            "stopped_exploration_due_to_publish_reserve": self._stopped_exploration_due_to_publish_reserve,
            "slot1_budget_guaranteed": self.slot1_budget_guaranteed,
        }

    # ── サマリー出力 ──────────────────────────────────────────────────────────

    def log_summary(self, day_runs: int, day_publishes: int) -> None:
        """実行終了時のサマリーをログに出力する。"""
        cluster_max = max(0, self.run_budget - self.RESERVED_FOR_SCRIPT - self.RESERVED_FOR_ARTICLE)
        remaining_before_script = self._phase_snapshots.get("before_script", "N/A")
        remaining_before_article = self._phase_snapshots.get("before_article", "N/A")

        logger.info(
            "[Budget] === Run Summary === | "
            f"mode={self._mode} | "
            f"run_llm={self._run_calls}/{self.run_budget} | "
            f"day_llm={self._day_calls}/{self.day_budget} | "
            f"day_runs={day_runs} | "
            f"day_publishes={day_publishes}"
        )
        logger.info(
            "[Budget] === Allocation === | "
            f"run_budget_total={self.run_budget} | "
            f"reserved_for_script={self.RESERVED_FOR_SCRIPT} | "
            f"reserved_for_article={self.RESERVED_FOR_ARTICLE} | "
            f"available_for_cluster={cluster_max} | "
            f"actually_used_by_cluster={self._cluster_calls} | "
            f"remaining_before_script={remaining_before_script} | "
            f"remaining_before_article={remaining_before_article}"
        )
        logger.info(
            "[Budget] === Publish Reserve === | "
            f"publish_reserve_calls={self._publish_reserve_calls} | "
            f"exploration_calls_used={self._exploration_calls} | "
            f"day_remaining={self.day_remaining} | "
            f"publish_reserve_preserved={self.publish_reserve_preserved} | "
            f"stopped_due_to_reserve={self._stopped_exploration_due_to_publish_reserve} | "
            f"slot1_budget_guaranteed={self.slot1_budget_guaranteed}"
        )
        if self._skipped:
            logger.info(f"[Budget] Skipped features: {', '.join(self._skipped)}")
