"""Tiny U-Net smoke training for UAV BLB segmentation 408 v1.

This script is for a short experiment only. It does not modify source data,
backend files, .env, or production weights. Outputs are written under
runs/uav_blb_segmentation_408_v1_short_exp and reports/.
"""

from __future__ import annotations

import csv
import json
import math
import os
import random
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from torch import nn
from torch.utils.data import DataLoader, Dataset


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "datasets" / "rice_uav_ms_blb_segmentation_408_v1"
PREVIEW_DATASET = ROOT / "datasets" / "rice_uav_ms_blb_preview_1000"
STATS_CSV = ROOT / "reports" / "uav_blb_segmentation_408_v1_mask_stats.csv"
RUN_DIR = ROOT / "runs" / "uav_blb_segmentation_408_v1_short_exp"
REPORTS = ROOT / "reports"
META = ROOT / "metadata" / "uav_blb_segmentation_route_status.yaml"

SEED = 20260703
EPOCHS = 3
BATCH_SIZE = 8
IMAGE_SIZE = 256
LR = 3e-4
WEIGHT_DECAY = 1e-4


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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def preview_image_path(row: dict[str, str]) -> Path:
    return PREVIEW_DATASET / "images" / row["split"] / row["image_name"]


def normalize_image(path: Path) -> np.ndarray:
    # Smoke-only input policy: use the existing 3-channel preview JPG because the
    # torchgpu environment lacks a TIFF reader for 5/6-channel multispectral TIF.
    image = Image.open(path).convert("RGB").resize((IMAGE_SIZE, IMAGE_SIZE), Image.BILINEAR)
    arr = np.array(image, dtype=np.float32) / 255.0
    return np.moveaxis(arr, -1, 0)


class BLBSegDataset(Dataset):
    def __init__(self, rows: list[dict[str, str]], augment: bool) -> None:
        self.rows = rows
        self.augment = augment

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        row = self.rows[index]
        image = normalize_image(preview_image_path(row))
        mask = np.array(Image.open(ROOT / row["mask_path"]).convert("L").resize((IMAGE_SIZE, IMAGE_SIZE), Image.NEAREST), dtype=np.float32)
        mask = (mask > 0).astype(np.float32)[None, ...]
        if self.augment and random.random() < 0.5:
            image = image[:, :, ::-1].copy()
            mask = mask[:, :, ::-1].copy()
        if self.augment and random.random() < 0.5:
            image = image[:, ::-1, :].copy()
            mask = mask[:, ::-1, :].copy()
        return torch.from_numpy(image), torch.from_numpy(mask)


class ConvBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class TinyUNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.down1 = ConvBlock(3, 16)
        self.down2 = ConvBlock(16, 32)
        self.down3 = ConvBlock(32, 64)
        self.pool = nn.MaxPool2d(2)
        self.up2 = nn.ConvTranspose2d(64, 32, 2, stride=2)
        self.dec2 = ConvBlock(64, 32)
        self.up1 = nn.ConvTranspose2d(32, 16, 2, stride=2)
        self.dec1 = ConvBlock(32, 16)
        self.out = nn.Conv2d(16, 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.down1(x)
        x2 = self.down2(self.pool(x1))
        x3 = self.down3(self.pool(x2))
        y = self.up2(x3)
        y = self.dec2(torch.cat([y, x2], dim=1))
        y = self.up1(y)
        y = self.dec1(torch.cat([y, x1], dim=1))
        return self.out(y)


def dice_loss(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    pred = torch.sigmoid(logits)
    smooth = 1.0
    intersection = (pred * target).sum(dim=(1, 2, 3))
    union = pred.sum(dim=(1, 2, 3)) + target.sum(dim=(1, 2, 3))
    return 1 - ((2 * intersection + smooth) / (union + smooth)).mean()


def loss_fn(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    return nn.functional.binary_cross_entropy_with_logits(logits, target) + dice_loss(logits, target)


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> dict[str, float]:
    model.eval()
    losses = []
    tp = fp = fn = tn = 0.0
    for image, mask in loader:
        image = image.to(device)
        mask = mask.to(device)
        logits = model(image)
        losses.append(float(loss_fn(logits, mask).item()))
        pred = torch.sigmoid(logits) > 0.5
        target = mask > 0.5
        tp += float((pred & target).sum().item())
        fp += float((pred & ~target).sum().item())
        fn += float((~pred & target).sum().item())
        tn += float((~pred & ~target).sum().item())
    dice = (2 * tp) / (2 * tp + fp + fn + 1e-7)
    iou = tp / (tp + fp + fn + 1e-7)
    precision = tp / (tp + fp + 1e-7)
    recall = tp / (tp + fn + 1e-7)
    pixel_accuracy = (tp + tn) / (tp + tn + fp + fn + 1e-7)
    return {
        "loss": sum(losses) / max(1, len(losses)),
        "dice": dice,
        "iou": iou,
        "precision": precision,
        "recall": recall,
        "pixel_accuracy": pixel_accuracy,
    }


def make_prediction_previews(model: nn.Module, rows: list[dict[str, str]], device: torch.device) -> list[str]:
    preview_dir = RUN_DIR / "sample_predictions"
    preview_dir.mkdir(parents=True, exist_ok=True)
    model.eval()
    outputs: list[str] = []
    font = ImageFont.load_default()
    for row in rows[:12]:
        image_np = normalize_image(preview_image_path(row))
        x = torch.from_numpy(image_np[None]).to(device)
        with torch.no_grad():
            prob = torch.sigmoid(model(x))[0, 0].cpu().numpy()
        rgb = np.moveaxis((image_np * 255).astype(np.uint8), 0, -1)
        target = np.array(Image.open(ROOT / row["mask_path"]).convert("L")) > 0
        pred = prob > 0.5
        panels = []
        for title, mask in [("image", None), ("target", target), ("prediction", pred)]:
            panel = rgb.copy()
            if mask is not None:
                panel[mask] = (0.45 * panel[mask] + 0.55 * np.array([255, 0, 0])).astype(np.uint8)
            img = Image.fromarray(panel)
            draw = ImageDraw.Draw(img)
            draw.rectangle((0, 0, img.width, 18), fill=(255, 255, 255))
            draw.text((4, 2), title, fill=(0, 0, 0), font=font)
            panels.append(img)
        canvas = Image.new("RGB", (panels[0].width * 3, panels[0].height + 24), "white")
        for idx, panel in enumerate(panels):
            canvas.paste(panel, (idx * panel.width, 24))
        ImageDraw.Draw(canvas).text((4, 4), row["image_name"], fill=(0, 0, 0), font=font)
        out_path = preview_dir / f"{Path(row['image_name']).stem}_prediction.jpg"
        canvas.save(out_path, quality=92)
        outputs.append(rel(out_path))
    return outputs


def main() -> int:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_csv(STATS_CSV)
    train_rows = [row for row in rows if row["split"] == "train"]
    val_rows = [row for row in rows if row["split"] == "val"]
    test_rows = [row for row in rows if row["split"] == "test"]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_loader = DataLoader(BLBSegDataset(train_rows, augment=True), batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    val_loader = DataLoader(BLBSegDataset(val_rows, augment=False), batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    test_loader = DataLoader(BLBSegDataset(test_rows, augment=False), batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    model = TinyUNet().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    history = []
    best_val_dice = -math.inf
    best_path = RUN_DIR / "best_tiny_unet_smoke.pth"
    last_path = RUN_DIR / "last_tiny_unet_smoke.pth"
    for epoch in range(1, EPOCHS + 1):
        model.train()
        train_losses = []
        for image, mask in train_loader:
            image = image.to(device)
            mask = mask.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(image)
            loss = loss_fn(logits, mask)
            loss.backward()
            optimizer.step()
            train_losses.append(float(loss.item()))
        val_metrics = evaluate(model, val_loader, device)
        train_loss = sum(train_losses) / len(train_losses)
        row = {"epoch": epoch, "train_loss": train_loss, **{f"val_{k}": v for k, v in val_metrics.items()}}
        history.append(row)
        if val_metrics["dice"] > best_val_dice:
            best_val_dice = val_metrics["dice"]
            torch.save({"model": model.state_dict(), "epoch": epoch, "val_metrics": val_metrics}, best_path)
        torch.save({"model": model.state_dict(), "epoch": epoch, "val_metrics": val_metrics}, last_path)
        print(json.dumps(row, ensure_ascii=False))
    best_ckpt = torch.load(best_path, map_location=device, weights_only=False)
    model.load_state_dict(best_ckpt["model"])
    test_metrics = evaluate(model, test_loader, device)
    preview_paths = make_prediction_previews(model, test_rows, device)
    metrics = {
        "generated_at": now_iso(),
        "purpose": "segmentation_short_experiment_smoke",
        "formal_model": False,
        "production_ready": False,
        "backend_integration_allowed": False,
        "epochs": EPOCHS,
        "batch_size": BATCH_SIZE,
        "device": str(device),
        "input_policy": "preview_jpg_rgb_smoke_input",
        "full_multispectral_tif_used": False,
        "train_count": len(train_rows),
        "val_count": len(val_rows),
        "test_count": len(test_rows),
        "history": history,
        "best_checkpoint": rel(best_path),
        "last_checkpoint": rel(last_path),
        "best_val_dice": best_val_dice,
        "test_metrics": test_metrics,
        "sample_prediction_paths": preview_paths,
        "known_risks": {"mask_too_small_samples": 26},
    }
    atomic_write_json(REPORTS / "uav_blb_segmentation_408_v1_short_exp_metrics.json", metrics)
    report = f"""# UAV BLB Segmentation 408 v1 Short Experiment Training Report

## Scope

- purpose: `segmentation_short_experiment_smoke`
- formal_model: `NO`
- production_ready: `NO`
- backend_integration_allowed: `NO`
- epochs: `{EPOCHS}`
- batch_size: `{BATCH_SIZE}`
- device: `{device}`

## Outputs

- best_checkpoint: `{rel(best_path)}`
- last_checkpoint: `{rel(last_path)}`
- metrics_json: `reports/uav_blb_segmentation_408_v1_short_exp_metrics.json`
- sample_predictions_dir: `runs/uav_blb_segmentation_408_v1_short_exp/sample_predictions`

## Metrics

- best_val_dice: `{best_val_dice}`
- test_loss: `{test_metrics['loss']}`
- test_dice: `{test_metrics['dice']}`
- test_iou: `{test_metrics['iou']}`
- test_pixel_accuracy: `{test_metrics['pixel_accuracy']}`
- test_precision: `{test_metrics['precision']}`
- test_recall: `{test_metrics['recall']}`

## Risk

- mask_too_small_samples: `26`
- This is not a production model and must not be connected to backend inference.
"""
    atomic_write_text(REPORTS / "uav_blb_segmentation_408_v1_short_exp_training_report.md", report)
    pred_md = "# UAV BLB Segmentation 408 v1 Short Experiment Sample Predictions\n\n"
    for path in preview_paths:
        pred_md += f"- `{path}`\n"
    atomic_write_text(REPORTS / "uav_blb_segmentation_408_v1_short_exp_sample_predictions.md", pred_md)
    status = f"""segmentation_route_stage: SHORT_EXPERIMENT_COMPLETE
bbox_route_status: BLOCKED
visual_qa_gate: PASS
segmentation_training_allowed: true
short_experiment_allowed: true
short_experiment_executed: true
production_ready: false
backend_integration_allowed: false
original_images_modified: false
original_labels_modified: false
yolo_bbox_labels_used: false
weights_modified: true
weights_are_smoke_only: true
best_checkpoint: {rel(best_path)}
last_checkpoint: {rel(last_path)}
backend_modified: false
env_modified: false
next_allowed_stage: SHORT_EXPERIMENT_REVIEW_OR_SEGMENTATION_MODEL_SELECTION
notes:
  - smoke weights are not production weights
  - do not integrate backend without a separate approval gate
"""
    atomic_write_text(META, status)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
