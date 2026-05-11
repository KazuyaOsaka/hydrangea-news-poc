# F-jp-coverage-tune-followup REPORT

最終更新: 2026-05-09 (Step A+B+C 完了、Step D スキップでカズヤ判断、Step E ドッグフーディング完了)

## 概要

F-jp-coverage-tune (2026-05-09, commit `beb4aa7`/merge `82ce0d0`) の post-tuning
verdict=fail (Recall covered 42.11% / Precision blind 26.67% / F1 0.5926 / Tier 一致率 62.50%)
を受け、verdict=fail の根本原因を 3 つに分解 (= WL サブドメイン不一致 / WL 漏れ準大手 /
Grounding API 構造的限界) し、本バッチで前 2 つを根本治療した。

結果: **Recall covered +47.36pp / F1 covered +27.92pp 改善 + F1 covered 0.8718 で
threshold 0.85 を初突破**、verdict=fail のまま (Recall 0.53pp 不足 / Precision blind /
Tier 一致率 / Stream accuracy が未達) だが、根本原因の半分以上を解消した大幅改善。

残課題は (a) Recall 90% 突破 / (b) Precision blind 真値母数問題 / (c) Tier 一致率
Grounding 非決定性 / (d) Stream accuracy stream_3 過剰検出 の 4 つに分離して
FUTURE_WORK に記録。

## 実装内容

### Step A: WL サブドメイン不一致修正

`src/triage/jp_coverage_verifier.py` の `_match_whitelist()` ドメイン判定を
**substring match → ドメイン階層判定** に置換。

新規モジュール関数 `_domain_matches_hierarchy(host, wl_domain)` 追加:
- 完全一致: `host == wl_domain`
- host が wl の子孫: `host.endswith("." + wl_domain)`
- wl が host の子孫: `wl_domain.endswith("." + host)`
のいずれかでマッチ。TLD 共通だけ (`co.jp` 同士) や文字列部分一致
(`not-nikkei.com` vs `nikkei.com`) はマッチしない (= "." 区切り階層関係のみ判定)。

`_match_whitelist()` 自体は host 抽出 (`_normalize_domain` 流用) + 階層判定への
置換のみで、Tier 優先度 / 重複除去ロジックは不変。

### Step B: WL 拡張 (確定 3 ドメイン)

`JP_MEDIA_WHITELIST` 定数に以下を追加:
- Tier 2 (通信社・国際メディア日本版): `afpbb.com` (AFP 通信日本版)
- Tier 4 (大手ビジネス・国際情勢メディア): `forbesjapan.com` / `nippon.com`

判定基準 3 つ全部満たすことを確認: 発行元独立性 / 取材リソース / 大手認知度。

議論余地 2 件 (`arabnews.jp` / `chosunonline.com`) は **本バッチで保留**。WL 整備
で大幅改善した今、追加効果は限定的 + 退行リスクあり、後続バッチで判断する方針
(カズヤ判断、CP-3 中)。

### Step C: 中間再測定 + CP-3

`scripts/measure_two_stage_accuracy.py` を独立 23 件で再実行 (重複 2 ペア除外:
blind_005 / blind_004 採用)。結果は `docs/runs/F-jp-coverage-tune-followup/measurement_result_step_c.json`
+ per-event ログ 23 件 (`logs/<event_id>.log`)。

**4 指標 vs F-jp-coverage-tune post-tuning**:

| 指標 | post-tune (旧) | step_c (本バッチ) | 差分 | threshold | 判定 |
|---|---|---|---|---|---|
| Recall covered | 0.4211 (8/19) | **0.8947 (17/19)** | **+0.4736** | 0.90 | ✗ (0.53pp 不足) |
| Precision covered | 1.0000 | 0.8500 | -0.1500 | — | informational |
| F1 covered | 0.5926 | **0.8718** | **+0.2792** | 0.85 | **✓** ★ 初突破 |
| Precision blind | 0.2667 | 0.3333 | +0.0666 | 0.80 | ✗ |
| Recall blind | 1.0000 | 0.2500 | -0.7500 | — | informational |
| Tier 一致率 | 0.6250 (5/8) | 0.3077 (4/13) | -0.3173 | 0.70 | ✗ |
| Stream accuracy (info) | 0.2727 (6/22) | 0.0909 (2/22) | -0.1818 | — | informational |

**confusion** (post-tune → step_c): TP=8→17 (+9) / FN=11→2 (-9) / TN=4→1 (-3) / FP=0→3 (+3)。

**verdict: fail** (recall_covered / precision_blind / tier_accuracy 未達)。
ただし F1 covered が threshold を初突破。

### Step D スキップ判定 (★ カズヤ判断)

CP-3 中間レポートを提示後、カズヤから「Step D スキップで Step E へ進んで OK」と判断。

