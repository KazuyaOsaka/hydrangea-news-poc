# F-trial-run-candidate-a-reverify 統合レポート

実行日時: 2026-05-18 20:12-20:40 JST (試運転) / 2026-05-19 (分析・レポート)
main HEAD コミット: `3c964c7` (F-image-prompt-spec マージ後)
試運転コマンド: `python -m src.ingestion.run_ingestion && python -m src.main --mode normalized`
batch_id: `20260518_111201`

---

## 1. バッチ概要

候補A `cls-6889e9e1c7ac` (Israel 9,600人収監・ICRC 監視操作疑惑、TeleSUR 発) の
B-3' 改修後本番完全再現での再判定を目的とした **最終前提確認バッチ**。

「対症療法じゃなく根本治療」+「動くものを壊さない」+「将来に負債を残さない」原則に従い、
`src/` `tests/` `configs/` `scripts/` `CLAUDE.md` 全て 0 行変更、`docs/` + `data/output/`
のみ更新。baseline **1417 passed** 維持。

### ★ CP-1 カズヤ判断 (2026-05-19): 選択肢3 で続行 (Task C/D のみ、Task E/CP-2 スキップ)

CP-1 時点で 2 つの事実が判明:
1. **候補A は拾われなかった** (完全新規 RSS batch のため母集団に不在)
2. **動画化 Slot-1 の台本が fallback テンプレ** (Gemini 503 多発 run、`llm_error:RemoteProtocolError`)

カズヤ判断根拠:
- 候補A に固執する理由なし。本バッチ目的『B-3' 改修後本番再確認』は 3 連続データ
  (5/11 → 5/16 → 5/18) で構造的効果が既に観察済 = **達成済み**
- Slot-1 fallback で axis_5 採点は無意味。Phase A.5-3b 第一作起案バッチで候補A を
  手動 event 固定 + 実台本生成 + axis_5 採点が本来の流れ
- Gemini 503 の頻発は FUTURE_WORK 観察中の F-17 候補「Gemini API 503 安定性対処」の
  着手条件「503 多発確認」に該当

| 項目 | 結果 |
|---|---|
| 試運転実行 | ✅ 成功 (batch_id=20260518_111201, exit 0, 約28分) |
| 候補A 拾われたか | ❌ 不在 (完全新規 RSS batch、機械判定 ≠ 事実、perspective_gap 維持) |
| シナリオ A/B/C | 直接適用不可 (候補A 不在)。ただし B-3' 構造的効果は 3 連続データで再確認 |
| B-3' 構造的効果 | ✅ 3 連続: 3T(5/11) → 1T/2F(5/16) → 0T/3F(5/18)、True 比率単調減少 |
| 防衛機構 5 層 | ✅ 全層正常 (異常なし、即停止条件非該当) |
| Slot-1 台本 | ⚠️ fallback テンプレ (Gemini 503 由来、axis_5 採点対象外) |
| axis_5 採点 | スキップ (CP-1 判断、Phase A.5-3b 第一作起案バッチで実施) |
| baseline テスト | ✅ 1417 passed (`src/ tests/ configs/ scripts/ CLAUDE.md` 0 変更) |

---

## 2. 試運転実行結果

- batch_id: `20260518_111201`、exit 0、20:12:09 - 20:39:56 JST (約28分)
- RSS: 47 raw / 47 normalized、545 articles loaded
- GarbageFilter: 1159 → 545 (静的除外 151 / LLM除外 463)
- clustering: 351 events built
- F-1 EditorialMissionFilter: 351 → **19 通過** (threshold 45.0、prescore max 65.3/mean 22.48)
- EliteJudge Gate3: 10 評価 → 採用 7 / 棄却 3
- GeminiJudge: 1 candidate judged (cls-d6301853cf24 → blind_spot_global, bs=8.0, div=0.0)、publish reserve 保護で early stop
- Slot 選定: 3 件 (Slot-1 動画化 + Slot-2/3 article-only)、Budget run_llm=39/150 (publish_reserve_preserved=True)

