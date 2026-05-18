# F-trial-run-post-llm-extraction 統合レポート

実行日時: 2026-05-16 12:09-12:31 JST
main HEAD コミット: `ba51e5f` (F-jp-coverage-llm-judgement-extraction B-3' マージ後)
試運転コマンド: `python -m src.ingestion.run_ingestion && python -m src.main --mode normalized`
batch_id: `20260516_030927`

---

## 1. バッチ概要

F-jp-coverage-llm-judgement-extraction (2026-05-16 merge、`ba51e5f`) で LLM judgement
bypass を Option (i) で根本治療 (`_parse_llm_judgement` + B-3' 表) した改修後の
**本番試運転**を実施。改修後 F-13.B + 防衛機構 5 層の本番挙動確認、拾われた Slot の
axis_5 主観評価、video_payload 画像プロンプト品質確認 (F-image-prompt-spec 事前調査)、
Phase A.5-3b 第一作題材確定の 4 角度で測定。

「観察と記録に集中するバッチ」+「動くものを壊さない」哲学に従い、`src/` `tests/`
`configs/` `scripts/` `CLAUDE.md` 全て 0 行変更、`docs/` + `data/output/` のみ更新。
baseline **1417 passed** 維持。

| 項目 | 結果 |
|---|---|
| 試運転実行 | ✅ 成功 (job_id=d7062d13..., batch_id=20260516_030927, exit 0, ~22分) |
| F-13.B 動作 | ✅ **B-3' が production verify() に確かに配線・本番で安全装置発火** |
| F-13.B 結果分布 | ★★★ 反転: 1 True / 2 False (F-trial-run-post-tune は 3/3 True bypass だった) |
| 防衛機構 5 層 | ✅ 全層機能 (F-13 隠れ層のみ 0 件 = quality floor ブロック自体なし) |
| 台本生成 | 1 件 (Slot-1 cls-e2429c77f48e) のみ、Slot-2/3 は F-16-A article-only |
| axis_5 主観評価 | 候補B (cls-e2429c77f48e) = **15/25** |
| 第一作題材確定 | **選択肢4: 候補A cls-6889e9e1c7ac を perspective_gap framing で確定** |
| baseline テスト | ✅ 1417 passed (`src/ tests/ configs/ scripts/` 0 変更) |

---

## 2. 試運転実行結果

### 2.1 パイプライン全体

- batch_id: `20260516_030927`
- RSS 取得: 41 ソース (NHK系/Asahi/Yomiuri/Kyodo 他 + 海外 38)、608 articles loaded (1284→608 garbage除去)
- clustering: 369 events built (giant cluster 147件=台湾武器売却を3分割)
- F-1 EditorialMissionFilter: 369 → **20 通過** (threshold 45.0、prescore max 56.25/mean 23.82)
- EliteJudge Gate3: 10 評価 → 採用 7 / 棄却 3 (基準未達)
- GeminiJudge: 2 候補 → blind_spot_global=1 (cls-51fe3e924b0c) + investigate_more=1 (cls-02e505cc1310)
- F-5 fallback: 1 件発火 (cls-02e505cc1310, editorial_mission=75.0 → flagship 認定)
- Slot 選定: 3 件、Budget run_llm=40/150 (publish_reserve_preserved=True)

### 2.2 Slot 別詳細

| # | Event ID | Title | source | mission | F-13.B | llm_judgement | B-3' ブランチ | Outputs |
|---|---|---|---|---|---|---|---|---|
| 1 | cls-e2429c77f48e | Ukrainian drones stray into Baltic/Finnish airspace (Russian EW) | Meduza | 83.0 | **True** / tier_1 / matched=2 (newsweekjapan.jp, yomiuri.co.jp) | `uncertain` | WL あり+uncertain→True (WL尊重) | article+script+video_payload+evidence |
| 2 | cls-f48ab61c4b45 | US congresswoman: 'Nakba did not end in 1948' | Middle East Eye | 89.0 | **False** / None / matched=0 / excluded=1 | `no_match` | WL なし→False | article only |
| 3 | cls-02e505cc1310 | Nearly 200 ex-diplomats call on Canada to act against Israel | Middle East Eye | 75.0 | **False** / tier_2 / matched=1 / excluded=1 | `no_match` | ★ WL あり+no_match→**False (安全装置発火)** | article only |

★ 選定 3 Slot は全て前回 F-trial-run-post-tune (cls-6889e9e1c7ac / cls-1a38c0ca8c99 /
cls-03892eab2072) とは**別 RSS 日の別題材**。Slot 単位の系統判定変化追跡は不可、
分布・挙動レベルでの比較のみ実施。

### 2.3 重要な所見

#### ★★★ 重要 1: B-3' が production verify() に配線・本番で安全装置初発火

Slot-3 cls-02e505cc1310 は WL `tier_2_wire_service` matched=1 だが
`llm_judgement=no_match` のため `has_jp_coverage=False` に B-3' 安全装置で覆った。
これは production `verify()` (broad-only) に B-3' が確かに配線されている**決定的証拠**。
F-trial-run-post-tune では 3/3 が bare-domain afpbb/nippon の WL マッチだけで強制 True
(= LLM judgement bypass そのもの) だったが、本バッチで bypass が**構造的に解消**。

#### ★ 重要 2: has_jp_coverage 分布が 3/3 True → 1 True / 2 False に反転

LLM judgement が捕捉され誤陽性 WL マッチが除去された結果、Hydrangea ブランド
メッセージ (`blind_spot_global` ルート = 「日本では報道されない」) が **2/3 Slot で復活**。
F-trial-run-post-tune で観察された「WL 拡張で blind_spot_global ルートが機械判別で
消滅」現象が B-3' で是正された。

#### ★ 重要 3: Slot-1 の WL マッチ品質向上 (bare-domain → tier_1 実名紙)

Slot-1 は afpbb bare-domain ではなく **tier_1 実名紙 2 件 (newsweekjapan.jp +
yomiuri.co.jp)** でマッチ。`llm_judgement=uncertain` を WL マッチが正しく上書き
(B-3': uncertain→True) = B-3' の Recall 保護 (Task E 過剰保守退行の修正) も本番で機能。

#### ★ 重要 4: production-pipeline の未配線状況は前バッチと不変

verify_two_stage / particular_angle_metadata / sontaku_signals は依然本番未配線。
src/main.py は legacy verify() (broad-only) のみ呼び出し。系統 1/2/3 機械判別は
production-pipeline 上では実施されない。新ルート generate_script_with_analysis も
未起動 (analysis_result=null、旧ルート write_script で台本生成)。

#### ★ 重要 5: llm_judgement_text が非永続化 (観察事項)

run_log には `llm_judgement` 分類値 (uncertain/no_match) のみ出力。full response_text
は run_log にも cache (jp_coverage_cache.db は空) にも非永続化。本バッチでは
judgement 分類値で十分だが、将来のデバッグ用に response_text 永続化は検討余地
(スコープ拡大せず観察記録のみ、DISCUSSION_NOTES 4-A 記載)。

---

## 3. F-13.B 改修後の本番挙動分析 (Task C)

詳細: `docs/runs/F-trial-run-post-llm-extraction/f13b_output_analysis.json`

### 3.1 F-trial-run-post-tune (5/11) との比較

| 観点 | F-trial-run-post-tune | F-trial-run-post-llm-extraction | Delta |
|---|---|---|---|
| has_jp_coverage 分布 | 3/3 True | 1 True / 2 False | **反転 (bypass 解消)** |
| WL ヒット品質 | 全 bare-domain (afpbb×2, nippon×1) | Slot-1 tier_1 実名紙2件 / Slot-3 tier_2 を no_match で却下 | **品質向上 + 誤陽性除去** |
| llm_judgement | 未捕捉 (bypass) | uncertain×1, no_match×2 捕捉 | **B-3' 本番配線確認** |
| blind_spot_global ルート | 機械判別で消滅 | 2/3 Slot で復活 | **ブランド整合改善** |
| B-3' 安全装置発火 | n/a (B-3' 未実装) | 1 件 (Slot-3) | **新規** |
| 系統機械判別 | n/a (verify_two_stage 未配線) | n/a (不変) | 変化なし |

### 3.2 B-3' 各ブランチの本番発火実績

| B-3' ブランチ | 本番発火 | 該当 Slot |
|---|---|---|
| WL あり + match → True | 0 | — |
| WL あり + **no_match → False (安全装置)** | **1** | Slot-3 cls-02e505cc1310 |
| WL あり + uncertain → True (WL尊重) | 1 | Slot-1 cls-e2429c77f48e |
| WL あり + None → True (後方互換) | 0 | — |
| WL なし → False | 1 | Slot-2 cls-f48ab61c4b45 |

B-3' 設計表の全主要ブランチが本番で正しく機能。特に Task E-fix で修正した
`uncertain→True` (WL尊重) と核心の `no_match→False` (安全装置) の両方が同一試運転で
発火し、設計通りの挙動を確認。

---

## 4. 防衛機構 5 層の発火状況 (Task C-2)

| 層 | 発火状況 | 結果 |
|---|---|---|
| F-1 EditorialMissionFilter | 369 → 20 通過 (threshold 45.0)、選定3 Slot scores 83/89/75 | ✅ 正常稼働 |
| F-2 FlagshipGate / EliteJudge | Gate3 10評価→採用7/棄却3、GeminiJudge 2件、CoherenceGate 2件 PASSED、**Blocked 0** | ✅ 正常稼働 |
| F-13.B JpCoverageVerifier | 3 invocations: True×1 / False×2、**B-3' 安全装置 1 件発火** | ✅ bypass 構造解消確認 |
| F-5 下流救済 | 1 件発火 (cls-02e505cc1310, editorial_mission=75.0→flagship)。reranked_top だが scheduler は cls-e2429c77f48e を動画Slot-1 に保持、本件は Slot-3 へ | ✅ 正常稼働 |
| F-13 隠れ層 (quality_floor bypass) | **0 件** (quality_floor_report per_event 空 = quality floor ブロック自体が発生せず、bypass 不要) | ✅ 正常 (前回1件発火と挙動差) |

全 5 層が構造的に機能。F-13 隠れ層は前回 (Slot-1 で 1 件発火) と異なり 0 件 =
本試運転では quality floor ブロックが発生しなかったため bypass 不要 (= 隠れ層は
ブロック発生時のみ作動する設計通り)。

---

## 5. axis_5 主観評価 + 第一作題材確定 (Task D)

詳細: `docs/runs/F-trial-run-post-llm-extraction/axis_5_evaluation.json`

### 5.1 候補B (cls-e2429c77f48e) axis_5 採点 = 15/25

| 観点 | 点 | カズヤ + クラウド協議コメント |
|---|---|---|
| 1. 台本の刺さり度 | 4 | hook+twist 強い (ラトビア政府退陣+「弾丸一発使わず政治破壊」= ReHacQ級) が punchline 失速 |
| 2. Hydrangeaブランド整合 | 3 | punchline メディア断定が「中間が良い」原則から外れる、修正必須 |
| 3. 系統判定の妥当性 | 3 | perspective_gap、platform_title「日本では報道されない」誇大 |
| 4. 動画化適性 | 3 | twist 165字詰めすぎ中盤失速、抽象図解のみ |
| 5. video_prompt品質 | 2 | F-image-prompt-spec スコープ再定義事案、ブランド表現不足 |

### 5.2 第一作題材確定 = 選択肢4: 候補A perspective_gap framing

| 項目 | 内容 |
|---|---|
| event_id | **cls-6889e9e1c7ac** |
| title | Israel Prison 9,600 Detainees / ICRC 監視操作疑惑 |
| source | TeleSUR (F-trial-run-post-tune Slot-1) |
| editorial_mission_score | 86.0 (機械1位) |
| 系統判定 | **perspective_gap 確定** (F-wl-hit-quality-audit 2026-05-14) |
| axis_5 試算 | 19/25 (web側クラウド試算、Phase A.5-3b 第一作起案バッチで台本生成後に最終確定) |

**framing 指針** (Phase A.5-3b 第一作起案バッチで反映):
1. 「9,600人虐待 itself は afpbb 等で日本でも報道済み」を明示
2. 「しかし ICRC 監視操作疑惑等の specific 角度は日本主要メディアで未報道」が perspective_gap の核心
3. platform_title は「日本では報道されない」誇大を避け「日本では触れられない構造」「日本の報道で抜け落ちる視点」等の中立表現に修正
4. 台本 punchline は「中間が良い」原則遵守 (シニカル × 生活実感への着地、メディア断定回避)

**候補B 不採用理由**: punchline メディア断定矛盾 / Meduza 単独+露発二重バイアス /
題材専門性過多 (80秒に多層構造) / axis_5 15 < 候補A試算 19。
**候補C 不採用理由**: 再試運転コスト対効果不足 / perspective_gap でも Hydrangea
ミッション十分達成可能 (観点の選択的欠落=忖度を暴く構造)。

---

## 6. video_payload 画像プロンプト確認 (F-image-prompt-spec 事前調査, Task C-4)

詳細: `docs/runs/F-trial-run-post-llm-extraction/video_payload_audit.json`

★ **重要発見**: バッチプロンプトの想定 (`image_prompt` フィールド + 統一シネマティック
末尾 + 12-15枚/80秒) は**現行実装に存在しない**:
- スキーマは `video_prompt` + `negative_prompt` (image_prompt フィールド無し)
- **4 scene のみ** (script 4ブロック hook/setup/twist/punchline に 1:1 対応)
- 統一シネマティック末尾なし。`visual_safety_level=elevated` で実在人物肖像・再現
  映像・戦闘映像を明示禁止する強い negative_prompt
- 4 モード (anchor_style / document_style / structure_diagram / infographic) = 抽象図解志向

→ **F-image-prompt-spec は「既存 image_prompt の品質改善」ではなく「image_prompt
レイヤーが現行に無い前提での新設 or video_prompt 拡張の設計判断」バッチになる。**
バッチプロンプトのスコープ前提自体の再定義が必要 (Task F で FUTURE_WORK に新規残課題化)。

---

## 7. 残課題 / カズヤ確認推奨事項

### 7.1 Phase A.5-3b 第一作着手前の追加確認事項 (カズヤ指示、Task F で FUTURE_WORK 記載)

1. **F-trial-run-candidate-a-reverify (仮称)**: 候補A (cls-6889e9e1c7ac) を改修後 main
   (ba51e5f) で再試運転 1 回 → afpbb bare-domain WL マッチが B-3' でどう判定されるか
   確認 (1 Slot 限定の軽量試運転、別バッチ案件)
2. **F-image-prompt-spec スコープ再定義**: image_prompt フィールド非存在、video_payload
   設計再検討要 (新規残課題)
3. **ElevenLabs 声選定**: Phase A.5-3b 着手前 30 分作業 (既存登録済み、カズヤ手作業)
4. **Remotion セットアップ**: Phase A.5-3b 第一作で Claude Code に書かせる
   (Node 環境カズヤ手動準備)

### 7.2 想定外結果の有無

- ★ 想定通り: B-3' 挙動は設計通り (llm_judgement 全件 None ではなく uncertain/no_match
  を正しく捕捉、安全装置発火も B-3' 表通り)。バッチプロンプトの想定外閾値
  (llm_judgement 全件 None / stream 判定異常) には**該当せず**。
- ⚠️ 観察事項のみ: llm_judgement_text 非永続化 (記録のみ、スコープ拡大せず)。
- ✅ Gemini API timeout / 503 なし。拾われた Slot 3 件 (要件充足)。
- baseline 1417 passed 維持 (src/ tests/ configs/ scripts/ 0 変更)。

---

## 8. BATCH_PROTOCOL Task 1-5 ドッグフーディング適用内容

### Task 1: DECISION_LOG エントリ追加
`docs/DECISION_LOG.md` 末尾に「2026-05-16: F-trial-run-post-llm-extraction 完了 —
B-3' 本番試運転 + 第一作題材確定 (候補A perspective_gap framing)」エントリ追加。

### Task 2: FUTURE_WORK 更新
- 完了済みセクションに「F-trial-run-post-llm-extraction」追加
- 第一作着手判断結果 (選択肢4) 反映
- 新規残課題追加: 「F-trial-run-candidate-a-reverify (仮称)」「F-image-prompt-spec
  スコープ再定義」

### Task 3: 完了レポートに更新内容明記
本 REPORT.md 本セクション (8)。

### Task 4: DISCUSSION_NOTES 整理
- 4-A 新規追加: 「2026-05-16: B-3' 本番安全装置発火 + bypass 構造解消の本番実証」
  「2026-05-16: video_payload に image_prompt レイヤー非存在 (F-image-prompt-spec
  スコープ再定義)」「2026-05-16: llm_judgement_text 非永続化」
- 4-B 既存再評価: 「F-13.B WL ヒット品質問題」エントリに B-3' 本番是正を追記、
  「production-pipeline と docs 概念整理の乖離」エントリに不変を追記

### Task 5: CURRENT_STATE 全置換更新
最終更新日 2026-05-16、F-trial-run-post-llm-extraction 完了反映、ロードマップに
1-I 行を完了化、第一作題材確定 (候補A perspective_gap) を前面化、次バッチ候補刷新。

---

## 9. 環境構築・依存追加

- requirements.txt 追加: なし / 環境変数追加: なし
- 新規ファイル: `docs/runs/F-trial-run-post-llm-extraction/` 配下
  (REPORT.md / environment_snapshot.json / run_log.log / f13b_output_analysis.json /
  video_payload_audit.json / axis_5_evaluation.json)
- 更新ファイル: `docs/CURRENT_STATE.md` (全置換) / `docs/DECISION_LOG.md` /
  `docs/FUTURE_WORK.md` / `docs/DISCUSSION_NOTES.md`
- `data/output/` 配下は本番試運転副産物 (git 管理外、既存運用通り)

`src/` `tests/` `configs/` `scripts/` `CLAUDE.md` 全て 0 行変更、baseline 1417 passed 維持。

---

*このレポートは F-trial-run-post-llm-extraction (Phase A.5-3a-verify ゲート完了後の
11 つ目のバッチ) が生成。F-jp-coverage-llm-judgement-extraction B-3' 改修後の本番
試運転で **LLM judgement bypass の構造的解消を本番実証** + Phase A.5-3b 第一作題材を
候補A perspective_gap framing で確定。「観察と記録に集中するバッチ」+「動くものを
壊さない」原則遵守。*
