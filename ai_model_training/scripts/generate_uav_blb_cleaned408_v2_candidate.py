"""Generate cleaned408_v2 candidate labels for UAV BLB 408.

This creates a derived dataset. It does not modify source images or source labels.
"""

from __future__ import annotations

import csv
import json
import math
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "datasets" / "rice_uav_ms_blb_preview_1000"
OUT = ROOT / "datasets" / "rice_uav_ms_blb_cleaned408_v2"
REPORTS = ROOT / "reports"
META = ROOT / "metadata"
IMAGE_META = SRC / "metadata" / "image_metadata.csv"
DECISIONS = REPORTS / "uav_blb_408_manual_review_decisions.csv"

SPLITS = ("train", "val", "test")
BLB_VALUES = (2, 3)
CLASS_NAME = "bacterial_leaf_blight"

# Conservative candidate rules. These are intentionally not a training release.
MIN_AREA_PIXELS = 80
CLOSING_ITERATIONS = 2
DILATION_ITERATIONS = 2
MIN_BOX_AREA_RATIO = 0.0012
MAX_BOX_AREA_RATIO = 0.62
MAX_ASPECT_RATIO = 8.0
SECOND_REVIEW_BBOX_COUNT = 8
MANUAL_SECOND_REVIEW_ISSUES = {
    "OVERLAP_DUPLICATE_BBOX",
    "FRAGMENTED_PATCH",
    "SMALL_OR_MISSING_BBOX",
    "EDGE_CUT_OR_BLUR",
    "unclear",
}


@dataclass(frozen=True)
class Box:
    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float
    area: int

    @property
    def area_ratio(self) -> float:
        return self.width * self.height

    @property
    def aspect_ratio(self) -> float:
        if self.width <= 0 or self.height <= 0:
            return float("inf")
        return max(self.width / self.height, self.height / self.width)

    def line(self) -> str:
        return f"{self.class_id} {self.x_center:.6f} {self.y_center:.6f} {self.width:.6f} {self.height:.6f}"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def atomic_write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    tmp.replace(path)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def source_path(row: dict[str, str], field: str) -> Path:
    return ROOT / row[field].replace("\\", "/")


def read_tif(path: Path) -> np.ndarray:
    return np.asarray(tifffile.imread(path))


def boxes_from_yolo(path: Path) -> list[Box]:
    boxes: list[Box] = []
    if not path.exists():
        return boxes
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            class_id = int(float(parts[0]))
            x, y, w, h = [float(value) for value in parts[1:]]
        except ValueError:
            continue
        boxes.append(Box(class_id, x, y, w, h, area=int(round(w * h * 256 * 256))))
    return boxes


