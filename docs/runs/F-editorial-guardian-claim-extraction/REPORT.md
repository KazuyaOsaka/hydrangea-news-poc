# F-editorial-guardian-claim-extraction (1-T.1) 完了レポート

実施: 2026-06-10 / ブランチ: `feature/F-editorial-guardian-claim-extraction` / 実装バッチ (ゲート完了後 25 つ目)

## 実装ファイル一覧

- 新規作成:
  - `src/generation/editorial_guardian.py` (約 480 行) — 抽出 + 第1層忠実性 judge + 2層レポート (Pydantic)
  - `configs/prompts/analysis/geo_lens/editorial_guardian_extract.md` — 高リスク主張抽出プロンプト
  - `configs/prompts/analysis/geo_lens/editorial_guardian_faithfulness.md` — 忠実性判定 + 突合クエリ生成プロンプト
  - `scripts/run_editorial_guardian.py` (約 165 行) — 手動ランナー (exit 2 = guardian_unavailable)
  - `tests/test_editorial_guardian.py` (32 tests) — LLM mock で決定的
  - `docs/runs/F-editorial-guardian-claim-extraction/` — 本 REPORT + `x1_slot1_guardian_report.json` (X1 実走レポート例) + `grounding_reuse_survey.md` (仮説 7 偵察)
- 変更:
  - `src/llm/factory.py` (+約 45 行) — GUARDIAN_ROLES + tier/max_attempts 分岐 + `get_guardian_llm_client()` + module docstring 整合
  - `.env` (gitignored) / `.env.example` (+各 7 行) — `GEMINI_GUARDIAN_TIER1=gemini-3.1-pro-preview` + 系統コメント
  - docs: `CURRENT_STATE.md` (全置換) / `DECISION_LOG.md` (本エントリ + placeholder 2 件埋め) / `FUTURE_WORK.md` / `DISCUSSION_NOTES.md`

## テスト結果

- pytest tests/: **1519 passed, 0 failed** (126s)
- 既存テスト影響: **なし** (変更前 baseline 1487 passed 実測 = 仮説 6 通り、破壊ゼロ)
- 新規テスト追加: **32 個** (`tests/test_editorial_guardian.py`、全て LLM mock)

## 起案前仮説 7 点の検証結果 (CP-1、誤り 10 作法)

| # | 結果 | 要点 |
|---|---|---|
| 1 ★ | **確認 + 精密化** | article 生成器 = NewsEvent + ScoredEvent + VideoScript の**全 JSON** (`article_writer.py` L300-310)。script 新ルート = title + summary + AnalysisResult フィールド + 参照 article (`script_writer.py` L1223-1247)。★ 元ソース全文は **ingestion が `event.summary` に raw テキストを埋込** (X1 Slot-1 実測 4,678 字 = MEE 原文。3,371 / 10,129 / 25 人 / スモトリッチ発言が全て入力に実在 = 忠実性検証成立)。★ `recent_event_pool.event_snapshot` は**分析・審判前に保存** (analysis_result=None / judge_result=None 実測) ⇒ 照合素材 = snapshot.event + `{cls}_analysis.json` の合成再構成。再構成不能な wrapper フィールド (judge_result / editorial_mission_*) と「生成物の相互参照は照合素材に含めない」方針を `SourceMaterialScope.notes` に構造的に記録 |
| 2 | **確認** | article.md 本文 + script.json ナレーション (新ルートは sections のみ、intro/outro 空。旧形式互換で非空なら含める) + title_layer 4 フィールド = 抽出入力 3 ブロック |
| 3 ★ | **確認 + 設計確定** | GUARDIAN role 不在 → 新設。★ 沈黙的劣化の禁止の実装方式 = **単一要素 tier list** (`TieredGeminiClient` の文書化済み single-element 挙動 = same-model retry only / fallback なし / 尽きたら RuntimeError)。TIER2〜4 を**作らない**ことで chain を構造から排除。3 協調箇所 (.env / .env.example / factory.py inline) 配置。非 Gemini provider への委譲も None (guardian_unavailable) |
| 4 ★ | **確認 (疎通成功)** | gemini-3.1-pro-preview へ最小 probe 1 回 → 'OK' (prompt 8 / output 1 token)。**課金設定済み**。X1 実走可能と確定 |
| 5 | **確認** | `particular_angle_extractor.py` (抽出→JSON、coercion、DI、retry) + `coverage_claim_guard.py` (judge + Pydantic + ランナー) の慣例を踏襲 |
| 6 | **確認** | baseline **1487 passed** 実測 (87.97s) = 起案前提と一致 |
| 7 ★ | **偵察完了 (コード変更なし)** | `grounding_reuse_survey.md` に出力。流用可 = raw genai.Client + google_search tool パターン / redirect URL 回避のドメイン抽出ヘルパ / B-3' 哲学 / per-call timeout。新設計要 = クエリ生成 (1-T.1 の verification_queries が代替) / WL Tier / キャッシュ。1-T.2 CP 要検証 = (a) 3.1-pro の google_search tool サポート (b) 分散下の複数クエリ集約 (c) redirect URL 記事実体解決 |

