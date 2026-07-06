# P11-1C Download And Gate Audit

Generated at: 2026-07-05T23:23:06Z

## Summary

- Automatic network download of large raw datasets was not performed.
- Sethy + RiceSeg are locally available and pairable; pairing reports were generated.
- Mendeley classification and Weedy Rice pages are reachable but direct archive URLs were not available to this non-interactive script.
- Kaggle bbox direct download was not public in this environment; manual Kaggle workflow is required.
- BLB UAV remains LICENSE_GATE_BLOCKED.
- Optional Maize MS Zenodo tiny metadata/readme download status: SUCCESS_SMALL_METADATA_ONLY; no full dataset was downloaded.
- risk_fusion_tabular_shadow_model = BLOCKED_FOR_LABELS.

## Download Results

| Dataset | Auto Download Status | Local Status | Allowed Next Step |
| --- | --- | --- | --- |
| Sethy + RiceSeg-5932 | NO_NETWORK_DOWNLOAD_LOCAL_FOUND | masks=5932; images=5932; paired=5932 | P11-2 segmentation smoke only |
| Rice Leaf Bacterial and Fungal Disease Dataset | FAILED_NO_DIRECT_PUBLIC_FILE_URL | not_landed | manual download then P11-2 phone RGB smoke gate |
| Rice Disease bbox | FAILED_KAGGLE_DIRECT_DOWNLOAD_NOT_PUBLIC | not_landed | manual download then P11-2 YOLO bbox smoke |
| Aligned RGB+MS Weedy Rice | FAILED_NO_DIRECT_PUBLIC_FILE_URL | not_landed | manual download then P11-2 MS pipeline smoke / NDVI-NDRE calculator smoke |
| BLB UAV Dataset | BLOCKED_LICENSE_UNCLEAR | local_data_found_but_training_blocked | license confirmation only |
| UAV-Based Multispectral Maize Dataset for Water Stress and Common Rust | SUCCESS_SMALL_METADATA_ONLY | metadata_files=2; metadata_size=12506 | optional MS pipeline metadata review / transfer-only smoke planning |

## Safety

No backend main-chain logic, `.env`, model weights, risk_fusion ML training, formal disease probability, prescription, or dosage advice was modified or produced.

## Verification

| Command | Result | Notes |
| --- | --- | --- |
| `python -m compileall app app/scripts` | PASS | Python files compiled successfully. |
| `pytest -q` | PASS | 75 passed, 16 skipped, 1 warning. |
| `python -m app.scripts.system_smoke_test` | PASS | FastAPI, SQLite, static files, dashboard/mobile/alerts, and WebSocket smoke checks passed. |
| `python verify_p5_frontend_backend_contract.py` | PASS | Executed via `../../mark-video-demo/scripts/verify_p5_frontend_backend_contract.py`; P5 contract checks passed. |
