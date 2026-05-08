# F-particular-angle-redesign 実行レポート

実行日時: 2026-05-07 〜 2026-05-08 (Phase A.5-3a-verify ゲート完了後の 2 つ目のバッチ)
バッチ: F-particular-angle-redesign
状態: ★ Task A-D + F 完了、Task E (カズヤレビュー) 待ち、Task G (本レポート + ドッグフーディング) 実施中

## 1. サマリ

3 分類 (系統 1 / 系統 2 / 動画化対象外) → **4 分類** (系統 1 / 系統 1.5 / 系統 2 /
動画化対象外) への構造化、`docs/PARTICULAR_ANGLE_DEFINITION.md` 改訂 +
`annotations.json` 25 件 LLM 再分類 + 台本表現ガイドライン (新サブセクション 3.5)
追加。F-particular-angle-design (2026-05-07) のレビュー過程で発見された
「広範事件は報道済み + 特定角度のみ未報道」という構造的不備を、系統 1.5
(perspective_gap) を新設することで解消した。本バッチは src/ tests/ configs/ への
変更なし、新規 scripts/ + docs/ 配下のみ。baseline 1345 passed 維持。

## 2. docs/PARTICULAR_ANGLE_DEFINITION.md 改訂内容

### 2.1 主要変更箇所

- **セクション 1 末尾**: 新サブセクション「1.1 3 分類の構造的不備と 1.5 分類追加
  の経緯」を追記。F-particular-angle-design でのカズヤレビュー過程で発見された
  blind_002/004/009 等の構造的問題と、4 分類化に至った経緯を散文展開。
- **セクション 3 (大幅改訂)**: 3 分類論理フロー → 4 分類論理フロー に再構成。
  Step 2 (広範事件報道判定) と Step 3 (特定角度報道判定) を分離し、両者の組み合わせ
  で系統 1 / 系統 1.5 を区別する。各分類の定義 (系統 1 / 系統 1.5 NEW / 系統 2 /
  動画化対象外) を散文展開し、台本表現の方向性も明記。
- **新サブセクション 3.5: 系統別の台本表現の方向性**: カズヤとの 2026-05-07 議論
  で確立された「LLM の知性に委ねる」設計哲学を 3.5.1 - 3.5.4 で展開。具体的な
  particular_angle_metadata 構造、系統別の言い回し例 (ルール強制ではなく例示)、
  Phase A.5-3b 手動 PoC への接続経路を記述。
- **セクション 4 (微修正)**: 4 分類対応 (Step 1-4 論理フロー) に LLM プロンプト
  方針を更新、`scripts/reclassify_annotations.py` への参照を追加。
- **セクション 5 (構造化)**: 関連ファイルを 5.1 (F-particular-angle-design 由来) /
  5.2 (F-particular-angle-redesign 由来) / 5.3 (後続バッチ参照) の 3 サブ
  セクションに整理。

### 2.2 ヘッダ更新

最終更新を「2026-05-07 (F-particular-angle-redesign / 2026-05-07 完了 — 3 分類 →
4 分類化)」に更新。冒頭注記に 4 分類化の経緯を追記。

## 3. scripts/reclassify_annotations.py 新規作成 (Task B)

主要関数:
- `build_prompt(annotation)`: 既存 particular_angle (3 要素) を context として
  与えつつ、4 分類 (Step 1-4 論理フロー) で再判定させるプロンプトを組み立て
- `_generate_with_timeout(client, prompt, 90s)`: ThreadPoolExecutor ベースの
  per-call timeout (90 秒)。Gemini API ハング発生時の防衛策
- `reclassify_one(client, ann)`: 1 件分の 4 分類判定 (TimeoutError / parse 失敗 /
  API エラーで個別に最大 3 回リトライ)
- `reclassify_all(annotations, output_path, ..., skip_already_reclassified=True)`:
  resume 対応 + incremental save (1 件ごとに output_path を更新、kill 中断耐性)
- `_is_already_reclassified(ann)`: legacy_stream_classification_v1 + 4 分類値の
  両方が揃っていれば既判定とみなす (resume 判定)
- `_build_extract_client()`: max_output_tokens=4096 専用クライアント
  (extract_particular_angle.py から流用)
- `summarize_after(annotations)` / `build_diff(log_entries)`: 4 分類対応の集計

プロンプト設計の核心:
- 4 分類定義を明示 (stream_1 = 両方未報道、stream_1_5 = 広範のみ報道、stream_2
  = 特定角度報道済み + 解釈差、out_of_scope = 4 軸該当なしまたは差分なし)
- Step 1 → 2 → 3 → 4 の順序で判定、Step 2 と Step 3 を **独立判定** させる
  (broad_event_jp_coverage / particular_angle_jp_coverage を別フィールドで返却)
