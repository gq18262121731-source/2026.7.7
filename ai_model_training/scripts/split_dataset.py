"""Grouped train/val/test splitter skeleton.

This script prepares a split plan and can optionally copy files in a later stage.
It is designed to prevent leakage by grouping samples with the same plot, flight
task, date, device, or other metadata field.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create grouped train/val/test split plan.")
    parser.add_argument("--metadata", required=True, help="CSV with image_id/source_file and group columns.")
    parser.add_argument("--output-plan", required=True, help="Output JSON split plan.")
    parser.add_argument("--group-key", default="plot_id", help="Metadata column used to avoid leakage.")
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--test-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--dry-run", action="store_true", help="Print plan only; no file operation.")
    return parser.parse_args()


def validate_ratios(train: float, val: float, test: float) -> None:
    total = train + val + test
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Split ratios must sum to 1.0, got {total:.4f}")


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def grouped_split(rows: list[dict[str, str]], group_key: str, ratios: tuple[float, float, float], seed: int) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        group_value = row.get(group_key) or row.get("image_id") or row.get("source_file") or "ungrouped"
        groups[group_value].append(row)

    rng = random.Random(seed)
    group_items = list(groups.items())
    rng.shuffle(group_items)

    total = sum(len(items) for _, items in group_items)
    train_target = total * ratios[0]
    val_target = total * ratios[1]
    splits = {"train": [], "val": [], "test": []}

    for _, items in group_items:
        if len(splits["train"]) < train_target:
            target = "train"
        elif len(splits["val"]) < val_target:
            target = "val"
        else:
            target = "test"
        splits[target].extend(items)
    return splits


def main() -> int:
    args = parse_args()
    validate_ratios(args.train_ratio, args.val_ratio, args.test_ratio)
    rows = load_rows(Path(args.metadata))
    splits = grouped_split(rows, args.group_key, (args.train_ratio, args.val_ratio, args.test_ratio), args.seed)
    plan = {
        "boundary": "split plan only; no training and no metrics",
        "metadata": args.metadata,
        "group_key": args.group_key,
        "seed": args.seed,
        "ratios": {"train": args.train_ratio, "val": args.val_ratio, "test": args.test_ratio},
        "counts": {name: len(items) for name, items in splits.items()},
        "splits": splits,
        "next_step": "After human review, implement/call file copy or move with explicit approval.",
    }
    output = json.dumps(plan, ensure_ascii=False, indent=2)
    Path(args.output_plan).write_text(output + "\n", encoding="utf-8")
    print(output if args.dry_run else f"Split plan written to {args.output_plan}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
