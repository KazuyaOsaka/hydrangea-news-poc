# Hydrangea Discovery Audit

Generated: 2026-05-31T10:49:31.911913+00:00  |  Total candidates this batch: 247

**Dominant failure mode: `none`**

- No obvious failure mode detected — pipeline appears healthy.

## Pipeline Stats

| Metric | Value |
|--------|-------|
| JP articles loaded | 123 |
| EN articles loaded | 325 |
| Cross-lang BFS edges | 232 |
| LLM merges | 3 |
| Cross-lang clusters | 8 |
| Candidates selected | 3 |
| Candidates held-back | 0 |

## Lane A — Linked JP↔Global  (showing top 5 of 8)

> Stories with confirmed JP+global source linkage. Primary Hydrangea candidate pool.

### 1. 米大統領が覚書の修正要求か イスラエルはヒズボラへの攻撃も
- **event_id**: `cls-352d8d308324` | **bucket**: politics_economy | **score**: 100.0
- **regions**: east_asia, europe, global, global_south, japan, latin_america, middle_east, south_asia
- JP=77 EN=64 non-West=20 | cross_lang=True merge_conf=low
- JR=7.0 GA=8.0 PG=5.0 CG=3.0 BIP=5.0 **blind_spot=8.44**
- **Why interesting**: JP and global press cover this from opposing angles — strong perspective gap.
- **Why not yet**: Impact on Japan not established — quality floor requires this field.

### 2. WHO事務局長 エボラ出血熱流行確認のコンゴ民主共和国を訪問
- **event_id**: `cls-77432745c375` | **bucket**: politics_economy | **score**: 98.95
- **regions**: east_asia, europe, global, japan, latin_america
- JP=1 EN=7 non-West=3 | cross_lang=True merge_conf=low
- JR=7.0 GA=8.0 PG=5.0 CG=3.0 BIP=5.0 **blind_spot=5.44**
- **Why interesting**: JP and global press cover this from opposing angles — strong perspective gap.
- **Why not yet**: Impact on Japan not established — quality floor requires this field.

### 3. イラン戦闘終結の覚書合意は不透明 米は経済制裁
- **event_id**: `cls-a26fa8290255` | **bucket**: politics_economy | **score**: 98.6
- **regions**: east_asia, europe, global, japan
- JP=1 EN=3 non-West=1 | cross_lang=True merge_conf=low
- JR=7.0 GA=6.0 PG=5.0 CG=3.0 BIP=5.0 **blind_spot=6.79**
- **Why interesting**: JP and global press cover this from opposing angles — strong perspective gap.
- **Why not yet**: Impact on Japan not established — quality floor requires this field.

### 4. ルーマニアがロシア総領事館閉鎖、住宅への無人機衝突で大統領「どのように侵入したかは知っている」 - 読売新聞
- **event_id**: `cls-c9ebac986fad` | **bucket**: politics_economy | **score**: 98.3
- **regions**: europe, global, japan, middle_east
- JP=3 EN=4 non-West=1 | cross_lang=True merge_conf=low
- JR=7.0 GA=6.0 PG=5.0 CG=0.0 BIP=4.5 **blind_spot=4.8**
- **Why interesting**: JP and global press cover this from opposing angles — strong perspective gap.
- **Why not yet**: Impact on Japan not established — quality floor requires this field.

### 5. 大熊に世界初「人工ダイヤ半導体」量産工場 - 47NEWS
- **event_id**: `cls-656f9cc47deb` | **bucket**: general | **score**: 58.25
- **regions**: east_asia, global, japan
- JP=1 EN=2 non-West=1 | cross_lang=True merge_conf=low
- JR=5.0 GA=6.0 PG=5.0 CG=3.0 BIP=6.5 **blind_spot=4.69**
- **Why interesting**: JP and global press cover this from opposing angles — strong perspective gap.
- **Why not yet**: Ranked outside top 15 — not appraised; quality floor not yet applied.

## Lane B — Global Big, Japan Missing  (showing top 5 of 10)

> Globally significant stories Japan is under-covering. Watch for future JP angle.

### 1. NYT: Trump sent revised proposal with toughened terms back to Iran
- **event_id**: `cls-82101968fa87` | **bucket**: tech_geopolitics | **score**: 78.0
- **regions**: middle_east
- JP=0 EN=1 non-West=1 | cross_lang=False merge_conf=none
- JR=0.0 GA=8.0 PG=0.0 CG=6.0 BIP=3.0 **blind_spot=6.62**
- **Why interesting**: Major global story with near-zero Japanese press coverage — textbook blind spot.
- **Why not yet**: Impact on Japan not established — quality floor requires this field.