- reasoning に **広範事件報道状態 + 特定角度報道状態の両方を必ず明記** と指示

CLI 引数: `--input` / `--output` / `--backup` / `--diff-output` / `--log-output` /
`--llm-model`。同じパスで input == output も許容 (上書き運用)。

## 4. 25 件再分類の実行結果 (Task C)

### 4.1 実行サマリ

- 起動: 2026-05-07T22:00:22+00:00 → 完了: 2026-05-07T23:36:19+00:00
  (約 1 時間 36 分、Gemini API 503 高負荷で Tier 1 → Tier 2 → Tier 3 フォールバック
  多発のため通常より長い)
- 25 件全件処理完了、success=25、error=0、skipped=0、timeout 警告 3 件 (covered_002 /
  covered_004 / cls-204a683f73ee_7K で 90s タイムアウト発生 + 後続リトライで成功)
- 旧版バックアップ: `annotations_v1_3class.json` (idempotent、既存ファイルがある
  場合は上書きしない)
- LLM モデル: gemini-analysis-tier-extended (analysis Tier 階層 + max_output_tokens=4096)

### 4.2 4 分類分布 (LLM 推定段階)

| 分類 | 件数 | 比率 | 想定値 (バッチ仕様) | 差異 |
|---|---|---|---|---|
| 系統 1 (silence_gap) | 4 | 16% | 約 6 件 (24%) | -2 |
| 系統 1.5 (perspective_gap) ★ NEW | **20** | **80%** | 約 5 件 (20%) | **+15** |
| 系統 2 (framing_inversion) | **0** | **0%** | 約 13 件 (52%) | **-13** |
| 動画化対象外 | 1 | 4% | 1 件 (4%) | 0 |
| 合計 | 25 | 100% | 25 | — |

★ **想定外結果**: stream_1_5 が想定 5 件 → 実測 20 件 (4 倍超)、stream_2 が
想定 13 件 → 実測 0 件 (全消失)。詳細考察はセクション 9 を参照。

### 4.3 旧 3 分類 → 新 4 分類の transition

| 遷移 | 件数 |
|---|---|
| stream_1 → stream_1 | 4 |
| stream_1 → stream_1_5 | 7 |
| stream_2 → stream_1_5 | 13 |
| out_of_scope → out_of_scope | 1 |
| 合計 | 25 |

変更件数 = 20 (80%)、不変件数 = 5。

## 5. 顕著な変更パターン (Task D 用の事前整理)

### 5.1 stream_1 → stream_1_5 への移動 (7 件)

3 分類版で「日本未報道 = stream_1」と判定されていたが、4 分類版で「広範事件は
報道済みだが、特定角度は未報道 = stream_1_5」と再判定されたケース。

- blind_002 (Israel ラビ庁): 像破壊事件本体は朝日・日経で報道済み、ラビ庁拒否角度
  は未報道 → stream_1_5
- blind_004 (Gaza 潤滑油 100 倍): ガザ電力危機本体は東京新聞で報道済み、潤滑油
  100 倍角度は未報道 → stream_1_5
- blind_009 (Iran-US 戦争長期化): 米イラン対立本体は広範報道、革命防衛隊利権の
  経済構造分析は未報道 → stream_1_5
- blind_010 (Zionism 危機): イスラエル戦争政策本体は広範報道、シオニズム構造
  批判は未報道 → stream_1_5
- cls-204a683f73ee_7K (Gaza 7-K): blind_004 と同形 → stream_1_5
- cls-6be4fc09d9ed (Insider trading): 米イラン合意本体は Tier 1-2 報道済み、
  TACO トレード疑惑は未報道 → stream_1_5
- cls-a4132ec7d949 (Met Police): デモ自体は周辺報道、警視庁トップへの法的
  異議申し立ては日本では未報道、と LLM は判定したが、実は事件全体が日本で
  ほぼ無報道に近い可能性あり (kazuya review 対象)

これらは F-particular-angle-design の DISCUSSION_NOTES 観察 1 (golden_set v1.1
stream_2_candidate メタとの差分) と整合する変化で、4 分類化の妥当性を支持する事例。

### 5.2 stream_2 → stream_1_5 への移動 (13 件) ★ 想定外規模

3 分類版で「広範事件は報道済み + 解釈差 = stream_2」と判定されていたが、
4 分類版では LLM が「広範事件は報道済みだが、海外メディアの **特定角度** 自体は
日本主要メディアで未報道 = stream_1_5」と判定。

- 全 covered 系列 9 件 (covered_001/002/003/004/005/007/008/009/010): broad event
  は報道済み、海外メディアの特定角度 (例: 米国忖度の構造分析、新外交秩序の
  解釈) は日本では深掘り未報道 → stream_1_5
