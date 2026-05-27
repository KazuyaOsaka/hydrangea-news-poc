# F-gemini-3.5-flash-api-audit — Gemini 3.5 Flash API 影響範囲調査レポート

生成日: 2026-05-27
ブランチ: `feature/F-gemini-3.5-flash-api-audit`
main HEAD: `07dc175`
baseline: **1417 passed** 維持 (調査専用、`src/ tests/ configs/ scripts/ CLAUDE.md .env .env.example` 0 行変更)

---

## 1. バッチ概要 (調査専用、改修なし)

2026-05 GA リリースの **Gemini 3.5 Flash (Stable)** を Hydrangea コードベースに投入する
前提として、API 破壊的変更の影響範囲を **grep + コード精読 + 公式仕様対比** で確認する
**調査専用バッチ (改修一切なし)**。後続 `F-gemini-quality-tier-poc` (1-Q) で Narrative
primary (QUALITY Tier1) 候補に追加するための前提情報を整備する。

★ クラウド誤り 10 (Project Knowledge / 事前情報の過信 + grep 不足) の再発回避のため、
F-script-writer-target-enemy-fix-investigate と同型の調査専用バッチにスコープ縮小。
事前情報 (2026-05-19 Google I/O 由来) は**仮説**として扱い、grep 実態で検証した。

出力は `docs/runs/F-gemini-3.5-flash-api-audit/` 配下のみ:
`environment_snapshot.json` / `grep_inventory.json` / `current_usage.json` /
`adoption_simulation.json` / `breaking_change_analysis.json` / `REPORT.md`。

---

## 2. Task B grep + コード精読 + 公式仕様対比結果

### 2-1. API パラメータの参照棚卸し (B-1)

| 調査軸 | grep 実態 | 露出 |
|---|---|---|
| `top_p` | **0 件** (Gemini パラメータとして) | なし |
| `top_k` | **0 件** (ヒットは event_builder の token 集計/not_top_k count = API 無関係) | なし |
| `temperature` | analysis client (`factory.py:524`、ANALYSIS_LAYER_ENABLED=false で**本番未起動**) + 手動スクリプト 3 件のみ。本番生成系は `generation_config=None` で非指定 | 最小 |
| `thinking_budget` / `thinking_level` | **0 件** | なし |
| `thinking` / `thought` | 全て Hydrangea ドメインフィールド `director_thought` = Gemini Thinking 機能と無関係 | なし |
| カスタム function calling (`FunctionDeclaration` 等) | **0 件** | なし |
| `tools=` | Grounding 組込み `types.Tool(google_search=types.GoogleSearch())` のみ (`jp_coverage_verifier.py:594,1153` + デバッグスクリプト) | Grounding 限定 |
| structured outputs (`response_schema` / `response_mime_type`) | **0 件**。free-text から自前 JSON パース | なし |
| `gemini-3.5-flash` | **0 件** (未採用) | — |
| `gemini-3.1-pro` | **0 件** (Editorial Guardian 候補、未配線) | — |

### 2-2. 現状の Gemini モデル使用状況 (B-2)

解決経路 = `.env → config.py → factory.py` (factory は `os.getenv` 直読で `.env` を最優先)。

```
QUALITY_ROLES {judge, script, article, title, analysis, generation(未分類→QUALITY既定)}
  Tier1  gemini-3-flash-preview   [PREVIEW]  primary (= Narrative primary)
  Tier2  gemini-2.5-flash         [GA]
  Tier3  gemini-3.1-flash-lite    [GA]   (5/25 shutdown 対応で -preview→GA 置換済を再確認)
  Tier4  gemini-2.5-flash-lite    [GA]   最終安全網

LIGHTWEIGHT_ROLES {garbage_filter, merge_batch, viral_filter, editorial_mission_filter}
  Tier1  gemini-2.5-flash         [GA]   primary
  Tier2  gemini-2.5-flash-lite    [GA]
  Tier3  gemini-3.1-flash-lite    [GA]
  Tier4  gemini-3-flash-preview   [PREVIEW]  最終 fallback

generation (script+article) 実 resolved = gemini-3-flash-preview  (run_summary 20260526)
judge 実 resolved              = gemini-2.5-flash  (JUDGE_MODEL=GEMINI_MODEL_TIER2)
merge_batch 実 resolved        = gemini-2.5-flash
F-13.B Grounding               = gemini-2.5-flash  (JP_COVERAGE_GROUNDING_MODEL、Tier 非経由)
```

