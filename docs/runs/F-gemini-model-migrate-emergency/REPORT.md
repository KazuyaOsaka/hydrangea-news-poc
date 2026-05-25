# F-gemini-model-migrate-emergency — 5/25 shutdown 緊急対応 実装レポート

生成日: 2026-05-19
ブランチ: `feature/F-gemini-model-migrate-emergency`
main HEAD (分岐元): `2a73a0d` (F-gemini-model-audit merge 後)
baseline: **1417 passed 維持** (CP-1 承認の test 2 行更新後に復帰確認済)

---

## 1. バッチ概要

2026-05-25 `gemini-3.1-flash-lite-preview` shutdown 対応の **最小改修実装バッチ**。
前バッチ `F-gemini-model-audit` で確定したスコープ + カズヤ AI Studio 確認済
active quota / preview-GA 状態を反映し、両系統 Tier3 + factory.py/config.py
default + `.env`/`.env.example` を `gemini-3.1-flash-lite` (GA) に一括置換。
shutdown モデル ID を Tier 階層から完全除去することで 5/25 以降の
「404 即 raise で安全網 (Tier4) に降りられず生成失敗」リスクを **構造的に根絶**。
retry.py の設計変更は不要 (= 最小対処で十分、audit CP-1 仮説どおり)。

原則: 「対症療法じゃなく根本治療」+「動くものを壊さない」+「あるべき姿で進める」。

---

## 2. 改修 diff サマリー (6 ファイル、機能ロジック変更なし)

| ファイル | 区分 | 変更内容 |
|---|---|---|
| `.env` (gitignored) | functional | `GEMINI_MODEL_TIER3` / `GEMINI_LIGHTWEIGHT_TIER3` を `gemini-3.1-flash-lite-preview` → `gemini-3.1-flash-lite` (GA)。インライン/性能順コメント整合更新 |
| `.env.example` | functional + doc | 上記 2 行と同一置換 + 性能順コメント + TIER1 インターバル説明コメント整合 |
| `src/llm/factory.py` | functional default + doc | L316 `GEMINI_LIGHTWEIGHT_TIER3` default / L324 `GEMINI_MODEL_TIER3` default を GA 化。docstring/コメント 3 箇所 (L82, L96, L309-310) doc-drift 整理。**既存メソッド contract 完全不変** |
| `src/shared/config.py` | functional default + doc | L76 `GEMINI_MODEL_TIER1` default を GA 化 (audit grep_results.json が正本: config.py:76 は TIER1 default 行で、shutdown モデルはここに pin されていた)。L142 doc-drift コメント整理 |
| `src/main.py` | doc-drift | L2471-2473 Elite Judge コメントを実態 (QUALITY Tier1=gemini-3-flash-preview) に整合、stale な "RPD 500" 記述除去 |
| `src/llm/judge.py` | doc-drift | L72 docstring の typo モデル名 `gemini-3.1-flash-preview` を実態 `gemini-3-flash-preview` (QUALITY Tier1) に修正 |
| `tests/test_factory_role_tier_separation.py` | test 追従 (★CP-1 カズヤ承認) | L56 / L69 の期待値リテラル `"gemini-3.1-flash-lite-preview"` → `"gemini-3.1-flash-lite"` (各 1 トークン、テストロジック・assert 構造・mock・docstring 一切不変) |

tracked diff: 6 files, +18 / -17。`.env` は gitignored のため git diff 非表示
(値変更は実ファイルに反映済、commit 対象は `.env` 除く tracked のみ)。

### 改修しなかった対象 (明示)

- **`src/llm/retry.py`**: 0 行変更。404 非フォールバック判定ロジック不変。
  shutdown モデル ID を階層から除去 → 404 到達自体が構造的に消滅 = 設計変更不要。
