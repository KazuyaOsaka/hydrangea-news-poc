"""source_profiles.py — 出典権威プロファイルのローダー + 媒体名ペア選択。

スクリプト台本で媒体名を言及する際に、evidence に実際に存在する
上位ソースを最大2つ選ぶロジックを提供する。

重要な制約:
  - evidence（sources_jp / sources_en / sources_by_locale）に存在するソースのみ選択
  - source_profiles.yaml の can_authority_mention=true のソースのみ言及可
  - このモジュールは「言及根拠の生成」は行わない。呼び出し元がソース在否を確認すること。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from src.shared.logger import get_logger

if TYPE_CHECKING:
    from src.shared.models import SourceRef

logger = get_logger(__name__)

_PROFILES_PATH = Path(__file__).resolve().parents[2] / "configs" / "source_profiles.yaml"

# authority_tier → 数値（小さいほど優先度が高い）
_TIER_ORDER: dict[str, int] = {"top": 0, "major": 1, "standard": 2}


@lru_cache(maxsize=1)
def load_source_profiles() -> dict[str, dict]:
    """configs/source_profiles.yaml をロードして source_name をキーとする dict を返す。

    ファイルが存在しない・読み込み失敗の場合は空 dict を返す（graceful fallback）。
    """
    try:
        import yaml  # type: ignore[import]
        with open(_PROFILES_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        result: dict[str, dict] = {}
        for p in data.get("source_profiles", []):
            name = p.get("source_name", "")
            if name:
                result[name] = p
        logger.debug(f"[SourceProfiles] Loaded {len(result)} profiles from {_PROFILES_PATH}")
        return result
    except Exception as exc:
        logger.warning(f"[SourceProfiles] Failed to load source_profiles.yaml: {exc}")
        return {}


def _normalize_name(name: str) -> str:
    """ソース名を正規化（大文字小文字・スペース・ハイフン・アンダースコア無視）。"""
    return name.strip().lower().replace(" ", "").replace("-", "").replace("_", "")


def find_profile(profiles: dict[str, dict], source_name: str) -> Optional[dict]:
    """source_name でプロファイルを検索する（大文字小文字を区別しない）。

    完全一致 → 正規化マッチ の順で探す。
    """
    if source_name in profiles:
        return profiles[source_name]
    norm = _normalize_name(source_name)
    for k, v in profiles.items():
        if _normalize_name(k) == norm:
            return v
    return None


def select_authority_pair(
    sources_jp: "list[SourceRef]",
    sources_overseas: "list[SourceRef]",
    profiles: dict[str, dict] | None = None,
    max_mentions: int = 2,
) -> list[str]:
    """evidence に存在するソースから最大 max_mentions 個の媒体名（mention_style_short）を返す。

    選択ルール（優先順）:
      1. can_authority_mention=true かつ authority_tier が高い（top > major > standard）
      2. 対比ペアを優先: JP ソース 1 本 + 海外ソース 1 本
      3. JP ソースがない場合: 海外ソースから異なるリージョン2本
      4. 海外ソースのみ1本 / JP ソースのみ1本 にフォールバック
      5. 0件の場合: 空リストを返す（媒体名言及なし）

    Args:
        sources_jp       : evidence の JP ソースリスト（SourceRef）
        sources_overseas : evidence の 非JP ソースリスト（SourceRef）
        profiles         : source_profiles.yaml のロード済み dict。None なら自動ロード。
        max_mentions     : 最大返却数（デフォルト 2）

    Returns:
        list[str]: mention_style_short のリスト（最大 max_mentions 件）
    """
    if profiles is None:
        profiles = load_source_profiles()

    def _ranked(sources: "list[SourceRef]") -> list[tuple[int, str, str]]:
        """(tier_order, mention_style_short, source_name) のソート済みリスト。"""
        items: list[tuple[int, str, str]] = []
        seen_mentions: set[str] = set()
        for src in sources:
            p = find_profile(profiles, src.name)
            if not p:
                continue
            if not p.get("can_authority_mention", False):
                continue
            tier = _TIER_ORDER.get(p.get("authority_tier", "standard"), 2)
            mention = p.get("mention_style_short", src.name)
            if mention in seen_mentions:
                continue  # 同じ表示名を重複して追加しない（NHK_Politics vs NHK など）
            seen_mentions.add(mention)
            items.append((tier, mention, src.name))
        items.sort(key=lambda x: x[0])
        return items

    jp_ranked = _ranked(sources_jp)
    ov_ranked = _ranked(sources_overseas)

    result: list[str] = []

    if jp_ranked and ov_ranked:
        # 最良の対比ペア: JP トップ + 海外トップ
        result.append(jp_ranked[0][1])
        result.append(ov_ranked[0][1])
    elif ov_ranked and len(ov_ranked) >= 2:
        # 海外ソースが複数: 異なるリージョンから2本選ぶ
        regions_seen: set[str] = set()
        for _, mention, sname in ov_ranked:
            p = find_profile(profiles, sname)
            region = p.get("region", "global") if p else "global"
            if region not in regions_seen:
                result.append(mention)
                regions_seen.add(region)
            if len(result) >= max_mentions:
                break
        # リージョン多様性で2本選べなかった場合、トップ2で埋める
        if len(result) < 2 and len(ov_ranked) >= 2:
            for _, mention, _ in ov_ranked:
                if mention not in result:
                    result.append(mention)
                if len(result) >= max_mentions:
                    break
    elif jp_ranked:
        result.append(jp_ranked[0][1])
    elif ov_ranked:
        result.append(ov_ranked[0][1])

    return result[:max_mentions]


def get_mention_style_long(source_name: str, profiles: dict[str, dict] | None = None) -> str:
    """mention_style_long を返す。プロファイルが見つからない場合は source_name をそのまま返す。"""
    if profiles is None:
        profiles = load_source_profiles()
    p = find_profile(profiles, source_name)
    if p:
        return p.get("mention_style_long", source_name)
    return source_name
