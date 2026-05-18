# ADR-0003: Hydrangea コンテンツモラル設計

## ステータス
Accepted (2026-05-16 に 3 AI 三角測量で確立、ICRC + プラットフォーム規約に
対応。2026-05-18 F-image-prompt-spec バッチで ADR として正典化)

## 文脈
Hydrangea は政治・戦争・人権系の題材を扱う = 法的リスク + 印象操作リスク +
プラットフォーム規約リスクが高い。第一作 (候補A `cls-6889e9e1c7ac`、Israel
9,600 人収監、ICRC 監視操作疑惑) でこれら全てに該当する。

なお現行 `video_payload_writer.py` の `_make_negative_prompt()` /
`_make_must_avoid()` は既にデフォルトで強い安全方向に倒れている (Task B §3:
実在人物顔アップ / 架空会談シーン / 戦闘映像を `_BASE_NEGATIVE` で常時禁止、
visual_safety_level=elevated)。本 ADR はその防御姿勢を **正典化し後退させない**
ことを明文化する。

## 決定

### 視覚表現の禁止事項 (第一作以降全作品で適用)
- 実在人物の顔・肖像 NG (AI 生成含む)
- 実在施設の写実再現 NG
- 事件再現映像 NG (推測でドラマ化しない)
- ICRC 標章 (赤十字・赤新月・赤水晶) NG (法的リスク、ICRC 公式ガイド参照)
- ICRC 職員風の人物 NG
- 制服・腕章・赤十字っぽいマーク NG
- リアルな戦争映像・暴力描写 NG (emotional gore 排除)

### 視覚表現の OK 事項
- 抽象アイコン (監視チェックリスト等)
- 数字グラフィック (9,600 等の数字を主役にした表示)
- 文書カード ("reported monitoring mechanism" 等)
- 構造図・フロー図・タイムライン・インセンティブダイアグラム
- 抽象的シルエット (顔・固有特徴を持たない)
- 場所の象徴 (有刺鉄線、監獄ゲート等の一般化シンボル)

### テキスト表現の方針
- 固有名詞 (ICRC、Israel、Hamas 等) は **出典付きで明示**、逃げない
- 数字 (9,600 等) は出典 + 日付 + リンクを source_card で表示
- 「日本では報道されない」誇大表現を避け、「日本では触れられない構造」等の
  中立表現を使う (第一作 framing 指針 3、perspective_gap 前提)
- 台本 punchline は「中間が良い」原則遵守
  (シニカル × 生活実感への着地、メディア断定回避 — 第一作 framing 指針 4)

### AI 生成ラベル付与
Phase A.5-3d 投稿前ゲートで判定:
- 写実 AI 映像・実在人物風・実在施設風・事件再現風を **含む**
  → AI ラベル必須
- 抽象インフォグラフィック中心で上記なし
  → AI ラベル任意 (透明性として付与推奨)

### 公開前検証 (高リスク事実主張)
**必須工程**、過剰防衛ではない。対象:
- 数字 (9,600 人等)
- 固有名詞関連の事実主張 (ICRC 監視操作疑惑等)
- 人権侵害・戦争犯罪・拘束者数等の主張
- 台本に含まれる全ての断定的事実主張

検証方法:
- 一次ソース確認 (TeleSUR 原文、ICRC 公式声明等)
- 複数ソース突合 (TeleSUR + Al Jazeera + Middle East Eye 等)
- 日本主要メディアの報道状況確認 (perspective_gap 前提の維持確認)

### 投稿前ゲートのチェックリスト (Phase A.5-3d で実装)
1. 視覚: 禁止事項に該当する画像が含まれていないか
2. テキスト: 固有名詞に出典が付いているか
3. 数字: 出典 + 日付が source_card で表示されているか
4. 台本: 「日本では報道されない」誇大表現がないか
5. AI ラベル: 写実 AI 含むなら必須付与
6. 高リスク事実: 公開前検証完了済みか

## 帰結
- video_payload schema の各 image/event に `must_avoid` / `safety_flags` /
  `visual_safety_level` を保持 (現行の安全方向を構造として継承、
  `schema_extension_design.md`)
- ADR-0001 のブランドトーン禁止語彙 (cinematic / photorealistic 等) と整合
- 投稿前ゲートチェックリストは Phase A.5-3d の新規残課題として
  FUTURE_WORK に登録 (本バッチでは設計のみ、実装しない)

## 参考
- ICRC: Use of emblems (icrc.org/en/law-and-policy/use-emblems)
- TikTok: AI-generated content guidelines
- YouTube: Disclosing use of altered or synthetic content
- 3 AI 三角測量議論ログ (2026-05-16)
- `docs/runs/F-image-prompt-spec/current_schema_analysis.md` §3 (現行安全機構)
- ADR-0001 (画像戦略 C') / ADR-0002 (Remotion MVP 境界)
