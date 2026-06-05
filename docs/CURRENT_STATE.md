# Hydrangea — Current State (CURRENT_STATE.md)

最終更新: 2026-05-31 (★ F-particular-angle-metadata-production-wire (X1) 完了、Phase A.5-3a-verify ゲート完了後の **22 つ目のバッチ (1-R)**、**実装バッチ**。`docs/PARTICULAR_ANGLE_DEFINITION.md` セクション 3.6-3.7 で正典化された `ParticularAngleMetadata` (3 要素 + nested `SontakuSignals`) を Hydrangea production に配線、新ルート `generate_script_with_analysis` を production default 起動 (`ANALYSIS_LAYER_ENABLED=true`)。**target_enemy framing が production から自動退役** (Slot-1 試運転で target_enemy=None 確認)。**不変原則 4 例外条件 5 点充足適用** で `src/analysis/particular_angle_extractor.py` 新規作成 (単一パス α、get_analysis_llm_client 経由 = Gemini 3 系 temperature ガード + ANALYSIS_LLM_MAX_TOKENS env 自動適用)。CP-1 でクラウド誤り 10 系統の grep 作法により起案前提と実コードの 3 つの乖離を発見・訂正 (移植元 `scripts/extract_particular_angle.py` は旧 3 分類版 + sontaku 不在、3 要素名称ズレ "broad_event/particular_angle/framing" → 正典 "core_question/differentiation_from_mainstream/hydrangea_axis_alignment"、dispatch 既配線)。CP-2 で sample mode 分析未起動 + スタール枯渇 + GarbageFilter 48h でブロック → **Path A pure (1 fresh batch + 1 run、本番状態維持)** に変更 (カズヤ判断、3 回処理 scaffolding は recency_guard 無効化等で本番と違う人工状態を作るため不採用)。試運転: ingestion `batch_id=20260531_102637` (47 sources / 1326 articles / $0 LLM) + normalized mode exit 0 / run_llm=39 / Slot-1 cls-c8876d474612 で全 X1 必須目的達成 (stream_2_perspective_gap + sontaku.level=high/diplomatic + target_enemy=None + Cultural Divide + char validation passed + used_fallback=false / retries=0 + JSON 切断ゼロ)。axis_5 カズヤ採点で「築900年の城→日本郵船→電気代」具体着地 + target_enemy 退役が質に表れたと評価、**CP-3 = W1 完全成功**。**F-analysis-max-tokens-tune 統合完了** (.env / .env.example で `ANALYSIS_LLM_MAX_TOKENS=2000→4096`)。baseline 1432 → **1466 passed** (新規 +34、破壊ゼロ、113s)。6 後続バッチ向け引継ぎ事項を FUTURE_WORK / DISCUSSION_NOTES に確定: 高リスク事実検証必要性 production 実証 (1-T 必須化、★高に格上げ) / punchline 尻切れ未完結 / title guard + broad/particular 切り分け曖昧さ (1-Q.5 + 第一作 framing) / 視覚プロンプト「仮想敵」語彙残存 / run 間分散未検証 (F-periodic-health-check 統合) / 試運転データ確保の構造的困難 (F-trial-data-procurement-protocol)。前バッチ F-gemini-quality-tier-poc のコミットハッシュ `880ebfb` / `f21f373` を DECISION_LOG に追記。次バッチ最有力: **1-Q.5 F-title-guard-coverage-claim-policy** (第一作着手前必須、X1 trial で本番再現実証))

> このドキュメントは Hydrangea の「今この瞬間のスナップショット」。
> 各バッチ完了時に Claude Code が **全置換更新** する (追記ではない)。
> 過去の経緯は DECISION_LOG.md / FUTURE_WORK.md / DISCUSSION_NOTES.md を参照。

---

## 0. Hydrangea コアミッション (2 系統並立)

> ★最重要: 別チャット移行時のクラウド誤り再発防止のため冒頭配置 (F-doc-cleanup-followup / 2026-05-03)。
> 系統 1 中心で理解して系統 2 を過小評価する誤りはクラウド誤り 7 として記録済み。

Hydrangea のコアミッションは **2 系統並立** で、片方だけでは Hydrangea のメディア性が成立しない。

★ 2026-05-07 (F-particular-angle-design) で系統 1 / 系統 2 の判定単位が
**「特定角度」(particular_angle)** に正典化された。判定基準の正本は
`docs/PARTICULAR_ANGLE_DEFINITION.md`。

★ 2026-05-08 (F-particular-angle-redesign) で **3 分類 → 4 分類化** が完了。
系統 2 (perspective_gap) を独立させ「完全空白」と「観点不足」を分離した。

★ 2026-05-08 (F-particular-angle-redesign-extension) で **系統名 1/1.5/2 →
1/2/3** にリネーム + sontaku_signals 別軸メタデータ独立化 + MECE 判別基準
明示 + クラウド誤り 9 (各論コントロールの誘惑) を CLAUDE.md / DISCUSSION_NOTES
に記録。

★ 2026-05-16 (F-jp-coverage-llm-judgement-extraction) で **LLM judgement
bypass 問題を Option (i) で根本治療完了**。`_parse_llm_judgement` 新規 +
B-3' 表。LLM の **明示的否定 (no_match)** のみ尊重し **沈黙 (uncertain)** を
否定と読み替えない。

★ 2026-05-26 (F-jp-coverage-cache-judgement-persist) で **F-13.B の
llm_judgement / llm_judgement_text を 24h cache に永続化** (案 A、DB schema 2 列 +
idempotent migration + verifier の save/get 拡張、判定ロジック不変)。

