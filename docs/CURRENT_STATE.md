# Hydrangea — Current State (CURRENT_STATE.md)

最終更新: 2026-05-11 (F-trial-run-post-tune 完了、Phase A.5-3a-verify ゲート完了後の 8 つ目のバッチ、F-jp-coverage-tune-followup マージ後の本番試運転 + 防衛機構 5 層監査 + 拾われた Slot の台本品質確認 + 第一作題材ランク付け、3/3 で WL 拡張ドメイン (afpbb x2 + nippon x1) ヒット = 本番影響の強さ確認、機械スコア 1 位 = Slot-1 cls-6889e9e1c7ac 「9,600 Detainees: Israel Prison Abuses」(10pt) で第一作の最有力候補確定、`src/` `tests/` `configs/` `scripts/` 0 変更で baseline 1390 passed 維持、新規残課題 4 件追加 (= F-13.B WL ヒット品質検証 / verify_two_stage 本番配線判断 / particular_angle_metadata + sontaku_signals 本番配線判断 / F-stream-2-filter-design 責務範囲再評価))

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

★ 2026-05-09 (F-jp-coverage-tune-followup) で F-jp-coverage-tune verdict=fail の
**根本原因 3 分解 → 主因 2 つを根本治療** を実施。`_match_whitelist()` 内のドメイン
判定を **substring match → ドメイン階層判定** に置換 (新規モジュール関数
`_domain_matches_hierarchy` 追加、`news.fnn.jp` 登録に対して `fnn.jp` 返却でも
同 Tier 扱い、TLD 共通や部分文字列の過剰マッチは排除) + `JP_MEDIA_WHITELIST` に
3 ドメイン追加 (`afpbb.com` Tier 2 / `forbesjapan.com` / `nippon.com` Tier 4)。
Step C 再測定結果: **Recall covered 42.11% → 89.47% (+47.36pp)** / **F1 covered
0.5926 → 0.8718 (+0.2792、threshold 0.85 を初突破)**。verdict=fail のまま
(Recall 0.53pp 不足 + Precision blind / Tier 一致率 / Stream accuracy 未達) だが、
F-13.B 系列で F1 covered が threshold を初突破した実用ライン到達。

★ 2026-05-11 (F-trial-run-post-tune) で F-jp-coverage-tune-followup マージ後の
**本番試運転 + 防衛機構 5 層監査 + 第一作題材ランク付け** を実施。試運転 3 Slot
全件で has_jp_coverage=True (WL 拡張 afpbb x2 + nippon x1 でヒット、F-trial-run-post-fix
0/3 から完全反転) = WL 拡張の本番影響が想定以上に強いことを確認。第一作題材機械
スコア: Slot-1 cls-6889e9e1c7ac (10pt) > Slot-2 (6pt) > Slot-3 (5pt)、Slot-1 は
editorial_mission_score=86.0 (Hydrangea ど真ん中) + 唯一 video_payload 生成済み
= 第一作の最有力候補確定。`src/` `tests/` `configs/` `scripts/` 0 行変更、`docs/`
配下のみ更新で完結、baseline 1390 passed 維持。**重要な観察事項として 4 件**を残課題化:
(1) F-13.B WL ヒット品質の独立検証 (matched_urls がベアドメインのみで誤陽性リスク)、
(2) verify_two_stage 本番配線判断 (production main.py は legacy verify() のみ呼び出し)、
(3) particular_angle_metadata + sontaku_signals 本番配線判断 (src/ 配下 grep で 0 件)、
(4) F-stream-2-filter-design 責務範囲再評価 (本番運用視点反映)。

### 系統 1 (silence_gap): 完全な情報空白 — 広範事件も特定角度も日本主要メディアで未報道

完全な情報空白で、Hydrangea コアミッションど真ん中。台本表現は「日本では報じられ
なかった」が成立する。25 件アノテーションの最終分類 (Task E カズヤレビュー後 = LLM
推定値そのまま) で 4 件 (16%): blind_001 (Ukrainian forces) / blind_003 (US-Israel
intervention) / blind_007 (Putin ヨット) / cls-0c7fa7c667d6 (ロシア焼身)。

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

★ F-task-e-finalize (2026-05-08) で「観点の選択的欠落 = 忖度」判定軸が確立:
**主要扱い事象なのに特定角度だけ抜ける場合は、リソース不足ではなく忖度**
(blind_009 / covered_005 / covered_010 等)。「忖度」の定義を「特定国・人物への
外交的配慮」だけに限定せず、「権力構造・戦争構造・利権構造に踏み込まない」
全般を含める。

### 系統 2 (perspective_gap、★ F-particular-angle-redesign で新設、★ extension で命名整理): 観点不足 — 広範事件は報道済み、特定角度は未報道

