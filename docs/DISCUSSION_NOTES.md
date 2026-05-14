# Hydrangea — Discussion Notes (DISCUSSION_NOTES.md)

最終更新: 2026-05-14 (F-wl-hit-quality-audit 完了、F-trial-run-post-tune で観察された
matched_urls ベアドメイン問題を独立検証、★ Task D Grounding chunk dump で **LLM judgement
bypass 問題** が決定的に判明 = Gemini LLM が response_text で『該当しない』と明示判定して
いるのに F-13.B は WL マッチだけで True を返している、根本治療 Option (i) LLM response_text
判定抽出を別バッチ案件として記録、4-A 新規エントリ追加 = 「2026-05-14: LLM judgement bypass
問題」、4-B 既存再評価 = 「2026-05-11: F-13.B WL ヒット品質問題」を Active → 部分的解消
(構造的理解完了、Option (i) 実装は別バッチ) に更新)

> このドキュメントは「議論中だがまだ確定していないメモ」を蓄積する場所。
> 各バッチ完了時に Claude Code が再評価し、以下のいずれかに振り分ける:
>   - **確定済み** → DECISION_LOG.md に昇格 (時系列エントリとして追加)
>   - **タスク化** → FUTURE_WORK.md に昇格 (緊急度別に追加)
>   - **アーカイブ** → 30 日以上古い + 状況変化で意味を失ったものを下のセクションに移動
>
> 各エントリは「日付 / トピック / 内容 / 出典 / ステータス」の 5 項目で記載する。

---

## 未分類 (Active)

### 2026-05-14: F-13.B LLM judgement bypass 問題 — Gemini LLM が「該当しない」と明示判定しているのに F-13.B は WL マッチだけで True を返している (F-wl-hit-quality-audit Task D で決定的発見)

**背景**:
F-wl-hit-quality-audit (2026-05-14) の Task D で `scripts/dump_grounding_chunks.py` を新規
作成し、Slot-2 cls-1a38c0ca8c99 (BBC Gaza documentary BAFTA、Suspect FP 確定) について
Gemini Grounding API を呼び chunk 生データを JSON 保存した結果、**Gemini LLM 自身が
response_text で『指定されたニュース「BBCが放送を取りやめたガザに関するドキュメンタリーが
受賞し、映画製作者がBBCを非難した」という2026年5月上旬の出来事とは異なる内容で、かつ
日付も異なります』と明示的に「該当しない」判定** をしている事実が確認された。

にもかかわらず、F-13.B `_search_with_grounding` 現実装は LLM の response_text 判定を完全に
無視し、chunk のドメイン抽出 + WL 階層マッチのみで True/False を決めている (= afpbb.com
chunk 2 件存在で True 返却)。

**chunk.web 構造の確認 (Slot-2 dump、8 chunks)**:
- 全 8 件で `web_uri` = Vertex AI redirect URL のみ (decode 不可)
- 全 8 件で `web_title` = ドメイン名のみ (article path もページタイトルも含まれない)
- 全 8 件で `web_domain` 属性 = None (SDK 戦略 1 未実装)
- 抽出戦略は全件 strategy_2 (title フィールド経由)

**仮説の切り分け**:
| 仮説 | 判定 |
|---|---|
| (a) SDK バグ説 (chunk.web.uri が redirect URL のみ) | ✅ 部分確認 (仕様) |
| (b) Grounding API 仕様説 (article path は元から返されない) | ✅ 確認 |
| (c) クエリ品質説 | ❌ 主因ではない (LLM は正しく判定) |
| **(d) ★ LLM judgement bypass 説** | ✅★ 確認 = **最大の改善余地** |

**Hydrangea カズヤ哲学との整合性問題**:
F-task-e-finalize (2026-05-08) で確立された「Hydrangea のポイントの一つに LLM の膨大な
知識による評価とか判定があるから、一定 LLM を信用したいから」原則および クラウド誤り 9
(各論コントロールへの誘惑、2026-05-08) と本発見が直接呼応。現実装は LLM の知性を完全に
bypass する設計 = カズヤ哲学に反する。

**論点**:
- **(i) ★★★ LLM response_text 判定抽出 (推奨)**: プロンプト改修 + response 解釈で
  LLM 判定を verify() に反映 (= LLM 判定が WL マッチを上書き)。工数 4-8h、Recall -5〜
  -10pp / Precision +20〜+40pp 想定
- (ii) WL マッチ信頼度フラグ追加 → Task D 発見で無効化 (article path 取得不能)
- (iii) 高信頼度マッチのみで True → 同上、無効化
- (iv) 別 API (Google Custom Search) 移行 → 工数 1-2 日、F-jp-coverage-tune-followup-2
  統合候補
- (v) Grounding クエリ品質改善 → (i) の補助として併用可能

**Hydrangea コアミッションへの影響**:
- 本問題は perspective_gap (系統 2、= 特定角度の日本未報道) の機械検出を構造的に妨げる
- 試運転 + golden サンプリングで 3/8 = 37.5% のケースで topic-family 一致 / specific event
  不一致パターンが観察 → Option (i) 実装で大幅改善可能性
- F-13.B WL ヒット品質問題 (前エントリ) の根本原因として確定

**出典**:
- F-wl-hit-quality-audit Task D 結果
  (`docs/runs/F-wl-hit-quality-audit/grounding_chunk_raw_dump.json`)
- 構造的分析 (`docs/runs/F-wl-hit-quality-audit/structural_analysis.{json,md}`)
- 統合 REPORT (`docs/runs/F-wl-hit-quality-audit/REPORT.md`)

**ステータス**: `Active` (FUTURE_WORK 緊急度 高に `F-jp-coverage-llm-judgement-extraction`
新規追加済み。Phase A.5-3b 第一作着手判断と密接に関連 = Slot-1 cls-6889e9e1c7ac の
perspective_gap 確定後、Option (i) 実装で WL ヒット品質根本治療 → 再試運転 → 第一作着手の
フローが推奨)

---

### 2026-05-11: F-13.B WL ヒット品質問題 — matched_urls がベアドメインのみで記事レベル一致が不明 (F-trial-run-post-tune で観察、F-wl-hit-quality-audit で部分的解消)

**2026-05-14 ステータス更新**: F-wl-hit-quality-audit (2026-05-14) で本問題を独立検証した
結果、**構造的理解は完了** (= 根本原因は (d) LLM judgement bypass 問題、別エントリ参照)、
ただし **改善案 Option (i) の実装は別バッチ案件 (`F-jp-coverage-llm-judgement-extraction`)
として記録**。本エントリは Active → **部分的解消 (構造的理解完了、根本治療実装は別バッチ)**
に更新。

**F-wl-hit-quality-audit 検証結果サマリー**:
1. 試運転 3 Slot 検証: Slot-1 = TP (Israel 9,600 Detainees は afpbb で報道済み)、Slot-2 =
   Suspect FP (BBC Gaza documentary BAFTA は afpbb で別事象のみ)、Slot-3 = Topic-Level TP
   (Iran 降伏フレーミングは nippon.com で類似トピック報道、specific 主張不在)
2. ゴールデンセット TP 17 件から seed=42 で 5 件サンプリング: TP=1、Topic-Level TP=3、
   Specific Event Suspect FP=1 (cls-a4132ec7d949)
3. ★ Slot-2 Grounding chunk dump で **LLM 自身が「該当しない」判定しているのに F-13.B は
   WL マッチだけで True を返している** ことが決定的に判明 → 根本原因 (d) を確定

**F-jp-coverage-tune-followup Step C メトリクスの再解釈**:
- F1 covered 0.8718 / Recall covered 89.47% は **broader topic-family level の値**
- specific event (= particular_angle) level では下振れの可能性
- REPORT v2 化は別バッチ (F-wl-hit-quality-audit CP カズヤ判断で本バッチ記録のみと決定)

---

### 2026-05-11: F-13.B WL ヒット品質問題 — matched_urls がベアドメインのみで記事レベル一致が不明 (F-trial-run-post-tune で観察)

**背景**:
F-trial-run-post-tune 本番試運転 (2026-05-11) で `JpCoverageVerifier.verify()`
が 3 Slot 全件で has_jp_coverage=True を返却 (afpbb x2, nippon x1) したが、
`jp_coverage_cache` に保存された `matched_urls` が全件で **ベアドメイン
(`https://afpbb.com` / `https://nippon.com`)** のみ、記事レベルの URL
(article path) が取得されていない:

```
cls-6889e9e1c7ac (Israel Prison Abuses): matched_urls=["https://afpbb.com"], tier_2
cls-1a38c0ca8c99 (BBC Gaza documentary):  matched_urls=["https://afpbb.com"], tier_2
cls-03892eab2072 (Tehran/Iran surrender): matched_urls=["https://nippon.com"], tier_4
```

**根本原因 (推測)**:
- F-jp-coverage-improve (2026-05-07) のドメイン抽出層 (`_extract_domain_from_chunk`)
  には 2 戦略あり: 戦略 1 (chunk.web.domain、SDK が空値を返すケース多い) → 戦略 2
  (chunk.web.title でドメイン形式の文字列を識別、`afpbb.com` 等を識別)
- 戦略 2 で `afpbb.com` を識別した時、`https://{domain}` 形式で WL マッチングに
  供給するため、結果として matched_urls にはベアドメインしか入らない
- F-jp-coverage-tune-followup (2026-05-09) で導入された `_domain_matches_hierarchy`
  はドメイン文字列同士の階層判定で、article path は不要

**重要な懸念 (誤陽性のリスク)**:
- 「`afpbb.com` が当該事象 (Israel Prison Abuses) を実際に報道している」ことを
  Grounding API は保証しない
- Grounding がトピック関連で `afpbb.com` を chunk として返した事実までしか保証
  されない
- F-jp-coverage-tune-followup Step C 測定 (Recall covered 89.47% / Precision
  blind 33.33%) も同じ抽出経路を経るため、ゴールデンセット 23 件評価でも同等の
  誤陽性懸念がある可能性

**論点**:
- (a) **WebSearch 後追い検証**: Anthropic web search で本試運転 3 Slot +
  ゴールデンセット 23 件の matched_domains が実際に当該事象を報道しているか
  手作業 + WebSearch で確認 (F-trial-run-post-fix の past_videos_audit 構造を
  踏襲)
- (b) **Grounding chunk の生データダンプ**: `_search_with_grounding` /
  `_search_with_grounding_two_stage` の chunk.web 配列を全件 JSON 保存して目視
  確認、article path 取得失敗の根本原因 (SDK 不具合 / API 仕様 / Grounding 検索
  品質) を切り分け
- (c) **Grounding 検索クエリ品質改善**: 英語タイトル → 日本語キーワード抽出 +
  article path 取得を促すクエリ設計 (`記事のタイトル + URL も含めて返してください`
  系の指示)
- (d) **WebSearch クローラの制約再確認**: F-trial-run-post-fix audit_caveat で
  「Anthropic WebSearch は asahi.com / yomiuri.co.jp 等の主要紙への直接クロール
  がブロックされる仕様」が記録されており、検証側にも制約あり

**Hydrangea コアミッションへの影響**:
- もし誤陽性が支配的なら、F-jp-coverage-tune-followup の Recall covered 89.47%
  の信頼性が下がる
- production-pipeline で全 Slot が divergence ルートに進行する現象も「真の
  blind_spot が誤って divergence に流れている可能性」を含む
- Phase A.5-3b 第一作着手判断の前に独立検証が望ましい

**出典**:
- F-trial-run-post-tune 試運転結果
  (`docs/runs/F-trial-run-post-tune/trial_run_log.json` + `f13b_output_analysis.json`)
- `jp_coverage_cache` 保存内容 (`SELECT matched_urls FROM jp_coverage_cache`)

**ステータス**: `Active` (FUTURE_WORK 緊急度 高に「F-13.B WL ヒット品質の独立
検証」エントリを新規追加、Phase A.5-3b 第一作着手判断と同時 or 直前で実施想定。
独立検証で誤陽性が支配的と判明した場合は F-jp-coverage-tune-followup REPORT を
v2 に更新 + Recall covered 89.47% の信頼性を再評価する必要が出る)

---

### 2026-05-11: production-pipeline と docs 概念整理の乖離 — verify_two_stage / particular_angle_metadata / sontaku_signals 全て本番未配線 (F-trial-run-post-tune で観察)

**背景**:
Phase A.5-3a-verify ゲート完了後の連続バッチ (F-particular-angle-design /
-redesign / -extension / -followup / F-task-e-finalize / F-jp-coverage-tune /
F-jp-coverage-tune-followup) で「特定角度」概念正典化 + 4 分類化 (系統 1/2/3)
+ sontaku_signals 別軸メタデータ独立化 + Step 3-4 改良 + MECE 判別基準明示 +
verify_two_stage 二段階クエリ生成実装 + WL マッチング階層判定化 + WL 拡張
30 ドメイン化が進んだ。docs 上では `docs/PARTICULAR_ANGLE_DEFINITION.md`
セクション 3.7 で台本表現方向性も正典化済み。

しかし F-trial-run-post-tune (2026-05-11) で実施した production 試運転で:

- **`src/main.py:3187` は legacy `verify()` (broad-only) のみ呼び出し**で、
  `verify_two_stage()` 系統 1/2/3 機械判別は本番未配線
- **`particular_angle_metadata` は `src/` 配下 grep で 0 件**、本番未配線
- **`sontaku_signals` も `src/` 配下 grep で 0 件**、本番未配線
- Slot-1 (cls-6889e9e1c7ac、editorial_mission_score=86.0、Hydrangea ど真ん中)
  で `analysis_result=null` + F-13 隠れ層 quality_floor_miss bypass 発火 = 新ルート
  `generate_script_with_analysis` 未起動、旧ルートで台本生成

これは「対症療法じゃなく根本治療」原則を踏襲しつつ概念設計を docs 上で先に
正典化する戦略 (= F-particular-angle-design 系列の連続バッチ) の結果として
理解できるが、本番運用への配線は別バッチ案件として残課題化されたまま。

**論点**:
- (a) **verify_two_stage 本番配線判断**: `src/main.py` を改修して
  `verify_two_stage()` を呼び出すように切り替え、`particular_angle` 引数を
  `analysis_result` から導出する変換層を実装。`TwoStageVerifyResult.stream`
  値を `final_routing` ロジックに反映 (stream_1_silence_gap → blind_spot_global,
  stream_2_perspective_gap → divergence pattern + 系統 2 ラベル, stream_3_candidate
  → divergence pattern + 系統 3 ラベル, unknown → 既存挙動)
- (b) **particular_angle_metadata 配線**: `src/shared/models.py` に
  `ParticularAngleMetadata` Pydantic クラスを追加、`AnalysisResult` に optional
  フィールド組み込み。`src/analysis/particular_angle_extractor.py` を新規追加
  (`scripts/extract_particular_angle.py` のロジック移植、不変原則 4 例外条件要)
- (c) **sontaku_signals 配線**: `SontakuSignals` Pydantic クラス + 抽出
  ロジック追加、F-1 EditorialMissionFilter (動画化価値) + F-stream-2-filter-design
  (解説価値) で参照する設計
