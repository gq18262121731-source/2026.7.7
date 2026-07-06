from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except Exception:  # pragma: no cover - integrity report records unavailable image reader.
    Image = None


DATASET_ROOT_NAME = "ai_model_training/datasets_external/p11_open_datasets"


@dataclass(frozen=True)
class DatasetGate:
    dataset_name: str
    slug: str
    task_type: str
    modality: str
    label_type: str
    source_url: str
    source_platform: str
    crop_type: str
    annotation_type: str
    license_status: str
    license_name: str
    access_status: str
    local_status: str
    class_mapping_status: str
    split_status: str
    leakage_risk: str
    train_ready: str
    allowed_next_step: str
    allow_sample_download: bool
    allow_train_smoke: bool
    allow_formal_train: bool
    gate_status: str
    gate_reason: str
    risks: list[str]
    source_local_candidates: list[str] = field(default_factory=list)
    class_mappings: list[dict[str, str]] = field(default_factory=list)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def project_root_from_script() -> Path:
    return Path(__file__).resolve().parents[4]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_image_size(path: Path) -> tuple[int | None, int | None, bool]:
    if Image is None:
        return None, None, False
    try:
        with Image.open(path) as img:
            width, height = img.size
            img.verify()
        return width, height, True
    except Exception:
        return None, None, False


