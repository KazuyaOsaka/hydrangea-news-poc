"""分析レイヤー用プロンプトローダ。

CLAUDE.md の方針に従い、LLM プロンプトは Python コードに直書きせず
configs/prompts/analysis/{channel_id}/{prompt_name}.md から読み込む。

シンプルなファイルキャッシュを持つ（プロセス内 1 回のみ I/O）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

_PROMPTS_ROOT: Optional[Path] = None
_CACHE: dict[tuple[str, str], str] = {}


def _resolve_prompts_root() -> Path:
    global _PROMPTS_ROOT
    if _PROMPTS_ROOT is None:
        _PROMPTS_ROOT = Path(__file__).resolve().parents[2] / "configs" / "prompts" / "analysis"
    return _PROMPTS_ROOT


def load_prompt(channel_id: str, prompt_name: str, *, root: Optional[Path] = None) -> str:
    """configs/prompts/analysis/{channel_id}/{prompt_name}.md を読み込む。

    Args:
        channel_id: e.g. "geo_lens"
        prompt_name: ".md" を含めない名前。e.g. "perspective_select_and_verify"
        root: テスト用にプロンプトルートを差し替えたい場合に指定。

    Returns:
        プロンプト本文（str）。
    """
    cache_key = (str(root) if root else "__default__", f"{channel_id}/{prompt_name}")
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    base = root if root is not None else _resolve_prompts_root()
    path = base / channel_id / f"{prompt_name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    text = path.read_text(encoding="utf-8")
    _CACHE[cache_key] = text
    return text


def clear_cache() -> None:
    """テスト用: プロンプトキャッシュをクリアする。"""
    _CACHE.clear()