- (d) **`generate_script_with_analysis` 新ルートへの引数追加**: 新メタデータを
  受け取る引数追加 + `configs/prompts/analysis/geo_lens/script_with_analysis.md`
  プロンプト改修 (LLM の自律判断に委ねる設計、クラウド誤り 9 各論コントロール
  回避)

**Hydrangea コアミッションへの影響**:
- 現状の production-pipeline は **Phase A.5-3a-verify gate 完了前 (2026-05-07
  以前) の概念構造で稼働**
- gate 完了後の概念整理 (4 分類化 + sontaku_signals 独立化 + 二段階クエリ生成)
  は **本番運用に未反映**
- F-stream-2-filter-design 着手時は本配線判断が前提条件になる可能性が高い
- 「動くものを壊さない」哲学と「概念正典化先行 + 本番配線は段階的」戦略の整合
  を維持しつつ、配線タイミングは Phase A.5-3b 第一作着手判断と同時 or 並走で
  決定する必要

**運用ルール (運営者へのリマインダ)**:
- 新規バッチで `docs/PARTICULAR_ANGLE_DEFINITION.md` / `docs/CURRENT_STATE.md`
  「コアミッション 2 系統並立」セクションを参照する際は、本エントリで指摘した
  「docs 概念整理は最新だが本番未配線」点を念頭に置く
- 「production-pipeline の挙動 = docs 概念整理通り」と誤解しないように
  (= F-trial-run-post-tune で 3/3 Slot が divergence ルートに流れる現象は、
  単純な機械判別レイヤーの欠如によるもので、docs 設計と矛盾しない)

**出典**:
- F-trial-run-post-tune 試運転結果
  (`docs/runs/F-trial-run-post-tune/REPORT.md` + 5 件の json + 2 件の md)
- `src/main.py:3170-3220` (F-13.B 呼び出し箇所、legacy verify() のみ使用)
- `src/` 配下 grep 結果 (particular_angle_metadata / sontaku_signals 0 件)

**ステータス**: `Active` (FUTURE_WORK 緊急度 高に 3 件 + 1 件のエントリを新規
追加: (1) verify_two_stage 本番配線判断、(2) particular_angle_metadata +
sontaku_signals 本番配線判断、(3) F-stream-2-filter-design 責務範囲再評価
(本番運用視点反映)、(4) F-13.B WL ヒット品質の独立検証 — 関連性が高いため
1 つのバッチ群として並走進行が望ましい)

---

### 2026-05-09: Grounding API の構造的限界 — 主因 (WL マッチング欠陥 + WL 漏れ) は F-jp-coverage-tune-followup で解消、副因 (1 クエリ chunk 制限 + 政府系/研究機関偏重) のみ残存

**内容**:
F-jp-coverage-tune (2026-05-09) で `verify_two_stage` 二段階クエリ生成を独立
23 件で精度測定した結果、verdict=fail (Recall covered 42.11% / Precision blind
26.67% / F1 0.5926 / Tier 一致率 62.50%、(c) dateRestrict プロンプト埋め込み
除去で +10.53pp 改善後)。FN 13 件の broad 検索結果分析で、当初は **Grounding
API の構造的限界** が支配的な FN 要因として明確化されていたが、F-jp-coverage-tune-followup
(2026-05-09) で **本問題が 3 つの異なる原因に分解可能** であることが判明:

1. **WL マッチング欠陥** (★ 主因): WL `news.fnn.jp` 登録に対して Grounding が
   `fnn.jp` を返してきても WL マッチング側 (`domain in url_lower` substring
   match) がサブドメイン関係を別エントリ扱い → ✅ **F-jp-coverage-tune-followup
   Step A で解消** (`_domain_matches_hierarchy` 階層判定で吸収)
2. **WL 漏れ準大手** (★ 主因): `forbesjapan.com` / `nippon.com` / `afpbb.com`
   等が WL 未登録 → ✅ **F-jp-coverage-tune-followup Step B で解消** (3 ドメイン
   追加、判定 3 基準 = 発行元独立性 / 取材リソース / 大手認知度を満たす)
3. **Grounding API 仕様限界** (★ 副因のみ残存):
   - **1 クエリあたり 5-10 chunk しか返さない** (Gemini Grounding API 仕様)
   - **政府系・研究機関・アグリゲータ偏重**: covered_003 (米中関税協議) で
     jetro.go.jp / dir.co.jp / cistec.or.jp / livedoor.com 等が返却されるが
     日経・朝日等の主要メディアが上位に入らないケース
   - **論考型事象の構造的欠落**: blind_010 (Zionism crisis 論考) で日本主要
     メディアが取り上げていない事実上のもの (= Grounding 仕様限界ではなく
     報道側構造の問題)
   - **0 URL 返却ケースは F-jp-coverage-tune-followup でほぼ消失** (broad query
     からの dateRestrict 除去 + WL 整備で大半救済)

**F-jp-coverage-tune-followup Step C 再測定結果**:
- Recall covered: 42.11% → **89.47%** (+47.36pp、threshold 90% に **0.53pp
  不足**)
- F1 covered: 0.5926 → **0.8718** で threshold 0.85 を **初突破** ✓
- 残 FN 2 件: blind_010 (論考型、構造的欠落) + covered_003 (政府系/研究機関
  偏重、多クエリ並列発行で救済可能性高)

**残存副因の対応案 (F-jp-coverage-tune-followup-2 の検討候補)**:
- (p) **Grounding API 複数クエリ並列発行 + 結果統合**: covered_003 救済狙い、
  Recall 90% 突破見込み (94.7%+ 推測)。副作用リスク = Precision blind / Tier
  一致率がさらに退行する可能性 (broader matching で FP 増加)。
- (q) **検索 API 変更検討**: Google Custom Search / Bing Search 等への移行。
  dateRestrict / num=10 / siteSearch 等のパラメータが API レベルで supported
  される利点。検証コスト + コスト見積もり要。

**出典**:
- F-jp-coverage-tune バッチプロンプト + 完了レポート (2026-05-09)
- F-jp-coverage-tune-followup REPORT
  (`docs/runs/F-jp-coverage-tune-followup/REPORT.md`)
- F-jp-coverage-tune-followup Step C measurement
  (`docs/runs/F-jp-coverage-tune-followup/measurement_result_step_c.json`)
- `docs/runs/F-jp-coverage-tune/measurement_result.json` (post-tuning) +
  `measurement_result_pre_tuning.json` (Step 4 前ベースライン)
- 23 件の per-event ログ (両バッチ)
- F-trial-run-post-fix (2026-05-07) DISCUSSION_NOTES 関連エントリ

**ステータス**: **Partially Resolved** (主因 = WL マッチング欠陥 + WL 漏れ準大手
は F-jp-coverage-tune-followup で解消、副因 = 1 クエリ chunk 制限 + 政府系/研究
機関偏重 + 論考型構造欠落 のみ残存。残存副因は F-jp-coverage-tune-followup-2
で対応案 (p) 多クエリ並列発行を ★ カズヤ判断後に検討、Phase A.5-3b 第二作の
サンプル拡充も並行)。

**2026-05-11 追記 (F-trial-run-post-tune での観察)**:
- 本番試運転 3 Slot 全件で has_jp_coverage=True (afpbb x2 + nippon x1 でヒット)、
  excluded URLs は Slot-1 youtube 1 件のみ = **主因解消の本番証拠を確認**
- F-trial-run-post-fix (2026-05-07、構造的不具合修正前直後) では 0/3、F-trial-run-post-tune
  (2026-05-11、WL 整備後) では 3/3 で完全反転 = WL 整備の本番影響は想定以上
- ただし **matched_urls がベアドメインのみ問題** (新規論点として別エントリ参照、
  F-trial-run-post-tune で発覚) があり、Recall covered 89.47% も誤陽性を含む
  可能性 → 独立検証が次バッチ案件として残課題化

---

### 2026-05-09: stream_3 過剰検出 — URL ドメインマッチが特定角度の粒度を区別できない定義レベルの限界 (F-jp-coverage-tune で観察)

**内容**:
F-jp-coverage-tune (2026-05-09) post-tuning 結果で、stream_2 truth 18 件中
**6 件が stream_3_candidate と誤判定** された。誤判定された 6 件
(blind_002 / blind_009 / covered_001 / covered_002 / covered_004 / covered_009)
は、いずれも angle 検索で WL ヒット (diamond.jp / yomiuri.co.jp /
newsweekjapan.jp / asahi.com) が発生したが、真値は「特定角度は未報道」。

**根本原因 (定義レベルの限界)**:
- LLM truth は「特定角度を扱った記事 ≠ 広範事件のついでに触れた記事」と
  **厳格に区別** している (例: `covered_002` = 米ロ首脳停戦の特定角度として
  「トランプがバイデン政権をバイパスして直接交渉、G7 合意に破壊的影響」を
  抽出 → 真値「日本では深掘り未報道」)。
- 一方 `verify_two_stage._match_whitelist` は **ドメインヒット粒度しか見ない**
  ため、yomiuri.co.jp の何らかの記事がヒットすれば「報道済み」確定。
- 結果: angle 検索は LLM 生成クエリで広範事件全般にもマッチする粒度になり、
  WL 大手ドメインが「広範事件のついで報道」をヒットして stream_3 と誤判定。

**Pre-tuning vs Post-tuning の比較**:
- Pre-tuning (dateRestrict プロンプト埋め込み有り): stream_3 過剰検出 3 件
- Post-tuning (dateRestrict プロンプト埋め込み除去): stream_3 過剰検出 6 件
- = dateRestrict 解除で angle 検索の recall も上がり、WL ヒット件数増加 → 過剰
  検出も増加。トレードオフが存在。

**F-jp-coverage-tune-followup (2026-05-09) で更に顕在化**:
- WL マッチング階層判定化 + WL 拡張 3 ドメイン (afpbb.com / forbesjapan.com /
  nippon.com) で angle 検索もマッチ範囲が拡大、stream_2 真値 18 件中
  **15 件が stream_3_candidate に誤分類** (Stream accuracy 27.27% → **9.09%**、
  -18.18pp)
- 同型問題が WL 整備の副作用として深刻化、本エントリで指摘した「URL マッチング
  の粒度限界」が定量的に拡大した形
- = 本バッチでは scopes 外 (broad-level の Recall/Precision/F1 改善が主目的)、
  F-stream-2-filter-design 責務範囲として残課題分離

**対応案 (F-jp-coverage-tune-followup の (s) 副次論点)**:
- angle 検索結果に対する **LLM 解説価値判定** の追加: 単なる WL マッチでは
  確定せず、その記事内容が `particular_angle.core_question` を実際に扱って
  いるか LLM が判定 (= F-stream-2-filter-design の責務範囲とも重なる、責務
  境界の整理が必要)
- WL マッチング後に記事タイトル / スニペットを取得して LLM で再評価する 2 段
  構成 (Grounding API は記事タイトルを返すので、それを再評価入力にできる)

**出典**:
- F-jp-coverage-tune バッチプロンプト + 完了レポート (2026-05-09)
- post-tuning 6 件の per-event ログ (`docs/runs/F-jp-coverage-tune/logs/`)

**ステータス**: `Active` (★ 本バッチスコープ外の定義レベル限界、F-jp-coverage-tune-followup
の (s) 副次論点 + F-stream-2-filter-design 責務境界整理時に再評価)。

**2026-05-11 追記 (F-trial-run-post-tune での観察)**:
- production main.py:3187 は legacy `verify()` (broad-only) のみ呼び出し、
  `verify_two_stage()` の二段階クエリ生成 + 系統 1/2/3 機械判別は **本番未配線**
- production-pipeline 上で stream 機械判別は稼働しないため、stream_3 過剰検出
  問題も本番では現れない (= ゴールデンセット 23 件精度測定特有の問題)
- ただし、F-trial-run-post-tune では production verify() = has_jp_coverage=True
  3/3 (= 全 Slot が divergence ルート進行) = Hydrangea ブランドメッセージ
  消滅問題が本番で顕在化 = stream_3 過剰検出と同根の「URL ドメインマッチが
  特定角度の粒度を区別できない」問題が、本番では『stream_3 過剰検出』ではなく
  『blind_spot_global 系統が消滅』として現れる
- F-stream-2-filter-design 責務範囲再評価で本観察を反映予定 (= verify_two_stage
  本番配線 + LLM 解説価値判定の追加、本番運用視点での組み込み)

---

### 2026-05-08: クラウド誤り 9 — 各論コントロールへの誘惑 (F-particular-angle-redesign-extension で記録)

**背景**:
F-particular-angle-redesign Task E カズヤレビュー過程で、Claude Code (本
チャット) およびクラウドが「視聴者ファースト 3 原則」「ジレンマ解説」
「忖度明示」「系統別台本表現ルール」等の **具体的指針** をプロンプトや
ドキュメントに追加したくなる傾向が観察された。動機は善意 (品質保証 +
Hydrangea ミッション徹底) だが、ルール累積で全体劣化を招く。

**カズヤ哲学** (2026-05-08):
> いまは各論をコントロールしたくない。記事の質の悪化避けたいから。これは、
> 分析フェーズの LLM に期待って感じ。

**害**:
- ルール累積で LLM の自由度が削られ、全体品質が下がる経験則 (F-12-B-1
  NG リスト方式廃止と同根)
- `article_writer.py` / `script_writer.py` の自由度阻害 (不変原則 1-2 と
  整合)
- LLM の知性発揮を抑制 (= Hydrangea のコアバリューのひとつ「LLM の知性に
  委ねる」と矛盾)

**正しい設計**:
- メタデータ構造の正典化 (例: `particular_angle_metadata` +
  `sontaku_signals`)
- LLM の知性に委ねる
- 4 軸メタデータ + sontaku_signals メタデータで動機担保
  (= 各論ルールではなく、構造データを LLM に渡す)

**実装事例** (本バッチで適用):
- 系統判定ルールに「ジレンマ解説」「忖度明示」を組み込む案 → 却下
- 代わりに `sontaku_signals` を別軸メタデータとして独立化
  (PARTICULAR_ANGLE_DEFINITION.md セクション 3.6)
- 台本表現は `particular_angle_metadata + sontaku_signals` を
  `script_writer.py` 新ルートに渡し、LLM が自律選択する設計を維持
  (PARTICULAR_ANGLE_DEFINITION.md セクション 3.7)

**運用ルール**:
- 台本表現や記事品質の課題を見つけたら、まず **メタデータ構造** で表現
  できないか検討する (= LLM に判断材料を増やす)
- ルール追加で対処したくなったら、本誤り 9 を思い出す
- カズヤ承認なしに「具体的言い回しルール」をプロンプトに加えない

**類似誤り**:
- クラウド誤り 1 (NG リスト・Tier 分類で機械制御提案、2026-05-02): 同根
- クラウド誤り 2 (「これを真似ろ」テンプレ過剰押し付け、2026-05-02): 同根
- クラウド誤り 6 (過剰拡張性の罠、2026-05-03): 別系統の善意の誤り

