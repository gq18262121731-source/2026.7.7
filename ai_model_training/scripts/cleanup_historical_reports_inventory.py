#!/usr/bin/env python
"""Inventory historical reports and produce a conservative cleanup dry-run."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SCAN_DIRS = ("reports", "metadata", "configs", "model_delivery")
OUTPUT_CSV = Path("reports/report_cleanup_inventory.csv")
OUTPUT_JSON = Path("reports/report_cleanup_inventory.json")
OUTPUT_MD = Path("reports/report_cleanup_inventory.md")
DRY_RUN_JSON = Path("reports/report_cleanup_dry_run_plan.json")
DRY_RUN_MD = Path("reports/report_cleanup_dry_run_plan.md")

ARCHIVE_ROOT = Path("reports/_archive")
ARCHIVE_DIRS = (
    ARCHIVE_ROOT,
    ARCHIVE_ROOT / "obsolete_hotfix_reports",
    ARCHIVE_ROOT / "superseded_plans",
    ARCHIVE_ROOT / "old_diagnostics",
    ARCHIVE_ROOT / "old_frontend_review_app",
    ARCHIVE_ROOT / "old_intermediate_summaries",
    ARCHIVE_ROOT / "misc_reviewed_keep_copy",
)

CURRENT_KEEP_FILES = {
    "reports/next_stage_dual_line_execution_plan_and_status_report.md",
    "reports/dual_line_next_execution_results_report.md",
    "reports/dual_line_gate_followup_analysis_report.md",
    "reports/project_current_model_status_summary.md",
    "reports/demo_model_boundary_statement.md",
    "reports/uav_phone_dual_line_roadmap.md",
    "reports/frontend_demo_model_hint_policy.md",
    "reports/defense_talking_points_model_limitations.md",
    "reports/uav_blb_ab_eval_comparison.md",
    "reports/uav_blb_ab_eval_comparison.json",
    "reports/thirty_second_round_b_uav_blb_apples_to_apples_ab_eval_report.md",
    "reports/uav_blb_zero_detection_error_analysis.md",
    "reports/uav_blb_hard_case_review_plan.md",
    "reports/uav_blb_cleaned408_v2_plan.md",
    "reports/uav_blb_strict408_v0_2_validation_metrics.md",
    "reports/uav_blb_strict408_v0_2_validation_metrics.json",
    "reports/uav_blb_strict408_v0_2_candidate_gate_report.md",
    "reports/uav_blb_strict408_v0_2_candidate_gate_report.json",
    "reports/uav_blb_strict408_v0_2_vs_exp408_epoch5_comparison.md",
    "reports/uav_blb_strict408_v0_2_vs_exp408_epoch5_comparison.json",
    "reports/thirty_first_round_b_uav_blb_strict408_controlled_run_report.md",
    "reports/thirtieth_round_b_uav_blb_rule_change_review_report.md",
    "reports/uav_blb_rule_change_impact_matrix.md",
    "reports/uav_blb_rule_change_impact_matrix.json",
    "reports/uav_blb_rule_change_impact_matrix.csv",
    "reports/riceseg_preview_200_dataset_check.json",
    "reports/riceseg_preview_200_dataset_check.md",
    "reports/riceseg_preview_200_conversion_quality_summary.md",
    "reports/riceseg_preview_200_visual_audit/index.md",
    "reports/thirtieth_round_a_riceseg_preview200_manual_review_report.md",
    "reports/riceseg_preview_200_manual_review_items.csv",
    "reports/riceseg_preview_200_manual_review_items.json",
    "reports/riceseg_preview_200_manual_review_decisions.csv",
    "reports/riceseg_preview_200_manual_review_decisions.json",
    "reports/riceseg_preview_200_manual_review_summary.json",
    "reports/riceseg_preview_200_manual_review_gate_report.md",
    "reports/riceseg_preview_200_start_review_desktop.bat",
    "reports/riceseg_preview_200_review_desktop.log",
    "metadata/phone_dataset_status.yaml",
    "metadata/uav_blb_model_registry.yaml",
    "metadata/uav_blb_model_registry_update_draft.yaml",
    "metadata/uav_blb_model_registry_update_draft_v2.yaml",
}

HIGH_RISK_KEYWORDS = (
    "gate",
    "validation",
    "metrics",
    "comparison",
    "registry",
    "delivery",
    "manifest",
    "dataset_check",
    "quality_recheck",
    "backend",
    "integration",
    "model_status",
    "current",
    "final",
    "summary",
    "strict408",
    "ab_eval",
    "riceseg_preview_200",
    "phone_dataset_status",
    "uav_blb_model_registry",
    "decision",
    "roadmap",
    "defense",
    "boundary",
)

EVIDENCE_KEYWORDS = (
    "gate",
    "validation",
    "metrics",
    "comparison",
    "dataset_check",
    "registry",
    "delivery",
    "backend_integration_decision",
    "quality",
    "audit",
    "manual_review",
    "visual_audit",
    "infer",
    "sample",
)

ARCHIVE_HOTFIX_KEYWORDS = ("hotfix", "startup_error", "smoke_display")
FRONTEND_REVIEW_KEYWORDS = ("review_app", "desktop_review_app", "weak_class_review")
OLD_DIAGNOSTIC_KEYWORDS = (
    "startup_error",
    "download_blocking",
    "tmp",
    "temporary",
    "diagnostic",
)
PLAN_KEYWORDS = ("next_steps", "next_stage_plan", "gate_plan", "long_train_plan", "optimization_plan")
ROUND_WORDS = (
    "first_round",
    "second_round",
    "third_round",
    "fourth_round",
    "fifth_round",
    "sixth_round",
    "seventh_round",
    "eighth_round",
    "ninth_round",
    "tenth_round",
    "eleventh_round",
    "twelfth_round",
    "thirteenth_round",
    "fourteenth_round",
    "fifteenth_round",
    "sixteenth_round",
    "seventeenth_round",
    "eighteenth_round",
    "nineteenth_round",
    "twentieth_round",
    "twenty_first_round",
    "twenty_second_round",
    "twenty_third_round",
    "twenty_fourth_round",
    "twenty_fifth_round",
    "twenty_sixth_round",
    "twenty_seventh_round",
    "twenty_eighth_round",
    "twenty_ninth_round",
)

REPORT_EXTENSIONS = {".md", ".json", ".csv", ".yaml", ".yml", ".txt", ".log", ".bat"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass
class InventoryRow:
    file_path: str
    file_name: str
    extension: str
    size_bytes: int
    modified_time: str
    category_guess: str
    keep_reason: str
    archive_reason: str
    recommended_action: str
    risk_level: str


def normalize_path(path: Path) -> str:
    return path.as_posix()


def iter_files(root: Path) -> Iterable[Path]:
    for scan_dir in SCAN_DIRS:
        base = root / scan_dir
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                rel = path.relative_to(root)
                if rel.parts[:2] == ("reports", "_archive"):
                    continue
                yield path


def guess_category(rel: str, path: Path) -> str:
    lower = rel.lower()
    suffix = path.suffix.lower()
    if lower.startswith("model_delivery/"):
        return "delivery package"
    if lower.startswith("metadata/"):
        return "metadata registry/status"
    if lower.startswith("configs/"):
        return "training config"
    if "visual_audit" in lower:
        return "visual audit artifact"
    if "infer_inputs" in lower or "infer_samples" in lower or "yolo_val" in lower:
        return "inference or validation sample"
    if suffix in IMAGE_EXTENSIONS:
        return "image evidence artifact"
    if any(keyword in lower for keyword in ARCHIVE_HOTFIX_KEYWORDS):
        return "old hotfix report"
    if any(keyword in lower for keyword in FRONTEND_REVIEW_KEYWORDS):
        return "old frontend review app report"
    if any(keyword in lower for keyword in OLD_DIAGNOSTIC_KEYWORDS):
        return "old diagnostic/log artifact"
    if any(keyword in lower for keyword in PLAN_KEYWORDS):
        return "intermediate plan"
    if any(word in lower for word in ROUND_WORDS):
        return "round summary report"
    if suffix in REPORT_EXTENSIONS:
        return "report or manifest"
    return "misc scanned artifact"


def classify(rel: str, path: Path) -> tuple[str, str, str, str]:
    lower = rel.lower()
    suffix = path.suffix.lower()
    name = path.name.lower()
    category = guess_category(rel, path)

    if rel in CURRENT_KEEP_FILES:
        return ("KEEP", "high", "explicit current evidence-chain file", "")

    if "report_cleanup_" in lower or "historical_report_cleanup" in lower:
        return ("KEEP", "high", "current cleanup evidence/report is protected", "")

    if lower.startswith("model_delivery/"):
        return ("KEEP", "high", "model_delivery package is protected", "")

    if lower.startswith("metadata/"):
        if "registry" in lower or "status" in lower or "manifest" in lower:
            return ("KEEP", "high", "metadata registry/status/manifest is protected", "")
        return ("NEEDS_REVIEW", "medium", "", "metadata file is outside explicit registry/status list")

    if lower.startswith("configs/"):
        return ("KEEP", "high", "training configs are protected by current-round constraints", "")

    if suffix in IMAGE_EXTENSIONS:
        return ("KEEP", "medium", "image evidence/sample artifact; not an old report", "")

    if "riceseg_preview_200_visual_audit/" in lower:
        return ("KEEP", "high", "Phone preview_200 visual audit entry is protected", "")

    if any(keyword in lower for keyword in HIGH_RISK_KEYWORDS):
        return ("KEEP", "high", "filename contains protected evidence-chain keyword", "")

    if any(keyword in lower for keyword in EVIDENCE_KEYWORDS):
        return ("KEEP", "high", "validation/audit/evidence artifact is protected", "")

    if suffix not in REPORT_EXTENSIONS:
        return ("NEEDS_REVIEW", "medium", "", "non-report extension in scanned report tree")

    if any(keyword in lower for keyword in ARCHIVE_HOTFIX_KEYWORDS):
        return ("ARCHIVE_CANDIDATE", "low", "", "old hotfix or startup process report")

    if any(keyword in lower for keyword in FRONTEND_REVIEW_KEYWORDS):
        return ("ARCHIVE_CANDIDATE", "low", "", "old frontend review app process report")

    if any(keyword in lower for keyword in OLD_DIAGNOSTIC_KEYWORDS):
        return ("ARCHIVE_CANDIDATE", "low", "", "old diagnostic/log artifact")

    if any(keyword in lower for keyword in PLAN_KEYWORDS) and "twenty_eighth" not in lower:
        return ("ARCHIVE_CANDIDATE", "low", "", "intermediate plan likely superseded by current dual-line report")

    if any(word in lower for word in ROUND_WORDS):
        return ("ARCHIVE_CANDIDATE", "low", "", "older round summary likely superseded by current stage reports")

    if name.startswith("train_args_") or name.startswith("train_yolo_tmp"):
        return ("ARCHIVE_CANDIDATE", "low", "", "old intermediate training-argument snapshot")

    if suffix == ".log":
        return ("ARCHIVE_CANDIDATE", "low", "", "old log file outside protected current review entry")

    return ("NEEDS_REVIEW", "medium", "", "no conservative rule matched")


def build_inventory(root: Path) -> list[InventoryRow]:
    rows: list[InventoryRow] = []
    for path in iter_files(root):
        rel = normalize_path(path.relative_to(root))
        stat = path.stat()
        action, risk, keep_reason, archive_reason = classify(rel, path)
        rows.append(
            InventoryRow(
                file_path=rel,
                file_name=path.name,
                extension=path.suffix.lower(),
                size_bytes=stat.st_size,
                modified_time=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                category_guess=guess_category(rel, path),
                keep_reason=keep_reason,
                archive_reason=archive_reason,
                recommended_action=action,
                risk_level=risk,
            )
        )
    return rows


def write_csv(path: Path, rows: list[InventoryRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(InventoryRow.__dataclass_fields__.keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def markdown_table(rows: list[dict[str, object]], columns: list[str], limit: int | None = None) -> str:
    selected = rows[:limit] if limit else rows
    if not selected:
        return "_None._\n"
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in selected:
        values = [str(row.get(col, "")).replace("\n", " ") for col in columns]
        lines.append("| " + " | ".join(values) + " |")
    if limit and len(rows) > limit:
        lines.append(f"\n_Showing {limit} of {len(rows)} rows. See CSV/JSON for full inventory._")
    return "\n".join(lines) + "\n"


def summarize(rows: list[InventoryRow]) -> dict[str, object]:
    counts = {action: 0 for action in ("KEEP", "ARCHIVE_CANDIDATE", "NEEDS_REVIEW", "DO_NOT_TOUCH")}
    risk_counts = {risk: 0 for risk in ("low", "medium", "high")}
    total_size = 0
    archive_size = 0
    for row in rows:
        counts[row.recommended_action] += 1
        risk_counts[row.risk_level] += 1
        total_size += row.size_bytes
        if row.recommended_action == "ARCHIVE_CANDIDATE":
            archive_size += row.size_bytes
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scan_dirs": list(SCAN_DIRS),
        "total_scanned_files": len(rows),
        "counts_by_action": counts,
        "counts_by_risk": risk_counts,
        "total_size_bytes": total_size,
        "estimated_size_to_archive_bytes": archive_size,
        "deletion_executed": False,
        "archive_executed": False,
        "statement": "Dry-run only: no files were deleted and no files were moved.",
    }


def write_inventory_markdown(path: Path, rows: list[InventoryRow], summary: dict[str, object]) -> None:
    row_dicts = [asdict(row) for row in rows]
    columns = [
        "file_path",
        "category_guess",
        "recommended_action",
        "risk_level",
        "keep_reason",
        "archive_reason",
    ]
    content = [
        "# Report Cleanup Inventory",
        "",
        "Dry-run inventory for historical reports and evidence-chain artifacts.",
        "",
        "## Summary",
        "",
        f"- Generated at: {summary['generated_at']}",
        f"- Scanned directories: {', '.join(summary['scan_dirs'])}",
        f"- Total scanned files: {summary['total_scanned_files']}",
        f"- KEEP: {summary['counts_by_action']['KEEP']}",
        f"- ARCHIVE_CANDIDATE: {summary['counts_by_action']['ARCHIVE_CANDIDATE']}",
        f"- NEEDS_REVIEW: {summary['counts_by_action']['NEEDS_REVIEW']}",
        f"- DO_NOT_TOUCH: {summary['counts_by_action']['DO_NOT_TOUCH']}",
        f"- Estimated size to archive: {summary['estimated_size_to_archive_bytes']} bytes",
        "- Deletion executed: no",
        "- Archive executed: no",
        "",
        "## Inventory Preview",
        "",
        markdown_table(row_dicts, columns, limit=250),
    ]
    path.write_text("\n".join(content), encoding="utf-8")


def write_dry_run_plan(root: Path, rows: list[InventoryRow], summary: dict[str, object]) -> None:
    row_dicts = [asdict(row) for row in rows]
    archive_candidates = [row for row in row_dicts if row["recommended_action"] == "ARCHIVE_CANDIDATE"]
    high_risk_keep = [
        row
        for row in row_dicts
        if row["recommended_action"] == "KEEP" and row["risk_level"] == "high"
    ]
    needs_review = [row for row in row_dicts if row["recommended_action"] == "NEEDS_REVIEW"]
    payload = {
        **summary,
        "archive_candidate_table": archive_candidates,
        "high_risk_keep_table": high_risk_keep,
        "needs_review_table": needs_review,
        "no_deletion_statement": "No permanent deletion is performed by this dry-run.",
    }
    write_json(root / DRY_RUN_JSON, payload)

    columns = ["file_path", "size_bytes", "category_guess", "archive_reason", "risk_level"]
    keep_columns = ["file_path", "category_guess", "keep_reason", "risk_level"]
    review_columns = ["file_path", "category_guess", "archive_reason", "risk_level"]
    md = [
        "# Historical Report Cleanup Dry-Run Plan",
        "",
        "This plan is a dry-run only. No files were deleted, no files were moved, and no training or backend work was run.",
        "",
        "## Counts",
        "",
        f"- Total scanned files: {summary['total_scanned_files']}",
        f"- KEEP count: {summary['counts_by_action']['KEEP']}",
        f"- ARCHIVE_CANDIDATE count: {summary['counts_by_action']['ARCHIVE_CANDIDATE']}",
        f"- NEEDS_REVIEW count: {summary['counts_by_action']['NEEDS_REVIEW']}",
        f"- DO_NOT_TOUCH count: {summary['counts_by_action']['DO_NOT_TOUCH']}",
        f"- Estimated size to archive: {summary['estimated_size_to_archive_bytes']} bytes",
        "",
        "## Archive Candidate Table",
        "",
        markdown_table(archive_candidates, columns, limit=200),
        "",
        "## High-Risk Keep Table",
        "",
        markdown_table(high_risk_keep, keep_columns, limit=200),
        "",
        "## Needs-Review Table",
        "",
        markdown_table(needs_review, review_columns, limit=200),
        "",
        "## No Deletion Statement",
        "",
        "No permanent deletion is executed in this round. Archive execution is also withheld until explicit user approval.",
        "",
    ]
    (root / DRY_RUN_MD).write_text("\n".join(md), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    for directory in ARCHIVE_DIRS:
        (root / directory).mkdir(parents=True, exist_ok=True)

    rows = build_inventory(root)
    summary = summarize(rows)
    write_csv(root / OUTPUT_CSV, rows)
    write_json(root / OUTPUT_JSON, {"summary": summary, "files": [asdict(row) for row in rows]})
    write_inventory_markdown(root / OUTPUT_MD, rows, summary)
    write_dry_run_plan(root, rows, summary)

    print(f"Scanned {len(rows)} files.")
    print(f"Wrote {OUTPUT_CSV}, {OUTPUT_JSON}, {OUTPUT_MD}.")
    print(f"Wrote {DRY_RUN_JSON}, {DRY_RUN_MD}.")
    print("Dry-run only: no files were deleted or moved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