- blind_005 (Mandelson Gaza scandal): 人事スキャンダル本体は報道済み、ガザ
  道徳的責任角度は未報道 → stream_1_5
- blind_008 (Israel water as weapon): 水不足は報道済み、武器化フレームは未報道
  → stream_1_5
- cls-7bd1406438b6 (FIFA Palestine): 提訴自体は時事通信報道済み、FIFA 不作為の
  構造的バイアス分析は未報道 → stream_1_5
- cls-33b4f4960bf9_7K (Mandelson 7-K): blind_005 と同形 → stream_1_5

LLM の reasoning は技術的に整合 (「特定角度自体は日本で未報道」)。ただし、これが
4 分類定義の **厳密適用** の必然的帰結なのか、LLM が「stream_2 (= 解釈差) を選ぶ
基準が厳しすぎる」傾向を持つ集約バイアスなのかは、カズヤレビューで再評価する
必要がある。

### 5.3 不変 (5 件)

- 系統 1 のまま (4 件): blind_001 / blind_003 / blind_007 / cls-0c7fa7c667d6
  (ロシア焼身) — 全て『広範事件も特定角度も日本で未報道』という判定が維持
- 動画化対象外のまま (1 件): covered_006 (NVIDIA 株) — 4 軸該当なし

## 6. 4 分類最終分布 (LLM 推定段階、カズヤレビュー前)

### 系統 1 (silence_gap) - 4 件

- blind_001 (golden_set_v1.1): Ukrainian Forces Wounded, Killed 1,725 Civilians in Q1 2026
- blind_003 (golden_set_v1.1): US-Israel intervention frees Israeli-Turkish citizen held for serving in Israeli army
- blind_007 (golden_set_v1.1): Putin ally's $500 million Russian superyacht sails through Hormuz despite US blockade
- cls-0c7fa7c667d6 (trial_run_2026-05-07): Russian man sets himself on fire at war memorial on anniversary of Ukraine invasion, authorities suppress news of it

### 系統 1.5 (perspective_gap) ★ NEW - 20 件

- blind_002 / blind_004 / blind_005 / blind_008 / blind_009 / blind_010
- covered_001 / covered_002 / covered_003 / covered_004 / covered_005 /
  covered_007 / covered_008 / covered_009 / covered_010
- cls-7bd1406438b6 (FIFA 7-K) / cls-33b4f4960bf9_7K (Mandelson 7-K) /
  cls-204a683f73ee_7K (Gaza 7-K) / cls-6be4fc09d9ed (Insider trading) /
  cls-a4132ec7d949 (Met Police)

### 系統 2 (framing_inversion) - 0 件 ★ 想定外

(LLM 推定段階で 0 件、想定 13 件)

### 動画化対象外 - 1 件

- covered_006 (golden_set_v1.1): NVIDIA 株が半年ぶり最高値更新 衰えぬ AI 需要

## 7. F-stream-2-filter-design への引き継ぎ

### 7.1 想定外結果が示唆すること

LLM 推定段階で stream_2 が 0 件という結果は、F-stream-2-filter-design の責務
範囲に大きな影響を持つ。可能性は 2 通り:

1. **本当に系統 2 候補がほぼ存在しない**: 4 分類定義を厳密適用すると、Hydrangea
   が動画化したい海外メディア記事のほぼ全てが stream_1 / stream_1_5 になり、
   stream_2 (= 特定角度自体は報道済み + 解釈差) は極めて稀。F-stream-2-filter-design
   の責務範囲は 25 件中 0-数件まで縮小し、開発優先度は F-jp-coverage-tune
   (二段階クエリ生成、stream_1 vs stream_1_5 判別) より大幅に低くなる。
2. **LLM の集約バイアス**: LLM が「stream_2 を選ぶ基準」を厳しく取りすぎており、
   実態は stream_2 候補が複数存在する。カズヤレビューで stream_2 に再分類される
   ケース次第で、F-stream-2-filter-design の責務範囲が再評価される。

カズヤレビュー結果次第で F-stream-2-filter-design の優先度・スコープが変わる
可能性があるため、本バッチ完了後は **カズヤレビュー結果を待ってから**
F-stream-2-filter-design の着手を判断するのが望ましい。

### 7.2 4 分類前提の責務縮小

仮にカズヤレビュー後も stream_2 が 1-2 件しかない場合:
- F-stream-2-filter-design は **小規模実装** で済む (新規 LLM 解説価値判定 1 段
  のみ、ゴールデンセットも数件)
- F-jp-coverage-tune の二段階クエリ生成 (stream_1 vs stream_1_5 判別) が **より
  優先** される

仮にカズヤレビューで stream_2 が 5-10 件まで増えれば:
- F-stream-2-filter-design は当初想定通りの規模で実装

