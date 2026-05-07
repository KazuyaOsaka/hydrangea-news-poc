# Hydrangea — 「特定角度」(particular_angle) 概念の正典定義

最終更新: 2026-05-07 (F-particular-angle-redesign / 2026-05-07 完了 — 3 分類 → 4 分類化)

> このドキュメントは Hydrangea コアミッション (CURRENT_STATE.md セクション 0、
> 2 系統並立) を実装に翻訳する上での **判定単位** を明文化する正典である。
> 系統 1 (silence_gap) と系統 2 (framing_inversion) の判定基準が「広範な
> 事件レベル」のままだと両系統の重複ケースが避けられず、F-stream-2-filter-design
> および F-jp-coverage-tune の仕様化が曖昧になる。本ドキュメントは判定対象を
> 「特定角度」に限定することで重複を構造的に消し、後続バッチに共通基盤を
> 提供する。
>
> ★ F-particular-angle-redesign (2026-05-07) で **3 分類 (系統 1 / 系統 2 /
> 動画化対象外) → 4 分類 (系統 1 / 系統 1.5 / 系統 2 / 動画化対象外)** に
> 再構成された。系統 1 の中に「広範事件も特定角度も両方未報道」と「広範事件
> は報道済み + 特定角度のみ未報道」が混在する構造的不備を、系統 1.5
> (perspective_gap) を新設することで解消した。

---

## 1. なぜこの概念が必要か

Hydrangea のコアミッションは「日本未報道の大ニュース (silence_gap)」と
「日本/西側 vs 海外/東側 の報道差の背景解説 (framing_inversion + 構造分析)」
の 2 系統並立である (詳細は `docs/CURRENT_STATE.md` セクション 0)。
F-13.B JpCoverageVerifier (rescue 完全廃止 + Web 検証 + ドメイン抽出層、
2026-05-07 に F-jp-coverage-improve で構造的不具合を根本治療) が
「日本未報道か否か」の機械的判定を担う一方、系統 2 (= 報道差の質判定 +
解説価値判定) を担う 2 段階フィルタ (F-stream-2-filter-design) はまだ
未実装である。F-trial-run-post-fix (2026-05-07) で行った試運転と過去 7-K
動画化 3 件の WebSearch 後追いで、Hydrangea が動画化すべき素材は
「広範事件は既に日本主要メディアで報道済みだが、MEE/海外メディアが独自に
掘った特定角度は未報道」というパターンが多発することが確認された。
具体例として試運転 Slot-1 (Insider trading: Oil and stocks jolt on news of
US-Iran deal) は nikkei.com (Tier 1) と jiji.com / bloomberg.co.jp
(Tier 2) で米イラン和平交渉の進展自体が広範に報道されているが、合意
報道の 70 分前に約 9.2 億ドルの原油ショートが構築され、報道直後に
約 1.25 億ドルの利益が出たという「外交情報の金融商品化」「国家規模の
インサイダー取引」という MEE オリジナル角度は日本主要メディアで深掘り
されていない。過去 7-K Slot-2 (Mandelson) も同形で、人事スキャンダル
本体は Tier 1-2 で広範報道済みだが、英国によるガザ向け F-35 部品継続
供給とアクロティリ基地監視飛行という「英国の構造的なイスラエル軍事支援
こそが本来の道徳的負債」という MEE オピニオンの核心角度は日本では未報道
である。

このパターンを系統 1 と系統 2 のどちらで処理すべきかは、判定対象を
「広範事件」レベルで取ると両系統で重複してしまう。広範事件 (米イラン
和平交渉本体、マンデルソン人事スキャンダル本体) は日本で報道済みなので
系統 1 (silence_gap) では拾えないが、報道差の解釈という観点からは
広範事件レベルでは「同じことを報道している」と読める。したがって系統 2
の判定基準を「広範事件についての報道差」とすると、Hydrangea が動画化
したい『MEE オリジナルの構造分析角度』は両系統からこぼれ落ちる。逆に
判定基準を「特定角度」(海外メディアが独自に掘った視点) に限定すれば、
系統 1 は『その特定角度が日本主要メディアで未報道』を判定し、系統 2 は
『その特定角度は報道済みだが解釈・フレーミング・優先順位が日本/西側 vs
海外/東側で異なる』を判定する、という相互排他な責務分離が成立する。
カズヤとの 2026-05-07 議論で確立された結論は「重複しないように定義
すればよくね?」 = 判定対象を『特定角度』に限定すれば重複は構造的に
消える、というものだった。本ドキュメントはこの判定基準を後続バッチが
共通参照できる正典として固定化する。

