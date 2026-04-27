# Hydrangea — 将来対応リスト (FUTURE_WORK)

最終更新: 2026-04-27

このドキュメントは「今は対応せず、将来検討・対応すべき項目」を記録する。各バッチ完了時に新しい項目が追加され、対応完了したら「完了済み」セクションに移動する。

---

## 緊急度 高（次のフェーズで必ず対応）

各項目は以下の形式で記載:
- **タイトル** (発生バッチ)
  - 背景: なぜこれが必要か
  - 対応案: どう対応するか
  - 検討時期: いつ判断するか
  - 関連ファイル: 影響を受けるファイル

---

- **_MAX_ATTEMPTS_PER_TIER = 1（503 リトライ削減）** (E-1 で見送り)
  - 背景: E-1 ハイブリッド版投入時、テスト3件（test_503_retries_three_times_within_same_tier 等）が =3 前提で書かれているため変更を見送った
  - 対応案: 専用バッチで _MAX_ATTEMPTS_PER_TIER=1 に変更し、test_factory_quota_handling.py の3テストを書き換え
  - 検討時期: F-1 後の試運転で 503 待機時間が許容範囲を超えたら即対応
  - 関連ファイル: src/llm/factory.py, tests/test_factory_quota_handling.py

- **event_builder.py のガード変更** (E-1 で見送り)
  - 背景: 現状 `if garbage_filter_client is not None:` でガードしているため、API キー未設定時に静的ルールが走らない
  - 対応案: `if GARBAGE_FILTER_ENABLED:` に変更し、API キー無しでも静的ルールを動作させる
  - 検討時期: 触っちゃダメリスト見直しと同時
  - 関連ファイル: src/ingestion/event_builder.py (touch-禁止リスト掲載中)

- **触っちゃダメリスト（CLAUDE.md）の見直し** (E-1 完了後に発覚)
  - 背景: ハイブリッド版になって event_builder.py の garbage_filter 周辺は触ってOK。scoring.py も新 axis 追加が必要になる可能性
  - 対応案: 各ファイルの「なぜ触ってはいけないか」を明示し、状況依存で触ってよい範囲を定義
  - 検討時期: Phase 1.5 全完了後

---

## 緊急度 中（実運用データ収集後に判断）

---

- **EditorialMissionFilter 閾値の調整** (F-1 で暫定値設定)
  - 背景: F-1 では閾値 45.0 を暫定値として設定。実運用データが溜まったら通過率と選定品質を分析して調整
  - 対応案: 1週間以上の運用データ（通過率・選ばれた記事の質）を分析して閾値を 40〜55 の範囲で再設定
  - 検討時期: F-1 投入後 1〜2週間

- **scoring.py の新 axis 追加** (F-1 設計時に判断)
  - 背景: F-1 で political_intent / hidden_power_dynamics / economic_interests を Step1 で精密計算したいが、scoring.py が触っちゃダメリストにあるため Step2 LLM のみで判定
  - 対応案: 触っちゃダメリスト見直し後、editorial:political_intent_score 等の新 axis を追加して Step1 prescore に組み込む
  - 検討時期: 触っちゃダメリスト見直し後

- **Tier 階層の役割分け（E-3'）** (Phase 1.5 計画)
  - 背景: 軽量タスク（garbage_filter / cluster_merge 等）と重要タスク（script_writer / 分析レイヤー等）で Tier 階層を分ける。Lightweight 系統は GA 版主軸（503 回避）、Quality 系統は Preview 版主軸（性能重視）
  - 対応案: src/llm/factory.py に _make_lightweight_client / _make_quality_client を新設、role 別にルーティング
  - 検討時期: F-1 試運転後
  - 関連ファイル: src/llm/factory.py, src/shared/config.py, .env

- **LLM 結果キャッシュ（E-4）** (Phase 1.5 計画)
  - 背景: 同じ event を2回評価しないようにキャッシュ。デバッグ高速化
  - 対応案: キャッシュキー = event.id + sources_hash + prompt_template_hash
  - 検討時期: E-3' 完了後

- **judge バッチ化（E-3 元案）** (Phase 1.5 計画)
  - 背景: viral/elite/gemini judge を1回の LLM 呼び出しに統合。ただし役割分離は維持
  - 対応案: 各 judge を別プロンプトでバッチ化、統合はしない
  - 検討時期: E-4 完了後

---

## 緊急度 低（時間ある時に検討）

---

- **README 全面書き直し** (TECH_DEBT.md 7.1 由来)
  - 背景: 初期 PoC 時代のまま、現状と乖離
  - 対応案: 全フェーズ完了時に書き直し
  - 検討時期: Phase 1.5 完了後

- **触っちゃダメリストのコメント整理** (CLAUDE.md)
  - 背景: なぜ触ってはいけないかの理由が曖昧
  - 対応案: 各ファイルに「触れない理由」と「将来触れる条件」を併記
  - 検討時期: 触っちゃダメリスト見直しの一部として

- **ガベージフィルタの除外内容定期検証** (E-1 ハイブリッド版運用後の懸念)
  - 背景: 必要な記事を誤除外していないか
  - 対応案: 月1回、除外された記事タイトルをカズヤが目視確認。誤除外パターンを発見したら BLOCKED_CATEGORIES や閾値を調整
  - 検討時期: 1ヶ月運用後

---

## 完了済み（参考用）

各項目は以下の形式で記載:
- **タイトル** (完了バッチ / 完了日)
  - 何を対応したか

---

（まだ完了済み項目はありません）
