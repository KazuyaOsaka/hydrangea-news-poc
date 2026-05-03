# CLAUDE.md — Claude Code 振る舞い指針

最終更新: 2026-05-03 (F-doc-cleanup)

> このファイルは Claude Code がリポジトリで作業する際の **振る舞い指針** に
> 集約されている。プロジェクト概要・現フェーズ・不変原則 5 つ・触ってよい /
> 触ってはいけない領域は重複排除のため、`docs/CURRENT_STATE.md` /
> `docs/BATCH_PROTOCOL.md` を **正本** として参照すること。

---

## 必読ドキュメント (この順序で参照)

新規バッチ着手時は以下を必ず参照すること。1〜2 が **正本**、3〜6 は補助情報源。

1. **`docs/CURRENT_STATE.md`** ★最優先 — プロジェクトの「今この瞬間の
   スナップショット」。main HEAD / Phase / 不変原則 5 つ / 触ってよい・ダメ領域 /
   次バッチ候補等の最新状態。バッチ完了時に Claude Code が全置換更新する
   (BATCH_PROTOCOL Task 5)。
2. **`docs/BATCH_PROTOCOL.md`** — 全バッチ共通の必須タスク (Task 1-5)、
   不変原則 5 つの正本、拡張性差し込み判断ルールが集約。
3. **`docs/DECISION_LOG.md`** — 過去の意思決定の経緯 (時系列、なぜこの設計か)。
4. **`docs/FUTURE_WORK.md`** — 残課題リスト (緊急度別)。
5. **`docs/DISCUSSION_NOTES.md`** — 議論中の未確定メモ
   (バッチ完了時に再評価 → DECISION_LOG / FUTURE_WORK へ昇格)。
6. **`docs/ARCHITECTURE.md`** — システム全体像 (参考)。

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
  3. プロジェクト内 (`from src.shared import ...`)
- **型ヒント必須** (特に公開関数のシグネチャ)
- **docstring**: 関数・クラスの目的を 1〜3 行で記述

---

## 判断ルール

実装中に不明点が出た場合、**人間に質問せず、自分で判断して進める**。

判断の優先順位:

1. **`docs/CURRENT_STATE.md` / `docs/BATCH_PROTOCOL.md` の不変原則 5 つを最優先**
2. 不変原則に反しない範囲で、設計書 (`docs/ANALYSIS_LAYER_DESIGN_v1.1.md` /
   `docs/EDITORIAL_MISSION_FILTER_DESIGN.md` 等) の仕様を尊重
3. 設計書に明記がない場合 → **既存コードのパターンに揃える**
4. 既存パターンも不明な場合 → **最も保守的 (既存に影響少ない) 選択肢** を取る

完了レポートで「判断した内容」を必ず報告すること。

### 例外: 実装を停止して報告すべきケース

以下の場合のみ作業を中断して人間に報告:

- 不変原則 5 つに違反する変更が必要と判断した場合
- 設計書から大きく逸脱する判断が必要な場合 (新規大規模機能の追加等)
- 既存テストの本質的な書き換えが必要な場合
- 環境構築・依存関係の問題で実装が物理的に進められない場合

それ以外は **質問せず判断、完了後に報告** が原則。

---

## ガードレール

### 1. ブランチ運用

各バッチごとに必ずブランチを切る:

```bash
git checkout main
git pull
git checkout -b feature/{バッチ名}
```

作業はブランチ内で完結させる。main へのマージは人間が行う。

### 2. 既存テストの保護

- **作業前**: `pytest tests/ -v` で全テスト通過 (baseline 1315 passed) を確認
- **作業中**: 新規テストを追加しながら実装 (TDD 推奨)
- **作業後**: `pytest tests/ -v` で全テスト通過を再確認、baseline 1315 passed を維持

既存テストが失敗した場合:
- 既存ロジックの変更で失敗 → ロジックを元に戻す (既存挙動の維持を優先)
- テスト自体が古い場合 → 完了レポートで「テスト更新が必要」と報告
  (勝手に書き換えない)

### 3. ロールバック可能性

各バッチは独立してロールバック可能であること:
- ブランチ単位で `git reset --hard` できる構造
- main へのマージ後も問題発生時はフィーチャーフラグでオフ可能

---

## LLM 呼び出し方針

### 既存 LLMClient 抽象を活用

新規実装でも必ず `src/llm/base.py` の `LLMClient` インターフェース経由で呼び出す。
直接 `google.generativeai` を import してはいけない。

### 役割別クライアント

`src/llm/factory.py` の `create_client(role=...)` を使う:

```python
from src.llm.factory import create_analysis_client

client = create_analysis_client()
result = client.generate(prompt)
```

### 予算管理

