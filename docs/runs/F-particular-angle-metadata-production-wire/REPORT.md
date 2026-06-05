# F-particular-angle-metadata-production-wire (X1) — 完了レポート

最終更新: 2026-05-31 (X1 = `particular_angle_metadata` + `sontaku_signals` の本番配線完了、target_enemy 解消統合、F-analysis-max-tokens-tune 統合、不変原則 4 例外条件 5 点充足適用、CP-3 = W1 完全成功)

> Phase A.5-3a-verify ゲート完了後の **22 つ目のバッチ (1-R)**、**実装バッチ**。
> `docs/PARTICULAR_ANGLE_DEFINITION.md` セクション 3.6-3.7 で正典化された
> `ParticularAngleMetadata` (3 要素 + confidence + nested SontakuSignals) を
> Hydrangea production に配線し、新ルート `generate_script_with_analysis` を起動。
> 副次効果として、F-script-writer-target-enemy-fix-investigate (2026-05-26) で
> 確定の **target_enemy (仮想敵) framing が production から自動退役** した。

---

## 1. バッチ目的

1. **`particular_angle_metadata` + `sontaku_signals` 本番配線** (正典 3.6-3.7 を src/ に翻訳)
2. **新ルート `generate_script_with_analysis` 本番起動** (`ANALYSIS_LAYER_ENABLED=true`)
3. **target_enemy 退役** (新ルートは設計上既に排除済、production-default 化で自動退役)
4. **F-analysis-max-tokens-tune 統合** (ANALYSIS_LLM_MAX_TOKENS=4096 で JSON 切断回避)

## 2. CP 経緯 (3 checkpoints + 1 計画変更)

### CP-1: 改修方針判断 (Task B 完了後)

★ Task B grep で起案前提と実コードの **3 つの乖離** を発見 (クラウド誤り 10 系統の作法が機能):
1. **移植元 `scripts/extract_particular_angle.py` は旧 3 分類版** (perspective_gap 不在、sontaku_signals 一切なし)。4 分類 + sontaku は別 2 スクリプト (`reclassify_annotations.py` + `add_sontaku_signals.py`) にある。
2. **particular_angle 3 要素の名称**: バッチ起案は "broad_event / particular_angle / framing" だが、正典・実スクリプトとも `core_question / differentiation_from_mainstream / hydrangea_axis_alignment`。
3. **`dispatch` は既に配線済** (`main.py:2000` で `if top.analysis_result is not None:`)、batch C-5「dispatch 切替改修」の大半は既存。実作業は extractor 呼出 + metadata 付与 + 新ルート/プロンプトへ metadata 渡し。

カズヤ判断: **推奨バンドル (V1 + α + .env.example true)** で進行。
- V1 = `src/analysis/particular_angle_extractor.py` 新規 (不変原則 4 例外条件 5 点適用、承認済)
- α = 単一 LLM パスで 3 要素 + 4 分類 + sontaku を一括抽出 (+1 call/slot)
- `.env.example` を `ANALYSIS_LAYER_ENABLED=true` に倒し、新ルートを production default 宣言
- 既定: SontakuSignals を ParticularAngleMetadata に nested (正典 3.7.2)、extractor プロンプトは `configs/prompts/analysis/geo_lens/` に外部 .md 化

### CP-2: 試運転計画判断 (Task C/D 完了後)

baseline **1432 → 1466 passed** (新規 +34、破壊ゼロ) を確認後、カズヤ判断 = **5 batch 連続実行** を当初指示。

実行中に **計画変更**: sample mode は `run()` 経由で分析レイヤーブロックを通らない (`run_from_normalized` のみ) と判明。normalized mode で実行を試みるも、利用可能な normalized データが 2026-04-27 (5 週間古) のため GarbageFilter `_MAX_AGE_HOURS=48` で全弾かれる構造。3 batch 連続は技術的に困難 (RSS 重複排除で fresh batch を時間間隔なしで複数取得不可)。

カズヤ判断 (path 変更): **Path A pure (1 fresh batch + 1 run、本番状態維持)**。理由:
- 同一 batch 3 回処理は scaffolding (archive 復元 + RECENCY_GUARD_PENALTY=1.0 + snapshot) が必要、特に recency guard 無効化は本番と違う人工状態を作る → X1 試運転の「本番状態での機械的安定性検証」目的と矛盾。
- jp_coverage_cache が run 2/3 で hit するため run 間分散は部分的にしか見えない (本質的限界)。
- X1 必須目的 (新ルート起動 / target_enemy 退役 / extractor / JSON 切断 / fallback) は 1 fresh batch・1 run で本番状態のまま full に検証可能。

副作用 read-only 調査 (カズヤ条件):
- ingestion は **non-destructive (新規追加のみ、$0 LLM)**、52 sources serial RSS fetch、normalize はルールベース。
- 既存 DB / archive / output 一切不変。

