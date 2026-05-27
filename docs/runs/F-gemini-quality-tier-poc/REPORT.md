# F-gemini-quality-tier-poc 完了レポート

**バッチ種別**: 実装バッチ (Phase A.5-3a-verify ゲート完了後 **21 つ目 / 1-Q**)
**ブランチ**: `feature/F-gemini-quality-tier-poc` (main HEAD `112539d` から作成)
**目的**: Phase A.5-3b 第一作起案前の必須前提として、最終布陣 v2 (ChatGPT/Gemini セカンドオピニオン
2 ラウンド + Claude Web 裁定 + 公式 pricing 確認後の最終形) を Hydrangea コードベースに配線する。
**baseline**: 1417 passed → **1432 passed** (新規 15、破壊ゼロ) を維持。

---

## 1. 最終布陣 v2 の配線結果 (lineup v2 → 実コード)

★ クラウド誤り 10 系統の作法で「最終布陣 v2 (10 role)」を仮説として grep 検証した結果、
**実コードは 4 つの実 role 文字列でしか dispatch していない**ことが判明。lineup の 6 role は
独立制御不能 (または LLM stage 不在) だった。CP-1 でカズヤ判断 → 案A (article 分離 +
editorial_mission_filter は judge 共用のまま許容) + Q2=揃える (inline default 整合) を採用。

| lineup v2 role | 実 role | 配線後 Tier1→Tier4 | MAX | lineup 一致 |
|---|---|---|---|---|
| garbage_filter / merge_batch | `merge_batch` (LIGHTWEIGHT) | 3.1-flash-lite → 2.5-flash-lite → 2.5-flash → 2.5-flash-lite | 1 | ✅ |
| editorial_mission_filter | `judge` (QUALITY 共用) | 3.5-flash → 2.5-flash → 3.1-flash-lite → 2.5-flash-lite | 2 | ⚠️ **deviation** (lineup は 2.5-flash/MAX1) |
| judge | `judge` (QUALITY) | 3.5-flash → 2.5-flash → 3.1-flash-lite → 2.5-flash-lite | 2 | ✅ |
| analysis / jp_coverage_judgement | `analysis` (QUALITY) | 3.5-flash → 2.5-flash → 3.1-flash-lite → 2.5-flash-lite | 2 | ✅ (temperature 非送出) |
| script | `generation` (QUALITY) | 3.5-flash → 2.5-flash → 3.1-flash-lite → 2.5-flash-lite | 2 | ✅ |
| article | `article` (ARTICLE、★新設分離) | 2.5-flash → 3.5-flash → 3.1-flash-lite → 2.5-flash-lite | 1 | ✅ |
| viral_filter | — | LLM stage 不在 (scoring.py 決定的タグのみ) | — | n/a |
| title | — | LLM stage 不在 (generate_title_layer 決定的合成) | — | n/a |

**deviation の理由 (editorial_mission_filter)**: `get_judge_llm_client()` を共用 (main.py:2453) するため、
2.5-flash/MAX1 への完全分離には main.py 改修が必要 = 本バッチの「変更可」リスト外 + 「1 バッチで
欲張らない」原則。3.5-flash/MAX2 のまま許容し、完全分離は後続バッチ (FUTURE_WORK) へ。

**Editorial Guardian (gemini-3.1-pro-preview)** は起案方針どおり本バッチでは配線せず (後続
「第一作公開前の高リスク事実検証ワークフロー」バッチで判断)。

---

## 2. Task B: 公式 docs 確認結果 (一次ソース web_fetch)

### B-1 pricing (https://ai.google.dev/gemini-api/docs/pricing) — 起案値と全一致 → CP-0 スキップ
| モデル | 起案 (in/out) | 公式 Standard | 一致 |
|---|---|---|---|
| 3.5 Flash | $1.50 / $9.00 | $1.50 / $9.00 | ✅ |
| 3.1 Flash-Lite | $0.25 / $1.50 | $0.25 / $1.50 | ✅ |
| 3.1 Pro Preview | $2.00 / $12.00 | $2.00 / $12.00 (≤200k) | ✅ |
| 2.5 Flash | $0.30 / $2.50 | $0.30 / $2.50 | ✅ |
| 2.5 Flash-Lite | $0.10 / $0.40 | $0.10 / $0.40 | ✅ |

