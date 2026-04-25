# CLAUDE_CODE_INSTRUCTIONS.md — 分析レイヤー実装指示書

> Hydrangea News PoC の分析レイヤーを Claude Code に実装させるための指示書。
> 5つのバッチに分割し、各バッチを別々のセッションで実装する。
> 作成日: 2026-04-25

---

## 全体像

### バッチ構成

| バッチ | 内容 | 想定行数 | 依存関係 |
|---|---|---|---|
| **Batch 1** | 土台（データモデル + Recency Guard + 観点抽出） | 約400行 | 独立 |
| **Batch 2** | LLM工程前半（コンテキスト構築 + 観点選定検証） | 約300行 | Batch 1 必須 |
| **Batch 3** | LLM工程後半（多角的分析 + 洞察抽出 + 尺プロファイル） | 約400行 | Batch 1, 2 必須 |
| **Batch 4** | 統合（オーケストレータ + main.py 組込） | 約300行 | Batch 1〜3 必須 |
| **Batch 5** | 仕上げ（script_writer 改修 + E2E確認） | 約500行 | Batch 1〜4 必須 |

### 進行ルール

1. **1バッチ = 1 Claude Code セッション** で完結
2. **バッチ間で必ず人間（カズヤ）のレビュー** を挟む
3. **各バッチで git ブランチを切る**: `feature/analysis-layer-batch{N}`
4. **`CLAUDE.md` の判断ルールに従う** — 質問せず判断、完了後にレポート
5. **完了レポートを必ず出す** — `CLAUDE.md` 指定のフォーマットで

---

## Batch 1: 土台（データモデル + Recency Guard + 観点抽出）

### 目的

分析レイヤーの基礎となる「データ構造」「ルールベース判定」「投稿履歴管理」を実装する。
LLM 呼び出しは含まない（次バッチ以降）。

### 投入プロンプト

以下を Claude Code にコピペで投入：

```
docs/CLAUDE_CODE_INSTRUCTIONS.md の Batch 1 を実装してください。

判断ルールと触ってはいけないファイルは CLAUDE.md に従ってください。
不明点は質問せず、CLAUDE.md の優先順位で自分で判断してください。
完了したら CLAUDE.md 指定のフォーマットでレポートしてください。
```

### 作業準備

```bash
git checkout main
git pull
git checkout -b feature/analysis-layer-batch1

# 既存テスト全通過を確認
pytest tests/ -v
# 失敗があれば作業中止して報告
```

### 実装する Step

#### Step 1: データモデルとconfig

**1-1. `src/shared/models.py` に以下を追加**:

```python
from pydantic import BaseModel
from typing import Optional

class ChannelConfig(BaseModel):
    """チャンネル単位の設定。Phase 1 は geo_lens のみ enabled。"""
    channel_id: str
    display_name: str
    enabled: bool
    source_regions: list[str]
    perspective_axes: list[str]
    duration_profiles: list[str]
    prompt_variant: str
    posts_per_day: int
    schedule_cron: Optional[str] = None
    voice_id: Optional[str] = None
    visual_style: Optional[str] = None

class PerspectiveCandidate(BaseModel):
    axis: str
    score: float
    reasoning: str
    evidence_refs: list[str]

class MultiAngleAnalysis(BaseModel):
    geopolitical: Optional[str] = None
    political_intent: Optional[str] = None
    economic_impact: Optional[str] = None
    cultural_context: Optional[str] = None
    media_divergence: Optional[str] = None

class Insight(BaseModel):
    text: str
    importance: float
    evidence_refs: list[str]

class AnalysisResult(BaseModel):
    event_id: str
    channel_id: str
    selected_perspective: PerspectiveCandidate
    rejected_perspectives: list[PerspectiveCandidate] = []
    perspective_verified: bool
    verification_notes: str
    multi_angle: MultiAngleAnalysis
    insights: list[Insight]
    selected_duration_profile: str
    expanded_sources: list[str] = []
    visual_mood_tags: list[str] = []
    analysis_version: str = "v1.0"
    generated_at: str
    llm_calls_used: int

class RecencyRecord(BaseModel):
    event_id: str
    channel_id: str
    primary_entities: list[str]
    primary_topics: list[str]
    published_at: str
```

**1-2. `ScoredEvent` に以下フィールド追加**（既存フィールドは変更しない）:
- `channel_id: str = "geo_lens"` 
- `analysis_result: Optional[AnalysisResult] = None`
- `recency_guard_applied: bool = False`
- `recency_overlap: list[str] = []`

