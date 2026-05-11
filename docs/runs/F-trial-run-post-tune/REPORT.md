# F-trial-run-post-tune 統合レポート

実行日時: 2026-05-11 13:40-14:10 JST
main HEAD コミット: `4062639` (F-jp-coverage-tune-followup マージ後)
試運転コマンド: `python -m src.ingestion.run_ingestion && python -m src.main --mode normalized`

---

## 1. バッチ概要

F-jp-coverage-tune-followup (2026-05-09 merge) で `_match_whitelist` 階層判定化
+ `JP_MEDIA_WHITELIST` 30 ドメイン化 (afpbb / forbesjapan / nippon 追加) の
大改修が入った。独立 23 件ゴールデンセット評価では F1 covered 0.8718 で threshold
初突破まで到達したが、**改修後の本番運用 (RSS 41 ソース → triage → Slot 選定 →
script 生成) での実挙動は未検証**だった。

本バッチで試運転 + 防衛機構 5 層監査 + 拾われた Slot の台本品質確認 + 第一作
題材ランク付けの 4 角度から本番実挙動を測定。副次的に拾われた 3 Slot を
Phase A.5-3b 第一作の題材候補として 5 軸採点 (機械 4 軸 + カズヤ主観 1 軸) でランク化。

「動くものを壊さない」哲学に従い、`src/` `tests/` `configs/` `scripts/` 全て不変、
`docs/` 配下のみ更新。baseline 1390 passed 維持。

| 項目 | 結果 |
|---|---|
| 試運転実行 | ✅ 成功 (job_id=cbe56961...、batch_id=20260511_044914、20.4 分) |
| F-13.B 動作 | ✅ 構造機能 + WL 拡張 (afpbb / nippon) 機能 OK |
| F-13.B 結果分布 | ★ 反転: 3 Slot 全 has_jp_coverage=**True** (F-trial-run-post-fix は 0/3 だった) |
| 防衛機構 5 層 | ✅ 全層機能 (F-1 20/304, F-2 通過, F-13.B 3/3 True, F-5 救済 1 件, F-13 隠れ層 1 件) |
| 台本生成 | 1 件 (Slot-1) のみ、Slot-2/3 は F-16-A article-only モード |
| 第一作題材機械スコア | Slot-1 (10pt) > Slot-2 (6pt) > Slot-3 (5pt) |
| baseline テスト | ✅ 1390 passed (`src/ tests/ configs/` 0 変更) |

---

## 2. 試運転実行結果

### 2.1 パイプライン全体

- batch_id: `20260511_044914`
- RSS 取得: 41 ソース中 40 成功 (Reuters EN 0 entries、他全 OK)
- 記事収集: 47 raw → 1229 new → 469 重複/garbage 除去後 → 304 events
- triage: GarbageFilter 通過 469 (27 LLM batch)、EditorialMissionFilter 通過 20 (threshold 45.0)
- Gemini Judge: 3 候補評価 → blind_spot_global=1 (cls-03892eab) + insufficient_evidence=2
- F-5 Rescue: 1 件発火 (cls-da0a74aa712d、editorial_mission=86.0 で Hydrangea concept alignment → flagship 認定、ただし Top-3 Slot 選定外)
- Slot 選定: 上位 3 件
- Budget: run_llm=39/150 (publish_reserve_preserved=True、stopped_due_to_reserve=False)

### 2.2 Slot 別詳細 (= Hydrangea ブランドメッセージとの関係も含む)

| # | Event ID | Title | mission_score | F-13.B | judge | F-13 隠れ層 | Outputs |
|---|---|---|---|---|---|---|---|
| 1 | cls-6889e9e1c7ac | 9,600 Detainees: Israel Prison Abuses | **86.0** | True / afpbb (Tier 2) / matched=1 / excluded=1 | not_judged | ✅ fired | article+script+video_payload+evidence |
| 2 | cls-1a38c0ca8c99 | Filmmakers slam BBC after Gaza documentary | 77.0 | True / afpbb (Tier 2) / matched=1 / excluded=0 | not_judged | — | article only |
| 3 | cls-03892eab2072 | Tehran says US proposal sought Iran's surrender | 83.0 | True / **nippon (Tier 4)** / matched=1 / excluded=0 | blind_spot_global (score 9.0) | — | article only |

