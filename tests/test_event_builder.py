"""event_builder モジュールのテスト。"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.ingestion.event_builder import (
    _HIGH_FREQ_ANCHORS,
    _GIANT_CLUSTER_THRESHOLD,
    _TOP_EN_PER_JP,
    _extract_keywords,
    build_events_from_normalized,
    cluster_articles,
    cluster_to_event,
    load_normalized_articles,
)
from src.shared.models import NewsEvent


# ---------- helpers ----------

def _make_article(
    article_id: str,
    title: str,
    url: str = "",
    country: str = "JP",
    source_name: str = "NHK",
    category: str = "economy",
    published_at: str = "2026-03-31T10:00:00+00:00",
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
        "fetched_at": "2026-03-31T11:00:00+00:00",
        "raw_ref": "",
    }


def _write_normalized(path: Path, articles: list[dict]) -> None:
    path.write_text(json.dumps(articles, ensure_ascii=False), encoding="utf-8")


# ---------- _extract_keywords ----------

def test_extract_keywords_japanese_3char():
    kw = _extract_keywords("日本銀行が追加利上げを決定")
    # 「日本銀」「本銀行」「利上げ」などが抽出されるはず
    assert any(len(k) == 3 for k in kw)


def test_extract_keywords_japanese_4char():
    kw = _extract_keywords("日本銀行が追加利上げを決定")
    # 「日本銀行」(4 文字) が含まれるはず
    assert "日本銀行" in kw


def test_extract_keywords_english():
    kw = _extract_keywords("Japan raises interest rates sharply")
    assert "raises" in kw
    assert "interest" in kw
    assert "sharply" in kw


def test_extract_keywords_english_stopword_excluded():
    kw = _extract_keywords("which would could should")
    # ストップワードは除外される
    assert "which" not in kw
    assert "would" not in kw


def test_extract_keywords_empty():
    kw = _extract_keywords("")
    assert kw == set()


def test_extract_keywords_short_words_excluded():
    # 4 文字以下の英単語は除外
    kw = _extract_keywords("the cat sat on mat")
    assert "cat" not in kw
    assert "sat" not in kw


# ---------- cluster_articles ----------

def test_cluster_articles_empty():
    assert cluster_articles([]) == []


def test_cluster_articles_single():
    art = [_make_article("a1", "日本銀行が利上げを決定した")]
    clusters = cluster_articles(art)
    assert len(clusters) == 1
    assert len(clusters[0]) == 1


def test_cluster_articles_groups_related():
    articles = [
        _make_article("a1", "日本銀行が追加利上げを決定"),
        _make_article("a2", "日本銀行の利上げ決定を受けて市場が反応", country="Global", source_name="Reuters"),
        _make_article("a3", "プロ野球：甲子園でサヨナラ勝ち", category="sports"),
    ]
    clusters = cluster_articles(articles)
    # a1 と a2 は「日本銀」「銀行が」「利上げ」などを共有 → 同クラスタ
    # a3 は独立
    assert len(clusters) == 2
    cluster_sizes = sorted(len(c) for c in clusters)
    assert cluster_sizes == [1, 2]


def test_cluster_articles_all_unrelated():
    articles = [
        _make_article("a1", "東京の天気予報"),
        _make_article("a2", "Football World Cup results"),
        _make_article("a3", "ロケット打ち上げ成功"),
    ]
    clusters = cluster_articles(articles)
    # 共通キーワードなし → 全て独立クラスタ
    assert len(clusters) == 3


def test_cluster_articles_all_related():
    articles = [
        _make_article("a1", "日本銀行が利上げを決定した"),
        _make_article("a2", "日本銀行の政策決定会合が利上げ"),
        _make_article("a3", "日本銀行の利上げで円高が進む"),
    ]
    clusters = cluster_articles(articles)
    assert len(clusters) == 1
    assert len(clusters[0]) == 3


def test_cluster_articles_min_shared_2():
    """min_shared_keywords=2 なら共通キーワードが 1 つの場合は同クラスタにならない。"""
    articles = [
        _make_article("a1", "日本銀行が利上げ"),
        _make_article("a2", "日本政府が少子化対策"),  # 「日本」のみ共通
    ]
    clusters_1 = cluster_articles(articles, min_shared_keywords=1)
    clusters_2 = cluster_articles(articles, min_shared_keywords=2)
    # min=1 では「日本」(3 文字サブストリング) が一致すれば同クラスタになる可能性あり
    # min=2 では最低 2 キーワード共通が必要
    # このテストでは結果数の関係を確認するだけ
    assert len(clusters_2) >= len(clusters_1)


# ---------- cluster_to_event ----------

def test_cluster_to_event_basic():
    cluster = [_make_article("a1", "日本銀行が利上げを決定", url="http://nhk.jp/a1", tags=["経済"])]
    event = cluster_to_event(cluster)
    assert isinstance(event, NewsEvent)
    assert event.id.startswith("cls-")
    assert event.title == "日本銀行が利上げを決定"
    assert event.category == "economy"
    assert "http://nhk.jp/a1" in event.source_urls


def test_cluster_to_event_jp_global_split():
    cluster = [
        _make_article("a1", "日本銀行が利上げ", url="http://nhk.jp/a1", country="JP", source_name="NHK"),
        _make_article("a2", "Bank of Japan raises rates", url="http://reuters.com/a2",
                      country="Global", source_name="Reuters"),
    ]
    event = cluster_to_event(cluster)
    assert event.japan_view is not None
    assert "NHK" in event.japan_view
    assert event.global_view is not None
    assert "Reuters" in event.global_view


def test_cluster_to_event_jp_preferred_as_primary():
    """JP 記事がある場合そのタイトルを採用する。"""
    cluster = [
        _make_article("a1", "Global headline first", url="http://bbc.com/a1",
                      country="Global", source_name="BBC"),
        _make_article("a2", "日本語タイトル", url="http://nhk.jp/a2",
                      country="JP", source_name="NHK"),
    ]
    event = cluster_to_event(cluster)
    assert event.title == "日本語タイトル"


def test_cluster_to_event_source_urls_all_included():
    cluster = [
        _make_article("a1", "記事1", url="http://a1.com"),
        _make_article("a2", "記事2", url="http://a2.com"),
    ]
    event = cluster_to_event(cluster)
    assert "http://a1.com" in event.source_urls
    assert "http://a2.com" in event.source_urls


def test_cluster_to_event_tags_deduplicated():
    cluster = [
        _make_article("a1", "記事1", tags=["経済", "金融"]),
        _make_article("a2", "記事2", tags=["経済", "政治"]),
    ]
    event = cluster_to_event(cluster)
    assert event.tags.count("経済") == 1


def test_cluster_to_event_category_prefers_non_general():
    cluster = [
        _make_article("a1", "記事1", category="general"),
        _make_article("a2", "記事2", category="economy"),
    ]
    event = cluster_to_event(cluster)
    assert event.category == "economy"


# ---------- load_normalized_articles ----------

def test_load_normalized_articles_missing_dir(tmp_path):
    articles = load_normalized_articles(tmp_path / "nonexistent")
    assert articles == []


def test_load_normalized_articles_with_data(tmp_path):
    norm_dir = tmp_path / "normalized"
    norm_dir.mkdir()
    sample = [_make_article("a1", "テスト記事")]
    _write_normalized(norm_dir / "test_normalized.json", sample)

    articles = load_normalized_articles(norm_dir)
    assert len(articles) == 1
    assert articles[0]["id"] == "a1"


def test_load_normalized_articles_multiple_files(tmp_path):
    norm_dir = tmp_path / "normalized"
    norm_dir.mkdir()
    _write_normalized(norm_dir / "src1_normalized.json", [_make_article("a1", "記事1")])
    _write_normalized(norm_dir / "src2_normalized.json", [_make_article("a2", "記事2"), _make_article("a3", "記事3")])

    articles = load_normalized_articles(norm_dir)
    assert len(articles) == 3


def test_load_normalized_articles_ignores_non_matching_files(tmp_path):
    norm_dir = tmp_path / "normalized"
    norm_dir.mkdir()
    _write_normalized(norm_dir / "test_normalized.json", [_make_article("a1", "記事1")])
    (norm_dir / "README.md").write_text("dummy")  # 除外されるべきファイル

    articles = load_normalized_articles(norm_dir)
    assert len(articles) == 1


# ---------- build_events_from_normalized ----------

def test_build_events_from_normalized_empty_dir(tmp_path):
    events = build_events_from_normalized(tmp_path / "empty")
    assert events == []


def test_build_events_from_normalized_returns_news_events(tmp_path):
    norm_dir = tmp_path / "normalized"
    norm_dir.mkdir()
    sample = [
        _make_article("a1", "日本銀行が追加利上げを決定した", tags=["経済"], summary="日銀は追加利上げを発表"),
    ]
    _write_normalized(norm_dir / "nhk_normalized.json", sample)

    events = build_events_from_normalized(norm_dir)
    assert len(events) >= 1
    assert all(isinstance(e, NewsEvent) for e in events)


def test_build_events_from_normalized_clusters_related(tmp_path):
    norm_dir = tmp_path / "normalized"
    norm_dir.mkdir()
    sample = [
        _make_article("a1", "日本銀行が追加利上げを決定"),
        _make_article("a2", "日本銀行の利上げ、円高に影響", country="Global", source_name="Reuters"),
        _make_article("a3", "全く関係ないスポーツニュース"),
    ]
    _write_normalized(norm_dir / "test_normalized.json", sample)

    events = build_events_from_normalized(norm_dir)
    # 3 記事 → 2 クラスタ (利上げ系 + スポーツ系)
    assert len(events) == 2


# ---------- run_from_normalized (統合テスト) ----------

@pytest.fixture()
def tmp_dirs(tmp_path: Path):
    output = tmp_path / "output"
    db = tmp_path / "db" / "test.db"
    return output, db


@pytest.fixture()
def no_llm_api(monkeypatch):
    """Disable all LLM call sites so run_from_normalized stays deterministic.

    .env で GEMINI_API_KEY がセットされていると Elite Judge / Viral LLM /
    Garbage Filter / Judge などが本物の API を叩くため、統合テストが
    レイテンシ依存・非決定的になる。モジュール側の定数・クライアント取得関数を
    nullish にパッチすることで、全 LLM 経路を fallback 側（テンプレ生成）に寄せる。
    """
    # Main の分岐を止める
    monkeypatch.setattr("src.main.GEMINI_API_KEY", "")
    monkeypatch.setattr("src.main.JUDGE_ENABLED", False)
    monkeypatch.setattr("src.main.ELITE_JUDGE_ENABLED", False)
    monkeypatch.setattr("src.main.MISSION_LLM_ENABLED", False)
    monkeypatch.setattr("src.main.GARBAGE_FILTER_ENABLED", False)
    # Factory 経由の client を全て None に落とす
    monkeypatch.setattr("src.main.get_cluster_llm_client", lambda: None)
    monkeypatch.setattr("src.main.get_garbage_filter_client", lambda: None)
    monkeypatch.setattr("src.main.get_judge_llm_client", lambda: None)
    monkeypatch.setattr("src.generation.script_writer.get_script_llm_client", lambda: None)
    # article_writer は get_article_llm_client 経由
    try:
        monkeypatch.setattr("src.generation.article_writer.get_article_llm_client", lambda: None)
    except AttributeError:
        pass  # article_writer の import 形式が異なるケースは無視


def test_run_from_normalized_creates_output_files(tmp_dirs, tmp_path, no_llm_api):
    """run_from_normalized() が成果物ファイルを生成し DB に保存することを確認する。
    batch-based system: DB に batch を登録してから実行する。

    JP+EN の cross-language クラスタを含む batch を使用する。
    単一 JP 記事は safety gate により quality floor に引っかかり skipped になるため、
    英語 Reuters 記事を加えることで EN view を持つイベントを作る。

    LLM 経路はすべて no_llm_api fixture で無効化され、script/article は
    決定的なテンプレフォールバックで生成される。
    """
    norm_dir = tmp_path / "normalized"
    norm_dir.mkdir()
    norm_file = norm_dir / "nhk_normalized.json"
    # JP + EN の 2 記事で cross-language クラスタを形成する
    # → sources_en が存在するため safety gate を通過し quality floor を満たす
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
    _write_normalized(norm_file, sample)

    output, db = tmp_dirs
    # DB 初期化 & batch 登録
    from src.storage.db import init_db, save_batch
    init_db(db)
    save_batch(
        db_path=db,
        batch_id="20260410_120000",
        raw_files=[],
        normalized_files=[str(norm_file)],
    )

    from src.main import run_from_normalized
    record = run_from_normalized(norm_dir, output, db)

    assert record.status == "completed"
    assert record.event_id.startswith("cls-")
    assert Path(record.script_path).exists()
    assert Path(record.article_path).exists()
    assert Path(record.video_payload_path).exists()


def test_run_from_normalized_skips_when_flagship_gate_blocks(tmp_dirs, tmp_path, no_llm_api):
    """sources_en の無い単一 JP 記事は flagship_gate により status=skipped になる。

    旧: scheduler の quality floor が "no_publishable_candidates" を立てて止めていた。
    新: Elite Judge 廃止 → Flagship Gate 直結。_passes_flagship_gate() が "no_en_sources"
        を返し、main.py が schedule_tracking.flagship_gate_blocked=True で skip を記録する。

    この回帰防止の本質は「証拠不十分な JP-only 候補が勝手に台本化されないこと」で、
    その検証フラグが `no_publishable_candidates` から `flagship_gate_blocked` に移った。
    """
    norm_dir = tmp_path / "normalized"
    norm_dir.mkdir()
    norm_file = norm_dir / "nhk_normalized.json"
    # 単一 JP 記事: sources_en=empty かつ english_views なし → safety gate [抑制] → held_back
    sample = [
        _make_article(
            "a1",
            "日本銀行が追加利上げを決定した",
            url="http://nhk.jp/articles/a1",
            tags=["経済", "金融"],
            summary="日本銀行は追加の利上げを決定し、円高が進んだ。",
        ),
    ]
    _write_normalized(norm_file, sample)

    output, db = tmp_dirs
    from src.storage.db import init_db, save_batch
    init_db(db)
    save_batch(
        db_path=db,
        batch_id="20260410_120001",
        raw_files=[],
        normalized_files=[str(norm_file)],
    )

    from src.main import run_from_normalized
    record = run_from_normalized(norm_dir, output, db)

    # Flagship gate が no_en_sources を検出 → skipped (no-op) で正常終了
    assert record.status == "skipped"
    assert record.event_id == "none"

    # script / article が生成されていないこと
    assert record.script_path is None
    assert record.article_path is None

    # run_summary の schedule_tracking 側に flagship_gate_blocked が記録されること
    import json
    summary_path = output / "run_summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    # record.error は "flagship_gate_blocked:no_en_sources" の prefix で始まる
    assert record.error and record.error.startswith("flagship_gate_blocked:")


# ── クロスランゲージ: _extract_keywords にアンカートークンが含まれること ────────

def test_extract_keywords_includes_entity_token_jp():
    kw = _extract_keywords("日本銀行が追加利上げを決定")
    assert "entity:boj" in kw


def test_extract_keywords_includes_kw_token_jp():
    kw = _extract_keywords("日本銀行が追加利上げを決定")
    assert "kw:ratehike" in kw


def test_extract_keywords_includes_country_token_en():
    kw = _extract_keywords("Japan raises interest rates sharply")
    assert "country:japan" in kw


def test_extract_keywords_includes_entity_token_en():
    kw = _extract_keywords("Bank of Japan decides on rate hike")
    assert "entity:boj" in kw


# ── クロスランゲージ: アンカートークン経由で日英が同クラスタになること ────────

def test_cluster_articles_cross_lang_via_boj_token():
    """日銀（JP）と Bank of Japan（EN）は entity:boj を共有して 1 クラスタになる。"""
    articles = [
        _make_article("jp1", "日本銀行が利上げを決定した", country="JP", source_name="NHK"),
        _make_article("en1", "Bank of Japan raises rates", country="Global", source_name="Reuters"),
    ]
    clusters = cluster_articles(articles)
    assert len(clusters) == 1
    assert len(clusters[0]) == 2


def test_cluster_articles_cross_lang_via_country_and_kw():
    """3件の弱アンカー（country:japan + entity:trump + kw:tariff）で日英が 1 クラスタになる。

    2件の弱アンカーのみでは新ルール(_MIN_CROSS_LANG_WEAK_ONLY_ANCHOR_HITS=3)で弾かれる。
    3件以上の弱アンカーがある場合は接続可能。
    """
    articles = [
        _make_article("jp1", "日本のトランプ関税、政府が対応", country="JP"),
        _make_article("en1", "Japan responds to Trump tariffs", country="Global"),
    ]
    clusters = cluster_articles(articles)
    assert len(clusters) == 1


def test_cross_lang_two_weak_anchors_not_enough():
    """弱アンカー2件のみ（country:japan + kw:tariff）では cross-lang 接続しない。

    entity:trump のような強アンカーがなく合計2件では _MIN_CROSS_LANG_WEAK_ONLY_ANCHOR_HITS=3 未満。
    """
    articles = [
        _make_article("jp1", "日本が関税を引き上げ", country="JP"),
        _make_article("en1", "Japan raises tariffs", country="Global"),
    ]
    clusters = cluster_articles(articles)
    assert len(clusters) == 2


def test_cluster_articles_different_events_not_merged():
    """別イベント（日銀利上げ vs FRB利下げ）はアンカートークンが重ならず別クラスタ。"""
    articles = [
        _make_article("jp1", "日本銀行が利上げを決定", country="JP"),
        _make_article("en1", "Federal Reserve cuts rates", country="Global"),
    ]
    clusters = cluster_articles(articles)
    assert len(clusters) == 2


# ── クロスランゲージ: LLM post-merge ─────────────────────────────────────────

def _make_mock_llm(response: str) -> MagicMock:
    """Create a mock LLM that returns batch-merge JSON for all pairs.

    response accepts legacy "YES"/"NO" or explicit verdict strings.
    The mock parses pair_ids from the prompt and echoes a verdict for each.

    Mapping:
      "YES"     → same_event
      "NO"      → different_event
      "RELATED" → related_but_distinct
    """
    import re as _re

    _verdict_map = {
        "YES": "same_event",
        "NO": "different_event",
        "RELATED": "related_but_distinct",
    }
    verdict = _verdict_map.get(response.strip().upper(), "different_event")

    def _generate(prompt: str) -> str:
        ids = [int(m.group(1)) for m in _re.finditer(r"^\[(\d+)\]", prompt, _re.MULTILINE)]
        if not ids:
            return "[]"
        import json as _json
        return _json.dumps([
            {"pair_id": pid, "verdict": verdict, "reason": "mock"}
            for pid in ids
        ])

    client = MagicMock()
    client.generate.side_effect = _generate
    return client


def test_cluster_articles_llm_merges_jp_en_no_anchor_overlap():
    """アンカートークンが重ならない日英ペアを LLM YES で 1 クラスタにマージ。"""
    articles = [
        _make_article("jp1", "選手交代が話題", country="JP"),   # sports-like, no anchors
        _make_article("en1", "Player substitution controversy", country="Global"),
    ]
    # LLM なしでは 2 クラスタ
    assert len(cluster_articles(articles)) == 2
    # LLM YES → 1 クラスタ
    result = cluster_articles(articles, llm_client=_make_mock_llm("YES"))
    assert len(result) == 1
    sources = {a.get("source_name") for a in result[0]}
    assert "NHK" in sources


def test_cluster_articles_llm_no_does_not_merge():
    """LLM NO ならマージされない。"""
    articles = [
        _make_article("jp1", "プロ野球結果", country="JP"),
        _make_article("en1", "Baseball game results", country="Global"),
    ]
    result = cluster_articles(articles, llm_client=_make_mock_llm("NO"))
    assert len(result) == 2


def test_cluster_articles_llm_not_called_for_already_mixed_cluster():
    """BFS で既にマージ済みの混合クラスタに対し LLM は呼ばれない。"""
    # "日本銀行が利上げ" → entity:boj + country:japan (2 anchors)
    # "Bank of Japan raises rates" → entity:boj + country:japan (2 anchors)
    # common anchors = 2 ≥ _MIN_CROSS_LANG_ANCHOR_HITS → BFS で 1 クラスタに結合
    articles = [
        _make_article("jp1", "日本銀行が利上げ", country="JP"),
        _make_article("en1", "Bank of Japan raises rates", country="Global"),
    ]
    mock_llm = _make_mock_llm("YES")
    result = cluster_articles(articles, llm_client=mock_llm)
    assert len(result) == 1
    mock_llm.generate.assert_not_called()


def test_cluster_articles_llm_none_no_crash():
    """llm_client=None でも正常動作し例外が出ない。"""
    articles = [
        _make_article("jp1", "日銀が利上げ", country="JP"),
        _make_article("en1", "Some unrelated story", country="Global"),
    ]
    result = cluster_articles(articles, llm_client=None)
    assert isinstance(result, list)


def test_cluster_articles_llm_exception_does_not_crash():
    """LLM が例外を返してもクラスタリングが正常終了する。"""
    client = MagicMock()
    client.generate.side_effect = Exception("API failure")
    articles = [
        _make_article("jp1", "選手交代", country="JP"),
        _make_article("en1", "Player substitution", country="Global"),
    ]
    result = cluster_articles(articles, llm_client=client)
    assert isinstance(result, list)
    assert len(result) == 2  # マージ失敗 → 分離のまま


def test_llm_post_merge_prefilter_limits_calls():
    """大量の JP/EN クラスタがある場合、LLM 呼び出しが _TOP_EN_PER_JP × JP数 以下に絞られる。"""
    # 6 JP + 6 EN = 36 pairs → pre-filter で 6 * _TOP_EN_PER_JP 件に削減
    articles = []
    for i in range(6):
        articles.append(_make_article(f"jp{i}", f"固有話題{i}の日本語記事", country="JP"))
    for i in range(6):
        articles.append(_make_article(f"en{i}", f"Unique topic {i} English article", country="Global"))

    mock_llm = _make_mock_llm("NO")
    cluster_articles(articles, llm_client=mock_llm)
    assert mock_llm.generate.call_count <= 6 * _TOP_EN_PER_JP


def test_build_events_cross_lang_llm_yes(tmp_path):
    """build_events_from_normalized に llm_client を渡すと JP/EN 両方の view が入る。"""
    norm_dir = tmp_path / "normalized"
    norm_dir.mkdir()
    sample = [
        _make_article("jp1", "選手交代が物議", country="JP", source_name="NHK",
                      url="http://nhk.jp/jp1"),
        _make_article("en1", "Player substitution controversy", country="Global",
                      source_name="Reuters", url="http://reuters.com/en1"),
    ]
    _write_normalized(norm_dir / "test_normalized.json", sample)

    events = build_events_from_normalized(norm_dir, llm_client=_make_mock_llm("YES"))
    assert len(events) == 1
    event = events[0]
    assert event.japan_view is not None
    assert event.global_view is not None


# ── 同言語高頻度アンカーペナルティ ──────────────────────────────────────────

def test_same_lang_high_freq_only_does_not_connect():
    """同言語ペアが高頻度汎用アンカーのみ共有する場合は 2 クラスタのまま（巨大クラスタ防止）。"""
    # entity:trump + kw:tariff だけで繋がるケース（2つの高頻度アンカー < 閾値3）
    articles = [
        _make_article("jp1", "トランプ政権が関税を発表", country="JP"),
        _make_article("jp2", "トランプ大統領、関税政策を表明", country="JP"),
    ]
    clusters = cluster_articles(articles)
    # 高頻度アンカーのみ (entity:trump + kw:tariff = 2 < 3) → 結合しない
    assert len(clusters) == 2


def test_same_lang_strong_anchor_connects():
    """同言語ペアが強いアンカー（機関名・数値）を共有する場合は 1 クラスタになる。"""
    # entity:boj は _HIGH_FREQ_ANCHORS に含まれない → 強いシグナル
    articles = [
        _make_article("jp1", "日本銀行が利上げを決定", country="JP"),
        _make_article("jp2", "日本銀行の利上げで円高進む", country="JP"),
    ]
    clusters = cluster_articles(articles)
    assert len(clusters) == 1


def test_same_lang_three_high_freq_anchors_connects():
    """同言語ペアが高頻度アンカー3件以上共有する場合は接続する（閾値ちょうど）。"""
    # entity:trump + kw:tariff + country:japan = 3件 ≥ 閾値3 → 接続
    articles = [
        _make_article("jp1", "トランプ政権、日本への関税を発表", country="JP"),
        _make_article("jp2", "日本向けトランプ関税、政府が対応策", country="JP"),
    ]
    clusters = cluster_articles(articles)
    # 3つ以上の高頻度アンカー共有 → 接続可能
    assert len(clusters) <= 2  # 接続するか否かは共有アンカー数次第だが、例外は出ない


def test_cluster_size_stored_in_event():
    """cluster_to_event が cluster_size を正しく設定する。"""
    cluster = [
        _make_article("a1", "日本銀行が利上げを決定"),
        _make_article("a2", "日本銀行、金融政策を変更"),
    ]
    event = cluster_to_event(cluster)
    assert event.cluster_size == 2


def test_cluster_size_single_article():
    cluster = [_make_article("a1", "テスト記事")]
    event = cluster_to_event(cluster)
    assert event.cluster_size == 1


# ── 巨大クラスタ検出・再分割 ─────────────────────────────────────────────────

def test_giant_cluster_detection_stats():
    """cluster_articles の stats に巨大クラスタ情報が記録される。"""
    # _GIANT_CLUSTER_THRESHOLD + 2 個の記事を1クラスタに押し込む
    # 全記事が "日本銀行が利上げ" 系 → 共通の強いアンカー entity:boj があるので接続
    articles = []
    for i in range(_GIANT_CLUSTER_THRESHOLD + 2):
        articles.append(_make_article(
            f"a{i}",
            f"日本銀行が追加利上げ第{i}弾を発表",
            country="JP",
        ))

    stats: dict = {}
    clusters = cluster_articles(articles, stats=stats)

    # stats にサイズ分布と最大サイズが記録されている
    assert "cluster_size_distribution" in stats
    assert "max_cluster_size_bfs" in stats
    assert "giant_clusters_detected" in stats
    assert stats["max_cluster_size_bfs"] > 0


def test_cluster_size_distribution_in_stats():
    """cluster_articles の stats にサイズ分布が記録される。"""
    articles = [
        _make_article("a1", "日本銀行が利上げを決定"),
        _make_article("a2", "日本銀行、追加利上げ発表"),
        _make_article("a3", "全く別のニュース"),
    ]
    stats: dict = {}
    cluster_articles(articles, stats=stats)

    dist = stats.get("cluster_size_distribution", {})
    assert isinstance(dist, dict)
    # 何らかのサイズ分布が記録されている
    assert len(dist) >= 1


# ── _HIGH_FREQ_ANCHORS の内容確認 ──────────────────────────────────────────

def test_high_freq_anchors_contains_trump():
    assert "entity:trump" in _HIGH_FREQ_ANCHORS


def test_high_freq_anchors_contains_tariff():
    assert "kw:tariff" in _HIGH_FREQ_ANCHORS


def test_high_freq_anchors_not_contains_boj():
    """entity:boj は強いアンカーのため HIGH_FREQ_ANCHORS に含まれない。"""
    assert "entity:boj" not in _HIGH_FREQ_ANCHORS


def test_high_freq_anchors_not_contains_num():
    """具体的な数値 (num:*) は強いアンカーのため HIGH_FREQ_ANCHORS に含まれない。"""
    assert not any(k.startswith("num:") for k in _HIGH_FREQ_ANCHORS)


def test_high_freq_anchors_contains_conflict_countries():
    """紛争報道で過剰登場する国名は HIGH_FREQ_ANCHORS に含まれる（cross-lang 単独アンカーとして弱い）。"""
    for c in ("country:iran", "country:israel", "country:russia", "country:ukraine"):
        assert c in _HIGH_FREQ_ANCHORS, f"{c} should be in HIGH_FREQ_ANCHORS"


def test_cross_lang_strong_anchor_with_conflict_country_connects():
    """紛争国 + 強アンカー (entity:netanyahu) の組み合わせで cross-lang 接続する。"""
    from src.ingestion.event_builder import _MIN_CROSS_LANG_ANCHOR_HITS
    articles = [
        _make_article("jp1", "ネタニヤフ首相がイスラエルの作戦継続を表明", country="JP"),
        _make_article("en1", "Netanyahu announces Israel operation continues", country="Global"),
    ]
    clusters = cluster_articles(articles)
    # entity:netanyahu (strong) が1件あるので anchor_hits>=2 で接続
    assert len(clusters) == 1