LLM 呼び出しは既存の `src/budget.py` を経由。
チャンネル別の独立予算管理に対応すること
(ChannelConfig.budget が将来追加される可能性)。

### Tier フォールバック

Gemini Tier 1 (Flash Lite) → Tier 2 → Tier 3 → Tier 4 のフォールバックは
既存実装あり。新規呼び出しでもこのフォールバックを使う (独自実装しない)。

---

## プロンプト管理

LLM プロンプトは **必ず外部 .md ファイルに分離**:

```
configs/prompts/analysis/
├── geo_lens/
│   ├── perspective_select_and_verify.md
│   ├── multi_angle_analysis.md
│   ├── insights_extract.md
│   └── script_with_analysis.md  # 主戦場
├── japan_athletes/  # Phase 2 用、Phase 1 では雛形のみ
└── k_pulse/         # Phase 3 用、Phase 1 では雛形のみ
```

Python コード内にプロンプト文字列を直書きしない。
`load_prompt(channel_id, prompt_name)` のようなヘルパで読み込む。

---

## テスト方針

### ユニットテスト

- **対象**: 個別関数・クラス
- **LLM モック必須**: 実 LLM 呼び出しはテストで行わない
- **モックフィクスチャ**: `tests/fixtures/llm_responses/*.json` に保存
- **カバレッジ目標**: 主要関数 80% 以上

### 統合テスト

- **対象**: Step 0〜6 の全フロー、main.py との組込
- **LLM モック使用**: 決定的な動作を保証

### E2E テスト

- 既存の `test_main_smoke.py` を拡張
- パイプライン全体が台本生成までエラーなく動作することを確認

---

## 完了レポートフォーマット

各バッチ完了時に以下のフォーマットでレポートを出力:

```markdown
## Batch {N} 完了レポート

### 実装ファイル一覧
- 新規作成:
  - `src/triage/jp_coverage_verifier.py` (XX 行)
  - ...
- 変更:
  - `src/shared/models.py` (+XX 行, -X 行)
  - ...

### テスト結果
- pytest tests/: X passed, Y failed
- 既存テスト影響: なし / あり (詳細)
- 新規テスト追加: X 個

### 自分で判断した内容
- 判断 1: 〇〇について、設計書に明記なし → 既存パターンに従って XX を採用
- 判断 2: ...

### 不変原則違反 / 触ってはいけないファイルへの変更要望
- なし / あり (理由)

### BATCH_PROTOCOL Task 1-5 実施結果
- Task 1 (DECISION_LOG): 追加エントリ要約
- Task 2 (FUTURE_WORK): 完了済み移動 / 新規追加リスト
- Task 4 (DISCUSSION_NOTES): 新規追加 / 既存再評価結果
- Task 5 (CURRENT_STATE): 全置換更新の差分概要

### 次バッチへの引継ぎ事項
- 〇〇のテストが未完了、Batch {N+1} で対応
- ...

### 環境構築・依存追加
- requirements.txt 追加: なし / あり (パッケージ名)
- 環境変数追加: なし / あり (変数名)
```

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

- Hydrangea の哲学
  (Evidence-Grounded、量より質、既存破壊しない、対症療法じゃなくて根本治療) に
  沿って判断
- 完了レポートで判断内容を必ず報告

---

## 重要な参照 (重複排除のための導線)

| 知りたいこと | 参照先 |
|---|---|
| プロジェクト概要・ミッション | `docs/CURRENT_STATE.md` |
| 現フェーズ・次バッチ候補 | `docs/CURRENT_STATE.md` |
| 不変原則 5 つの正本 | `docs/BATCH_PROTOCOL.md` |
| 触ってよい / 触ってはいけない領域 | `docs/CURRENT_STATE.md` |
| バッチ完了時の必須タスク (Task 1-5) | `docs/BATCH_PROTOCOL.md` |
| 拡張性差し込み判断ルール | `docs/BATCH_PROTOCOL.md` |
| 過去の意思決定の経緯 | `docs/DECISION_LOG.md` |
| 残課題リスト | `docs/FUTURE_WORK.md` |
| 議論中の未確定メモ | `docs/DISCUSSION_NOTES.md` |
| アーキテクチャ全体像 | `docs/ARCHITECTURE.md` |
| 技術的負債リスト | `docs/TECH_DEBT.md` |
| リファクタ計画 (歴史的記録) | `docs/REFACTORING_PLAN.md` |

---

*このファイルは Hydrangea News PoC のメンテナーが管理する。
F-doc-cleanup (2026-05-03) で全面書き直し:
プロジェクト概要・不変原則・触ってはいけないリスト等の重複を完全排除し、
責務を「Claude Code の振る舞い指針」に集約した。
過去版 (v1.0、2026-04-25 分析レイヤー実装期) は git 履歴を参照。*
