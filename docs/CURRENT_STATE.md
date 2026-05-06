# Hydrangea — Current State (CURRENT_STATE.md)

最終更新: 2026-05-07 (F-jp-coverage-improve 完了時点)

> このドキュメントは Hydrangea の「今この瞬間のスナップショット」。
> 各バッチ完了時に Claude Code が **全置換更新** する (追記ではない)。
> 過去の経緯は DECISION_LOG.md / FUTURE_WORK.md / DISCUSSION_NOTES.md を参照。

---

## 0. Hydrangea コアミッション (2 系統並立)

> ★最重要: 別チャット移行時のクラウド誤り再発防止のため冒頭配置 (F-doc-cleanup-followup / 2026-05-03)。
> 系統 1 中心で理解して系統 2 を過小評価する誤りはクラウド誤り 7 として記録済み。

Hydrangea のコアミッションは **2 系統並立** で、片方だけでは Hydrangea のメディア性が成立しない。

### 系統 1: 日本未報道の大ニュース (silence_gap)

日本で **構造的に** 報じられていない海外大ニュースを日本人に届ける。

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

実装機構:
- F-13.B JpCoverageVerifier で `has_jp_coverage=False` を判定 → blind_spot_global
  として動画化
- 「未報道理由の構造性」判定は別レイヤー (LLM 判断 or 上流の素材選定) で担当
- DISCUSSION_NOTES「系統 1 (silence_gap) の判定基準明確化」参照
- 実装: rescue 完全廃止 + Web 検証導入済み (F-13.B / 2026-05-01) + 構造的不具合
  根本治療済み (F-jp-coverage-improve / 2026-05-07、ドメイン抽出レイヤー追加で
  `chunk.web.title` 経由の WL マッチングに移行)

### 系統 2: 報道差の背景解説 (framing_inversion + 構造分析)

日本/西側 vs 海外/東側 の報道差を取り上げ、その差の背景にある **地政学的理由 /
文化的歴史的背景 / 政治的意図 / 利害構造** を解説する。

「日本人が知っておくべき教養としての国際的評価」を提供するメディアとしての本質。

- `framing_inversion` 軸 (perspective_select_and_verify.md): 系統 2 を担う中核軸
- `multi_angle_analysis.md` の 5 観点 (geopolitical / political_intent /
  economic_impact / cultural_context / media_divergence): 報道差の背景を構造化
- `media_divergence` 観点: 日本 / 西側 / グローバルサウス の比較分析
- 実装は部分的: 3 ソース対比ルールが未実装 (系統 2 の核心機能の重大な欠落、
  DISCUSSION_NOTES「3 ソース対比ルール部分実装」参照)

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

- **main HEAD コミット**: `b5d571d` (本バッチ未マージ、feature/F-jp-coverage-improve 上で作業)
- **直近 5 件のコミットログ**:
  ```
  b5d571d Merge branch 'feature/F-verify-jp-coverage-measure'
  d23908e feat: measure F-13.B accuracy, verdict=fail, identify root cause (Grounding redirect URL vs web.title) (F-verify-jp-coverage-measure)
  20da7c0 Merge branch 'feature/F-verify-jp-coverage-golden'
  069c318 docs: create golden set v1.1 with truth values fixed + 4-axis stream-1 criteria + Hydrangea media manifesto + F-stream-2-filter-design plan (F-verify-jp-coverage-golden + F-verify-jp-coverage-golden-fix combined)
  b61d3f5 Merge branch 'feature/F-doc-cleanup-followup'
  ```
- **baseline テスト数**: `1345 passed` (2026-05-07 F-jp-coverage-improve 時点で確認、本バッチで `tests/test_jp_coverage_verifier_domain_extract.py` 28 テスト + 既存テストフィクスチャ整合化に伴う追加カウント = 1315 → 1345 で全 passed 維持)

## 2. 現在のフェーズ

- **Phase**: Phase A.5-3a 完了 → A.5-3a-verify **進行中**
  (1-D' F-jp-coverage-improve 完了で構造的不具合解消、1-D''' F-trial-run-post-fix
  着手前。verdict は再測定でも fail のため精度閾値達成は F-jp-coverage-tune に分離)
