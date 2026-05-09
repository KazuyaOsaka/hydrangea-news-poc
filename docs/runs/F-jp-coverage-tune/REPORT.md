# F-jp-coverage-tune 完了レポート

**日付**: 2026-05-09
**バッチ名**: F-jp-coverage-tune (Phase A.5-3a-verify ロードマップ 1-G)
**ブランチ**: `feature/F-jp-coverage-tune` (未マージ)
**着手時 main HEAD**: `e1ad637` (F-task-e-finalize マージ後)
**完了時 git HEAD**: `e1ad637` (本バッチ未 commit、変更は working tree)
**verdict**: **fail** (4 指標全部未達、Grounding API 構造的限界が支配的)

---

## 1. 実装ファイル一覧

### 新規作成
- `tests/test_jp_coverage_verifier_two_stage.py` (19 テスト)
- `scripts/measure_two_stage_accuracy.py` (新規測定スクリプト、incremental save + resume + ログ書き出し対応)
- `docs/runs/F-jp-coverage-tune/measurement_result.json` (post-tuning 最終結果)
- `docs/runs/F-jp-coverage-tune/measurement_result_pre_tuning.json` (Step 4 前ベースライン保存)
- `docs/runs/F-jp-coverage-tune/logs/<event_id>.log` × 23 件 (per-event デバッグログ)
- `docs/runs/F-jp-coverage-tune/REPORT.md` (本レポート)

### 変更 (新規追加のみ、既存メソッド完全不変)
- `src/triage/jp_coverage_verifier.py` (+約 290 行)
  - 新規 dataclass: `TwoStageVerifyResult`
  - 新規メソッド: `verify_two_stage()`, `_build_broad_query()`, `_build_angle_query()`, `_fallback_angle_query()`, `_search_with_grounding_two_stage()`, `_call_with_timeout()`
  - 既存メソッド (`verify()`, `_build_search_query`, `_search_with_grounding`, `_filter_excluded`, `_match_whitelist`) 完全不変
- `docs/CURRENT_STATE.md` (全置換更新)
- `docs/DECISION_LOG.md` (本バッチエントリ追加 + ヘッダ最終更新日付)
- `docs/FUTURE_WORK.md` (本バッチを完了済みに移動 + F-jp-coverage-tune-followup 緊急度 高新規追加 + ヘッダ最終更新日付)
- `docs/DISCUSSION_NOTES.md` (新規 2 エントリ + 既存 1 エントリ追記 + ヘッダ最終更新日付)

---

## 2. テスト結果

- **着手時 baseline**: 1345 passed
- **完了時 baseline**: **1364 passed** (新規 19 件追加、既存 1345 件全件維持)
- 既存テスト影響: なし (`tests/test_jp_coverage_verifier_domain_extract.py` 30 件、その他全て 1345 件 PASS)
- 新規テスト追加: 19 個 (`tests/test_jp_coverage_verifier_two_stage.py`)
  - stream_1 / stream_2 / stream_3 各分岐
  - unknown / graceful fallback (検索 API 例外、angle 失敗時)
  - Step 2 skip 確認 (broad 未報道時に angle 検索しない)
  - LLM クエリ fallback (LLM 失敗 / no_llm_client / no_core_question / bad_format)
  - フォーマット正規化 (ラベル接頭辞除去、複数行最初の行採用、引用符除去)
  - 既存 verify() 不変性確認

---

## 3. Step 別の実施結果

### Step 1: 実装 (CP-1 で停止 → カズヤ承認後 Step 2 へ)

新規 dataclass `TwoStageVerifyResult` + 新規メソッド `verify_two_stage()` 等を `src/triage/jp_coverage_verifier.py` に追加。既存メソッドは完全不変。

`verify_two_stage()` のフロー:
1. `_build_broad_query()` で広範事件クエリ生成 (既存 `_build_search_query` 流用)
2. `_search_with_grounding_two_stage()` で broad 検索 (per-call timeout + graceful fallback)
3. broad 未報道なら **Step 2 スキップ → stream_1 確定** (= API コール削減)
4. broad 報道済みなら `_build_angle_query()` で LLM 角度クエリ生成 → angle 検索
5. broad 報道 + angle 報道 → stream_3_candidate
6. broad 報道 + angle 未報道 → stream_2_perspective_gap

graceful fallback:
- 検索 API timeout / 例外 → `stream="unknown"`、`error_message` セット
- LLM 失敗 / フォーマット違反 → 簡易 fallback クエリ (title + core_question 先頭 20 文字)、`angle_query_fallback_reason` 記録