### 1.1 3 分類の構造的不備と 1.5 分類追加の経緯 (F-particular-angle-redesign / 2026-05-07)

F-particular-angle-design (2026-05-07) で 3 分類版 (系統 1 / 系統 2 /
動画化対象外) を確立し、25 件の LLM ベースアノテーションを完了した。
続くカズヤレビュー過程で、3 分類の構造的不備が明らかになった。具体的には
blind_002 (Israel ラビ庁) / blind_004 (Gaza 潤滑油 100 倍) / blind_009
(Iran-US 戦争長期化) のような事象群で『広範事件は日本主要メディアで報道
済み、特定角度のみ未報道』というパターンが多発しており、これらは LLM
判定では「特定角度ベース」で stream_1_silence_gap に分類されるが、台本
表現としては『日本では報じられていない』と書くと嘘になり、視聴者からの
ツッコミを誘発するリスクが残る。

この発見を受け、カズヤから 2026-05-07 のレビュー時に「一部報道だけど
観点不足っていう 1.5 分類儲けてもいいのかもしれない」と提案され、議論
の結果 4 分類化が必要との結論に到達した。系統 1 の中に「広範事件も特定
角度も両方未報道 (= 完全空白)」と「広範事件は報道済み + 特定角度のみ
未報道 (= 観点不足)」が混在する構造的問題を、系統 1.5 (perspective_gap)
を新設することで分離する。これにより、台本表現の方向性が分類別に明確化
され (系統 1 は「日本では報じられなかった」、系統 1.5 は「事件自体は
報じられたが、◯◯という構造には触れられなかった」、系統 2 は「日本の
メディアは××と捉えたが、海外では△△と批判されている」)、F-13.B
JpCoverageVerifier の二段階クエリ生成 (広範事件クエリ + 特定角度クエリ)
の責務も明確化され、F-stream-2-filter-design の責務範囲も縮まる
(= 系統 2 のみ担当、系統 1.5 は F-jp-coverage-tune の範疇)。F-particular-angle-redesign
(2026-05-07) で本改訂を実施し、PARTICULAR_ANGLE_DEFINITION.md セクション 3 を
4 分類対応に大幅改訂、annotations.json を 4 分類版で再分類、台本表現
ガイドライン (新サブセクション 3.5) を追加した。

## 2. 「特定角度」とは何か

「特定角度」(particular_angle) とは、海外メディア (Hydrangea 入力 RSS
41 媒体) が当該事象に対して **独自に掘った視点・問題意識・分析切り口**
である。広範事件 (= 事象そのもの、例: 米イラン和平交渉合意進展、
マンデルソン人事スキャンダル) ではなく、その事象の中で海外メディアが
強調している『誰が何をどう問題視しているか』『既存の主流フレームで
扱われていない構造分析』『日本の主流メディアでは見落とされている解釈』
の 1 ピース、と理解する。

特定角度は以下の 3 要素で構成される。

第一に、**誰が何をどう問題視しているか**。記事を書いている海外メディア
(MEE, Meduza, Al Jazeera 等) の編集視点、または記事内で引用されている
専門家・活動家・現地住民の声が、どの構造的問題を指弾しているかを 1〜2 文
で表現する。例: Insider trading の場合『市場参加者が、米国政府高官の
外交合意発表前に巨額の原油ショートが立てられたことを、外交情報を金融
商品として悪用する国家規模のインサイダー取引であると問題視している』。
これは広範事件 (米イラン和平交渉本体) ではなく、その事象の周辺で起きた
特定の市場挙動への構造分析角度である。

