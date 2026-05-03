# Hydrangea — Current State (CURRENT_STATE.md)

最終更新: 2026-05-04 (F-verify-jp-coverage-golden-fix 完了時点)

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
- 実装: rescue 完全廃止 + Web 検証導入済み (F-13.B / 2026-05-01)

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

- **main HEAD コミット**: `b61d3f5`
- **直近 5 件のコミットログ**:
  ```
  b61d3f5 Merge branch 'feature/F-doc-cleanup-followup'
  bcf3577 docs: reflect 2026-05-03 discussion results + add core mission 2-stream section (F-doc-cleanup-followup)
  3e817d8 Merge branch 'feature/F-doc-cleanup'
  e34f36e docs: cleanup doc debt before Phase A.5-3a-verify (F-doc-cleanup)
  eaa0ac1 Merge branch 'feature/F-cleanup-merge-streak'
  ```
- **baseline テスト数**: `1315 passed` (2026-05-03 F-doc-cleanup-followup 時点で確認、F-verify-jp-coverage-golden は docs のみで src/tests/configs 0 行変更のため維持)

## 2. 現在のフェーズ

- **Phase**: Phase A.5-3a 完了 → A.5-3a-verify **進行中**
  (F-verify-jp-coverage 第 1 段階 + 真値修正完了)
- **進行中バッチ**: なし (F-verify-jp-coverage-golden-fix 完了直後、
  main マージ待ち)
- **次バッチ候補と推奨** (F-verify-jp-coverage-golden-fix / 2026-05-04 で確定):
  - **1st: F-verify-jp-coverage-measure** (★最優先、ゴールデンセット使った
    F-13.B 精度測定、2-3 時間、ゲート性格)
  - **2nd: F-stream-2-filter-design** (★最優先、系統 2 用 2 段階フィルタ実装、
    4-6 時間、Phase A.5-3b の前提)
  - **3rd: Phase A.5-3b 手動 PoC 着手** (image-prompt-spec を 3b 最初の作業に
    組み込み、フィルタは事前確定済みで PoC に集中)
  - 並走: F-verify-perspective / F-verify-script-quality
    (3b/3c 中にデータ収集、判断は 3b/3c 完了後 = データ収集性格)
- **推奨フロー**:
  - F-verify-jp-coverage-measure 合格 + F-stream-2-filter-design 完了 →
    Phase A.5-3b 手動 PoC 着手 → 3c 自動化 (F-elevenlabs-integration /
    F-image-gen-integration / F-video-compose-integration / F-cron) →
    Phase A.5-3d で投稿前ゲート + 自動投稿

### Phase A.5-3a-verify ロードマップ (F-verify-jp-coverage-golden-fix / 2026-05-04 更新)

| 段階 | バッチ | 状態 | 概要 |
|---|---|---|---|
| 1-A | F-verify-jp-coverage-golden | ✅ 完了 (2026-05-03) | ゴールデンセット 20 件作成 |
| 1-B | カズヤレビュー (人手) | ✅ 完了 (2026-05-04) | 5 件件ごと判断完了 |
| 1-C | F-verify-jp-coverage-golden-fix | ✅ 完了 (2026-05-04) | 真値修正 + 4 軸判定基準明文化 + メディア宣言反映 + 2 段階フィルタ設計確定 |
| 1-D | **F-verify-jp-coverage-measure** | 着手前 | F-13.B 精度測定 (TP/FP/TN/FN)、ゲート判定 |
| 1-E | **F-stream-2-filter-design** | 着手前 | 系統 2 用 2 段階フィルタ実装、Phase A.5-3b の前提 |
| 2 | F-verify-perspective | 並走候補 | axis 分布集計 (3b/3c 中) |
| 3 | F-verify-script-quality | 並走候補 | NG 語彙頻度 / リトライ率集計 (3b/3c 中) |

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
| 7-K | F-13.B | 100% (3/3) | FIFA + Gaza×2、rescue path 完全廃止後初の全 Slot 動画化成功 |
| F-12-B-1 | F-12-B-1 | — | cls-56c4197b6fd2 米イスラエル隠密作戦、視聴者ファースト改善確認 (固有名詞補足・話し言葉化) |
| F-12-B-1-extension | F-12-B-1-extension | 未実施 | LLM 出力依存のため未実施、抽象比喩軽減は継続観察項目 |
| 7-J | F-15 / F-16-A | 0% | rescue 発動で動画化ゼロ → F-13-B (rescue 完全廃止) のトリガー |
| 7-I | F-16-A | 67% (2/3) | Slot-3 (UAE OPEC) が MAX_PUBLISHES_PER_DAY で skip → F-16-A 着手 |

## 4. Hydrangea コンセプト防衛機構の現状 (5 層)

