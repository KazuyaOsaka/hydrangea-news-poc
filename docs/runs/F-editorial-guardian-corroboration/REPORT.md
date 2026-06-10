# F-editorial-guardian-corroboration (1-T.2) 完了レポート

実施: 2026-06-10 / ブランチ: `feature/F-editorial-guardian-corroboration` / 実装バッチ (ゲート完了後 26 つ目)

## 実装ファイル一覧

- 新規作成:
  - `src/generation/editorial_guardian_corroboration.py` (666 行) — 証拠収集 (GroundingSearchClient) + Guardian 判定 + レポート enrichment + 公開可否バー
  - `configs/prompts/analysis/geo_lens/editorial_guardian_corroboration.md` — corroboration 判定プロンプト (証拠のみで判定 / 世界知識禁止 / 独立性ルール / 迷ったら uncorroborated)
  - `scripts/run_editorial_guardian_corroboration.py` (204 行) — 手動ランナー (入力 = 1-T.1 レポート JSON、exit 2 = judge unavailable)
  - `tests/test_editorial_guardian_corroboration.py` (38 tests) — fake genai client + LLM mock で決定的
  - `docs/runs/F-editorial-guardian-corroboration/` — 本 REPORT + `x1_slot1_guardian_report_enriched.json` (canonical = run 2) + `x1_slot1_guardian_report_enriched_run1_503wave.json` (503 波の監査証跡)
- 変更:
  - `src/generation/editorial_guardian.py` (+63 行, -3 行) — スキーマ正本への additive 追加のみ: truthfulness 語彙 4 定数 + `CorroborationEvidence` + `TruthfulnessSummary` + `ClaimVerification` / `EditorialGuardianReport` への default 付きフィールド (1-T.1 の 32 テスト無破壊)
  - `src/shared/config.py` (+9 行) — `GUARDIAN_GROUNDING_MODEL` (default gemini-2.5-flash)
  - `.env` (gitignored) / `.env.example` (+3 行) — `GUARDIAN_GROUNDING_MODEL` (config.py inline と 3 協調)
  - `CLAUDE.md` (+4 行) — ★ 相乗り: ガードレール §4 secrets 表示ガード
  - docs: `CURRENT_STATE.md` (全置換) / `DECISION_LOG.md` (本エントリ + 1-T.1 placeholder 埋め) / `FUTURE_WORK.md` / `DISCUSSION_NOTES.md`

## テスト結果

- pytest tests/: **1557 passed, 0 failed** (189s)
- 既存テスト影響: **なし** (変更前 baseline 1519 passed 実測 = 160s = 仮説 5 通り、破壊ゼロ。1-T.1 の `test_editorial_guardian.py` 32 件も全通過 = スキーマ additive 拡張の無破壊を確認)
- 新規テスト追加: **38 個** (`tests/test_editorial_guardian_corroboration.py`、実 LLM / 実ネットワークなし。corroborate_report 系テストは実プロンプトファイルを load するため format placeholder の整合も検証済)

## 起案前仮説 5 点の検証結果 (CP-1、誤り 10 作法)

