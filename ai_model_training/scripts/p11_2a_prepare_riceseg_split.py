from __future__ import annotations

import csv
import json
import os
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
SOURCE_PAIRING = ROOT / "datasets_external/p11_open_datasets/riceseg_5932/pairing_report.csv"
EXP_DIR = ROOT / "experiments/p11_2a_riceseg_smoke"
SEED = 20260706
SPLIT_RATIOS = {"train": 0.70, "val": 0.15, "test": 0.15}
IMAGE_SIZE = 256
RESAMPLE_BILINEAR = getattr(Image, "Resampling", Image).BILINEAR
RESAMPLE_NEAREST = getattr(Image, "Resampling", Image).NEAREST

CLASS_MAPPING = {
    "Bacterialblight": {"class_id": 0, "disease_id": "bacterial_leaf_blight", "mapping_status": "mapped"},
    "Blast": {"class_id": 1, "disease_id": "rice_blast", "mapping_status": "mapped"},
    "Brownspot": {"class_id": 2, "disease_id": "brown_spot", "mapping_status": "mapped"},
    "Tungro": {"class_id": 3, "disease_id": "tungro_review_only", "mapping_status": "review_required"},
}

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


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def image_info(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        return {"mode": image.mode, "width": image.size[0], "height": image.size[1]}


def split_class_rows(rows: list[dict[str, Any]], rng: random.Random) -> dict[str, list[dict[str, Any]]]:
    shuffled = rows[:]
    rng.shuffle(shuffled)
    count = len(shuffled)
    val_count = round(count * SPLIT_RATIOS["val"])
    test_count = round(count * SPLIT_RATIOS["test"])
    train_count = count - val_count - test_count
    return {
        "train": shuffled[:train_count],
        "val": shuffled[train_count : train_count + val_count],
        "test": shuffled[train_count + val_count :],
    }


def main() -> None:
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_csv(SOURCE_PAIRING)
    rng = random.Random(SEED)

    prepared: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    duplicate_keys = Counter(row.get("pairing_key", "") for row in rows)

    for index, row in enumerate(rows):
        class_original = row["class_original"]
        image_path = Path(row["image_path"])
        mask_path = Path(row["mask_path"])
        paired = row.get("paired", "").lower() == "true"
        mapping = CLASS_MAPPING.get(class_original, {"class_id": 99, "disease_id": "unknown", "mapping_status": "unmapped"})

        image_exists = image_path.exists()
        mask_exists = mask_path.exists()
        image_meta: dict[str, Any] = {}
        mask_meta: dict[str, Any] = {}
        if image_exists:
            image_meta = image_info(image_path)
        if mask_exists:
            mask_meta = image_info(mask_path)

        if not paired or not image_exists or not mask_exists:
            errors.append(
                {
                    "pairing_key": row.get("pairing_key", ""),
                    "reason": f"paired={paired}; image_exists={image_exists}; mask_exists={mask_exists}",
                }
            )

        prepared.append(
            {
                "sample_id": f"riceseg_{index:05d}",
                "split": "",
                "class_original": class_original,
                "class_id": mapping["class_id"],
                "disease_id": mapping["disease_id"],
                "class_mapping_status": mapping["mapping_status"],
                "image_path": str(image_path),
                "mask_path": str(mask_path),
                "pairing_key": row.get("pairing_key", ""),
                "image_exists": image_exists,
                "mask_exists": mask_exists,
                "paired": paired,
                "duplicate_pairing_key_count": duplicate_keys[row.get("pairing_key", "")],
                "image_width": image_meta.get("width", ""),
                "image_height": image_meta.get("height", ""),
                "image_mode": image_meta.get("mode", ""),
                "mask_width": mask_meta.get("width", ""),
                "mask_height": mask_meta.get("height", ""),
                "mask_mode": mask_meta.get("mode", ""),
            }
        )

    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in prepared:
        by_class[row["class_original"]].append(row)

    split_rows = {"train": [], "val": [], "test": []}
    for class_name in sorted(by_class):
        parts = split_class_rows(by_class[class_name], rng)
        for split_name, part_rows in parts.items():
            for row in part_rows:
                row["split"] = split_name
            split_rows[split_name].extend(part_rows)

    fieldnames = [
        "sample_id",
        "split",
        "class_original",
        "class_id",
        "disease_id",
        "class_mapping_status",
        "image_path",
        "mask_path",
        "pairing_key",
        "paired",
        "image_exists",
        "mask_exists",
        "duplicate_pairing_key_count",
        "image_width",
        "image_height",
        "image_mode",
        "mask_width",
        "mask_height",
        "mask_mode",
    ]
    for split_name in ["train", "val", "test"]:
        atomic_write_csv(EXP_DIR / f"{split_name}.csv", split_rows[split_name], fieldnames)

    all_split_rows = split_rows["train"] + split_rows["val"] + split_rows["test"]
    split_by_pairing = defaultdict(set)
    for row in all_split_rows:
        split_by_pairing[row["pairing_key"]].add(row["split"])
    leakage_keys = [key for key, splits in split_by_pairing.items() if len(splits) > 1]

    split_counts = {split: len(split_rows[split]) for split in ["train", "val", "test"]}
    class_counts = {
        split: dict(Counter(row["class_original"] for row in split_rows[split]))
        for split in ["train", "val", "test"]
    }
    manifest = {
        "generated_at": now(),
        "source_pairing_report": rel(SOURCE_PAIRING),
        "experiment_dir": rel(EXP_DIR),
        "random_seed": SEED,
        "split_ratios": SPLIT_RATIOS,
        "image_size": IMAGE_SIZE,
        "total_rows": len(rows),
        "total_split_rows": len(all_split_rows),
        "paired_rows": sum(1 for row in prepared if row["paired"]),
        "missing_or_unpaired_rows": errors,
        "pairing_all_passed": not errors,
        "duplicate_pairing_key_count": sum(1 for key, count in duplicate_keys.items() if count > 1),
        "cross_split_leakage_key_count": len(leakage_keys),
        "cross_split_leakage_keys_preview": leakage_keys[:20],
        "split_counts": split_counts,
        "class_counts_total": dict(Counter(row["class_original"] for row in prepared)),
        "class_counts_by_split": class_counts,
        "class_mapping": CLASS_MAPPING,
        "safety": SAFETY,
        "held_out_test_policy": "test split is held out and must not be used for training or tuning",
    }
    config = {
        "stage": "P11-2A",
        "task": "rice leaf lesion semantic segmentation smoke baseline",
        "model_family": "tiny_unet_if_dependencies_available",
        "training_policy": "smoke_only",
        "epochs": 1,
        "batch_size": 4,
        "image_size": IMAGE_SIZE,
        "max_train_samples": 64,
        "max_val_samples": 32,
        "random_seed": SEED,
        "outputs": {
            "weights": rel(EXP_DIR / "model_experimental_smoke.pt"),
            "metrics": rel(EXP_DIR / "metrics_smoke.json"),
            "prediction_samples": rel(EXP_DIR / "prediction_samples"),
        },
        "safety": SAFETY,
    }
    atomic_write_json(EXP_DIR / "split_manifest.json", manifest)
    atomic_write_json(EXP_DIR / "config.json", config)
    print(json.dumps({"status": "PASS", "split_counts": split_counts, "pairing_all_passed": not errors}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
