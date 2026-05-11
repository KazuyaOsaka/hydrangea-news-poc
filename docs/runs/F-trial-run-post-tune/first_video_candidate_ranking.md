# Phase A.5-3b 第一作 題材候補ランク付け

最終更新: 2026-05-11 (F-trial-run-post-tune)

> 機械側 4 軸採点 + カズヤ主観 1 軸 (空欄、レビュー時に埋める)。
> 機械スコア 1 位 = 第一作の最有力候補だが、最終決定はカズヤ主観評価後。

---

## 採点ルール (Rubric)

| 軸 | 採点基準 | 範囲 | 採点者 |
|---|---|---|---|
| (1) Hydrangea ミッション整合度 | 「忖度・報道規制ぶち壊し」というブランドメッセージに合うか、systematic suppression の構造性 | 0-5 | 機械 |
| (2) 系統分類 | 系統 1=5pt / 系統 2=4pt / 系統 3=3pt / unknown=1pt | 1-5 | 機械 |
| (3) sontaku_signals.level | high=3 / medium=2 / low=1 / none=0 | 0-3 | 機械 |
| (4) 台本品質 | NG 語彙ゼロ +1、字数遵守 +1、Hook 構造明示 +1、Punchline 構造明示 +1、analysis_result 利用 +1 | 0-5 | 機械 |
| (5) カズヤ主観 (空欄) | カズヤレビュー時に『刺さるか』を 0-5 で評価 | 0-5 | カズヤ |

---

## データの注意点

- ★ **axis_2 (系統分類)**: 本番 production-pipeline では `verify_two_stage` が未配線のため、機械判別された stream は全て **unknown = 1pt** で評価。Phase A.5-3a-verify gate 完了後の概念整理 (4 分類化) は production-pipeline 上では未稼働。
- ★ **axis_3 (sontaku_signals)**: `sontaku_signals` フィールドは `src/` 配下 grep でヒット 0 件 = 本番未配線。全 Slot で 0pt 評価。
- ★ **axis_4 (台本品質)**: script 生成は Slot-1 のみ (F-16-A `article-only` mode により Slot-2/Slot-3 は article のみ)。
- ★ **axis_5 (カズヤ主観)**: 本バッチでは空欄、カズヤレビュー時に埋める。

---

## 機械スコア ランキング

| 順位 | Event ID | タイトル | 機械スコア | axis_1 | axis_2 | axis_3 | axis_4 | axis_5 |
|---|---|---|---|---|---|---|---|---|
| ★ 1 位 | `cls-6889e9e1c7ac` | 9,600 Detainees: Shocking Denunciation of Israel Prison Abuses | **10** | 5 | 1 | 0 | 4 | (空欄) |
| 2 位 | `cls-1a38c0ca8c99` | Filmmakers slam BBC after Gaza documentary wins award | **6** | 5 | 1 | 0 | 0 | (空欄) |
| 3 位 | `cls-03892eab2072` | Tehran says US proposal sought Iran's surrender | **5** | 4 | 1 | 0 | 0 | (空欄) |

---

## 候補別 採点根拠

### ★ 1 位: cls-6889e9e1c7ac — 9,600 Detainees: Israel Prison Abuses

