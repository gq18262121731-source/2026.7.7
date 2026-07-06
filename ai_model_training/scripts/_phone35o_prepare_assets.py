from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
import yaml


ROOT = Path(r"F:/学校/病虫害识别/ai_model_training")
REPORTS = ROOT / "reports"
METADATA = ROOT / "metadata"
DATASET_ROOT = ROOT / "datasets" / "phone_riceseg_v35m_holdout_applied"
RUN_DIR = ROOT / "experiments" / "phone_rgb_yolo" / "runs" / "controlled_exp_phone_riceseg_v35m_holdout_applied_10epoch"
VISUAL_DIR = REPORTS / "phone_riceseg_35o_prediction_visual_audit"
NOW = datetime.now(timezone.utc).isoformat()

REQUIRED_FILES = {
    "status_yaml": METADATA / "phone_dataset_status.yaml",
    "config_yaml": ROOT / "configs" / "phone_riceseg_v35m_holdout_applied_10epoch.yaml",
    "round_35n_report": REPORTS / "thirty_fifth_round_n_phone_riceseg_fixed_dataset_10epoch_training_report.md",
    "model_card": REPORTS / "phone_riceseg_35n_10epoch_model_card.json",
    "comparison_md": REPORTS / "phone_riceseg_35n_10epoch_vs_35b_5epoch_comparison.md",
    "conf_sweep_md": REPORTS / "phone_riceseg_35n_10epoch_conf_sweep_summary.md",
    "test_infer": REPORTS / "phone_riceseg_35n_10epoch_test_infer_conf025_results.json",
    "test_infer_conf010": REPORTS / "phone_riceseg_35n_10epoch_test_infer_conf010_results.json",
    "holdout_infer": REPORTS / "phone_riceseg_35n_10epoch_holdout_infer_conf025_results.json",
    "validate_json": REPORTS / "phone_riceseg_35n_10epoch_validate_summary.json",
    "data_yaml": DATASET_ROOT / "data.yaml",
    "best_pt": RUN_DIR / "weights" / "best.pt",
}

DECISIONS_CSV = REPORTS / "phone_riceseg_35o_prediction_review_decisions.csv"
DECISIONS_JSON = REPORTS / "phone_riceseg_35o_prediction_review_decisions.json"
SUMMARY_JSON = REPORTS / "phone_riceseg_35o_prediction_review_summary.json"
GATE_REPORT_MD = REPORTS / "phone_riceseg_35o_prediction_review_gate_report.md"

SERIOUS_ISSUES = {
    "pred_no_detection",
    "pred_wrong_class",
    "pred_background_fp",
    "pred_too_many_boxes",
    "pred_duplicate_boxes",
    "pred_overbox",
}
ISSUE_TYPE_LABELS = {
    "pred_ok": "预测基本合理",
    "pred_no_detection": "明显有病斑但无检测",
    "pred_partial_detection": "只检测到部分病斑",
    "pred_overbox": "框过大",
    "pred_underbox": "框过小",
    "pred_wrong_class": "类别错误",
    "pred_background_fp": "背景误检",
    "pred_duplicate_boxes": "重复框",
    "pred_too_many_boxes": "框数量过多",
    "pred_low_conf_uncertain": "低置信不确定",
    "pred_gt_label_questionable": "原始标签可疑",
    "pred_uncertain": "人工无法判断",
    "pred_other": "其他",
}


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    if tmp.stat().st_size == 0:
        raise RuntimeError(f"temporary file is empty: {tmp}")
    tmp.replace(path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"final file missing or empty: {path}")


def atomic_write_json(path: Path, obj: Any) -> None:
    atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def atomic_write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    if tmp.stat().st_size == 0:
        raise RuntimeError(f"temporary file is empty: {tmp}")
    tmp.replace(path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"final file missing or empty: {path}")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_yolo_label(path: Path, names: dict[int, str], image_size: tuple[int, int]) -> list[dict[str, Any]]:
    boxes: list[dict[str, Any]] = []
    if not path.exists():
        return boxes
    width, height = image_size
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        class_id_str, cx_str, cy_str, w_str, h_str = line.split()
        class_id = int(class_id_str)
        cx = float(cx_str)
        cy = float(cy_str)
        bw = float(w_str)
        bh = float(h_str)
        x1 = (cx - bw / 2) * width
        y1 = (cy - bh / 2) * height
        x2 = (cx + bw / 2) * width
        y2 = (cy + bh / 2) * height
        boxes.append(
            {
                "class_id": class_id,
                "class_name": names.get(class_id, str(class_id)),
                "bbox": [x1, y1, x2, y2],
            }
        )
    return boxes


