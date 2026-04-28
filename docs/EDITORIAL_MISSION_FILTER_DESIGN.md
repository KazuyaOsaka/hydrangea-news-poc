# EditorialMissionFilter 設計書 (Phase 1.5 / batch F-1)

> 文書バージョン: v1.0
> 作成: 2026-04-27
> 関連設計: `docs/ANALYSIS_LAYER_DESIGN_v1.1.md`, `docs/CLAUDE_CODE_INSTRUCTIONS.md`
> 関連実装: `src/triage/editorial_mission_filter.py`

---

## 1. なぜ ViralFilter から変更したか

### 旧 ViralFilter の問題

旧 `src/triage/viral_filter.py` は「日本市場でバズる動画を選定する」ことを目的に設計されていた。

スコアリング軸:
- `japan_impact` (0-40点) — 日本への直接インパクト
- `topic_affinity` (0-25点) — 日本人の関心トピック
- `discussion_trigger` (0-20点) — 議論誘発
- `contrast_potential` (0-15点) — 視点ギャップ
- `both_lang_bonus` (0-3点)

100点中 40点 (= 40%) が `japan_impact` （日本関連性）に振られていたため、

- 日銀利上げ・首相動静・国内大手企業決算 → 高得点
- ガザ・ウクライナ・米中対立・中央アジア再編 → 低得点（threshold 40 を下回る）

実 LLM 試運転 (2026-04-27 19:34) では Hydrangea が扱うべき記事が
ことごとく ViralFilter で棄却され、動画生成ゼロという事態が発生した。

### Hydrangea のミッションとの矛盾

Hydrangea のミッションは:

> 日本で報じられないニュース、視点が偏ったニュースを、地政学・歴史・文化・政治・
> 経済的背景の解説付きで日本人に届ける

本来 Hydrangea が選ぶべき記事は:

- 日本では報じられていない (= `japan_impact` が低い)
- 海外で大きく扱われている (= ブラインドスポット度合いが高い)
- 視点フレームが日本と違う
- 構造的な解説余地がある

旧 ViralFilter は「届けるべき記事」を「日本市場性が低い」という理由で却下していた。
これは設計と実態のミスマッチであり、フィルタの目的そのものを再定義する必要があった。

---

## 2. 7軸の定義と配点

EditorialMissionFilter は「Hydrangea 編集ミッション適合度」を 7 軸で評価する
（合計 100点満点）。

| 軸 | 配点 | 評価する観点 |
|---|---|---|
| `perspective_gap` | 25 | 日本 vs 海外の報道フレーム差。同じ事実を異なる文脈で語る差 |
| `geopolitical_significance` | 20 | 国際秩序・大国関係・歴史的潮流への影響 |
| `blindspot_severity` | 15 | 日本では報じられていない / 不当に小さく扱われている度合い |
| `political_intent` | 10 | 報道・出来事の裏にある政治的・組織的意図の解説余地 |
| `hidden_power_dynamics` | 10 | 表に出ない権力構造・利害関係・癒着の解説余地 |
| `economic_interests` | 10 | 経済的得失・ロビー活動・受益者構造の解説余地 |
| `discussion_potential` | 10 | 日本人視聴者の常識を揺さぶり議論を呼ぶ力 |

### 配点ロジック

- `perspective_gap` (25) — Hydrangea の核心。「視点が偏ったニュース」を
  「届けるべき」と判断する最重要シグナル。
- `geopolitical_significance` (20) — 「地政学解説付きで届ける」ミッションの裏付け。
- `blindspot_severity` (15) — 「日本で報じられない」ミッションの裏付け。
- `political_intent` / `hidden_power_dynamics` / `economic_interests` (各 10) —
  「背景解説」の余地を測る 3 軸。事実報道だけでなく構造を解説する力を評価。
- `discussion_potential` (10) — 視聴者に届くかどうかの最終チェック。
  バズりではなく「常識を揺さぶる」ことを基準にする。

「日本人がバズらせるか」ではなく「日本人に届けるべきか」を測る、というのが
全軸を貫く基準である。

---

## 3. Step1 prescore の計算式

`_editorial_mission_prescore(se: ScoredEvent) -> tuple[float, dict]` は
既存の `score_breakdown` 上の `editorial:*` 軸から 7 軸スコアを近似計算する。