### 2.3 重要な所見

#### ★ 重要 1: WL 拡張 3 ドメインのうち 2 つが本番試運転 3 Slot 全件にヒット

- afpbb.com (Tier 2) × 2 Slot, nippon.com (Tier 4) × 1 Slot = **3/3 で WL 拡張ドメインがヒット**
- F-trial-run-post-fix (2026-05-07) では 3/3 で has_jp_coverage=False (全 youtube 偏重)
  だった → **本バッチで完全反転** (★ F-jp-coverage-tune-followup の影響は本番運用において想定以上)

#### ★ 重要 2: matched_urls がベアドメインのみという挙動 (誤陽性のリスク)

- 3/3 で `matched_urls` が `https://afpbb.com` / `https://nippon.com` という **ベアドメインのみ**
- 記事レベルの URL (article path) は取得されておらず、Grounding API の chunk.web.title 抽出パスに
  よる識別と推測 (F-jp-coverage-improve のドメイン抽出層の戦略 2 と同じ経路)
- 「afpbb.com が当該事象を実際に報道している」ことを必ずしも意味しない (= 誤陽性のリスク)
- WebSearch 後追い検証は本バッチ範囲外として記録、次バッチ案件

#### ★ 重要 3: Hydrangea ブランドメッセージ (blind_spot_global) が機械判別で消滅

- 3/3 で has_jp_coverage=True → 全 Slot が divergence ルートに進行
- Slot-3 (Tehran/Iran surrender) は judge が blind_spot_global 認定 (score 9.0) だが、F-13.B は
  nippon Tier 4 補助層でヒット = **judge と F-13.B が結論不一致**
- Slot-1 (Israel Prison Abuses) は editorial_mission_score=86 (最高) + Hydrangea ど真ん中
  (人権・忖度・systemic suppression) だが has_jp_coverage=True で divergence ルート進行

#### ★ 重要 4: production-pipeline に verify_two_stage / particular_angle_metadata / sontaku_signals 全て未配線

- src/main.py:3187 で legacy verify() (broad-only) のみ呼び出し
- verify_two_stage() は scripts/measure_two_stage_accuracy.py 等の計測専用
- 系統 1/2/3 機械判別 + sontaku_signals は本番未配線 = production-pipeline 上で stream 分類は
  常に unknown 扱い
- generate_script_with_analysis (新ルート) も Slot-1 で `analysis_result=null` のため未起動、旧ルート + F-13 隠れ層 quality_floor_miss bypass で台本生成

---

## 3. F-13.B 改修後の本番挙動分析 (Task C)

詳細: `docs/runs/F-trial-run-post-tune/f13b_output_analysis.json`

### 3.1 全 invocation 集計 (試運転 3 件)

| 項目 | 値 |
|---|---|
| has_jp_coverage = True | **3** |
| has_jp_coverage = False | 0 |
| Error | 0 |
| matched_tier 別: Tier 2 wire_service | 2 (afpbb x2) |
| matched_tier 別: Tier 4 business | 1 (nippon x1) |
| matched_tier 別: その他 (Tier 1/3) | 0 |
| matched_tier 別: null (False) | 0 |
| excluded URLs 合計 | 1 件 (Slot-1 で youtube.com) |
| 平均 elapsed | 7.3s (Slot-1: 9s, Slot-2: 6s, Slot-3: 7s) |

### 3.2 F-trial-run-post-fix (5/7) との比較

