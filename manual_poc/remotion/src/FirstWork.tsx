/**
 * Hydrangea 第一作テンプレート — セーフゾーン中央帯の「動く紙面」。
 *
 * 構造 (設計正典 2026-06-10/11):
 *   - ヘッダー帯: platform_title (常時、タイポはコードで描く)
 *   - 中央ビジュアル帯: 1:1 プレート + Ken Burns パン・ズーム + クロスフェード
 *   - 字幕帯: burned-in、タイムスタンプ駆動のフレーズ同期、抑制スタイル
 *   - frame 0〜2 秒: フックカード (thumbnail_text + 9:16 プレート) =
 *     ①フィード最初の1秒 ②Shorts サムネフレーム ③TikTok カバーの三役
 *   - BGM: ナレーション中は ducking
 *
 * アニメーションは全て useCurrentFrame + interpolate (CSS transition 禁止 =
 * Remotion 公式 Agent Skill の指針に従う)。
 */
import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {
  BGM_VOLUME_DUCKED,
  BGM_VOLUME_FULL,
  CAPTION_BAND,
  COLORS,
  HEADER_BAND,
  HOOK_CARD_SEC,
  SAFE_LEFT,
  SAFE_RIGHT,
  VISUAL_BAND,
} from './layout';
import type {CaptionInput, FirstWorkProps, SceneInput} from './types';

const CROSSFADE_SEC = 0.5;

// ── ヘッダー帯 (紙面の題字) ──────────────────────────────────────
const HeaderBand: React.FC<{title: string}> = ({title}) => (
  <div
    style={{
      position: 'absolute',
      top: HEADER_BAND.top,
      left: SAFE_LEFT,
      width: 1080 - SAFE_LEFT - SAFE_RIGHT,
      height: HEADER_BAND.height,
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
    }}
  >
    <div style={{width: 64, height: 6, backgroundColor: COLORS.accent, marginBottom: 18}} />
    <div
      style={{
        color: COLORS.text,
        fontFamily: 'Hiragino Sans, "Noto Sans JP", sans-serif',
        fontWeight: 700,
        fontSize: 44,
        lineHeight: 1.25,
      }}
    >
      {title}
    </div>
  </div>
);

