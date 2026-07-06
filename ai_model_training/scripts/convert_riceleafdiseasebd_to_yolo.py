#!/usr/bin/env python
"""Convert RiceLeafDiseaseBD official package into an independent YOLO dataset.

The converter is intentionally conservative:
- source files are never modified, moved, or renamed;
- output is first written to a sibling temporary directory and then atomically
  promoted to the final output directory;
- Healthy is excluded from YOLO disease classes;
- source label class ids are audited but the final class id is assigned from
  the source disease directory name, because this package contains observed
  source-id inconsistencies.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SOURCE_URL = "https://data.mendeley.com/datasets/86s4jzj2m4/1"
LICENSE = "CC BY 4.0"
DATASET_NAME = "RiceLeafDiseaseBD"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


CLASS_MAP = {
    "Brown spot": {"id": 0, "code": "brown_spot", "source_alias": "Brown Spot"},
    "Blast": {"id": 1, "code": "rice_blast", "source_alias": "Blast"},
    "Leaf smut": {"id": 2, "code": "leaf_smut", "source_alias": "Leaf Smut"},
    "Rice Tungro": {"id": 3, "code": "tungro", "source_alias": "Rice Tungro"},
    "Sheath blight": {"id": 4, "code": "sheath_blight", "source_alias": "Sheath Blight"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert RiceLeafDiseaseBD to independent YOLO layout.")
    parser.add_argument("--input-root", required=True, help="Extracted official package root.")
    parser.add_argument("--output-root", required=True, help="Final YOLO dataset output root.")
    parser.add_argument("--sample-size", type=int, help="Optional total sample size. Defaults to full conversion.")
    parser.add_argument("--seed", type=int, default=20260623)
    parser.add_argument("--dry-run", action="store_true", help="Audit only; do not write output dataset.")
    parser.add_argument("--execute", action="store_true", help="Write the output dataset.")
    return parser.parse_args()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    with tmp_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    if not tmp_path.exists() or tmp_path.stat().st_size == 0:
        raise RuntimeError(f"Temporary file was not written correctly: {tmp_path}")
    os.replace(tmp_path, path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"Final file was not written correctly: {path}")


def find_dataset_root(input_root: Path) -> Path:
    direct = input_root / "RiceLeafDiseaseBD"
    if (direct / "Original images").exists() and (direct / "Annotated images ( visual with labels)").exists():
        return direct
    candidates = [
        p
        for p in input_root.rglob("RiceLeafDiseaseBD")
        if p.is_dir() and (p / "Original images").exists() and (p / "Annotated images ( visual with labels)").exists()
    ]
    if not candidates:
        raise FileNotFoundError("Could not locate RiceLeafDiseaseBD/Original images and Annotated images directories.")
    return sorted(candidates, key=lambda p: len(p.parts))[0]


def read_label_lines(path: Path) -> tuple[list[str], Counter[str], int]:
    if not path.exists():
        raise FileNotFoundError(path)
    output_lines: list[str] = []
    source_ids: Counter[str] = Counter()
    invalid = 0
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            invalid += 1
            continue
        source_ids[parts[0]] += 1
        try:
            _ = int(float(parts[0]))
            coords = [float(v) for v in parts[1:]]
        except ValueError:
            invalid += 1
            continue
        if any(v < 0.0 or v > 1.0 for v in coords) or coords[2] <= 0.0 or coords[3] <= 0.0:
            invalid += 1
            continue
        output_lines.append(" ".join(f"{v:.6f}" for v in coords))
    return output_lines, source_ids, invalid


def file_sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_records(dataset_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    original_root = dataset_root / "Original images"
    annotated_root = dataset_root / "Annotated images ( visual with labels)"
    if not original_root.exists() or not annotated_root.exists():
        raise FileNotFoundError("Expected Original images and Annotated images directories are missing.")

    records: list[dict[str, Any]] = []
    seen_image_hashes: dict[str, dict[str, str]] = {}
    duplicate_excluded: list[dict[str, str]] = []
    class_counts: Counter[str] = Counter()
    source_id_counts_by_class: dict[str, Counter[str]] = defaultdict(Counter)
    invalid_label_lines = 0
    empty_label_files = 0

    for source_class, mapped in CLASS_MAP.items():
        image_dir = original_root / source_class
        label_dir = annotated_root / source_class / "labels"
        if not image_dir.exists():
            raise FileNotFoundError(f"Missing source image directory: {image_dir}")
        if not label_dir.exists():
            raise FileNotFoundError(f"Missing source label directory: {label_dir}")
        labels = sorted(label_dir.glob("*.txt"))
        for label_path in labels:
            image_path = None
            for suffix in IMAGE_SUFFIXES:
                candidate = image_dir / f"{label_path.stem}{suffix}"
                if candidate.exists():
                    image_path = candidate
                    break
            if image_path is None:
                raise FileNotFoundError(f"No matching original image for label: {label_path}")
            coord_lines, source_ids, invalid = read_label_lines(label_path)
            invalid_label_lines += invalid
            source_id_counts_by_class[source_class].update(source_ids)
            if not coord_lines:
                empty_label_files += 1
                continue
            image_hash = file_sha1(image_path)
            if image_hash in seen_image_hashes:
                first = seen_image_hashes[image_hash]
                duplicate_excluded.append(
                    {
                        "image_path": str(image_path),
                        "label_path": str(label_path),
                        "source_class": source_class,
                        "mapped_code": mapped["code"],
                        "duplicate_of_image_path": first["image_path"],
                        "duplicate_of_source_class": first["source_class"],
                        "sha1": image_hash,
                    }
                )
                continue
            seen_image_hashes[image_hash] = {
                "image_path": str(image_path),
                "source_class": source_class,
            }
            class_counts[mapped["code"]] += 1
            records.append(
                {
                    "source_class": source_class,
                    "source_alias": mapped["source_alias"],
                    "mapped_class_id": mapped["id"],
                    "mapped_code": mapped["code"],
                    "image_path": image_path,
                    "label_path": label_path,
                    "bbox_coords": coord_lines,
                    "bbox_count": len(coord_lines),
                    "source_id_counts": dict(source_ids),
                    "invalid_label_lines": invalid,
                }
            )

    healthy_dir = original_root / "Healthy"
    healthy_count = len(list(healthy_dir.glob("*.jpg"))) if healthy_dir.exists() else 0
    summary = {
        "source_image_count_by_class": dict(class_counts),
        "healthy_excluded_count": healthy_count,
        "source_id_counts_by_class": {
            source: dict(counts) for source, counts in sorted(source_id_counts_by_class.items())
        },
        "invalid_label_lines": invalid_label_lines,
        "empty_label_files": empty_label_files,
        "duplicate_image_files_excluded": len(duplicate_excluded),
        "duplicate_image_samples": duplicate_excluded[:50],
    }
    return records, summary


def choose_sample(records: list[dict[str, Any]], sample_size: int | None, seed: int) -> list[dict[str, Any]]:
    if sample_size is None or sample_size >= len(records):
        return records
    rng = random.Random(seed)
    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_class[record["mapped_code"]].append(record)
    selected: list[dict[str, Any]] = []
    remaining = sample_size
    class_names = sorted(by_class)
    for idx, class_name in enumerate(class_names):
        pool = list(by_class[class_name])
        rng.shuffle(pool)
        if idx == len(class_names) - 1:
            take = remaining
        else:
            take = min(len(pool), max(1, round(sample_size * len(pool) / len(records))))
            remaining -= take
        selected.extend(pool[:take])
    return selected[:sample_size]


def assign_splits(records: list[dict[str, Any]], seed: int) -> dict[str, list[dict[str, Any]]]:
    rng = random.Random(seed)
    splits: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "test": []}
    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_class[record["mapped_code"]].append(record)
    for class_name, class_records in sorted(by_class.items()):
        items = list(class_records)
        rng.shuffle(items)
        total = len(items)
        train_count = int(total * 0.7)
        val_count = int(total * 0.2)
        if total >= 10:
            train_count = max(1, train_count)
            val_count = max(1, val_count)
        test_count = total - train_count - val_count
        if total >= 10 and test_count == 0:
            test_count = 1
            train_count -= 1
        splits["train"].extend(items[:train_count])
        splits["val"].extend(items[train_count : train_count + val_count])
        splits["test"].extend(items[train_count + val_count :])
    for split_records in splits.values():
        split_records.sort(key=lambda r: (r["mapped_class_id"], r["image_path"].name))
    return splits


def unique_output_name(record: dict[str, Any]) -> str:
    class_code = record["mapped_code"]
    safe_stem = record["image_path"].stem.replace(" ", "_")
    return f"{class_code}__{safe_stem}{record['image_path'].suffix.lower()}"


def write_dataset(output_tmp: Path, output_root: Path, splits: dict[str, list[dict[str, Any]]], summary: dict[str, Any]) -> dict[str, Any]:
    for split in ("train", "val", "test"):
        (output_tmp / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_tmp / "labels" / split).mkdir(parents=True, exist_ok=True)
    (output_tmp / "metadata").mkdir(parents=True, exist_ok=True)

    metadata_rows: list[dict[str, Any]] = []
    split_counts: Counter[str] = Counter()
    class_distribution: Counter[str] = Counter()
    bbox_distribution: Counter[str] = Counter()
    label_files = 0
    image_files = 0
    total_bboxes = 0

    for split, records in splits.items():
        for record in records:
            image_name = unique_output_name(record)
            label_name = f"{Path(image_name).stem}.txt"
            image_dest = output_tmp / "images" / split / image_name
            label_dest = output_tmp / "labels" / split / label_name
            shutil.copy2(record["image_path"], image_dest)
            remapped_lines = [
                f"{record['mapped_class_id']} {coords}" for coords in record["bbox_coords"]
            ]
            atomic_write_text(label_dest, "\n".join(remapped_lines) + ("\n" if remapped_lines else ""))
            image_files += 1
            label_files += 1
            split_counts[split] += 1
            class_distribution[record["mapped_code"]] += 1
            bbox_distribution[record["mapped_code"]] += record["bbox_count"]
            total_bboxes += record["bbox_count"]
            metadata_rows.append(
                {
                    "image_name": image_name,
                    "dataset_name": DATASET_NAME,
                    "source_dataset": DATASET_NAME,
                    "source_url": SOURCE_URL,
                    "license": LICENSE,
                    "source_type": "phone_rgb",
                    "sensor_type": "smartphone_rgb",
                    "split": split,
                    "source_split": "none_official_split",
                    "original_label": record["source_alias"],
                    "mapped_code": record["mapped_code"],
                    "category_type": "disease",
                    "original_image_path": str(record["image_path"]),
                    "original_label_path": str(record["label_path"]),
                    "original_class_id": json.dumps(record["source_id_counts"], ensure_ascii=False),
                    "mapped_class_id": record["mapped_class_id"],
                    "bbox_count": record["bbox_count"],
                    "excluded_reason": "",
                    "notes": "source label class ids remapped by source directory name; Healthy excluded",
                }
            )

    data_yaml = [
        "path: datasets/rice_phone_rgb_expanded",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "nc: 5",
        "names:",
    ]
    for source_class, mapped in sorted(CLASS_MAP.items(), key=lambda item: item[1]["id"]):
        data_yaml.append(f"  {mapped['id']}: {mapped['code']}")
    atomic_write_text(output_tmp / "data.yaml", "\n".join(data_yaml) + "\n")

    class_map_lines = [
        "version: rice_phone_rgb_expanded_v1",
        "model_name: phone_rice_disease_yolo",
        f"dataset_name: {DATASET_NAME}",
        f"source_url: {SOURCE_URL}",
        f"license: {LICENSE}",
        "category_type: disease",
        "source_type: phone_rgb",
        "sensor_type: smartphone_rgb",
        "healthy_policy: excluded_from_yolo_labels_health_status_only",
        "classes:",
    ]
    for source_class, mapped in sorted(CLASS_MAP.items(), key=lambda item: item[1]["id"]):
        class_map_lines.extend(
            [
                f"  - id: {mapped['id']}",
                f"    code: {mapped['code']}",
                f"    source_label: {mapped['source_alias']}",
                "    category_type: disease",
            ]
        )
    class_map_lines.extend(
        [
            "excluded_classes:",
            "  - code: healthy",
            "    reason: health_status_only_not_a_yolo_disease_class",
            "notes:",
            "  - Source labels are remapped by source directory name because observed source class ids are inconsistent for Leaf smut and Rice Tungro.",
            "  - This dataset is independent from datasets/rice_phone_rgb and does not overwrite the smoke baseline.",
        ]
    )
    atomic_write_text(output_tmp / "metadata" / "class_map.yaml", "\n".join(class_map_lines) + "\n")

    metadata_path = output_tmp / "metadata" / "image_metadata.csv"
    metadata_tmp = metadata_path.with_name(metadata_path.name + ".tmp")
    with metadata_tmp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metadata_rows[0].keys()))
        writer.writeheader()
        writer.writerows(metadata_rows)
    os.replace(metadata_tmp, metadata_path)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_name": DATASET_NAME,
        "source_url": SOURCE_URL,
        "license": LICENSE,
        "output_root": str(output_root),
        "output_tmp": str(output_tmp),
        "images": image_files,
        "labels": label_files,
        "bboxes": total_bboxes,
        "class_count": 5,
        "class_distribution_images": dict(class_distribution),
        "class_distribution_bboxes": dict(bbox_distribution),
        "split_distribution": dict(split_counts),
        "healthy_excluded_count": summary["healthy_excluded_count"],
        "empty_label_files": summary["empty_label_files"],
        "duplicate_image_files_excluded": summary.get("duplicate_image_files_excluded", 0),
        "duplicate_image_samples": summary.get("duplicate_image_samples", []),
        "invalid_label_lines_skipped": summary["invalid_label_lines"],
        "source_id_counts_by_class": summary["source_id_counts_by_class"],
        "class_id_policy": "final class ids are assigned by source disease directory name; Healthy is excluded",
        "formal_metrics_generated": False,
        "training_started": False,
    }
    atomic_write_text(output_tmp / "conversion_report.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def main() -> int:
    args = parse_args()
    if args.dry_run and args.execute:
        raise SystemExit("Choose only one of --dry-run or --execute.")
    if not args.dry_run and not args.execute:
        raise SystemExit("Pass --dry-run or --execute.")

    input_root = Path(args.input_root)
    output_root = Path(args.output_root)
    dataset_root = find_dataset_root(input_root)
    records, summary = collect_records(dataset_root)
    records = choose_sample(records, args.sample_size, args.seed)
    splits = assign_splits(records, args.seed)

    dry_report = {
        "input_root": str(input_root),
        "dataset_root": str(dataset_root),
        "output_root": str(output_root),
        "record_count": len(records),
        "split_distribution": {split: len(items) for split, items in splits.items()},
        "class_distribution": dict(Counter(r["mapped_code"] for r in records)),
        "bbox_count": sum(r["bbox_count"] for r in records),
        "healthy_excluded_count": summary["healthy_excluded_count"],
        "empty_label_files": summary["empty_label_files"],
        "duplicate_image_files_excluded": summary.get("duplicate_image_files_excluded", 0),
        "invalid_label_lines": summary["invalid_label_lines"],
        "source_id_counts_by_class": summary["source_id_counts_by_class"],
    }

    if args.dry_run:
        print(json.dumps(dry_report, ensure_ascii=False, indent=2))
        return 0

    if output_root.exists():
        raise FileExistsError(f"Refusing to overwrite existing output root: {output_root}")
    output_tmp = output_root.with_name(output_root.name + ".tmp")
    if output_tmp.exists():
        raise FileExistsError(f"Temporary output root already exists: {output_tmp}")

    report = write_dataset(output_tmp, output_root, splits, summary)
    os.replace(output_tmp, output_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
