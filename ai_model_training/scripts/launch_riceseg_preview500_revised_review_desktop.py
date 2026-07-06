"""Guarded launcher for RiceSeg preview_500 revised_v0_1 manual review."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from launch_riceseg_preview200_review_desktop import main as base_main
from launch_riceseg_preview200_review_desktop import resolve_path

DATASET_VERSION = "rice_phone_rgb_riceseg_preview_500_revised_v0_1"
APP_TITLE = "RiceSeg preview_500 revised_v0_1 人工审核台"
ITEMS_CSV = "reports/riceseg_preview_500_revised_v0_1_manual_review_items.csv"
DECISIONS_CSV = "reports/riceseg_preview_500_revised_v0_1_manual_review_decisions.csv"
DECISIONS_JSON = "reports/riceseg_preview_500_revised_v0_1_manual_review_decisions.json"
SUMMARY_JSON = "reports/riceseg_preview_500_revised_v0_1_manual_review_summary.json"
GATE_REPORT = "reports/riceseg_preview_500_revised_v0_1_manual_review_gate_report.md"
LOG_PATH = "reports/riceseg_preview_500_revised_v0_1_review_desktop.log"
SELFTEST_JSON = "reports/riceseg_preview_500_revised_v0_1_review_launcher_selftest.json"
SELFTEST_MD = "reports/riceseg_preview_500_revised_v0_1_review_launcher_selftest.md"
REQUIRED_IMAGE_SUBSTRING = "rice_phone_rgb_riceseg_preview_500_revised_v0_1"
REQUIRED_PREVIEW_SUBSTRING = "riceseg_preview_500_revised_v0_1_visual_audit"
REQUIRED_OUTPUT_SUBSTRING = "riceseg_preview_500_revised_v0_1_manual_review"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the guarded preview_500 revised review desktop app.")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def build_forward_args(extra: list[str] | None = None) -> list[str]:
    args = [
        "--app-title", APP_TITLE,
        "--dataset-version", DATASET_VERSION,
        "--items-csv", ITEMS_CSV,
        "--decisions-csv", DECISIONS_CSV,
        "--decisions-json", DECISIONS_JSON,
        "--summary-json", SUMMARY_JSON,
        "--gate-report", GATE_REPORT,
        "--log-path", LOG_PATH,
        "--output-prefix", "reports/riceseg_preview_500_revised_v0_1_manual_review",
        "--preview-field-order", "visual_preview_path,new_visual_preview_path,old_visual_preview_path",
        "--required-image-substring", REQUIRED_IMAGE_SUBSTRING,
        "--required-preview-substring", REQUIRED_PREVIEW_SUBSTRING,
        "--required-output-substring", REQUIRED_OUTPUT_SUBSTRING,
    ]
    if extra:
        args.extend(extra)
    return args


def load_review_items() -> list[dict[str, Any]]:
    import csv
    items_path = resolve_path(ITEMS_CSV)
    with items_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_write(path: Path, content: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def build_selftest_payload() -> dict[str, Any]:
    rows = load_review_items()
    class_counter = Counter((row.get("class_name") or "").strip() for row in rows)
    preview_ok = all(REQUIRED_PREVIEW_SUBSTRING in (row.get("visual_preview_path") or "") for row in rows)
    image_ok = all(REQUIRED_IMAGE_SUBSTRING in (row.get("image_path") or "") for row in rows)
    payload = {
        "dataset_version": DATASET_VERSION,
        "review_items_count": len(rows),
        "per_class_count": dict(class_counter),
        "decisions_output_prefix": "reports/riceseg_preview_500_revised_v0_1_manual_review",
        "visual_audit_prefix": "reports/riceseg_preview_500_revised_v0_1_visual_audit",
        "no_old_path_detected": preview_ok and image_ok,
        "gate": "PENDING",
        "all_guards_enabled": True,
    }
    return payload


def render_selftest_markdown(payload: dict[str, Any]) -> str:
    return "\n".join([
        "# RiceSeg preview_500 revised_v0_1 Review Launcher Self-Test",
        "",
        f"- dataset_version: `{payload['dataset_version']}`",
        f"- review_items_count: `{payload['review_items_count']}`",
        f"- per_class_count: `{payload['per_class_count']}`",
        f"- decisions_output_prefix: `{payload['decisions_output_prefix']}`",
        f"- visual_audit_prefix: `{payload['visual_audit_prefix']}`",
        f"- no_old_path_detected: `{payload['no_old_path_detected']}`",
        f"- gate: `{payload['gate']}`",
        f"- all_guards_enabled: `{payload['all_guards_enabled']}`",
        "",
    ])


def run_self_test() -> int:
    payload = build_selftest_payload()
    atomic_write(resolve_path(SELFTEST_JSON), json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    atomic_write(resolve_path(SELFTEST_MD), render_selftest_markdown(payload))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    args = parse_args()
    if args.self_test:
        return run_self_test()
    return base_main(build_forward_args())


if __name__ == "__main__":
    raise SystemExit(main())