| # | 結果 | 要点 |
|---|---|---|
| 1 ★ grounding 疎通 | **確認** | raw `genai.Client` + `tools=[Tool(google_search=GoogleSearch())]` + gemini-2.5-flash で grounded 検索成功 (X1 c1 verification_query で実呼び出し 1 回、11 chunks、usage_metadata 取得可)。per-call timeout は `_call_with_timeout` 同形 (ThreadPoolExecutor) で再現。写し元 = `jp_coverage_verifier.py` L561-624 / L1104-1185 精読済 |
| 2 ★ redirect URL の罠 | **確認** | F-13.B 知見が現 API 応答でも成立: `chunk.web.domain=None` / 実ドメインは `chunk.web.title` / `chunk.web.uri` は vertexaisearch redirect URL (実測)。ドメイン抽出ヘルパ 4 つ + `_extract_response_text` + `_call_with_timeout` を**同形再実装** (写し元行番号を docstring に記録、不変原則 3 = triage は import しない)。★ probe で元ソース middleeasteye.net 自身が chunk に出現 = 独立性ルール (元ソースドメイン除外) の必要性をこの 1 回で実証 |
| 3 redirect 解決 (非ブロッキング) | **確認** | UA 付き HTTP HEAD で status 200 + 記事実体 URL (`middleeasteye.net/news/israel-seizes-...`) に解決。`CorroborationEvidence.resolved_urls` として記録 (best effort、クエリあたり最大 5 件、timeout 8s、失敗しても止めない) |
| 4 ★ レポート round-trip | **確認** | `EditorialGuardianReport.model_validate_json` → enrich → `model_dump_json` → 再 validate 成立。X1 実レポート = 20 claims、**全 claim に verification_queries 1〜2 件 (計 21 クエリ)**。enrichment は deep copy (入力レポート不変) + schema_version 1→2 |
| 5 baseline | **確認** | **1519 passed** 実測 (main HEAD `a1754b6`、160s) |

## X1 Slot-1 実走 (2 回、対象 = supported 19 / not_in_source 0、c17 = 第1層 contradicted は pending skip)

```
run 1: corroborated=7  unverified=12 pending=1  (gemini-2.5-flash 503 UNAVAILABLE が 13/21 クエリを直撃)
run 2: corroborated=10 unverified=9  pending=1  flagged=10 (再実行ループの実証、503 は 10/21 で継続)
uncorroborated=0 / truthfulness contradicted=0 (両 run。証拠が取れた claim は全て独立支持あり)
grounding_model=gemini-2.5-flash  judge_model=gemini-3.1-pro-preview  source_domains=[middleeasteye.net, aljazeera.com]
```

- ★ **沈黙的劣化の禁止が実地で機能**: transient 503 波の下で、検索が完了しなかった claim を「検証済み」と偽らず `unverified` (検証未完、理由 = `ServerError: 503` をクエリ単位で evidence に記録) として全件 flag した。c3 は 2 クエリ中 1 成功で判定続行 = 複数クエリ集約の効果。
- ★ **再実行ループの実証**: run 2 で 6 claims (c2/c5/c8/c13/c14/c20) を新規回収。一方 run 1 corroborated の c7/c11/c16 が 503 直撃で unverified に反転 = **run 間分散 (F-grounding-determinism-audit) を Guardian 文脈でも実測**。両 run 合算で 19 対象中 **13 claims が少なくとも一方の run で corroborated**、6 claims (c4/c6/c9/c10/c12/c15) は両 run とも 503 で未検証。run 横断マージ / claim 単位キャッシュは「やらないこと」(survey 2.2-3 判断) のスコープ境界として実装せず、両 run JSON を監査証跡として保存。
- ★ **判定品質 (人間監査サンプル)**: c16「死者 3,371 / 負傷 10,129」を独立ソース (sbs.com.au 等) のレバノン保健省発表報道で裏取り。c18 (スモトリッチ「ドローン 1 機につき建物 100 棟」発言) は judge が「一部ソースは 10 棟と報道」という数字不一致を**補足した上で**複数独立ソースの 100 棟支持で corroborated と判定 = 理由 + 根拠ドメイン明示の監査可能性が成立 (この数字ゆらぎは公開前にカズヤの目視確認推奨)。
- ★ **独立性安全網**: 元ソース 2 ドメイン (event_snapshot から導出) は evidence に出現しても corroborating_domains から全件除外。harness override (元ソースのみ / 幻覚引用での corroborated) の発動は 0 件 (judge が独立ソースを正しく引用)。
- **公開可否バー適用結果 (canonical = run 2)**: flagged = 10 (unverified 9 + 第1層 contradicted の c17)。supported × corroborated の 10 claims のみ非 flag。**flag のみ、公開判断はカズヤ。**

### コスト実測 (2 runs 合計)