| 指標 | F-trial-run-post-fix | F-trial-run-post-tune | Delta |
|---|---|---|---|
| has_jp_coverage=True | 0/3 | 3/3 | **+3 (完全反転)** |
| WL ヒット | 0 件 | 3 件 (afpbb x2, nippon x1) | **+3** |
| matched_tier 分布 | 全 null (False) | Tier 2 x2, Tier 4 x1 | 完全反転 |
| excluded_count 合計 | 23 件 (全 youtube) | 1 件 (Slot-1 youtube) | -22 |
| 平均 elapsed | 7.7s | 7.3s | -0.4s (微減) |
| F-5 救済発火 | 0 件 | 1 件 (Hydrangea concept alignment 経由) | +1 |
| F-13 隠れ層 bypass | 0 件 | 1 件 (Slot-1) | +1 |

### 3.3 verify_two_stage / Stream 判別の状況

- **verify_two_stage 発火回数**: 0 (本番未配線、production main.py は legacy verify() のみ呼び出し)
- **broad_query 発火回数**: 0 (verify_two_stage 内のみ、本番未稼働)
- **angle_query 発火回数**: 0 (同上)
- **per-call timeout 発火**: 0
- **graceful fallback unknown 件数**: 0 (verify() に該当機能なし)
- **stream_1/2/3 機械判別**: production-pipeline 上では実施されない (legacy verify() = has_jp_coverage の二値判定のみ)

設計意図 (= Phase A.5-3a-verify gate 完了後の概念整理) と本番実装 (verify_two_stage 未配線) には
乖離あり、これは後続バッチ案件として記録。

---

## 4. 防衛機構 5 層の発火状況 (Task D)

詳細: `docs/runs/F-trial-run-post-tune/defense_layers_audit.json`

| 層 | 発火状況 | 結果 |
|---|---|---|
| F-1 EditorialMissionFilter | 304 → 20 通過 (threshold 45.0)、selected 3 Slot scores: 86/77/83 (median 83) | ✅ 正常稼働 |
| F-2 FlagshipGate | 20 評価、Blocked 0 件、全通過 | ✅ 正常稼働 |
| F-13.B JpCoverageVerifier | 3 invocations、True 3 / False 0 / Error 0 (WL 拡張 afpbb x2 + nippon x1) | ✅ 構造機能 OK / WL 拡張機能 OK / WL ヒット品質要検証 |
| F-5 Downstream Rescue | 救済発火 1 件 (cls-da0a74aa712d、ただし Top-3 選定外) | ✅ 正常稼働 |
| F-13 隠れ層 (quality_floor bypass) | bypass 発火 1 件 (Slot-1、editorial_mission=86 + analysis_result=none) | ✅ 正常稼働 |

全 5 層が **構造的に機能** していることを確認。ただし以下 2 点の重要観察:
1. F-13.B WL ヒット品質 (`matched_urls` がベアドメインのみ問題) は誤陽性リスクとして要検証
2. F-13 隠れ層 fired = `analysis_result=none` = generate_script_with_analysis (新ルート) は本番未配線、Phase A.5-3a-verify gate 完了後の概念整理 (particular_angle_metadata / sontaku_signals) は production-pipeline 上では未反映

---

## 5. 拾われた Slot の台本品質確認 (Task E)

詳細: `docs/runs/F-trial-run-post-tune/script_quality_audit.json`

### 5.1 Slot-1 (cls-6889e9e1c7ac, "9,600 Detainees: Israel Prison Abuses") 台本品質