**1-3. `configs/channels.yaml` 作成**:

```yaml
channels:
  - channel_id: geo_lens
    display_name: "Geopolitical Lens"
    enabled: true
    source_regions:
      - global
      - middle_east
      - europe
      - east_asia
      - global_south
    perspective_axes:
      - silence_gap
      - framing_inversion
      - hidden_stakes
      - cultural_blindspot
    duration_profiles:
      - breaking_shock_60s
      - media_critique_80s
      - anti_sontaku_90s
      - paradigm_shift_100s
      - cultural_divide_100s
      - geopolitics_120s
    prompt_variant: geo_lens_v1
    posts_per_day: 3
    schedule_cron: "0 0,8,16 * * *"
    voice_id: null
    visual_style: dark_cinematic

  - channel_id: japan_athletes
    display_name: "Japan Athletes Abroad"
    enabled: false
    source_regions: []
    perspective_axes: []
    duration_profiles: []
    prompt_variant: japan_athletes_v1
    posts_per_day: 0

  - channel_id: k_pulse
    display_name: "K-Pulse"
    enabled: false
    source_regions: []
    perspective_axes: []
    duration_profiles: []
    prompt_variant: k_pulse_v1
    posts_per_day: 0
```

**1-4. `configs/entity_dictionary.yaml` 作成**:

主要エンティティ・トピックの辞書。最低でも以下のカテゴリ・件数を含める：
- 主要人物（Trump, Putin, Xi Jinping, Kishida, Ishiba, Modi, Biden, Netanyahu 等）30個以上
- 主要組織（Fed, BOJ, OPEC, TSMC, NVIDIA, Apple, Toyota, EU, NATO, UN, WHO, IMF 等）20個以上
- 主要国（USA, China, Japan, Russia, Iran, Israel, India, Korea 等）20個以上
- 主要トピック（trade_war, ukraine_war, middle_east, global_economy, energy_crisis, ai_regulation 等）10個以上

各エントリには日本語表記揺れも含める（例: "Trump" → ["Trump", "trump", "トランプ", "Donald Trump"]）。

**1-5. `src/storage/db.py` に `recency_records` テーブル追加**:

```sql
CREATE TABLE IF NOT EXISTS recency_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    primary_entities TEXT NOT NULL,
    primary_topics TEXT NOT NULL,
    published_at TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_recency_channel_published 
    ON recency_records(channel_id, published_at);
```

CRUD関数も追加:
- `save_recency_record(record: RecencyRecord) -> None`
- `get_recency_records(channel_id: str, within_hours: int) -> list[RecencyRecord]`

#### Step 2: Recency Guard と Entity Extractor

**2-1. `src/analysis/__init__.py` 作成**

**2-2. `src/analysis/entity_extractor.py` 実装**:

設計書 Section 9.3 の仕様に従う。LLM呼び出しは一切行わない。
- `extract_primary_entities(event: ScoredEvent) -> list[str]`
- `extract_primary_topics(event: ScoredEvent) -> list[str]`
- `_normalize_entity(term: str) -> str`

`configs/entity_dictionary.yaml` を起動時に1回ロードしてメモリキャッシュ。

**2-3. `src/analysis/recency_guard.py` 実装**:

設計書 Section 9.2, 9.4 の仕様に従う。
- `apply_recency_guard(candidates: list[ScoredEvent], channel_id: str, db: Database) -> list[ScoredEvent]`
- `record_publication(event: ScoredEvent, channel_id: str, db: Database) -> None`

降格率は環境変数 `RECENCY_GUARD_PENALTY` で制御（デフォルト 0.5）。
窓は `RECENCY_GUARD_HOURS` で制御（デフォルト 24）。

#### Step 3: 観点抽出（ルールベース）

**3-1. `src/analysis/perspective_extractor.py` 実装**:

設計書 Section 5 の仕様に従う。
- `extract_perspectives(scored_event: ScoredEvent, channel_config: ChannelConfig) -> list[PerspectiveCandidate]`

4軸それぞれについて：
- `_calculate_silence_gap_score(event)` — sources_en/jp、global_attention、indirect_japan_impact から計算
- `_calculate_framing_inversion_score(event)` — perspective_gap_score、sources_jp/en から計算
- `_calculate_hidden_stakes_score(event)` — indirect_japan_impact、japan_industry_keyword から計算
- `_calculate_cultural_blindspot_score(event)` — cultural_uniqueness（既存になければ仮実装、後で改善）

成立条件チェック：
- `_meets_silence_gap_conditions(event) -> bool`
- 他3軸も同様

