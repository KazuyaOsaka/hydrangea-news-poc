# CLAUDE.md — Hydrangea News PoC Context for Claude Code

> このファイルはリポジトリルートに配置し、Claude Code がプロジェクト全体の文脈を理解するための情報源として使用する。
> 各実装セッションで Claude Code は最初にこのファイルを参照すること。

---

## プロジェクト概要

**Hydrangea News PoC** は海外RSS（19媒体）から日本未報道のニュースを発掘し、
TikTok/YouTube Shorts 向けの縦型ショート動画を自動生成するシステム。

3チャンネル体制を計画（Phase 1 は `geo_lens` のみ稼働）：
- `geo_lens` — Geopolitical Lens（政治・経済の地政学解説）
- `japan_athletes` — Japan Athletes Abroad（海外で戦う日本人スポーツ選手、Phase 2）
- `k_pulse` — K-Pulse（韓国エンタメ、Phase 3）

ブランド方針：ReHacQ・東洋経済レベルの知性、シニカル・ダーク・シネマティック、陰謀論禁止。

---

## Hydrangea Batch Protocol

全バッチで `docs/BATCH_PROTOCOL.md` のプロトコルに従うこと。

各バッチ完了時の必須タスク:

1. **DECISION_LOG.md** に本バッチの決定エントリを追加 (Task 1)
2. **FUTURE_WORK.md** の完了済み移動 + 新規課題追加 (Task 2)
3. 完了レポートに上記更新内容を明記 (Task 3)

これらは省略不可。詳細・テンプレート・不変原則 5 つは
`docs/BATCH_PROTOCOL.md` を参照すること。

---

## 必読ドキュメント

実装作業の前に必ず以下を確認：

1. **`docs/ANALYSIS_LAYER_DESIGN_v1.1.md`** — 分析レイヤー設計書（実装の正典）
2. **`docs/CLAUDE_CODE_INSTRUCTIONS.md`** — バッチ分割された実装指示書
3. **`docs/ARCHITECTURE.md`** — 既存システムのアーキテクチャ
4. **`docs/TECH_DEBT.md`** — 既知の技術的負債
5. **`docs/REFACTORING_PLAN.md`** — 中長期のリファクタ計画
6. **`docs/DECISION_LOG.md`** — Phase 1.5 / Phase A.5-1 の意思決定履歴（なぜこの設計か）
7. **`docs/BATCH_PROTOCOL.md`** — 全バッチ共通の必須タスク（DECISION_LOG / FUTURE_WORK 更新の強制化）

---

## コーディング規約

- **言語**: Python 3.11
- **データモデル**: Pydantic v2
- **テストフレームワーク**: pytest
- **命名規則**:
  - ファイル名・関数名: `snake_case`
  - クラス名: `PascalCase`
  - 定数: `UPPER_SNAKE_CASE`
  - プライベート: `_underscore_prefix`
- **インポート順**:
  1. 標準ライブラリ
  2. サードパーティ
  3. プロジェクト内（`from src.shared import ...`）
- **型ヒント必須**（特に公開関数のシグネチャ）
- **docstring**: 関数・クラスの目的を1〜3行で記述

---

## 触っちゃダメリスト

以下のファイル・ディレクトリは **絶対に変更しない**：

### 完全禁止
- `src/generation/audio_renderer.py` — macOS sayの仮実装、後で完全置換予定
- `src/generation/video_renderer.py` — Pillow+FFmpeg、Remotion移行で破棄予定
- `src/ingestion/rss_fetcher.py` — RSS取り込みは安定済み
- `src/ingestion/normalizer.py` — 正規化ロジックは安定済み
- `src/ingestion/event_builder.py` — クラスタリングは複雑、触ると壊れる
- `src/ingestion/cross_lang_matcher.py` — 日英照合は複雑、触ると壊れる
- `src/triage/scoring.py` — 既存スコアリング、参照のみOK
- `src/triage/coherence_gate.py` — 既存判定、参照のみOK

