# Hydrangea — Current State (CURRENT_STATE.md)

最終更新: 2026-05-25 (★ F-f1-locale-key-fix 完了、Phase A.5-3a-verify ゲート完了後の **16 つ目のバッチ**。3 AI 三角測量 (ChatGPT + Gemini) のレビューで両者独立に指摘された `src/triage/editorial_mission_filter.py` の **locale key bug** を根本治療。`_editorial_mission_prescore` 内の `sources_by_locale.get("jp", [])` / `get("en", [])` を実データ構造の正しいキー (`"japan"` + 非 japan locale の合算 = `main.py` overseas_count パターン) に修正。機能ロジック (blindspot の if/elif・係数・cap) は不変、locale key 参照の正本化のみ。grep で当該ファイルが src/ 全体で `"jp"`/`"en"` を使う唯一のファイルと確定。★ **クラウド初期想定の訂正**: 初期バッチプロンプトは「日本ソース数が常に 0 で blindspot が不当に高く誤爆 (false positive)」と記載していたが、grep + コード精読で実態判明 = `jp_count`/`en_count` が両方常に 0 で中間 elif (12.0/10.0/8.0) が **dead code**、実害は「中間解像度 8〜12 点の永久喪失 (false negative 方向)」、第1分岐 `has_en and not has_jp → 15.0` は score_breakdown 由来で正常動作 (代替経路あり) → 緊急度 ★★★→★★。この経緯を **クラウド誤り 10 (Project Knowledge 過信 + grep 不足)** として記録 (採番は docs 正本 1-7+9 の次 = 10、Web 側メモの 17 は不採用)。**CP-1 カズヤ判断**: 判断1 = en_count 修正 = 選択肢 1 (非 japan 合算)、判断2 = test data キー本バッチ同時更新 (不変原則 5 例外条件 4 点充足)、判断3 = クラウド初期想定の訂正受容。改修 2 ファイル (editorial_mission_filter.py + test、機能ロジック不変)、baseline **1417 passed 維持**、1 batch 試運転 = exit 0 / status=completed / 3 slots published / used_fallback=false / 404・Traceback 0 件。before_after_prescore.json で blindspot 中間段階の復活 (0→8〜12) を決定的に確認。不変原則 3 例外条件 **5 点全充足**。`src/triage/` の editorial_mission_filter.py 以外 / `src/analysis/` / `article_writer.py` / `script_writer.py` 既存ルート / `retry.py` / `configs/` / `scripts/` / `CLAUDE.md` 0 行変更。次バッチ最有力 = F-jp-coverage-cache-judgement-persist (F-13.B llm_judgement cache 永続化、同レビュー両者指摘))

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
(機能ロジック不変)。grep で当該ファイルが src/ で `"jp"`/`"en"` を使う唯一の
ファイルと確定。クラウド初期想定 (false positive) を grep で訂正 (実態 =
中間解像度喪失 = false negative 方向) → クラウド誤り 10 記録。

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

### ★ docs 概念整理と production-pipeline の乖離 (2026-05-11 観察、2026-05-25 F-f1-locale-key-fix で再確認で不変)

Phase A.5-3a-verify ゲート完了後の連続バッチで概念整理が docs 上で進んだが、
**production-pipeline 上では未配線**:
- `src/main.py` は legacy `verify()` (broad-only) のみ呼び出し
- `verify_two_stage()` 系統 1/2/3 機械判別: 本番未配線 (計測専用)
- `particular_angle_metadata` / `sontaku_signals`: src/ 配下 grep で 0 件
- `generate_script_with_analysis` 新ルート: 未起動 (analysis_result=null)

★★ **2026-05-25 (F-f1-locale-key-fix) 再確認**: 上記乖離は不変。本バッチは
F-1 prescore の locale key 参照のみ修正 (機能ロジック不変) で pipeline 配線
には非介入。本番配線判断バッチ群 3 件は引き続き FUTURE_WORK 緊急度 高に
並走待機。

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

- **main HEAD コミット**: `231decd` (Merge branch 'feature/F-gemini-model-migrate-emergency')。F-f1-locale-key-fix は feature ブランチ `feature/F-f1-locale-key-fix` で Task A-F 完了、本完了レポート提示後にカズヤ承認 → commit/merge 実行 (Task G)
- **直近 5 件のログ (main、Task G merge 前)**:
  ```
  231decd Merge branch 'feature/F-gemini-model-migrate-emergency'
  7624f93 feat: F-gemini-model-migrate-emergency 5/25 shutdown deadline 緊急対応
  2a73a0d Merge branch 'feature/F-gemini-model-audit'
  92146f6 feat: F-gemini-model-audit Gemini model strategy investigation (no code changes)
  4510180 Merge branch 'feature/F-trial-run-candidate-a-reverify'
  ```
