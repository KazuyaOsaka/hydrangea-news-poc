# Hydrangea — 将来対応リスト (FUTURE_WORK)

最終更新: 2026-05-01 (F-12-B-1-extension 完了)

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

---

## 完了済み（参考用）

各項目は以下の形式で記載:
- **タイトル** (完了バッチ / 完了日)
  - 何を対応したか

---

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
