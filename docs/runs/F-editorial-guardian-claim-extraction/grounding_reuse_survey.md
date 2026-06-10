# 仮説7 偵察レポート: F-13.B grounding 機構の 1-T.2 再利用性調査

作成: 2026-06-10 (F-editorial-guardian-claim-extraction / 1-T.1、調査のみ・コード変更なし)
目的: 1-T.2 = **F-editorial-guardian-corroboration** (第2層・真実性検証 = grounding による
複数ソース突合) の起案入力。`src/triage/jp_coverage_verifier.py` (F-13.B) の grounding/web
検証機構を精読し、再利用できる部品・できない部品・設計上の論点を確定する。

★ 本調査で `src/triage/` 配下のコードは一切変更していない (不変原則 3 厳守、読むだけ)。

---

## 1. F-13.B grounding 機構の現状 (実コード精読結果)

### 1.1 クライアント取得

- `JpCoverageVerifier.__init__(gemini_client, db_path, cache_ttl_hours, model)` —
  **raw `google.genai.Client` を直接保持**する (`src/llm/base.py` の LLMClient 抽象では
  ない)。`main.py:3217-3226` で `genai.Client(api_key=GEMINI_API_KEY)` を生成して注入。
- モデルは `JP_COVERAGE_GROUNDING_MODEL` env (default **gemini-2.5-flash**、
  `config.py:221-223`)。Tier フォールバックは**通らない** (単一モデル直呼び)。
- ★ LLMClient 抽象を経由しない理由: `TieredGeminiClient.generate(prompt)` は
  `tools=[google_search]` の config 注入経路を持たないため。**repo 内に「grounding は
  raw client で直呼び」の前例が既に確立している**。

### 1.2 クエリ実行 (2 系統)

| 系統 | メソッド | 特徴 |
|---|---|---|
| 単段 (verify) | `_search_with_grounding(query)` (L561-624) | `tools=[types.Tool(google_search=types.GoogleSearch())]` で 1 回検索。クエリは `_build_search_query` = `f"{title} 日本 報道"` の決定的合成 |
| 二段 (verify_two_stage) | `_search_with_grounding_two_stage(query, date_restrict_days, timeout_seconds)` (L1104-1185) | per-call timeout (`_call_with_timeout` = ThreadPoolExecutor + `future.result(timeout=N)`、default 90s) 付き。dateRestrict は **API 非サポートのためプロンプト埋め込みを撤去済** (under-recall 副作用、F-jp-coverage-tune Step 4) |

### 1.3 結果解釈

- **URL/ドメイン抽出**: `grounding_metadata.grounding_chunks` を走査。
  ★ `chunk.web.uri` は Vertex AI の **redirect URL** を返す仕様のため WL マッチングに
  使わず、`_extract_domain_from_chunk()` (実ドメインは `chunk.web.title` に格納) +
  `_looks_like_domain()` + `_normalize_domain()` で実ドメインを取り出す
  (F-jp-coverage-improve / 2026-05-07 のバグ修正成果)。
