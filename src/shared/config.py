from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_DIR = BASE_DIR / os.getenv("INPUT_DIR", "data/input")
NORMALIZED_DIR = BASE_DIR / os.getenv("NORMALIZED_DIR", "data/normalized")
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "data/output")
DB_PATH = BASE_DIR / os.getenv("DB_PATH", "data/db/hydrangea.db")
ARCHIVE_DIR = BASE_DIR / os.getenv("ARCHIVE_DIR", "data/archive")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# LLMプロバイダ選択 (gemini | groq | ollama)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")

# ── 運用スケジュール ──────────────────────────────────────────────────────────
# F-16-A: per-run 上限の分離 (公開チャネル概念の分離)。
# cron 6 時間おき自動実行 (本番リリース時の F-16-B で実装) × per-run 上限で
# 実質的な公開頻度を制御する。
#   TOP_N_VIDEOS_PER_RUN   — 1 run あたり script + video まで生成する候補数 (動画化対象)
#   TOP_N_ARTICLES_PER_RUN — 1 run あたり article まで生成する候補数 (Web 記事対象)
# 設計上 video ⊆ article。TOP_N_VIDEOS_PER_RUN > TOP_N_ARTICLES_PER_RUN は無効で、
# main.py 側で min(video, article) にクランプして警告する。
# Phase 1-A で ChannelConfig.publishing_limits に統合される予定。
TOP_N_VIDEOS_PER_RUN: int = int(os.getenv("TOP_N_VIDEOS_PER_RUN", "1"))
# 旧 TOP_N_GENERATION (F-4 で導入、Top-3 ループ + AnalysisLayer の対象件数)
# は概念的に「1 run あたりの記事生成数」と同じ。明示的に設定されていれば
# TOP_N_ARTICLES_PER_RUN の default 値として後方互換を保つ。
_LEGACY_TOP_N_GENERATION = os.getenv("TOP_N_GENERATION", "3")
TOP_N_ARTICLES_PER_RUN: int = int(os.getenv("TOP_N_ARTICLES_PER_RUN", _LEGACY_TOP_N_GENERATION))

# DEPRECATED (F-16-A): MAX_PUBLISHES_PER_DAY は per-day という単一概念で公開を
# ゲートしていたため、Slot-3 で AnalysisLayer 完了済み候補が 5 件上限で
# skip される事故 (試運転 7-I) が発生した。
# 後方互換のため env / コードからは読み続けるが、default を 999 に変更し
# 実質撤廃する。新コードは TOP_N_VIDEOS_PER_RUN / TOP_N_ARTICLES_PER_RUN を使うこと。
# cron 6 時間おき実行 × per-run 上限で実質的な公開頻度を制御する。
MAX_PUBLISHES_PER_DAY: int = int(os.getenv("MAX_PUBLISHES_PER_DAY", "999"))

# NOTE: 旧 RUNS_PER_DAY はコード上で参照されない dead constant だったため削除。
# 実行回数上限を設けたい場合は main.py で get_daily_stats()["run_count"] を
# チェックするコードと併せて新設すること。

# ── 実行モード ────────────────────────────────────────────────────────────────
# publish_mode (default): daily budget を exploration / publish_reserve に分割し、
#   production ステージ (editorial_mission_filter+judge+script+article) 用の予算を常時保護する。
# research_mode: 予算制限なしに全 LLM 呼び出しを許可（実験・デバッグ用）。
RUN_MODE: str = os.getenv("RUN_MODE", "publish_mode")

# publish_mode 時に production ステージ用として day_budget から確保する呼び出し数の最小値。
# デフォルト = 15: top-3 生成（script+article）× 3 本 + retry 余裕 + elite_judge 分
# BudgetTracker(publish_reserve_calls=...) に未指定時はこの値が使われる。
PUBLISH_RESERVE_CALLS: int = int(os.getenv("PUBLISH_RESERVE_CALLS", "15"))

# ── LLM 呼び出し予算 ──────────────────────────────────────────────────────────
# 1回の実行あたりの LLM 呼び出し上限
LLM_CALL_BUDGET_PER_RUN: int = int(os.getenv("LLM_CALL_BUDGET_PER_RUN", "30"))

# 1日あたりの LLM 呼び出し上限
LLM_CALL_BUDGET_PER_DAY: int = int(os.getenv("LLM_CALL_BUDGET_PER_DAY", "300"))

# normalized モードで各 JP クラスタにつき LLM に渡す EN 候補の上限
EN_CANDIDATES_PER_JP_CLUSTER: int = int(os.getenv("EN_CANDIDATES_PER_JP_CLUSTER", "2"))

