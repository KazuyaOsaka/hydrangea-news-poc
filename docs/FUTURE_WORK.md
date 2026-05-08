# Hydrangea — 将来対応リスト (FUTURE_WORK)

最終更新: 2026-05-08 (F-task-e-finalize 完了、Task E カズヤレビュー結果反映 +
finalize_annotations.py 実行)

このドキュメントは「今は対応せず、将来検討・対応すべき項目」を記録する。各バッチ完了時に新しい項目が追加され、対応完了したら「完了済み」セクションに移動する。

---

## 緊急度 高（次のフェーズで必ず対応）

各項目は以下の形式で記載:
- **タイトル** (発生バッチ)
  - 背景: なぜこれが必要か
  - 対応案: どう対応するか
  - 検討時期: いつ判断するか
  - 関連ファイル: 影響を受けるファイル

---

- **F-12-B-2: perspective_extractor の axis 多様化** (F-13-B 完了後)
  - 背景: F-13-B 試運転で AnalysisLayer の selected_perspective が "cultural_blindspot" 等の限定的 axis に集中しがち。blind_spot_global 候補に適した axis (例: power_dynamics_blindspot, structural_silence) の不足が観察される。
  - 対応案: `src/analysis/perspective_extractor.py` の axis 定義を拡張し、Hydrangea ミッション本丸に対応する新 axis を追加。
  - 検討時期: F-12-B-1 完了後 (= 2026-05-01 完了済) → 次バッチで着手判断

- **event_builder.py のガード変更** (E-1 で見送り)
  - 背景: 現状 `if garbage_filter_client is not None:` でガードしているため、API キー未設定時に静的ルールが走らない
  - 対応案: `if GARBAGE_FILTER_ENABLED:` に変更し、API キー無しでも静的ルールを動作させる
  - 検討時期: 触っちゃダメリスト見直しと同時
  - 関連ファイル: src/ingestion/event_builder.py (touch-禁止リスト掲載中)

- **触っちゃダメリスト（CLAUDE.md）の見直し** (E-1 完了後に発覚)
  - 背景: ハイブリッド版になって event_builder.py の garbage_filter 周辺は触ってOK。scoring.py も新 axis 追加が必要になる可能性
  - 対応案: 各ファイルの「なぜ触ってはいけないか」を明示し、状況依存で触ってよい範囲を定義
  - 検討時期: Phase 1.5 全完了後

- **perspective_extractor 改善 (F-7-α 候補)** (試運転 7-G で発覚 / F-14 で関連事象を観測)
  - 背景: Slot-1 (cls-8bbec722d420 Venezuela) で `no perspective candidates met conditions → analysis_result=None` が再発。`extract_perspectives()` のルールベース判定が厳しすぎ、政治系イベントでも候補ゼロになるケースがある。F-14 は JSON parser を堅牢化したが、そもそも候補が抽出されないケースは救えない。
  - 対応案: `src/analysis/perspective_extractor.py` の各 axis 判定条件を緩和、または最低 1 件の候補を必ず返す保険ロジック (lowest-bar fallback) を追加。
  - 検討時期: F-12-B (script_writer プロンプト全面刷新) 完了後
  - 関連ファイル: src/analysis/perspective_extractor.py, tests/test_perspective_extractor.py

- **AnalysisLayer LLM の max_tokens / 切れ防止 (F-14 で workaround 済)** (F-14 / 試運転 7-G で発覚)
  - 背景: F-14 で JSON parser の修復ロジックを実装し、出力が途中で切れた場合でも可能な限り救済できるようになった。ただし根本原因は LLM 出力の途中切断 (max_tokens 制限 / Tier フォールバック中の長い応答) であり、F-14 は対症療法。
  - 対応案: (a) AnalysisLayer の `multi_angle_analyzer` / `insight_extractor` に `max_output_tokens` の明示指定を追加し、十分な余裕を確保する。(b) Tier 別に max_output_tokens を調整。(c) 出力長を抑えるプロンプト改修 (短く・JSON だけ生成させる)。
  - 検討時期: 試運転 7-H で F-14 修復ログ ([F-14] JSON repaired) の発動頻度を確認後。発動が多発するなら根本対応に着手。
  - 関連ファイル: src/llm/factory.py, src/analysis/multi_angle_analyzer.py, src/analysis/insight_extractor.py, configs/prompts/analysis/

- **EditorialMissionFilter Step1 prescore の軸スコアゼロ問題** (F-1.5 試運転で発覚)
  - 背景: F-1.5 試運転で発覚。軍事費・ゼレンスキー等の地政学記事で `editorial:geopolitics_depth_score` / `editorial:breaking_shock_score` / `editorial:mass_appeal_score` が 0.0 になっていた。本来高得点になるはずの記事が低 prescore で却下される/低位置に置かれる懸念
  - 対応案: `src/triage/scoring.py` の `compute_score_full()` を読み、各 axis 計算ロジックを確認。修正には scoring.py を触る必要があるため、触っちゃダメリスト見直しと一緒に対処
  - 検討時期: F-1.5 完了後の次のバッチ
  - 関連ファイル: src/triage/scoring.py（読み取り）, src/triage/editorial_mission_filter.py

- **cron 6 時間おき自動実行の整備 (F-16-B)** (F-16-A で per-run 上限分離後の本番リリース要件)
  - 背景: F-16-A で per-run 上限を `TOP_N_VIDEOS_PER_RUN` / `TOP_N_ARTICLES_PER_RUN` に分離した。本番運用は cron 6 時間おき × per-run 上限で公開頻度を制御する設計だが、cron 設定自体は未実装。
  - 対応案: GitHub Actions / launchd / VPS のいずれかで `python -m src.main --mode normalized` を 6 時間おきに実行。失敗時通知、ログローテーション、batch ロックの整備も同時。本番想定値: 4 run/日 × 1 動画/run = 4 動画/日 + 4 run × 3 記事 = 12 記事/日。
  - 検討時期: F-16-A 試運転 7-J で動画化率 100% を確認後、本番リリース判断時
  - 関連ファイル: 新規 `.github/workflows/run-pipeline.yml` または `launchd/*.plist` または systemd unit, src/main.py (CLI 引数追加の可能性)

- **ChannelConfig.publishing_limits 統合 (Phase 1-A)** (F-16-A で per-run 上限を環境変数化)
  - 背景: F-16-A は `TOP_N_VIDEOS_PER_RUN` / `TOP_N_ARTICLES_PER_RUN` をグローバル env で持つ暫定実装。Phase B で TikTok / Shorts / Web 別チャンネルや `japan_athletes` / `k_pulse` を稼働させる際は、チャンネル単位で上限を変えられる必要がある。
  - 対応案: `ChannelConfig` (src/shared/models.py) に `publishing_limits: PublishingLimits` を追加し、`videos_per_run` / `articles_per_run` を持たせる。main.py 側で env 読み込みからチャンネル設定読み込みに移行。env は deprecation 期間を経て撤廃。
  - 検討時期: Phase 1-A (REFACTORING_PLAN.md 段階 2) 着手時
  - 関連ファイル: src/shared/models.py, configs/channels.yaml, src/main.py, .env.example

### Phase A.5-3a-verify (F-state-protocol-supplement / 2026-05-02 登録、F-jp-coverage-improve / 2026-05-07 で順序更新、F-trial-run-post-fix / 2026-05-07 でゲート完了)

**Phase 順序 (★更新版、2026-05-07 F-trial-run-post-fix 完了後 = ゲート完了)**:

```
[完了] F-jp-coverage-improve (F-13.B 構造的不具合修正)
  ↓ 修正後 verify_jp_coverage_measure.py 再測定で構造的不具合は解消
    (TP=10/14, FN=4 vs 修正前 TP=0/14, FN=14)、verdict=fail のまま
[完了] F-trial-run-post-fix (修正後 F-13.B の本番試運転 + 過去判定後追い)
  ↓ 構造的不具合解消の本番動作確認 (excluded_count 非ゼロ)、防衛機構 5 層全機能、
    試運転 7-K 過去動画 3 件 WebSearch 後追いで stream_2_candidate パターン確認
★ Phase A.5-3a-verify ゲート完了 (1-A〜1-D''' 全完了) ★
  ↓
F-stream-2-filter-design (★着手 OK、系統 2 用 2 段階フィルタ実装)
  → Phase A.5-3b 手動 PoC (フィルタ確定済みで PoC に集中)

別系 (任意、並走可):
  F-jp-coverage-tune (Recall/Precision/Tier 一致率の閾値達成、ゲート完了の必須条件ではない)
```

★ F-trial-run-post-fix (2026-05-07 完了) で F-jp-coverage-improve の修正が
本番運用で機能していることを確認 (試運転 6 invocations のうち 5/6 で
excluded_urls_count > 0、ドメイン抽出層の本番動作証明)。試運転 7-K 過去動画化
3 件のうち 2 件 (Slot-1 FIFA / Slot-2 Mandelson) は WebSearch では Tier 1-2
報道済みと判明 = 典型的 stream_2_candidate パターン (golden set v1.1
blind_002/004/005/009 と同形)。Phase A.5-3a-verify ゲート完了の根拠が確保された。
F-stream-2-filter-design 着手 OK 状態に。

並走候補: F-verify-perspective / F-verify-script-quality (3b/3c 中にデータ収集)

- **F-jp-coverage-tune** ★最優先 (F-jp-coverage-improve / 2026-05-07 で派生、F-trial-run-post-fix / 2026-05-07 で本番再現性確認、F-particular-angle-redesign / 2026-05-08 で **二段階クエリ生成設計が確定 + 真値 25 件整備で優先度上昇**、F-particular-angle-redesign-extension / 2026-05-08 で **系統名 1/2/3 整理 + sontaku_signals メタデータ整備済みで設計確度更に向上**、再測定 verdict=fail の残課題対応 + 系統 1 vs 系統 2 機械判別)
  - 背景: F-jp-coverage-improve (2026-05-07) で F-13.B 構造的不具合を修正し、計測再実行で構造的不具合は解消したが、4 指標とも閾値未達のため verdict=fail のまま (Recall covered 71.43% < 90%, Precision blind 42.86% < 80%, F1 0.769 < 0.85, Tier 一致率 30% < 70%)。残課題は構造的不具合とは別の問題群で、F-jp-coverage-improve の責務範囲外として本バッチに分離した。F-trial-run-post-fix (2026-05-07) で本番試運転を実施し、3 Slot のうち Slot-1 (Insider trading: Oil and stocks jolt on news of US-Iran deal) は WebSearch で Tier 1 (nikkei.com)、Tier 2 (jiji.com、bloomberg.co.jp) で広範報道済みを確認したが F-13.B は Recall miss、Grounding API が youtube.com 偏重の結果を返す (英語タイトル + 「日本 報道」クエリ品質問題) ことを **本番でも再現** した。試運転 6 invocations の excluded URLs は全て youtube.com (計 23 件)。
  - 想定対応軸:
    1. **FN (4 件) の Recall 改善**: Grounding API が Tier 1-2 ソースを返さないクエリ最適化 (`_build_search_query` の改善、検索クエリに「NHK 朝日 日経 ロイター」等の WL ドメイン名ヒントを混ぜる、件名を要約する等)、または WL ドメイン拡張。★ F-trial-run-post-fix で本番再現性確認、最優先課題
    2. **英語タイトルクエリの日本語化**: F-trial-run-post-fix で観測された「英語タイトル + 『日本 報道』では Grounding が youtube.com 偏重」問題への対処。LLM で英語タイトルから日本語キーワードを抽出してクエリを構築する案
    3. **FP (2 件、両方 diamond.jp) の Precision 改善**: ゴールデン真値再評価 (diamond.jp が実際に該当事象を報じていたかの再確認)、または Tier 4 重み付け (diamond.jp / newsweekjapan / toyokeizai を Tier 1 並みに信頼するか議論)
    4. **Tier 一致率 30% の改善**: Grounding が Tier 4 (newsweekjapan / toyokeizai / diamond) を Tier 1 より先に返す傾向を観測。`_match_whitelist` の Tier 判定ロジックは複数 Tier 同時マッチ時に highest_tier を採用しているが、API レスポンス自体に Tier 1 が含まれない場合は Tier 4 のみ。クエリ改善で Tier 1 ソースを引き当てる方が根本解
  - 前提: ★ F-trial-run-post-fix 完了済み (2026-05-07) + ★ F-particular-angle-design 完了済み (2026-05-07、「特定角度」概念 docs + 25 件アノテーション) + ★ **F-particular-angle-redesign 完了済み (2026-05-08、3 分類 → 4 分類化 + 二段階クエリ生成設計確定 + broad_event_jp_coverage / particular_angle_jp_coverage 真値整備)** → 即着手可能
  - 対応軸への補強 (F-particular-angle-design / 2026-05-07 + F-particular-angle-redesign / 2026-05-08 で確立): (1) **二段階クエリ生成** = 広範事件クエリ (title + 「NHK 朝日 日経」等の WL ドメインヒント) + 特定角度クエリ (`particular_angle.core_question` を LLM で日本語キーワードに圧縮)。両者を独立に Grounding 検索することで系統 1 (両方未報道) vs 系統 1.5 (広範のみ報道) の機械的判別が可能。(2) **真値整備済み**: `docs/runs/F-particular-angle-design/annotations.json` (4 分類版) の各 event に `broad_event_jp_coverage` (reported / unreported / unknown) と `particular_angle_jp_coverage` (同) フィールドが付与されている。これは F-jp-coverage-tune の二段階クエリ各々の精度評価に使える 25 件の真値データ。
  - 検討時期: ★最優先 (F-particular-angle-redesign で二段階クエリ生成の設計基盤 + 真値 25 件が確定、F-stream-2-filter-design の責務スコープがカズヤレビュー次第で縮小する可能性があるため、本バッチ着手の優先度が相対的に上昇)
  - 想定工数: 3-5 時間 (クエリ最適化 + ゴールデン真値再評価 + 計測再々実行 + F-trial-run-post-fix の試運転データで本番再現性も確認)
  - 関連ファイル: `src/triage/jp_coverage_verifier.py` (`_build_search_query` 等のクエリ生成ロジック)、`docs/runs/F-verify-jp-coverage/golden_set.json` (v1.3、Task F カズヤレビュー後 `finalize_annotations.py --schema-version 2.0` で更新予定)、`scripts/verify_jp_coverage_measure.py` (再実行)、`docs/runs/F-trial-run-post-fix/` (本番再現性データ)、`docs/runs/F-particular-angle-design/annotations.json` (4 分類版アノテーション + broad_event_jp_coverage / particular_angle_jp_coverage 真値)、`docs/runs/F-particular-angle-redesign/` 配下 (再分類 diff + log)、`docs/PARTICULAR_ANGLE_DEFINITION.md` (4 分類版判定基準正典)
  - 関連: F-jp-coverage-improve REPORT.md v2 残課題セクション、F-trial-run-post-fix REPORT.md セクション 7.1 (Recall 観点の課題)、F-particular-angle-design REPORT.md セクション 9 (引き継ぎ事項)、F-particular-angle-redesign REPORT.md セクション 8 (二段階クエリ生成への引き継ぎ + 真値整備)

