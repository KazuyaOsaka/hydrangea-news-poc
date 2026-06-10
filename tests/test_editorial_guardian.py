"""F-editorial-guardian-claim-extraction (1-T.1): Editorial Guardian 検証。

src/generation/editorial_guardian.py を LLM mock で決定的に検証する:
  - 高リスク主張の抽出 (coercion 込) + 入力ブロック整形
  - 第1層・忠実性判定 (supported / contradicted / not_in_source の3値)
  - ★ flag 意味論 (1-Q.5 B-3' と安全方向が逆): supported 以外は全て人間レビュー行き、
    ただし unverified (検証未完) は contradicted (矛盾) と明確に区別する
  - ★ 沈黙的劣化の禁止: Guardian モデル不可時は guardian_unavailable を明示し
    「検証済み」スタンプを出さない (下位モデルでの検証続行はしない)
  - 2層レポート骨格 (truthfulness_status=pending / verification_queries) の固定
    = 1-T.2 (F-editorial-guardian-corroboration) の差し込み先
  - factory.py GUARDIAN role (単一要素 tier list、fallback chain なし)

正典: docs/ADR/0003-content-moral-guidelines.md「公開前検証」セクション。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.generation.editorial_guardian import (
    FAITHFULNESS_CONTRADICTED,
    FAITHFULNESS_NOT_IN_SOURCE,
    FAITHFULNESS_SUPPORTED,
    FAITHFULNESS_UNVERIFIED,
    TRUTHFULNESS_PENDING,
    ClaimVerification,
    EditorialGuardianReport,
    HighRiskClaim,
    _build_claims,
    _build_script_block,
    _build_source_material,
    _build_title_block,
    _coerce_artifact,
    _coerce_faithfulness,
    _coerce_risk_category,
    run_editorial_guardian,
)
from src.shared.models import (
    AnalysisResult,
    MultiAngleAnalysis,
    NewsEvent,
    ParticularAngleMetadata,
    PerspectiveCandidate,
    ScoredEvent,
    ScriptSection,
    SontakuSignals,
    SourceRef,
    TitleLayer,
    VideoScript,
)


# ---------- スタブ LLM ----------

class _SeqClient:
    """呼び出し順に固定応答を返す LLM mock (抽出 → 判定の 2 段呼出用)。"""

    def __init__(self, responses, model: str = "gemini-3.1-pro-preview"):
        self._responses = list(responses)
        self._model = model
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


# ---------- フィクスチャ ----------

def _scored_event(with_analysis: bool = True) -> ScoredEvent:
    ev = NewsEvent(
        id="evt-guardian-1",
        title="Israel seizes strategic castle in Lebanon",
        summary=(
            "Israeli troops captured Beaufort Castle. The death toll in Lebanon "
            "reached 3,371 and the number of wounded 10,129 since the war started, "
            "according to the Lebanese health ministry. Israeli troops killed in "
            "Lebanon since early March: 25. Finance Minister Smotrich called to "
            "destroy one hundred buildings for every drone."
        ),
        category="geopolitics",
        source="Middle East Eye",
        published_at=datetime.now(timezone.utc),
        global_view="Arab media frame the seizure as a sovereignty violation.",
        sources_en=[SourceRef(name="MEE", url="https://en.example/m", region="global")],
    )
    se = ScoredEvent(event=ev, score=71.7, channel_id="geo_lens")
    if not with_analysis:
        return se
    ar = AnalysisResult(
        event_id="evt-guardian-1",
        channel_id="geo_lens",
        selected_perspective=PerspectiveCandidate(
            axis="hidden_stakes", score=8.0, reasoning="r", evidence_refs=["a0"]
        ),
        perspective_verified=True,
        multi_angle=MultiAngleAnalysis(
            geopolitical="g", political_intent="p", economic_impact="e",
            cultural_context="c", media_divergence="m",
        ),
        selected_duration_profile="geopolitics_120s",
        generated_at=datetime.now(timezone.utc).isoformat(),
        particular_angle_metadata=ParticularAngleMetadata(
            stream_classification="stream_2_perspective_gap",
            core_question="占領の構造的意味",
            differentiation_from_mainstream="角度は未報道",
            hydrangea_axis_alignment="第 2 軸",
            sontaku_signals=SontakuSignals(level="high", type="diplomatic", reasoning="忖度"),
        ),
    )
    return se.model_copy(update={"analysis_result": ar})


def _video_script(intro: str = "", outro: str = "") -> VideoScript:
    return VideoScript(
        event_id="evt-guardian-1",
        title="Israel の城塞占領",
        intro=intro,
        sections=[
            ScriptSection(heading="hook", body="900年の城が、落ちた。", duration_sec=8),
            ScriptSection(heading="twist", body="死者3,371人。それでも止まらない。", duration_sec=30),
        ],
        outro=outro,
        total_duration_sec=38,
        title_layer=TitleLayer(
            canonical_title="Israel seizes strategic castle in Lebanon",
            platform_title="日本では報道されないIsraelの視点",
            hook_line="海外の見方、日本とは違う。",
            thumbnail_text="日本 vs 海外",
        ),
    )


_ARTICLE = (
    "# イスラエルが要衝を占拠\n\n"
    "レバノン保健省によると死者数が3,371人、負傷者数が10,129人に達した。"
    "イスラエル軍兵士25人が死亡した。"
    "スモトリッチ財務相が「ドローン1機につき建物100棟を破壊すべき」と発言した。"
)


def _claims_response(claims: list[dict]) -> str:
    return json.dumps({"claims": claims}, ensure_ascii=False)


def _verdicts_response(verdicts: list[dict]) -> str:
    return json.dumps({"verdicts": verdicts}, ensure_ascii=False)


_CLAIM_FIGURE = {
    "claim_id": "c1",
    "claim_text": "レバノン側の死者数は紛争開始以降 3,371 人に達した",
    "artifact": "article",
    "risk_category": "figure",
    "quote_span": "死者数が3,371人",
}
_CLAIM_STATEMENT = {
    "claim_id": "c2",
    "claim_text": "スモトリッチ財務相がドローン1機につき建物100棟の破壊を主張した",
    "artifact": "article",
    "risk_category": "attributed_statement",
    "quote_span": "「ドローン1機につき建物100棟を破壊すべき」と発言した",
}
_CLAIM_SCRIPT = {
    "claim_id": "c3",
    "claim_text": "死者は 3,371 人",
    "artifact": "script",
    "risk_category": "figure",
    "quote_span": "死者3,371人。",
}


def _verdict(cid: str, status: str, queries: list[dict] | None = None) -> dict:
    return {
        "claim_id": cid,
        "status": status,
        "reasoning": f"{cid} の判定理由",
        "source_evidence": "the death toll in Lebanon reached 3,371" if status != "not_in_source" else "",
        "verification_queries": queries if queries is not None else [
            {"query": "Lebanon death toll 3371 health ministry", "locale": "en", "purpose": "死者数の裏取り"}
        ],
    }


# ---------- 入力ブロック整形 ----------

def test_title_block_includes_title_layer_fields():
    block = _build_title_block(_video_script())
    assert "日本では報道されないIsraelの視点" in block
    assert "canonical_title: Israel seizes strategic castle in Lebanon" in block
    assert "hook_line: 海外の見方、日本とは違う。" in block


def test_title_block_falls_back_to_script_title():
    vs = _video_script()
    vs = vs.model_copy(update={"title_layer": None})
    block = _build_title_block(vs)
    assert "title: Israel の城塞占領" in block


def test_script_block_new_route_omits_empty_intro_outro():
    """新ルート (intro/outro 空) ではナレーション = sections のみ。"""
    block = _build_script_block(_video_script())
    assert "[hook] 900年の城が、落ちた。" in block
    assert "[twist] 死者3,371人。それでも止まらない。" in block
    assert "[intro]" not in block
    assert "[outro]" not in block


def test_script_block_includes_legacy_intro_outro():
    """旧形式 script.json (intro/outro 非空) も検証対象に含める (仮説2)。"""
    block = _build_script_block(_video_script(intro="冒頭の一文", outro="締めの一文"))
    assert "[intro] 冒頭の一文" in block
    assert "[outro] 締めの一文" in block


def test_source_material_scope_records_event_and_analysis():
    material, scope = _build_source_material(_scored_event())
    assert scope.has_event is True
    assert scope.has_analysis is True
    assert scope.event_summary_chars > 0
    assert "3,371" in material              # 生成器が見た素材に raw 数字が含まれる
    assert "NewsEvent" in material
    assert "AnalysisResult" in material
    # 生成物相互参照と wrapper フィールドの除外を notes に明示する
    assert "cannot vouch" in scope.notes
    assert "judge_result" in scope.notes


def test_source_material_scope_missing_analysis():
    material, scope = _build_source_material(_scored_event(with_analysis=False))
    assert scope.has_event is True
    assert scope.has_analysis is False
    assert "(missing)" in material


# ---------- coercion ----------

def test_coerce_faithfulness_valid_passthrough():
    assert _coerce_faithfulness("supported") == FAITHFULNESS_SUPPORTED
    assert _coerce_faithfulness("CONTRADICTED") == FAITHFULNESS_CONTRADICTED
    assert _coerce_faithfulness("not_in_source") == FAITHFULNESS_NOT_IN_SOURCE


def test_coerce_faithfulness_unknown_is_unverified_not_contradicted():
    """不明 status は unverified (検証未完 = flag) に倒し、contradicted (矛盾) とは
    区別する (flag 意味論: 未検証も人間レビュー行きだが虚偽断定はしない)。"""
    assert _coerce_faithfulness("maybe") == FAITHFULNESS_UNVERIFIED
    assert _coerce_faithfulness("") == FAITHFULNESS_UNVERIFIED
    assert _coerce_faithfulness(None) == FAITHFULNESS_UNVERIFIED


def test_coerce_risk_category_unknown_falls_to_assertive_fact():
    assert _coerce_risk_category("figure") == "figure"
    assert _coerce_risk_category("weird_category") == "assertive_fact"


def test_coerce_artifact_unknown():
    assert _coerce_artifact("article") == "article"
    assert _coerce_artifact("thumbnail") == "unknown"


def test_build_claims_skips_empty_and_assigns_ids():
    payload = {
        "claims": [
            {"claim_text": "", "artifact": "article"},               # 空 → skip
            {"claim_text": "主張A", "artifact": "article", "risk_category": "figure"},
            {"claim_id": "c2", "claim_text": "主張B", "artifact": "script"},
            {"claim_id": "c2", "claim_text": "主張C", "artifact": "title"},  # 重複 id → 連番再割当
        ]
    }
    claims = _build_claims(payload)
    assert len(claims) == 3
    assert claims[0].claim_id == "c2"
    assert claims[1].claim_id == "c2" or claims[1].claim_id.startswith("c")
    ids = [c.claim_id for c in claims]
    assert len(set(ids)) == 3  # 一意性


# ---------- E2E (mock): 抽出 → 忠実性判定 → 2層レポート ----------

def test_e2e_supported_claims_not_flagged():
    client = _SeqClient([
        _claims_response([_CLAIM_FIGURE, _CLAIM_STATEMENT]),
        _verdicts_response([
            _verdict("c1", "supported"),
            _verdict("c2", "supported"),
        ]),
    ])
    report = run_editorial_guardian(_scored_event(), _video_script(), _ARTICLE, client=client)
    assert report.guardian_unavailable is False
    assert report.guardian_model_used == "gemini-3.1-pro-preview"
    assert len(report.claims) == 2
    assert report.n_supported == 2
    assert report.flagged_claims == []
    # 2層スキーマ: truthfulness は 1-T.2 まで pending で固定
    for cv in report.claims:
        assert cv.truthfulness_status == TRUTHFULNESS_PENDING
        assert len(cv.verification_queries) >= 1
        assert cv.verification_queries[0].query


def test_e2e_contradicted_and_not_in_source_flagged():
    """flag 意味論: contradicted (矛盾) + not_in_source (入力に無い = 未検証) の
    両方が人間レビュー行き。supported は flag しない。"""
    client = _SeqClient([
        _claims_response([_CLAIM_FIGURE, _CLAIM_STATEMENT, _CLAIM_SCRIPT]),
        _verdicts_response([
            _verdict("c1", "supported"),
            _verdict("c2", "contradicted"),
            _verdict("c3", "not_in_source"),
        ]),
    ])
    report = run_editorial_guardian(_scored_event(), _video_script(), _ARTICLE, client=client)
    assert report.n_supported == 1
    assert report.n_contradicted == 1
    assert report.n_not_in_source == 1
    assert sorted(report.flagged_claims) == ["c2", "c3"]
    by_id = {cv.claim.claim_id: cv for cv in report.claims}
    assert by_id["c2"].faithfulness_status == FAITHFULNESS_CONTRADICTED
    assert by_id["c3"].faithfulness_status == FAITHFULNESS_NOT_IN_SOURCE


def test_e2e_unknown_status_becomes_unverified_and_flagged():
    client = _SeqClient([
        _claims_response([_CLAIM_FIGURE]),
        _verdicts_response([_verdict("c1", "plausible")]),  # 語彙外
    ])
    report = run_editorial_guardian(_scored_event(), _video_script(), _ARTICLE, client=client)
    assert report.claims[0].faithfulness_status == FAITHFULNESS_UNVERIFIED
    assert report.flagged_claims == ["c1"]
    assert report.n_unverified == 1
    assert report.n_contradicted == 0  # 矛盾と区別する


def test_e2e_missing_verdict_becomes_unverified():
    """judge が一部の主張の verdict を返さない → 当該主張は検証未完 (flag)。"""
    client = _SeqClient([
        _claims_response([_CLAIM_FIGURE, _CLAIM_STATEMENT]),
        _verdicts_response([_verdict("c1", "supported")]),  # c2 欠落
    ])
    report = run_editorial_guardian(_scored_event(), _video_script(), _ARTICLE, client=client)
    by_id = {cv.claim.claim_id: cv for cv in report.claims}
    assert by_id["c1"].faithfulness_status == FAITHFULNESS_SUPPORTED
    assert by_id["c2"].faithfulness_status == FAITHFULNESS_UNVERIFIED
    assert report.flagged_claims == ["c2"]


def test_e2e_no_claims_extracted_completes_without_flags():
    client = _SeqClient([_claims_response([])])
    report = run_editorial_guardian(_scored_event(), _video_script(), "短い無リスク本文。", client=client)
    assert report.guardian_unavailable is False
    assert report.claims == []
    assert report.flagged_claims == []
    assert len(client.prompts) == 1  # 判定段は呼ばれない


def test_e2e_extraction_prompt_contains_artifacts():
    client = _SeqClient([_claims_response([])])
    run_editorial_guardian(_scored_event(), _video_script(), _ARTICLE, client=client)
    prompt = client.prompts[0]
    assert "日本では報道されないIsraelの視点" in prompt   # title 層
    assert "900年の城が、落ちた。" in prompt              # script ナレーション
    assert "スモトリッチ財務相" in prompt                  # article 本文


def test_e2e_judge_prompt_contains_source_material_and_claims():
    client = _SeqClient([
        _claims_response([_CLAIM_FIGURE]),
        _verdicts_response([_verdict("c1", "supported")]),
    ])
    run_editorial_guardian(_scored_event(), _video_script(), _ARTICLE, client=client)
    judge_prompt = client.prompts[1]
    assert "death toll in Lebanon" in judge_prompt        # event.summary (生成器入力)
    assert "c1" in judge_prompt                            # claims_json
    # ★ 生成成果物は照合素材に含めない (生成物は自分の保証人になれない)
    assert "# イスラエルが要衝を占拠" not in judge_prompt.split("検証対象の主張一覧")[0]


# ---------- ★ 沈黙的劣化の禁止 (guardian_unavailable) ----------

def test_no_client_is_guardian_unavailable(monkeypatch):
    monkeypatch.setattr(
        "src.generation.editorial_guardian.get_guardian_llm_client", lambda: None
    )
    report = run_editorial_guardian(_scored_event(), _video_script(), _ARTICLE)
    assert report.guardian_unavailable is True
    assert report.guardian_model_used is None
    assert "NOT performed" in (report.unavailable_reason or "")
    assert report.claims == []


def test_extraction_failure_is_guardian_unavailable_not_silent():
    """抽出が落ちたら guardian_unavailable を明示する (空レポートで「検証済み」に
    見せない)。実際に試行したモデル ID も記録する。"""
    client = _SeqClient([RuntimeError("503"), RuntimeError("503")])
    report = run_editorial_guardian(
        _scored_event(), _video_script(), _ARTICLE, client=client, max_retries=2
    )
    assert report.guardian_unavailable is True
    assert "extraction failed" in (report.unavailable_reason or "")
    assert report.guardian_model_used == "gemini-3.1-pro-preview"
    assert len(client.prompts) == 2  # 同一モデルで max_retries 回のみ (劣化なし)


def test_judge_failure_marks_all_claims_unverified():
    """判定段が落ちたら抽出済み主張は全件 unverified (検証未完) + flag。
    下位モデルで判定を続行しない。"""
    client = _SeqClient([
        _claims_response([_CLAIM_FIGURE, _CLAIM_STATEMENT]),
        RuntimeError("503"),
        RuntimeError("503"),
    ])
    report = run_editorial_guardian(
        _scored_event(), _video_script(), _ARTICLE, client=client, max_retries=2
    )
    assert report.guardian_unavailable is True
    assert "faithfulness judgement failed" in (report.unavailable_reason or "")
    assert len(report.claims) == 2
    assert all(cv.faithfulness_status == FAITHFULNESS_UNVERIFIED for cv in report.claims)
    assert sorted(report.flagged_claims) == ["c1", "c2"]


# ---------- 2層レポート骨格 (1-T.2 差し込みスキーマの固定) ----------

def test_report_schema_reserves_truthfulness_for_1t2():
    cv = ClaimVerification(
        claim=HighRiskClaim(
            claim_id="c1", claim_text="t", artifact="article",
            risk_category="figure", quote_span="q",
        ),
        faithfulness_status=FAITHFULNESS_SUPPORTED,
    )
    assert cv.truthfulness_status == TRUTHFULNESS_PENDING
    assert cv.truthfulness_notes == ""
    assert cv.verification_queries == []


def test_report_is_json_serializable():
    client = _SeqClient([
        _claims_response([_CLAIM_FIGURE]),
        _verdicts_response([_verdict("c1", "contradicted")]),
    ])
    report = run_editorial_guardian(_scored_event(), _video_script(), _ARTICLE, client=client)
    dumped = json.loads(report.model_dump_json())
    assert dumped["schema_version"] == 1
    assert dumped["event_id"] == "evt-guardian-1"
    assert dumped["claims"][0]["faithfulness_status"] == "contradicted"
    assert dumped["claims"][0]["truthfulness_status"] == "pending"
    assert dumped["claims"][0]["verification_queries"][0]["locale"] == "en"
    assert dumped["source_material_scope"]["has_event"] is True
    assert dumped["flagged_claims"] == ["c1"]
    assert isinstance(report, EditorialGuardianReport)


# ---------- factory: GUARDIAN role (単一要素 tier list、fallback なし) ----------

def test_factory_guardian_tier_is_single_element_default():
    from src.llm.factory import _get_tier_models_for_role

    tiers = _get_tier_models_for_role("guardian")
    assert tiers == ["gemini-3.1-pro-preview"]  # ★ fallback chain を構造的に持たない


def test_factory_guardian_tier_env_override(monkeypatch):
    from src.llm.factory import _get_tier_models_for_role

    monkeypatch.setenv("GEMINI_GUARDIAN_TIER1", "gemini-9.9-pro-test")
    tiers = _get_tier_models_for_role("guardian")
    assert tiers == ["gemini-9.9-pro-test"]
    assert len(tiers) == 1


def test_factory_guardian_max_attempts_default():
    from src.llm.factory import _get_max_attempts_for_role

    assert _get_max_attempts_for_role("guardian") == 2


def test_factory_get_guardian_llm_client_single_tier(monkeypatch):
    import src.llm.factory as factory

    monkeypatch.setattr(factory, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(factory, "GENERATION_PROVIDER", "gemini")
    client = factory.get_guardian_llm_client()
    assert client is not None
    assert client._tiers == ["gemini-3.1-pro-preview"]
    assert client._model == "gemini-3.1-pro-preview"


def test_factory_get_guardian_llm_client_none_for_non_gemini(monkeypatch):
    """Gemini 以外の provider へ黙示 fallback しない (沈黙的劣化の禁止)。"""
    import src.llm.factory as factory

    monkeypatch.setattr(factory, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(factory, "GENERATION_PROVIDER", "groq")
    assert factory.get_guardian_llm_client() is None


def test_factory_get_guardian_llm_client_none_without_api_key(monkeypatch):
    import src.llm.factory as factory

    monkeypatch.setattr(factory, "GEMINI_API_KEY", "")
    assert factory.get_guardian_llm_client() is None


# ---------- プロンプトファイル ----------

_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "configs" / "prompts" / "analysis" / "geo_lens"


def test_extract_prompt_exists_with_placeholders():
    text = (_PROMPTS_DIR / "editorial_guardian_extract.md").read_text(encoding="utf-8")
    for ph in ("{event_id}", "{title_block}", "{script_block}", "{article_text}"):
        assert ph in text


def test_faithfulness_prompt_exists_with_placeholders():
    text = (_PROMPTS_DIR / "editorial_guardian_faithfulness.md").read_text(encoding="utf-8")
    for ph in ("{event_id}", "{source_material}", "{claims_json}"):
        assert ph in text


def test_prompts_format_without_key_error():
    """JSON 例の brace escape 漏れ ({{...}}) を検出する。"""
    extract = (_PROMPTS_DIR / "editorial_guardian_extract.md").read_text(encoding="utf-8")
    extract.format(event_id="e", title_block="t", script_block="s", article_text="a")
    judge = (_PROMPTS_DIR / "editorial_guardian_faithfulness.md").read_text(encoding="utf-8")
    judge.format(event_id="e", source_material="m", claims_json="[]")