第二に、**既存報道との差**。同じ事象を扱う他メディア (特に日本主要紙、
あるいは欧米メインストリーム) が何を強調し、海外メディアの当該記事が
何を強調しているかの『差分』を明確化する。例: マンデルソン Gaza scandal
の場合『日本主要紙 + Bloomberg JP は人事スキャンダル本体 (エプスタイン
氏との関係 + セキュリティ事前審査) を報道、MEE オピニオンは英国による
F-35 部品継続供給 + アクロティリ基地監視飛行 = ガザ情勢への構造的加担
こそ本来の道徳的負債と批判』。差分は事実 (factual) ベースの差ではなく、
解釈フレームの差として記述する。

第三に、**Hydrangea 編集ミッション (4 軸) との整合**。系統 1 の判定基準
として既に明文化された 4 軸 (制度・システム / 外交・経済・利害関係 /
個人・権力者 / 関心領域・地政学的死角、DISCUSSION_NOTES「系統 1
判定基準明確化」エントリ参照) のどれに該当するかを 1 軸特定する。
複数軸該当の場合は最も核心的な 1 軸を優先する。例: Insider trading は
『第 2 軸 (外交・経済・利害関係面、米国忖度) + 第 3 軸 (個人・権力者面、
トランプ政権中枢の市場操作疑惑)』で、より核心は第 2 軸 (米国忖度に
よる Hydrangea 動画化の典型) となる。この 4 軸整合は系統 1 と系統 2 の
両方で動画化価値判定に使う共通装置として機能する (= 4 軸該当が無い
特定角度は『単に専門ニッチ』『他国オピニオンの個人見解』に留まり、
Hydrangea としては動画化対象外)。

## 3. 「特定角度」を使った系統判定基準 (4 分類)

★ F-particular-angle-redesign (2026-05-07) で **3 分類 → 4 分類** に再構成。
特定角度を判定単位として使うと、Hydrangea が処理すべき海外ニュースは
以下の 4 つに排他的に分類される。

**系統 1 (silence_gap)**: **広範事件も特定角度も両方** 日本主要メディアで
未報道。動画化対象の核心 (= 特定角度) が未報道で、4 軸構造的バイアスの
いずれかに該当し、かつ広範事件レベルでも未報道の事象。完全な情報空白で、
Hydrangea コアミッションど真ん中。台本表現としては「日本では報じられ
なかった」という言い方が自然に成立する。

**系統 1.5 (perspective_gap、F-particular-angle-redesign で新設)**:
広範事件は日本主要メディアで報道済みだが、**特定角度は未報道**。動画化
対象の核心 (= 特定角度の構造分析) が日本では深掘りされていない事象。
事件本体は報道済みなので「日本では報じられなかった」と書くと嘘になり、
台本表現としては「日本でも事件は取り上げられたが、◯◯という構造には
触れられていない」になる。F-13.B の現実装は広範事件クエリ
(`title + 日本 報道`) で報道済み判定するため、現状では系統 1.5 を捕捉
できず系統 2 候補に流れているが、F-jp-coverage-tune の二段階クエリ
生成 (広範事件クエリ + 特定角度クエリ) で機械化可能。

**系統 2 (framing_inversion)**: 広範事件も特定角度も日本主要メディアで
報道済みだが、**解釈・フレーミング・優先順位** が日本/西側 vs 海外/東側
で異なる。動画化対象の核心 (= 特定角度) は報道されているが、解釈の差
が解説価値を生む事象。台本表現は「日本のメディアは××と捉えたが、海外
では△△と批判されている」になる。ここでは『その特定角度そのものの
解釈差』を扱うのであって、広範事件レベルの解釈差は対象ではない。
F-stream-2-filter-design の責務範囲。

**動画化対象外**: 特定角度が日本主要メディアで報道済みかつ解釈も同じ
(= 単に同じ内容が報道されているだけ)、または 4 軸構造的バイアスに該当
しない (= 単に専門ニッチ、他国オピニオンの個人見解、報道価値が低い)
事象。

### 3.1 判定の論理フロー (4 分類版)