★ 2026-05-26 (F-script-writer-target-enemy-fix-investigate) で **Gemini Round 1
独自指摘の `target_enemy` 不整合問題を調査専用バッチで実態確認**。真因 a 確定 =
production 稼働中の旧ルート `write_script` が仮想敵 framing を viewer-facing に
出力するが不変原則 2 で修正不可、新ルートは設計上既に排除済み = **新ルート配線
(X1) が唯一の解消経路**。

★ 2026-05-27 (F-gemini-3.5-flash-api-audit) で **Gemini 3.5 Flash (Stable) の
API 破壊的変更の影響範囲を調査専用バッチで実態確認**。真因 b 確定 = 事前情報の
4 破壊的変更候補 + structured outputs はいずれも Hydrangea 本番パスに該当箇所
ほぼゼロ。**migration 不要**、CP-1 = Y1 (quality-tier-poc に直進)。

★ 2026-05-27 (F-docs-update-chatgpt-round2-and-error10、docs-only) で **ChatGPT
Round 2 レビュー (7 指摘) を docs 正本と grep 裏取り照合**。指摘 3/4 = 解消済確認、
指摘 2/6/7 = 新規 3 タスク化、指摘 5 = F-periodic-health-check スコープ拡張。★★
**クラウド誤り 10 を CLAUDE.md に明文化**。

★ 2026-05-27 (F-gemini-quality-tier-poc) で **最終布陣 v2** を配線。
QUALITY (judge/script/analysis) = gemini-3.5-flash/MAX2、ARTICLE = gemini-2.5-flash/MAX1 (role 新設分離)、
LIGHTWEIGHT (garbage/merge) = gemini-3.1-flash-lite/MAX1 + JUDGE_MODEL 明示 + Gemini 3 系 temperature ガード。
クラウド誤り 10 派生「外部 AI セカンドオピニオンの権威化」を CLAUDE.md + DISCUSSION_NOTES に正本化。

★★★ 2026-05-31 (F-particular-angle-metadata-production-wire、X1、1-R) で
**`particular_angle_metadata` + nested `sontaku_signals` を Hydrangea production に配線完了**。
新ルート `generate_script_with_analysis` が `ANALYSIS_LAYER_ENABLED=true` で production default 起動、
**target_enemy framing が production から自動退役** (Slot-1 試運転で target_enemy=None 確認、退役の質的
裏付けはカズヤ axis_5 採点で「城→海運→電気代」具体着地 + 仮想敵不在で確認)。不変原則 4 例外条件 5 点
充足適用で `src/analysis/particular_angle_extractor.py` 新規 (単一パス α、3 要素 + 4 分類 + sontaku を
1 LLM call で抽出)。F-analysis-max-tokens-tune 統合 (ANALYSIS_LLM_MAX_TOKENS=4096)。baseline 1432 →
1466 passed (新規 +34、破壊ゼロ)。6 後続バッチ向け引継ぎ事項 (高リスク事実検証必須化 / punchline 尻切れ /
title guard 実証 / 視覚プロンプト旧語彙 / run 間分散 / 試運転データ確保) を確定。

### 系統 1 (silence_gap): 完全な情報空白 — 広範事件も特定角度も日本主要メディアで未報道

完全な情報空白で、Hydrangea コアミッションど真ん中。台本表現は「日本では報じられ
なかった」が成立する。25 件アノテーション最終分類で 4 件 (16%)。

### 系統 2 (perspective_gap、F-particular-angle-redesign で新設): 観点不足 — 広範事件は報道済み、特定角度は未報道

事件本体は日本でも取り上げられたが、海外メディアが独自に掘った構造分析角度は
深掘りされていない。台本表現は「日本でも事件は取り上げられたが、◯◯という構造に
は触れられていない」。25 件最終分類で **20 件 (80%)**。

★★★ Phase A.5-3b 第一作 (候補A cls-6889e9e1c7ac) は本系統の framing で起案する
(2026-05-16 確定、2026-05-19 F-trial-run-candidate-a-reverify で **最終確定**)。

★ X1 (2026-05-31) 試運転 Slot-1 cls-c8876d474612 (Israel seizes strategic castle, Lebanon)
も同系統 (stream_2_perspective_gap) を抽出し、新ルート + sontaku.level=high/diplomatic で生成成功 =
**候補A 系統での新ルート挙動が production 経路で実証された** (axis_5 採点でカズヤ評価)。

### 系統 3 (framing_inversion): 報道差の背景解説 — 特定角度も報道済み + 解釈差 + 忖度シグナル

広範事件 + 特定角度も日本主要メディアで報道済み + 評価フレーム対立 +
sontaku_signals.level=high/medium の 3 条件。25 件最終分類で **0 件** ★ 想定外
(根本治療は Phase A.5-3b 第二作のサンプル拡充)。

### ★ docs 概念整理と production-pipeline の乖離 (2026-05-11 観察、★ X1 / 2026-05-31 で 大幅解消)

★★ **2026-05-31 (X1 / F-particular-angle-metadata-production-wire) で本乖離が大幅解消**:
- ✅ `particular_angle_metadata` / `sontaku_signals`: src/ 配下に Pydantic クラス + 抽出 extractor 配線完了
- ✅ `generate_script_with_analysis` 新ルート: production default 起動 (ANALYSIS_LAYER_ENABLED=true)
- ✅ target_enemy framing: 新ルート稼働で production から自動退役 (Slot-1 試運転で確認)
- ⚠️ `verify_two_stage()` 系統 1/2/3 機械判別: **本番未配線のまま** (FUTURE_WORK 高、X1 範囲外、別バッチ)
- ⚠️ legacy fallback 経路 (budget 枯渇 / no_client / llm_error 時) は依然として旧ルート `write_script`
  に落ち target_enemy 復活する構造 (X1 試運転では未到達、構造的限界として記録)

