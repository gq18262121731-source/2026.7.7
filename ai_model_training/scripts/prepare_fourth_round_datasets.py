"""Prepare fourth-round real dataset smoke samples.

This script only organizes small public samples into YOLO format. It does not
train models, create weights, or calculate model metrics.
"""

from __future__ import annotations

import csv
import json
import shutil
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw_datasets"
PHONE_ROOT = ROOT / "datasets" / "rice_phone_rgb"
UAV_ROOT = ROOT / "datasets" / "rice_uav_ms"
REPORTS = ROOT / "reports"

TODAY = date.today().isoformat()


@dataclass(frozen=True)
class ClassInfo:
    id: int
    code: str
    zh_name: str
    category_type: str
    aliases: tuple[str, ...]


PHONE_CLASSES = [
    ClassInfo(0, "bacterial_leaf_blight", "bacterial leaf blight", "disease", ("Rice__BacterialLeafBlight",)),
    ClassInfo(1, "brown_spot", "brown spot", "disease", ("Rice__BrownSpot",)),
    ClassInfo(2, "rice_blast", "rice blast", "disease", ("Rice__LeafBlast", "Rice__NeckBlast", "Blast filename group")),
]

UAV_CLASSES = [
    ClassInfo(0, "rice_panicle", "rice panicle", "crop_object", ("Rice-Panicle",)),
]

PHONE_SOURCE_NAMES = {
    0: ("Rice__BacterialLeafBlight", "bacterial_leaf_blight", "disease"),
    1: ("Rice__BrownSpot", "brown_spot", "disease"),
    2: ("Rice__Healthy", None, "healthy"),
    3: ("Rice__Hispa", None, "uncertain"),
    4: ("Rice__LeafBlast_or_uncertain", None, "uncertain"),
    5: ("Rice__LeafScald_or_uncertain", None, "uncertain"),
    6: ("Rice__LeafBlast", "rice_blast", "disease"),
    7: ("Rice__NarrowBrownLeafSpot_or_uncertain", None, "uncertain"),
    8: ("Rice__NeckBlast", None, "uncertain"),
}

PHONE_CODE_TO_ID = {item.code: item.id for item in PHONE_CLASSES}

METADATA_FIELDS = [
    "image_name",
    "dataset_name",
    "source_url",
    "source_type",
    "sensor_type",
    "is_multispectral",
    "split",
    "original_label",
    "mapped_code",
    "category_type",
    "severity",
    "plant_part",
    "license",
    "download_date",
    "annotation_format",
    "annotation_source",
    "notes",
]


def ensure_clean_yolo_dirs(root: Path) -> None:
    for kind in ("images", "labels"):
        for split in ("train", "val", "test"):
            target = root / kind / split
            if target.exists():
                for path in target.iterdir():
                    if path.is_file():
                        path.unlink()
            target.mkdir(parents=True, exist_ok=True)
    (root / "metadata").mkdir(parents=True, exist_ok=True)


