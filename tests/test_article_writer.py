"""Tests for src/generation/article_writer.py — 多地域ソース対応が中心。

回帰防止:
  article_writer は以前 event.sources_en だけを参照して「海外ソースあり / なし」を
  判定していた。sources_by_locale に middle_east 等の non-japan エントリがある
  イベントで、sources_en=[] でも海外ソース扱いになるべきケースを担保する。
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.generation.article_writer import (
    _build_article_fallback,
    _collect_overseas_sources,
    _evidence_warning_section,
    _has_overseas_sources,
)
from src.shared.models import NewsEvent, SourceRef


def _make_event(**overrides) -> NewsEvent:
    defaults = dict(
        id="ev-test",
        title="タイトル",
        summary="サマリ",
        category="economy",
        source="NHK",
        published_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return NewsEvent(**defaults)


def _jp_src(name: str = "NHK") -> SourceRef:
    return SourceRef(name=name, url=f"http://{name.lower()}.example/a", region="japan")


def _overseas_src(name: str, region: str = "middle_east") -> SourceRef:
    return SourceRef(name=name, url=f"http://{name.lower()}.example/b", region=region)


# ── _has_overseas_sources ─────────────────────────────────────────────────────


class TestHasOverseasSources:
    def test_sources_en_populated_returns_true(self):
        ev = _make_event(sources_en=[_overseas_src("Reuters", "global")])
        assert _has_overseas_sources(ev) is True

    def test_sources_by_locale_non_japan_returns_true(self):
        """sources_en が空でも sources_by_locale に non-japan があれば overseas 扱い。"""
        ev = _make_event(
            sources_jp=[_jp_src()],
            sources_by_locale={
                "japan": [_jp_src()],
                "middle_east": [_overseas_src("AlJazeera", "middle_east")],
            },
        )
        assert _has_overseas_sources(ev) is True

    def test_jp_only_returns_false(self):
        ev = _make_event(
            sources_jp=[_jp_src()],
            sources_by_locale={"japan": [_jp_src()]},
        )
        assert _has_overseas_sources(ev) is False

    def test_empty_event_returns_false(self):
        ev = _make_event()
        assert _has_overseas_sources(ev) is False


# ── _collect_overseas_sources ─────────────────────────────────────────────────


class TestCollectOverseasSources:
    def test_sources_en_preferred_when_present(self):
        ev = _make_event(sources_en=[_overseas_src("Reuters", "global")])
        refs = _collect_overseas_sources(ev)
        assert len(refs) == 1
        assert refs[0].name == "Reuters"

    def test_falls_back_to_sources_by_locale(self):
        """sources_en が空なら sources_by_locale の non-japan 全件を返す。"""
        ev = _make_event(
            sources_jp=[_jp_src()],
            sources_by_locale={
                "japan": [_jp_src()],
                "middle_east": [_overseas_src("AlJazeera", "middle_east")],
                "global_south": [_overseas_src("News24", "global_south")],
            },
        )
        refs = _collect_overseas_sources(ev)
        names = sorted(r.name for r in refs)
        assert names == ["AlJazeera", "News24"], f"got {names}"

    def test_returns_empty_when_jp_only(self):
        ev = _make_event(sources_jp=[_jp_src()])
        assert _collect_overseas_sources(ev) == []

    def test_deduplicates_by_url(self):
        same_url = "http://dup.example/x"
        ev = _make_event(
            sources_by_locale={
                "middle_east": [SourceRef(name="A", url=same_url, region="middle_east")],
                "europe": [SourceRef(name="A", url=same_url, region="europe")],
            },
        )
        refs = _collect_overseas_sources(ev)
        assert len(refs) == 1


# ── _evidence_warning_section: 多地域対応 ──────────────────────────────────────


class TestEvidenceWarningMultiLocale:
    def test_locale_overseas_skips_en_absent_warning(self):
        """sources_en=[] でも sources_by_locale に non-japan があれば EN-absent にならない。"""
        ev = _make_event(
            sources_jp=[_jp_src()],
            sources_by_locale={
                "japan": [_jp_src()],
                "middle_east": [_overseas_src("AlJazeera")],
            },
            gap_reasoning="日本と中東で論点が違う",
            impact_on_japan="エネルギー価格への波及が見込まれる",
        )
        warning = _evidence_warning_section(ev, None)
        assert "EN-sources-absent" not in warning, (
            "多地域 non-japan ソースがあるなら EN-absent 警告は出してはいけない"
        )

    def test_jp_only_still_triggers_en_absent(self):
        ev = _make_event(
            sources_jp=[_jp_src()],
            sources_by_locale={"japan": [_jp_src()]},
        )
        warning = _evidence_warning_section(ev, None)
        assert "EN-sources-absent" in warning


# ── _build_article_fallback: Sources 欄に多地域ソースが入る ────────────────────


class TestFallbackSourcesSection:
    def test_sources_section_includes_locale_overseas(self):
        ev = _make_event(
            sources_jp=[_jp_src("NHK")],
            sources_by_locale={
                "japan": [_jp_src("NHK")],
                "middle_east": [_overseas_src("AlJazeera", "middle_east")],
                "europe": [_overseas_src("Guardian", "europe")],
            },
            gap_reasoning="JP と中東で視点が違う",
            impact_on_japan="エネルギー価格への影響が見込まれる",
        )
        article = _build_article_fallback(ev)
        md = article.markdown
        assert "NHK" in md
        assert "AlJazeera" in md, "Sources セクションに AlJazeera を含めること"
        assert "Guardian" in md, "Sources セクションに Guardian を含めること"
        # 海外メディア見出しも入る
        assert "**海外メディア**" in md
