# CLAUDE.md — Claude Code 振る舞い指針

最終更新: 2026-05-27 (F-docs-update-chatgpt-round2-and-error10 — クラウド誤り 10 明文化。
旧: 2026-05-08 F-particular-angle-redesign-extension — クラウド誤り 9 追加)

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

### 4. secrets の表示ガード (F-editorial-guardian-corroboration / 2026-06-10 追加)

- `.env` 等の secrets ファイルを表示する際は値をマスクする (キー名のみ表示、例: `grep -oE '^[A-Z_]+' .env`)。API キー・トークン等の実値を端末出力・レポート・ログに出さない。

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

## クラウド誤り (再発防止リマインダ、正本: docs/DISCUSSION_NOTES.md)

過去のクラウドインスタンスが繰り返してきた典型的な誤りを、再発防止のため
本セクションに集約する。各誤りの詳細 (背景・経緯・防止策) は
`docs/DISCUSSION_NOTES.md` の該当エントリを正本として参照すること
(クラウド誤り 1-7 は 2026-05-02 〜 2026-05-03 に登録、誤り 9 は 2026-05-08 に登録、
誤り 10 は 2026-05-25 に DISCUSSION_NOTES に登録 → 2026-05-27 に本セクションへ明文化)。

### クラウド誤り 9: 各論コントロールへの誘惑 (2026-05-08 記録、F-particular-angle-redesign-extension)

**誤り**: 視聴者ファースト 3 原則 + ジレンマ解説 + 忖度明示 + 台本表現
ルール等の「具体的指針」をプロンプトやドキュメントに追加したくなる傾向。

**動機**: 品質を保証したい、Hydrangea ミッションを徹底したい
(= 善意の誤り、放置すると深刻なルール累積劣化を引き起こす)。

**害**: ルール累積で全体劣化 (LLM の自由度が削られて全体品質が下がる
経験則、F-12-B-1 NG リスト方式廃止と同根)、`article_writer.py` /
`script_writer.py` の自由度阻害、LLM の知性発揮を抑制。

**正しい設計**: メタデータ構造の正典化 (例: `particular_angle_metadata` +
`sontaku_signals`) + LLM の知性に委ねる + 4 軸メタデータ + sontaku_signals
メタデータで動機担保 (= 各論ルールではなく、構造データを LLM に渡す)。

**カズヤ哲学** (2026-05-08): 「いまは各論をコントロールしたくない。記事の
質の悪化避けたいから。これは、分析フェーズの LLM に期待って感じ。」

**運用ルール**:
- 台本表現や記事品質の課題を見つけたら、まず **メタデータ構造**で表現
  できないか検討する (= LLM に判断材料を増やす)
- ルール追加で対処したくなったら、本誤り 9 を思い出す
- カズヤ承認なしに「具体的言い回しルール」をプロンプトに加えない

**出典**: F-particular-angle-redesign Task E カズヤレビュー (2026-05-08)、
`docs/DISCUSSION_NOTES.md` 「2026-05-08: クラウド誤り 9
(各論コントロールへの誘惑)」エントリ、`docs/PARTICULAR_ANGLE_DEFINITION.md`
セクション 3.7「系統別の台本表現の方向性」(LLM の知性に委ねる設計哲学)。

### クラウド誤り 10: Project Knowledge / 外部レビュー / 自分の過去提案の鵜呑み — 検証なしの仮説受容 (2026-05-25 記録、F-f1-locale-key-fix。2026-05-27 に F-docs-update-chatgpt-round2-and-error10 で CLAUDE.md に明文化)

**誤り**: 起案前に Project Knowledge / 外部 AI レビュー / 自分の過去提案を
grep + 実コード検証せず、「整合の説明」を「検証」と取り違える。バグの方向・
実害・解消状況を、当該コードの全分岐をトレースせず推定で断定する。

**動機**: レビュー指摘や事前情報が「もっともらしい」ため、検証コストを省いて
そのまま起案に転記したくなる (= 善意の効率化、放置すると誤った前提が
DECISION_LOG / CURRENT_STATE に転記され将来の保守者を誤導する)。

**発生実例** (= 外部 AI も同じ罠にハマる):
- **1 回目** (F-f1-locale-key-fix / 2026-05-25): 外部レビュー集約役が F-1 locale key
  bug の実害を「false positive (不当に高い誤爆)」と断定 → grep で実態は
  「false negative 方向 (中間解像度 8〜12 点の永久喪失)」と判明、緊急度を訂正。
- **2 回目** (F-jp-coverage-cache-judgement-persist / 2026-05-26): レビュー指摘
  「Recall 劣化リスク / 監査不能化」を grep + 実測なしに受容 → CP-1 で実害訂正
  (Recall 劣化なし、真の defect は cache round-trip のデータ忠実性欠落)。
- **ChatGPT Round 2 レビュー** (2026-05-27、F-docs-update-chatgpt-round2-and-error10):
  ★ **ChatGPT 側でも誤り 10 系統発生** — 古い Project Knowledge 由来で「既に
  解消済み」の問題 (指摘 3 = F-1 locale key / 指摘 4 = F-13.B cache 永続化) を
  「新規発見」として指摘。**外部 AI レビューも検証対象**である根拠の追加実例。

**害**: バグの緊急度・方向を誤評価し、誤った実害記述が docs 正本に転記されると、
将来の保守者が逆方向の本質を見失う。解消済みの問題を未解消と誤認し重複作業を
生む (ChatGPT Round 2 で実際に発生)。