判定の論理フローは以下の通り (上から順に評価する)。Step 2 と Step 3 を
分離することで「広範事件と特定角度の両方の報道状態」を独立に判定する
点が、3 分類版からの構造的変化である。これは F-jp-coverage-tune の
二段階クエリ生成 (広範事件クエリ + 特定角度クエリ) の責務分離に直結する。

```
[海外ニュース入力]
    ↓
[Step 0: 特定角度を抽出する (LLM ベース)]
    ↓
[Step 1: 特定角度が 4 軸のいずれかに該当するか?]
    No → 動画化対象外
    Yes ↓
[Step 2: 広範事件が日本主要メディアで報道済みか?]
    No → ↓ (Step 3 へ; 広範事件未報道フラグを保持)
    Yes → ↓ (Step 3 へ; 広範事件報道済みフラグを保持)

[Step 3: 特定角度が日本主要メディアで報道済みか?]
    No (Step 2 で広範事件も未報道) → 系統 1 (silence_gap)
    No (Step 2 で広範事件は報道済み) → 系統 1.5 (perspective_gap) ★ NEW
    Yes ↓
[Step 4: 解釈・フレーミング・優先順位が日本/西側 vs 海外/東側で異なるか?]
    No → 動画化対象外 (単に同じ内容が報道済み)
    Yes → 系統 2 (framing_inversion)
```

Step 2 / Step 3 の「日本主要メディアで報道済みか」は F-13.B
(JpCoverageVerifier) の責務範囲だが、判定対象が「広範事件」と「特定角度」
の **2 段階** に分離されている点が新しい。F-13.B の現実装は title + " 日本
報道" を Grounding クエリとして投げるので広範事件レベルの照合に留まる。
この乖離は F-jp-coverage-tune (FUTURE_WORK 緊急度 高) で **二段階クエリ
生成** として対処する想定で、本バッチ (F-particular-angle-redesign) では
4 分類対応のアノテーションデータを F-jp-coverage-tune の入力として準備
する位置付けに留める。

Step 4 の「解釈差」判定は F-stream-2-filter-design (FUTURE_WORK 緊急度
高) で実装する 2 段階フィルタの後段が担う。F-particular-angle-redesign
での 4 分類化により、F-stream-2-filter-design の責務範囲は **系統 2 のみ**
に縮まる (系統 1.5 は F-jp-coverage-tune の範疇に移行)。これにより、
F-stream-2-filter-design の解説価値判定 LLM プロンプトは「広範事件も特定
角度も日本で報道済みであることを前提に、解釈差を判定する」というシンプル
な責務に専念できる。

### 3.2 25 件アノテーションの想定分布 (4 分類版)

F-particular-angle-redesign で 25 件を 4 分類対応で再分類した結果の想定
分布は以下の通り (LLM 推定段階、実際の分布は再分類後の `annotations.json`
+ `stream_classification.json` を参照)。

| 分類 | 件数 (想定) | 比率 | 代表事例 |
|---|---|---|---|
| 系統 1 (silence_gap) | 約 6 件 | 約 24% | blind_001/003/007/010 + 試運転 ロシア焼身 + 試運転 Met Police |
| 系統 1.5 (perspective_gap) | 約 5 件 | 約 20% | blind_002/004/009 等 (3 分類版で stream_1 だが広範事件は報道済み) |
| 系統 2 (framing_inversion) | 約 13 件 | 約 52% | covered 系列 9-11 件 + 試運転 7-K Slot-1 (FIFA) / Slot-2 (Mandelson) |
| 動画化対象外 | 1 件 | 約 4% | covered_006 (NVIDIA 株) |

実際の再分類結果は `docs/runs/F-particular-angle-redesign/REPORT.md`
セクション 3-6 + `docs/runs/F-particular-angle-design/annotations.json`
(本バッチで 4 分類版に上書き、旧 3 分類版は `annotations_v1_3class.json`
にバックアップ) を参照。

## 3.5: 系統別の台本表現の方向性 (F-particular-angle-redesign で新設)

