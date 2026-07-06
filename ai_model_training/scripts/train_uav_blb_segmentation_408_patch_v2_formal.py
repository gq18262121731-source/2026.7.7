"""Formal-candidate training matrix for UAV BLB segmentation_408_patch_v2.

This script stays on the segmentation route only. It does not use YOLO bbox
labels, does not modify source data, and does not integrate with backend
inference. Outputs are formal-candidate experiment artifacts, not production
weights.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from torch import nn
from torch.utils.data import DataLoader, Dataset

try:
    from tqdm import tqdm
except Exception:  # pragma: no cover - fallback for minimal envs
    tqdm = None


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "uav_blb_segmentation_408_patch_v2_formal_training_matrix.yaml"
DATASET_DIR = ROOT / "datasets" / "rice_uav_ms_blb_segmentation_408_patch_v2"
MANIFEST = DATASET_DIR / "meta" / "split_manifest.csv"
RUN_ROOT = ROOT / "runs" / "uav_blb_segmentation_408_patch_v2_formal"
REPORTS = ROOT / "reports"
META = ROOT / "metadata" / "uav_blb_segmentation_route_status.yaml"

SEED = 20260703
EPOCHS = 100
PATIENCE = 25
BATCH_SIZE = 4
LR = 3e-4
WEIGHT_DECAY = 1e-4
INPUT_CHANNELS = 6
THRESHOLDS = [round(0.30 + 0.05 * i, 2) for i in range(10)]
MIN_AREAS = [16, 32, 64, 128]
SAMPLE_PREDICTION_COUNT = 30
GATE = {
    "test_precision_min": 0.72,
    "test_recall_min": 0.80,
    "test_dice_min": 0.78,
    "visual_acceptable_min": 0.80,
    "major_failure_max": 0,
}


INPUT_CONFIGS = {
    "D1_5BAND_VALID": "feature_d1_path",
    "D2_5BAND_NDVI": "feature_d2_path",
    "D3_5BAND_NDRE": "feature_d3_path",
}

MODEL_CONFIGS = {
    "UNET_BASELINE": {"kind": "unet", "base": 24},
    "UNETPP_EFFICIENTNET_B0_CANDIDATE": {"kind": "unetpp", "base": 24},
    "UNETPP_EFFICIENTNET_B3_CANDIDATE": {"kind": "unetpp", "base": 32},
}

LOSS_CONFIGS = {
    "BCE_DICE": {"kind": "dice"},
    "BCE_TVERSKY_A06_B04": {"kind": "tversky", "alpha": 0.6, "beta": 0.4},
    "BCE_TVERSKY_A07_B03": {"kind": "tversky", "alpha": 0.7, "beta": 0.3},
}


class NullProgress:
    def __init__(self, iterable, **_kwargs):
        self.iterable = iterable

    def __iter__(self):
        return iter(self.iterable)

    def set_postfix(self, *_args, **_kwargs) -> None:
        return None


def progress_wrap(iterable, enabled: bool, **kwargs):
    if enabled and tqdm is not None:
        return tqdm(iterable, **kwargs)
    return NullProgress(iterable, **kwargs)


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


def normalize_feature(arr: np.ndarray) -> np.ndarray:
    arr = arr.astype(np.float32)
    out = np.zeros_like(arr, dtype=np.float32)
    for idx in range(arr.shape[-1]):
        band = arr[..., idx]
        low = np.percentile(band, 1)
        high = np.percentile(band, 99)
        if high <= low:
            high = low + 1.0
        out[..., idx] = np.clip((band - low) / (high - low), 0, 1)
    return out


class PatchV2Dataset(Dataset):
    def __init__(self, rows: list[dict[str, str]], feature_column: str, augment: bool) -> None:
        self.rows = rows
        self.feature_column = feature_column
        self.augment = augment

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, str]:
        row = self.rows[index]
        feature = normalize_feature(np.load(ROOT / row[self.feature_column]))
        mask = np.array(Image.open(ROOT / row["mask_png_path"]).convert("L"), dtype=np.float32)
        mask = (mask > 0).astype(np.float32)
        if self.augment and random.random() < 0.5:
            feature = feature[:, ::-1, :].copy()
            mask = mask[:, ::-1].copy()
        if self.augment and random.random() < 0.5:
            feature = feature[::-1, :, :].copy()
            mask = mask[::-1, :].copy()
        x = torch.from_numpy(np.moveaxis(feature, -1, 0).astype(np.float32))
        y = torch.from_numpy(mask[None].astype(np.float32))
        return x, y, row["patch_id"]


class ConvBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class UNetBaseline(nn.Module):
    def __init__(self, in_channels: int, base: int) -> None:
        super().__init__()
        self.down1 = ConvBlock(in_channels, base)
        self.down2 = ConvBlock(base, base * 2)
        self.down3 = ConvBlock(base * 2, base * 4)
        self.pool = nn.MaxPool2d(2)
        self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
        self.dec2 = ConvBlock(base * 4, base * 2)
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.dec1 = ConvBlock(base * 2, base)
        self.out = nn.Conv2d(base, 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.down1(x)
        x2 = self.down2(self.pool(x1))
        x3 = self.down3(self.pool(x2))
        y = self.up2(x3)
        y = self.dec2(torch.cat([y, x2], dim=1))
        y = self.up1(y)
        y = self.dec1(torch.cat([y, x1], dim=1))
        return self.out(y)


class MiniUNetPlusPlus(nn.Module):
    """Small nested U-Net++ style fallback when SMP/EfficientNet is unavailable."""

    def __init__(self, in_channels: int, base: int) -> None:
        super().__init__()
        self.pool = nn.MaxPool2d(2)
        self.x00 = ConvBlock(in_channels, base)
        self.x10 = ConvBlock(base, base * 2)
        self.x20 = ConvBlock(base * 2, base * 4)
        self.up10 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.x01 = ConvBlock(base * 2, base)
        self.up20 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
        self.x11 = ConvBlock(base * 4, base * 2)
        self.up11 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.x02 = ConvBlock(base * 3, base)
        self.out = nn.Conv2d(base, 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x00 = self.x00(x)
        x10 = self.x10(self.pool(x00))
        x20 = self.x20(self.pool(x10))
        x01 = self.x01(torch.cat([x00, self.up10(x10)], dim=1))
        x11 = self.x11(torch.cat([x10, self.up20(x20)], dim=1))
        x02 = self.x02(torch.cat([x00, x01, self.up11(x11)], dim=1))
        return self.out(x02)


def build_model(model_code: str) -> nn.Module:
    cfg = MODEL_CONFIGS[model_code]
    if cfg["kind"] == "unet":
        return UNetBaseline(INPUT_CHANNELS, cfg["base"])
    return MiniUNetPlusPlus(INPUT_CHANNELS, cfg["base"])


def soft_dice_loss(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    prob = torch.sigmoid(logits)
    intersection = (prob * target).sum(dim=(1, 2, 3))
    union = prob.sum(dim=(1, 2, 3)) + target.sum(dim=(1, 2, 3))
    return 1 - ((2 * intersection + 1.0) / (union + 1.0)).mean()


def tversky_loss(logits: torch.Tensor, target: torch.Tensor, alpha: float, beta: float) -> torch.Tensor:
    prob = torch.sigmoid(logits)
    tp = (prob * target).sum(dim=(1, 2, 3))
    fp = (prob * (1 - target)).sum(dim=(1, 2, 3))
    fn = ((1 - prob) * target).sum(dim=(1, 2, 3))
    return 1 - ((tp + 1.0) / (tp + alpha * fp + beta * fn + 1.0)).mean()


def make_loss(loss_code: str):
    cfg = LOSS_CONFIGS[loss_code]

    def loss_fn(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        bce = nn.functional.binary_cross_entropy_with_logits(logits, target)
        if cfg["kind"] == "dice":
            return bce + soft_dice_loss(logits, target)
        return bce + tversky_loss(logits, target, cfg["alpha"], cfg["beta"])

    return loss_fn


def connected_components(binary: np.ndarray) -> Iterable[np.ndarray]:
    h, w = binary.shape
    seen = np.zeros_like(binary, dtype=bool)
    for y0 in range(h):
        for x0 in range(w):
            if not binary[y0, x0] or seen[y0, x0]:
                continue
            stack = [(y0, x0)]
            seen[y0, x0] = True
            coords = []
            while stack:
                y, x = stack.pop()
                coords.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and binary[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            yy, xx = zip(*coords)
            comp = np.zeros_like(binary, dtype=bool)
            comp[np.array(yy), np.array(xx)] = True
            yield comp


def remove_small_components(binary: np.ndarray, min_area: int) -> np.ndarray:
    try:
        from scipy import ndimage

        labeled, count = ndimage.label(binary)
        if count == 0:
            return np.zeros_like(binary, dtype=bool)
        sizes = np.bincount(labeled.ravel())
        keep = sizes >= min_area
        keep[0] = False
        return keep[labeled]
    except Exception:
        pass
    out = np.zeros_like(binary, dtype=bool)
    for comp in connected_components(binary):
        if int(comp.sum()) >= min_area:
            out |= comp
    return out


def morph(binary: np.ndarray, mode: str) -> np.ndarray:
    try:
        from scipy import ndimage

        structure = np.ones((3, 3), dtype=bool)
        if mode == "opening":
            return ndimage.binary_opening(binary, structure=structure)
        return ndimage.binary_closing(binary, structure=structure)
    except Exception:
        return binary


def apply_postprocess(prob: np.ndarray, threshold: float, mode: str, min_area: int) -> np.ndarray:
    if mode == "RAW_MASK":
        return prob >= 0.5
    binary = prob >= threshold
    if mode in {"THRESHOLD_REMOVE_SMALL_COMPONENTS", "THRESHOLD_REMOVE_SMALL_COMPONENTS_OPEN_CLOSE"}:
        binary = remove_small_components(binary, min_area)
    if mode == "THRESHOLD_REMOVE_SMALL_COMPONENTS_OPEN_CLOSE":
        binary = morph(morph(binary, "opening"), "closing")
    return binary


def metric_from_counts(tp: float, fp: float, fn: float, tn: float) -> dict[str, float]:
    total = tp + fp + fn + tn + 1e-7
    return {
        "dice": (2 * tp) / (2 * tp + fp + fn + 1e-7),
        "iou": tp / (tp + fp + fn + 1e-7),
        "precision": tp / (tp + fp + 1e-7),
        "recall": tp / (tp + fn + 1e-7),
        "pixel_accuracy": (tp + tn) / total,
        "pred_foreground_ratio": (tp + fp) / total,
        "fp_area_ratio": fp / total,
    }


@torch.no_grad()
def collect_probabilities(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[list[np.ndarray], list[np.ndarray], list[str], float]:
    model.eval()
    probs: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    ids: list[str] = []
    losses = []
    loss_fn = make_loss("BCE_DICE")
    for image, mask, patch_ids in loader:
        image = image.to(device)
        mask = mask.to(device)
        logits = model(image)
        losses.append(float(loss_fn(logits, mask).item()))
        batch_prob = torch.sigmoid(logits).cpu().numpy()[:, 0]
        batch_target = mask.cpu().numpy()[:, 0] > 0.5
        probs.extend([p for p in batch_prob])
        targets.extend([t for t in batch_target])
        ids.extend(list(patch_ids))
    return probs, targets, ids, sum(losses) / max(1, len(losses))


@torch.no_grad()
def evaluate_light(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    loss_fn,
    progress: bool,
    epoch: int,
    total_epochs: int,
) -> dict[str, float]:
    model.eval()
    losses = []
    tp = fp = fn = tn = 0.0
    iterator = progress_wrap(loader, progress, desc=f"val {epoch}/{total_epochs}", leave=False, dynamic_ncols=True)
    for image, mask, _patch_ids in iterator:
        image = image.to(device)
        mask = mask.to(device)
        logits = model(image)
        loss = loss_fn(logits, mask)
        losses.append(float(loss.item()))
        pred = torch.sigmoid(logits) >= 0.5
        target = mask > 0.5
        tp += float((pred & target).sum().item())
        fp += float((pred & ~target).sum().item())
        fn += float((~pred & target).sum().item())
        tn += float((~pred & ~target).sum().item())
        if hasattr(iterator, "set_postfix"):
            iterator.set_postfix(loss=f"{float(loss.item()):.4f}")
    metrics = metric_from_counts(tp, fp, fn, tn)
    metrics["loss"] = sum(losses) / max(1, len(losses))
    metrics["threshold"] = 0.5
    return metrics


def evaluate_postprocess(
    probs: list[np.ndarray],
    targets: list[np.ndarray],
    split: str,
    loss_value: float,
    quick: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    best = {"dice": -1.0}
    thresholds = [0.4, 0.5, 0.6] if quick else THRESHOLDS
    min_areas = [32] if quick else MIN_AREAS
    modes = [
        ("RAW_MASK", 0.5, 0),
        *[("THRESHOLD_ONLY", thr, 0) for thr in thresholds],
        *[("THRESHOLD_REMOVE_SMALL_COMPONENTS", thr, area) for thr in thresholds for area in min_areas],
        *[("THRESHOLD_REMOVE_SMALL_COMPONENTS_OPEN_CLOSE", thr, area) for thr in thresholds for area in min_areas],
    ]
    for mode, threshold, min_area in modes:
        tp = fp = fn = tn = 0.0
        for prob, target in zip(probs, targets):
            pred = apply_postprocess(prob, threshold, mode, min_area)
            tp += float((pred & target).sum())
            fp += float((pred & ~target).sum())
            fn += float((~pred & target).sum())
            tn += float((~pred & ~target).sum())
        metrics = metric_from_counts(tp, fp, fn, tn)
        row = {
            "split": split,
            "postprocess_mode": mode,
            "threshold": threshold,
            "min_area": min_area,
            "loss": loss_value,
            **metrics,
        }
        rows.append(row)
        if split == "val" and metrics["dice"] > best["dice"]:
            best = row
    return rows, best


def train_one(
    input_code: str,
    model_code: str,
    loss_code: str,
    *,
    quick: bool = False,
    epochs: int = EPOCHS,
    patience: int = PATIENCE,
    progress: bool = False,
    eval_full_final_only: bool = True,
    eval_full_every: int = 0,
) -> dict[str, Any]:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    run_name = f"{input_code}__{model_code}__{loss_code}"
    run_dir = RUN_ROOT / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = read_csv(MANIFEST)
    train_rows = [row for row in rows if row["split"] == "train"]
    val_rows = [row for row in rows if row["split"] == "val"]
    test_rows = [row for row in rows if row["split"] == "test"]
    if quick:
        train_rows = train_rows[:24]
        val_rows = val_rows[:12]
        test_rows = test_rows[:12]
    feature_column = INPUT_CONFIGS[input_code]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    epochs = 1 if quick else epochs
    train_loader = DataLoader(PatchV2Dataset(train_rows, feature_column, True), batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    val_loader = DataLoader(PatchV2Dataset(val_rows, feature_column, False), batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    test_loader = DataLoader(PatchV2Dataset(test_rows, feature_column, False), batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    model = build_model(model_code).to(device)
    loss_fn = make_loss(loss_code)
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    history: list[dict[str, Any]] = []
    best_val_dice = -1.0
    best_epoch = 0
    stale = 0
    best_path = run_dir / "best_formal_candidate.pth"
    last_path = run_dir / "last_formal_candidate.pth"
    interrupted = False
    try:
        for epoch in range(1, epochs + 1):
            epoch_start = time.perf_counter()
            model.train()
            train_losses = []
            train_start = time.perf_counter()
            train_iter = progress_wrap(train_loader, progress, desc=f"train {epoch}/{epochs}", leave=False, dynamic_ncols=True)
            for image, mask, _ids in train_iter:
                image = image.to(device)
                mask = mask.to(device)
                opt.zero_grad(set_to_none=True)
                logits = model(image)
                loss = loss_fn(logits, mask)
                loss.backward()
                opt.step()
                train_losses.append(float(loss.item()))
                if hasattr(train_iter, "set_postfix"):
                    train_iter.set_postfix(loss=f"{float(loss.item()):.4f}")
            train_seconds = time.perf_counter() - train_start

            val_start = time.perf_counter()
            val_metrics = evaluate_light(model, val_loader, device, loss_fn, progress, epoch, epochs)
            val_seconds = time.perf_counter() - val_start
            total_seconds = time.perf_counter() - epoch_start
            train_loss = sum(train_losses) / max(1, len(train_losses))
            row = {
                "epoch": epoch,
                "train_loss": train_loss,
                "val_loss": val_metrics["loss"],
                "val_dice": val_metrics["dice"],
                "val_iou": val_metrics["iou"],
                "val_precision": val_metrics["precision"],
                "val_recall": val_metrics["recall"],
                "val_threshold": 0.5,
                "train_seconds": train_seconds,
                "val_seconds": val_seconds,
                "epoch_seconds": total_seconds,
            }
            if eval_full_every and epoch % eval_full_every == 0:
                full_start = time.perf_counter()
                val_probs, val_targets, _val_ids, full_val_loss = collect_probabilities(model, val_loader, device)
                _val_rows_eval, val_best_full = evaluate_postprocess(val_probs, val_targets, "val", full_val_loss, quick=quick)
                row.update(
                    {
                        "full_eval_dice": val_best_full["dice"],
                        "full_eval_threshold": val_best_full["threshold"],
                        "full_eval_postprocess_mode": val_best_full["postprocess_mode"],
                        "full_eval_min_area": val_best_full["min_area"],
                        "full_eval_seconds": time.perf_counter() - full_start,
                    }
                )
            else:
                row.update(
                    {
                        "full_eval_dice": "",
                        "full_eval_threshold": "",
                        "full_eval_postprocess_mode": "",
                        "full_eval_min_area": "",
                        "full_eval_seconds": "",
                    }
                )
            history.append(row)
            if val_metrics["dice"] > best_val_dice:
                best_val_dice = val_metrics["dice"]
                best_epoch = epoch
                stale = 0
                torch.save({"model": model.state_dict(), "epoch": epoch, "val_light": val_metrics}, best_path)
            else:
                stale += 1
            torch.save({"model": model.state_dict(), "epoch": epoch, "val_light": val_metrics}, last_path)
            print(
                f"[{run_name}] epoch {epoch}/{epochs} "
                f"train_loss={train_loss:.4f} val_loss={val_metrics['loss']:.4f} "
                f"val_dice={val_metrics['dice']:.4f} val_iou={val_metrics['iou']:.4f} "
                f"val_precision={val_metrics['precision']:.4f} val_recall={val_metrics['recall']:.4f} "
                f"train={train_seconds:.1f}s val={val_seconds:.1f}s total={total_seconds:.1f}s",
                flush=True,
            )
            if not quick and epoch >= 100 and stale >= patience:
                print(f"[{run_name}] early stopping after epoch {epoch}; stale={stale}, patience={patience}", flush=True)
                break
    except KeyboardInterrupt:
        interrupted = True
        atomic_write_text(
            run_dir / "INTERRUPTED_NOT_PRODUCTION.txt",
            f"Interrupted at {now_iso()}. production_ready=false; backend_integration_allowed=false.\n",
        )
        print(f"[{run_name}] interrupted; production_ready=false backend_integration_allowed=false", flush=True)
        raise
    ckpt = torch.load(best_path, map_location=device, weights_only=False)
    model.load_state_dict(ckpt["model"])
    print(f"[{run_name}] running final threshold sweep and postprocess ablation on best checkpoint", flush=True)
    final_eval_start = time.perf_counter()
    val_probs, val_targets, val_ids, val_loss = collect_probabilities(model, val_loader, device)
    test_probs, test_targets, test_ids, test_loss = collect_probabilities(model, test_loader, device)
    val_eval_rows, val_best = evaluate_postprocess(val_probs, val_targets, "val", val_loss, quick=quick)
    test_eval_rows, _ = evaluate_postprocess(test_probs, test_targets, "test", test_loss, quick=quick)
    selected = [row for row in test_eval_rows if row["postprocess_mode"] == val_best["postprocess_mode"] and row["threshold"] == val_best["threshold"] and row["min_area"] == val_best["min_area"]][0]
    all_eval_rows = val_eval_rows + test_eval_rows
    atomic_write_csv(
        run_dir / "threshold_sweep_postprocess_ablation.csv",
        all_eval_rows,
        ["split", "postprocess_mode", "threshold", "min_area", "loss", "dice", "iou", "precision", "recall", "pixel_accuracy", "pred_foreground_ratio", "fp_area_ratio"],
    )
    atomic_write_csv(
        run_dir / "training_log.csv",
        history,
        [
            "epoch",
            "train_loss",
            "val_loss",
            "val_dice",
            "val_iou",
            "val_precision",
            "val_recall",
            "val_threshold",
            "train_seconds",
            "val_seconds",
            "epoch_seconds",
            "full_eval_dice",
            "full_eval_threshold",
            "full_eval_postprocess_mode",
            "full_eval_min_area",
            "full_eval_seconds",
        ],
    )
    sample_paths = render_samples(run_dir, rows, feature_column, model, device, val_best)
    summary = {
        "run_name": run_name,
        "input_code": input_code,
        "model_code": model_code,
        "loss_code": loss_code,
        "quick_mode": quick,
        "interrupted": interrupted,
        "epochs_completed": len(history),
        "formal_epoch_requirement_met": (not quick and len(history) >= 100),
        "best_epoch": best_epoch,
        "best_val_dice": best_val_dice,
        "final_threshold_sweep_seconds": time.perf_counter() - final_eval_start,
        "selected_postprocess": val_best,
        "test_metrics_at_selected_postprocess": selected,
        "best_checkpoint": rel(best_path),
        "last_checkpoint": rel(last_path),
        "sample_prediction_paths": sample_paths,
        "production_ready": False,
        "backend_integration_allowed": False,
    }
    atomic_write_json(run_dir / "metrics_summary.json", summary)
    return summary


def render_rgb_from_feature(feature: np.ndarray) -> np.ndarray:
    rgb = np.clip(feature[..., :3], 0, 1)
    return (rgb * 255).astype(np.uint8)


def render_samples(run_dir: Path, rows: list[dict[str, str]], feature_column: str, model: nn.Module, device: torch.device, selected: dict[str, Any]) -> list[str]:
    sample_dir = run_dir / "sample_predictions"
    sample_dir.mkdir(parents=True, exist_ok=True)
    test_rows = [row for row in rows if row["split"] == "test"][:SAMPLE_PREDICTION_COUNT]
    font = ImageFont.load_default()
    paths = []
    model.eval()
    for row in test_rows:
        feature = normalize_feature(np.load(ROOT / row[feature_column]))
        mask = np.array(Image.open(ROOT / row["mask_png_path"]).convert("L"), dtype=np.uint8) > 0
        x = torch.from_numpy(np.moveaxis(feature, -1, 0)[None].astype(np.float32)).to(device)
        with torch.no_grad():
            prob = torch.sigmoid(model(x))[0, 0].cpu().numpy()
        pred = apply_postprocess(prob, float(selected["threshold"]), selected["postprocess_mode"], int(selected["min_area"]))
        rgb = render_rgb_from_feature(feature)
        panels = []
        for title, overlay_mask in [("image", None), ("target", mask), ("prediction", pred)]:
            panel = rgb.copy()
            if overlay_mask is not None:
                panel[overlay_mask] = (0.45 * panel[overlay_mask] + 0.55 * np.array([255, 0, 0])).astype(np.uint8)
            img = Image.fromarray(panel)
            draw = ImageDraw.Draw(img)
            draw.rectangle((0, 0, img.width, 18), fill=(255, 255, 255))
            draw.text((4, 2), title, fill=(0, 0, 0), font=font)
            panels.append(img)
        canvas = Image.new("RGB", (panels[0].width * 3, panels[0].height + 26), "white")
        for idx, panel in enumerate(panels):
            canvas.paste(panel, (idx * panel.width, 26))
        ImageDraw.Draw(canvas).text((4, 5), row["patch_id"], fill=(0, 0, 0), font=font)
        out = sample_dir / f"{row['patch_id']}_prediction.jpg"
        canvas.save(out, quality=92)
        paths.append(rel(out))
    return paths


def write_global_reports(summaries: list[dict[str, Any]], quick: bool) -> None:
    metric_rows = []
    threshold_rows = []
    for summary in summaries:
        metrics = summary["test_metrics_at_selected_postprocess"]
        metric_rows.append(
            {
                "run_name": summary["run_name"],
                "input_code": summary["input_code"],
                "model_code": summary["model_code"],
                "loss_code": summary["loss_code"],
                "epochs_completed": summary["epochs_completed"],
                "formal_epoch_requirement_met": str(summary["formal_epoch_requirement_met"]).lower(),
                "best_val_dice": summary["best_val_dice"],
                "selected_postprocess_mode": summary["selected_postprocess"]["postprocess_mode"],
                "selected_threshold": summary["selected_postprocess"]["threshold"],
                "selected_min_area": summary["selected_postprocess"]["min_area"],
                "test_dice": metrics["dice"],
                "test_iou": metrics["iou"],
                "test_precision": metrics["precision"],
                "test_recall": metrics["recall"],
                "test_pred_foreground_ratio": metrics["pred_foreground_ratio"],
                "test_fp_area_ratio": metrics["fp_area_ratio"],
                "backend_integration_candidate": str(
                    metrics["precision"] >= GATE["test_precision_min"]
                    and metrics["recall"] >= GATE["test_recall_min"]
                    and metrics["dice"] >= GATE["test_dice_min"]
                    and summary["formal_epoch_requirement_met"]
                ).lower(),
            }
        )
        sweep_path = RUN_ROOT / summary["run_name"] / "threshold_sweep_postprocess_ablation.csv"
        for row in read_csv(sweep_path):
            row["run_name"] = summary["run_name"]
            row["input_code"] = summary["input_code"]
            row["model_code"] = summary["model_code"]
            row["loss_code"] = summary["loss_code"]
            threshold_rows.append(row)
    atomic_write_csv(
        REPORTS / "uav_blb_segmentation_408_patch_v2_metrics_summary.csv",
        metric_rows,
        ["run_name", "input_code", "model_code", "loss_code", "epochs_completed", "formal_epoch_requirement_met", "best_val_dice", "selected_postprocess_mode", "selected_threshold", "selected_min_area", "test_dice", "test_iou", "test_precision", "test_recall", "test_pred_foreground_ratio", "test_fp_area_ratio", "backend_integration_candidate"],
    )
    atomic_write_csv(
        REPORTS / "uav_blb_segmentation_408_patch_v2_threshold_sweep.csv",
        threshold_rows,
        ["run_name", "input_code", "model_code", "loss_code", "split", "postprocess_mode", "threshold", "min_area", "loss", "dice", "iou", "precision", "recall", "pixel_accuracy", "pred_foreground_ratio", "fp_area_ratio"],
    )
    payload = {
        "generated_at": now_iso(),
        "quick_mode": quick,
        "formal_training_requirement": ">=100 epochs with early stopping patience 20-30",
        "run_count": len(summaries),
        "summaries": summaries,
        "production_ready": False,
        "backend_integration_allowed": False,
    }
    atomic_write_json(REPORTS / "uav_blb_segmentation_408_patch_v2_metrics_summary.json", payload)
    gate_rows = [row for row in metric_rows if row["backend_integration_candidate"] == "true"]
    md = f"""# UAV BLB Segmentation 408 Patch v2 Formal Training Report

