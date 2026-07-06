"""Phone-36Train-Controlled-Tungro-15Epoch.

Controlled experimental training on the derived Tungro policy-fixed mini dataset.
This script:
- audits the derived dataset
- runs a new 15 epoch YOLO training
- validates baseline and controlled weights on the same derived val/test splits
- runs controlled-model confidence sweep and failure analysis for Tungro
- writes required reports with atomic file replacement

Boundaries:
- no backend/frontend changes
- no .env changes
- no original dataset mutation
- no baseline overwrite
- no formal/candidate claim
"""

from __future__ import annotations

import csv
import json
import math
import os
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import torch
import ultralytics
import yaml
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
DATASET_ROOT = ROOT / "datasets" / "_derived" / "phone_riceseg_v36_tungro_policy_fixed_mini"
DATA_YAML = DATASET_ROOT / "data.yaml"
FIXED_DATASET_MANIFEST = DATASET_ROOT / "fixed_dataset_manifest.csv"
POLICY_FIX_REPORT = ROOT / "reports" / "phone_36_tungro_annotation_policy_fix" / "phone_36_tungro_annotation_policy_fix_report.md"
ANNOTATION_POLICY_REPORT = ROOT / "reports" / "phone_36_tungro_annotation_policy_fix" / "annotation_policy.md"
BASELINE_RUN_DIR = ROOT / "experiments" / "phone_rgb_yolo" / "runs" / "controlled_exp_phone_riceseg_v35m_holdout_applied_10epoch"
BASELINE_WEIGHTS = BASELINE_RUN_DIR / "weights" / "best.pt"
BASELINE_DATA_YAML = ROOT / "datasets" / "phone_riceseg_v35m_holdout_applied" / "data.yaml"
BASELINE_ARGS_YAML = BASELINE_RUN_DIR / "args.yaml"
RUN_PROJECT = ROOT / "experiments" / "phone_rgb_yolo" / "runs"
RUN_NAME = "controlled_exp_phone_riceseg_v36_tungro_policy_fixed_15epoch"
RUN_DIR = RUN_PROJECT / RUN_NAME
REPORT_DIR = ROOT / "reports" / "phone_36_train_controlled_tungro_15epoch"
REPORT_MD = REPORT_DIR / "phone_36_train_controlled_tungro_15epoch_report.md"
TRAINING_CONTEXT_JSON = REPORT_DIR / "training_context.json"
TRAIN_METRICS_SUMMARY_CSV = REPORT_DIR / "train_metrics_summary.csv"
PER_CLASS_METRICS_CSV = REPORT_DIR / "per_class_metrics.csv"
TUNGRO_EVAL_SUMMARY_CSV = REPORT_DIR / "tungro_eval_summary.csv"
BASELINE_COMPARISON_CSV = REPORT_DIR / "baseline_vs_controlled_comparison.csv"
CONF_SWEEP_CSV = REPORT_DIR / "prediction_conf_sweep.csv"
FAILURE_CASES_CSV = REPORT_DIR / "failure_cases_tungro.csv"
DERIVED_DISTRIBUTION_CSV = REPORT_DIR / "derived_distribution_summary.csv"
VAL_PRED_DIR = REPORT_DIR / "predictions_val_conf_025"
TEST_PRED_DIR = REPORT_DIR / "predictions_test_conf_025"
TUNGRO_CONF_DIRS = {
    0.05: REPORT_DIR / "predictions_tungro_conf_005",
    0.10: REPORT_DIR / "predictions_tungro_conf_010",
    0.25: REPORT_DIR / "predictions_tungro_conf_025",
}
FAILURE_VIS_DIR = REPORT_DIR / "failure_visualizations"
VAL_PROJECT = REPORT_DIR / "yolo_val"
SEED = 2026
EPOCHS = 15
IMGSZ = 640
BATCH = 8
WORKERS = 0
MODEL_SOURCE = ROOT / "yolov8n.pt"
CLASS_NAMES_EXPECTED = {
    0: "bacterial_blight",
    1: "blast",
    2: "brown_spot",
    3: "tungro",
}
TUNGRO_CLASS_ID = 3
CONF_LIST = [0.05, 0.10, 0.25]
IOU = 0.7


@dataclass
class LabelRow:
    class_id: int
    cx: float
    cy: float
    w: float
    h: float
    raw_line: str


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except Exception:
        return path.resolve().as_posix()


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding=encoding, newline="") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    if not tmp.exists() or tmp.stat().st_size == 0:
        raise RuntimeError(f"Temporary file write failed: {tmp}")
    tmp.replace(path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"Atomic replace failed: {path}")


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
    if not tmp.exists() or tmp.stat().st_size == 0:
        raise RuntimeError(f"Temporary CSV write failed: {tmp}")
    tmp.replace(path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"Atomic CSV replace failed: {path}")


