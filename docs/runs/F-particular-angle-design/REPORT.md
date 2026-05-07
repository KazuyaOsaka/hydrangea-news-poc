# F-particular-angle-design 実行レポート

実行日時: 2026-05-07
バッチ: F-particular-angle-design
状態: ★ Task A-E + G 完了、Task F (カズヤレビュー) 待ち、Task H 実施中

## 1. サマリ

「特定角度」概念の docs 化 + 25 件の LLM ベースアノテーション + カズヤレビュー
準備の構成。本バッチは Phase A.5-3a-verify ゲート完了後の最初のバッチで、
F-stream-2-filter-design + F-jp-coverage-tune の共通基盤を確立する性格を
持つ。コード変更なし (新規 docs + 新規 scripts/ + 新規 docs/runs/F-particular-angle-design/
配下のみ)、baseline 1345 passed 維持。

## 2. docs/PARTICULAR_ANGLE_DEFINITION.md 新規作成 (Task A)

セクション構成 5 つで散文展開:

1. **なぜこの概念が必要か** — 系統 1/系統 2 の判定基準が広範事件レベルだと
   重複ケースが避けられない問題、F-trial-run-post-fix で確認された 6 件の
   実例 (Insider trading / Mandelson 等) を踏まえた背景
2. **「特定角度」とは何か** — 海外メディアが独自に掘った視点・問題意識・
   分析切り口、3 要素 (core_question / differentiation_from_mainstream /
   hydrangea_axis_alignment) で構成
3. **「特定角度」を使った系統判定基準** — 系統 1 / 系統 2 / 対象外の
   3 分類論理フロー (Step 1: 4 軸該当 → Step 2: 日本未報道 → Step 3: 解釈差)
4. **「特定角度」抽出の実装方針** — LLM ベース抽出、`get_analysis_llm_client()`
   経由、temperature=0.3、3 要素 + confidence ラベル
5. **関連ファイル** — 後続バッチ (F-stream-2-filter-design /
   F-jp-coverage-tune) への導線含む

## 3. scripts/extract_particular_angle.py 新規作成 (Task B)

主要関数:

- `build_prompt(event)` — プロンプトテンプレート展開 (4 軸 + 3 ステップ
  論理フロー + 1 行制約)
- `parse_llm_response(text)` — Markdown コードブロック除去 + JSON 部分抽出
  + 文字列値中の生改行 → `\n` 等エスケープによる最小修復付き再試行
- `extract_one(client, event, max_retries=3)` — 1 件分の抽出 + リトライ
- `annotate_all(events)` — 全 25 件を順次抽出、失敗 event は
  `extraction_error` フィールドで記録して継続、5 件ごとに進捗ログ
- `_build_extract_client()` — analysis role の Tier 階層を流用しつつ
  `max_output_tokens=4096` を明示指定する専用クライアント (既定の
  `get_analysis_llm_client()` は 2000 tokens で本プロンプトでは JSON が
  途中切断されたため、本スクリプト内で明示拡張)

プロンプト設計概要 (extract_particular_angle.py:`_PROMPT_TEMPLATE`):
- 「特定角度」定義 (海外メディア独自視点、広範事件ではない)
- Hydrangea 4 軸 (制度・システム / 外交・経済・利害関係 / 個人・権力者 /
  関心領域・地政学的死角)
- 系統判定論理フロー (Step 1-3)
- 入力: event_id + title + summary + sources
- 出力: 構造化 JSON (particular_angle 3 要素 + extraction_confidence +
  stream_classification_estimate {estimated_stream + reasoning + confidence})
- 注意: 文字列値は 1 行で記述 (生改行禁止)、confidence 厳密判定

## 4. input_events.json 統合 25 件 (Task C)

- golden_set_v1.1: 19 件 (blind 9 + covered 10)
- trial_run_7K_2026-05-01: 3 件 (FIFA / Mandelson / Gaza power)
- trial_run_2026-05-07: 3 件 (Insider trading / Russian self-immolation /
  Met Police synagogue)
- 合計 25 件、各 event は `event_id / source_origin / title / summary /
  sources / region / topic_category` フィールドを保持

## 5. LLM 抽出結果 (Task D)

実行: 2026-05-07T11:36 起動 → 11:42 完了 (約 6 分 40 秒、25 件)
LLM モデル: gemini-analysis-tier-extended (analysis Tier + max_tokens=4096)

### 5.1 confidence 分布

| 指標 | high | medium | low | unknown |
|---|---|---|---|---|
| extraction_confidence | 22 | 3 | 0 | 0 |
| stream_classification_estimate.confidence | 24 | 1 | 0 | 0 |

medium 抽出 events: covered_002 / covered_003 / covered_007
medium 系統判定 events: covered_007