判断根拠 (カズヤ提示):
1. 「対症療法じゃなく根本治療」原則: WL 整備で大半が解消されたことが分かった現状を確定させる方が筋
2. Step D は Recall 0.53pp 不足を埋めるためだけのコスト (60-90 分 + API 4 倍) としては大きすぎる
3. Step D 実施しても Precision blind 80% / Tier 一致率 70% には到達しない (= verdict=pass 確定しない)
4. F1 covered 0.8718 突破は本バッチの十分な成果として確定させたい
5. 残課題はそれぞれ別の問題で、1 バッチで全部解決すべきではない (= 個別の根本治療を別バッチで)

### Step E: ドッグフーディング

BATCH_PROTOCOL Task 1-5 を全件実施 (本 REPORT 含む):
- DECISION_LOG エントリ追加
- FUTURE_WORK 完了済み移動 + 4 つの残課題分離追加
- DISCUSSION_NOTES「Grounding API 構造的限界」エントリを部分的解消で更新 + ステータス整理
- CURRENT_STATE 全置換更新 (1-G' 行追加 + F-13.B 防衛機構行に WL 改修反映)

## 改善した event (broad FN→TP、9 件)

| event_id | truth | post-tune | step_c | マッチ理由 |
|---|---|---|---|---|
| blind_004 | reported (Gaza 電力) | FN | TP | tier_2_wire_service マッチ |
| blind_005 | reported (Starmer Gaza) | FN | TP | tier_2_wire_service マッチ |
| blind_008 | reported (Israel water weapon) | FN | TP | tier_4_business マッチ |
| covered_006 | reported (NVIDIA 株) | FN | TP | tier_4_business マッチ (forbesjapan?) |
| covered_007 | reported (ナイジェリア拉致) | FN | TP | tier_4_business マッチ |
| covered_010 | reported (フーシ派 イラン支援表明) | FN | TP | tier_4_business マッチ |
| cls-7bd1406438b6 | reported (FIFA Palestine) | FN | TP | tier_2_wire_service マッチ |
| cls-6be4fc09d9ed | reported (Insider trading) | FN | TP | tier_4_business マッチ |
| cls-a4132ec7d949 | reported (Met Police synagogue) | FN | TP | tier_2_wire_service マッチ |

→ いずれも WL 拡張 (forbesjapan/nippon/afpbb) または サブドメイン吸収 (fnn.jp 等) で
Tier 2/4 マッチが成立した結果。**仮説通りの効果**。

## 退行した event (broad TN→FP、3 件)

| event_id | truth | post-tune | step_c | マッチドメイン |
|---|---|---|---|---|
| blind_003 | unreported (US-Israel Israeli-Turkish citizen) | TN | FP | nippon.com (新追加) |
| blind_007 | unreported (Putin ヨット Hormuz) | TN | FP | newsweekjapan.jp |
| cls-0c7fa7c667d6 | unreported (ロシア戦争記念碑焼身) | TN | FP | newsweekjapan.jp + afpbb.com (新追加) |

→ Grounding がトピック関連だが Hydrangea 真値定義では「日本未報道」と扱われる事象に
対しても、新追加ドメイン経由でヒット。**WL 拡張のトレードオフ**。これらは真値再評価
の余地もある (newsweekjapan.jp / nippon.com / afpbb.com の記事が本当に「特定角度を
扱った記事」なのか、それとも「広範事件のついで」なのか) が、本バッチでは真値変更せず
FP として計上する保守的方針を維持。

## 残 FN 2 件の構造分析

| event_id | truth | broad URLs | 残 FN 理由 |
|---|---|---|---|
| blind_010 | reported (Zionism crisis 論考) | chosyu-journal.jp / note.com / kobunsha.com (3 件のみ、全非 WL) | 論考型で日本主要メディアが取り上げていない事実上の構造的欠落、**多クエリでも改善困難** |
| covered_003 | reported (米中関税協議 2026/04) | jp.net / jetro.go.jp×2 / recordchina.co.jp / livedoor.com / cistec.or.jp / dir.co.jp / theheadline.jp / global-scm.com (9 件、全非 WL) | 米中関税は日経・朝日等が確実に書いている事象だが、Grounding が政府系 (jetro) / 研究機関 (dir / cistec) / アグリゲータを優先返却。**多クエリ + キーワードバリエーションで主要メディアを引きやすくなる典型ケース** |

## Tier 一致率 / Stream accuracy 退行の解釈

### Tier 一致率 (62.5% → 30.77%)
- 母数が 8 → 13 に増えた (TP 増加で eligible 拡大)
- 新規追加 Tier 2/4 ドメインがマッチ優先度を変える + Grounding API の非決定性で chunk 構成が回ごとに揺れる
- 例: covered_001 / covered_009 が前回 tier_1 → 今回 tier_3 (Grounding 非決定性)、covered_005 が前回 tier_4 → 今回 tier_1 (改善)
- Step D は Tier 一致率改善には貢献しない (直交課題)、別系で議論

### Stream accuracy (27.27% → 9.09%)
- angle 検索も WL 拡張の恩恵を受けて、stream_2 真値の 18 件中 15 件が `stream_3_candidate` に分類
- DISCUSSION_NOTES 既存エントリ「2026-05-09: stream_3 過剰検出 — URL ドメインマッチが特定角度の粒度を区別できない定義レベルの限界」が顕在化
- **本バッチスコープ外**、F-stream-2-filter-design 責務範囲

## 不変原則例外適用の根拠記録

不変原則 3 (`src/triage/` 既存ファイル変更不可) に対し、例外条件 4 つ全部 (バグ修正
+ 既存メソッド完全維持 / データ追加のみ / baseline 維持 / カズヤ承認済) を満たす
ことを確認した上で `src/triage/jp_coverage_verifier.py` への以下を実施:

- Step A: `_match_whitelist()` 内のドメイン判定を **バグ修正** (旧 substring match
  はサブドメイン違いを別エントリ扱いにする実装上の欠陥) として階層判定に置換 +
  新モジュール関数 `_domain_matches_hierarchy()` 追加
- Step B: `JP_MEDIA_WHITELIST` 定数への **データ追加のみ** (3 ドメイン追加、既存
  エントリ削除なし、Tier 構造変更なし)

既存 `verify()` / `verify_two_stage()` / `_search_with_grounding` /
`_search_with_grounding_two_stage` / `_filter_excluded` のシグネチャ・挙動は完全
不変。

## baseline 影響

- baseline 1364 → **1390 passed** (新規 26 件追加、既存 1364 件全件維持)
- 内訳: `tests/test_jp_coverage_verifier_domain_extract.py` に追加
  - `TestDomainMatchesHierarchy`: 9 件 (階層判定の境界条件 + 過剰マッチ排除)
  - `TestWhitelistMatchSubdomainAbsorption`: 8 件 (Tier 3 親ドメイン全 5 種 + 過剰マッチ排除)
  - `TestWhitelistExtension`: 9 件 (3 確定追加ドメイン × Tier 配置 + サブドメイン吸収)

## 残課題 (4 軸に分離して FUTURE_WORK へ)

1. **(a) Recall 90% 突破** = F-jp-coverage-tune-followup-2 候補
   - Step D 相当 (多クエリ並列発行 or 別 API)、ただしカズヤ判断後に着手
   - 残 FN 2 件 (blind_010 / covered_003) のうち covered_003 は多クエリで救済可能性
2. **(b) Precision blind = 真値定義の母数問題**
   - truly unreported 母数 4 件 (blind_001 / blind_003 / blind_007 / cls-0c7fa7c667d6) で
     構造的に precision_blind 80% 達成困難
   - 根本治療: Phase A.5-3b 第二作のサンプル拡充
3. **(c) Tier 一致率 = Grounding 非決定性**
   - 同 event でも回ごとに Grounding 返却 chunk 構成が揺れる、再現性の問題
   - 別軸で議論 (F-jp-coverage-tune-followup-2 別系 or 単独バッチ)
4. **(d) Stream accuracy = stream_3 過剰検出**
   - F-stream-2-filter-design 責務範囲 (角度マッチ後の LLM 解説価値判定で対処)

## 関連ファイル

- 改修:
  - `src/triage/jp_coverage_verifier.py` (`_match_whitelist` 階層判定化 +
    `_domain_matches_hierarchy` 新規 + `JP_MEDIA_WHITELIST` 3 ドメイン追加)
- 追加テスト:
  - `tests/test_jp_coverage_verifier_domain_extract.py` (+26 件)
- 新規ファイル:
  - `docs/runs/F-jp-coverage-tune-followup/REPORT.md` (本ファイル)
  - `docs/runs/F-jp-coverage-tune-followup/measurement_result_step_c.json`
  - `docs/runs/F-jp-coverage-tune-followup/logs/<event_id>.log` × 23 件
- ドキュメント更新:
  - `docs/CURRENT_STATE.md` `docs/DECISION_LOG.md` `docs/FUTURE_WORK.md`
    `docs/DISCUSSION_NOTES.md`

## カズヤ確認推奨事項 (後続バッチで判断)

1. 議論余地 2 ドメイン (`arabnews.jp` / `chosunonline.com`) の採用可否
2. (a) F-jp-coverage-tune-followup-2 着手判断 (多クエリ並列 or 別 API、優先度)
3. (b) Phase A.5-3b 第二作のサンプル拡充タイミング (truly unreported 母数拡充も兼ねる)
4. (c) Tier 一致率の Grounding 非決定性対策 (集約戦略 / 平均化 / 単独バッチ要否)

---

*F-jp-coverage-tune-followup (2026-05-09 完了、verdict=fail)。
WL マッチング階層判定化 + WL 拡張 3 ドメインで Recall covered +47.36pp / F1 +27.92pp
の大幅改善 + F1 covered 0.8718 で threshold 初突破、ただし Recall 0.53pp 不足 +
Precision blind / Tier 一致率 / Stream accuracy 未達で verdict=fail のまま。
残課題 4 軸に分離して FUTURE_WORK に記録、後続バッチで個別根本治療する方針が確定。*
