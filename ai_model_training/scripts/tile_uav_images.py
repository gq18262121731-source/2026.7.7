"""UAV image tiling skeleton.

The coordinate conversion logic is intentionally conservative and marked as a
placeholder until real annotation format and source image conventions are known.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tile UAV large images for YOLO training.")
    parser.add_argument("--input-dir", required=True, help="Directory with UAV large images.")
    parser.add_argument("--label-dir", help="Optional YOLO label directory for source images.")
    parser.add_argument("--output-dir", required=True, help="Output directory for tiles and converted labels.")
    parser.add_argument("--tile-size", type=int, default=1024)
    parser.add_argument("--overlap", type=float, default=0.2, help="Overlap ratio, 0.0-0.9.")
    parser.add_argument("--min-object-keep-ratio", type=float, default=0.5)
    parser.add_argument("--dry-run", action="store_true", help="Only write a tiling plan.")
    return parser.parse_args()


def build_tiling_plan(args: argparse.Namespace) -> dict[str, object]:
    input_dir = Path(args.input_dir)
    images = sorted(p for p in input_dir.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff"})
    return {
        "boundary": "tiling plan skeleton; label conversion requires real image sizes and annotation review",
        "input_dir": str(input_dir),
        "label_dir": args.label_dir,
        "output_dir": args.output_dir,
        "tile_size": args.tile_size,
        "overlap": args.overlap,
        "min_object_keep_ratio": args.min_object_keep_ratio,
        "image_count": len(images),
        "images": [str(p) for p in images],
        "todo": [
            "open image to get width/height",
            "generate sliding-window coordinates",
            "crop image tiles",
            "convert YOLO boxes into tile-local coordinates",
            "drop or clip boxes by min_object_keep_ratio",
            "write tile metadata for stitching predictions back to source image",
        ],
    }


def main() -> int:
    args = parse_args()
    if not 0 <= args.overlap < 0.9:
        raise ValueError("--overlap must be in [0, 0.9)")
    if not 0 <= args.min_object_keep_ratio <= 1:
        raise ValueError("--min-object-keep-ratio must be in [0, 1]")
    plan = build_tiling_plan(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "tiling_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(plan, ensure_ascii=False, indent=2) if args.dry_run else f"Tiling plan written to {plan_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