## Boundary

- bbox_route_status: `BLOCKED`
- yolo_bbox_route_used: `NO`
- original_images_modified: `NO`
- original_raster_masks_modified: `NO`
- original_yolo_labels_overwritten: `NO`
- backend_modified: `NO`
- env_modified: `NO`
- production_ready: `false`
- backend_integration_allowed: `false`

## Training Scope

- quick_mode: `{quick}`
- formal_epoch_requirement: `>=100 epochs`
- early_stopping_patience: `{PATIENCE}`
- threshold_sweep: `0.30 to 0.75 step 0.05`
- postprocess_ablation: `raw mask / threshold only / threshold + remove small components / threshold + remove small components + opening/closing`
- per_epoch_validation: `light validation at threshold 0.5 only`
- full_threshold_postprocess_evaluation: `after best checkpoint training ends, plus optional --eval-full-every N`
- sample_prediction_count_per_run: `{SAMPLE_PREDICTION_COUNT}`

## Run Matrix

- input configs: `{list(INPUT_CONFIGS)}`
- model configs: `{list(MODEL_CONFIGS)}`
- loss configs: `{list(LOSS_CONFIGS)}`
- executed_run_count: `{len(summaries)}`

## Backend Integration Gate

Acceptance suggestion:

- test Precision >= `{GATE['test_precision_min']}`
- test Recall >= `{GATE['test_recall_min']}`
- test Dice >= `{GATE['test_dice_min']}`
- visual acceptable >= `{GATE['visual_acceptable_min']}`
- major failure = `{GATE['major_failure_max']}`

