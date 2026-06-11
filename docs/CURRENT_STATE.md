# Hydrangea — Current State (CURRENT_STATE.md)

最終更新: 2026-06-11 (★ F-first-work-golden-master 完了、**実装バッチ 1-S** (ゲート完了後 27 つ目)。
**Phase A.5-3b 第一作起案 = 候補A golden master 素材一式の自動出力完成 + 手動動画 PoC の道具立て**。
カズヤ原則「ワークフロー部品は自動で完成させてから手動 PoC。手動なのは動画組立と公開判断のみ」を実装。
①候補A `cls-6889e9e1c7ac` を新ルート + 確定布陣で再生成 (**editorial brief を script プロンプトのみに
プロセス内注入**、production プロンプト不変。article は不変原則 1 で注入不可 = 素のまま生成、brief 充足は
人間編集 + Guardian 再実行ループ = 編集差分が教師信号) ②validation run 2 ガード 3 ランナー実走
(coverage guard / Guardian 第1層 / 第2層 corroboration ×3 run) ③**image_prompt レイヤー新設**
(`src/generation/image_prompt_writer.py` = F-image-prompt-spec の解、決定論 5 プレート = 4 シーン 1:1 +
フックカード 9:16、文字なし / 意味記述正典 / ADR-0001+0003 強制) ④**Remotion テンプレート**
(`manual_poc/remotion/` 独立 npm、セーフゾーン 3 帯紙面 + フックカード + Ken Burns + フレーズ同期字幕 +
BGM ducking、props JSON 完全データ駆動、**ダミー素材 MP4 レンダ実証**) ⑤運用規約 docs 化
(`docs/golden_master_spec.md` = original 凍結 / `*_edited.*` 命名 / 編集→再検証ループ / 手動 PoC
チェックリスト / AI 開示投稿時必須)。★ **設計正典 5 点** (2026-06-10 クラウド調査): セーフゾーン中央帯の
「動く紙面」/ burned-in フレーズ同期字幕 / 文字はコードで描き絵は AI で描く分業 / モデル非結合 (正典 =
意味記述) / サムネ = 第1フレーム = フックカード三役 (ADR-0001/0002 を部分更新、注記済)。★ CP-1 で仮説
6 点検証 (誤り 10 作法)、**重大乖離 2 件訂正** = 候補A analysis.json 非存在 + **extract_perspectives が
構造的 0 件** (sources_en=1 < 最低 2、fallback ゲート sources_total>=2 も不通過を実測) → fallback 同形
hidden_stakes 候補をハーネス注入 (式同形・写し元記録・production 不変)。★ **モデル pin** = QUALITY/ARTICLE
全 Tier を gemini-3.5-flash に固定し 503 波での silent 劣化を fail に変換 (沈黙的劣化の禁止の生成版)。
★ validation 結果: guard run2 で **title contradiction flag** (platform_title silence、title_generator
ハードコード由来 = 想定通り、run1 consistent ⇄ run2 contradiction の **flag 反転分散をガード文脈で初観測**) /
Guardian 第1層 14 主張 → 12 supported + **1 contradicted (c5 = 告発主体の帰属エラー、本物の編集欠陥)** +
1 not_in_source / 第2層 **contradicted 2 (c10/c13 = article の coverage 過大主張を独立日本語ソースが明示
矛盾 = brief 注入不可な article の構造的弱点を実地立証)** + c6 (日本郵船/伊藤忠 = analysis 由来の企業主張)
は run3 で corroborated 回収。★ **punchline 尻切れ再発** (loop-2、X1 と同型 = 標本 2 例目)。手修正対象 5 点を
`flag_summary_for_human_audit.md` にサマリ化 (カズヤ監査の入口)。baseline 1557 → **1581 passed**
(新規 +24、破壊ゼロ)。不変原則 1-5 + **第一作隔離 (6)** 厳守。新規 1 タスク = F-fable5-guardian-poc ★低。
**バッチ完了 = 手動 PoC フェーズ開始** (次バッチは PoC 結果待ち、並走候補あり)。
前バッチ: F-editorial-guardian-corroboration 完了 (2026-06-10、1-T.2、ゲート完了後 26 つ目)。Editorial
Guardian 第2段 = 真実性検証 (grounding 複数ソース突合) + 公開可否バー (supported × corroborated のみ
非 flag)。検索と判定の分離 (証拠収集 = GUARDIAN_GROUNDING_MODEL 軽量 / 判定 = Guardian 単一モデル =
沈黙的劣化の禁止)。X1 Slot-1 実走 2 回 = 503 波下で沈黙的劣化の禁止が実地で機能。baseline 1519 → 1557。
前々バッチ: F-editorial-guardian-claim-extraction (2026-06-10、1-T.1)。Guardian 第1段 = 高リスク主張
抽出 + 忠実性検証。X1 Slot-1 で「兵士 25 人死亡」帰属取り違え検出。baseline 1487 → 1519)

> このドキュメントは Hydrangea の「今この瞬間のスナップショット」。
> 各バッチ完了時に Claude Code が **全置換更新** する (追記ではない)。
> 過去の経緯は DECISION_LOG.md / FUTURE_WORK.md / DISCUSSION_NOTES.md を参照。

---

## 0. Hydrangea コアミッション (2 系統並立)

