# Hydrangea — Current State (CURRENT_STATE.md)

最終更新: 2026-05-19 (★ F-gemini-model-audit 完了、Phase A.5-3a-verify ゲート完了後の **14 つ目のバッチ**。Gemini モデル戦略再検討の **影響調査専用バッチ (改修一切なし)**。5/25 `gemini-3.1-flash-lite-preview` shutdown + 2026-05 Gemini API モデル群更新の影響調査。主要発見: shutdown 対象の実稼働 functional 使用 = 2 箇所 (`.env:14` QUALITY Tier3 + `.env:21` LIGHTWEIGHT Tier3、両系統とも fallback 位置)。コード default 3 箇所 + テンプレ `.env.example` + doc-drift コメント群が付随。★★★ **重大発見**: shutdown 後の 404 NOT_FOUND は `retry.is_retryable()=False` のため `factory.generate()` が次 Tier (Tier4 GA 安全網) にフォールバックせず即 raise → 503 多発時 (F-trial-run-candidate-a-reverify で実確認) に Tier1→2 連鎖失敗で Tier3 到達 → 全生成失敗の致命傷リスク。Interactions API **未使用** (無関係)。F-13.B Grounding は `gemini-2.5-flash` で shutdown 非該当。CP-1 カズヤ判断 = **選択肢1 (両系統 Tier3 + config default + `.env.example` を `gemini-3.1-flash-lite` (GA) に一括置換)**。次バッチ `F-gemini-model-migrate-emergency` (★★★ 緊急度 高、5/25 deadline) でショットダウンモデルを Tier から除去 = 404 即 raise リスク根絶。`F-gemini-quality-tier-poc` 新規 (Narrative primary 選定 PoC)。`F-gemini-503-stability-audit` 撤回 (モデル切替で根本治療)、`F-periodic-health-check` 緊急度 高 → 中降格 (Phase A.5-3d 着手時)。`src/ tests/ configs/ scripts/ CLAUDE.md` 0 行変更、`docs/` のみ更新、baseline **1417 passed** 維持、不変原則 1-5 全遵守)

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

★★★ 2026-05-14 (F-wl-hit-quality-audit) で **LLM judgement bypass の設計
判断レベルの欠陥** を決定的に発見。Slot-1 cls-6889e9e1c7ac の系統判定 =
**perspective_gap 確定** (afpbb で 9,600 数字 + 虐待を継続報道済み、WebSearch
独立検証)。

★★★ 2026-05-16 (F-jp-coverage-llm-judgement-extraction) で **LLM judgement
bypass 問題を Option (i) で根本治療完了**。`_parse_llm_judgement` 新規 +
B-3' 表。WL マッチ条件下評価で Recall 1.0000 / Precision 0.8889 / FN=0。
LLM の **明示的否定 (no_match)** のみ尊重し **沈黙 (uncertain)** を否定と
読み替えない。

★★★ 2026-05-16 (F-trial-run-post-llm-extraction) で **B-3' 改修後の本番
挙動を実証**。production verify() (broad-only) に B-3' が配線され、本番で
安全装置が初発火。has_jp_coverage 分布が前回 3/3 True → 1 True / 2 False に
反転。Phase A.5-3b 第一作題材 = 候補A cls-6889e9e1c7ac を perspective_gap
framing で確定。

★ 2026-05-18 (F-image-prompt-spec) で **Phase A.5-3b 第一作の画像戦略 +
Remotion 実装範囲 + コンテンツモラルを ADR 3 件 + video_payload schema 拡張
設計として正典化** (設計のみ、実装は Phase A.5-3b)。

★★★ 2026-05-19 (F-trial-run-candidate-a-reverify) で **B-3' 改修の構造的
効果を 3 連続試運転で確定**。has_jp_coverage True 比率が 3 連続で単調減少
(3T/0F → 1T/2F → 0T/3F)。候補A は perspective_gap framing で維持 (機械判定
≠ 事実)。Phase A.5-3b 第一作着手 OK (前提最終確定)。