## 8. F-jp-coverage-tune への引き継ぎ

### 8.1 二段階クエリ生成の必要性

4 分類版では『広範事件報道状態』と『特定角度報道状態』を **独立判定** する設計
を採用したため、F-13.B の現実装 (`title + 日本 報道` 形式の 1 段階クエリ) では
両方を区別できない。F-jp-coverage-tune では:

- **広範事件クエリ**: title + 日本主要メディアキーワード (例: NHK 朝日 日経) で
  Grounding 検索 → Tier 1-4 の WL ヒット有無を判定
- **特定角度クエリ**: particular_angle.core_question を LLM で日本語キーワード
  に圧縮 → 同じ Grounding 検索 → 別途 WL ヒット有無を判定
- 両者の組み合わせで系統 1 / 系統 1.5 を機械的に分類

### 8.2 本バッチが提供する真値

- `docs/runs/F-particular-angle-design/annotations.json` (4 分類版): 各 event の
  `stream_classification_estimate` に加えて新フィールド
  `broad_event_jp_coverage` (reported / unreported / unknown) と
  `particular_angle_jp_coverage` (同) が記録されている。これは F-jp-coverage-tune
  の二段階クエリ生成の精度評価に使える真値データ。
- `docs/runs/F-particular-angle-redesign/reclassification_log.json`: 1 件ごとの
  実行ログ (timing / before-after / success フラグ)、F-jp-coverage-tune 着手時の
  参考データ。

## 9. 想定外結果と次バッチへの影響

### 9.1 stream_2 = 0 件、stream_1_5 = 20 件という結果の解釈

LLM の reasoning を 5 件サンプリング確認した結果、判定は **技術的には整合** している:

- covered_002 (米ロ停戦): 「広範事件であるトランプ氏とプーチン氏の接触や停戦案
  の存在は日本の主要メディアでも報じられている。しかし、この動きがバイデン政権
  をバイパスし既存のG7合意や国際秩序を根底から破壊するという『外交的正当性と
  構造的影響』に関する踏み込んだ特定角度の分析は、日本国内では殆ど見られず
  中立的な事実報道に留まっている。」
- blind_007 (Putin ヨット): 「広範事件である『ロシア大富豪のヨットがホルムズ海峡
  を通過した事実』自体が、日本の主要メディアではほとんど報じられておらず、
  情報の空白状態にある。」

つまり LLM は 4 分類定義を厳密に適用した結果として、

- 「広範事件は報道済み + 海外メディアの特定角度は (異なるフレーミングで) 報道済み」
  という stream_2 のケースを **ほぼ識別できていない**
- 代わりに「広範事件は報道済み + 海外メディアの特定角度自体が日本では未報道」
  と判定し stream_1_5 に集約している

### 9.2 これは LLM の集約バイアスか、4 分類定義の必然的帰結か

カズヤレビューで判断すべき論点:

- **集約バイアス説**: LLM は「特定角度の解釈差 (stream_2) を識別する」より
  「特定角度の不在 (stream_1_5) を識別する」方が易しいため、迷ったら
  stream_1_5 を選ぶ傾向。プロンプト改善で stream_2 識別を強化する余地あり。
- **必然的帰結説**: 海外メディアの特定角度 (例: MEE オピニオン記事の構造分析)
  は、その視点自体が日本主要メディアで報道されていないことが多い。同じ視点を
  日本メディアが取り上げて、かつ異なる解釈で論じるケース (= 厳密な stream_2)
  は実態として稀。3 分類版の stream_2 = 「広範事件レベルでの解釈差」だったため
  数が多く見えたが、4 分類化で正しく『特定角度レベル』に絞ると 0 になるのは
  むしろ正しい構造化。

結論: カズヤレビュー結果を踏まえて、(a) 4 分類定義の境界条件を再考するか、
(b) F-stream-2-filter-design のスコープを見直すかを判断する。本バッチでは
記録のみとし、勝手なプロンプト調整は行わなかった (BATCH PROMPT 想定外結果
ガイドラインに従う)。

### 9.3 後続バッチへの影響

- **F-stream-2-filter-design**: カズヤレビュー結果を待って着手判断 (スコープ
  縮小の可能性あり)
- **F-jp-coverage-tune**: 本バッチの 4 分類アノテーション + broad_event /
  particular_angle 別の jp_coverage 真値が揃ったため、二段階クエリ生成の
  精度評価基盤が確立。優先度は本バッチで **相対的に上昇**

## 10. ★ Task E (カズヤレビュー) 待ち

本バッチは Task E (カズヤレビュー) で一旦停止。Claude Code は Task F の
`scripts/finalize_annotations.py` を 4 分類対応 (`--schema-version 2.0`) に
改修済み + Task G (本レポート + ドッグフーディング) を完了させた状態で停止する。