> ★最重要: 別チャット移行時のクラウド誤り再発防止のため冒頭配置 (F-doc-cleanup-followup / 2026-05-03)。
> 系統 1 中心で理解して系統 2 を過小評価する誤りはクラウド誤り 7 として記録済み。

Hydrangea のコアミッションは **2 系統並立** で、片方だけでは Hydrangea のメディア性が成立しない。

★ 2026-05-07 (F-particular-angle-design) で系統 1 / 系統 2 の判定単位が
**「特定角度」(particular_angle)** に正典化された。判定基準の正本は
`docs/PARTICULAR_ANGLE_DEFINITION.md`。

★ 2026-05-08 (F-particular-angle-redesign) で **3 分類 → 4 分類化** が完了。
系統 2 (perspective_gap) を独立させ「完全空白」と「観点不足」を分離した。

★ 2026-05-08 (F-particular-angle-redesign-extension) で **系統名 1/1.5/2 →
1/2/3** にリネーム + sontaku_signals 別軸メタデータ独立化 + MECE 判別基準
明示 + クラウド誤り 9 (各論コントロールの誘惑) を CLAUDE.md / DISCUSSION_NOTES
に記録。

★ 2026-05-16 (F-jp-coverage-llm-judgement-extraction) で **LLM judgement
bypass 問題を Option (i) で根本治療完了**。`_parse_llm_judgement` 新規 +
B-3' 表。LLM の **明示的否定 (no_match)** のみ尊重し **沈黙 (uncertain)** を
否定と読み替えない。

★ 2026-05-26 (F-jp-coverage-cache-judgement-persist) で **F-13.B の
llm_judgement / llm_judgement_text を 24h cache に永続化** (案 A)。

★ 2026-05-26 (F-script-writer-target-enemy-fix-investigate) で target_enemy 問題の
真因 a 確定 = 旧ルート `write_script` の仮想敵 framing は不変原則 2 で修正不可、
**新ルート配線 (X1) が唯一の解消経路**。

★ 2026-05-27 (F-gemini-3.5-flash-api-audit / F-docs-update-chatgpt-round2-and-error10 /
F-gemini-quality-tier-poc) で Gemini 3.5 Flash migration 不要確定 + クラウド誤り 10 を
CLAUDE.md 明文化 + **最終布陣 v2** 配線 (QUALITY=gemini-3.5-flash / LIGHTWEIGHT=
gemini-3.1-flash-lite + JUDGE_MODEL 明示 + Gemini 3 系 temperature ガード)。

★ 2026-06-08 (F-article-model-upgrade、1-R.5) で **article = gemini-3.5-flash 品質昇格**
(選択肢C 第一歩、role 分離維持)。

★★★ 2026-05-31 (F-particular-angle-metadata-production-wire、X1、1-R) で
**`particular_angle_metadata` + nested `sontaku_signals` を production に配線完了**。
新ルート `generate_script_with_analysis` が production default 起動、**target_enemy が
production から自動退役**。baseline 1432 → 1466。