- **LLM judgement 抽出**: `_extract_response_text(response)` で応答本文を取り、
  `_parse_llm_judgement` (B-3' 表) で「明示的否定 (no_match) のみ尊重、沈黙 (uncertain)
  を否定と読み替えない」判定を行う (F-jp-coverage-llm-judgement-extraction / 2026-05-16)。
- **キャッシュ**: `jp_coverage_cache` テーブル (event 単位、24h TTL、
  llm_judgement / llm_judgement_text 永続化済 = F-jp-coverage-cache-judgement-persist)。

### 1.4 既知の課題 (1-T.2 に直接効くもの)

- **run 間分散**: Grounding API は同一クエリでも返す chunk 集合が run 間で変動する
  (F-grounding-determinism-audit ★、FUTURE_WORK L515 起案済・未着手)。単発クエリの
  結果を真実性の根拠にすると判定が不安定になる。
- **dateRestrict 非サポート**: 検索期間を API で絞れない。古い記事との突合混線リスク。
- **redirect URL**: 取得 URL から原文を辿る用途 (一次ソース引用の照合) には
  redirect URL の解決が必要 (現状は ドメイン特定まで)。

---

## 2. 1-T.2 (複数ソース突合 = 真実性検証) への再利用性評価

### 2.1 再利用できる部品 (流用推奨)

1. **呼び出しパターン**: raw `genai.Client` + `tools=[types.Tool(google_search=GoogleSearch())]`
   + per-call timeout (`_call_with_timeout` と同形の ThreadPoolExecutor ラッパ)。
2. **ドメイン抽出ヘルパ群**: `_extract_domain_from_chunk` / `_looks_like_domain` /
   `_normalize_domain` のロジック (redirect URL の罠を踏まないため必須)。
   ★ 不変原則 3 のため import 共有 or 同形再実装のどちらにするかは 1-T.2 で判断
   (module-private 関数のため import は慣例違反、ヘルパの共有化は別判断)。
3. **B-3' 判定哲学**: 「LLM の明示的回答のみ尊重、沈黙を否定と読み替えない」は
   corroboration 判定 (corroborated / uncorroborated / contradicted_by_external 等の
   語彙設計) にそのまま適用すべき。1-T.1 の flag 意味論 (unverified = 検証未完 ≠ 虚偽)
   と整合する。

### 2.2 再利用できない / 新設計が必要な部品

1. **クエリ生成**: F-13.B は `f"{title} 日本 報道"` の決定的合成 (JP 報道有無の確認用)。
   1-T.2 は **1-T.1 レポートの `verification_queries`** (claim ごとに 1〜3 件、ja/en
   locale 付き、Guardian が生成済) を入力にする — クエリ生成部は流用不要。
2. **WL Tier マッチング**: JP 大手メディア whitelist は「日本で報道されたか」用。
   真実性突合は**国際ソースの独立性** (party 非依存の複数ソース) が問われるため、
   ドメイン信頼性の評価軸は新設計 (例: 元ソース TeleSUR と独立系の区別)。
3. **キャッシュ**: jp_coverage_cache は event 単位。1-T.2 は claim 単位の検証になる
   ため、キャッシュするなら新テーブル (要否自体を 1-T.2 で判断、第一作は手動運用
   なのでキャッシュなしが最シンプル)。

### 2.3 設計上の論点 (1-T.2 起案で決めるべきこと)

1. **モデル選定 × 沈黙的劣化の禁止**: F-13.B の grounding は gemini-2.5-flash。
   1-T.2 の「検索実行」と「corroboration 判定」を分離するか:
   - 検索 (URL 収集) は軽量モデルでも成立しうるが、**判定** (検索結果と claim の意味
     照合) は Guardian 原則 (単一モデル・劣化禁止) を適用すべき。
   - gemini-3.1-pro-preview が google_search tool をサポートするかは **未検証**
     (本調査はコード精読のみ。1-T.2 の CP で公式 docs + 実呼び出し確認が必要)。
2. **分散対策**: F-grounding-determinism-audit の指摘 (run 間分散) に対し、1-T.2 は
   claim ごとに複数クエリ (1-T.1 が生成済) を実行して集約する設計が自然な緩和策。
   単発クエリ结果での corroborated 断定は避ける。
3. **LLMClient 抽象との関係**: grounding は raw client 直呼びの前例に従う
   (TieredGeminiClient への tools 注入拡張は本筋でない。CLAUDE.md「直接
   google.generativeai を import しない」原則とは要調整 — F-13.B は genai を main.py
   で生成し注入する形で原則と共存している。1-T.2 も**注入パターン**を踏襲するのが安全)。
4. **redirect URL 解決**: 真実性検証で「どの媒体が何と報じたか」を監査可能にするには
   ドメインだけでなく記事実体への到達性が要る。redirect URL の解決可否を 1-T.2 CP で
   実測する。

---

## 3. 結論

- F-13.B の grounding 機構は「呼び出しパターン + ドメイン抽出 + B-3' 判定哲学 +
  per-call timeout」が 1-T.2 にそのまま流用できる成熟部品。
- クエリ生成は 1-T.1 の `verification_queries` が代替済み、WL/キャッシュは流用不可
  (目的が違う)。
- 最大の未知数は (a) gemini-3.1-pro-preview の google_search tool サポート、
  (b) grounding 分散下での corroboration 判定の安定性。両方とも 1-T.2 の CP-1
  (grep + 実呼び出し) で検証すべき起案前仮説として登録する。