backend_integration_candidate_runs: `{len(gate_rows)}`

Even if a run passes metrics, backend integration remains blocked until visual QA and a separate backend gate are completed.
"""
    atomic_write_text(REPORTS / "uav_blb_segmentation_408_patch_v2_formal_training_report.md", md)
    atomic_write_text(
        REPORTS / "uav_blb_segmentation_408_patch_v2_backend_integration_gate.md",
        f"""# UAV BLB Segmentation 408 Patch v2 Backend Integration Gate

Current status: `BLOCKED`

The v2 formal route cannot be connected to backend unless all of the following are true:

- Formal training completed with at least 100 epochs or valid early stopping after the formal minimum.
- Test Precision >= `{GATE['test_precision_min']}`.
- Test Recall >= `{GATE['test_recall_min']}`.
- Test Dice >= `{GATE['test_dice_min']}`.
- At least 30 sample prediction QA images reviewed.
- Visual acceptable rate >= `{GATE['visual_acceptable_min']}`.
- major_failure = `{GATE['major_failure_max']}`.
- production_ready remains false until a separate production approval.

Current backend_integration_allowed: `false`
""",
    )
    atomic_write_text(
        REPORTS / "uav_blb_segmentation_408_patch_v2_failure_taxonomy.md",
        """# UAV BLB Segmentation 408 Patch v2 Failure Taxonomy

