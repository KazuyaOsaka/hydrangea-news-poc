# Hydrangea — Discussion Notes (DISCUSSION_NOTES.md)

最終更新: 2026-05-01 (F-state-protocol 完了時点)

> このドキュメントは「議論中だがまだ確定していないメモ」を蓄積する場所。
> 各バッチ完了時に Claude Code が再評価し、以下のいずれかに振り分ける:
>   - **確定済み** → DECISION_LOG.md に昇格 (時系列エントリとして追加)
>   - **タスク化** → FUTURE_WORK.md に昇格 (緊急度別に追加)
>   - **アーカイブ** → 30 日以上古い + 状況変化で意味を失ったものを下のセクションに移動
>
> 各エントリは「日付 / トピック / 内容 / 出典 / ステータス」の 5 項目で記載する。

---

## 未分類 (Active)

### 2026-05-01: 手動 PoC 推奨の軌道修正経緯 (クラウド誤り 5 例目)
- **内容**: クラウド (claude.ai 側) が当初「自動化を先に」と提案したが、
  カズヤが「自動化の前に最高傑作を 1 本人間が手作りする」哲学を主張し、
  Phase A.5-3b として手動 PoC をロードマップに正式登録した経緯。
  クラウドの誤り 5 例目として記録 (1-4 例目は別途整理予定)。
- **出典**: 引き継ぎプロンプト v3 / チャット移行時のロードマップ確定議論
- **ステータス**: `Active` (今後同種の誤りを防ぐため、CURRENT_STATE.md の
  「カズヤの直近フィードバック要点」に反映する候補)

### 2026-05-01: C-1/C-2/C-3 の RPM 対策が引き継ぎプロンプト全バッチ歴史リストから消えてる件
- **内容**: Phase 1 で実施した Gemini RPM 制限対策 3 バッチ (B-2 系)
  および C-1/C-2/C-3 の対応詳細が、最近の引き継ぎプロンプトの
  「全バッチリスト」から欠落している。CURRENT_STATE.md には
  「11 連続成功」のみが記載されており、Phase 1 / 1.5 の成果が
  時系列で追えなくなりつつある。
- **出典**: 引き継ぎプロンプト v3 / 過去の DECISION_LOG.md レビュー
- **ステータス**: `要確認` (DECISION_LOG.md に C-1/C-2/C-3 のエントリが
  存在するか確認 → 不足していれば補完する判断)

### 2026-05-01: CLAUDE_CODE_INSTRUCTIONS.md は分析レイヤー実装期 (2026-04-25) の遺産
- **内容**: `CLAUDE_CODE_INSTRUCTIONS.md` は 2026-04-25 の分析レイヤー実装期に
  作成されたもので、現運用 (BATCH_PROTOCOL ベース) と別系統。
  現状で参照されている形跡が薄く、アーカイブ判断対象。
- **出典**: 引き継ぎプロンプト v3 / リポジトリの docs/ ディレクトリ確認
- **ステータス**: `昇格候補(FUTURE_WORK)` (緊急度低: アーカイブ判断 + 移動先決定)

### 2026-05-01: スコープ転換 → DECISION_LOG 昇格運用ルール (F-12-B-1 前例)
- **内容**: F-12-B-1 で「NG リスト方式 → 考え方で制御」へスコープが
  根本転換した際、その判断経緯を DECISION_LOG.md に記録した前例がある。
  今後同種のスコープ転換が発生した場合、DISCUSSION_NOTES.md に
  メモを蓄積 → バッチ完了時に DECISION_LOG.md へ昇格する運用ルールを明文化したい。
- **出典**: 引き継ぎプロンプト v3 / DECISION_LOG.md の F-12-B-1 エントリ
- **ステータス**: `昇格候補(DECISION_LOG)` (BATCH_PROTOCOL.md に運用ルールとして
  追記 → DECISION_LOG.md に意思決定として登録)

### 2026-05-01: STEP 3 既存禁止語表と F-12-B-1 「考え方の原則」のレイヤー関係
- **内容**: configs/prompts/analysis/geo_lens/script_with_analysis.md の
  STEP 3 既存禁止語表 (真実→事実、衝撃→力学、黒幕→主導権 等) と、
  F-12-B-1 で導入した「考え方の原則」(視聴者ファースト 3 原則) は
  独立した 2 層として機能している。既存の語彙ガード (STEP 3) の上に
  思想的原則 (F-12-B-1) を重ねる構造が機能している事実が、どこにも
  明文化されていない。
- **出典**: 引き継ぎプロンプト v3 / configs/prompts/analysis/geo_lens/ 参照
- **ステータス**: `昇格候補(DECISION_LOG)` (構造を整理して登録すべき)

