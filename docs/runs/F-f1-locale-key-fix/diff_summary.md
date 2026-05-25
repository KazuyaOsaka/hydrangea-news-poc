# F-f1-locale-key-fix — diff サマリー

CP-1 カズヤ判断 = **選択肢 1（非 japan 合算）** + テスト同時更新。機能ロジック変更なし、locale key 参照の正本化のみ。

## 改修ファイル (2 ファイル、+11 / -4 行)

### 1. `src/triage/editorial_mission_filter.py` (`_editorial_mission_prescore`, L161-167)

**Before:**
```python
    # ソース数（ブラインドスポット計算用）
    en_count = len(se.event.sources_by_locale.get("en", []))
    jp_count = len(se.event.sources_by_locale.get("jp", []))
```

**After:**
```python
    # ソース数（ブラインドスポット計算用）
    # locale key は実データ構造に合わせる: 日本は "japan"、海外は非 japan locale
    # （"global"/"middle_east"/"europe" 等）の合算。main.py の overseas_count と同一パターン。
    jp_count = len(se.event.sources_by_locale.get("japan", []))
    en_count = sum(
        len(refs)
        for loc, refs in se.event.sources_by_locale.items()
        if loc != "japan"
    )
```

- `"jp"` → `"japan"`（実データ構造の正しいキー）
- `"en"`（存在しないキー）→ 非 japan locale の合算（`main.py:941-946` の `overseas_count` パターンと完全一致）
- blindspot の `if/elif` 判定ロジック・係数・cap は **一切変更なし**

### 2. `tests/test_editorial_mission_filter.py` (`test_blindspot_intermediate_tiers`, L173-191)

- `sources_by_locale` の data キー `"en"` → `"global"`、`"jp"` → `"japan"` に整合更新
- assert（`blindspot_severity == 12.0`）・期待値ロジック・score_breakdown 設定は **完全不変**
- 不変原則 5 例外条件 4 点充足（バグ修正類追従 / 設計変更ではない / DECISION_LOG 明記 / カズヤ承認済）

## 不変原則遵守

- `src/triage/` の `editorial_mission_filter.py` **以外** 0 行変更
- `src/analysis/` / `article_writer.py` / `script_writer.py` 既存ルート / `retry.py` / `configs/` / `scripts/` / `CLAUDE.md` 0 行変更
- 不変原則 3 例外条件 5 点全充足（バグ修正・設計変更ではない・既存メソッド contract 完全維持・baseline 維持・カズヤ承認済）

## 修正の本質（クラウド初期想定の訂正後）

バグの実害は「不当に高い誤爆（false positive）」ではなく、**`jp_count`/`en_count` が両方常に 0 で blindspot の中間 elif（12.0/10.0/8.0）が dead code 化** = 「中間解像度 8〜12 点の永久喪失（false negative 方向）」。修正後は has_jp=true かつ海外多数・日本少数のイベントが 0 → 8〜12 に**上がりうる**（設計どおりの解像度復元）。第1分岐 `has_en and not has_jp → 15.0` は score_breakdown 由来で従来から正常動作（代替経路）。
