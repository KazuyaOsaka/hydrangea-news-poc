"""tts_to_captions (manual_poc) のフレーズ分割ロジックのテスト。

F-first-work-golden-master (1-S)。決定論変換 (LLM/API 非関与) のため mock 不要。
入力契約は ElevenLabs with-timestamps 応答の alignment 構造
(characters / character_start_times_seconds / character_end_times_seconds)。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "manual_poc" / "tts_to_captions.py"
)
_spec = importlib.util.spec_from_file_location("tts_to_captions", _MODULE_PATH)
tts_to_captions = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tts_to_captions)

alignment_to_captions = tts_to_captions.alignment_to_captions


def _alignment_from(text: str, sec_per_char: float = 0.1) -> dict:
    """等速タイミングの alignment フィクスチャを合成する。"""
    chars = list(text)
    return {
        "characters": chars,
        "character_start_times_seconds": [i * sec_per_char for i in range(len(chars))],
        "character_end_times_seconds": [(i + 1) * sec_per_char for i in range(len(chars))],
    }


def test_hard_break_splits_sentences():
    captions = alignment_to_captions(_alignment_from("これは一文目。これは二文目。"))
    assert [c["text"] for c in captions] == ["これは一文目。", "これは二文目。"]


def test_timestamps_cover_phrase_range():
    captions = alignment_to_captions(_alignment_from("あいう。えおか。"))
    first, second = captions
    assert first["startSec"] == 0.0
    assert first["endSec"] == pytest.approx(0.4)
    assert second["startSec"] == pytest.approx(0.4)
    assert second["endSec"] == pytest.approx(0.8)
    # 時系列順 + 重複なし
    assert first["endSec"] <= second["startSec"]


def test_long_sentence_split_at_soft_break():
    # 読点を含む 18 字超の文 → 読点で分割される
    text = "ながいながいまえおき、そのあとにつづくほんぶんがここにある。"
    captions = alignment_to_captions(_alignment_from(text), max_chars=18)
    assert len(captions) >= 2
    assert captions[0]["text"].endswith("、")
    assert "".join(c["text"] for c in captions) == text


def test_long_run_without_breaks_hard_wraps():
    text = "あ" * 40  # 句読点なし
    captions = alignment_to_captions(_alignment_from(text), max_chars=18)
    assert all(len(c["text"]) <= 18 for c in captions)
    assert "".join(c["text"] for c in captions) == text


def test_no_empty_captions_and_monotonic():
    text = "短い。とてもとてもとてもながいぶんしょうがつづく、さらにつづく。end."
    captions = alignment_to_captions(_alignment_from(text))
    assert all(c["text"].strip() for c in captions)
    for a, b in zip(captions, captions[1:]):
        assert a["startSec"] <= a["endSec"] <= b["startSec"] + 1e-6


def test_length_mismatch_raises():
    bad = {
        "characters": ["a", "b"],
        "character_start_times_seconds": [0.0],
        "character_end_times_seconds": [0.1, 0.2],
    }
    with pytest.raises(ValueError, match="length mismatch"):
        alignment_to_captions(bad)