def ensure_dirs(dataset_root: Path, slug: str) -> dict[str, Path]:
    paths = {
        "dataset": dataset_root / slug,
        "sources": dataset_root / slug / "sources",
        "source_cards": dataset_root / slug / "source_cards",
        "manifests": dataset_root / slug / "manifests",
        "class_mapping": dataset_root / slug / "class_mapping",
        "split_plans": dataset_root / slug / "split_plans",
        "integrity": dataset_root / slug / "integrity",
        "smoke_outputs": dataset_root / slug / "smoke_outputs",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def select_riceseg_pairs(project_root: Path, limit: int = 4) -> list[tuple[str, Path, Path]]:
    mask_root = project_root / "ai_model_training/raw_datasets/rice_seg_5932/extracted/mask-vesrion1"
    image_root = project_root / "ai_model_training/raw_datasets/rice_leaf_disease_sethy/extracted/Rice Leaf Disease Images"
    if not mask_root.exists() or not image_root.exists():
        return []
    classes = [
        ("Bacterialblight", "bacterial_leaf_blight"),
        ("Brownspot", "brown_spot"),
        ("Leafblast", "rice_blast"),
        ("Tungro", "tungro"),
    ]
    pairs: list[tuple[str, Path, Path]] = []
    for source_class, mapped in classes:
        masks = sorted((mask_root / source_class).glob("*"))
        images_by_stem = {
            item.stem.lower(): item
            for item in (image_root / source_class).glob("*")
            if item.is_file() and item.suffix.lower() in {".jpg", ".jpeg", ".png"}
        }
        for mask in masks:
            if not mask.is_file() or mask.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                continue
            image = images_by_stem.get(mask.stem.lower())
            if image:
                pairs.append((mapped, image, mask))
                break
        if len(pairs) >= limit:
            break
    return pairs[:limit]


def count_files(root: Path | None, suffixes: set[str] | None = None) -> int:
    if not root or not root.exists():
        return 0
    total = 0
    for item in root.rglob("*"):
        if not item.is_file():
            continue
        if suffixes and item.suffix.lower() not in suffixes:
            continue
        total += 1
    return total


def dataset_definitions(project_root: Path) -> list[DatasetGate]:
    raw = project_root / "ai_model_training/raw_datasets"
    return [
        DatasetGate(
            dataset_name="Rice Leaf Bacterial and Fungal Disease Dataset",
            slug="rice_leaf_bacterial_fungal",
            task_type="phone_rgb_classification_baseline",
            modality="RGB / leaf close-up",
            label_type="classification",
            source_url="https://data.mendeley.com/datasets/hx6f852hw4/2",
            source_platform="Mendeley Data",
            crop_type="rice",
            annotation_type="classification label",
            license_status="PASSED",
            license_name="CC BY 4.0",
            access_status="SOURCE_PAGE_200_DOWNLOAD_NOT_ATTEMPTED",
            local_status="RAW_SAMPLE_NOT_LANDED_FOR_EXACT_DATASET",
            class_mapping_status="PARTIAL_NEEDS_REVIEW_FOR_LEAF_SCALD_HISPA_NARROW_BROWN",
            split_status="NEEDS_SPLIT_AFTER_DOWNLOAD; original/augmented must be grouped",
            leakage_risk="HIGH_ORIGINAL_AUGMENTED_LEAKAGE_RISK",
            train_ready="NO_RAW_SAMPLE_YET",
            allowed_next_step="ALLOW_SMALL_SAMPLE_DOWNLOAD_THEN_PHONE_RGB_SMOKE",
            allow_sample_download=True,
            allow_train_smoke=False,
            allow_formal_train=False,
            gate_status="SAMPLE_GATE_BLOCKED",
            gate_reason="License is clear, but exact dataset raw samples were not locally landed in this P11-1 run.",
            risks=[
                "Original and augmented images must not cross split boundaries.",
                "Some classes cannot be confidently mapped to current disease_id without review.",
                "Local RiceLeafDiseaseBD assets are a related but different source and were not substituted.",
            ],
            source_local_candidates=[str(raw / "rice_leaf_bacterial_fungal_disease")],
            class_mappings=[
                {"original_class": "Bacterial Leaf Blight", "mapped_class": "bacterial_leaf_blight", "mapped_disease_code": "bacterial_leaf_blight", "confidence": "high", "mapping_status": "APPROVED"},
                {"original_class": "Brown Spot", "mapped_class": "brown_spot", "mapped_disease_code": "brown_spot", "confidence": "high", "mapping_status": "APPROVED"},
                {"original_class": "Leaf Blast", "mapped_class": "rice_blast", "mapped_disease_code": "rice_blast", "confidence": "high", "mapping_status": "APPROVED"},
                {"original_class": "Healthy Rice Leaf", "mapped_class": "healthy_or_background", "mapped_disease_code": "healthy", "confidence": "high", "mapping_status": "APPROVED_HEALTHY_NOT_DISEASE"},
                {"original_class": "Sheath Blight", "mapped_class": "unknown_or_excluded", "mapped_disease_code": "sheath_blight", "confidence": "medium", "mapping_status": "NEEDS_REVIEW_IN_CURRENT_P11_TARGET_SET"},
                {"original_class": "Leaf scald", "mapped_class": "unknown_or_excluded", "mapped_disease_code": "", "confidence": "low", "mapping_status": "NEEDS_REVIEW"},
                {"original_class": "Narrow Brown Leaf Spot", "mapped_class": "unknown_or_excluded", "mapped_disease_code": "", "confidence": "low", "mapping_status": "NEEDS_REVIEW_DO_NOT_FORCE_MERGE"},
                {"original_class": "Rice Hispa", "mapped_class": "unknown_or_excluded", "mapped_disease_code": "", "confidence": "low", "mapping_status": "NEEDS_REVIEW_PEST_TARGET_TYPE"},
            ],
        ),
        DatasetGate(
            dataset_name="RiceSeg-5932",
            slug="riceseg_5932",
            task_type="leaf_lesion_segmentation_smoke",
            modality="RGB image + mask",
            label_type="segmentation mask",
            source_url="https://data.mendeley.com/datasets/92jc6w6mcy",
            source_platform="Mendeley Data + Sethy source images",
            crop_type="rice",
            annotation_type="pixel-level mask",
            license_status="PASSED",
            license_name="CC BY 4.0",
            access_status="SOURCE_PAGE_200_LOCAL_SOURCE_IMAGES_FOUND",
            local_status="SAMPLE_LANDED_FROM_EXISTING_LOCAL_RAW_DATA",
            class_mapping_status="PASSED_FOR_BLB_BROWN_SPOT_RICE_BLAST_TUNGRO",
            split_status="SAMPLE_SPLIT_PLAN_CREATED_HELD_OUT_REQUIRED_FOR_REAL_TRAINING",
            leakage_risk="MEDIUM_PAIRING_AND_SOURCE_IMAGE_VERSION_RISK",
            train_ready="SMOKE_READY_ONLY",
            allowed_next_step="ALLOW_SEGMENTATION_PIPELINE_SMOKE_ONLY",
            allow_sample_download=True,
            allow_train_smoke=True,
            allow_formal_train=False,
            gate_status="PASSED_FOR_SMOKE",
            gate_reason="Masks and matching Sethy source images were found locally and sample pairs were copied to the experimental external directory.",
            risks=[
                "Mask-only dataset requires exact source image pairing.",
                "Held-out split must be rebuilt on full data before any real experiment.",
                "Bacterial Blight naming must remain auditable against BLB disease_id.",
            ],
            source_local_candidates=[
                str(raw / "rice_seg_5932"),
                str(raw / "rice_leaf_disease_sethy"),
            ],
            class_mappings=[
                {"original_class": "Bacterial Blight", "mapped_class": "bacterial_leaf_blight", "mapped_disease_code": "bacterial_leaf_blight", "confidence": "medium", "mapping_status": "APPROVED_WITH_NAME_REVIEW"},
                {"original_class": "Brown Spot", "mapped_class": "brown_spot", "mapped_disease_code": "brown_spot", "confidence": "high", "mapping_status": "APPROVED"},
                {"original_class": "Leaf Blast", "mapped_class": "rice_blast", "mapped_disease_code": "rice_blast", "confidence": "high", "mapping_status": "APPROVED"},
                {"original_class": "Tungro", "mapped_class": "unknown_or_excluded", "mapped_disease_code": "tungro", "confidence": "medium", "mapping_status": "EXCLUDED_FROM_CURRENT_TARGET_SET_OR_REVIEW"},
            ],
        ),
        DatasetGate(
            dataset_name="Rice Disease bbox",
            slug="rice_disease_bbox",
            task_type="bbox_detection_smoke",
            modality="RGB / leaf close-up",
            label_type="bounding box",
            source_url="https://datasetninja.com/rice-disease",
            source_platform="Dataset Ninja / Kaggle",
            crop_type="rice",
            annotation_type="bbox",
            license_status="PASSED",
            license_name="CC0 1.0 per Dataset Ninja page",
            access_status="SOURCE_PAGE_200_KAGGLE_DOWNLOAD_NOT_ATTEMPTED",
            local_status="RAW_SAMPLE_NOT_LANDED; local zip placeholder not usable",
            class_mapping_status="PASSED_FOR_3_CLASSES",
            split_status="NEEDS_SPLIT_AFTER_SAMPLE_DOWNLOAD",
            leakage_risk="MEDIUM_SMALL_DATASET_EVALUATION_INSTABILITY",
            train_ready="NO_RAW_SAMPLE_YET",
            allowed_next_step="ALLOW_SMALL_SAMPLE_DOWNLOAD_THEN_BBOX_SMOKE",
            allow_sample_download=True,
            allow_train_smoke=False,
            allow_formal_train=False,
            gate_status="SAMPLE_GATE_BLOCKED",
            gate_reason="License appears clear, but raw bbox sample was not locally available; Kaggle download was not attempted in this no-large-download run.",
            risks=[
                "Small dataset, not suitable for formal performance claims.",
                "Kaggle metadata must be captured before smoke training.",
                "YOLO conversion must preserve bbox coordinate convention.",
            ],
            source_local_candidates=[str(raw / "rice_leaf_diseases_kaggle_yolo")],
            class_mappings=[
                {"original_class": "BacterialBlight", "mapped_class": "bacterial_leaf_blight", "mapped_disease_code": "bacterial_leaf_blight", "confidence": "high", "mapping_status": "APPROVED"},
                {"original_class": "BrownSpot", "mapped_class": "brown_spot", "mapped_disease_code": "brown_spot", "confidence": "high", "mapping_status": "APPROVED"},
                {"original_class": "RiceBlast", "mapped_class": "rice_blast", "mapped_disease_code": "rice_blast", "confidence": "high", "mapping_status": "APPROVED"},
            ],
        ),
        DatasetGate(
            dataset_name="Aligned RGB+MS Weedy Rice",
            slug="aligned_rgb_ms_weedy_rice",
            task_type="ms_pipeline_smoke_ndvi_ndre",
            modality="UAV RGB + multispectral Green/Red/RedEdge/NIR",
            label_type="binary segmentation mask for weedy rice; no disease label",
            source_url="https://data.mendeley.com/datasets/vt4s83pxx6",
            source_platform="Mendeley Data",
            crop_type="rice field / weedy rice",
            annotation_type="binary mask + metadata",
            license_status="PASSED",
            license_name="CC BY 4.0",
            access_status="SOURCE_PAGE_200_DOWNLOAD_NOT_ATTEMPTED",
            local_status="RAW_SAMPLE_NOT_LANDED",
            class_mapping_status="NOT_DISEASE_DATASET",
            split_status="SOURCE_HAS_SAMPLE_SPLIT; not locally verified",
            leakage_risk="MEDIUM_RGB_MS_MASK_PAIRING_RISK",
            train_ready="MS_PIPELINE_ONLY_AFTER_SAMPLE_DOWNLOAD",
            allowed_next_step="ALLOW_MS_PIPELINE_SMOKE_ONLY; NO_DISEASE_TRAINING",
            allow_sample_download=True,
            allow_train_smoke=False,
            allow_formal_train=False,
            gate_status="PASSED_FOR_MS_PIPELINE_ONLY",
            gate_reason="License is clear and source page is reachable, but no raw sample was downloaded; not a disease dataset.",
            risks=[
                "Labels are weedy rice, not disease.",
                "May validate NDVI/NDRE calculation and band alignment only.",
                "Must not be used for disease classification or field risk labels.",
            ],
            source_local_candidates=[str(raw / "weedy_rice_rgb_ms")],
            class_mappings=[
                {"original_class": "weedy rice", "mapped_class": "unknown_or_excluded", "mapped_disease_code": "", "confidence": "high", "mapping_status": "NON_DISEASE_EXCLUDED"},
                {"original_class": "background/cultivated rice", "mapped_class": "healthy_or_background", "mapped_disease_code": "background", "confidence": "medium", "mapping_status": "BACKGROUND_ONLY"},
            ],
        ),
        DatasetGate(
            dataset_name="BLB UAV Dataset",
            slug="blb_uav_dataset",
            task_type="uav_blb_license_gate_only",
            modality="UAV multispectral / patch data",
            label_type="segmentation or class labels, local structure only",
            source_url="https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0314535",
            source_platform="PLOS One / Figshare / Google Drive",
            crop_type="rice",
            annotation_type="BLB UAV segmentation candidate",
            license_status="NEEDS_CONFIRMATION",
            license_name="Data license not confirmed from dataset landing page",
            access_status="PLOS_PAGE_200_DATA_DOWNLOAD_GATE_NOT_CONFIRMED",
            local_status="LOCAL_EXISTING_DATA_FOUND_BUT_NOT_RELEASED_FOR_TRAINING",
            class_mapping_status="PASSED_FOR_BLB_ONLY",
            split_status="LOCAL_SPLITS_EXIST_BUT_NOT_TRUSTED_UNTIL_LICENSE_PASS",
            leakage_risk="HIGH_PATCH_FROM_SAME_ORTHOMOSAIC_LEAKAGE_RISK",
            train_ready="LICENSE_GATE_BLOCKED",
            allowed_next_step="LICENSE_GATE_AND_SOURCE_CARD_ONLY",
            allow_sample_download=False,
            allow_train_smoke=False,
            allow_formal_train=False,
            gate_status="LICENSE_GATE_BLOCKED",
            gate_reason="BLB UAV data license is not confirmed; local existing files are inspected only and cannot be used for training in this gate.",
            risks=[
                "Data license cannot be inferred from paper license.",
                "Patch extraction may leak source orthomosaic across split.",
                "No formal model replacement or UAV disease training is allowed before license gate passes.",
            ],
            source_local_candidates=[str(raw / "blb_uav_dataset")],
            class_mappings=[
                {"original_class": "BLB / Bacterial Leaf Blight", "mapped_class": "bacterial_leaf_blight", "mapped_disease_code": "bacterial_leaf_blight", "confidence": "medium", "mapping_status": "MAPPING_OK_BUT_LICENSE_BLOCKED"},
                {"original_class": "healthy/background", "mapped_class": "healthy_or_background", "mapped_disease_code": "background", "confidence": "medium", "mapping_status": "BACKGROUND_ONLY"},
            ],
        ),
    ]


def make_source_card(gate: DatasetGate, generated_at: str) -> dict[str, Any]:
    return {
        "dataset_name": gate.dataset_name,
        "slug": gate.slug,
        "source_url": gate.source_url,
        "source_platform": gate.source_platform,
        "data_type": gate.modality,
        "crop_type": gate.crop_type,
        "disease_classes": sorted({row["mapped_class"] for row in gate.class_mappings}),
        "annotation_type": gate.annotation_type,
        "license_status": gate.license_status,
        "license_name": gate.license_name,
        "allow_sample_download": gate.allow_sample_download,
        "allow_train_smoke": gate.allow_train_smoke,
        "allow_formal_train": gate.allow_formal_train,
        "allow_commercial_or_competition_display": "NEEDS_LICENSE_REVIEW" if gate.license_status != "PASSED" else "ATTRIBUTION_REQUIRED_OR_LICENSE_TERMS",
        "risk_notes": gate.risks,
        "decision": gate.gate_status,
        "gate_reason": gate.gate_reason,
        "generated_at": generated_at,
    }


def make_license_summary(gate: DatasetGate, generated_at: str) -> str:
    return f"""# License Summary: {gate.dataset_name}

- Generated at: {generated_at}
- Source: {gate.source_url}
- License status: {gate.license_status}
- License name: {gate.license_name}
- Access status: {gate.access_status}
- Gate status: {gate.gate_status}

## Training Decision

- allow_train_smoke: {str(gate.allow_train_smoke).lower()}
- allow_formal_train: {str(gate.allow_formal_train).lower()}
- allowed_next_step: {gate.allowed_next_step}

## Notes

{chr(10).join(f'- {item}' for item in gate.risks)}

No formal disease probability, prescription, dosage advice, backend main-chain change, model replacement, or risk_fusion ML training is permitted by this P11-1 gate.
"""


def copy_riceseg_samples(project_root: Path, dataset_paths: dict[str, Path]) -> list[dict[str, Any]]:
    pairs = select_riceseg_pairs(project_root)
    items: list[dict[str, Any]] = []
    images_dir = dataset_paths["sources"] / "images"
    masks_dir = dataset_paths["sources"] / "masks"
    images_dir.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)
    for index, (mapped, image_src, mask_src) in enumerate(pairs, start=1):
        item_id = f"riceseg_sample_{index:03d}"
        image_dest = images_dir / f"{item_id}{image_src.suffix.lower()}"
        mask_dest = masks_dir / f"{item_id}_mask{mask_src.suffix.lower()}"
        shutil.copy2(image_src, image_dest)
        shutil.copy2(mask_src, mask_dest)
        width, height, readable = read_image_size(image_dest)
        mask_width, mask_height, mask_readable = read_image_size(mask_dest)
        split = ["train", "val", "test", "train"][index - 1] if index <= 4 else "train"
        items.append(
            {
                "item_id": item_id,
                "dataset_name": "RiceSeg-5932",
                "source_card": "source_card.json",
                "source_path_or_url": str(image_src),
                "annotation_source_path_or_url": str(mask_src),
                "local_path": str(image_dest),
                "annotation_local_path": str(mask_dest),
                "media_type": "image/jpeg",
                "annotation_type": "segmentation_mask",
                "image_width": width,
                "image_height": height,
                "annotation_width": mask_width,
                "annotation_height": mask_height,
                "image_readable": readable,
                "annotation_readable": mask_readable,
                "class_original": image_src.parent.name,
                "class_mapped": mapped,
                "split_candidate": split,
                "license_gate_status": "PASSED",
                "allow_train_smoke": True,
                "allow_formal_train": False,
                "sha256": sha256_file(image_dest),
                "annotation_sha256": sha256_file(mask_dest),
                "file_size": image_dest.stat().st_size,
                "annotation_file_size": mask_dest.stat().st_size,
                "notes": "Copied from existing local raw RiceSeg/Sethy pair into experimental external directory for smoke-only verification.",
            }
        )
    return items


