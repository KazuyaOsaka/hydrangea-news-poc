# Hydrangea — Current State (CURRENT_STATE.md)

最終更新: 2026-05-27 (★ F-gemini-quality-tier-poc 完了、Phase A.5-3a-verify ゲート完了後の **21 つ目のバッチ (1-Q)**、**実装バッチ**。ChatGPT/Gemini セカンドオピニオン 2 ラウンド + Claude Web 裁定 + 公式 pricing 確認後の **最終布陣 v2** を配線。**配線結果**: QUALITY (judge/script/analysis、`get_judge`/`get_script`/`get_analysis`) = **gemini-3.5-flash** primary / MAX=2; ARTICLE (article、★ role 新設分離、article_writer.py 不変) = **gemini-2.5-flash** primary / MAX=1 (output $9.00→$2.50); LIGHTWEIGHT (garbage/merge_batch) = **gemini-3.1-flash-lite** primary / MAX=1 (★ migrate-emergency CP-1 保留分の切替採用); **`JUDGE_MODEL=gemini-3.5-flash` 明示追加** (未指定だと judge primary が 2.5-flash に落ちる prepend 機構を grep で発見); **Gemini 3 系 temperature ガード** (analysis primary が 3 系なら temperature 非送出、公式 default 1.0 推奨)。★ **CP-1 で「最終布陣 v2 (10 role)」を grep 検証 → 実コードは 4 実 role (merge_batch/judge/generation/analysis) でしか dispatch しないと判明** (viral_filter/title は LLM stage 不在、editorial_mission_filter は judge 共用で 3.5-flash/MAX2 のまま許容 = deviation、article は role 分離で 2.5-flash 実現)。公式 pricing/API 仕様を **web_fetch (一次ソース) で全項目裏取り** → 起案値と全一致で **CP-0 スキップ**。CP-2 試運転 (カズヤ「今すぐ run」) = exit 0/status=completed/script=3.5-flash+article=2.5-flash で retries=0/fallback 0/404・Traceback・ERROR 0、target_enemy='大手メディア' は旧ルート framing で X1 まで継続。実 tier 解決は `model_roles_resolution.json` で paid generation なしに決定的確認 (lineup v2 一致)。★★ **クラウド誤り 10 派生「外部 AI セカンドオピニオンの権威化」を CLAUDE.md + DISCUSSION_NOTES に正本化** (Gemini 価格誤情報 + Claude Web 廃止短絡 + ChatGPT 訂正の経緯)。Q2=揃える で config.py/factory.py inline default 不一致 (既知 doc-drift) も解消。baseline **1417 → 1432 passed** (新規 15、破壊ゼロ)。変更 = `src/llm/factory.py` / `src/shared/config.py` / `.env`(gitignored) / `.env.example` / `tests/` 新規 2 + 既存 1 整合 (構造不変)、`src/llm/model_registry.py` は確認のみ。不変原則 1-5 完全遵守 (article_writer.py / script_writer.py 既存ルート / triage 既存 / analysis 不変)。新規 follow-up = editorial_mission_filter 独立分離 ★低 / run_summary model_roles 忠実化 ★低。次バッチ最有力 = X1 (新ルート本番配線、target_enemy 解消統合) → F-title-guard-coverage-claim-policy (第一作着手前必須) → Phase A.5-3b 第一作起案)

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
台本表現の方向性も `docs/PARTICULAR_ANGLE_DEFINITION.md` セクション 3.7 で
正典化 (particular_angle_metadata + sontaku_signals 構造を script_writer.py
新ルートに渡し、LLM が系統別の言い回しを自律選択)。

★ 2026-05-08 (F-particular-angle-redesign-extension) で **系統名 1/1.5/2 →
1/2/3** にリネーム + sontaku_signals 別軸メタデータ独立化 + MECE 判別基準
明示 + クラウド誤り 9 (各論コントロールの誘惑) を CLAUDE.md / DISCUSSION_NOTES
に記録。

★ 2026-05-09 (F-jp-coverage-tune-followup) で `_match_whitelist` を
**ドメイン階層判定** に置換 + `JP_MEDIA_WHITELIST` 30 ドメイン化。Step C
再測定: F1 covered 0.8718 (threshold 0.85 初突破)。

★★★ 2026-05-16 (F-jp-coverage-llm-judgement-extraction) で **LLM judgement
bypass 問題を Option (i) で根本治療完了**。`_parse_llm_judgement` 新規 +
B-3' 表。LLM の **明示的否定 (no_match)** のみ尊重し **沈黙 (uncertain)** を
否定と読み替えない。

★★★ 2026-05-19 (F-trial-run-candidate-a-reverify) で **B-3' 改修の構造的
効果を 3 連続試運転で確定**。候補A は perspective_gap framing で維持。

★★★ 2026-05-19 (F-gemini-model-migrate-emergency) で **5/25 shutdown 緊急
対応を実装完了**。両系統 Tier3 + factory/config default + `.env` を
`gemini-3.1-flash-lite` (GA) に一括置換、shutdown モデル ID を Tier 階層から
構造除去で 404 即 raise リスク根絶 (retry.py 0 行変更)。

★★ 2026-05-25 (F-f1-locale-key-fix) で **F-1 EditorialMissionFilter の
locale key bug を根本治療**。`_editorial_mission_prescore` の
`sources_by_locale.get("jp"/"en")` を `"japan"` + 非 japan 合算に修正
(機能ロジック不変)。クラウド初期想定 (false positive) を grep で訂正 (実態 =
中間解像度喪失 = false negative 方向) → クラウド誤り 10 記録。