**ステータス**: `Resolved (記録済み + 防止策確立)` —
`CLAUDE.md` クラウド誤りセクションに本誤りを記載 (本バッチで導入)、
`docs/PARTICULAR_ANGLE_DEFINITION.md` セクション 3.7 で「LLM の知性に
委ねる」設計哲学を正典化。新チャット移行時の最重要参照対象。

**出典**:
- F-particular-angle-redesign Task E カズヤレビュー (2026-05-08)
- F-particular-angle-redesign-extension 完了 (2026-05-08)
- `CLAUDE.md` クラウド誤りセクション
- `docs/PARTICULAR_ANGLE_DEFINITION.md` セクション 3.6 / 3.7

### 2026-05-08: 系統 3 (旧系統 2) の典型パターン:日本-海外の評価対立 (カズヤ提起、F-particular-angle-redesign-extension で記録)

**背景**:
F-particular-angle-redesign Task E レビュー過程でカズヤから「系統 2
(現命名: 系統 3 framing_inversion) の典型パターンは日本-海外の **評価
対立**」と提起された。F-particular-angle-redesign で LLM 推定段階の
分布が stream_1=4 / stream_2=20 / stream_3=0 / out=1 となり、系統 3
候補が 0 件だった件への解釈軸の整理。

**カズヤの整理**:
- 系統 3 = 日本主要メディアと海外メディアが同じ特定角度について
  **評価が対立** している事象
- 「中立報道」(日本側が事実報道に留まり評価表明しない) は系統 3 ではなく
  系統 2 寄り (= 角度の不在)
- 評価対立の構造的背景には **忖度シグナル** (sontaku_signals) が必須
  (= 単発の専門解釈差は系統 3 ではなく out_of_scope)

**Phase A.5-3b 手動 PoC への影響**:
- 系統 3 の素材を手動 PoC に組み入れる場合は、評価対立 + 忖度シグナル
  level=high/medium のものを選定
- 系統 3 候補が極小 (0 件) 想定だが、F-jp-coverage-tune の二段階クエリ
  生成で系統 1 vs 系統 2 を機械判別した後、(報道済み) 候補に対して
  F-stream-2-filter-design が解釈差 + 忖度シグナルで系統 3 候補を救出
  する設計

**論点**:
- 25 件中 0 件の系統 3 を増やすには、入力 RSS 41 媒体の選定 +
  particular_angle 抽出プロンプトの改良で「日本でも語られる角度」を
  優先抽出する余地あり (将来検討)
- カズヤレビューで stream_3 に再分類されるケースが何件あるかで、
  F-stream-2-filter-design の責務スコープが再評価される

**ステータス**: `Active` (Phase A.5-3b 手動 PoC + F-stream-2-filter-design
着手時に参照する評価軸の整理)

**出典**:
- F-particular-angle-redesign Task E カズヤレビュー (2026-05-08)
- `docs/PARTICULAR_ANGLE_DEFINITION.md` セクション 3.5 (MECE 判別基準) +
  3.6 (sontaku_signals) で正典化

### 2026-05-08: 4 分類化で stream_3 = 0 件 / stream_2 = 20 件 という想定外分布 — LLM 集約バイアスか必然か (F-particular-angle-redesign で観察、★ 2026-05-08 命名 1/2/3 に整理)

**背景**:
F-particular-angle-redesign (2026-05-08) で 25 件を 4 分類版で LLM 再分類した結果、
LLM 推定段階で **stream_2 = 0 件** (想定 13 件) / **stream_1_5 = 20 件** (想定 5 件)
という想定外分布が観測された。3 分類版で stream_2 だった 13 件全て + stream_1 だった
7 件が新分類で stream_1_5 に集約された。

**LLM の reasoning は技術的に整合**:
- covered_002 (米ロ停戦): 「広範事件であるトランプ・プーチン接触は日本でも報道済みだが、
  既存 G7 合意を破壊するという特定角度の構造的影響は日本主要メディアで深掘り未報道」
- blind_007 (Putin ヨット): 「広範事件であるロシア大富豪ヨットのホルムズ通過自体が
  日本で未報道、特定角度 (制裁網無効化の構造分析) も未報道 → 両方未報道で stream_1」

**論点**:
(a) **LLM 集約バイアス説**: LLM は「特定角度の解釈差 (stream_2) を識別する」より
「特定角度の不在 (stream_1_5) を識別する」方が易しいため、迷ったら stream_1_5 を選ぶ
傾向。プロンプト改善で stream_2 識別を強化する余地あり。

(b) **必然的帰結説**: 海外メディアの特定角度 (例: MEE オピニオン記事の構造分析) は、
その視点自体が日本主要メディアで報道されていないことが多い。同じ視点を日本メディアが
取り上げて、かつ異なる解釈で論じるケース (= 厳密な stream_2) は実態として稀。3 分類版
の stream_2 = 「広範事件レベルでの解釈差」だったため数が多く見えたが、4 分類化で正しく
『特定角度レベル』に絞ると 0 になるのはむしろ正しい構造化。

(c) **サンプル選定バイアス説 (★ 前チャットでカズヤ提起、F-extension-followup で
追記)**: 25 件のサンプルは golden_set 19 件 + 試運転 6 件で、大半が「海外メディア
独自視点 (= 系統 2 perspective_gap、つまり日本で角度自体が論じられていない)」
事象。日本メディアと海外メディアが同じ角度で対立評価する事象 (= 真の系統 3
framing_inversion) はサンプルに偶然含まれていなかった可能性が高い。系統 3 の
典型パターン例 (処理水放出 / 入管法改正 / 辺野古 / ジャニーズ問題) は、現状 25 件
サンプルでは構造的に拾えない (RSS 41 媒体が海外メディア中心で、日本国内メディアの
論調は入力に含まれない)。本仮説が真なら、stream_3 = 0 件は「LLM 判定の問題」でも
「4 分類定義の問題」でもなく、**入力データセットの構造的問題**。根本治療は
「系統 3 候補を意図的に追加した拡張ゴールデンセット」になる。

**Hydrangea コアミッションへの影響**:
- (a) 説なら → プロンプトを微調整して stream_2 識別を強化、F-stream-2-filter-design は
  当初想定通りの規模で実装
- (b) 説なら → F-stream-2-filter-design は **責務範囲縮小** (stream_2 候補が極小、
  小規模実装で済む) + F-jp-coverage-tune の二段階クエリ生成が **より優先**

**カズヤレビューで判別する**:
F-particular-angle-redesign Task E (カズヤレビュー) で stream_2 に再分類されるケースが
何件あるかで判断 ((a)/(b) の判別):
- 0 件 → (b) 説支持、F-stream-2-filter-design 縮小
- 1-2 件 → (a) と (b) のハイブリッド、F-stream-2-filter-design はミニマル実装
- 5+ 件 → (a) 説支持、F-stream-2-filter-design は当初想定通り

(c) 仮説の判別: カズヤレビューで stream_3 に再分類されるケースが何件あるかと、
Phase A.5-3b 第二作で系統 3 事象 (例: 処理水放出 / 辺野古) を意図的に追加して
系統 3 サンプルを拡充できるかを併せて評価する。Task E カズヤレビューで stream_3
件数が依然 0 件 ((a)/(b) 判定で説明できない場合) なら (c) サンプル選定バイアス説の
証拠が強まる。

**(c) 仮説の証拠強化 (★ F-task-e-finalize / 2026-05-08 で追記)**:
F-particular-angle-redesign Task E カズヤレビュー (2026-05-08) で 25 件全件を
横断レビューした結果、(c) サンプル選定バイアス仮説の **強い証拠** が確認された:

- カズヤレビューを経ても新たに `stream_3_framing_inversion` に再分類される件は
  **0 件** だった (= 25 件全件 LLM 推定値そのまま採用、`kazuya_review.*_revised`
  全件 null)
- 25 件中 perspective_gap が 20 件 (80%) に集中したのは、サンプルが「海外
  メディア独自視点」事象中心で、**日本メディア起点の評価軸を持つ事象 (= 真の
  系統 3 候補)** が偶然含まれていなかったため
- 引き継ぎ v3 でカズヤが提案した系統 3 候補 (処理水放出 / 入管法改正 / 辺野古
  / ジャニーズ) は、いずれも日本メディアが明確な評価軸を持っている事象だが、
  RSS 41 媒体 (海外発のみ) では構造的に拾えない

→ **stream_3 = 0 件は LLM 判定の問題でも 4 分類定義の問題でもなく、入力
データセットの構造的問題** であることが、レビュー結果で裏付けられた。

**根本治療** (Phase A.5-3b 第二作で実施想定):
- 系統 3 候補事象 (処理水放出 / 辺野古 等) を意図的に追加した拡張ゴールデン
  セット
- (c) 仮説の最終検証 + sontaku_signals type=domestic / media_industry の
  実例追加も兼ねる

**2026-05-08 命名整理 (F-particular-angle-redesign-extension)**:
本エントリ内の系統名は **本エントリ作成時の命名 (1/1.5/2)** で記述されて
いるが、F-particular-angle-redesign-extension で **1/2/3** に
リネームされた。読み替え:
- `stream_1_silence_gap` (系統 1) → 不変
- `stream_1_5` / `stream_1_5_perspective_gap` (旧系統 1.5) →
  `stream_2_perspective_gap` (新系統 2)
- `stream_2_framing_inversion` (旧系統 2) → `stream_3_framing_inversion`
  (新系統 3)
新命名で読み替えると、LLM 推定段階分布は
`stream_1=4 / stream_2=20 / stream_3=0 / out=1`。

**ステータス**: `Active (要サンプル拡充、Phase A.5-3b 第二作で根本治療)` —
F-task-e-finalize (2026-05-08) で (c) 仮説の証拠が裏付けられた。構造論点は
Resolved、件数論点は Phase A.5-3b 第二作のサンプル拡充で根本治療する。

extension で実施した構造的解 3 つ:
(1) 命名 1/2/3 に整理して系統 3 = framing_inversion を本来の意味に正典化
(2) sontaku_signals を別軸メタデータとして独立化、Step 4 の追加判定軸に
    組み込み (= 評価フレーム対立 **かつ** 忖度シグナル level=high/medium
    が系統 3 の必須条件)
(3) MECE 判別基準を明示 (PARTICULAR_ANGLE_DEFINITION.md セクション 3.5)
    して、境界事例の判定者依存を sontaku_signals.level で間接区別する
    設計に統一

カズヤレビュー時の系統 3 件数は依然として後続バッチのスコープ判断材料に
なる。(c) 仮説が真なら Phase A.5-3b 第二作で意図的に系統 3 候補事象を
追加する根本治療が必要。

**出典**:
- F-particular-angle-redesign 完了 (2026-05-08)
- F-particular-angle-redesign-extension 完了 (2026-05-08)
- F-extension-followup (2026-05-08、(c) 仮説追記)
- 前チャット引き継ぎプロンプト v3 (カズヤ提起の (c) サンプル選定バイアス説)
- `docs/runs/F-particular-angle-redesign/REPORT.md` セクション 4 + 9
- `docs/runs/F-particular-angle-redesign/reclassification_diff.json`
- `docs/runs/F-particular-angle-design/annotations.json` (schema_version 2.1)

### 2026-05-08: sontaku_signals type 分布のサンプル設計バイアス (F-extension-followup で記録)

**背景**:
F-particular-angle-redesign-extension (2026-05-08) の sontaku_signals LLM 推定で、
25 件中 `type=diplomatic` が 20 件 (80%) と圧倒的多数を占める分布が観測された。
DECISION_LOG / FUTURE_WORK では「Hydrangea 入力 RSS 41 媒体 (MEE, Meduza, Al Jazeera 等)
が外交・地政学事象中心という構造的整合」と説明されているが、これは整合の **説明**
であって、検証ではない。

**指摘**:
25 件のサンプル (golden_set 19 + 試運転 6) はもともと **海外メディア発の事象** が
中心。日本メディア起点の以下の type 候補事象は、サンプル設計上ほぼ拾えない構造:
- `domestic` 忖度 (政治家・上級国民): 例 — 政治家スキャンダルへの忖度、上級官僚への
  記者クラブ忖度、司法判断への配慮
- `media_industry` 忖度 (記者クラブ・芸能スポーツ業界): 例 — ジャニーズ問題の長年放置、
  電通・博報堂への配慮、特定スポーツ団体への配慮

引き継ぎ v3 で明示された系統 3 (framing_inversion) 候補 (処理水放出 / 入管法改正 /
辺野古 / ジャニーズ) のうち、辺野古 / ジャニーズは `domestic` / `media_industry`
寄りの忖度が背景。

**含意**:
- 現サンプルでの sontaku_signals 整備は問題なし (= 25 件範囲内では type=diplomatic
  が真の分布として整合)
- ただし、将来の系統 3 候補の type 分布を過小評価する可能性あり
- F-1 EditorialMissionFilter で `level=high/medium` の事象を優先採点する将来設計時、
  type 分布の偏りが優先度判定の歪みを生むリスク

**対処方針**:
- 即対処は不要 (= 現サンプルでの整備は問題ない、論点として可視化するだけで良い)
- Phase A.5-3b 第二作 (系統 3 事象、引き継ぎ v3 で「処理水放出 / 辺野古 等」が
  カズヤ提案) で意図的に `domestic` / `media_industry` 候補を含める
- F-1 EditorialMissionFilter 着手時 (将来検討) に再評価し、サンプル拡充の必要性を判断

**ステータス**: `Active` (Phase A.5-3b 第二作 + F-1 EditorialMissionFilter
設計時に再評価)

**出典**:
- F-particular-angle-redesign-extension sontaku_signals 推定結果 (2026-05-08)
- 前チャット引き継ぎプロンプト v3 (系統 3 候補 4 件のカズヤ提案)
- `docs/runs/F-particular-angle-redesign/extension_log.json` (type 分布詳細)
- `docs/runs/F-particular-angle-design/annotations.json` (各 event の
  sontaku_signals フィールド)

### 2026-05-08: sontaku_signals は嘘をつかない設計、疑わしきは低く見積もる 運用原則 (F-task-e-finalize で確立)

**背景**:
F-particular-angle-redesign-extension Task E カズヤレビュー (2026-05-08) で、
sontaku_signals.level の判定方針について議論が発生。当初クラウドが「同パターン
事象で level がバラついているのは LLM の判定揺れだから揃えるべき」「低く見積も
ると本丸を取りこぼすリスク」を主張したが、カズヤから本質的な反論があった:

> Hydrangea のメディアとしてのリスクは嘘をつくことだよね?だとすると、取りこぼ
> したほうが安全じゃない?

**確立した原則**:
- sontaku_signals は **真値データ** であって、過大主張は信頼性損失のリスク
  (= 「Hydrangea = 何でも忖度認定する陰謀論メディア」というレッテルを避ける)
- level=high 妥当の reasoning が立てづらいなら `medium`、medium が立てづらい
  なら `low` / `none` に下げる
- 取りこぼしリスクは F-1 EditorialMissionFilter の採点側で寛容に扱えば
  カバーできる (= 採点と真値の責務分離)

**含意**:
- カズヤレビューでは「level を高めに揃える」誘惑を排除し、LLM 推定値を
  尊重する (= 「LLM の知性に委ねる」原則とも整合)