Track failures during visual QA using:

- OVER_SEGMENTATION: prediction is too broad while main BLB region is still covered.
- NOISE_FALSE_POSITIVE: multispectral texture or speckle is predicted as BLB.
- BACKGROUND_FALSE_POSITIVE: field edge, black border, water, soil, or unrelated background is predicted as BLB.
- UNDER_SEGMENTATION: major BLB foreground is missed.
- EDGE_FALSE_POSITIVE: valid-image boundary or black border creates false foreground.
- MAJOR_FAILURE: all-black, all-white, severe misalignment, or unrelated prediction.
- UNCERTAIN: multispectral texture cannot be judged without second review.
""",
    )
    stage = "FORMAL_TRAINING_QUICK_CHECK_COMPLETE" if quick else "FORMAL_TRAINING_MATRIX_COMPLETE"
    atomic_write_text(
        META,
        f"""bbox_route_status: BLOCKED
segmentation_route_stage: {stage}
segmentation_patch_v2_dataset_created: true
formal_training_executed: {str(not quick).lower()}
quick_training_check_executed: {str(quick).lower()}
formal_epoch_requirement_met: {str(any(s['formal_epoch_requirement_met'] for s in summaries)).lower()}
production_ready: false
backend_integration_allowed: false
original_images_modified: false
original_labels_modified: false
original_raster_masks_modified: false
backend_modified: false
env_modified: false
next_allowed_stage: VISUAL_QA_30_OR_FULL_FORMAL_TRAINING_COMPLETION
notes:
  - bbox route remains blocked
  - smoke weights are not formal weights
  - backend integration remains blocked
