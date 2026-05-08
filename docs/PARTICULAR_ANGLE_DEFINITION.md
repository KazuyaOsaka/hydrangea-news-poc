# Hydrangea — 「特定角度」(particular_angle) 概念の正典定義

最終更新: 2026-05-08 (F-particular-angle-redesign-extension 完了 — 系統名 1/1.5/2 → 1/2/3 リネーム + 忖度シグナル (sontaku_signals) メタデータ独立化 + MECE 判別基準明示 + 判定フロー Step 3-4 改良)

> このドキュメントは Hydrangea コアミッション (CURRENT_STATE.md セクション 0、
> 2 系統並立) を実装に翻訳する上での **判定単位** を明文化する正典である。
> 系統 1 (silence_gap) と系統 3 (framing_inversion、★ 命名整理前は系統 2)
> の判定基準が「広範な事件レベル」のままだと両系統の重複ケースが避けられず、
> F-stream-2-filter-design および F-jp-coverage-tune の仕様化が曖昧になる。
> 本ドキュメントは判定対象を「特定角度」に限定することで重複を構造的に
> 消し、後続バッチに共通基盤を提供する。
>
> ★ F-particular-angle-redesign (2026-05-08) で **3 分類 (系統 1 / 系統 2 /
> 動画化対象外) → 4 分類** に再構成された。系統 1 の中に「広範事件も特定角度も
> 両方未報道」と「広範事件は報道済み + 特定角度のみ未報道」が混在する構造的不備
> を、新たな分類を独立させることで解消した。
>
> ★ F-particular-angle-redesign-extension (2026-05-08) で **系統名のリネーム
> (1/1.5/2 → 1/2/3)** + **忖度シグナル (sontaku_signals) を別軸メタデータとして
> 独立化** + **MECE 判別基準の明示** + **判定フロー Step 3-4 改良** を実施。
> 「1.5」という時間的経緯の痕跡を伴う命名を定常状態に対応する 1/2/3 に整理し、
> 「忖度・報道規制・黙殺の構造」を系統判定軸に組み込まずに別軸で扱う設計に
> 整理した (= 系統判定は『報道状態』軸のみで MECE、忖度シグナルは動画化価値判定 +
> 解説価値判定で参照される独立軸メタデータ)。

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

### 1.1 3 分類の構造的不備と 4 分類化の経緯 (F-particular-angle-redesign / 2026-05-08)

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
観点不足っていう新分類儲けてもいいのかもしれない」と提案され、議論
の結果 4 分類化が必要との結論に到達した。系統 1 の中に「広範事件も特定
角度も両方未報道 (= 完全空白)」と「広範事件は報道済み + 特定角度のみ
未報道 (= 観点不足)」が混在する構造的問題を、新たに **系統 2
(perspective_gap)** を独立させることで分離する。これにより、台本表現
の方向性が分類別に明確化され (系統 1 は「日本では報じられなかった」、
系統 2 は「事件自体は報じられたが、◯◯という構造には触れられなかった」、
系統 3 は「日本のメディアは××と捉えたが、海外では△△と批判されている」)、
F-13.B JpCoverageVerifier の二段階クエリ生成 (広範事件クエリ + 特定角度
クエリ) の責務も明確化され、F-stream-2-filter-design の責務範囲も縮まる
(= 系統 3 のみ担当、系統 2 は F-jp-coverage-tune の範疇)。F-particular-angle-redesign
(2026-05-08) で本改訂を実施し、PARTICULAR_ANGLE_DEFINITION.md セクション 3 を
4 分類対応に大幅改訂、annotations.json を 4 分類版で再分類、台本表現
ガイドライン (新サブセクション 3.7) を追加した。

### 1.2 命名整理:1/1.5/2 → 1/2/3 (F-particular-angle-redesign-extension / 2026-05-08)

F-particular-angle-redesign 直後のカズヤレビューで、「1.5 という命名は
時間的経緯 (3 分類から 4 分類へ移行した名残) の痕跡で、定常状態の命名
としては不適切」「1.5 じゃなくてそれが 2 で、今までの 2 が 3」と提案
された。これを受け、F-particular-angle-redesign-extension で **系統名
1/1.5/2 → 1/2/3** に機械的にリネームし、変数名も `stream_1_5_perspective_gap`
→ `stream_2_perspective_gap`、`stream_2_framing_inversion` →
`stream_3_framing_inversion` に整理した。これは定常状態に至った 4 分類
体系の正典化で、以後はこの命名を採用する (旧 1/1.5/2 命名は
`annotations.json` 内の `legacy_stream_classification_v1` フィールドや
DECISION_LOG / DISCUSSION_NOTES の歴史的記録のみで残る)。

