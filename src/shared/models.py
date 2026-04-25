from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, model_validator


# ---------- 入力モデル ----------

class SourceRef(BaseModel):
    """媒体名とURLをセットで管理するソース参照。"""
    name: str                       # 媒体名（例: 日本経済新聞, Al Jazeera）
    url: str                        # 記事URL
    title: Optional[str] = None     # 記事タイトル（取得できる場合のみ）
    # ロケールメタデータ（多地域対応）— 全て省略可（後方互換）
    language: Optional[str] = None  # ISO 639-1 (ja / en / ar / zh / fr / ...)
    country: Optional[str] = None   # ISO 3166-1 alpha-2 (JP / US / QA / FR / SG / ...)
    region: Optional[str] = None    # japan / global / middle_east / europe / east_asia / global_south


class NewsEvent(BaseModel):
    id: str
    title: str
    summary: str
    category: str
    source: str
    published_at: datetime
    tags: list[str] = Field(default_factory=list)
    # 日本・海外報道比較フィールド（任意）
    japan_view: Optional[str] = None
    global_view: Optional[str] = None
    background: Optional[str] = None
    impact_on_japan: Optional[str] = None
    source_name_jp: Optional[str] = None
    source_name_global: Optional[str] = None
    source_urls: list[str] = Field(default_factory=list)
    # クラスタを構成した元記事数（event_builder が設定）
    cluster_size: Optional[int] = None
    # 構造化ソースリスト（name + url のペア）— 後方互換フィールド
    sources_jp: list[SourceRef] = Field(default_factory=list)
    sources_en: list[SourceRef] = Field(default_factory=list)
    # 多地域対応: region → SourceRef リストのマッピング
    # キー例: "japan", "global", "middle_east", "europe", "east_asia", "global_south"
    # sources_jp / sources_en は後方互換のために残すが、新コードは sources_by_locale を使う
    sources_by_locale: dict[str, list[SourceRef]] = Field(default_factory=dict)
    # 根拠メタデータ（元記事由来か LLM 推論かを記述）
    gap_reasoning: Optional[str] = None         # global_view と japan_view の差の根拠
    japan_impact_reasoning: Optional[str] = None  # impact_on_japan の根拠

    @model_validator(mode="after")
    def _derive_sources_by_locale(self) -> "NewsEvent":
        """sources_by_locale が空の場合、後方互換フィールド（sources_jp / sources_en）から導出する。

        sample_events.json など旧形式のイベントでも sources_by_locale が機能するよう、
        空の場合に限って自動補完する。既に設定済みの場合は上書きしない。

        SourceRef に region が明示されている場合はそれを使用（多地域ソースの正確な分類）。
        region が未設定の場合は sources_jp → "japan"、sources_en → "global" にフォールバック。
        """
        if not self.sources_by_locale:
            derived: dict[str, list[SourceRef]] = {}
            for s in self.sources_jp:
                r = s.region or "japan"
                if r not in derived:
                    derived[r] = []
                derived[r].append(
                    SourceRef(name=s.name, url=s.url, title=s.title,
                              language=s.language or "ja", country=s.country or "JP", region=r)
                )
            for s in self.sources_en:
                r = s.region or "global"
                if r not in derived:
                    derived[r] = []
                derived[r].append(
                    SourceRef(name=s.name, url=s.url, title=s.title,
                              language=s.language or "en", country=s.country, region=r)
                )
            if derived:
                self.sources_by_locale = derived
        return self