- **baseline テスト数**: **1417 passed** (F-f1-locale-key-fix は `src/triage/editorial_mission_filter.py` の locale key 修正 + `tests/test_editorial_mission_filter.py:175-184` の data キー 2 行を CP-1 カズヤ承認のもと整合更新。機能ロジック不変のため改修後も 1417 維持。`src/` の他ファイル / `configs/` / `scripts/` / `CLAUDE.md` / `retry.py` 0 行変更)

## 2. 現在のフェーズ

- **Phase**: Phase A.5-3a-verify **完了** (2026-05-07、ゲート完了後 16 バッチ目が本バッチ)
- **進行中バッチ**: なし (F-f1-locale-key-fix 完了直後、Task F 完了レポート提示 → カズヤ承認待ち → commit/merge Task G)
- **次バッチ候補と推奨** (★ F-f1-locale-key-fix / 2026-05-25 更新):
  - **1st: F-jp-coverage-cache-judgement-persist** ★★高 最有力 (3 AI 三角測量レビュー / 2026-05-25 起案、ChatGPT + Gemini 両者独立指摘)。F-13.B `CoverageCheckResult` の `llm_judgement*` フィールドが 24h SQLite キャッシュ (`jp_coverage_cache`) に永続化されていない可能性 → キャッシュヒット時に B-3' の no_match 判定が復元されず Recall 劣化リスク。読み取り専用の影響測定 → 永続化実装 → golden 再測定。2-4h
  - **2nd: F-script-writer-target-enemy-fix** ★★★高 (Gemini 独自指摘)。`target_enemy` プロンプト/モデル定義の不整合修正。`src/shared/models.py` / `script_writer.py` / `video_payload_writer.py` / `configs/prompts/analysis/geo_lens/script_with_analysis.md` に跨る参照を grep 棚卸し → CP でスコープ確定 (クラウド誤り 9 留意)。調査 1-2h + 修正
  - **3rd: F-gemini-quality-tier-poc** ★★高 (Phase A.5-3b 第一作起案前)。Narrative primary = QUALITY Tier1 のモデル選定 PoC + Lightweight Tier1 切替判断 (migrate-emergency CP-1 保留分) + axis_5 採点 + publish_gate_flags 構造設計。3-5h
  - **4th: Phase A.5-3b 第一作起案** ★ (緊急度 高、確定モデルで実装。候補A cls-6889e9e1c7ac 手動 event 固定 + 実台本生成 + perspective_gap framing + axis_5 採点)
  - **5th: F-grounding-determinism-audit** ★ (緊急度 中、broad Grounding API の WL ドメイン返却率 run 間分散の集約戦略検討)
  - **6th: 第一作公開前の高リスク事実検証ワークフロー** ★ (緊急度 中、ADR-0003 由来、Phase A.5-3b と並走)
  - **7th: F-periodic-health-check** ★ (緊急度 中、Phase A.5-3d 着手時、cron 完全自動投稿の前提)
  - **8th: 本番配線判断バッチ群 (3 件、並走可)**: verify_two_stage 本番配線 / particular_angle_metadata + sontaku_signals 本番配線 / F-stream-2-filter-design 責務範囲再評価
  - **9th: config.py/factory.py default 不一致整合** ★低 / locale key 定数一元化 (選択肢 3) ★低 (runtime 影響なし、別 doc/refactor or quality-tier-poc 同時対応)
- **推奨フロー**:
  - commit/merge (本完了レポート提示 → カズヤ承認後)
    → **F-jp-coverage-cache-judgement-persist (F-13.B キャッシュ永続化、最優先)**
    → F-script-writer-target-enemy-fix (target_enemy 定義整合)
    → F-gemini-quality-tier-poc (Narrative primary 確定 + Lightweight Tier1 切替品質検証)
    → Phase A.5-3b 第一作起案 (確定モデルで実装、候補A perspective_gap framing + axis_5 採点)
    → 並走: F-grounding-determinism-audit + 高リスク事実検証ワークフロー + 本番配線判断バッチ群
