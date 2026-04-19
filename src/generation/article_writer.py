from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.llm.base import LLMClient
from src.llm.factory import get_article_llm_client
from src.shared.config import LLM_PROVIDER
from src.shared.logger import get_logger
from src.shared.models import NewsEvent, ScoredEvent, VideoScript, WebArticle

if TYPE_CHECKING:
    from src.budget import BudgetTracker

logger = get_logger(__name__)

# 記事生成プロンプト
# 呼び出し側で {{SELECTED_EVENT_JSON}}, {{TRIAGE_RESULT_JSON}}, {{VIDEO_SCRIPT_JSON}} を
# .replace() で置換すること
_PROMPT_TEMPLATE = """\
あなたは、グローバルニュースを日本向けに再解釈する編集者です。
目的は、ショート動画の内容を補完し、読者が「なぜこのニュースが重要なのか」を文章で理解できるようにすることです。

## メディアのコンセプト
日本の報道では見えない「世界との認識差」を、短時間で理解できる知的メディア。

## 記事の役割
- 動画の内容をテキストで補完する
- 日本と海外の報道の差を、文章でより明確にする
- 背景構造を1段深く説明する
- 元ソースが分かる形で信頼性を担保する

## 文体
- 日本語
- わかりやすいが薄くない
- 知的で落ち着いたトーン
- SEOっぽいだけの空疎な文章は禁止
- 誇張や陰謀論は禁止
- 断定しすぎない
- 「〜かもしれない」「〜とみられる」を適切に使う

## 根拠ルール（必須）
- 断定形で書く文は、必ず入力の sources_jp または sources_en の報道内容を根拠とすること
- 元記事に記載のない推論は「〜とみられる」「〜という見方もある」「〜と指摘する声もある」で表現する
- gap_reasoning が入力にある場合は、日本と海外の差の説明に活用すること
- japan_impact_reasoning が入力にある場合は、日本への影響説明の根拠として参照すること
- 根拠不明の断定は記事の信頼性を損なうため、絶対に避ける

## 構成（Facts → Hypothesis → Implications の3層構造）
必ず以下の見出し構成にしてください。
このメディアの価値は「報道差から背景仮説を読み解くこと」です。単なるニュース要約は不可。

1. H1 title
- 記事タイトル
- 動画タイトルより少し固め
- 検索にも耐えやすい自然な日本語

2. TL;DR
- 箇条書き3点
- 忙しい人向けに要点だけまとめる

3. ## 事実：日本と世界の報道差（Facts）
- どの媒体が何をどう報じたか
- 日本と海外の論点差・評価差・責任主体の差・見落としを具体的に示す
- 「Financial Timesは〜と報じた」「NHKは〜を中心に伝えた」のように媒体名を明示する
- ここは「事実」として書く: 推測・仮説を含まない

4. ## 背景仮説：なぜこの差が生まれるか（Hypothesis）
- 上記の「事実の差」がなぜ生まれるのかを、推論として説明する
- 文化・制度・地政学・経済合理性・歴史的経緯・産業構造などから仮説を立てる
- 元記事に明示されていなくても、報道差の構造から自然に導ける仮説なら書いてよい
- 【重要】必ず推定表現を使うこと:
  「〜という仮説が立てられます」
  「〜が影響している可能性があります」
  「報道の差を見る限り、〜という見方が考えられます」
  「〜と指摘する声もあります」
- 断定しない。事実と仮説を混ぜない。陰謀論・誹謗中傷は禁止

5. ## 含意：あなたへの意味（Implications）
- この差・この仮説が読者にとって何を意味するか
- 生活・仕事・投資・企業・政策など、具体的な接続を示す
- 今後どこを注視すべきかを示す
- 煽りすぎない。余韻を残す

6. ## Sources
- 入力の sources_jp と sources_en に含まれる媒体名とURLのみを使うこと
- 勝手に新しいURLを捏造しない
- 形式: `- [媒体名](URL)` のMarkdownリンク形式で列挙
- sources_jp を先に、sources_en を後に並べる
- ソース情報が空の場合のみ「ソース情報なし」と記載

## 必ず含めること
- 単なるニュース要約で終わらない
- 日本と海外の「事実の差」をはっきり示す
- 差の背景仮説を推定表現で1段深く書く
- 含意・今後の注視ポイントで締める

## 入力
以下に、選ばれたイベント情報、トリアージ結果、動画台本を渡します。
入力の sources_jp（日本語媒体リスト）と sources_en（英語媒体リスト）に含まれるURLと媒体名を、Sourcesセクションにそのまま使うこと。

## 出力形式
Markdown本文のみを返してください。前置き不要です。

{{EVIDENCE_WARNING}}
## 入力データ
{{SELECTED_EVENT_JSON}}
{{TRIAGE_RESULT_JSON}}
{{VIDEO_SCRIPT_JSON}}
"""