### CP-3: 試運転結果評価 (Task E 完了後)

★ **W1 完全成功** (axis_5 採点後カズヤ判断):
- 試運転: ingestion → batch_id=`20260531_102637` (1326 articles, 47 sources, $0 LLM)
- normalized mode run: exit 0, status=completed, **run_llm=39 (estimate ~44 通り)**, day_publishes=2
- Slot-1 cls-c8876d474612: **新ルート稼働**、target_enemy=None、stream_2_perspective_gap + sontaku.level=high/diplomatic、used_fallback=false、retries=0、char validation passed
- Slot-2 cls-3e9544fee58f: article-only mode、analysis_result populated
- Slot-3 cls-c7d507fc74e8: analysis_result=None → deprecation gate で正しく skip
- axis_5 採点: 城→海運→電気代の具体着地で情報密度高、target_enemy 退役が質に表れたとカズヤ評価。

## 3. 実装内容

### 3.1 改修ファイル (8 種、計 +320 行程度)

| 種別 | ファイル | 変更概要 |
|---|---|---|
| **改修** | `src/shared/models.py` | `SontakuSignals` + `ParticularAngleMetadata` クラス追加 (sontaku は nested、正典 3.7.2)。`AnalysisResult` に `particular_angle_metadata: Optional[...] = None` 追加 (後方互換) |
| **新規** ★ | `src/analysis/particular_angle_extractor.py` | 単一パス α extractor。3 要素 + 4 分類 + sontaku を 1 LLM call で抽出。`get_analysis_llm_client()` 経由 (Gemini 3 温度ガード自動)。失敗時 None (後方互換) |
| **新規** | `configs/prompts/analysis/geo_lens/particular_angle_extract.md` | 統合プロンプト (extract+reclassify+add_sontaku 3 スクリプト由来の判定基準を統合)、外部 .md 分離 (CLAUDE.md 方針) |
| **改修** | `configs/prompts/analysis/geo_lens/script_with_analysis.md` | particular_angle_metadata + sontaku_signals 入力ブロック追加。各論ルール足さず LLM の知性に委ねる文言 (クラウド誤り 9 回避) |
| **改修** | `src/generation/script_writer.py` | `_build_script_with_analysis_prompt` に新プレースホルダ渡し。None 時は "(none)" placeholder。`generate_script_with_analysis` signature 不変、既存ルート `write_script` 完全不変 (不変原則 2) |
| **改修** | `src/main.py` | 分析ブロック L3028 で `extract_for_scored_event` を import + 呼出、`model_copy(update={...})` で metadata 付与。失敗時 non-fatal で None 維持。`run_analysis_layer` 不変 (不変原則 4) |
| **改修** | `.env.example` | `ANALYSIS_LAYER_ENABLED=false→true` (committed default)、`ANALYSIS_LLM_MAX_TOKENS=2000→4096` (F-analysis-max-tokens-tune 統合) |
| **追加** | `.env` (gitignored) | 同上 + DEFAULT_CHANNEL_ID=geo_lens |
| **新規** | `tests/conftest.py` | autouse fixture: 各テスト開始時に `ANALYSIS_LAYER_ENABLED=false` 強制。.env true 化のテスト波及防止 (新ルート挙動 test は既に monkeypatch 個別 override 済) |
| **新規** | `tests/test_models_particular_angle.py` | 10 tests (Pydantic 構造 + nesting + model_copy + JSON round-trip) |
| **新規** | `tests/test_particular_angle_extractor.py` | 21 tests (coerce / parse / retry / 失敗時 None / mock LLM) |
| **追加** | `tests/test_script_writer_with_analysis.py` | 3 tests (X1 placeholder rendering + target_enemy 維持) |

### 3.2 不変原則 4 例外条件 5 点充足 (最終確認)

| 条件 | 充足 | 根拠 |
|---|---|---|
| (a) バグ修正/機能追加が目的 | ✅ | target_enemy 解消 + particular_angle 起動 |
| (b) 既存メソッド完全維持 | ✅ | `analysis_engine.py`/`jp_coverage_verifier.py` 等 src/analysis 既存ファイル **0 行変更**。`run_analysis_layer` 経由せず main.py から `model_copy` で metadata 付与 |
| (c) データ追加のみ | ✅ | AnalysisResult optional field + 新規モジュール 1 つ |
| (d) baseline 1432 維持 | ✅ | **1432 → 1466 passed** (新規 +34、破壊ゼロ、113s) |
| (e) カズヤ承認 | ✅ | X1 プロンプト事前承認 + F-script-writer-target-enemy CP-1 sanctioned + 本バッチ CP-1 承認 |

## 4. テスト結果

