# Hydrangea — Current State (CURRENT_STATE.md)

最終更新: 2026-05-07 (F-trial-run-post-fix 完了、★ Phase A.5-3a-verify ゲート完了)

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
  `chunk.web.title` 経由の WL マッチングに移行) + ★ 本番動作確認済み
  (F-trial-run-post-fix / 2026-05-07、試運転 6 invocations 5/6 で
  excluded_count > 0 を確認、ドメイン抽出層が本番でも機能していることを証明)

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
- ★ F-trial-run-post-fix で系統 2 ターゲット候補が拡張: golden set 4 件
  (blind_002/004/005/009) + 試運転 7-K 過去動画 2 件 (Slot-1 FIFA Palestine /
  Slot-2 Mandelson Gaza scandal) = 6 件の実例で F-stream-2-filter-design の
  設計妥当性根拠が増強された

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

- **main HEAD コミット**: `fd76660` (本バッチ未マージ、feature/F-trial-run-post-fix 上で作業)
- **直近 5 件のコミットログ**:
  ```
  fd76660 Merge branch 'feature/F-jp-coverage-improve'
  3c8d470 feat: root-cause fix for F-13.B Grounding domain extraction (TP 0→10) + structural exception conditions + Project Knowledge update protocol + Phase A.5-3a-verify gate redefinition (F-jp-coverage-improve)
  b5d571d Merge branch 'feature/F-verify-jp-coverage-measure'
  d23908e feat: measure F-13.B accuracy, verdict=fail, identify root cause (Grounding redirect URL vs web.title) (F-verify-jp-coverage-measure)
  20da7c0 Merge branch 'feature/F-verify-jp-coverage-golden'
  ```
- **baseline テスト数**: `1345 passed` (本バッチで src/ tests/ configs/ への変更なし、`scripts/replay_jp_coverage.py` 新規 + `docs/runs/F-trial-run-post-fix/` 新規 + `docs/` 更新のみ、テスト影響なし、baseline 維持)

## 2. 現在のフェーズ

- **Phase**: Phase A.5-3a-verify **完了** ★ 1-A〜1-D''' 全完了で Phase A.5-3a-verify ゲート完了 (2026-05-07)
- **進行中バッチ**: なし (F-trial-run-post-fix 完了直後、main マージ待ち)
- **次バッチ候補と推奨** (★F-trial-run-post-fix / 2026-05-07 で更新):
  - **1st: F-stream-2-filter-design** (★最優先、系統 2 用 2 段階フィルタ実装、
    Phase A.5-3a-verify ゲート完了で着手 OK 状態に、4-6 時間)
  - **2nd: Phase A.5-3b 手動 PoC 着手準備** (image-prompt-spec を 3b 最初の作業に
    組み込み、フィルタは事前確定済みで PoC に集中)
  - 別系 (任意): **F-jp-coverage-tune** (★高、再測定 verdict=fail の残課題 = Recall/
    Precision/Tier 一致率閾値達成、3-5 時間、Phase A.5-3a-verify ゲート完了の必須
    条件ではない、F-stream-2-filter-design と並走可)
  - 並走: F-verify-perspective / F-verify-script-quality
    (3b/3c 中にデータ収集、判断は 3b/3c 完了後 = データ収集性格)
- **推奨フロー**:
  - F-stream-2-filter-design 完了 → Phase A.5-3b 手動 PoC 着手 → 3c 自動化
    (F-elevenlabs-integration / F-image-gen-integration / F-video-compose-integration /
    F-cron) → Phase A.5-3d で投稿前ゲート + 自動投稿
  - 並走: F-jp-coverage-tune (任意、F-stream-2-filter-design と並列可)

### Phase A.5-3a-verify ロードマップ (★F-trial-run-post-fix / 2026-05-07 完了版)

**ゲート完了**: 1-A〜1-D''' 全段階完了で Phase A.5-3a-verify ゲート完了。
1-E 以降は Phase A.5-3a-verify 後の次フェーズ (= F-stream-2-filter-design 着手)
として再開。

