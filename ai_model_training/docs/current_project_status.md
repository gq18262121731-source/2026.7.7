# Current Project Status

This page is a concise current-state summary for the AI model training branch.

Last organized: 2026-06-29.

## Overall Position

The project is split into two active lines:

- Phone close-range disease detection.
- UAV BLB disease detection on RGB preview renders from UAV multispectral data.

The current rule is gate-first:

- no dataset expansion without a data gate.
- no training without a data gate.
- no backend promotion without a model gate.
- no formal model claim for smoke or experimental routes.

## Phone Line

Current status: data-route rebuild, not training-ready.

### Old Phone Expanded Dataset

Dataset:

- `datasets/rice_phone_rgb_expanded`

Current decision:

- status: `data_quality_suspect`
- keep as historical evidence only.
- do not use for backend upgrade.
- do not continue blind long-train / 768 / yolov8s escalation.

Primary evidence:

- `metadata/phone_dataset_status.yaml`
- `reports/current_dataset_status_report.md`

### Original RiceSeg preview_200

Dataset:

- `datasets/rice_phone_rgb_riceseg_preview_200`

Current decision:

- human review completed: `80 / 80`
- gate: `WARNING`
- obvious error count: `13`
- obvious error ratio: `0.1625`
- dominant issues: `mask_noise`, `over_fragmented`

Primary evidence:

- `reports/riceseg_preview_200_manual_review_gate_report.md`
- `reports/riceseg_preview_200_manual_review_completed_analysis_report.md`

### Revised RiceSeg preview_200 v0.1

Dataset:

- `datasets/rice_phone_rgb_riceseg_preview_200_revised_v0_1`

Current decision:

- machine check: passed.
- review package: exists.
- revised manual gate: `PENDING`.
- preview_500 expansion: not allowed.
- training: not allowed.
- backend integration: not allowed.

Primary evidence:

- `reports/thirty_second_round_a_riceseg_revised_preview200_gate_report.md`
- `reports/riceseg_preview_200_revised_v0_1_dataset_check.md`
- `reports/riceseg_preview_200_revised_v0_1_pending_manual_review_notice.md`

## UAV Line

Current status: strongest current demo direction, still experimental.

Current active optional candidate:

- `experimental_408_epoch5`

Current hold line:

- keep as optional experimental candidate.
- do not present as formal.
- do not claim true multichannel multispectral modeling.
- do not replace backend default route without explicit approval.

Primary evidence:

- `metadata/uav_blb_model_registry.yaml`
- `reports/project_current_model_status_summary.md`
- `reports/thirty_second_round_b_uav_blb_apples_to_apples_ab_eval_report.md`

### strict408_v0_2_controlled

Current decision:

- locked A/B gate: `WARNING`.
- same-eval metrics improved, but zero-detection behavior and historical comparison prevent promotion.
- reference-only; not an active candidate replacement.

Primary evidence:

- `reports/uav_blb_strict408_v0_2_candidate_gate_report.md`
- `reports/uav_blb_strict408_v0_2_vs_exp408_epoch5_comparison.md`
- `reports/uav_blb_ab_eval_comparison.md`

## Demo And Backend Boundary

Current demo safety rules:

- smoke is not formal.
- experimental is not formal.
- `crop_object` must not be described as disease.
- `formal_metric_available=false` remains in effect for current optional disease routes.
- outputs are assistive recognition only, not pesticide prescription or mandatory agronomic action advice.

Primary evidence:

- `reports/demo_model_boundary_statement.md`
- `reports/frontend_demo_model_hint_policy.md`
- `reports/defense_talking_points_model_limitations.md`

## Documentation Map

Use this file as the quick status page.

Use `docs/documentation_index.md` as the full document map.

Use `reports/active_reports_evidence_index.md` as the full evidence report index.

## Current Next Steps

Recommended next gated work:

1. Phone: complete human review for revised `riceseg_preview_200_revised_v0_1`.
2. Phone: only if revised gate passes, consider preview_500 expansion.
3. UAV: review strict408 zero-detection hard cases before any promotion discussion.
4. Demo/defense: keep formal, experimental, smoke, crop-object, and disease wording separate.

## Boundary Confirmation For This Documentation Pass

- No dataset files modified.
- No label files modified.
- No weight files modified.
- No backend files modified.
- No real `.env` files modified.
- No training run.
- No new weights generated.
- No archive, delete, move, or rename operation.
- No `git add` or commit.
