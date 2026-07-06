"""Generate UAV BLB segmentation_408_patch_v2 derived patch dataset.

This stage keeps the bbox route frozen and derives segmentation patches from
source multispectral TIF images plus raster masks only. It does not modify
source images, source raster masks, YOLO labels, backend files, env files, or
existing weights.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFEST = ROOT / "datasets" / "rice_uav_ms_blb_segmentation_408_v1" / "meta" / "conversion_manifest.csv"
OUT = ROOT / "datasets" / "rice_uav_ms_blb_segmentation_408_patch_v2"
REPORTS = ROOT / "reports"
META = ROOT / "metadata"

PATCH_SIZE = 256
STRIDE = 128
BLB_VALUES = {2, 3}
MASK_FOREGROUND_VALUE = 255
HARD_BG_TEXTURE_STD_MIN = 0.055
BOUNDARY_RATIO_MIN = 0.003
BOUNDARY_RATIO_MAX = 0.25
POSITIVE_RATIO_MIN = 0.01
PURE_BG_RATIO_MAX = 0.0001


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


def image_to_hwc(arr: np.ndarray) -> np.ndarray:
    if arr.ndim == 2:
        return arr[..., None]
    if arr.ndim == 3 and arr.shape[-1] <= 16:
        return arr
    if arr.ndim == 3 and arr.shape[0] <= 16:
        return np.moveaxis(arr, 0, -1)
    raise ValueError(f"unsupported image shape: {arr.shape}")


def normalize_band(band: np.ndarray) -> np.ndarray:
    band = band.astype(np.float32)
    low = np.percentile(band, 1)
    high = np.percentile(band, 99)
    if high <= low:
        high = low + 1.0
    return np.clip((band - low) / (high - low), 0, 1)


def rendered_rgb(hwc: np.ndarray) -> np.ndarray:
    if hwc.shape[-1] >= 3:
        rgb = np.stack([normalize_band(hwc[..., i]) for i in range(3)], axis=-1)
    else:
        one = normalize_band(hwc[..., 0])
        rgb = np.stack([one, one, one], axis=-1)
    return (rgb * 255).astype(np.uint8)


def sliding_positions(length: int) -> list[int]:
    if length <= PATCH_SIZE:
        return [0]
    positions = list(range(0, max(1, length - PATCH_SIZE + 1), STRIDE))
    last = length - PATCH_SIZE
    if positions[-1] != last:
        positions.append(last)
    return positions


def classify_patch(mask: np.ndarray, hwc_patch: np.ndarray) -> tuple[str, float, float, str]:
    foreground_ratio = float((mask > 0).sum() / mask.size)
    texture = float(np.mean([np.std(normalize_band(hwc_patch[..., idx])) for idx in range(min(5, hwc_patch.shape[-1]))]))
    notes = []
    if foreground_ratio >= POSITIVE_RATIO_MIN:
        if BOUNDARY_RATIO_MIN <= foreground_ratio <= BOUNDARY_RATIO_MAX:
            patch_type = "boundary_patch"
        else:
            patch_type = "positive_blb_patch"
    elif texture >= HARD_BG_TEXTURE_STD_MIN:
        patch_type = "hard_background_patch"
        notes.append("foreground absent but multispectral texture is high")
    else:
        patch_type = "pure_background_patch"
    if foreground_ratio <= PURE_BG_RATIO_MAX:
        notes.append("pure_or_nearly_pure_background")
    return patch_type, foreground_ratio, texture, "; ".join(notes)


def make_valid_mask_channel(hwc_patch: np.ndarray) -> np.ndarray:
    base = hwc_patch[..., : min(5, hwc_patch.shape[-1])].astype(np.float32)
    nonzero = np.any(np.abs(base) > 1e-6, axis=-1)
    return nonzero.astype(np.float32)


def ensure_dirs() -> None:
    for split in ("train", "val", "test"):
        for sub in ("images_tif", "masks", "features_d1_5band_valid", "features_d2_5band_ndvi", "features_d3_5band_ndre"):
            (OUT / sub / split).mkdir(parents=True, exist_ok=True)
    (OUT / "meta").mkdir(parents=True, exist_ok=True)
    (OUT / "visual_qa_samples").mkdir(parents=True, exist_ok=True)


def save_feature_variants(hwc_patch: np.ndarray, split: str, patch_id: str) -> dict[str, str]:
    base5 = np.zeros((PATCH_SIZE, PATCH_SIZE, 5), dtype=np.float32)
    take = min(5, hwc_patch.shape[-1])
    base5[..., :take] = hwc_patch[..., :take].astype(np.float32)
    eps = 1e-6
    # Conservative index assumptions for planning: band 3 is red, band 4 is NIR, band 2 approximates red-edge.
    red = base5[..., 2]
    red_edge = base5[..., 3]
    nir = base5[..., 4]
    ndvi = ((nir - red) / (nir + red + eps)).astype(np.float32)
    ndre = ((nir - red_edge) / (nir + red_edge + eps)).astype(np.float32)
    valid = make_valid_mask_channel(hwc_patch).astype(np.float32)
    variants = {
        "D1_5BAND_VALID": np.concatenate([base5, valid[..., None]], axis=-1),
        "D2_5BAND_NDVI": np.concatenate([base5, ndvi[..., None]], axis=-1),
        "D3_5BAND_NDRE": np.concatenate([base5, ndre[..., None]], axis=-1),
    }
    paths: dict[str, str] = {}
    dirs = {
        "D1_5BAND_VALID": "features_d1_5band_valid",
        "D2_5BAND_NDVI": "features_d2_5band_ndvi",
        "D3_5BAND_NDRE": "features_d3_5band_ndre",
    }
    for code, arr in variants.items():
        path = OUT / dirs[code] / split / f"{patch_id}.npy"
        np.save(path, arr.astype(np.float32))
        paths[code] = rel(path)
    return paths


def load_font() -> ImageFont.ImageFont:
    for candidate in (Path("C:/Windows/Fonts/arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), 13)
    return ImageFont.load_default()


def save_visual_sample(hwc_patch: np.ndarray, mask_patch: np.ndarray, out_path: Path, title: str) -> None:
    rgb = rendered_rgb(hwc_patch)
    overlay = rgb.copy()
    fg = mask_patch > 0
    overlay[fg] = (0.45 * overlay[fg] + 0.55 * np.array([255, 0, 0])).astype(np.uint8)
    raw = Image.fromarray(rgb)
    over = Image.fromarray(overlay)
    canvas = Image.new("RGB", (raw.width * 2 + 8, raw.height + 46), "white")
    canvas.paste(raw, (0, 46))
    canvas.paste(over, (raw.width + 8, 46))
    draw = ImageDraw.Draw(canvas)
    font = load_font()
    draw.text((6, 5), title[:150], fill=(0, 0, 0), font=font)
    draw.text((6, 25), "left=rendered TIF preview, right=BLB mask overlay", fill=(150, 0, 0), font=font)
    canvas.save(out_path, quality=92)


def clean_existing_outputs() -> None:
    if OUT.exists():
        for sub in ("images_tif", "masks", "features_d1_5band_valid", "features_d2_5band_ndvi", "features_d3_5band_ndre", "visual_qa_samples"):
            target = OUT / sub
            if target.exists():
                shutil.rmtree(target)


def generate() -> dict[str, Any]:
    if not SOURCE_MANIFEST.exists():
        raise FileNotFoundError(SOURCE_MANIFEST)
    clean_existing_outputs()
    ensure_dirs()
    source_rows = read_csv(SOURCE_MANIFEST)
    rows: list[dict[str, Any]] = []
    leak_tracker: dict[str, set[str]] = defaultdict(set)
    type_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    visual_counts: Counter[str] = Counter()

    for source in source_rows:
        split = source["split"]
        source_image = source_path(source["source_image_path"])
        source_mask = source_path(source["source_mask_path"])
        source_stem = Path(source["image_name"]).stem
        hwc = image_to_hwc(tifffile.imread(source_image)).astype(np.float32)
        raster = tifffile.imread(source_mask)
        binary = np.where(np.isin(raster, list(BLB_VALUES)), MASK_FOREGROUND_VALUE, 0).astype(np.uint8)
        if hwc.shape[:2] != binary.shape[:2]:
            raise ValueError(f"image/mask size mismatch for {source['image_name']}: {hwc.shape} vs {binary.shape}")
        for y in sliding_positions(hwc.shape[0]):
            for x in sliding_positions(hwc.shape[1]):
                hwc_patch = hwc[y : y + PATCH_SIZE, x : x + PATCH_SIZE, :]
                mask_patch = binary[y : y + PATCH_SIZE, x : x + PATCH_SIZE]
                if hwc_patch.shape[0] != PATCH_SIZE or hwc_patch.shape[1] != PATCH_SIZE:
                    padded = np.zeros((PATCH_SIZE, PATCH_SIZE, hwc.shape[-1]), dtype=np.float32)
                    padded[: hwc_patch.shape[0], : hwc_patch.shape[1], :] = hwc_patch
                    mask_padded = np.zeros((PATCH_SIZE, PATCH_SIZE), dtype=np.uint8)
                    mask_padded[: mask_patch.shape[0], : mask_patch.shape[1]] = mask_patch
                    hwc_patch = padded
                    mask_patch = mask_padded
                patch_type, fg_ratio, texture, notes = classify_patch(mask_patch, hwc_patch)
                patch_id = f"{source_stem}_y{y:04d}_x{x:04d}"
                image_out = OUT / "images_tif" / split / f"{patch_id}.tif"
                mask_out = OUT / "masks" / split / f"{patch_id}.png"
                tifffile.imwrite(image_out, hwc_patch.astype(np.float32))
                Image.fromarray(mask_patch, mode="L").save(mask_out)
                feature_paths = save_feature_variants(hwc_patch, split, patch_id)
                type_counts[patch_type] += 1
                split_counts[split] += 1
                leak_tracker[source_stem].add(split)
                if visual_counts[patch_type] < 8:
                    visual_out = OUT / "visual_qa_samples" / f"{patch_id}_{patch_type}.jpg"
                    save_visual_sample(
                        hwc_patch,
                        mask_patch,
                        visual_out,
                        f"{patch_id} | split={split} | type={patch_type} | fg={fg_ratio:.4f}",
                    )
                    visual_counts[patch_type] += 1
                rows.append(
                    {
                        "patch_id": patch_id,
                        "source_image_name": source["image_name"],
                        "source_image_path": rel(source_image),
                        "source_mask_path": rel(source_mask),
                        "split": split,
                        "x": x,
                        "y": y,
                        "patch_size": PATCH_SIZE,
                        "stride": STRIDE,
                        "image_tif_path": rel(image_out),
                        "mask_png_path": rel(mask_out),
                        "feature_d1_path": feature_paths["D1_5BAND_VALID"],
                        "feature_d2_path": feature_paths["D2_5BAND_NDVI"],
                        "feature_d3_path": feature_paths["D3_5BAND_NDRE"],
                        "input_config_candidates": "D1_5BAND_VALID|D2_5BAND_NDVI|D3_5BAND_NDRE",
                        "patch_type": patch_type,
                        "foreground_ratio": f"{fg_ratio:.8f}",
                        "texture_score": f"{texture:.8f}",
                        "notes": notes,
                    }
                )

    leak_sources = {source: sorted(splits) for source, splits in leak_tracker.items() if len(splits) > 1}
    fieldnames = [
        "patch_id",
        "source_image_name",
        "source_image_path",
        "source_mask_path",
        "split",
        "x",
        "y",
        "patch_size",
        "stride",
        "image_tif_path",
        "mask_png_path",
        "feature_d1_path",
        "feature_d2_path",
        "feature_d3_path",
        "input_config_candidates",
        "patch_type",
        "foreground_ratio",
        "texture_score",
        "notes",
    ]
    atomic_write_csv(OUT / "meta" / "split_manifest.csv", rows, fieldnames)
    atomic_write_csv(REPORTS / "uav_blb_segmentation_408_patch_v2_dataset_manifest.csv", rows, fieldnames)
    report = {
        "generated_at": now_iso(),
        "dataset": "rice_uav_ms_blb_segmentation_408_patch_v2",
        "dataset_path": rel(OUT),
        "source_manifest": rel(SOURCE_MANIFEST),
        "source_sample_count": len(source_rows),
        "patch_count": len(rows),
        "patch_size": PATCH_SIZE,
        "stride": STRIDE,
        "split_counts": dict(split_counts),
        "patch_type_counts": dict(type_counts),
        "input_configs": {
            "D1_5BAND_VALID": "first 5 bands + valid-image mask channel",
            "D2_5BAND_NDVI": "first 5 bands + NDVI derived channel",
            "D3_5BAND_NDRE": "first 5 bands + NDRE derived channel",
        },
        "all_configs_output_channels": 6,
        "zero_padding_as_formal_feature": False,
        "split_leakage_found": bool(leak_sources),
        "split_leakage_sources": leak_sources,
        "bbox_route_status": "BLOCKED",
        "training_executed": False,
        "weights_generated": False,
        "production_ready": False,
        "backend_integration_allowed": False,
    }
    write_docs(report)
    return report


def write_docs(report: dict[str, Any]) -> None:
    atomic_write_json(REPORTS / "uav_blb_segmentation_408_patch_v2_dataset_manifest.json", report)
    md = f"""# UAV BLB Segmentation 408 Patch v2 Dataset Manifest