- **F-stream-2-filter-design** ★最優先 (F-verify-jp-coverage-golden-fix / 2026-05-04 で派生、F-verify-jp-coverage-measure / 2026-05-05 で着手保留 → F-jp-coverage-improve / 2026-05-07 で再開条件更新 → ★ F-trial-run-post-fix / 2026-05-07 で着手 OK 状態に)
  - 背景: Hydrangea コアミッション系統 2 (報道差の背景解説) を担う 2 段階フィルタの第 2 段階を実装する。系統 1 (F-13.B) では「広範な事件は報道済み」と弾かれるが、特定の構造分析角度 (地政学・文化・政治の意図) が日本未報道で解説価値ある事象を捕捉する。F-verify-jp-coverage-golden-fix で 4 件 (blind_002/004/005/009) が系統 2 候補として stream_2_candidate メタ付きで識別済み。F-jp-coverage-improve (2026-05-07) 修正後の再測定では stream_2_candidate 4 件中 3 件が True 判定 (blind_005 のみ FN) と動作確認できた。F-trial-run-post-fix (2026-05-07) で試運転 7-K 過去動画化 3 件のうち 2 件 (Slot-1 FIFA / Slot-2 Mandelson) が典型的 stream_2_candidate パターンと判明 (Tier 1-2 報道済みだが MEE オリジナル角度は未報道) → 系統 2 ターゲットの実例が **golden set 4 件 + 試運転 7-K 2 件 = 6 件** に拡大。
  - ★ **責務スコープ要再評価 (2026-05-08 更新、F-particular-angle-redesign + extension)**: F-jp-coverage-improve で構造的不具合解消、F-trial-run-post-fix で本番動作確認済み。Phase A.5-3a-verify ゲート完了 (1-A〜1-D''' 全完了) で着手再開条件達成。F-particular-angle-design (2026-05-07) で「特定角度」概念の正典 docs + 25 件 LLM ベースアノテーションを整備、F-particular-angle-redesign (2026-05-08) で 4 分類化を実施した **結果、LLM 推定段階で stream_3 (旧 stream_2) が 0 件 / stream_2 (旧 stream_1_5) が 20 件という想定外分布が観測された**。F-particular-angle-redesign-extension (2026-05-08) で **系統名 1/2/3 整理 + sontaku_signals メタデータを別軸として独立化** し、本バッチの責務は **系統 3 (framing_inversion) のみ + sontaku_signals.level を解説価値判定の追加軸として参照** に縮減された。系統 2 (perspective_gap、旧 1.5) は F-jp-coverage-tune の二段階クエリ生成範疇に移行。本バッチ着手は ★ **F-particular-angle-redesign のカズヤレビュー (新分類 1/2/3 + sontaku_signals 込み) 結果を待ってから** 判断するのが望ましい。仮にカズヤレビュー後も stream_3 が 1-2 件しかない場合、本バッチは小規模実装で済み (新規 LLM 解説価値判定 1 段のみ + sontaku_signals.level の追加軸組み込み、ゴールデンセットも数件)、F-jp-coverage-tune が **より優先** される構造になる。
  - 共通基盤 (F-particular-angle-design / 2026-05-07 で確立):
    * 「特定角度」を判定単位として、系統 1 / 系統 2 / 対象外の 3 分類論理フロー (Step 1: 4 軸該当 → Step 2: 日本未報道 → Step 3: 解釈差) を `docs/PARTICULAR_ANGLE_DEFINITION.md` で正典化
    * 25 件アノテーション (LLM 推定段階で stream_2=13 件、内訳: blind_005 / blind_008 / covered 系列 9/10 件 / 7-K Slot-1 FIFA / 7-K Slot-2 Mandelson) が系統 2 候補の実例として準備済み
    * `scripts/extract_particular_angle.py` のプロンプト設計 (max_output_tokens=4096、3 要素 + confidence ラベル) が本バッチの解説価値判定 LLM の参考実装として使える
  - 対応案: (1) 既存の framing_inversion 軸 + multi_angle_analysis 5 観点 + media_divergence 観点を統合した「3 ソース対比ルール + 解説価値判定」を新規実装。(2) パイプライン位置は F-13.B の下流 (報道済み判定後)。(3) 系統 2 ターゲット候補に対して LLM が「特定角度の差が存在するか」「解説価値があるか (5 観点のいずれか)」を判定。判定単位は **「特定角度」(F-particular-angle-design で正典化)** に限定する設計を採用。(4) ゴールデンセット v1.2 の `stream_classification` 付き 19 件 + 試運転 6 件 (stream_classification.json) で精度測定。(5) 不変原則順守 (article_writer 変更不可、script_writer 既存ルート変更不可、src/triage/ 既存ファイル変更不可、src/analysis/ 変更不可、新規追加のみ)。
  - 検討時期: F-particular-angle-design 完了後、Phase A.5-3b 着手前 (★PoC は PoC に集中するため、フィルタを事前に確定)
  - 想定工数: 4-6 時間 (新規ロジック実装 + テスト + ゴールデンセット追加)
  - 関連ファイル: src/triage/stream_2_filter.py (新規想定), tests/triage/test_stream_2_filter.py (新規想定), docs/runs/F-stream-2-filter-design/ (新規, ゴールデンセット拡張 + 精度測定レポート), configs/prompts/analysis/geo_lens/ 配下 (3 ソース対比 + 解説価値判定プロンプトを新規追加), docs/PARTICULAR_ANGLE_DEFINITION.md (判定基準正典), docs/runs/F-particular-angle-design/annotations.json (アノテーション参照), docs/runs/F-particular-angle-design/stream_classification.json (系統分類)
  - 関連 DISCUSSION_NOTES: 「系統 1 (silence_gap) の判定基準明確化」「F-13.B 動作仕様の検討課題」「3 ソース対比ルール部分実装」「特定角度抽出の LLM 限界観察」

- **F-verify-perspective** (F-state-protocol-supplement / 2026-05-02 登録、F-doc-cleanup / 2026-05-03 順序見直し)
  - 背景: 4 軸 (cultural_blindspot / silence_gap / hidden_stakes / framing_inversion) のバランスを検証。DISCUSSION_NOTES #6 (F-12-B-2 axis 多様化) の着手判断材料となる。cultural_blindspot 偏重が確認されれば F-12-B-2 起動。
  - 対応案: 直近 50 イベントで axis 分布を集計、cultural_blindspot 偏重があれば F-12-B-2 起動判断。
  - 検討時期: Phase A.5-3b 着手後に並走でデータ収集、判断は 3b/3c 完了後 (データ収集性格、ゲートではない)
  - 想定工数: 集計 1 時間 + 判断議論
  - 関連ファイル: src/analysis/perspective_extractor.py (読み取りのみ), data/output/ の AnalysisLayer 出力

- **F-verify-script-quality** (F-state-protocol-supplement / 2026-05-02 登録、F-doc-cleanup / 2026-05-03 順序見直し)
  - 背景: 新ルート (`generate_script_with_analysis`) の NG パターン出現頻度 / char validation リトライ率を測定。F-12-B-1.5 (文字数制約緩和) 着手判断材料を兼ねる。F-12-B-1 投入後 1 run の試運転では setup 1/1 でリトライ発動だが標本不足。
  - 対応案: 直近 30 件で NG 語彙頻度 / リトライ回数集計、`_CHAR_BOUNDS` 調整可否を判断。
  - 検討時期: Phase A.5-3b 着手後に並走でデータ収集、判断は 3b/3c 完了後 (データ収集性格、ゲートではない)
  - 想定工数: 集計 1 時間 + 判断議論
  - 関連ファイル: src/generation/script_writer.py (読み取りのみ), data/output/ の script.json

- **F-image-prompt-spec** (F-doc-backfill / 2026-05-02 登録、F-doc-backfill-supplement / 2026-05-02 改訂、F-doc-cleanup / 2026-05-03 順序見直し)
  - 背景: Phase A.5-3b 手動 PoC で「自動生成された台本 + 画像プロンプト」を使って Nano Banana Pro / ChatGPT Images 2.0 (gpt-image-2) / Flux 1.1 Pro に画像生成依頼する想定だが、現状 video_payload_writer.py がシーンごとの画像プロンプトを十分な品質で出力しているか未確認。Phase A.5-3b 着手前 or 着手と同時に仕様確認 + 必要なら改修。
  - 対応案: (1) src/generation/video_payload_writer.py の現状調査 (シーンごとに画像プロンプトを出してるか / 統一末尾「cinematic, hyper-realistic, dark geopolitical thriller style, high contrast, dramatic lighting, vertical composition, 9:16 aspect ratio」が含まれてるか) (2) 不十分なら configs/prompts/ 配下のプロンプトファイルを改修 (3) 試運転で画像プロンプト品質を確認
  - 検討時期: Phase A.5-3b 着手の最初の作業として組み込む (3b 直前 or 3b 内、3b 前提性格)
  - 想定工数: 2-3 時間
  - 関連ファイル: src/generation/video_payload_writer.py (調査のみ), configs/prompts/ (必要なら改修)
  - 不変原則整合: video_payload_writer.py は不変原則 1-4 の対象外、必要なら configs/prompts/ 経由で改修可能

### Phase A.5-3c 合成パート自動化 (F-doc-backfill / 2026-05-02 登録)

- **F-elevenlabs-integration** (F-doc-backfill / 2026-05-02 登録)
  - 背景: Phase A.5-3b 手動 PoC で確定した ElevenLabs 声選定を、Hydrangea 自動パイプラインに統合する。macOS say は廃止 (品質低い、Linux 対応の意義なし)。
  - 対応案:
    (1) AudioRenderer 抽象クラス化 (src/generation/audio_renderer.py 改修)
    (2) ElevenLabsRenderer 実装 (API キー + voice_id 設定 + character_alignment 取得)
    (3) configs/audio.yaml で声選定 (geo_lens / japan_athletes / k_pulse 別)
    (4) 既存 say 呼び出し部分を ElevenLabsRenderer に切り替え
    (5) フィーチャーフラグで段階移行 (AUDIO_RENDERER=elevenlabs|say)
  - 検討時期: Phase A.5-3b 完了直後 (声選定確定後)
  - 想定工数: 1 週間
  - 関連ファイル: src/generation/audio_renderer.py, configs/audio.yaml (新規)
  - 不変原則整合: audio_renderer.py は不変原則 1-4 の対象外、改修可能
  - 補足: TECH_DEBT 2.5 (macOS say 依存) は本エントリで解消

- **F-image-gen-integration** (F-doc-backfill / 2026-05-02 登録、F-doc-backfill-supplement / 2026-05-02 改訂)
  - 背景: Phase A.5-3b で選定した画像生成ツール (Nano Banana Pro / ChatGPT Images 2.0 (gpt-image-2) / Flux 1.1 Pro のいずれか) を Hydrangea パイプラインに統合。
  - 対応案:
    (1) ImageGenerator 抽象クラス化 (src/generation/ に新規作成)
    (2) 選定ツールの API クライアント実装
    (3) シーンごとの画像生成ロジック (12-15 枚 / 80 秒動画)
    (4) configs/image_gen.yaml で統一プロンプト末尾 + チャンネル別設定
    (5) 著作権配慮 (Wikimedia Commons + 政府公開画像 + Pexels + AI 生成の組み合わせ、通信社画像は使わない)
  - 検討時期: F-elevenlabs-integration と並行可
  - 想定工数: 1 週間
  - 関連ファイル: src/generation/image_generator.py (新規), configs/image_gen.yaml (新規)
  - 不変原則整合: 新規ファイル追加で既存に影響なし

- **F-video-compose-integration** (F-doc-backfill / 2026-05-02 登録)
  - 背景: Phase A.5-3b で確立した Remotion テンプレートを自動化に適用。現状の Pillow + FFmpeg ベース video_renderer.py は廃止。
  - 対応案:
    (1) Remotion プロジェクトを Hydrangea リポジトリに統合
    (2) Python パイプラインから Remotion CLI を呼ぶブリッジ実装
    (3) 各チャンネル別 Remotion テンプレート (geo_lens 用、後で japan_athletes / k_pulse 用追加)
    (4) Remotion Lambda for 並列レンダリング (Phase B で本格化)
    (5) フィーチャーフラグで段階移行 (VIDEO_RENDERER=remotion|legacy)
  - 検討時期: F-elevenlabs-integration / F-image-gen-integration 完了後
  - 想定工数: 2-3 週間
  - 関連ファイル: remotion/ (新規), src/generation/video_renderer.py (廃止予定), configs/remotion/ (新規)
  - 不変原則整合: video_renderer.py は不変原則 1-4 の対象外、廃止可能

- **F-cron** (F-doc-backfill / 2026-05-02 登録)
  - 背景: 現状はカズヤ手動実行のみ。本番リリース後は 1 日 4 動画 + 12 記事の自動生成が必要。F-16-B (旧 cron 計画) を ElevenLabs / Remotion 前提で再定義。
  - 対応案:
    (1) .github/workflows/hydrangea-pipeline.yml 新規
    (2) cron: 6 時間おき (00:00, 06:00, 12:00, 18:00 JST)
    (3) GitHub Secrets 設定 (GEMINI_API_KEY / ELEVENLABS_API_KEY / 画像生成 API キー / その他)
    (4) ロギング (実行結果を GitHub Issue or Slack に通知、run_summary.json を artifact 保存)
    (5) 環境変数: AUDIO_RENDERER=elevenlabs, VIDEO_RENDERER=remotion
  - 検討時期: F-elevenlabs-integration / F-image-gen-integration / F-video-compose-integration 完了後
  - 想定工数: 2-3 時間
  - 関連ファイル: .github/workflows/hydrangea-pipeline.yml (新規)
  - 不変原則整合: .github/ 配下は src/ 外、既存テスト破壊なし

### Phase A.5-3d 投稿前ゲート + 自動投稿 (F-doc-backfill / 2026-05-02 登録、F-doc-backfill-supplement / 2026-05-02 改訂)

- **Phase A.5-3d 投稿前ゲート + 自動投稿** (F-doc-backfill / 2026-05-02 登録、F-doc-backfill-supplement / 2026-05-02 改訂)
  - 背景: F-cron 完了で「動画自動生成」が動くが、品質保証ゲートと投稿自動化が未実装。
  - 対応案:
    (1) F-publish-gate: 投稿前ゲート実装
        - LLM 自己採点 7 軸 (Hook 強度 / 情報密度 / 価値観揺さぶり / 具体性 / 感情ドライブ / 共有動機 / ループ性、各 3.5 点以上で通過)
        - 文字化け検知 (字幕に不正文字)
        - 無音検知 (音声ファイルの音量ゼロ区間)
        - 不通過はレビューキューに退避、カズヤが定期的に確認
    (2) F-tiktok-api: TikTok Content Posting API 統合 (審査 1-3 週間、早めに申請)
    (3) F-youtube-api: YouTube Data API v3 統合 (即対応可)
    (4) 投稿開始
  - 投稿対象: geo_lens (政治・経済) のみ。japan_athletes / k_pulse は Phase B 以降に判断 (運用結果次第、DISCUSSION_NOTES「Phase B 以降の方向性未確定」参照)
  - 投稿先: TikTok と YouTube Shorts の両方同時 (TikTok は審査 1-3 週間あるので早めに申請、YouTube Data API v3 は即対応可で先行リリース可)
  - 投稿モード: 完全自動投稿 (cron 6 時間おき、人手介入ゼロ)
    - 投稿前ゲート (LLM 自己採点 7 軸 + 文字化け検知 + 無音検知) で品質保証
    - 不通過はレビューキューに退避、定期的にカズヤが確認
  - 拡張性確保: Phase A.5-3c の合成パート自動化実装時、将来の多チャンネル対応 / 別形式展開 (動画以外、独自メディア等) を阻害しない設計とする (configs/channels/{channel_id}.yaml で投稿先 / 形式 / カテゴリを切替可能に。DECISION_LOG「拡張性原則の明文化」参照)
  - 検討時期: F-cron 完了 + 1 週間の自動実行安定確認後
  - 想定工数: 2-3 週間 (TikTok 審査含む)
  - 関連ファイル: src/publishing/ (新規)
  - 不変原則整合: 新規ディレクトリ追加で既存に影響なし

---

## 緊急度 中（実運用データ収集後に判断）

---

- **F-12-B-1.5: 台本 4 ブロック文字数制約の緩和判断** (F-12-B-1 / 2026-05-01 発生)
  - 背景: F-12-B-1 (視聴者ファースト原則追加) により「聞き慣れない固有名詞には最小限の補足を添える」原則が導入された結果、setup ブロックの char validation で 1 リトライが発生 (94 字 → 82 字)。LLM が補足を入れようとして既存制約 (setup 60〜90 字 / twist 150〜220 字 / punchline 70〜110 字) の上限に当たりやすくなる傾向が試運転で確認された。
  - 対応案: (a) リトライ発動頻度を継続観察し、頻発するなら setup 上限を 100 字、twist 上限を 240 字、punchline 上限を 120 字程度に緩和。(b) `src/generation/script_writer.py` の char validation 範囲定数を調整 (script_writer.py 自体は不変原則 2 の対象だが、定数調整は最小改変で許容範囲)。(c) または estimated_duration_sec の許容幅を広げて 80→90 秒運用に移行。
  - 検討時期: F-12-B-1 投入後 5〜10 run の動画化で char validation リトライ率を集計。全 Slot の 30% 以上でリトライが発動するなら緩和着手。現状 (試運転 1 run) は 1/1 で発動したが標本不足のため判断保留。
  - 関連ファイル: src/generation/script_writer.py, configs/prompts/analysis/geo_lens/script_with_analysis.md (文字数指示部)

- **Reality Check Layer (F-10 候補): 「日本で本当に報じられていないか」の検証工程** (F-5 発生)
  - 背景: 現状の blind_spot_global_score は LLM の主観判断であり、実際に日本のメディアをチェックする工程が無い。Hydrangea のコンセプト「日本で報じられない海外ニュースを届ける」の信頼性に直結する。
  - 対応案: editorial_mission_filter 通過後 / EliteJudge 前に「Reality Check Layer」を挿入。LLM ベースの判定（短期）または Web 検索 API ベースの検証（長期）で「実際に日本メディアで報じられていないか」を確認する。
  - 検討時期: F-9 (チャンネル定義 YAML 化) 完了後
  - 関連ファイル: src/triage/, src/main.py, configs/channels.yaml

- **EditorialMissionFilter 閾値の調整** (F-1 で暫定値設定)
  - 背景: F-1 では閾値 45.0 を暫定値として設定。実運用データが溜まったら通過率と選定品質を分析して調整
  - 対応案: 1週間以上の運用データ（通過率・選ばれた記事の質）を分析して閾値を 40〜55 の範囲で再設定
  - 検討時期: F-1 投入後 1〜2週間

- **scoring.py の新 axis 追加** (F-1 設計時に判断)
  - 背景: F-1 で political_intent / hidden_power_dynamics / economic_interests を Step1 で精密計算したいが、scoring.py が触っちゃダメリストにあるため Step2 LLM のみで判定
  - 対応案: 触っちゃダメリスト見直し後、editorial:political_intent_score 等の新 axis を追加して Step1 prescore に組み込む
  - 検討時期: 触っちゃダメリスト見直し後

- **台本品質のアーティクル品質への引き上げ (F-12 候補)** (試運転7-D 発生 / **進行中: F-12-A 完了 / F-12-B 残**)
  - 背景: アーティクル (article.md) は Foreign Affairs 級の名フレーズと深い分析が出るが、台本 (script.json) は文字数制約とブロック分割で表現が硬くなりがち。アーティクルが「移動する主権領土」のような独自言語化を含むのに対し、台本は「物理的限界に達している構造的変化を象徴」のような平凡な表現になる。
  - 対応案:
    - 案A: アーティクル先行生成 → 台本に圧縮 (順序変更) **← F-12-A で実施済み (2026-04-29)**
    - 案B: アーティクルから「金フレーズ」抽出ループ (台本生成時に必ず使う制約) **← F-12-B で実施予定**
    - 案C: 台本のターゲット視聴者明確化 (ReHacQ・PIVOT 視聴層を想定) **← F-12-B で script_writer プロンプト全面刷新時に統合**
  - F-12-A 完了内容: src/main.py の生成順序を `script → article` から `article → script` に逆転。article.markdown を script_writer に `article_text` 引数で参照素材として渡す基盤を整備。article_writer.py は不変（プロンプト・シグネチャ・入力素材いずれも touch していない）。
  - F-12-B 残作業: script_writer プロンプト全面刷新（サマリ型台本 / AI 構文排除リスト / アーティクル独自言語化フレーズの強制使用）。
  - 検討時期: F-12-B は試運転 7-F でアーティクル品質維持を確認後に着手
  - 関連ファイル: src/generation/script_writer.py, src/generation/article_writer.py, src/main.py

- **LLM 結果キャッシュ（E-4）** (Phase 1.5 計画)
  - 背景: 同じ event を2回評価しないようにキャッシュ。デバッグ高速化
  - 対応案: キャッシュキー = event.id + sources_hash + prompt_template_hash
  - 検討時期: E-3' 完了後

- **judge バッチ化（E-3 元案）** (Phase 1.5 計画)
  - 背景: viral/elite/gemini judge を1回の LLM 呼び出しに統合。ただし役割分離は維持
  - 対応案: 各 judge を別プロンプトでバッチ化、統合はしない
  - 検討時期: E-4 完了後

- **FUTURE_WORK.md 月次レビュー** (FW-1 で導入)
  - 背景: 形骸化防止のため、月初または「気のいいタイミング」で全項目を見直す
  - 対応案: 緊急度の再評価、放置項目（高で1ヶ月以上未対応）の対応開始判断、完了済みの整理、新規バッチへの組み込み判断
  - 検討時期: 毎月1日 + 以下のイベントトリガー時
    - 新しい Phase の開始前
    - 主要バッチ完了直後
    - カズヤが「次何やる？」と問うたタイミング
    - 1週間以上 FUTURE_WORK.md が参照されていないと気づいた時
  - 関連ファイル: docs/FUTURE_WORK.md, CLAUDE.md
  - 補足: このレビュー自体も FUTURE_WORK.md の項目として登録されている（自己参照型管理）

### Phase A.5-3b 手動 PoC: Remotion + ElevenLabs + 画像生成 (F-doc-backfill / 2026-05-02 改訂、F-doc-backfill-supplement / 2026-05-02 再改訂)

- **Phase A.5-3b 手動 PoC: Remotion + ElevenLabs + 画像生成** (F-doc-backfill / 2026-05-02 改訂、F-doc-backfill-supplement / 2026-05-02 再改訂)
  - 背景: 「自動化の前に最高傑作を 1 本人間が手作りする」哲学 (DISCUSSION_NOTES #1 参照)。Phase A.5-3a-verify 全通過後、自動化前にゴールドスタンダードを確立。Remotion / ElevenLabs / 画像生成ツール選定を実地で確定する位置付け。当初 F-state-protocol-supplement では CapCut 仮組みも視野に入っていたが、F-doc-backfill (2026-05-02) で「Phase A.5-3b からいきなり Remotion」を採用 (二度手間回避、DECISION_LOG「動画合成ツール Remotion 採用確定」参照)。F-doc-backfill-supplement (2026-05-02) で画像生成候補の DALL-E 3 を ChatGPT Images 2.0 (gpt-image-2) に差し替え (DECISION_LOG「ChatGPT Images 2.0 (gpt-image-2) を画像生成候補に正式追加」参照)。
  - 対応案:
    (1) ElevenLabs アカウント取得 + API キー設定、声選定 (geo_lens 用は低音ダンディ男性、ブランド資産化のため 1 声に固定)
    (2) Nano Banana Pro / ChatGPT Images 2.0 (gpt-image-2) / Flux 1.1 Pro で画像生成比較 (シーンごとの画像プロンプトを使って最低 12-15 枚生成、品質とシネマティック表現を比較してツール確定)
        - ChatGPT Images 2.0 (gpt-image-2) は 2026-04-21 リリースの OpenAI 最新モデル。Image Arena #1、O-series reasoning (Thinking モード) 搭載、日本語の文字レベル精度向上、Web 検索統合でリアルタイムファクトチェック可能。Hydrangea のシネマティック表現とテキスト含む画像 (タイトルカード等) に強み。
        - 価格: 高品質 (1024x1024) 約 $0.21/image、4K $0.41/image、低品質 $0.006/image
        - 比較観点: シネマティック表現 / 日本語テキスト精度 / プロンプト追従性 / 価格 / API 安定性
    (3) Remotion プロジェクトセットアップ (Claude Code に書かせる)
        - 字幕コンポーネント (動的タイミング、Noto Sans JP Black、基本 72pt 強調 96pt、白/金/赤の 3 段階強調)
        - Ken Burns 効果 (ズームイン基本 1.0 → 1.15、強ズーム 1.25)
        - トランジション (ハードカット 0 秒、ピーク地点 0.1 秒ズームパンチ)
        - BGM ダッキング (通常 22%、ナレーション時 15%)
    (4) 動画 1 本完成 (80 秒 MP4)
    (5) docs/golden_master_spec.md に全パラメータ記録 (声 ID / 画像生成プロンプトテンプレ / Ken Burns 設定 / 字幕タイミング / BGM 設定等)
  - 検討時期: Phase A.5-3a-verify 全通過後 (4 カテゴリ全部 OK 判定)
  - 想定工数: 1-2 週間 (制作 3-4 時間 + Remotion セットアップ + 試行錯誤)
  - 関連ファイル: docs/golden_master_spec.md (新規), data/output/golden_master/ (新規), Remotion プロジェクト (新規)

### Phase 1 (F-doc-backfill / 2026-05-02 登録、Phase A.5-3 完了後着手)

- **Phase 1-A: ChannelConfig 統合** (F-doc-backfill / 2026-05-02 登録)
  - 背景: 現状 geo_lens 専用設計。Channel 2/3 追加には設計改修が必要。
  - 対応案: configs/channels/base.yaml + geo_lens.yaml、--channel-id フラグ、TECH_DEBT 2.1/2.2/2.3 同時対応 (YAML 化)
  - 検討時期: Phase A.5-3 全完了後
  - 想定工数: 1 週間
  - 関連: TECH_DEBT 2.1 (編集方針プロンプト YAML 化) / 2.2 (カテゴリ別ベース点数 YAML 化) / 2.3 (キーワード辞書 YAML 化) を本バッチ内で同時対応
  - 関連ファイル: configs/channels/ (新規), src/shared/models.py (ChannelConfig 拡張), src/main.py (CLI 引数)

- **Phase 1-B: src/pipeline/ 分割** (F-doc-backfill / 2026-05-02 登録)
  - 背景: main.py 3303 行は保守困難。pipeline/ への機能別モジュール分割が必要。
  - 対応案: ingestion / clustering / scoring / filtering / analysis / generation / rendering / reporting に分割
  - 検討時期: Phase 1-A 完了後
  - 想定工数: 2-3 週間
  - 関連: TECH_DEBT 4.4 (main.py モノリス化)
  - 関連ファイル: src/pipeline/ (新規), src/main.py (薄いエントリポイント化)

- **Phase 1-C: DB マイグレーション** (F-doc-backfill / 2026-05-02 登録)
  - 背景: 既存テーブルに channel_id カラム追加で多チャンネル対応。
  - 対応案: events / jobs / daily_stats / recent_event_pool / jp_coverage_cache に channel_id カラム追加、デフォルト 'geo_lens' で後方互換
  - 検討時期: Phase 1-A 完了後
  - 想定工数: 1 週間
  - 関連ファイル: src/storage/db.py, scripts/migrate_*.py (新規)

- **Phase 1-D: Supabase 段階移行** (F-doc-backfill / 2026-05-02 登録、★慎重に)
  - 背景: SQLite → Supabase 移行。影響範囲が大きく、段階的に実施必要。Apr 30 の議論で Gemini が「今週末 Supabase 移行」を提案したが、クラウドが「危険すぎる」と反論し計画的実施に変更 (DECISION_LOG「Supabase 段階移行『今週末は危険すぎる』判断」参照)。
  - 対応案: 接続抽象化 → 開発環境動作確認 → テスト並走 → 本番切替 (フィーチャーフラグで戻せる)
  - 検討時期: Phase 1-A/B/C 完了後、Phase B (Web メディア) 着手前
  - 想定工数: 2-3 週間
  - 関連ファイル: src/storage/db.py (抽象化), configs/database.yaml (新規)

---

## 緊急度 低（時間ある時に検討）

---

- **README 全面書き直し** (TECH_DEBT.md 7.1 由来)
  - 背景: 初期 PoC 時代のまま、現状と乖離
  - 対応案: 全フェーズ完了時に書き直し
  - 検討時期: Phase 1.5 完了後

- **REFACTORING_PLAN.md の最終整理** (F-doc-cleanup / 2026-05-03 登録)
  - 背景: REFACTORING_PLAN.md (2026-04-23) は Phase 1-4 系列の改修議論。F-doc-cleanup で冒頭にアーカイブ注記を追加し、個別改修内容は FUTURE_WORK の Phase 1-A / Phase B-3/4 / Phase A.5-3c F-video-compose-integration として現運用に取り込み済。本書は歴史的記録として保持中。
  - 対応案: アーカイブ統合 (docs/archive/REFACTORING_PLAN.md に移動) or 完全削除の最終判断 + 歴史的記録としての価値再評価。「対症療法じゃなくて根本治療」哲学に基づき、不要なら削除する選択肢も含めて検討。
  - 検討時期: README 全面書き直しと同時 (Phase A.5-3d 完了後)
  - 関連ファイル: docs/REFACTORING_PLAN.md, docs/CURRENT_STATE.md (関連ドキュメント導線の更新)

- **触っちゃダメリストのコメント整理** (CLAUDE.md)
  - 背景: なぜ触ってはいけないかの理由が曖昧
  - 対応案: 各ファイルに「触れない理由」と「将来触れる条件」を併記
  - 検討時期: 触っちゃダメリスト見直しの一部として

- **ガベージフィルタの除外内容定期検証** (E-1 ハイブリッド版運用後の懸念)
  - 背景: 必要な記事を誤除外していないか
  - 対応案: 月1回、除外された記事タイトルをカズヤが目視確認。誤除外パターンを発見したら BLOCKED_CATEGORIES や閾値を調整
  - 検討時期: 1ヶ月運用後

### Phase B (F-doc-backfill / 2026-05-02 登録、3-6 ヶ月後)

- **B-1: TikTok Content Posting API 申請 + 実装** (F-doc-backfill / 2026-05-02 登録)
  - 背景: 自動投稿の本命。審査期間が長いため早めに申請が必要。
  - 対応案: 申請 1 日 + 審査 1-3 週間 + 実装 1 週間。Phase A.5-3d で先行統合済の場合は本エントリは「審査通過後の本格運用」に縮小
  - 検討時期: Phase A.5-3d 後
  - 関連ファイル: src/publishing/tiktok.py (新規)

- **B-2: ElevenLabs 統合 (追加声)** (F-doc-backfill / 2026-05-02 登録)
  - 背景: ★Phase A.5-3c の F-elevenlabs-integration で前倒し実施済の予定。本エントリは japan_athletes / k_pulse 用の声追加のみ
  - 対応案: configs/audio.yaml に japan_athletes / k_pulse 用の声 ID を追加
  - 検討時期: Channel 2/3 立ち上げ時
  - 関連ファイル: configs/audio.yaml

- **B-3: Channel 2 (Japan Athletes Abroad) 立ち上げ** (F-doc-backfill / 2026-05-02 登録)
  - 背景: 海外で戦う日本人スポーツ選手チャンネル。
  - 対応案: スポーツ系 RSS ソース追加 (ESPN, Marca, L'Équipe 等)、scoring.py の sports カテゴリベース調整、Breaking Shock 中心の武器庫
  - 検討時期: Phase 1-A (ChannelConfig 統合) 完了後
  - 想定工数: 1-2 週間
  - 関連ファイル: configs/channels/japan_athletes.yaml (新規), configs/sources.yaml (拡張)

- **B-4: Channel 3 (K-Pulse) 立ち上げ** (F-doc-backfill / 2026-05-02 登録)
  - 背景: 韓国エンタメチャンネル。
  - 対応案: 韓国エンタメ系 RSS 追加 (Yonhap、Soompi、Koreaboo 等)、entertainment カテゴリベース調整、Breaking Shock + Cultural Divide 武器庫
  - 検討時期: Phase 1-A 完了後
  - 想定工数: 1-2 週間
  - 関連ファイル: configs/channels/k_pulse.yaml (新規), configs/sources.yaml (拡張)

- **B-5: Remotion Lambda 並列レンダリング** (F-doc-backfill / 2026-05-02 登録)
  - 背景: ★基本 Remotion 移行は Phase A.5-3c の F-video-compose-integration で前倒し実施済の予定。本エントリは Remotion Lambda 並列レンダリングのみ
  - 対応案: AWS Lambda + Remotion Lambda のセットアップ、3 チャンネル並列レンダリング
  - 検討時期: Channel 2/3 稼働後
  - 関連ファイル: remotion/ (拡張), .github/workflows/ (拡張)

- **B-6: Lovable + Vercel フロントエンド** (F-doc-backfill / 2026-05-02 登録)
  - 背景: Web メディアとしての公開、SEO で長期的トラフィック獲得。
  - 対応案: Lovable で Next.js 生成 + Vercel デプロイ、生成済み記事の表示 / チャンネル別アーカイブ / SEO 対策
  - 検討時期: Phase 1-D (Supabase 移行) 完了後
  - 想定工数: 2-3 週間
  - 関連ファイル: web/ (新規, 別リポジトリも検討)

- **B-7: Cloudflare R2 (ストレージ移行)** (F-doc-backfill / 2026-05-02 登録)
  - 背景: 動画ファイルの保存コスト削減。S3 互換 API、エグレス料金ゼロ、保存料金 $0.015/GB/月
  - 対応案: 動画ファイルの保存先を data/output/ → R2 に移行、CDN 配信
  - 検討時期: Phase B (動画自動化) 完了後
  - 想定工数: 1 週間
  - 関連ファイル: src/storage/ (R2 クライアント新規)

### Phase C (F-doc-backfill / 2026-05-02 登録、6-12 ヶ月後)

- **C-1: YouTube Partner Program 申請** (F-doc-backfill / 2026-05-02 登録)
  - 背景: 収益化の最初のマイルストーン。
  - 条件: フォロワー 1000 人 + 視聴時間 4000 時間
  - 期待: 収益化開始 (広告収入)
  - 検討時期: 投稿開始 + 数ヶ月後

- **C-2: サブスク (note 等) / B2B レポート販売** (F-doc-backfill / 2026-05-02 登録)
  - 背景: ストック型収益、ファンベース化。
  - 対応案: note プレミアム / Substack 等で月額、B2B レポート (10-50 万円)
  - 検討時期: Web メディア稼働後
  - 想定: 月額 500-2000 円のサブスクで読者数次第

- **C-3: SaaS 化検討** (F-doc-backfill / 2026-05-02 登録)
  - 背景: Hydrangea パイプラインを他メディア向けにカスタマイズ可能な SaaS 化
  - 対応案: マルチテナント化、テンプレート化された Channel 設定、API 提供
  - 期待: B2B SaaS、数百万-数千万 ARR
  - 検討時期: Channel 3 稼働 + 安定運用後

- **C-4: 事業売却検討** (F-doc-backfill / 2026-05-02 登録)
  - 背景: Exit 戦略の選択肢。
  - 期待: 単体 1-10 億円 / 自社連携 5-50 億円
  - 検討時期: 規模拡大後

- **C-5: 自社サービス (観光・ブライダル) 連携** (F-doc-backfill / 2026-05-02 登録)
  - 背景: Hydrangea を「メディア」として PR、本業との相乗効果
  - 対応案: コンテンツ内での自社サービス自然紹介、SEO 流入の自社サービス送客
  - 検討時期: Web メディア稼働後

### 観察中項目 (F-doc-backfill / 2026-05-02 登録)

- **F-17 候補: Gemini API 503 安定性対処** (F-doc-backfill / 2026-05-02 登録)
  - 背景: 現状の 4 階層フォールバック + GEMINI_QUALITY_MAX_ATTEMPTS=2 + GEMINI_CALL_INTERVAL_SEC=0.5 で大体動くが、スパイク時の 503 が時々発生。試運転は早朝 5-8 時に固定する運用ルール化、リトライ間隔の動的調整、サーキットブレーカーパターン等が改善余地。
  - 着手条件: 503 多発が確認された場合
  - 関連ファイル: src/llm/factory.py, src/llm/retry.py

- **_FRAMING_RESULTS の LRU 化** (F-doc-backfill / 2026-05-02 登録、Phase 2 案件)
  - 背景: src/analysis/perspective_extractor.py の _FRAMING_RESULTS が無制限 dict キャッシュ。長時間稼働でメモリ肥大化の可能性。functools.lru_cache(maxsize=1000) に変更。
  - 不変原則整合: 不変原則 4 (analysis 触らない) と衝突、Phase 1-A で他の analysis 改修と同時対応
  - 着手条件: メモリ使用量の実測値次第
  - 関連ファイル: src/analysis/perspective_extractor.py

- **並列化検討** (F-doc-backfill / 2026-05-02 登録、Phase 2 案件)
  - 背景: candidate1 の framing_inversion / multi_angle / insights は並列可能。asyncio + concurrent.futures で時間効率改善 (RPM 制限内のため合計コール数は変わらない)。
  - 着手条件: Phase 1 完了後
  - 関連ファイル: src/analysis/analysis_engine.py

---

## 完了済み（参考用）

各項目は以下の形式で記載:
- **タイトル** (完了バッチ / 完了日)
  - 何を対応したか

---

- **Task E カズヤレビュー結果反映 + finalize_annotations.py 実行 + 4 運用
  原則 docs 化 (F-task-e-finalize)** (F-task-e-finalize / 2026-05-08 完了)
  - 発生バッチ: F-particular-angle-redesign Task E (4 分類版 + sontaku_signals
    込みカズヤレビュー、25 件) がクラウド対話形式で完了。25 件全件 LLM 推定
    値そのまま採用 (= `kazuya_review.*_revised` 全件 null)、4 つの運用原則
    確立 + 1 つの構造的問題発覚 + (c) サンプル選定バイアス仮説の証拠強化を
    反映するための統合バッチ。
  - 対応内容: (Step 1) `python scripts/finalize_annotations.py
    --schema-version 2.0 ...` 実行で `annotation_diff.json` /
    `stream_classification.json` / `golden_set.json` 生成更新。25 件全件
    `final_stream_source=llm_estimate` /
    `final_sontaku_signals_source=llm_estimate`。(Step 2) DISCUSSION_NOTES
    に新規 4 エントリ追加 (運用原則 3 件 + 重複問題 1 件) + 既存 1 エントリ
    追記 ((c) 仮説証拠強化、ステータス Active 維持で根本治療を Phase A.5-3b
    第二作に明示) + REPORT.md セクション 12 (Task E カズヤレビュー実施結果)
    追加 + DECISION_LOG / FUTURE_WORK / CURRENT_STATE のドッグフーディング。
    コード変更ゼロ、`finalize_annotations.py` は既存スクリプトの実行のみ。
  - 重要な発見 / 観察: (1) **「LLM の知性に委ねる」原則の実証**: 25 件全件
    LLM 推定値そのまま採用 = カズヤ哲学「LLM の膨大な知識による評価・判定を
    信用したい」と整合。(2) **「観点の選択的欠落 = 忖度」判定軸の確立**:
    主要扱い事象なのに特定角度だけ抜ける = リソース不足ではなく忖度、これに
    より Hydrangea コアミッションの射程が明確化。(3) **(c) サンプル選定
    バイアス仮説の裏付け**: stream_3 に再分類される件は 0 件、根本治療は
    Phase A.5-3b 第二作のサンプル拡充。(4) **試運転 / golden_set 重複問題**:
    25 件中 2 ペア (4 件) が同一 MEE 記事の重複 = 独立件数は実質 23 件。
  - 残課題: F-jp-coverage-tune ★最優先着手 OK (真値 25 件 + sontaku_signals
    真値整備完了)。F-stream-2-filter-design は stream_3 = 0 件確定で小規模
    実装の可能性が高い、Phase A.5-3b 第二作のサンプル拡充後に再評価。
    Phase A.5-3b 第二作で系統 3 事象 (処理水放出 / 辺野古 等) のサンプル
    拡充検討 — (c) 仮説検証 + 系統 3 台本表現試行錯誤を兼ねる。F-1
    EditorialMissionFilter 着手時に本バッチの 4 運用原則を設計レビューで参照。
  - 関連ファイル: `docs/runs/F-particular-angle-design/annotation_diff.json`
    (新規)、`docs/runs/F-particular-angle-design/stream_classification.json`
    (新規)、`docs/runs/F-verify-jp-coverage/golden_set.json` (更新)、
    `docs/runs/F-verify-jp-coverage/golden_set_v1.1.json` (バックアップ自動
    生成)、`docs/DISCUSSION_NOTES.md` (新規 4 エントリ + 既存 1 エントリ
    追記 + ヘッダ更新)、`docs/runs/F-particular-angle-redesign/REPORT.md`
    (セクション 12 追加)、`docs/CURRENT_STATE.md` `docs/DECISION_LOG.md`
    `docs/FUTURE_WORK.md` (本バッチ反映)

- **stream_3=0 件 (c) 仮説追記 + sontaku_signals type 分布バイアス記録 + finalize_annotations.py の sontaku_signals 対応 (F-extension-followup)** (F-extension-followup / 2026-05-08 完了)
  - 発生バッチ: F-particular-angle-redesign-extension (2026-05-08, commit `6a8efc4` / merge `2c9ee96`) のクラウドレビューで指摘された 3 件 (sontaku_signals type 分布のサンプル設計バイアス / stream_3=0 件問題の (c) サンプル選定バイアス説 / Task E 着手前の finalize_annotations.py の sontaku_signals 対応確認) を反映するためのフォローアップ。
  - 対応内容: (Task A) `docs/DISCUSSION_NOTES.md` の既存「2026-05-08: 4 分類化で stream_3 = 0 件 / stream_2 = 20 件」エントリに **(c) サンプル選定バイアス説** (前チャットでカズヤ提起、25 件サンプルが海外メディア独自視点中心で真の系統 3 候補が偶然含まれていなかった可能性) を追記、ステータスを `Resolved` → `Active (要カズヤ判別 + サンプル拡充検討)` に降格、「カズヤレビューで判別する」セクションに (c) の判別フロー追加。新規エントリ「2026-05-08: sontaku_signals type 分布のサンプル設計バイアス」追加 (Active、Phase A.5-3b 第二作 + F-1 EditorialMissionFilter 設計時に再評価)。(Task B) `scripts/finalize_annotations.py` の sontaku_signals 対応確認 = **(c) 未対応** (4 関数で sontaku_signals / sontaku_signals_revised 両フィールドが完全にスルー)。最小修正で対応: `_resolve_final()` に `final_sontaku_signals` / `final_sontaku_signals_source` 追加 (null → LLM 推定値継承、object → 全フィールド上書き、フィールド単位 partial merge は未実装)、`build_stream_classification()` の event 出力に sontaku_signals 反映、`update_golden_set()` で schema 2.0 のとき entry に sontaku_signals 反映 + meta に source 記録、`build_annotation_diff()` に `sontaku_signals_revised_count` + diff entry に `sontaku_signals_revised` フラグ追加。既存関数のシグネチャ・戻り値構造は維持 (新キー追加のみ)。(Task C) BATCH_PROTOCOL Task 1-5 ドッグフーディング (DECISION_LOG エントリ + 本エントリ追加 + DISCUSSION_NOTES Task A で実施済み + CURRENT_STATE 全置換更新)。
  - 重要な発見 / 観察: (1) **(c) 仮説の影響**: stream_3=0 件問題は (a) LLM 集約バイアス / (b) 必然的帰結 だけでなく、**入力データセットの構造的問題** (海外メディア中心の RSS 41 媒体で日本国内メディアの論調が拾えない) の可能性が論点として残る。根本治療は系統 3 候補事象 (処理水放出 / 入管法改正 / 辺野古 / ジャニーズ問題) を意図的に追加した拡張ゴールデンセット。(2) **sontaku_signals type 分布バイアス**: 25 件中 type=diplomatic 20 件 (80%) は現サンプル範囲では整合だが、`domestic` (政治家・上級国民忖度) / `media_industry` (記者クラブ・芸能スポーツ業界忖度) はサンプル設計上ほぼ拾えない構造で、F-1 EditorialMissionFilter の優先度判定の歪みを生むリスクあり。(3) **finalize_annotations.py 修正粒度**: フィールド単位 partial merge は今回未実装 (Phase A.5-3b 実運用時にカズヤが手で全フィールド書く運用で支障なし)、null/object の単純ロジックで運用開始。
  - 残課題: ★ F-particular-angle-redesign Task E (4 分類版 + sontaku_signals 込みのカズヤレビュー) 待ち、本フォローアップで `scripts/finalize_annotations.py --schema-version 2.0` の sontaku_signals 対応が完了したためレビュー後即実行可能。Phase A.5-3b 第二作で系統 3 事象 (処理水放出 / 辺野古 等) のサンプル拡充検討、(c) 仮説検証も兼ねる。F-1 EditorialMissionFilter 着手時に sontaku_signals type 分布バイアスエントリを設計レビューで参照。
  - 関連ファイル: `docs/DISCUSSION_NOTES.md` (1 エントリ更新 [stream_3=0 件 + (c) 仮説] + 1 エントリ新規 [sontaku_signals type 分布バイアス] + ヘッダ最終更新日付)、`scripts/finalize_annotations.py` (4 関数 sontaku_signals 対応最小修正)、`docs/CURRENT_STATE.md` `docs/DECISION_LOG.md` `docs/FUTURE_WORK.md` (本バッチ反映)

- **系統名 1/1.5/2 → 1/2/3 リネーム + 忖度シグナル独立化 + クラウド誤り 9 記録 (F-particular-angle-redesign-extension)** (F-particular-angle-redesign-extension / 2026-05-08 完了、Task E カズヤレビュー待ち)
  - 発生バッチ: F-particular-angle-redesign 完了直後の Task E カズヤレビュー過程で、カズヤから本質的な指摘 3 件 (命名整理 / 忖度シグナル独立化 / 各論コントロール回避) が提示された。これらを反映するため F-particular-angle-redesign の **拡張作業** として実施。新規 commit + push で対応、コード変更なし (src/ tests/ configs/ への変更なし)。
  - 対応内容: (Task A) `docs/PARTICULAR_ANGLE_DEFINITION.md` 改訂 — 系統名 1/1.5/2 → 1/2/3 にリネーム + 新サブセクション 1.2 (命名整理経緯) + 1.3 (忖度シグナル独立化経緯) + セクション 3 大幅改訂 (Step 3-4 改良: Step 3 = 「日本メディアが特定角度を語っているか」、Step 4 = 「評価対立 + 忖度シグナル」) + 新サブセクション 3.5 (MECE 判別基準明示) + 3.6 (sontaku_signals 構造定義) + 既存 3.5 を 3.7 にリナンバー (メタデータ構造に sontaku_signals 追加 + クラウド誤り 9 への参照追加)。 (Task B) 3 scripts (`reclassify_annotations.py` / `generate_review_draft_v2.py` / `finalize_annotations.py`) の系統名リネーム + LLM プロンプト改良版 Step 0-4 反映 + ラベル更新。(Task C) `annotations.json` 系統名リネーム (25 件中 20 件) + schema_version 2.0 → 2.1 (`previous_schema_version=2.0` 記録)。`legacy_stream_classification_v1` フィールド内の値は 3 分類版の歴史的記録として変更せず保持。(Task D) `scripts/add_sontaku_signals.py` 新規 (per-call timeout 90s + incremental save + resume) で 25 件分の sontaku_signals を LLM 推定生成、各 event に `sontaku_signals` フィールド付与 + `kazuya_review.sontaku_signals_revised` スロット追加、`extension_log.json` に level / type / extraction_confidence 分布記録。(Task E) `CLAUDE.md` に「クラウド誤り」セクション新設 + 誤り 9 (各論コントロールへの誘惑) 本文記載 + DISCUSSION_NOTES に新エントリ追加 (Resolved、再発防止策確立) + 系統 3 (旧系統 2) の典型パターン (日本-海外の評価対立) 新エントリ (Active、Phase A.5-3b で参照)。(Task F) `REPORT.md` セクション 11 (拡張作業) 追加 + DECISION_LOG エントリ + FUTURE_WORK 本エントリ + DISCUSSION_NOTES 3 エントリ + CURRENT_STATE 全置換更新。
  - 重要な発見 / 観察: (1) **sontaku_signals LLM 推定分布 (25 件)**: level=high 7 件 / medium 14 件 / low 1 件 / none 3 件、type=diplomatic 20 件 / domestic 1 件 / media_industry 1 件 / null 3 件、extraction_confidence=high 23 件 / medium 2 件 / low 0 件。type=diplomatic が圧倒的多数 (20 件) なのは Hydrangea 入力 RSS 41 媒体 (MEE, Meduza, Al Jazeera 等) が外交・地政学事象中心という構造的整合。 (2) **クラウド誤り 9 の構造的解**: 系統判定にジレンマ解説 / 忖度明示の各論ルールを組み込まず、メタデータ構造 (`particular_angle_metadata + sontaku_signals`) を `script_writer.py` 新ルートに渡す設計を維持。LLM の自由度阻害を回避。 (3) **MECE 判別基準明示**: 系統 2 vs 系統 3 の境界条件を「日本メディアが特定角度について何かを語っているか」で MECE に整理、境界事例は sontaku_signals.level で間接区別。 (4) **Gemini API 安定動作**: 約 9 分で 25 件完走 (success=25 / error=0、timeout 警告 1 件 + 後続リトライで成功)、F-particular-angle-redesign の 1:36 hr (Tier 多発フォールバック) と比較して負荷が落ち着いている時間帯。
  - 残課題: ★ F-particular-angle-redesign Task E (4 分類版 + sontaku_signals 込みのカズヤレビュー) 待ち、レビュー完了後 `python scripts/finalize_annotations.py --input docs/runs/F-particular-angle-design/annotations.json --output-diff docs/runs/F-particular-angle-design/annotation_diff.json --output-classification docs/runs/F-particular-angle-design/stream_classification.json --update-golden-set docs/runs/F-verify-jp-coverage/golden_set.json --schema-version 2.0` を実行 → REPORT 補足更新 → 後続バッチ判断。
  - 関連ファイル: `scripts/add_sontaku_signals.py` (新規)、`docs/runs/F-particular-angle-redesign/extension_log.json` (新規)、`docs/PARTICULAR_ANGLE_DEFINITION.md` (命名 1/2/3 + 1.2 / 1.3 / 3.5 / 3.6 / 3.7 サブセクション + Step 3-4 改良)、`scripts/reclassify_annotations.py` `scripts/generate_review_draft_v2.py` `scripts/finalize_annotations.py` (命名リネーム)、`docs/runs/F-particular-angle-design/annotations.json` (schema 2.1 + sontaku_signals)、`CLAUDE.md` (クラウド誤りセクション新設)、`docs/runs/F-particular-angle-redesign/REPORT.md` (セクション 11 拡張作業追加)、`docs/CURRENT_STATE.md` `docs/DECISION_LOG.md` `docs/FUTURE_WORK.md` `docs/DISCUSSION_NOTES.md` (本バッチ反映)

- **3 分類 → 4 分類化 + 系統 1.5 perspective_gap 新設 + 台本表現ガイドライン正典化 (F-particular-angle-redesign)** (F-particular-angle-redesign / 2026-05-08 完了、Task E カズヤレビュー待ち、★ 拡張バッチ F-particular-angle-redesign-extension で命名 1/2/3 整理 + sontaku_signals 独立化を反映)
  - 発生バッチ: F-particular-angle-design (2026-05-07) の DISCUSSION_NOTES 4 エントリ追加 (2026-05-07 当日中) で、3 分類 (系統 1 / 系統 2 / 動画化対象外) の構造的不備が明らかになった。具体的には blind_002 / blind_004 / blind_009 のような事象群で「広範事件は日本主要メディアで報道済み + 特定角度のみ未報道」というパターンが多発しており、LLM 判定では「特定角度ベース」で stream_1_silence_gap に分類されるが台本表現として「日本では報じられていない」と書くと嘘になり視聴者からのツッコミを誘発するリスクが残った。カズヤから「一部報道だけど観点不足っていう 1.5 分類儲けてもいいのかもしれない」と提案され、議論の結果 4 分類化が必要との結論に到達。Phase A.5-3a-verify ゲート完了後の 2 つ目のバッチで、F-particular-angle-design の構造的不備の根本治療と F-stream-2-filter-design / F-jp-coverage-tune の責務分離を更に明確化する性格を持つ。
  - 対応内容: (Task A) `docs/PARTICULAR_ANGLE_DEFINITION.md` を 3 分類 → 4 分類版に改訂 (新サブセクション 1.1 「3 分類の構造的不備と 1.5 分類追加の経緯」+ セクション 3 大幅改訂で Step 1-4 論理フロー + 新サブセクション 3.5 「系統別の台本表現の方向性」で particular_angle_metadata 構造を正典化)。(Task B) `scripts/reclassify_annotations.py` 新規作成 (4 分類化用 LLM 再判定、per-call timeout 90s + resume + incremental save 付き、`_build_extract_client()` 流用で max_output_tokens=4096)。(Task C) 25 件再分類実行 (Gemini API 503 高負荷で Tier 1→2→3 フォールバック多発、第 1 試行 hung でタイムアウト追加して第 2 試行で完走、success=25 / error=0 / 約 1:36 hr)。(Task D) `review_draft_v2.md` 生成 (重点レビュー section: 3 分類 → 4 分類で変更があった 20 件を冒頭表示、各 event の「3 分類版 → 4 分類版判定」併記)。(Task E: ★ カズヤ手動レビュー、本バッチ内未実行)。(Task F) `scripts/finalize_annotations.py` を 4 分類対応に改修 (`--schema-version` 引数追加、デフォルト 2.0、3 分類対応関数 + 4 分類対応関数併存、golden_set v1.x → v1.3 更新パス、入力検証で schema 不整合を検知)。(Task G) `REPORT.md` + BATCH_PROTOCOL Task 1-5 ドッグフーディング (DECISION_LOG エントリ追加 + FUTURE_WORK 本エントリ追加 + F-stream-2-filter-design 責務スコープ要再評価更新 + F-jp-coverage-tune 優先度上昇 + DISCUSSION_NOTES 既存 4 エントリ更新 (Resolved 化等) + CURRENT_STATE 全置換更新)。
  - 重要な発見 / 想定外結果: (1) ★ **stream_2 = 0 件、stream_1_5 = 20 件 という想定外分布**: LLM が 4 分類定義を厳密適用した結果、3 分類版で stream_2 だった 13 件全てが stream_1_5 に移動 (covered 系列 9 件 + blind_005/008 + 試運転 cls-7bd1406438b6/cls-33b4f4960bf9_7K)。LLM の reasoning は技術的に整合 (例: covered_002「広範事件であるトランプ・プーチン接触は日本でも報道済みだが、外交的正当性と構造的影響の特定角度分析は深掘り未報道」)。これが LLM の集約バイアス (stream_2 を選ぶ基準が厳しすぎる) なのか、4 分類定義の必然的帰結 (海外メディアの特定角度が日本で同フレームで報道されることが稀) なのかは、カズヤレビューで判別する必要あり。(2) **3 分類版で stream_1 だった 7 件が stream_1_5 に移動**: blind_002/004/009/010 + 試運転 3 件 (cls-204a683f73ee_7K / cls-6be4fc09d9ed / cls-a4132ec7d949)。F-particular-angle-design DISCUSSION_NOTES 観察 1 (golden_set v1.1 stream_2_candidate メタとの差分) で予測された変化と整合、4 分類化の妥当性を支持する事例。(3) **不変 5 件**: 系統 1 のまま 4 件 (blind_001 / blind_003 / blind_007 / cls-0c7fa7c667d6 ロシア焼身) + 動画化対象外のまま 1 件 (covered_006 NVIDIA 株)。(4) **F-stream-2-filter-design の責務範囲縮小可能性**: 本想定外結果次第で F-stream-2-filter-design は小規模実装で済む可能性、F-jp-coverage-tune が相対的に最優先化。(5) **二段階クエリ生成の真値整備**: 各 event に `broad_event_jp_coverage` と `particular_angle_jp_coverage` の独立フィールドが追加され、F-jp-coverage-tune の二段階クエリ精度評価に使える 25 件の真値データが整備された。(6) **Gemini API 503 高負荷耐性**: per-call timeout 90s + incremental save + resume を組み合わせることで API ハング (50 分応答なし事例観測) からの復旧と部分結果保存が可能になった、reclassify_annotations.py は今後の同種スクリプトの参考実装として転用可。
  - 残課題: ★ Task E (カズヤレビュー) 待ち、レビュー完了後 `python scripts/finalize_annotations.py --input docs/runs/F-particular-angle-design/annotations.json --output-diff docs/runs/F-particular-angle-design/annotation_diff.json --output-classification docs/runs/F-particular-angle-design/stream_classification.json --update-golden-set docs/runs/F-verify-jp-coverage/golden_set.json --schema-version 2.0` を実行 → REPORT 補足更新 → 後続バッチ (F-stream-2-filter-design スコープ判断 / F-jp-coverage-tune 着手) を判断。
  - 関連ファイル: `scripts/reclassify_annotations.py` (新規)、`scripts/generate_review_draft_v2.py` (新規)、`scripts/finalize_annotations.py` (改修、`--schema-version 2.0` 追加)、`docs/PARTICULAR_ANGLE_DEFINITION.md` (3 分類 → 4 分類への改訂)、`docs/runs/F-particular-angle-redesign/` 配下 (REPORT.md / reclassification_log.json / reclassification_diff.json / reclassify_log.txt / review_draft_v2.md)、`docs/runs/F-particular-angle-design/annotations.json` (4 分類版に上書き、`legacy_stream_classification_v1` + `broad_event_jp_coverage` + `particular_angle_jp_coverage` 新フィールド付与)、`docs/runs/F-particular-angle-design/annotations_v1_3class.json` (3 分類版バックアップ)、`docs/CURRENT_STATE.md` (全置換更新)、`docs/DECISION_LOG.md` (本バッチエントリ追加)、`docs/FUTURE_WORK.md` (本エントリ + F-stream-2-filter-design 責務スコープ更新 + F-jp-coverage-tune 優先度上昇)、`docs/DISCUSSION_NOTES.md` (既存 4 エントリ更新)

- **「特定角度」概念の docs 化 + LLM ベースアノテーション 25 件 (F-particular-angle-design)** (F-particular-angle-design / 2026-05-07 完了)
  - 発生バッチ: F-trial-run-post-fix (2026-05-07) で「広範事件は日本主要メディアで報道済みだが、MEE/海外メディアの特定角度は未報道」という stream_2_candidate パターンが 6 件 (golden set 4 + 試運転 7-K 2) 確認された。系統 1 / 系統 2 の判定対象を「広範事件」レベルで取ると両系統で重複ケースが発生する問題が顕在化、カズヤとの議論 (2026-05-07) で「重複しないように定義すればよくね?」 = 判定対象を『特定角度』に限定すれば重複は構造的に消えるという結論に到達。Phase A.5-3a-verify ゲート完了後の最初のバッチで、F-stream-2-filter-design + F-jp-coverage-tune の共通基盤を確立する性格を持つ。
  - 対応内容: (Task A) `docs/PARTICULAR_ANGLE_DEFINITION.md` 新規作成 (5 セクション散文展開: 背景 / 概念定義 / 系統判定基準 / LLM 抽出方針 / 関連ファイル)。(Task B) `scripts/extract_particular_angle.py` 新規作成 (LLM ベース特定角度抽出、max_output_tokens=4096 専用クライアント、JSON パーサ最小修復、リトライ最大 3 回)。(Task C) `docs/runs/F-particular-angle-design/input_events.json` 25 件統合 (golden_set v1.1: 19 件 + 試運転 7-K 2026-05-01: 3 件 + 試運転 2026-05-07: 3 件)。(Task D) Gemini analysis Tier で 25 件抽出実行、`annotations.json` 出力 (extraction_confidence: high=22 / medium=3 / low=0、stream 推定: 系統 1=11 / 系統 2=13 / 対象外=1、errors=0)。試行 1-2 で max_output_tokens=2000 による JSON 途中切断を覚知 (6-7 件失敗) → 4096 への拡張で 0 errors 達成。(Task E) `review_draft.md` 生成 (655 行、25 events フォーマット統一、各 event に LLM 抽出 + LLM 判定 + 判定根拠 + カズヤレビュー欄)。(Task F: ★ カズヤ手動レビュー、本バッチ内未実行)。(Task G) `scripts/finalize_annotations.py` 新規作成 (annotation_diff + stream_classification + golden_set v1.2 を生成、試運転 6 件は golden_set 統合せず stream_classification.json で 25 件まとめて管理する責務分離)。(Task H) 統合レポート `REPORT.md` + BATCH_PROTOCOL Task 1-5 ドッグフーディング (DECISION_LOG エントリ + FUTURE_WORK 完了済み移動 + DISCUSSION_NOTES 「系統 1 判定基準明確化」「F-13.B 動作仕様」エントリ更新 + 新規エントリ「特定角度抽出の LLM 限界観察」+ CURRENT_STATE 全置換更新)。
  - 重要な発見: (1) **「特定角度」概念の有効性**: 試運転 2026-05-07 Slot-1 (Insider trading) は WebSearch で広範事件は Tier 1-2 報道済みと判明していたが、LLM は「特定角度 (国家規模インサイダー取引疑惑) は日本主要メディアで深掘り未報道」と判定し stream_1 に分類 = 「特定角度」概念を判定単位にすると blind_spot ルートに進んだ動画化が正当化される事例。(2) **golden_set v1.1 stream_2_candidate メタとの差分**: blind_002/004/009 は v1.1 で stream_2_candidate メタ付与だが LLM は stream_1 に分類。判定対象を『広範事件』vs『特定角度』で取ると同じ事象でも結論が変わる可能性、カズヤレビューで再評価対象。(3) **covered 系列 9/10 件が stream_2 に分類**: 「日本主要メディアで報道済みでも海外メディアの掘り下げ角度には解釈差があり stream_2 候補となる」という LLM 判断傾向、F-stream-2-filter-design が処理する候補数の見積もり材料。(4) **max_output_tokens=2000 では分析タスクで途中切断**: analysis_llm_client 既定の 2000 tokens は本タスクで JSON 途中切断を起こした、F-stream-2-filter-design 着手時の判断材料に。
  - 残課題: ★ Task F (3 分類版でのカズヤレビュー) は **スキップ済み** (F-particular-angle-redesign / 2026-05-08 で 4 分類化が必要なことが判明したため、3 分類版での確定作業は無駄になる判断)。3 分類版の LLM 判定結果は `annotations_v1_3class.json` としてバックアップ済み。カズヤレビューは F-particular-angle-redesign の Task E で 4 分類版に対して実施する。
  - 関連ファイル: `docs/PARTICULAR_ANGLE_DEFINITION.md` (新規、F-particular-angle-redesign で 4 分類化に改訂)、`scripts/extract_particular_angle.py` (新規)、`scripts/finalize_annotations.py` (新規、F-particular-angle-redesign で `--schema-version 2.0` 追加に改修)、`docs/runs/F-particular-angle-design/` 配下 (input_events.json / annotations.json / annotations_v1_3class.json / review_draft.md / extraction_log.txt / REPORT.md)、`docs/CURRENT_STATE.md` (全置換更新)、`docs/DECISION_LOG.md` (本バッチエントリ追加)、`docs/FUTURE_WORK.md` (本エントリ + F-stream-2-filter-design / F-jp-coverage-tune の前提に F-particular-angle-design 完了を追記)、`docs/DISCUSSION_NOTES.md` (既存 2 エントリ更新 + 新規 1 エントリ)

- **修正後 F-13.B の本番試運転 + 過去判定後追い + Phase A.5-3a-verify ゲート完了 (F-trial-run-post-fix)** (F-trial-run-post-fix / 2026-05-07 完了)
  - 発生バッチ: F-jp-coverage-improve (2026-05-07) で F-13.B 構造的不具合を修正したが、「動くものを壊さない」哲学に従い、本番運用 (RSS 収集 → triage → Slot 選定) で修正後 F-13.B が期待通り動くか試運転で確認 + 過去試運転 7-K 動画化 3 件 (FIFA + Gaza×2) の WebSearch 後追い + 修正後 F-13.B での過去試運転再判定が必要だった。Phase A.5-3a-verify ゲート完了の最終段階 (1-D''')。
  - 対応内容: (Task A) ブランチ作成 + 環境スナップショット (main HEAD `fd76660`、baseline 1345 passed、jp_coverage_cache 6 records、AUDIO/VIDEO_RENDER_ENABLED デフォルト false 確認)。(Task B) `python -m src.ingestion.run_ingestion` で RSS 取得 (41 ソース中 40 成功、1454 raw → 584 重複除去後)、`python -m src.main --mode normalized` で試運転 (約 26 分、batch_id=20260506_190600、job_id=033ed4bc...、status=completed、3 Slot 選定 = Slot-1 cls-6be4fc09d9ed Insider trading + Slot-2 cls-0c7fa7c667d6 Russian self-immolation + Slot-3 cls-a4132ec7d949 Met Police synagogue、F-13.B 3 invocations 全 has_jp_coverage=False、excluded_count=1/10/3)。(Task C) `f13b_output_analysis.json` に試運転 + replay 6 invocations 集計 (True 0 / False 6 / Error 0、excluded URLs 全 youtube.com 計 23 件、structural_fix_validated=true) と解釈 (Tier 1-2 ヒット 0、Grounding API が youtube.com 偏重 = F-jp-coverage-tune 既知課題と整合) を保存。(Task D) `defense_layers_audit.json` に防衛機構 5 層発火状況保存 (F-1 18/364 通過、F-2 全通過、F-13.B 3 invocations 構造機能 OK、F-5 救済 0、F-13 隠れ層 0)、all_5_layers_functional=true。(Task E) WebSearch (Anthropic web search) で試運転 7-K 過去動画化 3 件後追い、Slot-1 (FIFA) は jiji.com (Tier 2) で関連報道、Slot-2 (Mandelson) は nikkei.com (Tier 1) + jiji + bloomberg (Tier 2) で広範報道済み (Epstein 角度、MEE オリジナル Gaza 角度は未報道)、Slot-3 (Gaza 電力) は MEE 2026-04 時点の特定角度は未報道で真の blind_spot に近い、を `past_videos_audit.json` に保存。3 件中 2 件が典型的 stream_2_candidate パターン。(Task F) `scripts/replay_jp_coverage.py` 新規作成 (一時 DB `/tmp/jp_coverage_replay.db`、verify_jp_coverage_measure.py 構造踏襲)、入力 `trial_7k_events.json` で 3 件再判定、結果 `past_runs_replay.json` に 3 件全て False→False (判定不変、excluded 0/5/4 で構造機能は OK)。(Task G) 統合レポート `REPORT.md` 作成 + Phase A.5-3a-verify ゲート完了正式宣言 + BATCH_PROTOCOL Task 1-5 ドッグフーディング (DECISION_LOG エントリ + FUTURE_WORK 完了済み移動 + F-stream-2-filter-design 着手 OK 状態に更新 + F-jp-coverage-tune 優先度確認 + DISCUSSION_NOTES F-13.B エントリのステータス更新 + 新規エントリ「Grounding 検索クエリ品質問題」追加 + CURRENT_STATE 全置換更新)。リグレッション影響なし (`scripts/replay_jp_coverage.py` 新規 + `docs/runs/F-trial-run-post-fix/` + `docs/` のみ変更、`src/` `tests/` `configs/` `CLAUDE.md` 0 行変更、baseline 1345 passed 維持)。
  - 重要な発見: (1) 構造的不具合解消の **本番動作確認**: 試運転 6 invocations のうち 5/6 で excluded_urls_count > 0 (1/10/3/0/5/4)。修正前は redirect URL のみで構造的に excluded=0 だった、ドメイン抽出層 (`_extract_domain_from_chunk` / `_looks_like_domain` / `_normalize_domain`) の本番動作証明。(2) **Recall miss の本番再現**: 試運転 Slot-1 (Insider trading) は WebSearch で nikkei + jiji + bloomberg で広範報道済みだが F-13.B は Recall miss、Grounding API が英語タイトル + 「日本 報道」クエリで youtube.com 偏重の結果を返す問題が本番でも確認 (excluded URLs 全 23 件が youtube.com)。これは F-jp-coverage-tune の主要課題と完全整合。(3) **試運転 7-K 過去動画 3 件のうち 2 件が typical stream_2_candidate**: Slot-1 (FIFA) と Slot-2 (Mandelson) は『広範事件は Tier 1-2 報道済み + MEE オリジナル角度は未報道』パターン、F-stream-2-filter-design 完成後の 2 段階フィルタで救出される設計と整合 = 系統 2 設計の妥当性根拠拡張 (golden set 4 件 + 試運転 7-K 2 件 = 6 件)。(4) **WebSearch クローラ制約**: Anthropic WebSearch クローラは asahi.com / yomiuri.co.jp / nhk.or.jp / mainichi.jp / sankei.com / 47news.jp / kyodonews.jp / kyodonews.net への直接クロールがブロックされる仕様、Tier 1 主要紙の報道有無は jiji / nikkei / bloomberg 等の他 Tier ヒットから推定する制約あり。(5) **Phase A.5-3a-verify ゲート完了**: 1-A〜1-D''' 全完了、F-stream-2-filter-design 着手 OK 状態に。
  - 残課題: F-stream-2-filter-design 着手 (★最優先、Phase A.5-3a-verify ゲート完了で着手再開条件達成)、F-jp-coverage-tune (Recall miss の本番再現で優先度確認、F-stream-2-filter-design と並行可)、Project Knowledge の手動最新化 (★ Phase A.5-3a-verify ゲート完了の節目で必須最新化推奨)
  - 関連ファイル: `scripts/replay_jp_coverage.py` (新規)、`docs/runs/F-trial-run-post-fix/` 配下 9 ファイル (REPORT.md / trial_run_log.json / f13b_output_analysis.json / defense_layers_audit.json / past_videos_audit.json / past_runs_replay.json / trial_7k_events.json / trial_run_log.txt / ingestion_log.txt / replay_log.txt)、`docs/CURRENT_STATE.md` (全置換更新), `docs/DECISION_LOG.md` (本バッチエントリ追加), `docs/FUTURE_WORK.md` (本エントリ + F-stream-2-filter-design 着手 OK 状態 + F-jp-coverage-tune 優先度更新), `docs/DISCUSSION_NOTES.md` (F-13.B 動作仕様検討課題ステータス更新 + 新規エントリ「Grounding 検索クエリ品質問題」追加)

- **F-13.B 構造的不具合の根本治療 + 不変原則例外条件構造化 + Project Knowledge 運用ルール化 + Phase A.5-3a-verify ゲート完了条件再定義 (F-jp-coverage-improve)** (F-jp-coverage-improve / 2026-05-07 完了)
  - 発生バッチ: F-verify-jp-coverage-measure (2026-05-05、verdict=fail) で F-13.B JpCoverageVerifier の構造的不具合を特定したため、根本治療志向で 5 つの目的を同時達成する複合バッチを起動。(1) F-13.B 構造的不具合の根本治療、(2) 不変原則例外条件の構造化、(3) Project Knowledge 最新化運用のルール化、(4) Phase A.5-3a-verify ゲート完了条件の再定義、(5) 計測再実行で合格判定取得。
  - 対応内容: (Task A) `src/triage/jp_coverage_verifier.py` にドメイン抽出レイヤー (`_extract_domain_from_chunk` / `_looks_like_domain` / `_normalize_domain`) を追加。`_search_with_grounding()` を修正し、`chunk.web.title` を実ドメインとして読み取り `https://{domain}` 形式で WL マッチングに供給。`chunk.web.uri` (Vertex AI redirect URL) は `redirect_urls` に分離記録 (debug 用)。SDK 将来バージョンで `chunk.web.domain` が実値を返した時に透過対応する **防御層** として機能するフォールバック戦略 (戦略 1: domain → 戦略 2: title) を持つ。(Task B) `tests/test_jp_coverage_verifier_domain_extract.py` を新規作成 (28 テスト追加: `_looks_like_domain` / `_normalize_domain` / `_extract_domain_from_chunk` の各戦略 + 実 API 観測値での検証 + フォールバック確認)。`tests/test_f13b_rescue_abolition.py` の `_make_grounding_response` フィクスチャを実 API contract に合わせて更新 (uri に Vertex redirect URL、title に実ドメイン、domain=None)、除外 URL アサーション 1 つを host ベースに調整。テスト総数 1315 → 1345 (+30) 全 passed 維持。(Task C) `scripts/verify_jp_coverage_measure.py --cache-mode=fresh` 実行で 5 件 503 UNAVAILABLE エラー (Gemini API 一時的高負荷)、`--cache-mode=reuse` で残存 5 件のみ retry し全件完走。再測定結果: TP=10/14 (vs 修正前 0/14), FN=4/14 (vs 修正前 14/14), FP=2/5, TN=3/5, Recall covered 71.43% / Precision blind 42.86% / F1 0.769 / Tier 一致率 30% / Error 0%。**構造的不具合は解消されたが 4 指標とも閾値未達のため verdict=fail のまま**。残課題 (FN クエリ最適化 / FP diamond.jp 真値再評価 / Tier 一致率) は本バッチ責務範囲外として F-trial-run-post-fix + F-jp-coverage-tune に分離。`docs/runs/F-verify-jp-coverage/measurement_result.json` を v2 として上書き (root_cause_finding に resolved_in を追加)、`REPORT.md` を v2 として上書き (★1.5 セクションを「根本原因の特定と修正済み報告」に更新、修正前後の比較表を追加)。(Task D) `docs/BATCH_PROTOCOL.md` に「不変原則の例外条件」セクション (4 条件 + 例外不可ケース + 過去事例) と「Project Knowledge 最新化運用ルール」セクション (必須/推奨タイミング + 最新化対象 + 注意事項) を追加。(Task E) `docs/CURRENT_STATE.md` の Phase A.5-3a-verify ロードマップを 1-A〜1-D''' 構成に再定義 (1-D'' を 1-D' 内統合、1-D''' を F-trial-run-post-fix として分離)。(Task F) BATCH_PROTOCOL Task 1-5 ドッグフーディング (DECISION_LOG エントリ + FUTURE_WORK 完了済み移動 + F-trial-run-post-fix / F-jp-coverage-tune 緊急度 高新規追加 + F-stream-2-filter-design 着手再開条件更新 + DISCUSSION_NOTES 既存エントリ更新 + CURRENT_STATE 全置換更新)。
  - 不変原則例外: 不変原則 3 (`src/triage/` 既存ファイル変更不可) に例外適用。4 条件全て満たすことを確認 (1) 実装バグの修正 (Grounding redirect URL を WL マッチング使用) (2) 設計変更ではない (`verify()`/`verify_async()` シグネチャ・戻り値構造不変、ドメイン抽出ロジックの正しい実装への置換のみ) (3) DECISION_LOG エントリで明記 (4) Hydrangea コンセプト防衛機構 5 層中核なのでカズヤ承認必須 → バッチプロンプトの背景セクションに記録済み。
  - 重要な発見: 構造的不具合は解消されたものの精度指標は閾値未達。「ロジックが構造的に常に False を返す」状態 (v1) → 「正しく動くが精度が閾値未達」状態 (v2) は質的に異なる進捗。残 FN 4 件 (blind_005 / covered_006 / covered_007 / covered_009) は Grounding API がタイトル・ベース検索クエリで Tier 1-2 ソースを直接引き当てられないクエリ最適化問題、FP 2 件は両方 diamond.jp で WL に正規収録されたドメインが該当 → 真値再評価 or Tier 4 weighting 議論が必要、Tier 一致率低下は Grounding が Tier 4 ソースを Tier 1 より先に返す傾向 (構造的、別問題)。stream_2_candidate 4 件は 3/4 が True 判定でき、F-stream-2-filter-design の前提は確保されている。
  - 残課題: F-trial-run-post-fix (修正後 F-13.B の本番試運転 + 過去判定後追い、即着手可能)、F-jp-coverage-tune (Recall/Precision/Tier 一致率の閾値達成、F-trial-run-post-fix 完了後)、Project Knowledge の手動最新化 (カズヤ手作業、本バッチ完了後 = Phase A.5-3a-verify ゲート完了の節目で必須最新化推奨)
  - 関連ファイル: `src/triage/jp_coverage_verifier.py` (改修対象、★不変原則 3 例外条項適用、ドメイン抽出レイヤー追加 + `_search_with_grounding()` 修正), `tests/test_jp_coverage_verifier_domain_extract.py` (新規 28 テスト), `tests/test_f13b_rescue_abolition.py` (フィクスチャ実 API contract 整合化 + 除外 URL アサーション host ベース化), `docs/runs/F-verify-jp-coverage/measurement_result.json` v2 + `REPORT.md` v2 (再測定結果上書き), `docs/BATCH_PROTOCOL.md` (不変原則例外条件 + Project Knowledge 運用ルールセクション新設), `docs/CURRENT_STATE.md` (全置換更新), `docs/DECISION_LOG.md` (本バッチエントリ追加), `docs/FUTURE_WORK.md` (本エントリ + F-trial-run-post-fix / F-jp-coverage-tune 新規 + F-stream-2-filter-design 着手再開条件更新), `docs/DISCUSSION_NOTES.md` (F-13.B 動作仕様検討課題エントリ更新)