| 層 | バッチ | 場所 | 役割 | 状態 |
|---|---|---|---|---|
| F-1 | F-1 / F-1.5 | EditorialMissionFilter | 編集ミッション適合度で score 算出 (>= 45.0 で通過) | ✅ 稼働中 |
| F-2 | F-2 / F-5 | FlagshipGate (Hydrangea コンセプト整合) | 海外発の重要ニュースを優先 | ✅ 稼働中 |
| F-13.B | F-13.B | JpCoverageVerifier (rescue 完全廃止 + Web 検証) | JP 報道カバレッジを 27 ドメイン WL で検証 | ✅ 稼働中 |
| F-5 | F-5 | FlagshipGate 下流救済 | 上流ガードを通過した候補の最終整合 | ✅ 稼働中 |
| **F-13 (隠れ層)** | F-13 / F-doc-cleanup | script_writer.py:951-985 quality_floor_miss bypass | analysis_result 等が成立すれば appraisal の [抑制] を上書き | ✅ 稼働中 (F-doc-cleanup / 2026-05-03 で正式 5 層目に昇格、DECISION_LOG / EDITORIAL_MISSION_FILTER_DESIGN.md に明文化) |

## 5. 触ってよい / 触ってはいけない領域マップ

### 触ってよい領域
- `configs/prompts/` 配下全般 (主戦場: `configs/prompts/analysis/geo_lens/`)
- `docs/` 配下全般 (CURRENT_STATE / DISCUSSION_NOTES / DECISION_LOG /
  FUTURE_WORK / BATCH_PROTOCOL 等の更新)
- `tests/` 配下に新規テストファイル追加 (既存ファイルは原則変更しない)
- `src/triage/` に新規ファイル追加 (例: `jp_coverage_verifier.py`)
- `src/generation/script_writer.py` の **新ルート**
  (`generate_script_with_analysis` / `ScriptWithAnalysisDraft` /
  `_AXIS_TO_PATTERN_HINT` / `_ANALYSIS_DURATION_PROFILES` / `article_text` 等)
- `src/generation/script_writer.py` の `_CHAR_BOUNDS` 等の定数 (最小改変なら許容)

### 触ってはいけない領域
- `src/generation/article_writer.py` (不変原則 1)
- `src/generation/script_writer.py` の **既存ルート**
  (`write_script` / `_PROMPT_TEMPLATE` / `_build_script_from_llm`) (不変原則 2)
- `src/triage/` の既存ファイル (不変原則 3)
- `src/analysis/` 配下全般 (不変原則 4、F-12-B-2 着手時に例外条項追加検討)
- 既存テスト (不変原則 5、baseline 1315 passed 維持)

## 6. 不変原則 5 つ (リマインダ、正本: BATCH_PROTOCOL.md)

1. **`src/generation/article_writer.py` 一切変更不可**
2. **`src/generation/script_writer.py` の既存ルート (`write_script` /
   `_PROMPT_TEMPLATE` / `_build_script_from_llm`) は変更不可**。
   新ルート (`generate_script_with_analysis` 系) への追加・修正は OK。
   `_CHAR_BOUNDS` 等の定数調整も最小改変なら許容。
   **例外**: `configs/prompts/` 配下のプロンプトファイルは変更可、
   主戦場は `configs/prompts/analysis/geo_lens/`
3. **`src/triage/` の既存ファイル変更不可**。新規追加は OK
   (例: `jp_coverage_verifier.py`)
4. **`src/analysis/` 変更不可** (F-12-B-2 axis 多様化着手時に例外条項追加検討)
5. **既存テスト破壊しない** (baseline 1315 passed)

## 7. カズヤの直近フィードバック要点

- **「中間が良い」** — シニカル一辺倒でも生活実感一辺倒でもなく、両立
  (F-12-B-1-extension で punchline 定義を「シニカル × 具体着地」両立に)
- **「考え方で制御」** — NG リスト方式は廃止、原則ベースのプロンプト
  (F-12-B-1 で「視聴者ファースト 3 原則」として導入)
- **「対症療法じゃなくて根本治療」** — 仕組みで再発防止
  (F-doc-protocol / F-state-protocol / F-doc-cleanup 等の文書プロトコル整備の動機)
- **「負の遺産残さないように」** — 不整合・乖離を早期解消
  (F-doc-cleanup で F-13 隠れ層昇格 + DECISION_LOG 7 遡及 + CLAUDE.md 全面書き直し)
- **「カズヤの手作業はバッチプロンプトのコピペ 1 回のみ」** — 引き継ぎ
  プロンプト 2806 行の手作業再構築を排除する仕組みとして CURRENT_STATE.md /
  DISCUSSION_NOTES.md を導入
- **「過剰拡張性の罠」** — 「将来のため」の抽象化前倒しは見送る
  (BATCH_PROTOCOL「拡張性差し込み判断ルール」3 条件 / 2026-05-03)

## 8. 関連ドキュメントへの導線

- 過去の決定の経緯 → `docs/DECISION_LOG.md`
- 残課題リスト → `docs/FUTURE_WORK.md`
- 議論中の未確定メモ → `docs/DISCUSSION_NOTES.md`
- バッチ運用ルール → `docs/BATCH_PROTOCOL.md`
- アーキテクチャ全体像 → `docs/ARCHITECTURE.md`
- 技術的負債リスト → `docs/TECH_DEBT.md`
- リファクタ計画 (歴史的記録) → `docs/REFACTORING_PLAN.md`
- 編集ミッションフィルタ設計 (F-13 隠れ層含む) → `docs/EDITORIAL_MISSION_FILTER_DESIGN.md`
- Claude Code 振る舞い指針 → `CLAUDE.md`

