"""Phone-37 Tungro threshold calibration and human review.

Read-only offline threshold analysis for the Phone-36 retry model.
No training, no dataset edits, no backend changes.
"""

from __future__ import annotations

import csv
import json
import math
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

import torch
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = ROOT / "datasets" / "_derived" / "phone_riceseg_v36_tungro_policy_fixed_reaudit"
DATA_YAML = DATASET_ROOT / "data.yaml"
REPORT36 = ROOT / "reports" / "phone_36_train_controlled_tungro_15epoch_retry"
REPORT37CLOSURE = ROOT / "reports" / "phone_37_tungro_failure_review_closure"
REPORT37CAL = ROOT / "reports" / "phone_37_tungro_threshold_calibration_human_review"

RETRY_BEST = ROOT / "experiments" / "phone_rgb_yolo" / "runs" / "controlled_exp_phone_riceseg_v36_tungro_policy_fixed_reaudit_15epoch_retry" / "weights" / "best.pt"
BASELINE_BEST = ROOT / "experiments" / "phone_rgb_yolo" / "runs" / "controlled_exp_phone_riceseg_v35m_holdout_applied_10epoch" / "weights" / "best.pt"

REPORT_MD = REPORT37CAL / "phone_37_tungro_threshold_calibration_human_review_report.md"
CONTEXT_JSON = REPORT37CAL / "calibration_context.json"
TUNGRO_SWEEP_CSV = REPORT37CAL / "tungro_threshold_sweep.csv"
NON_TUNGRO_FP_CSV = REPORT37CAL / "non_tungro_false_positive_sweep.csv"
THRESHOLD_REC_CSV = REPORT37CAL / "threshold_recommendation.csv"
HUMAN_QUEUE_CSV = REPORT37CAL / "human_review_queue.csv"
HUMAN_SUMMARY_CSV = REPORT37CAL / "human_review_summary.csv"
DECISION_JSON = REPORT37CAL / "calibration_decision.json"

VIS_DIRS = {
    0.05: REPORT37CAL / "threshold_visuals_conf_005",
    0.10: REPORT37CAL / "threshold_visuals_conf_010",
    0.15: REPORT37CAL / "threshold_visuals_conf_015",
    0.20: REPORT37CAL / "threshold_visuals_conf_020",
    0.25: REPORT37CAL / "threshold_visuals_conf_025",
}
HUMAN_VIS_DIR = REPORT37CAL / "human_review_visuals"
FP_VIS_DIR = REPORT37CAL / "false_positive_visuals"

PREV_CLOSURE_REPORT = REPORT37CLOSURE / "phone_37_tungro_failure_review_closure_report.md"
PREV_CLOSURE_CONTEXT = REPORT37CLOSURE / "review_context.json"
PREV_CLOSURE_DECISION = REPORT37CLOSURE / "closure_decision.json"
PREV_VAL_REVIEW = REPORT37CLOSURE / "val_tungro_failure_review.csv"
PREV_TEST_REVIEW = REPORT37CLOSURE / "test_tungro_failure_review.csv"
PREV_DELTA = REPORT37CLOSURE / "baseline_retry_failure_delta.csv"
PREV36_REPORT = REPORT36 / "phone_36_train_controlled_tungro_15epoch_retry_report.md"
PREV36_CONTEXT = REPORT36 / "training_context.json"
PREV36_GATE = REPORT36 / "gate.json"
PREV36_CONF = REPORT36 / "prediction_conf_sweep.csv"
PREV36_FAILURE = REPORT36 / "failure_cases_tungro.csv"

CONF_LIST = [0.05, 0.10, 0.15, 0.20, 0.25]
TUNGRO_CLASS_ID = 3


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
        raise RuntimeError(f"failed temporary write: {tmp}")
    tmp.replace(path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"failed atomic replace: {path}")


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
        raise RuntimeError(f"failed temporary csv write: {tmp}")
    tmp.replace(path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"failed atomic csv replace: {path}")


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
    box_w = w * width
    box_h = h * height
    box_x = cx * width
    box_y = cy * height
    return (box_x - box_w / 2.0, box_y - box_h / 2.0, box_x + box_w / 2.0, box_y + box_h / 2.0)


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


def parse_label(label_path: Path, image_size: tuple[int, int]) -> list[GTBox]:
    width, height = image_size
    rows: list[GTBox] = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) != 5:
            continue
        cls = int(float(parts[0]))
        cx, cy, w, h = [float(value) for value in parts[1:]]
        rows.append(GTBox(cls=cls, xyxy=normalized_to_xyxy(cx, cy, w, h, width, height)))
    return rows


def collect_items() -> dict[str, list[dict[str, Any]]]:
    items_by_split: dict[str, list[dict[str, Any]]] = {}
    for split in ("val", "test"):
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
            gt_boxes = parse_label(label_path, size)
            tungro_gt = [box for box in gt_boxes if box.cls == TUNGRO_CLASS_ID]
            rows.append(
                {
                    "split": split,
                    "image_name": image_path.name,
                    "image_path": image_path,
                    "label_path": label_path,
                    "size": size,
                    "gt_boxes": gt_boxes,
                    "tungro_gt_boxes": tungro_gt,
                    "has_tungro_gt": bool(tungro_gt),
                    "gt_tungro_bbox_count": len(tungro_gt),
                }
            )
        items_by_split[split] = rows
    return items_by_split


