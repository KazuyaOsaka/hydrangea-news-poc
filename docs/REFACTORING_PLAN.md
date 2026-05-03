# REFACTORING_PLAN.md — Hydrangea 改修計画

> ⚠️ **本書は 2026-04-23 時点の改修議論アーカイブ**。Phase 命名 (Phase 1-4) は
> 当時のもので、最新の Phase 体系 (Phase A.5-3a-verify → 3b → 3c → 3d → Phase 1
> (1-A〜1-D) → Phase B → Phase C) とは別系列。最新の Phase 体系および
> ロードマップは `docs/CURRENT_STATE.md` / `docs/FUTURE_WORK.md` を **正本** として
> 参照すること。
>
> 本書の個別改修内容は以下のように現運用に取り込み済み:
>
> - 旧 Phase 1 (ChannelConfig / scoring.py YAML 化等) → FUTURE_WORK Phase 1-A
> - 旧 Phase 2 (japan_athletes 立ち上げ) → FUTURE_WORK Phase B-3
> - 旧 Phase 3 (k_pulse 立ち上げ) → FUTURE_WORK Phase B-4
> - 旧 Phase 4 (Remotion 移行) → FUTURE_WORK Phase A.5-3c
>   F-video-compose-integration として前倒し
>
> 本書は設計議論の歴史的記録として保持する (F-state-protocol 哲学
> 「アーカイブは削除しない」)。新規バッチ実装時の参照は限定的とすること。
> 最終整理 (アーカイブ統合 or 完全削除の判断) は README 全面書き直しと同時、
> Phase A.5-3d 完了後を予定 (FUTURE_WORK 緊急度低を参照)。

> このドキュメントは、Hydrangea の今後 2 つの大きな変更（**A: 3 チャンネル対応化**、**B: Remotion 移行**）に向けた改修計画です。
> エンジニア素人の方向けに、専門用語は都度注釈します。
> 作成日：2026-04-23

---

## 目次

