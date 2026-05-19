# F-gemini-model-audit — Gemini モデル戦略再検討 調査レポート

生成日: 2026-05-19
ブランチ: `feature/F-gemini-model-audit`
main HEAD: `4510180`
baseline: **1417 passed** 維持 (調査のみ、`src/ tests/ configs/ scripts/ CLAUDE.md` 0 行変更)

---

## 1. バッチ概要

5/25 deadline での `gemini-3.1-flash-lite-preview` shutdown + 2026-05 Gemini
API モデル群大幅更新を踏まえた **影響調査専用バッチ (改修一切なし)**。
設計判断と実装を分離する原則に従い、本調査結果を前提に次バッチ
`F-gemini-model-migrate-emergency` で実装する。コード変更なし、出力は
`docs/runs/F-gemini-model-audit/` 配下のみ。

---

## 2. 5/25 shutdown 対応の影響範囲サマリー

shutdown 対象 `gemini-3.1-flash-lite-preview` の使用箇所:

| # | 場所 | 役割 | runtime | 区分 |
|---|---|---|---|---|
| 1 | `.env:14` `GEMINI_MODEL_TIER3` | QUALITY Tier3 fallback | ★ 実稼働 | functional |
| 2 | `.env:21` `GEMINI_LIGHTWEIGHT_TIER3` | LIGHTWEIGHT Tier3 fallback | ★ 実稼働 | functional |
| 3 | `src/llm/factory.py:324` `GEMINI_MODEL_TIER3` default | QUALITY Tier3 | env 欠落時のみ | functional default |
| 4 | `src/llm/factory.py:316` `GEMINI_LIGHTWEIGHT_TIER3` default | LIGHTWEIGHT Tier3 | env 欠落時のみ | functional default |
| 5 | `src/shared/config.py:76` `GEMINI_MODEL_TIER1` default | GEMINI_MODEL_TIERS / interval・RPM dict キー / 旧 alias | env 欠落時のみ | functional default |
| 6 | `.env.example:15, :22` | テンプレ (非実行) | なし | テンプレ |
| 7 | `src/main.py:2471` / `src/llm/judge.py:72` / `factory.py` 各コメント / `config.py:142` | コメント・docstring | なし | doc-drift |

**結論**: 実稼働の functional 使用箇所は **2 箇所** (`.env` の QUALITY Tier3 +
LIGHTWEIGHT Tier3)。両系統とも **primary ではなく Tier3 fallback**。
コード default 3 箇所 + テンプレ 2 箇所 + doc-drift 群が付随。
→ `F-gemini-model-migrate-emergency` のスコープ = `.env` / `.env.example` /
`src/llm/factory.py` (defaults) / `src/shared/config.py:76` の
`gemini-3.1-flash-lite-preview` → `gemini-3.1-flash-lite` (GA, 2026-05-07 GA)
置換 + doc-drift コメント整理。**Lightweight 系のみ改修ではなく、Tier3 を
共有する QUALITY 系の env/default も同時置換が必要** (ただし全 LOW リスク、
後述)。

### ★ 重大発見: shutdown 後の非リトライ即 raise リスク

`retry.py` は 404 / NOT_FOUND を **非リトライ** 扱いとし、
`factory.py:250` の `if not is_retryable(exc): raise` で
`TieredGeminiClient.generate()` が **次 Tier にフォールバックせず即例外送出**
する。shutdown 後の `gemini-3.1-flash-lite-preview` 呼び出しは通常 404 を
返すため:

- 503 多発時 (2026-05-19 F-trial-run-candidate-a-reverify で実確認) に
  Tier1→Tier2 が連鎖失敗 → Tier3 (= shutdown モデル) 到達 → 404 即 raise
- **Tier4 (gemini-2.5-flash-lite GA = 最終安全網) に降りられず生成失敗**

= 503 多発時の最後の砦が逆に全生成失敗を誘発する。
5/25 までに必ず `F-gemini-model-migrate-emergency` で解消すること。

---

## 3. 現状 Tier 階層の構造図

