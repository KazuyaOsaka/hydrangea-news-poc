# 実装方針 3 案の比較 (Task B-4)

batch: F-jp-coverage-cache-judgement-persist
作成: 2026-05-26 (Task B 完了時点、CP-1 報告用)

> ★ クラウド誤り 10 を踏まえ、本比較は grep + コード精読で確認した**実態**に基づく。
> バッチプロンプト記載の「Recall 劣化リスク」「監査不能化」は実態と乖離していたため、
> impact_estimate.json / cache_hit_behavior.json で訂正済み。本案比較もその訂正を前提とする。

---

## 前提となる訂正済み実態 (impact_estimate.json / cache_hit_behavior.json より)

- `verify()` は cache hit 時 `_get_cached()` の結果を**そのまま return** し、`has_jp_coverage` を
  `llm_judgement` から再計算しない。→ B-3' 安全装置の**効果 (has_jp_coverage=False) は cache hit でも完全保存**。
  **Recall 劣化は発生しない**。
- cache round-trip で失われるのは `llm_judgement` / `llm_judgement_text` の**フィールド値 (= 判定根拠テキスト) のみ**。
- `llm_judgement` は src/ 全体で verifier 以外から参照されておらず、evidence.json / run_summary.json にも
  **cache hit / miss いずれでも書き出されていない** (main.py は has_jp_coverage を log するのみ)。
- 本番 DB 実測: 24 行中、B-3' 安全装置が発火した行 (False + WL マッチ) は **1 行 (4.2%)**。その 1 行も
  `has_jp_coverage=False` は正しく cache 保存されている。
- `verify_two_stage()` には**そもそも cache 経路が無い** → `broad/angle_llm_judgement` は cache で失われない
  (かつ本番未配線)。本バッチの cache 永続化対象は `JpCoverageResult.llm_judgement` / `llm_judgement_text` のみ。

→ 結論: 「真のバグ (cache round-trip のデータ忠実性欠落)」ではあるが、害は**潜在的・将来面**。
   根本治療としては「cache を lossless にする」= 案 A が素直。

---

## 案 A (Gemini 推奨): DB schema 拡張 + cache 永続化

**改修内容**
- `src/storage/db.py` の `jp_coverage_cache` DDL に `llm_judgement TEXT` / `llm_judgement_text TEXT` を追加
- 既存本番 DB (24 行) 向けに idempotent な `ALTER TABLE ADD COLUMN ... ` migration を `init_db` に追加
  (列存在チェック → 無ければ ADD COLUMN、DEFAULT NULL で後方互換)
- `src/triage/jp_coverage_verifier.py` の `_save_cache()` の INSERT に 2 列追加、`_get_cached()` の SELECT に
  2 列追加 + `JpCoverageResult(..., llm_judgement=, llm_judgement_text=)` で復元

**改修範囲**: `db.py` (DDL + migration) + `jp_coverage_verifier.py` (2 private メソッド)。計 2 ファイル。

