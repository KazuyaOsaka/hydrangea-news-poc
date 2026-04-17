"""ingestion モジュール (rss_fetcher / normalizer) のテスト。
ネットワークアクセスは発生しない（feedparser.parse をモック）。
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.normalizer import normalize_all, normalize_item, normalize_raw_file
from src.ingestion.rss_fetcher import fetch_all, load_sources


# ─────────────────────────────────────────────────────────────────────────────
# load_sources
# ─────────────────────────────────────────────────────────────────────────────

YAML_TWO_SOURCES = """\
sources:
  - country: JP
    name: NHK
    category: general
    rss_url: https://example.com/nhk.rss
    priority: 1
    enabled: true
  - country: JP
    name: Disabled
    category: general
    rss_url: https://example.com/disabled.rss
    priority: 2
    enabled: false
"""

YAML_ONE_GLOBAL = """\
sources:
  - country: Global
    name: Reuters
    category: general
    rss_url: https://example.com/reuters.rss
    priority: 1
    enabled: true
"""


def test_load_sources_returns_enabled_only(tmp_path):
    p = tmp_path / "sources.yaml"
    p.write_text(YAML_TWO_SOURCES)
    sources = load_sources(p)
    assert len(sources) == 1
    assert sources[0]["name"] == "NHK"


def test_load_sources_all_fields_present(tmp_path):
    p = tmp_path / "sources.yaml"
    p.write_text(YAML_ONE_GLOBAL)
    sources = load_sources(p)
    src = sources[0]
    assert src["country"] == "Global"
    assert src["name"] == "Reuters"
    assert src["rss_url"] == "https://example.com/reuters.rss"
    assert src["priority"] == 1
    assert src["enabled"] is True


def test_load_sources_skips_disabled(tmp_path):
    p = tmp_path / "sources.yaml"
    p.write_text(YAML_TWO_SOURCES)
    sources = load_sources(p)
    names = [s["name"] for s in sources]
    assert "Disabled" not in names


# ─────────────────────────────────────────────────────────────────────────────
# normalize_item
# ─────────────────────────────────────────────────────────────────────────────

BASE_META = {
    "source_name": "NHK",
    "country": "JP",
    "category": "general",
    "fetched_at": "2026-03-31T14:00:00+00:00",
}


def test_normalize_item_basic_fields():
    entry = {
        "title": "Test Article",
        "summary": "A test summary.",
        "link": "https://example.com/article/1",
        "published": "Mon, 31 Mar 2026 12:00:00 +0000",
    }
    item = normalize_item(entry, BASE_META)
    assert item["title"] == "Test Article"
    assert item["summary"] == "A test summary."
    assert item["url"] == "https://example.com/article/1"
    assert item["source_name"] == "NHK"
    assert item["country"] == "JP"
    assert item["category"] == "general"
    assert item["id"].startswith("art-")
    assert "published_at" in item
    assert item["fetched_at"] == BASE_META["fetched_at"]


def test_normalize_item_same_url_produces_same_id():
    entry1 = {"title": "A", "link": "https://example.com/1", "summary": ""}
    entry2 = {"title": "B", "link": "https://example.com/1", "summary": ""}
    id1 = normalize_item(entry1, BASE_META)["id"]
    id2 = normalize_item(entry2, BASE_META)["id"]
    assert id1 == id2


def test_normalize_item_different_urls_produce_different_ids():
    entry1 = {"title": "A", "link": "https://example.com/1", "summary": ""}
    entry2 = {"title": "B", "link": "https://example.com/2", "summary": ""}
    id1 = normalize_item(entry1, BASE_META)["id"]
    id2 = normalize_item(entry2, BASE_META)["id"]
    assert id1 != id2


def test_normalize_item_missing_published_falls_back():
    entry = {"title": "X", "link": "https://example.com/x", "summary": ""}
    item = normalize_item(entry, BASE_META)
    assert "published_at" in item
    assert item["published_at"]  # not empty


def test_normalize_item_tags_extracted():
    entry = {
        "title": "Tagged",
        "link": "https://example.com/t",
        "summary": "",
        "tags": [{"term": "economy"}, {"term": "japan"}],
    }
    item = normalize_item(entry, BASE_META)
    assert "economy" in item["tags"]
    assert "japan" in item["tags"]


def test_normalize_item_html_stripped_from_summary():
    entry = {
        "title": "<b>Bold Title</b>",
        "link": "https://example.com/html",
        "summary": "<p>Some <em>text</em> here</p>",
    }
    item = normalize_item(entry, BASE_META)
    assert "<" not in item["title"]
    assert "<" not in item["summary"]
    assert "text" in item["summary"]


def test_normalize_item_raw_ref_stored():
    entry = {"title": "X", "link": "https://example.com/x", "summary": ""}
    item = normalize_item(entry, BASE_META, raw_ref="data/raw/nhk_20260331.json")
    assert item["raw_ref"] == "data/raw/nhk_20260331.json"


# ─────────────────────────────────────────────────────────────────────────────
# normalize_raw_file
# ─────────────────────────────────────────────────────────────────────────────

def _write_raw(path: Path, entries: list[dict]) -> None:
    raw = {
        "source_name": "BBC",
        "country": "Global",
        "category": "general",
        "rss_url": "https://example.com/bbc.rss",
        "fetched_at": "2026-03-31T14:00:00+00:00",
        "feed_title": "BBC News",
        "entries": entries,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, ensure_ascii=False))


def test_normalize_raw_file_creates_output(tmp_path):
    raw_path = tmp_path / "raw" / "bbc_20260331_140000.json"
    _write_raw(raw_path, [
        {"title": "Article 1", "link": "https://bbc.com/1", "summary": "S1",
         "published": "Mon, 31 Mar 2026 10:00:00 +0000"},
        {"title": "Article 2", "link": "https://bbc.com/2", "summary": "S2"},
    ])
    norm_dir = tmp_path / "normalized"
    out = normalize_raw_file(raw_path, norm_dir)
    assert out.exists()
    items = json.loads(out.read_text())
    assert len(items) == 2
    assert items[0]["source_name"] == "BBC"
    assert items[0]["title"] == "Article 1"


def test_normalize_raw_file_empty_entries(tmp_path):
    raw_path = tmp_path / "raw" / "empty_20260331.json"
    _write_raw(raw_path, [])
    out = normalize_raw_file(raw_path, tmp_path / "normalized")
    items = json.loads(out.read_text())
    assert items == []


# ─────────────────────────────────────────────────────────────────────────────
# normalize_all
# ─────────────────────────────────────────────────────────────────────────────

def test_normalize_all_processes_multiple_files(tmp_path):
    raw_dir = tmp_path / "raw"
    norm_dir = tmp_path / "normalized"
    for name in ["nhk_20260331.json", "bbc_20260331.json"]:
        _write_raw(raw_dir / name, [{"title": "T", "link": f"https://ex.com/{name}", "summary": ""}])
    results = normalize_all(raw_dir, norm_dir)
    assert len(results) == 2
    assert all(p.exists() for p in results)


def test_normalize_all_returns_empty_when_raw_dir_missing(tmp_path):
    result = normalize_all(tmp_path / "nonexistent", tmp_path / "normalized")
    assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# fetch_all (feedparser をモック)
# ─────────────────────────────────────────────────────────────────────────────

YAML_SINGLE_ENABLED = """\
sources:
  - country: JP
    name: NHK
    category: general
    rss_url: https://example.com/nhk.rss
    priority: 1
    enabled: true