- **進行中バッチ**: なし (F-jp-coverage-improve 完了直後、main マージ待ち)
- **次バッチ候補と推奨** (★F-jp-coverage-improve / 2026-05-07 で更新):
  - **1st: F-trial-run-post-fix** (★★最優先、修正後 F-13.B の本番試運転 +
    過去判定後追い、Phase A.5-3a-verify ゲート完了の最終段階、2-3 時間)
  - **2nd: F-jp-coverage-tune** (★高、再測定 verdict=fail の残課題 = Recall/
    Precision/Tier 一致率閾値達成、3-5 時間、F-trial-run-post-fix 完了後着手)
  - **3rd: F-stream-2-filter-design** (★最優先、系統 2 用 2 段階フィルタ実装、
    F-trial-run-post-fix 完了後着手再開、Phase A.5-3b の前提、4-6 時間)
  - **4th: Phase A.5-3b 手動 PoC 着手** (image-prompt-spec を 3b 最初の作業に
    組み込み、フィルタは事前確定済みで PoC に集中)
  - 並走: F-verify-perspective / F-verify-script-quality
    (3b/3c 中にデータ収集、判断は 3b/3c 完了後 = データ収集性格)
- **推奨フロー**:
  - F-trial-run-post-fix 完了 (Phase A.5-3a-verify ゲート完了確定) →
    F-jp-coverage-tune (任意、精度閾値達成) → F-stream-2-filter-design 完了 →
    Phase A.5-3b 手動 PoC 着手 → 3c 自動化 (F-elevenlabs-integration /
    F-image-gen-integration / F-video-compose-integration / F-cron) →
    Phase A.5-3d で投稿前ゲート + 自動投稿

### Phase A.5-3a-verify ロードマップ (★F-jp-coverage-improve / 2026-05-07 更新版)

**ゲート完了条件**: 1-A 〜 1-D''' まで全て完了で Phase A.5-3a-verify ゲート完了。
1-E 以降は Phase A.5-3a-verify 後の次フェーズ (= F-stream-2-filter-design 着手)
として再開。

| 段階 | バッチ | 状態 | 概要 |
|---|---|---|---|
| 1-A | F-verify-jp-coverage-golden | ✅ 完了 (2026-05-03) | ゴールデンセット 20 件作成 |
| 1-B | カズヤレビュー (人手) | ✅ 完了 (2026-05-04) | 5 件件ごと判断完了 |
| 1-C | F-verify-jp-coverage-golden-fix | ✅ 完了 (2026-05-04) | 真値修正 + 4 軸 stream-1 基準明文化 + メディア宣言反映 + 2 段階フィルタ設計確定 |
| 1-D | F-verify-jp-coverage-measure | ✅ 完了 (2026-05-05) | F-13.B 精度実測 → verdict=fail、構造的不具合 (Grounding redirect URL vs web.title) を特定 |
| 1-D' | **F-jp-coverage-improve** | ✅ 完了 (2026-05-07) | F-13.B 構造的不具合の根本治療 (ドメイン抽出レイヤー追加) + 計測再実行 + 不変原則例外条件構造化 + Project Knowledge 運用ルール化 |
| 1-D'' | (1-D' 内で完結) | ✅ 完了 (2026-05-07) | 修正後 verify_jp_coverage_measure.py 再実行で構造的不具合解消を確認 (TP=0→10, FN=14→4)、ただし精度閾値未達は F-jp-coverage-tune に分離 |
| 1-D''' | **F-trial-run-post-fix** | ★着手前 | 修正後 F-13.B の試運転 + 既存試運転データ (7-K 等) の修正後 F-13.B での再判定 + 過去動画化 3 件の WebSearch 後追い確認 |
| 1-E | F-stream-2-filter-design | 着手前 (1-D''' 完了後) | 系統 2 用 2 段階フィルタ実装、Phase A.5-3b の前提 |
| 別系 | F-jp-coverage-tune | ★高 (1-D''' 完了後) | 再測定 verdict=fail の精度閾値達成 (Recall/Precision/Tier 一致率)、Phase A.5-3a-verify ゲート完了の必須条件ではない |
| 2 | F-verify-perspective | 並走候補 | axis 分布集計 (3b/3c 中) |
| 3 | F-verify-script-quality | 並走候補 | NG 語彙頻度 / リトライ率集計 (3b/3c 中) |

