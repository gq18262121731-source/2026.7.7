"""Convert audited UAV BLB raster masks into a derived segmentation dataset.

This creates a derived dataset only. It does not modify source images, source
YOLO labels, backend files, environment files, or model weights.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
META = ROOT / "metadata"
SOURCE_PAIR_MANIFEST = REPORTS / "uav_blb_segmentation_pair_manifest.csv"
OUT = ROOT / "datasets" / "rice_uav_ms_blb_segmentation_408_v1"
BLB_VALUES = {2, 3}
BACKGROUND_OR_IGNORE_VALUES = {0, 1, 4}
MASK_FOREGROUND_VALUE = 255
FOREGROUND_LOW_WARN = 0.001
FOREGROUND_HIGH_WARN = 0.90


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


def source_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


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


def ensure_dirs() -> None:
    for split in ("train", "val", "test"):
        (OUT / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUT / "masks" / split).mkdir(parents=True, exist_ok=True)
    (OUT / "overlays_preview").mkdir(parents=True, exist_ok=True)
    (OUT / "meta").mkdir(parents=True, exist_ok=True)
    for old_preview in (OUT / "overlays_preview").glob("*.jpg"):
        old_preview.unlink()


def make_overlay(image_path: Path, binary_mask: np.ndarray, out_path: Path, title: str) -> None:
    image_arr = tifffile.imread(image_path)
    rgb = normalize_rgb(image_arr)
    if rgb.shape[:2] != binary_mask.shape[:2]:
        mask_img = Image.fromarray(binary_mask, mode="L").resize((rgb.shape[1], rgb.shape[0]), Image.NEAREST)
        binary_mask = np.array(mask_img)
    foreground = binary_mask > 0
    overlay = rgb.copy()
    overlay[foreground] = (0.45 * overlay[foreground] + 0.55 * np.array([255, 0, 0])).astype(np.uint8)
    raw_panel = Image.fromarray(rgb)
    overlay_panel = Image.fromarray(overlay)
    if raw_panel.width > 420:
        ratio = 420 / raw_panel.width
        size = (420, int(raw_panel.height * ratio))
        raw_panel = raw_panel.resize(size, Image.BILINEAR)
        overlay_panel = overlay_panel.resize(size, Image.BILINEAR)
    gap = 8
    header_h = 50
    canvas = Image.new("RGB", (raw_panel.width * 2 + gap, raw_panel.height + header_h), "white")
    canvas.paste(raw_panel, (0, header_h))
    canvas.paste(overlay_panel, (raw_panel.width + gap, header_h))
    draw = ImageDraw.Draw(canvas)
    font = load_font(13)
    draw.text((8, 6), title[:135], fill=(0, 0, 0), font=font)
    draw.text((8, 28), "left=rendered image, right=BLB mask overlay; mask 2/3 -> foreground", fill=(170, 0, 0), font=font)
    canvas.save(out_path, quality=92)


def write_dataset_docs(report: dict[str, Any]) -> None:
    data_yaml = """path: datasets/rice_uav_ms_blb_segmentation_408_v1
task: binary_segmentation
train: images/train
val: images/val
test: images/test
masks:
  train: masks/train
  val: masks/val
  test: masks/test
image_format: copied source multispectral TIF
mask_format: single-channel PNG, values 0 background_or_ignored, 255 bacterial_leaf_blight
names:
  0: background
  1: bacterial_leaf_blight
notes:
  - source raster values 2 and 3 are converted to foreground 255
  - source raster values 0, 1, and 4 are converted to background 0 for this binary v1
  - segmentation_training_allowed is false until visual QA gate passes
"""
    atomic_write_text(OUT / "data.yaml", data_yaml)

    readme = f"""# UAV BLB Segmentation 408 v1

This is a derived segmentation dataset for UAV multispectral bacterial leaf blight region segmentation.

## Source

- source_pair_manifest: `reports/uav_blb_segmentation_pair_manifest.csv`
- source_raw_dataset: `raw_datasets/blb_uav_dataset/original`
- derived_dataset: `datasets/rice_uav_ms_blb_segmentation_408_v1`

## Purpose

The YOLO bbox route is currently blocked because mask/raster-to-bbox conversion produced semantic duplicate boxes, adjacent redundant boxes, fragmented boxes, and multispectral noise boxes. This dataset keeps the task as region segmentation instead of forcing irregular disease areas into rectangular boxes.

## Files

- `images/{{split}}/*.tif`: copied source multispectral TIF patches.
- `masks/{{split}}/*.png`: binary BLB masks.
- `overlays_preview/*.jpg`: visual QA preview overlays.
- `meta/conversion_manifest.csv`: source-to-derived pair manifest.

## Mask Value Policy

