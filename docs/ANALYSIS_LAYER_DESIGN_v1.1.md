# ANALYSIS_LAYER_DESIGN.md — 分析レイヤー設計書

> Hydrangea News PoC に「ニュース選定後の深掘り分析」を行う新規レイヤーを追加するための設計書。
> 作成日: 2026-04-25 / バージョン: v1.0 (Draft)

---

## 目次

0. [用語の約束](#0-用語の約束)
1. [背景と問題意識](#1-背景と問題意識)
2. [設計原則](#2-設計原則)
3. [新規データモデル](#3-新規データモデル)
4. [パイプラインフロー](#4-パイプラインフロー)
5. [観点4軸の定義](#5-観点4軸の定義)
6. [動的尺プロファイル6種](#6-動的尺プロファイル6種)
7. [多角的分析の5観点](#7-多角的分析の5観点)
8. [洞察抽出のフォーマット](#8-洞察抽出のフォーマット)
9. [Recency Guard 仕様](#9-recency-guard-仕様)
10. [LLM呼び出し設計](#10-llm呼び出し設計)
11. [既存コードへの変更点](#11-既存コードへの変更点)
12. [品質ルーブリック](#12-品質ルーブリック)
13. [テスト戦略](#13-テスト戦略)
14. [段階的ロールアウト計画](#14-段階的ロールアウト計画)
15. [音声・画像AIとの将来連携ポイント](#15-音声画像aiとの将来連携ポイント)
16. [付録A: Claude Code 実装指示書](#16-付録a-claude-code-実装指示書)

---

## 0. 用語の約束

このドキュメントで使う専門用語の意味を最初にまとめておく。

| 用語 | 意味 |
|---|---|
| **分析レイヤー** | 本ドキュメントで設計する新規レイヤー。既存パイプラインの「採用候補確定後」「台本生成前」に挿入する深掘り分析工程 |
| **観点** | ニュースを動画化する際の「切り口」。例: Silence Gap / Framing Inversion など |
| **観点軸** | 観点の種類のこと。本設計では4軸（Silence Gap / Framing Inversion / Hidden Stakes / Cultural Blindspot）|
| **insights** | 分析レイヤーが台本生成に渡す「視聴者が賢くなったと感じる核心情報」3〜5個 |
| **動的尺** | 動画の長さ（duration）を内容に応じて変える仕組み。60s/80s/90s/100s/120s等 |
| **ナラティブパターン** | 動画のストーリー構造の型。例: breaking_shock / geopolitics / cultural_divide など |
| **チャンネル** | 投稿先アカウントの単位。Phase 1 は geo_lens のみ、Phase 2/3 で japan_athletes / k_pulse 追加 |
| **Recency Guard** | 直近24h以内に投稿した話題を次回の選定で降格させる仕組み |
| **Elite Judge** | 既存の編集長役LLM判定（src/llm/judge.py）。採用判定（is_adopted）を行う |
| **Gemini Judge** | 既存の publishability_class 判定（src/triage/gemini_judge.py）|
| **ScoredEvent** | 既存のPydanticモデル。スコアリング後のニュースイベント |
| **ChannelConfig** | 本設計で新規追加するチャンネル設定モデル |
| **AnalysisResult** | 本設計で新規追加する分析結果モデル |

---

## 1. 背景と問題意識

### 1.1 現状システムの完成度

Hydrangea News PoC は約 **90% 完成のMVP**。RSS取得 → 日英クラスタリング → スコアリング → 編集判定 → 台本生成 → 動画組立、まで一気通貫で動いている。LLMは4階層フォールバック、SQLite永続化、recent_event_pool（48h窓）、予算管理まで実装済み。

### 1.2 顕在化した品質問題

2026-04-24に実行された台本（`cls-a83e0f0a56a5_script.json`、ホルムズ海峡ネタ）の品質に対するカズヤの評価：

> 「全然イケてない、理想とは程遠い」

具体的な問題：
- **Hookが弱い**（「NHKが言わない真実」のような抽象煽り）
- **事実誤認**（「日本メディアが沈黙」と書いたが実際は連日報道されていた）
- **地政学解説が浅い**（常套句だけで中身ゼロ）
- **日本語が不自然**（SEOキーワード機械埋め込み）
- **誇張表現**（「完全に人質に取られました」など扇動的）
- **ループ機構失敗**（宣言だけで成立してない）

### 1.3 根本原因

**「LLMに少量情報から創造させる」構造になっており、これがLLMの不得意領域に当たっている。**

現状、台本生成LLMが見られる情報：
- title / summary / japan_view / global_view（各300〜400字）
- gap_reasoning / impact_on_japan / background（多くがNone）
- score_breakdown の数値羅列のみ

致命的に不足しているもの：
- 同一事象のフル原稿（タイトルとサマリのみ取得、本文未取得）
- 地政学・歴史・経済の構造化文脈
- 「なぜこの差が生まれるか」の仮説候補

カズヤの正しい指摘：
> 「LLMは大量情報を渡されて咀嚼するのが得意で、少量情報から創造するのは苦手。現状システムは後者で破綻してる。」

加えて、`script_writer.py` の「武器庫6パターン」「Hook 5類型」「target_enemy」が**扇動型バズ最適化に偏っており**、Hydrangeaのブランド（ReHacQ・東洋経済レベルの知性）と矛盾している。

### 1.4 解決の方向性

**「採用候補が確定してから、その候補について世界中の関連報道を集めて多角的に分析し、その分析結果を素材として台本を書かせる」**ように構造を変える。

つまり「**一撃で台本生成**」を否定し、「**分析 → 台本生成**」の2段構造にする。

---

## 2. 設計原則

### 2.1 既存パイプラインを破壊しない

- 新機能はフィーチャーフラグ `ANALYSIS_LAYER_ENABLED` でON/OFF切替
- OFF時は既存パイプラインがそのまま動く
- 既存の `audio_renderer.py` / `video_renderer.py` には触らない

### 2.2 Evidence-Grounded（証拠ベース）

- LLMに「事実を創造させない」
- LLMには「集めた一次ソースから構造を抽出させる」
- 「事実 = 一次ソース」「文脈・意味づけ = LLMの知識＋分析」を明確に分離

### 2.3 Channel 抽象化

- ChannelConfig という設定オブジェクトを導入
- Phase 1 は geo_lens のみ enabled
- Phase 2/3 で japan_athletes / k_pulse を `configs/channels.yaml` に追加するだけで対応可能な構造

### 2.4 量より質

- 1日3回×1本=3投稿（既存のTop-3ループは廃止）
- 各動画がジャーナリズム作品としての品質を持つ
- 扇動ではなく情報密度で勝負

### 2.5 段階性の尊重

- Phase 1 は分析レイヤー実装と分析品質確立のみ
- 音声・画像・動画AIへの拡張は手動PoC後に別Phase
- 設計時点で将来連携を意識するが、Phase 1 では実装しない

### 2.6 LLM抽象化

- Phase 1 は Gemini で実装
- 既存の `LLMClient` 抽象クラス（`src/llm/base.py`）を活用
- 将来 Claude API 等への切替は config 1行変更で済む構造

---

## 3. 新規データモデル

### 3.1 ChannelConfig（新規）

チャンネル単位の設定を保持するモデル。`configs/channels.yaml` から読み込む。

```python
# src/shared/models.py に追加

from pydantic import BaseModel
from typing import Optional

class ChannelConfig(BaseModel):
    """チャンネル単位の設定。Phase 1 は geo_lens のみenabled。"""
    
    channel_id: str  # "geo_lens" | "japan_athletes" | "k_pulse"
    display_name: str
    enabled: bool
    
    # ソース設定
    source_regions: list[str]
    # 例: ["global", "middle_east", "europe", "east_asia", "global_south"]
    
    # 観点設定（このチャンネルで使う観点軸）
    perspective_axes: list[str]
    # 例: ["silence_gap", "framing_inversion", "hidden_stakes", "cultural_blindspot"]
    
    # 動画尺プロファイル
    duration_profiles: list[str]
    # 例: ["geopolitics_120s", "breaking_shock_60s", "paradigm_shift_100s", ...]
    
    # LLM プロンプトのバリアント名
    prompt_variant: str  # "geo_lens_v1"
    
    # 投稿スケジュール
    posts_per_day: int  # 3
    schedule_cron: Optional[str] = None  # "0 0,8,16 * * *"
    
    # 将来の音声設定（Phase 2以降で活用）
    voice_id: Optional[str] = None  # ElevenLabs Voice ID
    
    # 将来のビジュアル設定（Phase 2以降で活用）
    visual_style: Optional[str] = None  # "dark_cinematic" 等
```

### 3.2 AnalysisResult（新規）

分析レイヤーの出力結果を保持するモデル。

```python
# src/shared/models.py に追加

class PerspectiveCandidate(BaseModel):
    """観点候補（候補×観点のペア）"""
    axis: str  # "silence_gap" | "framing_inversion" | "hidden_stakes" | "cultural_blindspot"
    score: float  # 0.0〜10.0
    reasoning: str  # なぜこの観点が成立するか
    evidence_refs: list[str]  # 根拠となる article_id のリスト

class MultiAngleAnalysis(BaseModel):
    """多角的分析の結果（5観点）"""
    geopolitical: Optional[str] = None  # 地政学的分析
    political_intent: Optional[str] = None  # 政治的意図の分析
    economic_impact: Optional[str] = None  # 経済的影響（特に日本への影響）
    cultural_context: Optional[str] = None  # 文化的文脈
    media_divergence: Optional[str] = None  # 報道差異の分析

class Insight(BaseModel):
    """洞察（視聴者が賢くなる核心情報）"""
    text: str  # 洞察本文
    importance: float  # 0.0〜1.0
    evidence_refs: list[str]  # 根拠の article_id

class AnalysisResult(BaseModel):
    """分析レイヤーの最終出力。台本生成への入力となる。"""
    
    event_id: str  # 元のScoredEventのID
    channel_id: str
    
    # 観点関連
    selected_perspective: PerspectiveCandidate  # 採用された観点
    rejected_perspectives: list[PerspectiveCandidate] = []  # 不成立だった観点
    
    # 検証関連
    perspective_verified: bool  # 観点が成立したか
    verification_notes: str  # 検証時のメモ（例: 「日本でも実は連日報道」）
    
    # 多角的分析
    multi_angle: MultiAngleAnalysis
    
    # 洞察
    insights: list[Insight]  # 3〜5個
    
    # 動画尺プロファイル
    selected_duration_profile: str  # "geopolitics_120s" 等
    
    # 拡張ソース
    expanded_sources: list[str] = []  # 追加収集した article_id
    
    # メタ情報
    analysis_version: str = "v1.0"
    generated_at: str  # ISO8601
    llm_calls_used: int  # この分析で使ったLLM呼び出し回数
```

### 3.3 ScoredEvent の拡張

```python
# 既存の ScoredEvent (src/shared/models.py) にフィールド追加

class ScoredEvent(BaseModel):
    # ... 既存フィールド省略 ...
    
    # ★追加
    channel_id: str = "geo_lens"  # デフォルトgeo_lens、後方互換性確保
    analysis_result: Optional[AnalysisResult] = None  # 分析レイヤー実行後に設定
```

### 3.4 RecencyRecord（新規）

Recency Guard 用の記録モデル。

```python
# src/shared/models.py に追加

class RecencyRecord(BaseModel):
    """直近投稿の記録。Recency Guard で使用。"""
    
    event_id: str
    channel_id: str
    primary_entities: list[str]  # 例: ["Trump", "USA", "tariff"]
    primary_topics: list[str]  # 例: ["trade_war", "us_politics"]
    published_at: str  # ISO8601
```

---

## 4. パイプラインフロー

### 4.1 既存パイプラインへの挿入位置

```
[既存パイプライン]
RSS取得
  ↓
正規化
  ↓
クラスタリング
  ↓
スコアリング
  ↓
Editorial Appraisal
  ↓
recent_event_pool 結合
  ↓
Viral Filter
  ↓
Elite Judge（採用判定 = is_adopted）
  ↓
Final Selection（slot-1 確定）
  ↓
[★ここに分析レイヤー挿入 ★]
  ↓
Gemini Judge
  ↓
Coherence Gate
  ↓
台本生成（既存改修）
  ↓
記事/タイトル/動画ペイロード生成
  ↓
音声・動画生成
```

### 4.2 分析レイヤー内部のフロー

```
[入力: ScoredEvent (slot-1)]
  ↓
Step 0: Recency Guard 適用
  - 直近24h投稿の primary_entity と照合
  - 重複ありなら -50% 降格、次点候補に切替
  ↓
Step 1: 観点候補のルールベース抽出
  - 既存スコアから4軸（Silence Gap / Framing Inversion / Hidden Stakes / Cultural Blindspot）の
    成立可能性を機械的に判定
  - 各軸について score (0-10) と reasoning を生成
  ↓
Step 2: ソース拡充
  - 採用候補のキーワードで recent_event_pool を再スキャン
  - 同一事象の関連記事を追加収集（最大10件）
  - LLMの知識による背景補完用プロンプトを準備
  ↓
Step 3: LLMで観点最終選定
  - 候補×観点ペア3つを評価、ベスト1つを選定
  - 選ばれた観点の検証（perspective_verified）
  - 不成立なら次点候補へフォールバック
  ↓
Step 4: 多角的分析
  - 選ばれた観点を中心に、以下5観点でLLM分析:
    1. 地政学的分析
    2. 政治的意図の分析
    3. 経済的影響（特に日本）
    4. 文化的文脈
    5. 報道差異の分析
  - 各分析は3〜5文の構造化テキスト
  ↓
Step 5: 洞察抽出
  - 多角的分析から「視聴者が賢くなる核心情報」3〜5個を抽出
  - 各洞察に importance スコアと evidence_refs を紐付け
  ↓
Step 6: 動画尺プロファイル選定
  - 選ばれた観点・洞察の量から最適なナラティブパターンを決定
  - 例: 緊急性高 → breaking_shock_60s、深堀り系 → geopolitics_120s
  ↓
[出力: AnalysisResult]
  ↓
ScoredEvent.analysis_result にセット
  ↓
{event_id}_analysis.json として保存
  ↓
Gemini Judge へ
```

### 4.3 フォールバック構造

各Stepで失敗した場合の挙動：

| Step | 失敗時の挙動 |
|---|---|
| Step 0 | Recency重複で全候補降格 → 候補なしで実行スキップ（投稿しない）|
| Step 1 | ルール判定で観点軸が0個 → 既存パイプライン（分析レイヤー無効）にフォールバック |
| Step 2 | ソース拡充失敗 → 既存clusterのみで続行 |
| Step 3 | LLM観点選定失敗 → スコア最高軸を機械的に採用 |
| Step 4 | LLM分析失敗 → 最低限の `geopolitical` のみ生成、他はNone |
| Step 5 | 洞察抽出失敗 → multi_angle のテキストをそのまま insights として使用 |
| Step 6 | プロファイル選定失敗 → デフォルト `geopolitics_120s` を使用 |

---

## 5. 観点4軸の定義

### 5.1 全体方針

「**日本の視聴者が見て、賢くなった気分になり、人にシェアしたくなる切り口**」を観点として定義する。扇動・陰謀論ではなく、知的体験を提供する軸。

### 5.2 4軸の詳細

#### 軸1: Silence Gap（沈黙ギャップ）

**意味**: 海外で大ニュース、日本では報道ゼロ or 極小

**成立条件**:
- `sources_en >= 3` AND `sources_jp == 0` （絶対条件）
- `global_attention_score >= 6.0`
- `indirect_japan_impact_score >= 4.0`

**スコア計算**:
```
score = (sources_en数 * 1.5) + global_attention_score - (sources_jp数 * 5.0) + indirect_japan_impact_score
clamp(0.0, 10.0)
```

**採用理由（視聴者目線）**:
「えっ、これ日本では報道されてないの？」という驚き → シェア動機

**台本生成への入力**:
- 「日本主要紙では言及ゼロ、対して海外ではN紙が一斉に報道」という事実構造
- なぜ日本で報道されないかの仮説（メディア構造的問題、地政学的タブー等）

---

#### 軸2: Framing Inversion（フレーミング逆転）

**意味**: 日本と海外で「誰が悪者か」「何が原因か」が真逆に報じられている

**成立条件**:
- `sources_jp >= 1` AND `sources_en >= 2` （絶対条件）
- `perspective_gap_score >= 6.0`
- JP記事と海外記事で「主体（誰が）」「述語（何をした）」が異なる

**スコア計算**:
```
score = perspective_gap_score + (sources_en数 * 0.5) + framing_divergence_bonus
clamp(0.0, 10.0)

framing_divergence_bonus = LLM判定で「主体・述語が異なる」と認定された場合 +2.0
```

**採用理由（視聴者目線）**:
「自分が信じてた構図が逆だった」 → 世界観アップデート → 完了率向上

**台本生成への入力**:
- 日本での報じられ方 vs 海外での報じられ方の対比
- なぜこの差が生じるかの構造分析

---

#### 軸3: Hidden Stakes（隠れた利害関係）

**意味**: 日本の生活・経済に直結するが、報道で繋げられていない

**成立条件**:
- `indirect_japan_impact_score >= 5.0`
- 日本企業/業界キーワードがLLM分析で抽出される
- 既存の日本報道で「日本への影響」が言及されていない

**スコア計算**:
```
score = indirect_japan_impact_score + japan_industry_keyword_count + (impact_unmentioned_bonus)
clamp(0.0, 10.0)

impact_unmentioned_bonus = 既存JP記事に日本影響への言及がなければ +2.0
```

**採用理由（視聴者目線**:
「自分の生活に関係あるのか」 → 視聴維持率向上

**台本生成への入力**:
- 海外で起きた事象 → 日本企業/産業への因果連鎖
- 「あなたの〇〇に影響します」という具体的接続

---

#### 軸4: Cultural Blindspot（文化的盲点）

**意味**: 日本の常識では理解できない海外の論理

**成立条件**:
- 海外の社会・文化・制度に関する記事
- 日本の常識との対比が成立する文化軸を持つ
- LLM判定で「日本人読者にとって直感的に理解しづらい論理」と認定

**スコア計算**:
```
score = cultural_uniqueness_score + LLM判定の「日本人視点での違和感度」
clamp(0.0, 10.0)
```

**採用理由（視聴者目線）**:
「他国の論理を知る知的興奮」 → 知的優越感 → ブランド共感

**台本生成への入力**:
- 海外の論理の構造説明
- 日本の常識との対比軸
- 「だから何が起きるか」の予測

### 5.3 観点軸の選択ロジック

```python
def select_perspective(scored_event: ScoredEvent) -> PerspectiveCandidate:
    """
    Step 1: 4軸それぞれのスコアを計算
    Step 2: 成立条件を満たす軸だけ候補に残す
    Step 3: スコア降順でTop3を抽出
    Step 4: LLMに「この候補×観点ペアの中で、台本として最も
            "視聴者が賢くなる体験"を提供できるのはどれか？」を判定させる
    Step 5: 選ばれた観点の verification を実行
    """
    candidates = []
    for axis in ["silence_gap", "framing_inversion", "hidden_stakes", "cultural_blindspot"]:
        score, reasoning = calculate_axis_score(scored_event, axis)
        if meets_axis_conditions(scored_event, axis):
            candidates.append(PerspectiveCandidate(
                axis=axis, score=score, reasoning=reasoning,
                evidence_refs=collect_evidence(scored_event, axis)
            ))
    
    if not candidates:
        return None  # 4軸すべて不成立 → フォールバック発動
    
    top3 = sorted(candidates, key=lambda c: c.score, reverse=True)[:3]
    selected = llm_select_best_perspective(scored_event, top3)
    verified = verify_perspective(scored_event, selected)
    
    if not verified.success:
        # 次点候補で再試行
        for next_candidate in top3[1:]:
            verified = verify_perspective(scored_event, next_candidate)
            if verified.success:
                return next_candidate
        return None  # 全候補で不成立 → 投稿スキップ
    
    return selected
```

---

## 6. 動的尺プロファイル6種

### 6.1 全体方針

ナラティブパターン別に動画の尺を最適化する。短い尺は強い結論で締め、長い尺は構造的解説で展開する。

### 6.2 6プロファイル

| プロファイルID | 尺 | ナラティブ | 適合観点 | 構造 |
|---|---|---|---|---|
| `breaking_shock_60s` | 60秒 | 速報衝撃型 | Silence Gap / Framing Inversion | Hook(3s) + Setup(12s) + Twist(30s) + Punchline(15s) |
| `media_critique_80s` | 80秒 | メディア批判型 | Framing Inversion / Silence Gap | Hook(4s) + Setup(16s) + Twist(40s) + Punchline(20s) |
| `anti_sontaku_90s` | 90秒 | 忖度暴露型 | Hidden Stakes / Silence Gap | Hook(4s) + Setup(18s) + Twist(45s) + Punchline(23s) |
| `paradigm_shift_100s` | 100秒 | パラダイム転換型 | Cultural Blindspot / Framing Inversion | Hook(5s) + Setup(20s) + Twist(50s) + Punchline(25s) |
| `cultural_divide_100s` | 100秒 | 文化対比型 | Cultural Blindspot | Hook(5s) + Setup(20s) + Twist(50s) + Punchline(25s) |
| `geopolitics_120s` | 120秒 | 地政学解説型 | Hidden Stakes / Silence Gap | Hook(6s) + Setup(24s) + Twist(60s) + Punchline(30s) |

### 6.3 プロファイル選定ロジック

```python
def select_duration_profile(
    perspective: PerspectiveCandidate,
    insights_count: int,
    multi_angle: MultiAngleAnalysis
) -> str:
    """
    観点軸 × 洞察の量 × 分析の深さ から最適プロファイルを選定
    """
    axis = perspective.axis
    
    # 緊急性の高い Silence Gap 系 → 短尺で強く
    if axis == "silence_gap" and is_breaking_news(perspective):
        return "breaking_shock_60s"
    
    # 比較構造が強い Framing Inversion → メディア批判型
    if axis == "framing_inversion":
        return "media_critique_80s"
    
    # 利害が複雑な Hidden Stakes → 地政学解説型
    if axis == "hidden_stakes" and multi_angle.geopolitical:
        return "geopolitics_120s"
    
    # 文化軸 → 文化対比型 or パラダイム転換型
    if axis == "cultural_blindspot":
        if insights_count >= 4:
            return "paradigm_shift_100s"
        return "cultural_divide_100s"
    
    # デフォルト
    return "anti_sontaku_90s"
```

### 6.4 文字数試算と音声コスト

| プロファイル | 推定文字数（日本語）| ElevenLabs消費 |
|---|---|---|
| breaking_shock_60s | 約270字 | 270字 |
| media_critique_80s | 約360字 | 360字 |
| anti_sontaku_90s | 約405字 | 405字 |
| paradigm_shift_100s | 約450字 | 450字 |
| cultural_divide_100s | 約450字 | 450字 |
| geopolitics_120s | 約540字 | 540字 |

**1日3本×30日=90本/月の試算**:
- 全部が `geopolitics_120s` の場合: 約48,600字/月
- ElevenLabs Creator プラン（$22/月、100,000字）で**十分余裕あり**

→ Phase 1 では尺の上限を120秒に維持。コスト視点での制約は不要。

---

## 7. 多角的分析の5観点

### 7.1 全体方針

選ばれた候補×観点について、以下5観点で構造化分析を行う。各観点は3〜5文の文章として生成。

### 7.2 5観点の詳細

#### 観点A: 地政学的分析（geopolitical）

**何を分析するか**:
- 国家間の力学
- 地理的・歴史的文脈
- 過去の類似事例

**プロンプト方針**:
> 「この事象を地政学的に解釈すると、どのような国家間の力学が背景にあるか？過去の類似事例（具体的な歴史的出来事）と比較し、構造的な共通点を3〜5文で説明せよ。」

#### 観点B: 政治的意図の分析（political_intent）

**何を分析するか**:
- 各当事者の政治的動機
- 国内政治・選挙との関連
- 「誰が得をするか」の構造

**プロンプト方針**:
> 「この事象における主要当事者の政治的動機を、それぞれの国内政治状況（選挙・支持率・既得権益）と関連付けて分析せよ。誰が得をし、誰が損をするか、具体的な利害構造を3〜5文で説明せよ。」

#### 観点C: 経済的影響（economic_impact）

**何を分析するか**:
- マクロ経済への影響
- 特定産業への影響
- **特に日本企業・日本経済への影響**（重要）

**プロンプト方針**:
> 「この事象が経済に与える影響を分析せよ。特に日本企業・日本経済への影響について、具体的な業界・企業名を挙げ、因果連鎖を明確にして3〜5文で説明せよ。」

#### 観点D: 文化的文脈（cultural_context）

**何を分析するか**:
- 当事国の文化的・社会的背景
- 日本の常識との差異
- 価値観・倫理観の違い

**プロンプト方針**:
> 「この事象の背景にある当事国の文化的・社会的文脈を、日本の常識との差異を明示しながら3〜5文で説明せよ。価値観や倫理観の違いに焦点を当てよ。」

#### 観点E: 報道差異の分析（media_divergence）

**何を分析するか**:
- 各国メディアの報じ方の違い
- 強調する要素の差
- 「何が報じられて、何が報じられないか」

**プロンプト方針**:
> 「この事象に関する各国メディアの報じ方を比較せよ。日本メディア / 西側メディア / グローバルサウスメディア で何が強調され、何が省略されているかを3〜5文で分析せよ。」

### 7.3 LLM呼び出し戦略

5観点を**1回のLLM呼び出しで全部生成**する（コスト最適化）。

```python
def perform_multi_angle_analysis(
    scored_event: ScoredEvent,
    perspective: PerspectiveCandidate,
    expanded_sources: list[Article]
) -> MultiAngleAnalysis:
    prompt = build_multi_angle_prompt(
        event=scored_event,
        perspective=perspective,
        sources=expanded_sources
    )
    # 1回のLLM呼び出しで5観点すべて生成
    result = llm_client.generate(prompt, schema=MultiAngleAnalysis)
    return result
```

---

## 8. 洞察抽出のフォーマット

### 8.1 洞察の定義

「**視聴者がこの動画を見終わった後、人に話したくなる核心情報**」を3〜5個抽出する。

### 8.2 洞察の例

ホルムズ海峡ネタの場合（仮想例）：

```json
{
  "insights": [
    {
      "text": "世界の原油の20%が通る海峡を、人口9000万人のイランが事実上の通行権を握っている。これは2025年のOPEC+調整能力の崩壊と直結している。",
      "importance": 0.95,
      "evidence_refs": ["art_001", "art_003"]
    },
    {
      "text": "日本の原油輸入の80%超がホルムズ海峡経由。この事実をTwitter/X上で日本語で言及した報道機関は過去30日間で2社のみ。",
      "importance": 0.9,
      "evidence_refs": ["art_007"]
    },
    {
      "text": "イランは2019年にも同様の威嚇を行ったが、実際の封鎖は行わなかった。それは『封鎖した瞬間に中国の反対側からの圧力で潰される』という地政学的拘束による。",
      "importance": 0.85,
      "evidence_refs": ["art_002", "art_005"]
    }
  ]
}
```

### 8.3 洞察生成のプロンプト

```
あなたは知的好奇心の高い視聴者向けの優秀な編集者です。

以下の多角的分析を読み、視聴者が「人に話したくなる核心情報」を3〜5個抽出してください。

【条件】
- 各洞察は1〜2文の自己完結した断片
- 数字・固有名詞・因果関係のいずれかを含む
- importance（0.0〜1.0）と evidence_refs を付与
- 一般論・常套句は除外
- 視聴者の世界観をアップデートする要素を優先

【入力】
{multi_angle_analysis}

【出力形式】
{json_schema}
```

### 8.4 台本生成への接続

`script_writer.py` の改修時に、`insights` を入力として受け取り、4ブロック構造（Hook/Setup/Twist/Punchline）に配分する：

- Hook: 最も importance の高い洞察を変形
- Setup: 文脈となる洞察を要約
- Twist: 因果連鎖を含む洞察を展開
- Punchline: パンチライン性の強い洞察で締める

---

## 9. Recency Guard 仕様

### 9.1 目的

「**1日3回トランプ問題**」の回避。同日内に同じ人物・トピックを連続投稿することを防ぐ。

### 9.2 アルゴリズム

```python
def apply_recency_guard(
    candidates: list[ScoredEvent],
    channel_id: str,
    db: Database
) -> list[ScoredEvent]:
    """
    直近24h以内に投稿した primary_entity / primary_topic と重複する候補を
    -50%降格させる。
    """
    recent_records = db.get_recency_records(
        channel_id=channel_id,
        within_hours=24
    )
    
    recent_entities = set()
    recent_topics = set()
    for record in recent_records:
        recent_entities.update(record.primary_entities)
        recent_topics.update(record.primary_topics)
    
    for candidate in candidates:
        candidate_entities = extract_primary_entities(candidate)
        candidate_topics = extract_primary_topics(candidate)
        
        entity_overlap = recent_entities & set(candidate_entities)
        topic_overlap = recent_topics & set(candidate_topics)
        
        if entity_overlap or topic_overlap:
            # スコア-50%降格
            candidate.total_score *= 0.5
            candidate.recency_guard_applied = True
            candidate.recency_overlap = list(entity_overlap | topic_overlap)
    
    # 降格適用後にスコア順で再ソート
    return sorted(candidates, key=lambda c: c.total_score, reverse=True)
```

### 9.3 primary_entity / primary_topic の抽出方法

```python
def extract_primary_entities(event: ScoredEvent) -> list[str]:
    """
    既存のscoring結果から主要エンティティを抽出。
    例: ["Trump", "USA", "tariff"]
    """
    # 既存のappraisalフィールドや keyword_match からN個抽出
    # LLM呼び出しは行わない（軽量に）
    ...

def extract_primary_topics(event: ScoredEvent) -> list[str]:
    """
    主要トピックを抽出。
    例: ["trade_war", "us_politics", "global_economy"]
    """
    # 既存のcategoryやキーワードクラスタから抽出
    ...
```

### 9.4 投稿成功時の記録

```python
def record_publication(
    event: ScoredEvent,
    channel_id: str,
    db: Database
):
    """投稿が成功した時にRecencyRecordを保存。"""
    record = RecencyRecord(
        event_id=event.event_id,
        channel_id=channel_id,
        primary_entities=extract_primary_entities(event),
        primary_topics=extract_primary_topics(event),
        published_at=datetime.now().isoformat()
    )
    db.save_recency_record(record)
```

### 9.5 DB スキーマ

```sql
CREATE TABLE IF NOT EXISTS recency_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    primary_entities TEXT NOT NULL,  -- JSON配列
    primary_topics TEXT NOT NULL,    -- JSON配列
    published_at TEXT NOT NULL,       -- ISO8601
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_recency_channel_published ON recency_records(channel_id, published_at);
```

---

## 10. LLM呼び出し設計

### 10.1 呼び出し回数の試算

分析レイヤー1回あたりのLLM呼び出し：

| Step | 呼び出し回数 | 用途 |
|---|---|---|
| Step 1 | 0 | ルールベース判定のみ |
| Step 2 | 1 | ソース拡充時のキーワード抽出（必要時のみ） |
| Step 3 | 2 | 観点最終選定 + 観点検証 |
| Step 4 | 1 | 多角的分析（5観点まとめて1回）|
| Step 5 | 1 | 洞察抽出 |
| Step 6 | 0 | ルールベース判定のみ |
| **合計** | **5回** | |

既存パイプラインで約30回 + 分析レイヤー5回 = **約35回/実行**

1日3実行 = 105回/日 → Gemini Flash Lite 500/日 の **約21%消費**で運用可能。十分な余裕。

### 10.2 既存LLMClient抽象化の活用

```python
# src/llm/factory.py に新規roleを追加

def create_analysis_client() -> LLMClient:
    """分析レイヤー用のLLMクライアント。"""
    return create_client(
        role="analysis",
        tier_priority=["tier1", "tier2", "tier3"],  # tier4はフォールバック
        temperature=0.3,  # 分析は低めの温度（事実重視）
        max_tokens=2000
    )
```

### 10.3 プロンプト管理

プロンプトは外部ファイルに分離：

```
configs/prompts/analysis/
├── perspective_select.md       # Step 3: 観点最終選定
├── perspective_verify.md       # Step 3: 観点検証
├── multi_angle_analysis.md     # Step 4: 多角的分析
├── insights_extract.md         # Step 5: 洞察抽出
└── source_expand.md            # Step 2: ソース拡充用キーワード抽出
```

各プロンプトはチャンネル別バリアント対応：

```
configs/prompts/analysis/
├── geo_lens/                    # geo_lens用
│   ├── multi_angle_analysis.md
│   └── ...
├── japan_athletes/             # 将来Phase 2用（雛形だけ）
│   └── ...
└── k_pulse/                    # 将来Phase 3用（雛形だけ）
    └── ...
```

### 10.4 将来のClaude API切替対応

```python
# src/llm/factory.py

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")

def create_analysis_client() -> LLMClient:
    if LLM_PROVIDER == "gemini":
        return GeminiClient(...)
    elif LLM_PROVIDER == "claude":
        return ClaudeClient(...)  # Phase 2以降で実装
    else:
        raise ValueError(f"Unknown LLM provider: {LLM_PROVIDER}")
```

---

## 11. 既存コードへの変更点

### 11.1 新規追加するファイル

```
src/analysis/                              # 新規ディレクトリ
├── __init__.py
├── analysis_engine.py                     # 分析レイヤーのオーケストレータ
├── perspective_extractor.py               # Step 1: 観点候補ルールベース抽出
├── source_expander.py                     # Step 2: ソース拡充
├── perspective_selector.py                # Step 3: LLM観点選定・検証
├── multi_angle_analyzer.py                # Step 4: 多角的分析
├── insight_extractor.py                   # Step 5: 洞察抽出
├── duration_profile_selector.py           # Step 6: 動画尺プロファイル選定
└── recency_guard.py                       # Step 0: Recency Guard

configs/
├── channels.yaml                          # 新規: チャンネル設定
└── prompts/
    └── analysis/                          # 新規: 分析レイヤープロンプト
        ├── geo_lens/
        ├── japan_athletes/                # 雛形のみ
        └── k_pulse/                       # 雛形のみ

tests/
├── test_analysis_engine.py                # 新規
├── test_perspective_extractor.py          # 新規
├── test_recency_guard.py                  # 新規
└── test_channel_config.py                 # 新規
```

### 11.2 改修するファイル

| ファイル | 改修内容 | 影響度 |
|---|---|---|
| `src/shared/models.py` | `ChannelConfig`, `AnalysisResult`, `RecencyRecord` 等の追加。`ScoredEvent` に `channel_id`, `analysis_result` フィールド追加 | 中 |
| `src/main.py` | 分析レイヤー呼び出しの組込（slot-1確定後）。Top-3ループの廃止（フィーチャーフラグでオフ） | 中 |
| `src/storage/db.py` | `recency_records` テーブル追加。CRUD関数追加 | 小 |
| `src/llm/factory.py` | `create_analysis_client` 追加 | 小 |
| `src/generation/script_writer.py` | `AnalysisResult` を入力として受け取れるように改修。「武器庫6パターン」のうち情報密度型のみ使用するよう調整 | **大** |
| `src/generation/video_payload_writer.py` | 観点軸の情報を ペイロードに含める（将来のビジュアルマッピング用タグ）| 小 |

### 11.3 触らないファイル

以下は **絶対に触らない**：
- `src/generation/audio_renderer.py`（macOS sayの仮実装、後で完全置換）
- `src/generation/video_renderer.py`（Pillow+FFmpegの既存実装、Remotion移行で破棄予定）
- `src/ingestion/*`（RSSの取り込みロジックは安定）

### 11.4 環境変数の追加

```bash
# .env に追加
ANALYSIS_LAYER_ENABLED=true
ANALYSIS_LLM_TEMPERATURE=0.3
ANALYSIS_MAX_LLM_CALLS_PER_RUN=10
RECENCY_GUARD_HOURS=24
RECENCY_GUARD_PENALTY=0.5
DEFAULT_CHANNEL_ID=geo_lens
```

### 11.5 フィーチャーフラグ運用

```python
# src/main.py 内

if os.getenv("ANALYSIS_LAYER_ENABLED", "false").lower() == "true":
    analysis_result = run_analysis_layer(slot_1_event, channel_config)
    slot_1_event.analysis_result = analysis_result
    save_analysis_json(analysis_result, output_dir)

# 台本生成は analysis_result の有無で分岐
if slot_1_event.analysis_result:
    script = generate_script_with_analysis(slot_1_event)  # 新ルート
else:
    script = generate_script_legacy(slot_1_event)  # 既存ルート
```

---

## 12. 品質ルーブリック

### 12.1 4軸×3レベル評価

分析レイヤー実装後の台本品質を評価する基準。

| 軸 | レベル1（NG） | レベル2（許容）| レベル3（理想）|
|---|---|---|---|
| **事実の正確性** | 事実誤認あり | 事実は正確、根拠不明 | 全主張が evidence_refs で裏付け |
| **情報密度** | 一般論の羅列 | 具体的固有名詞あり | 視聴者が知らない事実3つ以上 |
| **視点の独自性** | テレビと同じ論調 | 海外視点の引用あり | 日本+複数地域の視点を統合 |
| **言語の自然さ** | SEOキーワード機械埋め込み | 自然な日本語 | 知的で耳に残る言い回し |

### 12.2 Phase 1 のゴール

- **全軸でレベル2以上を安定達成**
- **レベル3を3割以上で達成**

### 12.3 評価方法

1. 毎日の3本の台本をカズヤが手動レビュー
2. 4軸それぞれを1〜3で採点
3. スコアを `data/output/{event_id}_quality_review.json` に保存
4. 週次でアグリゲート、傾向分析

将来的にはLLMによる自動評価も追加可能（Phase 2以降）。

---

## 13. テスト戦略

### 13.1 ユニットテスト

| テストファイル | 対象 |
|---|---|
| `test_perspective_extractor.py` | 4軸の成立条件判定、スコア計算 |
| `test_recency_guard.py` | 24h窓の重複判定、降格ロジック |
| `test_channel_config.py` | YAML読み込み、Pydantic検証 |
| `test_duration_profile_selector.py` | プロファイル選定ロジック |

### 13.2 統合テスト

| テストファイル | 対象 |
|---|---|
| `test_analysis_engine.py` | Step 0〜6の全フロー（LLMはモック）|
| `test_main_with_analysis.py` | main.py の分析レイヤー組込確認 |

### 13.3 E2Eテスト

- 既存の `test_main_smoke.py` を拡張
- 分析レイヤー有効時に台本がエラーなく生成されることを確認
- ゴールデンマスター比較（Phase 2以降）

### 13.4 LLMモック戦略

LLM呼び出しは決定的にするためモック化：

```python
# tests/fixtures/llm_responses/
├── perspective_select_silence_gap.json
├── multi_angle_analysis_geopolitics.json
└── insights_extract_3items.json
```

---

## 14. 段階的ロールアウト計画

### 14.1 タイムライン

| Phase | 期間 | ゴール |
|---|---|---|
| **Phase 1-A** | Week 1 (今週) | 設計書承認、Claude Code 実装指示書作成 |
| **Phase 1-B** | Week 1-2 | データモデル実装、`channels.yaml` 作成 |
| **Phase 1-C** | Week 2 | 観点抽出（Step 1）+ Recency Guard実装 |
| **Phase 1-D** | Week 2-3 | LLM呼び出し系（Step 2-5）実装 |
| **Phase 1-E** | Week 3 | script_writer.py 改修、E2E動作確認 |
| **Phase 1-F** | Week 3-4 | 品質ルーブリック評価、台本品質確立 |
| **Phase 2** | Week 4-5 | 手動PoC（音声・画像・動画）|
| **Phase 3** | Week 5-7 | 半自動化（API組込）|
| **Phase 4** | Week 5-7 | Remotion移行（並行）|

### 14.2 Phase 1 の完了条件

- [ ] 分析レイヤーが ANALYSIS_LAYER_ENABLED=true で動作
- [ ] 4軸の観点判定がエラーなく稼働
- [ ] Recency Guard が24h窓で動作
- [ ] 台本品質ルーブリックで全軸レベル2以上達成
- [ ] 1日3回×1本生成が7日間連続でエラーなし
- [ ] geo_lens の channels.yaml 設定が正しく読み込める
- [ ] japan_athletes / k_pulse の雛形が用意されている（enabled: false）

### 14.3 ロールバック計画

問題発生時の切り戻し：
1. 環境変数 `ANALYSIS_LAYER_ENABLED=false` に変更
2. 既存パイプラインに即時切替（コード変更不要）
3. 並行で問題調査・修正

---

## 15. 音声・画像AIとの将来連携ポイント

### 15.1 設計時に意識すべき接続点

分析レイヤーの出力には、将来の音声・画像・動画パイプラインとの連携を意識した情報を含める。

#### 15.1.1 音声（ElevenLabs）連携用

```python
# AnalysisResult に含まれる情報が音声生成時にも活用される

# 文字数試算
char_count = sum(len(insight.text) for insight in insights)
# duration_profile から想定文字数算出
expected_chars = DURATION_PROFILES[selected_duration_profile].expected_chars

# Voice ID（ChannelConfigから）
voice_id = channel_config.voice_id  # Phase 2以降で活用
```

Phase 1 では SSML 対応は実装しない。プレーンテキストで台本を出力。Phase 2 の手動 PoC 中にポーズ・強調の入れ方を検証してから、Phase 3 で SSML 自動生成を実装する。

#### 15.1.2 画像生成連携用

`AnalysisResult` に「ビジュアル方針タグ」を含める：

```python
class AnalysisResult(BaseModel):
    # ... 既存フィールド省略 ...
    
    # ★将来連携用の追加フィールド
    visual_mood_tags: list[str] = []
    # 例: ["dark_cinematic", "split_contrast", "map_centric"]
```

観点 → ビジュアルタグの対応（参考、Phase 2で詰める）：

| 観点 | 推奨タグ |
|---|---|
| Silence Gap | `void_imagery`, `silenced_media`, `spotlight_absence` |
| Framing Inversion | `split_contrast`, `mirror_opposition`, `dual_perspective` |
| Hidden Stakes | `causal_chain`, `domino_effect`, `interconnected_systems` |
| Cultural Blindspot | `cultural_icon_contrast`, `civilizational_divide` |

Phase 1 では `visual_mood_tags` フィールドだけ用意。**具体的な画像プロンプトは Phase 2 の手動 PoC で詰める**。

#### 15.1.3 動画組立（Remotion移行後）連携用

`MultiAngleAnalysis` の各観点を、動画の章立て（チャプター）として活用可能：

```
Hook → 「Silence Gap の核心を1文で」
Setup → media_divergence + cultural_context（軽め）
Twist → geopolitical + political_intent + economic_impact（メイン）
Punchline → insights のトップ1〜2個
```

Phase 4 の Remotion 移行時に、`AnalysisResult` から直接動画スクリプトに変換するロジックを実装する。

### 15.2 今 Phase 1 で実装するもの

- `visual_mood_tags: list[str]` フィールドを `AnalysisResult` に用意
- 4観点 → デフォルトタグのマッピング（簡易版）
- ChannelConfig に `voice_id`, `visual_style` フィールド（値は未設定でOK）

### 15.3 Phase 1 で実装しないもの

- ElevenLabs API実装
- 画像生成API実装
- SSML 生成
- Remotion 移行
- 具体的なビジュアルプロンプトテンプレート

これらは手動 PoC（Phase 2）で型を作ってから自動化する。

---

## 16. 付録A: Claude Code 実装指示書

このセクションは、Claude Code に投げるための実装指示書のドラフト。設計書本体が承認されたら、別ファイルとして抽出する。

### 16.1 実装の前提

- 既存ブランチ: `main`
- 新規作業ブランチ: `feature/analysis-layer`
- 全変更はこのブランチで行い、テスト通過後に main へマージ

### 16.2 実装順序

#### Step 1: データモデルとconfig（Week 1-2前半）

1. `src/shared/models.py` に以下を追加:
   - `ChannelConfig`
   - `PerspectiveCandidate`
   - `MultiAngleAnalysis`
   - `Insight`
   - `AnalysisResult`
   - `RecencyRecord`
   - `ScoredEvent` に `channel_id`, `analysis_result` フィールド追加

2. `configs/channels.yaml` 作成:
   - `geo_lens` を enabled: true で設定
   - `japan_athletes`, `k_pulse` を enabled: false の雛形で用意

3. `src/storage/db.py` に `recency_records` テーブル追加

4. テスト: `tests/test_channel_config.py`, `tests/test_models_extension.py`

#### Step 2: Recency Guard（Week 2前半）

1. `src/analysis/recency_guard.py` 実装
2. `src/analysis/__init__.py` 作成
3. テスト: `tests/test_recency_guard.py`

#### Step 3: 観点抽出（ルールベース）（Week 2前半）

1. `src/analysis/perspective_extractor.py` 実装
   - 4軸の成立条件判定
   - スコア計算
2. テスト: `tests/test_perspective_extractor.py`

#### Step 4: ソース拡充（Week 2後半）

1. `src/analysis/source_expander.py` 実装
   - recent_event_pool からキーワード一致記事を取得
2. テスト: `tests/test_source_expander.py`

#### Step 5: LLM観点選定・検証（Week 2後半）

1. `configs/prompts/analysis/geo_lens/perspective_select.md` 作成
2. `configs/prompts/analysis/geo_lens/perspective_verify.md` 作成
3. `src/analysis/perspective_selector.py` 実装
4. `src/llm/factory.py` に `create_analysis_client` 追加
5. テスト: `tests/test_perspective_selector.py`（LLMモック使用）

#### Step 6: 多角的分析（Week 3前半）

1. `configs/prompts/analysis/geo_lens/multi_angle_analysis.md` 作成
2. `src/analysis/multi_angle_analyzer.py` 実装
3. テスト: `tests/test_multi_angle_analyzer.py`

#### Step 7: 洞察抽出（Week 3前半）

1. `configs/prompts/analysis/geo_lens/insights_extract.md` 作成
2. `src/analysis/insight_extractor.py` 実装
3. テスト: `tests/test_insight_extractor.py`

#### Step 8: 動画尺プロファイル選定（Week 3前半）

1. `src/analysis/duration_profile_selector.py` 実装
2. テスト: `tests/test_duration_profile_selector.py`

#### Step 9: オーケストレータ（Week 3前半）

1. `src/analysis/analysis_engine.py` 実装
   - 全Stepを束ねる関数 `run_analysis_layer()`
2. テスト: `tests/test_analysis_engine.py`（統合テスト）

#### Step 10: main.py への組込（Week 3後半）

1. `src/main.py` 改修:
   - 分析レイヤー呼び出しの追加（slot-1確定後）
   - Top-3ループの廃止（フィーチャーフラグでオフ）
2. `.env` 更新
3. テスト: `tests/test_main_with_analysis.py`

#### Step 11: script_writer.py 改修（Week 3-4）

1. `src/generation/script_writer.py` 改修:
   - `AnalysisResult` を入力として受け取れるように
   - 「武器庫6パターン」のうち情報密度型のみ使用
   - insights を Hook/Setup/Twist/Punchline に配分するロジック
2. テスト: `tests/test_script_writer_with_analysis.py`

#### Step 12: E2E動作確認（Week 4）

1. `python -m src.main --channel-id geo_lens` で実行
2. `data/output/{event_id}_analysis.json` が生成されることを確認
3. 台本品質を品質ルーブリックで評価
4. 7日間連続実行でエラーなしを確認

### 16.3 実装時の注意事項

- 既存テストを必ず通過させる
- フィーチャーフラグ `ANALYSIS_LAYER_ENABLED=false` で既存動作することを毎回確認
- LLM呼び出しは必ずモック可能な構造に
- プロンプトファイルは `.md` で外部化、ハードコード禁止
- `audio_renderer.py` / `video_renderer.py` には触らない

### 16.4 進捗報告フォーマット

各Step完了時に以下を報告：

```
## Step X 完了報告
- 実装ファイル: ...
- テスト結果: pytest X passed, Y failed
- 既存テスト影響: なし / あり（詳細）
- 次のSteps予定: ...
- 質問・懸念点: ...
```

---

## 改訂履歴

| 日付 | バージョン | 変更内容 | 作成者 |
|---|---|---|---|
| 2026-04-25 | v1.0 (Draft) | 初版作成 | Claude（カズヤとの議論ベース）|

---

*このドキュメントは、Hydrangea News PoC の分析レイヤー実装のための設計書です。実装前に必ずカズヤのレビューを受けること。*
