"""クロスランゲージ（日英）記事マッチングユーティリティ。

高度な埋め込みを使わず、以下の手がかりで日英タイトルを対応づける:
  - 国名辞書 (日本→country:japan, "japan"→country:japan, ...)
  - 企業・機関名辞書 (日銀→entity:boj, "bank of japan"→entity:boj, ...)
  - キーワード対訳辞書 (利上げ→kw:ratehike, "rate hike"→kw:ratehike, ...)
  - 年号・4桁数字 (2024→num:2024)
  - 大文字アクロニム (IMF, NATO, G7 など)

トークンはすべて "prefix:canonical" 形式で名前空間を分離する。
"""
from __future__ import annotations

import json as _json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.llm.base import LLMClient

# ── 国名辞書 ──────────────────────────────────────────────────────────────────

# JP表記 → 正規トークン
_COUNTRY_JP: dict[str, str] = {
    "日本": "japan",
    "米国": "usa",
    "アメリカ": "usa",
    "中国": "china",
    "韓国": "korea",
    "北朝鮮": "northkorea",
    "ロシア": "russia",
    "ウクライナ": "ukraine",
    "ドイツ": "germany",
    "フランス": "france",
    "英国": "uk",
    "イギリス": "uk",
    "インド": "india",
    "イスラエル": "israel",
    "パレスチナ": "palestine",
    "台湾": "taiwan",
    "欧州": "eu",
    "ＥＵ": "eu",
    "EU": "eu",
    "イラン": "iran",
    "サウジ": "saudi",
    "オーストラリア": "australia",
    "カナダ": "canada",
    "ブラジル": "brazil",
    "メキシコ": "mexico",
    "トルコ": "turkey",
}

# EN表記 → 正規トークン (小文字でマッチング)
_COUNTRY_EN: dict[str, str] = {
    "japan": "japan",
    "united states": "usa",
    "u.s.": "usa",
    "america": "usa",
    "china": "china",
    "south korea": "korea",
    "north korea": "northkorea",
    "russia": "russia",
    "ukraine": "ukraine",
    "germany": "germany",
    "france": "france",
    "britain": "uk",
    "united kingdom": "uk",
    "india": "india",
    "israel": "israel",
    "palestine": "palestine",
    "taiwan": "taiwan",
    "europe": "eu",
    "european union": "eu",
    "iran": "iran",
    "saudi": "saudi",
    "australia": "australia",
    "canada": "canada",
    "brazil": "brazil",
    "mexico": "mexico",
    "turkey": "turkey",
}

# ── 企業・機関名辞書 ───────────────────────────────────────────────────────────