- 過大主張による信頼性損失は、Hydrangea のメディアとしての存立基盤を毀損する
  ため、設計原則として明文化する価値がある

**ステータス**: `Resolved (運用原則として確立)` — 今後の sontaku_signals 関連
バッチ (F-1 EditorialMissionFilter / F-stream-2-filter-design 第二段階) で
本原則を参照する

**出典**:
- F-particular-angle-redesign Task E カズヤレビュー (2026-05-08) [B-3]
- カズヤ発言: 「Hydrangea のメディアとしてのリスクは嘘をつくことだよね?
  だとすると、取りこぼしたほうが安全じゃない?」

### 2026-05-08: 「LLM の知性に委ねる」原則 — カズヤレビューは検証であって 置き換えではない (F-task-e-finalize で確立)

**背景**:
F-particular-angle-redesign Task E カズヤレビュー過程で、カズヤから以下の
補足があった:

> Hydrangea のポイントの一つに LLM の膨大な知識による評価とか判定があるから、
> 一定 LLM を信用したいから

これを受けて、カズヤレビューの位置付けが明確化された。

**確立した原則**:
> **「カズヤレビューは LLM 判定の検証であって、置き換えではない」**

具体的な運用:
- カズヤが明確に LLM の誤判定を見つけたら → 修正
- カズヤが「どれもあり得る / 判別不能」なら → LLM 推定を採用 (= LLM の知識
  に委ねる)
- これは **クラウド誤り 9 (各論コントロールへの誘惑)** と同根の哲学 =
  「LLM の知性に委ねる」

**含意**:
- Hydrangea の根幹は「LLM の膨大な知識による評価・判定」を信頼すること
- 人間 (カズヤ) のバイアスや限定的知識で LLM 判定を上書きする方向には進まない
- カズヤレビューの責務は「LLM が明確に間違っている件のフィルタリング」のみ
- これは sontaku_signals だけでなく、particular_angle / stream_classification
  / 4 軸該当性すべての判定で適用される

**実装事例 (Task E カズヤレビュー、2026-05-08)**:
- 25 件全件 LLM 推定値そのまま採用 (`kazuya_review.*_revised` 全件 null)
- B-5 covered_004 (ローマ教皇)、B-7 covered_010 (フーシ派)、C-3 cls-0c7fa7c667d6
  (ロシア焼身) はカズヤ「判別困難」→ LLM 推定維持

**ステータス**: `Resolved (Hydrangea コアバリューとして明文化)` — 今後の
カズヤレビュー全般 (Phase A.5-3b 手動 PoC 含む) で本原則を適用

**出典**:
- F-particular-angle-redesign Task E カズヤレビュー (2026-05-08) [B-5/B-6]
- カズヤ発言: 「Hydrangea のポイントの一つに LLM の膨大な知識による評価とか
  判定があるから、一定 LLM を信用したいから」
- 関連: クラウド誤り 9 (各論コントロールへの誘惑) — 「LLM の知性に委ねる」
  設計哲学

### 2026-05-08: 「観点の選択的欠落 = 忖度」判定軸 — 主要扱い事象なのに特定 角度だけ抜ける場合の解釈 (F-task-e-finalize で確立)

**背景**:
F-particular-angle-redesign Task E カズヤレビューで、blind_009 (Iran-US 戦争
長期化、革命防衛隊の経済利権) の sontaku_signals.type 判定でクラウドが「専門
ニッチでリソース不足」とカズヤに提示したが、カズヤから本質的な反論があった:

> いや、これは明確に忖度だと思う。忖度というよりは暴くべき観点を暴いていない
> というか、『戦争経済』や利権構造を深掘り (しないこと)

**確立した判定軸**:
日本メディアが「報じない」理由を区別する基準として以下を採用する:

- **真の「リソース不足」(level=none / type=null)**:
  - 遠隔地のローカル国内問題で、日本メディアが現地取材リソースを持たない
  - 例: covered_007 (ナイジェリア拉致 = ナイジェリア国内統治不全)、
    covered_008 (マリ国防相暗殺 = マリ国内政情)
  - 日本でも主要事象として扱われていない場合
- **「観点の選択的欠落」= 忖度 (level=medium 以上)**:
  - **国際的に主要扱いの事象** (日本メディアでも主要ニュース化されている)
  - **なのに、特定の角度だけ抜け落ちる** (= 観点の選択的欠落)
  - 抜け落ちる角度が「権力構造に切り込む観点」であるほど忖度が強い
  - 例: blind_009 (中東情勢は主要扱いだが、戦争を経済構造として解剖する
    観点が欠落)、covered_005 (COP30 は NHK 等が現地取材まで行っているが、
    西側 vs グローバルサウスの構造的対立観点が欠落)

**含意**:
- 「忖度」の定義を「特定国・人物への外交的配慮」だけに限定しない
- 「権力構造・戦争構造・利権構造に踏み込まない」全般を含める
- これにより、Hydrangea コアミッション「忖度・報道規制をぶち壊す」の射程が
  明確化 (= 構造分析角度の選択的欠落こそが本丸)

**実装事例 (Task E カズヤレビュー、2026-05-08)**:
- B-4 blind_009 → 「戦争経済の利権構造を深掘りしない」= 忖度として
  level=medium 維持
- B-6 covered_005 → 「グローバルサウス主導の構造分析を深掘りしない」= 同型
- B-7 covered_010 → 「フーシ派の主体性を深掘りしない」= 同型
- B-8 cls-a4132ec7d949 → 「治安当局トップの中立性問題を深掘りしない」= 同型

**ステータス**: `Resolved (判定軸として確立)` — 今後の sontaku_signals 判定 +
F-1 EditorialMissionFilter 設計 + Phase A.5-3b 台本表現でこの判定軸を参照

**出典**:
- F-particular-angle-redesign Task E カズヤレビュー (2026-05-08) [B-4]
- カズヤ発言: 「これは明確に忖度だと思う。暴くべき観点を暴いていない」

### 2026-05-08: 試運転と golden_set の重複サンプリング問題 — 25 件中 2 ペア重複、独立件数は実質 23 件 (F-task-e-finalize で発覚)

**背景**:
F-particular-angle-redesign Task E カズヤレビュー過程で、annotations.json の
25 件を横断レビューした結果、**同一 MEE 記事を異なる経路で 2 回サンプリング
している** 重複が 2 ペア発覚した。

**重複事象**:
- **ペア 1**: blind_005 (golden_set 由来) ⇄ cls-33b4f4960bf9_7K (試運転 7-K
  由来) — 共に "Gaza was the scandal that should have ended Keir Starmer's
  political career" (英スターマー首相マンデルソン人事スキャンダル + ガザ加担
  対比)
- **ペア 2**: blind_004 (golden_set 由来) ⇄ cls-204a683f73ee_7K (試運転 7-K
  由来) — 共に "In Gaza, life flickers as power cuts shatter livelihoods and
  healthcare" (ガザ電力危機・潤滑油 100 倍暴騰)

**含意**:
- 25 件中 4 件が実質 2 件相当 = **独立サンプル件数は 23 件**
- F-jp-coverage-tune の二段階クエリ生成精度評価で、同一事象を 2 回計算する
  ノイズになる
- F-stream-2-filter-design の真値として使うとき、独立件数を誤認するリスク
- LLM の判定揺れも観察可能: ペア 1 は level が違う
  (blind_005=high / cls-33b4f4960bf9_7K=medium)、ペア 2 は揃っている
  (両方 medium) — これ自体は揃える必要なし (= データの実態として記録)

**対処方針**:
- 即対処は不要 (削除や統合はせず、両方とも annotations.json に残す)
- 後続バッチ (F-jp-coverage-tune / F-stream-2-filter-design) で真値として
  使うときに、本エントリを参照して独立件数を正しく扱う
- 将来検討: 試運転と golden_set で重複事象がある場合の検出ルールを定めるか、
  `source_origin` で重複検出する小機能を `finalize_annotations.py` に
  入れるかは Phase A.5-3b 着手前に判断

**追記 (2026-05-09, F-jp-coverage-tune 完了時)**: 本エントリの方針通り
F-jp-coverage-tune の精度測定で **独立 23 件** (= cls-33b4f4960bf9_7K /
cls-204a683f73ee_7K を除外、blind_005 / blind_004 を採用) を採用した。
`scripts/measure_two_stage_accuracy.py` の `EXCLUDED_DUPLICATE_EVENT_IDS`
セットでハードコード除外。post-tuning 結果 (Recall covered 42.11% / verdict=fail)
は独立 23 件ベースで計算済み = 後続 F-jp-coverage-tune-followup でも同方針
継承する想定。本エントリは Active 維持 (= F-stream-2-filter-design 着手時にも
参照する論点として残す)。

**ステータス**: `Active` (後続バッチで参照する論点として残す、即対処なし)

**出典**:
- F-particular-angle-redesign Task E カズヤレビュー (2026-05-08) [C-1/C-2]
- `docs/runs/F-particular-angle-design/annotations.json` blind_005 /
  cls-33b4f4960bf9_7K / blind_004 / cls-204a683f73ee_7K

### 2026-05-07: 台本表現:特定角度未報道のナレーション課題 (F-particular-angle-design レビューで派生)

**背景**:
F-particular-angle-design (2026-05-07) で 25 件 LLM アノテーション結果をカズヤがレビューした際、
系統 1 と判定された事象のうち blind_002/004/009 のような「広範事件は日本主要メディアで報道済み、
特定角度のみ未報道」というパターンで、台本に「日本では報じられていない」と書くと嘘になる
違和感が指摘された。

**カズヤの哲学的制約**:
- 言い回しを個別に指定するプロンプトルールは作りたくない (= ルール累積で全体劣化)
- article_writer.py は触りたくない (= 不変原則 1、記事クオリティの核心)
- LLM の知性に期待する設計を維持したい

**解決方向性 (議論中)**:
particular_angle メタデータを script_writer.py 新ルートに渡し、LLM が自分で言い回しを選択する設計。
具体的には:
- jp_coverage_status: 完全黙殺 / 広範のみ報道 / 解釈差
- core_question: 特定角度の核心
- differentiation_from_mainstream: 解釈差の内容
これらを台本生成 LLM に渡すと、LLM が:
- 完全黙殺 → 「日本では報じられなかった」
- 広範のみ報道 → 「日本でも取り上げられたが、◯◯という構造には触れていない」
- 解釈差 → 「日本のメディアは××と捉えたが、海外では△△と批判されている」
を文脈に応じて選択できる想定。

**自動化前提**:
- F-particular-angle-redesign で 1.5 分類確定 (jp_coverage_status の細分化)
- F-stream-2-filter-design で stream_2 候補に解説価値メタデータ付与
- F-jp-coverage-tune で jp_coverage_status のメタデータ自動付与
これらが揃った段階で script_writer.py 新ルートに particular_angle メタデータを統合する設計。

**Phase A.5-3b 手動 PoC での扱い**:
1 本目の素材 (Insider trading 候補) で実際に試行錯誤しながら表現を確立する。
カズヤがプロンプト微調整しながら最適解を探る運用。
バッチ化はせず PoC 内で吸収。

**ベストプラクティス調査**:
台本生成 LLM への構造化メタデータ入力の最新事例 (世界のベストプラクティス) を
Phase A.5-3b 着手前に web search で調査する想定。

**ステータス更新 (2026-05-08, F-particular-angle-redesign 完了時)**: `Active` (一部 Resolved)。
F-particular-angle-redesign (2026-05-08) で **メタデータ構造の正典化が完了**:
`docs/PARTICULAR_ANGLE_DEFINITION.md` 新サブセクション 3.5「系統別の台本表現の方向性」で
particular_angle_metadata 構造 (stream_classification + core_question +
differentiation_from_mainstream + hydrangea_axis_alignment) を確定。LLM への強制ルールは
書かず例示に留める設計哲学を明文化。残作業は (a) 具体的な言い回しの最適化 (Phase A.5-3b
手動 PoC で 1 本作りながら試行錯誤、Active のまま) + (b) F-jp-coverage-tune で
particular_angle_metadata の機械生成を実装 (二段階クエリ生成と一体化)。

**ステータス**: `Active` (Phase A.5-3b 手動 PoC で言い回し最適化、F-jp-coverage-tune で
メタデータ自動付与、F-stream-2-filter-design 完了後に script_writer.py 新ルートに統合)

**出典**:
- F-particular-angle-design レビュー (2026-05-07、カズヤ指摘)
- F-particular-angle-redesign 完了 (2026-05-08、メタデータ構造の正典化)
- `docs/PARTICULAR_ANGLE_DEFINITION.md` セクション 3.5 (台本表現ガイドライン)
- annotations.json blind_002/004/009 の判定差分 (4 分類化後は全て stream_1_5)

### 2026-05-07: 系統 1.5 分類追加の検討 (F-particular-angle-design レビューで派生)

**背景**:
F-particular-angle-design (2026-05-07) で 25 件レビュー時、カズヤから「一部報道だけど観点不足
っていう 1.5 分類儲けてもいいのかもしれない」と提案。現状の 3 分類 (系統 1 / 系統 2 / 対象外)
だと、系統 1 の中に「完全空白」と「広範のみ報道、特定角度未報道」が混在し、台本 LLM が
判断に迷う構造的問題がある。

**4 分類提案**:
- 系統 1 (silence_gap): 広範事件も特定角度も両方未報道
- 系統 1.5 (perspective_gap, 新規): 広範事件は報道済み + 特定角度のみ未報道
- 系統 2 (framing_inversion): 特定角度は報道済みだが解釈差
- 動画化対象外: 特定角度が報道済みかつ解釈も同じ

**メリット**:
- 台本表現の分類別ルールが明確化 (系統 1 / 1.5 / 2 で別表現)
- 25 件アノテーション分布が可視化される (系統 1 完全黙殺 6 件 + 系統 1.5 約 5 件 + 系統 2: 13 件 + 対象外: 1 件)
- F-13.B 二段階クエリ生成 (広範事件クエリ + 特定角度クエリ) の責務が明確化
- F-stream-2-filter-design の責務範囲が縮まる (系統 2 のみ担当)

**対処方針**:
F-particular-angle-redesign を新規バッチとして追加。本バッチ (F-particular-angle-design)
は 3 分類のまま完了させ、別バッチで 4 分類化を対処する設計。理由は:
- F-particular-angle-design のスコープ拡張は「勝手にスコープ広げない」原則違反
- 1.5 分類化は PARTICULAR_ANGLE_DEFINITION.md 改訂 + annotations.json 再分類が必要 (独立した責務)
- 別バッチで「動くものを壊さない」設計

**想定工数**: 2-3 時間 (PARTICULAR_ANGLE_DEFINITION.md 改訂 + annotations.json LLM 再抽出 or 手動再分類 + DISCUSSION_NOTES + DECISION_LOG 更新)

**実績工数 (2026-05-08 補正)**: 約 5-6 時間 (PARTICULAR_ANGLE_DEFINITION.md 改訂 + scripts/reclassify_annotations.py 新規 + Gemini API 503 高負荷で再分類実行 1:36 hr + per-call timeout + incremental save の追加 + scripts/finalize_annotations.py 改修 + scripts/generate_review_draft_v2.py 新規 + REPORT 統合 + ドッグフーディング)。Gemini API 高負荷耐性の追加実装が想定外コスト。