- **baseline**: 1432 → **1466 passed** (新規 +34、破壊ゼロ)
- **新規テスト構成**:
  - `tests/test_models_particular_angle.py`: 10 tests
  - `tests/test_particular_angle_extractor.py`: 21 tests
  - `tests/test_script_writer_with_analysis.py` 追加: 3 tests
- **conftest.py autouse**: `.env` の `ANALYSIS_LAYER_ENABLED=true` がテストランタイムに propagate するのを抑止、既存テスト無改修で保護

## 5. 試運転結果 (Task E、Path A pure)

### 5.1 ingestion

- batch_id: `20260531_102637`
- sources: 47 (configs/sources.yaml の有効ソース)
- new articles: **1326**
- duplicates skipped: 198
- cost: $0 LLM (ルールベース normalize)
- duration: ~32 秒

### 5.2 normalized mode run

- exit code: 0、status: completed、job_id: `71de7c0b-baeb-4531-a916-dbf02f59513f`
- llm_calls: **39** (estimate ~44 通り)、day_publishes: 2
- archive: 94 files moved to `data/archive/20260531/20260531_102637/`

### 5.3 Slot-1 (cls-c8876d474612) X1 核心検証

| 項目 | 結果 |
|---|---|
| route | `[ScriptWithAnalysis] Generated via gemini` (新ルート稼働 ✅) |
| analysis_result | populated (cultural_blindspot axis、paradigm_shift_100s) |
| particular_angle_metadata | populated、extraction_confidence=**high** |
| stream_classification | `stream_2_perspective_gap` (候補A と同系統) |
| hydrangea_axis | "4. 関心領域・地政学的死角" |
| sontaku_signals.level | **high** / type=**diplomatic** / extraction_confidence=high |
| sontaku reasoning | 米国・イスラエル忖度の構造説明 (Hydrangea ミッションど真ん中) |
| **★ target_enemy** | **None** (script、video_payload director_meta に不在) ← **退役確認** |
| selected_pattern | `Cultural Divide` (情報密度型 4 内) |
| char validation | passed (hook=22, setup=75, twist=177, punchline=81) |
| used_fallback | false |
| retries | 0 |
| total_duration_sec | 100s |

### 5.4 axis_5 採点 (カズヤ手動)

カズヤ評価要旨:
- 「城→海運→電気代」の具体着地で情報密度高、target_enemy 退役が質に表れた
- punchline で「冷徹なツケの現場」(シニカル × 生活実感) — Hydrangea ブランドポジション整合
- X1 必須目的の品質面での裏付け確認

## 6. ★ 後続バッチへの引継ぎ事項 (X1 範囲外、Task F 記録対象)

### 6.1 【高リスク事実検証の必要性を production 実証】 — FUTURE_WORK 緊急度 **高**

article 本文に死者数 (レバノン側 3,371人 / 負傷 10,129人)、イスラエル軍兵士死亡 25 人、スモトリッチ財務相の過激発言引用 ("ドローン 1 機につきレバノン国内の建物 100 棟を破壊すべき") などの高リスク数字・引用が含まれる。これらが元ソース (Middle East Eye / AlJazeera) に実在するかは本 trial では未検証。**X1 が「高リスク事実検証ワークフロー」(1-T、Editorial Guardian=gemini-3.1-pro-preview 配線) が第一作公開前に必須であることを production で実証** した。

### 6.2 【punchline 尻切れ】 — FUTURE_WORK

Slot-1 punchline 末尾「そこから繋がるのが、」で文未完結。loop-2 (連鎖含意) の意図か生成バグか要切り分け。script_writer の loop_mechanism 仕様起因なら別バッチ。

### 6.3 【title guard + broad/particular 切り分け曖昧さ】 — DISCUSSION_NOTES 記録

- `platform_title="日本では報道されないIsraelの視点"` ← `stream_2_perspective_gap` (一部報道済) なのに silence_gap 絶対表現混入 (既知、1-Q.5 = F-title-guard-coverage-claim-policy で扱う)
- 加えて article Facts セクションが「現在のところ、日本の主要メディアからのこの特定の出来事に関する詳細な報道は確認できません」と silence_gap 寄りに書いており、broad_event (中東紛争一般、日本で報道済) と particular_angle (ボーフォール城再占領、日本未深掘り) の切り分け精度に曖昧さ。F-title-guard-coverage-claim-policy + 第一作 framing 指針 (Phase A.5-3b) で扱う。

### 6.4 【視覚プロンプトの旧語彙残存】 — FUTURE_WORK 低優先

`src/generation/video_payload_writer.py:72` の twist visual_goal テンプレートに `"裏の構造・仮想敵・地政学/カネ/権力の文脈を図解で暴く"` がハードコード。target_enemy 退役済だが視覚プロンプト側に旧語彙が残存 (narration には実害なし、video_payload 出力に "仮想敵" 文字列が含まれる)。

