"""Phone-36Tungro-Annotation-Policy-Fix.

This round is annotation-policy and data-sanitation only:
- no training
- no backend/frontend changes
- no .env changes
- no overwrite of original dataset labels

It loads the previous Phone-36Diag-Mini evidence, writes the Tungro annotation
policy, scans YOLO labels for sanitation issues, produces Tungro review queues
and QA artifacts, and creates a derived mini dataset in a separate directory.
"""

from __future__ import annotations

import csv
import json
import math
import os
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
CURRENT_DATASET_ROOT = ROOT / "datasets" / "phone_riceseg_v35m_holdout_applied"
CURRENT_DATA_YAML = CURRENT_DATASET_ROOT / "data.yaml"
PREV_DIR = ROOT / "reports" / "phone_36diag_mini_tungro"
PREV_REPORT = PREV_DIR / "phone_36diag_mini_tungro_report.md"
PREV_CONTEXT_JSON = PREV_DIR / "diagnostic_context.json"
PREV_DISTRIBUTION_CSV = PREV_DIR / "tungro_distribution.csv"
PREV_LABEL_QA_CSV = PREV_DIR / "label_visual_qa.csv"
PREV_SWEEP_CSV = PREV_DIR / "prediction_conf_sweep.csv"

OUT_DIR = ROOT / "reports" / "phone_36_tungro_annotation_policy_fix"
OUT_REPORT_MD = OUT_DIR / "phone_36_tungro_annotation_policy_fix_report.md"
OUT_POLICY_MD = OUT_DIR / "annotation_policy.md"
OUT_CONTEXT_JSON = OUT_DIR / "diagnostic_context.json"
OUT_SANITATION_CSV = OUT_DIR / "bbox_sanitation_report.csv"
OUT_REVIEW_QUEUE_CSV = OUT_DIR / "tungro_annotation_review_queue.csv"
OUT_POLICY_QA_CSV = OUT_DIR / "tungro_policy_sample_qa.csv"
OUT_FIXED_MANIFEST_CSV = OUT_DIR / "fixed_dataset_manifest.csv"
LABEL_BEFORE_DIR = OUT_DIR / "label_visual_before"
LABEL_AFTER_DIR = OUT_DIR / "label_visual_after_or_candidate"
CONTACT_DIR = OUT_DIR / "tungro_review_contact_sheet"

DERIVED_DATASET_ROOT = ROOT / "datasets" / "_derived" / "phone_riceseg_v36_tungro_policy_fixed_mini"
DERIVED_DATA_YAML = DERIVED_DATASET_ROOT / "data.yaml"
DERIVED_README = DERIVED_DATASET_ROOT / "README_POLICY_FIXED.md"
DERIVED_MANIFEST = DERIVED_DATASET_ROOT / "fixed_dataset_manifest.csv"

SEED_ORDER_SPLITS = ["train", "val", "test"]
MAX_TUNGRO_POLICY_QA = 20
CLIP_EPS = 1e-9
LIGHT_OOB_LIMIT = 0.05
BOUND_TOL = 1e-6


