"""分析レイヤーの E2E テスト（LLM はスタブ）。

`ANALYSIS_LAYER_ENABLED=true` で run_from_normalized() を実行し、
{event_id}_script.json と {event_id}_analysis.json が両方生成され、
script.json の sections が hook/setup/twist/punchline 4 ブロックを含み、
metadata に selected_perspective が含まれていることを確認する。

実 LLM 呼び出しは行わず、analysis_engine と script_writer の
LLM クライアントをスタブする。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.llm.base import LLMClient
from src.main import run_from_normalized
from src.shared.models import (
    AnalysisResult,
    Insight,
    MultiAngleAnalysis,
    PerspectiveCandidate,
)


# ---------- Fixtures / helpers ----------

@pytest.fixture()
def tmp_dirs(tmp_path: Path):
    output = tmp_path / "output"
    db = tmp_path / "db" / "test.db"
    return output, db


@pytest.fixture()
def no_external_llm(monkeypatch):
    """E2E テストで実 LLM を使わないようにする。"""
    monkeypatch.setattr("src.main.GEMINI_API_KEY", "")
    monkeypatch.setattr("src.main.JUDGE_ENABLED", False)
    monkeypatch.setattr("src.main.ELITE_JUDGE_ENABLED", False)
    monkeypatch.setattr("src.main.MISSION_LLM_ENABLED", False)
    monkeypatch.setattr("src.main.GARBAGE_FILTER_ENABLED", False)
    monkeypatch.setattr("src.main.get_cluster_llm_client", lambda: None)
    monkeypatch.setattr("src.main.get_garbage_filter_client", lambda: None)
    monkeypatch.setattr("src.main.get_judge_llm_client", lambda: None)
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
    category: str = "geopolitics",
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
    norm_dir = tmp_path / "normalized"
    norm_dir.mkdir(exist_ok=True)
    norm_file = norm_dir / "batch_e2e.json"
    sample = [
        _make_article(
            "a1",
            "ホルムズ海峡封鎖の懸念で原油市場が動揺",
            url="http://nhk.jp/articles/a1",
            tags=["地政学", "原油"],
            summary="イランの威嚇でホルムズ海峡周辺の航路に影響が出ている。",
        ),
        _make_article(
            "a2",
            "Iran threatens Strait of Hormuz closure amid sanctions",
            url="http://reuters.com/articles/a2",
            country="Global",
            source_name="Reuters",
            tags=["geopolitics", "oil"],
            summary="Iran signaled possible closure as new sanctions loom; tankers re-routing observed.",
        ),
    ]
    norm_file.write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")

    from src.storage.db import init_db, save_batch
    init_db(db_path)
    save_batch(
        db_path=db_path,
        batch_id="20260425_e2e",
        raw_files=[],
        normalized_files=[str(norm_file)],
    )
    return norm_dir


def _fake_analysis_result(event_id: str) -> AnalysisResult:
    """E2E テスト用の固定 AnalysisResult。"""
    return AnalysisResult(
        event_id=event_id,
        channel_id="geo_lens",
        selected_perspective=PerspectiveCandidate(
            axis="hidden_stakes",
            score=8.5,
            reasoning="日本の原油輸入の 80% 超がホルムズ経由という構造的依存。",
            evidence_refs=["art_1", "art_2"],
        ),
        rejected_perspectives=[],
        perspective_verified=True,
        verification_notes="test verification",
        multi_angle=MultiAngleAnalysis(
            geopolitical="米中対立の延長線上にイランの威嚇カードがある。",
            political_intent="イランは制裁緩和を引き出すため威嚇を周期的に使う。",
            economic_impact="日本の石油元売りは備蓄取り崩し圧力に直面する。",
            cultural_context="湾岸の駆け引きは儒教圏の合意形成と論理が異なる。",
            media_divergence="日本では航行影響、海外では地政学リスクが主軸で報じられる。",
        ),
        insights=[
            Insight(
                text="日本の原油輸入の 80% がホルムズ経由という構造的依存。",
                importance=0.9,
                evidence_refs=["art_1"],
            ),
            Insight(
                text="2019 年の威嚇でも実際の封鎖は起きなかった構造的拘束がある。",
                importance=0.85,
                evidence_refs=["art_2"],
            ),
            Insight(
                text="日本の石油元売り各社はすでに備蓄取り崩しの準備に入った。",
                importance=0.7,
                evidence_refs=["art_1"],
            ),
        ],
        selected_duration_profile="geopolitics_120s",
        visual_mood_tags=["causal_chain", "domino_effect", "interconnected_systems"],
        analysis_version="v1.0",
        generated_at=datetime.now(timezone.utc).isoformat(),
        llm_calls_used=3,
    )


def _fake_script_response() -> str:
    """script_with_analysis プロンプトに対して返す固定 JSON 応答。"""
    return json.dumps(
        {
            "director_thought": (
                "hidden_stakes 軸の insights を Twist 中核に置き、Geopolitics で構造を解説。"
                "数字と固有名詞で日本への因果連鎖を可視化する。"
            ),
            "selected_pattern": "Geopolitics",
            "loop_mechanism": "loop-1",
            "seo_keywords": {
                "primary": "ホルムズ海峡",
                "secondary": ["原油価格", "地政学リスク"],
            },
            "thumbnail_text": {"main": "原油の生命線", "sub": "日本80%依存"},
            "hook_variants": [
                {"type": "A", "label": "数字ショック", "text": "8割。日本の原油は今ここで止まる"},
                {"type": "D", "label": "逆説宣言", "text": "ホルムズ封鎖は中国も困る"},
                {"type": "E", "label": "名指し暴露", "text": "イランが本当に狙うのは制裁解除です"},
            ],
            "setup": (
                "イランがホルムズ海峡の封鎖をちらつかせ始めました。"
                "現時点で実際の封鎖は確認されていません。"
                "ただ国際的なタンカーは航路の見直しを始めています。"
            ),
            "twist": (
                "ここで重要なのは日本の原油輸入の8割がこの海峡経由という事実です。"
                "イランは2019年にも同様の威嚇を行いましたが、実際の封鎖はしませんでした。"
                "なぜなら中国も逆方向から原油を輸入しており、封鎖した瞬間に中国の圧力で潰される。"
                "つまり封鎖カードは交渉用の脅しで、実行コストは極めて高い構造です。"
                "日本の石油元売り各社はすでに備蓄取り崩しの準備に入っています。"
            ),
            "punchline": (
                "つまり今動いているのは戦争ではなく、制裁解除を引き出すための高度な経済交渉です。"
                "次に「ホルムズ封鎖」という単語を聞いたら、その裏の構造を思い出してください。"
            ),
            "peaks": {
                "3s": "実は日本の原油の8割",
                "7s": "ホルムズ海峡 8割",
                "15s": "2019年も実行されなかった",
                "30s": "中国も困る構造",
            },
        },
        ensure_ascii=False,
    )


class _StubLLMClient(LLMClient):
    """LLM 呼び出しを記録し、固定応答を返すスタブ。"""

    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


# ---------- E2E ----------

def test_e2e_analysis_layer_geo_lens_writes_both_jsons(
    tmp_dirs, tmp_path, no_external_llm, monkeypatch
):
    """ANALYSIS_LAYER_ENABLED=true の E2E 完走と成果物検証。

    1. {event_id}_analysis.json と {event_id}_script.json が両方生成される
    2. script.json の sections が hook/setup/twist/punchline の 4 ブロック
    3. video_payload.json の metadata に selected_perspective が含まれる
       （分析レイヤー由来のメタ転送）
    """
    monkeypatch.setenv("ANALYSIS_LAYER_ENABLED", "true")
    monkeypatch.setenv("DEFAULT_CHANNEL_ID", "geo_lens")
    # F-16-A: legacy TOP_N_GENERATION は TOP_N_ARTICLES_PER_RUN にリネーム済み。
    # ユーザー .env に TOP_N_ARTICLES_PER_RUN=3 が固定されているため、新変数を
    # 明示的に上書きして Slot-1 のみ処理させる (E2E は単一イベントのフロー検証が目的)。
    # TOP_N_GENERATION も後方互換のため残す (一部下流テストが参照)。
    monkeypatch.setenv("TOP_N_GENERATION", "1")
    monkeypatch.setenv("TOP_N_ARTICLES_PER_RUN", "1")
    monkeypatch.setenv("TOP_N_VIDEOS_PER_RUN", "1")

    # 分析レイヤー: 固定 AnalysisResult を返す
    captured: dict = {"event_id": None}

    def _fake_run(scored_event, channel_config, db_path, **kwargs):
        captured["event_id"] = scored_event.event.id
        return _fake_analysis_result(scored_event.event.id)

    monkeypatch.setattr(
        "src.analysis.analysis_engine.run_analysis_layer", _fake_run
    )
    monkeypatch.setattr(
        "src.analysis.recency_guard.apply_recency_guard",
        lambda candidates, ch, db, **kw: list(candidates),
    )
    monkeypatch.setattr(
        "src.analysis.recency_guard.record_publication",
        lambda event, ch, db, **kw: None,
    )

    # 台本生成: スタブ LLM で固定応答
    stub = _StubLLMClient(_fake_script_response())
    monkeypatch.setattr(
        "src.generation.script_writer.get_script_llm_client", lambda: stub
    )

    output, db = tmp_dirs
    norm_dir = _setup_normalized_batch(tmp_path, db)
    record = run_from_normalized(norm_dir, output, db)

    assert record.status == "completed", f"unexpected status: {record}"
    eid = captured["event_id"]
    assert eid is not None

    # ── (1) 両 JSON が存在 ───────────────────────────────────────────────
    analysis_path = output / f"{eid}_analysis.json"
    script_path = output / f"{eid}_script.json"
    assert analysis_path.exists(), (
        f"missing analysis json. dir contents: {sorted(p.name for p in output.iterdir())}"
    )
    assert script_path.exists(), (
        f"missing script json. dir contents: {sorted(p.name for p in output.iterdir())}"
    )

    # ── (2) script の sections 構造 ─────────────────────────────────────
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    headings = [s["heading"] for s in script_data["sections"]]
    assert headings == ["hook", "setup", "twist", "punchline"]
    # 新ルートの selected_pattern が情報密度型 4 種に入っていること
    assert script_data["selected_pattern"] in (
        "Breaking Shock", "Geopolitics", "Paradigm Shift", "Cultural Divide",
    )
    # 仕様: target_enemy は新ルートでは付与されない
    assert script_data.get("target_enemy") is None

    # ── (3) video_payload の metadata に分析メタ転送 ─────────────────────
    payload_path = output / f"{eid}_video_payload.json"
    assert payload_path.exists()
    payload_data = json.loads(payload_path.read_text(encoding="utf-8"))
    meta = payload_data["metadata"]
    assert meta.get("selected_perspective") == "hidden_stakes"
    assert meta.get("selected_duration_profile") == "geopolitics_120s"
    assert meta.get("visual_mood_tags") == [
        "causal_chain", "domino_effect", "interconnected_systems"
    ]
    assert meta.get("analysis_layer_enabled") is True

    # ── (4) analysis.json も最低限の整合 ─────────────────────────────────
    analysis_data = json.loads(analysis_path.read_text(encoding="utf-8"))
    assert analysis_data["event_id"] == eid
    assert analysis_data["channel_id"] == "geo_lens"
    assert analysis_data["selected_perspective"]["axis"] == "hidden_stakes"

    # ── (5) スタブ LLM が呼ばれていること（=新ルート経由を確認） ─────────
    assert len(stub.prompts) == 1
    # 新ルートのプロンプトには insights ブロックや perspective_axis が含まれる
    assert "perspective_axis" in stub.prompts[0] or "hidden_stakes" in stub.prompts[0]


def test_e2e_legacy_smoke_unaffected_when_flag_false(
    tmp_dirs, tmp_path, no_external_llm, monkeypatch
):
    """ANALYSIS_LAYER_ENABLED=false（デフォルト）で従来通り完走し、
    {event_id}_analysis.json は生成されないこと。"""
    monkeypatch.delenv("ANALYSIS_LAYER_ENABLED", raising=False)

    output, db = tmp_dirs
    norm_dir = _setup_normalized_batch(tmp_path, db)
    record = run_from_normalized(norm_dir, output, db)

    assert record.status == "completed"
    # _analysis.json は出力されない
    assert not any(p.name.endswith("_analysis.json") for p in output.iterdir())
    # script.json は legacy ルートで生成される
    assert any(p.name.endswith("_script.json") for p in output.iterdir())