| 段階 | バッチ | 状態 | 概要 |
|---|---|---|---|
| 1-A | F-verify-jp-coverage-golden | ✅ 完了 (2026-05-03) | ゴールデンセット 20 件作成 |
| 1-B | カズヤレビュー (人手) | ✅ 完了 (2026-05-04) | 5 件件ごと判断完了 |
| 1-C | F-verify-jp-coverage-golden-fix | ✅ 完了 (2026-05-04) | 真値修正 + 4 軸 stream-1 基準明文化 + メディア宣言反映 + 2 段階フィルタ設計確定 |
| 1-D | F-verify-jp-coverage-measure | ✅ 完了 (2026-05-05) | F-13.B 精度実測 → verdict=fail、構造的不具合 (Grounding redirect URL vs web.title) を特定 |
| 1-D' | F-jp-coverage-improve | ✅ 完了 (2026-05-07) | F-13.B 構造的不具合の根本治療 (ドメイン抽出レイヤー追加) + 計測再実行 + 不変原則例外条件構造化 + Project Knowledge 運用ルール化 |
| 1-D'' | (1-D' 内で完結) | ✅ 完了 (2026-05-07) | 修正後 verify_jp_coverage_measure.py 再実行で構造的不具合解消を確認 (TP=0→10, FN=14→4)、ただし精度閾値未達は F-jp-coverage-tune に分離 |
| 1-D''' | **F-trial-run-post-fix** | ✅ **完了 (2026-05-07)** | 修正後 F-13.B の本番試運転 + 過去判定後追い、構造的不具合解消の本番動作確認 (excluded_count 非ゼロ)、防衛機構 5 層全機能、試運転 7-K 過去動画 3 件中 2 件が stream_2_candidate パターンと判明 |
| **★ ゲート完了** | — | ✅ **2026-05-07** | 1-A〜1-D''' 全完了で Phase A.5-3a-verify ゲート完了正式宣言 |
| 1-E | F-stream-2-filter-design | ★着手 OK | 系統 2 用 2 段階フィルタ実装、Phase A.5-3b の前提 |
| 別系 | F-jp-coverage-tune | ★高 (任意、F-stream-2-filter-design と並走可) | 再測定 verdict=fail の精度閾値達成 (Recall/Precision/Tier 一致率)、Phase A.5-3a-verify ゲート完了の必須条件ではない |
| 2 | F-verify-perspective | 並走候補 | axis 分布集計 (3b/3c 中) |
| 3 | F-verify-script-quality | 並走候補 | NG 語彙頻度 / リトライ率集計 (3b/3c 中) |

注: 1-D' 内に 1-D'' (計測再実行) を統合する設計とした (修正と検証は分離不能)。
1-D''' (F-trial-run-post-fix、本バッチで完了) で Phase A.5-3a-verify ゲート完了
正式宣言。F-jp-coverage-tune は精度閾値達成の別系で、ゲート完了の必須条件ではない
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
| **2026-05-07** | **F-trial-run-post-fix** | 1/3 動画化 (Slot-1 のみ) + 3 articles | 修正後 F-13.B が本番で機能 (excluded_count 1/10/3 非ゼロでドメイン抽出層が稼働)、3 Slot 全 has_jp_coverage=False、防衛機構 5 層全機能、WebSearch 後追いで Slot-1 (Insider trading) は Tier 1-2 報道済み = Recall miss (F-jp-coverage-tune の対象)、過去 7-K 動画 3 件のうち 2 件が typical stream_2_candidate パターンと判明 |
| 7-K | F-13.B | 100% (3/3) | FIFA + Gaza×2、rescue path 完全廃止後初の全 Slot 動画化成功 — ★ ただし F-13.B 構造的不具合 (常に False 返却) で全 Slot が blind_spot ルートに進んだだけと再解釈。F-trial-run-post-fix で WebSearch 後追い実施、3 件中 2 件 (FIFA / Mandelson) が実は Tier 1-2 報道済みと判明 |
| F-12-B-1 | F-12-B-1 | — | cls-56c4197b6fd2 米イスラエル隠密作戦、視聴者ファースト改善確認 (固有名詞補足・話し言葉化) |
| F-12-B-1-extension | F-12-B-1-extension | 未実施 | LLM 出力依存のため未実施、抽象比喩軽減は継続観察項目 |
| 7-J | F-15 / F-16-A | 0% | rescue 発動で動画化ゼロ → F-13-B (rescue 完全廃止) のトリガー |

## 4. Hydrangea コンセプト防衛機構の現状 (5 層)

| 層 | バッチ | 場所 | 役割 | 状態 |
|---|---|---|---|---|
| F-1 | F-1 / F-1.5 | EditorialMissionFilter | 編集ミッション適合度で score 算出 (>= 45.0 で通過) | ✅ 稼働中 (F-trial-run-post-fix 試運転で 18/364 通過確認) |
| F-2 | F-2 / F-5 | FlagshipGate (Hydrangea コンセプト整合) | 海外発の重要ニュースを優先 | ✅ 稼働中 (F-trial-run-post-fix 試運転で Blocked 0 件確認) |
| F-13.B | F-13.B / F-jp-coverage-improve / F-trial-run-post-fix | JpCoverageVerifier (rescue 完全廃止 + Web 検証 + ドメイン抽出レイヤー) | JP 報道カバレッジを 27 ドメイン WL で検証 | ✅ **構造的不具合修正完了** (F-jp-coverage-improve / 2026-05-07): ドメイン抽出レイヤー (`_extract_domain_from_chunk` / `_looks_like_domain` / `_normalize_domain`) を SDK 変更耐性の防御層として追加、`chunk.web.title` 経由で実ドメインを WL マッチングに供給、`chunk.web.uri` (Vertex redirect URL) は debug 用に分離記録。再測定で TP=0→10, FN=14→4。**+ 本番動作確認済み** (F-trial-run-post-fix / 2026-05-07): 試運転 6 invocations (試運転 3 + replay 3) で excluded_urls_count > 0 が 5/6 件 (1/10/3/0/5/4) を確認、ドメイン抽出層の本番動作証明。残課題 (Recall/Precision/Tier 一致率閾値) は F-jp-coverage-tune に分離 (Phase A.5-3a-verify ゲート完了の必須条件ではない) |
| F-5 | F-5 | FlagshipGate 下流救済 | 上流ガードを通過した候補の最終整合 | ✅ 稼働中 (F-trial-run-post-fix 試運転で救済発火 0 件、Elite Judge Gate 3 で十分採用) |
| **F-13 (隠れ層)** | F-13 / F-doc-cleanup | script_writer.py:951-985 quality_floor_miss bypass | analysis_result 等が成立すれば appraisal の [抑制] を上書き | ✅ 稼働中 (F-trial-run-post-fix 試運転で bypass 発火 0 件、3 Slot 全て floor 通過) |

## 5. 触ってよい / 触ってはいけない領域マップ

### 触ってよい領域
- `configs/prompts/` 配下全般 (主戦場: `configs/prompts/analysis/geo_lens/`)
- `docs/` 配下全般 (CURRENT_STATE / DISCUSSION_NOTES / DECISION_LOG /
  FUTURE_WORK / BATCH_PROTOCOL 等の更新)
- `tests/` 配下に新規テストファイル追加 (既存ファイルは原則変更しない、
  ただし API contract 整合化に伴うフィクスチャ更新は許容、
  例: F-jp-coverage-improve で `_make_grounding_response` を整合化)
- `scripts/` 配下に新規スクリプト追加 (例: `verify_jp_coverage_measure.py`,
  `replay_jp_coverage.py`)
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
  F-jp-coverage-tune に分離)
- **「負の遺産残さないように」** — 不整合・乖離を早期解消
  (F-doc-cleanup で F-13 隠れ層昇格 + DECISION_LOG 7 遡及 + CLAUDE.md 全面書き直し)
- **「カズヤの手作業はバッチプロンプトのコピペ 1 回のみ」** — 引き継ぎ
  プロンプト 2806 行の手作業再構築を排除する仕組みとして CURRENT_STATE.md /
  DISCUSSION_NOTES.md を導入
- **「過剰拡張性の罠」** — 「将来のため」の抽象化前倒しは見送る
  (BATCH_PROTOCOL「拡張性差し込み判断ルール」3 条件 / 2026-05-03)
- **「動くものを壊さない」** — F-jp-coverage-improve で構造的不具合修正後も
  本番試運転 + 過去判定後追い (F-trial-run-post-fix) を必須段階として組み込み、
  本バッチで完了

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
 F-jp-coverage-improve (2026-05-07) で F-13.B 構造的不具合の根本治療を実施。
 F-trial-run-post-fix (2026-05-07) で修正後 F-13.B の本番試運転 + 過去判定
 後追いを実施: 試運転 6 invocations のうち 5/6 で excluded_urls_count > 0 を
 確認 (ドメイン抽出層の本番動作証明)、防衛機構 5 層全機能確認、試運転 7-K
 過去動画化 3 件のうち 2 件 (FIFA / Mandelson) が典型的 stream_2_candidate
 パターンと判明 (golden set 4 件 + 試運転 7-K 2 件 = 6 件で系統 2 設計の
 妥当性根拠拡張)、修正後 F-13.B での過去 7-K 再判定で 3 件全て False→False
 判定不変だが excluded_count 非ゼロで構造機能 OK。Recall miss 1/3 は
 F-jp-coverage-tune の主要課題と完全整合 (本バッチでは記録のみ、根本治療は
 別系)。本バッチ完了で **Phase A.5-3a-verify ゲート完了** (1-A〜1-D''' 全完了)
 を正式宣言、F-stream-2-filter-design 着手 OK 状態に。本バッチは src/ tests/
 configs/ 変更なし (新規スクリプト + docs/runs/ + docs/ のみ)、baseline 1345
 passed 維持。
 ★ Project Knowledge 最新化リマインダ: 本バッチ完了は **Phase A.5-3a-verify
 ゲート完了の節目** (1-D''' 完了)、新チャット移行前にカズヤが手動で claude.ai
 の Project Knowledge を **必須最新化** することを推奨 (BATCH_PROTOCOL の
 Project Knowledge 運用ルールに従う)。
 過去の経緯は DECISION_LOG.md / FUTURE_WORK.md / DISCUSSION_NOTES.md を参照。*