### 2026-05-01: ★最優先 — 不変原則 2「script_writer.py 一切変更不可」が実装と乖離
- **内容**: BATCH_PROTOCOL.md (および各バッチプロンプト) に記載の
  不変原則 2「script_writer.py 一切変更不可」が、実装の現状と乖離している。
  実装は F-12-A / F-12-B / Batch 5 で大改修済み:
    - `generate_script_with_analysis` (新ルートのエントリポイント)
    - `ScriptWithAnalysisDraft` (新スキーマ)
    - `_AXIS_TO_PATTERN_HINT` (axis → pattern マッピング)
    - `_ANALYSIS_DURATION_PROFILES` (analysis 用 duration プロファイル)
    - `article_text` パラメータ (article-first 順序逆転対応)
  正しい不変原則 2 は「**既存の `write_script()` / `_PROMPT_TEMPLATE` /
  `_build_script_from_llm()` は触らない、新ルートへの追加・修正は OK**」。
  本バッチ (F-state-protocol) で BATCH_PROTOCOL.md を修正する。
- **出典**: 引き継ぎプロンプト v3 / src/generation/script_writer.py 実装確認
- **ステータス**: `昇格候補(DECISION_LOG)` ★最優先
  (本バッチで修正実施 → DECISION_LOG.md に「不変原則 2 の正確化」として登録)

### 2026-05-01: F-13 ガード quality_floor_miss bypass が独立した安全網として機能
- **内容**: src/generation/script_writer.py の 865-895 行に存在する
  F-13 の quality_floor_miss bypass ロジックが、独立した安全網として
  機能している事実が、DECISION_LOG.md / EDITORIAL_MISSION_FILTER_DESIGN.md の
  どこにも記録されていない。具体的には、`analysis_result` が存在すれば
  appraisal の `[抑制]` を上書きする動作。これは F-13 の意図通りだが、
  「Hydrangea コンセプト防衛機構の隠れ層」として明示的に位置付ける必要がある。
- **出典**: 引き継ぎプロンプト v3 / src/generation/script_writer.py:865-895 確認
- **ステータス**: `昇格候補(DECISION_LOG)` (CURRENT_STATE.md の防衛機構表に
  「F-13 隠れ層」として記載 → DECISION_LOG.md に意思決定として登録)

### 2026-05-01: 新ルートで target_enemy を排除した設計判断
- **内容**: F-12-A 系で導入された新ルート
  (`generate_script_with_analysis`) では `target_enemy` を意図的に排除
  している。コードコメントには「仮想敵濫用を抑止」と記載されているが、
  この設計判断 (Hydrangea のトーン方針との整合) が DECISION_LOG.md に
  記録されていない。忘れ去られた実装判断の典型例。
- **出典**: 引き継ぎプロンプト v3 / src/generation/script_writer.py の
  新ルート関連コード
- **ステータス**: `昇格候補(DECISION_LOG)`

### 2026-05-01: F-12-B-1.5 (文字数制約緩和) と不変原則 2 の現記述の不整合
- **内容**: F-12-B-1.5 で予定している `_CHAR_BOUNDS` 調整 (文字数制約緩和)
  は、不変原則 2 の現記述「script_writer.py 一切変更不可」だと違反と
  読めてしまう。エントリ #6 と一緒に解消する (新ルート向け or 定数の
  最小改変は許容、と明記)。
- **出典**: 引き継ぎプロンプト v3 / FUTURE_WORK.md の F-12-B-1.5 エントリ
- **ステータス**: `Active` (#6 と一括解消)

### 2026-05-01: FUTURE_WORK の F-7-α (perspective_extractor 改善) が既に部分実装済み
- **内容**: FUTURE_WORK.md に「F-7-α: perspective_extractor 改善」として
  登録されている内容のうち、以下が既に実装完了している:
    - silence_gap OR 条件 3 パターン化
    - hidden_stakes 段階的閾値
    - cultural_blindspot region+source ホワイトリスト経路
    - 4 軸全部不成立時のフォールバック観点
      (`_build_fallback_perspective`)
  FUTURE_WORK.md のエントリの方が古く、整合性が取れていない。
- **出典**: 引き継ぎプロンプト v3 / src/analysis/perspective_extractor.py 確認
- **ステータス**: `昇格候補(FUTURE_WORK)` (FUTURE_WORK.md 該当エントリの
  完了済みへの移動 + 残作業の再整理)

---

## アーカイブ

(現時点ではアーカイブ済みエントリなし。30 日以上経過 + 状況変化で
意味を失ったエントリをここに移動する。削除はしない、履歴として残す。)