### 2.1 選定 3 Slot

| # | Event ID | Title | Source | mission | has_jp | matched | llm_judg | B-3' branch | role |
|---|---|---|---|---|---|---|---|---|---|
| 1 | cls-f47e9ffde77d | Why Sudan disappeared from global headlines | Middle East Eye | 90.0 | False | 0 (tier=None) | no_match | WL なし→False | video (★fallback script) |
| 2 | cls-e29f905eabe0 | Berlin police storm Nakba Day march | Middle East Eye | 79.0 | False | 0 (tier=None) | uncertain | WL なし→False | article-only |
| 3 | cls-1b5226031840 | Israel advances plan to seize Palestinian property | Middle East Eye | 86.0 | False | 0 (tier=None) | no_match | WL なし→False | article-only |

### 2.2 重要所見

#### ★ 候補A 不在 (機械判定 ≠ 事実)

候補A `cls-6889e9e1c7ac` は run_log 全文 grep で 0 ヒット。完全新規 RSS batch
(2026-05-18) のため題材自体が ingestion/clustering に不在 = F-1/F-2 で『落ちた』
のではなく『そもそも母集団に不在』。RSS は時系列フィードであり 1 週間前の TeleSUR
記事が再出現しないのは正常挙動。**候補A の perspective_gap 系統判定は
F-wl-hit-quality-audit (2026-05-14) で WebSearch 独立検証済の事実であり、機械的に
拾われなかったことはこれを覆さない。** 候補A は Phase A.5-3b 第一作題材として
perspective_gap framing で維持。詳細: `candidate_a_analysis.json`。

#### ★★ B-3' 構造的効果が 3 連続試運転で一貫 (本バッチ目的の本質的達成)

本バッチ目的『候補A の B-3' 改修後本番再確認』の本質は、候補A 個別 Slot の再判定
ではなく『B-3' 改修の構造的効果が本番で安定して現れるか』の確認。3 連続試運転で
has_jp_coverage の True 比率が単調減少し、効果が別題材でも一貫:

| run | date | B-3' status | has_jp 分布 | WL マッチ | 安全装置発火 |
|---|---|---|---|---|---|
| post-tune | 5/11 | 未実装 | **3T** / 0F | 3件 (全 bare-domain) | n/a |
| post-llm-extraction | 5/16 | 配線後初 | 1T / **2F** | 2件 (tier_1/tier_2) | **1件** (Slot-3) |
| **本 run** | **5/18** | 改修後2回目 | **0T / 3F** | **0件** | 0件 (WL 0 で発火条件外) |

本 run は WL マッチが 3/3 で 0 件のため、誤陽性 WL マッチが**そもそも 1 件も発生
しなかった** = bare-domain bypass は構造的に発生せず。安全装置 (WL あり+no_match
→False) の本番発火は post-llm-extraction で 1 件実証済のため、本 run の 0 発火は
入力依存であり異常ではない。詳細: `f13b_comparison.json`。

#### ★★★ Slot-1 動画台本が fallback テンプレ (Gemini 503 由来)

動画化 Slot-1 (cls-f47e9ffde77d) の script は LLM 生成失敗の安全網テンプレ:
`used_fallback=true, fallback_reason=llm_error:RemoteProtocolError, retry_count=0`。
中身は boilerplate (hook=「日本と海外でこの出来事の受け止め方が、大きく異なって
います。」/ setup=英語タイトル生文字列+空白 / platform_title=「日本では報道され
ないWhy」で切れ)。背景: 本 run は試運転時刻 2026-05-18T20:12 JST (夜ピーク、推奨
早朝 5-8 時から外れ) で Gemini `tier=1` の **503 UNAVAILABLE が多発** (8回 retry
は retry.py が吸収して成功、台本生成のみ RemoteProtocolError で fallback に退避)。
これは防衛機構の異常ではなく script_writer 設計上の安全網 (exit 0)。axis_5 採点
は実台本でないため無意味 → CP-1 判断で Task E スキップ、Phase A.5-3b 第一作起案
バッチで候補A を対象に実施。

