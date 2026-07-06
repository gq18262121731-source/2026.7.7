from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter, defaultdict
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


DATASETS = ("D1", "D2", "D3")
SPLITS = ("train", "val", "test")
SPLIT_TARGET_RATIO = {"train": 0.7, "val": 0.2, "test": 0.1}

IGNORE_VALUES = {0, 1, 4}
BLB_VALUE_TO_SEVERITY = {2: "low", 3: "high"}


@dataclass(frozen=True)
class Pair:
    dataset: str
    split: str
    image_path: Path
    label_path: Path
    patch_id: str


@dataclass
class ComponentBox:
    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float
    area: int
    severity: str
    raster_value: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert official BLB UAV raster masks to YOLO bbox preview data.")
    parser.add_argument("--input-root", default="raw_datasets/blb_uav_dataset/original")
    parser.add_argument("--output-root", default="datasets/rice_uav_ms_blb_preview")
    parser.add_argument("--class-code", default="bacterial_leaf_blight")
    parser.add_argument("--max-samples", type=int, default=50)
    parser.add_argument("--min-area-pixels", type=int, default=25)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root() / path


def require_runtime() -> list[str]:
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
        raise RuntimeError("tifffile is required to read BLB UAV TIF/raster files.")
    return np.asarray(tifffile.imread(path))


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
        # Notebook comments identify B1/B2/B3 as Blue/Green/Red, so reverse them for RGB preview.
        rgb = np.stack([hwc[:, :, 2], hwc[:, :, 1], hwc[:, :, 0]], axis=-1)
    elif channels == 2:
        rgb = np.stack([hwc[:, :, 1], hwc[:, :, 0], hwc[:, :, 0]], axis=-1)
    else:
        rgb = np.repeat(hwc[:, :, :1], 3, axis=2)
    return np.stack([normalize_band(rgb[:, :, i]) for i in range(3)], axis=-1)


def clean_output_root(output_root: Path) -> None:
    if output_root.exists():
        shutil.rmtree(output_root)
    for split in SPLITS:
        (output_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_root / "labels" / split).mkdir(parents=True, exist_ok=True)
    (output_root / "metadata").mkdir(parents=True, exist_ok=True)


def ensure_output_dirs(output_root: Path) -> None:
    for split in SPLITS:
        (output_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_root / "labels" / split).mkdir(parents=True, exist_ok=True)
    (output_root / "metadata").mkdir(parents=True, exist_ok=True)


def find_pairs(input_root: Path) -> list[Pair]:
    pairs: list[Pair] = []
    for dataset in DATASETS:
        for split in SPLITS:
            image_dir = input_root / dataset / split
            label_dir = input_root / dataset / f"{split}_labels"
            if not image_dir.exists() or not label_dir.exists():
                continue
            for image_path in sorted(image_dir.glob("image_patch_*.tif")):
                patch_id = image_path.stem.replace("image_patch_", "")
                label_path = label_dir / f"label_patch_{patch_id}.tif"
                if label_path.exists():
                    pairs.append(Pair(dataset, split, image_path, label_path, patch_id))
    return pairs


def label_values(label: np.ndarray) -> list[int]:
    return sorted({int(v) for v in np.unique(label).tolist()})


def components_from_label(label: np.ndarray, min_area_pixels: int) -> list[ComponentBox]:
    if ndimage is None:
        raise RuntimeError("scipy is required for connected-component bbox extraction.")
    if label.ndim > 2:
        label = label[:, :, 0]
    height, width = label.shape[:2]
    boxes: list[ComponentBox] = []
    for raster_value, severity in BLB_VALUE_TO_SEVERITY.items():
        disease_mask = np.asarray(label == raster_value)
        labeled, count = ndimage.label(disease_mask)
        for component_id in range(1, count + 1):
            ys, xs = np.where(labeled == component_id)
            area = int(xs.size)
            if area < min_area_pixels:
                continue
            x1, x2 = int(xs.min()), int(xs.max())
            y1, y2 = int(ys.min()), int(ys.max())
            box_width = x2 - x1 + 1
            box_height = y2 - y1 + 1
            boxes.append(
                ComponentBox(
                    class_id=0,
                    x_center=((x1 + x2 + 1) / 2) / width,
                    y_center=((y1 + y2 + 1) / 2) / height,
                    width=box_width / width,
                    height=box_height / height,
                    area=area,
                    severity=severity,
                    raster_value=raster_value,
                )
            )
    return boxes


