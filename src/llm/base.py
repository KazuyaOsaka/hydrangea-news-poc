from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    """LLMプロバイダの共通インターフェース。"""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """プロンプトを受け取り、テキストを返す。"""
        ...
