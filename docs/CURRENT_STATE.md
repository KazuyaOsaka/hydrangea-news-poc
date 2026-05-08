# Hydrangea — Current State (CURRENT_STATE.md)

最終更新: 2026-05-08 (F-particular-angle-redesign-extension 完了、Phase A.5-3a-verify ゲート完了後の 3 つ目のバッチ、系統名 1/1.5/2 → 1/2/3 リネーム + 忖度シグナル独立化 + クラウド誤り 9 記録 + Step 3-4 改良 + MECE 判別基準明示)

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
忖度シグナルは系統判定とは独立な軸として F-1 EditorialMissionFilter +
F-stream-2-filter-design 第二段階で参照される設計に整理された。

### 系統 1 (silence_gap): 完全な情報空白 — 広範事件も特定角度も日本主要メディアで未報道

完全な情報空白で、Hydrangea コアミッションど真ん中。台本表現は「日本では報じられ
なかった」が成立する。25 件アノテーションの LLM 推定段階で 4 件 (16%):
blind_001 (Ukrainian forces) / blind_003 (US-Israel intervention) / blind_007
(Putin ヨット) / cls-0c7fa7c667d6 (ロシア焼身)。

**「構造的に」が核心**: 単に小さい・ニッチな事象ではなく、忖度 / 報道規制 /
報道の自由度の低さによって黙殺されている事象を対象とする。具体的には 4 軸の
構造的バイアスのいずれかに該当する事象:

**1. 制度・システム面の構造バイアス**:
- 報道規制・自由度の低さ (記者クラブ制度 / クロスオーナーシップ / 政治的圧力)
- スポンサー・広告主への配慮による忖度

**2. 外交・経済・利害関係面の構造バイアス**:
- 特定国への忖度 (米国・中国・韓国・イスラエル・サウジ・ロシア・北朝鮮等)
- 大企業・業界団体への忖度

**3. ★ 個人・権力者面の構造バイアス (Hydrangea ミッションど真ん中)**:
- 政治家・上級官僚・財界要人・司法関係者・メディアオーナー一族・芸能スポーツ界
  権力者等の「上級国民」層への構造的配慮 (スキャンダル黙殺 / 不祥事の遠慮等)

**4. 関心領域・地政学的死角**:
- 日本の地政学的死角 (中東・グローバルサウス・アフリカ・南米等への関心の低さ)

> 忖度、報道規制、報道の自由度の低さをぶち壊そう。
> そういうクソみたいな理由で報道されないものこそ Hydrangea で取り扱うべき記事。
> (2026-05-04 カズヤのメディア宣言)

### 系統 2 (perspective_gap、★ F-particular-angle-redesign で新設、★ extension で命名整理): 観点不足 — 広範事件は報道済み、特定角度は未報道

事件本体は日本でも取り上げられたが、海外メディアが独自に掘った構造分析角度は
深掘りされていない (= 日本メディアは特定角度について何も語っていない / 触れて
いない)。台本表現は「日本でも事件は取り上げられたが、◯◯という構造には触れられて
いない」になる。25 件アノテーションの LLM 推定段階で **20 件 (80%)** ★ 想定外
に多い分布。covered 系列 9 件 + blind_002/004/005/008/009/010 + cls-7bd1406438b6
(FIFA) / cls-33b4f4960bf9_7K (Mandelson) / cls-204a683f73ee_7K (Gaza 7-K) /
cls-6be4fc09d9ed (Insider trading) / cls-a4132ec7d949 (Met Police)。

★ stream_3 = 0 件 / stream_2 = 20 件 という想定外分布は LLM の集約バイアスか
4 分類定義の必然的帰結かをカズヤレビューで判別する論点 (DISCUSSION_NOTES
「2026-05-08: 4 分類化で stream_3 = 0 件 / stream_2 = 20 件 という想定外分布」
参照)、F-particular-angle-redesign-extension (2026-05-08) で命名整理 + sontaku_signals
独立化 + MECE 判別基準明示で構造論点としては Resolved 化、件数論点はカズヤレビュー
後の F-stream-2-filter-design スコープ判断材料として残る。

### 系統 3 (framing_inversion、★ extension で系統 2 → 系統 3 にリネーム): 報道差の背景解説 — 特定角度も報道済み + 解釈差 + 忖度シグナル

