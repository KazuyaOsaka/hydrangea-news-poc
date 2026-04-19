from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

from src.generation.title_generator import generate_title_layer
from src.llm.base import LLMClient
from src.llm.factory import get_script_llm_client
from src.shared.config import LLM_PROVIDER
from src.shared.logger import get_logger
from src.shared.models import NewsEvent, ScoredEvent, ScriptSection, VideoScript

if TYPE_CHECKING:
    from src.budget import BudgetTracker

logger = get_logger(__name__)

# 各セクションの秒数（合計75秒）
_DURATIONS = {
    "hook": 3,
    "fact": 12,
    "arbitrage_gap": 25,
    "background": 15,
    "japan_impact": 20,
}

_SECTION_KEYS = ["hook", "fact", "arbitrage_gap", "background", "japan_impact"]

# ── プラットフォームプロファイル ──────────────────────────────────────────────
# "shared" = TikTok + YouTube Shorts 共通。将来分岐できる設計。
PLATFORM_PROFILES: dict[str, dict[str, int]] = {
    "shared": {
        "target_sec":   75,
        "min_sec":      70,
        "max_sec":      90,
        "hard_min_sec": 60,   # TikTok 収益化ボーダー
        "hard_max_sec": 100,  # 絶対上限
    },
    "tiktok": {
        "target_sec":   72,
        "min_sec":      60,
        "max_sec":      85,
        "hard_min_sec": 60,
        "hard_max_sec": 90,
    },
    "youtube_shorts": {
        "target_sec":   78,
        "min_sec":      60,
        "max_sec":      90,
        "hard_min_sec": 60,
        "hard_max_sec": 100,
    },
}

# 日本語ナレーション速度（文字/秒）
_JP_CHARS_PER_SEC: float = 4.5

# セクションごとの目標文字数（_DURATIONS × _JP_CHARS_PER_SEC の近似値）
_TARGET_CHARS = {k: round(v * _JP_CHARS_PER_SEC) for k, v in _DURATIONS.items()}


def _estimate_duration_sec(text: str) -> int:
    """日本語テキストの読み上げ秒数を推定する（空白・改行を除いた文字数ベース）。"""
    chars = len("".join(text.split()))
    return round(chars / _JP_CHARS_PER_SEC)


def _trim_to_fit(text: str, max_chars: int) -> str:
    """テキストを max_chars 文字（空白除く）以下に、文末単位で切り詰める。

    句点（。）で自然に切る。ただし、目標長の 80% 以上の位置にある句点のみ使う。
    これにより、最初の短い文で大幅に短縮されるのを防ぐ。
    """
    cleaned_len = len("".join(text.split()))
    if cleaned_len <= max_chars:
        return text
    # 空白除き文字数で cut 位置を特定
    char_count = 0
    cut_pos = len(text)
    for i, ch in enumerate(text):
        if ch not in (" ", "\n", "\t", "\r"):
            char_count += 1
        if char_count >= max_chars:
            cut_pos = i + 1
            break
    # cut_pos より手前の最後の句点で終わらせる（自然な文末）
    # 80% より前の句点は使わない（大幅な短縮を防ぐ）
    last_kuten = text.rfind("。", 0, cut_pos)
    if last_kuten > int(cut_pos * 0.8):
        return text[:last_kuten + 1]
    return text[:cut_pos]


