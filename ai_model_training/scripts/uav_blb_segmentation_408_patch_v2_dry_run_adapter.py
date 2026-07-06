"""Dry-run inference adapter for UAV BLB segmentation_408_patch_v2.

This script validates the formal candidate as an offline/backend-style dry run.
It does not modify backend routes, env files, source images, source masks, YOLO
labels, or production weights.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
import torch
from PIL import Image, ImageDraw, ImageFont

from train_uav_blb_segmentation_408_patch_v2_formal import (
    INPUT_CHANNELS,
    apply_postprocess,
    build_model,
    normalize_feature,
)


ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "datasets" / "rice_uav_ms_blb_segmentation_408_patch_v2"
MANIFEST = DATASET_DIR / "meta" / "split_manifest.csv"
RUN_NAME = "D2_5BAND_NDVI__UNET_BASELINE__BCE_TVERSKY_A07_B03"
RUN_DIR = ROOT / "runs" / "uav_blb_segmentation_408_patch_v2_formal" / RUN_NAME
WEIGHT_PATH = RUN_DIR / "best_formal_candidate.pth"
METRICS_PATH = RUN_DIR / "metrics_summary.json"
REPORTS = ROOT / "reports"
OUTPUT_DIR = REPORTS / "uav_blb_segmentation_408_patch_v2_dry_run_sample_outputs"
LOCK_JSON = REPORTS / "uav_blb_segmentation_408_patch_v2_model_artifact_lock.json"
PARITY_CSV = REPORTS / "uav_blb_segmentation_408_patch_v2_adapter_parity_validation.csv"
REVIEW_MD = REPORTS / "uav_blb_segmentation_408_patch_v2_backend_dry_run_candidate_review.md"
META_PATH = ROOT / "metadata" / "uav_blb_segmentation_route_status.yaml"

PATCH_SIZE = 256
STRIDE = 128
THRESHOLD = 0.45
POSTPROCESS_MODE = "THRESHOLD_REMOVE_SMALL_COMPONENTS"
MIN_AREA = 128
PARITY_SAMPLE_COUNT = 6
AREA_RATIO_TOLERANCE = 1e-6
MASK_AREA_DIFF_TOLERANCE = 0
MODEL_NAME = "uav_blb_segmentation_408_patch_v2_d2_ndvi_unet_baseline"
MODEL_STAGE = "formal_candidate"
MODEL_WARNING = "experimental_dry_run_only"


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


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    raise ValueError(f"unsupported TIF shape: {arr.shape}")


def build_d2_5band_ndvi(hwc: np.ndarray) -> np.ndarray:
    base5 = np.zeros((hwc.shape[0], hwc.shape[1], 5), dtype=np.float32)
    take = min(5, hwc.shape[-1])
    base5[..., :take] = hwc[..., :take].astype(np.float32)
    eps = 1e-6
    red = base5[..., 2]
    nir = base5[..., 4]
    ndvi = ((nir - red) / (nir + red + eps)).astype(np.float32)
    return np.concatenate([base5, ndvi[..., None]], axis=-1).astype(np.float32)


def normalize_band(band: np.ndarray) -> np.ndarray:
    band = band.astype(np.float32)
    low = np.percentile(band, 1)
    high = np.percentile(band, 99)
    if high <= low:
        high = low + 1.0
    return np.clip((band - low) / (high - low), 0, 1)


def render_rgb_from_tif_hwc(hwc: np.ndarray) -> np.ndarray:
    if hwc.shape[-1] >= 3:
        rgb = np.stack([normalize_band(hwc[..., idx]) for idx in range(3)], axis=-1)
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


def pad_patch(arr: np.ndarray, y: int, x: int) -> tuple[np.ndarray, int, int]:
    patch = arr[y : y + PATCH_SIZE, x : x + PATCH_SIZE, :]
    valid_h, valid_w = patch.shape[:2]
    if valid_h == PATCH_SIZE and valid_w == PATCH_SIZE:
        return patch, valid_h, valid_w
    padded = np.zeros((PATCH_SIZE, PATCH_SIZE, arr.shape[-1]), dtype=arr.dtype)
    padded[:valid_h, :valid_w, :] = patch
    return padded, valid_h, valid_w


def load_model(device: torch.device) -> torch.nn.Module:
    model = build_model("UNET_BASELINE")
    checkpoint = torch.load(WEIGHT_PATH, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model"])
    model.to(device)
    model.eval()
    return model


@torch.no_grad()
def infer_probability_map_from_tif(tif_path: Path, model: torch.nn.Module, device: torch.device) -> tuple[np.ndarray, np.ndarray]:
    hwc = image_to_hwc(tifffile.imread(tif_path)).astype(np.float32)
    h, w = hwc.shape[:2]
    prob_sum = np.zeros((h, w), dtype=np.float32)
    count = np.zeros((h, w), dtype=np.float32)
    d2 = build_d2_5band_ndvi(hwc)
    for y in sliding_positions(h):
        for x in sliding_positions(w):
            patch, valid_h, valid_w = pad_patch(d2, y, x)
            patch = normalize_feature(patch)
            tensor = torch.from_numpy(np.moveaxis(patch, -1, 0)[None].astype(np.float32)).to(device)
            prob = torch.sigmoid(model(tensor))[0, 0].cpu().numpy()
            prob_sum[y : y + valid_h, x : x + valid_w] += prob[:valid_h, :valid_w]
            count[y : y + valid_h, x : x + valid_w] += 1.0
    probability = prob_sum / np.maximum(count, 1.0)
    return probability.astype(np.float32), hwc


@torch.no_grad()
def infer_reference_from_feature(feature_path: Path, model: torch.nn.Module, device: torch.device) -> np.ndarray:
    feature = normalize_feature(np.load(feature_path))
    tensor = torch.from_numpy(np.moveaxis(feature, -1, 0)[None].astype(np.float32)).to(device)
    return torch.sigmoid(model(tensor))[0, 0].cpu().numpy().astype(np.float32)


def save_dry_run_outputs(row: dict[str, str], prob: np.ndarray, binary: np.ndarray, hwc: np.ndarray) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = row["patch_id"]
    prob_npy = OUTPUT_DIR / f"{stem}_probability_map.npy"
    prob_png = OUTPUT_DIR / f"{stem}_probability_map.png"
    mask_png = OUTPUT_DIR / f"{stem}_binary_mask.png"
    overlay_jpg = OUTPUT_DIR / f"{stem}_overlay.jpg"
    meta_json = OUTPUT_DIR / f"{stem}_dry_run_metadata.json"

    np.save(prob_npy, prob.astype(np.float32))
    Image.fromarray(np.clip(prob * 255, 0, 255).astype(np.uint8), mode="L").save(prob_png)
    Image.fromarray((binary.astype(np.uint8) * 255), mode="L").save(mask_png)

    rgb = render_rgb_from_tif_hwc(hwc)
    overlay = rgb.copy()
    overlay[binary] = (0.45 * overlay[binary] + 0.55 * np.array([255, 0, 0])).astype(np.uint8)
    canvas = Image.new("RGB", (rgb.shape[1] * 2, rgb.shape[0] + 38), "white")
    canvas.paste(Image.fromarray(rgb), (0, 38))
    canvas.paste(Image.fromarray(overlay), (rgb.shape[1], 38))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    title = f"{stem} | dry-run candidate | disease_area_ratio={float(binary.mean()):.4f}"
    draw.text((5, 5), title[:180], fill=(0, 0, 0), font=font)
    draw.text((5, 22), "left=TIF preview, right=postprocessed mask overlay", fill=(150, 0, 0), font=font)
    canvas.save(overlay_jpg, quality=92)

    meta = {
        "patch_id": stem,
        "source_image_name": row.get("source_image_name", ""),
        "input_tif": rel(source_path(row["image_tif_path"])),
        "probability_map": rel(prob_npy),
        "probability_png": rel(prob_png),
        "binary_mask": rel(mask_png),
        "overlay_image": rel(overlay_jpg),
        "disease_area_ratio": float(binary.mean()),
        "model_name": MODEL_NAME,
        "model_stage": MODEL_STAGE,
        "model_warning": MODEL_WARNING,
        "input_config": "D2_5BAND_NDVI",
        "input_channels": INPUT_CHANNELS,
        "patch_size": PATCH_SIZE,
        "stride": STRIDE,
        "threshold": THRESHOLD,
        "postprocess_mode": POSTPROCESS_MODE,
        "min_area": MIN_AREA,
        "production_ready": False,
        "backend_integration_allowed": "dry_run_only",
    }
    atomic_write_json(meta_json, meta)
    meta["metadata_json"] = rel(meta_json)
    return meta


def write_artifact_lock(metrics: dict[str, Any]) -> dict[str, Any]:
    stat = WEIGHT_PATH.stat()
    selected = metrics["selected_postprocess"]
    test_metrics = metrics["test_metrics_at_selected_postprocess"]
    payload = {
        "locked_at": now_iso(),
        "artifact_status": "LOCKED_FOR_BACKEND_DRY_RUN_CANDIDATE_REVIEW",
        "production_ready": False,
        "backend_integration_allowed": "dry_run_only",
        "backend_default_route_modified": False,
        "env_modified": False,
        "weight_path": rel(WEIGHT_PATH),
        "sha256": sha256_file(WEIGHT_PATH),
        "file_size_bytes": stat.st_size,
        "last_write_time": stat.st_mtime,
        "run_name": RUN_NAME,
        "training_config_path": "configs/uav_blb_segmentation_408_patch_v2_formal_training_matrix.yaml",
        "dataset": "rice_uav_ms_blb_segmentation_408_patch_v2",
        "manifest": rel(MANIFEST),
        "input_config": {
            "code": "D2_5BAND_NDVI",
            "input_channels": INPUT_CHANNELS,
            "source": "5-band TIF plus NDVI",
            "red_band_index": 2,
            "nir_band_index": 4,
            "normalization": "per-channel 1%-99% percentile clipping to 0-1",
        },
        "model_config": {
            "model_code": "UNET_BASELINE",
            "loss_code": "BCE_TVERSKY_A07_B03",
            "epochs_completed": metrics["epochs_completed"],
            "best_epoch": metrics["best_epoch"],
        },
        "inference_config": {
            "patch_size": PATCH_SIZE,
            "stride": STRIDE,
            "stitching": "overlap average probability map",
            "postprocess_mode": selected["postprocess_mode"],
            "threshold": selected["threshold"],
            "min_area": selected["min_area"],
        },
        "test_metrics": test_metrics,
        "warnings": [
            "experimental dry-run only",
            "not production ready",
            "not connected to backend default route",
            "does not replace any existing model weight",
        ],
    }
    atomic_write_json(LOCK_JSON, payload)
    return payload


def update_status_yaml() -> None:
    content = """bbox_route_status: BLOCKED