# JP表記 → 正規トークン
_ENTITY_JP: dict[str, str] = {
    "日本銀行": "boj",
    "日銀": "boj",
    "連邦準備": "fed",
    "ＦＲＢ": "fed",
    "FRB": "fed",
    "欧州中央銀行": "ecb",
    "ＥＣＢ": "ecb",
    "ECB": "ecb",
    "財務省": "mof",
    "内閣府": "cao",
    "国際通貨基金": "imf",
    "ＩＭＦ": "imf",
    "IMF": "imf",
    "世界銀行": "worldbank",
    "東京証券取引所": "tse",
    "東証": "tse",
    "ＯＰＥＣ": "opec",
    "OPEC": "opec",
    "国連": "un",
    "Ｇ７": "g7",
    "G7": "g7",
    "Ｇ２０": "g20",
    "G20": "g20",
    "ＮＡＴＯ": "nato",
    "NATO": "nato",
    "自民党": "ldp",
    "トヨタ": "toyota",
    "ソニー": "sony",
    "日産": "nissan",
    "ホンダ": "honda",
    "ソフトバンク": "softbank",
    "任天堂": "nintendo",
    "パナソニック": "panasonic",
    "三菱": "mitsubishi",
    "三井": "mitsui",
    "住友": "sumitomo",
    "楽天": "rakuten",
    "ＮＴＴ": "ntt",
    "NTT": "ntt",
    "アップル": "apple",
    "マイクロソフト": "microsoft",
    "エヌビディア": "nvidia",
    "テスラ": "tesla",
    "オリンピック": "olympics",
    "パラリンピック": "paralympics",
    "ＷＨＯ": "who",
    "WHO": "who",
    "ＡＰＥＣ": "apec",
    "APEC": "apec",
    # 人物名（主要政治・経済リーダー）
    "トランプ": "trump",
    "バイデン": "biden",
    "マスク": "musk",
    "イーロン": "musk",
    "岸田": "kishida",
    "石破": "ishiba",
    "習近平": "xijinping",
    "プーチン": "putin",
    "ゼレンスキー": "zelensky",
    # テック企業
    "オープンＡＩ": "openai",
    "オープンAI": "openai",
    "OpenAI": "openai",
    "グーグル": "google",
    "アマゾン": "amazon",
    "メタ": "meta",
    "アルファベット": "alphabet",
    "ＴＳＭＣ": "tsmc",
    "TSMC": "tsmc",
    "台積電": "tsmc",
    "ディープシーク": "deepseek",
    "DeepSeek": "deepseek",
    # 機関・組織
    "ＷＴＯ": "wto",
    "WTO": "wto",
    "ＡＳＥＡＮ": "asean",
    "ASEAN": "asean",
    "ＲＣＥＰ": "rcep",
    "RCEP": "rcep",
    "ＴＰＰ": "tpp",
    "TPP": "tpp",
    "日米": "japan_us",
    "米中": "us_china",
    "日中": "japan_china",
    # スポーツ大型案件
    "大谷翔平": "ohtani",
    "大谷": "ohtani",
    "ドジャース": "dodgers",
    "ヤンキース": "yankees",
    # 地政学・紛争
    "ガザ": "gaza",
    "ハマス": "hamas",
    "ヒズボラ": "hezbollah",
    "ネタニヤフ": "netanyahu",
    "フーシ": "houthi",
    "ＩＳＩＳ": "isis",
    "ISIS": "isis",
    # 政治リーダー
    "マクロン": "macron",
    "モディ": "modi",
    "スターマー": "starmer",
    "ショルツ": "scholz",
}

# EN表記 → 正規トークン (小文字でマッチング)
_ENTITY_EN: dict[str, str] = {
    "bank of japan": "boj",
    "federal reserve": "fed",
    "european central bank": "ecb",
    "ministry of finance": "mof",
    "international monetary fund": "imf",
    "world bank": "worldbank",
    "tokyo stock exchange": "tse",
    "new york stock exchange": "nyse",
    "united nations": "un",
    "toyota": "toyota",
    "sony": "sony",
    "nissan": "nissan",
    "honda": "honda",
    "softbank": "softbank",
    "nintendo": "nintendo",
    "panasonic": "panasonic",
    "mitsubishi": "mitsubishi",
    "mitsui": "mitsui",
    "rakuten": "rakuten",
    "microsoft": "microsoft",
    "nvidia": "nvidia",
    "tesla": "tesla",
    "olympics": "olympics",
    "olympic games": "olympics",
    "world health organization": "who",
    # 人物名
    "trump": "trump",
    "biden": "biden",
    "musk": "musk",
    "elon musk": "musk",
    "kishida": "kishida",
    "ishiba": "ishiba",
    "xi jinping": "xijinping",
    "putin": "putin",
    "zelensky": "zelensky",
    # テック企業
    "openai": "openai",
    "google": "google",
    "amazon": "amazon",
    "meta": "meta",
    "alphabet": "alphabet",
    "tsmc": "tsmc",
    "deepseek": "deepseek",
    "apple": "apple",
    # 機関・組織
    "world trade organization": "wto",
    "asean": "asean",
    "rcep": "rcep",
    "trans-pacific partnership": "tpp",
    "us-japan": "japan_us",
    "japan-us": "japan_us",
    "us-china": "us_china",
    "china-us": "us_china",
    # スポーツ大型案件
    "ohtani": "ohtani",
    "shohei ohtani": "ohtani",
    "dodgers": "dodgers",
    "yankees": "yankees",
    # 地政学・紛争
    "hamas": "hamas",
    "hezbollah": "hezbollah",
    "netanyahu": "netanyahu",
    "houthi": "houthi",
    "houthis": "houthi",
    "isis": "isis",
    "islamic state": "isis",
    "gaza": "gaza",
    # 政治リーダー
    "macron": "macron",
    "modi": "modi",
    "narendra modi": "modi",
    "starmer": "starmer",
    "scholz": "scholz",
}

