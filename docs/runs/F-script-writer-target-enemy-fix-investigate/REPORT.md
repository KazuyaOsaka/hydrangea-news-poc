# F-script-writer-target-enemy-fix-investigate 完了レポート

**バッチ種別**: 調査専用 (改修なし)
**日付**: 2026-05-26
**ブランチ**: feature/F-script-writer-target-enemy-fix-investigate
**main HEAD**: 4aa6f54 (期待値一致)
**baseline**: 1417 passed 維持 (調査専用のため `src/` `tests/` `configs/` `scripts/` `CLAUDE.md` = 0 行変更 → 自動維持)

---

## 1. バッチ概要

3 AI 三角測量 (Gemini Round 1 / 2026-05-25) で指摘された「`target_enemy` プロンプト/モデル
定義に不整合がある可能性」について、起案前 Project Knowledge grep で得た仮説 1-5 を
**実コードで検証する調査専用バッチ**。クラウド誤り 10 (外部指摘の鵜呑み) の 4 回目発生を
回避するため、本格修正に着手せず CP-1 でカズヤ判断を仰ぐスコープに縮小した。

---

## 2. Task B 調査結果 (grep + コード精読 + 試運転観察)

### B-1: grep 全棚卸し (`grep_inventory.json`)

`target_enemy` 参照は **5 ファイル 20 箇所** (src/configs 11 + tests 9)。配下以外の
ハードコードは無し。ルート別分類:

| 分類 | 箇所 | 不変原則 |
|---|---|---|
| 旧ルート (ScriptDraft / _PROMPT_TEMPLATE / _draft_to_video_script) | script_writer.py:113-118, 317, 417, 445-446, 715, 782 | **不変原則 2 (変更不可)** |
| 新ルート (ScriptWithAnalysisDraft / _analysis_draft_to_video_script) | script_writer.py:1097, 1306 | 変更可 |
| 新ルートプロンプト (仮想敵設定の禁止) | script_with_analysis.md:152-156 | 変更可 (主戦場) |
| shared model (VideoScript) | models.py:221 (`Optional[str] = None`) | 変更可 |
| ルート非依存露出 (条件付き) | video_payload_writer.py:457-458 | 変更可 |
| 契約テスト (新ルート排除を固定) | test_script_writer_with_analysis.py:255,357 / test_e2e_analysis_layer.py:298 | — |

### B-2: 旧ルート vs 新ルート (`route_comparison.json`)

- **旧ルート** (`write_script`): `target_enemy` は `ScriptDraft` の **REQUIRED str フィールド**。
  候補リスト (財務省/日銀・大手メディア・米国政府/中国共産党・GAFAM・既存秩序) を
  `_PROMPT_TEMPLATE` にハードコードし、LLM に仮想敵選択を能動指示。STEP1 + Twist 必達
  チェックリスト経由で **台本本文 framing を仮想敵中心に誘導** (メタデータに留まらない)。
- **新ルート** (`generate_script_with_analysis`): `ScriptWithAnalysisDraft` に target_enemy
  フィールド無し。`_analysis_draft_to_video_script` が `target_enemy=None` 固定 (コメント
  「仮想敵濫用を抑止」)。プロンプトで仮想敵禁止 + 契約テストで固定 = **設計上既に解決済み**。
- **production 配線**: `.env` に `ANALYSIS_LAYER_ENABLED` 行なし → default `false`。かつ
  `analysis_result=None` (analysis layer 未配線) → `main.py:2019` の else 分岐で
  **旧ルート write_script が常時稼働**。新ルートの排除設計は production 未到達。

### B-3: production 試運転観察 (`production_observation.json`)

直近 batch 20260526_035220 (status=completed, used_fallback=false, 旧ルート LLM 生成):
- Slot-1 (cls-0741c099c775): `target_enemy: 米国政府`、director_meta 経由で video_payload に露出。
- ★ viewer-facing leakage 検出: hook「トランプの『合意間近』は、**真っ赤な嘘**です。」/
  punchline「**日本のメディアが報じない**のは…**情報を鵜呑みにする人が損をする**。」
  = 新ルートプロンプトが明示禁止する煽り表現 (script_with_analysis.md L142/149/152-156)。
- 横断観察: 大手メディア 5 件 / 米国政府 2 件 / 既存秩序 1 件 等 = 起案前仮説 5 (2026-05-11
  target_enemy=大手メディア) と同パターンが反復。template fallback 経路のみ null。

### B-4: 真因確定 (`root_cause_analysis.json`)

**真因 a 確定 (confidence: high)**: 旧ルートのハードコード仮想敵リストが原因。だが旧ルートは
不変原則 2 で**直接修正不可**。新ルートは設計上解決済み → target_enemy を production から消す
唯一の sanctioned 経路は**新ルートの production 配線**。

- 真因 b (configs 改修) = REJECTED: 新ルートプロンプトは既に禁止記述十分 + 新ルート未稼働の
  ため production 効果ゼロ。旧ルートプロンプトは Python 定数 = 不変原則 2 で触れない。
- 真因 c (両対応) = REJECTED: 新ルートに問題なし。
- 真因 d (問題不在) = PARTIAL: Gemini の「broken な参照のズレ」前提は厳密には不成立
  (意図的な migration 途上の設計乖離、コードは両ルートで正しく分岐)。だが「台本品質への
  影響」懸念は production で実在 → 「修正不要」とは結論できない。