**3-2. ChannelConfig.perspective_axes に応じてフィルタリング**:

geo_lens では4軸全部、他チャンネルは設定で制限。

### テスト要件

**3-3. テストファイル作成**:

- `tests/test_channel_config.py` — channels.yaml ロード、Pydantic 検証
- `tests/test_models_extension.py` — ScoredEvent 拡張フィールド、AnalysisResult 構築
- `tests/test_entity_extractor.py` — 辞書照合、表記揺れ吸収、LLM呼び出ししないこと
- `tests/test_recency_guard.py` — 24h窓判定、降格ロジック、DBクエリモック
- `tests/test_perspective_extractor.py` — 4軸スコア計算、成立条件、ChannelConfig制限

各テストは LLM モック不要（Batch 1 では LLM 使わない）。

### 完了条件

- [ ] `pytest tests/ -v` で全テスト通過（既存 + 新規）
- [ ] 既存テストへの影響なし
- [ ] `ANALYSIS_LAYER_ENABLED=false` で main.py が従来通り動作
- [ ] `configs/channels.yaml` から `ChannelConfig.load("geo_lens")` できる
- [ ] `configs/entity_dictionary.yaml` から辞書がロードされる
- [ ] DB に `recency_records` テーブルが作成される

### 完了レポート

`CLAUDE.md` 指定のフォーマットで報告。Batch 2 に必要な情報を「次バッチへの引継ぎ事項」に含める。

---

## Batch 2: LLM工程前半（コンテキスト構築 + 観点選定検証）

### 目的

分析レイヤーの中核 LLM 呼び出し（観点選定+検証）を実装する。
コンテキスト構築は LLM を使わないが、Step 3 のプロンプトに統合される設計。

### 投入プロンプト

```
docs/CLAUDE_CODE_INSTRUCTIONS.md の Batch 2 を実装してください。

前提:
- Batch 1 は完了し main にマージ済み
- CLAUDE.md の判断ルールに従う
- 不明点は自分で判断、完了後にレポート
```

### 作業準備

```bash
git checkout main
git pull  # Batch 1 のマージを取り込む
git checkout -b feature/analysis-layer-batch2

pytest tests/ -v  # 既存テスト全通過を確認
```

### 実装する Step

#### Step 4: コンテキスト構築

**4-1. `src/analysis/context_builder.py` 実装**:

```python
from pydantic import BaseModel

class AnalysisContext(BaseModel):
    """Step 3〜5 のLLMプロンプトに渡されるコンテキスト。"""
    event_id: str
    channel_id: str
    perspective_candidates: list[PerspectiveCandidate]  # Top3
    article_snippets: list[dict]  # 既存clusterの記事タイトル+サマリ
    background_questions: list[str]  # LLM知識補完用の質問テンプレート

def build_analysis_context(
    scored_event: ScoredEvent,
    perspective_candidates: list[PerspectiveCandidate],
    channel_config: ChannelConfig,
) -> AnalysisContext:
    """
    LLM呼び出しなし。
    既存の ScoredEvent.articles から記事スニペットを抽出し、
    観点軸ごとの背景質問テンプレートを準備する。
    """
    ...
```

**重要**: 関連記事の再検索は行わない（既存 event_builder のクラスタリングを信頼）。
LLM 呼び出しゼロ、純粋なプロンプト準備のみ。

#### Step 5: LLM観点選定+検証

**5-1. `configs/prompts/analysis/geo_lens/perspective_select_and_verify.md` 作成**:

設計書 Section 4.2 Step 3 の仕様に従う。

プロンプトの骨格：
```
あなたは Hydrangea Geopolitical Lens の編集長です。

【タスク】
以下の Top3 観点候補から、台本として最も「視聴者が賢くなる体験」を
提供できる観点を1つ選び、その成立を検証してください。

【観点候補】
{perspective_candidates}

【記事スニペット】
{article_snippets}

【背景質問】
{background_questions}

【出力形式】
以下のJSONのみを出力してください:
{
  "selected_axis": "silence_gap" | "framing_inversion" | "hidden_stakes" | "cultural_blindspot",
  "reasoning": "なぜこの観点を選んだか（2〜3文）",
  "evidence_for_selection": ["evidence_id_1", "evidence_id_2", ...],
  "verification": {
    "actually_holds": true | false,
    "notes": "検証メモ（例: 日本主要紙3社で言及確認、ゼロではない）",
    "confidence": 0.0〜1.0
  },
  "fallback_axis_if_failed": "silence_gap" | ... | null
}

【判断基準】
- silence_gap: 海外で大ニュース、日本未報道（sources_jp == 0 が絶対条件）
- framing_inversion: 日本と海外で「誰が悪者か」が真逆
- hidden_stakes: 日本生活・経済直結だが報道で繋げられてない
- cultural_blindspot: 日本の常識では理解できない海外の論理

【検証ルール】
- silence_gap の場合: sources_jp が本当にゼロか、記事スニペットで再確認
- framing_inversion の場合: 主体・述語の差異が本当にあるか確認
- hidden_stakes の場合: 日本企業・産業との因果連鎖が成立するか確認
- cultural_blindspot の場合: 文化対比軸が明確か確認
```