## X1 Slot-1 実証 (gemini-3.1-pro-preview 実呼出 2 回)

```
claims=20  supported=19  contradicted=1  not_in_source=0  unverified=0
flagged_claims=["c17"]  guardian_model_used="gemini-3.1-pro-preview"  guardian_unavailable=false
source_material_scope: has_event=true has_analysis=true summary=4,678字 global_view=4,967字
```

★ **flag された c17 は本物の歪曲**: article「ヒズボラがイスラエル北部への攻撃を継続し、イスラエル軍
兵士25人が死亡した」 — 元ソースでは「25 人 = 3 月上旬以降の**レバノン国内**での累計戦死者数」であり、
「北部への攻撃による死者」と読める書き方は**場所・期間帰属の取り違え** (judge の reasoning + source_evidence
引用つき)。X1 で「production 未検証」と指摘された死者数等の高リスク主張のうち、3,371 / 10,129 /
スモトリッチ発言は supported (生成器入力に実在)、「兵士 25 人」だけが実際に歪んでいたことを第1層が捕捉した
= 本ワークフローの実効性を production 成果物で実証。

レポート全文: `x1_slot1_guardian_report.json` (全 20 claim に verification_queries 付き = 1-T.2 の入力)。

## 自分で判断した内容

- 判断 1: 沈黙的劣化の禁止の実装方式 — 起案は「chain 慣例構造は維持してよい」としたが、TIER2〜4 を
  **作らない単一要素 tier list** を採用 (TieredGeminiClient の文書化済み挙動で fallback を構造的に排除。
  「実使用モデルを記録し primary 以外なら未検証扱い」の事後チェック方式より単純で誤り得ない)。
- 判断 2: 忠実性照合の対象から**生成成果物の相互参照を除外** (script 生成器は article を参照するが、
  生成物は自分の保証人になれない。article にしか無い主張が script に出たら not_in_source → 人間レビュー
  行きが安全方向)。`SourceMaterialScope.notes` に明記。
- 判断 3: LLM judge の語彙は 3 値のまま、判定が完了しなかった主張への harness 値 `unverified` を分離導入
  (語彙外 status / verdict 欠落 / judge 失敗時)。flag = supported 以外すべて、ただし unverified は
  contradicted と明確に区別 (バッチプロンプトの flag 意味論を語彙レベルで実装)。
- 判断 4: Guardian の generation_config=None (truncate なし + 3 系 temperature 非送出) = ARTICLE 前例踏襲。
- 判断 5: budget.py 経由化はしない (1-Q.5 guard / extractor とも非経由の前例。手動ランナー専用で
  production 配線は範囲外のため。production 配線判断時に budget 統合を再検討)。
- 判断 6: ランナーの event_snapshot 読みは `ab_article_model_upgrade.py` 前例踏襲 (sqlite3 直クエリ、
  db.py に単発 getter を足さない = 最小スコープ)。snapshot 不在時は analysis のみで続行し scope に欠落を明示。
- 判断 7: 抽出プロンプトは「取りこぼしより過剰抽出を優先」を明示 (ADR-0003 = 検証対象の見落としは
  安全性に直結。誤り 9 とは文脈が違う検証機械の指示であり、生成プロンプトへのルール追加ではない)。

## 不変原則違反 / 触ってはいけないファイルへの変更要望

- **なし** (article_writer.py 0 行 / script_writer.py 既存ルート 0 行 / triage 既存ファイル 0 行 =
  仮説 7 は読むだけ / analysis 既存ファイル 0 行 / 既存テスト 0 行変更)

## BATCH_PROTOCOL Task 1-5 実施結果