### 1.3 忖度シグナルを別軸メタデータに分離 (F-particular-angle-redesign-extension / 2026-05-08)

同レビューでカズヤから「『忖度・報道規制・黙殺の構造』を系統判定に
組み込むと MECE が崩れる」「系統判定は『報道状態』軸のみで MECE 化し、
忖度シグナルは別軸 (メタデータフィールド) で扱うべき」と提案された。
これを受けて、忖度シグナル (sontaku_signals) を **系統判定とは独立な
別軸メタデータ** として正典化し、本ドキュメント新サブセクション 3.6
で構造を確定した。系統判定は「広範事件 / 特定角度の報道状態」のみで
MECE に分類し、忖度シグナルは F-1 EditorialMissionFilter (動画化価値
判定) と F-stream-2-filter-design 第二段階 (解説価値判定) で参照される
独立軸として運用する。同時に、ジレンマ解説や台本表現の各論ルール追加
の誘惑を「クラウド誤り 9: 各論コントロールへの誘惑」として記録し
(`CLAUDE.md` および `DISCUSSION_NOTES.md`)、メタデータ構造の正典化 +
LLM の知性に委ねる設計哲学を再確認した。

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

## 3. 「特定角度」を使った系統判定基準 (4 分類、命名 1/2/3)

★ F-particular-angle-redesign (2026-05-08) で **3 分類 → 4 分類** に再構成、
F-particular-angle-redesign-extension (2026-05-08) で **系統名を 1/2/3 に
リネーム** + **忖度シグナルを別軸メタデータに分離** (セクション 3.6 参照)。
特定角度を判定単位として使うと、Hydrangea が処理すべき海外ニュースは
以下の 4 つに **報道状態軸のみで MECE に** 排他分類される。

**系統 1 (silence_gap)**: **広範事件も特定角度も両方** 日本主要メディアで
未報道。動画化対象の核心 (= 特定角度) が未報道で、4 軸構造的バイアスの
いずれかに該当し、かつ広範事件レベルでも未報道の事象。完全な情報空白で、
Hydrangea コアミッションど真ん中。台本表現としては「日本では報じられ
なかった」という言い方が自然に成立する。

**系統 2 (perspective_gap、★ F-particular-angle-redesign で新設、旧名: 系統 1.5)**:
広範事件は日本主要メディアで報道済みだが、**特定角度は未報道**。動画化
対象の核心 (= 特定角度の構造分析) が日本では深掘りされていない事象。
事件本体は報道済みなので「日本では報じられなかった」と書くと嘘になり、
台本表現としては「日本でも事件は取り上げられたが、◯◯という構造には
触れられていない」になる。F-13.B の現実装は広範事件クエリ
(`title + 日本 報道`) で報道済み判定するため、現状では系統 2 を捕捉
できず系統 3 候補に流れているが、F-jp-coverage-tune の二段階クエリ
生成 (広範事件クエリ + 特定角度クエリ) で機械化可能。

**系統 3 (framing_inversion、旧名: 系統 2)**: 広範事件も特定角度も日本
主要メディアで報道済みだが、**解釈・フレーミング・優先順位** が日本/西側
vs 海外/東側で異なる。動画化対象の核心 (= 特定角度) は報道されているが、
解釈の差が解説価値を生む事象。台本表現は「日本のメディアは××と捉えたが、
海外では△△と批判されている」になる。ここでは『その特定角度そのものの
解釈差』を扱うのであって、広範事件レベルの解釈差は対象ではない。
F-stream-2-filter-design の責務範囲。

**動画化対象外**: 特定角度が日本主要メディアで報道済みかつ解釈も同じ
(= 単に同じ内容が報道されているだけ)、または 4 軸構造的バイアスに該当
しない (= 単に専門ニッチ、他国オピニオンの個人見解、報道価値が低い)
事象。

### 3.1 判定の論理フロー (4 分類版、Step 3-4 改良)