- **F-13.B 精度実測 + 構造的不具合 (Grounding redirect URL) の特定 (F-verify-jp-coverage-measure)** (F-verify-jp-coverage-measure / 2026-05-05 完了、verdict=fail)
  - 発生バッチ: ゴールデンセット v1.1 (19 件) + F-13.B 既存実装で精度実測したところ、19/19 件で `matched=0`, `has_jp_coverage=False` という異常パターンを観測。Recall covered 0%、Precision blind 26.32%、F1 covered 0.000、Tier 一致率 0%、エラー 0/19 で全 4 指標未達。
  - 対応内容: (Task A) `scripts/verify_jp_coverage_measure.py` 新規作成 (約 600 行、CLI 引数 `--cache-mode` で fresh/reuse/warm-then-reuse 切替、一時 DB `/tmp/jp_coverage_measure.db` を使い本番 DB を汚染しない設計、TP/FP/TN/FN/Error + Precision/Recall/F1/Tier 一致率/stream_2 集計 + verdict 判定 (pass/conditional_pass/fail) を一通り実装、結果 JSON + 人間読み Markdown を生成)。(Task B) `--cache-mode=fresh` で実行、19 件全件完走 (エラー 0、所要 177s ≈ 3 分)。(Task C) 全件 matched=0 という異常を受け、Gemini Grounding API のレスポンス構造を直接デバッグ → `chunk.web.uri` は redirect URL (`vertexaisearch.cloud.google.com/grounding-api-redirect/...`)、実ドメインは `chunk.web.title` (例: `jiji.com`, `jetro.go.jp`, `recordchina.co.jp`) に格納されている事実を特定。`chunk.web.domain` は SDK 現行版で常に None。(Task D) verdict=fail として REPORT.md と measurement_result.json を確定、★1.5 根本原因の特定セクションを REPORT.md に挿入、root_cause_finding フィールドを measurement_result.json に追加、F-jp-coverage-improve バッチ起動 + F-stream-2-filter-design 着手保留を明記。(Task E) BATCH_PROTOCOL Task 1-5 ドッグフーディング実施 (DECISION_LOG エントリ追加 / FUTURE_WORK で本エントリ完了済み移動 + F-jp-coverage-improve 緊急度 高新規追加 + F-stream-2-filter-design 着手保留化 / DISCUSSION_NOTES「F-13.B 動作仕様の検討課題」に 2026-05-05 実測結果と根本原因特定を追記 / CURRENT_STATE 全置換更新 = main HEAD/直近 5 件/次バッチ候補刷新/Phase A.5-3a-verify ロードマップ 1-D 完了表示/F-13.B 行に精度実測値追記)。リグレッション影響なし (`scripts/` + `docs/runs/` + `docs/` 配下のみ変更、`src/` `tests/` `configs/` `CLAUDE.md` 0 行変更、baseline 1315 passed 維持)。
  - 重要な発見: F-13.B が本番でも常に `has_jp_coverage=False` を返している懸念。試運転 7-K の「100% (3/3) 動画化」は F-13.B の判定精度ではなく、F-13.B が常に False を返した結果として全 Slot が blind_spot 動画化ルートに進んだだけと再解釈される。Hydrangea コンセプト防衛機構 (5 層) の中核 (F-13.B 層) が機能していなかった可能性、即修正が必要。
  - 残課題: F-jp-coverage-improve 着手 (緊急度 高セクションに新規エントリ追加済み、即着手推奨)、改修後 `verify_jp_coverage_measure.py` 再実行で合格判定取得、試運転 7-K の 3 件が実は日本主要メディアで報道済みだったかの後追い確認
  - 関連ファイル: `scripts/verify_jp_coverage_measure.py` (新規), `docs/runs/F-verify-jp-coverage/measurement_result.json` (新規 + root_cause_finding), `docs/runs/F-verify-jp-coverage/REPORT.md` (新規 + ★1.5 根本原因特定), `docs/DECISION_LOG.md` (本バッチエントリ追加), `docs/FUTURE_WORK.md` (本エントリ + F-jp-coverage-improve 新規 + F-stream-2-filter-design 着手保留化 + Phase 順序更新), `docs/DISCUSSION_NOTES.md` (F-13.B 動作仕様検討課題に 2026-05-05 追記), `docs/CURRENT_STATE.md` (全置換更新)

