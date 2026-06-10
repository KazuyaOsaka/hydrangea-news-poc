"""F-editorial-guardian-corroboration (1-T.2): 真実性検証 (corroboration) の検証。

src/generation/editorial_guardian_corroboration.py を fake genai client +
LLM mock で決定的に検証する (実 LLM / 実ネットワーク呼び出しなし):
  - 証拠収集 (GroundingSearchClient): 実ドメイン抽出 (chunk.web.title 由来、
    redirect URL は使わない = F-13.B 知見)、クエリ単位の失敗記録、usage 集計
  - 検索と判定の分離: 検索モデルは証拠の運搬係、判定は Guardian 単一モデル
  - truthfulness 語彙: corroborated / contradicted / uncorroborated +
    harness 値 unverified (検索 or 判定が完了しなかった、≠ 虚偽)
  - 第2層の対象選別: supported / not_in_source のみ。第1層 contradicted /
    unverified は skip (pending のまま、skip 理由を notes に記録)
  - ★ 独立性の deterministic 安全網: 元ソースドメインのみ / 証拠に無いドメイン
    を根拠にした corroborated は harness が uncorroborated に倒す
  - ★ 公開可否バー: flag されないのは supported かつ corroborated のみ
  - ★ 沈黙的劣化の禁止: judge 不可は unverified (検証未完) を明示、下位モデルで
    判定を続行しない
  - enrichment 設計: 入力レポート不変 (deep copy) + schema_version=2 + round-trip

正典: docs/ADR/0003-content-moral-guidelines.md「公開前検証」(複数ソース突合)。
"""
from __future__ import annotations

import json
import time

import pytest

from src.generation.editorial_guardian import (
    FAITHFULNESS_CONTRADICTED,
    FAITHFULNESS_NOT_IN_SOURCE,
    FAITHFULNESS_SUPPORTED,
    FAITHFULNESS_UNVERIFIED,
    TRUTHFULNESS_CONTRADICTED,
    TRUTHFULNESS_CORROBORATED,
    TRUTHFULNESS_PENDING,
    TRUTHFULNESS_UNCORROBORATED,
    TRUTHFULNESS_UNVERIFIED,
    ClaimVerification,
    CorroborationEvidence,
    EditorialGuardianReport,
    HighRiskClaim,
    VerificationQuery,
)
from src.generation.editorial_guardian_corroboration import (
    ENRICHED_SCHEMA_VERSION,
    GroundingSearchClient,
    _build_evidence_block,
    _call_with_timeout,
    _coerce_truthfulness,
    _domain_matches_hierarchy,
    _extract_domain_from_chunk,
    _looks_like_domain,
    _normalize_domain,
    _normalize_source_domains,
    _validated_independent_domains,
    corroborate_report,
)


# ---------- fake genai client (grounded 検索のスタブ) ----------

class _FakeWeb:
    def __init__(self, title=None, uri=None, domain=None):
        self.title = title
        self.uri = uri
        self.domain = domain


class _FakeChunk:
    def __init__(self, web):
        self.web = web


class _FakeMeta:
    def __init__(self, chunks):
        self.grounding_chunks = chunks


class _FakePart:
    def __init__(self, text):
        self.text = text


class _FakeContent:
    def __init__(self, parts):
        self.parts = parts


class _FakeCandidate:
    def __init__(self, metadata, content):
        self.grounding_metadata = metadata
        self.content = content


class _FakeUsage:
    def __init__(self, prompt=10, candidates=20, total=30):
        self.prompt_token_count = prompt
        self.candidates_token_count = candidates
        self.total_token_count = total


class _FakeResponse:
    def __init__(self, domains=(), text="", uris=(), usage=None):
        chunks = []
        uris = list(uris) or [None] * len(tuple(domains))
        for d, u in zip(tuple(domains), uris):
            chunks.append(_FakeChunk(_FakeWeb(title=d, uri=u)))
        self.candidates = [
            _FakeCandidate(_FakeMeta(chunks), _FakeContent([_FakePart(text)]))
        ]
        self.usage_metadata = usage


