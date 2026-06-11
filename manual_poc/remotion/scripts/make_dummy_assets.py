#!/usr/bin/env python3
"""ダミー素材生成 (標準ライブラリのみ、Pillow / ffmpeg 不要)。

public/dummy/ に以下を生成する:
- plate_hook.png / plate_setup.png / plate_twist.png / plate_punchline.png (1024x1024)
- plate_hook_card.png (1080x1920)
- narration.wav (20s、控えめなトーン) / bgm.wav (20s、低音ループ用)

ダミーレンダ (`npm run render:dummy`) の入力。実素材の組み込みは手動 PoC
(docs/golden_master_spec.md のチェックリスト参照)。
"""
from __future__ import annotations

import math
import struct
import wave
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "public" / "dummy"

# ADR-0001 パレット (ダミープレートもブランドトーンで)
BASE = (10, 10, 10)
TEXT = (245, 245, 240)
ACCENT = (74, 111, 165)
GREY = (128, 128, 128)


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    raw = tag + data
    return struct.pack(">I", len(data)) + raw + struct.pack(">I", zlib.crc32(raw))


def write_png(path: Path, width: int, height: int, pixel_fn) -> None:
    """pixel_fn(x, y) -> (r, g, b) で PNG を書き出す。"""
    rows = bytearray()
    for y in range(height):
        rows.append(0)  # filter: None
        for x in range(width):
            rows.extend(pixel_fn(x, y))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(png)
    print(f"wrote {path} ({width}x{height})")


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make_plate(path: Path, size: int, accent_band: float) -> None:
    """near-black 地に対角グラデ + アクセント帯のダミープレート。"""

    def px(x, y):
        t = (x + y) / (2 * size)
        c = _lerp(BASE, (30, 38, 52), t)
        # アクセント斜め帯
        d = abs((x - y) / size - accent_band)
        if d < 0.04:
            c = _lerp(c, ACCENT, 0.8)
        elif d < 0.08:
            c = _lerp(c, ACCENT, 0.3)
        # グリッドドット (インフォグラフィック風)
        if x % 128 < 3 and y % 128 < 3:
            c = GREY
        return c

    write_png(path, size, size, px)


def make_hook_card(path: Path) -> None:
    """9:16 フックカード: 上 1/3 にモチーフ、中央帯は余白 (文字後乗せ用)。"""
    w, h = 1080, 1920

    def px(x, y):
        t = y / h
        c = _lerp((26, 32, 44), BASE, min(1.0, t * 1.6))
        # 上 1/3: 縦バー (監獄ゲートの抽象、ダミー)
        if y < 640 and 140 <= x <= 940 and (x - 140) % 100 < 18 and 120 < y:
            c = _lerp(c, TEXT, 0.55)
        # アクセント水平ライン
        if 660 <= y <= 668:
            c = ACCENT
        return c

    write_png(path, w, h, px)


def write_wav(path: Path, seconds: float, freq: float, volume: float) -> None:
    rate = 22050
    n = int(rate * seconds)
    with wave.open(str(path), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        frames = bytearray()
        for i in range(n):
            t = i / rate
            # 端をフェードしてクリックノイズ回避
            env = min(1.0, t / 0.5, (seconds - t) / 0.5)
            sample = volume * env * math.sin(2 * math.pi * freq * t)
            # ゆっくりした振幅揺らぎ (単調トーン緩和)
            sample *= 0.7 + 0.3 * math.sin(2 * math.pi * 0.25 * t)
            frames += struct.pack("<h", int(sample * 32767))
        f.writeframes(bytes(frames))
    print(f"wrote {path} ({seconds}s)")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    make_plate(OUT / "plate_hook.png", 1024, 0.0)
    make_plate(OUT / "plate_setup.png", 1024, 0.3)
    make_plate(OUT / "plate_twist.png", 1024, -0.3)
    make_plate(OUT / "plate_punchline.png", 1024, 0.6)
    make_hook_card(OUT / "plate_hook_card.png")
    write_wav(OUT / "narration.wav", 20.0, 220.0, 0.18)
    write_wav(OUT / "bgm.wav", 20.0, 110.0, 0.30)
    print("dummy assets done.")


if __name__ == "__main__":
    main()