### 制限付き変更可
- `src/main.py` — 分析レイヤー組込のみ可、既存ロジックは触らない
- `src/shared/models.py` — フィールド追加・新モデル追加のみ、既存フィールド変更禁止
- `src/storage/db.py` — テーブル追加のみ、既存テーブル変更禁止
- `src/triage/gemini_judge.py` — 入力に `analysis_result` を受け取る改修のみ
- `src/generation/script_writer.py` — 分析レイヤー入力対応の改修のみ

### 自由に変更・追加可
- `src/analysis/` 配下（新規ディレクトリ）
- `configs/channels.yaml`（新規）
- `configs/entity_dictionary.yaml`（新規）
- `configs/prompts/analysis/` 配下（新規）
- `tests/test_*.py` の新規ファイル

**触ってはいけないファイルを変更する必要があると判断した場合**：
→ 実装を停止し、完了レポートに「変更要望」として記載すること。勝手に変更しない。

---

## 判断ルール（重要）

実装中に不明点が出た場合、**人間に質問せず、自分で判断して進める**。

判断の優先順位：

1. **`docs/ANALYSIS_LAYER_DESIGN_v1.1.md` の仕様を最優先**
2. 設計書に明記がない場合 → **既存コードのパターンに揃える**
3. 既存パターンも不明な場合 → **最も保守的（既存に影響少ない）選択肢**を取る

完了レポートで「判断した内容」を必ず報告すること。

### 例外: 実装を停止して報告すべきケース

以下の場合のみ作業を中断して人間に報告：
- 触ってはいけないファイルの変更が必要と判断した場合
- 設計書から大きく逸脱する判断が必要な場合（新規大規模機能の追加等）
- 既存テストの本質的な書き換えが必要な場合
- 環境構築・依存関係の問題で実装が物理的に進められない場合

それ以外は **質問せず判断、完了後に報告** が原則。

---

## ガードレール

### 1. ブランチ運用

各バッチごとに必ずブランチを切る：

```bash
git checkout main
git pull
git checkout -b feature/analysis-layer-batch{N}
```

作業はブランチ内で完結させる。main へのマージは人間が行う。

### 2. 既存テストの保護

**作業前**: `pytest tests/ -v` で全テスト通過を確認。
**作業中**: 新規テストを追加しながら実装（TDD推奨）。
**作業後**: `pytest tests/ -v` で全テスト通過を再確認。

既存テストが失敗したら：
- 既存ロジックの変更で失敗 → ロジックを元に戻す（既存挙動の維持を優先）
- テスト自体が古い場合 → 完了レポートで「テスト更新が必要」と報告（勝手に書き換えない）

### 3. フィーチャーフラグ運用

分析レイヤーは `ANALYSIS_LAYER_ENABLED` 環境変数でON/OFF切替：

```bash
ANALYSIS_LAYER_ENABLED=false  # デフォルト、既存パイプライン動作
ANALYSIS_LAYER_ENABLED=true   # 分析レイヤー有効
```

**`ANALYSIS_LAYER_ENABLED=false` で従来通り動作することを毎バッチ確認すること。**

### 4. ロールバック可能性

各バッチは独立してロールバック可能であること：
- ブランチ単位で `git reset --hard` できる構造
- main へのマージ後も問題発生時はフィーチャーフラグでオフ可能

---

## LLM 呼び出し方針

### 既存 LLMClient 抽象を活用

新規実装でも必ず `src/llm/base.py` の `LLMClient` インターフェース経由で呼び出す。
直接 `google.generativeai` を import してはいけない。

### 役割別クライアント

`src/llm/factory.py` の `create_client(role=...)` を使う：

```python
from src.llm.factory import create_analysis_client

client = create_analysis_client()
result = client.generate(prompt)
```

### 予算管理

LLM 呼び出しは既存の `src/budget.py` を経由。
チャンネル別の独立予算管理に対応すること（ChannelConfig.budget が将来追加される可能性）。