★★★ 2026-05-19 (F-gemini-model-audit) で **2026-05 Gemini モデル戦略を
影響調査** (改修なし)。5/25 shutdown 対象 `gemini-3.1-flash-lite-preview`
の実稼働 functional 使用 = 2 箇所 (QUALITY/LIGHTWEIGHT 両 Tier3 fallback)。
重大発見 = shutdown 後 404 が retry 非対象で次 Tier フォールバックせず即
raise (503 多発時の致命傷)。CP-1 カズヤ判断 = 両系統 Tier3 一括 GA 置換
(選択肢1)。F-13.B Grounding は 2.5 系維持。

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
(2026-05-16 確定、2026-05-19 F-trial-run-candidate-a-reverify で **最終確定**:
機械判定 ≠ 事実のため候補A 機械不在は perspective_gap 確定を覆さない)。

### 系統 3 (framing_inversion): 報道差の背景解説 — 特定角度も報道済み + 解釈差 + 忖度シグナル

広範事件 + 特定角度も日本主要メディアで報道済み + 評価フレーム対立 +
sontaku_signals.level=high/medium の 3 条件。25 件最終分類で **0 件** ★ 想定外
(根本治療は Phase A.5-3b 第二作のサンプル拡充)。

### ★ docs 概念整理と production-pipeline の乖離 (2026-05-11 観察、2026-05-19 再評価で不変確認)

Phase A.5-3a-verify ゲート完了後の連続バッチで概念整理が docs 上で進んだが、
**production-pipeline 上では未配線**:
- `src/main.py` は legacy `verify()` (broad-only) のみ呼び出し
- `verify_two_stage()` 系統 1/2/3 機械判別: 本番未配線 (計測専用)
- `particular_angle_metadata` / `sontaku_signals`: src/ 配下 grep で 0 件
- `generate_script_with_analysis` 新ルート: 未起動 (analysis_result=null)

★★★ **2026-05-19 (F-gemini-model-audit) 再評価**: 上記乖離は不変。本バッチは
調査専用でコード非改修。なお `analysis` role (QUALITY 系統) は
`ANALYSIS_LAYER_ENABLED=false` で本番未起動 = Gemini モデル移行の analysis
リスクは実害なし (将来配線時に F-gemini-quality-tier-poc で再評価)。本番配線
判断バッチ群 3 件は引き続き FUTURE_WORK 緊急度 高に並走待機。

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

- **main HEAD コミット**: `4510180` (Merge branch 'feature/F-trial-run-candidate-a-reverify')。F-gemini-model-audit は feature ブランチ `feature/F-gemini-model-audit` で Task A-F 完了、本完了レポート提示後にカズヤ承認 → commit/merge 実行 (Task G)
- **直近 5 件のログ (main)**:
  ```
  4510180 Merge branch 'feature/F-trial-run-candidate-a-reverify'
  bc0f531 feat: F-trial-run-candidate-a-reverify candidate-A B-3' post-fix reverification
  3c964c7 Merge branch 'feature/F-image-prompt-spec'
  5331998 feat: F-image-prompt-spec ADR 3 documents + video_payload schema extension design
  8dc62da Merge branch 'feature/F-trial-run-post-llm-extraction'
  ```
- **baseline テスト数**: **1417 passed** (F-gemini-model-audit は調査専用で `src/ tests/ configs/ scripts/ CLAUDE.md` 0 行変更、baseline 完全不変)

## 2. 現在のフェーズ