### 6.5 【run 間分散 未検証】 — F-periodic-health-check 統合候補

1 batch・1 run のため未検証。本番状態を歪めず観察するには実運用で時間差 fresh batches が貯まる必要があるため、F-periodic-health-check (ChatGPT Round 2 指摘 5 = tier fallback / retry 観測強化) に統合する候補。

### 6.6 【試運転データ確保の構造的困難】 — DISCUSSION_NOTES + FUTURE_WORK

本バッチで blocker 4 連鎖 (sample mode 分析未起動 → スタール データ枯渇 → GarbageFilter 48h → RSS 重複排除) を経験。根本原因 = 「試運転用 fresh データ確保手段が PoC 未整備」。試運転データ確保手順の整備を別バッチとして登録。

## 7. 自分で判断した内容 (CLAUDE.md 判断ルール記録)

- **判断 1**: SontakuSignals を ParticularAngleMetadata に nested 配置 (正典 3.7.2 と整合、AnalysisResult への optional field 1 つで完結)。バッチ起案 C-1 は「2 クラスを別 field」だが正典に従う。CP-1 で報告済。
- **判断 2**: extractor を単一 LLM パス α で実装 (移植元 3 スクリプトの判定基準を 1 プロンプトに統合)。CP-1 でカズヤ判断 (β 3 パスは cost 3 倍)。
- **判断 3**: tests/conftest.py autouse fixture で `ANALYSIS_LAYER_ENABLED=false` を強制。`.env` の true 化がテストランタイムに propagate して既存 smoke/budget tests を破壊する問題を、新規 conftest 追加 (既存テスト無改修) で解決。
- **判断 4**: ingestion read-only 調査結果 (non-destructive) を踏まえ、processing → pending リセットの代替として 2 stale batches を元の processing 状態に戻し state クリーンに保つ。
- **判断 5**: Path A pure (1 batch・1 run) に変更後、run 間分散は明示的に「未検証」として CP-3 / FUTURE_WORK に記録 (誤魔化さない)。

## 8. 不変原則違反 / 触ってはいけないファイルへの変更要望

なし。
- 不変原則 1 (article_writer.py): ✅ 完全不変
- 不変原則 2 (script_writer.py 既存ルート write_script): ✅ 完全不変、新ルート generate_script_with_analysis のみ拡張
- 不変原則 3 (src/triage/ 既存): ✅ 完全不変
- 不変原則 4 (src/analysis/ 全般): ✅ 既存ファイル不変 + particular_angle_extractor.py 新規作成のみ (例外条件 5 点充足適用、カズヤ承認済)
- 不変原則 5 (既存テスト): ✅ baseline 1432 → 1466 維持、新規テストへの追加のみ、既存テスト本体不変

## 9. BATCH_PROTOCOL Task 1-5 適用結果

- **Task 1** (DECISION_LOG): X1 バッチエントリ追加 + 前バッチ F-gemini-quality-tier-poc コミットハッシュ追記 (880ebfb / f21f373)
- **Task 2** (FUTURE_WORK): X1 完了済み移動 (F-particular-angle-metadata-production-wire / F-analysis-max-tokens-tune)、新規 6 タスク追加 (上記セクション 6 の 6.1-6.4 / 6.6)
- **Task 3** (REPORT 末尾に Task 1-5): 本セクション
- **Task 4** (DISCUSSION_NOTES): 4-A 新規 1 件 = X1 完了 + 試運転実証 + 6 引継ぎ事項。4-B 既存再評価 = target_enemy 関連エントリ Resolved 化、新ルート未配線エントリ Resolved 化
- **Task 5** (CURRENT_STATE): 全置換更新 (22 つ目のバッチ 1-R、次バッチ候補 1st: 1-Q.5 F-title-guard-coverage-claim-policy / 2nd: 1-T 高リスク事実検証ワークフロー / 3rd: 1-S Phase A.5-3b 第一作起案)

## 10. 環境構築・依存追加

- requirements.txt 追加: なし
- 環境変数追加: `.env` / `.env.example` に `ANALYSIS_LAYER_ENABLED=true` + `ANALYSIS_LLM_MAX_TOKENS=4096` (F-analysis-max-tokens-tune 統合)

---

*X1 = F-particular-angle-metadata-production-wire は Phase A.5-3a-verify ゲート完了後 22 つ目のバッチ。
particular_angle_metadata + sontaku_signals (nested) の本番配線完了で、新ルートが production
default 起動、target_enemy framing が自動退役。1 fresh batch trial で全 X1 必須目的を達成し、
6 つの後続バッチ向け引継ぎ事項を確定。第一作 (1-S) 着手前に必須の 1-Q.5 (F-title-guard) と
1-T (高リスク事実検証) を最優先で並走する設計が確立した。*