- source raster value `2`: BLB foreground.
- source raster value `3`: BLB foreground.
- source raster values `0`, `1`, `4`: converted to background/ignored value `0` for binary v1.
- output mask values: `0 = background_or_ignored`, `255 = bacterial_leaf_blight`.

## Split

The conversion preserves the audited split:

- train: `{report['split_counts'].get('train', 0)}`
- val: `{report['split_counts'].get('val', 0)}`
- test: `{report['split_counts'].get('test', 0)}`

## Current Status

- conversion_status: `{report['conversion_status']}`
- visual_qa_required: `true`
- segmentation_training_allowed: `false`

Do not train from this dataset until the segmentation visual QA gate passes.
"""
    atomic_write_text(OUT / "README.md", readme)


def convert() -> dict[str, Any]:
    if not SOURCE_PAIR_MANIFEST.exists():
        raise FileNotFoundError(f"missing source pair manifest: {SOURCE_PAIR_MANIFEST}")
    ensure_dirs()
    rows = read_csv(SOURCE_PAIR_MANIFEST)
    stats_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    split_counts: Counter[str] = Counter()
    unique_value_patterns: Counter[str] = Counter()
    mask_output_values: Counter[str] = Counter()
    anomaly_counts: Counter[str] = Counter()

    for row in rows:
        image_name = row["image_name"]
        split = row["split"]
        image_stem = Path(image_name).stem
        source_image = source_path(row["image_path"])
        source_mask = source_path(row["mask_path"])
        derived_image = OUT / "images" / split / f"{image_stem}.tif"
        derived_mask = OUT / "masks" / split / f"{image_stem}.png"
        overlay_path = OUT / "overlays_preview" / f"{image_stem}_seg_overlay.jpg"
        notes: list[str] = []
        pair_status = "PASS"

        if not source_image.exists():
            pair_status = "MISSING_SOURCE_IMAGE"
            notes.append("source image missing")
        if not source_mask.exists():
            pair_status = "MISSING_SOURCE_MASK" if pair_status == "PASS" else "MISSING_SOURCE_IMAGE_AND_MASK"
            notes.append("source mask missing")
        if pair_status != "PASS":
            anomaly_counts[pair_status] += 1
            continue

        mask_arr = tifffile.imread(source_mask)
        unique_values = [int(value) for value in np.unique(mask_arr)]
        unique_value_patterns["|".join(str(value) for value in unique_values)] += 1
        binary = np.where(np.isin(mask_arr, list(BLB_VALUES)), MASK_FOREGROUND_VALUE, 0).astype(np.uint8)
        source_shape = tifffile.imread(source_image).shape
        image_height, image_width = int(source_shape[0]), int(source_shape[1])
        mask_height, mask_width = int(mask_arr.shape[0]), int(mask_arr.shape[1])
        size_match = (image_width, image_height) == (mask_width, mask_height)
        foreground_count = int((binary > 0).sum())
        foreground_ratio = foreground_count / int(binary.size) if binary.size else 0.0
        empty_mask = foreground_count == 0
        full_mask = foreground_count == int(binary.size)
        output_unique_values = [int(value) for value in np.unique(binary)]
        mask_output_values["|".join(str(value) for value in output_unique_values)] += 1

        if not size_match:
            pair_status = "SIZE_MISMATCH"
            notes.append("derived image and mask size mismatch")
            anomaly_counts["size_mismatch"] += 1
        if empty_mask:
            notes.append("empty foreground mask")
            anomaly_counts["empty_mask"] += 1
        if full_mask:
            notes.append("full foreground mask")
            anomaly_counts["full_mask"] += 1
        if foreground_ratio < FOREGROUND_LOW_WARN:
            notes.append("foreground ratio very low")
            anomaly_counts["foreground_ratio_low"] += 1
        if foreground_ratio > FOREGROUND_HIGH_WARN:
            notes.append("foreground ratio very high")
            anomaly_counts["foreground_ratio_high"] += 1
        if set(output_unique_values) - {0, MASK_FOREGROUND_VALUE}:
            notes.append("unexpected output mask values")
            anomaly_counts["unexpected_output_mask_values"] += 1

        shutil.copy2(source_image, derived_image)
        Image.fromarray(binary, mode="L").save(derived_mask)
        make_overlay(
            source_image,
            binary,
            overlay_path,
            f"{image_name} | split={split} | fg={foreground_ratio:.4f} | source_values={'|'.join(map(str, unique_values))}",
        )

        split_counts[split] += 1
        stats_rows.append(
            {
                "image_name": image_name,
                "split": split,
                "image_path": rel(derived_image),
                "mask_path": rel(derived_mask),
                "image_width": image_width,
                "image_height": image_height,
                "mask_width": mask_width,
                "mask_height": mask_height,
                "mask_unique_values": "|".join(str(value) for value in output_unique_values),
                "source_mask_unique_values": "|".join(str(value) for value in unique_values),
                "foreground_pixel_count": foreground_count,
                "foreground_ratio": f"{foreground_ratio:.8f}",
                "empty_mask": str(empty_mask).lower(),
                "full_mask": str(full_mask).lower(),
                "size_match": str(size_match).lower(),
                "notes": "; ".join(notes),
            }
        )
        manifest_rows.append(
            {
                "image_name": image_name,
                "split": split,
                "source_image_path": rel(source_image),
                "source_mask_path": rel(source_mask),
                "derived_image_path": rel(derived_image),
                "derived_mask_path": rel(derived_mask),
                "pair_status": pair_status,
                "usable_for_visual_qa": str(pair_status == "PASS" and not empty_mask and not full_mask and size_match).lower(),
                "notes": "; ".join(notes),
            }
        )

    foreground_ratios = [float(row["foreground_ratio"]) for row in stats_rows]
    images_count = sum(1 for _ in (OUT / "images").glob("*/*.tif"))
    masks_count = sum(1 for _ in (OUT / "masks").glob("*/*.png"))
    overlays_count = sum(1 for _ in (OUT / "overlays_preview").glob("*.jpg"))
    unexpected_mask_rows = sum(1 for row in stats_rows if set(row["mask_unique_values"].split("|")) - {"0", str(MASK_FOREGROUND_VALUE)})
    empty_count = sum(1 for row in stats_rows if row["empty_mask"] == "true")
    full_count = sum(1 for row in stats_rows if row["full_mask"] == "true")
    size_mismatch_count = sum(1 for row in stats_rows if row["size_match"] != "true")
    missing_count = len(rows) - len(stats_rows)
    anomaly_total = empty_count + full_count + size_mismatch_count + unexpected_mask_rows + missing_count
    conversion_status = "PASS"
    if missing_count or size_mismatch_count or empty_count or full_count or unexpected_mask_rows or images_count != len(rows) or masks_count != len(rows):
        conversion_status = "WARNING" if stats_rows else "FAIL"

    report = {
        "generated_at": now_iso(),
        "source_pair_manifest": rel(SOURCE_PAIR_MANIFEST),
        "derived_dataset_path": rel(OUT),
        "source_pair_count": len(rows),
        "images_count": images_count,
        "masks_count": masks_count,
        "overlay_preview_count": overlays_count,
        "split_counts": dict(split_counts),
        "mask_value_mapping": "source 2/3 -> output 255 foreground; source 0/1/4/other -> output 0 background_or_ignore_documented",
        "mask_output_unique_value_patterns": dict(mask_output_values),
        "source_mask_unique_value_patterns": dict(unique_value_patterns),
        "foreground_ratio": {
            "min": min(foreground_ratios) if foreground_ratios else None,
            "max": max(foreground_ratios) if foreground_ratios else None,
            "mean": sum(foreground_ratios) / len(foreground_ratios) if foreground_ratios else None,
        },
        "empty_mask_count": empty_count,
        "full_mask_count": full_count,
        "size_mismatch_count": size_mismatch_count,
        "unexpected_mask_value_count": unexpected_mask_rows,
        "missing_pair_count": missing_count,
        "foreground_ratio_low_warn_count": anomaly_counts.get("foreground_ratio_low", 0),
        "foreground_ratio_high_warn_count": anomaly_counts.get("foreground_ratio_high", 0),
        "anomaly_counts": dict(anomaly_counts),
        "anomaly_sample_count": anomaly_total,
        "conversion_status": conversion_status,
        "visual_qa_required": True,
        "segmentation_training_allowed": False,
        "boundaries": {
            "training_executed": False,
            "new_weights_generated": False,
            "original_images_modified": False,
            "original_yolo_labels_overwritten": False,
            "backend_modified": False,
            "env_modified": False,
        },
    }

    stats_fields = [
        "image_name",
        "split",
        "image_path",
        "mask_path",
        "image_width",
        "image_height",
        "mask_width",
        "mask_height",
        "mask_unique_values",
        "source_mask_unique_values",
        "foreground_pixel_count",
        "foreground_ratio",
        "empty_mask",
        "full_mask",
        "size_match",
        "notes",
    ]
    manifest_fields = [
        "image_name",
        "split",
        "source_image_path",
        "source_mask_path",
        "derived_image_path",
        "derived_mask_path",
        "pair_status",
        "usable_for_visual_qa",
        "notes",
    ]
    atomic_write_csv(REPORTS / "uav_blb_segmentation_408_v1_mask_stats.csv", stats_rows, stats_fields)
    atomic_write_csv(REPORTS / "uav_blb_segmentation_408_v1_pair_manifest.csv", manifest_rows, manifest_fields)
    atomic_write_csv(OUT / "meta" / "conversion_manifest.csv", manifest_rows, manifest_fields)
    atomic_write_json(REPORTS / "uav_blb_segmentation_408_v1_conversion_report.json", report)
    write_dataset_docs(report)
    write_reports(report)
    write_status(report)
    return report


def write_reports(report: dict[str, Any]) -> None:
    md = f"""# UAV BLB Segmentation 408 v1 Conversion Report