def _compress_sections(
    sections: list[ScriptSection],
    target_max_sec: int,
    estimated_sec: int,
) -> tuple[list[ScriptSection], int]:
    """
    推定秒数が target_max_sec を超えている場合にセクションを圧縮する。

    - hook / fact は短いため触らない
    - arbitrage_gap / background / japan_impact を比率で削る
    - 句点単位で自然に切り詰める

    Returns:
        (compressed_sections, new_estimated_sec)
    """
    if estimated_sec <= target_max_sec:
        return sections, estimated_sec

    target_total_chars = int(target_max_sec * _JP_CHARS_PER_SEC)
    current_total = sum(len("".join(s.body.split())) for s in sections)
    if current_total == 0:
        return sections, estimated_sec

    excess = current_total - target_total_chars
    if excess <= 0:
        return sections, estimated_sec

    _COMPRESSIBLE = ("arbitrage_gap", "background", "japan_impact")
    compress_source_chars = sum(
        len("".join(s.body.split())) for s in sections if s.heading in _COMPRESSIBLE
    )
    if compress_source_chars == 0:
        return sections, estimated_sec

    new_sections: list[ScriptSection] = []
    for s in sections:
        if s.heading not in _COMPRESSIBLE:
            new_sections.append(s)
            continue
        chars = len("".join(s.body.split()))
        # 超過分をこのセクションの比率で削る
        trim = int(excess * chars / compress_source_chars)
        # セクション目標文字数の 75% を下限とする
        new_max = max(chars - trim, int(_TARGET_CHARS.get(s.heading, chars) * 0.75))
        trimmed_body = _trim_to_fit(s.body, new_max)
        new_sections.append(s.model_copy(update={"body": trimmed_body}))

    all_body = " ".join(s.body for s in new_sections)
    new_estimated = _estimate_duration_sec(all_body)
    logger.info(
        f"[Duration] Compressed {estimated_sec}s → {new_estimated}s "
        f"(target_max={target_max_sec}s)"
    )
    return new_sections, new_estimated

