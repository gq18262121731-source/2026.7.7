"""Phone-36Diag-Mini: Tungro train-set recognition diagnostic.

This script is diagnostic-only:
- no training
- no dataset mutation
- no backend/frontend changes

It audits the current controlled Phone RiceSeg Tungro setup, writes
distribution/config evidence, creates label QA overlays for sampled Tungro
training images, and runs a prediction confidence sweep on Tungro training
images with the current best.pt.
"""

from __future__ import annotations

import csv
import json
import math
import os
import random
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO
import ultralytics


ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = ROOT / "datasets" / "phone_riceseg_v35m_holdout_applied"
DATA_YAML = DATASET_ROOT / "data.yaml"
RUN_DIR = ROOT / "experiments" / "phone_rgb_yolo" / "runs" / "controlled_exp_phone_riceseg_v35m_holdout_applied_10epoch"
MODEL_PATH = RUN_DIR / "weights" / "best.pt"
ARGS_YAML = RUN_DIR / "args.yaml"
MODEL_CARD_JSON = ROOT / "reports" / "phone_riceseg_35n_10epoch_model_card.json"
VALIDATE_JSON = ROOT / "reports" / "phone_riceseg_35n_10epoch_validate_summary.json"
TUNGRO_REVIEW_JSON = ROOT / "reports" / "phone_riceseg_35t_tungro_class_review_final_aggregation_report.json"
OUT_DIR = ROOT / "reports" / "phone_36diag_mini_tungro"
LABEL_VIS_DIR = OUT_DIR / "label_visualizations"
PRED_DIRS = {
    0.05: OUT_DIR / "predictions_conf_005",
    0.10: OUT_DIR / "predictions_conf_010",
    0.25: OUT_DIR / "predictions_conf_025",
}

CONF_LIST = [0.05, 0.10, 0.25]
DEFAULT_IOU = 0.7
MAX_LABEL_QA_IMAGES = 10
SEED = 2026


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


