"""Plan cleaned408_v2 label correction from UAV BLB 408 manual review results.

Read-only against source images and labels.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
METADATA = ROOT / "metadata"
DECISIONS_CSV = REPORTS / "uav_blb_408_manual_review_decisions.csv"
SUMMARY_JSON = REPORTS / "uav_blb_408_manual_review_summary.json"
GATE_REPORT = REPORTS / "uav_blb_408_manual_review_gate_report.md"

OVERLAP_CSV = REPORTS / "uav_blb_408_cleaned408_v2_overlap_duplicate_analysis.csv"
FIX_CSV = REPORTS / "uav_blb_408_cleaned408_v2_targeted_fix_list.csv"
PLAN_MD = REPORTS / "uav_blb_408_cleaned408_v2_plan.md"
REVIEW_PLAN_MD = REPORTS / "uav_blb_408_cleaned408_v2_targeted_review_plan.md"
STATUS_YAML = METADATA / "uav_blb_cleaned408_v2_status.yaml"

FIX_ISSUES = {
    "OVERLAP_DUPLICATE_BBOX",
    "LARGE_BBOX_AREA",
    "SMALL_OR_MISSING_BBOX",
    "box_misaligned",
    "box_too_large",
    "box_too_small",
    "missing_bbox",
}
REVIEW_ISSUES = {"FRAGMENTED_PATCH", "EDGE_CUT_OR_BLUR", "unclear", "blur"}
REJECT_ISSUES = {"MULTISPECTRAL_NOISE_TEXTURE", "UNUSABLE_SAMPLE", "bad_image", "wrong_target"}
ACCEPT_ISSUES = {"OK_STANDARD", "ok"}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def atomic_write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    tmp.replace(path)


def read_decisions() -> list[dict[str, str]]:
    with DECISIONS_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_yolo_label(path: Path) -> list[dict[str, Any]]:
    boxes: list[dict[str, Any]] = []
    if not path.exists():
        return boxes
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            class_id = int(float(parts[0]))
            x, y, w, h = [float(value) for value in parts[1:]]
        except ValueError:
            continue
        boxes.append(
            {
                "bbox_id": idx,
                "class_id": class_id,
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "area": w * h,
                "xyxy": (x - w / 2, y - h / 2, x + w / 2, y + h / 2),
            }
        )
    return boxes


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = inter_w * inter_h
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return inter / denom if denom else 0.0


def pairwise_overlap(boxes: list[dict[str, Any]], threshold: float = 0.50) -> tuple[int, float, list[str]]:
    duplicate_pairs: list[str] = []
    max_iou = 0.0
    for i, box_a in enumerate(boxes):
        for box_b in boxes[i + 1 :]:
            value = iou(box_a["xyxy"], box_b["xyxy"])
            max_iou = max(max_iou, value)
            if value >= threshold:
                duplicate_pairs.append(f"{box_a['bbox_id']}-{box_b['bbox_id']}:{value:.3f}")
    return len(duplicate_pairs), max_iou, duplicate_pairs


def recommended_action(issue_type: str, duplicate_pair_count: int, max_iou: float) -> tuple[str, str]:
    if issue_type == "OVERLAP_DUPLICATE_BBOX" or duplicate_pair_count > 0:
        return "remove_duplicate_bbox", "high"
    if issue_type == "FRAGMENTED_PATCH":
        return "merge_fragmented_bbox_or_second_review", "medium"
    if issue_type in {"SMALL_OR_MISSING_BBOX", "missing_bbox"}:
        return "add_missing_bbox_or_adjust_small_bbox", "high"
    if issue_type in {"LARGE_BBOX_AREA", "box_too_large"}:
        return "adjust_misaligned_bbox", "high"
    if issue_type in {"MULTISPECTRAL_NOISE_TEXTURE", "wrong_target"}:
        return "remove_wrong_target_bbox_or_second_review", "high"
    if issue_type in {"EDGE_CUT_OR_BLUR", "unclear", "blur"}:
        return "second_review_required", "medium"
    return ("clean_seed_no_action", "low") if issue_type in ACCEPT_ISSUES else ("second_review_required", "medium")


def main() -> int:
    rows = read_decisions()
    summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    overlap_rows: list[dict[str, Any]] = []
    fix_rows: list[dict[str, Any]] = []
    issue_counter = Counter(row.get("issue_type", "") for row in rows if row.get("review_status") == "reviewed")

    for row in rows:
        label_path = ROOT / row["label_path"]
        boxes = parse_yolo_label(label_path)
        duplicate_pair_count, max_iou, duplicate_pairs = pairwise_overlap(boxes)
        issue_type = row.get("issue_type", "")
        action, priority = recommended_action(issue_type, duplicate_pair_count, max_iou)
        review_decision = "ACCEPT"
        if issue_type in REVIEW_ISSUES:
            review_decision = "NEEDS_REVIEW"
        elif issue_type in FIX_ISSUES or action.startswith(("remove", "merge", "adjust", "add")):
            review_decision = "NEEDS_FIX"
        elif issue_type in REJECT_ISSUES:
            review_decision = "REJECT"

        if issue_type == "OVERLAP_DUPLICATE_BBOX" or duplicate_pair_count > 0:
            overlap_rows.append(
                {
                    "image_name": row["image_name"],
                    "split": row["split"],
                    "bbox_count": row.get("bbox_count", len(boxes)),
                    "issue_type": issue_type,
                    "duplicate_pair_count": duplicate_pair_count,
                    "max_iou": f"{max_iou:.4f}",
                    "suspected_duplicate_bbox_ids": ";".join(duplicate_pairs),
                    "recommended_action": "remove_duplicate_bbox" if duplicate_pair_count else action,
                    "review_decision": review_decision,
                }
            )

        if review_decision in {"NEEDS_FIX", "NEEDS_REVIEW", "REJECT"}:
            notes = row.get("reviewer_notes", "")
            if issue_type == "OVERLAP_DUPLICATE_BBOX" and not duplicate_pairs:
                notes = (notes + " " if notes else "") + "Manual review marked overlap/duplicate; automatic IoU>=0.50 pair not found, inspect visually."
            fix_rows.append(
                {
                    "image_name": row["image_name"],
                    "split": row["split"],
                    "decision": review_decision,
                    "issue_type": issue_type,
                    "problem_bbox_ids": ";".join(duplicate_pairs),
                    "recommended_action": action,
                    "priority": priority,
                    "notes": notes,
                }
            )

    overlap_fields = [
        "image_name",
        "split",
        "bbox_count",
        "issue_type",
        "duplicate_pair_count",
        "max_iou",
        "suspected_duplicate_bbox_ids",
        "recommended_action",
        "review_decision",
    ]
    fix_fields = [
        "image_name",
        "split",
        "decision",
        "issue_type",
        "problem_bbox_ids",
        "recommended_action",
        "priority",
        "notes",
    ]
    atomic_write_csv(OVERLAP_CSV, overlap_rows, overlap_fields)
    atomic_write_csv(FIX_CSV, fix_rows, fix_fields)

    needs_fix = sum(1 for row in fix_rows if row["decision"] == "NEEDS_FIX")
    needs_review = sum(1 for row in fix_rows if row["decision"] == "NEEDS_REVIEW")
    rejected = sum(1 for row in fix_rows if row["decision"] == "REJECT")
    accepted = sum(1 for row in rows if row.get("issue_type") in ACCEPT_ISSUES)

    atomic_write_text(
        PLAN_MD,
        f"""# UAV BLB 408 cleaned408_v2 Plan

