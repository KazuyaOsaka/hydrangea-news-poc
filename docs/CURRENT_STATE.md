# Hydrangea — Current State (CURRENT_STATE.md)

最終更新: 2026-05-02 (F-state-protocol-supplement 完了時点)

> このドキュメントは Hydrangea の「今この瞬間のスナップショット」。
> 各バッチ完了時に Claude Code が **全置換更新** する (追記ではない)。
> 過去の経緯は DECISION_LOG.md / FUTURE_WORK.md / DISCUSSION_NOTES.md を参照。

---

## 1. リポジトリ状態

- **main HEAD コミット**: `1e4a932`
- **直近 5 件のコミットログ**:
  ```
  1e4a932 docs: record commit hash for F-12-B-1-extension entry
  4db3335 feat: refine punchline definition for cynical+grounded balance (F-12-B-1-extension)
  972ec04 docs: record commit hash for F-12-B-1 entry
  535f8e0 feat: add viewer-first editorial stance to script prompt (F-12-B-1)
  e70594e docs: establish batch protocol for forced doc updates (F-doc-protocol)
  ```
- **baseline テスト数**: `1315 passed` (2026-05-01 F-state-protocol 着手時点で確認)
- **連続 main マージ成功カウント**: `11 連続` (F-12-A → F-12-B-1-extension)

## 2. 現在のフェーズ

- **Phase**: Phase A.5-3a 完了 → A.5-3a-verify 着手中
- **進行中バッチ**: なし (F-state-protocol-supplement 完了直後)
- **次バッチ候補と推奨**:
  - 1st: **F-verify-jp-coverage** (★最優先、ゴールデンセット 20 件、2-3 時間)
  - 2nd: F-verify-e2e (5 日連続稼働、毎日 30 分手動運用)
  - 3rd: F-verify-rss (47+ sources 疎通、1 時間)
  - 4th: F-verify-perspective (4 軸バランス検証、F-12-B-2 着手判断材料)
  - 5th: F-verify-script-quality (NG パターン頻度、F-12-B-1.5 着手判断材料)
  - Phase A.5-3a-verify 全通過後 → Phase A.5-3b (手動 PoC、golden_master_spec 作成)

## 3. 直近の試運転結果サマリー

| 試運転 | バッチ | 動画化率 | 主要観察 |
|---|---|---|---|
| 7-K | F-13.B | 100% (3/3) | FIFA + Gaza×2、rescue path 完全廃止後初の全 Slot 動画化成功 |
| F-12-B-1 | F-12-B-1 | — | cls-56c4197b6fd2 米イスラエル隠密作戦、視聴者ファースト改善確認 (固有名詞補足・話し言葉化) |
| F-12-B-1-extension | F-12-B-1-extension | 未実施 | LLM 出力依存のため未実施、抽象比喩軽減は継続観察項目 |
| 7-J | F-15 / F-16-A | 0% | rescue 発動で動画化ゼロ → F-13-B (rescue 完全廃止) のトリガー |
| 7-I | F-16-A | 67% (2/3) | Slot-3 (UAE OPEC) が MAX_PUBLISHES_PER_DAY で skip → F-16-A 着手 |

## 4. Hydrangea コンセプト防衛機構の現状 (4+1 層)

| 層 | バッチ | 場所 | 役割 | 状態 |
|---|---|---|---|---|
| F-1 | F-1 / F-1.5 | EditorialMissionFilter | 編集ミッション適合度で score 算出 (>= 45.0 で通過) | ✅ 稼働中 |
| F-2 | F-2 / F-5 | FlagshipGate (Hydrangea コンセプト整合) | 海外発の重要ニュースを優先 | ✅ 稼働中 |
| F-13.B | F-13.B | JpCoverageVerifier (rescue 完全廃止 + Web 検証) | JP 報道カバレッジを 27 ドメイン WL で検証 | ✅ 稼働中 |
| F-5 | F-5 | FlagshipGate 下流救済 | 上流ガードを通過した候補の最終整合 | ✅ 稼働中 |
| **F-13 (隠れ層)** | F-13 | script_writer.py:865-895 quality_floor_miss bypass | analysis_result があれば appraisal の [抑制] を上書き | ⚠️ DECISION_LOG / EDITORIAL_MISSION_FILTER_DESIGN に未記録 (DISCUSSION_NOTES #7 参照) |

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

## 6. 不変原則 5 つ (リマインダ)

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
  (F-doc-protocol / F-state-protocol 等の文書プロトコル整備の動機)
- **「負の遺産残さないように」** — 不整合・乖離を早期解消
  (本バッチで不変原則 2 の実装乖離を是正)
- **「カズヤの手作業はバッチプロンプトのコピペ 1 回のみ」** — 引き継ぎ
  プロンプト 2806 行の手作業再構築を排除する仕組みとして CURRENT_STATE.md /
  DISCUSSION_NOTES.md を導入

## 8. 関連ドキュメントへの導線

- 過去の決定の経緯 → `docs/DECISION_LOG.md`
- 残課題リスト → `docs/FUTURE_WORK.md`
- 議論中の未確定メモ → `docs/DISCUSSION_NOTES.md`
- バッチ運用ルール → `docs/BATCH_PROTOCOL.md`
- アーキテクチャ全体像 → `docs/ARCHITECTURE.md`
- 技術的負債リスト → `docs/TECH_DEBT.md`
- リファクタ計画 → `docs/REFACTORING_PLAN.md`

---

*このドキュメントは F-state-protocol (2026-05-01) で導入。
 Claude Code がバッチ完了時に全置換更新する運用 (BATCH_PROTOCOL.md Task 5 参照)。
 F-state-protocol-supplement (2026-05-02) で「次バッチ候補」セクションを最小更新し、
 Phase A.5-3a-verify ロードマップを反映。*
