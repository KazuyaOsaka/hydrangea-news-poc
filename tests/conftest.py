"""tests/conftest.py — X1 (F-particular-angle-metadata-production-wire) で新設。

.env が `ANALYSIS_LAYER_ENABLED=true` を declare するようになった (X1 production
default) ため、`src/shared/config.py:8` の `load_dotenv()` でテストランタイムにも
同設定が propagate する。既存テストの大半は ANALYSIS_LAYER_ENABLED=false の
旧ルート挙動を前提としており (analysis_result LLM mock 未整備、新ルートでは
main.py:1942-1955 の deprecation gate で skip される)、本 autouse fixture で
test 開始時に false にリセットしてテスト独立性を担保する。

新ルート挙動を確かめる既存テスト (test_main_analysis_layer_top_n /
test_e2e_analysis_layer / test_main_with_analysis 等) は内部で
`monkeypatch.setenv("ANALYSIS_LAYER_ENABLED", "true")` を呼んでおり、
function-scoped monkeypatch 内で後置 setenv が優先されるため動作に影響しない。

★ 本ファイルは tests/ への新規追加で、既存テスト本体は一切変更していない
(不変原則 5 完全遵守)。
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _x1_default_analysis_layer_disabled(monkeypatch):
    """各テスト開始時に ANALYSIS_LAYER_ENABLED=false を強制する。

    X1 で .env (gitignored) / .env.example が ANALYSIS_LAYER_ENABLED=true を
    production default として宣言したため、テスト環境がその値を継承して
    smoke/budget 系テストが skip される問題を回避する。test が新ルート挙動を
    検証したい場合は monkeypatch.setenv で true を再設定すれば良い (後置優先)。
    """
    monkeypatch.setenv("ANALYSIS_LAYER_ENABLED", "false")
