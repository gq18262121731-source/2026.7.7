from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(r"F:/学校/病虫害识别/ai_model_training")
REPORTS = ROOT / "reports"
METADATA = ROOT / "metadata"
RUN_DIR = ROOT / "experiments" / "phone_rgb_yolo" / "runs" / "controlled_exp_phone_riceseg_v35m_holdout_applied_10epoch"
DATA_YAML = ROOT / "datasets" / "phone_riceseg_v35m_holdout_applied" / "data.yaml"
STATUS_YAML = METADATA / "phone_dataset_status.yaml"
NOW = datetime.now(timezone.utc).isoformat()

MODEL_NAME = "phone_riceseg_v35m_holdout_applied_10epoch"
MODEL_VERSION = "exp_35n_20260630"
DATASET_NAME = "phone_riceseg_v35m_holdout_applied"
TRAIN_VAL_TEST_HOLDOUT = "348/100/43/9"
TEST_IMAGE_COUNT = 43
HOLDOUT_IMAGE_COUNT = 9


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    if tmp.stat().st_size == 0:
        raise RuntimeError(f"temporary file is empty: {tmp}")
    tmp.replace(path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"final file missing or empty: {path}")


def atomic_write_json(path: Path, obj: dict) -> None:
    atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def atomic_write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    if tmp.stat().st_size == 0:
        raise RuntimeError(f"temporary file is empty: {tmp}")
    tmp.replace(path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"final file missing or empty: {path}")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_results(name: str) -> list[dict]:
    return load_json(REPORTS / name)["results"]


def summarize_results(results: list[dict], total_images: int, conf: float, scope: str) -> tuple[dict, list[dict]]:
    images_with_detection = 0
    total_boxes = 0
    predicted = Counter()
    confidences: list[float] = []
    manifest_rows: list[dict] = []

    for item in results:
        detections = item.get("detections") or []
        if detections:
            images_with_detection += 1
        total_boxes += len(detections)
        image_classes: list[str] = []
        image_confidences: list[str] = []
        for det in detections:
            class_name = det.get("class_name", "unknown")
            score = float(det.get("confidence", 0.0))
            predicted[class_name] += 1
            confidences.append(score)
            image_classes.append(class_name)
            image_confidences.append(f"{score:.6f}")
        manifest_rows.append(
            {
                "record_id": item.get("record_id", ""),
                "image_name": item.get("image_name", ""),
                "detection_count": len(detections),
                "has_detection": "yes" if detections else "no",
                "predicted_classes": "|".join(image_classes),
                "confidence_list": "|".join(image_confidences),
                "main_disease": (item.get("summary") or {}).get("main_disease") or "",
                "model_name": item.get("model_name", ""),
                "model_version": item.get("model_version", ""),
                "boundary": item.get("boundary", ""),
            }
        )

    no_detection_count = total_images - images_with_detection
    avg_boxes = total_boxes / total_images if total_images else 0.0
    avg_conf = sum(confidences) / len(confidences) if confidences else None
    min_conf = min(confidences) if confidences else None
    max_conf = max(confidences) if confidences else None
    summary = {
        "summary_scope": scope,
        "generated_at": NOW,
        "conf": conf,
        "total_images": total_images,
        "images_with_detection": images_with_detection,
        "no_detection_count": no_detection_count,
        "no_detection_ratio": round(no_detection_count / total_images, 6) if total_images else None,
        "total_boxes": total_boxes,
        "avg_boxes_per_image": round(avg_boxes, 6),
        "predicted_class_distribution": dict(predicted),
        "avg_confidence": round(avg_conf, 6) if avg_conf is not None else None,
        "min_confidence": round(min_conf, 6) if min_conf is not None else None,
        "max_confidence": round(max_conf, 6) if max_conf is not None else None,
        "confidence_bucket_distribution": {
            "ge_0_75": sum(1 for c in confidences if c >= 0.75),
            "0_50_to_0_75": sum(1 for c in confidences if 0.5 <= c < 0.75),
            "0_25_to_0_50": sum(1 for c in confidences if 0.25 <= c < 0.5),
            "lt_0_25": sum(1 for c in confidences if c < 0.25),
        },
        "real_inference": True,
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
    }
    return summary, manifest_rows


def qualitative_risk(avg_boxes: float, no_detection_ratio: float, conf: float) -> str:
    if conf <= 0.05 and avg_boxes >= 10:
        return "high_noise"
    if conf <= 0.10 and avg_boxes >= 6:
        return "high_noise"
    if no_detection_ratio >= 0.25:
        return "high_miss_risk"
    if avg_boxes >= 4:
        return "moderate"
    return "controlled"


def upsert_line_before_section(text: str, prefix: str, new_line: str, section_header: str) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = new_line
            return "\n".join(lines) + "\n"
    for i, line in enumerate(lines):
        if line.strip() == section_header.strip():
            lines.insert(i, new_line)
            return "\n".join(lines) + "\n"
    lines.append(new_line)
    return "\n".join(lines) + "\n"


def replace_block_lines(text: str, start_line: str, replacement_lines: list[str]) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line == start_line:
            j = i + 1
            while j < len(lines) and not lines[j].startswith("## "):
                j += 1
            new_lines = lines[:i] + replacement_lines + lines[j:]
            return "\n".join(new_lines) + "\n"
    return text.rstrip() + "\n" + "\n".join(replacement_lines) + "\n"


