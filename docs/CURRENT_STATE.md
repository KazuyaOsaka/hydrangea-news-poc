# Hydrangea — Current State (CURRENT_STATE.md)

最終更新: 2026-05-16 (★ F-trial-run-post-llm-extraction 完了、Phase A.5-3a-verify ゲート完了後の **11 つ目のバッチ**。F-jp-coverage-llm-judgement-extraction B-3' 改修後 main (`ba51e5f`) の **本番試運転**。★★★ **B-3' が production verify() に確かに配線され本番で安全装置初発火** = Slot-3 cls-02e505cc1310 で WL tier_2 matched=1 + llm_judgement=no_match → has_jp_coverage=False に B-3' で覆った。has_jp_coverage 分布が F-trial-run-post-tune の 3/3 True (bare-domain bypass) → **1 True / 2 False に反転** = LLM judgement bypass の構造的解消を本番実証。Slot-1 WL 品質も afpbb bare-domain → tier_1 実名紙 2 件 (newsweekjapan.jp + yomiuri.co.jp) に向上。防衛機構 5 層全機能 (F-1 369→20 / F-2 Blocked 0 / F-13.B B-3' 安全装置 1 件 / F-5 救済 1 件 / F-13 隠れ層 0 件 = quality floor ブロック自体なし)。axis_5 候補B cls-e2429c77f48e = 15/25。**Phase A.5-3b 第一作題材確定 = 選択肢4: 候補A cls-6889e9e1c7ac を perspective_gap framing で確定** (editorial_mission=86.0 機械1位、TeleSUR発、axis_5 試算 19/25、framing 指針 4 点)。F-image-prompt-spec 事前調査で video_payload は image_prompt 非存在・4 scene・統一末尾なし = スコープ再定義要。新規残課題 F-trial-run-candidate-a-reverify (第一作着手前必須) 起案。`src/ tests/ configs/ scripts/ CLAUDE.md` 0 行変更、`docs/` + `data/output/` のみ更新、baseline **1417 passed** 維持)

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
系統 1 の中に「広範事件も特定角度も両方未報道 (= 完全空白)」と「広範事件は
報道済み + 特定角度のみ未報道 (= 観点不足)」が混在する構造的問題を、新たに
**系統 2 (perspective_gap)** を独立させることで分離した。台本表現の方向性も
`docs/PARTICULAR_ANGLE_DEFINITION.md` セクション 3.7 で正典化された
(particular_angle_metadata + sontaku_signals 構造を script_writer.py
新ルートに渡し、LLM が系統別の言い回しを自律選択)。

★ 2026-05-08 (F-particular-angle-redesign-extension) で **系統名 1/1.5/2 →
1/2/3** にリネーム + **忖度シグナル (sontaku_signals) を別軸メタデータと
して独立化** + **MECE 判別基準明示** + **Step 3-4 改良** + **クラウド誤り 9
(各論コントロールへの誘惑) を CLAUDE.md / DISCUSSION_NOTES に記録** を実施。

★ 2026-05-09 (F-jp-coverage-tune-followup) で `_match_whitelist` を
**ドメイン階層判定** に置換 + `JP_MEDIA_WHITELIST` 30 ドメイン化
(afpbb.com Tier 2 / forbesjapan.com / nippon.com Tier 4 追加)。Step C
再測定: Recall covered 42.11% → 89.47% / F1 covered 0.5926 → 0.8718
(threshold 0.85 初突破)。

★ 2026-05-11 (F-trial-run-post-tune) 本番試運転で 3 Slot 全件
has_jp_coverage=True (WL 拡張 afpbb x2 + nippon x1)。第一作機械スコア
Slot-1 cls-6889e9e1c7ac (10pt) が最有力候補確定。

★★★ 2026-05-14 (F-wl-hit-quality-audit) で **LLM judgement bypass の設計
判断レベルの欠陥** を決定的に発見 (Gemini が response_text で『該当しない』と
明示判定しても F-13.B は WL マッチだけで True)。Slot-1 cls-6889e9e1c7ac の
系統判定 = **perspective_gap 確定** (afpbb で 9,600 数字 + 虐待を継続報道済み
= 真の silence_gap ではない)。