# ── キーワード対訳辞書 ─────────────────────────────────────────────────────────

# JP表記 → 正規トークン
_KW_JP: dict[str, str] = {
    "利上げ": "ratehike",
    "利下げ": "ratecut",
    "金利": "interestrate",
    "金融緩和": "easing",
    "量的緩和": "easing",
    "金融引き締め": "tightening",
    "インフレ": "inflation",
    "デフレ": "deflation",
    "物価上昇": "inflation",
    "物価": "inflation",
    "円高": "yenstrength",
    "円安": "yenweaken",
    "株価": "stockprice",
    "株式": "stock",
    "株安": "stockdown",
    "株高": "stockup",
    "為替": "forex",
    "景気後退": "recession",
    "不況": "recession",
    "貿易": "trade",
    "貿易摩擦": "tradetension",
    "貿易戦争": "tradewar",
    "関税": "tariff",
    "報復関税": "retaliation",
    "報復": "retaliation",
    "輸入規制": "importrestriction",
    "輸出規制": "exportcontrol",
    "禁輸": "exportcontrol",
    "制裁": "sanction",
    "経済制裁": "sanction",
    "選挙": "election",
    "首相": "primeminister",
    "大統領": "president",
    "地震": "earthquake",
    "台風": "typhoon",
    "増税": "taxhike",
    "減税": "taxcut",
    "戦争": "war",
    "停戦": "ceasefire",
    "半導体": "semiconductor",
    "人工知能": "ai",
    "ＡＩ": "ai",
    "AI": "ai",
    "生成ＡＩ": "genai",
    "生成AI": "genai",
    "少子化": "birthrate",
    "出生率": "birthrate",
    "エネルギー": "energy",
    "原油": "oilprice",
    "石油": "oilprice",
    "原発": "nuclear",
    "核": "nuclear",
    "合併": "merger",
    "買収": "acquisition",
    "倒産": "bankruptcy",
    "破綻": "bankruptcy",
    "リストラ": "layoff",
    "解雇": "layoff",
    "大量解雇": "masslayoff",
    "赤字": "deficit",
    "黒字": "surplus",
    "財政赤字": "fiscaldeficit",
    "国債": "govbond",
    "円": "yen",
    "ドル": "dollar",
    "サプライチェーン": "supplychain",
    "供給網": "supplychain",
    "脱炭素": "decarbonization",
    "再生可能エネルギー": "renewables",
    "太陽光": "solar",
    "EVバッテリー": "ev",
    "電気自動車": "ev",
    "ＥＶ": "ev",
    "EV": "ev",
    # スポーツ大型大会
    "ワールドシリーズ": "worldseries",
    "ＷＢＣ": "wbc",
    "WBC": "wbc",
    "全米オープン": "usopen",
    "全仏オープン": "frenchopen",
    "全豪オープン": "ausopen",
    "ウィンブルドン": "wimbledon",
    "チャンピオンズリーグ": "championsleague",
    "スーパーボウル": "superbowl",
    "ワールドカップ": "worldcup",
    # 地政学・紛争KW
    "停戦合意": "ceaseagreement",
    "和平交渉": "peacetalks",
    "ミサイル攻撃": "missilestrike",
    "地上侵攻": "groundinvasion",
    "人質解放": "hostagerelease",
    "領土問題": "territorial",
    "核兵器": "nuclearweapon",
    "ミサイル": "missile",
    # 東西論点KW
    "言論の自由": "freespeech",
    "検閲": "censorship",
    "人権侵害": "humanrights",
}

