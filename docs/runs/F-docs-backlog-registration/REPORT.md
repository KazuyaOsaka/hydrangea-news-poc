# F-docs-backlog-registration 完了レポート

docs-only バッチ (ゲート完了後 28 つ目)。チャット合意 3 件の FUTURE_WORK 登録漏れ回収 +
DECISION_LOG のコミット未記載 placeholder 解消。コード・テスト・configs 0 行変更。

## 実装ファイル一覧

`git status --short` の写し (全変更が docs/ 配下のみであることを確認済):

```
 M docs/CURRENT_STATE.md
 M docs/DECISION_LOG.md
 M docs/DISCUSSION_NOTES.md
 M docs/FUTURE_WORK.md
```

- 新規作成:
  - `docs/runs/F-docs-backlog-registration/REPORT.md` (本ファイル)
- 変更:
  - `docs/FUTURE_WORK.md` (3 エントリ追加 + ヘッダ更新)
  - `docs/DECISION_LOG.md` (placeholder 17 箇所埋め + 本バッチエントリ追加)
  - `docs/DISCUSSION_NOTES.md` (4-A 新規 2 件 + ヘッダ更新)
  - `docs/CURRENT_STATE.md` (全置換更新)

## テスト結果

- pytest tests/: **1581 passed**, 0 failed (実測 283.87s、変更前後でコード 0 行変更のため
  baseline 自動維持だが念のため実測)
- 既存テスト影響: なし
- 新規テスト追加: 0 個 (docs-only)

## スコープ A: FUTURE_WORK.md への登録 3 件 (登録位置)

いずれも「緊急度 低（時間ある時に検討）」セクションの先頭に既存フォーマット
(背景 / 対応案 / 検討時期 / 想定工数 / 関連ファイル / 関連) で追加:

| エントリ | 位置 (L) | 補足 |
|---|---|---|
| F-docs-architecture-refresh | L707 | BATCH_PROTOCOL 老朽化 (baseline 1315 化石化 + PK 運用ルール見直し) をスコープに含む |
| F-tech-debt-audit-pre-3c | L722 | 読み取り専用棚卸し、dynamic workflow 試用候補 |
| F-claude-code-auto-progression-principle | L733 | **推定定義・起案前カズヤ意図確認必須** を明記 |

## スコープ B: DECISION_LOG placeholder 解消 — ★ 起案前提の重大訂正

**起案前提「3 箇所残存」に対し、着手時 grep で 17 箇所の残存を実測** (クラウド誤り 10 作法 =
CP-1 訂正権限で起案者前提を訂正)。完了条件が「`grep "push 後追記"` = 0 件」と定義されていた
ため、全 17 箇所を git log / git show --stat 実測ハッシュで解消した。

### 全 17 箇所の対応表 (エントリ → feature コミット / merge コミット)

