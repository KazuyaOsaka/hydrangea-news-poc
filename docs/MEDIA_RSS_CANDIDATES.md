# Hydrangea — RSS Media Candidates Verification

F-8-PRE で実施した RSS 取得検証の結果。
Phase A.5-1 で本番 `configs/sources.yaml` に追加する候補を実測する。

検証日: 2026-04-28

## 凡例

| Status | 意味 |
|---|---|
| OK | 5件以上のエントリ取得成功 → 本番投入推奨 |
| LOW_VOLUME | 1〜4件取得 → 投入可能だが要監視 |
| EMPTY | 接続成功だがエントリ0 → 要再調査 |
| FAILED | 全候補 URL で接続失敗 → 別URL要調査 or 除外 |

## Tier 1 必須追加

| Name | Status | Entries | Latest | URL |
|---|---|---|---|---|
| Yomiuri | FAILED | 0 | — | — |
| Sankei | FAILED | 0 | — | — |
| Tokyo_Shimbun | FAILED | 0 | — | — |
| Sydney_Morning_Herald | OK | 20 | Tue, 28 Ap | https://www.smh.com.au/rss/feed.xml |
| Guardian_Australia | OK | 24 | Tue, 28 Ap | https://www.theguardian.com/australia-news/rss |
| WION | FAILED | 0 | — | — |
| The_Hindustan_Times | OK | 100 | Tue, 28 Ap | https://www.hindustantimes.com/feeds/rss/world-news/rssfeed.xml |
| Middle_East_Eye | OK | 20 | Tue, 28 Ap | https://www.middleeasteye.net/rss |
| Al_Jazeera_Arabic | FAILED | 0 | — | — |
| Caixin_Global | FAILED | 0 | — | — |
| The_Initium | OK | 15 | Tue, 28 Ap | https://theinitium.com/rss/ |
| Meduza | OK | 30 | Tue, 28 Ap | https://meduza.io/rss/en/all |
| Le_Figaro | FAILED | 0 | — | — |
| Il_Sole_24_Ore | OK | 12 | Tue, 28 Ap | https://www.ilsole24ore.com/rss/mondo.xml |
| The_Atlantic | OK | 25 | 2026-04-27 | https://www.theatlantic.com/feed/all/ |
| Politico | OK | 30 | Mon, 27 Ap | https://rss.politico.com/politics-news.xml |
| Eurasianet | FAILED | 0 | — | — |

## Tier 3 警告付き

| Name | Status | Entries | Latest | Warning | URL |
|---|---|---|---|---|---|
| TeleSUR | OK | 30 | Tue, 28 Ap | ベネズエラ・キューバ系反米メディア | https://www.telesurenglish.net/rss/ |
| TRT_World | FAILED | 0 | — | トルコ国営英語放送 | — |
| Iran_International | FAILED | 0 | — | 反イラン政府メディア (亡命者系) | — |
| Saudi_Gazette | FAILED | 0 | — | サウジ国家系メディア | — |
| Mada_Masr | OK | 10 | Mon, 27 Ap | エジプト独立メディア (政府批判可能) | https://www.madamasr.com/en/feed/ |

## 推奨アクション

### F-8-1 (Phase A.5-1) で本番投入推奨 (OK)

- **Sydney_Morning_Herald** (Tier 1)
  - URL: `https://www.smh.com.au/rss/feed.xml`
  - 20 entries, latest: Tue, 28 Apr 2026 18:42:02 +1000
- **Guardian_Australia** (Tier 1)
  - URL: `https://www.theguardian.com/australia-news/rss`
  - 24 entries, latest: Tue, 28 Apr 2026 08:28:45 GMT
- **The_Hindustan_Times** (Tier 1)
  - URL: `https://www.hindustantimes.com/feeds/rss/world-news/rssfeed.xml`
  - 100 entries, latest: Tue, 28 Apr 2026 13:42:38 +0530
- **Middle_East_Eye** (Tier 1)
  - URL: `https://www.middleeasteye.net/rss`
  - 20 entries, latest: Tue, 28 Apr 2026 07:53:31 +0100