★ 2026-05-26 (F-jp-coverage-cache-judgement-persist) で **F-13.B の
llm_judgement / llm_judgement_text を 24h cache に永続化** (案 A、DB schema 2 列 +
idempotent migration + verifier の save/get 拡張、判定ロジック不変)。cache hit 時
も B-3' 判定値 + 判定根拠テキストが忠実復元 (試運転で実証)。★ プロンプト記載の
「Recall 劣化リスク」「監査不能化」を grep + 実測で訂正 → クラウド誤り 10 の 2 回目発生記録。

★ 2026-05-26 (F-script-writer-target-enemy-fix-investigate) で **Gemini Round 1
独自指摘の `target_enemy` 不整合問題を調査専用バッチで実態確認**。真因 a 確定 =
production 稼働中の旧ルート `write_script` が仮想敵 framing を viewer-facing に
出力するが不変原則 2 で修正不可、新ルートは設計上既に排除済み = **新ルート配線
(X1) が唯一の解消経路**。起案前仮説 1-5 が grep で概ね CONFIRMED = クラウド誤り
10 の 3 回目発生なし。改修なし、baseline 1417 維持。

★ 2026-05-27 (F-gemini-3.5-flash-api-audit) で **Gemini 3.5 Flash (Stable) の
API 破壊的変更の影響範囲を調査専用バッチで実態確認**。真因 b 確定 = 事前情報の
4 破壊的変更候補 + structured outputs はいずれも Hydrangea 本番パスに該当箇所
ほぼゼロ (top_p/top_k/thinking_budget/thinking_level/カスタム function calling/
response_schema = 全て 0 件)。構造的理由 = Tier ベース解決 + free-text JSON
パース + Grounding 限定 tools。**migration 不要**、CP-1 = Y1 (quality-tier-poc
に直進)。起案前事前情報を grep で検証する作法が機能 (クラウド誤り 10 系統の検証)。
改修なし、baseline 1417 維持。

★ 2026-05-27 (F-docs-update-chatgpt-round2-and-error10、docs-only) で **ChatGPT
Round 2 レビュー (7 指摘) を docs 正本と grep 裏取り照合**。指摘 3/4 = 解消済確認
(古い Project Knowledge 由来 = ★ ChatGPT 側でもクラウド誤り 10 系統発生)、指摘 2/6/7
= 新規 3 タスク化 (F-title-guard-coverage-claim-policy 高 / F-analysis-max-tokens-tune
中 / F-job-record-av-path 低)、指摘 5 = F-periodic-health-check スコープ拡張。★★
**クラウド誤り 10 を CLAUDE.md に明文化** (外部 AI レビューも grep 検証対象である根拠)。
改修なし、baseline 1417 維持。

### 系統 1 (silence_gap): 完全な情報空白 — 広範事件も特定角度も日本主要メディアで未報道

完全な情報空白で、Hydrangea コアミッションど真ん中。台本表現は「日本では報じられ
なかった」が成立する。25 件アノテーション最終分類で 4 件 (16%)。

**「構造的に」が核心**: 忖度 / 報道規制 / 報道の自由度の低さによって黙殺されて
いる事象を対象とする。4 軸の構造的バイアスのいずれかに該当。

> 忖度、報道規制、報道の自由度の低さをぶち壊そう。(2026-05-04 カズヤのメディア宣言)

### 系統 2 (perspective_gap、F-particular-angle-redesign で新設): 観点不足 — 広範事件は報道済み、特定角度は未報道

事件本体は日本でも取り上げられたが、海外メディアが独自に掘った構造分析角度は
深掘りされていない。台本表現は「日本でも事件は取り上げられたが、◯◯という構造に
は触れられていない」。25 件最終分類で **20 件 (80%)**。

★★★ Phase A.5-3b 第一作 (候補A cls-6889e9e1c7ac) は本系統の framing で起案する
(2026-05-16 確定、2026-05-19 F-trial-run-candidate-a-reverify で **最終確定**)。

### 系統 3 (framing_inversion): 報道差の背景解説 — 特定角度も報道済み + 解釈差 + 忖度シグナル

広範事件 + 特定角度も日本主要メディアで報道済み + 評価フレーム対立 +
sontaku_signals.level=high/medium の 3 条件。25 件最終分類で **0 件** ★ 想定外
(根本治療は Phase A.5-3b 第二作のサンプル拡充)。

### ★ docs 概念整理と production-pipeline の乖離 (2026-05-11 観察、2026-05-27 で再確認で不変)

Phase A.5-3a-verify ゲート完了後の連続バッチで概念整理が docs 上で進んだが、
**production-pipeline 上では未配線**:
- `src/main.py` は legacy `verify()` (broad-only) のみ呼び出し
- `verify_two_stage()` 系統 1/2/3 機械判別: 本番未配線 (計測専用)
- `particular_angle_metadata` / `sontaku_signals`: src/ 配下 grep で 0 件
- `generate_script_with_analysis` 新ルート: 未起動 (`ANALYSIS_LAYER_ENABLED=false`
  default + `analysis_result=null` → `main.py:2019` else 分岐で旧ルート稼働)

★★ **2026-05-26 (F-script-writer-target-enemy-fix-investigate) 再確認**: 上記乖離は
不変。旧ルートの target_enemy (仮想敵 framing) が production で viewer-facing に
出力され続けている = 新ルート配線の遅延が品質負債として累積。X1 (新ルート本番配線)
で target_enemy 含む旧ルートの煽り framing が一括退役する。本番配線判断バッチ群は
引き続き FUTURE_WORK 緊急度 高に並走待機。

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

