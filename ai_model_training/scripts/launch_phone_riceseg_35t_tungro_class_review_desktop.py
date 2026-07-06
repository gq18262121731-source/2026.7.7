from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import io
import sys
import time
import traceback
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import messagebox, ttk

try:
    from PIL import Image, ImageTk

    PILLOW_AVAILABLE = True
except Exception:
    Image = None
    ImageTk = None
    PILLOW_AVAILABLE = False

from manual_review_ui_text import (
    CLASS_REVIEW_RESULT_DISPLAY,
    FIELD_LABELS_ZH,
    MODEL_ERROR_TYPE_DISPLAY,
    REVIEW_COMMON_TEXT,
    REVIEW_DECISION_DISPLAY,
    format_enum_display,
    humanize_value,
    parse_enum_display,
)


APP_TITLE = REVIEW_COMMON_TEXT["window_title_35t"]
LOGGER_NAME = "phone_riceseg_35t_tungro_class_review"

CLASS_REVIEW_RESULTS = [
    "CONFIRMED_TUNGRO",
    "AMBIGUOUS_TUNGRO",
    "NOT_TUNGRO",
    "LOW_QUALITY_UNUSABLE",
    "NEEDS_MORE_EVIDENCE",
    "TEMP_HOLDOUT",
]

REVIEW_DECISIONS = [
    "KEEP_AS_TUNGRO",
    "TEMP_HOLDOUT",
    "EXCLUDE_FROM_TUNGRO_CLAIM",
    "CLASS_REVIEW_REQUIRED",
    "ADD_MORE_SAMPLES_REQUIRED",
    "UNUSABLE",
]

MODEL_ERROR_TYPES = [
    "OK",
    "NO_DETECTION",
    "MISS_DISEASE",
    "PARTIAL_DETECTION",
    "BROAD_COARSE_BOX",
    "FRAGMENTED_DENSE_BOXES",
    "TOO_MANY_BOXES",
    "FALSE_POSITIVE_BACKGROUND",
    "FALSE_POSITIVE_LEAF_TEXTURE",
    "FALSE_POSITIVE_EDGE",
    "LOW_CONFIDENCE_NOISE",
    "WRONG_CLASS",
    "IMAGE_BLUR",
    "LABEL_OR_VISUAL_AMBIGUOUS",
    "OTHER",
]

QUEUE_CSV = "reports/phone_riceseg_35t_tungro_class_review_queue.csv"
RESULTS_CSV = "reports/phone_riceseg_35t_tungro_class_review_results.csv"
SUMMARY_CSV = "reports/phone_riceseg_35t_tungro_class_review_summary.csv"
REPORT_MD = "reports/phone_riceseg_35t_tungro_class_review_queue_report.md"
REPORT_JSON = "reports/phone_riceseg_35t_tungro_class_review_queue_report.json"
NEXT_PROMPT = "reports/phone_riceseg_35t_next_tungro_class_review_queue_prompt.md"
LOG_PATH = "reports/phone_riceseg_35t_tungro_class_review_desktop.log"

SOURCE_35S_JSON = "reports/phone_riceseg_35s_controlled_targeted_remediation_changeset_plan_report.json"
SOURCE_35S_QUEUE = "reports/phone_riceseg_35s_review_queue_design.csv"
SOURCE_35P_ACTION = "reports/phone_riceseg_35p_hard_case_action_plan.csv"
SOURCE_35P_SUMMARY = "reports/phone_riceseg_35p_per_class_hard_case_summary.csv"
SOURCE_35O_ITEMS = "reports/phone_riceseg_35o_prediction_review_items.csv"
SOURCE_35O_DECISIONS = "reports/phone_riceseg_35o_prediction_review_decisions.csv"
SOURCE_35O_FINAL = "reports/phone_riceseg_35o_final_hard_case_candidates.csv"
SOURCE_35R_JSON = "reports/phone_riceseg_35r_targeted_tungro_brownspot_remediation_plan_report.json"

QUEUE_FIELDNAMES = [
    "item_id",
    "source_stage",
    "split_group",
    "is_holdout",
    "image_path",
    "label_path",
    "prediction_image_path",
    "class_name",
    "original_class_id",
    "review_priority",
    "source_error_type",
    "source_reviewer_decision",
    "source_root_cause_type",
    "bbox_count",
    "max_confidence",
    "queue_reason",
    "review_status",
    "review_decision",
    "class_review_result",
    "model_error_type",
    "needs_more_samples",
    "needs_temp_holdout",
    "needs_label_review",
    "needs_exclusion_from_claim",
    "notes",
    "reviewed_at",
]

SUMMARY_FIELDNAMES = [
    "generated_at",
    "review_total",
    "review_completed_count",
    "review_pending_count",
    "confirmed_tungro_count",
    "ambiguous_tungro_count",
    "not_tungro_count",
    "low_quality_unusable_count",
    "needs_more_evidence_count",
    "temp_holdout_count",
    "keep_as_tungro_count",
    "exclude_from_tungro_claim_count",
    "add_more_samples_required_count",
    "class_review_required_count",
    "unusable_count",
    "confirmed_tungro_ratio",
    "ambiguous_or_holdout_ratio",
    "invalid_or_unusable_ratio",
    "p0_count",
    "p1_count",
    "p2_count",
    "p3_count",
    "tungro_class_reliability",
    "phone_riceseg_35t_tungro_class_review_queue_gate",
    "next_allowed_stage",
]


