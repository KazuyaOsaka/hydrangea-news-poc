# F-jp-coverage-llm-judgement-extraction — 設計仕様 (design_spec.md)

最終更新: 2026-05-14 (Task B、CP-1 提示前ドラフト)

> **目的**: F-wl-hit-quality-audit Task D で決定的に判明した **LLM judgement
> bypass 問題** の根本治療 = `verify()` (本番稼働、broad-only) + `verify_two_stage()`
> (計測専用、二段階クエリ生成) の **両方** に LLM response_text 判定抽出を実装する。
> 既存メソッド contract を完全維持 + optional フィールド追加のみ + 既存テスト
> 全件破壊しない の三大制約下で、Hydrangea カズヤ哲学『LLM の知性に委ねる』に
> 整合する形で改修する。

---

## B-1: 既存メソッド contract の維持方針

### B-1.a: シグネチャ完全不変

| メソッド | シグネチャ | 維持方針 |
|---|---|---|
| `verify(event_id, title, summary)` | `(self, event_id: str, title: str, summary: str = "") -> JpCoverageResult` | ★ 完全不変 |
| `verify_two_stage(candidate, particular_angle, *, timeout_seconds, date_restrict_days, analysis_llm_client)` | 既存シグネチャ通り | ★ 完全不変 |

### B-1.b: 戻り値型 (dataclass) クラス名完全不変

| クラス | 維持方針 |
|---|---|
| `JpCoverageResult` | ★ クラス名 / 既存フィールド完全不変、optional フィールド追加のみ |
| `TwoStageVerifyResult` | ★ クラス名 / 既存フィールド完全不変、optional フィールド追加のみ |

### B-1.c: 既存フィールド完全不変、optional フィールド追加のみ

`JpCoverageResult` への追加:
```python
@dataclass
class JpCoverageResult:
    # 既存フィールド (完全不変)
    event_id: str
    title: str
    has_jp_coverage: bool
    matched_urls: list[str] = field(default_factory=list)
    matched_domains: list[str] = field(default_factory=list)
    matched_tier: Optional[str] = None
    excluded_urls: list[str] = field(default_factory=list)
    search_query: str = ""
    raw_grounding_response: Optional[str] = None
    error: Optional[str] = None
    cached: bool = False
    cached_at: Optional[str] = None
    # ★ 新規追加 (optional、デフォルト値ありで既存呼び出し側影響なし)
    llm_judgement: Optional[str] = None          # "match" / "no_match" / "uncertain"
    llm_judgement_text: Optional[str] = None     # response_text の該当判定部分 (デバッグ用)
```

`TwoStageVerifyResult` への追加:
```python
@dataclass
class TwoStageVerifyResult:
    # 既存フィールド (完全不変)
    # ... 全て省略 (既存定義参照) ...
    # ★ 新規追加 (broad / angle 各々、optional、デフォルト None)
    broad_llm_judgement: Optional[str] = None
    broad_llm_judgement_text: Optional[str] = None
    angle_llm_judgement: Optional[str] = None
    angle_llm_judgement_text: Optional[str] = None
```

### B-1.d: 呼び出し側影響評価

既存呼び出し箇所 (production-pipeline):
- `src/main.py:3187` (legacy `verify()` のみ呼び出し) → optional フィールド追加で影響なし
- `scripts/measure_two_stage_accuracy.py` (verify_two_stage を呼び出し計測専用) → optional フィールド追加で影響なし

既存テスト箇所:
- `tests/test_jp_coverage_verifier_domain_extract.py` (10 ケース、WL マッチング階層判定 + WL 拡張) → optional フィールドにデフォルト値ありで完全維持
- `tests/test_jp_coverage_verifier_two_stage.py` (16 ケース、verify_two_stage 機能) → 同上完全維持

★ **判定ロジック変更 (B-3) が既存テストを壊さない理由**: 既存テストは全件 LLM response 抽出機構を持たない MagicMock を使用しているため、`llm_judgement = None` (= 抽出不能 → 後方互換) パスで既存挙動を維持できる設計が必須。

