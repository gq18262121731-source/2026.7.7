"""Generate UAV BLB 408 manual-gate assets without training or label edits."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception as exc:  # noqa: BLE001
    raise SystemExit(f"Pillow is required for visual audit generation: {exc}") from exc


ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = ROOT / "datasets" / "rice_uav_ms_blb_preview_1000"
REPORTS = ROOT / "reports"
METADATA = ROOT / "metadata"
VISUAL_DIR = REPORTS / "uav_blb_408_manual_gate_visual_audit"
DATASET_NAME = "uav_blb_408"
CLASS_NAMES = {0: "bacterial_leaf_blight"}
RANDOM_SEED = 40835
REVIEW_TARGET = 120
SPLITS = ("train", "val", "test")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


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
    tmp.replace(path)


def read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_images(split: str) -> list[Path]:
    folder = DATASET_ROOT / "images" / split
    if not folder.exists():
        return []
    return sorted(path for path in folder.iterdir() if path.suffix.lower() in IMAGE_EXTS)


def label_path_for(image_path: Path, split: str) -> Path:
    return DATASET_ROOT / "labels" / split / f"{image_path.stem}.txt"


def parse_label(label_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    boxes: list[dict[str, Any]] = []
    issues: list[str] = []
    if not label_path.exists():
        return boxes, ["missing_label"]
    text = label_path.read_text(encoding="utf-8").strip()
    if not text:
        return boxes, ["empty_label"]
    for line_no, line in enumerate(text.splitlines(), start=1):
        parts = line.split()
        if len(parts) != 5:
            issues.append(f"invalid_label_format:{line_no}")
            continue
        try:
            class_id_float = float(parts[0])
            class_id = int(class_id_float)
            x, y, w, h = [float(value) for value in parts[1:]]
        except ValueError:
            issues.append(f"non_numeric_label:{line_no}")
            continue
        if class_id_float != class_id or class_id not in CLASS_NAMES:
            issues.append(f"invalid_class_id:{line_no}:{parts[0]}")
        finite = all(math.isfinite(value) for value in (x, y, w, h))
        if not finite:
            issues.append(f"non_finite_bbox:{line_no}")
            continue
        left, top, right, bottom = x - w / 2, y - h / 2, x + w / 2, y + h / 2
        out_of_bounds = w <= 0 or h <= 0 or left < -1e-6 or top < -1e-6 or right > 1 + 1e-6 or bottom > 1 + 1e-6
        if out_of_bounds:
            issues.append(f"bbox_out_of_bounds:{line_no}")
        boxes.append(
            {
                "class_id": class_id,
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "area": w * h,
                "line_no": line_no,
            }
        )
    return boxes, issues


def image_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_dataset() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    split_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    issue_counter: Counter[str] = Counter()
    missing_labels: list[str] = []
    empty_labels: list[str] = []
    orphan_labels: list[str] = []
    unreadable_images: list[str] = []
    dims_counter: Counter[str] = Counter()
    hash_to_records: dict[str, list[str]] = defaultdict(list)
    stem_to_splits: dict[str, set[str]] = defaultdict(set)
    bbox_total = 0

    for split in SPLITS:
        for image_path in list_images(split):
            split_counts[split] += 1
            label_path = label_path_for(image_path, split)
            boxes, label_issues = parse_label(label_path)
            if label_path.exists():
                label_counts[split] += 1
            bbox_total += len(boxes)
            for box in boxes:
                class_counts[CLASS_NAMES.get(box["class_id"], f"class_{box['class_id']}")] += 1
            for issue in label_issues:
                issue_counter[issue.split(":", 1)[0]] += 1
            if "missing_label" in label_issues:
                missing_labels.append(rel(image_path))
            if "empty_label" in label_issues:
                empty_labels.append(rel(label_path))
            width = height = None
            image_issue: list[str] = []
            try:
                with Image.open(image_path) as image:
                    width, height = image.size
                dims_counter[f"{width}x{height}"] += 1
                digest = image_hash(image_path)
                hash_to_records[digest].append(f"{split}/{image_path.name}")
            except Exception as exc:  # noqa: BLE001
                image_issue.append(f"unreadable_image:{exc}")
                issue_counter["unreadable_image"] += 1
                unreadable_images.append(rel(image_path))
            stem_to_splits[image_path.stem].add(split)
            records.append(
                {
                    "split": split,
                    "image_name": image_path.name,
                    "image_path": image_path,
                    "label_path": label_path,
                    "bbox_count": len(boxes),
                    "boxes": boxes,
                    "label_issues": label_issues,
                    "image_issues": image_issue,
                    "image_width": width,
                    "image_height": height,
                    "max_bbox_area": max((box["area"] for box in boxes), default=0.0),
                    "min_bbox_area": min((box["area"] for box in boxes), default=0.0),
                    "small_bbox_count": sum(1 for box in boxes if box["area"] < 0.002),
                    "large_bbox_count": sum(1 for box in boxes if box["area"] > 0.12),
                }
            )

    for split in SPLITS:
        label_dir = DATASET_ROOT / "labels" / split
        image_stems = {path.stem for path in list_images(split)}
        if label_dir.exists():
            for label_path in sorted(label_dir.glob("*.txt")):
                if label_path.stem not in image_stems:
                    orphan_labels.append(rel(label_path))
                    issue_counter["orphan_label"] += 1

    duplicate_hash_groups = [names for names in hash_to_records.values() if len(names) > 1]
    for group in duplicate_hash_groups:
        issue_counter["duplicate_image"] += len(group)
    split_leakage_by_name = {stem: sorted(splits) for stem, splits in stem_to_splits.items() if len(splits) > 1}
    split_leakage_by_hash = [group for group in duplicate_hash_groups if len({item.split("/", 1)[0] for item in group}) > 1]
    if split_leakage_by_name:
        issue_counter["split_leakage_name"] += len(split_leakage_by_name)
    if split_leakage_by_hash:
        issue_counter["split_leakage_hash"] += len(split_leakage_by_hash)

    issues = []
    for key, count in sorted(issue_counter.items()):
        if count:
            issues.append({"issue": key, "count": count})

    return {
        "generated_at": now_iso(),
        "dataset_name": DATASET_NAME,
        "dataset_root": rel(DATASET_ROOT),
        "data_yaml": rel(DATASET_ROOT / "data.yaml"),
        "records": records,
        "images_count": sum(split_counts.values()),
        "labels_count": sum(label_counts.values()),
        "bbox_count": bbox_total,
        "split_distribution": dict(split_counts),
        "label_split_distribution": dict(label_counts),
        "class_distribution": dict(class_counts),
        "image_dimension_distribution": dict(dims_counter),
        "missing_labels": missing_labels,
        "empty_labels": empty_labels,
        "orphan_labels": orphan_labels,
        "unreadable_images": unreadable_images,
        "duplicate_image_groups": duplicate_hash_groups,
        "split_leakage_by_name": split_leakage_by_name,
        "split_leakage_by_hash": split_leakage_by_hash,
        "issues": issues,
        "machine_check": "PASS" if not issues else "WARNING",
        "consistent_with_historical_408": sum(split_counts.values()) == 408 and bbox_total == 2373,
        "has_real_labeled_objects": bbox_total > 0,
        "no_real_object": bbox_total == 0,
    }


def report_exists(name: str) -> bool:
    return (REPORTS / name).exists()


def build_inventory(scan: dict[str, Any]) -> dict[str, Any]:
    model_dirs = [
        "experiments/uav_blb_yolo/runs/exp_uav_blb_preview408_v0_1_5epoch",
        "experiments/uav_blb_yolo/runs/exp_uav_blb_preview408_strict_v0_2_controlled",
    ]
    return {
        "generated_at": now_iso(),
        "dataset_root": scan["dataset_root"],
        "images_count": scan["images_count"],
        "labels_count": scan["labels_count"],
        "bbox_count": scan["bbox_count"],
        "split_distribution": scan["split_distribution"],
        "class_distribution": scan["class_distribution"],
        "data_yaml": scan["data_yaml"],
        "has_dataset_check": report_exists("uav_blb_preview408_quality_recheck.json") or report_exists("uav_blb_preview408_quality_recheck.md"),
        "has_ab_eval": report_exists("uav_blb_ab_eval_comparison.json") and report_exists("uav_blb_ab_eval_sample_list.json"),
        "has_zero_detection_analysis": report_exists("uav_blb_zero_detection_error_analysis.md"),
        "available_models": [
            {
                "model_id": "experimental_408_epoch5",
                "path": model_dirs[0],
                "exists": (ROOT / model_dirs[0]).exists(),
                "status": "active_optional_candidate",
            },
            {
                "model_id": "strict408_v0_2_controlled",
                "path": model_dirs[1],
                "exists": (ROOT / model_dirs[1]).exists(),
                "status": "experimental_reference_only",
            },
        ],
        "active_optional_candidate": "experimental_408_epoch5",
        "experimental_reference": "strict408_v0_2_controlled",
        "training_allowed": False,
        "notes": [
            "UAV crop_object / rice_panicle are assistive object targets, not disease recognition.",
            "strict408_v0_2_controlled is not promoted despite stronger metrics because locked A/B increased zero detections.",
        ],
    }


def render_inventory_md(payload: dict[str, Any]) -> str:
    lines = [
        "# UAV BLB 408 Current Asset Inventory",
        "",
        f"- dataset_root: `{payload['dataset_root']}`",
        f"- images_count: `{payload['images_count']}`",
        f"- labels_count: `{payload['labels_count']}`",
        f"- bbox_count: `{payload['bbox_count']}`",
        f"- split_distribution: `{payload['split_distribution']}`",
        f"- class_distribution: `{payload['class_distribution']}`",
        f"- data_yaml: `{payload['data_yaml']}`",
        f"- has_dataset_check: `{payload['has_dataset_check']}`",
        f"- has_ab_eval: `{payload['has_ab_eval']}`",
        f"- has_zero_detection_analysis: `{payload['has_zero_detection_analysis']}`",
        f"- active_optional_candidate: `{payload['active_optional_candidate']}`",
        f"- experimental_reference: `{payload['experimental_reference']}`",
        f"- training_allowed: `{payload['training_allowed']}`",
        "",
        "## Available Models",
        "",
    ]
    for model in payload["available_models"]:
        lines.append(f"- `{model['model_id']}`: `{model['status']}`, exists=`{model['exists']}`, path=`{model['path']}`")
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {note}" for note in payload["notes"])
    return "\n".join(lines) + "\n"


def build_dataset_check(scan: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "dataset_name": DATASET_NAME,
        "dataset_root": scan["dataset_root"],
        "machine_check": scan["machine_check"],
        "images_count": scan["images_count"],
        "labels_count": scan["labels_count"],
        "bbox_count": scan["bbox_count"],
        "train_val_test_split": scan["split_distribution"],
        "class_id_legal": not any(item["issue"] == "invalid_class_id" for item in scan["issues"]),
        "bbox_out_of_bounds": any(item["issue"] == "bbox_out_of_bounds" for item in scan["issues"]),
        "has_empty_label": bool(scan["empty_labels"]),
        "has_missing_label": bool(scan["missing_labels"]),
        "has_orphan_label": bool(scan["orphan_labels"]),
        "has_duplicate_image": bool(scan["duplicate_image_groups"]),
        "has_split_leakage": bool(scan["split_leakage_by_name"] or scan["split_leakage_by_hash"]),
        "no_real_object": scan["no_real_object"],
        "has_real_labeled_objects": scan["has_real_labeled_objects"],
        "issues": scan["issues"],
        "consistent_with_historical_408": scan["consistent_with_historical_408"],
        "unreadable_images": scan["unreadable_images"],
    }


def render_dataset_check_md(payload: dict[str, Any]) -> str:
    lines = [
        "# UAV BLB 408 Manual Gate Dataset Check",
        "",
        f"- machine_check: `{payload['machine_check']}`",
        f"- dataset_root: `{payload['dataset_root']}`",
        f"- images_count: `{payload['images_count']}`",
        f"- labels_count: `{payload['labels_count']}`",
        f"- bbox_count: `{payload['bbox_count']}`",
        f"- train_val_test_split: `{payload['train_val_test_split']}`",
        f"- class_id_legal: `{payload['class_id_legal']}`",
        f"- bbox_out_of_bounds: `{payload['bbox_out_of_bounds']}`",
        f"- has_empty_label: `{payload['has_empty_label']}`",
        f"- has_missing_label: `{payload['has_missing_label']}`",
        f"- has_orphan_label: `{payload['has_orphan_label']}`",
        f"- has_duplicate_image: `{payload['has_duplicate_image']}`",
        f"- has_split_leakage: `{payload['has_split_leakage']}`",
        f"- no_real_object: `{payload['no_real_object']}`",
        f"- has_real_labeled_objects: `{payload['has_real_labeled_objects']}`",
        f"- consistent_with_historical_408: `{payload['consistent_with_historical_408']}`",
        "",
        "## Issues",
        "",
    ]
    if payload["issues"]:
        for issue in payload["issues"]:
            lines.append(f"- `{issue['issue']}`: `{issue['count']}`")
    else:
        lines.append("- No machine-check issues found.")
    if payload["unreadable_images"]:
        lines.extend(["", "## Unreadable Images", ""])
        lines.extend(f"- `{item}`" for item in payload["unreadable_images"])
    return "\n".join(lines) + "\n"


def extract_no_detection_names() -> dict[str, set[str]]:
    comparison = read_json(REPORTS / "uav_blb_ab_eval_comparison.json") or {}
    buckets = {
        "ab_eval_no_detection": set(),
        "strict408_no_detection": set(),
        "exp408_no_detection": set(),
    }
    for candidate_key, reason_key in (("candidate_a", "exp408_no_detection"), ("candidate_b", "strict408_no_detection")):
        candidate = comparison.get(candidate_key, {})
        for summary in candidate.get("infer_summary", {}).values():
            names = summary.get("images_with_zero_detection", []) or []
            buckets[reason_key].update(names)
            buckets["ab_eval_no_detection"].update(names)
    return buckets


def extract_hard_case_names() -> set[str]:
    hard_cases: set[str] = set()
    for name in ("uav_blb_zero_detection_error_analysis.md", "uav_blb_hard_case_review_plan.md"):
        path = REPORTS / name
        if path.exists():
            hard_cases.update(re.findall(r"blb_[A-Za-z0-9_]+\.jpg", path.read_text(encoding="utf-8")))
    return hard_cases


def score_record(record: dict[str, Any], no_det: dict[str, set[str]], hard_cases: set[str], common_dim: str | None) -> tuple[int, list[str], list[str], bool]:
    reasons: list[str] = []
    tags: list[str] = []
    image_name = record["image_name"]
    score = 0
    source_ab = False
    for reason, names in no_det.items():
        if image_name in names:
            reasons.append(reason)
            tags.append("no_detection")
            score += 100
            source_ab = True
    if image_name in hard_cases:
        reasons.append("existing_hard_case_review_plan")
        tags.append("hard_case")
        score += 80
    if record["split"] in {"val", "test"}:
        reasons.append(f"{record['split']}_priority")
        tags.append("val_test_priority")
        score += 12
    if record["bbox_count"] >= 9:
        reasons.append("high_bbox_count")
        tags.append("dense_boxes")
        score += 35
    if record["bbox_count"] <= 2:
        reasons.append("low_bbox_count")
        tags.append("sparse_boxes")
        score += 28
    if record["large_bbox_count"] > 0 or record["max_bbox_area"] > 0.12:
        reasons.append("large_bbox_area_abnormal")
        tags.append("large_box")
        score += 30
    if record["small_bbox_count"] >= 3:
        reasons.append("many_small_bboxes")
        tags.append("small_boxes")
        score += 25
    dim = f"{record['image_width']}x{record['image_height']}"
    if common_dim and dim != common_dim:
        reasons.append("image_size_abnormal")
        tags.append("size_outlier")
        score += 18
    if not reasons:
        reasons.append("random_representative")
        tags.append("representative")
    return score, sorted(set(reasons)), sorted(set(tags)), source_ab


def choose_review_items(scan: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    no_det = extract_no_detection_names()
    hard_cases = extract_hard_case_names()
    dim_counts = Counter(scan["image_dimension_distribution"])
    common_dim = dim_counts.most_common(1)[0][0] if dim_counts else None
    scored: list[dict[str, Any]] = []
    for record in scan["records"]:
        score, reasons, tags, source_ab = score_record(record, no_det, hard_cases, common_dim)
        item = dict(record)
        item.update(
            {
                "score": score,
                "selection_reasons": reasons,
                "risk_tags": tags,
                "source_from_ab_eval": source_ab,
            }
        )
        scored.append(item)

    selected: dict[str, dict[str, Any]] = {}
    quotas = {"val": 48, "test": 48, "train": 24}
    for item in sorted(scored, key=lambda row: (-row["source_from_ab_eval"], -row["score"], row["split"], row["image_name"])):
        if item["source_from_ab_eval"] or "existing_hard_case_review_plan" in item["selection_reasons"]:
            selected[item["image_name"]] = item

    for split, quota in quotas.items():
        split_items = [item for item in scored if item["split"] == split]
        split_items.sort(key=lambda row: (-row["score"], row["image_name"]))
        for item in split_items:
            if sum(1 for row in selected.values() if row["split"] == split) >= quota:
                break
            selected[item["image_name"]] = item

    if len(selected) < REVIEW_TARGET:
        rng = random.Random(RANDOM_SEED)
        remaining = [item for item in scored if item["image_name"] not in selected]
        rng.shuffle(remaining)
        for item in remaining:
            selected[item["image_name"]] = item
            if len(selected) >= REVIEW_TARGET:
                break
    elif len(selected) > REVIEW_TARGET:
        forced_names = {
            name
            for names in no_det.values()
            for name in names
        } | hard_cases
        selected_items = list(selected.values())
        selected_items.sort(key=lambda row: (row["image_name"] not in forced_names, -row["score"], row["split"], row["image_name"]))
        selected = {item["image_name"]: item for item in selected_items[:REVIEW_TARGET]}

    ordered = sorted(selected.values(), key=lambda row: ({"val": 0, "test": 1, "train": 2}.get(row["split"], 9), -row["score"], row["image_name"]))
    selected_rows: list[dict[str, Any]] = []
    for idx, item in enumerate(ordered, start=1):
        selected_rows.append(
            {
                "review_id": f"uav_blb_{idx:03d}",
                **item,
            }
        )
    plan = {
        "generated_at": now_iso(),
        "total_candidates": len(scored),
        "selected_review_items": len(selected_rows),
        "split_distribution": dict(Counter(item["split"] for item in selected_rows)),
        "bbox_count_distribution": {
            "min": min((item["bbox_count"] for item in selected_rows), default=0),
            "max": max((item["bbox_count"] for item in selected_rows), default=0),
            "average": round(sum(item["bbox_count"] for item in selected_rows) / len(selected_rows), 4) if selected_rows else 0,
            "low_1_2": sum(1 for item in selected_rows if item["bbox_count"] <= 2),
            "mid_3_8": sum(1 for item in selected_rows if 3 <= item["bbox_count"] <= 8),
            "high_9_plus": sum(1 for item in selected_rows if item["bbox_count"] >= 9),
        },
        "high_risk_reason_counts": dict(Counter(reason for item in selected_rows for reason in item["selection_reasons"] if reason != "random_representative")),
        "no_detection_sample_count": sum(1 for item in selected_rows if item["source_from_ab_eval"]),
        "random_seed": RANDOM_SEED,
        "selection_rules": [
            "Default sample count is 120.",
            "Locked A/B zero-detection and existing hard-case names are forced into the review list when present.",
            "Val/test are prioritized while train remains covered.",
            "High bbox count, low bbox count, large boxes, many small boxes, and image-size outliers receive higher scores.",
            "Remaining slots are filled deterministically with random_seed for representative coverage.",
        ],
        "limitations": [
            "No new inference was run.",
            "No labels or source images were modified.",
            "no_detection tags only come from existing locked A/B artifacts.",
        ],
    }
    return selected_rows, plan


def render_sampling_plan_md(plan: dict[str, Any]) -> str:
    lines = [
        "# UAV BLB 408 Manual Review Sampling Plan",
        "",
        f"- total_candidates: `{plan['total_candidates']}`",
        f"- selected_review_items: `{plan['selected_review_items']}`",
        f"- split_distribution: `{plan['split_distribution']}`",
        f"- bbox_count_distribution: `{plan['bbox_count_distribution']}`",
        f"- high_risk_reason_counts: `{plan['high_risk_reason_counts']}`",
        f"- no_detection_sample_count: `{plan['no_detection_sample_count']}`",
        f"- random_seed: `{plan['random_seed']}`",
        "",
        "## Selection Rules",
        "",
    ]
    lines.extend(f"- {item}" for item in plan["selection_rules"])
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in plan["limitations"])
    return "\n".join(lines) + "\n"


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def draw_overlay(item: dict[str, Any]) -> tuple[str, str | None]:
    image_path: Path = item["image_path"]
    output_path = VISUAL_DIR / f"{Path(item['image_name']).stem}_manual_gate_overlay.jpg"
    try:
        with Image.open(image_path) as source:
            image = source.convert("RGB")
    except Exception as exc:  # noqa: BLE001
        return rel(output_path), str(exc)
    max_width = 1280
    scale = min(1.0, max_width / image.width)
    if scale < 1.0:
        image = image.resize((int(image.width * scale), int(image.height * scale)))
    header_h = 100
    canvas = Image.new("RGB", (image.width, image.height + header_h), (245, 247, 250))
    canvas.paste(image, (0, header_h))
    draw = ImageDraw.Draw(canvas)
    font = load_font(24)
    small = load_font(18)
    title = f"{item['image_name']} | split={item['split']} | bbox_count={item['bbox_count']} | class=bacterial_leaf_blight"
    reason = "reason=" + ",".join(item["selection_reasons"])
    draw.text((16, 12), title, fill=(20, 24, 32), font=font)
    draw.text((16, 56), reason[:160], fill=(64, 72, 86), font=small)
    width, height = item["image_width"] or image.width, item["image_height"] or image.height
    sx = image.width / width
    sy = image.height / height
    colors = [(220, 38, 38), (37, 99, 235), (22, 163, 74), (217, 119, 6)]
    for idx, box in enumerate(item["boxes"]):
        x, y, w, h = box["x"], box["y"], box["w"], box["h"]
        left = (x - w / 2) * width * sx
        top = header_h + (y - h / 2) * height * sy
        right = (x + w / 2) * width * sx
        bottom = header_h + (y + h / 2) * height * sy
        color = colors[idx % len(colors)]
        for offset in range(3):
            draw.rectangle((left - offset, top - offset, right + offset, bottom + offset), outline=color)
        draw.text((left + 3, max(header_h, top - 22)), str(idx + 1), fill=color, font=small)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, quality=92)
    return rel(output_path), None


def build_visuals_and_review_items(selected: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    review_rows: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    unreadable: list[str] = []
    for item in selected:
        preview_path, error = draw_overlay(item)
        if error:
            unreadable.append(item["image_name"])
            if "needs_review" not in item["risk_tags"]:
                item["risk_tags"].append("needs_review")
        row = {
            "review_id": item["review_id"],
            "dataset_name": DATASET_NAME,
            "dataset_root": rel(DATASET_ROOT),
            "split": item["split"],
            "image_name": item["image_name"],
            "image_path": rel(item["image_path"]),
            "label_path": rel(item["label_path"]),
            "visual_preview_path": preview_path,
            "bbox_count": item["bbox_count"],
            "image_width": item["image_width"] or "",
            "image_height": item["image_height"] or "",
            "class_name": "bacterial_leaf_blight",
            "selection_reason": ";".join(item["selection_reasons"]),
            "risk_tags": ";".join(sorted(set(item["risk_tags"]))),
            "source_from_ab_eval": str(bool(item["source_from_ab_eval"])).lower(),
            "old_candidate_status": "active_optional_candidate=experimental_408_epoch5; experimental_reference=strict408_v0_2_controlled",
            "review_status": "unreviewed",
            "issue_type": "",
            "reviewer_notes": "",
            "reviewed_at": "",
        }
        review_rows.append(row)
        manifest.append(
            {
                "review_id": item["review_id"],
                "split": item["split"],
                "image_name": item["image_name"],
                "image_path": rel(item["image_path"]),
                "label_path": rel(item["label_path"]),
                "visual_preview_path": preview_path,
                "bbox_count": item["bbox_count"],
                "class_name": "bacterial_leaf_blight",
                "selection_reason": row["selection_reason"],
                "risk_tags": row["risk_tags"],
                "unreadable_error": error or "",
            }
        )
    return review_rows, manifest, unreadable


def render_visual_index(manifest: list[dict[str, Any]], unreadable: list[str]) -> str:
    lines = [
        "# UAV BLB 408 Manual Gate Visual Audit",
        "",
        f"- generated_at: `{now_iso()}`",
        f"- total_overlay_images: `{len(manifest) - len(unreadable)}`",
        f"- unreadable_images: `{len(unreadable)}`",
        "",
        "| review_id | split | image | bbox_count | reason | preview |",
        "|---|---|---:|---:|---|---|",
    ]
    for row in manifest:
        preview = row["visual_preview_path"]
        lines.append(
            f"| {row['review_id']} | {row['split']} | `{row['image_name']}` | {row['bbox_count']} | "
            f"{row['selection_reason']} | [{Path(preview).name}](./{Path(preview).name}) |"
        )
    if unreadable:
        lines.extend(["", "## Unreadable Images", ""])
        lines.extend(f"- `{name}`" for name in unreadable)
    return "\n".join(lines) + "\n"


def render_review_items_json(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "dataset_name": DATASET_NAME,
        "review_items_count": len(rows),
        "issue_types": {
            "ok": "正常",
            "box_misaligned": "框位置错误",
            "whole_leaf_or_background_box": "整叶/背景大框",
            "irrelevant_box": "无关框",
            "over_fragmented": "过度碎片化",
            "missing_blight_region": "漏标明显病斑",
            "label_noise": "标注噪声",
            "image_label_mismatch": "图像与标签不匹配",
            "uncertain_symptom": "症状不确定",
            "other": "其他",
        },
        "items": rows,
    }


def check_manual_review_status(review_count: int) -> dict[str, Any]:
    decisions_csv = REPORTS / "uav_blb_408_manual_review_decisions.csv"
    decisions_json = REPORTS / "uav_blb_408_manual_review_decisions.json"
    summary_json = REPORTS / "uav_blb_408_manual_review_summary.json"
    gate_report = REPORTS / "uav_blb_408_manual_review_gate_report.md"
    required = [decisions_csv, decisions_json, summary_json, gate_report]
    missing = [rel(path) for path in required if not path.exists()]
    reviewed_count = 0
    gate = "PENDING"
    summary = read_json(summary_json)
    if summary:
        reviewed_count = int(summary.get("reviewed_count", 0) or 0)
        gate = str(summary.get("gate", "PENDING"))
    elif decisions_csv.exists():
        with decisions_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            reviewed_count = sum(1 for row in csv.DictReader(handle) if (row.get("review_status") or "") == "reviewed")
    if missing:
        gate = "PENDING"
        reviewed_count = 0 if decisions_csv in [path for path in required if not path.exists()] else reviewed_count
    elif reviewed_count < review_count:
        gate = "PENDING"
    return {
        "generated_at": now_iso(),
        "manual_gate": gate,
        "review_items_count": review_count,
        "reviewed_count": reviewed_count,
        "remaining_count": max(0, review_count - reviewed_count),
        "training_allowed": False,
        "required_result_files": [rel(path) for path in required],
        "missing_result_files": missing,
        "status": "PENDING" if gate == "PENDING" else gate,
        "reason": "Manual review is not complete; direct training and backend integration remain forbidden.",
    }


def render_status_check_md(status: dict[str, Any]) -> str:
    lines = [
        "# UAV BLB 408 Manual Review Status Check",
        "",
        f"- manual_gate: `{status['manual_gate']}`",
        f"- review_items_count: `{status['review_items_count']}`",
        f"- reviewed_count: `{status['reviewed_count']}`",
        f"- remaining_count: `{status['remaining_count']}`",
        f"- training_allowed: `{status['training_allowed']}`",
        f"- reason: {status['reason']}",
        "",
        "## Missing Result Files",
        "",
    ]
    if status["missing_result_files"]:
        lines.extend(f"- `{path}`" for path in status["missing_result_files"])
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def render_pending_notice(status: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# UAV BLB 408 Pending Manual Review Notice",
            "",
            "- review_launcher: `reports/uav_blb_408_start_manual_review_desktop.bat`",
            f"- review_items_required: `{status['review_items_count']}`",
            f"- reviewed_count: `{status['reviewed_count']}`",
            "- training_allowed: `false`",
            "- backend_integration_allowed: `false`",
            "- next_action: complete the guarded manual review before any controlled training planning decision.",
            "",
        ]
    )


def render_postreview_gate_result(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "dataset_name": DATASET_NAME,
        "manual_gate": status["manual_gate"],
        "reviewed_count": status["reviewed_count"],
        "review_items_count": status["review_items_count"],
        "serious_issue_ratio": None,
        "training_allowed": False,
        "controlled_training_planning_allowed": False,
        "reason": status["reason"],
    }


def write_status_yaml(status: dict[str, Any], machine_check: str) -> None:
    yaml_text = f"""uav_blb_408:
  dataset_root: datasets/rice_uav_ms_blb_preview_1000
  machine_check: {machine_check}
  manual_gate: {status['manual_gate']}
  current_status: manual review assets generated; guarded review pending; training not allowed
  active_optional_candidate: experimental_408_epoch5
  experimental_reference: strict408_v0_2_controlled
  allowed_usage:
    - manual review
    - dataset quality audit
    - controlled training planning if manual_gate PASS
  forbidden_usage:
    - direct training if manual_gate not PASS
    - backend upgrade
    - formal claim
    - pesticide recommendation
  next_action:
    - complete UAV BLB 408 guarded manual review
    - compute manual gate after all review items are reviewed