- **RSS ソース**: TeleSUR (en/VE/latin_america, state_aligned, ベネズエラ政府系)
- **概要**: パレスチナ囚人擁護センターがイスラエル当局を告発 — 国内刑務所に収容されている 9,600 人以上のパレスチナ人に対する組織的虐待を隠蔽するため、ICRC (赤十字国際委員会) の訪問調査を制限・操作している、と。
- **本番 status**: Slot-1 (動画 payload + script + article + evidence 生成済み、動画レンダリング前)
- **採点根拠**:
  - **(1) Hydrangea ミッション整合度 = 5/5**
    - `editorial_mission_score=86.0` で本試運転 3 Slot 中最高
    - perspective_gap=22, blindspot=14, political_intent=9, hidden_power=9 で 4 軸全て高評価
    - トピックは国際人権侵害 + 国際機関 (ICRC) への忖度 + システムバイアス
    - 4 分類のうち **1.制度・システム面** + **3.個人・権力者面 (上級国民層への構造的配慮)** に該当
    - LLM コメント: 「日本で報じにくい人権問題と国際機関への操作は、視点ギャップとブラインドスポットが極めて大きい。地政学的・歴史的背景、政治的意図、力関係の解説余地も高い」
  - **(2) 系統分類 = 1/5 (unknown)**
    - production verify_two_stage 未配線、has_jp_coverage=True (afpbb Tier 2) のみ
    - docs 観点では 系統 2 (perspective_gap) 候補だが機械判別は出ていない
  - **(3) sontaku_signals.level = 0/3 (null)**
    - 本番未配線、null 扱い
    - docs 観点では 「観点の選択的欠落 = 忖度」軸では high 候補だが、メタデータ未付与
  - **(4) 台本品質 = 4/5**
    - NG 語彙ゼロ: ✅ +1
    - 字数遵守: ✅ +1 (hook 18字, setup 90字, twist 179字, punchline 87字、全 char bounds 内)
    - Hook 構造明示: ✅ +1 (数字提示型 「9,600人。今、消された人々の数。」)
    - Punchline 構造明示: ✅ +1 (シニカル × 視聴者直接質問 「あなたは、まだ世界が平等だと言えますか？」 + loop-3 で hook 数字に帰着)
    - analysis_result 利用: ❌ 0 (analysis_result=null、新ルート未配線で旧ルート使用)
  - **(5) カズヤ主観 = 空欄**
    - Hook「9,600人。今、消された人々の数。」が刺さるか
    - Punchline「あなたは、まだ世界が平等だと言えますか？」が視聴者着地として強いか
    - Media Critique パターン + 大手メディア批判の構図が Hydrangea ブランドとして妥当か
    - TeleSUR (ベネズエラ政府系) のみがソースという信頼性スコープが許容範囲か
- **機械スコア合計**: **10pt** (1+2+3+4 全合計)

### 2 位: cls-1a38c0ca8c99 — Filmmakers slam BBC after Gaza documentary

- **RSS ソース**: Middle_East_Eye (en/GB/middle_east, bridge_source)
- **概要**: BBC が放送中止にしたガザ医療従事者ドキュメンタリー (Gaza: Doctors Under Attack) が BAFTA TV 賞を受賞、製作陣が公的に BBC の自己検閲・パレスチナの声排除を非難。Channel 4 が代替放送した。
- **本番 status**: Slot-2 (article のみ、F-16-A article-only mode で script/video 未生成)
- **採点根拠**:
  - **(1) Hydrangea ミッション整合度 = 5/5**
    - `editorial_mission_score=77.0` (perspective_gap=22, blindspot=13, political_intent=8, hidden_power=8)
    - 4 分類のうち **1.制度・システム面 (報道規制・自由度の低さ)** に直接該当
    - LLM コメント: 「ガザ報道の視点ギャップ、主要メディアの自己検閲と権力構造、情報操作の可能性を解き明かす価値が高い」
    - Hydrangea コアミッションど真ん中
  - **(2) 系統分類 = 1/5 (unknown)**
    - production verify_two_stage 未配線、has_jp_coverage=True (afpbb Tier 2) のみ
    - docs 観点では 系統 2 (perspective_gap = BAFTA 受賞ニュースは日本でも報道される可能性 + BBC 検閲側面は未報道) 候補
  - **(3) sontaku_signals.level = 0/3 (null)**
    - 本番未配線、0pt
    - docs 観点では `sontaku_signals.type=media_industry` (媒体業界の構造的忖度) に該当する可能性
  - **(4) 台本品質 = 0/5**
    - F-16-A article-only mode で script 生成スキップ、評価不能のため 0pt
  - **(5) カズヤ主観 = 空欄**
    - BBC 自己検閲事件は Hydrangea 第一作として題材として刺さるか
    - ガザ medical 攻撃 + メディア規制の二重構造を 80 秒台本で表現できるか (script 生成は次回試運転待ち)