### 2. Middle East crisis live: Israeli army captures strategic castle in Leban
- **event_id**: `cls-5bcf77445b2b` | **bucket**: sports | **score**: 45.95
- **regions**: europe, global_south
- JP=0 EN=2 non-West=0 | cross_lang=False merge_conf=none
- JR=0.0 GA=8.0 PG=0.0 CG=6.0 BIP=3.0 **blind_spot=5.38**
- **Why interesting**: Major global story with near-zero Japanese press coverage — textbook blind spot.
- **Why not yet**: Ranked outside top 15 — not appraised; quality floor not yet applied.

### 3. Iran reasserts control over Hormuz Strait as deal with US remains elusiv
- **event_id**: `cls-462f48bfe6e7` | **bucket**: coverage_gap | **score**: 38.5
- **regions**: middle_east
- JP=0 EN=1 non-West=1 | cross_lang=False merge_conf=none
- JR=0.0 GA=4.0 PG=0.0 CG=6.0 BIP=3.0 **blind_spot=7.22**
- **Why interesting**: Major global story with near-zero Japanese press coverage — textbook blind spot.
- **Why not yet**: Ranked outside top 15 — not appraised; quality floor not yet applied.

### 4. The strait may reopen, but global confidence may not return
- **event_id**: `cls-198b3808d922` | **bucket**: coverage_gap | **score**: 37.9
- **regions**: middle_east
- JP=0 EN=1 non-West=1 | cross_lang=False merge_conf=none
- JR=0.0 GA=4.0 PG=0.0 CG=6.0 BIP=3.0 **blind_spot=7.22**
- **Why interesting**: Major global story with near-zero Japanese press coverage — textbook blind spot.
- **Why not yet**: Ranked outside top 15 — not appraised; quality floor not yet applied.

### 5. Qatar says temporary toll at Strait of Hormuz is negotiable, could help 
- **event_id**: `cls-c97daaa76f4d` | **bucket**: coverage_gap | **score**: 37.0
- **regions**: east_asia
- JP=0 EN=1 non-West=1 | cross_lang=False merge_conf=none
- JR=0.0 GA=4.0 PG=0.0 CG=6.0 BIP=3.0 **blind_spot=7.22**
- **Why interesting**: Major global story with near-zero Japanese press coverage — textbook blind spot.
- **Why not yet**: Ranked outside top 15 — not appraised; quality floor not yet applied.

## Lane C — JP Story, Missing Global Link  (showing top 5 of 10)

> Strong JP stories that likely have EN counterparts but cross-language merge failed.

### 1. 小泉防衛相“高い透明性で防衛力強化” 中国の批判念頭に反論
- **event_id**: `cls-6c58f477a32f` | **bucket**: politics_economy | **score**: 68.8
- **regions**: japan
- JP=1 EN=0 non-West=0 | cross_lang=False merge_conf=none
- JR=10.0 GA=0.0 PG=0.0 CG=0.0 BIP=1.5 **blind_spot=0.5**
- **Why interesting**: Strong JP story that likely has EN coverage but cross-language merge didn't connect them.
- **Why not yet**: Ranked outside top 15 — not appraised; quality floor not yet applied.
- **Nearest EN candidates** (potential missed partners):
  - `cls-82101968fa87` NYT: Trump sent revised proposal with toughened terms b  _fail: topic_mismatch: JP bucket=politics_economy vs EN bucket=tech_geop_
  - `cls-101f08924f2b` Kremlin-funded propaganda film shows Ukrainian children  _fail: topic_mismatch: JP bucket=politics_economy vs EN bucket=entertain_
  - `cls-eb11c907c28d` Thousands March in Lima and Other Peruvian Cities Again  _fail: topic_mismatch: JP bucket=politics_economy vs EN bucket=coverage__