広範事件 + 特定角度 (= 海外メディアが独自に掘った視点) も日本主要メディアで
報道済み + 日本メディアと海外メディアの **評価フレームが対立** + 「忖度・報道規制・
黙殺」の構造的シグナル (`sontaku_signals.level=high/medium`) があるという 3 条件
を満たす事象。日本/西側 vs 海外/東側 の解釈・フレーミング・優先順位の差を取り
上げ、その差の背景にある **地政学的理由 / 文化的歴史的背景 / 政治的意図 / 利害
構造** を解説する。台本表現は「日本のメディアは××と捉えたが、海外では△△と
批判されている」になる。25 件アノテーションの LLM 推定段階で **0 件** ★ 想定外。
カズヤレビュー結果次第で F-stream-2-filter-design の責務スコープが大きく変わる。

「日本人が知っておくべき教養としての国際的評価」を提供するメディアとしての本質。

- `framing_inversion` 軸 (perspective_select_and_verify.md): 系統 3 を担う中核軸
- `multi_angle_analysis.md` の 5 観点 (geopolitical / political_intent /
  economic_impact / cultural_context / media_divergence): 報道差の背景を構造化
- `media_divergence` 観点: 日本 / 西側 / グローバルサウス の比較分析
- 実装は部分的: 3 ソース対比ルールが未実装 (DISCUSSION_NOTES「3 ソース対比ルール部分実装」参照)
- ★ F-particular-angle-redesign (2026-05-08) で系統 3 候補が 0 件と推定、
  ★ F-particular-angle-redesign-extension (2026-05-08) で sontaku_signals メタ
  データを Step 4 の追加判定軸として正典化、F-stream-2-filter-design の責務
  スコープはカズヤレビュー後に再評価する

### ブランドポジション

ReHacQ・東洋経済オンラインのトーン。シニカル × 知性、ただし「シニカル = 抽象詩で飾る」
ではなく **「シニカル × 視聴者の生活実感への着地」** が punchline 定義
(F-12-B-1-extension で確定)。陰謀論・扇動禁止、情報密度で勝負。

ターゲット: 20 代後半〜40 代の知的好奇心が高いビジネス層。

### 3 チャンネル構想と現フォーカス

| チャンネル | 内容 | 状態 |
|---|---|---|
| `geo_lens` | Geopolitical Lens (政治・経済地政学) | **現在唯一のフォーカス** |
| `japan_athletes` | 海外で戦う日本人アスリート | Phase B 以降、立ち上げ未確定 |
| `k_pulse` | 韓国エンタメ | Phase B 以降、立ち上げ未確定 |

Phase A.5-3d で本番リリースするのは geo_lens のみ単独。japan_athletes / k_pulse /
カテゴリ細分化は Phase A.5-3d 安定稼働後に判断 (DISCUSSION_NOTES「Phase B 以降の
方向性未確定」参照、2026-05-03 議論で「本命: geo_lens 動画自動投稿、その先は
動画 / 独自メディア / 手動 note・LinkedIn の 3 択」に縮約)。

### Phase B 以降の新選択肢: 大規模調査機能 (オンデマンド深掘り)

通常運用 (cron 自動 / 短尺動画) とは別に、カズヤが事象を指定して大規模調査 →
長尺動画 + 記事を生成する手動起動パイプラインを Phase B 以降に追加する構想。
**系統 2 を特定事象についてオンデマンドで深掘りする機能** = コアミッションの本流
深掘り版。詳細は DISCUSSION_NOTES「大規模調査機能 (オンデマンド深掘りパイプライン)」
参照。

---

## 1. リポジトリ状態

- **main HEAD コミット**: `6b9a1fb` (拡張バッチ未マージ、feature/F-particular-angle-redesign-extension 上で作業)
- **直近 5 件のコミットログ**:
  ```
  6b9a1fb Merge branch 'feature/F-particular-angle-redesign'
  e789b2f feat: 4-classification (stream_1 / stream_1.5 / stream_2 / out_of_scope) for particular_angle, reclassify 25 events, update PARTICULAR_ANGLE_DEFINITION with narrative guidelines (F-particular-angle-redesign, Task A-D + F + G complete, Task E kazuya review pending)
  c469084 Merge branch 'feature/F-particular-angle-design-followup'
  576204e docs: add 4 entries from F-particular-angle-design review (script narration challenge / 1.5 classification proposal / classification distribution / covered_002 confirmation)
  edca8e6 Merge branch 'feature/F-particular-angle-design'
  ```
- **baseline テスト数**: `1345 passed` (本拡張バッチで src/ tests/ configs/ への変更
  なし、`docs/PARTICULAR_ANGLE_DEFINITION.md` 改訂 (命名 1/2/3 + 1.2/1.3/3.5/3.6/3.7
  サブセクション) + `scripts/add_sontaku_signals.py` 新規 + 3 scripts (`reclassify_annotations.py`
  / `generate_review_draft_v2.py` / `finalize_annotations.py`) 命名リネーム +
  `docs/runs/F-particular-angle-design/annotations.json` schema 2.0 → 2.1 + sontaku_signals
  付与 + `docs/runs/F-particular-angle-redesign/extension_log.json` 新規 + `CLAUDE.md`
  クラウド誤りセクション新設 + `docs/` 既存ドキュメント更新のみ、テスト影響なし、
  baseline 維持)