# EN表記 → 正規トークン (小文字でマッチング)
_KW_EN: dict[str, str] = {
    "rate hike": "ratehike",
    "interest rate hike": "ratehike",
    "rate cut": "ratecut",
    "interest rate cut": "ratecut",
    "interest rate": "interestrate",
    "quantitative easing": "easing",
    "monetary easing": "easing",
    "inflation": "inflation",
    "deflation": "deflation",
    "tariff": "tariff",
    "tariffs": "tariff",
    "trade war": "tradewar",
    "trade tension": "tradetension",
    "retaliation": "retaliation",
    "retaliatory": "retaliation",
    "export control": "exportcontrol",
    "import ban": "importrestriction",
    "sanction": "sanction",
    "sanctions": "sanction",
    "election": "election",
    "prime minister": "primeminister",
    "president": "president",
    "earthquake": "earthquake",
    "typhoon": "typhoon",
    "recession": "recession",
    "semiconductor": "semiconductor",
    "chip": "semiconductor",
    "artificial intelligence": "ai",
    " ai ": "ai",
    "generative ai": "genai",
    "nuclear": "nuclear",
    "merger": "merger",
    "acquisition": "acquisition",
    "bankrupt": "bankruptcy",
    "layoff": "layoff",
    "mass layoff": "masslayoff",
    "oil price": "oilprice",
    "crude oil": "oilprice",
    "energy": "energy",
    "ceasefire": "ceasefire",
    "cease-fire": "ceasefire",
    "tax hike": "taxhike",
    "tax cut": "taxcut",
    "stock market": "stockprice",
    "stock price": "stockprice",
    "market sell": "stockdown",
    "foreign exchange": "forex",
    "yen": "yen",
    "dollar": "dollar",
    "birth rate": "birthrate",
    "war": "war",
    "deficit": "deficit",
    "surplus": "surplus",
    "fiscal deficit": "fiscaldeficit",
    "government bond": "govbond",
    "treasury": "govbond",
    "supply chain": "supplychain",
    "decarbonization": "decarbonization",
    "renewable energy": "renewables",
    "solar": "solar",
    "electric vehicle": "ev",
    # スポーツ大型大会
    "world series": "worldseries",
    "world baseball classic": "wbc",
    "us open": "usopen",
    "french open": "frenchopen",
    "australian open": "ausopen",
    "wimbledon": "wimbledon",
    "champions league": "championsleague",
    "super bowl": "superbowl",
    "world cup": "worldcup",
    # 地政学・紛争KW
    "ceasefire agreement": "ceaseagreement",
    "peace talks": "peacetalks",
    "missile strike": "missilestrike",
    "ground invasion": "groundinvasion",
    "hostage release": "hostagerelease",
    "territorial dispute": "territorial",
    "nuclear weapon": "nuclearweapon",
    "missile": "missile",
    # 東西論点KW
    "free speech": "freespeech",
    "censorship": "censorship",
    "human rights": "humanrights",
}

# ── 年号パターン ───────────────────────────────────────────────────────────────
# \b は Python3 の re で CJK 文字も \w 扱いするため機能しない場合がある。
# 代わりに「前後が数字でない」条件でマッチする。
_YEAR_RE = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")
# 全角数字を半角に変換するテーブル
_ZEN_TO_HAN = str.maketrans("０１２３４５６７８９．％", "0123456789.%")
# 大文字アクロニム (2文字以上)
_ACRONYM_RE = re.compile(r"\b([A-Z]{2,})\b")
# パーセンテージ: "0.25%", "2.5%", "10%" などの具体的な数値
# → 同一数値が JP/EN 両タイトルに出現すれば高精度なアンカーになる
_PERCENT_RE = re.compile(r"(\d+\.?\d*)%")
# 通貨金額: "$500B", "¥1兆", "€200M" などの規模感
_CURRENCY_RE = re.compile(r"[\$€£¥￥](\d+\.?\d*[BKMT兆億万]?)")


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3040-\u9fff\uf900-\ufaff]", text))