# Gemini設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# 階層型フォールバック (TIER1 → TIER4 の順に試行、各 Tier は 3回指数バックオフ後に次へ)
GEMINI_MODEL_TIER1: str = os.getenv("GEMINI_MODEL_TIER1", "gemini-3.1-flash-lite-preview")
GEMINI_MODEL_TIER2: str = os.getenv("GEMINI_MODEL_TIER2", "gemini-3-flash-preview")
GEMINI_MODEL_TIER3: str = os.getenv("GEMINI_MODEL_TIER3", "gemini-2.5-flash")
GEMINI_MODEL_TIER4: str = os.getenv("GEMINI_MODEL_TIER4", "gemini-2.5-flash-lite")
GEMINI_MODEL_TIERS: list[str] = [
    GEMINI_MODEL_TIER1,
    GEMINI_MODEL_TIER2,
    GEMINI_MODEL_TIER3,
    GEMINI_MODEL_TIER4,
]

# 旧ロール別モデル変数 (後方互換; factory は GEMINI_MODEL_TIERS を使用)
GEMINI_SCRIPT_MODEL = os.getenv("GEMINI_SCRIPT_MODEL", GEMINI_MODEL_TIER1)
GEMINI_ARTICLE_MODEL = os.getenv("GEMINI_ARTICLE_MODEL", GEMINI_MODEL_TIER1)
GEMINI_TRIAGE_MODEL = os.getenv("GEMINI_TRIAGE_MODEL", GEMINI_MODEL_TIER2)
GEMINI_CLUSTER_MODEL = os.getenv("GEMINI_CLUSTER_MODEL", GEMINI_MODEL_TIER2)

# 旧環境変数 GEMINI_JUDGE_MODEL は JUDGE_MODEL の bootstrap デフォルトとして残す。
# 下流コードは JUDGE_MODEL を使うこと（GEMINI_JUDGE_MODEL は JUDGE_MODEL への alias で、
# 常に同値）。これにより .env の書き換えと run_summary の表記が食い違うことがなくなる。
_LEGACY_GEMINI_JUDGE_MODEL_ENV = os.getenv("GEMINI_JUDGE_MODEL", GEMINI_MODEL_TIER2)

# Gemini Judge fallback priority list (comma-separated, tried in order when
# GEMINI_JUDGE_MODEL is unavailable in the current API tier).
GEMINI_JUDGE_FALLBACK_MODELS: list[str] = [
    m.strip()
    for m in os.getenv(
        "GEMINI_JUDGE_FALLBACK_MODELS",
        "gemini-2.5-flash-lite,gemini-2.5-flash,gemini-2.0-flash-lite,gemini-2.0-flash,gemini-1.5-flash-8b,gemini-1.5-flash",
    ).split(",")
    if m.strip()
]

# ── Role-based model config ──────────────────────────────────────────────────
# Business logic must reference only roles ("merge_batch", "judge", "generation").
# factory.py resolves provider + model from these vars.
# .env → config.py → factory.py is the only allowed resolution path.

# merge_batch role: cluster post-merge / garbage filter (Gemini 経由は統一 Tier 階層を共有)
MERGE_BATCH_PROVIDER: str = os.getenv("MERGE_BATCH_PROVIDER", LLM_PROVIDER)
MERGE_BATCH_MODEL: str = os.getenv("MERGE_BATCH_MODEL", GEMINI_CLUSTER_MODEL)

# judge role: editorial judgment (always Gemini; independent of LLM_PROVIDER)
JUDGE_PROVIDER: str = os.getenv("JUDGE_PROVIDER", "gemini")
JUDGE_MODEL: str = os.getenv("JUDGE_MODEL", _LEGACY_GEMINI_JUDGE_MODEL_ENV)

# Back-compat alias — always equal to JUDGE_MODEL after both env vars are resolved.
# 新規コードは JUDGE_MODEL を使うこと。
GEMINI_JUDGE_MODEL: str = JUDGE_MODEL

# generation role: script + article generation (heavier capable model)
GENERATION_PROVIDER: str = os.getenv("GENERATION_PROVIDER", LLM_PROVIDER)
GENERATION_MODEL: str = os.getenv("GENERATION_MODEL", GEMINI_SCRIPT_MODEL)

# ── Gemini Judge 設定 ────────────────────────────────────────────────────────
# ジャッジを実行する上位候補の件数（LLM 呼び出し節約のため上限を設ける）
JUDGE_CANDIDATE_LIMIT: int = int(os.getenv("JUDGE_CANDIDATE_LIMIT", "3"))
# ジャッジを有効にするか（false にすると完全スキップ）
JUDGE_ENABLED: bool = os.getenv("JUDGE_ENABLED", "true").lower() != "false"

