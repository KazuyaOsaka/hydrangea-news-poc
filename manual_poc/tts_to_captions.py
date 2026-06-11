#!/usr/bin/env python3
"""ElevenLabs with-timestamps 応答 → Remotion 字幕 JSON 変換。

F-first-work-golden-master (1-S)。手動 PoC で ElevenLabs TTS を実行した後、
本スクリプトで Remotion テンプレート (manual_poc/remotion) の captions 契約
`[{"text": str, "startSec": float, "endSec": float}, ...]` に変換する。

入力契約 (一次ソース: ElevenLabs API docs
https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps
2026-06-11 確認):
    POST /v1/text-to-speech/{voice_id}/with-timestamps の応答 JSON
    - audio_base64: base64 エンコードされた音声
    - alignment: {characters: [str], character_start_times_seconds: [float],
                  character_end_times_seconds: [float]}
    - normalized_alignment: 同構造 (正規化テキスト基準)

フレーズ分割 (設計正典: 字幕は単語/フレーズレベル同期、1〜2 行、抑制スタイル):
    句読点 (。．！？!?…) で必ず区切り、読点 (、) は最大長超過時のみ区切る。
    1 フレーズ最大 --max-chars 文字 (default 18 = 字幕帯 1〜2 行)。

使い方:
    python manual_poc/tts_to_captions.py response.json \
        --captions-out manual_poc/remotion/public/assets/captions.json \
        --audio-out manual_poc/remotion/public/assets/narration.mp3

API キーは不要 (保存済み応答 JSON の変換のみ)。TTS 実行自体は手動 PoC
(docs/golden_master_spec.md チェックリスト参照)。
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

# 必ず区切る文末記号 / 超過時のみ区切る弱い境界
_HARD_BREAKS = set("。．！？!?…")
_SOFT_BREAKS = set("、,")
DEFAULT_MAX_CHARS = 18


def alignment_to_captions(
    alignment: dict, *, max_chars: int = DEFAULT_MAX_CHARS
) -> list[dict]:
    """character-level alignment をフレーズ単位の captions に変換する。

    Args:
        alignment: characters / character_start_times_seconds /
                   character_end_times_seconds の 3 配列 (同長)。
        max_chars: 1 フレーズの最大文字数 (空白除去後)。

    Returns:
        [{"text": str, "startSec": float, "endSec": float}, ...] (時系列順)
    """
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    if not (len(chars) == len(starts) == len(ends)):
        raise ValueError(
            f"alignment arrays length mismatch: chars={len(chars)} "
            f"starts={len(starts)} ends={len(ends)}"
        )

    captions: list[dict] = []
    buf: list[str] = []
    buf_start: float | None = None
    buf_end: float = 0.0
    last_soft_idx: int | None = None  # buf 内の弱い境界位置 (境界文字の次)

    def _flush(upto: int | None = None) -> None:
        nonlocal buf, buf_start, buf_end, last_soft_idx
        if not buf:
            return
        cut = len(buf) if upto is None else upto
        text = "".join(buf[:cut]).strip()
        rest = buf[cut:]
        if text:
            captions.append(
                {
                    "text": text,
                    "startSec": round(buf_start or 0.0, 3),
                    "endSec": round(buf_end, 3),
                }
            )
        buf = rest
        buf_start = None if not rest else buf_start  # rest の開始時刻は次の文字で補正
        last_soft_idx = None

    rest_start: float | None = None
    for i, ch in enumerate(chars):
        if buf_start is None and not ch.isspace():
            buf_start = rest_start if rest_start is not None else float(starts[i])
            rest_start = None
        if ch == "\n" or ch.isspace() and not buf:
            continue
        buf.append(ch)
        buf_end = float(ends[i])
        if ch in _HARD_BREAKS:
            _flush()
            continue
        if ch in _SOFT_BREAKS:
            last_soft_idx = len(buf)
        visible_len = len("".join(buf).strip())
        if visible_len >= max_chars:
            if last_soft_idx is not None:
                # 弱い境界で割る。残りの開始時刻は概算 (境界文字の終了時刻)
                rest_start = buf_end
                _flush(last_soft_idx)
                if buf and buf_start is None:
                    buf_start = rest_start
                    rest_start = None
            else:
                _flush()
    _flush()
    return captions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("response_json", help="with-timestamps 応答 JSON のパス")
    parser.add_argument(
        "--captions-out", required=True, help="captions JSON の出力先"
    )
    parser.add_argument(
        "--audio-out", default=None, help="audio_base64 をデコードして保存 (任意)"
    )
    parser.add_argument(
        "--max-chars", type=int, default=DEFAULT_MAX_CHARS, help="1 フレーズ最大文字数"
    )
    parser.add_argument(
        "--use-normalized",
        action="store_true",
        help="normalized_alignment を使う (default は alignment)",
    )
    args = parser.parse_args()

    data = json.loads(Path(args.response_json).read_text(encoding="utf-8"))
    key = "normalized_alignment" if args.use_normalized else "alignment"
    alignment = data.get(key)
    if not alignment:
        raise SystemExit(f"response JSON has no {key!r}")

    captions = alignment_to_captions(alignment, max_chars=args.max_chars)
    out = Path(args.captions_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(captions, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[tts_to_captions] {len(captions)} captions → {out}")

    if args.audio_out and data.get("audio_base64"):
        audio_path = Path(args.audio_out)
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(base64.b64decode(data["audio_base64"]))
        print(f"[tts_to_captions] audio → {audio_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