事件本体は日本でも取り上げられたが、海外メディアが独自に掘った構造分析角度は
深掘りされていない (= 日本メディアは特定角度について何も語っていない / 触れて
いない)。台本表現は「日本でも事件は取り上げられたが、◯◯という構造には触れられて
いない」になる。25 件アノテーションの最終分類で **20 件 (80%)** ★ 想定外
に多い分布。covered 系列 9 件 + blind_002/004/005/008/009/010 + cls-7bd1406438b6
(FIFA) / cls-33b4f4960bf9_7K (Mandelson) / cls-204a683f73ee_7K (Gaza 7-K) /
cls-6be4fc09d9ed (Insider trading) / cls-a4132ec7d949 (Met Police)。

★ stream_3 = 0 件 / stream_2 = 20 件 という想定外分布は F-task-e-finalize
(2026-05-08) のカズヤレビューで (c) サンプル選定バイアス仮説の **強い証拠**
が確認された。根本治療は Phase A.5-3b 第二作のサンプル拡充 (処理水放出 / 辺野古 等)。

### 系統 3 (framing_inversion、★ extension で系統 2 → 系統 3 にリネーム): 報道差の背景解説 — 特定角度も報道済み + 解釈差 + 忖度シグナル

広範事件 + 特定角度 (= 海外メディアが独自に掘った視点) も日本主要メディアで
報道済み + 日本メディアと海外メディアの **評価フレームが対立** + 「忖度・報道規制・
黙殺」の構造的シグナル (`sontaku_signals.level=high/medium`) があるという 3 条件
を満たす事象。「日本人が知っておくべき教養としての国際的評価」を提供するメディア
としての本質。25 件アノテーションの最終分類で **0 件** ★ 想定外。

### ★ docs 概念整理と production-pipeline の乖離 (2026-05-11 F-trial-run-post-tune で確認)

Phase A.5-3a-verify ゲート完了後の連続バッチで概念整理 (4 分類化 +
sontaku_signals 独立化 + verify_two_stage 二段階クエリ生成実装) が docs 上で
進んだが、**production-pipeline 上では未配線**:
- `src/main.py:3187` は legacy `verify()` (broad-only) のみ呼び出し
- `verify_two_stage()` 系統 1/2/3 機械判別: 本番未配線 (scripts/measure_two_stage_accuracy.py 計測専用)
- `particular_angle_metadata` / `sontaku_signals`: src/ 配下 grep で 0 件
- `generate_script_with_analysis` 新ルート: F-trial-run-post-tune Slot-1 で `analysis_result=null` で未起動、旧ルート + F-13 隠れ層 bypass で台本生成

これは「概念正典化先行 + 本番配線は段階的」戦略の結果であり、配線判断バッチ
3 件が FUTURE_WORK 緊急度 高に新規追加された (verify_two_stage / particular_angle_metadata
+ sontaku_signals 本番配線 / F-stream-2-filter-design 責務範囲再評価)。

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

Phase A.5-3d で本番リリースするのは geo_lens のみ単独。

### Phase B 以降の新選択肢: 大規模調査機能 (オンデマンド深掘り)

通常運用 (cron 自動 / 短尺動画) とは別に、カズヤが事象を指定して大規模調査 →
長尺動画 + 記事を生成する手動起動パイプラインを Phase B 以降に追加する構想。
**系統 2 を特定事象についてオンデマンドで深掘りする機能** = コアミッションの本流
深掘り版。

---

## 1. リポジトリ状態

- **main HEAD コミット**: `4062639` (F-jp-coverage-tune-followup マージ後。F-trial-run-post-tune は feature ブランチ `feature/F-trial-run-post-tune` で作業中、未マージ)
- **直近 5 件のコミットログ**:
  ```
  4062639 Merge branch 'feature/F-jp-coverage-tune-followup'
  84a678e feat: WL hierarchy match + WL extension 3 domains (F-jp-coverage-tune-followup, verdict=fail but Recall +47.36pp / F1 covered 0.8718 first threshold break, root cause resolved, 4 residual axes split)
  82ce0d0 Merge branch 'feature/F-jp-coverage-tune'
  beb4aa7 feat: F-13.B verify_two_stage two-stage query generation + 23-event accuracy measurement (F-jp-coverage-tune, verdict=fail, Grounding API structural limit identified, followup drafted)
  e1ad637 Merge branch 'feature/F-task-e-finalize'
  ```
- **baseline テスト数**: **1390 passed** (F-trial-run-post-tune では `src/` `tests/` `configs/` `scripts/` 0 行変更、`docs/` のみ更新で baseline 完全維持。F-trial-run-post-tune 開始時に baseline 1390 passed を再確認、終了時も 1390 passed)