def load_names(data_yaml: Path) -> dict[int, str]:
    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
    names = data.get("names", {})
    if isinstance(names, list):
        return {idx: str(name) for idx, name in enumerate(names)}
    return {int(k): str(v) for k, v in names.items()}


def detection_index(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["image_name"]: item for item in results}


def safe_rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def draw_boxes(base: Image.Image, boxes: list[dict[str, Any]], color: tuple[int, int, int], title_lines: list[str]) -> Image.Image:
    image = base.copy().convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    for box in boxes:
        x1, y1, x2, y2 = box["bbox"]
        x1, x2 = sorted((float(x1), float(x2)))
        y1, y2 = sorted((float(y1), float(y2)))
        label = box.get("class_name", "unknown")
        conf = box.get("confidence")
        if conf is not None:
            label = f"{label} {conf:.2f}"
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        label_top = max(0.0, y1 - 14.0)
        label_bottom = max(label_top + 1.0, y1)
        label_right = x1 + max(70, len(label) * 7)
        draw.rectangle([x1, label_top, label_right, label_bottom], fill=color)
        draw.text((x1 + 2, label_top + 2), label, fill=(255, 255, 255), font=font)

    header_height = 16 * len(title_lines) + 12
    canvas = Image.new("RGB", (image.width, image.height + header_height), color=(24, 24, 24))
    canvas.paste(image, (0, header_height))
    header_draw = ImageDraw.Draw(canvas)
    y = 6
    for line in title_lines:
        header_draw.text((6, y), line, fill=(240, 240, 240), font=font)
        y += 16
    return canvas


def side_by_side(gt_img: Image.Image, pred_img: Image.Image) -> Image.Image:
    width = gt_img.width + pred_img.width
    height = max(gt_img.height, pred_img.height)
    canvas = Image.new("RGB", (width, height), color=(12, 12, 12))
    canvas.paste(gt_img, (0, 0))
    canvas.paste(pred_img, (gt_img.width, 0))
    return canvas


def find_paths(split: str, image_name: str) -> tuple[Path, Path]:
    if split == "holdout":
        image_path = DATASET_ROOT / "holdout" / "images" / "test" / image_name
        label_path = DATASET_ROOT / "holdout" / "labels" / "test" / f"{Path(image_name).stem}.txt"
    else:
        image_path = DATASET_ROOT / "images" / split / image_name
        label_path = DATASET_ROOT / "labels" / split / f"{Path(image_name).stem}.txt"
    return image_path, label_path


def load_35b_image_names() -> set[str]:
    path = REPORTS / "phone_riceseg_short_exp_5epoch_infer_demo_conf025_results.json"
    if not path.exists():
        return set()
    data = load_json(path)
    return {item.get("image_name", "") for item in data.get("results", [])}