- **Hook**: 18字 / 4s "9,600人。今、消された人々の数。" — **数字提示型 + 詩的省略**
- **Setup**: 90字 / 16s "イスラエルの刑務所には、膨大な数のパレスチナ人がいます。ベネズエラ政府系の国際テレビ局テレスールによれば、そこでは組織的な虐待が疑われ、国際機関の監視すら操作されているといいます。"
- **Twist**: 179字 / 40s "なぜ日本のメディアは沈黙するのか。それはこれが「国際ルールの崩壊」を意味するからです。... 日本が信じる「法の支配」が通用しない。"
- **Punchline**: 87字 / 20s "綺麗事の裏で、監視の目は組織的に遮断されています。力を持つ者がルールを上書きし、弱者は闇に葬られる。あなたは、まだ世界が平等だと言えますか？この暗闇に消された、9,600人。" — **シニカル × 視聴者直接質問 + loop-3 帰着**
- **視聴維持ピーク (peaks)**: 3s (闇), 7s (9600 + TeleSUR), **15s (赤十字の監視操作 = 中盤最大衝撃)**, 30s (世界の柱無力化)
- **NG 語彙**: 検出なし (char validation 1 回 retry: hook=23→18字に補正、2 回目で全項目合格)
- **字数遵守**: ✅ 全 char_bounds 内 (hook 8-22, setup 60-90, twist 150-220, punchline 70-110)
- **総 duration**: 80s (target=80s で完全一致)、estimated=83s
- **Pattern**: Media Critique, loop-3, target_enemy=大手メディア
- **Title strength**: strong
- **analysis_result 利用**: ❌ null (新ルート未配線)
- **particular_angle_metadata / sontaku_signals**: ❌ 本番未配線

### 5.2 platform_title と F-13.B の乖離

- Slot-1 の `platform_title` = "日本では報道されない9,600 Detainees" は『日本未報道』を強調
- 一方、F-13.B では has_jp_coverage=True (afpbb) と判定
- 台本生成は (1) 旧ルート + (2) appraisal_cautions=[抑制] を F-13 隠れ層 bypass で上書きしているため、F-13.B の True 判定とは独立に『日本未報道』軸でタイトルが組まれた

### 5.3 Slot-2 / Slot-3

F-16-A article-only モード (slot_idx >= TOP_N_VIDEOS_PER_RUN=1) で script 未生成。article のみ生成。
記事品質は TL;DR + Facts/Hypothesis/Implications 構造で十分 (詳細は省略)。

---

## 6. 第一作題材ランク付け (Task F)

詳細: `docs/runs/F-trial-run-post-tune/first_video_candidate_ranking.json` + `.md`

### 6.1 機械側 4 軸採点結果

| 順位 | Event ID | Title | axis_1 ミッション | axis_2 系統 | axis_3 sontaku | axis_4 台本 | 機械合計 |
|---|---|---|---|---|---|---|---|
| ★ 1 | cls-6889e9e1c7ac | 9,600 Detainees: Israel Prison Abuses | **5** | 1 | 0 | **4** | **10** |
| 2 | cls-1a38c0ca8c99 | Filmmakers slam BBC after Gaza documentary | 5 | 1 | 0 | 0 | 6 |
| 3 | cls-03892eab2072 | Tehran says US proposal sought Iran's surrender | 4 | 1 | 0 | 0 | 5 |

注:
- axis_2 全件 1pt = 機械判別 stream は unknown (production verify_two_stage 未配線)
- axis_3 全件 0pt = sontaku_signals 本番未配線
- axis_4 は Slot-1 のみ評価可 (Slot-2/3 は article-only モードで script 未生成)
- axis_5 (カズヤ主観) は本バッチでは空欄、レビュー時に埋める

### 6.2 1 位 Slot-1 の決定要因

★ Slot-1 は唯一 script 生成された slot (Slot-2/Slot-3 は article-only) のため axis_4 で +4 点獲得、
機械スコア他の 2 Slot に大差で先行。axis_1 でも 5pt 同率最大 = Hydrangea ミッション最適合。

editorial_mission_score=86.0 (3 Slot 中最高) + 4 軸全てで Hydrangea ど真ん中 (人権・忖度・power 構造)
+ 動画 payload 生成済み = **第一作の最有力候補**。

ただし最終決定はカズヤ主観評価 (axis_5) 後。

