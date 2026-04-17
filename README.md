# Hydrangea News PoC

ダミーのニュース候補JSONを読み込み、スコアリングで1件を選択し、
**動画台本・Web記事・動画制作用JSON** を生成して SQLite に保存する最小PoC。

## ディレクトリ構成

```
hydrangea-news-poc/
├── data/
│   ├── input/           # 入力ニュースJSON
│   ├── output/          # 生成成果物（gitignore推奨）
│   └── db/              # SQLiteデータベース
├── src/
│   ├── shared/          # 設定・ロガー・Pydanticモデル
│   ├── ingestion/       # JSONローダー
│   ├── triage/          # スコアリング & 選択エンジン
│   ├── generation/      # 台本・記事・動画ペイロード生成
│   ├── storage/         # SQLite保存
│   └── main.py          # エントリポイント
└── tests/               # pytest テスト
```

## セットアップ

```bash
# Python 3.11 推奨
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# 環境変数（任意）
cp .env.example .env
```

## 実行

```bash
# プロジェクトルートから実行
python -m src.main
```

デフォルトでは `data/input/sample_events.json` を読み込み、
`data/output/` に以下を出力します。

| ファイル | 内容 |
|---|---|
| `{event_id}_script.json` | 動画台本 |
| `{event_id}_article.md` | Web記事 (Markdown) |
| `{event_id}_video_payload.json` | 動画制作用JSON |
| `triage_scores.json` | スコアリング結果 |

SQLiteは `data/db/hydrangea.db` に保存されます。

### オプション

```bash
python -m src.main \
  --input  data/input/sample_events.json \
  --output data/output \
  --db     data/db/hydrangea.db
```

## テスト

```bash
pytest tests/ -v
```

## 処理フロー

```
sample_events.json
      │
      ▼
[ingestion] load_events()
      │
      ▼
[triage] compute_score() → pick_top()   ← ルールベース（将来LLM化）
      │
      ├──▶ [generation] write_script()        → {id}_script.json
      ├──▶ [generation] write_article()       → {id}_article.md
      └──▶ [generation] write_video_payload() → {id}_video_payload.json
                │
                ▼
          [storage] save_job()  → hydrangea.db (SQLite)
```

## 将来の拡張ポイント

- `src/triage/scoring.py` のルールベーススコアリングを LLM 呼び出しに置き換え
- `src/generation/` の各 writer を実際のプロンプトエンジニアリングで実装
- `src/ingestion/loader.py` でRSSフィードや外部APIからの取り込みに対応