★ カズヤとの 2026-05-07 議論で確立された設計哲学に従い、台本表現は
以下の方向性で **LLM の知性に委ねる** 設計を採用する。具体的な言い回し
最適化は Phase A.5-3b 手動 PoC で 1 本作りながら試行錯誤する設計で、
本ドキュメントは メタデータ構造の確定までを担当する。

### 3.5.1 設計哲学

- **言い回しを個別ルールで指定しない** — ルール累積で全体劣化を回避する。
  「系統 1 のときは『〜は報じられなかった』と書け」のような言い回し強制
  ルールを script_writer.py のプロンプトに加えると、ルールが増えるほど
  台本生成 LLM の自由度が削られて全体品質が劣化する経験則 (F-12-B-1
  視聴者ファースト 3 原則導入の動機と整合)。
- **article_writer.py は触らない** — 不変原則 1、記事クオリティの核心
  であり、本バッチを含む後続バッチでも一切変更しない。
- **script_writer.py 新ルートに particular_angle メタデータを渡す** —
  LLM が自分で文脈に応じた言い回しを選択する設計。具体的には系統別の
  メタデータを構造化して渡し、LLM が『広範事件は報道済みだが特定角度は
  未報道』のような状態を理解した上で言い回しを選ぶ。

### 3.5.2 メタデータ構造 (script_writer.py 新ルート入力)

```python
particular_angle_metadata = {
    "stream_classification": "stream_1_silence_gap"
                          | "stream_1_5_perspective_gap"
                          | "stream_2_framing_inversion"
                          | "out_of_scope",
    "core_question": "<特定角度の核心、1-2 文>",
    "differentiation_from_mainstream": "<既存報道との差、1-2 文>",
    "hydrangea_axis_alignment": "<4 軸該当性、1 軸特定>",
}
```

このメタデータ構造は F-stream-2-filter-design (系統 2 担当) +
F-jp-coverage-tune (系統 1 vs 1.5 判別担当) の出力フォーマットでもある。
両バッチで同じ構造のメタデータを生成し、script_writer.py 新ルートに
パススルーする責務分担とする。

### 3.5.3 台本 LLM が選択する言い回しの例 (例示、ルール強制ではない)

LLM は メタデータの `stream_classification` フィールドを見て、以下の
ような言い回しを **自律的に選択** する想定。あくまで例示であり、台本
LLM への強制ルールとしては書かない (= プロンプトには「メタデータを
踏まえて自然な日本語で語る」程度の指示に留める)。

- **系統 1 (silence_gap)** → 「この事件は日本のメディアで一切報じられ
  なかった」「日本の主流メディアでは黙殺されてきた」
- **系統 1.5 (perspective_gap)** → 「事件自体は報じられたが、◯◯という
  構造的問題には触れられなかった」「日本でも事件は取り上げられたが、
  本質的な角度は欠落していた」
- **系統 2 (framing_inversion)** → 「日本のメディアは××と捉えたが、
  海外では△△と批判されている」「同じ出来事を、日本と海外では全く
  異なる角度から論じている」

### 3.5.4 自動化への到達経路

- F-particular-angle-redesign (本バッチ): 4 分類確定 +
  particular_angle_metadata 構造の正典化
- F-jp-coverage-tune: 二段階クエリ生成で広範事件 vs 特定角度の報道状態
  を独立判定 → `stream_classification` を `stream_1` / `stream_1_5` /
  (報道済み) で機械的に分類
- F-stream-2-filter-design: (報道済み) 候補に対して解釈差判定 →
  `stream_classification` を `stream_2` / `out_of_scope` で機械的に分類
- Phase A.5-3b 手動 PoC: 1 本目の素材で言い回しを試行錯誤、最適表現を
  プロンプトに反映 (ルール強制ではなく『参考事例』として埋め込む)
- 最終形態: script_writer.py 新ルートに `particular_angle_metadata` を
  渡し、LLM が自律選択

参照: `docs/DISCUSSION_NOTES.md` 「2026-05-07: 台本表現:特定角度未報道
のナレーション課題」(本バッチで `Resolved (本ドキュメントで方向性確定、
Phase A.5-3b で実装試行)` に更新)。

