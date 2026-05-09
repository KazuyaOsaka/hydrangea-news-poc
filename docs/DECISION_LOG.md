# Hydrangea — 意思決定ログ (DECISION_LOG)

最終更新: 2026-05-09 (F-jp-coverage-tune 完了、verify_two_stage 二段階クエリ
生成実装 + 独立 23 件精度測定 + (c) dateRestrict プロンプト埋め込み除去 1 回
チューニング + verdict=fail 確定で Grounding API 構造的限界が明確化 +
F-jp-coverage-tune-followup を ★最優先として FUTURE_WORK 追加)

このドキュメントは Hydrangea プロジェクトにおける重要な意思決定の履歴を記録する。
コードや設定の「結果」ではなく、「なぜそうなったか」の判断プロセスを残すことが目的。

## 読み方

- 各バッチは時系列順に並ぶ
- 各エントリは「背景」「議論」「決定」「結果」の4セクション構成
- 「議論」セクションは Gemini/ChatGPT/Claude.ai/カズヤ間の論点を要約
- 「結果」セクションには事後的な評価・後続バッチへの影響を記載
- 各エントリの末尾に関連ファイル・コミットハッシュを記載

## 関連ドキュメント

- `docs/EDITORIAL_MISSION_FILTER_DESIGN.md` — F-1/F-1.5/F-2 の実装詳細
- `docs/ANALYSIS_LAYER_DESIGN_v1.1.md` — F-3/F-4 の分析レイヤー詳細
- `docs/FUTURE_WORK.md` — 将来対応リスト
- `docs/REFACTORING_PLAN.md` — 全体改修計画
- `docs/TECH_DEBT.md` — 技術的負債一覧
- `docs/ARCHITECTURE.md` — 現状アーキテクチャ
- `roadmap.md` — フェーズ別ロードマップ

---

## Phase 1.5 概要

### 期間

2026-04-27 〜 2026-04-28 (実質 1.5 日、深夜含む)

### 背景

Phase 1 完成 (B-4 main マージ済み、2026-04-26 `e8f5b61`) 後の実 LLM 試運転で以下が発覚:
- Gemini 無料枠 RPD 超過、503 エラー多発
- ViralFilter のスコアリング設計が Hydrangea コンセプトと矛盾
- 動画生成ゼロ問題 (publishability_class ベースの判定で flagship 認定されない)
- AnalysisLayer の Slot-2/3 で `analysis_result` が None になる
- 媒体数 25 では多視点対比が困難

### 実施バッチ一覧

| バッチ | 内容 | main マージ |
|---|---|---|
| E-2 | Tier 階層統一 (TIER1〜4) | ✅ |
| E-1 | ハイブリッド garbage_filter (静的+LLM) | ✅ |
| FW-0 | FUTURE_WORK.md 導入 | ✅ |
| F-1 | ViralFilter → EditorialMissionFilter 抜本改修 (7軸採点) | ✅ |
| FW-1 | 月次レビュートリガー追加 | ✅ |
| F-1.5 | EditorialMissionFilter ゲート機能不全修正 | ✅ |
| F-2 | FlagshipGate Hydrangea コンセプト整合 | ✅ |
| F-3 | AnalysisLayer フォールバック強化 (Slot-2/3 対応) | ✅ |
| F-4 | AnalysisLayer Top-N 全 Slot 拡張 | ✅ |
| E-3' | Tier 役割別分離 (LIGHTWEIGHT/QUALITY) | ✅ |
| F-5 | publishability_class ベース flagship fallback (動画化ゼロ問題解消) | ✅ |
| F-8-PRE | RSS 媒体候補検証 (22媒体中11 OK) | ✅ |
| F-8-PRE-2 | 失敗5媒体救済検証 (5/5 RESCUED via Google News) | ✅ |
| F-8-1-A | Direct RSS 12媒体追加 + 3層表示名 + Tier3警告 | ✅ |
| F-8-1-B | Google News 5媒体追加 + display_name_speech 配線 (Phase A.5-1 完了) | ✅ |

### 試運転履歴

| 試運転 | 日時 | 結果 | 主な発見 |
|---|---|---|---|
| 試運転1〜3 | 〜2026-04-27 | Phase 1 動作確認 | 503エラー多発、無料枠 RPD 超過 |
| 試運転4 | 2026-04-27 19:34 | F-1 直前 | ViralFilter で Hydrangea 該当記事が大量棄却 → F-1 必要と判明 |
| 試運転5 | 2026-04-27 夜 | F-1 後 | 動画生成ゼロ → F-1.5 / F-2 必要と判明 |
| 試運転6 | 2026-04-28 早朝 | F-2 後 | **動画生成成功** (北朝鮮ロシア軍事同盟、ReHacQ 級品質)。ただし Slot-2/3 で analysis_result=None |
| 試運転7-A/B/C | 2026-04-28 昼 | F-3/F-4/E-3' 系 | 試運転7-C で動画化ゼロ再発 (publishability_class=investigate_more) → F-5 必要と判明 |
| 試運転7-D | 2026-04-28 夕方 | F-5 後 | **大成功** (プーチン盟友のヨット記事、品質「東洋経済オンライン超え」評価) |
| 試運転7-E (準備中) | 2026-04-28 夜 | F-8-1-B 後 | 41/42 媒体取得成功 + display_name_speech 反映確認 |

### Phase 1.5 で達成したこと

1. **コンセプト整合性の確立**: 「日本で報じられない海外ニュース」を全層 (Filter/Gate/FinalSelection) で一貫させた
2. **動画化体制の完成**: 試運転7-D で ReHacQ 級品質の動画を自動生成可能に
3. **多言語化基盤**: 媒体数 25 → 41、3層表示名、Tier3 警告システム導入
4. **LLM 効率化**: Tier 階層を役割別に分離、garbage_filter ハイブリッド化
5. **観点深化**: AnalysisLayer 完成、学術論文レベルの多角的分析を実現

---

## 2026-04-27: E-2 — Tier 階層統一 (lightweight 経路廃止)

### 背景

Phase 1 完成後の実 LLM 試運転 (2026-04-27) で、Gemini 無料枠の RPD (Requests Per Day) 超過が頻発。
特に lightweight 用に分けていた `gemini-2.5-flash-lite` が RPD=20 を瞬時に使い切る一方、
TIER1 で使っている `gemini-3.1-flash-lite-preview` は RPD=500 に余裕があるという非対称な状況だった。

### 議論

- **案A (lightweight 経路維持)**: 既存の lightweight client を残し、別キーで RPD を分散
- **案B (統一階層)**: 全 LLM 呼び出しを単一の TIER1→TIER4 階層に統合し、quota も統一管理

別キー方式は鍵管理コストが高く、quota の見える化が難しい。統一階層なら 503 / 429 時のフォールバックも単純になる。

### 決定

案B (統一階層) を採用。

- `src/llm/factory.py`: `_make_lightweight_client` を削除し `_make_tiered_gemini_client` に統合
- `_make_client` から `quality` flag を撤廃、全 Gemini ロールが統一階層を共有
- `get_garbage_filter_client` / `get_cluster_llm_client` は role 名による named accessor として維持 (E-1 までの後方互換)
- `src/shared/config.py`: `GEMINI_LIGHTWEIGHT_MODEL` 定数削除

### 結果

503 / 429 発生時のフォールバック挙動が予測可能に。後続の E-3' で「同じ階層を全ロール共有する」設計の限界が露呈し、役割別分離に進化することになる (= 段階的進化の起点)。

### 関連ファイル・コミット

- コミット: `06e2712` (2026-04-27)
- 変更: `src/llm/factory.py`, `src/shared/config.py`

---

## 2026-04-27: E-1 — ハイブリッド garbage_filter (静的ルール + LLM)

### 背景

Hydrangea は多言語プロジェクト (geo_lens / japan_athletes / k_pulse) として設計されており、
Gate 1 ガベージフィルタは韓国語・アラビア語・キリル文字・タイ語等の記事も処理する必要がある。

旧設計は LLM-only で動作はしていたが、明らかなゴミ (5文字以下のタイトル、広告/星占いカテゴリ) にもトークンを浪費していた。
途中で「完全静的ルール化」も試みられたが、情報密度チェックが JP/EN regex に依存しており、正当な多言語記事が誤除外される問題が判明。

### 議論

- **完全静的化案**: 速い・安い、しかし多言語非対応で Hydrangea のミッションと矛盾
- **完全 LLM 化案**: 多言語対応できるがトークン浪費が大きい
- **ハイブリッド案 (採用)**: 言語非依存の静的ルールで明らかなゴミを足切り、判定困難なものだけ LLM へ

### 決定

2段構成のハイブリッドフィルタを採用:

- Stage 1 (言語非依存の静的ルール):
  - title length < 5 文字
  - title + summary < 30 文字
  - blocked categories (advertisement / horoscope / promotion / sponsored 等)
  - published_at が 48h より古い
- Stage 2 (LLM): Stage 1 通過分のみ既存のバッチ判定を実行
- `llm_client=None` で Stage 2 をスキップ (テスト・API キー無し環境の後方互換)

### 結果

LLM 呼び出し回数が大幅削減、品質維持。多言語対応が確保され geo_lens 以外の将来チャンネルへ拡張可能に。
ただし `event_builder.py` の `if garbage_filter_client is not None:` ガードは残ったため、API キー未設定時に静的ルールが走らない問題は FUTURE_WORK 「event_builder.py のガード変更」として登録 (緊急度 高)。

### 関連ファイル・コミット

- コミット: `1a32914` (2026-04-27)
- 変更: `src/triage/garbage_filter.py`, 関連テスト

---

## 2026-04-27: FW-0 — FUTURE_WORK.md 導入

### 背景

Phase 1.5 開始時点で、各バッチ実装中に「今は対応せず将来やるべき」と判断する項目が散逸し始めていた。
口頭やコミットメッセージに散らばると再現性が低下し、3ヶ月後に検索しても出てこない。

### 議論

- 案A: 各 PR / コミットメッセージに「将来対応」セクションを書く → 検索性が低い
- 案B: 専用ドキュメントを設ける (採用)
- 緊急度を「高/中/低」の3段階で運用するか、「P0/P1/P2」にするか → 日本語「高/中/低」が直感的で採用

### 決定

- `docs/FUTURE_WORK.md` を新設、緊急度3段階 + 完了済みセクション構成
- CLAUDE.md にメンテナンスルールを明文化 (各バッチ完了時に新規追加 / 完了済み移動を必須化)
- 新規項目は「タイトル / 背景 / 対応案 / 検討時期 / 関連ファイル」フォーマット

### 結果

引継ぎ事項が一元管理され、次バッチでの取捨選択が容易に。
形骸化リスクへの対策は FW-1 で月次レビュー機構として補強される。

### 関連ファイル・コミット

- コミット: `4ece725` (2026-04-27)
- 変更: `docs/FUTURE_WORK.md` (新規), `CLAUDE.md`

---

## 2026-04-27: F-1 — ViralFilter → EditorialMissionFilter 抜本改修

### 背景

実 LLM 試運転 (2026-04-27 19:34) で、Hydrangea が扱うべき記事が ViralFilter で大量棄却され動画生成ゼロという事態が発生。
原因は ViralFilter のスコアリング設計:

- `japan_impact` (0-40点) — 日本への直接インパクトに 40% 配点
- 結果: 日銀利上げ・国内決算が高得点 / ガザ・ウクライナ・米中対立・中央アジア再編が threshold 40 を下回る

つまり Hydrangea が「届けるべき記事」を「日本市場性が低い」という理由で却下していた。
これは Hydrangea のミッション「日本で報じられないニュース、視点が偏ったニュースを背景解説付きで届ける」と真逆。

### 議論

- **緩和案**: japan_impact の配点を 40 → 20 に下げる → ViralFilter の前提 (バズ最適化) 自体が Hydrangea と合わないため対症療法
- **抜本改修案 (採用)**: 「Hydrangea 編集ミッション適合度」を測る7軸スコアリングに作り変え、ファイル名・関数名・環境変数まで `editorial_mission` 系に統一

### 決定

7軸 × 100点満点の `EditorialMissionFilter` を新設:

| 軸 | 配点 | 評価する観点 |
|---|---|---|
| `perspective_gap` | 25 | 日本 vs 海外の報道フレーム差 |
| `geopolitical_significance` | 20 | 国際秩序・大国関係への影響 |
| `blindspot_severity` | 15 | 日本で報じられない度合い |
| `political_intent` | 10 | 政治的・組織的意図の解説余地 |
| `hidden_power_dynamics` | 10 | 表に出ない権力構造の解説余地 |
| `economic_interests` | 10 | 経済的得失・受益者構造の解説余地 |
| `discussion_potential` | 10 | 常識を揺さぶる議論誘発力 |

- Step1 prescore (既存 `editorial:*` axis から計算) で Top-20 に絞り込み
- Step2 LLM (Gemini Tier 階層) で 7軸を再評価
- 閾値 `MISSION_SCORE_THRESHOLD = 45.0` (暫定値、運用後再調整)
- `EDITORIAL_MISSION_FILTER_ENABLED=false` で完全スキップ (後方互換)
- 旧 `viral_filter.py` (367 行) を削除、新 `editorial_mission_filter.py` (480 行) に置換

### 結果

コンセプト整合性が確立。ただし試運転4でゲート機能不全 (rejected 候補が Elite Judge に流れる) 発覚 → F-1.5 必要に。
また `political_intent` / `hidden_power_dynamics` / `economic_interests` の Step1 計算は近接 axis での粗い近似に留まり、scoring.py 触禁解除後の精緻化が FUTURE_WORK 登録された。

### 関連ファイル・コミット

- コミット: `564bff1` (2026-04-27)
- 新規: `src/triage/editorial_mission_filter.py`, `tests/test_editorial_mission_filter.py`, `docs/EDITORIAL_MISSION_FILTER_DESIGN.md`
- 削除: `src/triage/viral_filter.py`, `tests/test_viral_filter.py`
- 変更: `src/main.py`, `src/budget.py`, `src/shared/config.py`, `src/shared/models.py`

---

## 2026-04-27: FW-1 — 月次レビュートリガー追加

### 背景

FW-0 で FUTURE_WORK.md を導入したものの、形骸化リスク (緊急度 高項目が放置される、完了済みに移動されない等) への対策がなかった。

### 議論

- 案A: 各バッチ完了時のみ更新 → 緊急度 高で 1ヶ月放置されても気付かない
- 案B: 定期トリガー (月初) + イベントトリガー (新 Phase 開始前等) の併用 (採用)

### 決定

- `docs/FUTURE_WORK.md` 自身に「FUTURE_WORK.md 月次レビュー」項目を登録 (自己参照型管理)
- CLAUDE.md にレビュータイミング (毎月1日 + 主要バッチ完了直後 + カズヤが「次何やる？」と問うた時等) を明記
- レビュー時の確認項目 (緊急度 高で1ヶ月以上放置はないか、緊急度更新が必要な項目はあるか等) を5点列挙

### 結果

「忘れる」リスクの構造的低減。レビュー自体が項目化されているため、レビューを忘れたこと自体がレビュー対象になる。

### 関連ファイル・コミット

- コミット: `07b4199` (2026-04-27)
- 変更: `docs/FUTURE_WORK.md`, `CLAUDE.md`

---

## 2026-04-27: F-1.5 — EditorialMissionFilter ゲート機能不全修正

### 背景

F-1 投入後の試運転 (2026-04-27 夜) で、`why_rejected_before_generation` がセットされた候補 (= EditorialMissionFilter で却下されたはずの記事) が Elite Judge の入力に流れていることが発覚。

### 議論

`apply_editorial_mission_filter()` は `why_rejected_before_generation` をセットするのみで `all_ranked` リストから除外しない設計だった。
これは旧 ViralFilter からの継承で、`latest_candidate_report.md` の「Rejected Before Generation」セクションが rejected 候補のメタデータを引き続き参照できるようにする意図。

→ フィルタ責務を変更するのではなく、**下流 (Elite Judge) 側で除外する責務を負わせる** のが既存パターンと整合。

### 決定

- `src/main.py` の Elite Judge 入力で `why_rejected_before_generation` を持つ候補を除外する処理を追加
- `apply_editorial_mission_filter()` の挙動 (rejected を残す) は変更しない (レポート互換)
- 新規テストで「rejected 候補が Elite Judge に渡らないこと」を保証

### 結果

ゲート機能正常化。F-2 へ進める前提条件が揃う。

### 関連ファイル・コミット

- コミット: `3a7d27d` (2026-04-27)
- 変更: `src/main.py`, `tests/test_editorial_mission_filter.py`, `docs/EDITORIAL_MISSION_FILTER_DESIGN.md`

---

## 2026-04-27: F-2 — FlagshipGate Hydrangea コンセプト整合

### 背景

F-1.5 試運転で、EditorialMissionFilter を通過した候補 (北朝鮮ロシア軍事同盟、中東情勢等) が
`src/triage/scheduler.py::_passes_flagship_gate()` で「weak_japan」として弾かれる問題が発覚。

旧 FlagshipGate は ViralFilter 時代の設計で、`japan_relevance_score` / `indirect_japan_impact_score` が低い候補を「日本で再生されない」として弾く仕様。Hydrangea のコンセプトと正面から矛盾していた。

### 議論

- 案A: FlagshipGate を削除 → 後方互換破壊が大きい (jp_only 系の運用に影響)
- 案B: EditorialMissionFilter を通過した候補は旧基準を**免除**するルートを追加 (採用)

### 決定

`_passes_flagship_gate()` に以下を追加:

```python
if se.editorial_mission_score is not None and se.editorial_mission_score >= 45.0:
    return True, f"flagship_editorial_mission:score=..."
```

- `FLAGSHIP_EDITORIAL_MISSION` 定数を追加 (documentation 用)
- 既存の `get_flagship_class()` ロジックは後方互換のため維持

### 結果

試運転6 (2026-04-28 早朝) で**初の動画生成成功**。北朝鮮ロシア軍事同盟記事を ReHacQ レベル品質で生成。
ただし Slot-2 / Slot-3 の `analysis_result=None` 問題が浮上 → F-3 へ。

### 関連ファイル・コミット

- コミット: `dd2ca85` (2026-04-27)
- 変更: `src/triage/scheduler.py`, `docs/EDITORIAL_MISSION_FILTER_DESIGN.md`

---

## 2026-04-28: F-3 — AnalysisLayer フォールバック強化 (PerspectiveSelector 3 段階化)

### 背景

試運転6で Slot-2 / Slot-3 の `analysis_result` が None になり動画化失敗:

```
[Slot-2] Iran offers deal to US to reopen Strait of Hormuz...
event_id=cls-b574fcfd8cb3: analysis_result is None, skipping script generation. ★

[Slot-3] Russian superyacht crosses blockaded Strait of Hormuz
event_id=cls-74974ee82dbd: analysis_result is None, skipping script generation. ★
```

真因: `select_perspective()` で LLM が Top3 外の axis (典型的には `hidden_stakes`) を選び、かつ `fallback_axis_if_failed` も Top3 にない場合、None を返す設計だった。

### 議論

- 案A: プロンプトで Top3 内 axis を強制 → LLM の出力安定性に依存、運用で実害が出る
- 案B: 多段フォールバック (採用) → LLM が Top3 外を選んでも実装側で救済、堅牢

### 決定

`select_perspective()` を 3 段階フォールバックに強化:

| Step | 条件 | 採用候補 |
|---|---|---|
| Step 1a | LLM `selected_axis` が Top3 + `actually_holds=True` | selected_axis 候補 (既存) |
| Step 1b | Step1a 不成立 + `fallback_axis_if_failed` が Top3 | fallback_axis_if_failed 候補 (既存) |
| Step 2 ★NEW | Step1a/1b 不成立 | **Top3 内の最高スコア候補** |
| Step 3 ★NEW | candidates が空 | None (最終安全網) |

- LLM 例外失敗時も Step 2 にフォールバック (quota / transient 失敗の救済)
- `framing_divergence_bonus` は Step 2 採用候補にも従来通り後加算
- 各段階の発動を WARNING ログで可視化

### 結果

candidates が 1 件以上あれば必ず `PerspectiveCandidate` を返すため、Slot-2/3 で `analysis_result=None` となる経路を排除。
ただし試運転7-A で別の問題が判明: そもそも main.py で Slot-1 にしか AnalysisLayer が走っていなかった → F-4 へ。

### 関連ファイル・コミット

- コミット: `8d53be5` (2026-04-28)
- 変更: `src/analysis/perspective_selector.py`, `tests/test_perspective_selector.py`, `tests/test_analysis_engine.py`

---

## 2026-04-28: F-4 — AnalysisLayer 実行範囲を Top-N 全 Slot に拡張

### 背景

F-3 後の試運転7-A で別の問題発覚:

```
試運転7-A:
- Slot-1 (Australia green energy): analysis_result is None → skip
- Slot-2 (Iran ホルムズ): analysis_result 存在 → 動画化成功 ✅
- Slot-3 (Russian superyacht): analysis_result is None → skip
```

真因: `src/main.py` の AnalysisLayer ブロックが Recency Guard 後の `all_ranked[0]` (slot-1) に対してのみ `run_analysis_layer()` を呼び、`override_top.analysis_result` にセットしていた。
Slot-2 / Slot-3 の `analysis_result` は None のまま、台本生成ループで skip されていた。

これは「1日5本 (最低3本) の継続生成」体制の最大ブロッカーだった。

### 議論

- Slot 間の独立性をどう確保するか → 各 Slot ループ内に try/except、1 Slot 失敗は他 Slot に影響させない
- LLM コスト増 (1 Slot あたり 5〜8 回追加、N=3 で 15〜24 回増) → `TOP_N_GENERATION` 環境変数で制御可能に

### 決定

| 項目 | 旧 | 新 (F-4) |
|---|---|---|
| AnalysisLayer 実行範囲 | Slot-1 のみ | Top-N 全 Slot (default N=3) |
| 制御変数 | なし (固定) | `TOP_N_GENERATION` 環境変数 |
| 1 Slot 失敗時 | 全体 fallback | 当該 Slot のみ skip、他は続行 |

- Recency Guard は全候補に一括適用後 `all_ranked[:N]` を抽出 (重複適用回避)
- `override_top` (= slot-1 確定) は既存挙動維持
- AnalysisLayer 全体の import エラー等は既存の最外側 try/except で legacy ルートにフォールバック (現状維持)

### 結果

Top-N 候補すべてで `analysis_result` 生成可能に。`TOP_N_GENERATION=1` で F-3 以前の挙動に戻せる。
継続生成体制が技術的に完成。

### 関連ファイル・コミット

- コミット: `671d6bb` (2026-04-28)
- 変更: `src/main.py`, `tests/test_main_analysis_layer_top_n.py`, `docs/EDITORIAL_MISSION_FILTER_DESIGN.md`, `.env.example`

---

## 2026-04-28: E-3' — Tier 階層の役割別分離 (LIGHTWEIGHT / QUALITY)

### 背景

試運転7-A / 7-B (2026-04-28) で以下が判明:

1. 試運転時間が長すぎる (13分): 503 待機が大半 (8回発生、合計 5〜10分)
2. すべてのタスクが同じ TIER1 (Preview) を使う: 軽量タスクも性能タスクも同じモデル
3. モデル性能順が逆転: 公式情報では `gemini-2.5-flash` > `gemini-3.1-flash-lite-preview` なのに TIER 順序が違っていた

### 議論

E-2 で「統一階層」にした直後だが、実運用で「速度優先 vs 性能優先」のトレードオフが顕在化。
カズヤが「速度と性能を両立させたい」と要望、Lightweight/Quality の役割別分離に進化。
モデル順序は公式情報に基づき正規化 (Preview を盲目的に最上位にしない)。

### 決定

役割を 2 系統に分離:

| 系統 | 対象 role | 性能 | 速度 |
|---|---|---|---|
| LIGHTWEIGHT | garbage_filter, merge_batch, viral_filter, editorial_mission_filter | 中 | 速 |
| QUALITY | judge, script, article, title, analysis | 高 | 中 |

- Lightweight 系統 (GA 主軸 / 503 回避): `gemini-2.5-flash` → `2.5-flash-lite` → `3.1-flash-lite-preview` → `3-flash-preview`
- Quality 系統 (Preview 主軸 / 性能優先): `gemini-3-flash-preview` → `2.5-flash` → `3.1-flash-lite-preview` → `2.5-flash-lite`
- 全 Tier で MAX_ATTEMPTS=2 統一 (失敗率 ~0.002%、月 1 件未満)
- `TieredGeminiClient` に `max_attempts_per_tier` 引数を追加、未指定時は既定値 3 (テスト後方互換)

### 結果

- 試運転時間: 13分 → 5〜6分 (平均、503 待機削減)
- 503 発生 (Lightweight): 7回/試運転 → 0回 (GA 主軸のため)
- 月コスト: $15/月 (1チャンネル) / $45/月 (3チャンネル)

ただし試運転7-C で動画化ゼロが再発 → F-5 必要に。

### 関連ファイル・コミット

- コミット: `5a76b80` (2026-04-28)
- 変更: `src/llm/factory.py`, `.env.example`, `tests/test_factory_role_tier_separation.py` (新規)

---

## 2026-04-28: F-5 — publishability_class ベース flagship fallback (動画化ゼロ問題解消)

### 背景

試運転7-C (2026-04-28) で動画化ゼロが再発。GeminiJudge は3件評価したが:

```
cls-3165c4e2: class=investigate_more, blind_spot=7.0, ijai=9.0  ★
cls-651b292a: class=insufficient_evidence, blind_spot=0.0, ijai=4.0
cls-13ef2b35: class=investigate_more, blind_spot=0.0, ijai=1.0
```

`cls-3165c4e2` は「日本では報じられてない (blind_spot=7.0)、日本にとって重要 (ijai=9.0)」を強く示しているが、`publishability_class=investigate_more` のため reject された。

F-2 で FlagshipGate を緩和したが、その**さらに上流**の FinalSelection で publishability_class ベースの判定が貫徹されており、Hydrangea コンセプトとの整合が3層完結していなかった。

### 議論

- 案A: GeminiJudge の publishability_class 判定を変える → judge プロンプト改変は影響範囲が広く危険
- 案B: FinalSelection に F-5 fallback 経路を追加 (採用) → publishability_class 判定はそのまま、下流で Hydrangea 観点で救済

判定の精度ではなく**解釈側の不整合**が真因なので、下流救済が正しい設計。

### 決定

`src/main.py` の FinalSelection に F-5 fallback を追加:

| 判定軸 | 旧 | 新 (F-5) |
|---|---|---|
| 主判定 | `class in {linked_jp_global, blind_spot_global}` | (旧と同じ) |
| F-5 フォールバック | (なし、reject) | `class in {investigate_more, insufficient_evidence}` かつ `blind_spot >= 5.0 OR ijai >= 5.0` かつ `editorial_mission_score >= 45.0` → flagship 認定 |

- `jp_only` / `judge_error` は救済対象外 (Hydrangea コンセプトに合致しないため)
- `editorial_mission_score >= 45.0` を必須条件にすることで低品質救済を防止
- F-5 経路発動を WARNING ログで可視化

### 結果

試運転7-D (2026-04-28 夕方) で**大成功**。プーチン盟友のヨット記事を「東洋経済オンライン超え」品質で動画化。
F-1 (EditorialMissionFilter) → F-2 (FlagshipGate) → F-5 (FinalSelection) の3層で Hydrangea コンセプトが貫徹。
試運転7-D の成功で Phase 1.5 のコア改修は完了。

### 関連ファイル・コミット

- コミット: `85572b8` (2026-04-28)
- 変更: `src/main.py`, `tests/test_main_final_selection_f5_fallback.py` (新規, 220 行), `docs/EDITORIAL_MISSION_FILTER_DESIGN.md`, `docs/FUTURE_WORK.md`

---

## 2026-04-28: F-8-PRE — RSS 媒体候補検証 (22 媒体)

### 背景

Phase A.5-1 の多言語化で、媒体を 25 → 40+ に増やす計画。
事前に各媒体 RSS の取得可能性を検証する必要があった。Gemini が推奨した 22 媒体について、URL を実測する。

### 議論

- 検証スクリプトを汎用化するか F-8 専用にするか → スクリプトは `scripts/verify_rss_candidates.py` として独立、結果を `docs/MEDIA_RSS_CANDIDATES_RESULT.json` に保存
- 失敗時は別 URL を探すか除外するか → まず F-8-PRE で実測、結果次第で F-8-PRE-2 (救済) を計画

### 決定

- `scripts/verify_rss_candidates.py` で 22 媒体の RSS URL を取得検証
- Status: OK / LOW_VOLUME / EMPTY / FAILED の 4 段階
- 結果を `docs/MEDIA_RSS_CANDIDATES.md` (人間可読) と `.json` (機械可読) に分けて保存

### 結果

- OK: 11 媒体 (Sydney_Morning_Herald, Guardian_Australia, The_Hindustan_Times, Middle_East_Eye, The_Initium, Meduza, Il_Sole_24_Ore, The_Atlantic, Politico, TeleSUR, Mada_Masr)
- FAILED: 11 媒体 (Yomiuri, Sankei, Tokyo_Shimbun, WION, Al_Jazeera_Arabic, Caixin_Global, Le_Figaro, Eurasianet, TRT_World, Iran_International, Saudi_Gazette)
- 半数 FAILED の主因: 既知の RSS URL が古くなっている / RSS 廃止 / HTML 返却 → 別経路救済を F-8-PRE-2 で計画

