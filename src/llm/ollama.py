from __future__ import annotations

from src.llm.base import LLMClient


class OllamaClient(LLMClient):
    """Ollama (ローカル Llama 系) を使う LLMClient スタブ実装。

    実装手順:
      1. https://ollama.com からインストール
      2. ollama pull llama3.2 などでモデルを取得
      3. .env に OLLAMA_BASE_URL, OLLAMA_SCRIPT_MODEL 等を設定
      4. このクラスの generate() を実装する
    """

    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url
        self._model = model

    def generate(self, prompt: str) -> str:
        raise NotImplementedError(
            "Ollama provider はまだ実装されていません。"
            " ollama パッケージをインストールして generate() を実装してください。"
        )
