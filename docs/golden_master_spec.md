# Golden Master 運用規約 (第一作 / F-first-work-golden-master)

最終更新: 2026-06-11 (F-first-work-golden-master / 1-S で新設)

本ドキュメントは Phase A.5-3b 第一作 (候補A `cls-6889e9e1c7ac`) の
**golden master 素材一式の編集・再検証・手動動画 PoC の運用規約** の正典である。
設計判断の経緯は `docs/DECISION_LOG.md` (2026-06-11 エントリ)、画像・Remotion・
モラルの正典は `docs/ADR/0001-0003` を参照。

---

## 1. 第一作隔離原則 (不変原則 6 として扱う)

- 第一作の成果物・作業は以下に隔離する:
  - `manual_poc/` — 生成ハーネス / editorial brief / TTS 変換 / Remotion プロジェクト
  - `data/output/golden_master/` — 凍結成果物 (gitignored、コミット用スナップショットは
    `docs/runs/F-first-work-golden-master/golden_master/`)
  - `docs/golden_master_spec.md` — 本ドキュメント
- **production 経路 (main.py / configs/prompts/ / src/) の振る舞いを第一作固有の事情で
  変えない**。候補A 固有の操作 (観点候補注入 / editorial brief 注入 / 系統の人間検証値
  訂正) は全て `manual_poc/generate_golden_master.py` 内のプロセスローカルな注入で行い、
  `generation_metadata.json` に全て記録される。
- 例外 (production 機能として実装したもの): `src/generation/image_prompt_writer.py`
  (image_prompt レイヤー、元から F-image-prompt-spec の設計判断)。
- `manual_poc/remotion/` は独立 npm プロジェクトであり、本体リポジトリの
  requirements.txt / 依存構成を汚染しない。

## 2. original 凍結と edited 命名規約

- `data/output/golden_master/` の生成物は **original として凍結** する。
  以後一切手で書き換えない。
  - `cls-6889e9e1c7ac_script.json` / `_article.md` / `_analysis.json` /
    `_video_payload.json` / `image_prompts.json` / `generation_metadata.json`
- カズヤの編集は **別ファイル** に保存する: 元名に `_edited` を付ける。
  - 例: `cls-6889e9e1c7ac_script_edited.json` / `cls-6889e9e1c7ac_article_edited.md`
- **original vs edited の diff が AI 文体・framing 改善の教師信号**
  (DISCUSSION_NOTES 2026-06-08 方針)。生成プロンプトの改修は第一作の編集差分を
  観測してから別バッチで行う (本バッチでは観測の器のみ)。

## 3. 編集 → Guardian 再検証の運用ループ

検証 3 ランナーは全て **flag のみ** (自動修正・公開ブロックなし)。公開判断はカズヤ。

```bash
# (1) coverage claim guard (title / article の報道状態主張の事実整合)
PYTHONPATH=. python scripts/run_coverage_claim_guard.py \
    --dir data/output/golden_master --cls cls-6889e9e1c7ac

# (2) Editorial Guardian 第1層 (高リスク主張抽出 + 忠実性)
PYTHONPATH=. python scripts/run_editorial_guardian.py \
    --cls cls-6889e9e1c7ac --dir data/output/golden_master \
    --out docs/runs/F-first-work-golden-master/golden_master_guardian_report.json

# (3) Editorial Guardian 第2層 (真実性 = grounding 複数ソース突合)
PYTHONPATH=. python scripts/run_editorial_guardian_corroboration.py \
    --report docs/runs/F-first-work-golden-master/golden_master_guardian_report.json \
    --out docs/runs/F-first-work-golden-master/golden_master_guardian_report_enriched.json
```

ループ手順:

1. flag (公開可否バー: **supported × corroborated のみ非 flag**) をレビューし、
   `*_edited.*` に修正を反映する。
2. 編集後ファイルを一時ディレクトリに `{cls}_script.json` 等の命名で並べ、
   `--dir` を差し替えて (1)〜(3) を再実行する (original は触らない)。
3. 503 波で `unverified` が出たら (3) を再実行する (1-T.2 再実行ループ。検証未完は
   「検証済み」と偽らない = 沈黙的劣化の禁止)。
4. 全 claim が解消 (または人間判断で許容) されるまで繰り返す。

### 既知の注意点 (2026-06-11 初回 validation で実測)

- **editorial brief 由来の記述は第1層で flag される**: brief は人間検証済み事実
  (例: TeleSUR = ベネズエラ政府系) を script に注入するが、Guardian 第1層の照合素材
  (event_snapshot + analysis) には存在しないため `not_in_source` / `contradicted` に
  なりうる。これは仕様 (第1層 = 忠実性、第2層 = 真実性)。brief 由来の記述は第2層の
  corroboration / 人間判断で解消する。
- **title (platform_title) の silence 絶対表現**: `title_generator.py` ハードコード
  template 由来 (F-title-generator-stream-aware-fix ★中 未対応)。guard が flag するので
  手修正する。第一作の手修正対象 1 号。