### Step 2: ユニットテスト追加 (CP-1 後カズヤ承認で着手)

19 件追加、baseline 1345 → 1364 passed。1 件 (test_verify_two_stage_llm_query_fallback) で文字数カウントの誤りを発見し即時修正、最終的に全 19 件 PASS。

### Step 3: 精度測定スクリプト + 実行 (CP-2 で停止 → カズヤ承認後 Step 4 へ)

`scripts/measure_two_stage_accuracy.py` を新規作成、独立 23 件で精度測定実行。

**Pre-tuning 結果 (verdict=fail)**:
| 指標 | 実測値 | 閾値 | 判定 |
|---|---|---|---|
| Recall covered | 0.3158 (6/19) | ≥ 0.90 | ✗ |
| Precision blind | 0.2353 (4/17) | ≥ 0.80 | ✗ |
| F1 covered | 0.4800 | ≥ 0.85 | ✗ |
| Tier 一致率 | 0.6667 (4/6) | ≥ 0.70 | ✗ (僅差) |
| Stream accuracy (informational) | 0.3182 (7/22) | — | — |

confusion: TP=6 / FP=0 / FN=13 / TN=4。**支配的失敗モード = broad search の under-recall** (FN 13 件)。total elapsed 322s、平均 14s/件。

### Step 4: チューニング (1 回のみ、カズヤ判断で (c) 採択)

CP-2 で 4 候補 (a)-(d) 提示、カズヤ判断で **(c) dateRestrict プロンプト埋め込み除去** を採択。`_search_with_grounding_two_stage` のプロンプト本文から日付制約文を削除 (`date_restrict_days` パラメータ自体は backward-compat で残置)。

**Post-tuning 結果 (verdict=fail のまま)**:
| 指標 | Pre | Post | Δ | 閾値 | 判定 |
|---|---|---|---|---|---|
| Recall covered | 0.3158 | **0.4211** (8/19) | +0.1053 | ≥ 0.90 | ✗ |
| Precision blind | 0.2353 | **0.2667** (4/15) | +0.0314 | ≥ 0.80 | ✗ |
| F1 covered | 0.4800 | **0.5926** | +0.1126 | ≥ 0.85 | ✗ |
| Tier 一致率 | 0.6667 | **0.6250** (5/8) | -0.0417 | ≥ 0.70 | ✗ |
| Stream accuracy (informational) | 0.3182 | **0.2727** (6/22) | -0.0455 | — | — |

confusion (post): TP=8 / FP=0 / FN=11 / TN=4。total elapsed 341s、平均 15s/件。

**dateRestrict 除去の効果分析**:
- broad recall +10.53pp 改善 (covered_005 ブラジル COP30 が newsweekjapan.jp ヒットで stream_2 確定など)
- 旧 F-13.B 水準 (Recall 71.43%) には届かず → 残る under-recall は Grounding API 構造的限界に起因
- stream_3 過剰検出は 3 件 → 6 件に増加 (dateRestrict 解除で angle recall も上がり WL ヒット件数増加、ただし真値「特定角度は未報道」と矛盾)

### Step 5: ドッグフーディング (BATCH_PROTOCOL Task 1-5)

- Task 1: DECISION_LOG.md にエントリ追加 ✅
- Task 2: FUTURE_WORK.md 完了済み移動 + F-jp-coverage-tune-followup 緊急度 高新規追加 ✅
- Task 3: 完了レポート (本ドキュメント) で Task 1-2 反映を明記 ✅
- Task 4: DISCUSSION_NOTES.md 新規 2 エントリ + 既存 1 エントリ追記 ✅
- Task 5: CURRENT_STATE.md 全置換更新 ✅

---

## 4. 系統別正答率 (informational)

| 真値 stream | 件数 | Pre 正答 | Post 正答 | 主な誤分類 (post-tuning) |
|---|---|---|---|---|
| stream_1_silence_gap | 4 | 4 (100%) | 4 (100%) | — (完璧) |
| stream_2_perspective_gap | 18 | 3 (17%) | 2 (11%) | 10 件 → stream_1 (broad miss)、6 件 → stream_3 (angle WL hit、過剰検出 +3 件) |
| stream_3_framing_inversion | 0 | — | — | (真値 0 件、評価不能) |

**正しく stream_2 を捕捉できたケース** (post-tuning 2 件、pre-tuning 3 件):
- post-tuning: covered_003 (米中関税)、covered_008 (マリ国防相暗殺)
- pre-tuning では covered_002 (米ロ首脳停戦) も含まれていたが、post-tuning では angle 検索で asahi.com がヒットし stream_3 過剰検出に転落