---

## 7. 残課題 / カズヤ確認推奨事項

### 7.1 機械スコア 1 位の Slot 第一作着手判断 (カズヤレビュー必要)

- Slot-1 (cls-6889e9e1c7ac) は本バッチ機械スコア 1 位 (10pt) で、Phase A.5-3b 第一作の最有力候補
- 動画 payload + script + article + evidence 生成済み (動画レンダリング前)
- カズヤレビュー focus:
  - Hook 「9,600人。今、消された人々の数。」が刺さるか
  - Punchline 「あなたは、まだ世界が平等だと言えますか？」が視聴者着地として強いか
  - Media Critique パターン + 大手メディア批判の構図が Hydrangea ブランドとして妥当か
  - TeleSUR (ベネズエラ政府系) 単独ソースという信頼性スコープが許容範囲か
- 最終判断 = Task F (5) 主観評価 → カズヤ承認後に動画レンダリング着手

### 7.2 後続バッチへの引き継ぎ事項

#### ★ 高優先

1. **F-13.B WL ヒット品質の独立検証**: matched_urls がベアドメインのみという挙動の意味、afpbb / nippon が本当に当該事象を報道しているか (= 誤陽性かどうか)。手段: WebSearch 後追い or Grounding chunk の生データ取得。
2. **production-pipeline への verify_two_stage 配線判断**: 系統 1/2/3 機械判別は docs 上正典化済みだが本番未配線。配線するかどうか、配線する場合の F-13.B 既存 verify() との関係を整理。
3. **particular_angle_metadata / sontaku_signals 配線判断**: 同上、新ルート (generate_script_with_analysis) への配線が次フェーズで必要。F-13 隠れ層 quality_floor_miss bypass が動いている現状は新ルート未配線の証拠。

#### 中優先

4. **F-stream-2-filter-design 責務範囲再評価**: 本バッチで判明した 「has_jp_coverage=True 3/3 = blind_spot_global ルート消滅」現象は、F-stream-2-filter-design の二段階フィルタが Hydrangea ブランドメッセージ維持に直結することを示唆。
5. **F-jp-coverage-tune-followup-2 ((p) 多クエリ並列発行) の優先度判断**: 本バッチで Recall 観点は十分 (3/3 でヒット) と確認、ただし WL ヒット品質は別問題。多クエリ並列発行は Precision blind がさらに退行するリスクがあるため後回し or skip も検討。
6. **Phase A.5-3b 第二作のサンプル拡充 (= Precision blind 母数問題 + WL ヒット品質検証も兼ねる)**: 系統 3 事象 (処理水放出 / 辺野古 等) + sontaku_signals.type=domestic/media_industry の実例追加が、副次的に Precision blind 母数問題 (本バッチ残課題 (b)) を緩和する。

### 7.3 想定外結果の有無

- ★ 想定外結果あり: **F-13.B has_jp_coverage が 3 Slot 全 True で完全反転**。設計意図 (= Slot-1 のような Hydrangea ど真ん中 = 系統 2 候補 → divergence ルート) ではあるが、F-trial-run-post-fix と比較して反転の度合いが想定以上。
- バッチプロンプト指示通り「記録のみ、勝手にスコープを広げず Task G の REPORT に明記」で対応。
- baseline 1390 passed は維持 (src/ tests/ configs/ 0 変更)。

---

## 8. BATCH_PROTOCOL Task 1-5 ドッグフーディング適用内容

### Task 1: DECISION_LOG エントリ追加

`docs/DECISION_LOG.md` 末尾に「2026-05-11: F-trial-run-post-tune 完了 — F-jp-coverage-tune-followup 改修後の本番試運転」エントリを追加 (背景 / 議論 / 決定 / 結果 / 関連ファイル の 5 セクション構成)。

### Task 2: FUTURE_WORK 更新

