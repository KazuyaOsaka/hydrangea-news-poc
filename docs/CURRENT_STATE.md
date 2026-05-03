# Hydrangea — Current State (CURRENT_STATE.md)

最終更新: 2026-05-03 (F-doc-cleanup 完了時点)

> このドキュメントは Hydrangea の「今この瞬間のスナップショット」。
> 各バッチ完了時に Claude Code が **全置換更新** する (追記ではない)。
> 過去の経緯は DECISION_LOG.md / FUTURE_WORK.md / DISCUSSION_NOTES.md を参照。

---

## 1. リポジトリ状態

- **main HEAD コミット**: `eaa0ac1`
- **直近 5 件のコミットログ**:
  ```
  eaa0ac1 Merge branch 'feature/F-cleanup-merge-streak'
  9369867 feat: remove meaningless 'consecutive merge streak' counter (F-cleanup-merge-streak)
  c736dc2 Merge branch 'feature/F-doc-backfill-supplement'
  a618803 feat: confirm image gen candidates + auto-publishing policy + extensibility (F-doc-backfill-supplement)
  fd1a41b Merge branch 'feature/F-doc-backfill'
  ```
- **baseline テスト数**: `1315 passed` (2026-05-03 F-doc-cleanup 完了時点で確認)

## 2. 現在のフェーズ

- **Phase**: Phase A.5-3a 完了 → A.5-3a-verify 着手前
- **進行中バッチ**: なし (F-doc-cleanup 完了直後)
- **次バッチ候補と推奨** (F-doc-cleanup / 2026-05-03 順序見直し):
  - 1st: **F-verify-jp-coverage** (★最優先、ゴールデンセット 20 件、2-3 時間、ゲート性格)
  - 2nd: **Phase A.5-3b 手動 PoC 着手** (image-prompt-spec を 3b 最初の作業に組み込み)
  - 並走: F-verify-perspective / F-verify-script-quality
    (3b/3c 中にデータ収集、判断は 3b/3c 完了後 = データ収集性格)
  - Phase A.5-3a-verify (jp-coverage) 通過 → Phase A.5-3b 手動 PoC
    (Remotion + ElevenLabs + 画像生成 [Nano Banana Pro / ChatGPT Images 2.0
    (gpt-image-2) / Flux 1.1 Pro 比較])
  - Phase A.5-3c で自動化 (F-elevenlabs-integration / F-image-gen-integration /
    F-video-compose-integration / F-cron)
  - Phase A.5-3d で投稿前ゲート + 自動投稿

### Phase A.5-3d 投稿対象の補足

Phase A.5-3d で本番リリースする対象は **geo_lens (政治・経済) のみ**。
japan_athletes / k_pulse / カテゴリ細分化 / 独自メディア化等の方向性は
Phase A.5-3d 安定稼働後に判断 (DISCUSSION_NOTES「Phase B 以降の方向性未確定」参照、
2026-05-03 議論で「本命 + 動画継続 / 独自メディア / 手動投稿の 3 択」に縮約)。

投稿先は TikTok と YouTube Shorts の両方同時、完全自動投稿 (cron 6 時間おき、
人手介入ゼロ、投稿前ゲートで品質保証)。

Phase A.5-3c 実装時は「拡張性差し込み判断ルール」(BATCH_PROTOCOL / 2026-05-03) を
遵守。力点は **ChannelConfig YAML 化 + Publisher 抽象** の 2 つで必要十分
(Content Format 抽象化や Renderer 前倒し抽象化は不要、過剰拡張性の罠を回避)。

## 3. 直近の試運転結果サマリー

| 試運転 | バッチ | 動画化率 | 主要観察 |
|---|---|---|---|
| 7-K | F-13.B | 100% (3/3) | FIFA + Gaza×2、rescue path 完全廃止後初の全 Slot 動画化成功 |
| F-12-B-1 | F-12-B-1 | — | cls-56c4197b6fd2 米イスラエル隠密作戦、視聴者ファースト改善確認 (固有名詞補足・話し言葉化) |
| F-12-B-1-extension | F-12-B-1-extension | 未実施 | LLM 出力依存のため未実施、抽象比喩軽減は継続観察項目 |
| 7-J | F-15 / F-16-A | 0% | rescue 発動で動画化ゼロ → F-13-B (rescue 完全廃止) のトリガー |
| 7-I | F-16-A | 67% (2/3) | Slot-3 (UAE OPEC) が MAX_PUBLISHES_PER_DAY で skip → F-16-A 着手 |