# 動画台本生成プロンプト
# 呼び出し側で {{SELECTED_EVENT_JSON}} と {{TRIAGE_RESULT_JSON}} を .replace() で置換すること
_PROMPT_TEMPLATE = """\
あなたは、TikTok・YouTube Shorts 向けの知的ショート動画台本作家です。
目的は、日本の視聴者に「点と点が繋がって霧が晴れる」という知的興奮（Intellectual High）を、60〜90秒で届けることです。

## メディアのコンセプト
「このチャンネルを見ると、世界がいつもと違って見える」——煽りではなく、純粋な知的好奇心を満たすインテリジェンス・ショートメディア。

## ターゲット
20代後半〜40代の、知的好奇心が高く、世界の動きで損をしたくない日本人ビジネス層。

## 台本のゴール（Intellectual High）
1. **情報の価値提示**: 「今、この瞬間に世界で起きている本当の変化」を知るべき理由を冒頭で提示する
2. **3Dの世界観**: 日英だけでなく、中東・アジア・欧州など複数地域の視点を組み合わせ、「パズルが揃う」体験を作る
3. **圧倒的なわかりやすさ**: 専門用語を直感的なメタファーに置き換え（「キャリートレード」→「低金利円を借りて他国に投資する手法」「地政学的緊張」→「隣国同士の縄張り争い」）
4. **知的な祝福で締める**: 最後に「この視点を持てば、明日からのニュースが違って見えます」という一言で視聴者の成長を後押しする

## 台本構成（Facts → Global Map → Deep Insight → Empowerment）
必ず以下の5部構成にしてください。

1. hook（0〜3秒）— 【Opening: 問い or 視点差の逆転】
- 冒頭の1文で「問い」か「視点差の逆転」を提示する
- 1文で完結させる。20字以内が理想
- 「日本ではA。でも世界ではBという問いが立っている」のように視点を反転させる
- 汎用的な挨拶（「こんにちは」「今日は〜についてです」）は禁止
- 長い文・複数文・自分の立場表明は禁止
- 例: 「なぜ世界がこれほど違う反応をしたのか。」（18字）

2. fact（3〜15秒）— 【FACTS: 起きたこと】
- 最重要の事実を1点に絞り、2〜3文以内で書く
- 余計な装飾・背景・推測を入れない
- 事実を短く、客観的に示す

3. arbitrage_gap（15〜40秒）— 【Global Map: 世界の見え方マップ】
- sources_by_locale の各地域（japan / global / middle_east / europe / east_asia 等）の視点を積極的に活用する
- 「日本ではA、米英ではB」という対比で示す。ただし列挙しすぎない
- **報道差の中で最も鮮明な差を1〜2点だけ取り上げる**（冗長な列挙は禁止）
- どの媒体が何を強調し、何を強調しなかったかを具体的に示す
- ここはまだ「事実の差」の提示であり、その理由の推測は次のセクションで行う

4. background（40〜55秒）— 【Deep Insight: 構造的な「なぜ？」】
- **冒頭の1文で「結局、これは〇〇の問題なんです」と構造を一言で言う**
- 続けて、直感的なメタファーで構造を解き明かす（「〇〇の取り合い」「クラス内の〇〇関係と同じ構図」）
- 文化・制度・地政学・経済合理性・歴史的経緯などから背景仮説を立てる
- 【重要】必ず推定表現を使うこと:
  「〜という仮説が立てられます」
  「〜という背景が影響している可能性があります」
  「報道の差を見る限り、〜という見方が考えられます」
- 事実と仮説を混ぜない。断定しない。陰謀論・誹謗中傷は禁止

5. japan_impact（55〜75秒）— 【Empowerment: あなたへの知的武器】
- **生活・市場・キャリア・家計のどれか1つに具体的に落とす**（複数並べない）
- 「今後どこを注視すべきか」を一言で指し示す
- **必ず「この視点を持てば〜」「これを知っておくと〜」という知的な祝福の一文で締める**
- 煽りすぎず、余韻を残す

## 文体（TikTok向け口語・短文ルール — 最重要）
- 日本語で書く
- 1文は20字以内を目安にする。長い文は句点で区切る
- 話し言葉に近づける（「〜ですよね」「〜なんです」「実はこうなんです」）
- 接続詞を使って流れを作る（「でも」「だから」「つまり」「ここが重要で」）
- 難しい専門用語は必ず言い換える（例: 「キャリートレード」→「低金利円を借りて他国に投資する手法」）
- 1文に1つの情報だけ入れる
- 「〜という背景があります」「〜ということです」は使わない（冗長）
- 「こんにちは」「今日は〜についてです」などの弱い導入は禁止
- 陰謀論っぽい言い回しは禁止
- 過激な煽りは禁止

## 根拠ルール
- 断定形（「〜だ」「〜である」）は、必ず sources_jp / sources_en / sources_by_locale の報道内容を根拠とすること
- 元記事に明記されていない推論は必ず「〜とみられる」「〜という見方もある」「〜という仮説が考えられる」で表現する
- gap_reasoning と japan_impact_reasoning が入力にある場合は、それを根拠として優先参照する
- background セクションでの仮説生成は、報道差の「構造的パターン」から導くこと（根拠のない飛躍は禁止）
- 事実と仮説の区別を常に明確にする: 事実は fact / arbitrage_gap に、仮説は background に入れる

## 文字量の目安（厳守）
- 目標は 72〜78秒（TikTok + YouTube Shorts 共通）
- 下限: 60秒（TikTok 収益化ライン）、上限: 100秒（絶対上限）
- 日本語ナレーション速度の目安: 約4.5文字/秒
- **各セクションの目標文字数（空白除く）:**
  - hook: 約13字（3秒）— 短い問いまたは視点差の逆転
  - fact: 約45字（10秒）— 主要事実1点のみ
  - arbitrage_gap: 約113字（25秒）— 最鮮明な差1〜2点
  - background: 約68字（15秒）— 構造を一言で解く
  - japan_impact: 約90字（20秒）— 具体的な生活・市場接続
  - 全体合計: 約329字（73秒）
- 各セクションは上記の目標文字数を±20%以内に収めること
- 冗長な接続詞・繰り返しは削除する
- 一文を短く区切る（句点で20字以内）
- "賢そうな長文" より "一発で入る短文" を徹底する
- 視聴者が「結局、何が本質か」を1行で言える構成にする

## 必ず含めること
- 世界で何が起きたか
- 複数地域からの見え方の差（sources_by_locale を最大活用）
- その背景にある構造（直感的メタファーで）
- 視聴者への知的な祝福（明日からの世界が変わる一言）

## 入力
以下に、選定済みニュースの情報と、トリアージ結果を渡します。
入力の sources_jp（日本語媒体）と sources_en（英語媒体）を参照し、台本の根拠として使うこと。

## 出力形式
必ずJSONのみで返してください。前置きや説明は不要です。

{
  "title": "動画用の短いタイトル",
  "total_duration_sec": 75,
  "sections": [
    {
      "name": "hook",
      "duration_sec": 3,
      "text": "..."
    },
    {
      "name": "fact",
      "duration_sec": 12,
      "text": "..."
    },
    {
      "name": "arbitrage_gap",
      "duration_sec": 25,
      "text": "..."
    },
    {
      "name": "background",
      "duration_sec": 15,
      "text": "..."
    },
    {
      "name": "japan_impact",
      "duration_sec": 20,
      "text": "..."
    }
  ],
  "keywords": ["...", "...", "..."]
}

{{EVIDENCE_WARNING}}
{{AUTHORITY_MENTION_INSTRUCTION}}
## 入力データ
{{SELECTED_EVENT_JSON}}
{{TRIAGE_RESULT_JSON}}
"""