```
解決経路: .env → factory._get_tier_models_for_role() (os.getenv 直読、config.py 非経由)

QUALITY_ROLES  {judge, script, article, title, analysis}
  Tier1  gemini-3-flash-preview           [PREVIEW]  primary
  Tier2  gemini-2.5-flash                 [GA]
  Tier3  gemini-3.1-flash-lite-preview    [PREVIEW]  ★5/25 shutdown
  Tier4  gemini-2.5-flash-lite            [GA]       最終安全網

LIGHTWEIGHT_ROLES  {garbage_filter, merge_batch, viral_filter, editorial_mission_filter}
  Tier1  gemini-2.5-flash                 [GA]       primary
  Tier2  gemini-2.5-flash-lite            [GA]
  Tier3  gemini-3.1-flash-lite-preview    [PREVIEW]  ★5/25 shutdown
  Tier4  gemini-3-flash-preview           [PREVIEW]

max_attempts_per_tier = 2 (both)
429/RESOURCE_EXHAUSTED → 即次 Tier  | 503/UNAVAILABLE → 2 回指数バックオフ後次 Tier
404/NOT_FOUND → 非リトライ即 raise (★ 上記重大発見)

named accessor: get_garbage_filter_client()/get_cluster_llm_client()
  → get_llm_client('merge_batch') = LIGHTWEIGHT 経路に集約

F-13.B Grounding: JP_COVERAGE_GROUNDING_MODEL = gemini-2.5-flash [GA] (独立、Tier 非経由)
```

config.py vs factory.py の default 不一致 (runtime 影響なし、env 上書きのため):
config.py:76-79 = `[3.1-flash-lite-preview, 3-flash-preview, 2.5-flash, 2.5-flash-lite]`
factory.py:322-325 (QUALITY) = `[3-flash-preview, 2.5-flash, 3.1-flash-lite-preview, 2.5-flash-lite]`

---

## 4. 各 role の移行リスク評価表

評価軸: 「shutdown 対象 (Tier3 fallback) を `gemini-3.1-flash-lite` (GA) に
置換する挙動変化」。**primary (Narrative 主軸) 選定は本バッチ対象外**
(`F-gemini-quality-tier-poc` 管轄)。

| role | 系統 | shutdown 位置 | リスク | 根拠 |
|---|---|---|---|---|
| garbage_filter | LIGHTWEIGHT | Tier3 | **LOW** | 単純ノイズ分類、preview→GA 同等以上 |
| merge_batch | LIGHTWEIGHT | Tier3 | **LOW** | クラスタ統合判定、決定性タスク |
| viral_filter | LIGHTWEIGHT | Tier3 | **LOW** | 簡易スコアリング |
| editorial_mission_filter | LIGHTWEIGHT | Tier3 | **LOW** | prescore 併用、回帰容易 |
| judge | QUALITY | Tier3 | **MEDIUM** | EditorScore 採点、Tier3 fallback (primary=3-flash-preview)、回帰確認推奨 |
| analysis | QUALITY | Tier3 | **MEDIUM** | ANALYSIS_LAYER_ENABLED=false で本番未起動 = 実害なし、将来 PoC 再評価 |
| title | QUALITY | Tier3 | **MEDIUM** | 第一作品質関与だが短文 + Tier3 fallback |
| script | QUALITY | Tier3 | **HIGH→実質LOW** | script_writer は第一作直結だが shutdown 対象は劣化前提の Tier3 fallback。GA 化は劣化幅縮小方向 |
| article | QUALITY | Tier3 | **HIGH→実質LOW** | 同上。article_writer は不変原則1 だがモデル ID は env/config 解決でコード非改修移行可 |

**総合**: Lightweight 系統 = LOW、Quality 系統 = 名目 MEDIUM/HIGH だが
shutdown 対象が **全系統 Tier3 fallback** のため emergency 移行
(preview→GA) は実質全 LOW。Narrative primary の品質確定は別 PoC。

---

## 5. Interactions API 使用状況

