# F-title-guard-coverage-claim-policy (1-Q.5) 完了レポート

最終更新: 2026-06-08

> stream_classification (系統判定) と、生成された title / article の coverage claim (報道状態の主張) の
> **事実整合** を第一作公開前に構造的に担保するバッチ。X1 試運転で本番再現した「perspective_gap なのに
> silence 絶対表現」を、原則プロンプト指示 + 生成後 guard の二段で防止する。検出 → **flag のみ**。

---

## 実装ファイル一覧

### 新規作成
- `configs/coverage_claim_policy.yaml` (Layer 2 構造データ。系統 → allowed_claim_level /
  forbidden_claim_categories の意味カテゴリ。guard + プロンプト原則の共有判定基準)
- `configs/prompts/analysis/geo_lens/coverage_claim_guard.md` (Layer 3 guard の LLM judge プロンプト)
- `src/generation/coverage_claim_guard.py` (Layer 3 guard モジュール。policy ローダ + LLM judge +
  B-3' 抽出 + Pydantic 結果モデル `CoverageClaimGuardResult`)
- `scripts/run_coverage_claim_guard.py` (保存済み成果物に guard を適用する手動ランナー、第一作 1-S 用)
- `tests/test_coverage_claim_policy.py` (7 tests)
- `tests/test_coverage_claim_guard.py` (14 tests)

### 変更
- `configs/prompts/analysis/geo_lens/script_with_analysis.md` (Layer 1。既存の particular_angle_metadata
  ブロック直後に事実整合原則を追記。新規 `{}` プレースホルダなし = `.format()` 不変)

### 不変原則対象は 0 行
- `src/generation/article_writer.py` (不変原則 1) — 0 行
- `src/generation/script_writer.py` 既存ルート (不変原則 2) — 0 行
- `src/triage/` / `src/analysis/` 既存ファイル (不変原則 3/4) — 0 行

---

## テスト結果

- `pytest tests/`: baseline 1466 → **1487 passed** (新規 +21、破壊ゼロ)。変更前 311s / 変更後 280s。
- 既存テスト影響: なし (新規 2 ファイルのみ、既存テスト無改変)。
- 新規テスト: `test_coverage_claim_policy.py` (7) + `test_coverage_claim_guard.py` (14)。
  LLM mock で決定的 (短絡経路 / contradiction flag / B-3' uncertain / 許容外カテゴリ安全網 /
  LLM 失敗 skip / シリアライズ等を網羅)。

---

## 起案前仮説 6 点の検証結果 (CP-1、クラウド誤り 10 作法 = grep-first)

| # | 仮説 | 結果 | 検証根拠 |
|---|---|---|---|
| 1 | title の silence は **script の title 素材から流入** | ★ **訂正** | `generate_title_layer` は LLM stage 不在の決定的合成 (factory.py L20)。silence 絶対表現は `title_generator.py:_platform_title_candidates` の **ハードコード template** (L136 `日本では報道されない{topic}の視点` / L149 / L203) を `is_strong` evidence ヒューリスティクス (`_is_strong_evidence` L41-72、`perspective_gap_score>=3.0` でも真) で選択した結果。**script 本文非依存・stream 非参照**。⇒ title の silence は Layer 1 プロンプト原則 (script/article テキスト向け) では届かない。guard (Layer 3) が title の唯一の安全網。 |
| 2 | article プロンプトは article_writer.py の **外** にあり原則追記可 | ★ **確認 → branch (b)** | article プロンプトは `article_writer.py` 内 `_PROMPT_TEMPLATE` (L19) **ハードコード**。不変原則 1 で触れない ⇒ **article 側はプロンプト原則を追加せず guard のみで担保**。Layer 1 は script 新ルートのみ。 |
| 3 | script は新ルート `generate_script_with_analysis` 経由で stream 配線済 | 確認 | `_build_script_with_analysis_prompt` L1199-1236 が `particular_angle_metadata.stream_classification` を `script_with_analysis.md` に配線済 (X1)。新ルートは不変原則 2 の例外で改修可。 |
| 4 | 既存の title/coverage guard は不在 | 確認 | grep で coverage/title guard 不在 (recency_guard のみ、無関係) = グリーンフィールド。 |
| 5 | guard の真値 stream_classification は成果物から参照可能 | 確認 | `ScoredEvent.analysis_result.particular_angle_metadata.stream_classification` (models.py L455/L485/L170)。main.py 生成 dispatch (L1959 article / L2010 script) で event/top/script/article が全て揃う。 |
| 6 | 新 HEAD `896da92` の baseline | 確認 | 実測 **1466 passed** (311s)。本バッチ後 1487 passed。 |

★ 仮説 1/2 の訂正で実装スコープが確定: **Layer 1 プロンプト原則は script 新ルートのみ**、article + title は
**Layer 3 guard で担保**。title の根本修正 (title_generator.py を stream-aware にする) は別タスク
`F-title-generator-stream-aware-fix` (★中) に分離。

---

## 自分で判断した内容

- **判断 1 (Layer 2 配置)**: バッチプロンプトは「configs/ か manual_poc/」だが grep で `manual_poc/` は
  **存在しない**ため、YAML config 慣例 (channels.yaml / source_profiles.yaml 等) に揃え
  `configs/coverage_claim_policy.yaml` に配置。
- **判断 2 (guard モジュール配置)**: `src/generation/coverage_claim_guard.py` (src/generation/ への新規
  ファイル追加)。article_writer.py / script_writer.py 既存ルートに触れず出力を外から検証 = 不変原則 1-2 に
  非抵触。src/analysis/ (原則 4、新規も原則禁止) は避けた。
- **判断 3 (LLM クライアント)**: guard は `get_analysis_llm_client()` (事実重視 temperature 0.3、
  gemini-3.5-flash QUALITY) を default + DI 可。fact-consistency 検証は低温が適切で extractor と同方針。
- **判断 4 (production 配線は見送り)**: guard は flag のみ / 第一作は手動のため、main.py 本番パスへの
  配線は本バッチでは行わず、手動ランナー `scripts/run_coverage_claim_guard.py` + 第一作 (1-S) での
  適用に留める。自動アクション + production 配線は `F-coverage-claim-guard-auto-action` (★低) に分離。
- **判断 5 (guard 安全網の追加)**: LLM が系統ポリシーに無い forbidden_category を返した場合は不採用、
  contradiction 宣言でも採用可能な flag が無ければ consistent に倒す (B-3' + LLM 逸脱の二重安全網)。

---

## guard の flag 出力例

X1 Slot-1 (`cls-c8876d474612`、stream_2_perspective_gap、`platform_title="日本では報道されないIsraelの視点"`)
に guard を適用した出力構造 (LLM judge が title を event_total_silence と判定した場合):

```json
{
  "stream_classification": "stream_2_perspective_gap",
  "flagged": true,
  "flags": [
    {
      "artifact": "title",
      "span": "日本では報道されないIsraelの視点",
      "forbidden_category": "event_total_silence",
      "reasoning": "事件本体は日本でも報道済みのため未報道断定は事実に反する"
    }
  ],
  "title_status": "contradiction",
  "article_status": "consistent",
  "skipped": false,
  "skip_reason": null
}
```

silence_gap / out_of_scope (forbidden カテゴリ空) は LLM を呼ばず `skipped=true` で flag せず返す
(未報道断定が事実整合 / 真値不明 → 安全側)。uncertain / 沈黙は flag しない (B-3')。

---

## 不変原則違反 / 触ってはいけないファイルへの変更要望

- なし。article_writer.py 0 行 / script_writer.py 既存ルート 0 行 / triage・analysis 既存ファイル 0 行。
  guard は src/generation/ 新規ファイルで生成成果物を外から検証 = 不変原則 1-5 厳守。

---

## BATCH_PROTOCOL Task 1-5 実施結果

- **Task 1 (DECISION_LOG)**: 「2026-06-08: F-title-guard-coverage-claim-policy」エントリ追加
  (背景 = X1 + A/B の coverage claim 破れ / 設計 = 原則指示 + guard の事実整合検証 / 仮説 6 点 grep 結果 /
  仮説 1 訂正 + 仮説 2 分岐確定 / flag 出力例 / 関連ファイル)。
- **Task 2 (FUTURE_WORK)**: `F-title-guard-coverage-claim-policy` を緊急度 高 → 完了済みに移動。
  新規 2 タスク追加: `F-title-generator-stream-aware-fix` (★中、title silence 根本修正、仮説 1 訂正由来) /
  `F-coverage-claim-guard-auto-action` (★低 条件付き、guard 自動アクション要否を第一作後に判断)。
- **Task 3 (本完了レポート)**: 本ファイル。guard の flag 出力例を明記。
- **Task 4 (DISCUSSION_NOTES)**: 4-A 新規 2 件 = ① coverage claim 事実整合 guard の設計判断
  (各論コントロール=誤り9 を踏まずに虚偽を弾く整理、昇格候補 DECISION_LOG) / ② AI 文体の根治方針
  (生成プロンプト側で burstiness/反ヘッジ/反テンプレ、humanizer は最後の質感のみ、検出回避は追わない、
  人間編集は第一作で観測し生成プロンプト改善の教師信号、本格設計は第一作後 = 今は実装しない、Active)。
- **Task 5 (CURRENT_STATE 全置換)**: 1-Q.5 完了反映 (Section 0 star note / Section 1 HEAD 896da92 +
  baseline 1487 / Section 2 次バッチ = 1-T → 1-S / Section 5 touchable map に新規ファイル / Section 6
  baseline 1487 / Section 7 フィードバック 3 件 / Section 8 links + footer)。

---

## 次バッチへの引継ぎ事項

- **F-title-generator-stream-aware-fix (★中)**: title の silence 絶対表現は `title_generator.py` の
  決定的合成 (ハードコード template + `is_strong` ヒューリスティクス) 由来で、guard (flag のみ) が暫定
  安全網。生成時に stream に応じて silence template を抑制する根本修正は第一作で guard の flag 挙動を
  観測してから判断。
- **F-coverage-claim-guard-auto-action (★低 条件付き)**: guard の自動アクション (再生成 trigger / 置換) +
  production 配線 (main.py) の要否は第一作の guard 挙動観測後に判断。
- **1-S (第一作起案)**: 候補A 固有の coverage framing 指針 (9,600 人虐待は報道済を明示する等) +
  `scripts/run_coverage_claim_guard.py` での guard 適用 + 第一作の人間編集差分を AI 文体改善の教師信号に
  する観点 (DISCUSSION_NOTES 2026-06-08) を統合。

---

## 環境構築・依存追加

- requirements.txt 追加: なし (yaml は既存依存)。
- 環境変数追加: なし。
