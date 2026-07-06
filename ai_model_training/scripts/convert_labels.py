"""Convert annotation files into YOLO labels.

LabelMe -> YOLO is implemented for smoke-test preparation. COCO/VOC entry
points are kept as explicit TODOs until real samples and category conventions
are confirmed.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency
    yaml = None


SUPPORTED_FORMATS = ("labelme", "coco", "voc")
RESERVED_LABELS = {"unknown", "uncertain", "normal", "正常", "不确定"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert annotations to YOLO format.")
    parser.add_argument("--input", required=True, help="Input annotation file or directory.")
    parser.add_argument("--format", required=True, choices=SUPPORTED_FORMATS)
    parser.add_argument("--class-map", required=True, help="class_map.yaml path.")
    parser.add_argument("--output-label-dir", required=True)
    parser.add_argument("--summary-json", help="Optional conversion summary JSON path.")
    parser.add_argument("--execute", action="store_true", help="Write converted labels. Default is dry-run.")
    return parser.parse_args()


def load_class_map(path: Path) -> dict[str, int]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to read class_map.yaml.")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    mapping: dict[str, int] = {}
    for item in data.get("classes", []):
        class_id = int(item["id"])
        for key in ("name", "zh_name"):
            value = item.get(key)
            if value:
                mapping[str(value)] = class_id
    if not mapping:
        raise ValueError(f"No classes found in {path}")
    for reserved in RESERVED_LABELS:
        mapping.pop(reserved, None)
    return mapping


def iter_labelme_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(input_path.rglob("*.json"))


def shape_to_bbox(shape: dict[str, Any]) -> tuple[float, float, float, float] | None:
    points = shape.get("points") or []
    if len(points) < 2:
        return None
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    if x_max <= x_min or y_max <= y_min:
        return None
    return x_min, y_min, x_max, y_max


def convert_labelme_file(path: Path, class_map: dict[str, int]) -> tuple[list[str], Counter[str], list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    image_width = data.get("imageWidth")
    image_height = data.get("imageHeight")
    if not image_width or not image_height:
        raise ValueError("LabelMe file missing imageWidth/imageHeight")

    lines: list[str] = []
    stats: Counter[str] = Counter()
    warnings: list[str] = []
    for shape in data.get("shapes", []):
        label = str(shape.get("label", "")).strip()
        if label in RESERVED_LABELS:
            stats["reserved_skipped"] += 1
            warnings.append(f"reserved_label_skipped:{label}")
            continue
        if label not in class_map:
            stats["unknown_skipped"] += 1
            warnings.append(f"unknown_label_skipped:{label}")
            continue
        bbox = shape_to_bbox(shape)
        if bbox is None:
            stats["invalid_shape_skipped"] += 1
            warnings.append(f"invalid_shape_skipped:{label}")
            continue
        x_min, y_min, x_max, y_max = bbox
        x_min = max(0.0, min(float(image_width), x_min))
        x_max = max(0.0, min(float(image_width), x_max))
        y_min = max(0.0, min(float(image_height), y_min))
        y_max = max(0.0, min(float(image_height), y_max))
        width = x_max - x_min
        height = y_max - y_min
        if width <= 0 or height <= 0:
            stats["invalid_shape_skipped"] += 1
            continue
        x_center = (x_min + x_max) / 2 / float(image_width)
        y_center = (y_min + y_max) / 2 / float(image_height)
        norm_w = width / float(image_width)
        norm_h = height / float(image_height)
        class_id = class_map[label]
        lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} {norm_w:.6f} {norm_h:.6f}")
        stats["converted_objects"] += 1
        stats[f"class_{class_id}"] += 1
    return lines, stats, warnings


def convert_labelme(input_path: Path, output_dir: Path, class_map: dict[str, int], execute: bool) -> dict[str, Any]:
    files = iter_labelme_files(input_path)
    summary: dict[str, Any] = {
        "format": "labelme",
        "dry_run": not execute,
        "total_files": len(files),
        "success_files": 0,
        "failed_files": 0,
        "skipped_files": 0,
        "class_distribution": {},
        "files": [],
    }
    class_counter: Counter[str] = Counter()
    for path in files:
        item: dict[str, Any] = {"input": str(path)}
        try:
            lines, stats, warnings = convert_labelme_file(path, class_map)
            class_counter.update({k: v for k, v in stats.items() if k.startswith("class_")})
            item["objects"] = len(lines)
            item["warnings"] = warnings
            if lines:
                summary["success_files"] += 1
                output_path = output_dir / f"{path.stem}.txt"
                item["output"] = str(output_path)
                if execute:
                    output_dir.mkdir(parents=True, exist_ok=True)
                    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            else:
                summary["skipped_files"] += 1
                item["reason"] = "no_trainable_objects_after_filtering"
        except Exception as exc:  # noqa: BLE001 - report conversion issue and continue
            summary["failed_files"] += 1
            item["error"] = f"{exc.__class__.__name__}: {exc}"
        summary["files"].append(item)
    summary["class_distribution"] = dict(class_counter)
    return summary


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_label_dir)
    class_map = load_class_map(Path(args.class_map))

    if args.format == "labelme":
        summary = convert_labelme(input_path, output_dir, class_map, args.execute)
    else:
        summary = {
            "format": args.format,
            "dry_run": not args.execute,
            "status": "TODO",
            "message": "COCO/VOC conversion is reserved until real annotation examples are reviewed.",
        }

    summary["boundary"] = "unknown/uncertain/normal labels are skipped and never written as training classes"
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.summary_json:
        Path(args.summary_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary_json).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if summary.get("failed_files", 0) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
