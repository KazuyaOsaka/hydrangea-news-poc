# ADR-0002: Remotion 第一作 MVP の境界線 (D-minimal)

## ステータス
Accepted (2026-05-16 に 3 AI 三角測量で確立、2026-05-18 F-image-prompt-spec
バッチで ADR として正典化)

## 文脈
Phase A.5-3b 第一作で Remotion をどこまで実装するか。検討した 4 案:
- A. フル実装
- B. Remotion 最小 + CapCut
- C. CapCut 手動
- D. Remotion セットアップ + 最小機能

3 AI 三角測量で **D-minimal** に収束。背景には Hydrangea 哲学
「動くものを壊さない」「負債を残さない」「過剰拡張性の罠を避ける」がある。
第一作の目的は **Hydrangea 第一作の公開**であって Remotion 作品の完成ではない。

## 決定
**D-minimal**: Remotion 環境は Phase A.5-3b で構築するが、第一作の実装は
厳格に最小機能のみ。

### 第一作でやること
- Remotion プロジェクト作成 + 9:16 縦動画テンプレート
- 6-8 枚の静的ベース画像表示 (ADR-0001 images[])
- 4 種類のテキストカード
  (title_card / number_card / source_card / claim_card)
- 字幕: scene ごとのシンプルなフェードイン・アウト
- トランジション: カット または クロスフェード (ディゾルブ) のみ
- scene 開始秒・終了秒制御
- 書き出し確認 (MP4、9:16、TikTok/YouTube Shorts 投稿可能形式)

### 第一作でやらないこと (明示的禁止)
- Ken Burns エフェクト (パン・ズーム)
- キネティックタイポグラフィ (1 語ずつハイライト等)
- 図解アニメーション (矢印が動く等)
- 複雑トランジション (ワイプ、グリッチ等)
- テロップの凝ったモーション
- CapCut との二重運用 (CapCut は非常口扱い)
- 12-20 イベント完全実装 (理想仕様、第一作 MVP では 10 イベント)

### 失敗条件・撤退基準
- 第一作の Remotion 実装が **1 週間**を超える → 機能をさらに削る
  (字幕簡素化、トランジション削減等)
- 公開可能な最低ライン (再生可能 + 字幕可読 + 音声同期) を下回る
  → CapCut で非常口対応
- 目的は Hydrangea 第一作の公開、Remotion 作品完成ではない

### CapCut の扱い
- **主工程ではない、非常口**
- Remotion 出力が公開最低ラインを下回った場合のみ使用
- 「最初から CapCut 補完を前提」は禁止 (二重管理 → 負債)

## 帰結
- Remotion 学習コストは第一作完成と並行
- 第二作以降で Ken Burns / キネティックタイポ / 複雑アニメーションを
  段階的に追加
- video_payload schema の `events[]` は将来拡張可能な構造で設計
  (第一作 animation は `fade-in` / `cut` / `dissolve` の 3 種のみ、
  種別追加・event type 拡張を構造で許容 — `schema_extension_design.md`)
- Node 環境はカズヤが手動準備 (CURRENT_STATE §2 着手前確認事項 4)

## 参考
- 3 AI 三角測量議論ログ (claude.ai + ChatGPT + Gemini、2026-05-16)
- `docs/runs/F-image-prompt-spec/schema_extension_design.md`
- ADR-0001 (画像戦略 C') / ADR-0003 (コンテンツモラル)
- BATCH_PROTOCOL「拡張性差し込み判断ルール」(過剰拡張性の罠 = クラウド誤り 6)
