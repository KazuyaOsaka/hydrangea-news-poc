# F-article-model-upgrade — REPORT

**日付**: 2026-06-08
**種別**: config 変更バッチ (選択肢C 第一歩)
**ブランチ**: `feature/F-article-model-upgrade`
**baseline**: 1466 passed (変更前後とも維持、テスト追加/削除なし)

---

## 1. 目的

記事 (article) 生成モデルを `gemini-2.5-flash` → `gemini-3.5-flash` に品質昇格する
(選択肢C の第一歩。3.1 Pro は本バッチ対象外、条件付きで FUTURE_WORK に登録)。

**スコープ方式 (カズヤ確定)**: B案 = config 変更 + 保存済み候補A event での article A/B 再生成評価。
新規 ingestion / full pipeline run は行わない。

**不変原則 1 厳守**: `src/generation/article_writer.py` は一切変更せず、公開 API `write_article()` を呼ぶのみ。

---

## 2. 起案前仮説 5 点の grep 検証結果 (CP-1、クラウド誤り 10 作法)

| # | 仮説 | 検証結果 |
|---|---|---|
| 1 | article model ID は factory `ARTICLE_ROLES` 経由で gemini-2.5-flash を引く | ✅ 確認 + ⚠️ **訂正**: 「変える 1 値」は `GEMINI_ARTICLE_TIER1` だが **3 箇所に協調配置** — `.env` L20 (runtime 正、gitignored)、`.env.example` L19 (committed template)、`factory.py` L343 inline default。実 runtime を変えるには `.env` が必須。`GEMINI_ARTICLE_MODEL` (config.py L92) は business logic 未使用の dead legacy 定数。 |
| 2 ★ | article role は他 role と完全分離 | ✅ **確認**。article は `GEMINI_ARTICLE_TIER1〜4` (専用 env 名)、judge/script/analysis は `GEMINI_MODEL_TIER1〜4`、lightweight は `GEMINI_LIGHTWEIGHT_TIER1〜4` を引く。env 名が完全別 = `GEMINI_ARTICLE_TIER1` 変更は他 role に巻き込まない (alias 共有でなく独立解決)。runtime 実測で confirm (下記)。 |
| 3 | article max_tokens (MAX1) が full article を truncate するか | ⚠️ **訂正 (用語混同)**: 「MAX1」は MAX_ATTEMPTS=1 (リトライ回数) であって max_output_tokens ではない。article client は `generation_config=None` (`_make_tiered_gemini_client`) = **max_output_tokens を一切設定せず**、モデル既定の出力上限をフルに使う。3.5-flash 出力上限 65,536 でも Hydrangea 側 truncate は存在しない = **token tier 変更不要**。 |
| 4 ★ | 世代境界 (共通 client / thinking 系) | ✅ **確認**。(a) article は `get_article_llm_client()` → 共通 `LLMClient.generate(prompt)` 経由 (article_writer L482/L313)、独自 import なし。(b) src/ 全体で thinking_level/thinking_budget/thinking 系は 0 件。article は generation_config=None で temperature も送らず 3.5-flash default temp 1.0 で動作。judge/script/analysis は 1-Q で既に 3.5-flash 本番稼働済。(c) F-gemini-3.5-flash-api-audit は article 分離 (1-Q) 以前の調査だが article は共通 client の API 面を使うため固有リスクなし。(d) A/B で 3.5-flash article 生成を実測 = retries=0、API エラーなし。 |
| 5 | 候補A scored_event が DB に残存 | ✅ **確認**。`recent_event_pool` に `cls-6889e9e1c7ac` の event_snapshot (4693 bytes) + `data/output/cls-6889e9e1c7ac_script.json` 残存。A案 (config-only) フォールバック不要。 |

### runtime 実測 (仮説 2/3 確認)

```
article    : ['gemini-3.5-flash', 'gemini-3.5-flash', 'gemini-3.1-flash-lite', 'gemini-2.5-flash-lite']
judge      : ['gemini-3.5-flash', 'gemini-2.5-flash', 'gemini-3.1-flash-lite', 'gemini-2.5-flash-lite']   ← 不変
analysis   : ['gemini-3.5-flash', 'gemini-2.5-flash', 'gemini-3.1-flash-lite', 'gemini-2.5-flash-lite']   ← 不変
generation : ['gemini-3.5-flash', 'gemini-2.5-flash', 'gemini-3.1-flash-lite', 'gemini-2.5-flash-lite']   ← 不変
merge_batch: ['gemini-3.1-flash-lite', 'gemini-2.5-flash-lite', 'gemini-2.5-flash', 'gemini-2.5-flash-lite'] ← 不変
article client: primary=gemini-3.5-flash / max_attempts=1 / generation_config=None
```

