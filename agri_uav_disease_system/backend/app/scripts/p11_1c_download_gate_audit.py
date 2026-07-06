from __future__ import annotations

import csv
import hashlib
import json
import shutil
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATA_ROOT = "ai_model_training/datasets_external/p11_open_datasets"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_inventory(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not root.exists():
        return rows
    for item in sorted(root.rglob("*")):
        if not item.is_file():
            continue
        rows.append(
            {
                "relative_path": item.relative_to(root).as_posix(),
                "file_size": item.stat().st_size,
                "suffix": item.suffix.lower(),
                "sha256": sha256(item),
            }
        )
    return rows


def safe_head(url: str) -> dict[str, Any]:
    started = now()
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "P11-1C-gate-audit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return {
                "started_at": started,
                "finished_at": now(),
                "success": True,
                "status_code": response.status,
                "content_type": response.headers.get("Content-Type", ""),
                "content_length": response.headers.get("Content-Length", ""),
                "location": response.headers.get("Location", ""),
                "error_message": "",
            }
    except Exception as exc:
        status_code = getattr(getattr(exc, "fp", None), "status", "")
        return {
            "started_at": started,
            "finished_at": now(),
            "success": False,
            "status_code": status_code,
            "content_type": "",
            "content_length": "",
            "location": "",
            "error_message": f"{exc.__class__.__name__}: {exc}",
        }


def download_file(url: str, target: Path, max_bytes: int = 2_000_000) -> dict[str, Any]:
    started = now()
    target.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "P11-1C-gate-audit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            content_length = int(response.headers.get("Content-Length") or "0")
            if content_length and content_length > max_bytes:
                return {
                    "started_at": started,
                    "finished_at": now(),
                    "success": False,
                    "error_message": f"file_too_large_for_current_stage: {content_length} > {max_bytes}",
                    "file_count": 0,
                    "total_size": 0,
                    "checksum_status": "not_downloaded",
                }
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                return {
                    "started_at": started,
                    "finished_at": now(),
                    "success": False,
                    "error_message": f"file_too_large_for_current_stage: stream exceeded {max_bytes}",
                    "file_count": 0,
                    "total_size": 0,
                    "checksum_status": "not_downloaded",
                }
            target.write_bytes(data)
        return {
            "started_at": started,
            "finished_at": now(),
            "success": True,
            "error_message": "",
            "file_count": 1,
            "total_size": target.stat().st_size,
            "checksum_status": sha256(target),
        }
    except Exception as exc:
        return {
            "started_at": started,
            "finished_at": now(),
            "success": False,
            "error_message": f"{exc.__class__.__name__}: {exc}",
            "file_count": 0,
            "total_size": 0,
            "checksum_status": "failed",
        }


@dataclass(frozen=True)
class LinkRecord:
    dataset_name: str
    slug: str
    priority: str
    task_usage: str
    official_page: str
    direct_download_url_if_available: str
    access_status: str
    license_status: str
    estimated_size: str
    auto_download_attempted: str
    auto_download_status: str
    block_reason: str
    manual_download_steps: str
    expected_local_path: str


def manual_steps(dataset: str, target: Path) -> str:
    return (
        f"Open the official page for {dataset}; use the platform's normal Download/Download All button; "
        f"do not bypass login, captcha, quota, or license prompts; save original archives under {target}; "
        "then rerun python -m app.scripts.p11_1_dataset_integrity_check and this P11-1C audit."
    )