**ステータス**: ★ **Resolved (F-particular-angle-redesign / 2026-05-08 で実施完了、Task E カズヤレビュー待ち)**。
4 分類化を実施し、`docs/PARTICULAR_ANGLE_DEFINITION.md` を 4 分類版に大幅改訂、25 件アノテーションを 4 分類で再分類した。LLM 推定段階の分布は **stream_1=4 / stream_1_5=20 / stream_2=0 / out_of_scope=1** で、想定値 (stream_1≈6 / stream_1_5≈5 / stream_2≈13 / out_of_scope=1) と大きく乖離。stream_1_5 が想定外に多い (20 件) 結果は LLM の集約バイアスか 4 分類定義の必然的帰結かをカズヤレビューで判別する必要があり、F-stream-2-filter-design の責務スコープ縮小判断にも影響する論点として残る。

**出典**:
- F-particular-angle-design レビュー (2026-05-07、カズヤ提案)
- F-particular-angle-redesign 完了 (2026-05-08)
- `docs/runs/F-particular-angle-redesign/REPORT.md` セクション 4 (分布実測値) + 9 (想定外結果の解釈)
- annotations.json 25 件の 4 分類分布実態

### 2026-05-07: Hydrangea 動画化候補の系統分布実態 (F-particular-angle-design レビューで観察)

**背景**:
F-particular-angle-design (2026-05-07) のレビューで、カズヤから「直近で日本のメディアが完全に
黙殺したり報道規制するみたいなニュースはなかったってことなんだね」という観察が提示された。
データに基づいて整理した結果、Hydrangea が動画化する典型は実は完全黙殺ではなく、系統 2 や
系統 1.5 が中心であることが判明。

**25 件の分布実態 (★ F-particular-angle-redesign / 2026-05-08 で 4 分類実測値に更新)**:

3 分類版 (F-particular-angle-design / 2026-05-07):
| 分類 | 件数 | 比率 |
|---|---|---|
| stream_1_silence_gap | 11 件 | 44% |
| stream_2_framing_inversion | 13 件 | 52% |
| out_of_scope | 1 件 | 4% |

4 分類版 LLM 推定 (F-particular-angle-redesign / 2026-05-08):
| 分類 | 件数 | 比率 | 想定値 (バッチ仕様) | 差異 |
|---|---|---|---|---|
| 系統 1 (silence_gap) | 4 件 | 16% | 約 6 件 | -2 |
| 系統 1.5 (perspective_gap) ★ NEW | **20 件** | **80%** | 約 5 件 | **+15** |
| 系統 2 (framing_inversion) | **0 件** | **0%** | 約 13 件 | **-13** |
| 動画化対象外 | 1 件 | 4% | 1 件 | 0 |

**4 分類実測の含意 (2026-05-08 追加)**: stream_1_5 が圧倒的多数 (80%)、stream_2 が
0 件という想定外結果は LLM が 4 分類定義を厳密適用した結果で、海外メディアの特定
角度は『日本主流メディアと同じフレームでは報道されない』ケースが多い構造を可視化。
カズヤレビューで stream_2 が増えるか、LLM の集約バイアスによるものかを判別する。

**4 分類版 stream_1 (silence_gap) 4 件の特徴 (2026-05-08 確定)**:
- blind_001 (Ukrainian forces civilian casualties) → 西側プロパガンダ整合バイアス
- blind_003 (US-Israel intervention frees Israeli-Turkish) → 米イスラエル同盟の影
- blind_007 (Putin ally superyacht) → 制裁突破の限界露呈
- 試運転 cls-0c7fa7c667d6 (ロシア焼身) → 報道規制 (ロシア国内 + 西側両方)

3 分類版で stream_1 だった blind_010 / 試運転 cls-204a683f73ee_7K (Gaza 7-K) /
cls-6be4fc09d9ed (Insider trading) / cls-a4132ec7d949 (Met Police) は 4 分類化で
stream_1_5 に移動した。これらは 4 分類定義に厳密に従うと「広範事件は日本でも
報道済み (= 米イラン対立 / ガザ電力危機 / 米イラン合意 / Palestine デモ)、
特定角度のみ未報道」という構造に該当する。完全黙殺の核は **米国・イスラエル・
ロシアへの忖度** ど真ん中で、4 分類化後は **24% → 16% に縮小** した。

**カズヤの確認**:
F-1 EditorialMissionFilter で「日本人が知るべき」フィルタは既に機能している (試運転 18/364 通過、
通過率 5%)。25 件アノテーションは全て F-1 通過済みの「Hydrangea が取り上げるべき」事象。
ローカルすぎる出来事は弾かれている。

**含意 (★ 2026-05-08 更新)**:
- F-stream-2-filter-design の **責務範囲縮小可能性**: LLM 推定段階で stream_2 = 0 件
  なので、当初想定の「13 件の系統 2 候補を処理」から大幅縮小する可能性。カズヤレビュー
  結果次第で実装スコープ判断 (1-2 件なら新規 LLM 解説価値判定 1 段のみで済む)
- F-jp-coverage-tune の **優先度上昇**: 二段階クエリ生成 (広範事件クエリ + 特定角度
  クエリ) で系統 1 完全黙殺 vs 系統 1.5 広範報道を機械的に判別する責務、本バッチで
  真値 25 件 (broad_event_jp_coverage + particular_angle_jp_coverage 別フィールド)
  が整備されたため設計確度が向上、F-stream-2-filter-design より優先される構造に
- Phase A.5-3b 手動 PoC の **重要性が増す**: stream_1_5 が圧倒的多数なので、表現
  課題は「事件は報じられたが角度が欠落」を視聴者の違和感無く伝える文体を確立する
  ことが核心。`PARTICULAR_ANGLE_DEFINITION.md` セクション 3.5 のメタデータ構造を
  script_writer.py 新ルートに渡し、LLM が自律選択する設計を 1 本作りながら検証

**ステータス**: `Resolved (記録済み + 4 分類実測で更新済み)` (F-particular-angle-redesign / 2026-05-08 で 4 分類分布が確定、F-stream-2-filter-design + F-jp-coverage-tune の責務範囲再定義の根拠データに発展)

**出典**:
- F-particular-angle-design レビュー (2026-05-07、カズヤ観察 + Claude 補正)
- F-particular-angle-redesign 完了 (2026-05-08、4 分類分布実測)
- `docs/runs/F-particular-angle-redesign/REPORT.md` セクション 4-6 (分布 + 顕著な変更パターン)
- `docs/runs/F-particular-angle-design/annotations.json` (4 分類版上書き、25 件の実データ)
- F-trial-run-post-fix 試運転 18/364 通過実績

### 2026-05-07: covered_002 確定:米ロ停戦は系統 2、日本忖度パターン (F-particular-angle-design レビューで確定)

**背景**:
F-particular-angle-design (2026-05-07) のレビューで covered_002 (米ロ停戦電話会談、
トランプ 20 項目交渉) について、Claude (claude.ai) が「トランプ批判は欧米メインストリームでも
普通にされてる、視聴者にとって新鮮な角度か?」と懸念を提示し、stream_2 から動画化対象外への
格下げを示唆した。これに対しカズヤは「日本は忖度している良い例だからこれは取り扱うに値する」
と判断、Claude の意見を撤回。

**カズヤ判断の根拠**:
- 欧米メインストリーム (NYT 等): トランプ独断外交を批判する
- 日本主要メディア (日経 / NHK 等): 「停戦の可能性」を中立報道、深掘りしない
- これは米国忖度 (Hydrangea 4 軸第 2 軸) の典型例
- Hydrangea の視聴者は日本人で、日本メディアの忖度こそが取り扱う対象

**Claude 反省**:
元の評価「欧米でも報道されてるから視聴者に新鮮じゃない」は視点を西側中心で捉えていた。
Hydrangea ミッションは「日本人視聴者にとっての知識ギャップ」であり、欧米基準ではない。
意見を撤回し、LLM 判定 (stream_2_framing_inversion) で確定。

**確定**:
- covered_002 → stream_2_framing_inversion (LLM 判定維持)
- annotations.json 修正なし
- 米ロ停戦事象は Hydrangea 動画化候補として有効

**含意**:
- Claude (claude.ai) のレビュー判断にも視点バイアスのリスクがある
- カズヤレビューが「日本人視聴者基準」を保持する役割を持つ
- 今後のレビューでも Hydrangea ミッションの「日本人視聴者中心性」を意識する必要

**ステータス**: `Resolved` (covered_002 は stream_2 で確定、Claude 視点バイアス事例として記録)

**出典**:
- F-particular-angle-design レビュー (2026-05-07、カズヤ vs Claude 議論)
- annotations.json covered_002 詳細

### 2026-05-07: 特定角度抽出の LLM 限界観察 (F-particular-angle-design で観察)

**背景**:
F-particular-angle-design (2026-05-07) で 25 件の特定角度を Gemini analysis Tier
で抽出した結果、いくつかの構造的観察が得られた。

**観察 1: golden_set v1.1 stream_2_candidate メタとの差分**:
v1.1 で `stream_2_candidate` メタを付与した 4 件 (blind_002 / blind_004 /
blind_005 / blind_009) のうち、3 件 (blind_002 / blind_004 / blind_009) が
LLM では `stream_1_silence_gap` に分類された。これは判定対象を「広範事件」から
「特定角度」に絞ると同じ事象でも結論が変わる構造を示唆する事例。
- blind_002 (Israel Jewish religious body): v1.1 では「像破壊事件本体は朝日・
  日経で報道済み = stream_2_candidate」、LLM では「ラビ庁拒否という特定角度自体は
  日本主要メディアで未報道 = stream_1_silence_gap」
- blind_004 (Gaza power cuts): v1.1 では「ガザ電力危機本体は東京新聞で報道済み」、
  LLM では「潤滑油 100 倍 / 産業構造の物理的解体という特定角度は日本未報道」
- blind_009 (Iran-US war money): v1.1 では「戦争長期化の経済的理由は SPF/JBpress 等で
  解説」、LLM では「制裁収益分配・革命防衛隊利権という特定角度は日本未報道」

ただしこれは LLM 判断であり、カズヤレビューで再評価される。重要なのは「広範事件」
vs「特定角度」の判定単位差で結論が変わる構造そのものの可視化。

**観察 2: covered 系列 9/10 件が stream_2 に分類**:
covered 系列 (= 日本主要メディアで広範事件は報道済みの 10 件) のうち 9 件が
LLM では `stream_2_framing_inversion` に分類された (covered_006 NVIDIA 株式
のみ out_of_scope)。これは LLM が「日本主要メディアで報道済みの事象でも、
海外メディアの掘り下げ角度には解釈差があり stream_2 候補となる」と読む傾向を
示す。F-stream-2-filter-design が処理する候補数の見積もり材料になる
(= 系統 2 として救出される事象は『日本未報道』に限らず、『日本報道済み + 解釈差』も
含む)。

**観察 3: max_output_tokens=2000 では分析タスクで途中切断**:
試行 1-2 で `get_analysis_llm_client()` 既定の max_output_tokens=2000 で
6-7 件の JSON 途中切断 (= "Unterminated string" パース失敗) が発生。
4096 への拡張で 0 errors 達成。analysis_llm_client 既定値は本タスクには
不十分という観察を F-stream-2-filter-design で同種の LLM 分析を行う際の
判断材料として記録。

**観察 4: extraction_confidence の分布**:
high=22 / medium=3 / low=0 / unknown=0。medium 3 件は covered_002 (米ロ停戦)、
covered_003 (米中関税)、covered_007 (ナイジェリア拉致)。これらは『広範事件は
日本でもガッツリ報道済み + MEE/海外特有の特定角度が薄い』タイプで、LLM が
4 軸該当性の判断に自信を持てなかった (= 解釈差を抽出しにくい)。系統 2 候補の
中でも解説価値の濃淡があることを示唆。

**論点**:
- (a) カズヤレビュー後に LLM 出力との差分が大きい場合、プロンプト改善の
  余地ありと判断 → F-stream-2-filter-design でプロンプトを微調整
- (b) covered 系列の stream_2 一括分類が「LLM の集約バイアス」(系統 2 寄りの
  判定をしがち) なのか、本当に解説価値のある事象なのかを確認する必要 →
  F-stream-2-filter-design で第二段階の解説価値判定を厳しくする設計の
  根拠データになる
- (c) max_output_tokens 既定値の見直し (=4096 に上げる方針) を analysis 系の
  全 LLM 呼び出しに適用すべきかは別議論

**Hydrangea コアミッションへの影響**:
- 「特定角度」概念導入で系統 1 / 系統 2 の判定が排他になり、両系統並立の
  実装基盤が確立した
- ただし LLM 一次推定の精度はカズヤレビューで検証する必要があり、過度に
  LLM 推定を信頼しないことが重要

**出典**:
- F-particular-angle-design REPORT.md セクション 5 (LLM 抽出結果) + セクション 7.1
  (興味深い観察)
- `docs/runs/F-particular-angle-design/annotations.json` 25 件の実データ
- `docs/runs/F-particular-angle-design/extraction_log.txt` 試行 1-2-3 の
  パース失敗ログ
- DECISION_LOG (F-particular-angle-design / 2026-05-07)

**ステータス**: `Active` (カズヤレビュー後に再評価、観察 1 の 3 件の差分が
解消されればステータス変更可。観察 3 は F-stream-2-filter-design 着手時に
判断材料として参照、観察 2/4 は同バッチで第二段階の解説価値判定設計の
根拠データになる)

### 2026-05-07: F-13.B Grounding 検索クエリ品質問題 — 英語タイトルクエリでの youtube.com 偏重 (F-trial-run-post-fix で観測)

**背景**:
F-trial-run-post-fix 試運転 (2026-05-07) で F-13.B が 6 invocations
(試運転 3 Slot + replay 7-K 3 件) 行われた。全 invocation で Grounding API が
返す URL は `youtube.com` (excluded URLs 計 23 件) 中心で、日本主要メディア
(WL 27 ドメイン) のヒットが 0 件だった。

WebSearch 後追いで明らかになった事実:
- 試運転 Slot-1 (Insider trading: Oil and stocks jolt on news of US-Iran deal)
  は nikkei.com (Tier 1) + jiji.com (Tier 2) + bloomberg.co.jp (Tier 2) で広範
  に報道済み
- 過去 7-K Slot-1 (FIFA Palestine) は jiji.com (Tier 2) で関連報道
- 過去 7-K Slot-2 (Mandelson) は nikkei.com (Tier 1) + bloomberg.co.jp (Tier 2)
  + jiji.com (Tier 2) で広範に報道済み

→ F-13.B の Grounding 検索クエリ (`{title} 日本 報道` 形式) では英語タイトルの
場合、Grounding が日本語ニュース記事を引き当てられない傾向。代わりに英語
タイトル文字列にマッチする YouTube 動画が返される構造。