def empty_manifest_item(gate: DatasetGate) -> list[dict[str, Any]]:
    return []


def build_integrity(gate: DatasetGate, items: list[dict[str, Any]], local_counts: dict[str, int]) -> dict[str, Any]:
    sha_values = [item.get("sha256") for item in items if item.get("sha256")]
    duplicate_count = len(sha_values) - len(set(sha_values))
    broken_file_count = sum(1 for item in items if item.get("image_readable") is False)
    broken_annotation_count = sum(1 for item in items if item.get("annotation_local_path") and item.get("annotation_readable") is False)
    license_issue_count = 1 if gate.license_status != "PASSED" else 0
    formal_train_gate_violation = gate.allow_formal_train and gate.license_status != "PASSED"
    allow_smoke_without_items = gate.allow_train_smoke and not items
    pass_status = (
        broken_file_count == 0
        and broken_annotation_count == 0
        and duplicate_count == 0
        and not formal_train_gate_violation
        and not allow_smoke_without_items
    )
    return {
        "dataset_name": gate.dataset_name,
        "gate_status": gate.gate_status,
        "license_status": gate.license_status,
        "local_status": gate.local_status,
        "total_items": len(items),
        "readable_images": sum(1 for item in items if item.get("image_readable") is True),
        "readable_annotations": sum(1 for item in items if item.get("annotation_readable") is True),
        "duplicate_count": duplicate_count,
        "broken_file_count": broken_file_count,
        "broken_annotation_count": broken_annotation_count,
        "license_issue_count": license_issue_count,
        "formal_train_gate_violation": bool(formal_train_gate_violation),
        "allow_smoke_without_items": bool(allow_smoke_without_items),
        "local_existing_counts": local_counts,
        "pass": pass_status,
        "notes": gate.gate_reason,
    }


