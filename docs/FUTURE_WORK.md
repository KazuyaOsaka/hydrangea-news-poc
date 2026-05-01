# Hydrangea — 将来対応リスト (FUTURE_WORK)

最終更新: 2026-05-02 (F-cleanup-merge-streak 完了)

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

### Phase A.5-3a-verify (F-state-protocol-supplement / 2026-05-02 登録)

- **F-verify-jp-coverage** ★最優先 (F-state-protocol-supplement / 2026-05-02 登録)
  - 背景: F-13.B JpCoverageVerifier の精度を実データで検証する。Phase A.5-3a 完了時点では理論動作のみ確認、実 precision/recall は未測定。Hydrangea コンセプト防衛機構の中核 (rescue 完全廃止後の唯一の JP 報道判定経路) であり、ここの精度がコンセプト整合性を決める。
  - 対応案: ゴールデンセット 20 件作成 (日本未報道 10 件 / 報道済み 10 件) で precision / recall を測定。閾値調整の判断材料にする。Grounding API 失敗時の安全側倒し (`has_jp_coverage=True`) の発動率も同時計測。
  - 検討時期: F-state-protocol-supplement 完了直後 (Phase A.5-3a-verify 開始の最優先)
  - 想定工数: 2-3 時間
  - 関連ファイル: src/triage/jp_coverage_verifier.py, tests/golden/jp_coverage/ (新規)

- **F-verify-perspective** (F-state-protocol-supplement / 2026-05-02 登録)
  - 背景: 4 軸 (cultural_blindspot / silence_gap / hidden_stakes / framing_inversion) のバランスを検証。DISCUSSION_NOTES #6 (F-12-B-2 axis 多様化) の着手判断材料となる。cultural_blindspot 偏重が確認されれば F-12-B-2 起動。
  - 対応案: 直近 50 イベントで axis 分布を集計、cultural_blindspot 偏重があれば F-12-B-2 起動判断。
  - 検討時期: F-verify-jp-coverage と並行可
  - 想定工数: 集計 1 時間 + 判断議論
  - 関連ファイル: src/analysis/perspective_extractor.py (読み取りのみ), data/output/ の AnalysisLayer 出力

- **F-verify-script-quality** (F-state-protocol-supplement / 2026-05-02 登録)
  - 背景: 新ルート (`generate_script_with_analysis`) の NG パターン出現頻度 / char validation リトライ率を測定。F-12-B-1.5 (文字数制約緩和) 着手判断材料を兼ねる。F-12-B-1 投入後 1 run の試運転では setup 1/1 でリトライ発動だが標本不足。
  - 対応案: 直近 30 件で NG 語彙頻度 / リトライ回数集計、`_CHAR_BOUNDS` 調整可否を判断。
  - 検討時期: F-verify-jp-coverage と並行可
  - 想定工数: 集計 1 時間 + 判断議論
  - 関連ファイル: src/generation/script_writer.py (読み取りのみ), data/output/ の script.json

- **F-image-prompt-spec** (F-doc-backfill / 2026-05-02 登録、F-doc-backfill-supplement / 2026-05-02 改訂)
  - 背景: Phase A.5-3b 手動 PoC で「自動生成された台本 + 画像プロンプト」を使って Nano Banana Pro / ChatGPT Images 2.0 (gpt-image-2) / Flux 1.1 Pro に画像生成依頼する想定だが、現状 video_payload_writer.py がシーンごとの画像プロンプトを十分な品質で出力しているか未確認。Phase A.5-3b 着手前に仕様確認 + 必要なら改修。
  - 対応案: (1) src/generation/video_payload_writer.py の現状調査 (シーンごとに画像プロンプトを出してるか / 統一末尾「cinematic, hyper-realistic, dark geopolitical thriller style, high contrast, dramatic lighting, vertical composition, 9:16 aspect ratio」が含まれてるか) (2) 不十分なら configs/prompts/ 配下のプロンプトファイルを改修 (3) 試運転で画像プロンプト品質を確認
  - 検討時期: F-verify-jp-coverage / F-verify-perspective / F-verify-script-quality と並行
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
