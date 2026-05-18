# Hydrangea — Current State (CURRENT_STATE.md)

最終更新: 2026-05-18 (★ F-image-prompt-spec 完了、Phase A.5-3a-verify ゲート完了後の **12 つ目のバッチ**。2026-05-16 の 3 AI 三角測量 3 ラウンド (claude.ai + ChatGPT + Gemini) で確立した D-minimal 仕様を **ADR 3 件 + video_payload schema 拡張設計として正典化** = ADR-0001 (Hydrangea 画像戦略 C': 6-8 枚ベース + 10 イベント、5 色パレット、editorial 路線、cinematic/photorealistic 禁止語彙)、ADR-0002 (Remotion D-minimal 境界: やること/やらないこと/失敗条件1週間/CapCut 非常口)、ADR-0003 (コンテンツモラル: 実在人物 NG / ICRC 標章 NG / AI ラベル投稿前判定 / 高リスク事実公開前検証 / 投稿前ゲート 6 項目)。Task B コード読解で事前調査結果 (image_prompt 非存在・**構造的に必ず 4 scene**・統一末尾なし・video_prompt はテンプレ決定論で LLM 非関与) を**完全裏付け、想定外なし**。schema 拡張は現行 4 scene を壊さず `images[]`/`events[]` を新設・後方互換、第一作 animation は fade-in/cut/dissolve のみ。**実装は一切せず設計のみ** (video_payload_writer.py 改修は Phase A.5-3b 第一作起案で別途)。`src/ tests/ configs/ scripts/ CLAUDE.md` 0 行変更、`docs/` のみ更新、baseline **1417 passed** 維持。新規残課題: Phase A.5-3b 第一作起案 (緊急度 高、ADR+schema 前提) + 第一作公開前の高リスク事実検証ワークフロー (緊急度 中、ADR-0003 由来))

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
**ドメイン階層判定** に置換 + `JP_MEDIA_WHITELIST` 30 ドメイン化。Step C
再測定: Recall covered 42.11% → 89.47% / F1 covered 0.5926 → 0.8718
(threshold 0.85 初突破)。

★★★ 2026-05-14 (F-wl-hit-quality-audit) で **LLM judgement bypass の設計
判断レベルの欠陥** を決定的に発見。Slot-1 cls-6889e9e1c7ac の系統判定 =
**perspective_gap 確定** (afpbb で 9,600 数字 + 虐待を継続報道済み)。

★★★ 2026-05-16 (F-jp-coverage-llm-judgement-extraction) で **LLM judgement
bypass 問題を Option (i) で根本治療完了**。`_parse_llm_judgement` 新規 +
B-3' 表。WL マッチ条件下評価で Recall 1.0000 / Precision 0.8889 / FN=0。
LLM の **明示的否定 (no_match)** のみ尊重し **沈黙 (uncertain)** を否定と
読み替えない。

★★★ 2026-05-16 (F-trial-run-post-llm-extraction) で **B-3' 改修後の本番
挙動を実証**。production verify() (broad-only) に B-3' が確かに配線され、
本番で安全装置が初発火。has_jp_coverage 分布が前回 3/3 True → 1 True /
2 False に反転。**Phase A.5-3b 第一作題材 = 候補A cls-6889e9e1c7ac
(Israel 9,600人) を perspective_gap framing で確定**。

★ 2026-05-18 (F-image-prompt-spec) で **Phase A.5-3b 第一作の画像戦略 +
Remotion 実装範囲 + コンテンツモラルを ADR 3 件 + video_payload schema 拡張
設計として正典化**。本バッチは設計のみ (実装は Phase A.5-3b)。

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

★★★ Phase A.5-3b 第一作 (候補A cls-6889e9e1c7ac) は本系統の framing で起案する
(2026-05-16 確定)。framing 指針 4 点は ADR-0003 / FUTURE_WORK「Phase A.5-3b
第一作起案」に反映済。

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
- `generate_script_with_analysis` 新ルート: 未起動 (analysis_result=null)

★★★ **2026-05-16 (F-trial-run-post-llm-extraction) 再評価**: 上記乖離は
不変。ただし **B-3' は legacy verify() に配線済** のため LLM judgement bypass
是正は本配線群とは **直交して本番反映済**。F-image-prompt-spec (2026-05-18)
は docs バッチで production 未接触のため本乖離に変化なし。本番配線判断バッチ群
3 件は引き続き FUTURE_WORK 緊急度 高に並走待機。

### ブランドポジション

ReHacQ・東洋経済オンラインのトーン。シニカル × 知性、ただし
**「シニカル × 視聴者の生活実感への着地」** が punchline 定義
(F-12-B-1-extension で確定)。陰謀論・扇動禁止、情報密度で勝負。
ターゲット: 20 代後半〜40 代の知的好奇心が高いビジネス層。
★ 視覚ブランドは ADR-0001 で正典化 (5 色パレット: near black / off-white /
hydrangea blue / muted red 限定 / grey、editorial 路線、cinematic/
photorealistic 禁止)。

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

- **main HEAD コミット**: `8dc62da` (F-trial-run-post-llm-extraction マージ後)。F-image-prompt-spec は feature ブランチ `feature/F-image-prompt-spec` で Task A-F 完了、本完了レポート提示後にカズヤ承認 → commit/merge 実行 (Task G)
- **直近 5 件のログ (main)**:
  ```
  8dc62da Merge branch 'feature/F-trial-run-post-llm-extraction'
  71eb2b4 feat: F-trial-run-post-llm-extraction trial run after LLM judgement bypass fix + first video candidate confirmation
  ba51e5f Merge branch 'feature/F-jp-coverage-llm-judgement-extraction'
  3d90f34 feat: F-jp-coverage-llm-judgement-extraction LLM judgement bypass fix (B-3' final)
  f239e13 feat(WIP): F-jp-coverage-llm-judgement-extraction Task E unexpected regression detected
  ```
- **baseline テスト数**: **1417 passed** (F-image-prompt-spec は docs のみで `src/ tests/ configs/ scripts/ CLAUDE.md` 0 行変更、baseline 完全不変)

## 2. 現在のフェーズ

- **Phase**: Phase A.5-3a-verify **完了** (2026-05-07、ゲート完了後 12 バッチ目が本バッチ)
- **進行中バッチ**: なし (F-image-prompt-spec 完了直後、Task E 完了レポート提示 → カズヤ承認待ち → commit/merge)
- **次バッチ候補と推奨** (★ F-image-prompt-spec / 2026-05-18 更新):
  - **1st: F-trial-run-candidate-a-reverify** ★★★ 最有力 (緊急度 高、Phase A.5-3b 第一作着手前**必須**。候補A cls-6889e9e1c7ac を改修後 main で 1 Slot 軽量再試運転 → afpbb bare-domain WL マッチが B-3' でどう判定されるか確認、perspective_gap 前提の妥当性を最終確定、工数 1-2h)
  - **2nd: Phase A.5-3b 第一作起案** ★ (緊急度 高、ADR-0001/0002/0003 + `schema_extension_design.md` 前提。models.py に VideoImage/VideoEvent Optional 追加 + video_payload_writer.py 最小改変 + image_prompt にブランド構造データ注入 + Remotion D-minimal 構築 + framing 指針 4 点反映。F-trial-run-candidate-a-reverify 完了後着手)
  - **3rd: F-grounding-determinism-audit** ★ (緊急度 中、broad Grounding API の WL ドメイン返却率 run 間分散の集約戦略検討)
  - **4th: 第一作公開前の高リスク事実検証ワークフロー** ★ (緊急度 中、ADR-0003 由来、Phase A.5-3b と並走)
  - **5th: 本番配線判断バッチ群 (3 件、並走可)**: verify_two_stage 本番配線 / particular_angle_metadata + sontaku_signals 本番配線 / F-stream-2-filter-design 責務範囲再評価
- **推奨フロー**:
  - commit/merge (本完了レポート提示 → カズヤ承認後)
    → F-trial-run-candidate-a-reverify (★ 第一作着手前必須、軽量)
    → Phase A.5-3b 第一作起案 (候補A cls-6889e9e1c7ac perspective_gap framing、ADR + schema 前提)
    → 並走: F-grounding-determinism-audit + 高リスク事実検証ワークフロー + 本番配線判断バッチ群
    → Phase A.5-3b 第二作のサンプル拡充 → 3c 自動化 → Phase A.5-3d
- **★ Phase A.5-3b 第一作着手前の追加確認事項** (カズヤ指示、2026-05-16 / 2026-05-18 更新):
  1. F-trial-run-candidate-a-reverify (候補A の B-3' 改修後再確認、別バッチ案件)
  2. ~~F-image-prompt-spec スコープ再定義~~ ✅ **完了 (2026-05-18、ADR 3 件 + schema 設計固定化)**
  3. ElevenLabs 声選定 (着手前 30 分作業、既存登録済み、カズヤ手作業)
  4. Remotion セットアップ (第一作で Claude Code に書かせる、Node 環境カズヤ手動準備、ADR-0002 D-minimal)

### Phase A.5-3a-verify ロードマップ (★ F-image-prompt-spec / 2026-05-18 更新版)

**ゲート完了**: 1-A〜1-D''' 全段階完了で Phase A.5-3a-verify ゲート完了 (2026-05-07)。
本バッチはゲート完了後の **12 つ目のバッチ**。

| 段階 | バッチ | 状態 | 概要 |
|---|---|---|---|
| 1-A〜1-D''' | (F-verify-jp-coverage-golden 〜 F-trial-run-post-fix) | ✅ 完了 | ゲート完了 (2026-05-07) |
| 1-E〜1-F''' | (F-particular-angle-design 〜 F-task-e-finalize) | ✅ 完了 | 特定角度概念正典化 + 4 分類化 + sontaku_signals 独立化 |
| 1-G | F-jp-coverage-tune | ✅ 完了 (2026-05-09) | verify_two_stage 新メソッド + 独立 23 件精度測定 |
| 1-G' | F-jp-coverage-tune-followup | ✅ 完了 (2026-05-09) | WL マッチング階層判定化 + WL 拡張、F1 covered 0.8718 初突破 |
| 1-G'' | F-trial-run-post-tune | ✅ 完了 (2026-05-11) | 試運転 3 Slot 全 True (bare-domain bypass)、第一作機械1位 Slot-1 |
| 1-G''' | F-wl-hit-quality-audit | ✅ 完了 (2026-05-14) | ★★★ LLM judgement bypass 決定的発見、Slot-1 perspective_gap 確定 |
| 1-H | F-jp-coverage-llm-judgement-extraction | ✅ 完了 (2026-05-16) | LLM judgement bypass を Option (i) B-3' で根本治療、Recall 1.0000 / FN=0 |
| 1-I | F-trial-run-post-llm-extraction | ✅ 完了 (2026-05-16) | B-3' 本番試運転で bypass 構造解消を本番実証、第一作題材確定 (候補A perspective_gap) |
| **1-J** | **F-trial-run-candidate-a-reverify** | ★★★ **最有力 (緊急度 高)** | 候補A cls-6889e9e1c7ac を改修後 main で 1 Slot 軽量再試運転、perspective_gap 前提の最終確定。Phase A.5-3b 第一作着手前必須。工数 1-2h |
| **1-K** | **F-image-prompt-spec** | ✅ **完了 (2026-05-18)** | **ゲート完了後 12 つ目**。3 AI 三角測量 D-minimal 仕様を ADR 3 件 + video_payload schema 拡張設計として正典化。Task B コード読解で事前調査結果を完全裏付け (想定外なし)。設計のみ、`src/ tests/ configs/ scripts/ CLAUDE.md` 0 変更、baseline 1417 維持 |
| 1-L | Phase A.5-3b 第一作起案 | ★ 緊急度 高 (ADR + schema 前提) | 1-J 完了後着手、候補A perspective_gap framing |
| 1-M | F-grounding-determinism-audit | ★ 緊急度 中 | broad Grounding API の WL ドメイン返却率 run 間分散の集約戦略検討 |
| 1-N | 本番配線判断バッチ群 (3 件) | ★ 並走候補 | verify_two_stage / particular_angle_metadata+sontaku_signals / F-stream-2-filter-design |

### Phase A.5-3d 投稿対象の補足

Phase A.5-3d で本番リリースする対象は **geo_lens (政治・経済) のみ**。
投稿先は TikTok と YouTube Shorts の両方同時、完全自動投稿 (cron 6 時間おき、
人手介入ゼロ、投稿前ゲートで品質保証)。★ 投稿前ゲートのチェックリスト 6 項目は
ADR-0003 で正典化 (実装は FUTURE_WORK「高リスク事実検証ワークフロー」)。

## 3. 直近の試運転結果サマリー

| 試運転 | バッチ | 動画化率 | 主要観察 |
|---|---|---|---|
| **2026-05-18** | **F-image-prompt-spec** | **試運転なし (docs バッチ)** | ★ 3 AI 三角測量 D-minimal 仕様を ADR 3 件 + schema 設計に正典化。Task B コード読解で video_payload は image_prompt 非存在・構造的に必ず 4 scene・統一末尾なし・video_prompt はテンプレ決定論 (LLM 非関与、configs/prompts/ に video_payload プロンプト 0 件) を確認、事前調査結果と完全一致 (想定外なし)。現行 `_BASE_NEGATIVE`/visual_safety_level=elevated の強い安全方向は ADR-0003 と方向一致。実装せず設計のみ、baseline 1417 維持。 |
| 2026-05-16 | F-trial-run-post-llm-extraction | 1/3 動画化 (Slot-1 cls-e2429c77f48e) + 3 articles | ★★★ B-3' が production verify() に配線・本番で安全装置初発火 (Slot-3 cls-02e505cc1310: WL tier_2 + no_match → False)。has_jp_coverage 分布 3/3 True → 1 True / 2 False に反転。防衛機構 5 層全機能。axis_5 候補B=15/25。第一作題材確定 = 候補A cls-6889e9e1c7ac perspective_gap framing。 |
| 2026-05-16 | F-jp-coverage-llm-judgement-extraction | (試運転なし、ゴールデンセット 23 件再測定) | LLM judgement bypass 根本治療。WL マッチ条件下サブセットで Recall 1.0000 / Precision 0.8889 / FN=0 = B-3' 設計通り。baseline 1417 維持。 |
| 2026-05-14 | F-wl-hit-quality-audit | (試運転なし、WebSearch 検証 + Grounding chunk dump) | ★★★ LLM judgement bypass 問題が決定的判明。Slot-1 cls-6889e9e1c7ac = perspective_gap 確定。baseline 1390 維持。 |
| 2026-05-11 | F-trial-run-post-tune | 1/3 動画化 + 3 articles | 3 Slot 全件 has_jp_coverage=True (bare-domain bypass)。第一作機械スコア Slot-1 cls-6889e9e1c7ac 最有力候補確定。 |

## 4. Hydrangea コンセプト防衛機構の現状 (5 層)

> ★ F-image-prompt-spec (2026-05-18) は docs バッチで production 未接触。
> 各層の状態は前バッチ F-trial-run-post-llm-extraction の本番試運転時点から
> **不変** (本バッチで新たな発火・改修なし)。

| 層 | バッチ | 場所 | 役割 | 状態 |
|---|---|---|---|---|
| F-1 | F-1 / F-1.5 | EditorialMissionFilter | 編集ミッション適合度で score 算出 (>= 45.0 で通過) | ✅ 稼働中 (F-trial-run-post-llm-extraction で 369→20 通過) |
| F-2 | F-2 / F-5 | FlagshipGate / EliteJudge | 海外発の重要ニュースを優先 | ✅ 稼働中 (Gate3 10評価→採用7/棄却3、Blocked 0) |
| F-13.B | F-13.B / … / F-jp-coverage-llm-judgement-extraction / F-trial-run-post-llm-extraction | JpCoverageVerifier (WL 30 ドメイン階層判定 + LLM judgement 抽出 B-3') | JP 報道カバレッジを WL + LLM judgement で検証 | ✅ **LLM judgement bypass を B-3' で根本治療 + 本番実証完了**。production verify() に配線、Slot-3 で安全装置初発火、分布 3/3 True → 1 True / 2 False に反転。verify_two_stage 系統機械判別は依然本番未配線 (B-3' とは直交) |
| F-5 | F-5 | FlagshipGate 下流救済 | 上流ガードを通過した候補の最終整合 | ✅ 稼働中 (F-trial-run-post-llm-extraction で 1 件発火) |
| F-13 (隠れ層) | F-13 / F-doc-cleanup | script_writer.py quality_floor_miss bypass | analysis_result 等が成立すれば appraisal の [抑制] を上書き | ✅ 稼働中 (F-trial-run-post-llm-extraction では 0 件発火 = quality floor ブロック自体が発生せず bypass 不要、設計通り) |

## 5. 触ってよい / 触ってはいけない領域マップ

### 触ってよい領域
- `configs/prompts/` 配下全般 (主戦場: `configs/prompts/analysis/geo_lens/`)
- `docs/` 配下全般 (★ `docs/ADR/` 配下に ADR 新規作成可、F-image-prompt-spec で 3 件作成)
- `tests/` 配下に新規テストファイル追加 (既存ファイルは原則変更しない、
  ただし API contract 整合化に伴うフィクスチャ更新 + 既存ファイルへの新規
  テストクラス追加は許容)
- `scripts/` 配下に新規スクリプト追加
- `src/triage/` に新規ファイル追加
- `src/generation/script_writer.py` の **新ルート**
  (`generate_script_with_analysis` / `ScriptWithAnalysisDraft` 等)
- `src/generation/script_writer.py` の `_CHAR_BOUNDS` 等の定数 (最小改変なら許容)
- `src/generation/video_payload_writer.py` (不変原則 1-4 対象外、★ Phase A.5-3b 第一作起案で images[]/events[] 追加の最小改変対象、F-image-prompt-spec では調査のみ・改修なし)
- `src/shared/models.py` (★ Phase A.5-3b で VideoImage/VideoEvent Optional 追加予定、後方互換必須)
- `src/main.py` (不変原則対象外、★ verify_two_stage 本番配線判断バッチで改修対象)

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
   **例外条件 (F-jp-coverage-improve / 2026-05-07 で構造化)**:
   実装バグ修正 + 設計変更ではない + DECISION_LOG 明記 + Hydrangea ミッション
   中核機構ならカズヤ承認必須、の 4 条件全て満たす場合のみ例外適用可。
4. **`src/analysis/` 変更不可**
5. **既存テスト破壊しない** (baseline **1417 passed**)

## 7. カズヤの直近フィードバック要点

- **「中間が良い」** — シニカル一辺倒でも生活実感一辺倒でもなく両立。
  第一作 (候補A) は punchline メディア断定回避を framing 指針化 (ADR-0003)。
- **「考え方で制御」** — NG リスト方式は廃止、原則ベースのプロンプト
- **「対症療法じゃなくて根本治療」** — ★ F-image-prompt-spec (2026-05-18) で
  「スコープ乖離を ADR + schema 設計で正典化、実装は Phase A.5-3b で別途」=
  「動くものを壊さない」+「負債を残さない」+「設計と実装を分離する」運用を実証
- **「LLM の知性に委ねる」** (★ Hydrangea コアバリュー) — LLM の明示的否定
  (no_match) のみ尊重し沈黙 (uncertain) を否定と読み替えない (B-3')
- **「重複しないように定義すればよくね?」** — 系統 1/2 判定対象を『特定角度』
  に限定すれば重複は構造的に消える
- **「言い回しを個別ルールで指定するのは避けたい」** (クラウド誤り 9 = 各論
  コントロールへの誘惑) — ★ F-image-prompt-spec ではブランドカラー/トーン
  語彙を **構造データとして固定**し構図・主題は LLM に委ねる折衷で整理
- **「Hydrangea のメディアとしてのリスクは嘘をつくこと」** — 疑わしきは低く
  見積もる。★ ADR-0003 で高リスク事実主張の公開前検証を必須工程化
- **「観点の選択的欠落 = 忖度」** (F-task-e-finalize / 2026-05-08) — 第一作
  (候補A perspective_gap) を「観点の選択的欠落を暴く構造」として確定
- **「負の遺産残さないように」** / **「カズヤの手作業はバッチプロンプトの
  コピペ 1 回のみ」** / **「過剰拡張性の罠」** / **「動くものを壊さない」**
  — ★ F-image-prompt-spec は実装前倒しを拡張性差し込み判断ルールで却下、
  設計のみに留めた
- **「整合の説明であって検証ではない」** — 独立検証バッチの価値

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
- ★ **Phase A.5-3b 画像戦略 / Remotion / モラル ADR** → `docs/ADR/0001-image-strategy.md` + `0002-remotion-mvp-scope.md` + `0003-content-moral-guidelines.md`
- ★ **F-image-prompt-spec REPORT + 設計** → `docs/runs/F-image-prompt-spec/REPORT.md` + `current_schema_analysis.md` + `schema_extension_design.md`
- F-trial-run-post-llm-extraction REPORT + 分析 → `docs/runs/F-trial-run-post-llm-extraction/REPORT.md` + `video_payload_audit.json`
- F-jp-coverage-llm-judgement-extraction REPORT + 設計仕様 → `docs/runs/F-jp-coverage-llm-judgement-extraction/REPORT.md` + `design_spec_v2.md` (B-3')

---

*このドキュメントは F-state-protocol (2026-05-01) で導入。Claude Code が
バッチ完了時に全置換更新する運用 (BATCH_PROTOCOL.md Task 5)。
F-image-prompt-spec (2026-05-18) は **ゲート完了後の 12 つ目のバッチ**で、
2026-05-16 の 3 AI 三角測量 3 ラウンドで確立した D-minimal 仕様を **ADR 3 件
(ADR-0001 画像戦略 C' / ADR-0002 Remotion D-minimal / ADR-0003 コンテンツ
モラル) + video_payload schema 拡張設計として正典化**。Task B コード読解で
事前調査結果 (image_prompt 非存在・構造的に必ず 4 scene・統一末尾なし・
video_prompt はテンプレ決定論で LLM 非関与) を完全裏付け、想定外なし
(即停止条件に非該当)。schema 拡張は現行 4 scene を壊さず images[]/events[]
を新設・後方互換、第一作 animation は fade-in/cut/dissolve のみ。**実装は
一切せず設計のみ**、video_payload_writer.py 改修は Phase A.5-3b 第一作起案で
別途。`src/ tests/ configs/ scripts/ CLAUDE.md` 0 行変更、`docs/` のみ更新、
baseline **1417 passed** 維持、不変原則 1-5 全遵守。次バッチ候補 =
F-trial-run-candidate-a-reverify (★ 最有力、第一作着手前必須) → Phase A.5-3b
第一作起案 (候補A perspective_gap framing、ADR + schema 前提) →
F-grounding-determinism-audit + 高リスク事実検証ワークフロー + 本番配線判断
バッチ群。★ Project Knowledge 最新化リマインダ: 本バッチで Phase A.5-3b
実装の設計前提 (ADR 3 件) が確定したため、新チャット移行前にカズヤが
claude.ai の Project Knowledge を最新化することを推奨 (特に `docs/ADR/`
配下を追加)。過去の経緯は DECISION_LOG.md / FUTURE_WORK.md /
DISCUSSION_NOTES.md を参照。*
