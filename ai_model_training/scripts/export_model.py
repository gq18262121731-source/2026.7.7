"""Model export skeleton.

Reserved for exporting trained YOLO weights to deployment formats. This delivery
round does not create fake weights or exported artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SUPPORTED_FORMATS = ("pt", "onnx", "tensorrt", "ncnn")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare model export plan without exporting.")
    parser.add_argument("--weights", required=True)
    parser.add_argument("--formats", nargs="+", default=["pt", "onnx"], choices=SUPPORTED_FORMATS)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--execute", action="store_true", help="Reserved. Currently blocked by design.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.execute:
        raise RuntimeError("Real model export is blocked in this delivery round.")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    plan = {
        "boundary": "export plan only; no artifacts generated",
        "weights": args.weights,
        "formats": args.formats,
        "output_dir": str(output_dir),
        "expected_artifacts": {
            "pt": "original or copied PyTorch weight after real training",
            "onnx": "ONNX model after approved export",
            "tensorrt": "TensorRT engine after target hardware confirmation",
            "ncnn": "NCNN param/bin after mobile deployment confirmation",
        },
    }
    plan_path = output_dir / "export_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