## Boundary

- bbox_route_status: `BLOCKED`
- training_executed: `NO`
- weights_generated: `NO`
- original_images_modified: `NO`
- original_raster_masks_modified: `NO`
- original_yolo_labels_overwritten: `NO`
- backend_modified: `NO`
- env_modified: `NO`
- production_ready: `false`
- backend_integration_allowed: `false`

## Dataset

- dataset_path: `{report['dataset_path']}`
- source_manifest: `{report['source_manifest']}`
- source_sample_count: `{report['source_sample_count']}`
- patch_count: `{report['patch_count']}`
- patch_size: `{report['patch_size']}`
- stride: `{report['stride']}`
- split_counts: `{report['split_counts']}`
- split_leakage_found: `{report['split_leakage_found']}`

The source 408 images are already 256 x 256 patches, so the current extraction creates one 256 x 256 patch per source image. The extractor is still implemented with `patch_size=256` and `stride=128`, so it can be reused if larger source rasters are introduced later.

## Patch Sampling Types

- patch_type_counts: `{report['patch_type_counts']}`
- required sampling categories:
  - positive BLB patch
  - boundary patch
  - hard background patch
  - pure background patch

The present 408-patch source set is BLB-audited and foreground-heavy, so pure and hard background counts may be limited. These categories are still encoded in the manifest and extraction logic for formal balancing and future source expansion.