## Current Gate Fail Reason

- source_manual_review: `COMPLETE`
- source_manual_gate: `FAIL`
- reviewed_count: `{summary['reviewed_count']}` / `{summary['review_items_count']}`
- serious_issue_count: `{summary['serious_issue_count']}`
- serious_issue_ratio: `{summary['serious_issue_ratio']}`
- dominant_issue: `OVERLAP_DUPLICATE_BBOX`
- OVERLAP_DUPLICATE_BBOX_count: `{issue_counter.get('OVERLAP_DUPLICATE_BBOX', 0)}`

The data is not rejected because images are unusable. It failed because YOLO bbox annotation quality is not yet stable enough: duplicate/overlap boxes, fragmented patches, and uncertain multispectral texture cases need targeted correction.

## cleaned408_v2 Goal

- Build a derived cleaned label plan for UAV BLB 408 without polluting the original dataset.
- Keep the model class single-class `bacterial_leaf_blight`.
- Treat manual issue types such as `FRAGMENTED_PATCH` and `MULTISPECTRAL_NOISE_TEXTURE` as review metadata only, not YOLO classes.
- Correct duplicate/overlap boxes first, then review fragmented and uncertain samples.

## Cleaning Principles

- Do not overwrite original YOLO labels.
- Prefer a derived label directory or future derived dataset root, for example `datasets/rice_uav_ms_blb_cleaned408_v2/`, only after correction rules are approved.
- For overlap duplicates: keep the most representative main bbox, remove highly duplicated boxes, and visually inspect cases where automatic IoU does not catch manual duplicate judgments.
- For fragmented patches: decide whether to merge nearby fragments into a stable region or keep separate boxes only when lesions are visually separable.
- For multispectral noise texture: do not treat pseudo-color intensity alone as BLB; route uncertain samples to second review.
- ACCEPT samples can seed clean references but are not training release approval in this round.