- **ゴールデンセット真値修正 + 系統 1 判定基準 4 軸明文化 + Hydrangea メディア宣言反映 + F-stream-2-filter-design 計画 (F-verify-jp-coverage-golden-fix)** (F-verify-jp-coverage-golden-fix / 2026-05-04 完了、中間成果物)
  - 発生バッチ: F-verify-jp-coverage-golden 完了後のカズヤレビューで 5 件の真値修正必要 + 系統 1 判定基準が「日本未報道」だけでは不十分 + 「個人・権力者への忖度」軸が新規追加 + Hydrangea のメディアとしての存在意義 (「忖度、報道規制、報道の自由度の低さをぶち壊そう」というカズヤ宣言) が明示化される必要がある重要な発見が確定。また機械の根本的役割について「2 段階フィルタ + 解説価値判定」設計が確立し、F-stream-2-filter-design として Phase A.5-3b 前に独立実装する Phase 配置が確定した。
  - 対応内容: (Task A) golden_set.json 修正 = 4 件 (blind_002/004/005/009) の expected_has_jp_coverage を False → True 修正 (広範な事件は日本でも報道済み、特定角度は系統 2 候補)、blind_006 削除 (Palestine FIFA、Hydrangea 系統 1 ミッションに整合せず、heuristic 未採用 12 件から差し替え候補探索したが該当なし → 9 件構成に変更)、stream_2_candidate メタフィールド追加 (4 件に系統 2 候補メタ付与)、集計フィールド更新 (kazuya_review_required_ids 空配列、True/False 分布を expected_distribution として新設、last_updated_at + last_update_batch + v1_1_changelog 追加)。(Task B) DISCUSSION_NOTES 新規エントリ「系統 1 (silence_gap) の判定基準明確化」追加 (制度・システム面 / 外交・経済・利害関係面 / 個人・権力者面 / 関心領域・地政学的死角 の 4 軸構造で記録、Hydrangea メディア宣言を明記)、既存エントリ「F-13.B 動作仕様の検討課題」に 2026-05-04 議論結果追記 (カズヤの整理 + 2 段階フィルタ採用 + Phase A.5-3b 前独立実装方針、ステータス: 要確認 → 確定)。(Task C) FUTURE_WORK 緊急度 高に F-stream-2-filter-design 新規追加、F-verify-jp-coverage-measure の前提更新 (即着手可能)、Phase 順序を「measure → stream_2_filter → 3b」に更新、完了済みに本エントリ追加。(Task D) DECISION_LOG エントリ追加 (本バッチの設計判断 4 つを記録)。(Task E) CURRENT_STATE 更新 (最終更新日、次バッチ候補刷新、Phase A.5-3a-verify ロードマップ 1-C/1-D/1-E 段階追加、セクション 0 のコアミッション系統 1 説明を強化 = 4 軸構造 + Hydrangea メディア宣言を明示、末尾注記更新)。リグレッション影響なし (docs/ + docs/runs/ のみ追加、src/ tests/ configs/ CLAUDE.md は 0 行変更、baseline 1315 passed 維持)。
  - 残課題: F-verify-jp-coverage-measure 着手 (前提条件確定済み、即着手可能)
  - 関連ファイル: docs/runs/F-verify-jp-coverage/golden_set.json (v1.0 → v1.1 修正), docs/DISCUSSION_NOTES.md (1 新規 + 1 追記), docs/FUTURE_WORK.md (本エントリ + F-stream-2-filter-design 新規 + F-verify-jp-coverage-measure 前提更新 + Phase 順序新設), docs/DECISION_LOG.md (本バッチエントリ), docs/CURRENT_STATE.md (全置換更新 + セクション 0 系統 1 説明強化)