def candidate_boxes_from_raster(label_path: Path) -> tuple[list[Box], dict[str, Any]]:
    label = read_tif(label_path)
    if label.ndim > 2:
        label = label[:, :, 0]
    height, width = label.shape[:2]
    structure = np.ones((3, 3), dtype=bool)
    all_boxes: list[Box] = []
    stats = Counter()
    values_present = sorted(int(value) for value in np.unique(label).tolist())

    for value in BLB_VALUES:
        mask = np.asarray(label == value)
        if not mask.any():
            continue
        stats[f"value_{value}_pixels"] += int(mask.sum())
        closed = ndimage.binary_closing(mask, structure=structure, iterations=CLOSING_ITERATIONS)
        dilated = ndimage.binary_dilation(closed, structure=structure, iterations=DILATION_ITERATIONS)
        merged = ndimage.binary_erosion(dilated, structure=structure, iterations=max(1, DILATION_ITERATIONS - 1))
        labeled, count = ndimage.label(merged)
        stats[f"value_{value}_components_after_merge"] += int(count)
        for component_id in range(1, count + 1):
            ys, xs = np.where(labeled == component_id)
            if xs.size == 0:
                continue
            original_area = int(mask[labeled == component_id].sum())
            merged_area = int(xs.size)
            if max(original_area, merged_area) < MIN_AREA_PIXELS:
                stats["filtered_small_component"] += 1
                continue
            x1, x2 = int(xs.min()), int(xs.max())
            y1, y2 = int(ys.min()), int(ys.max())
            box_w = (x2 - x1 + 1) / width
            box_h = (y2 - y1 + 1) / height
            box = Box(
                0,
                ((x1 + x2 + 1) / 2) / width,
                ((y1 + y2 + 1) / 2) / height,
                box_w,
                box_h,
                max(original_area, merged_area),
            )
            if box.area_ratio < MIN_BOX_AREA_RATIO:
                stats["filtered_tiny_bbox"] += 1
                continue
            if box.area_ratio > MAX_BOX_AREA_RATIO:
                stats["flag_large_bbox_kept_for_review"] += 1
            if box.aspect_ratio > MAX_ASPECT_RATIO:
                stats["filtered_extreme_aspect"] += 1
                continue
            all_boxes.append(box)

    # De-duplicate boxes created separately from low/high masks when they describe near-identical regions.
    kept: list[Box] = []
    for box in sorted(all_boxes, key=lambda item: item.area_ratio, reverse=True):
        duplicate = False
        for existing in kept:
            if box_iou(box, existing) >= 0.70:
                duplicate = True
                stats["deduped_cross_value_bbox"] += 1
                break
        if not duplicate:
            kept.append(box)
    kept.sort(key=lambda item: (item.y_center, item.x_center, item.width * item.height))
    return kept, {"values_present": values_present, "stats": dict(stats)}


def box_iou(a: Box, b: Box) -> float:
    ax1, ay1, ax2, ay2 = yolo_to_xyxy(a)
    bx1, by1, bx2, by2 = yolo_to_xyxy(b)
    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = inter_w * inter_h
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return inter / denom if denom else 0.0


def yolo_to_xyxy(box: Box) -> tuple[float, float, float, float]:
    return (
        box.x_center - box.width / 2,
        box.y_center - box.height / 2,
        box.x_center + box.width / 2,
        box.y_center + box.height / 2,
    )


def review_reason(decision_row: dict[str, str], original_count: int, cleaned_count: int, diagnostics: dict[str, Any]) -> str:
    reasons: list[str] = []
    issue = decision_row.get("issue_type", "")
    if issue in MANUAL_SECOND_REVIEW_ISSUES:
        reasons.append(issue)
    if cleaned_count == 0:
        reasons.append("no_candidate_bbox_after_cleaning")
    if cleaned_count >= SECOND_REVIEW_BBOX_COUNT:
        reasons.append("bbox_count_still_high")
    if cleaned_count > original_count:
        reasons.append("candidate_increased_bbox_count")
    if diagnostics.get("stats", {}).get("flag_large_bbox_kept_for_review", 0):
        reasons.append("large_bbox_still_present")
    if not reasons and abs(original_count - cleaned_count) >= 3:
        reasons.append("large_bbox_count_delta")
    return ";".join(reasons)