`grep -rn -i "interactions" src/` = **0 件**。**未使用、無関係、対応不要**。
2026-05-26 / 2026-06-08 の Interactions API deadline は Hydrangea に影響なし。
`F-gemini-model-migrate-emergency` スコープ外。

---

## 6. AI Studio active quota 確認チェックリスト (カズヤ手動)

> 本バッチ背景の RPD 値は 2026-05-19 時点 AI Studio 表示の伝聞値。
> migrate 実装前に下記をカズヤが手動確認 (Claude Code は API 叩かない)。

1. [ ] **AI Studio → 左メニュー「Get API key」→ 該当プロジェクト → "Usage & Billing" / "Quotas"** を開く
2. [ ] `gemini-3.1-flash-lite` (GA) の **RPD / RPM** 実値を確認 (期待: RPD 150K 規模)
3. [ ] `gemini-3-flash-preview` の RPD/RPM (期待: RPD 10K)
4. [ ] `gemini-2.5-flash` (GA) の RPD/RPM (期待: RPD 10K、現 QUALITY Tier2 / LIGHTWEIGHT Tier1)
5. [ ] `gemini-2.5-flash-lite` (GA) の RPD/RPM (現 QUALITY Tier4 / LIGHTWEIGHT Tier2、最終安全網)
6. [ ] **Grounding 専用 quota**: 「Grounding with Google Search」項目で Gemini 2.5 系の active quota (期待 RPD 5K) を確認。Gemini 3 系 Grounding (RPD 1.5K) は **使わない方針** なので確認のみ
7. [ ] free tier か有料 (Tier 1 課金) かをページ上部のプラン表記で確認 → RPD 桁が伝聞と乖離する場合 migrate スコープ再検討

---

## 7. preview/GA 状態確認チェックリスト (カズヤ手動)

