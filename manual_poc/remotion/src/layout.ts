/**
 * Hydrangea 第一作 — レイアウト定数 (設計正典 2026-06-10/11、DECISION_LOG 参照)。
 *
 * セーフゾーン中央帯の「動く紙面」: 1080×1920。上部 250px (ユーザー名/音源 UI) と
 * 下部 320px (説明/CTA/ボタン UI) には重要要素を置かない。右端も UI が重い
 * (特に TikTok)。全画面没入型は UGC の文法であり採らない。
 */

export const FRAME_WIDTH = 1080;
export const FRAME_HEIGHT = 1920;
export const FPS = 30;

// ── セーフゾーン ────────────────────────────────────────────────
export const SAFE_TOP = 250; // ユーザー名 / 音源 UI
export const SAFE_BOTTOM = 320; // 説明 / CTA / ボタン UI
export const SAFE_RIGHT = 110; // 右端 UI (いいね/コメント列、特に TikTok)
export const SAFE_LEFT = 60;

// ── 紙面 3 帯 (コンテンツ領域 y = [SAFE_TOP, FRAME_HEIGHT - SAFE_BOTTOM]) ──
export const HEADER_BAND = { top: SAFE_TOP, height: 190 } as const;
export const VISUAL_BAND = { top: SAFE_TOP + 190, height: 760 } as const;
export const CAPTION_BAND = {
  top: SAFE_TOP + 190 + 760,
  height: FRAME_HEIGHT - SAFE_BOTTOM - (SAFE_TOP + 190 + 760), // = 400
} as const;

// ── ブランドパレット (ADR-0001、5 色) ───────────────────────────
export const COLORS = {
  base: '#0A0A0A', // near black
  text: '#F5F5F0', // off-white (本文・数字)
  accent: '#4A6FA5', // hydrangea blue (主アクセント)
  warn: '#A04848', // muted red (限定使用、常用禁止)
  grey: '#808080', // 出典・補足
} as const;

// ── フックカード (第1フレーム = サムネ = カバーの三役) ──────────
export const HOOK_CARD_SEC = 2;

// ── BGM ducking ─────────────────────────────────────────────────
export const BGM_VOLUME_DUCKED = 0.12; // ナレーション中
export const BGM_VOLUME_FULL = 0.35; // ナレーション外
