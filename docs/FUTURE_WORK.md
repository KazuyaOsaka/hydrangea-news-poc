# Hydrangea — 将来対応リスト (FUTURE_WORK)

最終更新: 2026-04-28 (F-3)

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

- **EditorialMissionFilter Step1 prescore の軸スコアゼロ問題** (F-1.5 試運転で発覚)
  - 背景: F-1.5 試運転で発覚。軍事費・ゼレンスキー等の地政学記事で `editorial:geopolitics_depth_score` / `editorial:breaking_shock_score` / `editorial:mass_appeal_score` が 0.0 になっていた。本来高得点になるはずの記事が低 prescore で却下される/低位置に置かれる懸念
  - 対応案: `src/triage/scoring.py` の `compute_score_full()` を読み、各 axis 計算ロジックを確認。修正には scoring.py を触る必要があるため、触っちゃダメリスト見直しと一緒に対処
  - 検討時期: F-1.5 完了後の次のバッチ
  - 関連ファイル: src/triage/scoring.py（読み取り）, src/triage/editorial_mission_filter.py

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

- **FUTURE_WORK.md 月次レビュー** (FW-1 で導入)
  - 背景: 形骸化防止のため、月初または「気のいいタイミング」で全項目を見直す
  - 対応案: 緊急度の再評価、放置項目（高で1ヶ月以上未対応）の対応開始判断、完了済みの整理、新規バッチへの組み込み判断
  - 検討時期: 毎月1日 + 以下のイベントトリガー時
    - 新しい Phase の開始前
    - 主要バッチ完了直後
    - カズヤが「次何やる？」と問うたタイミング
    - 1週間以上 FUTURE_WORK.md が参照されていないと気づいた時
  - 関連ファイル: docs/FUTURE_WORK.md, CLAUDE.md
  - 補足: このレビュー自体も FUTURE_WORK.md の項目として登録されている（自己参照型管理）

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

- **Analysis Layer の hidden_stakes axis バグ** (F-3 / 2026-04-28 完了)
  - 発生バッチ: F-1.5 試運転で発覚 → F-3 で対応完了
  - 対応内容: `src/analysis/perspective_selector.py::select_perspective()` を 3 段階フォールバックに強化。LLM が Top3 外の axis (`hidden_stakes` 等) を選んだ場合や、`fallback_axis_if_failed` も Top3 にない場合でも、Step 2 で Top3 内の最高スコア候補を強制採用する。candidates が 1 件以上あれば必ず `PerspectiveCandidate` を返すため、Slot-2 / Slot-3 で `analysis_result=None` となり動画化失敗していた問題を解消。
  - 関連ドキュメント: `docs/EDITORIAL_MISSION_FILTER_DESIGN.md` の F-3 セクション
  - 関連ファイル: `src/analysis/perspective_selector.py`, `tests/test_perspective_selector.py`, `tests/test_analysis_engine.py`