**論点**:
- (a) F-jp-coverage-tune で Grounding クエリを改善 (英語タイトル → LLM で
  日本語キーワード抽出 → 「NHK 朝日 日経 ロイター」等の WL ドメイン名ヒント
  混入) で対応する案
- (b) 検索クエリそのものに加えて、Grounding API の filter / site: 演算子等で
  日本主要メディアサイトを優先指定する案 (Gemini Grounding が site: 演算子を
  サポートするかは要確認)
- (c) Grounding API → 別の検索 API (Bing 等) に変更する案 (過剰スコープ、
  既存設計大幅変更のため見送り推奨)

**Hydrangea コアミッションへの影響**:
- 系統 1 (silence_gap) 判定で Recall miss が発生 = 本来 divergence 扱いすべき
  事象を blind_spot として動画化する誤判定が現状残存
- F-stream-2-filter-design 完成後は系統 2 で救出される設計だが、Grounding
  クエリ品質改善でフィルタの上流精度を上げる方が根本解
- これは F-jp-coverage-tune の主要課題と整合

**出典**:
- F-trial-run-post-fix 試運転結果 (`docs/runs/F-trial-run-post-fix/trial_run_log.json`)
- 過去 7-K WebSearch 後追い (`docs/runs/F-trial-run-post-fix/past_videos_audit.json`)
- DECISION_LOG (F-trial-run-post-fix / 2026-05-07)
- 既存 FUTURE_WORK エントリ「F-jp-coverage-tune」の対応案 1 (FN Recall 改善)
  が本論点と完全整合

**ステータス**: `昇格候補(FUTURE_WORK)` (F-jp-coverage-tune に統合可、本エントリは
F-jp-coverage-tune 着手時の根拠データとして再利用)

**2026-05-11 追記 (F-trial-run-post-tune での状況改善)**:
- F-jp-coverage-tune-followup (2026-05-09) で WL マッチング階層判定化 + WL 拡張
  3 ドメイン (afpbb / forbesjapan / nippon) 投入後、F-trial-run-post-tune 試運転
  で **excluded_count が 23→1 件 (-22) と劇的減少、Slot-1 で youtube 1 件のみ**
- has_jp_coverage=True が 3/3 になり、Grounding 検索クエリ品質問題は **WL 整備
  経由で実質的に解消傾向** (= 検索クエリ自体は変えていないが、WL 拡張で受け
  止められるようになった)
- ただし matched_urls がベアドメインのみ問題 (別エントリ参照) が新規発覚した
  ため、本問題と密接に関連 = 「Grounding が WL 内ドメインを返すようになった」
  + 「ただしそれが記事レベルで一致しているかは別問題」という二層構造に


### 2026-05-04: 系統 1 (silence_gap) の判定基準明確化 — 「未報道理由の構造性」(4 軸)

**背景**:
F-verify-jp-coverage-golden の blind_006 (パレスチナ FIFA 提訴) について、
カズヤから「これは blind ケースとしては弱い」と指摘。理由は単にマイナーで
報道価値が低いだけで、報道規制 / 自由度の低さや忖度が原因ではないため。

**確立した判定基準 (4 軸構造)**:
系統 1 (silence_gap) のターゲットは「日本未報道」だけでは不十分。
未報道の理由が以下 4 軸のいずれかに該当する事象のみ系統 1 として動画化価値がある:

**1. 制度・システム面の構造バイアス**:
- 報道規制・自由度の低さ (報道機関への政治的圧力 / クロスオーナーシップ問題等)
- 記者クラブ制度等の既得権益による議題設定の偏り
- スポンサー・広告主への配慮による忖度

**2. 外交・経済・利害関係面の構造バイアス**:
- 特定国への忖度 (米国 / 中国 / 韓国 / イスラエル / サウジ / ロシア / 北朝鮮等
  との外交・経済・歴史的関係性に起因する報道抑制)
- 大企業・業界団体への忖度 (広告主だけでなく、業界・産業構造としての配慮)

**3. ★ 個人・権力者面の構造バイアス (Hydrangea ミッションど真ん中)**:
- 政治家・上級官僚への忖度 (スキャンダルや不祥事の黙殺)
- 財界要人・大企業経営者への配慮
- 司法関係者 (検察・裁判官等) への遠慮
- メディアオーナー一族への内部配慮 (マスコミ自身の経営陣・幹部含む)
- 警察上層部への配慮
- 芸能・スポーツ界の権力者への忖度
- 「上級国民」と揶揄される層への構造的配慮全般

**4. 関心領域・地政学的死角**:
- 日本の地政学的死角 (中東・グローバルサウス・アフリカ・南米等への関心の低さ)
- 国際的に重要だが日本に直接関係薄い事象

逆に以下は系統 1 として弱い (除外基準):
- 単にマイナーで報道価値が低い
- 専門領域でニッチすぎる
- 海外でも大きく扱われていない

**Hydrangea のメディアとしての存在意義 (2026-05-04 カズヤ宣言)**:

> 忖度、報道規制、報道の自由度の低さをぶち壊そう。
> そういうクソみたいな理由で報道されないものこそ Hydrangea で取り扱うべき記事。

系統 1 (silence_gap) は単なる「日本未報道の海外ニュース紹介」ではなく、
**構造的に黙殺されている事実を可視化することで、日本の報道環境の構造的歪みを
ぶち壊す** ことが本質的ミッション。

「未報道理由の構造性」判定で「単にマイナー」「専門ニッチ」を除外するのは、
このミッションに整合しない事象 (= 動画化価値がない事象) を排除するため。
逆に「個人・権力者への忖度」「特定国への忖度」「報道規制起因」のものは
**Hydrangea が取り扱うべきど真ん中**。

**実装上の波及**:
F-13.B JpCoverageVerifier は「日本未報道か否か」の機械的判定のみで、
「未報道理由の構造性」までは判定しない。これは設計思想として:
- (i) F-13.B は機械的フィルタ (URL ドメイン照合) に責務を限定
- (ii) 「未報道理由の構造性」判定は別レイヤー (LLM 判断 or 上流の素材選定) で担当

ゴールデンセット作成・運用時にこの基準を意識する。

- **出典**: F-verify-jp-coverage-golden-fix (2026-05-04) のカズヤレビュー +
  `docs/runs/F-verify-jp-coverage/golden_set.json` v1.1 changelog +
  本エントリ自体が判定基準の正本

**2026-05-07 更新 (F-particular-angle-design 完了反映)**:
4 軸構造は維持しつつ、判定対象が「広範事件」から「特定角度」に絞られた
(F-particular-angle-design / 2026-05-07)。これは系統 1 / 系統 2 / 対象外の
判定が広範事件レベルだと両系統で重複する問題を構造的に消すための変更。
詳細は `docs/PARTICULAR_ANGLE_DEFINITION.md` セクション 2-3 参照。
4 軸該当性 (本エントリの内容) は「特定角度が 4 軸のいずれかに該当するか」を
判定する Step 1 として `docs/PARTICULAR_ANGLE_DEFINITION.md` の論理フロー
内に組み込まれ、本エントリは引き続き 4 軸の正本として機能する。

- **ステータス**: `Active` (★ F-particular-angle-design / 2026-05-07 で
  「特定角度」概念と統合、`docs/PARTICULAR_ANGLE_DEFINITION.md` を判定基準
  正典として参照する運用に。Phase A.5-3b 系統 2 ロジック実装時 +
  F-stream-2-filter-design + F-jp-coverage-tune で参照される判定基準)