### ブランドポジション

ReHacQ・東洋経済オンラインのトーン。シニカル × 知性、ただし
**「シニカル × 視聴者の生活実感への着地」** が punchline 定義。
陰謀論・扇動禁止、情報密度で勝負。ターゲット: 20 代後半〜40 代の知的好奇心が
高いビジネス層。★ 視覚ブランドは ADR-0001 で正典化 (5 色パレット、editorial
路線、cinematic/photorealistic 禁止)。

### 3 チャンネル構想と現フォーカス

| チャンネル | 内容 | 状態 |
|---|---|---|
| `geo_lens` | Geopolitical Lens (政治・経済地政学) | **現在唯一のフォーカス** |
| `japan_athletes` | 海外で戦う日本人アスリート | Phase B 以降、未確定 |
| `k_pulse` | 韓国エンタメ | Phase B 以降、未確定 |

Phase A.5-3d で本番リリースするのは geo_lens のみ単独。

### Phase B 以降の新選択肢: 大規模調査機能 (オンデマンド深掘り)

通常運用とは別に、カズヤが事象を指定して大規模調査 → 長尺動画 + 記事を
生成する手動起動パイプラインを Phase B 以降に追加する構想。

---

## 1. リポジトリ状態

- **main HEAD コミット**: `f21f373` (Merge branch 'feature/F-gemini-quality-tier-poc')。X1 = F-particular-angle-metadata-production-wire は feature ブランチ `feature/F-particular-angle-metadata-production-wire` で Task A-F 完了、本完了レポート提示後にカズヤ承認 → commit/merge 実行 (Task G)。★ 本バッチは実装バッチ (models.py / particular_angle_extractor.py 新規 / script_writer.py 新ルート / main.py / プロンプト .md / env / tests)
- **直近 5 件のログ (main、Task G merge 前)**:
  ```
  f21f373 Merge branch 'feature/F-gemini-quality-tier-poc'
  880ebfb feat: F-gemini-quality-tier-poc 最終布陣 v2 配線 + Gemini 3 系 temperature 修正 + 外部 AI 権威化警告 CLAUDE.md 追記
  112539d Merge branch 'feature/F-docs-update-chatgpt-round2-and-error10'
  41f09d6 docs: F-docs-update-chatgpt-round2-and-error10 ChatGPT Round 2 レビュー由来の新規 3 タスク FUTURE_WORK 追加 + クラウド誤り 10 系統 CLAUDE.md 明文化 (docs-only)
  2f99ebd Merge branch 'feature/F-gemini-3.5-flash-api-audit'
  ```
- **baseline テスト数**: **1466 passed** (★ X1 = baseline 1432 + 新規 +34 [test_models_particular_angle.py 10 + test_particular_angle_extractor.py 21 + test_script_writer_with_analysis.py 追加 3]。Task A baseline 1432 passed 確認済 = 76.67s、Task D 後 1466 passed = 113.12s、Task E 試運転前 1466 passed 再確認 = 118.13s)
- **DB schema 変更**: なし (本バッチは新ルート配線 + extractor 新規のみ。AnalysisResult Pydantic に optional field 追加のみで永続化 schema 不変)

## 2. 現在のフェーズ

- **Phase**: Phase A.5-3a-verify **完了** (2026-05-07、ゲート完了後 22 バッチ目が本バッチ)
- **進行中バッチ**: なし (F-particular-angle-metadata-production-wire 完了直後、Task G 完了レポート提示 → カズヤ承認待ち → commit/merge Task G)
- **次バッチ候補と推奨** (★ X1 / 2026-05-31 更新):
  - ~~**X1 = F-particular-angle-metadata-production-wire (1-R)**~~ ✅ **完了 (2026-05-31)**。`particular_angle_metadata` + nested `sontaku_signals` 本番配線 + 新ルート起動 + target_enemy 自動退役 + F-analysis-max-tokens-tune 統合。baseline 1432 → 1466 passed、Path A pure trial で CP-3 = W1 完全成功。
  - **1st: F-title-guard-coverage-claim-policy (1-Q.5)** ★★高 (★ 第一作着手前必須、X1 試運転で本番再現実証)。X1 trial で `platform_title="日本では報道されないIsraelの視点"` が stream_2_perspective_gap (一部報道済) に対して silence_gap 絶対表現を出力、さらに article Facts も silence_gap 寄りに書かれ broad/particular 切り分け曖昧さを production 経路で確認 = 本タスクの必要性を実証。`manual_poc/` 配下の coverage_claim_policy 構造データ (allowed_claim_level / forbidden_title_claims) + 生成後 title_layer_guard で虚偽防止 + article 側 framing 指針も統合。工数 3-5h
  - **2nd: 第一作公開前の高リスク事実検証ワークフロー (1-T)** ★高 (★ X1 試運転で必須性 production 実証 = 緊急度 中 → 高に格上げ)。X1 trial で article 内に死者数 (3,371 人 / 10,129 人) / 兵士死亡 25 人 / スモトリッチ過激発言引用が production 未検証と判明 = Editorial Guardian (gemini-3.1-pro-preview) 配線が第一作公開前に必須。
  - **3rd: Phase A.5-3b 第一作起案 (1-S)** ★ (緊急度 高、確定モデル [QUALITY=gemini-3.5-flash / article=gemini-2.5-flash] + 新ルート [particular_angle_metadata + sontaku_signals + target_enemy 排除] で実装。候補A cls-6889e9e1c7ac 手動 event 固定 + 実台本生成 + perspective_gap framing + axis_5 採点)
  - **4th: F-script-punchline-tail-cut-investigate** ★中 (X1 試運転で観察、Slot-1 punchline 「そこから繋がるのが、」未完結。loop-2 仕様か生成バグかの切り分け)
  - **5th: F-trial-data-procurement-protocol** ★中 (X1 試運転 blocker 4 連鎖から起案、試運転実行手順整備 + GarbageFilter env tunable 化判断 + replay_stuck_batch.py 整備)
  - **6th: F-evidence-jp-coverage-audit-trail** ★中 (案 B、score_breakdown evidence 証跡化)
  - **7th: F-grounding-determinism-audit** ★ (broad Grounding API 分散集約戦略)
  - **8th: F-periodic-health-check** ★ (Phase A.5-3d 着手時、cron 完全自動投稿前提。★ ChatGPT Round 2 指摘 5 + X1 引継ぎ「run 間分散統計」を統合)
  - **9th: 本番配線判断バッチ群 (X1 に内包しない残分、並走可)**: verify_two_stage 本番配線 / F-stream-2-filter-design 責務範囲再評価
  - **10th: 低優先整合タスク群** ★低: editorial_mission_filter 独立分離 / run_summary model_roles 忠実化 / F-video-payload-visual-prompt-target-enemy (視覚プロンプト旧語彙除去) / locale key 定数一元化 / F-job-record-av-path (Phase A.5-3c DB schema 整理に統合)
