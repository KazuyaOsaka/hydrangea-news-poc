"""F-article-model-upgrade: article 生成モデル 2.5-flash vs 3.5-flash の A/B 再生成スクリプト。

B案 (カズヤ確定): 新規 ingestion / full pipeline は行わず、保存済み候補 event に対して
article を 2 モデルで再生成し、出力を並置する。評価 (axis_5 主観) はカズヤが行う。
本スクリプトは「両出力を並置・提示する」までが責務 — どちらが上かの判定は出さない。

不変原則 1 厳守: src/generation/article_writer.py は一切変更せず、公開 API
`write_article()` を呼び出すのみ。モデル切替は role="article" の Tier1 を os.environ で
明示制御する (factory._get_tier_models_for_role が call-time に os.getenv を引くため、
config reload 不要)。

入力 (両モデルで完全同一):
  - NewsEvent     : recent_event_pool.event_snapshot (ScoredEvent JSON) の .event
  - triage_result : 同 ScoredEvent
  - video_script  : data/output/<event_id>_script.json (VideoScript)

出力先: docs/runs/F-article-model-upgrade/
  - article_2.5flash.md / article_3.5flash.md
  - ab_eval_metadata.json (生成条件)

使い方:
    python scripts/ab_article_model_upgrade.py [event_id]
    event_id 省略時は候補A cls-6889e9e1c7ac。
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.shared.config import DB_PATH
from src.shared.models import ScoredEvent, VideoScript
from src.generation.article_writer import write_article

# 候補A (Phase A.5-3b 第一作 event)。X1 Slot-1 は cls-c8876d474612。
DEFAULT_EVENT_ID = "cls-6889e9e1c7ac"

OUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "runs" / "F-article-model-upgrade"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "output"

# A/B 対象モデル。順序 = ファイル名サフィックス。
MODELS = [
    ("gemini-2.5-flash", "article_2.5flash.md"),
    ("gemini-3.5-flash", "article_3.5flash.md"),
]

# template fallback (LLM 失敗時) の署名。検出用。
_FALLBACK_SIGNATURE = "*この記事は Hydrangea News PoC によって自動生成されました。*"


def _load_scored_event(event_id: str) -> tuple[ScoredEvent, dict]:
    """recent_event_pool から event_snapshot を読み (ScoredEvent, pool_meta) を返す。"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        row = conn.execute(
            "SELECT event_snapshot, batch_id, created_at FROM recent_event_pool WHERE event_id = ?",
            (event_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise SystemExit(f"event_id={event_id} not found in recent_event_pool")
    pool_meta = {"batch_id": row[1], "created_at": row[2]}
    return ScoredEvent.model_validate(json.loads(row[0])), pool_meta


def _load_video_script(event_id: str) -> VideoScript | None:
    """data/output/<event_id>_script.json があれば VideoScript に復元する。"""
    path = OUTPUT_DIR / f"{event_id}_script.json"
    if not path.exists():
        return None
    return VideoScript.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _pin_article_model(model: str) -> None:
    """role='article' の全 Tier を指定モデルに固定する。

    全 Tier を同一モデルにすることで、生成成功時の出力は必ず指定モデル由来、
    全失敗時のみ template fallback に落ちる (= API エラーとして検出可能) ことを保証する。
    A/B のモデル混入を防ぐ。
    """
    for tier in ("TIER1", "TIER2", "TIER3", "TIER4"):
        os.environ[f"GEMINI_ARTICLE_{tier}"] = model


def main() -> None:
    event_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EVENT_ID
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    scored, pool_meta = _load_scored_event(event_id)
    event = scored.event
    video_script = _load_video_script(event_id)

    print(f"[A/B] event_id={event_id}")
    print(f"[A/B] title={event.title!r}")
    print(f"[A/B] video_script={'loaded' if video_script else 'None'}")
    print(f"[A/B] sources_jp={len(event.sources_jp)} sources_en={len(event.sources_en)}")

    results = []
    for model, out_name in MODELS:
        _pin_article_model(model)
        print(f"\n[A/B] === generating with {model} → {out_name} ===")
        started = datetime.now(timezone.utc)
        # budget=None: 予算ゲートなし (純粋に LLM 経路を通す)
        article = write_article(event, triage_result=scored, video_script=video_script, budget=None)
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()

        used_fallback = _FALLBACK_SIGNATURE in article.markdown
        out_path = OUT_DIR / out_name
        out_path.write_text(article.markdown, encoding="utf-8")

        result = {
            "model_id": model,
            "output_file": out_name,
            "word_count": article.word_count,
            "char_len": len(article.markdown),
            "used_template_fallback": used_fallback,
            "elapsed_sec": round(elapsed, 1),
            "article_max_attempts_per_tier": 1,
            "generation_config": None,  # article 経路は max_output_tokens / temperature を設定しない
        }
        results.append(result)
        flag = "  ⚠️ TEMPLATE FALLBACK (LLM failed)" if used_fallback else "  ✅ LLM-generated"
        print(f"[A/B] {model}: {article.word_count} chars in {elapsed:.1f}s{flag}")

    metadata = {
        "batch": "F-article-model-upgrade",
        "scope": "B案 (config 変更 + 保存済み event での article A/B 再生成)",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "event_id": event_id,
        "event_title": event.title,
        "event_pool_batch_id": pool_meta["batch_id"],
        "event_pool_created_at": pool_meta["created_at"],
        "video_script_source": (
            f"data/output/{event_id}_script.json" if video_script else None
        ),
        "inputs_identical_across_models": True,
        "model_separation_note": (
            "role='article' の Tier を os.environ で固定。GEMINI_ARTICLE_TIER1〜4 を "
            "対象モデルに pin (生成成功時は必ず対象モデル由来、全失敗時のみ template fallback)。"
        ),
        "article_writer_unchanged": True,
        "evaluator": "カズヤ (axis_5 主観評価) — 本スクリプトは並置のみ、優劣判定はしない",
        "runs": results,
    }
    meta_path = OUT_DIR / "ab_eval_metadata.json"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[A/B] metadata → {meta_path}")
    print("[A/B] done.")


if __name__ == "__main__":
    main()
