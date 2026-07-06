# P11-1 Training Gate Matrix

Generated at: 2026-07-05T22:44:52Z

| dataset_name | task_type | modality | label_type | license_status | access_status | local_status | class_mapping_status | split_status | leakage_risk | train_ready | allowed_next_step |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Rice Leaf Bacterial and Fungal Disease Dataset | phone_rgb_classification_baseline | RGB / leaf close-up | classification | PASSED | SOURCE_PAGE_200_DOWNLOAD_NOT_ATTEMPTED | RAW_SAMPLE_NOT_LANDED_FOR_EXACT_DATASET | PARTIAL_NEEDS_REVIEW_FOR_LEAF_SCALD_HISPA_NARROW_BROWN | NEEDS_SPLIT_AFTER_DOWNLOAD; original/augmented must be grouped | HIGH_ORIGINAL_AUGMENTED_LEAKAGE_RISK | NO_RAW_SAMPLE_YET | ALLOW_SMALL_SAMPLE_DOWNLOAD_THEN_PHONE_RGB_SMOKE |
| RiceSeg-5932 | leaf_lesion_segmentation_smoke | RGB image + mask | segmentation mask | PASSED | SOURCE_PAGE_200_LOCAL_SOURCE_IMAGES_FOUND | SAMPLE_LANDED_FROM_EXISTING_LOCAL_RAW_DATA | PASSED_FOR_BLB_BROWN_SPOT_RICE_BLAST_TUNGRO | SAMPLE_SPLIT_PLAN_CREATED_HELD_OUT_REQUIRED_FOR_REAL_TRAINING | MEDIUM_PAIRING_AND_SOURCE_IMAGE_VERSION_RISK | SMOKE_READY_ONLY | ALLOW_SEGMENTATION_PIPELINE_SMOKE_ONLY |
| Rice Disease bbox | bbox_detection_smoke | RGB / leaf close-up | bounding box | PASSED | SOURCE_PAGE_200_KAGGLE_DOWNLOAD_NOT_ATTEMPTED | RAW_SAMPLE_NOT_LANDED; local zip placeholder not usable | PASSED_FOR_3_CLASSES | NEEDS_SPLIT_AFTER_SAMPLE_DOWNLOAD | MEDIUM_SMALL_DATASET_EVALUATION_INSTABILITY | NO_RAW_SAMPLE_YET | ALLOW_SMALL_SAMPLE_DOWNLOAD_THEN_BBOX_SMOKE |
| Aligned RGB+MS Weedy Rice | ms_pipeline_smoke_ndvi_ndre | UAV RGB + multispectral Green/Red/RedEdge/NIR | binary segmentation mask for weedy rice; no disease label | PASSED | SOURCE_PAGE_200_DOWNLOAD_NOT_ATTEMPTED | RAW_SAMPLE_NOT_LANDED | NOT_DISEASE_DATASET | SOURCE_HAS_SAMPLE_SPLIT; not locally verified | MEDIUM_RGB_MS_MASK_PAIRING_RISK | MS_PIPELINE_ONLY_AFTER_SAMPLE_DOWNLOAD | ALLOW_MS_PIPELINE_SMOKE_ONLY; NO_DISEASE_TRAINING |
| BLB UAV Dataset | uav_blb_license_gate_only | UAV multispectral / patch data | segmentation or class labels, local structure only | NEEDS_CONFIRMATION | PLOS_PAGE_200_DATA_DOWNLOAD_GATE_NOT_CONFIRMED | LOCAL_EXISTING_DATA_FOUND_BUT_NOT_RELEASED_FOR_TRAINING | PASSED_FOR_BLB_ONLY | LOCAL_SPLITS_EXIST_BUT_NOT_TRUSTED_UNTIL_LICENSE_PASS | HIGH_PATCH_FROM_SAME_ORTHOMOSAIC_LEAKAGE_RISK | LICENSE_GATE_BLOCKED | LICENSE_GATE_AND_SOURCE_CARD_ONLY |

## Immediate Decisions

- Immediate smoke-ready: RiceSeg-5932 segmentation pipeline smoke only.
- Smoke allowed after small sample download: Rice Leaf Bacterial and Fungal Disease, Rice Disease bbox.
- MS pipeline only after sample download: Aligned RGB+MS Weedy Rice.
- Blocked: BLB UAV Dataset for any training until dataset license is explicitly confirmed.