---

*このドキュメントは F-state-protocol (2026-05-01) で導入。
 Claude Code がバッチ完了時に全置換更新する運用 (BATCH_PROTOCOL.md Task 5 参照)。
 F-state-protocol-supplement (2026-05-02) で「次バッチ候補」セクションを最小更新し、
 Phase A.5-3a-verify ロードマップを反映。
 F-doc-backfill (2026-05-02) で過去 19 セッション分の積み残しを正式登録、
 Phase A.5-3a-verify を 5→4 カテゴリに縮小、ElevenLabs 前倒しと Remotion 採用を
 DECISION_LOG に記録、ロードマップを 4 段階 (3a-verify → 3b → 3c → 3d) に再構成。
 F-doc-backfill-supplement (2026-05-02) で画像生成候補を ChatGPT Images 2.0
 (gpt-image-2) に確定、Phase A.5-3d 投稿対象を geo_lens 単独 + TikTok/YouTube
 同時 + 完全自動に明確化、拡張性原則 (Phase A.5-3c 設計時) を DECISION_LOG に追加。
 F-cleanup-merge-streak (2026-05-02) で「連続 main マージ成功カウント」を
 削除 (情報ノイズ・悪いインセンティブ排除)、main HEAD と直近 5 件ログを
 最新値に更新。
 F-doc-cleanup (2026-05-03) で文書負債の一括根本治療を実施: F-13 隠れ層を防衛機構の
 正式 5 層目に昇格 (4+1 → 5 層化、⚠️ 削除)、DECISION_LOG 遡及記録 7 エントリ追加
 (F-13 / F-13.B / F-15 / F-16-A / F-12-A / F-12-B / F-14)、CLAUDE.md 全面書き直し
 (Claude Code 振る舞い指針に集約、重複セクション排除)、REFACTORING_PLAN.md
 アーカイブ注記、2026-05-03 議論結果の docs 反映 (Phase B 3 択構造、Phase A.5-3a-verify
 順序見直し、クラウド誤り 6 追加)、BATCH_PROTOCOL に拡張性差し込み判断ルール新設。
 F-doc-cleanup-followup (2026-05-03) で 2026-05-03 議論結果を完全反映: DISCUSSION_NOTES に
 3 エントリ追加 (大規模調査機能 / ★最重要 コアミッション 2 系統並立 / クラウド誤り 7)、
 CURRENT_STATE.md 冒頭に新セクション「0. Hydrangea コアミッション (2 系統並立)」を追加
 (別チャット移行時のクラウド誤り 7 再発防止のため最重要事項を冒頭配置)。
 F-verify-jp-coverage-golden (2026-05-03) で Phase A.5-3a-verify 第 1 段階完了:
 docs/runs/F-verify-jp-coverage/golden_set.json (20 entries valid JSON、blind 10 +
 covered 10、kazuya_review_required 5 件) 作成、F-13.B JpCoverageVerifier の
 真値判定独立性を確保 (F-13.B 自体を呼ばず WebSearch で独立検証)、F-verify-jp-coverage
 を 2 段階分割 (golden 完了 → カズヤレビュー → measure 着手) に再構成、Phase A.5-3a-verify
 ロードマップに 1-A/1-B/1-C 表を新設。F-13.B 動作仕様の検討課題 (タイトルクエリで広範な
 事件を引き当てる構造、MEE 記事の核心 = 特定構造分析角度の判定不能性) を DISCUSSION_NOTES
 に新エントリで提起。
 F-verify-jp-coverage-golden-fix (2026-05-04) でカズヤレビュー結果を反映: golden_set.json
 v1.0 → v1.1 で 5 件真値修正 (4 件 True 化 + 1 件削除、blind 9 + covered 10 = 19 件構成) +
 stream_2_candidate メタ追加、系統 1 (silence_gap) 判定基準を「未報道理由の構造性」として
 4 軸構造で明文化 (制度・システム面 / 外交・経済・利害関係面 / 個人・権力者面 / 関心領域・
 地政学的死角)、Hydrangea のメディア宣言「忖度、報道規制、報道の自由度の低さをぶち壊そう」
 を docs に固定化、F-13.B の役割を系統 1 専用と確定 + F-stream-2-filter-design (系統 2 用
 2 段階フィルタ) を Phase A.5-3b 前に独立実装する Phase 配置確定。Phase A.5-3a-verify
 ロードマップに 1-C / 1-D / 1-E 段階を追加。CURRENT_STATE セクション 0 (コアミッション)
 の系統 1 説明を 4 軸 + メディア宣言を含む強化版に全置換 (系統 2 / ブランドポジション /
 3 チャンネル構想は不変)。*
