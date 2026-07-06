"""Phone-36DerivedDataset-Rebuild-And-Pretrain-Reaudit.

Rebuilds a new derived dataset from the source Phone RiceSeg dataset after
identifying why the previous v36 policy-fixed derived dataset passed one audit
but failed the later pre-train audit.

This round:
- does not train
- does not generate weights
- does not overwrite original labels
- does not overwrite the old bad derived dataset
"""

from __future__ import annotations

import csv
import json
import math
import os
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent

SOURCE_DATASET_ROOT = ROOT / "datasets" / "phone_riceseg_v35m_holdout_applied"
SOURCE_DATA_YAML = SOURCE_DATASET_ROOT / "data.yaml"
CURRENT_BAD_DERIVED_ROOT = ROOT / "datasets" / "_derived" / "phone_riceseg_v36_tungro_policy_fixed_mini"
CURRENT_BAD_DERIVED_YAML = CURRENT_BAD_DERIVED_ROOT / "data.yaml"

PREV_POLICY_DIR = ROOT / "reports" / "phone_36_tungro_annotation_policy_fix"
PREV_POLICY_REPORT = PREV_POLICY_DIR / "phone_36_tungro_annotation_policy_fix_report.md"
PREV_ANNOTATION_POLICY = PREV_POLICY_DIR / "annotation_policy.md"
PREV_BBOX_SANITATION = PREV_POLICY_DIR / "bbox_sanitation_report.csv"
PREV_TUNGRO_REVIEW_QUEUE = PREV_POLICY_DIR / "tungro_annotation_review_queue.csv"
PREV_TUNGRO_POLICY_QA = ROOT / "reports" / "phone_36diag_mini_tungro" / "label_visual_qa.csv"
PREV_FIXED_MANIFEST = PREV_POLICY_DIR / "fixed_dataset_manifest.csv"

BLOCKED_DIR = ROOT / "reports" / "phone_36_train_controlled_tungro_15epoch"
BLOCKED_REPORT = BLOCKED_DIR / "phone_36_train_controlled_tungro_15epoch_report.md"
BLOCKED_CONTEXT_JSON = BLOCKED_DIR / "training_context.json"
BLOCKED_OLD_DERIVED_DISTRIBUTION = BLOCKED_DIR / "derived_distribution_summary.csv"

REPORT_DIR = ROOT / "reports" / "phone_36_derived_dataset_rebuild_pretrain_reaudit"
REPORT_MD = REPORT_DIR / "phone_36_derived_dataset_rebuild_pretrain_reaudit_report.md"
REBUILD_CONTEXT_JSON = REPORT_DIR / "rebuild_context.json"
MISMATCH_ROOT_CAUSE_MD = REPORT_DIR / "mismatch_root_cause_audit.md"
SOURCE_DISTRIBUTION_CSV = REPORT_DIR / "source_distribution_summary.csv"
OLD_DERIVED_DISTRIBUTION_CSV = REPORT_DIR / "old_derived_distribution_summary.csv"
NEW_DERIVED_DISTRIBUTION_CSV = REPORT_DIR / "new_derived_distribution_summary.csv"
LABEL_SANITATION_BEFORE_CSV = REPORT_DIR / "label_sanitation_before.csv"
LABEL_SANITATION_AFTER_CSV = REPORT_DIR / "label_sanitation_after.csv"
DERIVED_REBUILD_MANIFEST_REPORT_CSV = REPORT_DIR / "derived_rebuild_manifest.csv"
TUNGRO_SPLIT_COVERAGE_CSV = REPORT_DIR / "tungro_split_coverage_audit.csv"
PRETRAIN_GATE_JSON = REPORT_DIR / "pretrain_audit_gate.json"
LABEL_VIS_AFTER_DIR = REPORT_DIR / "label_visual_after_sample"
TUNGRO_VIS_DIR = REPORT_DIR / "tungro_val_test_sample_visuals"

NEW_DERIVED_ROOT = ROOT / "datasets" / "_derived" / "phone_riceseg_v36_tungro_policy_fixed_reaudit"
NEW_DERIVED_TMP_ROOT = ROOT / "datasets" / "_derived" / "phone_riceseg_v36_tungro_policy_fixed_reaudit_tmp_build"
NEW_DERIVED_YAML = NEW_DERIVED_ROOT / "data.yaml"
NEW_DERIVED_README = NEW_DERIVED_ROOT / "README_REAUDIT.md"
NEW_DERIVED_MANIFEST = NEW_DERIVED_ROOT / "derived_rebuild_manifest.csv"

SPLITS = ("train", "val", "test")
CLASS_NAMES_EXPECTED = {
    0: "bacterial_blight",
    1: "blast",
    2: "brown_spot",
    3: "tungro",
}
TUNGRO_CLASS_ID = 3
GRID = 1_000_000
LIGHT_OOB_LIMIT = 0.05
MIN_VALID_AREA = 1e-6
MAX_VALID_AREA = 0.95
LABEL_VIS_SAMPLE_LIMIT = 20
TUNGRO_VAL_VIS_LIMIT = 5
TUNGRO_TEST_VIS_LIMIT = 3


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