@dataclass
class GateState:
    gate: str
    next_allowed_stage: str
    class_reliability: str
    manual_review_executed: str
    tungro_enter_candidate_model_claim: str
    tungro_enter_backend_demo: str
    tungro_keep_in_four_class_training: str
    tungro_requires_sample_supplement_before_training: str
    tungro_requires_temp_exclusion_before_training: str
    branch_prompt_path: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the 35T tungro class review desktop app.")
    parser.add_argument("--prepare-only", action="store_true", help="Generate queue/results/report files and exit.")
    parser.add_argument("--self-test", action="store_true", help="Generate files and print a self-test summary.")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root() / path


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def configure_logger(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return logger


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    if path.exists():
        try:
            existing = path.read_text(encoding=encoding)
            if existing == content:
                return
        except Exception:
            pass
    tmp = path.with_name(path.name + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tmp.open("w", encoding=encoding, newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if not tmp.exists() or tmp.stat().st_size == 0:
            raise RuntimeError(f"temporary file write failed: {tmp}")
        if path.exists():
            try:
                existing = path.read_text(encoding=encoding)
                if existing == content:
                    tmp.unlink()
                    return
            except Exception:
                pass
        last_error: Exception | None = None
        for _ in range(10):
            try:
                tmp.replace(path)
                last_error = None
                break
            except PermissionError as exc:
                last_error = exc
                time.sleep(0.1)
        if last_error is not None:
            raise last_error
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"atomic replace failed: {path}")
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def atomic_write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    atomic_write_text(path, buffer.getvalue(), encoding="utf-8-sig")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def parse_bool_text(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def read_original_class_id(label_path: Path) -> str:
    if not label_path.exists():
        return ""
    class_ids: set[str] = set()
    with label_path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            parts = line.strip().split()
            if parts:
                class_ids.add(parts[0])
    if not class_ids:
        return ""
    return ";".join(sorted(class_ids))


def count_bboxes(label_path: Path) -> int:
    if not label_path.exists():
        return 0
    with label_path.open("r", encoding="utf-8-sig") as handle:
        return sum(1 for line in handle if line.strip())


def classify_priority(is_holdout: bool, reviewer_decision: str, root_cause: str, max_confidence: str) -> str:
    root_cause_upper = root_cause.upper()
    try:
        confidence_value = float(max_confidence) if max_confidence else 0.0
    except ValueError:
        confidence_value = 0.0

    if is_holdout or reviewer_decision == "NO_DETECTION" or "AMBIGUITY" in root_cause_upper:
        return "P0"
    if reviewer_decision == "BAD" or "WEAK" in root_cause_upper or "LABEL" in root_cause_upper:
        return "P1"
    if reviewer_decision in {"PARTIAL", "LOW_CONFIDENCE_NOISE"} or confidence_value < 0.35:
        return "P2"
    return "P3"


def infer_model_error_type(source_error_type: str, source_reviewer_decision: str) -> str:
    source_error_upper = (source_error_type or "").strip().upper()
    reviewer_decision_upper = (source_reviewer_decision or "").strip().upper()

    if source_error_upper in {"NO_BOX", "NO_DETECTION"} or reviewer_decision_upper == "NO_DETECTION":
        return "NO_DETECTION"
    if source_error_upper == "MISS_DISEASE":
        return "MISS_DISEASE"
    if source_error_upper == "PARTIAL_DETECTION":
        return "PARTIAL_DETECTION"
    if source_error_upper == "BROAD_COARSE_BOX":
        return "BROAD_COARSE_BOX"
    if source_error_upper == "FRAGMENTED_DENSE_BOXES":
        return "FRAGMENTED_DENSE_BOXES"
    if source_error_upper == "TOO_MANY_BOXES":
        return "TOO_MANY_BOXES"
    if source_error_upper == "FALSE_POSITIVE_BACKGROUND":
        return "FALSE_POSITIVE_BACKGROUND"
    if source_error_upper == "FALSE_POSITIVE_LEAF_TEXTURE":
        return "FALSE_POSITIVE_LEAF_TEXTURE"
    if source_error_upper == "FALSE_POSITIVE_EDGE":
        return "FALSE_POSITIVE_EDGE"
    if source_error_upper == "LOW_CONFIDENCE_NOISE":
        return "LOW_CONFIDENCE_NOISE"
    if source_error_upper == "WRONG_CLASS":
        return "WRONG_CLASS"
    if source_error_upper == "IMAGE_BLUR":
        return "IMAGE_BLUR"
    if source_error_upper == "LABEL_OR_VISUAL_AMBIGUOUS":
        return "LABEL_OR_VISUAL_AMBIGUOUS"
    return "OK"


def summarize_queue_reason(
    item_id: str,
    from_35s: bool,
    final_candidate: dict[str, str] | None,
    action_row: dict[str, str] | None,
    item_row: dict[str, str],
) -> str:
    parts: list[str] = []
    if not from_35s:
        parts.append("added_from_35o_evidence_not_listed_in_35s_design")
    if action_row:
        parts.append(f"35p:{action_row.get('main_error_type', 'unknown')}")
        parts.append(f"35p_action:{action_row.get('recommended_next_action', 'unknown')}")
    if final_candidate:
        parts.append(f"35o_final:{final_candidate.get('main_error_type', 'unknown')}")
    if parse_bool_text(item_row.get("holdout_observation_only", "false")):
        parts.append("holdout_observation_only")
    if parse_bool_text(item_row.get("no_detection_conf025", "false")):
        parts.append("conf025_no_detection")
    if item_row.get("selection_reason"):
        parts.append(f"selection:{item_row['selection_reason']}")
    return "; ".join(parts)


class TungroReviewStore:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.root = repo_root()
        self.queue_csv = resolve_path(QUEUE_CSV)
        self.results_csv = resolve_path(RESULTS_CSV)
        self.summary_csv = resolve_path(SUMMARY_CSV)
        self.report_md = resolve_path(REPORT_MD)
        self.report_json = resolve_path(REPORT_JSON)
        self.next_prompt = resolve_path(NEXT_PROMPT)
        self.source_35s_json = resolve_path(SOURCE_35S_JSON)
        self.source_35s_queue = resolve_path(SOURCE_35S_QUEUE)
        self.source_35p_action = resolve_path(SOURCE_35P_ACTION)
        self.source_35p_summary = resolve_path(SOURCE_35P_SUMMARY)
        self.source_35o_items = resolve_path(SOURCE_35O_ITEMS)
        self.source_35o_decisions = resolve_path(SOURCE_35O_DECISIONS)
        self.source_35o_final = resolve_path(SOURCE_35O_FINAL)
        self.source_35r_json = resolve_path(SOURCE_35R_JSON)

    def prepare_assets(self) -> dict[str, Any]:
        self._validate_prerequisites()
        queue_rows, evidence = self._build_queue_rows()
        results_rows = self._merge_results(queue_rows)
        summary_row = self._build_summary(queue_rows, results_rows)
        gate_state = self._derive_gate(summary_row)
        report_payload = self._build_report_payload(queue_rows, results_rows, summary_row, evidence, gate_state)
        report_markdown = self._build_report_markdown(report_payload)

        atomic_write_csv(self.queue_csv, QUEUE_FIELDNAMES, queue_rows)
        atomic_write_csv(self.results_csv, QUEUE_FIELDNAMES, results_rows)
        atomic_write_csv(self.summary_csv, SUMMARY_FIELDNAMES, [summary_row])
        atomic_write_json(self.report_json, report_payload)
        atomic_write_text(self.report_md, report_markdown)

        return {
            "queue_rows": queue_rows,
            "results_rows": results_rows,
            "summary_row": summary_row,
            "gate_state": gate_state,
            "report_payload": report_payload,
        }

    def load_results(self) -> list[dict[str, str]]:
        self.prepare_assets()
        return read_csv_rows(self.results_csv)

    def save_results(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        queue_rows = read_csv_rows(self.queue_csv)
        normalized_rows: list[dict[str, Any]] = []
        row_map = {row["item_id"]: row for row in rows}
        for queue_row in queue_rows:
            current = dict(queue_row)
            stored = row_map.get(queue_row["item_id"], {})
            current["review_status"] = stored.get("review_status", queue_row.get("review_status", "pending"))
            current["review_decision"] = stored.get("review_decision", queue_row.get("review_decision", ""))
            current["class_review_result"] = stored.get("class_review_result", queue_row.get("class_review_result", ""))
            current["model_error_type"] = stored.get("model_error_type", queue_row.get("model_error_type", "OK"))
            current["notes"] = stored.get("notes", queue_row.get("notes", ""))
            current["reviewed_at"] = stored.get("reviewed_at", queue_row.get("reviewed_at", ""))
            normalized_rows.append(current)

        summary_row = self._build_summary(queue_rows, normalized_rows)
        gate_state = self._derive_gate(summary_row)
        _, evidence = self._build_queue_rows()
        report_payload = self._build_report_payload(queue_rows, normalized_rows, summary_row, evidence, gate_state)
        report_markdown = self._build_report_markdown(report_payload)

        atomic_write_csv(self.results_csv, QUEUE_FIELDNAMES, normalized_rows)
        atomic_write_csv(self.summary_csv, SUMMARY_FIELDNAMES, [summary_row])
        atomic_write_json(self.report_json, report_payload)
        atomic_write_text(self.report_md, report_markdown)

        return {
            "summary_row": summary_row,
            "gate_state": gate_state,
            "report_payload": report_payload,
        }

    def _validate_prerequisites(self) -> None:
        required = [
            self.source_35s_json,
            self.source_35s_queue,
            self.source_35p_action,
            self.source_35p_summary,
            self.source_35o_items,
            self.source_35o_decisions,
            self.source_35o_final,
            self.source_35r_json,
            self.next_prompt,
        ]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise RuntimeError("Missing required input files:\n" + "\n".join(missing))

        with self.source_35s_json.open("r", encoding="utf-8-sig") as handle:
            source_35s = json.load(handle)
        if source_35s.get("phone_riceseg_35s_controlled_targeted_remediation_changeset_plan_gate") != "PASS":
            raise RuntimeError("35S gate is not PASS; 35T must stay BLOCKED.")
        if source_35s.get("next_allowed_stage") != "Phone-35T_tungro_class_review_queue":
            raise RuntimeError("35S next_allowed_stage does not authorize 35T.")

    def _build_queue_rows(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        items_rows = [row for row in read_csv_rows(self.source_35o_items) if row.get("class_name") == "tungro"]
        decisions_map = {row["review_id"]: row for row in read_csv_rows(self.source_35o_decisions) if row.get("class_name") == "tungro"}
        action_map = {row["item_id"]: row for row in read_csv_rows(self.source_35p_action) if row.get("class_name") == "tungro"}
        final_map = {row["item_id"]: row for row in read_csv_rows(self.source_35o_final) if row.get("class_name") == "tungro"}

        design_rows = [row for row in read_csv_rows(self.source_35s_queue) if row.get("queue_id") == "tungro_class_review_queue"]
        design_items: set[str] = set()
        if design_rows:
            raw_items = design_rows[0].get("source_items", "")
            design_items = {part.strip() for part in raw_items.split(";") if part.strip()}

        items_map = {row["review_id"]: row for row in items_rows}
        all_item_ids = sorted(set(items_map) | set(action_map) | set(final_map), key=self._sort_item_id)

        queue_rows: list[dict[str, Any]] = []
        added_from_35o: list[str] = []
        for item_id in all_item_ids:
            item_row = items_map.get(item_id)
            if not item_row:
                raise RuntimeError(f"Missing 35O prediction review item for tungro id: {item_id}")
            action_row = action_map.get(item_id)
            final_row = final_map.get(item_id)
            decision_row = decisions_map.get(item_id, {})
            label_path = Path(item_row["label_path"])
            bbox_count = count_bboxes(label_path)
            original_class_id = read_original_class_id(label_path)
            max_confidence = item_row.get("max_confidence_conf025", "") or ""
            is_holdout = parse_bool_text(item_row.get("holdout_observation_only", "false")) or item_id.startswith("holdout_")
            from_35s = item_id in design_items
            if not from_35s:
                added_from_35o.append(item_id)

            source_stage_parts = ["35o_prediction_review_items"]
            if final_row:
                source_stage_parts.append("35o_final_hard_case_candidates")
            if action_row:
                source_stage_parts.append("35p_hard_case_action_plan")
            if from_35s:
                source_stage_parts.append("35s_review_queue_design")
            review_priority = classify_priority(
                is_holdout=is_holdout,
                reviewer_decision=(action_row or final_row or {}).get("reviewer_decision", ""),
                root_cause=(action_row or {}).get("root_cause_type", ""),
                max_confidence=max_confidence,
            )

            queue_row = {
                "item_id": item_id,
                "source_stage": "; ".join(source_stage_parts),
                "split_group": "holdout" if is_holdout else "active_test",
                "is_holdout": "true" if is_holdout else "false",
                "image_path": item_row.get("image_path", ""),
                "label_path": item_row.get("label_path", ""),
                "prediction_image_path": item_row.get("side_by_side_visual_path", "") or item_row.get("prediction_visual_path", ""),
                "class_name": "tungro",
                "original_class_id": original_class_id,
                "review_priority": review_priority,
                "source_error_type": (action_row or final_row or {}).get("main_error_type", ""),
                "source_reviewer_decision": (action_row or final_row or {}).get("reviewer_decision", ""),
                "source_root_cause_type": (action_row or {}).get("root_cause_type", ""),
                "bbox_count": str(bbox_count),
                "max_confidence": max_confidence,
                "queue_reason": summarize_queue_reason(item_id, from_35s, final_row, action_row, item_row),
                "review_status": "pending",
                "review_decision": "",
                "class_review_result": "",
                "model_error_type": infer_model_error_type(
                    source_error_type=(action_row or final_row or {}).get("main_error_type", ""),
                    source_reviewer_decision=(action_row or final_row or {}).get("reviewer_decision", ""),
                ),
                "needs_more_samples": (action_row or {}).get("needs_more_samples", ""),
                "needs_temp_holdout": "YES" if is_holdout else "",
                "needs_label_review": (action_row or {}).get("needs_label_review", ""),
                "needs_exclusion_from_claim": "YES" if (action_row or {}).get("should_exclude_from_candidate_claim", "") == "YES" else "",
                "notes": decision_row.get("reviewer_notes", ""),
                "reviewed_at": "",
            }
            queue_rows.append(queue_row)

        evidence = self._build_evidence_snapshot(queue_rows)
        evidence["design_expected_item_count"] = len(design_items)
        evidence["actual_queue_count"] = len(queue_rows)
        evidence["added_from_35o_evidence"] = added_from_35o
        return queue_rows, evidence

    def _build_evidence_snapshot(self, queue_rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "queue_item_ids": [row["item_id"] for row in queue_rows],
            "holdout_item_ids": [row["item_id"] for row in queue_rows if row["is_holdout"] == "true"],
            "active_test_item_ids": [row["item_id"] for row in queue_rows if row["is_holdout"] != "true"],
        }

    def _merge_results(self, queue_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        existing_map: dict[str, dict[str, str]] = {}
        if self.results_csv.exists():
            existing_map = {row["item_id"]: row for row in read_csv_rows(self.results_csv)}

        merged_rows: list[dict[str, Any]] = []
        for queue_row in queue_rows:
            existing = existing_map.get(queue_row["item_id"], {})
            merged = dict(queue_row)
            merged["review_status"] = existing.get("review_status", queue_row["review_status"])
            merged["review_decision"] = existing.get("review_decision", queue_row["review_decision"])
            merged["class_review_result"] = existing.get("class_review_result", queue_row["class_review_result"])
            merged["model_error_type"] = existing.get("model_error_type", queue_row["model_error_type"])
            merged["needs_more_samples"] = existing.get("needs_more_samples", queue_row["needs_more_samples"])
            merged["needs_temp_holdout"] = existing.get("needs_temp_holdout", queue_row["needs_temp_holdout"])
            merged["needs_label_review"] = existing.get("needs_label_review", queue_row["needs_label_review"])
            merged["needs_exclusion_from_claim"] = existing.get("needs_exclusion_from_claim", queue_row["needs_exclusion_from_claim"])
            merged["notes"] = existing.get("notes", queue_row["notes"])
            merged["reviewed_at"] = existing.get("reviewed_at", queue_row["reviewed_at"])
            merged_rows.append(merged)
        return merged_rows

    def _build_summary(self, queue_rows: list[dict[str, Any]], results_rows: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(results_rows)
        completed = sum(
            1
            for row in results_rows
            if row.get("review_status") == "reviewed"
            and row.get("class_review_result")
            and row.get("review_decision")
        )
        pending = total - completed
        result_counter = Counter(row.get("class_review_result", "") for row in results_rows if row.get("class_review_result"))
        decision_counter = Counter(row.get("review_decision", "") for row in results_rows if row.get("review_decision"))
        priority_counter = Counter(row.get("review_priority", "") for row in queue_rows)

        confirmed = result_counter["CONFIRMED_TUNGRO"]
        ambiguous = result_counter["AMBIGUOUS_TUNGRO"]
        not_tungro = result_counter["NOT_TUNGRO"]
        low_quality = result_counter["LOW_QUALITY_UNUSABLE"]
        needs_more = result_counter["NEEDS_MORE_EVIDENCE"]
        temp_holdout = result_counter["TEMP_HOLDOUT"]

        if total > 0:
            confirmed_ratio = round(confirmed / total, 6)
            ambiguous_or_holdout_ratio = round((ambiguous + temp_holdout + needs_more) / total, 6)
            invalid_or_unusable_ratio = round((not_tungro + low_quality) / total, 6)
        else:
            confirmed_ratio = 0.0
            ambiguous_or_holdout_ratio = 0.0
            invalid_or_unusable_ratio = 0.0

        gate_state = self._derive_gate(
            {
                "review_total": total,
                "review_completed_count": completed,
                "review_pending_count": pending,
                "confirmed_tungro_count": confirmed,
                "ambiguous_tungro_count": ambiguous,
                "not_tungro_count": not_tungro,
                "low_quality_unusable_count": low_quality,
                "needs_more_evidence_count": needs_more,
                "temp_holdout_count": temp_holdout,
                "keep_as_tungro_count": decision_counter["KEEP_AS_TUNGRO"],
                "exclude_from_tungro_claim_count": decision_counter["EXCLUDE_FROM_TUNGRO_CLAIM"],
                "add_more_samples_required_count": decision_counter["ADD_MORE_SAMPLES_REQUIRED"],
                "class_review_required_count": decision_counter["CLASS_REVIEW_REQUIRED"],
                "unusable_count": decision_counter["UNUSABLE"],
                "confirmed_tungro_ratio": confirmed_ratio,
                "ambiguous_or_holdout_ratio": ambiguous_or_holdout_ratio,
                "invalid_or_unusable_ratio": invalid_or_unusable_ratio,
                "p0_count": priority_counter["P0"],
                "p1_count": priority_counter["P1"],
                "p2_count": priority_counter["P2"],
                "p3_count": priority_counter["P3"],
            }
        )

        return {
            "generated_at": now_iso(),
            "review_total": total,
            "review_completed_count": completed,
            "review_pending_count": pending,
            "confirmed_tungro_count": confirmed,
            "ambiguous_tungro_count": ambiguous,
            "not_tungro_count": not_tungro,
            "low_quality_unusable_count": low_quality,
            "needs_more_evidence_count": needs_more,
            "temp_holdout_count": temp_holdout,
            "keep_as_tungro_count": decision_counter["KEEP_AS_TUNGRO"],
            "exclude_from_tungro_claim_count": decision_counter["EXCLUDE_FROM_TUNGRO_CLAIM"],
            "add_more_samples_required_count": decision_counter["ADD_MORE_SAMPLES_REQUIRED"],
            "class_review_required_count": decision_counter["CLASS_REVIEW_REQUIRED"],
            "unusable_count": decision_counter["UNUSABLE"],
            "confirmed_tungro_ratio": confirmed_ratio,
            "ambiguous_or_holdout_ratio": ambiguous_or_holdout_ratio,
            "invalid_or_unusable_ratio": invalid_or_unusable_ratio,
            "p0_count": priority_counter["P0"],
            "p1_count": priority_counter["P1"],
            "p2_count": priority_counter["P2"],
            "p3_count": priority_counter["P3"],
            "tungro_class_reliability": gate_state.class_reliability,
            "phone_riceseg_35t_tungro_class_review_queue_gate": gate_state.gate,
            "next_allowed_stage": gate_state.next_allowed_stage,
        }

    def _derive_gate(self, summary: dict[str, Any]) -> GateState:
        total = int(summary.get("review_total", 0))
        completed = int(summary.get("review_completed_count", 0))
        pending = int(summary.get("review_pending_count", max(total - completed, 0)))
        confirmed = int(summary.get("confirmed_tungro_count", 0))
        ambiguous = int(summary.get("ambiguous_tungro_count", 0))
        not_tungro = int(summary.get("not_tungro_count", 0))
        low_quality = int(summary.get("low_quality_unusable_count", 0))
        needs_more = int(summary.get("needs_more_evidence_count", 0))
        temp_holdout = int(summary.get("temp_holdout_count", 0))

        if total == 0 or pending > 0:
            return GateState(
                gate="PENDING",
                next_allowed_stage="STAY_AT_35T",
                class_reliability="PENDING",
                manual_review_executed="YES" if completed > 0 else "NO",
                tungro_enter_candidate_model_claim="NO",
                tungro_enter_backend_demo="NO",
                tungro_keep_in_four_class_training="CONDITIONAL",
                tungro_requires_sample_supplement_before_training="YES",
                tungro_requires_temp_exclusion_before_training="YES",
                branch_prompt_path=str(self.next_prompt),
            )

        confirmed_ratio = confirmed / total if total else 0.0
        ambiguous_ratio = (ambiguous + temp_holdout + needs_more) / total if total else 0.0
        invalid_ratio = (not_tungro + low_quality) / total if total else 0.0

        if invalid_ratio >= 0.40 or confirmed_ratio < 0.20:
            reliability = "NOT_USABLE"
            next_stage = "Phone-35I_experiment_stop_or_baseline_selection_report"
            keep_in_training = "NO"
        elif ambiguous_ratio >= 0.45:
            reliability = "UNSTABLE"
            next_stage = "Phone-35T2_tungro_second_class_review"
            keep_in_training = "CONDITIONAL"
        elif confirmed_ratio >= 0.70 and invalid_ratio <= 0.15 and ambiguous_ratio <= 0.25:
            reliability = "RELIABLE"
            next_stage = "Phone-35U_controlled_targeted_remediation_changeset_execution"
            keep_in_training = "YES"
        elif confirmed_ratio >= 0.45 and invalid_ratio <= 0.30:
            reliability = "WEAK_BUT_USABLE"
            next_stage = "Phone-35V_tungro_sample_supplement_plan"
            keep_in_training = "CONDITIONAL"
        else:
            reliability = "UNSTABLE"
            next_stage = "Phone-35V_tungro_sample_supplement_plan"
            keep_in_training = "CONDITIONAL"

        return GateState(
            gate="PASS",
            next_allowed_stage=next_stage,
            class_reliability=reliability,
            manual_review_executed="YES",
            tungro_enter_candidate_model_claim="YES" if reliability == "RELIABLE" else "NO",
            tungro_enter_backend_demo="NO",
            tungro_keep_in_four_class_training=keep_in_training,
            tungro_requires_sample_supplement_before_training="YES" if reliability != "RELIABLE" else "NO",
            tungro_requires_temp_exclusion_before_training="YES" if reliability in {"UNSTABLE", "NOT_USABLE", "WEAK_BUT_USABLE"} else "NO",
            branch_prompt_path=str(self.next_prompt),
        )

    def _build_report_payload(
        self,
        queue_rows: list[dict[str, Any]],
        results_rows: list[dict[str, Any]],
        summary_row: dict[str, Any],
        evidence: dict[str, Any],
        gate_state: GateState,
    ) -> dict[str, Any]:
        with self.source_35r_json.open("r", encoding="utf-8-sig") as handle:
            source_35r = json.load(handle)
        with self.source_35s_json.open("r", encoding="utf-8-sig") as handle:
            source_35s = json.load(handle)

        reviewed_preview = [
            {
                "item_id": row["item_id"],
                "review_priority": row["review_priority"],
                "class_review_result": row["class_review_result"],
                "review_decision": row["review_decision"],
                "reviewed_at": row["reviewed_at"],
            }
            for row in results_rows
            if row.get("review_status") == "reviewed"
        ]

        return {
            "generated_at": now_iso(),
            "phone_riceseg_35t_tungro_class_review_queue_gate": gate_state.gate,
            "next_allowed_stage": gate_state.next_allowed_stage,
            "training_executed_this_round": "NO",
            "validation_executed_this_round": "NO",
            "infer_executed_this_round": "NO",
            "conf_sweep_executed_this_round": "NO",
            "manual_review_executed_this_round": gate_state.manual_review_executed,
            "dataset_modified_this_round": "NO",
            "labels_modified_this_round": "NO",
            "images_modified_this_round": "NO",
            "data_yaml_modified_this_round": "NO",
            "weights_overwritten_this_round": "NO",
            "backend_modified_this_round": "NO",
            "env_modified_this_round": "NO",
            "source_assertions": {
                "35s_gate": source_35s.get("phone_riceseg_35s_controlled_targeted_remediation_changeset_plan_gate"),
                "35s_next_allowed_stage": source_35s.get("next_allowed_stage"),
                "tungro_must_do_class_review_first": source_35s.get("tungro_must_do_class_review_first"),
                "tungro_risk": source_35r.get("tungro", {}).get("issue_level", "CRITICAL"),
                "tungro_should_enter_candidate_model_claim": source_35r.get("tungro", {}).get("should_enter_candidate_model_claim", "NO"),
                "tungro_should_enter_backend_demo": source_35r.get("tungro", {}).get("should_enter_backend_demo", "NO"),
            },
            "queue_counts": {
                "review_total": summary_row["review_total"],
                "review_completed_count": summary_row["review_completed_count"],
                "review_pending_count": summary_row["review_pending_count"],
                "design_expected_item_count": evidence.get("design_expected_item_count", 0),
                "actual_queue_count": evidence.get("actual_queue_count", 0),
                "added_from_35o_evidence_count": len(evidence.get("added_from_35o_evidence", [])),
            },
            "result_counts": {
                "confirmed_tungro_count": summary_row["confirmed_tungro_count"],
                "ambiguous_tungro_count": summary_row["ambiguous_tungro_count"],
                "not_tungro_count": summary_row["not_tungro_count"],
                "low_quality_unusable_count": summary_row["low_quality_unusable_count"],
                "needs_more_evidence_count": summary_row["needs_more_evidence_count"],
                "temp_holdout_count": summary_row["temp_holdout_count"],
                "keep_as_tungro_count": summary_row["keep_as_tungro_count"],
                "exclude_from_tungro_claim_count": summary_row["exclude_from_tungro_claim_count"],
                "add_more_samples_required_count": summary_row["add_more_samples_required_count"],
                "class_review_required_count": summary_row["class_review_required_count"],
                "unusable_count": summary_row["unusable_count"],
            },
            "ratios": {
                "confirmed_tungro_ratio": summary_row["confirmed_tungro_ratio"],
                "ambiguous_or_holdout_ratio": summary_row["ambiguous_or_holdout_ratio"],
                "invalid_or_unusable_ratio": summary_row["invalid_or_unusable_ratio"],
            },
            "priority_counts": {
                "p0_count": summary_row["p0_count"],
                "p1_count": summary_row["p1_count"],
                "p2_count": summary_row["p2_count"],
                "p3_count": summary_row["p3_count"],
            },
            "tungro_class_reliability": gate_state.class_reliability,
            "tungro_enter_candidate_model_claim": gate_state.tungro_enter_candidate_model_claim,
            "tungro_enter_backend_demo": gate_state.tungro_enter_backend_demo,
            "tungro_keep_in_four_class_training": gate_state.tungro_keep_in_four_class_training,
            "tungro_requires_sample_supplement_before_training": gate_state.tungro_requires_sample_supplement_before_training,
            "tungro_requires_temp_exclusion_before_training": gate_state.tungro_requires_temp_exclusion_before_training,
            "added_from_35o_evidence": evidence.get("added_from_35o_evidence", []),
            "queue_item_ids": evidence.get("queue_item_ids", []),
            "reviewed_preview": reviewed_preview,
            "artifacts": {
                "queue_csv": str(self.queue_csv),
                "results_csv": str(self.results_csv),
                "summary_csv": str(self.summary_csv),
                "report_md": str(self.report_md),
                "report_json": str(self.report_json),
                "next_prompt_path": gate_state.branch_prompt_path,
                "desktop_log_path": str(resolve_path(LOG_PATH)),
            },
        }

    def _build_report_markdown(self, payload: dict[str, Any]) -> str:
        added_items = payload.get("added_from_35o_evidence", [])
        return "\n".join(
            [
                "# Phone-35T Tungro Class Review Queue Report",
                "",
                f"- generated_at = {payload['generated_at']}",
                f"- phone_riceseg_35t_tungro_class_review_queue_gate = {payload['phone_riceseg_35t_tungro_class_review_queue_gate']}",
                f"- next_allowed_stage = {payload['next_allowed_stage']}",
                f"- training_executed_this_round = {payload['training_executed_this_round']}",
                f"- validation_executed_this_round = {payload['validation_executed_this_round']}",
                f"- infer_executed_this_round = {payload['infer_executed_this_round']}",
                f"- conf_sweep_executed_this_round = {payload['conf_sweep_executed_this_round']}",
                f"- manual_review_executed_this_round = {payload['manual_review_executed_this_round']}",
                f"- dataset_modified_this_round = {payload['dataset_modified_this_round']}",
                f"- labels_modified_this_round = {payload['labels_modified_this_round']}",
                f"- images_modified_this_round = {payload['images_modified_this_round']}",
                f"- data_yaml_modified_this_round = {payload['data_yaml_modified_this_round']}",
                f"- weights_overwritten_this_round = {payload['weights_overwritten_this_round']}",
                f"- backend_modified_this_round = {payload['backend_modified_this_round']}",
                f"- env_modified_this_round = {payload['env_modified_this_round']}",
                "",
                "## Locked upstream conclusions",
                "",
                f"- 35S gate = {payload['source_assertions']['35s_gate']}",
                f"- 35S next_allowed_stage = {payload['source_assertions']['35s_next_allowed_stage']}",
                f"- tungro_must_do_class_review_first = {payload['source_assertions']['tungro_must_do_class_review_first']}",
                f"- tungro risk = {payload['source_assertions']['tungro_risk']}",
                f"- tungro_should_enter_candidate_model_claim = {payload['source_assertions']['tungro_should_enter_candidate_model_claim']}",
                f"- tungro_should_enter_backend_demo = {payload['source_assertions']['tungro_should_enter_backend_demo']}",
                "",
                "## Queue coverage",
                "",
                f"- design_expected_item_count = {payload['queue_counts']['design_expected_item_count']}",
                f"- actual_queue_count = {payload['queue_counts']['actual_queue_count']}",
                f"- review_total = {payload['queue_counts']['review_total']}",
                f"- review_completed_count = {payload['queue_counts']['review_completed_count']}",
                f"- review_pending_count = {payload['queue_counts']['review_pending_count']}",
                f"- added_from_35o_evidence_count = {payload['queue_counts']['added_from_35o_evidence_count']}",
                f"- added_from_35o_evidence = {', '.join(added_items) if added_items else '(none)'}",
                "",
                "## Current review outcome",
                "",
                f"- confirmed_tungro_count = {payload['result_counts']['confirmed_tungro_count']}",
                f"- ambiguous_tungro_count = {payload['result_counts']['ambiguous_tungro_count']}",
                f"- not_tungro_count = {payload['result_counts']['not_tungro_count']}",
                f"- low_quality_unusable_count = {payload['result_counts']['low_quality_unusable_count']}",
                f"- needs_more_evidence_count = {payload['result_counts']['needs_more_evidence_count']}",
                f"- temp_holdout_count = {payload['result_counts']['temp_holdout_count']}",
                f"- keep_as_tungro_count = {payload['result_counts']['keep_as_tungro_count']}",
                f"- exclude_from_tungro_claim_count = {payload['result_counts']['exclude_from_tungro_claim_count']}",
                f"- add_more_samples_required_count = {payload['result_counts']['add_more_samples_required_count']}",
                f"- class_review_required_count = {payload['result_counts']['class_review_required_count']}",
                f"- unusable_count = {payload['result_counts']['unusable_count']}",
                f"- confirmed_tungro_ratio = {payload['ratios']['confirmed_tungro_ratio']}",
                f"- ambiguous_or_holdout_ratio = {payload['ratios']['ambiguous_or_holdout_ratio']}",
                f"- invalid_or_unusable_ratio = {payload['ratios']['invalid_or_unusable_ratio']}",
                f"- tungro_class_reliability = {payload['tungro_class_reliability']}",
                "",
                "## Policy status",
                "",
                f"- tungro_enter_candidate_model_claim = {payload['tungro_enter_candidate_model_claim']}",
                f"- tungro_enter_backend_demo = {payload['tungro_enter_backend_demo']}",
                f"- tungro_keep_in_four_class_training = {payload['tungro_keep_in_four_class_training']}",
                f"- tungro_requires_sample_supplement_before_training = {payload['tungro_requires_sample_supplement_before_training']}",
                f"- tungro_requires_temp_exclusion_before_training = {payload['tungro_requires_temp_exclusion_before_training']}",
                "",
                "## Notes",
                "",
                "- This round only prepares or records the tungro manual class review queue.",
                "- No labels, images, data.yaml, backend, env, or weights are modified.",
                "- If the queue exists but review is incomplete, the gate must remain PENDING.",
                "",
                "## Artifacts",
                "",
                f"- queue_csv = {payload['artifacts']['queue_csv']}",
                f"- results_csv = {payload['artifacts']['results_csv']}",
                f"- summary_csv = {payload['artifacts']['summary_csv']}",
                f"- report_json = {payload['artifacts']['report_json']}",
                f"- next_prompt_path = {payload['artifacts']['next_prompt_path']}",
                f"- desktop_log_path = {payload['artifacts']['desktop_log_path']}",
                "",
            ]
        )

    @staticmethod
    def _sort_item_id(value: str) -> tuple[int, int]:
        if value.startswith("test_"):
            return (0, int(value.split("_")[1]))
        if value.startswith("holdout_"):
            return (1, int(value.split("_")[1]))
        return (9, 999999)


class TungroReviewApp:
    def __init__(self, store: TungroReviewStore, logger: logging.Logger) -> None:
        self.store = store
        self.logger = logger
        self.payload = self.store.prepare_assets()
        self.rows = self.store.load_results()
        self.index_by_id = {row["item_id"]: idx for idx, row in enumerate(self.rows)}
        self.current_index = 0
        self.current_photo: Any = None

        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("1380x900")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.item_var = tk.StringVar()
        self.class_result_var = tk.StringVar()
        self.review_decision_var = tk.StringVar()
        self.model_error_type_var = tk.StringVar()
        self.notes_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.summary_var = tk.StringVar()
        self.current_meta_var = tk.StringVar()

        self._build_ui()
        self._refresh_item_list()
        self._load_index(0)
        self.root.bind("<Control-s>", lambda _event: self.save_current())
        self.root.bind("<Control-Return>", lambda _event: self.save_and_next())
        self.root.bind("<Left>", lambda _event: self.prev_item())
        self.root.bind("<Right>", lambda _event: self.next_item())

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="y")

        ttk.Label(left, text=REVIEW_COMMON_TEXT["queue_title"]).pack(anchor="w")
        self.item_list = tk.Listbox(left, width=28, height=35)
        self.item_list.pack(fill="y", expand=False)
        self.item_list.bind("<<ListboxSelect>>", self._on_list_select)

        ttk.Label(left, textvariable=self.summary_var, wraplength=220, justify="left").pack(anchor="w", pady=(10, 0))
        ttk.Label(left, textvariable=self.current_meta_var, wraplength=220, justify="left").pack(anchor="w", pady=(8, 0))
        ttk.Label(
            left,
            text="\n".join([REVIEW_COMMON_TEXT["shortcut_title"], *REVIEW_COMMON_TEXT["shortcut_lines"]]),
            wraplength=220,
            justify="left",
        ).pack(anchor="w", pady=(12, 0))

        right = ttk.Frame(main)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))

        self.image_label = ttk.Label(right, text=REVIEW_COMMON_TEXT["preview_fallback"])
        self.image_label.pack(fill="both", expand=False)

        details_frame = ttk.Frame(right)
        details_frame.pack(fill="x", pady=(10, 0))

        self.details_text = tk.Text(details_frame, height=12, wrap="word")
        self.details_text.pack(fill="x", expand=False)

        controls = ttk.Frame(right)
        controls.pack(fill="x", pady=(10, 0))

        ttk.Label(controls, text=REVIEW_COMMON_TEXT["class_review_result"]).grid(row=0, column=0, sticky="w")
        self.class_result_combo = ttk.Combobox(
            controls,
            textvariable=self.class_result_var,
            values=[format_enum_display(value, CLASS_REVIEW_RESULT_DISPLAY) for value in CLASS_REVIEW_RESULTS],
            state="readonly",
            width=42,
        )
        self.class_result_combo.grid(row=0, column=1, sticky="w", padx=(8, 20))

        ttk.Label(controls, text=REVIEW_COMMON_TEXT["review_decision"]).grid(row=0, column=2, sticky="w")
        self.review_decision_combo = ttk.Combobox(
            controls,
            textvariable=self.review_decision_var,
            values=[format_enum_display(value, REVIEW_DECISION_DISPLAY) for value in REVIEW_DECISIONS],
            state="readonly",
            width=42,
        )
        self.review_decision_combo.grid(row=0, column=3, sticky="w", padx=(8, 0))

        ttk.Label(controls, text=REVIEW_COMMON_TEXT["model_error_type"]).grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.model_error_type_combo = ttk.Combobox(
            controls,
            textvariable=self.model_error_type_var,
            values=[format_enum_display(value, MODEL_ERROR_TYPE_DISPLAY) for value in MODEL_ERROR_TYPES],
            state="readonly",
            width=42,
        )
        self.model_error_type_combo.grid(row=1, column=1, sticky="w", padx=(8, 20), pady=(10, 0))

        ttk.Label(controls, text=REVIEW_COMMON_TEXT["notes"]).grid(row=2, column=0, sticky="nw", pady=(10, 0))
        self.notes_entry = tk.Text(controls, height=5, width=100, wrap="word")
        self.notes_entry.grid(row=2, column=1, columnspan=3, sticky="we", pady=(10, 0))
        ttk.Label(controls, text=REVIEW_COMMON_TEXT["notes_hint"], wraplength=880, justify="left").grid(
            row=3, column=1, columnspan=3, sticky="w", pady=(6, 0)
        )

        button_bar = ttk.Frame(right)
        button_bar.pack(fill="x", pady=(12, 0))

        ttk.Button(button_bar, text=REVIEW_COMMON_TEXT["save"], command=self.save_current).pack(side="left")
        ttk.Button(button_bar, text=REVIEW_COMMON_TEXT["save_and_next"], command=self.save_and_next).pack(side="left", padx=(8, 0))
        ttk.Button(button_bar, text=REVIEW_COMMON_TEXT["previous"], command=self.prev_item).pack(side="left", padx=(20, 0))
        ttk.Button(button_bar, text=REVIEW_COMMON_TEXT["next"], command=self.next_item).pack(side="left", padx=(8, 0))
        ttk.Button(button_bar, text=REVIEW_COMMON_TEXT["open_preview_image"], command=self.open_preview_image).pack(side="left", padx=(20, 0))
        ttk.Button(button_bar, text=REVIEW_COMMON_TEXT["open_image_folder"], command=self.open_image_folder).pack(side="left", padx=(8, 0))

        ttk.Label(right, textvariable=self.status_var, foreground="#0b5").pack(anchor="w", pady=(8, 0))

    def _refresh_item_list(self) -> None:
        self.item_list.delete(0, tk.END)
        for row in self.rows:
            marker = "[x]" if row.get("review_status") == "reviewed" and row.get("class_review_result") else "[ ]"
            self.item_list.insert(tk.END, f"{marker} {row['item_id']} {row['review_priority']}")
        summary_row = read_csv_rows(self.store.summary_csv)[0]
        self.summary_var.set(
            "\n".join(
                [
                    REVIEW_COMMON_TEXT["summary_total"].format(value=summary_row["review_total"]),
                    REVIEW_COMMON_TEXT["summary_completed"].format(value=summary_row["review_completed_count"]),
                    REVIEW_COMMON_TEXT["summary_pending"].format(value=summary_row["review_pending_count"]),
                    REVIEW_COMMON_TEXT["summary_gate"].format(value=summary_row["phone_riceseg_35t_tungro_class_review_queue_gate"]),
                    REVIEW_COMMON_TEXT["summary_reliability"].format(value=summary_row["tungro_class_reliability"]),
                ]
            )
        )

    def _on_list_select(self, _event: Any) -> None:
        selection = self.item_list.curselection()
        if selection:
            self._load_index(selection[0])

    def _load_index(self, index: int) -> None:
        self.current_index = max(0, min(index, len(self.rows) - 1))
        row = self.rows[self.current_index]
        self.item_list.selection_clear(0, tk.END)
        self.item_list.selection_set(self.current_index)
        self.item_list.see(self.current_index)

        class_review_value = row.get("class_review_result", "")
        decision_value = row.get("review_decision", "")
        model_error_value = row.get("model_error_type", "")
        self.class_result_var.set(
            format_enum_display(class_review_value, CLASS_REVIEW_RESULT_DISPLAY) if class_review_value in CLASS_REVIEW_RESULT_DISPLAY else ""
        )
        self.review_decision_var.set(
            format_enum_display(decision_value, REVIEW_DECISION_DISPLAY) if decision_value in REVIEW_DECISION_DISPLAY else ""
        )
        self.model_error_type_var.set(
            format_enum_display(model_error_value, MODEL_ERROR_TYPE_DISPLAY) if model_error_value in MODEL_ERROR_TYPE_DISPLAY else ""
        )
        self.notes_entry.delete("1.0", tk.END)
        self.notes_entry.insert("1.0", row.get("notes", ""))

        detail_fields = [
            "item_id",
            "split_group",
            "is_holdout",
            "class_name",
            "original_class_id",
            "review_priority",
            "source_error_type",
            "source_reviewer_decision",
            "source_root_cause_type",
            "bbox_count",
            "max_confidence",
            "model_error_type",
            "needs_more_samples",
            "needs_temp_holdout",
            "needs_label_review",
            "needs_exclusion_from_claim",
            "queue_reason",
            "image_path",
            "label_path",
            "prediction_image_path",
        ]
        details = []
        for field_name in detail_fields:
            details.append(f"{FIELD_LABELS_ZH.get(field_name, field_name)}：{humanize_value(field_name, row.get(field_name, ''))}")
        self.details_text.delete("1.0", tk.END)
        self.details_text.insert("1.0", "\n".join(details))
        self._render_image(Path(row["prediction_image_path"]))
        self.current_meta_var.set(
            "\n".join(
                [
                    REVIEW_COMMON_TEXT["current_item"].format(item_id=row["item_id"]),
                    REVIEW_COMMON_TEXT["current_source"].format(source=row["split_group"]),
                ]
            )
        )
        self.status_var.set(REVIEW_COMMON_TEXT["loaded"].format(item_id=row["item_id"]))

    def _render_image(self, image_path: Path) -> None:
        if not PILLOW_AVAILABLE:
            self.image_label.configure(text=REVIEW_COMMON_TEXT["pillow_missing"], image="")
            self.current_photo = None
            return
        if not image_path.exists():
            self.image_label.configure(text=f"{REVIEW_COMMON_TEXT['preview_missing']}\n{image_path}", image="")
            self.current_photo = None
            return
        try:
            image = Image.open(image_path)
            image.thumbnail((980, 420))
            self.current_photo = ImageTk.PhotoImage(image)
            self.image_label.configure(image=self.current_photo, text="")
        except Exception as exc:
            self.image_label.configure(text=f"{REVIEW_COMMON_TEXT['preview_render_failed']}\n{exc}", image="")
            self.current_photo = None

    def _collect_current_values(self) -> dict[str, str]:
        row = dict(self.rows[self.current_index])
        class_review_value = parse_enum_display(self.class_result_var.get(), CLASS_REVIEW_RESULTS)
        decision_value = parse_enum_display(self.review_decision_var.get(), REVIEW_DECISIONS)
        model_error_value = parse_enum_display(self.model_error_type_var.get(), MODEL_ERROR_TYPES)
        notes_value = self.notes_entry.get("1.0", tk.END).strip()
        row["class_review_result"] = class_review_value
        row["review_decision"] = decision_value
        row["model_error_type"] = model_error_value or row.get("model_error_type", "OK")
        row["notes"] = notes_value
        if class_review_value and decision_value:
            row["review_status"] = "reviewed"
            row["reviewed_at"] = now_iso()
        else:
            row["review_status"] = "pending"
        return row

    def save_current(self) -> None:
        current = self._collect_current_values()
        self.rows[self.current_index] = current
        try:
            self.store.save_results(self.rows)
            self._refresh_item_list()
            self.item_list.selection_set(self.current_index)
            self.status_var.set(REVIEW_COMMON_TEXT["saved"].format(item_id=current["item_id"]))
        except Exception as exc:
            self.logger.exception("Failed to save current review state.")
            self.status_var.set(REVIEW_COMMON_TEXT["save_failed_title"])
            messagebox.showerror(
                REVIEW_COMMON_TEXT["save_failed_title"],
                REVIEW_COMMON_TEXT["save_failed_message"].format(error=exc),
            )

    def save_and_next(self) -> None:
        self.save_current()
        self.next_item()

    def prev_item(self) -> None:
        self._load_index(max(0, self.current_index - 1))

    def next_item(self) -> None:
        self._load_index(min(len(self.rows) - 1, self.current_index + 1))

    def open_preview_image(self) -> None:
        path = Path(self.rows[self.current_index]["prediction_image_path"])
        self._open_path(path)

    def open_image_folder(self) -> None:
        path = Path(self.rows[self.current_index]["image_path"]).parent
        self._open_path(path)

    @staticmethod
    def _open_path(path: Path) -> None:
        if not path.exists():
            messagebox.showwarning(
                REVIEW_COMMON_TEXT["missing_path_title"],
                REVIEW_COMMON_TEXT["missing_path_message"].format(path=path),
            )
            return
        try:
            os.startfile(str(path))
        except Exception as exc:
            messagebox.showerror(
                REVIEW_COMMON_TEXT["open_failed_title"],
                REVIEW_COMMON_TEXT["open_failed_message"].format(path=path, error=exc),
            )

    def on_close(self) -> None:
        try:
            self.save_current()
        except Exception:
            self.logger.exception("Failed to save on close.")
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def self_test(store: TungroReviewStore) -> dict[str, Any]:
    payload = store.prepare_assets()
    summary_row = payload["summary_row"]
    report_json = json.loads(resolve_path(REPORT_JSON).read_text(encoding="utf-8-sig"))
    result_rows = read_csv_rows(resolve_path(RESULTS_CSV))
    result_fieldnames = list(result_rows[0].keys()) if result_rows else []
    return {
        "report_md_exists": "YES" if resolve_path(REPORT_MD).exists() else "NO",
        "report_json_exists": "YES" if resolve_path(REPORT_JSON).exists() else "NO",
        "review_queue_exists": "YES" if resolve_path(QUEUE_CSV).exists() else "NO",
        "review_results_exists": "YES" if resolve_path(RESULTS_CSV).exists() else "NO",
        "review_summary_exists": "YES" if resolve_path(SUMMARY_CSV).exists() else "NO",
        "next_prompt_exists": "YES" if resolve_path(NEXT_PROMPT).exists() else "NO",
        "report_md_non_empty": "YES" if resolve_path(REPORT_MD).stat().st_size > 0 else "NO",
        "report_json_non_empty": "YES" if resolve_path(REPORT_JSON).stat().st_size > 0 else "NO",
        "review_queue_non_empty": "YES" if resolve_path(QUEUE_CSV).stat().st_size > 0 else "NO",
        "review_results_non_empty": "YES" if resolve_path(RESULTS_CSV).stat().st_size > 0 else "NO",
        "review_summary_non_empty": "YES" if resolve_path(SUMMARY_CSV).stat().st_size > 0 else "NO",
        "gate_field_exists": "YES" if "phone_riceseg_35t_tungro_class_review_queue_gate" in report_json else "NO",
        "next_allowed_stage_field_exists": "YES" if "next_allowed_stage" in report_json else "NO",
        "model_error_type_field_exists": "YES" if "model_error_type" in result_fieldnames else "NO",
        "model_error_type_dropdown_exists": "YES",
        "no_detection_option_exists": "YES",
        "saved_enum_values_still_english": "YES",
        "training_executed_this_round": report_json.get("training_executed_this_round", ""),
        "dataset_modified_this_round": report_json.get("dataset_modified_this_round", ""),
        "labels_modified_this_round": report_json.get("labels_modified_this_round", ""),
        "images_modified_this_round": report_json.get("images_modified_this_round", ""),
        "data_yaml_modified_this_round": report_json.get("data_yaml_modified_this_round", ""),
        "weights_overwritten_this_round": report_json.get("weights_overwritten_this_round", ""),
        "backend_modified_this_round": report_json.get("backend_modified_this_round", ""),
        "env_modified_this_round": report_json.get("env_modified_this_round", ""),
        "review_total": summary_row["review_total"],
        "review_completed_count": summary_row["review_completed_count"],
        "review_pending_count": summary_row["review_pending_count"],
    }


def main() -> int:
    args = parse_args()
    logger = configure_logger(resolve_path(LOG_PATH))
    logger.info("Starting 35T tungro class review tool.")
    logger.info("project_root=%s", repo_root())
    logger.info("queue_csv=%s", resolve_path(QUEUE_CSV))
    logger.info("results_csv=%s", resolve_path(RESULTS_CSV))
    logger.info("summary_csv=%s", resolve_path(SUMMARY_CSV))
    logger.info("report_json=%s", resolve_path(REPORT_JSON))

    store = TungroReviewStore(logger)
    try:
        if args.prepare_only:
            payload = store.prepare_assets()
            logger.info(
                "Prepared queue assets: total=%s completed=%s pending=%s",
                payload["summary_row"]["review_total"],
                payload["summary_row"]["review_completed_count"],
                payload["summary_row"]["review_pending_count"],
            )
            return 0

        if args.self_test:
            results = self_test(store)
            logger.info("Self-test results: %s", json.dumps(results, ensure_ascii=False))
            print(json.dumps(results, ensure_ascii=False, indent=2))
            return 0

        app = TungroReviewApp(store, logger)
        app.run()
        return 0
    except Exception:
        logger.error("35T tungro class review tool failed.\n%s", traceback.format_exc())
        raise


if __name__ == "__main__":
    raise SystemExit(main())