class _FakeModels:
    """generate_content の呼び出しを記録し、応答列 (or 例外) を順に返す。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _FakeGenAI:
    def __init__(self, responses):
        self.models = _FakeModels(responses)


def _grounding(responses, **kwargs):
    """テスト用 GroundingSearchClient (ネットワークなし = redirect 解決オフ)。"""
    kwargs.setdefault("resolve_redirects", False)
    kwargs.setdefault("model", "fake-grounding-model")
    return GroundingSearchClient(_FakeGenAI(responses), **kwargs)


# ---------- LLM judge mock ----------

class _JudgeLLM:
    """呼び出し順に固定応答 (str or Exception) を返す Guardian judge mock。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _judge_json(status, *, claim_id="c1", domains=(), reasoning="theory"):
    return json.dumps(
        {
            "claim_id": claim_id,
            "status": status,
            "reasoning": reasoning,
            "corroborating_domains": list(domains),
            "contradicting_domains": [],
        }
    )


# ---------- レポートフィクスチャ ----------

def _claim(cid, faithfulness, *, n_queries=1):
    return ClaimVerification(
        claim=HighRiskClaim(
            claim_id=cid,
            claim_text=f"claim text {cid}",
            artifact="article",
            risk_category="figure",
        ),
        faithfulness_status=faithfulness,
        faithfulness_reasoning=f"reasoning {cid}",
        verification_queries=[
            VerificationQuery(query=f"query {cid} #{i}", locale="en", purpose="check")
            for i in range(n_queries)
        ],
    )


def _report(claims) -> EditorialGuardianReport:
    return EditorialGuardianReport(
        event_id="cls-test",
        guardian_model_used="gemini-3.1-pro-preview",
        claims=list(claims),
        flagged_claims=[
            cv.claim.claim_id
            for cv in claims
            if cv.faithfulness_status != FAITHFULNESS_SUPPORTED
        ],
    )


# ---------- ドメインヘルパ (同形再実装の挙動固定) ----------

class TestDomainHelpers:
    def test_looks_like_domain(self):
        assert _looks_like_domain("jiji.com")
        assert _looks_like_domain("jetro.go.jp")
        assert not _looks_like_domain("Jiji News")
        assert not _looks_like_domain("https://jiji.com/article/123")
        assert not _looks_like_domain("")

    def test_normalize_domain(self):
        assert _normalize_domain("Jiji.com") == "jiji.com"
        assert _normalize_domain("https://jiji.com/article/123") == "jiji.com"
        assert _normalize_domain("  jetro.go.jp  ") == "jetro.go.jp"

    def test_domain_matches_hierarchy(self):
        assert _domain_matches_hierarchy("www.aljazeera.com", "aljazeera.com")
        assert _domain_matches_hierarchy("aljazeera.com", "www.aljazeera.com")
        assert _domain_matches_hierarchy("aljazeera.com", "aljazeera.com")
        assert not _domain_matches_hierarchy("not-nikkei.com", "nikkei.com")
        assert not _domain_matches_hierarchy("", "nikkei.com")

    def test_extract_domain_from_chunk_title(self):
        # CP-1 仮説2 実測: 実ドメインは web.title、web.domain は None
        chunk = _FakeChunk(_FakeWeb(title="middleeasteye.net", uri="https://vertexaisearch.cloud.google.com/x"))
        assert _extract_domain_from_chunk(chunk) == "middleeasteye.net"

    def test_extract_domain_prefers_domain_field(self):
        chunk = _FakeChunk(_FakeWeb(title="Some Title", domain="Reuters.com"))
        assert _extract_domain_from_chunk(chunk) == "reuters.com"

    def test_extract_domain_rejects_non_domain_title(self):
        chunk = _FakeChunk(_FakeWeb(title="Reuters News Article"))
        assert _extract_domain_from_chunk(chunk) is None
        assert _extract_domain_from_chunk(_FakeChunk(None)) is None

    def test_normalize_source_domains(self):
        out = _normalize_source_domains(
            ["https://www.middleeasteye.net/news/x", "aljazeera.com", "", "aljazeera.com"]
        )
        assert out == ["www.middleeasteye.net", "aljazeera.com"]