""",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-config", choices=list(INPUT_CONFIGS), default="D2_5BAND_NDVI")
    parser.add_argument("--model", choices=list(MODEL_CONFIGS), default="UNET_BASELINE")
    parser.add_argument("--loss", choices=list(LOSS_CONFIGS), default="BCE_TVERSKY_A07_B03")
    parser.add_argument("--all", action="store_true", help="run full 3x3x3 matrix")
    parser.add_argument("--quick-check", action="store_true", help="2 epoch syntax/runtime check, not formal training")
    parser.add_argument("--epochs", type=int, default=EPOCHS, help="training epochs; formal runs should be >=100")
    parser.add_argument("--patience", type=int, default=PATIENCE, help="early stopping patience after epoch 100")
    parser.add_argument("--progress", action="store_true", help="show tqdm train/val batch progress bars")
    parser.add_argument(
        "--eval-full-final-only",
        action="store_true",
        default=True,
        help="run full threshold/postprocess evaluation only after best checkpoint training ends; this is the default",
    )
    parser.add_argument("--eval-full-every", type=int, default=0, help="also run full threshold/postprocess eval every N epochs")
    parser.add_argument("--debug-fast", action="store_true", help="1 epoch small-subset debug run with visible logs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not MANIFEST.exists():
        raise FileNotFoundError(f"missing patch v2 manifest: {MANIFEST}")
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    combos = []
    if args.all:
        combos = [(i, m, l) for i in INPUT_CONFIGS for m in MODEL_CONFIGS for l in LOSS_CONFIGS]
    else:
        combos = [(args.input_config, args.model, args.loss)]
    quick = args.quick_check or args.debug_fast
    summaries = [
        train_one(
            i,
            m,
            l,
            quick=quick,
            epochs=args.epochs,
            patience=args.patience,
            progress=args.progress,
            eval_full_final_only=args.eval_full_final_only,
            eval_full_every=args.eval_full_every,
        )
        for i, m, l in combos
    ]
    write_global_reports(summaries, quick=quick)
    print(
        json.dumps(
            {
                "completed_runs": len(summaries),
                "quick_check": args.quick_check,
                "debug_fast": args.debug_fast,
                "epochs": args.epochs,
                "patience": args.patience,
                "progress": args.progress,
                "eval_full_final_only": args.eval_full_final_only,
                "eval_full_every": args.eval_full_every,
                "summaries": summaries,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