def _build_authority_mention_instruction(authority_pair: list[str]) -> str:
    """evidence に存在する媒体名を最大2つ使ってよいという指示文を返す。

    authority_pair が空の場合は空文字列を返す（媒体名言及なし）。
    このリストは呼び出し元 (main.py) が evidence に実在するソースのみで構築すること。
    """
    if not authority_pair:
        return ""
    names = "、".join(f"「{n}」" for n in authority_pair[:2])
    return f"""\
## 媒体名言及ルール【evidence-grounded authority mentions】
以下の媒体名は evidence.json に実在が確認済みです。最大2つまで台本内で自然に使ってよいです。
  使ってよい媒体名: {names}

使い方の例（参考）:
  - 「日本では日経が「X」と報じる一方、英Financial Timesは「Y」を強調しています。」
  - 「NHKはAを前面に出していますが、中東のAl JazeeraはBを重く見ています。」

守るべきルール:
  - 上記リスト以外の媒体名を追加・創作しないこと
  - hook セクションに媒体名を並べるだけの文は禁止（内容の対比を示すこと）
  - 媒体名を入れると文が不自然になる場合は省略してよい
  - 台本全体（全セクション合計）で媒体名は最大2つまで

"""


# 疑惑・未確認情報の検出キーワード
_ALLEGATION_KW = [
    "疑惑", "インサイダー", "insider trading", "insider deal", "alleged", "allegation",
    "不正", "横領", "背任", "粉飾", "accounting fraud", "市場操作", "market manipulation",
    "容疑", "被疑", "捜査中", "under investigation",
]
# 権威ある一次ソース（これがあり且つ証拠もある場合のみ断定許可）
_ALLEGATION_AUTH_SOURCES = [
    "reuters", "ap ", "afp", "associated press",
    "financial times", "wsj", "wall street journal",
    "new york times", "bloomberg", "nikkei", "日本経済新聞",
]


def _allegation_warning(event: NewsEvent) -> str:
    """疑惑・未確認情報を含む場合に警告文を返す。権威ソース+証拠が揃っていれば空文字列。"""
    text = f"{(event.title or '').lower()} {(event.summary or '').lower()}"
    if not any(kw in text for kw in _ALLEGATION_KW):
        return ""
    source_lower = (event.source or "").lower()
    has_auth = any(s in source_lower for s in _ALLEGATION_AUTH_SOURCES)
    has_evidence = bool(event.sources_en or event.gap_reasoning)
    if has_auth and has_evidence:
        return ""  # 権威ソース + 証拠あり: 通常の根拠ルールで十分
    return """
## ⚠️ 疑惑・未確認情報の警告【allegation-unverified】
このイベントには疑惑・未確認情報が含まれる可能性があります。以下を厳守すること:
- Reuters / AP / AFP / FT / WSJ / Bloomberg 等の権威ある一次ソースの明示的な裏付けがない限り、疑惑の内容を断言しない
- 「報道によると」「疑いがある」「当局が調査中とされる」など、未確定であることを必ず明示する
- insider trading / 不正 / 疑惑などの表現は推定形（「〜の疑いが報じられている」）のみ使用する
- 訴訟・刑事事件の段階（「疑い」「調査中」「起訴」「有罪判決」）を正確に区別し、混同しない
- script 内でこの疑惑を「確定事実」として断言してはならない
"""


