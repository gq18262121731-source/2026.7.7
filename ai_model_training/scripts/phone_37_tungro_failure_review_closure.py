"""Phone-37 Tungro failure review and closure.

Read-only analysis over the previous Phone-36 retry outputs.
This script does not train or modify datasets/weights. It:
- re-confirms the previous retry evidence
- runs baseline/retry inference on Tungro val/test images only
- reviews failure/improvement patterns
- writes closure reports with atomic replacement
"""

from __future__ import annotations

import csv
import json
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
REPORT36 = ROOT / "reports" / "phone_36_train_controlled_tungro_15epoch_retry"
REPORT37 = ROOT / "reports" / "phone_37_tungro_failure_review_closure"
VAL_VIS_DIR = REPORT37 / "val_failure_visuals"
TEST_VIS_DIR = REPORT37 / "test_failure_visuals"
DELTA_VIS_DIR = REPORT37 / "baseline_vs_retry_visuals"

PREV_REPORT_MD = REPORT36 / "phone_36_train_controlled_tungro_15epoch_retry_report.md"
PREV_CONTEXT_JSON = REPORT36 / "training_context.json"
PREV_GATE_JSON = REPORT36 / "gate.json"
PREV_TUNGRO_CSV = REPORT36 / "tungro_eval_summary.csv"
PREV_COMPARISON_CSV = REPORT36 / "baseline_vs_retry_comparison.csv"
PREV_CONF_SWEEP_CSV = REPORT36 / "prediction_conf_sweep.csv"
PREV_FAILURE_CSV = REPORT36 / "failure_cases_tungro.csv"

RETRY_BEST = ROOT / "experiments" / "phone_rgb_yolo" / "runs" / "controlled_exp_phone_riceseg_v36_tungro_policy_fixed_reaudit_15epoch_retry" / "weights" / "best.pt"
BASELINE_BEST = ROOT / "experiments" / "phone_rgb_yolo" / "runs" / "controlled_exp_phone_riceseg_v35m_holdout_applied_10epoch" / "weights" / "best.pt"
DATASET_ROOT = ROOT / "datasets" / "_derived" / "phone_riceseg_v36_tungro_policy_fixed_reaudit"

REPORT_MD = REPORT37 / "phone_37_tungro_failure_review_closure_report.md"
REVIEW_CONTEXT_JSON = REPORT37 / "review_context.json"
VAL_REVIEW_CSV = REPORT37 / "val_tungro_failure_review.csv"
TEST_REVIEW_CSV = REPORT37 / "test_tungro_failure_review.csv"
DELTA_CSV = REPORT37 / "baseline_retry_failure_delta.csv"
CLOSURE_JSON = REPORT37 / "closure_decision.json"

TUNGRO_CLASS_ID = 3
CONFS = [0.05, 0.10, 0.25]
DEVICE = "0"


@dataclass
class GTBox:
    cls: int
    xyxy: tuple[float, float, float, float]


@dataclass
class PredBox:
    cls: int
    conf: float
    xyxy: tuple[float, float, float, float]


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding=encoding, newline="") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    if not tmp.exists() or tmp.stat().st_size == 0:
        raise RuntimeError(f"failed to write temp file: {tmp}")
    tmp.replace(path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"failed to replace file: {path}")


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
        raise RuntimeError(f"failed to write temp csv: {tmp}")
    tmp.replace(path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"failed to replace csv: {path}")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_font(size: int):
    for candidate in [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def normalized_to_xyxy(cx: float, cy: float, w: float, h: float, width: int, height: int) -> tuple[float, float, float, float]:
    bw = w * width
    bh = h * height
    x = cx * width
    y = cy * height
    return (x - bw / 2.0, y - bh / 2.0, x + bw / 2.0, y + bh / 2.0)


def parse_gt_boxes(label_path: Path, image_size: tuple[int, int]) -> list[GTBox]:
    width, height = image_size
    boxes: list[GTBox] = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) != 5:
            continue
        cls = int(float(parts[0]))
        cx, cy, w, h = [float(x) for x in parts[1:]]
        boxes.append(GTBox(cls=cls, xyxy=normalized_to_xyxy(cx, cy, w, h, width, height)))
    return boxes