---

## 3. 実装

1. **config 1 論理値変更**: `GEMINI_ARTICLE_TIER1` を gemini-2.5-flash → **gemini-3.5-flash**
   (`.env` / `.env.example` / `factory.py` inline default + now-false コメント/docstring の正確化)。
   - TIER1==TIER2 (両 3.5-flash) は「1 値のみ変更」(カズヤ起案) を厳守した結果で **意図的**
     (503 時に 3.5-flash を 2 回試してから lite へ落ちる)。旧主軸 2.5-flash は chain から除外。
   - article の MAX_ATTEMPTS=1 / generation_config=None は不変。
2. **A/B 再生成**: `scripts/ab_article_model_upgrade.py` (新規) — 候補A の ScoredEvent + VideoScript を
   ロードし `write_article()` を 2 モデルで実行 (role="article" の Tier を os.environ で pin = モデル混入防止)。

---

## 4. A/B 再生成結果 (評価はカズヤ axis_5)

| モデル | 出力 | 文字数 | 生成 | 備考 |
|---|---|---|---|---|
| gemini-2.5-flash | `article_2.5flash.md` | 1887 | ✅ LLM | tier1 で transient 503 → tier2 も 2.5-flash で成功 (pin が機能、混入なし) |
| gemini-3.5-flash | `article_3.5flash.md` | 2066 | ✅ LLM | retries=0、**API エラーなし** (仮説 4d 実証) |

- 両出力とも Facts→Hypothesis→Implications 構造の実記事 (template fallback なし)。
- 入力 (NewsEvent + ScoredEvent + VideoScript) は両モデルで完全同一。差分はモデルのみ。
- ★ **どちらが上かの判定は Claude Code は出さない**。axis_5 主観評価はカズヤが `article_2.5flash.md` と
  `article_3.5flash.md` を並べて行う。3.5-flash 不足なら 3.1 Pro エスカレ (F-article-3.1-pro-escalation ★低)。
- 生成条件の詳細は `ab_eval_metadata.json` を参照。

---

## 5. テスト

- baseline **1466 passed** 維持 (変更前 136s / 変更後 90s)。テスト追加/削除なし。
- ★ 起案前提 (invariant 5「mock 前提なので落ちない」) を **訂正**: 4 件が article=2.5-flash の旧設計
  (primary 値 + quality と distinct) を直接 assert していたため model ID 変更で fail。旧設計を符号化した
  テストで、本バッチの仕様変更に伴う **期待値修正 (構造変更なし)** で対応:
  - `tests/test_factory_role_model_resolution.py`: `_LINEUP_V2_TIERS["article"]` 更新 +
    `test_quality_and_article_primary_differ` → `test_quality_and_article_share_primary_after_upgrade`
    (primary 共有・MAX_ATTEMPTS で分離 を assert)。
  - `tests/test_factory_role_tier_separation.py`: `test_article_role_uses_cost_optimized_primary` →
    `test_article_role_uses_quality_primary`、`test_lightweight_quality_article_have_distinct_tier1` →
    `test_lightweight_quality_article_tier1_lineup` (article==quality primary、lightweight のみ別)。
  - env-override mechanism テスト (`TestArticleScriptClientSeparation`) は default 非依存のため不変。

---

## 6. 不変原則 / auto mode 観察

- **不変原則違反: なし** — article_writer.py 0 行 / script_writer.py 既存ルート不変 / triage 不変 / analysis 不変。
- **auto mode 観察**: 「ブランチで完結 + main へのマージはカズヤ」原則を維持したため、main 直 push / force push は
  **試行していない** (= classifier がブロックすべき対象が発生せず)。feature ブランチ commit はローカルで実施、
  merge コマンドを完了レポートで提示。auto mode の push 挙動を観察したい場合は feature ブランチ push をカズヤ指示で実施可能。

---

## 7. 成果物

- 変更 (config + コメント正確化): `.env` (gitignored) / `.env.example` / `src/llm/factory.py`
- 変更 (テスト期待値、構造変更なし): `tests/test_factory_role_model_resolution.py` / `tests/test_factory_role_tier_separation.py`
- 新規: `scripts/ab_article_model_upgrade.py`
- A/B 証跡: `docs/runs/F-article-model-upgrade/article_2.5flash.md` / `article_3.5flash.md` / `ab_eval_metadata.json` / 本 REPORT
- docs: DECISION_LOG / FUTURE_WORK / DISCUSSION_NOTES / CURRENT_STATE (Task 1-5)