def local_counts_for_gate(project_root: Path, gate: DatasetGate) -> dict[str, int]:
    suffix_images = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    suffix_annotations = {".txt", ".json", ".xml", ".csv", ".yaml", ".yml"}
    counts: dict[str, int] = {}
    for index, candidate in enumerate(gate.source_local_candidates, start=1):
        root = Path(candidate)
        key = f"candidate_{index}"
        counts[f"{key}_exists"] = 1 if root.exists() else 0
        counts[f"{key}_files"] = count_files(root)
        counts[f"{key}_images"] = count_files(root, suffix_images)
        counts[f"{key}_annotations"] = count_files(root, suffix_annotations)
    return counts


def write_dataset_files(project_root: Path, dataset_root: Path, gate: DatasetGate, generated_at: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    paths = ensure_dirs(dataset_root, gate.slug)
    if gate.slug == "riceseg_5932":
        items = copy_riceseg_samples(project_root, paths)
    else:
        items = empty_manifest_item(gate)

    source_card = make_source_card(gate, generated_at)
    local_counts = local_counts_for_gate(project_root, gate)
    manifest = {
        "dataset_name": gate.dataset_name,
        "slug": gate.slug,
        "generated_at": generated_at,
        "source_card": "source_card.json",
        "license_gate_status": gate.license_status,
        "access_status": gate.access_status,
        "local_status": gate.local_status,
        "items": items,
        "blocked_reason": None if items else gate.gate_reason,
        "local_existing_counts": local_counts,
    }
    class_mapping = {
        "dataset_name": gate.dataset_name,
        "generated_at": generated_at,
        "rules": [
            {
                "dataset_name": gate.dataset_name,
                "original_class": row.get("original_class", ""),
                "mapped_class": row.get("mapped_class", "unknown_or_excluded"),
                "mapped_disease_code": row.get("mapped_disease_code", ""),
                "target_model": gate.task_type,
                "use_case": gate.allowed_next_step,
                "confidence": row.get("confidence", ""),
                "mapping_status": row.get("mapping_status", ""),
                "notes": "P11-1 conservative mapping; do not force unmapped classes.",
            }
            for row in gate.class_mappings
        ],
    }
    split_items = [
        {
            "dataset_name": gate.dataset_name,
            "item_id": item.get("item_id", ""),
            "class_mapped": item.get("class_mapped", ""),
            "split": item.get("split_candidate", ""),
            "split_reason": "sample-only deterministic split; rebuild grouped split before real training",
            "leakage_group": Path(str(item.get("source_path_or_url", ""))).stem,
            "source_hash": item.get("sha256", ""),
            "notes": "No same original image may cross multiple split buckets.",
        }
        for item in items
    ]
    split_plan = {
        "dataset_name": gate.dataset_name,
        "generated_at": generated_at,
        "split_status": gate.split_status,
        "leakage_risk": gate.leakage_risk,
        "items": split_items,
        "blocked_reason": None if split_items else gate.gate_reason,
    }
    integrity = build_integrity(gate, items, local_counts)

    write_json(paths["dataset"] / "source_card.json", source_card)
    (paths["dataset"] / "license_summary.md").write_text(make_license_summary(gate, generated_at), encoding="utf-8")
    write_json(paths["dataset"] / "dataset_manifest.json", manifest)
    write_json(paths["dataset"] / "class_mapping.json", class_mapping)
    write_json(paths["dataset"] / "split_plan.json", split_plan)
    write_json(paths["dataset"] / "integrity_check.json", integrity)
    (paths["dataset"] / "README_LOCAL.md").write_text(
        f"""# {gate.dataset_name}

This directory is a P11-1 experimental external-data gate record.

- Gate status: `{gate.gate_status}`
- License status: `{gate.license_status}`
- Local status: `{gate.local_status}`
- Allowed next step: `{gate.allowed_next_step}`
- allow_train_smoke: `{str(gate.allow_train_smoke).lower()}`
- allow_formal_train: `false`

No backend main-chain code, `.env`, existing model weights, risk_fusion ML path, formal disease probability, pesticide prescription, or dosage advice is changed or produced here.
""",
        encoding="utf-8",
    )

    write_json(paths["source_cards"] / f"{gate.slug}_source_card.json", source_card)
    write_json(paths["manifests"] / f"{gate.slug}_manifest.json", manifest)
    write_json(paths["class_mapping"] / f"{gate.slug}_class_mapping.json", class_mapping)
    write_json(paths["split_plans"] / f"{gate.slug}_split_plan.json", split_plan)
    write_json(paths["integrity"] / f"{gate.slug}_integrity_check.json", integrity)

    return items, integrity


def gate_matrix_row(gate: DatasetGate) -> dict[str, Any]:
    return {
        "dataset_name": gate.dataset_name,
        "task_type": gate.task_type,
        "modality": gate.modality,
        "label_type": gate.label_type,
        "license_status": gate.license_status,
        "access_status": gate.access_status,
        "local_status": gate.local_status,
        "class_mapping_status": gate.class_mapping_status,
        "split_status": gate.split_status,
        "leakage_risk": gate.leakage_risk,
        "train_ready": gate.train_ready,
        "allowed_next_step": gate.allowed_next_step,
    }


def write_reports(project_root: Path, dataset_root: Path, gates: list[DatasetGate], item_map: dict[str, list[dict[str, Any]]], integrity_map: dict[str, dict[str, Any]], generated_at: str) -> None:
    reports = project_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    lines = [
        "# P11-1 Open Dataset Landing Audit",
        "",
        f"Generated at: {generated_at}",
        "",
        "## Scope",
        "",
        "P11-1 performed experimental external-data landing gates only. It did not modify backend main-chain logic, `.env`, existing model weights, risk_fusion logic, formal disease probability outputs, pesticide prescriptions, or dosage advice.",
        "",
        f"Experimental data root: `{dataset_root}`",
        "",
        "## Dataset Results",
        "",
        "| Dataset | License Gate | Local Status | Items | Train Ready | Allowed Next Step | Gate Reason |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for gate in gates:
        lines.append(
            f"| {gate.dataset_name} | {gate.license_status} | {gate.local_status} | {len(item_map[gate.slug])} | {gate.train_ready} | {gate.allowed_next_step} | {gate.gate_reason} |"
        )
    lines.extend(
        [
            "",
            "## Key Findings",
            "",
            "- RiceSeg-5932 has local mask and Sethy source image pairs; four sample pairs were copied into the experimental external-data directory for segmentation pipeline smoke only.",
            "- Rice Leaf Bacterial and Fungal Disease has clear CC BY 4.0 source metadata, but exact raw samples were not locally landed in this run; it remains sample-gated.",
            "- Rice Disease bbox has a clear CC0 signal on Dataset Ninja, but the local Kaggle zip placeholder is not usable; it remains sample-gated.",
            "- Aligned RGB+MS Weedy Rice is allowed only for MS pipeline smoke / NDVI / NDRE calculation verification / migration pretraining. It is not disease training data.",
            "- BLB UAV Dataset has local existing files, but the dataset license gate is still blocked. Local files were counted only; they are not released for training.",
            "- risk_fusion_tabular_shadow_model = BLOCKED_FOR_LABELS because public image datasets do not provide field-level final decision labels.",
            "",
            "## Safety Boundary",
            "",
            "No dataset in this P11-1 gate is allowed to produce formal disease probability, diagnosis, pesticide prescription, dosage advice, or risk_fusion ML training.",
        ]
    )
    (reports / "p11_1_open_dataset_landing_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    matrix_rows = [gate_matrix_row(gate) for gate in gates]
    matrix_lines = [
        "# P11-1 Training Gate Matrix",
        "",
        f"Generated at: {generated_at}",
        "",
        "| dataset_name | task_type | modality | label_type | license_status | access_status | local_status | class_mapping_status | split_status | leakage_risk | train_ready | allowed_next_step |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in matrix_rows:
        matrix_lines.append(
            "| "
            + " | ".join(str(row[key]).replace("|", "/") for key in [
                "dataset_name",
                "task_type",
                "modality",
                "label_type",
                "license_status",
                "access_status",
                "local_status",
                "class_mapping_status",
                "split_status",
                "leakage_risk",
                "train_ready",
                "allowed_next_step",
            ])
            + " |"
        )
    matrix_lines.extend(
        [
            "",
            "## Immediate Decisions",
            "",
            "- Immediate smoke-ready: RiceSeg-5932 segmentation pipeline smoke only.",
            "- Smoke allowed after small sample download: Rice Leaf Bacterial and Fungal Disease, Rice Disease bbox.",
            "- MS pipeline only after sample download: Aligned RGB+MS Weedy Rice.",
            "- Blocked: BLB UAV Dataset for any training until dataset license is explicitly confirmed.",
        ]
    )
    (reports / "p11_1_training_gate_matrix.md").write_text("\n".join(matrix_lines) + "\n", encoding="utf-8")

    write_json(dataset_root / "p11_1_training_gate_matrix.json", matrix_rows)
    write_json(dataset_root / "p11_1_integrity_summary.json", integrity_map)


def run(project_root: Path) -> dict[str, Any]:
    generated_at = utc_now()
    dataset_root = project_root / DATASET_ROOT_NAME
    dataset_root.mkdir(parents=True, exist_ok=True)
    gates = dataset_definitions(project_root)
    item_map: dict[str, list[dict[str, Any]]] = {}
    integrity_map: dict[str, dict[str, Any]] = {}
    for gate in gates:
        items, integrity = write_dataset_files(project_root, dataset_root, gate, generated_at)
        item_map[gate.slug] = items
        integrity_map[gate.slug] = integrity
    write_reports(project_root, dataset_root, gates, item_map, integrity_map, generated_at)
    return {
        "generated_at": generated_at,
        "dataset_root": str(dataset_root),
        "datasets": [
            {
                "slug": gate.slug,
                "dataset_name": gate.dataset_name,
                "items": len(item_map[gate.slug]),
                "gate_status": gate.gate_status,
                "train_ready": gate.train_ready,
                "allowed_next_step": gate.allowed_next_step,
            }
            for gate in gates
        ],
        "integrity_pass": all(item["pass"] for item in integrity_map.values()),
        "risk_fusion_tabular_shadow_model": "BLOCKED_FOR_LABELS",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate P11-1 dataset landing gates and integrity reports.")
    parser.add_argument("--project-root", default=str(project_root_from_script()))
    args = parser.parse_args()
    summary = run(Path(args.project_root).resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