本番生成パスは `generation_config=None` = temperature/top_p/top_k 一切非指定で API
デフォルト依存。**API パラメータ設定面が構造的に最小**。

### 2-3. 採用シミュレーション (B-3)

**Narrative primary 投入 (gemini-3.5-flash → QUALITY Tier1)**:
- RPD: 直近 run = 41 calls/run のうち QUALITY Tier1 は 5-10。cron 4 runs/日 → **20-40 calls/日**。
  RPD 10K に対し **250-500x の余裕** (worst case 全 calls Tier1 でも 164/日 = 60x 余裕)。
- RPM 1K / TPM 2M も余裕大。API パラメータ非指定で互換問題ゼロ。
- → **RPD/RPM/TPM/API 互換すべてクリア**。残る判断軸は品質 (3-flash-preview vs 3.5-flash Stable) = PoC 管轄。

**LIGHTWEIGHT Tier1**: 高頻度・低難度タスク。**gemini-3.1-flash-lite (RPD 150K, RPM 4K) 推奨**
(3.5 Flash の RPD 10K を Narrative primary と共有せず、spike 耐性を確保)。3.5 Flash は使わない。

**Editorial Guardian**: gemini-3.1-pro (RPD 250) は高リスク事実検証専用の局所使用。
3.5 Flash (Narrative primary) と役割分担、別途配線判断。

### 2-4. API 破壊的変更の実態判定 (B-4) → **真因 b**

| 事前情報 (仮説) | grep 実態 | 露出 |
|---|---|---|
| 1. temperature/top_p/top_k 非推奨化 | top_p/top_k=0件、temperature は未配線パスのみ | MINIMAL |
| 2. thinking_budget→thinking_level rename | thinking 系=0件 | NONE |
| 3. Function calling 厳密マッチ必須化 | カスタム関数宣言=0件、google_search は Supported | NONE |
| 4. Thought preservation 自動 ON | thinking 未使用、response.text のみ消費 | MINIMAL (cost 留意点のみ) |
| (追加) structured outputs 仕様変更 | response_schema=0件、free-text パース | NONE |

**判定 = 真因 b: API 破壊的変更は無いか軽微 → migration 不要、quality-tier-poc に直進**。

構造的理由: (a) Tier ベースのモデル ID 解決で本番生成系は API パラメータ非指定、
(b) 構造化出力 API でなく free-text JSON パース、(c) カスタム function calling 不使用で
`tools=` は Grounding `google_search` のみ。この 3 特性が破壊的変更への露出を構造的に最小化。

真因 a (migration 必要) / 真因 c (部分 migration) はともに REJECTED (本番パスに該当箇所不在)。

---

## 3. CP-1 で確定した後続バッチ方針

- **後続バッチ方針 = Y1 (F-gemini-quality-tier-poc にそのまま進める)** [クラウド推奨]
  - 真因 b 確定により部分/全面 migration 不要。`gemini-3.5-flash` を候補追加して 1-Q に直進。
  - 「対症療法じゃなく根本治療」「1 バッチで欲張らない」と整合。
- Y2 (部分 migration) / Y3 (全面 migration) はともに不採用 (解消対象が本番パスに実在しない)。
- ★ 本判断はクラウド推奨を既定として進めた (CP-1 選択の最終確定は Task G commit/merge 承認時にカズヤが確認可能)。

> ★ CP-1 の AskUserQuestion で選択が捕捉されなかったため、クラウド推奨 (Y1 + 候補リスト
> 「3.5 Flash 追加 + 3 Flash Preview 削除」) を既定として Task E/F を進めた。本作業は
> docs のみ・完全可逆で、Task G (commit/merge) がカズヤ承認ゲートとして機能する。
> 方針変更が必要な場合は merge 前に修正可能。