# Gemini API 呼び出し間の最小インターバル (秒) — 429 抑制のためのレート制限
# 後方互換用の共通値。Tier 別設定が無い場合のフォールバックとしてのみ使う。
GEMINI_CALL_INTERVAL_SEC: float = float(os.getenv("GEMINI_CALL_INTERVAL_SEC", "0.5"))

# ── Tier 別呼び出しインターバル (秒) — 各モデルの RPM 上限を尊重 ──────────────
# 安全マージン 70% を考慮した値をデフォルトに採用:
#   TIER1 (gemini-3.1-flash-lite-preview, RPM=15): 60 / (15 * 0.7) ≈ 5.7s
#   TIER2 (gemini-2.5-flash-lite,        RPM=10): 60 / (10 * 0.7) ≈ 8.6s
#   TIER3 (gemini-3-flash-preview,        RPM=5):  60 / (5  * 0.7) ≈ 17.2s
#   TIER4 (gemini-2.5-flash,              RPM=5):  60 / (5  * 0.7) ≈ 17.2s
GEMINI_CALL_INTERVAL_SEC_TIER1: float = float(os.getenv("GEMINI_CALL_INTERVAL_SEC_TIER1", "5.7"))
GEMINI_CALL_INTERVAL_SEC_TIER2: float = float(os.getenv("GEMINI_CALL_INTERVAL_SEC_TIER2", "8.6"))
GEMINI_CALL_INTERVAL_SEC_TIER3: float = float(os.getenv("GEMINI_CALL_INTERVAL_SEC_TIER3", "17.2"))
GEMINI_CALL_INTERVAL_SEC_TIER4: float = float(os.getenv("GEMINI_CALL_INTERVAL_SEC_TIER4", "17.2"))

# モデル名 → インターバル（秒）の対応表。
# TieredGeminiClient はこの表を参照して、現在呼び出している実モデルに応じた
# 待機時間を算出する（tier_idx ではなく model で引くのは、judge ルートのように
# resolved_model を primary に置き直す経路があるため tier_idx だけでは
# 待機時間を引き当てられないため）。
GEMINI_INTERVAL_SEC_BY_MODEL: dict[str, float] = {
    GEMINI_MODEL_TIER1: GEMINI_CALL_INTERVAL_SEC_TIER1,
    GEMINI_MODEL_TIER2: GEMINI_CALL_INTERVAL_SEC_TIER2,
    GEMINI_MODEL_TIER3: GEMINI_CALL_INTERVAL_SEC_TIER3,
    GEMINI_MODEL_TIER4: GEMINI_CALL_INTERVAL_SEC_TIER4,
}

# モデル別の RPM 上限（無料枠基準、2026-04 時点の値）。
# TieredGeminiClient._wait_for_rpm_slot が直近 60 秒の呼び出し履歴と突き合わせ、
# 上限の安全率（既定 70%）を超えそうな場合に動的に待機するために参照する。
# 静的な GEMINI_INTERVAL_SEC_BY_MODEL は「単一スレッドが連続呼び出ししても
# RPM 上限に当たらない最低間隔」を保証するが、複数経路から並行呼び出しが
# 入った場合にバーストして上限に当たることがあるため、動的レートリミッタを
# 追加で被せて二重防衛する。
GEMINI_RPM_LIMIT_BY_MODEL: dict[str, int] = {
    GEMINI_MODEL_TIER1: 15,
    GEMINI_MODEL_TIER2: 10,
    GEMINI_MODEL_TIER3: 5,
    GEMINI_MODEL_TIER4: 5,
}

# NOTE: 旧 lightweight 経路の固定モデル env var は Phase 1.5 batch E-2 で廃止された。
# garbage_filter / cluster_merge を専用モデル固定で流す経路は無料枠 RPD=20 を超過する
# 事故が発生したため、全 Gemini 呼び出しを統一 Tier 階層 (TIER1→TIER4) に統合し、
# 高 RPD の TIER1 を主軸に流すように変更している。

# ── Garbage Filter 設定（Gate 1: 高速スクリーニング） ────────────────────────
# Tier 2 Lite モデルによるノイズ除去を有効にするか（false で完全スキップ）
GARBAGE_FILTER_ENABLED: bool = os.getenv("GARBAGE_FILTER_ENABLED", "true").lower() != "false"

# ── Elite Judge 設定（Gate 3: 編集長・一点突破判定） ──────────────────────────
# evaluate_cluster_buzz (Tier 1) による最終採用判定を有効にするか
ELITE_JUDGE_ENABLED: bool = os.getenv("ELITE_JUDGE_ENABLED", "true").lower() != "false"
# Elite Judge を実行する上位候補の件数（budget 節約のため上限を設ける）
ELITE_JUDGE_CANDIDATE_LIMIT: int = int(os.getenv("ELITE_JUDGE_CANDIDATE_LIMIT", "10"))