- **F-13.B 精度測定用ゴールデンセット作成 (F-verify-jp-coverage-golden / 第 1 段階)** (F-verify-jp-coverage-golden / 2026-05-03 完了、中間成果物)
  - 発生バッチ: F-verify-jp-coverage を 2 段階分割した第 1 段階。F-13.B JpCoverageVerifier (Hydrangea コンセプト防衛機構の中核) の精度測定 (TP/FP/TN/FN) を行うための真値となるゴールデンセット 20 件 (blind 10 + covered 10) を独立に作成し、カズヤレビューを経てから第 2 段階 (F-verify-jp-coverage-measure) で実際の精度測定を行う 2 段階構成。ゴールデンセットの品質が F-verify-jp-coverage 全体の信頼性を決めるため、判断密度の高い真値判定を独立バッチに切り分けた。
  - 対応内容: (1) `docs/runs/F-verify-jp-coverage/golden_set.json` を新規作成 (20 entries valid JSON、blind 10 + covered 10)。(2) blind 候補は F-13.B 過去キャッシュ (jp_coverage_cache に has_jp_coverage=False が残る 6 件) + 過去試運転 evidence.json から has_jp_view=0.0 + coverage_gap_score>=6.0 + sources.jp=[] を満たすヒューリスティック抽出候補 (18 件) から region/topic 多様性を考慮して 10 件選定。(3) covered 候補は WebSearch で 2026 年 4-5 月の主要国際ニュース (Trump-Hormuz / Russia-Ukraine 停戦 / 米中関税 / 教皇レオ 14 世警告 / Lula-Amazon / NVIDIA / Boko Haram / Mali 国防相殺害 / India-Pakistan Kashmir / フーシ-イラン支援表明) の JP_MEDIA_WHITELIST Tier 1-4 直接報道 URL を確認。(4) 真値判定は F-13.B 自体を呼ばず WebSearch ツールで Claude Code が独立に日本語検索 (例: タイトル + 'NHK 朝日 日経' 等) を実行 (自己参照回避)。F-13.B 過去判定は f13b_prior_verdict フィールドに参考情報として併記のみ。(5) 各 entry に title / summary / expected_has_jp_coverage / expected_tier / source_run / topic_category / region / volume_in_jp / manual_verification_note / manual_verification_urls 完備。(6) diversity_check (region/topic/tier/volume) + bias_note (中東バイアスは試運転データの構造的反映) + tier_2_4_only_deviation_note (仕様要求 ≥2 に対して 1 件達成、構造的困難の理由明記)。(7) kazuya_review_required_ids 5 件 (blind_002 / 004 / 005 / 006 / 009) を明示、共通パターン (広範な事件は Tier 1 報道あり、MEE 記事の核心 = 特定の構造分析角度は未報道) を kazuya_review_summary に記述。(8) next_batch_handoff に F-verify-jp-coverage-measure の期待 input/output とカズヤレビューゲートを定義。(9) BATCH_PROTOCOL Task 1-5 軽量版ドッグフーディング実施 (DECISION_LOG / FUTURE_WORK / DISCUSSION_NOTES / CURRENT_STATE 更新)。リグレッション影響なし (docs/ + docs/runs/ のみ追加、src/ tests/ configs/ CLAUDE.md は 0 行変更、baseline 1315 passed 維持)。
  - 残課題: F-verify-jp-coverage-measure 着手 (緊急度 高セクションに新規エントリ追加済み、カズヤレビュー後に着手)
  - 関連ファイル: `docs/runs/F-verify-jp-coverage/golden_set.json` (新規), `docs/DECISION_LOG.md` (本バッチエントリ追加), `docs/FUTURE_WORK.md` (F-verify-jp-coverage 改訂 + F-verify-jp-coverage-measure 新規追加 + 本エントリ追加), `docs/DISCUSSION_NOTES.md` (F-13.B 動作仕様の検討課題 1 エントリ追加), `docs/CURRENT_STATE.md` (main HEAD / 直近 5 件 / 次バッチ候補刷新)

