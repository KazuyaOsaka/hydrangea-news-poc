# F-f1-locale-key-fix — F-1 EditorialMissionFilter の locale key 修正 レポート

生成日: 2026-05-25
ブランチ: `feature/F-f1-locale-key-fix`
main HEAD (分岐元): `231decd` (F-gemini-model-migrate-emergency merge 後)
baseline: **1417 passed 維持** (改修後確認済)

---

## 1. バッチ概要

3 AI 三角測量 (ChatGPT + Gemini) のレビューで **両者独立に指摘** された
`src/triage/editorial_mission_filter.py` の locale key bug を根本治療した。
`_editorial_mission_prescore` 内で `sources_by_locale.get("jp", [])` /
`get("en", [])` が参照されていたが、実データ構造の正しいキーは `"japan"` /
非 japan 地域名 (`"global"`/`"middle_east"`/`"europe"` 等)。grep の結果、当該
ファイルは src/ 全体で `"jp"`/`"en"` キーを使う **唯一のファイル** で、他の
triage / analysis / generation / `main.py` は全て `"japan"` + 「非 japan =
海外」パターンで統一済みと確定した。

原則: 「対症療法じゃなく根本治療」+「動くものを壊さない」+「あるべき姿で
進める」+「LLM の知性に委ねる前に構造データの正しさを担保する」。

---

## 2. ★ クラウド初期想定の訂正 (クラウド誤り 10)

初期バッチプロンプト (Claude Web 側起案) はバグの実害を「日本ソース数が常に
0 で blindspot_severity が **不当に高く算出される誤爆 (false positive)**」と
記載していたが、Claude Code の grep + コード精読で実態が判明:

- `jp_count` (`get("jp")`) と `en_count` (`get("en")`) が **両方** 常に 0
- → blindspot の count ベース中間 elif (12.0 / 10.0 / 8.0) は **全て dead code**
  で一度も発火しない
- → 実害は「不当に高い誤爆」ではなく「**中間解像度 8〜12 点の永久喪失
  (false negative 方向)**」。修正後はむしろ一部スコアが 0 → 8〜12 に**上がる**
- → 第1分岐 `if has_en and not has_jp: blindspot = 15.0` は `score_breakdown` の
  `editorial:has_*_view` 由来 (scoring.py:546-547) で **従来から正常動作** =
  代替経路あり = 安全網は全壊していなかった

→ 緊急度を **★★★ → ★★** に下方修正 (production 破壊なし、ただし設計どおり
動いていない事実は不変で修正は妥当)。この経緯を **クラウド誤り 10
(Project Knowledge 過信 + grep 不足)** として `docs/DISCUSSION_NOTES.md` に登録。
番号は docs 登録済の 1-7 + 9 に続く 10 (Claude Web 側の個人メモ上の 8/10-16/17
は docs 正本に存在しないため不採用 — この取り違え自体が誤り 10 の本質)。

---

## 3. 影響範囲サマリー (Task B)

| 観点 | 結果 |
|---|---|
| バグ箇所 | `editorial_mission_filter.py:161-162` の 2 行のみ |
| 同種バグの他ファイル | **0 件** (src/ で `"jp"`/`"en"` を使うのは本ファイルのみ) |
| 海外ソース数の正本パターン | `main.py:941-946` = `sum(len(refs) for loc,refs in items() if loc != "japan")` |
| 代替経路 | あり (`has_jp_view`/`has_en_view` 由来の binary 15.0/0.0 は正常動作) |
| 既存テスト影響 | `tests/test_editorial_mission_filter.py:173-190` が data キーに `"en"`/`"jp"` を hard-pin (要整合更新) |
| 救済不能な実害 | なし (binary 信号は機能、中間解像度のみ喪失) |

詳細: `grep_results.json` / `locale_key_inventory.json` / `impact_analysis.json`。

---

## 4. CP-1 で確定したカズヤ判断

### 判断 1: en_count 修正方針 = **選択肢 1 (非 japan 合算)**

根拠 5 点: (1) `main.py` overseas_count と完全一致 = 既存パターン統一、
(2) 選択肢 2 ("global" リテラル) は middle_east/europe/east_asia/global_south を
取りこぼし別 bug を生む = 対症療法、(3)「対症療法じゃなく根本治療」、
(4)「構造データの正しさを担保」= 多様な locale の正しい意味解釈、
(5) 選択肢 3 (定数一元化) は「1 バッチで欲張らない」で別バッチ任意。