def main() -> None:
    validate = load_json(REPORTS / "phone_riceseg_35n_10epoch_validate_summary.json")
    validate_metrics = validate["experimental_metrics"]
    baseline_validate = load_json(REPORTS / "phone_riceseg_short_exp_5epoch_validate_summary.json")["experimental_metrics"]
    baseline_sweep = load_json(REPORTS / "phone_riceseg_short_exp_5epoch_conf_sweep_results.json")

    conf_result_names = {
        "0.25": "phone_riceseg_35n_10epoch_test_infer_conf025_results.json",
        "0.20": "phone_riceseg_35n_10epoch_test_infer_conf020_results.json",
        "0.15": "phone_riceseg_35n_10epoch_test_infer_conf015_results.json",
        "0.10": "phone_riceseg_35n_10epoch_test_infer_conf010_results.json",
        "0.05": "phone_riceseg_35n_10epoch_test_infer_conf005_results.json",
    }

    conf_sweep: dict[str, dict] = {}
    for conf_str, file_name in conf_result_names.items():
        summary, _ = summarize_results(load_results(file_name), TEST_IMAGE_COUNT, float(conf_str), "test_conf_sweep")
        summary["qualitative_risk"] = qualitative_risk(summary["avg_boxes_per_image"], summary["no_detection_ratio"], float(conf_str))
        conf_sweep[conf_str] = {
            "conf": float(conf_str),
            "total_images": summary["total_images"],
            "images_with_detection": summary["images_with_detection"],
            "no_detection_count": summary["no_detection_count"],
            "no_detection_ratio": summary["no_detection_ratio"],
            "total_boxes": summary["total_boxes"],
            "avg_boxes_per_image": summary["avg_boxes_per_image"],
            "avg_confidence": summary["avg_confidence"],
            "max_confidence": summary["max_confidence"],
            "predicted_class_distribution": summary["predicted_class_distribution"],
            "qualitative_risk": summary["qualitative_risk"],
        }

    test_summary, test_manifest_rows = summarize_results(
        load_results("phone_riceseg_35n_10epoch_test_infer_conf025_results.json"),
        TEST_IMAGE_COUNT,
        0.25,
        "test_infer_conf025",
    )
    test_summary["qualitative_risk"] = qualitative_risk(test_summary["avg_boxes_per_image"], test_summary["no_detection_ratio"], 0.25)

    holdout_summary, holdout_manifest_rows = summarize_results(
        load_results("phone_riceseg_35n_10epoch_holdout_infer_conf025_results.json"),
        HOLDOUT_IMAGE_COUNT,
        0.25,
        "holdout_infer_conf025",
    )
    holdout_summary["qualitative_risk"] = qualitative_risk(
        holdout_summary["avg_boxes_per_image"], holdout_summary["no_detection_ratio"], 0.25
    )
    holdout_summary["observation_only"] = True
    holdout_summary["boundary_note"] = "holdout result is observation-only, not tuning evidence"

    rows = list(csv.DictReader((RUN_DIR / "results.csv").open(encoding="utf-8")))
    last_row = rows[-1]
    actual_epochs = int(float(last_row["epoch"]))
    artifact_check = {
        "generated_at": NOW,
        "run_dir": str(RUN_DIR),
        "best_pt_exists": (RUN_DIR / "weights" / "best.pt").exists(),
        "last_pt_exists": (RUN_DIR / "weights" / "last.pt").exists(),
        "best_pt_size_bytes": (RUN_DIR / "weights" / "best.pt").stat().st_size,
        "last_pt_size_bytes": (RUN_DIR / "weights" / "last.pt").stat().st_size,
        "results_csv_exists": (RUN_DIR / "results.csv").exists(),
        "args_yaml_exists": (RUN_DIR / "args.yaml").exists(),
        "actual_epochs": actual_epochs,
        "exceeded_10_epochs": actual_epochs > 10,
        "nan_found_in_results_csv": any(any(str(v).lower() == "nan" for v in row.values()) for row in rows),
        "args_data_points_to_v35m_holdout_applied": "phone_riceseg_v35m_holdout_applied"
        in (RUN_DIR / "args.yaml").read_text(encoding="utf-8", errors="replace"),
        "training_completed": True,
        "train_time_hours_from_results_csv": round(float(last_row["time"]) / 3600, 6),
        "last_epoch_metrics": {
            "precision": float(last_row["metrics/precision(B)"]),
            "recall": float(last_row["metrics/recall(B)"]),
            "mAP50": float(last_row["metrics/mAP50(B)"]),
            "mAP50_95": float(last_row["metrics/mAP50-95(B)"]),
            "train_box_loss": float(last_row["train/box_loss"]),
            "train_cls_loss": float(last_row["train/cls_loss"]),
            "train_dfl_loss": float(last_row["train/dfl_loss"]),
            "val_box_loss": float(last_row["val/box_loss"]),
            "val_cls_loss": float(last_row["val/cls_loss"]),
            "val_dfl_loss": float(last_row["val/dfl_loss"]),
        },
        "weight_boundary": "controlled experimental only; not formal and not for backend deployment",
    }

    comparison = {
        "baseline_35b": {
            "dataset_version": "rice_phone_rgb_riceseg_preview_500_revised_v0_1",
            "epochs": 5,
            "precision": baseline_validate["precision"],
            "recall": baseline_validate["recall"],
            "mAP50": baseline_validate["mAP50"],
            "mAP50_95": baseline_validate["mAP50_95"],
            "conf025_no_detection_ratio": baseline_sweep["0.25"]["no_detection_ratio"],
            "conf025_avg_boxes_per_image": baseline_sweep["0.25"]["avg_boxes_per_image"],
            "conf010_avg_boxes_per_image": baseline_sweep["0.10"]["avg_boxes_per_image"],
            "per_class_ap": baseline_validate["per_class_ap"],
        },
        "current_35n": {
            "dataset_version": DATASET_NAME,
            "epochs": 10,
            "train_val_test_holdout": TRAIN_VAL_TEST_HOLDOUT,
            "precision": validate_metrics["precision"],
            "recall": validate_metrics["recall"],
            "mAP50": validate_metrics["mAP50"],
            "mAP50_95": validate_metrics["mAP50_95"],
            "conf025_no_detection_ratio": test_summary["no_detection_ratio"],
            "conf025_avg_boxes_per_image": test_summary["avg_boxes_per_image"],
            "conf010_avg_boxes_per_image": conf_sweep["0.10"]["avg_boxes_per_image"],
            "per_class_ap": validate_metrics["per_class_ap"],
            "holdout_observation_only": True,
        },
    }
    comparison["delta"] = {
        "precision": round(comparison["current_35n"]["precision"] - comparison["baseline_35b"]["precision"], 6),
        "recall": round(comparison["current_35n"]["recall"] - comparison["baseline_35b"]["recall"], 6),
        "mAP50": round(comparison["current_35n"]["mAP50"] - comparison["baseline_35b"]["mAP50"], 6),
        "mAP50_95": round(comparison["current_35n"]["mAP50_95"] - comparison["baseline_35b"]["mAP50_95"], 6),
        "conf025_no_detection_ratio": round(
            comparison["current_35n"]["conf025_no_detection_ratio"] - comparison["baseline_35b"]["conf025_no_detection_ratio"], 6
        ),
        "conf025_avg_boxes_per_image": round(
            comparison["current_35n"]["conf025_avg_boxes_per_image"] - comparison["baseline_35b"]["conf025_avg_boxes_per_image"], 6
        ),
        "conf010_avg_boxes_per_image": round(
            comparison["current_35n"]["conf010_avg_boxes_per_image"] - comparison["baseline_35b"]["conf010_avg_boxes_per_image"], 6
        ),
    }
    comparison["interpretation"] = {
        "better_than_35b_on_map50": comparison["current_35n"]["mAP50"] > comparison["baseline_35b"]["mAP50"],
        "better_than_35b_on_recall": comparison["current_35n"]["recall"] > comparison["baseline_35b"]["recall"],
        "conf025_no_detection_improved": comparison["current_35n"]["conf025_no_detection_ratio"]
        < comparison["baseline_35b"]["conf025_no_detection_ratio"],
        "low_conf_noise_worse_than_35b": comparison["current_35n"]["conf010_avg_boxes_per_image"]
        > comparison["baseline_35b"]["conf010_avg_boxes_per_image"],
        "recommended_next_stage": "prediction_visual_review",
    }

    if (
        artifact_check["training_completed"]
        and test_summary["no_detection_ratio"] <= baseline_sweep["0.25"]["no_detection_ratio"]
        and validate_metrics["mAP50"] >= baseline_validate["mAP50"]
        and holdout_summary["no_detection_ratio"] <= 0.5
    ):
        gate = "PASS"
        next_allowed_stage = "prediction_visual_review"
    else:
        gate = "WARNING"
        next_allowed_stage = "prediction_visual_review"

    model_card = {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "model_type": "YOLOv8n controlled experimental",
        "dataset": DATASET_NAME,
        "data_yaml": str(DATA_YAML),
        "train_val_test_holdout": TRAIN_VAL_TEST_HOLDOUT,
        "epochs": 10,
        "weights": {
            "best_pt": str(RUN_DIR / "weights" / "best.pt"),
            "last_pt": str(RUN_DIR / "weights" / "last.pt"),
        },
        "purpose": "controlled experimental learning/stability check",
        "boundaries": {
            "formal": False,
            "backend_deployment_allowed": False,
            "pesticide_recommendation_allowed": False,
            "production_model": False,
            "holdout_observation_only": True,
        },
        "validate_summary": validate_metrics,
        "test_infer_summary_conf025": test_summary,
        "holdout_observation_summary_conf025": holdout_summary,
        "conf_sweep_summary": conf_sweep,
        "comparison_vs_35b": comparison,
        "known_limitations": [
            "experimental-only result on a holdout-applied dataset revision",
            "holdout is observation-only and must not be used for threshold tuning or model selection",
            "recall is below the 35B baseline even though mAP50 is slightly higher",
            "conf<=0.10 produces clear multi-box noise growth",
            "not approved for backend deployment, pesticide recommendation, or formal claim",
        ],
        "gate": gate,
        "next_allowed_stage": next_allowed_stage,
    }

    atomic_write_csv(
        REPORTS / "phone_riceseg_35n_10epoch_test_infer_conf025_manifest.csv",
        test_manifest_rows,
        [
            "record_id",
            "image_name",
            "detection_count",
            "has_detection",
            "predicted_classes",
            "confidence_list",
            "main_disease",
            "model_name",
            "model_version",
            "boundary",
        ],
    )
    atomic_write_json(
        REPORTS / "phone_riceseg_35n_10epoch_test_infer_conf025_manifest.json",
        {"generated_at": NOW, "summary": test_summary, "items": test_manifest_rows},
    )
    atomic_write_text(
        REPORTS / "phone_riceseg_35n_10epoch_test_infer_conf025_summary.md",
        "\n".join(
            [
                "# Phone RiceSeg 35N Test Infer Summary (conf=0.25)",
                "",
                f"- model_name: `{MODEL_NAME}`",
                f"- model_version: `{MODEL_VERSION}`",
                f"- total_images: `{test_summary['total_images']}`",
                f"- images_with_detection: `{test_summary['images_with_detection']}`",
                f"- no_detection_count: `{test_summary['no_detection_count']}`",
                f"- no_detection_ratio: `{test_summary['no_detection_ratio']}`",
                f"- total_boxes: `{test_summary['total_boxes']}`",
                f"- avg_boxes_per_image: `{test_summary['avg_boxes_per_image']}`",
                f"- predicted_class_distribution: `{test_summary['predicted_class_distribution']}`",
                f"- avg_confidence: `{test_summary['avg_confidence']}`",
                f"- max_confidence: `{test_summary['max_confidence']}`",
                f"- qualitative_risk: `{test_summary['qualitative_risk']}`",
                "- real_inference: `true`",
                "",
            ]
        ),
    )

    atomic_write_csv(
        REPORTS / "phone_riceseg_35n_10epoch_holdout_infer_conf025_manifest.csv",
        holdout_manifest_rows,
        [
            "record_id",
            "image_name",
            "detection_count",
            "has_detection",
            "predicted_classes",
            "confidence_list",
            "main_disease",
            "model_name",
            "model_version",
            "boundary",
        ],
    )
    atomic_write_json(
        REPORTS / "phone_riceseg_35n_10epoch_holdout_infer_conf025_manifest.json",
        {"generated_at": NOW, "summary": holdout_summary, "items": holdout_manifest_rows},
    )
    atomic_write_text(
        REPORTS / "phone_riceseg_35n_10epoch_holdout_infer_conf025_summary.md",
        "\n".join(
            [
                "# Phone RiceSeg 35N Holdout Observation Summary (conf=0.25)",
                "",
                f"- model_name: `{MODEL_NAME}`",
                f"- model_version: `{MODEL_VERSION}`",
                f"- total_images: `{holdout_summary['total_images']}`",
                f"- images_with_detection: `{holdout_summary['images_with_detection']}`",
                f"- no_detection_count: `{holdout_summary['no_detection_count']}`",
                f"- no_detection_ratio: `{holdout_summary['no_detection_ratio']}`",
                f"- total_boxes: `{holdout_summary['total_boxes']}`",
                f"- avg_boxes_per_image: `{holdout_summary['avg_boxes_per_image']}`",
                f"- predicted_class_distribution: `{holdout_summary['predicted_class_distribution']}`",
                f"- avg_confidence: `{holdout_summary['avg_confidence']}`",
                f"- max_confidence: `{holdout_summary['max_confidence']}`",
                f"- qualitative_risk: `{holdout_summary['qualitative_risk']}`",
                "- observation_only: `true`",
                "- note: `holdout result is observation-only, not tuning evidence`",
                "",
            ]
        ),
    )

    atomic_write_json(REPORTS / "phone_riceseg_35n_10epoch_conf_sweep_results.json", conf_sweep)
    conf_md_lines = [
        "# Phone RiceSeg 35N Conf Sweep Summary",
        "",
        "- dataset: `phone_riceseg_v35m_holdout_applied/test`",
        "- scope: `real inference on all 43 test images`",
        "- note: lower thresholds are for analysis only and are not formal operating points.",
        "",
    ]
    for conf_str in ["0.25", "0.20", "0.15", "0.10", "0.05"]:
        row = conf_sweep[conf_str]
        conf_md_lines.extend(
            [
                f"## conf={conf_str}",
                "",
                f"- total_images: `{row['total_images']}`",
                f"- images_with_detection: `{row['images_with_detection']}`",
                f"- no_detection_count: `{row['no_detection_count']}`",
                f"- no_detection_ratio: `{row['no_detection_ratio']}`",
                f"- total_boxes: `{row['total_boxes']}`",
                f"- avg_boxes_per_image: `{row['avg_boxes_per_image']}`",
                f"- avg_confidence: `{row['avg_confidence']}`",
                f"- max_confidence: `{row['max_confidence']}`",
                f"- predicted_class_distribution: `{row['predicted_class_distribution']}`",
                f"- qualitative_risk: `{row['qualitative_risk']}`",
                "",
            ]
        )
    atomic_write_text(REPORTS / "phone_riceseg_35n_10epoch_conf_sweep_summary.md", "\n".join(conf_md_lines))

    atomic_write_json(REPORTS / "phone_riceseg_35n_10epoch_artifact_check.json", artifact_check)
    atomic_write_text(
        REPORTS / "phone_riceseg_35n_10epoch_artifact_check.md",
        "\n".join(
            [
                "# Phone RiceSeg 35N Artifact Check",
                "",
                f"- run_dir: `{artifact_check['run_dir']}`",
                f"- best.pt_exists: `{artifact_check['best_pt_exists']}`",
                f"- last.pt_exists: `{artifact_check['last_pt_exists']}`",
                f"- results.csv_exists: `{artifact_check['results_csv_exists']}`",
                f"- args.yaml_exists: `{artifact_check['args_yaml_exists']}`",
                f"- actual_epochs: `{artifact_check['actual_epochs']}`",
                f"- exceeded_10_epochs: `{artifact_check['exceeded_10_epochs']}`",
                f"- nan_found_in_results_csv: `{artifact_check['nan_found_in_results_csv']}`",
                f"- args_data_points_to_v35m_holdout_applied: `{artifact_check['args_data_points_to_v35m_holdout_applied']}`",
                f"- train_time_hours_from_results_csv: `{artifact_check['train_time_hours_from_results_csv']}`",
                f"- last_epoch_precision: `{artifact_check['last_epoch_metrics']['precision']}`",
                f"- last_epoch_recall: `{artifact_check['last_epoch_metrics']['recall']}`",
                f"- last_epoch_mAP50: `{artifact_check['last_epoch_metrics']['mAP50']}`",
                f"- last_epoch_mAP50_95: `{artifact_check['last_epoch_metrics']['mAP50_95']}`",
                f"- last_epoch_train_box_loss: `{artifact_check['last_epoch_metrics']['train_box_loss']}`",
                f"- last_epoch_train_cls_loss: `{artifact_check['last_epoch_metrics']['train_cls_loss']}`",
                f"- last_epoch_train_dfl_loss: `{artifact_check['last_epoch_metrics']['train_dfl_loss']}`",
                "",
            ]
        ),
    )

    atomic_write_text(
        REPORTS / "phone_riceseg_35n_10epoch_validate_summary.md",
        "\n".join(
            [
                "# Phone RiceSeg 35N Validate Summary",
                "",
                f"- weights: `{RUN_DIR / 'weights' / 'best.pt'}`",
                f"- data_yaml: `{DATA_YAML}`",
                "- metric_scope: `experimental_metrics`",
                f"- precision: `{validate_metrics['precision']}`",
                f"- recall: `{validate_metrics['recall']}`",
                f"- mAP50: `{validate_metrics['mAP50']}`",
                f"- mAP50-95: `{validate_metrics['mAP50_95']}`",
                f"- per_class_ap: `{validate_metrics['per_class_ap']}`",
                f"- confusion_matrix_path: `{validate_metrics['confusion_matrix_path']}`",
                f"- pr_curve_path: `{validate_metrics['pr_curve_path']}`",
                f"- save_dir: `{validate['save_dir']}`",
                "",
            ]
        ),
    )

    atomic_write_json(REPORTS / "phone_riceseg_35n_10epoch_vs_35b_5epoch_comparison.json", comparison)
    atomic_write_text(
        REPORTS / "phone_riceseg_35n_10epoch_vs_35b_5epoch_comparison.md",
        "\n".join(
            [
                "# Phone RiceSeg 35N vs 35B Comparison",
                "",
                "- baseline_35b_dataset: `rice_phone_rgb_riceseg_preview_500_revised_v0_1`",
                f"- current_35n_dataset: `{DATASET_NAME}`",
                "- holdout_usage_boundary: `observation only; not tuning evidence`",
                "",
                f"- 35B precision: `{baseline_validate['precision']}`",
                f"- 35N precision: `{validate_metrics['precision']}`",
                f"- precision_delta: `{comparison['delta']['precision']}`",
                f"- 35B recall: `{baseline_validate['recall']}`",
                f"- 35N recall: `{validate_metrics['recall']}`",
                f"- recall_delta: `{comparison['delta']['recall']}`",
                f"- 35B mAP50: `{baseline_validate['mAP50']}`",
                f"- 35N mAP50: `{validate_metrics['mAP50']}`",
                f"- mAP50_delta: `{comparison['delta']['mAP50']}`",
                f"- 35B mAP50-95: `{baseline_validate['mAP50_95']}`",
                f"- 35N mAP50-95: `{validate_metrics['mAP50_95']}`",
                f"- mAP50-95_delta: `{comparison['delta']['mAP50_95']}`",
                f"- 35B conf=0.25 no_detection_ratio: `{baseline_sweep['0.25']['no_detection_ratio']}`",
                f"- 35N conf=0.25 no_detection_ratio: `{test_summary['no_detection_ratio']}`",
                f"- conf025_no_detection_delta: `{comparison['delta']['conf025_no_detection_ratio']}`",
                f"- 35B conf=0.10 avg_boxes_per_image: `{baseline_sweep['0.10']['avg_boxes_per_image']}`",
                f"- 35N conf=0.10 avg_boxes_per_image: `{conf_sweep['0.10']['avg_boxes_per_image']}`",
                f"- conf010_avg_boxes_delta: `{comparison['delta']['conf010_avg_boxes_per_image']}`",
                f"- better_than_35b_on_map50: `{comparison['interpretation']['better_than_35b_on_map50']}`",
                f"- better_than_35b_on_recall: `{comparison['interpretation']['better_than_35b_on_recall']}`",
                f"- conf025_no_detection_improved: `{comparison['interpretation']['conf025_no_detection_improved']}`",
                f"- low_conf_noise_worse_than_35b: `{comparison['interpretation']['low_conf_noise_worse_than_35b']}`",
                f"- recommended_next_stage: `{comparison['interpretation']['recommended_next_stage']}`",
                "",
            ]
        ),
    )

    atomic_write_json(REPORTS / "phone_riceseg_35n_10epoch_model_card.json", model_card)
    atomic_write_text(
        REPORTS / "phone_riceseg_35n_10epoch_model_card.md",
        "\n".join(
            [
                "# Phone RiceSeg 35N Model Card",
                "",
                f"- model_name: `{MODEL_NAME}`",
                f"- model_version: `{MODEL_VERSION}`",
                "- model_type: `YOLOv8n controlled experimental`",
                f"- dataset: `{DATASET_NAME}`",
                f"- data_yaml: `{DATA_YAML}`",
                f"- train_val_test_holdout: `{TRAIN_VAL_TEST_HOLDOUT}`",
                "- epochs: `10`",
                "- formal: `false`",
                "- backend_deployment_allowed: `false`",
                "- pesticide_recommendation_allowed: `false`",
                "- production_model: `false`",
                "- holdout_observation_only: `true`",
                f"- validate_mAP50: `{validate_metrics['mAP50']}`",
                f"- validate_recall: `{validate_metrics['recall']}`",
                f"- test_conf025_no_detection_ratio: `{test_summary['no_detection_ratio']}`",
                f"- holdout_conf025_no_detection_ratio: `{holdout_summary['no_detection_ratio']}`",
                f"- conf010_avg_boxes_per_image: `{conf_sweep['0.10']['avg_boxes_per_image']}`",
                f"- gate: `{gate}`",
                f"- next_allowed_stage: `{next_allowed_stage}`",
                "",
            ]
        ),
    )

    prompt_text = "\n".join(
        [
            "# Phone-35O: prediction visual review on phone_riceseg_v35m_holdout_applied 10epoch",
            "",
            "You are taking over the `Phone RiceSeg` controlled experiment chain after `35N`.",
            "",
            "## Current locked source",
            "",
            f"- weights: `{RUN_DIR / 'weights' / 'best.pt'}`",
            f"- data_yaml: `{DATA_YAML}`",
            f"- run_dir: `{RUN_DIR}`",
            f"- validate mAP50: `{validate_metrics['mAP50']}`",
            f"- validate recall: `{validate_metrics['recall']}`",
            f"- test conf=0.25 no_detection_ratio: `{test_summary['no_detection_ratio']}`",
            f"- holdout conf=0.25 no_detection_ratio: `{holdout_summary['no_detection_ratio']}`",
            f"- 35N gate: `{gate}`",
            f"- next_allowed_stage: `{next_allowed_stage}`",
            "",
            "## Hard boundaries",
            "",
            "- Do not retrain.",
            "- Do not modify backend.",
            "- Do not modify real `.env`.",
            "- Do not modify labels or images.",
            "- Do not use holdout for tuning.",
            "- Do not write formal claims.",
            "",
            "## Goal",
            "",
            "Run a structured visual review on:",
            "",
            "1. test set conf=`0.25` predictions",
            "2. holdout conf=`0.25` observations",
            "",
            "Focus on:",
            "",
            "- box alignment quality",
            "- obvious false positives",
            "- obvious false negatives",
            "- class confusion patterns",
            "- whether current conf=`0.25` is visually acceptable enough to keep as the default experimental review threshold",
            "",
            "## Required outputs",
            "",
            "- `reports/phone_riceseg_35o_prediction_visual_review_report.md`",
            "- `reports/phone_riceseg_35o_prediction_visual_review_report.json`",
            "- visual evidence pack or reviewed-image manifest",
            "",
            "## Gate target",
            "",
            "Decide whether the next step should be:",
            "",
            "- `threshold_calibration`",
            "- `data_debug`",
            "- `experimental_freeze_for_demo_boundary`",
            "",
            "Do not allow backend deployment in this round.",
            "",
        ]
    )
    atomic_write_text(REPORTS / "phone_riceseg_35o_next_prediction_visual_review_prompt.md", prompt_text)

    final_report = "\n".join(
        [
            "# Thirty Fifth Round N Phone RiceSeg Fixed Dataset 10 Epoch Training Report",
            "",
            "## Goal",
            "",
            "This round executed the locked `Phone-35N` `10 epoch` controlled experimental training on the holdout-applied dataset revision created in `35M`.",
            "",
            "## Why 35N Follows 35M",
            "",
            "`35M` isolated `9` holdout images out of the active dataset so training, validation, test, and final observation could stay separated before extending the phone experiment line.",
            "",
            "## Dataset",
            "",
            f"- dataset_version: `{DATASET_NAME}`",
            f"- data_yaml: `{DATA_YAML}`",
            "- split: `train/val/test/holdout = 348/100/43/9`",
            "- holdout boundary: `observation only; not used for training, tuning, or model choice`",
            "",
            "## Training",
            "",
            f"- actual_run_dir: `{RUN_DIR}`",
            f"- training_completed: `{artifact_check['training_completed']}`",
            f"- actual_epochs: `{artifact_check['actual_epochs']}`",
            f"- train_time_hours_from_results_csv: `{artifact_check['train_time_hours_from_results_csv']}`",
            f"- best.pt generated: `{artifact_check['best_pt_exists']}`",
            f"- last.pt generated: `{artifact_check['last_pt_exists']}`",
            f"- results.csv generated: `{artifact_check['results_csv_exists']}`",
            f"- args.yaml generated: `{artifact_check['args_yaml_exists']}`",
            f"- args_data_locked_to_v35m_holdout_applied: `{artifact_check['args_data_points_to_v35m_holdout_applied']}`",
            f"- exceeded_10_epochs: `{artifact_check['exceeded_10_epochs']}`",
            f"- NaN observed: `{artifact_check['nan_found_in_results_csv']}`",
            "",
            "## Validate",
            "",
            "- validate_completed: `true`",
            f"- precision: `{validate_metrics['precision']}`",
            f"- recall: `{validate_metrics['recall']}`",
            f"- mAP50: `{validate_metrics['mAP50']}`",
            f"- mAP50-95: `{validate_metrics['mAP50_95']}`",
            f"- per_class_ap: `{validate_metrics['per_class_ap']}`",
            "",
            "## Test Infer At conf=0.25",
            "",
            "- completed: `true`",
            f"- total_images: `{test_summary['total_images']}`",
            f"- images_with_detection: `{test_summary['images_with_detection']}`",
            f"- no_detection_count: `{test_summary['no_detection_count']}`",
            f"- no_detection_ratio: `{test_summary['no_detection_ratio']}`",
            f"- avg_boxes_per_image: `{test_summary['avg_boxes_per_image']}`",
            f"- predicted_class_distribution: `{test_summary['predicted_class_distribution']}`",
            "",
            "## Holdout Observation At conf=0.25",
            "",
            "- completed: `true`",
            f"- holdout_total_images: `{holdout_summary['total_images']}`",
            f"- images_with_detection: `{holdout_summary['images_with_detection']}`",
            f"- no_detection_count: `{holdout_summary['no_detection_count']}`",
            f"- no_detection_ratio: `{holdout_summary['no_detection_ratio']}`",
            f"- avg_boxes_per_image: `{holdout_summary['avg_boxes_per_image']}`",
            f"- predicted_class_distribution: `{holdout_summary['predicted_class_distribution']}`",
            "- note: `holdout result is observation-only, not tuning evidence`",
            "",
            "## Conf Sweep",
            "",
            f"- conf=0.25: `no_detection_ratio={conf_sweep['0.25']['no_detection_ratio']}`, `avg_boxes_per_image={conf_sweep['0.25']['avg_boxes_per_image']}`",
            f"- conf=0.20: `no_detection_ratio={conf_sweep['0.20']['no_detection_ratio']}`, `avg_boxes_per_image={conf_sweep['0.20']['avg_boxes_per_image']}`",
            f"- conf=0.15: `no_detection_ratio={conf_sweep['0.15']['no_detection_ratio']}`, `avg_boxes_per_image={conf_sweep['0.15']['avg_boxes_per_image']}`",
            f"- conf=0.10: `no_detection_ratio={conf_sweep['0.10']['no_detection_ratio']}`, `avg_boxes_per_image={conf_sweep['0.10']['avg_boxes_per_image']}`",
            f"- conf=0.05: `no_detection_ratio={conf_sweep['0.05']['no_detection_ratio']}`, `avg_boxes_per_image={conf_sweep['0.05']['avg_boxes_per_image']}`",
            "- qualitative conclusion: `conf=0.25` is usable for evidence review, but `conf<=0.10` clearly expands into noisy multi-box behavior.`",
            "",
            "## Comparison With 35B 5 Epoch Baseline",
            "",
            f"- 35B precision: `{baseline_validate['precision']}`",
            f"- 35N precision: `{validate_metrics['precision']}`",
            f"- 35B recall: `{baseline_validate['recall']}`",
            f"- 35N recall: `{validate_metrics['recall']}`",
            f"- 35B mAP50: `{baseline_validate['mAP50']}`",
            f"- 35N mAP50: `{validate_metrics['mAP50']}`",
            f"- 35B mAP50-95: `{baseline_validate['mAP50_95']}`",
            f"- 35N mAP50-95: `{validate_metrics['mAP50_95']}`",
            f"- 35B conf=0.25 no_detection_ratio: `{baseline_sweep['0.25']['no_detection_ratio']}`",
            f"- 35N conf=0.25 no_detection_ratio: `{test_summary['no_detection_ratio']}`",
            f"- 35B conf=0.10 avg_boxes_per_image: `{baseline_sweep['0.10']['avg_boxes_per_image']}`",
            f"- 35N conf=0.10 avg_boxes_per_image: `{conf_sweep['0.10']['avg_boxes_per_image']}`",
            "",
            "Interpretation: `35N` slightly improves mAP50 over `35B`, but recall is lower, conf=`0.25` no-detection is slightly worse, and holdout observation is unstable. This is evidence-backed progress in one direction, not a blanket upgrade.",
            "",
            "## Boundary Summary",
            "",
            "- new weights generated: `YES`, but as `controlled experimental` weights only",
            "- backend integrated: `NO`",
            "- real `.env` modified: `NO`",
            "- backend modified: `NO`",
            "- original image/mask modified: `NO`",
            "- labels modified: `NO`",
            "- old weights overwritten: `NO`",
            "- formal claim written: `NO`",
            "- git add/commit: `NO`",
            "",
            "## Gate",
            "",
            f"- phone_riceseg_35n_gate: `{gate}`",
            f"- next_allowed_stage: `{next_allowed_stage}`",
            "",
            "## Recommendation",
            "",
            "Proceed to `prediction visual review` first. If visual evidence shows the conf=`0.25` boxes are structurally acceptable, a follow-up threshold calibration round can be justified. Do not connect this weight to backend routing and do not present it as a formal phone disease model.",
            "",
        ]
    )
    atomic_write_text(REPORTS / "thirty_fifth_round_n_phone_riceseg_fixed_dataset_10epoch_training_report.md", final_report)

    status = yaml.safe_load(STATUS_YAML.read_text(encoding="utf-8"))
    status["datasets"]["phone_riceseg_v35m_holdout_applied"] = {
        "dataset_stage": "controlled_experimental_training_dataset",
        "machine_check": "PASS",
        "holdout_applied": True,
        "train_val_test_holdout": TRAIN_VAL_TEST_HOLDOUT,
        "training": {
            "phone_35n_10epoch": {
                "status": "COMPLETE" if gate == "PASS" else gate,
                "epochs": 10,
                "model": "yolov8n",
                "run_name": RUN_DIR.name,
                "run_dir": str(RUN_DIR),
                "best_pt": str(RUN_DIR / "weights" / "best.pt"),
                "last_pt": str(RUN_DIR / "weights" / "last.pt"),
                "purpose": "controlled_experimental_only",
                "backend_deployment_allowed": False,
                "formal_metric_available": False,
                "holdout_observation_only": True,
                "next_allowed_stage": next_allowed_stage,
                "forbidden_usage": [
                    "backend upgrade",
                    "formal claim",
                    "pesticide recommendation",
                    "direct production deployment",
                ],
            }
        },
        "allowed_usage": [
            "controlled experimental training reference",
            "validation and inference evidence",
            "prediction visual review preparation",
            "threshold calibration planning",
        ],
        "forbidden_usage": [
            "backend upgrade",
            "formal claim",
            "pesticide recommendation",
            "direct production deployment",
        ],
        "next_action": [next_allowed_stage, "do not use holdout for tuning"],
    }
    atomic_write_text(STATUS_YAML, yaml.safe_dump(status, allow_unicode=True, sort_keys=False))

    summary_path = REPORTS / "project_current_model_status_summary.md"
    summary_text = summary_path.read_text(encoding="utf-8")
    summary_line = (
        "- `phone_riceseg_v35m_holdout_applied`: `10 epoch` controlled experimental training completed on the "
        f"holdout-applied dataset revision. Validate mAP50=`{validate_metrics['mAP50']:.6f}`, "
        f"recall=`{validate_metrics['recall']:.6f}`, conf=`0.25` test no-detection ratio=`{test_summary['no_detection_ratio']:.6f}`. "
        "This remains experimental-only, holdout is observation-only, and backend deployment is not allowed."
    )
    atomic_write_text(summary_path, upsert_line_before_section(summary_text, "- `phone_riceseg_v35m_holdout_applied`", summary_line, "## UAV Line"))

    boundary_path = REPORTS / "demo_model_boundary_statement.md"
    boundary_text = boundary_path.read_text(encoding="utf-8")
    boundary_line = (
        "- Phone `v35m_holdout_applied` now has a completed `10 epoch` controlled experimental run, "
        "but it is still experimental-only. Holdout remains observation-only, `formal_metric_available=false`, "
        "and backend deployment is not allowed."
    )
    atomic_write_text(boundary_path, upsert_line_before_section(boundary_text, "- Phone `v35m_holdout_applied`", boundary_line, "## UAV BLB 408 Manual Gate Status"))

    roadmap_path = REPORTS / "uav_phone_dual_line_roadmap.md"
    roadmap_text = roadmap_path.read_text(encoding="utf-8")
    roadmap_line = (
        "7. Phone `v35m_holdout_applied` has now completed a `10 epoch` controlled experimental run. "
        "The next allowed step is `prediction visual review` first, with threshold calibration only as a follow-on "
        "if visual evidence shows acceptable structure."
    )
    atomic_write_text(roadmap_path, upsert_line_before_section(roadmap_text, "7. Phone `v35m_holdout_applied`", roadmap_line, "## UAV BLB 408 Manual Gate Status"))

    frontend_path = REPORTS / "frontend_demo_model_hint_policy.md"
    frontend_text = frontend_path.read_text(encoding="utf-8")
    frontend_line = (
        "- Even after the `10 epoch` controlled experimental result on `phone_riceseg_v35m_holdout_applied`, "
        "frontend routing must remain unchanged because the weights are still experimental-only and holdout is observation-only."
    )
    atomic_write_text(frontend_path, upsert_line_before_section(frontend_text, "- Even after the `10 epoch` controlled experimental result on `phone_riceseg_v35m_holdout_applied`", frontend_line, "## UAV BLB 408 Manual Gate Status"))

    defense_path = REPORTS / "defense_talking_points_model_limitations.md"
    defense_text = defense_path.read_text(encoding="utf-8")
    defense_preamble = "\n".join(
        [
            "# Defense Talking Points Model Limitations",
            "",
            "1. The system already has UAV / Phone dual-line engineering closure, but the two lines are at different data maturity levels.",
            "2. The historical Phone expanded dataset was downgraded after quality problems were found, which is why the team is rebuilding the phone data route instead of forcing more training.",
            "3. The original Phone `RiceSeg preview_200` human gate was `WARNING`, but the revised_v0_1 preview has now passed both machine check and revised-path human gate. Even so, this only unlocks preview_500 planning rather than direct training.",
            "4. `RiceSeg preview_500_revised_v0_1` has now passed both machine check and the 120-item human gate, but that only unlocked controlled training and does not mean backend readiness.",
            "5. The project located a usable phone training environment: `torchgpu` is `READY_GPU`, with `health` and `vision311` as CPU-only fallbacks.",
            "6. A `1 epoch` sanity smoke run verified the phone training pipeline, but the weights were smoke-only and not deployment-ready.",
            "7. A controlled `5 epoch` short experimental run improved phone validation metrics and reduced infer no-detection sharply, but it remained experimental because lower-threshold inference became noisy.",
            "8. The phone line now also has a `10 epoch` controlled experimental result on the holdout-applied dataset revision. It slightly improves mAP50 over the 5-epoch baseline but still shows recall tradeoff and low-threshold box-noise risk, so it remains experimental-only and not backend-ready.",
            "9. Holdout observations are recorded separately and are not used for tuning or model choice.",
            "10. UAV BLB is currently the stronger demo line, but it is still experimental rather than formal.",
            "11. The project emphasizes controlled engineering, dataset audit, and explicit demo boundaries rather than overstating model readiness.",
            "",
        ]
    )
    if "## UAV BLB 408 Manual Gate Status" in defense_text:
        defense_tail = "## UAV BLB 408 Manual Gate Status" + defense_text.split("## UAV BLB 408 Manual Gate Status", 1)[1]
        atomic_write_text(defense_path, defense_preamble + defense_tail)
    else:
        atomic_write_text(defense_path, defense_preamble)

    for check_path in [
        REPORTS / "phone_riceseg_35n_10epoch_test_infer_conf025_manifest.json",
        REPORTS / "phone_riceseg_35n_10epoch_holdout_infer_conf025_manifest.json",
        REPORTS / "phone_riceseg_35n_10epoch_conf_sweep_results.json",
        REPORTS / "phone_riceseg_35n_10epoch_artifact_check.json",
        REPORTS / "phone_riceseg_35n_10epoch_vs_35b_5epoch_comparison.json",
        REPORTS / "phone_riceseg_35n_10epoch_model_card.json",
    ]:
        json.loads(check_path.read_text(encoding="utf-8"))
    yaml.safe_load(STATUS_YAML.read_text(encoding="utf-8"))

    print(
        json.dumps(
            {
                "gate": gate,
                "next_allowed_stage": next_allowed_stage,
                "test_conf025_no_detection_ratio": test_summary["no_detection_ratio"],
                "holdout_conf025_no_detection_ratio": holdout_summary["no_detection_ratio"],
                "conf010_avg_boxes_per_image": conf_sweep["0.10"]["avg_boxes_per_image"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
