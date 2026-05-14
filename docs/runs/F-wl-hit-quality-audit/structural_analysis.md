# 構造的理解 + 改善案議論 (Task E)

最終更新: 2026-05-14 (F-wl-hit-quality-audit)

本ドキュメントは Task B-D の結果を統合し、F-13.B WL ヒット品質問題の構造的
理解 + 改善案論点整理 + 第一作着手判断への影響をまとめる。正本データは
`structural_analysis.json`。

---

## 1. 決定的発見 (Task D dump で確認)

★★★ **Gemini LLM 自身が response_text で『該当しない (別事象)』と明言しているのに、
F-13.B `_search_with_grounding` は chunk.web の WL マッチだけで has_jp_coverage=True
を返している**。

Slot-2 cls-1a38c0ca8c99 (BBC Gaza documentary BAFTA 受賞) の Grounding dump で
Gemini 自身が以下のように判定:

> 「ユーザーが確認を求めている『BBCが放送を取りやめたガザに関するドキュメンタリー
> が受賞し、映画製作者がBBCを非難した』という2026年5月上旬の出来事とは異なる
> 内容で、かつ日付も異なります」

にもかかわらず、F-13.B は afpbb.com chunk が 2 件存在することだけで
has_jp_coverage=True を返している。これは ★ **設計判断レベルの欠陥** (LLM の
知性に委ねていない、カズヤ哲学に反する設計)。

---

## 2. chunk.web データ構造の確認 (Slot-2 dump、8 chunks)

| chunk idx | web_uri | web_title | web_domain | extracted (戦略) |
|---|---|---|---|---|
| 0 | `vertexaisearch.../redirect/...` | `afpbb.com` | None | `afpbb.com` (strategy_2) |
| 1 | `vertexaisearch.../redirect/...` | `afpbb.com` | None | `afpbb.com` (strategy_2) |
| 2 | `vertexaisearch.../redirect/...` | `arabnews.jp` | None | `arabnews.jp` (strategy_2) |
| 3 | `vertexaisearch.../redirect/...` | `middleeasteye.net` | None | (strategy_2) |
| 4 | `vertexaisearch.../redirect/...` | `newarab.com` | None | (strategy_2) |
| 5 | `vertexaisearch.../redirect/...` | `madhyamamonline.com` | None | (strategy_2) |
| 6 | `vertexaisearch.../redirect/...` | `themarysue.com` | None | (strategy_2) |
| 7 | `vertexaisearch.../redirect/...` | `aa.com.tr` | None | (strategy_2) |

**観察事項**:
- 全 8 chunk で `web_uri` は Vertex AI redirect URL のみ (実 URL は SDK で decode 不可)
- 全 8 chunk で `web_title` は **ドメイン名のみ** (article path もページタイトルも含まれない)
- 全 8 chunk で `web_domain` は None (SDK の戦略 1 公式 domain フィールドは未実装)
- 抽出戦略は全件 strategy_2 (title フィールド経由)
- WL マッチは afpbb.com chunk 2 件で tier_2_wire_service 認定 → has_jp_coverage=True

---

## 3. 仮説の切り分け

### (a) SDK バグ説 — Gemini SDK が chunk.web.uri を redirect URL でしか返さない仕様
- **証拠**: Slot-2 ダンプの 8/8 chunk で web_uri = Vertex AI redirect URL のみ
- **判定**: ✅ 部分確認。ただし bug というより仕様

### (b) Grounding API 仕様説 — article path は元から返されない
- **証拠**: 8/8 chunk で web_title = ドメイン名のみ。SDK で取得可能なフィールドに article URL が一切ない
- **判定**: ✅ 確認 (API 仕様レベルで article 粒度の URL 取得は不可能)

### (c) クエリ品質説 — 検索クエリが article URL を引き出せていない
- **証拠**: 現クエリ = `{英語 title} 日本 報道` で Gemini は『該当しない』と response_text で正しく判定。
  chunk が低品質なのではなく、Grounding が返す chunk 構造自体に article URL が含まれない設計
