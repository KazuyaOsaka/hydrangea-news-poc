# Hydrangea — 将来対応リスト (FUTURE_WORK)

最終更新: 2026-06-11 (★ F-first-work-golden-master 完了、実装バッチ 1-S。第一作 (候補A
cls-6889e9e1c7ac) の golden master 素材一式を自動出力で完成 = ①新ルート再生成 (editorial brief を
script プロンプトのみにプロセス内注入、article は不変原則 1 で素のまま) ②validation run 2 ガード
3 ランナー (coverage guard flag 1 = platform_title silence / Guardian 第1層 contradicted 1 = 告発主体
帰属エラー / 第2層 contradicted 2 = article の coverage 過大主張を独立ソースが明示矛盾) ③image_prompt
レイヤー新設 (`src/generation/image_prompt_writer.py`、5 プレート = 4 シーン 1:1 + フックカード 9:16、
文字なし / 意味記述正典 / ADR-0001+0003 強制) ④Remotion テンプレート (manual_poc/remotion/ 独立 npm、
セーフゾーン 3 帯紙面 + フックカード + Ken Burns + フレーズ同期字幕 + ducking、ダミー MP4 レンダ実証)
⑤運用規約 docs 化 (docs/golden_master_spec.md = original 凍結 / *_edited 命名 / 再検証ループ / 手動 PoC
チェックリスト)。★ CP-1 重大乖離訂正 = 候補A は sources_en=1 で extract_perspectives 構造的 0 件 →
fallback 同形 hidden_stakes 候補をハーネス注入 (production 不変)。★ モデル pin = QUALITY/ARTICLE 全
Tier を 3.5-flash に固定 (503 波での silent 劣化を fail に変換)。★ punchline 尻切れ再発 (loop-2、X1 と
同型 = 標本 2 例目)。`Phase A.5-3b 第一作起案` を完了移動 (残り = 手動 PoC、新エントリ ★高)。
`F-video-payload-visual-prompt-target-enemy` を完了移動 (L72 仮想敵 1 行除去)。新規:
**F-fable5-guardian-poc** (★低 条件付き)。baseline 1557 → **1581 passed** (新規 +24、破壊ゼロ)。
不変原則 1-5 + 第一作隔離 (6) 厳守。
前回 2026-06-10: F-editorial-guardian-corroboration 完了、実装バッチ 1-T.2。Editorial Guardian
第2段 = 真実性検証 (grounding 複数ソース突合) + レポート enrichment。検索と判定の分離 (証拠収集 =
`GUARDIAN_GROUNDING_MODEL` 軽量モデル / 判定 = Guardian 単一モデル = 沈黙的劣化の禁止を判定層で維持)。
truthfulness 語彙確定 (`corroborated / contradicted / uncorroborated` + harness 値 `unverified`) +
公開可否バー (supported × corroborated のみ非 flag) + 独立性最小定義 + deterministic 安全網。
X1 Slot-1 実走 2 回 = 503 波下で沈黙的劣化の禁止が実地で機能 + 再実行ループ実証 + run 間分散を
Guardian 文脈でも実測。`F-editorial-guardian-corroboration` を完了済みに移動 (**第一作前の関門ゼロ、
次バッチ = 1-S**)。新規 2 タスク: **F-guardian-production-wire** (★中、Guardian 2 層 production 配線 +
Phase A.5-3d 投稿前ゲート統合) / **F-guardian-independence-axis** (★低 条件付き、独立性評価軸の拡張要否)。
baseline 1519 → **1557 passed** (新規 +38、破壊ゼロ)。不変原則 1-5 厳守。
前回 2026-06-10: F-editorial-guardian-claim-extraction 完了、実装バッチ 1-T.1。Editorial
Guardian 第1段 = 高リスク事実主張の抽出 + 元ソース忠実性検証 (`supported / contradicted /
not_in_source` 3値 + harness 値 `unverified`) + 2層検証レポート骨格 (truthfulness_status=pending で
1-T.2 差し込みスキーマ固定)。factory.py に GUARDIAN role 新設 (gemini-3.1-pro-preview **単一要素
tier list** = 沈黙的劣化の禁止を構造的に担保、TIER2〜4 なし)。★ CP-1 で仮説 7 点を grep + 実コード +
実呼び出しで検証: 仮説 1 精密化 (元ソース全文は `event.summary` に raw 埋込 / pool snapshot は
分析前保存のため analysis_result=None → snapshot.event + analysis.json の合成再構成と確定)、仮説 4
疎通成功 (paid-only 課金済)。★ X1 Slot-1 実走で**本物の歪曲を検出** (20 主張中 1 contradicted =
「兵士 25 人死亡」の場所・期間帰属取り違え)。仮説 7 偵察 = F-13.B grounding 再利用性調査を
grounding_reuse_survey.md に出力 (コード変更なし)。`第一作公開前の高リスク事実検証ワークフロー`
(1-T) を 1-T.1 完了として完了済みに移動、**1-T.2 = F-editorial-guardian-corroboration を ★★高
(第一作前必須、次バッチ最有力) で緊急度 高に正式登録**。baseline 1487 → **1519 passed** (新規 +32、
破壊ゼロ)。不変原則 1-5 厳守。
前回 2026-06-08: F-title-guard-coverage-claim-policy 完了、実装バッチ 1-Q.5。coverage claim
事実整合の 3 層 (構造データ `configs/coverage_claim_policy.yaml` + script 新ルート生成プロンプト原則 +
生成後 guard `src/generation/coverage_claim_guard.py` = LLM judge / B-3' / flag のみ) を実装。X1 試運転で
本番再現した「perspective_gap に silence 絶対表現」を構造的に防止。★ CP-1 grep で起案者仮説 1 を訂正
(title の silence は `title_generator.py` ハードコード template + `is_strong` ヒューリスティクス由来 = script
非依存 → Layer 1 プロンプト原則では届かず guard が唯一の安全網) + 仮説 2 確認 (article プロンプトは
article_writer.py 内ハードコード = branch b、article は guard のみ)。`F-title-guard-coverage-claim-policy` を
完了済みに移動。新規 2 タスク追加: **F-title-generator-stream-aware-fix** (★中、title silence の根本修正) /
**F-coverage-claim-guard-auto-action** (★低 条件付き、guard 自動アクション要否を第一作後に判断)。
baseline 1466 → **1487 passed** (新規 +21、破壊ゼロ)。不変原則 1-5 厳守。
前々回 2026-06-08: F-article-model-upgrade 完了、config 変更バッチ。article 生成モデルを
gemini-2.5-flash → gemini-3.5-flash に品質昇格 = 選択肢C 第一歩 (B案 = config 変更 + 保存済み候補A
event での article A/B 再生成)。`GEMINI_ARTICLE_TIER1` を 3 協調箇所 (`.env` runtime / `.env.example`
template / `factory.py` inline default) で変更 (TIER1==TIER2 = 3.5-flash 追加リトライは意図的、1 値のみ変更)。
CP-1 grep で起案前提 5 点検証: ★仮説 1 訂正 (「変える 1 値」は 3 箇所協調 + 実 runtime 正は gitignored な
`.env`)、★仮説 3 訂正 (「MAX1」は MAX_ATTEMPTS であり max_output_tokens ではない。article は
generation_config=None で token 上限を設定せず truncate なし = クラウド誤り 10 の用語混同訂正)、仮説 2 確認
(article role は GEMINI_ARTICLE_TIER* 専用 env で完全分離、judge/script/analysis/lightweight に巻き込みなし)、
仮説 4 確認 (article は共通 LLMClient 経由 / src 全体に thinking_level・thinking_budget 不在 / 3.5-flash で
A/B 実測 retries=0 = API エラーなし)、仮説 5 確認 (候補A cls-6889e9e1c7ac event_snapshot 残存)。
article_writer.py / script_writer.py 既存ルート / triage / analysis 既存ファイル不変 (不変原則 1-4 厳守)。
既存テスト 4 件 (article=2.5-flash の旧設計 = primary distinct を符号化) を新仕様に期待値更新 (構造変更なし)、
baseline 1466 passed 維持。A/B 両出力 (article_2.5flash.md / article_3.5flash.md + ab_eval_metadata.json) を
docs/runs/F-article-model-upgrade/ に並置 (優劣判定はせず、axis_5 評価はカズヤ)。新規 2 タスク追加:
**F-article-3.1-pro-escalation** (★低、条件付き = 3.5-flash 不足時のみ 3.1 Pro へ) / **F-article-max-tokens-policy**
(★低、grep で article は truncate なし確定済、当面 no-action)。

前回 2026-05-31: F-particular-angle-metadata-production-wire (X1) 完了、実装バッチ 1-R。
`particular_angle_metadata` + `sontaku_signals` (nested) 本番配線完了で新ルートが production default
起動 + **target_enemy 自動退役**。不変原則 4 例外条件 5 点充足適用で `src/analysis/particular_angle_extractor.py`
新規作成。CP-1 でクラウド誤り 10 系統の作法により起案前提と実コードの 3 つの乖離を発見・訂正。
CP-2 で sample mode 分析未起動 + スタール枯渇 + GarbageFilter 48h でブロック → Path A pure (1 fresh
batch + 1 run、本番状態維持) に変更 (カズヤ判断、scaffolding は本番と違う人工状態を作るため不採用)。
試運転 (ingestion + normalized mode 1 run) で Slot-1 cls-c8876d474612 が全 X1 必須目的達成
(stream_2_perspective_gap + sontaku.level=high/diplomatic + target_enemy=None + Cultural Divide +
char validation passed + used_fallback=false / retries=0)。axis_5 カズヤ採点で CP-3 = **W1 完全成功**。
**F-analysis-max-tokens-tune 統合完了** (ANALYSIS_LLM_MAX_TOKENS=2000→4096)、本リストから完了移動。
baseline 1432→1466 passed (新規 +34、破壊ゼロ)。6 後続バッチ向け引継ぎ事項を新規追加: ★高
**F-editorial-guardian-fact-check-wire** (高リスク事実検証ワークフロー配線、X1 試運転で article 内
死者数 3,371人 / 兵士 25 人 / スモトリッチ過激発言引用が production 未検証と判明 = 1-T 必須化を実証) +
**F-script-punchline-tail-cut-investigate** (★中、Slot-1 punchline 「そこから繋がるのが、」未完結) +
**F-video-payload-visual-prompt-target-enemy** (★低、video_payload_writer.py:72 視覚プロンプトに
「仮想敵」語彙ハードコード残存) + **F-trial-data-procurement-protocol** (★中、試運転データ確保手順整備、
本バッチで blocker 4 連鎖を経験) + **F-periodic-health-check** スコープ拡張 (run 間分散観察を統合)。
前回 2026-05-27: F-gemini-quality-tier-poc 完了、実装バッチ。最終布陣 v2 を配線
(QUALITY=gemini-3.5-flash / ARTICLE=gemini-2.5-flash 分離 / LIGHTWEIGHT=gemini-3.1-flash-lite +
JUDGE_MODEL 明示 + Gemini 3 系 temperature ガード)。★ CP-1 で lineup v2 (10 role) を grep 検証 →
実 dispatch は 4 role のみ判明、新規 2 タスク起案 (**editorial_mission_filter 独立分離** ★低 /
**run_summary model_roles 忠実化** ★低)、**config.py/factory.py default 不一致整合** ★低 を完了 (Q2=揃える)。
baseline 1417→1432 passed、CP-2 試運転 exit 0。クラウド誤り 10 派生「外部 AI セカンドオピニオンの
権威化」を CLAUDE.md 明文化。前々回 2026-05-27: F-docs-update-chatgpt-round2-and-error10 完了、docs-only。
ChatGPT Round 2 レビュー (2026-05-27) の 7 指摘を grep 裏取りで照合し、新規 3 タスク追加 +
既存 1 タスクのスコープ拡張: ★★高 **F-title-guard-coverage-claim-policy** (緊急度 高、指摘 2 =
title_generator.py の perspective_gap に対する silence_gap 絶対表現リスク) + ★中
**F-analysis-max-tokens-tune** (緊急度 中、指摘 6 = factory.py:516 default 2000 → 4096 推奨) +
★低 **F-job-record-av-path** (緊急度 低、指摘 7 = JobRecord AV path が jobs DDL に未保存) +
**F-periodic-health-check** のスコープ拡張 (指摘 5 = tier fallback / retry 観測強化、★ 起案の
「F-pipeline-health-check」呼称を正本 F-periodic-health-check に統合)。指摘 3 (F-1 locale key) /
指摘 4 (F-13.B cache 永続化) は grep で解消済確認 (古い Project Knowledge 由来 = ChatGPT 側でも
クラウド誤り 10 系統発生)。指摘 1 は F-evidence-jp-coverage-audit-trail で登録済。クラウド誤り 10
系統を CLAUDE.md に明文化。baseline 1417 passed 維持 (改修なし自動維持)、src/ tests/ configs/
scripts/ .env .env.example 0 行変更。前回 2026-05-26: F-jp-coverage-cache-judgement-persist 完了。
F-13.B の
`llm_judgement` / `llm_judgement_text` を `jp_coverage_cache` に永続化 (案 A、DB
schema 2 列 + idempotent migration + verifier の save/get 拡張、判定ロジック不変)。
`F-jp-coverage-cache-judgement-persist` を完了済みに移動。★ CP-1 実害訂正:
Recall 劣化なし・既存監査トレース不在 = 真の defect は cache round-trip のデータ
忠実性欠落、緊急度 ★★→★ (クラウド誤り 10 の 2 回目発生を記録)。新規分離 =
**F-evidence-jp-coverage-audit-trail** (★中、案 B = evidence 監査トレース新設) +
**scripts schema doc-drift** (★低)。**F-script-writer-target-enemy-fix** (★★★高、
Gemini 独自指摘) を次バッチ最有力に格上げ。baseline 1417 passed 維持、1 batch
試運転 status=completed。前回 2026-05-25: F-f1-locale-key-fix 完了
(locale key bug 根本治療))

このドキュメントは「今は対応せず、将来検討・対応すべき項目」を記録する。各バッチ完了時に新しい項目が追加され、対応完了したら「完了済み」セクションに移動する。

---

## 緊急度 高（次のフェーズで必ず対応）

各項目は以下の形式で記載:
- **タイトル** (発生バッチ)
  - 背景: なぜこれが必要か
  - 対応案: どう対応するか
  - 検討時期: いつ判断するか
  - 関連ファイル: 影響を受けるファイル

---

- **F-12-B-2: perspective_extractor の axis 多様化** (F-13-B 完了後)
  - 背景: F-13-B 試運転で AnalysisLayer の selected_perspective が "cultural_blindspot" 等の限定的 axis に集中しがち。blind_spot_global 候補に適した axis (例: power_dynamics_blindspot, structural_silence) の不足が観察される。
  - 対応案: `src/analysis/perspective_extractor.py` の axis 定義を拡張し、Hydrangea ミッション本丸に対応する新 axis を追加。
  - 検討時期: F-12-B-1 完了後 (= 2026-05-01 完了済) → 次バッチで着手判断

- **event_builder.py のガード変更** (E-1 で見送り)
  - 背景: 現状 `if garbage_filter_client is not None:` でガードしているため、API キー未設定時に静的ルールが走らない
  - 対応案: `if GARBAGE_FILTER_ENABLED:` に変更し、API キー無しでも静的ルールを動作させる
  - 検討時期: 触っちゃダメリスト見直しと同時
  - 関連ファイル: src/ingestion/event_builder.py (touch-禁止リスト掲載中)

- **触っちゃダメリスト（CLAUDE.md）の見直し** (E-1 完了後に発覚)
  - 背景: ハイブリッド版になって event_builder.py の garbage_filter 周辺は触ってOK。scoring.py も新 axis 追加が必要になる可能性
  - 対応案: 各ファイルの「なぜ触ってはいけないか」を明示し、状況依存で触ってよい範囲を定義
  - 検討時期: Phase 1.5 全完了後

- **perspective_extractor 改善 (F-7-α 候補)** (試運転 7-G で発覚 / F-14 で関連事象を観測)
  - 背景: Slot-1 (cls-8bbec722d420 Venezuela) で `no perspective candidates met conditions → analysis_result=None` が再発。`extract_perspectives()` のルールベース判定が厳しすぎ、政治系イベントでも候補ゼロになるケースがある。F-14 は JSON parser を堅牢化したが、そもそも候補が抽出されないケースは救えない。
  - 対応案: `src/analysis/perspective_extractor.py` の各 axis 判定条件を緩和、または最低 1 件の候補を必ず返す保険ロジック (lowest-bar fallback) を追加。
  - 検討時期: F-12-B (script_writer プロンプト全面刷新) 完了後
  - 関連ファイル: src/analysis/perspective_extractor.py, tests/test_perspective_extractor.py

- **AnalysisLayer LLM の max_tokens / 切れ防止 (F-14 で workaround 済)** (F-14 / 試運転 7-G で発覚)
  - 背景: F-14 で JSON parser の修復ロジックを実装し、出力が途中で切れた場合でも可能な限り救済できるようになった。ただし根本原因は LLM 出力の途中切断 (max_tokens 制限 / Tier フォールバック中の長い応答) であり、F-14 は対症療法。
  - 対応案: (a) AnalysisLayer の `multi_angle_analyzer` / `insight_extractor` に `max_output_tokens` の明示指定を追加し、十分な余裕を確保する。(b) Tier 別に max_output_tokens を調整。(c) 出力長を抑えるプロンプト改修 (短く・JSON だけ生成させる)。
  - 検討時期: 試運転 7-H で F-14 修復ログ ([F-14] JSON repaired) の発動頻度を確認後。発動が多発するなら根本対応に着手。
  - 関連ファイル: src/llm/factory.py, src/analysis/multi_angle_analyzer.py, src/analysis/insight_extractor.py, configs/prompts/analysis/

- **EditorialMissionFilter Step1 prescore の軸スコアゼロ問題** (F-1.5 試運転で発覚)
  - 背景: F-1.5 試運転で発覚。軍事費・ゼレンスキー等の地政学記事で `editorial:geopolitics_depth_score` / `editorial:breaking_shock_score` / `editorial:mass_appeal_score` が 0.0 になっていた。本来高得点になるはずの記事が低 prescore で却下される/低位置に置かれる懸念
  - 対応案: `src/triage/scoring.py` の `compute_score_full()` を読み、各 axis 計算ロジックを確認。修正には scoring.py を触る必要があるため、触っちゃダメリスト見直しと一緒に対処
  - 検討時期: F-1.5 完了後の次のバッチ
  - 関連ファイル: src/triage/scoring.py（読み取り）, src/triage/editorial_mission_filter.py

- **cron 6 時間おき自動実行の整備 (F-16-B)** (F-16-A で per-run 上限分離後の本番リリース要件)
  - 背景: F-16-A で per-run 上限を `TOP_N_VIDEOS_PER_RUN` / `TOP_N_ARTICLES_PER_RUN` に分離した。本番運用は cron 6 時間おき × per-run 上限で公開頻度を制御する設計だが、cron 設定自体は未実装。
  - 対応案: GitHub Actions / launchd / VPS のいずれかで `python -m src.main --mode normalized` を 6 時間おきに実行。失敗時通知、ログローテーション、batch ロックの整備も同時。本番想定値: 4 run/日 × 1 動画/run = 4 動画/日 + 4 run × 3 記事 = 12 記事/日。
  - 検討時期: F-16-A 試運転 7-J で動画化率 100% を確認後、本番リリース判断時
  - 関連ファイル: 新規 `.github/workflows/run-pipeline.yml` または `launchd/*.plist` または systemd unit, src/main.py (CLI 引数追加の可能性)

- **ChannelConfig.publishing_limits 統合 (Phase 1-A)** (F-16-A で per-run 上限を環境変数化)
  - 背景: F-16-A は `TOP_N_VIDEOS_PER_RUN` / `TOP_N_ARTICLES_PER_RUN` をグローバル env で持つ暫定実装。Phase B で TikTok / Shorts / Web 別チャンネルや `japan_athletes` / `k_pulse` を稼働させる際は、チャンネル単位で上限を変えられる必要がある。
  - 対応案: `ChannelConfig` (src/shared/models.py) に `publishing_limits: PublishingLimits` を追加し、`videos_per_run` / `articles_per_run` を持たせる。main.py 側で env 読み込みからチャンネル設定読み込みに移行。env は deprecation 期間を経て撤廃。
  - 検討時期: Phase 1-A (REFACTORING_PLAN.md 段階 2) 着手時
  - 関連ファイル: src/shared/models.py, configs/channels.yaml, src/main.py, .env.example

### Phase A.5-3a-verify (F-state-protocol-supplement / 2026-05-02 登録、F-jp-coverage-improve / 2026-05-07 で順序更新、F-trial-run-post-fix / 2026-05-07 でゲート完了)

**Phase 順序 (★更新版、2026-05-07 F-trial-run-post-fix 完了後 = ゲート完了)**:

```
[完了] F-jp-coverage-improve (F-13.B 構造的不具合修正)
  ↓ 修正後 verify_jp_coverage_measure.py 再測定で構造的不具合は解消
    (TP=10/14, FN=4 vs 修正前 TP=0/14, FN=14)、verdict=fail のまま
[完了] F-trial-run-post-fix (修正後 F-13.B の本番試運転 + 過去判定後追い)
  ↓ 構造的不具合解消の本番動作確認 (excluded_count 非ゼロ)、防衛機構 5 層全機能、
    試運転 7-K 過去動画 3 件 WebSearch 後追いで stream_2_candidate パターン確認
★ Phase A.5-3a-verify ゲート完了 (1-A〜1-D''' 全完了) ★
  ↓
F-stream-2-filter-design (★着手 OK、系統 2 用 2 段階フィルタ実装)
  → Phase A.5-3b 手動 PoC (フィルタ確定済みで PoC に集中)

別系 (任意、並走可):
  F-jp-coverage-tune (Recall/Precision/Tier 一致率の閾値達成、ゲート完了の必須条件ではない)
```

★ F-trial-run-post-fix (2026-05-07 完了) で F-jp-coverage-improve の修正が
本番運用で機能していることを確認 (試運転 6 invocations のうち 5/6 で
excluded_urls_count > 0、ドメイン抽出層の本番動作証明)。試運転 7-K 過去動画化
3 件のうち 2 件 (Slot-1 FIFA / Slot-2 Mandelson) は WebSearch では Tier 1-2
報道済みと判明 = 典型的 stream_2_candidate パターン (golden set v1.1
blind_002/004/005/009 と同形)。Phase A.5-3a-verify ゲート完了の根拠が確保された。
F-stream-2-filter-design 着手 OK 状態に。

並走候補: F-verify-perspective / F-verify-script-quality (3b/3c 中にデータ収集)

- ~~**F-jp-coverage-tune-followup** (★最優先、2026-05-09 完了、完了済みセクション参照)~~

- ~~**F-jp-coverage-tune** (★最優先、2026-05-09 完了、完了済みセクション参照)~~

- ~~**F-trial-run-post-tune** (★最優先、2026-05-11 完了、完了済みセクション参照)~~

- ~~**F-13.B WL ヒット品質の独立検証** ★高 (F-trial-run-post-tune / 2026-05-11 で観察、F-wl-hit-quality-audit / 2026-05-14 完了、完了済みセクション参照)~~

- ~~**F-jp-coverage-llm-judgement-extraction** ★最優先 (F-wl-hit-quality-audit / 2026-05-14 で根本原因確定、F-jp-coverage-llm-judgement-extraction / 2026-05-16 完了、完了済みセクション参照)~~

- ~~**F-trial-run-post-llm-extraction** ★最優先 (F-jp-coverage-llm-judgement-extraction / 2026-05-16 で起案、F-trial-run-post-llm-extraction / 2026-05-16 完了、完了済みセクション参照)~~

- ~~**F-trial-run-candidate-a-reverify** ★高 (F-trial-run-post-llm-extraction / 2026-05-16 でカズヤ起案、F-trial-run-candidate-a-reverify / 2026-05-19 完了、完了済みセクション参照。候補A 不在 + 3 連続試運転で B-3' 構造的効果確定 = 目的達成、候補A は perspective_gap framing で維持)~~

- ~~**F-gemini-model-migrate-emergency** ★★★高 (F-gemini-model-audit / 2026-05-19 起案、**5/25 deadline 必達**)~~ → ★ **完了 (F-gemini-model-migrate-emergency / 2026-05-19)**。両系統 Tier3 + factory.py/config.py default + `.env`/`.env.example` を `gemini-3.1-flash-lite` (GA) に一括置換、shutdown モデル ID を Tier 階層から構造的に除去 = 404 即 raise リスク根絶 (retry.py 0 行変更)。CP-1 カズヤ判断 = test 2 行更新承認 + Lightweight Tier1 据置 (B)。baseline 1417 passed 維持、1 batch 試運転 status=completed。詳細は完了済みセクション + `docs/runs/F-gemini-model-migrate-emergency/REPORT.md`。

- ~~**F-f1-locale-key-fix** ★★高 (3 AI 三角測量レビュー / 2026-05-25 起案)~~ → ★ **完了 (F-f1-locale-key-fix / 2026-05-25)**。`src/triage/editorial_mission_filter.py` の `_editorial_mission_prescore` 内 `sources_by_locale.get("jp"/"en")` を実データ構造の正しいキー (`"japan"` + 非 japan 合算 = main.py overseas_count パターン) に修正。機能ロジック不変、locale key 参照の正本化のみ。CP-1 カズヤ判断 = 選択肢 1 (非 japan 合算) + test data キー同時更新。★ クラウド初期想定 (「不当に高い誤爆」) を grep で訂正 = 実態は「中間解像度 8〜12 点の永久喪失 (false negative 方向)」、緊急度 ★★★→★★ (クラウド誤り 10 記録)。baseline 1417 維持、1 batch 試運転 status=completed。詳細は完了済みセクション + `docs/runs/F-f1-locale-key-fix/REPORT.md`。

- ~~**F-jp-coverage-cache-judgement-persist** ★★高 (3 AI 三角測量レビュー / 2026-05-25 起案)~~ → ★ **完了 (F-jp-coverage-cache-judgement-persist / 2026-05-26)**。`src/storage/db.py` の `jp_coverage_cache` DDL に `llm_judgement` / `llm_judgement_text` 列追加 + idempotent migration、`src/triage/jp_coverage_verifier.py` の `_save_cache` / `_get_cached` を 2 列対応に拡張 (案 A、判定ロジック不変)。★ CP-1 で実害訂正: `verify()` は cache hit を再計算せずそのまま return し has_jp_coverage は保存済 → **Recall 劣化は発生せず**、また llm_judgement は evidence/run_summary に未出力で**既存監査トレースも不在** = 真の defect は「cache round-trip のデータ忠実性欠落 (判定根拠テキスト消失)」、緊急度 ★★→★。クラウド誤り 10 の 2 回目発生 (外部レビュー指摘の鵜呑み) を DISCUSSION_NOTES に記録。baseline 1417 維持、golden Recall 非劣化を決定パス不変性で確認、1 batch 試運転で cache hit 時 llm_judgement 忠実復元を実証 (Slot-2 no_match)。不変原則 3 例外条件 5 点全充足。詳細は完了済みセクション + `docs/runs/F-jp-coverage-cache-judgement-persist/REPORT.md`。

- **F-evidence-jp-coverage-audit-trail** ★中 (F-jp-coverage-cache-judgement-persist / 2026-05-26 起案、案 B 単独を分離)
  - 背景: F-jp-coverage-cache-judgement-persist の Task B で判明 — `llm_judgement` は src/ で verifier 以外から参照されず、evidence.json / run_summary.json に出力されていない (main.py は has_jp_coverage を log するのみ)。F-13.B の判定根拠を事後監査するには evidence への証跡化が必要。ChatGPT レビューの「score_breakdown 経由案」がこれに相当 (= 案 B、本体バッチでは新機能のためスコープ外に分離)。
  - 対応案: main.py で `score_breakdown["jp_coverage_verification"]` に has_jp_coverage / matched_domains / matched_tier / llm_judgement を積む経路を追加 (evidence_writer は score_breakdown を保存するため writer 改修なし)。★ cache lossless 化 (本体バッチ案 A 完了) が前提として整ったため、cache hit/miss で値が割れない。クラウド誤り 9 (各論コントロール) に留意し構造データ注入に留める。
  - 検討時期: F-script-writer-target-enemy-fix の後など任意 (新機能、緊急度 中)
  - 想定工数: 1-2h (score_breakdown 注入 + evidence 出力確認 + 試運転)
  - 関連ファイル: `src/main.py` (F-13.B 呼び出し L3168-3212 周辺), `src/generation/evidence_writer.py` (score_breakdown 保存経路、writer 不変)
  - 関連: F-jp-coverage-cache-judgement-persist (案 A = cache lossless 化の土台)、3 AI 三角測量レビュー ChatGPT 案

- ~~**F-script-writer-target-enemy-fix** ★★★高 (3 AI 三角測量レビュー / 2026-05-25 起案、Gemini 独自指摘) [★ 重複 2 エントリを統合]~~ → ★ **調査完了 (F-script-writer-target-enemy-fix-investigate / 2026-05-26)**。読み取り専用調査 (grep + コード精読 + 試運転観察) で実態確定。**真因 a 確定**: production 稼働中の旧ルート `write_script` が `target_enemy` (仮想敵) をハードコード候補リストから出力し viewer-facing な煽り framing を誘導するが、旧ルートは不変原則 2 で直接修正不可。新ルート `generate_script_with_analysis` は設計上既に target_enemy 排除済み (契約テストで固定) = **新ルート配線が唯一の sanctioned 解消経路**。CP-1 カズヤ判断 = **X1 (新ルート配線バッチに統合)** = 下記「particular_angle_metadata + sontaku_signals の本番配線判断」エントリに target_enemy 解消を吸収。★ 起案前 Project Knowledge 仮説 1-5 は grep で概ね CONFIRMED = クラウド誤り 10 の 3 回目発生なし (外部指摘を grep で検証してから起案する作法が機能)。詳細は `docs/runs/F-script-writer-target-enemy-fix-investigate/REPORT.md`。

- ~~**F-gemini-quality-tier-poc** ★★高 (F-gemini-model-audit / 2026-05-19 起案、Phase A.5-3b 第一作起案前)~~ → ★ **完了 (F-gemini-quality-tier-poc / 2026-05-27)**。最終布陣 v2 を配線: QUALITY (judge/script/analysis) = `gemini-3.5-flash` primary/MAX2、ARTICLE (article、新設 role 分離) = `gemini-2.5-flash` primary/MAX1 (output $9.00→$2.50)、LIGHTWEIGHT (garbage/merge_batch) = `gemini-3.1-flash-lite` primary/MAX1 (★ migrate-emergency CP-1 保留分の切替採用)。`JUDGE_MODEL=gemini-3.5-flash` 明示追加 + Gemini 3 系 temperature ガード追加。★ CP-1 で lineup v2 (10 role) を grep 検証 → 実 dispatch は 4 role のみ判明 (viral_filter/title は LLM stage 不在、editorial_mission_filter は judge 共用で 3.5-flash/MAX2 のまま許容 = deviation、article は role 分離で 2.5-flash 実現)。公式 pricing/API 仕様を web_fetch で全裏取り (CP-0 スキップ)。baseline 1417→1432 passed、CP-2 試運転 exit 0/status=completed (script=3.5-flash + article=2.5-flash, retries=0, fallback 0)。axis_5 採点はカズヤ手動 (第一作着手前)。残課題 = editorial_mission_filter 独立分離 / run_summary model_roles 忠実化 (下記新規)。詳細は完了済みセクション + `docs/runs/F-gemini-quality-tier-poc/REPORT.md`。
  - 背景: 2026-05 Gemini モデル群更新で Narrative 主軸 (QUALITY Tier1) の最適モデルが未確定。★ **候補リスト更新 (F-gemini-3.5-flash-api-audit / 2026-05-27)**: 2026-05 GA リリースの `gemini-3.5-flash` (Stable、RPD 10K/RPM 1K/TPM 2M、Thinking/FunctionCalling/StructuredOutputs/Grounding すべて Supported) を**候補に追加**し、`gemini-3-flash-preview` を**削除** (3.5 Flash Stable が GA 後継で代替可能)。確定候補 = `gemini-3.5-flash` (Stable、新主軸本命) / `gemini-2.5-flash` (RPD 10K、安定 fallback ベースライン) / `gemini-3.1-pro` (RPD 250、Editorial Guardian 候補、別枠局所使用)。emergency 移行は Tier3 GA 化のみで primary 品質は別途 PoC で確定する必要がある (設計判断と実装の分離)。★ API 破壊的変更は audit で**真因 b (無いか軽微)** 確定済 = migration 不要、API 互換問題なしで投入可能 (本番生成系は generation_config=None で API パラメータ非指定、構造化出力/カスタム function calling 未使用)。
  - ★ 内包課題 (F-gemini-model-migrate-emergency CP-1 判断 B からの保留分): **Lightweight 主軸 (Tier1) を `gemini-2.5-flash` (RPD 10K) → `gemini-3.1-flash-lite` (GA, RPD 150K = 15 倍) に切替えるか**を axis_5 品質検証で判断。emergency では「動くものを壊さない」優先で据置 (Gemini 2→3 系統変更は MEDIUM リスク、1 batch 試運転だけでは検証不十分)。本 PoC で Lightweight 4 role (garbage_filter/merge_batch/viral_filter/editorial_mission_filter) の出力品質を検証後に投入判断。
  - 対応案: Narrative 系 QUALITY モデル + Lightweight Tier1 候補の品質 PoC + axis_5 採点で主軸確定。Pro は Editorial Guardian (高リスク事実検証専用、局所使用) に限定し Quality 主軸にしない方針を検証。`publish_gate_flags` 構造設計も併せて検討。
  - 検討時期: Phase A.5-3b 第一作起案前 (起案で使う確定モデルが必要)、次バッチ最有力
  - 想定工数: 3-5h + axis_5 採点
  - 関連ファイル: `src/llm/factory.py`, `.env`, `docs/runs/F-gemini-model-audit/REPORT.md` §8-3, `docs/runs/F-gemini-model-migrate-emergency/REPORT.md` §4, `docs/runs/F-gemini-3.5-flash-api-audit/REPORT.md` §5 (候補リスト更新提案) + `adoption_simulation.json` (RPD/RPM 試算)
  - ★ 追加留意点 (F-gemini-3.5-flash-api-audit / 2026-05-27): 3.5 Flash 投入時に Thought preservation 自動 ON による output_token/レイテンシ増加を PoC 試運転で実測観察 (機能破壊なし、改修不要のコスト面留意点)。LIGHTWEIGHT Tier1 切替は `gemini-3.1-flash-lite` (RPD 150K) が本命 (高頻度・低難度に spike 耐性、3.5 Flash は RPD 10K を Narrative primary と共有しないため使わない)。
  - 関連: F-gemini-model-audit (本起案元)、F-gemini-model-migrate-emergency (emergency 移行完了、Lightweight Tier1 切替を本 PoC に保留)、F-gemini-3.5-flash-api-audit (★ 候補リスト更新 + API 破壊的変更なし確定)、Phase A.5-3b 第一作起案

- ~~**F-title-guard-coverage-claim-policy** ★★高 (1-Q.5)~~ → ★ **完了 (F-title-guard-coverage-claim-policy / 2026-06-08)**。汎用 coverage_claim_policy 構造データ (`configs/coverage_claim_policy.yaml`) + script 新ルート生成プロンプト原則 (事実整合) + 生成後 guard (LLM judge、事実整合検証、flag のみ) を実装。詳細は「完了済み」セクション参照。★ CP-1 訂正: 起案者仮説 1「silence 表現は script の title 素材から流入」は **誤り** — grep で `title_generator.py` の **ハードコード template** (`_platform_title_candidates` L136/149/203) + `is_strong` evidence ヒューリスティクス由来と確定 (script 本文非依存)。よって title の silence は Layer 1 プロンプト原則では届かず、guard (Layer 3) が唯一の安全網。title_generator.py を stream-aware にする根本修正は別タスク (下記新規 ★中) に分離。

- ~~**config.py/factory.py default 不一致整合** ★低 (F-gemini-model-audit §9-3 / F-gemini-model-migrate-emergency 2026-05-19 残置)~~ → ★ **完了 (F-gemini-quality-tier-poc / 2026-05-27、Q2=揃える)**。config.py:76-79 の GEMINI_MODEL_TIER1-4 inline default を最終布陣 v2 (QUALITY 系統 = gemini-3.5-flash / 2.5-flash / 3.1-flash-lite / 2.5-flash-lite) に整合し、factory.py QUALITY default と一致させた。runtime 影響なしの既知 doc-drift を解消。

- **editorial_mission_filter のモデル独立分離** ★低 (F-gemini-quality-tier-poc / 2026-05-27 起案、CP-1 deviation 由来)
  - 背景: 最終布陣 v2 は editorial_mission_filter を 2.5-flash/MAX1 (LIGHTWEIGHT 寄り) と想定したが、実コードでは `get_judge_llm_client()` を共用 (main.py:2453) するため judge と同一 client = gemini-3.5-flash/MAX2 になる。F-gemini-quality-tier-poc では「1 バッチで欲張らない」+ main.py が本バッチ変更可リスト外のため 3.5-flash/MAX2 のまま許容 (deviation)。
  - 対応案: factory.py に `get_mission_llm_client()` (role="editorial_mission_filter") を新設 + main.py:2453 を差替 + `_get_tier_models_for_role` に editorial_mission_filter 専用群 (2.5-flash 主軸) 追加。コスト面: mission scoring は top-20 prescore に bounded、input 偏重のため deviation のコスト影響は中程度。
  - 検討時期: 低優先、X1 (main.py 改修バッチ) 同時対応 or 別 refactor
  - 想定工数: 1-2h
  - 関連ファイル: `src/llm/factory.py`、`src/main.py` L2453、`docs/runs/F-gemini-quality-tier-poc/factory_current_structure.json`
  - 関連: F-gemini-quality-tier-poc (本起案元、CP-1 deviation)

- **run_summary.model_roles の実 tier 解決忠実化** ★低 (F-gemini-quality-tier-poc / 2026-05-27 起案、CP-2 試運転で発見)
  - 背景: run_summary.json の `model_roles` は config role 定数 (GENERATION_MODEL / MERGE_BATCH_MODEL / JUDGE_MODEL) を label 化する機構で、Gemini の実 tier 解決 (`_get_tier_models_for_role`) と部分乖離する。特に merge_batch label (= GEMINI_CLUSTER_MODEL = GEMINI_MODEL_TIER2 = gemini-2.5-flash) が実 LIGHTWEIGHT tier1 (gemini-3.1-flash-lite) と不一致 = 監査時に実使用モデルを誤認するリスク。
  - 対応案: run_summary に各 role の実 tier1 (TieredGeminiClient._tiers[0]) を記録、または used_fallback と併せて実モデルを snapshot。F-periodic-health-check (ChatGPT Round 2 指摘 5 = tier fallback/retry runtime snapshot) に統合候補。
  - 検討時期: F-periodic-health-check 着手時 (Phase A.5-3d 前提) に統合
  - 想定工数: 1-2h (health-check 統合なら追加 0.5h)
  - 関連ファイル: `src/main.py` (run_summary 構築箇所)、`src/llm/model_registry.py`、`docs/runs/F-gemini-quality-tier-poc/trial_run_summary.json`
  - 関連: F-gemini-quality-tier-poc (本起案元)、F-periodic-health-check (統合候補)
  - 関連ファイル: `src/shared/config.py:77-79`, `src/llm/factory.py:322-325`

- **scripts/verify_jp_coverage_measure.py の inline schema doc-drift** ★低 (F-jp-coverage-cache-judgement-persist / 2026-05-26 検出)
  - 背景: 測定スクリプトが自前の `_TEMP_DB_SCHEMA` で `jp_coverage_cache` DDL を複製しており (「src/storage/db.py 102-112 と一致」コメント付き)、F-jp-coverage-cache-judgement-persist の 2 列追加 (`llm_judgement` / `llm_judgement_text`) で db.py 正本と乖離した。scripts/ は当該バッチで変更不可だったため未修正。fresh モードでは cache 非依存のため accuracy に影響なし。
  - 対応案: スクリプトの temp DB 構築を `init_db()` 呼び出しに置換 (DDL 複製を廃し正本に一元化)、または `_TEMP_DB_SCHEMA` に 2 列追記。
  - 検討時期: 低優先、scripts/ を触る別バッチ or doc-drift 整理時
  - 関連ファイル: `scripts/verify_jp_coverage_measure.py` (`_TEMP_DB_SCHEMA`), `src/storage/db.py` (DDL 正本 + `_migrate_jp_coverage_cache`)

- ~~**F-gemini-503-stability-audit** ★高 (F-17 候補から昇格)~~ → ★ **撤回 (F-gemini-model-audit / 2026-05-19)**。理由: Gemini モデル切替 (`F-gemini-model-migrate-emergency` で Tier3 を GA 化 + Lightweight 主軸 RPD 150K 化候補) で 503 多発リスクは**根本治療**される。リトライ間隔調整 / サーキットブレーカー等の対症療法的個別対処は不要。503/fallback の早期検知は `F-periodic-health-check` (緊急度 中に降格、Phase A.5-3d 前提) でカバー。

- ~~**F-periodic-health-check** ★高 (F-trial-run-candidate-a-reverify / 2026-05-19 新規起案)~~ → ★ **緊急度 中に降格 (F-gemini-model-audit / 2026-05-19、カズヤ確認済)**。理由: 本番リリース前は不要、Phase A.5-3d cron 完全自動投稿実装時で OK。詳細エントリは「緊急度 中」セクション参照。

- **F-jp-coverage-tune-followup REPORT v2 化** ★高 (F-wl-hit-quality-audit / 2026-05-14 で要件確定)
  - 背景: F-wl-hit-quality-audit の独立検証で F-jp-coverage-tune-followup Step C メトリクス (F1 covered 0.8718 / Recall covered 89.47% / Precision blind 33.33%) が **broader topic-family level の値**であって、**specific event (= particular_angle) level では下振れの可能性** が確認 (試運転 + golden サンプリングで 3/8 = 37.5% で topic-family 一致 / specific 不一致パターン観察)。CP カズヤ判断 = 本バッチ (F-wl-hit-quality-audit) は記録のみ、REPORT v2 化は別バッチとして分離。
  - 対応案: F-jp-coverage-tune-followup REPORT.md に broader vs specific caveat セクションを追加 + F-wl-hit-quality-audit 検証結果へのリンク + 解釈ガイダンス (= 機械検出の現在地と Option (i) 実装後の予想再評価値)。本来は F-jp-coverage-llm-judgement-extraction の再測定結果と統合して書き直すのが最適。
  - 検討時期: F-jp-coverage-llm-judgement-extraction 完了直後 (= 再測定値が出てから統合 v2 化、現状値だけで v2 化するメリットは小さい) OR F-jp-coverage-tune-followup-2 着手と統合
  - 想定工数: 1-2 時間 (単体バッチで実施する場合)、F-jp-coverage-llm-judgement-extraction or -tune-followup-2 に統合する場合は工数追加最小
  - 関連ファイル: `docs/runs/F-jp-coverage-tune-followup/REPORT.md` (v2 化対象)、`docs/runs/F-wl-hit-quality-audit/REPORT.md` (caveat の根拠)
  - 関連: F-wl-hit-quality-audit (caveat 発見元)、F-jp-coverage-llm-judgement-extraction (再測定値の供給元)、F-jp-coverage-tune-followup-2 (統合候補)

- **ゴールデンセット v2 化検討 (specific angle truth annotation)** (F-wl-hit-quality-audit / 2026-05-14 で論点提起)
  - 背景: F-wl-hit-quality-audit で『topic-family level』と『specific event level』の Recall/Precision 乖離が顕在化。現ゴールデンセットは `expected_broad_jp_coverage` / `expected_angle_jp_coverage` truth を持つが、★ **『specific angle level (= MEE/TeleSUR が独自に掘った particular_angle 単位) で日本主要メディアが報じているか』という truth は明示的に annotate されていない** 可能性。これが annotate されていれば F-jp-coverage-llm-judgement-extraction の再測定で broader vs specific の Recall/Precision を 2 軸で評価可能。
  - 対応案: `docs/runs/F-verify-jp-coverage/golden_set.json` v2 として specific angle truth フィールドを追加。各 event について particular_angle (例: Slot-1 なら『ICRC 訪問操作疑惑』) と該当 angle が日本主要メディアで報じられているか truth を明示する。F-particular-angle-design の `annotations.json` と整合させる。
  - 検討時期: F-jp-coverage-llm-judgement-extraction 着手前に実施する (= 再測定の評価軸を整える) OR 着手と並走
  - 想定工数: 2-4 時間 (annotate + 整合性チェック + 既存メトリクス計算ロジックへの対応)
  - 関連ファイル: `docs/runs/F-verify-jp-coverage/golden_set.json`、`docs/runs/F-particular-angle-design/annotations.json`、`scripts/measure_two_stage_accuracy.py` (specific angle metric 対応)
  - 関連: F-jp-coverage-llm-judgement-extraction (再測定で specific angle level の精度評価)、F-jp-coverage-tune-followup REPORT v2 化 (caveat 反映)

- **verify_two_stage 本番配線判断** (F-trial-run-post-tune / 2026-05-11 で観察)
  - 背景: F-jp-coverage-tune (2026-05-09) で `verify_two_stage()` 二段階クエリ生成メソッドが新規実装され、F-jp-coverage-tune-followup (2026-05-09) で `_match_whitelist` 階層判定化 + WL 拡張で機械精度が改善 (F1 covered 0.8718 で threshold 初突破) したが、**production main.py:3187 は legacy `verify()` (broad-only) のみ呼び出し** で本番未配線。F-trial-run-post-tune で stream_1/2/3 機械判別が production-pipeline 上で稼働しないことが確認された。
  - 対応案: (a) `src/main.py` を改修して `verify_two_stage()` を呼び出すように切り替え (`particular_angle` 引数を analysis_result から導出する必要あり)、(b) `verify_two_stage()` 戻り値 (`TwoStageVerifyResult`) の `stream` 値を `final_routing` ロジックに反映 (stream_1_silence_gap → blind_spot_global, stream_2_perspective_gap → divergence pattern + 系統 2 ラベル, stream_3_candidate → divergence pattern + 系統 3 ラベル, unknown → 既存挙動)、(c) `analysis_result.selected_perspective` から `particular_angle.core_question` を抽出する変換層を実装、(d) F-stream-2-filter-design との関係整理 (= verify_two_stage 配線後、stream_3 候補に対する解説価値判定を F-stream-2-filter-design で行う設計)
  - 検討時期: F-stream-2-filter-design 責務範囲再評価と同時 OR Phase A.5-3b 第一作着手後の並走バッチ
  - 想定工数: 4-8 時間 (main.py 改修 + analysis_result → particular_angle 変換 + 既存 verify() からの段階的移行設計 + テスト + 試運転)
  - 関連ファイル: `src/main.py` (3170-3220 行帯の F-13.B 呼び出し箇所、★ 不変原則対象外)、`src/triage/jp_coverage_verifier.py` (既存メソッド完全不変)、`src/shared/models.py` (`AnalysisResult` から `particular_angle` を導出する論理)、関連 docs (`docs/PARTICULAR_ANGLE_DEFINITION.md`)
  - 関連: F-stream-2-filter-design (★ 配線後の系統 3 候補処理を担う)、Phase A.5-3b 第一作起案 (試運転で本配線効果を確認)、F-particular-angle-redesign-extension (4 分類化 + sontaku_signals 独立化の本番反映を兼ねる)

- ~~**particular_angle_metadata + sontaku_signals の本番配線判断** (F-trial-run-post-tune / 2026-05-11 で観察、★ F-script-writer-target-enemy-fix-investigate / 2026-05-26 で target_enemy 解消 (X1) を統合)~~ → ★ **完了 (F-particular-angle-metadata-production-wire / 2026-05-31、1-R)**。`SontakuSignals` + `ParticularAngleMetadata` (nested) Pydantic 追加 + `src/analysis/particular_angle_extractor.py` 新規 (不変原則 4 例外条件 5 点充足適用、単一パス α、get_analysis_llm_client 経由) + 新ルート `_build_script_with_analysis_prompt` に metadata 渡し + main.py 分析ブロックで extractor 呼出 (model_copy で metadata 付与、run_analysis_layer 不変) + プロンプト改修 (LLM の知性に委ねる文言、誤り 9 回避) + `.env`/`.env.example` で `ANALYSIS_LAYER_ENABLED=true` production default 化。試運転 (1 fresh batch + 1 run、Path A pure) で Slot-1 が全 X1 必須目的達成 (新ルート起動 + target_enemy=None + stream_2_perspective_gap + sontaku.level=high/diplomatic + used_fallback=false / retries=0 / char validation passed + max_tokens 4096 で JSON 切断ゼロ)。axis_5 カズヤ採点で CP-3 = W1 完全成功。F-analysis-max-tokens-tune 統合完了。baseline 1432 → 1466 passed。詳細は `docs/runs/F-particular-angle-metadata-production-wire/REPORT.md`。
  - (旧エントリ参考、★ 履歴) 背景: F-particular-angle-redesign-extension (2026-05-08) で `particular_angle_metadata` (3 要素 + confidence) + `sontaku_signals` (level + type + extraction_confidence) を別軸メタデータとして正典化、`docs/PARTICULAR_ANGLE_DEFINITION.md` セクション 3.7 で台本表現方向性も正典化したが、**src/ 配下 grep で 0 件 = 本番未配線**。F-trial-run-post-tune Slot-1 (cls-6889e9e1c7ac、editorial_mission_score=86.0、Hydrangea ど真ん中) でも `analysis_result=null` で旧ルート + F-13 隠れ層 bypass で台本生成 = 新ルート `generate_script_with_analysis` 未起動。
  - ★ **target_enemy 解消の統合 (X1、F-script-writer-target-enemy-fix-investigate / 2026-05-26 CP-1 確定)**: 同調査で「production 稼働中の旧ルートが `target_enemy` (仮想敵) を出力し viewer-facing な煽り framing を誘導するが旧ルートは不変原則 2 で修正不可、新ルートは設計上既に target_enemy 排除済み」と判明 (真因 a)。→ 本配線バッチ完了 = 新ルート起動 = **target_enemy が production から自動退役**。本配線の成果検証項目に「video_payload.json で target_enemy が None になること (新ルート経由)」+「hook/punchline から仮想敵 framing・煽り表現が消えること」を追加する。詳細は `docs/runs/F-script-writer-target-enemy-fix-investigate/REPORT.md`。
  - 対応案: (a) `src/shared/models.py` に `ParticularAngleMetadata` + `SontakuSignals` Pydantic クラスを追加、`AnalysisResult` に optional フィールドとして組み込む (新規追加のみ、不変原則 4 例外条件適用要)、(b) `src/analysis/` 配下に LLM 抽出ロジック (`scripts/extract_particular_angle.py` のロジックを `src/analysis/particular_angle_extractor.py` に移植)、(c) `src/generation/script_writer.py` `generate_script_with_analysis` 新ルートの引数に追加、(d) `configs/prompts/analysis/geo_lens/script_with_analysis.md` に `particular_angle_metadata` + `sontaku_signals` を渡すプロンプト改修 (LLM の自律判断に委ねる設計、クラウド誤り 9 各論コントロール回避)
  - ★ **Editorial Guardian (gemini-3.1-pro-preview) 配線は後続** (F-gemini-quality-tier-poc / 2026-05-27): 最終布陣 v2 では Editorial Guardian を配線せず QUALITY/ARTICLE/LIGHTWEIGHT の 3 群のみ配線した。高リスク事実検証専用の Editorial Guardian (gemini-3.1-pro-preview、RPD 250、局所使用) の配線判断は本 X1 では行わず、「第一作公開前の高リスク事実検証ワークフロー」バッチ (緊急度 中、ADR-0003 由来) で実施する。
  - 検討時期: verify_two_stage 本番配線と同時 OR Phase A.5-3b 第一作着手後の並走バッチ。F-stream-2-filter-design は本配線を前提に動作する設計が望ましい。
  - 想定工数: 8-16 時間 (model 追加 + analysis 配線 + script_writer 新ルート改修 + プロンプト改修 + テスト + 試運転)
  - 関連ファイル: `src/shared/models.py` (★ ★ AnalysisResult 拡張)、`src/analysis/particular_angle_extractor.py` (新規想定、`src/analysis/` 不変原則 4 例外要)、`src/generation/script_writer.py` (新ルート `generate_script_with_analysis` 拡張)、`configs/prompts/analysis/geo_lens/script_with_analysis.md` (プロンプト改修)、`docs/PARTICULAR_ANGLE_DEFINITION.md` (正典)
  - 関連: F-particular-angle-redesign-extension (正典化バッチ)、verify_two_stage 本番配線判断 (関連 task)、F-stream-2-filter-design (本配線で sontaku_signals.level を参照する設計)

- **F-stream-2-filter-design 責務範囲再評価 (本番運用視点反映)** (F-trial-run-post-tune / 2026-05-11 で論点強化)
  - 背景: F-trial-run-post-tune で has_jp_coverage=True 3/3 = 全 Slot が divergence ルートに進行、blind_spot_global ルートが機械判別で消滅した。F-stream-2-filter-design は本来「系統 3 (framing_inversion) のみ + sontaku_signals.level を解説価値判定の追加軸として参照」というスコープに縮減されていたが、本番実挙動を踏まえると **Hydrangea ブランドメッセージ (『日本未報道』) の維持には F-stream-2-filter-design 二段階フィルタが不可欠** であることが顕在化。stream_3 過剰検出問題 ((d)) と合わせて責務範囲を再評価する必要あり。
  - 対応案: F-stream-2-filter-design 着手時に、本バッチで観察された「divergence ルートに流れた Slot-1 (Hydrangea ど真ん中) を救出する仕組み」を責務範囲として組み込む。具体的には、divergence ルート上の事象に対しても「特定角度は日本未報道」判定を行い、F-1 EditorialMissionFilter の judgment を信頼する場合は blind_spot_global 様の処理に切り替えるロジック (= 二段階フィルタの第 1 段で broad coverage が判定された後、第 2 段で perspective_gap を判定する設計)
  - 検討時期: F-stream-2-filter-design 着手判断と同時 (★ verify_two_stage 本番配線判断 + particular_angle_metadata 配線判断と密接に関連)
  - 想定工数: F-stream-2-filter-design 本体 + 1-2 時間 (本観察事項の反映)
  - 関連ファイル: F-stream-2-filter-design 範疇全般
  - 関連: verify_two_stage 本番配線判断、particular_angle_metadata + sontaku_signals 配線判断、F-jp-coverage-tune-followup-2

- **F-jp-coverage-tune-followup-2** ★候補 (F-jp-coverage-tune-followup / 2026-05-09 verdict=fail 残課題 (a) Recall 90% 突破 + (c) Tier 一致率 Grounding 非決定性、★ カズヤ判断後着手)
  - 背景: F-jp-coverage-tune-followup で WL マッチング階層判定化 + WL 拡張 3 ドメインで Recall covered 42.11% → **89.47%** (+47.36pp) 大幅改善 + F1 covered 0.5926 → **0.8718** で threshold 0.85 初突破。verdict は依然 fail だが、threshold 突破に一番近いのは Recall covered (0.53pp 不足)。残 FN 2 件のうち covered_003 (米中関税協議) は Grounding が政府系/研究機関/アグリゲータ偏重で日経・朝日等の主要メディアを引き当てられない典型ケースで、多クエリ並列発行で救済可能性が高い。
  - 想定対応軸 (★ カズヤ判断要、F-jp-coverage-tune-followup CP-3 で議論済):
    1. **(p) Grounding API 複数クエリ並列発行 + 結果統合** ★ Recall 90% 突破狙い
       - 1 イベントに対して複数の異なるクエリ表現 (元タイトル / 短縮タイトル / WL ドメイン名ヒント混入クエリ / 英→日翻訳クエリ) を並列発行し、結果を WL マッチングでマージ
       - Grounding API 1 クエリの 5-10 chunk 制限を「複数クエリで疑似的に拡張」する戦略
       - 期待効果: Recall covered 89.47% → 94.7%+ (covered_003 救済)、blind_010 (論考型) は構造的に救えない可能性高
       - 副作用リスク: Precision blind / Tier 一致率がさらに退行する可能性 (broader matching で FP 増加)
       - 想定工数: 4-6 時間 (実装 + テスト + 再測定)
    2. **(q) 検索 API 変更検討** (代替手段)
       - Google Custom Search API / Bing Search API への移行
       - dateRestrict / num=10 / siteSearch 等のパラメータが API レベルでサポート
       - 想定工数: 1-2 日 (検証 + 移行コスト + コスト見積もり)
    3. **(c) Tier 一致率の Grounding 非決定性対策** (Recall 90% 達成後の別軸論点)
       - 同 event でも回ごとに Grounding 返却 chunk 構成が揺れる、再現性問題
       - 対策候補: 複数回呼び出して集約 / Tier 優先度ロジックの変更 / Tier expectation を確率分布化
       - 想定工数: 1-2 日 (調査 + 設計議論)
  - 前提: F-jp-coverage-tune-followup の `measurement_result_step_c.json` + 23 件の per-event ログ + 残 FN 2 件分析 + 退行 FP 3 件分析が整備済み。`verify_two_stage` + `_match_whitelist` 階層判定 + WL 30 ドメインで安定動作確認済み。
  - 検討時期: F-jp-coverage-tune-followup 完了直後 (= 2026-05-09 直後)、★ カズヤ判断後着手
  - 関連ファイル: `src/triage/jp_coverage_verifier.py` (`_search_with_grounding_two_stage` の複数クエリ並列化 / 別 API 移行)、`scripts/measure_two_stage_accuracy.py` (再実行用)、`docs/runs/F-jp-coverage-tune-followup/` (Step C ベースラインデータ)
  - 関連: F-jp-coverage-tune-followup REPORT (前バッチで作成)、F-jp-coverage-tune (前々バッチ verdict=fail 起点)、F-stream-2-filter-design ((d) Stream accuracy stream_3 過剰検出が責務範囲)、Phase A.5-3b 第二作 ((b) Precision blind 母数問題の根本治療)

- **F-stream-2-filter-design responsibilities (d) stream_3 過剰検出の組み込み検討** (F-jp-coverage-tune-followup / 2026-05-09 で顕在化)
  - 背景: F-jp-coverage-tune-followup Step C で WL 拡張 + 階層判定化により angle 検索も recall が上がり、stream_2 真値 18 件中 15 件が `stream_3_candidate` に誤分類 (Stream accuracy 27.27% → 9.09%)。DISCUSSION_NOTES 既存エントリ「2026-05-09: stream_3 過剰検出 — URL ドメインマッチが特定角度の粒度を区別できない定義レベルの限界」が顕在化したもの。
  - 対応案: F-stream-2-filter-design の責務範囲として「angle 検索の WL マッチ後に LLM 解説価値判定」を追加 (= 単なる WL マッチでは stream_3 確定せず、その記事内容が `particular_angle.core_question` を実際に扱っているか LLM 判定)。F-stream-2-filter-design はもともと系統 3 候補に対する解説価値判定を責務とするので、この 1 段を後追いで stream_2/3 境界判別にも使う設計拡張。
  - 検討時期: F-stream-2-filter-design 着手判断と同時 (★ Phase A.5-3b 第二作のサンプル拡充後に再評価)
  - 想定工数: F-stream-2-filter-design に 1-2 時間追加 (LLM 解説価値判定の入力/出力契約に angle 記事タイトル/スニペット追加)
  - 関連ファイル: `src/triage/stream_2_filter.py` (新規想定、F-stream-2-filter-design 範疇)、`docs/PARTICULAR_ANGLE_DEFINITION.md` (判定基準正典)
  - 関連: F-jp-coverage-tune-followup REPORT (前バッチで顕在化)、F-stream-2-filter-design (★責務スコープ要再評価)

- **(c) Tier 一致率の Grounding 非決定性対策** (F-jp-coverage-tune-followup / 2026-05-09 で観測強化)
  - 背景: F-jp-coverage-tune-followup Step C で Tier 一致率 62.5% → 30.77% (-31.73pp) 退行。母数が 8 → 13 に増えた (TP 増加で eligible 拡大) のも一因だが、同 event でも回ごとに Grounding 返却 chunk 構成が揺れる Grounding API の非決定性が支配的。例: covered_001 / covered_009 が前回 tier_1 → 今回 tier_3、covered_005 が前回 tier_4 → 今回 tier_1。
  - 対応案: (a) 複数回呼び出して chunk 集約 (重複除去 + Tier 優先度集計)、(b) Tier expectation を確率分布化して評価 (golden_set 側を「Tier 1 が含まれることが期待される」型に変更)、(c) Tier 優先度ロジック変更 (現状: Tier 1 → 4 priority break、案: 全 Tier 集計して max-Tier 採用)
  - 検討時期: F-jp-coverage-tune-followup-2 ((p) 多クエリ並列発行) と統合検討 OR 単独バッチ
  - 想定工数: 1-2 日 (調査 + 設計議論 + 実装 + 再測定)
  - 関連ファイル: `src/triage/jp_coverage_verifier.py` (`_match_whitelist` の Tier 優先度ロジック)、`scripts/measure_two_stage_accuracy.py` (Tier 一致率計算ロジック)、`docs/runs/F-verify-jp-coverage/golden_set.json` (expected_tier の定義変更)
  - 関連: F-jp-coverage-tune-followup-2 (★ (p) 多クエリ並列発行と統合検討候補)

- **議論余地 2 ドメイン (`arabnews.jp` / `chosunonline.com`) の WL 採用判断** (F-jp-coverage-tune-followup / 2026-05-09 で保留)
  - 背景: F-jp-coverage-tune-followup Step B で WL 拡張時の議論余地として保留。`arabnews.jp` (Arab News Japan、中東情報の貴重なソース) / `chosunonline.com` (朝鮮日報日本語版、韓国メディアを「日本のメディア」と扱うか議論余地)。WL 整備で大幅改善した今、追加効果は限定的 + 退行リスクあり (新追加で TN→FP 退行が 3 件発生した実例あり) で本バッチでは保留。
  - 対応案: F-jp-coverage-tune-followup-2 の議論内で同時判断 OR 単独で議論。判定 3 基準 (発行元独立性 / 取材リソース / 大手認知) で再評価。
  - 検討時期: F-jp-coverage-tune-followup-2 着手と同時 OR Phase A.5-3b 第二作のサンプル拡充後
  - 想定工数: 30 分 (議論 + 採用なら WL 追加 + テスト)
  - 関連ファイル: `src/triage/jp_coverage_verifier.py` (`JP_MEDIA_WHITELIST`)、`tests/test_jp_coverage_verifier_domain_extract.py` (採用なら追加テスト)
  - 関連: F-jp-coverage-tune-followup REPORT (本保留事項を記録)

- **F-stream-2-filter-design** ★最優先 (F-verify-jp-coverage-golden-fix / 2026-05-04 で派生、F-verify-jp-coverage-measure / 2026-05-05 で着手保留 → F-jp-coverage-improve / 2026-05-07 で再開条件更新 → ★ F-trial-run-post-fix / 2026-05-07 で着手 OK 状態に)
  - 背景: Hydrangea コアミッション系統 2 (報道差の背景解説) を担う 2 段階フィルタの第 2 段階を実装する。系統 1 (F-13.B) では「広範な事件は報道済み」と弾かれるが、特定の構造分析角度 (地政学・文化・政治の意図) が日本未報道で解説価値ある事象を捕捉する。F-verify-jp-coverage-golden-fix で 4 件 (blind_002/004/005/009) が系統 2 候補として stream_2_candidate メタ付きで識別済み。F-jp-coverage-improve (2026-05-07) 修正後の再測定では stream_2_candidate 4 件中 3 件が True 判定 (blind_005 のみ FN) と動作確認できた。F-trial-run-post-fix (2026-05-07) で試運転 7-K 過去動画化 3 件のうち 2 件 (Slot-1 FIFA / Slot-2 Mandelson) が典型的 stream_2_candidate パターンと判明 (Tier 1-2 報道済みだが MEE オリジナル角度は未報道) → 系統 2 ターゲットの実例が **golden set 4 件 + 試運転 7-K 2 件 = 6 件** に拡大。
  - ★ **責務スコープ要再評価 (2026-05-08 更新、F-particular-angle-redesign + extension)**: F-jp-coverage-improve で構造的不具合解消、F-trial-run-post-fix で本番動作確認済み。Phase A.5-3a-verify ゲート完了 (1-A〜1-D''' 全完了) で着手再開条件達成。F-particular-angle-design (2026-05-07) で「特定角度」概念の正典 docs + 25 件 LLM ベースアノテーションを整備、F-particular-angle-redesign (2026-05-08) で 4 分類化を実施した **結果、LLM 推定段階で stream_3 (旧 stream_2) が 0 件 / stream_2 (旧 stream_1_5) が 20 件という想定外分布が観測された**。F-particular-angle-redesign-extension (2026-05-08) で **系統名 1/2/3 整理 + sontaku_signals メタデータを別軸として独立化** し、本バッチの責務は **系統 3 (framing_inversion) のみ + sontaku_signals.level を解説価値判定の追加軸として参照** に縮減された。系統 2 (perspective_gap、旧 1.5) は F-jp-coverage-tune の二段階クエリ生成範疇に移行。本バッチ着手は ★ **F-particular-angle-redesign のカズヤレビュー (新分類 1/2/3 + sontaku_signals 込み) 結果を待ってから** 判断するのが望ましい。仮にカズヤレビュー後も stream_3 が 1-2 件しかない場合、本バッチは小規模実装で済み (新規 LLM 解説価値判定 1 段のみ + sontaku_signals.level の追加軸組み込み、ゴールデンセットも数件)、F-jp-coverage-tune が **より優先** される構造になる。
  - 共通基盤 (F-particular-angle-design / 2026-05-07 で確立):
    * 「特定角度」を判定単位として、系統 1 / 系統 2 / 対象外の 3 分類論理フロー (Step 1: 4 軸該当 → Step 2: 日本未報道 → Step 3: 解釈差) を `docs/PARTICULAR_ANGLE_DEFINITION.md` で正典化
    * 25 件アノテーション (LLM 推定段階で stream_2=13 件、内訳: blind_005 / blind_008 / covered 系列 9/10 件 / 7-K Slot-1 FIFA / 7-K Slot-2 Mandelson) が系統 2 候補の実例として準備済み
    * `scripts/extract_particular_angle.py` のプロンプト設計 (max_output_tokens=4096、3 要素 + confidence ラベル) が本バッチの解説価値判定 LLM の参考実装として使える
  - 対応案: (1) 既存の framing_inversion 軸 + multi_angle_analysis 5 観点 + media_divergence 観点を統合した「3 ソース対比ルール + 解説価値判定」を新規実装。(2) パイプライン位置は F-13.B の下流 (報道済み判定後)。(3) 系統 2 ターゲット候補に対して LLM が「特定角度の差が存在するか」「解説価値があるか (5 観点のいずれか)」を判定。判定単位は **「特定角度」(F-particular-angle-design で正典化)** に限定する設計を採用。(4) ゴールデンセット v1.2 の `stream_classification` 付き 19 件 + 試運転 6 件 (stream_classification.json) で精度測定。(5) 不変原則順守 (article_writer 変更不可、script_writer 既存ルート変更不可、src/triage/ 既存ファイル変更不可、src/analysis/ 変更不可、新規追加のみ)。
  - 検討時期: F-particular-angle-design 完了後、Phase A.5-3b 着手前 (★PoC は PoC に集中するため、フィルタを事前に確定)
  - 想定工数: 4-6 時間 (新規ロジック実装 + テスト + ゴールデンセット追加)
  - 関連ファイル: src/triage/stream_2_filter.py (新規想定), tests/triage/test_stream_2_filter.py (新規想定), docs/runs/F-stream-2-filter-design/ (新規, ゴールデンセット拡張 + 精度測定レポート), configs/prompts/analysis/geo_lens/ 配下 (3 ソース対比 + 解説価値判定プロンプトを新規追加), docs/PARTICULAR_ANGLE_DEFINITION.md (判定基準正典), docs/runs/F-particular-angle-design/annotations.json (アノテーション参照), docs/runs/F-particular-angle-design/stream_classification.json (系統分類)
  - 関連 DISCUSSION_NOTES: 「系統 1 (silence_gap) の判定基準明確化」「F-13.B 動作仕様の検討課題」「3 ソース対比ルール部分実装」「特定角度抽出の LLM 限界観察」

- **F-verify-perspective** (F-state-protocol-supplement / 2026-05-02 登録、F-doc-cleanup / 2026-05-03 順序見直し)
  - 背景: 4 軸 (cultural_blindspot / silence_gap / hidden_stakes / framing_inversion) のバランスを検証。DISCUSSION_NOTES #6 (F-12-B-2 axis 多様化) の着手判断材料となる。cultural_blindspot 偏重が確認されれば F-12-B-2 起動。
  - 対応案: 直近 50 イベントで axis 分布を集計、cultural_blindspot 偏重があれば F-12-B-2 起動判断。
  - 検討時期: Phase A.5-3b 着手後に並走でデータ収集、判断は 3b/3c 完了後 (データ収集性格、ゲートではない)
  - 想定工数: 集計 1 時間 + 判断議論
  - 関連ファイル: src/analysis/perspective_extractor.py (読み取りのみ), data/output/ の AnalysisLayer 出力

- **F-verify-script-quality** (F-state-protocol-supplement / 2026-05-02 登録、F-doc-cleanup / 2026-05-03 順序見直し)
  - 背景: 新ルート (`generate_script_with_analysis`) の NG パターン出現頻度 / char validation リトライ率を測定。F-12-B-1.5 (文字数制約緩和) 着手判断材料を兼ねる。F-12-B-1 投入後 1 run の試運転では setup 1/1 でリトライ発動だが標本不足。
  - 対応案: 直近 30 件で NG 語彙頻度 / リトライ回数集計、`_CHAR_BOUNDS` 調整可否を判断。
  - 検討時期: Phase A.5-3b 着手後に並走でデータ収集、判断は 3b/3c 完了後 (データ収集性格、ゲートではない)
  - 想定工数: 集計 1 時間 + 判断議論
  - 関連ファイル: src/generation/script_writer.py (読み取りのみ), data/output/ の script.json

- ~~**F-image-prompt-spec** ★スコープ再定義要 (F-doc-backfill / 2026-05-02 登録、F-trial-run-post-llm-extraction / 2026-05-16 でスコープ乖離判明、**F-image-prompt-spec / 2026-05-18 完了**、完了済みセクション参照)~~

- ~~**Phase A.5-3b 第一作起案**~~ ✅ **golden master 部分完了 (F-first-work-golden-master / 2026-06-11、完了済みセクション参照)**。残作業は下記「第一作 手動 PoC」に引き継ぎ。

- **第一作 手動 PoC (カズヤ手作業 + axis_5 採点)** (F-first-work-golden-master / 2026-06-11 起案、★ 第一作公開の最終工程)
  - 背景: golden master 素材一式 (script/article/analysis/video_payload/image_prompts 5 本) は
    `data/output/golden_master/` に凍結済み、validation 3 レポートと手修正対象リストは
    `docs/runs/F-first-work-golden-master/` に出力済み。道具 (Remotion テンプレート / tts_to_captions /
    編集→再検証ループ) も全部揃った。残りは人間にしかできない工程のみ。
  - 対応案: `docs/golden_master_spec.md` §4 チェックリストに従う = flag レビュー + `*_edited.*` 編集 →
    ガード 3 本再実行ループ → ElevenLabs 実生成 → captions 変換 → 画像 3 候補比較 (Nano Banana Pro /
    GPT Image 2 / Flux 2 系に同文投入) → BGM 用意 → Remotion 実素材レンダ → axis_5 採点 →
    公開判断 (公開可否バー + ADR-0003 チェックリスト + AI 開示ラベル必須)。
  - ★ 特に: c6 (日本郵船/伊藤忠 = analysis 由来の企業主張) は corroborated になるまで公開に乗せない /
    punchline 尻切れの手修正 / platform_title silence 表現の手修正。
  - 検討時期: 即時 (バッチ完了直後から着手可)
  - 関連ファイル: `docs/golden_master_spec.md` (正本)、`data/output/golden_master/`、
    `docs/runs/F-first-work-golden-master/`、`manual_poc/`

### Phase A.5-3c 合成パート自動化 (F-doc-backfill / 2026-05-02 登録)

- **F-elevenlabs-integration** (F-doc-backfill / 2026-05-02 登録)
  - 背景: Phase A.5-3b 手動 PoC で確定した ElevenLabs 声選定を、Hydrangea 自動パイプラインに統合する。macOS say は廃止 (品質低い、Linux 対応の意義なし)。
  - 対応案:
    (1) AudioRenderer 抽象クラス化 (src/generation/audio_renderer.py 改修)
    (2) ElevenLabsRenderer 実装 (API キー + voice_id 設定 + character_alignment 取得)
    (3) configs/audio.yaml で声選定 (geo_lens / japan_athletes / k_pulse 別)
    (4) 既存 say 呼び出し部分を ElevenLabsRenderer に切り替え
    (5) フィーチャーフラグで段階移行 (AUDIO_RENDERER=elevenlabs|say)
  - 検討時期: Phase A.5-3b 完了直後 (声選定確定後)
  - 想定工数: 1 週間
  - 関連ファイル: src/generation/audio_renderer.py, configs/audio.yaml (新規)
  - 不変原則整合: audio_renderer.py は不変原則 1-4 の対象外、改修可能
  - 補足: TECH_DEBT 2.5 (macOS say 依存) は本エントリで解消

- **F-image-gen-integration** (F-doc-backfill / 2026-05-02 登録、F-doc-backfill-supplement / 2026-05-02 改訂)
  - 背景: Phase A.5-3b で選定した画像生成ツール (Nano Banana Pro / ChatGPT Images 2.0 (gpt-image-2) / Flux 1.1 Pro のいずれか) を Hydrangea パイプラインに統合。
  - 対応案:
    (1) ImageGenerator 抽象クラス化 (src/generation/ に新規作成)
    (2) 選定ツールの API クライアント実装
    (3) シーンごとの画像生成ロジック (12-15 枚 / 80 秒動画)
    (4) configs/image_gen.yaml で統一プロンプト末尾 + チャンネル別設定
    (5) 著作権配慮 (Wikimedia Commons + 政府公開画像 + Pexels + AI 生成の組み合わせ、通信社画像は使わない)
  - 検討時期: F-elevenlabs-integration と並行可
  - 想定工数: 1 週間
  - 関連ファイル: src/generation/image_generator.py (新規), configs/image_gen.yaml (新規)
  - 不変原則整合: 新規ファイル追加で既存に影響なし

- **F-video-compose-integration** (F-doc-backfill / 2026-05-02 登録)
  - 背景: Phase A.5-3b で確立した Remotion テンプレートを自動化に適用。現状の Pillow + FFmpeg ベース video_renderer.py は廃止。
  - 対応案:
    (1) Remotion プロジェクトを Hydrangea リポジトリに統合
    (2) Python パイプラインから Remotion CLI を呼ぶブリッジ実装
    (3) 各チャンネル別 Remotion テンプレート (geo_lens 用、後で japan_athletes / k_pulse 用追加)
    (4) Remotion Lambda for 並列レンダリング (Phase B で本格化)
    (5) フィーチャーフラグで段階移行 (VIDEO_RENDERER=remotion|legacy)
  - 検討時期: F-elevenlabs-integration / F-image-gen-integration 完了後
  - 想定工数: 2-3 週間
  - 関連ファイル: remotion/ (新規), src/generation/video_renderer.py (廃止予定), configs/remotion/ (新規)
  - 不変原則整合: video_renderer.py は不変原則 1-4 の対象外、廃止可能

- **F-cron** (F-doc-backfill / 2026-05-02 登録)
  - 背景: 現状はカズヤ手動実行のみ。本番リリース後は 1 日 4 動画 + 12 記事の自動生成が必要。F-16-B (旧 cron 計画) を ElevenLabs / Remotion 前提で再定義。
  - 対応案:
    (1) .github/workflows/hydrangea-pipeline.yml 新規
    (2) cron: 6 時間おき (00:00, 06:00, 12:00, 18:00 JST)
    (3) GitHub Secrets 設定 (GEMINI_API_KEY / ELEVENLABS_API_KEY / 画像生成 API キー / その他)
    (4) ロギング (実行結果を GitHub Issue or Slack に通知、run_summary.json を artifact 保存)
    (5) 環境変数: AUDIO_RENDERER=elevenlabs, VIDEO_RENDERER=remotion
  - 検討時期: F-elevenlabs-integration / F-image-gen-integration / F-video-compose-integration 完了後
  - 想定工数: 2-3 時間
  - 関連ファイル: .github/workflows/hydrangea-pipeline.yml (新規)
  - 不変原則整合: .github/ 配下は src/ 外、既存テスト破壊なし

### Phase A.5-3d 投稿前ゲート + 自動投稿 (F-doc-backfill / 2026-05-02 登録、F-doc-backfill-supplement / 2026-05-02 改訂)

- **Phase A.5-3d 投稿前ゲート + 自動投稿** (F-doc-backfill / 2026-05-02 登録、F-doc-backfill-supplement / 2026-05-02 改訂)
  - 背景: F-cron 完了で「動画自動生成」が動くが、品質保証ゲートと投稿自動化が未実装。
  - 対応案:
    (1) F-publish-gate: 投稿前ゲート実装
        - LLM 自己採点 7 軸 (Hook 強度 / 情報密度 / 価値観揺さぶり / 具体性 / 感情ドライブ / 共有動機 / ループ性、各 3.5 点以上で通過)
        - 文字化け検知 (字幕に不正文字)
        - 無音検知 (音声ファイルの音量ゼロ区間)
        - 不通過はレビューキューに退避、カズヤが定期的に確認
    (2) F-tiktok-api: TikTok Content Posting API 統合 (審査 1-3 週間、早めに申請)
    (3) F-youtube-api: YouTube Data API v3 統合 (即対応可)
    (4) 投稿開始
  - 投稿対象: geo_lens (政治・経済) のみ。japan_athletes / k_pulse は Phase B 以降に判断 (運用結果次第、DISCUSSION_NOTES「Phase B 以降の方向性未確定」参照)
  - 投稿先: TikTok と YouTube Shorts の両方同時 (TikTok は審査 1-3 週間あるので早めに申請、YouTube Data API v3 は即対応可で先行リリース可)
  - 投稿モード: 完全自動投稿 (cron 6 時間おき、人手介入ゼロ)
    - 投稿前ゲート (LLM 自己採点 7 軸 + 文字化け検知 + 無音検知) で品質保証
    - 不通過はレビューキューに退避、定期的にカズヤが確認
  - 拡張性確保: Phase A.5-3c の合成パート自動化実装時、将来の多チャンネル対応 / 別形式展開 (動画以外、独自メディア等) を阻害しない設計とする (configs/channels/{channel_id}.yaml で投稿先 / 形式 / カテゴリを切替可能に。DECISION_LOG「拡張性原則の明文化」参照)
  - 検討時期: F-cron 完了 + 1 週間の自動実行安定確認後
  - 想定工数: 2-3 週間 (TikTok 審査含む)
  - 関連ファイル: src/publishing/ (新規)
  - 不変原則整合: 新規ディレクトリ追加で既存に影響なし

---

## 緊急度 中（実運用データ収集後に判断）

---

- **F-title-generator-stream-aware-fix** (F-title-guard-coverage-claim-policy / 2026-06-08 CP-1 起案、仮説 1 訂正由来)
  - 背景: 1-Q.5 CP-1 で確定 = `src/generation/title_generator.py` の silence 絶対表現
    「日本では報道されない{topic}(の視点)」(`_platform_title_candidates` L136/149/203) + サムネ
    「日本で無報道」(L380/394) は **決定的合成のハードコード template** で、`is_strong` evidence
    ヒューリスティクス (`_is_strong_evidence` L41-72、`perspective_gap_score>=3.0` でも真) で選択される。
    stream_classification を一切参照しないため、**perspective_gap / framing_inversion でも silence
    絶対表現が出る**。1-Q.5 では guard (Layer 3、flag のみ) が安全網になったが、**根本 (生成時に
    stream に応じて silence template を抑制) は未対処**。Layer 1 プロンプト原則は title が LLM 非経由の
    決定的合成のため届かない。
  - 対応案: `title_generator.py` の `is_strong → silence template` 選択を stream-aware にする
    (例: perspective_gap / framing_inversion では silence 絶対 candidate を非選択、coverage_claim_policy
    の allowed_claim_level を参照)。★ title_generator.py は不変原則対象外だが本体改修のため最小改変 +
    既存テスト保護。各論の言い回し強制ではなく「事実に反する template を選ばない」構造選択に留める
    (クラウド誤り 9 回避)。selected_pattern / stream の橋渡しが必要 (現状 title 生成に stream 未伝播)。
  - 検討時期: 第一作 (1-S) で guard の flag 挙動を観測してから判断 (flag が多発 = 根本修正の価値が高い)。
  - 関連ファイル: `src/generation/title_generator.py`、`src/generation/script_writer.py` (title 生成呼出時の
    stream 伝播)、`configs/coverage_claim_policy.yaml`、`src/generation/coverage_claim_guard.py`
  - 関連: F-title-guard-coverage-claim-policy (guard = 暫定安全網)、クラウド誤り 9

- **F-periodic-health-check** (F-trial-run-candidate-a-reverify / 2026-05-19 起案、F-gemini-model-audit / 2026-05-19 で緊急度 高 → 中に降格、カズヤ確認済)
  - 背景: Phase A.5-3d は cron 6 時間おきの完全自動投稿 (人手介入ゼロ)。F-trial-run-candidate-a-reverify で Gemini 503 多発 → Slot-1 台本 fallback 落ちが起きたように、無人運用では Gemini 503 / Grounding 0 件 / fallback 落ち等の品質劣化を検知する仕組みが前提として必要。
  - 降格理由 (F-gemini-model-audit / 2026-05-19): 本番リリース前は不要。Phase A.5-3d cron 自動投稿実装時に着手すれば足りる (カズヤ確認済)。
  - 対応案: production パイプライン全工程 (RSS 取得 / GarbageFilter / clustering / F-1〜F-13.B / 台本生成 / video_payload) の定期ヘルスチェック。fallback 発生率 / Gemini 503 率 / Grounding ヒット率 / 防衛機構各層の通過数を集計し閾値逸脱時にアラート。run_summary.json への health フィールド追加 + 集約レポート。
  - 検討時期: **Phase A.5-3d 着手時** (cron 完全自動投稿の前提、本番リリース前は不要)
  - 着手条件: Phase A.5-3d 着手
  - 関連ファイル: src/main.py, src/budget.py, data/output/run_summary.json
  - 関連: F-gemini-model-migrate-emergency (503 多発の根本治療)、Phase A.5-3d (cron 完全自動投稿の前提)
  - ★ 追加スコープ (ChatGPT Round 2 レビュー / 2026-05-27 指摘 5 統合、F-docs-update-chatgpt-round2-and-error10。★ 起案プロンプトは本タスクを「F-pipeline-health-check (1-Q.5)」と呼称したが該当エントリは存在せず、health-check の正本は本 F-periodic-health-check のため本エントリにスコープ統合):
    - **model_role 解決状況の runtime snapshot (tier fallback 検出)**: factory.py の Tier1/2/3 解決経路を 1 batch 試運転で trace し、tier fallback (Gemini 503 等で primary → 下位 Tier に落ちる事象) が発生したかを観測。直近 run_summary では `used_fallback` / `model_roles` を記録済 = これを health フィールドに集約。
    - **BudgetTracker の retry count 観測強化 (factory tier fallback の見える化)**: TieredGeminiClient.generate() 内部の tier retry が budget 記録に反映されているか観測 + 必要なら最小修正案を CP で起案。
    - 工数 +1-2h (合計 3-5h、元の本番リリース前不要スコープから観測強化分を加算)
    - ★ ChatGPT 指摘の懸念: 「Gemini 503 / fallback が第一作品質に直撃している状況では、どの tier が何回落ちたかが見えないと診断しづらい」= Phase A.5-3b 第一作の事故率を下げるための観測強化。
  - 関連 (追加): ChatGPT Round 2 レビュー (2026-05-27 指摘 5)、F-gemini-quality-tier-poc (1-Q、tier 選定と並走)
  - ★ 追加スコープ (X1 / F-particular-angle-metadata-production-wire / 2026-05-31 統合):
    - **run 間分散統計の観察** = 同一 batch を時間差で 2 回以上処理し、particular_angle_metadata の `stream_classification` / `sontaku_signals.level` / `extraction_confidence` の run 間ブレを集計。X1 試運転は 1 batch・1 run のみで実施 (3 回処理は scaffolding が本番状態を歪めるため不採用)、本観察は実運用で時間差 fresh batch が貯まる Phase A.5-3d 着手時に統合する。
    - 工数 +1-2h (上記 health snapshot 拡張と並走実装で吸収)
  - 関連 (追加): X1 (run 間分散統合先)

- ~~**F-analysis-max-tokens-tune** ★中 (ChatGPT Round 2 レビュー / 2026-05-27 起案)~~ → ★ **完了 (F-particular-angle-metadata-production-wire / 2026-05-31、1-R で統合配線)**。`.env` / `.env.example` で `ANALYSIS_LLM_MAX_TOKENS=2000→4096` に更新。factory.py:516 のコード改修は不要 (env で吸収、`get_analysis_llm_client()` が `os.getenv("ANALYSIS_LLM_MAX_TOKENS", "2000")` を読み込む現行実装で 4096 が直接反映)。試運転で particular_angle_extractor + perspective/insight 抽出いずれも JSON 切断ゼロを確認。

- **F-script-punchline-tail-cut-investigate** ★中 (F-particular-angle-metadata-production-wire / 2026-05-31 起案、X1 試運転で観察)
  - 背景: X1 試運転 Slot-1 (cls-c8876d474612) の punchline 末尾「これは遠い国の出来事ではありません。毎月届く電気代の請求書こそが、ルールが機能しない世界で私たちが支払うことになる、冷徹なツケの現場なのです。そこから繋がるのが、」で文未完結。`char validation passed` (punchline=81 字、規定 70-110 内) のため文字数バリデーションでは検知されない構造。loop_mechanism=`loop-2` (連鎖含意で次パートに繋ぐ意図) の仕様か、LLM 生成バグかの切り分けが必要。
  - 対応案: (a) 調査専用バッチで loop-1/2/3 の各仕様を script_writer prompt + Pydantic schema から精読、(b) `_validate_analysis_draft_chars` 等の検証パスで「文末閉じ確認」(例: 「、」/「が、」/「のが、」で終わる場合の警告) を追加するか判断、(c) loop-2 が「次パートへの引き継ぎ」を意図しているなら仕様どおりだが、production output に未完文が残る品質懸念は残るため別途対処
  - 検討時期: Phase A.5-3b 第一作起案前か並走 (第一作の punchline 品質直結)
  - 想定工数: 2-3 時間 (調査 + 必要なら最小修正)
  - 関連ファイル: `src/generation/script_writer.py` (新ルート punchline 生成 + loop_mechanism)、`configs/prompts/analysis/geo_lens/script_with_analysis.md` (loop_mechanism プロンプト仕様)
  - 関連: X1 試運転実証、Phase A.5-3b 第一作品質
  - ★ **標本 2 例目** (F-first-work-golden-master / 2026-06-11): 候補A golden master でも
    punchline 末尾「…地政学の歪みを生活実感として突きつける、あの」で未完結 (loop-2、
    char validation passed 87 字)。X1 Slot-1 と完全同型 = **loop-2 × 尻切れの再現性が確認された**。
    調査優先度を裏付ける標本。第一作は手修正で対処 (golden_master_spec §3)。

- **F-trial-data-procurement-protocol** ★中 (F-particular-angle-metadata-production-wire / 2026-05-31 起案、X1 試運転 blocker 4 連鎖から起案)
  - 背景: X1 試運転で blocker 4 連鎖を経験 = (1) sample mode は分析レイヤーブロックを通らない (`run_from_normalized` のみ) → 新ルート未起動、(2) スタール normalized データ (2026-04-27 の 5 週間前) で GarbageFilter `_MAX_AGE_HOURS=48` に全弾かれ → 0 events 処理、(3) 同一 RSS state では duplicate URL ばかりで複数 fresh batch を連続作成できず、(4) 試運転用 fresh データ確保手段 (cron / batch-prefetch / mock-fresh) が PoC 未整備。X1 は「ingestion + 1 run」で本番状態維持しつつ Path A pure で凌いだが、後続バッチ (Phase A.5-3b 第一作 / 1-Q.5 title guard / 1-T 高リスク事実検証) で同様の試運転需要が再発する確率高。
  - 対応案: (a) 試運転実行手順のドキュメント化 (CLAUDE.md or 新 `docs/TRIAL_RUN_GUIDE.md`、sample/normalized mode の選択基準 + ingestion → batch_id 確認 → run → snapshot のテンプレ手順)、(b) GarbageFilter `_MAX_AGE_HOURS` を env tunable 化検討 (★ 不変原則 3 例外条件適用要、対症療法か根本治療かの判断)、(c) stuck batch の安全な再処理スクリプト (`scripts/replay_stuck_batch.py` 新規) で archive 復元 + status reset + snapshot を 1 コマンド化、(d) 試運転前提の最小データセット (5-10 events 固定、analysis_result 含む) を `data/fixtures/` に整備し sample mode の analysis 経路を強化
  - 検討時期: Phase A.5-3b 第一作着手前 (再発リスク回避のため早期着手推奨)
  - 想定工数: 3-5 時間 (手順化 + 最小スクリプト整備、env 化は別途判断)
  - 関連ファイル: `src/main.py` (sample/normalized mode 分岐、★ 不変原則対象外)、`src/ingestion/run_ingestion.py` (ingestion パス、★ 不変原則対象外)、`src/triage/garbage_filter.py` (★ 不変原則 3 保護)、新規 `scripts/replay_stuck_batch.py` / `docs/TRIAL_RUN_GUIDE.md`
  - 関連: X1 (本起案元)、F-periodic-health-check (production 観測との対比)、Phase A.5-3b 第一作 / 1-Q.5 / 1-T (再発リスク回避先)

- **F-guardian-production-wire: Guardian 2 層の production 配線 + Phase A.5-3d 投稿前ゲート統合** ★中 (F-editorial-guardian-corroboration / 2026-06-10 起案、第一作後)
  - 背景: 1-T.1 + 1-T.2 で Editorial Guardian 2 層 (忠実性 + 真実性) が手動ランナー 2 本
    (`scripts/run_editorial_guardian.py` → `scripts/run_editorial_guardian_corroboration.py`)
    で完成した。第一作 (1-S) は手動運用だが、Phase A.5-3d (cron 完全自動投稿) では投稿前
    ゲートのチェックリスト 6 項目 (ADR-0003) の「6. 高リスク事実: 公開前検証完了済みか」を
    機械判定に組み込む必要がある。
  - 対応案: (a) main.py 生成 dispatch 後の Guardian 2 層自動実行 (非ブロッキング観測 →
    ブロッキング gate の段階導入、coverage_claim_guard の production 配線判断と並走)、
    (b) budget.py 経由化 (1-T.1 判断 5 で手動運用のため見送った分)、(c) flagged_claims
    非空時の投稿保留フロー (公開可否バー = supported × corroborated のみ通過を gate 化)。
    レポート層の統合 (coverage_claim_guard + Guardian を 1 レポートに束ねる) は
    DISCUSSION_NOTES 2026-06-10 ② の整理に従い判定ロジックは統合しない。
  - 検討時期: 第一作 (1-S) で手動運用の運用感を観測後、Phase A.5-3d 着手時
  - 想定工数: 3-5 時間 (配線 + gate 化判断 + budget 統合)
  - 関連ファイル: `src/main.py`、`src/generation/editorial_guardian.py` /
    `editorial_guardian_corroboration.py`、`src/budget.py`、`scripts/run_editorial_guardian*.py`
  - 関連: 1-T.1 / 1-T.2 (実装元)、Phase A.5-3d 投稿前ゲート (統合先)、
    F-coverage-claim-guard-auto-action (並走判断)、F-periodic-health-check (無人運用の前提)

- **F-grounding-determinism-audit** (F-jp-coverage-llm-judgement-extraction / 2026-05-16 で起案)
  - 背景: F-jp-coverage-llm-judgement-extraction Task E-fix-F 再々測定で、ゴールデンセット live-API 計測が **run 間で broad Grounding API の WL メディアドメイン返却が大きく変動** することが顕在化。v3 run では 11 件の reported event で WL ヒット 0 (うち Gemini 503 が 2) = B-3' 判定以前に False に倒れ、ヘッドライン Recall を 0.4706 まで薄めた (WL マッチ条件下では Recall 1.0000 = B-3' 自体は設計通り機能)。同一クエリでも Task E run と v3 run で WL ヒット有無が反転する event 多数 (例: covered_008/009)。
  - 対応案: (a) 同一ゴールデンセットを N 回 (3-5 回) 連続再測定し WL ドメイン返却率の run 間分散を定量化、(b) 集約戦略の検討 (複数 run の OR / 多数決 / response_text 優先等)、(c) Gemini 503 リトライ強化の費用対効果評価、(d) 別 API 移行検討 (F-jp-coverage-tune-followup-2) との統合可否判断。
  - 検討時期: Phase A.5-3b 第二作と並走可 (カズヤ判断)、F-trial-run-post-llm-extraction の本番試運転で再現性が確認されたら優先度再評価
  - 想定工数: 4-8 時間 (連続再測定 N 回 + 分散分析 + 集約戦略 PoC)
  - 関連ファイル: `scripts/measure_two_stage_accuracy.py`、`docs/runs/F-jp-coverage-llm-judgement-extraction/measurement_result_v3.json` (分散観察元)、`docs/runs/F-jp-coverage-llm-judgement-extraction/REPORT.md` §4.3
  - 関連: F-jp-coverage-llm-judgement-extraction (分散顕在化元)、F-jp-coverage-tune-followup-2 (別 API 移行統合候補)、ゴールデンセット v2 化検討 (評価軸整備で並走)

- **F-12-B-1.5: 台本 4 ブロック文字数制約の緩和判断** (F-12-B-1 / 2026-05-01 発生)
  - 背景: F-12-B-1 (視聴者ファースト原則追加) により「聞き慣れない固有名詞には最小限の補足を添える」原則が導入された結果、setup ブロックの char validation で 1 リトライが発生 (94 字 → 82 字)。LLM が補足を入れようとして既存制約 (setup 60〜90 字 / twist 150〜220 字 / punchline 70〜110 字) の上限に当たりやすくなる傾向が試運転で確認された。
  - 対応案: (a) リトライ発動頻度を継続観察し、頻発するなら setup 上限を 100 字、twist 上限を 240 字、punchline 上限を 120 字程度に緩和。(b) `src/generation/script_writer.py` の char validation 範囲定数を調整 (script_writer.py 自体は不変原則 2 の対象だが、定数調整は最小改変で許容範囲)。(c) または estimated_duration_sec の許容幅を広げて 80→90 秒運用に移行。
  - 検討時期: F-12-B-1 投入後 5〜10 run の動画化で char validation リトライ率を集計。全 Slot の 30% 以上でリトライが発動するなら緩和着手。現状 (試運転 1 run) は 1/1 で発動したが標本不足のため判断保留。
  - 関連ファイル: src/generation/script_writer.py, configs/prompts/analysis/geo_lens/script_with_analysis.md (文字数指示部)

- **Reality Check Layer (F-10 候補): 「日本で本当に報じられていないか」の検証工程** (F-5 発生)
  - 背景: 現状の blind_spot_global_score は LLM の主観判断であり、実際に日本のメディアをチェックする工程が無い。Hydrangea のコンセプト「日本で報じられない海外ニュースを届ける」の信頼性に直結する。
  - 対応案: editorial_mission_filter 通過後 / EliteJudge 前に「Reality Check Layer」を挿入。LLM ベースの判定（短期）または Web 検索 API ベースの検証（長期）で「実際に日本メディアで報じられていないか」を確認する。
  - 検討時期: F-9 (チャンネル定義 YAML 化) 完了後
  - 関連ファイル: src/triage/, src/main.py, configs/channels.yaml

- **EditorialMissionFilter 閾値の調整** (F-1 で暫定値設定)
  - 背景: F-1 では閾値 45.0 を暫定値として設定。実運用データが溜まったら通過率と選定品質を分析して調整
  - 対応案: 1週間以上の運用データ（通過率・選ばれた記事の質）を分析して閾値を 40〜55 の範囲で再設定
  - 検討時期: F-1 投入後 1〜2週間

- **scoring.py の新 axis 追加** (F-1 設計時に判断)
  - 背景: F-1 で political_intent / hidden_power_dynamics / economic_interests を Step1 で精密計算したいが、scoring.py が触っちゃダメリストにあるため Step2 LLM のみで判定
  - 対応案: 触っちゃダメリスト見直し後、editorial:political_intent_score 等の新 axis を追加して Step1 prescore に組み込む
  - 検討時期: 触っちゃダメリスト見直し後

- **台本品質のアーティクル品質への引き上げ (F-12 候補)** (試運転7-D 発生 / **進行中: F-12-A 完了 / F-12-B 残**)
  - 背景: アーティクル (article.md) は Foreign Affairs 級の名フレーズと深い分析が出るが、台本 (script.json) は文字数制約とブロック分割で表現が硬くなりがち。アーティクルが「移動する主権領土」のような独自言語化を含むのに対し、台本は「物理的限界に達している構造的変化を象徴」のような平凡な表現になる。
  - 対応案:
    - 案A: アーティクル先行生成 → 台本に圧縮 (順序変更) **← F-12-A で実施済み (2026-04-29)**
    - 案B: アーティクルから「金フレーズ」抽出ループ (台本生成時に必ず使う制約) **← F-12-B で実施予定**
    - 案C: 台本のターゲット視聴者明確化 (ReHacQ・PIVOT 視聴層を想定) **← F-12-B で script_writer プロンプト全面刷新時に統合**
  - F-12-A 完了内容: src/main.py の生成順序を `script → article` から `article → script` に逆転。article.markdown を script_writer に `article_text` 引数で参照素材として渡す基盤を整備。article_writer.py は不変（プロンプト・シグネチャ・入力素材いずれも touch していない）。
  - F-12-B 残作業: script_writer プロンプト全面刷新（サマリ型台本 / AI 構文排除リスト / アーティクル独自言語化フレーズの強制使用）。
  - 検討時期: F-12-B は試運転 7-F でアーティクル品質維持を確認後に着手
  - 関連ファイル: src/generation/script_writer.py, src/generation/article_writer.py, src/main.py

- **LLM 結果キャッシュ（E-4）** (Phase 1.5 計画)
  - 背景: 同じ event を2回評価しないようにキャッシュ。デバッグ高速化
  - 対応案: キャッシュキー = event.id + sources_hash + prompt_template_hash
  - 検討時期: E-3' 完了後

- **judge バッチ化（E-3 元案）** (Phase 1.5 計画)
  - 背景: viral/elite/gemini judge を1回の LLM 呼び出しに統合。ただし役割分離は維持
  - 対応案: 各 judge を別プロンプトでバッチ化、統合はしない
  - 検討時期: E-4 完了後

- **FUTURE_WORK.md 月次レビュー** (FW-1 で導入)
  - 背景: 形骸化防止のため、月初または「気のいいタイミング」で全項目を見直す
  - 対応案: 緊急度の再評価、放置項目（高で1ヶ月以上未対応）の対応開始判断、完了済みの整理、新規バッチへの組み込み判断
  - 検討時期: 毎月1日 + 以下のイベントトリガー時
    - 新しい Phase の開始前
    - 主要バッチ完了直後
    - カズヤが「次何やる？」と問うたタイミング
    - 1週間以上 FUTURE_WORK.md が参照されていないと気づいた時
  - 関連ファイル: docs/FUTURE_WORK.md, CLAUDE.md
  - 補足: このレビュー自体も FUTURE_WORK.md の項目として登録されている（自己参照型管理）

### Phase A.5-3b 手動 PoC: Remotion + ElevenLabs + 画像生成 (F-doc-backfill / 2026-05-02 改訂、F-doc-backfill-supplement / 2026-05-02 再改訂)

- **Phase A.5-3b 手動 PoC: Remotion + ElevenLabs + 画像生成** (F-doc-backfill / 2026-05-02 改訂、F-doc-backfill-supplement / 2026-05-02 再改訂)
  - 背景: 「自動化の前に最高傑作を 1 本人間が手作りする」哲学 (DISCUSSION_NOTES #1 参照)。Phase A.5-3a-verify 全通過後、自動化前にゴールドスタンダードを確立。Remotion / ElevenLabs / 画像生成ツール選定を実地で確定する位置付け。当初 F-state-protocol-supplement では CapCut 仮組みも視野に入っていたが、F-doc-backfill (2026-05-02) で「Phase A.5-3b からいきなり Remotion」を採用 (二度手間回避、DECISION_LOG「動画合成ツール Remotion 採用確定」参照)。F-doc-backfill-supplement (2026-05-02) で画像生成候補の DALL-E 3 を ChatGPT Images 2.0 (gpt-image-2) に差し替え (DECISION_LOG「ChatGPT Images 2.0 (gpt-image-2) を画像生成候補に正式追加」参照)。
  - 対応案:
    (1) ElevenLabs アカウント取得 + API キー設定、声選定 (geo_lens 用は低音ダンディ男性、ブランド資産化のため 1 声に固定)
    (2) Nano Banana Pro / ChatGPT Images 2.0 (gpt-image-2) / Flux 1.1 Pro で画像生成比較 (シーンごとの画像プロンプトを使って最低 12-15 枚生成、品質とシネマティック表現を比較してツール確定)
        - ChatGPT Images 2.0 (gpt-image-2) は 2026-04-21 リリースの OpenAI 最新モデル。Image Arena #1、O-series reasoning (Thinking モード) 搭載、日本語の文字レベル精度向上、Web 検索統合でリアルタイムファクトチェック可能。Hydrangea のシネマティック表現とテキスト含む画像 (タイトルカード等) に強み。
        - 価格: 高品質 (1024x1024) 約 $0.21/image、4K $0.41/image、低品質 $0.006/image
        - 比較観点: シネマティック表現 / 日本語テキスト精度 / プロンプト追従性 / 価格 / API 安定性
    (3) Remotion プロジェクトセットアップ (Claude Code に書かせる)
        - 字幕コンポーネント (動的タイミング、Noto Sans JP Black、基本 72pt 強調 96pt、白/金/赤の 3 段階強調)
        - Ken Burns 効果 (ズームイン基本 1.0 → 1.15、強ズーム 1.25)
        - トランジション (ハードカット 0 秒、ピーク地点 0.1 秒ズームパンチ)
        - BGM ダッキング (通常 22%、ナレーション時 15%)
    (4) 動画 1 本完成 (80 秒 MP4)
    (5) docs/golden_master_spec.md に全パラメータ記録 (声 ID / 画像生成プロンプトテンプレ / Ken Burns 設定 / 字幕タイミング / BGM 設定等)
  - 検討時期: Phase A.5-3a-verify 全通過後 (4 カテゴリ全部 OK 判定)
  - 想定工数: 1-2 週間 (制作 3-4 時間 + Remotion セットアップ + 試行錯誤)
  - 関連ファイル: docs/golden_master_spec.md (新規), data/output/golden_master/ (新規), Remotion プロジェクト (新規)

### Phase 1 (F-doc-backfill / 2026-05-02 登録、Phase A.5-3 完了後着手)

- **Phase 1-A: ChannelConfig 統合** (F-doc-backfill / 2026-05-02 登録)
  - 背景: 現状 geo_lens 専用設計。Channel 2/3 追加には設計改修が必要。
  - 対応案: configs/channels/base.yaml + geo_lens.yaml、--channel-id フラグ、TECH_DEBT 2.1/2.2/2.3 同時対応 (YAML 化)
  - 検討時期: Phase A.5-3 全完了後
  - 想定工数: 1 週間
  - 関連: TECH_DEBT 2.1 (編集方針プロンプト YAML 化) / 2.2 (カテゴリ別ベース点数 YAML 化) / 2.3 (キーワード辞書 YAML 化) を本バッチ内で同時対応
  - 関連ファイル: configs/channels/ (新規), src/shared/models.py (ChannelConfig 拡張), src/main.py (CLI 引数)

- **Phase 1-B: src/pipeline/ 分割** (F-doc-backfill / 2026-05-02 登録)
  - 背景: main.py 3303 行は保守困難。pipeline/ への機能別モジュール分割が必要。
  - 対応案: ingestion / clustering / scoring / filtering / analysis / generation / rendering / reporting に分割
  - 検討時期: Phase 1-A 完了後
  - 想定工数: 2-3 週間
  - 関連: TECH_DEBT 4.4 (main.py モノリス化)
  - 関連ファイル: src/pipeline/ (新規), src/main.py (薄いエントリポイント化)

- **Phase 1-C: DB マイグレーション** (F-doc-backfill / 2026-05-02 登録)
  - 背景: 既存テーブルに channel_id カラム追加で多チャンネル対応。
  - 対応案: events / jobs / daily_stats / recent_event_pool / jp_coverage_cache に channel_id カラム追加、デフォルト 'geo_lens' で後方互換
  - 検討時期: Phase 1-A 完了後
  - 想定工数: 1 週間
  - 関連ファイル: src/storage/db.py, scripts/migrate_*.py (新規)

- **Phase 1-D: Supabase 段階移行** (F-doc-backfill / 2026-05-02 登録、★慎重に)
  - 背景: SQLite → Supabase 移行。影響範囲が大きく、段階的に実施必要。Apr 30 の議論で Gemini が「今週末 Supabase 移行」を提案したが、クラウドが「危険すぎる」と反論し計画的実施に変更 (DECISION_LOG「Supabase 段階移行『今週末は危険すぎる』判断」参照)。
  - 対応案: 接続抽象化 → 開発環境動作確認 → テスト並走 → 本番切替 (フィーチャーフラグで戻せる)
  - 検討時期: Phase 1-A/B/C 完了後、Phase B (Web メディア) 着手前
  - 想定工数: 2-3 週間
  - 関連ファイル: src/storage/db.py (抽象化), configs/database.yaml (新規)

---

## 緊急度 低（時間ある時に検討）

---

- **F-guardian-independence-axis: 独立性評価軸の拡張要否** ★低 (条件付き・未確定) (F-editorial-guardian-corroboration / 2026-06-10 起案)
  - 背景: 1-T.2 の corroboration は独立性を**最小定義** (元ソースドメインの階層除外のみ) で
    実装した。提携メディア・通信社配信 (同一ワイヤ記事の転載)・国家系メディア同士の相互引用は
    「独立した支持」に見えても実質同源の可能性がある。1-T.2 では作り込まず (誤り6 = 過剰拡張性
    回避)、発見ドメインを evidence に全列挙して人間監査に委ねる設計とした。
  - 対応案: 第一作 (1-S) + 数本の validation run で「corroborated の根拠ドメインが実質同源
    だった」事例が観測された場合のみ拡張を検討。候補: (a) 通信社 (AP / Reuters / AFP) 配信の
    検出、(b) 国家系メディア群の同源グルーピング (TeleSUR/RT 系等)、(c) 判定プロンプトへの
    「同一ワイヤ記事の転載は独立扱いしない」原則追加 (構造データ化が先、誤り9 回避)。
  - 検討時期: 1-S validation run の観測後 (事例が出なければ着手しない)
  - 関連ファイル: `src/generation/editorial_guardian_corroboration.py`
    (`_validated_independent_domains`)、`configs/prompts/analysis/geo_lens/editorial_guardian_corroboration.md`
  - 関連: F-editorial-guardian-corroboration (1-T.2、最小定義の採用元)、クラウド誤り 6 / 9

- **F-coverage-claim-guard-auto-action** ★低 (条件付き・未確定) (F-title-guard-coverage-claim-policy / 2026-06-08 起案)
  - 背景: 1-Q.5 で coverage claim guard は **flag のみ** (自動置換・自動再生成はしない) で実装した。
    検出した虚偽を機械が穏当表現に直すのは「どう書くべきか」を機械が決める = クラウド誤り 9。第一作は
    手動運用のため flag 止まりで十分。自動アクション (再生成 trigger / 置換) の要否は第一作の guard
    挙動を観測してから判断する。
  - 対応案: 第一作 (1-S) + 数本の運用で guard の flag 頻度・精度・false positive 率を観測。flag が
    高頻度かつ手動修正が回らないなら、(a) 再生成 trigger (script 新ルートを stream 強調で再呼出) /
    (b) production パイプライン (main.py) への guard 配線 (非ブロッキング観測 → ブロッキング gate) を
    段階導入。いずれも各論の言い回し強制を機械化しない設計に留める (クラウド誤り 9)。
  - 検討時期: 第一作 (1-S) の guard 観測後。production 配線 (main.py) は本バッチでは見送り
    (flag のみ / 第一作は手動 / 自動アクションは挙動観測後)。
  - 関連ファイル: `src/generation/coverage_claim_guard.py`、`src/main.py` (生成 dispatch
    L1959/L2010、配線時)、`scripts/run_coverage_claim_guard.py`
  - 関連: F-title-guard-coverage-claim-policy、クラウド誤り 9、1-S 第一作起案

- **F-article-3.1-pro-escalation** ★低 (条件付き・未確定) (F-article-model-upgrade / 2026-06-08 起案)
  - 背景: F-article-model-upgrade で article を gemini-2.5-flash → gemini-3.5-flash に品質昇格 (選択肢C 第一歩)。3.5-flash で article 品質が物足りない場合、選択肢C の次段として gemini-3.1-pro-preview へエスカレする構想。本バッチでは扱わない (3.1 Pro は未配線)。
  - 対応案: カズヤの axis_5 主観評価 (`docs/runs/F-article-model-upgrade/article_2.5flash.md` vs `article_3.5flash.md`) で 3.5-flash が不足と判断された場合のみ着手。`GEMINI_ARTICLE_TIER1` を gemini-3.1-pro-preview に変更 (+ pricing / RPD / thinking パラメータを公式 docs 一次ソースで確認 = クラウド誤り 10 派生「外部 AI 権威化」回避)。★ DISCUSSION_NOTES「article が 3.1 Pro に上がる場合の Editorial Guardian (1-T、gemini-3.1-pro-preview 予定) との布陣整理」観点と統合検討 (3.1 Pro 二役問題)。
  - 検討時期: F-article-model-upgrade の axis_5 評価後 (カズヤ判断)
  - 関連ファイル: `src/llm/factory.py` (GEMINI_ARTICLE_TIER1 解決)、`.env` / `.env.example`、`docs/runs/F-article-model-upgrade/`
  - 関連: F-article-model-upgrade (本起案元)、1-T (Editorial Guardian = gemini-3.1-pro-preview 配線、布陣整理観点)

- **F-article-max-tokens-policy** ★低 (F-article-model-upgrade / 2026-06-08 起案、仮説 3 grep で実態確定)
  - 背景: F-article-model-upgrade 仮説 3 (article の max_tokens が full article を truncate するか) を grep で検証した結果、**article 経路は max_output_tokens を一切設定していない** (`get_article_llm_client()` → `generation_config=None`、`src/llm/factory.py`)。布陣 docs の「MAX1」は MAX_ATTEMPTS=1 (リトライ回数) であって token 上限ではない (起案前提の用語混同を訂正 = クラウド誤り 10 作法)。よって 3.5-flash 出力上限 65,536 までモデル既定でフルに使え、Hydrangea 側の truncate は存在しない = 現状 truncate リスクなし。
  - 対応案: 当面 no-action。将来 article output コスト/長さを明示制御したくなった場合のみ、analysis 経路 (`ANALYSIS_LLM_MAX_TOKENS`) と同様に article 専用 max_output_tokens env を新設する判断を行う (現状は不要)。
  - 検討時期: article output が想定外に長く/高コストになった場合のみ
  - 関連ファイル: `src/llm/factory.py` (`get_article_llm_client` / `generation_config`)、`src/generation/article_writer.py` (不変、呼び出しのみ)
  - 関連: F-article-model-upgrade (本起案元)、F-analysis-max-tokens-tune (analysis 側の max_tokens 制御の前例)

- **F-job-record-av-path** ★低 (ChatGPT Round 2 レビュー / 2026-05-27 起案、F-docs-update-chatgpt-round2-and-error10 で grep 裏取り、Phase A.5-3c 以降)
  - 背景: `src/shared/models.py` の `JobRecord` (L335) に `voiceover_path` (L342) / `review_mp4_path` (L343) フィールドが存在するが、`src/storage/db.py` の jobs テーブル DDL (L14) + `save_job()` (L189) には `script_path` / `article_path` / `video_payload_path` (L18-20) までしか対応していない = AV path は INSERT/UPSERT いずれにも含まれず DB に永続化されない (grep 裏取り済)。Remotion 化後 (Phase A.5-3c) の成果物追跡を DB に寄せたい際に「あれ、MP4 path が DB にない」が発生する未来負債。現状は run_summary / manifest で追えるため致命的ではない。
  - 対応案: Phase A.5-3c の合成パート自動化 (ElevenLabs + Remotion + 画像生成の本番統合) で DB schema を整理。jobs テーブル DDL + save_job() を JobRecord 全フィールド対応に拡張 + idempotent migration 適用 (F-jp-coverage-cache-judgement-persist の `_migrate_jp_coverage_cache` パターン踏襲)。Phase 1-C「DB マイグレーション」(channel_id 追加) と並走整理可能。
  - 検討時期: Phase A.5-3c 着手時
  - 想定工数: 1-2h (DB migration + テスト + 関連書き込み箇所更新)
  - 関連ファイル: `src/storage/db.py` (jobs DDL L14 + save_job L189 拡張、idempotent migration)、`src/shared/models.py` (JobRecord 既存維持)、`docs/runs/F-docs-update-chatgpt-round2-and-error10/job_record_analysis.json` (grep 裏取り)
  - 関連: ChatGPT Round 2 レビュー (2026-05-27 指摘 7)、Phase A.5-3c (ElevenLabs + Remotion + 画像生成 本番統合)、Phase 1-C (DB マイグレーション、並走整理候補)

- ~~**F-video-payload-visual-prompt-target-enemy**~~ ✅ **完了 (F-first-work-golden-master / 2026-06-11、完了済みセクション参照)**。L72 仮想敵 1 行除去 (同時解消条項 = 5 行以内 + tests 非依存を grep 確認)。

- **F-fable5-guardian-poc: Claude Fable 5 を Guardian 役で比較 PoC** ★低 (条件付き・未確定) (F-first-work-golden-master / 2026-06-11 起案)
  - 背景: 第一作 validation run で人間監査済みの ground truth (Guardian 2 層レポート + カズヤの
    flag レビュー結果) が初めて手に入る。これを使い、Claude Fable 5 ($10/$50 per 1M tokens、
    拒否時は HTTP 200 + stop_reason:"refusal" で課金なし、Covered Model = 30日 retention・ZDR 不可)
    を Guardian 役 (抽出 + 忠実性 + corroboration 判定) で gemini-3.1-pro と比較する PoC 構想。
    1-T.1 harness が client DI 可能 (LLMClient 注入) なので adapter 1 本で試せる。
  - 対応案: 第一作の人間監査済みレポートを正解セットに、同一入力で Fable 5 adapter を回し
    事故検出力 (contradicted / not_in_source の検出一致率 + 人間が真と認めた flag の再現) を比較。
    **採用条件 = 3.1-pro より明確に事故検出力が高い場合のみ**。非採用条件 = コスト不釣合 /
    拒否多発 / 過剰保守 (supported を過剰に flag)。
  - 検討時期: 第一作 validation 完了 (カズヤ flag レビュー済み) 後
  - 関連ファイル: `src/generation/editorial_guardian.py` (client DI) / `src/llm/` (adapter 新規)
  - 関連: F-editorial-guardian-claim-extraction (1-T.1、DI 設計元)、F-first-work-golden-master
    (ground truth 供給元)、CLAUDE.md クラウド誤り 10 派生 (一次ソース = 公式 pricing 確認済)

- **README 全面書き直し** (TECH_DEBT.md 7.1 由来)
  - 背景: 初期 PoC 時代のまま、現状と乖離
  - 対応案: 全フェーズ完了時に書き直し
  - 検討時期: Phase 1.5 完了後

- **REFACTORING_PLAN.md の最終整理** (F-doc-cleanup / 2026-05-03 登録)
  - 背景: REFACTORING_PLAN.md (2026-04-23) は Phase 1-4 系列の改修議論。F-doc-cleanup で冒頭にアーカイブ注記を追加し、個別改修内容は FUTURE_WORK の Phase 1-A / Phase B-3/4 / Phase A.5-3c F-video-compose-integration として現運用に取り込み済。本書は歴史的記録として保持中。
  - 対応案: アーカイブ統合 (docs/archive/REFACTORING_PLAN.md に移動) or 完全削除の最終判断 + 歴史的記録としての価値再評価。「対症療法じゃなくて根本治療」哲学に基づき、不要なら削除する選択肢も含めて検討。
  - 検討時期: README 全面書き直しと同時 (Phase A.5-3d 完了後)
  - 関連ファイル: docs/REFACTORING_PLAN.md, docs/CURRENT_STATE.md (関連ドキュメント導線の更新)

- **触っちゃダメリストのコメント整理** (CLAUDE.md)
  - 背景: なぜ触ってはいけないかの理由が曖昧
  - 対応案: 各ファイルに「触れない理由」と「将来触れる条件」を併記
  - 検討時期: 触っちゃダメリスト見直しの一部として

- **ガベージフィルタの除外内容定期検証** (E-1 ハイブリッド版運用後の懸念)
  - 背景: 必要な記事を誤除外していないか
  - 対応案: 月1回、除外された記事タイトルをカズヤが目視確認。誤除外パターンを発見したら BLOCKED_CATEGORIES や閾値を調整
  - 検討時期: 1ヶ月運用後

### Phase B (F-doc-backfill / 2026-05-02 登録、3-6 ヶ月後)

- **B-1: TikTok Content Posting API 申請 + 実装** (F-doc-backfill / 2026-05-02 登録)
  - 背景: 自動投稿の本命。審査期間が長いため早めに申請が必要。
  - 対応案: 申請 1 日 + 審査 1-3 週間 + 実装 1 週間。Phase A.5-3d で先行統合済の場合は本エントリは「審査通過後の本格運用」に縮小
  - 検討時期: Phase A.5-3d 後
  - 関連ファイル: src/publishing/tiktok.py (新規)

- **B-2: ElevenLabs 統合 (追加声)** (F-doc-backfill / 2026-05-02 登録)
  - 背景: ★Phase A.5-3c の F-elevenlabs-integration で前倒し実施済の予定。本エントリは japan_athletes / k_pulse 用の声追加のみ
  - 対応案: configs/audio.yaml に japan_athletes / k_pulse 用の声 ID を追加
  - 検討時期: Channel 2/3 立ち上げ時
  - 関連ファイル: configs/audio.yaml

- **B-3: Channel 2 (Japan Athletes Abroad) 立ち上げ** (F-doc-backfill / 2026-05-02 登録)
  - 背景: 海外で戦う日本人スポーツ選手チャンネル。
  - 対応案: スポーツ系 RSS ソース追加 (ESPN, Marca, L'Équipe 等)、scoring.py の sports カテゴリベース調整、Breaking Shock 中心の武器庫
  - 検討時期: Phase 1-A (ChannelConfig 統合) 完了後
  - 想定工数: 1-2 週間
  - 関連ファイル: configs/channels/japan_athletes.yaml (新規), configs/sources.yaml (拡張)

- **B-4: Channel 3 (K-Pulse) 立ち上げ** (F-doc-backfill / 2026-05-02 登録)
  - 背景: 韓国エンタメチャンネル。
  - 対応案: 韓国エンタメ系 RSS 追加 (Yonhap、Soompi、Koreaboo 等)、entertainment カテゴリベース調整、Breaking Shock + Cultural Divide 武器庫
  - 検討時期: Phase 1-A 完了後
  - 想定工数: 1-2 週間
  - 関連ファイル: configs/channels/k_pulse.yaml (新規), configs/sources.yaml (拡張)

- **B-5: Remotion Lambda 並列レンダリング** (F-doc-backfill / 2026-05-02 登録)
  - 背景: ★基本 Remotion 移行は Phase A.5-3c の F-video-compose-integration で前倒し実施済の予定。本エントリは Remotion Lambda 並列レンダリングのみ
  - 対応案: AWS Lambda + Remotion Lambda のセットアップ、3 チャンネル並列レンダリング
  - 検討時期: Channel 2/3 稼働後
  - 関連ファイル: remotion/ (拡張), .github/workflows/ (拡張)

- **B-6: Lovable + Vercel フロントエンド** (F-doc-backfill / 2026-05-02 登録)
  - 背景: Web メディアとしての公開、SEO で長期的トラフィック獲得。
  - 対応案: Lovable で Next.js 生成 + Vercel デプロイ、生成済み記事の表示 / チャンネル別アーカイブ / SEO 対策
  - 検討時期: Phase 1-D (Supabase 移行) 完了後
  - 想定工数: 2-3 週間
  - 関連ファイル: web/ (新規, 別リポジトリも検討)

- **B-7: Cloudflare R2 (ストレージ移行)** (F-doc-backfill / 2026-05-02 登録)
  - 背景: 動画ファイルの保存コスト削減。S3 互換 API、エグレス料金ゼロ、保存料金 $0.015/GB/月
  - 対応案: 動画ファイルの保存先を data/output/ → R2 に移行、CDN 配信
  - 検討時期: Phase B (動画自動化) 完了後
  - 想定工数: 1 週間
  - 関連ファイル: src/storage/ (R2 クライアント新規)

### Phase C (F-doc-backfill / 2026-05-02 登録、6-12 ヶ月後)

- **C-1: YouTube Partner Program 申請** (F-doc-backfill / 2026-05-02 登録)
  - 背景: 収益化の最初のマイルストーン。
  - 条件: フォロワー 1000 人 + 視聴時間 4000 時間
  - 期待: 収益化開始 (広告収入)
  - 検討時期: 投稿開始 + 数ヶ月後

- **C-2: サブスク (note 等) / B2B レポート販売** (F-doc-backfill / 2026-05-02 登録)
  - 背景: ストック型収益、ファンベース化。
  - 対応案: note プレミアム / Substack 等で月額、B2B レポート (10-50 万円)
  - 検討時期: Web メディア稼働後
  - 想定: 月額 500-2000 円のサブスクで読者数次第

- **C-3: SaaS 化検討** (F-doc-backfill / 2026-05-02 登録)
  - 背景: Hydrangea パイプラインを他メディア向けにカスタマイズ可能な SaaS 化
  - 対応案: マルチテナント化、テンプレート化された Channel 設定、API 提供
  - 期待: B2B SaaS、数百万-数千万 ARR
  - 検討時期: Channel 3 稼働 + 安定運用後

- **C-4: 事業売却検討** (F-doc-backfill / 2026-05-02 登録)
  - 背景: Exit 戦略の選択肢。
  - 期待: 単体 1-10 億円 / 自社連携 5-50 億円
  - 検討時期: 規模拡大後

- **C-5: 自社サービス (観光・ブライダル) 連携** (F-doc-backfill / 2026-05-02 登録)
  - 背景: Hydrangea を「メディア」として PR、本業との相乗効果
  - 対応案: コンテンツ内での自社サービス自然紹介、SEO 流入の自社サービス送客
  - 検討時期: Web メディア稼働後

### 観察中項目 (F-doc-backfill / 2026-05-02 登録)

- ~~**F-17 候補: Gemini API 503 安定性対処** (F-doc-backfill / 2026-05-02 登録)~~ → F-trial-run-candidate-a-reverify / 2026-05-19 で `F-gemini-503-stability-audit` として緊急度 高に昇格 → ★ **F-gemini-model-audit / 2026-05-19 で撤回** (Gemini モデル切替 = `F-gemini-model-migrate-emergency` で 503 多発リスクは根本治療されるため、503 専用の対症療法バッチは不要。早期検知は F-periodic-health-check でカバー)

- **_FRAMING_RESULTS の LRU 化** (F-doc-backfill / 2026-05-02 登録、Phase 2 案件)
  - 背景: src/analysis/perspective_extractor.py の _FRAMING_RESULTS が無制限 dict キャッシュ。長時間稼働でメモリ肥大化の可能性。functools.lru_cache(maxsize=1000) に変更。
  - 不変原則整合: 不変原則 4 (analysis 触らない) と衝突、Phase 1-A で他の analysis 改修と同時対応
  - 着手条件: メモリ使用量の実測値次第
  - 関連ファイル: src/analysis/perspective_extractor.py

- **並列化検討** (F-doc-backfill / 2026-05-02 登録、Phase 2 案件)
  - 背景: candidate1 の framing_inversion / multi_angle / insights は並列可能。asyncio + concurrent.futures で時間効率改善 (RPM 制限内のため合計コール数は変わらない)。
  - 着手条件: Phase 1 完了後
  - 関連ファイル: src/analysis/analysis_engine.py

---

## 完了済み（参考用）

各項目は以下の形式で記載:
- **タイトル** (完了バッチ / 完了日)
  - 何を対応したか

---

- **Phase A.5-3b 第一作起案 (1-S) — golden master 素材一式 + 手動 PoC の道具立て (実装バッチ)**
  (F-first-work-golden-master / 2026-06-11 完了)
  - 発生バッチ: F-image-prompt-spec (2026-05-18) で起案、1-T.2 完了 (2026-06-10) で関門ゼロ。
  - 対応: 候補A `cls-6889e9e1c7ac` の golden master を新ルート + 確定布陣 (QUALITY/ARTICLE 全 Tier
    gemini-3.5-flash pin = silent 劣化を fail に変換) で再生成し `data/output/golden_master/` に
    original 凍結 (スナップショット = `docs/runs/F-first-work-golden-master/golden_master/`)。
    editorial brief (報道済み明示 / ICRC 角度限定 / silence 回避 / punchline 方向 + ADR-0003) は
    script プロンプトのみプロセス内注入 (production プロンプト不変、article は不変原則 1 で素のまま)。
    ★ CP-1 重大乖離訂正: 候補A は sources_en=1 で extract_perspectives 構造的 0 件 → fallback 同形
    hidden_stakes 候補をハーネス注入 (式同形・写し元 L805-847 記録・品質ゲートのみ bypass)。
    validation = 2 ガード 3 ランナー実走 (title silence flag / c5 帰属エラー contradicted / article
    coverage 過大主張 c10/c13 を独立ソースが明示矛盾 / c6 企業主張は run3 で corroborated 回収)。
    image_prompt レイヤー新設 (`src/generation/image_prompt_writer.py`、5 プレート、文字なし /
    意味記述正典 / ADR-0001+0003 強制、テスト 18 件)。Remotion テンプレート (`manual_poc/remotion/`、
    独立 npm、セーフゾーン 3 帯紙面 + フックカード + Ken Burns + フレーズ同期字幕 + ducking、
    ダミー MP4 レンダ実証 = `npx remotion render FirstWork`)。`manual_poc/tts_to_captions.py`
    (ElevenLabs with-timestamps → captions 変換、公式 docs 一次ソース確認、テスト 6 件)。
    運用規約 = `docs/golden_master_spec.md` (original 凍結 / *_edited 命名 / 編集→再検証ループ /
    手動 PoC チェックリスト / AI 開示必須)。axis_5 採点は手動 PoC (新エントリ「第一作 手動 PoC」★高)。
    baseline 1557 → 1581 passed (+24)。

- **F-video-payload-visual-prompt-target-enemy — twist visual_goal の「仮想敵」語彙除去**
  (F-first-work-golden-master / 2026-06-11 完了)
  - 発生バッチ: X1 (2026-05-31) で起案 (★低)。
  - 対応: `src/generation/video_payload_writer.py` L72 の twist visual_goal テンプレートから
    「仮想敵」を除去 (「裏の構造・地政学/カネ/権力の文脈を図解で暴く」)。1-S の image_prompt
    レイヤー新設と同時解消 (5 行以内 + tests 非依存を grep 確認、image_prompt 側には最初から
    持ち込まない)。既存テスト破壊ゼロ。

- **F-editorial-guardian-corroboration (1-T.2) — Editorial Guardian 第2段: 真実性検証 = grounding 複数ソース突合 + レポート enrichment (実装バッチ)**
  (F-editorial-guardian-corroboration / 2026-06-10 完了)
  - 発生バッチ: F-editorial-guardian-claim-extraction (1-T.1 / 2026-06-10) で ★★高 起案。
    カズヤ確定 2 バッチ構成の後半、**第一作 (1-S) 前の最後の関門** (これで関門ゼロ)。
  - 対応 (検証の2層モデルの第2層、★ 検索と判定の分離):
    - **`src/generation/editorial_guardian_corroboration.py` 新規**: 証拠収集 =
      `GroundingSearchClient` (raw genai.Client 注入 + google_search tool、
      `GUARDIAN_GROUNDING_MODEL` default gemini-2.5-flash = F-13.B 同実績、per-call timeout、
      redirect URL の記事実体解決 best effort)。claim ごとに 1-T.1 の verification_queries を
      全実行 (run 間分散への緩和 = 複数クエリ証拠の集約判定)。判定 = Guardian 単一モデル
      (gemini-3.1-pro-preview、沈黙的劣化の禁止は判定層で維持、3.1-pro の google_search
      サポートに非依存)。
    - **truthfulness 語彙確定**: `corroborated / contradicted (明示的矛盾のみ = B-3') /
      uncorroborated (≠ 虚偽)` + harness 値 `unverified` (検証未完)。第1層 contradicted /
      unverified は skip (pending + skip 理由 notes、人間修正後に手動ランナー再実行が運用ループ)。
    - **独立性の最小定義 + deterministic 安全網**: 元ソースドメイン (event_snapshot 由来) の
      階層除外のみ。judge が元ソースのみ / 証拠に無いドメインを根拠に corroborated →
      harness が uncorroborated に倒す。発見ドメインは evidence に全列挙 (人間監査)。
    - **公開可否の最終バー**: supported × corroborated のみ非 flag。**flag のみ** (自動修正・
      公開ブロックなし、公開判断はカズヤ)。enriched レポートは schema_version=2 (入力不変の
      deep copy enrichment)。
    - 手動ランナー `scripts/run_editorial_guardian_corroboration.py` (入力 = 1-T.1 レポート
      JSON、exit 2 = judge unavailable)。
  - ★ X1 Slot-1 実走 2 回: run1 = 2.5-flash の transient 503 波 (13/21 クエリ) 下で
    corroborated 7 / unverified 12 = **沈黙的劣化の禁止が実地で機能**。run2 (再実行ループ実証) =
    corroborated 10 / unverified 9。両 run 合算 13/19 corroborated、run 間分散
    (c7/c11/c16 反転) を Guardian 文脈でも実測 (F-grounding-determinism-audit 観点)。
    c16 (死者 3,371 / 負傷 10,129) / c18 (スモトリッチ発言) 等を独立ソースで裏取り成功。
  - テスト: `tests/test_editorial_guardian_corroboration.py` 新規 +38。baseline 1519 →
    **1557 passed** (破壊ゼロ、1-T.1 の 32 テストも全通過 = スキーマ additive 拡張の無破壊)。
  - 不変原則違反: なし (triage ヘルパは同形再実装、写し元行番号記録)。
  - 相乗り: CLAUDE.md ガードレール §4 secrets 表示ガード (1-T.1 の .env 露出の再発防止)。
  - 詳細レポート: `docs/runs/F-editorial-guardian-corroboration/REPORT.md`
  - 関連バッチ: 1-T.1 (前半 + スキーマ正本) / F-guardian-production-wire (★中、新規起案) /
    F-guardian-independence-axis (★低、新規起案) / 1-S 第一作起案 (次バッチ、関門ゼロ)

- **第一作公開前の高リスク事実検証ワークフロー 第1段 (1-T.1) — Editorial Guardian: 高リスク主張抽出 + 忠実性検証 + 2層レポート骨格 (実装バッチ)**
  (F-editorial-guardian-claim-extraction / 2026-06-10 完了)
  - 発生バッチ: F-image-prompt-spec (2026-05-18、ADR-0003 由来) で起案、X1 (2026-05-31) で
    必須性 production 実証 (article 内の死者数 3,371 / 10,129 人・兵士死亡 25 人・スモトリッチ
    発言引用が production 未検証のまま出力)。カズヤ確定の 2 バッチ構成の前半。
  - 対応 (検証の2層モデルの第1層):
    - **factory.py GUARDIAN role 新設**: gemini-3.1-pro-preview **単一要素 tier list**
      (TIER2〜4 なし) = 沈黙的劣化の禁止を構造的に担保。`get_guardian_llm_client()` 新設。
      `GEMINI_GUARDIAN_TIER1` を 3 協調箇所 (.env / .env.example / factory.py inline) に配置。
    - **`src/generation/editorial_guardian.py` 新規**: Guardian モデルで高リスク主張を構造化
      抽出 (ADR-0003 対象 5 分類 + quote_span) → 第1層・忠実性判定 (`supported / contradicted /
      not_in_source` 3値 + harness 値 `unverified` = 検証未完) + verification_queries 生成。
      flag = supported 以外すべて (1-Q.5 B-3' と安全方向が逆、ただし unverified ≠ 虚偽)。
      **flag のみ** (自動修正・再生成・公開ブロックなし)。
    - **2層レポート骨格**: `EditorialGuardianReport` (guardian_model_used / guardian_unavailable /
      SourceMaterialScope / truthfulness_status=pending 確保) = 1-T.2 の差し込みスキーマ固定。
    - 手動ランナー `scripts/run_editorial_guardian.py` (event_snapshot + analysis.json 合成 →
      レポート JSON、exit 2 = guardian_unavailable)。
  - ★ X1 Slot-1 実走 (gemini-3.1-pro-preview 実呼出) で**本物の歪曲を検出**: 20 主張中
    1 contradicted = article「ヒズボラがイスラエル北部への攻撃を継続し、イスラエル軍兵士25人が
    死亡した」は元ソースでは「25 人 = 3 月以降のレバノン国内累計戦死者数」(場所・期間帰属の
    取り違え)。レポート例 `docs/runs/F-editorial-guardian-claim-extraction/x1_slot1_guardian_report.json`。
  - ★ 仮説 7 偵察: F-13.B grounding 機構の 1-T.2 再利用性調査を
    `docs/runs/F-editorial-guardian-claim-extraction/grounding_reuse_survey.md` に出力 (コード変更なし)。
  - テスト: `tests/test_editorial_guardian.py` 新規 +32。baseline 1487 → **1519 passed** (破壊ゼロ)。
  - 不変原則違反: なし。
  - 詳細レポート: `docs/runs/F-editorial-guardian-claim-extraction/REPORT.md`
  - 関連バッチ: 1-T.2 F-editorial-guardian-corroboration (★★高、緊急度 高に正式登録) /
    1-S 第一作起案 (適用先) / F-grounding-determinism-audit (1-T.2 の分散課題元)

- **F-title-guard-coverage-claim-policy — coverage claim 事実整合の構造データ + 生成プロンプト原則 + 生成後 guard (実装バッチ、1-Q.5)**
  (F-title-guard-coverage-claim-policy / 2026-06-08 完了)
  - 発生バッチ: ChatGPT Round 2 (2026-05-27 指摘 2) で起案、X1 試運転 (2026-05-31) で本番再現実証。
    Slot-1 cls-c8876d474612 の `platform_title="日本では報道されないIsraelの視点"` が
    stream_classification=`stream_2_perspective_gap` (= 事件本体は一部報道済) に対して silence 絶対
    表現を出力。F-article-model-upgrade A/B でも article 本文が「9,600 人虐待は日本でも報道済」を明示
    せず silence 寄りに振れた = title 単体でなく article 本文も coverage claim が破れる production 再現。
  - 対応 (原則プロンプト指示 + 生成後 guard の 3 層):
    - **Layer 2 構造データ**: `configs/coverage_claim_policy.yaml` 新規 (系統 → allowed_claim_level /
      forbidden_claim_categories の意味カテゴリ)。guard 判定基準 + プロンプト原則の根拠を両層で共有。
      各論の言い回し強制ではなく「自系統判定に反する事実主張を弾く」基準のみを構造化 (クラウド誤り 9 回避)。
    - **Layer 1 プロンプト原則**: `configs/prompts/analysis/geo_lens/script_with_analysis.md` に事実整合
      原則を追記 (perspective_gap / framing_inversion なら事件本体は報道済の事実を踏まえ silence 絶対
      表現をしない。具体的言い回しは LLM の知性に委ねる = 足すのは「事実に反するな」原則のみ)。
      ★ 仮説 2 分岐 = branch (b): article プロンプトは `article_writer.py` 内 `_PROMPT_TEMPLATE`
      ハードコード (不変原則 1) のため **article 側はプロンプト原則を追加せず guard のみで担保**。
    - **Layer 3 生成後 guard**: `src/generation/coverage_claim_guard.py` 新規 (article_writer.py /
      script_writer.py 既存ルート不変)。title + article + 真値 stream_classification を入力に LLM judge
      で事実整合を検証。★ キーワードマッチ不採用 (言い換えで漏れる脆さ + Stream 3 過剰検出の轍)。
      ★ B-3' 原則: LLM が「明示的に矛盾」(status=contradiction) と判定した場合のみ flag、uncertain /
      沈黙は flag しない。検出 → **flag のみ** (自動置換・再生成はしない、第一作は手動)。
      silence_gap / out_of_scope は forbidden 空のため LLM を呼ばず短絡 (flag なし)。
    - 手動ランナー `scripts/run_coverage_claim_guard.py` 新規 (保存済み script.json + article.md +
      analysis.json に guard を適用、第一作 1-S 用)。
  - ★ CP-1 起案前提訂正 (クラウド誤り 10 作法、grep-first):
    - **仮説 1 (訂正)**: 起案者は「title の silence は script の title 素材から流入」と想定したが、grep で
      `generate_title_layer` は LLM stage 不在の決定的合成 (factory.py L20 裏取り)、silence 絶対表現は
      `title_generator.py:_platform_title_candidates` の **ハードコード template** (L136/149/203) を
      `is_strong` evidence ヒューリスティクス (`_is_strong_evidence` L41-72、perspective_gap_score>=3.0
      でも真) で選択した結果と確定 = **script 本文非依存**。⇒ title の silence は Layer 1 プロンプト原則
      では届かず、guard (Layer 3) が唯一の安全網。
    - **仮説 2 (確認、scope 分岐)**: article プロンプトは `article_writer.py` 内 `_PROMPT_TEMPLATE`
      ハードコード = branch (b)。article 側はプロンプト原則を加えず guard のみで対応。
    - 仮説 3/4/5 確認: 新ルート `generate_script_with_analysis` は X1 で particular_angle_metadata
      (stream_classification 含む) 配線済 / title・coverage guard は不在 (グリーンフィールド) /
      stream_classification 真値は `ScoredEvent.analysis_result.particular_angle_metadata.stream_classification`
      で guard 実行時に参照可能。
    - 仮説 6 確認: baseline 実測 **1466 passed** (311s)。
  - テスト: `tests/test_coverage_claim_policy.py` (7) + `tests/test_coverage_claim_guard.py` (14) =
    新規 +21。baseline 1466 → **1487 passed** (破壊ゼロ)。
  - 不変原則違反: なし (article_writer.py 0 行 / script_writer.py 既存ルート 0 行 / triage 不変 /
    analysis 既存ファイル不変。guard は src/generation/ 新規ファイルで出力を外から検証)。
  - 詳細レポート: `docs/runs/F-title-guard-coverage-claim-policy/REPORT.md`
  - 関連バッチ: F-particular-angle-metadata-production-wire (X1、本番再現実証元) / 1-S 第一作起案
    (候補A 固有 framing 指針はこちらの領分) / 1-T Editorial Guardian (高リスク事実検証)

- **F-particular-angle-metadata-production-wire (X1) — particular_angle_metadata + sontaku_signals 本番配線 + target_enemy 解消統合 + F-analysis-max-tokens-tune 統合 (実装バッチ、1-R)**
  (F-particular-angle-metadata-production-wire / 2026-05-31 完了)
  - 発生バッチ: F-particular-angle-redesign-extension (2026-05-08) で正典化された
    `ParticularAngleMetadata` + nested `SontakuSignals` を Hydrangea production に配線し、
    新ルート `generate_script_with_analysis` を production default 起動 (ANALYSIS_LAYER_ENABLED=true)。
    F-script-writer-target-enemy-fix-investigate (2026-05-26、1-P) で確定の target_enemy
    解消も統合 (新ルート起動で target_enemy framing が production から自動退役)。
  - 対応: 不変原則 4 例外条件 5 点充足適用で `src/analysis/particular_angle_extractor.py` 新規
    (単一パス α、`get_analysis_llm_client()` 経由 = Gemini 3 系 temperature ガード + ANALYSIS_LLM_MAX_TOKENS
    env 自動適用)。`src/shared/models.py` に SontakuSignals + ParticularAngleMetadata (nested)
    + AnalysisResult.particular_angle_metadata: Optional[...] 追加 (後方互換)。新規プロンプト
    `configs/prompts/analysis/geo_lens/particular_angle_extract.md` (統合判定、3 スクリプト由来基準を
    1 プロンプトに統合)。`script_with_analysis.md` に metadata 入力ブロック追加 (各論ルール足さず =
    クラウド誤り 9 回避)。`src/generation/script_writer.py` の `_build_script_with_analysis_prompt`
    に新プレースホルダ渡し (既存ルート write_script 完全不変、不変原則 2 厳守)。`src/main.py`
    分析ブロックで extract_for_scored_event 呼出 + model_copy で metadata 付与 (run_analysis_layer
    不変、不変原則 4 厳守)。`.env` / `.env.example` で ANALYSIS_LAYER_ENABLED=true (production
    default 化) + ANALYSIS_LLM_MAX_TOKENS=2000→4096 (F-analysis-max-tokens-tune 統合)。
    `tests/conftest.py` 新規 autouse fixture で .env true 化のテスト波及を抑止 (既存テスト無改修)。
    新規テスト 31 + 既存ファイル追加 3 = 計 +34 tests。baseline 1432 → **1466 passed** (破壊ゼロ)。
  - CP 経緯:
    - CP-1: クラウド誤り 10 系統の grep 作法で起案前提と実コードの 3 つの乖離を発見・訂正
      (移植元 `scripts/extract_particular_angle.py` は旧 3 分類版 + sontaku 不在 / 3 要素名称ズレ /
      dispatch 既配線)。推奨バンドル (V1 + α + .env.example true) でカズヤ承認。
    - CP-2: sample mode 分析未起動 + スタール枯渇 + GarbageFilter 48h で当初 5 batch 案ブロック
      → **Path A pure (1 fresh batch + 1 run、本番状態維持)** に変更 (カズヤ判断、scaffolding は
      本番と違う人工状態を作るため不採用)。ingestion + run normalized mode の副作用 read-only 調査で
      non-destructive (新規追加のみ、$0 LLM) を確認。
    - CP-3: 試運転 exit 0 / run_llm=39 / Slot-1 cls-c8876d474612 で全 X1 必須目的達成
      (stream_2_perspective_gap + sontaku.level=high/diplomatic + target_enemy=None + Cultural Divide +
      char validation passed + used_fallback=false / retries=0 + max_tokens 4096 で JSON 切断ゼロ)。
      axis_5 カズヤ採点で「城→海運→電気代」具体着地 + target_enemy 退役が質に表れたと評価、
      **W1 完全成功**。
  - 後続バッチ向け引継ぎ事項 6 件確定 (X1 範囲外、FUTURE_WORK / DISCUSSION_NOTES 記録):
    (1) 高リスク事実検証必要性 production 実証 (1-T の必須化、緊急度 中 → 高) /
    (2) punchline 尻切れ未完結 (F-script-punchline-tail-cut-investigate ★中) /
    (3) title guard + broad/particular 切り分け曖昧さ (F-title-guard-coverage-claim-policy
    スコープ拡張 + 第一作 framing 指針) /
    (4) 視覚プロンプト「仮想敵」語彙残存 (F-video-payload-visual-prompt-target-enemy ★低) /
    (5) run 間分散未検証 (F-periodic-health-check 統合) /
    (6) 試運転データ確保の構造的困難 (F-trial-data-procurement-protocol ★中)
  - 不変原則違反: なし (article_writer.py 不変 / script_writer.py 既存ルート write_script 不変 /
    triage 既存ファイル不変 / analysis 既存ファイル不変 + 新規 1 ファイル例外条件適用 /
    既存テスト不変、baseline 1432 → 1466 passed で +34 全新規)
  - 詳細レポート: `docs/runs/F-particular-angle-metadata-production-wire/REPORT.md`
  - 関連バッチ: F-particular-angle-redesign-extension (メタデータ正典化) /
    F-script-writer-target-enemy-fix-investigate (1-P、sanctioned 経路確定) /
    F-gemini-quality-tier-poc (1-Q、モデル布陣 v2 で analysis=gemini-3.5-flash 配線) /
    F-title-guard-coverage-claim-policy (1-Q.5、第一作着手前必須) /
    Phase A.5-3b 第一作起案 (1-S、確定モデル + 候補A perspective_gap で実装)

- **F-docs-update-chatgpt-round2-and-error10 (ChatGPT Round 2 レビュー統合 + クラウド誤り 10 明文化)**
  (F-docs-update-chatgpt-round2-and-error10 / 2026-05-27 完了、docs-only・改修なし)
  - 発生バッチ: ChatGPT が Gemini モデル布陣セカンドオピニオン依頼を保留して Phase A.5-3b
    第一作前のコードレビュー Round 2 (7 指摘) を返却。docs 正本との grep 裏取り照合 + 新規
    タスク化 + クラウド誤り 10 系統の CLAUDE.md 明文化を行う docs-only バッチ。
  - 対応: main `2f99ebd` から branch 作成、baseline 1417 passed 確認 (99.31s)。7 指摘を grep 裏取り:
    - 指摘 3 (F-1 locale key) / 指摘 4 (F-13.B cache 永続化) = **RESOLVED** (古い Project
      Knowledge 由来、editorial_mission_filter.py:163 `get("japan")` + db.py:120-121 で確認)
    - 指摘 1 = 既に FUTURE_WORK 登録済 (F-evidence-jp-coverage-audit-trail)
    - 指摘 2 (title 誇大) / 指摘 6 (analysis max_tokens) / 指摘 7 (JobRecord AV path) =
      **REAL → 新規 3 タスク起案** (F-title-guard-coverage-claim-policy 高 /
      F-analysis-max-tokens-tune 中 / F-job-record-av-path 低)
    - 指摘 5 (model drift + retry 観測) = F-periodic-health-check スコープ拡張 (★ 起案の
      「F-pipeline-health-check」呼称を正本 F-periodic-health-check に統合)
  - 判定: ★ ChatGPT 側でも古い Project Knowledge 由来で「解消済みを新規発見と誤認」=
    **クラウド誤り 10 系統が外部 AI レビューでも発生**することを観察。クラウド誤り 10 を
    CLAUDE.md に明文化 (発生実例 4 件 + ChatGPT Round 2 観察)。起案前提を 2 点訂正
    (指摘 6 default 箇所 = factory.py:516 / 指摘 5 受け皿エントリ名)。
  - baseline 1417 passed 維持 (改修なし自動維持)、src/ tests/ configs/ scripts/ .env
    .env.example 0 行変更。不変原則 1-5 完全遵守 (例外条件適用なし)。
  - 詳細: `docs/runs/F-docs-update-chatgpt-round2-and-error10/REPORT.md` + grep 裏取り JSON 4 件。

- **F-gemini-3.5-flash-api-audit (Gemini 3.5 Flash API 影響範囲調査)**
  (F-gemini-3.5-flash-api-audit / 2026-05-27 完了、調査専用・改修なし)
  - 発生バッチ: 2026-05 GA リリースの Gemini 3.5 Flash (Stable) を Narrative
    primary (QUALITY Tier1) 候補に追加する前提として、API 破壊的変更の影響範囲を
    grep + コード精読 + 公式仕様対比で確認する調査専用バッチ。F-gemini-quality-tier-poc
    (1-Q) の前提情報整備。
  - 対応: main `07dc175` から branch 作成、baseline 1417 passed 確認。grep 棚卸し =
    top_p/top_k/thinking_budget/thinking_level/カスタム function calling/response_schema
    すべて **0 件**。temperature は analysis client (本番未起動) + 手動スクリプトのみ。
    `tools=` は Grounding 組込み `google_search` 限定。`gemini-3.5-flash`/`gemini-3.1-pro`
    はコードベースに **0 件** (未採用/未配線)。
  - 判定: **真因 b (API 破壊的変更は無いか軽微) 確定** = migration 不要。構造的理由 =
    (a) Tier ベースのモデル ID 解決で本番生成系は API パラメータ非指定 (generation_config=None)、
    (b) 構造化出力 API でなく free-text JSON パース、(c) カスタム function calling 不使用で
    `tools=` は Grounding 限定。RPD シミュレーション = 3.5 Flash を Narrative primary 投入で
    20-40 calls/日 << RPD 10K (250-500x 余裕)。
  - CP-1 カズヤ判断: **Y1 (F-gemini-quality-tier-poc に直進)** [クラウド推奨]。候補リスト =
    3.5 Flash 追加 + 3 Flash Preview 削除。★ UI で選択捕捉が得られず、クラウド推奨を既定として
    Task E/F を進行 (docs のみ・完全可逆、Task G commit/merge がカズヤ承認ゲート)。
  - ★ クラウド誤り 10 系統の検証: 起案前事前情報 (2026-05-19 Google I/O 由来、4 破壊的変更
    候補) を仮説として grep で検証 → Hydrangea には当てはまらないと確定 = grep-first 作法が機能。
  - 結果: `src/` `tests/` `configs/` `scripts/` `CLAUDE.md` `.env` `.env.example` 0 行変更、
    baseline **1417 passed 維持** (自動)、不変原則 1-5 完全遵守 (例外条件適用なし)。
  - 新規/保留残課題: F-gemini-quality-tier-poc 候補リスト更新 (3.5 Flash 追加 + 3 Flash
    Preview 削除) / 3.5 Flash 投入時の output_token・レイテンシ実測 (Thought preservation
    自動 ON のコスト面、PoC 試運転で観察) / LIGHTWEIGHT Tier1 切替本命 = gemini-3.1-flash-lite
    (RPD 150K)。
  - 関連: `docs/runs/F-gemini-3.5-flash-api-audit/REPORT.md` + grep_inventory.json +
    current_usage.json + adoption_simulation.json + breaking_change_analysis.json +
    environment_snapshot.json

- **F-gemini-model-migrate-emergency (5/25 shutdown 緊急対応 Tier3 GA 一括置換)**
  (F-gemini-model-migrate-emergency / 2026-05-19 完了)
  - 発生バッチ: F-gemini-model-audit (2026-05-19) で確定したスコープに基づく
    最小改修実装。`gemini-3.1-flash-lite-preview` 5/25 shutdown 対応。
  - 対応: main `2a73a0d` から branch 作成、baseline 1417 passed 確認。
    両系統 Tier3 (`.env` GEMINI_MODEL_TIER3 / GEMINI_LIGHTWEIGHT_TIER3) +
    factory.py default (L316/L324) + config.py default (L76) +
    `.env.example` を `gemini-3.1-flash-lite` (GA) に一括置換。doc-drift
    コメント (factory.py L82/L96/L309-310, config.py L142, main.py
    L2471-2473, judge.py L72) 整理。`src/llm/retry.py` 0 行変更
    (shutdown モデル ID を Tier 階層から除去 → 404 到達自体が構造的に消滅
    = audit CP-1 仮説どおり最小対処で十分)。
  - 想定外結果対処: 改修後 baseline 1417→1415 (test 2 件が Tier3 default
    を旧モデル名 hard-pin、機能回帰ではなく default 追従)。task 規定どおり
    Task D-2 前に即停止 → CP-1 エスカレーション。
  - CP-1 カズヤ判断 (2026-05-19): 判断1 = test 2 行更新承認 (期待値
    リテラルのみ、ロジック不変、BATCH_PROTOCOL 例外条件 4 点充足)。
    判断2 = Lightweight Tier1 据置 (選択肢 B、「動くものを壊さない」優先、
    系統変更 MEDIUM リスクは F-gemini-quality-tier-poc で品質検証後判断)。
  - 結果: test 更新後 baseline **1417 passed 復帰**。1 batch 試運転
    exit 0 / status=completed / 3 slots published / used_fallback=false /
    judge error 0 / ログに 404・NOT_FOUND・shutdown モデル参照 0 件。
    不変原則違反なし (`src/triage/` `src/analysis/` article_writer.py
    retry.py `configs/` `scripts/` `CLAUDE.md` 0 行変更、`tests/` 2 行は
    CP-1 明示承認済)。
  - 新規/保留残課題: Lightweight Tier1 切替判断を F-gemini-quality-tier-poc
    に保留 (内包課題化)。config.py:77-79 default 不一致整合を ★低 で残置。
  - 関連: `docs/runs/F-gemini-model-migrate-emergency/REPORT.md` +
    trial_run_summary.json + environment_snapshot.json

- **F-gemini-model-audit (Gemini モデル戦略再検討 影響調査)**
  (F-gemini-model-audit / 2026-05-19 完了)
  - 発生バッチ: 5/25 `gemini-3.1-flash-lite-preview` shutdown + 2026-05
    Gemini API モデル群更新を受けた影響調査専用バッチ (改修なし、設計判断と
    実装の分離原則)。
  - 対応: main `4510180` から branch 作成、baseline 1417 passed 確認。
    grep で shutdown 対象の実稼働 functional 使用 = 2 箇所特定 (`.env` の
    QUALITY Tier3 + LIGHTWEIGHT Tier3、両系統とも fallback 位置)。コード
    default 3 箇所 (factory.py:316/324, config.py:76) + テンプレ
    `.env.example` + doc-drift コメント群を整理。★ 重大発見: shutdown 後の
    404 NOT_FOUND は retry.is_retryable()=False のため次 Tier フォール
    バックせず即 raise = 503 多発時に全生成失敗リスク。Interactions API
    未使用 (無関係)。出力 = `docs/runs/F-gemini-model-audit/` に
    REPORT.md + grep_results.json + current_tier_analysis.json +
    interactions_api_status.json + environment_snapshot.json。
  - CP-1 カズヤ判断 (2026-05-19): 選択肢1 = 両系統 Tier3 + config default
    + `.env.example` を `gemini-3.1-flash-lite` (GA) に一括置換 (404 即
    raise リスク完全除去 = 「動くものを壊さない」「あるべき姿で進める」)。
    404 対処は Tier 除去で足りる方針。Lightweight Tier1 切替タイミングは
    quota 確認後判断として保持。
  - 結果: `src/ tests/ configs/ scripts/ CLAUDE.md` 0 行変更、baseline
    1417 passed 維持。`docs/runs/F-gemini-model-audit/` 新規 +
    `docs/{CURRENT_STATE,DECISION_LOG,FUTURE_WORK,DISCUSSION_NOTES}.md`
    更新のみ。
  - 新規残課題: F-gemini-model-migrate-emergency (★★★ 緊急度 高、5/25
    deadline) + F-gemini-quality-tier-poc (緊急度 高、Phase A.5-3b 前)。
    F-gemini-503-stability-audit 撤回、F-periodic-health-check 緊急度
    高 → 中降格。
  - 関連: `docs/runs/F-gemini-model-audit/REPORT.md` + grep_results.json
    + current_tier_analysis.json + interactions_api_status.json

- **F-trial-run-candidate-a-reverify (候補A B-3' 改修後本番再確認)**
  (F-trial-run-candidate-a-reverify / 2026-05-19 完了)
  - 発生バッチ: F-trial-run-post-llm-extraction (2026-05-16) でカズヤ起案、
    Phase A.5-3b 第一作着手前の必須前提確認。
  - 対応: 改修後 main (`3c964c7`) で本番完全再現試運転 (batch_id
    20260518_111201, exit 0)。CP-1 で (1) 候補A `cls-6889e9e1c7ac` 不在
    (完全新規 RSS batch のため母集団に不在、F-1/F-2 で落ちたのではない)、
    (2) 動画化 Slot-1 台本が fallback テンプレ (Gemini 503 多発、
    `llm_error:RemoteProtocolError`) 判明 → カズヤ判断 = 選択肢3 (Task C/D
    のみ実施、Task E/CP-2 スキップ)。B-3' 構造的効果は 3 連続試運転
    (5/11 3T → 5/16 1T/2F → 5/18 0T/3F) で has_jp True 比率単調減少 = 確定。
  - 結果: 防衛機構 5 層全機能 (異常なし、即停止条件非該当)。候補A は
    perspective_gap framing で維持 (機械判定 ≠ 事実、perspective_gap は
    F-wl-hit-quality-audit 2026-05-14 で WebSearch 独立検証済)。Phase A.5-3b
    第一作着手 OK (前提最終確定)。`src/ tests/ configs/ scripts/ CLAUDE.md`
    0 行変更、baseline 1417 passed 維持、`docs/` + `data/output/` のみ更新。
  - 新規残課題: F-gemini-503-stability-audit (F-17 候補から昇格、緊急度 高、
    着手条件達成) + F-periodic-health-check (緊急度 高、Phase A.5-3d 前提)。
    axis_5 採点は Phase A.5-3b 第一作起案バッチに移送。
  - 関連: `docs/runs/F-trial-run-candidate-a-reverify/REPORT.md` +
    f13b_comparison.json + candidate_a_analysis.json + trial_run_summary.json

- **F-image-prompt-spec (ADR 3 件 + video_payload schema 拡張設計の固定化)**
  (F-image-prompt-spec / 2026-05-18 完了)
  - 発生バッチ: F-doc-backfill (2026-05-02) 登録、F-trial-run-post-llm-extraction
    (2026-05-16) でスコープ前提が現行実装と乖離 (image_prompt 非存在・4 scene・
    統一末尾なし) と判明、スコープ再定義要に更新。
  - 対応: 2026-05-16 の 3 AI 三角測量 3 ラウンド (claude.ai + ChatGPT + Gemini)
    で確立した D-minimal 仕様を ADR 3 件 + schema 拡張設計として正典化。
    Task B コード読解で事前調査結果を完全裏付け (想定外なし)。ADR-0001
    (画像戦略 C': 6-8 枚 + 10 イベント、5 色パレット、editorial 路線)、
    ADR-0002 (Remotion D-minimal 境界)、ADR-0003 (コンテンツモラル: 実在人物
    NG / ICRC 標章 NG / AI ラベル投稿前判定 / 高リスク事実公開前検証)。
    schema 拡張は現行 4 scene を壊さず images[]/events[] を新設・後方互換。
  - 結果: `src/ tests/ configs/ scripts/ CLAUDE.md` 0 行変更、baseline 1417
    passed 維持、`docs/` のみ更新。実装は一切せず設計のみ (Phase A.5-3b へ)。
  - 新規残課題: Phase A.5-3b 第一作起案 (緊急度 高、ADR + schema 前提) +
    第一作公開前の高リスク事実検証ワークフロー (緊急度 中、ADR-0003 由来)。
  - 関連: `docs/ADR/0001-0003`、`docs/runs/F-image-prompt-spec/REPORT.md` +
    current_schema_analysis.md + schema_extension_design.md、DECISION_LOG
    「2026-05-18: F-image-prompt-spec」エントリ。

- **F-jp-coverage-llm-judgement-extraction (LLM judgement bypass 根本治療)**
  (F-jp-coverage-llm-judgement-extraction / 2026-05-16 完了)
  - 発生バッチ: F-wl-hit-quality-audit (2026-05-14) Task D で LLM judgement
    bypass 問題 (Gemini が response_text で『該当しない』と明示判定しても
    F-13.B は WL マッチだけで True を返す設計欠陥) を確定。
  - 対応: Option (i) LLM response_text 判定抽出を `verify()` +
    `verify_two_stage()` 両方に実装。`_parse_llm_judgement` /
    `_extract_response_text` 新規 + dataclass optional フィールド拡張 +
    プロンプト回答形式指示 3 行追加。
  - 二段階設計プロセス: Task C-D で初版 B-3 表 (`uncertain→False`) 実装 →
    Task E ゴールデンセット 23 件再測定で **想定外退行検出** (Recall
    89.47%→37.50%、uncertain→False 過剰保守が主因 = クラウド誤り 9 自己
    事例) → Task E-fix で B-3' 表 (`no_match のみ False で覆す`) に根本治療。
  - 結果: baseline 1417 passed 維持 + 既存メソッド contract 完全不変。
    WL マッチ条件下評価で **Recall 1.0000 / Precision 0.8889 / FN=0** =
    B-3' は設計通り完璧に機能。ヘッドライン Recall 0.4706 は v3 run の
    broad Grounding 非決定性 (WL ヒット 0 が 11 件 + Gemini 503 が 2) で
    薄まる (本バッチスコープ外 → F-grounding-determinism-audit 起案)。
  - CP-3 でカズヤ + クラウド web 側協議 → 選択肢 1 (Task F-G 進行 + merge)
    確定。不変原則 3 例外 (src/triage) + scripts/ 例外 (measure script)
    の二箇所適用、DECISION_LOG 明記。
  - 関連: `docs/runs/F-jp-coverage-llm-judgement-extraction/REPORT.md`
    (主軸: WL マッチ条件下評価)、`design_spec.md` (v1 B-3) /
    `design_spec_v2.md` (v2 B-3')、DECISION_LOG「2026-05-16:
    F-jp-coverage-llm-judgement-extraction」エントリ。

- **F-trial-run-post-llm-extraction (B-3' 本番試運転 + 第一作題材確定)**
  (F-trial-run-post-llm-extraction / 2026-05-16 完了)
  - 発生バッチ: F-jp-coverage-llm-judgement-extraction (2026-05-16) で
    起案。B-3' 改修後 main (ba51e5f) の本番試運転で改修後挙動 + 防衛機構
    5 層影響 + 第一作題材ランク再評価。
  - 対応: production-pipeline 試運転 (batch_id=20260516_030927)。
    **★★★ B-3' が production verify() に確かに配線・本番で安全装置初発火**
    (Slot-3 cls-02e505cc1310: WL tier_2 matched=1 + llm_judgement=no_match
    → has_jp_coverage=False に B-3' で覆った)。has_jp_coverage 分布が
    F-trial-run-post-tune の 3/3 True (bare-domain bypass) → 1 True /
    2 False に反転 = LLM judgement bypass の構造的解消を本番実証。
    Slot-1 WL 品質も afpbb bare-domain → tier_1 実名紙 2 件に向上。
  - 防衛機構 5 層全機能 (F-1 369→20、F-2 Blocked 0、F-13.B B-3' 安全装置
    1 件、F-5 救済 1 件、F-13 隠れ層 0 件 = quality floor ブロック自体なし)。
  - axis_5: 候補B cls-e2429c77f48e = 15/25 (punchline メディア断定が
    「中間が良い」原則と矛盾 + Meduza 単独+露発二重バイアス + 専門性過多)。
  - 第一作題材確定 = **選択肢4: 候補A cls-6889e9e1c7ac を perspective_gap
    framing で確定** (editorial_mission=86.0 機械1位、TeleSUR発、axis_5
    試算 19/25、framing 指針 4 点)。
  - F-image-prompt-spec 事前調査: video_payload は image_prompt 非存在 /
    4 scene / 統一末尾なし = スコープ再定義要 (緊急度 高に反映)。
  - 新規残課題起案: F-trial-run-candidate-a-reverify (候補A の B-3' 改修後
    再確認、第一作着手前必須) + F-image-prompt-spec スコープ再定義。
  - `src/ tests/ configs/ scripts/ CLAUDE.md` 0 行変更、`docs/` +
    `data/output/` のみ更新、baseline 1417 passed 維持。
  - 関連: `docs/runs/F-trial-run-post-llm-extraction/REPORT.md` +
    f13b_output_analysis.json + video_payload_audit.json +
    axis_5_evaluation.json、DECISION_LOG「2026-05-16:
    F-trial-run-post-llm-extraction」エントリ。

- **F-13.B WL ヒット品質の独立検証 (F-wl-hit-quality-audit)** (F-wl-hit-quality-audit /
  2026-05-14 完了)
  - 発生バッチ: F-trial-run-post-tune (2026-05-11) で 試運転 3 Slot 全件 has_jp_coverage=True
    + matched_urls が全件ベアドメインのみ (`https://afpbb.com` / `https://nippon.com`、
    article path なし) という挙動が観察され、Grounding API の chunk.web.title 抽出経路で
    『afpbb.com』等の文字列をドメイン形式として識別 + `_domain_matches_hierarchy` 階層
    判定で Tier 認定する仕組みが、「当該事象を実際に報道している」ことを保証しない
    (= 誤陽性リスク) ことが懸念された。本バッチで独立検証を実施。
  - 対応内容: (Task A) ブランチ作成 + 環境スナップショット (main HEAD `eb0dd5e`、
    baseline 1390 passed)。(Task B) 試運転 3 Slot の WebSearch 後追い検証 = Slot-1 (Israel
    9,600 Detainees) が afpbb で 9,600 数字 + 虐待を継続報道 = **TP**、Slot-2 (Channel 4
    `Doctors Under Attack` BAFTA 受賞) が afpbb で別事象 (`How to Survive Warzone Gaza`
    Ofcom 制裁 `3604087`) のみ = **Suspect FP 確定**、Slot-3 (Tehran 降伏フレーミング)
    が nippon.com で類似トピック家系報道 = **Topic-Level TP / Specific Partial**。
    (Task C) ゴールデンセット TP 17 件から seed=42 で 5 件サンプリング検証 = blind_008 /
    blind_009 が Topic-Level TP、blind_002 が Topic-Level TP / Specific Suspect FP
    (Jesus 像破壊 itself は afpbb 報道、Rabbinate 沈黙の specific 角度は不在)、covered_008
    が TP Confirmed (nippon.com direct match)、cls-a4132ec7d949 が Specific Event Suspect
    FP (Met Police シナゴーグ法的苦情、afpbb で specific event 不在)。**CP 中間レポート
    提出 → カズヤ判断**: Task D は Slot-2 のみ実施 (診断価値最大)、Slot-1 系統判定は両論
    併記で保留、F1 信頼性は本バッチ記録のみで REPORT v2 化は別バッチ。(Task D)
    `scripts/dump_grounding_chunks.py` 新規作成、Slot-2 で Grounding chunk 8 件取得
    (7.51 秒、≒$0.05)。**★★★ 決定的発見**: Gemini LLM 自身が response_text で『指定された
    ニュース [...] とは異なる内容で、かつ日付も異なります』と明示判定しているのに、
    F-13.B は chunk の WL マッチだけで True を返している = **LLM judgement bypass の
    設計判断レベルの欠陥**。chunk.web 構造の確認: 全 8 件で web_uri = Vertex AI redirect
    URL のみ (decode 不可)、web_title = ドメイン名のみ (article path なし)、web_domain =
    None (戦略 1 未実装)。(Task E) 構造的理解 + 改善案 5 オプション整理、Option (i)
    LLM response_text 判定抽出 = 推奨 (工数 4-8h、Recall -5〜-10pp / Precision +20〜+40pp
    想定、不変原則 3 例外条件適用要)。Option (ii)(iii) は Task D 発見で無効化、Option
    (iv) 別 API 移行は F-jp-coverage-tune-followup-2 統合候補、Option (v) クエリ品質改善
    は補助。(Task F) 統合 REPORT.md + Slot-1 系統判定両論併記 + 第一作着手判断材料 +
    残課題リスト。(Task G) BATCH_PROTOCOL Task 1-5 ドッグフーディング。
  - 重要な発見 / 観察:
    (1) ★★★ **F-13.B 現実装は LLM response_text 判定を完全に無視し、chunk のドメイン抽出
    + WL 階層マッチのみで True/False を決定** = 根本原因 (d) LLM judgement bypass を確定。
    Grounding API 仕様 (article path 取得不能) と組み合わせて、broader topic 一致のみで
    True 返却する構造的弱点が顕在化。
    (2) ★ **Slot-1 cls-6889e9e1c7ac の系統判定 = perspective_gap 確定** (afpbb で 9,600
    数字 + 虐待を継続報道済み = 真の silence_gap ではない)。第一作起案で『日本未報道』
    というブランドメッセージで売り出すのは事実と矛盾、台本表現は『日本でも事象は報道
    されたが、TeleSUR が掘った構造 (ICRC 訪問操作疑惑等) は触れられていない』
    perspective_gap 型が正しい。第一作着手判断は両論併記でカズヤ判断待ち。
    (3) ★ **F-jp-coverage-tune-followup Step C メトリクス (F1 covered 0.8718 / Recall
    covered 89.47% / Precision blind 33.33%) は broader topic-family level の値** = specific
    event (= particular_angle) level では下振れの可能性。試運転 + golden サンプリング
    8 件中 3 件 (37.5%) で topic-family 一致 / specific 不一致パターンが観察された。
    (4) ★ **改善案 = Option (i) LLM response_text 判定抽出** が根本治療。本バッチでは
    実装せず、別バッチ案件 `F-jp-coverage-llm-judgement-extraction` として記録。
    `src/triage/jp_coverage_verifier.py` 改修必要 = 不変原則 3 例外条件 (実装バグ修正 +
    設計変更ではない + DECISION_LOG 明記 + Hydrangea ミッション中核機構、4 条件全) で
    カズヤ承認必須。
  - 残課題:
    1. `F-jp-coverage-llm-judgement-extraction` (Option (i) 実装、緊急度 高、本バッチで
       FUTURE_WORK 新規追加済み)
    2. F-jp-coverage-tune-followup REPORT v2 化 (broader vs specific caveat、緊急度 高、
       F-jp-coverage-llm-judgement-extraction 再測定値と統合推奨)
    3. ゴールデンセット v2 化検討 (specific angle truth annotation、F-jp-coverage-llm-judgement-extraction
       着手前 OR 並走推奨)
    4. Phase A.5-3b 第一作着手判断: Slot-1 を perspective_gap framing で起案する (Option A)
       か、別題材選定 (Option B) か、Option (i) 実装後に着手する (Option B' 統合) か =
       カズヤ判断要
  - 関連ファイル: 新規 `scripts/dump_grounding_chunks.py` + `docs/runs/F-wl-hit-quality-audit/`
    配下 8 ファイル (REPORT.md + 5 JSON + 1 MD + 1 environment_snapshot.json) +
    `docs/CURRENT_STATE.md` 全置換 + `docs/DECISION_LOG.md` 末尾追加 + `docs/FUTURE_WORK.md`
    本エントリ完了済み移動 + 新規残課題 3 件追加 + `docs/DISCUSSION_NOTES.md` 4-A 新規 1 件
    + 4-B 既存 1 件再評価。リグレッション影響なし (`src/` `tests/` `configs/` `CLAUDE.md`
    0 行変更、baseline 1390 passed 維持)。

- **F-jp-coverage-tune-followup マージ後の本番試運転 + Phase A.5-3b 第一作
  題材候補ランク付け (F-trial-run-post-tune)** (F-trial-run-post-tune /
  2026-05-11 完了)
  - 発生バッチ: F-jp-coverage-tune-followup (2026-05-09 merge) で `_match_whitelist`
    階層判定化 + WL 30 ドメイン化の大改修が入り、独立 23 件ゴールデンセット評価では
    F1 covered 0.8718 で threshold 初突破まで到達。ただし **改修後の本番運用での
    実挙動は未検証**だった。本バッチで試運転 + 防衛機構 5 層監査 + 拾われた Slot の
    台本品質確認 + 第一作題材ランク付けの 4 角度を統合実施。「動くものを壊さない」
    哲学 (= F-trial-run-post-fix 踏襲) で `src/` `tests/` `configs/` `scripts/`
    全て不変、`docs/` のみ更新する設計。
  - 対応内容: (Task A) ブランチ作成 + 環境スナップショット (main HEAD `4062639`、
    baseline 1390 passed、jp_coverage_cache 9 records、AUDIO/VIDEO_RENDER_ENABLED
    デフォルト false 確認)。(Task B) `python -m src.ingestion.run_ingestion` で
    RSS 取得 (41 ソース中 40 成功、47 raw → 1229 new → 469 garbage 除去後)、
    `python -m src.main --mode normalized` で試運転 (20.4 分、batch_id=20260511_044914、
    job_id=cbe56961...、status=completed、3 Slot 選定 = Slot-1 cls-6889e9e1c7ac
    "9,600 Detainees: Israel Prison Abuses" + Slot-2 cls-1a38c0ca8c99 "Filmmakers
    slam BBC after Gaza documentary" + Slot-3 cls-03892eab2072 "Tehran says US
    proposal sought Iran's surrender"、F-13.B 3 invocations 全 has_jp_coverage=True
    で afpbb x2 + nippon x1 にヒット、F-trial-run-post-fix から完全反転)。
    (Task C) `f13b_output_analysis.json` に試運転 3 invocations 集計 (True 3 /
    False 0 / Error 0、WL 拡張ドメインのみがヒット、excluded URLs Slot-1 youtube
    1 件のみ) + F-trial-run-post-fix との比較 (has_jp_coverage 0/3 → 3/3 完全反転)
    + verify_two_stage 機械判別が本番未配線である状況の clarification を保存。
    (Task D) `defense_layers_audit.json` に防衛機構 5 層発火状況保存 (F-1 20/304
    通過 threshold 45.0、F-2 全通過、F-13.B 3 invocations 全 True、F-5 救済 1 件
    (cls-da0a74aa712d、Top-3 選定外)、F-13 隠れ層 quality_floor_miss bypass 発火
    1 件 (Slot-1、editorial_mission_score=86.0 + analysis_result=none で fired))、
    all_5_layers_functional=true。(Task E) `script_quality_audit.json` に Slot-1
    台本品質保存 (Hook 18字 数字提示型 / Setup 90字 / Twist 179字 / Punchline 87字
    シニカル × 視聴者直接質問 + loop-3 帰着、全 char_bounds 内、NG 語彙ゼロ、
    Pattern=Media Critique、total 80s、analysis_result=null で新ルート未起動 +
    particular_angle_metadata/sontaku_signals 本番未配線も記録)。(Task F)
    `first_video_candidate_ranking.{json,md}` に第一作題材 5 軸採点 (4 軸機械
    + 1 軸カズヤ主観空欄)、機械スコア Slot-1 (10pt) > Slot-2 (6pt) > Slot-3 (5pt)、
    Slot-1 が axis_1 (Hydrangea ミッション)=5 + axis_4 (台本品質、唯一 script
    生成)=4 で大差勝ち。(Task G) 統合 REPORT.md + BATCH_PROTOCOL Task 1-5
    ドッグフーディング。リグレッション影響なし (`src/` `tests/` `configs/`
    `scripts/` `CLAUDE.md` 0 行変更、`docs/runs/F-trial-run-post-tune/` 新規 10
    ファイル + `docs/` 既存 4 ファイル更新のみ、baseline 1390 passed 維持)。
  - 重要な発見 / 観察:
    (1) ★ **WL 拡張 3 ドメインのうち 2 つ (afpbb / nippon) が本番試運転 3 Slot
    全件にヒット** = F-trial-run-post-fix から **完全反転** (0/3 → 3/3)。WL 拡張
    の本番影響は想定以上に強い。
    (2) ★ **matched_urls がベアドメインのみ** (3/3 で `https://afpbb.com` /
    `https://nippon.com` のみ、article path なし) = Grounding chunk.web.title
    抽出経路で識別された結果、記事レベル一致は不明 (= **誤陽性のリスク**)。
    F-jp-coverage-tune-followup measurement Step C (Recall covered 89.47%) も
    同じ抽出経路を経るため同等の懸念あり。FUTURE_WORK で「F-13.B WL ヒット品質
    の独立検証」を新規追加。
    (3) ★ **Hydrangea ブランドメッセージ (blind_spot_global) が機械判別で消滅**:
    3/3 で has_jp_coverage=True → 全 Slot が divergence ルート。Slot-3 (judge
    blind_spot_global 認定 score=9.0) と F-13.B (nippon Tier 4 でヒット) が
    結論不一致。F-stream-2-filter-design 責務範囲再評価で対処方向性を整理。
    (4) ★ **production-pipeline と docs 概念整理の乖離が顕在化**: src/main.py:3187
    は legacy verify() (broad-only) のみ呼び出し、verify_two_stage / 系統 1/2/3
    機械判別 / particular_angle_metadata / sontaku_signals 全て本番未配線
    (src/ 配下 grep でヒット 0 件)。Slot-1 で `analysis_result=null` + F-13 隠れ層
    quality_floor_miss bypass 発火 = 新ルート未起動。FUTURE_WORK で 3 件の本番
    配線判断バッチを新規追加。
    (5) ★ **Slot-1 cls-6889e9e1c7ac が第一作の最有力候補**: editorial_mission_score=86.0
    (本試運転最高) + Hydrangea ど真ん中 (人権・忖度・systemic suppression) +
    台本品質 axis_4=4pt + 唯一 video_payload 生成済み = 機械スコア 10pt で 2 位以下に
    大差。最終判断はカズヤ axis_5 主観評価後。
    (6) ★ **「動くものを壊さない」哲学の運用実証**: 本バッチは試運転 + 観察 +
    記録に集中する性格で、`src/` `tests/` `configs/` `scripts/` 0 行変更、
    `docs/` 配下のみ更新で完結。F-particular-angle-design 以降の連続バッチで
    最も「観察と記録に集中」した性格。
  - 残課題 (FUTURE_WORK 緊急度 高に追加): (1) F-13.B WL ヒット品質の独立検証 ★高
    (matched_urls ベアドメイン問題、誤陽性リスク)、(2) verify_two_stage 本番配線
    判断 (production-pipeline と docs 概念整理の乖離解消)、(3) particular_angle_metadata
    + sontaku_signals 本番配線判断 (新ルート起動条件)、(4) F-stream-2-filter-design
    責務範囲再評価 (本番運用視点反映)
  - baseline 影響: 1390 → 1390 passed (0 件変更、src/ tests/ configs/ scripts/
    全て不変、CLAUDE.md も不変、docs/ のみ更新)。
  - 関連ファイル: `docs/runs/F-trial-run-post-tune/REPORT.md` (本バッチ統合
    レポート)、`docs/runs/F-trial-run-post-tune/{environment_snapshot,trial_run_log,
    f13b_output_analysis,defense_layers_audit,script_quality_audit,
    first_video_candidate_ranking}.{json,md,txt}`、`docs/CURRENT_STATE.md`
    (全置換更新)、`docs/DECISION_LOG.md` (本バッチエントリ追加)、
    `docs/FUTURE_WORK.md` (本エントリ完了済み移動 + 新規残課題 4 件追加)、
    `docs/DISCUSSION_NOTES.md` (新規 2 件追加 + 既存 3 件更新)

- **WL マッチング階層判定化 + WL 拡張 3 ドメイン (verdict=fail のまま、ただし
  Recall covered +47.36pp / F1 covered +27.92pp 改善 + F1 covered 0.8718 で
  threshold 初突破) (F-jp-coverage-tune-followup)** (F-jp-coverage-tune-followup
  / 2026-05-09 完了)
  - 発生バッチ: F-jp-coverage-tune (2026-05-09, commit `beb4aa7`/merge `82ce0d0`)
    の post-tuning verdict=fail を受けて、verdict=fail の根本原因を 3 つに分解
    (= WL サブドメイン不一致 / WL 漏れ準大手 / Grounding API 構造的限界) し、
    本バッチで前 2 つを根本治療する目的で起動。Step A→B→C→D→E の単一バッチ
    構成、Step C で CP-3 中間チェックポイント設置の上 Step D 着手可否をカズヤ
    判断する設計。
  - 対応内容: (Step A) `src/triage/jp_coverage_verifier.py` の
    `_match_whitelist()` 内のドメイン判定を **substring match → ドメイン階層
    判定** に置換、新規モジュール関数 `_domain_matches_hierarchy(host, wl_domain)`
    追加 (完全一致 / host が wl の子孫 / wl が host の子孫 のいずれかでマッチ、
    TLD 共通や部分文字列はマッチしない)。(Step B) `JP_MEDIA_WHITELIST` 定数に
    3 ドメイン追加 = `afpbb.com` (Tier 2) / `forbesjapan.com` (Tier 4) /
    `nippon.com` (Tier 4)。議論余地 2 件 (`arabnews.jp` / `chosunonline.com`)
    は本バッチで保留。(Step C) `scripts/measure_two_stage_accuracy.py` を独立
    23 件で再実行、`docs/runs/F-jp-coverage-tune-followup/measurement_result_step_c.json`
    + per-event ログ 23 件生成。CP-3 中間レポートをカズヤに提示。(Step D)
    ★ カズヤ判断で **スキップ** (= 「対症療法じゃなく根本治療」原則 + Recall
    0.53pp 不足のためだけに API 4 倍コスト + Step D 実施しても Precision blind
    80% / Tier 一致率 70% には到達しない)。(Step E) BATCH_PROTOCOL Task 1-5
    ドッグフーディング (REPORT.md 新規 + DECISION_LOG エントリ + FUTURE_WORK
    完了済み移動 + 4 つの残課題分離追加 + DISCUSSION_NOTES Grounding API 構造的
    限界エントリを部分的解消で更新 + CURRENT_STATE 全置換更新)。
  - 重要な発見 / 観察:
    (1) ★ **F1 covered が threshold 初突破** (0.5926 → 0.8718、+0.2792)。
    F-13.B の Recall/Precision/F1 系列で F1 が threshold 0.85 を超えたのは本
    バッチが初。
    (2) **Recall covered +47.36pp 改善** (42.11% → 89.47%、threshold 90% **0.53pp
    不足**)。WL 拡張 + 階層判定化で 9 件の broad FN→TP 改善 (blind_004/005/008,
    covered_006/007/010, cls-7bd1406438b6/6be4fc09d9ed/a4132ec7d949)。
    (3) **退行 3 件** (TN→FP): blind_003 / blind_007 / cls-0c7fa7c667d6 が新追加
    nippon.com / newsweekjapan.jp / afpbb.com 経由でヒット。**WL 拡張のトレード
    オフ**。これらは真値再評価の余地もあるが、本バッチでは保守的方針 (真値変更
    せず FP 計上) を維持。
    (4) **残 FN 2 件の構造分析**: blind_010 (Zionism crisis 論考) は論考型で
    日本主要メディアが取り上げていない事実上の構造的欠落 = 多クエリでも改善困難。
    covered_003 (米中関税協議) は Grounding が政府系 (jetro) / 研究機関 (dir /
    cistec) / アグリゲータ偏重で日経・朝日等を引き当てられない典型ケース = 多
    クエリ + キーワードバリエーションで救済可能性高。
    (5) **Tier 一致率 / Stream accuracy 退行は本バッチスコープ外の直交課題**:
    Tier 一致率は Grounding API 非決定性 (同 event でも chunk 構成が揺れる)、
    Stream accuracy は stream_3 過剰検出 (DISCUSSION_NOTES 既存エントリの顕在化)。
    どちらも Step D では解消しない別系問題、4 軸分離で FUTURE_WORK 記録。
    (6) **「対症療法じゃなく根本治療」原則の運用実証**: Step C 中間チェック
    ポイントで Step D 着手可否をカズヤ判断する設計が、verdict=fail 根本原因の
    3 分解 → WL 整備で半分以上解消 → 残課題 4 軸分離 という収束をもたらした。
    F-jp-coverage-tune CP-1/CP-2 中間チェックポイント方式 (2026-05-09 確立) の
    踏襲かつ深化版。
  - 残課題 (4 軸に分離して FUTURE_WORK 記録): (a) Recall 90% 突破 = F-jp-coverage-tune-followup-2
    候補、(b) Precision blind 母数問題 = Phase A.5-3b 第二作、(c) Tier 一致率
    Grounding 非決定性 = 単独バッチ or F-jp-coverage-tune-followup-2 と統合、
    (d) Stream accuracy stream_3 過剰検出 = F-stream-2-filter-design 責務範囲。
    議論余地 2 ドメイン (`arabnews.jp` / `chosunonline.com`) の WL 採用判断は
    後続バッチで判定。
  - 不変原則例外: 不変原則 3 (`src/triage/` 既存ファイル変更不可) に対し、例外
    条件 4 つ全部 (バグ修正 + データ追加のみ / 既存メソッド完全維持 / baseline
    維持 / カズヤ承認済) を満たすことを確認した上で `_match_whitelist` 内の
    判定ロジック修正 + 新モジュール関数追加 + WL データ追加を実施。既存
    `verify()` / `verify_two_stage()` / `_search_with_grounding` /
    `_search_with_grounding_two_stage` / `_filter_excluded` のシグネチャ・挙動
    完全不変、`_match_whitelist` は内部判定ロジックのみ修正で戻り値 contract 不変。
  - baseline 影響: 1364 → **1390 passed** (新規 26 件追加、既存 1364 件全件
    維持)。新規テストは `tests/test_jp_coverage_verifier_domain_extract.py` に
    3 クラス追加 (`TestDomainMatchesHierarchy` 9 件 + `TestWhitelistMatchSubdomainAbsorption`
    8 件 + `TestWhitelistExtension` 9 件)。
  - 関連ファイル: `src/triage/jp_coverage_verifier.py` (`_match_whitelist`
    階層判定化 + `_domain_matches_hierarchy` 新規 + `JP_MEDIA_WHITELIST` 3
    ドメイン追加)、`tests/test_jp_coverage_verifier_domain_extract.py` (+26
    件)、`docs/runs/F-jp-coverage-tune-followup/REPORT.md` (新規)、
    `docs/runs/F-jp-coverage-tune-followup/measurement_result_step_c.json` +
    `logs/<event_id>.log` × 23 件 (新規)、`docs/CURRENT_STATE.md`
    `docs/DECISION_LOG.md` `docs/FUTURE_WORK.md` `docs/DISCUSSION_NOTES.md`
    (本バッチ反映)

- **F-13.B 二段階クエリ生成改修 (verify_two_stage 実装 + 独立 23 件精度測定 +
  (c) dateRestrict 除去 1 回チューニング、verdict=fail) (F-jp-coverage-tune)**
  (F-jp-coverage-tune / 2026-05-09 完了)
  - 発生バッチ: F-task-e-finalize (2026-05-08) で Task E カズヤレビュー結果
    反映が完了し、Phase A.5-3a-verify ゲート完了後の 5 連続バッチを経て真値
    25 件 (独立 23 件) + sontaku_signals 整備済み + 4 運用原則確立で
    F-jp-coverage-tune 着手の前提が完全に整った。F-13.B の構造的限界 (= 系統 2
    perspective_gap = 80% を全部弾く) を解消する目的で、**新メソッド
    `verify_two_stage()` 追加 + 二段階クエリ生成で系統 1 / 2 / 3 / unknown
    機械判別** + 独立 23 件精度測定 + 1 回限りチューニングを実施。
  - 対応内容: (Step 1) `src/triage/jp_coverage_verifier.py` に **新規追加のみ**
    で実装 = `TwoStageVerifyResult` dataclass + `verify_two_stage()` 本体メソッド
    + `_build_broad_query()` (既存 `_build_search_query` への薄いラッパ) +
    `_build_angle_query()` (LLM で `particular_angle.core_question` から短い
    日本語検索クエリ生成、失敗時は簡易 fallback) + `_fallback_angle_query()` +
    `_search_with_grounding_two_stage()` (per-call timeout 対応) +
    `_call_with_timeout()` (ThreadPoolExecutor 経由、graceful fallback の基盤)。
    既存 `verify()` / `_build_search_query` / `_search_with_grounding` /
    `_filter_excluded` / `_match_whitelist` 完全不変、不変原則 3 例外条件 4 つ
    (バグ修正ではない設計拡張 / 既存メソッド完全維持 / baseline 維持 / カズヤ
    承認済) 全部適用。(Step 2) `tests/test_jp_coverage_verifier_two_stage.py`
    新規 19 件 (stream_1/2/3/unknown 分岐 / Step 2 skip 確認 / LLM fallback /
    フォーマット正規化 / 既存 verify() 不変性確認)。baseline 1345 → 1364 passed。
    (Step 3) `scripts/measure_two_stage_accuracy.py` 新規作成 + 独立 23 件で
    実行 (重複 2 ペア除外 = blind_005 / blind_004 採用、cls-33b4f4960bf9_7K /
    cls-204a683f73ee_7K 除外)。pre-tuning 結果: Recall covered 31.58% /
    Precision blind 23.53% / F1 0.4800 / Tier 一致率 66.67% / Stream accuracy
    31.82% = **verdict=fail**。FN 13 件中の broad 検索結果分析で 13 件の根本
    原因が判明。(Step 4) CP-2 でカズヤ判断: **(c) dateRestrict プロンプト埋め
    込み除去** を 1 回試行。`_search_with_grounding_two_stage` のプロンプト
    本文から日付制約文を削除 (パラメータ自体は backward-compat で残置)。
    post-tuning 結果: Recall covered **42.11%** (+10.53pp) / Precision blind
    26.67% (+3.14pp) / F1 0.5926 (+0.1126) / Tier 一致率 62.50% (-4.17pp、
    僅差) / Stream accuracy 27.27% (-4.55pp、stream_3 過剰検出 3→6 件) =
    **verdict=fail のまま**。(Step 5) BATCH_PROTOCOL Task 1-5 ドッグフーディング
    (DECISION_LOG エントリ + FUTURE_WORK 完了済み移動 + F-jp-coverage-tune-followup
    ★最優先新規追加 + DISCUSSION_NOTES 新規 2 エントリ + CURRENT_STATE 全置換更新)。
  - 重要な発見 / 観察:
    (1) ★ **Grounding API の構造的限界が明確化** (本バッチで発覚、followup 起案
    根拠): 1 クエリあたり 5-10 chunk しか返さない / 上位ヒットが WL 外で埋まる
    (chiba-tv.com / hatena.ne.jp / msf.or.jp / nippon.com / forbesjapan.com /
    afpbb.com 等) / 0 URL 返却ケース複数。verify_two_stage 固有ではなく
    F-13.B 全体の課題。1 回のチューニングで verdict=pass に到達するのは構造的
    に困難。
    (2) **dateRestrict プロンプト埋め込みの副作用は部分的に効いていた**:
    +10.53pp 改善は確かに発生したが、旧 F-13.B 水準 (Recall 71.43%) には届かず
    = 残る under-recall は Grounding API 構造的限界に起因。
    (3) **stream_3 過剰検出 (定義レベルの限界、本バッチスコープ外)**:
    post-tuning で 6 件 (blind_002 / blind_009 / covered_001 / covered_002 /
    covered_004 / covered_009) が真値「特定角度は未報道」だが angle 検索で
    diamond.jp / yomiuri.co.jp / newsweekjapan.jp / asahi.com がヒット →
    stream_3 誤判定。LLM truth は「特定角度を扱った記事 ≠ 広範事件のついでに
    触れた記事」と厳格区別、URL マッチング側はドメインヒット粒度しか見ない
    定義レベルの限界。後続バッチで議論。
    (4) **graceful fallback / per-call timeout / incremental save / resume**
    の全機能が安定動作: 23 件中 unknown 0 件、graceful fallback 発火 0 件、
    total elapsed 322s (pre) / 341s (post)、平均 14-15s/件。
    (5) **正しく stream_2 を捕捉できたケース 3 件** (post-tuning では 2 件):
    covered_002 (米ロ首脳停戦) / covered_003 (米中関税) / covered_008 (マリ
    国防相暗殺) — broad で yomiuri / nikkei / asahi 等の Tier 1 マッチ + angle
    が WL 外で正しく stream_2 確定。
  - 残課題: ★ **F-jp-coverage-tune-followup** (★最優先、緊急度 高) で
    Grounding API 構造的限界対策 = (p) 複数クエリ並列発行 + 結果統合 (★最有力
    候補) / (q) 検索 API 変更検討 (Google Custom Search 移行 等) / (r) WL
    ドメイン拡張検討 (forbesjapan / nippon.com / afpbb 追加) / (s) stream_3
    過剰検出解消 (angle 検索結果に LLM 解説価値判定追加) を議論。
  - 関連ファイル: `src/triage/jp_coverage_verifier.py` (新規 dataclass + 新規
    メソッド + 既存メソッド完全不変、+約 290 行)、
    `tests/test_jp_coverage_verifier_two_stage.py` (新規 19 件)、
    `scripts/measure_two_stage_accuracy.py` (新規)、
    `docs/runs/F-jp-coverage-tune/measurement_result.json` (post-tuning 最終)、
    `docs/runs/F-jp-coverage-tune/measurement_result_pre_tuning.json` (Step 4
    前のベースライン保存)、`docs/runs/F-jp-coverage-tune/logs/` 23 件、
    `docs/CURRENT_STATE.md` `docs/DECISION_LOG.md` `docs/FUTURE_WORK.md`
    `docs/DISCUSSION_NOTES.md` (本バッチ反映)

- **Task E カズヤレビュー結果反映 + finalize_annotations.py 実行 + 4 運用
  原則 docs 化 (F-task-e-finalize)** (F-task-e-finalize / 2026-05-08 完了)
  - 発生バッチ: F-particular-angle-redesign Task E (4 分類版 + sontaku_signals
    込みカズヤレビュー、25 件) がクラウド対話形式で完了。25 件全件 LLM 推定
    値そのまま採用 (= `kazuya_review.*_revised` 全件 null)、4 つの運用原則
    確立 + 1 つの構造的問題発覚 + (c) サンプル選定バイアス仮説の証拠強化を
    反映するための統合バッチ。
  - 対応内容: (Step 1) `python scripts/finalize_annotations.py
    --schema-version 2.0 ...` 実行で `annotation_diff.json` /
    `stream_classification.json` / `golden_set.json` 生成更新。25 件全件
    `final_stream_source=llm_estimate` /
    `final_sontaku_signals_source=llm_estimate`。(Step 2) DISCUSSION_NOTES
    に新規 4 エントリ追加 (運用原則 3 件 + 重複問題 1 件) + 既存 1 エントリ
    追記 ((c) 仮説証拠強化、ステータス Active 維持で根本治療を Phase A.5-3b
    第二作に明示) + REPORT.md セクション 12 (Task E カズヤレビュー実施結果)
    追加 + DECISION_LOG / FUTURE_WORK / CURRENT_STATE のドッグフーディング。
    コード変更ゼロ、`finalize_annotations.py` は既存スクリプトの実行のみ。
  - 重要な発見 / 観察: (1) **「LLM の知性に委ねる」原則の実証**: 25 件全件
    LLM 推定値そのまま採用 = カズヤ哲学「LLM の膨大な知識による評価・判定を
    信用したい」と整合。(2) **「観点の選択的欠落 = 忖度」判定軸の確立**:
    主要扱い事象なのに特定角度だけ抜ける = リソース不足ではなく忖度、これに
    より Hydrangea コアミッションの射程が明確化。(3) **(c) サンプル選定
    バイアス仮説の裏付け**: stream_3 に再分類される件は 0 件、根本治療は
    Phase A.5-3b 第二作のサンプル拡充。(4) **試運転 / golden_set 重複問題**:
    25 件中 2 ペア (4 件) が同一 MEE 記事の重複 = 独立件数は実質 23 件。
  - 残課題: F-jp-coverage-tune ★最優先着手 OK (真値 25 件 + sontaku_signals
    真値整備完了)。F-stream-2-filter-design は stream_3 = 0 件確定で小規模
    実装の可能性が高い、Phase A.5-3b 第二作のサンプル拡充後に再評価。
    Phase A.5-3b 第二作で系統 3 事象 (処理水放出 / 辺野古 等) のサンプル
    拡充検討 — (c) 仮説検証 + 系統 3 台本表現試行錯誤を兼ねる。F-1
    EditorialMissionFilter 着手時に本バッチの 4 運用原則を設計レビューで参照。
  - 関連ファイル: `docs/runs/F-particular-angle-design/annotation_diff.json`
    (新規)、`docs/runs/F-particular-angle-design/stream_classification.json`
    (新規)、`docs/runs/F-verify-jp-coverage/golden_set.json` (更新)、
    `docs/runs/F-verify-jp-coverage/golden_set_v1.1.json` (バックアップ自動
    生成)、`docs/DISCUSSION_NOTES.md` (新規 4 エントリ + 既存 1 エントリ
    追記 + ヘッダ更新)、`docs/runs/F-particular-angle-redesign/REPORT.md`
    (セクション 12 追加)、`docs/CURRENT_STATE.md` `docs/DECISION_LOG.md`
    `docs/FUTURE_WORK.md` (本バッチ反映)

- **stream_3=0 件 (c) 仮説追記 + sontaku_signals type 分布バイアス記録 + finalize_annotations.py の sontaku_signals 対応 (F-extension-followup)** (F-extension-followup / 2026-05-08 完了)
  - 発生バッチ: F-particular-angle-redesign-extension (2026-05-08, commit `6a8efc4` / merge `2c9ee96`) のクラウドレビューで指摘された 3 件 (sontaku_signals type 分布のサンプル設計バイアス / stream_3=0 件問題の (c) サンプル選定バイアス説 / Task E 着手前の finalize_annotations.py の sontaku_signals 対応確認) を反映するためのフォローアップ。
  - 対応内容: (Task A) `docs/DISCUSSION_NOTES.md` の既存「2026-05-08: 4 分類化で stream_3 = 0 件 / stream_2 = 20 件」エントリに **(c) サンプル選定バイアス説** (前チャットでカズヤ提起、25 件サンプルが海外メディア独自視点中心で真の系統 3 候補が偶然含まれていなかった可能性) を追記、ステータスを `Resolved` → `Active (要カズヤ判別 + サンプル拡充検討)` に降格、「カズヤレビューで判別する」セクションに (c) の判別フロー追加。新規エントリ「2026-05-08: sontaku_signals type 分布のサンプル設計バイアス」追加 (Active、Phase A.5-3b 第二作 + F-1 EditorialMissionFilter 設計時に再評価)。(Task B) `scripts/finalize_annotations.py` の sontaku_signals 対応確認 = **(c) 未対応** (4 関数で sontaku_signals / sontaku_signals_revised 両フィールドが完全にスルー)。最小修正で対応: `_resolve_final()` に `final_sontaku_signals` / `final_sontaku_signals_source` 追加 (null → LLM 推定値継承、object → 全フィールド上書き、フィールド単位 partial merge は未実装)、`build_stream_classification()` の event 出力に sontaku_signals 反映、`update_golden_set()` で schema 2.0 のとき entry に sontaku_signals 反映 + meta に source 記録、`build_annotation_diff()` に `sontaku_signals_revised_count` + diff entry に `sontaku_signals_revised` フラグ追加。既存関数のシグネチャ・戻り値構造は維持 (新キー追加のみ)。(Task C) BATCH_PROTOCOL Task 1-5 ドッグフーディング (DECISION_LOG エントリ + 本エントリ追加 + DISCUSSION_NOTES Task A で実施済み + CURRENT_STATE 全置換更新)。
  - 重要な発見 / 観察: (1) **(c) 仮説の影響**: stream_3=0 件問題は (a) LLM 集約バイアス / (b) 必然的帰結 だけでなく、**入力データセットの構造的問題** (海外メディア中心の RSS 41 媒体で日本国内メディアの論調が拾えない) の可能性が論点として残る。根本治療は系統 3 候補事象 (処理水放出 / 入管法改正 / 辺野古 / ジャニーズ問題) を意図的に追加した拡張ゴールデンセット。(2) **sontaku_signals type 分布バイアス**: 25 件中 type=diplomatic 20 件 (80%) は現サンプル範囲では整合だが、`domestic` (政治家・上級国民忖度) / `media_industry` (記者クラブ・芸能スポーツ業界忖度) はサンプル設計上ほぼ拾えない構造で、F-1 EditorialMissionFilter の優先度判定の歪みを生むリスクあり。(3) **finalize_annotations.py 修正粒度**: フィールド単位 partial merge は今回未実装 (Phase A.5-3b 実運用時にカズヤが手で全フィールド書く運用で支障なし)、null/object の単純ロジックで運用開始。
  - 残課題: ★ F-particular-angle-redesign Task E (4 分類版 + sontaku_signals 込みのカズヤレビュー) 待ち、本フォローアップで `scripts/finalize_annotations.py --schema-version 2.0` の sontaku_signals 対応が完了したためレビュー後即実行可能。Phase A.5-3b 第二作で系統 3 事象 (処理水放出 / 辺野古 等) のサンプル拡充検討、(c) 仮説検証も兼ねる。F-1 EditorialMissionFilter 着手時に sontaku_signals type 分布バイアスエントリを設計レビューで参照。
  - 関連ファイル: `docs/DISCUSSION_NOTES.md` (1 エントリ更新 [stream_3=0 件 + (c) 仮説] + 1 エントリ新規 [sontaku_signals type 分布バイアス] + ヘッダ最終更新日付)、`scripts/finalize_annotations.py` (4 関数 sontaku_signals 対応最小修正)、`docs/CURRENT_STATE.md` `docs/DECISION_LOG.md` `docs/FUTURE_WORK.md` (本バッチ反映)

- **系統名 1/1.5/2 → 1/2/3 リネーム + 忖度シグナル独立化 + クラウド誤り 9 記録 (F-particular-angle-redesign-extension)** (F-particular-angle-redesign-extension / 2026-05-08 完了、Task E カズヤレビュー待ち)
  - 発生バッチ: F-particular-angle-redesign 完了直後の Task E カズヤレビュー過程で、カズヤから本質的な指摘 3 件 (命名整理 / 忖度シグナル独立化 / 各論コントロール回避) が提示された。これらを反映するため F-particular-angle-redesign の **拡張作業** として実施。新規 commit + push で対応、コード変更なし (src/ tests/ configs/ への変更なし)。
  - 対応内容: (Task A) `docs/PARTICULAR_ANGLE_DEFINITION.md` 改訂 — 系統名 1/1.5/2 → 1/2/3 にリネーム + 新サブセクション 1.2 (命名整理経緯) + 1.3 (忖度シグナル独立化経緯) + セクション 3 大幅改訂 (Step 3-4 改良: Step 3 = 「日本メディアが特定角度を語っているか」、Step 4 = 「評価対立 + 忖度シグナル」) + 新サブセクション 3.5 (MECE 判別基準明示) + 3.6 (sontaku_signals 構造定義) + 既存 3.5 を 3.7 にリナンバー (メタデータ構造に sontaku_signals 追加 + クラウド誤り 9 への参照追加)。 (Task B) 3 scripts (`reclassify_annotations.py` / `generate_review_draft_v2.py` / `finalize_annotations.py`) の系統名リネーム + LLM プロンプト改良版 Step 0-4 反映 + ラベル更新。(Task C) `annotations.json` 系統名リネーム (25 件中 20 件) + schema_version 2.0 → 2.1 (`previous_schema_version=2.0` 記録)。`legacy_stream_classification_v1` フィールド内の値は 3 分類版の歴史的記録として変更せず保持。(Task D) `scripts/add_sontaku_signals.py` 新規 (per-call timeout 90s + incremental save + resume) で 25 件分の sontaku_signals を LLM 推定生成、各 event に `sontaku_signals` フィールド付与 + `kazuya_review.sontaku_signals_revised` スロット追加、`extension_log.json` に level / type / extraction_confidence 分布記録。(Task E) `CLAUDE.md` に「クラウド誤り」セクション新設 + 誤り 9 (各論コントロールへの誘惑) 本文記載 + DISCUSSION_NOTES に新エントリ追加 (Resolved、再発防止策確立) + 系統 3 (旧系統 2) の典型パターン (日本-海外の評価対立) 新エントリ (Active、Phase A.5-3b で参照)。(Task F) `REPORT.md` セクション 11 (拡張作業) 追加 + DECISION_LOG エントリ + FUTURE_WORK 本エントリ + DISCUSSION_NOTES 3 エントリ + CURRENT_STATE 全置換更新。
  - 重要な発見 / 観察: (1) **sontaku_signals LLM 推定分布 (25 件)**: level=high 7 件 / medium 14 件 / low 1 件 / none 3 件、type=diplomatic 20 件 / domestic 1 件 / media_industry 1 件 / null 3 件、extraction_confidence=high 23 件 / medium 2 件 / low 0 件。type=diplomatic が圧倒的多数 (20 件) なのは Hydrangea 入力 RSS 41 媒体 (MEE, Meduza, Al Jazeera 等) が外交・地政学事象中心という構造的整合。 (2) **クラウド誤り 9 の構造的解**: 系統判定にジレンマ解説 / 忖度明示の各論ルールを組み込まず、メタデータ構造 (`particular_angle_metadata + sontaku_signals`) を `script_writer.py` 新ルートに渡す設計を維持。LLM の自由度阻害を回避。 (3) **MECE 判別基準明示**: 系統 2 vs 系統 3 の境界条件を「日本メディアが特定角度について何かを語っているか」で MECE に整理、境界事例は sontaku_signals.level で間接区別。 (4) **Gemini API 安定動作**: 約 9 分で 25 件完走 (success=25 / error=0、timeout 警告 1 件 + 後続リトライで成功)、F-particular-angle-redesign の 1:36 hr (Tier 多発フォールバック) と比較して負荷が落ち着いている時間帯。
  - 残課題: ★ F-particular-angle-redesign Task E (4 分類版 + sontaku_signals 込みのカズヤレビュー) 待ち、レビュー完了後 `python scripts/finalize_annotations.py --input docs/runs/F-particular-angle-design/annotations.json --output-diff docs/runs/F-particular-angle-design/annotation_diff.json --output-classification docs/runs/F-particular-angle-design/stream_classification.json --update-golden-set docs/runs/F-verify-jp-coverage/golden_set.json --schema-version 2.0` を実行 → REPORT 補足更新 → 後続バッチ判断。
  - 関連ファイル: `scripts/add_sontaku_signals.py` (新規)、`docs/runs/F-particular-angle-redesign/extension_log.json` (新規)、`docs/PARTICULAR_ANGLE_DEFINITION.md` (命名 1/2/3 + 1.2 / 1.3 / 3.5 / 3.6 / 3.7 サブセクション + Step 3-4 改良)、`scripts/reclassify_annotations.py` `scripts/generate_review_draft_v2.py` `scripts/finalize_annotations.py` (命名リネーム)、`docs/runs/F-particular-angle-design/annotations.json` (schema 2.1 + sontaku_signals)、`CLAUDE.md` (クラウド誤りセクション新設)、`docs/runs/F-particular-angle-redesign/REPORT.md` (セクション 11 拡張作業追加)、`docs/CURRENT_STATE.md` `docs/DECISION_LOG.md` `docs/FUTURE_WORK.md` `docs/DISCUSSION_NOTES.md` (本バッチ反映)

- **3 分類 → 4 分類化 + 系統 1.5 perspective_gap 新設 + 台本表現ガイドライン正典化 (F-particular-angle-redesign)** (F-particular-angle-redesign / 2026-05-08 完了、Task E カズヤレビュー待ち、★ 拡張バッチ F-particular-angle-redesign-extension で命名 1/2/3 整理 + sontaku_signals 独立化を反映)
  - 発生バッチ: F-particular-angle-design (2026-05-07) の DISCUSSION_NOTES 4 エントリ追加 (2026-05-07 当日中) で、3 分類 (系統 1 / 系統 2 / 動画化対象外) の構造的不備が明らかになった。具体的には blind_002 / blind_004 / blind_009 のような事象群で「広範事件は日本主要メディアで報道済み + 特定角度のみ未報道」というパターンが多発しており、LLM 判定では「特定角度ベース」で stream_1_silence_gap に分類されるが台本表現として「日本では報じられていない」と書くと嘘になり視聴者からのツッコミを誘発するリスクが残った。カズヤから「一部報道だけど観点不足っていう 1.5 分類儲けてもいいのかもしれない」と提案され、議論の結果 4 分類化が必要との結論に到達。Phase A.5-3a-verify ゲート完了後の 2 つ目のバッチで、F-particular-angle-design の構造的不備の根本治療と F-stream-2-filter-design / F-jp-coverage-tune の責務分離を更に明確化する性格を持つ。
  - 対応内容: (Task A) `docs/PARTICULAR_ANGLE_DEFINITION.md` を 3 分類 → 4 分類版に改訂 (新サブセクション 1.1 「3 分類の構造的不備と 1.5 分類追加の経緯」+ セクション 3 大幅改訂で Step 1-4 論理フロー + 新サブセクション 3.5 「系統別の台本表現の方向性」で particular_angle_metadata 構造を正典化)。(Task B) `scripts/reclassify_annotations.py` 新規作成 (4 分類化用 LLM 再判定、per-call timeout 90s + resume + incremental save 付き、`_build_extract_client()` 流用で max_output_tokens=4096)。(Task C) 25 件再分類実行 (Gemini API 503 高負荷で Tier 1→2→3 フォールバック多発、第 1 試行 hung でタイムアウト追加して第 2 試行で完走、success=25 / error=0 / 約 1:36 hr)。(Task D) `review_draft_v2.md` 生成 (重点レビュー section: 3 分類 → 4 分類で変更があった 20 件を冒頭表示、各 event の「3 分類版 → 4 分類版判定」併記)。(Task E: ★ カズヤ手動レビュー、本バッチ内未実行)。(Task F) `scripts/finalize_annotations.py` を 4 分類対応に改修 (`--schema-version` 引数追加、デフォルト 2.0、3 分類対応関数 + 4 分類対応関数併存、golden_set v1.x → v1.3 更新パス、入力検証で schema 不整合を検知)。(Task G) `REPORT.md` + BATCH_PROTOCOL Task 1-5 ドッグフーディング (DECISION_LOG エントリ追加 + FUTURE_WORK 本エントリ追加 + F-stream-2-filter-design 責務スコープ要再評価更新 + F-jp-coverage-tune 優先度上昇 + DISCUSSION_NOTES 既存 4 エントリ更新 (Resolved 化等) + CURRENT_STATE 全置換更新)。
  - 重要な発見 / 想定外結果: (1) ★ **stream_2 = 0 件、stream_1_5 = 20 件 という想定外分布**: LLM が 4 分類定義を厳密適用した結果、3 分類版で stream_2 だった 13 件全てが stream_1_5 に移動 (covered 系列 9 件 + blind_005/008 + 試運転 cls-7bd1406438b6/cls-33b4f4960bf9_7K)。LLM の reasoning は技術的に整合 (例: covered_002「広範事件であるトランプ・プーチン接触は日本でも報道済みだが、外交的正当性と構造的影響の特定角度分析は深掘り未報道」)。これが LLM の集約バイアス (stream_2 を選ぶ基準が厳しすぎる) なのか、4 分類定義の必然的帰結 (海外メディアの特定角度が日本で同フレームで報道されることが稀) なのかは、カズヤレビューで判別する必要あり。(2) **3 分類版で stream_1 だった 7 件が stream_1_5 に移動**: blind_002/004/009/010 + 試運転 3 件 (cls-204a683f73ee_7K / cls-6be4fc09d9ed / cls-a4132ec7d949)。F-particular-angle-design DISCUSSION_NOTES 観察 1 (golden_set v1.1 stream_2_candidate メタとの差分) で予測された変化と整合、4 分類化の妥当性を支持する事例。(3) **不変 5 件**: 系統 1 のまま 4 件 (blind_001 / blind_003 / blind_007 / cls-0c7fa7c667d6 ロシア焼身) + 動画化対象外のまま 1 件 (covered_006 NVIDIA 株)。(4) **F-stream-2-filter-design の責務範囲縮小可能性**: 本想定外結果次第で F-stream-2-filter-design は小規模実装で済む可能性、F-jp-coverage-tune が相対的に最優先化。(5) **二段階クエリ生成の真値整備**: 各 event に `broad_event_jp_coverage` と `particular_angle_jp_coverage` の独立フィールドが追加され、F-jp-coverage-tune の二段階クエリ精度評価に使える 25 件の真値データが整備された。(6) **Gemini API 503 高負荷耐性**: per-call timeout 90s + incremental save + resume を組み合わせることで API ハング (50 分応答なし事例観測) からの復旧と部分結果保存が可能になった、reclassify_annotations.py は今後の同種スクリプトの参考実装として転用可。
  - 残課題: ★ Task E (カズヤレビュー) 待ち、レビュー完了後 `python scripts/finalize_annotations.py --input docs/runs/F-particular-angle-design/annotations.json --output-diff docs/runs/F-particular-angle-design/annotation_diff.json --output-classification docs/runs/F-particular-angle-design/stream_classification.json --update-golden-set docs/runs/F-verify-jp-coverage/golden_set.json --schema-version 2.0` を実行 → REPORT 補足更新 → 後続バッチ (F-stream-2-filter-design スコープ判断 / F-jp-coverage-tune 着手) を判断。
  - 関連ファイル: `scripts/reclassify_annotations.py` (新規)、`scripts/generate_review_draft_v2.py` (新規)、`scripts/finalize_annotations.py` (改修、`--schema-version 2.0` 追加)、`docs/PARTICULAR_ANGLE_DEFINITION.md` (3 分類 → 4 分類への改訂)、`docs/runs/F-particular-angle-redesign/` 配下 (REPORT.md / reclassification_log.json / reclassification_diff.json / reclassify_log.txt / review_draft_v2.md)、`docs/runs/F-particular-angle-design/annotations.json` (4 分類版に上書き、`legacy_stream_classification_v1` + `broad_event_jp_coverage` + `particular_angle_jp_coverage` 新フィールド付与)、`docs/runs/F-particular-angle-design/annotations_v1_3class.json` (3 分類版バックアップ)、`docs/CURRENT_STATE.md` (全置換更新)、`docs/DECISION_LOG.md` (本バッチエントリ追加)、`docs/FUTURE_WORK.md` (本エントリ + F-stream-2-filter-design 責務スコープ更新 + F-jp-coverage-tune 優先度上昇)、`docs/DISCUSSION_NOTES.md` (既存 4 エントリ更新)

- **「特定角度」概念の docs 化 + LLM ベースアノテーション 25 件 (F-particular-angle-design)** (F-particular-angle-design / 2026-05-07 完了)
  - 発生バッチ: F-trial-run-post-fix (2026-05-07) で「広範事件は日本主要メディアで報道済みだが、MEE/海外メディアの特定角度は未報道」という stream_2_candidate パターンが 6 件 (golden set 4 + 試運転 7-K 2) 確認された。系統 1 / 系統 2 の判定対象を「広範事件」レベルで取ると両系統で重複ケースが発生する問題が顕在化、カズヤとの議論 (2026-05-07) で「重複しないように定義すればよくね?」 = 判定対象を『特定角度』に限定すれば重複は構造的に消えるという結論に到達。Phase A.5-3a-verify ゲート完了後の最初のバッチで、F-stream-2-filter-design + F-jp-coverage-tune の共通基盤を確立する性格を持つ。
  - 対応内容: (Task A) `docs/PARTICULAR_ANGLE_DEFINITION.md` 新規作成 (5 セクション散文展開: 背景 / 概念定義 / 系統判定基準 / LLM 抽出方針 / 関連ファイル)。(Task B) `scripts/extract_particular_angle.py` 新規作成 (LLM ベース特定角度抽出、max_output_tokens=4096 専用クライアント、JSON パーサ最小修復、リトライ最大 3 回)。(Task C) `docs/runs/F-particular-angle-design/input_events.json` 25 件統合 (golden_set v1.1: 19 件 + 試運転 7-K 2026-05-01: 3 件 + 試運転 2026-05-07: 3 件)。(Task D) Gemini analysis Tier で 25 件抽出実行、`annotations.json` 出力 (extraction_confidence: high=22 / medium=3 / low=0、stream 推定: 系統 1=11 / 系統 2=13 / 対象外=1、errors=0)。試行 1-2 で max_output_tokens=2000 による JSON 途中切断を覚知 (6-7 件失敗) → 4096 への拡張で 0 errors 達成。(Task E) `review_draft.md` 生成 (655 行、25 events フォーマット統一、各 event に LLM 抽出 + LLM 判定 + 判定根拠 + カズヤレビュー欄)。(Task F: ★ カズヤ手動レビュー、本バッチ内未実行)。(Task G) `scripts/finalize_annotations.py` 新規作成 (annotation_diff + stream_classification + golden_set v1.2 を生成、試運転 6 件は golden_set 統合せず stream_classification.json で 25 件まとめて管理する責務分離)。(Task H) 統合レポート `REPORT.md` + BATCH_PROTOCOL Task 1-5 ドッグフーディング (DECISION_LOG エントリ + FUTURE_WORK 完了済み移動 + DISCUSSION_NOTES 「系統 1 判定基準明確化」「F-13.B 動作仕様」エントリ更新 + 新規エントリ「特定角度抽出の LLM 限界観察」+ CURRENT_STATE 全置換更新)。
  - 重要な発見: (1) **「特定角度」概念の有効性**: 試運転 2026-05-07 Slot-1 (Insider trading) は WebSearch で広範事件は Tier 1-2 報道済みと判明していたが、LLM は「特定角度 (国家規模インサイダー取引疑惑) は日本主要メディアで深掘り未報道」と判定し stream_1 に分類 = 「特定角度」概念を判定単位にすると blind_spot ルートに進んだ動画化が正当化される事例。(2) **golden_set v1.1 stream_2_candidate メタとの差分**: blind_002/004/009 は v1.1 で stream_2_candidate メタ付与だが LLM は stream_1 に分類。判定対象を『広範事件』vs『特定角度』で取ると同じ事象でも結論が変わる可能性、カズヤレビューで再評価対象。(3) **covered 系列 9/10 件が stream_2 に分類**: 「日本主要メディアで報道済みでも海外メディアの掘り下げ角度には解釈差があり stream_2 候補となる」という LLM 判断傾向、F-stream-2-filter-design が処理する候補数の見積もり材料。(4) **max_output_tokens=2000 では分析タスクで途中切断**: analysis_llm_client 既定の 2000 tokens は本タスクで JSON 途中切断を起こした、F-stream-2-filter-design 着手時の判断材料に。
  - 残課題: ★ Task F (3 分類版でのカズヤレビュー) は **スキップ済み** (F-particular-angle-redesign / 2026-05-08 で 4 分類化が必要なことが判明したため、3 分類版での確定作業は無駄になる判断)。3 分類版の LLM 判定結果は `annotations_v1_3class.json` としてバックアップ済み。カズヤレビューは F-particular-angle-redesign の Task E で 4 分類版に対して実施する。
  - 関連ファイル: `docs/PARTICULAR_ANGLE_DEFINITION.md` (新規、F-particular-angle-redesign で 4 分類化に改訂)、`scripts/extract_particular_angle.py` (新規)、`scripts/finalize_annotations.py` (新規、F-particular-angle-redesign で `--schema-version 2.0` 追加に改修)、`docs/runs/F-particular-angle-design/` 配下 (input_events.json / annotations.json / annotations_v1_3class.json / review_draft.md / extraction_log.txt / REPORT.md)、`docs/CURRENT_STATE.md` (全置換更新)、`docs/DECISION_LOG.md` (本バッチエントリ追加)、`docs/FUTURE_WORK.md` (本エントリ + F-stream-2-filter-design / F-jp-coverage-tune の前提に F-particular-angle-design 完了を追記)、`docs/DISCUSSION_NOTES.md` (既存 2 エントリ更新 + 新規 1 エントリ)

- **修正後 F-13.B の本番試運転 + 過去判定後追い + Phase A.5-3a-verify ゲート完了 (F-trial-run-post-fix)** (F-trial-run-post-fix / 2026-05-07 完了)
  - 発生バッチ: F-jp-coverage-improve (2026-05-07) で F-13.B 構造的不具合を修正したが、「動くものを壊さない」哲学に従い、本番運用 (RSS 収集 → triage → Slot 選定) で修正後 F-13.B が期待通り動くか試運転で確認 + 過去試運転 7-K 動画化 3 件 (FIFA + Gaza×2) の WebSearch 後追い + 修正後 F-13.B での過去試運転再判定が必要だった。Phase A.5-3a-verify ゲート完了の最終段階 (1-D''')。
  - 対応内容: (Task A) ブランチ作成 + 環境スナップショット (main HEAD `fd76660`、baseline 1345 passed、jp_coverage_cache 6 records、AUDIO/VIDEO_RENDER_ENABLED デフォルト false 確認)。(Task B) `python -m src.ingestion.run_ingestion` で RSS 取得 (41 ソース中 40 成功、1454 raw → 584 重複除去後)、`python -m src.main --mode normalized` で試運転 (約 26 分、batch_id=20260506_190600、job_id=033ed4bc...、status=completed、3 Slot 選定 = Slot-1 cls-6be4fc09d9ed Insider trading + Slot-2 cls-0c7fa7c667d6 Russian self-immolation + Slot-3 cls-a4132ec7d949 Met Police synagogue、F-13.B 3 invocations 全 has_jp_coverage=False、excluded_count=1/10/3)。(Task C) `f13b_output_analysis.json` に試運転 + replay 6 invocations 集計 (True 0 / False 6 / Error 0、excluded URLs 全 youtube.com 計 23 件、structural_fix_validated=true) と解釈 (Tier 1-2 ヒット 0、Grounding API が youtube.com 偏重 = F-jp-coverage-tune 既知課題と整合) を保存。(Task D) `defense_layers_audit.json` に防衛機構 5 層発火状況保存 (F-1 18/364 通過、F-2 全通過、F-13.B 3 invocations 構造機能 OK、F-5 救済 0、F-13 隠れ層 0)、all_5_layers_functional=true。(Task E) WebSearch (Anthropic web search) で試運転 7-K 過去動画化 3 件後追い、Slot-1 (FIFA) は jiji.com (Tier 2) で関連報道、Slot-2 (Mandelson) は nikkei.com (Tier 1) + jiji + bloomberg (Tier 2) で広範報道済み (Epstein 角度、MEE オリジナル Gaza 角度は未報道)、Slot-3 (Gaza 電力) は MEE 2026-04 時点の特定角度は未報道で真の blind_spot に近い、を `past_videos_audit.json` に保存。3 件中 2 件が典型的 stream_2_candidate パターン。(Task F) `scripts/replay_jp_coverage.py` 新規作成 (一時 DB `/tmp/jp_coverage_replay.db`、verify_jp_coverage_measure.py 構造踏襲)、入力 `trial_7k_events.json` で 3 件再判定、結果 `past_runs_replay.json` に 3 件全て False→False (判定不変、excluded 0/5/4 で構造機能は OK)。(Task G) 統合レポート `REPORT.md` 作成 + Phase A.5-3a-verify ゲート完了正式宣言 + BATCH_PROTOCOL Task 1-5 ドッグフーディング (DECISION_LOG エントリ + FUTURE_WORK 完了済み移動 + F-stream-2-filter-design 着手 OK 状態に更新 + F-jp-coverage-tune 優先度確認 + DISCUSSION_NOTES F-13.B エントリのステータス更新 + 新規エントリ「Grounding 検索クエリ品質問題」追加 + CURRENT_STATE 全置換更新)。リグレッション影響なし (`scripts/replay_jp_coverage.py` 新規 + `docs/runs/F-trial-run-post-fix/` + `docs/` のみ変更、`src/` `tests/` `configs/` `CLAUDE.md` 0 行変更、baseline 1345 passed 維持)。
  - 重要な発見: (1) 構造的不具合解消の **本番動作確認**: 試運転 6 invocations のうち 5/6 で excluded_urls_count > 0 (1/10/3/0/5/4)。修正前は redirect URL のみで構造的に excluded=0 だった、ドメイン抽出層 (`_extract_domain_from_chunk` / `_looks_like_domain` / `_normalize_domain`) の本番動作証明。(2) **Recall miss の本番再現**: 試運転 Slot-1 (Insider trading) は WebSearch で nikkei + jiji + bloomberg で広範報道済みだが F-13.B は Recall miss、Grounding API が英語タイトル + 「日本 報道」クエリで youtube.com 偏重の結果を返す問題が本番でも確認 (excluded URLs 全 23 件が youtube.com)。これは F-jp-coverage-tune の主要課題と完全整合。(3) **試運転 7-K 過去動画 3 件のうち 2 件が typical stream_2_candidate**: Slot-1 (FIFA) と Slot-2 (Mandelson) は『広範事件は Tier 1-2 報道済み + MEE オリジナル角度は未報道』パターン、F-stream-2-filter-design 完成後の 2 段階フィルタで救出される設計と整合 = 系統 2 設計の妥当性根拠拡張 (golden set 4 件 + 試運転 7-K 2 件 = 6 件)。(4) **WebSearch クローラ制約**: Anthropic WebSearch クローラは asahi.com / yomiuri.co.jp / nhk.or.jp / mainichi.jp / sankei.com / 47news.jp / kyodonews.jp / kyodonews.net への直接クロールがブロックされる仕様、Tier 1 主要紙の報道有無は jiji / nikkei / bloomberg 等の他 Tier ヒットから推定する制約あり。(5) **Phase A.5-3a-verify ゲート完了**: 1-A〜1-D''' 全完了、F-stream-2-filter-design 着手 OK 状態に。
  - 残課題: F-stream-2-filter-design 着手 (★最優先、Phase A.5-3a-verify ゲート完了で着手再開条件達成)、F-jp-coverage-tune (Recall miss の本番再現で優先度確認、F-stream-2-filter-design と並行可)、Project Knowledge の手動最新化 (★ Phase A.5-3a-verify ゲート完了の節目で必須最新化推奨)
  - 関連ファイル: `scripts/replay_jp_coverage.py` (新規)、`docs/runs/F-trial-run-post-fix/` 配下 9 ファイル (REPORT.md / trial_run_log.json / f13b_output_analysis.json / defense_layers_audit.json / past_videos_audit.json / past_runs_replay.json / trial_7k_events.json / trial_run_log.txt / ingestion_log.txt / replay_log.txt)、`docs/CURRENT_STATE.md` (全置換更新), `docs/DECISION_LOG.md` (本バッチエントリ追加), `docs/FUTURE_WORK.md` (本エントリ + F-stream-2-filter-design 着手 OK 状態 + F-jp-coverage-tune 優先度更新), `docs/DISCUSSION_NOTES.md` (F-13.B 動作仕様検討課題ステータス更新 + 新規エントリ「Grounding 検索クエリ品質問題」追加)

- **F-13.B 構造的不具合の根本治療 + 不変原則例外条件構造化 + Project Knowledge 運用ルール化 + Phase A.5-3a-verify ゲート完了条件再定義 (F-jp-coverage-improve)** (F-jp-coverage-improve / 2026-05-07 完了)
  - 発生バッチ: F-verify-jp-coverage-measure (2026-05-05、verdict=fail) で F-13.B JpCoverageVerifier の構造的不具合を特定したため、根本治療志向で 5 つの目的を同時達成する複合バッチを起動。(1) F-13.B 構造的不具合の根本治療、(2) 不変原則例外条件の構造化、(3) Project Knowledge 最新化運用のルール化、(4) Phase A.5-3a-verify ゲート完了条件の再定義、(5) 計測再実行で合格判定取得。
  - 対応内容: (Task A) `src/triage/jp_coverage_verifier.py` にドメイン抽出レイヤー (`_extract_domain_from_chunk` / `_looks_like_domain` / `_normalize_domain`) を追加。`_search_with_grounding()` を修正し、`chunk.web.title` を実ドメインとして読み取り `https://{domain}` 形式で WL マッチングに供給。`chunk.web.uri` (Vertex AI redirect URL) は `redirect_urls` に分離記録 (debug 用)。SDK 将来バージョンで `chunk.web.domain` が実値を返した時に透過対応する **防御層** として機能するフォールバック戦略 (戦略 1: domain → 戦略 2: title) を持つ。(Task B) `tests/test_jp_coverage_verifier_domain_extract.py` を新規作成 (28 テスト追加: `_looks_like_domain` / `_normalize_domain` / `_extract_domain_from_chunk` の各戦略 + 実 API 観測値での検証 + フォールバック確認)。`tests/test_f13b_rescue_abolition.py` の `_make_grounding_response` フィクスチャを実 API contract に合わせて更新 (uri に Vertex redirect URL、title に実ドメイン、domain=None)、除外 URL アサーション 1 つを host ベースに調整。テスト総数 1315 → 1345 (+30) 全 passed 維持。(Task C) `scripts/verify_jp_coverage_measure.py --cache-mode=fresh` 実行で 5 件 503 UNAVAILABLE エラー (Gemini API 一時的高負荷)、`--cache-mode=reuse` で残存 5 件のみ retry し全件完走。再測定結果: TP=10/14 (vs 修正前 0/14), FN=4/14 (vs 修正前 14/14), FP=2/5, TN=3/5, Recall covered 71.43% / Precision blind 42.86% / F1 0.769 / Tier 一致率 30% / Error 0%。**構造的不具合は解消されたが 4 指標とも閾値未達のため verdict=fail のまま**。残課題 (FN クエリ最適化 / FP diamond.jp 真値再評価 / Tier 一致率) は本バッチ責務範囲外として F-trial-run-post-fix + F-jp-coverage-tune に分離。`docs/runs/F-verify-jp-coverage/measurement_result.json` を v2 として上書き (root_cause_finding に resolved_in を追加)、`REPORT.md` を v2 として上書き (★1.5 セクションを「根本原因の特定と修正済み報告」に更新、修正前後の比較表を追加)。(Task D) `docs/BATCH_PROTOCOL.md` に「不変原則の例外条件」セクション (4 条件 + 例外不可ケース + 過去事例) と「Project Knowledge 最新化運用ルール」セクション (必須/推奨タイミング + 最新化対象 + 注意事項) を追加。(Task E) `docs/CURRENT_STATE.md` の Phase A.5-3a-verify ロードマップを 1-A〜1-D''' 構成に再定義 (1-D'' を 1-D' 内統合、1-D''' を F-trial-run-post-fix として分離)。(Task F) BATCH_PROTOCOL Task 1-5 ドッグフーディング (DECISION_LOG エントリ + FUTURE_WORK 完了済み移動 + F-trial-run-post-fix / F-jp-coverage-tune 緊急度 高新規追加 + F-stream-2-filter-design 着手再開条件更新 + DISCUSSION_NOTES 既存エントリ更新 + CURRENT_STATE 全置換更新)。
  - 不変原則例外: 不変原則 3 (`src/triage/` 既存ファイル変更不可) に例外適用。4 条件全て満たすことを確認 (1) 実装バグの修正 (Grounding redirect URL を WL マッチング使用) (2) 設計変更ではない (`verify()`/`verify_async()` シグネチャ・戻り値構造不変、ドメイン抽出ロジックの正しい実装への置換のみ) (3) DECISION_LOG エントリで明記 (4) Hydrangea コンセプト防衛機構 5 層中核なのでカズヤ承認必須 → バッチプロンプトの背景セクションに記録済み。
  - 重要な発見: 構造的不具合は解消されたものの精度指標は閾値未達。「ロジックが構造的に常に False を返す」状態 (v1) → 「正しく動くが精度が閾値未達」状態 (v2) は質的に異なる進捗。残 FN 4 件 (blind_005 / covered_006 / covered_007 / covered_009) は Grounding API がタイトル・ベース検索クエリで Tier 1-2 ソースを直接引き当てられないクエリ最適化問題、FP 2 件は両方 diamond.jp で WL に正規収録されたドメインが該当 → 真値再評価 or Tier 4 weighting 議論が必要、Tier 一致率低下は Grounding が Tier 4 ソースを Tier 1 より先に返す傾向 (構造的、別問題)。stream_2_candidate 4 件は 3/4 が True 判定でき、F-stream-2-filter-design の前提は確保されている。
  - 残課題: F-trial-run-post-fix (修正後 F-13.B の本番試運転 + 過去判定後追い、即着手可能)、F-jp-coverage-tune (Recall/Precision/Tier 一致率の閾値達成、F-trial-run-post-fix 完了後)、Project Knowledge の手動最新化 (カズヤ手作業、本バッチ完了後 = Phase A.5-3a-verify ゲート完了の節目で必須最新化推奨)
  - 関連ファイル: `src/triage/jp_coverage_verifier.py` (改修対象、★不変原則 3 例外条項適用、ドメイン抽出レイヤー追加 + `_search_with_grounding()` 修正), `tests/test_jp_coverage_verifier_domain_extract.py` (新規 28 テスト), `tests/test_f13b_rescue_abolition.py` (フィクスチャ実 API contract 整合化 + 除外 URL アサーション host ベース化), `docs/runs/F-verify-jp-coverage/measurement_result.json` v2 + `REPORT.md` v2 (再測定結果上書き), `docs/BATCH_PROTOCOL.md` (不変原則例外条件 + Project Knowledge 運用ルールセクション新設), `docs/CURRENT_STATE.md` (全置換更新), `docs/DECISION_LOG.md` (本バッチエントリ追加), `docs/FUTURE_WORK.md` (本エントリ + F-trial-run-post-fix / F-jp-coverage-tune 新規 + F-stream-2-filter-design 着手再開条件更新), `docs/DISCUSSION_NOTES.md` (F-13.B 動作仕様検討課題エントリ更新)

- **F-13.B 精度実測 + 構造的不具合 (Grounding redirect URL) の特定 (F-verify-jp-coverage-measure)** (F-verify-jp-coverage-measure / 2026-05-05 完了、verdict=fail)
  - 発生バッチ: ゴールデンセット v1.1 (19 件) + F-13.B 既存実装で精度実測したところ、19/19 件で `matched=0`, `has_jp_coverage=False` という異常パターンを観測。Recall covered 0%、Precision blind 26.32%、F1 covered 0.000、Tier 一致率 0%、エラー 0/19 で全 4 指標未達。
  - 対応内容: (Task A) `scripts/verify_jp_coverage_measure.py` 新規作成 (約 600 行、CLI 引数 `--cache-mode` で fresh/reuse/warm-then-reuse 切替、一時 DB `/tmp/jp_coverage_measure.db` を使い本番 DB を汚染しない設計、TP/FP/TN/FN/Error + Precision/Recall/F1/Tier 一致率/stream_2 集計 + verdict 判定 (pass/conditional_pass/fail) を一通り実装、結果 JSON + 人間読み Markdown を生成)。(Task B) `--cache-mode=fresh` で実行、19 件全件完走 (エラー 0、所要 177s ≈ 3 分)。(Task C) 全件 matched=0 という異常を受け、Gemini Grounding API のレスポンス構造を直接デバッグ → `chunk.web.uri` は redirect URL (`vertexaisearch.cloud.google.com/grounding-api-redirect/...`)、実ドメインは `chunk.web.title` (例: `jiji.com`, `jetro.go.jp`, `recordchina.co.jp`) に格納されている事実を特定。`chunk.web.domain` は SDK 現行版で常に None。(Task D) verdict=fail として REPORT.md と measurement_result.json を確定、★1.5 根本原因の特定セクションを REPORT.md に挿入、root_cause_finding フィールドを measurement_result.json に追加、F-jp-coverage-improve バッチ起動 + F-stream-2-filter-design 着手保留を明記。(Task E) BATCH_PROTOCOL Task 1-5 ドッグフーディング実施 (DECISION_LOG エントリ追加 / FUTURE_WORK で本エントリ完了済み移動 + F-jp-coverage-improve 緊急度 高新規追加 + F-stream-2-filter-design 着手保留化 / DISCUSSION_NOTES「F-13.B 動作仕様の検討課題」に 2026-05-05 実測結果と根本原因特定を追記 / CURRENT_STATE 全置換更新 = main HEAD/直近 5 件/次バッチ候補刷新/Phase A.5-3a-verify ロードマップ 1-D 完了表示/F-13.B 行に精度実測値追記)。リグレッション影響なし (`scripts/` + `docs/runs/` + `docs/` 配下のみ変更、`src/` `tests/` `configs/` `CLAUDE.md` 0 行変更、baseline 1315 passed 維持)。
  - 重要な発見: F-13.B が本番でも常に `has_jp_coverage=False` を返している懸念。試運転 7-K の「100% (3/3) 動画化」は F-13.B の判定精度ではなく、F-13.B が常に False を返した結果として全 Slot が blind_spot 動画化ルートに進んだだけと再解釈される。Hydrangea コンセプト防衛機構 (5 層) の中核 (F-13.B 層) が機能していなかった可能性、即修正が必要。
  - 残課題: F-jp-coverage-improve 着手 (緊急度 高セクションに新規エントリ追加済み、即着手推奨)、改修後 `verify_jp_coverage_measure.py` 再実行で合格判定取得、試運転 7-K の 3 件が実は日本主要メディアで報道済みだったかの後追い確認
  - 関連ファイル: `scripts/verify_jp_coverage_measure.py` (新規), `docs/runs/F-verify-jp-coverage/measurement_result.json` (新規 + root_cause_finding), `docs/runs/F-verify-jp-coverage/REPORT.md` (新規 + ★1.5 根本原因特定), `docs/DECISION_LOG.md` (本バッチエントリ追加), `docs/FUTURE_WORK.md` (本エントリ + F-jp-coverage-improve 新規 + F-stream-2-filter-design 着手保留化 + Phase 順序更新), `docs/DISCUSSION_NOTES.md` (F-13.B 動作仕様検討課題に 2026-05-05 追記), `docs/CURRENT_STATE.md` (全置換更新)

- **ゴールデンセット真値修正 + 系統 1 判定基準 4 軸明文化 + Hydrangea メディア宣言反映 + F-stream-2-filter-design 計画 (F-verify-jp-coverage-golden-fix)** (F-verify-jp-coverage-golden-fix / 2026-05-04 完了、中間成果物)
  - 発生バッチ: F-verify-jp-coverage-golden 完了後のカズヤレビューで 5 件の真値修正必要 + 系統 1 判定基準が「日本未報道」だけでは不十分 + 「個人・権力者への忖度」軸が新規追加 + Hydrangea のメディアとしての存在意義 (「忖度、報道規制、報道の自由度の低さをぶち壊そう」というカズヤ宣言) が明示化される必要がある重要な発見が確定。また機械の根本的役割について「2 段階フィルタ + 解説価値判定」設計が確立し、F-stream-2-filter-design として Phase A.5-3b 前に独立実装する Phase 配置が確定した。
  - 対応内容: (Task A) golden_set.json 修正 = 4 件 (blind_002/004/005/009) の expected_has_jp_coverage を False → True 修正 (広範な事件は日本でも報道済み、特定角度は系統 2 候補)、blind_006 削除 (Palestine FIFA、Hydrangea 系統 1 ミッションに整合せず、heuristic 未採用 12 件から差し替え候補探索したが該当なし → 9 件構成に変更)、stream_2_candidate メタフィールド追加 (4 件に系統 2 候補メタ付与)、集計フィールド更新 (kazuya_review_required_ids 空配列、True/False 分布を expected_distribution として新設、last_updated_at + last_update_batch + v1_1_changelog 追加)。(Task B) DISCUSSION_NOTES 新規エントリ「系統 1 (silence_gap) の判定基準明確化」追加 (制度・システム面 / 外交・経済・利害関係面 / 個人・権力者面 / 関心領域・地政学的死角 の 4 軸構造で記録、Hydrangea メディア宣言を明記)、既存エントリ「F-13.B 動作仕様の検討課題」に 2026-05-04 議論結果追記 (カズヤの整理 + 2 段階フィルタ採用 + Phase A.5-3b 前独立実装方針、ステータス: 要確認 → 確定)。(Task C) FUTURE_WORK 緊急度 高に F-stream-2-filter-design 新規追加、F-verify-jp-coverage-measure の前提更新 (即着手可能)、Phase 順序を「measure → stream_2_filter → 3b」に更新、完了済みに本エントリ追加。(Task D) DECISION_LOG エントリ追加 (本バッチの設計判断 4 つを記録)。(Task E) CURRENT_STATE 更新 (最終更新日、次バッチ候補刷新、Phase A.5-3a-verify ロードマップ 1-C/1-D/1-E 段階追加、セクション 0 のコアミッション系統 1 説明を強化 = 4 軸構造 + Hydrangea メディア宣言を明示、末尾注記更新)。リグレッション影響なし (docs/ + docs/runs/ のみ追加、src/ tests/ configs/ CLAUDE.md は 0 行変更、baseline 1315 passed 維持)。
  - 残課題: F-verify-jp-coverage-measure 着手 (前提条件確定済み、即着手可能)
  - 関連ファイル: docs/runs/F-verify-jp-coverage/golden_set.json (v1.0 → v1.1 修正), docs/DISCUSSION_NOTES.md (1 新規 + 1 追記), docs/FUTURE_WORK.md (本エントリ + F-stream-2-filter-design 新規 + F-verify-jp-coverage-measure 前提更新 + Phase 順序新設), docs/DECISION_LOG.md (本バッチエントリ), docs/CURRENT_STATE.md (全置換更新 + セクション 0 系統 1 説明強化)

- **F-13.B 精度測定用ゴールデンセット作成 (F-verify-jp-coverage-golden / 第 1 段階)** (F-verify-jp-coverage-golden / 2026-05-03 完了、中間成果物)
  - 発生バッチ: F-verify-jp-coverage を 2 段階分割した第 1 段階。F-13.B JpCoverageVerifier (Hydrangea コンセプト防衛機構の中核) の精度測定 (TP/FP/TN/FN) を行うための真値となるゴールデンセット 20 件 (blind 10 + covered 10) を独立に作成し、カズヤレビューを経てから第 2 段階 (F-verify-jp-coverage-measure) で実際の精度測定を行う 2 段階構成。ゴールデンセットの品質が F-verify-jp-coverage 全体の信頼性を決めるため、判断密度の高い真値判定を独立バッチに切り分けた。
  - 対応内容: (1) `docs/runs/F-verify-jp-coverage/golden_set.json` を新規作成 (20 entries valid JSON、blind 10 + covered 10)。(2) blind 候補は F-13.B 過去キャッシュ (jp_coverage_cache に has_jp_coverage=False が残る 6 件) + 過去試運転 evidence.json から has_jp_view=0.0 + coverage_gap_score>=6.0 + sources.jp=[] を満たすヒューリスティック抽出候補 (18 件) から region/topic 多様性を考慮して 10 件選定。(3) covered 候補は WebSearch で 2026 年 4-5 月の主要国際ニュース (Trump-Hormuz / Russia-Ukraine 停戦 / 米中関税 / 教皇レオ 14 世警告 / Lula-Amazon / NVIDIA / Boko Haram / Mali 国防相殺害 / India-Pakistan Kashmir / フーシ-イラン支援表明) の JP_MEDIA_WHITELIST Tier 1-4 直接報道 URL を確認。(4) 真値判定は F-13.B 自体を呼ばず WebSearch ツールで Claude Code が独立に日本語検索 (例: タイトル + 'NHK 朝日 日経' 等) を実行 (自己参照回避)。F-13.B 過去判定は f13b_prior_verdict フィールドに参考情報として併記のみ。(5) 各 entry に title / summary / expected_has_jp_coverage / expected_tier / source_run / topic_category / region / volume_in_jp / manual_verification_note / manual_verification_urls 完備。(6) diversity_check (region/topic/tier/volume) + bias_note (中東バイアスは試運転データの構造的反映) + tier_2_4_only_deviation_note (仕様要求 ≥2 に対して 1 件達成、構造的困難の理由明記)。(7) kazuya_review_required_ids 5 件 (blind_002 / 004 / 005 / 006 / 009) を明示、共通パターン (広範な事件は Tier 1 報道あり、MEE 記事の核心 = 特定の構造分析角度は未報道) を kazuya_review_summary に記述。(8) next_batch_handoff に F-verify-jp-coverage-measure の期待 input/output とカズヤレビューゲートを定義。(9) BATCH_PROTOCOL Task 1-5 軽量版ドッグフーディング実施 (DECISION_LOG / FUTURE_WORK / DISCUSSION_NOTES / CURRENT_STATE 更新)。リグレッション影響なし (docs/ + docs/runs/ のみ追加、src/ tests/ configs/ CLAUDE.md は 0 行変更、baseline 1315 passed 維持)。
  - 残課題: F-verify-jp-coverage-measure 着手 (緊急度 高セクションに新規エントリ追加済み、カズヤレビュー後に着手)
  - 関連ファイル: `docs/runs/F-verify-jp-coverage/golden_set.json` (新規), `docs/DECISION_LOG.md` (本バッチエントリ追加), `docs/FUTURE_WORK.md` (F-verify-jp-coverage 改訂 + F-verify-jp-coverage-measure 新規追加 + 本エントリ追加), `docs/DISCUSSION_NOTES.md` (F-13.B 動作仕様の検討課題 1 エントリ追加), `docs/CURRENT_STATE.md` (main HEAD / 直近 5 件 / 次バッチ候補刷新)

- **議論結果反映 + コアミッション 2 系統並立の docs 化 (F-doc-cleanup-followup)** (F-doc-cleanup-followup / 2026-05-03 完了)
  - 発生バッチ: F-doc-cleanup (2026-05-03 / e34f36e、main マージ 3e817d8) 完了直後、カズヤとの議論で 3 つの追加判断が確定 (大規模調査機能登録 / ★最重要 コアミッション 2 系統並立訂正 / クラウド誤り 7 過小評価)。これらは F-doc-cleanup のスコープ外で、別バッチで反映する必要があった。特にコアミッション 2 系統並立は、F-doc-cleanup で CLAUDE.md の「プロジェクト概要」セクションを削除して CURRENT_STATE 参照に統合した結果、現状 docs のどこにもコアミッションが明文化されていない状態となっており、別チャット移行時のクラウド誤り 7 (系統 1 中心理解で系統 2 を過小評価) の再発リスクが極めて高い構造だった。
  - 対応内容: (Task A) DISCUSSION_NOTES.md に 3 エントリ追加 = (1) 大規模調査機能 (オンデマンド深掘りパイプライン): Phase B 以降の新選択肢として、井上 vs 中谷の例を含む実装上の主要論点 6 点と Phase 配置を記録、(2) ★最重要 — Hydrangea コアミッション 2 系統並立: 系統 1 (silence_gap) と系統 2 (framing_inversion + 構造分析) の並立、既存構造との関係 (framing_inversion 軸 / multi_angle 5 観点 / media_divergence) を明文化、(3) クラウド誤り 7 — 系統 1 中心理解で系統 2 を過小評価: 訂正前のクラウド理解と教訓・類似リスク・防止策を記録。Active 件数 18 → 21。(Task B) CURRENT_STATE.md 冒頭に新セクション「0. Hydrangea コアミッション (2 系統並立)」を追加: 系統 1 / 系統 2 の説明、ブランドポジション、3 チャンネル構想と現フォーカス、Phase B 以降の新選択肢 (大規模調査機能) を集約。既存セクション 1-8 はそのまま維持 (リナンバーしない)。末尾注記に本バッチ概要追記。(Task C) BATCH_PROTOCOL Task 1-5 を本バッチ自身に適用 (ドッグフーディング)。リグレッション影響なし (docs/ のみ変更、src/ tests/ configs/ CLAUDE.md は 0 行変更、baseline 1315 passed 維持)。
  - 関連ファイル: `docs/DISCUSSION_NOTES.md` (3 エントリ追加 + 最終更新日更新), `docs/CURRENT_STATE.md` (新セクション「0. Hydrangea コアミッション (2 系統並立)」冒頭追加 + 最終更新日更新 + 末尾注記更新), `docs/DECISION_LOG.md` (本バッチエントリ追加), `docs/FUTURE_WORK.md` (本エントリ追加)

- **文書負債の一括根本治療 (F-doc-cleanup)** (F-doc-cleanup / 2026-05-03 完了)
  - 発生バッチ: F-state-protocol / F-state-protocol-supplement / F-doc-backfill / F-doc-backfill-supplement / F-cleanup-merge-streak の文書整備系 5 連発の最終仕上げ。Phase A.5-3a 完了 → A.5-3a-verify 着手前に過去の文書負債 (F-13 隠れ層未昇格、DECISION_LOG 遡及記録の未完、CLAUDE.md の現運用乖離、REFACTORING_PLAN.md の重複ドキュメント化、2026-05-03 議論結果の docs 未反映、拡張性差し込み判断ルールの暗黙運用) を一括清算する必要があった。カズヤ哲学「対症療法じゃなくて根本治療」「負の遺産残さないように」に従い、注記による応急処置ではなく文書構造そのものを整地。
  - 対応内容: (Task A) F-13 隠れ層を防衛機構の正式 5 層目として昇格 — DECISION_LOG エントリ追加、CURRENT_STATE 防衛機構表を 4+1 → 5 層化、EDITORIAL_MISSION_FILTER_DESIGN.md に F-13 隠れ層セクション追加、DISCUSSION_NOTES の該当エントリ削除。(Task B) DECISION_LOG 遡及記録 7 エントリ追加 — F-13 / F-13.B / F-15 / F-16-A / F-12-A / F-12-B / F-14 の本体エントリを既存 docs から事実集約のみで再構成 (新規情報の創作なし)、各エントリにコミットハッシュと日時を実測値で記録。(Task C) CLAUDE.md 全面書き直し — 責務を「Claude Code 振る舞い指針」に集約、プロジェクト概要 / 不変原則 / 触ってはいけないリスト / 将来対応リスト運用 / FUTURE_WORK レビュータイミング / ファイル配置等の重複セクションを完全削除し、CURRENT_STATE / BATCH_PROTOCOL への導線のみに整理。(Task D) REFACTORING_PLAN.md 整理 — 冒頭にアーカイブ注記追加 (歴史的記録として保持、Phase 命名整合化)、FUTURE_WORK 緊急度低に最終整理エントリ追加。(Task E) 2026-05-03 議論内容の docs 反映 — DISCUSSION_NOTES Phase B 方向性エントリを 3 択構造に更新、クラウド誤り 6 (過剰拡張性の罠) 追加、DECISION_LOG に「Phase B 方向性整理 + 拡張性原則の力点確定 + verify 順序見直し」エントリ追加、FUTURE_WORK の Phase A.5-3a-verify セクションを順序見直し (1st: jp-coverage、2nd: 3b 着手、perspective/script-quality は 3b/3c 並走、image-prompt-spec は 3b 直前 or 3b 内) に合わせて更新。(Task F) 拡張性差し込み判断ルールの BATCH_PROTOCOL 明文化 — 3 条件 + 4 つの過去判断例 (ChannelConfig YAML 化 / Publisher 抽象 / Renderer 抽象化 / Content Format 抽象化) + 例外 (文書層) を新セクションとして追加。(Task 1-5 のドッグフーディング) BATCH_PROTOCOL Task 1-5 を本バッチ自身に適用。リグレッション影響なし (docs/ + CLAUDE.md のみ変更、src/ tests/ configs/ は 0 行変更、baseline 1315 passed 維持)。
  - 関連ファイル: `docs/DECISION_LOG.md` (Task A エントリ + Task B 7 エントリ + Task E-3 エントリ = 計 9 エントリ追加), `docs/CURRENT_STATE.md` (防衛機構表 5 層化 + 次バッチ候補刷新 + main HEAD / 直近 5 件ログ / baseline 実測値更新), `docs/BATCH_PROTOCOL.md` (拡張性差し込み判断ルール新設), `docs/DISCUSSION_NOTES.md` (F-13 隠れ層エントリ削除 + Phase B エントリ更新 + クラウド誤り 6 追加 = 18 → 17 → 18 Active), `docs/EDITORIAL_MISSION_FILTER_DESIGN.md` (F-13 隠れ層セクション追加), `docs/REFACTORING_PLAN.md` (冒頭アーカイブ注記追加), `docs/FUTURE_WORK.md` (verify 順序更新 + REFACTORING_PLAN 整理エントリ追加 + 本エントリ), `CLAUDE.md` (全面書き直し)

- **「連続 main マージ成功カウント」廃止 (F-cleanup-merge-streak)** (F-cleanup-merge-streak / 2026-05-02 完了)
  - 発生バッチ: F-state-protocol (2026-05-01) で CURRENT_STATE.md / BATCH_PROTOCOL.md に「連続 main マージ成功カウント」を導入したが、F-state-protocol-supplement / F-doc-backfill / F-doc-backfill-supplement の 3 連続バッチで Claude Code が Task 5 でこの数値を更新し忘れる事象が発生 (CURRENT_STATE.md は 11 連続のまま、実際は 15 連続)。カズヤとの議論 (2026-05-02) で指標自体の意味を再検討した結果、(1) 何の意思決定にも使えない (12 連続と 100 連続で何が違うのか?)、(2) 品質保証は別の指標 (baseline 1315 passed / 試運転動画化率) で担保されている、(3) 「カウントを途切れさせたくない」という悪いインセンティブを生む、(4) 重要数値 (main HEAD / baseline / Phase) と並べると情報ノイズになる、と判明。カズヤ哲学「対症療法じゃなくて根本治療」「負の遺産残さないように」に照らし、形骸化リスクのある指標を早期削除。
  - 対応内容: (1) `docs/CURRENT_STATE.md` の「連続 main マージ成功カウント」項目を完全削除 + main HEAD コミット (1e4a932 → c736dc2) と直近 5 件コミットログを実測値で更新 (3 連続バッチでの Task 5 数値更新漏れを回収)。(2) `docs/BATCH_PROTOCOL.md` の Task 5 仕様から「連続 main マージ成功カウント」言及を完全削除し、「main HEAD ハッシュは `git log -1 --format=%H` で実測値を取得、直近 5 件ログは `git log --oneline -5` で取得」の明示注記を追加 (機械的踏襲・更新漏れの再発防止)。(3) `docs/DECISION_LOG.md` に「F-cleanup-merge-streak — 連続 main マージ成功カウント廃止」エントリ追加 (廃止理由 4 点 + 悪いインセンティブの位置付け)。(4) `docs/DISCUSSION_NOTES.md` に「仕組み導入時の機械的踏襲リスク」エントリ追加 (将来の F-state-protocol-v2 等で「指標導入チェックリスト」として運用ルール化検討の学習材料)。(5) BATCH_PROTOCOL Task 1-5 を本バッチ自身に適用 (ドッグフーディング)。リグレッション影響なし (docs/ のみ変更、src/ tests/ configs/ は 0 行変更、baseline 1315 passed 維持)。
  - 関連ファイル: `docs/CURRENT_STATE.md` (連続成功カウント削除 + main HEAD / 直近 5 件ログ更新), `docs/BATCH_PROTOCOL.md` (Task 5 仕様修正 + git log 実測値取得の明示), `docs/DECISION_LOG.md` (本廃止エントリ追加), `docs/DISCUSSION_NOTES.md` (機械的踏襲リスクエントリ = 18 Active), `docs/FUTURE_WORK.md` (本エントリ)

- **画像生成候補確定 + 自動投稿フェーズ方針 + 拡張性原則の明文化 (F-doc-backfill-supplement)** (F-doc-backfill-supplement / 2026-05-02 完了)
  - 発生バッチ: F-doc-backfill (2026-05-02) 直後にカズヤとの議論で 3 つの追加判断が確定: (1) ChatGPT Images 2.0 (gpt-image-2) を画像生成候補に正式追加 (DALL-E 3 から差し替え、2026-04-21 リリースの OpenAI 最新モデル、Image Arena #1)、(2) 自動投稿フェーズ方針確定 (Phase A.5-3d は geo_lens のみ単独本番、TikTok と YouTube Shorts 両方同時、完全自動投稿)、(3) 拡張性原則の明文化 (Phase A.5-3c 合成パート自動化実装時に「将来の多チャンネル対応 / 別形式展開を阻害しない最小限の抽象化」を設計原則として遵守)。Phase B 以降の方向性 (japan_athletes / k_pulse 追加 / 動画継続 / 独自メディア化 / カテゴリ細分化等) は Phase A.5-3d 安定稼働後に判断保留。
  - 対応内容: (1) `docs/FUTURE_WORK.md` の F-image-prompt-spec / Phase A.5-3b / F-image-gen-integration の画像生成ツール候補を ChatGPT Images 2.0 (gpt-image-2) に差し替え (DALL-E 3 削除、価格・特徴・比較観点の補足追記)。(2) `docs/FUTURE_WORK.md` の Phase A.5-3d エントリに「投稿対象: geo_lens のみ」「投稿先: TikTok + YouTube Shorts 同時」「投稿モード: 完全自動 (cron 6 時間おき、人手介入ゼロ)」「拡張性確保: configs/channels/{channel_id}.yaml で投稿先 / 形式 / カテゴリを切替可能に」を明記。(3) `docs/DECISION_LOG.md` に 4 エントリ追加 (本バッチ概要 + ChatGPT Images 2.0 採用 + 自動投稿フェーズ方針確定 + 拡張性原則の明文化)。(4) `docs/DISCUSSION_NOTES.md` に「Phase B 以降の方向性未確定」エントリ追加 (シナリオ A〜E の整理、Phase A.5-3d 安定稼働後に再評価)。(5) `docs/CURRENT_STATE.md` に「Phase A.5-3d 投稿対象の補足」セクションを追加 (geo_lens のみ / TikTok + YouTube 同時 / 完全自動 + Phase A.5-3c 拡張性原則遵守)。(6) BATCH_PROTOCOL Task 1-5 を本バッチ自身に適用 (ドッグフーディング)。リグレッション影響なし (docs/ のみ変更、src/ tests/ configs/ は 0 行変更、baseline 1315 passed 維持)。
  - 関連ファイル: `docs/FUTURE_WORK.md` (F-image-prompt-spec / Phase A.5-3b / F-image-gen-integration / Phase A.5-3d 改訂 + 本エントリ), `docs/DECISION_LOG.md` (4 エントリ追加), `docs/DISCUSSION_NOTES.md` (1 エントリ追加 = 17 Active), `docs/CURRENT_STATE.md` (Phase A.5-3d 投稿対象の補足セクション追加)

- **過去 19 セッション分の積み残し登録 + ロードマップ大幅改訂 (F-doc-backfill)** (F-doc-backfill / 2026-05-02 完了)
  - 発生バッチ: F-state-protocol / F-state-protocol-supplement で CURRENT_STATE.md / DISCUSSION_NOTES.md / Phase A.5-3a-verify ロードマップを整備した直後、2026-05-02 のカズヤとの議論で「F-verify-e2e / F-verify-rss は過剰防衛」「ElevenLabs 採用なら macOS say の Linux 対応 (F-16-B-pre) は無意味」「動画合成は Remotion で確定 (Phase A.5-3b から使う)」「画像プロンプト出力仕様の確認が必要」「過去 19 セッション分の積み残し (Phase 1 / Phase B / Phase C / クラウド誤り 1-4 / 三角測量未対応 / 3 ソース対比未実装 等) が未登録」が判明。ロードマップを 4 段階 (3a-verify → 3b → 3c → 3d) に再構成する必要があった。
  - 対応内容: (1) FUTURE_WORK.md の Phase A.5-3a-verify を 5→4 カテゴリに縮小 (F-verify-e2e / F-verify-rss を削除、F-image-prompt-spec を新規追加)。(2) Phase A.5-3b を Remotion + ElevenLabs + 画像生成前提に書き直し (CapCut 仮組み案を廃止)。(3) Phase A.5-3c (合成パート自動化) を新設、F-elevenlabs-integration / F-image-gen-integration / F-video-compose-integration / F-cron の 4 エントリを登録。(4) Phase A.5-3d (投稿前ゲート + 自動投稿) を新設。(5) Phase 1 (1-A〜1-D + TECH_DEBT 2.1/2.2/2.3/2.5 同時対応) を緊急度 中に登録。(6) Phase B (B-1〜B-7) と Phase C (C-1〜C-5) を緊急度 低に登録。(7) 観察中項目 (F-17 候補 / _FRAMING_RESULTS LRU / 並列化検討) を新設。(8) DISCUSSION_NOTES.md にクラウド誤り 1-4 + 三角測量未対応 + 3 ソース対比部分実装の 6 エントリ追加。(9) DECISION_LOG.md に F-doc-backfill 概要 + 「Phase A.5-3a-verify スコープ縮小」「macOS say 廃止 + ElevenLabs 前倒し」「動画合成ツール Remotion 採用」「Supabase 移行『今週末は危険すぎる』判断 (Apr 30 遡及)」「6 パターン武器庫 → 4 パターン削減経緯 (遡及)」「Hook 5 類型 / 視聴維持ピーク 4 点設計の廃止経緯 (遡及)」の 7 エントリ追加。(10) CURRENT_STATE.md の「次バッチ候補」を新ロードマップに合わせて全置換更新。(11) BATCH_PROTOCOL Task 1-5 を本バッチ自身に適用 (ドッグフーディング)。リグレッション影響なし (docs/ のみ変更、src/ tests/ configs/ は 0 行変更、baseline 1315 passed 維持)。
  - 関連ファイル: `docs/FUTURE_WORK.md` (Phase A.5-3a-verify 縮小 + 3c/3d/Phase1/B/C/観察中項目 新設 + 本エントリ), `docs/DISCUSSION_NOTES.md` (6 エントリ追加 = 16 Active), `docs/DECISION_LOG.md` (7 エントリ追加), `docs/CURRENT_STATE.md` (次バッチ候補刷新)

- **CURRENT_STATE / DISCUSSION_NOTES 導入と不変原則 2 の正確化 (F-state-protocol)** (F-state-protocol / 2026-05-01 完了)
  - 発生バッチ: Phase A.5-3a で 11 連続 main マージ成功 (F-12-A → F-12-B-1-extension) を達成したが、チャット移行のたびに 2806 行の引き継ぎプロンプトを手作業で再構築する運用が持続不可能になった。過去の決定事項 (C-1/C-2/C-3 RPM 対策、F-13 隠れ層、F-7-α 部分実装等) がバッチ歴史リストから消える事故、不変原則 2「script_writer.py 一切変更不可」が実装と乖離 (F-12-A / F-12-B / Batch 5 で大改修済み、新ルート稼働中)、DECISION_LOG / FUTURE_WORK が時系列ログとして機能する一方で「今この瞬間のスナップショット」と「議論中の未確定メモ蓄積」の仕組みがない、といった構造的課題が顕在化していた。
  - 対応内容: (1) `docs/CURRENT_STATE.md` を新規作成 — 8 セクション構成 (リポジトリ状態 / 現在のフェーズ / 直近試運転 / 防衛機構の現状 4+1 層 / 触ってよい・ダメ領域マップ / 不変原則 5 つ / カズヤの直近フィードバック / 関連ドキュメント導線)、初回値として main HEAD `1e4a932` / baseline `1315 passed` / 11 連続成功 / 試運転 7-K 動画化率 100% / Phase A.5-3a 完了 → A.5-3a-verify 着手前を投入。バッチ完了時に「全置換更新」する運用 (追記ではない)。(2) `docs/DISCUSSION_NOTES.md` を新規作成 — 「未分類 (Active)」と「アーカイブ」の 2 セクション構成、初期エントリ 10 件投入 (手動 PoC 軌道修正 / C-1/C-2/C-3 欠落 / CLAUDE_CODE_INSTRUCTIONS.md 遺産化 / スコープ転換昇格ルール / STEP 3 と F-12-B-1 のレイヤー関係 / ★不変原則 2 乖離 / F-13 隠れ層 / target_enemy 排除 / F-12-B-1.5 と原則 2 不整合 / F-7-α 部分実装済み)。(3) `docs/BATCH_PROTOCOL.md` を拡張 — 不変原則 5 つを A.5-3a 時点版に差し替え (特に不変原則 2 を「既存ルート不可、新ルート可、`_CHAR_BOUNDS` 等の定数調整は最小改変なら許容」に正確化)、Task 4 (DISCUSSION_NOTES 整理: 4-A 新規追加 + 4-B 既存再評価) と Task 5 (CURRENT_STATE 全置換更新) を追加、バッチプロンプトテンプレートを Task 1-5 に更新。(4) `CLAUDE.md` を更新 — 必読ドキュメントリストの最上位に CURRENT_STATE.md を配置、DISCUSSION_NOTES.md を 5 番目に追加、参照順序を明示化。(5) 本バッチ自身に Task 1-5 を適用 (ドッグフーディング)。リグレッション影響なし (docs/ + CLAUDE.md のみ変更、src/ tests/ configs/ は 0 行変更、baseline 1315 passed 維持)。
  - 関連ファイル: `docs/CURRENT_STATE.md` (新規), `docs/DISCUSSION_NOTES.md` (新規), `docs/BATCH_PROTOCOL.md` (不変原則差し替え + Task 4/5 追加), `CLAUDE.md` (必読リスト刷新), `docs/DECISION_LOG.md` (F-state-protocol エントリ), `docs/FUTURE_WORK.md` (本エントリ)

- **punchline 定義の「シニカル × 具体着地」両立化 (F-12-B-1-extension)** (F-12-B-1-extension / 2026-05-01 完了)
  - 発生バッチ: F-12-B-1 (視聴者ファースト原則追加) 完了後の試運転で、punchline 末尾に抽象比喩の癖が残存することが観察された (「地政学の檻に閉じ込める」「冷徹な力学」)。根本原因は `configs/prompts/analysis/geo_lens/script_with_analysis.md` STEP 2 の punchline 定義「シニカルかつ知的な余韻」が抽象詩を呼び込んでいたこと、および例示された「綺麗事を信じた側が損をする」が STEP 3 禁止表現 (物申す系 YouTuber 構文) と矛盾していたこと。視聴者ファースト原則 (抽象より具体) と punchline 定義 (シニカルな余韻) の方向性が一貫していない構造的問題。
  - 対応内容: STEP 2 punchline 定義のみを修正 (hook / setup / twist は不変)。「シニカルかつ知的な余韻を残す」は保持しつつ、「ただし『シニカル』は抽象詩や抽象比喩で飾ることではない。視聴者の生活実感（電気代、物価、給料、税金、日常の選択）に着地して初めて、シニカルさが知的な余韻として機能する」で両立を明文化。優れた例として「秩序を信じる代償を、私たちは電気代という形で支払うことになる」(F-12-B-1 議論でカズヤが評価した実例 ── シニカル → 具体着地の両立) を、避けるべき例として「地政学の檻に閉じ込められた国の宿命」「冷徹な力学が動く」(試運転で観察された抽象比喩) を併記。「綺麗事を信じた側が損をする」例を削除して STEP 3 との矛盾を解消。試運転は LLM 出力依存のため未実施 (時間と再現性を考慮、必須化せず継続観察項目とした)。リグレッション影響なし (1315 passed 維持)。
  - 関連ファイル: `configs/prompts/analysis/geo_lens/script_with_analysis.md` (STEP 2 punchline のみ +10 行 / -2 行), `docs/DECISION_LOG.md` (F-12-B-1-extension エントリ), `docs/FUTURE_WORK.md` (本エントリ)

- **台本プロンプトの「視聴者ファースト」原則追加 (F-12-B-1)** (F-12-B-1 / 2026-05-01 完了)
  - 発生バッチ: 試運転 7-K (2026-05-01) の baseline 台本 (cls-7bd1406438b6 FIFA 提訴 / cls-579833967531 フーシ派) で、カズヤから 6 個の問題が指摘された (略しすぎ「イスラエル入植地クラブ」/補足なし「スポーツ仲裁裁判所」/不明「ロシア侵攻時の即時排除」/直訳「公然たる支持」/抽象比喩「地政学的断層」「直撃弾」/硬い文語「発動」「ツール」)。`configs/prompts/analysis/geo_lens/script_with_analysis.md` を分析した結果、「扇動・陰謀論の禁止」(STEP 3) は強力だが「視聴者へのわかりやすさ」への配慮が皆無で、LLM が「教科書っぽい硬い分析調」に寄っていたことが根本原因。
  - 対応内容: 同プロンプトの【ターゲット】直後・【入力データ】の前に「【視聴者ファーストの編集姿勢】」セクションを追加 (3 原則: 聞いてわかる / 抽象より具体 / 読み上げて自然 + 合格基準「TikTok/Shorts で違和感なく聞けるか」)。NG リストではなく姿勢として記述し、判断は LLM の知性に委ねる設計。既存セクションは一切変更せず追加のみ。あわせて `docs/BATCH_PROTOCOL.md` 不変原則 2 の例外条項を `configs/prompts/script/` → `configs/prompts/` に拡大し、現状の主戦場が `configs/prompts/analysis/geo_lens/` であることを注記。試運転 (cls-56c4197b6fd2 米イスラエル隠密作戦) で「中東独立メディアのミドル・イースト・アイ」のような固有名詞補足、「動かしたんです」「ある日突然」のような話し言葉的接続を確認。char validation で 1 リトライ発生 (setup=94→82 字)、許容範囲だが継続観察項目として F-12-B-1.5 を緊急度中に新設。
  - 旧 F-12-B-1 (blind_spot_global 用フレーム追加) は試運転 7-K の結果を受けて視聴者ファースト原則の方が優先と判断され、本エントリにスコープを再定義した。
  - 関連ファイル: `configs/prompts/analysis/geo_lens/script_with_analysis.md`, `docs/BATCH_PROTOCOL.md`, `docs/DECISION_LOG.md` (F-12-B-1 エントリ), `docs/FUTURE_WORK.md` (本エントリ)

- **文書自動更新プロトコルの確立 (F-doc-protocol)** (F-doc-protocol / 2026-05-01 完了)
  - 発生バッチ: Phase A.5-2 の 7 連続バッチで DECISION_LOG.md / FUTURE_WORK.md の更新が散逸し、「台本の日本語改善」「document 更新」「手動 PoC」等の重要事項が忘却される問題が発生。月次レビュー (FW-1) だけでは速度が追いつかないと判明。
  - 対応内容: `docs/BATCH_PROTOCOL.md` を新規作成し、各バッチ完了時に必須となる 3 タスク (Task 1: DECISION_LOG エントリ追加 / Task 2: FUTURE_WORK 更新 / Task 3: 完了レポート明記) と 5 つの不変原則を明文化。`CLAUDE.md` 冒頭に「Hydrangea Batch Protocol」セクションを追加し、必読ドキュメントリストにも追記することで全セッションで参照される動線を整備。本プロトコル自体も月 1 レビュー対象に登録。`src/` `tests/` `configs/` には一切手を入れず、ドキュメント層のみで仕組み化 (リグレッション 1315 passed 維持)。
  - 関連ファイル: `docs/BATCH_PROTOCOL.md` (新規), `CLAUDE.md` (参照追加), `docs/DECISION_LOG.md` (Task 1 最初の実装例), `docs/FUTURE_WORK.md` (Task 2 最初の実装例)

- **rescue path の Hydrangea ミッション本丸との矛盾 (F-13-B で完全廃止)** (F-13-B / 2026-05-01 完了)
  - 発生バッチ: 試運転 7-J (2026-04-30) で動画化率 0%。Slot-1 候補が JP=0 件で `requires_more_evidence=True` → rescue 発動 → script skip。これは Hydrangea ミッション「日本で封殺されている海外ニュース」(blind_spot_global) を skip する本末転倒な設計だった。
  - 対応内容: `_write_judge_rescue()` 関数と main.py 内の rescue 分岐を完全撤去。判定ロジック (`is_rescue_candidate`) は src/triage/gemini_judge.py 側に残置 (不変原則 3 遵守) しつつ、main.py からは呼ばれない。requires_more_evidence=True でも必ず動画化フローへ進む。試運転 7-K で 3/3 Slot 完了 (article 生成 100%、Slot-1 video まで生成) を確認。judge_report.json / followup_queries.* の新規出力が無いことも確認 (既存ファイルは履歴として残置)。
  - 関連ファイル: `src/main.py`

- **日本未報道判定のための Web 検証導入 (F-13-B 完了)** (F-13-B / 2026-05-01 完了)
  - 発生バッチ: F-13-A で JP RSS を 13 媒体に拡張後もニッチ海外ニュースは JP=0 件のケースが残ることを確認。RSS 取得漏れと「真の日本未報道」を区別できないままだった。
  - 対応内容: `src/triage/jp_coverage_verifier.py` に `JpCoverageVerifier` を新規実装。Gemini Grounding (Google Search) で日本語検索を実行し、ホワイトリスト (新聞・テレビ・通信社・主要ビジネスメディア計 27+ ドメイン) と除外リスト (Yahoo!ニュース・SNS・個人ブログ等) で照合する。判定基準は「大手メディアの報道有無のみ」(個人投稿は判定材料にしない、Hydrangea のミッション本丸: 大手の空白を埋める)。24h SQLite キャッシュ (`jp_coverage_cache` テーブル新設) で重複検証を抑制、月コスト約 $4.2 想定。Grounding API エラー時は `has_jp_coverage=True` で安全側に倒す。環境変数: `JP_COVERAGE_VERIFIER_ENABLED` / `JP_COVERAGE_CACHE_HOURS` / `JP_COVERAGE_GROUNDING_MODEL`。試運転 7-K で Slot-2 (cls-33b4f4960bf9) と Slot-3 (cls-204a683f73ee) の両方で `has_jp_coverage=False` を確認、blind_spot_global として動画化フローへ進めた。
  - 関連ファイル: `src/triage/jp_coverage_verifier.py` (新規), `src/storage/db.py` (jp_coverage_cache テーブル), `src/main.py` (Web 検証統合), `src/shared/config.py`, `.env.example`, `tests/test_f13b_rescue_abolition.py` (36 テスト)

- **日本ソース基盤の弱さ (一部対処)** (F-13-A / 2026-05-01 部分完了)
  - 発生バッチ: 試運転 7-J (2026-04-30) で動画化率 0% を観測。日本ソース 8 媒体のみで主要海外ニュースを拾えず、「日本未報道」誤判定が多発。
  - 対応内容: `configs/sources.yaml` に Mainichi / Kyodo (47news.jp 経由) / JIJI / Bloomberg_JP / Reuters_JP の 5 媒体を追加 (8 → 13 enabled JP sources)。`configs/source_profiles.yaml` に対応する authority profile を追加 (tier=top: Mainichi/Kyodo/JIJI、tier=major: Bloomberg_JP/Reuters_JP)。各 RSS は 2026-05-01 疎通確認済み (status=200, entries 50 件取得確認)。src/ tests/ には変更なし (不変原則 5 つ遵守)。
  - 残課題: 13 媒体に拡張してもニッチ海外ニュース (Gaza 電力危機等) は依然 JP ソース 0 件のケースが残る → F-13-B (Web 検証 + rescue 廃止) で根本対処
  - 関連ファイル: `configs/sources.yaml`, `configs/source_profiles.yaml`

- **MAX_PUBLISHES_PER_DAY ハードコード上限による Slot skip 問題** (F-16-A / 2026-04-30 完了)
  - 発生バッチ: 試運転 7-I (2026-04-29) で動画化率 67% (2/3) で頭打ち。Slot-3 (UAE OPEC) は AnalysisLayer 完了済みだったが MAX_PUBLISHES_PER_DAY=5 のハードコード制限で skip された
  - 対応内容: per-run 上限を `TOP_N_VIDEOS_PER_RUN` (default 1) / `TOP_N_ARTICLES_PER_RUN` (default 3) に分離。`_generate_outputs()` に `generate_video_track: bool = True` パラメータを追加し、Slot index >= TOP_N_VIDEOS_PER_RUN は article のみ生成。`MAX_PUBLISHES_PER_DAY` は default 999 に変更し実質撤廃 (後方互換のため env / コードからは読み続ける)。video > article は min クランプして警告。AnalysisLayer Top 3 対象 (F-15) と publish_count インクリメント (後方互換) は維持。
  - cron 自動実行 (F-16-B) と組み合わせて公開頻度を制御する設計に移行。本番運用想定: 4 run/日 × 1 動画 = 4 動画/日 + 4 run × 3 記事 = 12 記事/日
  - 関連ファイル: `src/shared/config.py`, `src/main.py`, `.env.example`, `tests/test_f16a_per_run_limits.py` (26 テスト追加)

- **Slot-event_id 同期問題（AnalysisLayer 対象 vs Top-3 台本生成対象の不整合）** (F-15 / 2026-04-29 完了)
  - 発生バッチ: 試運転 7-H' (2026-04-29 21:20) で動画化率 1/3 (33%) で頭打ちが発覚
  - 対応内容: `src/main.py` の AnalysisLayer 対象選定を `all_ranked[:_top_n_for_analysis]`（Tier 1 score 降順）から、Top-3 台本生成ループと同じ `sorted(all_ranked, key=lambda se: _elite_judge_results[...].total_score, reverse=True)[:_top_n_for_analysis]`（Elite Judge total_score 降順）に変更。これにより両ループが必ず同じ event_id 列を対象とするようになり、Slot-event_id ズレで「analysis_result is None, skipping」になっていた構造的問題を解消。
  - 関連ドキュメント: `docs/EDITORIAL_MISSION_FILTER_DESIGN.md` の F-15 セクション (該当があれば)
  - 関連ファイル: `src/main.py`, `tests/test_main_f15_slot_event_sync.py`
  - 試運転 7-I で動画化率の改善 (期待値 67-100%) を確認後にカズヤがマージ判断

- **Analysis Layer の hidden_stakes axis バグ** (F-3 / 2026-04-28 完了)
  - 発生バッチ: F-1.5 試運転で発覚 → F-3 で対応完了
  - 対応内容: `src/analysis/perspective_selector.py::select_perspective()` を 3 段階フォールバックに強化。LLM が Top3 外の axis (`hidden_stakes` 等) を選んだ場合や、`fallback_axis_if_failed` も Top3 にない場合でも、Step 2 で Top3 内の最高スコア候補を強制採用する。candidates が 1 件以上あれば必ず `PerspectiveCandidate` を返すため、Slot-2 / Slot-3 で `analysis_result=None` となり動画化失敗していた問題を解消。
  - 関連ドキュメント: `docs/EDITORIAL_MISSION_FILTER_DESIGN.md` の F-3 セクション
  - 関連ファイル: `src/analysis/perspective_selector.py`, `tests/test_perspective_selector.py`, `tests/test_analysis_engine.py`

- **Tier 階層の役割分け（E-3'）** (E-3' / 2026-04-28 完了)
  - 発生バッチ: 試運転7-A / 7-B で 503 待機 (5〜10分) が試運転時間 (13分) の大半を占めることが判明
  - 対応内容: `src/llm/factory.py` に `LIGHTWEIGHT_ROLES` / `QUALITY_ROLES` を定義し、`_get_tier_models_for_role(role)` / `_get_max_attempts_for_role(role)` で役割別に Tier 階層と MAX_ATTEMPTS を切り替えるよう改修。Lightweight 系統は GA 主軸 (gemini-2.5-flash → flash-lite → preview-lite → flash-preview) で 503 回避、Quality 系統は Preview 主軸 (gemini-3-flash-preview → 2.5-flash → preview-lite → flash-lite) で性能優先。env 由来のデフォルトを公式の性能順に正規化。
  - 関連ドキュメント: `docs/EDITORIAL_MISSION_FILTER_DESIGN.md` の E-3' セクション
  - 関連ファイル: `src/llm/factory.py`, `.env.example`, `tests/test_factory_role_tier_separation.py`

- **_MAX_ATTEMPTS_PER_TIER = 1（503 リトライ削減）** (E-3' / 2026-04-28 完了)
  - 発生バッチ: E-1 で見送り → E-3' で役割別 MAX_ATTEMPTS として実装
  - 対応内容: 当初は `_MAX_ATTEMPTS_PER_TIER=1` への一括変更を計画していたが、E-3' でより安全な役割別 MAX_ATTEMPTS に切り替え。`GEMINI_LIGHTWEIGHT_MAX_ATTEMPTS=2` / `GEMINI_QUALITY_MAX_ATTEMPTS=2` に統一 (失敗率約 0.002%)。`TieredGeminiClient` のコンストラクタに `max_attempts_per_tier` 引数を追加し、未指定時は既定値 3 を維持することで、`test_factory_quota_handling.py` の3テストを書き換えずに後方互換を保った。
  - 関連ドキュメント: `docs/EDITORIAL_MISSION_FILTER_DESIGN.md` の E-3' セクション
  - 関連ファイル: `src/llm/factory.py`, `.env.example`, `tests/test_factory_quota_handling.py` (変更なし)