### 判断 2: テスト = **本バッチで同時更新** (CP-2 にせず)

不変原則 5 例外条件 4 点充足 (バグ修正類追従 / 設計変更ではない /
DECISION_LOG 明記 / カズヤ承認)。「将来に負債を残さない」原則 = dead code
テストデータを残さない。data キー `"en"`/`"jp"` → `"global"`/`"japan"`、
assert 構造・期待値ロジックは完全不変。

### 判断 3: クラウド初期想定の訂正受容 + クラウド誤り 10 記録 (§2)。

---

## 5. 改修 diff サマリー (2 ファイル、機能ロジック変更なし)

| ファイル | 区分 | 変更内容 |
|---|---|---|
| `src/triage/editorial_mission_filter.py` | bug fix | L161-162 の `get("jp")`→`get("japan")`、`get("en")`→非 japan locale 合算 (overseas_count パターン)。blindspot の if/elif 判定・係数・cap は不変 |
| `tests/test_editorial_mission_filter.py` | test 追従 (★CP-1 承認) | `test_blindspot_intermediate_tiers` の data キー `"en"`→`"global"`、`"jp"`→`"japan"`。assert (`blindspot==12.0`)・ロジック不変 |

tracked diff: 2 files, +11 / -4。詳細: `diff_summary.md`。

### 改修しなかった対象 (明示)

- `src/triage/` の `editorial_mission_filter.py` 以外 (jp_coverage_verifier.py /
  cross_lang_matcher.py / coherence_gate.py / gemini_judge.py / scoring.py /
  appraisal.py): 既に `"japan"` パターンで正しい → 0 行変更
- `src/analysis/` / `article_writer.py` / `script_writer.py` 既存ルート /
  `retry.py` / `configs/` / `scripts/` / `CLAUDE.md`: 0 行変更
- F-1 LLM プロンプト本体 / 閾値 (45.0) / 7 軸ロジック: 不変
- locale key 定数一元化 (選択肢 3): FUTURE_WORK に任意残置

---

## 6. baseline + 試運転結果

### 6-1. baseline

| フェーズ | 結果 |
|---|---|
| Task A baseline | 1417 passed |
| Task C 改修後 (targeted) | tests/test_editorial_mission_filter.py 32 passed |
| Task D-1 改修後 (full) | **1417 passed** 維持 |

### 6-2. 1 batch 試運転 (Task D-2)

`python -m src.ingestion.run_ingestion` → `python -m src.main --mode normalized`

- ingestion: batch=20260525_085458, normalized=47, new=1355, OK
- main: exit 0, **status=completed**, 3 slots published (Slot-1 video + Slot-2/3 article-only = F-16-A 通常挙動)
- generation: script/article とも `used_fallback=false`, `retries=0`
- ログ全文に `404` / `NOT_FOUND` / `Traceback` / `ERROR` 出現 **0 件**
- 防衛機構 5 層異常なし。F-13.B は Slot-2/3 で `llm_judgement=no_match` 確定 (blind_spot_global)。動画化候補消失なし
- budget: run_llm=42/150, publish_reserve_preserved=true, slot1_budget_guaranteed=true

### 6-3. 修正前後の prescore 分布変化 (定性評価)

run_summary レベルの before/after は入力 RSS バッチが異なる
(before=753 cands / after=369 cands) ため **confounded**:
- before (pre-fix prior run): prescore_stats min=0.0 / max=72.4 / mean=23.3
- after (post-fix this run): prescore_stats min=0.0 / max=65.2 / mean=21.62

blindspot 修正の効果を分離するため、blindspot 計算式を **旧キー/新キーで
決定的に比較** (`before_after_prescore.json`):

| シナリオ | OLD blindspot | NEW blindspot | Δ |
|---|---|---|---|
| 海外3(global)+日本1 | 0.0 (en=0,jp=0) | 12.0 (en=3,jp=1) | **+12.0** |
| 中東のみ3+日本1 | 0.0 | 12.0 (en=3,jp=1) | **+12.0** ★ 選択肢1の根拠 |
| 海外2(global+europe)+日本0 | 0.0 | 10.0 (en=2,jp=0) | +10.0 |
| 海外2(global)+日本1 | 0.0 | 8.0 (en=2,jp=1) | +8.0 |
| 海外1+日本view無 (has_jp=F) | 15.0 | 15.0 | 0.0 (代替経路、不変) |

