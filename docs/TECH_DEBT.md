# TECH_DEBT.md — 技術的負債リスト（Hydrangea）

> このドキュメントは、現状のコードを読んで見つけた「今後困りそうな部分」を、エンジニア素人の方にもわかるように列挙したものです。
> 作成日：2026-04-23

---

## 目次

1. [⚠️ 最優先：セキュリティの問題](#1-️-最優先セキュリティの問題)
2. [ハードコードされた値](#2-ハードコードされた値)
3. [エラーハンドリングの不足](#3-エラーハンドリングの不足)
4. [命名・設計の不統一](#4-命名設計の不統一)
5. [テストの不足](#5-テストの不足)
6. [重複・巨大化したコード](#6-重複巨大化したコード)
7. [ドキュメントの古さ・不足](#7-ドキュメントの古さ不足)

---

## 用語の約束（TECH_DEBT 専用）

| 用語 | 素人向けの意味 |
|---|---|
| **`.gitignore`**（ギットイグノア） | Git のバージョン管理から外すファイル／フォルダを指定するリスト。 |
| **コミット** | Git で「変更をスナップショット保存」すること。 |
| **履歴** | Git に保存された過去のスナップショットの連なり。 |
| **ハードコード** | 値を直接コードに書き込んでしまうこと（設定ファイルで変えられない）。 |
| **マジックナンバー** | ハードコードの一種で、「なぜこの数字なのか」が説明されていない数字。 |
| **DRY**（Don't Repeat Yourself） | 「同じロジックを複数箇所に書かない」という原則。 |
| **リーク**（leak） | 秘密情報が外に漏れること。 |

---

## 1. ⚠️ 最優先：セキュリティの問題

### 🔴 問題 1.1：`.gitignore` のバグで `.venv/` が Git にコミット済み（**緊急度：高**）

**問題点**

`.gitignore` の 1 行目が `.env.venv/` となっています。これは「`.env.venv/` というフォルダを無視する」という意味になり、**本来無視したい `.venv/` は無視されません**。

```
.gitignore:
1: .env.venv/     ← バグ。.venv/ を無視する意図だったはず
2: .env
3: __pycache__/
4: *.pyc
5: data/
```

実際に `git ls-files | grep ".venv/" | wc -l` で確認したところ、**3,878 個の `.venv/` 配下ファイルが Git にコミット済み**でした（`cfab968 chore: initial snapshot` で大量に混入）。

**なぜ問題か（素人向け）**

- `.venv/` は Python の「仮想環境」で、OS ごとにインストールされた依存ライブラリが大量に入っています。
- これを Git に含めると：
  - **リポジトリサイズが数百 MB に膨らむ**（クローンが遅くなる）
  - **OS 依存のバイナリが混ざる**（Mac で作った .venv を Windows で使うと壊れる）
  - **セキュリティ更新があった時、ライブラリのバージョンが固定されていて危険**
  - git の履歴がノイズだらけになり差分が読みにくい

**どう直すべきか**

1. `.gitignore` を正しく修正：
   ```
   .venv/
   .env
   __pycache__/
   *.pyc
   data/
   ```
2. 既にコミットされている `.venv/` を履歴から削除：
   ```bash
   git rm -r --cached .venv
   git commit -m "fix: .venv をリポジトリから除外（.gitignore バグ修正）"
   ```
   （履歴からも完全消去したい場合は `git filter-repo` が必要。チームで運用中なら事前相談必須。）

**緊急度：高** — 動作には影響しないが、チームで共有する前に直すべき。

---

### 🔴 問題 1.2：`.env` に本物の API キーが平文保存されている（**緊急度：中**）

**問題点**

`.env:3` に実際の Gemini API キー（`AIzaSyAdbm...`）が書かれています。

```
.env:3: GEMINI_API_KEY=AIzaSyAdbmbzBOHO9FTMSbrotCsK9mBvrn4EiwA
```

**良いニュース**：`git log -p -S "AIzaSy"` で履歴を全検索したところ、**このキーは Git 履歴には一度も含まれていません**（`.gitignore` の 2 行目 `.env` は効いている）。

**なぜ問題か（素人向け）**

- このキーは **Google 有料枠に請求が発生する鍵**。漏れたら悪用される可能性。
- 現状、.env のままでもローカル利用に限れば問題ないが、次のリスクあり：
  - **誰かが間違えて `.env` を Git にコミットしたら即座に漏れる**（ .gitignore を誤修正した時の事故）
  - **画面共有・スクリーンショット・配布用 zip 作成時**に混入する
  - 問題 1.1 を直す過程で `.gitignore` を書き換えて事故る可能性

**どう直すべきか**

1. **今すぐ**：Google AI Studio で該当キーを **ローテーション（再発行）**する。旧キーは無効化。
2. 新キーは macOS Keychain か 1Password などのシークレット管理ツールに保管し、`.env` への転記は最小限に。
3. チーム共有する場合は、`.env` を使わず `gcloud auth` 等のクラウドネイティブな認証に移行検討。
4. もし Git 履歴に万が一キーが含まれていた場合は、必ずキーを失効させる（履歴を消してもクローン済みの相手からは消せないため）。

**緊急度：中** — 漏洩は確認されていないが、本番運用前に必ずローテーション。

---

### 🔴 問題 1.3：`.gitignore` に `.DS_Store` が無い（**緊急度：低**）

**問題点**

macOS 特有の `.DS_Store` ファイル（1 ルートに 1 個）が放置。現状コミットはされていないが、`.gitignore` に書かれていないため、うっかりコミットのリスクあり。

**どう直すべきか**

```
.gitignore に追加：
.DS_Store
**/.DS_Store
```

**緊急度：低**

---

## 2. ハードコードされた値

### 🟡 問題 2.1：編集方針プロンプトが完全に日本向け固定（**緊急度：高**）

**該当箇所**

- `src/triage/prompts.py:6-115` — 全文 115 行の日本語プロンプト
- `src/generation/script_writer.py:268-446` — 台本生成の「武器庫 6 パターン」定義（全文日本語、Japan 想定）

**問題点**

トリアージ（選定）と台本生成のプロンプトが**「日本の視聴者向け」に完全に固定**されており、他チャンネル（韓国エンタメ・スポーツ）にそのまま流用できない。

例（`src/triage/prompts.py:14`）：

```
ターゲット: 20代後半〜40代の、知的好奇心が高く、世界の動きで損をしたくない日本人ビジネス層。
```

例（`src/generation/script_writer.py:284`）：

```
**`target_enemy`** — 財務省/日銀・大手メディア・米国政府/中国共産党・GAFAM・既存秩序 から選べ。
```

**なぜ問題か**

マルチチャンネル化（目的 A）で、これらプロンプトを YAML 駆動にしない限り、3 チャンネルに別 Python コピーを用意するしかない。

**どう直すべきか（REFACTORING_PLAN と共通）**

- プロンプトを `configs/channels/{channel_id}.yaml` に外出し
- `channel_id` を引数で受け取り、対応する YAML からプロンプト本文を動的にロード

**緊急度：高**（マルチチャンネル化の主要ブロッカー）

---

### 🟡 問題 2.2：カテゴリ別ベース点数がハードコード（**緊急度：高**）

**該当箇所**：`src/triage/scoring.py:9-16`

```python
CATEGORY_BASE = {
    "economy":       85.0,
    "politics":      80.0,
    "technology":    75.0,
    "startup":       70.0,
    "sports":        60.0,
    "entertainment": 55.0,
}
```

**問題点**

- Geopolitical Lens は経済・政治中心で OK だが、**Japan Athletes Abroad ではスポーツがベース 60 では絶対選ばれない**。
- K-Pulse ではエンタメが 55 では選ばれない。

**どう直すべきか**

- `channels/{channel_id}.yaml` に `category_base:` セクションを移す。
- スポーツチャンネルなら `sports: 95.0, economy: 40.0` のように上書き。

**緊急度：高**

---

### 🟡 問題 2.3：重要キーワード辞書が全て日本経済・地政学向け（**緊急度：高**）

**該当箇所**：`src/triage/scoring.py:19-200` 周辺

- `HIGH_IMPACT_KEYWORDS`（19-30）：利上げ+10, 利下げ+10, 増税+8, 少子化+7
- `_TECH_KW`, `_TECH_GEO_KW`（112-121）：半導体・輸出規制・経済安保
- `_BIG_EVENT_KW`（122-128）：選挙・日銀・fed
- `_GEO_CONFLICT_KW`（129-134）：ウクライナ・台湾・安保
- `_SPORTS_KW`（135-139）：大谷・オリンピック（ここだけチャンネル2で使える）
- `_JAPANESE_PERSON_KW`（171-181）：孫正義・大谷翔平・宮崎駿
- `_BREAKING_SHOCK_KW`（184-200）：停戦・制裁・デフォルト
- `_INDIRECT_JAPAN_IMPACT_KW`（237-297）：ホルムズ海峡・TSMC・円安

**問題点**

合計 100 個以上のキーワードが `scoring.py` の**ソースコードに直書き**されている。

**どう直すべきか**

- `channels/{channel_id}/keywords.yaml` に移す（REFACTORING_PLAN で詳述）。
- スコアリング関数は YAML をパラメータで受け取る形に変える。

**緊急度：高**

---

### 🟡 問題 2.4：動画サイズ・フォーマットが「縦型 Shorts 専用」前提（**緊急度：中**）

**該当箇所**

- `src/shared/config.py:161-164`：`VIDEO_WIDTH=720`, `VIDEO_HEIGHT=1280`, `VIDEO_FPS=30`
- `src/generation/video_renderer.py:44-46`：`DEFAULT_WIDTH=720, DEFAULT_HEIGHT=1280, DEFAULT_FPS=30`
- `src/generation/script_writer.py:42-64`：PLATFORM_PROFILES（shared=80秒, tiktok=72秒, youtube_shorts=78秒）

**問題点**

3 チャンネル全て縦型 Shorts なので当面問題は出ないが、**将来横型 YouTube 動画や 16:9 Instagram Reels に展開したい場合、ここが障害になる**。

**どう直すべきか**

- Remotion 移行後は Remotion の Composition 定義（`width`/`height`/`fps`/`durationInFrames`）で統一される想定。
- それまでは `configs/base.yaml` に `video_output:` セクションを作り、`channels/*.yaml` で上書き可能にする。

**緊急度：中**

---

### 🟡 問題 2.5：macOS の `say` コマンドに依存（**緊急度：中**）

**該当箇所**：`src/generation/audio_renderer.py:120-130`

```python
subprocess.run([
    "say",
    "-v", voice,                                # 既定 "Kyoko"
    "-o", tmp_path,
    f"--data-format=LEI16@{framerate}",
    text,
], ...)
```

**問題点**

- macOS 以外では `FileNotFoundError` で即座に無音フォールバック → 動画は全部無音で出荷されてしまう。
- Linux のクラウド実行環境（GitHub Actions / AWS EC2）では動かない。
- 音質が TikTok のプロ音声に比べてやや機械的。

**なぜ問題か**

- マルチチャンネル化（特に **K-Pulse 韓国エンタメ**）で韓国語ボイスを使いたい場合、`say -v Kyoko` では対応できない。macOS には韓国語 `Yuna` がある。
- Remotion 移行とセットで、クラウド TTS（Google Cloud TTS, ElevenLabs, OpenAI TTS-1 など）への切り替えを検討すべき。

**どう直すべきか**

- `AudioRenderer` を **抽象クラス**にし、具体実装として `SayRenderer`, `ElevenLabsRenderer`, `GoogleCloudTTSRenderer` を用意。
- `channel_id` or `channels/*.yaml` の `audio.provider` で選択。
- 中期的には macOS 依存から脱却。

**緊急度：中**（現状動くが、クラウド運用の障害）

---

### 🟡 問題 2.6：フォント検索パスが macOS 依存（**緊急度：低**）

**該当箇所**：`src/generation/video_renderer.py:110-116`

```python
_JP_FONT_CANDIDATES = [
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W2.ttc",
    ...
]
```

**問題点**

Linux では同パスに該当フォントが存在しないため `ImageFont.load_default()` に落ちる。デフォルトフォントは日本語が文字化け。

**どう直すべきか**

- Remotion 移行で `video_renderer.py` は丸ごと廃止する計画なので、それまで放置でよい。
- Remotion 側は React で Web フォント（Noto Sans JP 等）を使えば OS 非依存。

**緊急度：低**（Remotion 移行で解消予定）

---

### 🟡 問題 2.7：台本 4 ブロックの文字数境界がマジックナンバー（**緊急度：低**）

**該当箇所**：`src/generation/script_writer.py:33-38`

```python
_CHAR_BOUNDS: dict[str, tuple[int, int]] = {
    "hook":      (8,   22),
    "setup":     (60,  90),
    "twist":     (150, 220),
    "punchline": (70,  110),
}
```

**問題点**

- 「なぜ 60〜90 なのか」がコメント無し。`_JP_CHARS_PER_SEC = 4.5` から逆算と推測できるが、明記されていない。
- スポーツ・エンタメチャンネルでテンポを変えたい時に、調整の根拠が不明。

**どう直すべきか**

- コメントに「setup=16秒 × 4.5字/秒 = 72字を中心に ±15% の余裕」のように根拠を書く。
- 長期的には `channels/*.yaml` の `script.duration` から自動計算。

**緊急度：低**

---

### 🟡 問題 2.8：日英翻訳辞書が 38 ペア以上のハードコード（**緊急度：中**）

**該当箇所**：`src/ingestion/cross_lang_matcher.py:23-82`

```python
_COUNTRY_MAP = {
    "日本": "japan", "米国": "usa", "アメリカ": "usa", "中国": "china", ...
}
_ENTITY_MAP = {
    "日本銀行": "boj", "ＦＲＢ": "fed", "国際通貨基金": "imf", ...
}
_KEYWORD_MAP = {
    "利上げ": "rate hike", "減税": "tax cut", ...
}
```

**問題点**

- スポーツチャンネルでは「大谷翔平→Shohei Ohtani」などスポーツ用語の辞書が必要。
- 韓国エンタメなら「BLACKPINK→ブラックピンク」など日韓対訳が必要。
- 現状のコードに手を入れないと拡張できない。

**どう直すべきか**

- `configs/dictionaries/{channel_id}.yaml` に外出し。
- ベース辞書（`configs/dictionaries/common.yaml`）＋チャンネル固有辞書のマージ方式。

**緊急度：中**

---

### 🟡 問題 2.9：モデル名が 4 Tier 固定でチャンネル別差別化不可（**緊急度：低**）

**該当箇所**：`.env:7-13`、`src/shared/config.py:56-65`

現状 `GEMINI_MODEL_TIER1` などは global 固定で、チャンネルごとに別のモデル（例：スポーツチャンネルは安いモデルでよい）を使えない。

**どう直すべきか**

- `channels/{channel_id}.yaml` に `llm.model_tiers:` セクションを作り、未指定なら `base.yaml` の global 値を使う。

**緊急度：低**

---

## 3. エラーハンドリングの不足

### 🟡 問題 3.1：YAML 読み込み失敗が致命的ではなくなっている（**緊急度：中**）

**該当箇所**：`src/main.py:137-151`

```python
try:
    import yaml
    _sources_path = Path("configs/sources.yaml")
    if _sources_path.exists():
        with open(_sources_path, encoding="utf-8") as _f:
            _sources_cfg = yaml.safe_load(_f)
        ...
except Exception:
    pass  # メタデータ読み込み失敗時はデフォルト値にフォールバック
```

**問題点**

`except Exception: pass` で**黙って失敗を握りつぶしている**。YAML が壊れていても何もログに出ない。

**なぜ問題か**

マルチチャンネル化後、YAML の構文エラーを発見しづらくなる。運用中にレポートのメタデータが欠損する原因を追えない。

**どう直すべきか**

```python
except Exception as exc:
    logger.warning(f"sources.yaml 読み込み失敗（デフォルト値使用）: {exc}")
```

**緊急度：中**

---

### 🟡 問題 3.2：`audio_renderer.py` の TTS 失敗が静かすぎる（**緊急度：中**）

**該当箇所**：`src/generation/audio_renderer.py:144-152`

```python
except FileNotFoundError:
    logger.info("[AudioRenderer] `say` command not found — using silent placeholder.")
    return _make_silence(len(text) * 0.06, framerate), True
```

**問題点**

- ログレベルが `info` なので、大量の placeholder 発生時も目立たない。
- **全セグメントが placeholder になった場合は MP4 組み立てを中止する安全網**が `src/main.py:2092-2103` にあるが、`say` が壊れている初期設定時に気づきにくい。

**なぜ問題か**

「音声なしの無音動画」が「成功」として publish カウントに加算されてしまう事故が過去にあった（`main.py:2088` のコメント参照）。

**どう直すべきか**

- `say` 存在チェックを事前に 1 回だけ行い、`FileNotFoundError` なら `WARN` ログを出し、`AUDIO_RENDER_ENABLED=True` のときは起動時に明示的に失敗させる。

**緊急度：中**

---

### 🟡 問題 3.3：LLM レスポンスの JSON パース失敗処理がばらつく（**緊急度：中**）

**該当箇所**：複数

- `src/generation/script_writer.py`：内部 ScriptDraft でパース → 失敗時は `_build_script_fallback`
- `src/triage/gemini_judge.py:85-100`：`parse_error` を `judge_error_type` に記録
- `src/ingestion/event_builder.py:799-825`：LLM クラスタ合体判定はパース失敗時は「非合体」扱い

**問題点**

各所で JSON パース失敗の扱いが違う。共通のバリデーション層がない。

**どう直すべきか**

- `src/llm/retry.py` に `call_llm_with_schema(prompt, schema)` のようなヘルパを作り、Pydantic スキーマで自動バリデーション。
- 失敗時の fallback 戦略を呼び出し側が明示する。

**緊急度：中**

---

### 🟡 問題 3.4：`subprocess.run` のタイムアウトが一律 60 秒／120 秒（**緊急度：低**）

**該当箇所**

- `audio_renderer.py:129`：`timeout=60`（TTS）
- `video_renderer.py:421`：`timeout=120`（ffmpeg mux）

**問題点**

長尺の台本（80 秒）でも既定 60 秒で止まる可能性。`TTS_TIMEOUT_SEC` 環境変数はあるが、`video_renderer.py` の 120 は変数化されていない。

**どう直すべきか**

- `FFMPEG_MUX_TIMEOUT_SEC` 環境変数を追加。

**緊急度：低**

---

## 4. 命名・設計の不統一

### 🟡 問題 4.1：後方互換のため同じ概念の 3 重フィールドが残る（**緊急度：中**）

**該当箇所**：`src/shared/models.py:41-46`

```python
sources_jp: list[SourceRef] = Field(default_factory=list)   # 旧
sources_en: list[SourceRef] = Field(default_factory=list)   # 旧
sources_by_locale: dict[str, list[SourceRef]] = Field(...)  # 新（推奨）
```

そして `NewsEvent._derive_sources_by_locale()` で旧→新を自動導出。

**問題点**

下流コード（scoring, appraisal, script_writer など）で「旧を見る／新を見る／両方見る」の使い分けが混在。例：

- `src/main.py:2443-2454`：Elite Judge では `sources_by_locale` を優先、fallback で `sources_jp + sources_en`
- `src/generation/video_payload_writer.py:114-120`：`sources_by_locale` のみで評価

**なぜ問題か**

マルチチャンネル化で新しい region（例：`korea`）を追加する時、「どこが sources_by_locale を見ていて、どこが sources_en しか見ていないか」を全て追いかける必要がある。

**どう直すべきか**

- 新規 1 リリースで `sources_jp` と `sources_en` に Deprecation 警告を付け、全呼び出し側を `sources_by_locale` に寄せる。
- 2 リリース後に旧フィールドを削除。

**緊急度：中**

---

### 🟡 問題 4.2：`main.py` に「旧 heading」と「新 heading」の 2 系統が残る（**緊急度：低**）

**該当箇所**：`src/generation/video_payload_writer.py:10-86`

```python
_VISUAL_HINTS = {
    # 新 heading（script_writer の 4 ブロック構成）
    "hook": "...", "setup": "...", "twist": "...", "punchline": "...",
    # 旧 heading（後方互換）
    "fact": "...", "arbitrage_gap": "...", "background": "...", "japan_impact": "...",
}
```

**問題点**

古いデータとの互換性のために残しているが、実データに旧 heading はもう来ない。コード量が倍になって読みにくい。

**どう直すべきか**

- 旧 heading を使う古い `script.json` が `data/archive/` に残っていないか確認した上で、旧ブロックを削除。

**緊急度：低**

---

### 🟡 問題 4.3：`_` プレフィックス変数が巨大関数内で乱立（**緊急度：低**）

**該当箇所**：`src/main.py:2500-3188`（`run_from_normalized` 関数）

```python
_slot_records, _published_event_id, _published_event_ids, _rescue_triggered,
authority_pair, _av_summary, _slot_av_summaries, _slot_judge, _slot_authority_pair,
_live_publishes, _slot_record, _ev_id, _slot_av, _candidate_to_generate,
_selection_override_applied, _completed_count, _any_archivable, ...
```

**問題点**

- 1 関数内で `_` プレフィックス付きローカル変数が 30 個以上。
- Python では `_` は「プライベート」を意味する慣例だが、関数内ローカル変数に使うのは冗長。
- 新メンバーが読めない。

**どう直すべきか**

- `run_from_normalized` を以下のフェーズに分割（目安 200 行程度のサブ関数）：
  - `_prepare_batch()`
  - `_build_and_rank_events()`
  - `_apply_filters()`（garbage → viral → elite_judge → gemini_judge）
  - `_select_slot1()`
  - `_generate_top3()`
  - `_finalize_and_archive()`

**緊急度：低**（機能に影響はない）

---

### 🟡 問題 4.4：`src/main.py` が 3,303 行の「神ファイル」（**緊急度：中**）

**問題点**

`main.py` だけで 3,303 行。通常 Python ファイルは 500 行以下が目安。`_save_run_summary`（500 行以上）、`_write_latest_candidate_report`（480 行）など巨大ヘルパが混在。

**なぜ問題か**

- 変更時の差分が読めない
- テストが書きにくい（全部 `main.py` インポートが必要）
- マルチチャンネル化の改修で衝突が起きやすい

**どう直すべきか**

次のように分割（REFACTORING_PLAN で詳述）：

```
src/
├── main.py                        # CLIパーサと run() / run_from_normalized() のみ（~300行）
├── pipeline/
│   ├── runner.py                  # オーケストレーション本体（~500行）
│   ├── budget_init.py             # _make_budget
│   ├── slot_selection.py          # _find_eligible_judged_slot1 ほか
│   ├── reports.py                 # _save_run_summary, _write_latest_candidate_report
│   ├── pool.py                    # _build_combined_candidate_pool
│   └── archive.py                 # _archive_batch
```

**緊急度：中**（マルチチャンネル化前に着手推奨）

---

## 5. テストの不足

### 🟢 観察 5.1：テストカバレッジは広いが偏りあり（**緊急度：低**）

tests/ に 31 ファイル。広く網羅されているが、次が弱い：

| 弱い分野 | 観察 |
|---|---|
| **実際の LLM 呼び出しを伴う E2E** | ほぼ全部モック。Gemini が実際にどういう JSON を返すか、どこで壊れるかのリアル検証が無い。 |
| **マルチチャンネル想定のテスト** | 当然まだ無い。リファクタ後に追加必須。 |
| **`rss_fetcher.py` の HTTP エラー処理** | `feedparser.parse` の失敗パスが未テスト（RSS が 404、Network Error、SSL エラー等）。 |
| **`video_renderer.py` のフォント不在経路** | macOS 特有フォントパスが無い環境のテストなし。 |
| **`.env` 未設定での起動失敗** | `GEMINI_API_KEY` が空の場合のエラーメッセージ品質は未検証。 |

**どう直すべきか**

- マルチチャンネル化の改修時に「チャンネル別スナップショットテスト」を追加。
- RSS 取得については `feedparser.parse` を HTTP モックして 404/timeout のテストを追加。

**緊急度：低**

---

### 🟢 観察 5.2：リグレッションテストの「動画バイナリ比較」が無い（**緊急度：中**）

**問題点**

- Remotion 移行時に「移行前後で同じ MP4 が出るか」を自動検証する仕組みがない。
- 現行 MP4 の SHA256 や尺・フレーム数のスナップショットが `tests/` に無い。

**どう直すべきか**（REFACTORING_PLAN で詳述）

- 移行前に：代表的な 1 イベントで現行 MP4 を生成し、`tests/golden/` に保存。
  - MP4 の **尺**（秒）
  - **解像度**（720x1280）
  - **シーン分割時刻のリスト**（render_manifest.json の scene_timing）
  - **音声のテキスト書き起こし**（既に voiceover_segments.json にある）
- 移行後に：同じイベントを Remotion で生成し、上記 4 指標を比較。ピクセル単位の完全一致ではなく**「許容される変化」を明示**する。

**緊急度：中**

---

## 6. 重複・巨大化したコード

### 🟡 問題 6.1：「なぜ選ばれたか」レポート生成が 2 箇所に重複（**緊急度：低**）

**該当箇所**

- `src/main.py:1012-1487`：`_write_latest_candidate_report()` — 480 行
- `src/triage/viral_filter.py:...`：`build_why_slot1_won_editorially()` — 一部重複

**どう直すべきか**

- 報告文字列の整形を `src/pipeline/reports.py` に集約。

**緊急度：低**

---

### 🟡 問題 6.2：`_run_summary` 構築が深くネスト（**緊急度：低**）

**該当箇所**：`src/main.py:113-336`（`_save_run_summary` 関数、約 220 行）

**問題点**

1 つの dict リテラルの中に 10 層ネストしたメタデータ。途中でキーを追加する時にどの括弧の中か追いにくい。

**どう直すべきか**

- 各セクション（ingestion / clustering / budget / model_roles / ...）を個別のビルダー関数に分割。

**緊急度：低**

---

### 🟡 問題 6.3：Pydantic モデルのスキーマが 3 派生（**緊急度：低**）

**該当箇所**：`src/shared/models.py`

`NewsEvent` / `ScoredEvent` / `DailyScheduleEntry` / `GeminiJudgeResult` などで、似たような「editorial_tags, appraisal_type, appraisal_hook, appraisal_reason」フィールドが複数モデルに散らばる。

**なぜ問題か**

スキーマ変更時に全てのモデルを同時に更新し忘れる。

**どう直すべきか**

- 共通部を `AppraisalFields`（Mixin）に抽出。

**緊急度：低**

---

## 7. ドキュメントの古さ・不足

### 🟡 問題 7.1：`README.md` が初期 PoC 時代のまま（**緊急度：中**）

**該当箇所**：`README.md`

- 「ダミーのニュース候補 JSON を読み込み、スコアリングで 1 件を選択」と書いてあるが、実態はバッチ処理・RSS・Judge・Remotion 連携まで成長している。
- `python -m src.main` の例も `--mode sample` / `--mode normalized` / `--mode render_existing` の 3 モードを網羅していない。

**どう直すべきか**

- このリファクタ完了時に全面書き直し。

**緊急度：中**

---

### 🟡 問題 7.2：コメントが「現状の設計理由」と「過去の経緯」の混在（**緊急度：低**）

**該当箇所**：多数。例 `src/shared/config.py:73-87`

```python
# 旧環境変数 GEMINI_JUDGE_MODEL は JUDGE_MODEL の bootstrap デフォルトとして残す。
# 下流コードは JUDGE_MODEL を使うこと（GEMINI_JUDGE_MODEL は JUDGE_MODEL への alias で、
# 常に同値）。これにより .env の書き換えと run_summary の表記が食い違うことがなくなる。
```

**問題点**

「過去の変更理由」が大量にコメントとして残っており、現在の設計に集中できない。

**どう直すべきか**

- 「なぜ」は `docs/` や git log に寄せ、コードコメントは「**今の動作**」だけに絞る。
- 大規模コードリーディング時のノイズが減る。

**緊急度：低**

---

## 📊 緊急度まとめ表

| 問題 | 緊急度 | 推定工数 |
|---|---|---|
| 1.1 `.gitignore` の `.venv/` バグ | **高** | 30 分 |
| 1.2 `.env` API キーローテーション | **中** | 15 分 |
| 1.3 `.DS_Store` を gitignore に追加 | 低 | 5 分 |
| 2.1 編集方針プロンプトの外出し | **高** | 2-3 日（マルチチャンネル化と一体） |
| 2.2 カテゴリベース点の YAML 化 | **高** | 1 日 |
| 2.3 キーワード辞書の YAML 化 | **高** | 1-2 日 |
| 2.4 動画サイズの YAML 化 | 中 | 半日 |
| 2.5 TTS の macOS 依存脱却 | 中 | 2-3 日（Remotion 移行と共に） |
| 2.6 フォント検索の OS 依存 | 低 | （Remotion 移行で解消） |
| 2.7 台本 4 ブロック文字数の根拠明記 | 低 | 1 時間 |
| 2.8 日英翻訳辞書の外出し | 中 | 1 日 |
| 2.9 モデル名のチャンネル別化 | 低 | 半日 |
| 3.1 YAML 読み込み失敗の握り潰し | 中 | 30 分 |
| 3.2 TTS 失敗ログレベル | 中 | 1 時間 |
| 3.3 LLM JSON パースの統一 | 中 | 1 日 |
| 3.4 ffmpeg タイムアウト変数化 | 低 | 30 分 |
| 4.1 sources_jp/en/by_locale の 3 重 | 中 | 1-2 日 |
| 4.2 新旧 heading 併存 | 低 | 1 時間 |
| 4.3 ローカル変数名の整理 | 低 | （4.4 と一緒） |
| 4.4 main.py 3303 行の分割 | 中 | 3-5 日 |
| 5.1 テストの偏り | 低 | 継続 |
| 5.2 MP4 リグレッションテスト | 中 | 1 日（Remotion 移行前に必須） |
| 6.1-6.3 重複コードの集約 | 低 | 段階的 |
| 7.1 README 書き直し | 中 | 半日 |
| 7.2 コメント整理 | 低 | 継続 |

---

## 🎯 3 チャンネル対応化の前に必ず片付けるべき項目

優先度の高い順に：

1. **問題 1.1**（.gitignore バグ） — 作業前に直す
2. **問題 2.2**（カテゴリベース点の YAML 化）
3. **問題 2.3**（キーワード辞書の YAML 化）
4. **問題 2.1**（編集方針プロンプトの外出し）
5. **問題 4.4**（main.py の分割）

これらは `docs/REFACTORING_PLAN.md` の「3 チャンネル対応」フェーズに組み込まれています。

---

*最終更新: 2026-04-23 / 作成者: Claude*