カズヤがレビュー完了後に以下を実行:

```bash
python scripts/finalize_annotations.py \
    --input docs/runs/F-particular-angle-design/annotations.json \
    --output-diff docs/runs/F-particular-angle-design/annotation_diff.json \
    --output-classification docs/runs/F-particular-angle-design/stream_classification.json \
    --update-golden-set docs/runs/F-verify-jp-coverage/golden_set.json \
    --schema-version 2.0
```

その後、カズヤが Claude Code に「F-particular-angle-redesign Task F (finalize)
実行完了、REPORT 補足更新お願い」と指示する想定。

## 11. 整合性検証

- baseline テスト数: 1345 passed 維持 (本バッチは scripts/ + docs/ のみ変更、
  src/ tests/ configs/ への変更なし、テスト影響なし)
- 不変原則違反: なし (新規スクリプト 2 本 + docs 改訂のみ)
  - 新規: `scripts/reclassify_annotations.py` / `scripts/generate_review_draft_v2.py`
  - 改修: `scripts/finalize_annotations.py` (`--schema-version` 引数追加 + 4 分類
    対応関数追加、3 分類対応関数も保持)
  - 改訂: `docs/PARTICULAR_ANGLE_DEFINITION.md` (3 分類 → 4 分類化)
  - 新規 docs: `docs/runs/F-particular-angle-redesign/` 配下
- main HEAD コミット (本バッチ着手時): `c469084` (F-particular-angle-design-followup マージ後)

## 12. Task 別の実施結果

| Task | 状態 | 主要成果物 |
|---|---|---|
| A | ✅ | `docs/PARTICULAR_ANGLE_DEFINITION.md` 改訂 (3 分類 → 4 分類、新サブセクション 1.1 / 3.5 追加) |
| B | ✅ | `scripts/reclassify_annotations.py` (新規、resume + incremental save + per-call timeout 90s) |
| C | ✅ | `annotations.json` (4 分類版、stream_1=4 / stream_1_5=20 / stream_2=0 / out_of_scope=1)、`reclassification_diff.json` / `reclassification_log.json` |
| D | ✅ | `review_draft_v2.md` (重点レビュー: 3 分類 → 4 分類で変更があった events 20 件を冒頭表示) |
| E | ★ 待ち | カズヤ手動レビュー (本バッチ内では未実行) |
| F | ✅ | `scripts/finalize_annotations.py` 改修 (`--schema-version 2.0` 追加、4 分類対応関数 + 3 分類対応関数を併存) |
| G | ✅ | 本レポート + DECISION_LOG (新エントリ) + FUTURE_WORK (本バッチを完了済みに移動) + DISCUSSION_NOTES (既存 4 エントリ更新) + CURRENT_STATE 全置換更新 |

## 13. カズヤ確認推奨事項

- 4 分類最終分布の妥当性 (★ 特に stream_2 = 0 件、stream_1_5 = 20 件という結果)
- stream_1 → stream_1_5 への移動 7 件 (blind_002/004/009/010 + 試運転 3 件) の判定妥当性
- stream_2 → stream_1_5 への移動 13 件 (covered 系列 9 件 + blind_005/008 + 試運転
  cls-7bd1406438b6/cls-33b4f4960bf9_7K) の判定妥当性 — ★ ここが最大の論点
- 台本表現ガイドライン (PARTICULAR_ANGLE_DEFINITION.md セクション 3.5) の方向性合意
- F-stream-2-filter-design の責務スコープ縮小判断 (stream_2 候補が極小なら設計変更)
- F-jp-coverage-tune の優先度上昇判断 (二段階クエリ生成が stream_1 vs 1.5 判別の
  鍵)

---

## 11. 拡張作業 (2026-05-08): F-particular-angle-redesign-extension

### 11.1 背景 — カズヤレビュー時の 3 つの本質的指摘

F-particular-angle-redesign 完了後の Task E カズヤレビュー過程で、カズヤから
本質的な指摘が 3 件提示された:

1. **命名整理**: 「1.5 という命名は時間的経緯の痕跡。定常状態の命名としては
   不適切。1.5 じゃなくてそれが 2 で、今までの 2 が 3」
2. **忖度シグナルの独立化**: 「忖度・報道規制・黙殺の構造」を系統判定に
   組み込むと MECE が崩れる。系統判定は『報道状態』軸のみで MECE 化し、
   忖度シグナルは別軸 (メタデータフィールド) で扱う
3. **各論コントロール回避**: ジレンマ解説等のルール追加は記事品質劣化の
   リスク、article_writer.py / script_writer.py の自由度阻害、LLM の
   知性発揮を抑制。ドキュメント化せず LLM に委ねる

