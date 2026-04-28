"""source_profiles.py — 出典権威プロファイルのローダー + 媒体名ペア選択。

スクリプト台本で媒体名を言及する際に、evidence に実際に存在する
上位ソースを最大2つ選ぶロジックを提供する。

重要な制約:
  - evidence（sources_jp / sources_en / sources_by_locale）に存在するソースのみ選択
  - source_profiles.yaml の can_authority_mention=true のソースのみ言及可
  - このモジュールは「言及根拠の生成」は行わない。呼び出し元がソース在否を確認すること。

F-8-1-A (Phase A.5-1) で SourceProfile Pydantic モデルを導入し、3層表示名
(display_name_speech / display_name_article / display_name_subtitle) と
Tier 3 媒体向け警告フィールド (requires_political_warning / state_aligned /
parent_company / funding_sources / warning_note) を追加した。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.shared.logger import get_logger

if TYPE_CHECKING:
    from src.shared.models import SourceRef

logger = get_logger(__name__)

_PROFILES_PATH = Path(__file__).resolve().parents[2] / "configs" / "source_profiles.yaml"

# authority_tier → 数値（小さいほど優先度が高い）
_TIER_ORDER: dict[str, int] = {"top": 0, "major": 1, "standard": 2}


class SourceProfile(BaseModel):
    """source_profiles.yaml の1エントリを表す Pydantic モデル。

    既存コードとの後方互換のため `.get(key, default)` メソッドを提供する
    (内部的には getattr フォールバック)。
    """
    model_config = ConfigDict(extra="allow")

    source_name: str

    # 既存の表示用フィールド（後方互換、必須ではない）
    display_name_ja: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    language: Optional[str] = None
    authority_tier: Optional[str] = None

    # F-8-1-A 以降は display_name_speech を使う。後方互換のため残す。
    # F-12 完了後に削除予定。
    mention_style_short: Optional[str] = None
    mention_style_long: Optional[str] = None
    can_authority_mention: bool = False

    # F-8-1-A: 3層表示名（必須）
    display_name_speech: str = Field(
        default="",
        description="台本発話用の表示名 (例: '独高級ニュース誌のシュピーゲル')",
    )
    display_name_article: str = Field(
        default="",
        description="記事用の表示名 (例: '独高級誌・Der Spiegel(シュピーゲル)')",
    )
    display_name_subtitle: str = Field(
        default="",
        description="字幕・テロップ用の表示名 (原語、例: 'Der Spiegel')",
    )
    requires_political_warning: bool = Field(
        default=False,
        description="Tier 3 媒体は True。台本生成時に政治的立場を強調する。",
    )

    # F-8-1-A: Tier 3 警告補強フィールド（任意、Tier 3 媒体のみ設定）
    state_aligned: Optional[bool] = Field(
        default=None,
        description="政府系メディアか。TeleSUR=True など。",
    )
    parent_company: Optional[str] = Field(
        default=None,
        description="親会社・運営組織",
    )
    funding_sources: Optional[list[str]] = Field(
        default=None,
        description="主要資金源 (例: ['venezuela_government', 'cuba_government'])",
    )
    warning_note: Optional[str] = Field(
        default=None,
        description="政治的警告の詳細注記。引用時の留意事項を記載。",
    )

    # F-8-1-A: Phase A.5-1 で追加された任意のメタデータ（新規媒体用）
    tier: Optional[str] = None
    political_lean: Optional[str] = None

    def get(self, key: str, default: Any = None) -> Any:
        """dict 互換アクセサ。属性が存在しなければ default を返す。

        既存の dict ベースの呼び出し（profile.get("can_authority_mention", False) 等）
        との後方互換のために提供する。
        """
        return getattr(self, key, default)


@lru_cache(maxsize=4)
def load_source_profiles(path: Path = _PROFILES_PATH) -> dict[str, SourceProfile]:
    """configs/source_profiles.yaml をロードして source_name をキーとする dict を返す。

    ファイルが存在しない・読み込み失敗の場合は空 dict を返す（graceful fallback）。
    """
    try:
        import yaml  # type: ignore[import]
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        result: dict[str, SourceProfile] = {}
        for raw in data.get("source_profiles", []):
            name = raw.get("source_name", "")
            if not name:
                continue
            try:
                result[name] = SourceProfile.model_validate(raw)
            except Exception as parse_exc:  # noqa: BLE001
                # 個別エントリのパース失敗は警告ログにとどめ、他のエントリは読み込み続行する
                logger.warning(
                    f"[SourceProfiles] Failed to parse entry '{name}': {parse_exc}"
                )
        logger.debug(f"[SourceProfiles] Loaded {len(result)} profiles from {path}")
        return result
    except Exception as exc:
        logger.warning(f"[SourceProfiles] Failed to load source_profiles.yaml: {exc}")
        return {}


def _normalize_name(name: str) -> str:
    """ソース名を正規化（大文字小文字・スペース・ハイフン・アンダースコア無視）。"""
    return name.strip().lower().replace(" ", "").replace("-", "").replace("_", "")


def find_profile(
    profiles: dict[str, SourceProfile], source_name: str
) -> Optional[SourceProfile]:
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
    profiles: dict[str, SourceProfile] | None = None,
    max_mentions: int = 2,
    name_field: str = "mention_style_short",
) -> list[str]:
    """evidence に存在するソースから最大 max_mentions 個の媒体名を返す。

    選択ルール（優先順）:
      1. can_authority_mention=true かつ authority_tier が高い（top > major > standard）
      2. 対比ペアを優先: JP ソース 1 本 + 海外ソース 1 本
      3. JP ソースがない場合: 海外ソースから異なるリージョン2本
      4. 海外ソースのみ1本 / JP ソースのみ1本 にフォールバック
      5. 0件の場合: 空リストを返す（媒体名言及なし）

    Args:
        sources_jp       : evidence の JP ソースリスト（SourceRef）
        sources_overseas : evidence の 非JP ソースリスト（SourceRef）
        profiles         : load 済み dict[str, SourceProfile]。None なら自動ロード。
        max_mentions     : 最大返却数（デフォルト 2）
        name_field       : 返す媒体名フィールド名。
                           デフォルト "mention_style_short" は後方互換。
                           台本では "display_name_speech"、記事では "display_name_article"
                           を呼び出し側で指定することを推奨 (F-8-1-A)。

    Returns:
        list[str]: 指定 name_field のリスト（最大 max_mentions 件）。
                   name_field の値が空の場合は mention_style_short にフォールバック。
    """
    if profiles is None:
        profiles = load_source_profiles()

    def _resolve_name(p: SourceProfile, fallback: str) -> str:
        # name_field を優先、空なら mention_style_short → fallback (source name) の順
        primary = p.get(name_field, "") or ""
        if primary:
            return primary
        secondary = p.get("mention_style_short", "") or ""
        if secondary:
            return secondary
        return fallback

    def _ranked(sources: "list[SourceRef]") -> list[tuple[int, str, str]]:
        """(tier_order, mention, source_name) のソート済みリスト。"""
        items: list[tuple[int, str, str]] = []
        seen_mentions: set[str] = set()
        for src in sources:
            p = find_profile(profiles, src.name)
            if not p:
                continue
            if not p.get("can_authority_mention", False):
                continue
            tier = _TIER_ORDER.get(p.get("authority_tier", "standard"), 2)
            mention = _resolve_name(p, src.name)
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


def get_mention_style_long(
    source_name: str, profiles: dict[str, SourceProfile] | None = None
) -> str:
    """mention_style_long を返す。プロファイルが見つからない場合は source_name をそのまま返す。"""
    if profiles is None:
        profiles = load_source_profiles()
    p = find_profile(profiles, source_name)
    if p:
        return p.get("mention_style_long", source_name) or source_name
    return source_name