| # | DECISION_LOG エントリ | feature | merge | 備考 |
|---|---|---|---|---|
| 1 | F-verify-jp-coverage-golden (2026-05-03) | `069c318` | `20da7c0` | ★ golden-fix と合算 1 コミット (コミットメッセージに combined 明記) |
| 2 | F-verify-jp-coverage-golden-fix (2026-05-04) | `069c318` | `20da7c0` | 同上 (合算) |
| 3 | F-verify-jp-coverage-measure (1-D / 2026-05-05) | `d23908e` | `b5d571d` | |
| 4 | F-jp-coverage-improve (1-D' / 2026-05-07) | `3c8d470` | `fd76660` | ★ 後続 `27be010` は同一メッセージだが内容は post-fix 成果物 (注記済) |
| 5 | F-trial-run-post-fix (1-D''' / 2026-05-07) | `27be010` | `2925fb8` | ★ コミットメッセージは F-jp-coverage-improve 文面の流用。内容 = docs/runs/F-trial-run-post-fix/ 一式 + scripts/replay_jp_coverage.py を git show --stat で確認 |
| 6 | F-particular-angle-design (2026-05-07) | `737d85c` | `edca8e6` | |
| 7 | F-particular-angle-redesign (2026-05-08) | `e789b2f` | `6b9a1fb` | |
| 8 | F-particular-angle-redesign-extension (2026-05-08) | `6a8efc4` | `2c9ee96` | |
| 9 | F-extension-followup (2026-05-08) | `038c298` | `1311cd0` | |
| 10 | F-task-e-finalize (2026-05-08) | `bbc00db` | `e1ad637` | |
| 11 | F-jp-coverage-tune (1-G / 2026-05-09) | `beb4aa7` | `82ce0d0` | |
| 12 | F-jp-coverage-tune-followup (2026-05-09) | `84a678e` | `4062639` | |
| 13 | F-trial-run-post-tune (2026-05-11) | `b81376f` | `eb0dd5e` | |
| 14 | F-wl-hit-quality-audit (2026-05-14) | `12e92c1` | `915ace3` | |
| 15 | F-jp-coverage-llm-judgement-extraction (2026-05-16) | `3d90f34` | `ba51e5f` | WIP コミット `e97eea7` (Task C-D) / `f239e13` (Task E 退行検出) も併記 (起案指示どおり feature 側確認済) |
| 16 | F-particular-angle-metadata-production-wire (X1 / 2026-05-31) | `8089012` | `c6e00c2` | 起案指定 2 件目 |
| 17 | F-first-work-golden-master (1-S / 2026-06-11) | `6230649` | `eadb517` | 起案指定 1 件目 (起案時の `6230649` / merge `eadb517` と一致確認) |

- 起案指定 3 件 (1-S / X1 / llm-judgement-extraction) は #17 / #16 / #15。残り 14 箇所が
  grep で追加発見された埋め漏れ。
- 検証: `grep -n "push 後追記" docs/DECISION_LOG.md` = **0 件** (完了条件達成)。
- 全置換は Python スクリプトで「対象行が placeholder 文字列と完全一致する場合のみ置換」の
  ガード付きで実施 (誤置換ゼロ)。

## 自分で判断した内容

- **判断 1 (スコープ拡大)**: 起案前提「placeholder 3 箇所」に対し grep 実測 17 箇所。完了条件が
  「grep = 0 件」のため、CP-1 訂正権限の範囲で全 17 箇所を埋める方針に拡大 (docs-only・全ハッシュ
  実測でリスクなし。3 箇所だけ埋めると完了条件を満たせない)。
- **判断 2 (誤帰属の罠の注記)**: `27be010` はコミットメッセージが F-jp-coverage-improve 文面の
  流用だが、git show --stat で内容が F-trial-run-post-fix 成果物であることを確認。メッセージだけで
  ハッシュを拾うと誤帰属するため、improve / post-fix 両エントリに相互注記を追加。
- **判断 3 (本バッチエントリのコミット欄)**: 完了条件 (grep 0 件) を恒久維持するため、本バッチの
  DECISION_LOG エントリでは仮置き文字列を使わず「ブランチ名参照」とした。placeholder 慣行が
  約 5 週間 17 箇所放置で機能していないことが確定したため、恒久ルール化は F-docs-architecture-refresh
  (BATCH_PROTOCOL 老朽化解消) のスコープに含めた。
- **判断 4 (登録位置)**: 3 エントリとも ★低 のため「緊急度 低」セクション先頭に追加 (新しい起案が
  上に来る既存の並び順に整合)。
- **判断 5 (CURRENT_STATE の HEAD)**: 起案文書の「1-S は feature ブランチ・承認待ち」に対し、
  実測で main HEAD = `eadb517` (1-S マージ済) を確認 → CURRENT_STATE に実測値を反映。

## 不変原則違反 / 触ってはいけないファイルへの変更要望

- なし (docs/ 配下のみ。不変原則 1-5 + 第一作隔離 (6) 自明に維持)

## BATCH_PROTOCOL Task 1-5 実施結果

- **Task 1 (DECISION_LOG)**: 本バッチエントリを末尾追加 (L6421〜)。チャット合意 3 件の登録漏れ
  回収 + placeholder 起案前提 3 → 実測 17 の訂正と全件解消 + 副次発見 2 件 (合算コミット /
  メッセージ流用) + auto-progression は推定定義・カズヤ確認待ちと明記。
- **Task 2 (FUTURE_WORK)**:
  - 完了済みに移動した項目: なし (本バッチは登録のみ)
  - 緊急度 高に追加した項目: なし
  - 緊急度 中に追加した項目: なし
  - 緊急度 低に追加した項目: F-docs-architecture-refresh / F-tech-debt-audit-pre-3c /
    F-claude-code-auto-progression-principle (3 件)
  - 冒頭「最終更新」ヘッダを本バッチで更新
- **Task 3 (完了レポート)**: 本ファイル
- **Task 4 (DISCUSSION_NOTES)**: 4-A 新規 2 件を未分類 (Active) 先頭に追加 = ①「auto-progression
  原則の推定定義 (カズヤ確認待ち — 確認まで起案不可)」②「チャット側クラウドの起案セッションは
  必ずプロジェクト内で開始する (PK 接続自己点検込み。三重安全構造で実害ゼロ監査済 = 不変原則違反 0 /
  ADR 改訂は正規手続き / 未訂正の誤前提 0)」+ ヘッダ更新。4-B 再評価 = 既存エントリ全件継続
  (本バッチは登録・回収のみで既存議論の状況変化なし、昇格・アーカイブ対象なし)。
- **Task 5 (CURRENT_STATE)**: 全置換更新。ゲート完了後 28 つ目のバッチとして反映 (ヘッダ /
  §1 リポジトリ状態 = main HEAD `eadb517` 実測 + 直近 5 件ログ + baseline 1581 / §2 ロードマップに
  本バッチ行追加 / §3 試運転なし注記 / §7 CP-1 適用例追記 / §8 導線 / footer)。フェーズは引き続き
  「手動 PoC」。

## 次バッチへの引継ぎ事項

- **F-claude-code-auto-progression-principle は起案前にカズヤの意図確認が必須** (推定定義のまま
  正典化しない。DISCUSSION_NOTES「auto-progression 原則の推定定義」参照)。
- placeholder 慣行の恒久ルール化 (仮置き文字列廃止 → ブランチ名参照 + 次バッチ遡及追記) は
  F-docs-architecture-refresh (BATCH_PROTOCOL 老朽化解消) のスコープ。
- 本バッチの merge 後、DECISION_LOG 本バッチエントリのコミット欄はブランチ名参照のまま
  (次の docs 更新バッチで実ハッシュに遡及追記してもよいが、必須ではない)。

## 環境構築・依存追加

- requirements.txt 追加: なし
- 環境変数追加: なし

## Project Knowledge 最新化 reminder

docs/ 正本 4 ファイル (CURRENT_STATE / DECISION_LOG / FUTURE_WORK / DISCUSSION_NOTES) が
更新されたため、新チャット移行前に Project Knowledge の再アップロードを推奨
(BATCH_PROTOCOL「Project Knowledge 最新化運用ルール」。★ 本バッチで記録した
「起案セッションは必ずプロジェクト内で開始 + PK 接続自己点検」運用の実践第 1 回となる)。