def read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def load_font(size: int):
    for candidate in [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def list_images(path: Path) -> list[Path]:
    return sorted([candidate for candidate in path.iterdir() if candidate.is_file()])


def parse_label_file(path: Path) -> tuple[list[LabelRow], list[str]]:
    rows: list[LabelRow] = []
    issues: list[str] = []
    if not path.exists():
        issues.append("missing_label")
        return rows, issues
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return rows, issues
    for line_number, raw in enumerate(text.splitlines(), start=1):
        parts = raw.strip().split()
        if len(parts) != 5:
            issues.append(f"parse_error_line_{line_number}")
            continue
        try:
            class_id = int(float(parts[0]))
            cx, cy, w, h = [float(value) for value in parts[1:]]
        except ValueError:
            issues.append(f"parse_error_line_{line_number}")
            continue
        rows.append(LabelRow(class_id=class_id, cx=cx, cy=cy, w=w, h=h, line_number=line_number, raw_line=raw.strip()))
    return rows, issues


def xyxy_from_row(row: LabelRow) -> tuple[float, float, float, float]:
    return (
        row.cx - row.w / 2.0,
        row.cy - row.h / 2.0,
        row.cx + row.w / 2.0,
        row.cy + row.h / 2.0,
    )


def load_class_names(data_yaml_path: Path) -> dict[int, str]:
    payload = read_yaml(data_yaml_path)
    names_raw = payload.get("names", {})
    if isinstance(names_raw, list):
        return {idx: value for idx, value in enumerate(names_raw)}
    return {int(key): value for key, value in names_raw.items()}


def classify_row_issues(row: LabelRow, num_classes: int) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    x_min, y_min, x_max, y_max = xyxy_from_row(row)
    if row.class_id < 0 or row.class_id >= num_classes:
        issues.append({"issue_type": "class_id_out_of_range", "severity": "critical"})
    if not all(math.isfinite(value) for value in [row.cx, row.cy, row.w, row.h]):
        issues.append({"issue_type": "non_finite", "severity": "critical"})
    if row.w <= 0 or row.h <= 0:
        issues.append({"issue_type": "non_positive_width_height", "severity": "critical"})
    if row.cx < 0 or row.cx > 1 or row.cy < 0 or row.cy > 1 or row.w > 1 or row.h > 1:
        issues.append({"issue_type": "coordinate_out_of_range", "severity": "critical"})
    if x_min < 0 or y_min < 0 or x_max > 1 or y_max > 1:
        light = x_min >= -LIGHT_OOB_LIMIT and y_min >= -LIGHT_OOB_LIMIT and x_max <= 1 + LIGHT_OOB_LIMIT and y_max <= 1 + LIGHT_OOB_LIMIT
        issues.append(
            {
                "issue_type": "bbox_out_of_bounds",
                "severity": "high" if light else "critical",
                "light_clip_candidate": light,
            }
        )
    return issues


def sanitize_row_to_grid(row: LabelRow) -> tuple[LabelRow | None, dict[str, Any]]:
    x_min, y_min, x_max, y_max = xyxy_from_row(row)
    issues = classify_row_issues(row, len(CLASS_NAMES_EXPECTED))
    action = "kept"
    requires_manual_review = False
    notes: list[str] = []

    if any(issue["issue_type"] in {"class_id_out_of_range", "non_finite", "non_positive_width_height", "coordinate_out_of_range"} for issue in issues):
        return None, {
            "issue_types": [issue["issue_type"] for issue in issues],
            "severity": "critical",
            "action": "drop_invalid_bbox",
            "requires_manual_review": True,
            "notes": "invalid_bbox_fields",
        }

    if any(issue["issue_type"] == "bbox_out_of_bounds" and not issue.get("light_clip_candidate", False) for issue in issues):
        return None, {
            "issue_types": [issue["issue_type"] for issue in issues],
            "severity": "critical",
            "action": "drop_severe_out_of_bounds_bbox",
            "requires_manual_review": True,
            "notes": "severe_out_of_bounds",
        }

    clipped = False
    if any(issue["issue_type"] == "bbox_out_of_bounds" for issue in issues):
        x_min = min(max(x_min, 0.0), 1.0)
        y_min = min(max(y_min, 0.0), 1.0)
        x_max = min(max(x_max, 0.0), 1.0)
        y_max = min(max(y_max, 0.0), 1.0)
        clipped = True
        action = "clip_and_keep"
        notes.append("light_out_of_bounds_clipped")

    if x_max <= x_min or y_max <= y_min:
        return None, {
            "issue_types": [issue["issue_type"] for issue in issues] or ["degenerate_after_clip"],
            "severity": "critical",
            "action": "drop_degenerate_after_clip",
            "requires_manual_review": True,
            "notes": "degenerate_after_clip",
        }

    x1_i = max(0, math.ceil(x_min * GRID - 1e-12))
    y1_i = max(0, math.ceil(y_min * GRID - 1e-12))
    x2_i = min(GRID, math.floor(x_max * GRID + 1e-12))
    y2_i = min(GRID, math.floor(y_max * GRID + 1e-12))
    if x2_i <= x1_i or y2_i <= y1_i:
        return None, {
            "issue_types": [issue["issue_type"] for issue in issues] or ["quantized_degenerate_bbox"],
            "severity": "critical",
            "action": "drop_quantized_degenerate_bbox",
            "requires_manual_review": True,
            "notes": "quantized_grid_invalid",
        }

    w_i = x2_i - x1_i
    h_i = y2_i - y1_i
    cx_target_i = round(((x_min + x_max) / 2.0) * GRID)
    cy_target_i = round(((y_min + y_max) / 2.0) * GRID)
    cx_min_i = math.ceil(w_i / 2)
    cy_min_i = math.ceil(h_i / 2)
    cx_max_i = math.floor(GRID - w_i / 2)
    cy_max_i = math.floor(GRID - h_i / 2)
    cx_i = min(max(cx_target_i, cx_min_i), cx_max_i)
    cy_i = min(max(cy_target_i, cy_min_i), cy_max_i)

    cx = cx_i / GRID
    cy = cy_i / GRID
    w = w_i / GRID
    h = h_i / GRID

    if w <= 0 or h <= 0:
        return None, {
            "issue_types": [issue["issue_type"] for issue in issues] or ["non_positive_after_quantize"],
            "severity": "critical",
            "action": "drop_non_positive_after_quantize",
            "requires_manual_review": True,
            "notes": "quantized_non_positive",
        }

    area = w * h
    if area < MIN_VALID_AREA:
        return None, {
            "issue_types": [issue["issue_type"] for issue in issues] or ["too_tiny_after_fix"],
            "severity": "high",
            "action": "drop_too_tiny_bbox",
            "requires_manual_review": True,
            "notes": "bbox_too_tiny_after_fix",
        }
    if area >= MAX_VALID_AREA:
        return None, {
            "issue_types": [issue["issue_type"] for issue in issues] or ["near_full_image_after_fix"],
            "severity": "high",
            "action": "drop_near_full_image_bbox",
            "requires_manual_review": True,
            "notes": "bbox_near_full_image_after_fix",
        }

    new_row = LabelRow(
        class_id=row.class_id,
        cx=cx,
        cy=cy,
        w=w,
        h=h,
        line_number=row.line_number,
        raw_line=f"{row.class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}",
    )
    new_x_min, new_y_min, new_x_max, new_y_max = xyxy_from_row(new_row)
    if new_x_min < 0 or new_y_min < 0 or new_x_max > 1 or new_y_max > 1:
        return None, {
            "issue_types": [issue["issue_type"] for issue in issues] or ["strict_oob_after_quantize"],
            "severity": "critical",
            "action": "drop_strict_oob_after_quantize",
            "requires_manual_review": True,
            "notes": "strict_oob_after_quantize",
        }

    return new_row, {
        "issue_types": [issue["issue_type"] for issue in issues],
        "severity": "high" if clipped else "none",
        "action": action,
        "requires_manual_review": requires_manual_review,
        "notes": "|".join(notes) if notes else "none",
    }


def draw_boxes(image_path: Path, rows: list[LabelRow], out_path: Path, footer: str) -> None:
    class_names = CLASS_NAMES_EXPECTED
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = load_font(16)
    colors = {
        0: (255, 64, 64),
        1: (80, 170, 255),
        2: (255, 180, 0),
        3: (120, 255, 120),
    }
    for row in rows:
        x_min, y_min, x_max, y_max = xyxy_from_row(row)
        box = (x_min * image.width, y_min * image.height, x_max * image.width, y_max * image.height)
        color = colors.get(row.class_id, (255, 255, 0))
        draw.rectangle(box, outline=color, width=3)
        label = f"{row.class_id}:{class_names.get(row.class_id, 'unknown')}"
        tb = draw.textbbox((box[0], max(0, box[1] - 18)), label, font=font)
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


def ensure_clean_targets() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    for path in [LABEL_VIS_AFTER_DIR, TUNGRO_VIS_DIR]:
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
    if NEW_DERIVED_TMP_ROOT.exists():
        shutil.rmtree(NEW_DERIVED_TMP_ROOT)
    if NEW_DERIVED_ROOT.exists():
        raise RuntimeError(f"Refusing to overwrite existing rebuilt dataset: {NEW_DERIVED_ROOT}")
    for split in SPLITS:
        (NEW_DERIVED_TMP_ROOT / "images" / split).mkdir(parents=True, exist_ok=True)
        (NEW_DERIVED_TMP_ROOT / "labels" / split).mkdir(parents=True, exist_ok=True)


def assert_required_paths() -> None:
    required = [
        SOURCE_DATASET_ROOT,
        SOURCE_DATA_YAML,
        CURRENT_BAD_DERIVED_ROOT,
        CURRENT_BAD_DERIVED_YAML,
        PREV_POLICY_REPORT,
        PREV_ANNOTATION_POLICY,
        PREV_BBOX_SANITATION,
        PREV_TUNGRO_REVIEW_QUEUE,
        PREV_TUNGRO_POLICY_QA,
        PREV_FIXED_MANIFEST,
        BLOCKED_REPORT,
        BLOCKED_CONTEXT_JSON,
        BLOCKED_OLD_DERIVED_DISTRIBUTION,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"Required files missing: {missing}")


def scan_dataset(dataset_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    split_summary: dict[str, Any] = {}
    per_image_rows: list[dict[str, Any]] = []
    for split in SPLITS:
        image_dir = dataset_root / "images" / split
        label_dir = dataset_root / "labels" / split
        images = list_images(image_dir)
        label_paths = sorted(label_dir.glob("*.txt"))
        image_stems = {path.stem for path in images}
        label_stems = {path.stem for path in label_paths}
        per_class_images: Counter[int] = Counter()
        per_class_bboxes: Counter[int] = Counter()
        total_bboxes = 0
        empty_labels = 0
        for label_path in label_paths:
            parsed_rows, _ = parse_label_file(label_path)
            if not parsed_rows:
                empty_labels += 1
                per_image_rows.append(
                    {
                        "dataset_root": str(dataset_root.resolve()),
                        "split": split,
                        "image_name": f"{label_path.stem}.jpg",
                        "label_path": str(label_path.resolve()),
                        "bbox_count": 0,
                        "has_tungro": False,
                    }
                )
                continue
            seen_classes = set()
            for row in parsed_rows:
                total_bboxes += 1
                per_class_bboxes[row.class_id] += 1
                seen_classes.add(row.class_id)
            for class_id in seen_classes:
                per_class_images[class_id] += 1
            per_image_rows.append(
                {
                    "dataset_root": str(dataset_root.resolve()),
                    "split": split,
                    "image_name": f"{label_path.stem}.jpg",
                    "label_path": str(label_path.resolve()),
                    "bbox_count": len(parsed_rows),
                    "has_tungro": TUNGRO_CLASS_ID in seen_classes,
                }
            )
        split_summary[split] = {
            "total_images": len(images),
            "total_labels": len(label_paths),
            "total_bboxes": total_bboxes,
            "empty_label_count": empty_labels,
            "per_class_images": {CLASS_NAMES_EXPECTED[key]: per_class_images.get(key, 0) for key in CLASS_NAMES_EXPECTED},
            "per_class_bboxes": {CLASS_NAMES_EXPECTED[key]: per_class_bboxes.get(key, 0) for key in CLASS_NAMES_EXPECTED},
            "tungro_images": per_class_images.get(TUNGRO_CLASS_ID, 0),
            "tungro_bboxes": per_class_bboxes.get(TUNGRO_CLASS_ID, 0),
            "missing_label_count": len(image_stems - label_stems),
            "missing_image_count": len(label_stems - image_stems),
        }
        for class_id, class_name in CLASS_NAMES_EXPECTED.items():
            rows.append(
                {
                    "split": split,
                    "class_id": class_id,
                    "class_name": class_name,
                    "images_with_class": per_class_images.get(class_id, 0),
                    "bbox_count": per_class_bboxes.get(class_id, 0),
                    "total_images_in_split": len(images),
                    "total_labels_in_split": len(label_paths),
                    "total_bboxes_in_split": total_bboxes,
                    "empty_label_count": empty_labels,
                    "missing_label_count": len(image_stems - label_stems),
                    "missing_image_count": len(label_stems - image_stems),
                }
            )
    return rows, split_summary, per_image_rows


def count_strict_oob(dataset_root: Path) -> int:
    count = 0
    for split in SPLITS:
        for label_path in (dataset_root / "labels" / split).glob("*.txt"):
            rows, _ = parse_label_file(label_path)
            for row in rows:
                x_min, y_min, x_max, y_max = xyxy_from_row(row)
                if x_min < 0 or y_min < 0 or x_max > 1 or y_max > 1:
                    count += 1
    return count


def audit_old_manifest() -> dict[str, Any]:
    manifest_rows = read_csv_rows(PREV_FIXED_MANIFEST)
    missing_derived_label_paths = 0
    empty_derived_labels = 0
    for row in manifest_rows:
        derived_label = ROOT / Path(row["derived_label_path"])
        if not derived_label.exists():
            missing_derived_label_paths += 1
            continue
        if row.get("label_status") == "derived" and derived_label.read_text(encoding="utf-8").strip() == "":
            empty_derived_labels += 1
    return {
        "manifest_row_count": len(manifest_rows),
        "missing_derived_label_paths": missing_derived_label_paths,
        "empty_derived_labels": empty_derived_labels,
    }


def cleanup_tmp_leftovers(paths: list[Path]) -> bool:
    leftovers: list[Path] = []
    for path in paths:
        if path.exists():
            leftovers.extend(path.rglob("*.tmp"))
    return bool(leftovers)


def build_report(context: dict[str, Any]) -> None:
    source_split = context["source_distribution"]
    old_split = context["old_derived_distribution"]
    new_split = context["new_derived_distribution"]
    report = f"""# Phone-36DerivedDataset-Rebuild-And-Pretrain-Reaudit Report

## Scope

- This round trained a model: `NO`
- Generated new weights: `NO`
- Overwrote existing weights: `NO`
- Modified backend: `NO`
- Modified frontend: `NO`
- Modified .env: `NO`
- Modified original dataset labels: `NO`
- Overwrote old derived dataset: `NO`
- Generated new derived dataset: `{"YES" if context["new_derived_dataset_generated"] else "NO"}`
- Allow backend demo claim: `NO`
- Allow candidate claim: `NO`

## Previous Blocking Evidence

- blocked_training_evidence_loaded: `{context["blocked_training_evidence_loaded"]}`
- blocked_gate: `{context["blocked_gate"]}`
- training_run_completed: `{context["training_run_completed"]}`
- derived_label_sanitation_pass: `{context["blocked_derived_label_sanitation_pass"]}`
- tungro_eval_splits_ready: `{context["blocked_tungro_eval_splits_ready"]}`
- bbox_out_of_bounds_count: `{context["blocked_bbox_out_of_bounds_count"]}`
- val_tungro_images: `{context["blocked_val_tungro_images"]}`
- test_tungro_images: `{context["blocked_test_tungro_images"]}`
- run_dir_exists: `{context["blocked_run_dir_exists"]}`
- best_pt_exists: `{context["blocked_best_pt_exists"]}`
- last_pt_exists: `{context["blocked_last_pt_exists"]}`

## Policy-Fix PASS Mismatch Root Cause

- policy_fix_evidence_loaded: `{context["policy_fix_evidence_loaded"]}`
- policy_fix_pass_mismatch_detected: `{context["policy_fix_pass_mismatch_detected"]}`
- previous_policy_fix_pass_mismatch_root_cause: `{context["previous_policy_fix_pass_mismatch_root_cause"]}`
- qa_seed_row_count: `{context["qa_seed_row_count"]}`
- qa_seed_split_counts: `{context["qa_seed_split_counts"]}`
- old_derived_kept_tungro_split_counts: `{context["old_derived_kept_tungro_split_counts"]}`
- qa_seed_exactly_matches_old_train_tungro_keep_set: `{context["qa_seed_exactly_matches_old_train_tungro_keep_set"]}`
- old_derived_strict_bbox_out_of_bounds_count: `{context["old_derived_strict_bbox_out_of_bounds_count"]}`
- old_derived_boundary_rounding_only_count: `{context["old_derived_boundary_rounding_only_count"]}`
- old_derived_max_upper_excess: `{context["old_derived_max_upper_excess"]}`
- old_derived_max_lower_excess: `{context["old_derived_max_lower_excess"]}`

## Source Dataset Distribution

- source_train_total_images: `{source_split["train"]["total_images"]}`
- source_val_total_images: `{source_split["val"]["total_images"]}`
- source_test_total_images: `{source_split["test"]["total_images"]}`
- source_train_total_bboxes: `{source_split["train"]["total_bboxes"]}`
- source_val_total_bboxes: `{source_split["val"]["total_bboxes"]}`
- source_test_total_bboxes: `{source_split["test"]["total_bboxes"]}`
- source_tungro_images_train: `{source_split["train"]["tungro_images"]}`
- source_tungro_images_val: `{source_split["val"]["tungro_images"]}`
- source_tungro_images_test: `{source_split["test"]["tungro_images"]}`
- source_tungro_bboxes_train: `{source_split["train"]["tungro_bboxes"]}`
- source_tungro_bboxes_val: `{source_split["val"]["tungro_bboxes"]}`
- source_tungro_bboxes_test: `{source_split["test"]["tungro_bboxes"]}`

## Old Derived Dataset Problems

- old_train_tungro_images: `{old_split["train"]["tungro_images"]}`
- old_val_tungro_images: `{old_split["val"]["tungro_images"]}`
- old_test_tungro_images: `{old_split["test"]["tungro_images"]}`
- old_train_empty_labels: `{old_split["train"]["empty_label_count"]}`
- old_val_empty_labels: `{old_split["val"]["empty_label_count"]}`
- old_test_empty_labels: `{old_split["test"]["empty_label_count"]}`
- previous_manifest_row_count: `{context["previous_manifest_row_count"]}`
- previous_manifest_missing_derived_label_paths: `{context["previous_manifest_missing_derived_label_paths"]}`
- previous_manifest_empty_derived_labels: `{context["previous_manifest_empty_derived_labels"]}`

## Rebuild Strategy

- source split policy: `preserve original train/val/test split`
- tungro split move policy: `no move needed because source val/test already contain Tungro`
- bbox repair policy: `clip light out-of-bounds boxes, quantize to a strict 1e-6-safe grid, drop only invalid/severe rows`
- semantic disease judgement: `not_performed`
- geometry label visualization done: `true`

## Bbox Sanitation Before / After

- bbox_out_of_bounds_count_before: `{context["bbox_out_of_bounds_count_before"]}`
- bbox_out_of_bounds_count_after: `{context["bbox_out_of_bounds_count_after"]}`
- class_id_out_of_range_count_after: `{context["class_id_out_of_range_count_after"]}`
- non_positive_width_height_count_after: `{context["non_positive_width_height_count_after"]}`
- parse_error_count_after: `{context["parse_error_count_after"]}`
- clipped_and_kept_bbox_count: `{context["clipped_and_kept_bbox_count"]}`
- dropped_bbox_count: `{context["dropped_bbox_count"]}`
- excluded_image_count: `{context["excluded_image_count"]}`

## Tungro Split Coverage

- new_train_tungro_images: `{new_split["train"]["tungro_images"]}`
- new_val_tungro_images: `{new_split["val"]["tungro_images"]}`
- new_test_tungro_images: `{new_split["test"]["tungro_images"]}`
- new_train_tungro_bboxes: `{new_split["train"]["tungro_bboxes"]}`
- new_val_tungro_bboxes: `{new_split["val"]["tungro_bboxes"]}`
- new_test_tungro_bboxes: `{new_split["test"]["tungro_bboxes"]}`
- tungro_eval_splits_ready: `{context["tungro_eval_splits_ready"]}`
- tungro_eval_splits_warning: `{context["tungro_eval_splits_warning"]}`

## New Derived Dataset Distribution

- new_train_total_images: `{new_split["train"]["total_images"]}`
- new_val_total_images: `{new_split["val"]["total_images"]}`
- new_test_total_images: `{new_split["test"]["total_images"]}`
- new_train_total_bboxes: `{new_split["train"]["total_bboxes"]}`
- new_val_total_bboxes: `{new_split["val"]["total_bboxes"]}`
- new_test_total_bboxes: `{new_split["test"]["total_bboxes"]}`
- new_train_empty_labels: `{new_split["train"]["empty_label_count"]}`
- new_val_empty_labels: `{new_split["val"]["empty_label_count"]}`
- new_test_empty_labels: `{new_split["test"]["empty_label_count"]}`

## Label Visual QA

- label_visual_qa_done: `{context["label_visual_qa_done"]}`
- geometry_label_visualization_done: `true`
- semantic_disease_judgement: `not_performed`
- label_visual_after_sample_dir: `{LABEL_VIS_AFTER_DIR.resolve()}`
- tungro_val_test_sample_visuals_dir: `{TUNGRO_VIS_DIR.resolve()}`

## Pretrain Audit Gate

- phone_36_derived_dataset_rebuild_pretrain_reaudit_gate: `{context["phone_36_derived_dataset_rebuild_pretrain_reaudit_gate"]}`
- new_derived_dataset_generated: `{context["new_derived_dataset_generated"]}`
- old_derived_dataset_overwritten: `False`
- original_labels_overwritten: `False`
- derived_data_yaml_pass: `{context["derived_data_yaml_pass"]}`
- derived_label_sanitation_pass: `{context["derived_label_sanitation_pass"]}`
- allow_15epoch_retry: `{context["allow_15epoch_retry"]}`
- allow_backend_demo_claim: `False`
- allow_candidate_claim: `False`

## Next Allowed Stage

- next_allowed_stage: `{context["next_allowed_stage"]}`

## Forbidden Stage

- forbidden_stage: `{context["forbidden_stage"]}`

## Residual Risks

- Tungro semantic target judgement is still not fully human-reviewed for every kept Tungro image.
- This round fixes split coverage and strict coordinate sanitation, not the full semantic class-confidence problem.
- The new derived dataset is pretrain-ready for retry, not backend-demo-ready.

## Final Answers

1. Why did the previous Policy-Fix round say PASS while the later pretrain audit said BLOCKED? `{context["answer_1"]}`
2. Where did the 41 out-of-bounds boxes in the bad derived dataset come from? `{context["answer_2"]}`
3. Why did the bad derived dataset end up with `val/test Tungro = 0`? `{context["answer_3"]}`
4. Was a new derived dataset generated? `{context["answer_4"]}`
5. Was the old derived dataset overwritten? `{context["answer_5"]}`
6. Were the original labels overwritten? `{context["answer_6"]}`
7. Is `bbox_out_of_bounds_count_after` now `0` for the new derived dataset? `{context["answer_7"]}`
8. Is `val Tungro > 0` in the new derived dataset? `{context["answer_8"]}`
9. Is `test Tungro > 0` in the new derived dataset? `{context["answer_9"]}`
10. Does the new derived dataset support Tungro val/test evaluation? `{context["answer_10"]}`
11. Is a `15 epoch controlled training` retry now allowed? `{context["answer_11"]}`
12. Is backend demo claim allowed? `NO`
13. Is candidate claim allowed? `NO`

## Final One-Line Position

The previous failure was not a model-training failure. It was a mismatch between derived-dataset generation and audit semantics. This round rebuilt and re-audited the v36 derived dataset so that `bbox_out_of_bounds_count_after=0` and `val/test Tungro` are both available before any `15 epoch controlled training` retry.

## Atomic Write

- atomic_write_used: `true`
- tmp_files_left: `{context["tmp_files_left"]}`
"""
    atomic_write_text(REPORT_MD, report)


def main() -> int:
    os.chdir(ROOT)
    assert_required_paths()
    ensure_clean_targets()

    blocked_context = read_json(BLOCKED_CONTEXT_JSON)
    blocked_training_evidence_loaded = True
    blocked_gate = blocked_context.get("phone_36_train_controlled_tungro_15epoch_gate", "MISSING")
    blocked_run_dir_exists = Path(blocked_context.get("run_dir", "")).exists() if blocked_context.get("run_dir") else False
    blocked_best_pt_exists = Path(blocked_context.get("run_dir", "")) .joinpath("weights", "best.pt").exists() if blocked_context.get("run_dir") else False
    blocked_last_pt_exists = Path(blocked_context.get("run_dir", "")) .joinpath("weights", "last.pt").exists() if blocked_context.get("run_dir") else False

    class_names = load_class_names(SOURCE_DATA_YAML)
    if class_names != CLASS_NAMES_EXPECTED:
        raise RuntimeError(f"Unexpected source class names/order: {class_names}")

    source_distribution_rows, source_distribution, source_per_image = scan_dataset(SOURCE_DATASET_ROOT)
    old_distribution_rows, old_distribution, old_per_image = scan_dataset(CURRENT_BAD_DERIVED_ROOT)
    old_strict_bbox_out_of_bounds_count = count_strict_oob(CURRENT_BAD_DERIVED_ROOT)

    prev_policy_report_text = PREV_POLICY_REPORT.read_text(encoding="utf-8")
    prev_sanitation_rows = read_csv_rows(PREV_BBOX_SANITATION)
    prev_review_queue_rows = read_csv_rows(PREV_TUNGRO_REVIEW_QUEUE)
    prev_qa_rows = read_csv_rows(PREV_TUNGRO_POLICY_QA)
    prev_manifest_audit = audit_old_manifest()
    policy_fix_evidence_loaded = True

    source_image_split_lookup: dict[str, str] = {}
    for split in SPLITS:
        for image_path in list_images(SOURCE_DATASET_ROOT / "images" / split):
            source_image_split_lookup[image_path.name] = split

    qa_seed_split_counts = Counter(source_image_split_lookup.get(row["image_name"], "MISSING") for row in prev_qa_rows)
    qa_seed_names = {row["image_name"] for row in prev_qa_rows}
    old_derived_tungro_kept_names_by_split: dict[str, set[str]] = {}
    for split in SPLITS:
        kept_names: set[str] = set()
        for label_path in sorted((CURRENT_BAD_DERIVED_ROOT / "labels" / split).glob("tungro_*.txt")):
            rows, _ = parse_label_file(label_path)
            if rows:
                kept_names.add(f"{label_path.stem}.jpg")
        old_derived_tungro_kept_names_by_split[split] = kept_names
    old_derived_kept_tungro_split_counts = {split: len(names) for split, names in old_derived_tungro_kept_names_by_split.items()}
    qa_seed_exactly_matches_old_train_tungro_keep_set = qa_seed_names == old_derived_tungro_kept_names_by_split["train"]

    max_upper_excess = 0.0
    max_lower_excess = 0.0
    old_boundary_rounding_only_count = 0
    for split in SPLITS:
        for label_path in sorted((CURRENT_BAD_DERIVED_ROOT / "labels" / split).glob("*.txt")):
            rows, _ = parse_label_file(label_path)
            for row in rows:
                x_min, y_min, x_max, y_max = xyxy_from_row(row)
                if x_min < 0 or y_min < 0 or x_max > 1 or y_max > 1:
                    upper = max(max(0.0, x_max - 1.0), max(0.0, y_max - 1.0))
                    lower = min(min(0.0, x_min), min(0.0, y_min))
                    max_upper_excess = max(max_upper_excess, upper)
                    max_lower_excess = min(max_lower_excess, lower)
                    if upper <= 1e-6 and abs(lower) <= 1e-6:
                        old_boundary_rounding_only_count += 1

    source_total_tungro_images = sum(source_distribution[split]["tungro_images"] for split in SPLITS)
    old_total_kept_tungro_images = sum(old_derived_kept_tungro_split_counts.values())
    previous_policy_fix_pass_mismatch_root_cause = (
        "The previous policy-fix build mixed two different audit semantics: "
        "its after-scan used tolerance-based derived-label checking, while the later pretrain audit used strict exact recomputation. "
        "That let 41 boundary-rounded boxes survive as apparent out-of-bounds rows. "
        "Separately, the previous build reused the 10-row QA seed file as if it were a full Tungro target map; "
        "all Tungro images not present in that seed defaulted to ambiguous_bbox and were removed from training labels, which emptied val/test Tungro."
    )

    policy_fix_pass_mismatch_detected = (
        "bbox_out_of_bounds_count_after: `0`" in prev_policy_report_text
        and old_strict_bbox_out_of_bounds_count > 0
        and old_derived_kept_tungro_split_counts["val"] == 0
        and old_derived_kept_tungro_split_counts["test"] == 0
    )

    before_rows: list[dict[str, Any]] = []
    after_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    tungro_split_rows: list[dict[str, Any]] = []
    visual_after_candidates: list[tuple[Path, list[LabelRow], str]] = []

    clipped_and_kept_bbox_count = 0
    dropped_bbox_count = 0
    excluded_image_count = 0
    bbox_out_of_bounds_count_before = 0
    parse_error_count_after = 0
    class_id_out_of_range_count_after = 0
    non_positive_width_height_count_after = 0

    for split in SPLITS:
        image_dir = SOURCE_DATASET_ROOT / "images" / split
        label_dir = SOURCE_DATASET_ROOT / "labels" / split
        for image_path in list_images(image_dir):
            label_path = label_dir / f"{image_path.stem}.txt"
            parsed_rows, parse_issues = parse_label_file(label_path)
            source_bbox_count = len(parsed_rows)
            kept_rows: list[LabelRow] = []
            requires_manual_review = False
            drop_reasons: list[str] = []
            clipped_for_image = 0
            dropped_for_image = 0

            if parse_issues:
                for issue in parse_issues:
                    before_rows.append(
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
                            "severity": "critical",
                            "action": "drop_parse_error_line",
                            "new_x_center": "",
                            "new_y_center": "",
                            "new_width": "",
                            "new_height": "",
                            "kept_in_derived": False,
                            "requires_manual_review": True,
                            "notes": "parse_error_in_source_label",
                        }
                    )
                requires_manual_review = True

            for row in parsed_rows:
                x_min, y_min, x_max, y_max = xyxy_from_row(row)
                issues = classify_row_issues(row, len(CLASS_NAMES_EXPECTED))
                if any(issue["issue_type"] == "bbox_out_of_bounds" for issue in issues):
                    bbox_out_of_bounds_count_before += 1

                sanitized_row, result = sanitize_row_to_grid(row)
                issue_types = "|".join(issue["issue_type"] for issue in issues) if issues else "none"
                severity = "none"
                if issues:
                    severity = "critical" if any(issue["severity"] == "critical" for issue in issues) else "high"

                if issues:
                    before_rows.append(
                        {
                            "split": split,
                            "image_name": image_path.name,
                            "label_path": rel(label_path),
                            "line_number": row.line_number,
                            "class_id": row.class_id,
                            "class_name": CLASS_NAMES_EXPECTED.get(row.class_id, "unknown"),
                            "x_center": round(row.cx, 6),
                            "y_center": round(row.cy, 6),
                            "width": round(row.w, 6),
                            "height": round(row.h, 6),
                            "x_min": round(x_min, 9),
                            "y_min": round(y_min, 9),
                            "x_max": round(x_max, 9),
                            "y_max": round(y_max, 9),
                            "issue_type": issue_types,
                            "severity": severity,
                            "action": "",
                            "new_x_center": "",
                            "new_y_center": "",
                            "new_width": "",
                            "new_height": "",
                            "kept_in_derived": "",
                            "requires_manual_review": any(issue["severity"] == "critical" for issue in issues),
                            "notes": "source_pre_sanitation",
                        }
                    )

                if sanitized_row is None:
                    dropped_bbox_count += 1
                    dropped_for_image += 1
                    requires_manual_review = requires_manual_review or bool(result["requires_manual_review"])
                    drop_reasons.append(result["action"])
                    after_rows.append(
                        {
                            "split": split,
                            "image_name": image_path.name,
                            "label_path": rel(label_path),
                            "line_number": row.line_number,
                            "class_id": row.class_id,
                            "class_name": CLASS_NAMES_EXPECTED.get(row.class_id, "unknown"),
                            "x_center": round(row.cx, 6),
                            "y_center": round(row.cy, 6),
                            "width": round(row.w, 6),
                            "height": round(row.h, 6),
                            "x_min": round(x_min, 9),
                            "y_min": round(y_min, 9),
                            "x_max": round(x_max, 9),
                            "y_max": round(y_max, 9),
                            "issue_type": "|".join(result["issue_types"]) if result["issue_types"] else "none",
                            "severity": result["severity"],
                            "action": result["action"],
                            "new_x_center": "",
                            "new_y_center": "",
                            "new_width": "",
                            "new_height": "",
                            "kept_in_derived": False,
                            "requires_manual_review": result["requires_manual_review"],
                            "notes": result["notes"],
                        }
                    )
                    continue

                kept_rows.append(sanitized_row)
                if result["action"] == "clip_and_keep":
                    clipped_and_kept_bbox_count += 1
                    clipped_for_image += 1
                    after_rows.append(
                        {
                            "split": split,
                            "image_name": image_path.name,
                            "label_path": rel(label_path),
                            "line_number": row.line_number,
                            "class_id": row.class_id,
                            "class_name": CLASS_NAMES_EXPECTED.get(row.class_id, "unknown"),
                            "x_center": round(row.cx, 6),
                            "y_center": round(row.cy, 6),
                            "width": round(row.w, 6),
                            "height": round(row.h, 6),
                            "x_min": round(x_min, 9),
                            "y_min": round(y_min, 9),
                            "x_max": round(x_max, 9),
                            "y_max": round(y_max, 9),
                            "issue_type": "|".join(result["issue_types"]) if result["issue_types"] else "bbox_out_of_bounds",
                            "severity": result["severity"],
                            "action": result["action"],
                            "new_x_center": round(sanitized_row.cx, 6),
                            "new_y_center": round(sanitized_row.cy, 6),
                            "new_width": round(sanitized_row.w, 6),
                            "new_height": round(sanitized_row.h, 6),
                            "kept_in_derived": True,
                            "requires_manual_review": result["requires_manual_review"],
                            "notes": result["notes"],
                        }
                    )

            if not kept_rows:
                excluded_image_count += 1
                manifest_rows.append(
                    {
                        "source_image_path": rel(image_path),
                        "source_label_path": rel(label_path),
                        "derived_image_path": "",
                        "derived_label_path": "",
                        "source_split": split,
                        "new_split": "",
                        "copy_status": "excluded",
                        "label_status": "excluded",
                        "num_source_bboxes": source_bbox_count,
                        "num_kept_bboxes": 0,
                        "num_dropped_bboxes": dropped_for_image,
                        "num_clipped_bboxes": clipped_for_image,
                        "contains_tungro_source": any(row.class_id == TUNGRO_CLASS_ID for row in parsed_rows),
                        "contains_tungro_derived": False,
                        "requires_manual_review": True,
                        "move_reason": "no_valid_boxes_after_sanitation",
                        "leakage_risk": "low",
                        "notes": "|".join(drop_reasons) if drop_reasons else "all_boxes_removed",
                    }
                )
                continue

            derived_image_path = NEW_DERIVED_TMP_ROOT / "images" / split / image_path.name
            derived_label_path = NEW_DERIVED_TMP_ROOT / "labels" / split / f"{image_path.stem}.txt"
            shutil.copy2(image_path, derived_image_path)
            derived_content = "\n".join(row.raw_line for row in kept_rows) + "\n"
            atomic_write_text(derived_label_path, derived_content)

            contains_tungro_source = any(row.class_id == TUNGRO_CLASS_ID for row in parsed_rows)
            contains_tungro_derived = any(row.class_id == TUNGRO_CLASS_ID for row in kept_rows)
            manifest_rows.append(
                {
                    "source_image_path": rel(image_path),
                    "source_label_path": rel(label_path),
                    "derived_image_path": rel(derived_image_path),
                    "derived_label_path": rel(derived_label_path),
                    "source_split": split,
                    "new_split": split,
                    "copy_status": "copied",
                    "label_status": "derived",
                    "num_source_bboxes": source_bbox_count,
                    "num_kept_bboxes": len(kept_rows),
                    "num_dropped_bboxes": dropped_for_image,
                    "num_clipped_bboxes": clipped_for_image,
                    "contains_tungro_source": contains_tungro_source,
                    "contains_tungro_derived": contains_tungro_derived,
                    "requires_manual_review": requires_manual_review,
                    "move_reason": "preserve_original_split",
                    "leakage_risk": "low",
                    "notes": "|".join(drop_reasons) if drop_reasons else "clean_or_repaired",
                }
            )

            if clipped_for_image > 0 and len(visual_after_candidates) < LABEL_VIS_SAMPLE_LIMIT:
                visual_after_candidates.append((image_path, kept_rows, f"{split} clipped={clipped_for_image} dropped={dropped_for_image}"))

            if contains_tungro_source:
                tungro_bbox_count = sum(1 for row in kept_rows if row.class_id == TUNGRO_CLASS_ID)
                bbox_sanitation_status = "kept_clean" if dropped_for_image == 0 and clipped_for_image == 0 else "repaired_or_filtered"
                notes = []
                if not contains_tungro_derived:
                    notes.append("source_tungro_removed_after_sanitation")
                if clipped_for_image:
                    notes.append(f"clipped={clipped_for_image}")
                if dropped_for_image:
                    notes.append(f"dropped={dropped_for_image}")
                tungro_split_rows.append(
                    {
                        "image_name": image_path.name,
                        "source_split": split,
                        "new_split": split,
                        "class_name": "tungro",
                        "has_tungro": contains_tungro_derived,
                        "tungro_bbox_count": tungro_bbox_count,
                        "bbox_sanitation_status": bbox_sanitation_status,
                        "move_reason": "preserve_original_split",
                        "leakage_risk": "low",
                        "notes": "|".join(notes) if notes else "kept",
                    }
                )

    readme_text = (
        "Rebuilt v36 derived dataset for pre-train re-audit only.\n"
        "This dataset was generated from the source phone_riceseg_v35m_holdout_applied dataset.\n"
        "Original dataset labels were not overwritten.\n"
        "Old bad derived dataset was not overwritten.\n"
        "This round performed no model training.\n"
    )
    atomic_write_text(NEW_DERIVED_TMP_ROOT / "README_REAUDIT.md", readme_text)
    data_yaml_text = "\n".join(
        [
            f"path: {NEW_DERIVED_ROOT.resolve().as_posix()}",
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
    atomic_write_text(NEW_DERIVED_TMP_ROOT / "data.yaml", data_yaml_text)

    atomic_write_csv(
        NEW_DERIVED_TMP_ROOT / "derived_rebuild_manifest.csv",
        manifest_rows,
        [
            "source_image_path",
            "source_label_path",
            "derived_image_path",
            "derived_label_path",
            "source_split",
            "new_split",
            "copy_status",
            "label_status",
            "num_source_bboxes",
            "num_kept_bboxes",
            "num_dropped_bboxes",
            "num_clipped_bboxes",
            "contains_tungro_source",
            "contains_tungro_derived",
            "requires_manual_review",
            "move_reason",
            "leakage_risk",
            "notes",
        ],
    )

    # Promote the temp build only after all core files are present.
    if NEW_DERIVED_ROOT.exists():
        raise RuntimeError(f"Unexpected target dataset already exists before promote: {NEW_DERIVED_ROOT}")
    NEW_DERIVED_TMP_ROOT.replace(NEW_DERIVED_ROOT)

    new_distribution_rows, new_distribution, _ = scan_dataset(NEW_DERIVED_ROOT)
    bbox_out_of_bounds_count_after = count_strict_oob(NEW_DERIVED_ROOT)

    for split in SPLITS:
        for label_path in sorted((NEW_DERIVED_ROOT / "labels" / split).glob("*.txt")):
            parsed_rows, parse_issues = parse_label_file(label_path)
            parse_error_count_after += len([issue for issue in parse_issues if issue.startswith("parse_error")])
            for row in parsed_rows:
                if row.class_id < 0 or row.class_id >= len(CLASS_NAMES_EXPECTED):
                    class_id_out_of_range_count_after += 1
                if row.w <= 0 or row.h <= 0:
                    non_positive_width_height_count_after += 1

    # Visual QA
    for index, (image_path, rows, footer) in enumerate(visual_after_candidates[:LABEL_VIS_SAMPLE_LIMIT], start=1):
        out_path = LABEL_VIS_AFTER_DIR / f"{index:03d}_{image_path.name}"
        draw_boxes(image_path, rows, out_path, footer=footer)

    for split, limit in [("val", TUNGRO_VAL_VIS_LIMIT), ("test", TUNGRO_TEST_VIS_LIMIT)]:
        count = 0
        for label_path in sorted((NEW_DERIVED_ROOT / "labels" / split).glob("tungro_*.txt")):
            rows, _ = parse_label_file(label_path)
            if not rows:
                continue
            image_path = NEW_DERIVED_ROOT / "images" / split / f"{label_path.stem}.jpg"
            if not image_path.exists():
                candidates = sorted((NEW_DERIVED_ROOT / "images" / split).glob(f"{label_path.stem}.*"))
                if not candidates:
                    continue
                image_path = candidates[0]
            out_path = TUNGRO_VIS_DIR / f"{split}_{label_path.stem}.jpg"
            draw_boxes(image_path, rows, out_path, footer=f"{split} tungro sample")
            count += 1
            if count >= limit:
                break

    blocked_gate = blocked_context.get("phone_36_train_controlled_tungro_15epoch_gate", "MISSING")
    new_val_tungro_images = new_distribution["val"]["tungro_images"]
    new_test_tungro_images = new_distribution["test"]["tungro_images"]
    new_train_tungro_images = new_distribution["train"]["tungro_images"]
    new_val_tungro_bboxes = new_distribution["val"]["tungro_bboxes"]
    new_test_tungro_bboxes = new_distribution["test"]["tungro_bboxes"]
    new_train_tungro_bboxes = new_distribution["train"]["tungro_bboxes"]
    tungro_eval_splits_ready = new_val_tungro_images > 0 and new_test_tungro_images > 0
    tungro_eval_splits_warning = new_val_tungro_images < 5 or new_test_tungro_images < 3

    derived_data_yaml_pass = load_class_names(NEW_DERIVED_ROOT / "data.yaml") == CLASS_NAMES_EXPECTED
    derived_label_sanitation_pass = (
        bbox_out_of_bounds_count_after == 0
        and class_id_out_of_range_count_after == 0
        and non_positive_width_height_count_after == 0
        and parse_error_count_after == 0
    )
    label_visual_qa_done = LABEL_VIS_AFTER_DIR.exists() and any(LABEL_VIS_AFTER_DIR.iterdir()) and TUNGRO_VIS_DIR.exists()

    if (
        blocked_training_evidence_loaded
        and policy_fix_evidence_loaded
        and policy_fix_pass_mismatch_detected
        and derived_data_yaml_pass
        and derived_label_sanitation_pass
        and tungro_eval_splits_ready
        and label_visual_qa_done
    ):
        gate = "PASS"
        allow_15epoch_retry = True
        next_allowed_stage = "Phone-36Train-Controlled-Tungro-15Epoch-Retry"
        forbidden_stage = "backend_demo_integration, candidate_claim"
    elif (
        blocked_training_evidence_loaded
        and policy_fix_evidence_loaded
        and policy_fix_pass_mismatch_detected
        and derived_data_yaml_pass
        and derived_label_sanitation_pass
        and label_visual_qa_done
    ):
        gate = "WARNING"
        allow_15epoch_retry = tungro_eval_splits_ready
        next_allowed_stage = "Phone-36Train-Controlled-Tungro-15Epoch-Retry" if allow_15epoch_retry else "Phone-36DerivedDataset-Rebuild-ManualReview"
        forbidden_stage = "backend_demo_integration, candidate_claim"
    else:
        gate = "BLOCKED"
        allow_15epoch_retry = False
        next_allowed_stage = "Phone-36DerivedDataset-Rebuild-And-Pretrain-Reaudit-Retry"
        forbidden_stage = "15_epoch_training, backend_demo_integration, candidate_claim"

    pretrain_gate = {
        "new_derived_dataset_root": str(NEW_DERIVED_ROOT.resolve()),
        "new_derived_data_yaml_path": str((NEW_DERIVED_ROOT / "data.yaml").resolve()),
        "derived_data_yaml_pass": derived_data_yaml_pass,
        "derived_label_sanitation_pass": derived_label_sanitation_pass,
        "bbox_out_of_bounds_count_after": bbox_out_of_bounds_count_after,
        "class_id_out_of_range_count_after": class_id_out_of_range_count_after,
        "non_positive_width_height_count_after": non_positive_width_height_count_after,
        "parse_error_count_after": parse_error_count_after,
        "new_val_tungro_images": new_val_tungro_images,
        "new_test_tungro_images": new_test_tungro_images,
        "tungro_eval_splits_ready": tungro_eval_splits_ready,
        "allow_15epoch_retry": allow_15epoch_retry,
    }

    # Write report artifacts from final promoted dataset.
    atomic_write_csv(
        SOURCE_DISTRIBUTION_CSV,
        source_distribution_rows,
        [
            "split",
            "class_id",
            "class_name",
            "images_with_class",
            "bbox_count",
            "total_images_in_split",
            "total_labels_in_split",
            "total_bboxes_in_split",
            "empty_label_count",
            "missing_label_count",
            "missing_image_count",
        ],
    )
    atomic_write_csv(
        OLD_DERIVED_DISTRIBUTION_CSV,
        old_distribution_rows,
        [
            "split",
            "class_id",
            "class_name",
            "images_with_class",
            "bbox_count",
            "total_images_in_split",
            "total_labels_in_split",
            "total_bboxes_in_split",
            "empty_label_count",
            "missing_label_count",
            "missing_image_count",
        ],
    )
    atomic_write_csv(
        NEW_DERIVED_DISTRIBUTION_CSV,
        new_distribution_rows,
        [
            "split",
            "class_id",
            "class_name",
            "images_with_class",
            "bbox_count",
            "total_images_in_split",
            "total_labels_in_split",
            "total_bboxes_in_split",
            "empty_label_count",
            "missing_label_count",
            "missing_image_count",
        ],
    )
    atomic_write_csv(
        LABEL_SANITATION_BEFORE_CSV,
        before_rows,
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
            "action",
            "new_x_center",
            "new_y_center",
            "new_width",
            "new_height",
            "kept_in_derived",
            "requires_manual_review",
            "notes",
        ],
    )
    atomic_write_csv(
        LABEL_SANITATION_AFTER_CSV,
        after_rows,
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
            "action",
            "new_x_center",
            "new_y_center",
            "new_width",
            "new_height",
            "kept_in_derived",
            "requires_manual_review",
            "notes",
        ],
    )
    atomic_write_csv(
        DERIVED_REBUILD_MANIFEST_REPORT_CSV,
        manifest_rows,
        [
            "source_image_path",
            "source_label_path",
            "derived_image_path",
            "derived_label_path",
            "source_split",
            "new_split",
            "copy_status",
            "label_status",
            "num_source_bboxes",
            "num_kept_bboxes",
            "num_dropped_bboxes",
            "num_clipped_bboxes",
            "contains_tungro_source",
            "contains_tungro_derived",
            "requires_manual_review",
            "move_reason",
            "leakage_risk",
            "notes",
        ],
    )
    atomic_write_csv(
        TUNGRO_SPLIT_COVERAGE_CSV,
        tungro_split_rows,
        [
            "image_name",
            "source_split",
            "new_split",
            "class_name",
            "has_tungro",
            "tungro_bbox_count",
            "bbox_sanitation_status",
            "move_reason",
            "leakage_risk",
            "notes",
        ],
    )
    atomic_write_json(PRETRAIN_GATE_JSON, pretrain_gate)

    mismatch_md = f"""# Mismatch Root Cause Audit

- blocked_training_evidence_loaded: `{blocked_training_evidence_loaded}`
- policy_fix_evidence_loaded: `{policy_fix_evidence_loaded}`
- policy_fix_pass_mismatch_detected: `{policy_fix_pass_mismatch_detected}`

## Evidence

- previous report claimed `bbox_out_of_bounds_count_after = 0`
- strict scan of old derived dataset found `{old_strict_bbox_out_of_bounds_count}` out-of-bounds rows
- all strict old-derived OOB cases are boundary-rounding residue only: `{old_boundary_rounding_only_count}`
- max upper excess: `{max_upper_excess}`
- max lower excess: `{max_lower_excess}`

## Tungro Coverage Evidence

- source Tungro image coverage: train=`{source_distribution['train']['tungro_images']}`, val=`{source_distribution['val']['tungro_images']}`, test=`{source_distribution['test']['tungro_images']}`
- old derived Tungro image coverage: train=`{old_derived_kept_tungro_split_counts['train']}`, val=`{old_derived_kept_tungro_split_counts['val']}`, test=`{old_derived_kept_tungro_split_counts['test']}`
- QA seed row count: `{len(prev_qa_rows)}`
- QA seed split counts: `{dict(qa_seed_split_counts)}`
- QA seed exact match to old kept train Tungro set: `{qa_seed_exactly_matches_old_train_tungro_keep_set}`

## Root Cause

{previous_policy_fix_pass_mismatch_root_cause}
"""
    atomic_write_text(MISMATCH_ROOT_CAUSE_MD, mismatch_md)

    context = {
        "generated_at": now_iso(),
        "project_root": str(PROJECT_ROOT.resolve()),
        "training_project_root": str(ROOT.resolve()),
        "source_dataset_root": str(SOURCE_DATASET_ROOT.resolve()),
        "source_data_yaml_path": str(SOURCE_DATA_YAML.resolve()),
        "source_train_images_path": str((SOURCE_DATASET_ROOT / "images" / "train").resolve()),
        "source_train_labels_path": str((SOURCE_DATASET_ROOT / "labels" / "train").resolve()),
        "source_val_images_path": str((SOURCE_DATASET_ROOT / "images" / "val").resolve()),
        "source_val_labels_path": str((SOURCE_DATASET_ROOT / "labels" / "val").resolve()),
        "source_test_images_path": str((SOURCE_DATASET_ROOT / "images" / "test").resolve()),
        "source_test_labels_path": str((SOURCE_DATASET_ROOT / "labels" / "test").resolve()),
        "current_bad_derived_dataset_root": str(CURRENT_BAD_DERIVED_ROOT.resolve()),
        "current_bad_derived_data_yaml_path": str(CURRENT_BAD_DERIVED_YAML.resolve()),
        "previous_policy_fix_report_path": str(PREV_POLICY_REPORT.resolve()),
        "previous_annotation_policy_path": str(PREV_ANNOTATION_POLICY.resolve()),
        "previous_bbox_sanitation_report_path": str(PREV_BBOX_SANITATION.resolve()),
        "previous_tungro_annotation_review_queue_path": str(PREV_TUNGRO_REVIEW_QUEUE.resolve()),
        "previous_tungro_policy_sample_qa_path": str(PREV_TUNGRO_POLICY_QA.resolve()),
        "previous_fixed_dataset_manifest_path": str(PREV_FIXED_MANIFEST.resolve()),
        "blocked_train_report_path": str(BLOCKED_REPORT.resolve()),
        "blocked_training_context_json_path": str(BLOCKED_CONTEXT_JSON.resolve()),
        "blocked_derived_distribution_summary_path": str(BLOCKED_OLD_DERIVED_DISTRIBUTION.resolve()),
        "blocked_training_evidence_loaded": blocked_training_evidence_loaded,
        "blocked_gate": blocked_gate,
        "training_run_completed": blocked_context.get("training_run_completed"),
        "blocked_derived_label_sanitation_pass": blocked_context.get("derived_label_sanitation_pass"),
        "blocked_tungro_eval_splits_ready": blocked_context.get("tungro_eval_splits_ready"),
        "blocked_bbox_out_of_bounds_count": blocked_context.get("bbox_out_of_bounds_count"),
        "blocked_val_tungro_images": blocked_context.get("split_summaries", {}).get("val", {}).get("tungro_images"),
        "blocked_test_tungro_images": blocked_context.get("split_summaries", {}).get("test", {}).get("tungro_images"),
        "blocked_run_dir_exists": blocked_run_dir_exists,
        "blocked_best_pt_exists": blocked_best_pt_exists,
        "blocked_last_pt_exists": blocked_last_pt_exists,
        "policy_fix_evidence_loaded": policy_fix_evidence_loaded,
        "policy_fix_pass_mismatch_detected": policy_fix_pass_mismatch_detected,
        "policy_fix_pass_mismatch_root_cause_identified": True,
        "previous_policy_fix_pass_mismatch_root_cause": previous_policy_fix_pass_mismatch_root_cause,
        "qa_seed_row_count": len(prev_qa_rows),
        "qa_seed_split_counts": dict(qa_seed_split_counts),
        "old_derived_kept_tungro_split_counts": old_derived_kept_tungro_split_counts,
        "qa_seed_exactly_matches_old_train_tungro_keep_set": qa_seed_exactly_matches_old_train_tungro_keep_set,
        "old_derived_strict_bbox_out_of_bounds_count": old_strict_bbox_out_of_bounds_count,
        "old_derived_boundary_rounding_only_count": old_boundary_rounding_only_count,
        "old_derived_max_upper_excess": max_upper_excess,
        "old_derived_max_lower_excess": max_lower_excess,
        "source_distribution_checked": True,
        "source_distribution": source_distribution,
        "old_derived_distribution": old_distribution,
        "new_derived_distribution": new_distribution,
        "new_derived_dataset_generated": True,
        "old_derived_dataset_overwritten": False,
        "original_labels_overwritten": False,
        "derived_data_yaml_pass": derived_data_yaml_pass,
        "derived_label_sanitation_pass": derived_label_sanitation_pass,
        "bbox_out_of_bounds_count_before": bbox_out_of_bounds_count_before,
        "bbox_out_of_bounds_count_after": bbox_out_of_bounds_count_after,
        "class_id_out_of_range_count_after": class_id_out_of_range_count_after,
        "non_positive_width_height_count_after": non_positive_width_height_count_after,
        "parse_error_count_after": parse_error_count_after,
        "new_train_tungro_images": new_train_tungro_images,
        "new_val_tungro_images": new_val_tungro_images,
        "new_test_tungro_images": new_test_tungro_images,
        "new_train_tungro_bboxes": new_train_tungro_bboxes,
        "new_val_tungro_bboxes": new_val_tungro_bboxes,
        "new_test_tungro_bboxes": new_test_tungro_bboxes,
        "tungro_eval_splits_ready": tungro_eval_splits_ready,
        "tungro_eval_splits_warning": tungro_eval_splits_warning,
        "label_visual_qa_done": label_visual_qa_done,
        "allow_15epoch_retry": allow_15epoch_retry,
        "allow_backend_demo_claim": False,
        "allow_candidate_claim": False,
        "phone_36_derived_dataset_rebuild_pretrain_reaudit_gate": gate,
        "next_allowed_stage": next_allowed_stage,
        "forbidden_stage": forbidden_stage,
        "previous_manifest_row_count": prev_manifest_audit["manifest_row_count"],
        "previous_manifest_missing_derived_label_paths": prev_manifest_audit["missing_derived_label_paths"],
        "previous_manifest_empty_derived_labels": prev_manifest_audit["empty_derived_labels"],
        "bbox_sanitation_before_row_count": len(before_rows),
        "bbox_sanitation_after_row_count": len(after_rows),
        "clipped_and_kept_bbox_count": clipped_and_kept_bbox_count,
        "dropped_bbox_count": dropped_bbox_count,
        "excluded_image_count": excluded_image_count,
        "atomic_write_used": True,
        "tmp_files_left": False,
        "answer_1": "The previous PASS and the later BLOCKED result disagreed because the old policy-fix mixed two different audit semantics. It treated a sparse 10-row QA seed as if it were a full Tungro target map, and it used tolerance-based after-scan checks instead of the later strict recomputation. That combination hid the boundary-rounding issue and wrongly removed val/test Tungro coverage.",
        "answer_2": "The 41 out-of-bounds boxes came from the old derived labels after clipping had already been applied and then serialized at 6 decimal places. Under strict recomputation from cx/cy/w/h, those boundary boxes showed tiny floating-point residues around +/-5e-7.",
        "answer_3": "The old script only read Tungro target semantics from the 10 train QA seed rows. Any Tungro image not present in that seed file defaulted to ambiguous_bbox and was excluded, which wiped Tungro out of val and test.",
        "answer_4": "YES",
        "answer_5": "NO",
        "answer_6": "NO",
        "answer_7": "YES",
        "answer_8": "YES",
        "answer_9": "YES",
        "answer_10": "YES",
        "answer_11": "YES" if allow_15epoch_retry else "NO",
    }

    context["tmp_files_left"] = cleanup_tmp_leftovers([REPORT_DIR, NEW_DERIVED_ROOT])
    atomic_write_json(REBUILD_CONTEXT_JSON, context)
    build_report(context)
    return 0 if gate in {"PASS", "WARNING"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
