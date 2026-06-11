# F-first-work-golden-master (1-S) 完了レポート

実施日: 2026-06-11 / ブランチ: `feature/F-first-work-golden-master` (base = main `18b5287`)
実行環境: Claude Fable 5 (xhigh)

## 実装ファイル一覧

- 新規作成:
  - `manual_poc/generate_golden_master.py` (約 380 行) — 候補A 単発再生成ハーネス
    (snapshot ロード / 観点候補注入 / brief 注入 / モデル pin / fallback fail-fast / 監査 metadata)
  - `manual_poc/editorial_brief_candidate_a.md` — 候補A 固有 editorial brief (4 点 + ADR-0003)
  - `manual_poc/tts_to_captions.py` (約 160 行) — ElevenLabs with-timestamps → captions 変換
  - `manual_poc/README.md`
  - `manual_poc/remotion/` — 独立 npm プロジェクト (Remotion 4.0.475):
    `package.json` / `tsconfig.json` / `remotion.config.ts` / `.gitignore` /
    `src/{index.ts,Root.tsx,FirstWork.tsx,layout.ts,types.ts,dummy-props.json}` /
    `scripts/make_dummy_assets.py` (純 Python PNG/WAV 生成、Pillow/ffmpeg 不要)
  - `src/generation/image_prompt_writer.py` (約 300 行) — image_prompt レイヤー (production 機能)
  - `tests/test_image_prompt_writer.py` (18 tests) / `tests/test_tts_to_captions.py` (6 tests)
  - `docs/golden_master_spec.md` — 第一作運用規約 (正本)
  - `docs/runs/F-first-work-golden-master/` — 本ディレクトリ (validation レポート一式 +
    golden_master スナップショット + flag サマリ)
- 変更:
  - `src/generation/video_payload_writer.py` (+1 行, -1 行) — L72 仮想敵語彙除去のみ
  - `docs/ADR/0001-image-strategy.md` / `docs/ADR/0002-remotion-mvp-scope.md` — 部分更新注記
  - `docs/CURRENT_STATE.md` (全置換) / `docs/DECISION_LOG.md` / `docs/FUTURE_WORK.md` /
    `docs/DISCUSSION_NOTES.md`

## テスト結果

- `pytest tests/`: **1581 passed** (baseline 1557 → 1581、+24、破壊ゼロ、345s)
- 既存テスト影響: なし (既存テスト 0 行変更。仮想敵 L72 除去は tests 非依存を grep 確認済)
- 新規テスト追加: 24 個 (image_prompt_writer 18 + tts_to_captions 6、いずれも決定論で mock 不要)

## 起案前仮説 6 点の検証結果 (CP-1、誤り 10 作法)