### 2026-05-03: F-13.B 動作仕様の検討課題 — タイトルクエリで広範な事件を引き当てる構造 (F-verify-jp-coverage-golden で観察)
- **内容**: F-verify-jp-coverage-golden のゴールデンセット作成中に、blind 候補
  10 件中 5 件で共通パターンが観察された:
  - **広範な事件**は Tier 1 (NHK / 日経 / 朝日等) で報道済み
  - **MEE 記事の核心** (特定の構造分析角度) は未報道
  - 例 (5 件):
    1. blind_002 (cls-a1fde1c574a7): キリスト像破壊事件本体は Nikkei / Asahi
       で報道、ラビ庁拒否の構造分析角度は未報道
    2. blind_004 (cls-204a683f73ee): ガザ電力危機本体は東京新聞 / CNN.co.jp
       で報道、潤滑油 100 倍 / 社会インフラの物理的解体角度は未報道
    3. blind_005 (cls-33b4f4960bf9): マンデルソン人事スキャンダル本体は Nikkei /
       Bloomberg JP で報道、ガザ支援こそ真のスキャンダル角度は未報道
    4. blind_006 (cls-7bd1406438b6): Palestine FIFA 関連報道は Jiji 等で過去
       あり、2026-04 特定提訴は未報道
    5. blind_009 (cls-4045a389ba04): 戦争長期化の経済的理由を扱う日本側分析
       は SPF/Bloomberg JP で複数あり、MEE オピニオン特有の制裁収益分配角度
       は未報道

  F-13.B の現実装は `_build_search_query()` で title + " 日本 報道" を
  クエリとし Gemini Grounding で検索 → URL を WL 照合する。タイトル文字列
  が広範な事件をカバーしている場合 (例: "Israel's top Jewish religious body
  refuses to condemn smashing of Jesus statue") キリスト像破壊事件本体の
  Tier 1 報道を引き当てて has_jp_coverage=True と判定する可能性が高い。

  これは Hydrangea コアミッション系統 1 (silence_gap = 日本未報道の大ニュース
  発掘) と系統 2 (framing_inversion + 構造分析 = 報道差の背景解説) の両方に
  影響する設計判断:
  - **系統 1 視点**: 広範な事件が Tier 1 報道済みなら『日本未報道』ではない
    → has_jp_coverage=True で正しい (現仕様 OK)
  - **系統 2 視点**: 特定構造分析角度が未報道なら『報道差』が存在
    → 動画化対象として残すべき、has_jp_coverage 判定だけでは不十分

  F-13.B は系統 1 のためのフィルタとして設計されたが、系統 2 と組み合わせる
  場合の判定基準が不明確。

  **検討すべき対応案**:
  - (a) 現仕様維持: F-13.B は系統 1 のみ判定、系統 2 (構造分析角度の未報道
    検出) は別の検証ロジックで担当 → coverage_gap (系統 1) と
    angle_gap (系統 2) の 2 段階検証に拡張
  - (b) F-13.B 改修: 検索クエリに『MEE 視点』『特定キーフレーズ』を加え、
    広範な事件ヒットをフィルタアウトする → 実装複雑化、Gemini Grounding の
    精度依存度上昇
  - (c) ゴールデンセットで現仕様の挙動を測定し、系統 2 ニーズが顕在化した
    時点で改修判断 → 過剰拡張性の罠を回避

- **出典**: F-verify-jp-coverage-golden 作成過程の観察
  (docs/runs/F-verify-jp-coverage/golden_set.json の kazuya_review_required_ids
  5 件)、CURRENT_STATE.md セクション 0 (コアミッション 2 系統並立)

**2026-05-04 議論結果 (カズヤレビュー後の方針確定)**:

カズヤから「機械の役割」について以下の整理が提示された:
> この工程は、日本未報道って判定されたニュースに対して本当に日本未報道なんだよね?
> ってチェックする工程。未報道ならそれで OK だけど、実は日本で報道ありましたって
> なったら、それは日本との報道内容の差があって、その背景に地政学的な解説とか歴史的
> または文化的背景の解説とかはたまた政治的な意図とかの解説によって Hydrangea で
> 報道する価値があるならそっち方面で取り扱うべきだし、そうじゃないなら報道対象外
> に振り分けるべき。

これを実現する設計として **2 段階フィルタ + 解説価値判定** を採用:

```
[海外ニュース入力]
    ↓
[ステップ 1: 日本未報道チェック (今の機械、F-13.B)]
    ├── 未報道 → 系統 1 として動画化 (silence_gap)
    │   ※ ただし「未報道理由の構造性」判定が別レイヤーで必要
    │   (DISCUSSION_NOTES「系統 1 判定基準明確化」エントリ参照)
    └── 報道済み
            ↓
        [ステップ 2: 報道差の質チェック (新規実装)]
            ├── 海外と日本で報道されてる「角度」が違う + 解説価値あり
            │       → 系統 2 として動画化 (framing_inversion / divergence_analysis)
            └── 単に同じ内容が報道されてるだけ
                    → 報道対象外
```

ステップ 2 の実装には以下既存資産を統合活用:
- `framing_inversion` 軸 (perspective_select_and_verify.md): 既存
- `multi_angle_analysis.md` 5 観点 (geopolitical / political_intent / economic_impact
  / cultural_context / media_divergence): 既存
- 3 ソース対比ルール (DISCUSSION_NOTES 既存エントリ): **未実装** ← ここを実装する

**Phase 配置の判断**:
- 当初案: Phase A.5-3b 内に組み込み
- カズヤ指摘: 「手動 PoC は手動 PoC に集中したいから、PoC 前に実装するべき」
- → **Phase A.5-3b 着手前に独立バッチ F-stream-2-filter-design として実装**
  - F-verify-jp-coverage-measure 完了後 → F-stream-2-filter-design → Phase A.5-3b
- これにより 3b は手動 PoC に集中、フィルタは事前確定

**選定された対応案**: (a) 現仕様維持 (F-13.B は系統 1 専用) + 系統 2 用ロジックを
F-stream-2-filter-design として独立実装

**ステータス更新**: `要確認 → 確定` (方針確定、F-stream-2-filter-design として
FUTURE_WORK 緊急度 高に登録)

**2026-05-05 実測結果 (F-verify-jp-coverage-measure)**:

ゴールデンセット v1.1 (19 件) で F-13.B の精度を実測したところ、
全 19 件で `matched=0`, `has_jp_coverage=False` という異常パターンが観測された:

| 指標 | 実測値 | 合格基準 | 達成 |
|---|---|---|---|
| Recall (covered) | 0.00% | >= 90% | ❌ |
| Precision (blind) | 26.32% | >= 80% | ❌ |
| F1 (covered) | 0.000 | >= 0.85 | ❌ |
| Tier 一致率 | 0.00% (0/0) | >= 70% | ❌ |
| Errors | 0/19 | — | (測定は安定) |

verdict=fail。NHK / Nikkei / Jiji / Bloomberg JP 等で確実に報道されている
covered 10 件 (例: covered_001 ホルムズ封鎖、covered_003 米中関税) でも
すべて `has_jp_coverage=False` 判定。

★ **根本原因の特定 (2026-05-05 デバッグ追加)**:
F-13.B `_search_with_grounding()` (`src/triage/jp_coverage_verifier.py:271-285`)
は `chunk.web.uri` を URL として WL マッチングに使っているが、
Gemini Grounding API は実ソースドメインではなく Vertex AI のリダイレクト URL
(`vertexaisearch.cloud.google.com/grounding-api-redirect/...`) を返す仕様。
実ドメインは `chunk.web.title` (例: `jiji.com`, `jetro.go.jp`,
`recordchina.co.jp`) に格納されている。`chunk.web.domain` は SDK 現行版で
常に None。

このため WL マッチング (`if domain in url_lower`) は redirect URL に対して
構造的に常に不一致 → F-13.B は **本番でも常に has_jp_coverage=False を
返している** 可能性が極めて高い。本来 divergence 扱いすべき「日本で報道済み
の海外ニュース」を blind_spot として動画化していた懸念。試運転 7-K の
「100% (3/3) 動画化」は F-13.B の判定精度ではなく、F-13.B が常に False を
返した結果として全 Slot が blind_spot ルートに進んだだけと再解釈される。

**修正方針**: `_search_with_grounding()` で `chunk.web.title` を読み取り、
`https://{title.lower().strip()}` 形式で urls に積む最小修正。
F-jp-coverage-improve バッチで対応 (FUTURE_WORK 緊急度 高に新規登録)。
F-stream-2-filter-design 着手は **保留** (F-13.B が機能していない状態で
系統 2 だけ実装しても上流で報道済み事象が blind_spot ルートに流れたままに
なるため、設計前提が崩れる)。

**ステータス更新**: `確定 (2 段階フィルタ採用) → 確定 + 致命バグ特定 (2026-05-05)
→ F-jp-coverage-improve で修正後に再測定で取り直し → 確定 + 致命バグ修正完了
(2026-05-07、F-jp-coverage-improve resolved) → 確定 + 修正の本番動作確認済み
(2026-05-07, F-trial-run-post-fix)` (本検討課題は F-13.B 仕様の理解に決着し、
別途見つかった構造的不具合も F-jp-coverage-improve で根本治療済み。
F-trial-run-post-fix で本番試運転 + 過去判定後追いを実施し、構造的に機能している
ことが本番運用でも確認できた。2 段階フィルタ設計の前提条件が完全に確保された。
残課題は精度閾値達成のみで F-jp-coverage-tune に分離)

**2026-05-07 修正完了報告 (F-jp-coverage-improve)**:

`src/triage/jp_coverage_verifier.py` にドメイン抽出レイヤー
(`_extract_domain_from_chunk` / `_looks_like_domain` / `_normalize_domain`) を
SDK 変更耐性のある防御層として追加。`_search_with_grounding()` を修正して
`chunk.web.title` を実ドメインとして読み取り `https://{domain}` 形式で WL
マッチングに供給。`chunk.web.uri` (Vertex redirect URL) は debug 用
`redirect_urls` に分離記録。

再測定結果 (verdict=fail のままだが構造的不具合は解消):

| 指標 | v1 (修正前) | v2 (修正後) | 変化 |
|---|---|---|---|
| TP | 0 | 10 | +10 |
| FN | 14 | 4 | -10 |
| Recall (covered) | 0.00% | 71.43% | +71.43pt |
| F1 (covered) | 0.000 | 0.769 | +0.769 |

残課題 (FN クエリ最適化 / FP diamond.jp 真値再評価 / Tier 一致率) は本検討課題
の対象外で、F-jp-coverage-tune (FUTURE_WORK 緊急度 高新規登録) で対応。
F-stream-2-filter-design 着手再開条件は「F-trial-run-post-fix 完了後」に更新
(精度閾値達成は F-stream-2-filter-design の必須前提ではない、構造的に動いて
いれば設計は進められる)。

**2026-05-07 本番動作確認 (F-trial-run-post-fix)**:

修正後 F-13.B を本番パイプライン (`python -m src.main --mode normalized`) で試運転
し、防衛機構 5 層の発火状況 + 過去試運転 7-K 動画化 3 件の WebSearch 後追いと
修正後 F-13.B での再判定を実施。

主要結果:
- 試運転で 3 Slot 全て has_jp_coverage=False、ただし excluded_urls_count > 0
  (1/10/3、全 youtube.com) で **構造的不具合解消の本番動作確認済み** (修正前は
  excluded=0 で構造的に常に False だった)
- WebSearch 後追いで 試運転 Slot-1 (Insider trading) は Tier 1 (nikkei) + Tier 2
  (jiji + bloomberg) で報道済みと判明 = Recall miss 1/3 (F-jp-coverage-tune 対象)
- 過去 7-K 動画化 3 件: Slot-1 (FIFA) + Slot-2 (Mandelson) は WebSearch では
  Tier 1-2 報道済み (典型的 stream_2_candidate パターン)、Slot-3 (Gaza 電力) は
  真の blind_spot に近い
- 修正後 F-13.B での 7-K 再判定: 3 件全て False→False 判定不変 (excluded 0/5/4 で
  構造機能は OK、Recall miss は Grounding クエリ品質問題)
- 防衛機構 5 層全機能確認 (F-1 18/364, F-2 全通過, F-13.B 3 invocations,
  F-5 救済 0, F-13 隠れ層 0)

→ Phase A.5-3a-verify ゲート完了 (1-A〜1-D''' 全完了) を正式宣言。
F-stream-2-filter-design 着手 OK。F-jp-coverage-tune は別系で並走可能。

- **出典**: F-verify-jp-coverage-measure (2026-05-05) 実測 + F-jp-coverage-improve
  (2026-05-07) 修正後再測定 + F-trial-run-post-fix (2026-05-07) 本番試運転 +
  `docs/runs/F-verify-jp-coverage/measurement_result.json` v2 (root_cause_finding
  に resolved_in 追加) + `docs/runs/F-verify-jp-coverage/REPORT.md` v2 (★1.5
  根本原因の特定と修正済み報告セクション) + `docs/runs/F-trial-run-post-fix/REPORT.md`
  + DECISION_LOG エントリ (F-jp-coverage-improve / 2026-05-07,
  F-trial-run-post-fix / 2026-05-07)

### 2026-05-01: 手動 PoC 推奨の軌道修正経緯 (クラウド誤り 5 例目)
- **内容**: クラウド (claude.ai 側) が当初「自動化を先に」と提案したが、
  カズヤが「自動化の前に最高傑作を 1 本人間が手作りする」哲学を主張し、
  Phase A.5-3b として手動 PoC をロードマップに正式登録した経緯。
  クラウドの誤り 5 例目として記録 (1-4 例目は別途整理予定)。
- **出典**: 引き継ぎプロンプト v3 / チャット移行時のロードマップ確定議論
- **ステータス**: `Active` (今後同種の誤りを防ぐため、CURRENT_STATE.md の
  「カズヤの直近フィードバック要点」に反映する候補)

### 2026-05-01: C-1/C-2/C-3 の RPM 対策が引き継ぎプロンプト全バッチ歴史リストから消えてる件
- **内容**: Phase 1 で実施した Gemini RPM 制限対策 3 バッチ (B-2 系)
  および C-1/C-2/C-3 の対応詳細が、最近の引き継ぎプロンプトの
  「全バッチリスト」から欠落している。CURRENT_STATE.md には
  「11 連続成功」のみが記載されており、Phase 1 / 1.5 の成果が
  時系列で追えなくなりつつある。
- **出典**: 引き継ぎプロンプト v3 / 過去の DECISION_LOG.md レビュー
- **ステータス**: `要確認` (DECISION_LOG.md に C-1/C-2/C-3 のエントリが
  存在するか確認 → 不足していれば補完する判断)

### 2026-05-01: CLAUDE_CODE_INSTRUCTIONS.md は分析レイヤー実装期 (2026-04-25) の遺産
- **内容**: `CLAUDE_CODE_INSTRUCTIONS.md` は 2026-04-25 の分析レイヤー実装期に
  作成されたもので、現運用 (BATCH_PROTOCOL ベース) と別系統。
  現状で参照されている形跡が薄く、アーカイブ判断対象。
- **出典**: 引き継ぎプロンプト v3 / リポジトリの docs/ ディレクトリ確認
- **ステータス**: `昇格候補(FUTURE_WORK)` (緊急度低: アーカイブ判断 + 移動先決定)

### 2026-05-01: スコープ転換 → DECISION_LOG 昇格運用ルール (F-12-B-1 前例)
- **内容**: F-12-B-1 で「NG リスト方式 → 考え方で制御」へスコープが
  根本転換した際、その判断経緯を DECISION_LOG.md に記録した前例がある。
  今後同種のスコープ転換が発生した場合、DISCUSSION_NOTES.md に
  メモを蓄積 → バッチ完了時に DECISION_LOG.md へ昇格する運用ルールを明文化したい。
- **出典**: 引き継ぎプロンプト v3 / DECISION_LOG.md の F-12-B-1 エントリ
- **ステータス**: `昇格候補(DECISION_LOG)` (BATCH_PROTOCOL.md に運用ルールとして
  追記 → DECISION_LOG.md に意思決定として登録)

### 2026-05-01: STEP 3 既存禁止語表と F-12-B-1 「考え方の原則」のレイヤー関係
- **内容**: configs/prompts/analysis/geo_lens/script_with_analysis.md の
  STEP 3 既存禁止語表 (真実→事実、衝撃→力学、黒幕→主導権 等) と、
  F-12-B-1 で導入した「考え方の原則」(視聴者ファースト 3 原則) は
  独立した 2 層として機能している。既存の語彙ガード (STEP 3) の上に
  思想的原則 (F-12-B-1) を重ねる構造が機能している事実が、どこにも
  明文化されていない。
- **出典**: 引き継ぎプロンプト v3 / configs/prompts/analysis/geo_lens/ 参照
- **ステータス**: `昇格候補(DECISION_LOG)` (構造を整理して登録すべき)

### 2026-05-01: ★最優先 — 不変原則 2「script_writer.py 一切変更不可」が実装と乖離
- **内容**: BATCH_PROTOCOL.md (および各バッチプロンプト) に記載の
  不変原則 2「script_writer.py 一切変更不可」が、実装の現状と乖離している。
  実装は F-12-A / F-12-B / Batch 5 で大改修済み:
    - `generate_script_with_analysis` (新ルートのエントリポイント)
    - `ScriptWithAnalysisDraft` (新スキーマ)
    - `_AXIS_TO_PATTERN_HINT` (axis → pattern マッピング)
    - `_ANALYSIS_DURATION_PROFILES` (analysis 用 duration プロファイル)
    - `article_text` パラメータ (article-first 順序逆転対応)
  正しい不変原則 2 は「**既存の `write_script()` / `_PROMPT_TEMPLATE` /
  `_build_script_from_llm()` は触らない、新ルートへの追加・修正は OK**」。
  本バッチ (F-state-protocol) で BATCH_PROTOCOL.md を修正する。
- **出典**: 引き継ぎプロンプト v3 / src/generation/script_writer.py 実装確認
- **ステータス**: `昇格候補(DECISION_LOG)` ★最優先
  (本バッチで修正実施 → DECISION_LOG.md に「不変原則 2 の正確化」として登録)

### 2026-05-01: 新ルートで target_enemy を排除した設計判断
- **内容**: F-12-A 系で導入された新ルート
  (`generate_script_with_analysis`) では `target_enemy` を意図的に排除
  している。コードコメントには「仮想敵濫用を抑止」と記載されているが、
  この設計判断 (Hydrangea のトーン方針との整合) が DECISION_LOG.md に
  記録されていない。忘れ去られた実装判断の典型例。
- **出典**: 引き継ぎプロンプト v3 / src/generation/script_writer.py の
  新ルート関連コード
- **ステータス**: `昇格候補(DECISION_LOG)`

### 2026-05-01: F-12-B-1.5 (文字数制約緩和) と不変原則 2 の現記述の不整合
- **内容**: F-12-B-1.5 で予定している `_CHAR_BOUNDS` 調整 (文字数制約緩和)
  は、不変原則 2 の現記述「script_writer.py 一切変更不可」だと違反と
  読めてしまう。エントリ #6 と一緒に解消する (新ルート向け or 定数の
  最小改変は許容、と明記)。
- **出典**: 引き継ぎプロンプト v3 / FUTURE_WORK.md の F-12-B-1.5 エントリ
- **ステータス**: `Active` (#6 と一括解消)

### 2026-05-01: FUTURE_WORK の F-7-α (perspective_extractor 改善) が既に部分実装済み
- **内容**: FUTURE_WORK.md に「F-7-α: perspective_extractor 改善」として
  登録されている内容のうち、以下が既に実装完了している:
    - silence_gap OR 条件 3 パターン化
    - hidden_stakes 段階的閾値
    - cultural_blindspot region+source ホワイトリスト経路
    - 4 軸全部不成立時のフォールバック観点
      (`_build_fallback_perspective`)
  FUTURE_WORK.md のエントリの方が古く、整合性が取れていない。
- **出典**: 引き継ぎプロンプト v3 / src/analysis/perspective_extractor.py 確認
- **ステータス**: `昇格候補(FUTURE_WORK)` (FUTURE_WORK.md 該当エントリの
  完了済みへの移動 + 残作業の再整理)

### 2026-05-02: クラウド誤り 1 — NG リスト・Tier 分類で機械制御提案
- **内容**: F-12-B-1 のスコープ議論で、クラウドが「禁止表現リスト Tier 1:
  直訳調 / Tier 2: 抽象比喩 / Tier 3: 硬い文語」を script_writer プロンプトに
  NG リストとして組み込む提案をした。カズヤが「無理だから、考え方で制御したい」で
  軌道修正。LLM の判断を信頼、抽象的原則で方向性を示すべきというカズヤの哲学。
  機械的なリスト管理は形骸化する。
- **出典**: 過去 transcript Session 18 (2026-05-01) / 引き継ぎプロンプト
- **ステータス**: `Active` (将来の俺が同じ誤りを繰り返さない安全装置として記録)

### 2026-05-02: クラウド誤り 2 — 「これを真似ろ」テンプレ過剰押し付け
- **内容**: F-12-B-1 議論で、クラウドが「優れた具体例 A/B/C を提示、これらを
  参考にするように指示、さらに『こう書きなさい』テンプレを 5 個用意」を提案。
  カズヤが「いちいち制御する話じゃない、感想だよ」で軌道修正。カズヤの
  「感想」と「命令」を区別する必要。例示は最小限、原則は抽象的に。
  「絶妙なフレーズ」(電気代という形で) は登録するが「フレーズリスト」化はしない。
- **出典**: 過去 transcript Session 18 (2026-05-01) / 引き継ぎプロンプト
- **ステータス**: `Active`

### 2026-05-02: クラウド誤り 3 — 直近のチャットしか振り返らず過去経緯無視
- **内容**: F-13.B 完了後の総決算依頼でクラウドが直近の Phase A.5-3a だけ
  整理した。カズヤから「最近のやり取りばかり整理されてない？昔のやり取りとか
  やってきたこととか積み残しの課題とかこれから検討が必要な内容も含めて完全に
  抜けもれなく整理してほしい」と叱責。過去 18 transcript すべてを参照する責任、
  「忘れ去られた約束」を絶対忘れない仕組みを使う必要。
- **出典**: 過去 transcript Session 18 (2026-05-01) / 引き継ぎプロンプト
- **ステータス**: `Active` (F-state-protocol が本誤りへの根本治療)

### 2026-05-02: クラウド誤り 4 — F-doc-protocol 結果見落とし
- **内容**: F-doc-protocol 完了後、クラウドが「待ってる」発言をしたが、
  実はカズヤは既に貼っていた。カズヤから「だからさっきも貼ったんだってばっっっｍ」と叱責。
  ユーザーの送ったメッセージは漏らさず確認する、同じ内容を 2 回貼らせない、
  チャット履歴を雑に読まない。
- **出典**: 過去 transcript Session 18 (2026-05-01) / 引き継ぎプロンプト
- **ステータス**: `Active`

### 2026-05-02: 三角測量にハマらないパターンへの対応未実装
- **内容**: カズヤが Apr 28 に提起したが未対応の問題。Hydrangea の三角測量
  (西側 vs 東側 vs 日本) にハマらない記事のパターンが 4 種類:
  A. 西側のみで報じてる (東側無視)
  B. 東側のみで報じてる (西側無視)
  C. 報道のされ方が「3 軸」じゃなく「N 軸」
  D. グローバルサウス特有 (西側も東側も無視)
  これらの処理ロジックが未実装。Phase 1-A or A.5-4 で対応検討。
- **出典**: 過去 transcript Session 7-9 (2026-04-28) / 引き継ぎプロンプト
- **ステータス**: `昇格候補(FUTURE_WORK)` (Phase 1-A 着手時に対応エントリ追加)

### 2026-05-02: 3 ソース対比ルール部分実装
- **内容**: Hydrangea ミッション本丸の 1 つ「同一事象について異なる視点・論調の 3 つの
  ソースを必ず対比、プロパガンダ系メディアは『ロシア国営』等明示」が
  プロンプトベースでは存在するが、安定的に 3 ソース対比を確保するロジックは
  未実装。試運転 7-K (cls-7bd1406438b6 FIFA) では 4 ソース対比達成したが
  再現性は未保証。Phase 1-A or A.5-4 で強化検討。
- **出典**: 過去 transcript / architecture_decisions.md / 引き継ぎプロンプト
- **ステータス**: `昇格候補(FUTURE_WORK)` (Phase 1-A 着手時に対応エントリ追加)

### 2026-05-02: Phase B 以降の方向性は未確定 (本命 geo_lens 動画自動投稿、その先は様子見)
- **内容**: Phase A.5-3d で geo_lens (政治・経済) の自動投稿が安定稼働した後の
  方向性は、現時点で本命と選択肢の 3 択に整理:

  - **本命 (確定)**: geo_lens 動画自動投稿 (Phase A.5-3d) を完成 → 安定稼働
  - **その先の選択肢 (運用結果次第)**:
    - 動画継続 (geo_lens の TikTok / YouTube Shorts 投稿を主軸として継続)
    - 独自メディア (Web / Substack / note 等への記事配信展開)
    - 手動 note・LinkedIn 投稿 (完全自動化を諦めるオプション、新チャネルは
      手動から始める柔軟性確保)

  Phase A.5-3d の運用結果 (フォロワー獲得 / バイラル発生率 / 収益性 / 競合状況) を
  見ながら判断。当初想定していた japan_athletes / k_pulse 並行展開や
  カテゴリ細分化、SaaS 化は、現時点では明示的な選択肢から後退
  (運用結果次第で再浮上の可能性)。

- **拡張性確保 (2026-05-03 議論で確定)**: Phase A.5-3c 拡張性原則の力点は
  「ChannelConfig YAML 化」と「Publisher 抽象」の 2 つで必要十分。
  Content Format 抽象化や マルチテナント DB 設計は過剰 (記事は既に高品質
  Markdown で出ているため、Web メディア展開は UI に流し込むだけで足りる)。
- **出典**: カズヤとの議論 (2026-05-02 + 2026-05-03)
- **ステータス**: `Active` (Phase A.5-3d 安定稼働後に再評価、判断時点で
  DECISION_LOG 昇格)

### 2026-05-02: 仕組み導入時の機械的踏襲リスク

- **内容**: F-state-protocol で CURRENT_STATE.md / DISCUSSION_NOTES.md /
  BATCH_PROTOCOL Task 4/5 を導入した際、当時の引き継ぎプロンプトに記載されていた
  「連続 main マージ成功カウント」を意義を再検討せず機械的に転記した。
  結果、後日カズヤの「なんの意味があるの?」という問いで指標自体が無意味と判明、
  F-cleanup-merge-streak で削除した (DECISION_LOG 参照)。

  教訓:
  - 仕組み導入時、既存の数値・指標を「これまで使われていたから」で機械的に
    踏襲しない
  - 各指標について「これは何の意思決定に使うか?」を必ず問う
  - 答えられない指標は導入しない (or 既にあれば削除する)
  - F-state-protocol 自体の根幹 (CURRENT_STATE / DISCUSSION_NOTES /
    Task 4/5) は機能しているが、その中の個別項目は定期的に見直し対象

  類似リスク: 今後 F-state-protocol-v2 / 別の仕組み導入時に、再度
  「指標の機械的踏襲」が発生する可能性。バッチ着手時のチェックリストに
  「導入する各指標は意思決定に使えるか?」を加える運用ルール化を検討。

- **出典**: カズヤとの議論 (2026-05-02、F-cleanup-merge-streak 直前)
- **ステータス**: `昇格候補(DECISION_LOG)` または `昇格候補(FUTURE_WORK)`
  (将来の F-state-protocol-v2 着手時に「指標導入チェックリスト」として
  運用ルール化、その時点で DECISION_LOG / FUTURE_WORK に昇格)

### 2026-05-03: クラウド誤り 6 — 過剰拡張性の罠 (Content Format 抽象化の過剰見積もり)
- **内容**: 2026-05-03 の Phase B 5 シナリオ議論で、クラウドが「シナリオ C/D
  (動画 + 独自メディア / 独自メディア軸足) には Content Format 抽象化と Publisher
  抽象が必要」と提案した。カズヤから「記事は既に高品質 Markdown で出ているので、
  Web メディアは UI に流し込むだけ。Content Format 抽象化は不要、Publisher 抽象だけで
  足りる」と訂正。

  教訓:
  - 「将来の柔軟性のため」と称して抽象化レイヤーを増やすと、各シナリオで本当に
    必要な抽象化を見誤る
  - 既存パイプラインの出力 (記事 = Markdown / 動画 = MP4) が完成している場合、
    その出力を「別の出力先に流す」だけで多くのシナリオがカバー可能
  - 抽象化の必要性は「実装先が存在するか」で判断する (Publisher は実装先複数、
    Content Format は実装先 1 つしかないので不要)

  類似リスク: Phase A.5-3c 実装時に「将来のため」と称して過剰な抽象化を入れる誘惑。
  Task F (拡張性差し込み判断ルール) として BATCH_PROTOCOL.md に明文化、構造的に防ぐ。

- **出典**: カズヤとの議論 (2026-05-03)
- **ステータス**: `Active` (将来の俺が同じ誤りを繰り返さない安全装置として記録)

### 2026-05-03: 大規模調査機能 (オンデマンド深掘りパイプライン) のアイデア
- **内容**: 通常運用 (cron 自動 / 短尺動画) とは別に、カズヤが事象を指定して
  大規模調査 → 長尺動画 + 記事を生成する機能を Phase B 以降に追加したい。
  位置付けは「**日本人が知っておくべき教養としての国際的評価**」を提供する機能。

  例: 「2026-05-02 の井上尚弥対中谷潤人の試合について、海外ではどのくらいの
  規模で報道されているか、世界の新聞・メディア・権威ある専門誌の報道内容と
  取り扱いの大きさを広く深く調査して整理」

  通常運用との対比:
  - 起動: cron 自動 vs カズヤ手動指定
  - 入力: RSS 41 媒体 vs カズヤ指定事象
  - 調査範囲: 直近 24-48h vs 世界中の専門メディア含めて広く深く
  - 出力: 80 秒縦型 vs 長尺動画 + 深掘り記事
  - 時間制約: run あたり数分 vs 「時間かかってもいい」

  Hydrangea コアミッションとの関係:
  本機能は **系統 2 (報道差の背景解説) を特定事象についてオンデマンドで深掘り
  する機能** = コアミッションの本流であって派生機能ではない (コアミッション
  2 系統並立の詳細は別エントリ「Hydrangea コアミッション 2 系統並立」参照)。
  日常運用 (cron 自動 / 短尺動画) では時間制約で薄い解説しかできないが、
  本機能ではフル深さで実装できる。

  井上 vs 中谷の例で見ると:
  - 「海外でどのくらい報じられているか」= 報道規模の差 (系統 1 の反転的側面)
  - 「権威あるボクシング誌の報道内容」= 海外専門メディアの視点・論調 (系統 2 の核心)
  - 「広く深く調査して整理」= 報道差の背景にある文化・産業・地政学的構造の解説
    = まさに「日本人が知っておくべき教養としての国際的評価」の提供

  実装上の主要論点 (Phase 設計時に詰める):
  1. Web 検索 API の本格活用 (Brave / Serper / Tavily 等、Grounding だけでは薄い可能性)
  2. 長尺動画フォーマット設計 (16:9 横型 5-15 分、番組構成)
  3. コスト構造 (通常 $1-3/本 → 長尺 $10-50/本)
  4. 既存パイプライン再利用範囲 (article_writer / script_writer の長尺ルート追加)
  5. 権威ある専門誌の動的発見ロジック (ジャンル別 YAML or LLM 動的発見)
  6. 中間レポート → カズヤレビュー → 動画/記事生成の 2 ステップフロー

  Phase 配置: Phase B 以降の **新しい選択肢の 1 つ** として追加。他の選択肢
  (動画継続 / 独自メディア / 手動 note・LinkedIn 投稿) と両立可能で排他ではない。
  Phase A.5-3d 安定稼働後の運用結果次第で優先順位判断。
  想定工数 2-4 週間、Phase B 期間 (3-6 ヶ月後)。

- **出典**: カズヤとの議論 (2026-05-03、F-doc-cleanup 投入中の雑談)
- **ステータス**: `Active` (Phase A.5-3d 安定稼働後に再評価、判断時点で
  DECISION_LOG 昇格)

### 2026-05-03: ★最重要 — Hydrangea コアミッション 2 系統並立 (系統 1 中心理解の訂正)
- **内容**: Hydrangea のコアミッションは「日本で報じられない海外ニュースを届ける」
  という単一系統ではなく、**2 系統並立** であることをカズヤが明示的に訂正した。

  **系統 1: 日本未報道の大ニュース (silence_gap)**
  - 日本で報じられていない海外大ニュースを日本人に届ける
  - F-13.B の `has_jp_coverage=False` 判定で blind_spot_global として動画化するパス
  - 実装は完成済み (rescue 完全廃止、Web 検証導入済み)

  **系統 2: 報道差の背景解説 (framing_inversion + 構造分析)**
  - 日本/西側 vs 海外/東側 の報道差を取り上げる
  - その差の背景にある **地政学的理由 / 文化的歴史的背景 / 政治的意図 / 利害構造** を解説する
  - 「日本人が知っておくべき教養としての国際的評価」を提供するメディアとしての本質
  - 実装は部分的 (3 ソース対比ルールが未実装、安定的に確保するロジックが必要)

  **既存構造との関係 (訂正で見え方が変わる箇所)**:
  - `framing_inversion` 軸 (perspective_select_and_verify.md): 単なる論調逆転検出
    ではなく、**系統 2 のミッションそのもの** を担う中核軸
  - `multi_angle_analysis.md` の 5 観点 (geopolitical / political_intent /
    economic_impact / cultural_context / media_divergence): 「報道差の背景解説」
    を構造化するための装置。なぜ 5 観点もあるかは系統 2 を考えれば必然
  - `media_divergence` 観点: 「日本 / 西側 / グローバルサウス」の比較分析が明示的に
    入っている = 系統 2 の実装の核心
  - 3 ソース対比ルール (DISCUSSION_NOTES 既存エントリ、未実装): 系統 2 の核心機能で、
    未実装は Hydrangea ミッション完遂上の重大な欠落

  **クラウド誤り (将来再発防止のため記録)**:
  訂正前のクラウドは系統 1 中心で Hydrangea を理解していて、系統 2 の重要性を
  過小評価していた。これは別チャット移行時に再発する典型パターンとして、
  クラウド誤り 7 として別エントリに登録 (本日同時登録)。

  **将来の波及**:
  - CURRENT_STATE.md / CLAUDE.md / その他 docs のミッション記述が系統 1 寄りに
    なっていないか継続的に確認する必要 (本バッチで CURRENT_STATE.md に
    新セクション「0. Hydrangea コアミッション (2 系統並立)」を冒頭追加して根本治療)
  - 大規模調査機能 (本日同時登録) は系統 2 の本流深掘り機能として位置付けられる
  - 3 ソース対比ルールの実装優先度が再評価される可能性

- **出典**: カズヤの訂正 (2026-05-03)
- **ステータス**: `Active` (★最重要、CURRENT_STATE.md に本バッチで反映済み、
  CLAUDE.md は CURRENT_STATE 参照に統合されているため間接的に反映、
  3 ソース対比未実装の優先度再評価のトリガー)

### 2026-05-03: クラウド誤り 7 — Hydrangea コアミッションを系統 1 中心で理解、系統 2 を過小評価
- **内容**: 2026-05-03 の大規模調査機能議論で、クラウドが Hydrangea コア
  ミッションを「日本で報じられない海外ニュースを届ける」と短絡的にまとめた。
  カズヤから「もちろんそれも重要だが、日本/西側 vs 海外/東側 の報道差の背景を
  地政学・文化・歴史・政治の観点で解説するメディアにしていきたい」と訂正。

  教訓:
  - Hydrangea のコアミッションは **2 系統並立** (系統 1: 日本未報道大ニュース /
    系統 2: 報道差の背景解説)
  - クラウドは系統 1 (silence_gap、F-13.B) の実装が目立つため、それをミッション
    全体と誤認識しがち
  - 系統 2 (framing_inversion + 5 観点解説) は実装上「分析レイヤー」として
    分散しているため、「ミッション本流」として明示的に位置付けないと過小評価される
  - docs に記載されている「日本未報道」「blind_spot」のキーワードが多いため、
    読み込み時に系統 1 中心のフレームで解釈してしまう

  類似リスク:
  - 別チャット移行時、新しいクラウドインスタンスが docs を読み込んで同じ誤りを
    繰り返す可能性が高い
  - 特に CURRENT_STATE.md / CLAUDE.md のミッション記述が系統 1 寄りだと再発確実

  防止策:
  - DISCUSSION_NOTES 同日エントリ「★最重要 — Hydrangea コアミッション 2 系統並立」を
    別途登録 (本日同時登録)
  - CURRENT_STATE.md 冒頭に新セクション「0. Hydrangea コアミッション (2 系統並立)」を
    追加し、新しいクラウドが最初に読むよう構造化 (本バッチで実施)
  - 別チャット移行後の引き継ぎプロンプトで、本誤りの存在を明示的に伝える運用を継続

- **出典**: カズヤの訂正 (2026-05-03)
- **ステータス**: `Active` (将来のクラウドが同じ誤りを繰り返さない安全装置として記録、
  特に新チャット移行時の最重要参照対象)

---

## アーカイブ

(現時点ではアーカイブ済みエントリなし。30 日以上経過 + 状況変化で
意味を失ったエントリをここに移動する。削除はしない、履歴として残す。)