# 疑惑・未確認情報の検出キーワード（script_writer と共通）
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
    """疑惑・未確認情報を含む場合に警告文を返す。権威ソース+証拠が揃っていれば空文字列。"""
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
- 訴訟・刑事事件の段階（「疑い」「調査中」「起訴」「有罪判決」）を正確に区別し、混同しない
- 記事内でこの疑惑を「確定事実」として断言してはならない
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
- 「事実：日本と世界の報道差」セクションに「海外の反応・評価・報道内容」を書いてはならない
- 「背景仮説」セクションで「海外での見方」「欧米の視点」「グローバルな文脈」を推測で補完しない
- 「現時点で十分な海外報道は確認できない」と記事内に明示すること
- 断定形・比較形はすべて禁止。海外メディア名を根拠なく引用しない
- 「含意」セクションは「動向を注視している」「影響が出る可能性がある」程度に留めること
"""
        return allegation + base

    # ── 条件 2: 背景推論の根拠が存在しない ──────────────────────────────────
    if not has_gap and bip < 2.0:
        base = """
## ⚠️ エビデンス警告【inference-absent】
日英の報道差に関する根拠（gap_reasoning）がなく、背景推論の余地が不十分です:
- 「背景仮説」セクションで「なぜこの差が生まれるか」という仮説を書かない
- 「この時点では強い比較仮説は置けない」と明示すること
- 「事実：報道差」セクションは事実の記述に留め、構造的解釈を加えない
- 比較・対比は「〜とみられる」「〜という見方もある」を必ずつける
- 「含意」セクションは「今後の動向に注視が必要」「影響の可能性がある」程度に留める
"""
        return allegation + base

    # ── 条件 3: perspective_conflict が弱い（sources_en なし + gap_reasoning なし）──
    if not has_gap and not has_sources_en:
        base = """
## ⚠️ エビデンス注意【perspective-weak】
gap_reasoning と sources_en が未設定です:
- 認識差の説明は推定表現のみ（「〜とみられる」「〜という見方もある」「〜と指摘する声もある」）で書く
- 「背景仮説」の内容は「可能性がある」「示唆される」程度に留める
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
- gap_reasoning が未設定の場合、認識差の説明は「〜とみられる」「〜という指摘もある」で表現する
- japan_impact_reasoning が未設定の場合、日本への影響は「〜が懸念される」「注視が必要」程度に留める
- 断定形は入力 sources_jp/sources_en に実際に記載のある内容にのみ使用する
"""
        return allegation + base

    base = """
