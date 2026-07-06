from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

try:
    import tifffile
except ImportError:  # pragma: no cover
    tifffile = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

try:
    from scipy import ndimage
except ImportError:  # pragma: no cover
    ndimage = None


SPLITS = ("train", "val", "test")
DEFAULT_SOURCE_DATASETS = ("D1", "D2", "D3")
SPLIT_RATIOS = {"train": 0.70, "val": 0.20, "test": 0.10}
BLB_VALUE_TO_SEVERITY = {2: "low", 3: "high"}
CLASS_CODE = "bacterial_leaf_blight"
SOURCE_URL = "https://figshare.com/articles/dataset/BLB_UAV_Dataset/26955862"


@dataclass(frozen=True)
class Pair:
    dataset: str
    split: str
    patch_id: str
    image_path: Path
    label_path: Path


@dataclass(frozen=True)
class Box:
    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float
    area: int
    severity: str
    raster_value: int


@dataclass(frozen=True)
class Candidate:
    pair: Pair
    boxes: tuple[Box, ...]
    severity_key: str
    mask_values: tuple[int, ...]
    preview_sha1: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Expand BLB UAV TIF masks into a YOLO RGB preview dataset.")
    parser.add_argument("--input-root", default="raw_datasets/blb_uav_dataset/original")
    parser.add_argument("--output-root", default="datasets/rice_uav_ms_blb_preview_300")
    parser.add_argument("--target-samples", type=int, default=300)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--min-area-pixels", type=int, default=25)
    parser.add_argument("--balance-severity", action="store_true")
    parser.add_argument("--source-datasets", nargs="+", default=list(DEFAULT_SOURCE_DATASETS))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root() / path