**不変原則 3 例外条件 5 点該当性** (verifier 改修):
1. 実装バグ修正: ✅ B-3' 導入時にフィールド永続化が欠落した設計不整合の修正
2. 設計変更ではない: ✅ 判定ロジック (B-3' if/else)・`verify()`/`verify_two_stage()` 戻り値型不変、cache 列追加 + シリアライズ拡張のみ
3. 既存メソッド contract 完全維持: ✅ public signature 不変、private メソッドの内部拡張のみ
4. baseline 維持: ✅ (Task D で確認予定。既存 cache テスト `test_f13b_rescue_abolition.py` は `has_jp_coverage`/`matched_tier` のみ assert、列追加で破壊されない)
5. カズヤ承認: CP-1 で取得
→ **5 点全充足見込み**。db.py は不変原則対象外 (storage、保護リスト外)。

**migration リスク**: 低。`ADD COLUMN ... DEFAULT NULL` は SQLite で安全 (テーブル再構築不要)。既存 24 行は NULL =
現状の cache hit 挙動 (llm_judgement=None) と完全一致 → 後方互換。

**後方互換性**: 完全。新列が無い古い DB に対しても列存在チェック付き migration で吸収。

**カズヤ承認難度**: 低〜中。verifier への不変原則 3 例外適用が必要だが、F-f1-locale-key-fix / F-jp-coverage-improve と
同種 (純粋なバグ/不整合修正、ロジック不変) で前例あり。

---

## 案 B (ChatGPT 推奨): score_breakdown 経由で evidence 証跡化

**改修内容**
- cache には保存せず、`main.py` で `_jp_coverage_result` の has_jp_coverage / matched_domains / matched_tier /
  llm_judgement を `score_breakdown["jp_coverage_verification"]` に積む経路を追加
- evidence_writer は `score_breakdown` をそのまま保存する (writer 改修なし) ので、evidence.json に証跡が残る

**改修範囲**: `main.py` (score_breakdown 注入箇所)。evidence_writer は不変。

**重大な問題点 (実態確認で判明)**:
- ★ **案 B 単独では本バッチの defect を解消しない**。cache hit 時 `_jp_coverage_result.llm_judgement` は **None のまま**
  なので、score_breakdown に注入される値も cache hit では None。→ cache hit 行は llm_judgement=None を evidence に
  書き、cache miss 行は実値を書く、という**不整合な監査トレースを新規に作り出す**。
- ★ そもそも「監査トレースを evidence に新設する」のは**バグ修正ではなく新機能**。不変原則 3 例外条件 1
  (実装バグ修正) に該当しない。クラウド誤り 9 (各論コントロール/スコープ膨張) の観点でも、本バッチ (cache 永続化)
  とは別議論にすべき。
- main.py 改修は不変原則対象外だが、score_breakdown の構造拡張は evidence schema への影響があり波及範囲が広い。

**不変原則 3 例外条件該当性**: 該当しない (バグ修正ではなく機能追加)。別バッチでの根本議論対象。

**migration リスク**: なし (DB 不変)。

**後方互換性**: evidence.json に新キー追加 = 後方互換だが、cache hit/miss で値が割れる不整合を内包。

**カズヤ承認難度**: 中。新機能であり、かつ案 A 無しでは cache hit で破綻するため、単独採用は非推奨。

---

## 案 C (両方併用): cache 永続化 (A) + score_breakdown 注入 (B)

**改修内容**: 案 A + 案 B を両方実施。cache を lossless にした上で evidence に監査トレースを出す。

**改修範囲**: `db.py` + `jp_coverage_verifier.py` + `main.py`。計 3 ファイル + evidence schema 影響。

**メリット**: 監査性が最大 (cache hit でも正しい llm_judgement が evidence に残る)。

**デメリット**:
- バグ修正 (A) と新機能 (B) を 1 バッチに混載 → 不変原則 3 例外条件 2 (設計変更ではない/機能追加しない) に
  抵触するパートを含む。
- スコープ膨張。クラウド誤り 9 (善意のルール/機能累積) の典型パターン。
- 「監査トレースは本当に今必要か」の判断 (実態: 現状 llm_judgement は誰も読んでいない) を飛ばして実装する形になる。

**カズヤ承認難度**: 中〜高 (スコープ膨張の是非判断が必要)。

---

## クラウドの推奨: **案 A**

**根拠**:
1. 本バッチの defect の**根本原因**は「cache round-trip が `llm_judgement` を失う」こと。案 A はこれを
   発生源 (cache 層) で lossless 化する = 「対症療法じゃなく根本治療」。
2. 実態訂正 (Recall 劣化なし / 既存監査トレースは存在しない) を踏まえると、**今必要なのは「将来 evidence 監査を
   足したときに cache hit/miss で値が割れない土台を作ること」**であり、それは案 A が提供する。案 B は土台 (A) 抜きでは
   むしろ不整合を新設してしまう。
3. 案 B (evidence 監査トレースの新設) は**バグ修正ではなく機能追加**。スコープ規律 (クラウド誤り 9) と
   不変原則 3 例外条件の観点から、本バッチに混ぜず**別バッチ (FUTURE_WORK)** に切り出すのが筋。カズヤが
   「監査を今すぐ evidence に出したい」と判断した場合のみ案 C に拡張。
4. 案 A は 2 ファイル・private メソッド + DDL + idempotent migration の最小改修で、不変原則 3 例外条件 5 点を
   素直に満たし、baseline / golden 非劣化を担保しやすい。

**留保 (カズヤ判断を仰ぐ点)**:
- 実態として llm_judgement は現在どこからも読まれていない。それでも「将来の audit / lossless 化」目的で
  案 A を今やる価値があるか (= 緊急度 ★★ 維持か、それとも ★ に下げて後回しか) はカズヤ判断。
  クラウドの見解: 改修が最小・低リスクで「負債を残さない」哲学に合致するため、**今やる価値あり (案 A 推奨)**。
- 監査トレースを evidence に出す案 B は、必要なら別バッチ化を提案 (FUTURE_WORK ★★/★)。

---

## 不変原則 3 例外条件 5 点 — 案別サマリー

| 条件 | 案 A | 案 B | 案 C |
|---|---|---|---|
| 1. 実装バグ修正 | ✅ | ❌ (新機能) | △ (A 部分のみ) |
| 2. 設計変更ではない | ✅ | ❌ | △ |
| 3. 既存メソッド contract 維持 | ✅ | ✅ (verifier 不変) | ✅ |
| 4. baseline 1417 維持 | ✅ 見込 | ✅ | ✅ 見込 |
| 5. カズヤ承認 | CP-1 | CP-1 | CP-1 |
| **総合** | **5 点充足** | 1/3 条件で不適格 | A 部分は充足、B 部分が不適格 |
