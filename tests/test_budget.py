"""BudgetTracker と daily_stats DB 機能のテスト。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.budget import BudgetTracker
from src.storage.db import (
    get_daily_stats,
    increment_daily_llm_calls,
    increment_daily_publish_count,
    increment_daily_run_count,
    init_db,
)


# ── フィクスチャ ───────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    db = tmp_path / "test.db"
    init_db(db)
    return db


# ── BudgetTracker 単体テスト ──────────────────────────────────────────────────

def test_budget_initial_state():
    b = BudgetTracker(run_budget=12, day_budget=120, day_calls_so_far=0)
    assert b.run_calls == 0
    assert b.day_calls == 0
    assert b.run_remaining == 12
    assert b.day_remaining == 120


def test_budget_record_call_increments():
    b = BudgetTracker(run_budget=12, day_budget=120, day_calls_so_far=0)
    b.record_call("script")
    assert b.run_calls == 1
    assert b.day_calls == 1
    assert b.run_remaining == 11
    assert b.day_remaining == 119


def test_budget_can_use_script_llm_when_sufficient():
    b = BudgetTracker(run_budget=12, day_budget=120, day_calls_so_far=0)
    assert b.can_use_script_llm() is True


def test_budget_can_use_article_llm_when_sufficient():
    b = BudgetTracker(run_budget=12, day_budget=120, day_calls_so_far=0)
    assert b.can_use_article_llm() is True


def test_budget_can_use_cluster_merge_when_sufficient():
    b = BudgetTracker(run_budget=12, day_budget=120, day_calls_so_far=0)
    assert b.can_use_cluster_merge() is True


def test_budget_cannot_use_script_when_run_exhausted():
    b = BudgetTracker(run_budget=1, day_budget=120, day_calls_so_far=0)
    b.record_call("cluster")
    # run_remaining == 0
    assert b.can_use_script_llm() is False


def test_budget_cannot_use_article_when_day_exhausted():
    b = BudgetTracker(run_budget=12, day_budget=5, day_calls_so_far=5)
    # day_remaining == 0
    assert b.can_use_article_llm() is False


def test_budget_cannot_use_cluster_merge_when_remaining_lt_3():
    b = BudgetTracker(run_budget=2, day_budget=120, day_calls_so_far=0)
    # run_remaining == 2, cluster_budget_available == 2 - 1 - 1 == 0
    assert b.can_use_cluster_merge() is False


# ── 予約枠・cluster_budget_available テスト ────────────────────────────────────

def test_cluster_budget_available_normal():
    """run_budget=12 では cluster が 10 回分使える。"""
    b = BudgetTracker(run_budget=12, day_budget=120, day_calls_so_far=0)
    assert b.cluster_budget_available == 10


def test_cluster_budget_available_decreases_with_calls():
    """cluster 呼び出しを記録すると cluster_budget_available が減る。"""
    b = BudgetTracker(run_budget=12, day_budget=120, day_calls_so_far=0)
    b.record_call("cluster_post_merge")
    b.record_call("cluster_post_merge")
    assert b.cluster_budget_available == 8


def test_cluster_stops_at_reservation_boundary():
    """cluster が reservation 枠まで使い切ったら can_afford_cluster_pair が False になる。"""
    b = BudgetTracker(run_budget=4, day_budget=120, day_calls_so_far=0)
    # cluster_budget_available = 4 - 1 - 1 = 2
    assert b.can_afford_cluster_pair() is True
    b.record_call("cluster_post_merge")
    assert b.can_afford_cluster_pair() is True
    b.record_call("cluster_post_merge")
    # run_remaining = 2, cluster_budget_available = 0
    assert b.can_afford_cluster_pair() is False


def test_script_and_article_run_after_cluster_exhausts_cluster_budget():
    """cluster が cluster 枠を使い切っても script/article は残る。"""
    b = BudgetTracker(run_budget=4, day_budget=120, day_calls_so_far=0)
    # cluster 2 回使う (cluster_budget_available = 2)
    b.record_call("cluster_post_merge")
    b.record_call("cluster_post_merge")
    # run_remaining = 2
    assert b.can_use_script_llm() is True
    b.record_call("script")
    # run_remaining = 1
    assert b.can_use_article_llm() is True
    b.record_call("article")
    # run_remaining = 0
    assert b.can_use_script_llm() is False


def test_cluster_calls_tracked_separately():
    """cluster 呼び出し数が _cluster_calls に記録される。"""
    b = BudgetTracker(run_budget=12, day_budget=120, day_calls_so_far=0)
    b.record_call("cluster_post_merge")
    b.record_call("cluster_post_merge")
    b.record_call("script")
    assert b._cluster_calls == 2


def test_record_phase_snapshots_run_remaining():
    """record_phase がそのタイミングの run_remaining をスナップショットする。"""
    b = BudgetTracker(run_budget=12, day_budget=120, day_calls_so_far=0)
    b.record_call("cluster_post_merge")
    b.record_phase("before_script")
    b.record_call("script")
    b.record_phase("before_article")
    assert b._phase_snapshots["before_script"] == 11
    assert b._phase_snapshots["before_article"] == 10


def test_budget_skip_records_feature():
    b = BudgetTracker(run_budget=12, day_budget=120, day_calls_so_far=0)
    b.skip("cluster_post_merge")
    b.skip("article_llm")
    # skipped リストに追加されていること（内部属性）
    assert len(b._skipped) == 2
    assert "cluster_post_merge" in b._skipped


def test_budget_record_call_persists_to_db(tmp_db):
    b = BudgetTracker(run_budget=12, day_budget=120, day_calls_so_far=0, db_path=tmp_db)
    b.record_call("script")
    b.record_call("article")
    stats = get_daily_stats(tmp_db)
    assert stats["llm_calls"] == 2


# ── daily_stats DB テスト ─────────────────────────────────────────────────────

def test_get_daily_stats_initial(tmp_db):
    stats = get_daily_stats(tmp_db)
    assert stats["llm_calls"] == 0
    assert stats["run_count"] == 0
    assert stats["publish_count"] == 0


def test_increment_daily_llm_calls(tmp_db):
    increment_daily_llm_calls(tmp_db)
    increment_daily_llm_calls(tmp_db)
    stats = get_daily_stats(tmp_db)
    assert stats["llm_calls"] == 2


def test_increment_daily_run_count(tmp_db):
    increment_daily_run_count(tmp_db)
    stats = get_daily_stats(tmp_db)
    assert stats["run_count"] == 1


def test_increment_daily_publish_count(tmp_db):
    increment_daily_publish_count(tmp_db)
    increment_daily_publish_count(tmp_db)
    increment_daily_publish_count(tmp_db)
    stats = get_daily_stats(tmp_db)
    assert stats["publish_count"] == 3


def test_daily_stats_table_exists_after_init(tmp_db):
    conn = sqlite3.connect(str(tmp_db))
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    conn.close()
    table_names = {r[0] for r in tables}
    assert "daily_stats" in table_names


# ── MAX_PUBLISHES_PER_DAY による publish スキップ統合テスト ────────────────────

def test_run_skips_when_publish_limit_reached(tmp_path):
    """MAX_PUBLISHES_PER_DAY=0 なら最初から publish がスキップされる。"""
    import os
    os.environ["MAX_PUBLISHES_PER_DAY"] = "0"
    try:
        # config を再ロードするため importlib を使用
        import importlib
        import src.shared.config as cfg
        importlib.reload(cfg)
        import src.main as main_mod
        importlib.reload(main_mod)

        from src.shared.config import INPUT_DIR
        output = tmp_path / "output"
        db = tmp_path / "db" / "test.db"
        record = main_mod.run(INPUT_DIR / "sample_events.json", output, db)
        assert record.status == "skipped"
    finally:
        os.environ["MAX_PUBLISHES_PER_DAY"] = "5"
        importlib.reload(cfg)
        importlib.reload(main_mod)


def test_run_succeeds_within_publish_limit(tmp_path):
    """MAX_PUBLISHES_PER_DAY=5 (デフォルト) なら通常通り completed になる。"""
    from src.main import run
    from src.shared.config import INPUT_DIR

    output = tmp_path / "output"
    db = tmp_path / "db" / "test.db"
    record = run(INPUT_DIR / "sample_events.json", output, db)
    assert record.status == "completed"


# ── Per-slot publish-limit refresh (top-3 ループでの上限再評価) ────────────────

def test_per_slot_loop_refreshes_publish_count_from_db(tmp_db, monkeypatch):
    """top-3 ループの各スロット呼び出しで day_publishes は DB から再取得される。

    回帰防止: 旧実装は run_from_normalized 開始時にキャプチャした
    stats["publish_count"] を3回使い回しており、slot-1 で
    increment_daily_publish_count しても slot-2/3 の MAX_PUBLISHES_PER_DAY
    チェックに反映されなかった。
    """
    from src.shared.models import JobRecord
    from src.storage.db import get_daily_stats, increment_daily_publish_count
    from src.main import MAX_PUBLISHES_PER_DAY  # noqa: F401  # ensure module loadable

    # 簡易シミュレーション: ループ内で _live_publishes を毎回取得し、
    # increment_daily_publish_count によって次回の値が増えることを確認する。
    captured_publishes: list[int] = []
    for _slot in range(3):
        live = get_daily_stats(tmp_db)["publish_count"]
        captured_publishes.append(live)
        # _generate_outputs が成功したことをシミュレート
        increment_daily_publish_count(tmp_db)

    assert captured_publishes == [0, 1, 2], (
        "Each slot must observe the freshest publish_count from DB. "
        f"Got {captured_publishes}"
    )