### 関連ファイル・コミット

- コミット: `43c5109` (2026-04-28)
- 新規: `scripts/verify_rss_candidates.py`, `docs/MEDIA_RSS_CANDIDATES.md`, `docs/MEDIA_RSS_CANDIDATES_RESULT.json`, `docs/MEDIA_RSS_CANDIDATES_INPUT.yaml`

---

## 2026-04-28: F-8-PRE-2 — 失敗媒体の Google News RSS 経由救済

### 背景

F-8-PRE で FAILED した 11 媒体のうち、優先度の高い 5 媒体 (Yomiuri, Sankei, Tokyo_Shimbun, WION, Caixin_Global) を Google News RSS proxy 経由で救済できないか検証。

### 議論

- Google News RSS は `?q=when:24h+site:<domain>` 形式で任意ドメインのフィードを生成可能
- メリット: ほぼ確実に取得できる、24h ウィンドウで鮮度確保
- デメリット: タイトル末尾に媒体名が付与される、Google News のサマリ品質に依存 → 受容範囲

### 決定

- `scripts/verify_rss_rescue.py` で 5 媒体の Google News URL を実測
- Status: RESCUED / RESCUED_LOW_VOLUME / EMPTY / STILL_FAILED の 4 段階

### 結果

**5/5 全て RESCUED** (Yomiuri 100, Sankei 100, Tokyo_Shimbun 100, WION 100, Caixin_Global 27 entries)。
Google News 経由が極めて有効と判明。F-8-1-B で本番投入。

### 関連ファイル・コミット

- コミット: `9838206` (2026-04-28)
- 新規: `scripts/verify_rss_rescue.py`, `docs/MEDIA_RSS_RESCUE.md`, `docs/MEDIA_RSS_RESCUE_RESULT.json`, `docs/MEDIA_RSS_CANDIDATES_RESCUE_INPUT.yaml`

---

## 2026-04-28: F-8-1-A — Direct RSS 12 媒体追加 + 3層表示名 + Tier3 警告

### 背景

F-8-PRE で OK 判定した 11 媒体 + Tier3 警告対象 (TeleSUR / Mada_Masr) の本番投入。
合わせて、ナレーション (TTS) と画面表示で表現を変えたいというカズヤの要望から、表示名の3層化を導入。

### 議論

- **3層表示名の必要性**: 「ロイター」と発音させたいが画面字幕は「Reuters」が自然、記事内引用ではフルネームが望ましい
- **Tier3 警告の運用**: TeleSUR (ベネズエラ・キューバ系反米メディア) や WION (BJP寄り民間) のような国家系・偏向メディアは、台本で必ず警告文を付ける運用を強制したい
- **既存コード破壊回避**: `SourceProfile` を Pydantic 化するが、既存コードは dict.get() で参照しているため `.get()` shim を追加して無改修で移行

### 決定

- `configs/sources.yaml` に 12 媒体追加 (Direct RSS 11 + Tier3 警告 2、Eurasianet も含む)
- `configs/source_profiles.yaml` に以下を導入:
  - `display_name_speech` (TTS 用): 例 "国際通信社のロイター"
  - `display_name_article` (記事/字幕): 例 "ロイター"
  - `display_name_subtitle` (字幕短縮): 例 "Reuters"
  - `requires_political_warning`: bool
  - `state_aligned`, `parent_company`, `funding_sources`, `warning_note`
- `src/ingestion/source_profiles.py` を Pydantic 化、`.get()` shim 追加で後方互換
- `select_authority_pair()` に `name_field` 引数追加 (default `mention_style_short` で既存挙動維持)
- 既存 25 媒体にも 3層表示名を遡及付与
- `cross_lang_matcher.py` に新 11 媒体の JP/EN 翻訳追加

### 結果

- テスト 1187 件全通過
- 既存25媒体改訂 + 新規12媒体追加完了
- ただし F-8-1-A 時点では `select_authority_pair` は `display_name_speech` を実際には使っておらず (default のまま)、配線は F-8-1-B に持ち越し

### 関連ファイル・コミット

- コミット: `acc9df2` (2026-04-28)
- 変更: `configs/sources.yaml` (+123), `configs/source_profiles.yaml` (+317), `src/ingestion/source_profiles.py` (+144), `src/ingestion/cross_lang_matcher.py` (+27), `tests/test_source_profiles_display_names.py` (新規 +159)

---

## 2026-04-28: F-8-1-B — Google News 5 媒体追加 + display_name_speech 配線 (Phase A.5-1 完了)

### 背景

F-8-1-A の YAML スキーマ不整合修正、`display_name_speech` の実配線、F-8-PRE-2 で救済された Google News 5 媒体の本番投入。

### 議論

- F-8-1-A で追加した 12 媒体は `category` / `bridge_source` フィールドが欠落、`priority` が文字列 (high/medium/low) のままで、ベースラインの 25 媒体スキーマと不整合だった → 統一が必要
- **WION の定義**: Web 調査 (RRM Canada 2024-09) の結果「BJP寄り民間 (Zee Media 傘下)」が正確。`warning_note` に RRM Canada 認定情報を記録、speech ラベルは中立 ("インドの民間英語ニュース局WION") に保つ
- **Caixin Global**: 中国国内で比較的独立性の高い経済メディア → warning なしで投入
- **`select_authority_pair` の配線**: `name_field='display_name_speech'` を `src/main.py:3215` で渡すよう変更
  - Claude Code が自主判断で `src/main.py:3209` の judge ペア分岐も同期更新 (出力一貫性のため)
  - Fallback: `display_name_speech` → `mention_style_short` → raw name の3段階

### 決定

- `configs/sources.yaml`: F-8-1-A の 12 媒体に `category` / `bridge_source` 追加、`priority` 数値化 (1/2/3)、`country` 大文字化
- 5 媒体追加 (Yomiuri, Sankei, Tokyo_Shimbun, WION, Caixin_Global、すべて Google News 経由)
- `src/main.py:3215` の `select_authority_pair` に `name_field="display_name_speech"` を渡す
- `src/main.py:3209` の judge ブランチも同期更新 (Claude Code 自主判断)
- `src/ingestion/rss_fetcher.py`: `source['category']` を `.get('category', 'general')` に変更 (KeyError 安全網)
- `cross_lang_matcher.py` に F-8-1-B 5 媒体の翻訳追加
- `tests/test_phase_a51_google_news_sources.py` (新規 8 tests)

### 結果

- **媒体数 41 達成、Phase A.5-1 完了**
- テスト 1195 件全通過 (1187 baseline + 8 新規)
- 試運転7-E ingestion: 41/42 成功 (Eurasianet のみ 0 entries、既知。feed-side 問題として FUTURE_WORK 持ち越し)
- `display_name_speech` 配線確認:
  - NHK + Reuters → 「NHK」/「国際通信社のロイター」
  - Yomiuri + WION → 「日本最大手の保守系紙、読売新聞」/「インドの民間英語ニュース局WION」
- 「英経済紙のフィナンシャル・タイムズ」「独高級ニュース誌のシュピーゲル」のような言い回しが TTS で出るように

### 関連ファイル・コミット

- コミット: `0a640f4` (2026-04-28)
- 変更: `configs/sources.yaml` (+135), `configs/source_profiles.yaml` (+69), `src/main.py` (+8/-3), `src/ingestion/rss_fetcher.py` (+1/-1), `src/ingestion/cross_lang_matcher.py` (+18), `docs/FUTURE_WORK.md` (+1/-1), `tests/test_phase_a51_google_news_sources.py` (新規 +131)

---

## 採用予定 (将来バッチ)

### F-12 — 台本品質革命 (Phase A.5-2 で実施予定)

#### 背景

試運転7-D で動画化に成功したが、品質ギャップが発覚:
- アーティクル (`article.md`): ★★★★★ Foreign Affairs 級、「移動する主権領土」のような独自言語化フレーズが出る
- 台本 (`script.json`): ★★★★ ReHacQ 級だが、「物理的限界に達している構造的変化を象徴」のような平凡表現に留まる

カズヤが Gemini に相談したところ「サマリ型台本」案を提示された。

#### Gemini の提案 (要旨)

> 動画台本は記事のサマリ (要約) として生成すべき。
> - AI構文 (「象徴している」「考察すると」) を排除
> - メディア批判 (「NHKが言わない」) を削除
> - アーティクルから純粋な事実 + 構造分析 + 日本への実利影響だけを抽出
> - 完全に「知性」だけで勝負する

#### 採用判断 (カズヤ + Claude.ai)

理由:
1. Gemini の分析が正しい (アーティクル品質は既に高い、台本だけ平凡)
2. 「移動する主権領土」「中東諸国の冷徹な実利主義」等の概念は現在の `script_writer` プロンプトでは絶対に出ない
3. 手作業 PoC ではなく自動化前提の設計が Hydrangea のコンセプト
4. ReHacQ・PIVOT・東洋経済オンラインの編集言語に到達するには順序逆転 (article → script) が必要

#### 実装方針

- Step 1: アーティクル先行生成 (article.md → script.json の順序逆転)
- Step 2: `script_writer` プロンプト全面刷新 (「サマリ型」+ 禁止語彙リスト)
- Step 3: Hook 強度ブースト (7軸自己採点ループ活用)

#### 実施タイミング

Phase A.5-2 の最優先バッチ。LLM コスト影響: ほぼ変わらず (生成回数は同じ、順序のみ変更)。改修規模: 1〜2 バッチ。

---

## Phase 1.5 完了後の展望

### 完了

- ✅ Phase 1.5 (改修): 15 バッチ
- ✅ Phase A.5-1 (多言語化深化): 4 バッチ (F-8-PRE / F-8-PRE-2 / F-8-1-A / F-8-1-B)
- ✅ 41 媒体体制
- ✅ 動画化体制完成 (ReHacQ 級品質、試運転7-D)

### 次フェーズ

- **Phase A.5-2**: F-12 (台本品質革命) 主導
- **Phase A.5-3**: F-7-α (動的多軸ペアリング) / F-7-β (多言語 cross_lang_matcher) / F-10 (Reality Check Layer)
- **Phase B**: 動画生成 PoC (ElevenLabs + 画像生成 + Remotion)
- **Phase C**: 投稿自動化 (TikTok / YouTube Shorts API)

### 3 ヶ月後ゴール

- 1 日 4 本投稿、ReHacQ・東洋経済オンライン超え品質
- Web メディア最小構成稼働
- 自社サービス送客導線

---

## 2026-05-01: F-doc-protocol — 文書自動更新プロトコルの確立

### 背景

Phase A.5-2 で 7 連続バッチ (F-12-A / F-13-A / F-13.B / F-14 / F-15 / F-16-A 等) を進めた結果、
過去の決定や予定が散逸する問題が発生した。「台本の日本語改善」「document 更新」「手動 PoC」等の
重要事項が「忘れ去られていた」。

カズヤの哲学「対症療法じゃなくて根本治療」「負の遺産残さないように」「月 1 棚卸しじゃ間に合わない」
に照らすと、月次レビュー (FW-1 で導入) だけでは追いつかない速度で文書負債が蓄積する状態だった。
都度更新を強制化する仕組みが必要と判断。

### 議論

- **案A (現状維持 + 月次レビュー強化)**: 既存の `FUTURE_WORK.md` 月次レビュー (FW-1) のみで運用継続
  - 短期的に楽だが、Phase A.5-2 の連続バッチで既に破綻している
- **案B (Claude Code の memory 系で記憶)**: メモリに「常に DECISION_LOG を更新」と書く
  - メモリは harness が実行する保証が無く、忘れる確率が残る
- **案C (バッチプロトコル文書化 + 各バッチプロンプトで参照強制)**: 採用
  - `docs/BATCH_PROTOCOL.md` を新設し、必須タスクを明文化
  - 各バッチプロンプト末尾でこのプロトコルを参照させる
  - CLAUDE.md からも参照することで全セッションで読まれる
  - Claude Code が「忘れない仕組み」を文書側で担保 (harness 依存しない)

### 決定

案C (バッチプロトコル文書化) を採用。

- `docs/BATCH_PROTOCOL.md` を新規作成。Task 1 (DECISION_LOG 更新) / Task 2 (FUTURE_WORK 更新) /
  Task 3 (完了レポート明記) の 3 タスクを必須化
- 不変原則 5 つ (article_writer / script_writer / src/triage 既存 / src/analysis / 既存テスト)
  も同ドキュメントに集約
- `CLAUDE.md` の冒頭付近に「Hydrangea Batch Protocol」セクションを追加し、必読ドキュメント
  リストにも `docs/BATCH_PROTOCOL.md` を追記

### 結果

- 各バッチ完了時に DECISION_LOG / FUTURE_WORK が必ず更新される運用が確立
- 形骸化防止のため、本プロトコル自体も月 1 レビュー対象に組み込み
- `src/` `tests/` `configs/` には一切変更を加えず、ドキュメント層のみで仕組み化したため
  リグレッション影響なし (1315 passed)

### 関連ファイル・コミット

- コミット: (push 時に追記)
- 変更:
  - `docs/BATCH_PROTOCOL.md` (新規作成)
  - `CLAUDE.md` (Hydrangea Batch Protocol セクション + 必読ドキュメント追記)
  - `docs/DECISION_LOG.md` (本エントリ — Task 1 の最初の実装例)
  - `docs/FUTURE_WORK.md` (完了済みへの本バッチ移動 — Task 2 の最初の実装例)

---

## 2026-05-01: F-12-B-1 — 台本プロンプトの「視聴者ファースト」原則追加

### 背景

試運転 7-K (2026-05-01) の baseline 台本 2 本 (cls-7bd1406438b6 FIFA 提訴 / cls-579833967531
フーシ派) を分析したところ、カズヤから 6 個の問題が指摘された:

1. 「イスラエル入植地クラブ」 — 略しすぎ (何のクラブか不明)
2. 「スポーツ仲裁裁判所」 — 補足なし (どこの組織か不明)
3. 「ロシア侵攻時の即時排除」 — 何を排除したか不明
4. 「公然たる支持」 — 直訳、口語的でない
5. 「地政学的断層」「直撃弾」「防衛戦」 — 抽象比喩で映像が浮かばない
6. 「発動」「看過」「露呈」「断じる」「ツール」 — 硬い文語、読み上げて違和感

一方で「秩序を信じる代償を、私たちは電気代という形で支払うことになるのです」のような
「抽象 → 具体」橋渡しは Hydrangea 理念を体現していると評価された。

根本原因: `configs/prompts/analysis/geo_lens/script_with_analysis.md` を確認したところ、
「扇動・陰謀論の禁止」(STEP 3) は強力に書かれているが、「視聴者へのわかりやすさ」への
配慮はゼロ。結果として LLM が「教科書っぽい硬い分析調」に寄っていた。

旧 F-12-B-1 (FUTURE_WORK 緊急度高) は当初「blind_spot_global 用フレーム追加」として
設計されていたが、試運転 7-K の結果から「全パターン共通の視聴者ファースト原則」の方が
優先度が高いと判断され、スコープを再定義した。

### 議論

- **案A (NG リスト方式: 禁止語の追加)**: 既存 STEP 3 と同じ NG リストに「断じる」「発動」等を追加
  - 短期的には効くが、いたちごっこになる。「考え方で制御」できないと類似ケースで再発
- **案B (具体例の押し付け: 推奨表現を細かく定義)**: 「こう書け」のテンプレを大量に追加
  - 「いちいち制御する話じゃない」(カズヤ)。LLM の柔軟な判断力を殺す
- **案C (抽象的な原則のみ追加 + LLM の判断信頼)**: 採用
  - 「視聴者ファースト」という姿勢を 3 原則 (聞いてわかる / 抽象より具体 / 読み上げて自然) で記述
  - 具体的な NG/OK リストは作らず、合格基準は「TikTok/Shorts で違和感なく聞けるか」のみ
  - 既存 STEP 3 (NG リスト) とは別軸として明示し、補完関係に位置付ける

### 決定

案C を採用。`configs/prompts/analysis/geo_lens/script_with_analysis.md` の
【ターゲット】直後・【入力データ】の前に「【視聴者ファーストの編集姿勢】」セクションを
追加 (既存セクションは一切変更しない)。

3 原則:
- **聞いてわかる**: 聞き慣れない固有名詞・専門用語・組織名は最小限の補足を添える
- **抽象より具体**: 比喩で締めず、視聴者の頭に映像が浮かぶ具体に落とす。抽象を使うときは直後に必ず具体への橋渡し
- **読み上げて自然**: 硬い文語・難しい漢語よりも、声に出した時に耳に届く語を選ぶ

合わせて `docs/BATCH_PROTOCOL.md` 不変原則 2 の例外条項を
「`configs/prompts/script/`」→「`configs/prompts/`」に拡大し、現状の主戦場が
`configs/prompts/analysis/geo_lens/` であることを注記した。

### 結果

試運転 (2026-05-01) で別事象 (cls-56c4197b6fd2 米イスラエル隠密作戦による二重国籍者奪還)
が選定され、新台本で以下が観察された:

- ✅ 「**中東独立メディアの**ミドル・イースト・アイによれば」— 固有名詞への補足が機能
  (旧台本「スポーツ仲裁裁判所」を素出ししていた問題と対照的)
- ✅ 「許可なき外国軍への従事」「過去の軍服写真を掘り起こし」— 平易な動詞・補足
- ✅ 「でも、地政学的に見れば」「動かしたんです」「ある日突然」— 話し言葉的接続
- ⚠️ 「地政学の檻」「冷徹な力学」— punchline で抽象比喩の癖は残存 (継続観察)
- ⚠️ char validation で 1 回リトライ発生 (setup=94字 → 82字)。原則「補足を添える」が
  文字数を押し上げる傾向確認。1 リトライで収束のため許容範囲だが、発動頻度は継続観察

リグレッション影響なし (プロンプトのみ変更、Python コード未touch)。
試運転で同一事象が再現できなかったため 6 個の問題の直接消失は未検証だが、
固有名詞補足・話し言葉化の効果は別事象でも観察できた。

### 関連ファイル・コミット

- コミット: 535f8e0 (feature/F-12-B-1)
- 変更:
  - `configs/prompts/analysis/geo_lens/script_with_analysis.md` (【視聴者ファーストの編集姿勢】追加、20 行追加)
  - `docs/BATCH_PROTOCOL.md` (不変原則 2 の例外条項拡大 + 注記追加)
  - `docs/DECISION_LOG.md` (本エントリ)
  - `docs/FUTURE_WORK.md` (旧 F-12-B-1 を完了済みに移動、F-12-B-1.5 を緊急度中に追加)

---

## 2026-05-01: F-12-B-1-extension — punchline 定義の「シニカル × 具体着地」両立化

### 背景

F-12-B-1 完了後の試運転で punchline 末尾に抽象比喩の癖が残存
(「地政学の檻に閉じ込める」「冷徹な力学」)。
根本原因は STEP 2 の punchline 定義「シニカルかつ知的な余韻」が
抽象詩を呼び込んでいたこと、および例として記載された
「綺麗事を信じた側が損をする」が STEP 3 の禁止表現
(物申す系 YouTuber 構文「綺麗事を信じる側が損をする」) と矛盾していたこと。

視聴者ファースト原則 (F-12-B-1 で「抽象より具体」を追加) と
punchline 定義 (シニカルな余韻) の方向性が一貫していない構造的問題。

### 議論

- **案A (シニカルかつ知的な余韻を完全削除)**: Hydrangea の知的切れ味が消え、
  ReHacQ・東洋経済の劣化コピーになる。Hydrangea ブランドの本質を毀損するため不採用
- **案B (シニカルさを保ちつつ具体着地で両立)**: 採用 (カズヤ判断)。
  「シニカル × 生活実感への橋渡し」が正解。シニカルさを「抽象詩で飾ること」と
  混同しないよう punchline 定義側で再定義する
- **案C (現状維持で継続観察)**: 残課題が放置され、抽象比喩の癖が固着するため不採用

### 決定

案B 採用。`configs/prompts/analysis/geo_lens/script_with_analysis.md` の
STEP 2 punchline 定義のみを修正 (他ブロック hook / setup / twist は不変):

- 「シニカルかつ知的な余韻を残す」は保持 (Hydrangea の知的切れ味を維持)
- 「ただし『シニカル』は抽象詩や抽象比喩で飾ることではない」を追加
  (試運転で観察された「地政学の檻」「冷徹な力学」型の抽象比喩に直接釘を刺す)
- 「視聴者の生活実感（電気代、物価、給料、税金、日常の選択）に着地して
  初めて、シニカルさが知的な余韻として機能する」で両立を明文化
- 優れた例:「秩序を信じる代償を、私たちは電気代という形で支払うことになる」
  (F-12-B-1 議論でカズヤが評価した実例 ── シニカル → 具体への着地が両立)
- 避けるべき例:「地政学の檻に閉じ込められた国の宿命」「冷徹な力学が動く」
  (試運転で実際に観察された抽象比喩を反面教師として明示)
- 「綺麗事を信じた側が損をする」例を削除
  (STEP 3 で禁止されている物申す系 YouTuber 構文との矛盾を解消)

### 結果

- punchline 定義と視聴者ファースト原則 (F-12-B-1 で追加) の一貫性確保
- STEP 2 例示と STEP 3 禁止リストの矛盾を解消
- 試運転は LLM 出力依存のため必須化せず未実施 (時間と再現性を考慮)。
  抽象比喩の軽減は今後の運用で継続観察
- リグレッション影響なし (プロンプトのみ変更、Python コード未 touch / 1315 passed)

### 関連ファイル・コミット

- コミット: 4db3335 (feature/F-12-B-1-extension)
- 変更:
  - `configs/prompts/analysis/geo_lens/script_with_analysis.md` (STEP 2 punchline 定義のみ修正、+10 行 / -2 行)
  - `docs/DECISION_LOG.md` (本エントリ)
  - `docs/FUTURE_WORK.md` (本エントリを完了済みに追加)

---

## 2026-05-01: F-state-protocol — CURRENT_STATE / DISCUSSION_NOTES 導入と不変原則 2 の正確化

### 背景

Phase A.5-3a で 11 連続 main マージ成功 (F-12-A → F-12-B-1-extension) を達成
したが、チャット移行のたびに 2806 行の引き継ぎプロンプトを手作業で再構築する
運用が持続不可能になった。具体的には:

- 引き継ぎプロンプトが毎回ゼロから手作業で再構築されている
- 過去の決定事項 (C-1/C-2/C-3 RPM 対策、F-13 隠れ層、F-7-α 部分実装等) が
  バッチ歴史リストから消える事故が発生
- 不変原則 2「`script_writer.py` 一切変更不可」が実装と乖離
  (F-12-A / F-12-B / Batch 5 で大改修済み、新ルート
  `generate_script_with_analysis` 系が稼働中)
- DECISION_LOG / FUTURE_WORK は時系列ログとして機能するが、「今この瞬間の
  プロジェクトのスナップショット」を提供する仕組みがない
- 議論中の未確定メモを蓄積する場所がない

カズヤの哲学:「対症療法じゃなくて根本治療」「負の遺産残さないように」
「月 1 棚卸しじゃ間に合わない」「カズヤの手作業はバッチプロンプトのコピペ
1 回のみ」を、F-doc-protocol (DECISION_LOG / FUTURE_WORK 強制更新) の上に
「生きたサナリー」と「議論メモ蓄積」のレイヤーとして実装する必要があった。

### 議論

- **案A (CURRENT_STATE.md のみ追加)**: 議論メモの蓄積先がないため、
  バッチ完了時に「これ DECISION_LOG にするほどでもないが残したい」項目が
  散逸する問題が解消しない → 不採用
- **案B (DISCUSSION_NOTES.md のみ追加)**: 「今この瞬間のスナップショット」が
  ないままだと、引き継ぎプロンプトの手作業再構築は解消しない → 不採用
- **案C (両方追加 + BATCH_PROTOCOL に Task 4/5 追加 + 不変原則 2 是正)**:
  採用。CURRENT_STATE.md (全置換更新型) で「現在地」を提供し、
  DISCUSSION_NOTES.md (蓄積型) で「議論中メモ」を吸収する。
  バッチ完了時の必須タスクを Task 1-3 から Task 1-5 に拡張する。
  あわせて、長く乖離していた不変原則 2 を「既存ルート不可、新ルート可」に
  是正する。

### 決定

案C 採用。以下を一括投入:

1. **`docs/CURRENT_STATE.md` を新規作成**:
   - 8 セクション構成 (リポジトリ状態 / 現在のフェーズ / 直近試運転 /
     防衛機構の現状 4+1 層 / 触ってよい・ダメ領域マップ / 不変原則 5 つ /
     カズヤの直近フィードバック / 関連ドキュメント導線)
   - 初回値: main HEAD `1e4a932`、baseline `1315 passed`、11 連続成功、
     試運転 7-K 動画化率 100%、Phase A.5-3a 完了 → A.5-3a-verify 着手前
   - バッチ完了時に「全置換更新」する運用 (追記ではない)
2. **`docs/DISCUSSION_NOTES.md` を新規作成**:
   - 「未分類 (Active)」と「アーカイブ」の 2 セクション構成
   - 各エントリは「日付 / トピック / 内容 / 出典 / ステータス」の 5 項目
   - 初期エントリ 10 件投入 (本タスクで集約された未記録の議論を一気に
     書き起こし)
3. **`docs/BATCH_PROTOCOL.md` を拡張**:
   - 不変原則 5 つを A.5-3a 時点版に差し替え
     (特に不変原則 2 を「既存ルート不可、新ルート可、`_CHAR_BOUNDS` 等の
     定数調整は最小改変なら許容」に正確化)
   - Task 4 (DISCUSSION_NOTES 整理: 4-A 新規追加 + 4-B 既存再評価) 追加
   - Task 5 (CURRENT_STATE 全置換更新) 追加
   - バッチプロンプトテンプレートを Task 1-5 に更新
4. **`CLAUDE.md` を更新**:
   - 必読ドキュメントリストの最上位に CURRENT_STATE.md を配置
   - DISCUSSION_NOTES.md を 5 番目に追加
   - 順序を「実装作業の前に必ず以下を確認」から
     「新規バッチ着手時は以下を **この順序で** 必ず参照」に変更
5. **本バッチ自身に Task 1-5 を適用** (ドッグフーディング)

### 結果

- 引き継ぎプロンプトの手作業再構築が CURRENT_STATE.md の参照で代替可能に
- 議論中メモの蓄積先が DISCUSSION_NOTES.md として確保され、バッチ完了時の
  再評価で DECISION_LOG / FUTURE_WORK へ昇格させる運用が確立
- 不変原則 2 の実装乖離が解消され、F-12-B-1.5 (`_CHAR_BOUNDS` 調整) や
  今後の新ルート改修が「不変原則 2 違反」と読まれない仕組みに
- リグレッション影響なし (docs/ + CLAUDE.md のみ変更、
  src/ tests/ configs/ は 0 行変更、baseline 1315 passed 維持)

### 関連ファイル・コミット

- コミット: (push 後に追記)
- 変更:
  - `docs/CURRENT_STATE.md` (新規)
  - `docs/DISCUSSION_NOTES.md` (新規 + 初期エントリ 10 件)
  - `docs/BATCH_PROTOCOL.md` (不変原則差し替え + Task 4/5 追加 +
    テンプレート更新 + 関連ドキュメント追記)
  - `CLAUDE.md` (必読ドキュメントリスト刷新)
  - `docs/DECISION_LOG.md` (本エントリ)
  - `docs/FUTURE_WORK.md` (本エントリを完了済みに追加)

---

## 2026-05-02: F-state-protocol-supplement — Phase A.5-3a-verify / A.5-3b ロードマップ確定

### 背景

F-state-protocol で CURRENT_STATE.md / DISCUSSION_NOTES.md / BATCH_PROTOCOL Task 4/5 が
確立した直後、次フェーズの詳細仕様を FUTURE_WORK.md に正式登録する必要があった。

CURRENT_STATE.md 初版の「次バッチ候補」セクションは `Phase A.5-3a-verify
(F-verify-jp-coverage 最優先)` と総称的な記載のみで、各 verify エントリの
具体的内容 (想定工数 / 関連ファイル / 判断材料) が定義されていなかった。
このままでは次バッチ着手時に「何を verify すれば良いのか」を再考する必要があり、
F-state-protocol で目指した「CURRENT_STATE を読めば次の手が即座に判明する」
状態に到達していなかった。

### 議論

- **Phase A.5-3a-verify を 5 カテゴリで構成**: jp-coverage / e2e / rss /
  perspective / script-quality。Hydrangea コンセプト防衛機構 (jp-coverage)、
  パイプライン安定性 (e2e / rss)、品質判定材料 (perspective / script-quality)
  の 3 系統に整理した
- **F-verify-jp-coverage を最優先**: F-13.B 防衛機構の実 precision/recall
  未測定が最大のリスク (rescue 完全廃止後の唯一の JP 報道判定経路)
- **F-verify-perspective と F-verify-script-quality は判断材料を兼ねる**:
  それぞれ F-12-B-2 (axis 多様化) / F-12-B-1.5 (文字数制約緩和) の着手判断
  材料となる。「測定先行 → 判断後着手」の原則に沿って、verify を判断ゲート
  として設計
