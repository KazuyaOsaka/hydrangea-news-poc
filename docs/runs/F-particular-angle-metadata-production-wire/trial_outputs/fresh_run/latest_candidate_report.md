# Hydrangea News — Latest Candidate Report

*Generated: 2026-05-31T10:49:31.913999+00:00*

---

## 0. Judge Model Resolution

- **requested:** `gemini-3.5-flash`
- **resolved:**  `gemini-3.5-flash`
- **reason:**    `requested_model_available`

---

## 1. Scheduled Slot-1 (scheduler output)

**ID:** `cls-c8876d474612` — Israel seizes strategic castle as it expands invasion of south Lebanon
**Score:** 71.7
**Bucket:** `coverage_gap`
**Sources:** JP=0, EN=2
**Judge result:** not_judged

## 2. Reranked Top Candidate (after judge boost)

**ID:** `cls-c8876d474612` — Israel seizes strategic castle as it expands invasion of south Lebanon
**Score:** 71.7
**Bucket:** `coverage_gap`
**Sources:** JP=0, EN=2
**Judge result:** not_judged

## 3. Final Slot-1 (used for generation)

**ID:** `cls-82101968fa87` — NYT: Trump sent revised proposal with toughened terms back to Iran
**Score:** 78.0
**Bucket:** `tech_geopolitics`
**Sources:** JP=0, EN=1
**Judge result:** `insufficient_evidence` (div=0.0, blind_spot=0.0, indirect_jp=5.0)
**Selection source:** `judged_flagship_f5:insufficient_evidence:score=78.0:divergence=0.0`

## 4. Publish Identity

| Field | Value |
|-------|-------|
| scheduled_slot1_id | `cls-c8876d474612` |
| final_selected_slot1_id | `cls-82101968fa87` |
| generated_event_id | `cls-c8876d474612` |
| published_event_id | `cls-c8876d474612` |
| selection_override_applied | `True` |
| override_reason | `judged_flagship_f5:insufficient_evidence:score=78.0:divergence=0.0` |

> **Override**: scheduler nominated `cls-c8876d474612` but FinalSelection promoted `cls-82101968fa87` (judged_flagship_f5:insufficient_evidence:score=78.0:divergence=0.0). The scheduled slot was marked consumed; the pool marks the generated event as published.
## 5. Why Final Slot-1 Won

- Judged by Gemini with `publishability_class=insufficient_evidence`
- divergence_score=0.0, blind_spot_global_score=0.0, indirect_japan_impact_score_judge=5.0
- Why it matters: 日本側の報道が確認できないため、トランプ氏による対イラン交渉条件の厳格化が日本に与える影響を分析するにはさらなる情報収集が必要である。
- Perspective gap: 日本側の報道データが提供されていないため、国内外の報道におけるフレーミングの差を特定することはできない。
- Selection source: judged_flagship_f5:insufficient_evidence:score=78.0:divergence=0.0
- semantic_coherence_score: 0.3786
- coherence_gate_passed: True
- candidate_blacklist_flags: []
- slot1_source_titles_present_jp: 0 / 0
- slot1_source_titles_present_en: 1 / 1
- slot1_coherence_input_quality: {'jp_titles_present_count': 0, 'overseas_titles_present_count': 1, 'missing_title_sources_count': 0}
- slot1_overlap_signals: ['direct_keyword:back,iran,nyt,proposal', 'year_neutral']

## 6. Skipped / Blocked Candidates

**Judged candidates (3 total):**

- `cls-82101968fa87` score=78.0 class=insufficient_evidence ← **SELECTED**
- `cls-101f08924f2b` score=75.2 class=insufficient_evidence — skipped: publishability_class=`insufficient_evidence` not eligible
- `cls-7a2ef22d7ef2` score=71.8 class=insufficient_evidence — skipped: publishability_class=`insufficient_evidence` not eligible

**Not-judged candidates (7 — excluded from slot-1 when judge ran):**

- `cls-c8876d474612` score=71.7 bucket=`coverage_gap` ← was scheduler's slot-1 choice
- `cls-3e9544fee58f` score=68.2 bucket=`coverage_gap`
- `cls-5bcf77445b2b` score=46.0 bucket=`sports`
- `cls-c7d507fc74e8` score=44.2 bucket=`coverage_gap`
- `cls-e555ec516d8e` score=44.2 bucket=`coverage_gap`
- ... and 2 more

## 10. Budget Mode & Publish Reserve

| Field | Value |
|-------|-------|
| run_mode | `publish_mode` |
| daily_budget_total | 1000 |
| exploration_budget_used | 26 |
| publish_reserve_budget | 15 |
| publish_reserve_preserved | True |
| stopped_exploration_due_to_publish_reserve | False |
| slot1_budget_guaranteed | True |

**Publish reserve:** **PRESERVED** ✓
**Slot-1 production budget:** **GUARANTEED** ✓

## 11. Audio & Video Render

| Field | Value |
|-------|-------|
| audio_render_enabled | `False` |
| video_render_enabled | `False` |
| audio_status | **SKIPPED** |
| video_status | **SKIPPED** |
| voiceover_path | `N/A` |
| review_mp4_path | `N/A` |
| render_manifest_path | `N/A` |
| total_duration_sec | N/A |
| placeholder_count | 0 |
| timing_mismatches | 0 |

---

*This report is generated automatically by the Hydrangea News pipeline.*