class TestCallWithTimeout:
    def test_returns_value(self):
        assert _call_with_timeout(lambda: 42, 5.0) == 42

    def test_raises_timeout(self):
        with pytest.raises(TimeoutError):
            _call_with_timeout(lambda: time.sleep(0.5), 0.05)


# ---------- 証拠収集 (GroundingSearchClient) ----------

class TestGroundingSearchClient:
    def test_search_collects_domains_and_text(self):
        client = _grounding(
            [
                _FakeResponse(
                    domains=("independent.co.uk", "middleeasteye.net", "independent.co.uk"),
                    text="Independent outlets report the seizure.",
                    usage=_FakeUsage(),
                )
            ]
        )
        q = VerificationQuery(query="castle seizure", locale="en", purpose="verify")
        ev = client.search(q, "claim text")
        assert ev.error == ""
        assert ev.domains == ["independent.co.uk", "middleeasteye.net"]  # dedupe
        assert ev.titles == ["independent.co.uk", "middleeasteye.net"]
        assert ev.response_text == "Independent outlets report the seizure."
        assert ev.query == "castle seizure"
        assert ev.locale == "en"
        # 検索 prompt は claim + クエリを含み、判定はさせない (運搬係の規律)
        prompt = client.genai_client.models.calls[0]["contents"]
        assert "claim text" in prompt
        assert "castle seizure" in prompt
        assert "判定はしないでください" in prompt

    def test_search_uses_configured_model(self):
        client = _grounding([_FakeResponse(text="x")], model="my-light-model")
        client.search(VerificationQuery(query="q"), "c")
        assert client.genai_client.models.calls[0]["model"] == "my-light-model"

    def test_search_records_usage(self):
        client = _grounding(
            [
                _FakeResponse(text="a", usage=_FakeUsage(10, 20, 30)),
                _FakeResponse(text="b", usage=_FakeUsage(1, 2, 3)),
            ]
        )
        client.search(VerificationQuery(query="q1"), "c")
        client.search(VerificationQuery(query="q2"), "c")
        assert client.usage == {
            "calls": 2,
            "prompt_tokens": 11,
            "candidates_tokens": 22,
            "total_tokens": 33,
        }

    def test_search_failure_recorded_per_query(self):
        client = _grounding([RuntimeError("api down")])
        ev = client.search(VerificationQuery(query="q"), "c")
        assert "RuntimeError" in ev.error
        assert ev.domains == []
        assert client.usage["calls"] == 0

    def test_search_without_client_records_error(self):
        client = GroundingSearchClient(None, model="m", resolve_redirects=False)
        ev = client.search(VerificationQuery(query="q"), "c")
        assert "not configured" in ev.error

    def test_default_model_from_config(self):
        client = GroundingSearchClient(_FakeGenAI([]), resolve_redirects=False)
        # config default (GUARDIAN_GROUNDING_MODEL) が使われる
        assert client.model


# ---------- 判定 (corroborate_report) ----------

def _run(report, judge_responses, grounding_responses, *, source_domains=("middleeasteye.net",)):
    judge = _JudgeLLM(judge_responses)
    grounding = _grounding(grounding_responses)
    enriched = corroborate_report(
        report,
        source_domains=list(source_domains),
        grounding_client=grounding,
        guardian_client=judge,
    )
    return enriched, judge, grounding