def relative_for_yaml(path: Path) -> str:
    try:
        return str(path.relative_to(repo_root())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def runtime_missing() -> list[str]:
    missing: list[str] = []
    if tifffile is None:
        missing.append("tifffile")
    if Image is None:
        missing.append("Pillow")
    if ndimage is None:
        missing.append("scipy")
    return missing


def read_tif(path: Path) -> np.ndarray:
    if tifffile is None:
        raise RuntimeError("tifffile is required.")
    return np.asarray(tifffile.imread(path))


def label_values(label: np.ndarray) -> tuple[int, ...]:
    return tuple(sorted(int(v) for v in np.unique(label).tolist()))


def image_hw_channels(array: np.ndarray) -> tuple[int, int, int]:
    if array.ndim == 2:
        return int(array.shape[0]), int(array.shape[1]), 1
    if array.ndim == 3 and array.shape[0] <= 12 and array.shape[2] > 12:
        return int(array.shape[1]), int(array.shape[2]), int(array.shape[0])
    if array.ndim == 3:
        return int(array.shape[0]), int(array.shape[1]), int(array.shape[2])
    raise ValueError(f"Unsupported image array shape: {array.shape}")


def to_hwc(array: np.ndarray) -> np.ndarray:
    if array.ndim == 2:
        return array[:, :, None]
    if array.ndim == 3 and array.shape[0] <= 12 and array.shape[2] > 12:
        return np.moveaxis(array, 0, -1)
    if array.ndim == 3:
        return array
    raise ValueError(f"Unsupported image array shape: {array.shape}")


def normalize_band(band: np.ndarray) -> np.ndarray:
    band = band.astype(np.float32)
    finite = band[np.isfinite(band)]
    if finite.size == 0:
        return np.zeros(band.shape, dtype=np.uint8)
    lo, hi = np.percentile(finite, [1, 99])
    if hi <= lo:
        lo = float(np.min(finite))
        hi = float(np.max(finite))
    if hi <= lo:
        return np.zeros(band.shape, dtype=np.uint8)
    scaled = (band - lo) / (hi - lo)
    return (np.clip(scaled, 0.0, 1.0) * 255).astype(np.uint8)


def multispectral_to_rgb(array: np.ndarray) -> np.ndarray:
    hwc = to_hwc(array)
    channels = hwc.shape[2]
    if channels >= 3:
        rgb = np.stack([hwc[:, :, 2], hwc[:, :, 1], hwc[:, :, 0]], axis=-1)
    elif channels == 2:
        rgb = np.stack([hwc[:, :, 1], hwc[:, :, 0], hwc[:, :, 0]], axis=-1)
    else:
        rgb = np.repeat(hwc[:, :, :1], 3, axis=2)
    return np.stack([normalize_band(rgb[:, :, i]) for i in range(3)], axis=-1)


def boxes_from_label(label: np.ndarray, min_area_pixels: int) -> tuple[Box, ...]:
    if ndimage is None:
        raise RuntimeError("scipy is required.")
    if label.ndim > 2:
        label = label[:, :, 0]
    height, width = label.shape[:2]
    boxes: list[Box] = []
    for raster_value, severity in BLB_VALUE_TO_SEVERITY.items():
        labeled, count = ndimage.label(np.asarray(label == raster_value))
        for component_id in range(1, count + 1):
            ys, xs = np.where(labeled == component_id)
            area = int(xs.size)
            if area < min_area_pixels:
                continue
            x1, x2 = int(xs.min()), int(xs.max())
            y1, y2 = int(ys.min()), int(ys.max())
            boxes.append(
                Box(
                    class_id=0,
                    x_center=((x1 + x2 + 1) / 2) / width,
                    y_center=((y1 + y2 + 1) / 2) / height,
                    width=(x2 - x1 + 1) / width,
                    height=(y2 - y1 + 1) / height,
                    area=area,
                    severity=severity,
                    raster_value=raster_value,
                )
            )
    return tuple(boxes)


def find_pairs(input_root: Path, source_datasets: list[str]) -> list[Pair]:
    pairs: list[Pair] = []
    for dataset in source_datasets:
        for split in SPLITS:
            image_dir = input_root / dataset / split
            label_dir = input_root / dataset / f"{split}_labels"
            if not image_dir.exists() or not label_dir.exists():
                continue
            for image_path in sorted(image_dir.glob("image_patch_*.tif")):
                patch_id = image_path.stem.replace("image_patch_", "")
                label_path = label_dir / f"label_patch_{patch_id}.tif"
                if label_path.exists():
                    pairs.append(Pair(dataset, split, patch_id, image_path, label_path))
    return pairs


def severity_key(boxes: tuple[Box, ...]) -> str:
    values = sorted({box.severity for box in boxes})
    if values == ["high", "low"]:
        return "mixed"
    return values[0] if values else "none"


def scan_candidates(pairs: list[Pair], min_area_pixels: int) -> tuple[list[Candidate], dict[str, Any]]:
    candidates: list[Candidate] = []
    stats: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    for pair in pairs:
        stats["pairs_scanned"] += 1
        try:
            label = read_tif(pair.label_path)
            boxes = boxes_from_label(label, min_area_pixels)
            values = label_values(label)
        except Exception as exc:  # noqa: BLE001 - report source issue and continue
            stats["scan_errors"] += 1
            errors.append({"label": str(pair.label_path), "error": f"{type(exc).__name__}: {exc}"})
            continue
        if not boxes:
            stats["skipped_without_blb_bbox"] += 1
            continue
        try:
            preview_rgb = multispectral_to_rgb(read_tif(pair.image_path))
            preview_sha1 = hashlib.sha1(preview_rgb.tobytes()).hexdigest()
        except Exception as exc:  # noqa: BLE001 - report source issue and continue
            stats["preview_hash_errors"] += 1
            errors.append({"image": str(pair.image_path), "error": f"{type(exc).__name__}: {exc}"})
            continue
        candidate = Candidate(
            pair=pair,
            boxes=boxes,
            severity_key=severity_key(boxes),
            mask_values=values,
            preview_sha1=preview_sha1,
        )
        candidates.append(candidate)
        stats[f"positive_split_{pair.split}"] += 1
        stats[f"positive_dataset_{pair.dataset}"] += 1
        stats[f"positive_severity_{candidate.severity_key}"] += 1
    return candidates, {"stats": dict(stats), "errors": errors[:50], "error_count": len(errors)}


def split_targets(target_samples: int) -> dict[str, int]:
    targets = {split: int(round(target_samples * SPLIT_RATIOS[split])) for split in SPLITS}
    targets["train"] += target_samples - sum(targets.values())
    return targets


def select_for_split(
    candidates: list[Candidate],
    limit: int,
    rng: random.Random,
    balance_severity: bool,
    global_used_keys: set[tuple[str, str, str]],
    global_used_hashes: set[str],
) -> list[Candidate]:
    group_order: list[tuple[str, str]] = []
    groups: dict[tuple[str, str], deque[Candidate]] = {}
    severities = ("low", "high", "mixed") if balance_severity else ("any",)

    for severity in severities:
        for dataset in DEFAULT_SOURCE_DATASETS:
            group_order.append((dataset, severity))

    for dataset, severity in group_order:
        values = [
            item
            for item in candidates
            if item.pair.dataset == dataset and (severity == "any" or item.severity_key == severity)
        ]
        rng.shuffle(values)
        groups[(dataset, severity)] = deque(values)

    selected: list[Candidate] = []
    used_patch_ids: set[str] = set()
    while len(selected) < limit:
        progressed = False
        for group in group_order:
            queue = groups[group]
            while queue:
                item = queue.popleft()
                unique_key = (item.pair.dataset, item.pair.split, item.pair.patch_id)
                if unique_key in global_used_keys:
                    continue
                if item.preview_sha1 in global_used_hashes:
                    continue
                if item.pair.patch_id in used_patch_ids:
                    continue
                selected.append(item)
                used_patch_ids.add(item.pair.patch_id)
                global_used_keys.add(unique_key)
                global_used_hashes.add(item.preview_sha1)
                progressed = True
                break
            if len(selected) >= limit:
                break
        if not progressed:
            break

    if len(selected) < limit:
        leftovers = candidates[:]
        rng.shuffle(leftovers)
        for item in leftovers:
            unique_key = (item.pair.dataset, item.pair.split, item.pair.patch_id)
            if unique_key in global_used_keys:
                continue
            if item.preview_sha1 in global_used_hashes:
                continue
            selected.append(item)
            global_used_keys.add(unique_key)
            global_used_hashes.add(item.preview_sha1)
            if len(selected) >= limit:
                break
    return selected


def select_candidates(
    candidates: list[Candidate],
    target_samples: int,
    seed: int,
    balance_severity: bool,
) -> tuple[list[Candidate], dict[str, Any]]:
    rng = random.Random(seed)
    targets = split_targets(target_samples)
    selected: list[Candidate] = []
    used_keys: set[tuple[str, str, str]] = set()
    used_hashes: set[str] = set()
    for split in SPLITS:
        split_candidates = [item for item in candidates if item.pair.split == split]
        selected.extend(select_for_split(split_candidates, targets[split], rng, balance_severity, used_keys, used_hashes))

    stats = summarize_selection(selected)
    shortages = {
        split: max(0, targets[split] - stats["split_distribution"].get(split, 0))
        for split in SPLITS
    }
    return selected, {"target_split_distribution": targets, "shortages": shortages, **stats}


def summarize_selection(selected: list[Candidate]) -> dict[str, Any]:
    split_counts = Counter(item.pair.split for item in selected)
    dataset_counts = Counter(item.pair.dataset for item in selected)
    severity_image_counts = Counter(item.severity_key for item in selected)
    severity_bbox_counts: Counter[str] = Counter()
    bbox_total = 0
    for item in selected:
        bbox_total += len(item.boxes)
        for box in item.boxes:
            severity_bbox_counts[box.severity] += 1
    return {
        "selected_count": len(selected),
        "bbox_count": bbox_total,
        "split_distribution": dict(split_counts),
        "source_dataset_distribution": dict(dataset_counts),
        "severity_image_distribution": dict(severity_image_counts),
        "severity_bbox_distribution": dict(severity_bbox_counts),
    }


def clean_output(output_root: Path) -> None:
    if output_root.exists():
        shutil.rmtree(output_root)
    for split in SPLITS:
        (output_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_root / "labels" / split).mkdir(parents=True, exist_ok=True)
    (output_root / "metadata").mkdir(parents=True, exist_ok=True)


def ensure_output(output_root: Path) -> None:
    for split in SPLITS:
        (output_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_root / "labels" / split).mkdir(parents=True, exist_ok=True)
    (output_root / "metadata").mkdir(parents=True, exist_ok=True)


def write_static_files(output_root: Path) -> None:
    yaml_root = relative_for_yaml(output_root)
    (output_root / "data.yaml").write_text(
        "\n".join(
            [
                f"path: {yaml_root}",
                "train: images/train",
                "val: images/val",
                "test: images/test",
                "nc: 1",
                "names:",
                f"  0: {CLASS_CODE}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (output_root / "metadata" / "class_map.yaml").write_text(
        "\n".join(
            [
                "version: rice_uav_ms_blb_preview_expanded_v1",
                "model_name: uav_rice_disease_yolo",
                "source_dataset: BLB_UAV_Dataset",
                f"source_url: {SOURCE_URL}",
                "license: CC BY 4.0",
                "category_type: disease",
                "source_type: uav_multispectral",
                "sensor_type: multispectral",
                "classes:",
                f"  0: {CLASS_CODE}",
                "mapping_rules:",
                "  raster_value_2: low severity BLB -> class_id 0",
                "  raster_value_3: high severity BLB -> class_id 0",
                "  raster_value_0: ignored/unlabeled",
                "  raster_value_1: ignored/others",
                "  raster_value_4: ignored/healthy",
                "notes: severity is recorded in metadata, not split into YOLO classes.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def metadata_fieldnames() -> list[str]:
    return [
        "image_name",
        "dataset_name",
        "source_dataset",
        "source_url",
        "source_type",
        "sensor_type",
        "is_multispectral",
        "channel_count",
        "split",
        "source_split",
        "original_image_path",
        "original_label_path",
        "original_label",
        "mapped_code",
        "category_type",
        "severity",
        "bbox_count",
        "bbox_area_pixels",
        "mask_values",
        "annotation_format",
        "annotation_source",
        "license",
        "notes",
    ]


def convert_candidate(item: Candidate, input_root: Path, output_root: Path) -> dict[str, Any]:
    pair = item.pair
    image = read_tif(pair.image_path)
    label = read_tif(pair.label_path)
    image_h, image_w, channel_count = image_hw_channels(image)
    label_h, label_w = int(label.shape[0]), int(label.shape[1])
    if image_h != label_h or image_w != label_w:
        raise ValueError(f"Image/label size mismatch for {pair.image_path}")

    image_name = f"blb_{pair.dataset}_{pair.split}_patch_{pair.patch_id}.jpg"
    label_name = f"blb_{pair.dataset}_{pair.split}_patch_{pair.patch_id}.txt"
    target_image = output_root / "images" / pair.split / image_name
    target_label = output_root / "labels" / pair.split / label_name

    Image.fromarray(multispectral_to_rgb(image), mode="RGB").save(target_image, quality=95)
    target_label.write_text(
        "\n".join(
            f"{box.class_id} {box.x_center:.6f} {box.y_center:.6f} {box.width:.6f} {box.height:.6f}"
            for box in item.boxes
        )
        + "\n",
        encoding="utf-8",
    )
    severities = sorted({box.severity for box in item.boxes})
    return {
        "image_name": image_name,
        "dataset_name": "BLB_UAV_Dataset",
        "source_dataset": pair.dataset,
        "source_url": SOURCE_URL,
        "source_type": "uav_multispectral",
        "sensor_type": "multispectral",
        "is_multispectral": "true",
        "channel_count": channel_count,
        "split": pair.split,
        "source_split": f"{pair.dataset}/{pair.split}",
        "original_image_path": str(pair.image_path.relative_to(input_root)),
        "original_label_path": str(pair.label_path.relative_to(input_root)),
        "original_label": "low/high bacterial leaf blight raster mask",
        "mapped_code": CLASS_CODE,
        "category_type": "disease",
        "severity": "|".join(severities),
        "bbox_count": len(item.boxes),
        "bbox_area_pixels": "|".join(str(box.area) for box in item.boxes),
        "mask_values": "|".join(str(v) for v in label_values(label)),
        "annotation_format": "raster_mask_connected_components_to_yolo_bbox",
        "annotation_source": "official BLB UAV raster label TIF",
        "license": "CC BY 4.0",
        "notes": "raster values 2 and 3 mapped to class_id 0; healthy/others/unlabeled ignored",
    }


def write_metadata(output_root: Path, rows: list[dict[str, Any]]) -> None:
    with (output_root / "metadata" / "image_metadata.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=metadata_fieldnames())
        writer.writeheader()
        writer.writerows(rows)


def execute_conversion(selected: list[Candidate], input_root: Path, output_root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    stats: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    clean_output(output_root)
    for item in selected:
        try:
            row = convert_candidate(item, input_root, output_root)
            rows.append(row)
            stats["images"] += 1
            stats["label_files"] += 1
            stats["objects"] += int(row["bbox_count"])
            stats[f"split_{item.pair.split}"] += 1
            stats[f"source_{item.pair.dataset}"] += 1
            for box in item.boxes:
                stats[f"severity_bbox_{box.severity}"] += 1
        except Exception as exc:  # noqa: BLE001 - keep converting the rest and report failures
            errors.append(
                {
                    "image": str(item.pair.image_path),
                    "label": str(item.pair.label_path),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            stats["conversion_errors"] += 1
    write_static_files(output_root)
    write_metadata(output_root, rows)
    return {"stats": dict(stats), "errors": errors, "metadata_rows": len(rows)}


def main() -> int:
    args = parse_args()
    input_root = resolve_path(args.input_root)
    output_root = resolve_path(args.output_root)
    mode = "execute" if args.execute else "dry-run"
    report: dict[str, Any] = {
        "boundary": "dataset expansion only; no training, no new weights, no precision/recall/mAP/F1",
        "mode": mode,
        "input_root": args.input_root,
        "output_root": args.output_root,
        "target_samples": args.target_samples,
        "seed": args.seed,
        "source_datasets": args.source_datasets,
        "balance_severity": bool(args.balance_severity),
        "class_map": {"0": CLASS_CODE},
        "ignored_raster_values": {"0": "unlabeled", "1": "others", "4": "healthy"},
        "severity_mapping": {"2": "low", "3": "high"},
        "missing_dependencies": runtime_missing(),
    }
    ensure_output(output_root)
    if report["missing_dependencies"]:
        report["status"] = "dependency_missing"
        (output_root / "conversion_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    if not input_root.exists():
        report["status"] = "input_root_missing"
        (output_root / "conversion_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    pairs = find_pairs(input_root, args.source_datasets)
    candidates, scan_report = scan_candidates(pairs, args.min_area_pixels)
    selected, selection_report = select_candidates(candidates, args.target_samples, args.seed, args.balance_severity)
    report["pair_count"] = len(pairs)
    report["positive_candidate_count"] = len(candidates)
    report["scan"] = scan_report
    report["selection"] = selection_report
    report["selected_preview"] = [
        {
            "source_dataset": item.pair.dataset,
            "source_split": item.pair.split,
            "patch_id": item.pair.patch_id,
            "severity": item.severity_key,
            "bbox_count": len(item.boxes),
        }
        for item in selected[:20]
    ]

    if not args.execute:
        write_static_files(output_root)
        write_metadata(output_root, [])
        report["status"] = "planned"
        (output_root / "conversion_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    conversion_report = execute_conversion(selected, input_root, output_root)
    report["conversion"] = conversion_report
    report["status"] = "converted" if conversion_report["metadata_rows"] == args.target_samples else "converted_with_shortfall"
    (output_root / "conversion_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if conversion_report["metadata_rows"] > 0 and not conversion_report["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