### Tier フォールバック

Gemini Tier 1 (Flash Lite) → Tier 2 → Tier 3 → Tier 4 のフォールバックは既存実装あり。
新規呼び出しでもこのフォールバックを使う（独自実装しない）。

---

## プロンプト管理

LLM プロンプトは **必ず外部 .md ファイルに分離**：

```
configs/prompts/analysis/
├── geo_lens/
│   ├── perspective_select_and_verify.md
│   ├── multi_angle_analysis.md
│   └── insights_extract.md
├── japan_athletes/  # Phase 2 用、Phase 1 では雛形のみ
└── k_pulse/         # Phase 3 用、Phase 1 では雛形のみ
```

Python コード内にプロンプト文字列を直書きしない。
`load_prompt(channel_id, prompt_name)` のようなヘルパで読み込む。

---

## テスト方針

### ユニットテスト

- **対象**: 個別関数・クラス
- **LLMモック必須**: 実LLM呼び出しはテストで行わない
- **モックフィクスチャ**: `tests/fixtures/llm_responses/*.json` に保存
- **カバレッジ目標**: 主要関数 80% 以上

### 統合テスト

- **対象**: Step 0〜6 の全フロー
- **対象**: main.py との組込
- **LLMモック使用**: 決定的な動作を保証

### E2E テスト

- 既存の `test_main_smoke.py` を拡張
- ANALYSIS_LAYER_ENABLED=true で台本生成までエラーなく動作

---

## 完了レポートフォーマット

各バッチ完了時に以下のフォーマットでレポートを出力：

```markdown
## Batch {N} 完了レポート

### 実装ファイル一覧
- 新規作成: 
  - `src/analysis/recency_guard.py` (XX 行)
  - ...
- 変更:
  - `src/shared/models.py` (+XX 行, -X 行)
  - ...

### テスト結果
- pytest tests/: X passed, Y failed
- 既存テスト影響: なし / あり（詳細）
- 新規テスト追加: X 個

### フィーチャーフラグ確認
- ANALYSIS_LAYER_ENABLED=false で main.py の従来動作: OK / NG
- ANALYSIS_LAYER_ENABLED=true での新ルート動作: OK / NG / 該当なし

### 自分で判断した内容
- 判断1: 〇〇について、設計書に明記なし → 既存パターンに従って XX を採用
- 判断2: ...

### 触ってはいけないファイルへの変更要望
- なし / あり（理由）

### 次バッチへの引継ぎ事項
- 〇〇のテストが未完了、Batch {N+1} で対応
- ...

### 環境構築・依存追加
- requirements.txt 追加: なし / あり（パッケージ名）
- 環境変数追加: なし / あり（ANALYSIS_LAYER_ENABLED 等）
```

---

## 将来対応リストの運用

各バッチ完了時、以下を必ず実施すること:

1. 完了レポートの末尾に「FUTURE_WORK.md への追加項目」セクションを設ける
2. バッチ実装中に「今やらないが将来やるべき」と判断した項目があれば、`docs/FUTURE_WORK.md` の適切な緊急度セクションに追加する
3. バッチ完了時に対応した既存の FUTURE_WORK 項目があれば、「完了済み」セクションに移動する

判断基準:
- 緊急度 高: 次のフェーズ（次の数バッチ以内）で必ず対応すべき
- 緊急度 中: 実運用データ収集後に判断、または別バッチで計画的に対応
- 緊急度 低: 時間ある時に検討、Phase 完了後の整理対象

新規項目の記載フォーマット:
- **タイトル** (発生バッチ)
  - 背景: なぜこれが必要か
  - 対応案: どう対応するか
  - 検討時期: いつ判断するか
  - 関連ファイル: 影響を受けるファイル

---

## FUTURE_WORK.md のレビュータイミング

形骸化防止のため、以下のタイミングで FUTURE_WORK.md を見直すことが推奨される:

### 定期トリガー
- 月初（毎月1日）

