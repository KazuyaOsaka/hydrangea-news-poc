from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field

from src.generation.title_generator import generate_title_layer
from src.llm.base import LLMClient
from src.llm.factory import get_script_llm_client
from src.shared.config import LLM_PROVIDER
from src.shared.logger import get_logger
from src.shared.models import NewsEvent, ScoredEvent, ScriptSection, VideoScript

if TYPE_CHECKING:
    from src.budget import BudgetTracker

logger = get_logger(__name__)

# ── 4ブロック構成の秒数 ───────────────────────────────────────────────────────
_DURATIONS = {
    "hook":      4,   # hook_variants[0] を採用
    "setup":    16,   # ~70字
    "twist":    40,   # ~180字
    "punchline": 20,  # ~90字
}

_SECTION_KEYS = ["hook", "setup", "twist", "punchline"]

# ── 文字数ハードバリデーション境界 ────────────────────────────────────────────
# Python側で計測し、範囲外ならLLMに修正を指示してリトライ
_CHAR_BOUNDS: dict[str, tuple[int, int]] = {
    "hook":      (8,   22),   # hook_variants[0].text: _DURATIONS['hook']=4s × 4.5字/s = 18字 + 余裕
    "setup":     (60,  90),
    "twist":     (150, 220),
    "punchline": (70,  110),
}
_MAX_VALIDATION_RETRIES = 3  # 文字数違反による最大リトライ回数