def _evidence_warning_section(
    event: NewsEvent,
    triage_result: "Optional[ScoredEvent]" = None,
) -> str:
    """エビデンス強度に応じた断定制限指示を返す。証拠が弱い場合のみ非空文字列を返す。

    優先度順に判定:
    0. allegation-unverified: 疑惑キーワードあり + 権威ソースなし → 断言禁止
    1. EN-sources-absent: sources_en も global_view も存在しない → 海外比較・推論を全面禁止
    2. inference-absent : gap_reasoning なし かつ bip < 2 → background 仮説を禁止
    3. perspective-weak : gap_reasoning なし かつ sources_en なし → 比較に推定表現を強制
    4. moderate / weak  : 既存のシグナル強度ベース判定
    """
    # 疑惑警告を先頭に結合（他の警告と独立して付与）
    allegation = _allegation_warning(event)
    has_sources_jp = bool(event.sources_jp)
    has_sources_en = bool(event.sources_en)
    has_global_view = bool(event.global_view and event.global_view.strip())
    has_gap = bool(event.gap_reasoning)
    has_impact = bool(event.impact_on_japan)
    has_bg = bool(event.background)

    # background_inference_potential を triage_result から取得（0 = 仮説余地ゼロ）
    bip = 0.0
    if triage_result is not None and triage_result.score_breakdown:
        bip = float(
            triage_result.score_breakdown.get("editorial:background_inference_potential", 0.0)
        )

    # ── 条件 1: EN ソースが存在しない ────────────────────────────────────────
    if not has_sources_en and not has_global_view:
        base = """
## ⚠️ エビデンス警告【EN-sources-absent】
このイベントには海外ソース・海外報道が確認されていません。以下を厳守すること:
- arbitrage_gap セクションに「日本 vs 海外の報道差」や「海外の反応・評価」を書いてはならない
- background セクションで「海外での見方」「欧米の視点」「グローバルな文脈」を推測補完しない
- 「現時点で十分な海外報道は確認できない」と台本内に明示すること
- 断定形・比較形・対比表現はすべて禁止
- japan_impact は「動向を注視している」「影響が出る可能性がある」程度に留めること
- hook は「〜かもしれない」「〜という指摘もある」などの疑問・推測形で開くこと
"""
        return allegation + base

    # ── 条件 2: 背景推論の根拠が存在しない ──────────────────────────────────
    if not has_gap and bip < 2.0:
        base = """
## ⚠️ エビデンス警告【inference-absent】
日英の報道差に関する根拠（gap_reasoning）がなく、背景推論の余地が不十分です:
- background セクションで「なぜこの差が生まれるか」という背景仮説を書かない
- 「この時点では強い比較仮説は置けない」という方向で記述すること
- arbitrage_gap セクションは事実の記述に留め、構造的解釈・仮説を加えない
- 比較・対比は「〜とみられる」「〜という見方もある」を必ずつける
- japan_impact は「今後の動向に注視が必要」「影響の可能性がある」程度に留める
"""
        return allegation + base

    # ── 条件 3: perspective_conflict が弱い（sources_en なし + gap_reasoning なし）──
    if not has_gap and not has_sources_en:
        base = """
## ⚠️ エビデンス注意【perspective-weak】
gap_reasoning と sources_en が未設定です:
- 認識差の説明は推定表現のみ（「〜とみられる」「〜という見方もある」）で書く
- background セクションの仮説は「可能性がある」「示唆される」程度に留める
- EN 媒体名・報道内容を具体的に引用しない（根拠なし）
"""
        return allegation + base

    # ── 条件 4: シグナル強度ベースの従来判定 ────────────────────────────────
    has_sources = has_sources_jp or has_sources_en
    strength = sum([has_sources, has_gap, has_impact, has_bg])

    if strength >= 3:
        return allegation  # 証拠十分: 疑惑警告のみ（あれば）

    if strength >= 1:
        base = """
## ⚠️ エビデンス注意（moderate）
入力データの証拠シグナルが一部不足しています。以下を守ること:
- gap_reasoning が未設定のため、JP/EN の認識差は「〜とみられる」「〜という見方もある」で表現する
- japan_impact セクションは「影響が懸念される」「今後の注視が必要」程度に留める
- 断定形は入力 sources_jp/sources_en に実際に記載のある内容にのみ使用する
"""
        return allegation + base

    base = """
## ⚠️ エビデンス警告（weak）
入力データの証拠シグナルが不十分です。以下のルールを厳守すること:
- sources が不完全なため、ソース名・媒体名を断定的に引用しない
- JP/EN の認識差は必ず推定表現で書く（「〜とみられる」「〜と推測される」）
- japan_impact セクションは「影響が考えられる」「動向に注目したい」程度に留め、断言しない
- hook も断定的な煽りにせず、疑問形や「〜かもしれない」で開くこと
"""
    return allegation + base


