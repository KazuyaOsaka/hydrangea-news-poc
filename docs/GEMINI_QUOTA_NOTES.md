# Gemini API 無料枠ノート

最終更新: 2026-04-26

> 試運転中に何度も RPM 超過 (429 RESOURCE_EXHAUSTED) を踏んで日次クォータを溶かした
> ため、その経緯と対策をここに集約する。今後 Gemini モデルを差し替えるとき、
> 並行呼び出しを増やすとき、課金プランへの移行を検討するときの一次情報として使う。

---

## 1. 各モデルの無料枠（2026-04 時点）

| モデル                          | RPM | RPD | 用途（このリポジトリ）                          |
|--------------------------------|-----|-----|-----------------------------------------------|
| `gemini-3.1-flash-lite-preview` | 15  | 500 | TIER1: Quality ルートの第一候補                 |
| `gemini-2.5-flash-lite`         | 10  | 20  | TIER2 / Lightweight ルート専用 (高スループット) |
| `gemini-3-flash-preview`        | 5   | 20  | TIER3: Quality ルートのフォールバック           |
| `gemini-2.5-flash`              | 5   | 20  | TIER4: Quality ルート最終フォールバック         |

- RPM = Requests Per Minute（分あたりリクエスト数）
- RPD = Requests Per Day（日あたりリクエスト数）
- **重要**: Gemini は **失敗した 429 リクエストもクォータカウントに計上する**ため、
  429 を踏んだ後に同一モデルへ即リトライすると残量を更に溶かすだけになる。

---

## 2. 経緯（2026-04 時点での発生事象と対策）

### 試運転で判明した問題

PoC の試運転を 1 日に何度か走らせていたところ、以下が連鎖して RPM/RPD クォータが
あっという間に枯渇するようになった:

1. **TIER1 (gemini-3.1-flash-lite-preview, RPM=15) が並行呼び出しでバースト**
   - GarbageFilter / Event Builder / 分析レイヤー / Script Writer が同じ実行内で
     順次呼び出される。Per-tier の最低間隔が無かったため、呼び出しが集中して
     1 分で 15 件を超え 429 を踏むケースが頻発。

2. **同一モデルへのリトライがクォータを更に消費**
   - 旧実装は 429 を「一時エラー」扱いして `_MAX_ATTEMPTS_PER_TIER` (=3) 回まで
     リトライしていた。Gemini 仕様では 429 もクォータ消費に計上されるため、
     1 回の 429 が 3 回のクォータ消費になっていた。

3. **lightweight ルートが Tier 並び替えで RPM=5 のモデルに乗ってしまった**
   - Tier 並び替え（RPM 上限が高い順に降格）で TIER4 が `gemini-2.5-flash`
     (RPM=5) に変わった結果、`_make_lightweight_client` が「TIER4 固定」と
     書かれていたために高スループット工程まで RPM=5 で動かしていた。

### 対策の流れ

| バッチ   | コミット                                | 対策内容                                                      |
|---------|----------------------------------------|--------------------------------------------------------------|
| C-1     | `4b318c7 fix: configure per-tier ...` | Tier 別の最低呼び出し間隔（GEMINI_CALL_INTERVAL_SEC_TIER{1..4}）を導入 |
| C-2     | `fd1e088 fix: skip same-model retries` | 429 検出時は同一モデルへのリトライを廃止し即座に次の Tier へ降格 |
| **C-3** | 本コミット                              | 動的レートリミッタ + lightweight client 修正（後述）              |

---

## 3. 実装済みの対策

### バッチ C-1: Tier 別呼び出し間隔の設定

`src/shared/config.py` に `GEMINI_CALL_INTERVAL_SEC_TIER{1..4}` を追加し、
`TieredGeminiClient._throttle()` が**モデル別に**最終呼び出し時刻を保持して、
各モデルの RPM 上限から逆算した最低間隔（安全率 70%）を強制する。

| モデル                          | 最低間隔 |
|--------------------------------|---------|
| `gemini-3.1-flash-lite-preview` | 5.7s    |
| `gemini-2.5-flash-lite`         | 8.6s    |
| `gemini-3-flash-preview`        | 17.2s   |
| `gemini-2.5-flash`              | 17.2s   |

