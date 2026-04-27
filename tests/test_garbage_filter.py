"""ハイブリッド garbage_filter（静的ルール + LLM）の挙動を検証する。

Phase 1.5 batch E-1 で導入したハイブリッド構成:
  - ステージ1: 言語非依存の静的ルール（length/category/date）
  - ステージ2: LLM による文脈的判定（llm_client=None ならスキップ）

実 LLM は呼ばない — llm_client は MagicMock で差し替える。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.triage import garbage_filter
from src.triage.garbage_filter import (
    BLOCKED_CATEGORIES,
    apply_garbage_filter,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _old_iso(hours: int = 72) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def _make_article(
    *,
    title: str = "Tensions rise as G7 leaders meet in Brussels over trade dispute",
    summary: str = "Leaders gathered to discuss escalating trade tensions and renewed export controls in semiconductor supply chains.",
    published_at: str | None = None,
    categories: list[str] | None = None,
) -> dict:
    """十分な長さ・新しい日時・空カテゴリのデフォルト記事。"""
    return {
        "title": title,
        "summary": summary,
        "published_at": published_at if published_at is not None else _now_iso(),
        "categories": categories or [],
    }


def _llm_mock_returning(items: list[dict]) -> MagicMock:
    """generate() が JSON 配列を返すモック LLM クライアント。"""
    import json as _json
    client = MagicMock()
    client.generate.return_value = _json.dumps(items)
    return client


# ── ステージ1: 静的ルール ────────────────────────────────────────────────────


def test_static_excludes_short_title():
    """タイトル < 5 文字は length 理由で除外される。"""
    articles = [
        _make_article(title="Hi"),  # 2 文字 → 除外
        _make_article(),             # 通過想定
    ]
    kept = apply_garbage_filter(articles, llm_client=None)
    assert len(kept) == 1
    assert kept[0]["title"].startswith("Tensions")


def test_static_excludes_short_total_text():
    """タイトル + 概要 < 30 文字は length 理由で除外される。"""
    articles = [
        _make_article(title="Hello!", summary="Hi"),  # 8 文字合計 → 除外
        _make_article(),                                # 通過
    ]
    kept = apply_garbage_filter(articles, llm_client=None)
    assert len(kept) == 1


def test_static_excludes_too_old():
    """48 時間より古い記事は date 理由で除外される。"""
    articles = [
        _make_article(published_at=_old_iso(hours=72)),  # 72h 前 → 除外
        _make_article(),                                    # now → 通過
    ]
    kept = apply_garbage_filter(articles, llm_client=None)
    assert len(kept) == 1


def test_static_keeps_recent_within_48h():
    """48 時間ぴったり境界（実際は <= 48h）の記事は通過する。"""
    articles = [
        _make_article(published_at=_old_iso(hours=24)),
        _make_article(published_at=_old_iso(hours=47)),
    ]
    kept = apply_garbage_filter(articles, llm_client=None)
    assert len(kept) == 2


def test_static_excludes_blocked_category():
    """BLOCKED_CATEGORIES (advertisement/horoscope 等) は category 理由で除外。"""
    for cat in ["advertisement", "horoscope", "promotion", "sponsored"]:
        assert cat in BLOCKED_CATEGORIES
        articles = [
            _make_article(categories=[cat]),
            _make_article(categories=["politics"]),  # 通過
        ]
        kept = apply_garbage_filter(articles, llm_client=None)
        assert len(kept) == 1, f"category={cat} should be excluded"
        assert "politics" in (kept[0].get("categories") or [])


def test_static_blocked_category_case_insensitive():
    """カテゴリ判定は大文字小文字を区別しない。"""
    articles = [_make_article(categories=["ADVERTISEMENT"])]
    kept = apply_garbage_filter(articles, llm_client=None)
    assert kept == []


def test_static_missing_published_at_passes():
    """published_at が無い記事は静的ルールで除外しない（保守的）。"""
    art = _make_article()
    art["published_at"] = None
    kept = apply_garbage_filter([art], llm_client=None)
    assert len(kept) == 1


def test_static_unparseable_published_at_passes():
    """published_at が ISO 8601 でパースできない場合も除外しない。"""
    art = _make_article(published_at="not a date")
    kept = apply_garbage_filter([art], llm_client=None)
    assert len(kept) == 1


def test_empty_articles_returns_empty():
    """空入力は空のまま返す（LLM クライアントの有無は無関係）。"""
    assert apply_garbage_filter([], llm_client=None) == []
    assert apply_garbage_filter([], llm_client=MagicMock()) == []


# ── 多言語対応（言語依存の正規表現を持たないことの確認）─────────────────────


def test_static_does_not_exclude_korean_articles():
    """ハングルのみの記事を静的ルールで除外しないこと。"""
    article = _make_article(
        title="삼성전자, 차세대 반도체 패키징 기술 공개",
        summary="삼성전자가 차세대 반도체 패키징 기술을 공개하고 글로벌 시장 공략에 나섰다.",
    )
    kept = apply_garbage_filter([article], llm_client=None)
    assert len(kept) == 1


def test_static_does_not_exclude_arabic_articles():
    """アラビア語のみの記事を静的ルールで除外しないこと。"""
    article = _make_article(
        title="ارتفاع التوترات الجيوسياسية في الشرق الأوسط",
        summary="شهدت منطقة الشرق الأوسط ارتفاعا حادا في التوترات الجيوسياسية بعد الأحداث الأخيرة.",
    )
    kept = apply_garbage_filter([article], llm_client=None)
    assert len(kept) == 1


def test_static_does_not_exclude_cyrillic_articles():
    """キリル文字（ロシア語）のみの記事を静的ルールで除外しないこと。"""
    article = _make_article(
        title="Россия объявила о новой энергетической стратегии",
        summary="Российские власти представили долгосрочный план по диверсификации экспорта энергоносителей.",
    )
    kept = apply_garbage_filter([article], llm_client=None)
    assert len(kept) == 1


def test_static_does_not_exclude_thai_articles():
    """タイ語のみの記事を静的ルールで除外しないこと。"""
    article = _make_article(
        title="ประเทศไทยเผยแผนยุทธศาสตร์เศรษฐกิจดิจิทัลใหม่",
        summary="รัฐบาลไทยประกาศแผนยุทธศาสตร์เศรษฐกิจดิจิทัลใหม่เพื่อเพิ่มขีดความสามารถในการแข่งขัน.",
    )
    kept = apply_garbage_filter([article], llm_client=None)
    assert len(kept) == 1


# ── ステージ2: LLM 判定 ─────────────────────────────────────────────────────


def test_llm_passthrough_when_client_is_none():
    """llm_client=None なら静的ルール通過分をそのまま返す（LLM 呼ばない）。"""
    articles = [_make_article(), _make_article(title="Another major geopolitical development unfolds in Asia")]
    kept = apply_garbage_filter(articles, llm_client=None)
    assert len(kept) == 2


def test_llm_excludes_when_is_valuable_false():
    """LLM が is_valuable=false を返した記事は除外される。"""
    articles = [
        _make_article(title="Geopolitical shift in South China Sea reshapes alliances"),
        _make_article(title="Local market price for cucumbers wobbles by 0.3 percent"),
    ]
    llm = _llm_mock_returning([
        {"item_id": 0, "is_valuable": True, "reason": "地政学的重要性あり"},
        {"item_id": 1, "is_valuable": False, "reason": "微価格変動"},
    ])
    kept = apply_garbage_filter(articles, llm_client=llm)
    assert len(kept) == 1
    assert "South China Sea" in kept[0]["title"]
    llm.generate.assert_called_once()


def test_llm_keeps_when_is_valuable_true():
    """LLM が全件 is_valuable=true なら全件通過する。"""
    articles = [
        _make_article(title="Major shift in EU-China trade policy announced today"),
        _make_article(title="Breakthrough in fusion energy reported by international team"),
    ]
    llm = _llm_mock_returning([
        {"item_id": 0, "is_valuable": True, "reason": "通商の構造変化"},
        {"item_id": 1, "is_valuable": True, "reason": "技術ブレークスルー"},
    ])
    kept = apply_garbage_filter(articles, llm_client=llm)
    assert len(kept) == 2


def test_llm_error_passes_batch_through():
    """LLM が例外を投げたバッチは全件通過させる（保守的フォールバック）。"""
    articles = [_make_article(), _make_article()]
    llm = MagicMock()
    llm.generate.side_effect = RuntimeError("LLM unavailable")
    kept = apply_garbage_filter(articles, llm_client=llm)
    assert len(kept) == 2


def test_static_runs_before_llm_so_llm_only_sees_survivors():
    """静的ルールで除外された記事は LLM プロンプトに含まれないこと。"""
    articles = [
        _make_article(title="Hi"),                                  # 静的除外（length）
        _make_article(categories=["advertisement"]),                # 静的除外（category）
        _make_article(published_at=_old_iso(hours=72)),             # 静的除外（date）
        _make_article(title="Strategic geopolitical realignment in Indo-Pacific"),  # 通過
    ]
    llm = _llm_mock_returning([
        {"item_id": 0, "is_valuable": True, "reason": "地政学的重要性"},
    ])
    kept = apply_garbage_filter(articles, llm_client=llm)

    # LLM は 1 件しか見ていないこと (item_id=0 のみ)
    assert llm.generate.call_count == 1
    sent_prompt = llm.generate.call_args[0][0]
    assert "Indo-Pacific" in sent_prompt
    assert "Hi" not in sent_prompt or "[0]" in sent_prompt  # 短すぎ記事は混入しない
    assert len(kept) == 1


def test_all_excluded_by_static_skips_llm():
    """静的ルールで全件除外された場合、LLM は呼ばれない。"""
    articles = [
        _make_article(title="A"),
        _make_article(categories=["horoscope"]),
    ]
    llm = MagicMock()
    kept = apply_garbage_filter(articles, llm_client=llm)
    assert kept == []
    llm.generate.assert_not_called()


def test_llm_batches_when_more_than_batch_size(monkeypatch):
    """30 件超は複数バッチに分割される。"""
    monkeypatch.setattr(garbage_filter, "_BATCH_SIZE", 5)

    articles = [
        _make_article(title=f"Significant geopolitical event number {i} unfolds globally")
        for i in range(12)
    ]

    import json as _json
    def _generate(_prompt: str) -> str:
        # バッチに含まれる item_id 数だけ true を返す
        # _BATCH_SIZE=5 なので各バッチ max 5 件
        n = _prompt.count("] タイトル:")
        return _json.dumps([
            {"item_id": i, "is_valuable": True, "reason": "ok"} for i in range(n)
        ])

    llm = MagicMock()
    llm.generate.side_effect = _generate

    kept = apply_garbage_filter(articles, llm_client=llm)
    # 12 件 / batch=5 → 3 バッチ
    assert llm.generate.call_count == 3
    assert len(kept) == 12


def test_llm_unexpected_response_passes_batch_through():
    """LLM が JSON でない応答を返したバッチは全件通過する（堅牢性）。"""
    articles = [_make_article()]
    llm = MagicMock()
    llm.generate.return_value = "not a json array"
    kept = apply_garbage_filter(articles, llm_client=llm)
    assert len(kept) == 1


# ── ログ出力（3 段階）─────────────────────────────────────────────────────


def test_logs_three_stage_summary(caplog):
    """ステージ1・ステージ2・完了の 3 段階ログが INFO で出ること。"""
    import logging

    articles = [
        _make_article(title="Hi"),                                  # 静的除外
        _make_article(title="Major shift in global trade dynamics"),  # 通過
    ]
    llm = _llm_mock_returning([
        {"item_id": 0, "is_valuable": True, "reason": "ok"},
    ])

    with caplog.at_level(logging.INFO, logger="src.triage.garbage_filter"):
        apply_garbage_filter(articles, llm_client=llm)

    messages = [r.getMessage() for r in caplog.records]
    assert any("ステージ1 (静的)" in m for m in messages)
    assert any("ステージ2 (LLM)" in m for m in messages)
    assert any("[GarbageFilter] 完了:" in m for m in messages)


def test_logs_skip_llm_when_client_none(caplog):
    """llm_client=None のときに 'スキップ' ログが出る。"""
    import logging

    articles = [_make_article()]
    with caplog.at_level(logging.INFO, logger="src.triage.garbage_filter"):
        apply_garbage_filter(articles, llm_client=None)

    messages = [r.getMessage() for r in caplog.records]
    assert any("ステージ2 (LLM)" in m and "スキップ" in m for m in messages)