- **`gemini-3-flash-preview` / `gemini-3.1-pro-preview` の Tier1-2 配置**: 本バッチ非対象。
- **F-13.B Grounding** (`JP_COVERAGE_GROUNDING_MODEL=gemini-2.5-flash`): 維持。
- **Lightweight Tier1** (`GEMINI_LIGHTWEIGHT_TIER1=gemini-2.5-flash`): **据置** (CP-1 判断 B、後述)。
- `config.py:77-79` の config.py/factory.py default 不一致 (audit §9-3): runtime 影響なし
  (env が常に上書き) かつ shutdown モデル非該当のため最小スコープから除外。
  FUTURE_WORK に整合タスクとして残置。

---

## 3. baseline + 試運転結果

### 3-1. baseline

| フェーズ | 結果 |
|---|---|
| Task A baseline | 1417 passed |
| Task D-1 改修後 (test 更新前) | **1415 passed, 2 failed** → 想定外結果、CP-1 stop |
| Task D-1 改修後 (CP-1 承認 test 更新後) | **1417 passed** 復帰確認 |

2 failed の正体: `tests/test_factory_role_tier_separation.py::test_lightweight_role_uses_ga_primary` (L56) /
`::test_quality_role_uses_preview_primary` (L69)。両者とも `models[2]` (= Tier3 default)
を旧 shutdown モデル名で hard-pin。本 migration が意図的に変える default 値を
テストが固定 = 機能回帰ではなく **migration と同一スコープの default 追従**。
CP-1 でカズヤが選択肢 1 (2 行更新承認) を判断 → 期待値リテラルのみ更新。

### 3-2. 1 batch 試運転 (Task D-2)

`python -m src.ingestion.run_ingestion` → `python -m src.main --mode normalized`

- ingestion: batch=20260519_104204, new=1044, OK
- main: exit 0, **status=completed**, 3 slots published
- model_roles: merge_batch=gemini-2.5-flash / judge=gemini-2.5-flash /
  generation=gemini-3-flash-preview (全て Tier1/Tier2 GA 解決、resolution 正常)
- generation_outcomes: script/article とも `used_fallback=false`, `retry_count=0`
- judge: error 0 / quota_exhausted 0 / temporary_unavailable 0
- ログ全文に `404` / `NOT_FOUND` / `Traceback` / `ERROR` /
  `gemini-3.1-flash-lite-preview` 出現 **0 件**

Tier3 fallback 経路 (= 改修箇所) は本 run では未発火。これは 503/429 連鎖が
起きず Tier1/Tier2 GA で完結したためで、CP-1 カズヤ判断のとおり実環境で
fallback が発火しにくいのは想定どおり・異常ではない。改修の本質は
**shutdown モデル ID を Tier 階層から完全除去** したこと自体であり、grep /
model_roles 上に functional 参照が 0 件であることがリスク根絶の確証。
詳細は `trial_run_summary.json`。

---

## 4. CP-1 で確定したカズヤ判断 + 根拠

### 判断 1: test 対処 = **選択肢 1 (2 行テスト更新承認)**

> 機能ロジック変更ゼロ、default 値追従のみ。default 値を変える migration が
> default 値を pin するテストと論理的に整合必須 = 本来 migration の同一スコープ。
> BATCH_PROTOCOL 不変原則 5 の本旨 (機能回帰防止) と矛盾なし、例外条件
> (バグ修正類 + 設計変更ではない + DECISION_LOG 明記 + カズヤ承認) と整合。

→ `tests/test_factory_role_tier_separation.py:56/:69` の期待値リテラルのみ更新。
テストロジック・assert 構造・mock・docstring (Tier1 主張) は一切不変。

### 判断 2: Lightweight Tier1 切替 = **選択肢 B (Tier1 据置)**

> 「動くものを壊さない」優先。5/25 shutdown 対応は Tier3 置換で達成済。
> Tier1 主軸変更は Gemini 2 系 → 3 系の系統変更で MEDIUM リスク
> (garbage_filter / merge_batch / viral_filter / editorial_mission_filter の
> 出力品質に微妙な影響あり得る、1 batch 試運転だけでは検証不十分)。
> F-gemini-quality-tier-poc で axis_5 採点による品質検証後に投入が筋。

→ `GEMINI_LIGHTWEIGHT_TIER1=gemini-2.5-flash` のまま据置。
RPD 150K (15 倍) の quota 確保メリットは F-gemini-quality-tier-poc で
品質検証後に別途投入判断する。