---

## 5. 自分で判断した内容

1. **`_build_angle_query` の戻り値型**: 設計書では str を返す指定だったが、`fallback_reason` を呼び出し側が把握できるようタプル `(query, fallback_reason)` に拡張。`TwoStageVerifyResult.angle_query_fallback_reason` で精度測定スクリプトから観察可能にした。
2. **LLM プロンプト文言**: クラウド誤り 9「各論コントロールへの誘惑」を避け、構造制約 (単一行 / 6-15 単語 / 固有名詞+角度キーワード / site: 禁止 / JSON 不可) のみで指示。「こう書け」という具体的言い回しルールは入れず、「LLM の知性に委ねる」原則尊重。
3. **dateRestrict 実装方針 (Step 1)**: Gemini Grounding API は dateRestrict を直接サポートしないため、プロンプト本文に埋め込む方針を採用。ただし Step 4 の (c) チューニングで副作用検証のため除去 = 仮説 #2 (副作用) が部分的に正しいことが実測値で確認された。
4. **`analysis_llm_client` の差し込み方式**: `__init__` を変更せずに `verify_two_stage` の kwarg として注入する設計を採用 (= 既存初期化フロー一切不変、テストでは mock 注入容易)。本番では None 時に `get_analysis_llm_client()` で遅延生成。
5. **`broad_matched_tier` / `angle_matched_tier` フィールドの追加**: 設計書の `TwoStageVerifyResult` 仕様には Tier 情報フィールドはなかったが、Step 3 の精度測定スクリプトで「Tier 一致率」を計算するために必要なため追加。
6. **`_call_with_timeout` の実装方式**: signal.SIGALRM はマルチスレッド非対応 (テスト並走時に問題発生) のため、ThreadPoolExecutor 方式を採用。timeout 超過時はワーカースレッドはバックグラウンド継続 (Python の協調キャンセル制約) だが、メインフローは即座に `unknown` で graceful fallback できる。CP-1 でカズヤから「将来課題として認識、本バッチでは実害なし」と承認済。
7. **「covered/blind」の定義 (broad-level 採用)**: stream_3 が真値 0 件のため angle-level Recall は計算不能、broad-level (= truth.broad_event_jp_coverage) を採用して旧 F-13.B との比較可能性も確保。
8. **真値 stream_3_framing_inversion ⇄ 予測 stream_3_candidate を一致扱い**: 命名差吸収のため、Stream accuracy 計算でこの揺れは技術的差異ではなく意味的に同じ。
9. **out_of_scope 1 件 (covered_006 NVIDIA) を Stream accuracy 計算から除外**: 4 系統判定の対象外として扱う設計、ただし Recall covered 計算には truth.broad_event_jp_coverage="reported" のため含まれる (= FN として扱われる、これは仕様通り)。
10. **テストファイル配置**: 設計書では `tests/triage/test_jp_coverage_verifier.py` だったが、プロジェクト既存テスト (フラット配置) に揃え `tests/test_jp_coverage_verifier_two_stage.py` とした。CP-2 でカズヤ承認済。

---

## 6. 不変原則違反 / 触ってはいけないファイルへの変更要望

なし。`src/triage/jp_coverage_verifier.py` への新規 dataclass + 新規メソッド追加は不変原則 3 の例外条件 4 つ全部 (バグ修正ではない設計拡張 / 既存メソッド完全維持 / baseline 維持 / カズヤ承認済) を満たすことを確認した上で実施。

---

## 7. BATCH_PROTOCOL Task 1-5 実施結果

### Task 1 (DECISION_LOG.md): 追加エントリ要約

`docs/DECISION_LOG.md` 末尾に新規エントリ「2026-05-09: F-jp-coverage-tune — F-13.B 二段階クエリ生成改修 (Phase A.5-3a-verify 1-G)」追加。背景 / 議論 (7 論点 + API エラー耐性 + CP 中間チェックポイント方式 + チューニング上限) / 決定 (実装内容 + 不変原則 3 例外条件 4 つ適用根拠 + Step 4 (c) 採択理由) / 結果 (4 指標 pre/post 比較表 + Grounding API 構造的限界の発覚) / 関連ファイル・コミット を完備。