## 4. Hydrangea コンセプト防衛機構の現状 (5 層)

| 層 | バッチ | 場所 | 役割 | 状態 |
|---|---|---|---|---|
| F-1 | F-1 / F-1.5 | EditorialMissionFilter | 編集ミッション適合度で score 算出 (>= 45.0 で通過) | ✅ 稼働中 |
| F-2 | F-2 / F-5 | FlagshipGate (Hydrangea コンセプト整合) | 海外発の重要ニュースを優先 | ✅ 稼働中 |
| F-13.B | F-13.B | JpCoverageVerifier (rescue 完全廃止 + Web 検証) | JP 報道カバレッジを 27 ドメイン WL で検証 | ✅ 稼働中 |
| F-5 | F-5 | FlagshipGate 下流救済 | 上流ガードを通過した候補の最終整合 | ✅ 稼働中 |
| **F-13 (隠れ層)** | F-13 / F-doc-cleanup | script_writer.py:951-985 quality_floor_miss bypass | analysis_result 等が成立すれば appraisal の [抑制] を上書き | ✅ 稼働中 (F-doc-cleanup / 2026-05-03 で正式 5 層目に昇格、DECISION_LOG / EDITORIAL_MISSION_FILTER_DESIGN.md に明文化) |

## 5. 触ってよい / 触ってはいけない領域マップ

### 触ってよい領域
- `configs/prompts/` 配下全般 (主戦場: `configs/prompts/analysis/geo_lens/`)
- `docs/` 配下全般 (CURRENT_STATE / DISCUSSION_NOTES / DECISION_LOG /
  FUTURE_WORK / BATCH_PROTOCOL 等の更新)
- `tests/` 配下に新規テストファイル追加 (既存ファイルは原則変更しない)
- `src/triage/` に新規ファイル追加 (例: `jp_coverage_verifier.py`)
- `src/generation/script_writer.py` の **新ルート**
  (`generate_script_with_analysis` / `ScriptWithAnalysisDraft` /
  `_AXIS_TO_PATTERN_HINT` / `_ANALYSIS_DURATION_PROFILES` / `article_text` 等)
- `src/generation/script_writer.py` の `_CHAR_BOUNDS` 等の定数 (最小改変なら許容)

### 触ってはいけない領域
- `src/generation/article_writer.py` (不変原則 1)
- `src/generation/script_writer.py` の **既存ルート**
  (`write_script` / `_PROMPT_TEMPLATE` / `_build_script_from_llm`) (不変原則 2)
- `src/triage/` の既存ファイル (不変原則 3)
- `src/analysis/` 配下全般 (不変原則 4、F-12-B-2 着手時に例外条項追加検討)
- 既存テスト (不変原則 5、baseline 1315 passed 維持)

## 6. 不変原則 5 つ (リマインダ、正本: BATCH_PROTOCOL.md)

1. **`src/generation/article_writer.py` 一切変更不可**
2. **`src/generation/script_writer.py` の既存ルート (`write_script` /
   `_PROMPT_TEMPLATE` / `_build_script_from_llm`) は変更不可**。
   新ルート (`generate_script_with_analysis` 系) への追加・修正は OK。
   `_CHAR_BOUNDS` 等の定数調整も最小改変なら許容。
   **例外**: `configs/prompts/` 配下のプロンプトファイルは変更可、
   主戦場は `configs/prompts/analysis/geo_lens/`
3. **`src/triage/` の既存ファイル変更不可**。新規追加は OK
   (例: `jp_coverage_verifier.py`)
4. **`src/analysis/` 変更不可** (F-12-B-2 axis 多様化着手時に例外条項追加検討)
5. **既存テスト破壊しない** (baseline 1315 passed)

## 7. カズヤの直近フィードバック要点