## Input Configurations

All formal configurations output a 6-channel tensor. The smoke-stage zero-padding policy is not used as a formal feature.

- `D1_5BAND_VALID`: first 5 multispectral bands + valid-image mask channel.
- `D2_5BAND_NDVI`: first 5 multispectral bands + NDVI derived channel.
- `D3_5BAND_NDRE`: first 5 multispectral bands + NDRE derived channel.

## Files

- split_manifest: `datasets/rice_uav_ms_blb_segmentation_408_patch_v2/meta/split_manifest.csv`
- report copy: `reports/uav_blb_segmentation_408_patch_v2_dataset_manifest.csv`
- visual QA samples: `datasets/rice_uav_ms_blb_segmentation_408_patch_v2/visual_qa_samples`

This dataset is a training-candidate dataset, not a production dataset. Backend integration remains blocked.
"""
    atomic_write_text(REPORTS / "uav_blb_segmentation_408_patch_v2_dataset_manifest.md", md)
    data_yaml = """dataset: rice_uav_ms_blb_segmentation_408_patch_v2
task: binary_segmentation
patch_size: 256
stride: 128
manifest: meta/split_manifest.csv
mask_format: png_binary_0_255
input_configs:
  D1_5BAND_VALID:
    feature_column: feature_d1_path
    channels: 6
    description: first 5 multispectral bands plus valid-image mask channel
  D2_5BAND_NDVI:
    feature_column: feature_d2_path
    channels: 6
    description: first 5 multispectral bands plus NDVI
  D3_5BAND_NDRE:
    feature_column: feature_d3_path
    channels: 6
    description: first 5 multispectral bands plus NDRE
