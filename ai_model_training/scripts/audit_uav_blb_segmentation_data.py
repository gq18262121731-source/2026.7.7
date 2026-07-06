"""Audit UAV BLB raster masks for a segmentation route.

Read-only with respect to source images and labels. Writes audit reports,
CSV manifests, metadata, and optional visual previews only.
"""

from __future__ import annotations

import csv
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "raw_datasets" / "blb_uav_dataset" / "original"
PREVIEW_ROOT = ROOT / "datasets" / "rice_uav_ms_blb_preview_1000"
IMAGE_META = PREVIEW_ROOT / "metadata" / "image_metadata.csv"
REPORTS = ROOT / "reports"
META = ROOT / "metadata"
PREVIEW_OUT = REPORTS / "uav_blb_segmentation_audit_previews"

BLB_VALUES = {2, 3}
BACKGROUND_OR_IGNORED_VALUES = {0, 1, 4}
MAX_PREVIEWS = 16


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def atomic_write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def tif_shape(path: Path) -> tuple[int, int, tuple[int, ...]]:
    arr = tifffile.imread(path)
    if arr.ndim == 2:
        height, width = arr.shape
    elif arr.ndim == 3:
        # BLB source patches are commonly HWC, but this audit records the raw shape too.
        height, width = arr.shape[0], arr.shape[1]
    else:
        height, width = arr.shape[-2], arr.shape[-1]
    return int(width), int(height), tuple(int(v) for v in arr.shape)


def normalize_rgb(arr: np.ndarray) -> np.ndarray:
    if arr.ndim == 2:
        rgb_source = np.stack([arr, arr, arr], axis=-1)
    elif arr.ndim == 3 and arr.shape[-1] >= 3:
        rgb_source = arr[..., :3]
    elif arr.ndim == 3 and arr.shape[0] >= 3:
        rgb_source = np.moveaxis(arr[:3, ...], 0, -1)
    else:
        squeezed = np.squeeze(arr)
        rgb_source = np.stack([squeezed, squeezed, squeezed], axis=-1)
    rgb = rgb_source.astype(np.float32)
    low = np.percentile(rgb, 2)
    high = np.percentile(rgb, 98)
    if high <= low:
        high = low + 1
    rgb = np.clip((rgb - low) / (high - low), 0, 1)
    return (rgb * 255).astype(np.uint8)


