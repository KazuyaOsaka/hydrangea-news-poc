# F-trial-run-post-fix 実行レポート

実行日時: 2026-05-07 04:06-04:32 JST
F-13.B コミット: `fd76660` (= main HEAD、F-jp-coverage-improve マージ後)
試運転コマンド: `python -m src.ingestion.run_ingestion && python -m src.main --mode normalized`

---

## 1. サマリ

修正後 F-13.B (F-jp-coverage-improve / 2026-05-07) の本番試運転実行と、過去試運転 7-K
動画化 3 件の WebSearch 後追い + 修正後 F-13.B 再判定の統合レポート。

| 項目 | 結果 |
|---|---|
| 試運転実行 | ✅ 成功 (job_id=033ed4bc...、batch_id=20260506_190600、26 分) |
| F-13.B 動作 | ✅ 構造的に正常 (excluded_urls_count > 0 が証拠) |
| F-13.B 結果分布 | ⚠️ 全 3 Slot has_jp_coverage=False (うち 1 件は WebSearch 後追いで Recall miss と判明) |
| 防衛機構 5 層 | ✅ 全層機能 (F-1 18/364, F-2 通過, F-13.B 3/3 invocations, F-5 救済 0, F-13 隠れ層 0) |
| 過去 7-K 再判定 | ✅ 3/3 完了、判定不変 (False→False)、ただし excluded_count 非ゼロで構造機能を確認 |
| WebSearch 後追い | ✅ 3/3 完了、6 件中 4 件で Tier 1-2 報道済みと判明 (stream_2_candidate パターン) |
| **Phase A.5-3a-verify ゲート完了** | ✅ **達成** (1-A〜1-D''' 全完了) |

---

## 2. 試運転実行結果

### 2.1 パイプライン全体

- batch_id: 20260506_190600
- RSS 取得: 41 ソース中 40 成功 (Reuters 0 entries, Eurasianet 404)
- 記事収集: 1454 raw → 584 重複除去後 → 364 events
- triage: GarbageFilter 通過 575、EditorialMissionFilter 通過 18 (45.0 閾値)
- Elite Judge Gate 3: 10 評価 → 採用 9
- Slot 選定: 上位 3 件
- Budget: run_llm=38/150 (publish_reserve_preserved=True)

### 2.2 Slot 別詳細

| # | Event ID | Title | Elite Judge | F-13.B | Routing | Output |
|---|---|---|---|---|---|---|
| 1 | cls-6be4fc09d9ed | 'Insider trading': Oil and stocks jolt on news of US-Iran deal | 38点 (アンチ忖度 9) | False / matched=0 / excluded=1 (youtube) | blind_spot_global | article + script + video_payload + evidence |
| 2 | cls-0c7fa7c667d6 | Russian man sets himself on fire at war memorial... authorities suppress news | 35点 (アウトサイド・イン 9) | False / matched=0 / excluded=10 (youtube×10) | blind_spot_global | article only |
| 3 | cls-a4132ec7d949 | Legal complaint filed by Palestine activists against Met Police chief over synagogue remarks | 33点 (多極的視点 9) | False / matched=0 / excluded=3 (youtube×3) | blind_spot_global | article only |

### 2.3 重要な所見

- **構造的不具合は解消**: 全 3 Slot で `excluded_urls_count > 0` (1/10/3)。
  これは F-jp-coverage-improve のドメイン抽出層 (`_extract_domain_from_chunk`)
  が正しく動作している証拠。修正前は redirect URL のみ収集 → matched=0 +
  excluded=0 という形で構造的に常に False を返していた。

- **Recall 課題**: 全 3 Slot has_jp_coverage=False は WebSearch 後追いで以下の通り:
  - Slot-1 (Insider trading): nikkei.com (Tier 1)、jiji.com (Tier 2)、bloomberg.co.jp
    (Tier 2) で広範に報道済み = **Recall miss**
  - Slot-2 (ロシア焼身): WL 範囲で未報道、真の blind_spot 判定は妥当
  - Slot-3 (Met Police シナゴーグ告訴): WL 範囲で未報道、真の blind_spot 判定は妥当

- **Recall miss の原因**: Grounding API が youtube.com 偏重の結果を返す (英語タイトル
  + 「日本 報道」クエリ品質問題)。本試運転 6 invocations の excluded URLs は全て
  youtube.com (計 23 件)。これは F-jp-coverage-tune の対象 (検索クエリ最適化)。

---

## 3. F-13.B 出力分布

### 3.1 全 invocation 集計 (試運転 3 + replay 3 = 6 件)

| 項目 | 件数 |
|---|---|
| has_jp_coverage = True | 0 |
| has_jp_coverage = False | 6 |
| Error | 0 |
| matched_tier 別: Tier 1-4 のいずれか | 0 |
| matched_tier 別: null (False 判定) | 6 |
| excluded URLs 合計 | 23 件 (全 youtube.com) |
| Top matched domains | (なし) |

### 3.2 解釈

- **構造的不具合は完全解消** (excluded_count > 0 が証拠、修正前は構造的に常に 0)
- **Tier 一致率は 0/0 で算出不能**: WL マッチング 0 件のため
- **Tier 偏重パターンの観察も不能**: マッチング自体が発生せず
- **Grounding 結果品質**: 英語タイトル + 「日本 報道」クエリで youtube.com 偏重、
  日本主要メディアの URL が Grounding に取られていない構造が観測された
- **次バッチルーティング**: F-stream-2-filter-design 着手 OK
  (構造的不具合解消で系統 2 設計の前提条件は確保)。F-jp-coverage-tune は
  Grounding クエリ品質改善 (英語→日本語キーワード抽出 + WL ドメイン名ヒント混入)
  に注力すれば Recall 大幅改善見込み

---

## 4. 防衛機構 5 層の発火状況

| 層 | 発火状況 | 結果 |
|---|---|---|
| F-1 EditorialMissionFilter | 364 評価、20 LLM scored (failed 0)、threshold 45.0、18 通過 | ✅ 正常稼働 |
| F-2 FlagshipGate | 18 評価、Blocked 0 件、全通過 | ✅ 正常稼働 |
| F-13.B JpCoverageVerifier | 3 invocations、True 0 / False 3 / Error 0 | ✅ 構造機能 OK / Recall 課題は別系 |
| F-5 Downstream Rescue | 救済発火 0 件 (Elite Judge Gate 3 で 9 件採用済みのため不要) | ✅ 正常稼働 |
| F-13 隠れ層 (quality_floor bypass) | bypass 発火 0 件 (3 Slot 全て floor 通過) | ✅ 正常稼働 |

全 5 層が **構造的に機能** していることを確認。F-13.B Recall miss は構造的不具合
ではなく Grounding API の検索結果品質問題 (F-jp-coverage-tune の対象)。

---

## 5. 試運転 7-K 過去動画化 3 件の WebSearch 後追い

(詳細: `docs/runs/F-trial-run-post-fix/past_videos_audit.json`)

| Slot | Event ID | 旧 F-13.B 判定 | WebSearch 後追い結論 | stream_2 候補 |
|---|---|---|---|---|
| 1 | cls-7bd1406438b6 (FIFA Palestine 提訴) | False (動画化) | ★ Tier 2 (jiji.com) で関連報道済み (2026-03-25)、Tier 1 (nikkei.com) で近接トピック | ✅ |
| 2 | cls-33b4f4960bf9 (Mandelson Gaza scandal) | False (動画化) | ★ Tier 1 (nikkei) + Tier 2 (jiji + bloomberg) で広範に報道済み (Epstein 角度)、ただし MEE オリジナル『Gaza 道徳的責任』角度は未報道 | ✅ |
| 3 | cls-204a683f73ee (Gaza 電力遮断) | False (動画化) | 2023-2024 古い基本事実は Tier 1 (nikkei) で過去報道、ただし MEE 2026-04 時点の特定角度 (潤滑油 100 倍 / 中小企業 9 割廃業) は未報道 | ❌ (真の blind_spot に近い) |

**含意**:
- 試運転 7-K で動画化された 3 件のうち、2 件 (Slot-1/Slot-2) は実は Tier 1-2 で
  広範報道済みだった = F-13.B 構造的不具合による誤判定の証拠
- いずれも『広範事件は報道済み + MEE オリジナル角度は未報道』という典型的
  stream_2_candidate パターン
- 修正後 F-13.B + F-stream-2-filter-design (系統 2 二段階フィルタ) の組み合わせで、
  本来 Slot-1/Slot-2 は divergence + stream_2 として処理されるのが望ましい
- Slot-3 は 2026-04 時点の特定角度が真に未報道、blind_spot_global 判定は妥当

**audit caveat**: Anthropic WebSearch クローラは asahi.com / yomiuri.co.jp /
nhk.or.jp / mainichi.jp / sankei.com / 47news.jp / kyodonews.jp / kyodonews.net
への直接クロールがブロックされる仕様。これら主要紙は jiji.com / nikkei.com /
bloomberg.co.jp 等の他 Tier ヒットから推定した。

---

## 6. 過去試運転データの修正後 F-13.B 再判定

(詳細: `docs/runs/F-trial-run-post-fix/past_runs_replay.json`)

| Event ID | 旧判定 (b950813) | 新判定 (fd76660) | diff | excluded_urls_count |
|---|---|---|---|---|
| cls-7bd1406438b6 (FIFA) | False | False | 判定不変 | 0 |
| cls-33b4f4960bf9 (Mandelson) | False | False | 判定不変 | 5 |
| cls-204a683f73ee (Gaza 電力) | False | False | 判定不変 | 4 |

**所見**:
- 3 件全て「判定不変」(False→False)
- WebSearch 後追いとの整合性: 不整合 (Slot-1 FIFA / Slot-2 Mandelson は WebSearch
  では Tier 1-2 報道済み、修正後 F-13.B でも検出できず)
- excluded_urls_count: 0/5/4 = 構造機能は OK (Slot-1 は Grounding が 0 件返した
  ため 0、これは検索クエリ品質問題)
- これらは F-jp-coverage-tune の対象 (Grounding クエリ最適化) であり、
  F-jp-coverage-improve の責務範囲外という分離は妥当 (DECISION_LOG の議論 5 と整合)

---

## 7. 総合所見

### 7.1 修正後 F-13.B は本番運用で機能しているか?

**Yes (構造的観点で)**:
- ドメイン抽出層 (`_extract_domain_from_chunk`) は機能
  (excluded_urls_count > 0 が証拠、修正前は構造的に常に 0)
- WL マッチング 0 件 + excluded 件数 23 (全 youtube.com) の組み合わせは
  「Grounding API が日本主要メディアを返さない検索クエリ品質問題」を示しており、
  F-13.B コード自体の不具合ではない

**No (Recall 観点で)**:
- 試運転 3 Slot のうち 1 Slot (Insider trading) は Tier 1-2 報道済みを Recall miss
- 過去 7-K 再判定 3 件のうち 2 件 (FIFA / Mandelson) は WebSearch では Tier 1-2 報道
  済み、修正後 F-13.B でも検出できず
- 上記は F-jp-coverage-improve 計測再実行時 (verdict=fail、Recall covered 71.43%)
  の傾向と整合する既知課題

### 7.2 Phase A.5-3a-verify ゲート完了の判定根拠

**達成 (1-A〜1-D''' 全完了)**:
- 1-A 〜 1-D'' (F-jp-coverage-improve / 2026-05-07): ✅ 完了
- 1-D''' (F-trial-run-post-fix / 本バッチ): ✅ 完了
  - 試運転実行 (Task B): ✅
  - 構造的不具合解消の本番動作確認 (excluded_count 非ゼロ): ✅
  - 防衛機構 5 層全機能確認 (Task D): ✅
  - 過去 7-K 動画化 3 件の WebSearch 後追い (Task E): ✅
  - 修正後 F-13.B での過去試運転再判定 (Task F): ✅
- F-jp-coverage-tune は別系で精度閾値達成の課題、ゲート完了の必須条件ではない

→ **Phase A.5-3a-verify ゲート完了を正式宣言**。次フェーズ
F-stream-2-filter-design 着手 OK。

---

## 8. 次バッチへの引き継ぎ

### 8.1 即着手可能

- **F-stream-2-filter-design** ★最優先 (Phase A.5-3a-verify ゲート完了で着手再開
  条件達成)
  - 本 audit の試運転 7-K 過去動画化 3 件 (Slot-1 FIFA / Slot-2 Mandelson) が
    典型的 stream_2_candidate パターンと判明、設計の妥当性根拠が増えた
  - golden_set v1.1 の blind_002/004/005/009 と試運転 7-K Slot-1/Slot-2 を
    系統 2 ターゲットの実例として活用可能

### 8.2 並走候補 (任意)

- **F-jp-coverage-tune** ★高 (本試運転で Recall miss が再確認された)
  - 試運転 Slot-1 (Insider trading) と replay Slot-1/Slot-2 (FIFA / Mandelson) で
    Grounding が youtube.com 偏重の結果を返す傾向を確認
  - 対策候補: `_build_search_query` 改善 (英語タイトル → 日本語キーワード抽出 →
    「NHK 朝日 日経 ロイター」等の WL ドメイン名ヒント混入)
  - F-stream-2-filter-design と並行可

### 8.3 想定外結果への対応

- **想定外結果**: なし (試運転は仕様通り進行、F-13.B Recall miss は既知課題と整合)
- **検出された懸念**: Anthropic WebSearch クローラが asahi.com 等への直接クロール
  がブロック (= WebSearch ベースの後追い検証は jiji/nikkei/bloomberg 等のヒットで
  代理推定する必要)、これは将来の WebSearch ベース検証スクリプトの設計に影響

### 8.4 Project Knowledge 最新化

★ 本バッチ完了は **Phase A.5-3a-verify ゲート完了の節目** (1-D''' 完了)。
BATCH_PROTOCOL の Project Knowledge 運用ルールに従い、新チャット移行前に
カズヤが手動で claude.ai の Project Knowledge を **必須最新化** することを推奨:
- `docs/CURRENT_STATE.md` (本バッチで全置換更新)
- `docs/DECISION_LOG.md` (本バッチエントリ追加)
- `docs/FUTURE_WORK.md` (F-trial-run-post-fix 完了済み移動 + F-stream-2-filter-design
  着手 OK 状態に更新)
- `docs/DISCUSSION_NOTES.md` (本バッチで F-13.B 動作仕様検討課題を確定状態に更新)
- `docs/runs/F-trial-run-post-fix/` 配下 (本バッチ output、新規)

### 8.5 カズヤ確認推奨事項

- 試運転実行結果の妥当性 (F-13.B が期待通り動いたか、Recall miss 1/3 の許容性)
- WebSearch 後追い 3 件の判定 (Slot-1/2 stream_2 / Slot-3 真 blind_spot の解釈)
- F-stream-2-filter-design 着手 OK 判断
- F-jp-coverage-tune 優先度判断 (本試運転で Recall miss 再確認)

---

*このレポートは F-trial-run-post-fix (Phase A.5-3a-verify 1-D''') が自動生成。
試運転実行 (`python -m src.main --mode normalized`) + 過去試運転データ
(`scripts/replay_jp_coverage.py`) + WebSearch 後追い (Anthropic WebSearch ツール)
の 3 軸統合。Phase A.5-3a-verify ゲート完了の最終段階バッチ。*