## 4. 「特定角度」抽出の実装方針

「特定角度」抽出は LLM ベースで行う。決定的ルール (キーワードマッチ
等) では海外メディアが独自に掘った視点を捉えきれず、Hydrangea コア
ミッションと整合する 4 軸該当性も判定できないためである。F-particular-angle-design
(2026-05-07) で実装した `scripts/extract_particular_angle.py` は事前に
25 件のゴールデン候補に対してアノテーション抽出を行い、F-stream-2-filter-design
/ F-jp-coverage-tune の入力として整備した。F-particular-angle-redesign
(本バッチ) では同じ 25 件を 4 分類対応で再分類する `scripts/reclassify_annotations.py`
を新規追加し、`particular_angle` 自体は保持しつつ
`stream_classification_estimate` を 4 分類で上書きする運用とした。

LLM プロンプト設計の方向性は以下の通りである。第一に、入力として
event_id + title + summary + sources (RSS 媒体名) のみを与え、3 要素
(core_question / differentiation_from_mainstream / hydrangea_axis_alignment)
を構造化された JSON として抽出させる。第二に、各要素には `confidence`
ラベル (high/medium/low) を付与させ、LLM が抽出に自信を持てない場合は
medium / low を返すように指示する。confidence=low の件数が多すぎる場合
(例: 25 件中 5 件以上) はプロンプト改善の余地ありとして次バッチで対処
する。第三に、抽出と同時に系統判定 (stream_1_silence_gap /
stream_1_5_perspective_gap / stream_2_framing_inversion / out_of_scope)
の estimate を出させ、カズヤレビュー時に LLM 判断と人間判断の差分を
可視化できるようにする。LLM 推定は確定値ではなく、カズヤレビュー後の
`kazuya_review.*_revised` フィールドが正本となる。

★ F-particular-angle-redesign (2026-05-07) で 4 分類対応 (Step 1-4 論理
フロー) に LLM プロンプトを更新した。`scripts/reclassify_annotations.py`
は『広範事件報道状態』と『特定角度報道状態』の両方を `reasoning` に
明記させる設計で、これは F-jp-coverage-tune の二段階クエリ生成における
判定基準の参考実装としても機能する。

LLM モデルは Gemini Flash (analysis role の Tier 階層) を採用する。
既存 LLMClient 抽象 (`src/llm/factory.py` の `get_analysis_llm_client()`)
経由で呼び出すことで、プロジェクト全体の LLM 呼び出し方針 (役割別
クライアント / Tier フォールバック / 予算管理) と整合させる。
temperature は 0.3 (analysis role デフォルト) で『事実重視』設定を
踏襲する。max_output_tokens は 4096 を明示指定する (既定の analysis
client の 2000 では JSON 途中切断のリスクがあることを F-particular-angle-design
で覚知済み)。

「特定角度」抽出の難所は以下の通りである。第一に、海外メディアの記事
本体 (article body) ではなく title + summary のみで判定するため、
記事内で詳細に展開される構造分析角度を見落とす可能性がある。
F-particular-angle-design では本バッチのスコープを title + summary
ベースに限定したが、F-stream-2-filter-design 実装時は記事本体の
content も入力に加えるかどうか議論する余地がある。第二に、海外
メディア自身が複数の特定角度を 1 記事に詰め込んでいる場合 (例:
MEE の長尺オピニオン記事)、最も核心の 1 角度に集約する必要があり、
LLM の集約バイアス (いつも同じ角度を抽出する偏り) が出やすい。
第三に、Hydrangea の 4 軸該当性判定は LLM のドメイン知識依存で、
特に第 3 軸 (個人・権力者面) は日本国内文脈の理解 (記者クラブ /
クロスオーナーシップ等) が必要なため、海外メディア記事だけからは
判定が難しい場合がある。これらの難所は本バッチの抽出結果で
extraction_confidence=low の事例を観察することで定量的に把握し、
F-stream-2-filter-design で本実装する際のプロンプト改善材料に転用する。

## 5. 関連ファイル

### 5.1 F-particular-angle-design (2026-05-07、3 分類版確立) で生成