**5-2. `src/analysis/perspective_selector.py` 実装**:

```python
from src.llm.factory import create_analysis_client

def llm_select_and_verify_perspective(
    scored_event: ScoredEvent,
    candidates: list[PerspectiveCandidate],
    context: AnalysisContext,
    mode: str = "select_and_verify",  # or "verify_only"
) -> dict:
    """
    1回のLLM呼び出しで観点選定 + 検証を行う。
    検証失敗時は fallback_axis を返す。
    """
    client = create_analysis_client()
    prompt = load_prompt("geo_lens", "perspective_select_and_verify")
    formatted_prompt = prompt.format(
        perspective_candidates=candidates,
        article_snippets=context.article_snippets,
        background_questions=context.background_questions,
    )
    response = client.generate(formatted_prompt)
    return parse_json_response(response)


def select_perspective(
    scored_event: ScoredEvent,
    perspective_candidates: list[PerspectiveCandidate],
    context: AnalysisContext,
) -> Optional[PerspectiveCandidate]:
    """
    設計書 Section 5.3 に従う。
    Top3 → LLM Select & Verify → 必要時 fallback で再検証。
    """
    ...
```

**5-3. `src/llm/factory.py` に `create_analysis_client` 追加**:

既存の `create_client(role=...)` パターンに従って `role="analysis"` を追加。
- temperature: 0.3（事実重視）
- max_tokens: 2000
- Tier 1〜3 を使用、Tier 4 はフォールバックのみ

### テスト要件

- `tests/test_context_builder.py` — LLM 呼び出ししないこと、article_snippets 抽出
- `tests/test_perspective_selector.py` — LLM モック使用、Select & Verify、フォールバック分岐

LLM モックフィクスチャ:
- `tests/fixtures/llm_responses/perspective_select_and_verify_silence_gap.json`
- `tests/fixtures/llm_responses/perspective_select_and_verify_failed_fallback.json`

### 完了条件

- [ ] `pytest tests/ -v` で全テスト通過
- [ ] 既存テストへの影響なし
- [ ] `ANALYSIS_LAYER_ENABLED=false` で main.py が従来通り動作
- [ ] LLM モックで Step 4〜5 が結合動作する

### 完了レポート

`CLAUDE.md` 指定のフォーマットで報告。Batch 3 への引継ぎ事項を明記。

---

## Batch 3: LLM工程後半（多角的分析 + 洞察抽出 + 尺プロファイル）

### 目的

分析レイヤーの残り3 Step（多角的分析、洞察抽出、動画尺プロファイル選定）を実装する。

### 投入プロンプト

```
docs/CLAUDE_CODE_INSTRUCTIONS.md の Batch 3 を実装してください。

前提:
- Batch 1, 2 は完了し main にマージ済み
- CLAUDE.md の判断ルールに従う
```

### 作業準備

```bash
git checkout main
git pull
git checkout -b feature/analysis-layer-batch3

pytest tests/ -v
```

### 実装する Step

#### Step 6: 多角的分析

**6-1. `configs/prompts/analysis/geo_lens/multi_angle_analysis.md` 作成**:

設計書 Section 7 の5観点を1回のLLM呼び出しで生成する。

```
あなたは Hydrangea Geopolitical Lens の解説アナリストです。

【タスク】
以下のニュース事象について、5つの観点で構造化分析を行ってください。
各観点は3〜5文の文章で、具体的な固有名詞・数字・因果関係を含めてください。

【選ばれた観点軸】
{selected_axis}: {selected_axis_reasoning}

【記事スニペット】
{article_snippets}

【出力形式】
{
  "geopolitical": "地政学的分析（3〜5文）",
  "political_intent": "政治的意図の分析（3〜5文）",
  "economic_impact": "経済的影響、特に日本への影響（3〜5文）",
  "cultural_context": "文化的文脈、日本との差異（3〜5文）",
  "media_divergence": "報道差異の分析、各国メディアの強調点（3〜5文）"
}

【禁止事項】
- 一般論・常套句の羅列
- 出典のない断定
- 陰謀論的表現
- 扇動的表現
```