---

## B-2: LLM 判定抽出方針

### B-2.a: ハイブリッド方式 (プロンプト改修 + 正規表現/キーワード判定)

#### ステップ 1: プロンプト改修

既存プロンプト (`_search_with_grounding` / `_search_with_grounding_two_stage`) に
**「該当する記事があれば URL を列挙、該当しない場合は『該当する記事はありません』と明示してください」** 指示を追加する。

ただし、F-wl-hit-quality-audit Task D 既存 dump で確認した通り、現プロンプトでも
Gemini は「見つかりませんでした」「異なる内容」「日付も異なります」のような明確な
no_match シグナルを既に返している。新プロンプトは「より明確な明示」を狙う改善で、
パース戦略の堅牢性を上げる。

#### ステップ 2: response_text パース (新規関数 `_parse_llm_judgement`)

`_parse_llm_judgement(response_text: str) -> tuple[str, Optional[str]]`
- 戻り値: `("match" | "no_match" | "uncertain", 判定該当テキスト or None)`
- 曖昧なら "uncertain" に倒す (= クラウド誤り 9 各論コントロール回避、LLM 判定を素直に拾う)

### B-2.b: キーワードリスト (★ Hydrangea「嘘をつかない設計」優先)

**判定アルゴリズム**: パース戦略は「**先に no_match を確定**、次に match、最後に uncertain」の優先順序。これは「**嘘をつかない設計、疑わしきは低く見積もる**」(F-task-e-finalize / カズヤ哲学) の応用 = 報道済み判定 (= silence_gap でない判定) を出すには高いバーを要求する。

| 判定 | キーワード (response_text に含まれていれば該当) |
|---|---|
| **no_match** (= 該当記事なし) | `該当する記事はありません` / `該当する記事は見つかりませんでした` / `見つかりませんでした` / `見つかりません` / `該当しません` / `該当なし` / `異なる内容` / `異なる事象` / `別の事象` / `日付も異なります` / `報道されていません` / `報道は確認できませんでした` / `見当たりません` |
| **match** (= 該当記事あり) | `該当する記事は以下` / `該当する記事は次の` / `以下の URL` / `以下の記事` / `次の記事` / `報道されています` / `報道されました` / `報道済み` / `確認できました` |
| **uncertain** | 上記いずれにも該当しない、または両方含む文 |

### B-2.c: 過剰検出を避ける保守的設計

★ **「該当しない」が含まれてても「ただし類似報道は該当する」のような文脈** に注意。
具体的な実装ガード:

1. **複合文の処理**: response_text を文単位 (`。`区切り) で分割し、各文を個別に評価。複数文で判定が割れた場合は uncertain に倒す
2. **否定句チェック**: 「該当しない」「見つかりませんでした」が `しかし` `ただし` `一方で` `に対し` のような転換接続詞の後ろにある場合は弱める (= 否定の否定 = uncertain)
3. **接続詞の優先順位**: 単独で no_match キーワードが現れたら強く no_match に倒す。match キーワードと混在した場合は uncertain に倒す (= 嘘をつかない設計)

### B-2.d: F-wl-hit-quality-audit Slot-2 既存 dump への適用 (dry-run #1、API コスト 0)

`docs/runs/F-wl-hit-quality-audit/grounding_chunk_raw_dump.json` の `response_text_excerpt` に B-2.b のキーワードリストを適用した dry-run。

response_text (要約):
> 「日本語のWeb検索結果を確認したところ、指定されたニュース [...] が日本の主要メディアで報道されていることを示す記事URLは**見つかりませんでした**。[中略] これらの記事は、ユーザーが確認を求めている [...] とは**異なる内容**で、かつ**日付も異なります**。」

検出されるキーワード:
- 「**見つかりませんでした**」 → no_match ★
- 「**異なる内容**」 → no_match ★
- 「**日付も異なります**」 → no_match ★

判定: **no_match** (3 件の独立シグナル、全て同方向)

判定該当テキスト (llm_judgement_text 候補):
> 「日本の主要メディアで報道されていることを示す記事URLは見つかりませんでした」

