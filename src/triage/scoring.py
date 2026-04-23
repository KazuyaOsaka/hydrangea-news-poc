from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from src.shared.models import NewsEvent

# ── カテゴリ基礎スコア ──────────────────────────────────────────────────────────
CATEGORY_BASE: dict[str, float] = {
    "economy": 85.0,
    "politics": 80.0,
    "technology": 75.0,
    "startup": 70.0,
    "sports": 60.0,
    "entertainment": 55.0,
}

# ── 高インパクトキーワード（タイトル・要約） ─────────────────────────────────────
HIGH_IMPACT_KEYWORDS: list[tuple[str, float]] = [
    ("利上げ", 10.0),
    ("利下げ", 10.0),
    ("解散", 10.0),
    ("増税", 8.0),
    ("減税", 8.0),
    ("資金調達", 6.0),
    ("EV", 5.0),
    ("AI", 5.0),
    ("少子化", 7.0),
    ("サヨナラ", 4.0),
]

# ── クロスランゲージボーナス（証拠強度段階） ────────────────────────────────────
_CROSS_LANG_BONUS_FULL    = 5.0   # gap_reasoning + structured sources
_CROSS_LANG_BONUS_GAP_ONLY = 3.0  # gap_reasoning のみ
_CROSS_LANG_BONUS_SRC_ONLY = 2.0  # structured sources のみ
_CROSS_LANG_BONUS_CLUSTER  = 1.5  # BFS cluster mode (ソース・gap とも未設定)

# ── 品質ペナルティ ────────────────────────────────────────────────────────────
_SOURCE_FALLBACK_PENALTY      = -10.0
_JAPAN_IMPACT_ABSENT_PENALTY  = -8.0
_CONTEXT_DEPTH_ABSENT_PENALTY = -5.0
_PERSPECTIVE_WEAK_PENALTY     = -5.0

# ── 編集重み調整（perspective_gap 優先） ──────────────────────────────────────
_ADJ_PG_WEIGHT = 0.9   # perspective_gap 比例ボーナス係数（旧 0.8）
_ADJ_PG_CAP    = 8.0   # 上限（旧 7.0）
_ADJ_CG_WEIGHT = 0.15  # coverage_gap 比例ボーナス係数（旧 0.25）
_ADJ_CG_CAP    = 1.5   # 上限（旧 2.0）

# ── 犯罪・事故・地域事件ペナルティ ───────────────────────────────────────────
_CRIME_LOCAL_PENALTY = -20.0  # 戦略的文脈なしの犯罪/地域事件

# ── 地域スコアリング定数（multi-region pilot） ────────────────────────────────
# global_south を pilot/non-western 両方に含める。TimesOfIndia / News24 /
# FolhaDeSPaulo / BuenosAiresTimes などのグローバルサウス媒体が
# multi_region_score / regional_contrast_score の加点対象になる。
_PILOT_REGIONS = frozenset({"middle_east", "europe", "east_asia", "global_south"})
_NON_WESTERN_REGIONS = frozenset({"middle_east", "east_asia", "global_south"})

# bridge source 名: sources.yaml の bridge_source:true から動的ロード。
# 読み込み失敗時は旧ハードコード集合にフォールバックする。
_BRIDGE_SOURCE_NAMES_FALLBACK: frozenset[str] = frozenset(
    {"al jazeera", "aljazeera", "france24", "cna"}
)