def extract_anchor_tokens(title: str) -> set[str]:
    """タイトルから言語非依存のアンカートークンを抽出する。

    Returns:
        "prefix:canonical" 形式のトークンセット。
        prefix は country / entity / kw / num のいずれか。
    """
    if not title:
        return set()

    tokens: set[str] = set()
    # 全角数字を半角に正規化してから処理
    title_norm = title.translate(_ZEN_TO_HAN)
    lower = title_norm.lower()

    # ── 国名 ──
    for key, canonical in _COUNTRY_JP.items():
        if key in title_norm:
            tokens.add(f"country:{canonical}")
    for key, canonical in _COUNTRY_EN.items():
        if _has_cjk(key):
            if key in title_norm:
                tokens.add(f"country:{canonical}")
        else:
            if key in lower:
                tokens.add(f"country:{canonical}")

    # ── 企業・機関名 ──
    for key, canonical in _ENTITY_JP.items():
        if key in title_norm:
            tokens.add(f"entity:{canonical}")
    for key, canonical in _ENTITY_EN.items():
        if key in lower:
            tokens.add(f"entity:{canonical}")

    # ── キーワード対訳 ──
    for key, canonical in _KW_JP.items():
        if key in title_norm:
            tokens.add(f"kw:{canonical}")
    for key, canonical in _KW_EN.items():
        if key in lower:
            tokens.add(f"kw:{canonical}")

    # ── 年号 ──
    for m in _YEAR_RE.finditer(title_norm):
        tokens.add(f"num:{m.group()}")

    # ── パーセンテージ値 ──
    # 同一の割合（例: 0.25%, 2.5%）が JP/EN タイトルに出れば強いアンカー
    for m in _PERCENT_RE.finditer(title_norm):
        tokens.add(f"num:{m.group()}")

    # ── 通貨金額 ──
    for m in _CURRENCY_RE.finditer(title_norm):
        tokens.add(f"num:currency{m.group()[:8]}")  # 先頭8文字でノイズを抑制

    # ── 大文字アクロニムのフォールバック ──
    # ENTITY_JP/EN に含まれていない未知のアクロニムも拾う (BOJ, FRB, IMF 等)
    for m in _ACRONYM_RE.finditer(title_norm):
        acronym = m.group().lower()
        tokens.add(f"entity:{acronym}")

    return tokens


from typing import Literal

from pydantic import BaseModel, ValidationError


class _MergeVerdict(BaseModel):
    pair_id: int
    verdict: Literal["same_event", "related_but_distinct", "different_event"]
    reason: str = ""


_BATCH_MERGE_PROMPT_TEMPLATE = """\
You are a semantic news deduplication system.

TASK: For each numbered pair (A and B), decide if both headlines describe \
the EXACT SAME real-world event.

STRICT RULE — same_event requires ALL of the following:
  1. Same SUBJECT  — the same actor/entity is the subject of the story
  2. Same PREDICATE — the same specific action or development is described
  3. Same OBJECT/SCOPE — the target or scope of the action matches

COUNTER-EXAMPLES (must NOT be merged even though subjects share a country):
  • "Canada cuts gasoline tax" vs "Canada sends troops to Lebanon"
    → different_event (tax policy ≠ military deployment)
  • "Trump announces China tariffs" vs "Trump meets NATO allies"
    → different_event (trade policy ≠ diplomatic meeting)
  • "Israel strikes Gaza" vs "Israel negotiates hostage deal"
    → different_event (military strike ≠ negotiation)

CORRECT same_event examples:
  • "日本銀行が利上げを決定" vs "Bank of Japan raises interest rates"
    → same_event (BOJ = BOJ; rate hike = rate hike)
  • "ガザ停戦合意が成立" vs "Gaza ceasefire agreement reached"
    → same_event (Gaza ceasefire = Gaza ceasefire)

VERDICT OPTIONS (choose exactly one per pair):
  same_event           — identical subject AND predicate AND scope (merge)
  related_but_distinct — same broad topic, different specific events (keep separate)
  different_event      — clearly different or unrelated events (keep separate)

Return ONLY a valid JSON array — no markdown fences, no text outside JSON.
Format: [{{"pair_id":<int>,"verdict":"<verdict>","reason":"<one-sentence subject+predicate analysis>"}}]

Pairs:
{pairs}"""