---

## 5. 自分で判断した内容

- **判断 1**: config.py:76 はバッチ指示書本文では「GEMINI_MODEL_TIER3 default」と
  記載されていたが、audit `grep_results.json` (line→var マッピングの正本) では
  config.py:76 = `GEMINI_MODEL_TIER1` default 行であり shutdown モデルはここに
  pin されていた。正本に従い L76 の shutdown モデル文字列のみ置換、L77-79 の
  config.py/factory.py default 不一致 (runtime 影響なし) は最小スコープ堅持で
  非改修・FUTURE_WORK 残置とした。
- **判断 2**: doc-drift コメント整理範囲。`.env`/`.env.example`/`factory.py` の
  性能順コメント・TIER1 インターバル説明コメントは変更行と直接矛盾する stale
  参照のため、不変原則の「doc-drift 整理」許容範囲内として整合更新
  (機能影響ゼロ)。`.env` の migration 注記コメントには意図的に旧モデル名を
  残置 (置換の事実を記録するため、grep 上は functional 参照 0 件で問題なし)。
- **判断 3**: 想定外結果 (baseline 1417→1415) で task 規定どおり Task D-2 試運転
  前に即停止し CP-1 へ。test 失敗は機能回帰ではないと分析した上で、勝手に
  書き換えず CP-1 でカズヤ承認を得てから更新 (CLAUDE.md ガードレール遵守)。

---

## 6. 不変原則違反 / 触ってはいけないファイルへの変更要望

- **なし**。`src/triage/` / `src/analysis/` / `src/generation/article_writer.py` /
  `src/generation/script_writer.py` 既存ルート / `configs/` / `scripts/` /
  `CLAUDE.md` / `src/llm/retry.py` = **0 行変更**。
- `tests/` への 2 行変更は **CP-1 でカズヤ明示承認済** (BATCH_PROTOCOL 例外条件
  4 点: バグ修正類 / 設計変更ではない / DECISION_LOG 明記 / カズヤ承認 を全充足)。

---

## 7. 残課題 (次バッチ引継ぎ)

1. **F-gemini-quality-tier-poc** (次バッチ最有力): Narrative 主軸 (QUALITY Tier1)
   選定 + Lightweight Tier1 を `gemini-3.1-flash-lite` (RPD 150K) に切替するかを
   axis_5 採点で品質検証。CP-1 判断 B の保留分。
2. **Phase A.5-3b 第一作起案** (2nd 候補)。
3. config.py:77-79 の config.py/factory.py default 不一致整合 (runtime 影響なし、
   低優先、別 doc/refactor バッチ)。
4. `GEMINI_QUOTA_NOTES.md` 陳腐化更新 (2026-04-26 時点記述、現状乖離)。

---

## 8. BATCH_PROTOCOL Task 1-5 適用内容

- **Task 1 (DECISION_LOG)**: 本バッチエントリ追加 (両系統 Tier3 GA 置換 +
  CP-1 判断 1/2 + test 2 行更新の例外承認を明記) + 前バッチ
  `F-gemini-model-audit` の「コミット: (push 後追記)」を実ハッシュ
  `92146f6` (feat) / `2a73a0d` (merge) に追記更新。
- **Task 2 (FUTURE_WORK)**: 本バッチ完了済み移動 / `F-gemini-quality-tier-poc`
  を次バッチ最有力に格上げ (Lightweight Tier1 切替検討を内包) /
  config.py default 不一致整合タスク残置。
- **Task 3**: 本セクション = REPORT への明記。
- **Task 4 (DISCUSSION_NOTES)**: 新規 4-A「2026-05-19: 5/25 shutdown 緊急対応
  完了、両系統 Tier3 GA 置換 + Lightweight Tier1 判断 B (据置)」追加。
- **Task 5 (CURRENT_STATE)**: 15 つ目バッチとして全置換更新、次バッチ候補
  1st=F-gemini-quality-tier-poc / 2nd=Phase A.5-3b 第一作起案。