- **The_Initium** (Tier 1)
  - URL: `https://theinitium.com/rss/`
  - 15 entries, latest: Tue, 28 Apr 2026 02:50:25 GMT
- **Meduza** (Tier 1)
  - URL: `https://meduza.io/rss/en/all`
  - 30 entries, latest: Tue, 28 Apr 2026 06:51:53 +0300
- **Il_Sole_24_Ore** (Tier 1)
  - URL: `https://www.ilsole24ore.com/rss/mondo.xml`
  - 12 entries, latest: Tue, 28 Apr 2026 08:08:00 GMT
- **The_Atlantic** (Tier 1)
  - URL: `https://www.theatlantic.com/feed/all/`
  - 25 entries, latest: 2026-04-27T20:36:00-04:00
- **Politico** (Tier 1)
  - URL: `https://rss.politico.com/politics-news.xml`
  - 30 entries, latest: Mon, 27 Apr 2026 16:01:24 EST
- **TeleSUR** (Tier 3) ⚠️ ベネズエラ・キューバ系反米メディア
  - URL: `https://www.telesurenglish.net/rss/`
  - 30 entries, latest: Tue, 28 Apr 2026 07:22:29 +0000
- **Mada_Masr** (Tier 3) ⚠️ エジプト独立メディア (政府批判可能)
  - URL: `https://www.madamasr.com/en/feed/`
  - 10 entries, latest: Mon, 27 Apr 2026 18:37:06 +0000

### 要監視 (LOW_VOLUME)

なし

### 要再調査 (FAILED / EMPTY)

- **Yomiuri**: all_candidates_failed
  - 試行 URL: `https://www.yomiuri.co.jp/rss/feed/index.xml`
- **Sankei**: all_candidates_failed
  - 試行 URL: `https://www.sankei.com/rss/news.xml`
- **Tokyo_Shimbun**: all_candidates_failed
  - 試行 URL: `https://www.tokyo-np.co.jp/feed`
- **WION**: all_candidates_failed
  - 試行 URL: `https://www.wionews.com/rss`
  - 試行 URL: `https://www.wionews.com/feed`
- **Al_Jazeera_Arabic**: all_candidates_failed
  - 試行 URL: `https://www.aljazeera.net/rss/all.xml`
- **Caixin_Global**: all_candidates_failed
  - 試行 URL: `https://www.caixinglobal.com/rss/all.xml`
- **Le_Figaro**: all_candidates_failed
  - 試行 URL: `https://www.lefigaro.fr/rss/figaro_actualites.xml`
- **Eurasianet**: all_candidates_failed
  - 試行 URL: `https://eurasianet.org/rss.xml`
- **TRT_World**: all_candidates_failed
  - 試行 URL: `https://www.trtworld.com/rss`
- **Iran_International**: all_candidates_failed
  - 試行 URL: `https://www.iranintl.com/en/rss.xml`
- **Saudi_Gazette**: all_candidates_failed
  - 試行 URL: `https://saudigazette.com.sa/rssfeed/0`

## 注目媒体の状況

Hydrangea のコンセプト深化に重要な媒体:

- ✅ **The_Initium**: OK (15 entries)
- ✅ **Mada_Masr**: OK (10 entries)
- ❌ **WION**: FAILED (0 entries)
- ✅ **Meduza**: OK (30 entries)
- ✅ **Middle_East_Eye**: OK (20 entries)
- ✅ **TeleSUR**: OK (30 entries)
- ❌ **Caixin_Global**: FAILED (0 entries)

## 次のアクション

1. OK 媒体は F-8-1 で `configs/sources.yaml` に追加
2. LOW_VOLUME 媒体は監視しつつ追加
3. FAILED 媒体は別 URL を再調査するか除外
4. configs/source_profiles.yaml で Tier / 警告フラグを定義

---
*Generated by `scripts/verify_rss_candidates.py` at 2026-04-28 17:50:15*