判定の論理フローは以下の通り (上から順に評価する)。F-particular-angle-redesign
(2026-05-08) で Step 2 と Step 3 を分離して「広範事件と特定角度の両方の
報道状態」を独立判定する設計に再構成し、F-particular-angle-redesign-extension
(2026-05-08) で Step 3 を「日本メディアが特定角度について何かを語っているか」
の二択に整理 + Step 4 で「評価フレーム対立 **かつ** 忖度・報道規制・黙殺の
構造的シグナルがあるか」を判定する形に改良した。

```
[海外ニュース入力]
    ↓
[Step 0: 特定角度を抽出する (LLM ベース)]
    ↓
[Step 1: 特定角度が 4 軸のいずれかに該当するか?]
    No → 動画化対象外
    Yes ↓
[Step 2: 広範事件が日本主要メディアで報道済みか?]
    No (両方未報道) → 系統 1 (silence_gap)
    Yes ↓
[Step 3 (改): 日本メディアはこの特定角度について何かを語っているか?]
    No (角度の不在 = 触れられていない / 言及なし) → 系統 2 (perspective_gap)
    Yes (語られている) ↓
[Step 4 (改): 日本メディアと海外メディアの評価フレームが対立、かつ
              「忖度・報道規制・黙殺」の構造的シグナル (sontaku_signals.level
              が high または medium、セクション 3.6) があるか?]
    No → 動画化対象外 (報道済み + 解釈差なし、または忖度シグナルなしで
                       単発の専門解釈差に留まる)
    Yes → 系統 3 (framing_inversion)
```

Step 2 / Step 3 の「日本主要メディアで報道済みか / 何かを語っているか」は
F-13.B (JpCoverageVerifier) の責務範囲だが、判定対象が「広範事件」と
「特定角度」の **2 段階** に分離されている点が新しい。F-13.B の現実装は
title + " 日本 報道" を Grounding クエリとして投げるので広範事件レベルの
照合に留まる。この乖離は F-jp-coverage-tune (FUTURE_WORK 緊急度 高) で
**二段階クエリ生成** として対処する想定で、F-particular-angle-redesign
+ extension では 4 分類対応のアノテーションデータ + 忖度シグナル
メタデータを F-jp-coverage-tune の入力として準備する位置付けに留める。

Step 4 の「解釈差 + 忖度シグナル」判定は F-stream-2-filter-design
(FUTURE_WORK 緊急度 高) で実装する 2 段階フィルタの後段が担う。
F-particular-angle-redesign での 4 分類化により F-stream-2-filter-design
の責務範囲は **系統 3 のみ** に縮まり (系統 2 は F-jp-coverage-tune の
範疇に移行)、さらに F-particular-angle-redesign-extension で
sontaku_signals メタデータが Step 4 の追加判定軸として正典化された。
これにより、F-stream-2-filter-design の解説価値判定 LLM プロンプトは
「広範事件も特定角度も日本で報道済みであることを前提に、解釈差 +
忖度シグナル level を踏まえて解説価値を判定する」というシンプルな責務に
専念できる。

### 3.2 25 件アノテーションの想定分布 (4 分類版、命名 1/2/3)

F-particular-angle-redesign で 25 件を 4 分類対応で再分類した結果の想定
分布は以下の通り (LLM 推定段階、実際の分布は再分類後の `annotations.json`
+ `stream_classification.json` を参照)。

| 分類 | 件数 (想定) | 比率 | 代表事例 |
|---|---|---|---|
| 系統 1 (silence_gap) | 約 6 件 | 約 24% | blind_001/003/007/010 + 試運転 ロシア焼身 + 試運転 Met Police |
| 系統 2 (perspective_gap) | 約 5 件 | 約 20% | blind_002/004/009 等 (3 分類版で stream_1 だが広範事件は報道済み) |
| 系統 3 (framing_inversion) | 約 13 件 | 約 52% | covered 系列 9-11 件 + 試運転 7-K Slot-1 (FIFA) / Slot-2 (Mandelson) |
| 動画化対象外 | 1 件 | 約 4% | covered_006 (NVIDIA 株) |