# ── Editorial Mission Filter 設定（Pass C） ──────────────────────────────────
# Hydrangea 編集ミッション適合度（7軸: perspective_gap, geopolitical_significance,
# blindspot_severity, political_intent, hidden_power_dynamics, economic_interests,
# discussion_potential）でニュース候補をスコアリングし、生成前ゲートとして機能する。
# Step-1 prescore から LLM scoring に送る上位候補数
MISSION_PRESCORE_TOP_N: int = int(os.getenv("MISSION_PRESCORE_TOP_N", "20"))
# Step-2 LLM mission scoring を実行するか（false にすると prescore のみ使用）
MISSION_LLM_ENABLED: bool = os.getenv("MISSION_LLM_ENABLED", "true").lower() != "false"
# editorial_mission_score がこの値未満の候補は生成前にドロップ
# 暫定値 45.0（FUTURE_WORK.md の「EditorialMissionFilter 閾値の調整」を参照）
MISSION_SCORE_THRESHOLD: float = float(os.getenv("MISSION_SCORE_THRESHOLD", "45.0"))
# Editorial Mission Filter を有効にするか（false で完全スキップ、スコアはセットされない）
EDITORIAL_MISSION_FILTER_ENABLED: bool = os.getenv("EDITORIAL_MISSION_FILTER_ENABLED", "true").lower() != "false"

# ── F-13.B: JP 大手メディア Web 検証 (Gemini Grounding) ───────────────────────
# JP ソース 0 件の候補に対して Web 検索で日本の大手メディアの報道有無を確認する。
# 大手メディア報道あり → Hydrangea 取り込み漏れケースとして divergence 生成へ。
# 大手メディア報道なし → 真の blind_spot_global として動画化 (ミッション本丸)。
# 検証対象: 全国紙、通信社、大手テレビ局、主要ビジネスメディア (27 ドメイン)。
# 除外: Yahoo!ニュース、個人ブログ、SNS、タブロイド誌等。
JP_COVERAGE_VERIFIER_ENABLED: bool = os.getenv(
    "JP_COVERAGE_VERIFIER_ENABLED", "true"
).lower() == "true"
# キャッシュ有効時間 (時間)。同一 event_id への再検証を抑制する。
JP_COVERAGE_CACHE_HOURS: int = int(os.getenv("JP_COVERAGE_CACHE_HOURS", "24"))
# Grounding に使うモデル名。
JP_COVERAGE_GROUNDING_MODEL: str = os.getenv(
    "JP_COVERAGE_GROUNDING_MODEL", "gemini-2.5-flash"
)

# Groq設定 (LLM_PROVIDER=groq のとき使用)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_SCRIPT_MODEL = os.getenv("GROQ_SCRIPT_MODEL", "llama-3.3-70b-versatile")
GROQ_ARTICLE_MODEL = os.getenv("GROQ_ARTICLE_MODEL", "llama-3.3-70b-versatile")

# Ollama設定 (LLM_PROVIDER=ollama のとき使用)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_SCRIPT_MODEL = os.getenv("OLLAMA_SCRIPT_MODEL", "llama3.2")
OLLAMA_ARTICLE_MODEL = os.getenv("OLLAMA_ARTICLE_MODEL", "llama3.2")

# ── Audio / Video レンダリング設定 ────────────────────────────────────────────
# true にするとスクリプト生成後に TTS ボイスオーバーを生成する
AUDIO_RENDER_ENABLED: bool = os.getenv("AUDIO_RENDER_ENABLED", "false").lower() == "true"
# true にするとボイスオーバー生成後にレビュー用 MP4 を生成する
VIDEO_RENDER_ENABLED: bool = os.getenv("VIDEO_RENDER_ENABLED", "false").lower() == "true"
# macOS `say` コマンドで使用する日本語音声名
TTS_VOICE: str = os.getenv("TTS_VOICE", "Kyoko")
# TTS 音声サンプルレート (Hz) — say コマンド対応値: 22050, 44100
TTS_FRAMERATE: int = int(os.getenv("TTS_FRAMERATE", "22050"))
# TTS 生成タイムアウト (秒)
TTS_TIMEOUT_SEC: int = int(os.getenv("TTS_TIMEOUT_SEC", "60"))
# 動画解像度 (縦型 9:16 ショート)
VIDEO_WIDTH: int = int(os.getenv("VIDEO_WIDTH", "720"))
VIDEO_HEIGHT: int = int(os.getenv("VIDEO_HEIGHT", "1280"))
# 動画フレームレート
VIDEO_FPS: int = int(os.getenv("VIDEO_FPS", "30"))
