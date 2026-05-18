# 現行 video_payload 構造の精密調査 (Task B)

調査日: 2026-05-18
対象: `src/generation/video_payload_writer.py` (HEAD `8dc62da`、**調査のみ・改修なし**)
本番出力サンプル: `data/output/cls-e2429c77f48e_video_payload.json`
(F-trial-run-post-llm-extraction Slot-1、Ukrainian drones / Russian EW、Meduza)

> 本調査は F-trial-run-post-llm-extraction の事前調査
> (`video_payload_audit.json`) を実コード読解で精密化したもの。事前調査結論
> (image_prompt 非存在・4 scene・統一末尾なし) は **コード読解でも完全に裏付け
> られた**。

---

## 1. 現行フィールド一覧

### 1.1 VideoPayload (トップレベル) — `src/shared/models.py:271-276`

| フィールド | 型 | 内容 |
|---|---|---|
| `event_id` | str | クラスタ ID (例: `cls-e2429c77f48e`) |
| `title` | str | event.title (英語原題そのまま) |
| `scenes` | list[VideoScene] | **常に 4 要素** (script の 4 ブロックに 1:1) |
| `total_duration_sec` | int | scenes の duration_sec 合計 (サンプルは 80) |
| `metadata` | dict | 後述 (title_layer / director / analysis 由来メタを集約) |

### 1.2 VideoScene (1 シーン) — `src/shared/models.py:252-268`

| フィールド | 型 | 生成元 | 内容 |
|---|---|---|---|
| `index` | int | enumerate | 0-3 |
| `narration` | str | script.sections[i].body | 台本本文 (LLM 生成) |
| `visual_hint` | str | `_VISUAL_HINTS[heading]` | 日本語の制作ヒント (テンプレ固定) |
| `duration_sec` | int | section.duration_sec | hook=4 / setup=16 / twist=40 / punchline=20 |
| `scene_id` | str | `{event.id}_s{i:02d}_{heading}` | 例 `cls-..._s02_twist` |
| `heading` | str | section.heading | hook / setup / twist / punchline |
| `visual_goal` | str | `_VISUAL_GOALS[heading]` | 日本語の演出目的 (テンプレ固定) |
| `visual_mode` | str | `_resolve_mode(heading, strength)` | anchor_style / document_style / structure_diagram 等 |
| `video_prompt` | str | `_make_video_prompt()` | **英語の映像生成プロンプト (テンプレ条件分岐生成、LLM 非関与)** |
| `negative_prompt` | str | `_make_negative_prompt()` | 安全ネガティブ (テンプレ固定 + 条件加算) |
| `on_screen_text` | str | `_make_on_screen_text()` 等 | 字幕/サムネ用テキスト |
| `must_include` | list[str] | `_make_must_include()` | 日本語の必須要素 |
| `must_avoid` | list[str] | `_make_must_avoid()` | 日本語の禁止要素 |
| `source_grounding` | list[str] | `_make_source_grounding()` | ソース地域 (例 `["russia_cis"]`) |
| `transition_hint` | str | `_TRANSITION_HINTS[heading]` | トランジション指示 (テンプレ固定) |

### 1.3 `image_prompt` フィールドは存在しない

`VideoScene` / `VideoPayload` モデル定義・実装・本番出力すべてに `image_prompt`
フィールドは **存在しない**。映像生成志向の `video_prompt` のみ。これは
F-image-prompt-spec バッチプロンプトが当初想定した「既存 image_prompt の品質
改善」という前提が成立しないことを意味する (スコープ再定義の根拠)。

---

## 2. 現行 4 scene 設計の構造

`write_video_payload()` (`video_payload_writer.py:355-511`) は
`script.sections` を `enumerate` で回し、**section と scene を 1:1 対応**させる。
script_writer の既存ルートが hook/setup/twist/punchline の 4 ブロックを生成する
ため、scene は **構造的に必ず 4 個**。バッチプロンプト旧想定の「12-15 scene /
80秒」は実装上発生し得ない。

| heading | duration | visual_mode (partial 時) | 役割 (visual_goal) |
|---|---|---|---|
| hook | 4s | `anchor_style` | 注意喚起・テーマ一言提示 |
| setup | 16s | `document_style` | 公式発表・建前を「建前」として提示 |
| twist | 40s | `structure_diagram` | 裏の構造・地政学/カネ/権力を図解で暴く |
| punchline | 20s | `infographic` | 価値観を揺さぶる結末 + loop 機構定着 |

`visual_mode` は `_resolve_mode(heading, strength)` で `evidence_strength`
(strong/partial/weak) により分岐 (`_VISUAL_MODES`)。strength は
`_get_evidence_strength()` がソース地域構成から判定 (jp+non-jp=strong /
何かしらある=partial / なし=weak)。サンプルは partial。

旧 heading (fact / arbitrage_gap / background / japan_impact) のテンプレも
後方互換で全関数に残置されているが、現行 script_writer の出力では発火しない。

---

## 3. 現行 visual_safety_level の動作

