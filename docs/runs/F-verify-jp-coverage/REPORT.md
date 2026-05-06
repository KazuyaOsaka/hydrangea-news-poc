# F-jp-coverage-improve 再測定レポート (v2)

- 実行日時: 2026-05-07T03:12:30
- F-13.B コミット: `b5d571d` (本バッチの修正コミットは未マージ、本レポートは feature/F-jp-coverage-improve の作業ツリー上で取得)
- ゴールデンセット: v1.1 (19 entries)
- Grounding モデル: `gemini-2.5-flash`
- Cache mode: `reuse` (1 周目 fresh で 5 件が 503 UNAVAILABLE、reuse で残存 5 件のみ再試行)

> 旧 v1 (F-verify-jp-coverage-measure / 2026-05-05、verdict=fail / Recall covered 0%) は
> Git history で参照可能。本 v2 は F-jp-coverage-improve (2026-05-07) で
> 構造的不具合 (Grounding redirect URL を WL マッチングに使用) を修正した後の
> 再測定結果を上書き反映している。

## ★ 1.5 根本原因の特定と修正済み報告 (2026-05-07 更新版)

F-verify-jp-coverage-measure (2026-05-05) v1 で 19/19 件 `matched=0`,
`has_jp_coverage=False` という異常パターンを観測し、デバッグで
**Gemini Grounding API の `chunk.web.uri` は実ソースドメインではなく
Vertex AI のリダイレクト URL** であることを特定した
(`vertexaisearch.cloud.google.com/grounding-api-redirect/...`)。
実ドメインは `chunk.web.title` (例: `jiji.com` / `jetro.go.jp` / `recordchina.co.jp`) に
格納されており、`chunk.web.domain` は SDK 現行版で常に None。

### 修正実装 (F-jp-coverage-improve / 2026-05-07)

`src/triage/jp_coverage_verifier.py` にドメイン抽出レイヤーを追加:

- `_extract_domain_from_chunk(chunk)` — フォールバック戦略 (1) `chunk.web.domain` →
  (2) `chunk.web.title` (ドメイン形式チェック付き) で実ドメインを抽出
- `_looks_like_domain(s)` — `^[a-z0-9.-]+\.[a-z]{2,}$` 簡易ヒューリスティック
  (表示名 "Jiji News" 等を弾く)
- `_normalize_domain(s)` — lowercase + プロトコル / パス除去

`_search_with_grounding()` を修正し、`urls.append(f"https://{domain}")` で
実ドメインを WL マッチングに供給。`chunk.web.uri` (redirect URL) は
ログ用に `redirect_urls` に分離記録 (WL マッチングには使わない)。

設計思想: SDK 将来バージョンで `chunk.web.domain` が実値を返すようになっても
透過的に動作する **防御層** として機能。新規テスト 28 件 (戦略 1 / 戦略 2 /
フォールバック / 実 API 観測値での検証) で挙動を担保。

### 修正前後の比較

| 指標 | v1 (修正前) | v2 (修正後) | 変化 |
| --- | --- | --- | --- |
| TP (covered, 一致) | 0 | 10 | +10 |
| FN (報道済→False 誤判定) | 14 | 4 | -10 (大幅改善) |
| TN (blind, 一致) | 5 | 3 | -2 |
| FP (未報道→True 誤判定) | 0 | 2 | +2 |
| Recall (covered) | 0.00% | 71.43% | +71.43pt |
| Precision (blind) | 26.32% | 42.86% | +16.54pt |
| F1 (covered) | 0.000 | 0.769 | +0.769 |
| Tier 一致率 | 0.00% (0/0) | 30.00% (3/10) | +30.00pt |
| stream_2_candidate F-13.B True | 0/4 | 3/4 | +3/4 |

### 残課題 (verdict は v2 でもなお fail)

構造的不具合は解消されたが、4 指標とも閾値未達のため verdict=**fail**。
ただし「ロジックが構造的に常に False を返す」状態 (v1) → 「正しく動くが
精度が閾値未達」状態 (v2) は質的に異なる進捗である。残課題の本質は本バッチの
責務範囲外であり、別バッチで対処すべき:

- **FN 4 件**: Grounding API が Tier 1-2 ソースを返さないクエリ最適化問題
  (検索クエリ改善 / WL ドメイン拡張)
- **FP 2 件 (両方 diamond.jp)**: ゴールデン真値再評価 or Tier 4 weighting 検討
- **Tier 一致率低**: Grounding が Tier 4 (newsweekjapan / toyokeizai / diamond) を
  Tier 1 より先に返す傾向、Tier 判定ロジックは別問題

詳細は本レポート末尾「7. 改善提案」および FUTURE_WORK.md の
F-jp-coverage-tune (新規登録予定) を参照。

## 1. 判定

**Verdict: ❌ **fail** (不合格、ただし構造的不具合は修正完了)**

判定根拠:

| 指標 | 実測値 | 合格基準 | 達成 |
| --- | --- | --- | --- |
| Recall (covered) | 71.43% | >= 90.00% | ❌ |
| Precision (blind) | 42.86% | >= 80.00% | ❌ |
| F1 (covered) | 0.769 | >= 0.85 | ❌ |
| Tier 一致率 | 30.00% | >= 70.00% | ❌ |

