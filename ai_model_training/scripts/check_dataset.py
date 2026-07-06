"""Check a YOLO dataset for the rice disease dual-model branch.

The checker is safe to run before training. It performs dataset validation only:
no training, no downloads, and no model metrics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional dependency
    Image = None

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency
    yaml = None


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
SPLITS = ("train", "val", "test")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check a YOLO dataset directory.")
    parser.add_argument("--dataset-root", required=True, help="Dataset root with images/, labels/, metadata/.")
    parser.add_argument("--data-yaml", help="Optional YOLO data.yaml path.")
    parser.add_argument("--class-count", type=int, help="Expected class count. Defaults to data.yaml nc.")
    parser.add_argument("--metadata", help="Optional image metadata CSV.")
    parser.add_argument("--output", help="Optional JSON report path.")
    parser.add_argument("--check-duplicates", action="store_true", help="Hash images to find duplicate files.")
    parser.add_argument(
        "--require-label-file",
        action="store_true",
        help="Require every image to have a label file. Empty labels are still counted as normal/negative samples.",
    )
    return parser.parse_args()


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required when --data-yaml is provided.")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def infer_class_count(data_yaml: Path | None, explicit_count: int | None) -> int:
    if explicit_count is not None:
        return explicit_count
    if data_yaml:
        data = load_yaml(data_yaml)
        if "nc" in data:
            return int(data["nc"])
        names = data.get("names")
        if isinstance(names, dict):
            return len(names)
        if isinstance(names, list):
            return len(names)
    raise ValueError("class count is required: pass --class-count or --data-yaml with nc/names.")


def list_images(image_dir: Path) -> list[Path]:
    if not image_dir.exists():
        return []
    return sorted(p for p in image_dir.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)


def read_label_file(label_path: Path, class_count: int) -> tuple[list[str], Counter[str]]:
    errors: list[str] = []
    stats: Counter[str] = Counter()
    if not label_path.exists():
        errors.append("missing_label_file")
        stats["missing_label_files"] += 1
        return errors, stats

    raw_text = label_path.read_text(encoding="utf-8").strip()
    if not raw_text:
        stats["empty_label_files"] += 1
        return errors, stats

    for line_no, line in enumerate(raw_text.splitlines(), start=1):
        parts = line.split()
        if len(parts) != 5:
            errors.append(f"line_{line_no}:invalid_yolo_field_count")
            continue
        try:
            class_id = int(parts[0])
        except ValueError:
            errors.append(f"line_{line_no}:class_id_not_integer")
            continue
        try:
            x_center, y_center, width, height = [float(v) for v in parts[1:]]
        except ValueError:
            errors.append(f"line_{line_no}:bbox_value_not_numeric")
            continue
        if class_id < 0 or class_id >= class_count:
            errors.append(f"line_{line_no}:class_id_out_of_range")
        coords = (x_center, y_center, width, height)
        if any(v < 0.0 or v > 1.0 for v in coords):
            errors.append(f"line_{line_no}:bbox_coordinate_out_of_range")
        if width <= 0.0 or height <= 0.0:
            errors.append(f"line_{line_no}:bbox_non_positive_size")
        stats["objects"] += 1
        stats[f"class_{class_id}"] += 1
    return errors, stats


def check_image_open(image_path: Path) -> str | None:
    if Image is None:
        return "pillow_not_installed_image_open_check_skipped"
    try:
        with Image.open(image_path) as img:
            img.verify()
    except Exception as exc:  # noqa: BLE001 - report data issue, do not crash
        return f"bad_image:{exc.__class__.__name__}"
    return None


def file_sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def metadata_image_key(row: dict[str, str]) -> str:
    for key in ("image_name", "file_name", "filename"):
        if row.get(key):
            return Path(row[key]).name
    for key in ("source_file", "image_path", "path"):
        if row.get(key):
            return Path(row[key]).name
    image_id = row.get("image_id", "")
    return Path(image_id).name


def check_metadata(metadata_path: Path, image_names: set[str], image_stems: set[str]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "rows": 0,
        "matched": 0,
        "missing_images": [],
        "source_dataset_distribution": {},
        "dataset_name_distribution": {},
        "split_distribution": {},
        "severity_distribution": {},
        "source_split_distribution": {},
    }
    if not metadata_path.exists():
        result["issue"] = "metadata_file_not_found"
        return result
    source_counts: Counter[str] = Counter()
    dataset_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    source_split_counts: Counter[str] = Counter()
    with metadata_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            result["rows"] += 1
            source_counts[row.get("source_dataset") or row.get("dataset_name") or "<missing>"] += 1
            dataset_counts[row.get("dataset_name") or "<missing>"] += 1
            split_counts[row.get("split") or "<missing>"] += 1
            severity_counts[row.get("severity") or "<missing>"] += 1
            source_split_counts[row.get("source_split") or "<missing>"] += 1
            key = metadata_image_key(row)
            if not key:
                result["missing_images"].append({"row": result["rows"], "reason": "no_image_key"})
                continue
            if key in image_names or Path(key).stem in image_stems:
                result["matched"] += 1
            else:
                result["missing_images"].append({"row": result["rows"], "image_key": key})
    result["source_dataset_distribution"] = dict(source_counts)
    result["dataset_name_distribution"] = dict(dataset_counts)
    result["split_distribution"] = dict(split_counts)
    result["severity_distribution"] = dict(severity_counts)
    result["source_split_distribution"] = dict(source_split_counts)
    return result


def main() -> int:
    args = parse_args()
    root = Path(args.dataset_root)
    data_yaml = Path(args.data_yaml) if args.data_yaml else None
    class_count = infer_class_count(data_yaml, args.class_count)

    report: dict[str, Any] = {
        "dataset_root": str(root),
        "data_yaml": str(data_yaml) if data_yaml else None,
        "class_count": class_count,
        "boundary": "dataset check only; no training, no downloads, no model metrics",
        "directories": {},
        "splits": {},
        "totals": {},
        "metadata": None,
        "issues": [],
    }
    issues: list[dict[str, str]] = []
    hashes: dict[str, list[str]] = defaultdict(list)
    all_image_names: set[str] = set()
    all_image_stems: set[str] = set()
    total_stats: Counter[str] = Counter()

    for split in SPLITS:
        image_dir = root / "images" / split
        label_dir = root / "labels" / split
        report["directories"][f"images/{split}"] = image_dir.exists()
        report["directories"][f"labels/{split}"] = label_dir.exists()
        if not image_dir.exists():
            issues.append({"split": split, "file": str(image_dir), "issue": "missing_images_split_dir"})
        if not label_dir.exists():
            issues.append({"split": split, "file": str(label_dir), "issue": "missing_labels_split_dir"})

        split_stats: Counter[str] = Counter()
        images = list_images(image_dir)
        image_stems = {p.stem for p in images}
        all_image_names.update(p.name for p in images)
        all_image_stems.update(image_stems)

        for image_path in images:
            split_stats["images"] += 1
            bad_image = check_image_open(image_path)
            if bad_image:
                issues.append({"split": split, "file": str(image_path), "issue": bad_image})
                split_stats["bad_images"] += 1
            if args.check_duplicates:
                hashes[file_sha1(image_path)].append(str(image_path))

            label_path = label_dir / f"{image_path.stem}.txt"
            label_errors, label_stats = read_label_file(label_path, class_count)
            split_stats.update(label_stats)
            if label_path.exists():
                split_stats["label_files"] += 1
            for error in label_errors:
                if error == "missing_label_file" and not args.require_label_file:
                    continue
                issues.append({"split": split, "file": str(image_path), "issue": error})

        if label_dir.exists():
            for label_path in label_dir.rglob("*.txt"):
                if label_path.stem not in image_stems:
                    issues.append({"split": split, "file": str(label_path), "issue": "orphan_label_without_image"})
                    split_stats["orphan_labels"] += 1
        report["splits"][split] = dict(split_stats)
        total_stats.update(split_stats)

    for group in [paths for paths in hashes.values() if len(paths) > 1]:
        issues.append({"split": "all", "file": " | ".join(group), "issue": "duplicate_image_hash"})
        total_stats["duplicate_image_groups"] += 1

    if args.metadata:
        report["metadata"] = check_metadata(Path(args.metadata), all_image_names, all_image_stems)
        if report["metadata"].get("missing_images"):
            issues.append({"split": "all", "file": args.metadata, "issue": "metadata_rows_reference_missing_images"})

    report["totals"] = dict(total_stats)
    report["class_distribution"] = {
        key.replace("class_", ""): value
        for key, value in sorted(total_stats.items())
        if key.startswith("class_")
    }
    report["split_distribution"] = {
        split: report["splits"].get(split, {}).get("images", 0)
        for split in SPLITS
    }
    report["source_dataset_distribution"] = (
        report["metadata"].get("source_dataset_distribution", {}) if report["metadata"] else {}
    )
    report["severity_distribution"] = report["metadata"].get("severity_distribution", {}) if report["metadata"] else {}
    report["source_split_distribution"] = (
        report["metadata"].get("source_split_distribution", {}) if report["metadata"] else {}
    )
    report["duplicate_count"] = total_stats.get("duplicate_image_groups", 0)
    report["orphan_label_count"] = total_stats.get("orphan_labels", 0)
    report["missing_label_count"] = total_stats.get("missing_label_files", 0)
    report["has_real_labeled_objects"] = total_stats.get("objects", 0) > 0
    report["empty_labels_allowed_and_counted"] = True
    report["issues"] = issues

    output_text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output_text + "\n", encoding="utf-8")
    print(output_text)
    return 0 if not issues else 2


if __name__ == "__main__":
    raise SystemExit(main())
