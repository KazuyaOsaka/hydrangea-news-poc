# Hydrangea — 意思決定ログ (DECISION_LOG)

最終更新: 2026-05-03 (F-doc-cleanup-followup 完了)

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

