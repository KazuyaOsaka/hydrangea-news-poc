# video_payload schema 拡張設計 (Task D)

設計日: 2026-05-18
ステータス: **設計のみ** (実装は Phase A.5-3b、本バッチでは
`src/generation/video_payload_writer.py` を一切改修しない)
前提 ADR: ADR-0001 (画像戦略 C') / ADR-0002 (Remotion D-minimal) /
ADR-0003 (コンテンツモラル)
現行構造: `docs/runs/F-image-prompt-spec/current_schema_analysis.md`

---

## 1. 設計方針

現行 video_payload は「script 4 ブロックに 1:1 の 4 scene」(構造的に必ず 4 個、
`image_prompt` 非存在、`video_prompt` はテンプレ決定論出力)。第一作 MVP では
これを壊さず、上に **`images[]`** (6-8 枚ベース画像) と **`events[]`** (10 個の
視覚イベント) の 2 レイヤーを新設する。各 image/event は `scene_block`
(hook/setup/twist/punchline) で現行 4 scene 構造に紐付け、後方互換を保つ。

---

## 2. 新スキーマ提案

```json
{
  "event_id": "cls-6889e9e1c7ac",
  "title": "...",
  "total_duration_sec": 80,
  "metadata": { "...": "現行 metadata を維持 (title_layer / director / analysis)" },
  "scenes": [ "... 現行 4 scene を後方互換で維持 (Remotion は images/events を使う)" ],
  "images": [
    {
      "image_id": "img-001",
      "scene_block": "hook",
      "purpose": "anchor_visual_for_hook",
      "image_prompt": "near-black background, abstract investigative documentary infographic style, off-white text foreground, single hydrangea blue accent, no faces, no real places, sober editorial layout, source-driven, restrained, high-density, sharp, 9:16 vertical composition",
      "negative_prompt": "no cinematic lighting, no thriller mood, no dramatic shadows, no photorealistic reenactment, no real faces, no fake footage, no emotional gore, no red cross emblem, no ICRC uniform, no battlefield imagery",
      "visual_safety_level": "elevated",
      "must_avoid": ["real faces", "real prisons", "ICRC uniforms", "red cross", "battle scenes"]
    }
  ],
  "events": [
    {
      "event_id": "evt-001",
      "timestamp_start_sec": 0,
      "timestamp_end_sec": 4,
      "scene_block": "hook",
      "type": "title_card",
      "text": "9,600 という数字の意味",
      "source_ref": null,
      "animation": "fade-in",
      "safety_flags": ["no_real_faces", "no_real_places"],
      "associated_image_id": "img-001"
    },
    {
      "event_id": "evt-002",
      "timestamp_start_sec": 4,
      "timestamp_end_sec": 20,
      "scene_block": "setup",
      "type": "number_card",
      "text": "9,600",
      "subtitle": "Palestinian detainees in Israeli prisons",
      "source_ref": "TeleSUR 2026-XX-XX",
      "source_url": "https://...",
      "animation": "cut",
      "safety_flags": ["source_required"],
      "associated_image_id": "img-002"
    }
  ]
}
```

(events[] は 10 個構成: hook 2 / setup 2 / twist 4 / punchline 2)

---

## 3. 設計の核心

- `images[]` (6-8 枚) と `events[]` (10 個) を分離 (1 image を複数 event で
  再利用可能 — ベース画像点数を抑えつつ視覚展開を増やす)
- 各 event は最低限の固定フィールド
  (timestamp / scene_block / type / text / source_ref / animation /
  safety_flags / associated_image_id)
- `associated_image_id` で event と image を疎結合に紐付け
- 第一作 animation は `fade-in` / `cut` / `dissolve` の **3 種のみ**
  (ADR-0002 D-minimal)
- `scene_block` で現行 4 scene 構造に接続 (後方互換、`scenes[]` は残置)
- 第二作以降の拡張余地を構造で許容
  (animation 種別追加、event type 拡張、images 増加 — モデルを破壊せず追加)

### 現行 4 scene → 新 images/events マッピング (第一作 MVP)

| scene_block | duration | images | events | event types 例 |
|---|---|---|---|---|
| hook | 4s | 1-2 | 2 | title_card, number_card |
| setup | 16s | 2 | 2 | number_card, source_card |
| twist | 40s | 2-3 | 4 | claim_card, source_card, number_card |
| punchline | 20s | 1 | 2 | claim_card, title_card |
| **計** | 80s | **6-8** | **10** | — |

---

## 4. フィールド設計の根拠 (ADR トレーサビリティ)

| フィールド | 由来 ADR | 根拠 |
|---|---|---|
| `image_prompt` 末尾 5 色 + 採用語彙 | ADR-0001 | ブランドカラー / トーン語彙の強制 |
| `negative_prompt` / `must_avoid` | ADR-0003 | 実在人物 NG / ICRC 標章 NG 等、現行 `_BASE_NEGATIVE` の防御姿勢を構造継承 |
| `visual_safety_level` | 現行実装 §3 | strength → standard/elevated/strict マップを継承 |
| `animation` 3 種限定 | ADR-0002 | D-minimal (Ken Burns / キネティックタイポ禁止) |
| `source_ref` / `source_url` | ADR-0003 | 数字・固有名詞に出典必須 (source_card) |
| `safety_flags` | ADR-0003 | 投稿前ゲートチェックリストの機械判定材料 |
| `scene_block` | Task B §2 | 現行 4 scene 構造との後方互換 |

---

## 5. Phase A.5-3b 実装時の未決論点 (本バッチではスコープ外、論点提示のみ)

1. **image_prompt 生成主体**: 現行 `_make_video_prompt()` はテンプレ決定論
   (LLM 非関与、Task B §4)。新 `image_prompt` を (a) テンプレ拡張で生成するか、
   (b) 分析フェーズ LLM に書かせるか。クラウド誤り 9 (各論コントロールの誘惑)
   との関係で、ブランドカラー/トーン語彙は **構造データとして固定**し、
   構図・主題は LLM に委ねる折衷が有力 (Phase A.5-3b で判断)。
2. **scenes[] と images[]/events[] の責務分離**: scenes[] を完全に維持して
   Remotion は images/events のみ参照するか、scenes[] を段階的に廃止するか。
   第一作は後方互換優先 (scenes[] 残置) を推奨。
3. **video_payload_writer.py 改修範囲**: 不変原則対象外だが、最小改変
   (新フィールド追加のみ、既存 scene 生成は不変) を推奨 (動くものを壊さない)。
4. **モデル拡張**: `src/shared/models.py` に `VideoImage` / `VideoEvent`
   モデル新設 + `VideoPayload` に `images` / `events` フィールド追加
   (Optional default で後方互換、既存テスト 1417 を壊さない設計が前提)。

これらは Phase A.5-3b 第一作起案バッチで決定する (FUTURE_WORK 登録済み)。