★★★ 2026-05-16 (F-jp-coverage-llm-judgement-extraction) で **LLM judgement
bypass 問題を Option (i) で根本治療完了**。`_parse_llm_judgement` 新規 +
B-3' 表 (`WL あり + no_match → False (LLM 明確否定のみ安全装置)`、
`match/uncertain/None → True (WL マッチ尊重)`)。WL マッチ条件下評価で
Recall 1.0000 / Precision 0.8889 / FN=0。「LLM の知性に委ねる」原則の解釈
見直し = LLM の **明示的否定 (no_match)** のみ尊重し **沈黙 (uncertain)** を
否定と読み替えない。

★★★ 2026-05-16 (F-trial-run-post-llm-extraction) で **B-3' 改修後の本番
挙動を実証**。production verify() (broad-only) に B-3' が確かに配線され、
本番で安全装置が初発火 (Slot-3 cls-02e505cc1310 で WL tier_2 マッチを LLM
no_match が覆して False)。has_jp_coverage 分布が前回 3/3 True (bare-domain
bypass) → 1 True / 2 False に反転 = LLM judgement bypass の構造的解消を
本番実証。Hydrangea ブランドメッセージ (blind_spot_global ルート =
「日本では報道されない」) が 2/3 Slot で復活。**Phase A.5-3b 第一作題材 =
候補A cls-6889e9e1c7ac (Israel 9,600人) を perspective_gap framing で確定**。

### 系統 1 (silence_gap): 完全な情報空白 — 広範事件も特定角度も日本主要メディアで未報道

完全な情報空白で、Hydrangea コアミッションど真ん中。台本表現は「日本では報じられ
なかった」が成立する。25 件アノテーションの最終分類で 4 件 (16%): blind_001 /
blind_003 / blind_007 / cls-0c7fa7c667d6。

**「構造的に」が核心**: 単に小さい・ニッチな事象ではなく、忖度 / 報道規制 /
報道の自由度の低さによって黙殺されている事象を対象とする。4 軸の構造的
バイアス (1.制度・システム面 / 2.外交・経済・利害関係面 / 3.★個人・権力者面
= 上級国民層への構造的配慮 / 4.関心領域・地政学的死角) のいずれかに該当。

> 忖度、報道規制、報道の自由度の低さをぶち壊そう。
> (2026-05-04 カズヤのメディア宣言)

★ F-task-e-finalize (2026-05-08): **主要扱い事象なのに特定角度だけ抜ける
場合は、リソース不足ではなく忖度**。

### 系統 2 (perspective_gap、★ F-particular-angle-redesign で新設): 観点不足 — 広範事件は報道済み、特定角度は未報道

事件本体は日本でも取り上げられたが、海外メディアが独自に掘った構造分析角度は
深掘りされていない。台本表現は「日本でも事件は取り上げられたが、◯◯という構造に
は触れられていない」になる。25 件アノテーション最終分類で **20 件 (80%)**。

★★★ 2026-05-14 (F-wl-hit-quality-audit) で Slot-1 cls-6889e9e1c7ac
(第一作確定題材) も含めて試運転 3 Slot 中 2 件 + golden サンプリング 5 件中
3 件が stream_2_perspective_gap に該当することが独立検証で確認。Phase
A.5-3b 第一作 (候補A) は本系統の framing で起案する (2026-05-16 確定)。

### 系統 3 (framing_inversion): 報道差の背景解説 — 特定角度も報道済み + 解釈差 + 忖度シグナル

広範事件 + 特定角度も日本主要メディアで報道済み + 評価フレーム対立 +
sontaku_signals.level=high/medium の 3 条件。25 件最終分類で **0 件** ★ 想定外
((c) サンプル選定バイアス仮説の強い証拠、根本治療は Phase A.5-3b 第二作の
サンプル拡充)。

### ★ docs 概念整理と production-pipeline の乖離 (2026-05-11 観察、2026-05-16 再評価で不変確認)

Phase A.5-3a-verify ゲート完了後の連続バッチで概念整理 (4 分類化 +
sontaku_signals 独立化 + verify_two_stage 二段階クエリ生成実装) が docs 上で
進んだが、**production-pipeline 上では未配線**:
- `src/main.py` は legacy `verify()` (broad-only) のみ呼び出し
- `verify_two_stage()` 系統 1/2/3 機械判別: 本番未配線 (計測専用)
- `particular_angle_metadata` / `sontaku_signals`: src/ 配下 grep で 0 件
- `generate_script_with_analysis` 新ルート: 未起動 (analysis_result=null)、
  旧ルート write_script で台本生成