→ blindspot 中間 elif (8/10/12) が dead code から復活、海外多数・日本少数の
イベントが 0 → 8〜12 に上がる (graduated 評価の復元、false negative 方向の是正)。
binary 15.0 経路は不変。中東のみシナリオは「選択肢 2 (global 単独) なら
middle_east を取りこぼし 0 のまま」= 選択肢 1 (非 japan 合算) が正しい根拠。

---

## 7. 自分で判断した内容

- **判断 1**: `en_count` の意図は「海外ソース数」であり `"global"` 単独では
  middle_east/europe 等を取りこぼす。CP-1 で選択肢 1 (非 japan 合算 =
  main.py overseas_count パターン) を推奨し、カズヤ承認を得た。
- **判断 2**: `test_blindspot_intermediate_tiers` は overseas-sum 方式なら data
  未更新でも green を維持する (en+jp 両方が非 japan として合算され 12.0 を
  満たす) が、data が意味的に誤りのため CP-1 で同時更新を提案・承認。
- **判断 3**: タスク前提 (「不当に高く誤爆」) を鵜呑みにせず、全分岐トレース +
  grep で実態 (中間解像度喪失) を確認し CP-1 で訂正提案 → クラウド誤り 10 記録。
- **判断 4**: クラウド誤り採番。Claude Web 側メモの 17 ではなく docs 正本連番
  (1-7+9 の次 = 10) を採用 (カズヤ CP 指示で確定)。

---

## 8. 不変原則違反 / 触ってはいけないファイルへの変更要望

- **なし**。不変原則 3 例外条件 5 点全充足 (バグ修正 + 設計変更ではない +
  既存メソッド contract 完全維持 + baseline 1417 維持 + カズヤ承認済)。
- `src/triage/` の `editorial_mission_filter.py` 以外 / `src/analysis/` /
  `article_writer.py` / `script_writer.py` 既存ルート / `retry.py` /
  `configs/` / `scripts/` / `CLAUDE.md` = 0 行変更。
- `tests/` への 5 行変更は CP-1 でカズヤ明示承認済 (不変原則 5 例外条件 4 点充足)。

---

## 9. 残課題 (次バッチ引継ぎ)

1. **F-jp-coverage-cache-judgement-persist** (★★高、次バッチ最有力): F-13.B
   `llm_judgement` の 24h SQLite キャッシュ永続化 (ChatGPT + Gemini 両者独立指摘)。
2. **F-script-writer-target-enemy-fix** (★★★高): `target_enemy` プロンプト/モデル
   定義の不整合修正 (Gemini 独自指摘)。★ 試運転 Slot-1 でも `target_enemy=米国政府`
   が director_thought に出現、定義整合の調査価値あり。
3. **F-gemini-quality-tier-poc** (★★高): Narrative 主軸 + Lightweight Tier1 切替の品質検証。
4. locale key 定数一元化 (選択肢 3): 任意、低優先。

---

## 10. BATCH_PROTOCOL Task 1-5 適用内容

- **Task 1 (DECISION_LOG)**: 本バッチエントリ追加 (locale key bug 根本治療 +
  CP-1 判断 + クラウド誤り 10 + 不変原則 3 例外条件 5 点) + 前バッチ
  `F-gemini-model-migrate-emergency` の「コミット: (push 後追記)」を実ハッシュ
  `7624f93` (feat) / `231decd` (merge) に追記更新。
- **Task 2 (FUTURE_WORK)**: `F-f1-locale-key-fix` 完了済み移動 +
  `F-jp-coverage-cache-judgement-persist` (★★高) / `F-script-writer-target-enemy-fix`
  (★★★高) を緊急度 高に新規追加。
- **Task 3**: 本セクション = REPORT への明記。
- **Task 4 (DISCUSSION_NOTES)**: 新規 4-A「2026-05-25: 3 AI 三角測量で F-1
  locale key bug 発見 → 即座に根本治療」+ クラウド誤り 10 (Project Knowledge
  過信 + grep 不足) を クラウド誤り 9 直後に登録。
- **Task 5 (CURRENT_STATE)**: 16 つ目バッチとして全置換更新、次バッチ候補
  1st=F-jp-coverage-cache-judgement-persist / 2nd=F-script-writer-target-enemy-fix /
  3rd=F-gemini-quality-tier-poc / 4th=Phase A.5-3b 第一作起案。