def pair_audit(pair: Pair) -> dict[str, Any]:
    image = read_tif(pair.image_path)
    label = read_tif(pair.label_path)
    image_h, image_w, channels = image_hw_channels(image)
    label_h, label_w = int(label.shape[0]), int(label.shape[1])
    values = label_values(label)
    boxes = components_from_label(label, min_area_pixels=25)
    return {
        "dataset": pair.dataset,
        "split": pair.split,
        "patch_id": pair.patch_id,
        "image_path": str(pair.image_path),
        "label_path": str(pair.label_path),
        "image_shape": list(image.shape),
        "label_shape": list(label.shape),
        "image_height": image_h,
        "image_width": image_w,
        "label_height": label_h,
        "label_width": label_w,
        "channels": channels,
        "image_dtype": str(image.dtype),
        "label_dtype": str(label.dtype),
        "mask_values": values,
        "contains_low_value_2": 2 in values,
        "contains_high_value_3": 3 in values,
        "size_match": image_h == label_h and image_w == label_w,
        "connected_components_for_2_or_3": len(boxes),
        "largest_component_area": max((box.area for box in boxes), default=0),
        "can_generate_bbox": bool(boxes),
    }


def summarize_structure(input_root: Path, pairs: list[Pair]) -> dict[str, Any]:
    split_counts: dict[str, Any] = {}
    for dataset in DATASETS:
        split_counts[dataset] = {}
        for split in SPLITS:
            image_dir = input_root / dataset / split
            label_dir = input_root / dataset / f"{split}_labels"
            split_counts[dataset][split] = {
                "images_dir_exists": image_dir.exists(),
                "labels_dir_exists": label_dir.exists(),
                "images": len(list(image_dir.glob("*.tif"))) if image_dir.exists() else 0,
                "labels": len(list(label_dir.glob("*.tif"))) if label_dir.exists() else 0,
            }
    files = [p for p in input_root.rglob("*") if p.is_file()]
    ext_counts = Counter(p.suffix.lower() or "<none>" for p in files)
    return {
        "input_root": str(input_root),
        "datasets_exist": {dataset: (input_root / dataset).exists() for dataset in DATASETS},
        "split_counts": split_counts,
        "total_files": len(files),
        "extension_counts": dict(sorted(ext_counts.items())),
        "paired_image_label_count": len(pairs),
        "zip_count": ext_counts.get(".zip", 0),
        "csv_count": ext_counts.get(".csv", 0),
        "notebook_count": ext_counts.get(".ipynb", 0),
    }


def select_preview_pairs(pairs: list[Pair], max_samples: int, min_area_pixels: int) -> tuple[list[Pair], dict[str, Any]]:
    positives_by_split_dataset: dict[str, dict[str, list[Pair]]] = {
        split: {dataset: [] for dataset in DATASETS} for split in SPLITS
    }
    scanned = 0
    skipped_no_blb = 0
    skipped_unreadable = 0
    for pair in pairs:
        scanned += 1
        try:
            label = read_tif(pair.label_path)
            boxes = components_from_label(label, min_area_pixels)
        except Exception:
            skipped_unreadable += 1
            continue
        if boxes:
            positives_by_split_dataset[pair.split][pair.dataset].append(pair)
        else:
            skipped_no_blb += 1

    targets = {
        split: int(round(max_samples * SPLIT_TARGET_RATIO[split]))
        for split in SPLITS
    }
    targets["train"] += max_samples - sum(targets.values())

    selected: list[Pair] = []
    for split in SPLITS:
        selected.extend(round_robin_take(positives_by_split_dataset[split], targets[split]))

    if len(selected) < max_samples:
        already = {(p.dataset, p.split, p.patch_id) for p in selected}
        leftovers = [
            p
            for split in SPLITS
            for dataset in DATASETS
            for p in positives_by_split_dataset[split][dataset]
            if (p.dataset, p.split, p.patch_id) not in already
        ]
        selected.extend(leftovers[: max_samples - len(selected)])

    return selected[:max_samples], {
        "pairs_scanned": scanned,
        "positive_pairs_by_split": {
            split: sum(len(positives_by_split_dataset[split][dataset]) for dataset in DATASETS)
            for split in SPLITS
        },
        "positive_pairs_by_dataset": {
            dataset: sum(len(positives_by_split_dataset[split][dataset]) for split in SPLITS)
            for dataset in DATASETS
        },
        "selected_by_split": dict(Counter(p.split for p in selected)),
        "selected_by_dataset": dict(Counter(p.dataset for p in selected)),
        "skipped_no_blb": skipped_no_blb,
        "skipped_unreadable": skipped_unreadable,
    }


def round_robin_take(groups: dict[str, list[Pair]], limit: int) -> list[Pair]:
    selected: list[Pair] = []
    offsets = {dataset: 0 for dataset in DATASETS}
    while len(selected) < limit:
        progressed = False
        for dataset in DATASETS:
            offset = offsets[dataset]
            values = groups[dataset]
            if offset >= len(values):
                continue
            selected.append(values[offset])
            offsets[dataset] += 1
            progressed = True
            if len(selected) >= limit:
                break
        if not progressed:
            break
    return selected


