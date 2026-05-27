# F-docs-update-chatgpt-round2-and-error10 完了レポート

**バッチ種別**: docs-only (改修なし、grep + コード精読のみ)
**完了日**: 2026-05-27
**ブランチ**: `feature/F-docs-update-chatgpt-round2-and-error10` (main `2f99ebd` から作成)
**baseline**: 1417 passed 維持 (改修なしのため自動維持、Task A で確認済 = 99.31s)

---

## 1. バッチ概要

ChatGPT/Gemini への Gemini モデル布陣セカンドオピニオン依頼に対し、ChatGPT が当該依頼を
保留して **Phase A.5-3b 第一作前のコードレビュー Round 2 (7 指摘)** を返却した。本バッチは
その 7 指摘を docs 正本との **grep 裏取り照合** で精査し、以下を実施した (★ docs-only、改修なし):

1. **新規 3 タスクを FUTURE_WORK に追加** + 既存 F-periodic-health-check のスコープ拡張
2. **クラウド誤り 10 系統を CLAUDE.md に明文化** (1-N / 1-O で 2 回発生 → 1-P / 1-P.5 で 2 回連続回避)
3. DISCUSSION_NOTES に統合エントリ追加 + 既存クラウド誤り 10 エントリの再評価

★ **本バッチの核心観察**: ChatGPT Round 2 でも **クラウド誤り 10 系統 (検証なしの仮説受容)** が
発生した。古い Project Knowledge 由来で「既に解消済み」の問題を「新規発見」として指摘した
半数 (2/4 の REAL 候補) があり、「外部 AI レビュー指摘も grep で検証してから起案する」作法の
重要性が再証明された。

---

## 2. Task B — ChatGPT Round 2 指摘の grep 裏取り結果

| # | ChatGPT 指摘 | 緊急度 | grep verdict | 対応 |
|---|---|---|---|---|
| 1 | F-13.B 結果が evidence に残らない | 高 | — | ✅ 既に FUTURE_WORK 登録済 = F-evidence-jp-coverage-audit-trail |
| 2 | title_generator.py で perspective_gap 誇大タイトルリスク | 高 | **REAL** | ❌ **新規** = F-title-guard-coverage-claim-policy ★★高 |
| 3 | F-1 EditorialMissionFilter の sources_by_locale キー参照ズレ | 高 | **RESOLVED** | ✅ F-f1-locale-key-fix (1-N / 2026-05-25) で修正済 (古い PK) |
| 4 | F-13.B の llm_judgement が cache hit 時に消える | 中 | **RESOLVED** | ✅ F-jp-coverage-cache-judgement-persist (1-O / 2026-05-26) で修正済 (古い PK) |
| 5 | LLM factory/config に model drift + retry 観測リスク | 中 | — | ⚡ F-periodic-health-check スコープ拡張 |
| 6 | analysis の max_output_tokens default 2000 不足 | 中 | **REAL** (env 可) | ❌ **新規** = F-analysis-max-tokens-tune ★中 |
| 7 | JobRecord の AV path が DB に保存されない | 低 | **REAL** | ❌ **新規** = F-job-record-av-path ★低 |

### 指摘 3 (解消済確認) — grep_evidence_3_4.json
- `src/triage/editorial_mission_filter.py:163` = `sources_by_locale.get("japan", [])`、L166 で非 japan 合算。
- 旧バグの `get("jp")`/`get("en")` は **残存ゼロ** = F-f1-locale-key-fix (2026-05-25) で根本治療済。

### 指摘 4 (解消済確認) — grep_evidence_3_4.json
- `src/storage/db.py:120-121` = `llm_judgement` / `llm_judgement_text` 列 + L134-153 idempotent migration。
- `src/triage/jp_coverage_verifier.py` `_get_cached` (L673-721) / `_save_cache` (L724-748) が 2 列対応。
- = F-jp-coverage-cache-judgement-persist (2026-05-26、案 A) で永続化済。

### 指摘 2 (新規タスク化根拠) — title_guard_analysis.json
- `src/generation/title_generator.py` は `is_strong=True` 時に絶対的 silence_gap 表現を出力:
  - L136 「日本では報道されない{topic}の視点」/ L149・L203 「日本では報道されない{topic}」/ L380・L394 「日本で無報道」
- `is_strong` ゲート (`_is_strong_evidence` L41-72) は **`editorial:perspective_gap_score >= 3.0`** でも真になる (L66/L70)。
- = 系統 2 (perspective_gap = 候補A cls-6889e9e1c7ac) の事象でも絶対的 silence_gap 表現が選択され得る。
  広範事件 (9,600 人虐待) は AFPBB 等で日本報道済 = 事実誤認リスク = ADR-0003「誇大表現回避」と衝突、
  Hydrangea ミッション「検証可能な事実で殴る」に矛盾。
- `coverage_claim_policy` / `title_layer_guard` / `publish_gate` / `manual_poc/` はいずれも **0 件** = グリーンフィールド。