注: 1-D' 内に 1-D'' (計測再実行) を統合する設計とした (修正と検証は分離不能)。
1-D''' (試運転バッチ) は別バッチ F-trial-run-post-fix として後日投入。
F-jp-coverage-tune は精度閾値達成の別系で、ゲート完了の必須条件ではない
(構造的不具合解消で F-stream-2-filter-design の前提条件は確保されている)。

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
| 7-K | F-13.B | 100% (3/3) | FIFA + Gaza×2、rescue path 完全廃止後初の全 Slot 動画化成功 — ★ ただし F-13.B 構造的不具合 (常に False 返却) で全 Slot が blind_spot ルートに進んだだけと再解釈。F-trial-run-post-fix で WebSearch 後追い確認予定 |
| F-12-B-1 | F-12-B-1 | — | cls-56c4197b6fd2 米イスラエル隠密作戦、視聴者ファースト改善確認 (固有名詞補足・話し言葉化) |
| F-12-B-1-extension | F-12-B-1-extension | 未実施 | LLM 出力依存のため未実施、抽象比喩軽減は継続観察項目 |
| 7-J | F-15 / F-16-A | 0% | rescue 発動で動画化ゼロ → F-13-B (rescue 完全廃止) のトリガー |
| 7-I | F-16-A | 67% (2/3) | Slot-3 (UAE OPEC) が MAX_PUBLISHES_PER_DAY で skip → F-16-A 着手 |

## 4. Hydrangea コンセプト防衛機構の現状 (5 層)

| 層 | バッチ | 場所 | 役割 | 状態 |
|---|---|---|---|---|
| F-1 | F-1 / F-1.5 | EditorialMissionFilter | 編集ミッション適合度で score 算出 (>= 45.0 で通過) | ✅ 稼働中 |
| F-2 | F-2 / F-5 | FlagshipGate (Hydrangea コンセプト整合) | 海外発の重要ニュースを優先 | ✅ 稼働中 |
| F-13.B | F-13.B / F-jp-coverage-improve | JpCoverageVerifier (rescue 完全廃止 + Web 検証 + ドメイン抽出レイヤー) | JP 報道カバレッジを 27 ドメイン WL で検証 | ✅ **構造的不具合修正完了** (F-jp-coverage-improve / 2026-05-07): ドメイン抽出レイヤー (`_extract_domain_from_chunk` / `_looks_like_domain` / `_normalize_domain`) を SDK 変更耐性の防御層として追加、`chunk.web.title` 経由で実ドメインを WL マッチングに供給、`chunk.web.uri` (Vertex redirect URL) は debug 用に分離記録。再測定で TP=0→10, FN=14→4 と構造的不具合は解消、ただし verdict=fail のまま (Recall covered 71.43% / Precision blind 42.86% / F1 0.769 / Tier 一致率 30%)。残課題は F-jp-coverage-tune に分離、F-trial-run-post-fix で本番試運転 + 過去判定後追い予定 |
| F-5 | F-5 | FlagshipGate 下流救済 | 上流ガードを通過した候補の最終整合 | ✅ 稼働中 |
| **F-13 (隠れ層)** | F-13 / F-doc-cleanup | script_writer.py:951-985 quality_floor_miss bypass | analysis_result 等が成立すれば appraisal の [抑制] を上書き | ✅ 稼働中 (F-doc-cleanup / 2026-05-03 で正式 5 層目に昇格、DECISION_LOG / EDITORIAL_MISSION_FILTER_DESIGN.md に明文化) |

## 5. 触ってよい / 触ってはいけない領域マップ

### 触ってよい領域
- `configs/prompts/` 配下全般 (主戦場: `configs/prompts/analysis/geo_lens/`)
- `docs/` 配下全般 (CURRENT_STATE / DISCUSSION_NOTES / DECISION_LOG /
  FUTURE_WORK / BATCH_PROTOCOL 等の更新)
- `tests/` 配下に新規テストファイル追加 (既存ファイルは原則変更しない、
  ただし API contract 整合化に伴うフィクスチャ更新は許容、
  例: F-jp-coverage-improve で `_make_grounding_response` を整合化)
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
  F-jp-coverage-improve でドメイン抽出レイヤーを SDK 変更耐性の防御層として実装)
- **「負の遺産残さないように」** — 不整合・乖離を早期解消
  (F-doc-cleanup で F-13 隠れ層昇格 + DECISION_LOG 7 遡及 + CLAUDE.md 全面書き直し)
- **「カズヤの手作業はバッチプロンプトのコピペ 1 回のみ」** — 引き継ぎ
  プロンプト 2806 行の手作業再構築を排除する仕組みとして CURRENT_STATE.md /
  DISCUSSION_NOTES.md を導入
- **「過剰拡張性の罠」** — 「将来のため」の抽象化前倒しは見送る
  (BATCH_PROTOCOL「拡張性差し込み判断ルール」3 条件 / 2026-05-03)
- **「動くものを壊さない」** — F-jp-coverage-improve で構造的不具合修正後も
  本番試運転 + 過去判定後追い (F-trial-run-post-fix) を必須段階として組み込む

## 8. 関連ドキュメントへの導線

- 過去の決定の経緯 → `docs/DECISION_LOG.md`
- 残課題リスト → `docs/FUTURE_WORK.md`
- 議論中の未確定メモ → `docs/DISCUSSION_NOTES.md`
- バッチ運用ルール → `docs/BATCH_PROTOCOL.md` (不変原則例外条件 + Project Knowledge 運用ルール含む)
- アーキテクチャ全体像 → `docs/ARCHITECTURE.md`
- 技術的負債リスト → `docs/TECH_DEBT.md`
- リファクタ計画 (歴史的記録) → `docs/REFACTORING_PLAN.md`
- 編集ミッションフィルタ設計 (F-13 隠れ層含む) → `docs/EDITORIAL_MISSION_FILTER_DESIGN.md`
- Claude Code 振る舞い指針 → `CLAUDE.md`

---

*このドキュメントは F-state-protocol (2026-05-01) で導入。
 Claude Code がバッチ完了時に全置換更新する運用 (BATCH_PROTOCOL.md Task 5 参照)。
 F-jp-coverage-improve (2026-05-07) で F-13.B 構造的不具合の根本治療を実施:
 ドメイン抽出レイヤー (`_extract_domain_from_chunk` / `_looks_like_domain` /
 `_normalize_domain`) を SDK 変更耐性の防御層として追加、`_search_with_grounding()`
 を修正して `chunk.web.title` 経由で実ドメインを WL マッチングに供給、不変原則 3
 例外適用 (4 条件全て満たすことを確認)、計測再実行で TP=0→10 / FN=14→4 と構造的
 不具合は解消、ただし精度閾値未達のため verdict=fail のまま (残課題は F-jp-coverage-tune
 に分離)。BATCH_PROTOCOL.md に「不変原則の例外条件」セクション (4 条件 + 例外不可
 ケース + 過去事例) と「Project Knowledge 最新化運用ルール」セクション (必須/推奨
 タイミング + 最新化対象 + 注意事項) を新設。Phase A.5-3a-verify ロードマップを
 1-A〜1-D''' 構成に再定義 (1-D'' を 1-D' 内統合、1-D''' に F-trial-run-post-fix を
 配置)。新規 28 テスト追加 + 既存テストフィクスチャの API contract 整合化、
 baseline 1315 → 1345 全 passed 維持。
 ★ Project Knowledge 最新化リマインダ: 本バッチ完了は Phase A.5-3a-verify ゲート
 完了の節目 (1-D' 完了)、新チャット移行前にカズヤが手動で claude.ai の Project
 Knowledge を最新化することを推奨。
 過去の経緯は DECISION_LOG.md / FUTURE_WORK.md / DISCUSSION_NOTES.md を参照。*