→ 単一スレッドが連続呼び出ししても RPM 上限に当たらない最低保証。

### バッチ C-2: 429 即フォールバック

`TieredGeminiClient.generate()` が 429 / RESOURCE_EXHAUSTED を検出した場合、
同一モデルへのリトライをスキップして即座に次の Tier へ進む。
503 / UNAVAILABLE 等の一時エラーは従来通り指数バックオフで再試行する。

→ クォータ消費の二重計上を回避し、無料枠の延命に直結。

### バッチ C-3: 動的レートリミッタ + lightweight client 修正

#### 3-1. lightweight client の切り出し

`GEMINI_LIGHTWEIGHT_MODEL` 環境変数を追加（既定値 `gemini-2.5-flash-lite`, RPM=10）。
`_make_lightweight_client()` はこの変数を参照するように変更し、Tier 並び替えに
左右されないようにした。GarbageFilter / Event Builder のような高スループット工程
でも RPM=10 のモデルに固定される。

#### 3-2. 動的レートリミッタ

`TieredGeminiClient._wait_for_rpm_slot()` を新設。直近 60 秒のモデル別呼び出し
履歴を保持し、`RPM 上限 × 0.7` を超えそうな場合に sleep する。

```python
GEMINI_RPM_LIMIT_BY_MODEL = {
    "gemini-3.1-flash-lite-preview": 15,
    "gemini-2.5-flash-lite": 10,
    "gemini-3-flash-preview": 5,
    "gemini-2.5-flash": 5,
}
```

`generate()` の中で **動的レートリミッタ → 静的最低間隔 (`_throttle`)** の順に呼ぶ
二段構え:

- 静的最低間隔だけでは、複数経路から並行で短時間に呼ばれた場合のバーストを
  抑止できない。
- 動的レートリミッタは sliding-window 方式で過去 60 秒の実績を見るため、
  並行呼び出しのバーストにも自動で対応する。

→ 並行処理時の RPM 超過を防ぐ最終防衛線。

---

## 4. 推奨運用

### 試運転

- **1 日 1〜2 回まで**を目安にする。
  - 多くのモデルが RPD=20 しかないため、1 日に 4 回以上回すと最終フォールバック
    まで詰まり始める。
- 試運転前に `pytest tests/` で全テスト通過を確認する（実 LLM は呼ばない）。
- 試運転時は `LOG_LEVEL=INFO` で `[TieredGemini] RPM throttle:` のログ件数を
  チェックすること。多発するようなら GEMINI_CALL_INTERVAL_SEC_TIER{n} を更に
  保守側に倒す。

### 課金プラン移行の判断軸

以下のいずれかが恒常的に発生したら課金プラン移行を検討する:

- 1 回の試運転で `RPM throttle: ... → wait` ログが 10 件以上出る
- 1 日のうちに RPD クォータを使い切って実行が打ち切られる
- 3 チャンネル並行運用 (Phase 4) を始める前

課金プラン移行は **Phase 4 (3 チャンネル並行運用) を本格起動するタイミング**を
基準とし、それまでは無料枠 + 本書の対策で運用する。

### 新規モデル追加時の手順

1. `.env` / `.env.example` に新しいモデル名を追加
2. `src/shared/config.py` の `GEMINI_RPM_LIMIT_BY_MODEL` に RPM 上限を追加
3. `src/shared/config.py` の `GEMINI_INTERVAL_SEC_BY_MODEL` に最低間隔を追加
4. 本ファイル（`docs/GEMINI_QUOTA_NOTES.md`）の表を更新
5. `pytest tests/` を全通過させる

これらを忘れると、新モデルが `_RPM_DEFAULT_LIMIT=5` で扱われて過剰に保守的になる
（落ちはしないが性能が出ない）。

---

## 5. 参考リンク

- Google AI for Developers — [Rate limits and quotas](https://ai.google.dev/gemini-api/docs/rate-limits)
- リポジトリ内の関連コード:
  - `src/llm/factory.py` — `TieredGeminiClient`, `_make_lightweight_client`
  - `src/shared/config.py` — `GEMINI_*` 関連定数
  - `tests/test_factory_quota_handling.py` — 429 即フォールバックの検証
  - `tests/test_rate_limiter.py` — 動的レートリミッタの検証
