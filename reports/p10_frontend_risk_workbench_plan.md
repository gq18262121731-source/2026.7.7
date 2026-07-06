# P10 Frontend Risk Workbench Plan

Date: 2026-07-05  
Planning status: Draft  
Depends on: Frozen P9 rule-based UAV index analysis and multisource risk fusion

## 1. P10 Objective

Integrate P9 UAV index anomaly analysis and multisource risk fusion into the collaborative inspection workbench and inspection report display.

P10 must remain an experimental auxiliary display layer. It must not present formal agricultural diagnosis, formal disease probability, pesticide prescription, or dosage recommendations.

## 2. Recommended Scope

### 2.1 Collaborative Inspection Workbench Display

- Show only the current workspace at this stage.
- In the UAV task stage, display:
  - NDVI summary
  - NDRE summary
  - Abnormal region summary
  - `data_mode=dry_run` / mock status where applicable

- In the anomaly discovery stage, display:
  - UAV index anomaly analysis result
  - `uav_risk_score`
  - `uav_abnormal_level`
  - Main anomaly reasons

- In the report closure stage, display:
  - `risk_model_detail`
  - `factor_scores`
  - `main_factors`
  - `model_stage=experimental`
  - `probability_claim=false`

### 2.2 Risk Fusion Display

Display:

- Risk level
- Rule-weighted score
- Participating feature sources
  - UAV index analysis
  - Phone follow-up recognition
  - Weather records
  - Growth stage
  - Historical disease records
  - Treatment feedback
- Experimental marker
- Safety note for `probability_claim=false`

Do not display:

- Disease probability
- Prediction probability
- Formal diagnosis probability
- Precision / Recall / mAP / AUC claims

### 2.3 Inspection Report Display

Add a report section named:

`Experimental Multisource Risk Analysis`

The section should display:

- UAV index anomaly summary
- Phone follow-up result
- Recognition result summary
- Rule-based factor scores
- Total risk score
- Risk level
- Main contributing factors
- Safety note

Required wording:

> This result is used only to support inspection priority judgment and does not represent formal disease probability, diagnosis, pesticide prescription, or dosage guidance.

### 2.4 Frontend Safety Wording

Do not use:

- Prediction probability
- Confirmed diagnosis
- Prescription
- Recommended pesticide dosage
- Guaranteed treatment plan

Recommended wording:

- Risk score
- Anomaly hint
- Auxiliary judgment
- Experimental analysis
- Inspection priority suggestion
- Rule-based score

## 3. Data Handling Requirements

- P10 must gracefully handle old reports without `risk_model_detail`.
- P10 must gracefully handle missing `factor_scores`.
- P10 must gracefully handle missing UAV analysis.
- P10 must display a neutral empty state rather than crashing.
- P10 should prefer P9 API response fields over legacy `risk_probability`.
- If `probability_claim=false`, the UI must not render any value as disease probability.

## 4. Suggested Frontend Components

- UAV index analysis panel
  - NDVI / NDRE metrics
  - Abnormal area ratio
  - UAV risk score
  - Abnormal level

- Risk factor contribution panel
  - Horizontal bars for factor scores
  - Labels for UAV, image, environment, growth stage, history, treatment
  - Negative treatment score should be shown as risk reduction, not as a treatment recommendation.

- Risk explanation panel
  - Main factors list
  - Safety note
  - Experimental marker

- Inspection report risk section
  - Compact summary for report detail page
  - Defensive rendering for missing fields

## 5. API Integration Targets

- `GET /api/uav/tasks/{uav_task_id}/index-analysis`
- `POST /api/uav/tasks/{uav_task_id}/analyze-indices`
- `POST /api/risk/fusion/evaluate`
- `GET /api/risk/fusion/{prediction_id}`
- `GET /api/risk/fusion/field/{field_id}`
- `GET /api/inspection-reports/{report_id}`

Recommended behavior:

- Prefer GET endpoints for display.
- Use POST evaluate only when the user explicitly triggers risk analysis or report generation requires it.
- Do not auto-trigger repeated writes on every page render.

## 6. P10 Acceptance Criteria

- Frontend build: PASS
- Backend tests: PASS
- P5 contract verification: PASS
- Smoke test: PASS
- Page does not display formal probability, prescription, or dosage wording.
- P9 API results are displayed correctly.
- Old data missing `risk_model_detail` does not crash the page.
- Experimental label is visible where P9 risk fusion is shown.
- `probability_claim=false` safety explanation is visible.

## 7. Out of Scope for P10

- No formal disease probability prediction.
- No pesticide prescription.
- No dosage suggestions.
- No model replacement.
- No `.env` change.
- No experimental ML training.
- No real UAV SDK integration.
- No real weather API integration unless separately approved as a later stage.

## 8. Suggested Development Tasks

1. Add frontend data adapters for P9 API responses.
2. Add defensive rendering helpers for missing `risk_model_detail`.
3. Add collaborative workbench UAV index analysis panel.
4. Add risk factor contribution panel using `factor_scores`.
5. Add inspection report section for experimental multisource risk analysis.
6. Add frontend safety wording constants.
7. Add frontend tests or static checks preventing prohibited terms such as prediction probability, prescription, and dosage.
8. Re-run backend tests, smoke test, P5 contract verification, and frontend build.

## 9. P10 Entry Decision

P10 is allowed to enter development after P9 freeze.

The recommended first implementation slice is report-detail display of `risk_model_detail`, because it is read-only, low-risk, and directly validates the P9 backend contract before expanding to the broader collaborative workbench.