**スコープ洞察**: target_enemy は「旧ルート全体の仮想敵/煽り framing 哲学」の最も可視な
マーカーに過ぎず、pinpoint 修正でなく旧→新ルート移行が根本治療。新ルートは既に「メタデータ
構造 + LLM の知性に委ねる」設計でこれを達成 (クラウド誤り 9 各論コントロール回避と整合)。

---

## 3. CP-1 カズヤ判断

- **後続バッチ方針 = X1 (新ルート配線バッチに統合)** ✅ 採用
- FUTURE_WORK 既登録「particular_angle_metadata + sontaku_signals の本番配線判断」
  (想定 8-16h) に target_enemy 解消を吸収。新ルート配線で target_enemy は自動的に
  production から消える。
- X2 (configs 改修、production 効果ゼロ) / X3 (両対応、新ルート問題なし) / X4 (修正不要、
  品質懸念実在) は不採用。

---

## 4. 起案前仮説と grep 実態の比較 (クラウド誤り 10 系統の検証)

**★ クラウド誤り 10 の 3 回目発生は無し**。起案前 Project Knowledge 仮説 1-5 は grep +
コード精読 + 試運転で **概ね一致 (CONFIRMED)**。今回は仮説が実態と整合した。軽微な訂正のみ:

| 仮説 | 検証結果 |
|---|---|
| 1: 旧ルートに候補リストがハードコード | CONFIRMED (★ 行番号は「80-88」でなく 113-118/317/445-446 = ドリフトのみ) |
| 2: 新ルートで target_enemy 排除 | CONFIRMED (1097, 1306 + 契約テスト) |
| 3: script_with_analysis.md に仮想敵禁止記述 | CONFIRMED (152-156) |
| 4: production は旧ルートのみ稼働 | CONFIRMED (★ 「fallback」でなく else 分岐の primary route) |
| 5: 2026-05-11 target_enemy=大手メディア 出力 | CONFIRMED (直近 run でも大手メディア 5 件等を観察) |

仮説外の追加発見: `ANALYSIS_LAYER_ENABLED=true` + `analysis_result=None` なら deprecation
gate (main.py:1942) で生成自体が skip される。現 production は false のため旧ルート稼働。

→ F-f1-locale-key-fix / F-jp-coverage-cache-judgement-persist では仮説と実態が乖離したが、
本バッチでは grep-first アプローチで**仮説が検証され整合**。外部指摘も grep で検証してから
起案する作法が機能した好例。

---

## 5. 残課題 (後続バッチへの引き継ぎ)

- **X1: particular_angle_metadata + sontaku_signals の本番配線判断** に target_enemy 解消を
  統合 (FUTURE_WORK、想定 8-16h)。新ルート配線で旧ルートの仮想敵 framing を production から
  退役させる。verify_two_stage 本番配線判断 + F-stream-2-filter-design と密接に関連。
- 旧ルート (`write_script`) は不変原則 2 で保護されたまま残る。新ルート配線完了後は legacy
  fallback として deprecation gate (ANALYSIS_LAYER_ENABLED=true) で退役させる設計が既に存在。

---

## 6. BATCH_PROTOCOL Task 1-5 適用内容 (Task F)

- **Task 1 (DECISION_LOG)**: 本バッチエントリ追加。★ 前バッチ F-jp-coverage-cache-judgement-persist
  の「コミット: (push 後追記)」を実ハッシュ `817ba66` (feat) / `4aa6f54` (merge) で追記更新。
  本バッチは調査専用のため不変原則 1-5 完全遵守 (例外条件適用なし)。
- **Task 2 (FUTURE_WORK)**: F-script-writer-target-enemy-fix の重複 2 エントリを完了済みに移動
  (調査結果サマリ + 真因 a + X1 決定明記)。「particular_angle_metadata + sontaku_signals 本番
  配線判断」エントリに target_enemy 解消の統合を追記。
- **Task 3 (REPORT)**: 本セクション。
- **Task 4 (DISCUSSION_NOTES)**: 4-A 新規「2026-05-26: target_enemy 問題の実態調査 — 真因 a
  確定 + X1 統合」(Resolved/タスク化)。4-B 既存「2026-05-01: 新ルートで target_enemy を排除した
  設計判断」を本調査結果と統合 (昇格候補 → 本バッチで DECISION_LOG に記録済へ更新)。
- **Task 5 (CURRENT_STATE)**: 全置換更新、18 つ目バッチ (1-P)。

---

## 7. 不変原則遵守確認

- `src/` `tests/` `configs/` `scripts/` `CLAUDE.md` = **0 行変更** (調査専用)。
- `docs/runs/F-script-writer-target-enemy-fix-investigate/` 配下に新規ファイルのみ作成 +
  `docs/CURRENT_STATE.md` / `DECISION_LOG.md` / `FUTURE_WORK.md` / `DISCUSSION_NOTES.md` 更新。
- baseline 1417 passed 維持 (改修なしのため自動維持)。不変原則 1-5 完全遵守。

## 8. 出力ファイル一覧

- `REPORT.md` (本ファイル)
- `environment_snapshot.json`
- `grep_inventory.json` (B-1)
- `route_comparison.json` (B-2)
- `production_observation.json` (B-3)
- `root_cause_analysis.json` (B-4)
