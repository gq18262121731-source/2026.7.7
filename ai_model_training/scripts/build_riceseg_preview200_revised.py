from __future__ import annotations

import argparse
import csv
import json
import math
import random
import shutil
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont


DEFAULT_CLASSES = ["bacterial_blight", "blast", "brown_spot", "tungro"]
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
SEVERE_ISSUES = {"whole_leaf_box", "irrelevant_box", "image_mask_mismatch", "box_misaligned"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build revised RiceSeg preview_200 dataset and review artifacts.")
    parser.add_argument(
        "--source-manifest",
        default="datasets/rice_phone_rgb_riceseg_preview_200/metadata/conversion_manifest.csv",
    )
    parser.add_argument(
        "--source-data-yaml",
        default="datasets/rice_phone_rgb_riceseg_preview_200/data.yaml",
    )
    parser.add_argument(
        "--source-class-map",
        default="datasets/rice_phone_rgb_riceseg_preview_200/metadata/class_map.yaml",
    )
    parser.add_argument(
        "--review-items-csv",
        default="reports/riceseg_preview_200_manual_review_items.csv",
    )
    parser.add_argument(
        "--review-decisions-csv",
        default="reports/riceseg_preview_200_manual_review_decisions.csv",
    )
    parser.add_argument(
        "--review-summary-json",
        default="reports/riceseg_preview_200_manual_review_summary.json",
    )
    parser.add_argument(
        "--review-gate-report",
        default="reports/riceseg_preview_200_manual_review_gate_report.md",
    )
    parser.add_argument(
        "--rules-config",
        default="configs/riceseg_mask_to_bbox_revised_v0_1.yaml",
    )
    parser.add_argument(
        "--output-dataset",
        default="datasets/rice_phone_rgb_riceseg_preview_200_revised_v0_1",
    )
    parser.add_argument(
        "--output-visual-audit",
        default="reports/riceseg_preview_200_revised_v0_1_visual_audit",
    )
    parser.add_argument(
        "--output-review-items-csv",
        default="reports/riceseg_preview_200_revised_v0_1_manual_review_items.csv",
    )
    parser.add_argument(
        "--output-review-items-json",
        default="reports/riceseg_preview_200_revised_v0_1_manual_review_items.json",
    )
    parser.add_argument(
        "--output-before-after-csv",
        default="reports/riceseg_preview_200_revised_v0_1_before_after_comparison.csv",
    )
    parser.add_argument(
        "--output-before-after-json",
        default="reports/riceseg_preview_200_revised_v0_1_before_after_comparison.json",
    )
    parser.add_argument(
        "--output-issue-analysis-json",
        default="reports/riceseg_preview_200_issue_pattern_analysis.json",
    )
    parser.add_argument(
        "--output-issue-analysis-md",
        default="reports/riceseg_preview_200_issue_pattern_analysis.md",
    )
    parser.add_argument(
        "--output-conversion-report-json",
        default="reports/riceseg_preview_200_revised_v0_1_conversion_report.json",
    )
    parser.add_argument(
        "--output-conversion-report-md",
        default="reports/riceseg_preview_200_revised_v0_1_conversion_report.md",
    )
    parser.add_argument(
        "--output-quality-summary-md",
        default="reports/riceseg_preview_200_revised_v0_1_conversion_quality_summary.md",
    )
    parser.add_argument(
        "--output-dataset-check-md",
        default="reports/riceseg_preview_200_revised_v0_1_dataset_check.md",
    )
    parser.add_argument(
        "--review-bat",
        default="reports/riceseg_preview_200_revised_v0_1_start_review_desktop.bat",
    )
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root() / path


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def class_id_map_from_data_yaml(path: Path) -> dict[str, int]:
    data = load_yaml(path)
    names = data.get("names", {})
    if isinstance(names, list):
        return {name: index for index, name in enumerate(names)}
    return {str(name): int(index) for index, name in names.items()}


def normalize_review_seed_items(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        normalized.append(
            {
                "review_id": row["review_id"],
                "class_name": row["class_name"],
                "split": row["split"],
                "image_path": row["image_path"],
                "label_path": row["label_path"],
                "visual_preview_path": row["visual_preview_path"],
                "bbox_count": int(float(row.get("bbox_count") or 0)),
                "selection_reason": row.get("selection_reason", ""),
            }
        )
    return normalized


def analyze_review_results(
    decision_rows: list[dict[str, str]],
    summary_payload: dict[str, Any],
    gate_report_path: Path,
) -> tuple[dict[str, Any], str]:
    reviewed = [row for row in decision_rows if row.get("review_status") == "reviewed"]
    issue_rows = [row for row in reviewed if row.get("issue_type") and row.get("issue_type") != "ok"]
    issue_by_class = Counter(row["class_name"] for row in issue_rows)
    issue_by_split = Counter(row["split"] for row in issue_rows)
    issue_by_type = Counter(row["issue_type"] for row in issue_rows)
    mask_noise_bbox_counts = [
        int(float(row.get("bbox_count") or 0))
        for row in issue_rows
        if row.get("issue_type") == "mask_noise"
    ]
    over_fragmented_bbox_counts = [
        int(float(row.get("bbox_count") or 0))
        for row in issue_rows
        if row.get("issue_type") == "over_fragmented"
    ]
    review_issue_ids = [row["review_id"] for row in issue_rows]
    analysis = {
        "source_summary": summary_payload,
        "gate_report_path": str(gate_report_path),
        "issue_count": len(issue_rows),
        "issue_ids": review_issue_ids,
        "issue_rows": [
            {
                "review_id": row["review_id"],
                "class_name": row["class_name"],
                "split": row["split"],
                "bbox_count": int(float(row.get("bbox_count") or 0)),
                "issue_type": row.get("issue_type", ""),
                "reviewer_notes": row.get("reviewer_notes", ""),
                "image_path": row.get("image_path", ""),
                "label_path": row.get("label_path", ""),
                "visual_preview_path": row.get("visual_preview_path", ""),
            }
            for row in issue_rows
        ],
        "issue_by_class": dict(issue_by_class),
        "issue_by_split": dict(issue_by_split),
        "issue_by_type": dict(issue_by_type),
        "mask_noise_bbox_counts": mask_noise_bbox_counts,
        "over_fragmented_bbox_counts": over_fragmented_bbox_counts,
        "dominant_problem_classes": [
            name for name, _count in issue_by_class.most_common()
        ],
        "conclusions": {
            "is_mainly_bacterial_blight": issue_by_class.get("bacterial_blight", 0) >= 1,
            "is_mainly_tungro": issue_by_class.get("tungro", 0) >= 1,
            "split_related_pattern": dict(issue_by_split),
            "bbox_count_related_pattern": {
                "mask_noise_mean_bbox_count": round(sum(mask_noise_bbox_counts) / len(mask_noise_bbox_counts), 3)
                if mask_noise_bbox_counts
                else None,
                "over_fragmented_mean_bbox_count": round(
                    sum(over_fragmented_bbox_counts) / len(over_fragmented_bbox_counts),
                    3,
                )
                if over_fragmented_bbox_counts
                else None,
            },
            "needs_class_specific_thresholds": True,
            "needs_component_merge_rule": True,
        },
        "recommendation": (
            "Keep blast and brown_spot on the original conservative rule; "
            "tighten bacterial_blight and tungro with morphology + higher component "
            "filtering + nearby-box merge, then rebuild the same 200-image lineage."
        ),
    }
    md_lines = [
        "# RiceSeg preview_200 Issue Pattern Analysis",
        "",
        f"- review_gate: `{summary_payload.get('gate')}`",
        f"- total_review_items: `{summary_payload.get('total_review_items')}`",
        f"- reviewed_count: `{summary_payload.get('reviewed_count')}`",
        f"- obvious_error_count: `{summary_payload.get('obvious_error_count')}`",
        f"- obvious_error_ratio: `{summary_payload.get('obvious_error_ratio')}`",
        "",
        "## Issue Concentration",
        "",
    ]
    for name, count in issue_by_class.items():
        md_lines.append(f"- `{name}`: `{count}`")
    md_lines += [
        "",
        "## Issue Type Counts",
        "",
    ]
    for name, count in issue_by_type.items():
        md_lines.append(f"- `{name}`: `{count}`")
    md_lines += [
        "",
        "## Split Distribution",
        "",
    ]
    for name, count in issue_by_split.items():
        md_lines.append(f"- `{name}`: `{count}`")
    md_lines += [
        "",
        "## BBox Count Clues",
        "",
        f"- `mask_noise_bbox_counts`: `{mask_noise_bbox_counts}`",
        f"- `over_fragmented_bbox_counts`: `{over_fragmented_bbox_counts}`",
        "",
        "## Recommendation",
        "",
        analysis["recommendation"],
        "",
    ]
    return analysis, "\n".join(md_lines) + "\n"


def binary_morphology(mask: Image.Image, open_kernel: int, close_kernel: int) -> Any:
    out = mask.convert("L").point(lambda p: 255 if p > 0 else 0)
    if open_kernel and open_kernel > 1:
        out = out.filter(ImageFilter.MinFilter(open_kernel)).filter(ImageFilter.MaxFilter(open_kernel))
    if close_kernel and close_kernel > 1:
        out = out.filter(ImageFilter.MaxFilter(close_kernel)).filter(ImageFilter.MinFilter(close_kernel))
    return out


def connected_components(mask: Image.Image) -> list[dict[str, int]]:
    gray = mask.convert("L")
    width, height = gray.size
    pixels = gray.load()
    visited = set()
    components = []
    for y in range(height):
        for x in range(width):
            if pixels[x, y] == 0 or (x, y) in visited:
                continue
            queue = deque([(x, y)])
            visited.add((x, y))
            min_x = max_x = x
            min_y = max_y = y
            area = 0
            while queue:
                cx, cy = queue.popleft()
                area += 1
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height or (nx, ny) in visited:
                        continue
                    if pixels[nx, ny] > 0:
                        visited.add((nx, ny))
                        queue.append((nx, ny))
            components.append(
                {
                    "x1": min_x,
                    "y1": min_y,
                    "x2": max_x + 1,
                    "y2": max_y + 1,
                    "area": area,
                    "width": max_x - min_x + 1,
                    "height": max_y - min_y + 1,
                }
            )
    return components


def boxes_are_close(a: dict[str, int], b: dict[str, int], distance: int) -> bool:
    gap_x = max(0, max(b["x1"] - a["x2"], a["x1"] - b["x2"]))
    gap_y = max(0, max(b["y1"] - a["y2"], a["y1"] - b["y2"]))
    return gap_x <= distance and gap_y <= distance


def merge_boxes(boxes: list[dict[str, int]], distance: int) -> tuple[list[dict[str, int]], int]:
    remaining = [dict(box) for box in boxes]
    merged_boxes = []
    merge_count = 0
    while remaining:
        current = remaining.pop(0)
        changed = True
        while changed:
            changed = False
            next_remaining = []
            for candidate in remaining:
                if boxes_are_close(current, candidate, distance):
                    current = {
                        "x1": min(current["x1"], candidate["x1"]),
                        "y1": min(current["y1"], candidate["y1"]),
                        "x2": max(current["x2"], candidate["x2"]),
                        "y2": max(current["y2"], candidate["y2"]),
                        "area": current["area"] + candidate["area"],
                        "width": max(current["x2"], candidate["x2"]) - min(current["x1"], candidate["x1"]),
                        "height": max(current["y2"], candidate["y2"]) - min(current["y1"], candidate["y1"]),
                    }
                    merge_count += 1
                    changed = True
                else:
                    next_remaining.append(candidate)
            remaining = next_remaining
        current["width"] = current["x2"] - current["x1"]
        current["height"] = current["y2"] - current["y1"]
        merged_boxes.append(current)
    return merged_boxes, merge_count


def yolo_line(class_id: int, box: dict[str, int], image_size: tuple[int, int]) -> str:
    width, height = image_size
    x_center = ((box["x1"] + box["x2"]) / 2) / width
    y_center = ((box["y1"] + box["y2"]) / 2) / height
    box_width = (box["x2"] - box["x1"]) / width
    box_height = (box["y2"] - box["y1"]) / height
    return f"{class_id} {x_center:.6f} {y_center:.6f} {box_width:.6f} {box_height:.6f}"


def to_relative(path: Path, base: Path) -> str:
    return str(path.resolve().relative_to(base.resolve()))


def sanitize_for_preview_name(value: str) -> str:
    cleaned = []
    for ch in value:
        cleaned.append(ch if ch.isalnum() or ch in {"_", "-"} else "_")
    return "".join(cleaned)


def render_preview(image_path: Path, label_path: Path, output_path: Path, class_names: dict[int, str]) -> int:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    width, height = image.size
    bbox_count = 0
    if label_path.exists():
        for line in label_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            class_id_str, x_str, y_str, w_str, h_str = line.split()
            class_id = int(class_id_str)
            x = float(x_str)
            y = float(y_str)
            w = float(w_str)
            h = float(h_str)
            x1 = (x - w / 2) * width
            y1 = (y - h / 2) * height
            x2 = (x + w / 2) * width
            y2 = (y + h / 2) * height
            draw.rectangle([x1, y1, x2, y2], outline=(255, 40, 40), width=3)
            draw.text((x1 + 2, max(0, y1 - 12)), class_names[class_id], fill=(255, 255, 0), font=font)
            bbox_count += 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, quality=92)
    return bbox_count


def build_dataset(args: argparse.Namespace) -> dict[str, Any]:
    source_manifest_path = resolve_path(args.source_manifest)
    source_data_yaml_path = resolve_path(args.source_data_yaml)
    source_class_map_path = resolve_path(args.source_class_map)
    review_items_path = resolve_path(args.review_items_csv)
    review_decisions_path = resolve_path(args.review_decisions_csv)
    review_summary_path = resolve_path(args.review_summary_json)
    review_gate_report_path = resolve_path(args.review_gate_report)
    rules_config_path = resolve_path(args.rules_config)

    output_dataset_root = resolve_path(args.output_dataset)
    output_visual_audit_root = resolve_path(args.output_visual_audit)
    output_review_items_csv = resolve_path(args.output_review_items_csv)
    output_review_items_json = resolve_path(args.output_review_items_json)
    output_before_after_csv = resolve_path(args.output_before_after_csv)
    output_before_after_json = resolve_path(args.output_before_after_json)
    output_issue_analysis_json = resolve_path(args.output_issue_analysis_json)
    output_issue_analysis_md = resolve_path(args.output_issue_analysis_md)
    output_conversion_report_json = resolve_path(args.output_conversion_report_json)
    output_conversion_report_md = resolve_path(args.output_conversion_report_md)
    output_quality_summary_md = resolve_path(args.output_quality_summary_md)
    output_dataset_check_md = resolve_path(args.output_dataset_check_md)
    review_bat_path = resolve_path(args.review_bat)

    source_rows = load_csv_rows(source_manifest_path)
    review_seed_rows = normalize_review_seed_items(load_csv_rows(review_items_path))
    review_decision_rows = load_csv_rows(review_decisions_path)
    review_summary_payload = json.loads(review_summary_path.read_text(encoding="utf-8"))
    rules_config = load_yaml(rules_config_path)
    class_id_map = class_id_map_from_data_yaml(source_data_yaml_path)
    source_class_map_payload = load_yaml(source_class_map_path)
    random.Random(args.seed)

    issue_analysis, issue_analysis_md = analyze_review_results(
        review_decision_rows,
        review_summary_payload,
        review_gate_report_path,
    )
    write_json(output_issue_analysis_json, issue_analysis)
    write_text(output_issue_analysis_md, issue_analysis_md)

    if output_dataset_root.exists():
        shutil.rmtree(output_dataset_root)
    if output_visual_audit_root.exists():
        shutil.rmtree(output_visual_audit_root)

    for split in ("train", "val", "test"):
        (output_dataset_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_dataset_root / "labels" / split).mkdir(parents=True, exist_ok=True)
    (output_dataset_root / "metadata").mkdir(parents=True, exist_ok=True)
    output_visual_audit_root.mkdir(parents=True, exist_ok=True)

    source_by_image_name = {row["image_name"]: row for row in source_rows}
    old_review_by_image_name = {Path(row["image_path"]).name: row for row in review_decision_rows}
    old_review_seed_by_image_name = {Path(row["image_path"]).name: row for row in review_seed_rows}
    class_names_by_id = {index: name for name, index in class_id_map.items()}

    manifest_rows = []
    before_after_rows = []
    conversion_report_rows = []
    class_bbox_counter = Counter()
    class_image_counter = Counter()
    split_image_counter = Counter()
    split_bbox_counter = Counter()
    filter_reason_counter = Counter()
    source_issue_review_ids = set(issue_analysis["issue_ids"])

    for row in source_rows:
        class_name = row["class_name"]
        split = row["split"]
        class_id = int(row["class_id"])
        source_image_path = resolve_path(row["source_image"])
        source_mask_path = resolve_path(row["source_mask"])
        output_image_path = output_dataset_root / row["relative_image_path"].replace("\\", "/")
        output_label_path = output_dataset_root / row["relative_label_path"].replace("\\", "/")
        image = Image.open(source_image_path).convert("RGB")
        raw_mask = Image.open(source_mask_path)
        if image.size != raw_mask.size:
            raise RuntimeError(f"Image/mask size mismatch for {source_image_path.name}")

        per_class_rules = rules_config["per_class"][class_name]
        global_rules = rules_config["global"]
        open_kernel = int(per_class_rules.get("morph_open_kernel", global_rules["default_morph_open_kernel"]))
        close_kernel = int(per_class_rules.get("morph_close_kernel", global_rules["default_morph_close_kernel"]))
        min_area_pixels = int(per_class_rules.get("min_area_pixels", global_rules["default_min_area_pixels"]))
        min_area_ratio = float(per_class_rules.get("min_area_ratio", global_rules["default_min_area_ratio"]))
        min_box_width = int(per_class_rules.get("min_box_width", global_rules["default_min_box_width"]))
        min_box_height = int(per_class_rules.get("min_box_height", global_rules["default_min_box_height"]))
        merge_nearby_boxes = bool(
            per_class_rules.get("merge_nearby_boxes", global_rules["default_merge_nearby_boxes"])
        )
        merge_distance_pixels = int(
            per_class_rules.get("merge_distance_pixels", global_rules["default_merge_distance_pixels"])
        )
        min_area_effective = max(min_area_pixels, int(math.ceil(image.size[0] * image.size[1] * min_area_ratio)))

        morphed = binary_morphology(raw_mask, open_kernel, close_kernel)
        components = connected_components(morphed)
        kept_boxes = []
        filtered_tiny = 0
        filtered_small_box = 0
        for component in components:
            if component["area"] < min_area_effective:
                filtered_tiny += 1
                continue
            if component["width"] < min_box_width or component["height"] < min_box_height:
                filtered_small_box += 1
                continue
            kept_boxes.append(component)

        merged_component_count = 0
        if merge_nearby_boxes and kept_boxes:
            kept_boxes, merged_component_count = merge_boxes(kept_boxes, merge_distance_pixels)

        label_lines = [yolo_line(class_id, box, image.size) for box in kept_boxes]
        shutil.copy2(source_image_path, output_image_path)
        output_label_path.parent.mkdir(parents=True, exist_ok=True)
        output_label_path.write_text(("\n".join(label_lines) + "\n") if label_lines else "", encoding="utf-8")

        image_name = output_image_path.name
        old_review = old_review_by_image_name.get(image_name, {})
        old_review_seed = old_review_seed_by_image_name.get(image_name, {})
        old_visual_preview_path = resolve_path(old_review_seed.get("visual_preview_path", "")) if old_review_seed else None
        new_preview_name = (
            f"{old_review_seed.get('review_id', row['output_stem'])}_"
            f"{sanitize_for_preview_name(Path(image_name).stem)}.jpg"
        )
        new_visual_preview_path = output_visual_audit_root / new_preview_name
        new_bbox_count = render_preview(output_image_path, output_label_path, new_visual_preview_path, class_names_by_id)

        manifest_rows.append(
            {
                "split": split,
                "source_split": split,
                "class_name": class_name,
                "class_id": class_id,
                "dataset_name": "rice_phone_rgb_riceseg_preview_200_revised_v0_1",
                "source_dataset": "RiceSeg-5932 paired with Sethy phone RGB lineage",
                "image_name": image_name,
                "label_name": output_label_path.name,
                "relative_image_path": str(Path("images") / split / image_name),
                "relative_label_path": str(Path("labels") / split / output_label_path.name),
                "source_image": str(source_image_path),
                "source_mask": str(source_mask_path),
                "original_preview_dataset": "datasets/rice_phone_rgb_riceseg_preview_200",
                "old_bbox_count": int(row["bbox_count"]),
                "new_bbox_count": new_bbox_count,
                "raw_component_count": len(components),
                "filtered_component_count": filtered_tiny + filtered_small_box,
                "filtered_tiny_component_count": filtered_tiny,
                "filtered_small_box_component_count": filtered_small_box,
                "merged_component_count": merged_component_count,
                "min_area_pixels_effective": min_area_effective,
                "min_box_width": min_box_width,
                "min_box_height": min_box_height,
                "morph_open_kernel": open_kernel,
                "morph_close_kernel": close_kernel,
                "merge_nearby_boxes": merge_nearby_boxes,
                "merge_distance_pixels": merge_distance_pixels,
                "conversion_rule_version": rules_config["rule_version"],
            }
        )
        before_after_rows.append(
            {
                "review_id": old_review_seed.get("review_id", ""),
                "class_name": class_name,
                "split": split,
                "image_name": image_name,
                "image_path": str(output_image_path),
                "label_path": str(output_label_path),
                "old_visual_preview_path": str(old_visual_preview_path) if old_visual_preview_path else "",
                "new_visual_preview_path": str(new_visual_preview_path),
                "old_bbox_count": int(row["bbox_count"]),
                "new_bbox_count": new_bbox_count,
                "bbox_delta": new_bbox_count - int(row["bbox_count"]),
                "old_issue_type": old_review.get("issue_type", ""),
                "old_reviewer_notes": old_review.get("reviewer_notes", ""),
                "selection_reason": old_review_seed.get("selection_reason", ""),
            }
        )
        conversion_report_rows.append(
            {
                "image_name": image_name,
                "class_name": class_name,
                "split": split,
                "old_bbox_count": int(row["bbox_count"]),
                "new_bbox_count": new_bbox_count,
                "raw_component_count": len(components),
                "filtered_component_count": filtered_tiny + filtered_small_box,
                "merged_component_count": merged_component_count,
                "filtered_tiny_component_count": filtered_tiny,
                "filtered_small_box_component_count": filtered_small_box,
                "rule_version": rules_config["rule_version"],
            }
        )
        class_bbox_counter[class_name] += new_bbox_count
        class_image_counter[class_name] += 1
        split_image_counter[split] += 1
        split_bbox_counter[split] += new_bbox_count
        filter_reason_counter["filtered_tiny_components"] += filtered_tiny
        filter_reason_counter["filtered_small_box_components"] += filtered_small_box
        filter_reason_counter["merged_component_events"] += merged_component_count

    data_yaml_payload = {
        "path": str(output_dataset_root),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "nc": len(DEFAULT_CLASSES),
        "names": {class_id_map[name]: name for name in DEFAULT_CLASSES},
    }
    write_text(
        output_dataset_root / "data.yaml",
        yaml.safe_dump(data_yaml_payload, sort_keys=False, allow_unicode=True),
    )
    write_text(
        output_dataset_root / "metadata" / "class_map.yaml",
        yaml.safe_dump(source_class_map_payload, sort_keys=False, allow_unicode=True),
    )
    write_text(
        output_dataset_root / "metadata" / "revised_rules.yaml",
        yaml.safe_dump(rules_config, sort_keys=False, allow_unicode=True),
    )
    write_csv(
        output_dataset_root / "metadata" / "conversion_manifest.csv",
        manifest_rows,
        list(manifest_rows[0].keys()),
    )

    visual_manifest_rows = []
    review_selection_rows = []
    grouped_seed_rows = defaultdict(list)
    for seed in review_seed_rows:
        grouped_seed_rows[seed["class_name"]].append(seed)
    issue_review_rows = {row["review_id"]: row for row in issue_analysis["issue_rows"]}
    selected_review_ids = []
    for class_name in DEFAULT_CLASSES:
        issue_ids_for_class = [
            seed["review_id"]
            for seed in grouped_seed_rows[class_name]
            if seed["review_id"] in source_issue_review_ids
        ]
        normal_ids_for_class = [
            seed["review_id"]
            for seed in grouped_seed_rows[class_name]
            if seed["review_id"] not in source_issue_review_ids
        ]
        ordered = issue_ids_for_class + normal_ids_for_class
        selected_review_ids.extend(ordered[: int(rules_config["global"]["review_items_per_class"])])

    before_after_by_review_id = {row["review_id"]: row for row in before_after_rows if row["review_id"]}
    for review_id in selected_review_ids:
        source_seed = next(seed for seed in review_seed_rows if seed["review_id"] == review_id)
        before_after = before_after_by_review_id[review_id]
        old_review = issue_review_rows.get(review_id, {})
        class_name = source_seed["class_name"]
        selection_reason = (
            "prior_issue_sample"
            if review_id in source_issue_review_ids
            else source_seed.get("selection_reason", "same_lineage_followup")
        )
        review_selection_rows.append(
            {
                "review_id": review_id,
                "class_name": class_name,
                "split": source_seed["split"],
                "image_path": before_after["image_path"],
                "label_path": before_after["label_path"],
                "visual_preview_path": before_after["new_visual_preview_path"],
                "old_visual_preview_path": before_after["old_visual_preview_path"],
                "new_visual_preview_path": before_after["new_visual_preview_path"],
                "old_issue_type": old_review.get("issue_type", ""),
                "old_reviewer_notes": old_review.get("reviewer_notes", ""),
                "old_bbox_count": before_after["old_bbox_count"],
                "new_bbox_count": before_after["new_bbox_count"],
                "bbox_count": before_after["new_bbox_count"],
                "selection_reason": selection_reason,
                "review_status": "unreviewed",
                "issue_type": "",
                "reviewer_notes": "",
                "reviewed_at": "",
            }
        )
        visual_manifest_rows.append(
            {
                "review_id": review_id,
                "class_name": class_name,
                "split": source_seed["split"],
                "old_bbox_count": before_after["old_bbox_count"],
                "new_bbox_count": before_after["new_bbox_count"],
                "old_visual_preview_path": before_after["old_visual_preview_path"],
                "new_visual_preview_path": before_after["new_visual_preview_path"],
                "old_issue_type": old_review.get("issue_type", ""),
            }
        )

    write_csv(output_review_items_csv, review_selection_rows, list(review_selection_rows[0].keys()))
    write_json(
        output_review_items_json,
        {
            "generated_from": "same_lineage_preview_200_rebuild",
            "review_items": review_selection_rows,
        },
    )
    write_csv(output_before_after_csv, before_after_rows, list(before_after_rows[0].keys()))
    write_json(
        output_before_after_json,
        {
            "comparison_rows": before_after_rows,
            "summary": {
                "row_count": len(before_after_rows),
                "issue_review_ids": list(source_issue_review_ids),
            },
        },
    )
    write_csv(output_visual_audit_root / "manifest.csv", visual_manifest_rows, list(visual_manifest_rows[0].keys()))

    visual_md_lines = [
        "# RiceSeg preview_200 revised_v0_1 Visual Audit",
        "",
        "This audit keeps the same 80 review seeds where possible so old/new bbox previews stay directly comparable.",
        "",
    ]
    for row in visual_manifest_rows:
        visual_md_lines.append(
            f"- `{row['review_id']}` / `{row['class_name']}` / `{row['split']}` / "
            f"old_bbox=`{row['old_bbox_count']}` / new_bbox=`{row['new_bbox_count']}`"
        )
        visual_md_lines.append(f"  - old: `{row['old_visual_preview_path']}`")
        visual_md_lines.append(f"  - new: `{row['new_visual_preview_path']}`")
    write_text(output_visual_audit_root / "index.md", "\n".join(visual_md_lines) + "\n")

    conversion_report_payload = {
        "rule_version": rules_config["rule_version"],
        "source_preview_dataset": "datasets/rice_phone_rgb_riceseg_preview_200",
        "output_dataset": str(output_dataset_root),
        "image_count": len(manifest_rows),
        "label_count": len(manifest_rows),
        "total_old_bbox_count": sum(int(row["old_bbox_count"]) for row in manifest_rows),
        "total_new_bbox_count": sum(int(row["new_bbox_count"]) for row in manifest_rows),
        "class_image_distribution": dict(class_image_counter),
        "class_bbox_distribution": dict(class_bbox_counter),
        "split_image_distribution": dict(split_image_counter),
        "split_bbox_distribution": dict(split_bbox_counter),
        "filter_reason_counter": dict(filter_reason_counter),
        "zero_label_images": [
            row["image_name"] for row in manifest_rows if int(row["new_bbox_count"]) == 0
        ],
        "sample_row_count": len(conversion_report_rows),
    }
    write_json(output_conversion_report_json, conversion_report_payload)
    conversion_md_lines = [
        "# RiceSeg preview_200 revised_v0_1 Conversion Report",
        "",
        f"- rule_version: `{rules_config['rule_version']}`",
        f"- source_preview_dataset: `datasets/rice_phone_rgb_riceseg_preview_200`",
        f"- output_dataset: `{output_dataset_root}`",
        f"- image_count: `{conversion_report_payload['image_count']}`",
        f"- total_old_bbox_count: `{conversion_report_payload['total_old_bbox_count']}`",
        f"- total_new_bbox_count: `{conversion_report_payload['total_new_bbox_count']}`",
        "",
        "## Class BBox Distribution",
        "",
    ]
    for name in DEFAULT_CLASSES:
        conversion_md_lines.append(
            f"- `{name}`: images=`{class_image_counter[name]}` new_bbox=`{class_bbox_counter[name]}`"
        )
    conversion_md_lines += [
        "",
        "## Filter Summary",
        "",
    ]
    for name, count in filter_reason_counter.items():
        conversion_md_lines.append(f"- `{name}`: `{count}`")
    write_text(output_conversion_report_md, "\n".join(conversion_md_lines) + "\n")

    quality_summary_lines = [
        "# RiceSeg preview_200 revised_v0_1 Conversion Quality Summary",
        "",
        f"- prior_review_gate: `{review_summary_payload.get('gate')}`",
        f"- prior_obvious_error_ratio: `{review_summary_payload.get('obvious_error_ratio')}`",
        "- rationale: the revised build only changes mask-to-bbox rules for bacterial_blight and tungro.",
        f"- rebuilt_dataset_path: `{output_dataset_root}`",
        f"- before_after_table: `{output_before_after_csv}`",
        f"- visual_audit_index: `{output_visual_audit_root / 'index.md'}`",
        "",
        "## Expected Effect",
        "",
        "- bacterial_blight and tungro should have far fewer shard-like boxes.",
        "- blast and brown_spot keep the original conservative rule for comparability.",
        "- This is still a preview gate artifact, not a formal training dataset.",
        "",
    ]
    write_text(output_quality_summary_md, "\n".join(quality_summary_lines))

    review_bat_content = "\n".join(
        [
            "@echo off",
            "chcp 65001 >nul",
            f'cd /d "{repo_root()}"',
            "python scripts\\launch_riceseg_preview200_review_desktop.py ^",
            f'  --items-csv "{output_review_items_csv}" ^',
            f'  --decisions-csv "reports\\riceseg_preview_200_revised_v0_1_manual_review_decisions.csv" ^',
            f'  --decisions-json "reports\\riceseg_preview_200_revised_v0_1_manual_review_decisions.json" ^',
            f'  --summary-json "reports\\riceseg_preview_200_revised_v0_1_manual_review_summary.json" ^',
            f'  --gate-report "reports\\riceseg_preview_200_revised_v0_1_manual_review_gate_report.md" ^',
            f'  --log-path "reports\\riceseg_preview_200_revised_v0_1_review_desktop.log"',
            "echo.",
            "echo Review app exited.",
            "pause",
            "",
        ]
    )
    write_text(review_bat_path, review_bat_content)

    dataset_check_md_lines = [
        "# RiceSeg preview_200 revised_v0_1 Dataset Check",
        "",
        "Run `scripts/check_dataset.py` against the revised dataset to confirm split directories, labels, objects, and metadata.",
        "",
        f"- dataset_root: `{output_dataset_root}`",
        f"- metadata_manifest: `{output_dataset_root / 'metadata' / 'conversion_manifest.csv'}`",
        "",
        "The JSON report is generated by the explicit `check_dataset.py` run in this round.",
        "",
    ]
    write_text(output_dataset_check_md, "\n".join(dataset_check_md_lines))

    return {
        "dataset_root": str(output_dataset_root),
        "visual_audit_root": str(output_visual_audit_root),
        "review_items_csv": str(output_review_items_csv),
        "review_items_json": str(output_review_items_json),
        "before_after_csv": str(output_before_after_csv),
        "before_after_json": str(output_before_after_json),
        "issue_analysis_json": str(output_issue_analysis_json),
        "issue_analysis_md": str(output_issue_analysis_md),
        "conversion_report_json": str(output_conversion_report_json),
        "conversion_report_md": str(output_conversion_report_md),
        "conversion_quality_summary_md": str(output_quality_summary_md),
        "dataset_check_md": str(output_dataset_check_md),
        "review_bat": str(review_bat_path),
    }


def main() -> int:
    args = parse_args()
    if not args.execute:
        print(json.dumps({"status": "dry_run_only", "next_step": "rerun with --execute"}, ensure_ascii=False, indent=2))
        return 0
    result = build_dataset(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