## Current Target Counts

- accepted_clean_seed_candidates: `{accepted}`
- targeted_fix_items: `{needs_fix}`
- targeted_review_items: `{needs_review}`
- rejected_items: `{rejected}`
- overlap_duplicate_analysis_rows: `{len(overlap_rows)}`

## Outputs

- `reports/uav_blb_408_cleaned408_v2_overlap_duplicate_analysis.csv`
- `reports/uav_blb_408_cleaned408_v2_targeted_fix_list.csv`
- `reports/uav_blb_408_cleaned408_v2_targeted_review_plan.md`
- `metadata/uav_blb_cleaned408_v2_status.yaml`

## Next Execution Route

1. Review the targeted fix CSV and prioritize `OVERLAP_DUPLICATE_BBOX`.
2. Define label correction rules for duplicate removal and fragmented patch handling.
3. Create a derived cleaned label workspace only after rules are approved.
4. Perform targeted second review on needs_review samples.
5. Re-run a second manual gate before any training planning resumes.

Training remains forbidden in this planning stage.
""",
    )

    atomic_write_text(
        REVIEW_PLAN_MD,
        f"""# UAV BLB 408 cleaned408_v2 Targeted Review Plan

## Needs Fix Strategy

- needs_fix_items: `{needs_fix}`
- Primary focus: `OVERLAP_DUPLICATE_BBOX`.
- For duplicate/overlap cases, inspect bbox pairs in `uav_blb_408_cleaned408_v2_overlap_duplicate_analysis.csv`.
- Suggested actions:
  - `remove_duplicate_bbox`: remove redundant boxes around the same suspected lesion/canopy region.
  - `merge_fragmented_bbox`: merge nearby fragments only when they form one stable suspected BLB region.
  - `adjust_misaligned_bbox`: shrink or move overly large/misaligned boxes.
  - `add_missing_bbox`: add missing regions only after visual confirmation.
  - `second_review_required`: do not auto-fix ambiguous cases.

## Needs Review Strategy

- needs_review_items: `{needs_review}`
- Review `FRAGMENTED_PATCH`, `EDGE_CUT_OR_BLUR`, and legacy `unclear` samples separately.
- Do not auto-pass these samples.
- Require a second reviewer decision before including them in cleaned408_v2.

## Overlap Duplicate Strategy

- overlap_duplicate_manual_or_iou_rows: `{len(overlap_rows)}`
- Automatic IoU uses threshold `0.50`.
- If manual review marked duplicate but IoU does not exceed threshold, inspect visually because duplicate boxes may be adjacent, nested, or semantically redundant rather than strictly high-IoU.

## Second Gate Pass Standard

- All corrected labels must remain single-class `bacterial_leaf_blight`.
- No source images or original labels may be overwritten.
- Targeted second review must complete on corrected hard cases.
- serious_issue_ratio should be `<= 0.10`.
- Duplicate/overlap issue must not remain concentrated in val/test.
- Training is still not allowed until second gate passes.
""",
    )

    atomic_write_text(
        STATUS_YAML,
        """cleaned408_v2_stage: PLANNING
source_manual_review: COMPLETE
source_manual_gate: FAIL
training_allowed: false
original_images_modified: false
original_labels_modified: false
weights_modified: false
backend_modified: false
env_modified: false
derived_dataset_created: false
next_allowed_stage: TARGETED_LABEL_CORRECTION_OR_SECOND_REVIEW
notes:
  - manual issue types are review metadata only, not YOLO classes
  - current YOLO class remains bacterial_leaf_blight
  - do not train until cleaned408_v2 second gate passes
""",
    )

    print(
        json.dumps(
            {
                "accepted": accepted,
                "needs_fix": needs_fix,
                "needs_review": needs_review,
                "rejected": rejected,
                "overlap_rows": len(overlap_rows),
                "training_allowed": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