★ **既存プロンプトでも明確な no_match 判定が抽出可能**を Slot-2 既存 dump で確認。新プロンプト改修は「より明確化」のための補強で、本質的なパース戦略は既存出力でも機能する。

---

## B-3: WL マッチ × LLM judgement の優先順位

★ B-2.c の「嘘をつかない設計」原則を判定ルールに反映。

| WL マッチ | LLM judgement | 最終 has_jp_coverage | 根拠 |
|---|---|---|---|
| あり | match | **True** (報道済み) | 両方一致 (現状維持) |
| あり | **no_match** | **False (未報道)** ★ | LLM が支配 (本改修の核心) |
| あり | uncertain | **False (未報道)** ★ | 「疑わしきは低く見積もる」(嘘をつかない設計) |
| **あり** | **None** (パース不能 / 後方互換) | **True (報道済み)** ★ | ★ **既存挙動維持** = 既存テストを壊さない (LLM 抽出が機能しない MagicMock テスト群を維持) |
| なし | (LLM 判定不問) | False (未報道) | 現状維持 |

### B-3.a: ★ 既存テスト維持のための後方互換挙動 (重要)

**`llm_judgement = None`** (= response_text 抽出が機能しなかった / MagicMock で response が空) の場合は **WL マッチのみで判定** (= 既存挙動と一致)。

これにより:
- 既存 16 ケース (test_jp_coverage_verifier_two_stage.py) は完全維持
- 既存 35+ ケース (test_jp_coverage_verifier_domain_extract.py) は完全維持
- 新規テストでは `llm_judgement` を明示セットして B-3 表の挙動を検証

### B-3.b: verify_two_stage の系統判定における LLM judgement の扱い

`verify_two_stage` の系統判定 (stream_1_silence_gap / stream_2_perspective_gap / stream_3_candidate) は **broad_jp_coverage / angle_jp_coverage を本ルールで計算した後** の判定で機能する。

| Step 1 (broad_jp_coverage 計算後) | Step 2 (angle_jp_coverage 計算後) | 最終 stream |
|---|---|---|
| broad_jp_coverage = False (WL マッチ なし、または LLM = no_match で支配) | (Step 2 スキップ) | stream_1_silence_gap |
| broad_jp_coverage = True | angle_jp_coverage = False (WL マッチ なし、または LLM = no_match で支配) | stream_2_perspective_gap |
| broad_jp_coverage = True | angle_jp_coverage = True | stream_3_candidate |

★ 重要: LLM judgement bypass の構造的欠陥は broad / angle 両方で同じ機構が動いているため、本ルールは broad / angle の各 `_search_with_grounding*` に同等に適用される。

### B-3.c: Slot-2 cls-1a38c0ca8c99 適用シミュレーション (= 期待される本改修効果)

| 項目 | 現状 (改修前) | 改修後期待 |
|---|---|---|
| WL マッチ | あり (afpbb.com x 2 = tier_2_wire_service) | あり (同じ) |
| LLM judgement | (抽出されず) | **no_match** (B-2.d で確認、独立 3 シグナル) |
| has_jp_coverage | **True** (誤陽性) | **False** ★ (LLM 判定が支配で真陰性に修正) |
| stream (二段階版) | stream_2_perspective_gap (broad が True 扱い、angle で False) | **stream_1_silence_gap** ★ (broad で no_match → Step 2 スキップ) |

---

## B-4: テスト戦略

### B-4.a: 新規テストファイル

`tests/test_jp_coverage_verifier_llm_judgement.py` (新規追加、12-15 件)

#### TestParseLLMJudgement (パース関数の境界条件、6-8 件)
- `test_parse_明示的no_match_keyword`: 「該当する記事はありません」→ no_match
- `test_parse_見つかりませんでした_keyword`: 「見つかりませんでした」→ no_match
- `test_parse_異なる内容_keyword`: 「異なる内容」「日付も異なります」→ no_match
- `test_parse_明示的match_keyword`: 「該当する記事は以下」→ match
- `test_parse_報道されています_keyword`: 「報道されています」→ match
- `test_parse_曖昧文_uncertain`: キーワード不在 / 中立文 → uncertain
- `test_parse_混在文_uncertain`: match + no_match キーワード混在 → uncertain
- `test_parse_転換接続詞_uncertain`: 「該当しないが類似報道は確認」→ uncertain