def safe_rmtree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def load_font(size: int) -> ImageFont.ImageFont:
    for candidate in [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


@dataclass
class LabelRow:
    class_id: int
    cx: float
    cy: float
    w: float
    h: float
    raw_line: str


def read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def image_and_label_dirs(split: str) -> tuple[Path, Path]:
    return DATASET_ROOT / "images" / split, DATASET_ROOT / "labels" / split


def parse_label_file(label_path: Path) -> tuple[list[LabelRow], list[str]]:
    rows: list[LabelRow] = []
    issues: list[str] = []
    if not label_path.exists():
        issues.append("missing_label")
        return rows, issues
    text = label_path.read_text(encoding="utf-8").strip()
    if not text:
        issues.append("empty_label")
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
        if row.cx < 0 or row.cx > 1 or row.cy < 0 or row.cy > 1:
            issues.append(f"center_out_of_range_line_{idx}")
        if row.w <= 0 or row.h <= 0:
            issues.append(f"nonpositive_size_line_{idx}")
        if row.w > 1 or row.h > 1:
            issues.append(f"size_gt_one_line_{idx}")
        x1 = row.cx - row.w / 2.0
        y1 = row.cy - row.h / 2.0
        x2 = row.cx + row.w / 2.0
        y2 = row.cy + row.h / 2.0
        if x1 < 0 or y1 < 0 or x2 > 1 or y2 > 1:
            issues.append(f"bbox_out_of_bounds_line_{idx}")
    return issues


def sample_items(items: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
    if len(items) <= k:
        return items
    rng = random.Random(SEED)
    return sorted(rng.sample(items, k), key=lambda row: row["image_name"])


def draw_label_overlay(image_path: Path, label_rows: list[LabelRow], class_names: dict[int, str], out_path: Path) -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = load_font(16)
    colors = {
        0: (255, 64, 64),
        1: (64, 180, 255),
        2: (255, 170, 0),
        3: (120, 255, 120),
    }
    for row in label_rows:
        x1, y1, x2, y2 = normalized_box_to_xyxy(row, image.width, image.height)
        color = colors.get(row.class_id, (255, 255, 0))
        draw.rectangle((x1, y1, x2, y2), outline=color, width=3)
        label = f"{row.class_id}:{class_names.get(row.class_id, 'unknown')}"
        text_bbox = draw.textbbox((x1, max(0, y1 - 18)), label, font=font)
        draw.rectangle(text_bbox, fill=(0, 0, 0))
        draw.text((text_bbox[0], text_bbox[1]), label, fill=color, font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, quality=92)


def classify_annotation_target(tungro_rows: list[LabelRow]) -> str:
    if not tungro_rows:
        return "uncertain"
    areas = [row.w * row.h for row in tungro_rows]
    median_area = sorted(areas)[len(areas) // 2]
    if median_area < 0.03:
        return "lesion"
    if median_area < 0.18:
        return "leaf"
    if median_area < 0.45:
        return "region"
    return "plant"


def estimate_bbox_position_quality(tungro_rows: list[LabelRow]) -> str:
    if not tungro_rows:
        return "uncertain"
    edge_touch_count = 0
    for row in tungro_rows:
        x1 = row.cx - row.w / 2.0
        y1 = row.cy - row.h / 2.0
        x2 = row.cx + row.w / 2.0
        y2 = row.cy + row.h / 2.0
        if x1 <= 0.01 or y1 <= 0.01 or x2 >= 0.99 or y2 >= 0.99:
            edge_touch_count += 1
    if edge_touch_count >= max(1, len(tungro_rows) // 2):
        return "uncertain"
    return "true"


def estimate_bbox_scale_quality(tungro_rows: list[LabelRow]) -> str:
    if not tungro_rows:
        return "uncertain"
    bad = 0
    for row in tungro_rows:
        area = row.w * row.h
        if area < 0.001 or area > 0.75:
            bad += 1
    if bad == 0:
        return "true"
    if bad == len(tungro_rows):
        return "false"
    return "uncertain"


def infer_python_env() -> str:
    import sys

    exe = Path(sys.executable)
    return exe.as_posix()


def gather_dataset_context() -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    payload = read_yaml(DATA_YAML)
    names_raw = payload.get("names", {})
    if isinstance(names_raw, list):
        class_names = {idx: value for idx, value in enumerate(names_raw)}
    elif isinstance(names_raw, dict):
        class_names = {int(key): value for key, value in names_raw.items()}
    else:
        class_names = {}

    class_count = int(payload.get("nc", len(class_names)))
    risk_notes: list[str] = []
    if not class_names:
        risk_notes.append("data.yaml missing names")
    tungro_class_id = next((cid for cid, name in class_names.items() if str(name).lower() == "tungro"), None)
    if tungro_class_id is None:
        risk_notes.append("tungro not found in data.yaml names")

    split_rows: list[dict[str, Any]] = []
    label_config_issues: list[str] = []

    for split in ["train", "val", "test"]:
        image_dir, label_dir = image_and_label_dirs(split)
        image_paths = sorted([path for path in image_dir.iterdir() if path.is_file()])
        label_paths = sorted([path for path in label_dir.iterdir() if path.is_file()])
        label_map = {path.stem: path for path in label_paths}
        image_map = {path.stem: path for path in image_paths}

        unmatched_images = sorted(set(image_map) - set(label_map))
        unmatched_labels = sorted(set(label_map) - set(image_map))
        if unmatched_images:
            label_config_issues.append(f"{split}_unmatched_images={len(unmatched_images)}")
        if unmatched_labels:
            label_config_issues.append(f"{split}_unmatched_labels={len(unmatched_labels)}")

        for image_path in image_paths:
            label_path = label_map.get(image_path.stem, label_dir / f"{image_path.stem}.txt")
            parsed_rows, parse_issues = parse_label_file(label_path)
            valid_issues = validate_label_rows(parsed_rows, class_count) if parsed_rows else []
            all_issues = parse_issues + valid_issues
            if all_issues:
                label_config_issues.extend([f"{split}:{image_path.name}:{issue}" for issue in all_issues])
            class_counter = Counter(row.class_id for row in parsed_rows)
            split_rows.append(
                {
                    "split": split,
                    "image_name": image_path.name,
                    "image_path": image_path,
                    "label_path": label_path,
                    "label_exists": label_path.exists(),
                    "rows": parsed_rows,
                    "class_counter": class_counter,
                    "issues": all_issues,
                    "image_size": Image.open(image_path).size,
                    "has_tungro": bool(tungro_class_id is not None and class_counter.get(tungro_class_id, 0) > 0),
                    "tungro_bbox_count": int(class_counter.get(tungro_class_id, 0)) if tungro_class_id is not None else 0,
                }
            )

    context = {
        "data_yaml_path": DATA_YAML.resolve().as_posix(),
        "dataset_root": DATASET_ROOT.resolve().as_posix(),
        "class_names": [class_names[idx] for idx in sorted(class_names)],
        "class_name_map": {str(idx): class_names[idx] for idx in sorted(class_names)},
        "tungro_class_id": tungro_class_id if tungro_class_id is not None else "MISSING",
        "label_config_pass": len(label_config_issues) == 0 and tungro_class_id is not None,
    }
    return context, split_rows, risk_notes + label_config_issues


def build_distribution(rows: list[dict[str, Any]], tungro_class_id: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    per_split = {}
    total_bbox_by_split = defaultdict(int)
    total_tungro_bbox_by_split = defaultdict(int)
    total_images_by_split = defaultdict(int)
    tungro_images_by_split = defaultdict(int)

    for row in rows:
        split = row["split"]
        total_images_by_split[split] += 1
        bbox_count = sum(row["class_counter"].values())
        total_bbox_by_split[split] += bbox_count
        total_tungro_bbox_by_split[split] += row["class_counter"].get(tungro_class_id, 0)
        if row["class_counter"].get(tungro_class_id, 0) > 0:
            tungro_images_by_split[split] += 1

    csv_rows = []
    for split in ["train", "val", "test"]:
        total_images = total_images_by_split[split]
        tungro_images = tungro_images_by_split[split]
        total_bboxes = total_bbox_by_split[split]
        tungro_bboxes = total_tungro_bbox_by_split[split]
        row = {
            "split": split,
            "total_images": total_images,
            "tungro_images": tungro_images,
            "total_bboxes": total_bboxes,
            "tungro_bboxes": tungro_bboxes,
            "tungro_image_ratio": round(tungro_images / total_images, 6) if total_images else 0.0,
            "tungro_bbox_ratio": round(tungro_bboxes / total_bboxes, 6) if total_bboxes else 0.0,
        }
        csv_rows.append(row)
        per_split[split] = row

    train_tungro_images = per_split["train"]["tungro_images"]
    low_sample = "uncertain"
    if train_tungro_images < 30:
        low_sample = True
    elif train_tungro_images >= 60:
        low_sample = False

    summary = {
        "train_total_images": per_split["train"]["total_images"],
        "val_total_images": per_split["val"]["total_images"],
        "test_total_images": per_split["test"]["total_images"],
        "train_tungro_images": per_split["train"]["tungro_images"],
        "val_tungro_images": per_split["val"]["tungro_images"],
        "test_tungro_images": per_split["test"]["tungro_images"],
        "train_tungro_bboxes": per_split["train"]["tungro_bboxes"],
        "val_tungro_bboxes": per_split["val"]["tungro_bboxes"],
        "test_tungro_bboxes": per_split["test"]["tungro_bboxes"],
        "train_tungro_image_ratio": per_split["train"]["tungro_image_ratio"],
        "val_tungro_image_ratio": per_split["val"]["tungro_image_ratio"],
        "test_tungro_image_ratio": per_split["test"]["tungro_image_ratio"],
        "train_tungro_bbox_ratio": per_split["train"]["tungro_bbox_ratio"],
        "val_tungro_bbox_ratio": per_split["val"]["tungro_bbox_ratio"],
        "test_tungro_bbox_ratio": per_split["test"]["tungro_bbox_ratio"],
        "tungro_is_low_sample_class": low_sample,
    }
    return csv_rows, summary


def run_label_visual_qa(rows: list[dict[str, Any]], tungro_class_id: int, class_names: dict[int, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    train_tungro_rows = [row for row in rows if row["split"] == "train" and row["has_tungro"]]
    sampled = sample_items(train_tungro_rows, MAX_LABEL_QA_IMAGES)
    qa_rows: list[dict[str, Any]] = []
    target_counter = Counter()
    for item in sampled:
        tungro_rows = [row for row in item["rows"] if row.class_id == tungro_class_id]
        draw_label_overlay(item["image_path"], item["rows"], class_names, LABEL_VIS_DIR / item["image_name"])
        annotation_target = classify_annotation_target(tungro_rows)
        target_counter[annotation_target] += 1
        qa_row = {
            "image_name": item["image_name"],
            "label_exists": str(item["label_exists"]).lower(),
            "tungro_bbox_count": len(tungro_rows),
            "bbox_position_ok": estimate_bbox_position_quality(tungro_rows),
            "bbox_scale_ok": estimate_bbox_scale_quality(tungro_rows),
            "annotation_target": annotation_target,
            "notes": ";".join(item["issues"]) if item["issues"] else "",
        }
        qa_rows.append(qa_row)

    non_uncertain_targets = {row["annotation_target"] for row in qa_rows if row["annotation_target"] != "uncertain"}
    annotation_target_inconsistency = len(non_uncertain_targets) > 1
    summary = {
        "sample_count": len(qa_rows),
        "annotation_target_counter": dict(target_counter),
        "annotation_target_inconsistency": annotation_target_inconsistency,
    }
    return qa_rows, summary


def copy_prediction_outputs(save_dir: Path, conf: float) -> None:
    dest = PRED_DIRS[conf]
    safe_rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for path in save_dir.iterdir():
        target = dest / path.name
        if path.is_file():
            shutil.copy2(path, target)


def run_prediction_sweep(rows: list[dict[str, Any]], tungro_class_id: int, class_names: dict[int, str], imgsz: int, iou: float, device: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    train_tungro_rows = [row for row in rows if row["split"] == "train" and row["has_tungro"]]
    image_paths = [str(row["image_path"]) for row in train_tungro_rows]
    model = YOLO(str(MODEL_PATH))
    csv_rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}

    for conf in CONF_LIST:
        temp_project = OUT_DIR / "_predict_tmp"
        temp_name = f"conf_{str(conf).replace('.', '')}"
        temp_save_dir = temp_project / temp_name
        safe_rmtree(temp_save_dir)
        results = model.predict(
            source=image_paths,
            conf=conf,
            iou=iou,
            imgsz=imgsz,
            device=device,
            verbose=False,
            project=str(temp_project),
            name=temp_name,
            exist_ok=True,
            save=True,
            save_txt=True,
            save_conf=True,
        )
        any_pred_images = 0
        tungro_pred_images = 0
        tungro_pred_count = 0
        tungro_conf_values: list[float] = []
        for result in results:
            class_ids = result.boxes.cls.tolist() if result.boxes is not None else []
            confs = result.boxes.conf.tolist() if result.boxes is not None else []
            if class_ids:
                any_pred_images += 1
            current_has_tungro = False
            for cls_value, conf_value in zip(class_ids, confs):
                if int(cls_value) == tungro_class_id:
                    current_has_tungro = True
                    tungro_pred_count += 1
                    tungro_conf_values.append(float(conf_value))
            if current_has_tungro:
                tungro_pred_images += 1
        copy_prediction_outputs(temp_save_dir, conf)
        row = {
            "conf": conf,
            "num_images_tested": len(train_tungro_rows),
            "num_images_with_any_prediction": any_pred_images,
            "num_images_with_tungro_prediction": tungro_pred_images,
            "num_tungro_predictions": tungro_pred_count,
            "avg_tungro_conf": round(sum(tungro_conf_values) / len(tungro_conf_values), 6) if tungro_conf_values else 0.0,
            "max_tungro_conf": round(max(tungro_conf_values), 6) if tungro_conf_values else 0.0,
            "train_set_tungro_detectable": str(tungro_pred_images > 0).lower(),
        }
        csv_rows.append(row)
        summary[str(conf)] = row

    safe_rmtree(OUT_DIR / "_predict_tmp")
    return csv_rows, summary


def classify_root_cause(
    label_config_pass: bool,
    train_set_tungro_detectable_005: bool,
    train_set_tungro_detectable_025: bool,
    annotation_target_inconsistency: bool,
) -> tuple[str, str, list[str], bool]:
    forbidden = ["backend_demo_integration", "candidate_claim"]
    if annotation_target_inconsistency:
        return "ANNOTATION_TARGET_INCONSISTENCY", "Phone-36Tungro-Annotation-Policy-Fix", forbidden + ["15_epoch_training"], False
    if not train_set_tungro_detectable_005 and not label_config_pass:
        return "TRAIN_LABEL_CONFIG_ERROR", "Phone-36Fix-LabelConfig", forbidden + ["15_epoch_training"], False
    if not train_set_tungro_detectable_005:
        return "TUNGRO_NOT_LEARNED", "Phone-36Overfit-Tungro-Mini", forbidden, False
    if train_set_tungro_detectable_005 and not train_set_tungro_detectable_025:
        return "WEAK_CONFIDENCE_DETECTION", "Phone-36Train-Controlled-Tungro-15Epoch", forbidden, True
    return "GENERALIZATION_FAILURE", "Phone-36Data-Tungro-Generalization-Plan", forbidden, False


def build_context(context: dict[str, Any], class_names: dict[int, str], imgsz: int, iou: float, device: str, risk_notes: list[str]) -> dict[str, Any]:
    args_payload = read_yaml(ARGS_YAML)
    validate_payload = read_json(VALIDATE_JSON)
    review_payload = read_json(TUNGRO_REVIEW_JSON)
    return {
        "generated_at": now_iso(),
        "project_root": ROOT.resolve().as_posix(),
        "training_project_root": ROOT.resolve().as_posix(),
        "model_path": MODEL_PATH.resolve().as_posix() if MODEL_PATH.exists() else "MISSING",
        "data_yaml_path": DATA_YAML.resolve().as_posix() if DATA_YAML.exists() else "MISSING",
        "class_names": [class_names[idx] for idx in sorted(class_names)],
        "tungro_class_id": context["tungro_class_id"],
        "train_images_path": (DATASET_ROOT / "images" / "train").resolve().as_posix(),
        "train_labels_path": (DATASET_ROOT / "labels" / "train").resolve().as_posix(),
        "val_images_path": (DATASET_ROOT / "images" / "val").resolve().as_posix(),
        "val_labels_path": (DATASET_ROOT / "labels" / "val").resolve().as_posix(),
        "test_images_path": (DATASET_ROOT / "images" / "test").resolve().as_posix(),
        "test_labels_path": (DATASET_ROOT / "labels" / "test").resolve().as_posix(),
        "imgsz": imgsz,
        "conf_list": CONF_LIST,
        "iou": iou,
        "device": device,
        "run_source": {
            "run_dir": RUN_DIR.resolve().as_posix(),
            "run_name": args_payload.get("name", "MISSING"),
            "run_time": "MISSING",
            "training_round": "Phone-35N",
            "training_report_dataset": read_json(MODEL_CARD_JSON).get("dataset", "MISSING") if MODEL_CARD_JSON.exists() else "MISSING",
        },
        "python_env": infer_python_env(),
        "ultralytics_version": getattr(ultralytics, "__version__", "MISSING"),
        "validate_summary_path": VALIDATE_JSON.resolve().as_posix() if VALIDATE_JSON.exists() else "MISSING",
        "tungro_review_summary": {
            "tungro_class_reliability": review_payload.get("tungro_class_reliability", "MISSING"),
            "confirmed_tungro_count": review_payload.get("confirmed_tungro_count", "MISSING"),
            "ambiguous_tungro_count": review_payload.get("ambiguous_tungro_count", "MISSING"),
        },
        "risk_notes": risk_notes,
    }


def render_report(payload: dict[str, Any]) -> str:
    q = payload["questions"]
    gate = payload["gate"]
    dist = payload["distribution_summary"]
    val = payload["validate_reference"]
    lines = [
        "# Phone-36Diag-Mini Tungro Diagnostic Report",
        "",
        "## Scope",
        "",
        "- This round trained a formal model: NO",
        "- Generated new formal weights: NO",
        "- Overwrote existing weights: NO",
        "- Modified backend: NO",
        "- Modified frontend: NO",
        "- Modified .env: NO",
        "- Allow backend demo claim: NO",
        "- Allow candidate claim: NO",
        "",
        "## Diagnostic Target",
        "",
        f"- Model path: `{payload['diagnostic_context']['model_path']}`",
        f"- Data YAML: `{payload['diagnostic_context']['data_yaml_path']}`",
        f"- Dataset root: `{payload['diagnostic_context']['train_images_path']}` (train images root)",
        f"- Class names: `{payload['diagnostic_context']['class_names']}`",
        f"- Tungro class id: `{payload['diagnostic_context']['tungro_class_id']}`",
        "",
        "## Reference Context",
        "",
        f"- 35T Tungro class reliability: `{payload['diagnostic_context']['tungro_review_summary']['tungro_class_reliability']}`",
        f"- 35N experimental mAP50: `{val.get('experimental_metrics', {}).get('mAP50', 'MISSING')}`",
        f"- 35N Tungro per-class AP: `{val.get('experimental_metrics', {}).get('per_class_ap', {}).get('tungro', 'MISSING')}`",
        "",
        "## Label / Config Check",
        "",
        f"- label_config_pass: `{str(payload['label_config_pass']).lower()}`",
        f"- class_id confirmed: `{str(payload['tungro_class_id_confirmed']).lower()}`",
        f"- risk notes count: `{len(payload['risk_notes'])}`",
        "",
        "## Tungro Distribution",
        "",
        f"- train_total_images: `{dist['train_total_images']}`",
        f"- val_total_images: `{dist['val_total_images']}`",
        f"- test_total_images: `{dist['test_total_images']}`",
        f"- train_tungro_images: `{dist['train_tungro_images']}`",
        f"- val_tungro_images: `{dist['val_tungro_images']}`",
        f"- test_tungro_images: `{dist['test_tungro_images']}`",
        f"- train_tungro_bboxes: `{dist['train_tungro_bboxes']}`",
        f"- val_tungro_bboxes: `{dist['val_tungro_bboxes']}`",
        f"- test_tungro_bboxes: `{dist['test_tungro_bboxes']}`",
        f"- tungro_is_low_sample_class: `{dist['tungro_is_low_sample_class']}`",
        "",
        "## Label Visual QA",
        "",
        f"- label_visual_qa_done: `{str(payload['label_visual_qa_done']).lower()}`",
        f"- annotation_target_inconsistency: `{str(payload['annotation_target_inconsistency']).lower()}`",
        f"- annotation target counter: `{payload['label_visual_qa_summary']['annotation_target_counter']}`",
        "",
        "## Train-Set Tungro Prediction Sweep",
        "",
    ]
    for row in payload["prediction_conf_sweep_rows"]:
        lines.extend(
            [
                f"- conf={row['conf']}: any_pred_images={row['num_images_with_any_prediction']}/{row['num_images_tested']}, "
                f"tungro_pred_images={row['num_images_with_tungro_prediction']}/{row['num_images_tested']}, "
                f"num_tungro_predictions={row['num_tungro_predictions']}, avg_tungro_conf={row['avg_tungro_conf']}, "
                f"max_tungro_conf={row['max_tungro_conf']}, train_set_tungro_detectable={row['train_set_tungro_detectable']}",
            ]
        )
    lines.extend(
        [
            "",
            "## Root Cause Classification",
            "",
            f"- final_root_cause: `{payload['final_root_cause']}`",
            f"- next_allowed_stage: `{gate['next_allowed_stage']}`",
            f"- forbidden_stage: `{', '.join(gate['forbidden_stage'])}`",
            "",
            "## Final Answers",
            "",
            f"1. Current best.pt can detect Tungro on the training set: `{q['q1_train_set_can_detect']}`",
            f"2. Weak Tungro prediction exists at conf=0.05: `{q['q2_weak_detection_conf005']}`",
            f"3. conf=0.25 still has major NO_DETECTION: `{q['q3_conf025_still_major_no_detection']}`",
            f"4. Label/config has a clear issue: `{q['q4_label_config_clear_issue']}`",
            f"5. Tungro training samples are clearly insufficient: `{q['q5_train_samples_clearly_insufficient']}`",
            f"6. Tungro annotation target is consistent: `{q['q6_annotation_target_consistent']}`",
            f"7. Allow 15 epoch controlled training now: `{q['q7_allow_15_epoch_controlled_training']}`",
            f"8. Allow backend demo claim now: `{q['q8_allow_backend_demo_claim']}`",
            "",
            "## Gate",
            "",
            f"- phone_36diag_mini_gate: `{gate['phone_36diag_mini_gate']}`",
            f"- label_config_pass: `{str(gate['label_config_pass']).lower()}`",
            f"- tungro_class_id_confirmed: `{str(gate['tungro_class_id_confirmed']).lower()}`",
            f"- tungro_train_distribution_checked: `{str(gate['tungro_train_distribution_checked']).lower()}`",
            f"- label_visual_qa_done: `{str(gate['label_visual_qa_done']).lower()}`",
            f"- train_set_tungro_detectable: `{str(gate['train_set_tungro_detectable']).lower()}`",
            f"- low_conf_weak_detection_exists: `{str(gate['low_conf_weak_detection_exists']).lower()}`",
            f"- annotation_target_inconsistency: `{str(gate['annotation_target_inconsistency']).lower()}`",
            f"- allow_15_epoch_controlled_training: `{str(gate['allow_15_epoch_controlled_training']).lower()}`",
            f"- allow_backend_demo_claim: `{str(gate['allow_backend_demo_claim']).lower()}`",
            f"- allow_candidate_claim: `{str(gate['allow_candidate_claim']).lower()}`",
            f"- next_allowed_stage: `{gate['next_allowed_stage']}`",
            f"- forbidden_stage: `{', '.join(gate['forbidden_stage'])}`",
            "",
        ]
    )
    if payload["risk_notes"]:
        lines.extend(["## Risk Notes", ""])
        for note in payload["risk_notes"]:
            lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    random.seed(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LABEL_VIS_DIR.mkdir(parents=True, exist_ok=True)
    for pred_dir in PRED_DIRS.values():
        pred_dir.mkdir(parents=True, exist_ok=True)

    dataset_context, split_rows, risk_notes = gather_dataset_context()
    class_names = {idx: name for idx, name in enumerate(dataset_context["class_names"])}
    tungro_class_id = dataset_context["tungro_class_id"]
    if tungro_class_id == "MISSING":
        raise RuntimeError("Tungro class id could not be confirmed from data.yaml")

    args_payload = read_yaml(ARGS_YAML)
    imgsz = int(args_payload.get("imgsz", 640))
    device = str(args_payload.get("device", "cpu"))
    iou = float(args_payload.get("iou", DEFAULT_IOU))

    diagnostic_context = build_context(dataset_context, class_names, imgsz, iou, device, risk_notes)
    dist_rows, dist_summary = build_distribution(split_rows, int(tungro_class_id))
    label_qa_rows, label_qa_summary = run_label_visual_qa(split_rows, int(tungro_class_id), class_names)
    pred_rows, pred_summary = run_prediction_sweep(split_rows, int(tungro_class_id), class_names, imgsz, iou, device)

    detect_005 = pred_summary["0.05"]["num_images_with_tungro_prediction"] > 0
    detect_025 = pred_summary["0.25"]["num_images_with_tungro_prediction"] > 0
    final_root_cause, next_stage, forbidden_stage, allow_15_epoch = classify_root_cause(
        label_config_pass=dataset_context["label_config_pass"],
        train_set_tungro_detectable_005=detect_005,
        train_set_tungro_detectable_025=detect_025,
        annotation_target_inconsistency=label_qa_summary["annotation_target_inconsistency"],
    )
    low_conf_weak_detection_exists = detect_005 and not detect_025
    gate_value = "PASS" if dataset_context["label_config_pass"] and dist_summary["train_tungro_images"] > 0 else "BLOCKED"
    if gate_value == "PASS" and (low_conf_weak_detection_exists or label_qa_summary["annotation_target_inconsistency"]):
        gate_value = "WARNING"

    questions = {
        "q1_train_set_can_detect": "YES" if detect_005 else "NO",
        "q2_weak_detection_conf005": "YES" if low_conf_weak_detection_exists else "NO",
        "q3_conf025_still_major_no_detection": "YES" if not detect_025 else "NO",
        "q4_label_config_clear_issue": "YES" if not dataset_context["label_config_pass"] else "NO",
        "q5_train_samples_clearly_insufficient": "YES" if dist_summary["tungro_is_low_sample_class"] is True else "NO",
        "q6_annotation_target_consistent": "NO" if label_qa_summary["annotation_target_inconsistency"] else "YES",
        "q7_allow_15_epoch_controlled_training": "YES" if allow_15_epoch else "NO",
        "q8_allow_backend_demo_claim": "NO",
    }

    gate = {
        "phone_36diag_mini_gate": gate_value,
        "label_config_pass": dataset_context["label_config_pass"],
        "tungro_class_id_confirmed": tungro_class_id != "MISSING",
        "tungro_train_distribution_checked": True,
        "label_visual_qa_done": True,
        "train_set_tungro_detectable": detect_005,
        "low_conf_weak_detection_exists": low_conf_weak_detection_exists,
        "annotation_target_inconsistency": label_qa_summary["annotation_target_inconsistency"],
        "allow_15_epoch_controlled_training": allow_15_epoch,
        "allow_backend_demo_claim": False,
        "allow_candidate_claim": False,
        "next_allowed_stage": next_stage,
        "forbidden_stage": forbidden_stage,
    }

    report_payload = {
        "generated_at": now_iso(),
        "diagnostic_context": diagnostic_context,
        "label_config_pass": dataset_context["label_config_pass"],
        "tungro_class_id_confirmed": tungro_class_id != "MISSING",
        "distribution_summary": dist_summary,
        "label_visual_qa_done": True,
        "label_visual_qa_summary": label_qa_summary,
        "prediction_conf_sweep_rows": pred_rows,
        "prediction_conf_sweep_summary": pred_summary,
        "annotation_target_inconsistency": label_qa_summary["annotation_target_inconsistency"],
        "final_root_cause": final_root_cause,
        "questions": questions,
        "gate": gate,
        "risk_notes": risk_notes,
        "validate_reference": read_json(VALIDATE_JSON) if VALIDATE_JSON.exists() else {},
    }

    atomic_write_json(OUT_DIR / "diagnostic_context.json", diagnostic_context)
    atomic_write_csv(
        OUT_DIR / "tungro_distribution.csv",
        dist_rows,
        ["split", "total_images", "tungro_images", "total_bboxes", "tungro_bboxes", "tungro_image_ratio", "tungro_bbox_ratio"],
    )
    atomic_write_csv(
        OUT_DIR / "label_visual_qa.csv",
        label_qa_rows,
        ["image_name", "label_exists", "tungro_bbox_count", "bbox_position_ok", "bbox_scale_ok", "annotation_target", "notes"],
    )
    atomic_write_csv(
        OUT_DIR / "prediction_conf_sweep.csv",
        pred_rows,
        ["conf", "num_images_tested", "num_images_with_any_prediction", "num_images_with_tungro_prediction", "num_tungro_predictions", "avg_tungro_conf", "max_tungro_conf", "train_set_tungro_detectable"],
    )
    atomic_write_text(OUT_DIR / "phone_36diag_mini_tungro_report.md", render_report(report_payload))


if __name__ == "__main__":
    main()