- **議論結果反映 + コアミッション 2 系統並立の docs 化 (F-doc-cleanup-followup)** (F-doc-cleanup-followup / 2026-05-03 完了)
  - 発生バッチ: F-doc-cleanup (2026-05-03 / e34f36e、main マージ 3e817d8) 完了直後、カズヤとの議論で 3 つの追加判断が確定 (大規模調査機能登録 / ★最重要 コアミッション 2 系統並立訂正 / クラウド誤り 7 過小評価)。これらは F-doc-cleanup のスコープ外で、別バッチで反映する必要があった。特にコアミッション 2 系統並立は、F-doc-cleanup で CLAUDE.md の「プロジェクト概要」セクションを削除して CURRENT_STATE 参照に統合した結果、現状 docs のどこにもコアミッションが明文化されていない状態となっており、別チャット移行時のクラウド誤り 7 (系統 1 中心理解で系統 2 を過小評価) の再発リスクが極めて高い構造だった。
  - 対応内容: (Task A) DISCUSSION_NOTES.md に 3 エントリ追加 = (1) 大規模調査機能 (オンデマンド深掘りパイプライン): Phase B 以降の新選択肢として、井上 vs 中谷の例を含む実装上の主要論点 6 点と Phase 配置を記録、(2) ★最重要 — Hydrangea コアミッション 2 系統並立: 系統 1 (silence_gap) と系統 2 (framing_inversion + 構造分析) の並立、既存構造との関係 (framing_inversion 軸 / multi_angle 5 観点 / media_divergence) を明文化、(3) クラウド誤り 7 — 系統 1 中心理解で系統 2 を過小評価: 訂正前のクラウド理解と教訓・類似リスク・防止策を記録。Active 件数 18 → 21。(Task B) CURRENT_STATE.md 冒頭に新セクション「0. Hydrangea コアミッション (2 系統並立)」を追加: 系統 1 / 系統 2 の説明、ブランドポジション、3 チャンネル構想と現フォーカス、Phase B 以降の新選択肢 (大規模調査機能) を集約。既存セクション 1-8 はそのまま維持 (リナンバーしない)。末尾注記に本バッチ概要追記。(Task C) BATCH_PROTOCOL Task 1-5 を本バッチ自身に適用 (ドッグフーディング)。リグレッション影響なし (docs/ のみ変更、src/ tests/ configs/ CLAUDE.md は 0 行変更、baseline 1315 passed 維持)。
  - 関連ファイル: `docs/DISCUSSION_NOTES.md` (3 エントリ追加 + 最終更新日更新), `docs/CURRENT_STATE.md` (新セクション「0. Hydrangea コアミッション (2 系統並立)」冒頭追加 + 最終更新日更新 + 末尾注記更新), `docs/DECISION_LOG.md` (本バッチエントリ追加), `docs/FUTURE_WORK.md` (本エントリ追加)