class GeminiJudgeResult(BaseModel):
    """Gemini 編集審判パスの構造化出力。

    Gemini は evidence に存在するソースのみを評価対象とし、
    hallucination による媒体名の捏造を防ぐ guardrail が適用される。
    judge_error が非 None の場合はジャッジ失敗（スコアはデフォルト値）。
    """
    # スコア (0-10)
    divergence_score: float = 0.0                          # JP vs 海外の報道乖離度
    blind_spot_global_score: float = 0.0                   # 日本が見落としているグローバル重要度
    indirect_japan_impact_score_judge: float = 0.0         # 日本への間接インパクト（ジャッジ評価）
    authority_signal_score: float = 0.0                    # 権威ソースの証拠強度
    # 出版可否クラス
    publishability_class: str = "insufficient_evidence"
    # linked_jp_global    — JP+海外ソース両方あり、乖離が鮮明
    # blind_spot_global   — 海外では注目、日本で未報道 + 強い間接インパクト
    # jp_only             — JP ソースのみ、海外比較不可
    # insufficient_evidence — 証拠不足
    # investigate_more    — 可能性は高いが追加調査が必要
    # ナラティブ出力
    why_this_matters_to_japan: str = ""                    # 日本にとってなぜ重要か（1文）
    strongest_perspective_gap: str = ""                    # 最も鮮明な視点差（1文）
    strongest_authority_pair: list[str] = Field(default_factory=list)  # 最大2媒体名
    # 判定フラグ
    confidence: float = 0.0                                # ジャッジの確信度 (0-1)
    requires_more_evidence: bool = True                    # 追加証拠が必要か
    hard_claims_supported: bool = False                    # 断定可能な根拠が揃っているか
    # リサーチレスキュー
    recommended_followup_queries: list[str] = Field(default_factory=list)  # 最大5件
    recommended_followup_source_types: list[str] = Field(default_factory=list)  # 最大5件
    # メタデータ
    judged_event_id: str = ""
    judged_at: str = ""
    judge_error: Optional[str] = None                      # 非 None = ジャッジ失敗
    # 失敗種別 (judge_error が非 None の場合のみ意味を持つ)
    # "quota_exhausted"       — 429 RESOURCE_EXHAUSTED
    # "temporary_unavailable" — 503 UNAVAILABLE
    # "parse_error"           — JSON 解析失敗
    # "unknown_error"         — その他
    judge_error_type: Optional[str] = None
    # Retry count for this judge call (0 = succeeded first try)
    llm_retry_count: int = 0


class ScoredEvent(BaseModel):
    event: NewsEvent
    score: float
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    # 編集方針メタデータ
    primary_tier: str = "Tier 3"
    editorial_tags: list[str] = Field(default_factory=list)
    editorial_reason: str = ""
    # Daily programming 向け: 主要バケット（scheduler が参照）
    primary_bucket: str = "general"
    # 複数タグ（排他的でない）— appraisal が設定する
    tags_multi: list[str] = Field(default_factory=list)
    # Stage B: Editorial Appraisal フィールド
    appraisal_type: Optional[str] = None          # "Perspective Inversion" | "Media Blind Spot" | "Structural Why" | "Personal Stakes"
    appraisal_hook: Optional[str] = None           # 動画冒頭3秒で使える一行
    appraisal_reason: Optional[str] = None         # なぜこの候補に切れ味があるか
    appraisal_cautions: Optional[str] = None       # どこまでが事実で、どこからが仮説か
    editorial_appraisal_score: float = 0.0         # 補助加点（上限付き tie-breaker）
    # Rolling comparison window フィールド
    story_fingerprint: str = ""                    # 16-char hex; cross-batch story identity key
    freshness_decay: float = 1.0                   # 1.0=current batch, 0.9/0.8/0.65=pool events
    from_recent_pool: bool = False                 # True if restored from recent_event_pool
    pool_created_at: Optional[str] = None          # ISO datetime; when event entered pool
    # Stage D: Gemini 編集審判パス（オプション）
    judge_result: Optional[GeminiJudgeResult] = None  # None = 未審判 or ジャッジ無効
    # Stage D2: Semantic Coherence Gate（judge 後、generation 前に適用）
    semantic_coherence_score: Optional[float] = None     # 0.0-1.0; None = 未評価
    coherence_gate_passed: Optional[bool] = None         # True/False; None = 未評価
    coherence_block_reason: Optional[str] = None         # ブロック理由（gate_passed=False の場合のみ）
    candidate_blacklist_flags: list[str] = Field(default_factory=list)  # マッチした国内ルーティンパターン
    coherence_overlap_signals: list[str] = Field(default_factory=list)  # overlap signals from coherence gate
    coherence_input_quality: dict[str, Any] = Field(default_factory=dict)  # title presence counts
    # Pass C: Viral & Interest Filter
    viral_filter_score: Optional[float] = None          # 0-100; None = not yet scored
    viral_filter_breakdown: dict[str, Any] = Field(default_factory=dict)  # sub-score details
    why_rejected_before_generation: Optional[str] = None  # set when viral filter drops candidate
    why_slot1_won_editorially: Optional[str] = None       # editorial rationale for slot-1 selection
    # ── 分析レイヤー（Phase 1: geo_lens のみ） ───────────────────────────────
    # ANALYSIS_LAYER_ENABLED=true 時のみ設定される。デフォルトは既存挙動を維持する値。
    channel_id: str = "geo_lens"
    analysis_result: Optional["AnalysisResult"] = None
    recency_guard_applied: bool = False
    recency_overlap: list[str] = Field(default_factory=list)