- **Phase**: Phase A.5-3a-verify **完了** (2026-05-07、ゲート完了後 14 バッチ目が本バッチ)
- **進行中バッチ**: なし (F-gemini-model-audit 完了直後、Task F 完了レポート提示 → カズヤ承認待ち → commit/merge Task G)
- **次バッチ候補と推奨** (★ F-gemini-model-audit / 2026-05-19 更新):
  - **1st: F-gemini-model-migrate-emergency** ★★★ 最有力 (緊急度 高、**5/25 deadline 必達**)。両系統 Tier3 (QUALITY + LIGHTWEIGHT) + `factory.py`/`config.py` default + `.env.example` を `gemini-3.1-flash-lite` (GA) に一括置換。shutdown モデルを Tier から除去 = 404 即 raise リスク根絶 (retry.py 不変、最小対処)。doc-drift コメント整理。全 LOW リスク、想定 2-3h。AI Studio quota + preview/GA 状態のカズヤ手動確認 (REPORT.md §6-7) が実装前提
  - **2nd: F-gemini-quality-tier-poc** ★ (緊急度 高、Phase A.5-3b 第一作起案前)。Narrative primary = QUALITY Tier1 のモデル選定 PoC (`gemini-3-flash-preview` / `gemini-3.1-pro-preview` / `gemini-2.5-flash`) + axis_5 採点 + publish_gate_flags 構造設計。Pro は Editorial Guardian 限定方針を検証、3-5h
  - **3rd: Phase A.5-3b 第一作起案** ★★★ (緊急度 高、ADR-0001/0002/0003 + schema 前提、前提最終確定済。候補A cls-6889e9e1c7ac 手動 event 固定 + 実台本生成 + perspective_gap framing + axis_5 採点。確定モデル (F-gemini-quality-tier-poc 後) で実装)
  - **4th: F-grounding-determinism-audit** ★ (緊急度 中、broad Grounding API の WL ドメイン返却率 run 間分散の集約戦略検討)
  - **5th: 第一作公開前の高リスク事実検証ワークフロー** ★ (緊急度 中、ADR-0003 由来、Phase A.5-3b と並走)
  - **6th: F-periodic-health-check** ★ (緊急度 中、Phase A.5-3d 着手時、cron 完全自動投稿の前提)
  - **7th: 本番配線判断バッチ群 (3 件、並走可)**: verify_two_stage 本番配線 / particular_angle_metadata + sontaku_signals 本番配線 / F-stream-2-filter-design 責務範囲再評価
- **推奨フロー**:
  - commit/merge (本完了レポート提示 → カズヤ承認後)
    → **F-gemini-model-migrate-emergency (5/25 deadline 必達、最優先)**
    → F-gemini-quality-tier-poc (Narrative primary 確定)
    → Phase A.5-3b 第一作起案 (確定モデルで実装、候補A perspective_gap framing + axis_5 採点)
    → 並走: F-grounding-determinism-audit + 高リスク事実検証ワークフロー + 本番配線判断バッチ群
    → Phase A.5-3b 第二作のサンプル拡充 → 3c 自動化 → Phase A.5-3d (F-periodic-health-check 並走)
- **★ Phase A.5-3b 第一作着手前の追加確認事項** (カズヤ指示、2026-05-19 更新):
  1. ~~F-trial-run-candidate-a-reverify~~ ✅ **完了 (2026-05-19、前提最終確定、候補A perspective_gap 維持)**
  2. ~~F-image-prompt-spec スコープ再定義~~ ✅ **完了 (2026-05-18、ADR 3 件 + schema 設計)**
  3. ★ **F-gemini-model-migrate-emergency** (5/25 deadline、第一作実台本生成の前提安定化、最優先) + **F-gemini-quality-tier-poc** (Narrative primary 確定、第一作起案前必須)
  4. ElevenLabs 声選定 (着手前 30 分作業、既存登録済み、カズヤ手作業)
  5. Remotion セットアップ (第一作で Claude Code に書かせる、Node 環境カズヤ手動準備、ADR-0002 D-minimal)
  6. ★ AI Studio active quota + preview/GA 状態のカズヤ手動確認 (REPORT.md §6-7、migrate 実装前提)

### Phase A.5-3a-verify ロードマップ (★ F-gemini-model-audit / 2026-05-19 更新版)