def _validate_script(script: VideoScript) -> bool:
    """Return True if all required sections have non-empty body text."""
    if not script.sections:
        return False
    return all(bool(s.body and s.body.strip()) for s in script.sections)


def _build_script_from_llm(
    client: LLMClient,
    event: NewsEvent,
    triage_result: Optional[ScoredEvent] = None,
    authority_pair: list[str] | None = None,
) -> tuple[VideoScript, int]:
    """Build script via LLM. Returns (VideoScript, retry_count)."""
    from src.llm.retry import call_with_retry

    event_json = event.model_dump_json(indent=2)
    triage_json = triage_result.model_dump_json(indent=2) if triage_result else "{}"
    evidence_warning = _evidence_warning_section(event, triage_result)
    authority_instruction = _build_authority_mention_instruction(authority_pair or [])

    prompt = (
        _PROMPT_TEMPLATE
        .replace("{{SELECTED_EVENT_JSON}}", event_json)
        .replace("{{TRIAGE_RESULT_JSON}}", triage_json)
        .replace("{{EVIDENCE_WARNING}}", evidence_warning)
        .replace("{{AUTHORITY_MENTION_INSTRUCTION}}", authority_instruction)
    )

    raw, retry_count = call_with_retry(lambda: client.generate(prompt), role="generation")

    if not raw or not raw.strip():
        raise ValueError("LLM returned None or empty string for script")

    # コードブロックで囲まれていれば除去
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    data = json.loads(raw)

    # 新フォーマット: sections は [{name, duration_sec, text}, ...] の配列
    sections_data = data.get("sections", [])
    if not sections_data:
        raise ValueError("Missing 'sections' in response")

    sections_by_name = {s["name"]: s for s in sections_data}

    sections = []
    for key in _SECTION_KEYS:
        section = sections_by_name.get(key)
        if not section or not section.get("text"):
            raise ValueError(f"Missing section: {key}")
        sections.append(ScriptSection(
            heading=key,
            body=section["text"],
            duration_sec=section.get("duration_sec", _DURATIONS[key]),
        ))

    title = data.get("title", event.title)
    total = data.get("total_duration_sec", sum(_DURATIONS.values()))

    all_body = " ".join(s.body for s in sections)
    estimated = _estimate_duration_sec(all_body)
    profile = PLATFORM_PROFILES["shared"]

    # ── 再圧縮パス: max_sec (90s) を超えている場合に削る ───────────────────
    if estimated > profile["max_sec"]:
        sections, estimated = _compress_sections(sections, profile["max_sec"], estimated)

    if estimated < profile["hard_min_sec"]:
        logger.warning(
            f"[Duration] Estimated {estimated}s < hard_min {profile['hard_min_sec']}s "
            f"— script may be too short for TikTok monetization"
        )
    elif estimated > profile["hard_max_sec"]:
        logger.warning(
            f"[Duration] Estimated {estimated}s > hard_max {profile['hard_max_sec']}s "
            f"— script exceeds absolute ceiling"
        )

    return VideoScript(
        event_id=event.id,
        title=title,
        intro="",
        sections=sections,
        outro="",
        total_duration_sec=total,
        target_duration_sec=profile["target_sec"],
        estimated_duration_sec=estimated,
        platform_profile="shared",
    ), retry_count