## 2. 集計指標

| 指標 | 値 |
| --- | --- |
| Total | 19 |
| TP (covered, 一致) | 10 |
| TN (blind, 一致) | 3 |
| FP (未報道→True 誤判定) | 2 |
| FN (報道済→False 誤判定) | 4 |
| Error (測定不能) | 0 |
| Precision (covered) | 83.33% |
| Recall (covered) | 71.43% |
| F1 (covered) | 0.769 |
| Precision (blind) | 42.86% |
| Recall (blind) | 60.00% |
| Tier 一致率 | 30.00% (3/10) |
| stream_2_candidate F-13.B True | 3/4 |

### 混同行列

|  | Actual True | Actual False | Error |
| --- | --- | --- | --- |
| Expected True (14 件) | 10 | 4 | 0 |
| Expected False (5 件) | 2 | 3 | 0 |

## 3. 誤判定詳細

### 3.1 False Negative (致命的、報道済み → 未報道判定)

| id | title | expected_tier | matched_urls | search_query |
| --- | --- | --- | --- | --- |
| blind_005 | Gaza was the scandal that should have ended Keir S | tier_1_newspaper | 0 urls | Gaza was the scandal that should have ended Keir Starmer's p |
| covered_006 | NVIDIA 株が半年ぶり最高値更新 衰えぬ AI 需要、循環投資にはリスク | tier_1_newspaper | 0 urls | NVIDIA 株が半年ぶり最高値更新 衰えぬ AI 需要、循環投資にはリスク 日本 報道 |
| covered_007 | ナイジェリアで 100 人拉致 過激派襲撃、死者多数か | tier_1_newspaper | 0 urls | ナイジェリアで 100 人拉致 過激派襲撃、死者多数か 日本 報道 |
| covered_009 | インド・パキスタン カシミール 緊張 (4 月 22 日テロ攻撃 + 5 月 7-10 日 Oper | tier_1_newspaper | 0 urls | インド・パキスタン カシミール 緊張 (4 月 22 日テロ攻撃 + 5 月 7-10 日 Operation Sind |

### 3.2 False Positive (機会損失、未報道 → 報道済み判定)

| id | title | actual_matched_tier | matched_domains | search_query |
| --- | --- | --- | --- | --- |
| blind_008 | Israel accused of using 'water as a weapon' agains | tier_4_business | diamond.jp | Israel accused of using 'water as a weapon' against Palestin |
| blind_010 | Israel's policy of endless war is fuelled by the c | tier_4_business | diamond.jp | Israel's policy of endless war is fuelled by the crisis of Z |

### 3.3 Error (測定不能)

- なし ✅

## 4. Tier 判定の精度

| id | expected_tier | actual_matched_tier | 一致 |
| --- | --- | --- | --- |
| blind_002 | tier_1_newspaper | tier_1_newspaper | ✅ |
| blind_004 | tier_1_newspaper | tier_4_business | ❌ |
| blind_009 | tier_2_wire_service | tier_4_business | ❌ |
| covered_001 | tier_1_newspaper | tier_1_newspaper | ✅ |
| covered_002 | tier_1_newspaper | tier_1_newspaper | ✅ |
| covered_003 | tier_1_newspaper | tier_2_wire_service | ❌ |
| covered_004 | tier_1_newspaper | tier_4_business | ❌ |
| covered_005 | tier_1_newspaper | tier_4_business | ❌ |
| covered_008 | tier_1_newspaper | tier_4_business | ❌ |
| covered_010 | tier_2_wire_service | tier_4_business | ❌ |

## 5. stream_2_candidate 4 件の F-13.B 出力

stream_2_candidate メタ付きエントリ (blind_002/004/005/009) は 「広範な事件は Tier 1-2 で報道済み (True 期待)、特定角度は系統 2 候補」というパターン。F-stream-2-filter-design 実装時に系統 2 ターゲット候補として再評価される。

| id | actual | actual_matched_tier | matched_domains | 系統 2 角度 (要約) |
| --- | --- | --- | --- | --- |
| blind_002 | True | tier_1_newspaper | yomiuri.co.jp | イスラエル最高宗教権威『ラビ庁』が軍からの非難要請を拒否した、軍と宗教界の宗教的シオニズム融合という構造分析角度 |
| blind_004 | True | tier_4_business | newsweekjapan.jp | 潤滑油 1L 14 → 1,500 シェケル (100 倍) 暴騰、中小企業 9 割廃業危機、ケーキ店主の生活破綻、ジェネレーター燃料に食用油転用といった『社会 |
| blind_005 | False | None |  | 英国によるガザ向け F-35 部品継続供給、キプロス・アクロティリ基地からの監視飛行情報共有といった『英国の構造的なイスラエル軍事支援』こそが本来の道徳的スキャ |
| blind_009 | True | tier_4_business | toyokeizai.net | イラン革命防衛隊が制裁網下の闇経済から得る既得権益と、それが戦争継続の構造的動機になっているという『継戦の経済的合理性』分析角度 |

## 6. 全件詳細

| id | expected | actual | expected_tier | actual_tier | matched_n | elapsed | cached |
| --- | --- | --- | --- | --- | --- | --- | --- |
| blind_001 | False | False | None | None | 0 | 0.00s | yes |
| blind_002 | True | True | tier_1_newspaper | tier_1_newspaper | 1 | 7.98s | no |
| blind_003 | False | False | None | None | 0 | 4.51s | no |
| blind_004 | True | True | tier_1_newspaper | tier_4_business | 1 | 0.00s | yes |
| blind_005 | True | False | tier_1_newspaper | None | 0 | 8.29s | no |
| blind_007 | False | False | None | None | 0 | 0.01s | yes |
| blind_008 | False | True | None | tier_4_business | 1 | 0.00s | yes |
| blind_009 | True | True | tier_2_wire_service | tier_4_business | 1 | 0.00s | yes |
| blind_010 | False | True | None | tier_4_business | 2 | 0.00s | yes |
| covered_001 | True | True | tier_1_newspaper | tier_1_newspaper | 4 | 0.00s | yes |
| covered_002 | True | True | tier_1_newspaper | tier_1_newspaper | 1 | 0.00s | yes |
| covered_003 | True | True | tier_1_newspaper | tier_2_wire_service | 2 | 0.00s | yes |
| covered_004 | True | True | tier_1_newspaper | tier_4_business | 1 | 8.17s | no |
| covered_005 | True | True | tier_1_newspaper | tier_4_business | 1 | 7.34s | no |
| covered_006 | True | False | tier_1_newspaper | None | 0 | 0.00s | yes |
| covered_007 | True | False | tier_1_newspaper | None | 0 | 0.00s | yes |
| covered_008 | True | True | tier_1_newspaper | tier_4_business | 1 | 0.00s | yes |
| covered_009 | True | False | tier_1_newspaper | None | 0 | 0.00s | yes |
| covered_010 | True | True | tier_2_wire_service | tier_4_business | 2 | 0.00s | yes |

## 7. 改善提案

### 未達指標と該当エントリの傾向

- **recall_covered**: 実測 0.714 < 閾値 0.90 (未達)
- **precision_blind**: 実測 0.429 < 閾値 0.80 (未達)
- **f1_covered**: 実測 0.769 < 閾値 0.85 (未達)
- **tier_accuracy**: 実測 0.300 < 閾値 0.70 (未達)

### FN (4 件) — 報道済みなのに未報道判定

Recall 未達の主因。検索クエリ改善 / WL ドメイン拡張 / Tier 別重み付け等で対処要検討。

- `blind_005` (Gaza was the scandal that should have ended Keir Starmer's p)
  - search_query: `Gaza was the scandal that should have ended Keir Starmer's political career 日本 報道`
  - F-13.B が拾った WL ドメイン: (なし)
  - 真値で確認済み URL (manual): 3 件
- `covered_006` (NVIDIA 株が半年ぶり最高値更新 衰えぬ AI 需要、循環投資にはリスク)
  - search_query: `NVIDIA 株が半年ぶり最高値更新 衰えぬ AI 需要、循環投資にはリスク 日本 報道`
  - F-13.B が拾った WL ドメイン: (なし)
  - 真値で確認済み URL (manual): 4 件
- `covered_007` (ナイジェリアで 100 人拉致 過激派襲撃、死者多数か)
  - search_query: `ナイジェリアで 100 人拉致 過激派襲撃、死者多数か 日本 報道`
  - F-13.B が拾った WL ドメイン: (なし)
  - 真値で確認済み URL (manual): 3 件
- `covered_009` (インド・パキスタン カシミール 緊張 (4 月 22 日テロ攻撃 + 5 月 7-10 日 Operation Sind)
  - search_query: `インド・パキスタン カシミール 緊張 (4 月 22 日テロ攻撃 + 5 月 7-10 日 Operation Sindoor) 日本 報道`
  - F-13.B が拾った WL ドメイン: (なし)
  - 真値で確認済み URL (manual): 2 件

### FP (2 件) — 未報道なのに報道済み判定

Precision (blind) 未達の主因。F-13.B が WL ドメイン以外を WL 扱いしていないか、または擬似マッチング (URL 部分文字列衝突) が発生していないか確認要。

- `blind_008` (Israel accused of using 'water as a weapon' against Palestin)
  - matched_domains: ['diamond.jp']
  - matched_urls (先頭): ['https://diamond.jp']
- `blind_010` (Israel's policy of endless war is fuelled by the crisis of Z)
  - matched_domains: ['diamond.jp']
  - matched_urls (先頭): ['https://diamond.jp', 'https://diamond.jp']

### 推奨アクション

- F-jp-coverage-improve バッチを起動 (緊急度 高に登録)。F-stream-2-filter-design 着手は **保留**。

---

*このレポートは scripts/verify_jp_coverage_measure.py が自動生成。ゴールデンセット v1.1 (19 entries) を真値として F-13.B の精度を実測。*