**ゲート完了**: 1-A〜1-D''' 全段階完了で Phase A.5-3a-verify ゲート完了 (2026-05-07)。
本バッチはゲート完了後の **14 つ目のバッチ**。

| 段階 | バッチ | 状態 | 概要 |
|---|---|---|---|
| 1-A〜1-D''' | (F-verify-jp-coverage-golden 〜 F-trial-run-post-fix) | ✅ 完了 | ゲート完了 (2026-05-07) |
| 1-E〜1-F''' | (F-particular-angle-design 〜 F-task-e-finalize) | ✅ 完了 | 特定角度概念正典化 + 4 分類化 + sontaku_signals 独立化 |
| 1-G〜1-G''' | (F-jp-coverage-tune 〜 F-wl-hit-quality-audit) | ✅ 完了 | WL 階層判定化 + LLM judgement bypass 決定的発見 |
| 1-H | F-jp-coverage-llm-judgement-extraction | ✅ 完了 (2026-05-16) | LLM judgement bypass を Option (i) B-3' で根本治療、Recall 1.0000 / FN=0 |
| 1-I | F-trial-run-post-llm-extraction | ✅ 完了 (2026-05-16) | B-3' 本番試運転で bypass 構造解消を本番実証、第一作題材確定 |
| 1-K | F-image-prompt-spec | ✅ 完了 (2026-05-18) | 3 AI 三角測量 D-minimal 仕様を ADR 3 件 + schema 拡張設計として正典化 (設計のみ) |
| 1-J | F-trial-run-candidate-a-reverify | ✅ 完了 (2026-05-19) | 候補A B-3' 改修後本番再確認。B-3' 構造的効果を 3 連続試運転で確定。候補A perspective_gap 維持 |
| **1-L** | **F-gemini-model-audit** | ✅ **完了 (2026-05-19)** | **ゲート完了後 14 つ目**。Gemini モデル戦略再検討 影響調査専用 (改修なし)。5/25 shutdown 対象 2 箇所特定 + 404 即 raise 重大発見。CP-1 = 選択肢1 (両系統 Tier3 一括 GA 置換)。`src/ tests/ configs/ scripts/ CLAUDE.md` 0 変更、baseline 1417 維持 |
| 1-M | F-gemini-model-migrate-emergency | ★★★ 緊急度 高 (5/25 deadline 必達) | 両系統 Tier3 + config default + .env.example を gemini-3.1-flash-lite (GA) 一括置換、shutdown モデル Tier 除去で 404 即 raise リスク根絶 |
| 1-N | F-gemini-quality-tier-poc | ★ 緊急度 高 (Phase A.5-3b 前) | Narrative primary (QUALITY Tier1) モデル選定 PoC + axis_5 + publish_gate_flags 設計 |
| 1-O | Phase A.5-3b 第一作起案 | ★ 緊急度 高 (確定モデルで実装) | 候補A 手動固定 + perspective_gap framing + axis_5 採点 |
| 1-P | F-grounding-determinism-audit | ★ 緊急度 中 | broad Grounding API の WL ドメイン返却率 run 間分散の集約戦略検討 |
| 1-Q | 本番配線判断バッチ群 (3 件) | ★ 並走候補 | verify_two_stage / particular_angle_metadata+sontaku_signals / F-stream-2-filter-design |

### Phase A.5-3d 投稿対象の補足

Phase A.5-3d で本番リリースする対象は **geo_lens (政治・経済) のみ**。
投稿先は TikTok と YouTube Shorts の両方同時、完全自動投稿 (cron 6 時間おき、
人手介入ゼロ、投稿前ゲートで品質保証)。★ 投稿前ゲートのチェックリスト 6 項目は
ADR-0003 で正典化。★ 完全自動投稿の前提として F-periodic-health-check
(緊急度 中、Phase A.5-3d 着手時) が必要。

## 3. 直近の試運転結果サマリー