def _build_script_fallback(event: NewsEvent) -> VideoScript:
    """API失敗時のテンプレートフォールバック。

    EN ソース・global_view が存在しない場合は、海外比較・推論を生成しない。
    証拠がある場合のみ比較を示す。
    """
    _CATEGORY_CONTEXT = {
        "tech": ("テクノロジー", "AI・半導体・プラットフォーム競争"),
        "technology": ("テクノロジー", "AI・半導体・プラットフォーム競争"),
        "finance": ("金融", "金利・為替・資本市場"),
        "economy": ("経済", "金利・為替・マクロ経済"),
        "geopolitics": ("地政学", "貿易・安全保障・同盟関係"),
        "energy": ("エネルギー", "脱炭素・資源・電力インフラ"),
        "health": ("ヘルスケア", "医薬品・規制・医療費"),
    }
    category_label, category_theme = _CATEGORY_CONTEXT.get(
        event.category.lower(), ("国際情勢", "グローバルなトレンド")
    )

    has_en_evidence = bool(event.global_view or event.sources_en)
    has_gap = bool(event.gap_reasoning)

    # hook: EN ソースがある場合のみ「世界との差」を匂わせる
    if has_en_evidence:
        hook_body = f"「{event.title}」——日本と海外でこの出来事の受け止め方が異なっているかもしれない。"
    else:
        hook_body = f"「{event.title}」——この動きが、今後の{category_theme}にどう影響するか注目されている。"

    # arbitrage_gap: EN 証拠がある場合のみ差分を示す、なければ国内状況のみ
    if has_en_evidence:
        global_summary = event.global_view or ""
        gap_text = (
            f"日本のメディアは{category_label}分野の出来事として伝えた。"
            + (f"一方、海外では「{global_summary[:60]}…」という文脈で報じられているとみられる。" if global_summary else "海外報道との比較は現時点では限られた情報しかない。")
        )
    else:
        gap_text = (
            f"現時点では、この件に関する海外報道は確認できていない。"
            f"{event.source}の報道をもとに、国内の状況を整理する。"
        )

    # background: gap_reasoning があれば使う、なければ推論しない
    if has_gap:
        background_body = (
            f"この報道差が生まれる背景として、{event.gap_reasoning}という可能性が指摘されている。"
        )
    elif has_en_evidence:
        background_body = (
            f"この動きの背景については、現時点では具体的な根拠が十分ではない。"
            f"{category_label}分野における構造変化との関連が考えられるが、仮説の域を出ない段階だ。"
        )
    else:
        background_body = (
            f"現時点では背景の詳細を裏付ける十分な情報がない。"
            f"続報や海外メディアの報道が出てから、改めて分析が必要な段階だ。"
        )

    sections = [
        ScriptSection(
            heading="hook",
            body=hook_body,
            duration_sec=_DURATIONS["hook"],
        ),
        ScriptSection(
            heading="fact",
            body=event.summary,
            duration_sec=_DURATIONS["fact"],
        ),
        ScriptSection(
            heading="arbitrage_gap",
            body=gap_text,
            duration_sec=_DURATIONS["arbitrage_gap"],
        ),
        ScriptSection(
            heading="background",
            body=background_body,
            duration_sec=_DURATIONS["background"],
        ),
        ScriptSection(
            heading="japan_impact",
            body=(
                f"日本への影響としては、"
                + (event.impact_on_japan if event.impact_on_japan else
                   f"国内の{category_label}関連企業や政策立案者にとって動向を注視すべき局面が続く。")
                + "続報とともに引き続き確認していく必要がある。"
            ),
            duration_sec=_DURATIONS["japan_impact"],
        ),
    ]

    total = sum(_DURATIONS.values())
    all_body = " ".join(s.body for s in sections)
    estimated = _estimate_duration_sec(all_body)
    profile = PLATFORM_PROFILES["shared"]

    # ── 再圧縮パス: max_sec (90s) を超えている場合に削る ───────────────────
    if estimated > profile["max_sec"]:
        sections, estimated = _compress_sections(sections, profile["max_sec"], estimated)

    return VideoScript(
        event_id=event.id,
        title=event.title,
        intro="",
        sections=sections,
        outro="",
        total_duration_sec=total,
        target_duration_sec=profile["target_sec"],
        estimated_duration_sec=estimated,
        platform_profile="shared",
    )