**6-2. `src/analysis/multi_angle_analyzer.py` 実装**:

```python
def perform_multi_angle_analysis(
    scored_event: ScoredEvent,
    perspective: PerspectiveCandidate,
    context: AnalysisContext,
) -> MultiAngleAnalysis:
    """1回のLLM呼び出しで5観点すべて生成。"""
    ...
```

#### Step 7: 洞察抽出

**7-1. `configs/prompts/analysis/geo_lens/insights_extract.md` 作成**:

設計書 Section 8 の仕様に従う。

```
あなたは知的好奇心の高い視聴者向けの優秀な編集者です。

【タスク】
以下の多角的分析を読み、視聴者が「人に話したくなる核心情報」を3〜5個抽出してください。

【条件】
- 各洞察は1〜2文の自己完結した断片
- 数字・固有名詞・因果関係のいずれかを必ず含む
- 視聴者の世界観をアップデートする要素を優先
- 一般論・常套句は除外

【入力】
{multi_angle_analysis}

【出力形式】
{
  "insights": [
    {
      "text": "洞察本文",
      "importance": 0.0〜1.0,
      "evidence_refs": ["evidence_id_1", "evidence_id_2"]
    },
    ...
  ]
}
```

**7-2. `src/analysis/insight_extractor.py` 実装**:

```python
def extract_insights(
    multi_angle: MultiAngleAnalysis,
    perspective: PerspectiveCandidate,
    context: AnalysisContext,
) -> list[Insight]:
    """LLM呼び出し1回で3〜5個の洞察を抽出。"""
    ...
```

#### Step 8: 動画尺プロファイル選定

**8-1. `src/analysis/duration_profile_selector.py` 実装**:

設計書 Section 6.3 のロジックに従う。LLM呼び出しなし。

```python
def select_duration_profile(
    perspective: PerspectiveCandidate,
    insights: list[Insight],
    multi_angle: MultiAngleAnalysis,
    channel_config: ChannelConfig,
) -> str:
    """
    観点軸 × 洞察の量 × 分析の深さ から最適プロファイルを選定。
    ChannelConfig.duration_profiles の中から1つ選ぶ。
    """
    ...
```

**8-2. ビジュアルムードタグの生成**:

設計書 Section 15.1.2 の対応マッピングを実装：

```python
def generate_visual_mood_tags(perspective: PerspectiveCandidate) -> list[str]:
    """観点軸からビジュアル方針タグを生成（Phase 2以降の画像生成用）。"""
    AXIS_TO_TAGS = {
        "silence_gap": ["void_imagery", "silenced_media", "spotlight_absence"],
        "framing_inversion": ["split_contrast", "mirror_opposition", "dual_perspective"],
        "hidden_stakes": ["causal_chain", "domino_effect", "interconnected_systems"],
        "cultural_blindspot": ["cultural_icon_contrast", "civilizational_divide"],
    }
    return AXIS_TO_TAGS.get(perspective.axis, [])
```

### テスト要件

- `tests/test_multi_angle_analyzer.py` — LLM モック、5観点出力検証
- `tests/test_insight_extractor.py` — LLM モック、3〜5個出力検証
- `tests/test_duration_profile_selector.py` — ルールベース判定、各観点ごとのプロファイル選定

LLM モックフィクスチャ:
- `tests/fixtures/llm_responses/multi_angle_analysis_geopolitics.json`
- `tests/fixtures/llm_responses/multi_angle_analysis_minimal.json`
- `tests/fixtures/llm_responses/insights_extract_3items.json`

### 完了条件

- [ ] `pytest tests/ -v` で全テスト通過
- [ ] 既存テストへの影響なし
- [ ] LLM モックで Step 6〜8 が結合動作する

---

## Batch 4: 統合（オーケストレータ + main.py 組込）

### 目的

Batch 1〜3 で実装した個別 Step を束ねて、分析レイヤー全体を main.py に組み込む。

### 投入プロンプト

```
docs/CLAUDE_CODE_INSTRUCTIONS.md の Batch 4 を実装してください。

前提:
- Batch 1, 2, 3 は完了し main にマージ済み
- CLAUDE.md の判断ルールに従う
- main.py の改修は分析レイヤー組込のみ、既存ロジックは触らない
```