実際の再分類結果 (LLM 推定段階) は **系統 1 = 4 件 / 系統 2 = 20 件 /
系統 3 = 0 件 / 動画化対象外 = 1 件** で、想定値と大きく乖離した。詳細は
`docs/runs/F-particular-angle-redesign/REPORT.md` セクション 3-6 +
`docs/runs/F-particular-angle-design/annotations.json` (4 分類版上書き、
旧 3 分類版は `annotations_v1_3class.json` にバックアップ) を参照。

### 3.5 系統 2 と系統 3 の MECE 判別基準 (F-particular-angle-redesign-extension で新設)

系統 2 (perspective_gap) と系統 3 (framing_inversion) の境界条件は
LLM 判定でも揺れやすい論点だったため、F-particular-angle-redesign-extension
(2026-05-08) で MECE 判別基準を以下のとおり明示した。

> **判別の核心**: 「日本メディアがその特定角度について何かを語っているか?」
> - 何も語っていない / 触れていない → **系統 2 (perspective_gap)**
> - 語っているが評価が海外と対立 → **系統 3 (framing_inversion)**

境界事例の中立報道の扱い:

- 「中立報道 = 何も語っていない」と解釈 → **系統 2** に寄せる
- 「中立報道 = 暗黙的に肯定 (= 批判していない) という評価表明 +
  忖度シグナルあり」と解釈 → **系統 3** に寄せる

判定者の解釈に依存する境界事例は、後述の **忖度シグナル
(sontaku_signals.level)** の値で間接的に区別する設計とする (level が
high / medium = 系統 3 寄り、low / none = 系統 2 寄り)。系統判定 LLM が
迷う場合は系統 2 にデフォルトし、忖度シグナル level を併記することで
F-1 EditorialMissionFilter / F-stream-2-filter-design 第二段階で再評価
される設計。

### 3.6 忖度シグナル (sontaku_signals) — 系統判定とは独立な別軸メタデータ (F-particular-angle-redesign-extension で新設)

F-particular-angle-redesign-extension (2026-05-08) でカズヤから「忖度・
報道規制・黙殺の構造を系統判定に組み込むと MECE が崩れる」「系統判定は
報道状態軸のみで MECE 化、忖度シグナルは別軸メタデータで扱うべき」と
提案された。これを受け、忖度シグナルを **系統判定とは独立な別軸メタ
データ** として正典化する。

系統判定 (セクション 3-3.5) は『日本メディアでの報道状態 + 角度の有無 +
評価フレーム対立の有無』のみで MECE に分類し、「なぜそうなっているか」
の構造的説明 (= 忖度シグナル) は別軸として動画化価値判定 + 解説価値判定
で参照される設計とする。これは Hydrangea コアミッション「忖度・報道
規制・報道の自由度の低さをぶち壊す」を担保する独立軸として機能する。

#### 3.6.1 メタデータ構造

```python
sontaku_signals = {
    "level": "high" | "medium" | "low" | "none",
    "type": "diplomatic" | "domestic" | "media_industry" | None,
    "reasoning": "<忖度の構造的説明、1-2 文>",
    "extraction_confidence": "high" | "medium" | "low",
}
```

#### 3.6.2 level の定義

- **`high`**: 明確な忖度・報道規制・黙殺の構造あり
  - 例: 米国忖度で日本政府を批判できない、ジャニーズ問題の長年放置、
    特定国 (中国・韓国・イスラエル等) への外交的配慮による報道抑制
- **`medium`**: 構造的バイアスはあるが明確な忖度とは言えない
  - 例: 業界記者クラブの慣行的偏向、スポンサー配慮による触れ方のソフト化
- **`low`**: 部分的な構造的バイアスのみ
  - 例: 一部メディアの編集方針差、特定論調傾向のごく弱い表れ
- **`none`**: 忖度シグナルなし
  - 例: 単にローカルすぎる事象、専門ニッチ、海外でも大きく扱われていない

#### 3.6.3 type の定義

- **`diplomatic`**: 外交的忖度
  - 米国・中国・韓国・イスラエル・サウジ・ロシア・北朝鮮等への
    外交的配慮
- **`domestic`**: 国内権力者忖度
  - 政治家・上級官僚・財界要人・司法関係者・メディアオーナー一族等
    「上級国民」層への構造的配慮
- **`media_industry`**: メディア業界忖度
  - 記者クラブ制度・クロスオーナーシップ・芸能スポーツ界権力者等
    メディア業界内構造に起因する忖度