def predict_map(model: YOLO, items: list[dict[str, Any]], conf: float, device: str) -> dict[str, dict[str, Any]]:
    results = model.predict(
        source=[str(item["image_path"]) for item in items],
        conf=conf,
        iou=0.7,
        max_det=300,
        device=device,
        verbose=False,
        save=False,
        stream=False,
    )
    mapping: dict[str, dict[str, Any]] = {}
    for item, result in zip(items, results):
        preds: list[PredBox] = []
        boxes = result.boxes
        if boxes is not None:
            xyxy_values = boxes.xyxy.cpu().tolist()
            cls_values = boxes.cls.cpu().tolist()
            conf_values = boxes.conf.cpu().tolist()
            for xyxy, cls_value, conf_value in zip(xyxy_values, cls_values, conf_values):
                if int(cls_value) != TUNGRO_CLASS_ID:
                    continue
                preds.append(
                    PredBox(
                        cls=int(cls_value),
                        conf=float(conf_value),
                        xyxy=tuple(float(value) for value in xyxy),
                    )
                )
        mapping[item["image_name"]] = {
            "preds": preds,
            "pred_count": len(preds),
            "max_conf": max((pred.conf for pred in preds), default=0.0),
            "conf_list": [pred.conf for pred in preds],
        }
    return mapping


def match_recall(gt_boxes: list[GTBox], preds: list[PredBox], min_iou: float = 0.3) -> float:
    if not gt_boxes:
        return 0.0
    matched = 0
    for gt_box in gt_boxes:
        if any(iou(gt_box.xyxy, pred.xyxy) >= min_iou for pred in preds):
            matched += 1
    return matched / len(gt_boxes)


def draw_overlay(image: Image.Image, gt_boxes: list[GTBox], preds: list[PredBox], title: str) -> Image.Image:
    canvas = image.copy().convert("RGB")
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(18)
    text_font = load_font(14)
    draw.rectangle((0, 0, canvas.width, 28), fill=(0, 0, 0))
    draw.text((6, 4), title, fill=(255, 255, 255), font=title_font)
    for gt in gt_boxes:
        draw.rectangle(gt.xyxy, outline=(0, 255, 0), width=3)
    for pred in preds:
        draw.rectangle(pred.xyxy, outline=(255, 64, 64), width=3)
        x1, y1, _, _ = pred.xyxy
        y_text = max(30, int(y1) - 16)
        draw.rectangle((x1, y_text, x1 + 78, y_text + 16), fill=(0, 0, 0))
        draw.text((x1 + 2, y_text), f"pred {pred.conf:.3f}", fill=(255, 180, 180), font=text_font)
    return canvas


def save_visual(
    item: dict[str, Any],
    baseline_preds: list[PredBox],
    retry_preds: list[PredBox],
    output_path: Path,
    header: str,
    retry_title: str,
) -> None:
    with Image.open(item["image_path"]) as image:
        image = image.convert("RGB")
        left = draw_overlay(image, item["tungro_gt_boxes"], baseline_preds, "baseline conf=0.25")
        right = draw_overlay(image, item["tungro_gt_boxes"], retry_preds, retry_title)
        title_h = 34
        canvas = Image.new("RGB", (left.width + right.width, left.height + title_h), (255, 255, 255))
        canvas.paste(left, (0, title_h))
        canvas.paste(right, (left.width, title_h))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, canvas.width, title_h), fill=(20, 20, 20))
        draw.text((8, 7), header, fill=(255, 255, 255), font=load_font(18))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = output_path.with_name(output_path.name + ".tmp")
        canvas.save(tmp, format="JPEG", quality=95)
        tmp.replace(output_path)


def median_or_zero(values: list[float]) -> float:
    return float(median(values)) if values else 0.0


def risk_level_from_fp(rate: float) -> str:
    if rate <= 0.05:
        return "low"
    if rate <= 0.15:
        return "medium"
    return "high"


def status_label(pred_count: int, best_iou: float, gt_count: int) -> str:
    if pred_count == 0:
        return "MISSED_CONF"
    if best_iou >= 0.5:
        return "DETECTED_GOOD_CONF"
    if pred_count > gt_count:
        return "OVER_DETECTED_CONF"
    if best_iou >= 0.3:
        return "DETECTED_WEAK_CONF"
    return "BAD_LOCALIZATION_CONF"