### 作業準備

```bash
git checkout main
git pull
git checkout -b feature/analysis-layer-batch4

pytest tests/ -v
```

### 実装する Step

#### Step 9: オーケストレータ

**9-1. `src/analysis/analysis_engine.py` 実装**:

```python
import time
from datetime import datetime

def run_analysis_layer(
    scored_event: ScoredEvent,
    channel_config: ChannelConfig,
    db: Database,
) -> Optional[AnalysisResult]:
    """
    設計書 Section 4.2 のフロー全体をオーケストレートする。
    
    Step 0: Recency Guard（候補レベル、上流で適用済み想定）
    Step 1: 観点候補ルールベース抽出
    Step 2: コンテキスト構築
    Step 3: 観点選定 + 検証 (Select & Verify in one call)
    Step 4: 多角的分析
    Step 5: 洞察抽出
    Step 6: 動画尺プロファイル選定
    
    Returns:
        AnalysisResult | None  (Noneの場合は分析失敗、既存ルートにフォールバック)
    """
    llm_calls = 0
    started_at = datetime.now().isoformat()
    
    try:
        # Step 1: 観点候補抽出（ルールベース）
        candidates = extract_perspectives(scored_event, channel_config)
        if not candidates:
            return None  # 4軸全部不成立
        
        top3 = sorted(candidates, key=lambda c: c.score, reverse=True)[:3]
        
        # Step 2: コンテキスト構築（LLMなし）
        context = build_analysis_context(scored_event, top3, channel_config)
        
        # Step 3: 観点選定 + 検証（LLM 1回、フォールバック時+1）
        selected = select_perspective(scored_event, top3, context)
        llm_calls += 1
        if not selected:
            return None
        
        # Step 4: 多角的分析（LLM 1回）
        multi_angle = perform_multi_angle_analysis(scored_event, selected, context)
        llm_calls += 1
        
        # Step 5: 洞察抽出（LLM 1回）
        insights = extract_insights(multi_angle, selected, context)
        llm_calls += 1
        
        # Step 6: 動画尺プロファイル選定（ルールベース）
        duration_profile = select_duration_profile(
            selected, insights, multi_angle, channel_config
        )
        
        # ビジュアルムードタグ生成
        visual_tags = generate_visual_mood_tags(selected)
        
        return AnalysisResult(
            event_id=scored_event.event_id,
            channel_id=channel_config.channel_id,
            selected_perspective=selected,
            rejected_perspectives=[c for c in top3 if c.axis != selected.axis],
            perspective_verified=True,
            verification_notes="...",
            multi_angle=multi_angle,
            insights=insights,
            selected_duration_profile=duration_profile,
            visual_mood_tags=visual_tags,
            analysis_version="v1.0",
            generated_at=started_at,
            llm_calls_used=llm_calls,
        )
    
    except Exception as e:
        logger.error(f"Analysis layer failed: {e}", exc_info=True)
        return None  # 失敗時は None、既存ルートにフォールバック


def save_analysis_json(
    analysis_result: AnalysisResult,
    output_dir: Path,
) -> Path:
    """{event_id}_analysis.json として保存。"""
    output_path = output_dir / f"{analysis_result.event_id}_analysis.json"
    output_path.write_text(
        analysis_result.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return output_path
```

#### Step 10: main.py への組込

**10-1. `src/main.py` 改修**:

slot-1 確定後、Gemini Judge の前に分析レイヤーを呼び出す。

```python
# 既存のslot-1選定コードの後

if os.getenv("ANALYSIS_LAYER_ENABLED", "false").lower() == "true":
    channel_id = os.getenv("DEFAULT_CHANNEL_ID", "geo_lens")
    channel_config = ChannelConfig.load(channel_id)
    
    # Recency Guard 適用
    candidates = apply_recency_guard(candidates, channel_id, db)
    
    # slot-1 再決定（Recency Guard 後）
    slot_1_event = candidates[0] if candidates else None
    
    if slot_1_event:
        # 分析レイヤー実行
        analysis_result = run_analysis_layer(slot_1_event, channel_config, db)
        if analysis_result:
            slot_1_event.analysis_result = analysis_result
            save_analysis_json(analysis_result, output_dir)
            logger.info(f"Analysis layer completed: {analysis_result.event_id}")
        else:
            logger.warning(f"Analysis layer returned None, falling back to legacy")

# 既存の Gemini Judge 以降の処理
```

**10-2. Top-3 ループの廃止（フィーチャーフラグ）**:

```python
TOP_N_GENERATION = int(os.getenv("TOP_N_GENERATION", "1"))  # デフォルト1（旧3）

for i, event in enumerate(top_candidates[:TOP_N_GENERATION]):
    # 台本生成...
```

**10-3. 投稿成功時の Recency Record 記録**:

```python
# 投稿成功後
if os.getenv("ANALYSIS_LAYER_ENABLED", "false").lower() == "true":
    record_publication(slot_1_event, channel_id, db)
```

**10-4. `.env.example` 更新**:

```bash
# 分析レイヤー設定
ANALYSIS_LAYER_ENABLED=false
ANALYSIS_LLM_TEMPERATURE=0.3
ANALYSIS_MAX_LLM_CALLS_PER_RUN=10
RECENCY_GUARD_HOURS=24
RECENCY_GUARD_PENALTY=0.5
DEFAULT_CHANNEL_ID=geo_lens
TOP_N_GENERATION=1
```

### テスト要件

- `tests/test_analysis_engine.py` — 全Step統合テスト、各Stepの失敗時フォールバック
- `tests/test_main_with_analysis.py` — main.py の分析レイヤー組込確認

### 完了条件

- [ ] `pytest tests/ -v` で全テスト通過
- [ ] `ANALYSIS_LAYER_ENABLED=false` で main.py が完全に従来通り動作
- [ ] `ANALYSIS_LAYER_ENABLED=true` で分析レイヤーが起動し、`{event_id}_analysis.json` が生成される
- [ ] `ANALYSIS_LAYER_ENABLED=true` で Recency Guard が動作する
- [ ] LLM モックを使った E2E テストが通る

---

## Batch 5: 仕上げ（script_writer 改修 + E2E確認）

### 目的

分析レイヤーの出力（AnalysisResult）を台本生成に接続し、台本品質を抜本的に改善する。
この Batch が分析レイヤー実装の最終工程。

### 投入プロンプト

```
docs/CLAUDE_CODE_INSTRUCTIONS.md の Batch 5 を実装してください。

前提:
- Batch 1〜4 は完了し main にマージ済み
- CLAUDE.md の判断ルールに従う
- script_writer.py の改修は AnalysisResult 入力対応のみ
- 既存の「武器庫6パターン」のうち情報密度型のみ使用
```

### 作業準備

```bash
git checkout main
git pull
git checkout -b feature/analysis-layer-batch5

pytest tests/ -v
```

### 実装する Step

#### Step 11: script_writer.py 改修

**11-1. `src/generation/script_writer.py` 改修**:

`AnalysisResult` を入力として受け取れる新ルートを追加。

```python
def generate_script_with_analysis(
    scored_event: ScoredEvent,
    analysis_result: AnalysisResult,
    channel_config: ChannelConfig,
) -> VideoScript:
    """
    分析レイヤーの結果を入力に台本生成。
    既存の generate_script_legacy() とは別ルート。
    """
    # 動画尺から構造を決定
    duration_profile = analysis_result.selected_duration_profile
    profile_config = DURATION_PROFILES[duration_profile]
    # 例: profile_config = {hook_sec: 6, setup_sec: 24, twist_sec: 60, punchline_sec: 30}
    
    # insights を Hook/Setup/Twist/Punchline に配分
    sorted_insights = sorted(
        analysis_result.insights,
        key=lambda i: i.importance,
        reverse=True,
    )
    
    # LLM プロンプト構築
    prompt = load_prompt(channel_config.channel_id, "script_with_analysis")
    formatted_prompt = prompt.format(
        perspective=analysis_result.selected_perspective,
        insights=sorted_insights,
        multi_angle=analysis_result.multi_angle,
        duration_profile=duration_profile,
        target_chars=profile_config["target_chars"],
    )
    
    # LLM 呼び出し
    response = generation_client.generate(formatted_prompt)
    return parse_video_script(response)
```

**11-2. プロンプト追加**:

`configs/prompts/script/geo_lens/script_with_analysis.md` を新規作成。

設計書 Section 8.4 の「insights を Hook/Setup/Twist/Punchline に配分」ルールに従う。
扇動ではなく情報密度で勝負。武器庫6パターンのうち以下のみ使用：
- breaking_shock
- geopolitics
- paradigm_shift
- cultural_divide

**禁止する旧パターン**:
- 「target_enemy」概念の濫用
- 「物申す系YouTuber構文」
- 抽象煽りHook（「〇〇が言わない真実」など）

**11-3. main.py の台本生成分岐**:

```python
if slot_1_event.analysis_result:
    script = generate_script_with_analysis(
        slot_1_event,
        slot_1_event.analysis_result,
        channel_config,
    )
else:
    # 従来ルート（フィーチャーフラグオフ時、または分析失敗時）
    script = generate_script_legacy(slot_1_event)
```

**11-4. video_payload_writer.py の軽微改修**:

`AnalysisResult.visual_mood_tags` を video_payload に含める。
具体的なビジュアル選定は Phase 2 の手動 PoC で詰めるため、Phase 1 ではタグ転送のみ。

#### Step 12: E2E 動作確認

**12-1. 統合 E2E テスト**:

`tests/test_e2e_analysis_layer.py` 新規作成。

```python
def test_e2e_analysis_layer_geo_lens():
    """
    LLMモックを使って main.py を起動、
    {event_id}_script.json が分析レイヤー経由で生成されることを確認。
    """
    # 環境変数設定
    os.environ["ANALYSIS_LAYER_ENABLED"] = "true"
    os.environ["DEFAULT_CHANNEL_ID"] = "geo_lens"
    
    # サンプルデータで main 実行
    result = run_main_with_sample_data()
    
    # assertions
    assert (output_dir / "{event_id}_analysis.json").exists()
    assert (output_dir / "{event_id}_script.json").exists()
    
    script = load_json(output_dir / "{event_id}_script.json")
    assert "selected_perspective" in script.get("metadata", {})
    assert script["sections"][0]["heading"] == "hook"
```

**12-2. ローカル実行確認**:

実 LLM を使った1回の試運転：

```bash
ANALYSIS_LAYER_ENABLED=true python -m src.main --mode normalized --channel-id geo_lens
```

生成された `{event_id}_analysis.json` と `{event_id}_script.json` を完了レポートに添付。

**12-3. 既存パイプラインとの並列動作確認**:

```bash
# 既存ルート
ANALYSIS_LAYER_ENABLED=false python -m src.main --mode normalized
# → 従来通りの台本が生成されることを確認

# 新ルート
ANALYSIS_LAYER_ENABLED=true python -m src.main --mode normalized
# → 分析レイヤー経由の台本が生成されることを確認
```

### テスト要件

- `tests/test_script_writer_with_analysis.py` — 新ルート単体テスト、insights 配分検証
- `tests/test_e2e_analysis_layer.py` — E2E 統合テスト

### 完了条件

- [ ] `pytest tests/ -v` で全テスト通過
- [ ] 既存テストへの影響なし
- [ ] `ANALYSIS_LAYER_ENABLED=true` で `{event_id}_analysis.json` と `{event_id}_script.json` が両方生成される
- [ ] `ANALYSIS_LAYER_ENABLED=false` で従来通りの台本が生成される
- [ ] 実 LLM での試運転1回成功
- [ ] 設計書 Section 12 の品質ルーブリック観点で、生成された台本がレベル2以上を達成（人間レビュー必要）

### 完了レポート

`CLAUDE.md` 指定のフォーマットで報告。実 LLM 試運転で生成した `_analysis.json` と `_script.json` の内容も添付。

---

## バッチ完了後のチェックリスト（人間用）

### 各バッチごと

- [ ] 完了レポートの内容を確認
- [ ] `pytest tests/ -v` の結果を確認
- [ ] 触ってはいけないファイルへの変更がないか確認
- [ ] ブランチを main にマージ
  ```bash
  git checkout main
  git merge feature/analysis-layer-batch{N}
  git push origin main
  ```

### Batch 5 完了後の試運転

- [ ] 開発環境で `ANALYSIS_LAYER_ENABLED=true` での1日試運転
- [ ] 生成された台本3本を品質ルーブリック（設計書 Section 12）で評価
- [ ] 全軸でレベル2以上達成を確認
- [ ] 問題なければ本番環境で `ANALYSIS_LAYER_ENABLED=true` に切替

### 問題発生時のロールバック

```bash
# 即時切戻し
export ANALYSIS_LAYER_ENABLED=false
# main.py 再起動
```

または特定バッチを取り消したい場合：

```bash
git revert {merge_commit_hash}
git push origin main
```

---

## バージョン情報

- 文書バージョン: v1.0
- 対応する設計書: `docs/ANALYSIS_LAYER_DESIGN_v1.1.md`
- 最終更新: 2026-04-25

---

*この指示書は Hydrangea News PoC の分析レイヤー実装のために Claude Code に投入する。各バッチを別セッションで実装し、人間（カズヤ）のレビューを必ず挟むこと。*