def update_status_docs(total_review_items: int) -> None:
    status_path = METADATA / "phone_dataset_status.yaml"
    status = yaml.safe_load(status_path.read_text(encoding="utf-8"))
    dataset_status = status.setdefault("datasets", {}).setdefault("phone_riceseg_v35m_holdout_applied", {})
    dataset_status.setdefault("training", {}).setdefault("phone_35n_10epoch", {})
    dataset_status["prediction_visual_review"] = {
        "phone_35o": {
            "status": "PREPARED",
            "reviewed_count": 0,
            "total_review_items": total_review_items,
            "gate": "PENDING",
            "serious_issue_ratio": None,
            "next_allowed_stage": "pending",
        }
    }
    dataset_status["backend_deployment_allowed"] = False
    dataset_status["formal_metric_available"] = False
    dataset_status["pesticide_recommendation_allowed"] = False
    atomic_write_text(status_path, yaml.safe_dump(status, allow_unicode=True, sort_keys=False))

    summary_path = REPORTS / "project_current_model_status_summary.md"
    summary_text = summary_path.read_text(encoding="utf-8")
    line = (
        "- `phone_riceseg_v35m_holdout_applied` is now in `prediction_visual_review` after the 35N `WARNING` gate. "
        f"A guarded review pack covering `{total_review_items}` conf=`0.25` prediction cases has been prepared. "
        "This round adds no training, no new weights, and no backend integration."
    )
    if "- `phone_riceseg_v35m_holdout_applied` is now in `prediction_visual_review`" not in summary_text:
        summary_text = summary_text.replace("## UAV Line", line + "\n## UAV Line")
    atomic_write_text(summary_path, summary_text)

    boundary_path = REPORTS / "demo_model_boundary_statement.md"
    boundary_text = boundary_path.read_text(encoding="utf-8")
    boundary_line = (
        "- Phone `v35m_holdout_applied` has entered guarded `prediction visual review`. "
        "This round prepares visual audit assets only; it does not retrain, does not create new weights, and does not unlock backend deployment."
    )
    if boundary_line not in boundary_text:
        boundary_text = boundary_text.replace("## UAV BLB 408 Manual Gate Status", boundary_line + "\n## UAV BLB 408 Manual Gate Status")
    atomic_write_text(boundary_path, boundary_text)

    roadmap_path = REPORTS / "uav_phone_dual_line_roadmap.md"
    roadmap_text = roadmap_path.read_text(encoding="utf-8")
    roadmap_line = (
        f"8. Phone `v35m_holdout_applied` is now in guarded prediction visual review on `{total_review_items}` prepared cases. "
        "The next decision should come from visual evidence before any threshold calibration or further training."
    )
    if "8. Phone `v35m_holdout_applied` is now in guarded prediction visual review" not in roadmap_text:
        roadmap_text = roadmap_text.replace("## UAV BLB 408 Manual Gate Status", roadmap_line + "\n## UAV BLB 408 Manual Gate Status")
    atomic_write_text(roadmap_path, roadmap_text)

    frontend_path = REPORTS / "frontend_demo_model_hint_policy.md"
    frontend_text = frontend_path.read_text(encoding="utf-8")
    frontend_line = (
        "- The phone 35N line is currently under guarded prediction visual review only. "
        "Frontend routing must remain unchanged and must continue to present the phone experimental line as non-deployable."
    )
    if frontend_line not in frontend_text:
        frontend_text = frontend_text.replace("## UAV BLB 408 Manual Gate Status", frontend_line + "\n## UAV BLB 408 Manual Gate Status")
    atomic_write_text(frontend_path, frontend_text)

    defense_path = REPORTS / "defense_talking_points_model_limitations.md"
    defense_text = defense_path.read_text(encoding="utf-8")
    insert_line = (
        "12. After the 35N warning gate, the phone line has moved into prediction visual review rather than further blind training. "
        "That means the team is checking whether the predicted boxes themselves are visually credible before deciding on threshold tuning or more debugging."
    )
    if insert_line not in defense_text:
        defense_text = defense_text.replace(
            "11. The project emphasizes controlled engineering, dataset audit, and explicit demo boundaries rather than overstating model readiness.\n",
            "11. The project emphasizes controlled engineering, dataset audit, and explicit demo boundaries rather than overstating model readiness.\n"
            + insert_line
            + "\n",
        )
    atomic_write_text(defense_path, defense_text)


def render_readiness_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Phone RiceSeg 35O Prediction Review Readiness Check",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- 35N_gate: `{payload['gate']}`",
        f"- next_allowed_stage: `{payload['next_allowed_stage']}`",
        f"- best_pt_exists: `{payload['best_pt_exists']}`",
        f"- test_infer_exists: `{payload['test_infer_exists']}`",
        f"- holdout_infer_exists: `{payload['holdout_infer_exists']}`",
        f"- conf_sweep_exists: `{payload['conf_sweep_exists']}`",
        f"- backend_deployment_allowed: `{payload['backend_deployment_allowed']}`",
        f"- formal_metric_available: `{payload['formal_metric_available']}`",
        f"- missing_files: `{payload['missing_files']}`",
        "",
    ]
    return "\n".join(lines)