status:
  bbox_route_status: BLOCKED
  production_ready: false
  backend_integration_allowed: false
"""
    atomic_write_text(OUT / "data.yaml", data_yaml)


def write_status(report: dict[str, Any]) -> None:
    status = f"""bbox_route_status: BLOCKED
segmentation_route_stage: SEGMENTATION_408_PATCH_V2_DATASET_READY
segmentation_patch_v2_dataset_created: true
segmentation_patch_v2_dataset_path: {report['dataset_path']}
patch_size: {report['patch_size']}
stride: {report['stride']}
source_sample_count: {report['source_sample_count']}
patch_count: {report['patch_count']}
split_leakage_found: {str(report['split_leakage_found']).lower()}
input_configs_ready:
  - D1_5BAND_VALID
  - D2_5BAND_NDVI
  - D3_5BAND_NDRE
formal_zero_padding_used: false
formal_training_ready_for_gate: true
production_ready: false
backend_integration_allowed: false
original_images_modified: false
original_labels_modified: false
original_raster_masks_modified: false
backend_modified: false
env_modified: false
next_allowed_stage: FORMAL_SEGMENTATION_TRAINING_MATRIX_OR_THRESHOLD_SWEEP
notes:
  - bbox route is frozen and remains blocked
  - patch v2 is derived from source TIF and raster masks only
  - backend integration requires a later acceptance gate
"""
    atomic_write_text(META / "uav_blb_segmentation_route_status.yaml", status)


def main() -> int:
    report = generate()
    write_status(report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