# ---------- 生成モデル ----------

class ScriptSection(BaseModel):
    heading: str
    body: str
    duration_sec: int


class TitleLayer(BaseModel):
    """3層タイトル + サムネイルテロップ。"""
    canonical_title: str    # 事実ベースの元タイトル
    platform_title: str     # TikTok / Shorts 用キャッチーなタイトル
    hook_line: str          # 冒頭で読み上げる一文
    thumbnail_text: str = ""  # 短いテロップ用（任意）
    title_strength: Optional[str] = None  # "strong" or "soft" — evidence 強度
    title_style: Optional[str] = None     # appraisal_type or "default"


class VideoScript(BaseModel):
    """ショート動画の台本。

    duration 系フィールドの役割:
      - total_duration_sec      : sections の duration_sec 合計（sections 非空なら必ずこれに同期）。
                                  下流 (audio_renderer / video_renderer) が TTS タイミングの基準に使う。
      - target_duration_sec     : platform プロファイルの目標秒数（shared=80, tiktok=72, shorts=78）。
                                  total とほぼ一致するはずだが、プロファイルの変更で独立して動きうる。
      - estimated_duration_sec  : 実際のテキスト文字数ベースで推定した秒数（~4.5字/秒）。
                                  total/target は「その尺で話す予定」の宣言値、estimated は「現状のテキストなら
                                  実際にはこれくらい」という実測推定値。3者の乖離は観測性のシグナル。
    """

    event_id: str
    title: str
    intro: str
    sections: list[ScriptSection]
    outro: str
    total_duration_sec: int
    target_duration_sec: int = 75
    estimated_duration_sec: Optional[int] = None
    platform_profile: str = "shared"
    title_layer: Optional["TitleLayer"] = None
    # ── ディレクター思考メタデータ（additive / optional） ─────────────
    # 既存パイプライン（render/audio/payload/article）は sections のみ消費するため、
    # 下記フィールドはログ・分析・サムネ生成など upstream 用途で参照される。
    # 旧形式の script.json とも互換（全て Optional）。
    director_thought: Optional[str] = None
    target_enemy: Optional[str] = None
    selected_pattern: Optional[str] = None
    loop_mechanism: Optional[str] = None
    seo_keywords: Optional[dict[str, Any]] = None
    thumbnail_text_variants: Optional[dict[str, str]] = None
    hook_variants: list[dict[str, str]] = Field(default_factory=list)
    peaks: Optional[dict[str, str]] = None

    @model_validator(mode="after")
    def _sync_total_duration_from_sections(self) -> "VideoScript":
        """sections が非空なら total_duration_sec を sections の合計に同期させる。

        - `_compress_sections` 等で section.duration_sec を変更したあと、呼び出し側が
          total_duration_sec の更新を忘れる drift を防ぐ。
        - sections が空（テスト fixture の VideoScript(sections=[], total_duration_sec=75) 等）
          の場合は後方互換のため既存値を維持する。
        """
        if self.sections:
            actual = sum(int(s.duration_sec) for s in self.sections)
            if self.total_duration_sec != actual:
                object.__setattr__(self, "total_duration_sec", actual)
        return self