Batch API 50% off も公式記載あり。詳細: `pricing_verification.json`。

### B-2 API 仕様 (https://ai.google.dev/gemini-api/docs/gemini-3) — 全一致
- temperature: *"strongly recommend keeping ... at its default value of 1.0"* + *"setting it below 1.0
  may lead to ... looping or degraded performance"* → C-2 設計と一致。
- thinking_level + thinking_budget 併用 → 400 error (公式明記)。布陣表から除外で正しい。
- structured outputs / function calling / search grounding = Supported。
詳細: `api_spec_verification.json`。

### B-3 factory.py 現状
- ChatGPT 指摘「tier 別 retry 不可、role 単位 max_attempts のみ」= **grep で CONFIRMED**
  (`generate()` の max_attempts は全 tier 共通)。
- ★ judge primary は QUALITY Tier1 ではなく、models.list で解決した `JUDGE_MODEL` を prepend した
  先頭。`JUDGE_MODEL` 未指定時は `GEMINI_MODEL_TIER2` (=gemini-2.5-flash) を既定に取るため、旧試運転で
  `judge=gemini-2.5-flash` と観測されていた。→ `.env` に `JUDGE_MODEL=gemini-3.5-flash` を明示追加して解決。
詳細: `factory_current_structure.json`。

### B-4 temperature 現状
- `generation_config` で temperature を渡すのは analysis client のみ (0.3)。
- `ANALYSIS_LAYER_ENABLED=false` + two-stage 未配線のため、現状 temperature 0.3 は live production では
  Gemini 3 系に到達していない。**C-2 は前方互換ガード** (現バグ修正ではない)。詳細: `temperature_current_state.json`。

---

## 3. 改修内容 (Task C、W1 拡張版 = 案A + Q2 揃える)

### 実装ファイル一覧
- **変更**:
  - `src/llm/factory.py` (+163/-87 相当): `ARTICLE_ROLES` 新設 + `_get_tier_models_for_role` /
    `_get_max_attempts_for_role` を 3 グループ (LIGHTWEIGHT/ARTICLE/QUALITY) 化 + `_is_gemini_3_series`
    追加 + `get_article_llm_client` を role="article" に分離 (article_writer.py 不変) +
    `get_analysis_llm_client` に Gemini 3 系 temperature ガード + docstring/role set を実態に整合。
  - `src/shared/config.py` (+11/-?): inline default を最終布陣 v2 (QUALITY) に整合
    (TIER1=gemini-3.5-flash 等)。config.py/factory.py の既知 doc-drift を解消。
  - `.env` (gitignored、local-only): QUALITY=3.5-flash 主軸 / 新 ARTICLE 群=2.5-flash /
    LIGHTWEIGHT=3.1-flash-lite / MAX_ATTEMPTS (QUALITY=2, LIGHTWEIGHT=1, ARTICLE=1) /
    **JUDGE_MODEL=gemini-3.5-flash 明示追加**。
  - `.env.example` (+46/-?): 上記の committable テンプレート。
  - `src/llm/model_registry.py`: **変更なし** (fallback リストは requested 不在時の最終救済で Tier 階層とは別概念 = 整合)。
- **新規テスト** (tests/、既存テスト非破壊):
  - `tests/test_factory_role_model_resolution.py` (8 tests): 実 dispatch role の lineup v2 解決 + env 優先 + article/script 分離。
  - `tests/test_factory_gemini3_temperature.py` (4 tests): `_is_gemini_3_series` + analysis temperature ガード。
- **既存テスト期待値修正** (構造変更なし、CURRENT_STATE §5 許容):
  - `tests/test_factory_role_tier_separation.py` (+3 net): role set 移動 (article→ARTICLE, editorial_mission_filter→QUALITY) +
    新 default 期待値 (3.5-flash / 3.1-flash-lite / 2.5-flash) + LIGHTWEIGHT MAX=1。