これらを反映するため、F-particular-angle-redesign の **拡張作業** として
本セクション (Task A-F) を実施した。新規 commit + push で対応、コード変更
なし (src/ tests/ configs/ への変更なし)。

### 11.2 系統名 1/1.5/2 → 1/2/3 のリネーム (Task A-C)

機械的リネームを以下に実施:
- 系統 1.5 → **系統 2** (perspective_gap、旧名表記は legacy エントリと
  記載済みの歴史的記録のみ残す)
- 系統 2 → **系統 3** (framing_inversion、同上)
- `stream_1_5_perspective_gap` → `stream_2_perspective_gap`
- `stream_2_framing_inversion` → `stream_3_framing_inversion`

対象ファイル:
- `docs/PARTICULAR_ANGLE_DEFINITION.md` (Task A): 全面リネーム + Step 3-4
  改良 + MECE 判別基準新設 (3.5) + sontaku_signals 新設 (3.6) + 既存 3.5
  を 3.7 にリナンバー
- `scripts/reclassify_annotations.py` (Task B): 命名 + LLM プロンプト Step
  0-4 改良反映
- `scripts/generate_review_draft_v2.py` (Task B): `_stream_label` ラベル更新
- `scripts/finalize_annotations.py` (Task B): `_VALID_STREAMS_V2` 定数更新
- `docs/runs/F-particular-angle-design/annotations.json` (Task C):
  schema_version 2.0 → 2.1 (`previous_schema_version=2.0` 記録)、25 件中
  20 件の `estimated_stream` 値更新、`legacy_stream_classification_v1` は
  3 分類版の歴史的記録として保持

リネーム後の 25 件 LLM 推定段階分布 (新命名):
- 系統 1 (silence_gap): 4 件
- 系統 2 (perspective_gap、★ 旧 1.5): 20 件
- 系統 3 (framing_inversion、★ 旧 2): 0 件
- 動画化対象外: 1 件

### 11.3 忖度シグナル (sontaku_signals) メタデータ独立化 (Task D)

`sontaku_signals` を **系統判定とは独立な別軸メタデータ** として正典化
(`docs/PARTICULAR_ANGLE_DEFINITION.md` セクション 3.6)。

メタデータ構造:
```python
sontaku_signals = {
    "level": "high" | "medium" | "low" | "none",
    "type": "diplomatic" | "domestic" | "media_industry" | None,
    "reasoning": "<忖度の構造的説明、1-2 文>",
    "extraction_confidence": "high" | "medium" | "low",
}
```

`scripts/add_sontaku_signals.py` を新規追加し、既存 `_build_extract_client()`
方式 (max_output_tokens=4096) + per-call timeout 90 秒 + incremental save
1 件ごと + resume を流用して 25 件分の sontaku_signals を LLM 推定生成した。
判定基準 LLM プロンプトは PARTICULAR_ANGLE_DEFINITION.md セクション 3.6 に
従う。

LLM 推定結果サマリ (25 件):
- level 分布 / type 分布 / extraction_confidence 分布の詳細は
  `docs/runs/F-particular-angle-redesign/extension_log.json` を参照
- annotations.json schema_version 2.1、各 event に `sontaku_signals` フィールド
  が付与され、`kazuya_review` に `sontaku_signals_revised: null` スロット
  追加 (カズヤレビュー対象)

F-stream-2-filter-design (系統 3 担当) + F-jp-coverage-tune (系統 1 vs 系統 2
判別) で参照する独立軸メタデータとして整備完了。

### 11.4 クラウド誤り 9 (各論コントロールへの誘惑) 記録 (Task E)

「視聴者ファースト 3 原則 + ジレンマ解説 + 忖度明示 + 台本表現ルール等の
具体的指針をプロンプトやドキュメントに追加したくなる傾向」をクラウド誤り 9
として記録、再発防止策を確立:

- `CLAUDE.md` に新セクション「クラウド誤り」を導入し、誤り 9 の本文
  (誤り / 動機 / 害 / 正しい設計 / カズヤ哲学 / 運用ルール) を記載
- `docs/DISCUSSION_NOTES.md` に新エントリ「2026-05-08: クラウド誤り 9 —
  各論コントロールへの誘惑」を追加 (Resolved、再発防止策確立)
- `docs/PARTICULAR_ANGLE_DEFINITION.md` セクション 3.7「系統別の台本表現
  の方向性」で「LLM の知性に委ねる」設計哲学を正典化

カズヤ哲学 (2026-05-08): 「いまは各論をコントロールしたくない。記事の質の
悪化避けたいから。これは、分析フェーズの LLM に期待って感じ。」

### 11.5 想定外結果と対応