@lru_cache(maxsize=1)
def _load_bridge_source_names() -> frozenset[str]:
    """sources.yaml から bridge_source:true のソース名を小文字で取得する。

    取得失敗時（yaml 欠損・破損）はフォールバック集合を返す。呼び出しは lru_cache
    のため 1 プロセスで 1 回のみ yaml を読む。
    """
    try:
        import yaml
        cfg_path = Path(__file__).resolve().parents[2] / "configs" / "sources.yaml"
        if not cfg_path.exists():
            return _BRIDGE_SOURCE_NAMES_FALLBACK
        with open(cfg_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        names = {
            s["name"].lower()
            for s in data.get("sources", [])
            if s.get("bridge_source", False) and s.get("name")
        }
        if not names:
            return _BRIDGE_SOURCE_NAMES_FALLBACK
        return frozenset(names)
    except Exception:
        return _BRIDGE_SOURCE_NAMES_FALLBACK


# 名前の付き合わせには部分一致（substring）を維持したいので、下流は
# _load_bridge_source_names() をそのまま in チェックに使う。
_BRIDGE_SOURCE_NAMES = _load_bridge_source_names()
# 地域ラベル（日本語表示用）
_REGION_LABELS: dict[str, str] = {
    "japan": "日本", "global": "欧米英語圏",
    "middle_east": "中東", "europe": "欧州", "east_asia": "東アジア",
}

# ── 戦略×日本ボーナス ─────────────────────────────────────────────────────────
_STRATEGIC_JAPAN_BONUS  = 5.0  # (big_event/geopolitics/tech_geopolitics) × japan_relevance 高
_DUAL_HIGH_BONUS        = 4.0  # japan_relevance >= 6 AND global_attention >= 5（旧 3.0）
_JP_EN_BOTH_BONUS       = 2.0  # JP+EN 両ビューあり場合の優先ボーナス
_EN_ONLY_LOW_JR_PENALTY = -5.0  # EN-only かつ low_japan_relevance（jr<4）の追加減点

# ────────────────────────────────────────────────────────────────────────────
# Editorial Policy — キーワード定義
# ────────────────────────────────────────────────────────────────────────────

_TECH_KW = [
    "ai", "人工知能", "半導体", "chip", "semiconductor", "quantum", "量子",
    "llm", "gpu", "nvidia", "エヌビディア", "tsmc", "クラウド", "cloud computing",
    "deep learning", "generative", "生成ai",
]
_TECH_GEO_KW = [
    "覇権", "国家戦略", "安全保障", "輸出規制", "禁輸", "sanctions", "export control",
    "national security", "huawei", "ファーウェイ", "decoupling", "supply chain",
    "サプライチェーン", "tech war", "chip war", "経済安保",
]
_BIG_EVENT_KW = [
    "選挙", "election", "大統領", "president", "首相", "prime minister",
    "日銀", "fed", "boj", "central bank", "中央銀行", "gdp", "imf",
    "world bank", "g7", "g20", "summit", "サミット",
    "利上げ", "利下げ", "rate hike", "rate cut", "インフレ", "inflation",
    "増税", "減税", "budget", "予算", "政策金利", "monetary policy",
]
_GEO_CONFLICT_KW = [
    "war", "戦争", "conflict", "紛争", "sanctions", "制裁",
    "ukraine", "ウクライナ", "gaza", "ガザ", "taiwan", "台湾",
    "nuclear", "核", "missile", "ミサイル", "nato", "安保",
    "中東", "middle east", "south china sea", "南シナ海", "侵攻",
]
_SPORTS_KW = [
    "大谷", "ohtani", "mlb", "nba", "nfl", "野球", "baseball",
    "サッカー", "football", "soccer", "tennis", "テニス",
    "オリンピック", "olympic", "ワールドカップ", "world cup", "pga",
]
_ENT_KW = [
    "芸能", "celebrity", "映画", "film", "music", "音楽",
    "grammy", "oscar", "hollywood", "ドラマ", "アーティスト",
]
_ECON_CONTEXT_KW = [
    "contract", "契約", "salary", "年俸", "lawsuit", "訴訟",
    "billion", "億", "deal", "legal", "法的", "endorsement",
    "損害賠償", "settlement", "独占", "antitrust",
]
_MAJOR_EN_SOURCES = [
    "reuters", "bbc", "financial times", "bloomberg", "wsj",
    "new york times", "guardian", "ap ", "afp",
]

# ── Japan Abroad / Japanese Person Abroad ──────────────────────────────────
# 日本の政治・経済が海外でどう報じられるか
_JAPAN_POLITICS_KW = [
    "首相", "prime minister japan", "japanese prime minister", "japanese government",
    "kishida", "岸田", "ishiba", "石破", "日本政府", "日本の政府",
    "自民党", "ldp ", "日米関係", "us-japan", "japan-us", "japan's foreign policy",
    "日米首脳", "ministry of finance japan", "japan's defense", "防衛省",
]
_JAPAN_ECONOMY_KW = [
    "toyota", "トヨタ", "sony", "ソニー", "honda", "ホンダ", "nintendo", "任天堂",
    "softbank", "ソフトバンク", "panasonic", "パナソニック", "hitachi", "日立",
    "japan's economy", "japanese economy", "japan gdp", "日本経済",
    "japan trade", "japan's trade surplus", "japan's exports",
    "boj ", "bank of japan", "日銀", "jgb ", "japan's debt",
    "nikkei 225", "nikkei index", "japan's stock",
]
# 海外で報道される日本人著名人
_JAPANESE_PERSON_KW = [
    # スポーツ
    "ohtani", "大谷", "shohei", "shohei ohtani",
    "nishikori", "錦織", "naomi osaka", "大坂なおみ",
    "yuzuru hanyu", "羽生結弦", "hideki matsuyama", "松山英樹",
    "rui hachimura", "八村塁", "yoshi tsutsugo",
    # 経済・経営
    "masayoshi son", "孫正義", "hiroshi mikitani", "三木谷",
    # 著名人
    "hayao miyazaki", "宮崎駿",
]

# ── 速報性・地政学ショック ────────────────────────────────────────────────────
_BREAKING_SHOCK_KW = [
    # 停戦・軍事衝突
    "停戦", "ceasefire", "cease-fire", "停戦合意", "攻撃", "airstrike", "空爆", "侵攻", "invasion",
    "軍事作戦", "military operation",
    # 制裁・関税・貿易制限
    "制裁", "sanction", "関税", "tariff", "禁輸", "embargo", "輸出規制", "export ban",
    # 中銀・金融政策の急変
    "緊急利上げ", "emergency rate hike", "利上げ幅", "rate hike", "rate cut",
    "量的緩和", "量的引き締め", "qe ", "qt ",
    # 政変・政策転換
    "政変", "coup", "クーデター", "崩壊", "collapse", "政権崩壊", "大統領令", "executive order",
    "国家非常事態", "state of emergency", "非常事態宣言",
    # 大型デフォルト・破産
    "デフォルト", "sovereign default", "破産", "bankruptcy", "債務不履行",
    # 速報・重大発表
    "速報", "breaking:", "breaking news", "緊急声明", "緊急会合", "emergency meeting",
]

_MARKET_SHOCK_KW = [
    # 原油・エネルギー
    "原油", "crude oil", "crude ", "wti", "brent", "opec", "天然ガス", "natural gas",
    # 金・コモディティ
    "gold price", "gold ", "金価格", "金相場", "commodity",
    # 為替
    "為替急変", "ドル円", "円安", "円高", "yen plunge", "yen surge", "fx shock",
    "人民元安", "yuan", "ユーロ安",
    # 株価・指数の急変
    "日経平均", "nikkei", "s&p 500", "s&p500", "dow jones", "nasdaq",
    "暴落", "crash", "急落", "plunge", "急騰", "surge", "sell-off", "selloff",
    "market rout", "リスクオフ", "risk-off",
    # 利回り・債券
    "米国債", "treasury yield", "長期金利急騰",
]

_BREAKING_SHOCK_BONUS = 6.0  # geopolitics/big_event × breaking_shock コンボボーナス

# ── 犯罪・事故・地域事件 検出キーワード ──────────────────────────────────────
_CRIME_LOCAL_KW = [
    "逮捕", "容疑", "被疑者", "犯罪", "暴行", "性的暴行", "窃盗", "詐欺",
    "強盗", "殺人", "傷害", "不審", "捜査", "書類送検", "起訴",
    "遺体", "遺棄", "摘発",
    "arrest", "suspect", "assault", "robbery", "murder",
]
# これらが含まれる場合は戦略的文脈ありとみなしてペナルティ免除
_CRIME_STRATEGIC_OVERRIDE_KW = [
    "テロ", "terror", "組織犯罪", "organized crime", "マネーロンダリング",
    "money laundering", "サイバー犯罪", "cyber", "スパイ", "espionage",
    "情報漏洩", "data breach", "大規模", "systematic",
    "経済安保", "国家", "安全保障", "national security",
]

# ── 間接的日本インパクト ── JP記事不在でも日本への波及を示すキーワード ──────────────
# title + summary + global_view から評価する（JP記事の有無に依存しない）
_INDIRECT_JAPAN_IMPACT_KW: list[tuple[str, float]] = [
    # エネルギー安全保障（日本は資源輸入に高度依存）
    ("strait of hormuz", 5.0),
    ("hormuz strait", 5.0),
    ("hormuz", 4.5),
    ("ホルムズ海峡", 5.0),
    ("lng", 4.0),
    ("liquefied natural gas", 4.0),
    ("oil supply", 3.5),
    ("energy supply", 3.5),
    ("oil price", 3.0),
    ("crude oil", 3.0),
    ("opec", 3.5),
    ("sea lane", 3.5),
    ("shipping lane", 3.5),
    ("maritime", 3.0),
    ("logistics", 2.5),
    ("freight", 2.5),
    ("supply disruption", 3.5),
    # 半導体・サプライチェーン（日本の製造業・電機産業への直撃）
    ("tsmc", 4.0),
    ("semiconductor supply", 4.0),
    ("chip supply", 3.5),
    ("supply chain", 3.0),
    ("サプライチェーン", 3.0),
    # 為替・金融政策（円安・輸入物価への波及）
    ("usdjpy", 4.0),
    ("yen ", 3.5),
    ("円安", 4.0),
    ("円高", 4.0),
    ("boj", 3.5),
    ("bank of japan", 3.5),
    ("日銀", 3.5),
    ("inflation", 2.5),
    ("インフレ", 2.5),
    # 輸出規制・経済制裁（日本の技術輸出・貿易への影響）
    ("export control", 3.5),
    ("export ban", 3.5),
    ("輸出規制", 3.5),
    ("sanctions", 2.5),
    ("制裁", 2.5),
    ("tariff", 2.5),
    ("関税", 2.5),
    # 安全保障・シーレーン（自衛隊・同盟国への影響）
    ("strait blockade", 5.0),
    ("blockade", 4.0),
    ("sea blockade", 4.5),
    ("naval", 3.0),
    ("carrier strike", 3.5),
    ("military escalation", 3.0),
    # エネルギー輸入価格→輸入インフレ
    ("imported inflation", 3.5),
    ("energy cost", 3.0),
    ("surcharge", 2.5),
    ("fuel surcharge", 3.0),
    # 日本語固有表現
    ("エネルギー安全保障", 4.0),
    ("エネルギー価格", 3.5),
    ("原油高", 4.0),
    ("輸送費", 2.5),
]


# ────────────────────────────────────────────────────────────────────────────
# 内部ユーティリティ
# ────────────────────────────────────────────────────────────────────────────

def _score_editorial_axes(event: NewsEvent) -> dict[str, float]:
    """イベントの編集価値を 8 軸でヒューリスティック評価する（各軸 0〜10）。

    キーワードマッチは代表記事の title + summary のみに行う。
    japan_view / global_view はクラスタ内全記事の連結テキストのため、
    perspective/coverage gap の有無判定にのみ使用し、誤マッチを防ぐ。
    """
    title   = (event.title or "").lower()
    summary = (event.summary or "").lower()
    jv      = (event.japan_view or "").lower()
    gv      = (event.global_view or "").lower()
    source  = (event.source or "").lower()
    # キーワード検索は代表記事 (title + summary) に限定
    text    = f"{title} {summary}"

    has_jp   = bool(event.japan_view and event.japan_view.strip())
    has_en   = bool(event.global_view and event.global_view.strip())
    has_both = has_jp and has_en and event.japan_view.strip() != event.global_view.strip()

    # 1. Perspective Gap ─ 日英で切り口が違う
    pg = 0.0
    if has_both:
        pg += 5.0
        if event.gap_reasoning:
            pg += 4.0
        diff_kws = ["格差", "視点", "異なる", "differ", "contrast", "while", "whereas", "however"]
        if any(kw in text for kw in diff_kws):
            pg = min(pg + 1.5, 10.0)

    # 2. Coverage Gap ─ 海外では大きいが日本では弱い
    cg = 0.0
    if has_en and not has_jp:
        cg += 6.0
    elif has_both and len(event.global_view or "") > len(event.japan_view or "") * 2.5:
        cg += 3.0
    if any(kw in text for kw in ["未報道", "underreported", "overlooked"]):
        cg = min(cg + 3.0, 8.0)

    # 3. Tech Geopolitics ─ AI/半導体を国家戦略・覇権視点で
    tech_hit     = any(kw in text for kw in _TECH_KW)
    geostrat_hit = any(kw in text for kw in _TECH_GEO_KW)
    tg = 0.0
    if tech_hit:
        tg += 5.0
    if geostrat_hit:
        tg += 4.0
    if tech_hit and geostrat_hit:
        tg += 1.0
    tg = min(tg, 10.0)

    # 4. Big Event ─ 政治・経済の大型イベント
    be_hits = sum(1 for kw in _BIG_EVENT_KW if kw in text)
    be = min(be_hits * 1.5, 8.0)

    # 5. Geopolitics Depth ─ 地政学・紛争・安全保障
    gd_hits = sum(1 for kw in _GEO_CONFLICT_KW if kw in text)
    gd = min(gd_hits * 2.0, 8.0)

    # 6. Mass Appeal ─ スポーツ・エンタメ（経済・法的背景で加点）
    has_sports   = any(kw in text for kw in _SPORTS_KW)
    has_ent      = any(kw in text for kw in _ENT_KW)
    has_econ_ctx = any(kw in text for kw in _ECON_CONTEXT_KW)
    ma = 0.0
    if has_sports:
        ma += 4.0
    if has_ent:
        ma += 3.0
    if (has_sports or has_ent) and has_econ_ctx:
        ma += 3.0   # 経済・法的文脈があれば Tier 1 相当に近づける
    ma = min(ma, 8.0)

    # 7. Japan Relevance ─ 日本への関連性
    jr = 0.0
    if has_jp:
        jr += 5.0
    if any(kw in text for kw in ["日本", "japan", "japanese", "東京", "tokyo"]):
        jr = min(jr + 3.0, 8.0)
    if event.impact_on_japan:
        jr = min(jr + 2.0, 10.0)
    if any(s in source for s in ["nhk", "nikkei", "asahi", "mainichi", "yomiuri", "日経"]):
        jr = min(jr + 2.0, 10.0)

    # 8. Global Attention ─ 国際的注目度
    ga = 0.0
    if has_en:
        ga += 2.0
    for ms in _MAJOR_EN_SOURCES:
        if ms in source or ms in gv:
            ga = min(ga + 2.0, 8.0)
    if event.sources_en:
        ga = min(ga + 2.0, 8.0)
    ga = min(ga, 8.0)

    # 9. Crime / Local Incident Detection ─ 犯罪・事故・地域事件フラグ
    # tech_geopolitics / economic_impact / major_social_impact と結びつかない限りペナルティ
    crime_hits = sum(1 for kw in _CRIME_LOCAL_KW if kw in text)
    crime_strategic = any(kw in text for kw in _CRIME_STRATEGIC_OVERRIDE_KW)
    # tg>=5 なら戦略的文脈ありとみなして免除
    cli = 1.0 if (crime_hits >= 1 and not crime_strategic and tg < 5) else 0.0

    # 10(a). Japan Abroad Score ─ 日本の政治・経済・文化が海外でどう報じられるか
    jp_pol_hit  = any(kw in text for kw in _JAPAN_POLITICS_KW)
    jp_eco_hit  = any(kw in text for kw in _JAPAN_ECONOMY_KW)
    ja = 0.0
    if (jp_pol_hit or jp_eco_hit) and has_en:   # EN メディアが日本を取り上げている
        ja += 5.0
        if jp_pol_hit and jp_eco_hit:
            ja += 2.0                            # 政治・経済の両面をカバー
        if has_both:
            ja += 2.0                            # JP+EN 比較で視点差が生まれやすい
        if jr >= 5:
            ja = min(ja + 1.0, 10.0)
    ja = min(ja, 10.0)

    # 10(b). Japanese Person Abroad Score ─ 日本人著名人が海外でどう報じられるか
    jp_person_hit = any(kw in text for kw in _JAPANESE_PERSON_KW)
    jpa = 0.0
    if jp_person_hit and has_en:                 # EN メディアが日本人を取り上げている
        jpa += 6.0
        if has_both:
            jpa += 2.0
        if ga >= 4:
            jpa = min(jpa + 1.0, 10.0)
        if jr >= 4:
            jpa = min(jpa + 1.0, 10.0)
    jpa = min(jpa, 10.0)

    # 10(c). Breaking Shock Score ─ 速報性の高い地政学・マクロショック
    # title + summary にキーワードが含まれる場合のみ加点
    bs_hits  = sum(1 for kw in _BREAKING_SHOCK_KW if kw in text)
    mkt_hits = sum(1 for kw in _MARKET_SHOCK_KW  if kw in text)
    bs = min(bs_hits * 2.5, 7.5)
    if mkt_hits >= 2:
        bs = min(bs + 2.5, 9.5)           # 市場キーワード2件以上: 強いインパクト
    elif mkt_hits >= 1:
        bs = min(bs + 2.0, 9.5)           # 市場キーワード1件
    if bs_hits >= 2 and mkt_hits >= 1:
        bs = min(bs + 0.5, 10.0)          # 複合シグナルへのコンボボーナス
    bs = min(bs, 10.0)

    # 10. Background Inference Potential ─ 報道差から意味ある背景仮説を立てられる余地
    # 「記事に背景説明が書かれているか」ではなく「差分から仮説を推論できるか」を評価する
    bip = 0.0
    if has_both:
        bip += 2.0          # 両言語ビューあり → 比較素材がある
    if event.gap_reasoning:
        bip += 3.0          # 差の根拠が明示されている → 仮説の土台が整っている
    if pg >= 4:
        bip += 2.0          # 強い視点差 → 仮説を立てる余地が大きい
    elif pg >= 2:
        bip += 0.5
    if cg >= 5:
        bip += 1.5          # 海外vs日本の報道量差 → 「なぜ注目度が違うか」の仮説余地
    elif cg >= 3:
        bip += 0.5
    # 戦略的文脈 → 地政学・経済・技術覇権の仮説は意味がある
    if any(s >= 3 for s in [tg, be, gd]):
        bip += 1.5
    if event.background:
        bip += 0.5          # 既存の背景情報があり仮説を補強できる
    if event.sources_jp and event.sources_en:
        bip += 0.5          # 両ソースあり → 具体的な比較根拠がある
    bip = min(bip, 10.0)

    # ── Region-aware scores（多地域 pilot 対応） ───────────────────────────────
    regions: frozenset[str] = frozenset(event.sources_by_locale.keys()) if event.sources_by_locale else frozenset()
    has_japan_region = "japan" in regions
    pilot_in_regions = regions & _PILOT_REGIONS
    non_western_in_regions = regions & _NON_WESTERN_REGIONS
    n_regions = len(regions)

    # multi_region_score: 地域ソースの多様性
    # japan + pilot 地域の組み合わせを高く評価。EN-only 多地域寄せは抑制。
    mrs = 0.0
    if n_regions >= 2:
        mrs += 2.0
    if n_regions >= 3:
        mrs += 2.0
    if n_regions >= 4:
        mrs += 2.0
    if has_japan_region and pilot_in_regions:
        mrs += 3.0   # japan + 非西側 / 欧州 pilot region の組み合わせ
    # EN-only 多地域（global + europe のみ）は過大評価しない
    if not has_japan_region and regions <= frozenset({"global", "europe"}):
        mrs *= 0.4
    mrs = min(mrs, 8.0)

    # regional_contrast_score: JP vs 非西側 の視点コントラスト
    rcs = 0.0
    if has_japan_region and non_western_in_regions:
        rcs += 5.0
        if len(non_western_in_regions) >= 2:
            rcs += 2.0   # middle_east + east_asia 両方あり
    elif has_japan_region and "europe" in regions:
        rcs += 3.0       # JP + 欧州（西側だが視点差あり）
    rcs = min(rcs, 8.0)

    # jp_plus_nonwestern_score: JP + 非西側の具体的シグナル
    jpnw = 0.0
    if has_japan_region and non_western_in_regions:
        jpnw = min(3.0 + len(non_western_in_regions) * 2.0, 7.0)

    # 11. Indirect Japan Impact Score ─ JP記事不在でも日本への間接的波及を評価
    # title + summary + global_view から評価（JP記事の有無に依存しない）
    ijai_text = f"{title} {summary} {gv}"
    ijai_raw = sum(w for kw, w in _INDIRECT_JAPAN_IMPACT_KW if kw in ijai_text)
    ijai = min(ijai_raw, 10.0)

    # bridge_source_bonus: sources.yaml で bridge_source:true に設定された媒体の検出。
    # 比較時は両辺で空白を除去し、"Al Jazeera" / "AlJazeera" / "al jazeera" を
    # 同一に扱う（legacy pool snapshot の表記揺れに耐える）。
    def _norm(s: str) -> str:
        return s.replace(" ", "").lower()

    all_src_names_norm = frozenset(
        _norm(ref.name)
        for refs in event.sources_by_locale.values()
        for ref in refs
    ) if event.sources_by_locale else frozenset()
    bridge_names_norm = frozenset(_norm(b) for b in _BRIDGE_SOURCE_NAMES)
    bridge_count = sum(
        1 for n in all_src_names_norm
        if any(b in n for b in bridge_names_norm)
    )
    bsb = min(bridge_count * 2.0, 4.0)

    return {
        "perspective_gap_score":          pg,
        "coverage_gap_score":             cg,
        "tech_geopolitics_score":         tg,
        "big_event_score":                be,
        "geopolitics_depth_score":        gd,
        "mass_appeal_score":              ma,
        "japan_relevance_score":          jr,
        "global_attention_score":         ga,
        "crime_local_indicator":          cli,
        "background_inference_potential": bip,
        "breaking_shock_score":           bs,
        "japan_abroad_score":             ja,
        "japanese_person_abroad_score":   jpa,
        "indirect_japan_impact_score":    ijai,
        # EN-only / JP+EN 判定に使用（下流の Tier 決定・スコア調整で参照）
        "has_jp_view":  1.0 if has_jp else 0.0,
        "has_en_view":  1.0 if has_en else 0.0,
        "_has_sports":  1.0 if has_sports else 0.0,
        "_has_ent":     1.0 if has_ent else 0.0,
        # Region-aware axes（多地域 pilot）
        "multi_region_score":        mrs,
        "regional_contrast_score":   rcs,
        "jp_plus_nonwestern_score":  jpnw,
        "bridge_source_bonus":       bsb,
        # 地域フラグ（Tier 判定・タグ付けに使用）
        "_has_japan_region":    1.0 if has_japan_region else 0.0,
        "_has_pilot_region":    float(len(pilot_in_regions)),
        "_has_non_western":     float(len(non_western_in_regions)),
    }


def _compute_editorial_meta(
    axes: dict[str, float],
) -> tuple[str, list[str], str]:
    """editorial_tags・primary_tier・editorial_reason を導出する。"""
    pg  = axes["perspective_gap_score"]
    cg  = axes["coverage_gap_score"]
    tg  = axes["tech_geopolitics_score"]
    be  = axes["big_event_score"]
    gd  = axes["geopolitics_depth_score"]
    ma  = axes["mass_appeal_score"]
    jr  = axes["japan_relevance_score"]
    ga  = axes["global_attention_score"]
    bip = axes.get("background_inference_potential", 0.0)
    bs  = axes.get("breaking_shock_score", 0.0)
    ja  = axes.get("japan_abroad_score", 0.0)
    jpa = axes.get("japanese_person_abroad_score", 0.0)

    tags: list[str] = []
    reasons: list[str] = []

    # ── Breaking Shock タグ（最優先で付与） ───────────────────────────────────
    if bs >= 7:
        tags.append("breaking_shock")
        reasons.append("速報性の高い地政学・マクロショック（市場インパクトを伴う）")
    elif bs >= 4:
        tags.append("market_shock")
        reasons.append("市場・地政学ショックの兆候あり")

    # ── Japan Abroad / Japanese Person Abroad タグ ───────────────────────────
    if jpa >= 5:
        tags.append("japanese_person_abroad")
        reasons.append("日本人著名人が海外メディアで注目されている")
    if ja >= 5:
        tags.append("japan_abroad")
        reasons.append("日本の政治・経済が海外メディアでどう報じられているか")

    # ── Tier 1 タグ ─────────────────────────────────────────────────────────
    if pg >= 6:
        tags.append("perspective_gap")
        reasons.append("日英で報道の視点・切り口が大きく異なる")
    elif pg >= 4:
        tags.append("perspective_gap")
        reasons.append("日英間の視点差が確認できる")

    if cg >= 5:
        tags.append("coverage_gap")
        reasons.append("海外では注目されているが日本での報道が弱い")

    if tg >= 8:
        tags.append("tech_geopolitics")
        reasons.append("AI・半導体など技術覇権・国家安全保障の観点がある")
    elif tg >= 4:
        tags.append("tech")

    # ── Tier 2 タグ ─────────────────────────────────────────────────────────
    if be >= 5:
        tags.append("big_event")
        reasons.append("政治・経済の大型イベント")

    if gd >= 5:
        tags.append("geopolitics")
        reasons.append("地政学・安全保障・紛争に関連")

    # ── Daily Programming バケット補助タグ ──────────────────────────────────
    if be >= 3 or gd >= 3:
        tags.append("politics_economy")
    if axes.get("_has_sports", 0.0) > 0:
        tags.append("sports")
    if axes.get("_has_ent", 0.0) > 0 and not axes.get("_has_sports", 0.0):
        tags.append("entertainment")

    # ── Tier 3 タグ ─────────────────────────────────────────────────────────
    if ma >= 6:
        if be >= 3 or tg >= 3:
            tags.append("sports_economics")
            reasons.append("スポーツ・エンタメだが経済・社会的背景が強い（Tier 1 相当）")
        else:
            tags.append("viral")
            reasons.append("大型スポーツ・エンタメ案件")
    elif ma >= 3:
        tags.append("mass_appeal")

    # ── 共通タグ ─────────────────────────────────────────────────────────────
    if jr >= 7:
        tags.append("japan_core")
    elif jr >= 4:
        tags.append("japan_relevant")
    else:
        tags.append("low_japan_relevance")
        if "日本との関連性が弱い" not in reasons:
            reasons.append("日本との関連性が弱い")

    if ga >= 4:
        tags.append("global_coverage")

    # ── 背景推論ポテンシャルタグ ─────────────────────────────────────────────
    if bip >= 7:
        tags.append("inference_rich")
        reasons.append("報道差から意味ある背景仮説を立てられる可能性が高い")
    elif bip >= 4:
        tags.append("inference_possible")

    # ── Region-aware タグ（多地域 pilot） ────────────────────────────────────
    mrs  = axes.get("multi_region_score", 0.0)
    rcs  = axes.get("regional_contrast_score", 0.0)
    jpnw = axes.get("jp_plus_nonwestern_score", 0.0)
    bsb  = axes.get("bridge_source_bonus", 0.0)

    if mrs >= 5.0:
        tags.append("multi_region")
        reasons.append("複数の地域・地政学視点からの報道（多地域ソース）")
    if rcs >= 5.0:
        tags.append("jp_nonwestern")
        reasons.append("日本 vs 中東・東アジアなど非西側視点との比較可能")
    if bsb >= 2.0 and "multi_region" not in tags:
        tags.append("bridge_source")
        reasons.append("AlJazeera / France24 / CNA などの bridge source あり")

    # ── Tier 決定 ────────────────────────────────────────────────────────────
    cli = axes.get("crime_local_indicator", 0.0)

    # EN-only（jp_view なし）かつ low_japan_relevance（jr<4）の場合は Tier 1 をさらに制限
    has_jp_v = axes.get("has_jp_view", 1.0) > 0
    en_only_low_jr = (not has_jp_v) and (jr < 4)

    # coverage_gap 単独では Tier 1 に上がりにくくする
    # EN-only + low_jr の場合は非常に厳しい条件（強い戦略的文脈が必須）
    if en_only_low_jr:
        cg_qualifies_t1 = (cg >= 7 and (tg >= 5 or be >= 5 or gd >= 5))
    else:
        cg_qualifies_t1 = (cg >= 7) or (cg >= 5 and (tg >= 3 or be >= 3 or gd >= 3 or jr >= 5))

    # 戦略×日本ブースト: big_event/geopolitics/tech_geopolitics が強く且つ japan_relevance 高
    strategic_jp_boost = (be >= 5 or gd >= 5 or tg >= 7) and jr >= 6

    # 速報ショック × geopolitics/big_event コンボ → Tier 1
    # breaking_shock が強く、かつ地政学・大型イベント・技術地政学の何れかを伴う場合
    breaking_shock_t1 = bs >= 7 and (gd >= 3 or be >= 3 or tg >= 3)
    # geopolitics + market_shock の複合 → Tier 1
    geo_market_t1 = (gd >= 5 or be >= 5) and bs >= 4

    # Tier 1 基本条件（犯罪フラグがない場合のみ）
    tier1_base = (
        pg >= 6
        or cg_qualifies_t1
        or tg >= 7
        or (ma >= 6 and (be >= 3 or tg >= 3))
        or strategic_jp_boost
        or breaking_shock_t1
        or geo_market_t1
    )
    # Tier 2 基本条件（breaking_shock >= 5 も Tier 2 以上に）
    tier2_base = be >= 5 or gd >= 5 or pg >= 4 or tg >= 5 or bs >= 5

    # 犯罪フラグはティアを 1 段階降格（戦略的文脈なし犯罪/地域事件を抑制）
    if tier1_base and cli == 0.0:
        tier = "Tier 1"
    elif tier1_base and cli > 0.0:
        tier = "Tier 2"   # 犯罪 → Tier 1 から 2 に降格
    elif tier2_base and cli == 0.0:
        tier = "Tier 2"
    elif tier2_base and cli > 0.0:
        tier = "Tier 3"   # 犯罪 → Tier 2 から 3 に降格
    else:
        tier = "Tier 3"

    if not reasons:
        reasons.append("国内単独トピック（視点差・技術覇権・グローバル注目度が低い）")

    reason = f"{tier}: " + "、".join(reasons[:3])
    return tier, tags, reason


def _editorial_score_adjustment(axes: dict[str, float], tier: str) -> float:
    """編集方針に基づくスコア調整値を返す（加点・減点ともあり）。"""
    pg  = axes["perspective_gap_score"]
    cg  = axes["coverage_gap_score"]
    tg  = axes["tech_geopolitics_score"]
    gd  = axes["geopolitics_depth_score"]
    be  = axes["big_event_score"]
    jr  = axes["japan_relevance_score"]
    ga  = axes["global_attention_score"]
    cli = axes.get("crime_local_indicator", 0.0)
    bip = axes.get("background_inference_potential", 0.0)

    has_jp_v = axes.get("has_jp_view", 1.0) > 0
    has_en_v = axes.get("has_en_view", 0.0) > 0
    bs  = axes.get("breaking_shock_score", 0.0)

    adj = 0.0

    # Tier ボーナス（編集方針の核心）
    adj += {"Tier 1": 15.0, "Tier 2": 8.0, "Tier 3": 0.0}.get(tier, 0.0)

    # perspective_gap を coverage_gap より明確に高く重みづけ
    adj += min(pg * _ADJ_PG_WEIGHT, _ADJ_PG_CAP)   # pg*0.9 cap 8
    adj += min(cg * _ADJ_CG_WEIGHT, _ADJ_CG_CAP)   # cg*0.15 cap 1.5（coverage_gap 単独を抑制）
    adj += min(tg * 0.3, 3.0)
    adj += min(gd * 0.3, 2.0)

    # 速報・マクロショックボーナス（比例 + コンボ）
    adj += min(bs * 0.5, 5.0)                        # 比例: bs*0.5 cap 5.0
    if bs >= 6 and (gd >= 3 or be >= 3):
        adj += _BREAKING_SHOCK_BONUS                  # geopolitics × breaking_shock コンボ

    # 背景推論ポテンシャルボーナス（報道差から仮説を立てられる素地）
    adj += min(bip * 0.4, 4.0)

    # JP+EN 両ビューあり → 優先ボーナス
    if has_jp_v and has_en_v:
        adj += _JP_EN_BOTH_BONUS

    # 戦略×日本ボーナス: big_event/geopolitics/tech が強く且つ japan_relevance 高
    if (be >= 5 or gd >= 5 or tg >= 7) and jr >= 6:
        adj += _STRATEGIC_JAPAN_BONUS

    # 日本関連 & グローバル注目の両軸高ボーナス（旧 3.0 → 4.0）
    if jr >= 6 and ga >= 5:
        adj += _DUAL_HIGH_BONUS

    # ペナルティ: 日本関連性が低い
    if jr < 2:
        adj -= 8.0
    # ペナルティ: EN-only かつ low_japan_relevance（Bloomberg 単独等の抑制）
    if not has_jp_v and jr < 4:
        adj += _EN_ONLY_LOW_JR_PENALTY
    # ペナルティ: JP も EN も弱い（ローカル・マイナー）
    if ga < 2 and jr < 5:
        adj -= 5.0
    # ペナルティ: 編集的シグナルが全体的に弱い（国内フィラー）
    if all(s < 3 for s in [pg, cg, tg, be, gd]):
        adj -= 5.0

    # 犯罪/地域事件ペナルティ（戦略的文脈なし）
    if cli > 0.0:
        adj += _CRIME_LOCAL_PENALTY

    # ── Region-aware bonus（上限付き・quality floor を上書きしない） ───────────
    # 多地域ソースによる視点の豊かさを小さく加点する。
    # weak candidate を無理に押し上げないよう、各軸の上限を小さく設定。
    mrs  = axes.get("multi_region_score", 0.0)
    rcs  = axes.get("regional_contrast_score", 0.0)
    jpnw = axes.get("jp_plus_nonwestern_score", 0.0)
    bsb  = axes.get("bridge_source_bonus", 0.0)

    adj += min(mrs  * 0.2, 1.5)   # up to 1.5: multi-region source diversity
    adj += min(rcs  * 0.3, 2.0)   # up to 2.0: JP vs non-western contrast
    adj += min(jpnw * 0.3, 1.5)   # up to 1.5: JP + non-western specific signal
    adj += min(bsb  * 0.4, 1.5)   # up to 1.5: bridge source (AlJazeera/France24/CNA)

    return adj


# ────────────────────────────────────────────────────────────────────────────
# トリアージ説明生成（透明性のための根拠出力）
# ────────────────────────────────────────────────────────────────────────────

def _build_triage_explanation(
    axes: dict[str, float],
    tier: str,
    breakdown: dict[str, float],
) -> list[str]:
    """なぜ選ばれたか・方針適合・懸念を4行で返す（簡潔版）。

    形式:
      [Tier] Tier X
      [選定理由] シグナル1, シグナル2, シグナル3
      [方針適合] ◎/○/△/× 短い評価
      [懸念] 懸念点 or なし
    """
    pg  = axes["perspective_gap_score"]
    cg  = axes["coverage_gap_score"]
    tg  = axes["tech_geopolitics_score"]
    be  = axes["big_event_score"]
    gd  = axes["geopolitics_depth_score"]
    jr  = axes["japan_relevance_score"]
    ga  = axes["global_attention_score"]
    cli = axes.get("crime_local_indicator", 0.0)
    bip = axes.get("background_inference_potential", 0.0)
    bs  = axes.get("breaking_shock_score", 0.0)
    has_jp_v = axes.get("has_jp_view", 1.0) > 0
    has_en_v = axes.get("has_en_view", 0.0) > 0

    lines: list[str] = [f"[Tier] {tier}"]

    # 選定理由: 有効なシグナルを最大3つ（breaking_shock は最優先で先頭に）
    signals: list[str] = []
    if bs >= 7:
        signals.append(f"breaking_shock={bs:.0f}(地政学×市場ショック)")
    elif bs >= 5:
        signals.append(f"market_shock={bs:.0f}(ショックシグナル)")
    if pg >= 6:
        signals.append(f"perspective_gap={pg:.0f}(日英視点差大)")
    elif pg >= 4:
        signals.append(f"perspective_gap={pg:.0f}(日英視点差あり)")
    if tg >= 7:
        signals.append(f"tech_geopolitics={tg:.0f}(技術覇権)")
    elif tg >= 5:
        signals.append(f"tech_geopolitics={tg:.0f}(技術関連)")
    if be >= 5:
        signals.append(f"big_event={be:.0f}(大型イベント)")
    if gd >= 5:
        signals.append(f"geopolitics={gd:.0f}(地政学)")
    if cg >= 6:
        label = "EN-only未報道" if not has_jp_v else "海外>>日本"
        signals.append(f"coverage_gap={cg:.0f}({label})")
    if jr >= 6 and ga >= 5:
        signals.append(f"jp×global高(jr={jr:.0f}/ga={ga:.0f})")
    # Region-aware シグナル
    rcs_sig  = axes.get("regional_contrast_score", 0.0)
    mrs_sig  = axes.get("multi_region_score", 0.0)
    bsb_sig  = axes.get("bridge_source_bonus", 0.0)
    if rcs_sig >= 5.0:
        regions_sig = breakdown.get("source_regions", [])
        non_jp_sig = [r for r in regions_sig if r not in ("japan", "global")]
        signals.append(f"regional_contrast={rcs_sig:.0f}(JP vs {'+'.join(non_jp_sig)})")
    elif mrs_sig >= 5.0:
        regions_sig = breakdown.get("source_regions", [])
        signals.append(f"multi_region={mrs_sig:.0f}({','.join(regions_sig)})")
    elif bsb_sig >= 2.0:
        signals.append(f"bridge_source={bsb_sig:.0f}(AlJazeera/France24/CNA)")
    if has_jp_v and has_en_v and not signals:
        signals.append("JP+EN両ソース")
    lines.append(f"[選定理由] {', '.join(signals[:3]) if signals else '特記シグナルなし'}")

    # 方針適合評価
    strategic_signals = sum([
        pg >= 6,
        cg >= 7 or (cg >= 5 and (jr >= 5 or tg >= 3 or be >= 3)),
        tg >= 7,
        be >= 5,
        gd >= 5,
        bool(jr >= 6 and ga >= 5),
        bs >= 7,
    ])
    if cli > 0.0:
        lines.append("[方針適合] × 犯罪/地域事件・戦略的文脈なし")
    elif strategic_signals >= 2:
        lines.append("[方針適合] ◎ 複数の戦略的シグナル")
    elif strategic_signals == 1:
        lines.append("[方針適合] ○ 一部の戦略的シグナル")
    else:
        lines.append("[方針適合] △ 戦略的シグナル弱")

    # 懸念点
    concerns: list[str] = []
    if not has_jp_v and jr < 4:
        concerns.append("EN-only + 日本関連性低")
    elif jr < 2:
        concerns.append("日本関連性極低")
    if cli > 0.0:
        concerns.append("犯罪フラグ")
    if all(s < 3 for s in [pg, cg, tg, be, gd]):
        concerns.append("編集シグナル全般弱")
    lines.append(f"[懸念] {', '.join(concerns) if concerns else 'なし'}")

    return lines


# ────────────────────────────────────────────────────────────────────────────
# Primary Bucket 決定（Daily Programming 用）
# ────────────────────────────────────────────────────────────────────────────

def _assign_primary_bucket(axes: dict[str, float], category: str) -> str:
    """編集カテゴリ（primary_bucket）を決定する。

    Bucket 一覧:
        breaking_shock          速報性の高い地政学・マクロショック
        japanese_person_abroad  日本人著名人の海外報道
        japan_abroad            日本の政治・経済の海外報道
        tech_geopolitics        AI/半導体等の技術覇権
        geopolitics             地政学・紛争・安全保障
        politics_economy        政治・経済の大型イベント
        sports                  スポーツ（経済角度含む）
        entertainment           エンタメ
        coverage_gap            海外注目・日本未報道
        mass_appeal             大衆的関心
        general                 その他
    """
    bs  = axes.get("breaking_shock_score", 0.0)
    jpa = axes.get("japanese_person_abroad_score", 0.0)
    ja  = axes.get("japan_abroad_score", 0.0)
    tg  = axes.get("tech_geopolitics_score", 0.0)
    gd  = axes.get("geopolitics_depth_score", 0.0)
    be  = axes.get("big_event_score", 0.0)
    ma  = axes.get("mass_appeal_score", 0.0)
    cg  = axes.get("coverage_gap_score", 0.0)

    # 優先順位順に決定
    if bs >= 7:
        return "breaking_shock"
    if jpa >= 5:
        return "japanese_person_abroad"
    if ja >= 5:
        return "japan_abroad"
    if tg >= 7:
        return "tech_geopolitics"
    if gd >= 5:
        return "geopolitics"
    if be >= 5:
        return "politics_economy"
    # スポーツ / エンタメ
    if axes.get("_has_sports", 0.0) > 0 and ma >= 4:
        return "sports"
    if axes.get("_has_ent", 0.0) > 0 and ma >= 4:
        return "entertainment"
    # EN-only coverage_gap
    if cg >= 6 and axes.get("has_jp_view", 1.0) == 0:
        return "coverage_gap"
    if ma >= 3:
        return "mass_appeal"
    # カテゴリベースの fallback
    _CAT_BUCKET = {
        "economy": "politics_economy",
        "politics": "politics_economy",
        "technology": "tech_geopolitics",
        "sports": "sports",
        "entertainment": "entertainment",
    }
    return _CAT_BUCKET.get(category, "general")


# ────────────────────────────────────────────────────────────────────────────
# コアスコアリング（既存ロジック）
# ────────────────────────────────────────────────────────────────────────────

def _compute_score_core(event: NewsEvent) -> tuple[float, dict[str, float]]:
    """カテゴリ・キーワード・クロスランゲージ・品質ペナルティによる基本スコア。"""
    breakdown: dict[str, float] = {}

    base = CATEGORY_BASE.get(event.category, 50.0)
    breakdown["category_base"] = base

    keyword_bonus = 0.0
    text = event.title + " " + event.summary
    for kw, bonus in HIGH_IMPACT_KEYWORDS:
        if kw in text:
            keyword_bonus += bonus
            breakdown[f"kw:{kw}"] = bonus

    tag_bonus = min(len(event.tags) * 1.5, 6.0)
    breakdown["tag_bonus"] = tag_bonus

    jv = event.japan_view
    gv = event.global_view
    has_sources      = bool(event.sources_jp or event.sources_en)
    has_gap_reasoning = bool(event.gap_reasoning)
    has_both_views   = bool(jv and gv and jv.strip() != gv.strip())

    cross_lang_bonus = 0.0
    if has_both_views:
        if has_gap_reasoning and has_sources:
            cross_lang_bonus = _CROSS_LANG_BONUS_FULL
        elif has_gap_reasoning:
            cross_lang_bonus = _CROSS_LANG_BONUS_GAP_ONLY
        elif has_sources:
            cross_lang_bonus = _CROSS_LANG_BONUS_SRC_ONLY
        else:
            cross_lang_bonus = _CROSS_LANG_BONUS_CLUSTER
    if cross_lang_bonus:
        breakdown["cross_lang_bonus"] = cross_lang_bonus

    if not has_sources:
        breakdown["source_fallback_penalty"] = _SOURCE_FALLBACK_PENALTY
    if not event.impact_on_japan:
        breakdown["japan_impact_absent_penalty"] = _JAPAN_IMPACT_ABSENT_PENALTY
    if not event.background:
        breakdown["context_depth_absent_penalty"] = _CONTEXT_DEPTH_ABSENT_PENALTY
    if has_sources and has_both_views and not has_gap_reasoning:
        breakdown["perspective_weak_penalty"] = _PERSPECTIVE_WEAK_PENALTY

    penalties = sum(v for k, v in breakdown.items() if "penalty" in k)
    core_total = max(0.0, min(base + keyword_bonus + tag_bonus + cross_lang_bonus + penalties, 100.0))
    breakdown["total"] = core_total
    return core_total, breakdown


# ────────────────────────────────────────────────────────────────────────────
# 公開 API
# ────────────────────────────────────────────────────────────────────────────

def compute_score_full(
    event: NewsEvent,
) -> tuple[float, dict[str, float], str, list[str], str]:
    """スコア・breakdown・編集メタデータを全て返す。

    Returns:
        (total_score, breakdown_dict, primary_tier, editorial_tags, editorial_reason)
    """
    core_score, breakdown = _compute_score_core(event)

    axes = _score_editorial_axes(event)
    tier, tags, reason = _compute_editorial_meta(axes)
    adj = _editorial_score_adjustment(axes, tier)

    # primary_bucket を決定（Daily Programming 用）
    primary_bucket = _assign_primary_bucket(axes, event.category)

    # editorial 軸を breakdown に追記（namespace: "editorial:"）
    # NOTE: _has_sports / _has_ent などの内部フラグは "editorial:_" で保存（参照用）
    for k, v in axes.items():
        breakdown[f"editorial:{k}"] = v
    breakdown["editorial_adjustment"] = adj
    breakdown["primary_bucket"] = primary_bucket

    # 透明性: どの地域・言語ソース由来かを記録（スコアには影響しない）
    if event.sources_by_locale:
        breakdown["source_regions"] = sorted(event.sources_by_locale.keys())  # type: ignore[assignment]
    source_languages = sorted({
        ref.language
        for refs in event.sources_by_locale.values()
        for ref in refs
        if ref.language
    })
    if source_languages:
        breakdown["source_languages"] = source_languages  # type: ignore[assignment]

    # Region mix 説明（scheduler / daily_schedule の透明性のために）
    _regions_list: list[str] = sorted(event.sources_by_locale.keys()) if event.sources_by_locale else []
    _rcs = axes.get("regional_contrast_score", 0.0)
    _mrs = axes.get("multi_region_score", 0.0)
    _jpnw = axes.get("jp_plus_nonwestern_score", 0.0)
    if _regions_list:
        _labels = [_REGION_LABELS.get(r, r) for r in _regions_list]
        _non_jp = [r for r in _regions_list if r not in ("japan", "global")]
        _non_jp_labels = [_REGION_LABELS.get(r, r) for r in _non_jp]
        if _rcs >= 5.0 and _non_jp:
            breakdown["why_this_region_mix"] = (  # type: ignore[assignment]
                f"日本 vs {'/'.join(_non_jp_labels)}の視点コントラスト（{', '.join(_labels)}）"
            )
            breakdown["regional_contrast_reason"] = (  # type: ignore[assignment]
                f"regional_contrast={_rcs:.1f}：{'/'.join(_non_jp_labels)}視点が加わることで"
                f"日本との比較が成立する"
            )
        elif _rcs >= 3.0 and _non_jp:
            breakdown["why_this_region_mix"] = (  # type: ignore[assignment]
                f"日本 + {'/'.join(_non_jp_labels)}の比較可能（{', '.join(_labels)}）"
            )
            breakdown["regional_contrast_reason"] = (  # type: ignore[assignment]
                f"regional_contrast={_rcs:.1f}：{'/'.join(_non_jp_labels)}視点あり"
            )
        elif _mrs >= 5.0:
            breakdown["why_this_region_mix"] = (  # type: ignore[assignment]
                f"複数地域ソース（{', '.join(_labels)}）による多角的報道"
            )
            breakdown["regional_contrast_reason"] = (  # type: ignore[assignment]
                f"multi_region={_mrs:.1f}：{len(_regions_list)}地域からの視点"
            )
        elif len(_regions_list) >= 2:
            breakdown["why_this_region_mix"] = (  # type: ignore[assignment]
                f"ソース地域: {', '.join(_labels)}"
            )

    # core score に editorial 調整を適用
    total = max(0.0, min(core_score + adj, 100.0))
    breakdown["total"] = total

    # トリアージ説明（why / policy_fit / which scores / which penalties）
    breakdown["triage_explanation"] = _build_triage_explanation(axes, tier, breakdown)  # type: ignore[assignment]

    return total, breakdown, tier, tags, reason


def compute_score(event: NewsEvent) -> tuple[float, dict[str, float]]:
    """後方互換ラッパー。(score, breakdown) のみ返す。"""
    total, breakdown, _, _, _ = compute_score_full(event)
    return total, breakdown
