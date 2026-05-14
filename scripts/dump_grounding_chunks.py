"""F-wl-hit-quality-audit Task D: Slot-2 用 Grounding chunk 生データダンプ。

F-trial-run-post-tune (2026-05-11) 試運転で観察された matched_urls がベアドメイン
のみ問題の構造的切り分けのため、F-13.B の `_search_with_grounding` 経路と同条件で
Gemini Grounding API を呼び、chunk.web 配列の生フィールド (uri / title / domain) を
JSON 保存する。

Slot-2 cls-1a38c0ca8c99 (Suspect FP 確定、診断価値最大) のみ対象。

不変原則順守:
- src/triage/jp_coverage_verifier.py は触らない (呼び出すだけ)
- 本番 DB (data/db/hydrangea.db) は触らず一時 DB を使用
- 新規スクリプトは scripts/ への追加のみ

Usage:
    python -m scripts.dump_grounding_chunks \\
        --output docs/runs/F-wl-hit-quality-audit/grounding_chunk_raw_dump.json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.shared.config import GEMINI_API_KEY  # noqa: E402
from src.triage.jp_coverage_verifier import (  # noqa: E402
    JpCoverageVerifier,
    _extract_domain_from_chunk,
)


SLOT_2_EVENT = {
    "slot_index": 2,
    "event_id": "cls-1a38c0ca8c99",
    "title": "Filmmakers slam BBC after Gaza documentary wins award despite being dropped",
    "summary": (
        "BAFTA TV 賞を受賞したガザ医療従事者ドキュメンタリーを巡り、BBC が放送中止に "
        "したとして製作陣が公的に非難。Channel 4 が代替放送。"
    ),
    "f13b_observed_matched_urls": ["https://afpbb.com"],
    "f13b_observed_matched_tier": "tier_2_wire_service",
    "audit_verdict": "Suspect FP (afpbb は別事象 BBC Gaza doc Ofcom 制裁 3604087 を報じるのみ、Slot-2 specific event は不在)",
}


def get_gemini_client() -> Any:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")
    from google import genai

    return genai.Client(api_key=GEMINI_API_KEY)


def dump_chunks(
    verifier: JpCoverageVerifier,
    event: dict[str, Any],
) -> dict[str, Any]:
    """Gemini Grounding を実行し、chunk.web 配列の生フィールドを抽出する。"""
    query = verifier._build_search_query(event["title"], event["summary"])
    start = time.time()

    if verifier.gemini_client is None:
        raise RuntimeError("gemini_client is not configured")

    from google.genai import types

    prompt = (
        f"次のニュースが日本のメディアで報道されているか、"
        f"日本語の Web 検索で確認してください。\n\n"
        f"検索クエリ: {query}\n\n"
        f"検索結果から、日本のメディア (新聞、テレビ局、通信社等) の "
        f"記事 URL を中心に確認してください。"
    )

    response = verifier.gemini_client.models.generate_content(
        model=verifier.model,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )

    elapsed = time.time() - start

    chunks_dump: list[dict[str, Any]] = []
    candidates = getattr(response, "candidates", None) or []
    if candidates:
        metadata = getattr(candidates[0], "grounding_metadata", None)
        if metadata is not None:
            grounding_chunks = getattr(metadata, "grounding_chunks", None) or []
            for idx, chunk in enumerate(grounding_chunks):
                web = getattr(chunk, "web", None)
                if web is None:
                    chunks_dump.append({
                        "idx": idx,
                        "web_present": False,
                        "raw_repr": repr(chunk)[:500],
                    })
                    continue

                uri = getattr(web, "uri", None)
                title = getattr(web, "title", None)
                domain_attr = getattr(web, "domain", None)
                extracted_domain = _extract_domain_from_chunk(chunk)

                chunks_dump.append({
                    "idx": idx,
                    "web_present": True,
                    "web_uri": uri,
                    "web_title": title,
                    "web_domain_attr": domain_attr,
                    "extracted_domain_via_strategy": extracted_domain,
                    "extraction_strategy_used": (
                        "strategy_1_web_domain" if isinstance(domain_attr, str) and domain_attr.strip()
                        else "strategy_2_web_title" if isinstance(title, str) and extracted_domain
                        else "none"
                    ),
                })

    response_text = ""
    try:
        if candidates:
            content = getattr(candidates[0], "content", None)
            if content is not None:
                parts = getattr(content, "parts", None) or []
                response_text = "".join(getattr(p, "text", "") or "" for p in parts)
    except Exception:
        response_text = ""

    return {
        "event": event,
        "query": query,
        "elapsed_seconds": round(elapsed, 2),
        "chunk_count": len(chunks_dump),
        "chunks": chunks_dump,
        "response_text_excerpt": response_text[:800],
        "model": verifier.model,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/runs/F-wl-hit-quality-audit/grounding_chunk_raw_dump.json"),
        help="出力 JSON パス",
    )
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_db = Path(tmpdir) / "audit_temp.db"
        gemini_client = get_gemini_client()
        verifier = JpCoverageVerifier(
            gemini_client=gemini_client,
            db_path=temp_db,
        )

        result = dump_chunks(verifier, SLOT_2_EVENT)

    payload = {
        "version": "1.0",
        "batch": "F-wl-hit-quality-audit",
        "task": "Task D — Slot-2 cls-1a38c0ca8c99 Grounding chunk 生データダンプ",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "scope": "Slot-2 only (Suspect FP 確定、診断価値最大、カズヤ承認後)",
        "purpose": (
            "F-trial-run-post-tune 試運転で matched_urls=https://afpbb.com (ベアドメイン) "
            "となった原因を切り分ける: (a) SDK バグ説 (chunk.web.uri が redirect URL のみ) / "
            "(b) API 仕様説 (article path は元から返されない) / (c) クエリ品質説"
        ),
        "result": result,
    }

    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Saved: {args.output}")
    print(f"  chunk_count={result['chunk_count']}, elapsed={result['elapsed_seconds']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