- `docs/runs/F-particular-angle-design/annotations.json` — 25 件の
  LLM ベースアノテーション (★ F-particular-angle-redesign で 4 分類版
  に上書き、旧 3 分類版は `annotations_v1_3class.json` にバックアップ)
- `docs/runs/F-particular-angle-design/annotations_v1_3class.json` —
  3 分類版アノテーションのバックアップ (F-particular-angle-redesign で生成)
- `docs/runs/F-particular-angle-design/input_events.json` — 入力 25 件の
  統合データ (golden_set 19 + 試運転 7-K 3 + 試運転 2026-05-07 3)
- `docs/runs/F-particular-angle-design/review_draft.md` — カズヤレビュー
  用の人間読みドラフト (3 分類版、★ F-particular-angle-redesign で
  カズヤレビュー対象は `review_draft_v2.md` に移行)
- `scripts/extract_particular_angle.py` — LLM ベース特定角度抽出
  バッチスクリプト (F-particular-angle-design で作成、本バッチでは未変更)
- `scripts/finalize_annotations.py` — カズヤレビュー後の最終化
  スクリプト (F-particular-angle-design で作成、★ F-particular-angle-redesign
  で 4 分類対応 `--schema-version 2.0` オプション追加)

### 5.2 F-particular-angle-redesign (2026-05-07、4 分類化) で生成

- `docs/runs/F-particular-angle-redesign/reclassification_log.json` —
  4 分類化 LLM 再判定実行ログ
- `docs/runs/F-particular-angle-redesign/reclassification_diff.json` —
  旧 3 分類 → 新 4 分類の差分集計
- `docs/runs/F-particular-angle-redesign/review_draft_v2.md` — 4 分類版
  カズヤレビュー用ドラフト (3 分類 → 4 分類への変更箇所を冒頭で重点表示)
- `docs/runs/F-particular-angle-redesign/REPORT.md` — 統合レポート
- `scripts/reclassify_annotations.py` — 4 分類化用 LLM 再判定スクリプト

### 5.3 後続バッチでの参照

- 後続バッチ: `F-stream-2-filter-design` (系統 2 のみ担当、本バッチで
  4 分類確定済みの annotations を入力として使用)、`F-jp-coverage-tune`
  (二段階クエリ生成で系統 1 vs 1.5 を機械的に判別、本バッチの 4 分類
  アノテーションを精度測定の真値として使用)
- `docs/runs/F-verify-jp-coverage/golden_set.json` v1.3 — 各 event に
  `particular_angle` + `stream_classification` (4 分類) フィールドを
  追加した版 (Task F カズヤレビュー後 `finalize_annotations.py
  --schema-version 2.0` で更新)
- `docs/runs/F-particular-angle-design/stream_classification.json` —
  25 件の最終系統分類 (4 分類対応スキーマ v2.0、Task F カズヤレビュー
  後 `finalize_annotations.py --schema-version 2.0` で生成)
- `docs/DISCUSSION_NOTES.md` — 系統 1 判定基準明確化エントリ + 系統 2
  設計エントリ (F-particular-angle-design で追記、F-particular-angle-redesign
  で 4 分類化エントリを Resolved 化)
- `docs/CURRENT_STATE.md` — セクション 0 (Hydrangea コアミッション
  2 系統並立) と本ドキュメントへの導線 (本バッチで 4 分類化を反映)

---

*このドキュメントは F-particular-angle-design (2026-05-07) で導入し、
F-particular-angle-redesign (2026-05-07) で 3 分類 → 4 分類化を実施した。
Phase A.5-3a-verify ゲート完了 (2026-05-07) 後の最初のバッチ群で、
F-stream-2-filter-design + F-jp-coverage-tune の共通基盤を確立する性格を
持つ。本ドキュメント自体は docs 層の判定基準正典であり、コード層
(`src/triage/` `src/analysis/`) には変更を加えない。後続バッチ着手時に
本ドキュメントを参照することで、両バッチが同じ判定単位 (= 特定角度) +
同じ 4 分類スキーマで実装される設計を担保する。*