def render_sampling_md(summary: dict[str, Any]) -> str:
    lines = [
        "# Phone RiceSeg 35O Prediction Review Sampling Plan",
        "",
        f"- total_review_items: `{summary['total_review_items']}`",
        f"- test_items: `{summary['test_items']}`",
        f"- holdout_items: `{summary['holdout_items']}`",
        f"- no_detection_conf025_items: `{summary['no_detection_conf025_items']}`",
        f"- high_box_count_conf025_items: `{summary['high_box_count_conf025_items']}`",
        f"- high_growth_conf010_items: `{summary['high_growth_conf010_items']}`",
        f"- overlap_with_35b_demo_items: `{summary['overlap_with_35b_demo_items']}`",
        f"- gt_class_distribution: `{summary['gt_class_distribution']}`",
        "",
        "All 43 test images and all 9 holdout images are included. Additional hard-case tags come from `no_detection`, higher predicted box count, lower confidence, and conf=0.10 box growth behavior.",
        "",
    ]
    return "\n".join(lines)


def compute_review_status(total_review_items: int) -> tuple[dict[str, Any], str]:
    if not DECISIONS_CSV.exists() or not DECISIONS_JSON.exists() or not SUMMARY_JSON.exists() or not GATE_REPORT_MD.exists():
        payload = {
            "generated_at": NOW,
            "review_items_count": total_review_items,
            "reviewed_count": 0,
            "manual_prediction_review_gate": "PENDING",
            "reason": "review decision files are absent",
            "backend_deployment_allowed": False,
            "formal_metric_available": False,
        }
        md = "\n".join(
            [
                "# Phone RiceSeg 35O Prediction Review Status Check",
                "",
                f"- review_items_count: `{total_review_items}`",
                "- reviewed_count: `0`",
                "- manual_prediction_review_gate: `PENDING`",
                "- reason: review decision files are absent",
                "- backend_deployment_allowed: `false`",
                "- formal_metric_available: `false`",
                "",
            ]
        )
        return payload, md

    summary = load_json(SUMMARY_JSON)
    reviewed_count = int(summary.get("reviewed_count", 0))
    gate = summary.get("gate", "PENDING")
    payload = {
        "generated_at": NOW,
        "review_items_count": total_review_items,
        "reviewed_count": reviewed_count,
        "manual_prediction_review_gate": gate,
        "reason": "review outputs present",
        "backend_deployment_allowed": False,
        "formal_metric_available": False,
    }
    md = "\n".join(
        [
            "# Phone RiceSeg 35O Prediction Review Status Check",
            "",
            f"- review_items_count: `{total_review_items}`",
            f"- reviewed_count: `{reviewed_count}`",
            f"- manual_prediction_review_gate: `{gate}`",
            "- reason: review outputs present",
            "- backend_deployment_allowed: `false`",
            "- formal_metric_available: `false`",
            "",
        ]
    )
    return payload, md