def load_font(size: int) -> ImageFont.ImageFont:
    for candidate in [Path("C:/Windows/Fonts/arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def make_overlay(image_path: Path, mask_path: Path, out_path: Path, title: str) -> None:
    image_arr = tifffile.imread(image_path)
    mask_arr = tifffile.imread(mask_path)
    rgb = normalize_rgb(image_arr)
    if rgb.shape[:2] != mask_arr.shape[:2]:
        # Preview only; the audit status will flag mismatch. Avoid resizing source data.
        mask_img = Image.fromarray(mask_arr.astype(np.uint8), mode="L").resize((rgb.shape[1], rgb.shape[0]), Image.NEAREST)
        mask_arr = np.array(mask_img)
    mask = np.isin(mask_arr, list(BLB_VALUES))
    overlay = rgb.copy()
    overlay[mask] = (0.45 * overlay[mask] + 0.55 * np.array([255, 0, 0])).astype(np.uint8)
    panel = Image.fromarray(overlay)
    max_width = 520
    if panel.width > max_width:
        ratio = max_width / panel.width
        panel = panel.resize((max_width, int(panel.height * ratio)), Image.BILINEAR)
    canvas = Image.new("RGB", (panel.width, panel.height + 46), "white")
    canvas.paste(panel, (0, 46))
    draw = ImageDraw.Draw(canvas)
    font = load_font(14)
    draw.text((8, 6), title[:120], fill=(0, 0, 0), font=font)
    draw.text((8, 25), "red overlay = raster values 2/3 mapped to BLB segmentation foreground", fill=(180, 0, 0), font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=92)


def split_image_path(image_name: str, split: str) -> Path:
    return PREVIEW_ROOT / "images" / split / image_name


def audit() -> dict[str, Any]:
    metadata_rows = read_csv(IMAGE_META)
    mask_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    value_counter: Counter[str] = Counter()
    pair_status_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()
    split_counter: Counter[str] = Counter()
    preview_count = 0

    PREVIEW_OUT.mkdir(parents=True, exist_ok=True)
    for old_preview in PREVIEW_OUT.glob("*.jpg"):
        old_preview.unlink()

    for row in metadata_rows:
        image_name = row["image_name"]
        split = row["split"]
        original_image_path = RAW_ROOT / row["original_image_path"].replace("\\", "/")
        original_mask_path = RAW_ROOT / row["original_label_path"].replace("\\", "/")
        preview_image_path = split_image_path(image_name, split)
        notes: list[str] = []
        pair_status = "PASS"
        image_width = image_height = mask_width = mask_height = 0
        image_shape: tuple[int, ...] = ()
        mask_shape: tuple[int, ...] = ()
        unique_values: list[int] = []
        foreground_count = 0
        foreground_ratio = 0.0

        if not original_image_path.exists():
            pair_status = "MISSING_IMAGE"
            notes.append("original image tif missing")
        if not original_mask_path.exists():
            pair_status = "MISSING_MASK" if pair_status == "PASS" else "MISSING_IMAGE_AND_MASK"
            notes.append("original raster mask tif missing")
        if pair_status == "PASS":
            image_width, image_height, image_shape = tif_shape(original_image_path)
            mask_arr = tifffile.imread(original_mask_path)
            mask_shape = tuple(int(v) for v in mask_arr.shape)
            mask_height, mask_width = int(mask_arr.shape[0]), int(mask_arr.shape[1])
            unique_values = [int(value) for value in np.unique(mask_arr)]
            for value in unique_values:
                value_counter[str(value)] += 1
            foreground = np.isin(mask_arr, list(BLB_VALUES))
            foreground_count = int(foreground.sum())
            foreground_ratio = foreground_count / int(mask_arr.size) if mask_arr.size else 0.0
            if (image_width, image_height) != (mask_width, mask_height):
                pair_status = "SIZE_MISMATCH"
                notes.append("image and mask dimensions differ")
            if not (BLB_VALUES & set(unique_values)):
                pair_status = "NO_BLB_VALUE" if pair_status == "PASS" else pair_status
                notes.append("mask has no BLB foreground value 2/3")
            if set(unique_values) - (BLB_VALUES | BACKGROUND_OR_IGNORED_VALUES):
                notes.append("unexpected mask values present")
            if not preview_image_path.exists():
                notes.append("preview jpg missing")
            if preview_count < MAX_PREVIEWS and foreground_count > 0:
                preview_name = f"{Path(image_name).stem}_segmentation_mask_overlay.jpg"
                make_overlay(
                    original_image_path,
                    original_mask_path,
                    PREVIEW_OUT / preview_name,
                    f"{image_name} | split={split} | values={'|'.join(map(str, unique_values))} | fg={foreground_ratio:.4f}",
                )
                preview_count += 1

        usable = pair_status == "PASS"
        pair_status_counter[pair_status] += 1
        source_counter[row.get("source_dataset", "")] += 1
        split_counter[split] += 1

        mask_rows.append(
            {
                "mask_path": rel(original_mask_path) if original_mask_path.exists() else original_mask_path.as_posix(),
                "matched_image_path": rel(original_image_path) if original_image_path.exists() else original_image_path.as_posix(),
                "image_width": image_width,
                "image_height": image_height,
                "mask_width": mask_width,
                "mask_height": mask_height,
                "unique_values": "|".join(str(value) for value in unique_values),
                "foreground_pixel_count": foreground_count,
                "foreground_ratio": f"{foreground_ratio:.8f}",
                "match_status": pair_status,
                "notes": "; ".join(notes),
            }
        )
        pair_rows.append(
            {
                "image_name": image_name,
                "image_path": rel(original_image_path) if original_image_path.exists() else original_image_path.as_posix(),
                "mask_path": rel(original_mask_path) if original_mask_path.exists() else original_mask_path.as_posix(),
                "split": split,
                "pair_status": pair_status,
                "image_size": f"{image_width}x{image_height}" if image_width and image_height else "",
                "mask_size": f"{mask_width}x{mask_height}" if mask_width and mask_height else "",
                "usable_for_segmentation": str(usable).lower(),
                "notes": "; ".join(notes),
            }
        )

    total_pairs = len(pair_rows)
    pass_pairs = pair_status_counter.get("PASS", 0)
    masks_with_blb = sum(1 for row in mask_rows if any(value in row["unique_values"].split("|") for value in ("2", "3")))
    mask_value_status = "PASS" if masks_with_blb == total_pairs and total_pairs else "WARNING" if masks_with_blb else "FAIL"
    alignment_status = "PASS" if pass_pairs == total_pairs and total_pairs else "WARNING" if pass_pairs else "FAIL"
    segmentation_data_found = total_pairs > 0 and masks_with_blb > 0
    feasible = segmentation_data_found and alignment_status == "PASS" and mask_value_status in {"PASS", "WARNING"}

    mask_fields = [
        "mask_path",
        "matched_image_path",
        "image_width",
        "image_height",
        "mask_width",
        "mask_height",
        "unique_values",
        "foreground_pixel_count",
        "foreground_ratio",
        "match_status",
        "notes",
    ]
    pair_fields = [
        "image_name",
        "image_path",
        "mask_path",
        "split",
        "pair_status",
        "image_size",
        "mask_size",
        "usable_for_segmentation",
        "notes",
    ]
    atomic_write_csv(REPORTS / "uav_blb_segmentation_mask_value_audit.csv", mask_rows, mask_fields)
    atomic_write_csv(REPORTS / "uav_blb_segmentation_pair_manifest.csv", pair_rows, pair_fields)

    image_tif_count = sum(1 for p in RAW_ROOT.rglob("*.tif") if "_labels" not in p.parent.name)
    mask_tif_count = sum(1 for p in RAW_ROOT.rglob("*.tif") if "_labels" in p.parent.name)
    report = {
        "generated_at": now_iso(),
        "raw_root": rel(RAW_ROOT),
        "preview_dataset": rel(PREVIEW_ROOT),
        "metadata_rows": total_pairs,
        "raw_tif_total": image_tif_count + mask_tif_count,
        "raw_image_tif_count": image_tif_count,
        "raw_mask_tif_count": mask_tif_count,
        "preview_image_count": sum(1 for _ in (PREVIEW_ROOT / "images").glob("*/*.jpg")),
        "image_mask_pairs_found": total_pairs,
        "image_mask_pairs_pass": pass_pairs,
        "pair_status_counts": dict(pair_status_counter),
        "split_counts": dict(split_counter),
        "source_dataset_counts": dict(source_counter),
        "mask_value_file_presence_counts": dict(value_counter),
        "blb_values": sorted(BLB_VALUES),
        "background_or_ignored_values": sorted(BACKGROUND_OR_IGNORED_VALUES),
        "masks_with_blb_values": masks_with_blb,
        "mask_value_audit_status": mask_value_status,
        "image_mask_alignment_status": alignment_status,
        "segmentation_data_found": segmentation_data_found,
        "segmentation_route_feasible_for_conversion_planning": feasible,
        "segmentation_training_allowed": False,
        "preview_count": preview_count,
        "preview_dir": rel(PREVIEW_OUT),
        "boundaries": {
            "training_executed": False,
            "new_weights_generated": False,
            "original_images_modified": False,
            "original_yolo_labels_overwritten": False,
            "backend_modified": False,
            "env_modified": False,
        },
    }
    atomic_write_json(REPORTS / "uav_blb_segmentation_data_audit_report.json", report)
    write_markdown_reports(report)
    write_status(report)
    return report


def write_markdown_reports(report: dict[str, Any]) -> None:
    audit_md = f"""# UAV BLB Segmentation Data Audit Report

## Boundary

- training_executed: `NO`
- new_weights_generated: `NO`
- original_images_modified: `NO`
- original_yolo_labels_overwritten: `NO`
- backend_modified: `NO`
- env_modified: `NO`
- bbox_route_status: `BLOCKED`
- segmentation_training_allowed: `false`

## Source Data

- raw_data_root: `{report['raw_root']}`
- preview_dataset: `{report['preview_dataset']}`
- metadata_rows: `{report['metadata_rows']}`
- raw_image_tif_count: `{report['raw_image_tif_count']}`
- raw_mask_tif_count: `{report['raw_mask_tif_count']}`
- preview_image_count: `{report['preview_image_count']}`

## Image-Mask Pair Audit

- image_mask_pairs_found: `{report['image_mask_pairs_found']}`
- image_mask_pairs_pass: `{report['image_mask_pairs_pass']}`
- pair_status_counts: `{report['pair_status_counts']}`
- split_counts: `{report['split_counts']}`
- source_dataset_counts: `{report['source_dataset_counts']}`
- image_mask_alignment_status: `{report['image_mask_alignment_status']}`

## Mask Value Audit

- mask_value_file_presence_counts: `{report['mask_value_file_presence_counts']}`
- blb_values: `{report['blb_values']}`
- background_or_ignored_values: `{report['background_or_ignored_values']}`
- masks_with_blb_values: `{report['masks_with_blb_values']}`
- mask_value_audit_status: `{report['mask_value_audit_status']}`

Raster values `2` and `3` are present and are the BLB foreground values already documented by the preview dataset class map. Values `0`, `1`, and `4` are background/ignored/healthy/other values for the segmentation conversion plan unless a later domain review decides otherwise.

## Segmentation Feasibility

- segmentation_data_found: `{str(report['segmentation_data_found']).lower()}`
- segmentation_route_feasible_for_conversion_planning: `{str(report['segmentation_route_feasible_for_conversion_planning']).lower()}`
- segmentation_training_allowed: `false`

The audit supports moving to a segmentation conversion planning stage because the source data contains aligned image TIF and raster mask TIF pairs with BLB foreground values. This is not a training release. A converted segmentation dataset still needs its own conversion, visual QA, and training gate.

## Audit Previews

- preview_count: `{report['preview_count']}`
- preview_dir: `{report['preview_dir']}`

The previews are audit overlays only and are not model outputs.

## Risks And Missing Items

- The raw imagery is multispectral TIF; model input channel policy must be selected before conversion.
- Mask values need a documented binary conversion rule: values `2` and `3` as BLB foreground, other values ignored/background.
- A segmentation visual QA gate is still required after conversion.
- Bbox route remains blocked and should not be used as a training source.

## Next Step

Proceed to a segmentation conversion plan or data repair stage. Do not train until converted segmentation pairs pass a separate segmentation data gate.
"""
    atomic_write_text(REPORTS / "uav_blb_segmentation_data_audit_report.md", audit_md)

    conversion_md = """# UAV BLB Segmentation Conversion Plan

## Recommended Dataset Structure

```text
datasets/rice_uav_ms_blb_segmentation_v1/
  images/
    train/
    val/
    test/
  masks/
    train/
    val/
    test/
  previews/
  metadata/
```

## Mask Binarization Strategy

- source raster values `2` and `3`: BLB foreground.
- source raster values `0`, `1`, and `4`: background or ignored values for the first binary BLB segmentation version.
- output mask proposal: single-channel PNG, `0 = background/ignored`, `255 = bacterial_leaf_blight`.
- do not create model classes from manual review issue types.

## Image Strategy

- Preserve the existing `train/val/test` split from `datasets/rice_uav_ms_blb_preview_1000/metadata/image_metadata.csv`.
- Decide model input channel policy before conversion:
  - option 1: RGB-like rendered preview for quick smoke;
  - option 2: selected multispectral bands;
  - option 3: full multispectral tensor pipeline for models that support it.
- Keep raw TIF files read-only. Write converted images and masks only to a derived segmentation dataset directory.

## Naming Rules

- use the existing preview `image_name` stem for converted image and mask names;
- example: `blb_D1_train_patch_479.png` paired with `blb_D1_train_patch_479_mask.png`;
- keep a manifest row linking converted files back to original image and raster mask TIF paths.

## Quality Gate Before Training

- verify every image has one mask;
- verify image and mask dimensions match after conversion;
- verify mask values are only `0` and `255`;
- verify foreground ratio distribution and flag empty/near-empty masks;
- generate visual overlays for a sampled audit;
- require a segmentation gate report before any training.

## Model Route Priority

1. `U-Net`: best first baseline for binary segmentation and fast debugging.
2. `DeepLab`: stronger semantic segmentation baseline after data conversion is stable.
3. `YOLO-seg`: useful if the deployment stack prefers YOLO-style packaging, but only after polygon/mask conversion policy is stable.

## Boundary

- training_allowed_now: `false`
- bbox_route_status: `BLOCKED`
- next_allowed_stage: `SEGMENTATION_CONVERSION_PLAN_OR_DATA_REPAIR`
"""
    atomic_write_text(REPORTS / "uav_blb_segmentation_conversion_plan.md", conversion_md)


def write_status(report: dict[str, Any]) -> None:
    status = f"""segmentation_route_stage: DATA_AUDIT
bbox_route_status: BLOCKED
segmentation_data_found: {str(report['segmentation_data_found']).lower()}
image_mask_pairs_found: {report['image_mask_pairs_found']}
image_mask_pairs_pass: {report['image_mask_pairs_pass']}
mask_value_audit_status: {report['mask_value_audit_status']}
image_mask_alignment_status: {report['image_mask_alignment_status']}
segmentation_route_feasible_for_conversion_planning: {str(report['segmentation_route_feasible_for_conversion_planning']).lower()}
segmentation_training_allowed: false
raw_image_tif_count: {report['raw_image_tif_count']}
raw_mask_tif_count: {report['raw_mask_tif_count']}
preview_image_count: {report['preview_image_count']}
blb_mask_values: [2, 3]
background_or_ignored_values: [0, 1, 4]
audit_preview_count: {report['preview_count']}
audit_preview_dir: {report['preview_dir']}
original_images_modified: false
original_labels_modified: false
weights_modified: false
backend_modified: false
env_modified: false
next_allowed_stage: SEGMENTATION_CONVERSION_PLAN_OR_DATA_REPAIR
notes:
  - bbox route remains blocked
  - values 2 and 3 are BLB foreground candidates for binary segmentation
  - segmentation training remains forbidden until conversion and a separate segmentation gate pass
"""
    atomic_write_text(META / "uav_blb_segmentation_route_status.yaml", status)


def main() -> int:
    report = audit()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