★★★ **2026-05-16 (F-trial-run-post-llm-extraction) 再評価**: 本バッチ試運転
でも上記乖離は不変。ただし **B-3' は legacy verify() に配線済** のため
LLM judgement bypass 是正は本配線群とは **直交して本番反映済** (本番試運転
Slot-3 で安全装置初発火を実証)。本番配線判断バッチ群 3 件は引き続き
FUTURE_WORK 緊急度 高に並走待機。

### ブランドポジション

ReHacQ・東洋経済オンラインのトーン。シニカル × 知性、ただし
**「シニカル × 視聴者の生活実感への着地」** が punchline 定義
(F-12-B-1-extension で確定)。陰謀論・扇動禁止、情報密度で勝負。
ターゲット: 20 代後半〜40 代の知的好奇心が高いビジネス層。

### 3 チャンネル構想と現フォーカス

| チャンネル | 内容 | 状態 |
|---|---|---|
| `geo_lens` | Geopolitical Lens (政治・経済地政学) | **現在唯一のフォーカス** |
| `japan_athletes` | 海外で戦う日本人アスリート | Phase B 以降、未確定 |
| `k_pulse` | 韓国エンタメ | Phase B 以降、未確定 |

Phase A.5-3d で本番リリースするのは geo_lens のみ単独。

### Phase B 以降の新選択肢: 大規模調査機能 (オンデマンド深掘り)

通常運用とは別に、カズヤが事象を指定して大規模調査 → 長尺動画 + 記事を
生成する手動起動パイプラインを Phase B 以降に追加する構想 (系統 2 を特定
事象についてオンデマンドで深掘りする = コアミッションの本流深掘り版)。

---

## 1. リポジトリ状態

- **main HEAD コミット**: `ba51e5f` (F-jp-coverage-llm-judgement-extraction マージ後)。F-trial-run-post-llm-extraction は feature ブランチ `feature/F-trial-run-post-llm-extraction` で Task A-F 完了、本完了レポート提示後にカズヤ承認 → commit/merge 実行 (Task G)
- **feature ブランチ (merge 前)**:
  ```
  ba51e5f Merge branch 'feature/F-jp-coverage-llm-judgement-extraction'
  3d90f34 feat: F-jp-coverage-llm-judgement-extraction LLM judgement bypass fix (B-3' final)
  f239e13 feat(WIP): F-jp-coverage-llm-judgement-extraction Task E unexpected regression detected
  ```
- **baseline テスト数**: **1417 passed** (F-trial-run-post-llm-extraction は試運転 + docs 更新のみで `src/ tests/ configs/ scripts/ CLAUDE.md` 0 行変更、baseline 完全不変)

## 2. 現在のフェーズ