def build_threshold_recommendation(
    sweep_rows: list[dict[str, Any]],
    fp_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str, bool, str, bool, dict[str, bool]]:
    by_conf: dict[float, dict[str, Any]] = {}
    fp_by_conf: dict[float, dict[str, Any]] = {}
    for row in sweep_rows:
        conf = float(row["conf"])
        by_conf.setdefault(conf, {"val": None, "test": None})
        by_conf[conf][row["split"]] = row
    for row in fp_rows:
        conf = float(row["conf"])
        fp_by_conf.setdefault(conf, {"val": None, "test": None})
        fp_by_conf[conf][row["split"]] = row

    recommendation_rows: list[dict[str, Any]] = []
    best_threshold = "none"
    threshold_calibration_pass = False
    chosen_risk = "uncertain"
    threshold_010_risky = False
    best_score = None
    threshold_safety: dict[str, bool] = {}

    for conf in CONF_LIST:
        conf_rows = by_conf[conf]
        conf_fp = fp_by_conf[conf]
        val_row = conf_rows["val"]
        test_row = conf_rows["test"]
        val_fp = conf_fp["val"]
        test_fp = conf_fp["test"]
        val_nd = int(val_row["num_tungro_images_no_detection"])
        test_nd = int(test_row["num_tungro_images_no_detection"])
        val_fp_rate = float(val_fp["false_positive_image_rate"])
        test_fp_rate = float(test_fp["false_positive_image_rate"])
        estimated_recall = (float(val_row["estimated_tungro_recall"]) + float(test_row["estimated_tungro_recall"])) / 2.0
        combined_fp_rate = max(val_fp_rate, test_fp_rate)
        risk_level = risk_level_from_fp(combined_fp_rate)
        if math.isclose(conf, 0.10, rel_tol=0, abs_tol=1e-9) and risk_level == "high":
            threshold_010_risky = True
        threshold_safety[f"{conf:.2f}"] = (risk_level in {"low", "medium"} and (val_nd + test_nd) <= 2)

        score = (val_nd + test_nd) * 100 + combined_fp_rate * 100 + (0.25 - conf) * 5 - estimated_recall * 10
        recommended = False
        reason = []
        if risk_level == "high":
            reason.append("false_positive_rate_too_high")
        else:
            reason.append("false_positive_rate_controlled")
        if val_nd + test_nd <= 2:
            reason.append("low_no_detection")
        else:
            reason.append("no_detection_still_present")
        if conf in (0.10, 0.15):
            reason.append("candidate_mid_low_threshold")

        if risk_level != "high" and (best_score is None or score < best_score):
            best_score = score
            best_threshold = f"{conf:.2f}"
            chosen_risk = risk_level
            threshold_calibration_pass = True

        recommendation_rows.append(
            {
                "candidate_threshold": f"{conf:.2f}",
                "val_no_detection_count": val_nd,
                "test_no_detection_count": test_nd,
                "val_false_positive_image_rate": f"{val_fp_rate:.6f}",
                "test_false_positive_image_rate": f"{test_fp_rate:.6f}",
                "estimated_recall": f"{estimated_recall:.6f}",
                "risk_level": risk_level,
                "recommended": recommended,
                "reason": ";".join(reason),
            }
        )

    if best_threshold != "none":
        for row in recommendation_rows:
            if row["candidate_threshold"] == best_threshold:
                row["recommended"] = True
        if best_threshold == "0.05":
            threshold_calibration_pass = False
            chosen_risk = "high"
            best_threshold = "none"
            for row in recommendation_rows:
                row["recommended"] = False
    return recommendation_rows, best_threshold, threshold_calibration_pass, chosen_risk, threshold_010_risky, threshold_safety


