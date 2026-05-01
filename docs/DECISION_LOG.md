# Hydrangea — 意思決定ログ (DECISION_LOG)

最終更新: 2026-05-01 (F-doc-protocol 完了)

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