| 試運転 | バッチ | 動画化率 | 主要観察 |
|---|---|---|---|
| **2026-05-19** | **F-gemini-model-audit** | **試運転なし (調査バッチ)** | ★ Gemini モデル戦略影響調査 (改修なし)。5/25 shutdown 対象の実稼働 functional 使用 = 2 箇所 (QUALITY/LIGHTWEIGHT 両 Tier3 fallback)。重大発見 = shutdown 後 404 が retry 非対象で次 Tier フォールバックせず即 raise。Interactions API 未使用。CP-1 = 選択肢1 (両系統 Tier3 一括 GA 置換)。 |
| 2026-05-18 | F-trial-run-candidate-a-reverify | 1/3 動画化 (Slot-1 cls-f47e9ffde77d, ★ fallback script) + 3 articles | ★ 候補A cls-6889e9e1c7ac 不在 (完全新規 RSS batch)。has_jp True 比率 3 連続単調減少 (5/11 3T/0F → 5/16 1T/2F → 5/18 0T/3F)。Slot-1 台本 fallback (Gemini 503 多発)。防衛機構 5 層全機能。 |
| 2026-05-18 | F-image-prompt-spec | 試運転なし (docs バッチ) | 3 AI 三角測量 D-minimal 仕様を ADR 3 件 + schema 設計に正典化。 |
| 2026-05-16 | F-trial-run-post-llm-extraction | 1/3 動画化 (Slot-1 cls-e2429c77f48e) + 3 articles | ★★★ B-3' が production verify() に配線・本番で安全装置初発火。has_jp 分布 3/3 True → 1 True / 2 False に反転。第一作題材確定 = 候補A perspective_gap。 |
| 2026-05-14 | F-wl-hit-quality-audit | (試運転なし、WebSearch 検証) | ★★★ LLM judgement bypass 問題が決定的判明。Slot-1 cls-6889e9e1c7ac = perspective_gap 確定。 |

## 4. Hydrangea コンセプト防衛機構の現状 (5 層)

> ★ F-gemini-model-audit (2026-05-19) は調査専用バッチで試運転なし。
> 防衛機構の挙動は前バッチ F-trial-run-candidate-a-reverify (2026-05-19)
> 試運転 (batch_id 20260518_111201) の再確認結果が直近の正。**異常挙動なし**。
> ★ Gemini モデル移行 (F-gemini-model-migrate-emergency) は防衛機構の
> モデル ID のみ env/config で置換可能、防衛ロジック自体は不変。

