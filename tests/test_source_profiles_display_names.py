"""
F-8-1-A: source_profiles.yaml の display_name 3フィールドの整合性テスト。
"""
from __future__ import annotations
import pytest
from pathlib import Path

from src.ingestion.source_profiles import load_source_profiles


PROFILES_PATH = Path("configs/source_profiles.yaml")


@pytest.fixture
def profiles():
    return load_source_profiles(PROFILES_PATH)


def test_all_profiles_have_display_name_speech(profiles):
    """全媒体に display_name_speech が定義されている。"""
    for source_id, profile in profiles.items():
        assert profile.display_name_speech, (
            f"{source_id}: display_name_speech が空"
        )


def test_all_profiles_have_display_name_article(profiles):
    """全媒体に display_name_article が定義されている。"""
    for source_id, profile in profiles.items():
        assert profile.display_name_article, (
            f"{source_id}: display_name_article が空"
        )


def test_all_profiles_have_display_name_subtitle(profiles):
    """全媒体に display_name_subtitle が定義されている。"""
    for source_id, profile in profiles.items():
        assert profile.display_name_subtitle, (
            f"{source_id}: display_name_subtitle が空"
        )


def test_speech_name_contains_no_punctuation(profiles):
    """発話用は記号を含まない (TTSで読みやすい)。"""
    for source_id, profile in profiles.items():
        # 「・」「(」「)」は許容 (発話可能)
        # 「/」「\」は不可
        assert "/" not in profile.display_name_speech, (
            f"{source_id}: display_name_speech にスラッシュ"
        )
        assert "\\" not in profile.display_name_speech, (
            f"{source_id}: display_name_speech にバックスラッシュ"
        )


def test_tier_3_has_political_warning(profiles):
    """Tier 3 警告付き媒体は requires_political_warning=True。"""
    tier_3_media = ["TeleSUR", "Mada_Masr"]
    for source_id in tier_3_media:
        if source_id in profiles:
            assert profiles[source_id].requires_political_warning, (
                f"{source_id}: Tier 3 だが requires_political_warning=False"
            )


def test_tier_3_has_warning_note(profiles):
    """Tier 3 警告付き媒体は warning_note が設定されている。"""
    tier_3_media = ["TeleSUR", "Mada_Masr"]
    for source_id in tier_3_media:
        if source_id in profiles:
            assert profiles[source_id].warning_note, (
                f"{source_id}: Tier 3 だが warning_note が空"
            )
            # warning_note は最低30文字以上 (具体的な指針が含まれていることを担保)
            assert len(profiles[source_id].warning_note) >= 30, (
                f"{source_id}: warning_note が短すぎる "
                f"({len(profiles[source_id].warning_note)} chars)"
            )


def test_telesur_state_aligned(profiles):
    """TeleSUR は state_aligned=True で出資国が記録されている。"""
    if "TeleSUR" in profiles:
        assert profiles["TeleSUR"].state_aligned is True, (
            "TeleSUR: state_aligned=True であるべき"
        )
        funding = profiles["TeleSUR"].funding_sources or []
        assert "venezuela_government" in funding, (
            "TeleSUR: funding_sources に venezuela_government がない"
        )


def test_existing_media_no_political_warning(profiles):
    """既存25媒体は requires_political_warning=False (Tier 3 でないため)。"""
    existing_media = [
        "NHK", "NHK_Politics", "NHK_Economy", "Nikkei", "Asahi",
        "Reuters", "APNews", "BBC", "Bloomberg", "FinancialTimes",
        "AlJazeera", "France24", "CNA", "TheGuardian", "LeMonde",
        "DerSpiegel", "ElPais", "Yonhap", "StraitsTimes", "TimesOfIndia",
        "ABCNewsAU", "News24", "NYTWorld", "FolhaDeSPaulo", "BuenosAiresTimes",
    ]
    for source_id in existing_media:
        if source_id in profiles:
            assert not profiles[source_id].requires_political_warning, (
                f"{source_id}: 既存媒体だが requires_political_warning=True"
            )


def test_subtitle_is_brand_name(profiles):
    """字幕用は原語ブランド名 (日本語のみは可、ただし長すぎない)。"""
    for source_id, profile in profiles.items():
        assert len(profile.display_name_subtitle) <= 30, (
            f"{source_id}: display_name_subtitle が長すぎる "
            f"({len(profile.display_name_subtitle)} chars)"
        )


def test_added_media_count(profiles):
    """F-8-1-A で12媒体が追加されている (10 Tier1 + 2 Tier3)。"""
    new_media = [
        "Sydney_Morning_Herald", "Guardian_Australia",
        "The_Hindustan_Times", "Middle_East_Eye",
        "The_Initium", "Meduza",
        "Il_Sole_24_Ore", "The_Atlantic", "Politico",
        "Eurasianet", "TeleSUR", "Mada_Masr",
    ]
    found = [m for m in new_media if m in profiles]
    assert len(found) == 12, (
        f"F-8-1-A 追加媒体が一部欠けている: 期待=12, 実際={len(found)}, "
        f"見つかったもの={found}"
    )


def test_telesur_speech_contains_government(profiles):
    """TeleSUR の発話用ラベルに「政府」「国営」等の語が含まれる
    (独立メディアと誤読されないことを担保)。"""
    if "TeleSUR" in profiles:
        speech = profiles["TeleSUR"].display_name_speech
        assert any(kw in speech for kw in ["政府", "国営"]), (
            f"TeleSUR: display_name_speech に「政府」「国営」が含まれない: '{speech}'"
        )


def test_meduza_speech_contains_independent(profiles):
    """Meduza の発話用ラベルに「独立」が含まれる。"""
    if "Meduza" in profiles:
        speech = profiles["Meduza"].display_name_speech
        assert "独立" in speech, (
            f"Meduza: display_name_speech に「独立」が含まれない: '{speech}'"
        )


def test_mada_masr_speech_contains_independent(profiles):
    """Mada_Masr の発話用ラベルに「独立」が含まれる。"""
    if "Mada_Masr" in profiles:
        speech = profiles["Mada_Masr"].display_name_speech
        assert "独立" in speech, (
            f"Mada_Masr: display_name_speech に「独立」が含まれない: '{speech}'"
        )
