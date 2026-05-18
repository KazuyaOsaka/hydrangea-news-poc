# F-image-prompt-spec 統合レポート

実行日: 2026-05-18
ブランチ: `feature/F-image-prompt-spec` (main `8dc62da` から作成)
baseline: **1417 passed** 維持 (`src/ tests/ configs/ scripts/ CLAUDE.md` 0 行変更)
種別: ドキュメントバッチ (ADR + schema 設計の固定化、実装は一切しない)

---

## 1. バッチ概要

Phase A.5-3b 第一作 (候補A `cls-6889e9e1c7ac`、Israel 9,600 人収監 / ICRC
監視操作疑惑、perspective_gap framing) 着手前に、Hydrangea ブランドの画像戦略
+ Remotion 実装範囲 + コンテンツモラル設計を **ADR 3 件 + video_payload schema
拡張設計**として固定化した。

2026-05-16 に 3 AI 三角測量 3 ラウンド (claude.ai + ChatGPT + Gemini) で
D-minimal 仕様が確定済み。本バッチはその仕様を ADR + schema に落とし込み、
Phase A.5-3b 実装の前提を整える「対症療法じゃなく根本治療」+「動くものを
壊さない」+「負債を残さない」バッチ。

| Task | 内容 | 結果 |
|---|---|---|
| A | ブランチ作成 + 環境スナップショット | ✅ main HEAD `8dc62da` 確認、baseline 1417 passed 確認 |
| B | 現行 video_payload 構造の精密調査 | ✅ `current_schema_analysis.md` |
| C | ADR 3 件作成 | ✅ ADR-0001 / 0002 / 0003 |
| D | video_payload schema 拡張設計 | ✅ `schema_extension_design.md` |
| E | 統合 REPORT 生成 | ✅ 本ファイル |
| F | BATCH_PROTOCOL Task 1-5 | ✅ §8 |
| G | commit/merge 準備 | カズヤ承認待ち |

---

## 2. 現行 video_payload 構造の精密調査結果 (Task B)

詳細: `docs/runs/F-image-prompt-spec/current_schema_analysis.md`

事前調査 (F-trial-run-post-llm-extraction `video_payload_audit.json`) の結論を
**コード読解で完全に裏付けた**。乖離・想定外なし (= バッチプロンプト「想定外
結果への対処」の即停止条件に非該当):

- `VideoScene` / `VideoPayload` モデル・実装・本番出力すべてに **`image_prompt`
  フィールドは存在しない**。映像生成志向の `video_prompt` のみ。
- scene は `script.sections` と **1:1 対応で構造的に必ず 4 個**
  (hook 4s / setup 16s / twist 40s / punchline 20s)。「12-15 scene」は
  実装上発生し得ない。
- `video_prompt` は `_make_video_prompt()` の **テンプレ条件分岐 (heading ×
  evidence_strength) による決定論出力。LLM 非関与**。`configs/prompts/` に
  video_payload 用プロンプトは 0 件 (grep 確認済)。
- `negative_prompt` / `must_avoid` は **デフォルトで強い安全方向**
  (`_BASE_NEGATIVE`: 実在人物顔アップ / 架空会談 / 戦闘映像を常時禁止、
  visual_safety_level=elevated)。ADR-0003 の禁止事項と方向一致。

→ F-image-prompt-spec は「既存 image_prompt の品質改善」ではなく
「image_prompt レイヤー新設の設計判断」バッチであることがコード読解でも確定。

---

## 3. ADR 3 件の決定内容サマリー (Task C)

