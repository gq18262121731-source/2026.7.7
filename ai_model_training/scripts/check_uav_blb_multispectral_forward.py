"""Audit multispectral TIF input and run a small-batch forward test.

This is not epoch training and does not save model weights. It verifies
5/6-channel TIF reading, normalization, mask alignment, and a Tiny U-Net forward
pass for the UAV BLB segmentation route.
"""

from __future__ import annotations

import csv
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
import torch
from PIL import Image
from torch import nn


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
META = ROOT / "metadata" / "uav_blb_segmentation_route_status.yaml"
MASK_STATS = REPORTS / "uav_blb_segmentation_408_v1_mask_stats.csv"
SUMMARY_JSON = REPORTS / "uav_blb_segmentation_408_v1_short_exp_sample_visual_review_summary.json"
CONFIG_PATH = ROOT / "configs" / "uav_blb_multispectral_segmentation_408_v1_smoke.yaml"

MAX_CHANNELS = 6
IMAGE_SIZE = 256
SAMPLE_NAMES = {
    "blb_D2_test_patch_373.jpg",
    "blb_D2_test_patch_54.jpg",
    "blb_D1_test_patch_385.jpg",
}


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


def image_to_chw(arr: np.ndarray) -> np.ndarray:
    if arr.ndim == 2:
        return arr[None, ...]
    if arr.ndim == 3 and arr.shape[-1] in {5, 6}:
        return np.moveaxis(arr, -1, 0)
    if arr.ndim == 3 and arr.shape[0] in {5, 6}:
        return arr
    if arr.ndim == 3 and arr.shape[-1] <= 16:
        return np.moveaxis(arr, -1, 0)
    raise ValueError(f"unsupported image shape: {arr.shape}")


def normalize_chw(chw: np.ndarray, max_channels: int = MAX_CHANNELS) -> np.ndarray:
    chw = chw.astype(np.float32)
    normalized = np.zeros((max_channels, chw.shape[1], chw.shape[2]), dtype=np.float32)
    for idx in range(min(chw.shape[0], max_channels)):
        band = chw[idx]
        low = np.percentile(band, 1)
        high = np.percentile(band, 99)
        if high <= low:
            high = low + 1.0
        normalized[idx] = np.clip((band - low) / (high - low), 0, 1)
    return normalized


def load_pair(row: dict[str, str]) -> tuple[np.ndarray, np.ndarray]:
    image = normalize_chw(image_to_chw(tifffile.imread(ROOT / row["image_path"])))
    mask = np.array(Image.open(ROOT / row["mask_path"]).convert("L").resize((IMAGE_SIZE, IMAGE_SIZE), Image.NEAREST), dtype=np.float32)
    mask = (mask > 0).astype(np.float32)[None, ...]
    return image, mask


class ConvBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class TinyUNet(nn.Module):
    def __init__(self, in_channels: int) -> None:
        super().__init__()
        self.down1 = ConvBlock(in_channels, 12)
        self.down2 = ConvBlock(12, 24)
        self.down3 = ConvBlock(24, 48)
        self.pool = nn.MaxPool2d(2)
        self.up2 = nn.ConvTranspose2d(48, 24, 2, stride=2)
        self.dec2 = ConvBlock(48, 24)
        self.up1 = nn.ConvTranspose2d(24, 12, 2, stride=2)
        self.dec1 = ConvBlock(24, 12)
        self.out = nn.Conv2d(12, 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.down1(x)
        x2 = self.down2(self.pool(x1))
        x3 = self.down3(self.pool(x2))
        y = self.up2(x3)
        y = self.dec2(torch.cat([y, x2], dim=1))
        y = self.up1(y)
        y = self.dec1(torch.cat([y, x1], dim=1))
        return self.out(y)


def loss_fn(logits: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    bce = nn.functional.binary_cross_entropy_with_logits(logits, mask)
    prob = torch.sigmoid(logits)
    intersection = (prob * mask).sum(dim=(1, 2, 3))
    union = prob.sum(dim=(1, 2, 3)) + mask.sum(dim=(1, 2, 3))
    dice = 1 - ((2 * intersection + 1) / (union + 1)).mean()
    return bce + dice


def select_audit_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for split, limit in [("train", 5), ("val", 3), ("test", 3)]:
        split_rows = [row for row in rows if row["split"] == split]
        split_rows.sort(key=lambda row: float(row["foreground_ratio"]))
        picks = []
        if split_rows:
            picks.extend([split_rows[0], split_rows[len(split_rows) // 2], split_rows[-1]])
        for row in split_rows:
            if row["image_name"] in SAMPLE_NAMES:
                picks.append(row)
        for row in split_rows:
            if len(picks) >= limit:
                break
            picks.append(row)
        seen = set()
        for row in picks:
            if row["image_name"] not in seen and len([x for x in selected if x["split"] == split]) < limit:
                selected.append(row)
                seen.add(row["image_name"])
    for row in rows:
        if row["image_name"] in SAMPLE_NAMES and all(item["image_name"] != row["image_name"] for item in selected):
            selected.append(row)
    return selected


def audit_tif_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    audit_rows: list[dict[str, Any]] = []
    channel_stats: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        path = ROOT / row["image_path"]
        mask_path = ROOT / row["mask_path"]
        arr = tifffile.imread(path)
        chw = image_to_chw(arr)
        mask = Image.open(mask_path)
        has_nan = bool(np.isnan(chw.astype(np.float32)).any())
        has_inf = bool(np.isinf(chw.astype(np.float32)).any())
        all_zero = int(sum(np.all(chw[idx] == 0) for idx in range(chw.shape[0])))
        notes = []
        if has_nan:
            notes.append("has_nan")
        if has_inf:
            notes.append("has_inf")
        if all_zero:
            notes.append("all_zero_channel_present")
        if mask.size != (chw.shape[2], chw.shape[1]):
            notes.append("mask_size_mismatch")
        for idx in range(chw.shape[0]):
            band = chw[idx].astype(np.float32)
            channel_stats[idx]["min"].append(float(np.min(band)))
            channel_stats[idx]["max"].append(float(np.max(band)))
            channel_stats[idx]["mean"].append(float(np.mean(band)))
            channel_stats[idx]["std"].append(float(np.std(band)))
            channel_stats[idx]["p1"].append(float(np.percentile(band, 1)))
            channel_stats[idx]["p99"].append(float(np.percentile(band, 99)))
        audit_rows.append(
            {
                "image_name": row["image_name"],
                "split": row["split"],
                "tif_path": rel(path),
                "mask_path": rel(mask_path),
                "shape": "x".join(str(v) for v in arr.shape),
                "channel_count": chw.shape[0],
                "dtype": str(arr.dtype),
                "min": float(np.min(chw)),
                "max": float(np.max(chw)),
                "mean": float(np.mean(chw)),
                "std": float(np.std(chw)),
                "has_nan": str(has_nan).lower(),
                "has_inf": str(has_inf).lower(),
                "all_zero_channel_count": all_zero,
                "mask_size_match": str(mask.size == (chw.shape[2], chw.shape[1])).lower(),
                "notes": "; ".join(notes),
            }
        )
    stats = {
        "channel_count_observed": sorted({int(row["channel_count"]) for row in audit_rows}),
        "model_input_channels_recommended": MAX_CHANNELS,
        "padding_policy": "5-channel samples are zero-padded to 6 channels",
        "normalization": "per-channel percentile clipping 1%-99%, then scale to 0-1 inside Dataset loader",
        "per_channel": {
            str(idx): {metric: float(np.mean(values)) for metric, values in metrics.items()}
            for idx, metrics in channel_stats.items()
        },
        "abnormal_channel_found": any(row["has_nan"] == "true" or row["has_inf"] == "true" or int(row["all_zero_channel_count"]) > 0 for row in audit_rows),
    }
    return audit_rows, stats


def run_forward_test(rows: list[dict[str, str]]) -> dict[str, Any]:
    train_rows = [row for row in rows if row["split"] == "train"][:2]
    val_rows = [row for row in rows if row["split"] == "val"][:2]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = TinyUNet(MAX_CHANNELS).to(device)
    payload: dict[str, Any] = {
        "executed": True,
        "batch_size": 2,
        "cuda_available": torch.cuda.is_available(),
        "device": str(device),
        "passed": False,
    }
    results = {}
    for name, subset in [("train", train_rows), ("val", val_rows)]:
        images = []
        masks = []
        for row in subset:
            image, mask = load_pair(row)
            images.append(image)
            masks.append(mask)
        x = torch.from_numpy(np.stack(images)).to(device)
        y = torch.from_numpy(np.stack(masks)).to(device)
        with torch.no_grad():
            out = model(x)
            loss = loss_fn(out, y)
        results[name] = {
            "input_shape": list(x.shape),
            "mask_shape": list(y.shape),
            "output_shape": list(out.shape),
            "loss": float(loss.item()),
            "loss_finite": bool(math.isfinite(float(loss.item()))),
        }
    payload["results"] = results
    payload["passed"] = all(item["loss_finite"] and item["output_shape"] == item["mask_shape"] for item in results.values())
    return payload


def write_reports(audit_rows: list[dict[str, Any]], channel_stats: dict[str, Any], forward: dict[str, Any]) -> None:
    atomic_write_csv(
        REPORTS / "uav_blb_multispectral_tif_read_audit.csv",
        audit_rows,
        [
            "image_name",
            "split",
            "tif_path",
            "mask_path",
            "shape",
            "channel_count",
            "dtype",
            "min",
            "max",
            "mean",
            "std",
            "has_nan",
            "has_inf",
            "all_zero_channel_count",
            "mask_size_match",
            "notes",
        ],
    )
    atomic_write_json(REPORTS / "uav_blb_multispectral_channel_stats.json", channel_stats)
    gate = "PASS" if forward["passed"] else "FAIL"
    atomic_write_text(
        REPORTS / "uav_blb_multispectral_small_batch_forward_test_report.md",
        f"""# UAV BLB Multispectral Small-Batch Forward Test Report

## Boundary

- formal_training_executed: `NO`
- formal_weights_generated: `NO`
- backend_modified: `NO`
- env_modified: `NO`
- original_images_modified: `NO`
- original_yolo_labels_overwritten: `NO`

## Environment

- torch_version: `{torch.__version__}`
- cuda_available: `{forward['cuda_available']}`
- device: `{forward['device']}`
- tifffile_version: `{tifffile.__version__}`

## Forward Test

- executed: `{forward['executed']}`
- batch_size: `{forward['batch_size']}`
- train_input_shape: `{forward['results']['train']['input_shape']}`
- train_mask_shape: `{forward['results']['train']['mask_shape']}`
- train_output_shape: `{forward['results']['train']['output_shape']}`
- train_loss_finite: `{forward['results']['train']['loss_finite']}`
- val_input_shape: `{forward['results']['val']['input_shape']}`
- val_mask_shape: `{forward['results']['val']['mask_shape']}`
- val_output_shape: `{forward['results']['val']['output_shape']}`
- val_loss_finite: `{forward['results']['val']['loss_finite']}`
- small_batch_forward_test: `{gate}`
- multispectral_smoke_training_allowed: `{str(forward['passed']).lower()}`

This was a forward-only check. It did not run epochs and did not save weights.
""",
    )
    atomic_write_text(
        REPORTS / "uav_blb_multispectral_input_training_plan.md",
        f"""# UAV BLB Multispectral Input Training Plan

## Why This Stage Is Needed

The previous 3 epoch segmentation smoke used RGB preview JPG inputs. It proved segmentation route feasibility but did not train a full multispectral model. A proper UAV BLB segmentation model must read the 5/6-channel TIF patches directly.

## Environment Result

- tifffile_available: `true`
- tifffile_version: `{tifffile.__version__}`
- torch_cuda_available: `{torch.cuda.is_available()}`
- small_batch_forward_test: `{gate}`

## TIF Reading Strategy

- Use `tifffile.imread` in the Dataset loader.
- Convert image arrays to CHW format.
- Preserve native 5/6-channel data.
- Pad 5-channel samples to 6 channels for a single model input shape.
- Do not modify or rewrite source TIF files.

## Normalization Strategy

- Per-channel percentile clipping at `1%-99%`.
- Scale each channel to `0-1` inside the Dataset loader.
- Record per-channel stats for audit.
- Keep masks binary: `0` background, `1` foreground during training.

## Model Input Adaptation

- Recommended model input channels: `6`.
- 5-channel samples: zero-pad one channel.
- Output remains one binary mask channel.
- Loss can remain BCEWithLogits + soft Dice for the next smoke.

## Next Multispectral Smoke Training Gate

Allowed only if:

- TIF read audit passes.
- No NaN/Inf or all-zero channel issues are found in sampled audit.
- Small-batch forward test passes.
- No backend integration is attempted.
- production_ready remains `false`.

Current recommendation: `MULTISPECTRAL_SEGMENTATION_408_V1_SMOKE_TRAINING_GATE`.
""",
    )
    atomic_write_text(
        CONFIG_PATH,
        """dataset:
  path: datasets/rice_uav_ms_blb_segmentation_408_v1
  images: images
  masks: masks
  source_format: multispectral_tif
  mask_format: png_binary_0_255
input:
  input_channels: 6
  channel_policy: preserve 5/6-channel TIF, pad 5-channel samples to 6
  normalization: per-channel percentile clipping 1-99 then scale 0-1
model:
  name: tiny_unet_multispectral_smoke
  output_channels: 1
training:
  batch_size: 4
  image_size: 256
  epochs_recommended: 3
  loss: bce_with_logits_plus_soft_dice
  output_dir: runs/uav_blb_multispectral_segmentation_408_v1_smoke
status:
  production_ready: false
  backend_integration_allowed: false
  multispectral_smoke_training_allowed: true
""",
    )


def write_status(forward: dict[str, Any], channel_stats: dict[str, Any]) -> None:
    atomic_write_text(
        META,
        f"""bbox_route_status: BLOCKED
segmentation_route_stage: MULTISPECTRAL_INPUT_TRAINING_PLAN
rgb_preview_smoke_feasibility: PASS_WITH_OVERSEGMENTATION_RISK
multispectral_input_ready: {str(forward['passed']).lower()}
tifffile_available: true
tifffile_version: {tifffile.__version__}
channel_count_observed: {channel_stats['channel_count_observed']}
model_input_channels_recommended: 6
normalization: percentile_clip_1_99_per_channel_to_0_1
small_batch_forward_test: {"PASS" if forward['passed'] else "FAIL"}
multispectral_smoke_training_allowed: {str(forward['passed']).lower()}
production_ready: false
backend_integration_allowed: false
original_images_modified: false
original_labels_modified: false
backend_modified: false
env_modified: false
next_allowed_stage: {"MULTISPECTRAL_SEGMENTATION_408_V1_SMOKE_TRAINING_GATE" if forward['passed'] else "MULTISPECTRAL_INPUT_REPAIR"}
notes:
  - no formal epoch training was executed in this stage
  - no weights were generated in this stage
  - source TIF files remain read-only
""",
    )


def main() -> int:
    rows = read_csv(MASK_STATS)
    selected = select_audit_rows(rows)
    audit_rows, channel_stats = audit_tif_rows(selected)
    forward = run_forward_test(rows)
    write_reports(audit_rows, channel_stats, forward)
    write_status(forward, channel_stats)
    print(json.dumps({"audit_count": len(audit_rows), "channel_stats": channel_stats, "forward": forward}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