- **文書負債の一括根本治療 (F-doc-cleanup)** (F-doc-cleanup / 2026-05-03 完了)
  - 発生バッチ: F-state-protocol / F-state-protocol-supplement / F-doc-backfill / F-doc-backfill-supplement / F-cleanup-merge-streak の文書整備系 5 連発の最終仕上げ。Phase A.5-3a 完了 → A.5-3a-verify 着手前に過去の文書負債 (F-13 隠れ層未昇格、DECISION_LOG 遡及記録の未完、CLAUDE.md の現運用乖離、REFACTORING_PLAN.md の重複ドキュメント化、2026-05-03 議論結果の docs 未反映、拡張性差し込み判断ルールの暗黙運用) を一括清算する必要があった。カズヤ哲学「対症療法じゃなくて根本治療」「負の遺産残さないように」に従い、注記による応急処置ではなく文書構造そのものを整地。
  - 対応内容: (Task A) F-13 隠れ層を防衛機構の正式 5 層目として昇格 — DECISION_LOG エントリ追加、CURRENT_STATE 防衛機構表を 4+1 → 5 層化、EDITORIAL_MISSION_FILTER_DESIGN.md に F-13 隠れ層セクション追加、DISCUSSION_NOTES の該当エントリ削除。(Task B) DECISION_LOG 遡及記録 7 エントリ追加 — F-13 / F-13.B / F-15 / F-16-A / F-12-A / F-12-B / F-14 の本体エントリを既存 docs から事実集約のみで再構成 (新規情報の創作なし)、各エントリにコミットハッシュと日時を実測値で記録。(Task C) CLAUDE.md 全面書き直し — 責務を「Claude Code 振る舞い指針」に集約、プロジェクト概要 / 不変原則 / 触ってはいけないリスト / 将来対応リスト運用 / FUTURE_WORK レビュータイミング / ファイル配置等の重複セクションを完全削除し、CURRENT_STATE / BATCH_PROTOCOL への導線のみに整理。(Task D) REFACTORING_PLAN.md 整理 — 冒頭にアーカイブ注記追加 (歴史的記録として保持、Phase 命名整合化)、FUTURE_WORK 緊急度低に最終整理エントリ追加。(Task E) 2026-05-03 議論内容の docs 反映 — DISCUSSION_NOTES Phase B 方向性エントリを 3 択構造に更新、クラウド誤り 6 (過剰拡張性の罠) 追加、DECISION_LOG に「Phase B 方向性整理 + 拡張性原則の力点確定 + verify 順序見直し」エントリ追加、FUTURE_WORK の Phase A.5-3a-verify セクションを順序見直し (1st: jp-coverage、2nd: 3b 着手、perspective/script-quality は 3b/3c 並走、image-prompt-spec は 3b 直前 or 3b 内) に合わせて更新。(Task F) 拡張性差し込み判断ルールの BATCH_PROTOCOL 明文化 — 3 条件 + 4 つの過去判断例 (ChannelConfig YAML 化 / Publisher 抽象 / Renderer 抽象化 / Content Format 抽象化) + 例外 (文書層) を新セクションとして追加。(Task 1-5 のドッグフーディング) BATCH_PROTOCOL Task 1-5 を本バッチ自身に適用。リグレッション影響なし (docs/ + CLAUDE.md のみ変更、src/ tests/ configs/ は 0 行変更、baseline 1315 passed 維持)。
  - 関連ファイル: `docs/DECISION_LOG.md` (Task A エントリ + Task B 7 エントリ + Task E-3 エントリ = 計 9 エントリ追加), `docs/CURRENT_STATE.md` (防衛機構表 5 層化 + 次バッチ候補刷新 + main HEAD / 直近 5 件ログ / baseline 実測値更新), `docs/BATCH_PROTOCOL.md` (拡張性差し込み判断ルール新設), `docs/DISCUSSION_NOTES.md` (F-13 隠れ層エントリ削除 + Phase B エントリ更新 + クラウド誤り 6 追加 = 18 → 17 → 18 Active), `docs/EDITORIAL_MISSION_FILTER_DESIGN.md` (F-13 隠れ層セクション追加), `docs/REFACTORING_PLAN.md` (冒頭アーカイブ注記追加), `docs/FUTURE_WORK.md` (verify 順序更新 + REFACTORING_PLAN 整理エントリ追加 + 本エントリ), `CLAUDE.md` (全面書き直し)

- **「連続 main マージ成功カウント」廃止 (F-cleanup-merge-streak)** (F-cleanup-merge-streak / 2026-05-02 完了)
  - 発生バッチ: F-state-protocol (2026-05-01) で CURRENT_STATE.md / BATCH_PROTOCOL.md に「連続 main マージ成功カウント」を導入したが、F-state-protocol-supplement / F-doc-backfill / F-doc-backfill-supplement の 3 連続バッチで Claude Code が Task 5 でこの数値を更新し忘れる事象が発生 (CURRENT_STATE.md は 11 連続のまま、実際は 15 連続)。カズヤとの議論 (2026-05-02) で指標自体の意味を再検討した結果、(1) 何の意思決定にも使えない (12 連続と 100 連続で何が違うのか?)、(2) 品質保証は別の指標 (baseline 1315 passed / 試運転動画化率) で担保されている、(3) 「カウントを途切れさせたくない」という悪いインセンティブを生む、(4) 重要数値 (main HEAD / baseline / Phase) と並べると情報ノイズになる、と判明。カズヤ哲学「対症療法じゃなくて根本治療」「負の遺産残さないように」に照らし、形骸化リスクのある指標を早期削除。
  - 対応内容: (1) `docs/CURRENT_STATE.md` の「連続 main マージ成功カウント」項目を完全削除 + main HEAD コミット (1e4a932 → c736dc2) と直近 5 件コミットログを実測値で更新 (3 連続バッチでの Task 5 数値更新漏れを回収)。(2) `docs/BATCH_PROTOCOL.md` の Task 5 仕様から「連続 main マージ成功カウント」言及を完全削除し、「main HEAD ハッシュは `git log -1 --format=%H` で実測値を取得、直近 5 件ログは `git log --oneline -5` で取得」の明示注記を追加 (機械的踏襲・更新漏れの再発防止)。(3) `docs/DECISION_LOG.md` に「F-cleanup-merge-streak — 連続 main マージ成功カウント廃止」エントリ追加 (廃止理由 4 点 + 悪いインセンティブの位置付け)。(4) `docs/DISCUSSION_NOTES.md` に「仕組み導入時の機械的踏襲リスク」エントリ追加 (将来の F-state-protocol-v2 等で「指標導入チェックリスト」として運用ルール化検討の学習材料)。(5) BATCH_PROTOCOL Task 1-5 を本バッチ自身に適用 (ドッグフーディング)。リグレッション影響なし (docs/ のみ変更、src/ tests/ configs/ は 0 行変更、baseline 1315 passed 維持)。
  - 関連ファイル: `docs/CURRENT_STATE.md` (連続成功カウント削除 + main HEAD / 直近 5 件ログ更新), `docs/BATCH_PROTOCOL.md` (Task 5 仕様修正 + git log 実測値取得の明示), `docs/DECISION_LOG.md` (本廃止エントリ追加), `docs/DISCUSSION_NOTES.md` (機械的踏襲リスクエントリ = 18 Active), `docs/FUTURE_WORK.md` (本エントリ)

