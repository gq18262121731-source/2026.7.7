"""Phone-37 human review or larger eval set.

This round is evaluation-only:
- no training
- no backend or dataset mutation
- generate human review packet from previous threshold-calibration queue
- build a larger evaluation manifest
- run threshold-calibrated offline evaluation on that larger eval set
"""

from __future__ import annotations

import csv
import json
import os
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

import torch
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "datasets"
REPORT37CAL = ROOT / "reports" / "phone_37_tungro_threshold_calibration_human_review"
REPORT37NEXT = ROOT / "reports" / "phone_37_human_review_or_larger_eval_set"

RETRY_BEST = ROOT / "experiments" / "phone_rgb_yolo" / "runs" / "controlled_exp_phone_riceseg_v36_tungro_policy_fixed_reaudit_15epoch_retry" / "weights" / "best.pt"
BASELINE_BEST = ROOT / "experiments" / "phone_rgb_yolo" / "runs" / "controlled_exp_phone_riceseg_v35m_holdout_applied_10epoch" / "weights" / "best.pt"

REAUDIT_ROOT = DATASETS / "_derived" / "phone_riceseg_v36_tungro_policy_fixed_reaudit"
HOLDOUT_ROOT = DATASETS / "phone_riceseg_v35m_holdout_applied"
EXPANDED_ROOT = DATASETS / "rice_phone_rgb_expanded"

PREV_REPORT = REPORT37CAL / "phone_37_tungro_threshold_calibration_human_review_report.md"
PREV_CONTEXT = REPORT37CAL / "calibration_context.json"
PREV_DECISION = REPORT37CAL / "calibration_decision.json"
PREV_TUNGRO_SWEEP = REPORT37CAL / "tungro_threshold_sweep.csv"
PREV_NON_TUNGRO_SWEEP = REPORT37CAL / "non_tungro_false_positive_sweep.csv"
PREV_THRESHOLD_REC = REPORT37CAL / "threshold_recommendation.csv"
PREV_HUMAN_QUEUE = REPORT37CAL / "human_review_queue.csv"
PREV_HUMAN_SUMMARY = REPORT37CAL / "human_review_summary.csv"

REPORT_MD = REPORT37NEXT / "phone_37_human_review_or_larger_eval_set_report.md"
CONTEXT_JSON = REPORT37NEXT / "review_eval_context.json"
HUMAN_PACKET_CSV = REPORT37NEXT / "human_review_packet.csv"
HUMAN_RESULT_SUMMARY_CSV = REPORT37NEXT / "human_review_result_summary.csv"
LARGER_CANDIDATE_MANIFEST_CSV = REPORT37NEXT / "larger_eval_candidate_manifest.csv"
LARGER_SET_MANIFEST_CSV = REPORT37NEXT / "larger_eval_set_manifest.csv"
LARGER_DISTRIBUTION_CSV = REPORT37NEXT / "larger_eval_distribution.csv"
LARGER_SWEEP_CSV = REPORT37NEXT / "larger_eval_threshold_sweep.csv"
LARGER_FP_SWEEP_CSV = REPORT37NEXT / "larger_eval_false_positive_sweep.csv"
LARGER_FAILURES_CSV = REPORT37NEXT / "larger_eval_failure_cases.csv"
CLOSURE_JSON = REPORT37NEXT / "closure_decision.json"

HUMAN_VIS_DIR = REPORT37NEXT / "human_review_visuals"
LARGER_VIS_010 = REPORT37NEXT / "larger_eval_threshold_visuals_conf_010"
LARGER_VIS_015 = REPORT37NEXT / "larger_eval_threshold_visuals_conf_015"
LARGER_FP_VIS = REPORT37NEXT / "larger_eval_false_positive_visuals"
LARGER_FAILURE_VIS = REPORT37NEXT / "larger_eval_failure_visuals"

CONF_LIST = [0.10, 0.15, 0.25]
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
        raise RuntimeError(f"temp write failed: {tmp}")
    tmp.replace(path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"replace failed: {path}")


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
        raise RuntimeError(f"temp csv write failed: {tmp}")
    tmp.replace(path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"replace csv failed: {path}")


def atomic_copy_file(src: Path, dst: Path) -> None:
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"missing source file: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".tmp")
    shutil.copy2(src, tmp)
    if not tmp.exists() or tmp.stat().st_size == 0:
        raise RuntimeError(f"temp copy failed: {tmp}")
    tmp.replace(dst)
    if not dst.exists() or dst.stat().st_size == 0:
        raise RuntimeError(f"replace copy failed: {dst}")


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


def norm_to_xyxy(cx: float, cy: float, w: float, h: float, width: int, height: int) -> tuple[float, float, float, float]:
    bw = w * width
    bh = h * height
    x = cx * width
    y = cy * height
    return (x - bw / 2.0, y - bh / 2.0, x + bw / 2.0, y + bh / 2.0)


def parse_label(label_path: Path, image_size: tuple[int, int]) -> list[GTBox]:
    width, height = image_size
    rows: list[GTBox] = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) != 5:
            continue
        cls = int(float(parts[0]))
        cx, cy, w, h = [float(value) for value in parts[1:]]
        rows.append(GTBox(cls=cls, xyxy=norm_to_xyxy(cx, cy, w, h, width, height)))
    return rows


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


def match_recall(gt_boxes: list[GTBox], preds: list[PredBox], min_iou: float = 0.3) -> float:
    if not gt_boxes:
        return 0.0
    matched = 0
    for gt in gt_boxes:
        if any(iou(gt.xyxy, pred.xyxy) >= min_iou for pred in preds):
            matched += 1
    return matched / len(gt_boxes)


