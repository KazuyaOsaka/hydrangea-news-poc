import React from 'react';
import {Composition} from 'remotion';
import {FirstWork} from './FirstWork';
import {FPS, FRAME_HEIGHT, FRAME_WIDTH} from './layout';
import type {FirstWorkProps} from './types';
import dummyProps from './dummy-props.json';

/**
 * durationInFrames は props (scenes の合計秒) から導出する = 完全データ駆動。
 * 実素材レンダは --props=<path> で props JSON を差し替えるだけでよい。
 */
export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="FirstWork"
      component={FirstWork}
      width={FRAME_WIDTH}
      height={FRAME_HEIGHT}
      fps={FPS}
      defaultProps={dummyProps as FirstWorkProps}
      calculateMetadata={({props}) => {
        const totalSec = (props.scenes as FirstWorkProps['scenes']).reduce(
          (acc, s) => acc + s.durationSec,
          0,
        );
        return {
          durationInFrames: Math.max(1, Math.round(totalSec * FPS)),
        };
      }}
    />
  );
};
