# F-wl-hit-quality-audit — REPORT

最終更新: 2026-05-14

> **TL;DR**
>
> F-13.B WL ヒット品質を独立検証した結果、
> 1. 試運転 3 Slot のうち 1 件 (Slot-2 cls-1a38c0ca8c99) が **Suspect FP 確定**、
>    1 件 (Slot-3) が Topic-Level TP / Specific Partial、1 件 (Slot-1) が TP (ただし
>    topic-level)。
> 2. ゴールデンセット TP 17 件から seed=42 で 5 件サンプリング検証した結果、
>    1 件 (cls-a4132ec7d949) が Specific Event Suspect FP、2 件が Topic-Level TP /
>    Specific Partial、2 件が TP。
> 3. ★ **Task D Slot-2 Grounding chunk 生データダンプで決定的発見**: Gemini LLM
>    自身が response_text で『該当しない (別事象)』と明言しているのに、F-13.B は
>    chunk の WL マッチだけで True を返している = LLM の知性を完全に無視する
>    **設計判断レベルの欠陥**。Grounding API の article URL 不在問題と合わせて
>    **根本治療には Option (i) LLM judgement 抽出** が必要。
> 4. Slot-1 cls-6889e9e1c7ac の系統は **stream_2_perspective_gap** (afpbb が
>    9,600 数字 + 虐待を継続報道済み = 真の silence_gap ではない)。第一作起案
>    判断は本バッチでは保留、両論併記でカズヤ判断待ち。
> 5. F-jp-coverage-tune-followup Step C の **F1 covered 0.8718 は broader topic
>    level の値**で、specific event (= particular_angle) level では下振れ可能性。
>    REPORT v2 化は別バッチに分離 (CP カズヤ判断)。
>
> `src/ tests/ configs/` 0 行変更、`scripts/dump_grounding_chunks.py` 新規 1 ファイル
> 追加、`docs/` のみ更新で完結。baseline 1390 passed 維持。

---

## 1. バッチ概要

### 目的

F-trial-run-post-tune (2026-05-11) で観察された問題:
- 試運転 3 Slot 全件 has_jp_coverage=True、ただし matched_urls が全件
  「ベアドメインのみ」(`https://afpbb.com` / `https://nippon.com`)
- Grounding API の chunk.web.title 抽出経路で『afpbb.com』等の文字列をドメイン
  として識別 → WL マッチング階層判定で Tier 認定する仕組みが、「当該事象を実際に
  報道している」ことを保証しない (= 誤陽性リスク)

本バッチは独立検証で以下を確定する:
1. Slot-1/2/3 の matched ドメインが実際に当該事象を報道しているか (本番試運転 3 件)
2. ゴールデンセット 23 件 TP 17 件の誤陽性率 (サンプリング 5 件)
3. Grounding chunk 生データ構造の理解 (article path が取れない構造的理由)
4. 判定: Slot-1 cls-6889e9e1c7ac が真 silence_gap か、ゴールデンセット F1 0.8718 が
   本物か

### 実行構成

- ブランチ: `feature/F-wl-hit-quality-audit` (main HEAD `eb0dd5e` から派生)
- baseline 1390 passed 維持確認 (Task A 開始時)
- 出力先: `docs/runs/F-wl-hit-quality-audit/` 配下に集約
- CP: Task C 完了時にカズヤ判断 → Task D-G 進行 (Slot-2 のみダンプ、両論併記、F1 v2 化別バッチ)

---

## 2. 試運転 3 Slot 検証結果 (Task B)

正本データ: `trial_run_websearch_audit.json`

