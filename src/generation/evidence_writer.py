"""evidence_writer.py — <id>_evidence.json を生成するモジュール。

各出力単位（evt-xxx / cls-xxx）について、
「何が選ばれ、なぜ選ばれ、何を根拠に書いたか」を一ファイルで追跡できるようにする。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.shared.logger import get_logger
from src.shared.models import NewsEvent, ScoredEvent, VideoScript, WebArticle

logger = get_logger(__name__)


# ---------- 内部ヘルパ ----------

def _event_type(event_id: str) -> str:
    """ID プレフィックスからイベント種別を判定する。"""
    if event_id.startswith("cls-"):
        return "cluster"
    if event_id.startswith("evt-"):
        return "sample"
    return "unknown"


def _cluster_info(event: NewsEvent) -> dict:
    """evt-... / cls-... の対応関係と記事数を返す。"""
    etype = _event_type(event.id)
    if etype == "cluster":
        return {
            "event_id": event.id,
            "cluster_id": event.id,          # cluster_to_event() では event.id == cluster_id
            "article_count": len(event.source_urls),
            "note": "クラスタリングにより生成（normalized モード）",
        }
    return {
        "event_id": event.id,
        "cluster_id": None,
        "article_count": None,
        "note": "サンプルイベント（手動作成）",
    }


def _sources_section(event: NewsEvent) -> dict:
    """sources_jp / sources_en を証跡用の辞書に変換する。

    sources_jp/en が未設定（cluster モード等）の場合は source_urls から URL のみで補完する。
    """
    if event.sources_jp or event.sources_en:
        return {
            "jp": [s.model_dump() for s in event.sources_jp],
            "en": [s.model_dump() for s in event.sources_en],
        }

    # cluster モード: sources_jp/en 未設定 → source_urls から補完
    jp_urls = [u for u in event.source_urls if "nhk" in u or "nikkei" in u
               or "asahi" in u or "mainichi" in u or "yomiuri" in u
               or "hochi" in u or "jp.techcrunch" in u or "xtech" in u]
    en_urls = [u for u in event.source_urls if u not in jp_urls]

    return {
        "jp": [{"name": event.source_name_jp or "（不明）", "url": u, "title": None}
               for u in jp_urls] if jp_urls else
              [{"name": event.source_name_jp or "（不明）", "url": u, "title": None}
               for u in event.source_urls[:1]],
        "en": [{"name": event.source_name_global or "（不明）", "url": u, "title": None}
               for u in en_urls],
        "_fallback": True,
        "_note": "sources_jp/en 未設定のため source_urls から推定",
    }


def _assess_quality(event: NewsEvent) -> dict:
    """coverage_gap / perspective_conflict / japan_impact / context_depth を評価する。

    各項目:
      rating: "present" | "documented" | "partial" | "inferred" | "minimal" | "absent"
      evidence: 評価の根拠（どのフィールドを見たか）
      detail: 実際の内容（長い場合は先頭 200 字）
    """

    def _trim(s: Optional[str], n: int = 200) -> Optional[str]:
        if not s:
            return None
        return s[:n] + "…" if len(s) > n else s

    # 1. coverage_gap: japan_view と global_view の両方が存在し内容が異なるか
    jv = event.japan_view
    gv = event.global_view
    if jv and gv and jv.strip() != gv.strip():
        cg_rating = "present"
        cg_evidence = "japan_view と global_view の両方が存在し内容が異なる"
    elif jv or gv:
        cg_rating = "partial"
        cg_evidence = "japan_view または global_view の片方のみ存在"
    else:
        cg_rating = "absent"
        cg_evidence = "japan_view / global_view ともに未設定"

    # 2. perspective_conflict: gap_reasoning が文書化されているか
    if event.gap_reasoning:
        pc_rating = "documented"
        pc_evidence = "gap_reasoning フィールドに根拠が明示されている"
    elif jv and gv and jv.strip() != gv.strip():
        pc_rating = "inferred"
        pc_evidence = "japan_view と global_view の差から推定（gap_reasoning 未記述）"
    else:
        pc_rating = "absent"
        pc_evidence = "認識差の根拠なし"

    # 3. japan_impact: impact_on_japan と japan_impact_reasoning の有無
    if event.impact_on_japan and event.japan_impact_reasoning:
        ji_rating = "documented"
        ji_evidence = "impact_on_japan と japan_impact_reasoning の両方が存在"
    elif event.impact_on_japan:
        ji_rating = "present"
        ji_evidence = "impact_on_japan は存在するが japan_impact_reasoning が未記述"
    else:
        ji_rating = "absent"
        ji_evidence = "impact_on_japan 未設定"

    # 4. context_depth: background の有無と長さ
    bg = event.background
    if bg and len(bg) > 100:
        cd_rating = "present"
        cd_evidence = f"background フィールドが存在（{len(bg)}字）"
    elif bg:
        cd_rating = "minimal"
        cd_evidence = f"background フィールドが存在するが短い（{len(bg)}字）"
    else:
        cd_rating = "absent"
        cd_evidence = "background 未設定"

    # 5. background_inference_potential: 報道差から背景仮説を推論できる余地
    # 「記事に背景説明があるか」ではなく「差分から仮説が立てられるか」を評価
    has_both_views = bool(jv and gv and jv.strip() != gv.strip())
    bip_signals: list[str] = []
    bip_score = 0
    if has_both_views:
        bip_signals.append("両言語ビューあり")
        bip_score += 2
    if event.gap_reasoning:
        bip_signals.append("gap_reasoning 明示")
        bip_score += 3
    if event.sources_jp and event.sources_en:
        bip_signals.append("日英両ソースあり")
        bip_score += 1
    if event.background:
        bip_signals.append("background フィールドあり")
        bip_score += 1

    if bip_score >= 5:
        bip_rating = "high"
        bip_evidence = "背景仮説の根拠素材が揃っている: " + "、".join(bip_signals)
    elif bip_score >= 3:
        bip_rating = "moderate"
        bip_evidence = "一部の素材あり: " + "、".join(bip_signals) if bip_signals else "最小限の素材のみ"
    elif bip_score >= 1:
        bip_rating = "low"
        bip_evidence = "素材が限定的: " + "、".join(bip_signals) if bip_signals else "差分なし"
    else:
        bip_rating = "absent"
        bip_evidence = "報道差の素材なし（単一言語・単一視点）"

    return {
        "coverage_gap": {
            "rating": cg_rating,
            "evidence": cg_evidence,
            "detail": _trim(event.gap_reasoning) or _trim(jv),
        },
        "perspective_conflict": {
            "rating": pc_rating,
            "evidence": pc_evidence,
            "detail": _trim(event.gap_reasoning),
        },
        "japan_impact": {
            "rating": ji_rating,
            "evidence": ji_evidence,
            "detail": _trim(event.japan_impact_reasoning) or _trim(event.impact_on_japan),
        },
        "context_depth": {
            "rating": cd_rating,
            "evidence": cd_evidence,
            "detail": _trim(bg),
        },
        "background_inference_potential": {
            "rating": bip_rating,
            "evidence": bip_evidence,
            "score": bip_score,
        },
    }


def _generation_section(
    event: NewsEvent,
    script: VideoScript,
    article: WebArticle,
) -> dict:
    """script / article 生成時に参照したソース一覧と生成メタデータを返す。"""
    # 参照ソース: sources_jp + sources_en を結合
    all_sources = [s.model_dump() for s in event.sources_jp + event.sources_en]

    # fallback: sources_jp/en 未設定なら source_urls をそのまま並べる
    if not all_sources:
        all_sources = [{"name": "（不明）", "url": u, "title": None}
                       for u in event.source_urls]

    return {
        "script": {
            "referenced_sources": all_sources,
            "section_count": len(script.sections),
            "total_duration_sec": script.total_duration_sec,
            "sections": [
                {"name": s.heading, "duration_sec": s.duration_sec, "chars": len(s.body)}
                for s in script.sections
            ],
        },
        "article": {
            "referenced_sources": all_sources,
            "word_count": article.word_count,
        },
    }


# ---------- 公開インタフェース ----------

def _exclusion_factors(triage_result: ScoredEvent, sources: dict) -> list[str]:
    """ペナルティ・品質不足理由を人間可読なリストで返す。

    triage_result.score_breakdown のペナルティキーを走査し、
    除外/減点の根拠を日本語で説明する。
    """
    reasons: list[str] = []
    bd = triage_result.score_breakdown

    if "source_fallback_penalty" in bd:
        reasons.append(
            f"ソースfallback ({bd['source_fallback_penalty']:+.1f}): "
            "sources_jp/en が未設定。source_name・title ともに不明で引用根拠が弱い。"
        )
    if "japan_impact_absent_penalty" in bd:
        reasons.append(
            f"japan_impact欠落 ({bd['japan_impact_absent_penalty']:+.1f}): "
            "impact_on_japan が未設定。日本への意義を示す記述がない。"
        )
    if "context_depth_absent_penalty" in bd:
        reasons.append(
            f"context_depth欠落 ({bd['context_depth_absent_penalty']:+.1f}): "
            "background が未設定。報道の背景・文脈が記述されていない。"
        )
    if "perspective_weak_penalty" in bd:
        reasons.append(
            f"perspective_conflict=inferred ({bd['perspective_weak_penalty']:+.1f}): "
            "sources は存在するが gap_reasoning が未記述。JP/EN 認識差が推定止まり。"
        )

    # cross_lang_bonus が期待最大値 (5.0) 未満の場合に理由を補足
    cross = bd.get("cross_lang_bonus", 0.0)
    if cross < 5.0 and ("japan_view" in str(bd) or cross > 0):
        if cross == 0.0:
            reasons.append(
                "cross_lang_bonus=0: gap_reasoning・構造化ソースともに未設定のため "
                "クロスランゲージボーナスなし（fallback推定ペアの可能性）。"
            )
        elif cross < 5.0:
            reasons.append(
                f"cross_lang_bonus={cross} (最大5.0未満): "
                "gap_reasoning または構造化ソースのいずれかが未設定。"
            )

    return reasons


def write_evidence(
    event: NewsEvent,
    triage_result: ScoredEvent,
    script: VideoScript,
    article: WebArticle,
    output_dir: Path,
) -> Path:
    """<id>_evidence.json を output_dir に保存し、パスを返す。"""
    sources = _sources_section(event)
    exclusion = _exclusion_factors(triage_result, sources)

    evidence = {
        "schema_version": "1",
        "id": event.id,
        "title": event.title,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_type": _event_type(event.id),
        "cluster_info": _cluster_info(event),
        "sources": sources,
        "triage": {
            "score": triage_result.score,
            "breakdown": triage_result.score_breakdown,
            "selected_reason": (
                f"score={triage_result.score}（全イベント中の最高スコア）で選択。"
                f"category={event.category}、tags={event.tags}"
            ),
            "exclusion_factors": exclusion,
        },
        "quality_assessment": _assess_quality(event),
        "generation": _generation_section(event, script, article),
    }

    path = output_dir / f"{event.id}_evidence.json"
    path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Evidence saved: {path}")
    return path
