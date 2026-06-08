"""F-title-guard-coverage-claim-policy (1-Q.5): coverage_claim_policy.yaml ローダ検証。

configs/coverage_claim_policy.yaml が Layer 2 構造データとして正しくロードされ、
系統別の forbidden_claim_categories が設計どおりであることを検証する。
"""
from __future__ import annotations

from pathlib import Path

from src.generation.coverage_claim_guard import (
    CoverageClaimPolicy,
    load_coverage_claim_policy,
)


def test_policy_loads_all_four_streams():
    policy = load_coverage_claim_policy()
    assert set(policy.streams.keys()) == {
        "stream_1_silence_gap",
        "stream_2_perspective_gap",
        "stream_3_framing_inversion",
        "out_of_scope",
    }


def test_silence_gap_has_no_forbidden_categories():
    """silence_gap = 未報道断定が事実整合 → forbidden 空 (guard が flag しない)。"""
    policy = load_coverage_claim_policy()
    sp = policy.stream_policy("stream_1_silence_gap")
    assert sp.forbidden_claim_categories == []
    assert sp.broad_event_reported_in_jp is False
    assert sp.particular_angle_reported_in_jp is False


def test_perspective_gap_forbids_event_total_silence_only():
    """perspective_gap = 事件本体は報道済 → event_total_silence のみ禁止。"""
    policy = load_coverage_claim_policy()
    sp = policy.stream_policy("stream_2_perspective_gap")
    assert sp.forbidden_claim_categories == ["event_total_silence"]
    assert sp.broad_event_reported_in_jp is True
    assert sp.particular_angle_reported_in_jp is False


def test_framing_inversion_forbids_both_silence_categories():
    """framing_inversion = 事件本体も角度も報道済 → 両方の未報道断定を禁止。"""
    policy = load_coverage_claim_policy()
    sp = policy.stream_policy("stream_3_framing_inversion")
    assert set(sp.forbidden_claim_categories) == {
        "event_total_silence",
        "angle_total_silence",
    }


def test_unknown_stream_falls_back_to_out_of_scope():
    policy = load_coverage_claim_policy()
    sp = policy.stream_policy("totally_unknown_stream")
    # out_of_scope は forbidden 空 = guard が flag しない (真値不明 → 安全側)。
    assert sp.forbidden_claim_categories == []


def test_forbidden_category_definitions_present():
    """forbidden_claim_categories の意味定義が guard プロンプト用に存在する。"""
    policy = load_coverage_claim_policy()
    assert "event_total_silence" in policy.forbidden_claim_categories
    assert "angle_total_silence" in policy.forbidden_claim_categories
    assert policy.forbidden_claim_categories["event_total_silence"].get("meaning")


def test_missing_policy_file_returns_empty_graceful():
    """ファイル欠損時は空ポリシー (全系統 forbidden なし = guard 無害化) を返す。"""
    policy = load_coverage_claim_policy(Path("/nonexistent/coverage_claim_policy.yaml"))
    assert isinstance(policy, CoverageClaimPolicy)
    assert policy.streams == {}
    # 空ポリシーでは stream_policy はデフォルト (forbidden 空) を返す。
    assert policy.stream_policy("stream_2_perspective_gap").forbidden_claim_categories == []