- **Phase**: Phase A.5-3a-verify **完了** (2026-05-07、ゲート完了後 11 バッチ目が本バッチ)
- **進行中バッチ**: なし (F-trial-run-post-llm-extraction 完了直後、Task F 完了レポート提示 → カズヤ承認待ち → commit/merge)
- **次バッチ候補と推奨** (★ F-trial-run-post-llm-extraction / 2026-05-16 更新、第一作題材確定で Phase A.5-3b が前面化):
  - **1st: F-trial-run-candidate-a-reverify** ★★★ 最有力 (緊急度 高、Phase A.5-3b 第一作着手前**必須**。候補A cls-6889e9e1c7ac を改修後 main で 1 Slot 軽量再試運転 → afpbb bare-domain WL マッチが B-3' でどう判定されるか確認、perspective_gap 前提の妥当性を最終確定、工数 1-2h)
  - **2nd: F-image-prompt-spec (スコープ再定義版)** ★ (Phase A.5-3b 前提。image_prompt レイヤー非存在・4 scene・統一末尾なしを踏まえた新設 or video_prompt 拡張の設計判断、着手時に再スコーピング必須)
  - **3rd: Phase A.5-3b 第一作起案** (★ 題材確定済 = 候補A cls-6889e9e1c7ac perspective_gap framing、framing 指針 4 点反映、F-trial-run-candidate-a-reverify + F-image-prompt-spec 完了後着手)
  - **4th: F-grounding-determinism-audit** ★ (緊急度 中、broad Grounding API の WL ドメイン返却率 run 間分散の集約戦略検討、ヘッドライン Recall 主因)
  - **5th: 本番配線判断バッチ群 (3 件、並走可)**: verify_two_stage 本番配線 / particular_angle_metadata + sontaku_signals 本番配線 / F-stream-2-filter-design 責務範囲再評価
  - **6th: F-jp-coverage-tune-followup REPORT v2 化 + ゴールデンセット v2 化検討**
- **推奨フロー**:
  - commit/merge (本完了レポート提示 → カズヤ承認後)
    → F-trial-run-candidate-a-reverify (★ 第一作着手前必須、軽量)
    → F-image-prompt-spec スコープ再定義 (Phase A.5-3b 前提)
    → Phase A.5-3b 第一作着手 (候補A cls-6889e9e1c7ac perspective_gap framing)
    → 並走: F-grounding-determinism-audit + 本番配線判断バッチ群
    → Phase A.5-3b 第二作のサンプル拡充 → 3c 自動化 → Phase A.5-3d
- **★ Phase A.5-3b 第一作着手前の追加確認事項** (カズヤ指示、2026-05-16):
  1. F-trial-run-candidate-a-reverify (候補A の B-3' 改修後再確認、別バッチ案件)
  2. F-image-prompt-spec スコープ再定義 (image_prompt 非存在、video_payload 設計再検討要)
  3. ElevenLabs 声選定 (着手前 30 分作業、既存登録済み、カズヤ手作業)
  4. Remotion セットアップ (第一作で Claude Code に書かせる、Node 環境カズヤ手動準備)

### Phase A.5-3a-verify ロードマップ (★ F-trial-run-post-llm-extraction / 2026-05-16 更新版)

**ゲート完了**: 1-A〜1-D''' 全段階完了で Phase A.5-3a-verify ゲート完了 (2026-05-07)。
本バッチはゲート完了後の **11 つ目のバッチ**。

| 段階 | バッチ | 状態 | 概要 |
|---|---|---|---|
| 1-A〜1-D''' | (F-verify-jp-coverage-golden 〜 F-trial-run-post-fix) | ✅ 完了 | ゲート完了 (2026-05-07) |
| 1-E〜1-F''' | (F-particular-angle-design 〜 F-task-e-finalize) | ✅ 完了 (2026-05-07〜08) | 特定角度概念正典化 + 4 分類化 + sontaku_signals 独立化 |
| 1-G | F-jp-coverage-tune | ✅ 完了 (2026-05-09)、verdict=fail | verify_two_stage 新メソッド + 独立 23 件精度測定 |
| 1-G' | F-jp-coverage-tune-followup | ✅ 完了 (2026-05-09)、F1 達成 | WL マッチング階層判定化 + WL 拡張、F1 covered 0.8718 初突破 |
| 1-G'' | F-trial-run-post-tune | ✅ 完了 (2026-05-11) | 試運転 3 Slot 全 has_jp_coverage=True (bare-domain bypass)、第一作機械1位 Slot-1 |
| 1-G''' | F-wl-hit-quality-audit | ✅ 完了 (2026-05-14) | ★★★ LLM judgement bypass 決定的発見、Slot-1 perspective_gap 確定 |
| 1-H | F-jp-coverage-llm-judgement-extraction | ✅ 完了 (2026-05-16) | LLM judgement bypass を Option (i) B-3' で根本治療、WL マッチ条件下 Recall 1.0000 / FN=0 |
| **1-I** | **F-trial-run-post-llm-extraction** | ✅ **完了 (2026-05-16)** | **ゲート完了後 11 つ目**。B-3' 本番試運転で **bypass 構造解消を本番実証** (Slot-3 安全装置初発火、分布 3/3 True → 1 True / 2 False)。防衛機構 5 層全機能。axis_5 候補B=15/25。**第一作題材確定 = 候補A cls-6889e9e1c7ac perspective_gap framing**。F-image-prompt-spec スコープ乖離判明。`src/ tests/ configs/ scripts/ CLAUDE.md` 0 変更、baseline 1417 維持 |
| **1-J** | **F-trial-run-candidate-a-reverify** | ★★★ **最有力 (2026-05-16 起案、緊急度 高)** | 候補A cls-6889e9e1c7ac を改修後 main で 1 Slot 軽量再試運転 → afpbb bare-domain が B-3' でどう判定されるか、perspective_gap 前提の妥当性を最終確定。Phase A.5-3b 第一作着手前必須。工数 1-2h |
| 1-K | F-image-prompt-spec (スコープ再定義) | ★ Phase A.5-3b 前提 (2026-05-16 スコープ乖離判明) | image_prompt 非存在・4 scene・統一末尾なしを踏まえた新設 or video_prompt 拡張の設計判断、着手時に再スコーピング必須 |
| 1-L | Phase A.5-3b 第一作起案 | ★ 題材確定済 (候補A perspective_gap framing) | 1-J + 1-K 完了後着手 |
| 1-M | F-grounding-determinism-audit | ★ 緊急度 中 | broad Grounding API の WL ドメイン返却率 run 間分散の集約戦略検討 |
| 1-N | 本番配線判断バッチ群 (3 件) | ★ 並走候補 | verify_two_stage / particular_angle_metadata+sontaku_signals / F-stream-2-filter-design |

### Phase A.5-3d 投稿対象の補足

Phase A.5-3d で本番リリースする対象は **geo_lens (政治・経済) のみ**。
投稿先は TikTok と YouTube Shorts の両方同時、完全自動投稿 (cron 6 時間おき、
人手介入ゼロ、投稿前ゲートで品質保証)。

## 3. 直近の試運転結果サマリー

| 試運転 | バッチ | 動画化率 | 主要観察 |
|---|---|---|---|
| **2026-05-16** | **F-trial-run-post-llm-extraction** | 1/3 動画化 (Slot-1 cls-e2429c77f48e のみ script+video_payload+evidence、Slot-2/3 article-only F-16-A) + 3 articles | ★★★ **B-3' が production verify() に確かに配線・本番で安全装置初発火**。試運転 3 Slot: Slot-1 cls-e2429c77f48e (Ukraine drone/Russian EW, Meduza, mission=83) has_jp_coverage=**True** / tier_1 (newsweekjapan.jp + yomiuri.co.jp) / llm_judgement=uncertain → B-3' WL尊重。Slot-2 cls-f48ab61c4b45 (US congresswoman Nakba, MEE, mission=89) **False** / WL なし / no_match。Slot-3 cls-02e505cc1310 (200 ex-diplomats Canada/Israel, MEE, mission=75) **False** / tier_2 matched=1 / no_match → ★ **B-3' 安全装置発火 (WL マッチを LLM no_match が覆す本番初事例)**。has_jp_coverage 分布 F-trial-run-post-tune 3/3 True → **1 True / 2 False に反転** = bypass 構造解消を本番実証、blind_spot_global ルート 2/3 復活。防衛機構 5 層全機能 (F-1 369→20, F-2 Blocked 0, F-13.B B-3' 安全装置 1, F-5 救済 1, F-13 隠れ層 0 = quality floor ブロック自体なし)。axis_5 候補B=15/25。**第一作題材確定 = 候補A cls-6889e9e1c7ac perspective_gap framing** (mission=86 機械1位、axis_5 試算 19/25)。F-image-prompt-spec 事前調査: video_payload は image_prompt 非存在・4 scene・統一末尾なし = スコープ再定義要。`src/ tests/ configs/ scripts/` 0 変更、baseline 1417 維持。 |
| 2026-05-16 | F-jp-coverage-llm-judgement-extraction | (試運転なし、ゴールデンセット 23 件再測定 v1/v2/v3) | LLM judgement bypass 根本治療。Task E (B-3 旧): Recall 0.3750 (想定外退行) → Task E-fix (B-3' 新): WL マッチ条件下サブセットで Recall 1.0000 / Precision 0.8889 / FN=0 = B-3' 設計通り完璧に機能。ヘッドライン Recall 0.4706 は broad Grounding 非決定性 (本スコープ外 → F-grounding-determinism-audit)。baseline 1417 passed 維持。 |
| 2026-05-14 | F-wl-hit-quality-audit | (試運転なし、WebSearch 検証 + Grounding chunk dump) | ★★★ LLM judgement bypass 問題が決定的判明。Slot-1 cls-6889e9e1c7ac = perspective_gap 確定 (afpbb で 9,600 数字 + 虐待継続報道済み)。baseline 1390 維持。 |
| 2026-05-11 | F-trial-run-post-tune | 1/3 動画化 + 3 articles | F-jp-coverage-tune-followup 後の試運転。**3 Slot 全件 has_jp_coverage=True** (afpbb x2 / nippon x1 = bare-domain bypass、F-trial-run-post-fix から完全反転)。第一作機械スコア Slot-1 cls-6889e9e1c7ac (10pt) 最有力候補確定 (★ F-wl-hit-quality-audit で perspective_gap 確定、★ F-trial-run-post-llm-extraction で第一作 framing として perspective_gap で確定)。 |
| 2026-05-09 | F-jp-coverage-tune-followup | (試運転なし) | Recall covered 42.11% → 89.47% / F1 covered 0.5926 → 0.8718 (threshold 初突破)。 |
| 2026-05-07 | F-trial-run-post-fix | 1/3 動画化 + 3 articles | 修正後 F-13.B 本番機能、3 Slot 全 has_jp_coverage=False、防衛機構 5 層全機能。 |

## 4. Hydrangea コンセプト防衛機構の現状 (5 層)

| 層 | バッチ | 場所 | 役割 | 状態 |
|---|---|---|---|---|
| F-1 | F-1 / F-1.5 | EditorialMissionFilter | 編集ミッション適合度で score 算出 (>= 45.0 で通過) | ✅ 稼働中 (F-trial-run-post-llm-extraction で 369→20 通過、selected 3 Slot scores 83/89/75) |
| F-2 | F-2 / F-5 | FlagshipGate / EliteJudge | 海外発の重要ニュースを優先 | ✅ 稼働中 (F-trial-run-post-llm-extraction で Gate3 10評価→採用7/棄却3、Blocked 0、CoherenceGate 2件 PASSED) |
| F-13.B | F-13.B / … / F-jp-coverage-llm-judgement-extraction / **F-trial-run-post-llm-extraction** | JpCoverageVerifier (rescue 廃止 + Web 検証 + ドメイン抽出 + WL 30 ドメイン階層判定 + **LLM judgement 抽出 B-3'**) | JP 報道カバレッジを WL + LLM judgement で検証 | ✅ **LLM judgement bypass を Option (i) B-3' で根本治療 + ★★★ 本番実証完了 (F-trial-run-post-llm-extraction / 2026-05-16)**。B-3' が production verify() (broad-only) に確かに配線され、本番で安全装置初発火 (Slot-3 cls-02e505cc1310: WL tier_2 matched=1 + no_match → False)。has_jp_coverage 分布が前回 3/3 True (bare-domain bypass) → 1 True / 2 False に反転 = bypass 構造的解消を本番実証。Slot-1 WL 品質も bare-domain → tier_1 実名紙 2 件に向上 (uncertain を WL マッチが上書き = Recall 保護も本番機能)。verify_two_stage 系統 1/2/3 機械判別は依然本番未配線 (本配線判断バッチ群と B-3' は直交) |
| F-5 | F-5 | FlagshipGate 下流救済 | 上流ガードを通過した候補の最終整合 | ✅ 稼働中 (F-trial-run-post-llm-extraction で 1 件発火 = cls-02e505cc1310 editorial_mission=75.0 → flagship 認定、reranked_top だが scheduler は cls-e2429c77f48e を動画 Slot-1 に保持、本件は Slot-3 へ) |
| **F-13 (隠れ層)** | F-13 / F-doc-cleanup | script_writer.py quality_floor_miss bypass | analysis_result 等が成立すれば appraisal の [抑制] を上書き | ✅ 稼働中 (F-trial-run-post-llm-extraction では **0 件発火** = quality_floor_report per_event 空 = quality floor ブロック自体が発生せず bypass 不要。前回 1 件発火と挙動差、隠れ層はブロック発生時のみ作動する設計通り) |

## 5. 触ってよい / 触ってはいけない領域マップ

### 触ってよい領域
- `configs/prompts/` 配下全般 (主戦場: `configs/prompts/analysis/geo_lens/`)
- `docs/` 配下全般
- `tests/` 配下に新規テストファイル追加 (既存ファイルは原則変更しない、
  ただし API contract 整合化に伴うフィクスチャ更新 + 既存ファイルへの新規
  テストクラス追加は許容)
- `scripts/` 配下に新規スクリプト追加
- `src/triage/` に新規ファイル追加
- `src/generation/script_writer.py` の **新ルート**
  (`generate_script_with_analysis` / `ScriptWithAnalysisDraft` 等)
- `src/generation/script_writer.py` の `_CHAR_BOUNDS` 等の定数 (最小改変なら許容)
- `src/generation/video_payload_writer.py` (不変原則 1-4 対象外、F-image-prompt-spec で改修対象)
- `src/main.py` (不変原則対象外、★ verify_two_stage 本番配線判断バッチで改修対象)

### 触ってはいけない領域
- `src/generation/article_writer.py` (不変原則 1)
- `src/generation/script_writer.py` の **既存ルート**
  (`write_script` / `_PROMPT_TEMPLATE` / `_build_script_from_llm`) (不変原則 2)
- `src/triage/` の既存ファイル (不変原則 3、F-jp-coverage-improve /
  F-jp-coverage-tune / F-jp-coverage-tune-followup /
  F-jp-coverage-llm-judgement-extraction (2026-05-16、B-3' 3 箇所、4 条件
  全充足) で例外条件適用済)
- `src/analysis/` 配下全般 (不変原則 4)
- 既存テスト (不変原則 5、baseline **1417 passed** 維持 — ただし
  フィクスチャの API contract 整合化 + 既存テストファイルへの新規テスト
  クラス追加 + 仕様変更に伴う既存テスト期待値修正 (構造変更なし) は許容)

## 6. 不変原則 5 つ (リマインダ、正本: BATCH_PROTOCOL.md)

1. **`src/generation/article_writer.py` 一切変更不可**
2. **`src/generation/script_writer.py` の既存ルート (`write_script` /
   `_PROMPT_TEMPLATE` / `_build_script_from_llm`) は変更不可**
3. **`src/triage/` の既存ファイル変更不可**。新規追加は OK。
   **例外条件 (F-jp-coverage-improve / 2026-05-07 で構造化)**:
   実装バグ修正 + 設計変更ではない + DECISION_LOG 明記 + Hydrangea ミッション
   中核機構ならカズヤ承認必須、の 4 条件全て満たす場合のみ例外適用可
   (F-jp-coverage-llm-judgement-extraction / 2026-05-16 で 4 条件全充足適用)。
   ★ scripts/ 例外条件: 実装バグ修正 + 設計変更ではない (出力フィールド追加のみ)
   + DECISION_LOG 明記 + カズヤ承認の 4 条件で計測スクリプト改修可。
4. **`src/analysis/` 変更不可**
5. **既存テスト破壊しない** (baseline **1417 passed**)

## 7. カズヤの直近フィードバック要点

- **「中間が良い」** — シニカル一辺倒でも生活実感一辺倒でもなく両立。
  ★ F-trial-run-post-llm-extraction (2026-05-16) で候補B cls-e2429c77f48e の
  punchline メディア断定 (『報じないのは理解していないから』) が本原則と
  矛盾と判定 → 第一作 (候補A) は punchline メディア断定回避を framing 指針化
- **「考え方で制御」** — NG リスト方式は廃止、原則ベースのプロンプト
- **「対症療法じゃなくて根本治療」** — F-jp-coverage-llm-judgement-extraction
  (2026-05-16) で Task E 想定外退行を CP 検知 → B-3' に設計仕様レベル修正、
  ★ F-trial-run-post-llm-extraction (2026-05-16) で **B-3' の本番実証 +
  「観察と記録に集中するバッチも根本治療の一部」運用が再度実証** (src/
  tests/ configs/ scripts/ 0 変更、docs/ + data/output/ のみで完結)
- **「LLM の知性に委ねる」** (F-task-e-finalize / 2026-05-08、★ Hydrangea
  コアバリュー) — F-jp-coverage-llm-judgement-extraction で Option (i) 根本
  治療、LLM の **明示的否定 (no_match)** のみ尊重し **沈黙 (uncertain)** を
  否定と読み替えない (B-3')。★ F-trial-run-post-llm-extraction で本番安全
  装置初発火を実証
- **「重複しないように定義すればよくね?」** — 系統 1/2 判定対象を『特定角度』
  に限定すれば重複は構造的に消える
- **「言い回しを個別ルールで指定するのは避けたい」** — particular_angle_metadata
  構造を渡して LLM が自律選択する設計 (クラウド誤り 9 = 各論コントロールへの誘惑)
- **「Hydrangea のメディアとしてのリスクは嘘をつくこと」 /「取りこぼした
  ほうが安全じゃない?」** — 疑わしきは低く見積もる。ただし F-jp-coverage-
  llm-judgement-extraction で「LLM 応答の曖昧さ」ではなく「シグナルが何も
  無い時」に適用する原則と再解釈
- **「観点の選択的欠落 = 忖度」** (F-task-e-finalize / 2026-05-08) — 主要扱い
  事象なのに特定角度だけ抜ける = 忖度。★ F-trial-run-post-llm-extraction で
  第一作 (候補A perspective_gap) を「観点の選択的欠落を暴く構造」として確定
- **F-jp-coverage-tune CP 中間チェックポイント方式** — 長時間バッチで中間
  レポート → カズヤ承認後に次 Step。★ F-trial-run-post-llm-extraction でも
  CP-1 (Task C 完了時) でカズヤ判断 (選択肢 2: Slot-1 axis_5 + 第一作再協議)
- **「負の遺産残さないように」** / **「カズヤの手作業はバッチプロンプトの
  コピペ 1 回のみ」** / **「過剰拡張性の罠」** / **「動くものを壊さない」**
- **「整合の説明であって検証ではない」** — 独立検証バッチの価値。★
  F-trial-run-post-llm-extraction は本番試運転で B-3' の整合説明を超えた
  実挙動実証 (Slot-3 安全装置初発火)

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
- ★ **F-trial-run-post-llm-extraction REPORT + 分析** → `docs/runs/F-trial-run-post-llm-extraction/REPORT.md` + `f13b_output_analysis.json` + `video_payload_audit.json` + `axis_5_evaluation.json`
- F-jp-coverage-llm-judgement-extraction REPORT + 設計仕様 → `docs/runs/F-jp-coverage-llm-judgement-extraction/REPORT.md` + `design_spec_v2.md` (B-3')

---

*このドキュメントは F-state-protocol (2026-05-01) で導入。Claude Code が
バッチ完了時に全置換更新する運用 (BATCH_PROTOCOL.md Task 5)。
F-trial-run-post-llm-extraction (2026-05-16) は **ゲート完了後の 11 つ目の
バッチ**で、F-jp-coverage-llm-judgement-extraction B-3' 改修後 main (`ba51e5f`)
の本番試運転。★★★ **B-3' が production verify() に確かに配線され本番で安全装置
初発火** (Slot-3 cls-02e505cc1310 で WL tier_2 マッチを LLM no_match が覆して
False) = LLM judgement bypass の構造的解消を本番実証。has_jp_coverage 分布が
前回 3/3 True (bare-domain bypass) → 1 True / 2 False に反転、blind_spot_global
ルート 2/3 復活。防衛機構 5 層全機能。axis_5 候補B=15/25。**Phase A.5-3b
第一作題材確定 = 候補A cls-6889e9e1c7ac (Israel 9,600人) を perspective_gap
framing で確定** (mission=86 機械1位、axis_5 試算 19/25、framing 指針 4 点)。
F-image-prompt-spec 事前調査で video_payload は image_prompt 非存在・4 scene・
統一末尾なし = スコープ再定義要。新規残課題 F-trial-run-candidate-a-reverify
(第一作着手前必須、緊急度 高) 起案。`src/ tests/ configs/ scripts/ CLAUDE.md`
0 行変更、`docs/` + `data/output/` のみ更新、baseline **1417 passed** 維持。
次バッチ候補 = F-trial-run-candidate-a-reverify (★ 最有力、第一作着手前必須) +
F-image-prompt-spec スコープ再定義 + Phase A.5-3b 第一作起案 (候補A
perspective_gap framing) + F-grounding-determinism-audit + 本番配線判断
バッチ群。★ Project Knowledge 最新化リマインダ: 本バッチ完了で第一作題材が
確定したため、新チャット移行前にカズヤが claude.ai の Project Knowledge を
最新化することを推奨。過去の経緯は DECISION_LOG.md / FUTURE_WORK.md /
DISCUSSION_NOTES.md を参照。*