segmentation_route_stage: BACKEND_DRY_RUN_CANDIDATE_REVIEW_PASS
segmentation_patch_v2_dataset_created: true
formal_training_executed: true
formal_single_run_numeric_gate: PASS
formal_single_run_visual_qa_gate: PASS
backend_dry_run_candidate_review: PASS
backend_integration_candidate: true
backend_integration_allowed: dry_run_only
backend_integration_mode: dry_run_candidate_only
production_ready: false
original_images_modified: false
original_labels_modified: false
original_raster_masks_modified: false
backend_modified: false
env_modified: false
formal_single_run_name: D2_5BAND_NDVI__UNET_BASELINE__BCE_TVERSKY_A07_B03
formal_single_run_selected_threshold: 0.45
formal_single_run_selected_postprocess: THRESHOLD_REMOVE_SMALL_COMPONENTS
formal_single_run_selected_min_area: 128
next_allowed_stage: BACKEND_DRY_RUN_ONLY_OR_PRODUCTION_APPROVAL_GATE
notes:
  - bbox route remains blocked
  - dry-run candidate is not production ready
  - backend default route remains unchanged
  - backend integration is limited to dry-run review artifacts only
"""
    atomic_write_text(META_PATH, content)


def write_review_report(lock: dict[str, Any], parity_rows: list[dict[str, Any]], sample_outputs: list[dict[str, Any]]) -> None:
    pass_count = sum(1 for row in parity_rows if row["parity_status"] == "PASS")
    reviewed = len(parity_rows)
    max_prob_diff = max(float(row["probability_max_abs_diff"]) for row in parity_rows) if parity_rows else 0.0
    max_area_ratio_diff = max(float(row["disease_area_ratio_abs_diff"]) for row in parity_rows) if parity_rows else 0.0
    status = "PASS" if pass_count == reviewed and reviewed > 0 else "FAIL"
    lines = [
        "# UAV BLB Segmentation 408 Patch v2 Backend Dry-Run Candidate Review",
        "",
        "## Decision",
        "",
        f"- backend_dry_run_candidate_review: `{status}`",
        "- backend_integration_candidate: `true`",
        "- backend_integration_allowed: `dry_run_only`",
        "- production_ready: `false`",
        "- backend_default_route_modified: `NO`",
        "- env_modified: `NO`",
        "- existing_weights_replaced: `NO`",
        "- formal_disease_statistics_polluted: `NO`",
        "- latest_alerts_polluted: `NO`",
        "",
        "## Locked Artifact",
        "",
        f"- weight_path: `{lock['weight_path']}`",
        f"- sha256: `{lock['sha256']}`",
        f"- file_size_bytes: `{lock['file_size_bytes']}`",
        f"- run_name: `{RUN_NAME}`",
        "- model: `UNET_BASELINE`",
        "- input_config: `D2_5BAND_NDVI`",
        "- input: `5-band TIF + NDVI`",
        "- normalization: `per-channel 1%-99% percentile clipping to 0-1`",
        f"- patch_size: `{PATCH_SIZE}`",
        f"- stride: `{STRIDE}`",
        f"- threshold: `{THRESHOLD}`",
        f"- postprocess: `{POSTPROCESS_MODE}`",
        f"- min_area: `{MIN_AREA}`",
        "",
        "## Dry-Run Adapter",
        "",
        "- adapter_script: `scripts/uav_blb_segmentation_408_patch_v2_dry_run_adapter.py`",
        "- reads patch-level or larger TIF input and converts it to D2 6-channel tensor.",
        "- computes NDVI with red band index 2 and NIR band index 4.",
        "- runs sliding-window patch inference with overlap-averaged probability stitching.",
        "- applies threshold + remove-small-components postprocess matching the selected formal candidate.",
        "- outputs probability map, binary mask, overlay image, disease_area_ratio, model_name, model_stage, and model_warning.",
        "",
        "## Offline/Adapter Parity Validation",
        "",
        f"- reviewed_samples: `{reviewed}`",
        f"- pass_samples: `{pass_count}`",
        f"- max_probability_abs_diff: `{max_prob_diff:.10f}`",
        f"- max_disease_area_ratio_abs_diff: `{max_area_ratio_diff:.10f}`",
        f"- parity_csv: `{rel(PARITY_CSV)}`",
        "",
        "## Dry-Run Sample Outputs",
        "",
        f"- output_dir: `{rel(OUTPUT_DIR)}`",
        "",
    ]
    for item in sample_outputs:
        lines.append(f"- `{item['patch_id']}`: overlay `{item['overlay_image']}`, ratio `{item['disease_area_ratio']:.4f}`")
    lines.extend(
        [
            "",
            "## Boundary Confirmation",
            "",
            "- training_executed_this_stage: `NO`",
            "- production_ready: `false`",
            "- backend_integration_allowed: `dry_run_only`",
            "- backend_modified: `NO`",
            "- env_modified: `NO`",
            "- original_images_modified: `NO`",
            "- original_raster_masks_modified: `NO`",
            "- original_yolo_labels_overwritten: `NO`",
            "- bbox_route_status: `BLOCKED`",
            "",
            "## Next Step",
            "",
            "Use the dry-run adapter outputs for a separate backend dry-run UI/API design review. A separate production approval gate is still required before any real backend integration, route change, alert flow, statistics flow, or weight replacement.",
            "",
        ]
    )
    atomic_write_text(REVIEW_MD, "\n".join(lines))


def main() -> int:
    if not WEIGHT_PATH.exists():
        raise FileNotFoundError(WEIGHT_PATH)
    if not METRICS_PATH.exists():
        raise FileNotFoundError(METRICS_PATH)
    if not MANIFEST.exists():
        raise FileNotFoundError(MANIFEST)

    rows = read_csv(MANIFEST)
    test_rows = [row for row in rows if row["split"] == "test"][:PARITY_SAMPLE_COUNT]
    if not test_rows:
        raise RuntimeError("no test rows found for dry-run parity validation")

    metrics = read_json(METRICS_PATH)
    lock = write_artifact_lock(metrics)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_model(device)

    parity_rows: list[dict[str, Any]] = []
    sample_outputs: list[dict[str, Any]] = []
    for row in test_rows:
        tif_path = source_path(row["image_tif_path"])
        feature_path = source_path(row["feature_d2_path"])
        adapter_prob, hwc = infer_probability_map_from_tif(tif_path, model, device)
        reference_prob = infer_reference_from_feature(feature_path, model, device)
        if adapter_prob.shape != reference_prob.shape:
            raise ValueError(f"shape mismatch for {row['patch_id']}: adapter {adapter_prob.shape}, reference {reference_prob.shape}")

        adapter_binary = apply_postprocess(adapter_prob, THRESHOLD, POSTPROCESS_MODE, MIN_AREA)
        reference_binary = apply_postprocess(reference_prob, THRESHOLD, POSTPROCESS_MODE, MIN_AREA)
        adapter_area = int(adapter_binary.sum())
        reference_area = int(reference_binary.sum())
        adapter_ratio = float(adapter_binary.mean())
        reference_ratio = float(reference_binary.mean())
        prob_max_abs_diff = float(np.max(np.abs(adapter_prob - reference_prob)))
        mask_area_diff = int(abs(adapter_area - reference_area))
        ratio_abs_diff = float(abs(adapter_ratio - reference_ratio))
        pass_status = (
            prob_max_abs_diff <= 1e-5
            and mask_area_diff <= MASK_AREA_DIFF_TOLERANCE
            and ratio_abs_diff <= AREA_RATIO_TOLERANCE
        )

        sample_meta = save_dry_run_outputs(row, adapter_prob, adapter_binary, hwc)
        sample_outputs.append(sample_meta)
        parity_rows.append(
            {
                "patch_id": row["patch_id"],
                "source_image_name": row.get("source_image_name", ""),
                "split": row["split"],
                "input_tif": rel(tif_path),
                "reference_feature_d2": rel(feature_path),
                "adapter_mask_area": adapter_area,
                "reference_mask_area": reference_area,
                "mask_area_abs_diff": mask_area_diff,
                "adapter_disease_area_ratio": f"{adapter_ratio:.10f}",
                "reference_disease_area_ratio": f"{reference_ratio:.10f}",
                "disease_area_ratio_abs_diff": f"{ratio_abs_diff:.10f}",
                "probability_max_abs_diff": f"{prob_max_abs_diff:.10f}",
                "threshold": THRESHOLD,
                "postprocess_mode": POSTPROCESS_MODE,
                "min_area": MIN_AREA,
                "overlay_image": sample_meta["overlay_image"],
                "parity_status": "PASS" if pass_status else "FAIL",
                "notes": "adapter TIF->D2 path compared with existing feature_d2 offline path",
            }
        )

    atomic_write_csv(
        PARITY_CSV,
        parity_rows,
        [
            "patch_id",
            "source_image_name",
            "split",
            "input_tif",
            "reference_feature_d2",
            "adapter_mask_area",
            "reference_mask_area",
            "mask_area_abs_diff",
            "adapter_disease_area_ratio",
            "reference_disease_area_ratio",
            "disease_area_ratio_abs_diff",
            "probability_max_abs_diff",
            "threshold",
            "postprocess_mode",
            "min_area",
            "overlay_image",
            "parity_status",
            "notes",
        ],
    )

    status = "PASS" if all(row["parity_status"] == "PASS" for row in parity_rows) else "FAIL"
    write_review_report(lock, parity_rows, sample_outputs)
    if status == "PASS":
        update_status_yaml()
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
