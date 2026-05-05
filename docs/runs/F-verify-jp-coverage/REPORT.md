# F-verify-jp-coverage-measure 実行レポート

- 実行日時: 2026-05-05T15:05:25
- F-13.B コミット: `20da7c0`
- ゴールデンセット: v1.1 (19 entries)
- Grounding モデル: `gemini-2.5-flash`
- Cache mode: `fresh`

## 1. 判定

**Verdict: ❌ **fail** (不合格)**

判定根拠:

| 指標 | 実測値 | 合格基準 | 達成 |
| --- | --- | --- | --- |
| Recall (covered) | 0.00% | >= 90.00% | ❌ |
| Precision (blind) | 26.32% | >= 80.00% | ❌ |
| F1 (covered) | 0.000 | >= 0.85 | ❌ |
| Tier 一致率 | 0.00% | >= 70.00% | ❌ |

## ★ 1.5 根本原因の特定 (2026-05-05 デバッグ追加)

19/19 件で `matched=0`, `has_jp_coverage=False` という異常パターンを受け、
F-13.B の Grounding URL 抽出ロジックを直接検証した結果、**Gemini Grounding API
が返す `chunk.web.uri` は実ソースドメインではなく Vertex AI のリダイレクト URL
(`vertexaisearch.cloud.google.com/grounding-api-redirect/...`)** であることを確認。

### 検証 (covered_003 米中関税協議で実測)

```
chunk[0].uri    = 'https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE...'
chunk[0].title  = 'jiji.com'         ← 実ドメインはここ (WL Tier 2 該当!)
chunk[0].domain = None               ← 新フィールドは未対応 (常に None)

chunk[1].title  = 'jp.net'
chunk[2].title  = 'dir.co.jp'
chunk[3].title  = 'jetro.go.jp'
chunk[4].title  = 'recordchina.co.jp'
chunk[5].title  = 'recordchina.co.jp'
chunk[6].title  = 'nippon.com'
```

### 該当コード (`src/triage/jp_coverage_verifier.py:271-285`)

```python
for chunk in chunks:
    web = getattr(chunk, "web", None)
    if web is not None:
        uri = getattr(web, "uri", None)   # ← redirect URL を取得
        if uri:
            urls.append(uri)
```

### 影響

- F-13.B の WL マッチング (`if domain in url_lower`) は redirect URL に対して
  常に不一致 → **構造的に常に `has_jp_coverage=False` を返す**。
- 19/19 件 `matched=0` の唯一かつ十分な説明。
- **この不具合は本番運用にも影響している可能性が極めて高い**。F-13.B は
  実質的に全 Slot を blind_spot 判定しており、本来 divergence 扱いすべき
  「日本で報道済みの海外ニュース」を blind_spot として動画化していた懸念。

### 修正方針 (F-jp-coverage-improve バッチで対応)

最小修正案: `_search_with_grounding()` 内で `web.title` を読み取り、
ドメイン正規化 (lowercase + URL 化) して urls に積む。具体例:

```python
title = getattr(web, "title", None)  # e.g. "jiji.com"
if title:
    urls.append(f"https://{title.lower().strip()}")
```

代替案: `chunk.web.domain` フィールドが Gemini SDK の将来バージョンで実値を
返すようになるまで待ち、SDK バージョンアップで吸収する。短期的には title
ベースの修正を採用し、SDK の API 変更を将来追跡する方針が現実的。

### 検証案 (修正後の再測定)

`web.title` 修正版を当てて本ゴールデンセット 19 件を再測定すれば、
covered 10 件の大半 (NHK / Nikkei / Jiji / Bloomberg JP の WL ドメイン Tier 1-2 多数)
は **TP** に転じる見込み。blind_spot 5 件 (FN なし) も維持される見込み。
F-jp-coverage-improve 完了時に本スクリプトを再実行して合格判定を取り直す。

## 2. 集計指標

| 指標 | 値 |
| --- | --- |
| Total | 19 |
| TP (covered, 一致) | 0 |
| TN (blind, 一致) | 5 |
| FP (未報道→True 誤判定) | 0 |
| FN (報道済→False 誤判定) | 14 |
| Error (測定不能) | 0 |
| Precision (covered) | 0.00% |
| Recall (covered) | 0.00% |
| F1 (covered) | 0.000 |
| Precision (blind) | 26.32% |
| Recall (blind) | 100.00% |
| Tier 一致率 | 0.00% (0/0) |
| stream_2_candidate F-13.B True | 0/4 |