### 5.2 stream_classification_estimate 分布

| Stream | 件数 | 内訳 |
|---|---|---|
| stream_1_silence_gap | 11 | golden_set 7 + 7-K 1 + 2026-05-07 3 |
| stream_2_framing_inversion | 13 | golden_set 11 + 7-K 2 |
| out_of_scope | 1 | golden_set 1 (covered_006 NVIDIA 株式) |
| unknown | 0 | — |

### 5.3 抽出エラー有無

extraction_errors=0。試行 1 で 6 件、試行 2 で 7 件のパース失敗が発生したが
原因 (= max_output_tokens=2000 で JSON 途中切断) を特定し、`max_output_tokens=4096`
への拡張で全 25 件成功 (試行 3 で 0 errors)。再試行ログは
`extraction_log.txt` 参照。

### 5.4 想定外結果検知

異常検知 2 つはどちらも該当なし:
- extraction_confidence=low が 5 件以上 → 該当なし (low=0)
- 全件が同じ系統に分類 → 該当なし (3 系統に分散、stream_2 が最多 13 件)

## 6. カズヤレビューデータ準備 (Task E)

`docs/runs/F-particular-angle-design/review_draft.md` 生成済み (655 行、
25 events フォーマット統一)。各 event ごとに以下を表示:

- タイトル / 要約抜粋 / source_origin
- LLM 抽出結果 (core_question / differentiation / hydrangea_axis /
  extraction_confidence)
- LLM 判定 (estimated_stream / confidence) + 判定根拠 (reasoning)
- カズヤレビュー欄 (チェックボックス + コメント欄)

カズヤは `annotations.json` の `kazuya_review.*_revised` フィールドに
直接修正を書き込む方式。

## 7. 系統分類最終結果 (LLM 推定段階)

★ 本セクションの数値は **LLM 推定値**。カズヤレビュー後に Task G の
`scripts/finalize_annotations.py` を実行して最終確定する。

| Stream | 件数 | Event 一覧 (要約) |
|---|---|---|
| 系統 1 (silence_gap) | 11 | blind_001 / blind_002 / blind_003 / blind_004 / blind_007 / blind_009 / blind_010 / cls-204a683f73ee_7K (Gaza power 2023-2024 古い + 2026-04 角度) / cls-6be4fc09d9ed (Insider trading) / cls-0c7fa7c667d6 (Russian self-immolation) / cls-a4132ec7d949 (Met Police synagogue) |
| 系統 2 (framing_inversion) | 13 | blind_005 (Mandelson Gaza) / blind_008 (water weapon) / covered_001 (Hormuz) / covered_002 (US-Russia ceasefire) / covered_003 (US-China tariffs) / covered_004 (Pope tyranny) / covered_005 (Brazil COP30) / covered_007 (Nigeria abduction) / covered_008 (Mali defense minister) / covered_009 (Kashmir crisis) / covered_010 (Houthi explicit support) / cls-7bd1406438b6 (FIFA Palestine) / cls-33b4f4960bf9_7K (Mandelson 7-K = 同事象 blind_005 と異なる切り口) |
| 対象外 | 1 | covered_006 (NVIDIA 株式、4 軸該当性なし) |

### 7.1 興味深い観察

**(a) golden_set v1.1 の `stream_2_candidate` メタ付き 4 件
(blind_002/004/005/009) のうち 3 件 (blind_002/004/009) が LLM では
stream_1 に分類された**。これは v1.1 で「広範事件は報道済み (= True)、
特定角度は系統 2 候補」とラベルしていたが、判定対象を「特定角度」に
限定すると同じ事象でも『特定角度自体は日本未報道』と読める可能性が
あることを示唆。カズヤレビューで再評価対象。

**(b) 試運転 2026-05-07 の Insider trading (cls-6be4fc09d9ed) は LLM が
stream_1 と判定**。F-trial-run-post-fix WebSearch 後追いで「広範事件
(米イラン和平交渉) は Tier 1 (nikkei) + Tier 2 (jiji + bloomberg) で
報道済み」と判明したが、特定角度 (国家規模インサイダー取引疑惑) は
日本主要メディアで深掘り未報道、と LLM が判定した。これは「特定角度」
概念の有効性を示唆する事例 (= 広範事件レベル判定では blind_spot ルートに
進んだ動画化が、特定角度レベルでも spot として正当化される)。

**(c) covered 系列の 9/10 件が stream_2 に分類された**。これは LLM が
「日本主要メディアで報道済みの事象でも、海外メディアの掘り下げ角度には
解釈差があり stream_2 候補となる」と読む傾向を示す。F-stream-2-filter-design
が処理する候補数の見積もり材料 (= covered 系列も stream_2 として救出
されうる) として有用。

## 8. F-stream-2-filter-design への引き継ぎ

