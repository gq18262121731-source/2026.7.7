from __future__ import annotations

import csv
import importlib.util
import json
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
EXP_DIR = ROOT / "experiments/p11_2a_riceseg_smoke"
TRAIN_CSV = EXP_DIR / "train.csv"
VAL_CSV = EXP_DIR / "val.csv"
METRICS_PATH = EXP_DIR / "metrics_smoke.json"
MODEL_PATH = EXP_DIR / "model_experimental_smoke.pt"
SEED = 20260706
RESAMPLE_BILINEAR = getattr(Image, "Resampling", Image).BILINEAR
RESAMPLE_NEAREST = getattr(Image, "Resampling", Image).NEAREST

SAFETY = {
    "experimental": True,
    "smoke_only": True,
    "not_for_production": True,
    "probability_claim": False,
    "backend_main_chain_integration": False,
    "risk_fusion_ml_training": False,
    "prescription_or_dosage": False,
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def missing_dependencies() -> list[str]:
    return [name for name in ["torch", "torchvision", "numpy"] if importlib.util.find_spec(name) is None]


def pil_dataloader_smoke(rows: list[dict[str, str]], limit: int = 8, image_size: int = 256) -> dict[str, Any]:
    checked = []
    for row in rows[:limit]:
        image = Image.open(row["image_path"]).convert("RGB").resize((image_size, image_size), RESAMPLE_BILINEAR)
        mask = Image.open(row["mask_path"]).convert("L").resize((image_size, image_size), RESAMPLE_NEAREST)
        positive_pixels = sum(1 for value in mask.getdata() if value > 0)
        checked.append(
            {
                "sample_id": row["sample_id"],
                "class_original": row["class_original"],
                "image_size": list(image.size),
                "mask_size": list(mask.size),
                "mask_positive_pixels": positive_pixels,
            }
        )
    return {"status": "PASS", "checked_samples": len(checked), "samples": checked}


def blocked_result(started_at: float, missing: list[str]) -> dict[str, Any]:
    train_rows = read_csv(TRAIN_CSV)
    val_rows = read_csv(VAL_CSV)
    return {
        "generated_at": now(),
        "status": "BLOCKED_BY_DEPENDENCY",
        "training_completed": False,
        "weights_generated": False,
        "weights_path": rel(MODEL_PATH),
        "missing_dependencies": missing,
        "suggested_install_command": "Install a project-approved CPU/GPU PyTorch build and numpy in the experimental training environment before rerunning.",
        "dataset_loaded": True,
        "train_rows": len(train_rows),
        "val_rows": len(val_rows),
        "pil_dataloader_smoke": pil_dataloader_smoke(train_rows),
        "smoke_metrics": {
            "loss": None,
            "iou": None,
            "dice": None,
            "metric_scope": "not_computed_dependency_blocked",
        },
        "duration_seconds": round(time.time() - started_at, 3),
        "safety": SAFETY,
    }


def run_torch_training(started_at: float) -> dict[str, Any]:
    import numpy as np
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, Dataset

    torch.manual_seed(SEED)
    random.seed(SEED)
    image_size = 256
    train_rows = read_csv(TRAIN_CSV)[:64]
    val_rows = read_csv(VAL_CSV)[:32]

    class RiceSegSmokeDataset(Dataset):
        def __init__(self, rows: list[dict[str, str]]) -> None:
            self.rows = rows

        def __len__(self) -> int:
            return len(self.rows)

        def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
            row = self.rows[index]
            image = Image.open(row["image_path"]).convert("RGB").resize((image_size, image_size), RESAMPLE_BILINEAR)
            mask = Image.open(row["mask_path"]).convert("L").resize((image_size, image_size), RESAMPLE_NEAREST)
            image_np = np.asarray(image, dtype=np.float32).transpose(2, 0, 1) / 255.0
            mask_np = (np.asarray(mask, dtype=np.float32) > 0).astype(np.float32)[None, :, :]
            return torch.from_numpy(image_np), torch.from_numpy(mask_np)

    class TinyUNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.enc1 = nn.Sequential(nn.Conv2d(3, 8, 3, padding=1), nn.ReLU(), nn.Conv2d(8, 8, 3, padding=1), nn.ReLU())
            self.pool = nn.MaxPool2d(2)
            self.enc2 = nn.Sequential(nn.Conv2d(8, 16, 3, padding=1), nn.ReLU(), nn.Conv2d(16, 16, 3, padding=1), nn.ReLU())
            self.up = nn.ConvTranspose2d(16, 8, 2, stride=2)
            self.dec = nn.Sequential(nn.Conv2d(16, 8, 3, padding=1), nn.ReLU(), nn.Conv2d(8, 8, 3, padding=1), nn.ReLU())
            self.out = nn.Conv2d(8, 1, 1)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            x1 = self.enc1(x)
            x2 = self.enc2(self.pool(x1))
            y = self.up(x2)
            y = torch.cat([y, x1], dim=1)
            return self.out(self.dec(y))

    def dice_iou(logits: torch.Tensor, masks: torch.Tensor) -> tuple[float, float]:
        pred = (torch.sigmoid(logits) > 0.5).float()
        intersection = (pred * masks).sum().item()
        pred_sum = pred.sum().item()
        mask_sum = masks.sum().item()
        union = pred_sum + mask_sum - intersection
        dice = (2 * intersection + 1e-6) / (pred_sum + mask_sum + 1e-6)
        iou = (intersection + 1e-6) / (union + 1e-6)
        return dice, iou

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = TinyUNet().to(device)
    loss_fn = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    train_loader = DataLoader(RiceSegSmokeDataset(train_rows), batch_size=4, shuffle=True, num_workers=0)
    val_loader = DataLoader(RiceSegSmokeDataset(val_rows), batch_size=4, shuffle=False, num_workers=0)

    model.train()
    losses = []
    for images, masks in train_loader:
        images = images.to(device)
        masks = masks.to(device)
        optimizer.zero_grad()
        logits = model(images)
        loss = loss_fn(logits, masks)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.item()))

    model.eval()
    val_dice = []
    val_iou = []
    with torch.no_grad():
        for images, masks in val_loader:
            logits = model(images.to(device))
            dice, iou = dice_iou(logits.cpu(), masks)
            val_dice.append(dice)
            val_iou.append(iou)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "model_type": "tiny_unet_smoke",
            "experimental": True,
            "smoke_only": True,
            "not_for_production": True,
            "probability_claim": False,
        },
        MODEL_PATH,
    )
    return {
        "generated_at": now(),
        "status": "PASS_SMOKE_TRAINING_COMPLETED",
        "training_completed": True,
        "weights_generated": True,
        "weights_path": rel(MODEL_PATH),
        "device": str(device),
        "train_rows_used": len(train_rows),
        "val_rows_used": len(val_rows),
        "epochs": 1,
        "batch_size": 4,
        "smoke_metrics": {
            "train_loss_mean": sum(losses) / max(1, len(losses)),
            "val_iou_mean": sum(val_iou) / max(1, len(val_iou)),
            "val_dice_mean": sum(val_dice) / max(1, len(val_dice)),
            "metric_scope": "smoke_metrics_only_not_formal",
        },
        "duration_seconds": round(time.time() - started_at, 3),
        "safety": SAFETY,
    }


def main() -> None:
    started_at = time.time()
    missing = missing_dependencies()
    if missing:
        result = blocked_result(started_at, missing)
    else:
        result = run_torch_training(started_at)
    atomic_write_json(METRICS_PATH, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