### 混同行列

|  | Actual True | Actual False | Error |
| --- | --- | --- | --- |
| Expected True (14 件) | 0 | 14 | 0 |
| Expected False (5 件) | 0 | 5 | 0 |

## 3. 誤判定詳細

### 3.1 False Negative (致命的、報道済み → 未報道判定)

| id | title | expected_tier | matched_urls | search_query |
| --- | --- | --- | --- | --- |
| blind_002 | Israel's top Jewish religious body 'refuses to con | tier_1_newspaper | 0 urls | Israel's top Jewish religious body 'refuses to condemn' smas |
| blind_004 | In Gaza, life flickers as power cuts shatter livel | tier_1_newspaper | 0 urls | In Gaza, life flickers as power cuts shatter livelihoods and |
| blind_005 | Gaza was the scandal that should have ended Keir S | tier_1_newspaper | 0 urls | Gaza was the scandal that should have ended Keir Starmer's p |
| blind_009 | The real reason Iran and the US cannot end the war | tier_2_wire_service | 0 urls | The real reason Iran and the US cannot end the war: Money 日本 |
| covered_001 | ホルムズ海峡めぐりアメリカの対イラン封鎖始まる イランは反発 | tier_1_newspaper | 0 urls | ホルムズ海峡めぐりアメリカの対イラン封鎖始まる イランは反発 日本 報道 |
| covered_002 | 米ロ首脳電話会談 ロシア『5月にウクライナと停戦の用意ある』 | tier_1_newspaper | 0 urls | 米ロ首脳電話会談 ロシア『5月にウクライナと停戦の用意ある』 日本 報道 |
| covered_003 | 米中 関税協議 / 通商交渉 (2026 年 4 月) | tier_1_newspaper | 0 urls | 米中 関税協議 / 通商交渉 (2026 年 4 月) 日本 報道 |
| covered_004 | ローマ教皇『多数派の専制』を警告 民主主義に危機感 | tier_1_newspaper | 0 urls | ローマ教皇『多数派の専制』を警告 民主主義に危機感 日本 報道 |
| covered_005 | ブラジル ルラ政権、アマゾン開催の COP30 で狙うグローバルサウス主導役 | tier_1_newspaper | 0 urls | ブラジル ルラ政権、アマゾン開催の COP30 で狙うグローバルサウス主導役 日本 報道 |
| covered_006 | NVIDIA 株が半年ぶり最高値更新 衰えぬ AI 需要、循環投資にはリスク | tier_1_newspaper | 0 urls | NVIDIA 株が半年ぶり最高値更新 衰えぬ AI 需要、循環投資にはリスク 日本 報道 |
| covered_007 | ナイジェリアで 100 人拉致 過激派襲撃、死者多数か | tier_1_newspaper | 0 urls | ナイジェリアで 100 人拉致 過激派襲撃、死者多数か 日本 報道 |
| covered_008 | マリ 軍事政権に反政府勢力が一斉攻撃 暫定国防相死亡 | tier_1_newspaper | 0 urls | マリ 軍事政権に反政府勢力が一斉攻撃 暫定国防相死亡 日本 報道 |
| covered_009 | インド・パキスタン カシミール 緊張 (4 月 22 日テロ攻撃 + 5 月 7-10 日 Oper | tier_1_newspaper | 0 urls | インド・パキスタン カシミール 緊張 (4 月 22 日テロ攻撃 + 5 月 7-10 日 Operation Sind |
| covered_010 | イエメン・フーシ派、イスラエルに弾道ミサイル発射し『イラン支援』を公式表明 | tier_2_wire_service | 0 urls | イエメン・フーシ派、イスラエルに弾道ミサイル発射し『イラン支援』を公式表明 日本 報道 |

### 3.2 False Positive (機会損失、未報道 → 報道済み判定)

- なし ✅

### 3.3 Error (測定不能)

- なし ✅

## 4. Tier 判定の精度

- Tier 判定対象 0 件 (TP かつ expected_tier 指定あり)

## 5. stream_2_candidate 4 件の F-13.B 出力

stream_2_candidate メタ付きエントリ (blind_002/004/005/009) は 「広範な事件は Tier 1-2 で報道済み (True 期待)、特定角度は系統 2 候補」というパターン。F-stream-2-filter-design 実装時に系統 2 ターゲット候補として再評価される。

| id | actual | actual_matched_tier | matched_domains | 系統 2 角度 (要約) |
| --- | --- | --- | --- | --- |
| blind_002 | False | None |  | イスラエル最高宗教権威『ラビ庁』が軍からの非難要請を拒否した、軍と宗教界の宗教的シオニズム融合という構造分析角度 |
| blind_004 | False | None |  | 潤滑油 1L 14 → 1,500 シェケル (100 倍) 暴騰、中小企業 9 割廃業危機、ケーキ店主の生活破綻、ジェネレーター燃料に食用油転用といった『社会 |
| blind_005 | False | None |  | 英国によるガザ向け F-35 部品継続供給、キプロス・アクロティリ基地からの監視飛行情報共有といった『英国の構造的なイスラエル軍事支援』こそが本来の道徳的スキャ |
| blind_009 | False | None |  | イラン革命防衛隊が制裁網下の闇経済から得る既得権益と、それが戦争継続の構造的動機になっているという『継戦の経済的合理性』分析角度 |

## 6. 全件詳細

| id | expected | actual | expected_tier | actual_tier | matched_n | elapsed | cached |
| --- | --- | --- | --- | --- | --- | --- | --- |
| blind_001 | False | False | None | None | 0 | 15.24s | no |
| blind_002 | True | False | tier_1_newspaper | None | 0 | 7.78s | no |
| blind_003 | False | False | None | None | 0 | 4.81s | no |
| blind_004 | True | False | tier_1_newspaper | None | 0 | 12.88s | no |
| blind_005 | True | False | tier_1_newspaper | None | 0 | 6.57s | no |
| blind_007 | False | False | None | None | 0 | 10.86s | no |
| blind_008 | False | False | None | None | 0 | 8.19s | no |
| blind_009 | True | False | tier_2_wire_service | None | 0 | 10.15s | no |
| blind_010 | False | False | None | None | 0 | 10.73s | no |
| covered_001 | True | False | tier_1_newspaper | None | 0 | 8.50s | no |
| covered_002 | True | False | tier_1_newspaper | None | 0 | 11.47s | no |
| covered_003 | True | False | tier_1_newspaper | None | 0 | 10.22s | no |
| covered_004 | True | False | tier_1_newspaper | None | 0 | 4.93s | no |
| covered_005 | True | False | tier_1_newspaper | None | 0 | 5.11s | no |
| covered_006 | True | False | tier_1_newspaper | None | 0 | 6.68s | no |
| covered_007 | True | False | tier_1_newspaper | None | 0 | 7.16s | no |
| covered_008 | True | False | tier_1_newspaper | None | 0 | 9.48s | no |
| covered_009 | True | False | tier_1_newspaper | None | 0 | 19.64s | no |
| covered_010 | True | False | tier_2_wire_service | None | 0 | 6.61s | no |

## 7. 改善提案

### 未達指標と該当エントリの傾向

- **recall_covered**: 実測 0.000 < 閾値 0.90 (未達)
- **precision_blind**: 実測 0.263 < 閾値 0.80 (未達)
- **f1_covered**: 実測 0.000 < 閾値 0.85 (未達)
- **tier_accuracy**: 実測 0.000 < 閾値 0.70 (未達)

### FN (14 件) — 報道済みなのに未報道判定

Recall 未達の主因。検索クエリ改善 / WL ドメイン拡張 / Tier 別重み付け等で対処要検討。

- `blind_002` (Israel's top Jewish religious body 'refuses to condemn' smas)
  - search_query: `Israel's top Jewish religious body 'refuses to condemn' smashing of Jesus statue 日本 報道`
  - F-13.B が拾った WL ドメイン: (なし)
  - 真値で確認済み URL (manual): 3 件
- `blind_004` (In Gaza, life flickers as power cuts shatter livelihoods and)
  - search_query: `In Gaza, life flickers as power cuts shatter livelihoods and healthcare 日本 報道`
  - F-13.B が拾った WL ドメイン: (なし)
  - 真値で確認済み URL (manual): 2 件
- `blind_005` (Gaza was the scandal that should have ended Keir Starmer's p)
  - search_query: `Gaza was the scandal that should have ended Keir Starmer's political career 日本 報道`
  - F-13.B が拾った WL ドメイン: (なし)
  - 真値で確認済み URL (manual): 3 件
- `blind_009` (The real reason Iran and the US cannot end the war: Money)
  - search_query: `The real reason Iran and the US cannot end the war: Money 日本 報道`
  - F-13.B が拾った WL ドメイン: (なし)
  - 真値で確認済み URL (manual): 3 件
- `covered_001` (ホルムズ海峡めぐりアメリカの対イラン封鎖始まる イランは反発)
  - search_query: `ホルムズ海峡めぐりアメリカの対イラン封鎖始まる イランは反発 日本 報道`
  - F-13.B が拾った WL ドメイン: (なし)
  - 真値で確認済み URL (manual): 4 件
- `covered_002` (米ロ首脳電話会談 ロシア『5月にウクライナと停戦の用意ある』)
  - search_query: `米ロ首脳電話会談 ロシア『5月にウクライナと停戦の用意ある』 日本 報道`
  - F-13.B が拾った WL ドメイン: (なし)
  - 真値で確認済み URL (manual): 4 件
- `covered_003` (米中 関税協議 / 通商交渉 (2026 年 4 月))
  - search_query: `米中 関税協議 / 通商交渉 (2026 年 4 月) 日本 報道`
  - F-13.B が拾った WL ドメイン: (なし)
  - 真値で確認済み URL (manual): 4 件
- `covered_004` (ローマ教皇『多数派の専制』を警告 民主主義に危機感)
  - search_query: `ローマ教皇『多数派の専制』を警告 民主主義に危機感 日本 報道`
  - F-13.B が拾った WL ドメイン: (なし)
  - 真値で確認済み URL (manual): 2 件
- `covered_005` (ブラジル ルラ政権、アマゾン開催の COP30 で狙うグローバルサウス主導役)
  - search_query: `ブラジル ルラ政権、アマゾン開催の COP30 で狙うグローバルサウス主導役 日本 報道`
  - F-13.B が拾った WL ドメイン: (なし)
  - 真値で確認済み URL (manual): 4 件
- `covered_006` (NVIDIA 株が半年ぶり最高値更新 衰えぬ AI 需要、循環投資にはリスク)
  - search_query: `NVIDIA 株が半年ぶり最高値更新 衰えぬ AI 需要、循環投資にはリスク 日本 報道`
  - F-13.B が拾った WL ドメイン: (なし)
  - 真値で確認済み URL (manual): 4 件
- `covered_007` (ナイジェリアで 100 人拉致 過激派襲撃、死者多数か)
  - search_query: `ナイジェリアで 100 人拉致 過激派襲撃、死者多数か 日本 報道`
  - F-13.B が拾った WL ドメイン: (なし)
  - 真値で確認済み URL (manual): 3 件
- `covered_008` (マリ 軍事政権に反政府勢力が一斉攻撃 暫定国防相死亡)
  - search_query: `マリ 軍事政権に反政府勢力が一斉攻撃 暫定国防相死亡 日本 報道`
  - F-13.B が拾った WL ドメイン: (なし)
  - 真値で確認済み URL (manual): 3 件
- `covered_009` (インド・パキスタン カシミール 緊張 (4 月 22 日テロ攻撃 + 5 月 7-10 日 Operation Sind)
  - search_query: `インド・パキスタン カシミール 緊張 (4 月 22 日テロ攻撃 + 5 月 7-10 日 Operation Sindoor) 日本 報道`
  - F-13.B が拾った WL ドメイン: (なし)
  - 真値で確認済み URL (manual): 2 件
- `covered_010` (イエメン・フーシ派、イスラエルに弾道ミサイル発射し『イラン支援』を公式表明)
  - search_query: `イエメン・フーシ派、イスラエルに弾道ミサイル発射し『イラン支援』を公式表明 日本 報道`
  - F-13.B が拾った WL ドメイン: (なし)
  - 真値で確認済み URL (manual): 4 件

### 推奨アクション

- F-jp-coverage-improve バッチを起動 (緊急度 高に登録)。F-stream-2-filter-design 着手は **保留**。

---

*このレポートは scripts/verify_jp_coverage_measure.py が自動生成。ゴールデンセット v1.1 (19 entries) を真値として F-13.B の精度を実測。*