### Task 2 (FUTURE_WORK.md): 変更内容
- 完了済みに移動した項目: F-jp-coverage-tune (緊急度 高 → 完了済み、項目内容は実装サマリ + 4 指標 + 重要な発見 + 残課題で再構成)
- 緊急度 高に追加した項目: **F-jp-coverage-tune-followup** ★最優先 (Grounding API 構造的限界対策、(p) 複数クエリ並列発行 + 結果統合 ★最有力候補 / (q) 検索 API 変更検討 / (r) WL ドメイン拡張検討 / (s) stream_3 過剰検出解消)
- 緊急度 中に追加した項目: なし
- 緊急度 低に追加した項目: なし

### Task 4 (DISCUSSION_NOTES.md): 整理結果
- **新規追加 2 エントリ**:
  1. 「2026-05-09: Grounding API の構造的限界 — 1 クエリ 5-10 chunk + WL 外で上位埋まる + 0 URL 返却 (F-jp-coverage-tune で発覚)」 (Active、★ F-jp-coverage-tune-followup ★最優先で 対応案 (p) を最有力候補に検討)
  2. 「2026-05-09: stream_3 過剰検出 — URL ドメインマッチが特定角度の粒度を区別できない定義レベルの限界 (F-jp-coverage-tune で観察)」 (Active、F-jp-coverage-tune-followup の (s) 副次論点 + F-stream-2-filter-design 責務境界整理時に再評価)
- **既存エントリ追記**: 「2026-05-08: 試運転と golden_set の重複サンプリング問題」に F-jp-coverage-tune での独立 23 件評価採用結果を追記、Active 維持。
- **昇格 / アーカイブ**: なし

### Task 5 (CURRENT_STATE.md): 全置換更新の差分概要
- ヘッダ最終更新日付: 2026-05-08 → 2026-05-09 (F-jp-coverage-tune 完了反映)
- セクション 0: F-jp-coverage-tune 完了の段落追加 (Grounding API 構造的限界の発見 + verdict=fail + F-jp-coverage-tune-followup 切り出し方針)
- セクション 1: main HEAD は `e1ad637` のまま (本バッチ未マージ)、baseline 1345 → 1364 passed 反映、生成ファイル一覧更新
- セクション 2: 進行中バッチを「なし (F-jp-coverage-tune 完了直後、verdict=fail)」、次バッチ候補で 1st を F-jp-coverage-tune-followup ★最優先に変更
- セクション 2 ロードマップ表: 1-G 行を ✅ 完了 (2026-05-09)、verdict=fail に更新
- セクション 3: 2026-05-09 F-jp-coverage-tune の行を冒頭に追加 (4 指標 pre/post + Grounding API 構造的限界 + graceful fallback 0 件等)
- セクション 4 (5 層): F-13.B 行に F-jp-coverage-tune の verify_two_stage 実装と verdict=fail を追記
- セクション 5: 触ってよい領域に `tests/test_jp_coverage_verifier_two_stage.py` + `scripts/measure_two_stage_accuracy.py` 追加、触ってはいけない領域に F-jp-coverage-tune の例外適用を追記
- セクション 6: baseline 1364 passed に更新 + 不変原則 3 例外条件に「設計拡張」用パターンを追加
- セクション 7: 「対症療法じゃなく根本治療」例として F-jp-coverage-tune を追加、CP-1/CP-2 中間チェックポイント方式を新規追加、「動くものを壊さない」例に F-jp-coverage-tune 追加、「いまは各論をコントロールしたくない」例に F-jp-coverage-tune の `_build_angle_query` プロンプト設計を追加

---

## 8. 整合性検証

- **baseline テスト数**: 1345 → 1364 passed (新規 19 件追加、既存全 1345 件維持) ✅
- **不変原則違反**: なし。既存 `verify()` シグネチャ・戻り値型・挙動完全維持を `inspect.signature` で確認、`tests/test_jp_coverage_verifier_domain_extract.py` 30 件 PASS。
- **main HEAD コミット (実測値)**:
  - 着手時: `e1ad637` (F-task-e-finalize マージ後)
  - 完了時: `e1ad637` (本バッチは feature/F-jp-coverage-tune ブランチで作業中、未 commit)
- **生成ファイルの差分確認**: `git status` で `M` (DECISION_LOG / DISCUSSION_NOTES / FUTURE_WORK / src/triage/jp_coverage_verifier.py) + `??` (docs/runs/F-jp-coverage-tune/ + scripts/measure_two_stage_accuracy.py + tests/test_jp_coverage_verifier_two_stage.py) を確認、`docs/CURRENT_STATE.md` も更新済。
- **API エラー耐性発火状況**:
  - per-call timeout 発火: 0 件 (post-tuning)
  - graceful fallback (検索 API 失敗) 発火: 0 件 (post-tuning)
  - 完了済み event_id resume 発火: 0 件 (本バッチは初回実行、resume 機能はテストのみで動作確認)
  - LLM クエリ fallback 発火: 0 件 (post-tuning、analysis_llm_client が安定動作)