- **機械スコア合計**: **6pt**

### 3 位: cls-03892eab2072 — Tehran says US proposal sought Iran's surrender

- **RSS ソース**: Middle_East_Eye (en/GB/middle_east, bridge_source)
- **概要**: イラン国営テレビが、米国の最新和平提案を「降伏要求」として拒否。最高指導者の死亡 (2026-02-28 戦争で) を含む戦争被害への賠償・凍結資産解除・ホルムズ海峡・核問題交渉を要求。
- **本番 status**: Slot-3 (article のみ、F-16-A article-only mode で script/video 未生成)
- **採点根拠**:
  - **(1) Hydrangea ミッション整合度 = 4/5**
    - `editorial_mission_score=83.0` (perspective_gap=22, blindspot=12, political_intent=9, hidden_power=8)
    - Gemini Judge で **blind_spot_global** 認定 (score=9.0, confidence=0.9) = 系統 1 期待値の最強候補
    - 4 分類のうち **2.外交・経済バイアス (特定国への忖度、米国)** に該当
    - LLM コメント: 「イランの異例な主張が示す地政学的背景と国内政治の意図は、日本で報じられにくい」
    - Slot-1 ほど Hydrangea ど真ん中 (人権・権力構造ぶち壊し) ではないが、blind_spot_global 明示で強い
  - **(2) 系統分類 = 1/5 (unknown)**
    - production verify_two_stage 未配線
    - F-13.B = has_jp_coverage=True (nippon Tier 4 補助層)
    - judge = blind_spot_global → F-13.B と judge の結論不一致 (注目点)
  - **(3) sontaku_signals.level = 0/3 (null)**
    - 本番未配線、0pt
    - docs 観点では `sontaku_signals.type=diplomatic` (特定国/米国への外交的配慮) に該当する可能性
  - **(4) 台本品質 = 0/5**
    - F-16-A article-only mode で script 生成スキップ、0pt
  - **(5) カズヤ主観 = 空欄**
    - Tehran 系の地政学トピックは Hydrangea 第一作として刺さるか
    - blind_spot_global judge スコア 9.0 が強い根拠だが、ベース情報 (Middle East Eye 単独ソース) の信頼性スコープは許容範囲か
    - 「最高指導者ハメネイ師の死」という極めて重い前提が含まれる情報の扱い (real-world status 検証要)
    - 巨大 cluster 警告 (giant cluster 112 articles の親トピックと近接) の影響
- **機械スコア合計**: **5pt**

---

## カズヤ確認推奨事項

1. **本ランクは機械スコアのみ。axis_5 (カズヤ主観) は未評価**。第一作の最終決定はカズヤレビュー後。
2. **Slot-1 (機械スコア 1 位) は editorial_mission_score=86.0 + 動画 payload 生成済み**で第一作の最有力候補。
3. Slot-2/Slot-3 は再試運転して script 生成しない限り axis_4 で再評価できない。
4. **F-13.B WL ヒット品質** (`matched_urls` がベアドメインのみ問題) の独立検証を推奨 (= afpbb / nippon が本当に当該事象を報道しているか)。
5. axis_2/axis_3 が全 Slot で 1pt/0pt = production-pipeline 上で系統判別 + 忖度シグナルが未配線。判別配線バッチ (= F-stream-2-filter-design or 並走バッチ) が次フェーズで必要。

---

*本ドキュメントは F-trial-run-post-tune Task F で自動生成。
機械側採点 (axis 1-4) は Claude Code が trial_run_log.json + script_quality_audit.json + f13b_output_analysis.json から導出。
カズヤ主観評価 (axis 5) は本ドキュメントレビュー時に直接埋めるか、別途承認手順で確定する。*
