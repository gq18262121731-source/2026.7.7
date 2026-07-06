#!/usr/bin/env python
"""Read-only structure audit for RiceLeafDiseaseBD landing checks.

This script does not modify source data. It only scans the given input root and
writes an audit JSON plus a Markdown summary using atomic temp-file replacement.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
LABEL_EXTS = {".txt"}
YAML_EXTS = {".yaml", ".yml"}
JSON_EXTS = {".json"}
CSV_EXTS = {".csv"}
XLSX_EXTS = {".xlsx", ".xls"}
XML_EXTS = {".xml"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz"}
README_NAMES = {"readme", "readme.md", "readme.txt"}
LICENSE_NAMES = {"license", "license.md", "license.txt", "licence", "licence.md", "licence.txt"}


EXPECTED_SOURCE_CLASSES = {
    "Brown Spot": "brown_spot",
    "Blast": "rice_blast",
    "Healthy": "excluded_health_status_only",
    "Leaf Smut": "leaf_smut",
    "Rice Tungro": "tungro",
    "Sheath Blight": "sheath_blight",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit RiceLeafDiseaseBD raw package structure.")
    parser.add_argument("--input-root", required=True, help="Path to the official extracted package root.")
    parser.add_argument("--output-report", required=True, help="Markdown report path.")
    parser.add_argument("--output-json", required=True, help="JSON report path.")
    return parser.parse_args()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    with tmp_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    if not tmp_path.exists() or tmp_path.stat().st_size == 0:
        raise RuntimeError(f"Temporary file was not written correctly: {tmp_path}")
    os.replace(tmp_path, path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"Final file was not written correctly: {path}")


def is_readme(path: Path) -> bool:
    name = path.name.lower()
    stem = path.stem.lower()
    return name in README_NAMES or stem == "readme"


def is_license(path: Path) -> bool:
    name = path.name.lower()
    stem = path.stem.lower()
    return name in LICENSE_NAMES or stem in {"license", "licence"}


def looks_like_yolo_label(path: Path) -> tuple[bool, list[str], Counter[int], int]:
    errors: list[str] = []
    class_counts: Counter[int] = Counter()
    bbox_count = 0
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError as exc:
        return False, [f"read_error: {exc}"], class_counts, bbox_count

    non_empty = [line.strip() for line in lines if line.strip()]
    if not non_empty:
        return True, errors, class_counts, bbox_count

    for line_no, line in enumerate(non_empty, start=1):
        parts = re.split(r"\s+", line)
        if len(parts) != 5:
            errors.append(f"line {line_no}: expected 5 YOLO fields, got {len(parts)}")
            continue
        try:
            class_id = int(float(parts[0]))
            values = [float(v) for v in parts[1:]]
        except ValueError:
            errors.append(f"line {line_no}: non-numeric YOLO values")
            continue
        if class_id < 0:
            errors.append(f"line {line_no}: negative class_id {class_id}")
        if not all(0.0 <= v <= 1.0 for v in values):
            errors.append(f"line {line_no}: bbox values are not normalized into [0, 1]")
        if values[2] <= 0 or values[3] <= 0:
            errors.append(f"line {line_no}: bbox width/height must be positive")
        class_counts[class_id] += 1
        bbox_count += 1
    return len(errors) == 0, errors[:20], class_counts, bbox_count


def scan_files(input_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "input_root": str(input_root),
        "input_exists": input_root.exists(),
        "scanned_at_utc": datetime.now(timezone.utc).isoformat(),
        "expected_source_classes": EXPECTED_SOURCE_CLASSES,
        "counts": {
            "total_files": 0,
            "image_count": 0,
            "label_txt_count": 0,
            "csv_count": 0,
            "xlsx_count": 0,
            "yaml_count": 0,
            "json_count": 0,
            "xml_count": 0,
            "readme_count": 0,
            "license_count": 0,
            "archive_count": 0,
        },
        "candidate_directories": [],
        "sample_files": {
            "images": [],
            "labels": [],
            "yaml": [],
            "csv": [],
            "readme": [],
            "license": [],
            "archives": [],
        },
        "pairing": {
            "paired_image_label_count": 0,
            "images_without_label_count": 0,
            "labels_without_image_count": 0,
            "sample_pairs": [],
            "sample_images_without_label": [],
            "sample_labels_without_image": [],
        },
        "label_audit": {
            "looks_like_yolo": False,
            "bbox_count": 0,
            "class_id_counts": {},
            "invalid_label_file_count": 0,
            "sample_label_errors": [],
            "class_id_out_of_project_range_count": 0,
            "source_directory_class_id_counts": {},
        },
        "class_map_evidence": {
            "confirmed": False,
            "source": None,
            "mapping": {},
        },
        "license_evidence": {
            "confirmed": False,
            "source": None,
            "license": None,
        },
        "decision": {
            "detection_ready": False,
            "classification_only": False,
            "can_convert_to_phone_expanded": False,
            "has_real_images": False,
            "has_real_yolo_labels": False,
            "has_confirmed_class_map": False,
            "has_license_file": False,
            "reason": "input root does not exist",
        },
        "healthy_handling": {
            "source_class": "Healthy",
            "policy": "exclude from YOLO disease classes; keep only as health_status metadata if conversion is later performed",
        },
    }

    if not input_root.exists():
        return result

    if not input_root.is_dir():
        result["decision"]["reason"] = "input root exists but is not a directory"
        return result

    all_files = [p for p in input_root.rglob("*") if p.is_file()]
    result["counts"]["total_files"] = len(all_files)

    images: list[Path] = []
    labels: list[Path] = []
    yaml_files: list[Path] = []
    csv_files: list[Path] = []
    xlsx_files: list[Path] = []
    json_files: list[Path] = []
    xml_files: list[Path] = []
    readme_files: list[Path] = []
    license_files: list[Path] = []
    archive_files: list[Path] = []

    candidate_dir_tokens = {
        "images",
        "labels",
        "train",
        "val",
        "valid",
        "test",
        "annotations",
        "original_images",
        "annotated_data",
        "yolo",
    }
    candidate_dirs = set()

    for path in all_files:
        suffix = path.suffix.lower()
        parts_lower = {part.lower() for part in path.parts}
        if parts_lower & candidate_dir_tokens:
            for parent in path.parents:
                if parent == input_root.parent:
                    break
                if parent == input_root:
                    break
                if parent.name.lower() in candidate_dir_tokens:
                    candidate_dirs.add(str(parent))

        if suffix in IMAGE_EXTS:
            images.append(path)
        if suffix in LABEL_EXTS:
            labels.append(path)
        if suffix in YAML_EXTS:
            yaml_files.append(path)
        if suffix in CSV_EXTS:
            csv_files.append(path)
        if suffix in XLSX_EXTS:
            xlsx_files.append(path)
        if suffix in JSON_EXTS:
            json_files.append(path)
        if suffix in XML_EXTS:
            xml_files.append(path)
        if suffix in ARCHIVE_EXTS:
            archive_files.append(path)
        if is_readme(path):
            readme_files.append(path)
        if is_license(path):
            license_files.append(path)

    result["counts"].update(
        {
            "image_count": len(images),
            "label_txt_count": len(labels),
            "csv_count": len(csv_files),
            "xlsx_count": len(xlsx_files),
            "yaml_count": len(yaml_files),
            "json_count": len(json_files),
            "xml_count": len(xml_files),
            "readme_count": len(readme_files),
            "license_count": len(license_files),
            "archive_count": len(archive_files),
        }
    )

    def rel_samples(paths: list[Path], limit: int = 10) -> list[str]:
        return [str(p.relative_to(input_root)) for p in sorted(paths)[:limit]]

    result["candidate_directories"] = sorted(candidate_dirs)[:50]
    result["sample_files"] = {
        "images": rel_samples(images),
        "labels": rel_samples(labels),
        "yaml": rel_samples(yaml_files),
        "csv": rel_samples(csv_files),
        "xlsx": rel_samples(xlsx_files),
        "readme": rel_samples(readme_files),
        "license": rel_samples(license_files),
        "archives": rel_samples(archive_files),
    }

    image_by_stem: dict[str, list[Path]] = defaultdict(list)
    for image_path in images:
        image_by_stem[image_path.stem].append(image_path)
    label_by_stem: dict[str, list[Path]] = defaultdict(list)
    for label_path in labels:
        label_by_stem[label_path.stem].append(label_path)

    paired_stems = sorted(set(image_by_stem) & set(label_by_stem))
    images_without_label = sorted(set(image_by_stem) - set(label_by_stem))
    labels_without_image = sorted(set(label_by_stem) - set(image_by_stem))
    result["pairing"] = {
        "paired_image_label_count": len(paired_stems),
        "images_without_label_count": len(images_without_label),
        "labels_without_image_count": len(labels_without_image),
        "sample_pairs": [
            {
                "image": str(image_by_stem[stem][0].relative_to(input_root)),
                "label": str(label_by_stem[stem][0].relative_to(input_root)),
            }
            for stem in paired_stems[:10]
        ],
        "sample_images_without_label": images_without_label[:20],
        "sample_labels_without_image": labels_without_image[:20],
    }

    aggregate_class_counts: Counter[int] = Counter()
    source_directory_class_counts: dict[str, Counter[int]] = defaultdict(Counter)
    invalid_label_files: list[dict[str, Any]] = []
    bbox_count = 0
    yolo_like_count = 0
    for label_path in labels:
        ok, errors, class_counts, file_bbox_count = looks_like_yolo_label(label_path)
        if ok:
            yolo_like_count += 1
        else:
            invalid_label_files.append(
                {
                    "path": str(label_path.relative_to(input_root)),
                    "errors": errors,
                }
            )
        aggregate_class_counts.update(class_counts)
        source_class_name = label_path.parent.parent.name if label_path.parent.name.lower() == "labels" else "<unknown>"
        source_directory_class_counts[source_class_name].update(class_counts)
        bbox_count += file_bbox_count

    out_of_range = sum(count for class_id, count in aggregate_class_counts.items() if class_id < 0 or class_id > 5)
    result["label_audit"] = {
        "looks_like_yolo": bool(labels) and yolo_like_count == len(labels),
        "bbox_count": bbox_count,
        "class_id_counts": {str(k): v for k, v in sorted(aggregate_class_counts.items())},
        "source_directory_class_id_counts": {
            source: {str(k): v for k, v in sorted(counts.items())}
            for source, counts in sorted(source_directory_class_counts.items())
        },
        "invalid_label_file_count": len(invalid_label_files),
        "sample_label_errors": invalid_label_files[:10],
        "class_id_out_of_project_range_count": out_of_range,
    }

    has_images = len(images) > 0
    has_yolo_labels = len(labels) > 0 and result["label_audit"]["looks_like_yolo"] and bbox_count > 0
    readme_text = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")[:20000] for p in readme_files[:3]
    )
    readme_has_expected_mapping = all(name in readme_text for name in EXPECTED_SOURCE_CLASSES)
    readme_has_class_ids = "Class ID Mapping" in readme_text and "YOLO-compatible" in readme_text
    readme_license = "CC BY 4.0" if "CC BY 4.0" in readme_text or "Creative Commons Attribution 4.0" in readme_text else None
    class_map_confirmed = bool(yaml_files or csv_files or json_files) or (readme_has_expected_mapping and readme_has_class_ids)
    license_confirmed = bool(license_files) or bool(readme_license)
    result["class_map_evidence"] = {
        "confirmed": class_map_confirmed,
        "source": "README.md" if readme_has_expected_mapping and readme_has_class_ids else (
            "yaml/csv/json candidate" if (yaml_files or csv_files or json_files) else None
        ),
        "mapping": {
            "0": "Brown Spot",
            "1": "Blast",
            "2": "Healthy (excluded)",
            "3": "Leaf Smut / observed also in Rice Tungro labels",
            "4": "Rice Tungro or Sheath Blight depending on source directory",
            "5": "Sheath Blight per README, not observed in current labels",
        } if readme_has_expected_mapping else {},
        "notes": [
            "README provides source class mapping and license.",
            "Observed labels are safest to convert by source directory name, then remap to project class ids.",
        ] if readme_has_expected_mapping else [],
    }
    result["license_evidence"] = {
        "confirmed": license_confirmed,
        "source": "README.md" if readme_license else ("LICENSE file" if license_files else None),
        "license": readme_license,
    }
    has_class_map = class_map_confirmed
    has_license_file = license_confirmed
    paired = result["pairing"]["paired_image_label_count"] > 0
    classification_only = has_images and not has_yolo_labels
    detection_ready = has_images and has_yolo_labels and paired and has_class_map and has_license_file

    reason_parts = []
    if not has_images:
        reason_parts.append("no image files found")
    if not has_yolo_labels:
        reason_parts.append("no valid non-empty YOLO bbox label files found")
    if not paired:
        reason_parts.append("no image-label basename pairs found")
    if not has_class_map:
        reason_parts.append("no confirmed class map found in yaml/csv/json/readme")
    if not has_license_file:
        reason_parts.append("no confirmed license found in license/readme")
    if result["label_audit"]["invalid_label_file_count"]:
        reason_parts.append("some label files are not valid YOLO normalized bbox files")

    result["decision"] = {
        "detection_ready": detection_ready,
        "classification_only": classification_only,
        "can_convert_to_phone_expanded": detection_ready,
        "has_real_images": has_images,
        "has_real_yolo_labels": has_yolo_labels,
        "has_confirmed_class_map": has_class_map,
        "has_license_file": has_license_file,
        "reason": "; ".join(reason_parts) if reason_parts else "ready for a guarded conversion plan",
    }
    return result


def render_markdown(audit: dict[str, Any]) -> str:
    counts = audit["counts"]
    decision = audit["decision"]
    label = audit["label_audit"]
    pairing = audit["pairing"]
    lines = [
        "# RiceLeafDiseaseBD Structure Audit",
        "",
        f"- Input root: `{audit['input_root']}`",
        f"- Scanned at UTC: `{audit['scanned_at_utc']}`",
        f"- Input exists: `{str(audit['input_exists']).lower()}`",
        "",
        "## File Counts",
        "",
        f"- Total files: {counts['total_files']}",
        f"- Images: {counts['image_count']}",
        f"- YOLO txt labels: {counts['label_txt_count']}",
        f"- CSV files: {counts['csv_count']}",
        f"- YAML files: {counts['yaml_count']}",
        f"- JSON files: {counts['json_count']}",
        f"- XML files: {counts['xml_count']}",
        f"- README files: {counts['readme_count']}",
        f"- LICENSE files: {counts['license_count']}",
        f"- Archives: {counts['archive_count']}",
        "",
        "## Pairing And Label Audit",
        "",
        f"- Paired image/label basenames: {pairing['paired_image_label_count']}",
        f"- Images without labels: {pairing['images_without_label_count']}",
        f"- Labels without images: {pairing['labels_without_image_count']}",
        f"- Looks like YOLO labels: `{str(label['looks_like_yolo']).lower()}`",
        f"- Bbox count: {label['bbox_count']}",
        f"- Class id counts: `{json.dumps(label['class_id_counts'], ensure_ascii=False)}`",
        f"- Invalid label files: {label['invalid_label_file_count']}",
        "",
        "## Decision",
        "",
        f"- has_real_images: `{str(decision['has_real_images']).lower()}`",
        f"- has_real_yolo_labels: `{str(decision['has_real_yolo_labels']).lower()}`",
        f"- detection_ready: `{str(decision['detection_ready']).lower()}`",
        f"- classification_only: `{str(decision['classification_only']).lower()}`",
        f"- can_convert_to_phone_expanded: `{str(decision['can_convert_to_phone_expanded']).lower()}`",
        f"- reason: {decision['reason']}",
        "",
        "## Expected Class Handling",
        "",
        "| Source class | Project handling |",
        "| --- | --- |",
    ]
    for source, mapped in EXPECTED_SOURCE_CLASSES.items():
        lines.append(f"| {source} | {mapped} |")
    lines.extend(
        [
            "",
            "Healthy, normal, background, unknown, and uncertain classes must not be emitted as YOLO disease labels.",
            "",
            "## Sample Files",
            "",
        ]
    )
    for group, samples in audit["sample_files"].items():
        lines.append(f"- {group}: {', '.join(f'`{s}`' for s in samples) if samples else 'none'}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    input_root = Path(args.input_root)
    output_report = Path(args.output_report)
    output_json = Path(args.output_json)
    audit = scan_files(input_root)
    atomic_write_text(output_json, json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    atomic_write_text(output_report, render_markdown(audit))


if __name__ == "__main__":
    main()