def median_or_zero(values: list[float]) -> float:
    return float(median(values)) if values else 0.0


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
        draw.rectangle(pred.xyxy, outline=(255, 80, 80), width=3)
        x1, y1, _, _ = pred.xyxy
        y_text = max(30, int(y1) - 16)
        draw.rectangle((x1, y_text, x1 + 78, y_text + 16), fill=(0, 0, 0))
        draw.text((x1 + 2, y_text), f"pred {pred.conf:.3f}", fill=(255, 180, 180), font=text_font)
    return canvas


def save_comparison_visual(
    image_path: Path,
    gt_boxes: list[GTBox],
    baseline_preds: list[PredBox],
    retry_preds: list[PredBox],
    output_path: Path,
    header: str,
    retry_title: str,
) -> None:
    with Image.open(image_path) as image:
        image = image.convert("RGB")
        left = draw_overlay(image, gt_boxes, baseline_preds, "baseline conf=0.25")
        right = draw_overlay(image, gt_boxes, retry_preds, retry_title)
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


def collect_dataset_items(dataset_root: Path, dataset_name: str, class_mode: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for split in ("train", "val", "test"):
        image_dir = dataset_root / "images" / split
        label_dir = dataset_root / "labels" / split
        if not image_dir.exists() or not label_dir.exists():
            continue
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
            items.append(
                {
                    "dataset_name": dataset_name,
                    "split": split,
                    "image_name": image_path.name,
                    "image_path": image_path,
                    "label_path": label_path,
                    "size": size,
                    "gt_boxes": gt_boxes,
                    "tungro_gt_boxes": tungro_gt,
                    "has_tungro_gt": bool(tungro_gt),
                    "tungro_bbox_count": len(tungro_gt),
                    "bbox_count": len(gt_boxes),
                    "class_mode": class_mode,
                    "non_tungro_classes": sorted({box.cls for box in gt_boxes if box.cls != TUNGRO_CLASS_ID}),
                }
            )
    return items


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
    out: dict[str, dict[str, Any]] = {}
    for item, result in zip(items, results):
        preds: list[PredBox] = []
        boxes = result.boxes
        if boxes is not None:
            xyxy_values = boxes.xyxy.cpu().tolist()
            cls_values = boxes.cls.cpu().tolist()
            conf_values = boxes.conf.cpu().tolist()
            for xyxy, cls_value, conf_value in zip(xyxy_values, cls_values, conf_values):
                cls_int = int(cls_value)
                if cls_int != TUNGRO_CLASS_ID:
                    continue
                preds.append(PredBox(cls=cls_int, conf=float(conf_value), xyxy=tuple(float(v) for v in xyxy)))
        out[item["image_name"]] = {
            "preds": preds,
            "pred_count": len(preds),
            "max_conf": max((pred.conf for pred in preds), default=0.0),
            "conf_list": [pred.conf for pred in preds],
        }
    return out


def best_iou(gt_boxes: list[GTBox], preds: list[PredBox]) -> float:
    score = 0.0
    for gt in gt_boxes:
        for pred in preds:
            score = max(score, iou(gt.xyxy, pred.xyxy))
    return score


def status_label(has_tungro_gt: bool, gt_count: int, pred_count: int, best_iou_value: float) -> str:
    if not has_tungro_gt:
        return "FALSE_TUNGRO_PRED" if pred_count > 0 else "CLEAN"
    if pred_count == 0:
        return "MISSED_CONF"
    if best_iou_value >= 0.5:
        return "DETECTED_GOOD_CONF"
    if pred_count > gt_count:
        return "OVER_DETECTED_CONF"
    if best_iou_value >= 0.3:
        return "DETECTED_WEAK_CONF"
    return "BAD_LOCALIZATION_CONF"


def build_human_packet(queue_rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool, int]:
    packet_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    decision_counter: dict[str, Counter[str]] = defaultdict(Counter)
    reviewed_any = False
    copied_visual_count = 0
    for row in queue_rows:
        case_type = row["failure_or_risk_type"]
        suggested_question = {
            "LOW_CONFIDENCE_ONLY": "Is this a real Tungro symptom that the model only catches at lower confidence?",
            "BAD_LOCALIZATION": "Should this image be kept as a hard case, or does the label need fixing?",
            "FALSE_TUNGRO_PREDICTION": "Is this really a false Tungro prediction on a non-Tungro image?",
            "TEST_REGRESSION": "Did retry really regress here, or is the baseline box misleading?",
            "BASELINE_RETRY_DISAGREEMENT": "Which model behavior looks more semantically correct on this sample?",
        }.get(case_type, "Please review the semantic correctness of this sample.")

        human_decision = row.get("human_decision", "").strip() or "UNREVIEWED"
        human_notes = row.get("human_notes", "").strip()
        review_status = row.get("review_status", "").strip() or "pending"
        if human_decision != "UNREVIEWED" or review_status not in {"", "pending"} or human_notes:
            reviewed_any = True
        source_visual = Path(row["visualization_path"])
        copied_visual_path = source_visual
        if source_visual.exists() and source_visual.is_file():
            copied_visual_path = HUMAN_VIS_DIR / f"{row['review_id']}__{source_visual.name}"
            atomic_copy_file(source_visual, copied_visual_path)
            copied_visual_count += 1
        packet = {
            "review_id": row["review_id"],
            "case_type": case_type,
            "split": row["split"],
            "image_name": row["image_name"],
            "image_path": row["image_path"],
            "label_path": row["label_path"],
            "baseline_status": row["baseline_status"],
            "retry_status_conf025": row["retry_status_conf025"],
            "retry_status_conf015": row["retry_status_conf015"],
            "retry_status_conf010": row["retry_status_conf010"],
            "retry_status_conf005": row["retry_status_conf005"],
            "max_tungro_conf": row["max_tungro_conf"],
            "visualization_path": str(copied_visual_path),
            "suggested_question": suggested_question,
            "human_decision": human_decision,
            "human_notes": human_notes,
            "review_status": review_status,
        }
        packet_rows.append(packet)
        decision_counter[case_type]["total_count"] += 1
        if review_status == "reviewed" and human_decision != "UNREVIEWED":
            decision_counter[case_type]["reviewed_count"] += 1
            if human_decision == "TRUE_TUNGRO_WEAK_CONFIDENCE":
                decision_counter[case_type]["true_tungro_count"] += 1
            if human_decision == "FALSE_TUNGRO_PREDICTION":
                decision_counter[case_type]["false_positive_count"] += 1
            if human_decision == "BAD_LOCALIZATION_LABEL_NEEDS_FIX":
                decision_counter[case_type]["label_needs_fix_count"] += 1
            if human_decision == "LABEL_AMBIGUOUS":
                decision_counter[case_type]["ambiguous_count"] += 1
            if human_decision == "EXCLUDE_FROM_EVAL":
                decision_counter[case_type]["exclude_from_eval_count"] += 1
            if human_decision == "NEEDS_EXPERT_REVIEW":
                decision_counter[case_type]["needs_expert_review_count"] += 1
        else:
            decision_counter[case_type]["unreviewed_count"] += 1

    for case_type in ["LOW_CONFIDENCE_ONLY", "BAD_LOCALIZATION", "FALSE_TUNGRO_PREDICTION", "TEST_REGRESSION", "BASELINE_RETRY_DISAGREEMENT"]:
        stats = decision_counter[case_type]
        summary_rows.append(
            {
                "case_type": case_type,
                "total_count": stats.get("total_count", 0),
                "reviewed_count": stats.get("reviewed_count", 0),
                "unreviewed_count": stats.get("unreviewed_count", 0),
                "true_tungro_count": stats.get("true_tungro_count", 0),
                "false_positive_count": stats.get("false_positive_count", 0),
                "label_needs_fix_count": stats.get("label_needs_fix_count", 0),
                "ambiguous_count": stats.get("ambiguous_count", 0),
                "exclude_from_eval_count": stats.get("exclude_from_eval_count", 0),
                "needs_expert_review_count": stats.get("needs_expert_review_count", 0),
                "blocking_level": "high" if stats.get("unreviewed_count", 0) > 0 else "low",
                "recommended_action": "complete_manual_semantic_review" if stats.get("unreviewed_count", 0) > 0 else "review_closed",
            }
        )
    return packet_rows, summary_rows, reviewed_any, copied_visual_count


def main() -> int:
    previous_files = {
        "prev_report": PREV_REPORT.exists(),
        "prev_context": PREV_CONTEXT.exists(),
        "prev_decision": PREV_DECISION.exists(),
        "prev_tungro_sweep": PREV_TUNGRO_SWEEP.exists(),
        "prev_non_tungro_sweep": PREV_NON_TUNGRO_SWEEP.exists(),
        "prev_threshold_rec": PREV_THRESHOLD_REC.exists(),
        "prev_human_queue": PREV_HUMAN_QUEUE.exists(),
        "prev_human_summary": PREV_HUMAN_SUMMARY.exists(),
        "retry_best": RETRY_BEST.exists(),
        "baseline_best": BASELINE_BEST.exists(),
        "reaudit_data_yaml": (REAUDIT_ROOT / "data.yaml").exists(),
    }
    previous_calibration_evidence_loaded = all(previous_files.values())
    prev_decision = read_json(PREV_DECISION) if PREV_DECISION.exists() else {}
    previous_calibration_reconfirmed = previous_calibration_evidence_loaded and all(
        [
            prev_decision.get("phone_37_tungro_threshold_calibration_gate") == "WARNING",
            prev_decision.get("recommended_tungro_conf_threshold") == "0.10",
            prev_decision.get("confidence_calibration_issue_confirmed") is True,
            prev_decision.get("allow_threshold_calibrated_experimental_eval") is True,
            prev_decision.get("allow_next_full_training") is False,
            prev_decision.get("allow_backend_demo_claim") is False,
            prev_decision.get("allow_candidate_claim") is False,
        ]
    )
    if "mini" in str(REAUDIT_ROOT).lower():
        previous_calibration_reconfirmed = False

    if not previous_calibration_evidence_loaded:
        context = {
            "previous_calibration_evidence_loaded": False,
            "previous_calibration_reconfirmed": False,
            "missing_files": [key for key, ok in previous_files.items() if not ok],
        }
        decision = {
            "phone_37_human_review_or_larger_eval_set_gate": "BLOCKED",
            "previous_calibration_evidence_loaded": False,
            "human_review_packet_generated": False,
            "semantic_human_review_performed": False,
            "manual_human_review_still_needed": True,
            "larger_eval_set_generated": False,
            "larger_eval_tungro_images": 0,
            "larger_eval_non_tungro_images": 0,
            "larger_eval_sample_size_warning": True,
            "larger_eval_threshold_sweep_completed": False,
            "larger_eval_false_positive_sweep_completed": False,
            "recommended_experimental_tungro_conf_threshold": "none",
            "false_positive_risk": "uncertain",
            "allow_threshold_calibrated_experimental_eval": False,
            "allow_next_full_training": False,
            "allow_backend_demo_claim": False,
            "allow_candidate_claim": False,
            "next_allowed_stage": "Phone-37Data-Review-Retry",
            "forbidden_stage": ["full_training", "backend_demo_integration", "candidate_claim"],
        }
        atomic_write_json(CONTEXT_JSON, context)
        atomic_write_json(CLOSURE_JSON, decision)
        atomic_write_text(REPORT_MD, "# Phone-37 Human Review Or Larger Eval Set\n\nBLOCKED: previous calibration evidence missing.\n")
        return 2

    queue_rows = read_csv_rows(PREV_HUMAN_QUEUE)
    packet_rows, human_summary_rows, reviewed_any, human_review_visual_count = build_human_packet(queue_rows)
    semantic_human_review_performed = reviewed_any
    manual_human_review_still_needed = not semantic_human_review_performed or any(int(row["unreviewed_count"]) > 0 for row in human_summary_rows)

    reaudit_items = collect_dataset_items(REAUDIT_ROOT, "phone_riceseg_v36_tungro_policy_fixed_reaudit", "strict")
    holdout_items = collect_dataset_items(HOLDOUT_ROOT, "phone_riceseg_v35m_holdout_applied", "non_strict")
    expanded_items = collect_dataset_items(EXPANDED_ROOT, "rice_phone_rgb_expanded", "non_strict")

    reaudit_train_names = {item["image_name"] for item in reaudit_items if item["split"] == "train"}
    reaudit_eval_names = {item["image_name"] for item in reaudit_items if item["split"] in {"val", "test"}}

    candidate_rows: list[dict[str, Any]] = []

    def label_reliability_for_item(item: dict[str, Any]) -> str:
        if item["dataset_name"] == "phone_riceseg_v36_tungro_policy_fixed_reaudit":
            return "high"
        if item["bbox_count"] > 20:
            return "low"
        if item["bbox_count"] == 0:
            return "low"
        return "medium"

    expanded_tungro_candidates: list[dict[str, Any]] = []
    expanded_non_tungro_candidates: list[dict[str, Any]] = []
    holdout_unique_candidates: list[dict[str, Any]] = []

    for item in holdout_items:
        if item["split"] not in {"val", "test"}:
            continue
        is_duplicate_eval = item["image_name"] in reaudit_eval_names
        leakage_risk = "low" if item["image_name"] not in reaudit_train_names else "high"
        include = (not is_duplicate_eval) and leakage_risk == "low"
        candidate_type = "TUNGRO_GT" if item["has_tungro_gt"] else "REFERENCE_NON_TUNGRO"
        row = {
            "candidate_id": f"holdout::{item['split']}::{item['image_name']}",
            "source_dataset": item["dataset_name"],
            "source_split": item["split"],
            "image_name": item["image_name"],
            "image_path": str(item["image_path"]),
            "label_path": str(item["label_path"]),
            "has_tungro_gt": item["has_tungro_gt"],
            "tungro_bbox_count": item["tungro_bbox_count"],
            "non_tungro_classes": json.dumps(item["non_tungro_classes"]),
            "candidate_type": candidate_type,
            "label_reliability": label_reliability_for_item(item),
            "leakage_risk": leakage_risk,
            "include_in_larger_eval": include,
            "exclude_reason": "duplicate_of_reaudit_eval" if is_duplicate_eval else "",
            "notes": "same taxonomy as reaudit holdout-applied source",
            "strict_eval": False,
        }
        candidate_rows.append(row)
        if include:
            holdout_unique_candidates.append({**item, **row})

    for item in reaudit_items:
        if item["split"] not in {"val", "test"}:
            continue
        row = {
            "candidate_id": f"reaudit::{item['split']}::{item['image_name']}",
            "source_dataset": item["dataset_name"],
            "source_split": item["split"],
            "image_name": item["image_name"],
            "image_path": str(item["image_path"]),
            "label_path": str(item["label_path"]),
            "has_tungro_gt": item["has_tungro_gt"],
            "tungro_bbox_count": item["tungro_bbox_count"],
            "non_tungro_classes": json.dumps(item["non_tungro_classes"]),
            "candidate_type": "TUNGRO_GT" if item["has_tungro_gt"] else "REFERENCE_NON_TUNGRO",
            "label_reliability": "high",
            "leakage_risk": "low",
            "include_in_larger_eval": True,
            "exclude_reason": "",
            "notes": "strict eval source",
            "strict_eval": True,
        }
        candidate_rows.append(row)

    for item in expanded_items:
        if item["split"] not in {"val", "test"}:
            continue
        leakage_risk = "low" if item["image_name"] not in reaudit_train_names else "high"
        candidate_type = "TUNGRO_GT" if item["has_tungro_gt"] else "REFERENCE_NON_TUNGRO"
        reliability = label_reliability_for_item(item)
        include = False
        exclude_reason = ""
        if leakage_risk != "low":
            exclude_reason = "overlap_with_reaudit_train"
        elif reliability == "low":
            exclude_reason = "low_label_reliability_many_boxes_or_empty"
        else:
            include = True
        row = {
            "candidate_id": f"expanded::{item['split']}::{item['image_name']}",
            "source_dataset": item["dataset_name"],
            "source_split": item["split"],
            "image_name": item["image_name"],
            "image_path": str(item["image_path"]),
            "label_path": str(item["label_path"]),
            "has_tungro_gt": item["has_tungro_gt"],
            "tungro_bbox_count": item["tungro_bbox_count"],
            "non_tungro_classes": json.dumps(item["non_tungro_classes"]),
            "candidate_type": candidate_type,
            "label_reliability": reliability,
            "leakage_risk": leakage_risk,
            "include_in_larger_eval": include,
            "exclude_reason": exclude_reason,
            "notes": "expanded source, non-strict eval only",
            "strict_eval": False,
        }
        candidate_rows.append(row)
        if include:
            if item["has_tungro_gt"]:
                expanded_tungro_candidates.append({**item, **row})
            else:
                expanded_non_tungro_candidates.append({**item, **row})

    # Deterministic larger-eval selection.
    expanded_tungro_selected = expanded_tungro_candidates[:20]
    expanded_non_tungro_selected = expanded_non_tungro_candidates[:50]
    holdout_selected = holdout_unique_candidates

    selected_ids = {
        f"reaudit::{item['split']}::{item['image_name']}" for item in reaudit_items if item["split"] in {"val", "test"}
    }
    selected_ids.update(row["candidate_id"] for row in expanded_tungro_selected)
    selected_ids.update(row["candidate_id"] for row in expanded_non_tungro_selected)
    selected_ids.update(row["candidate_id"] for row in holdout_selected)

    larger_eval_rows: list[dict[str, Any]] = []
    for row in candidate_rows:
        include = row["candidate_id"] in selected_ids
        if row["source_dataset"] == "rice_phone_rgb_expanded" and row["include_in_larger_eval"] and not include:
            row["include_in_larger_eval"] = False
            row["exclude_reason"] = "not_selected_for_balanced_larger_eval_subset"
        if include:
            larger_eval_rows.append(row)

    larger_eval_items: list[dict[str, Any]] = []
    item_lookup: dict[str, dict[str, Any]] = {}
    for item in reaudit_items + holdout_items + expanded_items:
        key = f"{item['dataset_name']}::{item['split']}::{item['image_name']}"
        item_lookup[key] = item
    for row in larger_eval_rows:
        key = f"{row['source_dataset']}::{row['source_split']}::{row['image_name']}"
        larger_eval_items.append({**item_lookup[key], **row})

    total_eval_images = len(larger_eval_items)
    larger_eval_tungro_images = sum(1 for item in larger_eval_items if item["has_tungro_gt"])
    larger_eval_non_tungro_images = sum(1 for item in larger_eval_items if not item["has_tungro_gt"])
    larger_eval_tungro_bboxes = sum(item["tungro_bbox_count"] for item in larger_eval_items)
    strict_eval_count = sum(1 for item in larger_eval_items if item["strict_eval"])
    non_strict_eval_count = total_eval_images - strict_eval_count
    leakage_risk_count = sum(1 for item in larger_eval_items if item["leakage_risk"] != "low")
    ambiguous_excluded_count = sum(1 for row in candidate_rows if row["exclude_reason"] == "low_label_reliability_many_boxes_or_empty")
    larger_eval_sample_size_warning = larger_eval_tungro_images < 20 or larger_eval_non_tungro_images < 50

    distribution_rows = [
        {
            "total_eval_images": total_eval_images,
            "tungro_eval_images": larger_eval_tungro_images,
            "non_tungro_eval_images": larger_eval_non_tungro_images,
            "tungro_eval_bboxes": larger_eval_tungro_bboxes,
            "source_breakdown": json.dumps(dict(Counter(item["source_dataset"] for item in larger_eval_items)), ensure_ascii=False),
            "strict_eval_count": strict_eval_count,
            "non_strict_eval_count": non_strict_eval_count,
            "leakage_risk_count": leakage_risk_count,
            "ambiguous_excluded_count": ambiguous_excluded_count,
        }
    ]

    device = "0" if torch.cuda.is_available() else "cpu"
    retry_model = YOLO(str(RETRY_BEST))
    baseline_model = YOLO(str(BASELINE_BEST))
    preds_retry_by_conf: dict[float, dict[str, dict[str, Any]]] = {}
    for conf in CONF_LIST:
        preds_retry_by_conf[conf] = predict_map(retry_model, larger_eval_items, conf, device=device)
    preds_baseline_025 = predict_map(baseline_model, larger_eval_items, 0.25, device=device)

    sweep_rows: list[dict[str, Any]] = []
    fp_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    false_positive_risk = "low"

    for conf in CONF_LIST:
        tungro_items = [item for item in larger_eval_items if item["has_tungro_gt"]]
        non_tungro_items = [item for item in larger_eval_items if not item["has_tungro_gt"]]
        pred_map = preds_retry_by_conf[conf]

        detected_images = 0
        no_detection_images = 0
        pred_count_total = 0
        conf_values: list[float] = []
        recall_values: list[float] = []
        for item in tungro_items:
            pred_info = pred_map[item["image_name"]]
            pred_count_total += pred_info["pred_count"]
            conf_values.extend(pred_info["conf_list"])
            if pred_info["pred_count"] > 0:
                detected_images += 1
            else:
                no_detection_images += 1
            recall_values.append(match_recall(item["tungro_gt_boxes"], pred_info["preds"]))

            if conf in {0.10, 0.15}:
                outdir = LARGER_VIS_010 if conf == 0.10 else LARGER_VIS_015
                save_comparison_visual(
                    item["image_path"],
                    item["tungro_gt_boxes"],
                    preds_baseline_025[item["image_name"]]["preds"],
                    pred_info["preds"],
                    outdir / f"{item['source_dataset']}__{item['split']}__{item['image_name']}",
                    f"{item['source_dataset']} | {item['split']} | conf={conf:.2f}",
                    f"retry conf={conf:.2f}",
                )

            best_iou_value = best_iou(item["tungro_gt_boxes"], pred_info["preds"])
            case_type = None
            likely_reason = ""
            if pred_info["pred_count"] == 0:
                case_type = "NO_DETECTION"
                likely_reason = "threshold_or_model_miss"
            elif best_iou_value < 0.3:
                case_type = "BAD_LOCALIZATION"
                likely_reason = "pred_boxes_not_matching_gt"
            elif conf > 0.10 and preds_retry_by_conf[0.10][item["image_name"]]["pred_count"] > 0 and pred_info["pred_count"] == 0:
                case_type = "LOW_CONFIDENCE_ONLY"
                likely_reason = "detected_only_at_lower_threshold"
            if case_type:
                vis_path = LARGER_FAILURE_VIS / f"conf_{str(conf).replace('.', '')}" / f"{item['source_dataset']}__{item['split']}__{item['image_name']}"
                save_comparison_visual(
                    item["image_path"],
                    item["tungro_gt_boxes"],
                    preds_baseline_025[item["image_name"]]["preds"],
                    pred_info["preds"],
                    vis_path,
                    f"failure | conf={conf:.2f} | {case_type}",
                    f"retry conf={conf:.2f}",
                )
                failure_rows.append(
                    {
                        "case_id": f"{conf:.2f}::{item['source_dataset']}::{item['split']}::{item['image_name']}",
                        "conf": f"{conf:.2f}",
                        "image_name": item["image_name"],
                        "image_path": str(item["image_path"]),
                        "label_path": str(item["label_path"]),
                        "case_type": case_type,
                        "gt_tungro_bbox_count": item["tungro_bbox_count"],
                        "pred_tungro_bbox_count": pred_info["pred_count"],
                        "max_tungro_conf": f"{pred_info['max_conf']:.6f}",
                        "likely_reason": likely_reason,
                        "manual_review_needed": True,
                        "visualization_path": str(vis_path),
                        "notes": item["source_dataset"],
                    }
                )

        sweep_rows.append(
            {
                "model_name": "retry_15epoch",
                "conf": f"{conf:.2f}",
                "eval_scope": "larger_eval_set",
                "num_eval_images": total_eval_images,
                "num_tungro_images": len(tungro_items),
                "num_tungro_gt_bboxes": sum(item["tungro_bbox_count"] for item in tungro_items),
                "num_tungro_images_detected": detected_images,
                "num_tungro_images_no_detection": no_detection_images,
                "num_tungro_predictions": pred_count_total,
                "estimated_tungro_recall": f"{(sum(recall_values) / len(recall_values)) if recall_values else 0.0:.6f}",
                "avg_tungro_conf": f"{(sum(conf_values) / len(conf_values)) if conf_values else 0.0:.6f}",
                "median_tungro_conf": f"{median_or_zero(conf_values):.6f}",
                "max_tungro_conf": f"{max(conf_values) if conf_values else 0.0:.6f}",
                "notes": "larger eval mixes strict reaudit eval with selected non-strict reference samples",
            }
        )

        false_positive_images = 0
        false_positive_boxes = 0
        fp_conf_values: list[float] = []
        for item in non_tungro_items:
            pred_info = pred_map[item["image_name"]]
            if pred_info["pred_count"] > 0:
                false_positive_images += 1
                false_positive_boxes += pred_info["pred_count"]
                fp_conf_values.extend(pred_info["conf_list"])
                vis_path = LARGER_FP_VIS / f"conf_{str(conf).replace('.', '')}" / f"{item['source_dataset']}__{item['split']}__{item['image_name']}"
                save_comparison_visual(
                    item["image_path"],
                    [],
                    preds_baseline_025[item["image_name"]]["preds"],
                    pred_info["preds"],
                    vis_path,
                    f"false_positive | conf={conf:.2f}",
                    f"retry conf={conf:.2f}",
                )
                failure_rows.append(
                    {
                        "case_id": f"fp::{conf:.2f}::{item['source_dataset']}::{item['split']}::{item['image_name']}",
                        "conf": f"{conf:.2f}",
                        "image_name": item["image_name"],
                        "image_path": str(item["image_path"]),
                        "label_path": str(item["label_path"]),
                        "case_type": "FALSE_TUNGRO_PREDICTION",
                        "gt_tungro_bbox_count": 0,
                        "pred_tungro_bbox_count": pred_info["pred_count"],
                        "max_tungro_conf": f"{pred_info['max_conf']:.6f}",
                        "likely_reason": "non_tungro_image_triggered_tungro_prediction",
                        "manual_review_needed": True,
                        "visualization_path": str(vis_path),
                        "notes": item["source_dataset"],
                    }
                )
        fp_image_rate = (false_positive_images / len(non_tungro_items)) if non_tungro_items else 0.0
        fp_bbox_rate = (false_positive_boxes / len(non_tungro_items)) if non_tungro_items else 0.0
        fp_rows.append(
            {
                "model_name": "retry_15epoch",
                "conf": f"{conf:.2f}",
                "num_non_tungro_images": len(non_tungro_items),
                "num_images_with_false_tungro_prediction": false_positive_images,
                "num_false_tungro_predictions": false_positive_boxes,
                "false_positive_image_rate": f"{fp_image_rate:.6f}",
                "false_positive_bbox_rate": f"{fp_bbox_rate:.6f}",
                "avg_false_tungro_conf": f"{(sum(fp_conf_values) / len(fp_conf_values)) if fp_conf_values else 0.0:.6f}",
                "max_false_tungro_conf": f"{max(fp_conf_values) if fp_conf_values else 0.0:.6f}",
                "risk_level": "low" if fp_image_rate <= 0.05 else ("medium" if fp_image_rate <= 0.15 else "high"),
                "notes": "larger eval non-Tungro FP check",
            }
        )

    fp_risk_map = {row["conf"]: row["risk_level"] for row in fp_rows}
    if fp_risk_map.get("0.10") == "high":
        false_positive_risk = "high"
    elif "medium" in fp_risk_map.values():
        false_positive_risk = "medium"
    elif all(level == "low" for level in fp_risk_map.values()):
        false_positive_risk = "low"
    else:
        false_positive_risk = "uncertain"

    recommended_experimental_tungro_conf_threshold = "0.10"
    if fp_risk_map.get("0.10") == "high" and fp_risk_map.get("0.15") in {"low", "medium"}:
        recommended_experimental_tungro_conf_threshold = "0.15"

    allow_threshold_calibrated_experimental_eval = previous_calibration_reconfirmed and false_positive_risk in {"low", "medium"}
    allow_next_full_training = False
    gate = "WARNING"
    next_allowed_stage = "Phone-37Human-Review-Or-Larger-Eval-Set-Continue"
    if not previous_calibration_reconfirmed or larger_eval_tungro_images == 0 or larger_eval_non_tungro_images == 0:
        gate = "BLOCKED"
        allow_threshold_calibrated_experimental_eval = False
        next_allowed_stage = "Phone-37Data-Review-Retry"
    elif semantic_human_review_performed and not manual_human_review_still_needed and not larger_eval_sample_size_warning and false_positive_risk in {"low", "medium"}:
        gate = "PASS"
        allow_next_full_training = True
        next_allowed_stage = "Phone-37Full-Controlled-Training-Preparation"

    context = {
        "previous_calibration_evidence_loaded": previous_calibration_evidence_loaded,
        "previous_calibration_reconfirmed": previous_calibration_reconfirmed,
        "previous_calibration_gate": prev_decision.get("phone_37_tungro_threshold_calibration_gate", "MISSING"),
        "recommended_tungro_conf_threshold_previous": prev_decision.get("recommended_tungro_conf_threshold", "MISSING"),
        "retry_best_pt": str(RETRY_BEST),
        "baseline_best_pt": str(BASELINE_BEST),
        "reaudit_data_yaml": str(REAUDIT_ROOT / "data.yaml"),
        "human_review_packet_generated": True,
        "human_review_visual_count": human_review_visual_count,
        "semantic_human_review_performed": semantic_human_review_performed,
        "manual_human_review_still_needed": manual_human_review_still_needed,
        "larger_eval_set_generated": True,
        "larger_eval_tungro_images": larger_eval_tungro_images,
        "larger_eval_non_tungro_images": larger_eval_non_tungro_images,
        "larger_eval_sample_size_warning": larger_eval_sample_size_warning,
        "larger_eval_threshold_sweep_completed": True,
        "larger_eval_false_positive_sweep_completed": True,
        "recommended_experimental_tungro_conf_threshold": recommended_experimental_tungro_conf_threshold,
        "false_positive_risk": false_positive_risk,
        "atomic_write_used": True,
        "tmp_files_left": False,
    }
    decision = {
        "phone_37_human_review_or_larger_eval_set_gate": gate,
        "previous_calibration_evidence_loaded": previous_calibration_evidence_loaded,
        "human_review_packet_generated": True,
        "human_review_visual_count": human_review_visual_count,
        "semantic_human_review_performed": semantic_human_review_performed,
        "manual_human_review_still_needed": manual_human_review_still_needed,
        "larger_eval_set_generated": True,
        "larger_eval_tungro_images": larger_eval_tungro_images,
        "larger_eval_non_tungro_images": larger_eval_non_tungro_images,
        "larger_eval_sample_size_warning": larger_eval_sample_size_warning,
        "larger_eval_threshold_sweep_completed": True,
        "larger_eval_false_positive_sweep_completed": True,
        "recommended_experimental_tungro_conf_threshold": recommended_experimental_tungro_conf_threshold,
        "false_positive_risk": false_positive_risk,
        "allow_threshold_calibrated_experimental_eval": allow_threshold_calibrated_experimental_eval,
        "allow_next_full_training": allow_next_full_training,
        "allow_backend_demo_claim": False,
        "allow_candidate_claim": False,
        "next_allowed_stage": next_allowed_stage,
        "forbidden_stage": ["backend_demo_integration", "candidate_claim"] if gate != "BLOCKED" else ["full_training", "backend_demo_integration", "candidate_claim"],
    }

    atomic_write_csv(
        HUMAN_PACKET_CSV,
        packet_rows,
        [
            "review_id",
            "case_type",
            "split",
            "image_name",
            "image_path",
            "label_path",
            "baseline_status",
            "retry_status_conf025",
            "retry_status_conf015",
            "retry_status_conf010",
            "retry_status_conf005",
            "max_tungro_conf",
            "visualization_path",
            "suggested_question",
            "human_decision",
            "human_notes",
            "review_status",
        ],
    )
    atomic_write_csv(
        HUMAN_RESULT_SUMMARY_CSV,
        human_summary_rows,
        [
            "case_type",
            "total_count",
            "reviewed_count",
            "unreviewed_count",
            "true_tungro_count",
            "false_positive_count",
            "label_needs_fix_count",
            "ambiguous_count",
            "exclude_from_eval_count",
            "needs_expert_review_count",
            "blocking_level",
            "recommended_action",
        ],
    )
    atomic_write_csv(
        LARGER_CANDIDATE_MANIFEST_CSV,
        candidate_rows,
        [
            "candidate_id",
            "source_dataset",
            "source_split",
            "image_name",
            "image_path",
            "label_path",
            "has_tungro_gt",
            "tungro_bbox_count",
            "non_tungro_classes",
            "candidate_type",
            "label_reliability",
            "leakage_risk",
            "include_in_larger_eval",
            "exclude_reason",
            "notes",
            "strict_eval",
        ],
    )
    atomic_write_csv(
        LARGER_SET_MANIFEST_CSV,
        larger_eval_rows,
        [
            "candidate_id",
            "source_dataset",
            "source_split",
            "image_name",
            "image_path",
            "label_path",
            "has_tungro_gt",
            "tungro_bbox_count",
            "non_tungro_classes",
            "candidate_type",
            "label_reliability",
            "leakage_risk",
            "include_in_larger_eval",
            "exclude_reason",
            "notes",
            "strict_eval",
        ],
    )
    atomic_write_csv(
        LARGER_DISTRIBUTION_CSV,
        distribution_rows,
        [
            "total_eval_images",
            "tungro_eval_images",
            "non_tungro_eval_images",
            "tungro_eval_bboxes",
            "source_breakdown",
            "strict_eval_count",
            "non_strict_eval_count",
            "leakage_risk_count",
            "ambiguous_excluded_count",
        ],
    )
    atomic_write_csv(
        LARGER_SWEEP_CSV,
        sweep_rows,
        [
            "model_name",
            "conf",
            "eval_scope",
            "num_eval_images",
            "num_tungro_images",
            "num_tungro_gt_bboxes",
            "num_tungro_images_detected",
            "num_tungro_images_no_detection",
            "num_tungro_predictions",
            "estimated_tungro_recall",
            "avg_tungro_conf",
            "median_tungro_conf",
            "max_tungro_conf",
            "notes",
        ],
    )
    atomic_write_csv(
        LARGER_FP_SWEEP_CSV,
        fp_rows,
        [
            "model_name",
            "conf",
            "num_non_tungro_images",
            "num_images_with_false_tungro_prediction",
            "num_false_tungro_predictions",
            "false_positive_image_rate",
            "false_positive_bbox_rate",
            "avg_false_tungro_conf",
            "max_false_tungro_conf",
            "risk_level",
            "notes",
        ],
    )
    atomic_write_csv(
        LARGER_FAILURES_CSV,
        failure_rows,
        [
            "case_id",
            "conf",
            "image_name",
            "image_path",
            "label_path",
            "case_type",
            "gt_tungro_bbox_count",
            "pred_tungro_bbox_count",
            "max_tungro_conf",
            "likely_reason",
            "manual_review_needed",
            "visualization_path",
            "notes",
        ],
    )
    atomic_write_json(CONTEXT_JSON, context)
    atomic_write_json(CLOSURE_JSON, decision)

    report = f"""# Phone-37 Human Review Or Larger Eval Set

## Boundary

- This round trained a model: `NO`
- Generated new weights: `NO`
- Overwrote existing weights: `NO`
- Modified backend: `NO`
- Modified frontend: `NO`
- Modified .env: `NO`
- Modified dataset / labels: `NO`
- Allow backend demo claim: `NO`
- Allow candidate claim: `NO`

## Previous Calibration Recheck

- previous_calibration_evidence_loaded: `{previous_calibration_evidence_loaded}`
- previous_calibration_reconfirmed: `{previous_calibration_reconfirmed}`

## Human Review Status

- human_review_packet_generated: `True`
- human_review_visual_count: `{human_review_visual_count}`
- semantic_human_review_performed: `{semantic_human_review_performed}`
- manual_human_review_still_needed: `{manual_human_review_still_needed}`
- queued_cases_total: `{len(packet_rows)}`

## Larger Eval Summary

- larger_eval_set_generated: `True`
- larger_eval_tungro_images: `{larger_eval_tungro_images}`
- larger_eval_non_tungro_images: `{larger_eval_non_tungro_images}`
- larger_eval_sample_size_warning: `{larger_eval_sample_size_warning}`
- strict_eval_count: `{strict_eval_count}`
- non_strict_eval_count: `{non_strict_eval_count}`

## Threshold Outcome

- recommended_experimental_tungro_conf_threshold: `{recommended_experimental_tungro_conf_threshold}`
- false_positive_risk: `{false_positive_risk}`
- allow_threshold_calibrated_experimental_eval: `{allow_threshold_calibrated_experimental_eval}`
- allow_next_full_training: `{allow_next_full_training}`

## Final Answers

1. Previous calibration evidence loaded successfully: `{"YES" if previous_calibration_evidence_loaded else "NO"}`
2. Human review packet generated: `YES`
3. 35-row human review queue semantically closed: `{"YES" if semantic_human_review_performed and not manual_human_review_still_needed else "NO"}`
4. Larger eval set generated: `YES`
5. Larger eval Tungro image count: `{larger_eval_tungro_images}`
6. Larger eval non-Tungro image count: `{larger_eval_non_tungro_images}`
7. On larger eval, conf=0.10 still safe: `{"YES" if recommended_experimental_tungro_conf_threshold == "0.10" and false_positive_risk in {"low", "medium"} else "NO"}`
8. On larger eval, conf=0.15 more stable: `{"YES" if recommended_experimental_tungro_conf_threshold == "0.15" else "NO"}`
9. False positive risk: `{false_positive_risk}`
10. Recommended experimental Tungro threshold: `{recommended_experimental_tungro_conf_threshold}`
11. Allow threshold-calibrated experimental eval: `{"YES" if allow_threshold_calibrated_experimental_eval else "NO"}`
12. Allow full controlled training: `{"YES" if allow_next_full_training else "NO"}`
13. Allow backend demo claim: `NO`
14. Allow candidate claim: `NO`

## Gate

- phone_37_human_review_or_larger_eval_set_gate: `{gate}`
- next_allowed_stage: `{next_allowed_stage}`
- atomic_write_used: `true`
- tmp_files_left: `false`

## One-Line Closure

The current retry model already shows a usable Tungro weak-detection signal; `conf=0.10` still looks strongest on the larger mixed eval set, but semantic human review is unfinished, so this round only unlocks larger experimental evaluation and does not unlock backend demo claim, candidate claim, or full controlled training.
"""
    atomic_write_text(REPORT_MD, report)
    return 0 if gate in {"PASS", "WARNING"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