- **判定**: ❌ 主因ではない (クエリ品質よりも API レベルの構造的制約が支配)

### (d) ★ LLM judgement bypass 説 (本検証で初顕在化)
- **証拠**: Slot-2 で LLM が『該当しない、別事象、日付も異なる』と明示判定。にもかかわらず
  F-13.B は WL マッチだけで True を返している
- **判定**: ✅★ 確認 = **改善余地が最大の論点**

---

## 4. 改善案 (5 つ)

| Option | 名前 | 推奨度 | 工数 | 効果 (推定) |
|---|---|---|---|---|
| **(i)** | LLM response_text 判定を抽出して使う | ★★★ 最高 | 4-8h | Recall -5〜-10pp / Precision +20〜+40pp |
| (ii) | WL マッチング側で『ベアドメインのみ = 低信頼度』フラグ | ★ 無効化 | — | (Task D で API 仕様問題判明) |
| (iii) | 高信頼度マッチ (article path あり) のみで True | ★ 無効化 | — | (同上、極端な Recall 低下) |
| (iv) | 別 API (Google Custom Search 等) への移行 | 中 | 1-2 日 | article 粒度のマッチ可能、 F-jp-coverage-tune-followup-2 と統合検討 |
| (v) | Grounding クエリの品質改善 | 補助 | 2-3h | (i) の補助として併用可能 |

### Option (i) 詳細 (推奨)

**実装スケッチ**:
1. プロンプトを改修: 『該当する記事があれば URL を列挙、ない場合は明示的に「なし」と回答してください』指示を追加
2. response_text の構造化 (JSON 出力をオプションで指示、無理なら正規表現/キーワード抽出で『なし』判定)
3. `_search_with_grounding` の戻り値型を `tuple[list[str], LLMJudgement]` に拡張、LLM judgement を verify() の判定に反映
4. `verify()` のロジック: WL match あり AND LLM 判定 = 『あり』 → True / WL match あり AND LLM 判定 = 『なし』 → False (= LLM 判定が支配) / WL match なし → False (現状維持)

**Pros**:
- ★ Hydrangea カズヤ哲学『LLM の知性に委ねる』に整合 (F-task-e-finalize / 2026-05-08 確立)
- ★ 誤陽性 (Slot-2 / blind_002 / cls-a4132ec7d949 のような broader topic 一致のみ) の根本治療
- Grounding API の article URL 不在問題を回避 (= LLM が記事内容をすでに読んで判定している)

**Cons**:
- LLM 判定にハルシネーション/誤判定のリスク
- src/triage/jp_coverage_verifier.py 改修必要 = **不変原則 3 例外条件** (Hydrangea ミッション中核機構 + 実装バグ修正 + 設計変更ではない + DECISION_LOG 明記、4 条件全) でカズヤ承認要

---

## 5. 推奨パス (Recommended Path)

**Primary**: Option (i) LLM response_text 判定を抽出して使う = **根本治療**

**根拠**:
- ★ カズヤ哲学『LLM の知性に委ねる』『対症療法じゃなく根本治療』に整合
- ★ Task D で LLM 自身が正しく『該当しない、別事象、日付も異なる』と判定していることが確認 = LLM の判定能力は高い
- ★ 現実装が LLM judgement を bypass している = 設計判断レベルの欠陥、修正で大きな効果が見込める
- ★ Grounding API の article URL 不在問題は回避できる (= LLM が記事内容を読んで判定済み)

**実装戦略提案 (別バッチ案件として、本バッチでは実装しない)**:
- ★ 別バッチ案件として `F-jp-coverage-llm-judgement-extraction` (仮称) を起案
- Step 1: プロンプト改修 + response_text 解釈ロジック実装 (= scripts/ に PoC を先に作る、F-jp-coverage-improve の F-13.B 構造的不具合修正と同様の段階的開発)
- Step 2: ゴールデンセット 23 件 + 試運転 3 件で再測定 (Recall covered + Precision blind の trade-off 評価)
- Step 3: verify() への配線 (不変原則 3 例外条件適用、カズヤ承認必須)
- Step 4: 本番試運転 + REPORT