### 2. 日米防衛相 同盟の抑止力と対処力強化で協力一致
- **event_id**: `cls-2996aca2c208` | **bucket**: politics_economy | **score**: 73.8
- **regions**: japan
- JP=1 EN=0 non-West=0 | cross_lang=False merge_conf=none
- JR=7.0 GA=0.0 PG=0.0 CG=0.0 BIP=1.5 **blind_spot=0.5**
- **Why interesting**: Strong JP story that likely has EN coverage but cross-language merge didn't connect them.
- **Why not yet**: No English sources — cross-language comparison unavailable.
- **Nearest EN candidates** (potential missed partners):
  - `cls-06a1e64d37fa` Japan rejects 'new militarism', accuses China of rapidl  _fail: topic_mismatch: JP bucket=politics_economy vs EN bucket=coverage__
  - `cls-cf52e291a156` Mosca, drone ucraino colpisce unità della centrale di Z  _fail: topic_mismatch: JP bucket=politics_economy vs EN bucket=coverage__
  - `cls-7a2ef22d7ef2` Jamming-resistant radio maker seeks $3bn-plus sale  _fail: topic_mismatch: JP bucket=politics_economy vs EN bucket=coverage__

### 3. ６月の食品値上げ１０７８品目、今月の１３倍に…中東情勢悪化によるコスト高背景「さらに増える可能性」 - 読売新聞
- **event_id**: `cls-b04d486dcc91` | **bucket**: general | **score**: 32.6
- **regions**: japan
- JP=1 EN=0 non-West=0 | cross_lang=False merge_conf=none
- JR=7.0 GA=0.0 PG=0.0 CG=0.0 BIP=0.0 **blind_spot=0.5**
- **Why interesting**: Strong JP story that likely has EN coverage but cross-language merge didn't connect them.
- **Why not yet**: Ranked outside top 15 — not appraised; quality floor not yet applied.
- **Nearest EN candidates** (potential missed partners):
  - `cls-4d6c0f1db66a` How Curry Shops Got Caught in Japan’s Immigration Crack  _fail: topic_mismatch: JP bucket=general vs EN bucket=coverage_gap_
  - `cls-5bcf77445b2b` Middle East crisis live: Israeli army captures strategi  _fail: topic_mismatch: JP bucket=general vs EN bucket=sports_
  - `cls-c7d507fc74e8` Israeli troops capture strategic Beaufort Castle as the  _fail: topic_mismatch: JP bucket=general vs EN bucket=coverage_gap_

### 4. 米英豪のAUKUS、第2の柱は水中ドローン装備　国防相会談で合意
- **event_id**: `cls-61662cb17001` | **bucket**: politics_economy | **score**: 68.5
- **regions**: japan
- JP=4 EN=0 non-West=0 | cross_lang=False merge_conf=none
- JR=7.0 GA=0.0 PG=0.0 CG=0.0 BIP=0.0 **blind_spot=0.5**
- **Why interesting**: Strong JP story that likely has EN coverage but cross-language merge didn't connect them.
- **Why not yet**: Ranked outside top 15 — not appraised; quality floor not yet applied.
- **Nearest EN candidates** (potential missed partners):
  - `cls-06a1e64d37fa` Japan rejects 'new militarism', accuses China of rapidl  _fail: topic_mismatch: JP bucket=politics_economy vs EN bucket=coverage__
  - `cls-cf52e291a156` Mosca, drone ucraino colpisce unità della centrale di Z  _fail: topic_mismatch: JP bucket=politics_economy vs EN bucket=coverage__
  - `cls-7a2ef22d7ef2` Jamming-resistant radio maker seeks $3bn-plus sale  _fail: topic_mismatch: JP bucket=politics_economy vs EN bucket=coverage__

### 5. ガソリン補助「月４０００億円」、与野党から引き下げ検討求める声…高市首相「価格はＧ７で最安水準」 - 読売新聞
- **event_id**: `cls-9a482db7cdc4` | **bucket**: general | **score**: 32.0
- **regions**: japan
- JP=1 EN=0 non-West=0 | cross_lang=False merge_conf=none
- JR=7.0 GA=0.0 PG=0.0 CG=0.0 BIP=0.0 **blind_spot=0.5**
- **Why interesting**: Strong JP story that likely has EN coverage but cross-language merge didn't connect them.
- **Why not yet**: Ranked outside top 15 — not appraised; quality floor not yet applied.
- **Nearest EN candidates** (potential missed partners):
  - `cls-4d6c0f1db66a` How Curry Shops Got Caught in Japan’s Immigration Crack  _fail: topic_mismatch: JP bucket=general vs EN bucket=coverage_gap_
  - `cls-5bcf77445b2b` Middle East crisis live: Israeli army captures strategi  _fail: topic_mismatch: JP bucket=general vs EN bucket=sports_
  - `cls-c7d507fc74e8` Israeli troops capture strategic Beaufort Castle as the  _fail: topic_mismatch: JP bucket=general vs EN bucket=coverage_gap_

## Bottom-Line Diagnosis

**No dominant failure** — Pipeline is producing discovery candidates normally.