★ 2026-06-08 (F-title-guard-coverage-claim-policy、1-Q.5) で **coverage claim 事実整合
guard** 新設 (policy YAML + script プロンプト原則 + LLM judge guard = B-3' / flag のみ)。

★ 2026-06-10 (F-editorial-guardian-claim-extraction、1-T.1) で **Editorial Guardian 第1段**
(高リスク主張抽出 + 元ソース忠実性 3値判定 + 2層レポート骨格、GUARDIAN role =
gemini-3.1-pro-preview 単一要素 tier list = 沈黙的劣化の禁止)。

★ 2026-06-10 (F-editorial-guardian-corroboration、1-T.2) で **Editorial Guardian 第2段**
(真実性検証 = grounding 複数ソース突合、検索と判定の分離、truthfulness 語彙 + **公開可否バー =
supported × corroborated のみ非 flag**)。**これで第一作 (1-S) 前の関門ゼロ**。

★★★ 2026-06-11 (F-first-work-golden-master、1-S) で **第一作 golden master 素材一式が完成**。
候補A の script (brief 注入) / article / analysis / video_payload / image_prompts 5 本を
`data/output/golden_master/` に original 凍結、validation 3 レポート + 手修正対象リストを
`docs/runs/F-first-work-golden-master/` に出力。Remotion テンプレート (ダミー MP4 実証済) +
tts_to_captions + 編集→再検証ループ規約 (`docs/golden_master_spec.md`) で**手動 PoC の道具が
全部揃った**。残りは人間工程のみ (flag レビュー編集 / ElevenLabs / 画像 3 候補比較 / 実素材レンダ /
axis_5 / 公開判断)。

### 系統 1 (silence_gap): 完全な情報空白 — 広範事件も特定角度も日本主要メディアで未報道

完全な情報空白で、Hydrangea コアミッションど真ん中。台本表現は「日本では報じられ
なかった」が成立する。25 件アノテーション最終分類で 4 件 (16%)。

### 系統 2 (perspective_gap): 観点不足 — 広範事件は報道済み、特定角度は未報道

事件本体は日本でも取り上げられたが、海外メディアが独自に掘った構造分析角度は
深掘りされていない。台本表現は「日本でも事件は取り上げられたが、◯◯という構造に
は触れられていない」。25 件最終分類で **20 件 (80%)**。

★★★ 第一作 (候補A cls-6889e9e1c7ac) は本系統の framing で **golden master 完成済み**
(2026-06-11)。機械抽出も stream_2_perspective_gap を返し人間確定値と一致 (訂正不要だった)。
setup「事実は、日本でも報道されています。しかし、そこにある隠蔽の構造までは報じられていません」=
brief が意図した perspective_gap framing が台本に実装された。

### 系統 3 (framing_inversion): 報道差の背景解説 — 特定角度も報道済み + 解釈差 + 忖度シグナル

広範事件 + 特定角度も日本主要メディアで報道済み + 評価フレーム対立 +
sontaku_signals.level=high/medium の 3 条件。25 件最終分類で **0 件** ★ 想定外
(根本治療は Phase A.5-3b 第二作のサンプル拡充)。

### ブランドポジション

ReHacQ・東洋経済オンラインのトーン。シニカル × 知性、ただし
**「シニカル × 視聴者の生活実感への着地」** が punchline 定義。
陰謀論・扇動禁止、情報密度で勝負。ターゲット: 20 代後半〜40 代の知的好奇心が
高いビジネス層。★ 視覚ブランドは ADR-0001 で正典化 (5 色パレット、editorial
路線、cinematic/photorealistic 禁止)。★ 2026-06-11 設計正典 5 点 (中央帯紙面 /
フレーズ同期字幕 / 文字とプレートの分業 / モデル非結合 / フックカード三役) を追加
(ADR-0001/0002 部分更新、`docs/golden_master_spec.md` §5 + DECISION_LOG 2026-06-11)。

### 3 チャンネル構想と現フォーカス

| チャンネル | 内容 | 状態 |
|---|---|---|
| `geo_lens` | Geopolitical Lens (政治・経済地政学) | **現在唯一のフォーカス** |
| `japan_athletes` | 海外で戦う日本人アスリート | Phase B 以降、未確定 |
| `k_pulse` | 韓国エンタメ | Phase B 以降、未確定 |

Phase A.5-3d で本番リリースするのは geo_lens のみ単独。

### Phase B 以降の新選択肢: 大規模調査機能 (オンデマンド深掘り)

通常運用とは別に、カズヤが事象を指定して大規模調査 → 長尺動画 + 記事を
生成する手動起動パイプラインを Phase B 以降に追加する構想。

---

## 1. リポジトリ状態

- **main HEAD コミット**: `18b5287` (Merge branch 'feature/F-editorial-guardian-corroboration' = 1-T.2 マージ済)。F-first-work-golden-master (1-S) は feature ブランチ `feature/F-first-work-golden-master` で完了、本完了レポート提示後にカズヤ承認 → commit/merge 実行。★ 本バッチは実装バッチ (manual_poc/ 新設一式 + image_prompt_writer.py + video_payload_writer.py 1 行 + tests 2 ファイル + docs/golden_master_spec.md + docs/runs/F-first-work-golden-master/ + ADR-0001/0002 注記 + docs)
- **直近 6 件のログ (main、F-first-work-golden-master merge 前)**:
  ```
  18b5287 Merge branch 'feature/F-editorial-guardian-corroboration'
  132082a feat: F-editorial-guardian-corroboration (1-T.2) 真実性検証 = grounding 複数ソース突合 + 公開可否バー + レポート enrichment
  a1754b6 Merge branch 'feature/F-editorial-guardian-claim-extraction'
  b7e9256 feat: F-editorial-guardian-claim-extraction (1-T.1) Editorial Guardian 第1段 — 高リスク主張抽出 + 忠実性検証 + 2層レポート骨格
  1bead80 Merge branch 'feature/F-title-guard-coverage-claim-policy'
  091cf5e feat: F-title-guard-coverage-claim-policy (1-Q.5) coverage claim 事実整合の構造データ + 生成プロンプト原則 + 生成後 guard
  ```
- **baseline テスト数**: **1581 passed** (F-first-work-golden-master で新規 +24 = `tests/test_image_prompt_writer.py` 18 + `tests/test_tts_to_captions.py` 6。いずれも決定論 (LLM 非関与) で mock 不要。変更前 baseline 1557 passed 実測 = 381s、変更後 1581 passed = 345s)
- **DB schema 変更**: なし (recent_event_pool は読み取りのみ。production 変更は `src/generation/image_prompt_writer.py` 新規 + `src/generation/video_payload_writer.py` L72 仮想敵 1 行除去のみ。article_writer.py / script_writer.py / triage / analysis 既存ファイル 0 行)
- **Node 依存**: `manual_poc/remotion/` は独立 npm プロジェクト (Remotion 4.0.475、node_modules は gitignored)。本体 requirements.txt 変更なし

## 2. 現在のフェーズ

- **Phase**: Phase A.5-3b 第一作 — **golden master 完成、手動 PoC フェーズ開始** (2026-06-11)
- **進行中バッチ**: なし (F-first-work-golden-master 完了直後、完了レポート提示 → カズヤ承認待ち → commit/merge)
- **★ 手動 PoC (カズヤ工程、`docs/golden_master_spec.md` §4 チェックリストが正本)**:
  1. flag レビュー (`docs/runs/F-first-work-golden-master/flag_summary_for_human_audit.md` = 入口、手修正対象 5 点) → `*_edited.*` 編集 → ガード 3 本再実行ループ
  2. ElevenLabs 実生成 (声選定済み前提) → `manual_poc/tts_to_captions.py` で captions 変換
  3. 画像 3 候補比較 (image_prompts.json の同文投入: Nano Banana Pro / GPT Image 2 / Flux 2 系)
  4. BGM 用意 (ロイヤリティフリー、editorial トーン) → Remotion 実素材レンダ (props JSON 差し替え)
  5. axis_5 採点 → 公開判断 (公開可否バー + ADR-0003 チェックリスト + **AI 開示ラベル投稿時必須**)
- **次バッチ候補と推奨** (★ F-first-work-golden-master / 2026-06-11 更新):
  - ~~**1-S Phase A.5-3b 第一作起案**~~ ✅ **golden master 部分完了 (2026-06-11)**。残り = 上記手動 PoC。
  - **1st (PoC 結果待ちの間の並走候補): F-script-punchline-tail-cut-investigate** ★中 (★ 1-S で標本 2 例目 = loop-2 × 尻切れの再現性確認、調査優先度が上がった)
  - **2nd: F-trial-data-procurement-protocol** ★中 (試運転実行手順整備)
  - **3rd: F-evidence-jp-coverage-audit-trail** ★中 (案 B、score_breakdown evidence 証跡化)
  - **4th: F-grounding-determinism-audit** ★ (run 間分散。★ 1-S で観測実例がさらに増えた = guard flag 反転 (consistent ⇄ contradiction) + corroboration c12 判定揺れ + c6/c7 run3 回収。観測 4 文脈目)
  - **5th: F-title-generator-stream-aware-fix** ★中 (1-S で guard flag が実証 = platform_title silence は第一作で手修正、根本修正の価値が確認された)
  - **6th: F-guardian-production-wire** ★中 (第一作後、Phase A.5-3d 投稿前ゲート統合)
  - **7th: F-fable5-guardian-poc** ★低 (条件付き、第一作の人間監査済み ground truth 確定後)
  - **8th: F-periodic-health-check** ★ (Phase A.5-3d 着手時) / 本番配線判断バッチ群 (verify_two_stage / F-stream-2-filter-design) / 低優先整合タスク群 ★低
- **推奨フロー**:
  - F-first-work-golden-master (✅ 完了) → commit/merge (カズヤ承認後)
    → **カズヤ手動 PoC** (上記 1-5、公開判断まで)
    → 並走: F-script-punchline-tail-cut-investigate / F-trial-data-procurement-protocol 等
    → PoC 完了後: 第二作起案 or Phase A.5-3c (合成パート自動化 = ElevenLabs/画像/Remotion の本番統合) 判断

### Phase A.5-3a-verify ロードマップ (★ F-first-work-golden-master / 2026-06-11 更新版)

**ゲート完了**: 1-A〜1-D''' 全段階完了で Phase A.5-3a-verify ゲート完了 (2026-05-07)。
本バッチ (F-first-work-golden-master) はゲート完了後の **27 つ目のバッチ**。

| 段階 | バッチ | 状態 | 概要 |
|---|---|---|---|
| 1-A〜1-K | (F-verify-jp-coverage-golden 〜 F-image-prompt-spec) | ✅ 完了 | ゲート完了 + 特定角度正典化 + LLM judgement bypass 根本治療 + 候補A 前提確定 + ADR 3 件 |
| 1-L〜1-P.6 | F-gemini-model-audit 〜 F-docs-update-chatgpt-round2-and-error10 | ✅ 完了 | Gemini モデル戦略 / 5/25 shutdown / locale key / cache 永続化 / target_enemy 調査 / API audit / 誤り 10 明文化 |
| 1-Q | F-gemini-quality-tier-poc | ✅ 完了 (2026-05-27) | 最終布陣 v2 配線 |
| 1-R | F-particular-angle-metadata-production-wire (X1) | ✅ 完了 (2026-05-31) | 新ルート production default 起動 + target_enemy 自動退役。baseline 1432→1466 |
| 1-R.5 | F-article-model-upgrade | ✅ 完了 (2026-06-08) | article = gemini-3.5-flash 品質昇格。baseline 1466 維持 |
| 1-Q.5 | F-title-guard-coverage-claim-policy | ✅ 完了 (2026-06-08) | coverage claim 事実整合 3 層。baseline 1466→1487 |
| 1-T.1 | F-editorial-guardian-claim-extraction | ✅ 完了 (2026-06-10) | Guardian 第1段 = 抽出 + 忠実性。baseline 1487→1519 |
| 1-T.2 | F-editorial-guardian-corroboration | ✅ 完了 (2026-06-10) | Guardian 第2段 = 真実性 + 公開可否バー。baseline 1519→1557 |
| **1-S** | **F-first-work-golden-master** | ✅ **完了 (2026-06-11、実装)** | **ゲート完了後 27 つ目**。第一作 golden master 素材一式の自動出力完成 + 手動 PoC 道具立て。①候補A 新ルート再生成 (brief script 注入 / モデル pin = 全 Tier 3.5-flash / fallback 検出 fail-fast) ②validation 2 ガード 3 ランナー (title silence flag + c5 帰属エラー + c10/c13 coverage 過大の明示矛盾 + c6 corroborated 回収) ③image_prompt レイヤー新設 (決定論 5 プレート、文字なし / 意味記述正典) ④Remotion テンプレート (3 帯紙面 + フックカード + Ken Burns + フレーズ同期字幕 + ducking、ダミー MP4 実証) ⑤golden_master_spec.md 正典化。CP-1 重大乖離 2 件訂正 (analysis.json 非存在 / 観点候補構造的 0 件 → fallback 同形注入)。punchline 尻切れ標本 2 例目。baseline 1557→1581 |
| 1-S 後続 | 手動 PoC (カズヤ) | ★ **進行中フェーズ** | flag レビュー編集 → 再検証ループ → ElevenLabs → 画像 3 候補 → 実素材レンダ → axis_5 → 公開判断 |
| 1-U | F-script-punchline-tail-cut-investigate / F-trial-data-procurement-protocol / F-evidence-jp-coverage-audit-trail / F-grounding-determinism-audit / 本番配線残分 | ★ 並走候補 | PoC 結果待ちの間に消化可 |

### Phase A.5-3d 投稿対象の補足

Phase A.5-3d で本番リリースする対象は **geo_lens (政治・経済) のみ**。
投稿先は TikTok と YouTube Shorts の両方同時、完全自動投稿 (cron 6 時間おき、
人手介入ゼロ、投稿前ゲートで品質保証)。★ 投稿前ゲートのチェックリスト 6 項目は
ADR-0003 で正典化。★ AI 生成コンテンツ開示 (YouTube/TikTok ラベル) は投稿時必須
(golden_master_spec §4 にも明記)。★ 完全自動投稿の前提として F-periodic-health-check
(緊急度 中、Phase A.5-3d 着手時) + F-guardian-production-wire (★中) が必要。

## 3. 直近の試運転結果サマリー

> ★ F-first-work-golden-master (1-S / 2026-06-11) は **パイプライン試運転なし** (保存済み候補A
> snapshot に対する単発再生成ハーネス + offline validation run)。
> **生成**: `manual_poc/generate_golden_master.py` で候補A を再生成。初回 run で 503 波により
> article が tier3 (gemini-3.1-flash-lite) へ silent 劣化 → **モデル pin (QUALITY/ARTICLE 全 Tier =
> gemini-3.5-flash) を追加して再生成** = 全成果物が確定布陣由来 (script retries=0 / target_enemy=None /
> char validation passed / 機械 stream = stream_2_perspective_gap で人間確定値と一致・訂正不要)。
> **validation**: coverage guard ×2 run (run1 consistent → run2 **title contradiction flag** =
> 同一入力で flag 有無反転、ガード文脈の run 間分散初観測) / Guardian 第1層 (14 主張 → 12 supported /
> 1 contradicted = c5 告発主体帰属エラー / 1 not_in_source) / 第2層 corroboration ×3 run (canonical =
> run1。corroborated: c2/c3/c4/c12/c14 + run3 で c6/c7 回収。**contradicted: c10/c13** = article
> 「日本では詳細報道が極めて少ない」に独立日本語ソースが明示矛盾。unverified: c8/c9 = 3 run とも
> 503、再実行で回収予定。c12 = corroborated ⇄ uncorroborated の判定揺れ = 503 ではなく証拠セット差)。
> レポート: `docs/runs/F-first-work-golden-master/` (guardian_report + enriched canonical/run2/run3 +
> guard 2 run + **flag_summary_for_human_audit.md** = 手修正対象 5 点)。コスト概算 ≈ $1 前後 (生成 2 回 +
> guard 2 回 + Guardian 1 回 + corroboration 3 回、503 リトライ込)。
> **Remotion**: ダミー素材 (純 Python 生成) で `npx remotion render FirstWork` → 600 frames / 20s /
> 2.6MB MP4 + 静止フレーム 2 点でレイアウト目視確認 (セーフゾーン / 3 帯 / フックカード / 字幕帯)。

| 試運転 | バッチ | 動画化率 | 主要観察 |
|---|---|---|---|
| **2026-06-11** | **F-first-work-golden-master (1-S)** | **golden master 1 式凍結 (offline)** | 上記。brief 4 点が台本に反映 (報道済み明示 / ICRC 角度 / silence 回避 / TeleSUR 透明化)。punchline 尻切れ再発 (loop-2、標本 2 例目)。Guardian 2 層が編集欠陥 (帰属エラー / coverage 過大) を公開前に捕捉 = 防衛機構が第一作で実効 |
| 2026-06-10 | F-editorial-guardian-corroboration (1-T.2) | offline validation ×2 run | 503 波下で沈黙的劣化の禁止が実地で機能 (run1: 7 corroborated / 12 unverified)、run2 で再実行ループ実証。run 間分散実測 |
| 2026-06-10 | F-editorial-guardian-claim-extraction (1-T.1) | offline validation | X1 Slot-1 の 20 主張中 1 contradicted (「兵士 25 人死亡」帰属取り違え) 検出 |
| 2026-05-31 | F-particular-angle-metadata-production-wire (X1) | 1/3 動画化 + 1 article-only + 1 skipped (completed) | 新ルート本番配線後の Path A pure 試運転。Slot-1 = stream_2_perspective_gap + sontaku high/diplomatic + **target_enemy=None (退役確認)**。axis_5 で W1 完全成功 |
| 2026-05-27 | F-gemini-quality-tier-poc | sample mode (1 video + 1 article、completed) | 最終布陣 v2 配線後の CP-2 試運転。retries=0 / fallback 0 |

## 4. Hydrangea コンセプト防衛機構の現状 (5 層 + 公開前検証)

> ★ 1-S は防衛機構ロジック (F-1〜F-13) 不変。公開前検証 (guard + Guardian 2 層) が第一作の実成果物で
> 初めてフル稼働し、編集欠陥 (帰属エラー / coverage 過大主張 / title silence) を公開前に捕捉した。

| 層 | バッチ | 場所 | 役割 | 状態 |
|---|---|---|---|---|
| F-1 | F-1 / F-1.5 / F-f1-locale-key-fix | EditorialMissionFilter | 編集ミッション適合度で score 算出 (>= 45.0 で通過) | ✅ 稼働中 |
| F-2 | F-2 / F-5 | FlagshipGate / EliteJudge | 海外発の重要ニュースを優先 | ✅ 稼働中 |
| F-13.B | … / F-jp-coverage-cache-judgement-persist | JpCoverageVerifier | JP 報道カバレッジを WL + LLM judgement で検証 | ✅ 稼働中 |
| F-5 | F-5 | FlagshipGate 下流救済 | 上流ガード通過候補の最終整合 | ✅ 稼働中 |
| F-13 (隠れ層) | F-13 / F-doc-cleanup | script_writer.py quality_floor_miss bypass | analysis_result 成立時の [抑制] 上書き | ✅ 稼働中 (新ルートが正常パス、bypass は legacy fallback 時の安全網) |
| 公開前検証 | 1-Q.5 / 1-T.1 / 1-T.2 | coverage_claim_guard + editorial_guardian (2 層) | 生成後の事実整合 + 忠実性 + 真実性 (flag のみ、公開判断はカズヤ) | ✅ **第一作で実効を実証** (手動ランナー 3 本、production 配線は F-guardian-production-wire ★中) |

## 5. 触ってよい / 触ってはいけない領域マップ

### 触ってよい領域
- `manual_poc/` 配下全般 (★ 1-S 新設 = 第一作隔離領域。生成ハーネス / editorial brief / tts_to_captions / `remotion/` 独立 npm プロジェクト。production 経路から import されない)
- `data/output/golden_master/` (★ 1-S 新設、gitignored。**original は凍結 = 手で書き換えない**、編集は `*_edited.*`。規約は `docs/golden_master_spec.md`)
- `configs/prompts/` 配下全般 (主戦場: `configs/prompts/analysis/geo_lens/`。★ 1-S では**変更なし** = brief はハーネスのプロセス内注入で production プロンプト不変)
- `configs/` 直下の YAML 構造データ (`coverage_claim_policy.yaml` 等)
- `src/generation/` への **新規ファイル追加** (★ 1-Q.5 `coverage_claim_guard.py` / 1-T.1 `editorial_guardian.py` / 1-T.2 `editorial_guardian_corroboration.py` / **1-S `image_prompt_writer.py`** = 決定論 5 プレートビルダー、LLM 非関与)
- `docs/` 配下全般 (★ `docs/ADR/` の ADR 新規作成・部分更新注記可。★ 1-S で `golden_master_spec.md` 新設 + ADR-0001/0002 に部分更新注記)
- `tests/` 配下に新規テストファイル追加 (既存ファイルは原則変更しない。★ 1-S で `test_image_prompt_writer.py` + `test_tts_to_captions.py` 新規、既存テスト 0 行変更)
- `scripts/` 配下に新規スクリプト追加
- `src/triage/` に新規ファイル追加
- `src/storage/db.py` (不変原則対象外 = storage 層。後方互換必須)
- `src/generation/script_writer.py` の **新ルート** (`generate_script_with_analysis` / `ScriptWithAnalysisDraft` 等)
- `src/generation/video_payload_writer.py` (不変原則 1-4 対象外。★ 1-S で L72 仮想敵 1 行除去 = F-video-payload-visual-prompt-target-enemy 完了。target_enemy は L457-458 で条件付き露出 = 新ルート None なら非露出)
- `src/shared/models.py` (後方互換必須)
- `src/main.py` (不変原則対象外)
- `src/llm/factory.py` / `src/shared/config.py` の Gemini モデル ID default (最終布陣 v2 + GUARDIAN role + GUARDIAN_GROUNDING_MODEL 配線済)
- `src/analysis/` (★ 新規ファイルは例外条件 5 点充足時のみ = X1 前例。★ 1-S では**不変** = 観点候補注入はハーネス側 monkeypatch で実現、analysis_engine.py / perspective_extractor.py 0 行)
- `.env` / `.env.example` (★ gitignored / secrets 表示ガード = CLAUDE.md §4 遵守。★ 1-S では変更なし = ELEVENLABS_API_KEY は手動 PoC でカズヤが追加予定)

### 触ってはいけない領域
- `src/generation/article_writer.py` (不変原則 1。★ 1-S で「brief 注入不可 → article は素のまま生成」の制約として実地に効いた = c10/c13 coverage 過大は人間編集で直す)
- `src/generation/script_writer.py` の **既存ルート** (`write_script` / `_PROMPT_TEMPLATE` / `_build_script_from_llm`) (不変原則 2) ★ legacy fallback 経路 (budget 枯渇 / no_client / llm_error) は旧ルートに落ち target_enemy 復活する構造的限界が残る (1-S ハーネスは fallback 検出で fail-fast し凍結を拒否する設計で対処)
- `src/triage/` の既存ファイル (不変原則 3、例外条件 5 点全充足 + カズヤ承認時のみ)
- `src/analysis/` 配下の **既存ファイル** (不変原則 4、新規追加も原則禁止・例外条件 5 点)
- 既存テスト (不変原則 5、baseline **1581 passed** 維持 — フィクスチャ API contract 整合化 / 新規テストクラス追加 / 構造変更なしの期待値修正は許容)
- **`data/output/golden_master/` の original ファイル** (★ 1-S 新設の凍結対象 = 不変原則 6 第一作隔離の一部。編集は `*_edited.*` へ)

## 6. 不変原則 5 つ + 第一作隔離 (リマインダ、正本: BATCH_PROTOCOL.md / golden_master_spec.md)

1. **`src/generation/article_writer.py` 一切変更不可**
2. **`src/generation/script_writer.py` の既存ルート (`write_script` / `_PROMPT_TEMPLATE` / `_build_script_from_llm`) は変更不可**
3. **`src/triage/` の既存ファイル変更不可**。新規追加は OK。例外条件 5 点 (過去 3 回適用)
4. **`src/analysis/` の既存ファイル変更不可。新規ファイル追加も原則禁止** (例外条件 5 点、X1 で 1 回適用)
5. **既存テスト破壊しない** (baseline **1581 passed**)
6. ★ **第一作隔離 (1-S 新設)**: 第一作固有の事情で production 経路の振る舞いを変えない。候補A 固有の操作は `manual_poc/` のハーネス内プロセスローカル注入に限定し、`generation_metadata.json` に全記録。`manual_poc/remotion/` は独立 npm プロジェクトで本体依存を汚染しない。golden master original は凍結 (正本: `docs/golden_master_spec.md` §1-2)

## 7. カズヤの直近フィードバック要点

- **「ワークフロー部品は自動で完成させてから手動 PoC」+「手動なのは動画組立と公開判断のみ」**
  (★ F-first-work-golden-master / 2026-06-11) — 第一作はハーネスで golden master を自動出力し、
  人間工程 (編集 / TTS / 画像比較 / レンダ調整 / axis_5 / 公開判断) だけを残す。道具 (Remotion
  テンプレ / 字幕変換 / 再検証ループ) も全部先に揃える。
- **「original 凍結 + 編集は別ファイル」= 編集差分が教師信号** (★ 1-S) — AI 文体の生成プロンプト
  改修は第一作の編集差分を観測してから (DISCUSSION_NOTES 2026-06-08 方針の実装)。本バッチは
  観測の器 (凍結 + `*_edited.*` 規約) まで。
- **「文字はコードで描く、絵は AI で描く」+「正典は意味記述、特定モデルの方言ではない」** (★ 1-S
  設計正典) — 日本語タイポ品質のモデル依存を構造排除 + 画像 3 候補比較は同文投入で公平に。
  AI 動画クリップは第一作不使用 (特定動画モデル結合 = 確定的負債)。
- **「沈黙的劣化の禁止」の生成版 = モデル pin** (★ 1-S 実装判断) — golden master の凍結条件は
  「確定布陣由来」。503 波で下位モデルに silent 劣化するくらいなら fail して再実行 (全 Tier pin)。
  検証層 (1-T) と同じ哲学を生成層にも適用した。
- **「検索と判定の分離」+「公開可否バー = supported × corroborated のみ非 flag」**
  (★ F-editorial-guardian-corroboration / 2026-06-10) — ★ 1-S validation で第一作の実成果物に
  フル適用され、帰属エラー (c5) / coverage 過大 (c10/c13) を公開前に捕捉。flag のみ、公開判断はカズヤ。
- **「検証の2層モデル (忠実性 / 真実性)」+「unverified ≠ 虚偽」** (★ 1-T.1/1-T.2) — ★ 1-S で
  「brief 由来の記述は第1層で flag され、第2層 + 人間判断で解消する」関係を実測・spec に明文化。
  analysis 由来の固有名詞主張 (c6 日本郵船/伊藤忠) は corroborated になるまで公開に乗せない。
- **「各論コントロール (誤り9) ではなく事実整合検証」+「flag のみ」** (★ 1-Q.5) — 1-S の editorial
  brief も「言い回しルール」ではなく「人間検証済みの事実関係 + 編集方針」の構造データとして注入
  (語の選択は LLM に委ねる)。
- **「起案前 grep で起案者前提を検証・訂正する権限 (CP-1)」** (★ クラウド誤り 10 作法) — ★ 1-S で
  重大乖離 2 件 (analysis.json 非存在 / 観点候補構造的 0 件) を実測で発見・訂正。ルールベース部分の
  実データドライランが有効だった。
- **「記事は最上級の知能で考えてほしい」** (★ F-article-model-upgrade) — 1-S は article=3.5-flash
  pin で生成。3.1 Pro エスカレは axis_5 評価後 (F-article-3.1-pro-escalation ★低)。
- **「外部レビュー / 事前情報も grep + コード精読で検証してから起案」** (クラウド誤り 10) /
  **「整合の説明であって検証ではない」** — 外部 AI も一次ソース (公式 docs / repo grep / 実測) で
  裏取り (1-S では ElevenLabs API / Remotion skills を公式ソースで確認)。
- **「1 バッチで欲張らない」+「設計判断と実装の分離」** — 1-S は golden master + 道具立てまで。
  AI 文体改修 / title_generator 根本修正 / 画像 API 配線 / 自動投稿はしない。
- **「対症療法じゃなく根本治療」/「動くものを壊さない」/「機械判定は事実の代替ではない」** —
  候補A perspective_gap は人間確定が正 (1-S では機械抽出も一致し訂正不要だった)。
- **「Hydrangea のメディアとしてのリスクは嘘をつくこと」** — ★ 1-S validation が article の coverage
  過大主張を独立ソースの明示矛盾で捕捉 = ミッションの防衛機構が第一作で機能した実証。
- **「負の遺産残さないように」/「カズヤの手作業はバッチプロンプトのコピペ 1 回のみ」/「過剰拡張性の罠」**

## 8. 関連ドキュメントへの導線

- 過去の決定の経緯 → `docs/DECISION_LOG.md`
- 残課題リスト → `docs/FUTURE_WORK.md`
- 議論中の未確定メモ → `docs/DISCUSSION_NOTES.md`
- バッチ運用ルール → `docs/BATCH_PROTOCOL.md`
- アーキテクチャ全体像 → `docs/ARCHITECTURE.md`
- 技術的負債リスト → `docs/TECH_DEBT.md`
- 編集ミッションフィルタ設計 (F-13 隠れ層含む) → `docs/EDITORIAL_MISSION_FILTER_DESIGN.md`
- ★ 「特定角度」概念正典 → `docs/PARTICULAR_ANGLE_DEFINITION.md`
- Claude Code 振る舞い指針 → `CLAUDE.md`
- ★★ **第一作 golden master 運用規約 (正本)** → `docs/golden_master_spec.md`
- ★★ **F-first-work-golden-master (1-S) 成果物** → `docs/runs/F-first-work-golden-master/`
  (`flag_summary_for_human_audit.md` = カズヤ監査の入口 / `golden_master/` = 凍結スナップショット /
  guard 2 run + Guardian 第1層 + corroboration 3 run) + `data/output/golden_master/` (original 凍結) +
  `manual_poc/` (ハーネス / brief / tts_to_captions / `remotion/`) + `src/generation/image_prompt_writer.py` +
  `tests/test_image_prompt_writer.py` / `tests/test_tts_to_captions.py`
- ★ **F-editorial-guardian-corroboration (1-T.2)** → `docs/runs/F-editorial-guardian-corroboration/` +
  `src/generation/editorial_guardian_corroboration.py` + `scripts/run_editorial_guardian_corroboration.py`
- ★ **F-editorial-guardian-claim-extraction (1-T.1)** → `docs/runs/F-editorial-guardian-claim-extraction/` +
  `src/generation/editorial_guardian.py` + `scripts/run_editorial_guardian.py`
- ★ **F-title-guard-coverage-claim-policy (1-Q.5)** → `docs/runs/F-title-guard-coverage-claim-policy/` +
  `configs/coverage_claim_policy.yaml` + `src/generation/coverage_claim_guard.py` + `scripts/run_coverage_claim_guard.py`
- ★ F-article-model-upgrade A/B 証跡 → `docs/runs/F-article-model-upgrade/`
- ★ X1 = F-particular-angle-metadata-production-wire → `docs/runs/F-particular-angle-metadata-production-wire/`
- ★ **Phase A.5-3b 画像戦略 / Remotion / モラル ADR** → `docs/ADR/0001-image-strategy.md` +
  `0002-remotion-mvp-scope.md` + `0003-content-moral-guidelines.md` (★ 0001/0002 は 2026-06-11 部分更新注記あり)

---

*このドキュメントは F-state-protocol (2026-05-01) で導入。Claude Code が
バッチ完了時に全置換更新する運用 (BATCH_PROTOCOL.md Task 5)。
F-first-work-golden-master (2026-06-11) は **ゲート完了後の 27 つ目のバッチ (1-S)**、**実装バッチ**。
Phase A.5-3b 第一作起案 = **候補A golden master 素材一式の自動出力完成 + 手動動画 PoC の道具立て**。
生成 (brief script 注入 + モデル pin + fallback fail-fast) → validation (2 ガード 3 ランナー、title
silence flag / c5 帰属エラー / c10/c13 coverage 過大の明示矛盾 / c6 corroborated 回収 / run 間分散を
ガード文脈でも実測) → image_prompt レイヤー (決定論 5 プレート) → Remotion (3 帯紙面 + フックカード +
Ken Burns + フレーズ同期 + ducking、ダミー MP4 実証) → spec 正典化、まで完了。CP-1 で重大乖離 2 件
訂正 (誤り 10 作法)。punchline 尻切れ標本 2 例目。baseline 1557 → **1581 passed** (+24、破壊ゼロ)。
不変原則 1-5 + 第一作隔離 (6) 厳守。**現在 = 手動 PoC フェーズ** (カズヤ工程、golden_master_spec §4)。
次バッチは PoC 結果待ち、並走候補 = F-script-punchline-tail-cut-investigate ★中 等。
過去の経緯は DECISION_LOG.md / FUTURE_WORK.md / DISCUSSION_NOTES.md を参照。*
