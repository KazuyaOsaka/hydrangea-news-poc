#!/usr/bin/env python
"""F-first-work-golden-master (1-S): 第一作 golden master 生成ハーネス。

候補A (cls-6889e9e1c7ac) の recent_event_pool.event_snapshot を入力に、
production と同じ部品 (run_analysis_layer → particular_angle_extractor →
write_article → generate_script_with_analysis → write_video_payload →
build_image_prompts) を製品コード無改修で単発実行し、golden master 素材一式を
data/output/golden_master/ に凍結保存する。

第一作隔離原則 (不変原則 6): production 経路 (main.py / プロンプトファイル) の
振る舞いを候補A 固有の事情で変えない。候補A 固有の操作は全て本ハーネス内の
プロセスローカルな注入 (monkeypatch) で行い、内容と根拠を
generation_metadata.json に記録する。

候補A 固有の注入 3 点 (CP-1 検証結果に基づく。完了レポート参照):

1. **観点候補の注入**: 候補A は sources_en=1 のため extract_perspectives の
   4 軸成立条件 + fallback 品質ゲート (sources_total >= 2) を構造的に通過できない
   (CP-1 実測 0 件)。engine の fallback ビルダー (_build_fallback_perspective、
   perspective_extractor.py L805-847) と同形の hidden_stakes 候補を品質ゲートのみ
   bypass して構築し、analysis_engine.extract_perspectives を差し替えて渡す。
   Step 2-6 (LLM 選定・検証 / 多角分析 / 洞察抽出 / 尺選定) は production
   オーケストレーション (run_analysis_layer) のまま実走する。

2. **editorial brief の注入 (script のみ)**: manual_poc/editorial_brief_candidate_a.md
   を script_with_analysis プロンプトの「## STEP 1」直前にプロセス内で挿入する
   (production プロンプトファイルは変更しない)。article は article_writer.py 内
   ハードコード (不変原則 1) のため注入せず素のまま生成し、brief 充足は人間編集 +
   Guardian 再実行ループで担保する。

3. **stream_classification の人間検証値への訂正**: 候補A = stream_2_perspective_gap
   は人間アノテーションで確定済み (2026-05-16 確定 / 2026-05-19 最終確定。
   「機械判定は事実の代替ではない」)。pool snapshot は JP 報道情報を含まないため
   (afpbb 報道済みの事実が入力に存在しない)、機械抽出が別系統を返した場合は
   人間検証値に訂正し、機械出力値を generation_metadata.json に記録する。

使い方:
    python manual_poc/generate_golden_master.py [--cls cls-6889e9e1c7ac]
        [--out data/output/golden_master]

GEMINI_API_KEY が必要 (analysis 3 calls + particular_angle 1 call +
article 1 call + script 1 call ≈ 計 6 LLM calls)。
新ルートが legacy にフォールバックした場合は exit 1 (凍結しない)。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.shared.config import DB_PATH
from src.shared.models import ChannelConfig, PerspectiveCandidate, ScoredEvent

DEFAULT_CLS = "cls-6889e9e1c7ac"
DEFAULT_OUT = "data/output/golden_master"
BRIEF_PATH = Path(__file__).resolve().parent / "editorial_brief_candidate_a.md"

# 人間検証済みの系統 (2026-05-16 確定、2026-05-19 F-trial-run-candidate-a-reverify で最終確定)
HUMAN_CONFIRMED_STREAM = "stream_2_perspective_gap"

# script プロンプトへの brief 挿入アンカー (production テンプレートの安定見出し)
_BRIEF_ANCHOR = "## STEP 1: パターン選択"

# article の template fallback 署名 (ab_article_model_upgrade.py 前例)
_ARTICLE_FALLBACK_SIGNATURE = "*この記事は Hydrangea News PoC によって自動生成されました。*"

# 候補A 固有のプレートモチーフ (英語の意味記述、ADR-0003 OK リスト準拠:
# 抽象シルエット / 場所の象徴 / 構造図。ICRC 標章・実在人物・文字は不使用)
CANDIDATE_A_MOTIF_HINTS = {
    "hook": [
        "dense grid of small anonymous human silhouettes behind vertical bars",
        "one silhouette highlighted in hydrangea blue",
    ],
    "setup": [
        "stacked official report documents as flat abstract shapes",
        "press-briefing podium silhouette with no person",
    ],
    "twist": [
        "abstract monitoring eye motif connected by arrows to a clipboard checklist and a prison gate",
        "a guided inspection route drawn as a dotted line that avoids dark areas of the diagram",
    ],
    "punchline": [
        "a single small lit window in a large dark wall",
        "barbed wire as a thin abstract line motif",
    ],
    "hook_card": [
        "prison gate silhouette with barbed wire under a single cold light",
        "dense grid of anonymous silhouettes fading into darkness",
    ],
}


# 確定布陣 (CURRENT_STATE: QUALITY=gemini-3.5-flash / ARTICLE=gemini-3.5-flash)。
# golden master は確定モデルで生成されることが凍結条件のため、全 Tier を pin して
# 503 波での下位モデルへの沈黙的劣化を構造的に排除する (劣化するくらいなら fail
# して再実行 = 1-T.2 の再実行ループと同じ運用。pin 手法は ab_article_model_upgrade.py
# `_pin_article_model` 前例)。
PINNED_QUALITY_MODEL = "gemini-3.5-flash"
PINNED_ARTICLE_MODEL = "gemini-3.5-flash"


def _pin_models() -> None:
    """QUALITY / ARTICLE role の全 Tier を確定モデルに固定する。"""
    import os

    for tier in ("TIER1", "TIER2", "TIER3", "TIER4"):
        os.environ[f"GEMINI_MODEL_{tier}"] = PINNED_QUALITY_MODEL
        os.environ[f"GEMINI_ARTICLE_{tier}"] = PINNED_ARTICLE_MODEL


def _load_scored_event(event_id: str) -> tuple[ScoredEvent, dict]:
    """recent_event_pool から event_snapshot を読む (ab_article_model_upgrade.py 前例)。"""
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


def _build_injected_perspective(scored: ScoredEvent) -> PerspectiveCandidate:
    """engine fallback と同形の hidden_stakes 候補 (品質ゲートのみ bypass)。

    同形再実装の写し元: src/analysis/perspective_extractor.py
    `_build_fallback_perspective` L805-847 (式・文言同形。ゲート
    `sources_total >= _FALLBACK_MIN_SOURCES_TOTAL (=2)` のみ適用しない)。
    ヘルパ _axis_score / _clamp / _topic_phrase / _collect_evidence_refs /
    _sources_en_count / _sources_jp_count も同形 (L34-90, L667-690)。
    """
    ev = scored.event

    # _sources_en_count / _sources_jp_count 同形 (L34-58)
    if ev.sources_by_locale:
        en = sum(len(refs) for region, refs in ev.sources_by_locale.items() if region != "japan")
    else:
        en = len(ev.sources_en)
    if ev.sources_by_locale and "japan" in ev.sources_by_locale:
        jp = len(ev.sources_by_locale["japan"])
    else:
        jp = len(ev.sources_jp)
    sources_total = en + jp

    # _axis_score 同形 (L60-66): unprefixed キーを参照 (無ければ 0.0)
    def _axis_score(key: str) -> float:
        val = (scored.score_breakdown or {}).get(key, 0.0)
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    ijai = _axis_score("indirect_japan_impact_score")
    ga = _axis_score("global_attention_score")
    raw = ijai * 0.5 + ga * 0.3
    score = max(0.0, min(5.0, raw))  # _clamp(raw, lo=0.0, hi=_FALLBACK_SCORE_MAX=5.0)

    # _topic_phrase 同形 (L667-690 冒頭部)
    topic = (ev.title or "").strip() or (
        (ev.summary or "").strip().splitlines()[0] if ev.summary else ""
    ) or ev.id

    metric_str = "、".join([f"間接インパクト {ijai:.1f}/10", f"海外関心度 {ga:.1f}/10"])
    why_now = (
        f"「{topic}」は 4 軸の典型成立条件には乗らないが、"
        f"({metric_str}; 海外 {en} 件 / 日本 {jp} 件) の構成で日本人視聴者にとっての"
        f"隠れた利害を世界視点から再解釈する余地がある。"
    )
    reasoning = (
        f"fallback 同形 (golden master ハーネス注入、品質ゲート bypass): "
        f"sources_total={sources_total}, ijai={ijai:.1f}, ga={ga:.1f} → score={score:.2f}"
    )

    # _collect_evidence_refs 同形 (L73-90)
    refs: list[str] = []
    seen: set[str] = set()
    if ev.sources_by_locale:
        for source_refs in ev.sources_by_locale.values():
            for s in source_refs:
                if s.url and s.url not in seen:
                    seen.add(s.url)
                    refs.append(s.url)
    else:
        for s in (*ev.sources_jp, *ev.sources_en):
            if s.url and s.url not in seen:
                seen.add(s.url)
                refs.append(s.url)

    return PerspectiveCandidate(
        axis="hidden_stakes",
        score=score,
        reasoning=reasoning,
        evidence_refs=refs,
        why_now=why_now,
    )


def _load_brief() -> str:
    """editorial brief を読み、.format() 安全化 (brace escape) して返す。"""
    text = BRIEF_PATH.read_text(encoding="utf-8")
    # 注入は「★ 本件固有の editorial brief」以降の本文のみ (ファイル冒頭の
    # 運用メモはプロンプトに不要)
    marker = "★ 本件固有の editorial brief"
    idx = text.find(marker)
    body = text[idx:] if idx >= 0 else text
    return body.replace("{", "{{").replace("}", "}}")


class _FallbackDetector(logging.Handler):
    """script_writer の legacy fallback ログを検出する。"""

    def __init__(self) -> None:
        super().__init__()
        self.fallback_detected = False
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        if "[ScriptWithAnalysis]" in msg:
            self.records.append(msg)
            if "Falling back to legacy route" in msg:
                self.fallback_detected = True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cls", default=DEFAULT_CLS)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()

    out_dir = _PROJECT_ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    _pin_models()
    print(
        f"[GM] models pinned: QUALITY={PINNED_QUALITY_MODEL} "
        f"ARTICLE={PINNED_ARTICLE_MODEL} (all tiers, no silent degradation)"
    )

    started_at = datetime.now(timezone.utc).isoformat()
    notes: list[str] = [
        f"all QUALITY/ARTICLE tiers pinned to {PINNED_QUALITY_MODEL} / "
        f"{PINNED_ARTICLE_MODEL}: a 503 wave degrades to FAIL (re-run), never to "
        "a lesser model (silent-degradation ban for the frozen golden master)"
    ]

    # ── 入力ロード ──────────────────────────────────────────────────────────
    scored, pool_meta = _load_scored_event(args.cls)
    event = scored.event
    scored.channel_id = "geo_lens"
    channel_config = ChannelConfig.load("geo_lens")
    print(f"[GM] event_id={args.cls}")
    print(f"[GM] title={event.title!r}")
    print(f"[GM] pool batch_id={pool_meta['batch_id']} created_at={pool_meta['created_at']}")

    # ── 注入 1: 観点候補 (fallback 同形、ゲート bypass) ─────────────────────
    injected = _build_injected_perspective(scored)
    print(f"[GM] injected perspective: axis={injected.axis} score={injected.score:.2f}")

    from src.analysis import analysis_engine

    _orig_extract = analysis_engine.extract_perspectives

    def _patched_extract(scored_event, channel_config=None):
        if scored_event.event.id == args.cls:
            return [injected]
        return _orig_extract(scored_event, channel_config)

    analysis_engine.extract_perspectives = _patched_extract
    notes.append(
        "perspective candidate injected (fallback-shaped hidden_stakes, quality "
        "gate bypassed): candidate A has sources_en=1 so extract_perspectives "
        "structurally returns 0 candidates (CP-1 measured)"
    )

    # ── 分析レイヤー実走 (production オーケストレーション) ──────────────────
    try:
        from src.analysis.analysis_engine import run_analysis_layer, save_analysis_json
        from src.analysis.particular_angle_extractor import extract_for_scored_event

        analysis = run_analysis_layer(scored, channel_config, DB_PATH)
    finally:
        analysis_engine.extract_perspectives = _orig_extract

    if analysis is None:
        raise SystemExit(
            "[GM] FATAL: run_analysis_layer returned None (LLM step failed). "
            "Golden master not frozen. Re-run after checking API status."
        )
    print(
        f"[GM] analysis ok: perspective={analysis.selected_perspective.axis} "
        f"verified={analysis.perspective_verified} insights={len(analysis.insights)} "
        f"profile={analysis.selected_duration_profile} llm_calls={analysis.llm_calls_used}"
    )

    # ── particular_angle_metadata 抽出 + 注入 3: 系統の人間検証値訂正 ────────
    pa_metadata = extract_for_scored_event(scored, channel_id="geo_lens")
    machine_stream = pa_metadata.stream_classification if pa_metadata else None
    stream_overridden = False
    if pa_metadata is None:
        raise SystemExit(
            "[GM] FATAL: particular_angle_extractor returned None. "
            "Golden master not frozen."
        )
    if pa_metadata.stream_classification != HUMAN_CONFIRMED_STREAM:
        pa_metadata = pa_metadata.model_copy(
            update={"stream_classification": HUMAN_CONFIRMED_STREAM}
        )
        stream_overridden = True
        notes.append(
            f"stream_classification overridden to human-confirmed value: "
            f"machine={machine_stream!r} → {HUMAN_CONFIRMED_STREAM!r} "
            f"(候補A は人間アノテーションで perspective_gap 確定 2026-05-16/19。"
            f"pool snapshot に JP 報道情報が無いため機械は誤分類しうる)"
        )
    print(
        f"[GM] particular_angle: machine_stream={machine_stream} "
        f"overridden={stream_overridden} sontaku="
        f"{pa_metadata.sontaku_signals.level if pa_metadata.sontaku_signals else '(none)'}"
    )

    analysis = analysis.model_copy(update={"particular_angle_metadata": pa_metadata})
    save_analysis_json(analysis, out_dir)

    # ── article 生成 (brief 注入なし = 素のまま、production API) ────────────
    from src.generation.article_writer import write_article

    article = write_article(event, triage_result=scored, budget=None)
    article_fallback = _ARTICLE_FALLBACK_SIGNATURE in article.markdown
    if article_fallback:
        raise SystemExit(
            "[GM] FATAL: article fell back to template (LLM failed). "
            "Golden master not frozen."
        )
    article_path = out_dir / f"{args.cls}_article.md"
    article_path.write_text(article.markdown, encoding="utf-8")
    print(f"[GM] article ok: {article.word_count} chars → {article_path.name}")

    # ── 注入 2: editorial brief (script プロンプトのみ、プロセス内) ──────────
    brief_block = _load_brief()
    from src.analysis import prompt_loader

    _orig_load_prompt = prompt_loader.load_prompt

    def _patched_load_prompt(channel_id: str, prompt_name: str, **kwargs):
        template = _orig_load_prompt(channel_id, prompt_name, **kwargs)
        if prompt_name == "script_with_analysis" and _BRIEF_ANCHOR in template:
            return template.replace(
                _BRIEF_ANCHOR, brief_block + "\n\n---\n\n" + _BRIEF_ANCHOR, 1
            )
        return template

    prompt_loader.load_prompt = _patched_load_prompt
    notes.append(
        "editorial brief injected into script_with_analysis prompt (process-local, "
        f"inserted before {_BRIEF_ANCHOR!r}; production prompt file unchanged; "
        "article NOT injected = invariant 1)"
    )

    # ── script 生成 (新ルート、fallback 検出付き) ───────────────────────────
    from src.generation import script_writer
    from src.generation.script_writer import generate_script_with_analysis

    detector = _FallbackDetector()
    script_writer.logger.addHandler(detector)
    try:
        script = generate_script_with_analysis(
            scored,
            analysis,
            channel_config,
            budget=None,
            article_text=article.markdown,
        )
    finally:
        script_writer.logger.removeHandler(detector)
        prompt_loader.load_prompt = _orig_load_prompt

    if detector.fallback_detected or script.target_enemy is not None:
        raise SystemExit(
            f"[GM] FATAL: script generation fell back to legacy route "
            f"(fallback_log={detector.fallback_detected}, "
            f"target_enemy={script.target_enemy!r}). Golden master not frozen."
        )
    script_path = out_dir / f"{args.cls}_script.json"
    script_path.write_text(script.model_dump_json(indent=2), encoding="utf-8")
    print(
        f"[GM] script ok (new route): pattern={script.selected_pattern} "
        f"target_enemy={script.target_enemy} sections="
        f"{[(s.heading, len(s.body)) for s in script.sections]}"
    )

    # ── video_payload 生成 ──────────────────────────────────────────────────
    from src.generation.video_payload_writer import write_video_payload

    payload = write_video_payload(event, script, analysis_result=analysis)
    payload_path = out_dir / f"{args.cls}_video_payload.json"
    payload_path.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
    print(f"[GM] video_payload ok: {len(payload.scenes)} scenes → {payload_path.name}")

    # ── image_prompt レイヤー (5 プレート) ──────────────────────────────────
    from src.generation.image_prompt_writer import build_image_prompts

    image_prompts = build_image_prompts(
        event, script, payload, motif_hints=CANDIDATE_A_MOTIF_HINTS
    )
    image_prompts_path = out_dir / "image_prompts.json"
    image_prompts_path.write_text(
        image_prompts.model_dump_json(indent=2), encoding="utf-8"
    )
    print(f"[GM] image_prompts ok: {len(image_prompts.plates)} plates → {image_prompts_path.name}")

    # ── generation metadata (凍結条件の監査証跡) ────────────────────────────
    import os

    brief_sha = hashlib.sha256(BRIEF_PATH.read_bytes()).hexdigest()[:16]
    metadata = {
        "batch": "F-first-work-golden-master",
        "generated_at_utc": started_at,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "event_id": args.cls,
        "event_title": event.title,
        "event_pool_batch_id": pool_meta["batch_id"],
        "event_pool_created_at": pool_meta["created_at"],
        "event_summary_chars": len(event.summary or ""),
        "models": {
            "quality_pinned_all_tiers": PINNED_QUALITY_MODEL,
            "article_pinned_all_tiers": PINNED_ARTICLE_MODEL,
            "pin_note": "成功出力は必ず pin モデル由来 (全 Tier 同一、下位モデル劣化なし)",
        },
        "harness_injections": notes,
        "injected_perspective": injected.model_dump(),
        "machine_stream_classification": machine_stream,
        "stream_overridden_to": HUMAN_CONFIRMED_STREAM if stream_overridden else None,
        "editorial_brief": {
            "path": "manual_poc/editorial_brief_candidate_a.md",
            "sha256_16": brief_sha,
            "injected_into": "script_with_analysis prompt only",
        },
        "script_route": "generate_script_with_analysis (new route, no legacy fallback)",
        "script_log_records": detector.records,
        "frozen_as_original": True,
        "editing_rule": (
            "this directory is the frozen ORIGINAL. Human edits go to separate "
            "*_edited.* files (docs/golden_master_spec.md). original vs edited "
            "diff = teaching signal for AI style improvement."
        ),
    }
    meta_path = out_dir / "generation_metadata.json"
    meta_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[GM] metadata → {meta_path}")
    print("[GM] done. Golden master frozen as original.")


if __name__ == "__main__":
    main()