def main() -> None:
    missing_files = [safe_rel(path) for path in REQUIRED_FILES.values() if not path.exists()]
    status = yaml.safe_load(REQUIRED_FILES["status_yaml"].read_text(encoding="utf-8"))
    training_status = status.get("datasets", {}).get("phone_riceseg_v35m_holdout_applied", {}).get("training", {}).get("phone_35n_10epoch", {})
    readiness = {
        "generated_at": NOW,
        "gate": training_status.get("status", "UNKNOWN"),
        "next_allowed_stage": training_status.get("next_allowed_stage", "UNKNOWN"),
        "best_pt_exists": REQUIRED_FILES["best_pt"].exists(),
        "test_infer_exists": REQUIRED_FILES["test_infer"].exists(),
        "holdout_infer_exists": REQUIRED_FILES["holdout_infer"].exists(),
        "conf_sweep_exists": REQUIRED_FILES["conf_sweep_md"].exists(),
        "backend_deployment_allowed": bool(training_status.get("backend_deployment_allowed", False)),
        "formal_metric_available": bool(training_status.get("formal_metric_available", False)),
        "missing_files": missing_files,
        "blocked": bool(missing_files),
    }
    atomic_write_json(REPORTS / "phone_riceseg_35o_prediction_review_readiness_check.json", readiness)
    atomic_write_text(REPORTS / "phone_riceseg_35o_prediction_review_readiness_check.md", render_readiness_md(readiness))
    if missing_files:
        return

    names = load_names(REQUIRED_FILES["data_yaml"])
    test_conf025 = detection_index(load_json(REQUIRED_FILES["test_infer"]).get("results", []))
    test_conf010 = detection_index(load_json(REQUIRED_FILES["test_infer_conf010"]).get("results", []))
    holdout_conf025 = detection_index(load_json(REQUIRED_FILES["holdout_infer"]).get("results", []))
    overlap_35b = load_35b_image_names()

    rows: list[dict[str, Any]] = []
    visual_manifest: list[dict[str, Any]] = []
    per_class_counter: Counter[str] = Counter()
    selection_summary = Counter()

    for split, results_index in (("test", test_conf025), ("holdout", holdout_conf025)):
        sorted_names = sorted(results_index.keys())
        for idx, image_name in enumerate(sorted_names, start=1):
            image_path, label_path = find_paths(split, image_name)
            image = Image.open(image_path).convert("RGB")
            gt_boxes = read_yolo_label(label_path, names, image.size)
            gt_class_names = sorted({box["class_name"] for box in gt_boxes}) or ["unknown"]
            primary_class = gt_class_names[0] if len(gt_class_names) == 1 else "+".join(gt_class_names)
            per_class_counter[primary_class] += 1

            pred_item = results_index[image_name]
            pred_boxes = []
            pred_classes = []
            pred_confs = []
            for det in pred_item.get("detections", []):
                pred_boxes.append(
                    {
                        "class_id": det.get("class_id"),
                        "class_name": det.get("class_name"),
                        "bbox": det.get("bbox", [0, 0, 0, 0]),
                        "confidence": float(det.get("confidence", 0.0)),
                    }
                )
                pred_classes.append(det.get("class_name", "unknown"))
                pred_confs.append(float(det.get("confidence", 0.0)))
            conf010_count = None
            if split == "test":
                conf010_count = len(test_conf010.get(image_name, {}).get("detections", []))

            selection_reason = [f"{split}_all"]
            risk_tags = [split]
            if not pred_boxes:
                selection_reason.append("no_detection_conf025")
                risk_tags.append("no_detection")
                selection_summary["no_detection_conf025_items"] += 1
            if len(pred_boxes) >= 5:
                selection_reason.append("high_box_count_conf025")
                risk_tags.append("high_box_count_conf025")
                selection_summary["high_box_count_conf025_items"] += 1
            if pred_confs and max(pred_confs) < 0.35:
                selection_reason.append("low_max_conf_conf025")
                risk_tags.append("low_conf")
            if split == "test" and conf010_count is not None and conf010_count - len(pred_boxes) >= 3:
                selection_reason.append("conf010_box_growth")
                risk_tags.append("conf010_growth")
                selection_summary["high_growth_conf010_items"] += 1
            if image_name in overlap_35b:
                selection_reason.append("overlap_with_35b_demo")
                risk_tags.append("compare_35b_35n")
                selection_summary["overlap_with_35b_demo_items"] += 1
            if split == "holdout":
                risk_tags.append("holdout_observation_only")

            review_id = f"{split}_{idx:03d}"
            pred_name = f"{review_id}_prediction_{image_name}"
            gt_name = f"{review_id}_ground_truth_{image_name}"
            side_name = f"{review_id}_side_by_side_{image_name}"
            pred_path = VISUAL_DIR / "prediction_only" / pred_name
            gt_path = VISUAL_DIR / "ground_truth_only" / gt_name
            side_path = VISUAL_DIR / "side_by_side" / side_name

            pred_header = [
                f"image={image_name}",
                f"split={split} conf=0.25 pred_boxes={len(pred_boxes)} gt_boxes={len(gt_boxes)}",
                f"pred_classes={','.join(sorted(set(pred_classes))) or 'none'} max_conf={max(pred_confs):.3f}" if pred_confs else "pred_classes=none max_conf=none",
                f"no_detection={str(not pred_boxes).lower()} holdout_observation_only={str(split == 'holdout').lower()}",
            ]
            gt_header = [
                f"image={image_name}",
                f"split={split} ground_truth_boxes={len(gt_boxes)} classes={','.join(gt_class_names)}",
                f"label_path={safe_rel(label_path)}",
                f"holdout_observation_only={str(split == 'holdout').lower()}",
            ]

            pred_overlay = draw_boxes(image, pred_boxes, (220, 40, 40), pred_header)
            gt_overlay = draw_boxes(image, gt_boxes, (40, 180, 60), gt_header)
            pair = side_by_side(gt_overlay, pred_overlay)

            pred_path.parent.mkdir(parents=True, exist_ok=True)
            gt_path.parent.mkdir(parents=True, exist_ok=True)
            side_path.parent.mkdir(parents=True, exist_ok=True)
            pred_overlay.save(pred_path, quality=92)
            gt_overlay.save(gt_path, quality=92)
            pair.save(side_path, quality=92)

            row = {
                "review_id": review_id,
                "source_split": split,
                "class_name": primary_class,
                "image_name": image_name,
                "image_path": str(image_path.resolve()),
                "label_path": str(label_path.resolve()),
                "prediction_visual_path": str(pred_path.resolve()),
                "ground_truth_visual_path": str(gt_path.resolve()),
                "side_by_side_visual_path": str(side_path.resolve()),
                "predicted_box_count_conf025": len(pred_boxes),
                "predicted_classes_conf025": "|".join(pred_classes),
                "max_confidence_conf025": round(max(pred_confs), 6) if pred_confs else "",
                "avg_confidence_conf025": round(sum(pred_confs) / len(pred_confs), 6) if pred_confs else "",
                "no_detection_conf025": str(not pred_boxes).lower(),
                "selection_reason": "|".join(selection_reason),
                "risk_tags": "|".join(sorted(set(risk_tags))),
                "holdout_observation_only": str(split == "holdout").lower(),
                "review_status": "unreviewed",
                "issue_type": "",
                "reviewer_notes": "",
                "reviewed_at": "",
            }
            rows.append(row)
            visual_manifest.append(
                {
                    "review_id": review_id,
                    "split": split,
                    "image_name": image_name,
                    "class_name": primary_class,
                    "prediction_visual_path": str(pred_path.resolve()),
                    "ground_truth_visual_path": str(gt_path.resolve()),
                    "side_by_side_visual_path": str(side_path.resolve()),
                    "predicted_box_count_conf025": len(pred_boxes),
                    "gt_box_count": len(gt_boxes),
                    "max_confidence_conf025": round(max(pred_confs), 6) if pred_confs else "",
                    "selection_reason": "|".join(selection_reason),
                    "risk_tags": "|".join(sorted(set(risk_tags))),
                }
            )

    total_review_items = len(rows)
    selection_summary["test_items"] = sum(1 for row in rows if row["source_split"] == "test")
    selection_summary["holdout_items"] = sum(1 for row in rows if row["source_split"] == "holdout")
    selection_summary["total_review_items"] = total_review_items
    selection_summary["gt_class_distribution"] = dict(per_class_counter)

    sampling_payload = {
        "generated_at": NOW,
        "dataset": str(DATASET_ROOT),
        "weights": str(REQUIRED_FILES["best_pt"]),
        "total_review_items": total_review_items,
        "test_items": selection_summary["test_items"],
        "holdout_items": selection_summary["holdout_items"],
        "no_detection_conf025_items": selection_summary["no_detection_conf025_items"],
        "high_box_count_conf025_items": selection_summary["high_box_count_conf025_items"],
        "high_growth_conf010_items": selection_summary["high_growth_conf010_items"],
        "overlap_with_35b_demo_items": selection_summary["overlap_with_35b_demo_items"],
        "gt_class_distribution": dict(per_class_counter),
        "sampling_rule": "all 43 test + all 9 holdout, with hard-case tags layered on top of unique images",
    }
    atomic_write_json(REPORTS / "phone_riceseg_35o_prediction_review_sampling_plan.json", sampling_payload)
    atomic_write_text(REPORTS / "phone_riceseg_35o_prediction_review_sampling_plan.md", render_sampling_md(sampling_payload))
    atomic_write_csv(
        REPORTS / "phone_riceseg_35o_prediction_review_items.csv",
        rows,
        list(rows[0].keys()),
    )
    atomic_write_json(REPORTS / "phone_riceseg_35o_prediction_review_items.json", {"generated_at": NOW, "items": rows})

    atomic_write_csv(
        REPORTS / "phone_riceseg_35o_prediction_visual_audit_manifest.csv",
        visual_manifest,
        list(visual_manifest[0].keys()),
    )
    atomic_write_json(
        REPORTS / "phone_riceseg_35o_prediction_visual_audit_manifest.json",
        {"generated_at": NOW, "items": visual_manifest},
    )

    index_lines = [
        "# Phone RiceSeg 35O Prediction Visual Audit",
        "",
        f"- dataset: `{DATASET_ROOT}`",
        f"- weights: `{REQUIRED_FILES['best_pt']}`",
        "- scope: `all 43 test + all 9 holdout images at conf=0.25`",
        "- note: holdout samples are observation only; they are not tuning evidence.",
        "",
    ]
    for row in visual_manifest:
        rel_side = safe_rel(Path(row["side_by_side_visual_path"]))
        index_lines.append(
            f"## {row['review_id']} | {row['split']} | {row['class_name']} | pred={row['predicted_box_count_conf025']} | gt={row['gt_box_count']}"
        )
        index_lines.append("")
        index_lines.append(f"- selection_reason: `{row['selection_reason']}`")
        index_lines.append(f"- risk_tags: `{row['risk_tags']}`")
        index_lines.append(f"- side_by_side_visual_path: `{rel_side}`")
        index_lines.append(f"![]({rel_side})")
        index_lines.append("")
    atomic_write_text(VISUAL_DIR / "index.md", "\n".join(index_lines))

    update_status_docs(total_review_items)

    status_payload, status_md = compute_review_status(total_review_items)
    atomic_write_json(REPORTS / "phone_riceseg_35o_prediction_review_status_check.json", status_payload)
    atomic_write_text(REPORTS / "phone_riceseg_35o_prediction_review_status_check.md", status_md)

    pending_payload = {
        "generated_at": NOW,
        "gate": status_payload["manual_prediction_review_gate"],
        "reviewed_count": status_payload["reviewed_count"],
        "total_review_items": total_review_items,
        "reason": "manual review not completed yet",
        "next_allowed_stage": "pending",
    }
    atomic_write_json(REPORTS / "phone_riceseg_35o_prediction_review_postreview_gate_result.json", pending_payload)
    atomic_write_text(
        REPORTS / "phone_riceseg_35o_prediction_review_postreview_gate_result.md",
        "\n".join(
            [
                "# Phone RiceSeg 35O Prediction Review Postreview Gate Result",
                "",
                f"- gate: `{pending_payload['gate']}`",
                f"- reviewed_count: `{pending_payload['reviewed_count']}`",
                f"- total_review_items: `{pending_payload['total_review_items']}`",
                f"- reason: {pending_payload['reason']}",
                f"- next_allowed_stage: `{pending_payload['next_allowed_stage']}`",
                "",
            ]
        ),
    )
    atomic_write_text(
        REPORTS / "phone_riceseg_35o_pending_prediction_review_notice.md",
        "\n".join(
            [
                "# Phone RiceSeg 35O Pending Prediction Review Notice",
                "",
                f"- total_review_items: `{total_review_items}`",
                "- manual_prediction_review_gate: `PENDING`",
                "- review decision files are not complete yet.",
                "- No backend integration is allowed.",
                "- No formal claim is allowed.",
                "",
            ]
        ),
    )

    final_report_md = "\n".join(
        [
            "# Thirty Fifth Round O Phone RiceSeg Prediction Visual Review Report",
            "",
            "## 本轮目标",
            "",
            "基于 35N 的 `WARNING` 结论，准备并检查 `prediction visual review` 证据链，审查的对象是模型预测框，而不是原始标签本身。",
            "",
            "## 为什么从 35N WARNING 进入 prediction visual review",
            "",
            "35N 的 mAP50 仅轻微高于 35B，但 recall 更低、test no-detection 略差、holdout 观察集不稳定，因此下一步不能直接继续宣称提升，而要先检查预测框本身是否视觉上可信。",
            "",
            f"- 35N best weight: `{REQUIRED_FILES['best_pt']}`",
            f"- dataset: `{DATASET_ROOT}`",
            "- test / holdout source: `43 test + 9 holdout`",
            "",
            "## Prediction Review Sampling Plan",
            "",
            f"- total_review_items: `{total_review_items}`",
            f"- test_items: `{selection_summary['test_items']}`",
            f"- holdout_items: `{selection_summary['holdout_items']}`",
            f"- no_detection_conf025_items: `{selection_summary['no_detection_conf025_items']}`",
            f"- high_box_count_conf025_items: `{selection_summary['high_box_count_conf025_items']}`",
            f"- high_growth_conf010_items: `{selection_summary['high_growth_conf010_items']}`",
            "",
            "## Visual Audit 输出",
            "",
            f"- visual_audit_dir: `{VISUAL_DIR}`",
            f"- visual_audit_index: `{VISUAL_DIR / 'index.md'}`",
            f"- visual_audit_manifest_csv: `{REPORTS / 'phone_riceseg_35o_prediction_visual_audit_manifest.csv'}`",
            "",
            "## Review Launcher",
            "",
            f"- launcher_script: `{ROOT / 'scripts' / 'launch_phone_riceseg_35o_prediction_review_desktop.py'}`",
            f"- launcher_bat: `{REPORTS / 'phone_riceseg_35o_start_prediction_review_desktop.bat'}`",
            "",
            "## Self-test / Status",
            "",
            f"- readiness_check: `{REPORTS / 'phone_riceseg_35o_prediction_review_readiness_check.json'}`",
            f"- launcher_selftest: `{REPORTS / 'phone_riceseg_35o_prediction_review_launcher_selftest.json'}`",
            f"- review_status_check: `{REPORTS / 'phone_riceseg_35o_prediction_review_status_check.json'}`",
            f"- current_review_gate: `{status_payload['manual_prediction_review_gate']}`",
            f"- reviewed_count: `{status_payload['reviewed_count']}`",
            "",
            "## 本轮边界",
            "",
            "- 是否训练：否",
            "- 是否生成新权重：否",
            "- 是否修改 backend：否",
            "- 是否修改真实 .env：否",
            "- 是否修改 images / masks / labels：否",
            "- 是否修改 data.yaml：否",
            "- 是否复制权重到后端：否",
            "- 是否 git add/commit：否",
            "",
            "## 下一步建议",
            "",
            "先完成人工 prediction review。审完之后，再依据 serious_issue_ratio、test/holdout 的 hard case 模式，决定进入 threshold/NMS calibration、hard case analysis、data debug，或保留 35B 作为更稳的 baseline。",
            "",
        ]
    )
    atomic_write_text(REPORTS / "thirty_fifth_round_o_phone_riceseg_prediction_visual_review_report.md", final_report_md)
    atomic_write_json(
        REPORTS / "phone_riceseg_35o_prediction_visual_review_report.json",
        {
            "generated_at": NOW,
            "goal": "prepare guarded prediction visual review for phone 35N",
            "weights": str(REQUIRED_FILES["best_pt"]),
            "dataset": str(DATASET_ROOT),
            "total_review_items": total_review_items,
            "review_status": status_payload,
            "training_executed_this_round": False,
            "new_weights_generated_this_round": False,
            "backend_modified_this_round": False,
            "env_modified_this_round": False,
            "labels_modified_this_round": False,
            "next_recommended_stage": "manual_prediction_review_pending",
        },
    )


if __name__ == "__main__":
    main()