// ── 中央ビジュアル帯 (Ken Burns + クロスフェード) ────────────────
const ScenePlate: React.FC<{
  scene: SceneInput;
  index: number;
  durationInFrames: number;
}> = ({scene, index, durationInFrames}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // Ken Burns: シーンごとに方向を交互に。1:1 プレートを帯より大きく描き、
  // scale + translate で「紙面の中の写真がゆっくり動く」量に抑制する。
  const progress = Math.min(1, frame / durationInFrames);
  const scale = interpolate(progress, [0, 1], [1.06, 1.16]);
  const direction = index % 2 === 0 ? 1 : -1;
  const translateX = interpolate(progress, [0, 1], [0, direction * -36]);
  const translateY = interpolate(progress, [0, 1], [0, direction * 22]);

  // クロスフェード (in/out)
  const fadeFrames = CROSSFADE_SEC * fps;
  const opacity = interpolate(
    frame,
    [0, fadeFrames, durationInFrames - fadeFrames, durationInFrames],
    [index === 0 ? 1 : 0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
  );

  return (
    <div
      style={{
        position: 'absolute',
        top: VISUAL_BAND.top,
        left: 0,
        width: 1080,
        height: VISUAL_BAND.height,
        overflow: 'hidden',
        opacity,
      }}
    >
      <Img
        src={staticFile(scene.image)}
        style={{
          position: 'absolute',
          width: 1080,
          height: 1080, // 1:1 プレートを幅基準で置き、帯が中央をクロップする
          top: (VISUAL_BAND.height - 1080) / 2,
          transform: `scale(${scale}) translate(${translateX}px, ${translateY}px)`,
        }}
      />
    </div>
  );
};

// ── 字幕帯 (タイムスタンプ駆動、抑制スタイル) ────────────────────
const CaptionBand: React.FC<{captions: CaptionInput[]; sourceLabel?: string}> = ({
  captions,
  sourceLabel,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const active = captions.find((c) => t >= c.startSec && t < c.endSec);

  // 抑制された出入り: 120ms フェードのみ (踊る字幕・カラオケ演出は禁止)
  let opacity = 0;
  if (active) {
    const fade = 0.12;
    opacity = interpolate(
      t,
      [active.startSec, active.startSec + fade, active.endSec - fade, active.endSec],
      [0, 1, 1, 0],
      {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
    );
  }

  return (
    <div
      style={{
        position: 'absolute',
        top: CAPTION_BAND.top,
        left: SAFE_LEFT,
        width: 1080 - SAFE_LEFT - SAFE_RIGHT,
        height: CAPTION_BAND.height,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div
        style={{
          opacity,
          color: COLORS.text,
          fontFamily: 'Hiragino Sans, "Noto Sans JP", sans-serif',
          fontWeight: 700,
          fontSize: 54,
          lineHeight: 1.45,
          textAlign: 'center',
          maxWidth: '100%',
          textShadow: '0 2px 12px rgba(0,0,0,0.9)',
        }}
      >
        {active?.text ?? ''}
      </div>
      {sourceLabel ? (
        <div
          style={{
            position: 'absolute',
            bottom: 12,
            color: COLORS.grey,
            fontFamily: 'Hiragino Sans, "Noto Sans JP", sans-serif',
            fontSize: 26,
          }}
        >
          {sourceLabel}
        </div>
      ) : null}
    </div>
  );
};

// ── フックカード (0〜2 秒、サムネ三役) ───────────────────────────
const HookCard: React.FC<{
  image: string;
  text: string;
  subText?: string;
}> = ({image, text, subText}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const total = HOOK_CARD_SEC * fps;
  // 終端 0.4s でフェードアウトして紙面へ。frame 0 は完全表示 (サムネフレーム)。
  const opacity = interpolate(frame, [total - 0.4 * fps, total], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <AbsoluteFill style={{opacity, backgroundColor: COLORS.base}}>
      <Img
        src={staticFile(image)}
        style={{position: 'absolute', width: 1080, height: 1920, objectFit: 'cover'}}
      />
      {/* thumbnail_text: プレート側で予約された中央余白帯に後乗せ (分業原則) */}
      <div
        style={{
          position: 'absolute',
          top: 760,
          left: SAFE_LEFT,
          width: 1080 - SAFE_LEFT - SAFE_RIGHT,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 28,
        }}
      >
        <div
          style={{
            color: COLORS.text,
            fontFamily: 'Hiragino Sans, "Noto Sans JP", sans-serif',
            fontWeight: 900,
            fontSize: 108,
            lineHeight: 1.2,
            textAlign: 'center',
            textShadow: '0 4px 24px rgba(0,0,0,0.95)',
          }}
        >
          {text}
        </div>
        {subText ? (
          <div
            style={{
              color: COLORS.accent,
              fontFamily: 'Hiragino Sans, "Noto Sans JP", sans-serif',
              fontWeight: 700,
              fontSize: 46,
              textAlign: 'center',
              textShadow: '0 2px 12px rgba(0,0,0,0.9)',
            }}
          >
            {subText}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

// ── BGM (ナレーション中 ducking) ─────────────────────────────────
const Bgm: React.FC<{src: string; captions: CaptionInput[]; hasNarration: boolean}> = ({
  src,
  captions,
  hasNarration,
}) => {
  return (
    <Audio
      src={staticFile(src)}
      loop
      volume={(f) => {
        if (!hasNarration) {
          return BGM_VOLUME_FULL;
        }
        const t = f / 30;
        const speaking = captions.some((c) => t >= c.startSec - 0.15 && t < c.endSec + 0.15);
        return speaking ? BGM_VOLUME_DUCKED : BGM_VOLUME_FULL;
      }}
    />
  );
};

// ── メインコンポジション ─────────────────────────────────────────
export const FirstWork: React.FC<FirstWorkProps> = (props) => {
  const {fps} = useVideoConfig();

  let cursor = 0;
  const sceneSequences = props.scenes.map((scene, i) => {
    const from = Math.round(cursor * fps);
    const durationInFrames = Math.max(1, Math.round(scene.durationSec * fps));
    cursor += scene.durationSec;
    return {scene, i, from, durationInFrames};
  });

  return (
    <AbsoluteFill style={{backgroundColor: COLORS.base}}>
      {/* 紙面 3 帯 */}
      <HeaderBand title={props.platformTitle} />
      {sceneSequences.map(({scene, i, from, durationInFrames}) => (
        <Sequence key={`${scene.block}-${i}`} from={from} durationInFrames={durationInFrames + Math.round(CROSSFADE_SEC * fps)}>
          <ScenePlate scene={scene} index={i} durationInFrames={durationInFrames} />
        </Sequence>
      ))}
      <CaptionBand captions={props.captions} sourceLabel={props.sourceLabel} />

      {/* 音声 */}
      {props.narrationAudio ? <Audio src={staticFile(props.narrationAudio)} /> : null}
      {props.bgmAudio ? (
        <Bgm
          src={props.bgmAudio}
          captions={props.captions}
          hasNarration={Boolean(props.narrationAudio)}
        />
      ) : null}

      {/* フックカード (最前面、0〜2 秒) */}
      <Sequence from={0} durationInFrames={HOOK_CARD_SEC * fps}>
        <HookCard
          image={props.hookCardImage}
          text={props.thumbnailText}
          subText={props.thumbnailSubText}
        />
      </Sequence>
    </AbsoluteFill>
  );
};