### イベントトリガー
- 新しい Phase の開始前
- 主要バッチ完了直後
- カズヤが「次何やる？」と問うたタイミング
- 1週間以上 FUTURE_WORK.md が参照されていないと気づいた時

### レビュー時の確認項目
- [ ] 緊急度 高 で 1ヶ月以上放置されている項目はあるか？（あれば対応バッチを計画）
- [ ] 緊急度の更新が必要な項目はあるか？（高→中、中→低 など）
- [ ] 既に対応済みなのに「完了済み」に移動していない項目はあるか？
- [ ] 新規 Phase に向けて追加すべき項目はあるか？
- [ ] 不要になった項目はあるか？（削除）

このレビュー自体も FUTURE_WORK.md の項目として登録されている（自己参照型管理）。

---

## 困った時の対処

### Gemini API のレート制限・エラー

- 429/503 エラー → 既存の `src/llm/retry.py` のリトライロジックに任せる
- 独自リトライを実装しない

### 既存テストが意味不明な理由で落ちる

- 一旦 `git stash` して `pytest tests/` を実行
- 落ちなければ自分の変更が原因
- 落ちるなら既存の問題、完了レポートで報告

### 設計書に書いてない仕様の判断

- 設計書 v1.1 の精神（Evidence-Grounded、量より質、既存破壊しない）に沿って判断
- 完了レポートで判断内容を必ず報告

---

## ファイル配置（実装後の最終形）

```
hydrangea-news-poc/
├── CLAUDE.md                            # このファイル
├── docs/
│   ├── ANALYSIS_LAYER_DESIGN_v1.1.md    # 設計書（正典）
│   ├── CLAUDE_CODE_INSTRUCTIONS.md      # バッチ実装指示書
│   ├── ARCHITECTURE.md                  # 既存
│   ├── TECH_DEBT.md                     # 既存
│   └── REFACTORING_PLAN.md              # 既存
├── src/
│   ├── analysis/                        # ★新規ディレクトリ
│   │   ├── __init__.py
│   │   ├── analysis_engine.py
│   │   ├── perspective_extractor.py
│   │   ├── context_builder.py
│   │   ├── perspective_selector.py
│   │   ├── multi_angle_analyzer.py
│   │   ├── insight_extractor.py
│   │   ├── duration_profile_selector.py
│   │   ├── recency_guard.py
│   │   └── entity_extractor.py
│   ├── shared/
│   │   └── models.py                    # 拡張のみ
│   ├── generation/
│   │   └── script_writer.py             # 入力対応改修のみ
│   ├── storage/
│   │   └── db.py                        # テーブル追加のみ
│   └── main.py                          # 分析レイヤー組込のみ
├── configs/
│   ├── channels.yaml                    # ★新規
│   ├── entity_dictionary.yaml           # ★新規
│   └── prompts/
│       └── analysis/                    # ★新規
│           ├── geo_lens/
│           ├── japan_athletes/
│           └── k_pulse/
└── tests/
    ├── test_channel_config.py           # ★新規
    ├── test_models_extension.py         # ★新規
    ├── test_entity_extractor.py         # ★新規
    ├── test_recency_guard.py            # ★新規
    ├── test_perspective_extractor.py    # ★新規
    ├── test_context_builder.py          # ★新規
    ├── test_perspective_selector.py     # ★新規
    ├── test_multi_angle_analyzer.py     # ★新規
    ├── test_insight_extractor.py        # ★新規
    ├── test_duration_profile_selector.py # ★新規
    ├── test_analysis_engine.py          # ★新規
    └── test_main_with_analysis.py       # ★新規
```

---

## バージョン情報

- 文書バージョン: v1.0
- 対応する設計書: `docs/ANALYSIS_LAYER_DESIGN_v1.1.md`
- 最終更新: 2026-04-25

---

*このファイルは Hydrangea News PoC のメンテナーが管理する。Claude Code はこのファイルを参照するが、勝手に編集しない。*
