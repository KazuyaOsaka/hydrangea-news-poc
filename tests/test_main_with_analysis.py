"""src/main.py の分析レイヤー組込テスト。

ANALYSIS_LAYER_ENABLED=false で従来通り動作することと、=true で
{event_id}_analysis.json が出力 / record_publication が呼ばれることを確認する。

実 LLM 呼び出しは行わず、analysis_engine と recency_guard を monkeypatch する。
分析レイヤーは run_from_normalized() の Top-3 ループ前に組み込まれているため、
flag=true のシナリオでは normalized batch を DB に登録して run_from_normalized を呼ぶ。
flag=false のシナリオは run()（sample mode）の smoke で十分（小さい）。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.main import run, run_from_normalized
from src.shared.config import INPUT_DIR
from src.shared.models import (
    AnalysisResult,
    MultiAngleAnalysis,
    PerspectiveCandidate,
)


# ---------- shared fixtures / helpers ----------

@pytest.fixture()
def tmp_dirs(tmp_path: Path):
    output = tmp_path / "output"
    db = tmp_path / "db" / "test.db"
    return output, db


@pytest.fixture()
def no_llm_api(monkeypatch):
    """LLM 経路を全て無効化（test_event_builder.py と同じパターン）。"""
    monkeypatch.setattr("src.main.GEMINI_API_KEY", "")
    monkeypatch.setattr("src.main.JUDGE_ENABLED", False)
    monkeypatch.setattr("src.main.ELITE_JUDGE_ENABLED", False)
    monkeypatch.setattr("src.main.MISSION_LLM_ENABLED", False)
    monkeypatch.setattr("src.main.GARBAGE_FILTER_ENABLED", False)
    monkeypatch.setattr("src.main.get_cluster_llm_client", lambda: None)
    monkeypatch.setattr("src.main.get_garbage_filter_client", lambda: None)
    monkeypatch.setattr("src.main.get_judge_llm_client", lambda: None)
    monkeypatch.setattr("src.generation.script_writer.get_script_llm_client", lambda: None)
    try:
        monkeypatch.setattr(
            "src.generation.article_writer.get_article_llm_client", lambda: None
        )
    except AttributeError:
        pass


def _make_article(
    article_id: str,
    title: str,
    *,
    url: str = "",
    country: str = "JP",
    source_name: str = "NHK",
    category: str = "economy",
    published_at: str = "2026-04-25T10:00:00+00:00",
    summary: str = "",
    tags: list[str] | None = None,
) -> dict:
    return {
        "id": article_id,
        "title": title,
        "url": url or f"http://example.com/{article_id}",
        "tags": tags or [],
        "country": country,
        "source_name": source_name,
        "category": category,
        "published_at": published_at,
        "summary": summary,
        "fetched_at": "2026-04-25T11:00:00+00:00",
        "raw_ref": "",
    }


def _setup_normalized_batch(tmp_path: Path, db_path: Path) -> Path:
    """JP+EN クラスタを 1 件含む batch を作成して DB に登録する。"""
    norm_dir = tmp_path / "normalized"
    norm_dir.mkdir(exist_ok=True)
    norm_file = norm_dir / "nhk_normalized.json"
    sample = [
        _make_article(
            "a1",
            "日本銀行が追加利上げを決定した",
            url="http://nhk.jp/articles/a1",
            tags=["経済", "金融"],
            summary="日本銀行は追加の利上げを決定し、円高が進んだ。",
        ),
        _make_article(
            "a2",
            "Bank of Japan raises interest rates further",
            url="http://reuters.com/articles/a2",
            country="Global",
            source_name="Reuters",
            tags=["economy", "finance"],
            summary="The Bank of Japan decided to raise interest rates again, pushing yen higher.",
        ),
    ]
    norm_file.write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")

    from src.storage.db import init_db, save_batch
    init_db(db_path)
    save_batch(
        db_path=db_path,
        batch_id="20260425_120000",
        raw_files=[],
        normalized_files=[str(norm_file)],
    )
    return norm_dir


def _no_analysis_files(output_dir: Path) -> bool:
    if not output_dir.exists():
        return True
    return not any(p.name.endswith("_analysis.json") for p in output_dir.iterdir())


def _no_script_files(output_dir: Path) -> bool:
    if not output_dir.exists():
        return True
    return not any(p.name.endswith("_script.json") for p in output_dir.iterdir())


def _fake_analysis_result(event_id: str) -> AnalysisResult:
    return AnalysisResult(
        event_id=event_id,
        channel_id="geo_lens",
        selected_perspective=PerspectiveCandidate(
            axis="silence_gap",
            score=8.5,
            reasoning="Fake test perspective",
            evidence_refs=["https://example.com/evidence"],
        ),
        rejected_perspectives=[],
        perspective_verified=True,
        verification_notes="test",
        multi_angle=MultiAngleAnalysis(
            geopolitical="g", political_intent="p", economic_impact="e",
            cultural_context="c", media_divergence="m",
        ),
        insights=[],
        selected_duration_profile="anti_sontaku_90s",
        visual_mood_tags=["void_imagery"],
        analysis_version="v1.0",
        generated_at=datetime.now(timezone.utc).isoformat(),
        llm_calls_used=3,
    )


# ── ANALYSIS_LAYER_ENABLED=false: 既存挙動の維持（sample mode） ────────────

def test_legacy_path_when_flag_false_produces_no_analysis_json(tmp_dirs, monkeypatch):
    monkeypatch.setenv("ANALYSIS_LAYER_ENABLED", "false")
    output, db = tmp_dirs
    record = run(INPUT_DIR / "sample_events.json", output, db)

    assert record.status == "completed"
    assert _no_analysis_files(output)


def test_legacy_path_when_flag_unset_produces_no_analysis_json(tmp_dirs, monkeypatch):
    monkeypatch.delenv("ANALYSIS_LAYER_ENABLED", raising=False)
    output, db = tmp_dirs
    record = run(INPUT_DIR / "sample_events.json", output, db)

    assert record.status == "completed"
    assert _no_analysis_files(output)


def test_legacy_path_does_not_call_analysis_engine(
    tmp_dirs, tmp_path, no_llm_api, monkeypatch
):
    """flag=false の normalized 実行で run_analysis_layer / apply_recency_guard が
    1 回も呼ばれないことを確認する（gate そのものの検証）。"""
    monkeypatch.setenv("ANALYSIS_LAYER_ENABLED", "false")

    called: dict = {"run_analysis_layer": 0, "apply_recency_guard": 0}

    def _fail_run(*args, **kwargs):
        called["run_analysis_layer"] += 1
        raise AssertionError("run_analysis_layer must not be called when flag=false")

    def _fail_guard(*args, **kwargs):
        called["apply_recency_guard"] += 1
        raise AssertionError("apply_recency_guard must not be called when flag=false")

    monkeypatch.setattr(
        "src.analysis.analysis_engine.run_analysis_layer", _fail_run
    )
    monkeypatch.setattr(
        "src.analysis.recency_guard.apply_recency_guard", _fail_guard
    )

    output, db = tmp_dirs
    norm_dir = _setup_normalized_batch(tmp_path, db)
    record = run_from_normalized(norm_dir, output, db)

    assert record.status == "completed"
    assert called["run_analysis_layer"] == 0
    assert called["apply_recency_guard"] == 0
    assert _no_analysis_files(output)


# ── ANALYSIS_LAYER_ENABLED=true: 分析レイヤーが起動する ────────────────────

def test_flag_true_writes_analysis_json_and_records_publication(
    tmp_dirs, tmp_path, no_llm_api, monkeypatch
):
    """flag=true で run_analysis_layer の結果が _analysis.json として保存され、
    投稿成功で record_publication が呼ばれること。"""
    monkeypatch.setenv("ANALYSIS_LAYER_ENABLED", "true")
    monkeypatch.setenv("DEFAULT_CHANNEL_ID", "geo_lens")
    # Top-N=1 にしてループ回数を最小化する（テスト高速化）
    monkeypatch.setenv("TOP_N_GENERATION", "1")

    spy: dict = {
        "run_calls": 0,
        "guard_calls": 0,
        "record_calls": 0,
        "last_event_id": None,
    }

    def _fake_run(scored_event, channel_config, db_path, **kwargs):
        spy["run_calls"] += 1
        spy["last_event_id"] = scored_event.event.id
        assert channel_config.channel_id == "geo_lens"
        return _fake_analysis_result(scored_event.event.id)

    def _identity_guard(candidates, channel_id, db_path, **kwargs):
        spy["guard_calls"] += 1
        assert channel_id == "geo_lens"
        return list(candidates)

    def _spy_record(event, channel_id, db_path, **kwargs):
        spy["record_calls"] += 1
        return None

    monkeypatch.setattr(
        "src.analysis.analysis_engine.run_analysis_layer", _fake_run
    )
    monkeypatch.setattr(
        "src.analysis.recency_guard.apply_recency_guard", _identity_guard
    )
    monkeypatch.setattr(
        "src.analysis.recency_guard.record_publication", _spy_record
    )

    output, db = tmp_dirs
    norm_dir = _setup_normalized_batch(tmp_path, db)
    record = run_from_normalized(norm_dir, output, db)

    assert record.status == "completed"
    assert spy["run_calls"] == 1
    assert spy["guard_calls"] == 1
    assert spy["record_calls"] >= 1

    expected_path = output / f"{spy['last_event_id']}_analysis.json"
    assert expected_path.exists(), (
        f"expected {expected_path} but found {sorted(p.name for p in output.iterdir())}"
    )
    parsed = json.loads(expected_path.read_text(encoding="utf-8"))
    assert parsed["event_id"] == spy["last_event_id"]
    assert parsed["channel_id"] == "geo_lens"
    assert parsed["selected_perspective"]["axis"] == "silence_gap"


def test_flag_true_skips_when_run_returns_none(
    tmp_dirs, tmp_path, no_llm_api, monkeypatch
):
    """run_analysis_layer が None を返した場合は動画生成をスキップする。

    旧 legacy fallback（write_script への分岐）は扇動的台本（ホルムズ海峡問題）
    再発防止のため廃止された。観点不成立時は _analysis.json も _script.json も
    出さず、JobRecord status='skipped' で記録する。
    """
    monkeypatch.setenv("ANALYSIS_LAYER_ENABLED", "true")
    monkeypatch.setenv("DEFAULT_CHANNEL_ID", "geo_lens")
    monkeypatch.setenv("TOP_N_GENERATION", "1")

    monkeypatch.setattr(
        "src.analysis.analysis_engine.run_analysis_layer",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "src.analysis.recency_guard.apply_recency_guard",
        lambda candidates, ch, db, **kwargs: list(candidates),
    )
    monkeypatch.setattr(
        "src.analysis.recency_guard.record_publication",
        lambda event, ch, db, **kwargs: None,
    )

    output, db = tmp_dirs
    norm_dir = _setup_normalized_batch(tmp_path, db)
    record = run_from_normalized(norm_dir, output, db)

    # 観点不成立で動画生成スキップ → status=skipped, error=analysis_layer_returned_none
    assert record.status == "skipped"
    assert record.error == "analysis_layer_returned_none"
    # _analysis.json も _script.json も作られないこと
    assert _no_analysis_files(output)
    assert _no_script_files(output)


def test_flag_true_swallows_analysis_exception_and_skips(
    tmp_dirs, tmp_path, no_llm_api, monkeypatch
):
    """分析レイヤーが例外を投げても run_from_normalized 自体はクラッシュせず、
    動画生成はスキップする。

    旧 legacy fallback は廃止されたため、分析レイヤーが落ちた場合の挙動は
    「completed via legacy」ではなく「skipped(analysis_layer_returned_none)」。
    """
    monkeypatch.setenv("ANALYSIS_LAYER_ENABLED", "true")
    monkeypatch.setenv("DEFAULT_CHANNEL_ID", "geo_lens")
    monkeypatch.setenv("TOP_N_GENERATION", "1")

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated analysis crash")

    monkeypatch.setattr(
        "src.analysis.recency_guard.apply_recency_guard", _boom
    )

    output, db = tmp_dirs
    norm_dir = _setup_normalized_batch(tmp_path, db)
    record = run_from_normalized(norm_dir, output, db)
    assert record.status == "skipped"
    assert record.error == "analysis_layer_returned_none"
    assert _no_analysis_files(output)
    assert _no_script_files(output)


def test_flag_true_uses_default_channel_id_geo_lens_when_env_unset(
    tmp_dirs, tmp_path, no_llm_api, monkeypatch
):
    monkeypatch.setenv("ANALYSIS_LAYER_ENABLED", "true")
    monkeypatch.delenv("DEFAULT_CHANNEL_ID", raising=False)
    monkeypatch.setenv("TOP_N_GENERATION", "1")

    captured: dict = {"channel_id": None}

    def _capture(scored_event, channel_config, db_path, **kwargs):
        captured["channel_id"] = channel_config.channel_id
        return _fake_analysis_result(scored_event.event.id)

    monkeypatch.setattr(
        "src.analysis.analysis_engine.run_analysis_layer", _capture
    )
    monkeypatch.setattr(
        "src.analysis.recency_guard.apply_recency_guard",
        lambda candidates, ch, db, **kwargs: list(candidates),
    )
    monkeypatch.setattr(
        "src.analysis.recency_guard.record_publication",
        lambda event, ch, db, **kwargs: None,
    )

    output, db = tmp_dirs
    norm_dir = _setup_normalized_batch(tmp_path, db)
    record = run_from_normalized(norm_dir, output, db)
    assert record.status == "completed"
    assert captured["channel_id"] == "geo_lens"


def test_flag_true_records_publication_persists_to_db(
    tmp_dirs, tmp_path, no_llm_api, monkeypatch
):
    """flag=true で投稿成功後に recency_records テーブルに 1 件以上 INSERT されること。

    record_publication をモックせず、実装の DB 書き込みパスまで検証する。
    """
    monkeypatch.setenv("ANALYSIS_LAYER_ENABLED", "true")
    monkeypatch.setenv("DEFAULT_CHANNEL_ID", "geo_lens")
    monkeypatch.setenv("TOP_N_GENERATION", "1")

    monkeypatch.setattr(
        "src.analysis.analysis_engine.run_analysis_layer",
        lambda se, cc, db, **kw: _fake_analysis_result(se.event.id),
    )
    monkeypatch.setattr(
        "src.analysis.recency_guard.apply_recency_guard",
        lambda candidates, ch, db, **kwargs: list(candidates),
    )

    output, db = tmp_dirs
    norm_dir = _setup_normalized_batch(tmp_path, db)
    record = run_from_normalized(norm_dir, output, db)

    assert record.status == "completed"
    # DB に recency_records が 1 件以上保存されていること
    import sqlite3
    conn = sqlite3.connect(str(db))
    rows = conn.execute(
        "SELECT channel_id, event_id FROM recency_records WHERE channel_id = ?",
        ("geo_lens",),
    ).fetchall()
    conn.close()
    assert len(rows) >= 1
    assert rows[0][0] == "geo_lens"
