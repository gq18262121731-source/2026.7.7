from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from expand_blb_uav_preview_dataset import (
    CLASS_CODE,
    DEFAULT_SOURCE_DATASETS,
    ensure_output,
    execute_conversion,
    find_pairs,
    repo_root,
    resolve_path,
    runtime_missing,
    scan_candidates,
    select_candidates,
    write_metadata,
    write_static_files,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a constrained UAV BLB expanded preview dataset plan or dataset."
    )
    parser.add_argument("--input-root", default="raw_datasets/blb_uav_dataset/original")
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--target-size", type=int, choices=(600, 800), default=600)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--min-area-pixels", type=int, default=25)
    parser.add_argument("--balance-severity", action="store_true", default=True)
    parser.add_argument("--source-datasets", nargs="+", default=list(DEFAULT_SOURCE_DATASETS))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def default_output_root(target_size: int) -> str:
    return f"datasets/rice_uav_ms_blb_preview_{target_size}"


def manifest_path_for_output(output_root: Path) -> Path:
    return output_root / "preview_build_manifest.json"


def relative_for_report(path: Path) -> str:
    try:
        return str(path.relative_to(repo_root())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_root = resolve_path(args.input_root)
    output_root = resolve_path(args.output_root or default_output_root(args.target_size))
    mode = "execute" if args.execute else "dry-run"

    report: dict[str, Any] = {
        "tool_name": "build_uav_blb_expanded_preview",
        "boundary": "dataset planning/conversion only; no training, no weights, no formal metrics",
        "mode": mode,
        "input_root": relative_for_report(input_root),
        "output_root": relative_for_report(output_root),
        "target_size": args.target_size,
        "seed": args.seed,
        "min_area_pixels": args.min_area_pixels,
        "source_datasets": args.source_datasets,
        "balance_severity": bool(args.balance_severity),
        "class_map": {"0": CLASS_CODE},
        "missing_dependencies": runtime_missing(),
        "status": "planned",
    }

    ensure_output(output_root)
    if report["missing_dependencies"]:
        report["status"] = "dependency_missing"
        write_manifest(manifest_path_for_output(output_root), report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    if not input_root.exists():
        report["status"] = "input_root_missing"
        write_manifest(manifest_path_for_output(output_root), report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    pairs = find_pairs(input_root, args.source_datasets)
    candidates, scan_report = scan_candidates(pairs, args.min_area_pixels)
    selected, selection_report = select_candidates(
        candidates, args.target_size, args.seed, args.balance_severity
    )
    report["pair_count"] = len(pairs)
    report["positive_candidate_count"] = len(candidates)
    report["scan"] = scan_report
    report["selection"] = selection_report
    report["feasible_to_target"] = selection_report.get("selected_count", 0) >= args.target_size
    report["shortfall_count"] = max(0, args.target_size - selection_report.get("selected_count", 0))
    report["selected_preview"] = [
        {
            "source_dataset": item.pair.dataset,
            "source_split": item.pair.split,
            "patch_id": item.pair.patch_id,
            "severity": item.severity_key,
            "bbox_count": len(item.boxes),
        }
        for item in selected[:20]
    ]

    if not args.execute:
        write_static_files(output_root)
        write_metadata(output_root, [])
        write_manifest(manifest_path_for_output(output_root), report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    conversion_report = execute_conversion(selected, input_root, output_root)
    report["conversion"] = conversion_report
    report["status"] = (
        "converted"
        if conversion_report.get("metadata_rows", 0) == args.target_size
        else "converted_with_shortfall"
    )
    write_manifest(manifest_path_for_output(output_root), report)
    (output_root / "conversion_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if conversion_report.get("metadata_rows", 0) > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
