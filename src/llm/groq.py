from __future__ import annotations

from src.llm.base import LLMClient


class GroqClient(LLMClient):
    """Groq (Llama系) を使う LLMClient スタブ実装。

    実装手順:
      1. pip install groq
      2. .env に GROQ_API_KEY を設定
      3. このクラスの generate() を実装する
    """

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def generate(self, prompt: str) -> str:
        raise NotImplementedError(
            "Groq provider はまだ実装されていません。"
            " groq パッケージをインストールして generate() を実装してください。"
        )
