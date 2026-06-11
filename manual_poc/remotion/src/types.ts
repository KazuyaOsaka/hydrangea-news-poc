/**
 * 入力契約: 完全データ駆動の props スキーマ。
 *
 * 実素材レンダ時は public/ に素材を置き、props JSON を
 * `npx remotion render FirstWork out/first_work.mp4 --props=path/to/props.json`
 * で渡す (パスは全て public/ 相対、staticFile で解決)。
 */

export type SceneBlock = 'hook' | 'setup' | 'twist' | 'punchline';

export interface SceneInput {
  block: SceneBlock;
  durationSec: number;
  /** public/ 相対パス。1:1 プレート (image_prompts.json の scene_plate 由来)。 */
  image: string;
}

export interface CaptionInput {
  /** 字幕フレーズ (1〜2 行想定)。tts_to_captions.py の出力契約。 */
  text: string;
  startSec: number;
  endSec: number;
}

export interface FirstWorkProps {
  /** ヘッダー帯に常時表示するタイトル (video_payload.metadata.platform_title)。 */
  platformTitle: string;
  /** フックカードの主文字 (thumbnail_text、3〜5 語規範)。 */
  thumbnailText: string;
  /** フックカードの副文字 (thumbnail_text_sub、任意)。 */
  thumbnailSubText?: string;
  /** 9:16 フックカードプレート (public/ 相対)。 */
  hookCardImage: string;
  scenes: SceneInput[];
  /** ナレーション音声 (public/ 相対、null = 無音レンダ)。 */
  narrationAudio: string | null;
  /** BGM (public/ 相対、null = BGM なし)。ducking は自動。 */
  bgmAudio: string | null;
  captions: CaptionInput[];
  /** 出典表示 (字幕帯下部に小さく常時表示、ADR-0003 出典明示)。 */
  sourceLabel?: string;
}
