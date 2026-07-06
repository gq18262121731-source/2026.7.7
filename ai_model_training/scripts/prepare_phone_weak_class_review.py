"""Prepare weak-class review items and visual samples for RiceLeafDiseaseBD."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


WEAK_CLASSES = ("leaf_smut", "tungro", "sheath_blight")
CLASS_ID_TO_NAME = {
    0: "brown_spot",
    1: "rice_blast",
    2: "leaf_smut",
    3: "tungro",
    4: "sheath_blight",
}
CLASS_NAME_TO_ID = {name: class_id for class_id, name in CLASS_ID_TO_NAME.items()}
ISSUE_TYPES = [
    "ok",
    "wrong_class",
    "missing_box",
    "over_boxed",
    "under_boxed",
    "too_tiny",
    "ambiguous_symptom",
    "duplicate_or_near_duplicate",
    "image_quality_bad",
    "other",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare weak-class review items and previews without changing labels.")
    parser.add_argument("--dataset-root", default="datasets/rice_phone_rgb_expanded")
    parser.add_argument("--metadata", default="datasets/rice_phone_rgb_expanded/metadata/image_metadata.csv")
    parser.add_argument("--infer-report", default="reports/phone_riceleafdiseasebd_exp30_infer_result.json")
    parser.add_argument("--output-root", default="reports/weak_class_review")
    parser.add_argument("--items-per-class", type=int, default=100)
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    root = repo_root()
    if path.parts and path.parts[0] == "ai_model_training":
        return root.parent / path
    return root / path


def parse_label_file(label_path: Path) -> list[dict[str, Any]]:
    boxes: list[dict[str, Any]] = []
    raw_text = label_path.read_text(encoding="utf-8").strip()
    if not raw_text:
        return boxes
    for line in raw_text.splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        class_id = int(parts[0])
        x_center, y_center, width, height = [float(v) for v in parts[1:]]
        boxes.append(
            {
                "class_id": class_id,
                "class_name": CLASS_ID_TO_NAME.get(class_id, str(class_id)),
                "x_center": x_center,
                "y_center": y_center,
                "width": width,
                "height": height,
                "area": width * height,
            }
        )
    return boxes


def load_infer_map(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    report = json.loads(path.read_text(encoding="utf-8"))
    infer_map: dict[str, dict[str, Any]] = {}
    for item in report.get("results", []):
        detections = item.get("detections", [])
        confidences = [float(det["confidence"]) for det in detections if "confidence" in det]
        infer_map[item.get("image_name", "")] = {
            "zero_detection": len(detections) == 0,
            "low_conf_detection": bool(confidences) and max(confidences) < 0.40,
            "max_confidence": max(confidences) if confidences else None,
            "predicted_classes": sorted({det.get("class_name") for det in detections}),
            "prediction_count": len(detections),
        }
    return infer_map


def quota_by_split(items: list[dict[str, Any]], total: int) -> dict[str, int]:
    counts = Counter(item["split"] for item in items)
    ordered_splits = [split for split in ("train", "val", "test") if counts.get(split, 0) > 0]
    quotas: dict[str, int] = {}
    remaining = total
    for split in ordered_splits:
        min_target = min(10, counts[split], remaining)
        quotas[split] = min_target
        remaining -= min_target
    if remaining > 0:
        extras = {
            split: max(0, counts[split] - quotas.get(split, 0))
            for split in ordered_splits
        }
        total_extra = sum(extras.values())
        if total_extra > 0:
            for split in ordered_splits:
                if remaining <= 0:
                    break
                proportional = int(round(remaining * (extras[split] / total_extra))) if total_extra else 0
                add = min(extras[split], proportional)
                quotas[split] = quotas.get(split, 0) + add
            assigned = sum(quotas.values())
            while assigned < total:
                progressed = False
                for split in ordered_splits:
                    if quotas[split] < counts[split] and assigned < total:
                        quotas[split] += 1
                        assigned += 1
                        progressed = True
                if not progressed:
                    break
        else:
            assigned = sum(quotas.values())
            while assigned < total:
                progressed = False
                for split in ordered_splits:
                    if quotas[split] < counts[split] and assigned < total:
                        quotas[split] += 1
                        assigned += 1
                        progressed = True
                if not progressed:
                    break
    return quotas


def priority_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        0 if item["infer_zero_detection"] else 1,
        0 if item["infer_low_conf_detection"] else 1,
        0 if item["has_small_box"] else 1,
        0 if item["has_many_boxes"] else 1,
        item["median_bbox_area"],
        -item["bbox_count"],
        item["image_name"],
    )


def select_items(class_items: list[dict[str, Any]], total: int) -> list[dict[str, Any]]:
    quotas = quota_by_split(class_items, total)
    selected: list[dict[str, Any]] = []
    selected_names: set[str] = set()
    by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in sorted(class_items, key=priority_key):
        by_split[item["split"]].append(item)

    for split in ("train", "val", "test"):
        target = quotas.get(split, 0)
        if target <= 0:
            continue
        for item in by_split.get(split, []):
            if len([x for x in selected if x["split"] == split]) >= target:
                break
            if item["image_name"] in selected_names:
                continue
            selected.append(item)
            selected_names.add(item["image_name"])

    if len(selected) < total:
        for item in sorted(class_items, key=priority_key):
            if item["image_name"] in selected_names:
                continue
            selected.append(item)
            selected_names.add(item["image_name"])
            if len(selected) >= total:
                break
    return selected[:total]


def pick_selection_reason(item: dict[str, Any]) -> str:
    reasons: list[str] = []
    if item["infer_zero_detection"]:
        reasons.append("infer_zero_detection")
    elif item["infer_low_conf_detection"]:
        reasons.append("infer_low_conf_detection")
    if item["has_small_box"]:
        reasons.append("small_box")
    if item["has_many_boxes"]:
        reasons.append("many_boxes")
    if not reasons:
        reasons.append("split_balanced_fill")
    return "+".join(reasons)


def draw_preview(image_path: Path, label_path: Path, output_path: Path, class_name: str) -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    for box in parse_label_file(label_path):
        x_center = box["x_center"] * width
        y_center = box["y_center"] * height
        box_w = box["width"] * width
        box_h = box["height"] * height
        x0 = max(0, x_center - box_w / 2)
        y0 = max(0, y_center - box_h / 2)
        x1 = min(width, x_center + box_w / 2)
        y1 = min(height, y_center + box_h / 2)
        draw.rectangle((x0, y0, x1, y1), outline=(255, 64, 64), width=3)
    draw.rectangle((0, 0, min(width, 320), min(height, 42)), fill=(0, 0, 0))
    draw.text((10, 12), f"{class_name} | {image_path.name}", fill=(255, 255, 255))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, quality=95)


def build_item(row: dict[str, str], dataset_root: Path, infer_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    split = row["split"]
    image_name = row["image_name"]
    image_path = dataset_root / "images" / split / image_name
    label_path = dataset_root / "labels" / split / f"{Path(image_name).stem}.txt"
    boxes = parse_label_file(label_path)
    areas = [box["area"] for box in boxes]
    infer_info = infer_map.get(image_name, {})
    bbox_count = int(row.get("bbox_count") or len(boxes))
    small_box_threshold = 0.0001
    return {
        "class_name": row["mapped_code"],
        "split": split,
        "image_name": image_name,
        "image_path": str(image_path),
        "label_path": str(label_path),
        "source_original_path": row["original_image_path"],
        "bbox_count": bbox_count,
        "mean_bbox_area": statistics.mean(areas) if areas else 0.0,
        "median_bbox_area": statistics.median(areas) if areas else 0.0,
        "min_bbox_area": min(areas) if areas else 0.0,
        "has_small_box": any(area < small_box_threshold for area in areas),
        "has_many_boxes": bbox_count >= 20,
        "infer_zero_detection": bool(infer_info.get("zero_detection", False)),
        "infer_low_conf_detection": bool(infer_info.get("low_conf_detection", False)),
        "infer_max_confidence": infer_info.get("max_confidence"),
        "predicted_classes": ",".join(infer_info.get("predicted_classes", [])),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "review_id",
        "class_name",
        "split",
        "image_path",
        "label_path",
        "bbox_count",
        "mean_bbox_area",
        "median_bbox_area",
        "source_original_path",
        "review_status",
        "issue_type",
        "reviewer_notes",
        "selection_reason",
        "infer_zero_detection",
        "infer_low_conf_detection",
        "infer_max_confidence",
        "predicted_classes",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_guide(path: Path) -> None:
    content = f"""# Phone RiceLeafDiseaseBD Weak Class Review Guide

