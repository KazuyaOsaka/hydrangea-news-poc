# manual_poc — 第一作 (golden master) の道具一式

F-first-work-golden-master (1-S / 2026-06-11) で新設。
**運用規約の正本は `docs/golden_master_spec.md`** (隔離原則 / original 凍結 /
編集→再検証ループ / 手動 PoC チェックリスト)。

| ファイル | 役割 |
|---|---|
| `generate_golden_master.py` | 候補A の golden master 再生成ハーネス (新ルート + brief 注入) |
| `editorial_brief_candidate_a.md` | 候補A 固有 editorial brief (script プロンプトにのみ注入) |
| `tts_to_captions.py` | ElevenLabs with-timestamps 応答 → Remotion 字幕 JSON 変換 |
| `remotion/` | 第一作 Remotion テンプレート (独立 npm プロジェクト) |

Remotion ダミーレンダ:

```bash
cd manual_poc/remotion
python3 scripts/make_dummy_assets.py
npm install
npx remotion render FirstWork out/first_work_dummy.mp4
```
