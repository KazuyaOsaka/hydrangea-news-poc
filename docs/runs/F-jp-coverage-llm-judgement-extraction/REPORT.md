# F-jp-coverage-llm-judgement-extraction — 統合 REPORT

最終更新: 2026-05-16 (Task F、カズヤ承認後生成。クラウド web 側協議で選択肢 1
= Task F-G 進行 + merge 確定)

> **一行サマリ**: F-wl-hit-quality-audit Task D で決定的に判明した **LLM
> judgement bypass 問題** の根本治療。Task C-D 初版 B-3 表 (`uncertain→False`)
> が Task E 想定外退行 (Recall 崩壊) を起こし、Task E-fix で B-3' 表
> (`no_match のみ False で覆す`) に修正。B-3' は **WL マッチ条件下で
> Recall 1.0000 / Precision 0.8889** と設計通り機能。ヘッドライン Recall
> (0.4706) は broad Grounding API 非決定性 + Gemini 503 (本バッチスコープ外)
> で薄まる。baseline 1417 passed 維持、既存メソッド contract 完全不変。

---

## 1. バッチ概要 (Task A-G 全体の流れ)

| Task | 内容 | commit |
|---|---|---|
| A-B | 設計仕様 (design_spec.md, B-3 表) + CP-1 カズヤ承認 | (Task B) |
| C-D | dataclass 拡張 + プロンプト改修 + `_parse_llm_judgement` + B-3 表反映 | `e97eea7` |
| E | ゴールデンセット 23 件再測定 → **想定外退行検出** | `f239e13` |
| E-fix-A | `design_spec_v2.md` (B-3' 表) | 本コミット |
| E-fix-B | `jp_coverage_verifier.py` 3 箇所 B-3' 反映 | 本コミット |
| E-fix-C | 既存テスト uncertain ケース期待値修正 | 本コミット |
| E-fix-D | `measure_two_stage_accuracy.py` LLM judgement serialize | 本コミット |
| E-fix-E | baseline 1417 passed 維持確認 | — |
| E-fix-F | ゴールデンセット 23 件再々測定 (v3) | 本コミット |
| CP-3 | 再々測定値提示 + カズヤ判断 (選択肢 1 確定) | — |
| F-G | REPORT + BATCH_PROTOCOL Task 1-5 | 本コミット |

### 重要発見

1. **初版 B-3 (`uncertain→False`) は過剰保守だった**: Gemini response_text は
   報道済み event でも約半数が uncertain (中立文 / キーワード不在)。これを
   全件 False に倒すと WL tier-1 マッチが明確に存在する報道済み event まで
   未報道判定 → Recall 89.47% → 37.50% に崩壊 (Task E)。
2. **B-3' (`no_match のみ False で覆す`) が正しい運用**: LLM が明確に否定した
   時のみ安全装置として WL マッチを覆す。WL マッチ条件下で Recall 1.0 /
   Precision 0.89 と設計通り機能 (後述 §4)。
3. **ヘッドライン Recall は API 非決定性で薄まる**: ゴールデンセット live-API
   計測は run 間で broad Grounding の WL ドメイン返却が大きく変動する。
   v3 run では 11 件の reported event で WL ヒット 0 (うち Gemini 503 が 2)
   = B-3' 判定以前に False。これは本バッチスコープ外の別軸問題
   (→ FUTURE_WORK `F-grounding-determinism-audit` 新規登録)。

---

## 2. 設計仕様 v1 (B-3) と v2 (B-3') の対比

| WL マッチ | LLM judgement | v1 B-3 (Task C-D) | **v2 B-3' (Task E-fix)** |
|---|---|---|---|
| あり | match | True | True |
| あり | no_match | False | **False (維持 = 安全装置)** |
| あり | **uncertain** | **False** | **True ★ 修正** |
| あり | None | True | True |
| なし | 不問 | False | False |

修正の核心: 「疑わしきは低く見積もる」は **LLM 応答の曖昧さ** ではなく
**シグナルが何も無い (WL マッチ無し) 時** に適用すべき原則だった。WL tier-1
マッチが存在する時点で「疑わしい」状態ではない。詳細は
`design_spec_v2.md` §「『LLM の知性に委ねる』原則の解釈見直し」。

---

## 3. 実装差分

### `src/triage/jp_coverage_verifier.py` (不変原則 3 例外条件適用)

3 箇所 (`verify()` / `verify_two_stage()` broad / angle) の判定分岐を統一:

```python
if wl_match:
    if llm_judgement == "no_match":
        has_jp_coverage = False   # ★ LLM 明確否定のみ安全装置として覆す
    else:
        has_jp_coverage = True    # "match" / "uncertain" / None: WL マッチを尊重
else:
    has_jp_coverage = False
```

シグネチャ・戻り値型・dataclass フィールドは完全不変 (B-1 維持方針通り)。

### `scripts/measure_two_stage_accuracy.py` (scripts/ 例外条件適用)

`result_to_dict()` 末尾に optional 4 フィールド追加 (既存呼び出し側影響なし):
`broad_llm_judgement` / `broad_llm_judgement_text` /
`angle_llm_judgement` / `angle_llm_judgement_text`。Task E では未 serialize で
`measurement_run.log` からの事後復元を強いられた構造的事後検証不能を解消。

### `tests/test_jp_coverage_verifier_llm_judgement.py`

`test_wl_match_llm_uncertain_returns_false` →
`test_wl_match_llm_uncertain_returns_true` (期待値 False→True、構造変更なし)。

---

## 4. メトリクス比較 3 段階 + WL マッチ条件下評価 (★ 主軸)

### 4.1 ヘッドライン (ゴールデンセット 23 件全体)

| 指標 | 改修前 Step C | Task E (B-3 旧) | **Task E-fix (B-3') v3** | 閾値 |
|---|---|---|---|---|
| Recall covered | 0.8947 | 0.3750 | 0.4706 | 0.90 |
| Precision blind | 0.3333 | 0.2308 | 0.2500 | 0.80 |
| F1 covered | 0.8718 | 0.5455 | 0.6154 | 0.85 |
| Tier accuracy | 0.3077 | 0.2000 | 0.3333 | 0.70 |
| confusion | TP17/FP3/TN1/FN2 | TP6/FP0/TN3/FN10 | TP8/FP1/TN3/FN9 | — |

ヘッドラインは全閾値未達。**ただし以下の分解が本評価の主軸。**

### 4.2 ★ WL マッチ条件下評価 (B-3' 判定が実走したサブセット = apples-to-apples)

broad WL マッチありの event のみで集計 (= B-3' 判定ロジックが実際に効くケース):

| WL マッチありサブセット | 値 |
|---|---|
| TP=8 / FP=1 / TN=1 / **FN=0** | — |
| **Recall = 1.0000** | Task E は同条件で uncertain→False により誤退行 |
| **Precision = 0.8889** | — |

B-3' は WL マッチが存在する限り **設計通り完璧に機能**。
- 報道済み + uncertain/match → 全件正しく True (blind_004/005, covered_001/002/004/010, cls-7bd1406438b6, cls-6be4fc09d9ed)
- no_match 安全装置も発火: **cls-0c7fa7c667d6** (真値 unreported、WL ヒット 1 + no_match → False = TN) ✓
- 唯一の FP: **blind_001** (真値 unreported、tier_4 単発 WL ヒット + uncertain → True)。B-3' のトレードオフコスト (uncertain を尊重する代償)。

### 4.3 低ヘッドライン Recall の真因 = 上流 broad 検索の API 非決定性

truth=reported なのに取りこぼした 11 件 **全てが「v3 run で broad Grounding が
WL メディアドメインを 1 件も返さなかった」**ケース:

- 検索ミス 9 件: blind_008/009/010, covered_005/006/007/008/009, cls-a4132ec7d949
- Gemini 503 エラー 2 件: blind_002, covered_003 (許容範囲内、閾値 5 件未満)

例: covered_008/009 は Task E run では fnn.jp 等 WL ヒットありだったが、v3 run
では同一クエリで WL ドメインゼロ。これは **ゴールデンセット live-API 計測の
既知の非決定性**で、本改修コードと直交する別軸問題。

---

## 5. LLM judgement 分布 + 退行/改善サンプル分析

### v3 broad LLM judgement 分布 (21 eligible)

uncertain / match / no_match が混在。Task E と同様 uncertain が約半数を占めるが、
**B-3' では uncertain で WL マッチを尊重するため、Task E のような Recall 崩壊は
発生しない** (WL マッチがあれば True、これが §4.2 の FN=0 に直結)。

### Task E 誤退行 (uncertain→False 6 件) の復帰確認

| event | Task E (B-3 旧) | v3 (B-3') | 復帰 |
|---|---|---|---|
| covered_001 | uncertain→False (誤) | wl=2 uncertain→**True** | ✓ クリーン復帰 |
| covered_002 | uncertain→False (誤) | wl=3 tier_1 uncertain→**True** | ✓ クリーン復帰 |
| covered_004 | uncertain→False (誤) | wl=2 uncertain→**True** | ✓ クリーン復帰 |
| covered_007 | uncertain→False (誤) | wl=0 (v3 検索ミス) | △ judgement 修正済だが今 run は WL ヒット無し |
| covered_009 | uncertain→False (誤) | wl=0 (v3 検索ミス) | △ 同上 |
| blind_008 | uncertain→False (誤) | wl=0 (v3 検索ミス) | △ 同上 |

3 件クリーン復帰、残り 3 件は judgement ロジックは修正済だが v3 run の検索
非決定性で WL ヒット 0 になり評価対象外 (= §4.3 の問題)。

### no_match 安全装置の維持確認

cls-0c7fa7c667d6 (真値 unreported): WL ヒット 1 + LLM no_match → False = TN ✓。
Task E の正しい修正 2 件のうち WL マッチ条件下のものは B-3' でも維持。

---

## 6. Task E 想定外退行と Task E-fix 根本治療プロセス (Hydrangea カズヤ哲学運用記録)

本バッチは Hydrangea カズヤ哲学の運用記録として重要な事例:

1. **「無制限自走禁止」**: Task E でゴールデンセット再測定し Recall 崩壊を
   検知した時点で commit/merge せず CP で停止。想定外結果を勝手にスコープを
   広げて取り繕わず、まず記録 (`measurement_result_v2.json` analysis_e4)。
2. **「対症療法じゃなく根本治療」**: B-3 を場当たり的にパッチせず、設計仕様
   レベルで B-3' に修正 (`design_spec_v2.md`)。「LLM の知性に委ねる」原則の
   **解釈そのものを見直した** (uncertain は LLM の曖昧さであって否定ではない)。
3. **クラウド誤り 9 (各論コントロールへの誘惑) の自己適用**: 初版 B-3 の
   `uncertain→False` は「品質保証したい善意」から来た過剰保守で、まさに
   クラウド誤り 9 の構造 (善意の誤りが全体劣化を招く) に該当。Task E-fix で
   この誤りを自己診断し是正した。
4. **CP でカズヤ判断を仰ぐ運用**: ヘッドライン Recall < 80% の想定外結果を
   CP-3 で詳細議論し、WL マッチ条件下評価を主軸に据えた本番反映可否判断を
   カズヤ + クラウド web 側協議で確定 (選択肢 1)。

---

## 7. 残課題 / カズヤ確認推奨事項

- **F-grounding-determinism-audit** (新規、FUTURE_WORK 緊急度 中): Gemini
  Grounding API の WL ドメイン返却率 run 間分散の集約戦略検討。本バッチで
  顕在化したヘッドライン Recall の主因。Phase A.5-3b 第二作と並走可。
- **F-jp-coverage-tune-followup REPORT v2 化**: 本バッチ再測定値が出たため
  統合 v2 化のタイミング。
- **ゴールデンセット v2 化検討**: specific angle level truth annotation。
  broad 検索非決定性問題と合わせて評価軸整備を検討。
- **F-trial-run-post-llm-extraction** (新規、最有力次バッチ候補): 本改修
  本番反映後の試運転。
- **Phase A.5-3b 第一作着手判断**: Slot-1 perspective_gap framing 前提条件。

---

## 8. BATCH_PROTOCOL Task 1-5 適用内容

- **Task 1 (DECISION_LOG)**: 本バッチエントリ追加。不変原則 3 例外条件
  (src/triage) + scripts/ 例外条件の両方を明記。Task E 想定外退行 + Task
  E-fix 根本治療プロセスを Hydrangea カズヤ哲学運用記録として記載。
- **Task 2 (FUTURE_WORK)**: `F-jp-coverage-llm-judgement-extraction` を完了済み
  に移動。新規残課題追加: `F-grounding-determinism-audit` (緊急度 中) /
  `F-trial-run-post-llm-extraction` (最有力次バッチ候補)。
- **Task 3 (REPORT)**: 本セクション。
- **Task 4 (DISCUSSION_NOTES)**: 4-A 新規「『LLM の知性に委ねる』原則の解釈
  見直し」追加。4-B「2026-05-14: F-13.B LLM judgement bypass 問題」エントリ
  ステータス Active → Resolved 更新。
- **Task 5 (CURRENT_STATE)**: 全置換更新 (改修完了 + 次バッチ候補刷新)。

---

*本ドキュメントは F-jp-coverage-llm-judgement-extraction Task F (2026-05-16)
で生成。CP-3 カズヤ + クラウド web 側協議で選択肢 1 確定後に着手。*