| # | 仮説 | 結果 |
|---|---|---|
| 1 | 候補A 再生成可能性 | ★ **乖離 2 件訂正**: (a) `cls-6889e9e1c7ac_analysis.json` 非存在 (2026-05-11 batch = analysis layer 配線前) → ハーネスが分析を新規実行。(b) **重大**: sources_en=1 のため `extract_perspectives` が構造的 0 件 (4 軸最低 en>=2 + fallback ゲート sources_total>=2 不通過、実データドライランで実測) → fallback 同形 hidden_stakes 候補 (式同形、写し元 perspective_extractor.py L805-847 記録、品質ゲートのみ bypass) を `analysis_engine.extract_perspectives` のプロセス内差し替えで注入。Step 2-6 は production オーケストレーションのまま。snapshot は残存 (4,693B、event.summary 403 字 = X1 の raw 埋込 4,678 字より薄い旧 ingestion 仕様) |
| 2 | brief 注入経路 | 確認: `load_prompt` はファイルロード + 呼出時 import → ハーネスがロード後に「## STEP 1」アンカー直前へ挿入 (brace escape 済、production プロンプトファイル不変)。article は article_writer.py 内ハードコード = 注入不可も確認 (素のまま生成) |
| 3 | video_payload 現行構造 | 確認 + 訂正: image_prompt 非存在 / 決定論 / 仮想敵は L72 のみ → 1 行除去で同時解消 (5 行以内条項適用、判断: tests 非依存 + FUTURE_WORK 対応案そのまま)。visual_mode は「4 modes」ではなく evidence strength 連動 7 種 (anchor_style/document_style/split_screen/structure_diagram/infographic/symbolic/market_graphic) |
| 4 | ElevenLabs タイムスタンプ | `.env` に ELEVENLABS_API_KEY **不在** (キー名のみ grep、値非表示 = §4 遵守) → 実呼出なし。公式 docs (一次ソース) で `POST /v1/text-to-speech/{voice_id}/with-timestamps` の応答契約 (audio_base64 + alignment{characters[], character_start_times_seconds[], character_end_times_seconds[]} + normalized_alignment) を確認し、変換スクリプトを合成 fixture テストで実装。実走は手動 PoC |
| 5 | Remotion セットアップ | 確認: Node v22.21.0 / npm 11.13.0。Remotion 4.0.475 を `manual_poc/remotion/` に独立 scaffold、`npx remotion render` ローカル完結。remotion-dev/skills は実在 (3.6k stars) だが「internal package / no documentation」→ skill 導入はせず SKILL.md 指針 (CSS アニメーション禁止 / useCurrentFrame+interpolate / staticFile / Sequence) を実装に反映 |
| 6 | baseline | 確認: **1557 passed** 実測 (main HEAD `18b5287`、381s) |

## golden master 一式の所在

- **original (凍結)**: `data/output/golden_master/` (gitignored) — `cls-6889e9e1c7ac_script.json` /
  `_article.md` / `_analysis.json` / `_video_payload.json` / `image_prompts.json` (5 プレート) /
  `generation_metadata.json` (注入 3 点 + pin + 機械 stream 値の監査証跡)
- **コミット用スナップショット**: `docs/runs/F-first-work-golden-master/golden_master/` (同一内容)
- 再現コマンド: `python3 manual_poc/generate_golden_master.py` (GEMINI_API_KEY 必要、≈6 LLM calls)
- 生成条件: QUALITY/ARTICLE 全 Tier = **gemini-3.5-flash pin** (503 波 silent 劣化 → fail 変換。
  初回 run で article が tier3 劣化したため pin を追加して再生成 = 全成果物が確定布陣由来)。
  script: 新ルート / retries=0 / target_enemy=None / char validation passed (hook=22, setup=82,
  twist=172, punchline=77)。機械 stream = stream_2_perspective_gap (人間確定値と一致、訂正不要)

## validation 3 レポートのサマリ (詳細 = `flag_summary_for_human_audit.md`)

| ランナー | 結果 |
|---|---|
| coverage_claim_guard (×2 run) | run1 = consistent → run2 = **title contradiction flag** (platform_title「日本では報道されない9,600 Detaineesの視点」、title_generator ハードコード由来 = 想定通り)。★ 同一入力で flag 有無が反転 = **ガード文脈の run 間分散を初観測** |
| Guardian 第1層 | 14 主張 → 12 supported / **1 contradicted (c5 = 告発主体の帰属エラー: 告発は囚人擁護センター、TeleSUR は報じた側)** / 1 not_in_source (c11)。★ brief 由来の記述 (TeleSUR=ベネズエラ政府系) は照合素材に無いため第1層で flag される = 仕様 (spec §3 に明文化) |
| Guardian 第2層 corroboration (×3 run、canonical = run1) | corroborated: c2/c3/c4/c12/c14 (run1) + **c6/c7 を run3 で回収** (c6 = 日本郵船回避運航 + 伊藤忠提携解消 = analysis 由来の企業主張が toyokeizai.net / arabnews.jp 等で裏取り成功)。**contradicted: c10/c13** (article「日本では詳細報道が極めて少ない」に独立日本語ソース [クーリエ・ジャポン / AFPBB / アムネスティ日本等] が明示矛盾 = brief 注入不可な article の構造的弱点を実地立証)。unverified: c8/c9 (3 run とも 503、再実行で回収予定)。c12 = run 間で corroborated ⇄ uncorroborated (証拠セット差 = 告発主体名の独立支持有無、人間監査向き検出) |