本拡張バッチでは想定外結果は観察されていない。sontaku_signals 推定結果に
ついて以下の異常検知ロジックを `scripts/add_sontaku_signals.py` に組み込み:

- 全件が同じ level に分類された場合: 警告ログのみ、本バッチでは再実行しない
- 5 件以上が `extraction_confidence=low` の場合: 警告ログのみ、本バッチでは
  対処しない

実際の分布は `docs/runs/F-particular-angle-redesign/extension_log.json`
+ annotations.json `sontaku_signals_summary` を参照 (バッチ仕様 D-5 に従う、
記録のみで勝手にスコープ広げない)。

### 11.6 整合性検証 (拡張バッチ)

- baseline テスト数: 1345 passed 維持 (本拡張バッチは scripts/ + docs/ +
  CLAUDE.md のみ変更、src/ tests/ configs/ への変更なし、テスト影響なし)
- 不変原則違反: なし (新規スクリプト 1 本 + docs 改訂 + CLAUDE.md 改訂のみ)
  - 新規: `scripts/add_sontaku_signals.py`
  - 改訂: `docs/PARTICULAR_ANGLE_DEFINITION.md` (命名 1/2/3 + 3.5 / 3.6 /
    3.7 サブセクション + Step 3-4 改良)、3 scripts (命名リネーム)、
    `docs/runs/F-particular-angle-design/annotations.json` (schema_version
    2.1 + sontaku_signals 付与)、`CLAUDE.md` (クラウド誤り 9 + 最終更新日)、
    DISCUSSION_NOTES.md (新規 2 エントリ + 既存 1 エントリ Resolved 化)
- main HEAD コミット (拡張バッチ着手時): `6b9a1fb` (F-particular-angle-redesign
  マージ後)

### 11.7 Task 別の実施結果 (拡張バッチ)

| Task | 状態 | 主要成果物 |
|---|---|---|
| A | ✅ | `docs/PARTICULAR_ANGLE_DEFINITION.md` 改訂 (命名 1/2/3 + Step 3-4 改良 + 3.5 / 3.6 新設 + 3.7 リナンバー + 1.2 / 1.3 経緯追記) |
| B | ✅ | 3 scripts リネーム (`reclassify_annotations.py` / `generate_review_draft_v2.py` / `finalize_annotations.py`) |
| C | ✅ | `annotations.json` 命名リネーム + schema_version 2.0 → 2.1 (`previous_schema_version=2.0` 記録、25 件中 20 件 `estimated_stream` 値更新) |
| D | ✅ | `scripts/add_sontaku_signals.py` 新規 + 25 件 LLM 推定生成 + `extension_log.json` |
| E | ✅ | `CLAUDE.md` に「クラウド誤り」セクション新設 + 誤り 9 記載 + DISCUSSION_NOTES.md にエントリ追加 |
| F | ✅ | 本 REPORT セクション 11 + DECISION_LOG (新エントリ) + FUTURE_WORK + DISCUSSION_NOTES (3 エントリ) + CURRENT_STATE 全置換更新 |

### 11.8 Task E (★ 旧、4 分類版カズヤレビュー) の状態

本拡張バッチ完了後、F-particular-angle-redesign の **Task E** (4 分類版
カズヤレビュー) は **新分類体系 (1/2/3) + sontaku_signals メタデータ付き** で
実施することになる。本拡張バッチでは Task E (カズヤレビュー) は実行せず、
レビュー準備完了状態で停止する。

カズヤがレビュー完了後に以下を実行する想定:

```bash
python scripts/finalize_annotations.py \
    --input docs/runs/F-particular-angle-design/annotations.json \
    --output-diff docs/runs/F-particular-angle-design/annotation_diff.json \
    --output-classification docs/runs/F-particular-angle-design/stream_classification.json \
    --update-golden-set docs/runs/F-verify-jp-coverage/golden_set.json \
    --schema-version 2.0
```

### 11.9 カズヤ確認推奨事項 (拡張バッチ)

- 改良版定義 (`docs/PARTICULAR_ANGLE_DEFINITION.md` セクション 3 + 3.5 +
  3.6 + 3.7) の妥当性
- sontaku_signals 推定値の妥当性 (level / type の分布と個別事象、25 件)
- クラウド誤り 9 記録の表現 (CLAUDE.md + DISCUSSION_NOTES)
- Task E (4 分類版カズヤレビュー) の進め方 (新分類 1/2/3 +
  sontaku_signals 込みで実施)

---

## 12. Task E カズヤレビュー実施結果 (F-task-e-finalize / 2026-05-08)

### 12.1 レビュー方式

クラウド (claude.ai 側) との **対話形式** で 25 件全件を横断レビュー。クラウド
が観点 A (stream_classification) / B (particular_angle) / C (sontaku_signals)
/ D (横断的気づき) で論点を整理し、3 カテゴリに分類:

- **[A] 即承認** (12 件): LLM 推定値で問題なし、流し見で OK
- **[B] 要判断** (8 件): 境界事例、カズヤの判断が必要
- **[C] 修正推奨** (5 件): 明確な問題あり、修正候補あり

### 12.2 レビュー結果

**25 件全件、`kazuya_review.*_revised` フィールドは null のまま** (= LLM
推定値そのまま正本化)。カテゴリ別:

- [A] 12 件: 全件 LLM 推定どおり
- [B] 8 件: 全件 LLM 推定どおり (B-3 重複事象は揃えず両方 LLM 推定維持)
- [C] 5 件: 4 件 LLM 推定どおり + 1 件は重複問題として記録のみ

詳細は `docs/DISCUSSION_NOTES.md` 関連エントリ参照。

### 12.3 確立された運用原則 (4 件、F-task-e-finalize で docs 化)

1. **「揃える必然性なし」原則**: LLM が同パターンで違う level を返したら、
   それは判定揺れではなくデータの実態
2. **「sontaku_signals は嘘をつかない設計、疑わしきは低く見積もる」運用原則**:
   過大主張は信頼性損失のリスク、取りこぼしは採点側で寛容にカバー
3. **「LLM の知性に委ねる」原則**: カズヤが判別不能なら LLM 推定を採用、
   Hydrangea コアバリュー
4. **「観点の選択的欠落 = 忖度」判定軸**: 主要扱い事象なのに特定角度だけ
   抜ける場合は、リソース不足ではなく忖度

### 12.4 発覚した構造的問題 (1 件)

- **試運転と golden_set の重複サンプリング**: 25 件中 2 ペア (4 件) が
  同一 MEE 記事の重複 = 独立件数は実質 23 件
  - blind_005 ⇄ cls-33b4f4960bf9_7K
  - blind_004 ⇄ cls-204a683f73ee_7K
- 後続バッチで真値として使うとき独立件数を誤認するリスク、本バッチでは
  記録のみ

### 12.5 (c) サンプル選定バイアス仮説の証拠強化

F-extension-followup で記録した (c) 仮説は、本レビュー結果で裏付けられた:
- カズヤレビューを経ても stream_3 に再分類される件は 0 件
- 25 件のサンプルは「海外メディア独自視点」事象中心で、日本メディア起点の
  評価軸を持つ事象 (= 真の系統 3 候補) が偶然含まれていなかった
- 根本治療は Phase A.5-3b 第二作のサンプル拡充 (処理水放出 / 辺野古 等)

### 12.6 finalize_annotations.py 実行結果

`python scripts/finalize_annotations.py --schema-version 2.0 ...` 実行で
以下を生成:
- `docs/runs/F-particular-angle-design/annotation_diff.json`:
  `fully_unmodified_count=25` (全件 LLM 推定維持)
- `docs/runs/F-particular-angle-design/stream_classification.json`:
  counts は LLM 推定分布と完全一致 (`stream_1=4 / stream_2=20 / stream_3=0
  / out=1`)
- `docs/runs/F-verify-jp-coverage/golden_set.json`: 19 件更新 (試運転由来
  6 件は対象外)、各 event に `final_sontaku_signals_source=llm_estimate`

### 12.7 後続バッチへの含意

- **F-jp-coverage-tune** (★最優先): 真値 25 件 + sontaku_signals 真値整備
  完了 + 重複問題の認識共有で、二段階クエリ生成の精度評価が可能な状態
- **F-stream-2-filter-design** (★ 責務スコープ要再評価): stream_3 = 0 件
  確定により小規模実装で済む可能性が高い、Phase A.5-3b 第二作のサンプル
  拡充後に再評価
- **Phase A.5-3b 第二作**: 系統 3 事象 (処理水放出 / 辺野古 等) のサンプル
  拡充で (c) 仮説検証 + 系統 3 台本表現の試行錯誤を兼ねる
- **F-1 EditorialMissionFilter** (将来検討): sontaku_signals.level=high/medium
  を優先採点する設計時、本バッチの 4 つの運用原則を設計レビューで参照

---

*このレポートは F-particular-angle-redesign (2026-05-07 〜 2026-05-08) +
拡張作業 F-particular-angle-redesign-extension (2026-05-08) の実行結果を
記録したもの。Task E (カズヤレビュー) 待ちで一旦停止し、レビュー後に
`scripts/finalize_annotations.py --schema-version 2.0` 実行 → 本レポート
補足更新 → 後続バッチ判断、というフロー。両バッチとも src/ tests/ configs/
一切変更なしの docs + scripts (+ CLAUDE.md) 改訂のみで、baseline 1345
passed 維持。*
