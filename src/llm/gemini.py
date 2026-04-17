from __future__ import annotations

from src.llm.base import LLMClient


class GeminiClient(LLMClient):
    """Google Gemini を使う LLMClient 実装。"""

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def generate(self, prompt: str) -> str:
        from google import genai

        client = genai.Client(api_key=self._api_key)
        response = client.models.generate_content(
            model=self._model,
            contents=prompt,
        )
        return response.text.strip()