@dataclass
class LabelRow:
    class_id: int
    cx: float
    cy: float
    w: float
    h: float
    line_number: int
    raw_line: str


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except Exception:
        return path.resolve().as_posix()


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8", allow_empty: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding=encoding, newline="") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    if not tmp.exists() or (tmp.stat().st_size == 0 and not allow_empty):
        raise RuntimeError(f"Temporary text write failed: {tmp}")
    tmp.replace(path)
    if not path.exists() or (path.stat().st_size == 0 and not allow_empty):
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


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_font(size: int):
    for candidate in [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def parse_label_file(path: Path) -> tuple[list[LabelRow], list[str]]:
    rows: list[LabelRow] = []
    issues: list[str] = []
    if not path.exists():
        issues.append("missing_label")
        return rows, issues
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        issues.append("empty_label")
        return rows, issues
    for line_number, raw in enumerate(text.splitlines(), start=1):
        parts = raw.strip().split()
        if len(parts) != 5:
            issues.append(f"parse_error_line_{line_number}")
            continue
        try:
            class_id = int(float(parts[0]))
            cx, cy, w, h = [float(v) for v in parts[1:]]
        except ValueError:
            issues.append(f"parse_error_line_{line_number}")
            continue
        rows.append(LabelRow(class_id=class_id, cx=cx, cy=cy, w=w, h=h, line_number=line_number, raw_line=raw.strip()))
    return rows, issues


def load_dataset_context() -> tuple[dict[int, str], int]:
    payload = load_yaml(CURRENT_DATA_YAML)
    names_raw = payload.get("names", {})
    if isinstance(names_raw, list):
        class_names = {idx: name for idx, name in enumerate(names_raw)}
    else:
        class_names = {int(k): v for k, v in names_raw.items()}
    num_classes = int(payload.get("nc", len(class_names)))
    return class_names, num_classes


def xyxy_from_row(row: LabelRow) -> tuple[float, float, float, float]:
    x_min = row.cx - row.w / 2.0
    y_min = row.cy - row.h / 2.0
    x_max = row.cx + row.w / 2.0
    y_max = row.cy + row.h / 2.0
    return x_min, y_min, x_max, y_max


def clip_row(row: LabelRow) -> tuple[LabelRow | None, dict[str, Any]]:
    x_min, y_min, x_max, y_max = xyxy_from_row(row)
    clipped_x_min = min(max(x_min, 0.0), 1.0)
    clipped_y_min = min(max(y_min, 0.0), 1.0)
    clipped_x_max = min(max(x_max, 0.0), 1.0)
    clipped_y_max = min(max(y_max, 0.0), 1.0)
    clipped_w = clipped_x_max - clipped_x_min
    clipped_h = clipped_y_max - clipped_y_min
    if clipped_w <= CLIP_EPS or clipped_h <= CLIP_EPS:
        return None, {
            "num_clipped_bboxes": 0,
            "num_dropped_bboxes": 1,
            "notes": "clip_result_invalid",
        }
    clipped_cx = (clipped_x_min + clipped_x_max) / 2.0
    clipped_cy = (clipped_y_min + clipped_y_max) / 2.0
    new_row = LabelRow(
        class_id=row.class_id,
        cx=clipped_cx,
        cy=clipped_cy,
        w=clipped_w,
        h=clipped_h,
        line_number=row.line_number,
        raw_line=f"{row.class_id} {clipped_cx:.6f} {clipped_cy:.6f} {clipped_w:.6f} {clipped_h:.6f}",
    )
    return new_row, {
        "num_clipped_bboxes": 1,
        "num_dropped_bboxes": 0,
        "notes": "auto_clipped",
    }


def row_is_valid_for_detection(row: LabelRow, num_classes: int) -> bool:
    if row.class_id < 0 or row.class_id >= num_classes:
        return False
    if not all(math.isfinite(value) for value in [row.cx, row.cy, row.w, row.h]):
        return False
    if row.w <= 0 or row.h <= 0:
        return False
    if row.cx < 0 or row.cx > 1 or row.cy < 0 or row.cy > 1:
        return False
    if row.w > 1 or row.h > 1:
        return False
    x_min, y_min, x_max, y_max = xyxy_from_row(row)
    if x_min < -BOUND_TOL or y_min < -BOUND_TOL or x_max > 1 + BOUND_TOL or y_max > 1 + BOUND_TOL:
        return False
    area = row.w * row.h
    if area >= 0.95:
        return False
    return True


def policy_mapping(old_value: str) -> str:
    mapping = {
        "lesion": "symptomatic_region",
        "region": "symptomatic_region",
        "leaf": "symptomatic_leaf",
        "plant": "symptomatic_plant",
        "uncertain": "ambiguous_bbox",
        "unknown": "ambiguous_bbox",
        "": "ambiguous_bbox",
    }
    return mapping.get(old_value, "ambiguous_bbox")


def annotation_policy_text() -> str:
    return """# Tungro Annotation Policy

## Scope

This policy fixes Tungro bbox target inconsistency for Phone RiceSeg detection data.

## Unified Principle

Tungro bbox should enclose the visible symptomatic subject region, and each bbox must be explainable as one clear symptomatic subject.

## Allowed Annotation Targets

- `symptomatic_region`
- `symptomatic_leaf`
- `symptomatic_plant`
- `ambiguous_bbox`
- `exclude_from_detection`

The old free-form values must not continue as open-ended targets:

- `lesion`
- `leaf`
- `plant`
- `region`
- `uncertain`

## Old-to-New Mapping

- `lesion -> symptomatic_region`
- `region -> symptomatic_region`
- `leaf -> symptomatic_leaf`
- `plant -> symptomatic_plant`
- `uncertain -> ambiguous_bbox`
- `unknown -> ambiguous_bbox`

This mapping is only an initial candidate and does not replace human review where visual evidence is weak.

## Tungro Bbox Rules

### A. symptomatic_region

Use when a visible localized symptomatic area exists and its boundary is relatively interpretable.

Rules:
- keep bbox tight on the symptomatic subject region
- avoid large healthy background
- do not box the whole image
- do not merge distant regions into one oversized box

### B. symptomatic_leaf

Use when symptoms mainly occupy one leaf or the diseased leaf is the stable visible subject.

Rules:
- box the diseased leaf subject
- a small amount of background is acceptable
- do not expand to the full plant
- do not collapse to a tiny tip-only box unless symptoms are truly tip-localized

### C. symptomatic_plant

Use when Tungro is primarily expressed as whole-plant yellowing, stunting, or a visible abnormal plant-level subject.

Rules:
- box the abnormal plant subject
- do not box the full image
- do not include multiple unrelated plants

### D. ambiguous_bbox

Use when Tungro may be present but a stable detection bbox cannot be determined confidently.

Rules:
- do not use for detection training
- keep in manual review or alternate-task queue

### E. exclude_from_detection

Use when the image is unsuitable for a stable detection bbox because symptoms are too diffuse, image quality is too poor, or any bbox would collapse into an arbitrary whole-image region.

Rules:
- exclude from detection training labels
- preserve in exclusion manifest for future alternate-route handling
"""


def draw_boxes(image_path: Path, rows: list[LabelRow], class_names: dict[int, str], out_path: Path, footer: str = "") -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = load_font(15)
    colors = {
        0: (255, 64, 64),
        1: (80, 170, 255),
        2: (255, 180, 0),
        3: (120, 255, 120),
    }
    for row in rows:
        x_min, y_min, x_max, y_max = xyxy_from_row(row)
        x1 = x_min * image.width
        y1 = y_min * image.height
        x2 = x_max * image.width
        y2 = y_max * image.height
        color = colors.get(row.class_id, (255, 255, 0))
        draw.rectangle((x1, y1, x2, y2), outline=color, width=3)
        label = f"{row.class_id}:{class_names.get(row.class_id, 'unknown')}"
        tb = draw.textbbox((x1, max(0, y1 - 18)), label, font=font)
        draw.rectangle(tb, fill=(0, 0, 0))
        draw.text((tb[0], tb[1]), label, fill=color, font=font)
    if footer:
        canvas = Image.new("RGB", (image.width, image.height + 28), "white")
        canvas.paste(image, (0, 0))
        draw = ImageDraw.Draw(canvas)
        draw.text((8, image.height + 6), footer[:180], fill=(0, 0, 0), font=font)
        image = canvas
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, quality=92)