def load_font(size: int) -> ImageFont.ImageFont:
    for candidate in [Path("C:/Windows/Fonts/arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]:
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except OSError:
                pass
    return ImageFont.load_default()


def draw_overlay_panel(image: Image.Image, boxes: list[Box], title: str) -> Image.Image:
    panel = image.convert("RGB").copy()
    draw = ImageDraw.Draw(panel)
    font = load_font(18)
    small = load_font(14)
    colors = [(220, 38, 38), (37, 99, 235), (22, 163, 74), (217, 119, 6)]
    draw.rectangle((0, 0, panel.width, 30), fill=(245, 247, 250))
    draw.text((8, 6), title, fill=(20, 24, 32), font=small)
    for idx, box in enumerate(boxes, start=1):
        x1, y1, x2, y2 = yolo_to_xyxy(box)
        coords = (x1 * panel.width, y1 * panel.height, x2 * panel.width, y2 * panel.height)
        color = colors[(idx - 1) % len(colors)]
        for offset in range(2):
            draw.rectangle(
                (coords[0] - offset, coords[1] - offset, coords[2] + offset, coords[3] + offset),
                outline=color,
            )
        draw.text((coords[0] + 2, max(32, coords[1] - 18)), str(idx), fill=color, font=font)
    return panel


def make_before_after(image_path: Path, original_boxes: list[Box], cleaned_boxes: list[Box], out_path: Path, title: str) -> None:
    image = Image.open(image_path).convert("RGB")
    image.thumbnail((512, 512))
    left = draw_overlay_panel(image, original_boxes, f"original labels: {len(original_boxes)}")
    right = draw_overlay_panel(image, cleaned_boxes, f"cleaned408_v2 candidate: {len(cleaned_boxes)}")
    header_h = 50
    canvas = Image.new("RGB", (left.width + right.width, left.height + header_h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    font = load_font(16)
    draw.text((8, 8), title[:140], fill=(20, 24, 32), font=font)
    canvas.paste(left, (0, header_h))
    canvas.paste(right, (left.width, header_h))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=92)


def write_data_yaml() -> None:
    atomic_write_text(
        OUT / "data.yaml",
        """path: datasets/rice_uav_ms_blb_cleaned408_v2
train: images/train
val: images/val
test: images/test
nc: 1
names:
  0: bacterial_leaf_blight
""",
    )


def main() -> int:
    metadata_rows = {row["image_name"]: row for row in load_csv(IMAGE_META)}
    decision_rows = load_csv(DECISIONS)
    decision_by_name = {row["image_name"]: row for row in decision_rows}
    before_after_rows: list[dict[str, Any]] = []
    second_review_rows: list[dict[str, Any]] = []
    generated_meta: list[dict[str, Any]] = []
    totals = Counter()

    for split in SPLITS:
        (OUT / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUT / "labels" / split).mkdir(parents=True, exist_ok=True)
    (OUT / "overlays_before_after").mkdir(parents=True, exist_ok=True)
    (OUT / "meta").mkdir(parents=True, exist_ok=True)
    for old_overlay in (OUT / "overlays_before_after").glob("*.jpg"):
        old_overlay.unlink()

    for split in SPLITS:
        for image_path in sorted((SRC / "images" / split).glob("*.jpg")):
            image_name = image_path.name
            row = metadata_rows[image_name]
            decision = decision_by_name.get(image_name, {})
            original_label_path = SRC / "labels" / split / f"{image_path.stem}.txt"
            original_boxes = boxes_from_yolo(original_label_path)
            raster_label_path = ROOT / "raw_datasets" / "blb_uav_dataset" / "original" / row["original_label_path"].replace("\\", "/")
            cleaned_boxes, diagnostics = candidate_boxes_from_raster(raster_label_path)

            out_image = OUT / "images" / split / image_path.name
            if not out_image.exists():
                shutil.copy2(image_path, out_image)
            out_label = OUT / "labels" / split / f"{image_path.stem}.txt"
            atomic_write_text(out_label, "\n".join(box.line() for box in cleaned_boxes) + ("\n" if cleaned_boxes else ""))

            original_count = len(original_boxes)
            cleaned_count = len(cleaned_boxes)
            totals["images"] += 1
            totals["original_bbox"] += original_count
            totals["cleaned_bbox"] += cleaned_count
            totals[f"split_{split}"] += 1
            totals[f"issue_{decision.get('issue_type', 'not_reviewed')}"] += 1
            reason = review_reason(decision, original_count, cleaned_count, diagnostics)
            needs_second_review = bool(reason)
            if needs_second_review:
                totals["second_review"] += 1
                second_review_rows.append(
                    {
                        "image_name": image_name,
                        "split": split,
                        "issue_type": decision.get("issue_type", ""),
                        "original_bbox_count": original_count,
                        "cleaned_bbox_count": cleaned_count,
                        "review_reason": reason,
                        "visual_path": f"datasets/rice_uav_ms_blb_cleaned408_v2/overlays_before_after/{image_path.stem}_before_after.jpg",
                    }
                )
            if needs_second_review:
                make_before_after(
                    image_path,
                    original_boxes,
                    cleaned_boxes,
                    OUT / "overlays_before_after" / f"{image_path.stem}_before_after.jpg",
                    f"{image_name} | issue={decision.get('issue_type','')} | reason={reason or 'candidate comparison'}",
                )

            before_after_rows.append(
                {
                    "image_name": image_name,
                    "split": split,
                    "issue_type": decision.get("issue_type", ""),
                    "original_bbox_count": original_count,
                    "cleaned_bbox_count": cleaned_count,
                    "bbox_delta": cleaned_count - original_count,
                    "bbox_reduction": original_count - cleaned_count,
                    "review_reason": reason,
                    "source_label_path": rel(original_label_path),
                    "candidate_label_path": rel(out_label),
                    "candidate_image_path": rel(out_image),
                }
            )
            generated_meta.append(
                {
                    "image_name": image_name,
                    "split": split,
                    "source_image_path": rel(image_path),
                    "candidate_image_path": rel(out_image),
                    "source_label_path": rel(original_label_path),
                    "candidate_label_path": rel(out_label),
                    "source_raster_label_path": rel(raster_label_path),
                    "issue_type": decision.get("issue_type", ""),
                    "original_bbox_count": original_count,
                    "cleaned_bbox_count": cleaned_count,
                    "diagnostics": json.dumps(diagnostics, ensure_ascii=False),
                }
            )

    write_data_yaml()
    atomic_write_csv(
        OUT / "meta" / "candidate_generation_manifest.csv",
        generated_meta,
        [
            "image_name",
            "split",
            "source_image_path",
            "candidate_image_path",
            "source_label_path",
            "candidate_label_path",
            "source_raster_label_path",
            "issue_type",
            "original_bbox_count",
            "cleaned_bbox_count",
            "diagnostics",
        ],
    )
    atomic_write_csv(
        REPORTS / "uav_blb_408_cleaned408_v2_before_after_summary.csv",
        before_after_rows,
        [
            "image_name",
            "split",
            "issue_type",
            "original_bbox_count",
            "cleaned_bbox_count",
            "bbox_delta",
            "bbox_reduction",
            "review_reason",
            "source_label_path",
            "candidate_label_path",
            "candidate_image_path",
        ],
    )
    atomic_write_csv(
        REPORTS / "uav_blb_408_cleaned408_v2_second_review_list.csv",
        second_review_rows,
        [
            "image_name",
            "split",
            "issue_type",
            "original_bbox_count",
            "cleaned_bbox_count",
            "review_reason",
            "visual_path",
        ],
    )

    original_total = int(totals["original_bbox"])
    cleaned_total = int(totals["cleaned_bbox"])
    reduced = original_total - cleaned_total
    reduction_ratio = reduced / original_total if original_total else 0.0
    report = {
        "generated_at": now_iso(),
        "source_dataset": "datasets/rice_uav_ms_blb_preview_1000",
        "candidate_dataset": "datasets/rice_uav_ms_blb_cleaned408_v2",
        "images": int(totals["images"]),
        "original_bbox_total": original_total,
        "cleaned408_v2_candidate_bbox_total": cleaned_total,
        "bbox_reduction_count": reduced,
        "bbox_reduction_ratio": reduction_ratio,
        "second_review_sample_count": len(second_review_rows),
        "manual_gate": "FAIL",
        "training_allowed": False,
        "class_policy": "single class bacterial_leaf_blight; manual review issue types are not YOLO classes",
        "cleaning_rules": {
            "min_area_pixels": MIN_AREA_PIXELS,
            "closing_iterations": CLOSING_ITERATIONS,
            "dilation_iterations": DILATION_ITERATIONS,
            "min_box_area_ratio": MIN_BOX_AREA_RATIO,
            "max_box_area_ratio": MAX_BOX_AREA_RATIO,
            "max_aspect_ratio": MAX_ASPECT_RATIO,
            "second_review_bbox_count": SECOND_REVIEW_BBOX_COUNT,
        },
        "outputs": {
            "before_after_summary": "reports/uav_blb_408_cleaned408_v2_before_after_summary.csv",
            "second_review_list": "reports/uav_blb_408_cleaned408_v2_second_review_list.csv",
            "candidate_manifest": "datasets/rice_uav_ms_blb_cleaned408_v2/meta/candidate_generation_manifest.csv",
            "overlays": "datasets/rice_uav_ms_blb_cleaned408_v2/overlays_before_after/",
        },
        "boundaries": {
            "training_executed": False,
            "new_weights_generated": False,
            "original_images_modified": False,
            "original_yolo_labels_overwritten": False,
            "backend_modified": False,
            "env_modified": False,
        },
    }
    atomic_write_json(REPORTS / "uav_blb_408_cleaned408_v2_candidate_generation_report.json", report)
    atomic_write_text(
        REPORTS / "uav_blb_408_cleaned408_v2_candidate_generation_report.md",
        f"""# UAV BLB 408 cleaned408_v2 Candidate Generation Report

## Boundary

- training_executed: `NO`
- new_weights_generated: `NO`
- original_images_modified: `NO`
- original_yolo_labels_overwritten: `NO`
- backend_modified: `NO`
- env_modified: `NO`

## Candidate Dataset

- source_dataset: `datasets/rice_uav_ms_blb_preview_1000`
- candidate_dataset: `datasets/rice_uav_ms_blb_cleaned408_v2`
- images_strategy: copied preview JPG images into derived dataset for review convenience; original images were not modified.
- labels_strategy: generated derived candidate YOLO labels from source raster masks using conservative morphology and filtering; original YOLO labels were not overwritten.
- class_policy: single class `bacterial_leaf_blight`; manual issue types are not YOLO classes.

## Counts

- images: `{report['images']}`
- original_bbox_total: `{original_total}`
- cleaned408_v2_candidate_bbox_total: `{cleaned_total}`
- bbox_reduction_count: `{reduced}`
- bbox_reduction_ratio: `{reduction_ratio:.4f}`
- second_review_sample_count: `{len(second_review_rows)}`

## Cleaning Rules

- min_area_pixels: `{MIN_AREA_PIXELS}`
- morphological_closing_iterations: `{CLOSING_ITERATIONS}`
- dilation_iterations: `{DILATION_ITERATIONS}`
- min_box_area_ratio: `{MIN_BOX_AREA_RATIO}`
- max_box_area_ratio: `{MAX_BOX_AREA_RATIO}`
- max_aspect_ratio: `{MAX_ASPECT_RATIO}`
- second_review_bbox_count_threshold: `{SECOND_REVIEW_BBOX_COUNT}`

## Outputs

- before_after_summary: `reports/uav_blb_408_cleaned408_v2_before_after_summary.csv`
- second_review_list: `reports/uav_blb_408_cleaned408_v2_second_review_list.csv`
- candidate_manifest: `datasets/rice_uav_ms_blb_cleaned408_v2/meta/candidate_generation_manifest.csv`
- overlays_before_after: `datasets/rice_uav_ms_blb_cleaned408_v2/overlays_before_after/`

## Gate Status

- manual_gate: `FAIL`
- training_allowed: `false`

cleaned408_v2 is a candidate label generation artifact only. It must enter targeted second review and a second manual gate before any training is allowed.
""",
    )
    atomic_write_text(
        META / "uav_blb_cleaned408_v2_status.yaml",
        f"""cleaned408_v2_stage: CANDIDATE_LABELS_GENERATED
source_manual_review: COMPLETE
source_manual_gate: FAIL
training_allowed: false
original_images_modified: false
original_labels_modified: false
weights_modified: false
backend_modified: false
env_modified: false
derived_dataset_created: true
derived_dataset_root: datasets/rice_uav_ms_blb_cleaned408_v2
candidate_bbox_total: {cleaned_total}
source_bbox_total: {original_total}
second_review_sample_count: {len(second_review_rows)}
next_allowed_stage: TARGETED_SECOND_REVIEW
notes:
  - manual issue types are review metadata only, not YOLO classes
  - current YOLO class remains bacterial_leaf_blight
  - do not train until cleaned408_v2 second gate passes
""",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