## 2. 現在のフェーズ

- **Phase**: Phase A.5-3a-verify **完了** ★ 1-A〜1-D''' 全完了で Phase A.5-3a-verify ゲート完了 (2026-05-07)
- **進行中バッチ**: なし (F-particular-angle-redesign-extension 完了直後、Task E (4 分類版 + sontaku_signals 込み) カズヤレビュー待ち)
- **次バッチ候補と推奨** (★F-particular-angle-redesign-extension / 2026-05-08 で更新):
  - **1st (★最優先): F-jp-coverage-tune** (二段階クエリ生成 + 真値 25 件整備済み + sontaku_signals 真値整備済み + 系統 1 vs 系統 2 機械判別、本拡張バッチで設計確度更に向上、3-5 時間)
  - **2nd: F-stream-2-filter-design** (★ **責務スコープ要再評価**、系統 3 = 0 件想定外結果のためカズヤレビュー後に判断、1-2 件なら小規模実装 + sontaku_signals.level を解説価値判定の追加軸に組み込む設計で済む)
  - **3rd: Phase A.5-3b 手動 PoC 着手準備** (image-prompt-spec を 3b 最初の作業に組み込み、系統 2 80% という分布を踏まえた言い回し最適化 + sontaku_signals 込みのメタデータ受け渡しが PoC の核心)
  - 並走: F-verify-perspective / F-verify-script-quality
    (3b/3c 中にデータ収集、判断は 3b/3c 完了後 = データ収集性格)
- **推奨フロー**:
  - F-particular-angle-redesign Task E (カズヤレビュー、新分類 1/2/3 + sontaku_signals 込み) 完了 →
    F-jp-coverage-tune 着手 (二段階クエリ生成、系統 1 vs 系統 2 機械判別)
    → F-stream-2-filter-design スコープ判断 (系統 3 件数 + sontaku_signals.level 次第で実装規模変動)
    → Phase A.5-3b 手動 PoC 着手 → 3c 自動化
    → Phase A.5-3d で投稿前ゲート + 自動投稿
- **★ Task E (カズヤレビュー) 待ち**: `docs/runs/F-particular-angle-redesign/review_draft_v2.md`
  をレビュー (★ 拡張バッチ後は新分類 1/2/3 + sontaku_signals メタデータ込みの再生成
  が必要なら別途タスク) → `docs/runs/F-particular-angle-design/annotations.json` の
  `kazuya_review.*_revised` 編集 (sontaku_signals_revised スロット含む) →
  `python scripts/finalize_annotations.py --schema-version 2.0 ...` 実行で
  最終化、その後 F-jp-coverage-tune / F-stream-2-filter-design 判断材料として使用

### Phase A.5-3a-verify ロードマップ (★F-particular-angle-redesign / 2026-05-08 完了版)

**ゲート完了**: 1-A〜1-D''' 全段階完了で Phase A.5-3a-verify ゲート完了。
F-particular-angle-design は **ゲート完了後の 1 つ目のバッチ**で「特定角度」概念を
正典化、F-particular-angle-redesign は **ゲート完了後の 2 つ目のバッチ**で 3 分類 →
4 分類化を実施。後続 2 バッチ (F-jp-coverage-tune / F-stream-2-filter-design) の
共通基盤と責務分離が確立した。