class TestCorroborateReport:
    def test_corroborated_with_independent_domain(self):
        report = _report([_claim("c1", FAITHFULNESS_SUPPORTED)])
        enriched, judge, _ = _run(
            report,
            [_judge_json("corroborated", domains=["independent.co.uk"])],
            [_FakeResponse(domains=("independent.co.uk", "middleeasteye.net"), text="evidence")],
        )
        cv = enriched.claims[0]
        assert cv.truthfulness_status == TRUTHFULNESS_CORROBORATED
        assert cv.corroborating_domains == ["independent.co.uk"]
        assert cv.truthfulness_reasoning == "theory"
        assert cv.truthfulness_verified_at != ""
        assert len(cv.truthfulness_evidence) == 1
        # 公開可否バー: supported × corroborated → 非 flag
        assert enriched.flagged_claims == []
        assert enriched.schema_version == ENRICHED_SCHEMA_VERSION
        s = enriched.truthfulness_summary
        assert s is not None
        assert s.n_corroborated == 1
        assert s.judge_model_used == "(injected)"
        assert s.grounding_model_used == "fake-grounding-model"
        # judge プロンプトに証拠・元ソース・第1層結果が束ねられている
        assert "independent.co.uk" in judge.prompts[0]
        assert "middleeasteye.net" in judge.prompts[0]
        assert "supported" in judge.prompts[0]

    def test_independence_safety_net_source_domain_only(self):
        # ★ judge が元ソースのみを根拠に corroborated → harness が uncorroborated に倒す
        report = _report([_claim("c1", FAITHFULNESS_SUPPORTED)])
        enriched, _, _ = _run(
            report,
            [_judge_json("corroborated", domains=["www.middleeasteye.net"])],
            [_FakeResponse(domains=("middleeasteye.net",), text="self-report")],
        )
        cv = enriched.claims[0]
        assert cv.truthfulness_status == TRUTHFULNESS_UNCORROBORATED
        assert "harness override" in cv.truthfulness_notes
        assert cv.corroborating_domains == []
        assert enriched.flagged_claims == ["c1"]

    def test_independence_safety_net_domain_not_in_evidence(self):
        # ★ 証拠 chunk に現れないドメインの引用 (judge の幻覚) も corroborated の根拠にしない
        report = _report([_claim("c1", FAITHFULNESS_SUPPORTED)])
        enriched, _, _ = _run(
            report,
            [_judge_json("corroborated", domains=["reuters.com"])],
            [_FakeResponse(domains=("middleeasteye.net",), text="evidence")],
        )
        assert enriched.claims[0].truthfulness_status == TRUTHFULNESS_UNCORROBORATED
        assert "harness override" in enriched.claims[0].truthfulness_notes

    def test_subdomain_independence(self):
        # www.aljazeera.com (証拠) vs aljazeera.com (元ソース) は階層マッチで除外
        report = _report([_claim("c1", FAITHFULNESS_SUPPORTED)])
        enriched, _, _ = _run(
            report,
            [_judge_json("corroborated", domains=["www.aljazeera.com"])],
            [_FakeResponse(domains=("www.aljazeera.com",), text="evidence")],
            source_domains=("aljazeera.com",),
        )
        assert enriched.claims[0].truthfulness_status == TRUTHFULNESS_UNCORROBORATED

    def test_contradicted_is_flagged(self):
        report = _report([_claim("c1", FAITHFULNESS_SUPPORTED)])
        enriched, _, _ = _run(
            report,
            [_judge_json("contradicted")],
            [_FakeResponse(domains=("reuters.com",), text="explicit contradiction")],
        )
        assert enriched.claims[0].truthfulness_status == TRUTHFULNESS_CONTRADICTED
        assert enriched.flagged_claims == ["c1"]
        assert enriched.truthfulness_summary.n_contradicted == 1

    def test_uncorroborated_is_flagged_not_false(self):
        report = _report([_claim("c1", FAITHFULNESS_SUPPORTED)])
        enriched, _, _ = _run(
            report,
            [_judge_json("uncorroborated")],
            [_FakeResponse(domains=(), text="関連する報道は見つかりませんでした")],
        )
        cv = enriched.claims[0]
        assert cv.truthfulness_status == TRUTHFULNESS_UNCORROBORATED
        assert enriched.flagged_claims == ["c1"]

    def test_out_of_vocabulary_status_becomes_unverified(self):
        report = _report([_claim("c1", FAITHFULNESS_SUPPORTED)])
        enriched, _, _ = _run(
            report,
            [_judge_json("definitely-true")],
            [_FakeResponse(domains=("reuters.com",), text="evidence")],
        )
        cv = enriched.claims[0]
        assert cv.truthfulness_status == TRUTHFULNESS_UNVERIFIED
        assert "out-of-vocabulary" in cv.truthfulness_notes

    def test_judge_failure_becomes_unverified(self):
        # 沈黙的劣化の禁止: 判定が完了しなかった claim は unverified (検証未完)
        report = _report([_claim("c1", FAITHFULNESS_SUPPORTED)])
        enriched, judge, _ = _run(
            report,
            [RuntimeError("503"), RuntimeError("503")],  # max_retries=2 で尽きる
            [_FakeResponse(domains=("reuters.com",), text="evidence")],
        )
        cv = enriched.claims[0]
        assert cv.truthfulness_status == TRUTHFULNESS_UNVERIFIED
        assert "judgement failed" in cv.truthfulness_notes
        assert len(judge.prompts) == 2

    def test_all_searches_failed_becomes_unverified_without_judge_call(self):
        report = _report([_claim("c1", FAITHFULNESS_SUPPORTED, n_queries=2)])
        enriched, judge, _ = _run(
            report,
            [],
            [RuntimeError("down"), RuntimeError("down")],
        )
        cv = enriched.claims[0]
        assert cv.truthfulness_status == TRUTHFULNESS_UNVERIFIED
        assert "grounded search(es) failed" in cv.truthfulness_notes
        assert judge.prompts == []  # 判定は呼ばれない
        assert len(cv.truthfulness_evidence) == 2

    def test_partial_search_failure_still_judges(self):
        report = _report([_claim("c1", FAITHFULNESS_SUPPORTED, n_queries=2)])
        enriched, judge, _ = _run(
            report,
            [_judge_json("corroborated", domains=["reuters.com"])],
            [RuntimeError("down"), _FakeResponse(domains=("reuters.com",), text="ok")],
        )
        assert enriched.claims[0].truthfulness_status == TRUTHFULNESS_CORROBORATED
        assert len(judge.prompts) == 1
        # 失敗クエリも証拠として記録される (監査可能性)
        assert enriched.claims[0].truthfulness_evidence[0].error != ""

    def test_no_queries_becomes_unverified(self):
        report = _report([_claim("c1", FAITHFULNESS_SUPPORTED, n_queries=0)])
        enriched, judge, _ = _run(report, [], [])
        assert enriched.claims[0].truthfulness_status == TRUTHFULNESS_UNVERIFIED
        assert "no verification queries" in enriched.claims[0].truthfulness_notes
        assert judge.prompts == []

    def test_multi_query_evidence_aggregation(self):
        # run 間分散への緩和策: 複数クエリ分の証拠が 1 つの judge プロンプトに束ねられる
        report = _report([_claim("c1", FAITHFULNESS_SUPPORTED, n_queries=3)])
        enriched, judge, grounding = _run(
            report,
            [_judge_json("corroborated", domains=["reuters.com"])],
            [
                _FakeResponse(domains=("reuters.com",), text="evidence A"),
                _FakeResponse(domains=("bbc.com",), text="evidence B"),
                _FakeResponse(domains=("reuters.com",), text="evidence C"),
            ],
        )
        assert len(grounding.genai_client.models.calls) == 3  # 全クエリ実行
        assert len(judge.prompts) == 1  # 判定は claim 単位で 1 回
        for t in ("evidence A", "evidence B", "evidence C"):
            assert t in judge.prompts[0]
        assert len(enriched.claims[0].truthfulness_evidence) == 3


