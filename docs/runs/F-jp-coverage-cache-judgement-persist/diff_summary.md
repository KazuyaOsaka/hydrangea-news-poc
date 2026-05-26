# 改修 diff サマリー (Task C)

batch: F-jp-coverage-cache-judgement-persist
方針: **案 A** (CP-1 カズヤ確定) — DB schema 拡張 + cache 永続化で round-trip を lossless 化
原則: 判定ロジック不変・既存メソッド contract 完全維持・後方互換

---

## 改修ファイル (2 ファイル)

### 1. `src/storage/db.py`

**(a) DDL 拡張** — `jp_coverage_cache` テーブルに 2 列追加 (fresh DB 用):
```sql
llm_judgement       TEXT,   -- B-3' LLM 判定 "match"/"no_match"/"uncertain"/NULL
llm_judgement_text  TEXT    -- B-3' 判定該当文 (監査・デバッグ用)
```

**(b) idempotent migration** — 新規 `_migrate_jp_coverage_cache(conn)` + `_JP_COVERAGE_CACHE_ADDED_COLUMNS`:
- `PRAGMA table_info` で既存列を確認し、欠けている列のみ `ALTER TABLE ADD COLUMN ... TEXT` (DEFAULT NULL)
- DDL は `CREATE TABLE IF NOT EXISTS` のため作成済 DB (本番 24 行) に列が増えない問題を吸収
- `init_db()` 内で `executescript(_DDL)` 直後に呼ぶ
- 既存行は NULL = 従来の cache hit 挙動 (llm_judgement=None) と完全一致 → 後方互換
- テーブル未作成時の `OperationalError` は warning ログで graceful skip

### 2. `src/triage/jp_coverage_verifier.py` (不変原則 3 例外適用)

**(a) `_get_cached()`** — SELECT に `llm_judgement, llm_judgement_text` を追加 (row[7], row[8])、
`JpCoverageResult` 復元時に `llm_judgement=row[7], llm_judgement_text=row[8]` をセット。

**(b) `_save_cache()`** — INSERT 列に `llm_judgement, llm_judgement_text` を追加、
values に `result.llm_judgement, result.llm_judgement_text` を渡す。

**判定ロジック (`verify()` / `verify_two_stage()` の B-3' if/else)・戻り値型・public signature は一切不変。**
private メソッド 2 つの SQL とフィールド復元のみ拡張。

---

## 不変・非対象 (念のため)

- `verify_two_stage()` は cache 経路を持たないため無改修 (broad/angle_llm_judgement は cache 対象外)。
- `main.py` 無改修 (案 B = score_breakdown 注入は本バッチ非採用、別バッチ FUTURE_WORK へ)。
- `evidence_writer.py` / `article_writer.py` / `script_writer.py` / `configs/` / `scripts/` /
  `retry.py` / `CLAUDE.md` / `tests/` 0 行変更。

---

## 検証結果 (実装直後の isolation 確認)

### migration (本番 DB コピー + fresh DB)
- 本番 DB コピー (24 行): 列追加成功、**24 行保全**、既存行は全て `llm_judgement IS NULL` (後方互換)、
  `init_db` 2 回実行で **idempotent** (二重 ADD COLUMN エラーなし)。
- fresh DB: DDL で 2 列が最初から存在。

### round-trip 忠実性 (verify() cache miss → cache hit)
シナリオ: WL マッチ (afpbb.com) + LLM `no_match` → B-3' 安全装置発火 (has_jp_coverage=False)。

| | cached | has_jp_coverage | llm_judgement | llm_judgement_text | API calls |
|---|---|---|---|---|---|
| 1st (cache miss) | False | False | `no_match` | 保存 | 1 |
| 2nd (cache hit) | True | False | **`no_match` (復元)** | **復元** | 1 (増えない) |

**改修前**: 2nd は `llm_judgement=None` で復元されていた。**改修後**: `no_match` が忠実に復元される。
`has_jp_coverage` は改修前後とも False で不変 (= Recall に影響しないことの再確認)。