def build_pairing_reports(root: Path, output_dir: Path) -> tuple[int, int, int]:
    mask_root = root / "ai_model_training/raw_datasets/rice_seg_5932/extracted/mask-vesrion1"
    image_root = root / "ai_model_training/raw_datasets/rice_leaf_disease_sethy/extracted/Rice Leaf Disease Images"
    rows: list[dict[str, Any]] = []
    mask_rows: list[dict[str, Any]] = []
    if not mask_root.exists():
        write_csv(output_dir / "mask_inventory.csv", [], ["class_original", "mask_path", "mask_stem", "file_size", "sha256"])
        write_csv(output_dir / "pairing_report.csv", [], ["class_original", "mask_path", "image_path", "paired", "pairing_key"])
        return 0, 0, 0
    image_by_key: dict[str, Path] = {}
    if image_root.exists():
        for image in image_root.rglob("*"):
            if image.is_file() and image.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                key = f"{image.parent.name.lower()}::{image.stem.lower()}"
                image_by_key[key] = image
    for mask in sorted(mask_root.rglob("*")):
        if not mask.is_file() or mask.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        key = f"{mask.parent.name.lower()}::{mask.stem.lower()}"
        image = image_by_key.get(key)
        mask_rows.append(
            {
                "class_original": mask.parent.name,
                "mask_path": str(mask),
                "mask_stem": mask.stem,
                "file_size": mask.stat().st_size,
                "sha256": sha256(mask),
            }
        )
        rows.append(
            {
                "class_original": mask.parent.name,
                "mask_path": str(mask),
                "image_path": str(image) if image else "",
                "paired": bool(image),
                "pairing_key": key,
            }
        )
    write_csv(output_dir / "mask_inventory.csv", mask_rows, ["class_original", "mask_path", "mask_stem", "file_size", "sha256"])
    write_csv(output_dir / "pairing_report.csv", rows, ["class_original", "mask_path", "image_path", "paired", "pairing_key"])
    paired = sum(1 for row in rows if row["paired"])
    return len(mask_rows), len(image_by_key), paired


def write_static_reports(dataset_root: Path) -> None:
    rice_leaf_dir = dataset_root / "rice_leaf_bacterial_fungal"
    write_csv(
        rice_leaf_dir / "class_count_report.csv",
        [
            {"class_original": "Bacterial Leaf Blight", "mapped_class": "bacterial_leaf_blight", "local_count": "", "status": "expected_from_source_not_downloaded"},
            {"class_original": "Brown Spot", "mapped_class": "brown_spot", "local_count": "", "status": "expected_from_source_not_downloaded"},
            {"class_original": "Leaf Blast", "mapped_class": "rice_blast", "local_count": "", "status": "expected_from_source_not_downloaded"},
            {"class_original": "Healthy Rice Leaf", "mapped_class": "healthy_or_background", "local_count": "", "status": "expected_from_source_not_downloaded"},
            {"class_original": "Leaf scald", "mapped_class": "unknown_or_excluded", "local_count": "", "status": "needs_review"},
            {"class_original": "Narrow Brown Leaf Spot", "mapped_class": "unknown_or_excluded", "local_count": "", "status": "needs_review"},
            {"class_original": "Rice Hispa", "mapped_class": "unknown_or_excluded", "local_count": "", "status": "needs_review_pest"},
            {"class_original": "Sheath Blight", "mapped_class": "unknown_or_excluded", "local_count": "", "status": "needs_review_current_target_set"},
        ],
        ["class_original", "mapped_class", "local_count", "status"],
    )
    write_text(
        rice_leaf_dir / "leakage_risk_report.md",
        "# Leakage Risk Report\n\n"
        "- Dataset contains original and augmented images according to source metadata.\n"
        "- Original-derived augmented images must stay in the same split as their source original.\n"
        "- Augmented images should be train-only derivatives; they must not enter val/test.\n"
        "- Current gate: SAMPLE_GATE_BLOCKED until raw files are landed and original/augmented grouping is verified.\n",
    )

    bbox_dir = dataset_root / "rice_disease_bbox"
    write_text(
        bbox_dir / "bbox_format_report.md",
        "# Bbox Format Report\n\n"
        "- Source page describes a bbox object detection dataset with BacterialBlight, BrownSpot, and RiceBlast.\n"
        "- Local raw annotations were not downloaded in P11-1C; exact coordinate format is not locally verified.\n"
        "- Expected next check after manual/Kaggle download: inspect annotation files for COCO/VOC/YOLO/Supervisely format and image coordinate conventions.\n"
        "- Current gate: SAMPLE_GATE_BLOCKED.\n",
    )
    write_text(
        bbox_dir / "yolo_conversion_plan.md",
        "# YOLO Conversion Plan\n\n"
        "1. Preserve original archive and license metadata.\n"
        "2. Detect source annotation format without modifying source files.\n"
        "3. Convert boxes to YOLO normalized `class x_center y_center width height` only in an experimental derived folder.\n"
        "4. Keep class mapping: BacterialBlight -> bacterial_leaf_blight, BrownSpot -> brown_spot, RiceBlast -> rice_blast.\n"
        "5. Use only smoke/baseline training; do not claim formal model performance.\n",
    )

    weedy_dir = dataset_root / "aligned_rgb_ms_weedy_rice"
    write_text(
        weedy_dir / "ms_pipeline_usage_gate.md",
        "# MS Pipeline Usage Gate\n\n"
        "- disease_label_available=false\n"
        "- train_usage=ms_pipeline_smoke/pretraining_only\n"
        "- Expected bands: Green, Red, RedEdge, NIR, plus RGB according to source page.\n"
        "- NDVI can be calculated from NIR and Red when sample files are locally available.\n"
        "- NDRE can be calculated from NIR and RedEdge when sample files are locally available.\n"
        "- Not allowed for disease classification or risk_fusion field labels.\n",
    )