---

## 9. カズヤ確認推奨事項 (最終、F-jp-coverage-tune-followup 着手前)

1. **F-jp-coverage-tune-followup 着手 OK 判断**: F-jp-coverage-tune が verdict=fail で完了したが、Grounding API 構造的限界の根本治療は別バッチで実施する方針 (= 本バッチ範囲では対処不能の構造的問題) で問題ないか。

2. **F-jp-coverage-tune-followup の対応案優先順位**: 想定対応軸 (p)/(q)/(r)/(s) のうち、(p) Grounding API 複数クエリ並列発行 + 結果統合 を最有力候補としているが、コスト見積もり (Gemini API call 数 2-4 倍) も加味して判断要。

3. **stream_3 過剰検出 6 件の取り扱い**: F-stream-2-filter-design 責務境界の整理が必要。「特定角度を扱った記事 vs 広範事件のついでに触れた記事」の判別を URL マッチング側で解くのか、後段の LLM 解説価値判定側で解くのかの設計判断。

4. **`verify_two_stage()` の本番組込タイミング**: 現状は新メソッド追加のみで実装パイプライン (`src/main.py`) からは呼び出されていない。F-jp-coverage-tune-followup で精度改善 (Recall 60-80% 達成) してから本番組込する流れか、それとも段階的に組込先を試行するか。

5. **Project Knowledge 最新化リマインダ**: 本バッチ完了 + F-jp-coverage-tune-followup 着手前に Project Knowledge を手動最新化することを推奨。

---

## 10. 環境構築・依存追加

- `requirements.txt` 追加: なし
- 環境変数追加: なし (既存 `GEMINI_API_KEY` 利用)
- 新規パッケージ追加: なし (`concurrent.futures.ThreadPoolExecutor` は標準ライブラリ)

---

## 11. 次バッチへの引継ぎ事項

### F-jp-coverage-tune-followup (★最優先) 着手時に参照すべきデータ

- `docs/runs/F-jp-coverage-tune/measurement_result.json` (post-tuning ベースライン)
- `docs/runs/F-jp-coverage-tune/measurement_result_pre_tuning.json` (Step 4 前ベースライン、dateRestrict 除去前)
- `docs/runs/F-jp-coverage-tune/logs/<event_id>.log` × 23 件 (per-event 詳細、対応案検証時のテストケース)
- `docs/DISCUSSION_NOTES.md` 「2026-05-09: Grounding API の構造的限界」エントリ (★ followup 起案根拠)
- `docs/DISCUSSION_NOTES.md` 「2026-05-09: stream_3 過剰検出」エントリ ((s) 副次論点)

### 対応案 (p) Grounding API 複数クエリ並列発行 + 結果統合 の設計指針

候補クエリパターン:
1. **元タイトル + 「日本 報道」** (現状の `_build_search_query` 仕様、ベースライン)
2. **元タイトル単独** (「日本 報道」接尾辞なし、より広範な検索)
3. **タイトル要約クエリ** (LLM で 6-12 単語に短縮、固有名詞中心)
4. **WL ドメイン名ヒント混入クエリ** (例: `<title> NHK OR 朝日 OR 日経`、特定 WL ドメイン狙い撃ち)
5. **英→日翻訳クエリ** (英語タイトル事象でのみ、LLM で日本語キーワード化)

並列発行 → WL マッチング結果をマージ (重複ドメイン排除、Tier 集約は最高 Tier 採用) → 後続処理は現状の `_filter_excluded` / `_match_whitelist` 流用。

### 期待される改善

- Recall covered: 42.11% → 60-80% (Grounding chunk 数を疑似的に拡張)
- Tier 一致率: 62.50% → 70%+ (複数クエリで上位 Tier ヒット率改善)
- Stream accuracy: stream_2 truth 18 件中の broad miss 10 件を半減できる見込み
- API コスト: 2-4 倍 (要見積もり)

---

*F-jp-coverage-tune (2026-05-09) 完了。Phase A.5-3a-verify ロードマップ 1-G 完了
(verdict=fail)。次は F-jp-coverage-tune-followup ★最優先で Grounding API 構造的
限界の根本治療を議論する。*