"""

YAML_SINGLE_DISABLED = """\
sources:
  - country: JP
    name: Disabled
    category: general
    rss_url: https://example.com/disabled.rss
    priority: 1
    enabled: false
"""


def _make_mock_feed(entries: list[dict] | None = None) -> MagicMock:
    mock = MagicMock()
    mock.feed.get = MagicMock(return_value="Mock Feed Title")
    mock.entries = entries or []
    return mock


@patch("src.ingestion.rss_fetcher.feedparser.parse")
def test_fetch_all_saves_raw_json(mock_parse, tmp_path):
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(YAML_SINGLE_ENABLED)
    mock_parse.return_value = _make_mock_feed()

    paths = fetch_all(sources_path, tmp_path / "raw")
    assert len(paths) == 1
    assert paths[0].exists()

    data = json.loads(paths[0].read_text())
    assert data["source_name"] == "NHK"
    assert data["country"] == "JP"
    assert data["category"] == "general"
    assert "fetched_at" in data
    assert isinstance(data["entries"], list)


@patch("src.ingestion.rss_fetcher.feedparser.parse")
def test_fetch_all_skips_disabled_sources(mock_parse, tmp_path):
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(YAML_SINGLE_DISABLED)

    paths = fetch_all(sources_path, tmp_path / "raw")
    assert len(paths) == 0
    mock_parse.assert_not_called()


@patch("src.ingestion.rss_fetcher.feedparser.parse")
def test_fetch_all_with_entries(mock_parse, tmp_path):
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(YAML_SINGLE_ENABLED)

    fake_entry = {
        "title": "日銀が利上げ",
        "summary": "概要テスト",
        "link": "https://nhk.or.jp/1",
        "published": "Mon, 31 Mar 2026 09:00:00 +0000",
        "tags": [{"term": "economy"}],
        "published_parsed": None,
    }
    mock_feed = _make_mock_feed([fake_entry])
    # feedparser entry は get() を持つ dict-like オブジェクト
    # ここでは plain dict を渡して _serialize_entry の動作を確認
    mock_parse.return_value = mock_feed

    paths = fetch_all(sources_path, tmp_path / "raw")
    data = json.loads(paths[0].read_text())
    assert len(data["entries"]) == 1
    assert data["entries"][0]["title"] == "日銀が利上げ"


@patch("src.ingestion.rss_fetcher.feedparser.parse")
def test_fetch_all_continues_on_error(mock_parse, tmp_path):
    """1 ソースでエラーが起きても他のソースは処理される。"""
    yaml_two = """\
sources:
  - country: JP
    name: ErrorSource
    category: general
    rss_url: https://example.com/error.rss
    priority: 1
    enabled: true
  - country: Global
    name: BBC
    category: general
    rss_url: https://example.com/bbc.rss
    priority: 2
    enabled: true
"""
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(yaml_two)

    def side_effect(url):
        if "error" in url:
            raise ConnectionError("Network error")
        return _make_mock_feed()

    mock_parse.side_effect = side_effect

    paths = fetch_all(sources_path, tmp_path / "raw")
    # エラーが起きたソースも空 entries で保存される
    assert len(paths) == 2