def llm_batch_merge(
    pairs: list[dict],
    llm_client: "LLMClient",
    batch_size: int = 15,
) -> list[dict]:
    """Batch LLM call to determine merge verdict for multiple title pairs.

    Sends up to ``batch_size`` pairs per LLM request and returns Pydantic-
    validated verdicts.  Uses the merge_batch role client (resolved by the
    caller via factory.get_llm_client("merge_batch")).

    The prompt enforces subject+predicate semantic matching: a pair is
    same_event only when both the acting entity AND the concrete action match,
    not merely when they share a country name or keyword.

    Args:
        pairs:      List of dicts with keys pair_id (int), title_a (str), title_b (str).
        llm_client: LLM client for the merge_batch role.
        batch_size: Max pairs per LLM request (10–20 recommended).

    Returns:
        List of dicts: {pair_id, verdict: same_event|related_but_distinct|different_event, reason}.
        On parse/validation failure all pairs in the failed batch default to different_event.
    """
    if not pairs:
        return []

    results: list[dict] = []

    for batch_start in range(0, len(pairs), batch_size):
        batch = pairs[batch_start : batch_start + batch_size]

        pair_lines = "\n".join(
            f'[{item["pair_id"]}] A: "{item["title_a"]}" | B: "{item["title_b"]}"'
            for item in batch
        )
        prompt = _BATCH_MERGE_PROMPT_TEMPLATE.format(pairs=pair_lines)

        try:
            raw = llm_client.generate(prompt).strip()
            # Strip markdown code fences if present
            if "```" in raw:
                raw = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()

            raw_list: list[dict] = _json.loads(raw)
            if not isinstance(raw_list, list):
                raise ValueError(f"Expected JSON array, got {type(raw_list)}")

            validated: list[dict] = []
            for item in raw_list:
                try:
                    verdict = _MergeVerdict.model_validate(item)
                    validated.append(verdict.model_dump())
                except ValidationError as ve:
                    # Coerce invalid verdict to different_event rather than dropping
                    pair_id = item.get("pair_id") if isinstance(item, dict) else None
                    if pair_id is not None:
                        validated.append({
                            "pair_id": pair_id,
                            "verdict": "different_event",
                            "reason": f"validation_error:{str(ve)[:80]}",
                        })
            results.extend(validated)
        except Exception as exc:
            # Conservative fallback: treat all as different_event
            for item in batch:
                results.append({
                    "pair_id": item["pair_id"],
                    "verdict": "different_event",
                    "reason": f"llm_batch_error:{str(exc)[:80]}",
                })

    return results


def llm_same_event(
    title_a: str,
    title_b: str,
    llm_client: "LLMClient",
) -> bool:
    """LLM を使って 2 記事タイトルが同一イベントかを判定する。

    Args:
        title_a: 記事 A のタイトル（JP / EN 不問）。
        title_b: 記事 B のタイトル（JP / EN 不問）。
        llm_client: LLMClient インスタンス。

    Returns:
        同一イベントと判定されれば True。エラー時は False。
    """
    prompt = (
        "Determine if the following two news headlines are reporting on the same "
        "real-world event.\n"
        "Reply with only YES or NO.\n\n"
        f"Headline A: {title_a}\n"
        f"Headline B: {title_b}"
    )
    try:
        answer = llm_client.generate(prompt).strip().upper()
        return answer.startswith("YES")
    except Exception:
        return False