class TestTargetSelection:
    def test_layer1_contradicted_and_unverified_are_skipped(self):
        report = _report(
            [
                _claim("c1", FAITHFULNESS_SUPPORTED),
                _claim("c2", FAITHFULNESS_CONTRADICTED),
                _claim("c3", FAITHFULNESS_UNVERIFIED),
                _claim("c4", FAITHFULNESS_NOT_IN_SOURCE),
            ]
        )
        enriched, judge, grounding = _run(
            report,
            [
                _judge_json("corroborated", claim_id="c1", domains=["reuters.com"]),
                _judge_json("corroborated", claim_id="c4", domains=["reuters.com"]),
            ],
            [
                _FakeResponse(domains=("reuters.com",), text="ev1"),
                _FakeResponse(domains=("reuters.com",), text="ev4"),
            ],
        )
        by_id = {cv.claim.claim_id: cv for cv in enriched.claims}
        # 対象 = supported + not_in_source のみ
        assert by_id["c1"].truthfulness_status == TRUTHFULNESS_CORROBORATED
        assert by_id["c4"].truthfulness_status == TRUTHFULNESS_CORROBORATED
        # skip = pending のまま + skip 理由 (修正後に手動ランナー再実行する運用)
        assert by_id["c2"].truthfulness_status == TRUTHFULNESS_PENDING
        assert "skipped by corroboration" in by_id["c2"].truthfulness_notes
        assert "contradicted" in by_id["c2"].truthfulness_notes
        assert by_id["c3"].truthfulness_status == TRUTHFULNESS_PENDING
        assert by_id["c3"].truthfulness_evidence == []
        assert len(judge.prompts) == 2
        assert len(grounding.genai_client.models.calls) == 2
        s = enriched.truthfulness_summary
        assert s.n_pending == 2 and s.n_corroborated == 2

    def test_publish_bar_not_in_source_corroborated_still_flagged(self):
        # ★ 公開可否バー: not_in_source は corroborated でも flag のまま
        #   (supported × corroborated のみ非 flag)
        report = _report(
            [
                _claim("c1", FAITHFULNESS_SUPPORTED),
                _claim("c2", FAITHFULNESS_NOT_IN_SOURCE),
                _claim("c3", FAITHFULNESS_CONTRADICTED),
            ]
        )
        enriched, _, _ = _run(
            report,
            [
                _judge_json("corroborated", claim_id="c1", domains=["reuters.com"]),
                _judge_json("corroborated", claim_id="c2", domains=["reuters.com"]),
            ],
            [
                _FakeResponse(domains=("reuters.com",), text="ev1"),
                _FakeResponse(domains=("reuters.com",), text="ev2"),
            ],
        )
        assert enriched.flagged_claims == ["c2", "c3"]

    def test_supported_uncorroborated_is_flagged(self):
        report = _report([_claim("c1", FAITHFULNESS_SUPPORTED)])
        enriched, _, _ = _run(
            report,
            [_judge_json("uncorroborated")],
            [_FakeResponse(domains=("reuters.com",), text="weak")],
        )
        assert enriched.flagged_claims == ["c1"]