- **★ Phase A.5-3b 第一作着手前の追加確認事項** (カズヤ指示、2026-05-25 更新):
  1. ~~F-trial-run-candidate-a-reverify~~ ✅ **完了 (2026-05-19、前提最終確定、候補A perspective_gap 維持)**
  2. ~~F-image-prompt-spec スコープ再定義~~ ✅ **完了 (2026-05-18、ADR 3 件 + schema 設計)**
  3. ~~F-gemini-model-migrate-emergency~~ ✅ **完了 (2026-05-19、5/25 shutdown リスク根絶)** + ★ **F-gemini-quality-tier-poc** (Narrative primary 確定 + Lightweight Tier1 切替判断、第一作起案前必須、3rd に後退 = cache/target_enemy 修正を先行)
  4. ElevenLabs 声選定 (着手前 30 分作業、既存登録済み、カズヤ手作業)
  5. Remotion セットアップ (第一作で Claude Code に書かせる、Node 環境カズヤ手動準備、ADR-0002 D-minimal)

### Phase A.5-3a-verify ロードマップ (★ F-f1-locale-key-fix / 2026-05-25 更新版)

**ゲート完了**: 1-A〜1-D''' 全段階完了で Phase A.5-3a-verify ゲート完了 (2026-05-07)。
本バッチはゲート完了後の **16 つ目のバッチ**。

| 段階 | バッチ | 状態 | 概要 |
|---|---|---|---|
| 1-A〜1-I | (F-verify-jp-coverage-golden 〜 F-trial-run-post-llm-extraction) | ✅ 完了 | ゲート完了 + 特定角度正典化 + LLM judgement bypass 根本治療 |
| 1-J〜1-K | F-trial-run-candidate-a-reverify / F-image-prompt-spec | ✅ 完了 (2026-05-18〜19) | 候補A 前提最終確定 + ADR 3 件 + schema 設計 |
| 1-L | F-gemini-model-audit | ✅ 完了 (2026-05-19) | Gemini モデル戦略 影響調査 (改修なし)。5/25 shutdown 対象 2 箇所特定 + 404 即 raise 重大発見 |
| 1-M | F-gemini-model-migrate-emergency | ✅ 完了 (2026-05-19) | 両系統 Tier3 + default + `.env` を gemini-3.1-flash-lite (GA) 一括置換、404 即 raise リスク根絶 (retry.py 0 変更)。baseline 1417 維持 |
| **1-N** | **F-f1-locale-key-fix** | ✅ **完了 (2026-05-25)** | **ゲート完了後 16 つ目**。3 AI 三角測量由来で F-1 EditorialMissionFilter の locale key bug (`get("jp"/"en")` → `"japan"` + 非 japan 合算) を根本治療、機能ロジック不変。CP-1 = 選択肢 1 + test 同時更新 + クラウド初期想定の訂正 (クラウド誤り 10)。baseline 1417 維持、試運転 status=completed。blindspot 中間段階 (8/10/12) を dead code から復活 |
| 1-O | F-jp-coverage-cache-judgement-persist | ★★高 (次バッチ最有力) | F-13.B llm_judgement の 24h cache 永続化 (ChatGPT + Gemini 両者指摘) |
| 1-P | F-script-writer-target-enemy-fix | ★★★高 | target_enemy プロンプト/モデル定義の不整合修正 (Gemini 独自指摘) |
| 1-Q | F-gemini-quality-tier-poc | ★★高 (Phase A.5-3b 前) | Narrative primary モデル選定 PoC + Lightweight Tier1 切替判断 + axis_5 + publish_gate_flags 設計 |
| 1-R | Phase A.5-3b 第一作起案 | ★ 緊急度 高 (確定モデルで実装) | 候補A 手動固定 + perspective_gap framing + axis_5 採点 |
| 1-S | F-grounding-determinism-audit / 本番配線判断バッチ群 | ★ 並走候補 | broad Grounding 分散集約 / verify_two_stage 等の本番配線 |

### Phase A.5-3d 投稿対象の補足

Phase A.5-3d で本番リリースする対象は **geo_lens (政治・経済) のみ**。
投稿先は TikTok と YouTube Shorts の両方同時、完全自動投稿 (cron 6 時間おき、
人手介入ゼロ、投稿前ゲートで品質保証)。★ 投稿前ゲートのチェックリスト 6 項目は
ADR-0003 で正典化。★ 完全自動投稿の前提として F-periodic-health-check
(緊急度 中、Phase A.5-3d 着手時) が必要。

## 3. 直近の試運転結果サマリー

| 試運転 | バッチ | 動画化率 | 主要観察 |
|---|---|---|---|
| **2026-05-25** | **F-f1-locale-key-fix** | **1/3 動画化 + 3 articles (status=completed)** | ★ locale key 修正後の 1 batch 試運転 (batch 20260525_085458)。exit 0 / status=completed / 3 slots published (Slot-1 video cls-b0a1e9bebbd5 + Slot-2/3 article)。used_fallback=false、retries=0、404/Traceback/ERROR 0 件。F-13.B は Slot-2/3 で llm_judgement=no_match 確定 (blind_spot_global)。防衛機構 5 層異常なし、動画化候補消失なし。run_summary prescore_stats min=0.0/max=65.2/mean=21.62 (入力 369 cands)。blindspot 中間段階の復活は before_after_prescore.json で決定的に確認 (run_summary 比較は入力差で confounded)。 |
| 2026-05-19 | F-gemini-model-migrate-emergency | 1/3 動画化 + 3 articles (status=completed) | ★ 5/25 shutdown 緊急対応の 1 batch 試運転 (batch 20260519_104204)。exit 0 / status=completed / 3 slots published。model_roles 全 GA 解決。used_fallback=false、404・shutdown モデル参照 0 件。Tier3 fallback は 503 連鎖なしで未発火 (想定どおり)。 |
| 2026-05-18 | F-trial-run-candidate-a-reverify | 1/3 動画化 (Slot-1 cls-f47e9ffde77d, ★ fallback script) + 3 articles | ★ 候補A cls-6889e9e1c7ac 不在。has_jp True 比率 3 連続単調減少 (3T/0F → 1T/2F → 0T/3F)。防衛機構 5 層全機能。 |
| 2026-05-16 | F-trial-run-post-llm-extraction | 1/3 動画化 (Slot-1 cls-e2429c77f48e) + 3 articles | ★★★ B-3' が production verify() に配線・本番で安全装置初発火。第一作題材確定 = 候補A perspective_gap。 |
| 2026-05-14 | F-wl-hit-quality-audit | (試運転なし、WebSearch 検証) | ★★★ LLM judgement bypass 問題が決定的判明。Slot-1 cls-6889e9e1c7ac = perspective_gap 確定。 |

## 4. Hydrangea コンセプト防衛機構の現状 (5 層)

> ★ F-f1-locale-key-fix (2026-05-25) の 1 batch 試運転 (batch_id 20260525_085458)
> で防衛機構 **異常挙動なし** を再確認 (status=completed、used_fallback=false、
> 404/Traceback 0 件)。F-1 の locale key 修正は blindspot prescore の参照キー
> 正本化のみで判定ロジック (if/elif・係数・cap) は完全不変。

| 層 | バッチ | 場所 | 役割 | 状態 |
|---|---|---|---|---|
| F-1 | F-1 / F-1.5 / **F-f1-locale-key-fix** | EditorialMissionFilter | 編集ミッション適合度で score 算出 (>= 45.0 で通過) | ✅ 稼働中。★ **2026-05-25 で blindspot prescore の locale key bug を根本治療** (`get("jp"/"en")` → `"japan"` + 非 japan 合算)。中間 elif (8/10/12) が dead code から復活、binary 15.0 経路 (has_*_view 由来) は従来から正常 = 不変。直近 run 369 cands → 20 通過 |
| F-2 | F-2 / F-5 | FlagshipGate / EliteJudge | 海外発の重要ニュースを優先 | ✅ 稼働中 |
| F-13.B | … / F-trial-run-candidate-a-reverify | JpCoverageVerifier (WL 30 ドメイン階層判定 + LLM judgement 抽出 B-3') | JP 報道カバレッジを WL + LLM judgement で検証 | ✅ 稼働中 (直近 run Slot-2/3 で llm_judgement=no_match 確定)。★ llm_judgement の 24h cache 永続化が未確認 = 次バッチ F-jp-coverage-cache-judgement-persist で対応 (ChatGPT + Gemini 指摘) |
| F-5 | F-5 | FlagshipGate 下流救済 | 上流ガードを通過した候補の最終整合 | ✅ 稼働中 (直近 run 0 件発火 = 入力依存、異常なし) |
| F-13 (隠れ層) | F-13 / F-doc-cleanup | script_writer.py quality_floor_miss bypass | analysis_result 等が成立すれば appraisal の [抑制] を上書き | ✅ 稼働中 (直近 run 0 件発火 = 設計通り) |

## 5. 触ってよい / 触ってはいけない領域マップ

### 触ってよい領域
- `configs/prompts/` 配下全般 (主戦場: `configs/prompts/analysis/geo_lens/`)
- `docs/` 配下全般 (★ `docs/ADR/` 配下に ADR 新規作成可)
- `tests/` 配下に新規テストファイル追加 (既存ファイルは原則変更しない、
  ただし API contract 整合化に伴うフィクスチャ更新 + 既存ファイルへの新規
  テストクラス追加 + 仕様/データ構造整合に伴う既存期待値修正 (構造変更なし) は許容)
- `scripts/` 配下に新規スクリプト追加
- `src/triage/` に新規ファイル追加
- `src/generation/script_writer.py` の **新ルート**
  (`generate_script_with_analysis` / `ScriptWithAnalysisDraft` 等)
- `src/generation/script_writer.py` の `_CHAR_BOUNDS` 等の定数 (最小改変なら許容)
- `src/generation/video_payload_writer.py` (不変原則 1-4 対象外、★ Phase A.5-3b 第一作起案で images[]/events[] 追加の最小改変対象)
- `src/shared/models.py` (★ Phase A.5-3b で VideoImage/VideoEvent Optional 追加予定、後方互換必須)
- `src/main.py` (不変原則対象外、★ verify_two_stage 本番配線判断バッチで改修対象)
- `src/llm/factory.py` / `src/shared/config.py` の Gemini モデル ID default (★ F-gemini-model-migrate-emergency / 2026-05-19 で Tier3 GA 置換済、不変原則対象外)
- `.env` / `.env.example` (リポジトリルート直下、★ F-gemini-model-migrate-emergency / 2026-05-19 で Tier3 GA 置換済)

### 触ってはいけない領域
- `src/generation/article_writer.py` (不変原則 1)
- `src/generation/script_writer.py` の **既存ルート**
  (`write_script` / `_PROMPT_TEMPLATE` / `_build_script_from_llm`) (不変原則 2)
- `src/triage/` の既存ファイル (不変原則 3、★ 過去に例外条件適用済 = F-f1-locale-key-fix / 2026-05-25 で `editorial_mission_filter.py` の locale key bug 修正に例外条件 5 点全充足で適用)
- `src/analysis/` 配下全般 (不変原則 4)
- 既存テスト (不変原則 5、baseline **1417 passed** 維持 — ただし
  フィクスチャの API contract 整合化 + 既存テストファイルへの新規テスト
  クラス追加 + 仕様/データ構造整合に伴う既存テスト期待値修正 (構造変更なし) は許容)

## 6. 不変原則 5 つ (リマインダ、正本: BATCH_PROTOCOL.md)

1. **`src/generation/article_writer.py` 一切変更不可**
2. **`src/generation/script_writer.py` の既存ルート (`write_script` /
   `_PROMPT_TEMPLATE` / `_build_script_from_llm`) は変更不可**
3. **`src/triage/` の既存ファイル変更不可**。新規追加は OK。
   **例外条件** (5 点全充足で適用): 実装バグ修正 + 設計変更ではない +
   既存メソッド contract 完全維持 + baseline 維持 + カズヤ承認。
   ★ F-f1-locale-key-fix (2026-05-25) で `editorial_mission_filter.py` の
   locale key bug に適用 (5 点全充足)。
4. **`src/analysis/` 変更不可**
5. **既存テスト破壊しない** (baseline **1417 passed**)

## 7. カズヤの直近フィードバック要点

- **「LLM の知性に委ねる前に構造データの正しさを担保する」** (★ F-f1-locale-key-fix
  2026-05-25) — locale key の正本化は「分析フェーズ LLM への期待」の前提となる
  構造データの整合性確保。選択肢 1 (非 japan 合算) は「対症療法じゃなく根本治療」
  かつ多様な locale の正しい意味解釈
- **「整合の説明であって検証ではない」/ Project Knowledge を鵜呑みにしない**
  (★ F-f1-locale-key-fix CP-1) — クラウド初期想定 (false positive) を grep +
  コード精読で訂正 (実態 = 中間解像度喪失 = false negative 方向)。Claude Web 側の
  個人作業ログを docs 正本と取り違える誤りを クラウド誤り 10 として記録、docs
  連番 (1-7+9 の次 = 10) を正本として再確立
- **「将来に負債を残さない」** (★ F-f1-locale-key-fix CP-1 判断2) — dead code
  テストデータ (`"en"`/`"jp"` キー) を残さず本バッチで同時更新 (不変原則 5
  例外条件 4 点充足)
- **「動くものを壊さない」+「あるべき姿で進める」** (F-gemini-model-migrate-emergency)
  — 機能ロジック不変を保ちつつ構造データの正しさを是正
- **「対症療法じゃなくて根本治療」** — locale key は `"global"` 単独 (対症療法、
  middle_east 取りこぼし) ではなく非 japan 合算 (根本治療)
- **「機械判定は事実の代替ではない」** — 候補A perspective_gap 確定は機械不在で覆らない
- **「中間が良い」/「考え方で制御」/「LLM の知性に委ねる」** — no_match のみ尊重 (B-3')
- **「言い回しを個別ルールで指定するのは避けたい」** (クラウド誤り 9) — target_enemy
  修正でもプロンプト各論化に留意
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
- ★ **F-f1-locale-key-fix REPORT + 調査/試運転出力** → `docs/runs/F-f1-locale-key-fix/REPORT.md` + grep_results.json + locale_key_inventory.json + impact_analysis.json + diff_summary.md + trial_run_summary.json + before_after_prescore.json + environment_snapshot.json
- F-gemini-model-migrate-emergency REPORT → `docs/runs/F-gemini-model-migrate-emergency/REPORT.md`
- ★ **Phase A.5-3b 画像戦略 / Remotion / モラル ADR** → `docs/ADR/0001-image-strategy.md` + `0002-remotion-mvp-scope.md` + `0003-content-moral-guidelines.md`
- F-image-prompt-spec REPORT + 設計 → `docs/runs/F-image-prompt-spec/REPORT.md` + `schema_extension_design.md`

---

*このドキュメントは F-state-protocol (2026-05-01) で導入。Claude Code が
バッチ完了時に全置換更新する運用 (BATCH_PROTOCOL.md Task 5)。
F-f1-locale-key-fix (2026-05-25) は **ゲート完了後の 16 つ目のバッチ (1-N)**。
3 AI 三角測量 (ChatGPT + Gemini) のレビューで両者独立に指摘された
`src/triage/editorial_mission_filter.py` の locale key bug
(`_editorial_mission_prescore` の `sources_by_locale.get("jp"/"en")`) を、実データ
構造の正しいキー (`"japan"` + 非 japan locale 合算 = `main.py` overseas_count
パターン) に修正。機能ロジック (blindspot if/elif・係数・cap) 不変、locale key
参照の正本化のみ。grep で当該ファイルが src/ で `"jp"`/`"en"` を使う唯一の
ファイルと確定。★ クラウド初期想定 (「不当に高い誤爆 = false positive」) を
grep + コード精読で訂正 = 実態は「中間解像度 8〜12 点の永久喪失 (false
negative 方向)」、`jp_count`/`en_count` 両方常に 0 で中間 elif が dead code、
第1分岐 15.0 は score_breakdown 由来で正常動作 (代替経路あり) → 緊急度
★★★→★★。この経緯を クラウド誤り 10 (Project Knowledge 過信 + grep 不足)
として記録 (採番は docs 正本 1-7+9 の次 = 10、Web 側メモの 17 は不採用)。
CP-1 カズヤ判断: 判断1 = en_count 修正 = 選択肢 1 (非 japan 合算)、判断2 =
test data キー本バッチ同時更新 (不変原則 5 例外条件 4 点充足)、判断3 =
クラウド初期想定の訂正受容。改修 2 ファイル (機能ロジック不変)、baseline
1417 passed 維持、1 batch 試運転 status=completed / used_fallback=false /
404・Traceback 0 件。before_after_prescore.json で blindspot 中間段階 (0→8〜12)
の復活を決定的に確認。不変原則 3 例外条件 5 点全充足。`src/triage/` の
editorial_mission_filter.py 以外 / `src/analysis/` / `article_writer.py` /
`script_writer.py` 既存ルート / `retry.py` / `configs/` / `scripts/` /
`CLAUDE.md` 0 行変更、`tests/` 2 行は CP-1 明示承認済、不変原則 1-5 全遵守。
次バッチ候補 = F-jp-coverage-cache-judgement-persist (★ 最有力、F-13.B
llm_judgement cache 永続化、ChatGPT + Gemini 両者指摘)。
過去の経緯は DECISION_LOG.md / FUTURE_WORK.md / DISCUSSION_NOTES.md を参照。*