- **Phase A.5-3b 手動 PoC は Phase A.5-3a-verify 全通過後**: 「自動化前に
  最高傑作を 1 本」哲学 (DISCUSSION_NOTES #1) を実装する位置付け。
  品質保証の積み上げ順 (verify 全通過 → ゴールドスタンダード作成) で配置

### 決定

1. `docs/FUTURE_WORK.md` 緊急度 高に Phase A.5-3a-verify 5 エントリを追加
   (各エントリに想定工数 / 関連ファイル / 判断材料を明記)
2. `docs/FUTURE_WORK.md` 緊急度 中に Phase A.5-3b 手動 PoC を追加
   (golden_master_spec.md 仕様付き)
3. `docs/CURRENT_STATE.md` の「次バッチ候補」を F-verify-jp-coverage 最優先で
   更新 (1st-5th + Phase A.5-3b への分岐を明記)
4. CURRENT_STATE.md の他セクション (リポジトリ状態 / 試運転結果 / 防衛機構等)
   は F-state-protocol で投入された値が前日のまま有効なため変更しない
   (最小改変原則)
5. 既存 FUTURE_WORK.md エントリは末尾追加のみで一切変更しない

### 結果

- 次バッチ着手時に CURRENT_STATE.md の「次バッチ候補」を読めば次の手が
  即座に判明する状態を確立
- 各 verify エントリに想定工数を付記したことで、カズヤが時間配分を判断しやすく
  なった (jp-coverage 2-3h / e2e 5d×30min / rss 1h / perspective+script-quality
  各 1h)
- F-12-B-2 / F-12-B-1.5 の着手タイミングが verify-perspective /
  verify-script-quality の結果に紐付けられたため、「いつ着手すべきか」が
  データドリブンに判定できる構造に
- F-state-protocol の仕組み (CURRENT_STATE.md / DISCUSSION_NOTES.md /
  Task 1-5) が想定通り機能することを実地テストで確認 (本バッチが初回適用)
- リグレッション影響なし (docs/ 3 ファイルのみ変更、src/ tests/ configs/ は
  0 行変更、baseline 1315 passed 維持)

### 関連ファイル・コミット

- コミット: (push 後に追記)
- 変更:
  - `docs/FUTURE_WORK.md` (緊急度 高に 5 エントリ追加 + 緊急度 中に 1 エントリ追加)
  - `docs/CURRENT_STATE.md` (Phase 行 + 次バッチ候補セクション + 末尾注記の最小更新)
  - `docs/DECISION_LOG.md` (本エントリ)
- 関連: F-state-protocol (CURRENT_STATE / DISCUSSION_NOTES 仕組み確立)

---

## 2026-05-02: F-doc-backfill — 過去 19 セッション分の積み残し登録 + ロードマップ大幅改訂

### 背景

F-state-protocol (2026-05-01) で CURRENT_STATE.md / DISCUSSION_NOTES.md /
BATCH_PROTOCOL Task 4/5 が確立し、F-state-protocol-supplement (2026-05-02) で
Phase A.5-3a-verify ロードマップを正式登録した直後、2026-05-02 のカズヤとの
議論で次の構造的課題が浮上した:

1. **Phase A.5-3a-verify が過剰防衛**: F-verify-e2e (5 日連続稼働) と
   F-verify-rss (47+ sources 疎通) は、試運転 7-K で動画化率 100% を達成済み
   である現状、得られる情報が反復のみで時間効率が悪い
2. **macOS say の Linux 対応 (旧 F-16-B-pre) が ElevenLabs 採用と矛盾**:
   say を維持する意義がなく、廃止 + ElevenLabs 統合を Phase A.5-3c に前倒すべき
3. **動画合成ツール Remotion 採用が docs に未記録**: 当初から想定だったが、
   Phase A.5-3b 手動 PoC を CapCut で組むと Remotion 移植で二度手間
4. **画像プロンプト出力仕様が未確認**: video_payload_writer.py がシーンごとの
   画像プロンプトを十分な品質で出しているかが、Phase A.5-3b 着手前の必須調査
5. **過去 19 セッション分の積み残しが未登録**: Phase 1 (1-A〜1-D) /
   TECH_DEBT 同時対応 / Phase B (B-1〜B-7) / Phase C (収益化系 5 項目) /
   観察中項目 (F-17 候補 / _FRAMING_RESULTS LRU / 並列化) / クラウド誤り 1-4 /
   三角測量未対応 / 3 ソース対比未実装

カズヤの哲学「対症療法じゃなくて根本治療」「負の遺産残さないように」
「忘れ去られた約束を絶対忘れない仕組み」に照らすと、F-state-protocol /
F-state-protocol-supplement の上に「過去 19 セッション分を一気に書き出す」
バッチが必要だった。

### 議論

- **案A (verify を 5 カテゴリのまま実施)**: 不採用。e2e / rss が過剰防衛で時間効率悪い
- **案B (verify を 4 カテゴリに縮小 + Phase A.5-3c/3d 新設 + 19 セッション分書き起こし)**:
  採用。スコープ大きいが、文書整備のみで src/ tests/ configs/ には触らないため
  リグレッションリスクなし
- **案C (バッチを 3 つに分割: ①verify 縮小 / ②3c-3d 新設 / ③19 セッション登録)**:
  不採用。バッチ間で「何が登録されたか」がコンテキスト散逸し、3 回プロトコル
  Task 1-5 を繰り返す手間が増える

### 決定

案B 採用。F-doc-backfill として一括投入:

1. **FUTURE_WORK.md 改訂**:
   - Phase A.5-3a-verify を 5→4 カテゴリに縮小
     (F-verify-e2e / F-verify-rss を完全削除、F-image-prompt-spec を新規追加)
   - Phase A.5-3b を Remotion + ElevenLabs + 画像生成前提に書き直し
   - Phase A.5-3c 合成パート自動化を新設
     (F-elevenlabs-integration / F-image-gen-integration /
      F-video-compose-integration / F-cron の 4 エントリ)
   - Phase A.5-3d 投稿前ゲート + 自動投稿を新設
   - Phase 1 (1-A〜1-D + TECH_DEBT 2.1/2.2/2.3/2.5 同時対応) を緊急度 中
   - Phase B (B-1〜B-7) と Phase C (C-1〜C-5) を緊急度 低
   - 観察中項目 (F-17 候補 / _FRAMING_RESULTS LRU / 並列化検討) を新設
2. **DISCUSSION_NOTES.md に 6 エントリ追加** (合計 16 Active):
   - クラウド誤り 1-4 (Tier 分類機械制御 / テンプレ過剰押し付け /
     直近チャットしか振り返らない / F-doc-protocol 結果見落とし)
   - 三角測量にハマらないパターン (4 種類) 未対応
   - 3 ソース対比ルール部分実装
3. **DECISION_LOG.md に 7 エントリ追加**:
   - 本エントリ (F-doc-backfill 概要)
   - Phase A.5-3a-verify スコープ縮小
   - macOS say 廃止 + ElevenLabs 前倒し採用
   - 動画合成ツール Remotion 採用確定
   - Supabase 段階移行「今週末は危険すぎる」判断 (Apr 30 遡及記録)
   - 6 パターン武器庫 → 4 パターン削減経緯 (遡及記録)
   - Hook 5 類型 / 視聴維持ピーク 4 点設計の廃止経緯 (遡及記録)
4. **CURRENT_STATE.md の「次バッチ候補」全置換更新**:
   - 1st: F-verify-jp-coverage (2-3h)
   - 2nd: F-verify-perspective
   - 3rd: F-verify-script-quality
   - 4th: F-image-prompt-spec
   - Phase A.5-3a-verify 全通過後 → 3b → 3c → 3d
5. **BATCH_PROTOCOL Task 1-5 を本バッチ自身に適用** (ドッグフーディング)

### 結果

- ロードマップが 4 段階 (3a-verify → 3b → 3c → 3d) に再構成され、CURRENT_STATE
  を読めば次の手が即座に判明する状態を維持
- ElevenLabs 前倒しと Remotion 採用が DECISION_LOG に正式記録され、Phase A.5-3b
  → 3c の連続性が確保 (CapCut 仮組み案による二度手間を回避)
- 過去 19 セッション分の積み残しが FUTURE_WORK に正式登録され、「忘れ去られた
  約束」が再発する確率が大幅に低下
- リグレッション影響なし (docs/ のみ変更、src/ tests/ configs/ は 0 行変更、
  baseline 1315 passed 維持)

### 関連ファイル・コミット

- コミット: (push 後に追記)
- 変更:
  - `docs/FUTURE_WORK.md` (Phase A.5-3a-verify 縮小 + 3c/3d/Phase1/B/C/観察中項目 新設 + 完了済みに本エントリ)
  - `docs/DISCUSSION_NOTES.md` (6 エントリ追加 = 16 Active)
  - `docs/DECISION_LOG.md` (7 エントリ追加)
  - `docs/CURRENT_STATE.md` (次バッチ候補全置換更新)
- 関連: F-state-protocol / F-state-protocol-supplement

---

## 2026-05-02: F-doc-backfill — Phase A.5-3a-verify スコープ縮小

### 背景

F-state-protocol-supplement で Phase A.5-3a-verify を 5 カテゴリ
(jp-coverage / e2e / rss / perspective / script-quality) で登録したが、
カズヤとの議論で過剰防衛と判明。1 回の試運転 (7-K) で動画化率 100% 達成済みで、
5 日連続稼働 (F-verify-e2e) で得られる情報は反復のみ。47+ sources 疎通
(F-verify-rss) も現時点で疎通失敗してないため緊急性なし。

### 議論

- **案A (当初予定通り 5 カテゴリで実施)**: 不採用 (e2e と rss は過剰防衛、時間効率悪い)
- **案B (e2e と rss を削除、jp-coverage / perspective / script-quality の
  3 カテゴリ + 新規 image-prompt-spec の 4 カテゴリに縮小)**: 採用
  (検証密度集中、時間効率改善)

### 決定

1. F-verify-e2e と F-verify-rss を FUTURE_WORK から削除 (完了済みでないため
   「完了済み」セクションには移動しない、本エントリで降格理由を記録)
2. F-image-prompt-spec を新規追加 (Phase A.5-3b 着手前に画像プロンプト仕様確認)
3. e2e / rss は「問題発生時に随時実施」枠として位置付け、再検討時は新規
   バッチとして起こす

### 結果

Phase A.5-3a-verify が 1 週間 → 数日に短縮、検証密度が jp-coverage /
perspective / script-quality / image-prompt-spec の 4 軸に集中。

### 関連ファイル・コミット

- コミット: (F-doc-backfill 一括コミットに統合)
- 変更: `docs/FUTURE_WORK.md` (F-verify-e2e / F-verify-rss 削除、F-image-prompt-spec 追加)

---

## 2026-05-02: F-doc-backfill — macOS say 廃止 + ElevenLabs 前倒し採用

### 背景

過去のロードマップで F-16-B-pre (macOS say の Linux 対応、1 時間) と
Phase B-2 (ElevenLabs 統合) が並列で計画されていたが、ElevenLabs 採用するなら
say の Linux 対応は無意味な作業。Phase A.5-3b で ElevenLabs で「最高傑作」を
作るので、自動化フェーズで say に戻すと品質劣化する。

### 議論

- **案A (当初予定通り F-16-B-pre → F-16-B → Phase B-2 ElevenLabs)**:
  不採用 (二度手間、品質劣化期間が発生)
- **案B (F-16-B-pre 廃止 + ElevenLabs を Phase A.5-3c に前倒し)**:
  採用 (一貫性確保、品質劣化なし)

### 決定

1. F-16-B-pre 廃止 (FUTURE_WORK に追加されていなかったため、改めて登録せず削除扱い)
2. F-elevenlabs-integration を Phase A.5-3c の最初に新規配置
3. F-cron (旧 F-16-B) は ElevenLabs 前提で実装
4. TECH_DEBT 2.5 (macOS say 依存) の対応時期を Phase 1-A → F-elevenlabs-integration に前倒し

### 結果

ロードマップが一貫し、Phase A.5-3b 手動 PoC で確定した品質基準が自動化
フェーズでも維持される構造に。

### 関連ファイル・コミット

- コミット: (F-doc-backfill 一括コミットに統合)
- 変更: `docs/FUTURE_WORK.md` (F-elevenlabs-integration を Phase A.5-3c に追加)

---

## 2026-05-02: F-doc-backfill — 動画合成ツール Remotion 採用確定

### 背景

過去 docs (architecture_decisions.md / REFACTORING_PLAN.md) で Remotion 移行は
言及されていたが Phase B 案件として後回しになっていた。Phase A.5-3b 手動 PoC で
CapCut 等 GUI ツールで仮組みすると、Phase A.5-3c の自動化で Remotion に移植する
二度手間が発生する。

### 議論

- **案A (Phase A.5-3b は CapCut で仮組み、Phase A.5-3c で Remotion 移植)**:
  不採用 (二度手間、PoC 時の品質基準と自動化結果が乖離するリスク)
- **案B (Phase A.5-3b からいきなり Remotion + Claude Code でコード書く)**:
  採用 (自動化スムーズ、PoC 時に確定したパラメータがそのまま自動化に活きる)

### 決定

1. 動画合成ツールは Remotion で確定
2. Phase A.5-3b 手動 PoC で Remotion セットアップ (Claude Code がコード、
   カズヤがレビュー)
3. F-video-compose-integration を Phase A.5-3c に配置
4. Phase B-5 (Remotion 移行) は前倒し実施済の扱いとし、本エントリは Lambda
   並列レンダリングに縮小

### 結果

Phase A.5-3b → 3c の連続性が確保、CapCut 案による二度手間を回避。

### 関連ファイル・コミット

- コミット: (F-doc-backfill 一括コミットに統合)
- 変更: `docs/FUTURE_WORK.md` (Phase A.5-3b Remotion 前提化, F-video-compose-integration を Phase A.5-3c に追加, Phase B-5 を Lambda のみに縮小)

---

## 2026-05-02: F-doc-backfill — Supabase 段階移行「今週末は危険すぎる」判断 (遡及記録)

### 背景 (Apr 30 議論を遡及記録)

Apr 30 の議論で Gemini が「今週末 Supabase 移行」を提案したが、クラウドが
「危険すぎる」と反論。当時 DECISION_LOG に未記録のため、F-doc-backfill で
遡及記録する。SQLite 前提の baseline 1315 passed が、影響範囲不明のまま週末
作業で破壊されるリスクが大きかった。

### 議論

- **案A (Gemini 提案: 今週末 Supabase 移行)**: 不採用 (影響範囲が大きすぎる、
  baseline 1315 passed の保護優先)
- **案B (クラウド反論: Phase 1 の他項目完了後、計画的に段階移行)**: 採用

### 決定

Phase 1-D として登録 (Phase 1-A/B/C 完了後)、フィーチャーフラグで段階移行、
ゴールデンテストでリグレッション保証。

### 結果

SQLite 前提の baseline 1315 passed が保護された。以後 4 連続バッチ
(F-12-B-1 / F-12-B-1-extension / F-state-protocol / F-state-protocol-supplement)
で 1315 passed を維持できたのは本判断の効果。

### 関連ファイル・コミット

- コミット: (F-doc-backfill 一括コミットに統合 — 議論自体は Apr 30)
- 変更: `docs/FUTURE_WORK.md` Phase 1-D に補足、`docs/DECISION_LOG.md` 本エントリ

---

## 2026-05-02: F-doc-backfill — 6 パターン武器庫 → 4 パターン削減経緯 (遡及記録)

### 背景

Phase 1 (Apr 25-27) で台本武器庫を 6 パターンから 4 パターンに削減した経緯が
DECISION_LOG に未記録。当時の議論で「Hydrangea のブランド (シニカル × 知性) と
扇動寄り 2 パターンが矛盾する」と判定された経緯を遡及記録する。

### 議論 (遡及)

- **6 パターン維持案**: 不採用。Media Critique と Anti-Sontaku が ReHacQ・
  東洋経済級の知的トーンと両立しない
- **4 パターン削減案**: 採用 (カズヤ判断)

### 決定

- 採用 4 パターン: Breaking Shock / Geopolitics (メイン) / Paradigm Shift /
  Cultural Divide
- 廃止 2 パターン:
  - Media Critique (扇動寄り、Hydrangea ブランドと矛盾)
  - Anti-Sontaku (物申す系、扇動寄り)

### 結果

Hydrangea のブランド (シニカル × 知性) との整合性確保。F-12-B-1 / F-12-B-1-extension
で「視聴者ファースト + 具体着地」を加えて完成形に。

### 関連ファイル・コミット

- コミット: (F-doc-backfill 一括コミットに統合 — 議論自体は Apr 25-27)
- 変更: `docs/DECISION_LOG.md` 本エントリ (遡及記録)

---

## 2026-05-02: F-doc-backfill — Hook 5 類型 / 視聴維持ピーク 4 点設計の廃止経緯 (遡及記録)

### 背景

Phase 1 (Apr 25-27) で Hook 5 類型 (Type-A 数字ショック / Type-B 固有名詞否定 /
Type-C カウントダウン / Type-D 逆説宣言 / Type-E 名指し暴露) と視聴維持ピーク
4 点設計 (0-1.5s Hook / 3.0s 継続フック / 7.0s 数字 / 15.0s 第 1 Reveal /
30.0s 第 2 Reveal) を廃止した経緯が DECISION_LOG に未記録。

### 議論 (遡及)

- **Hook 5 類型 + ピーク 4 点維持案**: 不採用。「機械的設計」とカズヤが判定。
  視聴者を扇動・操作する型に LLM を縛る方向性が Hydrangea のブランドと矛盾
- **抽象原則化案**: 採用 (カズヤ判断)。視聴者ファースト 3 原則 + punchline 定義に
  置き換え

### 決定

Hook 5 類型と視聴維持ピーク 4 点設計を廃止し、視聴者ファースト 3 原則 +
punchline 定義 (シニカル × 具体着地の両立) に置き換え。F-12-B-1 / F-12-B-1-extension
で完成形に。

### 結果

扇動型バズ最適化から、ReHacQ・東洋経済級の知的トーンへ転換。F-12-B-1 試運転で
固有名詞補足・話し言葉化が機能することを確認。

### 関連ファイル・コミット

- コミット: (F-doc-backfill 一括コミットに統合 — 議論自体は Apr 25-27)
- 変更: `docs/DECISION_LOG.md` 本エントリ (遡及記録)

---

## 2026-05-02: F-doc-backfill-supplement — 画像生成候補確定 + 自動投稿フェーズ方針 + 拡張性原則

### 背景

F-doc-backfill (2026-05-02) で過去 19 セッション分の積み残しを正式登録した
直後、カズヤとの議論で以下の追加判断が確定:

1. ChatGPT Images 2.0 (gpt-image-2) を画像生成候補に正式追加
   (2026-04-21 リリースの OpenAI 最新モデル、Image Arena #1、F-doc-backfill で
   登録した「DALL-E 3」は旧モデルのため差し替え)
2. 自動投稿フェーズ方針の確定 (geo_lens のみ単独本番、TikTok + YouTube Shorts
   両方同時、完全自動投稿、cron 6 時間おき、人手介入ゼロ)
3. 拡張性原則の明文化 (Phase A.5-3c 実装時に「将来の多チャンネル対応 /
   別形式展開を阻害しない最小限の抽象化」を設計原則として遵守)

詳細は本バッチで追加した 3 つの個別エントリ (本エントリ直下) を参照。

### 議論

- 案 A: F-doc-backfill のままで放置 (画像生成候補は DALL-E 3、Phase A.5-3d は
  詳細未定、拡張性原則は暗黙)
  → 不採用 (DALL-E 3 は旧モデル、Phase A.5-3d 実装時の判断軸が曖昧、Phase 1-A の
  ChannelConfig 統合まで「ハードコード」発生リスクあり)
- 案 B: 補足バッチで 3 判断を文書化、Phase A.5-3c 着手前に設計原則を確定
  → 採用

### 決定

1. 画像生成候補を「Nano Banana Pro / ChatGPT Images 2.0 (gpt-image-2) /
   Flux 1.1 Pro」の 3 つに確定 (DALL-E 3 を削除)
2. Phase A.5-3d は geo_lens のみ単独本番、TikTok + YouTube Shorts 両方同時、
   完全自動投稿
3. Phase A.5-3c 実装時から拡張性原則 (configs/channels/{channel_id}.yaml で
   投稿先 / 形式 / カテゴリを切替可能) を遵守
4. Phase B 以降の方向性 (japan_athletes / k_pulse 追加 / 動画継続 / 独自メディア化 /
   カテゴリ細分化等) は Phase A.5-3d 安定稼働後に判断 (DISCUSSION_NOTES に保留)

### 結果

Phase A.5-3a-verify → A.5-3b → A.5-3c → A.5-3d のロードマップが 2026-05-02 時点の
最新ラインナップに更新され、Phase A.5-3c 実装時の設計原則も明確化。Phase B 以降の
柔軟性も確保。

### 関連ファイル・コミット

- コミット: (F-doc-backfill-supplement で本エントリ + 個別 3 エントリを一括コミット)
- 変更: `docs/FUTURE_WORK.md` (F-image-prompt-spec / Phase A.5-3b /
  F-image-gen-integration / Phase A.5-3d 改訂 + 本バッチ完了済みエントリ),
  `docs/DECISION_LOG.md` (本エントリ + 個別 3 エントリ),
  `docs/DISCUSSION_NOTES.md` (Phase B 以降の方向性未確定エントリ),
  `docs/CURRENT_STATE.md` (Phase A.5-3d 投稿対象の補足セクション)

---

## 2026-05-02: F-doc-backfill-supplement — ChatGPT Images 2.0 (gpt-image-2) を画像生成候補に正式追加

### 背景

F-doc-backfill で画像生成候補を「Nano Banana Pro / DALL-E 3 / Flux 1.1 Pro」と
記載したが、DALL-E 3 は旧モデル。OpenAI が 2026-04-21 にリリースした
ChatGPT Images 2.0 (API 名 gpt-image-2) が最新版で、Image Arena リーダーボードで
全カテゴリ #1 (+242 ポイントリード)、業界初の Agentic 画像生成。
カズヤが実物を試して「今までとは次元が違う」と評価。

### 議論

- 案 A: F-doc-backfill のまま DALL-E 3 で進める
  → 不採用 (旧モデル、品質劣る)
- 案 B: ChatGPT Images 2.0 (gpt-image-2) に差し替え
  → 採用

### 決定

1. 画像生成候補を「Nano Banana Pro / ChatGPT Images 2.0 (gpt-image-2) /
   Flux 1.1 Pro」の 3 つに確定
2. Phase A.5-3b 手動 PoC で 3 つを実地比較し、シネマティック表現 / 日本語テキスト
   精度 / プロンプト追従性 / 価格 / API 安定性で総合判断
3. F-doc-backfill 該当エントリ (F-image-prompt-spec / Phase A.5-3b /
   F-image-gen-integration) を本バッチで修正

### 結果

画像生成候補が 2026-05-02 時点の最新ラインナップに更新

### 関連ファイル・コミット

- docs/FUTURE_WORK.md (F-image-prompt-spec / Phase A.5-3b / F-image-gen-integration
  の画像生成ツール候補修正)
- 関連: F-doc-backfill (画像生成候補の初期登録)

---

## 2026-05-02: F-doc-backfill-supplement — 自動投稿フェーズ方針確定

### 背景

F-doc-backfill で Phase A.5-3d (本番リリース + 自動投稿) を登録したが、
投稿対象 / 投稿先 / 投稿モードの詳細が曖昧だった。カズヤとの議論で確定。

### 議論

- **投稿対象**:
  - 案 A: 3 チャンネル (geo_lens / japan_athletes / k_pulse) 同時自動投稿
    → 不採用 (japan_athletes / k_pulse は Phase B 案件、現時点で実装なし)
  - 案 B: geo_lens (政治・経済) のみ単独本番、その他は運用見ながら
    → 採用 (動くものを壊さない、品質保証の積み上げ順)
- **投稿先**:
  - 案 A: YouTube から先行、TikTok は審査通過後
  - 案 B: TikTok と YouTube 両方同時 (TikTok 申請しながら YouTube 先行も可)
    → 採用 (リーチ最大化、両方ブランド資産化)
- **投稿モード**:
  - 案 A: 手動投稿 → 半自動 → 完全自動の段階移行
  - 案 B: 完全自動投稿 (cron 6 時間おき、人手介入ゼロ) を Phase A.5-3d で目指す
    → 採用 (投稿前ゲートで品質保証、人手介入はレビューキューでの定期確認のみ)

### 決定

1. Phase A.5-3d の投稿対象は geo_lens のみ
2. japan_athletes / k_pulse / その他カテゴリ追加 / 独自メディア化等は Phase B 以降に
   判断 (DISCUSSION_NOTES「Phase B 以降の方向性未確定」参照)
3. 投稿先は TikTok と YouTube Shorts の両方同時
4. 投稿モードは完全自動 (cron 6 時間おき、人手介入ゼロ、投稿前ゲートで品質保証)

### 結果

Phase A.5-3d の実装スコープが明確化、Phase B 以降の柔軟性も確保

### 関連ファイル・コミット

- docs/FUTURE_WORK.md (Phase A.5-3d エントリの対応案明確化)
- docs/DISCUSSION_NOTES.md (Phase B 以降の方向性未確定エントリ追加)
- 関連: F-doc-backfill (Phase A.5-3d 初期登録)

---

## 2026-05-02: F-doc-backfill-supplement — 拡張性原則の明文化

### 背景

カズヤ「japan_athletes / k_pulse のタイミングは未定だが、見通した拡張性は持たせた
実装をしたい」。Phase A.5-3c (合成パート自動化) の実装時に「将来の多チャンネル対応 /
別形式展開 (動画以外、独自メディア等) を阻害しない」を設計原則として明示する必要。

### 議論

- 案 A: 現状の geo_lens 専用設計を維持、多チャンネル対応は Phase 1-A で対応
  → 不採用 (Phase A.5-3c で「ハードコード」が発生すると Phase 1-A での改修コスト増)
- 案 B: Phase A.5-3c 実装時から「拡張性確保」を設計原則として持ち込む
  → 採用 (将来コスト削減、カズヤ哲学「負の遺産残さない」と整合)

### 決定

拡張性原則 (Phase A.5-3c 以降の実装時に遵守):

1. **チャンネル別設定の YAML 化**: 投稿先 / 形式 / 声 / 画風等は configs/channels/
   {channel_id}.yaml で切替可能とする (geo_lens.yaml が最初、後で他チャンネル追加)
2. **形式の抽象化**: 「動画」を前提にハードコードせず、「コンテンツ形式」として
   抽象化 (将来の独自メディア / 静止画ポスト / 記事配信等への展開を阻害しない)
3. **投稿先の抽象化**: TikTok / YouTube に限定せず、Publisher 抽象クラスで
   将来の Instagram / X / 独自メディア等への展開を許容
4. **カテゴリの拡張性**: 政治・経済以外への展開 (細分化 / スポーツ / エンタメ等) を
   configs/channels/ レベルで対応可能とする

ただし「過剰設計しない」原則も併記: Phase 1-A (ChannelConfig 統合) で本格対応する
ため、Phase A.5-3c では「将来阻害しない最小限の抽象化」に留める。

### 結果

Phase A.5-3c 実装時の設計指針が明確化、Phase 1-A 着手時の改修コストが軽減される
構造に

### 関連ファイル・コミット

- docs/DECISION_LOG.md (本エントリ)
- 関連: Phase A.5-3c の各エントリ (F-elevenlabs-integration /
  F-image-gen-integration / F-video-compose-integration / F-cron) で本原則を遵守

---

## 2026-05-02: F-cleanup-merge-streak — 「連続 main マージ成功カウント」廃止

### 背景

F-state-protocol (2026-05-01) で CURRENT_STATE.md と BATCH_PROTOCOL.md に
「連続 main マージ成功カウント」を導入したが、F-state-protocol-supplement /
F-doc-backfill / F-doc-backfill-supplement の 3 連続バッチで Claude Code が
この数値を Task 5 で更新し忘れる事象が発生 (CURRENT_STATE.md は 11 連続のまま、
実際は 15 連続に達していた)。

カズヤとの議論 (2026-05-02) で指標自体の意味を再検討した結果、無意味と判定。

### 議論

- **指標の意義**:
  - 案 A: 「N 連続成功」は進捗の可視化として価値がある → 不採用
    - 反論: 12 連続と 100 連続で何が違うのか? どんな行動を取るべきかの
      判断材料にならない
  - 案 B: 品質保証は別の指標で担保されているため、連続カウントは情報ノイズ → 採用
    - baseline 1315 passed と試運転動画化率が真の品質指標
    - マージ成功 = 品質保証ではない (動画品質が低くても、コンセプトが崩れても、
      マージ自体は成立する)

- **悪いインセンティブのリスク**:
  - 「カウントを途切れさせたくない」という無意識の動機が、本来やるべき
    大胆な変更や思い切ったロールバックを避けさせる方向に作用する可能性
  - これはカズヤ哲学「動くものを壊さない」とは別の話 (動くものを壊さない
    のは「機能する既存挙動の保護」、連続カウント維持は「数値の保護」で
    本質的に意味が違う)

- **形骸化の予兆**:
  - 3 連続バッチで Claude Code が更新し忘れた事実は、この指標が
    「重要だが見落とされやすい」のではなく「重要じゃないから見落とされる」
    可能性を示唆

### 決定

1. CURRENT_STATE.md から「連続 main マージ成功カウント」項目を完全削除
2. BATCH_PROTOCOL.md の Task 5 仕様から該当言及を完全削除
3. 同時に main HEAD と直近 5 件ログを最新値に更新 (Task 5 実施漏れの回収)
4. DISCUSSION_NOTES.md に「仕組み導入時の機械的踏襲リスク」エントリを追加
   (将来同種の問題を回避する学習材料)

### 結果

- CURRENT_STATE.md がよりシンプルに、重要数値 (main HEAD / baseline /
  Phase / 試運転結果) の視認性が向上
- 悪いインセンティブ (カウント維持のための過度な保守化) が排除
- 「仕組み導入時に既存指標を機械的踏襲する」リスクへの認識が
  DISCUSSION_NOTES に蓄積、将来の F-state-protocol-v2 等で活用可能

### 関連ファイル・コミット

- コミット: (push 後に追記)
- 変更:
  - `docs/CURRENT_STATE.md` (連続成功カウント削除 + main HEAD / 直近 5 件ログ更新)
  - `docs/BATCH_PROTOCOL.md` (Task 5 仕様修正)
  - `docs/DECISION_LOG.md` (本エントリ)
  - `docs/DISCUSSION_NOTES.md` (機械的踏襲リスクエントリ追加)
- 関連: F-state-protocol (連続成功カウント導入元)

---

## 2026-05-03: F-doc-cleanup — F-13 隠れ層の正式昇格 (遡及記録)

### 背景

`src/generation/script_writer.py:951-985` (旧 865-895 行から移動) に存在する
`quality_floor_miss` bypass ロジックは、Hydrangea コンセプト防衛機構の独立した
安全網として機能している。具体的には、`appraisal_cautions` が `[抑制]` で始まる
候補に対して、(1) `editorial_mission_score >= MISSION_SCORE_THRESHOLD`、
(2) `judge_result.publishability_class in {blind_spot_global, linked_jp_global}`、
(3) `analysis_result is not None` のいずれかが満たされれば抑制を上書きして
通過させる。

しかし本ロジックは F-13 本体エントリにも EDITORIAL_MISSION_FILTER_DESIGN.md にも
未記録で、CURRENT_STATE.md の防衛機構表に「⚠️ DECISION_LOG / 設計書未記録」と
注記された状態 (DISCUSSION_NOTES「F-13 ガード quality_floor_miss bypass が
独立した安全網として機能」エントリ) が続いていた。

F-doc-cleanup (2026-05-03) で正式に防衛機構の 5 層目として位置付け、
DECISION_LOG と CURRENT_STATE と EDITORIAL_MISSION_FILTER_DESIGN.md に
明文化することで「忘れ去られた約束」を解消する。

### 議論

- **位置付け案 A**: F-13 本体の一部として扱い、独立層として認めない
  → 不採用。判定主体 (script_writer 側) と発動条件 (3 通りの OR 条件) が独立で、
  Filter (F-1) / Gate (F-2) / Verifier (F-13.B) / FlagshipGate 下流救済 (F-5) と
  並ぶ独立した安全網としての性格が強い

- **位置付け案 B**: 独立した防衛機構の 5 層目として正式昇格 → 採用
  - 根拠: `analysis_result is not None` 条件は「多角的分析が成立している」という
    独立した証拠で、上流ガードとは別系統の判定材料 (analysis レイヤーは
    Filter/Gate/Verifier から独立している)
  - 根拠: `editorial_mission_score >= MISSION_SCORE_THRESHOLD` は F-1 通過条件と
    同じ閾値だが、bypass の発動タイミングが script_writer の最下流 (動画化直前)
    で、上流ガードとは時系列的にも独立
  - 根拠: 5 層目として明文化することで、防衛機構の総覧性が向上し、
    将来の防衛機構改修時の影響範囲が把握しやすくなる

- **F-13 命名の根拠**:
  - 旧 quality_floor_miss ガードは「証拠不足候補を script 生成時に弾く」設計
    だったが、F-13 (2026-04-29 / 3fbfa70) で「Hydrangea ミッション本丸候補は
    抑制を上書きする」設計に再構築された。本ロジックは F-13 本体の一部として
    実装されたため、5 層目として独立記録する際も F-13 隠れ層の名称を維持する

### 決定

1. F-13 隠れ層を防衛機構の正式 5 層目として位置付ける
   (4+1 層から 5 層体系に昇格)
2. CURRENT_STATE.md 防衛機構表の「⚠️」マークを削除し、状態を「✅ 稼働中」に変更
3. EDITORIAL_MISSION_FILTER_DESIGN.md に F-13 隠れ層セクションを追加
   (script_writer.py:951-985 のロジック説明 + 防衛機構との関係)
4. DISCUSSION_NOTES から「F-13 ガード quality_floor_miss bypass が独立した
   安全網として機能」エントリを削除 (DECISION_LOG に昇格、Active 18 → 17)

### 結果

- 防衛機構の総覧性が向上、5 層体系として明文化
- 「忘れ去られた約束」の典型例が解消、F-state-protocol 哲学の実証
- 将来の防衛機構改修時、F-13 隠れ層への影響を漏らさず検討できる構造に
- 実装変更ゼロ (記録のみ、`src/generation/script_writer.py` は参照のみ)

### 関連ファイル・コミット

- コミット: (F-doc-cleanup 一括コミットに統合 — 議論自体は 2026-05-03)
- 変更:
  - `docs/DECISION_LOG.md` (本エントリ)
  - `docs/CURRENT_STATE.md` (防衛機構表 5 層化、「⚠️」削除)
  - `docs/EDITORIAL_MISSION_FILTER_DESIGN.md` (F-13 隠れ層セクション追加)
  - `docs/DISCUSSION_NOTES.md` (該当エントリ削除、Active 18 → 17)
- 参照のみ: `src/generation/script_writer.py:951-985` (実装変更なし)

---

## 2026-05-03: F-doc-cleanup — F-13 (rescue 廃止前提整備) 本体 (遡及記録)

### 背景

試運転 7-J (2026-04-30) で動画化率 0%。Slot-1 候補が JP=0 件で
`requires_more_evidence=True` → rescue 発動 → script skip という挙動が観察され、
これが Hydrangea ミッション「日本で封殺されている海外ニュース」(blind_spot_global) を
skip する本末転倒な設計だと判明した。

旧 quality_floor_miss ガードは「証拠が不足した候補は script 生成段階で
ブロックする」という単純な設計だったが、F-1 (EditorialMissionFilter) や
F-2 (FlagshipGate) で「Hydrangea コンセプト本丸記事」として認められた候補も
同じ条件で弾かれてしまい、上流ガードと矛盾する状態だった。

F-13 本体エントリは DECISION_LOG に未記録のまま、F-13.B (rescue 完全廃止) や
他のバッチ群が積み上がっていた。F-doc-cleanup で遡及記録する。

### 議論

- **案 A**: quality_floor_miss ガードを完全撤去し、`appraisal_cautions=[抑制]` でも
  全部通す → 不採用。既存の品質保証 (証拠不足候補のブロック) が機能しなくなる

- **案 B (採用)**: ガードは残しつつ、Hydrangea コンセプト本丸記事は抑制を
  上書きする bypass 経路を追加
  - bypass 発動条件: 以下の OR
    - `editorial_mission_score >= MISSION_SCORE_THRESHOLD`
      (F-1 通過レベルの編集ミッション適合度)
    - `judge_result.publishability_class in {blind_spot_global, linked_jp_global}`
      (F-2 / FlagshipGate 通過判定)
    - `analysis_result is not None`
      (AnalysisLayer で多角的分析が成立)
  - bypass 発動時は WARNING ログで可視化 (`[F-13] quality_floor_miss bypass`)

- **rescue path との関係**: F-13 完了時点では rescue path (judge rescue) が
  まだ稼働中。F-13 は「script_writer 側のガード」、rescue は
  「main.py 側の judge rescue 分岐」で別系統。ただし両者が連動して動画化を
  阻害するケースが続いており、最終的には F-13.B (2026-05-01) で rescue 完全廃止に至る

### 決定

`src/generation/script_writer.py` の quality_floor_miss ガードを再設計し、
Hydrangea コンセプト本丸記事は bypass する経路を追加。実装は
`script_writer.py:951-985` (現行行番号) に集約。

### 結果

- F-13 完了直後の試運転 7-K (2026-05-01) で 3/3 Slot 動画化成功 (FIFA + Gaza×2)
- ただし rescue path は依然稼働中で、F-13.B (2026-05-01) で完全廃止に至る
- F-13 隠れ層は 5 層目の防衛機構として後日 (本バッチ) 正式昇格

### 関連ファイル・コミット

- コミット: 3fbfa70 (2026-04-29 13:09 +0900) — feat: redesign quality_floor_miss
  guard for Hydrangea concept (F-13)
- 変更:
  - `src/generation/script_writer.py` (quality_floor_miss bypass 追加)
- 関連:
  - F-13.B (2026-05-01 b950813) で rescue path 完全廃止
  - F-13 隠れ層の正式昇格は F-doc-cleanup (2026-05-03) で実施

---

## 2026-05-03: F-doc-cleanup — F-13.B (JpCoverageVerifier + rescue 完全廃止) 本体 (遡及記録)

### 背景

F-13 (2026-04-29) で quality_floor_miss bypass を追加したが、main.py の
`_write_judge_rescue()` 経由の rescue path (judge_report.json /
followup_queries.* 出力 + script skip) は依然稼働しており、Slot-1 候補が
JP=0 件のとき rescue 発動で動画化が止まる事象が継続していた。

これは Hydrangea ミッション「日本で封殺されている海外ニュース」(blind_spot_global) を
skip する設計矛盾の温存。さらに F-13-A (JP RSS 13 媒体拡張、c9502d0) でも
ニッチ海外ニュース (Gaza 電力危機等) は依然 JP ソース 0 件のケースが残ることが
判明し、RSS 取得漏れと「真の日本未報道」を区別できない構造的問題が顕在化。

### 議論

- **案 A**: rescue を維持しつつ閾値を緩和 → 不採用。Hydrangea ミッション本丸の
  blind_spot_global を skip する根本矛盾は解消されない

- **案 B (採用)**: rescue path を完全廃止 + 「日本未報道」の Web 検証経路を新設
  - rescue 完全廃止: `_write_judge_rescue()` 関数と main.py 内 rescue 分岐を撤去。
    `is_rescue_candidate` 判定ロジックは src/triage/gemini_judge.py 側に残置
    (不変原則 3 遵守) しつつ main.py から呼ばない
  - JpCoverageVerifier 新設: Gemini Grounding (Google Search) で日本語検索、
    27+ ドメインホワイトリスト (新聞・テレビ・通信社・主要ビジネスメディア) と
    除外リスト (Yahoo!ニュース・SNS・個人ブログ等) で照合。判定基準は
    「大手メディアの報道有無のみ」(個人投稿は判定材料にしない、Hydrangea の
    ミッション本丸: 大手の空白を埋める)。24h SQLite キャッシュ
    (`jp_coverage_cache` テーブル新設) で重複検証抑制、月コスト約 $4.2 想定
  - Grounding API エラー時の安全側倒し: `has_jp_coverage=True` で
    動画化を止める (誤って「日本未報道」と判定するリスクを回避)

- **不変原則 3 との整合**: src/triage/ の既存ファイルは触らず、
  `jp_coverage_verifier.py` を新規追加。`_write_judge_rescue()` は
  src/main.py 側の関数で、main.py は不変原則対象外

### 決定

1. rescue path 完全廃止 (`_write_judge_rescue()` + main.py の rescue 分岐撤去)
2. JpCoverageVerifier 新設 (Gemini Grounding + 27 ドメイン WL +
   24h キャッシュ + 安全側倒し)
3. 環境変数: `JP_COVERAGE_VERIFIER_ENABLED` /
   `JP_COVERAGE_CACHE_HOURS` / `JP_COVERAGE_GROUNDING_MODEL`
4. テスト 36 件追加 (`tests/test_f13b_rescue_abolition.py`)

### 結果

- 試運転 7-K (2026-05-01) で 3/3 Slot 動画化成功 (FIFA + Gaza×2)
- Slot-2 (cls-33b4f4960bf9) と Slot-3 (cls-204a683f73ee) で
  `has_jp_coverage=False` を確認、blind_spot_global として動画化フローへ進行
- judge_report.json / followup_queries.* の新規出力なし (既存ファイルは履歴として残置)
- rescue 廃止後初の全 Slot 動画化成功
- 防衛機構の正式 4 層目として CURRENT_STATE.md に登録

### 関連ファイル・コミット

- コミット: b950813 (2026-05-01 12:08 +0900) — feat: abolish rescue path +
  add JP major media Web verification (F-13.B)
- 関連: 800a01f (2026-05-01) — fix: align baseline test expectations with
  F-16-A / F-13.B design
- 変更:
  - `src/triage/jp_coverage_verifier.py` (新規)
  - `src/storage/db.py` (jp_coverage_cache テーブル追加)
  - `src/main.py` (rescue 分岐撤去 + Web 検証統合)
  - `src/shared/config.py`
  - `.env.example`
  - `tests/test_f13b_rescue_abolition.py` (新規 36 テスト)

---

## 2026-05-03: F-doc-cleanup — F-15 (Slot-event_id 同期) 本体 (遡及記録)

### 背景

試運転 7-H' (2026-04-29 21:20) で動画化率 1/3 (33%) で頭打ちが発覚。
原因は AnalysisLayer 対象選定ループと Top-3 台本生成ループが別の event_id 列を
対象にしていたこと:

- AnalysisLayer 対象: `all_ranked[:_top_n_for_analysis]` (Tier 1 score 降順)
- Top-3 台本生成: `sorted(all_ranked, key=lambda se:
  _elite_judge_results[...].total_score, reverse=True)[:_top_n_for_analysis]`
  (Elite Judge total_score 降順)

両ループでスコア基準が異なるため、特定の Slot で
「analysis_result is None, skipping」が発生し、Slot-2 / Slot-3 が動画化失敗。
構造的に Slot-event_id がズレる問題で、実装の不整合だった。

### 議論

- **案 A**: AnalysisLayer 対象を増やして両方のスコア順をカバー → 不採用。
  AnalysisLayer の LLM コストが線形増加する

- **案 B (採用)**: AnalysisLayer 対象を Top-3 台本生成と同じ Elite Judge
  total_score 降順に揃える
  - 根拠: 動画化されるのは Top-3 (Elite Judge total_score 降順) なので、
    AnalysisLayer も同じ順序で選定するのが筋
  - 副作用: Tier 1 score では低位だが Elite Judge では上位の event が
    AnalysisLayer 対象になる。これは品質的にも妥当 (Elite Judge は最上流のジャッジ)

- **不変原則との整合**: src/main.py は不変原則対象外、変更可能

### 決定

`src/main.py` の AnalysisLayer 対象選定を Elite Judge total_score 降順に変更。
両ループが必ず同じ event_id 列を対象とするよう同期。

### 結果

- 試運転 7-I (2026-04-29) で動画化率 67% (2/3) に改善
- Slot-3 (UAE OPEC) は AnalysisLayer 完了済みだったが
  MAX_PUBLISHES_PER_DAY=5 で skip → F-16-A の発見につながる
- 構造的な Slot-event_id ズレが解消、AnalysisLayer 完了 = 動画化対象が成立

### 関連ファイル・コミット

- コミット: c573df8 (2026-04-29 23:09 +0900) — fix: align AnalysisLayer
  target selection with Top-3 generation loop (F-15)
- 変更:
  - `src/main.py`
  - `tests/test_main_f15_slot_event_sync.py`

---

## 2026-05-03: F-doc-cleanup — F-16-A (per-run 上限分離 + MAX_PUBLISHES_PER_DAY 撤廃) 本体 (遡及記録)

### 背景

試運転 7-I (2026-04-29) で動画化率 67% (2/3) で頭打ち。Slot-3 (UAE OPEC) は
AnalysisLayer 完了済みだったが `MAX_PUBLISHES_PER_DAY=5` のハードコード制限で
skip された。

`MAX_PUBLISHES_PER_DAY` は Phase 1 の単発 PoC 時代の設計で「1 日の公開上限」を
グローバルに制御していたが、Phase A.5 以降は cron 6 時間おき自動実行 (1 日 4 run) の
本番運用が前提になり、per-run 上限と per-day 上限の概念が混乱していた。

### 議論

- **案 A**: MAX_PUBLISHES_PER_DAY を引き上げる → 不採用。設計上の混乱が残る

- **案 B (採用)**: per-run 上限と per-day 上限を分離
  - `TOP_N_VIDEOS_PER_RUN` (default 1) — 1 run で生成する動画数
  - `TOP_N_ARTICLES_PER_RUN` (default 3) — 1 run で生成する記事数
  - `MAX_PUBLISHES_PER_DAY` は default 999 に変更し実質撤廃
    (後方互換のため env / コードからは読み続ける)
  - cron 自動実行 (F-16-B) と組み合わせて公開頻度を制御
  - 本番運用想定: 4 run/日 × 1 動画 = 4 動画/日 + 4 run × 3 記事 = 12 記事/日

- **video > article クランプ**: video 数が article 数を超える設定は不整合
  なので min クランプして警告

- **AnalysisLayer Top 3 対象 (F-15) との整合**: AnalysisLayer は Top 3 全部で動かし、
  動画化は Slot index >= TOP_N_VIDEOS_PER_RUN は article のみ生成

- **publish_count インクリメント**: 後方互換のため維持
  (将来の per-day 上限復活に備える)

### 決定

1. `TOP_N_VIDEOS_PER_RUN` / `TOP_N_ARTICLES_PER_RUN` 環境変数を新設
2. `_generate_outputs()` に `generate_video_track: bool = True` パラメータ追加
3. `MAX_PUBLISHES_PER_DAY` を default 999 に変更 (実質撤廃)
4. テスト 26 件追加 (`tests/test_f16a_per_run_limits.py`)

### 結果

- 試運転 7-J (2026-04-30) でも依然動画化率 0% を観測 (rescue 発動が原因) →
  F-13.B のトリガー
- per-run / per-day の概念分離で、cron 自動実行 (F-16-B) の設計が明確化
- Phase 1-A で `ChannelConfig.publishing_limits` に統合予定
  (FUTURE_WORK 緊急度高)

### 関連ファイル・コミット

- コミット: 192eeaf (2026-04-30 00:44 +0900) — feat: separate per-run
  video/article limits (F-16-A, root-cause fix)
- 変更:
  - `src/shared/config.py`
  - `src/main.py`
  - `.env.example`
  - `tests/test_f16a_per_run_limits.py` (新規 26 テスト)

---

## 2026-05-03: F-doc-cleanup — F-12-A (article-first 順序逆転) 本体 (遡及記録)

### 背景

試運転 7-D (2026-04-28) で「アーティクル品質が東洋経済オンライン超え」評価を
得たが、台本 (script.json) は文字数制約とブロック分割で表現が硬くなりがちだった。
具体例として、アーティクルが「移動する主権領土」のような独自言語化を含むのに対し、
台本は「物理的限界に達している構造的変化を象徴」のような平凡な表現になっていた。

根本原因は生成順序: `script → article` だったため、台本生成時にアーティクルの
独自フレーズが存在せず、台本が独自言語化を獲得できなかった。

### 議論

- **案 A**: 台本生成プロンプトに「金フレーズ」を直接埋め込む → 不採用。
  プロンプトハードコードでバッチごとに更新が必要、保守性が低い

- **案 B (採用)**: 順序逆転 (`article → script`) を実施し、
  台本生成時にアーティクル本文を参考素材として渡す
  - article.markdown を script_writer に `article_text` 引数で参照素材として渡す
  - article_writer.py は不変原則 1 で touch しない
  - script_writer.py は新ルート (`generate_script_with_analysis`) のみ改修、
    既存ルート (`write_script` / `_PROMPT_TEMPLATE` / `_build_script_from_llm`) は
    不変原則 2 で触らない

- **F-12-B との関係**: F-12-A は順序逆転の基盤整備のみ。実際の台本品質改善
  (script_writer プロンプト全面刷新) は F-12-B (= F-12-B-1 / F-12-B-1-extension) で実施

### 決定

`src/main.py` の生成順序を `script → article` から `article → script` に逆転。
article.markdown を script_writer に `article_text` 引数で渡す基盤を整備。
article_writer.py は不変 (プロンプト・シグネチャ・入力素材いずれも touch しない)。

### 結果

- 試運転 7-F (2026-04-29) でアーティクル品質維持を確認
- F-12-B (= F-12-B-1) で script_writer プロンプト全面刷新を着手する基盤が整う
- 不変原則 1 / 2 を完全遵守 (article_writer.py / script_writer.py 既存ルート無改修)

### 関連ファイル・コミット

- コミット: f199834 (2026-04-29 01:56 +0900) — feat: invert generation
  order (article → script) for F-12-A
- 変更:
  - `src/main.py` (生成順序逆転)
  - `src/generation/script_writer.py` (新ルートに `article_text` 引数追加)

---

## 2026-05-03: F-doc-cleanup — F-12-B (script_writer サマリ型台本刷新) 本体 (遡及記録)

### 背景

F-12-A (2026-04-29) で生成順序を逆転し、台本生成時にアーティクルを参考素材として
渡す基盤が整った。次の段階として、script_writer プロンプト全面刷新が必要だった。

試運転 7-K (2026-05-01) の baseline 台本 (cls-7bd1406438b6 FIFA 提訴 /
cls-579833967531 フーシ派) で、カズヤから 6 個の問題が指摘された
(略しすぎ「イスラエル入植地クラブ」/補足なし「スポーツ仲裁裁判所」/
不明「ロシア侵攻時の即時排除」/直訳「公然たる支持」/
抽象比喩「地政学的断層」「直撃弾」/硬い文語「発動」「ツール」)。

`configs/prompts/analysis/geo_lens/script_with_analysis.md` を分析した結果、
「扇動・陰謀論の禁止」(STEP 3) は強力だが「視聴者へのわかりやすさ」への配慮が
皆無で、LLM が「教科書っぽい硬い分析調」に寄っていた。

### 議論

- **案 A**: NG リスト方式で禁止表現を Tier 1〜3 で機械的に管理 → 不採用
  (クラウド誤り 1: NG リスト・Tier 分類で機械制御提案、カズヤから
  「無理だから、考え方で制御したい」で軌道修正)

- **案 B**: 「優れた具体例 A/B/C」を提示 + 「こう書きなさい」テンプレ 5 個 → 不採用
  (クラウド誤り 2: テンプレ過剰押し付け、カズヤから「いちいち制御する話じゃない、
  感想だよ」で軌道修正)

- **案 C (採用)**: 「視聴者ファースト原則」(姿勢として記述、判断は LLM の知性に委ねる)
  - 3 原則: 聞いてわかる / 抽象より具体 / 読み上げて自然
  - 合格基準: TikTok/Shorts で違和感なく聞けるか
  - NG リストではなく姿勢として記述、既存セクションは一切変更せず追加のみ
  - F-12-B-1 (2026-05-01) で実施

- **F-12-B-1-extension の追加**: F-12-B-1 完了後の試運転で punchline 末尾に
  抽象比喩の癖が残存することが観察された (「地政学の檻に閉じ込める」「冷徹な力学」)。
  根本原因は STEP 2 punchline 定義「シニカルかつ知的な余韻」が抽象詩を呼び込んでいた
  ことと、例示「綺麗事を信じた側が損をする」が STEP 3 禁止表現と矛盾していたこと。
  F-12-B-1-extension で STEP 2 punchline 定義を「シニカル × 具体着地の両立」に
  改訂、優れた例「秩序を信じる代償を、私たちは電気代という形で支払うことになる」を
  併記、矛盾していた例を削除

- **不変原則 2 との整合**: F-12-B 系は configs/prompts/ 配下の改修のみで、
  script_writer.py 既存ルートは無改修。不変原則 2 完全遵守

### 決定

F-12-B 本体は 2 段階で実施:
1. F-12-B-1 (535f8e0、2026-05-01 15:22): 視聴者ファースト原則を STEP 3 直前に追加
2. F-12-B-1-extension (4db3335、2026-05-01 15:45): STEP 2 punchline 定義を
   「シニカル × 具体着地」両立化に改訂

### 結果

- 試運転 (cls-56c4197b6fd2 米イスラエル隠密作戦) で「中東独立メディアの
  ミドル・イースト・アイ」のような固有名詞補足、「動かしたんです」「ある日突然」の
  ような話し言葉的接続を確認
- char validation で 1 リトライ発生 (setup=94→82 字)、F-12-B-1.5
  (文字数制約緩和) を緊急度中に新設して継続観察項目化
- F-12-B-1-extension は LLM 出力依存のため試運転は未実施 (時間と再現性を考慮、
  必須化せず継続観察項目)
- 当初想定の旧 F-12-B-1 (blind_spot_global 用フレーム追加) は試運転 7-K の
  結果を受けて視聴者ファースト原則の方が優先と判断され、スコープを再定義

### 関連ファイル・コミット

- コミット (F-12-B-1): 535f8e0 (2026-05-01 15:22 +0900) — feat: add viewer-first
  editorial stance to script prompt (F-12-B-1)
- コミット (F-12-B-1-extension): 4db3335 (2026-05-01 15:45 +0900) — feat:
  refine punchline definition for cynical+grounded balance (F-12-B-1-extension)
- 変更:
  - `configs/prompts/analysis/geo_lens/script_with_analysis.md`
    (視聴者ファースト原則追加 + STEP 2 punchline 定義改訂)
  - `docs/BATCH_PROTOCOL.md` (不変原則 2 例外条項を `configs/prompts/` 全般に拡大)

---

## 2026-05-03: F-doc-cleanup — F-14 (AnalysisLayer JSON parser 堅牢化) 本体 (遡及記録)

### 背景

試運転 7-G (2026-04-29) で Slot-1 (cls-8bbec722d420 Venezuela) の
AnalysisLayer 出力が JSON parse エラーで `analysis_result=None` になる事象が発生。
LLM 出力が途中で切れた (max_tokens 制限 / Tier フォールバック中の長い応答) ことが
直接原因。

`analysis_result=None` は AnalysisLayer 全体の動画化阻害につながるため
(Slot ごとの AnalysisLayer は独立して動くが、Top 3 全体での品質保証が崩れる)、
JSON parse 失敗時の救済ロジックが必要だった。

### 議論

- **案 A**: max_output_tokens の明示指定 + プロンプト改修で根本対処 → 中長期対応
  (FUTURE_WORK 「AnalysisLayer LLM の max_tokens / 切れ防止」として登録、
  発動頻度確認後に着手判断)

- **案 B (採用、対症療法)**: JSON parser に修復ロジックを追加
  - 末尾の不完全な JSON フラグメントを検出し、可能な限り補完
  - 補完不可能な場合は途中まで parse できた構造を返す
  - 修復発動時は WARNING ログで可視化 (`[F-14] JSON repaired`)
  - 根本原因 (LLM 出力途中切断) は別途 FUTURE_WORK で追跡

- **対症療法と認識して登録**: F-14 は対症療法と明示し、根本対応 (max_tokens
  明示指定 + プロンプト改修) を FUTURE_WORK 緊急度高に登録。発動頻度を
  試運転 7-H で確認後、根本対応着手を判断する運用ルール

- **不変原則 4 との整合**: src/analysis/ 配下を変更するため、不変原則 4
  「analysis 触らない」と衝突するが、JSON parser の堅牢化は parse ロジックの
  不具合修正に該当 (axis 変更や設計改修ではない) ため、本質的な原則違反ではない

### 決定

`src/analysis/` 配下の JSON parser に修復ロジックを追加。発動頻度に応じて
FUTURE_WORK 緊急度高エントリ「AnalysisLayer LLM の max_tokens / 切れ防止」で
根本対応を判断する運用ルール化。

### 結果

- 試運転 7-G で `analysis_result=None` が解消、Slot-1 動画化が進行
- ただし `extract_perspectives()` のルールベース判定が厳しすぎる別事象は
  本対応の範囲外 (FUTURE_WORK「perspective_extractor 改善 (F-7-α 候補)」で別途追跡)
- F-14 は対症療法という性格を DECISION_LOG に明記することで、後続バッチで
  根本対応に着手する判断材料が時系列で残る

### 関連ファイル・コミット

- コミット: c93a8bb (2026-04-29 17:26 +0900) — feat: add JSON repair logic to
  AnalysisLayer parser (F-14)
- 変更:
  - `src/analysis/` 配下の JSON parser
- 関連:
  - FUTURE_WORK 緊急度高「AnalysisLayer LLM の max_tokens / 切れ防止」(根本対応)
  - FUTURE_WORK 緊急度高「perspective_extractor 改善 (F-7-α 候補)」(別事象)

---

## 2026-05-03: F-doc-cleanup — Phase B 方向性整理 + 拡張性原則の力点確定 + verify 順序見直し

### 背景

2026-05-03 のカズヤ x クラウド議論で Phase A.5-3a-verify 着手前の方針整理を実施。
新チャット移行時に同種の議論を繰り返さないため、議論結果を docs に反映する必要があった。

具体的論点:
1. Phase B 以降の方向性 (5 シナリオ並立だった当初整理を 3 択構造に縮約)
2. Phase A.5-3c 拡張性原則の力点 (4 項目から 2 項目に集約)
3. Phase A.5-3a-verify 順序 (4 つ全部完了 → 3b の当初計画を、性格別に並走可能な
   構造に修正)

### 議論

#### 1. Phase B 以降の方向性

- **当初整理 (DISCUSSION_NOTES 2026-05-02)**: シナリオ A〜E の 5 並立
  - A: japan_athletes / k_pulse 展開
  - B: 政治・経済細分化
  - C: 動画継続 + 独自メディア並行
  - D: 動画縮小 + 独自メディア軸足
  - E: SaaS 化

- **2026-05-03 議論で確定**: 本命 + 3 択に縮約
  - 本命: geo_lens 動画自動投稿 (Phase A.5-3d) を完成 → 安定稼働
  - その先の選択肢 (運用結果次第):
    - 動画継続 (geo_lens の TikTok / YouTube Shorts 投稿を主軸として継続)
    - 独自メディア (Web / Substack / note 等への記事配信展開)
    - 手動 note・LinkedIn 投稿 (完全自動化を諦めるオプション、新チャネルは
      手動から始める柔軟性確保)
  - japan_athletes / k_pulse / カテゴリ細分化 / SaaS 化は明示的選択肢から後退
    (運用結果次第で再浮上の可能性は残す)

#### 2. Phase A.5-3c 拡張性原則の力点

- **当初 (F-doc-backfill-supplement 2026-05-02)**: 4 項目の拡張性原則
  - ChannelConfig YAML 化
  - Publisher 抽象
  - Content Format 抽象化
  - Audio/Image/Video Renderer 抽象化

- **2026-05-03 議論で確定**: 2 項目に集約
  - ChannelConfig YAML 化 (必要)
  - Publisher 抽象 (必要)
  - Content Format 抽象化は不要 (記事は既に高品質 Markdown で出ているため、
    Web メディアは UI に流し込むだけで足りる)
  - Audio/Image/Video Renderer 抽象化は Phase A.5-3c 各統合バッチで
    「抽象化 + 実装」をセット実施 (前倒し却下)

- **クラウド誤り 6 (新規記録)**: 過剰拡張性の罠
  - 2026-05-03 議論でクラウドが「シナリオ C/D には Content Format 抽象化と
    Publisher 抽象が必要」と提案
  - カズヤから「記事は既に高品質 Markdown で出ているので、Web メディアは
    UI に流し込むだけ。Content Format 抽象化は不要、Publisher 抽象だけで足りる」
    で訂正
  - 教訓: 「将来の柔軟性のため」と称して抽象化レイヤーを増やすと、
    各シナリオで本当に必要な抽象化を見誤る
  - 抽象化の必要性は「実装先が存在するか」で判断する
    (Publisher は実装先複数、Content Format は実装先 1 つしかないので不要)
  - 構造的防止策として Task F (拡張性差し込み判断ルール) を BATCH_PROTOCOL に追加

#### 3. Phase A.5-3a-verify 順序

- **当初 (F-state-protocol-supplement 2026-05-02)**: 4 つ全部完了 → 3b
  - F-verify-jp-coverage / F-verify-perspective / F-verify-script-quality /
    F-image-prompt-spec を全部通過してから Phase A.5-3b 着手

- **2026-05-03 議論で確定**: 性格別の最適タイミングに分解
  - 1st: F-verify-jp-coverage (★最優先、ゲート / 防衛機構の中核)
  - 2nd: Phase A.5-3b 着手 (image-prompt-spec を 3b の最初の作業に組み込み)
  - 並走: F-verify-perspective / F-verify-script-quality
    (3b/3c 中にデータ収集、判断は 3b/3c 完了後)
  - 根拠: 4 つの verify が同じ性格ではなく、ゲート (jp-coverage) /
    3b 前提 (image-prompt-spec) / データ収集 (perspective / script-quality) の
    3 種類に分かれる。性格別に最適タイミングが違う

### 決定

1. DISCUSSION_NOTES「Phase B 以降の方向性未確定」エントリを 3 択構造に更新
2. DISCUSSION_NOTES にクラウド誤り 6「過剰拡張性の罠」を新規追加
3. FUTURE_WORK の Phase A.5-3a-verify セクションを順序見直しに合わせて更新
4. CURRENT_STATE.md「次バッチ候補」を新順序に全置換更新
5. BATCH_PROTOCOL.md に「拡張性差し込み判断ルール」セクション新設 (Task F)

### 結果

- 別チャット移行時に同種の議論を繰り返さない構造確保
- Phase A.5-3c 着手時の力点が明確化、過剰設計を構造的に防ぐ
  (BATCH_PROTOCOL「拡張性差し込み判断ルール」で運用ルール化)
- Phase A.5-3b 着手が verify 4 つ全通過待ちから 1 つ通過後に前倒し可能に

### 関連ファイル・コミット

- コミット: (F-doc-cleanup 一括コミットに統合 — 議論自体は 2026-05-03)
- 変更:
  - `docs/DISCUSSION_NOTES.md` (Phase B エントリ更新 + クラウド誤り 6 追加)
  - `docs/FUTURE_WORK.md` (Phase A.5-3a-verify セクション更新)
  - `docs/CURRENT_STATE.md` (次バッチ候補刷新 + 防衛機構表 5 層化)
  - `docs/BATCH_PROTOCOL.md` (拡張性差し込み判断ルール新設)
  - `docs/DECISION_LOG.md` (本エントリ + Task A エントリ + Task B 7 エントリ)

## 2026-05-03: F-doc-cleanup-followup — 議論結果反映 + コアミッション 2 系統並立の docs 化

### 背景

F-doc-cleanup (e34f36e、main マージ 3e817d8、2026-05-03) 完了直後、カズヤとの議論で
3 つの追加判断が確定:
1. 大規模調査機能 (オンデマンド深掘りパイプライン) を Phase B 以降の新選択肢として登録
2. ★最重要: Hydrangea コアミッション 2 系統並立の明示的訂正
3. クラウド誤り 7: 系統 1 中心理解で系統 2 を過小評価する誤りパターン

これらは F-doc-cleanup のスコープ外で、別バッチで反映する必要があった。
カズヤの哲学「忘れ去られた約束を絶対忘れない仕組み」に従い、議論結果を文書層で
完全に固定化する。

### 議論

- **案 A**: F-doc-cleanup 内で対応する → 不採用 (F-doc-cleanup 投入中に議論が発生、
  スコープ拡張は適切でない)
- **案 B (採用)**: F-doc-cleanup-followup として独立した小バッチで対応
  - メリット: F-doc-cleanup の差分が綺麗、責務分離
  - デメリット: バッチ数が増える (許容範囲、文書追加のみで 30 分〜1 時間)

- **CURRENT_STATE.md への反映方法**:
  - 案 i: 既存セクション「7. カズヤの直近フィードバック要点」に項目追加 → 不採用
    (最重要事項にしては埋もれる)
  - 案 ii (採用): 新セクション「0. Hydrangea コアミッション (2 系統並立)」を冒頭追加
    - 新しいクラウドが最初に読んで認識を固める構造
    - 既存セクション 1-8 の番号は変更せず維持 (リナンバーしない)

### 決定

1. DISCUSSION_NOTES.md に 3 エントリ追加 (Active 18 → 21)
2. CURRENT_STATE.md 冒頭に新セクション「0. Hydrangea コアミッション (2 系統並立)」を追加
3. BATCH_PROTOCOL Task 1-5 を本バッチ自身に適用 (ドッグフーディング)

### 結果

- 別チャット移行時、新しいクラウドが CURRENT_STATE.md の冒頭でコアミッション 2 系統
  並立を読む構造を確保
- クラウド誤り 7 が独立エントリとして記録、再発防止の構造化完了
- 大規模調査機能 (Phase B 以降の新選択肢) が文書化、忘却リスクゼロ
- リグレッション影響なし (docs/ のみ変更、src/ tests/ configs/ CLAUDE.md は 0 行変更、
  baseline 1315 passed 維持)

### 関連ファイル・コミット

- コミット: (push 後に追記)
- 変更:
  - `docs/DISCUSSION_NOTES.md` (3 エントリ追加 = Active 18 → 21、最終更新日更新)
  - `docs/CURRENT_STATE.md` (新セクション「0. Hydrangea コアミッション (2 系統並立)」
    を冒頭追加、最終更新日更新、末尾注記に本バッチ概要追記)
  - `docs/DECISION_LOG.md` (本エントリ)
  - `docs/FUTURE_WORK.md` (本エントリを完了済みに追加)
- 関連: F-doc-cleanup (e34f36e、main マージ 3e817d8) — 本バッチの前提となる文書整地バッチ

---

## 2026-05-03: F-verify-jp-coverage-golden — F-13.B 精度測定用ゴールデンセット作成 (2 段階分割の第 1 段階)

### 背景

F-verify-jp-coverage は Phase A.5-3a-verify の最優先ゲートとして FUTURE_WORK
緊急度 高に登録済み (F-state-protocol-supplement / 2026-05-02)。
F-13.B JpCoverageVerifier の precision/recall を実データで測定し、Hydrangea
コンセプト防衛機構の中核 (rescue 完全廃止後の唯一の JP 報道判定経路) の
信頼性を担保する位置付け。

ゴールデンセットの品質が F-verify-jp-coverage 全体の信頼性を決めるため、
本バッチでは独立にゴールデンセット 20 件 (blind 10 + covered 10) を作成し、
カズヤがレビューしてから次バッチ (F-verify-jp-coverage-measure) で実際の
精度測定を行う 2 段階構成を採用した。

### 議論

- **単一バッチ (golden + measure を同一バッチ) vs 2 段階分割**:
  - 単一バッチ案: 1 度の作業で完結、バッチ数が少ない、ゴールデンセット作成と
    測定の文脈を保持できる
  - 2 段階分割案 (採用): Task A の判断密度が高い (20 件全件で region/topic/tier
    多様性の判断 + 各件の独立 Web 検証 + 真値判定の確定)。ゴールデンセットは
    F-13.B 精度測定の真値となるため、measure 投入前にカズヤレビュー機会を
    持つ価値が高い。間違ったゴールデンセットで measure を回すと結果も
    間違う構造的リスク
  - → 2 段階分割を採用

- **真値判定の独立性確保**:
  - F-13.B 自体を呼んで「F-13.B が False と言ったから expected も False」と
    すると自己参照になり精度測定の意味がない
  - WebSearch ツールで Claude Code が独立に日本語検索 (例: タイトル + 'NHK
    朝日 日経' 等) を実行し、JP_MEDIA_WHITELIST Tier 1-4 ドメイン直接報道の
    有無を確認する方式を採用
  - F-13.B の jp_coverage_cache に残る過去判定 (6 件) は参考情報として
    `f13b_prior_verdict` フィールドに併記するが、expected_has_jp_coverage の
    真値は独立検証結果に基づく

- **blind 候補の選定方針**:
  - 案 i: F-13.B が `has_jp_coverage=False` 判定したものだけを使う → 6 件しか
    存在せず 10 件に届かない、かつ中東バイアスが極端
  - 案 ii (採用): F-13.B 過去判定 6 件 + 過去試運転 evidence.json から
    has_jp_view=0.0 + coverage_gap_score>=6.0 + sources.jp=[] を満たす
    候補をヒューリスティック抽出 (18 件) → そこから region/topic 多様性を
    考慮して 10 件選定
  - 結果: 中東バイアス (10 件中 7-8 件) は試運転期 (4-5 月) の世界的ニュース
    流通自体がホルムズ封鎖・ガザ等中東情勢中心であった構造的反映として
    diversity_check.bias_note に明記

- **覆われた事象 10 件の選定方針**:
  - F-13.B 自身の判定結果 (has_jp_coverage=True 出力) を使うと自己参照
  - WebSearch で 2026 年 4-5 月の主要国際ニュース (Trump-Hormuz / Russia-Ukraine
    停戦交渉 / 米中関税 / 教皇レオ 14 世警告 / Lula-Amazon / NVIDIA / Boko
    Haram / Mali 国防相殺害 / India-Pakistan Kashmir / フーシ-イラン支援表明)
    を検索し、JP_MEDIA_WHITELIST Tier 1-4 直接報道 URL を確認

- **Tier 2-4 only テストケースの確保**:
  - 仕様要求: Tier 1 ≥ 5、Tier 2-4 only ≥ 2
  - 達成: Tier 1 = 9 件、Tier 2-4 only = 1 件 (フーシ-イラン支援表明、Bloomberg
    JP T2 + Newsweek JP T4 + Jiji T2)
  - 1 件不足の理由: 国際大ニュースは Tier 1 (NHK / 日経) でほぼ必ず報道
    されるため、Tier 2-4 のみの事象を多数確保するのは構造的に困難
  - diversity_check.tier_2_4_only_deviation_note に明記、次バッチで追補可能性

- **kazuya_review_required_ids の発生**:
  - 5 件 (blind_002 / 004 / 005 / 006 / 009) で「広範な事件は Tier 1 報道あり、
    MEE 記事の核心 (特定の構造分析角度) は未報道」というパターンが共通発生
  - F-13.B の動作仕様 (タイトル全体の事件 vs 特定角度の判定基準) によって
    expected_has_jp_coverage の真値が False/True に分岐する可能性あり
  - カズヤレビューで真値を確定してから次バッチ起動の前提

### 決定

1. `docs/runs/F-verify-jp-coverage/golden_set.json` を新規作成
   - blind 10 件 + covered 10 件
   - 各 entry に title / summary / expected_has_jp_coverage / expected_tier
     / source_run / topic_category / region / volume_in_jp /
     manual_verification_note / manual_verification_urls
   - blind 6 件は f13b_prior_verdict 併記 (F-13.B 過去キャッシュからの参考情報)
   - diversity_check (region / topic / tier / volume) + bias_note 完備
   - kazuya_review_required_ids 5 件明示 + kazuya_review_summary に共通
     パターン記述
   - next_batch_handoff に F-verify-jp-coverage-measure の期待 input/output
     とカズヤレビューゲートを定義

2. F-13.B 自体は呼ばず、Claude Code が WebSearch で独立に日本語検索して
   真値判定 (F-13.B 過去判定は参考情報として併記のみ)

3. 中東バイアス (blind 10 件中 7-8 件 ME) は試運転データ自体の構造的反映
   として診断コメント明記、矯正のための差し替えは行わない (実運用データに
   即した評価を優先)

4. Tier 2-4 only 不足 (仕様要求 ≥2 に対して 1 件) は明示的偏差として
   diversity_check に記録、次バッチで追補可能性を残す

5. 本バッチは中間成果物のため BATCH_PROTOCOL Task 1-5 ドッグフーディングは
   軽量版で実施 (DECISION_LOG / FUTURE_WORK / DISCUSSION_NOTES /
   CURRENT_STATE 更新は通常通り、CLAUDE.md は変更なし)

### 結果

- `docs/runs/F-verify-jp-coverage/golden_set.json` 作成 (20 entries valid JSON)
- 真値判定独立性確保: F-13.B 自体の呼び出しなし、WebSearch 経由のみ
- カズヤレビュー対象 5 件を明示、レビュー後の真値確定により次バッチ
  (F-verify-jp-coverage-measure) で TP/FP/TN/FN 算出可能な状態
- Phase A.5-3a-verify の最優先ゲート (F-verify-jp-coverage) の第 1 段階完了、
  第 2 段階 (measure) 着手準備完了
- F-13.B 動作仕様の根本的な検討課題 (タイトルクエリで広範な事件を引き当てて
  しまう構造、MEE 記事の核心 = 特定構造分析角度の判定不能性) を 5 件の
  borderline 候補として浮き彫りにした → DISCUSSION_NOTES に新エントリ追加
- リグレッション影響なし (docs/ + docs/runs/ のみ追加、src/ tests/ configs/
  CLAUDE.md は 0 行変更、baseline 1315 passed 維持)

### 関連ファイル・コミット

- コミット: (push 後追記)
- 変更:
  - `docs/runs/F-verify-jp-coverage/golden_set.json` (新規、20 entries)
  - `docs/DECISION_LOG.md` (本エントリ)
  - `docs/FUTURE_WORK.md` (F-verify-jp-coverage を 2 段階分割反映 +
    F-verify-jp-coverage-measure を新規追加 + 本エントリを完了済みに)
  - `docs/DISCUSSION_NOTES.md` (F-13.B 動作仕様の検討課題 1 エントリ追加)
  - `docs/CURRENT_STATE.md` (main HEAD / 直近 5 件 / 次バッチ候補刷新)
- 関連: F-13.B JpCoverageVerifier (src/triage/jp_coverage_verifier.py、
  本バッチ時点コミット b61d3f5)
- 関連: F-doc-cleanup-followup (bcf3577、main マージ b61d3f5、2026-05-03) —
  本バッチの前提

---

## 2026-05-04: F-verify-jp-coverage-golden-fix — ゴールデンセット真値修正 + 系統 1 判定基準 4 軸明文化 + Hydrangea メディア宣言反映 + 2 段階フィルタ設計確定

### 背景

F-verify-jp-coverage-golden (前バッチ、未マージ feature ブランチ
`feature/F-verify-jp-coverage-golden` 上で同一ブランチ追加コミット) のカズヤレビューで、
4 つの重要な設計判断が確定:

1. ゴールデンセット 5 件の真値修正 (4 件 False → True、1 件削除)
2. 系統 1 (silence_gap) の判定基準明文化 (「未報道理由の構造性」が必要、4 軸構造)
3. Hydrangea のメディアとしての存在意義の明示化 (カズヤ宣言「忖度、報道規制、
   報道の自由度の低さをぶち壊そう」)
4. F-13.B の役割を系統 1 専用と確定 + 系統 2 用の独立ロジック
   (F-stream-2-filter-design) を Phase A.5-3b 前に実装する Phase 配置確定

### 議論

- **真値判定の修正方針**:
  - 案 α: 全件を True に修正 (機械仕様視点厳密化) → 不採用 (1 件は本物の未報道
    マイナー候補、機械の精度測定としては True が真値だが Hydrangea ミッション
    整合性を欠く)
  - 案 β: 全件を False のまま (系統 2 視点優先) → 不採用 (機械の精度測定としては
    誤り、F-13.B が広範な事件 = Tier 1 報道済みを正しく True 判定するのを
    『誤判定』扱いにすると測定が崩壊)
  - 案 γ (採用): 件ごとに判断 → 4 件 (blind_002/004/005/009) を True 化 +
    1 件 (blind_006 Palestine FIFA) は削除

- **blind_006 (Palestine FIFA) の扱い**:
  - 案 (B) ラベル付けて残す → 不採用 (ゴールデンセット純度低下)
  - 案 (C) 削除 → 採用 (Hydrangea 系統 1 ミッションに整合しない単マイナー候補は
    blind set から外す)
  - 案 (A) 構造的未報道理由を持つ候補に差し替え → 試行したが該当候補なし。
    heuristic 未採用 12 件を全件評価:
    - cls-2d791f7f4b17 (Iraq al-Zaidi 首相指名): Tier 1 報道済み (Nikkei + Asahi)
    - cls-f383daaef143 (NK-Russia 戦没者記念館): Tier 1 報道済み
      (Mainichi + Nikkei + Hokkaido + Jiji + ANN)
    - cls-579833967531 (Houthi 統一表明): Tier 2 報道済み (Bloomberg JP)
    - Hormuz クラスタ (cls-7eaa0040dfff / 819a09bdda6f / 962feee682b9 /
      a83e0f0a56a5 / b107a1e4becb / b574fcfd8cb3 / cf5b64e8fc3f): 全て Tier 1
      報道済み
    - cls-74974ee82dbd (Russian yacht): blind_007 と重複
    - cls-e97b90f53eac (Japan Rapidus AI chips): JP 国内、Tier 1 報道済み
    - 該当候補ゼロ → spec 規定 (該当なしなら 9 件構成許容) に従い 9 件構成で確定

- **系統 1 判定基準の構造化 (4 軸)**:
  - カズヤから「特定国への忖度」観点が追加提示
  - さらに「上級国民・政治家への忖度」観点が追加提示 (個人・権力者層への
    構造的配慮、メディアオーナー一族・司法関係者・財界要人等を含む)
  - カズヤのメディア宣言: 「忖度、報道規制、報道の自由度の低さをぶち壊そう。
    そういうクソみたいな理由で報道されないものこそ Hydrangea で取り扱うべき記事」
  - 制度・システム面 / 外交・経済・利害関係面 / **個人・権力者面 (★新規)** /
    関心領域・地政学的死角 の 4 軸に整理

- **Hydrangea のメディアとしての存在意義の明示化**:
  - 当初の系統 1 説明: 「日本で報じられていない海外大ニュースを日本人に届ける」
  - 課題: 「なぜ届けるか」の動機・ミッション本質が docs に明記されていない
  - 採用案: CURRENT_STATE.md セクション 0 (コアミッション) の系統 1 説明を強化、
    4 軸の構造的バイアス + カズヤ宣言を明示。これにより新しいクラウドインスタンス
    (別チャット移行時) も Hydrangea のメディアとしての存在意義を即座に理解できる

- **F-13.B の役割と Phase 配置**:
  - 当初案 (a): 現仕様維持 + 系統 2 は別ロジック → 採用
  - 当初案 (b): F-13.B 改修で広範な事件をフィルタアウト → 不採用 (過剰拡張性の罠、
    単一責任原則違反)
  - 当初案 (c): 段階的判断 → 採用 (a と統合)
  - 系統 2 用ロジックの Phase 配置:
    - 当初案: Phase A.5-3b 内に組み込み → 不採用 (カズヤ指摘「PoC は PoC に集中
      したい」)
    - 採用案: Phase A.5-3b 前に F-stream-2-filter-design として独立実装

### 決定

1. ゴールデンセット 5 件の真値修正 (4 件 True 化 + 1 件削除) +
   stream_2_candidate メタフィールドで系統 2 候補識別 (4 件)
2. 系統 1 (silence_gap) 判定基準を「未報道理由の構造性」として 4 軸構造で明文化、
   DISCUSSION_NOTES に新規エントリで記録 (制度・システム面 / 外交・経済・利害関係
   面 / 個人・権力者面 / 関心領域・地政学的死角)
3. Hydrangea のメディアとしての存在意義をカズヤ宣言として明示化、
   CURRENT_STATE.md セクション 0 の系統 1 説明を強化 (4 軸 + 宣言を明示)
4. 2 段階フィルタ設計を確立:
   - ステップ 1 (F-13.B): 系統 1 用、現仕様維持 (改修しない)
   - ステップ 2 (F-stream-2-filter-design 新規実装): 系統 2 用、F-verify-jp-
     coverage-measure 完了後 → Phase A.5-3b 前に実装
5. Phase 順序を更新: F-verify-jp-coverage-measure → F-stream-2-filter-design
   → Phase A.5-3b

### 結果

- ゴールデンセットが完成形に (kazuya_review_required_ids 空配列、19 件構成)
- 系統 1 判定基準が 4 軸構造で docs として固定化 (新チャット移行時の認識ブレ防止)
- Hydrangea メディア宣言が docs に固定化 (CURRENT_STATE セクション 0 で最初に
  読む構造、別チャット移行時にも本質的ミッションが伝わる)
- F-stream-2-filter-design が新規バッチ候補として FUTURE_WORK 緊急度 高に登録、
  Phase A.5-3b の前提条件として位置付け
- F-verify-jp-coverage-measure 着手の前提条件確定 (即着手可能)
- カズヤ哲学整合: 「動くものを壊さない」(F-13.B 維持)、「対症療法じゃなくて根本治療」
  (系統 1 判定基準明文化)、「過剰拡張性の罠回避」(F-13.B 改修不採用)、「PoC は PoC
  に集中」(系統 2 ロジックは PoC 前に独立実装)、「忘れ去られた約束を絶対忘れない
  仕組み」(メディア宣言を docs に固定化)
- リグレッション影響なし (docs/ のみ変更、baseline 1315 passed 維持)

### 関連ファイル・コミット

- コミット: (push 後追記)
- 変更:
  - `docs/runs/F-verify-jp-coverage/golden_set.json` (v1.0 → v1.1: 4 件
    True 修正 + 1 件削除 + メタ更新 + stream_2_candidate 追加 + v1_1_changelog
    追加 + selection_methodology 拡張)
  - `docs/DISCUSSION_NOTES.md` (1 新規 = 系統 1 判定基準 4 軸 + メディア宣言、
    1 追記 = F-13.B 動作仕様検討課題に 2026-05-04 議論結果)
  - `docs/FUTURE_WORK.md` (F-stream-2-filter-design 新規 + F-verify-jp-coverage-
    measure 前提更新 + Phase 順序新設 + 本エントリ)
  - `docs/CURRENT_STATE.md` (全置換更新 + ★セクション 0 系統 1 説明強化 = 4 軸 +
    Hydrangea メディア宣言 + Phase A.5-3a-verify ロードマップ 1-C/1-D/1-E 追加)
  - `docs/DECISION_LOG.md` (本エントリ)
- 関連: F-verify-jp-coverage-golden (前バッチ、未マージ feature ブランチ上で
  追加コミットとして本バッチを実施)

---

## F-verify-jp-coverage-measure (Phase A.5-3a-verify 1-D / 2026-05-05)

### 背景

F-verify-jp-coverage-golden + F-verify-jp-coverage-golden-fix で確定した
ゴールデンセット 19 件 (blind 9 + covered 10、v1.1) を真値として
F-13.B JpCoverageVerifier の実精度を測定。Phase A.5-3a-verify 1-D 段階。

合格基準 (本バッチで設定):
- Recall (covered) >= 90% (致命的 FN 抑制が最重要)
- Precision (blind) >= 80%
- F1 (covered) >= 0.85
- Tier 一致率 >= 70%

### 議論

実装方針:
- pytest 統合 vs scripts/ スタンドアロンスクリプト → スタンドアロン採用
  (pytest で実 API 呼び出し $0.10 が走るのは baseline 1315 passed 維持と
  相性が悪い、API エラーが pytest を破壊するリスク、結果ファイル永続化が
  後の再分析に有利)
- Gemini クライアント取得方法 → src/main.py:3179-3180 と同じ
  `google.genai.Client(api_key=...)` 直接生成パターンを採用 (LLMClient 抽象は
  Grounding ツールに対応していないため不採用)
- 一時 DB は `/tmp/jp_coverage_measure.db` に CREATE して本番 DB を汚染しない

### 決定

verdict: **fail** (Recall covered 0%、Precision blind 26.32%、
F1 covered 0.000、Tier 一致率 0%、エラー 0/19)。

★ **根本原因の特定** (2026-05-05 デバッグで判明):
F-13.B の `_search_with_grounding()` 内で `chunk.web.uri` を URL として
扱っているが、Gemini Grounding API は実ソースドメインではなく Vertex AI の
リダイレクト URL (`vertexaisearch.cloud.google.com/grounding-api-redirect/...`)
を返す仕様。実ドメインは `chunk.web.title` (例: `jiji.com`, `jetro.go.jp`,
`recordchina.co.jp`) に格納されている。`chunk.web.domain` は SDK 現行版で
常に None。

このため WL マッチング (`if domain in url_lower`) は redirect URL に対して
構造的に常に不一致 → F-13.B は **本番でも常に has_jp_coverage=False を
返している** 可能性が極めて高い。本来 divergence 扱いすべき「日本で報道済み
の海外ニュース」を blind_spot として動画化していた可能性があり、Hydrangea
ミッション系統 1 (silence_gap) の品質保証機構が機能していなかった懸念。

判定アクション:
- F-jp-coverage-improve バッチを FUTURE_WORK 緊急度 高に新規登録、即着手推奨
- F-stream-2-filter-design 着手は **保留** (F-13.B が機能していない状態で
  系統 2 だけ実装しても意味が薄いため)
- 修正方針: `_search_with_grounding()` で `web.title` を読み取り
  `https://{title.lower()}` で URL 化して urls に積む最小修正
- 修正後に本スクリプト (verify_jp_coverage_measure.py) を再実行して合格判定を
  取り直す (covered 10 件の大半は TP に転じる見込み: jiji.com / nippon.com /
  nikkei.com 等の WL ドメインが実測で chunk.web.title にヒット)

### 結果

- 合格基準 4 指標すべて未達 (Recall covered 0% は致命的)、verdict=fail
- 根本原因が特定できたため、F-jp-coverage-improve は最小修正で済む見込み
  (スコープ: jp_coverage_verifier.py 1 ファイル、既存テスト保護下で修正)
- 19 件全件 matched=0 + エラー 0 件という整合性のある計測ができた
  (ゴールデンセット v1.1 + 計測スクリプトの設計妥当性も同時に確認できた)
- 計測スクリプト `scripts/verify_jp_coverage_measure.py` は将来 (改修後の
  再測定・継続的な精度監視) に再利用可能な資産として確立
- 試運転 7-K で「100% (3/3) 動画化」と記録されているが、これは F-13.B が
  常に has_jp_coverage=False を返した結果、全 Slot が blind_spot 動画化
  ルートに進んだだけで、F-13.B の判定精度を示すものではないと再解釈される
  (試運転 7-K の 3 件は実際は日本主要メディアで報道済みだった可能性、要追跡)
- リグレッション影響なし (scripts/ + docs/runs/ + docs/ のみ変更、
  src/ tests/ configs/ CLAUDE.md 0 行、baseline 1315 passed 維持)

### 関連ファイル・コミット

- コミット: (push 後追記)
- 新規追加:
  - `scripts/verify_jp_coverage_measure.py` (約 600 行、CLI スクリプト)
  - `docs/runs/F-verify-jp-coverage/measurement_result.json`
    (機械読み詳細 + root_cause_finding フィールド)
  - `docs/runs/F-verify-jp-coverage/REPORT.md`
    (人間読みレポート + ★1.5 根本原因の特定セクション)
- 変更:
  - `docs/DECISION_LOG.md` (本エントリ)
  - `docs/FUTURE_WORK.md` (F-jp-coverage-improve 新規追加 +
    F-verify-jp-coverage-measure 完了済みに移動 +
    F-stream-2-filter-design 着手保留化)
  - `docs/DISCUSSION_NOTES.md` (F-13.B 動作仕様検討課題に
    2026-05-05 実測結果 + 根本原因特定を追記)
  - `docs/CURRENT_STATE.md` (全置換更新)
- 関連: F-verify-jp-coverage-golden / F-verify-jp-coverage-golden-fix
  (前バッチ、ゴールデンセット v1.1 を真値として使用)

---

## F-jp-coverage-improve (Phase A.5-3a-verify 1-D' / 2026-05-07)

### 背景

F-verify-jp-coverage-measure (2026-05-05、verdict=fail) で F-13.B
JpCoverageVerifier の構造的不具合 (`chunk.web.uri` を WL マッチングに使用、
Gemini Grounding は実ドメインを `chunk.web.title` で返す) を特定。Hydrangea
コンセプト防衛機構 5 層の中核 (F-13.B) が機能していなかった懸念。本バッチは
**根本治療志向** で 5 つの目的を同時達成する複合バッチ:

1. F-13.B 構造的不具合の根本治療 (ドメイン抽出レイヤー追加で SDK 変更耐性)
2. 不変原則例外条件の構造化 (「実装バグ修正は例外」の運用ルール化)
3. Project Knowledge 最新化運用のルール化 (別チャット移行時の認識ブレ防止)
4. Phase A.5-3a-verify ゲート完了条件の再定義 (試運転を必須段階に組込み)
5. 計測再実行で合格判定取得

### 議論

#### 議論 1: F-13.B 修正方針

選択肢:
- **案 A** (最小修正): `_search_with_grounding()` 内で `chunk.web.title` を
  直接 `https://{title}` 形式で urls に push。実装 5 行程度
- **案 B** (SDK アップデート待ち): `chunk.web.domain` が実値を返す SDK
  バージョンを待つ → 不採用 (SDK 改善時期不明、緊急対応が必要)
- **案 C** (検索戦略変更): Grounding API → 直接 Web 検索 API (Bing 等) に
  変更 → 不採用 (過剰スコープ、既存設計の根本見直し)
- **案 D** (URL 抽出 + ドメイン正規化レイヤー): `_extract_domain_from_chunk` /
  `_looks_like_domain` / `_normalize_domain` を独立関数化、フォールバック
  戦略 (戦略 1: domain → 戦略 2: title) を持たせる → ★ 採用

採用根拠: 案 A は機能するが脆弱 (SDK が将来 `domain` を実値で返した時に整合性を
取りにくい)、案 D は防御層としての設計 (SDK 変更耐性、ドメイン正規化ロジック
独立化で F-stream-2-filter-design でも再利用可能)。「対症療法じゃなくて根本
治療」哲学 + 「動くものを壊さない」哲学に整合。

#### 議論 2: 不変原則 3 例外適用の根拠

`src/triage/jp_coverage_verifier.py` 改修は不変原則 3 (`src/triage/` 既存
ファイル変更不可) に抵触する。例外条件 4 つ全て満たすか議論:

- **(1) 実装バグの修正である**: ✅ Gemini Grounding redirect URL を WL
  マッチングに使うバグの修正、仕様通り動かない状態を直す
- **(2) 設計変更ではない**: ✅ `verify()` / `verify_async()` シグネチャ・
  戻り値構造不変、ドメイン抽出ロジックの「正しい実装」への置換のみ、新たな
  責務は追加しない
- **(3) DECISION_LOG エントリで明記**: ✅ 本エントリで明記
- **(4) Hydrangea ミッション中核機構のためカズヤ承認必須**: ✅ Hydrangea
  コンセプト防衛機構 5 層の F-13.B 層、バッチプロンプトの背景セクションに
  カズヤ承認を記録済み

→ 4 条件全て満たすため例外適用を承認。本事例を BATCH_PROTOCOL.md の
「過去の例外適用事例」として記録し、将来の判断基準に資する。

#### 議論 3: Project Knowledge 運用ルール化の必要性

claude.ai の Project Knowledge は GitHub と自動同期されない。新チャット移行
時に古い docs を読んでいると認識ブレが発生する (= クラウド誤りの一因)。
F-doc-cleanup-followup (2026-05-03) でクラウド誤り 7 (系統 1 中心理解で
系統 2 を過小評価) を記録した経緯から、構造的に再発防止する仕組みが必要。

→ 「新チャット移行前に必ず Project Knowledge を最新化」を必須タイミング、
「大きなフェーズ完了時 / 重要 docs 変更後」を推奨タイミングとして
BATCH_PROTOCOL.md に明文化。

#### 議論 4: Phase A.5-3a-verify ゲート完了条件再定義

旧定義: 1-A〜1-E の 5 段階、1-D 完了で精度 verdict 取得 → 1-E (F-stream-2-
filter-design) に進む構成。

問題: 「動くものを壊さない」哲学に従えば、修正後 F-13.B の本番試運転 + 過去
判定後追いを **必須段階** として組み込むべき。

→ 1-D' (F-jp-coverage-improve、本バッチ) 内に 1-D'' (計測再実行) を統合
(修正と検証は分離不能)、1-D''' (F-trial-run-post-fix、試運転バッチ) を
新規段階として追加。1-A〜1-D''' 全完了で Phase A.5-3a-verify ゲート完了。

#### 議論 5: 計測再実行の verdict=fail への対処

修正後の再測定で構造的不具合は解消 (TP=0→10, FN=14→4) したが、4 指標とも
閾値未達のため verdict=fail のまま。

選択肢:
- **(a)** 本バッチでスコープを広げて Recall/Precision/Tier 一致率も改善 →
  ★ 不採用 (バッチプロンプト「勝手にスコープ広げないこと」、Tier ロジックは
  別問題)
- **(b)** 残課題を本バッチでは対象外として記録、別バッチに分離 → ★ 採用

採用根拠: 「ロジックが構造的に常に False を返す」状態 → 「正しく動くが精度が
閾値未達」状態は質的に異なる進捗。残課題 (FN クエリ最適化 / FP diamond.jp
真値再評価 / Tier 一致率) はそれぞれ独立した問題で、同一バッチで対処すると
複雑度が増す。F-trial-run-post-fix (試運転 + 過去後追い) と F-jp-coverage-tune
(精度閾値達成) に分離。

### 決定

1. **F-13.B 修正は案 D 採用**: ドメイン抽出レイヤー
   (`_extract_domain_from_chunk` / `_looks_like_domain` / `_normalize_domain`)
   を `src/triage/jp_coverage_verifier.py` に追加。`_search_with_grounding()`
   は新レイヤー経由で実ドメインを WL マッチングに供給、`chunk.web.uri` は
   debug 用 `redirect_urls` に分離記録。
2. **不変原則 3 例外適用**: 4 条件全て満たすため適用承認、BATCH_PROTOCOL.md
   に「不変原則の例外条件」セクション (4 条件 + 例外不可ケース + 過去事例) を
   新設、本バッチを過去事例として記録。
3. **Project Knowledge 最新化運用ルール**: BATCH_PROTOCOL.md に「Project
   Knowledge 最新化運用ルール」セクション (必須/推奨タイミング + 最新化対象 +
   注意事項) を新設。新チャット移行前は必須最新化。
4. **Phase A.5-3a-verify ゲート完了条件再定義**: 1-A〜1-D''' 構成に。
   1-D' (本バッチ) 内に 1-D'' (計測再実行) 統合、1-D''' (F-trial-run-post-fix、
   未着手) を最終段階として追加。
5. **再測定 verdict=fail の残課題は分離対応**: F-trial-run-post-fix で
   試運転 + 過去判定後追い、F-jp-coverage-tune で精度閾値達成。本バッチでは
   スコープを広げない。
6. **テスト**: 新規 28 テストを `tests/test_jp_coverage_verifier_domain_extract.py`
   に追加。既存 `tests/test_f13b_rescue_abolition.py` のフィクスチャ
   `_make_grounding_response` を実 API contract に整合化 (uri = Vertex
   redirect URL、title = 実ドメイン、domain = None)、除外 URL アサーション
   1 つを host ベースに調整。テスト総数 1315 → 1345 (+30) 全 passed 維持。

### 結果

#### 構造的不具合の解消 (修正前後比較)

| 指標 | v1 (修正前) | v2 (修正後) | 変化 |
| --- | --- | --- | --- |
| TP (covered, 一致) | 0 | 10 | +10 |
| FN (報道済→False 誤判定) | 14 | 4 | -10 (大幅改善) |
| TN (blind, 一致) | 5 | 3 | -2 |
| FP (未報道→True 誤判定) | 0 | 2 | +2 |
| Recall (covered) | 0.00% | 71.43% | +71.43pt |
| Precision (blind) | 26.32% | 42.86% | +16.54pt |
| F1 (covered) | 0.000 | 0.769 | +0.769 |
| Tier 一致率 | 0.00% (0/0) | 30.00% (3/10) | +30.00pt |
| stream_2_candidate True | 0/4 | 3/4 | +3/4 |

#### 計測再実行 verdict

verdict: **fail** (4 指標とも閾値未達のまま)。ただし「ロジックが構造的に
常に False を返す」状態 (v1) → 「正しく動くが精度が閾値未達」状態 (v2) は
質的に異なる進捗。残課題は本バッチ責務範囲外。

#### docs 化された運用ルール

- BATCH_PROTOCOL.md「不変原則の例外条件」セクション新設 (4 条件 + 例外不可
  ケース + 過去事例)
- BATCH_PROTOCOL.md「Project Knowledge 最新化運用ルール」セクション新設
  (必須/推奨タイミング + 最新化対象 + 注意事項)
- CURRENT_STATE.md の Phase A.5-3a-verify ロードマップを 1-A〜1-D''' 構成に
  再定義

#### カズヤ哲学整合

- 「対症療法じゃなくて根本治療」: 案 D (ドメイン抽出レイヤー) で SDK 変更耐性
  を持たせ、対症療法的な修正を避けた
- 「動くものを壊さない」: 既存 `verify()` シグネチャ・戻り値構造不変、
  既存テストフィクスチャは API contract 整合化のみ (テスト意図は不変)、
  baseline 1315 → 1345 全 passed 維持
- 「過剰拡張性の罠回避」: 戦略 3 (uri からの redirect 解析) は spec 通り
  実装せず、戦略 1/2 で十分と判断
- 「忘れ去られた約束を絶対忘れない仕組み」: BATCH_PROTOCOL.md に例外条件 +
  Project Knowledge 運用ルールを明文化 (個別バッチで再議論しない)
- 「PoC は PoC に集中」: F-stream-2-filter-design 着手再開条件を更新、
  F-trial-run-post-fix で本番試運転確認後に再開

#### リグレッション影響

- 本番コード変更: `src/triage/jp_coverage_verifier.py` (ドメイン抽出レイヤー
  追加 + `_search_with_grounding()` 修正)
- 新規テスト 28 件追加、既存テストフィクスチャ整合化、baseline 1315 → 1345
  全 passed 維持
- docs / configs / 他の src / は影響なし

### 関連ファイル・コミット

- コミット: (push 後追記)
- 新規追加:
  - `tests/test_jp_coverage_verifier_domain_extract.py` (28 テスト、ドメイン
    抽出レイヤー検証)
- 変更:
  - `src/triage/jp_coverage_verifier.py` (★不変原則 3 例外条項適用、ドメイン
    抽出レイヤー追加 + `_search_with_grounding()` 修正)
  - `tests/test_f13b_rescue_abolition.py` (`_make_grounding_response`
    フィクスチャを実 API contract に整合化、除外 URL アサーション host ベース化)
  - `docs/runs/F-verify-jp-coverage/measurement_result.json` v2 (再測定結果
    上書き、root_cause_finding に resolved_in 追加)
  - `docs/runs/F-verify-jp-coverage/REPORT.md` v2 (再測定結果上書き、★1.5
    セクションを「根本原因の特定と修正済み報告」に更新、修正前後比較表追加)
  - `docs/BATCH_PROTOCOL.md` (不変原則例外条件 + Project Knowledge 運用ルール
    セクション新設)
  - `docs/CURRENT_STATE.md` (全置換更新)
  - `docs/DECISION_LOG.md` (本エントリ)
  - `docs/FUTURE_WORK.md` (F-jp-coverage-improve 完了済み移動 +
    F-trial-run-post-fix / F-jp-coverage-tune 緊急度 高新規追加 +
    F-stream-2-filter-design 着手再開条件更新 + Phase 順序新版)
  - `docs/DISCUSSION_NOTES.md` (F-13.B 動作仕様検討課題エントリ更新)
- 関連: F-verify-jp-coverage-measure (前バッチ、本バッチ修正対象の構造的
  不具合を特定)

## F-trial-run-post-fix (Phase A.5-3a-verify 1-D''' / 2026-05-07)

### 背景

F-jp-coverage-improve (2026-05-07) で F-13.B の構造的不具合
(`chunk.web.uri` の Vertex redirect URL 誤読み問題) を根本治療し、ドメイン抽出
レイヤー (`_extract_domain_from_chunk` / `_looks_like_domain` / `_normalize_domain`)
を追加。修正後の `verify_jp_coverage_measure.py` 再測定で構造的不具合は解消
(TP=0→10, FN=14→4)。ただし精度閾値未達 (verdict=fail) のため残課題は
F-jp-coverage-tune に分離。

「動くものを壊さない」哲学に従い、修正後 F-13.B が本番運用 (RSS 収集 → triage →
Slot 選定) で期待通り動くか試運転で確認、過去試運転 7-K 動画化 3 件 (FIFA + Gaza×2)
の WebSearch 後追いで「実は日本主要メディアで報道済みだったか」を検証する必要が
あった。本バッチは Phase A.5-3a-verify ゲート完了の **最終段階 (1-D''')**。

### 議論

#### 議論 1: 試運転実行範囲

選択肢:
- (a) 試運転 = 動画化前段階まで (script + article 生成、TTS / 動画レンダリング
  スキップ) → ★ 採用
- (b) 試運転 = 動画レンダリングまで実施 → 不採用 (Phase A.5-3b 手動 PoC で
  品質確立する設計のため、本バッチは F-13.B 動作確認に責務を限定)
- (c) 試運転 = ingestion + triage まで (Slot 選定スキップ) → 不採用 (F-13.B
  は Slot 選定後の script 生成段階で呼ばれるため、Slot 選定まで実行が必須)

採用根拠: バッチプロンプト指定通り、Phase A.5-3b 手動 PoC との責務分離。

#### 議論 2: WebSearch 後追いの判定確信度

Anthropic WebSearch クローラは asahi.com / yomiuri.co.jp / nhk.or.jp /
mainichi.jp / sankei.com / 47news.jp / kyodonews.jp / kyodonews.net への直接
クロールがブロックされる仕様。Tier 1 主要紙の報道有無を直接確認できない制約。

選択肢:
- (a) 確認可能な WL ドメイン (jiji / nikkei / bloomberg / 各テレビ局 / Tier 4
  ビジネス誌) のヒットから推定する → ★ 採用
- (b) Tier 1 主要紙の報道有無は判定不能として記録 → 不採用 (jiji / nikkei
  ヒットがあれば「広範に報道済み」推定は妥当)

採用根拠: WL 27 ドメイン全体での「報道有無の傾向」判定が目的、特定 Tier の
個別判定ではない。past_videos_audit.json の audit_caveats に明記。

#### 議論 3: 試運転 3 Slot 全 has_jp_coverage=False への対処

試運転で全 3 Slot has_jp_coverage=False、ただし WebSearch 後追いで Slot-1
(Insider trading) は Tier 1-2 報道済み = Recall miss を確認。

選択肢:
- (a) 本バッチで F-13.B 検索クエリ修正に着手 → ★ 不採用 (バッチプロンプト
  「想定外結果が出た場合は本バッチでは記録のみ、勝手にスコープ広げない」)
- (b) 想定外結果として記録 + 次バッチ (F-jp-coverage-tune) に明示的に
  引き継ぐ → ★ 採用

採用根拠: 「対症療法じゃなくて根本治療」哲学、「動くものを壊さない」哲学
に整合。Recall miss は構造的不具合ではなく Grounding API の検索結果品質問題で、
F-jp-coverage-tune の主要課題と完全整合。本バッチでは記録のみ。

#### 議論 4: Phase A.5-3a-verify ゲート完了判定

本バッチ完了時点での 1-D''' 達成条件:
- 試運転実行 (Task B): ✅
- 構造的不具合解消の本番動作確認 (excluded_count 非ゼロ): ✅
- 防衛機構 5 層全機能確認 (Task D): ✅
- 過去 7-K 動画化 3 件の WebSearch 後追い (Task E): ✅
- 修正後 F-13.B での過去試運転再判定 (Task F): ✅

→ Phase A.5-3a-verify ゲート完了 (1-A〜1-D''' 全完了) を **正式宣言**。
F-stream-2-filter-design 着手 OK。F-jp-coverage-tune は別系で精度閾値達成の
課題、ゲート完了の必須条件ではない (CURRENT_STATE 1-D''' 完了時点の整理と整合)。

### 決定

1. **試運転実行モード**: `python -m src.ingestion.run_ingestion` で RSS 取得 →
   `python -m src.main --mode normalized` で動画化前段階まで実行 (AUDIO/VIDEO
   render はデフォルト false でスキップ)
2. **WebSearch 後追い判定基準**: 確認可能 WL ドメイン (jiji / nikkei /
   bloomberg / 各テレビ局 / Tier 4 ビジネス誌) のヒットから「広範報道」推定。
   Tier 1 主要紙 (asahi / yomiuri / nhk / mainichi / sankei / 47news / kyodo)
   は WebSearch クローラ制約で直接確認不能、past_videos_audit.json に明記
3. **想定外結果 (Recall miss 1/3) への対応**: 本バッチでは記録のみ、
   F-jp-coverage-tune に明示的に引き継ぐ
4. **過去試運転再判定**: 一時 DB (`/tmp/jp_coverage_replay.db`) で本番 DB を
   汚染しない構造、`scripts/replay_jp_coverage.py` で実装 (前バッチの
   `verify_jp_coverage_measure.py` 構造を踏襲)
5. **Phase A.5-3a-verify ゲート完了正式宣言**: 1-A〜1-D''' 全完了で
   F-stream-2-filter-design 着手 OK 状態に
6. **テスト**: 本バッチは src/ tests/ configs/ への変更なし (新規スクリプト +
   docs/runs/ + docs/ のみ)、baseline 1345 passed 維持

### 結果

#### 試運転実行結果

| 項目 | 値 |
|---|---|
| 実行時間 | 約 26 分 (ingestion 1.5 分 + 試運転 26 分) |
| batch_id | 20260506_190600 |
| RSS 取得 | 41 ソース中 40 成功 |
| 記事収集 | 1454 raw → 584 重複除去後 → 364 events |
| EditorialMissionFilter | 18/364 通過 (4.95%) |
| Elite Judge Gate 3 | 採用 9 / 棄却 1 |
| Slot 選定 | 上位 3 件 (動画化 1 件 + 記事化 3 件) |
| F-13.B invocations | 3 件、全 has_jp_coverage=False |
| Budget | run_llm=38/150 |
| 出力 | scripts 1, articles 3, video_payloads 1, evidence 1 |

#### F-13.B 出力分布 (試運転 3 + replay 7-K 3 = 6 invocations)

| 項目 | 件数 |
|---|---|
| has_jp_coverage = True | 0 |
| has_jp_coverage = False | 6 |
| Error | 0 |
| matched_tier 別: Tier 1-4 | 0 |
| excluded URLs 合計 | 23 件 (全 youtube.com) |

→ **構造的不具合解消の本番動作確認**: 全 6 invocations のうち 5/6 で
excluded_urls_count > 0 (1/10/3/0/5/4)。修正前は redirect URL のみ収集 → 全
構造的に excluded=0 だった。ドメイン抽出レイヤーが正しく機能している証拠。

#### 防衛機構 5 層発火状況

| 層 | 発火状況 | 結果 |
|---|---|---|
| F-1 EditorialMissionFilter | 364 評価、20 LLM scored、threshold 45.0、18 通過 | ✅ 正常稼働 |
| F-2 FlagshipGate | 18 評価、Blocked 0 件 | ✅ 正常稼働 |
| F-13.B JpCoverageVerifier | 3 invocations、True 0 / False 3 / Error 0 | ✅ 構造機能 OK |
| F-5 Downstream Rescue | 救済発火 0 件 (Elite Judge で十分採用済み) | ✅ 正常稼働 |
| F-13 隠れ層 (quality_floor bypass) | bypass 発火 0 件 | ✅ 正常稼働 |

→ 全 5 層が構造的に機能。

#### 試運転 7-K 過去動画化 3 件 WebSearch 後追い

| Slot | Event ID | 旧判定 | WebSearch 後追い結論 | stream_2 候補 |
|---|---|---|---|---|
| 1 | cls-7bd1406438b6 (FIFA Palestine) | False | Tier 2 (jiji.com) で関連報道 (2026-03-25) | ✅ |
| 2 | cls-33b4f4960bf9 (Mandelson Gaza) | False | Tier 1 (nikkei) + Tier 2 (jiji + bloomberg) で広範報道済み (Epstein 角度)、MEE オリジナル『Gaza 道徳的責任』角度は未報道 | ✅ |
| 3 | cls-204a683f73ee (Gaza 電力) | False | 2023-2024 古い基本事実は Tier 1 で過去報道、MEE 2026-04 時点の特定角度は未報道 | ❌ (真の blind_spot に近い) |

→ 3 件中 2 件 (Slot-1/Slot-2) は実は Tier 1-2 報道済み、典型的
stream_2_candidate パターン (golden set v1.1 の blind_002/004/005/009 と同形)。
F-stream-2-filter-design 完成後の 2 段階フィルタで救出される設計と整合。

#### 過去試運転 7-K 修正後 F-13.B 再判定

| Event ID | 旧判定 (b950813) | 新判定 (fd76660) | excluded_urls_count |
|---|---|---|---|
| cls-7bd1406438b6 | False | False (判定不変) | 0 |
| cls-33b4f4960bf9 | False | False (判定不変) | 5 |
| cls-204a683f73ee | False | False (判定不変) | 4 |

→ 3 件全て False→False、ただし excluded_count 非ゼロ (2/3 件) で構造機能 OK。
Recall miss は Grounding 検索クエリ品質問題 (F-jp-coverage-tune 対象)。

#### Phase A.5-3a-verify ゲート完了

1-A〜1-D''' 全完了確認 → **Phase A.5-3a-verify ゲート完了** 正式宣言。
F-stream-2-filter-design 着手 OK。

#### カズヤ哲学整合

- 「対症療法じゃなくて根本治療」: 試運転で発見された Recall miss を本バッチで
  即修正せず、F-jp-coverage-tune に分離して根本対応する判断
- 「動くものを壊さない」: 本バッチは src/ tests/ configs/ 変更なし、新規
  スクリプト + docs/runs/ + docs/ のみ。baseline 1345 passed 維持
- 「忘れ去られた約束を絶対忘れない仕組み」: Phase A.5-3a-verify ロードマップを
  1-D''' まで完了、CURRENT_STATE / DECISION_LOG / FUTURE_WORK に明文化
- 「PoC は PoC に集中」: 本バッチで Phase A.5-3a-verify ゲート完了確定 →
  Phase A.5-3b 手動 PoC 着手準備が整った
- 「過剰拡張性の罠回避」: 試運転で発見された WebSearch クローラ制約
  (asahi/yomiuri 等ブロック) について、特別対処せず audit_caveats に明記する
  方針

#### リグレッション影響

- 本番コード変更: なし
- 新規スクリプト: `scripts/replay_jp_coverage.py` (過去試運転データ再判定用)
- 新規 docs: `docs/runs/F-trial-run-post-fix/` 配下
  (trial_run_log.json / f13b_output_analysis.json / defense_layers_audit.json /
  past_videos_audit.json / past_runs_replay.json / REPORT.md /
  trial_7k_events.json / replay_log.txt / trial_run_log.txt / ingestion_log.txt)
- baseline 1345 passed 維持

### 関連ファイル・コミット

- コミット: (push 後追記)
- 新規追加:
  - `scripts/replay_jp_coverage.py` (過去試運転データ再判定スクリプト)
  - `docs/runs/F-trial-run-post-fix/REPORT.md` (統合レポート)
  - `docs/runs/F-trial-run-post-fix/trial_run_log.json` (試運転実行結果)
  - `docs/runs/F-trial-run-post-fix/f13b_output_analysis.json` (F-13.B 出力分布)
  - `docs/runs/F-trial-run-post-fix/defense_layers_audit.json` (防衛機構 5 層
    発火状況)
  - `docs/runs/F-trial-run-post-fix/past_videos_audit.json` (試運転 7-K 過去
    動画 3 件 WebSearch 後追い)
  - `docs/runs/F-trial-run-post-fix/past_runs_replay.json` (修正後 F-13.B での
    7-K 再判定結果)
  - `docs/runs/F-trial-run-post-fix/trial_7k_events.json` (replay 入力)
- 変更:
  - `docs/CURRENT_STATE.md` (全置換更新、Phase A.5-3a-verify ゲート完了反映)
  - `docs/DECISION_LOG.md` (本エントリ追加)
  - `docs/FUTURE_WORK.md` (F-trial-run-post-fix 完了済み移動 +
    F-stream-2-filter-design 着手 OK 状態に更新 + F-jp-coverage-tune 優先度確認)
  - `docs/DISCUSSION_NOTES.md` (F-13.B 動作仕様検討課題エントリのステータス更新 +
    新規エントリ「Grounding 検索クエリ品質問題」追加)
- 関連: F-jp-coverage-improve (前バッチ、本バッチで動作確認した F-13.B 修正)、
  F-jp-coverage-tune (本バッチで再確認された Recall 課題の対処バッチ、
  着手再開条件達成)、F-stream-2-filter-design (本バッチ完了で着手 OK 状態に)

## 2026-05-07: F-particular-angle-design — 「特定角度」概念の docs 化 + LLM ベースアノテーション 25 件

### 背景

F-trial-run-post-fix (2026-05-07) で Phase A.5-3a-verify ゲート完了が確定したが、
本番試運転と過去 7-K 後追いで重要な発見があった: 試運転 Slot-1 (Insider trading) は
WebSearch で nikkei (Tier 1) / jiji / bloomberg (Tier 2) で広範報道済みだったが
MEE オリジナル「インサイダー取引疑惑 + 国家による金融兵器化」角度は未報道、過去
7-K Slot-2 (Mandelson) は Tier 1-2 広範報道済みだが MEE オリジナル「Gaza 道徳的責任」
角度は未報道、というパターン。これを系統 1 (silence_gap) と系統 2 (framing_inversion) に
分類する際、判定対象を「広範事件」レベルで取ると両系統で重複ケースが発生し、
F-stream-2-filter-design + F-jp-coverage-tune の仕様化が曖昧になる。カズヤとの
議論 (2026-05-07) で「重複しないように定義すればよくね?」 = 判定対象を『特定角度』
(MEE/海外メディアが独自に掘った視点) に限定すれば重複は構造的に消える、という
結論に到達。本バッチは Phase A.5-3a-verify ゲート完了後の最初のバッチで、
F-stream-2-filter-design + F-jp-coverage-tune の共通基盤 (= 「特定角度」概念の
正典 docs + 25 件アノテーション) を確立する性格を持つ。

### 議論

(a) 「特定角度」概念の docs 化方針: 後続 2 バッチが同じ判定単位を参照できる
正典 docs として `docs/PARTICULAR_ANGLE_DEFINITION.md` を新規作成。bullet 形式
ではなく散文展開で系統 1 vs 系統 2 の責務分離 / 4 軸との関係 / multi_angle_analysis
5 観点との関係 / media_divergence 観点との関係 / 抽出の難所まで網羅。
(b) アノテーション方式: カズヤ手動 0 件 (= 全件 LLM 抽出 → カズヤレビュー方式)
を採用。理由は 25 件を全件カズヤ手作業すると 3-5 時間かかるが、LLM 一次抽出 +
カズヤレビューなら 1-2 時間で済む。LLM 出力は信頼ではなく初案として扱い、
カズヤレビューで `kazuya_review.*_revised` フィールドを上書きする方式。
(c) LLM モデル: Gemini Flash analysis Tier (既存 `get_analysis_llm_client()`
経由) を採用。既存 LLM 抽象との整合 + Tier フォールバック + 予算管理を継承。
ただし `max_output_tokens` は既定の 2000 では本プロンプトで JSON が途中切断
される事象を覚知 (試行 1-2 で 6-7 件失敗) し、本スクリプトで `max_output_tokens=4096`
の専用クライアントを構築する設計に変更 (試行 3 で 0 errors)。
(d) golden_set v1.2 への統合範囲: 試運転 6 件 (7-K 3 + 2026-05-07 3) は
golden_set には統合せず、`stream_classification.json` で全 25 件まとめて管理する
責務分離を採用。理由は golden_set は計測精度の真値セットとして 19 件構成を
維持する必要があり、試運転データはノイズになる。

### 決定

(1) ★ 「特定角度」概念採用: 系統 1 / 系統 2 / 対象外の判定対象を「広範事件」では
なく「特定角度 (海外メディアが独自に掘った視点)」に限定。論理フローは Step 1
(4 軸該当) → Step 2 (日本未報道) → Step 3 (解釈差) の 3 段階。これを
`docs/PARTICULAR_ANGLE_DEFINITION.md` で正典化。

(2) ★ LLM ベースアノテーション (カズヤ手動 0 件) 採用: 25 件全件を Gemini で
一次抽出 → カズヤレビュー → `scripts/finalize_annotations.py` で最終化、の
2 段階フロー。本バッチは Task A-E + G を完了させ、Task F (カズヤレビュー) は
本バッチ内では実行しない。

(3) ★ 系統 1/系統 2/対象外 の判定基準確定 (LLM 推定段階): stream_1_silence_gap=11、
stream_2_framing_inversion=13、out_of_scope=1。covered 系列の 9/10 件が
stream_2 に分類され、これは「日本主要メディアで報道済みの事象でも海外メディアの
掘り下げ角度には解釈差があり stream_2 候補となる」という LLM 判断傾向。
カズヤレビューで再評価され、最終確定値は `stream_classification.json` に記録される。

(4) ★ F-stream-2-filter-design + F-jp-coverage-tune への共通基盤確立:
本バッチで `docs/PARTICULAR_ANGLE_DEFINITION.md` + 25 件アノテーションを整備
することで、後続 2 バッチが「特定角度」を共通の判定単位として実装できる
状態に。F-stream-2-filter-design は系統 2 救出の 2 段階フィルタ実装、
F-jp-coverage-tune は Grounding 検索クエリの「特定角度」ベース化。

(5) ★ src/ tests/ configs/ への変更なし: 本バッチは新規 scripts/
(extract_particular_angle.py / finalize_annotations.py) + 新規 docs
(PARTICULAR_ANGLE_DEFINITION.md / runs/F-particular-angle-design/ 配下) +
docs 更新のみ。baseline 1345 passed 維持。

### 結果

#### Task 別実施結果

| Task | 状態 | 主要成果物 |
|---|---|---|
| A | ✅ | `docs/PARTICULAR_ANGLE_DEFINITION.md` (新規、5 セクション散文展開) |
| B | ✅ | `scripts/extract_particular_angle.py` (新規、`max_output_tokens=4096` 専用クライアント + パーサ最小修復) |
| C | ✅ | `docs/runs/F-particular-angle-design/input_events.json` (25 件統合: golden_set 19 + 7-K 3 + 2026-05-07 3) |
| D | ✅ | `annotations.json` (extraction_confidence: high=22 / medium=3、stream 推定: 系統 1=11 / 系統 2=13 / 対象外=1、errors=0) |
| E | ✅ | `review_draft.md` (655 行、25 events フォーマット統一) |
| F | ★ 待ち | カズヤ手動レビュー (本バッチ内では未実行) |
| G | ✅ | `scripts/finalize_annotations.py` (新規、annotation_diff + stream_classification + golden_set v1.2 を生成) |
| H | ✅ | `REPORT.md` + DECISION_LOG (本エントリ) + FUTURE_WORK + DISCUSSION_NOTES + CURRENT_STATE |

#### LLM 抽出の構造的観察

(a) golden_set v1.1 の `stream_2_candidate` メタ付き 4 件 (blind_002/004/005/009)
のうち 3 件 (blind_002/004/009) が LLM では stream_1 に分類された。これは v1.1 で
「広範事件は報道済み = True、特定角度は系統 2 候補」とラベルしていたが、
判定対象を『特定角度』に限定すると同じ事象でも『特定角度自体は日本未報道』と
読める可能性があることを示唆。カズヤレビューで再評価される。

(b) 試運転 2026-05-07 の Insider trading (cls-6be4fc09d9ed) は LLM が stream_1 と
判定。F-trial-run-post-fix WebSearch 後追いで広範事件は Tier 1-2 報道済みと判明
していたが、特定角度 (国家規模インサイダー取引疑惑) は日本主要メディアで
深掘り未報道、と LLM が判定。「特定角度」概念の有効性を示唆する事例。

(c) 試行 1-2 で max_output_tokens=2000 による JSON 途中切断を覚知 (6-7 件失敗)、
4096 への拡張で 0 errors 達成。analysis_llm_client 既定の 2000 tokens は
本タスクには不十分という観察を F-stream-2-filter-design 着手時の判断材料に。

#### 不変原則違反

なし (新規 scripts + docs のみ、src/ tests/ configs/ 変更なし)。

### 関連ファイル・コミット

- コミット: (push 後追記)
- 新規追加:
  - `docs/PARTICULAR_ANGLE_DEFINITION.md` (「特定角度」概念正典 docs)
  - `scripts/extract_particular_angle.py` (LLM ベース特定角度抽出スクリプト)
  - `scripts/finalize_annotations.py` (カズヤレビュー後の最終化スクリプト)
  - `docs/runs/F-particular-angle-design/input_events.json` (25 件入力統合)
  - `docs/runs/F-particular-angle-design/annotations.json` (LLM 抽出結果)
  - `docs/runs/F-particular-angle-design/review_draft.md` (カズヤレビュー用 Markdown)
  - `docs/runs/F-particular-angle-design/extraction_log.txt` (抽出実行ログ)
  - `docs/runs/F-particular-angle-design/REPORT.md` (統合レポート)
- 変更:
  - `docs/CURRENT_STATE.md` (全置換更新、F-particular-angle-design 完了反映)
  - `docs/DECISION_LOG.md` (本エントリ追加)
  - `docs/FUTURE_WORK.md` (F-particular-angle-design 完了済み移動 +
    F-stream-2-filter-design + F-jp-coverage-tune の前提に「F-particular-angle-design 完了」を追記)
  - `docs/DISCUSSION_NOTES.md` (系統 1 判定基準明確化エントリと系統 2 設計エントリを
    本バッチ結果で更新 + 新規エントリ「特定角度抽出の LLM 限界観察」)
- 関連: F-trial-run-post-fix (前バッチ、本バッチの背景となる 6 件実例を提供)、
  F-stream-2-filter-design (★ 本バッチで共通基盤確立、即着手 OK)、
  F-jp-coverage-tune (本バッチの「特定角度」概念を検索クエリ生成に転用)

---

## 2026-05-08: F-particular-angle-redesign — 3 分類 → 4 分類化 (系統 1.5 perspective_gap 追加) + 台本表現ガイドライン正典化

### 背景

F-particular-angle-design (2026-05-07) で 3 分類 (系統 1 / 系統 2 / 動画化対象外)
版を確立し、25 件の LLM ベースアノテーションを完了した。続くカズヤレビュー
(2026-05-07 同日中に DISCUSSION_NOTES へ 4 エントリ追加) 過程で、3 分類の
構造的不備が明らかになった。具体的には blind_002 (Israel ラビ庁) / blind_004
(Gaza 潤滑油 100 倍) / blind_009 (Iran-US 戦争長期化) のような事象群で「広範
事件は日本主要メディアで報道済み、特定角度のみ未報道」というパターンが多発
しており、LLM 判定では「特定角度ベース」で stream_1_silence_gap に分類される
が、台本表現としては「日本では報じられていない」と書くと嘘になり、視聴者
からのツッコミを誘発するリスクが残る。カズヤから「一部報道だけど観点不足って
いう 1.5 分類儲けてもいいのかもしれない」と提案され、議論の結果 4 分類化が
必要との結論に到達。本バッチは Phase A.5-3a-verify ゲート完了後の **2 つ目**
のバッチで、F-particular-angle-design の構造的不備の根本治療と、後続バッチ
(F-stream-2-filter-design / F-jp-coverage-tune) の責務分離をより明確化する
性格を持つ。

### 議論

(a) 4 分類化の構造: 系統 1 (両方未報道) / 系統 1.5 (広範のみ報道、特定角度
未報道、新設) / 系統 2 (特定角度報道済み + 解釈差) / 動画化対象外 (4 軸該当
なしまたは差分なし)。系統 1 の中に「完全空白」と「広範のみ報道」が混在する
構造的問題を、系統 1.5 を新設することで分離する。

(b) 4 分類化の論理フロー: Step 0 (特定角度抽出) → Step 1 (4 軸該当) → Step 2
(広範事件の日本報道) → Step 3 (特定角度の日本報道) → Step 4 (解釈差)。
Step 2 と Step 3 を **独立判定** することで、両者の組み合わせで系統 1 /
系統 1.5 を区別する。これは F-13.B JpCoverageVerifier の二段階クエリ生成
(広範事件クエリ + 特定角度クエリ) の責務分離に直結する。

(c) 台本表現ガイドラインの設計哲学: カズヤから「言い回しを個別ルールで指定
するのは避けたい (= ルール累積で全体劣化)、article_writer.py は触りたくない
(= 不変原則 1)、LLM の知性に期待したい」という 3 つの制約が提示された。これに
従い、台本表現は強制ルールではなく **particular_angle_metadata 構造を
script_writer.py 新ルートに渡し、LLM が自律選択** する設計を採用。具体的
言い回しは Phase A.5-3b 手動 PoC で 1 本作りながら試行錯誤する想定。

(d) カズヤレビュー方式: F-particular-angle-design の Task F (3 分類版での
カズヤレビュー) を **スキップ** し、4 分類版で初めてカズヤレビューを実施する
方式を採用。理由は 3 分類版を確定させる前に 4 分類化が必要なことが判明した
ため、3 分類版での確定作業は無駄になる。3 分類版の LLM 判定結果は
`annotations_v1_3class.json` として保存し、参照可能にした。

(e) `scripts/finalize_annotations.py` の改修方針: 既存の 3 分類対応関数を保持
しつつ、4 分類対応関数を新規追加する形式を採用。CLI 引数に `--schema-version`
を追加 (デフォルト 2.0 = 4 分類)。これは「動くものを壊さない」哲学に整合
する設計で、F-particular-angle-design の Task F (3 分類版) を実行する選択肢も
理論上は残る (実用上は実行しない)。

### 決定

(1) ★ **4 分類化採用**: 系統 1 / 系統 1.5 (perspective_gap、新設) / 系統 2 /
動画化対象外。`docs/PARTICULAR_ANGLE_DEFINITION.md` を 3 分類 → 4 分類版に
大幅改訂 (セクション 1 末尾追記 + セクション 3 大幅改訂 + 新サブセクション 3.5
台本表現ガイドライン)。

(2) ★ **二段階クエリ生成への接続**: 系統 1 vs 系統 1.5 の判別は『広範事件』
と『特定角度』の報道状態を独立判定する必要があり、F-jp-coverage-tune の
責務範囲。本バッチで `broad_event_jp_coverage` と `particular_angle_jp_coverage`
の真値を 25 件分整備した (annotations.json)。

(3) ★ **台本表現は LLM の知性に委ねる**: particular_angle_metadata 構造
(stream_classification + core_question + differentiation_from_mainstream +
hydrangea_axis_alignment) を script_writer.py 新ルートに渡し、LLM が系統別の
言い回しを自律選択する設計。具体的な言い回しは Phase A.5-3b 手動 PoC で確立。

(4) ★ **F-stream-2-filter-design の責務範囲縮小可能性**: LLM 推定段階で
stream_2 が 0 件 (想定 13 件)、stream_1_5 が 20 件 (想定 5 件) という想定外
分布が観測された。LLM が 4 分類定義を厳密適用した結果として技術的に整合
する判定だが、F-stream-2-filter-design の優先度・スコープ判断はカズヤ
レビュー後に再評価する。仮にカズヤレビュー後も stream_2 が 1-2 件しか
ない場合、F-stream-2-filter-design は小規模実装で済み、F-jp-coverage-tune
が **より優先** される構造になる。

(5) ★ **本バッチは src/ tests/ configs/ への変更なし**: 新規 scripts/
(reclassify_annotations.py / generate_review_draft_v2.py) + 改修 scripts/
(finalize_annotations.py の `--schema-version 2.0` 追加) + 新規 docs
(runs/F-particular-angle-redesign/ 配下) + 既存 docs 更新のみ。baseline
1345 passed 維持。

### 結果

#### Task 別実施結果

| Task | 状態 | 主要成果物 |
|---|---|---|
| A | ✅ | `docs/PARTICULAR_ANGLE_DEFINITION.md` 改訂 (3 分類 → 4 分類、新サブセクション 1.1 / 3.5 追加) |
| B | ✅ | `scripts/reclassify_annotations.py` (新規、per-call timeout 90s + resume + incremental save 付き) |
| C | ✅ | `annotations.json` (4 分類版、25/25 success、stream_1=4 / stream_1_5=20 / stream_2=0 / out_of_scope=1) + `reclassification_diff.json` + `reclassification_log.json` |
| D | ✅ | `review_draft_v2.md` (重点レビュー section: 3 分類 → 4 分類で変更があった 20 件を冒頭表示) |
| E | ★ 待ち | カズヤ手動レビュー (本バッチ内未実行) |
| F | ✅ | `scripts/finalize_annotations.py` 改修 (`--schema-version 2.0` 追加、4 分類対応関数 + 3 分類対応関数併存) |
| G | ✅ | `REPORT.md` + DECISION_LOG (本エントリ) + FUTURE_WORK + DISCUSSION_NOTES + CURRENT_STATE 全置換更新 |

#### LLM 再分類の構造的観察

(a) **想定外結果: stream_2 が 0 件 (想定 13 件)、stream_1_5 が 20 件 (想定 5 件)**:
LLM の reasoning は技術的に整合 (例えば covered_002 米ロ停戦は「広範事件は
日本でも報道済みだが、トランプ・プーチン直接交渉が既存 G7 合意を破壊する
という特定角度は日本主要メディアで深掘り未報道」)。これは LLM の集約バイアス
(stream_2 を選ぶ基準が厳しすぎる) または 4 分類定義の必然的帰結 (海外メディア
の特定角度は日本で同フレームで報道されることが稀) のいずれかで、カズヤ
レビューで判別する必要がある。

(b) **3 分類版で stream_2 だった 13 件全てが stream_1_5 に移動**: covered 系列
9 件 + blind_005/008 + 試運転 cls-7bd1406438b6 / cls-33b4f4960bf9_7K の全件。
3 分類版の stream_2 が「広範事件レベルでの解釈差」を許容する緩い定義
だったため数が多く見えたが、4 分類化で『特定角度レベル』に絞ると 0 になる
構造を可視化。

(c) **3 分類版で stream_1 だった 7 件が stream_1_5 に移動**: blind_002/004/009/
010 + 試運転 3 件 (cls-204a683f73ee_7K / cls-6be4fc09d9ed / cls-a4132ec7d949)。
F-particular-angle-design の DISCUSSION_NOTES 観察 1 で予測された変化と整合。

(d) **Gemini API 503 高負荷で実行時間 1:36 hr**: 通常 6-7 分で完了する
タスクが Tier 1 → Tier 2 → Tier 3 フォールバック多発のため大幅遅延。per-call
timeout 90 秒 + incremental save の組み合わせで最終完走 (success=25 / error=0、
timeout 警告 3 件 + 後続リトライで成功)。本バッチ内で第 1 試行 (kill 必要) →
incremental save + timeout 追加 → 第 2 試行で完走、というスクリプト改善
プロセスを経た。

#### 不変原則違反

なし (新規 scripts + docs のみ、src/ tests/ configs/ への変更なし)。

### 関連ファイル・コミット

- コミット: (push 後追記)
- 新規追加:
  - `scripts/reclassify_annotations.py` (4 分類化 LLM 再判定スクリプト、resume + incremental save + per-call timeout)
  - `scripts/generate_review_draft_v2.py` (4 分類版 review_draft_v2.md 生成)
  - `docs/runs/F-particular-angle-redesign/REPORT.md` (統合レポート)
  - `docs/runs/F-particular-angle-redesign/reclassification_log.json` (実行ログ)
  - `docs/runs/F-particular-angle-redesign/reclassification_diff.json` (3 → 4 分類差分)
  - `docs/runs/F-particular-angle-redesign/reclassify_log.txt` (stdout/stderr)
  - `docs/runs/F-particular-angle-redesign/review_draft_v2.md` (カズヤレビュー用)
  - `docs/runs/F-particular-angle-design/annotations_v1_3class.json` (3 分類版バックアップ)
- 改修:
  - `scripts/finalize_annotations.py` (`--schema-version` 追加、4 分類対応関数 + 3 分類対応関数併存、golden_set v1.2 → v1.3 更新パス)
  - `docs/PARTICULAR_ANGLE_DEFINITION.md` (3 分類 → 4 分類化、新サブセクション 1.1 / 3.5 追加、関連ファイル 3 サブセクション化)
  - `docs/runs/F-particular-angle-design/annotations.json` (4 分類版に上書き、`legacy_stream_classification_v1` フィールド + 4 分類版 `stream_classification_estimate` + `broad_event_jp_coverage` / `particular_angle_jp_coverage` 新フィールド付与)
- 更新:
  - `docs/CURRENT_STATE.md` (全置換更新、F-particular-angle-redesign 完了反映)
  - `docs/DECISION_LOG.md` (本エントリ追加)
  - `docs/FUTURE_WORK.md` (本バッチを完了済みに移動、F-stream-2-filter-design の責務スコープ縮小可能性 + F-jp-coverage-tune の優先度上昇を追記)
  - `docs/DISCUSSION_NOTES.md` (「2026-05-07: 系統 1.5 分類追加の検討」を Resolved 化、「2026-05-07: 台本表現課題」「2026-05-07: 動画化候補の系統分布実態」を 4 分類版データで更新)
- 関連: F-particular-angle-design (前バッチ、3 分類版を確立 + DISCUSSION_NOTES 4 エントリ追加で本バッチの起点)、F-stream-2-filter-design (★ 本バッチ後カズヤレビュー結果で責務スコープ判断)、F-jp-coverage-tune (★ 本バッチで二段階クエリ生成の真値整備、優先度上昇)



---

## 2026-05-08: F-particular-angle-redesign-extension — 系統名 1/1.5/2 → 1/2/3 リネーム + 忖度シグナル独立化 + クラウド誤り 9 記録

### 背景

F-particular-angle-redesign 完了直後の Task E カズヤレビュー過程で、
カズヤから本質的な指摘が 3 件提示された:

1. **命名整理**: 「1.5 という命名は時間的経緯の痕跡で、定常状態の命名としては
   不適切。1.5 じゃなくてそれが 2 で、今までの 2 が 3」
2. **忖度シグナルの独立化**: 「忖度・報道規制・黙殺の構造」を系統判定に
   組み込むと MECE が崩れる。系統判定は『報道状態』軸のみで MECE 化し、
   忖度シグナルは別軸 (メタデータフィールド) で扱うべき
3. **各論コントロール回避**: ジレンマ解説等のルール追加は記事品質劣化の
   リスク、article_writer.py / script_writer.py の自由度阻害、LLM の知性
   発揮を抑制。ドキュメント化せず LLM に委ねる

これらを反映するため F-particular-angle-redesign の **拡張作業** として
本バッチを実施。新規 commit + push で対応、コード変更なし
(src/ tests/ configs/ への変更なし)。

### 議論

#### 命名整理 (1/1.5/2 → 1/2/3)

カズヤ提案: 「1.5 じゃなくてそれが 2 で、今までの 2 が 3」。F-particular-angle-redesign
の 4 分類は時間的経緯 (3 分類 → 4 分類) で命名されたため「1.5」という非定常
ラベルが残った。定常状態に至った 4 分類体系では命名も整理し、純粋な順序
ラベル (1/2/3) に統一する。系統 3 (旧 2、framing_inversion) は本来の意味
(評価フレーム対立 + 忖度シグナル) を担う系統として正典化。

#### 忖度シグナルの独立化 (sontaku_signals)

カズヤ提案: 「忖度・報道規制・黙殺の構造を系統判定に組み込むと MECE が崩れる」。
F-particular-angle-redesign 直後の議論で、系統 3 の判定基準として「ジレンマ
解説」「忖度明示」のような各論ルールを追加する案が浮上したが、これは
クラウド誤り 9 (各論コントロールへの誘惑) の典型例。代わりに sontaku_signals
を **系統判定とは独立な別軸メタデータ** として正典化し、Step 4 (系統 3 判定)
の追加軸に組み込む設計を採用。これにより:
- 系統判定は『報道状態』軸のみで MECE
- 忖度シグナルは F-1 EditorialMissionFilter (動画化価値) +
  F-stream-2-filter-design 第二段階 (解説価値) で参照される独立軸として運用
- Hydrangea コアミッション「忖度・報道規制をぶち壊す」と直接整合する事象を
  3 系統横断で識別可能

#### クラウド誤り 9 (各論コントロールへの誘惑) 記録

レビュー過程で観察された「具体的指針 (視聴者ファースト 3 原則 / ジレンマ
解説 / 忖度明示 / 台本表現ルール) を追加したくなる傾向」を、再発防止策と
してクラウド誤り 9 に登録。CLAUDE.md にクラウド誤りセクションを新設 +
DISCUSSION_NOTES に詳細エントリ追加 + PARTICULAR_ANGLE_DEFINITION.md
セクション 3.7 で「LLM の知性に委ねる」設計哲学を正典化。

### 決定

#### Task A: PARTICULAR_ANGLE_DEFINITION.md 改訂

- 系統名 1/1.5/2 → 1/2/3 にリネーム (機械的置換 + 関連プロセ修正)
- 新サブセクション 1.2 (命名整理経緯) + 1.3 (忖度シグナル独立化経緯)
- セクション 3 改訂: 4 分類定義を新命名で記述、Step 3-4 改良 (Step 3 =
  「日本メディアが特定角度を語っているか」、Step 4 = 「評価対立 + 忖度
  シグナル」)
- 新サブセクション 3.5 (MECE 判別基準明示) + 3.6 (sontaku_signals 構造定義
  + 系統判定との関係 + 後続バッチでの参照)
- 既存 3.5 (系統別の台本表現の方向性) を 3.7 にリナンバー、メタデータ
  構造に sontaku_signals 追加 + クラウド誤り 9 への参照追加

#### Task B: scripts リネーム + 修正

- reclassify_annotations.py / generate_review_draft_v2.py /
  finalize_annotations.py の系統名リネーム
- reclassify_annotations.py の LLM プロンプトに改良版 Step 0-4 + MECE
  判別基準の核心を反映
- generate_review_draft_v2.py の `_stream_label` を新命名 + 旧名併記に更新

#### Task C: annotations.json 系統名リネーム + schema_version 更新

- `estimated_stream` 値の機械的置換 (25 件中 20 件、
  `stream_1_5_perspective_gap` → `stream_2_perspective_gap`、未使用の旧
  `stream_2_framing_inversion` → `stream_3_framing_inversion`)
- schema_version 2.0 → 2.1、`previous_schema_version=2.0` 記録
- `legacy_stream_classification_v1` フィールド内の値は変更しない (3 分類版
  の歴史的記録として保持)

#### Task D: scripts/add_sontaku_signals.py 新規作成 + 25 件推定生成

- 新規スクリプト (per-call timeout 90s + incremental save + resume) で
  25 件分の sontaku_signals を LLM 推定生成
- annotations.json 各 event に `sontaku_signals` フィールド付与 +
  `kazuya_review.sontaku_signals_revised` スロット追加
- `extension_log.json` に level / type / extraction_confidence 分布記録

#### Task E: クラウド誤り 9 記録

- CLAUDE.md にクラウド誤りセクション新設 + 誤り 9 本文を記載
  (誤り / 動機 / 害 / 正しい設計 / カズヤ哲学 / 運用ルール)
- DISCUSSION_NOTES に新エントリ追加 (Resolved、再発防止策確立)
- 系統 3 (旧系統 2) の典型パターン (日本-海外の評価対立) も新エントリ追加
  (Active、Phase A.5-3b で参照)

#### Task F: 統合レポート + ドッグフーディング

- REPORT.md にセクション 11 (拡張作業) 追加
- DECISION_LOG (本エントリ) + FUTURE_WORK (拡張作業反映) +
  DISCUSSION_NOTES (3 エントリ) + CURRENT_STATE 全置換更新

#### 不変原則例外適用

なし (新規 scripts + docs + CLAUDE.md のみ、src/ tests/ configs/ への変更
なし)。

### 結果

#### 後続バッチへの影響

- **F-jp-coverage-tune**: 二段階クエリ生成 (広範事件 + 特定角度) で系統 1
  vs 系統 2 を機械判別する設計の前提が整備 (annotations.json schema 2.1 +
  sontaku_signals 真値で精度評価可能)。優先度は本バッチで再確認: ★最優先
- **F-stream-2-filter-design**: 系統 3 (旧系統 2) のみ担当 + sontaku_signals
  を解説価値判定の追加軸として参照する設計。stream_3 候補が極小 (0 件)
  想定だが、カズヤレビュー結果次第で再評価。系統 3 候補が 1-2 件なら小規模
  実装で済む
- **Phase A.5-3b 手動 PoC**: `particular_angle_metadata + sontaku_signals`
  を `script_writer.py` 新ルートに渡し、LLM が言い回しを自律選択する設計
  を 1 本作りながら検証

#### Task E (★ 旧、4 分類版カズヤレビュー) の状態

新分類体系 (1/2/3) + sontaku_signals メタデータ付きで実施。本拡張バッチ
完了後にカズヤがレビュー → finalize_annotations.py --schema-version 2.0
実行 → 後続バッチ判断、というフロー。

#### LLM 推定段階の sontaku_signals 分布 (25 件、本拡張バッチ実測値)

- level: high=7 / medium=14 / low=1 / none=3
- type: diplomatic=20 / domestic=1 / media_industry=1 / null=3
- extraction_confidence: high=23 / medium=2 / low=0
- 実行時間: 約 9 分 (success=25 / error=0、timeout 警告 1 件 + 後続リトライで成功)
- LLM モデル: gemini-analysis-tier-extended (analysis Tier 階層 +
  max_output_tokens=4096)
- 詳細は `docs/runs/F-particular-angle-redesign/extension_log.json` および
  `docs/runs/F-particular-angle-design/annotations.json` の各 event の
  `sontaku_signals` フィールドを参照。本バッチでは LLM 推定値として整備し、
  カズヤレビュー後に `kazuya_review.sontaku_signals_revised` で確定。
- 観察: type=diplomatic が 20 件と圧倒的多数。Hydrangea 入力 RSS 41 媒体
  (MEE, Meduza, Al Jazeera 等) が外交・地政学事象を中心に扱うため、忖度
  シグナルも外交的忖度が中心という構造的整合 (記録のみ、F-stream-2-filter-design
  着手時の参考材料)。

#### 不変原則違反

なし (新規 scripts + docs + CLAUDE.md のみ、src/ tests/ configs/ への変更
なし)。

### 関連ファイル・コミット

- コミット: (push 後追記)
- 新規追加:
  - `scripts/add_sontaku_signals.py` (LLM ベース sontaku_signals 推定スクリプト、resume + incremental save + per-call timeout)
  - `docs/runs/F-particular-angle-redesign/extension_log.json` (拡張作業ログ + level / type / confidence 分布)
- 改修:
  - `docs/PARTICULAR_ANGLE_DEFINITION.md` (命名 1/2/3 + 1.2 / 1.3 / 3.5 / 3.6 / 3.7 サブセクション + Step 3-4 改良)
  - `scripts/reclassify_annotations.py` (命名リネーム + LLM プロンプト改良版 Step 0-4)
  - `scripts/generate_review_draft_v2.py` (命名リネーム + ラベル更新)
  - `scripts/finalize_annotations.py` (命名リネーム)
  - `docs/runs/F-particular-angle-design/annotations.json` (schema_version 2.0 → 2.1、25 件中 20 件 estimated_stream 値リネーム + sontaku_signals フィールド付与 + sontaku_signals_revised スロット追加)
  - `CLAUDE.md` (クラウド誤りセクション新設 + 誤り 9 記載 + 最終更新日)
  - `docs/runs/F-particular-angle-redesign/REPORT.md` (セクション 11 拡張作業追加)
- 更新:
  - `docs/CURRENT_STATE.md` (全置換更新、F-particular-angle-redesign-extension 完了反映)
  - `docs/DECISION_LOG.md` (本エントリ追加)
  - `docs/FUTURE_WORK.md` (拡張バッチを完了済みに移動、後続バッチ前提を更新)
  - `docs/DISCUSSION_NOTES.md` (新規エントリ 2 件: クラウド誤り 9 + 系統 3 典型パターン、既存 1 エントリを Resolved 化)
- 関連: F-particular-angle-redesign (前バッチ、4 分類化を確立)、F-jp-coverage-tune (★ 拡張バッチで sontaku_signals 真値整備で設計確度向上)、F-stream-2-filter-design (★ 拡張バッチで系統 3 + sontaku_signals 設計が確定)

---

## 2026-05-08: F-extension-followup — stream_3=0 件 (c) 仮説追記 + sontaku_signals サンプル設計バイアス記録 + finalize_annotations.py の sontaku_signals 対応

### 背景

F-particular-angle-redesign-extension (2026-05-08, commit `6a8efc4` / merge
`2c9ee96`) のクラウドレビューで本質的な指摘が 3 件浮上した:

1. **指摘 1 (sontaku_signals type 分布のサンプル設計バイアス)**: 25 件中
   `type=diplomatic` が 20 件 (80%) と圧倒的多数。DECISION_LOG /
   FUTURE_WORK では「Hydrangea 入力 RSS 41 媒体が外交・地政学事象中心」と
   いう構造的整合の **説明** で済まされていたが、これは整合の説明であって
   検証ではない。25 件のサンプル (golden_set 19 + 試運転 6) はもともと海外
   メディア発の事象が中心で、日本メディア起点の `domestic` 忖度
   (政治家・上級国民) や `media_industry` 忖度 (記者クラブ・ジャニーズ系)
   はサンプル設計上ほぼ拾えない構造。将来の系統 3 候補 (処理水放出 /
   入管法改正 / 辺野古 / ジャニーズ) の type 分布を過小評価する可能性。

2. **指摘 2 (stream_3 = 0 件問題の (c) サンプル選定バイアス説)**:
   DISCUSSION_NOTES の既存エントリ「2026-05-08: 4 分類化で stream_3 = 0 件 /
   stream_2 = 20 件 という想定外分布」では仮説 (a) LLM 集約バイアス説 /
   (b) 必然的帰結説のみ記録されていたが、前チャットでカズヤから第 3 仮説が
   提起されていた: **(c) サンプル選定バイアス説** — 25 件のサンプルは大半が
   「海外メディア独自視点 (= 系統 2 perspective_gap)」事象で、日本メディアと
   海外メディアが同じ角度で対立評価する事象 (= 真の系統 3 framing_inversion)
   はサンプルに偶然含まれていなかった可能性が高い。extension では構造論点
   としては Resolved 扱いだったが、(c) が真ならこれは「LLM 判定の問題」でも
   「4 分類定義の問題」でもなく、**入力データセットの構造的問題**。

3. **指摘 3 (Task E 着手前の finalize_annotations.py の sontaku_signals
   対応確認)**: annotations.json に `kazuya_review.sontaku_signals_revised`
   スロット (null) が追加されたが、Task E カズヤレビュー時の修正粒度が
   定義されていない。`scripts/finalize_annotations.py` が schema 2.0 で
   `sontaku_signals` をどう扱うかを Task E 着手前に確認が必要。

これらを反映するため本フォローアップバッチを実施。docs 追記 + scripts 最小
修正、src/ tests/ configs/ への変更なし。

### 議論

#### Task A (DISCUSSION_NOTES 追記 + 新規エントリ)

既存 stream_3=0 件エントリの ステータスは extension で「Resolved (構造的
整理完了)」と記載されていたが、(c) 仮説が論点として残ることを明示するため
ステータスを `Active (要カズヤ判別 + サンプル拡充検討)` に降格し、(c) 仮説
本文と Task E カズヤレビュー時の判別フローを追加。新規エントリ
「sontaku_signals type 分布のサンプル設計バイアス」を追加し、現サンプルの
整備自体は問題ないが、Phase A.5-3b 第二作 + F-1 EditorialMissionFilter
設計時に再評価することを記録。

#### Task B (finalize_annotations.py の sontaku_signals 対応確認)

確認結果は **(c) 未対応** (schema 2.0 で `sontaku_signals` /
`sontaku_signals_revised` 両フィールドが完全にスルーされる)。

確認した範囲:
- `_resolve_final()` (lines 68-93): `particular_angle` /
  `stream_classification` のみ resolve、`sontaku_signals` 未参照
- `build_stream_classification()` (lines 159-196): event 出力に
  `sontaku_signals` 含まれず
- `update_golden_set()` (lines 199-298): entry 更新に `sontaku_signals`
  含まれず
- `build_annotation_diff()` (lines 96-156): `sontaku_signals_revised`
  カウント欠落

Task B-4 の方針に沿い、最小修正で対応:
- `_resolve_final()` に `final_sontaku_signals` /
  `final_sontaku_signals_source` 追加 (null → LLM 推定値継承、object →
  全フィールド上書き、フィールド単位 partial merge は未実装)
- `build_stream_classification()` の event 出力に sontaku_signals 反映
- `update_golden_set()` で schema 2.0 のときのみ entry に sontaku_signals
  反映 + meta に `final_sontaku_signals_source` 記録
- `build_annotation_diff()` に `sontaku_signals_revised_count` 追加 +
  diff entry に `sontaku_signals_revised` フラグ追加

既存関数のシグネチャ・戻り値構造は維持 (新キー追加のみ、既存キーは不変)。
Hydrangea ミッション中核機構 (F-13.B / F-1 / F-2 / F-5 / F-13 隠れ層) には
触れず、scripts 配下の最終化スクリプトのみ修正。

#### Task C (BATCH_PROTOCOL Task 1-5 ドッグフーディング)

extension 完了直後で BATCH_PROTOCOL の運用ループを継続。新規緊急度
追加なし (Phase A.5-3b で再評価する論点として DISCUSSION_NOTES に既に記録)。

### 決定

- **Task A**: DISCUSSION_NOTES の既存 stream_3=0 件エントリに (c)
  サンプル選定バイアス説を追記、ステータスを Resolved → Active に降格、
  「カズヤレビューで判別する」セクションに (c) の判別フロー追加。新規
  エントリ「2026-05-08: sontaku_signals type 分布のサンプル設計バイアス」
  追加 (Active、Phase A.5-3b 第二作 + F-1 設計時に再評価)。
- **Task B**: `scripts/finalize_annotations.py` を最小修正、schema 2.0 で
  sontaku_signals を全 4 関数で扱えるように追加 (null → LLM 継承 / object →
  全上書き、フィールド単位 partial merge は未実装)。
- **Task C**: DECISION_LOG (本エントリ) + FUTURE_WORK (本バッチを完了済みに
  追加) + DISCUSSION_NOTES (Task A で実施済み) + CURRENT_STATE (全置換更新)
  をドッグフーディング。

#### 不変原則例外適用

なし (docs 追記 + scripts/finalize_annotations.py の最小修正のみ、src/
tests/ configs/ への変更なし、既存関数のシグネチャ・戻り値構造は維持で
不変原則 3 例外条件遵守)。

### 結果

#### 後続バッチへの影響

- **F-particular-angle-redesign Task E** (4 分類版 + sontaku_signals 込み
  カズヤレビュー): finalize_annotations.py の sontaku_signals 対応が完了
  したため、カズヤがレビュー後に `--schema-version 2.0` で実行すれば
  golden_set + stream_classification.json + annotation_diff.json の全てに
  sontaku_signals が反映される。`kazuya_review.sontaku_signals_revised` の
  修正粒度は「null = LLM 推定値継承 / object = 全フィールド上書き」で、
  フィールド単位の partial merge は実装しない (Phase A.5-3b 実運用時に
  カズヤが手で全フィールド書く運用で支障なし)。
- **Phase A.5-3b 第二作**: 系統 3 事象 (処理水放出 / 辺野古 等、引き継ぎ
  v3 でカズヤ提案) を意図的にサンプルに含めることで、sontaku_signals type
  分布の偏りと stream_3=0 件問題の (c) 仮説検証を兼ねる根拠に発展。
- **F-1 EditorialMissionFilter** (将来検討): sontaku_signals
  `level=high/medium` を優先採点する設計時、type 分布の偏りが優先度判定の
  歪みを生むリスクがあるため、本エントリを設計レビュー時に参照する。

#### 整合性検証

- baseline テスト数: **1345 passed 維持**
  (`python -m pytest tests/ -x --tb=short -q` 実行、101.01s)
- スクリプト動作確認 (実 annotations.json で smoke test):
  `_resolve_final` で `final_sontaku_signals` 解決、source=`llm_estimate` /
  diff summary に `sontaku_signals_revised_count=0` (全 25 件 null)、
  classification 出力に sontaku_signals 反映確認、counts は extension 値と
  完全一致 (`stream_1=4 / stream_2=20 / stream_3=0 / out=1`)。
- 不変原則違反: なし

### 関連ファイル・コミット

- コミット: (push 後追記)
- 改修:
  - `docs/DISCUSSION_NOTES.md` (1 エントリ更新 [stream_3=0 件 + (c) 仮説] +
    1 エントリ新規 [sontaku_signals type 分布バイアス] + ヘッダ最終更新日付)
  - `scripts/finalize_annotations.py` (sontaku_signals 対応最小修正、
    `_resolve_final` / `build_annotation_diff` /
    `build_stream_classification` / `update_golden_set` の 4 関数に追加)
- 更新:
  - `docs/CURRENT_STATE.md` (全置換更新、F-extension-followup 完了反映)
  - `docs/DECISION_LOG.md` (本エントリ追加)
  - `docs/FUTURE_WORK.md` (本バッチを完了済みに追加)
- 関連: F-particular-angle-redesign-extension (前バッチ、本フォローアップの
  発火元)、F-particular-angle-redesign Task E (★ 4 分類版 + sontaku_signals
  込みカズヤレビュー、本フォローアップで finalize_annotations.py の対応が
  完了)、Phase A.5-3b 第二作 (★ 系統 3 + domestic/media_industry サンプル
  拡充の根拠に本エントリを参照)、F-1 EditorialMissionFilter (将来、
  sontaku_signals type 分布バイアスを設計レビュー時に参照)

## 2026-05-08: F-task-e-finalize — Task E カズヤレビュー結果反映 + finalize_annotations.py 実行 + 4 運用原則 docs 化

### 背景

F-particular-angle-redesign-extension (2026-05-08, commit `6a8efc4` / merge
`2c9ee96`) + F-extension-followup (2026-05-08, commit `038c298` / merge
`1311cd0`) を経て、Task E (4 分類版 + sontaku_signals 込みのカズヤレビュー、
25 件) がクラウド (claude.ai 側) との対話形式で完了した。

レビュー結果は **25 件全件 LLM 推定値そのまま採用** (= `kazuya_review.*_revised`
フィールドは全件 null のまま)。これは Hydrangea のコアバリューのひとつ
「LLM の知性に委ねる」と整合する結果で、レビュー過程で 4 つの運用原則と
1 つの構造的問題が確立された:

1. 「揃える必然性なし」原則
2. 「sontaku_signals は嘘をつかない設計、疑わしきは低く見積もる」運用原則
3. 「LLM の知性に委ねる」原則
4. 「観点の選択的欠落 = 忖度」判定軸

加えて構造的な問題が 1 件発覚: **試運転と golden_set の重複サンプリング**
(25 件中 2 ペア = 4 件が同一 MEE 記事の重複、独立件数は実質 23 件)。

さらに、レビュー結果は F-extension-followup で記録した **(c) サンプル選定
バイアス仮説の証拠強化** にもなった (= カズヤレビュー後も stream_3 は 0 件)。

これらを反映するため本バッチを実施。Step 1: `finalize_annotations.py
--schema-version 2.0` で 25 件全件最終化。Step 2: 4 運用原則 + 1 構造的問題 +
(c) 仮説証拠強化を docs 化。

### 議論

#### Step 1 (finalize_annotations.py 実行)

`python scripts/finalize_annotations.py --schema-version 2.0 \
  --input docs/runs/F-particular-angle-design/annotations.json \
  --output-diff docs/runs/F-particular-angle-design/annotation_diff.json \
  --output-classification docs/runs/F-particular-angle-design/stream_classification.json \
  --update-golden-set docs/runs/F-verify-jp-coverage/golden_set.json` を実行。
F-extension-followup で sontaku_signals 対応最小修正済みのため、schema 2.0 で
全 25 件処理されること自体は確認済みの動作だが、Task E カズヤレビュー結果
(全件 null) が既に annotations.json に反映されている状態での最終化が本ステップ。

#### Step 2 (docs 化)

DISCUSSION_NOTES に新規 4 エントリ追加 (運用原則 3 件 + 重複問題 1 件) +
既存「stream_3=0 件」エントリに (c) 仮説証拠強化を追記、ステータスを
`Active (要サンプル拡充、Phase A.5-3b 第二作で根本治療)` に更新。
F-particular-angle-redesign/REPORT.md にセクション 12 (Task E カズヤレビュー
実施結果) 追加。DECISION_LOG / FUTURE_WORK / CURRENT_STATE のドッグフーディング。

### 決定

- **Step 1**: finalize_annotations.py を schema 2.0 で実行、25 件全件
  `final_stream_source=llm_estimate` / `final_sontaku_signals_source=llm_estimate`
  で最終化。golden_set 19 件更新 (v1.1 → v1.3、試運転由来 6 件は対象外)。
- **Step 2**: DISCUSSION_NOTES 新規 4 エントリ + 既存 1 エントリ追記 +
  REPORT.md セクション 12 追加 + ドッグフーディング。コード変更ゼロ
  (既存スクリプトの実行のみ)。
- 4 つの運用原則は今後のカズヤレビュー全般 + sontaku_signals 関連バッチ +
  F-1 EditorialMissionFilter 設計時に参照する設計原則として明文化。
- 重複サンプリング問題は即対処せず、後続バッチ (F-jp-coverage-tune /
  F-stream-2-filter-design) で真値として使うときに参照する論点として残す。

#### 不変原則例外適用

なし (docs 追記 + 既存 scripts の実行のみ、src/ tests/ configs/ への変更なし、
不変原則 1-5 完全遵守)。

### 結果

#### 後続バッチへの影響

- **F-jp-coverage-tune** (★最優先): 真値 25 件 + sontaku_signals 真値整備
  完了 + 重複問題の認識共有で、二段階クエリ生成の精度評価が可能な状態。
- **F-stream-2-filter-design** (★ 責務スコープ要再評価): stream_3 = 0 件
  確定により小規模実装で済む可能性が高い、Phase A.5-3b 第二作のサンプル拡充後
  に再評価が望ましい。
- **Phase A.5-3b 第二作**: 系統 3 事象 (処理水放出 / 辺野古 等) のサンプル
  拡充で (c) 仮説検証 + 系統 3 台本表現の試行錯誤を兼ねる。
- **F-1 EditorialMissionFilter** (将来検討): 4 つの運用原則を設計レビュー時
  に参照。特に「sontaku_signals は嘘をつかない設計、疑わしきは低く見積もる」
  原則は採点側の寛容な扱いの設計根拠になる。

#### 整合性検証

- baseline テスト数: **1345 passed 維持**
  (`python -m pytest tests/ -x --tb=no -q` 実行、134.60s)
- finalize_annotations.py 実行結果:
  - `annotation_diff.json`: `fully_unmodified_count=25`、各種
    `*_revised_count=0`
  - `stream_classification.json`: counts は LLM 推定分布と完全一致
    (`stream_1=4 / stream_2=20 / stream_3=0 / out=1`)、各 event に
    `final_stream_source=llm_estimate` /
    `final_sontaku_signals_source=llm_estimate` 付与
  - `golden_set.json`: 19 件更新 (v1.1 → v1.3)、各 entry に `particular_angle`
    / `stream_classification` / `sontaku_signals` / `particular_angle_meta`
    付与
- 不変原則違反: なし
- 試運転由来 6 件は golden_set 対象外で変更なし (= 責務分離維持)

### 関連ファイル・コミット

- コミット: (push 後追記)
- 改修:
  - `docs/DISCUSSION_NOTES.md` (新規 4 エントリ + 既存 1 エントリ追記 +
    ヘッダ最終更新日付)
  - `docs/runs/F-particular-angle-redesign/REPORT.md` (セクション 12 追加)
- 生成 (新規):
  - `docs/runs/F-particular-angle-design/annotation_diff.json`
  - `docs/runs/F-particular-angle-design/stream_classification.json`
  - `docs/runs/F-verify-jp-coverage/golden_set_v1.1.json` (バックアップ、
    finalize_annotations.py が自動生成)
- 更新:
  - `docs/runs/F-verify-jp-coverage/golden_set.json` (v1.1 → v1.3、19 件更新)
  - `docs/CURRENT_STATE.md` (全置換更新、F-task-e-finalize 完了反映)
  - `docs/DECISION_LOG.md` (本エントリ追加)
  - `docs/FUTURE_WORK.md` (本バッチを完了済みに追加)
- 関連: F-extension-followup (前バッチ、本バッチの発火元 = Task E 着手前
  整備)、F-particular-angle-redesign Task E (本バッチで結果反映完了)、
  F-jp-coverage-tune (★最優先、本バッチで真値整備が完了で着手 OK)、
  F-stream-2-filter-design (★責務スコープ要再評価、本バッチで stream_3 = 0
  件が確定)、Phase A.5-3b 第二作 (★ 系統 3 + domestic/media_industry サンプル
  拡充、(c) 仮説の根本治療)、F-1 EditorialMissionFilter (将来、4 運用原則を
  設計レビュー時に参照)



---

## 2026-05-09: F-jp-coverage-tune — F-13.B 二段階クエリ生成改修 (Phase A.5-3a-verify 1-G)

### 背景

F-task-e-finalize (2026-05-08) で Task E カズヤレビュー結果反映が完了し、Phase
A.5-3a-verify ゲート完了後の 5 連続バッチ (F-particular-angle-design /
-redesign / -extension / -followup / -task-e-finalize) を経て F-jp-coverage-tune
着手の前提が完全に整った: 真値 25 件 (独立 23 件、重複 2 ペア) + sontaku_signals
真値整備済み + 4 運用原則確立 + (c) サンプル選定バイアス仮説の証拠強化。

F-trial-run-post-fix (2026-05-07) の WebSearch 後追いで判明した F-13.B の
**構造的限界**:
- F-13.B は「事件本体のみ」を Google 検索で確認している
- しかし真値 25 件のうち 20 件 (= 80%) が系統 2 (perspective_gap) =
  「事件本体は日本でも報道済みだが、特定角度のみ未報道」
- F-13.B は事件本体の報道有無しか見ないため、系統 2 を全部「報道済み」と誤判定し、
  Hydrangea で扱うべき系統 2 事象を全部弾いてしまう

→ F-13.B の改修ではなく、**新メソッド `verify_two_stage()` を追加して二段階
クエリ生成で系統判別する** 設計に転換する。

### 議論

カズヤとのバッチプロンプト設計で 7 論点 + API エラー耐性 + 中間チェックポイント
方式 + チューニング上限を確定:

1. **LLM モデル**: `get_analysis_llm_client()` 流用 (gemini-analysis-tier-extended、
   Tier 階層フォールバック自動継承)
2. **大手メディア判定**: 既存 `JP_MEDIA_WHITELIST` 27 ドメイン + `_extract_domains()`
   再利用 (新規実装不要)
3. **過去事象除外**: Google API の `dateRestrict=d60` (過去 60 日) + 候補 publish_date
   ±60 日フィルタ
4. **検索回数**: 条件分岐 — 検索 1 (広範事件) で日本未報道なら検索 2 スキップ →
   系統 1 確定。報道済みなら検索 2 (特定角度) 実施
5. **信頼サイト**: WL 全 27 ドメインそのまま使用、`site:` 演算子は Google API クエリ
   長制限を見て判断 (本実装では使用しない)
6. **コード改修方針**: ★ 案 (B) 新メソッド `verify_two_stage()` 追加方式 (既存
   `verify()` 完全不変)、不変原則 3 例外条件 4 つ全部 (バグ修正ではない設計拡張 /
   既存メソッド完全維持 / baseline 維持 / カズヤ承認済) を満たす
7. **精度評価**: 独立 23 件 (重複 2 ペア除外、blind_005/blind_004 採用、
   cls-33b4f4960bf9_7K/cls-204a683f73ee_7K 除外)

**API エラー耐性**: レベル 2 + graceful fallback (per-call timeout 90s +
incremental save + resume + ログファイル書き出し + 完了済み event_id 記録 +
graceful fallback で `verdict=unknown` として処理継続)

**戻り値**: 新 dataclass `TwoStageVerifyResult` で `stream` フィールド =
`stream_1_silence_gap` / `stream_2_perspective_gap` / `stream_3_candidate` /
`unknown`

**中間チェックポイント方式**: CP-1 (Step 1 完了時) + CP-2 (Step 3 完了時) で
レポート提出 → カズヤ承認後に次 Step 着手。長時間実行バッチでカズヤ承認なしの
暴走を防ぐ仕組み。

**チューニング上限**: Step 4 で verdict=fail の場合、チューニング試行は **1 回のみ**。
1 回の試行で verdict=pass にならなかった場合は別バッチに切り出す (= 「対症療法
じゃなく根本治療」原則、無制限自走禁止)。

### 決定

#### 実装

`src/triage/jp_coverage_verifier.py` に以下を **新規追加** (既存メソッド一切変更なし):

- **`TwoStageVerifyResult` dataclass**: `stream` / `broad_query` / `angle_query` /
  `broad_jp_coverage` / `angle_jp_coverage` / `jp_media_hits_broad` /
  `jp_media_hits_angle` / `broad_matched_tier` / `angle_matched_tier` /
  `excluded_count_broad` / `excluded_count_angle` / `angle_query_fallback_reason` /
  `error_message` / `elapsed_seconds`
- **`verify_two_stage(candidate, particular_angle, *, timeout_seconds, date_restrict_days, analysis_llm_client)`**:
  二段階クエリ生成の本体メソッド。Step 1 で日本未報道なら Step 2 スキップ (=
  API コール削減) + graceful fallback で検索失敗時は `stream="unknown"`
- **`_build_broad_query(candidate)`**: 既存 `_build_search_query(title, summary)`
  への薄いラッパ (= 既存ロジック完全流用)
- **`_build_angle_query(candidate, particular_angle, *, analysis_llm_client, timeout_seconds)`**:
  LLM (Flash 系) で `particular_angle.core_question` から短い日本語検索クエリを生成。
  失敗時は簡易フォールバック (title + core_question 先頭 20 文字)。プロンプト
  設計は「LLM の知性に委ねる」原則尊重 = 構造制約のみで具体的言い回しルールは
  追加せず (クラウド誤り 9 回避)
- **`_fallback_angle_query(candidate, particular_angle)`**: LLM 失敗時の簡易
  フォールバック
- **`_search_with_grounding_two_stage(query, *, date_restrict_days, timeout_seconds)`**:
  二段階用 Grounding 検索 (per-call timeout)。
- **`_call_with_timeout(callable, timeout_seconds)`**: ThreadPoolExecutor.future.result
  で per-call timeout 実装

#### 不変原則 3 例外条件 4 つ全部適用根拠

1. ✅ **バグ修正ではなく設計拡張**: F-13.B の責務範囲拡大 (二段階クエリ生成の
   新メソッド追加)
2. ✅ **既存 `verify()` のシグネチャ・戻り値・挙動を完全維持**: `_build_search_query` /
   `_search_with_grounding` / `_filter_excluded` / `_match_whitelist` 不変
3. ✅ **既存テスト 1345 件全件通る**: baseline 維持 (1345 → 1364 passed、新規 19 件)
4. ✅ **Hydrangea ミッション中核機構の修正、カズヤ承認済**: 本バッチプロンプト
   自体がカズヤ承認のエビデンス

#### Step 4 チューニング (1 回のみ実施): (c) dateRestrict プロンプト埋め込み除去

CP-2 で 4 候補 (a-d) を提示し、カズヤ判断で **(c) dateRestrict プロンプト埋め込み
除去** を採択。理由: (i) 仮説 #2 (最有力) を直接検証できる最小変更、(ii) 影響範囲
最小 (`_search_with_grounding_two_stage` のプロンプト本文から日付制約文を削除する
だけ)、(iii) 旧 F-13.B との比較可能性を維持できる、(iv) 「対症療法じゃなく根本治療」
原則 = dateRestrict プロンプト埋め込みは設計レベルで無理があった撤回が筋。

`date_restrict_days` パラメータ自体は後方互換のため残置 (Grounding API 公式
サポート時の再導入を想定)。

### 結果

#### baseline 影響
- baseline 1345 → **1364 passed** (新規 19 件追加、既存 1345 件全件維持)
- 既存 `verify()` 不変性検証 OK (シグネチャ / 戻り値型 / 挙動)
- 不変原則違反: なし

#### 精度測定実行結果 (独立 23 件)

| 指標 | Pre-tuning | Post-tuning | Δ | 閾値 | 判定 |
|---|---|---|---|---|---|
| Recall covered | 0.3158 (6/19) | **0.4211 (8/19)** | +0.1053 | ≥ 0.90 | ✗ |
| Precision blind | 0.2353 (4/17) | **0.2667 (4/15)** | +0.0314 | ≥ 0.80 | ✗ |
| F1 covered | 0.4800 | **0.5926** | +0.1126 | ≥ 0.85 | ✗ |
| Tier 一致率 | 0.6667 (4/6) | **0.6250 (5/8)** | -0.0417 | ≥ 0.70 | ✗ |
| Stream accuracy (informational) | 0.3182 (7/22) | **0.2727 (6/22)** | -0.0455 | — | — |

**verdict: fail (pre/post 共通)**

confusion: TP=8 / FP=0 / FN=11 / TN=4 (post-tuning)。graceful fallback 発火 0 件、
unknown 0 件、全 23 件 stream 確定。total elapsed 322s (pre) / 341s (post)、
平均 14-15s/件。

#### dateRestrict 除去の効果分析

- broad recall +10.53pp 改善 (covered_005 ブラジル COP30 が newsweekjapan.jp
  ヒットで stream_2 確定など)
- ただし旧 F-13.B 水準 (Recall 71.43%) には届かず → dateRestrict 副作用は仮説
  通り部分的に効いていたが、**残る under-recall は Grounding API の構造的限界**
  に起因することが本バッチで明確化
- stream_3 過剰検出は 3 件 → 6 件に増加 (dateRestrict 解除で angle 検索の
  recall も上がり WL ヒット件数増加、ただし真値「特定角度は未報道」と矛盾)

#### Grounding API の構造的限界 (本バッチで発覚、F-jp-coverage-tune-followup 起案根拠)

13 件の FN 分析で以下の構造的問題が明確化:
1. **1 クエリあたり 5-10 chunk しか返さない** (Grounding API 仕様)
2. **上位ヒットが WL 外で埋まる** (chiba-tv.com / hatena.ne.jp / msf.or.jp /
   nippon.com / forbesjapan.com / afpbb.com 等が頻出、本来あるべき大手 WL
   ドメイン (NHK / 朝日 / 日経 / 読売等) が上位に入らない)
3. **0 URL 返却ケース複数発生** (covered_005 / cls-0c7fa7c667d6 /
   cls-a4132ec7d949 等)
4. **頻出 WL 外ドメイン**: youtube.com×6 / hatena.ne.jp×3 / chosunonline.com×2 /
   msf.or.jp×2 / nippon.com×2 / note.com×2 / reddit.com×2 / chiba-tv.com×2 /
   forbesjapan.com×1 / afpbb.com×1

→ verify_two_stage に固有ではなく F-13.B 全体の課題。1 回のチューニングで
verdict=pass に到達するのは構造的に困難なため、**F-jp-coverage-tune-followup**
(★最優先) として別バッチで以下を議論:
- (p) Grounding API の構造的限界対策 (複数クエリ並列発行 + 結果統合) ★最有力
- (q) 検索 API 変更検討 (Google Custom Search 移行 等)
- (r) WL ドメイン拡張検討 (forbesjapan.com / nippon.com / afpbb.com 追加)

#### stream_3 過剰検出 (定義レベルの限界、本バッチスコープ外)

post-tuning で 6 件 (blind_002 / blind_009 / covered_001 / covered_002 /
covered_004 / covered_009) が真値「特定角度は未報道」だが angle 検索で
diamond.jp / yomiuri.co.jp / newsweekjapan.jp / asahi.com がヒット → stream_3
誤判定。LLM truth は「特定角度を扱った記事 ≠ 広範事件のついでに触れた記事」と
厳格に区別するが、URL マッチング側はドメインヒット粒度しか見ないという定義レベル
の限界。後続バッチで議論。

#### 不変原則例外適用の根拠記録

不変原則 3 (`src/triage/` 既存ファイル変更不可) に対し、例外条件 4 つ全部 (バグ
修正ではない設計拡張 / 既存メソッド完全維持 / baseline 維持 / カズヤ承認済) を
満たすことを確認した上で `src/triage/jp_coverage_verifier.py` への新メソッド +
新 dataclass 追加を実施。既存 `verify()` のシグネチャ・戻り値・挙動は完全不変。

### 関連ファイル・コミット

- コミット: (push 後追記)
- 新規ファイル:
  - `tests/test_jp_coverage_verifier_two_stage.py` (19 件、新規)
  - `scripts/measure_two_stage_accuracy.py` (新規)
  - `docs/runs/F-jp-coverage-tune/measurement_result.json` (post-tuning 最終)
  - `docs/runs/F-jp-coverage-tune/measurement_result_pre_tuning.json` (Step 4 前
    のベースライン保存)
  - `docs/runs/F-jp-coverage-tune/logs/<event_id>.log` × 23 件
- 改修:
  - `src/triage/jp_coverage_verifier.py` (新規 dataclass + 新規メソッド追加のみ、
    既存メソッド完全不変、+約 290 行)
  - `docs/CURRENT_STATE.md` (全置換更新、F-jp-coverage-tune 完了反映)
  - `docs/DECISION_LOG.md` (本エントリ追加)
  - `docs/FUTURE_WORK.md` (本バッチを完了済みに移動 + F-jp-coverage-tune-followup
    を緊急度高に追加)
  - `docs/DISCUSSION_NOTES.md` (新規 2 エントリ + 既存 1 エントリ再評価)
- 関連: F-task-e-finalize (前バッチ、本バッチの真値整備が完了)、F-13.B
  (本バッチで責務拡張 = 二段階クエリ生成)、F-jp-coverage-improve (本バッチで
  例外条件 4 つの適用パターン継承)、F-jp-coverage-tune-followup (★最優先、
  Grounding API 構造的限界対策で次バッチ起案)、F-stream-2-filter-design
  (★責務スコープ要再評価、stream_3 = 0 件 + Phase A.5-3b 第二作のサンプル
  拡充後に再評価)、Phase A.5-3b 第二作 (★ 系統 3 + domestic/media_industry
  サンプル拡充、(c) 仮説の根本治療と並行)