class TestSilentDegradationBan:
    def test_judge_unavailable_marks_targets_unverified(self, monkeypatch):
        import src.generation.editorial_guardian_corroboration as mod

        monkeypatch.setattr(mod, "get_guardian_llm_client", lambda: None)
        report = _report(
            [
                _claim("c1", FAITHFULNESS_SUPPORTED),
                _claim("c2", FAITHFULNESS_CONTRADICTED),
            ]
        )
        enriched = corroborate_report(
            report,
            source_domains=["middleeasteye.net"],
            grounding_client=_grounding([]),
            guardian_client=None,
        )
        s = enriched.truthfulness_summary
        assert s.judge_unavailable is True
        assert "NOT performed" in s.unavailable_reason
        by_id = {cv.claim.claim_id: cv for cv in enriched.claims}
        assert by_id["c1"].truthfulness_status == TRUTHFULNESS_UNVERIFIED
        assert by_id["c2"].truthfulness_status == TRUTHFULNESS_PENDING  # skip 扱い
        # 全 claim が flag (公開可否バー: corroborated が 1 件も無い)
        assert enriched.flagged_claims == ["c1", "c2"]

    def test_prompt_not_found_marks_unverified(self):
        report = _report([_claim("c1", FAITHFULNESS_SUPPORTED)])
        enriched, _, _ = (
            corroborate_report(
                report,
                source_domains=[],
                grounding_client=_grounding([]),
                guardian_client=_JudgeLLM([]),
                channel_id="no_such_channel",
            ),
            None,
            None,
        )
        s = enriched.truthfulness_summary
        assert s.judge_unavailable is True
        assert "prompt not found" in s.unavailable_reason
        assert enriched.claims[0].truthfulness_status == TRUTHFULNESS_UNVERIFIED