---

## 4. ★ 起案前事前情報と grep 実態の比較 (クラウド誤り 10 系統の検証)

- 事前情報 (2026-05-19 Google I/O 由来、4 破壊的変更候補) を**仮説として扱い grep で検証**した
  結果、いずれも **Hydrangea コードベースには当てはまらない** ことが判明。
- 乖離の本質: 事前情報は「破壊的変更の可能性」を強調したが、Hydrangea の設計特性
  (Tier ベース解決 + free-text パース + Grounding 限定 tools) により実際の露出はほぼゼロ。
- ★ F-script-writer-target-enemy 同様、**外部/事前情報を grep-first で検証してから断定する作法が機能**。
- 留意: 事前情報そのものが誤りとは限らない (他コードベースには破壊的変更が該当しうる)。
  あくまで「Hydrangea には影響軽微」が grep で確定したという検証結果。

---

## 5. F-gemini-quality-tier-poc 候補リスト更新提案

| 区分 | 提案 |
|---|---|
| Narrative primary (QUALITY Tier1) 候補 | **gemini-3.5-flash (Stable) 追加** + **gemini-3-flash-preview 削除** (3.5 Flash Stable が GA 後継で代替可能) |
| 比較ベースライン (安定 fallback) | gemini-2.5-flash 維持 |
| Editorial Guardian (別枠、局所) | gemini-3.1-pro (RPD 250、高リスク事実検証専用) |
| LIGHTWEIGHT Tier1 主軸切替 | gemini-3.1-flash-lite (RPD 150K) を本命に (migrate-emergency CP-1 保留分の決着) |

→ PoC 候補 = **gemini-3.5-flash / gemini-2.5-flash** (+ Guardian 別枠 gemini-3.1-pro)。

---

## 6. 残課題 (後続バッチに引き継ぐ事項)

1. **F-gemini-quality-tier-poc (1-Q)**: 上記候補で Narrative primary 確定 PoC +
   axis_5 採点 + publish_gate_flags 構造設計 + LIGHTWEIGHT Tier1 切替判断。
2. **3.5 Flash 投入時の output_token/レイテンシ実測**: Thought preservation 自動 ON の
   cost 影響を PoC 試運転で観察 (改修不要の軽微な留意点)。
3. **config.py / factory.py default 不一致**: runtime 影響なしの既知 doc-drift。
   quality-tier-poc 同時 or 別 doc バッチで整合 (CURRENT_STATE 次バッチ候補 10th)。
4. **Editorial Guardian (gemini-3.1-pro) 配線判断**: 高リスク事実検証ワークフロー
   (ADR-0003 由来、Phase A.5-3b 並走) で別途判断。

---

## 7. BATCH_PROTOCOL Task 1-5 適用内容 (Task 3 = 本セクション)

- **Task 1 (DECISION_LOG)**: 本バッチエントリ追加 + 前バッチ
  F-script-writer-target-enemy-fix-investigate の「コミット: (push 後追記)」を実ハッシュ
  `1409e0a` (feat) / `07dc175` (merge) に追記更新。
- **Task 2 (FUTURE_WORK)**: 本バッチ完了済み移動 (調査結果サマリ + 引き継ぎ) +
  F-gemini-quality-tier-poc エントリの候補リストを「3.5 Flash 追加 + 3 Flash Preview 削除」で更新。
  Y1 採用のため部分 migration バッチの新規追加なし。
- **Task 3**: 本セクション = 完了レポートへの明記。
- **Task 4 (DISCUSSION_NOTES)**: 4-A 新規「2026-05-27: Gemini 3.5 Flash API 影響範囲調査 —
  破壊的変更の実態確定 (真因 b)」(ステータス Resolved/タスク化) 追加 + 既存再評価。
- **Task 5 (CURRENT_STATE)**: 19 つ目バッチ (1-P.5) として全置換更新。次バッチ候補
  1st=F-gemini-quality-tier-poc (1-Q) / 2nd=X1 (新ルート本番配線、target_enemy 解消統合)。

*(本レポートは Task A/B 完了 + CP-1 後に Task E として作成。)*