## 2. 現在のフェーズ

- **Phase**: Phase A.5-3a-verify **完了** ★ 1-A〜1-D''' 全完了で Phase A.5-3a-verify ゲート完了 (2026-05-07)
- **進行中バッチ**: なし (F-trial-run-post-tune 完了直後、`src/ tests/ configs/ scripts/` 0 変更、baseline 1390 passed 維持)
- **次バッチ候補と推奨** (★ F-trial-run-post-tune / 2026-05-11 で更新、★ Phase A.5-3b 第一作起案を最有力候補に昇格):
  - **1st: Phase A.5-3b 第一作起案** ★最有力候補昇格 (本バッチで題材ランク 1 位 = Slot-1 cls-6889e9e1c7ac 「9,600 Detainees: Israel Prison Abuses」が機械スコア 10pt で確定 + 動画 payload 生成済み + Hydrangea ど真ん中、カズヤ axis_5 主観評価が前提条件)
  - **2nd: 本番配線判断 + WL ヒット品質検証バッチ群 (4 件、並走進行が望ましい)**:
    - F-13.B WL ヒット品質の独立検証 (★ 高、matched_urls ベアドメイン問題、第一作着手判断と直前に実施)
    - verify_two_stage 本番配線判断 (production-pipeline と docs 概念整理の乖離解消)
    - particular_angle_metadata + sontaku_signals 本番配線判断 (新ルート起動条件)
    - F-stream-2-filter-design 責務範囲再評価 (本番運用視点反映)
  - **3rd: F-stream-2-filter-design** (★ 責務スコープ要再評価、stream_3 = 0 件確定 + Phase A.5-3b 第二作のサンプル拡充後に再評価が望ましい、小規模実装で済む可能性高 + 本バッチで顕在化した「has_jp_coverage=True 3/3 で blind_spot_global 消滅」問題を責務範囲として組み込む可能性高)
  - **4th: Phase A.5-3b 第二作のサンプル拡充検討** (★ 系統 3 事象 + sontaku_signals type=domestic / media_industry の実例追加、(c) 仮説検証 + 系統 3 台本表現の試行錯誤を兼ねる、★ 副次効果として truly unreported 母数の拡充 = Precision blind 母数問題の根本治療)
  - **5th (★ カズヤ判断後): F-jp-coverage-tune-followup-2** (★ 候補、Recall 90% 突破 + Tier 一致率 Grounding 非決定性、(p) 多クエリ並列発行 or (q) 検索 API 変更、副作用リスク = Precision blind / Tier 一致率がさらに退行する可能性、緊急性は低下)
- **推奨フロー**:
  - F-13.B WL ヒット品質独立検証 (Phase A.5-3b 第一作着手判断と直前で実施、結果次第で F-jp-coverage-tune-followup REPORT を v2 化する必要)
    → カズヤ Slot-1 axis_5 主観評価 → 承認なら **Phase A.5-3b 第一作着手** (動画レンダリング + 配信前ゲート + 投稿)
    → 並走: 本番配線判断バッチ群 (verify_two_stage / particular_angle_metadata + sontaku_signals)
    → F-stream-2-filter-design スコープ判断 → Phase A.5-3b 第二作のサンプル拡充
    → 3c 自動化 → Phase A.5-3d で投稿前ゲート + 自動投稿
- **★ F-trial-run-post-tune 完了** (F-trial-run-post-tune / 2026-05-11): `src/` `tests/`
  `configs/` `scripts/` 0 行変更、`docs/` 配下のみ更新で完結。baseline 1390 passed 維持。
  本番試運転 3 Slot 全件で has_jp_coverage=True (WL 拡張 afpbb x2 + nippon x1)、第一作
  題材ランク 1 位 = Slot-1 cls-6889e9e1c7ac (機械スコア 10pt、video_payload 生成済み)。
  Hydrangea ブランドメッセージ (blind_spot_global) が機械判別で消滅する副作用 +
  WL ヒット品質 (matched_urls ベアドメイン問題) + production-pipeline と docs 概念整理の
  乖離が顕在化、4 件の残課題を FUTURE_WORK 緊急度 高に追加。

### Phase A.5-3a-verify ロードマップ (★F-trial-run-post-tune / 2026-05-11 完了版)

**ゲート完了**: 1-A〜1-D''' 全段階完了で Phase A.5-3a-verify ゲート完了。
F-trial-run-post-tune は **ゲート完了後の 8 つ目のバッチ** で F-jp-coverage-tune-followup
改修後の本番試運転 + 第一作題材ランク付けを実施した。

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
| 1-F | F-particular-angle-redesign | ✅ 完了 (2026-05-08) | ゲート完了後の 2 つ目のバッチ、3 分類 → 4 分類化 + 系統 1.5 perspective_gap 新設 + 台本表現ガイドライン正典化 |
| 1-F' | F-particular-angle-redesign-extension | ✅ 完了 (2026-05-08) | ゲート完了後の 3 つ目のバッチ、系統名 1/1.5/2 → 1/2/3 リネーム + sontaku_signals 別軸メタデータ独立化 + クラウド誤り 9 記録 + Step 3-4 改良 + MECE 判別基準明示 |
| 1-F'' | F-extension-followup | ✅ 完了 (2026-05-08) | ゲート完了後の 4 つ目のバッチ、extension クラウドレビュー指摘 3 件反映 = stream_3=0 件 (c) サンプル選定バイアス仮説追記 + sontaku_signals type 分布バイアス記録 + finalize_annotations.py の sontaku_signals 対応最小修正 |
| 1-F''' | F-task-e-finalize | ✅ 完了 (2026-05-08) | ゲート完了後の 5 つ目のバッチ、Task E カズヤレビュー結果反映 (25 件全件 LLM 推定値そのまま) + finalize_annotations.py 実行 + 4 つの運用原則 + 1 つの構造的問題 + (c) 仮説証拠強化を docs 化 |
| 1-G | F-jp-coverage-tune | ✅ 完了 (2026-05-09)、verdict=fail | ゲート完了後の 6 つ目のバッチ、`verify_two_stage()` 新メソッド + `TwoStageVerifyResult` dataclass 追加 (不変原則 3 例外条件 4 つ全部適用) + 独立 23 件精度測定 + (c) dateRestrict プロンプト埋め込み除去 1 回チューニング。post-tuning verdict=fail (Recall 42.11% / Precision blind 26.67% / F1 0.5926 / Tier 62.50%)。**Grounding API 構造的限界が明確化** = F-jp-coverage-tune-followup で根本治療議論へ |
| 1-G' | F-jp-coverage-tune-followup | ✅ 完了 (2026-05-09)、verdict=fail (改善大、F1 達成) | ゲート完了後の 7 つ目のバッチ、verdict=fail 主因 3 分解 → WL マッチング階層判定化 (新規 `_domain_matches_hierarchy`) + WL 拡張 3 ドメイン (`afpbb.com` Tier 2 / `forbesjapan.com` `nippon.com` Tier 4) で根本治療。**Recall covered +47.36pp** (42.11%→89.47%、threshold 0.53pp 不足) / **F1 covered +27.92pp** (0.5926→0.8718、threshold 0.85 **初突破**) / Precision blind 33.33% / Tier 一致率 30.77% / Stream accuracy 9.09%。CP-3 で Step D スキップ判定 = 残課題 4 軸分離 |
| **1-G''** | **F-trial-run-post-tune** | ✅ **完了 (2026-05-11)** | **ゲート完了後の 8 つ目のバッチ**、F-jp-coverage-tune-followup マージ後の本番試運転 + 防衛機構 5 層監査 + 拾われた Slot の台本品質確認 + 第一作題材ランク付け (機械 4 軸 + カズヤ主観 1 軸空欄)。試運転 3 Slot 全件 has_jp_coverage=True (afpbb x2 + nippon x1)、F-trial-run-post-fix から完全反転。**機械スコア 1 位 = Slot-1 cls-6889e9e1c7ac (10pt) で第一作の最有力候補確定** (editorial_mission_score=86.0、Hydrangea ど真ん中、唯一 video_payload 生成済み)。`src/` `tests/` `configs/` `scripts/` 0 変更、`docs/` のみ更新、baseline 1390 passed 維持。重要観察事項 4 件残課題化: (1) F-13.B WL ヒット品質の独立検証 (matched_urls ベアドメインのみで誤陽性リスク)、(2) verify_two_stage 本番配線判断 (production-pipeline と docs 概念整理の乖離解消)、(3) particular_angle_metadata + sontaku_signals 本番配線判断 (新ルート起動条件)、(4) F-stream-2-filter-design 責務範囲再評価 (本番運用視点反映) |
| 1-H | F-stream-2-filter-design | ★ 責務スコープ要再評価 | stream_3 = 0 件確定 + sontaku_signals.level を追加軸に組み込む設計、Phase A.5-3b 第二作のサンプル拡充後に再評価、小規模実装の可能性が高い + **★ F-jp-coverage-tune-followup で顕在化した stream_3 過剰検出 + F-trial-run-post-tune で顕在化した「has_jp_coverage=True 3/3 で blind_spot_global 消滅」 を責務範囲として組み込む可能性高** |
| 2 | F-verify-perspective | 並走候補 | axis 分布集計 (3b/3c 中) |
| 3 | F-verify-script-quality | 並走候補 | NG 語彙頻度 / リトライ率集計 (3b/3c 中) |

### Phase A.5-3d 投稿対象の補足

Phase A.5-3d で本番リリースする対象は **geo_lens (政治・経済) のみ**。

投稿先は TikTok と YouTube Shorts の両方同時、完全自動投稿 (cron 6 時間おき、
人手介入ゼロ、投稿前ゲートで品質保証)。

Phase A.5-3c 実装時は「拡張性差し込み判断ルール」(BATCH_PROTOCOL / 2026-05-03) を
遵守。力点は **ChannelConfig YAML 化 + Publisher 抽象** の 2 つで必要十分。

## 3. 直近の試運転結果サマリー

| 試運転 | バッチ | 動画化率 | 主要観察 |
|---|---|---|---|
| **2026-05-11** | **F-trial-run-post-tune** | **1/3 動画化** (Slot-1 のみ video_payload + script 生成、Slot-2/3 article-only F-16-A mode) + 3 articles | F-jp-coverage-tune-followup マージ後の本番試運転。**3 Slot 全件で has_jp_coverage=True** (afpbb x2 / nippon x1 = WL 拡張ドメイン全件ヒット、F-trial-run-post-fix から完全反転)。Slot-1 cls-6889e9e1c7ac (TeleSUR 発「9,600 Detainees: Israel Prison Abuses」editorial_mission_score=86.0、Hydrangea ど真ん中) / Slot-2 cls-1a38c0ca8c99 (MEE 発「BBC Gaza documentary BAFTA 受賞」77.0) / Slot-3 cls-03892eab2072 (MEE 発「Tehran says US proposal sought Iran's surrender」83.0、judge=blind_spot_global score 9.0)。防衛機構 5 層全機能 (F-1 20/304, F-2 通過, F-13.B 3/3 True, F-5 救済 1 件 / cls-da0a74aa712d 選定外, F-13 隠れ層 bypass 1 件 / Slot-1)。**第一作題材機械スコア: Slot-1 (10pt) > Slot-2 (6pt) > Slot-3 (5pt)、Slot-1 が機械スコア 1 位 + 唯一 script 生成済み + Hydrangea ど真ん中 = 第一作最有力候補確定** (カズヤ axis_5 主観評価が最終判断)。重要観察 4 件: (1) matched_urls がベアドメインのみ = 誤陽性リスク、(2) production main.py は legacy verify() のみ呼び出し = verify_two_stage 未配線、(3) particular_angle_metadata / sontaku_signals 本番未配線、(4) Hydrangea ブランドメッセージ (blind_spot_global) が機械判別で消滅 = F-stream-2-filter-design 責務範囲再評価必要。`src/ tests/ configs/ scripts/` 0 変更、baseline 1390 passed 維持。 |
| 2026-05-09 | F-jp-coverage-tune-followup | (試運転なし、独立 23 件再測定 + WL 整備) | F-jp-coverage-tune verdict=fail の根本原因 3 分解 → 主因 2 つ (WL マッチング欠陥 + WL 漏れ準大手) を根本治療。Step C 再測定: **Recall covered 42.11% → 89.47% (+47.36pp)** / **F1 covered 0.5926 → 0.8718 (+0.2792、threshold 0.85 を ★ 初突破)**。CP-3 でカズヤ判断 = Step D スキップ、残課題 4 軸分離で個別根本治療へ。 |
| 2026-05-09 | F-jp-coverage-tune | (試運転なし、独立 23 件精度測定 + 1 回チューニング) | `verify_two_stage()` 二段階クエリ生成を独立 23 件で精度測定。**post-tuning verdict=fail**: Recall covered **42.11%** / Precision blind **26.67%** / F1 **0.5926** / Tier 一致率 **62.50%** / Stream accuracy **27.27%**。**Grounding API 構造的限界が明確化** (1 クエリ 5-10 chunk + WL 外ドメインで上位埋まる + 0 URL 返却ケース複数)。 |
| 2026-05-08 | F-task-e-finalize | (試運転なし) | Task E カズヤレビュー (25 件) 完了、全件 LLM 推定値そのまま採用。4 つの運用原則確立 + 1 つの構造的問題 (試運転/golden_set 重複 25→23 件) 発覚。 |
| 2026-05-08 | F-extension-followup | (試運転なし) | extension クラウドレビュー指摘 3 件反映: stream_3=0 件 (c) サンプル選定バイアス + sontaku_signals type 分布バイアス + finalize_annotations.py 最小修正。 |
| 2026-05-08 | F-particular-angle-redesign-extension | (試運転なし、docs + scripts + LLM 推定) | 系統名 1/1.5/2 → 1/2/3 リネーム + sontaku_signals 25 件 LLM 推定。クラウド誤り 9 記録 + Step 3-4 改良 + MECE 判別基準明示。 |
| 2026-05-08 | F-particular-angle-redesign | (試運転なし) | 25 件 4 分類化 LLM 再判定: 系統 1=4 (16%) / 系統 2=20 (80%) / 系統 3=0 (0%) / out_of_scope=1 (4%)。 |
| 2026-05-07 | F-particular-angle-design | (試運転なし) | LLM で 25 件特定角度抽出: extraction_confidence high=22 / medium=3、stream 3 分類版推定。 |
| 2026-05-07 | F-trial-run-post-fix | 1/3 動画化 (Slot-1 のみ) + 3 articles | 修正後 F-13.B が本番で機能 (excluded_count 1/10/3 非ゼロでドメイン抽出層が稼働)、3 Slot 全 has_jp_coverage=False、防衛機構 5 層全機能、WebSearch 後追いで Slot-1 (Insider trading) は Tier 1-2 報道済み = Recall miss、過去 7-K 動画 3 件のうち 2 件が stream_2_candidate パターン |

## 4. Hydrangea コンセプト防衛機構の現状 (5 層)

| 層 | バッチ | 場所 | 役割 | 状態 |
|---|---|---|---|---|
| F-1 | F-1 / F-1.5 | EditorialMissionFilter | 編集ミッション適合度で score 算出 (>= 45.0 で通過) | ✅ 稼働中 (F-trial-run-post-tune 試運転で 20/304 通過確認、selected 3 Slot scores: 86/77/83) |
| F-2 | F-2 / F-5 | FlagshipGate (Hydrangea コンセプト整合) | 海外発の重要ニュースを優先 | ✅ 稼働中 (F-trial-run-post-tune 試運転で Blocked 0 件、全 20 件通過) |
| F-13.B | F-13.B / F-jp-coverage-improve / F-trial-run-post-fix / F-jp-coverage-tune / F-jp-coverage-tune-followup / **F-trial-run-post-tune** | JpCoverageVerifier (rescue 完全廃止 + Web 検証 + ドメイン抽出レイヤー + verify_two_stage 二段階クエリ生成 + WL マッチング階層判定化 + WL 拡張 30 ドメイン) | JP 報道カバレッジを 30 ドメイン WL で検証 | ✅ **構造的不具合修正完了** + 本番動作確認済み + **★ F-trial-run-post-tune で WL 拡張本番効果確認** (3 Slot 全件 has_jp_coverage=True、F-trial-run-post-fix 0/3 → 3/3 完全反転)。**ただし matched_urls がベアドメインのみ問題が顕在化** (誤陽性リスク)、独立検証が次バッチ案件として残課題化。production main.py は legacy verify() (broad-only) のみ呼び出し、verify_two_stage 系統 1/2/3 機械判別は本番未配線 |
| F-5 | F-5 | FlagshipGate 下流救済 | 上流ガードを通過した候補の最終整合 | ✅ 稼働中 (F-trial-run-post-tune 試運転で 1 件発火 = cls-da0a74aa712d、ただし Top-3 選定外で「救済しても下流選定で適切に評価」が正常動作確認) |
| **F-13 (隠れ層)** | F-13 / F-doc-cleanup | script_writer.py:951-985 quality_floor_miss bypass | analysis_result 等が成立すれば appraisal の [抑制] を上書き | ✅ 稼働中 (F-trial-run-post-tune 試運転で 1 件発火 = Slot-1、editorial_mission_score=86.0 + analysis_result=none で bypass = 旧ルート救済、新ルート `generate_script_with_analysis` 未配線の証拠) |

## 5. 触ってよい / 触ってはいけない領域マップ

### 触ってよい領域
- `configs/prompts/` 配下全般 (主戦場: `configs/prompts/analysis/geo_lens/`)
- `docs/` 配下全般 (CURRENT_STATE / DISCUSSION_NOTES / DECISION_LOG /
  FUTURE_WORK / BATCH_PROTOCOL / **PARTICULAR_ANGLE_DEFINITION** 等の更新)
- `tests/` 配下に新規テストファイル追加 (既存ファイルは原則変更しない、
  ただし API contract 整合化に伴うフィクスチャ更新 + 既存ファイルへの新規
  テストクラス追加は許容)
- `scripts/` 配下に新規スクリプト追加
- `src/triage/` に新規ファイル追加 (例: `jp_coverage_verifier.py`)
- `src/generation/script_writer.py` の **新ルート**
  (`generate_script_with_analysis` / `ScriptWithAnalysisDraft` /
  `_AXIS_TO_PATTERN_HINT` / `_ANALYSIS_DURATION_PROFILES` / `article_text` 等)
- `src/generation/script_writer.py` の `_CHAR_BOUNDS` 等の定数 (最小改変なら許容)
- `src/main.py` (不変原則対象外、★ verify_two_stage 本番配線判断バッチで改修対象)

### 触ってはいけない領域
- `src/generation/article_writer.py` (不変原則 1)
- `src/generation/script_writer.py` の **既存ルート**
  (`write_script` / `_PROMPT_TEMPLATE` / `_build_script_from_llm`) (不変原則 2)
- `src/triage/` の既存ファイル (不変原則 3、F-jp-coverage-improve / F-jp-coverage-tune /
  F-jp-coverage-tune-followup で例外条件適用済)
- `src/analysis/` 配下全般 (不変原則 4、F-12-B-2 / particular_angle_metadata 配線判断バッチで例外条項追加検討)
- 既存テスト (不変原則 5、baseline 1390 passed 維持 — ただしフィクスチャの
  API contract 整合化 + 既存テストファイルへの新規テストクラス追加は許容)

## 6. 不変原則 5 つ (リマインダ、正本: BATCH_PROTOCOL.md)

1. **`src/generation/article_writer.py` 一切変更不可**
2. **`src/generation/script_writer.py` の既存ルート (`write_script` /
   `_PROMPT_TEMPLATE` / `_build_script_from_llm`) は変更不可**。
3. **`src/triage/` の既存ファイル変更不可**。新規追加は OK。
   **例外条件 (F-jp-coverage-improve / 2026-05-07 で構造化)**:
   実装バグ修正 + 設計変更ではない + DECISION_LOG 明記 + Hydrangea ミッション
   中核機構ならカズヤ承認必須、の 4 条件全て満たす場合のみ例外適用可。
4. **`src/analysis/` 変更不可** (F-12-B-2 axis 多様化 / particular_angle_metadata 配線判断着手時に例外条項追加検討)
5. **既存テスト破壊しない** (baseline 1390 passed)

## 7. カズヤの直近フィードバック要点

- **「中間が良い」** — シニカル一辺倒でも生活実感一辺倒でもなく、両立
  (F-12-B-1-extension で punchline 定義を「シニカル × 具体着地」両立に)
- **「考え方で制御」** — NG リスト方式は廃止、原則ベースのプロンプト
- **「対症療法じゃなくて根本治療」** — 仕組みで再発防止、★ F-trial-run-post-tune
  (2026-05-11) で「動くものを壊さない」哲学 + 「観察と記録に集中するバッチも
  根本治療の一部」運用が実証 = src/ tests/ configs/ scripts/ 0 変更、docs/ のみ
  更新で完結。本バッチで顕在化した 4 件の残課題 (WL ヒット品質検証 + 本番配線
  判断 3 件) は個別バッチに分離し、1 バッチで欲張らない原則を維持
- **「重複しないように定義すればよくね?」** — 系統 1 / 系統 2 の判定対象を
  『特定角度』に限定すれば重複は構造的に消える (2026-05-07 議論結論)
- **「一部報道だけど観点不足っていう 1.5 分類儲けてもいいのかもしれない」** — 系統 1
  内部の混在解決策をカズヤが提案 → 4 分類化として実装
- **「言い回しを個別ルールで指定するのは避けたい」 / 「LLM の知性に期待する」** —
  台本表現は強制ルールではなく particular_angle_metadata 構造を渡して LLM が自律
  選択する設計
- **「いまは各論をコントロールしたくない」 / 「分析フェーズの LLM に期待」** —
  クラウド誤り 9 (各論コントロールへの誘惑) として記録、再発防止策確立
- **「忖度・報道規制・黙殺の構造を系統判定に組み込むと MECE が崩れる」** —
  sontaku_signals を別軸メタデータとして独立化
- **「Hydrangea のメディアとしてのリスクは嘘をつくこと」 / 「取りこぼした
  ほうが安全じゃない?」** (F-task-e-finalize / 2026-05-08 記録) —
  sontaku_signals.level の判定方針として「嘘をつかない設計、疑わしきは低く見積もる」
- **「Hydrangea のポイントの一つに LLM の膨大な知識による評価とか判定があるから、
  一定 LLM を信用したいから」** (F-task-e-finalize / 2026-05-08 記録、★ Hydrangea
  コアバリュー) — 「LLM の知性に委ねる」原則
- **「これは明確に忖度だと思う。暴くべき観点を暴いていない」** (F-task-e-finalize /
  2026-05-08 記録) — 「観点の選択的欠落 = 忖度」判定軸を確立
- **F-jp-coverage-tune CP-1/CP-2 中間チェックポイント方式** (F-jp-coverage-tune /
  2026-05-09 確立) — 長時間実行バッチで中間レポート提出 → カズヤ承認後に次 Step
  着手。チューニング試行は **1 回のみ** = 無制限自走禁止
- **「負の遺産残さないように」** — 不整合・乖離を早期解消
- **「カズヤの手作業はバッチプロンプトのコピペ 1 回のみ」**
- **「過剰拡張性の罠」** — 「将来のため」の抽象化前倒しは見送る
- **「動くものを壊さない」** — F-jp-coverage-improve で構造的不具合修正後も
  本番試運転 + 過去判定後追い (F-trial-run-post-fix) を必須段階として組み込み、
  ★ F-trial-run-post-tune (2026-05-11) で「観察と記録に集中する性格のバッチも
  根本治療の一部」運用が確立 = src/ tests/ configs/ scripts/ 0 変更で完結
- **「整合の説明であって検証ではない」** (F-extension-followup / 2026-05-08
  記録、★ サンプル設計バイアス検出原則)

## 8. 関連ドキュメントへの導線

- 過去の決定の経緯 → `docs/DECISION_LOG.md`
- 残課題リスト → `docs/FUTURE_WORK.md`
- 議論中の未確定メモ → `docs/DISCUSSION_NOTES.md`
- バッチ運用ルール → `docs/BATCH_PROTOCOL.md` (不変原則例外条件 + Project Knowledge 運用ルール含む)
- アーキテクチャ全体像 → `docs/ARCHITECTURE.md`
- 技術的負債リスト → `docs/TECH_DEBT.md`
- リファクタ計画 (歴史的記録) → `docs/REFACTORING_PLAN.md`
- 編集ミッションフィルタ設計 (F-13 隠れ層含む) → `docs/EDITORIAL_MISSION_FILTER_DESIGN.md`
- ★ **「特定角度」概念正典 (4 分類版、命名 1/2/3) → `docs/PARTICULAR_ANGLE_DEFINITION.md`**
- Claude Code 振る舞い指針 → `CLAUDE.md`

---

*このドキュメントは F-state-protocol (2026-05-01) で導入。
 Claude Code がバッチ完了時に全置換更新する運用 (BATCH_PROTOCOL.md Task 5 参照)。
 F-trial-run-post-tune (2026-05-11) は **ゲート完了後の 8 つ目のバッチ**で、
 F-jp-coverage-tune-followup マージ後の本番試運転 + 防衛機構 5 層監査 + 拾われた
 Slot の台本品質確認 + 第一作題材ランク付け (機械 4 軸 + カズヤ主観 1 軸空欄) を実施。
 試運転 3 Slot 全件 has_jp_coverage=True (afpbb x2 / nippon x1 = WL 拡張ドメイン
 全件ヒット、F-trial-run-post-fix から完全反転)。**機械スコア 1 位 = Slot-1
 cls-6889e9e1c7ac (10pt) で第一作最有力候補確定** (editorial_mission_score=86.0、
 Hydrangea ど真ん中、唯一 video_payload 生成済み)。`src/` `tests/` `configs/`
 `scripts/` 0 変更、`docs/` のみ更新で完結、baseline 1390 passed 維持。
 重要観察事項 4 件残課題化: (1) F-13.B WL ヒット品質の独立検証 (matched_urls
 ベアドメインのみで誤陽性リスク)、(2) verify_two_stage 本番配線判断
 (production-pipeline と docs 概念整理の乖離解消)、(3) particular_angle_metadata
 + sontaku_signals 本番配線判断 (新ルート起動条件)、(4) F-stream-2-filter-design
 責務範囲再評価 (本番運用視点反映)。次バッチ候補 = Phase A.5-3b 第一作起案
 (Slot-1 cls-6889e9e1c7ac、機械スコア 10pt、★ 最有力候補昇格) + 並走 4 件の
 残課題バッチ群。
 ★ Project Knowledge 最新化リマインダ: 本バッチ完了で第一作題材候補が確定 +
 production-pipeline と docs 概念整理の乖離が明示化されたため、新チャット移行前
 にカズヤが手動で claude.ai の Project Knowledge を **必須最新化** することを推奨
 (BATCH_PROTOCOL の Project Knowledge 運用ルールに従う)。
 過去の経緯は DECISION_LOG.md / FUTURE_WORK.md / DISCUSSION_NOTES.md を参照。*