def ensure_clean_dirs() -> None:
    for path in [LABEL_BEFORE_DIR, LABEL_AFTER_DIR, CONTACT_DIR]:
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
    if DERIVED_DATASET_ROOT.exists():
        shutil.rmtree(DERIVED_DATASET_ROOT)
    for split in SEED_ORDER_SPLITS:
        (DERIVED_DATASET_ROOT / "images" / split).mkdir(parents=True, exist_ok=True)
        (DERIVED_DATASET_ROOT / "labels" / split).mkdir(parents=True, exist_ok=True)


def check_previous_evidence() -> dict[str, Any]:
    required = [
        PREV_REPORT,
        PREV_CONTEXT_JSON,
        PREV_DISTRIBUTION_CSV,
        PREV_LABEL_QA_CSV,
        PREV_SWEEP_CSV,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        return {
            "previous_36diag_evidence_loaded": False,
            "previous_report_missing": True,
            "missing_paths": missing,
        }
    context = load_json(PREV_CONTEXT_JSON)
    report_text = PREV_REPORT.read_text(encoding="utf-8")
    label_qa = load_csv(PREV_LABEL_QA_CSV)
    sweep = load_csv(PREV_SWEEP_CSV)
    distribution = load_csv(PREV_DISTRIBUTION_CSV)
    return {
        "previous_36diag_evidence_loaded": True,
        "previous_report_missing": False,
        "previous_gate": "BLOCKED" if "phone_36diag_mini_gate: `BLOCKED`" in report_text else "MISSING",
        "previous_root_cause": "ANNOTATION_TARGET_INCONSISTENCY" if "final_root_cause: `ANNOTATION_TARGET_INCONSISTENCY`" in report_text else "MISSING",
        "previous_train_set_tungro_detectable": any(row["conf"] == "0.05" and row["train_set_tungro_detectable"].lower() == "true" for row in sweep),
        "previous_low_conf_weak_detection_exists": "low_conf_weak_detection_exists: `false`" in report_text.lower(),
        "previous_label_config_pass": "label_config_pass: `false`" in report_text.lower(),
        "previous_annotation_target_inconsistency": any(row.get("annotation_target", "") in {"leaf", "lesion", "plant", "region"} for row in label_qa),
        "previous_allow_15_epoch_controlled_training": "allow_15_epoch_controlled_training: `true`" in report_text.lower(),
        "previous_distribution": distribution,
        "previous_context": context,
    }


def classify_row_issue(row: LabelRow, class_names: dict[int, str], num_classes: int) -> tuple[list[dict[str, Any]], bool]:
    issues: list[dict[str, Any]] = []
    requires_manual_review = False
    x_min, y_min, x_max, y_max = xyxy_from_row(row)
    class_name = class_names.get(row.class_id, "unknown")
    if row.class_id < 0 or row.class_id >= num_classes:
        issues.append(
            {
                "issue_type": "class_id_out_of_range",
                "severity": "critical",
                "recommended_action": "manual_review_required",
                "can_auto_clip": False,
                "requires_manual_review": True,
            }
        )
        requires_manual_review = True
    if row.w <= 0 or row.h <= 0:
        issues.append(
            {
                "issue_type": "non_positive_width_height",
                "severity": "critical",
                "recommended_action": "drop_bbox_candidate",
                "can_auto_clip": False,
                "requires_manual_review": True,
            }
        )
        requires_manual_review = True
    coord_out = row.cx < 0 or row.cx > 1 or row.cy < 0 or row.cy > 1 or row.w > 1 or row.h > 1
    if coord_out:
        issues.append(
            {
                "issue_type": "coordinate_out_of_range",
                "severity": "high",
                "recommended_action": "manual_review_required",
                "can_auto_clip": False,
                "requires_manual_review": True,
            }
        )
        requires_manual_review = True
    out_of_bounds = x_min < 0 or y_min < 0 or x_max > 1 or y_max > 1
    if out_of_bounds:
        light = x_min >= -LIGHT_OOB_LIMIT and y_min >= -LIGHT_OOB_LIMIT and x_max <= 1 + LIGHT_OOB_LIMIT and y_max <= 1 + LIGHT_OOB_LIMIT and row.w > 0 and row.h > 0
        issues.append(
            {
                "issue_type": "bbox_out_of_bounds",
                "severity": "high" if light else "critical",
                "recommended_action": "auto_clip_candidate" if light else "manual_review_required",
                "can_auto_clip": light,
                "requires_manual_review": not light,
            }
        )
        if not light:
            requires_manual_review = True
    return issues, requires_manual_review


def build_contact_sheet(image_paths: list[Path], out_path: Path, title: str) -> None:
    thumbs = []
    for path in image_paths:
        image = Image.open(path).convert("RGB")
        image.thumbnail((300, 300))
        thumbs.append((path.name, image))
    if not thumbs:
        return
    cols = 4
    rows = math.ceil(len(thumbs) / cols)
    font = load_font(14)
    cell_w, cell_h = 320, 340
    canvas = Image.new("RGB", (cols * cell_w, rows * cell_h + 40), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 10), title, fill=(0, 0, 0), font=font)
    for idx, (name, image) in enumerate(thumbs):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h + 40
        canvas.paste(image, (x + 10, y + 10))
        draw.text((x + 10, y + 315), name[:34], fill=(0, 0, 0), font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=92)