#### ★ judge provenance 観察事項

GeminiJudge は cls-d6301853cf24 (BRICS/Cuba, bs=8.0) を flagship 判定、
FinalSelection ログは `slot-1 corrected by judge: cls-f47e9ffde77d →
cls-d6301853cf24 (judged_flagship:blind_spot_global:score=82.0)` だが、台本生成・
F-13.B・全 output artifact は cls-f47e9ffde77d (Sudan) で確定。flagship クラスの
転写であり event swap ではない (既存パイプライン挙動、本バッチ未改修)。観察事項
として記録のみ。

---

## 3. 防衛機構 5 層挙動分析 (Task C)

詳細: `f13b_comparison.json`

| 層 | 本 run 挙動 | 前バッチ比較 | 状態 |
|---|---|---|---|
| F-1 EditorialMissionFilter | 351 → 19 通過 (th 45.0) | post-llm-extraction 369→20 と同水準 | ✅ 正常 |
| F-2 EliteJudge/FlagshipGate | Gate3 10→採用7/棄却3, GeminiJudge 1→blind_spot_global, CoherenceGate 1 PASSED, Blocked 0 | 同様の通過パターン | ✅ 正常 |
| F-13.B JpCoverageVerifier | 3 invocations 全 False, no_match x2/uncertain x1, 安全装置 0発火 (WL 0件) | 1T/2F → 0T/3F、安全装置 1→0 (WL 0 で発火条件外) | ✅ 正常 (B-3' 配線済) |
| F-5 下流救済 | 0発火 | 1→0 (入力依存) | ✅ 正常 |
| F-13 隠れ層 | 0発火 (quality_floor per_event 空) | 0→0 不変 | ✅ 正常 (設計通り) |

**防衛機構 5 層に異常挙動なし。即停止条件 (5層異常 / baseline 減 / batch 技術失敗)
非該当。** Slot-1 fallback は script_writer 安全網であり防衛機構異常ではない
(Gemini 503 多発 run が背景、F-17 候補昇格の根拠)。

---

## 4. 候補A 試運転結果分析 (Task D)

詳細: `candidate_a_analysis.json`

- **候補A は拾われなかった** = F-1/F-2 で落ちたのではなく ingestion 段階で母集団に不在
- **機械判定は事実の代替ではない**: 候補A の perspective_gap 系統は
  F-wl-hit-quality-audit (2026-05-14) で WebSearch 独立検証済。機械的に拾われ
  なかったことはこの確定事実を一切覆さない
- **Phase A.5-3b 第一作着手判断**: 候補A `cls-6889e9e1c7ac` を perspective_gap
  framing で第一作題材として **維持** (覆さない)。実台本生成 + axis_5 採点は
  Phase A.5-3b 第一作起案バッチで候補A を手動 event 固定して実施

---

## 5. Phase A.5-3b 第一作着手判断

| 観点 | 判定 |
|---|---|
| 候補A を perspective_gap framing で第一作にできるか | ✅ 維持で OK (F-trial-run-post-llm-extraction 2026-05-16 確定を覆す材料なし) |
| B-3' 改修の前提は最終確定したか | ✅ 3 連続試運転で構造的効果一貫、本バッチで最終確定 |
| 防衛機構 5 層は健全か | ✅ 全層正常、即停止条件非該当 |
| 本 run の Slot-1 で第一作 axis_5 を確定できるか | ❌ fallback テンプレのため不可。Phase A.5-3b 第一作起案バッチで候補A 手動固定 + 実台本生成 + axis_5 採点 |

→ **Phase A.5-3b 第一作着手 OK** (候補A perspective_gap framing 維持)。axis_5 採点
のみ第一作起案バッチに移送。

---

## 6. 残課題 / カズヤ確認推奨事項

1. ★ **F-gemini-503-stability-audit (F-17 候補から昇格、緊急度 高)**: 本バッチで
   「503 多発確認」着手条件達成 (Slot-1 fallback 落ち)。`src/llm/factory.py` +
   `retry.py` のリトライ間隔動的調整、サーキットブレーカー、Slot 別 fallback 戦略
   見直し
2. ★ **F-periodic-health-check (新規、緊急度 高)**: production パイプライン全工程の
   定期ヘルスチェック。Phase A.5-3d cron 6 時間おき完全自動投稿の前提、Gemini 503
   / Grounding 0件 / fallback 落ちの早期検知。Phase A.5-3b 着手前 or 並走
3. **Phase A.5-3b 第一作起案** (緊急度 高): 候補A 手動 event 固定 + 実台本生成 +
   axis_5 採点 + perspective_gap framing。本バッチで前提最終確定
4. 想定外結果の有無: ★ Slot-1 fallback (Gemini 503 由来、防衛機構異常ではなく
   script_writer 安全網)。baseline 1417 維持。即停止条件非該当。

---

## 7. BATCH_PROTOCOL Task 1-5 ドッグフーディング適用内容 (Task G)

### Task 1: DECISION_LOG エントリ追加
`docs/DECISION_LOG.md` 末尾に本バッチエントリ追加。併せて前 2 バッチの
「コミット: (push 後追記)」を実ハッシュで追記更新:
F-trial-run-post-llm-extraction → `8dc62da` / F-image-prompt-spec → `3c964c7`。

### Task 2: FUTURE_WORK 更新
- 完了済みに本バッチ移動
- 新規残課題 2 件 (緊急度 高): **F-gemini-503-stability-audit** (F-17 候補から昇格、
  着手条件達成) / **F-periodic-health-check** (新規、Phase A.5-3d 前提)
- Phase A.5-3b 第一作起案に「axis_5 採点を本バッチから移送」を明記

### Task 3: REPORT.md 本セクション (7) で明記

### Task 4: DISCUSSION_NOTES 整理
- 4-A 新規 1 件: 「2026-05-18: B-3' 改修の構造的効果を 3 連続試運転で観察 +
  Gemini 503 再発、F-17 候補昇格」
- 4-B 既存再評価: F-trial-run-post-tune の bare-domain bypass 関連エントリを
  完全 Resolved に更新

### Task 5: CURRENT_STATE 全置換更新
最終更新日 2026-05-19、本バッチ (ゲート完了後 13 つ目) 反映、ロードマップ 1-J
完了化、次バッチ候補刷新 (F-gemini-503-stability-audit / F-periodic-health-check
追加)。

---

## 8. 不変原則遵守確認 + 環境

- `src/` `tests/` `configs/` `scripts/` `CLAUDE.md` 全て **0 行変更**
- baseline **1417 passed** 維持 (Task A 開始時確認)
- requirements.txt 追加: なし / 環境変数追加: なし
- 新規ファイル: `docs/runs/F-trial-run-candidate-a-reverify/` 配下
  (REPORT.md / environment_snapshot.json / run_log.log / trial_run_summary.json /
  f13b_comparison.json / candidate_a_analysis.json)
- 更新ファイル: `docs/CURRENT_STATE.md` (全置換) / `docs/DECISION_LOG.md` /
  `docs/FUTURE_WORK.md` / `docs/DISCUSSION_NOTES.md`
- `data/output/` 配下は本番試運転副産物 (既存運用通り)

---

*このレポートは F-trial-run-candidate-a-reverify (Phase A.5-3a-verify ゲート完了後
13 つ目のバッチ、1-J) が生成。候補A B-3' 改修後本番再確認 = 候補A 不在 + 3 連続
試運転で B-3' 構造的効果一貫を確認し本バッチ目的達成。Slot-1 fallback (Gemini 503
由来) で F-17 候補昇格。axis_5 採点は Phase A.5-3b 第一作起案バッチに移送。
「対症療法じゃなく根本治療」+「動くものを壊さない」原則遵守。*