class WebArticle(BaseModel):
    event_id: str
    title: str
    markdown: str
    word_count: int


class VideoScene(BaseModel):
    index: int
    narration: str
    visual_hint: str
    duration_sec: int
    # Visual Brief fields (映像設計書)
    scene_id: str = ""
    heading: str = ""
    visual_goal: str = ""
    visual_mode: str = ""
    video_prompt: str = ""
    negative_prompt: str = ""
    on_screen_text: str = ""
    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    source_grounding: list[str] = Field(default_factory=list)
    transition_hint: str = ""


class VideoPayload(BaseModel):
    event_id: str
    title: str
    scenes: list[VideoScene]
    total_duration_sec: int
    metadata: dict = Field(default_factory=dict)


# ---------- Daily Programming モデル ----------

class DailyScheduleEntry(BaseModel):
    """1日の番組表における1枠分のエントリ。"""
    rank_in_candidates: int           # 全候補中のスコア順位
    event_id: str
    title: str
    score: float
    primary_bucket: str               # 主要バケット（geopolitics / japan_abroad など）
    editorial_tags: list[str] = Field(default_factory=list)
    tags_multi: list[str] = Field(default_factory=list)
    selection_reason: str = ""        # 採用理由
    rejection_reason: Optional[str] = None  # 非採用理由（rejected / held_back のみ）
    published: bool = False
    published_at: Optional[str] = None  # ISO datetime string
    # スロット状態: "selected"（未配信）| "published"（配信済み）| "held_back"（品質floor未達）
    slot_status: str = "selected"
    # Stage B Appraisal フィールド（透明性のために保存）
    appraisal_type: Optional[str] = None
    appraisal_hook: Optional[str] = None
    appraisal_reason: Optional[str] = None
    appraisal_cautions: Optional[str] = None
    editorial_appraisal_score: float = 0.0
    # Snapshot for reconstruction when event is not in a later batch's all_ranked.
    # Stores the full serialized ScoredEvent so generation can proceed without
    # re-ingesting the original batch.
    event_snapshot: Optional[dict] = None
    # 透明性: どの地域ソース由来かを追跡
    source_regions: list[str] = Field(default_factory=list)
    source_languages: list[str] = Field(default_factory=list)
    # Region-aware 多地域説明（scoring が設定）
    why_this_region_mix: Optional[str] = None
    regional_contrast_reason: Optional[str] = None
    # Rolling comparison window 透明性
    story_fingerprint: str = ""                    # 16-char hex; cross-batch dedup key
    freshness_decay: float = 1.0                   # 採用時の freshness 係数
    from_recent_pool: bool = False                 # True = 過去 batch のプール由来
    pool_created_at: Optional[str] = None          # プール登録時刻 (ISO)


class DailySchedule(BaseModel):
    """1日の番組表（最大5枠）。daily_schedule.json に保存される。"""
    date: str                                  # YYYY-MM-DD
    generated_at: str                          # ISO datetime
    total_candidates: int
    selected: list[DailyScheduleEntry]         # 採用（quality floor 通過、最大5枠）
    rejected: list[DailyScheduleEntry]         # 多様性制約で非採用（上位10件のみ保存）
    held_back: list[DailyScheduleEntry] = Field(default_factory=list)  # quality floor 未達（最大10件）
    open_slots: int = 0                        # quality 候補不足で埋まらなかった枠数
    diversity_rules_applied: list[str]         # 適用された多様性ルール
    coverage_summary: dict[str, int]           # primary_bucket → 採用件数
    region_coverage: dict[str, int] = Field(default_factory=dict)  # region → 採用件数（透明性）