This package is review-only. Do not modify dataset labels directly in this round.

## Target weak classes

- `leaf_smut`
- `tungro`
- `sheath_blight`

## Reviewer workflow

1. Open the preview image and compare it with the source image path in the CSV.
2. Check whether the bbox count looks plausible.
3. Focus first on rows marked with:
   - `infer_zero_detection=true`
   - `infer_low_conf_detection=true`
   - `selection_reason` containing `small_box`
   - `selection_reason` containing `many_boxes`
4. Fill:
   - `review_status`
   - `issue_type`
   - `reviewer_notes`

## Allowed `issue_type`

{chr(10).join(f"- `{item}`" for item in ISSUE_TYPES)}

## Suggested `review_status`

- `pending`
- `reviewed`
- `needs_followup`

## Boundary

- no relabeling in this round
- no split changes in this round
- no training in this round
"""
    path.write_text(content, encoding="utf-8")


def write_index(path: Path, selected: list[dict[str, Any]], output_root: Path) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in selected:
        grouped[item["class_name"]].append(item)
    lines = [
        "# Phone RiceLeafDiseaseBD Weak Class Visual Samples",
        "",
        "These previews are for manual review only. They do not modify source images or labels.",
        "",
        f"- review csv: `{(output_root / 'phone_riceleafdiseasebd_weak_class_review_items.csv').as_posix()}`",
        "",
    ]
    for class_name in WEAK_CLASSES:
        items = grouped[class_name]
        lines.append(f"## {class_name}")
        lines.append("")
        lines.append(f"- selected images: `{len(items)}`")
        lines.append(f"- preview dir: `{(output_root / 'visual_samples' / class_name).as_posix()}`")
        lines.append("")
        lines.append("| # | split | image | reason | preview |")
        lines.append("| ---: | --- | --- | --- | --- |")
        for index, item in enumerate(items[:20], start=1):
            preview_name = Path(item["preview_path"]).name
            lines.append(
                f"| {index} | `{item['split']}` | `{item['image_name']}` | `{item['selection_reason']}` | "
                f"[preview]({class_name}/{preview_name}) |"
            )
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    dataset_root = resolve_path(args.dataset_root)
    metadata_path = resolve_path(args.metadata)
    infer_path = resolve_path(args.infer_report)
    output_root = resolve_path(args.output_root)
    infer_map = load_infer_map(infer_path)

    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with metadata_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            class_name = row.get("mapped_code", "")
            if class_name not in WEAK_CLASSES:
                continue
            by_class[class_name].append(build_item(row, dataset_root, infer_map))

    selected_rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"classes": {}, "total_selected": 0}
    for class_name in WEAK_CLASSES:
        picked = select_items(by_class[class_name], args.items_per_class)
        summary["classes"][class_name] = {
            "available": len(by_class[class_name]),
            "selected": len(picked),
            "split_distribution": dict(Counter(item["split"] for item in picked)),
        }
        for index, item in enumerate(picked, start=1):
            preview_path = output_root / "visual_samples" / class_name / f"{index:03d}_{item['split']}_{item['image_name']}"
            draw_preview(Path(item["image_path"]), Path(item["label_path"]), preview_path, class_name)
            item["preview_path"] = str(preview_path)
            item["selection_reason"] = pick_selection_reason(item)
            selected_rows.append(
                {
                    "review_id": f"{class_name}_{index:03d}",
                    "class_name": class_name,
                    "split": item["split"],
                    "image_path": item["image_path"],
                    "label_path": item["label_path"],
                    "bbox_count": item["bbox_count"],
                    "mean_bbox_area": f"{item['mean_bbox_area']:.10f}",
                    "median_bbox_area": f"{item['median_bbox_area']:.10f}",
                    "source_original_path": item["source_original_path"],
                    "review_status": "pending",
                    "issue_type": "",
                    "reviewer_notes": "",
                    "selection_reason": item["selection_reason"],
                    "infer_zero_detection": str(item["infer_zero_detection"]).lower(),
                    "infer_low_conf_detection": str(item["infer_low_conf_detection"]).lower(),
                    "infer_max_confidence": "" if item["infer_max_confidence"] is None else f"{item['infer_max_confidence']:.6f}",
                    "predicted_classes": item["predicted_classes"],
                    "preview_path": item["preview_path"],
                    "image_name": item["image_name"],
                }
            )
    summary["total_selected"] = len(selected_rows)

    csv_path = output_root / "phone_riceleafdiseasebd_weak_class_review_items.csv"
    write_csv(csv_path, selected_rows)
    write_guide(output_root / "phone_riceleafdiseasebd_weak_class_review_guide.md")
    write_index(output_root / "visual_samples" / "index.md", selected_rows, output_root)
    (output_root / "visual_samples" / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output_root": str(output_root), **summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