def write_script(
    event: NewsEvent,
    triage_result: Optional[ScoredEvent] = None,
    budget: "BudgetTracker | None" = None,
    authority_pair: list[str] | None = None,
) -> VideoScript:
    """
    動画台本を生成する。LLM_PROVIDER のクライアントが利用可能な場合はそちらを使用し、
    失敗時はテンプレートにフォールバックする。
    budget が指定された場合、残量不足ならフォールバックを使用する。
    目標尺: 60〜90秒（目標75秒）

    Args:
        authority_pair: evidence.json に実在が確認済みの媒体名リスト（最大2件）。
                        呼び出し元 (main.py) が select_authority_pair() で構築して渡すこと。
                        None または空リストの場合は媒体名言及なし。
    """
    # ── 安全装置: quality floor 未達候補の検出 ──────────────────────────────
    # スケジューラが held_back に回すべき候補が誤ってここに到達した場合に警告する。
    # （正常フローでは get_next_unpublished が selected のみを返すため、通常は発生しない）
    if triage_result is not None:
        cautions = triage_result.appraisal_cautions or ""
        if (
            cautions.startswith("[抑制]")
            and triage_result.appraisal_type is None
            and triage_result.editorial_appraisal_score == 0.0
        ):
            raise ValueError(
                f"[ScriptWriter] quality_floor_miss: evidence-weak candidate blocked at script generation "
                f"— event_id={event.id}, cautions={cautions[:80]!r}. "
                "This candidate should have been held_back by the scheduler. "
                "Use an explicit override to bypass this guard."
            )

    logger.info(f"Generating script for event [{event.id}] via provider={LLM_PROVIDER}")

    _used_fallback = False
    _fallback_reason: str | None = None
    _retry_count = 0
    script: VideoScript | None = None

    # 予算チェック
    if budget is not None and not budget.can_use_script_llm():
        budget.skip("script_llm")
        _used_fallback = True
        _fallback_reason = "budget_exhausted"
    else:
        client = get_script_llm_client()
        if client is None:
            _used_fallback = True
            _fallback_reason = "no_client"
        else:
            try:
                script, _retry_count = _build_script_from_llm(client, event, triage_result, authority_pair)
                if budget is not None:
                    budget.record_call("script")
                logger.info(
                    f"Script generated via {LLM_PROVIDER}: "
                    f"{len(script.sections)} sections, {script.total_duration_sec}s total, "
                    f"retries={_retry_count}"
                )
            except Exception as e:
                logger.warning(
                    f"{LLM_PROVIDER} script generation failed (retries={_retry_count}), "
                    f"falling back to template: {e}"
                )
                _used_fallback = True
                _fallback_reason = f"llm_error:{type(e).__name__}"

    if _used_fallback or script is None:
        script = _build_script_fallback(event)
        logger.info(
            f"Script generated via fallback ({_fallback_reason}): "
            f"{len(script.sections)} sections, {script.total_duration_sec}s total"
        )

    # Fail-safe: never save an empty/broken script
    if not _validate_script(script):
        raise ValueError(
            f"[ScriptWriter] empty_script: all fallbacks produced empty sections "
            f"for event_id={event.id}. Run marked as error."
        )

    if budget is not None:
        budget.record_generation_outcome("script", _used_fallback, _fallback_reason, _retry_count)

    title_layer = generate_title_layer(event, triage_result)
    return script.model_copy(update={"title_layer": title_layer})
