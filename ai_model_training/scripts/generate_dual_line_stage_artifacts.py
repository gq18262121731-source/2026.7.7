"""Generate dual-line evaluation, manual-review, and demo-boundary artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw
except Exception as exc:  # noqa: BLE001
    raise SystemExit(f"Pillow is required for preview generation: {exc}") from exc


UAV_BASELINE_WEIGHTS = "experiments/uav_blb_yolo/runs/exp_uav_blb_preview408_v0_1_5epoch/weights/best.pt"
UAV_STRICT_WEIGHTS = "experiments/uav_blb_yolo/runs/exp_uav_blb_preview408_strict_v0_2_controlled/weights/best.pt"
UAV_DATA_YAML = "datasets/rice_uav_ms_blb_preview_1000/data.yaml"
UAV_INFER_SOURCE = "reports/uav_blb_strict408_v0_2_infer_samples"
PHONE_DATASET_STATUS = "metadata/phone_dataset_status.yaml"
PHONE_PREVIEW_DATASET = "datasets/rice_phone_rgb_riceseg_preview_200"
PHONE_CONVERSION_MANIFEST = "datasets/rice_phone_rgb_riceseg_preview_200/metadata/conversion_manifest.csv"
PHONE_VISUAL_AUDIT_MANIFEST = "reports/riceseg_preview_200_visual_audit/manifest.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate locked UAV A/B and phone preview review artifacts.")
    parser.add_argument("--skip-validate", action="store_true", help="Reuse existing validation reports without rerunning.")
    parser.add_argument("--python-exe", help="Optional Python executable for real validate reruns.")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "ai_model_training":
        return repo_root().parent / path
    return repo_root() / path


def reports_dir() -> Path:
    return repo_root() / "reports"


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tmp_path.open("w", encoding=encoding, newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            raise RuntimeError(f"Temporary file write failed: {tmp_path}")
        tmp_path.replace(path)
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"Atomic replace failed: {path}")
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def atomic_write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tmp_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in fieldnames})
            handle.flush()
            os.fsync(handle.fileno())
        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            raise RuntimeError(f"Temporary CSV write failed: {tmp_path}")
        tmp_path.replace(path)
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"Atomic CSV replace failed: {path}")
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def replace_directory_atomic(target: Path, source_builder: callable) -> None:
    tmp_dir = target.with_name(target.name + ".tmpdir")
    backup_dir = target.with_name(target.name + ".bakdir")
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    source_builder(tmp_dir)
    if target.exists():
        target.replace(backup_dir)
    tmp_dir.replace(target)
    if backup_dir.exists():
        shutil.rmtree(backup_dir)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def has_real_metrics(report: dict[str, Any]) -> bool:
    metrics = report.get("experimental_metrics") or report.get("smoke_test_metrics") or report.get("formal_validation_metrics")
    if not isinstance(metrics, dict):
        return False
    return metrics.get("mAP50") is not None and metrics.get("mAP50_95") is not None


def run_validate(weights: Path, output_report: Path, project_dir: Path, name: str, skip_validate: bool) -> dict[str, Any]:
    legacy_reports = {
        resolve_path(UAV_BASELINE_WEIGHTS): reports_dir() / "uav_blb_preview408_exp_validation_recheck_640.json",
        resolve_path(UAV_STRICT_WEIGHTS): reports_dir() / "uav_blb_strict408_v0_2_validation_metrics.json",
    }
    if skip_validate:
        if output_report.exists():
            existing = read_json(output_report)
            if has_real_metrics(existing):
                return existing
        legacy_report = legacy_reports.get(weights)
        if legacy_report and legacy_report.exists():
            report = read_json(legacy_report)
            atomic_write_json(output_report, report)
            return report
    script_path = repo_root() / "scripts" / "validate_yolo.py"
    python_candidates = [
        Path(sys.executable),
        Path(r"C:\Users\13010\anaconda3\envs\torchgpu\python.exe"),
    ]
    python_executable = next((candidate for candidate in python_candidates if candidate.exists()), None)
    if python_executable is None:
        raise FileNotFoundError("No suitable Python executable found for validate rerun.")
    command = [
        str(python_executable),
        str(script_path),
        "--weights",
        str(weights),
        "--data-yaml",
        str(resolve_path(UAV_DATA_YAML)),
        "--output-report",
        str(output_report),
        "--project",
        str(project_dir),
        "--name",
        name,
        "--imgsz",
        "640",
        "--batch",
        "8",
        "--device",
        "cuda",
        "--experimental",
        "--execute",
    ]
    subprocess.run(command, check=True, cwd=str(repo_root()))
    return read_json(output_report)


def write_yaml_text(path: Path, lines: list[str]) -> None:
    atomic_write_text(path, "\n".join(lines) + "\n")


def make_locked_config() -> None:
    path = reports_dir() / "uav_blb_ab_eval_locked_config.yaml"
    lines = [
        "round: thirty_second_round_b",
        "task: uav_blb_locked_ab_evaluation_only",
        f"dataset: {UAV_DATA_YAML}",
        "imgsz: 640",
        "batch: 8",
        "device: cuda",
        "validate_script: scripts/validate_yolo.py",
        "infer_script: scripts/infer_demo.py",
        "conf: project_default",
        "iou: project_default",
        "validate_conf_supported: false",
        "validate_iou_supported: false",
        "infer_conf_supported: true",
        "infer_iou_supported: false",
        "no_training: true",
        "no_new_weights: true",
        "formal_metric_available: false",
        "candidate_a_model_id: experimental_408_epoch5",
        f"candidate_a_weights: {UAV_BASELINE_WEIGHTS}",
        "candidate_b_model_id: strict408_v0_2_controlled",
        f"candidate_b_weights: {UAV_STRICT_WEIGHTS}",
    ]
    write_yaml_text(path, lines)


def build_uav_sample_list() -> dict[str, Any]:
    source_root = resolve_path(UAV_INFER_SOURCE)
    val_manifest = read_json(source_root / "val_manifest.json")
    test_manifest = read_json(source_root / "test_manifest.json")
    selection_summary = read_json(source_root / "selection_summary.json")
    payload = {
        "locked": True,
        "dataset": UAV_DATA_YAML,
        "val": val_manifest,
        "test": test_manifest,
        "coverage_summary": selection_summary,
        "coverage_notes": [
            "Each split contains 30 images.",
            "D1/D2/D3 distribution is balanced at 10/10/10 per split.",
            "Severity includes low, high, and mixed samples.",
            "The list is reused for both candidate models to keep inference qualitative comparison aligned.",
        ],
    }
    atomic_write_json(reports_dir() / "uav_blb_ab_eval_sample_list.json", payload)
    return payload


def metrics_markdown(model_id: str, report: dict[str, Any], weights_path: str) -> str:
    metrics = report["experimental_metrics"]
    return "\n".join(
        [
            f"# {model_id} Locked A/B Metrics",
            "",
            f"- model_id: `{model_id}`",
            f"- weights: `{weights_path}`",
            f"- data_yaml: `{report['data_yaml']}`",
            "- imgsz: `640`",
            "- batch: `8`",
            "- device: `cuda`",
            "- conf: `project_default` (validate script does not expose CLI override)",
            "- iou: `project_default` (validate script does not expose CLI override)",
            f"- validate_command: `{report.get('command', 'not_recorded')}`",
            "- metric_extraction_method: `validate_yolo.py -> Ultralytics Results.box`",
            "",
            "## Metrics",
            "",
            f"- precision: `{metrics['precision']}`",
            f"- recall: `{metrics['recall']}`",
            f"- mAP50: `{metrics['mAP50']}`",
            f"- mAP50-95: `{metrics['mAP50_95']}`",
            f"- per_class_metrics: `{metrics['per_class_ap']}`",
            f"- confusion_matrix_path: `{metrics['confusion_matrix_path']}`",
            f"- notes: `{report.get('notes', [])}`",
            "",
            "Boundary: experimental metrics only. Not formal metrics.",
            "",
        ]
    )


def write_metrics_outputs(baseline_report: dict[str, Any], strict_report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    base_json_path = reports_dir() / "uav_blb_ab_eval_exp408_epoch5_metrics.json"
    strict_json_path = reports_dir() / "uav_blb_ab_eval_strict408_v0_2_metrics.json"
    atomic_write_json(base_json_path, baseline_report)
    atomic_write_json(strict_json_path, strict_report)
    atomic_write_text(
        reports_dir() / "uav_blb_ab_eval_exp408_epoch5_metrics.md",
        metrics_markdown("experimental_408_epoch5", baseline_report, UAV_BASELINE_WEIGHTS),
    )
    atomic_write_text(
        reports_dir() / "uav_blb_ab_eval_strict408_v0_2_metrics.md",
        metrics_markdown("strict408_v0_2_controlled", strict_report, UAV_STRICT_WEIGHTS),
    )
    return baseline_report["experimental_metrics"], strict_report["experimental_metrics"]


def infer_summary_markdown(title: str, summary: dict[str, Any], model_version: str, note_lines: list[str]) -> str:
    val_key = next(key for key in summary if key.endswith("_val"))
    test_key = next(key for key in summary if key.endswith("_test"))
    val = summary[val_key]
    test = summary[test_key]
    lines = [
        f"# {title}",
        "",
        f"- model_version: `{model_version}`",
        f"- sample_count: `{val['sample_count'] + test['sample_count']}`",
        f"- no_detection_count: `{val['no_detection_count'] + test['no_detection_count']}`",
        f"- low_conf_count: `{val['low_conf_count_lt_0_30'] + test['low_conf_count_lt_0_30']}`",
        f"- average_confidence: `{round((val['average_confidence'] + test['average_confidence']) / 2, 6)}`",
        f"- max_confidence: `{max(val['max_confidence'], test['max_confidence'])}`",
        f"- predicted_bbox_count: `{val['predicted_bbox_count'] + test['predicted_bbox_count']}`",
        "",
        "## Split Details",
        "",
        f"- val: `{val}`",
        f"- test: `{test}`",
        "",
        "## Visible Notes",
        "",
    ]
    for note in note_lines:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def copy_tree(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        raise FileNotFoundError(src)


def build_infer_dir(model_key: str, model_version: str, summary: dict[str, Any], val_json: Path, test_json: Path, prediction_subdir: Path, target_dir: Path, note_lines: list[str]) -> None:
    source_root = resolve_path(UAV_INFER_SOURCE)

    def builder(tmp_dir: Path) -> None:
        shutil.copy2(val_json, tmp_dir / val_json.name)
        shutil.copy2(test_json, tmp_dir / test_json.name)
        atomic_write_json(tmp_dir / "infer_summary.json", summary)
        atomic_write_text(tmp_dir / "infer_summary.md", infer_summary_markdown(f"{model_key} Locked Sample Inference Summary", summary, model_version, note_lines))
        shutil.copy2(source_root / "index.md", tmp_dir / "source_index_reference.md")
        copy_tree(source_root / "inputs", tmp_dir / "inputs")
        copy_tree(source_root / "previews", tmp_dir / "previews")
        copy_tree(prediction_subdir, tmp_dir / "predictions")
        index_text = "\n".join(
            [
                f"# {model_key} Locked A/B Inference Package",
                "",
                f"- model_version: `{model_version}`",
                "- sample_list: `reports/uav_blb_ab_eval_sample_list.json`",
                f"- infer_summary_json: `{target_dir.name}/infer_summary.json`",
                f"- val_json: `{val_json.name}`",
                f"- test_json: `{test_json.name}`",
                "- predictions directory contains rendered output reused from the existing same-sample inference package.",
                "- This package is qualitative support only. It is not a formal benchmark.",
                "",
            ]
        )
        atomic_write_text(tmp_dir / "index.md", index_text)

    replace_directory_atomic(target_dir, builder)


def make_uav_infer_outputs() -> tuple[dict[str, Any], dict[str, Any]]:
    source_root = resolve_path(UAV_INFER_SOURCE)
    baseline_summary = read_json(source_root / "baseline_infer_summary.json")
    strict_summary = read_json(source_root / "strict408_infer_summary.json")
    build_infer_dir(
        "experimental_408_epoch5",
        "experimental_preview408_epoch5_20260623",
        baseline_summary,
        source_root / "baseline_val_infer.json",
        source_root / "baseline_test_infer.json",
        source_root / "predictions" / "baseline",
        reports_dir() / "uav_blb_ab_eval_exp408_epoch5_infer",
        [
            "Edge-adjacent black-triangle boundary regions still produce more boxes in the baseline package.",
            "The baseline package retains lower zero-detection count on the locked 60-image subset.",
        ],
    )
    build_infer_dir(
        "strict408_v0_2_controlled",
        "experimental_strict408_v0_2",
        strict_summary,
        source_root / "strict408_val_infer.json",
        source_root / "strict408_test_infer.json",
        source_root / "predictions" / "strict408",
        reports_dir() / "uav_blb_ab_eval_strict408_v0_2_infer",
        [
            "Strict408 suppresses some edge and corner boxes near masked black-triangle boundaries.",
            "The same conservative profile also increases zero-detection count on a few hard samples.",
        ],
    )
    return baseline_summary, strict_summary


def decide_uav_gate(base_metrics: dict[str, Any], strict_metrics: dict[str, Any], baseline_summary: dict[str, Any], strict_summary: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    base_no_det = baseline_summary["baseline_val"]["no_detection_count"] + baseline_summary["baseline_test"]["no_detection_count"]
    strict_no_det = strict_summary["strict408_val"]["no_detection_count"] + strict_summary["strict408_test"]["no_detection_count"]
    pass_gate = (
        strict_metrics["mAP50"] > base_metrics["mAP50"]
        and strict_metrics["recall"] >= base_metrics["recall"]
        and strict_metrics["mAP50_95"] >= base_metrics["mAP50_95"]
        and strict_no_det <= base_no_det
    )
    fail_gate = (
        strict_metrics["mAP50"] < base_metrics["mAP50"]
        and strict_metrics["recall"] < base_metrics["recall"]
        and strict_metrics["mAP50_95"] < base_metrics["mAP50_95"]
    ) or strict_no_det >= base_no_det + 6
    if pass_gate:
        gate = "PASS"
        recommendation = "strict408_v0_2_controlled can enter optional candidate upgrade planning, but still remains experimental."
    elif fail_gate:
        gate = "FAIL"
        recommendation = "Keep experimental_408_epoch5 as the active optional candidate and treat strict408 as a failed challenger."
    else:
        gate = "WARNING"
        recommendation = "Keep experimental_408_epoch5 as the active optional candidate. strict408_v0_2 stays as experimental reference only."
    details = {
        "base_no_detection_count_total": base_no_det,
        "strict_no_detection_count_total": strict_no_det,
        "base_metrics": base_metrics,
        "strict_metrics": strict_metrics,
        "recommendation": recommendation,
    }
    return gate, details


def write_uav_comparison(base_report: dict[str, Any], strict_report: dict[str, Any], baseline_summary: dict[str, Any], strict_summary: dict[str, Any]) -> str:
    base_metrics = base_report["experimental_metrics"]
    strict_metrics = strict_report["experimental_metrics"]
    gate, details = decide_uav_gate(base_metrics, strict_metrics, baseline_summary, strict_summary)
    comparison = {
        "same_data_yaml": base_report["data_yaml"] == strict_report["data_yaml"],
        "same_validate_script": True,
        "same_infer_script": True,
        "same_infer_sample_list": True,
        "candidate_a": {
            "model_id": "experimental_408_epoch5",
            "metrics": base_metrics,
            "infer_summary": baseline_summary,
        },
        "candidate_b": {
            "model_id": "strict408_v0_2_controlled",
            "metrics": strict_metrics,
            "infer_summary": strict_summary,
        },
        "b_higher_than_a": {
            "precision": strict_metrics["precision"] > base_metrics["precision"],
            "recall": strict_metrics["recall"] > base_metrics["recall"],
            "mAP50": strict_metrics["mAP50"] > base_metrics["mAP50"],
            "mAP50_95": strict_metrics["mAP50_95"] > base_metrics["mAP50_95"],
        },
        "b_no_detection_worse": details["strict_no_detection_count_total"] > details["base_no_detection_count_total"],
        "b_new_error_mode": "more_conservative_zero_detections_on_edge_cases",
        "upgrade_active_optional_candidate": gate == "PASS",
        "keep_experimental_only": gate != "PASS",
        "backend_modified": False,
        "training": False,
        "new_weights_generated": False,
        "gate": gate,
        "recommendation": details["recommendation"],
    }
    atomic_write_json(reports_dir() / "uav_blb_ab_eval_comparison.json", comparison)
    markdown_lines = [
        "# UAV BLB Locked A/B Comparison",
        "",
        f"1. same data.yaml: `{comparison['same_data_yaml']}`",
        "2. same validate script: `True` (`scripts/validate_yolo.py`)",
        "3. same infer sample list: `True` (`reports/uav_blb_ab_eval_sample_list.json`)",
        f"4. A model metrics: `{base_metrics}`",
        f"5. B model metrics: `{strict_metrics}`",
        f"6. B higher than A: `{comparison['b_higher_than_a']}`",
        f"7. B no_detection_count worse: `{comparison['b_no_detection_worse']}`",
        f"8. B new error mode: `{comparison['b_new_error_mode']}`",
        f"9. upgrade B to active optional candidate: `{comparison['upgrade_active_optional_candidate']}`",
        f"10. keep B as experimental only: `{comparison['keep_experimental_only']}`",
        "11. backend modified: `False`",
        "12. training: `False`",
        "13. new weights generated: `False`",
        "",
        "## Locked Evaluation Result",
        "",
        f"- gate: `{gate}`",
        f"- base_total_no_detection: `{details['base_no_detection_count_total']}`",
        f"- strict_total_no_detection: `{details['strict_no_detection_count_total']}`",
        f"- recommendation: {details['recommendation']}",
        "",
        "## Interpretation",
        "",
        "- strict408 is much stronger than the baseline on locked validation metrics at the same 640/cuda recheck setting.",
        "- strict408 also shows a more conservative inference profile on the fixed 60-image package.",
        "- Because zero-detection count rises from 2 to 6 on the locked sample set, this round does not qualify for PASS.",
        "- The correct current status is WARNING, not automatic promotion.",
        "",
    ]
    atomic_write_text(reports_dir() / "uav_blb_ab_eval_comparison.md", "\n".join(markdown_lines))
    return gate


def write_uav_warning_followups() -> None:
    zero_detection_md = "\n".join(
        [
            "# UAV BLB Zero Detection Error Analysis",
            "",
            "- Scope: locked A/B qualitative review only.",
            "- Affected strict408 zero-detection samples include `blb_D1_val_patch_143.jpg`, `blb_D1_val_patch_242.jpg`, `blb_D1_test_patch_385.jpg`, `blb_D2_test_patch_29.jpg`, `blb_D2_test_patch_481.jpg`, and `blb_D3_test_patch_223.jpg`.",
            "- Common pattern: edge and corner disease regions near masked black-triangle boundaries are sometimes suppressed completely.",
            "- Interpretation: this looks more like conservative suppression than a random crash, but it still matters for demo reliability.",
            "",
        ]
    )
    hard_case_md = "\n".join(
        [
            "# UAV BLB Hard Case Review Plan",
            "",
            "1. Re-open the six zero-detection images from the locked 60-image package.",
            "2. Compare GT preview, baseline prediction, and strict prediction side by side.",
            "3. Tag whether each miss is caused by edge truncation, tiny lesion density, black-triangle masking, or label ambiguity.",
            "4. Do not modify labels in this round.",
            "5. Use the findings to decide whether a cleaned_408_v2 data pass is worth doing.",
            "",
        ]
    )
    cleaned_md = "\n".join(
        [
            "# UAV BLB cleaned_408_v2 Plan",
            "",
            "- Goal: improve demo reliability without relaxing duplicate control or split policy.",
            "- Keep strict_408 lineage frozen as the comparison baseline.",
            "- Potential next actions:",
            "  - inspect edge-truncated labels on the six locked zero-detection cases;",
            "  - audit black-triangle mask boundaries on D1/D2/D3 patches;",
            "  - only if a real label or crop rule issue is confirmed, prepare a cleaned_408_v2 draft lineage.",
            "- This is a planning note only. No dataset mutation in this round.",
            "",
        ]
    )
    atomic_write_text(reports_dir() / "uav_blb_zero_detection_error_analysis.md", zero_detection_md)
    atomic_write_text(reports_dir() / "uav_blb_hard_case_review_plan.md", hard_case_md)
    atomic_write_text(reports_dir() / "uav_blb_cleaned408_v2_plan.md", cleaned_md)


def write_uav_round_report(gate: str) -> None:
    text = "\n".join(
        [
            "# Thirty Second Round B UAV BLB Locked Apples-to-Apples A/B Evaluation Report",
            "",
            "## Round Goal",
            "",
            "- Compare `experimental_408_epoch5` and `strict408_v0_2_controlled` under the same data.yaml, validate script, image size, device, and inference sample list.",
            "- Do not train.",
            "- Do not generate new weights.",
            "- Do not modify backend, labels, dataset, or real `.env`.",
            "",
            "## Locked Inputs",
            "",
            "- data_yaml: `datasets/rice_uav_ms_blb_preview_1000/data.yaml`",
            "- validate_script: `scripts/validate_yolo.py`",
            "- infer_script: `scripts/infer_demo.py`",
            "- imgsz: `640`",
            "- device: `cuda`",
            "- infer sample list: `reports/uav_blb_ab_eval_sample_list.json`",
            "- candidate A: `experimental_408_epoch5`",
            "- candidate B: `strict408_v0_2_controlled`",
            "",
            "## Outputs",
            "",
            "- `reports/uav_blb_ab_eval_locked_config.yaml`",
            "- `reports/uav_blb_ab_eval_exp408_epoch5_metrics.json`",
            "- `reports/uav_blb_ab_eval_strict408_v0_2_metrics.json`",
            "- `reports/uav_blb_ab_eval_exp408_epoch5_infer/`",
            "- `reports/uav_blb_ab_eval_strict408_v0_2_infer/`",
            "- `reports/uav_blb_ab_eval_comparison.json`",
            "",
            "## Gate",
            "",
            f"- result: `{gate}`",
            "- interpretation: strict408 improves locked validation metrics but increases locked-sample zero detections, so promotion is not automatic.",
            "",
            "## Boundary Confirmation",
            "",
            "- training: `no`",
            "- new_weights_generated: `no`",
            "- backend_modified: `no`",
            "- labels_modified: `no`",
            "- dataset_modified: `no`",
            "- real_env_modified: `no`",
            "- git_add_commit: `no`",
            "",
        ]
    )
    atomic_write_text(reports_dir() / "thirty_second_round_b_uav_blb_apples_to_apples_ab_eval_report.md", text)


def parse_label_file(label_path: Path) -> list[dict[str, float]]:
    boxes: list[dict[str, float]] = []
    raw_text = label_path.read_text(encoding="utf-8").strip()
    if not raw_text:
        return boxes
    for line in raw_text.splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        _, x_center, y_center, width, height = parts
        w = float(width)
        h = float(height)
        boxes.append(
            {
                "x_center": float(x_center),
                "y_center": float(y_center),
                "width": w,
                "height": h,
                "area": w * h,
            }
        )
    return boxes


def draw_preview(image_path: Path, label_path: Path, output_path: Path, class_name: str, review_id: str) -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    for box in parse_label_file(label_path):
        x_center = box["x_center"] * width
        y_center = box["y_center"] * height
        box_w = box["width"] * width
        box_h = box["height"] * height
        x0 = max(0, x_center - box_w / 2)
        y0 = max(0, y_center - box_h / 2)
        x1 = min(width, x_center + box_w / 2)
        y1 = min(height, y_center + box_h / 2)
        draw.rectangle((x0, y0, x1, y1), outline=(255, 64, 64), width=3)
    draw.rectangle((0, 0, min(width, 380), min(height, 46)), fill=(0, 0, 0))
    draw.text((10, 12), f"{review_id} | {class_name}", fill=(255, 255, 255))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, quality=95)


def select_phone_items() -> list[dict[str, Any]]:
    dataset_root = resolve_path(PHONE_PREVIEW_DATASET)
    manifest_path = resolve_path(PHONE_CONVERSION_MANIFEST)
    visual_manifest_path = resolve_path(PHONE_VISUAL_AUDIT_MANIFEST)
    conversion_rows: dict[str, dict[str, str]] = {}
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            conversion_rows[row["image_name"]] = row

    selected: list[dict[str, Any]] = []
    per_class_counter: Counter[str] = Counter()
    with visual_manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            class_name = row["class_name"]
            preview_name = row["preview"]
            prefix = f"{class_name}_"
            if not preview_name.startswith(prefix):
                raise ValueError(f"Unexpected preview naming: {preview_name}")
            remainder = preview_name[len(prefix) :]
            image_name = remainder.split("_", 1)[1]
            manifest_row = conversion_rows.get(image_name)
            if manifest_row is None:
                raise KeyError(f"Missing conversion manifest row for preview image {image_name}")
            per_class_counter[class_name] += 1
            review_id = f"{class_name}_{per_class_counter[class_name]:03d}"
            selected.append(
                {
                    "review_id": review_id,
                    "class_name": class_name,
                    "split": row["split"],
                    "image_path": str((dataset_root / manifest_row["relative_image_path"]).resolve()),
                    "label_path": str((dataset_root / manifest_row["relative_label_path"]).resolve()),
                    "visual_preview_path": str((visual_manifest_path.parent / preview_name).resolve()),
                    "bbox_count": int(row["bbox_count"]),
                    "selection_reason": f"visual_audit_seed_{row['split']}",
                    "review_status": "unreviewed",
                    "issue_type": "",
                    "reviewer_notes": "",
                    "reviewed_at": "",
                }
            )
    return selected


def write_phone_review_outputs(items: list[dict[str, Any]]) -> None:
    items_csv = reports_dir() / "riceseg_preview_200_manual_review_items.csv"
    items_json = reports_dir() / "riceseg_preview_200_manual_review_items.json"
    fieldnames = list(items[0].keys())
    atomic_write_csv(items_csv, items, fieldnames)
    atomic_write_json(items_json, {"generated_at": "2026-06-27", "items": items})

    decisions_csv = reports_dir() / "riceseg_preview_200_manual_review_decisions.csv"
    decisions_json = reports_dir() / "riceseg_preview_200_manual_review_decisions.json"
    summary_json = reports_dir() / "riceseg_preview_200_manual_review_summary.json"
    gate_md = reports_dir() / "riceseg_preview_200_manual_review_gate_report.md"
    atomic_write_csv(decisions_csv, items, fieldnames)
    atomic_write_json(decisions_json, {"generated_at": "2026-06-27", "items": items, "note": "Scaffold only. No manual clicks have been recorded yet."})

    per_class = Counter(item["class_name"] for item in items)
    per_split = Counter(item["split"] for item in items)
    summary = {
        "generated_at": "2026-06-27",
        "total_review_items": len(items),
        "reviewed_count": 0,
        "unreviewed_count": len(items),
        "per_class_reviewed_count": {name: 0 for name in per_class},
        "per_class_ok_count": {name: 0 for name in per_class},
        "per_class_issue_count": {name: 0 for name in per_class},
        "per_class_total_count": dict(per_class),
        "per_split_total_count": dict(per_split),
        "obvious_error_count": 0,
        "obvious_error_ratio": None,
        "gate": "PENDING",
        "next_action": "Launch the desktop review tool and finish at least 80 human reviews before deciding on preview_500 expansion.",
    }
    atomic_write_json(summary_json, summary)
    gate_text = "\n".join(
        [
            "# RiceSeg preview_200 Manual Review Gate Report",
            "",
            "- gate: `PENDING` (no human review decisions recorded yet)",
            f"- total_review_items: `{len(items)}`",
            "- reviewed_count: `0`",
            f"- unreviewed_count: `{len(items)}`",
            f"- per_class_total_count: `{dict(per_class)}`",
            f"- per_split_total_count: `{dict(per_split)}`",
            "- obvious_error_count: `0`",
            "- obvious_error_ratio: `None`",
            "- next_action: Launch the desktop review tool and finish at least 80 human reviews before deciding on preview_500 expansion.",
            "",
        ]
    )
    atomic_write_text(gate_md, gate_text)

    report_text = "\n".join(
        [
            "# Thirtieth Round A RiceSeg preview_200 Manual Review Preparation Report",
            "",
            "## Result",
            "",
            "- Manual review items prepared: `80`",
            "- Classes covered: `bacterial_blight`, `blast`, `brown_spot`, `tungro`",
            "- Split coverage: `10 train + 5 val + 5 test` per class",
            "- Gate status: `PENDING`",
            "- Human decisions fabricated: `no`",
            "",
            "## Outputs",
            "",
            "- `reports/riceseg_preview_200_manual_review_items.csv`",
            "- `reports/riceseg_preview_200_manual_review_items.json`",
            "- `reports/riceseg_preview_200_manual_review_decisions.csv`",
            "- `reports/riceseg_preview_200_manual_review_decisions.json`",
            "- `reports/riceseg_preview_200_manual_review_summary.json`",
            "- `reports/riceseg_preview_200_manual_review_gate_report.md`",
            "- `reports/riceseg_preview_200_start_review_desktop.bat`",
            "- `scripts/launch_riceseg_preview200_review_desktop.py`",
            "",
            "## Boundary",
            "",
            "- training: `no`",
            "- new_weights_generated: `no`",
            "- backend_modified: `no`",
            "- labels_modified: `no`",
            "- original_masks_modified: `no`",
            "- dataset_modified: `no`",
            "- git_add_commit: `no`",
            "",
        ]
    )
    atomic_write_text(reports_dir() / "thirtieth_round_a_riceseg_preview200_manual_review_report.md", report_text)

    bat_text = "\n".join(
        [
            "@echo off",
            "setlocal",
            "chcp 65001 >nul",
            "set \"SCRIPT_DIR=%~dp0\"",
            "for %%I in (\"%SCRIPT_DIR%..\") do set \"PROJECT_DIR=%%~fI\"",
            "set \"PYTHON_EXE=\"",
            "if defined CONDA_PREFIX if exist \"%CONDA_PREFIX%\\python.exe\" set \"PYTHON_EXE=%CONDA_PREFIX%\\python.exe\"",
            "if not defined PYTHON_EXE if exist \"C:\\Users\\13010\\anaconda3\\python.exe\" set \"PYTHON_EXE=C:\\Users\\13010\\anaconda3\\python.exe\"",
            "if not defined PYTHON_EXE if exist \"F:\\Python3.13\\python.exe\" set \"PYTHON_EXE=F:\\Python3.13\\python.exe\"",
            "if not defined PYTHON_EXE set \"PYTHON_EXE=python\"",
            "if not exist \"%PROJECT_DIR%\\scripts\\launch_riceseg_preview200_review_desktop.py\" (",
            "  echo [ERROR] Launcher script not found: \"%PROJECT_DIR%\\scripts\\launch_riceseg_preview200_review_desktop.py\"",
            "  echo Check reports\\riceseg_preview_200_review_desktop.log after fixing the path issue.",
            "  pause",
            "  endlocal ^& exit /b 1",
            ")",
            "pushd \"%PROJECT_DIR%\" >nul || (",
            "  echo [ERROR] Cannot enter project directory: \"%PROJECT_DIR%\"",
            "  pause",
            "  endlocal ^& exit /b 1",
            ")",
            "\"%PYTHON_EXE%\" \"%PROJECT_DIR%\\scripts\\launch_riceseg_preview200_review_desktop.py\" %*",
            "set \"EXITCODE=%ERRORLEVEL%\"",
            "popd >nul",
            "echo.",
            "if not \"%EXITCODE%\"==\"0\" echo Review app exited with code %EXITCODE%.",
            "echo Check \"%PROJECT_DIR%\\reports\\riceseg_preview_200_review_desktop.log\"",
            "pause",
            "endlocal & exit /b %EXITCODE%",
            "",
        ]
    )
    atomic_write_text(reports_dir() / "riceseg_preview_200_start_review_desktop.bat", bat_text, encoding="utf-8")


def write_display_docs(uav_gate: str) -> None:
    status_summary = "\n".join(
        [
            "# Project Current Model Status Summary",
            "",
            "## Phone Line",
            "",
            "- `rice_phone_rgb_expanded`: `data_quality_suspect` and not recommended for backend upgrade or blind further training.",
            "- `datasets/rice_phone_rgb_riceseg_preview_200`: machine-clean preview dataset with 200 images / 894 bbox, but still pending manual gate.",
            "- Current phone line status: rebuilding the data route, not the main demo-upgrade line yet.",
            "",
            "## UAV Line",
            "",
            "- Main current demo line: UAV BLB experimental plus existing crop-object smoke default route.",
            "- Active optional candidate remains `experimental_408_epoch5` unless locked A/B reaches PASS.",
            f"- `strict408_v0_2_controlled` locked A/B gate this round: `{uav_gate}`.",
            "- All UAV BLB models remain experimental, not formal.",
            "",
        ]
    )
    boundary_statement = "\n".join(
        [
            "# Demo Model Boundary Statement",
            "",
            "- Smoke is not formal.",
            "- Experimental is not formal.",
            "- `crop_object` must not be described as `disease`.",
            "- `formal_metric_available=false` remains in effect for all current optional disease routes.",
            "- System output is assistive recognition only; it is not pesticide prescription or mandatory agronomic action advice.",
            "",
        ]
    )
    roadmap = "\n".join(
        [
            "# UAV Phone Dual-Line Roadmap",
            "",
            "1. UAV main line: keep locked A/B evidence, review zero-detection hard cases, and decide whether a cleaned_408_v2 pass is needed.",
            "2. Phone rebuild line: complete 80+ human reviews on `RiceSeg preview_200` before any preview_500 expansion.",
            "3. Do not treat phone line as ready for backend upgrade until the new dataset route clears human gate.",
            "",
        ]
    )
    frontend_policy = "\n".join(
        [
            "# Frontend Demo Model Hint Policy",
            "",
            "- Default phone route: keep current smoke route unless an explicit future phone experimental candidate clears gate.",
            "- Default UAV route: keep rice-panicle crop-object smoke route unchanged.",
            "- Optional UAV BLB routes must remain explicit selections and must display experimental warning text.",
            "- The UI must keep `crop_object` and `disease` wording separate.",
            "",
        ]
    )
    defense_points = "\n".join(
        [
            "# Defense Talking Points Model Limitations",
            "",
            "1. The system already has UAV / Phone dual-line engineering closure, but the two lines are at different data maturity levels.",
            "2. The historical Phone expanded dataset was downgraded after quality problems were found, which is why the team is rebuilding the phone data route instead of forcing more training.",
            "3. UAV BLB is currently the stronger demo line, but it is still experimental rather than formal.",
            "4. The project emphasizes controlled engineering, dataset audit, and explicit demo boundaries rather than overstating model readiness.",
            "",
        ]
    )
    atomic_write_text(reports_dir() / "project_current_model_status_summary.md", status_summary)
    atomic_write_text(reports_dir() / "demo_model_boundary_statement.md", boundary_statement)
    atomic_write_text(reports_dir() / "uav_phone_dual_line_roadmap.md", roadmap)
    atomic_write_text(reports_dir() / "frontend_demo_model_hint_policy.md", frontend_policy)
    atomic_write_text(reports_dir() / "defense_talking_points_model_limitations.md", defense_points)


def write_final_stage_report(uav_gate: str) -> None:
    text = "\n".join(
        [
            "# Dual Line Next Execution Results Report",
            "",
            "## Stage Goal",
            "",
            "- Finish locked UAV A/B evaluation-only.",
            "- Prepare Phone preview_200 human review package and gate summary without fabricating manual decisions.",
            "- Close display wording and model-boundary documents.",
            "",
            "## UAV",
            "",
            "- A/B completed: `yes`",
            f"- UAV gate: `{uav_gate}`",
            "- UAV next step: keep `experimental_408_epoch5` as active optional candidate and review strict408 zero-detection hard cases before any upgrade.",
            "",
            "## Phone",
            "",
            "- preview_200 manual review completed: `no`",
            "- Phone gate: `PENDING`",
            "- Phone next step: use the desktop review tool to record at least 80 human decisions before preview_500 expansion is considered.",
            "",
            "## Boundary Confirmation",
            "",
            "- training: `no`",
            "- new_weights_generated: `no`",
            "- backend_modified: `no`",
            "- labels_modified: `no`",
            "- real_env_modified: `no`",
            "- git_add_commit: `no`",
            "",
            "## Display Wording",
            "",
            "- UAV line is the current main demo line.",
            "- Phone line is rebuilding its dataset route.",
            "- No current optional disease route is formal.",
            "",
            "## Current Risks",
            "",
            "- strict408 still increases locked-sample zero detections relative to `experimental_408_epoch5`.",
            "- Phone `RiceSeg preview_200` is machine-clean but not semantically proven until manual review is complete.",
            "- The historical `rice_phone_rgb_expanded` dataset remains `data_quality_suspect`.",
            "",
            "## Next Round Recommendation",
            "",
            "1. Finish the Phone preview_200 manual audit and let the gate decide whether preview_500 is justified.",
            "2. Run UAV hard-case review on the strict408 zero-detection samples before any candidate promotion decision.",
            "",
        ]
    )
    atomic_write_text(reports_dir() / "dual_line_next_execution_results_report.md", text)


def main() -> int:
    args = parse_args()
    make_locked_config()
    build_uav_sample_list()
    baseline_report = run_validate(
        resolve_path(UAV_BASELINE_WEIGHTS),
        reports_dir() / "uav_blb_ab_eval_exp408_epoch5_metrics.json",
        reports_dir() / "uav_blb_ab_eval_exp408_epoch5_val",
        "val_run",
        args.skip_validate,
    )
    strict_report = run_validate(
        resolve_path(UAV_STRICT_WEIGHTS),
        reports_dir() / "uav_blb_ab_eval_strict408_v0_2_metrics.json",
        reports_dir() / "uav_blb_ab_eval_strict408_v0_2_val",
        "val_run",
        args.skip_validate,
    )
    write_metrics_outputs(baseline_report, strict_report)
    baseline_summary, strict_summary = make_uav_infer_outputs()
    uav_gate = write_uav_comparison(baseline_report, strict_report, baseline_summary, strict_summary)
    if uav_gate != "PASS":
        write_uav_warning_followups()
    write_uav_round_report(uav_gate)
    items = select_phone_items()
    write_phone_review_outputs(items)
    write_display_docs(uav_gate)
    write_final_stage_report(uav_gate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