| 出力軸 | 計算式 | 上限 |
|---|---|---|
| `perspective_gap` | `pg * 1.5 + cg * 1.0` | 25 |
| `geopolitical_significance` | `gd * 2.0 + bs * 1.0` | 20 |
| `blindspot_severity` | 後述の段階判定 | 15 |
| `political_intent` | `gd * 1.0 + bs * 0.5` | 10 |
| `hidden_power_dynamics` | `tg * 1.2 + gd * 0.3` | 10 |
| `economic_interests` | `be * 1.0 + ijai * 0.3` | 10 |
| `discussion_potential` | `ma * 0.7 + bs * 0.5` | 10 |

入力軸の凡例:
- `pg`   = `editorial:perspective_gap_score`
- `cg`   = `editorial:coverage_gap_score`
- `gd`   = `editorial:geopolitics_depth_score`
- `bs`   = `editorial:breaking_shock_score`
- `tg`   = `editorial:tech_geopolitics_score`
- `be`   = `editorial:big_event_score`
- `ma`   = `editorial:mass_appeal_score`
- `ijai` = `editorial:indirect_japan_impact_score`

### blindspot_severity の段階判定

`event.sources_by_locale` のソース数 + 視点有無を組み合わせて段階的に決定する:

```
has_en and not has_jp                          → 15.0
en_count >= 3 and jp_count <= 1                → 12.0
en_count >= 2 and jp_count == 0                → 10.0
en_count >= 2 and jp_count <= 1                →  8.0
それ以外                                         →  0.0
```

「日本で報じられず、海外で大きく扱われている」ほど高得点になる単調設計。

### prescore 全体の動作

- `raw = sum(7軸)` を計算し、`min(raw, 100.0)` で 100 に丸める。
- breakdown には全 7 軸 + `raw_total` + `step="prescore"` を保存。
- LLM が走らないか LLM が失敗した場合は prescore 値が最終 `editorial_mission_score` となる。

---

## 4. Step2 LLM プロンプトの全文

`MISSION_PRESCORE_TOP_N` 件 (デフォルト 20) の prescore 上位候補に対して、
judge LLM (Gemini Tier 階層) で 7 軸を再評価する。

LLM プロンプト全文:

```
あなたは独立メディア「Hydrangea」の編集長です。
Hydrangea のミッションは「日本で報じられないニュース、視点が偏ったニュースを、
地政学・歴史・文化・政治・経済的背景の解説付きで日本人に届ける」ことです。

以下のニュース候補について、Hydrangea の編集ミッションへの適合度を7軸で
評価してください。

## 候補
タイトル: {title}
要約: {summary}
日本語視点: {japan_view}
海外視点: {global_view}

## 評価軸（各軸の最高点を厳格に守ること）

1. perspective_gap (0-25点) — 視点ギャップ
   日本メディアと海外メディアの間で、報道フレーム・解釈・強調点がどれだけ違うか。

2. geopolitical_significance (0-20点) — 地政学・歴史的重要性
   この出来事が国際秩序・大国関係・歴史的潮流にどれだけ影響するか。

3. blindspot_severity (0-15点) — ブラインドスポット
   日本では報じられていない、または不当に小さく扱われている度合い。

4. political_intent (0-10点) — 政治的意図
   この報道・出来事の裏にある政治的・経済的・組織的意図を読み解く価値。

5. hidden_power_dynamics (0-10点) — 力関係の不可視性
   表に出ていない権力構造・利害関係・癒着を解説する価値。

6. economic_interests (0-10点) — 経済的利害
   この出来事の裏で、誰がどう経済的に得失するかを解説する価値。

7. discussion_potential (0-10点) — 議論誘発力
   日本人視聴者の価値観や常識を揺さぶり、議論を呼ぶ力。

## 重要な指示

- 「日本人がバズらせるか」ではなく「日本人に届けるべきか」で評価する
- 派手さ・感情的扇動ではなく、知的に重要かどうか
- 陰謀論ではなく、事実に基づいた構造的解説の余地があるか
- ReHacQ・東洋経済レベルの知的水準を基準にする

## 出力

以下のJSONのみを返してください。前置き・コードブロック・説明文不要。

{
  "perspective_gap": <0-25の整数>,
  "geopolitical_significance": <0-20の整数>,
  "blindspot_severity": <0-15の整数>,
  "political_intent": <0-10の整数>,
  "hidden_power_dynamics": <0-10の整数>,
  "economic_interests": <0-10の整数>,
  "discussion_potential": <0-10の整数>,
  "reason": "<このスコアの根拠を80字以内で>"
}
```

実プロンプトは `src/triage/editorial_mission_filter.py` の
`_MISSION_SCORE_PROMPT` 定数を正典とする（本ドキュメントは要約版）。

### 後処理