#### TestVerifyWithLLMJudgement (`verify()` ハイブリッド判定、4 件)
- `test_verify_wl_match_llm_match`: WL あり + match → has_jp_coverage = True
- `test_verify_wl_match_llm_no_match`: WL あり + no_match → has_jp_coverage = **False** ★
- `test_verify_wl_match_llm_uncertain`: WL あり + uncertain → has_jp_coverage = **False** ★
- `test_verify_wl_no_match`: WL なし → has_jp_coverage = False (現状維持)

#### TestVerifyTwoStageWithLLMJudgement (`verify_two_stage` ハイブリッド判定、3 件)
- `test_two_stage_broad_llm_no_match_falls_to_stream_1`: broad で WL あり + LLM no_match → stream_1_silence_gap (Step 2 スキップ)
- `test_two_stage_angle_llm_no_match_falls_to_stream_2`: broad は通過、angle で WL あり + LLM no_match → stream_2_perspective_gap
- `test_two_stage_backward_compat_no_llm_judgement`: response_text 抽出不能 → 既存挙動維持

### B-4.b: 既存テスト 全件維持確認

`python -m pytest tests/ -x --tb=no -q` で **1390 (baseline) + 新規追加分** passed 確認。

特に重要な維持要件:
- `tests/test_jp_coverage_verifier_domain_extract.py` (35+ ケース): WL マッチング / WL 拡張 / 階層判定機能の不変性
- `tests/test_jp_coverage_verifier_two_stage.py` (16 ケース): stream_1/2/3/unknown 判別 / fallback 機能の不変性

★ もし既存テストが破壊された場合は **即停止 + カズヤに報告**、Task C 改修方針を再検討 (バッチプロンプト「想定外結果への対処」セクション)。

### B-4.c: モック戦略

新規テストで Gemini API 戻り値の構造をモック化する仕組みは既存 `_make_grounding_response` パターンを継承 + `response.text` フィールドを追加。

```python
def _make_grounding_response(domains, response_text=""):
    response = MagicMock()
    response.candidates = [MagicMock()]
    response.candidates[0].grounding_metadata = MagicMock()
    response.candidates[0].grounding_metadata.grounding_chunks = [...]
    # ★ 新規追加: response_text (content.parts[0].text) のモック
    response.candidates[0].content = MagicMock()
    part = MagicMock()
    part.text = response_text
    response.candidates[0].content.parts = [part]
    return response
```

既存テストの `_make_grounding_response` は `response_text=""` デフォルトでそのまま使えるため、既存テスト全件で `llm_judgement = None` (= 抽出されず) パスを通り B-3.a の後方互換挙動でカバーされる。

---

## B-5: 不変原則 3 例外条件チェックリスト

| 条件 | 確認内容 | 状況 |
|---|---|---|
| **実装バグ修正** | LLM judgement bypass の設計欠陥修正 (= Gemini LLM が response_text で『該当しない』と明示判定しているのに WL マッチだけで True を返している、F-wl-hit-quality-audit Task D で決定的に判明) | ✅ |
| **設計変更ではない** | 既存メソッド contract 完全維持、optional フィールド追加のみ (B-1) + 既存挙動は `llm_judgement = None` の後方互換パスで保持 (B-3.a) | ✅ |
| **DECISION_LOG 明記** | Task G (BATCH_PROTOCOL Task 1) で DECISION_LOG エントリ追加予定 | (バッチ完了時に充足) |
| **Hydrangea ミッション中核機構 + カズヤ承認済** | 本バッチプロンプトでクラウド (web) 経由カズヤ承認済、F-13.B (JpCoverageVerifier) は Hydrangea コンセプト防衛機構 5 層の中核 | ✅ |

