"""分析レイヤー Step 2: コンテキスト構築（LLM 呼び出しなし）。

設計書 Section 4.2 Step 2 の仕様に従う。
既存の event_builder のクラスタリング結果を信頼し、ScoredEvent.event の
記事メタデータと sources_by_locale から記事スニペットを抽出する。
関連記事の再検索は行わない。
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from src.shared.models import (
    ChannelConfig,
    PerspectiveCandidate,
    ScoredEvent,
    SourceRef,
)


class AnalysisContext(BaseModel):
    """Step 3〜5 の LLM プロンプトに渡されるコンテキスト。

    LLM 呼び出しなしで構築される純粋なプロンプト準備用データ。
    """

    event_id: str
    channel_id: str
    perspective_candidates: list[PerspectiveCandidate] = Field(default_factory=list)
    article_snippets: list[dict] = Field(default_factory=list)
    background_questions: list[str] = Field(default_factory=list)
    # 補助情報: 集約レベルのナラティブ（japan_view/global_view 等）
    event_summary: str = ""
    event_title: str = ""


# 観点軸ごとの背景質問テンプレート（LLM の検証ガイドに渡す）
_AXIS_BACKGROUND_QUESTIONS: dict[str, list[str]] = {
    "silence_gap": [
        "Are there truly zero Japanese-language sources covering this event in the cluster?",
        "If JP coverage is absent, what is the most likely reason (low news value to JP / language barrier / editorial avoidance)?",
        "What concrete evidence in the global sources signals high importance (scale, casualties, GDP impact, geopolitical shift)?",
    ],
    "framing_inversion": [
        "What is the subject and predicate divergence between Japanese and global sources?",
        "Is the contrast about 'who is the antagonist' or merely about emphasis?",
        "Which specific words or phrasings reveal the inversion?",
    ],
    "hidden_stakes": [
        "What is the causal chain from this event to Japanese industry, supply chains, or daily life?",
        "How many causal steps separate the event from a Japanese-perceptible impact?",
        "Which Japanese companies, sectors, or policy domains are most exposed?",
    ],
    "cultural_blindspot": [
        "Which cultural, religious, institutional, or normative axis differs between Japan and the source country?",
        "What does the foreign logic require the viewer to suspend or reconsider from a Japanese perspective?",
        "Is the contrast structural (rooted in institutions/history) or merely surface-level?",
    ],
}


def _snippet_from_source_ref(source: SourceRef, region: str) -> dict:
    """SourceRef を LLM 用の軽量スニペット dict に変換する。"""
    return {
        "region": region,
        "name": source.name,
        "url": source.url,
        "title": source.title or "",
        "language": source.language or "",
        "country": source.country or "",
    }


def _collect_article_snippets(scored_event: ScoredEvent) -> list[dict]:
    """ScoredEvent.event のソースから記事スニペットを抽出する。

    sources_by_locale を最優先（多地域）、なければ sources_jp / sources_en を使用。
    重複 URL は除外。
    """
    ev = scored_event.event
    snippets: list[dict] = []
    seen_urls: set[str] = set()

    if ev.sources_by_locale:
        for region, refs in ev.sources_by_locale.items():
            for ref in refs:
                if ref.url and ref.url in seen_urls:
                    continue
                if ref.url:
                    seen_urls.add(ref.url)
                snippets.append(_snippet_from_source_ref(ref, region))
    else:
        for ref in ev.sources_jp:
            if ref.url and ref.url in seen_urls:
                continue
            if ref.url:
                seen_urls.add(ref.url)
            snippets.append(_snippet_from_source_ref(ref, "japan"))
        for ref in ev.sources_en:
            if ref.url and ref.url in seen_urls:
                continue
            if ref.url:
                seen_urls.add(ref.url)
            snippets.append(_snippet_from_source_ref(ref, "global"))

    return snippets


def _build_background_questions(
    perspective_candidates: list[PerspectiveCandidate],
) -> list[str]:
    """観点候補の axis に対応する背景質問テンプレートを連結する。

    観点軸ごとに見出し付きで返すことで、LLM が候補ごとの検証ポイントを
    対応付けやすくする。
    """
    out: list[str] = []
    seen_axes: set[str] = set()
    for cand in perspective_candidates:
        if cand.axis in seen_axes:
            continue
        seen_axes.add(cand.axis)
        questions = _AXIS_BACKGROUND_QUESTIONS.get(cand.axis, [])
        if not questions:
            continue
        out.append(f"[{cand.axis}]")
        for q in questions:
            out.append(f"- {q}")
    return out


def build_analysis_context(
    scored_event: ScoredEvent,
    perspective_candidates: list[PerspectiveCandidate],
    channel_config: Optional[ChannelConfig] = None,
) -> AnalysisContext:
    """Step 3〜5 の LLM プロンプトに渡す AnalysisContext を構築する。

    LLM 呼び出しは行わない。関連記事の再検索もしない（既存 event_builder の
    クラスタリング結果を信頼）。

    Args:
        scored_event: 分析対象のイベント。
        perspective_candidates: ルールベース抽出済みの観点候補（呼び出し側で Top3 に絞り済み想定）。
        channel_config: 現状は channel_id を取り出すためだけに使う（None なら ScoredEvent.channel_id）。

    Returns:
        AnalysisContext: プロンプト準備用データ。
    """
    channel_id = (
        channel_config.channel_id if channel_config is not None else scored_event.channel_id
    )
    snippets = _collect_article_snippets(scored_event)
    questions = _build_background_questions(perspective_candidates)
    return AnalysisContext(
        event_id=scored_event.event.id,
        channel_id=channel_id,
        perspective_candidates=list(perspective_candidates),
        article_snippets=snippets,
        background_questions=questions,
        event_summary=scored_event.event.summary or "",
        event_title=scored_event.event.title or "",
    )