# ---------- ストレージモデル ----------

class JobRecord(BaseModel):
    id: str
    event_id: str
    status: str  # "completed" | "failed"
    script_path: Optional[str] = None
    article_path: Optional[str] = None
    video_payload_path: Optional[str] = None
    voiceover_path: Optional[str] = None
    review_mp4_path: Optional[str] = None
    # tz-aware で生成する。datetime.utcnow は Python 3.12 で deprecation 警告。
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None


# ---------- 分析レイヤー（Phase 1: geo_lens 単独稼働） ----------

class ChannelConfig(BaseModel):
    """チャンネル単位の設定。Phase 1 は geo_lens のみ enabled。

    configs/channels.yaml から `ChannelConfig.load(channel_id)` でロードする。
    """

    channel_id: str
    display_name: str
    enabled: bool
    source_regions: list[str] = Field(default_factory=list)
    perspective_axes: list[str] = Field(default_factory=list)
    duration_profiles: list[str] = Field(default_factory=list)
    prompt_variant: str
    posts_per_day: int = 0
    schedule_cron: Optional[str] = None
    voice_id: Optional[str] = None
    visual_style: Optional[str] = None

    @classmethod
    def load(cls, channel_id: str, config_path: Optional[Path] = None) -> "ChannelConfig":
        """configs/channels.yaml から該当チャンネル設定をロードする。"""
        if config_path is None:
            config_path = Path(__file__).resolve().parents[2] / "configs" / "channels.yaml"
        with open(config_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        for entry in data.get("channels", []):
            if entry.get("channel_id") == channel_id:
                return cls(**entry)
        raise ValueError(f"channel_id={channel_id!r} not found in {config_path}")

    @classmethod
    def load_all(cls, config_path: Optional[Path] = None) -> list["ChannelConfig"]:
        """全チャンネル設定をリストで返す。"""
        if config_path is None:
            config_path = Path(__file__).resolve().parents[2] / "configs" / "channels.yaml"
        with open(config_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return [cls(**entry) for entry in data.get("channels", [])]


class PerspectiveCandidate(BaseModel):
    """4軸（silence_gap / framing_inversion / hidden_stakes / cultural_blindspot）の観点候補。"""

    axis: str
    score: float
    reasoning: str
    evidence_refs: list[str] = Field(default_factory=list)


class MultiAngleAnalysis(BaseModel):
    """5観点（地政学・政治意図・経済影響・文化文脈・報道差異）の構造化分析。"""

    geopolitical: Optional[str] = None
    political_intent: Optional[str] = None
    economic_impact: Optional[str] = None
    cultural_context: Optional[str] = None
    media_divergence: Optional[str] = None


class Insight(BaseModel):
    """視聴者が「人に話したくなる核心情報」の単位。"""

    text: str
    importance: float
    evidence_refs: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """分析レイヤーの最終出力。{event_id}_analysis.json として保存される。"""

    event_id: str
    channel_id: str
    selected_perspective: PerspectiveCandidate
    rejected_perspectives: list[PerspectiveCandidate] = Field(default_factory=list)
    perspective_verified: bool
    verification_notes: str = ""
    multi_angle: MultiAngleAnalysis
    insights: list[Insight] = Field(default_factory=list)
    selected_duration_profile: str
    expanded_sources: list[str] = Field(default_factory=list)
    visual_mood_tags: list[str] = Field(default_factory=list)
    analysis_version: str = "v1.0"
    generated_at: str
    llm_calls_used: int = 0


class RecencyRecord(BaseModel):
    """投稿成功時に保存される primary_entities/topics の記録。

    Recency Guard が直近 24h 内の重複を判定するために使う。
    """

    event_id: str
    channel_id: str
    primary_entities: list[str] = Field(default_factory=list)
    primary_topics: list[str] = Field(default_factory=list)
    published_at: str  # ISO 8601


# ScoredEvent.analysis_result の forward ref を解決
ScoredEvent.model_rebuild()