- **推奨フロー**:
  - commit/merge (本完了レポート提示 → カズヤ承認後)
    → **1-Q.5 F-title-guard-coverage-claim-policy (第一作着手前必須、X1 trial で本番再現実証)**
    → 1-T 高リスク事実検証ワークフロー (Editorial Guardian 配線、X1 trial で必須性実証)
    → 1-S Phase A.5-3b 第一作起案 (確定モデル + 新ルート + 候補A perspective_gap framing + axis_5 採点)
    → 並走: F-script-punchline-tail-cut-investigate / F-trial-data-procurement-protocol / F-evidence-jp-coverage-audit-trail / F-grounding-determinism-audit / 本番配線残分
- **★ Phase A.5-3b 第一作着手前の追加確認事項** (カズヤ指示、2026-05-31 更新):
  1. ~~F-trial-run-candidate-a-reverify~~ ✅ **完了 (2026-05-19)**
  2. ~~F-image-prompt-spec スコープ再定義~~ ✅ **完了 (2026-05-18)**
  3. ~~F-gemini-model-migrate-emergency / -3.5-flash-api-audit / -quality-tier-poc~~ ✅ **完了 (2026-05-19 〜 27)**
  4. ~~X1 = particular_angle_metadata + sontaku_signals 本番配線 + target_enemy 解消統合 + F-analysis-max-tokens-tune 統合~~ ✅ **完了 (2026-05-31)**
  5. **F-title-guard-coverage-claim-policy** (★★高、第一作着手前必須、X1 trial で本番再現実証)
  6. **第一作公開前の高リスク事実検証ワークフロー** (★高に格上げ、Editorial Guardian=gemini-3.1-pro-preview 配線、X1 trial で必須性実証)
  7. ElevenLabs 声選定 (着手前 30 分作業、既存登録済み、カズヤ手作業)
  8. Remotion セットアップ (第一作で Claude Code に書かせる、Node 環境カズヤ手動準備、ADR-0002 D-minimal)

### Phase A.5-3a-verify ロードマップ (★ X1 / 2026-05-31 更新版)