# ── プラットフォームプロファイル ──────────────────────────────────────────────
PLATFORM_PROFILES: dict[str, dict[str, int]] = {
    "shared": {
        "target_sec":   80,
        "min_sec":      70,
        "max_sec":      90,
        "hard_min_sec": 60,
        "hard_max_sec": 100,
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

_JP_CHARS_PER_SEC: float = 4.5
_TARGET_CHARS = {k: round(v * _JP_CHARS_PER_SEC) for k, v in _DURATIONS.items()}


# ── LLM出力パース用スキーマ ───────────────────────────────────────────────────

class ScriptDraft(BaseModel):
    """LLMが生成するJSON全体をパースするための内部スキーマ。
    VideoScriptへの変換・文字数バリデーションに使用し、外部に公開しない。
    """
    # ── ディレクター思考 ─────────────────────────────────────────────────────
    director_thought: str = Field(
        description="事象の本質と選択した武器・仮想敵をどう叩くかの宣言（200字以内）"
    )
    target_enemy: str = Field(
        description="財務省/日銀・大手メディア・米国政府/中国共産党・GAFAM・既存秩序 等"
    )
    selected_pattern: str = Field(
        description="Breaking Shock / Media Critique / Geopolitics / Paradigm Shift / Anti-Sontaku / Cultural Divide"
    )
    loop_mechanism: str = Field(
        description="loop-1(冒頭伏線回収) / loop-2(未完結フック) / loop-3(冒頭単語回帰)"
    )
    # ── SEO・サムネ ──────────────────────────────────────────────────────────
    seo_keywords: dict[str, Any] = Field(
        description="{'primary': '主要検索語', 'secondary': ['副検索語1', '副検索語2']}"
    )
    thumbnail_text: dict[str, str] = Field(
        description="{'main': 'サムネ主文字10字以内', 'sub': 'サムネ副文字'}"
    )
    # ── Hook A/Bテスト候補 ───────────────────────────────────────────────────
    hook_variants: list[dict[str, str]] = Field(
        description="5類型から3つ選択。各18文字以内。[{'type':'A','label':'数字ショック','text':'...'},...] "
    )
    # ── 本文 ─────────────────────────────────────────────────────────────────
    setup: str = Field(description="事件の概要・建前（60〜90文字）")
    twist: str = Field(description="裏の文脈・構造を展開（150〜220文字）")
    punchline: str = Field(description="価値観を揺さぶる結末・loop_mechanism実装（70〜110文字）")
    # ── 視聴維持ピーク設計 ───────────────────────────────────────────────────
    peaks: dict[str, str] = Field(
        description="{'3s':'継続フック','7s':'具体的数字/固有名詞','15s':'第1のReveal','30s':'第2のReveal'}"
    )


# ── 文字数バリデーション ──────────────────────────────────────────────────────

def _count_chars(text: str) -> int:
    """空白・改行を除いた実文字数を返す。"""
    return len("".join(text.split()))


class _CharViolation:
    def __init__(self, field: str, actual: int, lo: int, hi: int) -> None:
        self.field = field
        self.actual = actual
        self.lo = lo
        self.hi = hi

    def correction_message(self) -> str:
        if self.actual > self.hi:
            diff = self.actual - self.hi
            return f"- {self.field}: 現在{self.actual}文字 → 目標{self.lo}〜{self.hi}文字（{diff}文字削ってください）"
        diff = self.lo - self.actual
        return f"- {self.field}: 現在{self.actual}文字 → 目標{self.lo}〜{self.hi}文字（{diff}文字増やしてください）"


_LOOP3_TOKEN_RE = re.compile(r"[一-龥ぁ-んァ-ヶ々ーA-Za-z]{2,}")


def _check_loop3_recurrence(draft: ScriptDraft) -> Optional[str]:
    """loop-3（冒頭単語回帰）のソフト検証。

    loop_mechanism=='loop-3' のとき hook の先頭キーワード（長さ2〜4のプレフィックス）が
    punchline に出現していなければ違反理由を返す（再生成はしない、WARNログ用）。
    日本語の助詞分割は簡易化のため、先頭2〜4字のいずれかが含まれていれば合格とする寛容判定。
    """
    if draft.loop_mechanism != "loop-3":
        return None
    hook_text = draft.hook_variants[0].get("text", "") if draft.hook_variants else ""
    if not hook_text:
        return "hook empty"
    m = _LOOP3_TOKEN_RE.search(hook_text)
    if not m:
        return None  # 数字のみ等で抽出不能 → ベネフィット・オブ・ザ・ダウト
    keyword = m.group()
    # 長いプレフィックスから順に確認（"NHKが言わない真実" → 先に4字→3字→2字）
    for prefix_len in (4, 3, 2):
        if len(keyword) >= prefix_len and keyword[:prefix_len] in draft.punchline:
            return None
    probe = keyword[: min(4, len(keyword))]
    return f"hook keyword prefix {probe!r} not found in punchline"


def _validate_draft_chars(draft: ScriptDraft) -> list[_CharViolation]:
    """hook/setup/twist/punchlineの文字数を検証し、違反リストを返す。空なら合格。

    hook は hook_variants[0].text（メイン採用される先頭候補）を対象とする。
    """
    violations: list[_CharViolation] = []
    for field, (lo, hi) in _CHAR_BOUNDS.items():
        if field == "hook":
            text = draft.hook_variants[0].get("text", "") if draft.hook_variants else ""
        else:
            text = getattr(draft, field, "")
        n = _count_chars(text)
        if not (lo <= n <= hi):
            violations.append(_CharViolation(field, n, lo, hi))
    return violations


def _build_correction_prompt(base_prompt: str, draft: ScriptDraft, violations: list[_CharViolation]) -> str:
    """文字数違反を具体的に示した修正リクエストプロンプトを返す。"""
    lines = ["以下のフィールドが文字数規定を逸脱しています。該当箇所のみ修正し、JSONをそのまま再出力してください。"]
    lines += [v.correction_message() for v in violations]
    lines += [
        "",
        "【修正ルール】",
        "- 違反フィールド以外は変更しないこと。",
        "- JSONのみを返すこと（前置き・説明不要）。",
        "",
        "## 前回の出力（参照用）",
        f"```json",
        json.dumps(draft.model_dump(), ensure_ascii=False, indent=2),
        "```",
    ]
    correction_instruction = "\n".join(lines)
    return f"{base_prompt}\n\n---\n## 🔁 修正指示\n{correction_instruction}"


# ── ユーティリティ ────────────────────────────────────────────────────────────

def _estimate_duration_sec(text: str) -> int:
    chars = len("".join(text.split()))
    return round(chars / _JP_CHARS_PER_SEC)


def _trim_to_fit(text: str, max_chars: int) -> str:
    cleaned_len = len("".join(text.split()))
    if cleaned_len <= max_chars:
        return text
    char_count = 0
    cut_pos = len(text)
    for i, ch in enumerate(text):
        if ch not in (" ", "\n", "\t", "\r"):
            char_count += 1
        if char_count >= max_chars:
            cut_pos = i + 1
            break
    last_kuten = text.rfind("。", 0, cut_pos)
    if last_kuten > int(cut_pos * 0.8):
        return text[:last_kuten + 1]
    return text[:cut_pos]


def _compress_sections(
    sections: list[ScriptSection],
    target_max_sec: int,
    estimated_sec: int,
) -> tuple[list[ScriptSection], int]:
    if estimated_sec <= target_max_sec:
        return sections, estimated_sec

    target_total_chars = int(target_max_sec * _JP_CHARS_PER_SEC)
    current_total = sum(len("".join(s.body.split())) for s in sections)
    if current_total == 0:
        return sections, estimated_sec

    excess = current_total - target_total_chars
    if excess <= 0:
        return sections, estimated_sec

    _COMPRESSIBLE = ("setup", "twist", "punchline")
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
        trim = int(excess * chars / compress_source_chars)
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


# ── システムプロンプト ────────────────────────────────────────────────────────
# {{EVIDENCE_WARNING}} / {{AUTHORITY_MENTION_INSTRUCTION}}
# / {{SELECTED_EVENT_JSON}} / {{TRIAGE_RESULT_JSON}} を呼び出し側で置換すること

_PROMPT_TEMPLATE = """\
あなたは、TikTok・YouTube Shorts 向けの知的ショート動画台本作家です。
目的は「点と点が繋がって霧が晴れる」という知的興奮（Intellectual High）を、約60秒・350〜400文字で届けることです。

## メディアのコンセプト
「このチャンネルを見ると、世界がいつもと違って見える」——煽りではなく、純粋な知的好奇心を満たすインテリジェンス・ショートメディア。

## ターゲット
20代後半〜40代の、知的好奇心が高く、世界の動きで損をしたくない日本人ビジネス層。

---

## STEP 1: ディレクター思考（台本を書く前に必ず実行）

`director_thought` フィールドに200字以内で以下を宣言せよ。
1. **この事象の本質** — 構造・権力・格差・価値観の衝突を一言で。
2. **`target_enemy`** — 財務省/日銀・大手メディア・米国政府/中国共産党・GAFAM・既存秩序 から選べ。視聴者が「そいつか！」と感じる仮想敵を明確にする。
3. **`selected_pattern`** — 以下の武器庫から最適な1つを選べ。選んだ理由と棄却理由を一言で。
4. **`loop_mechanism`** — loop-1(冒頭伏線回収) / loop-2(未完結フック) / loop-3(冒頭単語回帰) から選べ。

---

## STEP 2: 武器庫（6つの解説パターン）

選択は数値スコアではなく、**このニュースの本質・入力データの強み・視聴者の感情反応**で判断すること。組み合わせも可。

### [1] Breaking Shock（速報・歴史的スケール）
- **Hook**: 「たった今、〇〇の常識が崩壊しました」等。圧倒的な速報感・緊迫感で指を止める。
- **Twist**: この事態がどれほど異常か、過去のデータや歴史と比較してスケールを語る。「こんな数字は〇〇年ぶり」等。
- **Punchline**: 「明日からの〇〇に警戒してください」と具体的なアラートを鳴らして締める。

### [2] Media Critique（情報格差・メディア批判）
- **Hook**: 「なぜ日本のテレビはこれを報じないのか？」等。タブー感・情報格差への怒りで指を止める。
- **Twist**: 海外の熱狂/危機感と日本の無関心のギャップをデータで突きつける。「現地では〇〇万件の投稿」等。
- **Punchline**: 「情報鎖国ニッポン」への皮肉と、自衛のための情報収集の必要性で締める。

### [3] Geopolitics（地政学・多極的視点）
- **Hook**: 「裏で糸を引く真の黒幕は××です」等。善悪二元論を超えた「もう一つの真実」で指を止める。
- **Twist**: 対立陣営（中露・グローバルサウス等）から見た「彼らの正義」と資源・覇権争いを暴く。
- **Punchline**: 「これは正義ではなく、国益の衝突です」という冷徹な現実認識で締める。

### [4] Paradigm Shift（構造変化・時代の転換点）
- **Hook**: 「今日から〇〇のルールが変わりました」等。不可逆的な変化の節目感で指を止める。
- **Twist**: 旧時代の誰が没落し、誰が新覇権を握るか、勝者と敗者を具体的に語る。
- **Punchline**: 仕事・投資・生活への具体的なリスクまたはチャンスを1つだけ提示して締める。

### [5] Anti-Sontaku（アンチ忖度・権力の解剖）
- **Hook**: 「綺麗事抜きで言います。真の勝者は××です」等。建前を剥ぎ取る直球で指を止める。
- **Twist**: SDGs・平和・公平等の建前の裏で動く、生々しいカネと権力の流れを冷徹に指摘する。
- **Punchline**: 「綺麗事を信じた側が損をする世界で、あなたはどう動くか」というシニカルな問いで締める。

### [6] Cultural Divide（文化・価値観の断層）
- **Hook**: 「なぜ〇〇国でこんな異常な事件が起きるのか？」等。文化的ギャップへの驚きと好奇心で指を止める。
- **Twist**: 表層的な事件の奥にある、歴史・宗教・民族・制度という価値観の断層まで潜って解説する。
- **Punchline**: 「日本の常識で世界を測ってはいけない」という教訓で締める。

---

## STEP 3: アルゴリズム・ハック（必須実装）

### 【Hook 5類型 — A/Bテスト用3案を必ず作れ】
以下の5類型のうち3種類を選び `hook_variants` に格納せよ（各18文字以内）。
- **A: 数字ショック** — 最初の単語を数字にする（例:「3兆円。日本人の預金が...」）
- **B: 固有名詞否定** — 有名機関・人物を否定する（例:「NHKが言わない真実があります」）
- **C: カウントダウン** — 時限性で焦りを作る（例:「あと3日で〇〇が変わります」）
- **D: 逆説宣言** — 常識の逆を冒頭で言い切る（例:「円高は日本にとって損です」）
- **E: 名指し暴露** — 固有名詞で具体的に暴く（例:「〇〇省が隠していた数字」）

### 【ループ機構 — 2周目再視聴を設計せよ】
`loop_mechanism` に従い、Punchlineの最後を以下で締めること:
- **loop-1（冒頭伏線回収）**: Hookで仄めかした謎・伏線をPunchlineで「これがその答えです」と回収する。
- **loop-2（未完結フック）**: 「続きは次の動画で」「もう一つの真実がある」等で未完結感を残す。
- **loop-3（冒頭単語回帰）**: Hookの最初のキーワードをPunchlineの最後の文に再登場させる。

### 【SEOキーワード配置】
`seo_keywords.primary` をSetupのセリフ内に1回、`seo_keywords.secondary[0]` をTwistのセリフ内に1回、
自然な形で発話として組み込め（不自然なキーワード挿入は禁止）。

### 【視聴維持ピーク設計】
`peaks` に記した通り、各時間帯に引きがある要素を必ず配置せよ:
- 3秒: 継続フック（Hook終わりで「でも実は...」「しかし...」等の引き）
- 7秒: 具体的な数字または固有名詞（Setupの中で）
- 15秒: 第1のReveal（Twistの冒頭で視点を反転させる）
- 30秒: 第2のReveal（Twistの中盤で最大の「なぜ？」への答えを提示）

---

## STEP 4: 絶対ルール——ショート動画の黄金構成

| ブロック | 文字数 | 役割 |
|---------|--------|------|
| **hook** (hook_variants[0].text を使用) | 約20文字 | 指を止める1文。必ず1文完結。 |
| **setup** | **60〜90文字** | 前提・建前を事実のみで。推測禁止。 |
| **twist** | **150〜220文字** | 武器で視点をひっくり返す最大の見せ場。 |
| **punchline** | **70〜110文字** | シニカルで知的な結末。loop_mechanism必須。 |

**⚠️ 文字数は Python 側でハードチェックされます。範囲外の場合は自動リジェクトされ再生成を求められます。**

---

## STEP 4.5: 🚫 禁忌——Wikipedia 要約化の撲滅

**sections は記事の要約ではない。視聴者の世界観を揺さぶる『暴露と皮肉』の舞台である。**

### ❌ NG（要約型・教科書型）— 自動リジェクト対象
- setup: 「〇〇が△△を発表した。市場は反応した。」 ← 建前のみ、感情ゼロ
- twist: 「海外ではこの動きが注目されている。日本では報道が少ない。」 ← 事実の並列、構造不在
- punchline: 「今後の動向に注目したい。」 ← テレビのニュース閉め、loop機構も皮肉もない

### ✅ OK（暴露型・皮肉型）— 視聴者が二度見するやつ
- setup: 「公式発表は〇〇。NHKも日経もこの建前を繰り返しています。でも一歩引いて見てください。」 ← 建前を『建前』と名指しする意志
- twist: 「裏で動いているのは××という構造です。A国は〇〇という本音で、B国は△△という国益で動いている。日本のメディアが触れないのは、□□という空気があるからです。つまりこれは◯◯の覇権の話で、〇〇ではありません。」 ← 地政学/構造/仮想敵を具体的に暴く
- punchline: 「建前を信じた側が損をする。そして明日のニュースで、またあの単語を聞くことになります。」 ← シニカルな余韻 + loop機構

### 🔑 Twist 必達チェックリスト
- [ ] **構造が暴かれているか？** （単なる事実の列挙ではなく、「なぜこうなっているか」の仕組み）
- [ ] **target_enemy が存在感を持っているか？** （「誰がトクしているか」が見える）
- [ ] **地政学・カネ・権力のいずれかに踏み込んでいるか？** （綺麗事の一段下を見せる）
- [ ] **日本メディアが触れない理由まで言及したか？** （Media Critique を選んだ場合）

### 🔑 Punchline 必達チェックリスト
- [ ] **シニカルな知的余韻があるか？** （「〜に注目したい」等の無害な締めは禁止）
- [ ] **loop_mechanism が実装されているか？** （冒頭の伏線を回収／未完結／単語回帰）
- [ ] **視聴者の価値観を一度揺さぶるか？** （常識 → 反転 → 新しい視点）

## 文体ルール
- 1文は20字以内。句点で積極的に区切る。
- 話し言葉（「〜ですよね」「〜なんです」「実はこうなんです」）。
- 接続詞でテンポを作る（「でも」「だから」「つまり」「ここが重要で」）。
- 専門用語は必ず言い換える（例:「地政学的緊張」→「隣国同士の縄張り争い」）。
- 陰謀論的表現・過激な煽りは禁止。

## 根拠ルール
- gap_reasoning / japan_impact_reasoning が入力にある場合は優先参照する。
- 断定形は sources_jp / sources_en / sources_by_locale の報道内容を根拠とする場合のみ。
- 根拠のない推論は「〜とみられる」「〜という見方がある」で表現する。
- 事実は setup/twist 前半に、仮説は twist 後半に入れる。

---

## 出力形式
必ずJSONのみで返してください。前置きや説明は不要です。

{
  "director_thought": "事象の本質は〇〇。target_enemyは〇〇。武器[X]を選んだ理由は〜。loop_mechanismはloop-Xとする。（200字以内）",
  "target_enemy": "大手メディア",
  "selected_pattern": "Media Critique",
  "loop_mechanism": "loop-3",
  "seo_keywords": {
    "primary": "主要検索語",
    "secondary": ["副検索語1", "副検索語2"]
  },
  "thumbnail_text": {
    "main": "サムネ主文字（10字以内）",
    "sub": "サムネ副文字"
  },
  "hook_variants": [
    {"type": "B", "label": "固有名詞否定", "text": "NHKが言わない真実があります"},
    {"type": "A", "label": "数字ショック",  "text": "3兆円。今日から消えます。"},
    {"type": "D", "label": "逆説宣言",     "text": "円安は日本の勝利ではない。"}
  ],
  "setup": "事件の概要・世間の建前（60〜90文字）",
  "twist": "裏の文脈・構造を展開（150〜220文字）",
  "punchline": "価値観を揺さぶる結末、loop_mechanism実装（70〜110文字）",
  "peaks": {
    "3s":  "継続フック（Hook終わりの引き）",
    "7s":  "具体的数字か固有名詞",
    "15s": "第1のReveal",
    "30s": "第2のReveal"
  }
}

{{PATTERN_RESTRICTIONS}}
{{EVIDENCE_WARNING}}
{{AUTHORITY_MENTION_INSTRUCTION}}
## 入力データ
{{SELECTED_EVENT_JSON}}
{{TRIAGE_RESULT_JSON}}
"""


def _build_authority_mention_instruction(authority_pair: list[str]) -> str:
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
  - 台本全体（全セクション合計）で媒体名は最大2つまで

"""


_ALLEGATION_KW = [
    "疑惑", "インサイダー", "insider trading", "insider deal", "alleged", "allegation",
    "不正", "横領", "背任", "粉飾", "accounting fraud", "市場操作", "market manipulation",
    "容疑", "被疑", "捜査中", "under investigation",
]
_ALLEGATION_AUTH_SOURCES = [
    "reuters", "ap ", "afp", "associated press",
    "financial times", "wsj", "wall street journal",
    "new york times", "bloomberg", "nikkei", "日本経済新聞",
]


def _allegation_warning(event: NewsEvent) -> str:
    text = f"{(event.title or '').lower()} {(event.summary or '').lower()}"
    if not any(kw in text for kw in _ALLEGATION_KW):
        return ""
    source_lower = (event.source or "").lower()
    has_auth = any(s in source_lower for s in _ALLEGATION_AUTH_SOURCES)
    has_evidence = bool(event.sources_en or event.gap_reasoning)
    if has_auth and has_evidence:
        return ""
    return """
## ⚠️ 疑惑・未確認情報の警告【allegation-unverified】
このイベントには疑惑・未確認情報が含まれる可能性があります。以下を厳守すること:
- Reuters / AP / AFP / FT / WSJ / Bloomberg 等の権威ある一次ソースの明示的な裏付けがない限り、疑惑の内容を断言しない
- 「報道によると」「疑いがある」「当局が調査中とされる」など、未確定であることを必ず明示する
- insider trading / 不正 / 疑惑などの表現は推定形（「〜の疑いが報じられている」）のみ使用する
- script 内でこの疑惑を「確定事実」として断言してはならない
"""


def _pattern_restrictions_section(
    event: NewsEvent,
    triage_result: "Optional[ScoredEvent]" = None,
) -> str:
    """selected_pattern の候補から、証拠状況で整合しないものを除外する指示を返す。

    evidence_warning が twist 内容をガードするのと合わせ、そもそもパターン選択段階で
    禁止を明示することで「Media Critique を選んだのに海外比較が書けない」矛盾を防ぐ。
    """
    forbidden: list[tuple[str, str]] = []
    # 海外ソースは sources_en（後方互換）と sources_by_locale の non-japan エントリの和集合。
    # event_builder では country!=JP のソースは sources_en に入るが、テスト・将来の
    # 多地域ソース直接設定でも sources_by_locale 経由の海外ソースを認識できるようにする。
    has_overseas_locale = any(
        loc != "japan" and refs
        for loc, refs in (event.sources_by_locale or {}).items()
    )
    has_sources_en = bool(event.sources_en) or has_overseas_locale
    has_global_view = bool(event.global_view and event.global_view.strip())
    has_gap = bool(event.gap_reasoning)

    if not has_sources_en and not has_global_view:
        forbidden.append(
            ("Media Critique", "海外報道との比較が前提だが sources_en / global_view が不在")
        )
        forbidden.append(
            ("Geopolitics", "海外アクターの言説・視点の根拠が必要だが sources_en / global_view が不在")
        )
    elif not has_gap and not has_sources_en:
        forbidden.append(
            ("Media Critique", "海外との認識差（gap_reasoning）が未設定で、比較の切り口を断定できない")
        )

    if not forbidden:
        return ""

    lines = [
        "## ⚠️ パターン選択制約【pattern-candidate-restriction】",
        "以下のパターンは入力データの証拠不足により選択禁止。director_thought にも選ばないこと。",
    ]
    for name, reason in forbidden:
        lines.append(f"- **{name}** — {reason}")
    lines.append(
        "上記以外（Breaking Shock / Paradigm Shift / Anti-Sontaku / Cultural Divide 等）から必ず選ぶこと。"
    )
    return "\n".join(lines) + "\n"


def _evidence_warning_section(
    event: NewsEvent,
    triage_result: "Optional[ScoredEvent]" = None,
) -> str:
    allegation = _allegation_warning(event)
    has_sources_en = bool(event.sources_en)
    has_global_view = bool(event.global_view and event.global_view.strip())
    has_gap = bool(event.gap_reasoning)
    has_sources_jp = bool(event.sources_jp)
    has_impact = bool(event.impact_on_japan)
    has_bg = bool(event.background)

    bip = 0.0
    if triage_result is not None and triage_result.score_breakdown:
        bip = float(
            triage_result.score_breakdown.get("editorial:background_inference_potential", 0.0)
        )

    if not has_sources_en and not has_global_view:
        base = """
## ⚠️ エビデンス警告【EN-sources-absent】
このイベントには海外ソース・海外報道が確認されていません。以下を厳守すること:
- Twist セクションに「日本 vs 海外の報道差」や「海外の反応・評価」を書いてはならない
- 「現時点で十分な海外報道は確認できない」と台本内に明示すること
- 断定形・比較形・対比表現はすべて禁止
"""
        return allegation + base

    if not has_gap and bip < 2.0:
        base = """
## ⚠️ エビデンス警告【inference-absent】
日英の報道差に関する根拠（gap_reasoning）がなく、背景推論の余地が不十分です:
- Twist セクションで「なぜこの差が生まれるか」という背景仮説を書かない
- 比較・対比は「〜とみられる」「〜という見方もある」を必ずつける
"""
        return allegation + base

    if not has_gap and not has_sources_en:
        base = """
## ⚠️ エビデンス注意【perspective-weak】
gap_reasoning と sources_en が未設定です:
- 認識差の説明は推定表現のみで書く
- EN 媒体名・報道内容を具体的に引用しない
"""
        return allegation + base

    has_sources = has_sources_jp or has_sources_en
    strength = sum([has_sources, has_gap, has_impact, has_bg])

    if strength >= 3:
        return allegation

    if strength >= 1:
        base = """
## ⚠️ エビデンス注意（moderate）
入力データの証拠シグナルが一部不足しています:
- gap_reasoning が未設定のため、JP/EN の認識差は「〜とみられる」で表現する
- 断定形は sources に実際に記載のある内容にのみ使用する
"""
        return allegation + base

    base = """
## ⚠️ エビデンス警告（weak）
入力データの証拠シグナルが不十分です:
- ソース名・媒体名を断定的に引用しない
- JP/EN の認識差は必ず推定表現で書く
- Punchline は「影響が考えられる」「動向に注目したい」程度に留める
"""
    return allegation + base


def _validate_script(script: VideoScript) -> bool:
    if not script.sections:
        return False
    return all(bool(s.body and s.body.strip()) for s in script.sections)


def _parse_raw_json(raw: str) -> dict:
    """LLM出力からJSONを抽出・パースする。"""
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


def _draft_to_video_script(draft: ScriptDraft, event: NewsEvent) -> VideoScript:
    """ScriptDraft → VideoScript に変換する。hook は hook_variants[0] を採用。"""
    # hook_variants の先頭をメインhookとして採用
    hook_text = ""
    if draft.hook_variants:
        hook_text = draft.hook_variants[0].get("text", "")
    if not hook_text:
        hook_text = f"今、世界が動いています。"

    sections = [
        ScriptSection(heading="hook",      body=hook_text,       duration_sec=_DURATIONS["hook"]),
        ScriptSection(heading="setup",     body=draft.setup,     duration_sec=_DURATIONS["setup"]),
        ScriptSection(heading="twist",     body=draft.twist,     duration_sec=_DURATIONS["twist"]),
        ScriptSection(heading="punchline", body=draft.punchline, duration_sec=_DURATIONS["punchline"]),
    ]

    all_body = " ".join(s.body for s in sections)
    estimated = _estimate_duration_sec(all_body)
    profile = PLATFORM_PROFILES["shared"]

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
        title=event.title,
        intro="",
        sections=sections,
        outro="",
        total_duration_sec=sum(_DURATIONS.values()),
        target_duration_sec=profile["target_sec"],
        estimated_duration_sec=estimated,
        platform_profile="shared",
        # ── ディレクター思考メタデータを永続化（additive / 後続処理は無視しても可） ──
        director_thought=draft.director_thought,
        target_enemy=draft.target_enemy,
        selected_pattern=draft.selected_pattern,
        loop_mechanism=draft.loop_mechanism,
        seo_keywords=draft.seo_keywords,
        thumbnail_text_variants=draft.thumbnail_text,
        hook_variants=draft.hook_variants,
        peaks=draft.peaks,
    )


def _build_script_from_llm(
    client: LLMClient,
    event: NewsEvent,
    triage_result: Optional[ScoredEvent] = None,
    authority_pair: list[str] | None = None,
) -> tuple[VideoScript, int]:
    """Build script via LLM with char-count hard-validation and retry.

    Flow:
    1. Build base prompt.
    2. Call LLM → parse → validate char counts (Python hard check).
    3. If violations: inject correction message and retry (max _MAX_VALIDATION_RETRIES).
    4. On final failure: trim offending fields to bound, emit warning, accept.
    Returns (VideoScript, total_api_retry_count).
    """
    from src.llm.retry import call_with_retry

    event_json = event.model_dump_json(indent=2)
    triage_json = triage_result.model_dump_json(indent=2) if triage_result else "{}"
    evidence_warning = _evidence_warning_section(event, triage_result)
    authority_instruction = _build_authority_mention_instruction(authority_pair or [])
    pattern_restrictions = _pattern_restrictions_section(event, triage_result)

    base_prompt = (
        _PROMPT_TEMPLATE
        .replace("{{SELECTED_EVENT_JSON}}", event_json)
        .replace("{{TRIAGE_RESULT_JSON}}", triage_json)
        .replace("{{EVIDENCE_WARNING}}", evidence_warning)
        .replace("{{AUTHORITY_MENTION_INSTRUCTION}}", authority_instruction)
        .replace("{{PATTERN_RESTRICTIONS}}", pattern_restrictions)
    )

    current_prompt = base_prompt
    total_api_retries = 0
    last_draft: ScriptDraft | None = None

    try:
        for validation_attempt in range(_MAX_VALIDATION_RETRIES + 1):
            raw, api_retry_count = call_with_retry(
                lambda: client.generate(current_prompt), role="generation"
            )
            total_api_retries += api_retry_count

            if not raw or not raw.strip():
                raise ValueError("LLM returned None or empty string for script")

            data = _parse_raw_json(raw)

            # ── LLM の演出判断をログ出力 ────────────────────────────────────────
            dt = data.get("director_thought", "")
            if dt:
                logger.info(
                    f"[ScriptWriter] director_thought (attempt {validation_attempt + 1}): {dt[:200]}"
                )
            pat = data.get("selected_pattern", "")
            enemy = data.get("target_enemy", "")
            loop = data.get("loop_mechanism", "")
            if pat or enemy:
                logger.info(
                    f"[ScriptWriter] pattern={pat!r} enemy={enemy!r} loop={loop!r}"
                )

            # ── ScriptDraft パース ───────────────────────────────────────────────
            # 必須フィールドが欠けている場合は ValueError → call_with_retry の外側で捕捉
            try:
                draft = ScriptDraft(**data)
            except Exception as exc:
                raise ValueError(f"ScriptDraft parse error: {exc}") from exc

            last_draft = draft

            # ── 文字数ハードバリデーション ───────────────────────────────────────
            violations = _validate_draft_chars(draft)
            if not violations:
                hook_text = draft.hook_variants[0].get("text", "") if draft.hook_variants else ""
                logger.info(
                    f"[ScriptWriter] char validation passed "
                    f"(hook={_count_chars(hook_text)}, "
                    f"setup={_count_chars(draft.setup)}, "
                    f"twist={_count_chars(draft.twist)}, "
                    f"punchline={_count_chars(draft.punchline)})"
                )
                loop3_reason = _check_loop3_recurrence(draft)
                if loop3_reason:
                    logger.warning(
                        f"[ScriptWriter] loop-3 soft check failed: {loop3_reason} "
                        f"(hook={hook_text!r} / punchline tail={draft.punchline[-40:]!r})"
                    )
                break

            # 違反あり
            viol_summary = ", ".join(
                f"{v.field}={v.actual}字" for v in violations
            )
            if validation_attempt < _MAX_VALIDATION_RETRIES:
                logger.warning(
                    f"[ScriptWriter] char validation FAILED (attempt {validation_attempt + 1}/"
                    f"{_MAX_VALIDATION_RETRIES}): {viol_summary} — retrying with correction prompt"
                )
                current_prompt = _build_correction_prompt(base_prompt, draft, violations)
            else:
                # リトライ上限到達 → 強制採用（例外を出さず次の処理へ進む）
                logger.warning(
                    f"[ScriptWriter] 文字数調整失敗、そのまま採用 — "
                    f"{_MAX_VALIDATION_RETRIES} retries exhausted ({viol_summary}). "
                    f"Accepting best available draft without further correction."
                )
                break

    except Exception as exc:
        if last_draft is not None:
            logger.warning(
                f"[ScriptWriter] 文字数調整失敗、そのまま採用 — "
                f"exception during validation loop: {exc}. "
                f"Falling back to last available draft."
            )
        else:
            raise

    assert last_draft is not None
    return _draft_to_video_script(last_draft, event), total_api_retries


def _build_script_fallback(event: NewsEvent) -> VideoScript:
    """API失敗時の4ブロック構成テンプレートフォールバック。"""
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

    if has_en_evidence:
        hook_body = "日本と海外でこの出来事の受け止め方が、大きく異なっています。"
    else:
        hook_body = f"今、{category_theme}の構図が静かに変わっています。"

    setup_body = f"{event.summary[:85]}"

    if has_en_evidence and has_gap:
        twist_body = (
            f"日本メディアは{category_label}分野の出来事として報じた。"
            f"しかし海外では、{event.gap_reasoning[:80]}という文脈で語られているとみられる。"
            f"この温度差が、今後の動向を左右する可能性がある。"
        )
    elif has_en_evidence:
        global_summary = event.global_view or ""
        twist_body = (
            f"日本での報道は限られているが、"
            f"海外では{global_summary[:60]}という見方が広がっているとみられる。"
            f"この認識差が、{category_label}分野の今後に影響する可能性がある。"
        )
    else:
        twist_body = (
            f"現時点では海外報道の裏付けが十分ではない。"
            f"{category_label}分野における構造変化との関連が考えられるが、続報を待つ必要がある。"
        )

    if event.impact_on_japan:
        punchline_body = (
            f"{event.impact_on_japan[:75]}"
            "この視点を持っておくと、今後のニュースが違って見えるはずです。"
        )
    else:
        punchline_body = (
            f"国内の{category_label}関連の動向に引き続き注目が必要だ。"
            "これを知っておくだけで、次のニュースへの解像度が上がります。"
        )

    sections = [
        ScriptSection(heading="hook",      body=hook_body,      duration_sec=_DURATIONS["hook"]),
        ScriptSection(heading="setup",     body=setup_body,     duration_sec=_DURATIONS["setup"]),
        ScriptSection(heading="twist",     body=twist_body,     duration_sec=_DURATIONS["twist"]),
        ScriptSection(heading="punchline", body=punchline_body, duration_sec=_DURATIONS["punchline"]),
    ]

    total = sum(_DURATIONS.values())
    all_body = " ".join(s.body for s in sections)
    estimated = _estimate_duration_sec(all_body)
    profile = PLATFORM_PROFILES["shared"]

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
    """動画台本を生成する。

    LLMが利用可能な場合はScriptDraftスキーマで生成し、文字数ハードバリデーション後に
    VideoScriptへ変換する。失敗時はテンプレートにフォールバックする。
    目標尺: 約80秒（350〜400文字）

    Args:
        authority_pair: evidence.json に実在が確認済みの媒体名リスト（最大2件）。
    """
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
                script, _retry_count = _build_script_from_llm(
                    client, event, triage_result, authority_pair
                )
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

    if not _validate_script(script):
        raise ValueError(
            f"[ScriptWriter] empty_script: all fallbacks produced empty sections "
            f"for event_id={event.id}. Run marked as error."
        )

    if budget is not None:
        budget.record_generation_outcome("script", _used_fallback, _fallback_reason, _retry_count)

    # script の selected_pattern をタイトル生成に渡し、語り口とタイトルのトーンを揃える
    # （LLM 経路では script.selected_pattern が入る / fallback 経路では None → 従来挙動）
    title_layer = generate_title_layer(
        event, triage_result, selected_pattern=script.selected_pattern
    )
    return script.model_copy(update={"title_layer": title_layer})