| 層 | バッチ | 場所 | 役割 | 状態 |
|---|---|---|---|---|
| F-1 | F-1 / F-1.5 | EditorialMissionFilter | 編集ミッション適合度で score 算出 (>= 45.0 で通過) | ✅ 稼働中 (直近 run 351→19 通過) |
| F-2 | F-2 / F-5 | FlagshipGate / EliteJudge | 海外発の重要ニュースを優先 | ✅ 稼働中 (直近 run Blocked 0) |
| F-13.B | … / F-trial-run-candidate-a-reverify | JpCoverageVerifier (WL 30 ドメイン階層判定 + LLM judgement 抽出 B-3') | JP 報道カバレッジを WL + LLM judgement で検証 | ✅ **B-3' 改修の構造的効果を 3 連続試運転で確定** (has_jp True 比率 3T/0F → 1T/2F → 0T/3F)。verify_two_stage 系統機械判別は依然本番未配線 (B-3' とは直交) |
| F-5 | F-5 | FlagshipGate 下流救済 | 上流ガードを通過した候補の最終整合 | ✅ 稼働中 (直近 run 0 件発火 = 入力依存、異常なし) |
| F-13 (隠れ層) | F-13 / F-doc-cleanup | script_writer.py quality_floor_miss bypass | analysis_result 等が成立すれば appraisal の [抑制] を上書き | ✅ 稼働中 (直近 run 0 件発火 = 設計通り) |

## 5. 触ってよい / 触ってはいけない領域マップ

### 触ってよい領域
- `configs/prompts/` 配下全般 (主戦場: `configs/prompts/analysis/geo_lens/`)
- `docs/` 配下全般 (★ `docs/ADR/` 配下に ADR 新規作成可)
- `tests/` 配下に新規テストファイル追加 (既存ファイルは原則変更しない、
  ただし API contract 整合化に伴うフィクスチャ更新 + 既存ファイルへの新規
  テストクラス追加は許容)
- `scripts/` 配下に新規スクリプト追加
- `src/triage/` に新規ファイル追加
- `src/generation/script_writer.py` の **新ルート**
  (`generate_script_with_analysis` / `ScriptWithAnalysisDraft` 等)
- `src/generation/script_writer.py` の `_CHAR_BOUNDS` 等の定数 (最小改変なら許容)
- `src/generation/video_payload_writer.py` (不変原則 1-4 対象外、★ Phase A.5-3b 第一作起案で images[]/events[] 追加の最小改変対象)
- `src/shared/models.py` (★ Phase A.5-3b で VideoImage/VideoEvent Optional 追加予定、後方互換必須)
- `src/main.py` (不変原則対象外、★ verify_two_stage 本番配線判断バッチで改修対象)
- `src/llm/factory.py` / `src/llm/retry.py` / `src/shared/config.py` の Gemini モデル ID (★ F-gemini-model-migrate-emergency で改修対象、不変原則対象外。ただし retry.py のリトライ判定ロジック自体は不変、shutdown モデルを Tier から除去する最小対処)
- `.env` / `.env.example` (リポジトリルート直下、★ F-gemini-model-migrate-emergency で Tier3 GA 置換対象)

### 触ってはいけない領域
- `src/generation/article_writer.py` (不変原則 1)
- `src/generation/script_writer.py` の **既存ルート**
  (`write_script` / `_PROMPT_TEMPLATE` / `_build_script_from_llm`) (不変原則 2)
- `src/triage/` の既存ファイル (不変原則 3、過去に例外条件適用済)
- `src/analysis/` 配下全般 (不変原則 4)
- 既存テスト (不変原則 5、baseline **1417 passed** 維持 — ただし
  フィクスチャの API contract 整合化 + 既存テストファイルへの新規テスト
  クラス追加 + 仕様変更に伴う既存テスト期待値修正 (構造変更なし) は許容)

## 6. 不変原則 5 つ (リマインダ、正本: BATCH_PROTOCOL.md)

1. **`src/generation/article_writer.py` 一切変更不可**
2. **`src/generation/script_writer.py` の既存ルート (`write_script` /
   `_PROMPT_TEMPLATE` / `_build_script_from_llm`) は変更不可**
3. **`src/triage/` の既存ファイル変更不可**。新規追加は OK。
   **例外条件**: 実装バグ修正 + 設計変更ではない + DECISION_LOG 明記 +
   Hydrangea ミッション中核機構ならカズヤ承認必須、の 4 条件全て満たす場合のみ。
4. **`src/analysis/` 変更不可**
5. **既存テスト破壊しない** (baseline **1417 passed**)

## 7. カズヤの直近フィードバック要点

- **「動くものを壊さない」+「あるべき姿で進める」** (★ F-gemini-model-audit
  2026-05-19) — Gemini モデル移行は両系統 Tier3 を一括 GA 置換 (選択肢1)。
  分割対処は Quality 系 503 多発時の 404 即 raise = 第一作品質直結の致命傷、
  かつ同一 shutdown モデル共有を分割するのは対症療法。一括が論理的に正しい
- **「対症療法じゃなくて根本治療」** — F-gemini-503-stability-audit 撤回
  (リトライ間隔調整等の対症療法ではなく Gemini モデル切替で 503 多発を
  根本治療)
- **「機械判定は事実の代替ではない」** — 候補A が機械的に拾われなくても
  perspective_gap 確定 (WebSearch 独立検証済) は覆らない
- **「中間が良い」** — シニカル一辺倒でも生活実感一辺倒でもなく両立
- **「考え方で制御」** — NG リスト方式は廃止、原則ベースのプロンプト
- **「LLM の知性に委ねる」** — no_match のみ尊重し uncertain を否定と
  読み替えない (B-3')
- **「言い回しを個別ルールで指定するのは避けたい」** (クラウド誤り 9)
- **「Hydrangea のメディアとしてのリスクは嘘をつくこと」** — 疑わしきは低く
  見積もる。ADR-0003 で高リスク事実主張の公開前検証を必須工程化
- **「観点の選択的欠落 = 忖度」** — 第一作 (候補A perspective_gap) を
  「観点の選択的欠落を暴く構造」として確定
- **「負の遺産残さないように」** / **「カズヤの手作業はバッチプロンプトの
  コピペ 1 回のみ」** / **「過剰拡張性の罠」**
- **「整合の説明であって検証ではない」** — 独立検証バッチの価値
- **「設計判断と実装の分離」** — F-gemini-model-audit は調査専用、実装は
  F-gemini-model-migrate-emergency に分離

## 8. 関連ドキュメントへの導線

- 過去の決定の経緯 → `docs/DECISION_LOG.md`
- 残課題リスト → `docs/FUTURE_WORK.md`
- 議論中の未確定メモ → `docs/DISCUSSION_NOTES.md`
- バッチ運用ルール → `docs/BATCH_PROTOCOL.md`
- アーキテクチャ全体像 → `docs/ARCHITECTURE.md`
- 技術的負債リスト → `docs/TECH_DEBT.md`
- Gemini 無料枠 / RPM 対策の経緯 → `docs/GEMINI_QUOTA_NOTES.md` (★ 2026-04-26 時点で陳腐化、F-gemini-model-migrate-emergency で更新予定)
- 編集ミッションフィルタ設計 (F-13 隠れ層含む) → `docs/EDITORIAL_MISSION_FILTER_DESIGN.md`
- ★ 「特定角度」概念正典 → `docs/PARTICULAR_ANGLE_DEFINITION.md`
- Claude Code 振る舞い指針 → `CLAUDE.md`
- ★ **F-gemini-model-audit REPORT + 調査出力** → `docs/runs/F-gemini-model-audit/REPORT.md` + grep_results.json + current_tier_analysis.json + interactions_api_status.json + environment_snapshot.json
- ★ **Phase A.5-3b 画像戦略 / Remotion / モラル ADR** → `docs/ADR/0001-image-strategy.md` + `0002-remotion-mvp-scope.md` + `0003-content-moral-guidelines.md`
- ★ F-trial-run-candidate-a-reverify REPORT → `docs/runs/F-trial-run-candidate-a-reverify/REPORT.md`
- F-image-prompt-spec REPORT + 設計 → `docs/runs/F-image-prompt-spec/REPORT.md` + `schema_extension_design.md`

---

*このドキュメントは F-state-protocol (2026-05-01) で導入。Claude Code が
バッチ完了時に全置換更新する運用 (BATCH_PROTOCOL.md Task 5)。
F-gemini-model-audit (2026-05-19) は **ゲート完了後の 14 つ目のバッチ
(1-L)**。Gemini モデル戦略再検討の影響調査専用 (改修一切なし)。5/25
`gemini-3.1-flash-lite-preview` shutdown 対象の実稼働 functional 使用 = 2
箇所 (`.env` QUALITY Tier3 + LIGHTWEIGHT Tier3、両系統とも fallback 位置)。
★★★ 重大発見: shutdown 後 404 NOT_FOUND は `retry.is_retryable()=False`
のため `factory.generate()` が次 Tier フォールバックせず即 raise = 503
多発時の致命傷。Interactions API 未使用 (無関係)。F-13.B Grounding は
gemini-2.5-flash で shutdown 非該当 (2.5 系維持)。CP-1 カズヤ判断 =
選択肢1 (両系統 Tier3 + config default + `.env.example` を
gemini-3.1-flash-lite (GA) 一括置換、shutdown モデルを Tier から除去 =
404 即 raise リスク根絶)。F-gemini-503-stability-audit 撤回 (モデル切替で
根本治療)、F-periodic-health-check 緊急度 高 → 中降格 (Phase A.5-3d
着手時)。新規残課題 F-gemini-model-migrate-emergency (★★★ 緊急度 高、
5/25 deadline) + F-gemini-quality-tier-poc (緊急度 高、Phase A.5-3b 前)。
`src/ tests/ configs/ scripts/ CLAUDE.md` 0 行変更、`docs/` のみ更新、
baseline **1417 passed** 維持、不変原則 1-5 全遵守。次バッチ候補 =
F-gemini-model-migrate-emergency (★ 最優先、5/25 deadline) →
F-gemini-quality-tier-poc → Phase A.5-3b 第一作起案 (確定モデルで実装)。
過去の経緯は DECISION_LOG.md / FUTURE_WORK.md / DISCUSSION_NOTES.md を参照。*