**Deferred**:
- Option (iv) Alternative Search API = (i) で Recall/Precision 改善が不十分な場合 OR F-jp-coverage-tune-followup-2 (多クエリ並列発行) と統合検討
- Option (v) クエリ品質改善 = (i) の補助として併用可能

---

## 6. 既存メトリクスへの影響 (再解釈)

### F-jp-coverage-tune-followup Step C メトリクス再解釈

- **F1 covered 0.8718** (threshold 0.85 初突破) → ★ **broader topic-family レベル**での実用性指標
  であって、**specific event (= particular_angle) レベル**では下振れの可能性。本検証で
  Slot-2 / blind_002 / cls-a4132ec7d949 の 3 ケースで topic-family 一致 / specific event 不一致が
  確認された (試運転 + golden サンプリングで 3/8 = 37.5%)
- **Recall covered 89.47%** → 同様に broader topic level での Recall (= 当該日本メディアが当該
  topic 家系を報道しているか) であって、specific event level (= 当該日本メディアが当該 specific
  角度を報道しているか) ではない。Hydrangea コアミッション = perspective_gap (系統 2、= specific
  角度の日本未報道) を機械検出するには現 F-13.B では構造的に不足
- **Precision blind 33.33%** → blind 真値 4 件中 3 件が誤って『covered』と判定されている =
  Option (i) LLM judgement 抽出で大幅改善可能性 (= LLM が『該当しない』と言える broader topic-only
  ケースを救い出せる)

### メトリクス再評価の運用方針 (CP カズヤ判断)

★ CP でカズヤ判断 = 「本バッチは記録のみ、F-jp-coverage-tune-followup REPORT v2 化は別バッチ」 →
**REPORT v2 化は F-jp-coverage-tune-followup-2 着手時に実施推奨**。本バッチでは DISCUSSION_NOTES +
CURRENT_STATE に broader vs specific の caveat を記録する。

---

## 7. Phase A.5-3b 第一作着手判断への影響

### Slot-1 cls-6889e9e1c7ac の検証後ステータス

★ **Topic-Level TP 確定** (afpbb は 9,600 数字 + 虐待を継続報道) = 真の silence_gap ではなく
**perspective_gap (系統 2) のターゲット**

### 第一作着手の選択肢 (両論併記、カズヤ判断 = 保留)

**Option A: perspective_gap framing で第一作起案**
- Slot-1 で第一作起案、台本表現を『日本でも事象は報道されたが、TeleSUR が掘った構造
  (ICRC 訪問操作疑惑等) は触れられていない』perspective_gap 型に切り替え
- Hydrangea ブランドメッセージ『日本未報道』との整合は『特定角度の未報道』として再定義

**Option B: 別題材で試運転やり直し**
- Slot-1 は保留、別題材で試運転やり直し or 真の silence_gap 題材を選定
- F-13.B WL ヒット品質の根本治療 (Option i) を先に実施してから第一作着手

**Option C (CP カズヤ選択)**: 本バッチでは判断保留、REPORT に両論併記
- 最終判断は別議論。本バッチの役割は判定材料の整理まで

---

## 8. 不変原則遵守確認

本バッチで変更したファイル:
- `scripts/dump_grounding_chunks.py` (新規追加のみ、既存 scripts は不変)
- `docs/` 配下 (REPORT.md + 各種 JSON / MD = docs 更新のみ)

本バッチで一切変更していないファイル:
- `src/` 配下 全ファイル (= 不変原則 1-4 完全遵守)
- `tests/` 配下 全ファイル (= 不変原則 5 完全遵守)
- `configs/` 配下 全ファイル
- `CLAUDE.md`

baseline 1390 passed 維持確認済み (Task A 開始時)。

---

*このドキュメントは F-wl-hit-quality-audit (2026-05-14) で生成。
正本データは `structural_analysis.json` を参照。*
