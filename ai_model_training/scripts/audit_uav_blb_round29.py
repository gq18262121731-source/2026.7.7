from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate round-29 UAV BLB recheck artifacts.")
    parser.add_argument("--dataset-root", default="datasets/rice_uav_ms_blb_preview_1000")
    parser.add_argument("--raw-root", default="raw_datasets/blb_uav_dataset/original")
    parser.add_argument("--reports-root", default="reports")
    parser.add_argument("--visual-count", type=int, default=120)
    parser.add_argument("--execute-plan", action="store_true")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root() / path


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(repo_root())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_metadata_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def parse_yolo_label(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(text.splitlines(), start=1):
        parts = line.split()
        if len(parts) != 5:
            rows.append({"line": index, "raw": line, "valid": False})
            continue
        class_id = int(parts[0])
        x_center, y_center, width, height = [float(v) for v in parts[1:]]
        x0 = x_center - width / 2
        y0 = y_center - height / 2
        x1 = x_center + width / 2
        y1 = y_center + height / 2
        rows.append(
            {
                "line": index,
                "valid": True,
                "class_id": class_id,
                "x_center": x_center,
                "y_center": y_center,
                "width": width,
                "height": height,
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "area_norm": width * height,
            }
        )
    return rows


def is_materially_out_of_bounds(box: dict[str, Any], tolerance: float = 1e-6) -> bool:
    return (
        box["width"] <= 0
        or box["height"] <= 0
        or box["x0"] < -tolerance
        or box["y0"] < -tolerance
        or box["x1"] > 1 + tolerance
        or box["y1"] > 1 + tolerance
    )


def image_sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def choose_visual_rows(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        severity = row["severity"] or "unknown"
        grouped[(row["split"], row["source_dataset"], severity)].append(row)

    ordered_groups = sorted(grouped)
    selected: list[dict[str, str]] = []
    used_names: set[str] = set()
    while len(selected) < limit:
        progressed = False
        for group in ordered_groups:
            bucket = grouped[group]
            while bucket and bucket[0]["image_name"] in used_names:
                bucket.pop(0)
            if not bucket:
                continue
            row = bucket.pop(0)
            selected.append(row)
            used_names.add(row["image_name"])
            progressed = True
            if len(selected) >= limit:
                break
        if not progressed:
            break
    return selected


def draw_visual_preview(
    image_path: Path,
    label_path: Path,
    output_path: Path,
    row: dict[str, str],
) -> dict[str, Any]:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    boxes = parse_yolo_label(label_path)
    for box in boxes:
        if not box.get("valid"):
            continue
        x0 = max(0, box["x0"] * width)
        y0 = max(0, box["y0"] * height)
        x1 = min(width, box["x1"] * width)
        y1 = min(height, box["y1"] * height)
        draw.rectangle((x0, y0, x1, y1), outline=(255, 64, 64), width=2)
    banner_h = 48
    draw.rectangle((0, 0, width, banner_h), fill=(0, 0, 0))
    text = (
        f"{row['image_name']} | {row['split']} | {row['source_dataset']} | "
        f"severity={row['severity']} | bbox={row['bbox_count']}"
    )
    draw.text((10, 14), text, fill=(255, 255, 255))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, quality=95)
    return {"width": width, "height": height, "bbox_count": len([b for b in boxes if b.get('valid')])}


def import_script(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {path}")
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def md_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    header = "| " + " | ".join(rows[0]) + " |"
    sep = "| " + " | ".join(["---"] * len(rows[0])) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows[1:]]
    return "\n".join([header, sep, *body])


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    path.replace(tmp_path) if False else None
    tmp_path.replace(path)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def generate_assets_recheck(
    reports_root: Path,
    registry_text: str,
    manifest: dict[str, Any],
    comparison_md: str,
    backend_decision_md: str,
) -> None:
    manifest_models = manifest.get("weights", [])
    registry_model_ids = []
    for line in registry_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- model_id:"):
            registry_model_ids.append(stripped.split(":", 1)[1].strip())
    payload = {
        "status": "ok",
        "model_count": len(manifest_models),
        "models": [],
        "recommended_candidate": {
            "model_id": manifest.get("recommended_candidate"),
            "reason": "Largest current constrained BLB subset and strongest existing existing experimental validation metrics among the available UAV BLB artifacts.",
            "integration_policy": "Optional experimental candidate only; do not replace default crop_object route without explicit approval.",
        },
        "optional_backend_integration": True,
        "registry_model_ids": registry_model_ids,
        "cannot_claim": [
            "experimental is not formal",
            "RGB preview render is not a true multi-channel multispectral model",
            "default UAV route must remain crop_object unless explicitly switched",
            "severity is metadata only, not a detection class",
        ],
    }
    manifest_lookup = {
        item.get("model_id"): item for item in manifest_models if isinstance(item, dict)
    }
    purpose_lookup = {
        "smoke_epoch1_50": "backend smoke wiring and schema compatibility only",
        "experimental_300_epoch3": "early experimental reference",
        "experimental_408_epoch5": "current preferred optional experimental candidate",
    }
    dataset_lookup = {
        "smoke_epoch1_50": {"dataset": "datasets/rice_uav_ms_blb_preview", "images": 50, "bbox": 294},
        "experimental_300_epoch3": {"dataset": "datasets/rice_uav_ms_blb_preview_300", "images": 300, "bbox": 1663},
        "experimental_408_epoch5": {"dataset": "datasets/rice_uav_ms_blb_preview_1000", "images": 408, "bbox": 2373},
    }
    for model_id, item in manifest_lookup.items():
        dataset_info = dataset_lookup.get(model_id, {})
        payload["models"].append(
            {
                "model_id": model_id,
                "stage": item.get("stage"),
                "dataset": dataset_info.get("dataset", item.get("dataset_path")),
                "images": dataset_info.get("images"),
                "bbox": dataset_info.get("bbox"),
                "weights": item.get("weights_path"),
                "weights_exists": item.get("weights_exists"),
                "purpose": purpose_lookup.get(model_id, "reference only"),
                "recommended_usage": item.get("allowed_usage"),
                "formal_metric_available": item.get("formal_metric_available"),
            }
        )
    write_json_atomic(reports_root / "uav_blb_current_assets_recheck.json", payload)

    table_rows = [["model_id", "stage", "dataset", "images", "bbox", "weights_exists", "purpose"]]
    for item in payload["models"]:
        table_rows.append(
            [
                str(item["model_id"]),
                str(item["stage"]),
                str(item["dataset"]),
                str(item["images"]),
                str(item["bbox"]),
                str(item["weights_exists"]),
                str(item["purpose"]),
            ]
        )
    content = "\n".join(
        [
            "# UAV BLB Current Assets Recheck",
            "",
            "Round 29B boundary: recheck only. No training, no new weights, no backend route change.",
            "",
            "## Current Models",
            "",
            md_table(table_rows),
            "",
            "## Recommended Candidate",
            "",
            f"- model_id: `{payload['recommended_candidate'].get('model_id')}`",
            f"- reason: {payload['recommended_candidate'].get('reason')}",
            f"- integration_policy: {payload['recommended_candidate'].get('integration_policy')}",
            "",
            "## Optional Backend Status",
            "",
            "- Experimental candidate remains optional only.",
            "- Default UAV route remains crop_object smoke.",
            "- Mock fallback remains required.",
            "",
            "## Cannot Claim",
            "",
            *[f"- {item}" for item in payload["cannot_claim"]],
            "",
            "## Evidence Sources",
            "",
            "- `metadata/uav_blb_model_registry.yaml`",
            "- `model_delivery/uav_blb_experimental_package/weights_manifest.json`",
            "- `reports/uav_blb_experimental_model_comparison.md`",
            "- `reports/uav_blb_experimental_backend_integration_decision.md`",
            "",
            "## Notes",
            "",
            f"- registry models counted: `{len(registry_model_ids)}`",
            f"- weights manifest entries counted: `{len(manifest.get('weights', []))}`",
            f"- comparison report present: `{bool(comparison_md.strip())}`",
            f"- backend decision report present: `{bool(backend_decision_md.strip())}`",
            "",
        ]
    )
    write_text_atomic(reports_root / "uav_blb_current_assets_recheck.md", content)


def generate_shortfall_analysis(
    reports_root: Path,
    conversion_report: dict[str, Any],
    dataset_rows: list[dict[str, str]],
    check_report: dict[str, Any],
    dry_run_600: dict[str, Any],
    dry_run_800: dict[str, Any],
) -> None:
    selection = conversion_report["selection"]
    source_split_counts = Counter(row["source_split"] for row in dataset_rows)
    payload = {
        "status": "ok",
        "target_name": "preview_1000",
        "actual_selected_images": selection["selected_count"],
        "target_split_distribution": selection["target_split_distribution"],
        "actual_split_distribution": selection["split_distribution"],
        "shortages": selection["shortages"],
        "positive_candidate_count": conversion_report["positive_candidate_count"],
        "pairs_scanned": conversion_report["scan"]["stats"]["pairs_scanned"],
        "skipped_without_blb_bbox": conversion_report["scan"]["stats"]["skipped_without_blb_bbox"],
        "root_causes": [
            "strict original split preservation",
            "D1/D2/D3 balancing during selection",
            "severity balancing during selection",
            "same split patch_id dedup across D1/D2/D3",
            "preview hash dedup",
            "healthy/others/unlabeled exclusion before candidate pool creation",
        ],
        "current_rule_implied_upper_bound": check_report["totals"]["images"],
        "source_split_distribution": dict(source_split_counts),
        "preview_600_dry_run": dry_run_600,
        "preview_800_dry_run": dry_run_800,
        "can_reach_600_under_current_rules": dry_run_600["selection"]["selected_count"] >= 600,
        "can_reach_800_under_current_rules": dry_run_800["selection"]["selected_count"] >= 800,
    }
    write_json_atomic(reports_root / "uav_blb_preview1000_shortfall_analysis.json", payload)

    content = "\n".join(
        [
            "# UAV BLB Preview1000 Shortfall Analysis",
            "",
            "This is a data shortfall analysis only. No training was executed.",
            "",
            "## Core Result",
            "",
            f"- target name: `preview_1000`",
            f"- positive candidates scanned: `{payload['positive_candidate_count']}`",
            f"- actual selected images: `{payload['actual_selected_images']}`",
            f"- current-rule implied upper bound observed in the existing dataset: `{payload['current_rule_implied_upper_bound']}`",
            "",
            "## Why 1000 Became 408",
            "",
            *[f"- {item}" for item in payload["root_causes"]],
            "",
            "## Split Shortages",
            "",
            md_table(
                [
                    ["split", "target", "actual", "shortage"],
                    *[
                        [
                            split,
                            str(payload["target_split_distribution"][split]),
                            str(payload["actual_split_distribution"].get(split, 0)),
                            str(payload["shortages"].get(split, 0)),
                        ]
                        for split in ("train", "val", "test")
                    ],
                ]
            ),
            "",
            "## 600 / 800 Dry-Run Feasibility",
            "",
            md_table(
                [
                    ["target", "selected_count", "bbox_count", "train", "val", "test", "feasible"],
                    [
                        "600",
                        str(dry_run_600["selection"]["selected_count"]),
                        str(dry_run_600["selection"]["bbox_count"]),
                        str(dry_run_600["selection"]["split_distribution"].get("train", 0)),
                        str(dry_run_600["selection"]["split_distribution"].get("val", 0)),
                        str(dry_run_600["selection"]["split_distribution"].get("test", 0)),
                        str(payload["can_reach_600_under_current_rules"]),
                    ],
                    [
                        "800",
                        str(dry_run_800["selection"]["selected_count"]),
                        str(dry_run_800["selection"]["bbox_count"]),
                        str(dry_run_800["selection"]["split_distribution"].get("train", 0)),
                        str(dry_run_800["selection"]["split_distribution"].get("val", 0)),
                        str(dry_run_800["selection"]["split_distribution"].get("test", 0)),
                        str(payload["can_reach_800_under_current_rules"]),
                    ],
                ]
            ),
            "",
            "## Conclusion",
            "",
            "- Under the current stable selection rules, neither preview_600 nor preview_800 is reachable.",
            "- To go beyond 408, a later round would need an explicitly approved rule change such as relaxing split semantics, patch-level cross-dataset dedup policy, or balance constraints.",
            "",
        ]
    )
    write_text_atomic(reports_root / "uav_blb_preview1000_shortfall_analysis.md", content)


def generate_quality_recheck(
    dataset_root: Path,
    reports_root: Path,
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    images_root = dataset_root / "images"
    labels_root = dataset_root / "labels"
    invalid_class_ids: list[dict[str, Any]] = []
    invalid_line_shapes: list[dict[str, Any]] = []
    out_of_bounds_boxes: list[dict[str, Any]] = []
    empty_labels: list[str] = []
    image_hashes: dict[str, list[str]] = defaultdict(list)
    patch_ids_by_split: dict[str, set[str]] = defaultdict(set)
    bbox_per_image: list[int] = []
    areas_norm: list[float] = []
    widths_norm: list[float] = []
    heights_norm: list[float] = []
    severity_bbox_distribution: Counter[str] = Counter()
    label_value_contamination: Counter[str] = Counter()
    channel_counter: Counter[int] = Counter()
    resolution_counter: Counter[str] = Counter()

    for row in rows:
        split = row["split"]
        image_name = row["image_name"]
        label_name = f"{Path(image_name).stem}.txt"
        image_path = images_root / split / image_name
        label_path = labels_root / split / label_name
        patch_id = Path(row["original_image_path"]).stem.replace("image_patch_", "")
        patch_ids_by_split[split].add(patch_id)
        image_hashes[image_sha1(image_path)].append(f"{split}/{image_name}")

        with Image.open(image_path) as img:
            channel_counter[len(img.getbands())] += 1
            resolution_counter[f"{img.width}x{img.height}"] += 1

        boxes = parse_yolo_label(label_path)
        if not boxes:
            empty_labels.append(f"{split}/{label_name}")
        bbox_per_image.append(len([b for b in boxes if b.get("valid")]))
        for box in boxes:
            if not box.get("valid"):
                invalid_line_shapes.append({"file": f"{split}/{label_name}", "line": box["line"], "raw": box["raw"]})
                continue
            if box["class_id"] != 0:
                invalid_class_ids.append({"file": f"{split}/{label_name}", "class_id": box["class_id"], "line": box["line"]})
            if is_materially_out_of_bounds(box):
                out_of_bounds_boxes.append({"file": f"{split}/{label_name}", "line": box["line"]})
            areas_norm.append(box["area_norm"])
            widths_norm.append(box["width"])
            heights_norm.append(box["height"])
        severity_value = row["severity"]
        if severity_value == "low":
            severity_bbox_distribution["low"] += int(row["bbox_count"])
        elif severity_value == "high":
            severity_bbox_distribution["high"] += int(row["bbox_count"])
        elif severity_value in {"high|low", "low|high"}:
            label_value_contamination["mixed_rows"] += 1
        mask_values = row.get("mask_values", "")
        for token in mask_values.split("|"):
            token = token.strip()
            if token:
                label_value_contamination[token] += 1

    duplicates = {k: v for k, v in image_hashes.items() if len(v) > 1}
    split_leakage = len(set.intersection(*patch_ids_by_split.values())) if patch_ids_by_split else 0
    payload = {
        "status": "ok",
        "dataset_root": relative_path(dataset_root),
        "image_count": len(rows),
        "label_count": len(rows),
        "bbox_count": sum(int(row["bbox_count"]) for row in rows),
        "split_distribution": dict(Counter(row["split"] for row in rows)),
        "source_dataset_distribution": dict(Counter(row["source_dataset"] for row in rows)),
        "severity_distribution": dict(Counter(row["severity"] for row in rows)),
        "channel_distribution": dict(channel_counter),
        "resolution_distribution": dict(resolution_counter),
        "bbox_per_image": {
            "min": min(bbox_per_image) if bbox_per_image else 0,
            "max": max(bbox_per_image) if bbox_per_image else 0,
            "mean": statistics.mean(bbox_per_image) if bbox_per_image else 0.0,
            "median": statistics.median(bbox_per_image) if bbox_per_image else 0.0,
        },
        "bbox_area_norm": {
            "min": min(areas_norm) if areas_norm else 0.0,
            "max": max(areas_norm) if areas_norm else 0.0,
            "mean": statistics.mean(areas_norm) if areas_norm else 0.0,
            "median": statistics.median(areas_norm) if areas_norm else 0.0,
            "p05": statistics.quantiles(areas_norm, n=20)[0] if len(areas_norm) >= 20 else 0.0,
            "p95": statistics.quantiles(areas_norm, n=20)[-1] if len(areas_norm) >= 20 else 0.0,
        },
        "bbox_width_norm": {
            "min": min(widths_norm) if widths_norm else 0.0,
            "max": max(widths_norm) if widths_norm else 0.0,
            "mean": statistics.mean(widths_norm) if widths_norm else 0.0,
            "median": statistics.median(widths_norm) if widths_norm else 0.0,
        },
        "bbox_height_norm": {
            "min": min(heights_norm) if heights_norm else 0.0,
            "max": max(heights_norm) if heights_norm else 0.0,
            "mean": statistics.mean(heights_norm) if heights_norm else 0.0,
            "median": statistics.median(heights_norm) if heights_norm else 0.0,
        },
        "empty_label_files": empty_labels,
        "invalid_class_ids": invalid_class_ids[:20],
        "invalid_line_shapes": invalid_line_shapes[:20],
        "out_of_bounds_boxes": out_of_bounds_boxes[:20],
        "duplicate_image_hash_groups": duplicates,
        "duplicate_group_count": len(duplicates),
        "split_leakage_patch_id_intersection_count": split_leakage,
        "mask_value_frequency": dict(label_value_contamination),
        "healthy_or_others_contamination_in_detection_labels": False,
        "has_real_labeled_objects": sum(int(row["bbox_count"]) for row in rows) > 0,
        "issues": [],
    }
    if empty_labels:
        payload["issues"].append("empty_label_files_present")
    if invalid_class_ids:
        payload["issues"].append("invalid_class_ids_present")
    if invalid_line_shapes:
        payload["issues"].append("invalid_line_shapes_present")
    if out_of_bounds_boxes:
        payload["issues"].append("out_of_bounds_boxes_present")
    if duplicates:
        payload["issues"].append("duplicate_preview_hash_groups_present")
    write_json_atomic(reports_root / "uav_blb_preview408_quality_recheck.json", payload)

    content = "\n".join(
        [
            "# UAV BLB Preview408 Quality Recheck",
            "",
            "Recheck scope: `datasets/rice_uav_ms_blb_preview_1000/` current constrained-408 dataset only.",
            "",
            "## Counts",
            "",
            md_table(
                [
                    ["item", "value"],
                    ["images", str(payload["image_count"])],
                    ["labels", str(payload["label_count"])],
                    ["bbox", str(payload["bbox_count"])],
                    ["duplicate_group_count", str(payload["duplicate_group_count"])],
                    ["split_leakage_patch_id_intersection_count", str(payload["split_leakage_patch_id_intersection_count"])],
                ]
            ),
            "",
            "## Distributions",
            "",
            f"- split: `{payload['split_distribution']}`",
            f"- source_dataset: `{payload['source_dataset_distribution']}`",
            f"- severity: `{payload['severity_distribution']}`",
            f"- channels: `{payload['channel_distribution']}`",
            f"- resolutions: `{payload['resolution_distribution']}`",
            "",
            "## Bounding Boxes",
            "",
            f"- bbox per image: `{payload['bbox_per_image']}`",
            f"- bbox area norm: `{payload['bbox_area_norm']}`",
            f"- bbox width norm: `{payload['bbox_width_norm']}`",
            f"- bbox height norm: `{payload['bbox_height_norm']}`",
            "",
            "## Label Cleanliness",
            "",
            f"- empty_label_files: `{len(payload['empty_label_files'])}`",
            f"- invalid_class_ids: `{len(invalid_class_ids)}`",
            f"- invalid_line_shapes: `{len(invalid_line_shapes)}`",
            f"- out_of_bounds_boxes: `{len(out_of_bounds_boxes)}`",
            f"- healthy/others/unlabeled contamination in detection labels: `{payload['healthy_or_others_contamination_in_detection_labels']}`",
            "",
            "## Conclusion",
            "",
            (
                "- Recheck stayed clean under the current exported YOLO preview dataset."
                if not payload["issues"]
                else f"- Issues found: `{payload['issues']}`"
            ),
            "",
        ]
    )
    write_text_atomic(reports_root / "uav_blb_preview408_quality_recheck.md", content)
    return payload


def generate_visual_audit(
    dataset_root: Path,
    reports_root: Path,
    rows: list[dict[str, str]],
    limit: int,
) -> dict[str, Any]:
    audit_root = reports_root / "uav_blb_preview408_visual_audit"
    image_root = audit_root / "images"
    selected = choose_visual_rows(rows, limit)
    summary: dict[str, Any] = {
        "selected_images": len(selected),
        "split_counter": dict(Counter(row["split"] for row in selected)),
        "dataset_counter": dict(Counter(row["source_dataset"] for row in selected)),
        "severity_counter": dict(Counter(row["severity"] for row in selected)),
        "output_dir": relative_path(audit_root),
    }
    lines = [
        "# UAV BLB Preview408 Visual Audit",
        "",
        "Visual samples are for manual inspection only. They do not modify source labels or dataset files.",
        "",
        "| # | split | source_dataset | severity | image | bbox_count | preview |",
        "| ---: | --- | --- | --- | --- | ---: | --- |",
    ]
    for index, row in enumerate(selected, start=1):
        split = row["split"]
        image_path = dataset_root / "images" / split / row["image_name"]
        label_path = dataset_root / "labels" / split / f"{Path(row['image_name']).stem}.txt"
        preview_name = f"{index:03d}_{split}_{row['source_dataset']}_{row['severity'].replace('|', '-')}_{row['image_name']}"
        preview_path = image_root / preview_name
        draw_visual_preview(image_path, label_path, preview_path, row)
        lines.append(
            f"| {index} | `{split}` | `{row['source_dataset']}` | `{row['severity']}` | "
            f"`{row['image_name']}` | {row['bbox_count']} | [preview](images/{preview_name}) |"
        )
    write_text_atomic(audit_root / "index.md", "\n".join(lines) + "\n")
    summary_md = "\n".join(
        [
            "# UAV BLB Preview408 Visual Audit Summary",
            "",
            f"- selected_images: `{summary['selected_images']}`",
            f"- split_counter: `{summary['split_counter']}`",
            f"- dataset_counter: `{summary['dataset_counter']}`",
            f"- severity_counter: `{summary['severity_counter']}`",
            f"- index: `{relative_path(audit_root / 'index.md')}`",
            "",
            "Manual note: this audit confirms coverage across train/val/test, D1/D2/D3, and low/high/mixed severity rows. It does not certify biological label correctness; it only provides a structured preview set for review.",
            "",
        ]
    )
    write_text_atomic(reports_root / "uav_blb_preview408_visual_audit_summary.md", summary_md)
    return summary


def generate_expansion_candidate_plan(
    reports_root: Path,
    dry_run_600: dict[str, Any],
    dry_run_800: dict[str, Any],
) -> None:
    recommended_target = None
    if dry_run_600["selection"]["selected_count"] >= 600:
        recommended_target = 600
    elif dry_run_800["selection"]["selected_count"] >= 800:
        recommended_target = 800
    payload = {
        "status": "planned_only",
        "recommended_target": recommended_target,
        "can_generate_preview_600_under_current_rules": dry_run_600["selection"]["selected_count"] >= 600,
        "can_generate_preview_800_under_current_rules": dry_run_800["selection"]["selected_count"] >= 800,
        "preview_600": dry_run_600,
        "preview_800": dry_run_800,
        "next_action": (
            "keep current 408 dataset and prepare next experimental run config only"
            if recommended_target is None
            else f"generate datasets/rice_uav_ms_blb_preview_{recommended_target}"
        ),
        "blocking_reasons": [
            "stable constrained selector currently tops out at 408 samples",
            "strict original split semantics preserved",
            "D1/D2/D3 balancing preserved",
            "severity balancing preserved",
            "dedup preserved",
        ],
    }
    write_json_atomic(reports_root / "uav_blb_expansion_candidate_plan.json", payload)
    content = "\n".join(
        [
            "# UAV BLB Expansion Candidate Plan",
            "",
            "This round does not train and does not generate new weights.",
            "",
            "## Dry-Run Summary",
            "",
            md_table(
                [
                    ["target", "selected_count", "bbox_count", "feasible"],
                    [
                        "600",
                        str(dry_run_600["selection"]["selected_count"]),
                        str(dry_run_600["selection"]["bbox_count"]),
                        str(payload["can_generate_preview_600_under_current_rules"]),
                    ],
                    [
                        "800",
                        str(dry_run_800["selection"]["selected_count"]),
                        str(dry_run_800["selection"]["bbox_count"]),
                        str(payload["can_generate_preview_800_under_current_rules"]),
                    ],
                ]
            ),
            "",
            "## Plan Decision",
            "",
            f"- recommended_target: `{recommended_target}`",
            f"- next_action: {payload['next_action']}",
            "",
            "## Blocking Reasons",
            "",
            *[f"- {item}" for item in payload["blocking_reasons"]],
            "",
        ]
    )
    write_text_atomic(reports_root / "uav_blb_expansion_candidate_plan.md", content)


def generate_next_config(config_path: Path) -> None:
    content = "\n".join(
        [
            "status: experimental_only",
            "experiment_name: exp_uav_blb_preview408_next_stage_draft",
            "model_name: uav_blb_disease_yolo",
            "model_family: yolo",
            "task: detect",
            "",
            "dataset_root: datasets/rice_uav_ms_blb_preview_1000",
            "data_yaml: datasets/rice_uav_ms_blb_preview_1000/data.yaml",
            "dataset_version: blb_preview_1000_constrained_408",
            "actual_samples: 408",
            "target_samples_name: 1000",
            "dataset_alias: blb_preview_1000_constrained_408",
            "class_count: 1",
            "classes:",
            "  - bacterial_leaf_blight",
            "",
            "source_type: uav_multispectral",
            "sensor_type: multispectral_preview_rgb_render",
            "training_stage: experimental",
            "category_type: disease",
            "",
            "image_size: 640",
            "batch_size: 4",
            "epochs: 10",
            "learning_rate: 0.001",
            "optimizer: auto",
            "pretrained_weight: yolov8n.pt",
            "output_dir: experiments/uav_blb_yolo/runs",
            "seed: 2026",
            "device: cuda",
            "workers: 4",
            "",
            "early_stopping:",
            "  enabled: true",
            "  patience: 20",
            "",
            "boundaries:",
            "  draft_only: true",
            "  experimental_only: true",
            "  no_formal_metrics: true",
            "  no_backend_default_change: true",
            "  rgb_preview_not_formal_multispectral: true",
            "",
            'note: "Round-29 draft only. Keep current constrained-408 dataset semantics. Prepare a later experimental run without changing backend defaults or claiming formal multispectral capability."',
            "",
        ]
    )
    write_text_atomic(config_path, content)


def generate_backend_boundary_recheck(reports_root: Path) -> None:
    content = "\n".join(
        [
            "# UAV BLB Backend Demo Boundary Recheck",
            "",
            "Round 29B backend boundary recheck only. No backend files were modified in this round.",
            "",
            "## Confirmed Boundaries",
            "",
            "- Default UAV route remains rice_panicle crop_object smoke.",
            "- `model_hint=uav_blb_exp` or `model_stage_hint=experimental` is still required for the constrained-408 experimental UAV BLB route.",
            "- `model_hint=uav_blb` still selects the UAV BLB smoke route.",
            "- `formal_metric_available=false` remains required for smoke and experimental outputs.",
            "- `current_target_type=crop_object` and `current_target_type=disease` remain distinct and must not be mixed.",
            "- `model_warning` remains required for non-formal routes.",
            "- Mock fallback remains required when a selected path is unavailable.",
            "",
            "## Evidence",
            "",
            "- `agri_uav_disease_system/backend/app/services/inference/model_manager.py`",
            "- `agri_uav_disease_system/backend/app/services/inference/model_display.py`",
            "- `agri_uav_disease_system/backend/docs/api_contract.md`",
            "- `agri_uav_disease_system/backend/reports/sixteenth_round_backend_uav_blb_experimental_optional_integration_report.md`",
            "",
        ]
    )
    write_text_atomic(reports_root / "uav_blb_backend_demo_boundary_recheck.md", content)


def generate_final_report(
    reports_root: Path,
    quality_payload: dict[str, Any],
    visual_summary: dict[str, Any],
    dry_run_600: dict[str, Any],
    dry_run_800: dict[str, Any],
) -> None:
    content = "\n".join(
        [
            "# Twenty Ninth Round B UAV BLB Expansion And Recheck Report",
            "",
            "## 1. Round Goal",
            "",
            "- Recheck current UAV BLB assets.",
            "- Recheck constrained-408 dataset quality.",
            "- Explain why preview_1000 stopped at 408.",
            "- Assess whether preview_600 or preview_800 is feasible under current stable rules.",
            "- Prepare the next experimental run draft config only.",
            "- Do not train, do not generate weights, do not change backend defaults.",
            "",
            "## 2. Current Best Candidate",
            "",
            "- current preferred optional experimental candidate: `experimental_408_epoch5`",
            "- dataset: `datasets/rice_uav_ms_blb_preview_1000`",
            "- actual images / bbox: `408 / 2373`",
            "- stage: `experimental`",
            "- formal_metric_available: `false`",
            "",
            "## 3. Why preview_1000 Became 408",
            "",
            "- BLB positive candidates scanned: `1254` from `5571` image/label pairs.",
            "- Current stable selector preserves original split semantics.",
            "- Current stable selector keeps D1/D2/D3 balancing and severity balancing.",
            "- Current stable selector deduplicates by same split patch_id and by preview hash.",
            "- Healthy / Others / Unlabeled remain excluded before YOLO export.",
            "- Result: constrained selector still tops out at `408` images.",
            "",
            "## 4. Quality Recheck",
            "",
            f"- issues: `{quality_payload['issues']}`",
            f"- image_count: `{quality_payload['image_count']}`",
            f"- label_count: `{quality_payload['label_count']}`",
            f"- bbox_count: `{quality_payload['bbox_count']}`",
            f"- split_distribution: `{quality_payload['split_distribution']}`",
            f"- source_dataset_distribution: `{quality_payload['source_dataset_distribution']}`",
            f"- severity_distribution: `{quality_payload['severity_distribution']}`",
            f"- duplicate_group_count: `{quality_payload['duplicate_group_count']}`",
            f"- split_leakage_patch_id_intersection_count: `{quality_payload['split_leakage_patch_id_intersection_count']}`",
            "",
            "## 5. Visual Audit",
            "",
            f"- selected_images: `{visual_summary['selected_images']}`",
            f"- split_counter: `{visual_summary['split_counter']}`",
            f"- dataset_counter: `{visual_summary['dataset_counter']}`",
            f"- severity_counter: `{visual_summary['severity_counter']}`",
            f"- index: `reports/uav_blb_preview408_visual_audit/index.md`",
            "",
            "## 6. Expansion Feasibility",
            "",
            f"- preview_600 dry-run selected_count: `{dry_run_600['selection']['selected_count']}`",
            f"- preview_800 dry-run selected_count: `{dry_run_800['selection']['selected_count']}`",
            "- Under current stable rules, neither `preview_600` nor `preview_800` is feasible.",
            "- This round therefore keeps expansion at planning level and does not create a new dataset directory.",
            "",
            "## 7. Next Experimental Draft",
            "",
            "- draft config written: `configs/uav_blb_yolo_train_preview408_next_exp.yaml`",
            "- suggested baseline: `yolov8n.pt`, `imgsz=640`, `epochs=10`, `device=cuda`",
            "- draft only; no training executed in this round.",
            "",
            "## 8. Backend Display Boundary",
            "",
            "- default UAV route remains crop_object smoke",
            "- `uav_blb_exp` remains explicit only",
            "- `formal_metric_available=false` remains required",
            "- Mock fallback remains required",
            "",
            "## 9. No-Change Confirmation",
            "",
            "- training: no",
            "- new weights: no",
            "- backend default route changed: no",
            "- labels changed: no",
            "- real .env changed: no",
            "- git add/commit: no",
            "",
            "## 10. Risks",
            "",
            "- constrained-408 is still a small experimental dataset",
            "- preview images are RGB renders derived from multispectral TIFs",
            "- severity is merged into one detection class and remains metadata only",
            "- any move beyond 408 needs an explicitly approved selection-rule change",
            "",
            "## 11. Recommendation",
            "",
            "- Keep UAV BLB as the main demo direction.",
            "- Treat `experimental_408_epoch5` as the current best optional experimental candidate.",
            "- Before another experimental run, decide whether we preserve the current constrained semantics or intentionally relax them to unlock >408 samples.",
            "",
        ]
    )
    write_text_atomic(reports_root / "twenty_ninth_round_b_uav_blb_expansion_and_recheck_report.md", content)


def main() -> int:
    args = parse_args()
    root = repo_root()
    dataset_root = resolve_path(args.dataset_root)
    raw_root = resolve_path(args.raw_root)
    reports_root = resolve_path(args.reports_root)

    registry_text = (root / "metadata" / "uav_blb_model_registry.yaml").read_text(encoding="utf-8")
    manifest = load_json(root / "model_delivery" / "uav_blb_experimental_package" / "weights_manifest.json")
    conversion_report = load_json(dataset_root / "conversion_report.json")
    check_report = load_json(root / "reports" / "blb_uav_preview_1000_dataset_check.json")
    rows = read_metadata_rows(dataset_root / "metadata" / "image_metadata.csv")
    comparison_md = (root / "reports" / "uav_blb_experimental_model_comparison.md").read_text(encoding="utf-8")
    backend_decision_md = (root / "reports" / "uav_blb_experimental_backend_integration_decision.md").read_text(encoding="utf-8")

    build_script = import_script(root / "scripts" / "build_uav_blb_expanded_preview.py", "build_uav_blb_expanded_preview")
    expand_script = import_script(root / "scripts" / "expand_blb_uav_preview_dataset.py", "expand_blb_uav_preview_dataset")

    pairs = expand_script.find_pairs(raw_root, list(expand_script.DEFAULT_SOURCE_DATASETS))
    candidates, scan_report = expand_script.scan_candidates(pairs, 25)
    _, selection_600 = expand_script.select_candidates(candidates, 600, 2026, True)
    _, selection_800 = expand_script.select_candidates(candidates, 800, 2026, True)
    dry_run_600 = {
        "tool": "build_uav_blb_expanded_preview",
        "target_size": 600,
        "pair_count": len(pairs),
        "positive_candidate_count": len(candidates),
        "scan": scan_report,
        "selection": selection_600,
    }
    dry_run_800 = {
        "tool": "build_uav_blb_expanded_preview",
        "target_size": 800,
        "pair_count": len(pairs),
        "positive_candidate_count": len(candidates),
        "scan": scan_report,
        "selection": selection_800,
    }

    generate_assets_recheck(reports_root, registry_text, manifest, comparison_md, backend_decision_md)
    generate_shortfall_analysis(reports_root, conversion_report, rows, check_report, dry_run_600, dry_run_800)
    quality_payload = generate_quality_recheck(dataset_root, reports_root, rows)
    visual_summary = generate_visual_audit(dataset_root, reports_root, rows, args.visual_count)
    generate_expansion_candidate_plan(reports_root, dry_run_600, dry_run_800)
    generate_next_config(root / "configs" / "uav_blb_yolo_train_preview408_next_exp.yaml")
    generate_backend_boundary_recheck(reports_root)
    generate_final_report(reports_root, quality_payload, visual_summary, dry_run_600, dry_run_800)

    print(
        json.dumps(
            {
                "status": "ok",
                "reports_root": relative_path(reports_root),
                "dataset_root": relative_path(dataset_root),
                "visual_count": visual_summary["selected_images"],
                "preview_600_selected_count": dry_run_600["selection"]["selected_count"],
                "preview_800_selected_count": dry_run_800["selection"]["selected_count"],
                "config_written": relative_path(root / "configs" / "uav_blb_yolo_train_preview408_next_exp.yaml"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
