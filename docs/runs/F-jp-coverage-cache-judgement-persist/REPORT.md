# F-jp-coverage-cache-judgement-persist 完了レポート

batch: F-jp-coverage-cache-judgement-persist (Phase A.5-3a-verify ゲート完了後 **17 つ目 / 1-O**)
日付: 2026-05-26
ブランチ: feature/F-jp-coverage-cache-judgement-persist (main HEAD `d6ed916` から作成)

---

## 1. バッチ概要

3 AI 三角測量 (ChatGPT + Gemini) のレビューで両者独立に指摘された **F-13.B
cache の監査欠落** を根本治療。`JpCoverageResult.llm_judgement` /
`llm_judgement_text` (B-3' で導入) が 24h SQLite cache (`jp_coverage_cache`) に
永続化されておらず、cache round-trip でフィールド値が失われていた。

**案 A (DB schema 拡張)** を採用し、cache 層で round-trip を lossless 化。
判定ロジック (B-3' if/else)・既存メソッド contract は完全不変。

---

## 2. 影響範囲サマリー (Task B、★ プロンプト記載の実害を grep + 実測で訂正)

| プロンプト記載 | grep + コード精読 + 本番 DB 実測での実態 |
|---|---|
| cache hit で llm_judgement=None → 後方互換パス (沈黙=uncertain) → **Recall 劣化リスク** | ❌ **発生しない**。`verify()` は cache hit 時 `_get_cached()` を**そのまま return**、`has_jp_coverage` を `llm_judgement` から**再計算しない**。B-3' 安全装置の効果は boolean として保存済で完全復元。 |
| evidence/run_summary での**監査不能化** | △ 誤解を招く。`llm_judgement` は src/ で verifier 以外 0 参照、cache hit/miss いずれでも artifact に書かれていない (main.py は has_jp_coverage を log のみ)。**失う既存監査トレースは存在しない**。 |

- **真の defect**: cache round-trip が `llm_judgement` / `llm_judgement_text` の
  **フィールド値 (判定根拠テキスト) を失うデータ忠実性の不整合**。実害は潜在的・
  将来面 (将来 evidence 監査を足したとき cache hit/miss で値が割れる土台問題)。
- 本番 DB 実測 (24 行): B-3' 安全装置発火行 (False + WL マッチ) = **1 行 (4.2%)**、
  その行も has_jp_coverage は正しく保存済。
- `verify_two_stage()` は **cache 経路なし** → broad/angle_llm_judgement は cache
  対象外 (かつ本番未配線)。対象は `JpCoverageResult.llm_judgement` /
  `llm_judgement_text` のみ。
- 詳細: `cache_schema_audit.json` / `cache_hit_behavior.json` / `impact_estimate.json`。

---

## 3. CP-1 で確定した実装方針

- **案 A (DB schema 拡張、クラウド推奨)**: cache を発生源で lossless 化 =
  「対症療法じゃなく根本治療」。
- 案 B (score_breakdown 経由で evidence 監査トレース新設) は **バグ修正でなく
  新機能** + 案 A 無しでは cache hit で None 注入 → 不整合新設のため、別バッチ
  FUTURE_WORK 化 (F-evidence-jp-coverage-audit-trail)。案 C (A+B) はスコープ膨張で却下。
- 実害訂正受容 + 緊急度 ★★ → ★ 下方修正 (バッチ中止せず)。
- 3 案比較の詳細: `implementation_options.md`。

---

## 4. 改修 diff サマリー (機能ロジック変更なし、既存メソッド contract 完全維持)

### `src/storage/db.py`
- `jp_coverage_cache` DDL に `llm_judgement TEXT` / `llm_judgement_text TEXT` 追加 (fresh DB 用)。
- idempotent migration `_migrate_jp_coverage_cache(conn)` 新規: `PRAGMA table_info`
  で欠列のみ `ALTER TABLE ADD COLUMN ... TEXT` (DEFAULT NULL)。`init_db` に組込。
  DDL は `CREATE TABLE IF NOT EXISTS` のため作成済 DB に列が増えない問題を吸収。

### `src/triage/jp_coverage_verifier.py` (不変原則 3 例外)
- `_get_cached()`: SELECT に 2 列追加、`JpCoverageResult` 復元に
  `llm_judgement=row[7], llm_judgement_text=row[8]`。
- `_save_cache()`: INSERT 列 + values に 2 個追加。
- **判定パス (`verify()` / `verify_two_stage()` の has_jp_coverage 決定) は git diff
  上 0 行変更** (decision-path 不変を確認)。

詳細: `diff_summary.md`。

---

## 5. baseline + golden + 試運転結果

### Task D-1 — baseline
- **1417 passed 維持** (既存 cache テスト `test_f13b_rescue_abolition.py` は
  has_jp_coverage/matched_tier のみ assert、列追加で非破壊)。

### Task D-2 — golden Recall 非劣化 (`golden_accuracy.json`)
- **決定パス不変性の証明**で確認: decision-path diff = 空 + B-3' 判定テスト
  27 passed。baseline metrics (Recall 1.0000 / Precision 0.8889 / FN 0) と同値。
- live golden 再測定は **非採用** (Gemini Grounding run 間分散による confound +
  canonical REPORT 上書き副作用 + 測定 script の自前 temp schema が改修を
  exercise しない)。カズヤ承認下で実行可能。

### Task D-3 — 1 batch 試運転 (`trial_run_summary.json`)
- ingestion: batch 20260526_035220、normalized 47 files / new 844。
- **run 1 (full pipeline)**: exit 0 / status=completed / 3 slots published
  (Slot-1 video + Slot-2/3 article) / script via gemini (not fallback) / retries=0 /
  Traceback・ERROR・404 = 0。F-13.B 3 件:
  - Slot-1 cls-0741c099c775: has_jp=True / tier_1 / **llm_judgement=uncertain** 永続化
  - Slot-2 cls-c87c121e9def: has_jp=False / tier_2 / **llm_judgement=no_match** = B-3'
    安全装置発火、判定根拠テキスト `該当する記事はありません` も永続化
  - Slot-3 cls-49450ad2fefd: has_jp=True / tier_1 / **llm_judgement=uncertain** 永続化
  - 改修前はこれら 3 件が cache 上 NULL になっていた。
- **run 2 (verifier replay、同 event_id、API call が来たら fail する client)**:
  3 件すべて **cached=True + run 1 と完全一致 + API call 0** = cache hit 時の
  llm_judgement 忠実復元を本番フローで実証。
  - 注: literal な 2 回目 `main --mode normalized` は run 1 が 3 event を pool で
    consumed にするため同一 event の cache hit を再現しない (別 event を選定) →
    verifier replay が技術的に正しい検証。
- 防衛機構 5 層異常なし、動画化候補消失なし、即停止条件非該当。

---

## 6. 監査トレース確保の確認

- 本バッチ (案 A) は **cache の round-trip 忠実性**を確保 = cache hit でも
  `llm_judgement` / `llm_judgement_text` が正しい値で復元される (run 2 で実証)。
- ただし現状 `llm_judgement` は evidence.json / run_summary.json に**書き出されて
  いない** (main.py は log のみ)。evidence への監査トレース新設は本バッチスコープ外
  = 案 B 単独として FUTURE_WORK (F-evidence-jp-coverage-audit-trail) に切り出し。
  案 A が先に入ったことで、将来その監査を足しても cache hit/miss で値が割れない
  土台が整った。

---

## 7. 残課題

- **F-evidence-jp-coverage-audit-trail** (★中): score_breakdown 経由で
  `jp_coverage_verification` を evidence.json に出す案 B 単独。新機能のため別バッチ。
- **scripts/verify_jp_coverage_measure.py の inline schema doc-drift** (★低):
  自前 `_TEMP_DB_SCHEMA` が db.py DDL を複製しており本バッチの 2 列追加で乖離
  (scripts/ は本バッチ変更不可のため未修正)。fresh モード accuracy には影響なし。
- DB migration の本番運用: idempotent + 後方互換のため追加運用作業なし
  (init_db が startup で自動適用、本バッチで実本番 DB 適用済)。

---

## DECISION_LOG.md への追加内容

`2026-05-26: F-jp-coverage-cache-judgement-persist` エントリを追加。背景 (3 AI
三角測量レビュー)、CP-1 判断 (案 A 採用 + 実害訂正受容 + 緊急度 ★★→★ +
クラウド誤り 10 の 2 回目発生記録)、結果 (2 ファイル改修・baseline 1417 維持・
migration 検証・golden 不変性証明・試運転 cache hit 実証)、不変原則 3 例外条件
5 点全充足を記載。あわせて前バッチ F-f1-locale-key-fix のコミットハッシュを
`ddc2117` (feat) / `d6ed916` (merge) で追記。

## FUTURE_WORK.md への変更内容

- 完了済みに移動した項目: F-jp-coverage-cache-judgement-persist (F-13.B cache 永続化)
- 緊急度 高に追加した項目: なし (F-script-writer-target-enemy-fix は既存維持)
- 緊急度 中に追加した項目: F-evidence-jp-coverage-audit-trail (案 B 単独 = evidence 監査トレース新設)
- 緊急度 低に追加した項目: scripts/verify_jp_coverage_measure.py inline schema doc-drift 解消

## DISCUSSION_NOTES.md の整理結果

- 4-A 新規追加: 「2026-05-26: 3 AI 三角測量レビューで F-13.B cache 監査欠落を発見、
  根本治療実施 (案 A)」(ステータス: 昇格候補(DECISION_LOG) → 本バッチで Resolved)。
- クラウド誤り 10 の **2 回目発生**を同エントリ末尾に追記 (再番号付け不要、本質は
  Project Knowledge / 外部指摘の鵜呑み = 検証なしの仮説受容)。
- 既存エントリ再評価: 本バッチ起因の新規昇格・アーカイブなし。

## CURRENT_STATE.md の全置換更新

17 つ目のバッチ (1-O) として全置換更新。main HEAD / baseline 1417 / 防衛機構
F-13.B 行 (llm_judgement cache 永続化済) / 次バッチ候補
(1st F-script-writer-target-enemy-fix / 2nd F-gemini-quality-tier-poc /
3rd Phase A.5-3b 第一作起案) を最新化。

---

## 自分で判断した内容

- **判断 1 (実装スコープ)**: CP-1 で案 A 確定。verify_two_stage は cache 経路なし
  のため対象外 (broad/angle_llm_judgement は永続化しない) と判断 = 最小改修。
- **判断 2 (migration 方式)**: DDL が `CREATE TABLE IF NOT EXISTS` で作成済 DB に
  列が増えないため、`init_db` 内に idempotent な PRAGMA + ALTER TABLE ADD COLUMN
  migration を新設 (DEFAULT NULL = 既存行は従来挙動と一致 = 後方互換)。新列は
  ALTER append 順と一致させるため DDL でも末尾配置。
- **判断 3 (golden D-2)**: live 再測定は本改修の効果を測れず confound する +
  canonical REPORT 上書き副作用 + script の自前 schema が改修を exercise しない
  ため、決定パス不変性の証明を primary verification とした (クラウド誤り 10 の
  「検証なしの混同を避ける」原則)。live 実行はカズヤ承認下で可能と明記。
- **判断 4 (run 2 方式)**: literal な 2 回目 full run は pool consumed で同一 event の
  cache hit を再現しないため、verifier replay (API call が来たら fail する client) で
  cache hit + 結果一致 + 0 API call を厳密に検証した。
- **判断 5 (テスト追加なし)**: カズヤ CP-1 スコープが baseline 1417 維持を明示し、
  検証方法を試運転に指定したため、新規テストは追加せず 1417 を維持。cache
  round-trip 回帰テストの新設は任意の follow-up として残課題化。

## 不変原則違反 / 触ってはいけないファイルへの変更要望

- なし。不変原則 3 例外条件 5 点全充足 (jp_coverage_verifier.py)。`src/storage/db.py`
  は不変原則の保護対象外 (storage 層)。

## BATCH_PROTOCOL Task 1-5 実施結果

- Task 1 (DECISION_LOG): 本バッチエントリ追加 + 前バッチ commit hash 追記 → 実施済。
- Task 2 (FUTURE_WORK): 完了移動 + 新規 2 件 (中/低) → 実施済。
- Task 3 (本セクション): 完了レポートに更新内容明記 → 本レポート。
- Task 4 (DISCUSSION_NOTES): 4-A 新規 + クラウド誤り 10 の 2 回目発生 追記 → 実施済。
- Task 5 (CURRENT_STATE): 全置換更新 (17 つ目バッチ) → 実施済。

## 次バッチへの引継ぎ事項

- 次バッチ最有力: F-script-writer-target-enemy-fix (★★★高、Gemini 独自指摘)。
- F-evidence-jp-coverage-audit-trail (案 B、evidence 監査トレース新設) は本バッチで
  土台 (cache lossless 化) が整ったので着手可能 (★中)。
- Project Knowledge 最新化 reminder: 本バッチで docs を更新済。新チャット移行前に
  claude.ai 側の docs を再アップロードすること。

## 環境構築・依存追加

- requirements.txt 追加: なし。
- 環境変数追加: なし。
- DB schema: jp_coverage_cache に 2 列追加 (idempotent migration、後方互換)。