- **main HEAD コミット**: `112539d` (Merge branch 'feature/F-docs-update-chatgpt-round2-and-error10')。F-gemini-quality-tier-poc は feature ブランチ `feature/F-gemini-quality-tier-poc` で Task A-G 完了、本完了レポート提示後にカズヤ承認 → commit/merge 実行 (Task G)。★ 本バッチは実装バッチ (factory.py / config.py / .env(.example) / tests 改修)
- **直近 5 件のログ (main、Task G merge 前)**:
  ```
  112539d Merge branch 'feature/F-docs-update-chatgpt-round2-and-error10'
  41f09d6 docs: F-docs-update-chatgpt-round2-and-error10 ChatGPT Round 2 レビュー由来の新規 3 タスク
  2f99ebd Merge branch 'feature/F-gemini-3.5-flash-api-audit'
  de06887 investigate: F-gemini-3.5-flash-api-audit Gemini 3.5 Flash API 影響範囲調査 (調査専用)
  07dc175 Merge branch 'feature/F-script-writer-target-enemy-fix-investigate'
  ```
- **baseline テスト数**: **1432 passed** (★ F-gemini-quality-tier-poc = baseline 1417 + 新規 15 [test_factory_role_model_resolution.py 8 + test_factory_gemini3_temperature.py 4 + test_factory_role_tier_separation.py +3 net]。Task A で baseline 1417 passed 確認済 = 115.43s、Task D 後 1432 passed = 76.47s)
- **DB schema 変更**: なし (本バッチは LLM 階層配線のみ。F-jp-coverage-cache-judgement-persist で `jp_coverage_cache` に `llm_judgement` / `llm_judgement_text` 追加 + idempotent migration 適用済)

## 2. 現在のフェーズ

- **Phase**: Phase A.5-3a-verify **完了** (2026-05-07、ゲート完了後 21 バッチ目が本バッチ)
- **進行中バッチ**: なし (F-gemini-quality-tier-poc 完了直後、Task G 完了レポート提示 → カズヤ承認待ち → commit/merge Task G)
- **次バッチ候補と推奨** (★ F-gemini-quality-tier-poc / 2026-05-27 更新):
  - ~~**F-gemini-quality-tier-poc (1-Q)**~~ ✅ **完了 (2026-05-27)**。最終布陣 v2 配線 (QUALITY=gemini-3.5-flash / ARTICLE=gemini-2.5-flash 分離 / LIGHTWEIGHT=gemini-3.1-flash-lite + JUDGE_MODEL 明示 + Gemini 3 系 temperature ガード)。axis_5 採点はカズヤ手動 (第一作着手前)。
  - **1st: X1 = particular_angle_metadata + sontaku_signals の本番配線判断** ★★★高 (★ F-script-writer-target-enemy CP-1 で target_enemy 解消を統合)。新ルート `generate_script_with_analysis` を本番起動し、`ParticularAngleMetadata` / `SontakuSignals` を AnalysisResult に組込んで script_writer 新ルートに渡す。**新ルート起動で target_enemy 含む旧ルートの仮想敵/煽り framing が production から自動退役**。★ Editorial Guardian (gemini-3.1-pro-preview) 配線は本 X1 では行わず後続 (高リスク事実検証ワークフロー)。verify_two_stage 本番配線判断 + F-stream-2-filter-design と密接に関連。工数 8-16h
  - **1.5th (★ 第一作着手前必須): F-title-guard-coverage-claim-policy** ★★高 (ChatGPT Round 2 / 2026-05-27 起案)。title_generator.py の `is_strong` ゲートが `perspective_gap_score >= 3` でも真になり、系統 2 (perspective_gap = 候補A) の事象に silence_gap 絶対表現「日本では報道されない」「日本で無報道」(L136/149/203/380/394) が出力され得る。`manual_poc/` 配下の coverage_claim_policy 構造データ (allowed_claim_level / forbidden_title_claims) + 生成後 title_layer_guard で虚偽防止 (各論プロンプト制御でなく構造データ = クラウド誤り 9 回避)。3-5h
  - **2nd: Phase A.5-3b 第一作起案** ★ (緊急度 高、確定モデル [QUALITY=gemini-3.5-flash / article=gemini-2.5-flash] で実装。候補A cls-6889e9e1c7ac 手動 event 固定 + 実台本生成 + perspective_gap framing + axis_5 採点)
  - **4th: F-evidence-jp-coverage-audit-trail** ★中 (F-jp-coverage-cache-judgement-persist で分離、案 B 単独)。score_breakdown["jp_coverage_verification"] に has_jp_coverage/matched_domains/matched_tier/llm_judgement を積み evidence.json 証跡化 (evidence_writer 不変)。cache lossless 化が前提として整済。新機能のため緊急度 中
  - **5th: F-grounding-determinism-audit** ★ (緊急度 中、broad Grounding API の WL ドメイン返却率 run 間分散の集約戦略検討)
  - **6th: 第一作公開前の高リスク事実検証ワークフロー** ★ (緊急度 中、ADR-0003 由来、Phase A.5-3b と並走。★ Editorial Guardian = gemini-3.1-pro RPD 250 の配線判断はここで実施)
  - **7th: F-periodic-health-check** ★ (緊急度 中、Phase A.5-3d 着手時、cron 完全自動投稿の前提。★ ChatGPT Round 2 指摘 5 で **tier fallback / retry 観測強化スコープを統合** = どの Tier が何回落ちたかの runtime snapshot)
  - **7.5th: F-analysis-max-tokens-tune** ★中 (ChatGPT Round 2 / 2026-05-27 起案)。factory.py:516 default 2000 → 4096 推奨。Phase A.5-3b 実行時 env 指定 (改修なし) → X1 配線時 default 化判断
  - **8th: 本番配線判断バッチ群 (X1 に内包しない残分、並走可)**: verify_two_stage 本番配線 / F-stream-2-filter-design 責務範囲再評価
  - **9th: 低優先整合タスク群** ★低 (いずれも runtime 影響なし): ~~config.py/factory.py default 不一致整合~~ ✅ **完了 (F-gemini-quality-tier-poc / Q2=揃える)** / **editorial_mission_filter 独立分離** (F-gemini-quality-tier-poc CP-1 deviation 由来、2.5-flash/MAX1 化は main.py 改修要) / **run_summary model_roles 忠実化** (F-gemini-quality-tier-poc CP-2 発見、F-periodic-health-check 統合候補) / locale key 定数一元化 (選択肢 3) / scripts/verify_jp_coverage_measure.py inline schema doc-drift 解消 / **F-job-record-av-path** (ChatGPT Round 2 指摘 7、Phase A.5-3c DB schema 整理に統合)