1. [用語の約束](#0-用語の約束)
2. [A. 3 チャンネル対応化の改修計画](#a-3-チャンネル対応化の改修計画)
3. [B. Remotion 移行の改修計画](#b-remotion-移行の改修計画)
4. [全体スケジュール提案](#c-全体スケジュール提案)
5. [リスクと対策](#d-リスクと対策)

---

## 0. 用語の約束

| 用語 | 素人向けの意味 |
|---|---|
| **Remotion** | React（Web フロントエンドのライブラリ）で動画を作れるフレームワーク。コンポーネントをそのまま動画のワンシーンにできる。 |
| **React**（リアクト） | Facebook 製の UI 部品ライブラリ。Web ページの動的要素を作る定番。 |
| **props**（プロップス） | React のコンポーネントに渡すデータ。例：`<TitleCard title="ロイター速報" />` の `title` 部分。 |
| **TypeScript**（タイプスクリプト） | JavaScript に「型」を足した言語。Remotion の推奨言語。 |
| **スキーマ**（schema） | データの形・構造の約束事。JSON スキーマ、Pydantic スキーマ、Zod スキーマなど。 |
| **リファクタリング** | 動作を変えずにコードを整理・改善すること。 |
| **リグレッションテスト** | 変更後に「今まで動いていたものが壊れていないか」を確認するテスト。 |
| **スナップショットテスト** | 変更前の出力を保存し、変更後と照合するテスト手法。 |
| **CLI**（Command Line Interface） | コマンドラインで操作する UI（`python -m src.main ...` のような使い方）。 |
| **フィーチャーフラグ** | 機能を環境変数やフラグで ON/OFF できる仕組み。段階リリースに使う。 |
| **DI**（Dependency Injection） | 「依存するものを外から注入する」設計パターン。引数で渡すだけでも DI。 |

---

# A. 3 チャンネル対応化の改修計画

## A.1 ゴール

1 システム・複数 YAML で次の 3 チャンネルを並行運用できるようにする：

| チャンネル ID | 内容 | タイミング |
|---|---|---|
| `geo_lens` | Geopolitical Lens（政治・経済）— **現行システムの延長** | 最初にリリース |
| `japan_athletes` | Japan Athletes Abroad（スポーツ） | 後続 |
| `k_pulse` | K-Pulse（韓国エンタメ） | 後続 |

### 設計原則

1. **コードは 1 つ、設定を 3 つ**：`channels/{channel_id}.yaml` でチャンネル固有設定
2. **共通部分は `config/base.yaml`**：全チャンネル共通のデフォルト
3. **`channel_id` を関数引数で伝播**：グローバル変数に逃げない
4. **現行パイプライン（`geo_lens`）は無改修で動き続ける**：リファクタの前後で同じ動画が出ること

---

## A.2 現状で「チャンネル固定」になっている箇所の全列挙

ファイルと行番号、具体的な値をすべて列挙します。これを一つずつ YAML 駆動に変えていきます。

### A.2.1 スコアリング関連（`src/triage/`）

| ファイル:行 | ハードコード内容 | 使用目的 |
|---|---|---|
| `src/triage/scoring.py:9-16` | `CATEGORY_BASE`（economy=85, politics=80, sports=60, entertainment=55 など） | 記事カテゴリごとのベーススコア |
| `src/triage/scoring.py:19-30` | `HIGH_IMPACT_KEYWORDS`（利上げ+10, 解散+10, 増税+8, 少子化+7） | 日本経済・政治の重要キーワード |
| `src/triage/scoring.py:53-95` | `_PILOT_REGIONS` / `_BRIDGE_SOURCE_NAMES` / `_NON_WESTERN_REGIONS` | 地域多様性ボーナスの対象 |
| `src/triage/scoring.py:112-116` | `_TECH_KW`（ai, 半導体, chip, quantum, nvidia, クラウド） | 技術系カテゴリ判定 |
| `src/triage/scoring.py:117-121` | `_TECH_GEO_KW`（覇権, 輸出規制, supply chain, 経済安保） | 技術×地政学ボーナス |
| `src/triage/scoring.py:122-128` | `_BIG_EVENT_KW`（選挙, 大統領, 日銀, fed, 利上げ） | 大型事象ボーナス |
| `src/triage/scoring.py:129-134` | `_GEO_CONFLICT_KW`（war, 紛争, ukraine, 台湾, 核, 南シナ海） | 地政学ボーナス |
| `src/triage/scoring.py:135-139` | `_SPORTS_KW`（大谷, ohtani, mlb, サッカー, オリンピック） | スポーツ加点（ただしベース点が低い） |
| `src/triage/scoring.py:156-161` | `_JAPAN_POLITICS_KW`（首相, 岸田, 日米関係, 防衛省） | 日本政治キーワード |
| `src/triage/scoring.py:162-169` | `_JAPAN_ECONOMY_KW`（toyota, softbank, 日銀, nikkei 225） | 日本経済キーワード |
| `src/triage/scoring.py:171-181` | `_JAPANESE_PERSON_KW`（大谷, 孫正義, 宮崎駿） | 日本人有名人加点 |
| `src/triage/scoring.py:184-200` | `_BREAKING_SHOCK_KW`（停戦, 制裁, 緊急利上げ, デフォルト） | 速報性加点 |
| `src/triage/scoring.py:237-297` | `_INDIRECT_JAPAN_IMPACT_KW`（ホルムズ海峡, TSMC, 円安） | 日本への間接インパクト判定 |

### A.2.2 編集方針プロンプト

| ファイル:行 | ハードコード内容 | 使用目的 |
|---|---|---|
| `src/triage/prompts.py:6-115` | 全文 115 行の日本語システムプロンプト | トリアージ時の LLM 指示 |
| `src/generation/script_writer.py:268-446` | 「武器庫 6 パターン」「Hook 5 類型」「STEP 1〜4.5」の日本語指示 | 台本生成時の LLM 指示 |
| `src/generation/script_writer.py:80-88` | `target_enemy` 候補（財務省/日銀・大手メディア・米国政府/中国共産党・GAFAM・既存秩序） | 台本の仮想敵候補 |
| `src/generation/script_writer.py:470-497` | `_ALLEGATION_KW` / `_ALLEGATION_AUTH_SOURCES`（疑惑記事の警告発動トリガ） | allegation 警告用 |
| `src/generation/title_generator.py` | サムネタイトル生成の日本語指示 | |
| `src/generation/article_writer.py` | 記事生成の日本語指示 | |

### A.2.3 コヒーレンスゲート・judge

| ファイル:行 | ハードコード内容 | 使用目的 |
|---|---|---|
| `src/triage/coherence_gate.py:63-87` | `DOMESTIC_ROUTINE_PATTERNS`（首相動静, 決算短信, 訃報 など 9 種） | 国内ルーティンニュース検出 |
| `src/triage/coherence_gate.py:98-200` | JP↔EN 翻訳辞書 | ペア一致判定 |
| `src/triage/gemini_judge.py:47-80` | `_JUDGE_PROMPT`（日本向け上級編集者プロンプト） | Gemini Judge の指示 |
| `src/triage/gemini_judge.py:29-43` | `_MAX_SNIPPET_CHARS`, `_MAX_SOURCES_PER_SIDE`, `_VALID_PUBLISHABILITY` | Judge 入力制限 |
| `src/llm/judge.py` | Elite Judge 評価軸（アンチ忖度・多極的視点・アウトサイド・イン・知的優越感・ファンダム最速） | 編集軸 |

### A.2.4 クロス言語・クラスタリング

| ファイル:行 | ハードコード内容 | 使用目的 |
|---|---|---|
| `src/ingestion/cross_lang_matcher.py:23-82` | 日英翻訳辞書（国名 38、エンティティ 20+、キーワード 20+） | タイトル照合 |
| `src/ingestion/event_builder.py:104-142` | `_HIGH_FREQ_ANCHORS`（israel, iran, trump, biden, musk など） | クラスタリング用アンカー |
| `src/ingestion/event_builder.py:155-223` | `_PREDICATE_FAMILIES`（tax_fiscal, conflict_military, humanitarian, energy_supply など 6 種） | 意味ドメインの整合性ガード |
| `src/ingestion/event_builder.py:1203-1333` | JP 記事→`japan_view`, 非 JP→`global_view` の割り当て | イベント変換 |

### A.2.5 動画・音声・タイトル

| ファイル:行 | ハードコード内容 | 使用目的 |
|---|---|---|
| `src/shared/config.py:155-157` | `TTS_VOICE = "Kyoko"`（macOS say の日本語音声） | 音声合成 |
| `src/shared/config.py:161-164` | `VIDEO_WIDTH=720, VIDEO_HEIGHT=1280, VIDEO_FPS=30` | 動画フォーマット |
| `src/generation/video_renderer.py:44-107` | `_THEME` 6 テーマのカラーパレット | 視覚デザイン |
| `src/generation/video_renderer.py:110-116` | `_JP_FONT_CANDIDATES`（ヒラギノ角ゴシック優先） | 日本語フォント |
| `src/generation/script_writer.py:22-27` | `_DURATIONS`（hook=4, setup=16, twist=40, punchline=20 秒） | 4 ブロック尺 |
| `src/generation/script_writer.py:33-38` | `_CHAR_BOUNDS`（setup=60-90, twist=150-220 字） | 文字数境界 |
| `src/generation/script_writer.py:42-64` | `PLATFORM_PROFILES`（shared=80s, tiktok=72s, youtube_shorts=78s） | プラットフォーム別尺 |
| `src/generation/script_writer.py:66` | `_JP_CHARS_PER_SEC = 4.5`（日本語 1 秒あたり文字数） | 尺→文字数の換算 |
| `src/generation/video_payload_writer.py:11-60` | `_VISUAL_HINTS`, `_VISUAL_MODES`, `_VISUAL_GOALS`, `_TRANSITION_HINTS` | シーン別演出ヒント |
| `src/generation/video_payload_writer.py:89-103` | `_BASE_NEGATIVE`, `_WEAK_EVIDENCE_NEGATIVE_EXTRA`, `_HYPOTHESIS_NEGATIVE_EXTRA` | 映像生成の禁止事項 |

### A.2.6 ソース媒体

| ファイル:行 | ハードコード内容 | 使用目的 |
|---|---|---|
| `configs/sources.yaml` | 19 媒体 enabled（NHK, Reuters, Al Jazeera など） | RSS 取得対象 |
| `configs/source_profiles.yaml` | 媒体格付け（top/major/standard）と表示名（英FT, 米ロイター など） | 台本内の引用制御 |

### A.2.7 予算・スケジュール

| ファイル:行 | ハードコード内容 | 使用目的 |
|---|---|---|
| `.env:31-35` | `LLM_CALL_BUDGET_PER_RUN=150, PER_DAY=1000, PUBLISH_RESERVE_CALLS=15` | 予算 |
| `.env:26-27` | `RUNS_PER_DAY=5, MAX_PUBLISHES_PER_DAY=5` | 公開頻度 |
| `src/shared/config.py:40` | `PUBLISH_RESERVE_CALLS` デフォルト = 15 | production 温存 |

---

## A.3 YAML スキーマ提案

### A.3.1 ディレクトリ構造

```
configs/
├── base.yaml                     # 全チャンネル共通デフォルト
├── channels/
│   ├── geo_lens.yaml             # Geopolitical Lens
│   ├── japan_athletes.yaml       # Japan Athletes Abroad
│   └── k_pulse.yaml              # K-Pulse
├── sources/
│   ├── geo_lens_sources.yaml     # Geopolitical Lens 向け RSS リスト
│   ├── japan_athletes_sources.yaml
│   └── k_pulse_sources.yaml
├── source_profiles/
│   ├── geo_lens_profiles.yaml    # 媒体格付け（チャンネル別）
│   ├── japan_athletes_profiles.yaml
│   └── k_pulse_profiles.yaml
├── prompts/
│   ├── geo_lens/
│   │   ├── triage.md             # トリアージ用システムプロンプト
│   │   ├── script.md             # 台本生成プロンプト
│   │   ├── article.md
│   │   ├── title.md
│   │   └── judge.md
│   ├── japan_athletes/
│   │   └── ...同様...
│   └── k_pulse/
│       └── ...同様...
└── dictionaries/
    ├── common.yaml               # 共通の翻訳辞書
    ├── geo_lens.yaml             # 地政学固有
    ├── japan_athletes.yaml       # スポーツ固有
    └── k_pulse.yaml              # K-pop 固有
```

### A.3.2 `configs/base.yaml`（抜粋）

```yaml
# ── 全チャンネル共通デフォルト ─────────────────────────────────
# チャンネル固有 YAML で上書き可能

runtime:
  run_mode: publish_mode
  max_publishes_per_day: 5
  runs_per_day: 5

llm:
  provider: gemini
  # モデル階層（チャンネル別に上書き可）
  model_tiers:
    tier1: gemini-3.1-flash-lite-preview
    tier2: gemini-3.0-flash
    tier3: gemini-2.5-flash
    tier4: gemini-2.5-flash-lite
  call_interval_sec: 0.5

budget:
  per_run: 150
  per_day: 1000
  publish_reserve: 15
  en_candidates_per_jp_cluster: 2

gates:
  garbage_filter_enabled: true
  viral_filter_enabled: true
  viral_score_threshold: 40.0
  elite_judge_enabled: true
  elite_judge_candidate_limit: 10
  judge_enabled: true
  judge_candidate_limit: 3

video_output:
  width: 720
  height: 1280
  fps: 30
  platform_profile: shared  # shared / tiktok / youtube_shorts

audio:
  provider: macos_say  # 将来的に elevenlabs / google_tts 等
  voice: Kyoko
  framerate: 22050
  tts_timeout_sec: 60

script:
  platform_profile: shared
  chars_per_sec: 4.5
  durations_sec:
    hook: 4
    setup: 16
    twist: 40
    punchline: 20
  char_bounds:
    hook: [8, 22]
    setup: [60, 90]
    twist: [150, 220]
    punchline: [70, 110]
  max_validation_retries: 3

# プロンプトファイルパス（チャンネル固有 YAML で path を上書きして差し替え）
prompts:
  triage: null              # チャンネル固有で必ず指定
  script: null
  article: null
  title: null
  judge: null
```

### A.3.3 `configs/channels/geo_lens.yaml`（現行動作を再現する例）

```yaml
# ── Geopolitical Lens チャンネル設定 ──────────────────────────
channel_id: geo_lens
display_name: "Geopolitical Lens"
description: "日本の報道では見えない世界との認識差を 60〜90 秒で伝える"

# ソース（RSS 一覧）
sources_yaml: configs/sources/geo_lens_sources.yaml
source_profiles_yaml: configs/source_profiles/geo_lens_profiles.yaml

# プロンプト（.md ファイルを参照）
prompts:
  triage:  configs/prompts/geo_lens/triage.md
  script:  configs/prompts/geo_lens/script.md
  article: configs/prompts/geo_lens/article.md
  title:   configs/prompts/geo_lens/title.md
  judge:   configs/prompts/geo_lens/judge.md

# 辞書
dictionaries:
  - configs/dictionaries/common.yaml
  - configs/dictionaries/geo_lens.yaml

# スコアリング
scoring:
  category_base:
    economy: 85.0
    politics: 80.0
    technology: 75.0
    startup: 70.0
    sports: 60.0
    entertainment: 55.0
  high_impact_keywords:
    - ["利上げ", 10.0]
    - ["利下げ", 10.0]
    - ["解散", 10.0]
    - ["増税", 8.0]
    - ["減税", 8.0]
    - ["少子化", 7.0]
    - ["AI", 5.0]
    - ["EV", 5.0]
  keyword_sets:
    tech: [ai, 人工知能, 半導体, chip, quantum, nvidia, クラウド]
    tech_geo: [覇権, 国家戦略, 安全保障, 輸出規制, huawei, supply chain, 経済安保]
    big_event: [選挙, 大統領, 日銀, fed, 利上げ, 利下げ, 政策金利]
    geo_conflict: [war, 戦争, conflict, 紛争, ukraine, 台湾, 核, 南シナ海]
    sports: []            # このチャンネルはスポーツ加点なし
    japan_politics: [首相, kishida, 日米関係, 防衛省]
    japan_economy: [toyota, ソニー, softbank, 日銀, nikkei 225]
    japanese_person: [大谷, shohei ohtani, 孫正義, 宮崎駿]
    breaking_shock: [停戦, ceasefire, 制裁, sanction, 緊急利上げ, デフォルト]
    indirect_japan_impact:
      - ホルムズ海峡
      - TSMC
      - supply chain
      - usdjpy
      - 円安

# コヒーレンスゲート
coherence_gate:
  enabled: true
  threshold: 0.25
  blacklist_threshold: 0.50
  diary_threshold: 0.65
  domestic_routine_patterns:
    - 首相動静
    - 首相日程
    - 人事異動
    - 決算短信
    - 定例開示
    - スポーツ結果
    - 事故速報
    - 訃報
    - 市況

# 視覚テーマ（video_payload_writer が参照）
visual_themes:
  hook: anchor_style
  setup:
    strong: document_style
    partial: document_style
    weak: infographic
  twist:
    strong: split_screen
    partial: structure_diagram
    weak: symbolic
  punchline:
    strong: market_graphic
    partial: infographic
    weak: symbolic

# 音声（base.yaml を継承、上書きしない）
# audio: （デフォルトのまま Kyoko）

# 映像出力（base.yaml を継承）
# video_output: （720x1280 30fps）
```

### A.3.4 `configs/channels/japan_athletes.yaml`（差分イメージ）

```yaml
channel_id: japan_athletes
display_name: "Japan Athletes Abroad"

sources_yaml: configs/sources/japan_athletes_sources.yaml
source_profiles_yaml: configs/source_profiles/japan_athletes_profiles.yaml

prompts:
  triage:  configs/prompts/japan_athletes/triage.md
  script:  configs/prompts/japan_athletes/script.md
  # …

scoring:
  category_base:
    sports: 95.0         # スポーツを最重要に
    entertainment: 70.0
    economy: 30.0
    politics: 25.0
  keyword_sets:
    sports: [大谷, mlb, 野球, サッカー, エンゼルス, ドジャース, プレミアリーグ, ...]
    japan_politics: []   # このチャンネルでは使わない
  # ...

audio:
  voice: Kyoko  # 日本語解説なので Kyoko 継続
  # voice: Otoya  # 男性ナレーションに差し替えたい場合
```

### A.3.5 `configs/channels/k_pulse.yaml`（韓国エンタメ）

```yaml
channel_id: k_pulse
display_name: "K-Pulse"

prompts:
  triage:  configs/prompts/k_pulse/triage.md
  # …韓国エンタメ特化の編集方針…

scoring:
  category_base:
    entertainment: 90.0
    sports: 40.0
    economy: 30.0
  keyword_sets:
    kpop_artist: [BLACKPINK, BTS, NewJeans, SEVENTEEN, aespa, ...]
    drama: [Netflix, tvN, JTBC, ...]

audio:
  voice: Kyoko  # 視聴者は日本人想定なので日本語ナレーション維持
  # 将来的に Yuna（韓国語）に切替する場合のフック
```

---

## A.4 必要な新規ファイル・クラス・関数

### A.4.1 新規ファイル

```
src/
├── channel/                              # 【新規】チャンネル抽象化レイヤ
│   ├── __init__.py
│   ├── loader.py                         # ChannelConfig ロード
│   ├── config.py                         # ChannelConfig Pydantic モデル
│   ├── registry.py                       # チャンネル ID → 設定のレジストリ
│   └── prompt_loader.py                  # .md プロンプトファイル読み込み
│
├── pipeline/                             # 【新規】main.py から分離
│   ├── __init__.py
│   ├── runner.py                         # run_channel(channel_id, ...) のメイン
│   ├── budget_init.py
│   ├── slot_selection.py
│   ├── reports.py
│   ├── pool.py
│   └── archive.py
│
├── scoring/                              # 【新規】scoring.py を分解
│   ├── __init__.py
│   ├── engine.py                         # ChannelScorer クラス（DI可能）
│   ├── keyword_scorer.py                 # YAML 辞書駆動
│   └── editorial_scorer.py               # YAML 編集方針駆動
│
└── rendering_bridge/                     # 【新規】Remotion 用 props 生成（B で使用）
    ├── __init__.py
    └── remotion_props.py
```

### A.4.2 主要クラス

```python
# src/channel/config.py

from pydantic import BaseModel
from pathlib import Path

class ChannelRuntime(BaseModel):
    max_publishes_per_day: int
    run_mode: str

class ChannelLLM(BaseModel):
    provider: str
    model_tiers: dict[str, str]
    call_interval_sec: float

class ChannelScoringConfig(BaseModel):
    category_base: dict[str, float]
    high_impact_keywords: list[tuple[str, float]]
    keyword_sets: dict[str, list[str]]

class ChannelPromptPaths(BaseModel):
    triage:  Path
    script:  Path
    article: Path
    title:   Path
    judge:   Path

class ChannelConfig(BaseModel):
    channel_id: str
    display_name: str
    sources_yaml: Path
    source_profiles_yaml: Path
    prompts: ChannelPromptPaths
    dictionaries: list[Path]
    scoring: ChannelScoringConfig
    coherence_gate: dict
    visual_themes: dict
    audio: dict
    video_output: dict
    script: dict
    budget: dict
    gates: dict
    runtime: ChannelRuntime
    llm: ChannelLLM

    @classmethod
    def load(cls, channel_id: str, base_yaml: Path = Path("configs/base.yaml")) -> "ChannelConfig":
        """base.yaml をロード → channels/{channel_id}.yaml でマージ → ChannelConfig として返す"""
        ...
```

### A.4.3 関数シグネチャ変更

既存関数に `channel_config: ChannelConfig` を追加する。例：

```python
# Before
def rank_events(events: list[NewsEvent]) -> list[ScoredEvent]:
    ...

# After
def rank_events(
    events: list[NewsEvent],
    channel_config: ChannelConfig,
) -> list[ScoredEvent]:
    ...
```

この変更は `src/main.py`、`src/triage/*`、`src/generation/*` のほぼ全関数に波及します。

> **素人向け補足**：これは「DI（Dependency Injection = 依存を引数で注入する）」パターンです。グローバル変数ではなく引数として渡すことで、テストでダミー設定を差し込めるようになり、3 チャンネルを同時にテストできます。

---

## A.5 既存ファイルへの変更内容

| ファイル | 変更内容 | 影響規模 |
|---|---|---|
| `src/main.py` | `argparse` に `--channel-id` を追加。`run_channel()` に分岐。 | 中（~50 行追加） |
| `src/main.py` | 3303 行を `src/pipeline/` 配下に分割 | 大（全面書き直し） |
| `src/shared/config.py` | 環境変数ベースから YAML ベースに移行（base.yaml + channels/*.yaml をロード） | 中（ファイル全書き直し、ただし環境変数は後方互換で残す） |
| `src/triage/scoring.py` | ハードコード→`channel_config.scoring` 参照 | 大（1128 行を refactor） |
| `src/triage/prompts.py` | プロンプト定数削除 → `prompt_loader.load(channel_config.prompts.triage)` | 小（置き換えのみ） |
| `src/triage/gemini_judge.py` | `_JUDGE_PROMPT` を外部 .md ファイル化 | 小 |
| `src/triage/coherence_gate.py` | `DOMESTIC_ROUTINE_PATTERNS` を YAML 化 | 中 |
| `src/ingestion/cross_lang_matcher.py` | 翻訳辞書を YAML 化 | 中 |
| `src/ingestion/event_builder.py` | `_HIGH_FREQ_ANCHORS` などを YAML 化 | 大（1496 行、一部のみ） |
| `src/generation/script_writer.py` | `_PROMPT_TEMPLATE`, 定数を `channel_config.script` / prompts 参照 | 中 |
| `src/generation/article_writer.py` | 同上 | 中 |
| `src/generation/title_generator.py` | 同上 | 中 |
| `src/generation/video_payload_writer.py` | `_VISUAL_HINTS` 他を `channel_config.visual_themes` 参照 | 小 |
| `src/storage/db.py` | `jobs`, `events`, `recent_event_pool` テーブルに `channel_id` カラム追加 | 小（マイグレーション要） |

### DB マイグレーション

```sql
-- 全テーブルに channel_id カラム追加
ALTER TABLE jobs              ADD COLUMN channel_id TEXT NOT NULL DEFAULT 'geo_lens';
ALTER TABLE events            ADD COLUMN channel_id TEXT NOT NULL DEFAULT 'geo_lens';
ALTER TABLE daily_stats       ADD COLUMN channel_id TEXT NOT NULL DEFAULT 'geo_lens';
ALTER TABLE ingestion_batches ADD COLUMN channel_id TEXT NOT NULL DEFAULT 'geo_lens';
ALTER TABLE seen_article_urls ADD COLUMN channel_id TEXT NOT NULL DEFAULT 'geo_lens';
ALTER TABLE recent_event_pool ADD COLUMN channel_id TEXT NOT NULL DEFAULT 'geo_lens';

-- daily_stats の PRIMARY KEY を変更（(date, channel_id) で一意）
-- SQLite は ALTER TABLE で PK 変更ができないので、テーブル再作成する必要あり
```

---

## A.6 変更の優先順位と依存関係

**依存グラフ**：下ほど先に完了が必要。**段階的立ち上げ方針**（geo_lens → japan_athletes → k_pulse）に合わせてブロック化。

```
【Phase 1：geo_lens 完全自動化（Week 1-4）】
Phase 1-0: .gitignore 修正（TECH_DEBT 1.1） ✅完了
Phase 1-0: API キーローテーション（TECH_DEBT 1.2）
Phase 1-0: MP4 ゴールデン作成（REFACTORING_PLAN B.2）
  │
  ▼
Phase 1-A: ChannelConfig スキーマ定義（`src/channel/`）
  │
  ▼
Phase 1-B: base.yaml + geo_lens.yaml 作成（現行の再現のみ）
  │
  ▼
Phase 1-C: main.py に --channel-id フラグ追加（既定 geo_lens、他はエラー）
  │
  ▼
Phase 1-D: src/pipeline/ へ分割（main.py の責務分離）
  │
  ▼
Phase 1-E: scoring.py の YAML 駆動化
Phase 1-E: prompts の外部ファイル化（geo_lens/ 配下 5 本）
Phase 1-E: cross_lang_matcher の辞書 YAML 化
  │
  ▼
Phase 1-F: DB マイグレーション（channel_id カラム追加、default 'geo_lens'）
  │
  ▼
Phase 1-G: リグレッションテスト（geo_lens が旧実装と同じ動画を出す）
Phase 1-G: japan_athletes / k_pulse の YAML 雛形作成（ロードだけ通る）
  │
  ▼【Phase 1 完了ゲート：geo_lens が 1 週間連続稼働】
  │
  ▼
【Phase 2：japan_athletes 追加（Week 4-5）— コードに触らない】
Phase 2-A: スポーツ系 RSS ソース追加
Phase 2-B: japan_athletes.yaml 本格化（category_base, keywords, 辞書）
Phase 2-C: japan_athletes/ プロンプト 5 本作成（Breaking Shock 重視）
  │
  ▼【Phase 2 完了ゲート：japan_athletes が 3 日連続稼働】
  │
  ▼
【Phase 3：k_pulse 追加（Week 6-7）— コードに触らない】
Phase 3-A: 韓国エンタメ系 RSS ソース追加
Phase 3-B: k_pulse.yaml 本格化（entertainment 重視、日韓辞書 50+）
Phase 3-C: k_pulse/ プロンプト 5 本作成（ポップなトーン）
  │
  ▼【Phase 3 完了ゲート：3 チャンネル並行稼働】

【Phase 4：Remotion 移行（Week 5-7、Phase 2-3 と並列）】
Phase 4 は Phase 1 完了が前提だが、Phase 2-3 とは独立に進行可能。
video_renderer.py → Remotion コンポーネント群への置換。
全チャンネル同時切替（フィーチャーフラグ）。
```

**重要な設計上の前提：**

- **Phase 2 / Phase 3 ではソースコードに一切触らない**（YAML 追加のみで立ち上がるのが Phase 1 の成果物）。
- もし Phase 2 でコード修正が必要になったら、**Phase 1 の抽象化が不十分なサイン**。その場合は Phase 1 に戻って根本対処する（Phase 2 の延長線上での場当たり対応は禁止）。
- Phase 1 完了までは `japan_athletes` / `k_pulse` は YAML 雛形のみ存在し、**実稼働させない**。

---

# B. Remotion 移行の改修計画

## B.1 ゴール

現状の Python 動画合成（Pillow + imageio-ffmpeg + subprocess ffmpeg）を廃止し、React 製の **Remotion** に置き換える。

### B.1.1 責務の変化

| レイヤ | 現状 | 移行後 |
|---|---|---|
| Python | シーン画像を Pillow で描画 → MP4 エンコード → ffmpeg で音声 mux | **Remotion が読み込む JSON（props）を生成するだけ** |
| 音声 | macOS `say` で WAV 生成（Python 側） | 当面は Python `say` を維持（Remotion 側で音声ファイルを受け取る）／将来クラウド TTS |
| 動画合成 | Python `video_renderer.py`（532 行） | React/TypeScript の Remotion コンポーネント |
| 動画エンコード | `imageio-ffmpeg` + subprocess ffmpeg | Remotion CLI（内部で ffmpeg）|

---

## B.2 現状の動画合成処理の特定

### B.2.1 置き換え対象（削除予定）

| ファイル | 責務 | 削除後の扱い |
|---|---|---|
| `src/generation/video_renderer.py`（532 行） | Pillow でシーン描画・FFmpeg でエンコード・音声 mux | **完全削除** |
| `src/generation/video_renderer.py` 内の `_THEME`, `_JP_FONT_CANDIDATES`, `_make_gradient_bg`, `_render_scene_frame`, `_draw_lower_third` | 視覚デザイン関連 | **Remotion 側の React コンポーネントに再実装** |
| `src/render/run_render.py` の video render 呼び出し部分 | 既存候補の再レンダリング | Remotion CLI 呼び出しに置き換え |
| `src/main.py:_render_av_outputs()` の video 部分 | パイプライン連携 | Remotion CLI 呼び出しに置き換え |

### B.2.2 残す処理（責務変更）

| ファイル | 現在の責務 | 移行後の責務 |
|---|---|---|
| `src/generation/audio_renderer.py`（281 行） | macOS `say` で WAV 作成 | **そのまま残す**（音声はまだ Python 側） |
| `src/generation/video_payload_writer.py`（483 行） | 動画制作用 JSON を生成 | **Remotion 用 props JSON を生成**（大改修） |

### B.2.3 FFmpeg 呼び出し箇所（Remotion 置換で削除）

| ファイル:行 | 呼び出し | 削除 or 残す |
|---|---|---|
| `src/generation/video_renderer.py:358` | `ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()` | 削除 |
| `src/generation/video_renderer.py:366-382` | `imageio.get_writer(...)` で MP4 書き出し | 削除 |
| `src/generation/video_renderer.py:407-422` | `subprocess.run([ffmpeg_exe, -i, -i, -c:v, copy, -c:a, aac, ...])` の音声 mux | 削除（Remotion が内部で実行） |

---

## B.3 Remotion 用 props JSON スキーマ提案

### B.3.1 ディレクトリ構成（新規）

リポジトリ直下に `remotion/` ディレクトリを追加（別 Git サブプロジェクトではなく monorepo 的に同居）：

```
hydrangea-news-poc/
├── remotion/                          # 【新規】Remotion プロジェクト
│   ├── package.json
│   ├── remotion.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── Root.tsx                   # コンポジション登録
│   │   ├── Video.tsx                  # メイン Video コンポーネント
│   │   ├── scenes/
│   │   │   ├── HookScene.tsx          # 4 ブロックの各シーン
│   │   │   ├── SetupScene.tsx
│   │   │   ├── TwistScene.tsx
│   │   │   └── PunchlineScene.tsx
│   │   ├── components/
│   │   │   ├── LowerThird.tsx         # 下部テロップ
│   │   │   ├── TitleCard.tsx
│   │   │   └── SourceBadge.tsx
│   │   ├── themes/                    # _THEME の移植先
│   │   │   ├── anchor_style.ts
│   │   │   ├── split_screen.ts
│   │   │   └── ...
│   │   └── schema.ts                  # Zod スキーマ（Python JSON の検証）
│   └── public/
│       └── fonts/                     # Noto Sans JP 等の Web フォント
└── src/  # （Python、既存）
```

### B.3.2 Remotion props JSON スキーマ（Python → Remotion へ渡す形）

```json
{
  "schema_version": "1.0",
  "channel_id": "geo_lens",
  "event_id": "art-abc123...",
  "composition": {
    "width": 720,
    "height": 1280,
    "fps": 30,
    "durationInFrames": 2400
  },
  "meta": {
    "title_layer": {
      "canonical_title": "...",
      "platform_title": "...",
      "hook_line": "...",
      "thumbnail_text": "..."
    },
    "source_attribution": "Hydrangea News"
  },
  "audio": {
    "voiceover_path": "data/output/art-abc123_voiceover.wav",
    "total_duration_sec": 80.0,
    "segments": [
      {
        "scene_index": 0,
        "scene_id": "art-abc123_s00_hook",
        "start_sec": 0.0,
        "duration_sec": 4.0,
        "placeholder": false
      },
      ...
    ]
  },
  "scenes": [
    {
      "scene_index": 0,
      "scene_id": "art-abc123_s00_hook",
      "heading": "hook",
      "visual_mode": "anchor_style",
      "theme_id": "anchor_style",
      "start_sec": 0.0,
      "duration_sec": 4.0,
      "narration_text": "NHKが言わない真実があります",
      "on_screen_text": "NHKが言わない真実",
      "must_include": ["数字", "固有名詞"],
      "must_avoid": ["陰謀論的表現"],
      "source_grounding": ["ロイター", "英FT"],
      "transition_hint": "cut → news headline graphic (0.3s)"
    },
    ...
  ]
}
```

### B.3.3 Zod スキーマ（Remotion 側の型安全性）

```typescript
// remotion/src/schema.ts
import { z } from "zod";

export const SceneSchema = z.object({
  scene_index: z.number(),
  scene_id: z.string(),
  heading: z.enum(["hook", "setup", "twist", "punchline"]),
  visual_mode: z.string(),
  theme_id: z.string(),
  start_sec: z.number(),
  duration_sec: z.number(),
  narration_text: z.string(),
  on_screen_text: z.string().optional(),
  must_include: z.array(z.string()).default([]),
  must_avoid: z.array(z.string()).default([]),
  source_grounding: z.array(z.string()).default([]),
  transition_hint: z.string().optional(),
});

export const VideoPropsSchema = z.object({
  schema_version: z.literal("1.0"),
  channel_id: z.string(),
  event_id: z.string(),
  composition: z.object({
    width: z.number(),
    height: z.number(),
    fps: z.number(),
    durationInFrames: z.number(),
  }),
  meta: z.object({
    title_layer: z.object({
      canonical_title: z.string(),
      platform_title: z.string(),
      hook_line: z.string(),
      thumbnail_text: z.string(),
    }),
    source_attribution: z.string(),
  }),
  audio: z.object({
    voiceover_path: z.string(),
    total_duration_sec: z.number(),
    segments: z.array(z.object({...})),
  }),
  scenes: z.array(SceneSchema),
});

export type VideoProps = z.infer<typeof VideoPropsSchema>;
```

---

## B.4 Python 側の新規モジュール設計

### B.4.1 `src/rendering_bridge/remotion_props.py`（新規）

```python
"""
Remotion が読み込む props JSON を生成する。
既存の VideoPayload + VideoScript + AudioSegment から組み立て、
Remotion CLI 呼び出しで使える .json ファイルを data/output/ に書き出す。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.channel.config import ChannelConfig
    from src.shared.models import VideoPayload, VideoScript
    from src.generation.audio_renderer import AudioSegment


def build_remotion_props(
    channel_config: "ChannelConfig",
    script: "VideoScript",
    payload: "VideoPayload",
    audio_segments: list["AudioSegment"],
    voiceover_path: Path,
) -> dict:
    """Python の成果物 → Remotion props dict への変換。

    Returns:
        Remotion の VideoProps スキーマに準拠した dict
    """
    fps = channel_config.video_output["fps"]
    total_sec = sum(seg.actual_duration_sec for seg in audio_segments)
    duration_in_frames = int(round(total_sec * fps))

    scenes = []
    cursor = 0.0
    for i, scene in enumerate(payload.scenes):
        seg = next((s for s in audio_segments if s.scene_index == i), None)
        dur = seg.actual_duration_sec if seg else float(scene.duration_sec)
        scenes.append({
            "scene_index": i,
            "scene_id": scene.scene_id or f"{script.event_id}_s{i:02d}_{scene.heading}",
            "heading": scene.heading,
            "visual_mode": scene.visual_mode,
            "theme_id": _resolve_theme_id(scene, channel_config),
            "start_sec": cursor,
            "duration_sec": dur,
            "narration_text": scene.narration,
            "on_screen_text": scene.on_screen_text,
            "must_include": scene.must_include,
            "must_avoid": scene.must_avoid,
            "source_grounding": scene.source_grounding,
            "transition_hint": scene.transition_hint,
        })
        cursor += dur

    return {
        "schema_version": "1.0",
        "channel_id": channel_config.channel_id,
        "event_id": script.event_id,
        "composition": {
            "width": channel_config.video_output["width"],
            "height": channel_config.video_output["height"],
            "fps": fps,
            "durationInFrames": duration_in_frames,
        },
        "meta": {
            "title_layer": script.title_layer.model_dump() if script.title_layer else {},
            "source_attribution": "Hydrangea News",
        },
        "audio": {
            "voiceover_path": str(voiceover_path),
            "total_duration_sec": total_sec,
            "segments": [seg.to_dict() for seg in audio_segments],
        },
        "scenes": scenes,
    }


def write_remotion_props(
    props: dict,
    output_dir: Path,
    event_id: str,
) -> Path:
    """props を <event_id>_remotion_props.json に書き出す。"""
    path = output_dir / f"{event_id}_remotion_props.json"
    path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def invoke_remotion_render(
    props_path: Path,
    output_mp4_path: Path,
    remotion_project_dir: Path = Path("remotion"),
) -> dict:
    """Remotion CLI を subprocess で呼び出し、MP4 を生成する。

    コマンド例:
        cd remotion && npx remotion render src/Root.tsx HydrangeaVideo \
            --props=../data/output/art-abc123_remotion_props.json \
            ../data/output/art-abc123_review.mp4
    """
    import subprocess
    cmd = [
        "npx", "remotion", "render",
        "src/Root.tsx",
        "HydrangeaVideo",
        f"--props={props_path.absolute()}",
        str(output_mp4_path.absolute()),
    ]
    result = subprocess.run(
        cmd,
        cwd=remotion_project_dir,
        capture_output=True,
        timeout=600,  # 10 分（Remotion レンダは時間がかかりうる）
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.decode(errors="replace"),
        "stderr": result.stderr.decode(errors="replace"),
        "mp4_path": str(output_mp4_path) if result.returncode == 0 else None,
    }
```

### B.4.2 `src/main.py` の `_render_av_outputs()` の変更

```python
# Before (現行)
from src.generation.video_renderer import render_video
mp4_path, render_manifest = render_video(payload, audio_segments, output_dir, ...)

# After (Remotion)
from src.rendering_bridge.remotion_props import (
    build_remotion_props,
    write_remotion_props,
    invoke_remotion_render,
)
props = build_remotion_props(channel_config, script, payload, audio_segments, voiceover_path)
props_path = write_remotion_props(props, output_dir, event_id)
render_result = invoke_remotion_render(
    props_path,
    output_dir / f"{event_id}_review.mp4",
)
```

---

## B.5 移行の段階的な進め方

### フェーズ B-0：準備（1 日）

1. **ゴールデン MP4 を保存**：現在の `geo_lens` の代表 1〜3 イベントで MP4 を生成し、`tests/golden/` に保存。
2. **比較指標を定義**：
   - MP4 の尺（±0.1 秒）
   - 解像度（720x1280 固定）
   - シーン数（4 で固定）
   - 各シーンの開始時刻（voiceover_segments.json と照合）
   - 音声テキスト（voiceover_segments.json の narration_text が同一）

### フェーズ B-1：Remotion プロジェクト初期化（2-3 日）

1. `remotion/` ディレクトリに Remotion プロジェクトを `npx create-video` で作成
2. `remotion/src/schema.ts` に Zod スキーマ定義
3. 現行 `_THEME`（6 テーマ）を React コンポーネントとして移植
4. Noto Sans JP などの Web フォントを `remotion/public/fonts/` に配置

### フェーズ B-2：プレースホルダ版（3-4 日）

1. `HookScene.tsx` / `SetupScene.tsx` / `TwistScene.tsx` / `PunchlineScene.tsx` を実装
2. まずは現行 `video_renderer.py` と**見た目を揃える**（グラデーション背景、下部テロップ、ナレーション表示）
3. Remotion CLI で手動レンダリング確認

### フェーズ B-3：Python ↔ Remotion 連携（2-3 日）

1. `src/rendering_bridge/remotion_props.py` 実装
2. `src/main.py` のフィーチャーフラグ：
   - `VIDEO_RENDER_BACKEND=legacy`（現行 video_renderer.py、既定）
   - `VIDEO_RENDER_BACKEND=remotion`（新実装）
3. `src/render/run_render.py` にも同フラグを追加

### フェーズ B-4：リグレッションテスト（1-2 日）

1. `tests/golden/` で保存した指標と Remotion 版の出力を比較
2. 差異があれば Remotion コンポーネントを調整
3. 許容される差異：
   - ピクセル単位の色の違い（±5%）
   - テロップフォントの微差（ヒラギノ→Noto）
4. 許容されない差異：
   - シーン数の違い
   - 尺の 0.5 秒以上の違い
   - ナレーションテキストの違い

### フェーズ B-5：切り替え（半日）

1. `.env` のデフォルトを `VIDEO_RENDER_BACKEND=remotion` に変更
2. 1 週間並行稼働して安定確認
3. 問題なければ `src/generation/video_renderer.py` を削除

### フェーズ B-6：後片付け（1 日）

1. `imageio`, `imageio-ffmpeg`, `Pillow`, `numpy` の使用箇所を確認
2. `video_renderer.py` 以外で使っていれば残す、専用なら requirements.txt から削除
3. `data/output/` の旧 MP4 ディレクトリ整理

---

# C. 全体スケジュール提案

> 日数は「集中して 1 人で作業した場合の目安」。実際は確認作業・テスト・ミーティングで 2〜3 倍に膨らみます。

## C.0 段階的立ち上げ方針（チャンネル追加の順序）

**カズヤさん確定方針（2026-04-23）：geo_lens を完全に安定稼働させてから、1 チャンネルずつ追加する。**

| Phase | 期間 | ゴール | 稼働中のチャンネル |
|---|---|---|---|
| **Phase 1** | Week 1-4 | **geo_lens の完全自動化**<br/>＋3チャンネル対応の土台を並行構築 | `geo_lens` のみ |
| **Phase 2** | Week 4-5 | `japan_athletes` を追加（YAML を書くだけで立ち上がるのが Phase 1 の成果）| `geo_lens` + `japan_athletes` |
| **Phase 3** | Week 6-7 | `k_pulse` を追加 | 3 チャンネル並行稼働 |
| **Phase 4**（Phase 3 と並列） | Week 5-7 | Remotion 移行（全チャンネルに反映）| 動画レンダリングが Remotion 経由に |

この順序が重要な理由：

- **Phase 1 は `geo_lens` の挙動を一切変えないリファクタ**に専念する。ゴールデン MP4 比較で「旧実装と同じ動画が出る」ことを厳格に検証。ここで壊れると全チャンネルに波及するため。
- **Phase 2-3 は新規 YAML 書くだけで立ち上がる状態を Phase 1 で作り込む**。コードには一切触らない理想形。
- **Phase 4（Remotion）は Phase 2-3 と並列可**。ただし Phase 1 が完了してから着手（コード基盤が動いている状態で切り替える必要）。

## C.1 推奨順序（1 日単位）

### ── Phase 1 ：geo_lens の完全自動化（Week 1-4） ──

Phase 1 のゴールは **「`geo_lens` チャンネルが現行と同じ動画を YAML 駆動で自動生成できる」** こと。
`japan_athletes` と `k_pulse` の **YAML テンプレートは Phase 1 最終日に雛形だけ用意** するが、実稼働は Phase 2-3 に回す。

#### Week 1：セキュリティ＆基盤

| Day | タスク | 確認方法 |
|---|---|---|
| 1 | **[Day 1-1]** `.gitignore` 修正 + `.venv/` 除去 ✅（2026-04-23 完了、コミット `290b117`）| `git ls-files \| grep .venv` が 0 件 |
| 1 | **[Day 1-2]** API キーローテーション | 旧キーでの Gemini 呼び出しが失敗することを確認 |
| 1 | **[Day 1-3]** ゴールデン MP4 を `tests/golden/geo_lens/` に保存 | 3 イベント分の `review.mp4` + `voiceover_segments.json` + `script.json` + `triage_scores.json` が保存されている |
| 2 | **[Day 2]** `ChannelConfig` Pydantic モデル定義（`src/channel/`）| `pytest tests/test_channel_config.py` が通る |
| 3 | **[Day 3]** `configs/base.yaml` + `configs/channels/geo_lens.yaml` 作成（**現行を再現するだけ**）| YAML ロードで現行定数と全一致 |
| 4 | **[Day 4]** `.md` プロンプトファイル化（triage / script / article / title / judge の 5 ファイル、すべて `geo_lens/` 配下）| 改行・文字数が元と完全一致 |
| 5 | **[Day 5]** `src/main.py` に `--channel-id` フラグ追加（既定 `geo_lens`、他の値はまだエラー扱い）| `python -m src.main --mode normalized --channel-id geo_lens` が通る |

#### Week 2：pipeline 分割（geo_lens 内で検証）

| Day | タスク | 確認方法 |
|---|---|---|
| 6 | **[Day 6]** `src/pipeline/` ディレクトリ作成、`_save_run_summary` を `reports.py` に移動 | 既存テスト全通過 |
| 7 | **[Day 7]** `_build_combined_candidate_pool` を `pool.py` に移動 | 既存テスト全通過 |
| 8 | **[Day 8]** `_archive_batch` を `archive.py` に移動 | 既存テスト全通過 |
| 9 | **[Day 9]** `run_from_normalized` のフェーズ関数分割（`_prepare_batch` / `_build_and_rank_events` / `_apply_filters` / `_select_slot1` / `_generate_top3` / `_finalize_and_archive`）| `test_batch_pipeline.py` が通る |
| 10 | **[Day 10]** ゴールデン MP4 でリグレッション確認（**Week 2 完了ゲート**）| 差異なしを目視＋指標比較。<br/>`geo_lens` が旧実装と同じ動画を出力 |

#### Week 3：geo_lens のスコアリング・プロンプトを YAML 駆動化

> ここが **Phase 1 の山場**。`geo_lens` の挙動を一切変えずに、ハードコード → YAML 読み込みに置き換える。
> 他チャンネル用 YAML は**まだ作らない**。

| Day | タスク | 確認方法 |
|---|---|---|
| 11 | **[Day 11]** `scoring.py` の `CATEGORY_BASE` を `channel_config.scoring.category_base` 参照に | `test_scoring.py` が通る＋ゴールデンと同じスコアが出る |
| 12 | **[Day 12]** `scoring.py` のキーワード集合（`_TECH_KW`, `_GEO_CONFLICT_KW` ほか 10 種以上）を YAML 駆動に | 同上 |
| 13 | **[Day 13]** `prompts.py` → prompt_loader 経由に。`TRIAGE_SYSTEM_PROMPT` は `configs/prompts/geo_lens/triage.md` から読む | `test_main_smoke.py` が通る |
| 14 | **[Day 14]** `script_writer.py` の `_PROMPT_TEMPLATE` を `configs/prompts/geo_lens/script.md` 化 | `test_script_writer.py` が通る |
| 15 | **[Day 15]** `cross_lang_matcher.py` の翻訳辞書を `configs/dictionaries/common.yaml` + `geo_lens.yaml` に分離 | `test_cross_lang_matcher.py` が通る |

#### Week 4：DB マイグレーション＋geo_lens 完全自動化確認＋他チャンネル雛形

| Day | タスク | 確認方法 |
|---|---|---|
| 16 | **[Day 16]** DB テーブル 6 種に `channel_id` カラム追加、`ALTER TABLE ADD COLUMN DEFAULT 'geo_lens'` マイグレーション SQL | 既存 DB を開いて `channel_id='geo_lens'` が全行にアサインされる |
| 17 | **[Day 17]** `save_job`, `upsert_recent_event_pool` ほか DB アクセス関数を `channel_id` 受け取りに変更 | `test_publish_identity.py` が通る |
| 18 | **[Day 18]** **geo_lens 完全自動化の最終確認**：3 イベントでゴールデンと完全比較。`VIDEO_RENDER_ENABLED=true` で MP4 まで確認 | 差異なし（**Phase 1 完了ゲート**）|
| 19 | **[Day 19]** `japan_athletes` / `k_pulse` の **YAML テンプレート雛形**を作成（実稼働させないで、ロードだけ通るレベル）<br/>例：`configs/channels/japan_athletes.yaml` は `category_base` と `prompts` のパスだけ書く | `ChannelConfig.load("japan_athletes")` がエラーなくロードできる |
| 20 | **[Day 20]** Phase 1 レビュー＆引継ぎドキュメント整備（Phase 2 に進む前の一呼吸）| geo_lens が 1 週間連続稼働してエラーなし |

---

### ── Phase 2 ：japan_athletes を追加（Week 4-5 の後半〜Week 5） ──

**Phase 2 のゴール：コードには一切触らず、YAML を書くだけで `japan_athletes` チャンネルを立ち上げる。**

> これが成功すれば、Phase 1 のリファクタが正しく抽象化されていたことの証明になります。
> もしここでコード修正が必要になったら、Phase 1 の抽象化が不十分なサインなので、該当箇所を Phase 1 の延長として先に直します。

| Day | タスク | 確認方法 |
|---|---|---|
| 21 | **[Day 21]** スポーツ系 RSS ソース調査・追加（ESPN, Sports Illustrated, MLB.com, 日刊スポーツ, スポニチ 等）→ `configs/sources/japan_athletes_sources.yaml` | `python -m src.ingestion.run_ingestion --channel-id japan_athletes` で記事が取れる |
| 22 | **[Day 22]** `configs/channels/japan_athletes.yaml` 本格化：<br/>・`category_base`（`sports: 95, entertainment: 70, economy: 30`）<br/>・キーワード集合（MLB 選手名、Jリーグ、WBC 等）<br/>・日英翻訳辞書に選手名・チーム名 20 件以上追加 | YAML ロード＋スコア計算で `sports` 系記事が上位に来る |
| 23 | **[Day 23]** `configs/prompts/japan_athletes/` 配下に 5 つの .md プロンプトを作成。<br/>**ナラティブパターン調整：Breaking Shock 重視**（「速報：大谷 3 号アーチ」型）、<br/>Media Critique / Geopolitics / Anti-Sontaku は封印 | プロンプト内に「忖度・地政学」の語が出ないことを grep で確認 |
| 24 | **[Day 24]** `configs/source_profiles/japan_athletes_profiles.yaml` で媒体格付け（スポーツ紙の tier 調整）| 台本生成時に引用媒体がスポーツ紙に寄る |
| 25 | **[Day 25]** 実データで 3 イベント自動生成 → 手動レビュー（台本の品質チェック）| 「スポーツニュースとしておかしくない動画」が出力される |

**Phase 2 完了ゲート：**
- [ ] `japan_athletes` が 3 日連続で動画を出力（1 日 3 本想定）
- [ ] `geo_lens` も同時稼働してエラーなし
- [ ] LLM 予算（`daily_stats.llm_calls`）がチャンネル別に集計できている

---

### ── Phase 3 ：k_pulse を追加（Week 6-7） ──

**Phase 3 のゴール：同じく YAML を書くだけで `k_pulse`（韓国エンタメ）を立ち上げる。Phase 4（Remotion）と並行実施可能。**

| Day | タスク | 確認方法 |
|---|---|---|
| 26 | **[Day 26]** 韓国エンタメ系ソース調査（Soompi, Allkpop, スポーツ韓国, 中央日報日本語版, 東亜日報日本語版, 日本側の韓流メディア等）→ `configs/sources/k_pulse_sources.yaml` | 記事が取れる |
| 27 | **[Day 27]** `configs/channels/k_pulse.yaml`：<br/>・`category_base`（`entertainment: 90, sports: 40`）<br/>・K-pop アーティスト名、ドラマ名、芸能事務所名キーワード追加 | K-pop 系記事が上位に来る |
| 28 | **[Day 28]** `configs/prompts/k_pulse/` 配下に .md プロンプトを作成。<br/>**トーンをポップ寄りに調整**：<br/>・「シニカル」「皮肉」を抑制し、「熱量」「共感」「驚き」を優先<br/>・target_enemy は「保守的な既存価値観」に限定<br/>・ナラティブパターン：Cultural Divide / Fandom Fast を中心に | プロンプトから「財務省」「日銀」「地政学」の語が消えていることを grep で確認 |
| 29 | **[Day 29]** `configs/dictionaries/k_pulse.yaml` で日韓翻訳辞書整備（韓→日を中心に 50 項目以上：アイドル名・グループ名・ドラマタイトル）| クロス言語クラスタリングで日韓ペアが出る |
| 30 | **[Day 30]** 実データで 3 イベント自動生成 → 手動レビュー | 「K-pop 好きが見て違和感のない動画」が出力される |

**Phase 3 完了ゲート：**
- [ ] 3 チャンネル（geo_lens / japan_athletes / k_pulse）が並行稼働
- [ ] 合計で 1 日 15 本（3 ch × 5 本）以内に収まり、LLM 予算超過なし
- [ ] 各チャンネルの `run_summary.json` で `channel_id` が正しく記録されている

---

### ── Phase 4 ：Remotion 移行（Week 5-7、Phase 2-3 と並行） ──

> Phase 2-3 と並行して進行可能。ただし **Phase 1 完了（Day 18 ゲート通過）が前提**。
> 切り替えは全チャンネル同時（フィーチャーフラグでの段階切替）。

| Day | タスク | 確認方法 |
|---|---|---|
| Week5 前半 | **[Day 31-32]** `remotion/` プロジェクト初期化、Zod スキーマ定義、Noto Sans JP 配置 | `npx remotion preview` が起動 |
| Week5 後半 | **[Day 33-34]** テーマ（6 種）を React コンポーネントに移植 | プレビューで全テーマ表示確認 |
| Week6 前半 | **[Day 35-36]** Scene コンポーネント（Hook / Setup / Twist / Punchline）実装 | プレビューで 4 ブロック表示 |
| Week6 後半 | **[Day 37]** `src/rendering_bridge/remotion_props.py` 実装 | Python から props.json が書ける |
| Week6 後半 | **[Day 38]** `src/main.py` にフィーチャーフラグ `VIDEO_RENDER_BACKEND=legacy|remotion` 追加 | 旧経路で従来通り動く |
| Week7 前半 | **[Day 39]** Remotion レンダリング E2E（3 チャンネル分）| 3 チャンネルで MP4 が生成される |
| Week7 前半 | **[Day 40-41]** ゴールデン MP4 とリグレッション比較、微調整 | 尺・シーン数・ナレーションが一致 |
| Week7 後半 | **[Day 42-43]** 並行稼働（`legacy` と `remotion` を両方日次実行）| 両方の MP4 が出る |
| Week7 後半 | **[Day 44]** `VIDEO_RENDER_BACKEND` の既定を `remotion` に切替 | 日次バッチが Remotion だけで完走 |
| Week7 最終 | **[Day 45]** `video_renderer.py` 削除、`requirements.txt` から `imageio` / `Pillow` 整理 | 最終確認、すべてのチャンネルで正常稼働 |

---

## C.2 各ステップでの動作確認方法

### 汎用チェック（各 Day 終わりに実行）

```bash
# 1. 既存テスト全通過
pytest tests/ -v

# 2. サンプルモードで動作確認
python -m src.main --mode sample

# 3. 差分チェック（リファクタ前後で同じ出力か）
diff <(cat data/golden/art-xxx_script.json) <(cat data/output/art-xxx_script.json)
```

### リファクタ中の各フェーズ固有のチェック

**Phase 1-2（ChannelConfig）**
```bash
python -c "from src.channel.config import ChannelConfig; c = ChannelConfig.load('geo_lens'); print(c.scoring.category_base)"
# → {'economy': 85.0, 'politics': 80.0, ...} が表示される
```

**Phase 5（YAML 駆動化後）**
```bash
# geo_lens.yaml の category_base を編集して、スコアが変わることを確認
# （sports を 90.0 に変えると、スポーツ記事が上位に来る）
```

**Phase B-4（Remotion リグレッション）**
```bash
# ゴールデン比較スクリプト
python tools/compare_golden_mp4.py \
    --golden tests/golden/art-xxx_review.mp4 \
    --new    data/output/art-xxx_review.mp4
```

---

## C.3 リグレッションテスト設計

### C.3.1 何を比較するか

| 項目 | 許容差 | 理由 |
|---|---|---|
| MP4 の総尺 | ±0.5 秒 | FFmpeg エンコード誤差 |
| 解像度 | 完全一致（720x1280）| 絶対 |
| シーン数 | 完全一致（4）| 絶対 |
| 各シーン開始時刻 | ±0.3 秒 | 音声長の丸め誤差 |
| 音声テキスト | 完全一致 | 台本ロジックに変更なし |
| 音声の波形 SHA256 | 完全一致（Remotion 移行時のみ、移行後は変更される可能性）| 音声合成はまだ Python 側 |
| ナレーション読み上げ内容 | 完全一致 | voiceover_segments.json で比較 |
| ScoredEvent の最終選出 | 完全一致 | triage_scores.json で比較 |
| VideoScript の director_thought, sections | 完全一致 | script.json で比較（LLM 再生成は避ける。テスト時は固定シード or モック）|

### C.3.2 スナップショットテスト実装例

```python
# tests/test_regression_geo_lens.py

import json
from pathlib import Path

import pytest

GOLDEN_DIR = Path("tests/golden/geo_lens")

@pytest.mark.parametrize("event_id", ["art-sample001", "art-sample002"])
def test_script_regression(event_id):
    """geo_lens の台本が YAML 化前後で同一であることを確認。"""
    golden = json.loads((GOLDEN_DIR / f"{event_id}_script.json").read_text())
    new    = json.loads(Path(f"data/output/{event_id}_script.json").read_text())
    # sections の heading 順序と文字数境界内か
    assert [s["heading"] for s in new["sections"]] == [s["heading"] for s in golden["sections"]]
    for g, n in zip(golden["sections"], new["sections"]):
        assert g["heading"] == n["heading"]
        # 文字数は LLM の出力揺らぎで変動するので、完全一致ではなく bounds 確認
        # 完全一致させたい場合は LLM 呼び出しをモックする
```

### C.3.3 LLM 非決定性への対処

LLM は同じプロンプトでも呼び出しごとに違う出力を返す可能性があります。リグレッションテストでは：

1. **推奨**：LLM 呼び出しをモック化（`tests/test_main_smoke.py` で既に部分的に実施）。
2. **固定モデル・temperature=0** で安定性を上げる（完全決定論ではないが、差分は小さくなる）。
3. **構造のみ検証**：section 数、heading、duration の合計が一致することを確認。本文の完全一致は求めない。

---

# D. リスクと対策

## D.1 マルチチャンネル化のリスク

| リスク | 影響 | 対策 |
|---|---|---|
| YAML 構文エラーで起動失敗 | 全チャンネル停止 | CI で YAML lint。`pydantic.ValidationError` でわかりやすいエラー。 |
| `geo_lens` の挙動が変わる（リグレッション） | 現行ユーザー影響 | フェーズ毎にゴールデン比較。差分があれば段階戻し。 |
| DB マイグレーションで既存データ破損 | 過去の履歴喪失 | バックアップ必須。`ALTER TABLE ADD COLUMN DEFAULT 'geo_lens'` で既存行は `geo_lens` に自動アサイン。 |
| 1 日の LLM 予算が 3 チャンネル分になる | Gemini クォータ超過 | チャンネルごとに独立した日次予算。`daily_stats` テーブルで `channel_id` 別に集計。 |
| プロンプト品質のばらつき | スポーツ・K-pop 動画が品質低下 | まず `geo_lens` を完全再現し、`japan_athletes` / `k_pulse` は段階公開（フィーチャーフラグで dry-run）。 |
| 共通コードに「if channel_id == 'japan_athletes'」が増える | 保守不能 | **コードで分岐せず、YAML で表現できる範囲に収める**。どうしても必要ならストラテジーパターンでクラス分割。 |
| RSS ソース追加でクロス言語辞書が足りず同一イベント認識が落ちる | クラスタリング失敗 | `japan_athletes` 向けに辞書を増強（MLB 選手名、チーム名など）。 |

## D.2 Remotion 移行のリスク

| リスク | 影響 | 対策 |
|---|---|---|
| Node.js + React 環境依存 | デプロイ複雑化 | README に `nvm use 20` 等を明記。Docker 化を検討。 |
| Remotion レンダリングが Python より遅い | 日次バッチ時間増大 | 並列レンダリング（`--concurrency=N`）。Chromium プリウォーム。 |
| フォント差で見た目が変わる | デザイン一貫性の変化 | Noto Sans JP を選定してデザイン確認。古い視覚を捨てる覚悟も必要。 |
| macOS `say` の音声は変わらないが、Remotion 連携で音ズレ | 動画品質低下 | Remotion 側で `<Audio>` の `startFrom` / `trimBefore` を正確に設定。`voiceover_segments.json` の timing を厳密に守る。 |
| Python から Node.js プロセスを起動する subprocess 管理 | エラーハンドリング複雑化 | `timeout=600` 秒、stderr を `render_manifest.json` に記録。 |
| Remotion の依存（Chromium）を CI で用意 | CI 失敗 | GitHub Actions なら `ubuntu-latest` に Chromium がデフォルト。Remotion 公式のセットアップガイドに従う。 |

## D.3 全体リスク

| リスク | 影響 | 対策 |
|---|---|---|
| リファクタ中にバグで本番動画が出なくなる | 日次配信停止 | フィーチャーフラグで旧経路を常に保持。「切り戻し可能」を各 Phase の終了条件にする。 |
| 5 週間 7 週間のリファクタ中に新しい Gemini モデルが出る | 対応漏れ | 環境変数でモデル名を外出ししているので `.env` 更新だけで対応。 |
| スケジュールが他業務で押す | 中途半端な状態で放置 | Phase 1-2 完了時点で **途中終了しても `geo_lens` は動く** よう設計。後続 Phase は常に optional。 |
| 素人エンジニアの学習コスト | 作業停滞 | このドキュメント＋REFACTORING_PLAN に沿って 1 Day 単位で進める。詰まったら ARCHITECTURE.md で該当箇所を復習。 |

---

## 📋 最終チェックリスト（Phase 完了判定）

### Phase 1（Week 1-4 完了時）：geo_lens の完全自動化
- [x] `.venv/` が Git 管理外 ✅（2026-04-23 完了、コミット `290b117`）
- [ ] API キーがローテーション済み
- [ ] ゴールデン MP4 を `tests/golden/geo_lens/` に保存済み
- [ ] `ChannelConfig` でロード可能（`ChannelConfig.load("geo_lens")` が通る）
- [ ] `src/pipeline/` 配下に分割完了、`main.py` が 500 行以下
- [ ] `scoring.py` / `prompts.py` / `cross_lang_matcher.py` の辞書が YAML 駆動
- [ ] DB に `channel_id` カラム追加済み
- [ ] **`geo_lens` が 1 週間連続で動画を自動生成してエラーなし（Phase 1 完了ゲート）**
- [ ] `japan_athletes` / `k_pulse` の YAML テンプレート雛形が存在（ロードだけ通る）

### Phase 2（Week 4-5 完了時）：japan_athletes 稼働
- [ ] スポーツ系 RSS ソース（最低 5 媒体）が `japan_athletes_sources.yaml` に追加済み
- [ ] `japan_athletes.yaml` のスコアリング設定で `sports` 系記事が上位に来る
- [ ] スポーツ向けプロンプト（Breaking Shock 重視）が `configs/prompts/japan_athletes/` に完成
- [ ] **`japan_athletes` が 3 日連続で動画を出力**
- [ ] 2 チャンネル並行稼働で LLM 予算超過なし
- [ ] `daily_stats` が `channel_id` 別に集計できている

### Phase 3（Week 6-7 完了時）：k_pulse 稼働
- [ ] 韓国エンタメ系ソース（最低 5 媒体）が `k_pulse_sources.yaml` に追加済み
- [ ] `k_pulse.yaml` のスコアリング設定で `entertainment` 系記事が上位に来る
- [ ] ポップ寄りプロンプトが `configs/prompts/k_pulse/` に完成（シニカル語彙の排除を確認）
- [ ] 日韓翻訳辞書（50 項目以上）が `configs/dictionaries/k_pulse.yaml` に整備
- [ ] **3 チャンネル並行稼働（1 日最大 15 本）**
- [ ] LLM 予算・公開数がチャンネル別に独立制御

### Phase 4（Week 5-7、Phase 2-3 と並列）：Remotion 移行
- [ ] Remotion プロジェクトで全 3 チャンネルの動画が生成できる
- [ ] `VIDEO_RENDER_BACKEND=remotion` で日次バッチが 1 週間以上安定稼働
- [ ] `video_renderer.py` が削除済み
- [ ] `requirements.txt` から `imageio`, `Pillow` 等が整理済み
- [ ] ゴールデン MP4 とのリグレッション比較で許容範囲内

---

*最終更新: 2026-04-23 / 作成者: Claude*