- grounding (gemini-2.5-flash、usage_metadata 実測): run1 = 7 calls / 17,207 tokens、run2 = 10 calls / 30,073 tokens → **$0.1 未満**
- judge (gemini-3.1-pro-preview、$2/$12 per 1M): 計 17 calls (証拠ありの claim のみ呼出。入力 ~4K tokens/call + 出力 thinking 込推定) → **概算 ~$0.4**
- **合計 ≈ $0.5 / 2 runs** (judge は文字数からの推定。1 run あたり ~$0.2-0.3、第一作 validation run の予算目安)
- 実行時間: run1 ≈ 16 分 / run2 ≈ 27 分 (検索 + 3.1-pro thinking + redirect HEAD 解決の直列実行)

## 自分で判断した内容

- 判断 1: **スキーマの置き場所** — truthfulness 語彙定数 + 新モデル 2 つ + フィールド追加は 1-T.1 の `editorial_guardian.py` (スキーマ正本) に additive 追加し、ロジックは新規モジュールに分離。`_generate_with_retry` / `_parse_llm_response` / `_resolve_model_id` は**同一機能 (Guardian 2 バッチ構成) 内の共有としてimport** (リトライ意味論 = 沈黙的劣化の禁止の重複再実装による divergence リスク回避)。triage のヘルパは同形再実装 (保護領域、写し元行番号記録) — 自前モジュールと保護領域で使い分けた。
- 判断 2: **検索失敗の粒度** — クエリ単位で error を evidence に記録し、全クエリ失敗のみ claim を unverified に (部分成功は判定続行)。grounded 検索に独自リトライは実装しない (F-13.B 同形 = 単発呼び出し、CLAUDE.md「独自リトライを実装しない」と整合。回収は手動ランナー再実行の運用ループ)。
- 判断 3: **deterministic 安全網の範囲** — corroborated の根拠ドメインは「証拠 chunk に実在」かつ「元ソースと階層独立」の両方を要求 (幻覚引用も自己支持も排除)。contradicted には安全網を適用しない (どのみち flag = 人間レビュー行き、B-3' で judge の明示的矛盾のみ)。
- 判断 4: **run1 (503 波) の扱い** — 上書きせず `_run1_503wave.json` として保全し re-run を canonical に。run 間分散 + 沈黙的劣化の禁止 + 再実行ループの監査証跡として docs に残す価値があると判断。
- 判断 5: **元ソースドメインの導出** — 1-T.1 レポートに source domain が無いため、runner が event_snapshot (source_urls + sources_by_locale + sources_jp/en) から導出 + `--source-domains` で加算可能に。snapshot 不在時は warning + 除外なし続行 (レポートの source_domains 欄で監査可能)。
- 判断 6: **truthfulness_verified_at は試行時刻** — 判定失敗 (unverified) でも記録 (いつ検証を試みたかの監査情報)。skip (pending) には記録しない (検証していないため)。
- 判断 7: **GUARDIAN_GROUNDING_MODEL の置き場所** — factory.py の tier list ではなく config.py の単独定数 (JP_COVERAGE_GROUNDING_MODEL 前例と同形)。grounding は LLMClient 抽象 / tier fallback を通らない raw client 直呼びのため role 化しない。

## 不変原則違反 / 触ってはいけないファイルへの変更要望

- **なし** (article_writer.py 0 行 / script_writer.py 既存ルート 0 行 / triage 既存ファイル 0 行 = ヘルパは同形再実装 / analysis 既存ファイル 0 行 / 既存テスト 0 行変更)

## BATCH_PROTOCOL Task 1-5 実施結果

- **Task 1 (DECISION_LOG)**: 「2026-06-10: F-editorial-guardian-corroboration」エントリ追加 (分離アーキテクチャの根拠 / 語彙 / 対象選別 / 公開可否バー / 仮説 5 点 / X1 実走 2 回 + run 間分散実測 / コスト)。★ 1-T.1 エントリの「(push 後追記)」placeholder を埋めた: `b7e9256` (merge `a1754b6`)。
- **Task 2 (FUTURE_WORK)**: 1-T.2 を完了済みに移動 (詳細記録付き)。新規 2 タスク = **F-guardian-production-wire** (★中、Guardian 2 層 production 配線 + Phase A.5-3d 投稿前ゲート統合、第一作後) / **F-guardian-independence-axis** (★低 条件付き、独立性評価軸の拡張要否 = 通信社配信・国家系同源の観測後判断)。冒頭サマリ更新。
- **Task 4 (DISCUSSION_NOTES)**: 4-A 新規 1 件 = 「truthfulness 語彙と公開可否バーの確定」(昇格候補 DECISION_LOG = 実装完了)。4-B 再評価 2 件 = ①1-T.1「検証の2層モデル」エントリの pending 語彙を解決済みに更新 ②「Fable 5 挙動観察」エントリに ⑤ secrets 表示ガード不在 (1-T.1 で .env 全行表示により API キー露出、カズヤ判断でキー継続使用) + 1-T.2 での対策 (CLAUDE.md §4 + 本バッチは値の表示ゼロ) を追記。
- **Task 5 (CURRENT_STATE)**: 全置換更新 — 最終更新ヘッダ / §0 ★時系列 / §1 main HEAD `a1754b6` + baseline 1557 / §2 次バッチ = **1-S (関門ゼロ)** + ロードマップ表 1-T.2 行 + 候補リスト renumber / §3 X1 実走 2 回 / §5 touchable map / §6 baseline / §7 フィードバック要点先頭追加 / §8 導線 / フッタ。`git diff HEAD docs/CURRENT_STATE.md` = 135 insertions / 93 deletions で全置換確認。
- **★ 相乗り**: CLAUDE.md ガードレール §4「secrets の表示ガード」追記 (値をマスクしキー名のみ表示、例: `grep -oE '^[A-Z_]+' .env`。API キー・トークン等の実値を端末出力・レポート・ログに出さない)。

## 次バッチへの引継ぎ事項 (→ 1-S Phase A.5-3b 第一作起案、関門ゼロ)

- **第一作の validation run 手順 (2 段)**: ① `python scripts/run_editorial_guardian.py --cls <cls> --out <report.json>` → 人間が第1層 contradicted を修正 → ② `python scripts/run_editorial_guardian_corroboration.py --report <report.json> --out <enriched.json>`。flagged_claims が非空なら公開前にカズヤレビュー。503 由来の unverified は時間を置いて ② を再実行。
- **503 波と run 間分散の運用知見**: gemini-2.5-flash の transient 503 で unverified が出る日がある。再実行で回収できるが、run 横断マージは未実装 (スコープ境界) = 必要になったら F-guardian-production-wire / F-grounding-determinism-audit で判断。
- **判定の数字ゆらぎ**: c18 のように judge が「一部ソースは別の数字」と補足した corroborated は、reasoning を目視確認するのが安全 (flag はされない)。
- `coverage_claim_guard` と Guardian 2 層は責務直交のため第一作では 3 ランナー並走 (レポート層統合は運用観測後 = DISCUSSION_NOTES 2026-06-10 ②)。

## 環境構築・依存追加

- requirements.txt 追加: **なし** (redirect 解決は標準ライブラリ urllib)
- 環境変数追加: **あり** — `GUARDIAN_GROUNDING_MODEL` (default gemini-2.5-flash、.env / .env.example / config.py inline の 3 協調)
- 課金前提: judge = gemini-3.1-pro-preview (paid-only)。X1 実走 2 回の合計概算 ≈ $0.5。

## Project Knowledge 最新化 reminder

本バッチで docs 正本 (CURRENT_STATE / DECISION_LOG / FUTURE_WORK / DISCUSSION_NOTES) + CLAUDE.md + 新規実装が更新された。新チャット移行前に claude.ai Project Knowledge の手動最新化を推奨 (BATCH_PROTOCOL 運用ルール)。