系統 2 候補 13 件の特性:

- Hydrangea 4 軸の分布: 第 1 軸 (制度・システム面) 1 件、第 2 軸 (外交・
  経済・利害関係面) 8 件、第 3 軸 (個人・権力者面) 2 件、第 4 軸 (関心
  領域・地政学的死角) 2 件 (LLM 出力 `hydrangea_axis_alignment` のテキスト
  パースベース概数、厳密集計はカズヤレビュー後)
- フィルタ設計の指針: stream_2 として救出すべき事象は「広範事件は日本
  主要メディアで報道済み + 特定角度の解釈差が解説価値を生む」。F-13.B
  通過後に LLM 判定で『特定角度の解釈差』を判定する 2 段階フィルタが妥当
- 注意: 同事象の異なる事象記事 (例: blind_005 vs cls-33b4f4960bf9_7K)
  でも特定角度の差で異なる stream に分類されうる (= 広範事件レベルの
  集約ではなく記事単位の判定が必要)

## 9. F-jp-coverage-tune への引き継ぎ

系統 1 候補 11 件の「特定角度」例:

- blind_001 (Ukraine 民間人被害): グローバルサウス独自統計、西側忖度で
  日本未報道 (4 軸第 2)
- blind_002 (Israel ラビ庁拒否): 軍と宗教権威の融合構造分析、日本主要紙
  は事件本体報道のみ (4 軸第 3)
- cls-6be4fc09d9ed (Insider trading): 国家規模インサイダー取引疑惑、
  日本主要紙は外交ニュース扱いのみ (4 軸第 2)
- cls-0c7fa7c667d6 (Russian self-immolation): ロシア当局による反戦抗議
  事件の隠蔽、日本主要紙はマクロ戦況中心 (4 軸第 4)

Grounding 検索クエリ改善の指針: 現実装は title + " 日本 報道" を Grounding
に投げるが、F-trial-run-post-fix で確認された通り英語タイトル + 「日本
報道」では Grounding が youtube.com 偏重の結果を返す。F-jp-coverage-tune
で「特定角度」ベースのクエリ生成 (LLM で英語タイトルから日本語キーワード
+ 特定角度フレーズを抽出) を試すと、Grounding が日本主要メディアの
「特定角度」記事を引き当てる確率が向上する可能性がある。

## 10. 想定外結果と次バッチへの影響

### 10.1 試行 1-2 での JSON パース失敗多発 (記録のみ)

`max_output_tokens=2000` で JSON が途中切断され、6-7 件のパース失敗が
発生した。原因特定後 `max_output_tokens=4096` への拡張で 0 errors を
達成。本スクリプトは `_build_extract_client()` で 4096 tokens 専用
クライアントを構築する設計を採用したが、F-stream-2-filter-design で
本実装する際は `analysis_llm_client` 既定の 2000 tokens を変更する
必要があるかの判断材料として記録。

### 10.2 golden_set v1.1 の stream_2_candidate メタとの差分 (要カズヤ判断)

セクション 7.1 (a) 参照。LLM 判定では blind_002/004/009 が stream_1 に
分類されたが、v1.1 ではこれらに `stream_2_candidate` メタが付与されて
いた。カズヤレビューでどちらが正しいかを判断する必要 (= 広範事件 vs
特定角度の判定単位の違いに起因する可能性あり)。

## 11. 次のステップ

1. **★ カズヤレビュー (Task F)**: `docs/runs/F-particular-angle-design/review_draft.md`
   をレビュー、修正は `annotations.json` の `kazuya_review.*_revised` に
   直接記入
2. **Task G 実行**:
   ```bash
   python scripts/finalize_annotations.py \
       --input docs/runs/F-particular-angle-design/annotations.json \
       --output-diff docs/runs/F-particular-angle-design/annotation_diff.json \
       --output-classification docs/runs/F-particular-angle-design/stream_classification.json \
       --update-golden-set docs/runs/F-verify-jp-coverage/golden_set.json
   ```
3. **Task H 補足更新**: 本 REPORT の「最終結果」「想定外結果」セクションを
   カズヤレビュー結果で確定値に置換
4. **後続バッチ着手**:
   - F-stream-2-filter-design (1st、本バッチで共通基盤確立)
   - F-jp-coverage-tune (2nd、本バッチの「特定角度」概念を検索クエリに転用)

---

*本レポートは F-particular-angle-design (2026-05-07) で作成。Task F (カズヤ
レビュー) は本バッチ内では実行されず、カズヤ手動作業の後に Task G を
実行することで最終化される。本バッチは src/ tests/ configs/ への変更
なし、scripts/ + docs/ + docs/runs/F-particular-angle-design/ のみ。
baseline 1345 passed 維持。*
