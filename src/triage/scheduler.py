"""Daily Programming Scheduler (Stage C)

1日最大5本の番組編成を組む層。
appraisal 済みの15本から、カテゴリ分散・話題分散・appraisal_type 分散を考慮して選ぶ。

Buckets (primary_bucket):
    breaking_shock          速報性の高い地政学・マクロショック
    japanese_person_abroad  日本人著名人の海外報道
    japan_abroad            日本の政治・経済の海外報道
    tech_geopolitics        AI/半導体等の技術覇権
    geopolitics             地政学・紛争・安全保障
    politics_economy        政治・経済の大型イベント
    sports                  スポーツ（経済角度含む）
    entertainment           エンタメ
    coverage_gap            海外注目・日本未報道
    mass_appeal             大衆的関心
    general                 その他

tags_multi (non-exclusive, appraisal が設定):
    politics_economy, geopolitics, japan_abroad, japanese_person_abroad,
    sports, entertainment, tech_geopolitics, coverage_gap, mass_appeal,
    personal_stakes
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from src.shared.models import DailySchedule, DailyScheduleEntry, ScoredEvent
from src.shared.logger import get_logger

logger = get_logger(__name__)

# ── 定数 ──────────────────────────────────────────────────────────────────────
SLOT_COUNT = 5
MAX_SAME_BUCKET = 2          # 同じ primary_bucket は最大2本まで
MAX_SAME_ENTITY = 2          # 同じ主要エンティティ（国・人物）は最大2本まで
MAX_SAME_APPRAISAL_TYPE = 2  # 同じ appraisal_type は最大2本まで

# mandatory 枠の検索範囲（全候補を走査すると極低スコア候補が選ばれるため上位に限定）
MANDATORY_SEARCH_LIMIT = 30

# 優先的に埋めるべきスロットグループ（必須枠）
# group_name, bucket_list, tags_multi_check
# tags_multi_check: None なら primary_bucket のみ, list なら tags_multi でも照合
_MANDATORY_GROUPS: list[tuple[str, list[str], list[str] | None]] = [
    ("japan_focus",          ["japanese_person_abroad", "japan_abroad"],                         None),
    ("geo_politics",         ["breaking_shock", "geopolitics", "politics_economy"],              None),
    ("lighter_angle",        ["tech_geopolitics", "sports", "entertainment", "coverage_gap"],    None),
    # personal_stakes OR mass_appeal: primary_bucket="mass_appeal" or "personal_stakes" in tags_multi
    ("personal_stakes_mass", ["mass_appeal"],                                                    ["personal_stakes"]),
]

# エンティティ重複検出: "entity_key" → 検出に使うキーワード群
_ENTITY_MARKERS: dict[str, list[str]] = {
    "iran":     ["iran", "iranian", "tehran"],
    "ukraine":  ["ukraine", "ukrainian", "zelensky", "kyiv"],
    "china":    ["china", "chinese", "beijing", "xi jinping"],
    "russia":   ["russia", "russian", "putin", "moscow", "kremlin"],
    "usa":      ["united states", "u.s. ", "trump", "biden", "harris", "washington dc"],
    "israel":   ["israel", "israeli", "netanyahu", "tel aviv", "gaza"],
    "ohtani":   ["ohtani", "大谷", "shohei ohtani"],
    "fed":      ["federal reserve", "fed rates", "jerome powell", "fomc"],
    "boj":      ["bank of japan", "boj ", "日銀", "日本銀行"],
    "tariff":   ["tariff war", "trade war", "import tariff", "tariff on"],
    "opec":     ["opec", "oil price", "crude oil price"],
}


def _detect_entities(title: str) -> set[str]:
    """タイトルから主要エンティティを検出する。"""
    t = title.lower()
    return {entity for entity, markers in _ENTITY_MARKERS.items() if any(m in t for m in markers)}


def _categorize_hold_back_reason(se: ScoredEvent) -> str:
    """appraisal_cautions と score_breakdown から hold_back_reason を分類する。

    hold_back_reason 候補:
      no_cross_lang_support   — sources_en が空、日英比較の根拠なし
      weak_japan_angle        — japan_relevance が低い、または EN-only
      low_evidence            — 全編集軸が弱い（pg=0, bip=0 など）
      duplicate_story         — story fingerprint で重複検出
      weak_structural_insight — background_inference_potential=0
      low_novelty             — 新規性がない（pool 内の既存ストーリーの方が上質）
      pool_story_already_better — pool に同一 fingerprint でより高スコアが存在
      unknown                 — 上記に当てはまらない
    """
    cautions = se.appraisal_cautions or ""
    bd = se.score_breakdown

    # sources_en が空 → 日英比較根拠なし
    if "sources_en=empty" in cautions or not se.event.sources_en:
        return "no_cross_lang_support"

    # EN-only + low Japan relevance
    if "low_japan_relevance" in cautions or "EN-only" in cautions:
        return "weak_japan_angle"

    # japan_relevance スコアが低い
    jr = bd.get("editorial:japan_relevance_score", 0.0)
    if isinstance(jr, (int, float)) and jr < 3:
        return "weak_japan_angle"

    # 全編集軸が弱い
    if "all axes weak" in cautions or "all_axes_weak" in cautions:
        return "low_evidence"

    # background_inference_potential が 0
    bip = bd.get("editorial:background_inference_potential", 0.0)
    if isinstance(bip, (int, float)) and bip == 0 and not se.event.sources_en:
        return "weak_structural_insight"

    # pool イベントで重複フィンガープリント
    if se.from_recent_pool and se.freshness_decay < 1.0:
        return "pool_story_already_better"

    return "low_evidence"


def _passes_quality_floor(se: ScoredEvent) -> bool:
    """
    Global quality floor — 全フェーズ（mandatory / best_score / relaxed / fallback）に適用。

    以下の候補は selected に入れず held_back へ回す:
    - safety gate で appraisal が能動的に抑制されており、かつ appraisal_type もスコアもゼロ
      （appraisal_cautions が "[抑制]" で始まる AND appraisal_type is None AND eas==0）

    "[抑制]" は appraisal システムが明確に不適と判断した候補:
      - sources_en=empty + no_en_view → 比較根拠が皆無
      - EN-only + low_japan_relevance → 日本視聴者向けに成立しない
      - all_axes_weak (pg=0, cg<3, bip=0) → 編集軸が全て弱い

    appraisal_type が設定されている場合（例: Media Blind Spot + [抑制]ラベル）は通過する。
    appraisal 未適用（appraisal_cautions=None）の候補はデフォルトで通過する。
    """
    cautions = se.appraisal_cautions or ""
    if (
        cautions.startswith("[抑制]")
        and se.appraisal_type is None
        and se.editorial_appraisal_score == 0.0
    ):
        return False
    return True


def _publish_priority(entry: DailyScheduleEntry) -> float:
    """
    配信優先度スコアを返す（高いほど早く配信される）。

    優先基準（降順）:
    1. safety gate 抑制なし（抑制候補は最後尾）
    2. appraisal が効いている（appraisal_type あり）
    3. appraisal_hook あり
    4. editorial_appraisal_score が高い
    5. breaking_shock は速報として前に出す
    6. triage score（正規化）
    """
    cautions = entry.appraisal_cautions or ""
    # safety gate 抑制候補は最後尾（-1000 台）
    if cautions.startswith("[抑制]") and entry.appraisal_type is None:
        return -1000.0 + entry.score * 0.01

    priority = 0.0

    if entry.appraisal_type is not None:
        priority += 100.0
    if entry.appraisal_hook is not None:
        priority += 20.0

    priority += entry.editorial_appraisal_score * 10.0

    # 速報は優先配信
    if entry.primary_bucket == "breaking_shock":
        priority += 50.0

    # triage score（正規化して補助）
    priority += entry.score * 0.1

    return priority


def scored_event_to_schedule_entry(
    se: ScoredEvent,
    rank_in_candidates: int,
    selection_reason: str = "",
    rejection_reason: Optional[str] = None,
    published: bool = False,
    published_at: Optional[str] = None,
    slot_status: str = "selected",
) -> DailyScheduleEntry:
    """ScoredEvent から DailyScheduleEntry を生成する共通ヘルパー。

    build_daily_schedule と _maybe_upgrade_unpublished_slots の両方でこの
    関数を使うことで、フィールドの抜け漏れが起きないようにする。
    今後 DailyScheduleEntry にフィールドが追加された場合も、ここだけ更新すればよい。

    slot_status:
        "selected"   — selected リストに入る（未配信）
        "published"  — 配信済み
        "held_back"  — quality floor 未達（held_back リストに入る）
    """
    return DailyScheduleEntry(
        rank_in_candidates=rank_in_candidates,
        event_id=se.event.id,
        title=se.event.title[:80],
        score=round(se.score, 2),
        primary_bucket=se.primary_bucket,
        editorial_tags=list(se.editorial_tags),
        tags_multi=list(se.tags_multi),
        selection_reason=selection_reason,
        rejection_reason=rejection_reason,
        published=published,
        published_at=published_at,
        slot_status=slot_status,
        appraisal_type=se.appraisal_type,
        appraisal_hook=se.appraisal_hook,
        appraisal_reason=se.appraisal_reason,
        appraisal_cautions=se.appraisal_cautions,
        editorial_appraisal_score=round(se.editorial_appraisal_score, 3),
        event_snapshot=se.model_dump(mode="json"),
        source_regions=sorted(se.event.sources_by_locale.keys()) if se.event.sources_by_locale else [],
        source_languages=sorted({
            ref.language
            for refs in se.event.sources_by_locale.values()
            for ref in refs
            if ref.language
        }),
        why_this_region_mix=se.score_breakdown.get("why_this_region_mix"),  # type: ignore[arg-type]
        regional_contrast_reason=se.score_breakdown.get("regional_contrast_reason"),  # type: ignore[arg-type]
        story_fingerprint=se.story_fingerprint,
        freshness_decay=round(se.freshness_decay, 3),
        from_recent_pool=se.from_recent_pool,
        pool_created_at=se.pool_created_at,
    )


def _matches_mandatory_group(
    se: ScoredEvent,
    bucket_list: list[str],
    tags_multi_check: list[str] | None,
) -> bool:
    """mandatory group に候補がマッチするか判定する。

    - primary_bucket が bucket_list に含まれる、または
    - tags_multi_check が指定されており、そのいずれかが se.tags_multi に含まれる
    """
    if se.primary_bucket in bucket_list:
        return True
    if tags_multi_check:
        for tag in tags_multi_check:
            if tag in se.tags_multi:
                return True
    return False


def build_daily_schedule(
    ranked: list[ScoredEvent],
    max_slots: int = SLOT_COUNT,
    date_str: str | None = None,
) -> DailySchedule:
    """appraisal 済み候補リストから、多様性ルールに基づく1日の番組表を生成する。

    Algorithm:
        Phase 1: Mandatory 枠（4グループ × 1本）を優先的に埋める
                 - japan_focus    (japan_abroad / japanese_person_abroad)
                 - geo_politics   (breaking_shock / geopolitics / politics_economy)
                 - lighter_angle  (tech_geopolitics / sports / entertainment / coverage_gap)
                 - personal_stakes_mass (mass_appeal bucket OR personal_stakes tag)
        Phase 2: 残り枠をスコア順で埋める
                 （MAX_SAME_BUCKET / MAX_SAME_ENTITY / MAX_SAME_APPRAISAL_TYPE を守る）
        Phase 3: Phase 2 で埋まらなければ bucket 制約を緩めて補完
        Phase 4: entity 制約も緩める（最終手段）

    Breaking news 例外:
        本体ニュース + 市場インパクトが同 appraisal_type "Perspective Inversion" になる場合など、
        超大型 breaking news は同 bucket/entity を 2本まで許容（既存 MAX_SAME_BUCKET=2 で対応済）。
    """
    today = date_str or date.today().isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()

    if not ranked:
        return DailySchedule(
            date=today, generated_at=now_iso, total_candidates=0,
            selected=[], rejected=[], diversity_rules_applied=["no_candidates"],
            coverage_summary={},
        )

    # ── 状態管理 ──────────────────────────────────────────────────────────────
    selected_ids: set[str] = set()
    selected_list: list[tuple[int, ScoredEvent, str]] = []  # (rank_idx, event, reason)
    bucket_count: dict[str, int] = {}
    entity_count: dict[str, int] = {}
    appraisal_type_count: dict[str, int] = {}
    # Region diversity tracking（選出済み地域セット）
    selected_regions: set[str] = set()
    # Story fingerprint dedup — prevents same story appearing twice in 5 slots
    # (handles time-lag pool events that may have different event_ids but same story)
    selected_fingerprints: set[str] = set()
    duplicate_fingerprint_count: int = 0
    # Quality floor 未達候補の追跡（held_back リスト構築用）
    held_back_ids: set[str] = set()
    held_back_candidates: list[tuple[int, ScoredEvent, str]] = []  # (rank_idx, event, reason)

    def _track_held_back(rank_idx: int, se: ScoredEvent) -> None:
        """Quality floor 未達候補を held_back リストに追加する（重複なし）。"""
        if se.event.id not in held_back_ids:
            held_back_ids.add(se.event.id)
            structured_reason = _categorize_hold_back_reason(se)
            caution_text = (se.appraisal_cautions or "quality_floor_fail").replace("[抑制] safety gate: ", "")
            held_back_candidates.append(
                (rank_idx, se, f"quality_floor:{structured_reason}:{caution_text[:80]}")
            )

    def _can_add(
        se: ScoredEvent,
        relax_bucket: bool = False,
        relax_entity: bool = False,
        relax_appraisal_type: bool = False,
    ) -> tuple[bool, str]:
        nonlocal duplicate_fingerprint_count
        bucket = se.primary_bucket
        if not relax_bucket and bucket_count.get(bucket, 0) >= MAX_SAME_BUCKET:
            return False, f"bucket_limit:{bucket}({bucket_count[bucket]}/{MAX_SAME_BUCKET})"
        if not relax_entity:
            for ent in _detect_entities(se.event.title):
                if entity_count.get(ent, 0) >= MAX_SAME_ENTITY:
                    return False, f"entity_limit:{ent}({entity_count[ent]}/{MAX_SAME_ENTITY})"
        if not relax_appraisal_type and se.appraisal_type:
            at = se.appraisal_type
            if appraisal_type_count.get(at, 0) >= MAX_SAME_APPRAISAL_TYPE:
                return False, f"appraisal_type_limit:{at}({appraisal_type_count[at]}/{MAX_SAME_APPRAISAL_TYPE})"
        # Story fingerprint dedup: prevent same story in 5 slots
        # (handles pool events with different event_ids but same underlying story)
        fp = se.story_fingerprint
        if fp and fp in selected_fingerprints:
            duplicate_fingerprint_count += 1
            return False, f"duplicate_story_fingerprint:{fp[:8]}"
        return True, ""

    def _commit(rank_idx: int, se: ScoredEvent, reason: str) -> None:
        selected_ids.add(se.event.id)
        selected_list.append((rank_idx, se, reason))
        b = se.primary_bucket
        bucket_count[b] = bucket_count.get(b, 0) + 1
        for ent in _detect_entities(se.event.title):
            entity_count[ent] = entity_count.get(ent, 0) + 1
        if se.appraisal_type:
            at = se.appraisal_type
            appraisal_type_count[at] = appraisal_type_count.get(at, 0) + 1
        # Region tracking
        for r in se.score_breakdown.get("source_regions", []):
            selected_regions.add(r)
        # Fingerprint tracking
        fp = se.story_fingerprint
        if fp:
            selected_fingerprints.add(fp)

    # ── Phase 1: Mandatory 枠 ─────────────────────────────────────────────────
    mandatory_filled: dict[str, bool] = {}
    rules_applied: list[str] = []

    for group_name, target_buckets, tags_multi_check in _MANDATORY_GROUPS:
        if len(selected_list) >= max_slots:
            break
        # mandatory 検索は上位 MANDATORY_SEARCH_LIMIT 本に限定する
        # 全候補を走査すると極低スコア候補が選ばれるため
        for rank_idx, se in enumerate(ranked[:MANDATORY_SEARCH_LIMIT]):
            if se.event.id in selected_ids:
                continue
            if not _matches_mandatory_group(se, target_buckets, tags_multi_check):
                continue
            # quality floor: 弱い候補は mandatory 枠に入れない → held_back へ
            if not _passes_quality_floor(se):
                logger.debug(
                    f"[Scheduler] quality_floor rejected #{rank_idx+1} for {group_name}: "
                    f"{se.event.title[:40]} "
                    f"(cautions={se.appraisal_cautions!r})"
                )
                _track_held_back(rank_idx, se)
                continue
            ok, rej = _can_add(se)
            if ok:
                match_detail = (
                    se.primary_bucket
                    if se.primary_bucket in target_buckets
                    else f"tags_multi:{[t for t in (tags_multi_check or []) if t in se.tags_multi]}"
                )
                _commit(rank_idx, se, f"mandatory:{group_name}({match_detail})")
                mandatory_filled[group_name] = True
                rules_applied.append(
                    f"mandatory:{group_name} → {match_detail} "
                    f"(#{rank_idx+1}, score={se.score:.1f}, "
                    f"appraisal={se.appraisal_type or 'none'})"
                )
                break
        else:
            mandatory_filled[group_name] = False
            rules_applied.append(f"mandatory_miss:{group_name} (no eligible candidate)")

    # ── Phase 2: Region-aware ソート + スコア順で残り枠を埋める ─────────────
    # Phase 1 完了後の selected_regions に基づき、pilot 地域の novelty bonus を加算。
    # ボーナスは最大 2.5pt（弱候補を押し上げず、同スコア帯での tie-breaker として機能）。
    _PILOT_SCHED = frozenset({"middle_east", "europe", "east_asia"})
    _NON_WESTERN_SCHED = frozenset({"middle_east", "east_asia"})

    def _region_novelty_bonus(se: ScoredEvent) -> float:
        """Phase 1 完了時点での selected_regions に基づく地域新規性ボーナス。"""
        bd = se.score_breakdown
        se_regions = set(bd.get("source_regions", []))
        bonus = 0.0
        # 選出済みにない pilot 地域を持つ候補を優先
        new_pilots = (se_regions & _PILOT_SCHED) - selected_regions
        if new_pilots:
            bonus += 1.5
        # JP + 非西側の組み合わせで未選出のもの
        if ("japan" in se_regions
                and (se_regions & _NON_WESTERN_SCHED)
                and not (selected_regions & _NON_WESTERN_SCHED)):
            bonus += 1.0
        return min(bonus, 2.5)

    phase2_order = sorted(
        enumerate(ranked),
        key=lambda x: x[1].score + _region_novelty_bonus(x[1]),
        reverse=True,
    )
    region_diversity_applied = False
    for rank_idx, se in phase2_order:
        if len(selected_list) >= max_slots:
            break
        if se.event.id in selected_ids:
            continue
        # quality floor: 全フェーズで適用 — 弱い候補は held_back へ
        if not _passes_quality_floor(se):
            _track_held_back(rank_idx, se)
            continue
        ok, _ = _can_add(se)
        if ok:
            bonus = _region_novelty_bonus(se)
            reason_suffix = f",region_bonus={bonus:.1f}" if bonus > 0.1 else ""
            _commit(rank_idx, se, f"best_score:{se.primary_bucket}(#{rank_idx+1}{reason_suffix})")
            if bonus > 0.1:
                region_diversity_applied = True
    if region_diversity_applied:
        rules_applied.append("region_diversity: pilot region novelty bonus applied in Phase 2")

    # ── Phase 3: bucket 制約を緩めて補完 ─────────────────────────────────────
    if len(selected_list) < max_slots:
        rules_applied.append("relax:bucket_constraint (insufficient_quality_candidates)")
        for rank_idx, se in enumerate(ranked):
            if len(selected_list) >= max_slots:
                break
            if se.event.id in selected_ids:
                continue
            # quality floor: Phase 3 でも適用
            if not _passes_quality_floor(se):
                _track_held_back(rank_idx, se)
                continue
            ok, _ = _can_add(se, relax_bucket=True)
            if ok:
                _commit(rank_idx, se, f"relaxed_fill:{se.primary_bucket}(#{rank_idx+1})")

    # ── Phase 4: entity 制約も緩める（最終手段） ─────────────────────────────
    if len(selected_list) < max_slots:
        rules_applied.append("relax:entity_constraint (final_fallback)")
        for rank_idx, se in enumerate(ranked):
            if len(selected_list) >= max_slots:
                break
            if se.event.id in selected_ids:
                continue
            # quality floor: Phase 4 でも適用 — 弱い候補は held_back のみ、selected には入れない
            if not _passes_quality_floor(se):
                _track_held_back(rank_idx, se)
                continue
            # Story fingerprint dedup は最終手段でも維持する（重複投稿防止は最優先）
            fp_4 = se.story_fingerprint
            if fp_4 and fp_4 in selected_fingerprints:
                duplicate_fingerprint_count += 1
                continue
            _commit(rank_idx, se, f"fallback_fill:{se.primary_bucket}(#{rank_idx+1})")

    # ── Selected entries ──────────────────────────────────────────────────────
    selected_entries = [
        scored_event_to_schedule_entry(se, rank_in_candidates=rank_idx + 1, selection_reason=reason)
        for rank_idx, se, reason in selected_list
    ]

    # ── Publish order: 編集価値の高い候補を前に配置 ───────────────────────────
    # 選択と配信順は分離する。appraisal が効いている・breaking_shock・score が高い候補を先頭に。
    selected_entries.sort(key=_publish_priority, reverse=True)
    rules_applied.append(
        "publish_order: "
        + " > ".join(
            f"{e.event_id[:8]}({e.primary_bucket},pri={_publish_priority(e):.1f})"
            for e in selected_entries
        )
    )

    # ── Held-back entries（quality floor 未達、最大10件） ─────────────────────
    # selected / rejected とは分離して記録。「なぜ出さなかったか」の透明性を確保する。
    held_back_entries: list[DailyScheduleEntry] = [
        scored_event_to_schedule_entry(
            se,
            rank_in_candidates=rank_idx + 1,
            rejection_reason=reason,
            slot_status="held_back",
        )
        for rank_idx, se, reason in held_back_candidates[:10]
    ]

    # ── Open slots: quality 候補不足で埋まらなかった枠数 ─────────────────────
    open_slots = max(0, max_slots - len(selected_list))
    if open_slots > 0:
        rules_applied.append(
            f"open_slots:{open_slots} "
            f"(quality_floor_held_back={len(held_back_candidates)}, "
            f"insufficient_quality_candidates)"
        )

    # ── Rejected entries（上位20件から非採用を最大10件） ─────────────────────
    # held_back と重複しないよう selected_ids_final + held_back_ids を除外する
    selected_ids_final = {e.event_id for e in selected_entries}
    excluded_from_rejected = selected_ids_final | held_back_ids
    rejected_entries: list[DailyScheduleEntry] = []
    for rank_idx, se in enumerate(ranked[:20]):
        if se.event.id in excluded_from_rejected:
            continue
        # 非採用理由を再計算
        ok, rej_reason = _can_add(se, relax_bucket=False, relax_entity=False)
        if ok:
            rej_reason = "not_reached_in_greedy"
        rejected_entries.append(
            scored_event_to_schedule_entry(se, rank_in_candidates=rank_idx + 1, rejection_reason=rej_reason)
        )
        if len(rejected_entries) >= 10:
            break

    # ── Coverage summary ──────────────────────────────────────────────────────
    coverage: dict[str, int] = {}
    for e in selected_entries:
        coverage[e.primary_bucket] = coverage.get(e.primary_bucket, 0) + 1

    # region_coverage: どの地域ソース由来の候補が採用されたか（透明性）
    region_coverage: dict[str, int] = {}
    for e in selected_entries:
        for region in e.source_regions:
            region_coverage[region] = region_coverage.get(region, 0) + 1

    # region diversity サマリを rules_applied に追記（透明性）
    pilot_in_selected = [r for r in selected_regions if r in {"middle_east", "europe", "east_asia"}]
    if pilot_in_selected:
        rules_applied.append(f"region_diversity_selected: {', '.join(sorted(pilot_in_selected))}")
    else:
        rules_applied.append("region_diversity_selected: none (pilot regions not selected)")

    # Rolling window / fingerprint dedup サマリ
    pool_selected = [e for e in selected_entries if e.from_recent_pool]
    if pool_selected:
        rules_applied.append(
            f"rolling_window_pool_selected: {len(pool_selected)} event(s) from recent pool "
            f"({[e.event_id[:12] for e in pool_selected]})"
        )
    if duplicate_fingerprint_count > 0:
        rules_applied.append(
            f"fingerprint_dedup_in_session: {duplicate_fingerprint_count} duplicate(s) suppressed"
        )

    logger.info(
        f"[Scheduler] Built daily schedule for {today}: "
        f"selected={len(selected_entries)}, open_slots={open_slots}, "
        f"held_back={len(held_back_entries)}, "
        f"buckets={list(coverage.keys())}, "
        f"regions={list(region_coverage.keys())}, "
        f"pilot_regions_selected={pilot_in_selected}, "
        f"mandatory_filled={mandatory_filled}, "
        f"pool_selected={len(pool_selected)}, "
        f"fingerprint_dedup={duplicate_fingerprint_count}"
    )

    return DailySchedule(
        date=today,
        generated_at=now_iso,
        total_candidates=len(ranked),
        selected=selected_entries,
        rejected=rejected_entries,
        held_back=held_back_entries,
        open_slots=open_slots,
        diversity_rules_applied=rules_applied,
        coverage_summary=coverage,
        region_coverage=region_coverage,
    )


# ── Flagship クラス定数 ─────────────────────────────────────────────────────
FLAGSHIP_LINKED_JP_GLOBAL  = "flagship_linked_jp_global"
FLAGSHIP_BLIND_SPOT_GLOBAL = "flagship_blind_spot_global"


def get_flagship_class(se: ScoredEvent) -> str | None:
    """候補の flagship クラスを返す。flagship 条件を満たさない場合は None。

    flagship_linked_jp_global: JP+EN ソース両方あり、かつ強い perspective gap または
        高い japan_relevance × global_attention の組み合わせを持つ。
        → 「JPと世界の視点が交差する、本命のリンク済みストーリー」

    flagship_blind_spot_global: "Blind Spot Global" appraisal が付き、
        indirect_japan_impact が高く国際的注目も高い EN-only 候補。
        → 「JP記事はないが日本への間接的インパクトが強いグローバル重要案件」
    """
    bd = se.score_breakdown
    pg   = float(bd.get("editorial:perspective_gap_score", 0.0))
    jr   = float(bd.get("editorial:japan_relevance_score", 0.0))
    ga   = float(bd.get("editorial:global_attention_score", 0.0))
    ijai = float(bd.get("editorial:indirect_japan_impact_score", 0.0))
    bip  = float(bd.get("editorial:background_inference_potential", 0.0))

    has_jp_src = bool(se.event.sources_jp)
    has_en_src = bool(se.event.sources_en)

    # Hard blocks (非 flagship の絶対条件)
    if not has_en_src:
        return None
    if bip == 0.0 and ijai < 3.0:
        return None
    if jr < 2.0 and ijai < 3.0:
        return None

    # flagship_blind_spot_global: Blind Spot Global appraisal + 強い間接インパクト
    if (
        se.appraisal_type == "Blind Spot Global"
        and ijai >= 4.0
        and ga >= 5.0
    ):
        return FLAGSHIP_BLIND_SPOT_GLOBAL

    # flagship_linked_jp_global: JP+EN 両ソース + 強い perspective gap or 高 JR×GA
    if (
        has_jp_src
        and has_en_src
        and (pg >= 4.0 or (jr >= 6.0 and ga >= 4.0))
    ):
        return FLAGSHIP_LINKED_JP_GLOBAL

    return None


def _passes_flagship_gate(se: ScoredEvent) -> tuple[bool, str]:
    """
    候補が auto-generation に値する flagship 水準かを判定する。

    Returns:
        (passes: bool, reason: str)
        passes=True → auto-generation 許可
        passes=False → flagship 水準に満たない → generation をブロック

    用途: main.py の _generate_outputs 呼び出し前にチェックする。
    スケジューリング（何を番組表に載せるか）とは独立。
    """
    flagship_class = get_flagship_class(se)
    if flagship_class is not None:
        return True, flagship_class
    # 非 flagship — 理由を構造化して返す
    bd = se.score_breakdown
    jr   = float(bd.get("editorial:japan_relevance_score", 0.0))
    ga   = float(bd.get("editorial:global_attention_score", 0.0))
    pg   = float(bd.get("editorial:perspective_gap_score", 0.0))
    ijai = float(bd.get("editorial:indirect_japan_impact_score", 0.0))
    bip  = float(bd.get("editorial:background_inference_potential", 0.0))
    has_en_src = bool(se.event.sources_en)

    if not has_en_src:
        return False, "no_en_sources"
    if bip == 0.0 and ijai < 3.0:
        return False, f"no_depth:bip=0,ijai={ijai:.1f}"
    if jr < 2.0 and ijai < 3.0:
        return False, f"weak_japan:jr={jr:.1f},ijai={ijai:.1f}"
    # ある程度の evidence はあるが flagship 水準に届かない
    return False, f"below_flagship:pg={pg:.1f},jr={jr:.1f},ga={ga:.1f},ijai={ijai:.1f}"


def get_next_unpublished(schedule: DailySchedule) -> Optional[DailyScheduleEntry]:
    """今日の番組表から未配信の次の1本を返す。全て配信済みなら None。"""
    for entry in schedule.selected:
        if not entry.published:
            return entry
    return None


def mark_published(
    schedule: DailySchedule,
    event_id: str,
    published_at: str | None = None,
) -> DailySchedule:
    """指定 event_id を配信済みにマークした新しい DailySchedule を返す。"""
    ts = published_at or datetime.now(timezone.utc).isoformat()
    new_selected = []
    for entry in schedule.selected:
        if entry.event_id == event_id and not entry.published:
            new_selected.append(entry.model_copy(update={
                "published": True,
                "published_at": ts,
                "slot_status": "published",
            }))
        else:
            new_selected.append(entry)
    return schedule.model_copy(update={"selected": new_selected})