| Slot | event_id | matched_url | 判定 | 根拠 |
|---|---|---|---|---|
| **1** | cls-6889e9e1c7ac (Israel 9,600 Detainees) | afpbb.com Tier 2 | **TP** | afpbb で `9,600 人拘禁』数字 (`3541376` 等で明示) + 『虐待』 + 『拘禁処遇』を継続報道 |
| **2** | cls-1a38c0ca8c99 (BBC Gaza doc BAFTA) | afpbb.com Tier 2 | **Suspect FP** | afpbb は別事象 (`How to Survive Warzone Gaza` の Ofcom 制裁 `3604087`) を報じるのみ。Slot-2 の Channel 4 `Doctors Under Attack` BAFTA 受賞 (2026-05-11) は afpbb で不在 |
| **3** | cls-03892eab2072 (Tehran says US proposal sought Iran's surrender) | nippon.com Tier 4 | **Topic-Level TP** (Specific Partial) | nippon.com は `イラン「米降伏まで」抗戦`等の Iran-US 降伏フレーミング言説を継続報道。MEE 特定主張は direct match なし。Tier 4 (Business) categorical fit に違和感 |

**観察された誤陽性パターン**:
F-13.B は「topic-family 一致のみで has_jp_coverage=True を返す」 = MEE / TeleSUR が独自に
掘った **specific 角度 (= particular_angle) の日本未報道** を検出できず、**broader topic
家系の日本報道** を検出している。

---

## 3. ゴールデンセット サンプリング 5 件検証結果 (Task C)

正本データ: `golden_sampling_websearch_audit.json`

### サンプリング方法
- 母集団: F-jp-coverage-tune-followup `measurement_result_step_c.json` の TP 17 件
  (= expected_broad_jp_coverage='reported' AND predicted broad_jp_coverage=True)
- seed=42, sample_size=5 (Python `random.sample`)

### 5 件の判定

| event_id | matched | 判定 |
|---|---|---|
| blind_008 (Israel water as weapon) | newsweekjapan.jp Tier 4 | **Topic-Level TP** (NJ で『飢餓を武器化』『戦争犯罪』言説家系に包含) |
| blind_002 (Rabbinate refuses to condemn Jesus statue) | yomiuri/afpbb/nippon/fnn Tier 1 | **Topic-Level TP / Specific Angle Suspect FP** (Jesus 像破壊 itself は afpbb で `3632003`等 手厚く報道、Rabbinate 沈黙の specific 角度は不在) |
| covered_008 (Mali defense minister killed) | yomiuri/afpbb/nippon Tier 1 | **TP Confirmed** (nippon.com `kd1421073361225777944` で direct match) |
| blind_009 (Iran-US war: Money) | yomiuri/newsweekjapan Tier 1 | **Topic-Level TP** (NJ で経済論議家系に包含、Tier 1 認定は NJ が週刊誌系のため違和感) |
| cls-a4132ec7d949 (Met Police synagogue legal complaint) | afpbb Tier 2 | **Specific Event Suspect FP** (afpbb は同 topic 家系継続報道、Slot-2 と同じ Topic-Only パターン) |

**WebSearch クローラ制約**: yomiuri.co.jp / fnn.jp はブロック対象のため、Tier 1
ヒットの一部は直接検証不能。Tier 4 ヒット (afpbb / nippon / newsweekjapan) は問題なく
検証可能と確認。

**Specific Event Level FP 率 (推定)**: 2/5 = 40% (sample size 5 で 95% CI 広い)
**Topic Level Match 率**: 5/5 = 100% (broader topic family 一致は確実)

---

## 4. Grounding chunk 生データダンプ結果 (Task D)

正本データ: `grounding_chunk_raw_dump.json`

### スコープ
CP カズヤ判断 = Slot-2 のみ実施 (Suspect FP 確定、診断価値最大)

### 結果
Slot-2 cls-1a38c0ca8c99 で 8 chunk 取得 (7.51 秒、コスト ≒ $0.05)。

**chunk.web 構造の全件確認**:
- `web_uri`: 全 8 件で Vertex AI redirect URL のみ (例: `vertexaisearch.../redirect/...`)。
  実 URL は SDK で decode 不可
- `web_title`: 全 8 件で **ドメイン名のみ** (例: `afpbb.com`、`arabnews.jp`、
  `middleeasteye.net` 等。article path もページタイトルも含まれない)
- `web_domain` 属性: 全 8 件で None (SDK の戦略 1 公式 domain フィールドは未実装)
- 抽出戦略は全件 strategy_2 (title フィールド経由)

**WL マッチ結果**: afpbb.com chunk 2 件で tier_2_wire_service 認定 → has_jp_coverage=True

### ★★★ 決定的発見

Gemini LLM 自身が response_text で:

> 「ユーザーが確認を求めている『BBCが放送を取りやめたガザに関するドキュメンタリー
> が受賞し、映画製作者がBBCを非難した』という2026年5月上旬の出来事とは異なる
> 内容で、かつ日付も異なります」

と **正しく** 判定している。にもかかわらず F-13.B は chunk の WL マッチだけで
has_jp_coverage=True を返している = **LLM の知性を完全に無視する設計判断レベルの欠陥**。

---

## 5. 構造的理解 + 改善案 (Task E)

正本データ: `structural_analysis.json` + `structural_analysis.md`

### 仮説の切り分け
| 仮説 | 判定 |
|---|---|
| (a) SDK バグ説 (chunk.web.uri が redirect URL のみ) | ✅ 部分確認 (仕様) |
| (b) Grounding API 仕様説 (article path は元から返されない) | ✅ 確認 |
| (c) クエリ品質説 | ❌ 主因ではない (LLM は正しく判定) |
| **(d) ★ LLM judgement bypass 説** | ✅★ 確認 = **最大の改善余地** |

### 改善案 (5 オプション、推奨度順)

1. **★★★ Option (i) LLM response_text 判定を抽出して使う (推奨)**
   - 工数 4-8h、Recall -5〜-10pp / Precision +20〜+40pp
   - カズヤ哲学『LLM の知性に委ねる』に整合
   - `src/triage/jp_coverage_verifier.py` 改修必要 = 不変原則 3 例外条件 + カズヤ承認要

2. Option (ii) WL マッチング側で信頼度フラグ追加 → Task D で無効化 (article path 取得不能)
3. Option (iii) 高信頼度マッチのみで True → 同上、無効化
4. Option (iv) 別 API (Google Custom Search 等) 移行 → 工数 1-2 日、F-jp-coverage-tune-followup-2 と統合検討候補
5. Option (v) クエリ品質改善 → 補助、Option (i) と併用可能

### 推奨パス (本バッチでは実装しない、別バッチ案件)

★ 別バッチ案件として **`F-jp-coverage-llm-judgement-extraction`** (仮称) を起案。
4 段階 (プロンプト改修 → ゴールデン再測定 → verify() 配線 → 試運転)。

---

## 6. 既存メトリクスへの影響

### F-jp-coverage-tune-followup Step C メトリクスの再解釈

| メトリクス | 値 | 再解釈 |
|---|---|---|
| F1 covered | 0.8718 | ★ broader topic-family レベルの値、specific event レベルでは下振れの可能性 |
| Recall covered | 89.47% | 同上 |
| Precision blind | 33.33% | broader topic-only な False Positive が支配的 = Option (i) で大幅改善可能性 |

### REPORT v2 化判断 (CP カズヤ選択)

CP で「本バッチは記録のみ、F-jp-coverage-tune-followup REPORT v2 化は別バッチ」を選択 →
DISCUSSION_NOTES + CURRENT_STATE に broader vs specific の caveat を記録。REPORT v2 化は
**F-jp-coverage-tune-followup-2 着手時に実施推奨**。

---

## 7. 最終判定

### 7-1. Slot-1 cls-6889e9e1c7ac の系統判定 (両論併記、CP カズヤ判断 = 保留)

★ **Topic-Level TP 確定** = **stream_2_perspective_gap** のターゲット (afpbb が 9,600
数字 + 虐待を継続報道済み、真の silence_gap ではない)。

**Option A (perspective_gap framing で第一作起案)**:
- 台本表現を『日本でも事象は報道されたが、TeleSUR が掘った構造 (ICRC 訪問操作疑惑等) は
  触れられていない』perspective_gap 型に切り替え
- Hydrangea ブランドメッセージ『日本未報道』との整合は『特定角度の未報道』として再定義
- 第一作起案を Phase A.5-3b として進める

**Option B (別題材で試運転やり直し)**:
- Slot-1 は保留、別題材で試運転やり直し or 真の silence_gap 題材を選定
- F-13.B WL ヒット品質の根本治療 (Option i) を先に実施してから第一作着手

**Option C (CP カズヤ選択 = 保留)**:
- 本バッチでは判断保留、REPORT に両論併記
- 最終判断は別議論。本バッチの役割は判定材料の整理まで

### 7-2. ゴールデンセット F1 0.8718 信頼性 (CP カズヤ判断 = 記録のみ)

★ **broader topic level では実用ライン到達確認** (F1 0.8718 で threshold 0.85 初突破)、
ただし **specific event level (= particular_angle 一致 level) では下振れの可能性**
(3/8 = 37.5% で topic-family 一致 / specific 不一致パターン観察)。

CP で「本バッチは記録のみ」を選択 → F-jp-coverage-tune-followup REPORT v2 化は別バッチで
実施推奨。本バッチでは DISCUSSION_NOTES + CURRENT_STATE に caveat を記録。

### 7-3. Phase A.5-3b 第一作着手判断材料

| 観点 | 判定材料 |
|---|---|
| Slot-1 を真 silence_gap で売り出せるか | ❌ NO (perspective_gap 確定) |
| Slot-1 を perspective_gap framing で第一作にできるか | ✅ 可能 (台本表現修正必要) |
| F-13.B WL ヒット品質根本治療を先にすべきか | ★ Option (i) 実装 → 第一作着手 OR 並走 (カズヤ判断) |
| ゴールデンセット F1 信頼性は第一作の前提を破壊するか | ❌ broader level では実用、specific level の caveat は記録のみ |

---

## 8. 残課題 / カズヤ確認推奨事項

### 本バッチで顕在化した新規論点 (FUTURE_WORK に追加)

1. ★ **`F-jp-coverage-llm-judgement-extraction`** (仮称、新規バッチ案件): LLM response_text
   判定を抽出して `_search_with_grounding` の戻り値に組み込む根本治療バッチ。Option (i) 実装。
   不変原則 3 例外条件適用要 + カズヤ承認要。
2. ★ **F-jp-coverage-tune-followup REPORT v2 化** (別バッチ): broader topic vs specific event
   の caveat 反映 + 再測定。F-jp-coverage-tune-followup-2 着手時に統合推奨。
3. ★ **ゴールデンセット v2 化検討**: 現ゴールデンは broad_jp_coverage / angle_jp_coverage truth を
   持つが、specific angle level の truth annotation を追加するか別バッチで検討。

### カズヤ確認推奨事項

- **Slot-1 第一作着手可否**: Slot-1 を perspective_gap framing で第一作にする (Option A) か、
  別題材を選定 or F-13.B WL ヒット品質根本治療を先にする (Option B) か。両論併記済み、カズヤ判断要。
- **F-jp-coverage-llm-judgement-extraction 起案優先度**: Phase A.5-3b 第一作着手と並走で進めるか、
  第一作着手前に完了させるか。
- **F-jp-coverage-tune-followup REPORT v2 化のタイミング**: 単独バッチ or F-jp-coverage-tune-followup-2
  と統合か。

---

## 9. BATCH_PROTOCOL Task 1-5 適用結果 (Task G)

### Task 1: DECISION_LOG.md エントリ追加
- 本バッチ完了エントリを末尾追加 (本検証で確認された (d) LLM judgement bypass を歴史的決定として記録)

### Task 2: FUTURE_WORK.md 更新
- 完了済みセクションに「F-13.B WL ヒット品質の独立検証 (本バッチで完了)」を追加
- 新規残課題 3 件を緊急度 高に追加:
  - F-jp-coverage-llm-judgement-extraction (Option (i) 実装)
  - F-jp-coverage-tune-followup REPORT v2 化 (broader vs specific caveat)
  - ゴールデンセット v2 化検討 (specific angle truth annotation)

### Task 3: REPORT.md 末尾 (本セクション) で Task 1-5 適用内容明記

### Task 4: DISCUSSION_NOTES.md 整理
- 4-A 新規追加: 「LLM judgement bypass 問題」エントリを新規追加 (Active)
- 4-B 既存再評価: 「2026-05-11: F-13.B WL ヒット品質問題」エントリを Active → 部分的解消
  (= 構造的理解は完了、Option (i) 実装は別バッチ) に更新

### Task 5: CURRENT_STATE.md 全置換更新
- 最終更新日 + 直近の検証結果 + 次バッチ候補刷新

---

## 10. 不変原則遵守確認 + テスト結果

### 変更したファイル
- `scripts/dump_grounding_chunks.py` (新規追加のみ、既存 scripts は不変)
- `docs/` 配下: REPORT.md + 各種 JSON / MD (本バッチ生成物)
- `docs/CURRENT_STATE.md` (全置換更新)
- `docs/DECISION_LOG.md` (末尾追加)
- `docs/FUTURE_WORK.md` (完了済み移動 + 新規残課題追加)
- `docs/DISCUSSION_NOTES.md` (4-A 新規追加 + 4-B 既存再評価)

### 一切変更していないファイル
- `src/` 配下 全ファイル (= 不変原則 1-4 完全遵守)
- `tests/` 配下 全ファイル (= 不変原則 5 完全遵守)
- `configs/` 配下 全ファイル
- `CLAUDE.md`

### テスト結果
- **baseline 1390 passed 維持** (Task A 開始時に確認、本バッチで src/ tests/ configs/ 0 変更)

### 自分で判断した内容 (CLAUDE.md「完了レポート」フォーマット)
1. **判断 1 (Task D スコープ)**: CP カズヤ判断 = Slot-2 のみ実施を採用。Slot-1 (TP 確定) と
   Slot-3 (Topic-TP) は診断価値低いため省略。これにより API コスト最小化 + 1 バッチで欲張らない
   原則維持。
2. **判断 2 (改善案論点整理)**: 5 つの Option を提示、Option (i) を推奨。本バッチでは実装せず
   別バッチ案件として記録 (= 1 バッチで欲張らない原則)。
3. **判断 3 (Slot-1 系統判定の取り扱い)**: CP カズヤ判断 = REPORT 両論併記を採用。最終判断は
   別議論として保留。
4. **判断 4 (F1 信頼性の REPORT v2 化)**: CP カズヤ判断 = 本バッチは記録のみ、REPORT v2 化は
   別バッチを採用。F-jp-coverage-tune-followup-2 着手時に統合推奨と FUTURE_WORK に明記。
5. **判断 5 (LLM judgement bypass 問題の構造化)**: Task D ダンプで顕在化した新規問題を Active
   エントリとして DISCUSSION_NOTES に追加、関連エントリの再評価とともに整理。

### 不変原則違反 / 触ってはいけないファイルへの変更要望
- なし

### 環境構築・依存追加
- requirements.txt 追加: なし
- 環境変数追加: なし

---

*このドキュメントは F-wl-hit-quality-audit (2026-05-14) で生成。
本バッチは F-trial-run-post-tune (2026-05-11) で観察された WL ヒット品質問題に
対する独立検証バッチで、`src/` `tests/` `configs/` 0 変更で完結。
正本データは `trial_run_websearch_audit.json` / `golden_sampling_websearch_audit.json` /
`grounding_chunk_raw_dump.json` / `structural_analysis.json` を参照。
過去の経緯は DECISION_LOG.md / FUTURE_WORK.md / DISCUSSION_NOTES.md を参照。*