---

## B-6: 新プロンプト草案

### B-6.a: 改修対象プロンプト

| プロンプト関数 | 役割 | 改修内容 |
|---|---|---|
| `_search_with_grounding` (verify 本番用) | broad 検索 | 「該当する記事があれば URL 列挙、なければ明示」指示追加 |
| `_search_with_grounding_two_stage` (verify_two_stage broad / angle 共用) | broad / angle 検索 | 同上 |

### B-6.b: 新プロンプト本文 (草案、★ CP-1 カズヤ承認待ち)

★ 既存プロンプトに **3 行の追加指示** のみで根本治療を達成する保守的設計。
これは「クラウド誤り 9 (各論コントロールへの誘惑)」回避 = ルール累積劣化を避ける配慮。

#### `_search_with_grounding` (verify 本番用)

```
次のニュースが日本のメディアで報道されているか、日本語の Web 検索で確認してください。

検索クエリ: {query}

検索結果から、日本のメディア (新聞、テレビ局、通信社等) の記事 URL を中心に確認してください。

# 回答形式
- 該当する記事が見つかった場合: 該当記事の URL を箇条書きで列挙してください
- 該当する記事が見つからなかった場合: 文中に「該当する記事はありません」と明示してください
- 検索結果に類似トピックの記事はあるが当該事象とは異なる場合: 「該当する記事はありません。類似トピック (○○) は報道されていますが、当該事象自体は報道されていません」と明示してください
```

#### `_search_with_grounding_two_stage` (verify_two_stage broad / angle 共用)

```
次のニュースが日本のメディアで報道されているか、日本語の Web 検索で確認してください。

検索クエリ: {query}

日本のメディア (新聞、テレビ局、通信社等) の記事 URL を中心に確認してください。

# 回答形式
- 該当する記事が見つかった場合: 該当記事の URL を箇条書きで列挙してください
- 該当する記事が見つからなかった場合: 文中に「該当する記事はありません」と明示してください
- 検索結果に類似トピックの記事はあるが当該事象とは異なる場合: 「該当する記事はありません。類似トピック (○○) は報道されていますが、当該事象自体は報道されていません」と明示してください
```

### B-6.c: なぜこの設計が「各論コントロールの誘惑」を回避するか (クラウド誤り 9 再発防止)

本プロンプト改修は以下の理由で「各論コントロールの誘惑」に該当しない:

1. **構造データの明示要求** = LLM の自由度を削るのではなく「LLM が記事内容を読んで自分の判定を **明示的に書き出す** ように促す」だけ。判定基準は LLM に委ねている
2. **既存プロンプトに 3 行追加のみ** = 累積劣化リスクが極小
3. **メタデータ駆動** (B-2 の `llm_judgement` フィールド) = 各論ルール (台本表現等) ではなく LLM 判定の構造化抽出
4. **Hydrangea カズヤ哲学『LLM の知性に委ねる』整合** = LLM の判定能力を信頼し、その判定を機械側が読み取れる形式に変換するだけ

---

## B-7: 実装手順 (Task C のスケッチ、CP-1 承認後着手)

### C-1: dataclass 拡張 (B-1.c)
- `JpCoverageResult` に `llm_judgement` / `llm_judgement_text` フィールド追加
- `TwoStageVerifyResult` に `broad_*` / `angle_*` 各 2 フィールド追加

### C-2: プロンプト改修 (B-6.b)
- `_search_with_grounding` プロンプト書き換え
- `_search_with_grounding_two_stage` プロンプト書き換え

### C-3: response_text パース関数新規追加
- `_parse_llm_judgement(response_text: str) -> tuple[str, Optional[str]]` 新規関数 (B-2.b / B-2.c)
- `_extract_response_text(response: Any) -> str` ヘルパ (response.candidates[0].content.parts[0].text 経由で取り出し、欠損時は "")

### C-4: `_search_with_grounding` / `_search_with_grounding_two_stage` 改修
- 戻り値型を `list[str]` → `tuple[list[str], str]` (urls + response_text) に拡張
- 既存呼び出し側 (verify / verify_two_stage) を tuple アンパック対応に書き換え