- **`None`**: type 該当なし (level=none の場合、または 3 type のいずれにも
  該当しない場合)

#### 3.6.4 系統判定との関係

`sontaku_signals` は系統 1/2/3 のいずれにおいても付与される独立軸メタ
データである。

- **系統 1 (silence_gap)**: 完全な情報空白の理由として `level=high` +
  `type=diplomatic/domestic/media_industry` がほぼ必須 (none / low の場合
  は単にローカルすぎる事象で、Step 1 の 4 軸該当性で動画化対象外に弾かれる
  はず)
- **系統 2 (perspective_gap)**: 「事件本体は報道済み + 特定角度のみ未報道」
  の理由として level=high/medium が多い。none / low の場合は単に専門
  ニッチで角度が薄い事象を意味し、F-1 EditorialMissionFilter で動画化
  価値が低いと判定される
- **系統 3 (framing_inversion)**: 評価フレーム対立の構造的背景として
  level=high/medium がほぼ必須 (none / low の場合は Step 4 で動画化対象外
  に弾かれる、セクション 3.5 参照)

これにより、Hydrangea コアミッション「忖度・報道規制をぶち壊す」と
直接整合する事象を 3 系統横断で識別できる。

#### 3.6.5 後続バッチでの参照

- `F-1 EditorialMissionFilter` (動画化価値判定): `level=high/medium` の
  事象を優先採点 (将来検討、本バッチ範囲外)
- `F-stream-2-filter-design` 第二段階 (解説価値判定): 系統 3 候補に対して
  `level` を解説価値の追加軸として参照 (本バッチで設計の前提を整備)
- `F-jp-coverage-tune` 二段階クエリ生成: 系統 1 vs 系統 2 判別後に
  `level` を補助情報として参照 (本バッチで設計の前提を整備)

### 3.7 系統別の台本表現の方向性 (★ 旧サブセクション 3.5、F-particular-angle-redesign-extension で 3.7 にリナンバー + 命名 1/2/3 に整理)

★ カズヤとの 2026-05-07 + 2026-05-08 議論で確立された設計哲学に従い、
台本表現は以下の方向性で **LLM の知性に委ねる** 設計を採用する。具体的な
言い回し最適化は Phase A.5-3b 手動 PoC で 1 本作りながら試行錯誤する
設計で、本ドキュメントは メタデータ構造の確定までを担当する。

#### 3.7.1 設計哲学

- **言い回しを個別ルールで指定しない** — ルール累積で全体劣化を回避する。
  「系統 1 のときは『〜は報じられなかった』と書け」のような言い回し強制
  ルールを script_writer.py のプロンプトに加えると、ルールが増えるほど
  台本生成 LLM の自由度が削られて全体品質が劣化する経験則 (F-12-B-1
  視聴者ファースト 3 原則導入の動機 +
  F-particular-angle-redesign-extension で記録された **クラウド誤り 9
  「各論コントロールへの誘惑」** と整合)。
- **article_writer.py は触らない** — 不変原則 1、記事クオリティの核心
  であり、本バッチを含む後続バッチでも一切変更しない。
- **script_writer.py 新ルートに particular_angle メタデータと
  sontaku_signals メタデータを渡す** — LLM が自分で文脈に応じた言い回し
  を選択する設計。具体的には系統別 + 忖度シグナル別のメタデータを構造化
  して渡し、LLM が『広範事件は報道済みだが特定角度は未報道、忖度シグナル
  level=high で外交的忖度が背景』のような状態を理解した上で言い回しを
  選ぶ。

#### 3.7.2 メタデータ構造 (script_writer.py 新ルート入力)

```python
particular_angle_metadata = {
    "stream_classification": "stream_1_silence_gap"
                          | "stream_2_perspective_gap"
                          | "stream_3_framing_inversion"
                          | "out_of_scope",
    "core_question": "<特定角度の核心、1-2 文>",
    "differentiation_from_mainstream": "<既存報道との差、1-2 文>",
    "hydrangea_axis_alignment": "<4 軸該当性、1 軸特定>",
    "sontaku_signals": {
        "level": "high" | "medium" | "low" | "none",
        "type": "diplomatic" | "domestic" | "media_industry" | None,
        "reasoning": "<忖度の構造的説明、1-2 文>",
    },
}
```