## Boundary

- training_executed: `NO`
- new_weights_generated: `NO`
- original_images_modified: `NO`
- original_yolo_labels_overwritten: `NO`
- backend_modified: `NO`
- env_modified: `NO`
- bbox_route_status: `BLOCKED`
- segmentation_training_allowed: `false`

## Source And Derived Dataset

- source_pair_manifest: `{report['source_pair_manifest']}`
- derived_dataset_path: `{report['derived_dataset_path']}`
- source_pair_count: `{report['source_pair_count']}`
- images_count: `{report['images_count']}`
- masks_count: `{report['masks_count']}`
- split_counts: `{report['split_counts']}`

## Conversion Rule

- source raster values `2` and `3` -> output mask value `255` foreground (`bacterial_leaf_blight`)
- source raster values `0`, `1`, `4`, and other non-BLB values -> output mask value `0`
- image files are copied source multispectral TIF patches into the derived dataset.
- mask files are single-channel PNG files.

## Mask And Foreground Statistics

- mask_output_unique_value_patterns: `{report['mask_output_unique_value_patterns']}`
- source_mask_unique_value_patterns: `{report['source_mask_unique_value_patterns']}`
- foreground_ratio_min: `{report['foreground_ratio']['min']}`
- foreground_ratio_max: `{report['foreground_ratio']['max']}`
- foreground_ratio_mean: `{report['foreground_ratio']['mean']}`
- empty_mask_count: `{report['empty_mask_count']}`
- full_mask_count: `{report['full_mask_count']}`
- size_mismatch_count: `{report['size_mismatch_count']}`
- unexpected_mask_value_count: `{report['unexpected_mask_value_count']}`
- foreground_ratio_low_warn_count: `{report['foreground_ratio_low_warn_count']}`
- foreground_ratio_high_warn_count: `{report['foreground_ratio_high_warn_count']}`
- anomaly_sample_count: `{report['anomaly_sample_count']}`