**ゲート完了**: 1-A〜1-D''' 全段階完了で Phase A.5-3a-verify ゲート完了 (2026-05-07)。
本バッチはゲート完了後の **22 つ目のバッチ**。

| 段階 | バッチ | 状態 | 概要 |
|---|---|---|---|
| 1-A〜1-K | (F-verify-jp-coverage-golden 〜 F-image-prompt-spec) | ✅ 完了 | ゲート完了 + 特定角度正典化 + LLM judgement bypass 根本治療 + 候補A 前提確定 + ADR 3 件 |
| 1-L | F-gemini-model-audit | ✅ 完了 (2026-05-19) | Gemini モデル戦略 影響調査 |
| 1-M | F-gemini-model-migrate-emergency | ✅ 完了 (2026-05-19) | 5/25 shutdown 緊急対応、404 即 raise リスク根絶 |
| 1-N | F-f1-locale-key-fix | ✅ 完了 (2026-05-25) | F-1 locale key bug 根本治療、機能ロジック不変 |
| 1-O | F-jp-coverage-cache-judgement-persist | ✅ 完了 (2026-05-26) | F-13.B llm_judgement の 24h cache 永続化 (案 A) |
| 1-P | F-script-writer-target-enemy-fix-investigate | ✅ 完了 (2026-05-26、調査専用) | target_enemy 不整合問題実態確認、X1 への統合確定 |
| 1-P.5 | F-gemini-3.5-flash-api-audit | ✅ 完了 (2026-05-27、調査専用) | API 破壊的変更なし確定 (真因 b) |
| 1-P.6 | F-docs-update-chatgpt-round2-and-error10 | ✅ 完了 (2026-05-27、docs-only) | ChatGPT Round 2 統合 + クラウド誤り 10 CLAUDE.md 明文化 |
| 1-Q | F-gemini-quality-tier-poc | ✅ 完了 (2026-05-27、実装) | 最終布陣 v2 配線 (QUALITY/ARTICLE/LIGHTWEIGHT) + JUDGE_MODEL 明示 + Gemini 3 温度ガード |
| **1-R** | **F-particular-angle-metadata-production-wire (X1)** | ✅ **完了 (2026-05-31、実装)** | **ゲート完了後 22 つ目**。particular_angle_metadata + nested sontaku_signals 本番配線 + 新ルート production default 起動 (ANALYSIS_LAYER_ENABLED=true) + **target_enemy 自動退役** + F-analysis-max-tokens-tune 統合 (4096)。不変原則 4 例外条件 5 点充足適用で `src/analysis/particular_angle_extractor.py` 新規 (単一パス α、get_analysis_llm_client 経由)。CP-1 でクラウド誤り 10 系統の grep 作法により起案前提と実コードの 3 つの乖離 (移植元旧 3 分類版、3 要素名称、dispatch 既配線) を訂正。CP-2 で sample/スタール/48h/RSS 重複 blocker 4 連鎖 → Path A pure (1 fresh batch + 1 run、本番状態維持) に変更。試運転: ingestion `20260531_102637` + normalized exit 0 / run_llm=39 / Slot-1 で全 X1 必須目的達成。axis_5 カズヤ採点で CP-3 = W1 完全成功。baseline 1432→1466 passed。6 引継ぎ事項を FUTURE_WORK / DISCUSSION_NOTES に確定 |
| 1-Q.5 | F-title-guard-coverage-claim-policy | ★★高 (第一作着手前必須) | **X1 試運転で本番再現実証**。perspective_gap に silence_gap 絶対表現が title/article 両方に出力されるリスクを coverage_claim_policy 構造データ + 生成後 guard + 第一作 framing 指針で防止 |
| 1-S | Phase A.5-3b 第一作起案 | ★ 緊急度 高 | 確定モデル + 新ルート + 候補A perspective_gap framing + axis_5 採点 |
| 1-T | 第一作公開前の高リスク事実検証ワークフロー (Editorial Guardian 配線) | ★高に格上げ (X1 trial で必須性実証) | article 内の高リスク数字・引用検証ワークフロー実装、gemini-3.1-pro-preview 配線 |
| 1-U | F-evidence-jp-coverage-audit-trail / F-grounding-determinism-audit / 本番配線残分 (verify_two_stage / F-stream-2-filter-design) | ★ 並走候補 | evidence 監査トレース新設 / broad Grounding 分散集約 / 二段階クエリ機械判別 |

### Phase A.5-3d 投稿対象の補足

Phase A.5-3d で本番リリースする対象は **geo_lens (政治・経済) のみ**。
投稿先は TikTok と YouTube Shorts の両方同時、完全自動投稿 (cron 6 時間おき、
人手介入ゼロ、投稿前ゲートで品質保証)。★ 投稿前ゲートのチェックリスト 6 項目は
ADR-0003 で正典化。★ 完全自動投稿の前提として F-periodic-health-check
(緊急度 中、Phase A.5-3d 着手時、★ X1 引継ぎ「run 間分散統計」統合) が必要。

## 3. 直近の試運転結果サマリー

> ★ X1 (2026-05-31) の Task E 試運転は **Path A pure** (1 fresh batch + 1 run、本番状態維持、カズヤ判断) で
> 実施 = ingestion 1 回 + normalized mode 1 回。当初 5 batch 連続案は sample mode 分析未起動 / スタール枯渇 /
> GarbageFilter 48h / RSS 重複排除の blocker 4 連鎖で実行不可と判明、CP-2 で計画変更。

| 試運転 | バッチ | 動画化率 | 主要観察 |
|---|---|---|---|
| **2026-05-31** | **F-particular-angle-metadata-production-wire (X1)** | **1/3 動画化 + 1 article-only + 1 skipped (status=completed)** | ★ 新ルート本番配線後の Path A pure 試運転。ingestion `batch_id=20260531_102637` (47 sources / 1326 articles / $0 LLM) + normalized mode exit 0 / status=completed / run_llm=39 / day_publishes=2。Slot-1 cls-c8876d474612 = 新ルート稼働 ([ScriptWithAnalysis] Generated via gemini) / particular_angle_metadata 起動 (`stream_2_perspective_gap` + extraction_confidence=high) / sontaku.level=high・type=diplomatic (米国・イスラエル忖度の構造説明) / **target_enemy=None (退役確認)** / selected_pattern=Cultural Divide / used_fallback=false / retries=0 / char validation passed (hook=22, setup=75, twist=177, punchline=81) / max_tokens 4096 で JSON 切断ゼロ。Slot-2 cls-3e9544fee58f = article-only (TOP_N_VIDEOS_PER_RUN=1)。Slot-3 cls-c7d507fc74e8 = analysis_result=None で deprecation gate skip (1 件、analysis layer 失敗パス健在)。axis_5 カズヤ採点で「築900年の城→日本郵船→電気代」具体着地 + target_enemy 退役が質に表れたと評価、CP-3 = **W1 完全成功**。 |
| 2026-05-27 | F-gemini-quality-tier-poc | sample mode (1 video + 1 article、status=completed) | 最終布陣 v2 配線後の CP-2 試運転。script=gemini-3.5-flash + article=gemini-2.5-flash で retries=0 / fallback 0 / 404/Traceback/ERROR 0。target_enemy='大手メディア' を観測 = 旧ルート framing で X1 まで継続。 |
| 2026-05-26 | F-jp-coverage-cache-judgement-persist | 1/3 動画化 + 3 articles (status=completed) | cache 永続化後の 1 batch 試運転 (batch 20260526_035220)。 |
| 2026-05-25 | F-f1-locale-key-fix | 1/3 動画化 + 3 articles (status=completed) | locale key 修正後の 1 batch 試運転 (batch 20260525_085458)。 |
| 2026-05-19 | F-gemini-model-migrate-emergency | 1/3 動画化 + 3 articles (status=completed) | 5/25 shutdown 緊急対応の 1 batch 試運転 (batch 20260519_104204)。 |

## 4. Hydrangea コンセプト防衛機構の現状 (5 層)

> ★ X1 (2026-05-31) は新ルート `generate_script_with_analysis` を production default 起動したが、防衛機構
> ロジック (F-1〜F-13) は不変。各層の判定ロジック・閾値・bypass 条件は一切変更なし。X1 で追加された
> `particular_angle_metadata` + `sontaku_signals` は防衛機構の判定軸ではなく、script_writer 新ルートの
> 言い回し判断材料として LLM に渡される独立軸メタデータ (各論ルール強制せず LLM の知性に委ねる設計、
> クラウド誤り 9 回避)。

| 層 | バッチ | 場所 | 役割 | 状態 |
|---|---|---|---|---|
| F-1 | F-1 / F-1.5 / F-f1-locale-key-fix | EditorialMissionFilter | 編集ミッション適合度で score 算出 (>= 45.0 で通過) | ✅ 稼働中 |
| F-2 | F-2 / F-5 | FlagshipGate / EliteJudge | 海外発の重要ニュースを優先 | ✅ 稼働中 |
| F-13.B | … / F-jp-coverage-cache-judgement-persist | JpCoverageVerifier (WL 30 ドメイン階層判定 + LLM judgement 抽出 B-3' + llm_judgement cache 永続化) | JP 報道カバレッジを WL + LLM judgement で検証 | ✅ 稼働中 |
| F-5 | F-5 | FlagshipGate 下流救済 | 上流ガードを通過した候補の最終整合 | ✅ 稼働中 |
| F-13 (隠れ層) | F-13 / F-doc-cleanup | script_writer.py quality_floor_miss bypass | analysis_result 等が成立すれば appraisal の [抑制] を上書き | ✅ 稼働中。★ X1 で **新ルートが production default 起動** = analysis_result populated で新ルート (target_enemy=None) を直接呼ぶ経路が正常パス、F-13 隠れ層 bypass は legacy fallback 時の安全網に位置付け |

## 5. 触ってよい / 触ってはいけない領域マップ

### 触ってよい領域
- `configs/prompts/` 配下全般 (主戦場: `configs/prompts/analysis/geo_lens/`、★ X1 で `particular_angle_extract.md` 新規 + `script_with_analysis.md` 改修)
- `docs/` 配下全般 (★ `docs/ADR/` 配下に ADR 新規作成可)
- `tests/` 配下に新規テストファイル追加 (既存ファイルは原則変更しない、ただし API contract 整合化に伴うフィクスチャ更新 + 既存ファイルへの新規テストクラス追加 + 仕様/データ構造整合に伴う既存期待値修正 (構造変更なし) は許容、★ X1 で `tests/conftest.py` autouse fixture 新規 + `test_script_writer_with_analysis.py` に X1 contract 3 tests 追加)
- `scripts/` 配下に新規スクリプト追加
- `src/triage/` に新規ファイル追加
- `src/storage/db.py` (★ 不変原則対象外 = storage 層。後方互換必須)
- `src/generation/script_writer.py` の **新ルート**
  (`generate_script_with_analysis` / `ScriptWithAnalysisDraft` 等。★ X1 で `_build_script_with_analysis_prompt` に particular_angle_metadata + sontaku_signals プレースホルダ渡し追加、`generate_script_with_analysis` signature 不変)
- `src/generation/video_payload_writer.py` (不変原則 1-4 対象外、★ X1 で確認: target_enemy は L457-458 で条件付き露出 = 新ルート None なら非露出。`visual_goal` テンプレ L72 に「仮想敵」語彙残存 = F-video-payload-visual-prompt-target-enemy ★低)
- `src/shared/models.py` (★ X1 で SontakuSignals + ParticularAngleMetadata (nested) + AnalysisResult.particular_angle_metadata optional field 追加。後方互換必須)
- `src/main.py` (不変原則対象外、★ X1 で分析ブロック L3028 に `extract_for_scored_event` 呼出 + `model_copy(update={...})` で metadata 付与追加。run_analysis_layer 不変)
- `src/llm/factory.py` / `src/shared/config.py` の Gemini モデル ID default (★ F-gemini-quality-tier-poc / 2026-05-27 で最終布陣 v2 配線済)
- `src/analysis/` (★ X1 で不変原則 4 例外条件 5 点充足適用で `particular_angle_extractor.py` 新規作成、既存ファイル一切不変)
- `.env` / `.env.example` (リポジトリルート直下。★ `.env` は gitignored。★ X1 で `ANALYSIS_LAYER_ENABLED=false→true` (production default 化) + `ANALYSIS_LLM_MAX_TOKENS=2000→4096` (F-analysis-max-tokens-tune 統合))

### 触ってはいけない領域
- `src/generation/article_writer.py` (不変原則 1)
- `src/generation/script_writer.py` の **既存ルート**
  (`write_script` / `_PROMPT_TEMPLATE` / `_build_script_from_llm`) (不変原則 2)
  ★ **target_enemy のハードコード候補リスト (L113-118/317/445-446) はこの保護領域内
  = 直接修正不可。X1 では新ルート起動で旧ルートへの dispatch を回避することで target_enemy
  を production から退役させた (CP-3 = W1 成功)。legacy fallback 経路 (budget 枯渇 / no_client /
  llm_error) では依然として旧ルートに落ちる構造的限界が残る (X1 試運転では未到達)**
- `src/triage/` の既存ファイル (不変原則 3、★ 過去に例外条件適用済 = F-jp-coverage-improve / 2026-05-07 + F-f1-locale-key-fix / 2026-05-25 + F-jp-coverage-cache-judgement-persist / 2026-05-26)
- `src/analysis/` 配下の **既存ファイル** (不変原則 4、★ X1 で `particular_angle_extractor.py` 新規作成のみ例外条件 5 点充足適用、`analysis_engine.py` / `recency_guard.py` / `perspective_extractor.py` 等の既存ファイルは一切変更しない)
- 既存テスト (不変原則 5、baseline **1466 passed** 維持 — ただし
  フィクスチャの API contract 整合化 + 既存テストファイルへの新規テスト
  クラス追加 + 仕様/データ構造整合に伴う既存テスト期待値修正 (構造変更なし) は許容)

## 6. 不変原則 5 つ (リマインダ、正本: BATCH_PROTOCOL.md)

1. **`src/generation/article_writer.py` 一切変更不可**
2. **`src/generation/script_writer.py` の既存ルート (`write_script` /
   `_PROMPT_TEMPLATE` / `_build_script_from_llm`) は変更不可** ★ target_enemy
   ハードコード候補リストもこの保護領域内 (2026-05-26 調査で確定、X1 では新ルート起動で迂回)
3. **`src/triage/` の既存ファイル変更不可**。新規追加は OK。
   **例外条件** (5 点全充足で適用): 実装バグ修正 + 設計変更ではない +
   既存メソッド contract 完全維持 + baseline 維持 + カズヤ承認。
   ★ F-jp-coverage-improve (2026-05-07) / F-f1-locale-key-fix (2026-05-25) /
   F-jp-coverage-cache-judgement-persist (2026-05-26) で適用 (各 5 点全充足)。
4. **`src/analysis/` の既存ファイル変更不可**。**新規ファイル追加も原則禁止** (原則 3 と異なる、より厳格)。
   **例外条件** (5 点全充足で適用): バグ修正/機能追加が目的 + 既存メソッド完全維持 +
   データ追加のみ + baseline 維持 + カズヤ承認。
   ★ X1 (2026-05-31) で適用 = `src/analysis/particular_angle_extractor.py` 新規作成
   (F-script-writer-target-enemy-fix-investigate CP-1 で sanctioned 経路と確定、5 点全充足)。
5. **既存テスト破壊しない** (baseline **1466 passed**)

## 7. カズヤの直近フィードバック要点

- **「外部レビュー / 起案前事前情報も grep + コード精読で検証してから起案する」** (★ クラウド誤り 10、
  F-f1-locale-key-fix / F-jp-coverage-cache で 2 回発生 → F-script-writer-target-enemy (2026-05-26) +
  F-gemini-3.5-flash-api-audit (2026-05-27) で本作法が機能 → **★ X1 (2026-05-31) CP-1 で本作法
  により起案前提と実コードの 3 つの乖離を発見・訂正** (移植元は旧 3 分類版 + sontaku 不在、3 要素名称ズレ、
  dispatch 既配線) = grep-first 作法が機能した好例)。**ChatGPT Round 2 レビューでも誤り 10 系統が発生**
  (古い Project Knowledge 由来で解消済 2 件を「新規発見」と誤認) = 外部 AI レビューも grep 検証対象
  である根拠を本リポジトリで多数蓄積中。
- **「scaffolding は本番と違う人工状態を作るため不採用」** (★ X1 CP-2、2026-05-31) — 3 回処理に必要な
  recency guard 無効化 + archive 復元 + snapshot は本番状態を歪める。X1 試運転目的「本番状態での機械的
  安定性」と矛盾するため、Path A pure (1 fresh batch + 1 run、本番状態維持) を採用。run 間分散は
  FUTURE_WORK へ。
- **「1 バッチで欲張らない」+「設計判断と実装の分離」** (★ X1 起案 + CP-2 計画変更、Phase A.5-3b
  第一作着手前の段階分け) — title guard / 高リスク事実検証 / 第一作起案を別バッチに分離。
- **「対症療法じゃなく根本治療」** (★ F-script-writer-target-enemy → X1) — target_enemy は旧ルートの
  仮想敵 framing 哲学全体のマーカー。pinpoint 修正でなく新ルート配線 (X1) で根本治療。
- **「LLM の知性に委ねる前に構造データの正しさを担保する」** (F-f1-locale-key-fix) /
  **「言い回しを個別ルールで指定するのは避けたい」** (クラウド誤り 9) — ★ X1 でも遵守: extractor プロンプト
  + script_with_analysis.md のいずれも各論ルールを足さず、メタデータ構造を LLM に渡して自律選択させる
  設計に統一。
- **「整合の説明であって検証ではない」/ Project Knowledge・事前情報を鵜呑みにしない**
  (クラウド誤り 10) — ★ X1 CP-1 で 3 つの起案前提を grep で検証・訂正。
- **「将来に負債を残さない」** — ★ X1 で新ルート未配線負債 (5 月初旬の docs 概念整理と production の乖離)
  を解消。残存負債 (verify_two_stage 配線 / F-video-payload visual prompt 旧語彙 / legacy fallback 経路の
  target_enemy 復活構造) は FUTURE_WORK に明示登録。
- **「動くものを壊さない」+「あるべき姿で進める」** — ★ X1 で旧ルート完全不変 (不変原則 2 厳守)、
  新ルート起動で正しい姿に到達。
- **「機械判定は事実の代替ではない」** — 候補A perspective_gap 確定は機械不在で覆らない。
- **「中間が良い」/「考え方で制御」/「LLM の知性に委ねる」** — no_match のみ尊重 (B-3') + X1 でも踏襲。
- **「Hydrangea のメディアとしてのリスクは嘘をつくこと」** — 疑わしきは低く見積もる。★ X1 trial で
  article 内の高リスク数字・引用が production 未検証と判明 = 1-T (高リスク事実検証) の必須化を実証。
- **「観点の選択的欠落 = 忖度」** — 第一作 (候補A perspective_gap) を確定。X1 trial Slot-1 でも
  sontaku.level=high/diplomatic を抽出、米国・イスラエル忖度の構造説明を生成。
- **「負の遺産残さないように」/「カズヤの手作業はバッチプロンプトのコピペ 1 回のみ」/「過剰拡張性の罠」**

## 8. 関連ドキュメントへの導線

- 過去の決定の経緯 → `docs/DECISION_LOG.md`
- 残課題リスト → `docs/FUTURE_WORK.md`
- 議論中の未確定メモ → `docs/DISCUSSION_NOTES.md`
- バッチ運用ルール → `docs/BATCH_PROTOCOL.md`
- アーキテクチャ全体像 → `docs/ARCHITECTURE.md`
- 技術的負債リスト → `docs/TECH_DEBT.md`
- 編集ミッションフィルタ設計 (F-13 隠れ層含む) → `docs/EDITORIAL_MISSION_FILTER_DESIGN.md`
- ★ 「特定角度」概念正典 → `docs/PARTICULAR_ANGLE_DEFINITION.md`
- Claude Code 振る舞い指針 → `CLAUDE.md`
- ★ **X1 = F-particular-angle-metadata-production-wire REPORT + 試運転証跡** → `docs/runs/F-particular-angle-metadata-production-wire/REPORT.md` + `analysis_result_current.json` + `extractor_migration_design.json` + `script_writer_new_route.json` + `main_dispatch_point.json` + `jp_coverage_analysis_impact.json` + `side_effects_investigation.json` + `ingestion_investigation.json` + `trial_run_aggregated.json` + `environment_snapshot.json` + `trial_outputs/fresh_run/*` (Slot-1 script/article/analysis snapshot)
- F-gemini-quality-tier-poc REPORT → `docs/runs/F-gemini-quality-tier-poc/REPORT.md`
- F-docs-update-chatgpt-round2-and-error10 REPORT → `docs/runs/F-docs-update-chatgpt-round2-and-error10/REPORT.md`
- F-gemini-3.5-flash-api-audit REPORT → `docs/runs/F-gemini-3.5-flash-api-audit/REPORT.md`
- F-script-writer-target-enemy-fix-investigate REPORT → `docs/runs/F-script-writer-target-enemy-fix-investigate/REPORT.md`
- F-gemini-model-migrate-emergency REPORT → `docs/runs/F-gemini-model-migrate-emergency/REPORT.md`
- ★ **Phase A.5-3b 画像戦略 / Remotion / モラル ADR** → `docs/ADR/0001-image-strategy.md` + `0002-remotion-mvp-scope.md` + `0003-content-moral-guidelines.md`

---

*このドキュメントは F-state-protocol (2026-05-01) で導入。Claude Code が
バッチ完了時に全置換更新する運用 (BATCH_PROTOCOL.md Task 5)。
F-particular-angle-metadata-production-wire (X1 / 2026-05-31) は **ゲート完了後の 22 つ目のバッチ (1-R)**、**実装バッチ**。
`docs/PARTICULAR_ANGLE_DEFINITION.md` セクション 3.6-3.7 で正典化された `ParticularAngleMetadata` (3 要素 +
nested `SontakuSignals`) を Hydrangea production に配線、新ルート `generate_script_with_analysis` を
production default 起動 (ANALYSIS_LAYER_ENABLED=true)。**target_enemy framing が production から自動退役**
(Slot-1 試運転で target_enemy=None 確認、axis_5 カズヤ採点で「城→海運→電気代」具体着地評価)。不変原則 4
例外条件 5 点充足適用で `src/analysis/particular_angle_extractor.py` 新規作成 (単一パス α、3 要素 + 4 分類 +
sontaku を 1 LLM call で抽出、get_analysis_llm_client 経由)。CP-1 でクラウド誤り 10 系統の grep 作法により
起案前提と実コードの 3 つの乖離発見・訂正。CP-2 で Path A pure (1 fresh batch + 1 run、本番状態維持) に
計画変更。F-analysis-max-tokens-tune 統合 (ANALYSIS_LLM_MAX_TOKENS=4096)。baseline 1432→1466 passed
(新規 +34、破壊ゼロ)。6 後続バッチ向け引継ぎ事項 (高リスク事実検証必須化 / punchline 尻切れ / title guard
本番実証 / 視覚プロンプト旧語彙 / run 間分散 / 試運転データ確保) を FUTURE_WORK / DISCUSSION_NOTES に
確定。次バッチ最有力 = 1-Q.5 F-title-guard-coverage-claim-policy (第一作着手前必須、X1 trial で本番再現実証)。
過去の経緯は DECISION_LOG.md / FUTURE_WORK.md / DISCUSSION_NOTES.md を参照。*