このメタデータ構造は F-stream-2-filter-design (系統 3 担当) +
F-jp-coverage-tune (系統 1 vs 系統 2 判別担当) の出力フォーマットでもある。
両バッチで同じ構造のメタデータを生成し、script_writer.py 新ルートに
パススルーする責務分担とする。

#### 3.7.3 台本 LLM が選択する言い回しの例 (例示、ルール強制ではない)

LLM は メタデータの `stream_classification` + `sontaku_signals` フィールド
を見て、以下のような言い回しを **自律的に選択** する想定。あくまで例示
であり、台本 LLM への強制ルールとしては書かない (= プロンプトには
「メタデータを踏まえて自然な日本語で語る」程度の指示に留める。クラウド
誤り 9「各論コントロールへの誘惑」を回避するため)。

- **系統 1 (silence_gap)** → 「この事件は日本のメディアで一切報じられ
  なかった」「日本の主流メディアでは黙殺されてきた」
- **系統 2 (perspective_gap)** → 「事件自体は報じられたが、◯◯という
  構造的問題には触れられなかった」「日本でも事件は取り上げられたが、
  本質的な角度は欠落していた」
- **系統 3 (framing_inversion)** → 「日本のメディアは××と捉えたが、
  海外では△△と批判されている」「同じ出来事を、日本と海外では全く
  異なる角度から論じている」
- **`sontaku_signals.level=high/medium`** の併記時 → 系統別の上記言い回し
  に「忖度の背景」を 1-2 文添える (LLM が自律選択、type に応じて『米国
  忖度』『業界忖度』等の言葉を選ぶ)

#### 3.7.4 自動化への到達経路

- F-particular-angle-redesign (2026-05-08): 4 分類確定 +
  particular_angle_metadata 構造の正典化
- F-particular-angle-redesign-extension (2026-05-08): 系統名 1/2/3 への
  リネーム + sontaku_signals メタデータの正典化 + クラウド誤り 9 の記録
- F-jp-coverage-tune: 二段階クエリ生成で広範事件 vs 特定角度の報道状態
  を独立判定 → `stream_classification` を `stream_1_silence_gap` /
  `stream_2_perspective_gap` / (報道済み) で機械的に分類
- F-stream-2-filter-design: (報道済み) 候補に対して解釈差 + 忖度シグナル
  level の組み合わせで判定 → `stream_classification` を
  `stream_3_framing_inversion` / `out_of_scope` で機械的に分類
- Phase A.5-3b 手動 PoC: 1 本目の素材で言い回しを試行錯誤、最適表現を
  プロンプトに反映 (ルール強制ではなく『参考事例』として埋め込む)
- 最終形態: script_writer.py 新ルートに
  `particular_angle_metadata` (sontaku_signals 含む) を渡し、LLM が自律
  選択

参照: `docs/DISCUSSION_NOTES.md` 「2026-05-07: 台本表現:特定角度未報道
のナレーション課題」(F-particular-angle-redesign-extension で
particular_angle_metadata + sontaku_signals 構造の正典化により設計方向性
確定、Phase A.5-3b で実装試行)。

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
stream_2_perspective_gap / stream_3_framing_inversion / out_of_scope)
の estimate を出させ、カズヤレビュー時に LLM 判断と人間判断の差分を
可視化できるようにする。LLM 推定は確定値ではなく、カズヤレビュー後の
`kazuya_review.*_revised` フィールドが正本となる。

★ F-particular-angle-redesign (2026-05-08) で 4 分類対応 (Step 1-4 論理
フロー) に LLM プロンプトを更新した。`scripts/reclassify_annotations.py`
は『広範事件報道状態』と『特定角度報道状態』の両方を `reasoning` に
明記させる設計で、これは F-jp-coverage-tune の二段階クエリ生成における
判定基準の参考実装としても機能する。

★ F-particular-angle-redesign-extension (2026-05-08) で `scripts/add_sontaku_signals.py`
を新規追加し、25 件の annotations に `sontaku_signals` メタデータ
(level / type / reasoning / extraction_confidence) を LLM で付与する
運用を確立した。系統判定とは独立な軸として LLM に推定させ、Hydrangea
コアミッション「忖度・報道規制をぶち壊す」と直接整合する事象を 3 系統
横断で識別する基盤データを整備する。

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