- **推奨フロー**:
  - commit/merge (本完了レポート提示 → カズヤ承認後)
    → **X1 (particular_angle_metadata + sontaku_signals 本番配線、target_enemy 解消統合、最優先)**
    → F-title-guard-coverage-claim-policy (第一作着手前必須)
    → Phase A.5-3b 第一作起案 (確定モデル [QUALITY=gemini-3.5-flash / article=gemini-2.5-flash] で実装、候補A perspective_gap framing + axis_5 採点)
    → 並走: F-evidence-jp-coverage-audit-trail + F-grounding-determinism-audit + 高リスク事実検証ワークフロー (Editorial Guardian 配線) + 本番配線残分
- **★ Phase A.5-3b 第一作着手前の追加確認事項** (カズヤ指示、2026-05-27 更新):
  1. ~~F-trial-run-candidate-a-reverify~~ ✅ **完了 (2026-05-19、前提最終確定、候補A perspective_gap 維持)**
  2. ~~F-image-prompt-spec スコープ再定義~~ ✅ **完了 (2026-05-18、ADR 3 件 + schema 設計)**
  3. ~~F-gemini-model-migrate-emergency~~ ✅ **完了 (2026-05-19)** + ~~F-gemini-3.5-flash-api-audit~~ ✅ **完了 (2026-05-27、API 破壊的変更なし確定 = 真因 b)** + ~~F-gemini-quality-tier-poc~~ ✅ **完了 (2026-05-27、最終布陣 v2 配線 = QUALITY/script/judge/analysis gemini-3.5-flash + article gemini-2.5-flash 分離 + LIGHTWEIGHT gemini-3.1-flash-lite。axis_5 採点はカズヤ手動)**
  4. ★ **F-title-guard-coverage-claim-policy** (ChatGPT Round 2 / 2026-05-27 起案、★★高、第一作着手前必須)。perspective_gap (候補A) に silence_gap 絶対表現が出力されるリスクを coverage_claim_policy 構造データ + 生成後 guard で防止。3-5h
  5. ★ **F-analysis-max-tokens-tune** (ChatGPT Round 2 / 2026-05-27 起案、★中)。第一作実行時に env `ANALYSIS_LLM_MAX_TOKENS=4096` 指定 (改修なし、JSON 途中切断回避)
  6. ElevenLabs 声選定 (着手前 30 分作業、既存登録済み、カズヤ手作業)
  7. Remotion セットアップ (第一作で Claude Code に書かせる、Node 環境カズヤ手動準備、ADR-0002 D-minimal)

### Phase A.5-3a-verify ロードマップ (★ F-gemini-quality-tier-poc / 2026-05-27 更新版)

