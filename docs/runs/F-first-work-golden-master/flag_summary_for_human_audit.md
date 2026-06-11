# 第一作 golden master — flag サマリ (カズヤ監査の入口)

F-first-work-golden-master (2026-06-11)。validation run = 2 ガード 3 ランナー
(coverage_claim_guard / Guardian 第1層 / Guardian 第2層 corroboration ×3 run)。
**全て flag のみ。公開判断はカズヤ。** 編集→再検証ループの手順は
`docs/golden_master_spec.md` §3。

## 手修正対象 (優先順)

| # | 対象 | 内容 | 検出元 | 対処案 |
|---|---|---|---|---|
| 1 | title (platform_title) | 「日本では報道されない9,600 Detaineesの視点」= stream_2 に対する silence 絶対表現 (title_generator ハードコード由来、想定通り) | coverage guard run2 = contradiction / Guardian c1 = uncorroborated | 手修正 (例: 「事件は報じられた。触れられない構造がある」方向)。根本は F-title-generator-stream-aware-fix ★中 |
| 2 | script twist (c5) | **告発主体の帰属エラー**: 「ベネズエラ政府系のTeleSURは…疑惑を告発」— 告発主体は囚人擁護センターで、TeleSUR は報じたメディア | Guardian 第1層 contradicted | 「TeleSUR (ベネズエラ政府系) が報じたところによると、◯◯センターが…告発」へ手修正。修正後 1-T.1→1-T.2 再実行 |
| 3 | article (c10/c13) | 「日本国内では…詳細な報道が極めて少ない」「ほとんど見られない」— 独立日本語ソース (クーリエ・ジャポン / AFPBB / アムネスティ日本 / NewSphere 等) が拘束者処遇の詳細報道実例で**明示的に矛盾** | Guardian 第2層 contradicted (c10 = run1+run3 で一致 = 堅い) | 「角度限定」の表現に弱める (ICRC 監視操作疑惑という特定角度に限定)。★ article は brief 注入不可 (不変原則 1) の構造的弱点が実証された形 |
| 4 | script punchline | 尻切れ「…生活実感として突きつける、あの」(loop-2、X1 と同型 = **標本 2 例目**) | 目視 (char validation は通過) | 手修正で文を閉じる。F-script-punchline-tail-cut-investigate ★中 の標本 |
| 5 | article (c11/c12) | c11「多国籍メディア」記述はソース外 / c12 告発主体名の独立裏取りなし (外部は PPS = パレスチナ人捕虜協会に帰属、「囚人擁護センター」の独立支持なし) | 第1層 not_in_source / 第2層 uncorroborated | 出典確認のうえ表現調整 (主体名は TeleSUR 原文準拠で痩せさせる) |

## 裏取り成功 (公開可否バー通過 = supported × corroborated)

- c2/c3/c4 (9,600人収監・虐待告発・ICRC 訪問操作疑惑の基本事実) — 少なくとも 1 run で corroborated
- **c6 (日本郵船 回避運航 + 伊藤忠 提携解消)** — run3 で corroborated
  (toyokeizai.net / arabnews.jp / trafficnews.jp 等)。analysis レイヤー由来の企業主張が
  実在事実と確認された
- c7 (9,600人拘束 + 赤十字査察妨害の告発) — run3 で corroborated
- c14 — run1 で corroborated

## 未解決 (503 波で 3 run とも unverified)

- **c8 / c9** (article の ICRC 訪問制限・9,600人拘束の各記述) — 検証未完 ≠ 虚偽。
  corroboration ランナー再実行で回収する (`golden_master_spec.md` §3 手順 (3))

## run 間分散の記録 (F-grounding-determinism-audit への追加標本)

- coverage guard: run1 consistent ⇄ run2 contradiction (**flag 有無が反転**、ガード文脈で初観測)
- corroboration: c6/c7 (run3 のみ回収) / c3/c13/c14 (run3 で 503 落ち) / c12 (corroborated ⇄
  uncorroborated = 判定内容の揺れ、503 ではなく証拠セット差)
- canonical = run1 (単一 run で最も完全)、run2 (503 波) / run3 は監査証跡として並置
