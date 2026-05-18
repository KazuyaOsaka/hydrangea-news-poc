# ADR-0001: Hydrangea 画像戦略 (C')

## ステータス
Accepted (2026-05-16 に 3 AI 三角測量 3 ラウンドで確立、2026-05-18
F-image-prompt-spec バッチで ADR として正典化)

## 文脈
Phase A.5-3b 第一作 (候補A `cls-6889e9e1c7ac`、Israel 9,600 人収監 / ICRC
監視操作疑惑、perspective_gap framing) の画像戦略を確定する。

F-trial-run-post-llm-extraction の事前調査 + 本バッチ Task B のコード読解
(`docs/runs/F-image-prompt-spec/current_schema_analysis.md`) で、現行
video_payload は **`image_prompt` 非存在**・**構造的に必ず 4 scene**・**統一
トーン末尾なし**・`video_prompt` はテンプレ条件分岐の決定論的出力 (LLM 非関与)
と判明。当初想定の「既存 image_prompt の品質改善」は前提が成立せず、画像戦略
そのものを設計判断として固定する必要がある。

## 決定
画像戦略 = **C'** (現時点の最有力仮説):
- 理想仕様: 6-8 枚ベース画像 + 12-20 視覚イベント
- 第一作 MVP: 6-8 枚ベース画像 + 10 イベント
  (hook 2 / setup 2 / twist 4 / punchline 2)

現行の「script 4 ブロックに 1:1 の 4 scene」構造は維持したまま、その上に
**images[] レイヤー** (ベース画像) と **events[] レイヤー** (視覚イベント) を
新設する (詳細: ADR-0002 + `schema_extension_design.md`)。4 scene 構造自体は
壊さない (= scene_block として各 image/event に紐付ける)。

### ブランドカラー 5 色パレット
- ベース: near black (`#0A0A0A` 前後)
- 本文・数字: off-white (`#F5F5F0` 前後)
- 主アクセント: hydrangea blue (`#4A6FA5` 前後、紫陽花の青)
- 警告・矛盾・危険: muted red (`#A04848` 前後、**限定使用、常用禁止**)
- 出典・補足: grey (`#808080` 前後)

### ブランドトーン語彙
採用:
- sober investigative documentary infographic
- editorial lighting
- source-driven layout
- restrained, high-density, sharp

禁止 (画像生成プロンプトに絶対含めない):
- cinematic, dark cinematic, thriller, geopolitical thriller
- hyper-realistic, photorealistic
- emotional gore, dramatic shadows
- 「映画的」「劇的」を想起させる全ての英語表現

> 注: 現行 `_make_video_prompt()` は上記語彙を一切埋め込んでいない (Task B
> §4)。Phase A.5-3b で画像プロンプト末尾に 5 色パレット指定 + 採用語彙を
> **新たに強制**する。これは「ルール累積による全体劣化」(クラウド誤り 9) では
> なく **ブランド構造データの注入**であり、各論の言い回し統制ではない
> (LLM/レンダラに渡す構造化された素材)。

### イベントタイプ (第一作 MVP)
4 種類のみ:
- `title_card`: タイトル + サブタイトル表示
- `number_card`: 数字を主役にした表示 (9,600 等)
- `source_card`: 出典明示 (媒体名 + URL + 日付)
- `claim_card`: 主張・引用文表示

## 帰結
- video_payload schema を `images[]` と `events[]` に分離 (ADR-0002 +
  `schema_extension_design.md` で詳細)
- 画像生成プロンプト末尾に 5 色パレット指定を強制 (Phase A.5-3b 実装)
- 現行 4 scene 構造は維持 (scene_block で images/events に紐付け、後方互換)
- 第二作以降で視覚イベント拡張 (キネティックタイポ等) を段階的に追加可能
- ADR-0003 の視覚禁止事項と整合 (実在人物 NG / ICRC 標章 NG 等を
  must_avoid + negative_prompt で表現、現行の強い安全方向を後退させない)

## 参考
- 3 AI 三角測量議論ログ (claude.ai + ChatGPT + Gemini、2026-05-16)
- `docs/runs/F-image-prompt-spec/current_schema_analysis.md` (Task B)
- `docs/runs/F-trial-run-post-llm-extraction/REPORT.md` §6
- `docs/runs/F-trial-run-post-llm-extraction/video_payload_audit.json`
- ADR-0002 (Remotion MVP 境界) / ADR-0003 (コンテンツモラル)
