"""Validate a YOLO model or emit a metric template when weights are absent."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shlex
import sys
from pathlib import Path
from typing import Any


METRIC_FIELDS = [
    "precision",
    "recall",
    "mAP50",
    "mAP50_95",
    "f1_score",
    "per_class_ap",
    "confusion_matrix_path",
    "pr_curve_path",
    "inference_time_ms",
    "model_size_mb",
    "false_positive_cases",
    "false_negative_cases",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run YOLO validation or write a safe template.")
    parser.add_argument("--weights", required=True)
    parser.add_argument("--data-yaml", required=True)
    parser.add_argument("--output-report", default="reports/validation_report_template.json")
    parser.add_argument("--project", default="reports/yolo_val")
    parser.add_argument("--name", default="val_run")
    parser.add_argument("--imgsz", type=int)
    parser.add_argument("--batch", type=int)
    parser.add_argument("--device")
    parser.add_argument("--smoke", action="store_true", help="Mark metrics as smoke_test_metrics.")
    parser.add_argument("--experimental", action="store_true", help="Mark metrics as experimental_metrics.")
    parser.add_argument("--execute", action="store_true", help="Run YOLO val when weights exist.")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    root = repo_root()
    if path.parts and path.parts[0] == "ai_model_training":
        return root.parent / path
    return root / path


def build_command(args: argparse.Namespace) -> list[str]:
    yolo_candidates = [
        Path(sys.executable).with_name("yolo.exe"),
        Path(sys.executable).parent / "Scripts" / "yolo.exe",
        Path(sys.executable).parent / "bin" / "yolo",
    ]
    yolo_command = next((str(path) for path in yolo_candidates if path.exists()), "yolo")
    command = [
        yolo_command,
        "detect",
        "val",
        f"model={resolve_path(args.weights)}",
        f"data={resolve_path(args.data_yaml)}",
        f"project={resolve_path(args.project)}",
        f"name={args.name}",
    ]
    if args.imgsz:
        command.append(f"imgsz={args.imgsz}")
    if args.batch:
        command.append(f"batch={args.batch}")
    if args.device:
        command.append(f"device={args.device}")
    return command


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_real_metrics(metrics: Any, save_dir: Path) -> dict[str, Any]:
    box = getattr(metrics, "box", None)
    names = getattr(metrics, "names", None) or {}
    per_class_ap: dict[str, float | None] = {}
    maps = getattr(box, "maps", None) if box is not None else None
    if maps is not None:
        try:
            for class_id, value in enumerate(list(maps)):
                per_class_ap[str(names.get(class_id, class_id))] = as_float(value)
        except TypeError:
            per_class_ap = {}

    return {
        "precision": as_float(getattr(box, "mp", None) if box is not None else None),
        "recall": as_float(getattr(box, "mr", None) if box is not None else None),
        "mAP50": as_float(getattr(box, "map50", None) if box is not None else None),
        "mAP50_95": as_float(getattr(box, "map", None) if box is not None else None),
        "f1_score": None,
        "per_class_ap": per_class_ap or None,
        "confusion_matrix_path": str(save_dir / "confusion_matrix.png") if (save_dir / "confusion_matrix.png").exists() else None,
        "pr_curve_path": str(save_dir / "PR_curve.png") if (save_dir / "PR_curve.png").exists() else None,
        "inference_time_ms": None,
        "model_size_mb": None,
        "false_positive_cases": None,
        "false_negative_cases": None,
    }


def run_validation(args: argparse.Namespace) -> tuple[Any, Path]:
    from ultralytics import YOLO

    project = resolve_path(args.project)
    model = YOLO(str(resolve_path(args.weights)))
    kwargs: dict[str, Any] = {
        "data": str(resolve_path(args.data_yaml)),
        "project": str(project),
        "name": args.name,
        "plots": True,
        "verbose": True,
        "device": args.device or "cpu",
    }
    if args.imgsz:
        kwargs["imgsz"] = args.imgsz
    if args.batch:
        kwargs["batch"] = args.batch
    metrics = model.val(**kwargs)
    save_dir = Path(getattr(metrics, "save_dir", project / args.name))
    return metrics, save_dir


def main() -> int:
    args = parse_args()
    weights = resolve_path(args.weights)
    data_yaml = resolve_path(args.data_yaml)
    if args.smoke and args.experimental:
        print("--smoke and --experimental are mutually exclusive", file=sys.stderr)
        return 2
    if args.smoke:
        metric_key = "smoke_test_metrics"
    elif args.experimental:
        metric_key = "experimental_metrics"
    else:
        metric_key = "formal_validation_metrics"
    report: dict[str, Any] = {
        "boundary": "metrics are null unless produced by a real YOLO val run",
        "weights": str(weights),
        "data_yaml": str(data_yaml),
        "metric_scope": metric_key,
        metric_key: {field: None for field in METRIC_FIELDS},
        "notes": [],
    }

    if not weights.exists():
        report["notes"].append("weights_not_found; wrote template only")
        write_report(resolve_path(args.output_report), report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if not data_yaml.exists():
        report["notes"].append("data_yaml_not_found; validation not run")
        write_report(resolve_path(args.output_report), report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    if importlib.util.find_spec("ultralytics") is None:
        report["notes"].append("ultralytics_not_installed; validation not run")
        write_report(resolve_path(args.output_report), report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    command = build_command(args)
    report["command"] = " ".join(shlex.quote(part) for part in command)
    if not args.execute:
        report["notes"].append("dry_run; command preview only")
        write_report(resolve_path(args.output_report), report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    try:
        metrics, save_dir = run_validation(args)
    except Exception as exc:  # noqa: BLE001 - report validation failure without fabricating metrics
        report["returncode"] = 2
        report["notes"].append(f"real_yolo_val_run_failed:{exc.__class__.__name__}:{exc}")
        write_report(resolve_path(args.output_report), report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    report["returncode"] = 0
    report["save_dir"] = str(save_dir)
    report[metric_key] = extract_real_metrics(metrics, save_dir)
    report["notes"].append("real_yolo_val_run_completed; metrics extracted from Ultralytics Results object")
    write_report(resolve_path(args.output_report), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