def write_class_map(path: Path, version: str, model_name: str, classes: list[ClassInfo]) -> None:
    lines = [f"version: {version}", f"model_name: {model_name}", "classes:"]
    for item in classes:
        lines.extend(
            [
                f"  - id: {item.id}",
                f"    code: {item.code}",
                f"    zh_name: {item.zh_name}",
                f"    category_type: {item.category_type}",
                "    aliases:",
            ]
        )
        for alias in item.aliases:
            lines.append(f"      - {alias}")
    lines.extend(
        [
            "reserved:",
            "  healthy: health status only; never written as a YOLO detection class",
            "  background: excluded from YOLO labels",
            "  unknown: review-only; excluded from YOLO labels",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_data_yaml(path: Path, dataset_root: str, classes: list[ClassInfo]) -> None:
    lines = [
        f"path: {dataset_root}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        f"nc: {len(classes)}",
        "names:",
    ]
    for item in classes:
        lines.append(f"  {item.id}: {item.code}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_metadata(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=METADATA_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def normalize_phone_label_text(text: str) -> tuple[list[str], list[tuple[str, str, str]]]:
    lines: list[str] = []
    mapped_objects: list[tuple[str, str, str]] = []
    for raw in text.splitlines():
        parts = raw.strip().split()
        if len(parts) != 5:
            continue
        old_id = int(float(parts[0]))
        original_label, code, category_type = PHONE_SOURCE_NAMES.get(old_id, (f"unknown_{old_id}", None, "excluded"))
        if code is None:
            continue
        new_id = PHONE_CODE_TO_ID[code]
        lines.append(" ".join([str(new_id), *parts[1:]]))
        mapped_objects.append((original_label, code, category_type))
    return lines, mapped_objects


def select_phone_samples(zip_path: Path, out_root: Path) -> dict[str, object]:
    wanted_by_split = {"train": 10, "val": 3}
    selected_counts: dict[str, Counter[str]] = {split: Counter() for split in wanted_by_split}
    rows: list[dict[str, str]] = []
    report: dict[str, object] = {
        "source_zip": str(zip_path),
        "source_format": "YOLO",
        "target_format": "YOLO",
        "class_mapping": {},
        "selected_images": 0,
        "selected_labels": 0,
        "selected_objects": 0,
        "excluded_objects": Counter(),
    }

    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        label_paths = sorted(p for p in names if p.startswith("rice/labels/") and p.endswith(".txt"))
        for label_path in label_paths:
            parts = Path(label_path).parts
            if len(parts) < 4:
                continue
            source_split = parts[2]
            if source_split not in wanted_by_split:
                continue
            label_text = zf.read(label_path).decode("utf-8")
            yolo_lines, mapped_objects = normalize_phone_label_text(label_text)
            if not yolo_lines:
                continue
            primary_code = mapped_objects[0][1]
            if selected_counts[source_split][primary_code] >= wanted_by_split[source_split]:
                continue

            stem = Path(label_path).stem
            image_path = f"rice/images/{source_split}/{stem}.jpg"
            if image_path not in names:
                continue

            image_name = f"phone_kaggle_{source_split}_{stem}.jpg"
            label_name = f"phone_kaggle_{source_split}_{stem}.txt"
            (out_root / "images" / source_split / image_name).write_bytes(zf.read(image_path))
            (out_root / "labels" / source_split / label_name).write_text("\n".join(yolo_lines) + "\n", encoding="utf-8")

            selected_counts[source_split][primary_code] += 1
            report["selected_images"] = int(report["selected_images"]) + 1
            report["selected_labels"] = int(report["selected_labels"]) + 1
            report["selected_objects"] = int(report["selected_objects"]) + len(yolo_lines)
            original_labels = sorted({item[0] for item in mapped_objects})
            mapped_codes = sorted({item[1] for item in mapped_objects})
            category_types = sorted({item[2] for item in mapped_objects})
            rows.append(
                {
                    "image_name": image_name,
                    "dataset_name": "rice_leaf_diseases_kaggle_yolo",
                    "source_url": "https://www.kaggle.com/datasets/yusufmurtaza01/rice-leaf-diseases",
                    "source_type": "phone_rgb",
                    "sensor_type": "rgb",
                    "is_multispectral": "false",
                    "split": source_split,
                    "original_label": ";".join(original_labels),
                    "mapped_code": ";".join(mapped_codes),
                    "category_type": ";".join(category_types),
                    "severity": "",
                    "plant_part": "leaf",
                    "license": "CC0 1.0 per Dataset Ninja mirror; Kaggle page should be rechecked before formal use",
                    "download_date": TODAY,
                    "annotation_format": "YOLO",
                    "annotation_source": "Kaggle direct dataset download",
                    "notes": "healthy and uncertain source ids excluded; class 6 retained as rice_blast because labels align with Blast filename group",
                }
            )

    report["class_mapping"] = {
        str(old_id): {"original_label": original, "mapped_code": code, "category_type": category_type}
        for old_id, (original, code, category_type) in PHONE_SOURCE_NAMES.items()
    }
    report["selected_by_split_and_code"] = {
        split: dict(counter) for split, counter in selected_counts.items()
    }
    write_metadata(out_root / "metadata" / "image_metadata.csv", rows)
    return report


def coco_to_yolo_lines(annotations: list[dict[str, object]], width: int, height: int) -> list[str]:
    lines: list[str] = []
    for ann in annotations:
        x, y, w, h = [float(v) for v in ann["bbox"]]
        if w <= 0 or h <= 0:
            continue
        x_center = (x + w / 2) / width
        y_center = (y + h / 2) / height
        lines.append(f"0 {x_center:.6f} {y_center:.6f} {w / width:.6f} {h / height:.6f}")
    return lines


def select_uav_samples(zip_path: Path, out_root: Path) -> dict[str, object]:
    limits = {"train": 24, "valid": 8, "test": 8}
    split_map = {"train": "train", "valid": "val", "test": "test"}
    rows: list[dict[str, str]] = []
    report: dict[str, object] = {
        "source_zip": str(zip_path),
        "source_format": "COCO",
        "target_format": "YOLO",
        "target_class": "rice_panicle",
        "target_category_type": "crop_object",
        "selected_images": 0,
        "selected_labels": 0,
        "selected_objects": 0,
        "selected_by_split": {},
    }

    with zipfile.ZipFile(zip_path) as zf:
        for source_split, limit in limits.items():
            data = json.loads(zf.read(f"{source_split}/_annotations.coco.json").decode("utf-8"))
            images = sorted(data["images"], key=lambda item: item["file_name"])
            anns_by_image: dict[int, list[dict[str, object]]] = defaultdict(list)
            for ann in data["annotations"]:
                anns_by_image[int(ann["image_id"])].append(ann)

            selected = 0
            target_split = split_map[source_split]
            for image in images:
                if selected >= limit:
                    break
                image_id = int(image["id"])
                anns = anns_by_image.get(image_id, [])
                if not anns:
                    continue
                yolo_lines = coco_to_yolo_lines(anns, int(image["width"]), int(image["height"]))
                if not yolo_lines:
                    continue
                source_image_path = f"{source_split}/{image['file_name']}"
                image_name = f"uav_panicle_{target_split}_{image['file_name']}"
                label_name = f"{Path(image_name).stem}.txt"
                (out_root / "images" / target_split / image_name).write_bytes(zf.read(source_image_path))
                (out_root / "labels" / target_split / label_name).write_text("\n".join(yolo_lines) + "\n", encoding="utf-8")
                selected += 1
                report["selected_images"] = int(report["selected_images"]) + 1
                report["selected_labels"] = int(report["selected_labels"]) + 1
                report["selected_objects"] = int(report["selected_objects"]) + len(yolo_lines)
                rows.append(
                    {
                        "image_name": image_name,
                        "dataset_name": "rice_panicle_mendeley_coco",
                        "source_url": "https://data.mendeley.com/datasets/ndb6t28xbk/4",
                        "source_type": "auxiliary_uav_object",
                        "sensor_type": "rgb",
                        "is_multispectral": "false",
                        "split": target_split,
                        "original_label": "Rice-Panicle",
                        "mapped_code": "rice_panicle",
                        "category_type": "crop_object",
                        "severity": "",
                        "plant_part": "panicle",
                        "license": "CC BY 4.0",
                        "download_date": TODAY,
                        "annotation_format": "COCO converted to YOLO",
                        "annotation_source": "Mendeley Data / Roboflow export",
                        "notes": "UAV/field-distance auxiliary crop-object dataset; not disease or pest",
                    }
                )
            report["selected_by_split"][target_split] = selected

    write_metadata(out_root / "metadata" / "image_metadata.csv", rows)
    return report


def organize_raw_files() -> dict[str, str]:
    outputs: dict[str, str] = {}
    specs = {
        "rice_leaf_diseases_kaggle_yolo": "rice_leaf_diseases_kaggle_yolo.zip",
        "rice_panicle_mendeley_coco": "rice_panicle_mendeley_coco.zip",
    }
    for dataset_name, zip_name in specs.items():
        dataset_dir = RAW / dataset_name
        original_dir = dataset_dir / "original"
        annotations_dir = dataset_dir / "annotations_raw"
        license_dir = dataset_dir / "license_or_readme"
        for path in (original_dir, annotations_dir, license_dir):
            path.mkdir(parents=True, exist_ok=True)
        root_zip = RAW / zip_name
        target_zip = original_dir / zip_name
        if root_zip.exists() and not target_zip.exists():
            shutil.move(str(root_zip), str(target_zip))
        outputs[dataset_name] = str(target_zip)
    return outputs


def write_notes(raw_paths: dict[str, str], phone_report: dict[str, object], uav_report: dict[str, object]) -> None:
    notes = {
        "rice_leaf_diseases_kaggle_yolo": [
            "# Conversion Notes",
            "",
            "Source: https://www.kaggle.com/datasets/yusufmurtaza01/rice-leaf-diseases",
            "Download: Kaggle public direct API.",
            "Original format: YOLO.",
            "Action: sampled a small smoke-test subset, excluded healthy, remapped class ids.",
            f"Selected images: {phone_report['selected_images']}",
            f"Selected objects: {phone_report['selected_objects']}",
            "",
        ],
        "rice_panicle_mendeley_coco": [
            "# Conversion Notes",
            "",
            "Source: https://data.mendeley.com/datasets/ndb6t28xbk/4",
            "Download: Mendeley public file URL.",
            "Original format: COCO.",
            "Action: sampled a small UAV/field-distance auxiliary subset and converted boxes to YOLO.",
            "Caveat: rice panicle is a crop-object class, not a disease or pest class.",
            f"Selected images: {uav_report['selected_images']}",
            f"Selected objects: {uav_report['selected_objects']}",
            "",
        ],
    }
    for dataset_name, lines in notes.items():
        (RAW / dataset_name / "conversion_notes.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    raw_paths = organize_raw_files()
    ensure_clean_yolo_dirs(PHONE_ROOT)
    ensure_clean_yolo_dirs(UAV_ROOT)

    write_class_map(
        PHONE_ROOT / "metadata" / "class_map.yaml",
        "rice_phone_rgb_classes_v0.2_real_smoke",
        "phone_rice_disease_yolo",
        PHONE_CLASSES,
    )
    write_class_map(
        UAV_ROOT / "metadata" / "class_map.yaml",
        "rice_uav_ms_classes_v0.2_real_smoke",
        "uav_rice_disease_yolo",
        UAV_CLASSES,
    )
    write_data_yaml(PHONE_ROOT / "data.yaml", "datasets/rice_phone_rgb", PHONE_CLASSES)
    write_data_yaml(UAV_ROOT / "data.yaml", "datasets/rice_uav_ms", UAV_CLASSES)

    phone_report = select_phone_samples(Path(raw_paths["rice_leaf_diseases_kaggle_yolo"]), PHONE_ROOT)
    uav_report = select_uav_samples(Path(raw_paths["rice_panicle_mendeley_coco"]), UAV_ROOT)
    write_notes(raw_paths, phone_report, uav_report)

    REPORTS.mkdir(parents=True, exist_ok=True)
    report = {
        "boundary": "dataset preparation only; no training, no weights, no model metrics",
        "phone": phone_report,
        "uav": uav_report,
    }
    (REPORTS / "fourth_round_conversion_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
