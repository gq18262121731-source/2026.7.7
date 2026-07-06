"""YOLO training entry with inspectable parameter passthrough.

Default mode is dry-run. Real training only starts with --execute after
preflight checks pass. Dry-run can preview final Ultralytics kwargs and write
them to JSON so experiments can be audited before any GPU time is spent.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shlex
from pathlib import Path
from typing import Any, Callable

try:
    import yaml
except ImportError:  # pragma: no cover - dependency check reports this
    yaml = None


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
SAFE_MODEL_FIELDS = {"model"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview or execute an Ultralytics YOLO training call.")
    parser.add_argument("--config", required=True, help="Model config, e.g. configs/phone_yolo_train.yaml.")
    parser.add_argument("--common-config", default="configs/common_train.yaml")
    parser.add_argument("--execute", action="store_true", help="Start real training after preflight checks.")
    parser.add_argument("--epochs", type=int, help="Override epochs, e.g. 1 for smoke test.")
    parser.add_argument("--imgsz", type=int, help="Override image size, e.g. 320 or 640.")
    parser.add_argument("--batch", type=int, help="Override batch size, e.g. 2.")
    parser.add_argument("--device", help="Override device: cpu, cuda, 0, etc.")
    parser.add_argument("--project", help="Override output project directory, e.g. experiments/smoke.")
    parser.add_argument("--name", help="Override run name.")
    parser.add_argument("--smoke", action="store_true", help="Mark run as small-sample smoke test.")
    parser.add_argument(
        "--print-train-args",
        action="store_true",
        help="Print final train kwargs with source tracing. Dry-run still remains the default.",
    )
    parser.add_argument(
        "--output-args-json",
        help="Optional JSON report path for preview or execution metadata, e.g. reports/train_args_preview.json.",
    )
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required. Install with: pip install pyyaml")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def resolve_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    root = repo_root()
    if path.parts and path.parts[0] == "ai_model_training":
        return root.parent / path
    return root / path


def normalize_path_value(value: Any) -> str | None:
    if value is None or value == "":
        return None
    resolved = resolve_path(str(value))
    return str(resolved) if resolved is not None else None


def normalize_model_ref(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return "yolov8n.pt"
    path = Path(text)
    if path.is_absolute():
        return str(path)
    if path.parts and path.parts[0] == "ai_model_training":
        resolved = resolve_path(text)
        return str(resolved) if resolved is not None else text
    if any(sep in text for sep in ("/", "\\")):
        resolved = resolve_path(text)
        return str(resolved) if resolved is not None else text
    return text


def nested_get(mapping: dict[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def config_value(config: dict[str, Any], key: str, fallback_key: str | None = None) -> Any:
    if key in config:
        return config[key]
    training = config.get("training", {})
    if isinstance(training, dict):
        return training.get(fallback_key or key)
    return None


def list_images(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return [p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]


def count_labeled_objects(labels_root: Path) -> int:
    count = 0
    if not labels_root.exists():
        return 0
    for label_path in labels_root.rglob("*.txt"):
        for line in label_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                count += 1
    return count


def preflight(config: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    details: dict[str, Any] = {}
    data_yaml = resolve_path(str(config.get("data_yaml", "")))
    dataset_root = resolve_path(str(config.get("dataset_root", "")))
    if not data_yaml or not data_yaml.exists():
        errors.append(f"data_yaml_not_found:{data_yaml}")
    if not dataset_root or not dataset_root.exists():
        errors.append(f"dataset_root_not_found:{dataset_root}")
        return errors, details

    for split in ("train", "val"):
        image_dir = dataset_root / "images" / split
        label_dir = dataset_root / "labels" / split
        images = list_images(image_dir)
        labels = list(label_dir.rglob("*.txt")) if label_dir.exists() else []
        details[f"{split}_images"] = len(images)
        details[f"{split}_labels"] = len(labels)
        if not image_dir.exists():
            errors.append(f"missing_dir:{image_dir}")
        if not label_dir.exists():
            errors.append(f"missing_dir:{label_dir}")
        if len(images) == 0:
            errors.append(f"no_images:{image_dir}")
        if len(labels) == 0:
            errors.append(f"no_label_files:{label_dir}")

    labeled_objects = count_labeled_objects(dataset_root / "labels")
    details["labeled_objects"] = labeled_objects
    if labeled_objects == 0:
        errors.append("no_real_yolo_objects_found")
    if importlib.util.find_spec("ultralytics") is None:
        errors.append("ultralytics_not_installed")
    return errors, details


def load_supported_train_keys() -> set[str]:
    if importlib.util.find_spec("ultralytics") is None:
        return set()
    from ultralytics.cfg import DEFAULT_CFG_DICT

    return set(DEFAULT_CFG_DICT.keys())


def source_entry(value: Any, source: str, cli: bool = False) -> dict[str, Any]:
    return {"value": value, "source": source, "cli_override": cli}


def pick_value(
    *,
    config: dict[str, Any],
    cli_value: Any,
    cli_source: str | None,
    candidates: list[tuple[str, Callable[[dict[str, Any]], Any]]],
    default_value: Any = None,
    default_source: str | None = None,
    transform: Callable[[Any], Any] | None = None,
    required: bool = False,
) -> dict[str, Any]:
    if cli_source and cli_value is not None:
        value = transform(cli_value) if transform else cli_value
        return source_entry(value, cli_source, cli=True)
    for source, getter in candidates:
        raw = getter(config)
        if raw is None:
            continue
        value = transform(raw) if transform else raw
        if value is None and not required:
            continue
        return source_entry(value, source)
    if default_source is not None or required:
        value = transform(default_value) if transform else default_value
        return source_entry(value, default_source or "default")
    return source_entry(None, "omitted")


def render_value(value: Any) -> str:
    if isinstance(value, str):
        return shlex.quote(value)
    return repr(value)


def yolo_cli_candidates() -> list[Path]:
    import sys

    return [
        Path(sys.executable).with_name("yolo.exe"),
        Path(sys.executable).parent / "Scripts" / "yolo.exe",
        Path(sys.executable).parent / "bin" / "yolo",
    ]


def build_train_plan(config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    supported_keys = load_supported_train_keys()
    warnings: list[str] = []
    resolution: dict[str, dict[str, Any]] = {}

    def candidate(*path: str) -> tuple[str, Callable[[dict[str, Any]], Any]]:
        return ("config." + ".".join(path), lambda cfg: nested_get(cfg, *path))

    yolo_supported = supported_keys
    model_info = pick_value(
        config=config,
        cli_value=None,
        cli_source=None,
        candidates=[
            candidate("model"),
            candidate("pretrained_weight"),
            candidate("training", "model"),
            candidate("training", "pretrained_weight"),
        ],
        default_value="yolov8n.pt",
        default_source="default.model",
        transform=normalize_model_ref,
        required=True,
    )
    resolution["model"] = {
        **model_info,
        "status": "model_init_only",
        "supported_by_ultralytics": True,
    }

    specs: dict[str, dict[str, Any]] = {
        "data": {
            "cli_value": None,
            "cli_source": None,
            "candidates": [candidate("data_yaml"), candidate("data")],
            "default_value": None,
            "default_source": None,
            "transform": normalize_path_value,
            "required": True,
        },
        "imgsz": {
            "cli_value": args.imgsz,
            "cli_source": "cli.--imgsz",
            "candidates": [candidate("imgsz"), candidate("image_size"), candidate("training", "image_size")],
            "default_value": 640,
            "default_source": "default.imgsz",
            "transform": int,
        },
        "epochs": {
            "cli_value": args.epochs,
            "cli_source": "cli.--epochs",
            "candidates": [candidate("epochs"), candidate("training", "epochs")],
            "default_value": 100,
            "default_source": "default.epochs",
            "transform": int,
        },
        "batch": {
            "cli_value": args.batch,
            "cli_source": "cli.--batch",
            "candidates": [candidate("batch"), candidate("batch_size"), candidate("training", "batch_size")],
            "default_value": 8,
            "default_source": "default.batch",
            "transform": int,
        },
        "device": {
            "cli_value": args.device,
            "cli_source": "cli.--device",
            "candidates": [candidate("device"), candidate("training", "device")],
            "default_value": "auto",
            "default_source": "default.device",
            "transform": str,
        },
        "project": {
            "cli_value": args.project,
            "cli_source": "cli.--project",
            "candidates": [candidate("project"), candidate("output_dir"), candidate("output_root")],
            "default_value": "experiments/runs",
            "default_source": "default.project",
            "transform": normalize_path_value,
        },
        "name": {
            "cli_value": args.name,
            "cli_source": "cli.--name",
            "candidates": [candidate("experiment_name"), candidate("run_name"), candidate("name"), candidate("model_name")],
            "default_value": "yolo_train",
            "default_source": "default.name",
            "transform": str,
        },
        "seed": {
            "cli_value": None,
            "cli_source": None,
            "candidates": [candidate("seed"), candidate("training", "seed")],
            "default_value": 2026,
            "default_source": "default.seed",
            "transform": int,
        },
        "exist_ok": {
            "cli_value": None,
            "cli_source": None,
            "candidates": [candidate("exist_ok"), candidate("training", "exist_ok")],
            "default_value": False,
            "default_source": "default.exist_ok",
            "transform": bool,
        },
        "workers": {
            "cli_value": None,
            "cli_source": None,
            "candidates": [candidate("workers"), candidate("training", "workers")],
            "default_value": None,
            "default_source": None,
            "transform": int,
        },
        "cache": {
            "cli_value": None,
            "cli_source": None,
            "candidates": [candidate("cache"), candidate("training", "cache")],
            "default_value": None,
            "default_source": None,
        },
        "pretrained": {
            "cli_value": None,
            "cli_source": None,
            "candidates": [candidate("pretrained"), candidate("training", "pretrained")],
            "default_value": None,
            "default_source": None,
        },
        "resume": {
            "cli_value": None,
            "cli_source": None,
            "candidates": [candidate("resume"), candidate("training", "resume")],
            "default_value": None,
            "default_source": None,
        },
        "optimizer": {
            "cli_value": None,
            "cli_source": None,
            "candidates": [candidate("optimizer"), candidate("training", "optimizer")],
            "default_value": None,
            "default_source": None,
        },
        "lr0": {
            "cli_value": None,
            "cli_source": None,
            "candidates": [candidate("lr0"), candidate("learning_rate"), candidate("training", "learning_rate")],
            "default_value": None,
            "default_source": None,
            "transform": float,
        },
        "lrf": {
            "cli_value": None,
            "cli_source": None,
            "candidates": [candidate("lrf"), candidate("training", "lrf")],
            "default_value": None,
            "default_source": None,
            "transform": float,
        },
        "momentum": {
            "cli_value": None,
            "cli_source": None,
            "candidates": [candidate("momentum"), candidate("training", "momentum")],
            "default_value": None,
            "default_source": None,
            "transform": float,
        },
        "weight_decay": {
            "cli_value": None,
            "cli_source": None,
            "candidates": [candidate("weight_decay"), candidate("training", "weight_decay")],
            "default_value": None,
            "default_source": None,
            "transform": float,
        },
        "warmup_epochs": {
            "cli_value": None,
            "cli_source": None,
            "candidates": [candidate("warmup_epochs"), candidate("training", "warmup_epochs")],
            "default_value": None,
            "default_source": None,
            "transform": float,
        },
        "warmup_momentum": {
            "cli_value": None,
            "cli_source": None,
            "candidates": [candidate("warmup_momentum"), candidate("training", "warmup_momentum")],
            "default_value": None,
            "default_source": None,
            "transform": float,
        },
        "warmup_bias_lr": {
            "cli_value": None,
            "cli_source": None,
            "candidates": [candidate("warmup_bias_lr"), candidate("training", "warmup_bias_lr")],
            "default_value": None,
            "default_source": None,
            "transform": float,
        },
        "cos_lr": {
            "cli_value": None,
            "cli_source": None,
            "candidates": [candidate("cos_lr"), candidate("training", "cos_lr")],
            "default_value": None,
            "default_source": None,
        },
        "patience": {
            "cli_value": None,
            "cli_source": None,
            "candidates": [candidate("patience"), candidate("training", "patience"), candidate("early_stopping", "patience"), candidate("training", "early_stopping", "patience")],
            "default_value": None,
            "default_source": None,
            "transform": int,
        },
        "hsv_h": {"cli_value": None, "cli_source": None, "candidates": [candidate("hsv_h"), candidate("augmentation", "hsv_h")], "default_value": None, "default_source": None, "transform": float},
        "hsv_s": {"cli_value": None, "cli_source": None, "candidates": [candidate("hsv_s"), candidate("augmentation", "hsv_s")], "default_value": None, "default_source": None, "transform": float},
        "hsv_v": {"cli_value": None, "cli_source": None, "candidates": [candidate("hsv_v"), candidate("augmentation", "hsv_v")], "default_value": None, "default_source": None, "transform": float},
        "degrees": {"cli_value": None, "cli_source": None, "candidates": [candidate("degrees"), candidate("augmentation", "degrees")], "default_value": None, "default_source": None, "transform": float},
        "translate": {"cli_value": None, "cli_source": None, "candidates": [candidate("translate"), candidate("augmentation", "translate")], "default_value": None, "default_source": None, "transform": float},
        "scale": {"cli_value": None, "cli_source": None, "candidates": [candidate("scale"), candidate("augmentation", "scale")], "default_value": None, "default_source": None, "transform": float},
        "shear": {"cli_value": None, "cli_source": None, "candidates": [candidate("shear"), candidate("augmentation", "shear")], "default_value": None, "default_source": None, "transform": float},
        "perspective": {"cli_value": None, "cli_source": None, "candidates": [candidate("perspective"), candidate("augmentation", "perspective")], "default_value": None, "default_source": None, "transform": float},
        "flipud": {"cli_value": None, "cli_source": None, "candidates": [candidate("flipud"), candidate("augmentation", "flipud")], "default_value": None, "default_source": None, "transform": float},
        "fliplr": {"cli_value": None, "cli_source": None, "candidates": [candidate("fliplr"), candidate("augmentation", "fliplr")], "default_value": None, "default_source": None, "transform": float},
        "mosaic": {"cli_value": None, "cli_source": None, "candidates": [candidate("mosaic"), candidate("augmentation", "mosaic")], "default_value": None, "default_source": None, "transform": float},
        "mixup": {"cli_value": None, "cli_source": None, "candidates": [candidate("mixup"), candidate("augmentation", "mixup")], "default_value": None, "default_source": None, "transform": float},
        "copy_paste": {"cli_value": None, "cli_source": None, "candidates": [candidate("copy_paste"), candidate("augmentation", "copy_paste")], "default_value": None, "default_source": None, "transform": float},
        "close_mosaic": {"cli_value": None, "cli_source": None, "candidates": [candidate("close_mosaic"), candidate("augmentation", "close_mosaic")], "default_value": None, "default_source": None, "transform": int},
        "erasing": {"cli_value": None, "cli_source": None, "candidates": [candidate("erasing"), candidate("augmentation", "erasing")], "default_value": None, "default_source": None, "transform": float},
        "auto_augment": {"cli_value": None, "cli_source": None, "candidates": [candidate("auto_augment"), candidate("augmentation", "auto_augment")], "default_value": None, "default_source": None, "transform": str},
        "box": {"cli_value": None, "cli_source": None, "candidates": [candidate("box"), candidate("loss", "box")], "default_value": None, "default_source": None, "transform": float},
        "cls": {"cli_value": None, "cli_source": None, "candidates": [candidate("cls"), candidate("loss", "cls")], "default_value": None, "default_source": None, "transform": float},
        "dfl": {"cli_value": None, "cli_source": None, "candidates": [candidate("dfl"), candidate("loss", "dfl")], "default_value": None, "default_source": None, "transform": float},
        "save": {"cli_value": None, "cli_source": None, "candidates": [candidate("save"), candidate("training", "save")], "default_value": None, "default_source": None},
        "save_period": {"cli_value": None, "cli_source": None, "candidates": [candidate("save_period"), candidate("training", "save_period")], "default_value": None, "default_source": None, "transform": int},
        "plots": {"cli_value": None, "cli_source": None, "candidates": [candidate("plots"), candidate("training", "plots")], "default_value": None, "default_source": None},
        "val": {"cli_value": None, "cli_source": None, "candidates": [candidate("val"), candidate("training", "val")], "default_value": None, "default_source": None},
    }

    train_kwargs: dict[str, Any] = {}
    for key, spec in specs.items():
        entry = pick_value(
            config=config,
            cli_value=spec.get("cli_value"),
            cli_source=spec.get("cli_source"),
            candidates=spec.get("candidates", []),
            default_value=spec.get("default_value"),
            default_source=spec.get("default_source"),
            transform=spec.get("transform"),
            required=spec.get("required", False),
        )
        if key == "name" and args.smoke and entry["value"] is not None and "smoke" not in str(entry["value"]):
            entry["value"] = f"smoke_{entry['value']}"
            entry["source"] = f"{entry['source']}+smoke_suffix"
        supported = key in yolo_supported
        status = "omitted"
        if entry["value"] is not None:
            if supported:
                train_kwargs[key] = entry["value"]
                status = "forwarded"
            else:
                status = "unsupported"
                warnings.append(f"requested_but_unsupported:{key}:{entry['source']}")
        resolution[key] = {**entry, "status": status, "supported_by_ultralytics": supported}

    unsupported_requested = {
        key: info
        for key, info in resolution.items()
        if info["status"] == "unsupported"
    }
    omitted_params = {
        key: info["source"]
        for key, info in resolution.items()
        if info["status"] == "omitted"
    }

    cli_equivalent = []
    for candidate in yolo_cli_candidates():
        if candidate.exists():
            cli_equivalent.append(str(candidate))
            break
    if not cli_equivalent:
        cli_equivalent.append("yolo")
    cli_equivalent.extend(["detect", "train", f"model={model_info['value']}"])
    cli_equivalent.extend(f"{key}={render_value(value)}" for key, value in train_kwargs.items())

    return {
        "model_init": str(model_info["value"]),
        "train_kwargs": train_kwargs,
        "param_resolution": resolution,
        "unsupported_requested_params": unsupported_requested,
        "omitted_params": omitted_params,
        "warnings": warnings,
        "supported_train_keys": sorted(yolo_supported),
        "call_preview": f"YOLO({render_value(model_info['value'])}).train({', '.join(f'{key}={render_value(value)}' for key, value in train_kwargs.items())})",
        "command_preview": " ".join(shlex.quote(part) for part in cli_equivalent),
    }


def write_json_report(path_value: str | None, payload: dict[str, Any]) -> None:
    if not path_value:
        return
    path = resolve_path(path_value) or Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_training(model_ref: str, train_kwargs: dict[str, Any]) -> dict[str, Any]:
    from ultralytics import YOLO

    model = YOLO(model_ref)
    results = model.train(**train_kwargs)
    save_dir = getattr(results, "save_dir", None)
    return {
        "returncode": 0,
        "save_dir": str(save_dir) if save_dir is not None else None,
    }


def main() -> int:
    args = parse_args()
    common = load_yaml(resolve_path(args.common_config) or Path(args.common_config))
    specific = load_yaml(resolve_path(args.config) or Path(args.config))
    merged_config = deep_merge(common, specific)

    errors, details = preflight(merged_config)
    plan = build_train_plan(merged_config, args)
    payload = {
        "mode": "smoke_test" if args.smoke else merged_config.get("training_stage", "preview_only"),
        "boundary": "dry-run by default; --execute starts real training only after preflight checks",
        "warning": "Preview output only verifies config passthrough. It is not formal model performance.",
        "config": args.config,
        "common_config": args.common_config,
        "model_name": merged_config.get("model_name"),
        "print_train_args": args.print_train_args,
        "preflight": {"passed": not errors, "errors": errors, "details": details},
        **plan,
    }

    if not args.execute:
        write_json_report(args.output_args_json, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if errors:
        write_json_report(args.output_args_json, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    try:
        result = run_training(plan["model_init"], plan["train_kwargs"])
    except Exception as exc:  # noqa: BLE001 - propagate training failure in report without fabricating outputs
        payload["returncode"] = 2
        payload["execution_error"] = f"{exc.__class__.__name__}:{exc}"
        write_json_report(args.output_args_json, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    payload.update(result)
    write_json_report(args.output_args_json, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