`write_video_payload()` 末尾で evidence_strength から決定的にマップ
(`video_payload_writer.py:430`):

```python
safety_level = {"strong": "standard", "partial": "elevated", "weak": "strict"}[strength]
```

- `strong` → `standard`
- `partial` → `elevated` (サンプルはこれ)
- `weak` → `strict`

`visual_safety_level` 自体は **payload.metadata に格納される情報ラベル**であり、
これ自体が画像生成を制御するわけではない。実際の安全制御は
`negative_prompt` / `must_avoid` の内容で表現される。

### negative_prompt の構成 (`_make_negative_prompt()`)

- `_BASE_NEGATIVE` (常時): photorealistic reenactment / 実在人物顔アップ /
  架空会談シーン / 戦闘・戦争映像 / 実在人物の AI 生成肖像 /
  誤誘導ドキュメンタリー映像 — の 6 禁止
- `strength == "weak"` 時: `_WEAK_EVIDENCE_NEGATIVE_EXTRA` を加算
  (実イベント location のストック映像、断定的アーカイブ映像等)
- 仮説系 heading (twist/punchline + 旧 arbitrage_gap/background/japan_impact)
  かつ weak/partial 時: `_HYPOTHESIS_NEGATIVE_EXTRA` を加算

→ 現行実装は **デフォルトで強い安全方向** に倒れる設計。これは ADR-0003
(コンテンツモラル) の禁止事項とすでに方向性が一致しており、schema 拡張時も
この防御姿勢を後退させてはならない。

---

## 4. 現行 prompt 生成ロジック (LLM 非関与の確定)

### 4.1 video_payload 生成プロンプトは存在しない

`grep -rl "video_payload\|video_prompt\|VideoPayload" configs/prompts/`
→ **0 件**。`video_prompt` は `_make_video_prompt()` の Python 条件分岐
(heading × strength) による **f-string テンプレート組み立て**であり、LLM 呼び出し
を一切伴わない。`configs/prompts/` 配下に video_payload 用プロンプトファイルは
存在しない (台本本文は別途 script_writer の LLM プロンプトで生成済み、
video_payload_writer はそれを scene に詰め替えるだけ)。

### 4.2 含意

- 現行の画像/映像プロンプトは **完全に決定論的なテンプレ出力**。
  ブランドカラー・ブランドトーン語彙の概念は一切埋め込まれていない。
- ADR-0001 のブランドカラー 5 色パレット / トーン語彙を反映するには、
  Phase A.5-3b で `_make_video_prompt()` 相当のロジック (またはその後継)
  に手を入れる必要がある (本バッチではやらない、設計のみ)。
- LLM に画像プロンプトを書かせるか / テンプレを拡張するかは Phase A.5-3b の
  実装判断 (schema_extension_design.md §5 で論点提示)。

---

## 5. metadata に集約される情報 (参考)

`write_video_payload()` は以下を metadata に統合 (`video_payload_writer.py:484-505`):

- 基本: category / source / tags / published_at / 各 duration / platform_profile
- visual brief: visual_profile (`news_explainer_shared` 固定) /
  visual_safety_level / evidence_strength / scene_count /
  uses_multi_region_comparison / source_regions
- `**title_meta`: canonical_title / platform_title / hook_line /
  thumbnail_text (LLM 優先 + template fallback の両方保存) / title_strength 等
- `**director_meta`: director_thought / selected_pattern / target_enemy /
  loop_mechanism / seo_keywords / hook_variants
- `**analysis_meta`: analysis_result が渡された時のみ
  (selected_perspective / selected_duration_profile / visual_mood_tags /
  analysis_version)。**本番試運転では analysis_result=null = 未発火**
  (旧ルート write_script 経由のため、CURRENT_STATE §"docs と production の乖離"
  と整合)。

---

## 6. 結論: F-image-prompt-spec スコープ確定

| バッチプロンプト旧想定 | 現行実装の実態 | 帰結 |
|---|---|---|
| `image_prompt` フィールドの品質改善 | `image_prompt` 非存在、`video_prompt` のみ | **新設 or video_prompt 拡張の設計判断バッチ**へ再定義 |
| 統一シネマティック末尾あり | 統一末尾なし、scene 独立記述 | ADR-0001 で 5 色パレット末尾を**新たに導入**する設計 |
| 12-15 scene / 80秒 | **構造的に必ず 4 scene** | images[] と events[] の分離設計 (ADR-0002 / schema_extension_design) |
| (安全性) | デフォルト強い negative_prompt、safety_level=elevated | ADR-0003 と方向一致、後退させない |

→ 本バッチは「現行構造を ADR + schema 設計に正典化し、Phase A.5-3b 実装の
前提を固定する」ドキュメントバッチとして遂行する (実装は一切しない)。
事前調査結果との乖離は **なし** (image_prompt 非存在・4 scene・統一末尾なしを
コード読解で確認 = バッチプロンプト「想定外結果への対処」の即停止条件には
該当しない、想定通り)。
