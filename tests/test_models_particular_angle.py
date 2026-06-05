"""X1 (F-particular-angle-metadata-production-wire): Pydantic クラス構造テスト。

ParticularAngleMetadata + SontakuSignals + AnalysisResult.particular_angle_metadata
の構造・default 値・nesting・後方互換 (Optional) を検証する。

正典: docs/PARTICULAR_ANGLE_DEFINITION.md セクション 3.6-3.7。
"""
from __future__ import annotations

from src.shared.models import (
    AnalysisResult,
    MultiAngleAnalysis,
    ParticularAngleMetadata,
    PerspectiveCandidate,
    SontakuSignals,
)


def _minimal_analysis_result(**overrides) -> AnalysisResult:
    base = dict(
        event_id="evt_test",
        channel_id="geo_lens",
        selected_perspective=PerspectiveCandidate(
            axis="silence_gap", score=0.5, reasoning="r", why_now="w"
        ),
        perspective_verified=True,
        multi_angle=MultiAngleAnalysis(),
        selected_duration_profile="anti_sontaku_90s",
        generated_at="2026-05-31T00:00:00Z",
    )
    base.update(overrides)
    return AnalysisResult(**base)


# ---------- SontakuSignals ----------

def test_sontaku_signals_defaults():
    """デフォルトコンストラクタで全 field が default 値を持つ。"""
    ss = SontakuSignals()
    assert ss.level == "none"
    assert ss.type is None
    assert ss.reasoning == ""
    assert ss.extraction_confidence == "medium"


def test_sontaku_signals_full_construction():
    ss = SontakuSignals(
        level="high",
        type="diplomatic",
        reasoning="米国忖度で批判できない構造",
        extraction_confidence="high",
    )
    assert ss.level == "high"
    assert ss.type == "diplomatic"
    assert ss.reasoning == "米国忖度で批判できない構造"
    assert ss.extraction_confidence == "high"


def test_sontaku_signals_type_can_be_none_for_level_none():
    """level=none 時に type=None が許容される (正典 3.6.3)。"""
    ss = SontakuSignals(level="none", type=None)
    assert ss.type is None


# ---------- ParticularAngleMetadata ----------

def test_particular_angle_metadata_defaults():
    """デフォルトコンストラクタで stream=out_of_scope、sontaku_signals=None。"""
    pam = ParticularAngleMetadata()
    assert pam.stream_classification == "out_of_scope"
    assert pam.core_question == ""
    assert pam.differentiation_from_mainstream == ""
    assert pam.hydrangea_axis_alignment == ""
    assert pam.extraction_confidence == "medium"
    assert pam.sontaku_signals is None


def test_particular_angle_metadata_full_construction():
    """4 つの stream_classification 値が許容される (正典 3 セクション)。"""
    for stream in (
        "stream_1_silence_gap",
        "stream_2_perspective_gap",
        "stream_3_framing_inversion",
        "out_of_scope",
    ):
        pam = ParticularAngleMetadata(
            stream_classification=stream,
            core_question="q",
            differentiation_from_mainstream="d",
            hydrangea_axis_alignment="a",
            extraction_confidence="high",
            sontaku_signals=SontakuSignals(level="medium", type="domestic"),
        )
        assert pam.stream_classification == stream


def test_particular_angle_metadata_sontaku_signals_nested():
    """正典 3.7.2: sontaku_signals は particular_angle_metadata に nested。"""
    ss = SontakuSignals(level="high", type="media_industry", reasoning="記者クラブ")
    pam = ParticularAngleMetadata(
        stream_classification="stream_2_perspective_gap",
        sontaku_signals=ss,
    )
    assert pam.sontaku_signals is ss
    assert pam.sontaku_signals.level == "high"
    assert pam.sontaku_signals.type == "media_industry"


# ---------- AnalysisResult.particular_angle_metadata ----------

def test_analysis_result_default_particular_angle_metadata_is_none():
    """既存テスト互換: particular_angle_metadata は default None (X1 後方互換)。"""
    ar = _minimal_analysis_result()
    assert ar.particular_angle_metadata is None


def test_analysis_result_with_particular_angle_metadata():
    pam = ParticularAngleMetadata(
        stream_classification="stream_2_perspective_gap",
        core_question="qq",
        sontaku_signals=SontakuSignals(level="high", type="diplomatic"),
    )
    ar = _minimal_analysis_result(particular_angle_metadata=pam)
    assert ar.particular_angle_metadata is not None
    assert ar.particular_angle_metadata.stream_classification == "stream_2_perspective_gap"
    assert ar.particular_angle_metadata.sontaku_signals.level == "high"


def test_analysis_result_model_copy_attaches_particular_angle_metadata():
    """main.py の付与パターン: model_copy(update={...}) で非破壊的に metadata 付与。"""
    ar = _minimal_analysis_result()
    pam = ParticularAngleMetadata(stream_classification="stream_1_silence_gap")
    ar2 = ar.model_copy(update={"particular_angle_metadata": pam})
    # 原本不変
    assert ar.particular_angle_metadata is None
    # コピーに付与
    assert ar2.particular_angle_metadata is pam


def test_analysis_result_round_trip_via_model_dump_json():
    """JSON 永続化往復 (save_analysis_json 経由) で nesting が壊れない。"""
    pam = ParticularAngleMetadata(
        stream_classification="stream_3_framing_inversion",
        core_question="qq",
        sontaku_signals=SontakuSignals(level="medium", type="domestic", reasoning="rr"),
    )
    ar = _minimal_analysis_result(particular_angle_metadata=pam)
    j = ar.model_dump_json()
    ar2 = AnalysisResult.model_validate_json(j)
    assert ar2.particular_angle_metadata is not None
    assert ar2.particular_angle_metadata.stream_classification == "stream_3_framing_inversion"
    assert ar2.particular_angle_metadata.sontaku_signals is not None
    assert ar2.particular_angle_metadata.sontaku_signals.level == "medium"
    assert ar2.particular_angle_metadata.sontaku_signals.type == "domestic"