def write_static_dataset_files(output_root: Path, class_code: str) -> None:
    (output_root / "data.yaml").write_text(
        "\n".join(
            [
                "path: datasets/rice_uav_ms_blb_preview",
                "train: images/train",
                "val: images/val",
                "test: images/test",
                "nc: 1",
                "names:",
                f"  0: {class_code}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (output_root / "metadata" / "class_map.yaml").write_text(
        "\n".join(
            [
                "version: rice_uav_ms_blb_preview_v1",
                "model_name: uav_rice_disease_yolo",
                "source_dataset: BLB_UAV_Dataset",
                "source_url: https://figshare.com/articles/dataset/BLB_UAV_Dataset/26955862",
                "license: CC BY 4.0",
                "category_type: disease",
                "source_type: uav_multispectral",
                "sensor_type: multispectral",
                "classes:",
                f"  0: {class_code}",
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
        "notes",
    ]


def convert_pair(pair: Pair, output_root: Path, input_root: Path, class_code: str, min_area_pixels: int) -> dict[str, Any]:
    image = read_tif(pair.image_path)
    label = read_tif(pair.label_path)
    image_h, image_w, channel_count = image_hw_channels(image)
    label_h, label_w = int(label.shape[0]), int(label.shape[1])
    if image_h != label_h or image_w != label_w:
        raise ValueError(f"Image/label size mismatch: {pair.image_path} vs {pair.label_path}")
    boxes = components_from_label(label, min_area_pixels)
    if not boxes:
        raise ValueError(f"No BLB components after filtering: {pair.label_path}")

    image_name = f"blb_{pair.dataset}_{pair.split}_patch_{pair.patch_id}.jpg"
    label_name = f"blb_{pair.dataset}_{pair.split}_patch_{pair.patch_id}.txt"
    target_image = output_root / "images" / pair.split / image_name
    target_label = output_root / "labels" / pair.split / label_name

    rgb = multispectral_to_rgb(image)
    Image.fromarray(rgb, mode="RGB").save(target_image, quality=95)
    target_label.write_text(
        "\n".join(
            f"{box.class_id} {box.x_center:.6f} {box.y_center:.6f} {box.width:.6f} {box.height:.6f}"
            for box in boxes
        )
        + "\n",
        encoding="utf-8",
    )
    severities = sorted({box.severity for box in boxes})
    return {
        "image_name": image_name,
        "dataset_name": "BLB_UAV_Dataset",
        "source_dataset": "BLB_UAV_Dataset",
        "source_url": "https://figshare.com/articles/dataset/BLB_UAV_Dataset/26955862",
        "source_type": "uav_multispectral",
        "sensor_type": "multispectral",
        "is_multispectral": "true",
        "channel_count": channel_count,
        "split": pair.split,
        "source_split": f"{pair.dataset}/{pair.split}",
        "original_image_path": str(pair.image_path.relative_to(input_root)),
        "original_label_path": str(pair.label_path.relative_to(input_root)),
        "original_label": "low/high bacterial leaf blight raster mask",
        "mapped_code": class_code,
        "category_type": "disease",
        "severity": "|".join(severities),
        "bbox_count": len(boxes),
        "bbox_area_pixels": "|".join(str(box.area) for box in boxes),
        "mask_values": "|".join(str(v) for v in label_values(label)),
        "annotation_format": "raster_mask_connected_components_to_yolo_bbox",
        "notes": "raster values 2 and 3 mapped to class_id 0; healthy/others/unlabeled ignored",
    }


def write_metadata(output_root: Path, rows: list[dict[str, Any]]) -> None:
    with (output_root / "metadata" / "image_metadata.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=metadata_fieldnames())
        writer.writeheader()
        writer.writerows(rows)


def write_structure_report(input_root: Path, structure: dict[str, Any], sample_audit: dict[str, Any]) -> None:
    split_lines: list[str] = []
    for dataset in DATASETS:
        for split in SPLITS:
            data = structure["split_counts"][dataset][split]
            split_lines.append(
                f"| {dataset} | {split} | {data['images_dir_exists']} | {data['labels_dir_exists']} | "
                f"{data['images']} | {data['labels']} |"
            )
    text = "\n".join(
        [
            "# BLB UAV Structure Report",
            "",
            "Generated at: 2026-06-23 Asia/Shanghai",
            "",
            "## Summary",
            "",
            "- Input root: `raw_datasets/blb_uav_dataset/original`",
            f"- D1/D2/D3 exist: `{structure['datasets_exist']}`",
            f"- Total paired image/label TIF files: `{structure['paired_image_label_count']}`",
            f"- Total files: `{structure['total_files']}`",
            f"- Extension counts: `{structure['extension_counts']}`",
            "- Original zip files were kept in place; extracted D1/D2/D3 directories are present.",
            "",
            "## Split Counts",
            "",
            "| Dataset | Split | Images dir | Labels dir | Image TIFs | Label TIFs |",
            "|---|---|---:|---:|---:|---:|",
            *split_lines,
            "",
            "## Label Semantics",
            "",
            "- 0 Unlabeled: ignored",
            "- 1 Others: ignored",
            "- 2 Low-severity: mapped to class_id 0 `bacterial_leaf_blight`; severity metadata is `low`",
            "- 3 High-severity: mapped to class_id 0 `bacterial_leaf_blight`; severity metadata is `high`",
            "- 4 Healthy: ignored",
            "",
            "## Sample Audit",
            "",
            f"- Sample count: `{sample_audit.get('sample_count', 0)}`",
            "- Images are 256x256 multispectral TIFs. D1 samples observed with 5 channels; D2/D3 samples observed with 6 channels.",
            "- Labels are 256x256 single-channel raster TIFs.",
            "- Image/label naming pairs use `image_patch_<id>.tif` and `label_patch_<id>.tif`.",
            "- BBox generation is feasible where label values 2 or 3 are present.",
            "",
        ]
    )
    (input_root.parent / "blb_uav_structure_report.md").write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_root = resolve_path(args.input_root)
    output_root = resolve_path(args.output_root)
    missing = require_runtime()

    report: dict[str, Any] = {
        "boundary": "no training, no new weights, no precision/recall/mAP/F1",
        "input_root": args.input_root,
        "output_root": args.output_root,
        "class_code": args.class_code,
        "max_samples": args.max_samples,
        "min_area_pixels": args.min_area_pixels,
        "mode": "execute" if args.execute else "dry-run",
        "missing_dependencies": missing,
    }
    output_root.mkdir(parents=True, exist_ok=True)

    if missing:
        report["status"] = "dependency_missing"
        report["cannot_convert"] = True
        (output_root / "conversion_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    if not input_root.exists():
        report["status"] = "input_root_missing"
        report["cannot_convert"] = True
        (output_root / "conversion_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    pairs = find_pairs(input_root)
    structure = summarize_structure(input_root, pairs)
    sample_pairs: list[Pair] = []
    for dataset in DATASETS:
        for split in SPLITS:
            sample_pairs.extend([p for p in pairs if p.dataset == dataset and p.split == split][0:1])
    positive_samples, _ = select_preview_pairs(pairs, max_samples=3, min_area_pixels=args.min_area_pixels)
    sample_pairs.extend(positive_samples)
    sample_pairs = list(dict.fromkeys(sample_pairs))[:10]
    sample_audit = {"sample_count": len(sample_pairs), "samples": [pair_audit(pair) for pair in sample_pairs]}
    (input_root.parent / "blb_uav_sample_audit.json").write_text(
        json.dumps(sample_audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_structure_report(input_root, structure, sample_audit)

    selected, selection_stats = select_preview_pairs(pairs, args.max_samples, args.min_area_pixels)
    report["structure"] = structure
    report["selection"] = selection_stats
    report["selected_count"] = len(selected)
    report["selected_preview"] = [
        {
            "dataset": pair.dataset,
            "split": pair.split,
            "patch_id": pair.patch_id,
            "image": str(pair.image_path.relative_to(input_root)),
            "label": str(pair.label_path.relative_to(input_root)),
        }
        for pair in selected[:10]
    ]

    if not args.execute:
        ensure_output_dirs(output_root)
        write_static_dataset_files(output_root, args.class_code)
        write_metadata(output_root, [])
        (output_root / "conversion_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    clean_output_root(output_root)
    rows: list[dict[str, Any]] = []
    stats: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    for pair in selected:
        try:
            row = convert_pair(pair, output_root, input_root, args.class_code, args.min_area_pixels)
            rows.append(row)
            stats["images"] += 1
            stats["label_files"] += 1
            stats["objects"] += int(row["bbox_count"])
            stats[f"{pair.split}_images"] += 1
            stats[f"{pair.dataset}_images"] += 1
            for severity in str(row["severity"]).split("|"):
                if severity:
                    stats[f"severity_{severity}"] += 1
        except Exception as exc:  # noqa: BLE001 - report bad source sample, continue preview
            errors.append({"image": str(pair.image_path), "label": str(pair.label_path), "error": f"{type(exc).__name__}: {exc}"})
            stats["conversion_errors"] += 1

    write_static_dataset_files(output_root, args.class_code)
    write_metadata(output_root, rows)
    report["conversion"] = {"stats": dict(stats), "errors": errors, "metadata_rows": len(rows)}
    report["status"] = "converted" if rows else "no_rows_converted"
    (output_root / "conversion_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if rows else 2


if __name__ == "__main__":
    raise SystemExit(main())