- 完了済みセクションに「F-trial-run-post-tune」エントリ追加
- 「Phase A.5-3b 第一作の前提条件として本バッチで題材候補ランク 1 位 (Slot-1 cls-6889e9e1c7ac) が出たことを明記」
- 「F-stream-2-filter-design 責務範囲再評価」「verify_two_stage 本番配線判断」「particular_angle_metadata / sontaku_signals 本番配線判断」を新規追加

### Task 3: 完了レポートに更新内容明記

本 REPORT.md 本セクション (8) で明記。

### Task 4: DISCUSSION_NOTES 整理

- 4-A 新規追加:
  - 「2026-05-11: F-13.B WL ヒット品質問題 — matched_urls がベアドメインのみで記事レベル一致が不明 (F-trial-run-post-tune で観察)」
  - 「2026-05-11: production-pipeline と docs 概念整理の乖離 — verify_two_stage / particular_angle_metadata / sontaku_signals 全て本番未配線 (F-trial-run-post-tune で観察)」
- 4-B 既存再評価:
  - 「2026-05-09: Grounding API の構造的限界」エントリに本バッチ観察を追記 (WL 拡張で 3/3 ヒット = 主因解消の本番証拠)
  - 「2026-05-09: stream_3 過剰検出」エントリに本バッチ観察を追記 (production-pipeline では stream 機械判別が稼働しないため、stream_3 過剰検出も本番では現れない)
  - 「2026-05-07: F-13.B Grounding 検索クエリ品質問題」エントリに本バッチで状況改善を追記

### Task 5: CURRENT_STATE 全置換更新

最終更新日 = 2026-05-11、F-trial-run-post-tune 完了反映、Phase A.5-3a-verify ロードマップに 1-G'' (F-trial-run-post-tune) 行追加、F-13.B 防衛機構行に WL 拡張本番効果反映、次バッチ候補に Phase A.5-3b 第一作起案を最有力候補として昇格、追加で「verify_two_stage / particular_angle_metadata / sontaku_signals 本番配線判断」並走バッチを記載。

---

## 9. 環境構築・依存追加

- requirements.txt 追加: なし
- 環境変数追加: なし
- 新規ファイル:
  - `docs/runs/F-trial-run-post-tune/REPORT.md` (本ファイル)
  - `docs/runs/F-trial-run-post-tune/environment_snapshot.json`
  - `docs/runs/F-trial-run-post-tune/trial_run_log.json`
  - `docs/runs/F-trial-run-post-tune/trial_run_log.txt` (生ログ)
  - `docs/runs/F-trial-run-post-tune/ingestion_log.txt` (生ログ)
  - `docs/runs/F-trial-run-post-tune/f13b_output_analysis.json`
  - `docs/runs/F-trial-run-post-tune/defense_layers_audit.json`
  - `docs/runs/F-trial-run-post-tune/script_quality_audit.json`
  - `docs/runs/F-trial-run-post-tune/first_video_candidate_ranking.json`
  - `docs/runs/F-trial-run-post-tune/first_video_candidate_ranking.md`
- 更新ファイル:
  - `docs/CURRENT_STATE.md` (全置換更新)
  - `docs/DECISION_LOG.md` (エントリ追加)
  - `docs/FUTURE_WORK.md` (完了済み移動 + 新規残課題追加)
  - `docs/DISCUSSION_NOTES.md` (新規 2 件追加 + 既存 3 件更新)

`src/` `tests/` `configs/` `scripts/` `CLAUDE.md` 全て 0 行変更、baseline 1390 passed 維持。

---

*このレポートは F-trial-run-post-tune (Phase A.5-3a-verify 1-G'') が自動生成。
F-jp-coverage-tune-followup マージ後の本番試運転 + 防衛機構 5 層監査 + 拾われた Slot
の台本品質確認 + 第一作題材ランク付けの 4 角度統合。Phase A.5-3b 第一作の前提条件を確保。*
