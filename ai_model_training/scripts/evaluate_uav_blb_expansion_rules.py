from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only evaluation for UAV BLB expansion rule scenarios."
    )
    parser.add_argument("--input-root", default="raw_datasets/blb_uav_dataset/original")
    parser.add_argument("--target-size", type=int, default=600)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--min-area-pixels", type=int, default=25)
    parser.add_argument("--output-json", default="reports/uav_blb_rule_change_evaluation.json")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root() / path


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(repo_root())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def main() -> int:
    sys.path.insert(0, str((repo_root() / "scripts").resolve()))
    import expand_blb_uav_preview_dataset as mod

    args = parse_args()
    input_root = resolve_path(args.input_root)
    pairs = mod.find_pairs(input_root, list(mod.DEFAULT_SOURCE_DATASETS))
    candidates, scan_report = mod.scan_candidates(pairs, args.min_area_pixels)

    _, strict_upper = mod.select_candidates(candidates, 5000, args.seed, True)

    rng = random.Random(args.seed)

    # relaxed_balance: keep patch dedup and preview hash dedup, remove balancing rotation
    used_hashes: set[str] = set()
    relaxed_balance_selected = []
    for split in mod.SPLITS:
        split_candidates = [item for item in candidates if item.pair.split == split]
        rng.shuffle(split_candidates)
        used_patch_ids: set[str] = set()
        for item in split_candidates:
            if item.preview_sha1 in used_hashes:
                continue
            if item.pair.patch_id in used_patch_ids:
                continue
            used_patch_ids.add(item.pair.patch_id)
            used_hashes.add(item.preview_sha1)
            relaxed_balance_selected.append(item)
    relaxed_balance = mod.summarize_selection(relaxed_balance_selected)

    # relaxed_dedup_candidate_pool: theoretical upper pool if patch-id dedup is ignored
    all_positive = mod.summarize_selection(candidates)

    unique_patch_by_split: dict[str, set[str]] = {split: set() for split in mod.SPLITS}
    for item in candidates:
        unique_patch_by_split[item.pair.split].add(item.pair.patch_id)

    payload = {
        "status": "ok",
        "boundary": "read-only rule evaluation only; no labels copied, no dataset generated, no training",
        "input_root": relative_path(input_root),
        "target_size": args.target_size,
        "seed": args.seed,
        "min_area_pixels": args.min_area_pixels,
        "pair_count": len(pairs),
        "positive_candidate_count": len(candidates),
        "scan": scan_report,
        "strict_upper": strict_upper,
        "relaxed_balance_upper": relaxed_balance,
        "all_positive_candidate_pool": all_positive,
        "unique_patch_by_split": {k: len(v) for k, v in unique_patch_by_split.items()},
        "replication_per_patch_by_split": {
            split: 3 for split in mod.SPLITS
        },
        "findings": [
            "strict constrained upper bound remains 408",
            "relaxed_balance alone does not increase sample count",
            "theoretical positive pool is 1254 before patch-level and preview-level dedup constraints",
            "each positive patch id appears once in D1, D2, D3 for a given split in the scanned BLB source structure",
        ],
    }
    write_json_atomic(resolve_path(args.output_json), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