- **「中間が良い」** — シニカル一辺倒でも生活実感一辺倒でもなく、両立
  (F-12-B-1-extension で punchline 定義を「シニカル × 具体着地」両立に)
- **「考え方で制御」** — NG リスト方式は廃止、原則ベースのプロンプト
  (F-12-B-1 で「視聴者ファースト 3 原則」として導入)
- **「対症療法じゃなくて根本治療」** — 仕組みで再発防止
  (F-doc-protocol / F-state-protocol / F-doc-cleanup 等の文書プロトコル整備の動機)
- **「負の遺産残さないように」** — 不整合・乖離を早期解消
  (F-doc-cleanup で F-13 隠れ層昇格 + DECISION_LOG 7 遡及 + CLAUDE.md 全面書き直し)
- **「カズヤの手作業はバッチプロンプトのコピペ 1 回のみ」** — 引き継ぎ
  プロンプト 2806 行の手作業再構築を排除する仕組みとして CURRENT_STATE.md /
  DISCUSSION_NOTES.md を導入
- **「過剰拡張性の罠」** — 「将来のため」の抽象化前倒しは見送る
  (BATCH_PROTOCOL「拡張性差し込み判断ルール」3 条件 / 2026-05-03)

## 8. 関連ドキュメントへの導線

- 過去の決定の経緯 → `docs/DECISION_LOG.md`
- 残課題リスト → `docs/FUTURE_WORK.md`
- 議論中の未確定メモ → `docs/DISCUSSION_NOTES.md`
- バッチ運用ルール → `docs/BATCH_PROTOCOL.md`
- アーキテクチャ全体像 → `docs/ARCHITECTURE.md`
- 技術的負債リスト → `docs/TECH_DEBT.md`
- リファクタ計画 (歴史的記録) → `docs/REFACTORING_PLAN.md`
- 編集ミッションフィルタ設計 (F-13 隠れ層含む) → `docs/EDITORIAL_MISSION_FILTER_DESIGN.md`
- Claude Code 振る舞い指針 → `CLAUDE.md`

---

*このドキュメントは F-state-protocol (2026-05-01) で導入。
 Claude Code がバッチ完了時に全置換更新する運用 (BATCH_PROTOCOL.md Task 5 参照)。
 F-state-protocol-supplement (2026-05-02) で「次バッチ候補」セクションを最小更新し、
 Phase A.5-3a-verify ロードマップを反映。
 F-doc-backfill (2026-05-02) で過去 19 セッション分の積み残しを正式登録、
 Phase A.5-3a-verify を 5→4 カテゴリに縮小、ElevenLabs 前倒しと Remotion 採用を
 DECISION_LOG に記録、ロードマップを 4 段階 (3a-verify → 3b → 3c → 3d) に再構成。
 F-doc-backfill-supplement (2026-05-02) で画像生成候補を ChatGPT Images 2.0
 (gpt-image-2) に確定、Phase A.5-3d 投稿対象を geo_lens 単独 + TikTok/YouTube
 同時 + 完全自動に明確化、拡張性原則 (Phase A.5-3c 設計時) を DECISION_LOG に追加。
 F-cleanup-merge-streak (2026-05-02) で「連続 main マージ成功カウント」を
 削除 (情報ノイズ・悪いインセンティブ排除)、main HEAD と直近 5 件ログを
 最新値に更新。
 F-doc-cleanup (2026-05-03) で文書負債の一括根本治療を実施: F-13 隠れ層を防衛機構の
 正式 5 層目に昇格 (4+1 → 5 層化、⚠️ 削除)、DECISION_LOG 遡及記録 7 エントリ追加
 (F-13 / F-13.B / F-15 / F-16-A / F-12-A / F-12-B / F-14)、CLAUDE.md 全面書き直し
 (Claude Code 振る舞い指針に集約、重複セクション排除)、REFACTORING_PLAN.md
 アーカイブ注記、2026-05-03 議論結果の docs 反映 (Phase B 3 択構造、Phase A.5-3a-verify
 順序見直し、クラウド誤り 6 追加)、BATCH_PROTOCOL に拡張性差し込み判断ルール新設。*