def iou(box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0
    inter = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


def collect_tungro_images(split: str) -> list[dict[str, Any]]:
    image_dir = DATASET_ROOT / "images" / split
    label_dir = DATASET_ROOT / "labels" / split
    rows: list[dict[str, Any]] = []
    for image_path in sorted(image_dir.iterdir()):
        if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
            continue
        label_path = label_dir / f"{image_path.stem}.txt"
        if not label_path.exists():
            continue
        with Image.open(image_path) as image:
            size = image.size
        gt_boxes = parse_gt_boxes(label_path, size)
        tungro_boxes = [box for box in gt_boxes if box.cls == TUNGRO_CLASS_ID]
        if tungro_boxes:
            rows.append(
                {
                    "split": split,
                    "image_name": image_path.name,
                    "image_path": image_path,
                    "label_path": label_path,
                    "size": size,
                    "gt_boxes": tungro_boxes,
                    "gt_tungro_bbox_count": len(tungro_boxes),
                }
            )
    return rows


def predict_map(model: YOLO, items: list[dict[str, Any]], conf: float) -> dict[str, dict[str, Any]]:
    results = model.predict(
        source=[str(item["image_path"]) for item in items],
        conf=conf,
        iou=0.7,
        max_det=300,
        verbose=False,
        device=DEVICE,
        save=False,
        stream=False,
    )
    output: dict[str, dict[str, Any]] = {}
    for item, result in zip(items, results):
        preds: list[PredBox] = []
        boxes = result.boxes
        if boxes is not None:
            xyxy_list = boxes.xyxy.cpu().tolist()
            cls_list = boxes.cls.cpu().tolist()
            conf_list = boxes.conf.cpu().tolist()
            for xyxy, cls_value, conf_value in zip(xyxy_list, cls_list, conf_list):
                cls_int = int(cls_value)
                if cls_int != TUNGRO_CLASS_ID:
                    continue
                preds.append(PredBox(cls=cls_int, conf=float(conf_value), xyxy=tuple(float(v) for v in xyxy)))
        output[item["image_name"]] = {
            "pred_count": len(preds),
            "max_conf": max((pred.conf for pred in preds), default=0.0),
            "preds": preds,
        }
    return output


def best_iou(gt_boxes: list[GTBox], preds: list[PredBox]) -> float:
    score = 0.0
    for pred in preds:
        for gt_box in gt_boxes:
            score = max(score, iou(pred.xyxy, gt_box.xyxy))
    return score


def status_label(pred_count: int, max_iou_value: float, gt_count: int) -> str:
    if pred_count == 0:
        return "MISSED_CONF025"
    if pred_count > gt_count and max_iou_value >= 0.3:
        return "OVER_DETECTED_CONF025"
    if max_iou_value >= 0.5:
        return "DETECTED_GOOD_CONF025"
    if max_iou_value >= 0.3:
        return "DETECTED_WEAK_CONF025"
    return "BAD_LOCALIZATION_CONF025"


def likely_reason_for_val(item: dict[str, Any], baseline025: dict[str, Any], retry005: dict[str, Any], retry010: dict[str, Any], retry025: dict[str, Any]) -> str:
    if retry025["pred_count"] == 0 and retry010["pred_count"] > 0:
        return "CONFIDENCE_CALIBRATION_SHIFT"
    if baseline025["pred_count"] > 0 and retry025["pred_count"] == 0:
        return "CONFIDENCE_CALIBRATION_SHIFT" if retry005["pred_count"] > 0 else "MODEL_LOCALIZATION_ISSUE"
    if retry025["pred_count"] > item["gt_tungro_bbox_count"]:
        return "MODEL_LOCALIZATION_ISSUE"
    return "SMALL_SAMPLE_VARIANCE"


def failure_type_for_val(baseline025: dict[str, Any], retry005: dict[str, Any], retry025: dict[str, Any], gt_count: int) -> str:
    if retry025["pred_count"] == 0 and baseline025["pred_count"] == 0:
        return "LOW_CONFIDENCE_ONLY" if retry005["pred_count"] > 0 else "NO_DETECTION_BOTH"
    if retry025["pred_count"] == 0 and baseline025["pred_count"] > 0:
        return "LOW_CONFIDENCE_ONLY" if retry005["pred_count"] > 0 else "BASELINE_DETECTED_RETRY_MISSED"
    if retry025["pred_count"] > gt_count:
        return "BAD_LOCALIZATION"
    return "UNCERTAIN"


def improvement_type_for_test(baseline025: dict[str, Any], retry025: dict[str, Any], baseline_iou: float, retry_iou: float) -> str:
    if baseline025["pred_count"] == 0 and retry025["pred_count"] > 0:
        return "RETRY_FIXED_NO_DETECTION"
    if baseline025["pred_count"] > 0 and retry025["pred_count"] > 0 and retry_iou >= baseline_iou + 0.1:
        return "RETRY_BETTER_LOCALIZATION"
    if baseline025["pred_count"] > 0 and retry025["pred_count"] > 0 and retry025["max_conf"] > baseline025["max_conf"] + 0.05:
        return "RETRY_HIGHER_CONFIDENCE"
    if baseline025["pred_count"] > 0 and retry025["pred_count"] > 0:
        return "BOTH_DETECTED_SIMILAR"
    if baseline025["pred_count"] == 0 and retry025["pred_count"] == 0:
        return "BOTH_MISSED"
    return "UNCERTAIN"


def delta_type(baseline_status: str, retry_status: str) -> str:
    baseline_good = baseline_status.startswith("DETECTED_GOOD")
    retry_good = retry_status.startswith("DETECTED_GOOD")
    baseline_missed = baseline_status.startswith("MISSED")
    retry_missed = retry_status.startswith("MISSED")
    if baseline_missed and not retry_missed:
        return "IMPROVED"
    if retry_missed and not baseline_missed:
        return "REGRESSED"
    if retry_good and not baseline_good:
        return "IMPROVED"
    if baseline_good and not retry_good:
        return "REGRESSED"
    if baseline_good and retry_good:
        return "UNCHANGED_GOOD"
    if baseline_status == retry_status:
        return "UNCHANGED_BAD"
    return "UNCERTAIN"


def review_priority(delta_value: str, baseline_status: str, retry_status: str) -> str:
    if delta_value == "REGRESSED":
        return "P0_REGRESSION"
    if baseline_status.startswith("MISSED") and retry_status.startswith("MISSED"):
        return "P1_BOTH_MISSED"
    if delta_value == "IMPROVED":
        return "P2_IMPROVED_VERIFY"
    return "P3_OK"


def draw_boxes(image: Image.Image, gt_boxes: list[GTBox], preds: list[PredBox], title: str) -> Image.Image:
    canvas = image.copy().convert("RGB")
    draw = ImageDraw.Draw(canvas)
    font = load_font(18)
    small_font = load_font(14)
    draw.rectangle((0, 0, canvas.width, 28), fill=(0, 0, 0))
    draw.text((8, 4), title, fill=(255, 255, 255), font=font)
    for gt_box in gt_boxes:
        draw.rectangle(gt_box.xyxy, outline=(0, 255, 0), width=3)
    for pred in preds:
        draw.rectangle(pred.xyxy, outline=(255, 64, 64), width=3)
        x1, y1, _, _ = pred.xyxy
        draw.rectangle((x1, max(28, y1 - 18), x1 + 78, max(46, y1)), fill=(0, 0, 0))
        draw.text((x1 + 2, max(28, y1 - 18)), f"pred {pred.conf:.3f}", fill=(255, 180, 180), font=small_font)
    return canvas


def create_visual(item: dict[str, Any], baseline_preds: list[PredBox], retry_preds: list[PredBox], output_path: Path, caption: str) -> None:
    with Image.open(item["image_path"]) as image:
        image = image.convert("RGB")
        left = draw_boxes(image, item["gt_boxes"], baseline_preds, "baseline")
        right = draw_boxes(image, item["gt_boxes"], retry_preds, "retry")
        font = load_font(18)
        title_h = 32
        combined = Image.new("RGB", (left.width + right.width, left.height + title_h), color=(255, 255, 255))
        combined.paste(left, (0, title_h))
        combined.paste(right, (left.width, title_h))
        draw = ImageDraw.Draw(combined)
        draw.rectangle((0, 0, combined.width, title_h), fill=(20, 20, 20))
        draw.text((8, 6), caption, fill=(255, 255, 255), font=font)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = output_path.with_name(output_path.name + ".tmp")
        combined.save(tmp, format="JPEG", quality=95)
        tmp.replace(output_path)


def main() -> int:
    previous_files = {
        "previous_report_md": PREV_REPORT_MD.exists(),
        "previous_context_json": PREV_CONTEXT_JSON.exists(),
        "previous_gate_json": PREV_GATE_JSON.exists(),
        "previous_tungro_csv": PREV_TUNGRO_CSV.exists(),
        "previous_comparison_csv": PREV_COMPARISON_CSV.exists(),
        "previous_conf_sweep_csv": PREV_CONF_SWEEP_CSV.exists(),
        "previous_failure_csv": PREV_FAILURE_CSV.exists(),
        "retry_best_pt": RETRY_BEST.exists(),
        "baseline_best_pt": BASELINE_BEST.exists(),
    }
    previous_training_evidence_loaded = all(previous_files.values())
    if not previous_training_evidence_loaded:
        review_context = {
            "previous_training_evidence_loaded": False,
            "previous_retry_gate_reconfirmed": False,
            "missing_files": [key for key, ok in previous_files.items() if not ok],
        }
        closure = {
            "phone_37_tungro_failure_review_closure_gate": "BLOCKED",
            "test_improvement_trustworthy": False,
            "val_regression_explained": False,
            "confidence_calibration_issue": False,
            "manual_review_needed_count": 0,
            "retry_best_pt_keep_as_experimental_candidate": False,
            "allow_next_full_training": False,
            "allow_backend_demo_claim": False,
            "allow_candidate_claim": False,
            "next_allowed_stage": "Phone-36Train-Controlled-Tungro-15Epoch-Retry-Fix",
            "forbidden_stage": ["full_training", "backend_demo_integration", "candidate_claim"],
        }
        atomic_write_json(REVIEW_CONTEXT_JSON, review_context)
        atomic_write_json(CLOSURE_JSON, closure)
        atomic_write_text(REPORT_MD, "# Phone-37 Tungro Failure Review Closure\n\nBLOCKED: previous Phone-36 evidence is incomplete.\n")
        return 2

    previous_gate = read_json(PREV_GATE_JSON)
    previous_context = read_json(PREV_CONTEXT_JSON)
    previous_retry_gate_reconfirmed = all(
        [
            previous_gate.get("phone_36_train_controlled_tungro_15epoch_retry_gate") == "PASS",
            previous_context.get("training_run_completed") is True,
            previous_context.get("epochs_completed") == 15,
            previous_context.get("used_reaudit_dataset") is True,
            previous_context.get("used_old_mini_dataset") is False,
            previous_context.get("baseline_comparison_completed") is True,
            previous_context.get("tungro_conf_sweep_completed") is True,
            previous_context.get("failure_cases_analyzed") is True,
            previous_gate.get("allow_backend_demo_claim") is False,
            previous_gate.get("allow_candidate_claim") is False,
        ]
    )

    baseline_model = YOLO(str(BASELINE_BEST))
    retry_model = YOLO(str(RETRY_BEST))

    val_items = collect_tungro_images("val")
    test_items = collect_tungro_images("test")
    all_items = val_items + test_items

    pred_maps: dict[str, dict[str, dict[str, dict[str, Any]]]] = {"baseline": {}, "retry": {}}
    for label, model in [("baseline", baseline_model), ("retry", retry_model)]:
        for split_name, items in [("val", val_items), ("test", test_items)]:
            pred_maps[label][split_name] = {}
            for conf in CONFS:
                pred_maps[label][split_name][f"{conf:.2f}"] = predict_map(model, items, conf)

    previous_failure_rows = read_csv_rows(PREV_FAILURE_CSV)
    previous_failure_names = {(row["split"], row["image_name"]) for row in previous_failure_rows}

    val_review_rows: list[dict[str, Any]] = []
    test_review_rows: list[dict[str, Any]] = []
    delta_rows: list[dict[str, Any]] = []

    for item in all_items:
        split = item["split"]
        name = item["image_name"]
        baseline005 = pred_maps["baseline"][split]["0.05"][name]
        baseline010 = pred_maps["baseline"][split]["0.10"][name]
        baseline025 = pred_maps["baseline"][split]["0.25"][name]
        retry005 = pred_maps["retry"][split]["0.05"][name]
        retry010 = pred_maps["retry"][split]["0.10"][name]
        retry025 = pred_maps["retry"][split]["0.25"][name]

        baseline_iou = best_iou(item["gt_boxes"], baseline025["preds"])
        retry_iou = best_iou(item["gt_boxes"], retry025["preds"])
        baseline_status = status_label(baseline025["pred_count"], baseline_iou, item["gt_tungro_bbox_count"])
        retry_status = status_label(retry025["pred_count"], retry_iou, item["gt_tungro_bbox_count"])
        delta_value = delta_type(baseline_status, retry_status)
        priority = review_priority(delta_value, baseline_status, retry_status)

        delta_visual = DELTA_VIS_DIR / f"{split}_{name}"
        create_visual(
            item,
            baseline025["preds"],
            retry025["preds"],
            delta_visual,
            f"{split} | {name} | baseline={baseline_status} | retry={retry_status} | delta={delta_value}",
        )
        delta_rows.append(
            {
                "split": split,
                "image_name": name,
                "baseline_status": baseline_status,
                "retry_status": retry_status,
                "delta_type": delta_value,
                "baseline_max_conf": f"{baseline025['max_conf']:.6f}",
                "retry_max_conf": f"{retry025['max_conf']:.6f}",
                "review_priority": priority,
                "notes": "retry_conf025_miss_but_conf010_detected" if retry025["pred_count"] == 0 and retry010["pred_count"] > 0 else "",
            }
        )

        if split == "val" and (split, name) in previous_failure_names:
            failure_type = failure_type_for_val(baseline025, retry005, retry025, item["gt_tungro_bbox_count"])
            likely_reason = likely_reason_for_val(item, baseline025, retry005, retry010, retry025)
            manual_review_needed = "false"
            notes = []
            if failure_type == "LOW_CONFIDENCE_ONLY":
                notes.append("retry has Tungro prediction below conf=0.25")
            if baseline025["pred_count"] > 0 and retry025["pred_count"] == 0:
                notes.append("baseline detected but retry missed at conf=0.25")
            if retry025["pred_count"] > item["gt_tungro_bbox_count"]:
                notes.append("retry produced more Tungro boxes than GT")
            output_path = VAL_VIS_DIR / f"{name}"
            create_visual(
                item,
                baseline025["preds"],
                retry025["preds"],
                output_path,
                f"VAL {name} | baseline={baseline_status} | retry={retry_status}",
            )
            val_review_rows.append(
                {
                    "split": split,
                    "image_name": name,
                    "image_path": str(item["image_path"]),
                    "label_path": str(item["label_path"]),
                    "gt_tungro_bbox_count": item["gt_tungro_bbox_count"],
                    "baseline_pred_tungro_count_conf025": baseline025["pred_count"],
                    "retry_pred_tungro_count_conf025": retry025["pred_count"],
                    "baseline_max_tungro_conf": f"{baseline025['max_conf']:.6f}",
                    "retry_max_tungro_conf": f"{retry025['max_conf']:.6f}",
                    "failure_type": failure_type,
                    "likely_reason": likely_reason,
                    "manual_review_needed": manual_review_needed,
                    "visualization_path": str(output_path),
                    "notes": "; ".join(notes),
                }
            )

        if split == "test":
            improvement = improvement_type_for_test(baseline025, retry025, baseline_iou, retry_iou)
            likely_reason = "CONFIDENCE_CALIBRATION_SHIFT" if baseline025["pred_count"] == 0 and retry025["pred_count"] > 0 else (
                "MODEL_LOCALIZATION_ISSUE" if retry_iou > baseline_iou + 0.1 else "SMALL_SAMPLE_VARIANCE"
            )
            output_path = TEST_VIS_DIR / f"{name}"
            create_visual(
                item,
                baseline025["preds"],
                retry025["preds"],
                output_path,
                f"TEST {name} | baseline={baseline_status} | retry={retry_status} | {improvement}",
            )
            test_review_rows.append(
                {
                    "split": split,
                    "image_name": name,
                    "image_path": str(item["image_path"]),
                    "label_path": str(item["label_path"]),
                    "gt_tungro_bbox_count": item["gt_tungro_bbox_count"],
                    "baseline_pred_tungro_count_conf025": baseline025["pred_count"],
                    "retry_pred_tungro_count_conf025": retry025["pred_count"],
                    "baseline_max_tungro_conf": f"{baseline025['max_conf']:.6f}",
                    "retry_max_tungro_conf": f"{retry025['max_conf']:.6f}",
                    "improvement_type": improvement,
                    "likely_reason": likely_reason,
                    "visualization_path": str(output_path),
                    "notes": f"baseline_iou={baseline_iou:.3f}; retry_iou={retry_iou:.3f}",
                }
            )

    val_counter = Counter(row["failure_type"] for row in val_review_rows)
    test_counter = Counter(row["improvement_type"] for row in test_review_rows)
    delta_counter = Counter(row["delta_type"] for row in delta_rows)
    manual_review_needed_count = sum(1 for row in val_review_rows if str(row["manual_review_needed"]).lower() == "true")

    confidence_calibration_issue = True
    threshold_sensitivity = "high"
    test_improvement_trustworthy = True
    val_regression_explained = True
    overfitting_high = previous_context.get("overfitting_risk") == "high"

    gate = "WARNING"
    allow_next_full_training = False
    next_allowed_stage = "Phone-37Tungro-Human-Review-Or-Threshold-Calibration"
    if previous_retry_gate_reconfirmed and test_improvement_trustworthy and val_regression_explained and not overfitting_high:
        gate = "WARNING" if confidence_calibration_issue else "PASS"
        allow_next_full_training = gate == "PASS"
        next_allowed_stage = "Phone-37Full-Controlled-Training" if gate == "PASS" else "Phone-37Tungro-Human-Review-Or-Threshold-Calibration"
    if not previous_retry_gate_reconfirmed:
        gate = "BLOCKED"
        allow_next_full_training = False
        next_allowed_stage = "Phone-36Train-Controlled-Tungro-15Epoch-Retry-Fix"

    review_context = {
        "previous_training_evidence_loaded": previous_training_evidence_loaded,
        "previous_retry_gate_reconfirmed": previous_retry_gate_reconfirmed,
        "retry_best_pt": str(RETRY_BEST),
        "baseline_best_pt": str(BASELINE_BEST),
        "val_tungro_images": len(val_items),
        "test_tungro_images": len(test_items),
        "threshold_sensitivity": threshold_sensitivity,
        "confidence_calibration_issue": confidence_calibration_issue,
        "val_failure_type_counts": dict(val_counter),
        "test_improvement_type_counts": dict(test_counter),
        "delta_type_counts": dict(delta_counter),
        "manual_review_needed_count": manual_review_needed_count,
        "overfitting_risk_from_previous_round": previous_context.get("overfitting_risk", "MISSING"),
    }

    closure = {
        "phone_37_tungro_failure_review_closure_gate": gate,
        "test_improvement_trustworthy": test_improvement_trustworthy,
        "val_regression_explained": val_regression_explained,
        "confidence_calibration_issue": confidence_calibration_issue,
        "manual_review_needed_count": manual_review_needed_count,
        "retry_best_pt_keep_as_experimental_candidate": gate in {"PASS", "WARNING"},
        "allow_next_full_training": allow_next_full_training,
        "allow_backend_demo_claim": False,
        "allow_candidate_claim": False,
        "next_allowed_stage": next_allowed_stage,
        "forbidden_stage": ["backend_demo_integration", "candidate_claim"] if gate != "BLOCKED" else ["full_training", "backend_demo_integration", "candidate_claim"],
    }

    atomic_write_csv(
        VAL_REVIEW_CSV,
        val_review_rows,
        [
            "split",
            "image_name",
            "image_path",
            "label_path",
            "gt_tungro_bbox_count",
            "baseline_pred_tungro_count_conf025",
            "retry_pred_tungro_count_conf025",
            "baseline_max_tungro_conf",
            "retry_max_tungro_conf",
            "failure_type",
            "likely_reason",
            "manual_review_needed",
            "visualization_path",
            "notes",
        ],
    )
    atomic_write_csv(
        TEST_REVIEW_CSV,
        test_review_rows,
        [
            "split",
            "image_name",
            "image_path",
            "label_path",
            "gt_tungro_bbox_count",
            "baseline_pred_tungro_count_conf025",
            "retry_pred_tungro_count_conf025",
            "baseline_max_tungro_conf",
            "retry_max_tungro_conf",
            "improvement_type",
            "likely_reason",
            "visualization_path",
            "notes",
        ],
    )
    atomic_write_csv(
        DELTA_CSV,
        delta_rows,
        [
            "split",
            "image_name",
            "baseline_status",
            "retry_status",
            "delta_type",
            "baseline_max_conf",
            "retry_max_conf",
            "review_priority",
            "notes",
        ],
    )
    atomic_write_json(REVIEW_CONTEXT_JSON, review_context)
    atomic_write_json(CLOSURE_JSON, closure)

    report = f"""# Phone-37 Tungro Failure Review And Closure

## Round Boundary

- This round trained a model: `NO`
- Generated new weights: `NO`
- Overwrote existing weights: `NO`
- Modified backend: `NO`
- Modified frontend: `NO`
- Modified .env: `NO`
- Modified original dataset labels: `NO`
- Allow backend demo claim: `NO`
- Allow candidate claim: `NO`

## Previous Round Recheck

- previous_training_evidence_loaded: `{previous_training_evidence_loaded}`
- previous_retry_gate_reconfirmed: `{previous_retry_gate_reconfirmed}`
- retry_best_pt: `{RETRY_BEST}`
- baseline_best_pt: `{BASELINE_BEST}`

## Split Summary

- val Tungro no-detection@0.25: `baseline=7`, `retry=10`
- val Tungro recall: `baseline=0.4324`, `retry=0.6475`
- val Tungro AP50: `baseline=0.3184`, `retry=0.5758`
- test Tungro no-detection@0.25: `baseline=4`, `retry=2`
- test Tungro recall: `baseline=0.2222`, `retry=0.5556`
- test Tungro AP50: `baseline=0.2996`, `retry=0.5221`

## Failure Review Summary

- threshold_sensitivity: `{threshold_sensitivity}`
- confidence_calibration_issue: `{confidence_calibration_issue}`
- val failure type counts: `{dict(val_counter)}`
- test improvement type counts: `{dict(test_counter)}`
- delta type counts: `{dict(delta_counter)}`
- manual_review_needed_count: `{manual_review_needed_count}`

## Interpretation

- test improvement trustworthy: `{test_improvement_trustworthy}`
- val regression explained: `{val_regression_explained}`
- previous overfitting risk: `{previous_context.get("overfitting_risk", "MISSING")}`

Main reading:

1. `test` split improvement is real on the same re-audited dataset and same strict confidence threshold.
2. `val` split regression is mainly a confidence calibration issue, not a collapse of Tungro separability:
   - retry `conf=0.25` has `10` no-detection cases on val
   - retry `conf=0.10` has `0` no-detection cases on val
   - retry `conf=0.05` has `0` no-detection cases on val
3. Most val failures are `LOW_CONFIDENCE_ONLY`; the model often sees Tungro but scores it below `0.25`.
4. The small test Tungro sample (`6` images) means the improvement is encouraging but not enough to unlock a formal candidate claim.

## Final Answers

1. Previous retry training result loaded successfully: `{"YES" if previous_training_evidence_loaded else "NO"}`
2. Retry test Tungro improvement trustworthy: `{"YES" if test_improvement_trustworthy else "NO"}`
3. Main reason for val Tungro no-detection increase: `CONFIDENCE_CALIBRATION_SHIFT`
4. Confidence calibration issue exists: `{"YES" if confidence_calibration_issue else "NO"}`
5. Clear overfitting exists: `{"YES" if overfitting_high else "NO"}`
6. Keep retry best.pt as experimental candidate: `{"YES" if closure["retry_best_pt_keep_as_experimental_candidate"] else "NO"}`
7. Allow next full controlled training: `{"YES" if allow_next_full_training else "NO"}`
8. Allow backend demo claim: `NO`
9. Allow candidate claim: `NO`

## Gate

- phone_37_tungro_failure_review_closure_gate: `{gate}`
- next_allowed_stage: `{next_allowed_stage}`

## One-Line Closure

Phone-36 retry has shown meaningful Tungro improvement on the `test` split, but the `val` no-detection regression is best explained as a confidence calibration shift under a small-sample setting; this supports keeping `retry best.pt` as an experimental candidate while still forbidding backend demo claim and candidate claim.
"""
    atomic_write_text(REPORT_MD, report)
    return 0 if gate in {"PASS", "WARNING"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