- LLM が返した各軸値は per-axis 上限 (25/20/15/10/10/10/10) でクランプ。
- markdown フェンス (\`\`\`json） で囲まれた応答も解釈可能。
- JSON parse エラー → `step: "llm", error: "json_parse_error:..."` を返却し
  prescore 値を保持。
- 429 RESOURCE_EXHAUSTED → `step: "llm", error: "quota_exhausted:..."` を返却し
  prescore 値を保持。

---

## 5. 閾値 45.0 の根拠

`MISSION_SCORE_THRESHOLD = 45.0` （`.env` の `MISSION_SCORE_THRESHOLD` で
上書き可能）。

### 暫定値である理由

- F-1 投入時点で実 LLM 評価データが 1 ラン分しかなく、通過率を決め打ちできない。
- Step1 prescore が低めに出る傾向がある (構造的に最大 100 点だが、
  典型的な記事は 30〜60 点レンジに収まると想定) ので 40 〜 50 のレンジが妥当。
- 旧 ViralFilter の閾値 40.0 より少し上げて、Step2 LLM が積極的にスコア改善を
  反映できる余地を残す。
- 47 や 50 のような中途半端値ではなく、5 刻みのキリのいい値にして
  運用ログでの議論しやすさを優先。

### 将来の調整

`docs/FUTURE_WORK.md` の「緊急度 中」に「EditorialMissionFilter 閾値の調整」を
登録済み。1〜2 週間の運用ログ（通過率・選ばれた記事の質）を分析して
40〜55 の範囲で再設定する予定。

---

## 6. 既存 score_breakdown 軸との対応

| EditorialMission 軸 | 主な入力 axis | 補助 axis |
|---|---|---|
| perspective_gap | `editorial:perspective_gap_score` | `editorial:coverage_gap_score` |
| geopolitical_significance | `editorial:geopolitics_depth_score` | `editorial:breaking_shock_score` |
| blindspot_severity | `editorial:has_en_view`, `editorial:has_jp_view` | `event.sources_by_locale` source counts |
| political_intent | `editorial:geopolitics_depth_score` | `editorial:breaking_shock_score` (粗い近似) |
| hidden_power_dynamics | `editorial:tech_geopolitics_score` | `editorial:geopolitics_depth_score` (粗い近似) |
| economic_interests | `editorial:big_event_score` | `editorial:indirect_japan_impact_score` |
| discussion_potential | `editorial:mass_appeal_score` | `editorial:breaking_shock_score` |

これらの axis はすべて `src/triage/scoring.py` の
`_score_editorial_axes()` で計算されており、本フィルタはその後段で参照のみ行う。

---

## 7. 制限事項 (Step1 の限界と対処)

`political_intent` / `hidden_power_dynamics` / `economic_interests` の 3 軸は
既存 `editorial:*` axis 体系に直接対応する入力がない。Step1 prescore では
近接する axis を使った粗い近似を行うのみで、本格的な評価は Step2 LLM が担う。

### なぜ Step1 で正確に計算しないか

- `src/triage/scoring.py` は **触っちゃダメリスト** に含まれており、
  新 axis の追加が許可されていない (CLAUDE.md 参照)。
- prescore はあくまで「LLM に投げる候補を粗く絞る」ための関門であり、
  最終判定は Step2 LLM で行う設計。
- `MISSION_PRESCORE_TOP_N=20` 件は LLM 評価の対象になるため、
  上位候補に限って言えば Step1 の近似誤差は最終スコアに反映されない。

### 将来の精緻化

`docs/FUTURE_WORK.md` の「scoring.py の新 axis 追加」項目で追跡:
触っちゃダメリスト見直し後、`editorial:political_intent_score` 等の
新 axis を追加して Step1 prescore に組み込む計画。

### F-1.5 で修正された設計上の制約

apply_editorial_mission_filter() は `why_rejected_before_generation` をセットするのみで、
`all_ranked` リストから rejected 候補を除外しない設計を採用している。

これは旧 ViralFilter からの継承で、後段の latest_candidate_report.md「Rejected Before Generation」
セクションが rejected 候補のメタデータ（score / breakdown / why_rejected）を引き続き参照できるようにするため。

ただし、Elite Judge 等の下流処理は **rejected 候補を除外する責務を負う**。F-1.5 では main.py の
Elite Judge 入力で `why_rejected_before_generation` を持つ候補を除外する処理を追加した。

---

## 8. データフローと既存パイプラインへの組込

```
ingestion → clustering → ranking → appraisal → rolling_window
                                                      ↓
                              [EditorialMissionFilter]   ← ここ
                                                      ↓
                                    Elite Judge → Judge → Script → Article
```

- `EDITORIAL_MISSION_FILTER_ENABLED=false` で完全スキップ可能。
- スキップ時は既存挙動 (Elite Judge → Judge へ全候補が流れる) を維持。
- `MISSION_LLM_ENABLED=false` で Step2 をスキップ (prescore のみ使用)。

### 出力フィールド

`ScoredEvent` に以下を設定する:

- `editorial_mission_score: Optional[float]` — 0-100, prescore か LLM の最終値
- `editorial_mission_breakdown: dict` — 7 軸の breakdown + `step` メタ
- `why_rejected_before_generation: Optional[str]` — 閾値未満なら理由文字列

`score_breakdown` dict に以下のキーを追記する:

- `mission_prescore` / `mission_prescore_breakdown` — Step1 結果
- `editorial_mission_score_llm` / `editorial_mission_breakdown_llm` — Step2 結果
- `editorial_mission_score` / `editorial_mission_breakdown` — 最終値（同期）

`run_summary.json` には `editorial_mission_filter` キーで集計値が出力される。

---

## 9. 旧 ViralFilter からの移行マッピング

| 旧 (ViralFilter) | 新 (EditorialMissionFilter) |
|---|---|
| `src/triage/viral_filter.py` | `src/triage/editorial_mission_filter.py` |
| `apply_viral_filter()` | `apply_editorial_mission_filter()` (シグネチャ同一) |
| `viral_filter_score` | `editorial_mission_score` |
| `viral_filter_breakdown` | `editorial_mission_breakdown` |
| `VIRAL_FILTER_ENABLED` | `EDITORIAL_MISSION_FILTER_ENABLED` |
| `VIRAL_LLM_ENABLED` | `MISSION_LLM_ENABLED` |
| `VIRAL_PRESCORE_TOP_N` | `MISSION_PRESCORE_TOP_N` |
| `VIRAL_SCORE_THRESHOLD` (40.0) | `MISSION_SCORE_THRESHOLD` (45.0) |
| `BudgetTracker.can_afford_viral_filter()` | `BudgetTracker.can_afford_editorial_mission_filter()` |
| `record_call("viral_filter")` | `record_call("editorial_mission_filter")` |

`build_why_slot1_won_editorially()` 関数名は変更なし（移植のみ）。
シグネチャは同一なので main.py 側の呼び出し変更は import + 関数名 + 変数名のみで完了する。

---

### F-2 で導入した FlagshipGate の Hydrangea 適合改修

F-1.5 試運転で、EditorialMissionFilter で通過した候補（北朝鮮ロシア軍事同盟、中東情勢等）が
src/triage/scheduler.py::_passes_flagship_gate() で「weak_japan」として弾かれる問題が発覚。

旧 FlagshipGate は ViralFilter 時代の設計で、`japan_relevance_score` / `indirect_japan_impact_score`
が低い候補を「日本で再生されない」として弾く設計だった。これは Hydrangea のコンセプトと矛盾する。

F-2 では `_passes_flagship_gate()` に以下のロジックを追加:

```python
if se.editorial_mission_score is not None and se.editorial_mission_score >= 45.0:
    return True, f"flagship_editorial_mission:score=..."
```

これにより EditorialMissionFilter の 7 軸で評価された候補は、weak_japan / no_depth 等の
旧基準を免除される。既存の get_flagship_class() ロジックは後方互換のため維持。

---

### F-3 で修正した PerspectiveSelector のフォールバック強化

F-2 試運転で、Slot-2 / Slot-3 の `analysis_result` が None になり動画化失敗する問題が発覚。

ログ証拠 (試運転6):
```
[Slot-2] Iran offers deal to US to reopen Strait of Hormuz...
event_id=cls-b574fcfd8cb3: analysis_result is None, skipping script generation. ★

[Slot-3] Russian superyacht crosses blockaded Strait of Hormuz
event_id=cls-74974ee82dbd: analysis_result is None, skipping script generation. ★
```

#### 真因

`src/analysis/perspective_selector.py::select_perspective()` で、LLM が Top3 外の axis
（典型的には `hidden_stakes`）を選び、かつ `fallback_axis_if_failed` も Top3 にない場合、
None を返す設計だった（試運転4 ログ参照）:

```
[PerspectiveSelector] LLM selected axis 'hidden_stakes' not in Top3 for event=cls-05572b4977f4
[AnalysisEngine] event=cls-05572b4977f4: perspective selection failed; falling back to legacy route.
[AnalysisLayer] Returned None for event=cls-05572b4977f4; falling back to legacy generation route.
```

つまり LLM の二重 fallback 失敗パターンで、Top3 に有効な候補が残っていても採用されず
動画化フローに到達できなかった。これは「1日5本（最低3本）の継続生成」体制構築の最大ブロッカーだった。

#### F-3 改修内容: 3 段階フォールバック

`select_perspective()` を以下のフォールバックチェーンに強化:

| Step | 条件 | 採用候補 |
|---|---|---|
| Step 1a | LLM `selected_axis` が Top3 にあり `actually_holds=True` | selected_axis 候補 (既存) |
| Step 1b | Step1a 不成立 + `fallback_axis_if_failed` が Top3 にある | fallback_axis_if_failed 候補 (既存) |
| Step 2 ★NEW | Step1a/1b いずれも不成立 | **Top3 内の最高スコア候補** |
| Step 3 ★NEW | candidates リスト自体が空 | None (最終安全網) |

加えて、LLM 呼び出しが例外で失敗した場合も Step 2 にフォールバックする（quota / transient 失敗時の救済）。

#### 効果

candidates が 1 件以上あれば必ず `PerspectiveCandidate` を返すため、Slot-2 / Slot-3 でも
`analysis_result` が None になることはなくなり、動画化が継続される。

各段階で fallback が発動した場合は WARNING ログを出して可視化する:
```
[PerspectiveSelector] Step2 fallback (F-3): LLM selected_axis='hidden_stakes' not viable
(in_top3=False, actually_holds=True), fallback_axis_if_failed='unknown_axis' also missing.
Using highest-scoring candidate: axis=framing_inversion (score=8.00) for event=cls-b574fcfd8c
```

#### 設計上の判断

- LLM が `hidden_stakes` 等を選ぶ事自体を抑止するのではなく、選ばれても Top3 に含まれていれば
  採用する形にした（プロンプトで Top3 内 axis を強制するより、運用で実害を防ぐ方が堅牢）。
- `framing_divergence_bonus` は Step 2 で採用された候補にも従来通り後加算される。

---

### F-4 で対応した AnalysisLayer の実行範囲拡張

F-3 で 3 段階フォールバックを実装後、試運転7-A で別の問題が発覚:

```
試運転7-A:
- Slot-1 (Australia green energy): analysis_result is None → skip
- Slot-2 (Iran ホルムズ): analysis_result 存在 → 動画化成功 ✅
- Slot-3 (Russian superyacht): analysis_result is None → skip
```

#### 真因

src/main.py の AnalysisLayer ブロックが Recency Guard 後の `all_ranked[0]` (slot-1) に対してのみ `run_analysis_layer()` を呼び、`override_top.analysis_result` にセットしていた。Slot-2 / Slot-3 の `analysis_result` は None のまま、後続の台本生成ループで skip されていた。

これは「1 日 5 本（最低 3 本）の継続生成」体制の最大ブロッカーだった。

#### F-4 改修内容

| 項目 | 旧 | 新 (F-4) |
|---|---|---|
| AnalysisLayer 実行範囲 | Slot-1 のみ | Top-N 全 Slot (default N=3) |
| 制御変数 | なし (固定) | `TOP_N_GENERATION` 環境変数 |
| 1 Slot 失敗時 | 全体 fallback | 当該 Slot のみ skip、他は続行 |

#### 効果

- Top-N 候補すべてで `analysis_result` が生成され、Slot-2 / Slot-3 でも台本生成可能に。
- 1 Slot あたり LLM 約 5 ~ 8 回の追加呼び出しが発生する想定 (Step 3 perspective_select_and_verify, Step 4 multi_angle, Step 5 insights, Step 6 duration_profile)。N=3 時は約 15 ~ 24 回の増加。
- `TOP_N_GENERATION=1` で F-3 以前の挙動（Slot-1 のみ実行）に戻せる。

#### 設計上の判断

- **Slot 間の独立性**: 1 Slot の AnalysisLayer 失敗は他 Slot に影響しない。各 Slot ループ内に try/except を配置。
- **Recency Guard は 1 回**: 全候補に対して一括で適用後、`all_ranked[:N]` を抽出する。重複適用は避ける。
- **`override_top` (= slot-1 確定)**: 既存挙動維持のため `all_ranked[0]` で設定する流れは変えない。
- **legacy fallback**: AnalysisLayer 全体の import エラー等は依然として既存の最外側 try/except で legacy ルートにフォールバック (現状維持)。

