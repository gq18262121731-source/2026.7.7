"""YOLO inference demo aligned with backend detection_result fields."""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or preview YOLO inference JSON output.")
    parser.add_argument("--input", required=True, help="Image file or directory.")
    parser.add_argument("--source-type", default="unknown")
    parser.add_argument("--weights", help="Real weights path. Missing weights produce skeleton output.")
    parser.add_argument("--model-name", default="auto")
    parser.add_argument("--model-version", default="pending_real_training")
    parser.add_argument("--output-json", default="reports/inference_result_template.json")
    parser.add_argument("--conf", type=float, help="Optional YOLO confidence threshold for smoke schema checks.")
    parser.add_argument("--execute", action="store_true", help="Run real inference when weights exist.")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


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


def choose_model(source_type: str, requested: str) -> str:
    if requested != "auto":
        return requested
    if source_type in {"uav_rgb", "uav_multispectral", "uav_video_frame"}:
        return "uav_rice_disease_yolo"
    return "phone_rice_disease_yolo"


def target_type_for_source(source_type: str) -> str:
    if source_type in {"uav_multispectral", "uav_rgb", "uav_ms", "phone_rgb", "uav_video_frame"}:
        return "disease"
    return "unknown"


def postprocess_summary(detections: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "disease_count": len(detections),
        "main_disease": detections[0]["class_name"] if detections else None,
        "severity": "postprocess_pending",
        "risk_level": "postprocess_pending",
        "suggestion": "Postprocess placeholder only; no pesticide dosage or mandatory action advice.",
    }


def skeleton(args: argparse.Namespace, note: str) -> dict[str, Any]:
    input_path = resolve_path(args.input) or Path(args.input)
    detections: list[dict[str, Any]] = []
    return {
        "type": "detection_result",
        "record_id": "example_record_not_real",
        "image_id": input_path.stem,
        "image_name": input_path.name,
        "source_type": args.source_type,
        "category_type": target_type_for_source(args.source_type),
        "current_target_type": target_type_for_source(args.source_type),
        "model_name": choose_model(args.source_type, args.model_name),
        "model_version": args.model_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "is_mock": True,
        "detections": detections,
        "summary": postprocess_summary(detections),
        "boundary": note,
    }


def run_inference(args: argparse.Namespace) -> dict[str, Any]:
    from ultralytics import YOLO

    weights = resolve_path(args.weights)
    input_path = resolve_path(args.input)
    model = YOLO(str(weights))
    kwargs: dict[str, Any] = {"source": str(input_path), "save": False, "verbose": False}
    if args.conf is not None:
        kwargs["conf"] = args.conf
    results = model.predict(**kwargs)
    all_results = []
    for result in results:
        detections = []
        names = result.names or {}
        for box in result.boxes:
            class_id = int(box.cls[0].item())
            xyxy = [float(v) for v in box.xyxy[0].tolist()]
            detections.append(
                {
                    "class_id": class_id,
                    "class_name": str(names.get(class_id, class_id)),
                    "category_type": target_type_for_source(args.source_type),
                    "current_target_type": target_type_for_source(args.source_type),
                    "confidence": float(box.conf[0].item()),
                    "bbox": xyxy,
                    "severity": "postprocess_pending",
                    "risk_level": "postprocess_pending",
                    "suggestion": "Postprocess placeholder only; no pesticide dosage or mandatory action advice.",
                }
            )
        image_path = Path(result.path)
        all_results.append(
            {
                "type": "detection_result",
                "record_id": image_path.stem,
                "image_id": image_path.stem,
                "image_name": image_path.name,
                "source_type": args.source_type,
                "category_type": target_type_for_source(args.source_type),
                "current_target_type": target_type_for_source(args.source_type),
                "model_name": choose_model(args.source_type, args.model_name),
                "model_version": args.model_version,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "is_mock": False,
                "detections": detections,
                "summary": postprocess_summary(detections),
                "boundary": "real inference run; severity/risk/suggestion remain postprocess placeholders",
            }
        )
    return {"results": all_results}


def main() -> int:
    args = parse_args()
    weights = resolve_path(args.weights)
    if not weights or not weights.exists():
        result: dict[str, Any] = skeleton(args, "weights missing; schema preview only; no fake detections")
    elif importlib.util.find_spec("ultralytics") is None:
        result = skeleton(args, "ultralytics not installed; schema preview only; no fake detections")
    elif not args.execute:
        result = skeleton(args, "dry-run with existing weights; pass --execute to run real inference")
    else:
        result = run_inference(args)

    output_path = resolve_path(args.output_json) or Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