**ゲート完了**: 1-A〜1-D''' 全段階完了で Phase A.5-3a-verify ゲート完了 (2026-05-07)。
本バッチはゲート完了後の **21 つ目のバッチ**。

| 段階 | バッチ | 状態 | 概要 |
|---|---|---|---|
| 1-A〜1-K | (F-verify-jp-coverage-golden 〜 F-image-prompt-spec) | ✅ 完了 | ゲート完了 + 特定角度正典化 + LLM judgement bypass 根本治療 + 候補A 前提確定 + ADR 3 件 |
| 1-L | F-gemini-model-audit | ✅ 完了 (2026-05-19) | Gemini モデル戦略 影響調査。5/25 shutdown 対象 2 箇所 + 404 即 raise 重大発見 |
| 1-M | F-gemini-model-migrate-emergency | ✅ 完了 (2026-05-19) | 両系統 Tier3 + default + `.env` を gemini-3.1-flash-lite (GA) 一括置換、404 即 raise リスク根絶。baseline 1417 維持 |
| 1-N | F-f1-locale-key-fix | ✅ 完了 (2026-05-25) | 3 AI 三角測量由来で F-1 locale key bug 根本治療、機能ロジック不変。クラウド誤り 10 記録。baseline 1417 維持 |
| 1-O | F-jp-coverage-cache-judgement-persist | ✅ 完了 (2026-05-26) | 3 AI 三角測量由来で F-13.B の llm_judgement cache 永続化欠落を案 A で根本治療、判定ロジック不変。CP-1 = 実害訂正 + クラウド誤り 10 の 2 回目発生記録。baseline 1417 維持 |
| 1-P | F-script-writer-target-enemy-fix-investigate | ✅ 完了 (2026-05-26、調査専用) | Gemini Round 1 独自指摘の target_enemy 不整合問題を調査専用 (改修なし) で実態確認。真因 a 確定 (旧ルート稼働 + 不変原則 2 で修正不可、新ルートは設計上排除済み)。CP-1 = X1 (新ルート配線統合)。クラウド誤り 10 の 3 回目発生なし。baseline 1417 維持、src/ 0 行変更 |
| **1-P.5** | **F-gemini-3.5-flash-api-audit** | ✅ **完了 (2026-05-27、調査専用)** | **ゲート完了後 19 つ目**。Gemini 3.5 Flash (Stable) の API 破壊的変更の影響範囲を調査専用 (改修なし) で実態確認。**真因 b 確定 (破壊的変更は無いか軽微)** = top_p/top_k/thinking/カスタム function calling/response_schema 全て 0 件、本番生成系は generation_config=None。CP-1 = Y1 (quality-tier-poc に直進、migration 不要)。候補リスト = 3.5 Flash 追加 + 3 Flash Preview 削除。★ 起案前事前情報を grep で検証する作法が機能 (クラウド誤り 10 系統の検証)。baseline 1417 維持、src/ 0 行変更 |
| **1-P.6** | **F-docs-update-chatgpt-round2-and-error10** | ✅ **完了 (2026-05-27、docs-only)** | **ゲート完了後 20 つ目**。ChatGPT Round 2 レビュー (7 指摘) を docs 正本と grep 裏取り照合。指摘 3/4 = 解消済確認 (古い Project Knowledge = ★ ChatGPT 側でもクラウド誤り 10 系統発生)、指摘 2/6/7 = 新規 3 タスク (F-title-guard-coverage-claim-policy 高 / F-analysis-max-tokens-tune 中 / F-job-record-av-path 低)、指摘 5 = F-periodic-health-check スコープ拡張、指摘 1 = 既登録。★★ クラウド誤り 10 を CLAUDE.md に明文化 (外部 AI レビューも grep 検証対象)。baseline 1417 維持、src/ tests/ configs/ scripts/ .env 0 行変更 |
| **1-Q** | **F-gemini-quality-tier-poc** | ✅ **完了 (2026-05-27、実装)** | **ゲート完了後 21 つ目**。最終布陣 v2 配線: QUALITY (judge/script/analysis) = gemini-3.5-flash/MAX2、ARTICLE (article、role 新設分離) = gemini-2.5-flash/MAX1、LIGHTWEIGHT (garbage/merge) = gemini-3.1-flash-lite/MAX1 + JUDGE_MODEL 明示 + Gemini 3 系 temperature ガード。★ CP-1 で lineup v2 (10 role) を grep 検証 → 実 dispatch 4 role のみ判明 (viral_filter/title は LLM stage 不在、editorial_mission_filter は judge 共用で deviation 許容)。公式 pricing/API を web_fetch で全裏取り (CP-0 スキップ)。CP-2 試運転 exit 0/script=3.5-flash+article=2.5-flash。クラウド誤り 10 派生「外部 AI 権威化」CLAUDE.md 明文化。baseline 1417→1432 passed |
| 1-Q.5 | F-title-guard-coverage-claim-policy | ★★高 (第一作着手前必須) | perspective_gap に silence_gap 絶対表現が出力されるリスクを coverage_claim_policy 構造データ + 生成後 guard で防止 (ChatGPT Round 2 指摘 2) |
| 1-R | X1 = particular_angle_metadata + sontaku_signals 本番配線 (target_enemy 解消統合) | ★★★高 (次バッチ最有力) | 新ルート本番起動 → 旧ルートの target_enemy/煽り framing 退役 (★ Editorial Guardian gemini-3.1-pro-preview 配線は後続) |
| 1-S | Phase A.5-3b 第一作起案 | ★ 緊急度 高 (確定モデルで実装) | 候補A 手動固定 + perspective_gap framing + axis_5 採点 |
| 1-T | F-evidence-jp-coverage-audit-trail / F-grounding-determinism-audit / 高リスク事実検証 (Editorial Guardian 配線) / 本番配線残分 | ★ 並走候補 | evidence 監査トレース新設 / broad Grounding 分散集約 / gemini-3.1-pro 配線 / verify_two_stage 配線 |

### Phase A.5-3d 投稿対象の補足

Phase A.5-3d で本番リリースする対象は **geo_lens (政治・経済) のみ**。
投稿先は TikTok と YouTube Shorts の両方同時、完全自動投稿 (cron 6 時間おき、
人手介入ゼロ、投稿前ゲートで品質保証)。★ 投稿前ゲートのチェックリスト 6 項目は
ADR-0003 で正典化。★ 完全自動投稿の前提として F-periodic-health-check
(緊急度 中、Phase A.5-3d 着手時) が必要。

## 3. 直近の試運転結果サマリー

> ★ F-gemini-quality-tier-poc (2026-05-27) の CP-2 試運転は **sample mode** (5 events, top-1) で
> 実施 = run_llm 2 (article + script のみ)。run_summary.json は sample mode では新規生成されないため、
> 実 tier 解決は `docs/runs/F-gemini-quality-tier-poc/model_roles_resolution.json` で paid generation
> なしに決定的確認 (lineup v2 一致)。★ run_summary.model_roles label は config role 定数を読む機構で
> 実 tier 解決と部分乖離 (merge_batch label=2.5-flash vs 実 tier1=3.1-flash-lite) = 監査忠実化は
> follow-up (F-periodic-health-check 統合候補)。

| 試運転 | バッチ | 動画化率 | 主要観察 |
|---|---|---|---|
| **2026-05-27** | **F-gemini-quality-tier-poc** | **sample mode (1 video + 1 article, status=completed)** | ★ 最終布陣 v2 配線後の CP-2 試運転 (job 5ce761f7)。exit 0 / status=completed。**script=gemini-3.5-flash + article=gemini-2.5-flash** で retries=0 / fallback 0 / 404・503・Traceback・ERROR・WARNING 0 (出力 32 行全走査)。target_enemy='大手メディア' (Media Critique) を観測 = 旧ルート framing で X1 まで継続 (起案どおり)。sample mode は run_summary.json 非生成 = 実 tier は model_roles_resolution.json で決定的確認。 |
| 2026-05-26 | F-jp-coverage-cache-judgement-persist | 1/3 動画化 + 3 articles (status=completed) | ★ cache 永続化後の 1 batch 試運転 (batch 20260526_035220)。exit 0 / status=completed / 3 slots published。script via gemini (not fallback)、retries=0、404/Traceback/ERROR 0 件。★★ run_llm_calls=41 (model_roles label: generation=gemini-3-flash-preview / judge=gemini-2.5-flash / merge_batch=gemini-2.5-flash = 旧布陣)。F-script-writer-target-enemy で Slot-1 cls-0741c099c775 の target_enemy=米国政府 + 煽り表現を観察。 |
| 2026-05-25 | F-f1-locale-key-fix | 1/3 動画化 + 3 articles (status=completed) | ★ locale key 修正後の 1 batch 試運転 (batch 20260525_085458)。exit 0 / status=completed / 3 slots published。used_fallback=false、retries=0、404/Traceback 0。blindspot 中間段階の復活を before_after_prescore.json で決定的確認。 |
| 2026-05-19 | F-gemini-model-migrate-emergency | 1/3 動画化 + 3 articles (status=completed) | ★ 5/25 shutdown 緊急対応の 1 batch 試運転 (batch 20260519_104204)。model_roles 全 GA 解決。used_fallback=false、404・shutdown モデル参照 0 件。 |
| 2026-05-18 | F-trial-run-candidate-a-reverify | 1/3 動画化 (Slot-1 cls-f47e9ffde77d, ★ fallback script) + 3 articles | ★ 候補A cls-6889e9e1c7ac 不在。has_jp True 比率 3 連続単調減少。防衛機構 5 層全機能。 |
| 2026-05-16 | F-trial-run-post-llm-extraction | 1/3 動画化 (Slot-1 cls-e2429c77f48e) + 3 articles | ★★★ B-3' が production verify() に配線・本番で安全装置初発火。第一作題材確定 = 候補A perspective_gap。 |

## 4. Hydrangea コンセプト防衛機構の現状 (5 層)

> ★ F-gemini-quality-tier-poc (2026-05-27) は LLM 呼び出し基盤 (factory.py Tier 階層 / config.py
> モデル ID default / .env) のモデル布陣を最終布陣 v2 に切替えたが、防衛機構ロジック (F-1〜F-13) は
> 不変。各層が使う LLM client (judge / analysis / merge_batch / generation) の解決先モデルが変わった
> だけで、判定ロジック・閾値・bypass 条件は一切変更なし。

| 層 | バッチ | 場所 | 役割 | 状態 |
|---|---|---|---|---|
| F-1 | F-1 / F-1.5 / F-f1-locale-key-fix | EditorialMissionFilter | 編集ミッション適合度で score 算出 (>= 45.0 で通過) | ✅ 稼働中。blindspot prescore の locale key bug 根本治療済 (2026-05-25) |
| F-2 | F-2 / F-5 | FlagshipGate / EliteJudge | 海外発の重要ニュースを優先 | ✅ 稼働中 |
| F-13.B | … / F-jp-coverage-cache-judgement-persist | JpCoverageVerifier (WL 30 ドメイン階層判定 + LLM judgement 抽出 B-3' + llm_judgement cache 永続化) | JP 報道カバレッジを WL + LLM judgement で検証 | ✅ 稼働中。cache hit 時も B-3' 判定値 + 判定根拠テキストが忠実復元 (2026-05-26)。Grounding = gemini-2.5-flash (Tier 非経由独立) |
| F-5 | F-5 | FlagshipGate 下流救済 | 上流ガードを通過した候補の最終整合 | ✅ 稼働中 (直近 run で 3 件 flagship 認定 = 入力依存、異常なし) |
| F-13 (隠れ層) | F-13 / F-doc-cleanup | script_writer.py quality_floor_miss bypass | analysis_result 等が成立すれば appraisal の [抑制] を上書き | ✅ 稼働中。★ production は旧ルート稼働 (analysis_result=null) のため新ルート未起動 = target_enemy が出力される構造。X1 で解消 |

## 5. 触ってよい / 触ってはいけない領域マップ

### 触ってよい領域
- `configs/prompts/` 配下全般 (主戦場: `configs/prompts/analysis/geo_lens/`)
- `docs/` 配下全般 (★ `docs/ADR/` 配下に ADR 新規作成可)
- `tests/` 配下に新規テストファイル追加 (既存ファイルは原則変更しない、
  ただし API contract 整合化に伴うフィクスチャ更新 + 既存ファイルへの新規
  テストクラス追加 + 仕様/データ構造整合に伴う既存期待値修正 (構造変更なし) は許容)
- `scripts/` 配下に新規スクリプト追加
- `src/triage/` に新規ファイル追加
- `src/storage/db.py` (★ 不変原則対象外 = storage 層。後方互換必須)
- `src/generation/script_writer.py` の **新ルート**
  (`generate_script_with_analysis` / `ScriptWithAnalysisDraft` 等。★ 新ルートは
  target_enemy を排除済み = X1 で本番配線する対象)
- `src/generation/script_writer.py` の `_CHAR_BOUNDS` 等の定数 (最小改変なら許容)
- `src/generation/video_payload_writer.py` (不変原則 1-4 対象外、★ target_enemy は
  L457-458 で条件付き露出 = 新ルート None なら非露出。Phase A.5-3b 第一作起案で
  images[]/events[] 追加の最小改変対象)
- `src/shared/models.py` (★ target_enemy は L221 で `Optional[str] = None`。Phase
  A.5-3b で VideoImage/VideoEvent Optional 追加予定、後方互換必須)
- `src/main.py` (不変原則対象外、★ X1 / verify_two_stage 本番配線判断 /
  F-evidence-jp-coverage-audit-trail で改修対象)
- `src/llm/factory.py` / `src/shared/config.py` の Gemini モデル ID default
  (★ F-gemini-quality-tier-poc / 2026-05-27 で最終布陣 v2 配線済 = QUALITY default gemini-3.5-flash /
  ARTICLE_ROLES 新設で article=gemini-2.5-flash 分離 / LIGHTWEIGHT default gemini-3.1-flash-lite +
  `_is_gemini_3_series` temperature ガード。config.py/factory.py inline default 不一致は Q2=揃える で解消済)
- `.env` / `.env.example` (リポジトリルート直下。★ `.env` は gitignored = API キー保持で commit 対象外、
  committable テンプレートは `.env.example`。★ `ANALYSIS_LAYER_ENABLED` は未設定 = default false =
  旧ルート稼働。X1 配線時に true 化判断。★ Tier モデル ID + `JUDGE_MODEL=gemini-3.5-flash` +
  `GEMINI_ARTICLE_TIER1〜4` は F-gemini-quality-tier-poc / 2026-05-27 で最終布陣 v2 に設定済)

### 触ってはいけない領域
- `src/generation/article_writer.py` (不変原則 1)
- `src/generation/script_writer.py` の **既存ルート**
  (`write_script` / `_PROMPT_TEMPLATE` / `_build_script_from_llm`) (不変原則 2)
  ★ **target_enemy のハードコード候補リスト (L113-118/317/445-446) はこの保護領域内
  = 直接修正不可。解消は X1 (新ルート配線) 経由のみ** (2026-05-26 調査で確定)
- `src/triage/` の既存ファイル (不変原則 3、★ 過去に例外条件適用済 = F-jp-coverage-improve / 2026-05-07 + F-f1-locale-key-fix / 2026-05-25 + F-jp-coverage-cache-judgement-persist / 2026-05-26)
- `src/analysis/` 配下全般 (不変原則 4)
- 既存テスト (不変原則 5、baseline **1417 passed** 維持 — ただし
  フィクスチャの API contract 整合化 + 既存テストファイルへの新規テスト
  クラス追加 + 仕様/データ構造整合に伴う既存テスト期待値修正 (構造変更なし) は許容)

## 6. 不変原則 5 つ (リマインダ、正本: BATCH_PROTOCOL.md)

1. **`src/generation/article_writer.py` 一切変更不可**
2. **`src/generation/script_writer.py` の既存ルート (`write_script` /
   `_PROMPT_TEMPLATE` / `_build_script_from_llm`) は変更不可** ★ target_enemy
   ハードコード候補リストもこの保護領域内 (2026-05-26 調査で確定)
3. **`src/triage/` の既存ファイル変更不可**。新規追加は OK。
   **例外条件** (5 点全充足で適用): 実装バグ修正 + 設計変更ではない +
   既存メソッド contract 完全維持 + baseline 維持 + カズヤ承認。
   ★ F-jp-coverage-improve (2026-05-07) / F-f1-locale-key-fix (2026-05-25) /
   F-jp-coverage-cache-judgement-persist (2026-05-26) で適用 (各 5 点全充足)。
4. **`src/analysis/` 変更不可**
5. **既存テスト破壊しない** (baseline **1417 passed**)

## 7. カズヤの直近フィードバック要点

- **「外部レビュー / 起案前事前情報も grep + コード精読で検証してから起案する」** (★ クラウド誤り 10、
  F-f1-locale-key-fix / F-jp-coverage-cache で 2 回発生 → ★★ F-script-writer-target-enemy
  (2026-05-26) + F-gemini-3.5-flash-api-audit (2026-05-27) で本作法が機能した好例: 調査専用
  バッチで grep-first を徹底し、起案前事前情報 (Gemini Round 1 / 2026-05-19 Google I/O) を実コードで
  検証 = クラウド誤り 10 の再発なし)。★★ **2026-05-27 (F-docs-update-chatgpt-round2-and-error10) で
  クラウド誤り 10 を CLAUDE.md に明文化** + **ChatGPT Round 2 レビューでも誤り 10 系統が発生**
  (古い Project Knowledge 由来で解消済 2 件を「新規発見」と誤認) = 外部 AI レビューも grep 検証対象
  である根拠の追加実例)
- **「設計判断と実装の分離」+「1 バッチで欲張らない」** (★ F-gemini-model-audit / F-gemini-3.5-flash-api-audit)
  — モデル戦略は audit (調査) → migrate-emergency (緊急実装) → quality-tier-poc (品質確定) に分割。
  3.5 Flash の API 影響調査と PoC を分離し、改修なしの調査専用バッチに縮小
- **「対症療法じゃなく根本治療」** (★ F-script-writer-target-enemy) — target_enemy は旧ルートの
  仮想敵 framing 哲学全体のマーカー。pinpoint 修正でなく新ルート配線 (X1) が根本治療
- **「LLM の知性に委ねる前に構造データの正しさを担保する」** (F-f1-locale-key-fix) /
  **「言い回しを個別ルールで指定するのは避けたい」** (クラウド誤り 9) — 新ルートは
  「メタデータ構造 + LLM の知性に委ねる」設計で target_enemy を排除済み
- **「整合の説明であって検証ではない」/ Project Knowledge・事前情報を鵜呑みにしない**
  (クラウド誤り 10) — Claude Web 側の作業ログ / 外部 AI レビュー / Google I/O 事前情報を
  docs 正本・grep 実態と取り違えない
- **「将来に負債を残さない」** — 旧ルート target_enemy のような未配線負債を放置しない (X1 で解消)
- **「動くものを壊さない」+「あるべき姿で進める」** — 旧ルートは不変原則 2 で保護、新ルート配線で正しい姿へ
- **「機械判定は事実の代替ではない」** — 候補A perspective_gap 確定は機械不在で覆らない
- **「中間が良い」/「考え方で制御」/「LLM の知性に委ねる」** — no_match のみ尊重 (B-3')
- **「Hydrangea のメディアとしてのリスクは嘘をつくこと」** — 疑わしきは低く見積もる
- **「観点の選択的欠落 = 忖度」** — 第一作 (候補A perspective_gap) を確定
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
- ★ **F-gemini-quality-tier-poc REPORT + 配線検証出力** → `docs/runs/F-gemini-quality-tier-poc/REPORT.md` + pricing_verification.json + api_spec_verification.json + factory_current_structure.json + temperature_current_state.json + model_roles_resolution.json + trial_run_summary.json + environment_snapshot.json
- ★ **F-docs-update-chatgpt-round2-and-error10 REPORT + grep 裏取り出力** → `docs/runs/F-docs-update-chatgpt-round2-and-error10/REPORT.md` + grep_evidence_3_4.json + title_guard_analysis.json + analysis_tokens_analysis.json + job_record_analysis.json + environment_snapshot.json
- ★ **F-gemini-3.5-flash-api-audit REPORT + 調査出力** → `docs/runs/F-gemini-3.5-flash-api-audit/REPORT.md` + grep_inventory.json + current_usage.json + adoption_simulation.json + breaking_change_analysis.json + environment_snapshot.json
- F-script-writer-target-enemy-fix-investigate REPORT → `docs/runs/F-script-writer-target-enemy-fix-investigate/REPORT.md`
- F-gemini-model-audit REPORT (モデル戦略調査の先行) → `docs/runs/F-gemini-model-audit/REPORT.md`
- F-gemini-model-migrate-emergency REPORT → `docs/runs/F-gemini-model-migrate-emergency/REPORT.md`
- ★ **Phase A.5-3b 画像戦略 / Remotion / モラル ADR** → `docs/ADR/0001-image-strategy.md` + `0002-remotion-mvp-scope.md` + `0003-content-moral-guidelines.md`

---

*このドキュメントは F-state-protocol (2026-05-01) で導入。Claude Code が
バッチ完了時に全置換更新する運用 (BATCH_PROTOCOL.md Task 5)。
F-gemini-quality-tier-poc (2026-05-27) は **ゲート完了後の 21 つ目のバッチ (1-Q)**、**実装バッチ**。
ChatGPT/Gemini セカンドオピニオン 2 ラウンド + Claude Web 裁定 + 公式 pricing 確認後の最終布陣 v2 を配線:
QUALITY (judge/script/analysis) = gemini-3.5-flash/MAX2、ARTICLE (article、role 新設分離、article_writer.py
不変) = gemini-2.5-flash/MAX1 (output $9.00→$2.50)、LIGHTWEIGHT (garbage/merge) = gemini-3.1-flash-lite/MAX1、
`JUDGE_MODEL=gemini-3.5-flash` 明示 + Gemini 3 系 temperature ガード。★ CP-1 で「最終布陣 v2 (10 role)」を
grep 検証 → 実 dispatch は 4 role のみ判明 (viral_filter/title は LLM stage 不在、editorial_mission_filter は
judge 共用で 3.5-flash/MAX2 のまま許容 = deviation、article は role 分離で 2.5-flash 実現)。公式 pricing/API
仕様を web_fetch (一次ソース) で全項目裏取り → 起案値と全一致で CP-0 スキップ。CP-2 試運転 (sample mode、
カズヤ「今すぐ run」) = exit 0/status=completed/script=3.5-flash+article=2.5-flash で retries=0/fallback 0/
404・Traceback・ERROR 0、target_enemy='大手メディア' は旧ルート framing で X1 まで継続。★★ クラウド誤り 10
派生「外部 AI セカンドオピニオンの権威化」を CLAUDE.md + DISCUSSION_NOTES に正本化 (Gemini 価格誤情報 +
Claude Web 廃止短絡 + ChatGPT 訂正の経緯)。Q2=揃える で config.py/factory.py inline default 不一致を解消。
baseline 1417→1432 passed (新規 15、破壊ゼロ)。変更 = factory.py / config.py / .env(gitignored) / .env.example /
tests 新規 2 + 既存 1 整合 (構造不変)、model_registry.py 確認のみ。不変原則 1-5 完全遵守。新規 follow-up =
editorial_mission_filter 独立分離 ★低 / run_summary model_roles 忠実化 ★低。
過去の経緯は DECISION_LOG.md / FUTURE_WORK.md / DISCUSSION_NOTES.md を参照。*