def load_font(size: int) -> ImageFont.ImageFont:
    for candidate in [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def list_images(path: Path) -> list[Path]:
    return sorted(
        [
            candidate
            for candidate in path.iterdir()
            if candidate.is_file() and candidate.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        ]
    )


def parse_label_file(label_path: Path) -> tuple[list[LabelRow], list[str]]:
    rows: list[LabelRow] = []
    issues: list[str] = []
    if not label_path.exists():
        issues.append("missing_label")
        return rows, issues
    text = label_path.read_text(encoding="utf-8").strip()
    if not text:
        return rows, issues
    for idx, raw in enumerate(text.splitlines(), start=1):
        parts = raw.strip().split()
        if len(parts) != 5:
            issues.append(f"bad_field_count_line_{idx}")
            continue
        try:
            class_id = int(float(parts[0]))
            cx, cy, w, h = [float(value) for value in parts[1:]]
        except ValueError:
            issues.append(f"non_numeric_line_{idx}")
            continue
        rows.append(LabelRow(class_id=class_id, cx=cx, cy=cy, w=w, h=h, raw_line=raw.strip()))
    return rows, issues


def normalized_box_to_xyxy(row: LabelRow, width: int, height: int) -> tuple[float, float, float, float]:
    cx = row.cx * width
    cy = row.cy * height
    bw = row.w * width
    bh = row.h * height
    x1 = cx - bw / 2.0
    y1 = cy - bh / 2.0
    x2 = cx + bw / 2.0
    y2 = cy + bh / 2.0
    return x1, y1, x2, y2


def validate_label_rows(rows: list[LabelRow], class_count: int) -> list[str]:
    issues: list[str] = []
    for idx, row in enumerate(rows, start=1):
        if row.class_id < 0 or row.class_id >= class_count:
            issues.append(f"class_id_out_of_range_line_{idx}")
        for field_name, value in [("cx", row.cx), ("cy", row.cy), ("w", row.w), ("h", row.h)]:
            if not math.isfinite(value):
                issues.append(f"{field_name}_nonfinite_line_{idx}")
        if row.w <= 0 or row.h <= 0:
            issues.append(f"non_positive_width_height_line_{idx}")
        if row.cx < 0 or row.cx > 1 or row.cy < 0 or row.cy > 1:
            issues.append(f"center_out_of_range_line_{idx}")
        x1 = row.cx - row.w / 2.0
        y1 = row.cy - row.h / 2.0
        x2 = row.cx + row.w / 2.0
        y2 = row.cy + row.h / 2.0
        if x1 < 0 or y1 < 0 or x2 > 1 or y2 > 1:
            issues.append(f"bbox_out_of_bounds_line_{idx}")
    return issues


def compute_iou(box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    intersection = (ix2 - ix1) * (iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def load_data_yaml() -> dict[str, Any]:
    payload = read_yaml(DATA_YAML)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected YAML structure: {DATA_YAML}")
    return payload


def scan_dataset(data_yaml: dict[str, Any]) -> dict[str, Any]:
    names = data_yaml.get("names", {})
    yaml_path_value = str(data_yaml.get("path", ""))
    yaml_path_resolved = Path(yaml_path_value).resolve() if yaml_path_value else None
    derived_data_yaml_pass = yaml_path_resolved == DATASET_ROOT.resolve()
    name_pass = names == CLASS_NAMES_EXPECTED
    tungro_class_id_confirmed = names.get(TUNGRO_CLASS_ID) == "tungro"

    class_count = len(names)
    sanitation_counter: Counter[str] = Counter()
    distribution_rows: list[dict[str, Any]] = []
    split_summaries: dict[str, Any] = {}
    tungro_images_by_split: dict[str, list[Path]] = {}

    for split in ("train", "val", "test"):
        image_dir = DATASET_ROOT / "images" / split
        label_dir = DATASET_ROOT / "labels" / split
        images = list_images(image_dir)
        image_stems = {path.stem for path in images}
        label_paths = sorted(label_dir.glob("*.txt"))
        label_stems = {path.stem for path in label_paths}

        missing_label_count = len(image_stems - label_stems)
        missing_image_count = len(label_stems - image_stems)
        sanitation_counter["missing_label_count"] += missing_label_count
        sanitation_counter["missing_image_count"] += missing_image_count

        per_class_image_counter: Counter[int] = Counter()
        per_class_bbox_counter: Counter[int] = Counter()
        empty_label_count = 0
        total_bboxes = 0
        tungro_images: list[Path] = []

        for label_path in label_paths:
            rows, parse_issues = parse_label_file(label_path)
            if parse_issues:
                sanitation_counter.update(parse_issues)
            if not rows:
                empty_label_count += 1
                continue
            row_issues = validate_label_rows(rows, class_count)
            if row_issues:
                sanitation_counter.update(row_issues)
            seen_classes = set()
            for row in rows:
                total_bboxes += 1
                per_class_bbox_counter[row.class_id] += 1
                seen_classes.add(row.class_id)
            for class_id in seen_classes:
                per_class_image_counter[class_id] += 1
            if TUNGRO_CLASS_ID in seen_classes:
                image_path = image_dir / f"{label_path.stem}.jpg"
                if not image_path.exists():
                    candidates = sorted(image_dir.glob(f"{label_path.stem}.*"))
                    if candidates:
                        image_path = candidates[0]
                if image_path.exists():
                    tungro_images.append(image_path)

        split_summaries[split] = {
            "image_dir": str(image_dir.resolve()),
            "label_dir": str(label_dir.resolve()),
            "total_images": len(images),
            "total_labels": len(label_paths),
            "total_bboxes": total_bboxes,
            "missing_label_count": missing_label_count,
            "missing_image_count": missing_image_count,
            "empty_label_count": empty_label_count,
            "per_class_images": {CLASS_NAMES_EXPECTED[key]: per_class_image_counter.get(key, 0) for key in CLASS_NAMES_EXPECTED},
            "per_class_bboxes": {CLASS_NAMES_EXPECTED[key]: per_class_bbox_counter.get(key, 0) for key in CLASS_NAMES_EXPECTED},
            "tungro_images": per_class_image_counter.get(TUNGRO_CLASS_ID, 0),
            "tungro_bboxes": per_class_bbox_counter.get(TUNGRO_CLASS_ID, 0),
        }
        tungro_images_by_split[split] = tungro_images

        for class_id, class_name in CLASS_NAMES_EXPECTED.items():
            distribution_rows.append(
                {
                    "split": split,
                    "class_id": class_id,
                    "class_name": class_name,
                    "images_with_class": per_class_image_counter.get(class_id, 0),
                    "bbox_count": per_class_bbox_counter.get(class_id, 0),
                    "total_images_in_split": len(images),
                    "total_labels_in_split": len(label_paths),
                    "total_bboxes_in_split": total_bboxes,
                    "missing_label_count": missing_label_count,
                    "missing_image_count": missing_image_count,
                    "empty_label_count": empty_label_count,
                }
            )

    derived_label_sanitation_pass = (
        sanitation_counter.get("bbox_out_of_bounds_line_1", 0) == 0  # fast fail key is not enough
        and sum(count for key, count in sanitation_counter.items() if key.startswith("bbox_out_of_bounds")) == 0
        and sum(count for key, count in sanitation_counter.items() if key.startswith("class_id_out_of_range")) == 0
        and sum(count for key, count in sanitation_counter.items() if key.startswith("non_positive_width_height")) == 0
        and sanitation_counter.get("missing_label_count", 0) == 0
        and sanitation_counter.get("missing_image_count", 0) == 0
    )

    return {
        "derived_data_yaml_pass": bool(derived_data_yaml_pass and name_pass),
        "tungro_class_id_confirmed": tungro_class_id_confirmed,
        "class_names_pass": name_pass,
        "yaml_path_value": yaml_path_value,
        "yaml_path_resolved": str(yaml_path_resolved) if yaml_path_resolved else "MISSING",
        "derived_label_sanitation_pass": derived_label_sanitation_pass,
        "sanitation_issues": dict(sanitation_counter),
        "split_summaries": split_summaries,
        "distribution_rows": distribution_rows,
        "tungro_images_by_split": tungro_images_by_split,
    }


def run_train(device: str) -> Path:
    if RUN_DIR.exists():
        raise RuntimeError(f"Run directory already exists; refusing to overwrite: {RUN_DIR}")
    model = YOLO(str(MODEL_SOURCE))
    model.train(
        data=str(DATA_YAML),
        imgsz=IMGSZ,
        epochs=EPOCHS,
        batch=BATCH,
        device=device,
        project=str(RUN_PROJECT),
        name=RUN_NAME,
        seed=SEED,
        exist_ok=False,
        workers=WORKERS,
        cache=False,
        optimizer="auto",
        lr0=0.003,
        weight_decay=0.0005,
        warmup_epochs=3.0,
        cos_lr=True,
        patience=20,
        hsv_h=0.015,
        hsv_s=0.6,
        hsv_v=0.35,
        degrees=8.0,
        translate=0.08,
        scale=0.5,
        shear=0.0,
        perspective=0.0,
        flipud=0.0,
        fliplr=0.5,
        mosaic=0.8,
        mixup=0.05,
        copy_paste=0.0,
        close_mosaic=10,
        deterministic=True,
        pretrained=True,
        verbose=True,
        plots=True,
        save=True,
        val=True,
    )
    best_path = RUN_DIR / "weights" / "best.pt"
    if not best_path.exists():
        raise RuntimeError(f"Training completed without best.pt: {best_path}")
    return best_path


def extract_overall_metrics(metrics: Any) -> dict[str, Any]:
    box = metrics.box
    return {
        "precision": float(getattr(box, "mp", 0.0)),
        "recall": float(getattr(box, "mr", 0.0)),
        "mAP50": float(getattr(box, "map50", 0.0)),
        "mAP50_95": float(getattr(box, "map", 0.0)),
    }


def extract_per_class_rows(metrics: Any, model_name: str, split: str, weights_path: Path) -> list[dict[str, Any]]:
    box = metrics.box
    names = dict(getattr(metrics, "names", {}) or {})
    per_rows: list[dict[str, Any]] = []
    for class_id, class_name in CLASS_NAMES_EXPECTED.items():
        precision = None
        recall = None
        ap50 = None
        ap50_95 = None
        if hasattr(box, "class_result"):
            try:
                result = box.class_result(class_id)
                if len(result) >= 4:
                    precision = float(result[0])
                    recall = float(result[1])
                    ap50 = float(result[2])
                    ap50_95 = float(result[3])
            except Exception:
                pass
        if precision is None and hasattr(box, "p"):
            try:
                precision = float(box.p[class_id])
            except Exception:
                precision = None
        if recall is None and hasattr(box, "r"):
            try:
                recall = float(box.r[class_id])
            except Exception:
                recall = None
        if ap50 is None and hasattr(box, "all_ap"):
            try:
                ap50 = float(box.all_ap[class_id][0])
            except Exception:
                ap50 = None
        if ap50_95 is None and hasattr(box, "maps"):
            try:
                ap50_95 = float(box.maps[class_id])
            except Exception:
                ap50_95 = None
        per_rows.append(
            {
                "model_name": model_name,
                "dataset_split": split,
                "class_id": class_id,
                "class_name": names.get(class_id, class_name),
                "precision": precision,
                "recall": recall,
                "AP50": ap50,
                "AP50_95": ap50_95,
                "weights_path": str(weights_path.resolve()),
            }
        )
    return per_rows


def validate_model(
    weights_path: Path,
    model_name: str,
    split: str,
    device: str,
    name_suffix: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    model = YOLO(str(weights_path))
    metrics = model.val(
        data=str(DATA_YAML),
        split=split,
        imgsz=IMGSZ,
        batch=BATCH,
        device=device,
        workers=WORKERS,
        project=str(VAL_PROJECT),
        name=name_suffix,
        plots=True,
        verbose=False,
    )
    overall = extract_overall_metrics(metrics)
    overall.update(
        {
            "model_name": model_name,
            "dataset_split": split,
            "weights_path": str(weights_path.resolve()),
            "save_dir": str(Path(metrics.save_dir).resolve()),
        }
    )
    per_rows = extract_per_class_rows(metrics, model_name=model_name, split=split, weights_path=weights_path)
    return overall, per_rows


def run_predict_save(model: YOLO, source: str | list[str], conf: float, save_dir: Path, device: str) -> list[Any]:
    if save_dir.exists():
        raise RuntimeError(f"Prediction output directory already exists; refusing to mix outputs: {save_dir}")
    return model.predict(
        source=source,
        conf=conf,
        iou=IOU,
        imgsz=IMGSZ,
        device=device,
        verbose=False,
        save=True,
        project=str(save_dir.parent),
        name=save_dir.name,
        exist_ok=False,
        show_labels=True,
        show_conf=True,
        show_boxes=True,
    )


def summarize_prediction_results(
    results: list[Any],
    image_paths: list[Path],
    split_lookup: dict[str, str],
    conf: float,
    model_name: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, float]]]:
    rows: list[dict[str, Any]] = []
    per_split: dict[str, dict[str, Any]] = {}
    per_image_max_conf: dict[str, dict[str, float]] = {}

    for split in {"val", "test", "train"}:
        split_images = [path for path in image_paths if split_lookup[str(path.resolve())] == split]
        if split_images:
            per_split[split] = {
                "model_name": model_name,
                "split": split,
                "conf": conf,
                "num_images_tested": len(split_images),
                "num_images_with_any_prediction": 0,
                "num_images_with_tungro_prediction": 0,
                "num_tungro_predictions": 0,
                "avg_tungro_conf": 0.0,
                "max_tungro_conf": 0.0,
                "num_no_detection_cases": 0,
                "train_or_eval_set_tungro_detectable": False,
            }

    for image_path, result in zip(image_paths, results):
        resolved = str(image_path.resolve())
        split = split_lookup[resolved]
        boxes = result.boxes
        class_ids = [int(value) for value in boxes.cls.tolist()] if boxes is not None and boxes.cls is not None else []
        confidences = [float(value) for value in boxes.conf.tolist()] if boxes is not None and boxes.conf is not None else []
        tungro_confidences = [confidence for class_id, confidence in zip(class_ids, confidences) if class_id == TUNGRO_CLASS_ID]
        any_prediction = len(class_ids) > 0
        has_tungro_prediction = len(tungro_confidences) > 0
        max_tungro_conf = max(tungro_confidences) if tungro_confidences else 0.0
        per_image_max_conf[resolved] = {"max_tungro_conf": max_tungro_conf}

        stats = per_split[split]
        if any_prediction:
            stats["num_images_with_any_prediction"] += 1
        if has_tungro_prediction:
            stats["num_images_with_tungro_prediction"] += 1
            stats["num_tungro_predictions"] += len(tungro_confidences)
            stats["avg_tungro_conf"] += sum(tungro_confidences)
            stats["max_tungro_conf"] = max(stats["max_tungro_conf"], max_tungro_conf)
        else:
            stats["num_no_detection_cases"] += 1

    for split, stats in per_split.items():
        if stats["num_tungro_predictions"] > 0:
            stats["avg_tungro_conf"] = stats["avg_tungro_conf"] / stats["num_tungro_predictions"]
            stats["train_or_eval_set_tungro_detectable"] = True
        rows.append(stats)
    return rows, per_split, per_image_max_conf


def get_tungro_gt_boxes(label_path: Path, image_size: tuple[int, int]) -> list[tuple[float, float, float, float]]:
    rows, _ = parse_label_file(label_path)
    gt_boxes: list[tuple[float, float, float, float]] = []
    width, height = image_size
    for row in rows:
        if row.class_id == TUNGRO_CLASS_ID:
            gt_boxes.append(normalized_box_to_xyxy(row, width, height))
    return gt_boxes


def draw_failure_visualization(
    image_path: Path,
    gt_boxes: list[tuple[float, float, float, float]],
    pred_boxes: list[tuple[float, float, float, float]],
    pred_confidences: list[float],
    out_path: Path,
    title: str,
) -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = load_font(16)
    for box in gt_boxes:
        draw.rectangle(box, outline=(0, 255, 0), width=3)
    for box, confidence in zip(pred_boxes, pred_confidences):
        draw.rectangle(box, outline=(255, 64, 64), width=3)
        label = f"pred {confidence:.3f}"
        text_box = draw.textbbox((box[0], max(0, box[1] - 18)), label, font=font)
        draw.rectangle(text_box, fill=(0, 0, 0))
        draw.text((text_box[0], text_box[1]), label, fill=(255, 64, 64), font=font)
    header_box = draw.textbbox((8, 8), title, font=font)
    draw.rectangle(header_box, fill=(0, 0, 0))
    draw.text((header_box[0], header_box[1]), title, fill=(255, 255, 255), font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, quality=92)


def analyze_failure_cases(
    results_conf025: list[Any],
    results_conf005: list[Any],
    image_paths: list[Path],
    split_lookup: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    low_conf_lookup = {str(path.resolve()): result for path, result in zip(image_paths, results_conf005)}

    for image_path, result_025 in zip(image_paths, results_conf025):
        resolved = str(image_path.resolve())
        split = split_lookup[resolved]
        label_path = DATASET_ROOT / "labels" / split / f"{image_path.stem}.txt"
        image = Image.open(image_path)
        gt_boxes = get_tungro_gt_boxes(label_path, image.size)
        pred_boxes = result_025.boxes
        pred_class_ids = [int(value) for value in pred_boxes.cls.tolist()] if pred_boxes is not None and pred_boxes.cls is not None else []
        pred_confidences = [float(value) for value in pred_boxes.conf.tolist()] if pred_boxes is not None and pred_boxes.conf is not None else []
        pred_xyxy = pred_boxes.xyxy.tolist() if pred_boxes is not None and pred_boxes.xyxy is not None else []
        pred_tungro_boxes = [tuple(map(float, box)) for box, class_id in zip(pred_xyxy, pred_class_ids) if class_id == TUNGRO_CLASS_ID]
        pred_tungro_conf = [confidence for confidence, class_id in zip(pred_confidences, pred_class_ids) if class_id == TUNGRO_CLASS_ID]

        low_result = low_conf_lookup[resolved]
        low_boxes = low_result.boxes
        low_class_ids = [int(value) for value in low_boxes.cls.tolist()] if low_boxes is not None and low_boxes.cls is not None else []
        low_confidences = [float(value) for value in low_boxes.conf.tolist()] if low_boxes is not None and low_boxes.conf is not None else []
        low_tungro_conf = [confidence for confidence, class_id in zip(low_confidences, low_class_ids) if class_id == TUNGRO_CLASS_ID]
        max_tungro_conf = max(low_tungro_conf) if low_tungro_conf else 0.0

        if pred_tungro_boxes:
            max_iou = max((compute_iou(gt_box, pred_box) for gt_box in gt_boxes for pred_box in pred_tungro_boxes), default=0.0)
            if len(pred_tungro_boxes) > max(1, len(gt_boxes) * 2):
                failure_type = "OVER_DETECTION"
                possible_reason = "too_many_tungro_boxes_conf025"
            elif max_iou < 0.3:
                failure_type = "BAD_LOCALIZATION"
                possible_reason = "tungro_boxes_do_not_align_with_gt"
            else:
                continue
        else:
            if any(class_id != TUNGRO_CLASS_ID for class_id in pred_class_ids):
                failure_type = "WRONG_CLASS"
                possible_reason = "other_class_predicted_without_tungro"
            elif low_tungro_conf:
                failure_type = "LOW_CONFIDENCE_ONLY"
                possible_reason = "tungro_found_below_conf025_only"
            else:
                failure_type = "NO_DETECTION"
                possible_reason = "no_tungro_boxes_even_at_conf005"

        vis_path = FAILURE_VIS_DIR / f"{split}_{image_path.name}"
        draw_failure_visualization(
            image_path=image_path,
            gt_boxes=gt_boxes,
            pred_boxes=pred_tungro_boxes,
            pred_confidences=pred_tungro_conf,
            out_path=vis_path,
            title=f"{split} {failure_type}",
        )
        rows.append(
            {
                "split": split,
                "image_name": image_path.name,
                "image_path": str(image_path.resolve()),
                "label_path": str(label_path.resolve()),
                "gt_tungro_bbox_count": len(gt_boxes),
                "pred_tungro_bbox_count_conf025": len(pred_tungro_boxes),
                "max_tungro_conf": max_tungro_conf,
                "failure_type": failure_type,
                "possible_reason": possible_reason,
                "visualization_path": str(vis_path.resolve()),
            }
        )
    return rows


def compute_detection_stats(model: YOLO, image_paths: list[Path], conf: float, device: str) -> dict[str, Any]:
    if not image_paths:
        return {
            "num_images_tested": 0,
            "num_images_with_tungro_prediction": 0,
            "num_no_detection_cases": 0,
        }
    results = model.predict(
        source=[str(path) for path in image_paths],
        conf=conf,
        iou=IOU,
        imgsz=IMGSZ,
        device=device,
        verbose=False,
        save=False,
    )
    with_tungro = 0
    no_detection = 0
    for result in results:
        boxes = result.boxes
        class_ids = [int(value) for value in boxes.cls.tolist()] if boxes is not None and boxes.cls is not None else []
        has_tungro = any(class_id == TUNGRO_CLASS_ID for class_id in class_ids)
        if has_tungro:
            with_tungro += 1
        else:
            no_detection += 1
    return {
        "num_images_tested": len(image_paths),
        "num_images_with_tungro_prediction": with_tungro,
        "num_no_detection_cases": no_detection,
    }


def compute_overfitting_risk(results_rows: list[dict[str, Any]], train_tungro_stats: dict[str, Any], test_tungro_stats: dict[str, Any]) -> tuple[str, bool]:
    if not results_rows:
        return "uncertain", True
    final_row = results_rows[-1]
    train_box_loss = float(final_row.get("train/box_loss", 0.0))
    val_box_loss = float(final_row.get("val/box_loss", 0.0))
    final_map50 = float(final_row.get("metrics/mAP50(B)", 0.0))
    train_detect_rate = (
        train_tungro_stats["num_images_with_tungro_prediction"] / train_tungro_stats["num_images_tested"]
        if train_tungro_stats["num_images_tested"]
        else 0.0
    )
    test_detect_rate = (
        test_tungro_stats["num_images_with_tungro_prediction"] / test_tungro_stats["num_images_tested"]
        if test_tungro_stats["num_images_tested"]
        else 0.0
    )
    generalization_still_weak = train_detect_rate - test_detect_rate >= 0.35
    if generalization_still_weak and final_map50 < 0.35:
        return "high", True
    if train_box_loss < val_box_loss * 0.8 or generalization_still_weak:
        return "medium", generalization_still_weak
    if final_map50 >= 0.35:
        return "low", False
    return "uncertain", generalization_still_weak


def load_results_csv(path: Path) -> list[dict[str, Any]]:
    rows = read_csv_rows(path)
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append({key.strip(): value for key, value in row.items()})
    return normalized


def to_float(value: Any) -> float | None:
    if value in (None, "", "None"):
        return None
    try:
        return float(value)
    except Exception:
        return None


def build_tungro_eval_rows(
    overall_rows: list[dict[str, Any]],
    per_class_rows: list[dict[str, Any]],
    conf025_stats_by_model_split: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    per_class_lookup = {(row["model_name"], row["dataset_split"], row["class_name"]): row for row in per_class_rows}
    rows: list[dict[str, Any]] = []
    for overall in overall_rows:
        model_name = overall["model_name"]
        split = overall["dataset_split"]
        key = (model_name, split, "tungro")
        class_row = per_class_lookup.get(key, {})
        split_summary = scan_result["split_summaries"][split]
        conf_stats = conf025_stats_by_model_split.get((model_name, split), {})
        rows.append(
            {
                "model_name": model_name,
                "dataset_split": split,
                "num_tungro_images": split_summary["tungro_images"],
                "num_tungro_bboxes": split_summary["tungro_bboxes"],
                "tungro_precision": class_row.get("precision"),
                "tungro_recall": class_row.get("recall"),
                "tungro_AP50": class_row.get("AP50"),
                "tungro_AP50_95": class_row.get("AP50_95"),
                "num_no_detection_cases": conf_stats.get("num_no_detection_cases"),
                "num_low_conf_cases": conf_stats.get("num_low_conf_cases"),
                "notes": conf_stats.get("notes", ""),
            }
        )
    return rows


def ensure_parent_dirs() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    VAL_PROJECT.mkdir(parents=True, exist_ok=True)


def assert_required_paths() -> None:
    required = [
        DATASET_ROOT,
        DATA_YAML,
        FIXED_DATASET_MANIFEST,
        POLICY_FIX_REPORT,
        ANNOTATION_POLICY_REPORT,
        BASELINE_RUN_DIR,
        BASELINE_WEIGHTS,
        BASELINE_DATA_YAML,
        BASELINE_ARGS_YAML,
        MODEL_SOURCE,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"Required paths missing: {missing}")


def cleanup_tmp_files() -> bool:
    leftovers = list(REPORT_DIR.rglob("*.tmp")) if REPORT_DIR.exists() else []
    return bool(leftovers)


def write_report(
    training_context: dict[str, Any],
    train_results_rows: list[dict[str, Any]],
    overall_rows: list[dict[str, Any]],
    per_class_rows: list[dict[str, Any]],
    tungro_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    conf_rows: list[dict[str, Any]],
    failure_rows: list[dict[str, Any]],
) -> None:
    best_epoch = None
    best_map50 = None
    if train_results_rows:
        best_row = max(train_results_rows, key=lambda row: float(row.get("metrics/mAP50(B)", 0.0)))
        best_epoch = best_row.get("epoch")
        best_map50 = best_row.get("metrics/mAP50(B)")

    val_row = next((row for row in overall_rows if row["model_name"] == "controlled_15epoch" and row["dataset_split"] == "val"), None)
    test_row = next((row for row in overall_rows if row["model_name"] == "controlled_15epoch" and row["dataset_split"] == "test"), None)
    baseline_test_row = next((row for row in overall_rows if row["model_name"] == "baseline_35N" and row["dataset_split"] == "test"), None)
    controlled_tungro_test = next(
        (row for row in tungro_rows if row["model_name"] == "controlled_15epoch" and row["dataset_split"] == "test"),
        None,
    )
    baseline_tungro_test = next(
        (row for row in tungro_rows if row["model_name"] == "baseline_35N" and row["dataset_split"] == "test"),
        None,
    )

    report = f"""# Phone-36Train-Controlled-Tungro-15Epoch Report

## Scope

- This round trained a controlled experimental model: `{"YES" if training_context["training_run_completed"] else "NO"}`
- Generated new formal weights: `NO`
- Generated new experimental weights: `{"YES" if training_context["training_run_completed"] else "NO"}`
- Overwrote existing weights: `NO`
- Modified backend: `NO`
- Modified frontend: `NO`
- Modified .env: `NO`
- Modified original dataset labels: `NO`
- Used derived dataset: `YES`
- Allow backend demo claim: `NO`
- Allow candidate claim: `NO`

## Training Context

- project_root: `{training_context["project_root"]}`
- training_project_root: `{training_context["training_project_root"]}`
- derived_dataset_root: `{training_context["derived_dataset_root"]}`
- derived_data_yaml_path: `{training_context["derived_data_yaml_path"]}`
- fixed_dataset_manifest_path: `{training_context["fixed_dataset_manifest_path"]}`
- annotation_policy_report_path: `{training_context["annotation_policy_report_path"]}`
- previous_policy_fix_report_path: `{training_context["previous_policy_fix_report_path"]}`
- baseline_model_path: `{training_context["baseline_model_path"]}`
- baseline_data_yaml_path: `{training_context["baseline_data_yaml_path"]}`
- baseline_run_id: `{training_context["baseline_run_id"]}`
- new_experiment_name: `{training_context["new_experiment_name"]}`
- python_version: `{training_context["python_version"]}`
- ultralytics_version: `{training_context["ultralytics_version"]}`
- torch_version: `{training_context["torch_version"]}`
- device: `{training_context["device"]}`
- gpu_name: `{training_context["gpu_name"]}`
- cuda_available: `{training_context["cuda_available"]}`
- seed: `{training_context["seed"]}`
- epochs: `{training_context["epochs"]}`
- imgsz: `{training_context["imgsz"]}`
- batch: `{training_context["batch"]}`
- optimizer: `{training_context["optimizer"]}`
- learning_rate: `{training_context["learning_rate"]}`
- pretrained_or_resume_source: `{training_context["pretrained_or_resume_source"]}`

## Derived Dataset Audit

- derived_data_yaml_pass: `{training_context["derived_data_yaml_pass"]}`
- tungro_class_id_confirmed: `{training_context["tungro_class_id_confirmed"]}`
- derived_label_sanitation_pass: `{training_context["derived_label_sanitation_pass"]}`
- tungro_eval_splits_ready: `{training_context.get("tungro_eval_splits_ready", False)}`
- bbox_out_of_bounds_count: `{training_context["bbox_out_of_bounds_count"]}`
- class_id_out_of_range_count: `{training_context["class_id_out_of_range_count"]}`
- non_positive_width_height_count: `{training_context["non_positive_width_height_count"]}`
- missing_label_count: `{training_context["missing_label_count"]}`
- missing_image_count: `{training_context["missing_image_count"]}`

## Blocking Reasons

{chr(10).join(f"- `{reason}`" for reason in training_context.get("block_reasons", ["none"]))}

## Dataset Distribution

- train_total_images: `{training_context["split_summaries"]["train"]["total_images"]}`
- val_total_images: `{training_context["split_summaries"]["val"]["total_images"]}`
- test_total_images: `{training_context["split_summaries"]["test"]["total_images"]}`
- train_total_bboxes: `{training_context["split_summaries"]["train"]["total_bboxes"]}`
- val_total_bboxes: `{training_context["split_summaries"]["val"]["total_bboxes"]}`
- test_total_bboxes: `{training_context["split_summaries"]["test"]["total_bboxes"]}`
- tungro_train_images: `{training_context["split_summaries"]["train"]["tungro_images"]}`
- tungro_val_images: `{training_context["split_summaries"]["val"]["tungro_images"]}`
- tungro_test_images: `{training_context["split_summaries"]["test"]["tungro_images"]}`
- tungro_train_bboxes: `{training_context["split_summaries"]["train"]["tungro_bboxes"]}`
- tungro_val_bboxes: `{training_context["split_summaries"]["val"]["tungro_bboxes"]}`
- tungro_test_bboxes: `{training_context["split_summaries"]["test"]["tungro_bboxes"]}`

## Controlled Training Run

- run_dir: `{training_context.get("run_dir", "MISSING")}`
- best_pt_exists: `{training_context.get("best_pt_exists", False)}`
- last_pt_exists: `{training_context.get("last_pt_exists", False)}`
- results_csv_exists: `{training_context.get("results_csv_exists", False)}`
- args_yaml_exists: `{training_context.get("args_yaml_exists", False)}`
- final_epoch: `{training_context.get("final_epoch", 0)}`
- best_epoch_by_map50: `{best_epoch}`
- best_epoch_map50: `{best_map50}`

## Controlled Validation Snapshot

- controlled val precision: `{val_row["precision"] if val_row else "MISSING"}`
- controlled val recall: `{val_row["recall"] if val_row else "MISSING"}`
- controlled val mAP50: `{val_row["mAP50"] if val_row else "MISSING"}`
- controlled val mAP50-95: `{val_row["mAP50_95"] if val_row else "MISSING"}`
- controlled test precision: `{test_row["precision"] if test_row else "MISSING"}`
- controlled test recall: `{test_row["recall"] if test_row else "MISSING"}`
- controlled test mAP50: `{test_row["mAP50"] if test_row else "MISSING"}`
- controlled test mAP50-95: `{test_row["mAP50_95"] if test_row else "MISSING"}`

## Baseline Reference

- historical 35N experimental mAP50: `0.38768203615854735`
- historical 35N Tungro per-class AP: `0.11919959830149554`
- strict baseline test mAP50 on derived dataset: `{baseline_test_row["mAP50"] if baseline_test_row else "MISSING"}`
- strict baseline Tungro AP50 on derived test: `{baseline_tungro_test["tungro_AP50"] if baseline_tungro_test else "MISSING"}`

## Tungro Outcome

- controlled test Tungro precision: `{controlled_tungro_test["tungro_precision"] if controlled_tungro_test else "MISSING"}`
- controlled test Tungro recall: `{controlled_tungro_test["tungro_recall"] if controlled_tungro_test else "MISSING"}`
- controlled test Tungro AP50: `{controlled_tungro_test["tungro_AP50"] if controlled_tungro_test else "MISSING"}`
- controlled test Tungro AP50-95: `{controlled_tungro_test["tungro_AP50_95"] if controlled_tungro_test else "MISSING"}`
- controlled test Tungro no-detection count @ conf=0.25: `{controlled_tungro_test["num_no_detection_cases"] if controlled_tungro_test else "MISSING"}`
- baseline test Tungro no-detection count @ conf=0.25: `{baseline_tungro_test["num_no_detection_cases"] if baseline_tungro_test else "MISSING"}`

## Confidence Sweep

- tungro_conf_sweep_completed: `{training_context["tungro_conf_sweep_completed"]}`
- output_csv: `{CONF_SWEEP_CSV.resolve()}`
- saved prediction dirs:
  - `{VAL_PRED_DIR.resolve()}`
  - `{TEST_PRED_DIR.resolve()}`
  - `{TUNGRO_CONF_DIRS[0.05].resolve()}`
  - `{TUNGRO_CONF_DIRS[0.10].resolve()}`
  - `{TUNGRO_CONF_DIRS[0.25].resolve()}`

## Failure Analysis

- failure_cases_analyzed: `{training_context["failure_cases_analyzed"]}`
- failure_case_count: `{len(failure_rows)}`
- failure_visualizations_dir: `{FAILURE_VIS_DIR.resolve()}`

## Overfitting Risk

- overfitting_risk: `{training_context["overfitting_risk"]}`
- generalization_still_weak: `{training_context["generalization_still_weak"]}`

## Gate

- phone_36_train_controlled_tungro_15epoch_gate: `{training_context["phone_36_train_controlled_tungro_15epoch_gate"]}`
- derived_data_yaml_pass: `{training_context["derived_data_yaml_pass"]}`
- derived_label_sanitation_pass: `{training_context["derived_label_sanitation_pass"]}`
- training_run_completed: `{training_context["training_run_completed"]}`
- validation_completed: `{training_context["validation_completed"]}`
- baseline_comparison_completed: `{training_context["baseline_comparison_completed"]}`
- tungro_conf_sweep_completed: `{training_context["tungro_conf_sweep_completed"]}`
- failure_cases_analyzed: `{training_context["failure_cases_analyzed"]}`
- tungro_AP50_improved: `{training_context["tungro_AP50_improved"]}`
- tungro_recall_improved: `{training_context["tungro_recall_improved"]}`
- tungro_no_detection_reduced: `{training_context["tungro_no_detection_reduced"]}`
- allow_next_full_training: `{training_context["allow_next_full_training"]}`
- allow_backend_demo_claim: `False`
- allow_candidate_claim: `False`
- next_allowed_stage: `{training_context["next_allowed_stage"]}`
- forbidden_stage: `{training_context["forbidden_stage"]}`
- atomic_write_used: `{training_context["atomic_write_used"]}`
- tmp_files_left: `{training_context["tmp_files_left"]}`

## Explicit Answers

1. 本轮是否确实使用 derived dataset？`{"YES" if training_context["used_derived_dataset"] else "NO"}`
2. derived data.yaml 是否通过？`{"YES" if training_context["derived_data_yaml_pass"] else "NO"}`
3. derived labels 是否还有 bbox 越界？`{"NO" if training_context["bbox_out_of_bounds_count"] == 0 else "YES"}`
4. 本轮是否完成 15 epoch controlled training？`{"YES" if training_context["training_run_completed"] else "NO"}`
5. 是否生成新实验权重？`{"YES" if training_context["training_run_completed"] else "NO"}`
6. 是否覆盖旧权重？`NO`
7. Tungro AP50 是否提升？`{training_context["tungro_AP50_improved"]}`
8. Tungro recall 是否提升？`{training_context["tungro_recall_improved"]}`
9. Tungro NO_DETECTION 是否减少？`{training_context["tungro_no_detection_reduced"]}`
10. 是否出现明显过拟合？`{"YES" if training_context["overfitting_risk"] == "high" else "NO"}`
11. 是否完成 baseline 对比？`{"YES" if training_context["baseline_comparison_completed"] else "NO"}`
12. 是否完成 Tungro failure case 分析？`{"YES" if training_context["failure_cases_analyzed"] else "NO"}`
13. 是否允许进入下一轮 full controlled training？`{"YES" if training_context["allow_next_full_training"] else "NO"}`
14. 是否允许 backend demo claim？`NO`
15. 是否允许 candidate claim？`NO`

## Final Boundary Sentence

本轮是 Tungro 标注策略修复后的 15 epoch 受控训练验证；用于判断修复后的派生数据集是否改善 Tungro 检出；不代表正式模型，不允许 backend demo claim，不允许 candidate claim。
"""
    atomic_write_text(REPORT_MD, report)


def main() -> int:
    os.chdir(ROOT)
    ensure_parent_dirs()
    assert_required_paths()
    data_yaml = load_data_yaml()
    global scan_result
    scan_result = scan_dataset(data_yaml)

    distribution_rows = scan_result["distribution_rows"]
    atomic_write_csv(
        DERIVED_DISTRIBUTION_CSV,
        distribution_rows,
        [
            "split",
            "class_id",
            "class_name",
            "images_with_class",
            "bbox_count",
            "total_images_in_split",
            "total_labels_in_split",
            "total_bboxes_in_split",
            "missing_label_count",
            "missing_image_count",
            "empty_label_count",
        ],
    )

    bbox_out_of_bounds_count = sum(
        count for key, count in scan_result["sanitation_issues"].items() if key.startswith("bbox_out_of_bounds")
    )
    class_id_out_of_range_count = sum(
        count for key, count in scan_result["sanitation_issues"].items() if key.startswith("class_id_out_of_range")
    )
    non_positive_width_height_count = sum(
        count for key, count in scan_result["sanitation_issues"].items() if key.startswith("non_positive_width_height")
    )
    missing_label_count = scan_result["sanitation_issues"].get("missing_label_count", 0)
    missing_image_count = scan_result["sanitation_issues"].get("missing_image_count", 0)

    device = "0" if torch.cuda.is_available() else "cpu"
    training_context: dict[str, Any] = {
        "project_root": str(PROJECT_ROOT.resolve()),
        "training_project_root": str(ROOT.resolve()),
        "derived_dataset_root": str(DATASET_ROOT.resolve()),
        "derived_data_yaml_path": str(DATA_YAML.resolve()),
        "derived_train_images_path": str((DATASET_ROOT / "images" / "train").resolve()),
        "derived_train_labels_path": str((DATASET_ROOT / "labels" / "train").resolve()),
        "derived_val_images_path": str((DATASET_ROOT / "images" / "val").resolve()),
        "derived_val_labels_path": str((DATASET_ROOT / "labels" / "val").resolve()),
        "derived_test_images_path": str((DATASET_ROOT / "images" / "test").resolve()),
        "derived_test_labels_path": str((DATASET_ROOT / "labels" / "test").resolve()),
        "fixed_dataset_manifest_path": str(FIXED_DATASET_MANIFEST.resolve()),
        "annotation_policy_report_path": str(ANNOTATION_POLICY_REPORT.resolve()),
        "previous_policy_fix_report_path": str(POLICY_FIX_REPORT.resolve()),
        "baseline_model_path": str(BASELINE_WEIGHTS.resolve()),
        "baseline_data_yaml_path": str(BASELINE_DATA_YAML.resolve()),
        "baseline_run_id": "Phone-35N / controlled_exp_phone_riceseg_v35m_holdout_applied_10epoch",
        "new_experiment_name": RUN_NAME,
        "python_version": sys.version.split()[0],
        "ultralytics_version": getattr(ultralytics, "__version__", "MISSING"),
        "torch_version": torch.__version__,
        "device": device,
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
        "cuda_available": torch.cuda.is_available(),
        "seed": SEED,
        "epochs": EPOCHS,
        "imgsz": IMGSZ,
        "batch": BATCH,
        "optimizer": "auto",
        "learning_rate": 0.003,
        "pretrained_or_resume_source": str(MODEL_SOURCE.resolve()),
        "used_derived_dataset": True,
        "derived_data_yaml_pass": scan_result["derived_data_yaml_pass"],
        "tungro_class_id_confirmed": scan_result["tungro_class_id_confirmed"],
        "derived_label_sanitation_pass": scan_result["derived_label_sanitation_pass"],
        "tungro_eval_splits_ready": (
            scan_result["split_summaries"]["val"]["tungro_images"] > 0 and scan_result["split_summaries"]["test"]["tungro_images"] > 0
        ),
        "bbox_out_of_bounds_count": bbox_out_of_bounds_count,
        "class_id_out_of_range_count": class_id_out_of_range_count,
        "non_positive_width_height_count": non_positive_width_height_count,
        "missing_label_count": missing_label_count,
        "missing_image_count": missing_image_count,
        "split_summaries": scan_result["split_summaries"],
        "training_run_completed": False,
        "validation_completed": False,
        "baseline_comparison_completed": False,
        "tungro_conf_sweep_completed": False,
        "failure_cases_analyzed": False,
        "run_dir": str(RUN_DIR.resolve()),
        "best_pt_exists": False,
        "last_pt_exists": False,
        "results_csv_exists": False,
        "args_yaml_exists": False,
        "final_epoch": 0,
        "overfitting_risk": "uncertain",
        "generalization_still_weak": True,
        "tungro_AP50_improved": "uncertain",
        "tungro_recall_improved": "uncertain",
        "tungro_no_detection_reduced": "uncertain",
        "block_reasons": [],
        "phone_36_train_controlled_tungro_15epoch_gate": "BLOCKED",
        "allow_next_full_training": False,
        "allow_backend_demo_claim": False,
        "allow_candidate_claim": False,
        "next_allowed_stage": "Phone-36Train-Controlled-Tungro-15Epoch-Retry",
        "forbidden_stage": "backend_demo_integration, candidate_claim",
        "atomic_write_used": True,
        "tmp_files_left": True,
    }

    if bbox_out_of_bounds_count > 0:
        training_context["block_reasons"].append(f"derived_bbox_out_of_bounds_count={bbox_out_of_bounds_count}")
    if not training_context["tungro_eval_splits_ready"]:
        training_context["block_reasons"].append(
            "derived_tungro_eval_splits_empty: val_tungro_images=0 and/or test_tungro_images=0"
        )
    if (
        not training_context["derived_data_yaml_pass"]
        or not training_context["derived_label_sanitation_pass"]
        or not training_context["tungro_eval_splits_ready"]
    ):
        training_context["tmp_files_left"] = cleanup_tmp_files()
        atomic_write_json(TRAINING_CONTEXT_JSON, training_context)
        write_report(training_context, [], [], [], [], [], [], [])
        return 2

    best_weights = run_train(device=device)
    training_context["training_run_completed"] = True
    training_context["run_dir"] = str(RUN_DIR.resolve())
    training_context["best_weights_path"] = str(best_weights.resolve())
    training_context["best_pt_exists"] = best_weights.exists()
    training_context["last_pt_exists"] = (RUN_DIR / "weights" / "last.pt").exists()
    training_context["results_csv_exists"] = (RUN_DIR / "results.csv").exists()
    training_context["args_yaml_exists"] = (RUN_DIR / "args.yaml").exists()

    train_results_rows = load_results_csv(RUN_DIR / "results.csv")
    training_context["final_epoch"] = int(float(train_results_rows[-1]["epoch"])) if train_results_rows else 0
    atomic_write_csv(TRAIN_METRICS_SUMMARY_CSV, train_results_rows, list(train_results_rows[0].keys()))

    baseline_overall_val, baseline_per_val = validate_model(
        BASELINE_WEIGHTS,
        model_name="baseline_35N",
        split="val",
        device=device,
        name_suffix="baseline_35n_val_on_v36_derived",
    )
    baseline_overall_test, baseline_per_test = validate_model(
        BASELINE_WEIGHTS,
        model_name="baseline_35N",
        split="test",
        device=device,
        name_suffix="baseline_35n_test_on_v36_derived",
    )
    controlled_overall_val, controlled_per_val = validate_model(
        best_weights,
        model_name="controlled_15epoch",
        split="val",
        device=device,
        name_suffix="controlled_15epoch_val_on_v36_derived",
    )
    controlled_overall_test, controlled_per_test = validate_model(
        best_weights,
        model_name="controlled_15epoch",
        split="test",
        device=device,
        name_suffix="controlled_15epoch_test_on_v36_derived",
    )
    overall_rows = [baseline_overall_val, baseline_overall_test, controlled_overall_val, controlled_overall_test]
    per_class_rows = baseline_per_val + baseline_per_test + controlled_per_val + controlled_per_test
    training_context["validation_completed"] = True
    atomic_write_csv(
        PER_CLASS_METRICS_CSV,
        per_class_rows,
        ["model_name", "dataset_split", "class_id", "class_name", "precision", "recall", "AP50", "AP50_95", "weights_path"],
    )

    baseline_model = YOLO(str(BASELINE_WEIGHTS))
    controlled_model = YOLO(str(best_weights))
    val_dir = DATASET_ROOT / "images" / "val"
    test_dir = DATASET_ROOT / "images" / "test"
    run_predict_save(controlled_model, str(val_dir), 0.25, VAL_PRED_DIR, device)
    run_predict_save(controlled_model, str(test_dir), 0.25, TEST_PRED_DIR, device)

    tungro_images_val = scan_result["tungro_images_by_split"]["val"]
    tungro_images_test = scan_result["tungro_images_by_split"]["test"]
    all_tungro_images = tungro_images_val + tungro_images_test
    split_lookup = {str(path.resolve()): "val" for path in tungro_images_val}
    split_lookup.update({str(path.resolve()): "test" for path in tungro_images_test})

    conf_rows: list[dict[str, Any]] = []
    controlled_conf_stats_by_split: dict[tuple[str, str], dict[str, Any]] = {}
    results_conf_cache: dict[float, list[Any]] = {}
    per_image_max_conf_by_conf: dict[float, dict[str, dict[str, float]]] = {}
    for conf in CONF_LIST:
        results = run_predict_save(
            controlled_model,
            [str(path) for path in all_tungro_images],
            conf,
            TUNGRO_CONF_DIRS[conf],
            device,
        )
        results_conf_cache[conf] = results
        rows, per_split_stats, per_image_max_conf = summarize_prediction_results(
            results=results,
            image_paths=all_tungro_images,
            split_lookup=split_lookup,
            conf=conf,
            model_name="controlled_15epoch",
        )
        conf_rows.extend(rows)
        per_image_max_conf_by_conf[conf] = per_image_max_conf
        for split, stats in per_split_stats.items():
            controlled_conf_stats_by_split[("controlled_15epoch", split, conf)] = stats

    baseline_conf_stats_by_split: dict[tuple[str, str], dict[str, Any]] = {}
    for split, split_images in [("val", tungro_images_val), ("test", tungro_images_test)]:
        stats = compute_detection_stats(baseline_model, split_images, conf=0.25, device=device)
        baseline_conf_stats_by_split[("baseline_35N", split)] = {
            **stats,
            "num_low_conf_cases": None,
            "notes": "strict comparison on derived dataset at conf=0.25",
        }

    for split in ("val", "test"):
        conf025 = controlled_conf_stats_by_split[("controlled_15epoch", split, 0.25)]
        conf005 = controlled_conf_stats_by_split[("controlled_15epoch", split, 0.05)]
        low_conf_cases = max(0, conf025["num_no_detection_cases"] - conf005["num_no_detection_cases"])
        controlled_conf_stats_by_split[("controlled_15epoch", split)] = {
            **conf025,
            "num_low_conf_cases": low_conf_cases,
            "notes": "strict comparison on derived dataset at conf=0.25; low_conf from conf0.05 delta",
        }

    atomic_write_csv(
        CONF_SWEEP_CSV,
        conf_rows,
        [
            "model_name",
            "split",
            "conf",
            "num_images_tested",
            "num_images_with_any_prediction",
            "num_images_with_tungro_prediction",
            "num_tungro_predictions",
            "avg_tungro_conf",
            "max_tungro_conf",
            "num_no_detection_cases",
            "train_or_eval_set_tungro_detectable",
        ],
    )
    training_context["tungro_conf_sweep_completed"] = True

    failure_rows = analyze_failure_cases(
        results_conf025=results_conf_cache[0.25],
        results_conf005=results_conf_cache[0.05],
        image_paths=all_tungro_images,
        split_lookup=split_lookup,
    )
    atomic_write_csv(
        FAILURE_CASES_CSV,
        failure_rows,
        [
            "split",
            "image_name",
            "image_path",
            "label_path",
            "gt_tungro_bbox_count",
            "pred_tungro_bbox_count_conf025",
            "max_tungro_conf",
            "failure_type",
            "possible_reason",
            "visualization_path",
        ],
    )
    training_context["failure_cases_analyzed"] = True

    all_tungro_eval_stats: dict[tuple[str, str], dict[str, Any]] = {}
    for split in ("val", "test"):
        all_tungro_eval_stats[("controlled_15epoch", split)] = controlled_conf_stats_by_split[("controlled_15epoch", split)]
        all_tungro_eval_stats[("baseline_35N", split)] = baseline_conf_stats_by_split[("baseline_35N", split)]

    tungro_rows = build_tungro_eval_rows(
        overall_rows=overall_rows,
        per_class_rows=per_class_rows,
        conf025_stats_by_model_split=all_tungro_eval_stats,
    )
    atomic_write_csv(
        TUNGRO_EVAL_SUMMARY_CSV,
        tungro_rows,
        [
            "model_name",
            "dataset_split",
            "num_tungro_images",
            "num_tungro_bboxes",
            "tungro_precision",
            "tungro_recall",
            "tungro_AP50",
            "tungro_AP50_95",
            "num_no_detection_cases",
            "num_low_conf_cases",
            "notes",
        ],
    )

    comparison_rows: list[dict[str, Any]] = []
    baseline_lookup = {(row["model_name"], row["dataset_split"]): row for row in overall_rows if row["model_name"] == "baseline_35N"}
    controlled_lookup = {(row["model_name"], row["dataset_split"]): row for row in overall_rows if row["model_name"] == "controlled_15epoch"}
    baseline_tungro_lookup = {(row["model_name"], row["dataset_split"]): row for row in tungro_rows if row["model_name"] == "baseline_35N"}
    controlled_tungro_lookup = {(row["model_name"], row["dataset_split"]): row for row in tungro_rows if row["model_name"] == "controlled_15epoch"}

    for split in ("val", "test"):
        b_overall = baseline_lookup[("baseline_35N", split)]
        c_overall = controlled_lookup[("controlled_15epoch", split)]
        for metric in ("mAP50", "mAP50_95", "precision", "recall"):
            baseline_value = float(b_overall[metric])
            controlled_value = float(c_overall[metric])
            comparison_rows.append(
                {
                    "metric": f"{split}_{metric}",
                    "baseline_value": baseline_value,
                    "controlled_15epoch_value": controlled_value,
                    "delta": controlled_value - baseline_value,
                    "comparison_dataset": f"derived_{split}",
                    "comparison_not_strict": False,
                    "notes": "same derived split, different training datasets by design",
                }
            )
        b_tungro = baseline_tungro_lookup[("baseline_35N", split)]
        c_tungro = controlled_tungro_lookup[("controlled_15epoch", split)]
        for metric in ("tungro_AP50", "tungro_AP50_95", "tungro_precision", "tungro_recall", "num_no_detection_cases"):
            baseline_value = to_float(b_tungro.get(metric))
            controlled_value = to_float(c_tungro.get(metric))
            delta = None if baseline_value is None or controlled_value is None else controlled_value - baseline_value
            comparison_rows.append(
                {
                    "metric": f"{split}_{metric}",
                    "baseline_value": baseline_value,
                    "controlled_15epoch_value": controlled_value,
                    "delta": delta,
                    "comparison_dataset": f"derived_{split}",
                    "comparison_not_strict": False,
                    "notes": "same derived split, strict eval comparison",
                }
            )
    atomic_write_csv(
        BASELINE_COMPARISON_CSV,
        comparison_rows,
        ["metric", "baseline_value", "controlled_15epoch_value", "delta", "comparison_dataset", "comparison_not_strict", "notes"],
    )
    training_context["baseline_comparison_completed"] = True

    train_tungro_stats = compute_detection_stats(
        controlled_model,
        scan_result["tungro_images_by_split"]["train"],
        conf=0.25,
        device=device,
    )
    test_tungro_stats = compute_detection_stats(controlled_model, tungro_images_test, conf=0.25, device=device)
    overfitting_risk, generalization_still_weak = compute_overfitting_risk(
        train_results_rows,
        train_tungro_stats=train_tungro_stats,
        test_tungro_stats=test_tungro_stats,
    )
    training_context["overfitting_risk"] = overfitting_risk
    training_context["generalization_still_weak"] = generalization_still_weak

    comparison_lookup = {row["metric"]: row for row in comparison_rows}
    training_context["tungro_AP50_improved"] = (
        comparison_lookup.get("test_tungro_AP50", {}).get("delta", 0) is not None
        and comparison_lookup.get("test_tungro_AP50", {}).get("delta", 0) > 0
    )
    training_context["tungro_recall_improved"] = (
        comparison_lookup.get("test_tungro_recall", {}).get("delta", 0) is not None
        and comparison_lookup.get("test_tungro_recall", {}).get("delta", 0) > 0
    )
    training_context["tungro_no_detection_reduced"] = (
        comparison_lookup.get("test_num_no_detection_cases", {}).get("delta", 0) is not None
        and comparison_lookup.get("test_num_no_detection_cases", {}).get("delta", 0) < 0
    )

    pass_conditions = all(
        [
            training_context["derived_data_yaml_pass"],
            training_context["derived_label_sanitation_pass"],
            training_context["training_run_completed"],
            training_context["validation_completed"],
            training_context["baseline_comparison_completed"],
            training_context["tungro_conf_sweep_completed"],
            training_context["failure_cases_analyzed"],
            (training_context["tungro_AP50_improved"] or training_context["tungro_recall_improved"]),
            (training_context["tungro_no_detection_reduced"] or controlled_tungro_lookup[("controlled_15epoch", "test")]["num_no_detection_cases"] <= 1),
            training_context["overfitting_risk"] != "high",
        ]
    )

    if pass_conditions:
        gate = "PASS"
        allow_next = True
        next_stage = "Phone-37Full-Controlled-Training-Or-Human-Review-Closure"
    elif training_context["training_run_completed"] and training_context["validation_completed"]:
        gate = "WARNING"
        allow_next = False
        next_stage = "Phone-36Tungro-Data-Or-Policy-Review"
    else:
        gate = "BLOCKED"
        allow_next = False
        next_stage = "Phone-36Train-Controlled-Tungro-15Epoch-Retry"

    training_context["phone_36_train_controlled_tungro_15epoch_gate"] = gate
    training_context["allow_next_full_training"] = allow_next
    training_context["next_allowed_stage"] = next_stage
    training_context["tmp_files_left"] = cleanup_tmp_files()

    atomic_write_json(TRAINING_CONTEXT_JSON, training_context)
    write_report(
        training_context=training_context,
        train_results_rows=train_results_rows,
        overall_rows=overall_rows,
        per_class_rows=per_class_rows,
        tungro_rows=tungro_rows,
        comparison_rows=comparison_rows,
        conf_rows=conf_rows,
        failure_rows=failure_rows,
    )
    return 0 if gate in {"PASS", "WARNING"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