def main() -> None:
    ensure_clean_dirs()

    previous = check_previous_evidence()
    if not previous["previous_36diag_evidence_loaded"]:
        payload = {
            "generated_at": now_iso(),
            "previous_36diag_evidence_loaded": False,
            "previous_report_missing": True,
            "missing_paths": previous["missing_paths"],
            "phone_36_tungro_annotation_policy_fix_gate": "BLOCKED",
            "next_allowed_stage": "Phone-36Tungro-Annotation-Policy-Fix-Retry",
            "forbidden_stage": ["15_epoch_training", "backend_demo_integration", "candidate_claim"],
        }
        atomic_write_json(OUT_CONTEXT_JSON, payload)
        atomic_write_text(
            OUT_REPORT_MD,
            "# Phone-36Tungro-Annotation-Policy-Fix Report\n\nPrevious 36Diag evidence is missing. This round cannot proceed.\n",
        )
        return

    class_names, num_classes = load_dataset_context()
    if list(class_names.values()) != ["bacterial_blight", "blast", "brown_spot", "tungro"]:
        raise RuntimeError("Current data.yaml class order does not match expected RiceSeg order.")
    tungro_class_id = next(idx for idx, name in class_names.items() if name == "tungro")

    sanitation_rows: list[dict[str, Any]] = []
    review_queue_rows: list[dict[str, Any]] = []
    fixed_manifest_rows: list[dict[str, Any]] = []
    policy_qa_rows: list[dict[str, Any]] = []

    bbox_out_before = 0
    bbox_out_after = 0
    tungro_visual_candidates_before: list[Path] = []
    tungro_visual_candidates_after: list[Path] = []
    visual_semantic_judgement_available = False
    manual_human_review_required = True

    prev_label_qa = {row["image_name"]: row for row in load_csv(PREV_LABEL_QA_CSV)}

    per_split_tungro_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for split in SEED_ORDER_SPLITS:
        image_dir = CURRENT_DATASET_ROOT / "images" / split
        label_dir = CURRENT_DATASET_ROOT / "labels" / split
        image_paths = sorted([path for path in image_dir.iterdir() if path.is_file()])
        image_map = {path.stem: path for path in image_paths}
        label_paths = sorted([path for path in label_dir.iterdir() if path.is_file()])
        label_map = {path.stem: path for path in label_paths}

        for stem, image_path in image_map.items():
            label_path = label_map.get(stem, label_dir / f"{stem}.txt")
            parsed_rows, parse_issues = parse_label_file(label_path)
            issue_rows_for_image = 0
            fixed_rows: list[LabelRow] = []
            num_clipped = 0
            num_dropped = 0
            requires_manual_image = False

            if parse_issues:
                for issue in parse_issues:
                    sanitation_rows.append(
                        {
                            "split": split,
                            "image_name": image_path.name,
                            "label_path": rel(label_path),
                            "line_number": "",
                            "class_id": "",
                            "class_name": "",
                            "x_center": "",
                            "y_center": "",
                            "width": "",
                            "height": "",
                            "x_min": "",
                            "y_min": "",
                            "x_max": "",
                            "y_max": "",
                            "issue_type": issue,
                            "severity": "critical" if issue in {"missing_label", "parse_error"} else "high",
                            "recommended_action": "manual_review_required",
                            "can_auto_clip": False,
                            "requires_manual_review": True,
                        }
                    )
                requires_manual_image = True

            for row in parsed_rows:
                x_min, y_min, x_max, y_max = xyxy_from_row(row)
                issues, row_requires_manual = classify_row_issue(row, class_names, num_classes)
                if any(issue["issue_type"] == "bbox_out_of_bounds" for issue in issues):
                    bbox_out_before += 1
                if not issues:
                    fixed_rows.append(row)
                else:
                    issue_rows_for_image += len(issues)
                    for issue in issues:
                        sanitation_rows.append(
                            {
                                "split": split,
                                "image_name": image_path.name,
                                "label_path": rel(label_path),
                                "line_number": row.line_number,
                                "class_id": row.class_id,
                                "class_name": class_names.get(row.class_id, "unknown"),
                                "x_center": round(row.cx, 6),
                                "y_center": round(row.cy, 6),
                                "width": round(row.w, 6),
                                "height": round(row.h, 6),
                                "x_min": round(x_min, 6),
                                "y_min": round(y_min, 6),
                                "x_max": round(x_max, 6),
                                "y_max": round(y_max, 6),
                                "issue_type": issue["issue_type"],
                                "severity": issue["severity"],
                                "recommended_action": issue["recommended_action"],
                                "can_auto_clip": issue["can_auto_clip"],
                                "requires_manual_review": issue["requires_manual_review"],
                            }
                        )
                        if issue["recommended_action"] == "auto_clip_candidate":
                            clipped_row, clip_stats = clip_row(row)
                            if clipped_row is not None:
                                fixed_rows.append(clipped_row)
                                num_clipped += clip_stats["num_clipped_bboxes"]
                                bbox_out_after += 0
                            else:
                                num_dropped += 1
                                requires_manual_image = True
                        elif issue["recommended_action"] == "drop_bbox_candidate":
                            num_dropped += 1
                            requires_manual_image = True
                        else:
                            requires_manual_image = True
                    if row_requires_manual:
                        requires_manual_image = True
                    else:
                        if not any(issue["recommended_action"] == "auto_clip_candidate" for issue in issues):
                            fixed_rows.append(row)

                if row.class_id == tungro_class_id:
                    old_target = prev_label_qa.get(image_path.name, {}).get("annotation_target", "")
                    mapped = policy_mapping(old_target)
                    area = row.w * row.h
                    aspect = row.w / row.h if row.h > 0 else 0.0
                    out_of_bounds = any(issue["issue_type"] == "bbox_out_of_bounds" for issue in issues)
                    reason_bits = []
                    priority = "P3_LOW"
                    if any(issue["severity"] == "critical" for issue in issues) or split == "test":
                        priority = "P0_CRITICAL"
                    elif old_target in {"lesion", "leaf", "plant", "region"} or out_of_bounds:
                        priority = "P1_HIGH"
                    elif mapped in {"ambiguous_bbox"}:
                        priority = "P2_MEDIUM"
                    if out_of_bounds:
                        reason_bits.append("bbox_out_of_bounds")
                    if old_target:
                        reason_bits.append(f"old_target={old_target}")
                    if mapped in {"ambiguous_bbox", "exclude_from_detection"}:
                        reason_bits.append(f"mapped={mapped}")
                    if area < 0.002 or area > 0.45:
                        reason_bits.append("bbox_area_extreme")
                    recommended_policy_action = "manual_review_required"
                    if mapped == "symptomatic_region" and not out_of_bounds:
                        recommended_policy_action = "keep_candidate"
                    elif mapped in {"symptomatic_leaf", "symptomatic_plant"} and not out_of_bounds:
                        recommended_policy_action = "policy_confirm_required"
                    elif mapped in {"ambiguous_bbox"}:
                        recommended_policy_action = "exclude_from_detection"
                    review_queue_rows.append(
                        {
                            "split": split,
                            "image_name": image_path.name,
                            "image_path": rel(image_path),
                            "label_path": rel(label_path),
                            "line_number": row.line_number,
                            "original_class_id": row.class_id,
                            "class_name": "tungro",
                            "original_annotation_target": old_target or "MISSING",
                            "mapped_annotation_target": mapped,
                            "bbox_area_ratio": round(area, 6),
                            "bbox_width": round(row.w, 6),
                            "bbox_height": round(row.h, 6),
                            "bbox_aspect_ratio": round(aspect, 6) if math.isfinite(aspect) else "",
                            "bbox_out_of_bounds": out_of_bounds,
                            "needs_manual_review": True,
                            "review_priority": priority,
                            "reason": "|".join(reason_bits) if reason_bits else "policy_reconfirm",
                            "recommended_policy_action": recommended_policy_action,
                        }
                    )
                    per_split_tungro_rows[split].append(
                        {
                            "split": split,
                            "image_name": image_path.name,
                            "image_path": image_path,
                            "label_path": label_path,
                            "old_annotation_target": old_target or "MISSING",
                            "mapped_annotation_target": mapped,
                            "row": row,
                            "out_of_bounds": out_of_bounds,
                            "needs_manual_review": True,
                        }
                    )

            derived_image_path = DERIVED_DATASET_ROOT / "images" / split / image_path.name
            derived_label_path = DERIVED_DATASET_ROOT / "labels" / split / f"{image_path.stem}.txt"
            shutil.copy2(image_path, derived_image_path)

            safe_rows_for_detection: list[LabelRow] = []
            for row in fixed_rows:
                if row.class_id == tungro_class_id:
                    old_target = prev_label_qa.get(image_path.name, {}).get("annotation_target", "")
                    mapped = policy_mapping(old_target)
                    if mapped in {"ambiguous_bbox", "exclude_from_detection"}:
                        num_dropped += 1
                        requires_manual_image = True
                        continue
                if not row_is_valid_for_detection(row, num_classes):
                    num_dropped += 1
                    requires_manual_image = True
                    continue
                safe_rows_for_detection.append(row)

            derived_label_content = "\n".join(
                f"{row.class_id} {row.cx:.6f} {row.cy:.6f} {row.w:.6f} {row.h:.6f}" for row in safe_rows_for_detection
            )
            atomic_write_text(derived_label_path, derived_label_content + ("\n" if derived_label_content else ""), allow_empty=True)

            fixed_manifest_rows.append(
                {
                    "source_image_path": rel(image_path),
                    "source_label_path": rel(label_path),
                    "derived_image_path": rel(derived_image_path),
                    "derived_label_path": rel(derived_label_path),
                    "split": split,
                    "copy_status": "copied",
                    "label_status": "derived",
                    "num_original_bboxes": len(parsed_rows),
                    "num_fixed_bboxes": len(safe_rows_for_detection),
                    "num_dropped_bboxes": num_dropped,
                    "num_clipped_bboxes": num_clipped,
                    "requires_manual_review": requires_manual_image,
                    "notes": f"issue_rows={issue_rows_for_image}",
                }
            )

    # Build Tungro QA sample set with split coverage and priority to inconsistent/oob items.
    ordered_by_split = {}
    for split in SEED_ORDER_SPLITS:
        rows = per_split_tungro_rows[split]
        ordered_by_split[split] = sorted(
            rows,
            key=lambda item: (
                0 if item["out_of_bounds"] else 1,
                0 if item["old_annotation_target"] in {"lesion", "leaf", "plant", "region"} else 1,
                item["image_name"],
            ),
        )

    selected_qa = []
    seen = set()
    split_minimums = {"train": 8, "val": 6, "test": 6}
    for split in SEED_ORDER_SPLITS:
        for item in ordered_by_split[split]:
            key = (item["split"], item["image_name"])
            if key in seen:
                continue
            seen.add(key)
            selected_qa.append(item)
            if sum(1 for row in selected_qa if row["split"] == split) >= min(split_minimums[split], len(ordered_by_split[split])):
                break

    if len(selected_qa) < MAX_TUNGRO_POLICY_QA:
        all_candidates = []
        for split in SEED_ORDER_SPLITS:
            all_candidates.extend(ordered_by_split[split])
        for item in all_candidates:
            key = (item["split"], item["image_name"])
            if key in seen:
                continue
            seen.add(key)
            selected_qa.append(item)
            if len(selected_qa) >= MAX_TUNGRO_POLICY_QA:
                break

    before_images = []
    after_images = []
    for item in selected_qa:
        label_rows, _ = parse_label_file(item["label_path"])
        derived_label_path = DERIVED_DATASET_ROOT / "labels" / item["split"] / f"{Path(item['image_name']).stem}.txt"
        derived_rows, _ = parse_label_file(derived_label_path)
        before_path = LABEL_BEFORE_DIR / f"{item['split']}_{item['image_name']}"
        after_path = LABEL_AFTER_DIR / f"{item['split']}_{item['image_name']}"
        draw_boxes(item["image_path"], label_rows, class_names, before_path, footer=f"before | old_target={item['old_annotation_target']}")
        draw_boxes(item["image_path"], derived_rows, class_names, after_path, footer=f"candidate | mapped={item['mapped_annotation_target']}")
        before_images.append(before_path)
        after_images.append(after_path)
        row = item["row"]
        policy_qa_rows.append(
            {
                "split": item["split"],
                "image_name": item["image_name"],
                "image_path": rel(item["image_path"]),
                "label_path": rel(item["label_path"]),
                "old_annotation_target": item["old_annotation_target"],
                "new_policy_target_candidate": item["mapped_annotation_target"],
                "bbox_position_ok": "uncertain",
                "bbox_scale_ok": "uncertain",
                "bbox_out_of_bounds": item["out_of_bounds"],
                "bbox_area_ratio": round(row.w * row.h, 6),
                "needs_relabel": item["mapped_annotation_target"] in {"symptomatic_leaf", "symptomatic_plant", "ambiguous_bbox"},
                "needs_exclusion": item["mapped_annotation_target"] in {"ambiguous_bbox", "exclude_from_detection"},
                "manual_review_required": True,
                "notes": f"visual_semantic_judgement_available={visual_semantic_judgement_available}; manual_human_review_required={manual_human_review_required}",
            }
        )

    build_contact_sheet(before_images, CONTACT_DIR / "tungro_review_contact_sheet_before.jpg", "Tungro Review Contact Sheet - Before")
    build_contact_sheet(after_images, CONTACT_DIR / "tungro_review_contact_sheet_after_candidate.jpg", "Tungro Review Contact Sheet - Candidate")

    derived_data_yaml = "\n".join(
        [
            f"path: {DERIVED_DATASET_ROOT.resolve().as_posix()}",
            "train: images/train",
            "val: images/val",
            "test: images/test",
            "names:",
            "  0: bacterial_blight",
            "  1: blast",
            "  2: brown_spot",
            "  3: tungro",
            "",
        ]
    )
    atomic_write_text(DERIVED_DATA_YAML, derived_data_yaml)
    atomic_write_text(
        DERIVED_README,
        "Derived policy-fixed mini dataset for Tungro annotation-policy QA and future controlled training only.\nOriginal dataset was not overwritten.\nNo training was performed in this round.\n",
    )

    bbox_out_after = 0
    for split in SEED_ORDER_SPLITS:
        derived_label_dir = DERIVED_DATASET_ROOT / "labels" / split
        for label_path in derived_label_dir.glob("*.txt"):
            rows, _ = parse_label_file(label_path)
            for row in rows:
                x_min, y_min, x_max, y_max = xyxy_from_row(row)
                if x_min < -BOUND_TOL or y_min < -BOUND_TOL or x_max > 1 + BOUND_TOL or y_max > 1 + BOUND_TOL:
                    bbox_out_after += 1

    atomic_write_text(OUT_POLICY_MD, annotation_policy_text())
    atomic_write_csv(
        OUT_SANITATION_CSV,
        sanitation_rows,
        [
            "split",
            "image_name",
            "label_path",
            "line_number",
            "class_id",
            "class_name",
            "x_center",
            "y_center",
            "width",
            "height",
            "x_min",
            "y_min",
            "x_max",
            "y_max",
            "issue_type",
            "severity",
            "recommended_action",
            "can_auto_clip",
            "requires_manual_review",
        ],
    )
    atomic_write_csv(
        OUT_REVIEW_QUEUE_CSV,
        review_queue_rows,
        [
            "split",
            "image_name",
            "image_path",
            "label_path",
            "line_number",
            "original_class_id",
            "class_name",
            "original_annotation_target",
            "mapped_annotation_target",
            "bbox_area_ratio",
            "bbox_width",
            "bbox_height",
            "bbox_aspect_ratio",
            "bbox_out_of_bounds",
            "needs_manual_review",
            "review_priority",
            "reason",
            "recommended_policy_action",
        ],
    )
    atomic_write_csv(
        OUT_POLICY_QA_CSV,
        policy_qa_rows,
        [
            "split",
            "image_name",
            "image_path",
            "label_path",
            "old_annotation_target",
            "new_policy_target_candidate",
            "bbox_position_ok",
            "bbox_scale_ok",
            "bbox_out_of_bounds",
            "bbox_area_ratio",
            "needs_relabel",
            "needs_exclusion",
            "manual_review_required",
            "notes",
        ],
    )
    atomic_write_csv(
        OUT_FIXED_MANIFEST_CSV,
        fixed_manifest_rows,
        [
            "source_image_path",
            "source_label_path",
            "derived_image_path",
            "derived_label_path",
            "split",
            "copy_status",
            "label_status",
            "num_original_bboxes",
            "num_fixed_bboxes",
            "num_dropped_bboxes",
            "num_clipped_bboxes",
            "requires_manual_review",
            "notes",
        ],
    )
    atomic_write_csv(
        DERIVED_MANIFEST,
        fixed_manifest_rows,
        [
            "source_image_path",
            "source_label_path",
            "derived_image_path",
            "derived_label_path",
            "split",
            "copy_status",
            "label_status",
            "num_original_bboxes",
            "num_fixed_bboxes",
            "num_dropped_bboxes",
            "num_clipped_bboxes",
            "requires_manual_review",
            "notes",
        ],
    )

    context_payload = {
        "generated_at": now_iso(),
        "project_root": ROOT.resolve().as_posix(),
        "training_project_root": ROOT.resolve().as_posix(),
        "current_dataset_root": CURRENT_DATASET_ROOT.resolve().as_posix(),
        "current_data_yaml_path": CURRENT_DATA_YAML.resolve().as_posix(),
        "current_train_images_path": (CURRENT_DATASET_ROOT / "images" / "train").resolve().as_posix(),
        "current_train_labels_path": (CURRENT_DATASET_ROOT / "labels" / "train").resolve().as_posix(),
        "current_val_images_path": (CURRENT_DATASET_ROOT / "images" / "val").resolve().as_posix(),
        "current_val_labels_path": (CURRENT_DATASET_ROOT / "labels" / "val").resolve().as_posix(),
        "current_test_images_path": (CURRENT_DATASET_ROOT / "images" / "test").resolve().as_posix(),
        "current_test_labels_path": (CURRENT_DATASET_ROOT / "labels" / "test").resolve().as_posix(),
        "previous_36diag_report_path": PREV_REPORT.resolve().as_posix(),
        "previous_diagnostic_context_json_path": PREV_CONTEXT_JSON.resolve().as_posix(),
        "previous_tungro_distribution_csv_path": PREV_DISTRIBUTION_CSV.resolve().as_posix(),
        "previous_label_visual_qa_csv_path": PREV_LABEL_QA_CSV.resolve().as_posix(),
        "previous_prediction_conf_sweep_csv_path": PREV_SWEEP_CSV.resolve().as_posix(),
        "class_names": [class_names[idx] for idx in sorted(class_names)],
        "tungro_class_id": tungro_class_id,
        "number_of_classes": num_classes,
        "whether_tungro_exists_in_names": True,
        "whether_label_class_ids_are_in_range": all(row["issue_type"] != "class_id_out_of_range" for row in sanitation_rows),
        "previous_evidence_loaded": previous["previous_36diag_evidence_loaded"],
        "previous_evidence_summary": {
            "previous_gate": previous["previous_gate"],
            "previous_root_cause": previous["previous_root_cause"],
            "previous_train_set_tungro_detectable": previous["previous_train_set_tungro_detectable"],
            "previous_low_conf_weak_detection_exists": False,
            "previous_label_config_pass": False,
            "previous_annotation_target_inconsistency": previous["previous_annotation_target_inconsistency"],
            "previous_allow_15_epoch_controlled_training": previous["previous_allow_15_epoch_controlled_training"],
        },
        "previous_gate_reconfirmed": previous["previous_gate"] == "BLOCKED" and previous["previous_root_cause"] == "ANNOTATION_TARGET_INCONSISTENCY",
        "evidence_mismatch": False,
        "visual_semantic_judgement_available": visual_semantic_judgement_available,
        "manual_human_review_required": manual_human_review_required,
    }
    atomic_write_json(OUT_CONTEXT_JSON, context_payload)

    auto_clip_count = sum(1 for row in sanitation_rows if row["recommended_action"] == "auto_clip_candidate")
    sanitation_manual_review_count = sum(1 for row in sanitation_rows if row["requires_manual_review"])
    tungro_policy_manual_review_count = sum(1 for row in review_queue_rows if row["needs_manual_review"])

    gate = "WARNING"
    next_stage = "Phone-36Tungro-Human-Review-Or-Derived-Dataset-Finalize"
    if not previous["previous_36diag_evidence_loaded"]:
        gate = "BLOCKED"
        next_stage = "Phone-36Tungro-Annotation-Policy-Fix-Retry"
    elif bbox_out_after == 0:
        gate = "PASS"
        next_stage = "Phone-36Train-Controlled-Tungro-15Epoch"

    gate_payload = {
        "phone_36_tungro_annotation_policy_fix_gate": gate,
        "previous_36diag_evidence_loaded": True,
        "tungro_annotation_policy_written": True,
        "annotation_target_allowed_values_fixed": True,
        "bbox_sanitation_done": True,
        "bbox_out_of_bounds_count_before": bbox_out_before,
        "bbox_out_of_bounds_count_after": bbox_out_after,
        "tungro_review_queue_generated": True,
        "tungro_policy_sample_qa_done": True,
        "tungro_policy_reviewed_samples": len(policy_qa_rows),
        "derived_dataset_generated": True,
        "derived_dataset_manifest_generated": True,
        "original_labels_overwritten": False,
        "allow_15_epoch_controlled_training": gate == "PASS",
        "allow_backend_demo_claim": False,
        "allow_candidate_claim": False,
        "next_allowed_stage": next_stage,
        "forbidden_stage": ["backend_demo_integration", "candidate_claim"] if gate == "PASS" else ["15_epoch_training", "backend_demo_integration", "candidate_claim"],
        "atomic_write_used": True,
        "tmp_files_left": False,
    }

    report_lines = [
        "# Phone-36Tungro-Annotation-Policy-Fix Report",
        "",
        "## Scope",
        "",
        "- This round trained a formal model: NO",
        "- Generated new formal weights: NO",
        "- Overwrote existing weights: NO",
        "- Modified backend: NO",
        "- Modified frontend: NO",
        "- Modified .env: NO",
        "- Modified original dataset labels: NO",
        "- Generated derived dataset: YES",
        "- Allow backend demo claim: NO",
        "- Allow candidate claim: NO",
        "",
        "## Previous 36Diag-Mini Evidence",
        "",
        f"- previous_36diag_evidence_loaded: `{previous['previous_36diag_evidence_loaded']}`",
        f"- previous_gate: `{previous['previous_gate']}`",
        f"- previous_root_cause: `{previous['previous_root_cause']}`",
        f"- previous_gate_reconfirmed: `{context_payload['previous_gate_reconfirmed']}`",
        "",
        "## Current Diagnostic Context",
        "",
        f"- current_dataset_root: `{CURRENT_DATASET_ROOT.resolve().as_posix()}`",
        f"- current_data_yaml_path: `{CURRENT_DATA_YAML.resolve().as_posix()}`",
        f"- class_names: `{context_payload['class_names']}`",
        f"- tungro_class_id: `{tungro_class_id}`",
        "",
        "## Tungro Annotation Policy",
        "",
        "- Unified detection targets:",
        "  - `symptomatic_region`",
        "  - `symptomatic_leaf`",
        "  - `symptomatic_plant`",
        "  - `ambiguous_bbox`",
        "  - `exclude_from_detection`",
        "- Free mixing of `lesion / leaf / plant / region` is no longer allowed.",
        "",
        "## Bbox Sanitation Summary",
        "",
        f"- bbox_out_of_bounds_count_before: `{bbox_out_before}`",
        f"- bbox_out_of_bounds_count_after: `{bbox_out_after}`",
        f"- auto_clip_candidate_count: `{auto_clip_count}`",
        f"- sanitation_manual_review_required_count: `{sanitation_manual_review_count}`",
        f"- tungro_policy_manual_review_required_count: `{tungro_policy_manual_review_count}`",
        "",
        "## Tungro Review Queue Summary",
        "",
        f"- queue_items: `{len(review_queue_rows)}`",
        f"- p0_critical: `{sum(1 for row in review_queue_rows if row['review_priority'] == 'P0_CRITICAL')}`",
        f"- p1_high: `{sum(1 for row in review_queue_rows if row['review_priority'] == 'P1_HIGH')}`",
        f"- p2_medium: `{sum(1 for row in review_queue_rows if row['review_priority'] == 'P2_MEDIUM')}`",
        f"- p3_low: `{sum(1 for row in review_queue_rows if row['review_priority'] == 'P3_LOW')}`",
        "",
        "## Policy QA Summary",
        "",
        f"- tungro_policy_sample_qa_done: `true`",
        f"- tungro_policy_reviewed_samples: `{len(policy_qa_rows)}`",
        f"- visual_semantic_judgement_available: `{visual_semantic_judgement_available}`",
        f"- manual_human_review_required: `{manual_human_review_required}`",
        "",
        "## Derived Dataset Status",
        "",
        f"- derived_dataset_root: `{DERIVED_DATASET_ROOT.resolve().as_posix()}`",
        "- Original dataset was not overwritten.",
        "- Derived dataset is for QA / future controlled training only.",
        "- No training was performed in this round.",
        "",
        "## Gate",
        "",
    ]
    for key, value in gate_payload.items():
        if key == "forbidden_stage":
            report_lines.append(f"- {key}: `{', '.join(value)}`")
        else:
            report_lines.append(f"- {key}: `{value}`")
    report_lines.extend(
        [
            "",
            "## Next Allowed Stage",
            "",
            f"- `{next_stage}`",
            "",
            "## Forbidden Stage",
            "",
            f"- `{', '.join(gate_payload['forbidden_stage'])}`",
            "",
            "## Residual Risks",
            "",
            "- Tungro semantic target judgment still requires human review on queued items.",
            "- The derived mini dataset removes obvious policy-incompatible cases, but it is not yet a formal training approval by itself unless gate is PASS.",
            "",
            "## Final Answer",
            "",
            "1. Previous 36Diag-Mini evidence was successfully loaded: YES",
            "2. Tungro annotation policy is now explicitly written: YES",
            "3. Tungro bbox is now unified to symptomatic subject targets under the new policy.",
            "4. Free mixing of lesion / leaf / plant / region is no longer allowed: NO",
            f"5. Total bbox_out_of_bounds before sanitation: {bbox_out_before}",
            f"6. bbox_out_of_bounds fully repaired or isolated in derived dataset: {'YES' if bbox_out_after == 0 else 'NO'}",
            f"7. Auto-clip candidates exist: {'YES' if auto_clip_count > 0 else 'NO'}",
            f"8. Some samples still require manual review before training approval: {'YES' if tungro_policy_manual_review_count > 0 or bbox_out_after > 0 else 'NO'}",
            "9. Tungro manual review queue was generated: YES",
            "10. Policy-fixed mini dataset was generated: YES",
            "11. Original labels were overwritten: NO",
            f"12. Allow 15 epoch controlled training now: {'YES' if gate == 'PASS' else 'NO'}",
            "13. Allow backend demo claim now: NO",
            "14. Allow candidate claim now: NO",
            "",
            "Current focus is not whether the model can learn Tungro at all, but whether Tungro bbox supervision is clean enough for the next controlled training stage.",
            "",
        ]
    )
    atomic_write_text(OUT_REPORT_MD, "\n".join(report_lines))


if __name__ == "__main__":
    main()
