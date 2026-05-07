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

*このレポートは F-particular-angle-redesign (2026-05-07 〜 2026-05-08) の実行
結果を記録したもの。Task E (カズヤレビュー) 待ちで一旦停止し、レビュー後に
`scripts/finalize_annotations.py --schema-version 2.0` 実行 → 本レポート補足
更新 → 後続バッチ判断、というフロー。本バッチは src/ tests/ configs/ 一切
変更なしの docs + scripts 改訂のみで、baseline 1345 passed 維持。*
