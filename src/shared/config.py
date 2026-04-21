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
# 1日の実行回数上限 (スケジューラ側の目安値、コードでは参照のみ)
RUNS_PER_DAY: int = int(os.getenv("RUNS_PER_DAY", "5"))

# 1日の最大公開件数 (これを超えると publish をスキップする)
MAX_PUBLISHES_PER_DAY: int = int(os.getenv("MAX_PUBLISHES_PER_DAY", "5"))

# ── 実行モード ────────────────────────────────────────────────────────────────
# publish_mode (default): daily budget を exploration / publish_reserve に分割し、
#   production ステージ (viral+judge+script+article) 用の予算を常時保護する。
# research_mode: 予算制限なしに全 LLM 呼び出しを許可（実験・デバッグ用）。
RUN_MODE: str = os.getenv("RUN_MODE", "publish_mode")

# publish_mode 時に production ステージ用として day_budget から確保する呼び出し数の最小値。
# デフォルト = 6: viral(1) + judge(up to 3) + script(1) + article(1)
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
GEMINI_JUDGE_MODEL = os.getenv("GEMINI_JUDGE_MODEL", GEMINI_MODEL_TIER2)

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

# merge_batch role: cluster post-merge LLM (lightweight model preferred)
MERGE_BATCH_PROVIDER: str = os.getenv("MERGE_BATCH_PROVIDER", LLM_PROVIDER)
MERGE_BATCH_MODEL: str = os.getenv("MERGE_BATCH_MODEL", GEMINI_CLUSTER_MODEL)

# judge role: editorial judgment (always Gemini; independent of LLM_PROVIDER)
JUDGE_PROVIDER: str = os.getenv("JUDGE_PROVIDER", "gemini")
JUDGE_MODEL: str = os.getenv("JUDGE_MODEL", GEMINI_JUDGE_MODEL)

# generation role: script + article generation (heavier capable model)
GENERATION_PROVIDER: str = os.getenv("GENERATION_PROVIDER", LLM_PROVIDER)
GENERATION_MODEL: str = os.getenv("GENERATION_MODEL", GEMINI_SCRIPT_MODEL)

# ── Gemini Judge 設定 ────────────────────────────────────────────────────────
# ジャッジを実行する上位候補の件数（LLM 呼び出し節約のため上限を設ける）
JUDGE_CANDIDATE_LIMIT: int = int(os.getenv("JUDGE_CANDIDATE_LIMIT", "3"))
# ジャッジを有効にするか（false にすると完全スキップ）
JUDGE_ENABLED: bool = os.getenv("JUDGE_ENABLED", "true").lower() != "false"

# Gemini API 呼び出し間の最小インターバル (秒) — 429 抑制のためのレート制限
GEMINI_CALL_INTERVAL_SEC: float = float(os.getenv("GEMINI_CALL_INTERVAL_SEC", "0.5"))

# ── Garbage Filter 設定（Gate 1: 高速スクリーニング） ────────────────────────
# Tier 2 Lite モデルによるノイズ除去を有効にするか（false で完全スキップ）
GARBAGE_FILTER_ENABLED: bool = os.getenv("GARBAGE_FILTER_ENABLED", "true").lower() != "false"

# ── Elite Judge 設定（Gate 3: 編集長・一点突破判定） ──────────────────────────
# evaluate_cluster_buzz (Tier 1) による最終採用判定を有効にするか
ELITE_JUDGE_ENABLED: bool = os.getenv("ELITE_JUDGE_ENABLED", "true").lower() != "false"
# Elite Judge を実行する上位候補の件数（budget 節約のため上限を設ける）
ELITE_JUDGE_CANDIDATE_LIMIT: int = int(os.getenv("ELITE_JUDGE_CANDIDATE_LIMIT", "10"))

# ── Viral Filter 設定（Pass C） ──────────────────────────────────────────────
# Step-1 prescore から LLM scoring に送る上位候補数
VIRAL_PRESCORE_TOP_N: int = int(os.getenv("VIRAL_PRESCORE_TOP_N", "20"))
# Step-2 LLM viral scoring を実行するか（false にすると prescore のみ使用）
VIRAL_LLM_ENABLED: bool = os.getenv("VIRAL_LLM_ENABLED", "true").lower() != "false"
# viral_filter_score がこの値未満の候補は生成前にドロップ
VIRAL_SCORE_THRESHOLD: float = float(os.getenv("VIRAL_SCORE_THRESHOLD", "40.0"))
# Viral Filter を有効にするか（false で完全スキップ、スコアはセットされない）
VIRAL_FILTER_ENABLED: bool = os.getenv("VIRAL_FILTER_ENABLED", "true").lower() != "false"

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
