# P11-1 Open Dataset Landing Audit

Generated at: 2026-07-05T22:44:52Z

## Scope

P11-1 performed experimental external-data landing gates only. It did not modify backend main-chain logic, `.env`, existing model weights, risk_fusion logic, formal disease probability outputs, pesticide prescriptions, or dosage advice.

Experimental data root: `F:\学校\病虫害识别\ai_model_training\datasets_external\p11_open_datasets`

## Dataset Results

| Dataset | License Gate | Local Status | Items | Train Ready | Allowed Next Step | Gate Reason |
| --- | --- | --- | ---: | --- | --- | --- |
| Rice Leaf Bacterial and Fungal Disease Dataset | PASSED | RAW_SAMPLE_NOT_LANDED_FOR_EXACT_DATASET | 0 | NO_RAW_SAMPLE_YET | ALLOW_SMALL_SAMPLE_DOWNLOAD_THEN_PHONE_RGB_SMOKE | License is clear, but exact dataset raw samples were not locally landed in this P11-1 run. |
| RiceSeg-5932 | PASSED | SAMPLE_LANDED_FROM_EXISTING_LOCAL_RAW_DATA | 3 | SMOKE_READY_ONLY | ALLOW_SEGMENTATION_PIPELINE_SMOKE_ONLY | Masks and matching Sethy source images were found locally and sample pairs were copied to the experimental external directory. |
| Rice Disease bbox | PASSED | RAW_SAMPLE_NOT_LANDED; local zip placeholder not usable | 0 | NO_RAW_SAMPLE_YET | ALLOW_SMALL_SAMPLE_DOWNLOAD_THEN_BBOX_SMOKE | License appears clear, but raw bbox sample was not locally available; Kaggle download was not attempted in this no-large-download run. |
| Aligned RGB+MS Weedy Rice | PASSED | RAW_SAMPLE_NOT_LANDED | 0 | MS_PIPELINE_ONLY_AFTER_SAMPLE_DOWNLOAD | ALLOW_MS_PIPELINE_SMOKE_ONLY; NO_DISEASE_TRAINING | License is clear and source page is reachable, but no raw sample was downloaded; not a disease dataset. |
| BLB UAV Dataset | NEEDS_CONFIRMATION | LOCAL_EXISTING_DATA_FOUND_BUT_NOT_RELEASED_FOR_TRAINING | 0 | LICENSE_GATE_BLOCKED | LICENSE_GATE_AND_SOURCE_CARD_ONLY | BLB UAV data license is not confirmed; local existing files are inspected only and cannot be used for training in this gate. |

## Key Findings

- RiceSeg-5932 has local mask and Sethy source image pairs; three sample pairs were copied into the experimental external-data directory for segmentation pipeline smoke only.
- Rice Leaf Bacterial and Fungal Disease has clear CC BY 4.0 source metadata, but exact raw samples were not locally landed in this run; it remains sample-gated.
- Rice Disease bbox has a clear CC0 signal on Dataset Ninja, but the local Kaggle zip placeholder is not usable; it remains sample-gated.
- Aligned RGB+MS Weedy Rice is allowed only for MS pipeline smoke / NDVI / NDRE calculation verification / migration pretraining. It is not disease training data.
- BLB UAV Dataset has local existing files, but the dataset license gate is still blocked. Local files were counted only; they are not released for training.
- risk_fusion_tabular_shadow_model = BLOCKED_FOR_LABELS because public image datasets do not provide field-level final decision labels.

## Safety Boundary

No dataset in this P11-1 gate is allowed to produce formal disease probability, diagnosis, pesticide prescription, dosage advice, or risk_fusion ML training.

## Verification

Executed in `F:/学校/病虫害识别/agri_uav_disease_system/backend` with `.venv/Scripts/python.exe`.

| Command | Result |
| --- | --- |
| `python -m compileall app app/scripts` | PASS |
| `pytest -q` | PASS: 71 passed, 16 skipped, 1 warning |
| `python -m app.scripts.system_smoke_test` | PASS |
| `python ../../mark-video-demo/scripts/verify_p5_frontend_backend_contract.py` | PASS |
