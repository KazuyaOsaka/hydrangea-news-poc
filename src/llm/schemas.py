from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class GarbageFilterResult(BaseModel):
    """Tier 2 (Lite) モデルによるノイズ除去フィルターの出力。"""
    item_id: int
    is_valuable: bool
    reason: str


class EditorScore(BaseModel):
    """Tier 1 (Flash) モデルによる Hydrangea 5大評価軸スコアリング。"""
    score_anti_sontaku: int = Field(..., ge=0, le=10)
    score_multipolar: int = Field(..., ge=0, le=10)
    score_outside_in: int = Field(..., ge=0, le=10)
    score_insight: int = Field(..., ge=0, le=10)
    score_fandom_fast: int = Field(..., ge=0, le=10)
    total_score: int
    editor_comment: str

    @model_validator(mode="after")
    def _validate_total(self) -> "EditorScore":
        expected = (
            self.score_anti_sontaku
            + self.score_multipolar
            + self.score_outside_in
            + self.score_insight
            + self.score_fandom_fast
        )
        if self.total_score != expected:
            raise ValueError(
                f"total_score {self.total_score} != sum of subscores {expected}"
            )
        return self

    @property
    def is_adopted(self) -> bool:
        """採用判定: 総合力(>=20) または 一点突破(いずれか1項目>=9)。"""
        if self.total_score >= 20:
            return True
        scores = [
            self.score_anti_sontaku,
            self.score_multipolar,
            self.score_outside_in,
            self.score_insight,
            self.score_fandom_fast,
        ]
        return any(s >= 9 for s in scores)