### 指摘 6 (新規タスク化根拠、起案前提訂正) — analysis_tokens_analysis.json
- default 2000 は `src/llm/factory.py:516` の `os.getenv("ANALYSIS_LLM_MAX_TOKENS", "2000")` フォールバックのみ。
- ★ **起案前提訂正**: `src/shared/config.py` に ANALYSIS_LLM_MAX_TOKENS 定数は **0 件** = 起案プロンプトの
  「config.py default 2000」は不正確。default 化の改修箇所は config.py でなく **factory.py:516**。
- docs 正本は 4096 推奨 (`docs/PARTICULAR_ANGLE_DEFINITION.md:512` + `scripts/extract_particular_angle.py:253`)。
- env 指定 (`ANALYSIS_LLM_MAX_TOKENS=4096`) で改修なしに対応可能。

### 指摘 7 (新規タスク化根拠) — job_record_analysis.json
- `src/shared/models.py:335` JobRecord は `voiceover_path` (L342) / `review_mp4_path` (L343) を持つ。
- `src/storage/db.py:14` jobs DDL は `script_path`/`article_path`/`video_payload_path` (L18-20) のみ、
  `save_job()` (L189) の INSERT/UPSERT も 3 path のみ = AV path は **DB 未保存**。
- 現状 run_summary / manifest で代替追跡可 = 緊急度 低。Phase A.5-3c DB schema 整理に統合。

---

## 3. 新規 3 タスク + スコープ拡張の起案内容 (Task C / D)

### C-1: F-title-guard-coverage-claim-policy ★★高 (緊急度 高、Phase A.5-3b 第一作着手前必須)
- coverage_claim_policy 構造データ (`allowed_claim_level: perspective_gap_only` /
  `forbidden_title_claims: [absolute_silence_gap, event_not_reported_in_japan]`) を manual_poc/ 配下に追加
  + 生成後 title_layer_guard で整合チェック。各論プロンプト制御でなく構造データ = クラウド誤り 9 回避と整合。

### C-2: F-analysis-max-tokens-tune ★中 (緊急度 中)
- Phase A.5-3b 実行時に env `ANALYSIS_LLM_MAX_TOKENS=4096` 指定 (改修なし) → X1 配線時に factory.py:516 default 化判断。

### C-3: F-job-record-av-path ★低 (緊急度 低、Phase A.5-3c 以降)
- jobs DDL + save_job() を JobRecord 全フィールド対応に拡張 + idempotent migration。Phase 1-C と並走整理可能。

### D: F-periodic-health-check スコープ拡張 (指摘 5)
- ★ **起案前提訂正**: 起案プロンプトは受け皿を「F-pipeline-health-check (1-Q.5)」と呼称したが、grep で
  該当エントリは **存在せず** = health-check の正本は **F-periodic-health-check** (緊急度 中)。スコープが
  503/fallback 検知で一致するため、新規重複エントリを作らず本エントリにスコープ統合した (最も保守的な選択)。
- 追加スコープ: model_role 解決の runtime snapshot (tier fallback 検出) + BudgetTracker の retry count
  観測強化。工数 +1-2h。

---

## 4. クラウド誤り 10 系統の CLAUDE.md 明文化 (Task E)

- CLAUDE.md「クラウド誤り」セクションの **誤り 9 直後** に「クラウド誤り 10」を新規挿入。
  既存 CLAUDE.md は誤り 9 のみ詳細記載 (誤り 1-7 は DISCUSSION_NOTES 参照、誤り 8 は欠番) だったため、
  誤り 9 と同じ bold-label 構造 (誤り / 動機 / 発生実例 / 害 / 回避作法 / メタ的含意 / カズヤ哲学 / 出典) に揃えた。
- **発生実例 4 件 + 外部 AI 観察**:
  - 1 回目: F-f1-locale-key-fix (2026-05-25、false positive 誤認)
  - 2 回目: F-jp-coverage-cache-judgement-persist (2026-05-26、Recall 劣化リスク鵜呑み → CP-1 訂正)
  - 回避: F-script-writer-target-enemy-fix-investigate (1-P) / F-gemini-3.5-flash-api-audit (1-P.5)
  - ★ ChatGPT Round 2 (2026-05-27): **外部 AI 側でも誤り 10 系統発生** (解消済 2 件を新規発見と誤認)
- 他セクション (役割定義・バッチ運用原則・LLM 呼び出し方針 等) は不変。誤り 10 追加に伴う
  最小限の整合更新のみ実施: 最終更新日 / 導線表「クラウド誤り 1-7 / 9 / 10」/ 冒頭注記の登録履歴。

---

## 5. ★ ChatGPT 側でも誤り 10 系統が発生した観察記録

ChatGPT Round 2 の 7 指摘のうち、指摘 3 (F-1 locale key) と指摘 4 (F-13.B cache 永続化) は
いずれも **修正前の古い Project Knowledge スナップショット** に基づき「新規発見」として提示された
が、grep で **既に根本治療済み** と確定した。これは「整合の説明であって検証ではない」原則の
適用対象が外部 AI レビューにも及ぶことを示す追加実例である:

- **含意**: 外部 AI (3 AI 三角測量 / ChatGPT Round N / Gemini Round N) も Project Knowledge の
  鮮度に依存し、検証なしの仮説受容 (クラウド誤り 10 系統) を起こす。Claude Code 側で grep 裏取り
  してから起案する作法が、外部レビューの false alarm をフィルタする防壁として機能した。
- 本バッチでは起案者前提も 2 点訂正した (指摘 6 の default 箇所 = config.py でなく factory.py:516、
  指摘 5 の受け皿 = 存在しない F-pipeline-health-check でなく正本 F-periodic-health-check)。

---

## 6. 自分で判断した内容

- **判断 1 (F-pipeline-health-check 呼称)**: 起案プロンプトが指摘 5 の受け皿を
  「F-pipeline-health-check (1-Q.5)」と呼んだが grep で該当エントリ不在を確認。CLAUDE.md判断ルール 4
  (最も保守的 = 既存に影響少ない) に従い、health-check の正本 **F-periodic-health-check** に
  スコープ統合 (重複エントリ非作成)。
- **判断 2 (指摘 6 default 箇所)**: config.py に定数 0 件を grep 確認 → 起案文の「config.py default」を
  factory.py:516 に訂正して FUTURE_WORK に反映。
- **判断 3 (CLAUDE.md 誤り 10 の構造)**: 既存 CLAUDE.md は誤り 9 のみ詳細記載 (誤り 1-8 非詳細)。
  起案文の bullet 形式でなく、既存パターン (誤り 9 の bold-label 構造) に揃えた (CLAUDE.md判断ルール 3)。
- **判断 4 (CURRENT_STATE 全置換)**: docs-only バッチのため §3 試運転 / §4 防衛機構 は実態不変 = 記述維持。
  header / §0 / §1 / §2 (roadmap) / §7 / §8 / footer を最新化 (BATCH_PROTOCOL Task 5 の趣旨 = 現況反映)。

---

## 7. 不変原則違反 / 触ってはいけないファイルへの変更要望

- **なし**。`src/` `tests/` `configs/` `scripts/` `.env` `.env.example` = **0 行変更** (git status で確認済)。
  CLAUDE.md はクラウド誤り 10 明文化対象 (不変原則対象外)。docs/ 配下のみ更新 + docs/runs/ 新規。
- baseline **1417 passed 維持** (改修なしのため自動維持)。不変原則 1-5 完全遵守 (例外条件適用なし)。

---

## 8. BATCH_PROTOCOL Task 1-5 適用内容

- **Task 1 (DECISION_LOG)**: 本バッチエントリを末尾に追加。★ 前バッチ F-gemini-3.5-flash-api-audit の
  `コミット: (push 後追記)` を実ハッシュ `de06887` (feat) / `2f99ebd` (merge) で追記更新。
- **Task 2 (FUTURE_WORK)**: 新規 3 タスク追加 (高/中/低) + F-periodic-health-check スコープ拡張 +
  本バッチ完了済み移動 (調査結果サマリ明記)。header 最新化。
- **Task 3 (REPORT)**: 本セクション。
- **Task 4 (DISCUSSION_NOTES)**: 4-A 新規 1 件 (ChatGPT Round 2 統合、Resolved/タスク化) +
  4-B 既存クラウド誤り 10 エントリのステータスを「CLAUDE.md 正本化」反映に更新。header 最新化。
- **Task 5 (CURRENT_STATE)**: 全置換更新。header / §0 / §1 (main HEAD 2f99ebd) / §2 (20 つ目バッチ 1-P.6、
  roadmap 1-P.6 + 1-Q.5 行追加、次バッチ候補に新規タスク反映) / §7 / §8 / footer を最新化。

---

## 9. 次バッチへの引継ぎ事項

- **次バッチ最有力**: F-gemini-quality-tier-poc (1-Q、Narrative primary 確定) → X1 (新ルート本番配線、
  target_enemy 解消統合) → **F-title-guard-coverage-claim-policy (第一作着手前必須)** → Phase A.5-3b 第一作起案。
- F-analysis-max-tokens-tune は Phase A.5-3b 実行時に env 指定で先行回避 (改修なし)、X1 配線時に default 化判断。
- F-job-record-av-path は Phase A.5-3c の DB schema 整理 (Phase 1-C と並走) に統合。
- Project Knowledge 最新化 reminder: 本バッチで docs 5 件 + CLAUDE.md を更新したため、別チャット移行前に
  claude.ai の Project Knowledge を手動最新化推奨 (BATCH_PROTOCOL「Project Knowledge 最新化運用ルール」)。

---

## 10. 環境構築・依存追加

- requirements.txt 追加: なし
- 環境変数追加: なし (F-analysis-max-tokens-tune の `ANALYSIS_LLM_MAX_TOKENS=4096` は Phase A.5-3b 実行時の
  将来 env 指定であり、本バッチでは .env を 0 行変更)