| ADR | タイトル | 核心 |
|---|---|---|
| ADR-0001 | Hydrangea 画像戦略 (C') | 6-8 枚ベース画像 + 10 イベント (第一作 MVP)、5 色パレット (near black / off-white / hydrangea blue / muted red 限定 / grey)、editorial 路線、cinematic/photorealistic 禁止語彙、4 イベントタイプ |
| ADR-0002 | Remotion 第一作 MVP (D-minimal) | やること (9:16 / 静的画像 / 4 カード / fade-cut-dissolve のみ) と やらないこと (Ken Burns / キネティックタイポ / 複雑トランジション禁止)、失敗条件 (1 週間超で機能削減)、CapCut は非常口 |
| ADR-0003 | コンテンツモラル設計 | 実在人物 NG / ICRC 標章 NG / 事件再現 NG、出典明示、AI ラベル投稿前判定、高リスク事実の公開前検証必須、投稿前ゲート 6 項目チェックリスト |

3 ADR は相互参照で整合 (画像戦略の禁止語彙 ⇔ モラル設計の視覚禁止事項 ⇔
Remotion の D-minimal 境界)。現行実装の強い安全方向 (Task B §3) を
**後退させない**ことを ADR-0003 で明文化。

---

## 4. schema 拡張設計の核心 (Task D)

詳細: `docs/runs/F-image-prompt-spec/schema_extension_design.md`

- 現行 4 scene 構造を**壊さず** (`scenes[]` 残置・後方互換)、上に
  `images[]` (6-8 枚) と `events[]` (10 個) を新設。
- 各 image/event を `scene_block` (hook/setup/twist/punchline) で現行構造に
  紐付け。`associated_image_id` で event ↔ image を疎結合。
- 第一作 animation は `fade-in` / `cut` / `dissolve` の 3 種のみ (ADR-0002)。
- 各フィールドを ADR にトレース (image_prompt 末尾 5 色 ← ADR-0001、
  negative_prompt/must_avoid ← ADR-0003、animation 3 種 ← ADR-0002)。
- 第二作以降の拡張余地 (event type 追加・animation 種別追加) を
  モデル破壊なしの追加で許容する構造。

---

## 5. Phase A.5-3b 第一作実装での適用方針

1. `src/shared/models.py` に `VideoImage` / `VideoEvent` を新設し、
   `VideoPayload` に `images` / `events` を Optional default で追加
   (既存テスト 1417 を壊さない後方互換が前提)。
2. `src/generation/video_payload_writer.py` を**最小改変** (新フィールド
   追加のみ、既存 scene 生成ロジックは不変 = 動くものを壊さない)。
   不変原則 1-4 対象外だが最小改変を推奨。
3. `image_prompt` のブランドカラー/トーン語彙は **構造データとして固定**し、
   構図・主題は分析フェーズ LLM に委ねる折衷を有力案とする
   (クラウド誤り 9 = 各論コントロールの誘惑を回避、`schema_extension_design.md`
   §5 論点 1)。
4. Remotion プロジェクトは D-minimal で構築 (ADR-0002)。Node 環境は
   カズヤ手動準備。

---

## 6. 残課題 / カズヤ確認推奨事項

- **schema_extension_design.md §5 の未決論点 4 件** (image_prompt 生成主体 /
  scenes[] 責務分離 / writer 改修範囲 / モデル拡張) は Phase A.5-3b 第一作
  起案バッチで決定 (FUTURE_WORK 登録)。
- **ADR-0003 投稿前ゲートチェックリスト** の実装は Phase A.5-3d
  (FUTURE_WORK 新規残課題登録)。
- 第一作着手前の独立必須確認: **F-trial-run-candidate-a-reverify**
  (候補A の B-3' 改修後再確認、FUTURE_WORK 緊急度 高に既登録、本バッチでは
  着手しない)。
- ElevenLabs 声選定 (30 分作業、カズヤ手作業) / Remotion Node 環境準備
  (カズヤ手動) は CURRENT_STATE §2 着手前確認事項に既記載。
- 想定外結果: **なし**。事前調査結果との乖離なし (image_prompt 非存在・
  4 scene・統一末尾なしをコード読解で確認 = 想定通り)。スコープ拡大なし。

---

## 7. 不変原則遵守確認

- `src/` `tests/` `configs/` `scripts/` `CLAUDE.md`: **0 行変更**
  (`video_payload_writer.py` は調査のみ、改修なし)。
- baseline **1417 passed** 維持。
- 変更は `docs/ADR/` 3 件新規 + `docs/runs/F-image-prompt-spec/` 配下 +
  `docs/CURRENT_STATE.md` / `DECISION_LOG.md` / `FUTURE_WORK.md` /
  `DISCUSSION_NOTES.md` 更新のみ。

---

## 8. BATCH_PROTOCOL Task 1-5 ドッグフーディング適用内容

### Task 1: DECISION_LOG エントリ追加
`docs/DECISION_LOG.md` 末尾に「2026-05-18: F-image-prompt-spec — ADR 3 件 +
video_payload schema 拡張設計の固定化」エントリ追加。

### Task 2: FUTURE_WORK 更新
- 完了済みに「F-image-prompt-spec (ADR + schema 設計固定化)」追加。
- 緊急度 高「F-image-prompt-spec」(スコープ再定義要) を完了済みに移動。
- 新規残課題追加:
  - 緊急度 高「Phase A.5-3b 第一作起案」(ADR 3 件 + schema 拡張前提)
  - 緊急度 中「第一作公開前の高リスク事実検証ワークフロー」
    (ADR-0003 投稿前ゲートチェックリスト実装、Phase A.5-3d)

### Task 3: 完了レポートに更新内容明記
本 REPORT.md 本セクション (8)。

### Task 4: DISCUSSION_NOTES 整理
- 4-A 新規追加: 「2026-05-18: 3 AI 三角測量がブランドトーン + 実装範囲を
  確立した経緯 (ADR-0001/0002/0003 として正典化)」
- 4-B 既存再評価: 「2026-05-16: video_payload に image_prompt レイヤーが
  存在しない — F-image-prompt-spec スコープ再定義」を **Active → Resolved**
  (ADR + schema 設計で正典化完了)。

### Task 5: CURRENT_STATE 全置換更新
最終更新日 2026-05-18、F-image-prompt-spec 完了反映、ロードマップに
1-K 行を完了化、次バッチ候補刷新 (F-trial-run-candidate-a-reverify →
Phase A.5-3b 第一作起案)。

---

## 9. 環境構築・依存追加

- requirements.txt 追加: なし / 環境変数追加: なし
- 新規ファイル:
  - `docs/ADR/0001-image-strategy.md`
  - `docs/ADR/0002-remotion-mvp-scope.md`
  - `docs/ADR/0003-content-moral-guidelines.md`
  - `docs/runs/F-image-prompt-spec/environment_snapshot.json`
  - `docs/runs/F-image-prompt-spec/current_schema_analysis.md`
  - `docs/runs/F-image-prompt-spec/schema_extension_design.md`
  - `docs/runs/F-image-prompt-spec/REPORT.md`
- 更新ファイル: `docs/CURRENT_STATE.md` (全置換) / `docs/DECISION_LOG.md` /
  `docs/FUTURE_WORK.md` / `docs/DISCUSSION_NOTES.md`

`src/` `tests/` `configs/` `scripts/` `CLAUDE.md` 全て 0 行変更、
baseline 1417 passed 維持。

---

*このレポートは F-image-prompt-spec (Phase A.5-3a-verify ゲート完了後の
12 つ目のバッチ) が生成。3 AI 三角測量 3 ラウンドで確立した D-minimal 仕様を
ADR 3 件 + video_payload schema 拡張設計として固定化し、Phase A.5-3b 第一作
実装の前提を整えた。「動くものを壊さない」+「負債を残さない」原則遵守、実装は
一切せず設計のみ。*