- **画像生成候補確定 + 自動投稿フェーズ方針 + 拡張性原則の明文化 (F-doc-backfill-supplement)** (F-doc-backfill-supplement / 2026-05-02 完了)
  - 発生バッチ: F-doc-backfill (2026-05-02) 直後にカズヤとの議論で 3 つの追加判断が確定: (1) ChatGPT Images 2.0 (gpt-image-2) を画像生成候補に正式追加 (DALL-E 3 から差し替え、2026-04-21 リリースの OpenAI 最新モデル、Image Arena #1)、(2) 自動投稿フェーズ方針確定 (Phase A.5-3d は geo_lens のみ単独本番、TikTok と YouTube Shorts 両方同時、完全自動投稿)、(3) 拡張性原則の明文化 (Phase A.5-3c 合成パート自動化実装時に「将来の多チャンネル対応 / 別形式展開を阻害しない最小限の抽象化」を設計原則として遵守)。Phase B 以降の方向性 (japan_athletes / k_pulse 追加 / 動画継続 / 独自メディア化 / カテゴリ細分化等) は Phase A.5-3d 安定稼働後に判断保留。
  - 対応内容: (1) `docs/FUTURE_WORK.md` の F-image-prompt-spec / Phase A.5-3b / F-image-gen-integration の画像生成ツール候補を ChatGPT Images 2.0 (gpt-image-2) に差し替え (DALL-E 3 削除、価格・特徴・比較観点の補足追記)。(2) `docs/FUTURE_WORK.md` の Phase A.5-3d エントリに「投稿対象: geo_lens のみ」「投稿先: TikTok + YouTube Shorts 同時」「投稿モード: 完全自動 (cron 6 時間おき、人手介入ゼロ)」「拡張性確保: configs/channels/{channel_id}.yaml で投稿先 / 形式 / カテゴリを切替可能に」を明記。(3) `docs/DECISION_LOG.md` に 4 エントリ追加 (本バッチ概要 + ChatGPT Images 2.0 採用 + 自動投稿フェーズ方針確定 + 拡張性原則の明文化)。(4) `docs/DISCUSSION_NOTES.md` に「Phase B 以降の方向性未確定」エントリ追加 (シナリオ A〜E の整理、Phase A.5-3d 安定稼働後に再評価)。(5) `docs/CURRENT_STATE.md` に「Phase A.5-3d 投稿対象の補足」セクションを追加 (geo_lens のみ / TikTok + YouTube 同時 / 完全自動 + Phase A.5-3c 拡張性原則遵守)。(6) BATCH_PROTOCOL Task 1-5 を本バッチ自身に適用 (ドッグフーディング)。リグレッション影響なし (docs/ のみ変更、src/ tests/ configs/ は 0 行変更、baseline 1315 passed 維持)。
  - 関連ファイル: `docs/FUTURE_WORK.md` (F-image-prompt-spec / Phase A.5-3b / F-image-gen-integration / Phase A.5-3d 改訂 + 本エントリ), `docs/DECISION_LOG.md` (4 エントリ追加), `docs/DISCUSSION_NOTES.md` (1 エントリ追加 = 17 Active), `docs/CURRENT_STATE.md` (Phase A.5-3d 投稿対象の補足セクション追加)

- **過去 19 セッション分の積み残し登録 + ロードマップ大幅改訂 (F-doc-backfill)** (F-doc-backfill / 2026-05-02 完了)
  - 発生バッチ: F-state-protocol / F-state-protocol-supplement で CURRENT_STATE.md / DISCUSSION_NOTES.md / Phase A.5-3a-verify ロードマップを整備した直後、2026-05-02 のカズヤとの議論で「F-verify-e2e / F-verify-rss は過剰防衛」「ElevenLabs 採用なら macOS say の Linux 対応 (F-16-B-pre) は無意味」「動画合成は Remotion で確定 (Phase A.5-3b から使う)」「画像プロンプト出力仕様の確認が必要」「過去 19 セッション分の積み残し (Phase 1 / Phase B / Phase C / クラウド誤り 1-4 / 三角測量未対応 / 3 ソース対比未実装 等) が未登録」が判明。ロードマップを 4 段階 (3a-verify → 3b → 3c → 3d) に再構成する必要があった。
  - 対応内容: (1) FUTURE_WORK.md の Phase A.5-3a-verify を 5→4 カテゴリに縮小 (F-verify-e2e / F-verify-rss を削除、F-image-prompt-spec を新規追加)。(2) Phase A.5-3b を Remotion + ElevenLabs + 画像生成前提に書き直し (CapCut 仮組み案を廃止)。(3) Phase A.5-3c (合成パート自動化) を新設、F-elevenlabs-integration / F-image-gen-integration / F-video-compose-integration / F-cron の 4 エントリを登録。(4) Phase A.5-3d (投稿前ゲート + 自動投稿) を新設。(5) Phase 1 (1-A〜1-D + TECH_DEBT 2.1/2.2/2.3/2.5 同時対応) を緊急度 中に登録。(6) Phase B (B-1〜B-7) と Phase C (C-1〜C-5) を緊急度 低に登録。(7) 観察中項目 (F-17 候補 / _FRAMING_RESULTS LRU / 並列化検討) を新設。(8) DISCUSSION_NOTES.md にクラウド誤り 1-4 + 三角測量未対応 + 3 ソース対比部分実装の 6 エントリ追加。(9) DECISION_LOG.md に F-doc-backfill 概要 + 「Phase A.5-3a-verify スコープ縮小」「macOS say 廃止 + ElevenLabs 前倒し」「動画合成ツール Remotion 採用」「Supabase 移行『今週末は危険すぎる』判断 (Apr 30 遡及)」「6 パターン武器庫 → 4 パターン削減経緯 (遡及)」「Hook 5 類型 / 視聴維持ピーク 4 点設計の廃止経緯 (遡及)」の 7 エントリ追加。(10) CURRENT_STATE.md の「次バッチ候補」を新ロードマップに合わせて全置換更新。(11) BATCH_PROTOCOL Task 1-5 を本バッチ自身に適用 (ドッグフーディング)。リグレッション影響なし (docs/ のみ変更、src/ tests/ configs/ は 0 行変更、baseline 1315 passed 維持)。
  - 関連ファイル: `docs/FUTURE_WORK.md` (Phase A.5-3a-verify 縮小 + 3c/3d/Phase1/B/C/観察中項目 新設 + 本エントリ), `docs/DISCUSSION_NOTES.md` (6 エントリ追加 = 16 Active), `docs/DECISION_LOG.md` (7 エントリ追加), `docs/CURRENT_STATE.md` (次バッチ候補刷新)

- **CURRENT_STATE / DISCUSSION_NOTES 導入と不変原則 2 の正確化 (F-state-protocol)** (F-state-protocol / 2026-05-01 完了)
  - 発生バッチ: Phase A.5-3a で 11 連続 main マージ成功 (F-12-A → F-12-B-1-extension) を達成したが、チャット移行のたびに 2806 行の引き継ぎプロンプトを手作業で再構築する運用が持続不可能になった。過去の決定事項 (C-1/C-2/C-3 RPM 対策、F-13 隠れ層、F-7-α 部分実装等) がバッチ歴史リストから消える事故、不変原則 2「script_writer.py 一切変更不可」が実装と乖離 (F-12-A / F-12-B / Batch 5 で大改修済み、新ルート稼働中)、DECISION_LOG / FUTURE_WORK が時系列ログとして機能する一方で「今この瞬間のスナップショット」と「議論中の未確定メモ蓄積」の仕組みがない、といった構造的課題が顕在化していた。
  - 対応内容: (1) `docs/CURRENT_STATE.md` を新規作成 — 8 セクション構成 (リポジトリ状態 / 現在のフェーズ / 直近試運転 / 防衛機構の現状 4+1 層 / 触ってよい・ダメ領域マップ / 不変原則 5 つ / カズヤの直近フィードバック / 関連ドキュメント導線)、初回値として main HEAD `1e4a932` / baseline `1315 passed` / 11 連続成功 / 試運転 7-K 動画化率 100% / Phase A.5-3a 完了 → A.5-3a-verify 着手前を投入。バッチ完了時に「全置換更新」する運用 (追記ではない)。(2) `docs/DISCUSSION_NOTES.md` を新規作成 — 「未分類 (Active)」と「アーカイブ」の 2 セクション構成、初期エントリ 10 件投入 (手動 PoC 軌道修正 / C-1/C-2/C-3 欠落 / CLAUDE_CODE_INSTRUCTIONS.md 遺産化 / スコープ転換昇格ルール / STEP 3 と F-12-B-1 のレイヤー関係 / ★不変原則 2 乖離 / F-13 隠れ層 / target_enemy 排除 / F-12-B-1.5 と原則 2 不整合 / F-7-α 部分実装済み)。(3) `docs/BATCH_PROTOCOL.md` を拡張 — 不変原則 5 つを A.5-3a 時点版に差し替え (特に不変原則 2 を「既存ルート不可、新ルート可、`_CHAR_BOUNDS` 等の定数調整は最小改変なら許容」に正確化)、Task 4 (DISCUSSION_NOTES 整理: 4-A 新規追加 + 4-B 既存再評価) と Task 5 (CURRENT_STATE 全置換更新) を追加、バッチプロンプトテンプレートを Task 1-5 に更新。(4) `CLAUDE.md` を更新 — 必読ドキュメントリストの最上位に CURRENT_STATE.md を配置、DISCUSSION_NOTES.md を 5 番目に追加、参照順序を明示化。(5) 本バッチ自身に Task 1-5 を適用 (ドッグフーディング)。リグレッション影響なし (docs/ + CLAUDE.md のみ変更、src/ tests/ configs/ は 0 行変更、baseline 1315 passed 維持)。
  - 関連ファイル: `docs/CURRENT_STATE.md` (新規), `docs/DISCUSSION_NOTES.md` (新規), `docs/BATCH_PROTOCOL.md` (不変原則差し替え + Task 4/5 追加), `CLAUDE.md` (必読リスト刷新), `docs/DECISION_LOG.md` (F-state-protocol エントリ), `docs/FUTURE_WORK.md` (本エントリ)

- **punchline 定義の「シニカル × 具体着地」両立化 (F-12-B-1-extension)** (F-12-B-1-extension / 2026-05-01 完了)
  - 発生バッチ: F-12-B-1 (視聴者ファースト原則追加) 完了後の試運転で、punchline 末尾に抽象比喩の癖が残存することが観察された (「地政学の檻に閉じ込める」「冷徹な力学」)。根本原因は `configs/prompts/analysis/geo_lens/script_with_analysis.md` STEP 2 の punchline 定義「シニカルかつ知的な余韻」が抽象詩を呼び込んでいたこと、および例示された「綺麗事を信じた側が損をする」が STEP 3 禁止表現 (物申す系 YouTuber 構文) と矛盾していたこと。視聴者ファースト原則 (抽象より具体) と punchline 定義 (シニカルな余韻) の方向性が一貫していない構造的問題。
  - 対応内容: STEP 2 punchline 定義のみを修正 (hook / setup / twist は不変)。「シニカルかつ知的な余韻を残す」は保持しつつ、「ただし『シニカル』は抽象詩や抽象比喩で飾ることではない。視聴者の生活実感（電気代、物価、給料、税金、日常の選択）に着地して初めて、シニカルさが知的な余韻として機能する」で両立を明文化。優れた例として「秩序を信じる代償を、私たちは電気代という形で支払うことになる」(F-12-B-1 議論でカズヤが評価した実例 ── シニカル → 具体着地の両立) を、避けるべき例として「地政学の檻に閉じ込められた国の宿命」「冷徹な力学が動く」(試運転で観察された抽象比喩) を併記。「綺麗事を信じた側が損をする」例を削除して STEP 3 との矛盾を解消。試運転は LLM 出力依存のため未実施 (時間と再現性を考慮、必須化せず継続観察項目とした)。リグレッション影響なし (1315 passed 維持)。
  - 関連ファイル: `configs/prompts/analysis/geo_lens/script_with_analysis.md` (STEP 2 punchline のみ +10 行 / -2 行), `docs/DECISION_LOG.md` (F-12-B-1-extension エントリ), `docs/FUTURE_WORK.md` (本エントリ)

- **台本プロンプトの「視聴者ファースト」原則追加 (F-12-B-1)** (F-12-B-1 / 2026-05-01 完了)
  - 発生バッチ: 試運転 7-K (2026-05-01) の baseline 台本 (cls-7bd1406438b6 FIFA 提訴 / cls-579833967531 フーシ派) で、カズヤから 6 個の問題が指摘された (略しすぎ「イスラエル入植地クラブ」/補足なし「スポーツ仲裁裁判所」/不明「ロシア侵攻時の即時排除」/直訳「公然たる支持」/抽象比喩「地政学的断層」「直撃弾」/硬い文語「発動」「ツール」)。`configs/prompts/analysis/geo_lens/script_with_analysis.md` を分析した結果、「扇動・陰謀論の禁止」(STEP 3) は強力だが「視聴者へのわかりやすさ」への配慮が皆無で、LLM が「教科書っぽい硬い分析調」に寄っていたことが根本原因。
  - 対応内容: 同プロンプトの【ターゲット】直後・【入力データ】の前に「【視聴者ファーストの編集姿勢】」セクションを追加 (3 原則: 聞いてわかる / 抽象より具体 / 読み上げて自然 + 合格基準「TikTok/Shorts で違和感なく聞けるか」)。NG リストではなく姿勢として記述し、判断は LLM の知性に委ねる設計。既存セクションは一切変更せず追加のみ。あわせて `docs/BATCH_PROTOCOL.md` 不変原則 2 の例外条項を `configs/prompts/script/` → `configs/prompts/` に拡大し、現状の主戦場が `configs/prompts/analysis/geo_lens/` であることを注記。試運転 (cls-56c4197b6fd2 米イスラエル隠密作戦) で「中東独立メディアのミドル・イースト・アイ」のような固有名詞補足、「動かしたんです」「ある日突然」のような話し言葉的接続を確認。char validation で 1 リトライ発生 (setup=94→82 字)、許容範囲だが継続観察項目として F-12-B-1.5 を緊急度中に新設。
  - 旧 F-12-B-1 (blind_spot_global 用フレーム追加) は試運転 7-K の結果を受けて視聴者ファースト原則の方が優先と判断され、本エントリにスコープを再定義した。
  - 関連ファイル: `configs/prompts/analysis/geo_lens/script_with_analysis.md`, `docs/BATCH_PROTOCOL.md`, `docs/DECISION_LOG.md` (F-12-B-1 エントリ), `docs/FUTURE_WORK.md` (本エントリ)

- **文書自動更新プロトコルの確立 (F-doc-protocol)** (F-doc-protocol / 2026-05-01 完了)
  - 発生バッチ: Phase A.5-2 の 7 連続バッチで DECISION_LOG.md / FUTURE_WORK.md の更新が散逸し、「台本の日本語改善」「document 更新」「手動 PoC」等の重要事項が忘却される問題が発生。月次レビュー (FW-1) だけでは速度が追いつかないと判明。
  - 対応内容: `docs/BATCH_PROTOCOL.md` を新規作成し、各バッチ完了時に必須となる 3 タスク (Task 1: DECISION_LOG エントリ追加 / Task 2: FUTURE_WORK 更新 / Task 3: 完了レポート明記) と 5 つの不変原則を明文化。`CLAUDE.md` 冒頭に「Hydrangea Batch Protocol」セクションを追加し、必読ドキュメントリストにも追記することで全セッションで参照される動線を整備。本プロトコル自体も月 1 レビュー対象に登録。`src/` `tests/` `configs/` には一切手を入れず、ドキュメント層のみで仕組み化 (リグレッション 1315 passed 維持)。
  - 関連ファイル: `docs/BATCH_PROTOCOL.md` (新規), `CLAUDE.md` (参照追加), `docs/DECISION_LOG.md` (Task 1 最初の実装例), `docs/FUTURE_WORK.md` (Task 2 最初の実装例)

- **rescue path の Hydrangea ミッション本丸との矛盾 (F-13-B で完全廃止)** (F-13-B / 2026-05-01 完了)
  - 発生バッチ: 試運転 7-J (2026-04-30) で動画化率 0%。Slot-1 候補が JP=0 件で `requires_more_evidence=True` → rescue 発動 → script skip。これは Hydrangea ミッション「日本で封殺されている海外ニュース」(blind_spot_global) を skip する本末転倒な設計だった。
  - 対応内容: `_write_judge_rescue()` 関数と main.py 内の rescue 分岐を完全撤去。判定ロジック (`is_rescue_candidate`) は src/triage/gemini_judge.py 側に残置 (不変原則 3 遵守) しつつ、main.py からは呼ばれない。requires_more_evidence=True でも必ず動画化フローへ進む。試運転 7-K で 3/3 Slot 完了 (article 生成 100%、Slot-1 video まで生成) を確認。judge_report.json / followup_queries.* の新規出力が無いことも確認 (既存ファイルは履歴として残置)。
  - 関連ファイル: `src/main.py`

- **日本未報道判定のための Web 検証導入 (F-13-B 完了)** (F-13-B / 2026-05-01 完了)
  - 発生バッチ: F-13-A で JP RSS を 13 媒体に拡張後もニッチ海外ニュースは JP=0 件のケースが残ることを確認。RSS 取得漏れと「真の日本未報道」を区別できないままだった。
  - 対応内容: `src/triage/jp_coverage_verifier.py` に `JpCoverageVerifier` を新規実装。Gemini Grounding (Google Search) で日本語検索を実行し、ホワイトリスト (新聞・テレビ・通信社・主要ビジネスメディア計 27+ ドメイン) と除外リスト (Yahoo!ニュース・SNS・個人ブログ等) で照合する。判定基準は「大手メディアの報道有無のみ」(個人投稿は判定材料にしない、Hydrangea のミッション本丸: 大手の空白を埋める)。24h SQLite キャッシュ (`jp_coverage_cache` テーブル新設) で重複検証を抑制、月コスト約 $4.2 想定。Grounding API エラー時は `has_jp_coverage=True` で安全側に倒す。環境変数: `JP_COVERAGE_VERIFIER_ENABLED` / `JP_COVERAGE_CACHE_HOURS` / `JP_COVERAGE_GROUNDING_MODEL`。試運転 7-K で Slot-2 (cls-33b4f4960bf9) と Slot-3 (cls-204a683f73ee) の両方で `has_jp_coverage=False` を確認、blind_spot_global として動画化フローへ進めた。
  - 関連ファイル: `src/triage/jp_coverage_verifier.py` (新規), `src/storage/db.py` (jp_coverage_cache テーブル), `src/main.py` (Web 検証統合), `src/shared/config.py`, `.env.example`, `tests/test_f13b_rescue_abolition.py` (36 テスト)

- **日本ソース基盤の弱さ (一部対処)** (F-13-A / 2026-05-01 部分完了)
  - 発生バッチ: 試運転 7-J (2026-04-30) で動画化率 0% を観測。日本ソース 8 媒体のみで主要海外ニュースを拾えず、「日本未報道」誤判定が多発。
  - 対応内容: `configs/sources.yaml` に Mainichi / Kyodo (47news.jp 経由) / JIJI / Bloomberg_JP / Reuters_JP の 5 媒体を追加 (8 → 13 enabled JP sources)。`configs/source_profiles.yaml` に対応する authority profile を追加 (tier=top: Mainichi/Kyodo/JIJI、tier=major: Bloomberg_JP/Reuters_JP)。各 RSS は 2026-05-01 疎通確認済み (status=200, entries 50 件取得確認)。src/ tests/ には変更なし (不変原則 5 つ遵守)。
  - 残課題: 13 媒体に拡張してもニッチ海外ニュース (Gaza 電力危機等) は依然 JP ソース 0 件のケースが残る → F-13-B (Web 検証 + rescue 廃止) で根本対処
  - 関連ファイル: `configs/sources.yaml`, `configs/source_profiles.yaml`

- **MAX_PUBLISHES_PER_DAY ハードコード上限による Slot skip 問題** (F-16-A / 2026-04-30 完了)
  - 発生バッチ: 試運転 7-I (2026-04-29) で動画化率 67% (2/3) で頭打ち。Slot-3 (UAE OPEC) は AnalysisLayer 完了済みだったが MAX_PUBLISHES_PER_DAY=5 のハードコード制限で skip された
  - 対応内容: per-run 上限を `TOP_N_VIDEOS_PER_RUN` (default 1) / `TOP_N_ARTICLES_PER_RUN` (default 3) に分離。`_generate_outputs()` に `generate_video_track: bool = True` パラメータを追加し、Slot index >= TOP_N_VIDEOS_PER_RUN は article のみ生成。`MAX_PUBLISHES_PER_DAY` は default 999 に変更し実質撤廃 (後方互換のため env / コードからは読み続ける)。video > article は min クランプして警告。AnalysisLayer Top 3 対象 (F-15) と publish_count インクリメント (後方互換) は維持。
  - cron 自動実行 (F-16-B) と組み合わせて公開頻度を制御する設計に移行。本番運用想定: 4 run/日 × 1 動画 = 4 動画/日 + 4 run × 3 記事 = 12 記事/日
  - 関連ファイル: `src/shared/config.py`, `src/main.py`, `.env.example`, `tests/test_f16a_per_run_limits.py` (26 テスト追加)

- **Slot-event_id 同期問題（AnalysisLayer 対象 vs Top-3 台本生成対象の不整合）** (F-15 / 2026-04-29 完了)
  - 発生バッチ: 試運転 7-H' (2026-04-29 21:20) で動画化率 1/3 (33%) で頭打ちが発覚
  - 対応内容: `src/main.py` の AnalysisLayer 対象選定を `all_ranked[:_top_n_for_analysis]`（Tier 1 score 降順）から、Top-3 台本生成ループと同じ `sorted(all_ranked, key=lambda se: _elite_judge_results[...].total_score, reverse=True)[:_top_n_for_analysis]`（Elite Judge total_score 降順）に変更。これにより両ループが必ず同じ event_id 列を対象とするようになり、Slot-event_id ズレで「analysis_result is None, skipping」になっていた構造的問題を解消。
  - 関連ドキュメント: `docs/EDITORIAL_MISSION_FILTER_DESIGN.md` の F-15 セクション (該当があれば)
  - 関連ファイル: `src/main.py`, `tests/test_main_f15_slot_event_sync.py`
  - 試運転 7-I で動画化率の改善 (期待値 67-100%) を確認後にカズヤがマージ判断

- **Analysis Layer の hidden_stakes axis バグ** (F-3 / 2026-04-28 完了)
  - 発生バッチ: F-1.5 試運転で発覚 → F-3 で対応完了
  - 対応内容: `src/analysis/perspective_selector.py::select_perspective()` を 3 段階フォールバックに強化。LLM が Top3 外の axis (`hidden_stakes` 等) を選んだ場合や、`fallback_axis_if_failed` も Top3 にない場合でも、Step 2 で Top3 内の最高スコア候補を強制採用する。candidates が 1 件以上あれば必ず `PerspectiveCandidate` を返すため、Slot-2 / Slot-3 で `analysis_result=None` となり動画化失敗していた問題を解消。
  - 関連ドキュメント: `docs/EDITORIAL_MISSION_FILTER_DESIGN.md` の F-3 セクション
  - 関連ファイル: `src/analysis/perspective_selector.py`, `tests/test_perspective_selector.py`, `tests/test_analysis_engine.py`

- **Tier 階層の役割分け（E-3'）** (E-3' / 2026-04-28 完了)
  - 発生バッチ: 試運転7-A / 7-B で 503 待機 (5〜10分) が試運転時間 (13分) の大半を占めることが判明
  - 対応内容: `src/llm/factory.py` に `LIGHTWEIGHT_ROLES` / `QUALITY_ROLES` を定義し、`_get_tier_models_for_role(role)` / `_get_max_attempts_for_role(role)` で役割別に Tier 階層と MAX_ATTEMPTS を切り替えるよう改修。Lightweight 系統は GA 主軸 (gemini-2.5-flash → flash-lite → preview-lite → flash-preview) で 503 回避、Quality 系統は Preview 主軸 (gemini-3-flash-preview → 2.5-flash → preview-lite → flash-lite) で性能優先。env 由来のデフォルトを公式の性能順に正規化。
  - 関連ドキュメント: `docs/EDITORIAL_MISSION_FILTER_DESIGN.md` の E-3' セクション
  - 関連ファイル: `src/llm/factory.py`, `.env.example`, `tests/test_factory_role_tier_separation.py`

- **_MAX_ATTEMPTS_PER_TIER = 1（503 リトライ削減）** (E-3' / 2026-04-28 完了)
  - 発生バッチ: E-1 で見送り → E-3' で役割別 MAX_ATTEMPTS として実装
  - 対応内容: 当初は `_MAX_ATTEMPTS_PER_TIER=1` への一括変更を計画していたが、E-3' でより安全な役割別 MAX_ATTEMPTS に切り替え。`GEMINI_LIGHTWEIGHT_MAX_ATTEMPTS=2` / `GEMINI_QUALITY_MAX_ATTEMPTS=2` に統一 (失敗率約 0.002%)。`TieredGeminiClient` のコンストラクタに `max_attempts_per_tier` 引数を追加し、未指定時は既定値 3 を維持することで、`test_factory_quota_handling.py` の3テストを書き換えずに後方互換を保った。
  - 関連ドキュメント: `docs/EDITORIAL_MISSION_FILTER_DESIGN.md` の E-3' セクション
  - 関連ファイル: `src/llm/factory.py`, `.env.example`, `tests/test_factory_quota_handling.py` (変更なし)