**手修正対象 5 点** (カズヤ監査の入口): ①platform_title silence ②script c5 帰属エラー
③article c10/c13 coverage 過大 ④**punchline 尻切れ「…突きつける、あの」(loop-2、X1 と同型 =
標本 2 例目)** ⑤article c11/c12 主体名・記述の出典確認。

## image_prompts.json 実例 (twist プレート抜粋)

> "Abstract editorial news graphic: the hidden structure behind the story: an abstract diagram-like
> composition of actors, incentives and flows of power and money in politics... Suggested abstract
> motifs (render as flat icons, silhouettes or diagrams, never photorealistic): abstract monitoring
> eye motif connected by arrows to a clipboard checklist and a prison gate, a guided inspection
> route drawn as a dotted line that avoids dark areas of the diagram. ... Style: sober investigative
> documentary infographic style, editorial lighting, source-driven layout... Colors: near-black
> background (#0A0A0A)... Constraints: absolutely no text, no letters... (all typography is rendered
> separately in code)."

5 本構成 = hook/setup/twist/punchline (1:1) + hook_card (9:16、中央帯にタイポ余白予約)。
negative_prompt に文字排除 + ADR-0003 固定禁止 (ICRC 標章 / 実在人物 / 戦闘) + ADR-0001 禁止トーン。

## Remotion ダミーレンダ

- 出力: `manual_poc/remotion/out/first_work_dummy.mp4` (600 frames / 20s / 1080×1920 / 2.6MB、gitignored)
- 再現: `cd manual_poc/remotion && python3 scripts/make_dummy_assets.py && npm install && npx remotion render FirstWork out/first_work_dummy.mp4`
- 静止フレーム目視確認済: frame 15 (フックカード = サムネ三役) / frame 200 (3 帯紙面 + 字幕帯 +
  出典ラベル、セーフゾーン遵守)

## 自分で判断した内容

- 判断 1 (★ 最重要): 候補A の観点候補が構造的 0 件 → **fallback 同形候補のハーネス注入** で訂正
  (production 0 行、人間確定 framing が正 =「機械判定は事実の代替ではない」、注入内容は全て
  generation_metadata に記録)。停止条件 (設計大逸脱) には該当しないと判断 — 製品コードに触れず
  CP-1 訂正権限の範囲内。
- 判断 2: 初回生成の article tier3 劣化を受け **モデル pin (全 Tier 3.5-flash)** を追加して再生成
  (凍結条件 = 確定布陣由来。沈黙的劣化の禁止の生成版、ab_article 前例転用)。
- 判断 3: image_prompt レイヤーは video_payload_writer 拡張ではなく**新モジュール** (最シンプル +
  隔離的)。イベント固有モチーフは motif_hints 引数で外部注入 (production 汎用 / 候補A 固有値は
  ハーネス側)。
- 判断 4: 仮想敵 L72 を同時解消 (1 行、tests 非依存、バッチプロンプト 5 行条項適用)。
- 判断 5: coverage guard run1 の consistent 判定を 1-Q.5 実績 (同型 title が contradiction) との
  矛盾から鵜呑みにせず再実行 → run2 で flag (誤り 10 作法を validation 結果自体にも適用)。
- 判断 6: corroboration は 503 波対応で計 3 run、canonical = run1 (単一 run 最完全)。run 横断の
  自動マージは 1-T.2 スコープ判断を踏襲して実装せず、人間向けサマリ (flag_summary) で集約。
- 判断 7: remotion-dev/skills は internal package のため導入せず、公式 SKILL.md の指針のみ反映。
- 判断 8: ADR-0001/0002 と設計正典の矛盾 (Ken Burns / images[]+events[]) は ADR に部分更新注記を
  追加して解消 (バッチプロンプトの設計正典が新しい正、経緯は DECISION_LOG)。