## ⚠️ エビデンス警告（weak）
入力データの証拠シグナルが不十分です。以下のルールを厳守すること:
- sources が不完全なため、媒体名を「〜と報じている模様だ」「〜が伝えているとされる」のように間接表現にする
- JP/EN の認識差は推定前置きを必ずつける（「〜とみられる」「〜という見方もある」）
- 日本への影響は「〜が考えられる」「影響が出る可能性がある」程度に留め、断言しない
- Deep Dive セクションも構造的推論が弱いため、確定情報と推測を明示的に区別して書く
"""
    return allegation + base


def _validate_article(article: WebArticle) -> bool:
    """Return True if the article has non-empty markdown content."""
    return bool(article.markdown and article.markdown.strip())


def _build_article_from_llm(
    client: LLMClient,
    event: NewsEvent,
    triage_result: Optional[ScoredEvent] = None,
    video_script: Optional[VideoScript] = None,
) -> tuple[WebArticle, int]:
    """Build article via LLM. Returns (WebArticle, retry_count)."""
    from src.llm.retry import call_with_retry

    event_json = event.model_dump_json(indent=2)
    triage_json = triage_result.model_dump_json(indent=2) if triage_result else "{}"
    script_json = video_script.model_dump_json(indent=2) if video_script else "{}"
    evidence_warning = _evidence_warning_section(event, triage_result)

    prompt = (
        _PROMPT_TEMPLATE
        .replace("{{SELECTED_EVENT_JSON}}", event_json)
        .replace("{{TRIAGE_RESULT_JSON}}", triage_json)
        .replace("{{VIDEO_SCRIPT_JSON}}", script_json)
        .replace("{{EVIDENCE_WARNING}}", evidence_warning)
    )

    markdown, retry_count = call_with_retry(lambda: client.generate(prompt), role="generation")

    if not markdown or not markdown.strip():
        raise ValueError("LLM returned None or empty string for article")

    # コードブロックで囲まれていれば除去
    if markdown.startswith("```"):
        markdown = markdown.split("```")[1]
        if markdown.startswith("markdown") or markdown.startswith("md"):
            markdown = markdown.split("\n", 1)[1] if "\n" in markdown else markdown
        markdown = markdown.strip()

    if not markdown.startswith("# "):
        raise ValueError("Generated article does not start with H1 heading")

    word_count = len(markdown.replace("\n", "").replace(" ", ""))
    return WebArticle(
        event_id=event.id,
        title=event.title,
        markdown=markdown,
        word_count=word_count,
    ), retry_count


def _build_article_fallback(event: NewsEvent) -> WebArticle:
    """API失敗時のテンプレートフォールバック。

    EN ソース・global_view が存在しない場合は、海外比較・推論を生成しない。
    """
    pub = event.published_at.strftime("%Y年%m月%d日 %H:%M")

    has_en_evidence = bool(event.global_view or event.sources_en)
    has_gap = bool(event.gap_reasoning)

    md_lines = [
        f"# {event.title}",
        "",
        "## TL;DR",
        "",
        f"- {event.summary}",
    ]

    if has_en_evidence:
        md_lines.append(f"- 日本と海外で報道の切り口に差がある可能性がある")
    else:
        md_lines.append(f"- 現時点で海外報道は確認できていない")

    if event.impact_on_japan:
        md_lines.append(f"- {event.impact_on_japan[:80]}")
    else:
        md_lines.append(f"- 今後の動向と日本への影響を注視する必要がある")

    md_lines += [
        "",
        f"> **ソース**: {event.source} / **公開日時**: {pub} / **カテゴリ**: {event.category}",
        "",
        "## 事実：日本と世界の報道差",
        "",
    ]

    if has_en_evidence:
        jp_summary = event.japan_view or event.summary
        en_summary = event.global_view or ""
        md_lines.append(
            f"日本では、{jp_summary[:120]}という形で報じられた。"
        )
        if en_summary:
            md_lines.append(
                f"\n海外では「{en_summary[:120]}…」という文脈で伝えられているとみられる。"
                "ただし構造化されたソース情報が限られており、詳細な比較には続報が必要だ。"
            )
        else:
            md_lines.append("\n海外報道との詳細な比較は、現時点では限られた情報しかない。")
    else:
        jp_summary = event.japan_view or event.summary
        md_lines.append(
            f"{event.source}は「{jp_summary[:150]}」と報じた。"
            "\n\n現時点で十分な海外報道は確認できない。日本国内の報道をもとに状況を整理する段階だ。"
        )

    md_lines += ["", "## 背景仮説：なぜこの差が生まれるか", ""]

    if has_gap:
        md_lines.append(
            f"{event.gap_reasoning}\n\n"
            "ただしこれは報道差から推測される仮説であり、断定ではない。"
        )
    elif has_en_evidence:
        md_lines.append(
            "報道差の背景については、現時点では具体的な根拠が十分ではない。"
            f"\n{event.category}分野における構造変化との関連が考えられるが、この段階では強い仮説は置けない。"
            "\n続報や一次情報が出てから改めて分析が必要だ。"
        )
    else:
        md_lines.append(
            "海外報道が確認できていないため、現時点では比較仮説を立てることができない。"
            "\n今後、海外メディアの報道が出た時点で改めて分析する。"
        )

    md_lines += ["", "## 含意：あなたへの意味", ""]

    if event.impact_on_japan:
        md_lines.append(event.impact_on_japan)
    else:
        md_lines.append(
            f"{event.category}分野における今後の動向を注視する必要がある。"
            "\n特に政策・規制・市場への影響が出た場合は、速報で追う。"
        )

    md_lines += ["", "## Sources", ""]

    if event.sources_jp:
        md_lines.append("**日本語メディア**")
        for s in event.sources_jp:
            md_lines.append(f"- [{s.name}]({s.url})")
        md_lines.append("")
    if event.sources_en:
        md_lines.append("**海外メディア**")
        for s in event.sources_en:
            md_lines.append(f"- [{s.name}]({s.url})")
        md_lines.append("")
    if not event.sources_jp and not event.sources_en:
        md_lines.append(f"- {event.source} ({pub})")

    md_lines += [
        "",
        f"- イベントID: `{event.id}`",
        "",
        "---",
        "",
        "*この記事は Hydrangea News PoC によって自動生成されました。*",
    ]

    markdown = "\n".join(md_lines)
    word_count = len(markdown.replace("\n", "").replace(" ", ""))
    return WebArticle(
        event_id=event.id,
        title=event.title,
        markdown=markdown,
        word_count=word_count,
    )


def write_article(
    event: NewsEvent,
    triage_result: Optional[ScoredEvent] = None,
    video_script: Optional[VideoScript] = None,
    budget: "BudgetTracker | None" = None,
) -> WebArticle:
    """
    Web記事Markdownを生成する。LLM_PROVIDER のクライアントが利用可能な場合はそちらを使用し、
    失敗時はテンプレートにフォールバックする。
    budget が指定された場合、残量不足ならフォールバックを使用する。
    """
    logger.info(f"Generating article for event [{event.id}] via provider={LLM_PROVIDER}")

    _used_fallback = False
    _fallback_reason: str | None = None
    _retry_count = 0
    article: WebArticle | None = None

    # 予算チェック
    if budget is not None and not budget.can_use_article_llm():
        budget.skip("article_llm")
        _used_fallback = True
        _fallback_reason = "budget_exhausted"
    else:
        client = get_article_llm_client()
        if client is None:
            _used_fallback = True
            _fallback_reason = "no_client"
        else:
            try:
                article, _retry_count = _build_article_from_llm(client, event, triage_result, video_script)
                if budget is not None:
                    budget.record_call("article")
                logger.info(
                    f"Article generated via {LLM_PROVIDER}: {article.word_count} chars, "
                    f"retries={_retry_count}"
                )
            except Exception as e:
                logger.warning(
                    f"{LLM_PROVIDER} article generation failed (retries={_retry_count}), "
                    f"falling back to template: {e}"
                )
                _used_fallback = True
                _fallback_reason = f"llm_error:{type(e).__name__}"

    if _used_fallback or article is None:
        article = _build_article_fallback(event)
        logger.info(
            f"Article generated via fallback ({_fallback_reason}): {article.word_count} chars"
        )

    # Fail-safe: never save empty article content
    if not _validate_article(article):
        raise ValueError(
            f"[ArticleWriter] empty_article: all fallbacks produced empty content "
            f"for event_id={event.id}. Run marked as error."
        )

    if budget is not None:
        budget.record_generation_outcome("article", _used_fallback, _fallback_reason, _retry_count)

    return article