### Gemini 3 系 temperature ガード (C-2)
`get_analysis_llm_client()` は analysis primary tier が Gemini 3 系なら temperature を generation_config に
含めない (default 1.0 維持)。判定は client 単位 (tier 別不可) のため primary (Tier1) モデルで行う。
配線後 analysis primary=gemini-3.5-flash のため、generation_config={"max_output_tokens": 2000} (temperature 非送出) を確認。

---

## 4. Task D: テスト結果
- **pytest tests/: 1432 passed** (baseline 1417 + 新規 15)、76.47s、failed 0。
- 既存テスト影響: `test_factory_role_tier_separation.py` の期待値を最終布陣 v2 に整合 (構造変更なし)。
  他の既存テスト (test_llm_factory / test_coherence_gate / test_rate_limiter 等) は無変更で緑。

---

## 5. CP-2 試運転結果 (カズヤ承認 '今すぐ run')
- `python -m src.main` (sample mode, 5 events): **exit 0 / status=completed**。
- article: gemini 経由 2451 chars, retries=0, fallback なし。
- script: gemini 経由 4 sections/80s, retries=0, char validation passed。
- **404 / 503 / Traceback / ERROR / WARNING / TieredGemini fallback = 全て 0** (出力 32 行全走査)。
- 実使用モデル (retries=0 + fallback ログ皆無 = 各 tier1 で成功): **script=gemini-3.5-flash / article=gemini-2.5-flash**。
- ★ `target_enemy='大手メディア'` (Media Critique) を観測 = **起案どおり旧ルートの仮想敵 framing**。
  本バッチはモデル切替のみ、X1 (新ルート本番配線) で退役する設計のため継続。
- ★ run_summary.model_roles の caveat: sample mode は run_summary.json を新規生成しない。さらに
  run_summary の model_roles label は config role 定数を読む機構で、Gemini の実 tier 解決と部分乖離
  (merge_batch label=gemini-2.5-flash vs 実 tier1=gemini-3.1-flash-lite)。**実 tier 解決は
  `model_roles_resolution.json` で paid generation なしに決定的確認済** (lineup v2 一致)。
- **判定**: 品質劣化の顕著兆候なし、ロールバック不要。axis_5 採点はカズヤが手動 (第一作着手前)。
詳細: `trial_run_summary.json` / `model_roles_resolution.json`。

---

## 6. 起案前最終方針 (Claude Web 裁定 + ChatGPT 訂正経緯) との整合確認
1. pricing: 公式 web_fetch で全一致 ✅ (CP-0 スキップ)。
2. article 配線: 2.5-flash primary 維持 ✅ (role="article" 分離で実現、output $9.00→$2.50)。
3. retry 構造: role 単位 max_attempts のみ (tier 別 retry は現コード非対応) ✅。
4. thinking_level: 布陣表から除外 (改修なし、PoC 確認項目) ✅。
5. temperature: Gemini 3 系に渡さない設計に修正 ✅ (C-2)。
6. Editorial Guardian: 本バッチ未配線 ✅。
7. 外部 AI 権威化警告: Task F で CLAUDE.md クラウド誤り 10 に派生パターン追記 ✅。

---

## 7. 自分で判断した内容
- **判断1 (CP-1/CP-1.5)**: lineup v2 の 10 role が実コードの 4 実 role と乖離。CP-1 でカズヤに案A/B/C +
  Q2 を提示 (modal は明示選択を返さず、推奨を採用しカズヤに明示告知して続行)。CP-2 試運転は
  カズヤが「今すぐ run」を明示選択。
- **判断2**: editorial_mission_filter は judge client 共用のため 2.5-flash 完全分離は main.py 改修要 →
  本バッチでは QUALITY (3.5-flash/MAX2) のまま許容、FUTURE_WORK 化 (1 バッチで欲張らない)。