1. [ ] **AI Studio → 「Create prompt」画面右上のモデルドロップダウン** または
   [https://ai.google.dev/gemini-api/docs/models](https://ai.google.dev/gemini-api/docs/models) の Models 一覧を開く
2. [ ] `gemini-3.1-flash-lite` が **GA (preview サフィックス無し)** で選択可能か
   (= shutdown される `-preview` の正式置換先である確証)
3. [ ] `gemini-3.1-flash-lite-preview` に **deprecation / shutdown 2026-05-25** 表記があるか
4. [ ] `gemini-3-flash-preview` が依然 **-preview** 表記か (GA 昇格していれば model id 変更要)
5. [ ] `gemini-3.1-pro-preview` の preview/GA 状態 (Editorial Guardian 候補、局所使用、別 PoC)
6. [ ] 確認結果を Claude Code に共有 → migrate バッチで **AI Studio で確認した
   正確な model id (preview/GA サフィックス含む) のみ** を使用。Claude Code は
   model id を断定書きしない (`-preview` 付きを既定維持)

---

## 8. 推奨 Tier 階層案 (現時点最有力仮説、PoC で検証)

> 確定ではない。`F-gemini-quality-tier-poc` の品質 PoC + axis_5 採点で確定。
> 下記は本バッチ調査 + 3 AI 三角測量合意点に基づく作業仮説。

### 8-1. emergency 移行 (F-gemini-model-migrate-emergency、5/25 必達)

shutdown 対象 → GA への **最小・低リスク置換のみ**:

```
QUALITY      Tier3: gemini-3.1-flash-lite-preview → gemini-3.1-flash-lite (GA)
LIGHTWEIGHT  Tier3: gemini-3.1-flash-lite-preview → gemini-3.1-flash-lite (GA)
config.py:76 default も同様に GA 化 + factory.py default と整合
+ doc-drift コメント (main.py:2471 / judge.py:72 / factory.py / config.py:142) 整理
+ retry.py 404 非フォールバック問題の扱いを migrate バッチで判断
  (案: shutdown モデルを階層から除去すれば 404 到達自体が消える = 最小対処で足りる)
```

### 8-2. Lightweight 主軸切替仮説 (PoC 不要、emergency と同時 or 直後)

3 AI 合意点: Lightweight 主軸を `gemini-3.1-flash-lite` (RPD 150K = 現
`gemini-2.5-flash` 想定 15 倍) に切替候補。RPD 桁増で 503/429 リスクを
**根本治療**。要 AI Studio quota 実値確認 (セクション 6) 後に確定。

### 8-3. Narrative 主軸 (QUALITY Tier1) — 本バッチ対象外

`gemini-3-flash-preview` (RPD 10K) / `gemini-3.1-pro-preview` (RPD 250) /
`gemini-2.5-flash` (RPD 10K、安定 fallback) を品質 PoC で確定
(`F-gemini-quality-tier-poc`)。Pro は Editorial Guardian (高リスク事実検証
専用、局所使用) に限定、Quality 主軸にしない。

### 8-4. F-13.B Grounding — 変更なし

`gemini-2.5` 系維持 (既存安定性 + 回帰リスク + active quota 確認待ち)。
3 AI 合意点と一致。`JP_COVERAGE_GROUNDING_MODEL=gemini-2.5-flash` のまま。

---

## 9. ★ 残課題 / カズヤ確認推奨事項

1. **AI Studio active quota / preview-GA 状態の手動確認** (セクション 6・7、
   migrate 実装前必須、Claude Code は API を叩かない)
2. **retry.py 404 非フォールバック問題の対処方針**: shutdown モデルを Tier
   から除去すれば 404 到達自体が消滅 = 最小対処で十分か、それとも 404 を
   フォールバック対象に加える設計変更 (不変原則影響、要議論) か。
   → migrate バッチ着手時にカズヤ判断推奨 (本調査は「除去で足りる」を有力視)
3. **config.py / factory.py default 不一致** の整合 (runtime 影響なしだが
   env 欠落時の安全側 default 化、migrate バッチで同時対応推奨)
4. **GEMINI_QUOTA_NOTES.md の陳腐化**: 2026-04-26 時点の Tier 構成
   (TIER1=3.1-flash-lite-preview RPD 500) で記述されており現 .env と乖離。
   2026-05 動向反映の更新が必要 (migrate バッチ or 別 doc バッチ)
5. **`.env.example` の扱い**: repo ルートのテンプレ。本バッチ不変原則では
   configs/ 対象だが `.env.example` は configs/ 配下ではない (ルート直下)。
   migrate バッチで `.env`/`.env.example` 同時更新を明示すること
6. **Lightweight 主軸切替の判断**: quota 実値確認後、emergency と同時に
   Tier1 を `gemini-3.1-flash-lite` 化するか、emergency は Tier3 GA 化のみに
   留め Tier1 切替を別ステップにするか (本調査は「同時で可、ただし quota
   確認が前提」を有力視)

---

## 10. BATCH_PROTOCOL Task 1-5 適用内容

- **Task 1 (DECISION_LOG)**: 本バッチエントリ追加 +
  F-trial-run-candidate-a-reverify の「コミット: (push 後追記)」を実ハッシュ
  `bc0f531` (feat) / `4510180` (merge) に追記更新。
- **Task 2 (FUTURE_WORK)**: 本バッチ完了済み移動 /
  `F-gemini-503-stability-audit` 撤回 (モデル切替で根本治療) /
  `F-periodic-health-check` 緊急度 高→中・検討時期を Phase A.5-3d 着手時に変更 /
  新規 `F-gemini-model-migrate-emergency` (★★★ 高、5/25) +
  `F-gemini-quality-tier-poc` (高、Phase A.5-3b 前) 追加。
- **Task 3**: 本セクション = 完了レポートへの明記。
- **Task 4 (DISCUSSION_NOTES)**: 新規 4-A「2026-05-19: 3 AI 三角測量で
  2026-05 Gemini モデル戦略の方向性を確立」追加 + 既存再評価。
- **Task 5 (CURRENT_STATE)**: 14 つ目バッチ (1-K) として全置換更新、
  次バッチ候補 1st=F-gemini-model-migrate-emergency / 2nd=F-gemini-quality-tier-poc /
  3rd=Phase A.5-3b 第一作起案。

*(本セクションは CP-1 カズヤ判断後に Task F として実施・確定する。)*
