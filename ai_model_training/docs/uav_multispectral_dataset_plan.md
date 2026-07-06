# UAV Multispectral Disease Dataset Plan

This plan tracks the real UAV/multispectral disease data gap for `uav_rice_disease_yolo`.

## Current State

- Existing UAV smoke dataset: `datasets/rice_uav_ms`
- Current enabled class: `rice_panicle`
- Current category type: `crop_object`
- Disease/pest status: not a disease or pest dataset
- Training status in Stage 7B: no training started

## Priority Dataset

| Item | Value |
| --- | --- |
| Dataset | BLB UAV Dataset |
| Source | https://figshare.com/articles/dataset/BLB_UAV_Dataset/26955862 |
| Intended target | Bacterial leaf blight from UAV/multispectral data |
| Registry code | `bacterial_leaf_blight` |
| License | CC BY 4.0 as shown on Figshare; must be rechecked after manual download |
| Local status | Not present under `raw_datasets/blb_uav_dataset/original/` in Stage 7B |
| Access status | Page is public, but previous automated direct download returned HTTP 403; no bypass attempted |

## Manual Download Steps

1. Open the Figshare dataset page in a browser.
2. Use the official download option or officially linked storage location.
3. Place the archive or extracted contents under:

```text
raw_datasets/blb_uav_dataset/original/
```

4. Keep original filenames and directory names unchanged.
5. Run the dry-run converter:

```powershell
python scripts/convert_blb_uav_masks_to_yolo.py --input-root raw_datasets/blb_uav_dataset/original --output-root datasets/rice_uav_ms_blb_preview --class-code bacterial_leaf_blight --dry-run
```

## Conversion Rules

- Map low BLB and high BLB to the same detection class: `bacterial_leaf_blight`.
- Store severity in metadata, not in the YOLO class id.
- Generate bbox from mask connected components or label-map regions.
- Exclude background pixels/classes.
- Exclude healthy/normal from detection labels.
- Keep unknown/uncertain regions for review only.
- Do not merge this preview dataset into the active `datasets/rice_uav_ms/data.yaml` until labels pass audit.

## Next Deliverables After Manual Download

- `raw_datasets/blb_uav_dataset/blb_uav_structure_report.md`
- `datasets/rice_uav_ms_blb_preview/data.yaml`
- `datasets/rice_uav_ms_blb_preview/metadata/class_map.yaml`
- `datasets/rice_uav_ms_blb_preview/metadata/image_metadata.csv`
- YOLO labels generated from masks
- A dataset check report before any smoke train