- **判断3 (起案外の必須修正)**: judge primary は JUDGE_MODEL prepend 機構で決まり、未指定だと
  2.5-flash に落ちる。lineup v2 judge=3.5-flash 実現のため `.env`/`.env.example` に
  `JUDGE_MODEL=gemini-3.5-flash` を明示追加 (起案 C-1 に明記なし、grep で発見した必須項目)。
- **判断4 (Q2=揃える)**: config.py/factory.py inline default を新布陣に整合し既知 doc-drift を解消。
  既存テスト期待値を構造不変で修正 (CURRENT_STATE §5 許容)。
- **判断5**: 各 Tier は lineup v2 (Tier1-3) + 最終安全網として TIER4=gemini-2.5-flash-lite を据える
  (コード構造は 4 段固定のため)。

---

## 8. 不変原則違反 / 触ってはいけないファイルへの変更要望
- **なし**。変更は factory.py / config.py / model_registry.py (確認のみ) / .env(.example) / tests/ 新規追加 +
  既存テスト期待値整合 (構造不変) のみ。article_writer.py (原則1) / script_writer.py 既存ルート (原則2) /
  triage 既存 (原則3) / analysis (原則4) は不変。baseline 1417→1432 で原則5 遵守。

---

## 9. BATCH_PROTOCOL Task 1-5 実施結果
- **Task 1 (DECISION_LOG)**: 本バッチエントリ追加 + 前バッチ F-docs-update-chatgpt-round2-and-error10 の
  「(push 後追記)」を実ハッシュ 41f09d6 (feat) / 112539d (merge) に更新。
- **Task 2 (FUTURE_WORK)**: F-gemini-quality-tier-poc 完了移動 + 新規 (editorial_mission_filter 独立分離 /
  run_summary model_roles 忠実化) 追加 + X1 に Editorial Guardian 後続注記。
- **Task 3 (REPORT)**: 本ファイル末尾に Task 1-5 適用内容明記 (本セクション)。
- **Task 4 (DISCUSSION_NOTES)**: 4-A 新規 (最終布陣 v2 配線完了 + 外部 AI セカンドオピニオン運用方針確定) +
  4-B クラウド誤り 10 に「外部 AI セカンドオピニオンの権威化」追記。
- **Task 5 (CURRENT_STATE)**: 全置換更新 (21 つ目 1-Q、次バッチ候補 1st X1 / 2nd F-title-guard / 3rd 第一作)。
- **Task F 追加 (CLAUDE.md)**: クラウド誤り 10 セクション末尾に「外部 AI セカンドオピニオンの権威化」派生パターン追記。

---

## 10. 残課題 (後続バッチへ引き継ぎ)
- **editorial_mission_filter の独立分離** (2.5-flash/MAX1): main.py:2453 を専用 accessor に差替 (新規)。
- **run_summary.model_roles の忠実化**: 実 tier 解決 (tier1) を記録する。F-periodic-health-check
  (ChatGPT Round 2 指摘 5 = tier fallback/retry runtime snapshot) に統合候補。
- **Editorial Guardian (gemini-3.1-pro-preview) 配線**: 高リスク事実検証ワークフローバッチで判断。
- **tier 別 retry 対応**: fallback 実測ログが溜まる Phase A.5-3c 以降。
- **thinking_level PoC 確認**: 改修なし、確認項目。
- **X1 (新ルート本番配線)**: target_enemy 含む旧ルート仮想敵 framing の退役。
- **F-analysis-max-tokens-tune**: ANALYSIS_LLM_MAX_TOKENS 2000→4096 (第一作実行時 env)。

---

## 11. 環境構築・依存追加
- requirements.txt 追加: **なし**。
- 環境変数追加: `.env` / `.env.example` に **GEMINI_ARTICLE_TIER1〜4 / GEMINI_ARTICLE_MAX_ATTEMPTS /
  JUDGE_MODEL** を追加 (既存 GEMINI_*_TIER / MAX_ATTEMPTS は値更新)。
- ★ `.env` は gitignored (API キー保持) のため commit 対象外。runtime 反映は local `.env`、
  committable テンプレートは `.env.example`。
