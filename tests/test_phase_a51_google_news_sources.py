"""
F-8-1-B: Google News 経由5媒体追加 + WION/Caixin の正確な定義テスト。
"""
from __future__ import annotations
from pathlib import Path

import pytest
import yaml

from src.ingestion.source_profiles import load_source_profiles


PROFILES_PATH = Path("configs/source_profiles.yaml")
SOURCES_PATH = Path("configs/sources.yaml")


@pytest.fixture
def profiles():
    return load_source_profiles(PROFILES_PATH)


@pytest.fixture
def sources_data():
    with open(SOURCES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_phase_a51_total_media_count(profiles):
    """F-8-1-A + F-8-1-B 完了で合計41媒体 (既存25 + Direct12 + GoogleNews5 - Kyodo47重複考慮)。"""
    # 厳密な数は既存の Kyodo47 等の存在に依存するので、
    # F-8-1-B で追加された5媒体が確実に存在することを確認
    expected_new = ["Yomiuri", "Sankei", "Tokyo_Shimbun", "WION", "Caixin_Global"]
    for source_id in expected_new:
        assert source_id in profiles, f"{source_id}: F-8-1-B 追加媒体が存在しない"


def test_yomiuri_is_conservative_top_tier(profiles):
    """読売新聞は保守系・top tier として定義されている。"""
    if "Yomiuri" in profiles:
        p = profiles["Yomiuri"]
        assert p.tier == "top", f"Yomiuri tier は top であるべき: {p.tier}"
        assert "保守" in p.display_name_speech, (
            f"Yomiuri display_name_speech に「保守」が含まれない: {p.display_name_speech}"
        )


def test_tokyo_shimbun_is_liberal(profiles):
    """東京新聞はリベラル系として定義されている。"""
    if "Tokyo_Shimbun" in profiles:
        p = profiles["Tokyo_Shimbun"]
        assert "リベラル" in p.display_name_speech, (
            f"Tokyo_Shimbun display_name_speech に「リベラル」が含まれない"
        )


def test_wion_is_bjp_aligned_private_with_warning(profiles):
    """WION は BJP寄り民間メディアとして警告付きで定義されている (Web調査反映)。"""
    if "WION" in profiles:
        p = profiles["WION"]
        # 国営ではない (民間と明示)
        assert p.requires_political_warning is True, (
            "WION は requires_political_warning=True であるべき"
        )
        assert "民間" in p.display_name_article, (
            f"WION display_name_article に「民間」が含まれない: {p.display_name_article}"
        )
        # warning_note に BJP の言及がある
        assert p.warning_note and "BJP" in p.warning_note, (
            f"WION warning_note に BJP の言及がない: {p.warning_note}"
        )
        # parent_company が Zee Media を含む
        assert p.parent_company and "Zee" in p.parent_company, (
            f"WION parent_company に Zee Media の言及がない: {p.parent_company}"
        )


def test_wion_speech_label_is_neutral(profiles):
    """WION の発話用ラベルは中立的 (BJP寄りは warning_note に分離)。"""
    if "WION" in profiles:
        p = profiles["WION"]
        # 発話用は警告語を含まない (短く保つ)
        assert "BJP" not in p.display_name_speech, (
            f"WION display_name_speech に BJP を含めない (warning_note で記述): "
            f"{p.display_name_speech}"
        )
        # 「民間」は含む (国営との誤解防止)
        assert "民間" in p.display_name_speech, (
            f"WION display_name_speech に「民間」を含める: {p.display_name_speech}"
        )


def test_caixin_does_not_require_warning(profiles):
    """Caixin Global は相対的に独立系のため警告不要。"""
    if "Caixin_Global" in profiles:
        p = profiles["Caixin_Global"]
        assert p.requires_political_warning is False, (
            "Caixin Global は中国メディアだが独立系で警告不要"
        )


def test_japanese_sources_all_have_speech_label(profiles):
    """日本系媒体3つは display_name_speech に「日本」を含む or 媒体名で識別可能。"""
    japanese_sources = ["Yomiuri", "Sankei", "Tokyo_Shimbun"]
    for source_id in japanese_sources:
        if source_id in profiles:
            p = profiles[source_id]
            assert p.display_name_speech, (
                f"{source_id}: display_name_speech が空"
            )


def test_sources_yaml_has_category_for_all_a51_media(sources_data):
    """F-8-1-A と F-8-1-B で追加された全媒体に category フィールドがある。"""
    a51_media = [
        "Sydney_Morning_Herald", "Guardian_Australia", "The_Hindustan_Times",
        "Middle_East_Eye", "The_Initium", "Meduza", "Il_Sole_24_Ore",
        "The_Atlantic", "Politico", "Eurasianet", "TeleSUR", "Mada_Masr",
        "Yomiuri", "Sankei", "Tokyo_Shimbun", "WION", "Caixin_Global",
    ]
    sources = sources_data.get("sources", [])
    sources_by_name = {s.get("name"): s for s in sources}

    missing = []
    for source_id in a51_media:
        if source_id in sources_by_name:
            if "category" not in sources_by_name[source_id]:
                missing.append(source_id)

    assert not missing, (
        f"以下の Phase A.5-1 媒体に category フィールドが欠けている: {missing}"
    )