"""
    atomic_write_text(METADATA / "uav_blb_dataset_status.yaml", yaml_text)


def upsert_section(path: Path, title: str, body: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else f"# {path.stem}\n"
    marker = f"## {title}"
    pattern = re.compile(rf"\n## {re.escape(title)}\n.*?(?=\n## |\Z)", re.S)
    section = f"\n## {title}\n\n{body.strip()}\n"
    if pattern.search(existing):
        updated = pattern.sub(section, existing)
    else:
        updated = existing.rstrip() + "\n" + section
    atomic_write_text(path, updated.rstrip() + "\n")


def sync_boundary_docs(status: dict[str, Any]) -> None:
    shared = "\n".join(
        [
            "- UAV crop_object / rice_panicle are assistive object targets, not disease recognition.",
            "- UAV BLB 408 is the current UAV disease dataset under quality audit.",
            "- Machine-side dataset check is stable for the 408-image / 2373-box scale.",
            f"- UAV BLB 408 manual_gate is currently `{status['manual_gate']}`.",
            "- No training is allowed before the manual gate is complete and PASS.",
            "- Even after PASS, only controlled training planning is allowed in a separate round.",
            "- `strict408_v0_2_controlled` remains an experimental reference, not an active candidate.",
            "- `experimental_408_epoch5` remains the active optional candidate.",
            "- No formal pesticide recommendation should be emitted.",
        ]
    )
    for name in [
        "project_current_model_status_summary.md",
        "demo_model_boundary_statement.md",
        "uav_phone_dual_line_roadmap.md",
        "frontend_demo_model_hint_policy.md",
        "defense_talking_points_model_limitations.md",
    ]:
        upsert_section(REPORTS / name, "UAV BLB 408 Manual Gate Status", shared)


def render_bat() -> str:
    return "\n".join(
        [
            "@echo off",
            "cd /d %~dp0..",
            "python scripts\\launch_uav_blb_408_manual_review_desktop.py",
            "",
        ]
    )


def render_final_report(scan: dict[str, Any], inventory: dict[str, Any], check: dict[str, Any], sampling: dict[str, Any], status: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Thirty Fifth Round A UAV BLB 408 Manual Gate Report",
            "",
            "## Round Goal",
            "",
            "Build the UAV BLB 408 manual-gate evidence chain, stability assessment, guarded review entry, and pre-training decision. No training was executed.",
            "",
            "## Dataset Location",
            "",
            f"- dataset_root: `{inventory['dataset_root']}`",
            f"- data_yaml: `{inventory['data_yaml']}`",
            f"- images / labels / bbox: `{scan['images_count']}` / `{scan['labels_count']}` / `{scan['bbox_count']}`",
            f"- split_distribution: `{scan['split_distribution']}`",
            "",
            "## crop_object / rice_panicle Boundary",
            "",
            "- UAV crop_object and rice_panicle remain assistive object targets, not disease-recognition classes.",
            "- UAV BLB 408 is the current UAV disease dataset for bacterial leaf blight auditing.",
            "",
            "## Machine Check",
            "",
            f"- machine_check: `{check['machine_check']}`",
            f"- issues: `{check['issues']}`",
            f"- consistent_with_historical_408: `{check['consistent_with_historical_408']}`",
            "",
            "## A/B Historical Conclusion",
            "",
            "- Locked A/B found `strict408_v0_2_controlled` has stronger metrics but more zero detections.",
            "- `experimental_408_epoch5` remains the active optional candidate.",
            "- `strict408_v0_2_controlled` remains an experimental reference only.",
            "",
            "## Manual Review Sampling",
            "",
            f"- selected_review_items: `{sampling['selected_review_items']}`",
            f"- split_distribution: `{sampling['split_distribution']}`",
            f"- no_detection_sample_count: `{sampling['no_detection_sample_count']}`",
            f"- sampling_plan: `reports/uav_blb_408_manual_review_sampling_plan.md`",
            "",
            "## Evidence Paths",
            "",
            "- visual_audit: `reports/uav_blb_408_manual_gate_visual_audit/index.md`",
            "- visual_manifest_csv: `reports/uav_blb_408_manual_gate_visual_audit_manifest.csv`",
            "- review_items_csv: `reports/uav_blb_408_manual_review_items.csv`",
            "- review_items_json: `reports/uav_blb_408_manual_review_items.json`",
            "- launcher_selftest: `reports/uav_blb_408_manual_review_launcher_selftest.json`",
            "",
            "## Manual Review Status",
            "",
            f"- manual_gate: `{status['manual_gate']}`",
            f"- reviewed_count: `{status['reviewed_count']}`",
            f"- remaining_count: `{status['remaining_count']}`",
            f"- gate: `{status['manual_gate']}`",
            "",
            "## Boundary Confirmation",
            "",
            "- training_allowed: `false` unless a later completed manual gate is PASS and a separate training plan is opened.",
            "- new_weights_generated: `false`",
            "- labels_modified: `false`",
            "- original_images_modified: `false`",
            "- backend_modified: `false`",
            "- real_env_modified: `false`",
            "- git_add_commit: `false`",
            "",
            "## Next Step",
            "",
            "- Launch `reports/uav_blb_408_start_manual_review_desktop.bat` and complete all review items.",
            "- Recompute the gate after manual decisions exist.",
            "- Keep training and backend integration blocked while manual_gate is PENDING.",
            "",
        ]
    )


def main() -> int:
    scan = scan_dataset()
    inventory = build_inventory(scan)
    check = build_dataset_check(scan)
    selected, sampling = choose_review_items(scan)
    review_rows, manifest, unreadable = build_visuals_and_review_items(selected)

    atomic_write_json(REPORTS / "uav_blb_408_current_asset_inventory.json", inventory)
    atomic_write_text(REPORTS / "uav_blb_408_current_asset_inventory.md", render_inventory_md(inventory))
    atomic_write_json(REPORTS / "uav_blb_408_manual_gate_dataset_check.json", check)
    atomic_write_text(REPORTS / "uav_blb_408_manual_gate_dataset_check.md", render_dataset_check_md(check))
    atomic_write_json(REPORTS / "uav_blb_408_manual_review_sampling_plan.json", sampling)
    atomic_write_text(REPORTS / "uav_blb_408_manual_review_sampling_plan.md", render_sampling_plan_md(sampling))
    atomic_write_text(VISUAL_DIR / "index.md", render_visual_index(manifest, unreadable))
    atomic_write_csv(REPORTS / "uav_blb_408_manual_gate_visual_audit_manifest.csv", manifest, list(manifest[0].keys()))
    atomic_write_json(REPORTS / "uav_blb_408_manual_gate_visual_audit_manifest.json", {"generated_at": now_iso(), "items": manifest, "unreadable_images": unreadable})
    review_fields = [
        "review_id",
        "dataset_name",
        "dataset_root",
        "split",
        "image_name",
        "image_path",
        "label_path",
        "visual_preview_path",
        "bbox_count",
        "image_width",
        "image_height",
        "class_name",
        "selection_reason",
        "risk_tags",
        "source_from_ab_eval",
        "old_candidate_status",
        "review_status",
        "issue_type",
        "reviewer_notes",
        "reviewed_at",
    ]
    atomic_write_csv(REPORTS / "uav_blb_408_manual_review_items.csv", review_rows, review_fields)
    atomic_write_json(REPORTS / "uav_blb_408_manual_review_items.json", render_review_items_json(review_rows))
    atomic_write_text(REPORTS / "uav_blb_408_start_manual_review_desktop.bat", render_bat())

    status = check_manual_review_status(len(review_rows))
    atomic_write_json(REPORTS / "uav_blb_408_manual_review_status_check.json", status)
    atomic_write_text(REPORTS / "uav_blb_408_manual_review_status_check.md", render_status_check_md(status))
    atomic_write_text(REPORTS / "uav_blb_408_pending_manual_review_notice.md", render_pending_notice(status))
    post_gate = render_postreview_gate_result(status)
    atomic_write_json(REPORTS / "uav_blb_408_postreview_gate_result.json", post_gate)
    atomic_write_text(REPORTS / "uav_blb_408_postreview_gate_result.md", render_status_check_md({**status, "reason": post_gate["reason"]}))
    write_status_yaml(status, check["machine_check"])
    sync_boundary_docs(status)
    atomic_write_text(REPORTS / "thirty_fifth_round_a_uav_blb_408_manual_gate_report.md", render_final_report(scan, inventory, check, sampling, status))
    print(json.dumps({"review_items": len(review_rows), "machine_check": check["machine_check"], "manual_gate": status["manual_gate"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