**回避作法** (1-P / 1-P.5 で機能した好例 = grep-first が誤りを未然に防いだ):
- **起案前 grep を必須化**: 外部レビュー指摘・自分の過去提案・docs 正本との
  整合性を grep + 実コード精読で検証してから起案する。
- **仮説と明示**: Project Knowledge / 過去ログ / 事前情報は **仮説** として扱い、
  コードで検証する (バッチプロンプトに「起案前仮説」セクションを設けるのが望ましい)。
- **調査専用バッチへの縮小**: 仮説と実態の乖離リスクが大きい場合、改修なしの
  調査専用バッチに縮小 (F-script-writer-target-enemy-fix-investigate /
  F-gemini-3.5-flash-api-audit が好例 = grep-first で誤り 10 の再発を回避)。
- **CP-1 で起案者前提を訂正する権限**: Claude Code が Task B 調査で起案者前提を
  grep + 実測で訂正できる運用 (本バッチでも「F-pipeline-health-check」呼称の
  存在しないエントリを正本 F-periodic-health-check に訂正)。

**メタ的含意**: クラウド誤り 10 は Hydrangea ミッション「検証可能な事実で殴る」を
**メタレベルでクラウド自身が体現すべき作法**。外部レビュー (3 AI 三角測量 /
ChatGPT Round N / Gemini Round N) も「整合の説明であって検証ではない」原則の
適用対象であり、grep で裏取りしてから起案する。

**カズヤ哲学** (CURRENT_STATE §7): 「整合の説明であって検証ではない」/
Project Knowledge・事前情報を鵜呑みにしない。

**出典**: `docs/DISCUSSION_NOTES.md` 「2026-05-25: クラウド誤り 10 —
Project Knowledge 過信 + grep 不足」エントリ (正本)、F-f1-locale-key-fix (1 回目記録) /
F-jp-coverage-cache-judgement-persist (2 回目記録) /
F-script-writer-target-enemy-fix-investigate (3 回目回避、grep-first 好例) /
F-gemini-3.5-flash-api-audit (4 回目回避、外部 AI レビュー側で発生したパターンを観察) /
F-docs-update-chatgpt-round2-and-error10 (ChatGPT Round 2 で外部 AI 側発生を観察 +
本誤りを CLAUDE.md に明文化)。

**派生パターン: 外部 AI セカンドオピニオンの権威化** (2026-05-27 観察、F-gemini-quality-tier-poc で正本化)

ChatGPT / Gemini / Claude のいずれの回答も、公式 docs・repo grep・実測の
代替にしてはいけない。特に pricing / model availability / deprecation /
rate limit / API parameters は、必ず一次ソースを確認する。

外部 AI は仮説生成・観点比較には有用だが、事実の正本ではない。

**発生実例 (2026-05-27)**:
- Gemini が Gemini 3.5 Flash 価格を $0.50/$3.00 と提示 → 公式 pricing で
  $1.50/$9.00 と確定 (Gemini は Gemini 3 Flash Preview 価格と取り違えた)
- Claude (web 側) が「Gemini が誤情報を出したので Gemini 廃止 + Claude が
  web_fetch で確認」と判断 → ★★ これも別の権威化 = メタレベルでのクラウド誤り 10
- ChatGPT が「Claude が web_fetch したから正ではなく、公式 source が正」と指摘
  → カズヤ判断で「Gemini = 仮説生成係として継続」「公式 docs / repo grep / 実測
  を正本」運用に修正

**回避作法**:
- 「Claude が確認したから正」「ChatGPT が確認したから正」「Gemini が確認したから正」
  と短絡しない
- 一次ソース (公式 docs / repo grep / 実測) に一致するから正、と表現する
- カズヤも一次ソース確認役を兼ねる (AI 同士の権威化を防ぐ人間ループ)

**カズヤ哲学との整合**: 「検証可能な事実で殴る」「権威の鵜呑みは Hydrangea が
暴くべき構造」とメタレベルで一致。AI を「絶対的な検証者」ではなく「仮説生成 +
反対意見係」として扱う。

**本バッチでの実適用 (F-gemini-quality-tier-poc)**: 起案プロンプトの「最終布陣 v2
(10 role)」も仮説として扱い、grep で実コードを検証 → 実 dispatch は 4 role のみと判明
(viral_filter/title は LLM stage 不在、editorial_mission_filter/article は他 role 共用)。
公式 pricing/API 仕様は web_fetch (一次ソース) で全項目を裏取り (CP-0 スキップ)。

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
| クラウド誤り 1-7 / 9 / 10 の詳細 | `docs/DISCUSSION_NOTES.md` (本ファイルにも誤り 9 / 10 記載) |
| アーキテクチャ全体像 | `docs/ARCHITECTURE.md` |
| 技術的負債リスト | `docs/TECH_DEBT.md` |
| リファクタ計画 (歴史的記録) | `docs/REFACTORING_PLAN.md` |

---

*このファイルは Hydrangea News PoC のメンテナーが管理する。
F-doc-cleanup (2026-05-03) で全面書き直し:
プロジェクト概要・不変原則・触ってはいけないリスト等の重複を完全排除し、
責務を「Claude Code の振る舞い指針」に集約した。
過去版 (v1.0、2026-04-25 分析レイヤー実装期) は git 履歴を参照。*
