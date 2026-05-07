"""F-particular-angle-design: 「特定角度」LLM ベース抽出スクリプト。

入力 events.json から各 event の `particular_angle` (3 要素: core_question /
differentiation_from_mainstream / hydrangea_axis_alignment) を Gemini で抽出し、
系統判定 estimate (stream_1_silence_gap / stream_2_framing_inversion /
out_of_scope) と一緒に annotations.json に保存する。

判定基準は docs/PARTICULAR_ANGLE_DEFINITION.md セクション 2-3 に従う。

Usage:
    python scripts/extract_particular_angle.py \\
        --input docs/runs/F-particular-angle-design/input_events.json \\
        --output docs/runs/F-particular-angle-design/annotations.json \\
        --llm-model gemini-2.5-flash

出力:
    docs/runs/F-particular-angle-design/annotations.json (機械読み詳細)
    + 標準出力で進捗 + 異常検知結果

実装方針:
- LLM クライアントは src/llm/factory.py:get_analysis_llm_client() 経由
  (analysis role / Tier 階層 / 予算管理 / temperature=0.3 を継承)
- LLM 失敗時は最大 3 回リトライ、それでも失敗した event は
  extraction_error フィールドに記録して継続
- 5 件ごとに進捗ログを出力
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# プロジェクトルートを sys.path に追加 (scripts/ から src/ をインポートするため)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.llm.factory import (  # noqa: E402
    TieredGeminiClient,
    _get_max_attempts_for_role,
    _get_tier_models_for_role,
)
from src.shared.config import GEMINI_API_KEY  # noqa: E402
from src.shared.logger import get_logger  # noqa: E402

logger = get_logger("extract_particular_angle")

# 抽出プロンプト本体。docs/PARTICULAR_ANGLE_DEFINITION.md セクション 2-3 と
# 整合する判定基準を LLM に渡す。プロンプトは外部 .md 化せず本スクリプト内に
# 直書きする (本バッチは docs + scripts のみ、configs/prompts/ 配下は触らない
# 方針のため)。
_PROMPT_TEMPLATE = """\
あなたは Hydrangea (海外ニュース解説メディア) の編集判断を支援する LLM です。
入力された海外ニュース 1 件について「特定角度」を抽出し、Hydrangea の
コアミッション (2 系統並立) におけるどの系統で扱うべきかを判定してください。

# 「特定角度」とは
海外メディアが当該事象に対して **独自に掘った視点・問題意識・分析切り口** のこと。
事象そのもの (= 広範事件) ではなく、海外メディアが強調している『誰が何をどう
問題視しているか』『既存の主流フレームで扱われていない構造分析』『日本の主流
メディアでは見落とされている解釈』の 1 ピース。

# Hydrangea 4 軸 (構造的バイアス、系統 1 / 系統 2 共通の動画化価値判定軸)
1. **制度・システム面**: 報道規制 / 記者クラブ / クロスオーナーシップ / 自由度の低さ /
   スポンサー忖度
2. **外交・経済・利害関係面**: 特定国忖度 (米国・中国・韓国・イスラエル・サウジ・
   ロシア・北朝鮮等) / 大企業忖度
3. **個人・権力者面**: 政治家・官僚・財界要人・司法・メディアオーナー一族・芸能
   スポーツ界の権力者忖度 (Hydrangea ミッションど真ん中)
4. **関心領域・地政学的死角**: 中東・グローバルサウス・アフリカ・南米等への関心の低さ

# 系統判定の論理フロー (上から順に評価)
- **Step 1**: 特定角度が 4 軸のいずれかに該当するか?
  - No → out_of_scope
  - Yes ↓
- **Step 2**: 特定角度が日本主要メディアで報道済みか?
  - No → stream_1_silence_gap
  - Yes ↓
- **Step 3**: 解釈・フレーミング・優先順位が日本/西側 vs 海外/東側で異なるか?
  - No → out_of_scope (単に同じ内容が報道済み)
  - Yes → stream_2_framing_inversion

# 入力
event_id: {event_id}
title: {title}
summary: {summary}
sources: {sources}

# 出力 (必ず以下の JSON 形式で、それ以外の文字を一切含めない)
```json
{{
  "particular_angle": {{
    "core_question": "誰が何をどう問題視しているか、1-2 文",
    "differentiation_from_mainstream": "既存報道との差、1-2 文 (日本主要紙 / 欧米メインストリームが何を強調し、本記事が何を強調しているかの差分)",
    "hydrangea_axis_alignment": "4 軸のどれに該当するか + 理由 (最も核心的な 1 軸を選ぶ。複数該当の場合は最核心を優先)",
    "extraction_confidence": "high / medium / low (LLM が抽出に自信を持てなかった場合は medium / low)"
  }},
  "stream_classification_estimate": {{
    "estimated_stream": "stream_1_silence_gap / stream_2_framing_inversion / out_of_scope のいずれか",
    "reasoning": "判定根拠 (特定角度の日本未報道度合い + 解釈差の有無、2-3 文)",
    "confidence": "high / medium / low"
  }}
}}
```