## QA Preview

- overlay_preview_count: `{report['overlay_preview_count']}`
- overlay_preview_path: `datasets/rice_uav_ms_blb_segmentation_408_v1/overlays_preview`

## Status

- conversion_status: `{report['conversion_status']}`
- visual_qa_required: `true`
- segmentation_training_allowed: `false`
- next_step: `SEGMENTATION_VISUAL_QA_GATE`

The conversion output is a derived dataset for visual QA and later segmentation gate review. It is not a training release.
"""
    atomic_write_text(REPORTS / "uav_blb_segmentation_408_v1_conversion_report.md", md)


def write_status(report: dict[str, Any]) -> None:
    stage = "CONVERSION_COMPLETE" if report["conversion_status"] == "PASS" else "CONVERSION_WARNING"
    status = f"""segmentation_route_stage: {stage}
bbox_route_status: BLOCKED
segmentation_data_found: true
image_mask_pairs_found: {report['source_pair_count']}
derived_dataset_created: true
derived_dataset_path: {report['derived_dataset_path']}
mask_value_mapping: "2/3 -> foreground, 0/1/4 -> background_or_ignore_documented"
image_mask_alignment_status: PASS
conversion_status: {report['conversion_status']}
visual_qa_required: true
segmentation_training_allowed: false
images_count: {report['images_count']}
masks_count: {report['masks_count']}
overlay_preview_count: {report['overlay_preview_count']}
empty_mask_count: {report['empty_mask_count']}
full_mask_count: {report['full_mask_count']}
size_mismatch_count: {report['size_mismatch_count']}
unexpected_mask_value_count: {report['unexpected_mask_value_count']}
foreground_ratio_low_warn_count: {report['foreground_ratio_low_warn_count']}
foreground_ratio_high_warn_count: {report['foreground_ratio_high_warn_count']}
original_images_modified: false
original_labels_modified: false
weights_modified: false
backend_modified: false
env_modified: false
next_allowed_stage: SEGMENTATION_VISUAL_QA_GATE
notes:
  - derived images are copied multispectral TIF patches
  - derived masks are PNG binary masks with 0 background and 255 BLB foreground
  - segmentation training remains forbidden until visual QA gate passes
"""
    atomic_write_text(META / "uav_blb_segmentation_route_status.yaml", status)


def main() -> int:
    report = convert()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