### C-5: `verify()` / `verify_two_stage()` 判定ロジック改修
- `_parse_llm_judgement` を呼び `llm_judgement` 取得
- B-3 表に基づき has_jp_coverage / angle_jp_coverage を決定
- 新規フィールドを戻り値に格納

### C-6: モジュール scope の `_search_with_grounding` 内部関数 `_do_call` の戻り値型同期
- `_search_with_grounding_two_stage._do_call()` も同じ tuple 拡張

---

## B-8: テスト維持のためのモック修正リスト (Task D 着手前確認)

### 既存テスト維持戦略

★ 既存テストファイル `tests/test_jp_coverage_verifier_two_stage.py` の `_make_grounding_response` ヘルパは **変更しない** (既存ファイル不変原則)。代わりに、改修後の `_search_with_grounding*` で `response.candidates[0].content` 不在時に空文字列フォールバックする実装にすることで、既存 MagicMock がそのまま機能するよう設計する。

実装ガード (Task C-3):
```python
def _extract_response_text(response) -> str:
    """response.candidates[0].content.parts[*].text を結合。
    属性欠損時は "" にフォールバック (既存 MagicMock 互換性確保)。"""
    try:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return ""
        content = getattr(candidates[0], "content", None)
        if content is None:
            return ""
        parts = getattr(content, "parts", None) or []
        return "".join(getattr(p, "text", "") or "" for p in parts)
    except Exception:
        return ""
```

これにより、既存テストの MagicMock (= content attribute は MagicMock オブジェクトを返すが parts は MagicMock = 反復可能だが text 取得時に "" 扱い) で response_text = "" → llm_judgement = None → 後方互換パス (B-3.a) で既存挙動維持。

### MagicMock 検証ロジック (★ 重要)

MagicMock の `getattr(mock, "content", None)` は **MagicMock オブジェクト** を返すため、`content is None` ではなく `getattr(p, "text", "")` パスで実際の文字列が取れるかをチェックする必要がある。

```python
# parts は MagicMock の場合 反復可能だが要素が MagicMock の場合に "" or "" -> str OK
# part.text は MagicMock 属性 -> str ではない可能性あり -> 後段で空文字フォールバック
```

実装方針: `getattr(p, "text", "")` の結果が **str でない** (= MagicMock オブジェクト) 場合は "" 扱いに正規化:
```python
text = getattr(p, "text", "") or ""
if not isinstance(text, str):
    text = ""
```

これにより MagicMock を素のまま使った既存テストでも問題なく `response_text = ""` → `llm_judgement = None` → 後方互換パスに乗る。

---

## B-9: 想定外結果への対処方針 (バッチプロンプト「想定外結果」セクションの具現化)

| 想定外シナリオ | 検出タイミング | 対処 |
|---|---|---|
| CP-1 dry-run #2 (実 API 再実行) で Slot-2 が no_match 判定にならない | CP-1 提示時 | プロンプト草案再検討、CP-1 でカズヤ議論 |
| 既存テストが破壊される | Task D-2 (baseline 確認時) | **即停止 + カズヤ報告**、Task C 改修方針再検討 |
| ゴールデンセット再測定で Recall covered が 70% 未満に退行 | CP-2 提示時 | 想定外退行、CP-2 で詳細議論 (本番反映保留判断) |
| LLM judgement = uncertain が 50% 以上 | CP-2 提示時 | キーワードリスト見直し要、CP-2 で議論 |
| 退行サンプル分析で「LLM 判定が誤り」が複数件 | CP-2 提示時 | LLM 判定方針の根本再検討要 |

---

*このドキュメントは F-jp-coverage-llm-judgement-extraction Task B (2026-05-14) で生成。
CP-1 で本仕様 + 新プロンプト草案 + dry-run 結果をカズヤに提示し、承認後 Task C 着手する。
バッチプロンプト「想定外結果への対処」+「無制限自走禁止」+「1 バッチで欲張らない」原則遵守。*