| 段階 | バッチ | 状態 | 概要 |
|---|---|---|---|
| 1-A | F-verify-jp-coverage-golden | ✅ 完了 (2026-05-03) | ゴールデンセット 20 件作成 |
| 1-B | カズヤレビュー (人手) | ✅ 完了 (2026-05-04) | 5 件件ごと判断完了 |
| 1-C | F-verify-jp-coverage-golden-fix | ✅ 完了 (2026-05-04) | 真値修正 + 4 軸 stream-1 基準明文化 + メディア宣言反映 + 2 段階フィルタ設計確定 |
| 1-D | F-verify-jp-coverage-measure | ✅ 完了 (2026-05-05) | F-13.B 精度実測 → verdict=fail、構造的不具合 (Grounding redirect URL vs web.title) を特定 |
| 1-D' | F-jp-coverage-improve | ✅ 完了 (2026-05-07) | F-13.B 構造的不具合の根本治療 (ドメイン抽出レイヤー追加) + 計測再実行 + 不変原則例外条件構造化 + Project Knowledge 運用ルール化 |
| 1-D'' | (1-D' 内で完結) | ✅ 完了 (2026-05-07) | 修正後 verify_jp_coverage_measure.py 再実行で構造的不具合解消を確認 (TP=0→10, FN=14→4)、ただし精度閾値未達は F-jp-coverage-tune に分離 |
| 1-D''' | F-trial-run-post-fix | ✅ 完了 (2026-05-07) | 修正後 F-13.B の本番試運転 + 過去判定後追い、構造的不具合解消の本番動作確認、防衛機構 5 層全機能、試運転 7-K 過去動画 3 件中 2 件が stream_2_candidate パターンと判明 |
| **★ ゲート完了** | — | ✅ **2026-05-07** | 1-A〜1-D''' 全完了で Phase A.5-3a-verify ゲート完了正式宣言 |
| 1-E | F-particular-angle-design | ✅ 完了 (2026-05-07) | ゲート完了後の 1 つ目のバッチ、「特定角度」概念正典化 + 25 件 LLM アノテーション (3 分類版) |
| 1-F | F-particular-angle-redesign | ✅ **完了 (2026-05-08)** | ゲート完了後の 2 つ目のバッチ、3 分類 → 4 分類化 + 系統 1.5 perspective_gap 新設 + 台本表現ガイドライン正典化、Task E カズヤレビュー待ち |
| 1-F' | F-particular-angle-redesign-extension | ✅ **完了 (2026-05-08)** | ゲート完了後の 3 つ目のバッチ、系統名 1/1.5/2 → 1/2/3 リネーム + sontaku_signals 別軸メタデータ独立化 + クラウド誤り 9 記録 + Step 3-4 改良 + MECE 判別基準明示 (Task E カズヤレビューは引き続き待ち、拡張後の新分類 + sontaku_signals 込みで実施) |
| 1-G | F-jp-coverage-tune | ★最優先着手 OK | 二段階クエリ生成 + 系統 1 vs 系統 2 機械判別、本バッチで真値 25 件 + sontaku_signals 整備済み、優先度最上位 |
| 1-H | F-stream-2-filter-design | ★ 責務スコープ要再評価 | 系統 3 = 0 件想定外 + sontaku_signals.level を追加軸に組み込む設計、カズヤレビュー後に判断、1-2 件なら小規模実装 |
| 2 | F-verify-perspective | 並走候補 | axis 分布集計 (3b/3c 中) |
| 3 | F-verify-script-quality | 並走候補 | NG 語彙頻度 / リトライ率集計 (3b/3c 中) |

注: 1-D' 内に 1-D'' (計測再実行) を統合する設計とした (修正と検証は分離不能)。
1-D''' (F-trial-run-post-fix) で Phase A.5-3a-verify ゲート完了正式宣言。
1-E (F-particular-angle-design) と 1-F (F-particular-angle-redesign) は **ゲート完了
後の連続バッチ**で、ゲート完了の必須条件ではなく、後続バッチへの共通基盤確立 + 構造
精緻化の性格。F-jp-coverage-tune (1-G) は精度閾値達成 + 二段階クエリ生成の別系で、
ゲート完了の必須条件ではない。

### Phase A.5-3d 投稿対象の補足

Phase A.5-3d で本番リリースする対象は **geo_lens (政治・経済) のみ**。
japan_athletes / k_pulse / カテゴリ細分化 / 独自メディア化等の方向性は
Phase A.5-3d 安定稼働後に判断 (DISCUSSION_NOTES「Phase B 以降の方向性未確定」参照、
2026-05-03 議論で「本命 + 動画継続 / 独自メディア / 手動投稿の 3 択」に縮約)。

投稿先は TikTok と YouTube Shorts の両方同時、完全自動投稿 (cron 6 時間おき、
人手介入ゼロ、投稿前ゲートで品質保証)。

Phase A.5-3c 実装時は「拡張性差し込み判断ルール」(BATCH_PROTOCOL / 2026-05-03) を
遵守。力点は **ChannelConfig YAML 化 + Publisher 抽象** の 2 つで必要十分
(Content Format 抽象化や Renderer 前倒し抽象化は不要、過剰拡張性の罠を回避)。

## 3. 直近の試運転結果サマリー

| 試運転 | バッチ | 動画化率 | 主要観察 |
|---|---|---|---|
| **2026-05-08** | **F-particular-angle-redesign-extension** | (試運転なし、docs + scripts + LLM 推定) | 系統名 1/1.5/2 → 1/2/3 リネーム (annotations.json 25 件中 20 件 estimated_stream 値更新、schema_version 2.0 → 2.1) + sontaku_signals 25 件 LLM 推定 (level: high=7 / medium=14 / low=1 / none=3、type: diplomatic=20 / domestic=1 / media_industry=1 / null=3、extraction_confidence: high=23 / medium=2 / low=0、約 9 分で完走)。クラウド誤り 9 (各論コントロールへの誘惑) を CLAUDE.md / DISCUSSION_NOTES に記録。Step 3-4 改良 + MECE 判別基準明示で構造論点としては Resolved 化、件数論点はカズヤレビュー後の F-stream-2-filter-design スコープ判断材料として残る。 |
| 2026-05-08 | F-particular-angle-redesign | (試運転なし、docs + LLM 再分類) | 25 件 4 分類化 LLM 再判定: 系統 1=4 (16%) / 系統 2 (旧 1.5)=20 (80%) / 系統 3 (旧 2)=0 (0%) / out_of_scope=1 (4%)。系統 3 = 0 件、系統 2 = 20 件 という **想定外分布** が観測 (想定: 系統 1≈6 / 系統 2≈5 / 系統 3≈13 / out_of_scope=1)。LLM が 4 分類定義を厳密適用した結果として技術的に整合する判定だが、LLM 集約バイアスか必然的帰結かはカズヤレビューで判別。Gemini API 503 高負荷で実行時間 1:36 hr (Tier 1→2→3 フォールバック多発)、per-call timeout 90s + incremental save + resume 追加で完走 (success=25 / error=0)。 |
| 2026-05-07 | F-particular-angle-design | (試運転なし、docs + LLM アノテーション) | LLM (Gemini analysis Tier) で 25 件特定角度抽出: extraction_confidence (high=22 / medium=3 / low=0)、stream 推定 (3 分類版: 系統 1=11 / 系統 2=13 / 対象外=1)、errors=0。max_output_tokens=2000 で JSON 途中切断 (試行 1-2 で 6-7 件失敗) を覚知 → 4096 への拡張で 0 errors。golden_set v1.1 stream_2_candidate メタ付き 4 件のうち 3 件が LLM では stream_1 に分類された差分が観測され、判定対象を「広範事件」vs「特定角度」で取ると結論が変わる構造を可視化。 |
| 2026-05-07 | F-trial-run-post-fix | 1/3 動画化 (Slot-1 のみ) + 3 articles | 修正後 F-13.B が本番で機能 (excluded_count 1/10/3 非ゼロでドメイン抽出層が稼働)、3 Slot 全 has_jp_coverage=False、防衛機構 5 層全機能、WebSearch 後追いで Slot-1 (Insider trading) は Tier 1-2 報道済み = Recall miss (F-jp-coverage-tune の対象)、過去 7-K 動画 3 件のうち 2 件が typical stream_2_candidate パターンと判明 |
| 7-K | F-13.B | 100% (3/3) | FIFA + Gaza×2、rescue path 完全廃止後初の全 Slot 動画化成功 — ★ ただし F-13.B 構造的不具合 (常に False 返却) で全 Slot が blind_spot ルートに進んだだけと再解釈。F-trial-run-post-fix で WebSearch 後追い実施、3 件中 2 件 (FIFA / Mandelson) が実は Tier 1-2 報道済みと判明 |
| F-12-B-1 | F-12-B-1 | — | cls-56c4197b6fd2 米イスラエル隠密作戦、視聴者ファースト改善確認 (固有名詞補足・話し言葉化) |
| F-12-B-1-extension | F-12-B-1-extension | 未実施 | LLM 出力依存のため未実施、抽象比喩軽減は継続観察項目 |

## 4. Hydrangea コンセプト防衛機構の現状 (5 層)

| 層 | バッチ | 場所 | 役割 | 状態 |
|---|---|---|---|---|
| F-1 | F-1 / F-1.5 | EditorialMissionFilter | 編集ミッション適合度で score 算出 (>= 45.0 で通過) | ✅ 稼働中 (F-trial-run-post-fix 試運転で 18/364 通過確認) |
| F-2 | F-2 / F-5 | FlagshipGate (Hydrangea コンセプト整合) | 海外発の重要ニュースを優先 | ✅ 稼働中 (F-trial-run-post-fix 試運転で Blocked 0 件確認) |
| F-13.B | F-13.B / F-jp-coverage-improve / F-trial-run-post-fix | JpCoverageVerifier (rescue 完全廃止 + Web 検証 + ドメイン抽出レイヤー) | JP 報道カバレッジを 27 ドメイン WL で検証 | ✅ **構造的不具合修正完了** (F-jp-coverage-improve / 2026-05-07) + 本番動作確認済み (F-trial-run-post-fix / 2026-05-07)。残課題 (Recall/Precision/Tier 一致率閾値) は F-jp-coverage-tune に分離。**★ F-particular-angle-design (2026-05-07) で「特定角度」概念が正典化、★ F-particular-angle-redesign (2026-05-08) で 4 分類化 + 二段階クエリ生成設計が確定 (broad_event_jp_coverage + particular_angle_jp_coverage 真値 25 件整備済み)、F-jp-coverage-tune では二段階クエリ生成で系統 1 vs 1.5 を機械判別する設計に転換予定** |
| F-5 | F-5 | FlagshipGate 下流救済 | 上流ガードを通過した候補の最終整合 | ✅ 稼働中 (F-trial-run-post-fix 試運転で救済発火 0 件、Elite Judge Gate 3 で十分採用) |
| **F-13 (隠れ層)** | F-13 / F-doc-cleanup | script_writer.py:951-985 quality_floor_miss bypass | analysis_result 等が成立すれば appraisal の [抑制] を上書き | ✅ 稼働中 (F-trial-run-post-fix 試運転で bypass 発火 0 件、3 Slot 全て floor 通過) |

## 5. 触ってよい / 触ってはいけない領域マップ

### 触ってよい領域
- `configs/prompts/` 配下全般 (主戦場: `configs/prompts/analysis/geo_lens/`)
- `docs/` 配下全般 (CURRENT_STATE / DISCUSSION_NOTES / DECISION_LOG /
  FUTURE_WORK / BATCH_PROTOCOL / **PARTICULAR_ANGLE_DEFINITION** 等の更新)
- `tests/` 配下に新規テストファイル追加 (既存ファイルは原則変更しない、
  ただし API contract 整合化に伴うフィクスチャ更新は許容、
  例: F-jp-coverage-improve で `_make_grounding_response` を整合化)
- `scripts/` 配下に新規スクリプト追加 (例: `verify_jp_coverage_measure.py`,
  `replay_jp_coverage.py`, **`extract_particular_angle.py`**, **`finalize_annotations.py`**,
  **`reclassify_annotations.py`**, **`generate_review_draft_v2.py`**,
  **`add_sontaku_signals.py`**)
- `src/triage/` に新規ファイル追加 (例: `jp_coverage_verifier.py`)
- `src/generation/script_writer.py` の **新ルート**
  (`generate_script_with_analysis` / `ScriptWithAnalysisDraft` /
  `_AXIS_TO_PATTERN_HINT` / `_ANALYSIS_DURATION_PROFILES` / `article_text` 等)
- `src/generation/script_writer.py` の `_CHAR_BOUNDS` 等の定数 (最小改変なら許容)

### 触ってはいけない領域
- `src/generation/article_writer.py` (不変原則 1)
- `src/generation/script_writer.py` の **既存ルート**
  (`write_script` / `_PROMPT_TEMPLATE` / `_build_script_from_llm`) (不変原則 2)
- `src/triage/` の既存ファイル (不変原則 3、ただし F-jp-coverage-improve /
  2026-05-07 で `jp_coverage_verifier.py` の `_search_with_grounding()` 修正を
  例外適用済 — BATCH_PROTOCOL「不変原則の例外条件」4 条件全て満たすことを確認
  した上での 1 ファイル × 関数数個の最小修正)
- `src/analysis/` 配下全般 (不変原則 4、F-12-B-2 着手時に例外条項追加検討)
- 既存テスト (不変原則 5、baseline 1345 passed 維持 — ただしフィクスチャの
  API contract 整合化は許容)

## 6. 不変原則 5 つ (リマインダ、正本: BATCH_PROTOCOL.md)

1. **`src/generation/article_writer.py` 一切変更不可**
2. **`src/generation/script_writer.py` の既存ルート (`write_script` /
   `_PROMPT_TEMPLATE` / `_build_script_from_llm`) は変更不可**。
   新ルート (`generate_script_with_analysis` 系) への追加・修正は OK。
   `_CHAR_BOUNDS` 等の定数調整も最小改変なら許容。
   **例外**: `configs/prompts/` 配下のプロンプトファイルは変更可、
   主戦場は `configs/prompts/analysis/geo_lens/`
3. **`src/triage/` の既存ファイル変更不可**。新規追加は OK
   (例: `jp_coverage_verifier.py`)。
   **例外条件 (F-jp-coverage-improve / 2026-05-07 で構造化)**:
   実装バグ修正 + 設計変更ではない + DECISION_LOG 明記 + Hydrangea ミッション
   中核機構ならカズヤ承認必須、の 4 条件全て満たす場合のみ例外適用可。
   詳細は BATCH_PROTOCOL.md「不変原則の例外条件」セクション参照。
4. **`src/analysis/` 変更不可** (F-12-B-2 axis 多様化着手時に例外条項追加検討)
5. **既存テスト破壊しない** (baseline 1345 passed)

## 7. カズヤの直近フィードバック要点

- **「中間が良い」** — シニカル一辺倒でも生活実感一辺倒でもなく、両立
  (F-12-B-1-extension で punchline 定義を「シニカル × 具体着地」両立に)
- **「考え方で制御」** — NG リスト方式は廃止、原則ベースのプロンプト
  (F-12-B-1 で「視聴者ファースト 3 原則」として導入)
- **「対症療法じゃなくて根本治療」** — 仕組みで再発防止
  (F-doc-protocol / F-state-protocol / F-doc-cleanup 等の文書プロトコル整備の動機、
  F-jp-coverage-improve でドメイン抽出レイヤーを SDK 変更耐性の防御層として実装、
  F-trial-run-post-fix で本番試運転で発見された Recall miss は別系
  F-jp-coverage-tune に分離、★ F-particular-angle-design で「広範事件 vs 特定角度」の
  判定単位の曖昧さを概念正典化で根本治療、★ F-particular-angle-redesign で 3 分類の
  「系統 1 内部の混在」を 4 分類化で構造的に解消)
- **「重複しないように定義すればよくね?」** — 系統 1 / 系統 2 の判定対象が
  「広範事件」だと両系統で重複ケース発生 → 判定対象を『特定角度』に限定すれば
  重複は構造的に消える、という 2026-05-07 議論結論。F-particular-angle-design
  で `docs/PARTICULAR_ANGLE_DEFINITION.md` として正典化
- **「一部報道だけど観点不足っていう 1.5 分類儲けてもいいのかもしれない」** — 系統 1
  内部に「完全空白」と「広範のみ報道」が混在する不備の解決策としてカズヤが提案、
  F-particular-angle-redesign (2026-05-08) で 4 分類化 + 系統 1.5 perspective_gap
  新設 + 台本表現ガイドライン正典化として実施
- **「言い回しを個別ルールで指定するのは避けたい」 / 「LLM の知性に期待する」** —
  台本表現は強制ルールではなく particular_angle_metadata 構造を渡して LLM が自律
  選択する設計を採用、`docs/PARTICULAR_ANGLE_DEFINITION.md` セクション 3.7 で正典化
  (旧セクション 3.5、F-particular-angle-redesign-extension で 3.7 にリナンバー)
- **「いまは各論をコントロールしたくない」 / 「分析フェーズの LLM に期待」** —
  視聴者ファースト 3 原則 / ジレンマ解説 / 忖度明示 / 台本表現ルール等の
  各論ルールを追加したくなる傾向は **クラウド誤り 9 (各論コントロールへの誘惑)**
  として記録、再発防止策として CLAUDE.md にクラウド誤りセクション新設 +
  DISCUSSION_NOTES 詳細エントリ追加。代わりに particular_angle_metadata +
  sontaku_signals メタデータを script_writer.py 新ルートに渡し LLM の知性に
  委ねる設計 (F-particular-angle-redesign-extension / 2026-05-08 で正典化)
- **「忖度・報道規制・黙殺の構造を系統判定に組み込むと MECE が崩れる」** —
  忖度シグナル (sontaku_signals) を系統判定とは独立な別軸メタデータとして
  正典化、系統判定は『報道状態』軸のみで MECE、忖度シグナルは F-1
  EditorialMissionFilter (動画化価値) + F-stream-2-filter-design 第二段階
  (解説価値) で参照される独立軸として運用 (F-particular-angle-redesign-extension /
  2026-05-08)
- **「負の遺産残さないように」** — 不整合・乖離を早期解消
  (F-doc-cleanup で F-13 隠れ層昇格 + DECISION_LOG 7 遡及 + CLAUDE.md 全面書き直し)
- **「カズヤの手作業はバッチプロンプトのコピペ 1 回のみ」** — 引き継ぎ
  プロンプト 2806 行の手作業再構築を排除する仕組みとして CURRENT_STATE.md /
  DISCUSSION_NOTES.md を導入
- **「過剰拡張性の罠」** — 「将来のため」の抽象化前倒しは見送る
  (BATCH_PROTOCOL「拡張性差し込み判断ルール」3 条件 / 2026-05-03)
- **「動くものを壊さない」** — F-jp-coverage-improve で構造的不具合修正後も
  本番試運転 + 過去判定後追い (F-trial-run-post-fix) を必須段階として組み込み、
  F-particular-angle-design / F-particular-angle-redesign では src/ tests/ configs/
  一切変更せず docs + scripts のみ

## 8. 関連ドキュメントへの導線

- 過去の決定の経緯 → `docs/DECISION_LOG.md`
- 残課題リスト → `docs/FUTURE_WORK.md`
- 議論中の未確定メモ → `docs/DISCUSSION_NOTES.md`
- バッチ運用ルール → `docs/BATCH_PROTOCOL.md` (不変原則例外条件 + Project Knowledge 運用ルール含む)
- アーキテクチャ全体像 → `docs/ARCHITECTURE.md`
- 技術的負債リスト → `docs/TECH_DEBT.md`
- リファクタ計画 (歴史的記録) → `docs/REFACTORING_PLAN.md`
- 編集ミッションフィルタ設計 (F-13 隠れ層含む) → `docs/EDITORIAL_MISSION_FILTER_DESIGN.md`
- ★ **「特定角度」概念正典 (4 分類版、命名 1/2/3) → `docs/PARTICULAR_ANGLE_DEFINITION.md`** (F-particular-angle-design / 2026-05-07 で導入 + F-particular-angle-redesign / 2026-05-08 で 4 分類化 + F-particular-angle-redesign-extension / 2026-05-08 で命名 1/2/3 整理 + 忖度シグナル独立化 + Step 3-4 改良 + MECE 判別基準明示)
- Claude Code 振る舞い指針 → `CLAUDE.md`

---

*このドキュメントは F-state-protocol (2026-05-01) で導入。
 Claude Code がバッチ完了時に全置換更新する運用 (BATCH_PROTOCOL.md Task 5 参照)。
 F-jp-coverage-improve (2026-05-07) で F-13.B 構造的不具合の根本治療を実施。
 F-trial-run-post-fix (2026-05-07) で修正後 F-13.B の本番動作確認 + Phase A.5-3a-verify
 ゲート完了正式宣言。F-particular-angle-design (2026-05-07) は **ゲート完了後の 1 つ目
 のバッチ**で「特定角度」概念を正典化 + 25 件 LLM アノテーション (3 分類版)。
 F-particular-angle-redesign (2026-05-08) は **ゲート完了後の 2 つ目のバッチ**で 3 分類
 → 4 分類化 + 系統 1.5 perspective_gap 新設 + 台本表現ガイドライン
 (PARTICULAR_ANGLE_DEFINITION.md セクション 3.5、後 3.7 にリナンバー) を正典化。
 F-particular-angle-redesign-extension (2026-05-08) は **ゲート完了後の 3 つ目の
 バッチ**で系統名 1/1.5/2 → 1/2/3 リネーム + 忖度シグナル (sontaku_signals)
 を別軸メタデータとして独立化 + Step 3-4 改良 + MECE 判別基準明示 +
 クラウド誤り 9 (各論コントロールへの誘惑) を CLAUDE.md / DISCUSSION_NOTES に
 記録。LLM 推定段階の 4 分類分布は stream_1=4 / stream_2=20 / stream_3=0 /
 out_of_scope=1 (★ stream_3 = 0 件、stream_2 = 20 件 という想定外結果は構造論点
 としては Resolved 化、件数論点はカズヤレビューで判別する論点として残る)。
 sontaku_signals 25 件 LLM 推定分布: level high=7 / medium=14 / low=1 / none=3、
 type diplomatic=20 / domestic=1 / media_industry=1 / null=3、extraction_confidence
 high=23 / medium=2 / low=0。Task E (カズヤレビュー、新分類 1/2/3 +
 sontaku_signals 込み) 待ちで、レビュー後に `scripts/finalize_annotations.py
 --schema-version 2.0` で最終化される。本拡張バッチは src/ tests/ configs/
 一切変更なし (新規 scripts/add_sontaku_signals.py + 3 scripts 命名リネーム +
 docs 改訂 + annotations.json schema 2.1 + sontaku_signals 付与 + CLAUDE.md
 クラウド誤りセクション新設 + docs/runs/F-particular-angle-redesign/extension_log.json
 新規)、baseline 1345 passed 維持。
 ★ Project Knowledge 最新化リマインダ: 本拡張バッチ完了で F-jp-coverage-tune 着手の
 前提が完全に整ったため (4 分類 1/2/3 + sontaku_signals 真値 25 件)、新チャット移行前に
 カズヤが手動で claude.ai の Project Knowledge を **必須最新化** することを推奨
 (BATCH_PROTOCOL の Project Knowledge 運用ルールに従う、
 `docs/PARTICULAR_ANGLE_DEFINITION.md` の 1/2/3 命名版 + `CLAUDE.md` のクラウド誤り
 セクション新設版を新規アップロード対象に含めること)。
 過去の経緯は DECISION_LOG.md / FUTURE_WORK.md / DISCUSSION_NOTES.md を参照。*