- **analysis 由来の具体的企業・事象主張**: 分析レイヤーが世界知識から導入した固有名詞
  主張 (例: 日本郵船 / 伊藤忠) は第1層では supported (analysis に忠実) になる。
  **第2層で corroborated にならない限り公開に乗せない** (削除または出典確認)。

## 4. 手動 PoC 残作業チェックリスト

自動化済み (本バッチで完了): golden master 生成 / validation 3 ランナー /
image_prompt 5 プレート / Remotion テンプレート + ダミーレンダ / 字幕変換スクリプト。

残る手動作業 (カズヤ):

- [ ] **編集**: flag レビュー → `*_edited.*` 作成 → §3 ループで再検証
- [ ] **ElevenLabs 実生成**: 声選定 (登録済み) → `POST /v1/text-to-speech/{voice_id}/with-timestamps`
      で台本 (intro + 4 sections) を生成し応答 JSON を保存
- [ ] **captions 変換**: `python manual_poc/tts_to_captions.py response.json
      --captions-out manual_poc/remotion/public/assets/captions.json
      --audio-out manual_poc/remotion/public/assets/narration.mp3`
- [ ] **画像 3 候補比較**: `image_prompts.json` の prompt_en / negative_prompt_en を
      Nano Banana Pro / GPT Image 2 / Flux 2 系に **同文投入** し、ブランド適合
      (ADR-0001 パレット / 文字なし / ADR-0003 禁止事項) で比較選定
- [ ] **BGM 用意**: ロイヤリティフリーから editorial トーン (煽り曲禁止)。
      ducking は Remotion 実装済み
- [ ] **Remotion 実素材レンダ**: 素材を `manual_poc/remotion/public/assets/` に置き、
      props JSON (`src/types.ts` の FirstWorkProps 契約) を作成して
      `npx remotion render FirstWork out/first_work.mp4 --props=<props.json>`
- [ ] **axis_5 評価**: 完成動画 + 記事の主観評価
- [ ] **公開判断**: §3 の公開可否バー + ADR-0003 投稿前チェックリスト 6 項目
- [ ] **AI 生成コンテンツ開示**: YouTube「改変または合成されたコンテンツ」開示 +
      TikTok AI ラベルは **投稿時必須** (ADR-0003。抽象インフォグラフィック中心でも
      AI 音声 + AI 画像を含むため必須扱いとする)

## 5. Remotion テンプレート仕様 (manual_poc/remotion)

設計正典 (2026-06-10 クラウド調査 → DECISION_LOG 2026-06-11):

- **セーフゾーン中央帯の「動く紙面」**: 1080×1920 / 上 250px / 下 320px / 右 110px に
  重要要素を置かない (`src/layout.ts` 定数)。全画面没入型 (UGC 文法) は採らない。
- **紙面 3 帯**: ヘッダー帯 (platform_title) / 中央ビジュアル帯 (1:1 プレート +
  Ken Burns) / 字幕帯 (タイムスタンプ駆動フレーズ同期、burned-in、サンセリフ・
  高コントラスト・1〜2 行、演出抑制)
- **フックカード**: frame 0〜2 秒 = thumbnail_text + 9:16 プレート。
  ①フィード最初の1秒 ②Shorts サムネフレーム ③TikTok カバーの三役
- **分業原則**: 文字は全て Remotion レイヤーで描画。AI プレートは文字なし
- **BGM ducking**: ナレーション (= active caption) 中 0.12 / それ以外 0.35
- **完全データ駆動**: props JSON (FirstWorkProps) を差し替えるだけで実素材レンダ可能
- ダミーレンダ再現: `cd manual_poc/remotion && python3 scripts/make_dummy_assets.py &&
  npm install && npx remotion render FirstWork out/first_work_dummy.mp4`

※ ADR-0002 (D-minimal) は第一作で Ken Burns を「やらないこと」に挙げていたが、
2026-06-10 設計正典 (静止プレート + 紙面レイアウト前提では Ken Burns が最小限の
動きの担保) がこれを **部分的に更新** した。経緯は DECISION_LOG 2026-06-11 を参照。

## 6. 所在一覧

| 成果物 | パス |
|---|---|
| 凍結 golden master (original) | `data/output/golden_master/` (gitignored) |
| コミット用スナップショット | `docs/runs/F-first-work-golden-master/golden_master/` |
| validation レポート 3 種 | `docs/runs/F-first-work-golden-master/` |
| 生成ハーネス | `manual_poc/generate_golden_master.py` |
| editorial brief (候補A 固有) | `manual_poc/editorial_brief_candidate_a.md` |
| 字幕変換 | `manual_poc/tts_to_captions.py` |
| Remotion プロジェクト | `manual_poc/remotion/` |
| image_prompt レイヤー (production) | `src/generation/image_prompt_writer.py` |