- **Task 1 (DECISION_LOG)**: 「2026-06-10: F-editorial-guardian-claim-extraction」エントリ追加
  (2層モデル / flag 意味論の反転 / 沈黙的劣化の禁止 / 仮説 7 点の検証結果 / X1 実走結果)。
  ★ 既存エントリの「(push 後追記)」placeholder 2 件を埋めた: F-article-model-upgrade = `2514191`
  (merge `896da92`) / F-title-guard-coverage-claim-policy = `091cf5e` (merge `1bead80`)。
- **Task 2 (FUTURE_WORK)**: **1-T.2 = F-editorial-guardian-corroboration を ★★高 (第一作前必須、
  次バッチ最有力) で緊急度 高に正式登録** (grounding_reuse_survey.md への参照 + 起案前仮説 3 点付き)。
  「第一作公開前の高リスク事実検証ワークフロー」を 1-T.1 完了として完了済みへ移動。冒頭サマリ更新。
- **Task 4 (DISCUSSION_NOTES)**: 4-A 新規 3 件 = ①「検証の2層モデル + flag 意味論の文脈反転 (1-Q.5
  B-3' との対比)」②「coverage_claim_guard と Editorial Guardian の責務分担と将来統合の観点 (統合する
  ならレポート層が先、判定ロジックは統合しない)」③「Fable 5 (xhigh) 初バッチの挙動観察 (不変原則遵守 /
  頼んでいない改変ゼロ / grep-first が機能)」。4-B 再評価 1 件 = 「3.1 Pro 二役の布陣整理」エントリを
  更新 (1-T.1 で env 名レベルの role 分離が構造的に完了 → 残る観点は RPD 配分とコストのみに縮小)。
- **Task 5 (CURRENT_STATE)**: 全置換更新 — 最終更新ヘッダ / §0 ★時系列 / §1 main HEAD `1bead80` +
  baseline 1519 / §2 次バッチ = 1-T.2 + ロードマップ表 1-T.1 行 / §3 X1 Slot-1 validation run /
  §5 touchable map (editorial_guardian / GUARDIAN role / GEMINI_GUARDIAN_TIER1) / §6 baseline 1519 /
  §7 フィードバック要点先頭追加 / §8 導線 / フッタ。

## 次バッチへの引継ぎ事項 (→ 1-T.2 F-editorial-guardian-corroboration)

- 差し込みスキーマ確定済: `ClaimVerification.truthfulness_status` (現 "pending"、pending 以降の語彙は
  1-T.2 が確定) + `truthfulness_notes` + `verification_queries` (X1 レポートで全 20 claim 分生成済み)。
- 起案前仮説 (1-T.2 CP-1 で検証): (a) gemini-3.1-pro-preview の google_search tool サポート
  (非サポートなら検索実行と corroboration 判定のモデル分離設計)、(b) grounding run 間分散
  (F-grounding-determinism-audit) 下で複数クエリ集約により判定が安定するか、(c) redirect URL の
  記事実体解決可否 (監査可能性)。詳細: `grounding_reuse_survey.md`。
- 設計原則の継承: 沈黙的劣化の禁止 (corroboration 判定は Guardian 単一モデル) + uncorroborated ≠ 虚偽。
- 第一作 (1-S) では `run_coverage_claim_guard.py` と `run_editorial_guardian.py` を並走させる
  (責務直交、レポート層統合は運用観測後に判断 = DISCUSSION_NOTES 2026-06-10 ②)。

## 環境構築・依存追加

- requirements.txt 追加: **なし**
- 環境変数追加: **あり** — `GEMINI_GUARDIAN_TIER1` (default gemini-3.1-pro-preview、.env / .env.example
  設定済み) + `GEMINI_GUARDIAN_MAX_ATTEMPTS` (optional、default 2、env ファイル未記載 = inline default のみ)
- 課金前提: gemini-3.1-pro-preview は paid-only ($2.00/$12.00 per 1M)。疎通確認済み (CP-1 仮説 4)。
  X1 実走 2 呼出の概算コスト < $0.10 (入力 ~25K tokens + 出力 ~8K tokens)。

## Project Knowledge 最新化 reminder

本バッチで docs 正本 (CURRENT_STATE / DECISION_LOG / FUTURE_WORK / DISCUSSION_NOTES) + 新規実装が
追加された。新チャット移行前に claude.ai Project Knowledge の手動最新化を推奨 (BATCH_PROTOCOL 運用ルール)。