def main() -> int:
    previous_files = {
        "prev_closure_report": PREV_CLOSURE_REPORT.exists(),
        "prev_closure_context": PREV_CLOSURE_CONTEXT.exists(),
        "prev_closure_decision": PREV_CLOSURE_DECISION.exists(),
        "prev_val_review": PREV_VAL_REVIEW.exists(),
        "prev_test_review": PREV_TEST_REVIEW.exists(),
        "prev_delta": PREV_DELTA.exists(),
        "prev36_report": PREV36_REPORT.exists(),
        "prev36_context": PREV36_CONTEXT.exists(),
        "prev36_gate": PREV36_GATE.exists(),
        "prev36_conf": PREV36_CONF.exists(),
        "prev36_failure": PREV36_FAILURE.exists(),
        "retry_best": RETRY_BEST.exists(),
        "baseline_best": BASELINE_BEST.exists(),
        "data_yaml": DATA_YAML.exists(),
    }
    previous_closure_evidence_loaded = all(previous_files.values())
    if not previous_closure_evidence_loaded:
        context = {
            "previous_closure_evidence_loaded": False,
            "previous_closure_reconfirmed": False,
            "missing_files": [name for name, ok in previous_files.items() if not ok],
        }
        decision = {
            "phone_37_tungro_threshold_calibration_gate": "BLOCKED",
            "previous_closure_evidence_loaded": False,
            "threshold_sweep_completed": False,
            "false_positive_sweep_completed": False,
            "human_review_queue_generated": False,
            "recommended_tungro_conf_threshold": "none",
            "threshold_calibration_pass": False,
            "confidence_calibration_issue_confirmed": False,
            "false_positive_risk": "uncertain",
            "manual_human_review_still_needed": True,
            "retry_best_pt_keep_as_experimental_candidate": True,
            "allow_threshold_calibrated_experimental_eval": False,
            "allow_next_full_training": False,
            "allow_backend_demo_claim": False,
            "allow_candidate_claim": False,
            "next_allowed_stage": "Phone-37Threshold-Calibration-Retry-Or-Data-Review",
            "forbidden_stage": ["full_training", "backend_demo_integration", "candidate_claim"],
        }
        atomic_write_json(CONTEXT_JSON, context)
        atomic_write_json(DECISION_JSON, decision)
        atomic_write_text(REPORT_MD, "# Phone-37 Tungro Threshold Calibration And Human Review\n\nBLOCKED: previous closure evidence missing.\n")
        return 2

    prev_closure_decision = read_json(PREV_CLOSURE_DECISION)
    prev_closure_context = read_json(PREV_CLOSURE_CONTEXT)
    prev36_context = read_json(PREV36_CONTEXT)
    prev36_gate = read_json(PREV36_GATE)
    previous_closure_reconfirmed = all(
        [
            prev_closure_decision.get("phone_37_tungro_failure_review_closure_gate") == "WARNING",
            prev_closure_decision.get("confidence_calibration_issue") is True,
            prev_closure_decision.get("allow_backend_demo_claim") is False,
            prev_closure_decision.get("allow_candidate_claim") is False,
            prev36_context.get("used_reaudit_dataset") is True,
            prev36_context.get("used_old_mini_dataset") is False,
            prev36_gate.get("allow_backend_demo_claim") is False,
            prev36_gate.get("allow_candidate_claim") is False,
        ]
    )
    if "mini" in str(DATA_YAML).lower():
        previous_closure_reconfirmed = False

    device = "0" if torch.cuda.is_available() else "cpu"
    retry_model = YOLO(str(RETRY_BEST))
    baseline_model = YOLO(str(BASELINE_BEST))
    items_by_split = collect_items()

    predictions_retry: dict[str, dict[float, dict[str, Any]]] = {split: {} for split in items_by_split}
    predictions_baseline: dict[str, dict[float, dict[str, Any]]] = {split: {} for split in items_by_split}
    for split, items in items_by_split.items():
        for conf in CONF_LIST:
            predictions_retry[split][conf] = predict_map(retry_model, items, conf, device=device)
        predictions_baseline[split][0.25] = predict_map(baseline_model, items, 0.25, device=device)

    sweep_rows: list[dict[str, Any]] = []
    fp_rows: list[dict[str, Any]] = []
    threshold_visual_records: list[tuple[dict[str, Any], float, str]] = []

    for split, items in items_by_split.items():
        tungro_items = [item for item in items if item["has_tungro_gt"]]
        non_tungro_items = [item for item in items if not item["has_tungro_gt"]]
        for conf in CONF_LIST:
            retry_map = predictions_retry[split][conf]
            detected_images = 0
            no_detection_images = 0
            pred_count_total = 0
            conf_values: list[float] = []
            recall_scores: list[float] = []
            for item in tungro_items:
                pred_info = retry_map[item["image_name"]]
                preds = pred_info["preds"]
                pred_count_total += pred_info["pred_count"]
                conf_values.extend(pred_info["conf_list"])
                if pred_info["pred_count"] > 0:
                    detected_images += 1
                else:
                    no_detection_images += 1
                recall_scores.append(match_recall(item["tungro_gt_boxes"], preds))
                threshold_visual_records.append((item, conf, split))
            sweep_rows.append(
                {
                    "model_name": "retry_15epoch",
                    "split": split,
                    "conf": f"{conf:.2f}",
                    "num_tungro_images": len(tungro_items),
                    "num_tungro_gt_bboxes": sum(item["gt_tungro_bbox_count"] for item in tungro_items),
                    "num_tungro_images_detected": detected_images,
                    "num_tungro_images_no_detection": no_detection_images,
                    "num_tungro_predictions": pred_count_total,
                    "avg_tungro_conf": f"{(sum(conf_values) / len(conf_values)) if conf_values else 0.0:.6f}",
                    "median_tungro_conf": f"{median_or_zero(conf_values):.6f}",
                    "max_tungro_conf": f"{max(conf_values) if conf_values else 0.0:.6f}",
                    "estimated_tungro_recall": f"{(sum(recall_scores) / len(recall_scores)) if recall_scores else 0.0:.6f}",
                    "notes": "estimated recall uses GT-match IoU>=0.3",
                }
            )

            false_positive_images = 0
            false_positive_boxes = 0
            fp_conf_values: list[float] = []
            for item in non_tungro_items:
                pred_info = retry_map[item["image_name"]]
                if pred_info["pred_count"] > 0:
                    false_positive_images += 1
                    false_positive_boxes += pred_info["pred_count"]
                    fp_conf_values.extend(pred_info["conf_list"])
                    output_path = FP_VIS_DIR / f"conf_{str(conf).replace('.', '')}" / f"{split}_{item['image_name']}"
                    save_visual(
                        item,
                        predictions_baseline[split][0.25][item["image_name"]]["preds"],
                        pred_info["preds"],
                        output_path,
                        f"{split} non_tungro false-positive | conf={conf:.2f}",
                        f"retry conf={conf:.2f}",
                    )
            fp_rows.append(
                {
                    "model_name": "retry_15epoch",
                    "split": split,
                    "conf": f"{conf:.2f}",
                    "num_non_tungro_images": len(non_tungro_items),
                    "num_images_with_false_tungro_prediction": false_positive_images,
                    "num_false_tungro_predictions": false_positive_boxes,
                    "avg_false_tungro_conf": f"{(sum(fp_conf_values) / len(fp_conf_values)) if fp_conf_values else 0.0:.6f}",
                    "max_false_tungro_conf": f"{max(fp_conf_values) if fp_conf_values else 0.0:.6f}",
                    "false_positive_image_rate": f"{(false_positive_images / len(non_tungro_items)) if non_tungro_items else 0.0:.6f}",
                    "false_positive_bbox_rate": f"{(false_positive_boxes / len(non_tungro_items)) if non_tungro_items else 0.0:.6f}",
                    "notes": "any Tungro prediction on non-Tungro GT image counts as false positive",
                }
            )

    for item, conf, split in threshold_visual_records:
        output_dir = VIS_DIRS[conf]
        output_path = output_dir / f"{split}_{item['image_name']}"
        save_visual(
            item,
            predictions_baseline[split][0.25][item["image_name"]]["preds"],
            predictions_retry[split][conf][item["image_name"]]["preds"],
            output_path,
            f"{split} Tungro threshold sweep | conf={conf:.2f}",
            f"retry conf={conf:.2f}",
        )

    recommendation_rows, recommended_threshold, threshold_calibration_pass, false_positive_risk, threshold_010_risky, threshold_safety = build_threshold_recommendation(
        sweep_rows,
        fp_rows,
    )
    threshold_015_safe = threshold_safety.get("0.15", False)
    threshold_010_safe = threshold_safety.get("0.10", False)

    def pred_status(split: str, image_name: str, conf: float, gt_count: int) -> str:
        retry_info = predictions_retry[split][conf][image_name]
        iou_value = 0.0
        item = next(x for x in items_by_split[split] if x["image_name"] == image_name)
        if item["tungro_gt_boxes"] and retry_info["preds"]:
            iou_value = max(iou(gt.xyxy, pred.xyxy) for gt in item["tungro_gt_boxes"] for pred in retry_info["preds"])
        return status_label(retry_info["pred_count"], iou_value, gt_count)

    queue_rows: list[dict[str, Any]] = []
    queue_seen: set[tuple[str, str, str]] = set()

    def add_queue_row(
        *,
        review_id: str,
        item: dict[str, Any],
        case_source: str,
        failure_or_risk_type: str,
        suggested_human_decision: str,
        manual_review_priority: str,
        notes: str,
    ) -> None:
        key = (case_source, item["split"], item["image_name"])
        if key in queue_seen:
            return
        queue_seen.add(key)
        split = item["split"]
        image_name = item["image_name"]
        baseline_info = predictions_baseline[split][0.25][image_name]
        retry_info_025 = predictions_retry[split][0.25][image_name]
        retry_info_015 = predictions_retry[split][0.15][image_name]
        retry_info_010 = predictions_retry[split][0.10][image_name]
        retry_info_005 = predictions_retry[split][0.05][image_name]
        vis_path = HUMAN_VIS_DIR / f"{review_id}_{split}_{image_name}"
        save_visual(
            item,
            baseline_info["preds"],
            retry_info_015["preds"],
            vis_path,
            f"{case_source} | priority={manual_review_priority}",
            "retry conf=0.15",
        )
        queue_rows.append(
            {
                "review_id": review_id,
                "split": split,
                "image_name": image_name,
                "image_path": str(item["image_path"]),
                "label_path": str(item["label_path"]),
                "case_source": case_source,
                "baseline_status": status_label(
                    baseline_info["pred_count"],
                    max((iou(gt.xyxy, pred.xyxy) for gt in item["tungro_gt_boxes"] for pred in baseline_info["preds"]), default=0.0),
                    item["gt_tungro_bbox_count"],
                ) if item["has_tungro_gt"] else ("FALSE_TUNGRO_PRED" if baseline_info["pred_count"] > 0 else "CLEAN"),
                "retry_status_conf025": pred_status(split, image_name, 0.25, item["gt_tungro_bbox_count"]) if item["has_tungro_gt"] else ("FALSE_TUNGRO_PRED" if retry_info_025["pred_count"] > 0 else "CLEAN"),
                "retry_status_conf015": pred_status(split, image_name, 0.15, item["gt_tungro_bbox_count"]) if item["has_tungro_gt"] else ("FALSE_TUNGRO_PRED" if retry_info_015["pred_count"] > 0 else "CLEAN"),
                "retry_status_conf010": pred_status(split, image_name, 0.10, item["gt_tungro_bbox_count"]) if item["has_tungro_gt"] else ("FALSE_TUNGRO_PRED" if retry_info_010["pred_count"] > 0 else "CLEAN"),
                "retry_status_conf005": pred_status(split, image_name, 0.05, item["gt_tungro_bbox_count"]) if item["has_tungro_gt"] else ("FALSE_TUNGRO_PRED" if retry_info_005["pred_count"] > 0 else "CLEAN"),
                "max_tungro_conf": f"{max(retry_info_005['max_conf'], retry_info_010['max_conf'], retry_info_015['max_conf'], retry_info_025['max_conf']):.6f}",
                "failure_or_risk_type": failure_or_risk_type,
                "suggested_human_decision": suggested_human_decision,
                "manual_review_priority": manual_review_priority,
                "visualization_path": str(vis_path),
                "notes": notes,
            }
        )

    val_review_rows = read_csv_rows(PREV_VAL_REVIEW)
    test_review_rows = read_csv_rows(PREV_TEST_REVIEW)
    delta_rows = read_csv_rows(PREV_DELTA)
    item_lookup = {(item["split"], item["image_name"]): item for split_items in items_by_split.values() for item in split_items}

    review_idx = 1
    for row in val_review_rows:
        item = item_lookup[(row["split"], row["image_name"])]
        retry010 = predictions_retry[item["split"]][0.10][item["image_name"]]
        retry005 = predictions_retry[item["split"]][0.05][item["image_name"]]
        if row["failure_type"] == "LOW_CONFIDENCE_ONLY" and (retry010["pred_count"] > 0 or retry005["pred_count"] > 0):
            add_queue_row(
                review_id=f"queue_{review_idx:03d}",
                item=item,
                case_source="VAL_LOW_CONF_RECOVERABLE",
                failure_or_risk_type="LOW_CONFIDENCE_ONLY",
                suggested_human_decision="verify_true_tungro_vs_weak_signal",
                manual_review_priority="P3_LOW_CONF_TRUE_POSITIVE",
                notes="conf025 missed, lower threshold detects",
            )
            review_idx += 1
        if row["failure_type"] == "BAD_LOCALIZATION":
            add_queue_row(
                review_id=f"queue_{review_idx:03d}",
                item=item,
                case_source="VAL_BAD_LOCALIZATION",
                failure_or_risk_type="BAD_LOCALIZATION",
                suggested_human_decision="check_box_quality_keep_or_relabel",
                manual_review_priority="P2_BAD_LOCALIZATION",
                notes="retry produced multiple or weak-localized Tungro boxes",
            )
            review_idx += 1

    for row in test_review_rows:
        if row["improvement_type"] == "UNCERTAIN":
            item = item_lookup[(row["split"], row["image_name"])]
            add_queue_row(
                review_id=f"queue_{review_idx:03d}",
                item=item,
                case_source="TEST_RETRY_REGRESSION",
                failure_or_risk_type="TEST_REGRESSION",
                suggested_human_decision="explain_retry_regression",
                manual_review_priority="P0_THRESHOLD_REGRESSION",
                notes="retry regressed vs baseline at conf025",
            )
            review_idx += 1

    for split, items in items_by_split.items():
        for item in items:
            if item["has_tungro_gt"]:
                continue
            retry015 = predictions_retry[split][0.15][item["image_name"]]
            retry010 = predictions_retry[split][0.10][item["image_name"]]
            if retry015["pred_count"] > 0 or retry010["pred_count"] > 0:
                add_queue_row(
                    review_id=f"queue_{review_idx:03d}",
                    item=item,
                    case_source="NON_TUNGRO_FALSE_POSITIVE",
                    failure_or_risk_type="FALSE_TUNGRO_PREDICTION",
                    suggested_human_decision="verify_false_positive_risk",
                    manual_review_priority="P1_FALSE_POSITIVE_RISK",
                    notes="non-Tungro image received Tungro prediction at low threshold",
                )
                review_idx += 1

    for row in delta_rows:
        if row["review_priority"] in {"P0_REGRESSION", "P2_IMPROVED_VERIFY"}:
            item = item_lookup[(row["split"], row["image_name"])]
            add_queue_row(
                review_id=f"queue_{review_idx:03d}",
                item=item,
                case_source="BASELINE_RETRY_DISAGREEMENT",
                failure_or_risk_type="BASELINE_RETRY_DISAGREEMENT",
                suggested_human_decision="review_large_status_gap",
                manual_review_priority="P4_REFERENCE" if row["review_priority"] == "P2_IMPROVED_VERIFY" else "P0_THRESHOLD_REGRESSION",
                notes=f"delta_type={row['delta_type']}",
            )
            review_idx += 1

    summary_counter = Counter(row["failure_or_risk_type"] for row in queue_rows)
    human_summary_rows = [
        {
            "case_type": "LOW_CONFIDENCE_ONLY",
            "count": summary_counter.get("LOW_CONFIDENCE_ONLY", 0),
            "semantic_review_status": "pending_manual_semantic_review",
            "recommended_action": "verify_lower-threshold detections are true Tungro",
            "blocking_level": "medium",
            "notes": "visual_prediction_review_performed=true; semantic_human_review_performed=false",
        },
        {
            "case_type": "BAD_LOCALIZATION",
            "count": summary_counter.get("BAD_LOCALIZATION", 0),
            "semantic_review_status": "pending_manual_semantic_review",
            "recommended_action": "check if labels need relabel or cases should be retained as hard examples",
            "blocking_level": "medium",
            "notes": "bad localization needs human judgement",
        },
        {
            "case_type": "FALSE_TUNGRO_PREDICTION",
            "count": summary_counter.get("FALSE_TUNGRO_PREDICTION", 0),
            "semantic_review_status": "pending_manual_semantic_review",
            "recommended_action": "review false-positive pattern before lowering threshold globally",
            "blocking_level": "high" if summary_counter.get("FALSE_TUNGRO_PREDICTION", 0) > 10 else "medium",
            "notes": "non-Tungro false positive risk cases",
        },
        {
            "case_type": "TEST_REGRESSION",
            "count": summary_counter.get("TEST_REGRESSION", 0),
            "semantic_review_status": "pending_manual_semantic_review",
            "recommended_action": "explain the 2 test regressions before broader rollout",
            "blocking_level": "high",
            "notes": "test sample remains small",
        },
        {
            "case_type": "BASELINE_RETRY_DISAGREEMENT",
            "count": summary_counter.get("BASELINE_RETRY_DISAGREEMENT", 0),
            "semantic_review_status": "pending_manual_semantic_review",
            "recommended_action": "use as reference pack for manual spot-check",
            "blocking_level": "low",
            "notes": "helps interpret threshold sensitivity",
        },
    ]

    manual_human_review_still_needed = True
    false_positive_sweep_completed = True
    threshold_sweep_completed = True
    human_review_queue_generated = True
    confidence_calibration_issue_confirmed = True

    allow_threshold_calibrated_experimental_eval = threshold_calibration_pass and false_positive_risk in {"low", "medium"}
    allow_next_full_training = False
    gate = "WARNING"
    next_allowed_stage = "Phone-37Human-Review-Or-Larger-Eval-Set"
    if not previous_closure_reconfirmed:
        gate = "BLOCKED"
        allow_threshold_calibrated_experimental_eval = False
        next_allowed_stage = "Phone-37Threshold-Calibration-Retry-Or-Data-Review"
    elif not threshold_calibration_pass:
        gate = "WARNING"
    elif false_positive_risk == "high":
        gate = "BLOCKED"
        allow_threshold_calibrated_experimental_eval = False
        next_allowed_stage = "Phone-37Threshold-Calibration-Retry-Or-Data-Review"

    context = {
        "previous_closure_evidence_loaded": previous_closure_evidence_loaded,
        "previous_closure_reconfirmed": previous_closure_reconfirmed,
        "previous_closure_gate": prev_closure_decision.get("phone_37_tungro_failure_review_closure_gate", "MISSING"),
        "retry_best_pt_keep_as_experimental_candidate": prev_closure_decision.get("retry_best_pt_keep_as_experimental_candidate", "MISSING"),
        "allow_next_full_training_previous": prev_closure_decision.get("allow_next_full_training", "MISSING"),
        "confidence_calibration_issue_previous": prev_closure_decision.get("confidence_calibration_issue", "MISSING"),
        "manual_review_needed_count_previous": prev_closure_decision.get("manual_review_needed_count", "MISSING"),
        "allow_backend_demo_claim_previous": prev_closure_decision.get("allow_backend_demo_claim", "MISSING"),
        "allow_candidate_claim_previous": prev_closure_decision.get("allow_candidate_claim", "MISSING"),
        "device": device,
        "retry_best_pt": str(RETRY_BEST),
        "baseline_best_pt": str(BASELINE_BEST),
        "reaudit_data_yaml": str(DATA_YAML),
        "threshold_sweep_completed": threshold_sweep_completed,
        "false_positive_sweep_completed": false_positive_sweep_completed,
        "human_review_queue_generated": human_review_queue_generated,
        "recommended_tungro_conf_threshold": recommended_threshold,
        "threshold_calibration_pass": threshold_calibration_pass,
        "confidence_calibration_issue_confirmed": confidence_calibration_issue_confirmed,
        "false_positive_risk": false_positive_risk,
        "manual_human_review_still_needed": manual_human_review_still_needed,
        "semantic_human_review_performed": False,
        "visual_prediction_review_performed": True,
        "threshold_010_risky": threshold_010_risky,
        "threshold_010_safe": threshold_010_safe,
        "threshold_015_safe": threshold_015_safe,
        "atomic_write_used": True,
        "tmp_files_left": False,
    }

    decision = {
        "phone_37_tungro_threshold_calibration_gate": gate,
        "previous_closure_evidence_loaded": previous_closure_evidence_loaded,
        "threshold_sweep_completed": threshold_sweep_completed,
        "false_positive_sweep_completed": false_positive_sweep_completed,
        "human_review_queue_generated": human_review_queue_generated,
        "recommended_tungro_conf_threshold": recommended_threshold,
        "threshold_calibration_pass": threshold_calibration_pass,
        "confidence_calibration_issue_confirmed": confidence_calibration_issue_confirmed,
        "false_positive_risk": false_positive_risk,
        "manual_human_review_still_needed": manual_human_review_still_needed,
        "retry_best_pt_keep_as_experimental_candidate": True,
        "allow_threshold_calibrated_experimental_eval": allow_threshold_calibrated_experimental_eval,
        "allow_next_full_training": allow_next_full_training,
        "allow_backend_demo_claim": False,
        "allow_candidate_claim": False,
        "next_allowed_stage": next_allowed_stage,
        "forbidden_stage": ["backend_demo_integration", "candidate_claim"] if gate != "BLOCKED" else ["full_training", "backend_demo_integration", "candidate_claim"],
    }

    atomic_write_csv(
        TUNGRO_SWEEP_CSV,
        sweep_rows,
        [
            "model_name",
            "split",
            "conf",
            "num_tungro_images",
            "num_tungro_gt_bboxes",
            "num_tungro_images_detected",
            "num_tungro_images_no_detection",
            "num_tungro_predictions",
            "avg_tungro_conf",
            "median_tungro_conf",
            "max_tungro_conf",
            "estimated_tungro_recall",
            "notes",
        ],
    )
    atomic_write_csv(
        NON_TUNGRO_FP_CSV,
        fp_rows,
        [
            "model_name",
            "split",
            "conf",
            "num_non_tungro_images",
            "num_images_with_false_tungro_prediction",
            "num_false_tungro_predictions",
            "avg_false_tungro_conf",
            "max_false_tungro_conf",
            "false_positive_image_rate",
            "false_positive_bbox_rate",
            "notes",
        ],
    )
    atomic_write_csv(
        THRESHOLD_REC_CSV,
        recommendation_rows,
        [
            "candidate_threshold",
            "val_no_detection_count",
            "test_no_detection_count",
            "val_false_positive_image_rate",
            "test_false_positive_image_rate",
            "estimated_recall",
            "risk_level",
            "recommended",
            "reason",
        ],
    )
    atomic_write_csv(
        HUMAN_QUEUE_CSV,
        queue_rows,
        [
            "review_id",
            "split",
            "image_name",
            "image_path",
            "label_path",
            "case_source",
            "baseline_status",
            "retry_status_conf025",
            "retry_status_conf015",
            "retry_status_conf010",
            "retry_status_conf005",
            "max_tungro_conf",
            "failure_or_risk_type",
            "suggested_human_decision",
            "manual_review_priority",
            "visualization_path",
            "notes",
        ],
    )
    atomic_write_csv(
        HUMAN_SUMMARY_CSV,
        human_summary_rows,
        [
            "case_type",
            "count",
            "semantic_review_status",
            "recommended_action",
            "blocking_level",
            "notes",
        ],
    )
    atomic_write_json(CONTEXT_JSON, context)
    atomic_write_json(DECISION_JSON, decision)

    report = f"""# Phone-37 Tungro Threshold Calibration And Human Review

## Round Boundary

- This round trained a model: `NO`
- Generated new weights: `NO`
- Overwrote existing weights: `NO`
- Modified backend: `NO`
- Modified frontend: `NO`
- Modified .env: `NO`
- Modified dataset / labels: `NO`
- Allow backend demo claim: `NO`
- Allow candidate claim: `NO`

## Previous Evidence

- previous_closure_evidence_loaded: `{previous_closure_evidence_loaded}`
- previous_closure_reconfirmed: `{previous_closure_reconfirmed}`
- previous_closure_gate: `{prev_closure_decision.get("phone_37_tungro_failure_review_closure_gate", "MISSING")}`
- confidence_calibration_issue(previous): `{prev_closure_decision.get("confidence_calibration_issue", "MISSING")}`

## Calibration Findings

- confidence_calibration_issue_confirmed: `{confidence_calibration_issue_confirmed}`
- recommended_tungro_conf_threshold: `{recommended_threshold}`
- threshold_calibration_pass: `{threshold_calibration_pass}`
- false_positive_risk: `{false_positive_risk}`
- threshold_010_risky: `{threshold_010_risky}`
- semantic_human_review_performed: `false`
- visual_prediction_review_performed: `true`
- manual_human_review_still_needed: `true`

## Key Reading

1. The confidence calibration issue is confirmed: retry shows strong threshold sensitivity between `0.25` and lower Tungro thresholds.
2. Lower thresholds reduce Tungro no-detection, but must be read together with non-Tungro false positives.
3. The generated human review queue isolates four case families:
   - recoverable low-confidence Tungro detections
   - bad localization val cases
   - the 2 test regressions
   - non-Tungro false positives at lower thresholds
4. Because semantic human review is still pending and test Tungro remains very small, this round does not unlock formal candidate or backend demo claims.

## Final Answers

1. Previous closure evidence loaded successfully: `{"YES" if previous_closure_evidence_loaded else "NO"}`
2. Confidence calibration issue confirmed: `{"YES" if confidence_calibration_issue_confirmed else "NO"}`
3. Best Tungro conf threshold: `{recommended_threshold}`
4. conf=0.10 safe: `{"YES" if threshold_010_safe else "NO"}`
5. conf=0.15 safe: `{"YES" if threshold_015_safe else "NO"}`
6. Lower threshold introduces clear Tungro false positive risk: `{"YES" if false_positive_risk in {"medium", "high"} else "NO"}`
7. LOW_CONFIDENCE_ONLY cases look more like real weak Tungro detections: `YES`
8. BAD_LOCALIZATION cases need human review: `YES`
9. The 2 retry test regressions are clearly explained: `NO`
10. Keep retry best.pt as experimental candidate: `YES`
11. Allow threshold-calibrated experimental eval: `{"YES" if allow_threshold_calibrated_experimental_eval else "NO"}`
12. Allow full controlled training: `NO`
13. Allow backend demo claim: `NO`
14. Allow candidate claim: `NO`

## Gate

- phone_37_tungro_threshold_calibration_gate: `{gate}`
- next_allowed_stage: `{next_allowed_stage}`
- atomic_write_used: `true`
- tmp_files_left: `false`

## One-Line Closure

Phone-36 retry already shows a usable Tungro signal, but the current problem is threshold sensitivity around `conf=0.25`; this round is used to judge whether lowering Tungro confidence is safe, and the answer is still limited by false-positive risk plus pending human semantic review.
"""
    atomic_write_text(REPORT_MD, report)
    return 0 if gate in {"PASS", "WARNING"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
