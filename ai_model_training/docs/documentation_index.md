# Documentation Index

This index is the current entry point for the `ai_model_training` documentation set.

It separates stable project docs from current evidence reports. Some early Markdown files and the root `README.md` contain legacy encoding damage and first-round wording, so they should be treated as historical templates unless a newer report is listed here.

## Current Status First

Read these files first when you need the current project state:

| Purpose | File |
| --- | --- |
| Current concise status | `docs/current_project_status.md` |
| Active report evidence map | `reports/active_reports_evidence_index.md` |
| Active report audit | `reports/thirty_fourth_round_active_reports_evidence_audit.md` |
| Dataset status decision report | `reports/current_dataset_status_report.md` |
| Current model status summary | `reports/project_current_model_status_summary.md` |
| Demo model boundary | `reports/demo_model_boundary_statement.md` |
| Frontend hint policy | `reports/frontend_demo_model_hint_policy.md` |
| Defense talking points | `reports/defense_talking_points_model_limitations.md` |

## Current Phone Line Evidence

| Topic | Current Evidence |
| --- | --- |
| Old Phone expanded dataset status | `metadata/phone_dataset_status.yaml`, `reports/current_dataset_status_report.md` |
| Original RiceSeg preview_200 manual result | `reports/riceseg_preview_200_manual_review_gate_report.md`, `reports/riceseg_preview_200_manual_review_completed_analysis_report.md` |
| Revised RiceSeg preview_200 v0.1 gate | `reports/thirty_second_round_a_riceseg_revised_preview200_gate_report.md` |
| Revised preview pending notice | `reports/riceseg_preview_200_revised_v0_1_pending_manual_review_notice.md` |
| Revised preview machine check | `reports/riceseg_preview_200_revised_v0_1_dataset_check.md`, `reports/riceseg_preview_200_revised_v0_1_artifact_completeness_check.md` |

Current Phone hold line:

- old `rice_phone_rgb_expanded`: historical reference only.
- original `riceseg_preview_200`: human review completed, gate `WARNING`.
- revised `riceseg_preview_200_revised_v0_1`: machine check passed, revised manual gate `PENDING`.
- no preview_500 expansion, training, backend integration, or formal dataset claim until revised manual gate passes.

## Current UAV Line Evidence

| Topic | Current Evidence |
| --- | --- |
| UAV BLB registry | `metadata/uav_blb_model_registry.yaml` |
| Current UAV A/B report | `reports/thirty_second_round_b_uav_blb_apples_to_apples_ab_eval_report.md` |
| Locked A/B comparison | `reports/uav_blb_ab_eval_comparison.md`, `reports/uav_blb_ab_eval_comparison.json` |
| strict408 gate | `reports/uav_blb_strict408_v0_2_candidate_gate_report.md` |
| strict408 vs exp408 comparison | `reports/uav_blb_strict408_v0_2_vs_exp408_epoch5_comparison.md` |
| Hard-case follow-up | `reports/uav_blb_zero_detection_error_analysis.md`, `reports/uav_blb_hard_case_review_plan.md` |

Current UAV hold line:

- UAV remains the stronger current demo direction.
- `experimental_408_epoch5` remains the active optional experimental candidate.
- `strict408_v0_2_controlled` remains reference-only because the locked gate is `WARNING`.
- no backend default replacement and no formal model claim.

## Stable Reference Docs

These files are still useful as project reference material:

| Area | Files |
| --- | --- |
| Dataset layout | `docs/dataset_structure.md`, `docs/uav_multispectral_dataset_plan.md` |
| Labeling and classes | `docs/class_system.md`, `docs/labeling_rules.md` |
| Training/evaluation concepts | `docs/training_pipeline.md`, `docs/experiment_plan.md`, `docs/validation_metrics.md` |
| Script usage | `docs/script_usage.md` |
| Backend fields | `docs/backend_integration_fields.md` |
| Delivery package | `docs/model_delivery_package.md` |
| Error analysis | `docs/error_analysis_template.md` |
| Missing real data checklist | `docs/missing_real_data_checklist.md` |

Note: several of these docs were written in early rounds and may describe scaffolding-stage boundaries. Prefer the current evidence reports above for actual project status.

## Templates

| Template | File |
| --- | --- |
| Phone collection CSV | `docs/phone_collection_template.csv` |
| UAV collection CSV | `docs/uav_collection_template.csv` |

## Cleanup And Archive Evidence

| Purpose | File |
| --- | --- |
| Historical cleanup dry-run | `reports/thirty_third_round_c_historical_report_cleanup_plan.md` |
| Archive execution report | `reports/thirty_third_round_d_historical_report_archive_execution_report.md` |
| Cleanup inventory | `reports/report_cleanup_inventory.md` |
| Cleanup dry-run plan | `reports/report_cleanup_dry_run_plan.md` |
| Archive manifest | `reports/report_cleanup_archive_manifest.md` |

Current archive state:

- active `ARCHIVE_CANDIDATE`: `0`
- frozen `NEEDS_REVIEW`: `22`
- archived files under `reports/_archive/`: `52`

## What Not To Treat As Current

Do not treat the following as current-state authority without cross-checking the current reports:

- root `README.md`, because it contains early-round wording and legacy encoding damage.
- early round delivery reports such as `second_round_delivery_report.md` and `third_round_smoke_delivery_report.md`.
- historical Phone experimental reports that predate the `data_quality_suspect` decision.
- strict408 training/validation outputs alone, because the gate decision remains `WARNING`.

## Recommended Reading Order

1. `docs/current_project_status.md`
2. `reports/current_dataset_status_report.md`
3. `reports/project_current_model_status_summary.md`
4. `reports/active_reports_evidence_index.md`
5. Phone or UAV specific reports depending on the task.