### 5.2 F-particular-angle-redesign (2026-05-08、4 分類化) で生成

- `docs/runs/F-particular-angle-redesign/reclassification_log.json` —
  4 分類化 LLM 再判定実行ログ
- `docs/runs/F-particular-angle-redesign/reclassification_diff.json` —
  旧 3 分類 → 新 4 分類の差分集計
- `docs/runs/F-particular-angle-redesign/review_draft_v2.md` — 4 分類版
  カズヤレビュー用ドラフト (3 分類 → 4 分類への変更箇所を冒頭で重点表示)
- `docs/runs/F-particular-angle-redesign/REPORT.md` — 統合レポート
- `scripts/reclassify_annotations.py` — 4 分類化用 LLM 再判定スクリプト

### 5.3 F-particular-angle-redesign-extension (2026-05-08、命名整理 + 忖度シグナル独立化) で生成

- `docs/runs/F-particular-angle-redesign/extension_log.json` — 拡張作業
  ログ (sontaku_signals 推定実行 + 系統名リネーム + schema_version 更新)
- `scripts/add_sontaku_signals.py` — LLM ベース sontaku_signals 推定スクリプト
- `docs/runs/F-particular-angle-design/annotations.json` — 系統名 1/2/3
  への機械的リネーム + `sontaku_signals` フィールド追加 + schema_version
  2.0 → 2.1 (`previous_schema_version=2.0` 記録)

### 5.4 後続バッチでの参照

- 後続バッチ: `F-stream-2-filter-design` (系統 3 のみ担当、本バッチで
  4 分類確定済み + sontaku_signals 付与済みの annotations を入力として
  使用)、`F-jp-coverage-tune` (二段階クエリ生成で系統 1 vs 系統 2 を
  機械的に判別、本バッチの 4 分類アノテーション + sontaku_signals 真値
  を精度測定の真値として使用)
- `docs/runs/F-verify-jp-coverage/golden_set.json` v1.3 — 各 event に
  `particular_angle` + `stream_classification` (4 分類、命名 1/2/3) +
  `sontaku_signals` フィールドを追加した版 (Task E カズヤレビュー後
  `finalize_annotations.py --schema-version 2.0` で更新)
- `docs/runs/F-particular-angle-design/stream_classification.json` —
  25 件の最終系統分類 (4 分類対応スキーマ v2.0 / 命名 1/2/3、Task E
  カズヤレビュー後 `finalize_annotations.py --schema-version 2.0` で生成)
- `docs/DISCUSSION_NOTES.md` — 系統 1 判定基準明確化エントリ + 系統 3
  設計エントリ (F-particular-angle-design で追記、F-particular-angle-redesign
  で 4 分類化エントリを Resolved 化、F-particular-angle-redesign-extension
  で命名整理 + 忖度シグナル独立化 + クラウド誤り 9 を追記)
- `docs/CURRENT_STATE.md` — セクション 0 (Hydrangea コアミッション
  2 系統並立) と本ドキュメントへの導線 (extension で命名 1/2/3 + 忖度
  シグナル独立化を反映)
- `CLAUDE.md` — クラウド誤り 9 (各論コントロールへの誘惑、
  F-particular-angle-redesign-extension で記録)

---

*このドキュメントは F-particular-angle-design (2026-05-07) で導入し、
F-particular-angle-redesign (2026-05-08) で 3 分類 → 4 分類化、
F-particular-angle-redesign-extension (2026-05-08) で命名 1/1.5/2 → 1/2/3
リネーム + 忖度シグナル (sontaku_signals) を別軸メタデータとして独立化 +
MECE 判別基準明示 + Step 3-4 改良を実施した。Phase A.5-3a-verify ゲート
完了 (2026-05-07) 後のバッチ群で、F-stream-2-filter-design +
F-jp-coverage-tune の共通基盤 (4 分類 + sontaku_signals メタデータ) を
確立する性格を持つ。本ドキュメント自体は docs 層の判定基準正典であり、
コード層 (`src/triage/` `src/analysis/`) には変更を加えない。後続バッチ
着手時に本ドキュメントを参照することで、両バッチが同じ判定単位
(= 特定角度) + 同じ 4 分類スキーマ (1/2/3) + 同じ sontaku_signals
メタデータ構造で実装される設計を担保する。*