## 不変原則違反 / 触ってはいけないファイルへの変更要望

- なし (article_writer.py 0 行 / script_writer.py 既存ルート 0 行 / triage 0 行 / analysis 既存
  ファイル 0 行 / 既存テスト 0 行。第一作隔離 (6) も遵守 = production 変更は image_prompt_writer
  新規 + video_payload_writer 1 行のみ)

## BATCH_PROTOCOL Task 1-5 実施結果

- **Task 1 (DECISION_LOG)**: 2026-06-11 エントリ追加 (設計正典 5 点の採用根拠 / CP-1 乖離訂正 /
  モデル pin / validation 結果 / ADR 部分更新)。★ 1-T.2 エントリのコミット placeholder 埋め
  (`132082a` / merge `18b5287`)。
- **Task 2 (FUTURE_WORK)**: 完了移動 = Phase A.5-3b 第一作起案 (golden master 部分) +
  F-video-payload-visual-prompt-target-enemy。新規 = **第一作 手動 PoC** (★高、チェックリスト導線) +
  **F-fable5-guardian-poc** (★低 条件付き、採用条件 = 3.1-pro より明確に事故検出力が高い場合のみ)。
  既存更新 = F-script-punchline-tail-cut-investigate に標本 2 例目追記。
- **Task 4 (DISCUSSION_NOTES)**: 4-A 新規 2 件 (設計正典 5 点 / 編集差分 = 教師信号の観測開始宣言)。
  4-B 再評価 2 件 (Fable 5 挙動観察に ⑥ 1-S 観察追記 / image_prompt 非存在エントリに実装完了追記)。
- **Task 5 (CURRENT_STATE)**: 全置換更新 (HEAD / baseline 1581 / Phase = 手動 PoC フェーズ開始 /
  touchable map に manual_poc/ + golden_master/ + image_prompt_writer 追加 / 不変原則 6 = 第一作隔離 /
  導線更新)。`git diff HEAD` で全置換確認済 (241 insertions / 375 deletions)。

## 次バッチへの引継ぎ事項

- **手動 PoC はカズヤ工程** (`docs/golden_master_spec.md` §4 が正本、入口 =
  `flag_summary_for_human_audit.md` の手修正対象 5 点)。編集後は `*_edited.*` に保存し
  ガード 3 本を再実行 (original は凍結維持)。
- c8/c9 が 3 run とも 503 で unverified — corroboration ランナー再実行で回収する。
- punchline 尻切れの標本が 2 例 (X1 + 1-S、いずれも loop-2) に揃った —
  F-script-punchline-tail-cut-investigate の着手価値が上がった (並走候補 1st)。
- ガード文脈の run 間分散 (flag 反転) を初観測 — F-grounding-determinism-audit の観測 4 文脈目。
- ELEVENLABS_API_KEY は未設定 (手動 PoC でカズヤが `.env` に追加、値マスク運用)。
- Project Knowledge 最新化 reminder: 本バッチで CURRENT_STATE / FUTURE_WORK / DISCUSSION_NOTES /
  DECISION_LOG / ADR-0001/0002 + golden_master_spec.md (新規) が更新された。新チャット移行前に
  claude.ai Project Knowledge の再アップロード推奨。

## 環境構築・依存追加

- requirements.txt 追加: なし
- 環境変数追加: なし (.env / .env.example 変更なし。ELEVENLABS_API_KEY は手動 PoC 時にカズヤ追加)
- Node 依存: `manual_poc/remotion/` 内に独立 (Remotion 4.0.475 等、node_modules / out / dummy は
  gitignored、本体リポジトリ汚染なし)
- コスト概算: LLM ≈ $1 前後 (生成 2 回 + guard 2 回 + Guardian 1 回 + corroboration 3 回、503
  リトライ込。grounding usage 実測 = run1 9 calls 28K tokens / run3 同規模、judge は推定)