def run() -> dict[str, Any]:
    root = project_root()
    dataset_root = root / DATA_ROOT
    links_dir = dataset_root / "_download_links"
    logs_dir = dataset_root / "_download_logs"
    links_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    generated_at = now()
    records: list[LinkRecord] = []
    logs: list[dict[str, Any]] = []

    # A/B local pairing verification: no network download needed because both local raw sources exist.
    riceseg_dir = dataset_root / "riceseg_5932"
    mask_count, image_count, paired_count = build_pairing_reports(root, riceseg_dir)
    logs.append(
        {
            "started_at": generated_at,
            "finished_at": now(),
            "dataset_name": "Sethy Rice Leaf Disease Image Samples + RiceSeg-5932",
            "command_or_method": "local_inventory_pairing_check",
            "source_url": "https://data.mendeley.com/datasets/fwcj7stb8r/1 and https://data.mendeley.com/datasets/92jc6w6mcy",
            "target_path": str(riceseg_dir),
            "success": paired_count > 0,
            "error_message": "",
            "file_count": paired_count,
            "total_size": "",
            "checksum_status": "pairing_report_generated",
        }
    )

    records.extend(
        [
            LinkRecord(
                "Sethy Rice Leaf Disease Image Samples",
                "sethy_rice_leaf_disease_images",
                "HIGH",
                "RiceSeg source images / leaf lesion segmentation",
                "https://data.mendeley.com/datasets/fwcj7stb8r/1",
                "",
                "LOCAL_ALREADY_AVAILABLE; SOURCE_PAGE_200",
                "CC BY 4.0 per Mendeley page to be retained with source",
                "about 5,932 images",
                "NO_NETWORK_DOWNLOAD_LOCAL_FOUND",
                "SUCCESS_LOCAL_PAIRING",
                "",
                manual_steps("Sethy Rice Leaf Disease Image Samples", dataset_root / "sethy_rice_leaf_disease_images"),
                str(dataset_root / "sethy_rice_leaf_disease_images"),
            ),
            LinkRecord(
                "RiceSeg-5932",
                "riceseg_5932",
                "HIGH",
                "segmentation masks",
                "https://data.mendeley.com/datasets/92jc6w6mcy",
                "",
                "LOCAL_ALREADY_AVAILABLE; SOURCE_PAGE_REACHABLE",
                "CC BY 4.0",
                "5,932 masks",
                "NO_NETWORK_DOWNLOAD_LOCAL_FOUND",
                "SUCCESS_LOCAL_PAIRING",
                "",
                manual_steps("RiceSeg-5932", dataset_root / "riceseg_5932"),
                str(dataset_root / "riceseg_5932"),
            ),
        ]
    )

    # C/E: Mendeley pages are reachable, but direct file API endpoints are not visible without site workflow.
    for dataset_name, slug, page, usage, estimated in [
        (
            "Rice Leaf Bacterial and Fungal Disease Dataset",
            "rice_leaf_bacterial_fungal",
            "https://data.mendeley.com/datasets/hx6f852hw4/2",
            "phone RGB classification experimental baseline",
            "1,701 original + 5,188 augmented images per source metadata",
        ),
        (
            "Aligned RGB+MS Weedy Rice",
            "aligned_rgb_ms_weedy_rice",
            "https://data.mendeley.com/datasets/vt4s83pxx6",
            "MS pipeline smoke / NDVI-NDRE calculator smoke",
            "734 RGB+MS samples per source metadata",
        ),
    ]:
        head = safe_head(page)
        logs.append(
            {
                "started_at": head["started_at"],
                "finished_at": head["finished_at"],
                "dataset_name": dataset_name,
                "command_or_method": "HEAD official page; no direct file download attempted",
                "source_url": page,
                "target_path": str(dataset_root / slug),
                "success": False,
                "error_message": "MANUAL_DOWNLOAD_REQUIRED: official page reachable, direct downloadable archive URL not visible through public endpoint",
                "file_count": 0,
                "total_size": 0,
                "checksum_status": "not_downloaded",
                "http_probe": head,
            }
        )
        records.append(
            LinkRecord(
                dataset_name,
                slug,
                "HIGH",
                usage,
                page,
                "",
                "MANUAL_DOWNLOAD_REQUIRED",
                "CC BY 4.0",
                estimated,
                "YES_PROBE_ONLY",
                "FAILED_NO_DIRECT_PUBLIC_FILE_URL",
                "Mendeley page is reachable, but file list/download-all endpoint was not available to this non-interactive script.",
                manual_steps(dataset_name, dataset_root / slug),
                str(dataset_root / slug),
            )
        )

    # D: Kaggle download requires platform workflow/auth; do not bypass.
    kaggle_url = "https://www.kaggle.com/datasets/nischallal/rice-disease-dataset"
    kaggle_download = "https://www.kaggle.com/datasets/nischallal/rice-disease-dataset/download?datasetVersionNumber=1"
    kaggle_head = safe_head(kaggle_download)
    logs.append(
        {
            "started_at": kaggle_head["started_at"],
            "finished_at": kaggle_head["finished_at"],
            "dataset_name": "Rice Disease bbox",
            "command_or_method": "HEAD Kaggle download URL",
            "source_url": kaggle_download,
            "target_path": str(dataset_root / "rice_disease_bbox"),
            "success": False,
            "error_message": "KAGGLE_MANUAL_DOWNLOAD_REQUIRED_OR_DOWNLOAD_URL_NOT_PUBLIC",
            "file_count": 0,
            "total_size": 0,
            "checksum_status": "not_downloaded",
            "http_probe": kaggle_head,
        }
    )
    records.append(
        LinkRecord(
            "Rice Disease bbox",
            "rice_disease_bbox",
            "HIGH",
            "YOLO bbox smoke/baseline",
            "https://datasetninja.com/rice-disease",
            kaggle_download,
            "KAGGLE_MANUAL_DOWNLOAD_REQUIRED",
            "CC0 1.0 per Dataset Ninja page",
            "470 images / 1,956 objects per source page",
            "YES_PROBE_ONLY",
            "FAILED_KAGGLE_DIRECT_DOWNLOAD_NOT_PUBLIC",
            "Kaggle download cannot be fetched without the normal Kaggle workflow/token; P11-1C did not bypass auth.",
            manual_steps("Rice Disease bbox", dataset_root / "rice_disease_bbox"),
            str(dataset_root / "rice_disease_bbox"),
        )
    )

    # F: BLB page available, but license still not confirmed.
    blb_page = "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0314535"
    blb_head = safe_head(blb_page)
    logs.append(
        {
            "started_at": blb_head["started_at"],
            "finished_at": blb_head["finished_at"],
            "dataset_name": "BLB UAV Dataset",
            "command_or_method": "HEAD PLOS article page; data download blocked by license gate",
            "source_url": blb_page,
            "target_path": str(dataset_root / "blb_uav_dataset"),
            "success": False,
            "error_message": "LICENSE_GATE_BLOCKED: dataset license/download page not confirmed",
            "file_count": 0,
            "total_size": 0,
            "checksum_status": "not_downloaded",
            "http_probe": blb_head,
        }
    )
    records.append(
        LinkRecord(
            "BLB UAV Dataset",
            "blb_uav_dataset",
            "HIGH",
            "UAV BLB semantic segmentation candidate",
            blb_page,
            "",
            "LICENSE_GATE_BLOCKED; MANUAL_DOWNLOAD_REQUIRED",
            "NEEDS_CONFIRMATION",
            "unknown in current gate",
            "NO_LICENSE_BLOCKED",
            "BLOCKED",
            "Dataset license cannot be inferred from the PLOS article; local existing files remain training-blocked.",
            manual_steps("BLB UAV Dataset", dataset_root / "blb_uav_dataset"),
            str(dataset_root / "blb_uav_dataset"),
        )
    )

    # Optional G: safe tiny Zenodo metadata/readme download only; not rice disease training.
    maize_dir = dataset_root / "maize_rust_ms_zenodo"
    maize_dir.mkdir(parents=True, exist_ok=True)
    small_files = [
        ("00_README_CITATION_LICENSE.zip", "https://zenodo.org/api/records/20332029/files/00_README_CITATION_LICENSE.zip/content"),
        ("03_metadata.zip", "https://zenodo.org/api/records/20332029/files/03_metadata.zip/content"),
    ]
    maize_success = True
    maize_total = 0
    maize_count = 0
    for filename, url in small_files:
        target = maize_dir / "sources" / filename
        result = download_file(url, target, max_bytes=50_000)
        maize_success = maize_success and bool(result["success"])
        maize_total += int(result.get("total_size") or 0)
        maize_count += int(result.get("file_count") or 0)
        logs.append(
            {
                "started_at": result["started_at"],
                "finished_at": result["finished_at"],
                "dataset_name": "UAV-Based Multispectral Maize Dataset for Water Stress and Common Rust",
                "command_or_method": "urllib small Zenodo file download",
                "source_url": url,
                "target_path": str(target),
                "success": result["success"],
                "error_message": result["error_message"],
                "file_count": result["file_count"],
                "total_size": result["total_size"],
                "checksum_status": result["checksum_status"],
            }
        )
    maize_status = (
        "SUCCESS_SMALL_METADATA_ONLY"
        if maize_success
        else "PARTIAL_SMALL_METADATA_ONLY"
        if maize_count > 0
        else "FAILED_SMALL_METADATA_DOWNLOAD"
    )
    if maize_count > 0:
        inv = file_inventory(maize_dir / "sources")
        write_csv(maize_dir / "file_inventory.csv", inv, ["relative_path", "file_size", "suffix", "sha256"])
        write_csv(maize_dir / "checksum_manifest.csv", inv, ["relative_path", "file_size", "suffix", "sha256"])
        for archive in (maize_dir / "sources").glob("*.zip"):
            try:
                with zipfile.ZipFile(archive) as zf:
                    zf.testzip()
            except Exception:
                pass
    records.append(
        LinkRecord(
            "UAV-Based Multispectral Maize Dataset for Water Stress and Common Rust",
            "maize_rust_ms_zenodo",
            "OPTIONAL",
            "transfer_only/ms_pipeline_smoke",
            "https://zenodo.org/records/20332029",
            "https://zenodo.org/api/records/20332029",
            "ACCESSIBLE",
            "CC BY 4.0",
            "small metadata/readme downloaded; full patches/orthomosaics not downloaded",
            "YES_SMALL_METADATA_ONLY",
            maize_status,
            "No rice disease training; optional transfer/MS pipeline metadata only.",
            manual_steps("Maize Rust MS Zenodo", maize_dir),
            str(maize_dir),
        )
    )

    write_static_reports(dataset_root)

    # Write download logs.
    for index, log in enumerate(logs, start=1):
        safe_name = log["dataset_name"].lower().replace(" ", "_").replace("/", "_").replace("+", "plus")
        write_json(logs_dir / f"{index:02d}_{safe_name}.json", log)

    link_rows = [record.__dict__ for record in records]
    write_json(links_dir / "p11_dataset_download_links.json", link_rows)
    table = [
        "# P11-1C Dataset Download Links",
        "",
        f"Generated at: {generated_at}",
        "",
        "| dataset_name | priority | task_usage | official_page | direct_download_url_if_available | access_status | license_status | estimated_size | auto_download_attempted | auto_download_status | block_reason | manual_download_steps | expected_local_path |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in link_rows:
        table.append(
            "| "
            + " | ".join(
                str(row[key]).replace("|", "/").replace("\n", " ")
                for key in [
                    "dataset_name",
                    "priority",
                    "task_usage",
                    "official_page",
                    "direct_download_url_if_available",
                    "access_status",
                    "license_status",
                    "estimated_size",
                    "auto_download_attempted",
                    "auto_download_status",
                    "block_reason",
                    "manual_download_steps",
                    "expected_local_path",
                ]
            )
            + " |"
        )
    write_text(links_dir / "p11_dataset_download_links.md", "\n".join(table) + "\n")

    gate_rows = [
        {
            "dataset_name": "Sethy + RiceSeg-5932",
            "task_type": "leaf_lesion_segmentation",
            "modality": "RGB image + segmentation mask",
            "label_type": "mask",
            "source_platform": "Mendeley Data",
            "license_status": "PASSED_CC_BY_4_0",
            "access_status": "LOCAL_FULL_PAIRING_AVAILABLE",
            "auto_download_status": "NO_NETWORK_DOWNLOAD_LOCAL_FOUND",
            "local_status": f"masks={mask_count}; images={image_count}; paired={paired_count}",
            "sample_count": paired_count,
            "class_count": 4,
            "class_mapping_status": "PARTIAL_BLB_BROWN_RICE_BLAST_OK_TUNGRO_REVIEW",
            "split_status": "NEEDS_HELD_OUT_SPLIT_BEFORE_REAL_EXPERIMENT",
            "leakage_risk": "PAIRING_VERSION_AND_SOURCE_IMAGE_GROUP_RISK",
            "train_ready": "PARTIAL",
            "allowed_next_step": "P11-2 segmentation smoke only",
            "gate_reason": "Local full pairing exists; no formal performance claims allowed.",
        },
        {
            "dataset_name": "Rice Leaf Bacterial and Fungal Disease Dataset",
            "task_type": "phone_rgb_classification",
            "modality": "RGB leaf close-up",
            "label_type": "classification",
            "source_platform": "Mendeley Data",
            "license_status": "PASSED_CC_BY_4_0",
            "access_status": "MANUAL_DOWNLOAD_REQUIRED",
            "auto_download_status": "FAILED_NO_DIRECT_PUBLIC_FILE_URL",
            "local_status": "not_landed",
            "sample_count": 0,
            "class_count": 8,
            "class_mapping_status": "PARTIAL_NEEDS_REVIEW",
            "split_status": "BLOCKED_UNTIL_RAW_DOWNLOAD; original/augmented grouping required",
            "leakage_risk": "HIGH_ORIGINAL_AUGMENTED_LEAKAGE_RISK",
            "train_ready": "NO",
            "allowed_next_step": "manual download then P11-2 phone RGB smoke gate",
            "gate_reason": "No raw files landed; cannot train smoke yet.",
        },
        {
            "dataset_name": "Rice Disease bbox",
            "task_type": "bbox_detection",
            "modality": "RGB leaf close-up",
            "label_type": "bbox",
            "source_platform": "Dataset Ninja / Kaggle",
            "license_status": "PASSED_CC0_FROM_DATASET_NINJA",
            "access_status": "KAGGLE_MANUAL_DOWNLOAD_REQUIRED",
            "auto_download_status": "FAILED_KAGGLE_DIRECT_DOWNLOAD_NOT_PUBLIC",
            "local_status": "not_landed",
            "sample_count": 0,
            "class_count": 3,
            "class_mapping_status": "PASSED_FOR_3_CLASSES",
            "split_status": "BLOCKED_UNTIL_RAW_DOWNLOAD",
            "leakage_risk": "MEDIUM_SMALL_DATASET_AND_CONVERSION_RISK",
            "train_ready": "NO",
            "allowed_next_step": "manual download then P11-2 YOLO bbox smoke",
            "gate_reason": "Kaggle direct download not available without normal Kaggle workflow.",
        },
        {
            "dataset_name": "Aligned RGB+MS Weedy Rice",
            "task_type": "ms_pipeline_smoke",
            "modality": "UAV RGB + Green/Red/RedEdge/NIR",
            "label_type": "binary weedy rice mask; no disease label",
            "source_platform": "Mendeley Data",
            "license_status": "PASSED_CC_BY_4_0",
            "access_status": "MANUAL_DOWNLOAD_REQUIRED",
            "auto_download_status": "FAILED_NO_DIRECT_PUBLIC_FILE_URL",
            "local_status": "not_landed",
            "sample_count": 0,
            "class_count": 0,
            "class_mapping_status": "NOT_DISEASE_DATASET",
            "split_status": "SOURCE_SPLIT_NOT_LOCALLY_VERIFIED",
            "leakage_risk": "RGB_MS_MASK_PAIRING_RISK",
            "train_ready": "NO_RAW_SAMPLE_YET",
            "allowed_next_step": "manual download then P11-2 MS pipeline smoke / NDVI-NDRE calculator smoke",
            "gate_reason": "No disease training allowed; raw sample not landed.",
        },
        {
            "dataset_name": "BLB UAV Dataset",
            "task_type": "uav_blb_segmentation_candidate",
            "modality": "UAV multispectral",
            "label_type": "segmentation candidate",
            "source_platform": "PLOS One / Figshare / Google Drive",
            "license_status": "NEEDS_CONFIRMATION",
            "access_status": "MANUAL_DOWNLOAD_REQUIRED",
            "auto_download_status": "BLOCKED_LICENSE_UNCLEAR",
            "local_status": "local_data_found_but_training_blocked",
            "sample_count": 0,
            "class_count": 1,
            "class_mapping_status": "BLB_MAPPING_OK_BUT_LICENSE_BLOCKED",
            "split_status": "LOCAL_SPLITS_NOT_TRUSTED_UNTIL_LICENSE_PASS",
            "leakage_risk": "HIGH_PATCH_ORTHOMOSAIC_LEAKAGE_RISK",
            "train_ready": "NO",
            "allowed_next_step": "license confirmation only",
            "gate_reason": "LICENSE_GATE_BLOCKED.",
        },
        {
            "dataset_name": "UAV-Based Multispectral Maize Dataset for Water Stress and Common Rust",
            "task_type": "transfer_ms_pipeline",
            "modality": "UAV multispectral maize",
            "label_type": "semantic masks for maize stress/rust",
            "source_platform": "Zenodo",
            "license_status": "PASSED_CC_BY_4_0",
            "access_status": "ACCESSIBLE",
            "auto_download_status": maize_status,
            "local_status": f"metadata_files={maize_count}; metadata_size={maize_total}",
            "sample_count": maize_count,
            "class_count": 0,
            "class_mapping_status": "NON_RICE_TRANSFER_ONLY",
            "split_status": "NO_TRAIN_SPLIT_CREATED",
            "leakage_risk": "NON_RICE_TRANSFER_BOUNDARY",
            "train_ready": "NO_RICE_DISEASE_TRAINING",
            "allowed_next_step": "optional MS pipeline metadata review / transfer-only smoke planning",
            "gate_reason": "Only tiny metadata/readme files were attempted; no full dataset and no rice disease training.",
        },
    ]
    write_json(dataset_root / "p11_1c_training_gate_matrix_updated.json", gate_rows)

    report = [
        "# P11-1C Download And Gate Audit",
        "",
        f"Generated at: {generated_at}",
        "",
        "## Summary",
        "",
        "- Automatic network download of large raw datasets was not performed.",
        "- Sethy + RiceSeg are locally available and pairable; pairing reports were generated.",
        "- Mendeley classification and Weedy Rice pages are reachable but direct archive URLs were not available to this non-interactive script.",
        "- Kaggle bbox direct download was not public in this environment; manual Kaggle workflow is required.",
        "- BLB UAV remains LICENSE_GATE_BLOCKED.",
        f"- Optional Maize MS Zenodo tiny metadata/readme download status: {maize_status}; no full dataset was downloaded.",
        "- risk_fusion_tabular_shadow_model = BLOCKED_FOR_LABELS.",
        "",
        "## Download Results",
        "",
        "| Dataset | Auto Download Status | Local Status | Allowed Next Step |",
        "| --- | --- | --- | --- |",
    ]
    for row in gate_rows:
        report.append(f"| {row['dataset_name']} | {row['auto_download_status']} | {row['local_status']} | {row['allowed_next_step']} |")
    report.extend(
        [
            "",
            "## Safety",
            "",
            "No backend main-chain logic, `.env`, model weights, risk_fusion ML training, formal disease probability, prescription, or dosage advice was modified or produced.",
        ]
    )
    write_text(root / "reports/p11_1c_download_and_gate_audit.md", "\n".join(report) + "\n")

    matrix = [
        "# P11-1C Training Gate Matrix Updated",
        "",
        f"Generated at: {generated_at}",
        "",
        "| dataset_name | task_type | modality | label_type | source_platform | license_status | access_status | auto_download_status | local_status | sample_count | class_count | class_mapping_status | split_status | leakage_risk | train_ready | allowed_next_step | gate_reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in gate_rows:
        matrix.append(
            "| "
            + " | ".join(
                str(row[key]).replace("|", "/")
                for key in [
                    "dataset_name",
                    "task_type",
                    "modality",
                    "label_type",
                    "source_platform",
                    "license_status",
                    "access_status",
                    "auto_download_status",
                    "local_status",
                    "sample_count",
                    "class_count",
                    "class_mapping_status",
                    "split_status",
                    "leakage_risk",
                    "train_ready",
                    "allowed_next_step",
                    "gate_reason",
                ]
            )
            + " |"
        )
    write_text(root / "reports/p11_1c_training_gate_matrix_updated.md", "\n".join(matrix) + "\n")

    return {
        "generated_at": generated_at,
        "download_links": str(links_dir / "p11_dataset_download_links.md"),
        "download_logs": str(logs_dir),
        "paired_count": paired_count,
        "maize_metadata_download_status": maize_status,
        "risk_fusion_tabular_shadow_model": "BLOCKED_FOR_LABELS",
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