# 注意事項
- 必ず JSON 形式のみで応答してください。Markdown コードブロック (```json) は付けても
  付けなくても構いません。スクリプト側で除去します。
- ★ 重要: 各文字列値 (core_question / differentiation_from_mainstream /
  hydrangea_axis_alignment / reasoning) は **1 行に収め、生の改行を含めない**
  でください。複数文を入れる場合はスペースで連結してください。
- 「特定角度」は広範事件 (= 事象そのもの) ではなく、その事象内で海外メディアが
  独自に掘った視点を指します。広範事件レベルの説明にならないよう注意してください。
- extraction_confidence と confidence は厳密に判定してください。記事内の情報が
  限定的な場合 / 4 軸該当性の判断が困難な場合は medium / low を返してください。
"""


def build_prompt(event: dict) -> str:
    """1 件の event から LLM プロンプトを組み立てる。"""
    sources = event.get("sources", [])
    if isinstance(sources, list):
        sources_str = ", ".join(s if isinstance(s, str) else str(s) for s in sources)
    else:
        sources_str = str(sources)
    return _PROMPT_TEMPLATE.format(
        event_id=event.get("event_id", "(unknown)"),
        title=event.get("title", "(no title)"),
        summary=event.get("summary", "(no summary)"),
        sources=sources_str or "(no sources)",
    )


def _escape_unescaped_newlines_in_strings(s: str) -> str:
    """JSON 文字列値の中に生の改行が混じっている場合に \\n / \\r / \\t に
    エスケープする最小修復。LLM が複数行に分けて文字列値を出力した場合の救済。
    """
    out: list[str] = []
    in_string = False
    escape = False
    for ch in s:
        if escape:
            out.append(ch)
            escape = False
            continue
        if ch == "\\":
            out.append(ch)
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            out.append(ch)
            continue
        if in_string and ch == "\n":
            out.append("\\n")
            continue
        if in_string and ch == "\r":
            out.append("\\r")
            continue
        if in_string and ch == "\t":
            out.append("\\t")
            continue
        out.append(ch)
    return "".join(out)


def parse_llm_response(text: str) -> dict:
    """LLM の応答テキストから JSON 部分を抽出してパースする。

    Markdown コードブロック (```json ... ```) で囲まれている場合と、
    生 JSON のみの場合の両方に対応する。LLM が文字列値の中に生の改行を
    混入させた場合は最小修復を試みる。
    """
    # Markdown コードブロック除去
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()
    else:
        candidate = text.strip()

    # 先頭/末尾の余計な文字を除去
    if not candidate.startswith("{"):
        first_brace = candidate.find("{")
        if first_brace >= 0:
            candidate = candidate[first_brace:]
    if not candidate.endswith("}"):
        last_brace = candidate.rfind("}")
        if last_brace >= 0:
            candidate = candidate[: last_brace + 1]

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        # 文字列値中の生改行をエスケープして再試行
        fixed = _escape_unescaped_newlines_in_strings(candidate)
        return json.loads(fixed)


def extract_one(client, event: dict, max_retries: int = 3) -> dict:
    """1 件分の特定角度を LLM で抽出する。最大 max_retries 回リトライ。"""
    prompt = build_prompt(event)
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            response_text = client.generate(prompt)
            parsed = parse_llm_response(response_text)
            # 期待されるキーの存在を確認 (KeyError 早期検知)
            _ = parsed["particular_angle"]["core_question"]
            _ = parsed["particular_angle"]["extraction_confidence"]
            _ = parsed["stream_classification_estimate"]["estimated_stream"]
            return parsed
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            last_error = exc
            logger.warning(
                f"[{event.get('event_id', 'unknown')}] attempt {attempt}/{max_retries} "
                f"failed (parse): {str(exc)[:120]}"
            )
        except Exception as exc:
            last_error = exc
            logger.warning(
                f"[{event.get('event_id', 'unknown')}] attempt {attempt}/{max_retries} "
                f"failed (api): {str(exc)[:120]}"
            )
            if attempt < max_retries:
                time.sleep(2 * attempt)

    raise RuntimeError(
        f"All {max_retries} attempts failed for event_id={event.get('event_id')}: "
        f"{last_error}"
    )


def _build_extract_client():
    """本スクリプト専用の Gemini Tier クライアントを生成する。

    analysis role の Tier 階層を流用しつつ、max_output_tokens を 4096 に拡張。
    既定の analysis client (max=2000) は本プロンプトで JSON が途中切断される
    事例が観測されたため (F-particular-angle-design 試行 1 で覚知)。
    """
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set — cannot run extraction. "
            "GEMINI_API_KEY を .env または shell 環境変数に設定してください。"
        )
    return TieredGeminiClient(
        GEMINI_API_KEY,
        _get_tier_models_for_role("analysis"),
        generation_config={"temperature": 0.3, "max_output_tokens": 4096},
        max_attempts_per_tier=_get_max_attempts_for_role("analysis"),
    )


def annotate_all(events: list[dict], llm_model_label: str) -> list[dict]:
    """全 event を LLM で順次抽出する。失敗 event は extraction_error 付きで継続。"""
    client = _build_extract_client()

    annotations: list[dict] = []
    n = len(events)
    success = 0
    error = 0

    for i, event in enumerate(events, start=1):
        event_id = event.get("event_id", f"unknown_{i}")
        record = {
            "event_id": event_id,
            "title": event.get("title"),
            "summary_excerpt": (event.get("summary") or "")[:200],
            "source_origin": event.get("source_origin"),
            "particular_angle": None,
            "stream_classification_estimate": None,
            "extraction_error": None,
            "kazuya_review": {
                "particular_angle_revised": None,
                "stream_classification_revised": None,
                "review_note": None,
                "reviewed_at": None,
            },
        }
        try:
            extracted = extract_one(client, event)
            record["particular_angle"] = extracted.get("particular_angle")
            record["stream_classification_estimate"] = extracted.get(
                "stream_classification_estimate"
            )
            success += 1
        except Exception as exc:
            record["extraction_error"] = str(exc)[:500]
            error += 1
            logger.error(f"[{event_id}] extraction error: {str(exc)[:200]}")

        annotations.append(record)

        if i % 5 == 0 or i == n:
            logger.info(
                f"Progress: {i}/{n} (success={success}, error={error})"
            )

    return annotations


def summarize_annotations(annotations: list[dict]) -> dict:
    """抽出結果のサマリ (confidence 分布 / stream 推定分布 / エラー件数)。"""
    confidence_dist: dict[str, int] = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    stream_dist: dict[str, int] = {
        "stream_1_silence_gap": 0,
        "stream_2_framing_inversion": 0,
        "out_of_scope": 0,
        "unknown": 0,
    }
    error_count = 0
    for r in annotations:
        if r.get("extraction_error"):
            error_count += 1
            continue
        pa = r.get("particular_angle") or {}
        c = (pa.get("extraction_confidence") or "unknown").lower()
        if c not in confidence_dist:
            c = "unknown"
        confidence_dist[c] += 1
        sce = r.get("stream_classification_estimate") or {}
        s = (sce.get("estimated_stream") or "unknown").lower()
        if s not in stream_dist:
            s = "unknown"
        stream_dist[s] += 1
    return {
        "total": len(annotations),
        "extraction_confidence_distribution": confidence_dist,
        "stream_classification_estimate_distribution": stream_dist,
        "extraction_errors": error_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract particular_angle from input events using LLM (F-particular-angle-design)"
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="入力 events JSON のパス (例: docs/runs/F-particular-angle-design/input_events.json)",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="出力 annotations JSON のパス",
    )
    parser.add_argument(
        "--llm-model",
        default="gemini-analysis-tier",
        help="LLM モデルラベル (記録用、実モデルは factory.py の analysis Tier に従う)",
    )
    args = parser.parse_args()

    args.input = args.input.resolve()
    args.output = args.output.resolve()
    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        return 2

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    events = payload.get("events", [])
    if not events:
        logger.error(f"No events found in input: {args.input}")
        return 2

    logger.info(f"Loaded {len(events)} events from {args.input}")
    started_at = datetime.now(timezone.utc).isoformat()
    annotations = annotate_all(events, args.llm_model)
    completed_at = datetime.now(timezone.utc).isoformat()

    summary = summarize_annotations(annotations)
    output_payload = {
        "version": "1.0",
        "batch": "F-particular-angle-design",
        "extracted_at": completed_at,
        "started_at": started_at,
        "llm_model": args.llm_model,
        "input_file": str(args.input.relative_to(_PROJECT_ROOT)) if args.input.is_relative_to(_PROJECT_ROOT) else str(args.input),
        "input_total_events": len(events),
        "summary": summary,
        "events": annotations,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Wrote {len(annotations)} annotations to {args.output}")
    logger.info(f"Summary: {json.dumps(summary, ensure_ascii=False)}")

    # 異常検知 (記録のみ、勝手にプロンプト再調整はしない)
    low_conf = summary["extraction_confidence_distribution"].get("low", 0)
    if low_conf >= 5:
        logger.warning(
            f"⚠ extraction_confidence=low が {low_conf} 件 >= 5 件: "
            "プロンプト改善検討対象 (本バッチでは記録のみ)"
        )
    streams = summary["stream_classification_estimate_distribution"]
    nonzero_streams = [k for k, v in streams.items() if v > 0 and k != "unknown"]
    if len(nonzero_streams) <= 1 and len(events) >= 5:
        logger.warning(
            f"⚠ 系統推定が単一 ({nonzero_streams}) に集中: "
            "プロンプト判定ロジック要確認 (本バッチでは記録のみ)"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
