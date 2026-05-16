# F-jp-coverage-llm-judgement-extraction — 設計仕様 v2 (design_spec_v2.md)

最終更新: 2026-05-16 (Task E-fix-A、B-3' 表確定)

> **本ドキュメントの位置付け**: `design_spec.md` (v1, 2026-05-14 Task B) は
> 歴史的記録として保持。本 v2 は Task E 想定外退行を受けた **B-3 表の修正
> (= B-3')** を確定する。v1 の B-1 / B-2 / B-4〜B-9 (contract 維持方針 /
> パース戦略 / テスト戦略 / プロンプト / 実装手順) は **そのまま有効**。
> 本 v2 は B-3 (WL マッチ × LLM judgement の優先順位) のみを上書きする。

---

## 0. なぜ v2 が必要になったか (Task E 想定外退行)

Task C-D で v1 の B-3 表 (`uncertain → False`) を実装し commit `e97eea7`。
Task E でゴールデンセット 23 件を再測定 (commit `f239e13`、
`measurement_result_v2.json`) した結果、**想定外の Recall 崩壊** を検出:

| メトリクス | 改修前 (Step C) | Task E (B-3 旧) | 想定レンジ | 判定 |
|---|---|---|---|---|
| Recall covered | 0.8947 | **0.3750** | 0.79-0.84 | ✗ 大幅未達 (-51.97pp) |
| Precision blind | 0.3333 | 0.2308 | 0.60-0.70 | ✗ |
| F1 covered | 0.8718 | 0.5455 | 0.78-0.83 | ✗ |

退行内訳 (`analysis_e4.regression_breakdown`):

- 真値 True → 予測 False の退行 **10 件**
  - 正しい修正 (真値 unreported、覆って正解): **2 件** (blind_007 / cls-0c7fa7c667d6)
  - 誤退行 (真値 reported なのに False): **8 件**
    - `uncertain → False` ルール由来: **6 件** ★ 主因
    - `no_match → False` ルール由来: 2 件 (blind_005 / cls-a4132ec7d949)

LLM judgement 分布 (broad、eligible 19 件): uncertain 9 (47.4%) /
match 6 / no_match 4。**uncertain が約半数** を占め、その全件を `False` に
倒したため、WL tier-1 マッチが明確に存在する報道済み event
(covered_001/002/004/009 等) まで未報道判定 → Recall 崩壊。

### 根本原因の構造的理解

v1 B-3 の `uncertain → False (疑わしきは低く)` は「嘘をつかない設計」の
**過剰適用**だった。Gemini の response_text は明確な no_match を返す時もあるが、
**多くの報道済み event でも uncertain (中立文 / キーワード不在)** になる。
WL に tier-1 新聞社の明確なマッチがあるのに「LLM 応答が曖昧だから未報道」と
倒すのは、WL マッチという確度の高いシグナルを LLM 応答の曖昧さで打ち消す
過剰保守であり、クラウド誤り 9「各論コントロールへの誘惑」と同根
(品質保証の善意が全体劣化を招く)。

---

## B-3': WL マッチ × LLM judgement の優先順位 (修正版)

★ **新ルール: WL マッチを基準とし、LLM が明確に「該当しない」(no_match) と
言った時のみ安全装置として覆す。**

| WL マッチ | LLM judgement | 最終 has_jp_coverage | 根拠 |
|---|---|---|---|
| あり | match | **True** (報道済み) | 両方一致 |
| あり | **no_match** | **False (未報道)** ★ | LLM 明確否定のみ安全装置として覆す (本改修で維持する核心) |
| あり | **uncertain** | **True (報道済み)** ★ **修正** | WL マッチを尊重。旧 B-3 (False) は過剰保守で Task E Recall 崩壊の主因 |
| あり | None (パース不能 / 後方互換) | **True (報道済み)** | 既存挙動維持 = 既存テスト群を壊さない |
| なし | (LLM 判定不問) | False (未報道) | 現状維持 |

実装上は分岐を簡潔化:

```python
if wl_match:
    if llm_judgement == "no_match":
        has_jp_coverage = False   # ★ LLM 明確否定のみ安全装置として覆す
    else:
        has_jp_coverage = True    # "match" / "uncertain" / None: WL マッチを尊重
else:
    has_jp_coverage = False
```

broad / angle / verify() の 3 箇所に同一ロジックを適用
(`src/triage/jp_coverage_verifier.py`)。

### B-3'.a 後方互換 (v1 から不変)

`llm_judgement = None` (response_text 抽出不能 / MagicMock) は引き続き
`True` (WL マッチのみで判定)。既存テスト群
(`test_jp_coverage_verifier_two_stage.py` / `_domain_extract.py`) は完全維持。

### B-3'.b verify_two_stage の系統判定 (v1 から不変)

broad_jp_coverage / angle_jp_coverage を B-3' で計算した後、
stream_1/2/3 判定ロジック自体は v1 と同一。no_match による
broad False → stream_1_silence_gap (Step 2 スキップ) は維持。

---

## 「LLM の知性に委ねる」原則の解釈見直し (Hydrangea カズヤ哲学運用記録)

v1 では「LLM の知性に委ねる」を **「LLM が曖昧なら未報道側に倒す」** と解釈
したが、これは誤りだった。正しい解釈:

> **LLM が明確に否定 (no_match) した時のみその判断を尊重して覆す。
> LLM が明確な判断を示さない (uncertain) 場合は、WL マッチという別の確度の
> 高いシグナルを尊重する。**

「疑わしきは低く見積もる」は **LLM 応答の曖昧さ** に適用すべきものではなく、
**シグナルが何も無い (WL マッチ無し) 時** に適用すべき原則だった。WL tier-1
マッチが存在する時点で「疑わしい」状態ではない。

これは Task E 想定外退行を CP で検知し commit/merge せず保留した運用
(Hydrangea「無制限自走禁止」+「対症療法じゃなく根本治療」) の好例として
DECISION_LOG / DISCUSSION_NOTES に記録する (Task G)。

---

## 期待メトリクス (B-3' 適用後、Task E-fix-F で検証)

- Recall covered: **0.875 前後** (改修前 0.8947 に近接、uncertain 6 件が True 復帰)
- Precision blind: 改修前 0.3333 より改善 (no_match 由来 TN 確保)
- F1 covered: **0.80 前後**

想定外閾値 (バッチプロンプト): Recall covered < 0.80 → 設計再々検討要、
CP-3 で詳細議論。

---

*本ドキュメントは F-jp-coverage-llm-judgement-extraction Task E-fix-A
(2026-05-16) で生成。v1 (design_spec.md) は歴史的記録として保持。
バッチプロンプト「対症療法じゃなく根本治療」+「LLM の知性に委ねる」
(過剰保守の反省) +「動くものを壊さない」原則遵守。*