class TestEnrichmentDesign:
    def test_input_report_is_not_mutated(self):
        report = _report([_claim("c1", FAITHFULNESS_SUPPORTED)])
        _run(
            report,
            [_judge_json("corroborated", domains=["reuters.com"])],
            [_FakeResponse(domains=("reuters.com",), text="ev")],
        )
        assert report.claims[0].truthfulness_status == TRUTHFULNESS_PENDING
        assert report.schema_version == 1
        assert report.truthfulness_summary is None

    def test_enriched_report_round_trip(self):
        report = _report(
            [
                _claim("c1", FAITHFULNESS_SUPPORTED),
                _claim("c2", FAITHFULNESS_CONTRADICTED),
            ]
        )
        enriched, _, _ = _run(
            report,
            [_judge_json("corroborated", domains=["reuters.com"])],
            [_FakeResponse(domains=("reuters.com",), text="ev")],
        )
        dumped = enriched.model_dump_json()
        reloaded = EditorialGuardianReport.model_validate_json(dumped)
        assert reloaded.schema_version == ENRICHED_SCHEMA_VERSION
        assert reloaded.truthfulness_summary.n_corroborated == 1
        assert reloaded.claims[0].truthfulness_evidence[0].domains == ["reuters.com"]
        assert reloaded.flagged_claims == ["c2"]

    def test_pre_enrichment_report_round_trip_unchanged(self):
        # 1-T.1 素のレポート (truthfulness_summary なし) も従来通り読み書きできる
        report = _report([_claim("c1", FAITHFULNESS_SUPPORTED)])
        reloaded = EditorialGuardianReport.model_validate_json(report.model_dump_json())
        assert reloaded.truthfulness_summary is None
        assert reloaded.claims[0].truthfulness_status == TRUTHFULNESS_PENDING


class TestHelpers:
    def test_coerce_truthfulness(self):
        assert _coerce_truthfulness("corroborated") == TRUTHFULNESS_CORROBORATED
        assert _coerce_truthfulness(" CONTRADICTED ") == TRUTHFULNESS_CONTRADICTED
        assert _coerce_truthfulness("uncorroborated") == TRUTHFULNESS_UNCORROBORATED
        assert _coerce_truthfulness("pending") == TRUTHFULNESS_UNVERIFIED
        assert _coerce_truthfulness(None) == TRUTHFULNESS_UNVERIFIED
        assert _coerce_truthfulness("true") == TRUTHFULNESS_UNVERIFIED

    def test_validated_independent_domains(self):
        out = _validated_independent_domains(
            ["Reuters.com", "middleeasteye.net", "ghost.example", "reuters.com", 123],
            evidence_domains=["reuters.com", "middleeasteye.net"],
            source_domains=["middleeasteye.net"],
        )
        assert out == ["reuters.com"]
        assert _validated_independent_domains("not-a-list", ["a.com"], []) == []

    def test_build_evidence_block_includes_failures(self):
        block = _build_evidence_block(
            [
                CorroborationEvidence(
                    query="q1", domains=["reuters.com"], response_text="found",
                    resolved_urls=["https://reuters.com/a"],
                ),
                CorroborationEvidence(query="q2", error="TimeoutError: 90s"),
            ]
        )
        assert "reuters.com" in block
        assert "https://reuters.com/a" in block
        assert "この検索は失敗した" in block
        assert "TimeoutError" in block
        assert _build_evidence_block([]) == "(証拠なし)"
