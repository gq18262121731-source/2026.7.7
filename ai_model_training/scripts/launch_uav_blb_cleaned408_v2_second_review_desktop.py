"""Desktop UI for UAV BLB cleaned408_v2 targeted second review.

This launcher reads the before/after second-review queue and writes only
second-review decisions, summaries, gate reports, and status metadata.
It does not train, create weights, or modify source images/YOLO labels.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
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
except Exception:  # noqa: BLE001
    Image = None
    ImageTk = None
    PILLOW_AVAILABLE = False


APP_TITLE = "UAV BLB cleaned408_v2 targeted second review"
DATASET_VERSION = "uav_blb_cleaned408_v2"
QUEUE_CSV = "reports/uav_blb_408_cleaned408_v2_second_review_list.csv"
DECISIONS_CSV = "reports/uav_blb_408_cleaned408_v2_second_review_decisions.csv"
DECISIONS_JSON = "reports/uav_blb_408_cleaned408_v2_second_review_decisions.json"
SUMMARY_JSON = "reports/uav_blb_408_cleaned408_v2_second_review_summary.json"
GATE_REPORT = "reports/uav_blb_408_cleaned408_v2_second_review_gate_report.md"
STATUS_YAML = "metadata/uav_blb_cleaned408_v2_status.yaml"
SELFTEST_JSON = "reports/uav_blb_408_cleaned408_v2_second_review_launcher_selftest.json"
SELFTEST_MD = "reports/uav_blb_408_cleaned408_v2_second_review_launcher_selftest.md"
OUTPUT_PREFIX = "reports/uav_blb_408_cleaned408_v2_second_review"
DERIVED_DATASET = "datasets/rice_uav_ms_blb_cleaned408_v2"
OVERLAY_SUBSTRING = "datasets/rice_uav_ms_blb_cleaned408_v2/overlays_before_after"

DECISIONS = [
    "CANDIDATE_ACCEPT",
    "CANDIDATE_NEEDS_FIX",
    "CANDIDATE_REJECT",
    "KEEP_ORIGINAL",
    "SECOND_REVIEW_UNSURE",
]
DECISION_DISPLAY_ZH = {
    "CANDIDATE_ACCEPT": "候选标签通过",
    "CANDIDATE_NEEDS_FIX": "候选标签仍需修正",
    "CANDIDATE_REJECT": "候选标签不采用",
    "KEEP_ORIGINAL": "保留原始标注",
    "SECOND_REVIEW_UNSURE": "不确定，需再复核",
}
DECISION_CODE_BY_DISPLAY = {display: code for code, display in DECISION_DISPLAY_ZH.items()}
DECISION_DISPLAY_VALUES = [DECISION_DISPLAY_ZH[code] for code in DECISIONS]

ISSUES = [
    "box_quality_improved",
    "duplicate_reduced",
    "duplicate_still_exists",
    "fragmented_improved",
    "fragmented_still_exists",
    "noise_removed",
    "noise_still_exists",
    "true_lesion_removed",
    "missing_bbox_created",
    "box_quality_worse",
    "unclear_multispectral_texture",
]
ISSUE_DISPLAY_ZH = {
    "box_quality_improved": "框质量整体改善",
    "duplicate_reduced": "重复框已减少",
    "duplicate_still_exists": "重复框仍存在",
    "fragmented_improved": "碎片化有所改善",
    "fragmented_still_exists": "碎片化仍存在",
    "noise_removed": "噪声框已删除",
    "noise_still_exists": "噪声框仍存在",
    "true_lesion_removed": "疑似误删真实病斑",
    "missing_bbox_created": "候选标签产生漏框",
    "box_quality_worse": "候选标签质量变差",
    "unclear_multispectral_texture": "多光谱纹理不确定",
}
ISSUE_CODE_BY_DISPLAY = {display: code for code, display in ISSUE_DISPLAY_ZH.items()}
ISSUE_DISPLAY_VALUES = [ISSUE_DISPLAY_ZH[code] for code in ISSUES]

HOTKEYS = {
    "1": (
        "CANDIDATE_ACCEPT",
        "box_quality_improved",
        "候选标签通过：框质量整体改善，主要疑似 BLB 病斑区域仍被保留。",
    ),
    "2": (
        "CANDIDATE_NEEDS_FIX",
        "duplicate_still_exists",
        "候选标签仍需修正：重复框或相邻重叠框仍存在，需要继续合并或去重。",
    ),
    "3": (
        "CANDIDATE_NEEDS_FIX",
        "fragmented_still_exists",
        "候选标签仍需修正：碎片化框仍存在，拆分/合并关系仍不稳定。",
    ),
    "4": (
        "CANDIDATE_NEEDS_FIX",
        "noise_still_exists",
        "候选标签仍需修正：仍保留疑似多光谱噪声、纹理、反光、阴影或背景误检框。",
    ),
    "5": (
        "CANDIDATE_REJECT",
        "true_lesion_removed",
        "候选标签不采用：疑似误删真实病斑或有效病株冠层区域。",
    ),
    "6": (
        "KEEP_ORIGINAL",
        "box_quality_worse",
        "保留原始标注：候选标签质量变差，原始标注更合理。",
    ),
    "7": (
        "SECOND_REVIEW_UNSURE",
        "unclear_multispectral_texture",
        "不确定，需再复核：多光谱纹理仍不确定，需要再次人工确认。",
    ),
    "8": (
        "CANDIDATE_NEEDS_FIX",
        "missing_bbox_created",
        "候选标签仍需修正：候选标签产生漏框或删除了过多相关目标区域。",
    ),
}

SERIOUS_ISSUES = {
    "duplicate_still_exists",
    "fragmented_still_exists",
    "noise_still_exists",
    "true_lesion_removed",
    "missing_bbox_created",
    "box_quality_worse",
    "unclear_multispectral_texture",
}

HELP_TEXT = (
    "快捷键：\n"
    "1 = 候选标签通过 / 框质量整体改善\n"
    "2 = 仍需修正 / 重复框仍存在\n"
    "3 = 仍需修正 / 碎片化仍存在\n"
    "4 = 仍需修正 / 噪声框仍存在\n"
    "5 = 不采用候选 / 疑似误删真实病斑\n"
    "6 = 保留原始标注 / 候选标签质量变差\n"
    "7 = 不确定 / 多光谱纹理不确定\n"
    "8 = 仍需修正 / 候选标签产生漏框\n\n"
    "空格 = 保存并下一张\n"
    "← / → = 上一张 / 下一张\n"
    "O = 切换原始图 / 候选图\n"
    "B = 打开大图\n"
    "/ = 填写备注\n"
    "Esc = 退出备注输入"
)

REVIEW_GUIDE = (
    "请比较左侧原始标注和右侧 cleaned408_v2 候选标注。"
    "重点判断：候选标签是否减少重复框、是否保留主要病斑、是否误删真实病斑、是否产生漏框。"
    "中文选项用于人工审核理解；后台仍保存英文 code，便于统计。"
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root() / path


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    return path.resolve().relative_to(repo_root()).as_posix()


def atomic_write_text(path: Path, content: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def atomic_write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


@dataclass(frozen=True)
class GateThresholds:
    accept_ratio_min: float = 0.80
    needs_fix_max: int = 12
    serious_ratio_max: float = 0.12
    duplicate_still_exists_max: int = 6
    true_lesion_removed_max: int = 2
    missing_bbox_created_max: int = 2
    reject_keep_unsure_max: int = 5


class SecondReviewStore:
    def __init__(self) -> None:
        self.queue_csv = resolve_path(QUEUE_CSV)
        self.decisions_csv = resolve_path(DECISIONS_CSV)
        self.decisions_json = resolve_path(DECISIONS_JSON)
        self.summary_json = resolve_path(SUMMARY_JSON)
        self.gate_report = resolve_path(GATE_REPORT)
        self.status_yaml = resolve_path(STATUS_YAML)
        self.thresholds = GateThresholds()
        self.items: list[dict[str, Any]] = []
        self.item_by_id: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.queue_csv.exists():
            raise FileNotFoundError(f"second review queue not found: {self.queue_csv}")
        rows = read_csv(self.queue_csv)
        for idx, row in enumerate(rows, start=1):
            visual_path = row.get("visual_path", "")
            item = {
                "review_id": f"cleaned408_v2_sr_{idx:03d}",
                "dataset_version": DATASET_VERSION,
                "image_name": row.get("image_name", ""),
                "split": row.get("split", ""),
                "source_issue_type": row.get("issue_type", ""),
                "original_bbox_count": int(float(row.get("original_bbox_count") or 0)),
                "cleaned_bbox_count": int(float(row.get("cleaned_bbox_count") or 0)),
                "review_reason": row.get("review_reason", ""),
                "visual_path": visual_path,
                "review_status": "unreviewed",
                "review_decision": "",
                "decision_code": "",
                "decision_display_zh": "",
                "second_review_issue_type": "",
                "issue_code": "",
                "issue_display_zh": "",
                "reviewer_notes": "",
                "comment": "",
                "reviewer": "human_reviewer",
                "reviewed_at": "",
                "review_time": "",
            }
            self._validate_item(item)
            self.items.append(item)
            self.item_by_id[item["review_id"]] = item
        self._overlay_existing_decisions()

    def _validate_item(self, item: dict[str, Any]) -> None:
        visual_path = item.get("visual_path", "")
        normalized = visual_path.replace("\\", "/")
        if OVERLAY_SUBSTRING not in normalized:
            raise RuntimeError(f"unexpected visual path outside cleaned408_v2 overlays: {visual_path}")
        resolved = resolve_path(visual_path)
        if not resolved.exists():
            raise FileNotFoundError(f"before/after overlay missing: {resolved}")

    def _validate_output_paths(self) -> None:
        expected = (repo_root() / OUTPUT_PREFIX).as_posix()
        for path in (self.decisions_csv, self.decisions_json, self.summary_json, self.gate_report):
            if expected not in path.as_posix():
                raise RuntimeError(f"refusing to write outside second-review output prefix: {path}")

    def _overlay_existing_decisions(self) -> None:
        if not self.decisions_csv.exists():
            return
        for row in read_csv(self.decisions_csv):
            review_id = row.get("review_id", "")
            item = self.item_by_id.get(review_id)
            if not item:
                continue
            item["review_status"] = row.get("review_status", "unreviewed") or "unreviewed"
            decision_code = row.get("decision_code") or row.get("review_decision", "")
            issue_code = row.get("issue_code") or row.get("second_review_issue_type", "")
            item["review_decision"] = decision_code
            item["decision_code"] = decision_code
            item["decision_display_zh"] = row.get("decision_display_zh") or DECISION_DISPLAY_ZH.get(decision_code, "")
            item["second_review_issue_type"] = issue_code
            item["issue_code"] = issue_code
            item["issue_display_zh"] = row.get("issue_display_zh") or ISSUE_DISPLAY_ZH.get(issue_code, "")
            comment = row.get("comment") or row.get("reviewer_notes", "")
            item["reviewer_notes"] = comment
            item["comment"] = comment
            item["reviewer"] = row.get("reviewer") or "human_reviewer"
            review_time = row.get("review_time") or row.get("reviewed_at", "")
            item["reviewed_at"] = review_time
            item["review_time"] = review_time

    def visual_path_for(self, item: dict[str, Any]) -> Path:
        return resolve_path(item["visual_path"])

    def save_decision(self, review_id: str, review_decision: str, issue_type: str, notes: str) -> None:
        if review_decision not in DECISIONS:
            raise ValueError("review_decision is required")
        if issue_type not in ISSUES:
            raise ValueError("second_review_issue_type is required")
        self._validate_output_paths()
        item = self.item_by_id[review_id]
        review_time = now_iso()
        comment = notes.strip()
        item["review_status"] = "reviewed"
        item["review_decision"] = review_decision
        item["decision_code"] = review_decision
        item["decision_display_zh"] = DECISION_DISPLAY_ZH[review_decision]
        item["second_review_issue_type"] = issue_type
        item["issue_code"] = issue_type
        item["issue_display_zh"] = ISSUE_DISPLAY_ZH[issue_type]
        item["reviewer_notes"] = comment
        item["comment"] = comment
        item["reviewer"] = item.get("reviewer") or "human_reviewer"
        item["reviewed_at"] = review_time
        item["review_time"] = review_time
        self.persist(f"save:{review_id}")

    def persist(self, reason: str) -> None:
        rows = [dict(item) for item in self.items]
        fieldnames = [
            "review_id",
            "dataset_version",
            "image_name",
            "split",
            "source_issue_type",
            "original_bbox_count",
            "cleaned_bbox_count",
            "review_reason",
            "visual_path",
            "review_status",
            "decision_code",
            "decision_display_zh",
            "issue_code",
            "issue_display_zh",
            "comment",
            "reviewer",
            "review_time",
            "review_decision",
            "second_review_issue_type",
            "reviewer_notes",
            "reviewed_at",
        ]
        atomic_write_csv(self.decisions_csv, rows, fieldnames)
        atomic_write_json(self.decisions_json, {"generated_at": now_iso(), "reason": reason, "items": rows})
        summary = self.compute_summary()
        atomic_write_json(self.summary_json, summary)
        atomic_write_text(self.gate_report, self.render_gate_report(summary))
        atomic_write_text(self.status_yaml, self.render_status_yaml(summary))

    def compute_summary(self) -> dict[str, Any]:
        reviewed = [item for item in self.items if item.get("review_status") == "reviewed"]
        total = len(self.items)
        reviewed_count = len(reviewed)
        decision_counts = Counter(item.get("review_decision", "") for item in reviewed)
        issue_counts = Counter(item.get("second_review_issue_type", "") for item in reviewed)
        serious_issue_count = sum(
            1
            for item in reviewed
            if item.get("review_decision") in {"CANDIDATE_NEEDS_FIX", "CANDIDATE_REJECT", "KEEP_ORIGINAL", "SECOND_REVIEW_UNSURE"}
            or item.get("second_review_issue_type") in SERIOUS_ISSUES
        )
        serious_issue_ratio = serious_issue_count / reviewed_count if reviewed_count else None
        thresholds = self.thresholds
        reject_keep_unsure = (
            decision_counts.get("CANDIDATE_REJECT", 0)
            + decision_counts.get("KEEP_ORIGINAL", 0)
            + decision_counts.get("SECOND_REVIEW_UNSURE", 0)
        )
        accept_ratio = decision_counts.get("CANDIDATE_ACCEPT", 0) / total if total else 0.0
        if reviewed_count < total:
            gate = "PENDING"
            training_allowed = False
            next_action = "Continue targeted second review. Training remains forbidden."
        elif (
            accept_ratio >= thresholds.accept_ratio_min
            and decision_counts.get("CANDIDATE_NEEDS_FIX", 0) <= thresholds.needs_fix_max
            and (serious_issue_ratio or 0.0) <= thresholds.serious_ratio_max
            and issue_counts.get("duplicate_still_exists", 0) <= thresholds.duplicate_still_exists_max
            and issue_counts.get("true_lesion_removed", 0) <= thresholds.true_lesion_removed_max
            and issue_counts.get("missing_bbox_created", 0) <= thresholds.missing_bbox_created_max
            and reject_keep_unsure <= thresholds.reject_keep_unsure_max
        ):
            gate = "PASS"
            training_allowed = True
            next_action = "May enter UAV BLB short-experiment training gate; actual training remains a separate command."
        else:
            gate = "FAIL"
            training_allowed = False
            next_action = "Do not train. Continue rule tuning or manual label correction before another gate."
        return {
            "generated_at": now_iso(),
            "dataset_version": DATASET_VERSION,
            "total_second_review_items": total,
            "reviewed": reviewed_count,
            "unreviewed": total - reviewed_count,
            "candidate_accept": decision_counts.get("CANDIDATE_ACCEPT", 0),
            "candidate_needs_fix": decision_counts.get("CANDIDATE_NEEDS_FIX", 0),
            "candidate_reject": decision_counts.get("CANDIDATE_REJECT", 0),
            "keep_original": decision_counts.get("KEEP_ORIGINAL", 0),
            "second_review_unsure": decision_counts.get("SECOND_REVIEW_UNSURE", 0),
            "duplicate_still_exists_count": issue_counts.get("duplicate_still_exists", 0),
            "fragmented_still_exists_count": issue_counts.get("fragmented_still_exists", 0),
            "noise_still_exists_count": issue_counts.get("noise_still_exists", 0),
            "true_lesion_removed_count": issue_counts.get("true_lesion_removed", 0),
            "missing_bbox_created_count": issue_counts.get("missing_bbox_created", 0),
            "serious_issue_count": serious_issue_count,
            "serious_issue_ratio": serious_issue_ratio,
            "decision_counts": dict(decision_counts),
            "issue_counts": dict(issue_counts),
            "gate_thresholds": thresholds.__dict__,
            "cleaned408_v2_gate": gate,
            "training_allowed": training_allowed,
            "next_action": next_action,
            "boundaries": {
                "training_executed": False,
                "new_weights_generated": False,
                "original_images_modified": False,
                "original_yolo_labels_overwritten": False,
                "backend_modified": False,
                "env_modified": False,
                "manual_issue_types_are_yolo_classes": False,
                "yolo_class_policy": "single class 0=bacterial_leaf_blight",
            },
        }

    def render_gate_report(self, summary: dict[str, Any]) -> str:
        lines = [
            "# UAV BLB cleaned408_v2 Targeted Second Review Gate Report",
            "",
            "## Boundary",
            "",
            "- training_executed: `NO`",
            "- new_weights_generated: `NO`",
            "- original_images_modified: `NO`",
            "- original_yolo_labels_overwritten: `NO`",
            "- backend_modified: `NO`",
            "- env_modified: `NO`",
            "- yolo_class_policy: `single class 0=bacterial_leaf_blight`",
            "",
            "## Summary",
            "",
            f"- total_second_review_items: `{summary['total_second_review_items']}`",
            f"- reviewed: `{summary['reviewed']}`",
            f"- candidate_accept: `{summary['candidate_accept']}`",
            f"- candidate_needs_fix: `{summary['candidate_needs_fix']}`",
            f"- candidate_reject: `{summary['candidate_reject']}`",
            f"- keep_original: `{summary['keep_original']}`",
            f"- second_review_unsure: `{summary['second_review_unsure']}`",
            f"- duplicate_still_exists_count: `{summary['duplicate_still_exists_count']}`",
            f"- fragmented_still_exists_count: `{summary['fragmented_still_exists_count']}`",
            f"- noise_still_exists_count: `{summary['noise_still_exists_count']}`",
            f"- true_lesion_removed_count: `{summary['true_lesion_removed_count']}`",
            f"- missing_bbox_created_count: `{summary['missing_bbox_created_count']}`",
            f"- serious_issue_count: `{summary['serious_issue_count']}`",
            f"- serious_issue_ratio: `{summary['serious_issue_ratio']}`",
            f"- cleaned408_v2_gate: `{summary['cleaned408_v2_gate']}`",
            f"- training_allowed: `{str(summary['training_allowed']).lower()}`",
            f"- next_action: {summary['next_action']}",
            "",
            "## Decision Counts",
            "",
        ]
        for code in DECISIONS:
            lines.append(f"- `{code}`: `{summary['decision_counts'].get(code, 0)}`")
        lines.extend(["", "## Issue Counts", ""])
        if summary["issue_counts"]:
            for code, count in sorted(summary["issue_counts"].items()):
                lines.append(f"- `{code}`: `{count}`")
        else:
            lines.append("- No reviewed issue counts yet.")
        return "\n".join(lines) + "\n"

    def render_status_yaml(self, summary: dict[str, Any]) -> str:
        return f"""cleaned408_v2_stage: TARGETED_SECOND_REVIEW
source_manual_review: COMPLETE
source_manual_gate: FAIL
candidate_generation: COMPLETE
second_review_total: {summary['total_second_review_items']}
second_review_reviewed: {summary['reviewed']}
cleaned408_v2_gate: {summary['cleaned408_v2_gate']}
training_allowed: {str(summary['training_allowed']).lower()}
original_images_modified: false
original_labels_modified: false
weights_modified: false
backend_modified: false
env_modified: false
derived_dataset_created: true
derived_dataset_root: {DERIVED_DATASET}
yolo_class_policy: single class 0=bacterial_leaf_blight
next_allowed_stage: {"UAV_BLB_SHORT_EXPERIMENT_TRAINING_GATE" if summary['cleaned408_v2_gate'] == "PASS" else "TARGETED_LABEL_CORRECTION_OR_SECOND_REVIEW"}
notes:
  - decisions must come from real targeted second review operations
  - manual second-review issue types are metadata only, not YOLO classes
  - do not train unless cleaned408_v2_gate is PASS and the next training gate is explicitly started
"""


class SecondReviewApp:
    def __init__(self, store: SecondReviewStore) -> None:
        self.store = store
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("1480x920+40+40")
        self.status_filter_var = tk.StringVar(value="unreviewed")
        self.review_decision_var = tk.StringVar(value="")
        self.issue_type_var = tk.StringVar(value="")
        self.display_mode_var = tk.StringVar(value="comparison")
        self.summary_var = tk.StringVar(value="")
        self.item_var = tk.StringVar(value="")
        self.path_var = tk.StringVar(value="")
        self.preview_cache: ImageTk.PhotoImage | None = None
        self.filtered: list[dict[str, Any]] = []
        self.index = 0
        self._build()
        self._bind()
        self.refresh()

    def _build(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=0)
        self.root.rowconfigure(0, weight=1)

        left = ttk.Frame(self.root, padding=8)
        left.grid(row=0, column=0, sticky="nsew")
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        header = ttk.Frame(left)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        header.columnconfigure(4, weight=1)
        ttk.Label(header, text=APP_TITLE, font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self.summary_var, justify="right").grid(row=0, column=4, sticky="e")
        ttk.Label(header, textvariable=self.item_var, justify="left").grid(row=1, column=0, columnspan=5, sticky="ew")

        self.preview_label = ttk.Label(left, anchor="center")
        self.preview_label.grid(row=1, column=0, sticky="nsew")
        ttk.Label(left, textvariable=self.path_var, foreground="#555", wraplength=980).grid(row=2, column=0, sticky="ew")

        right = ttk.Frame(self.root, padding=10, width=430)
        right.grid(row=0, column=1, sticky="ns")
        right.columnconfigure(0, weight=1)

        ttk.Label(right, text="二次复审操作", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(right, text="筛选").grid(row=1, column=0, sticky="w", pady=(10, 0))
        filter_combo = ttk.Combobox(
            right,
            textvariable=self.status_filter_var,
            values=["unreviewed", "reviewed", "all"],
            state="readonly",
            width=28,
        )
        filter_combo.grid(row=2, column=0, sticky="ew")
        filter_combo.bind("<<ComboboxSelected>>", lambda _: self.refresh())

        ttk.Label(right, text="审核结论").grid(row=3, column=0, sticky="w", pady=(10, 0))
        decision_combo = ttk.Combobox(
            right,
            textvariable=self.review_decision_var,
            values=DECISION_DISPLAY_VALUES,
            state="readonly",
            width=36,
        )
        decision_combo.grid(row=4, column=0, sticky="ew")

        ttk.Label(right, text="问题类型").grid(row=5, column=0, sticky="w", pady=(10, 0))
        issue_combo = ttk.Combobox(
            right,
            textvariable=self.issue_type_var,
            values=ISSUE_DISPLAY_VALUES,
            state="readonly",
            width=36,
        )
        issue_combo.grid(row=6, column=0, sticky="ew")

        ttk.Label(right, text="备注 / 原因").grid(row=7, column=0, sticky="w", pady=(10, 0))
        self.notes = tk.Text(right, height=5, width=48, wrap="word")
        self.notes.grid(row=8, column=0, sticky="ew")

        buttons = ttk.Frame(right)
        buttons.grid(row=9, column=0, sticky="ew", pady=(10, 0))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        ttk.Button(buttons, text="保存", command=self.save_current).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="保存并下一张", command=self.save_and_next).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ttk.Button(buttons, text="上一张", command=self.prev_item).grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=(6, 0))
        ttk.Button(buttons, text="下一张", command=self.next_item).grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=(6, 0))
        ttk.Button(buttons, text="打开大图", command=self.open_current_image).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        ttk.Label(right, text="快捷键").grid(row=10, column=0, sticky="w", pady=(14, 0))
        ttk.Label(right, text=HELP_TEXT, wraplength=400, justify="left").grid(row=11, column=0, sticky="ew")

        ttk.Separator(right).grid(row=12, column=0, sticky="ew", pady=10)
        ttk.Label(right, text="审核说明").grid(row=13, column=0, sticky="w")
        ttk.Label(right, text=REVIEW_GUIDE, wraplength=400, justify="left").grid(row=14, column=0, sticky="ew")

    def _bind(self) -> None:
        self.root.bind("<Left>", lambda event: self.prev_item() if not self.is_text_focus() else None)
        self.root.bind("<Right>", lambda event: self.next_item() if not self.is_text_focus() else None)
        for key in HOTKEYS:
            self.root.bind(key, lambda event, value=key: self.select_hotkey(value) if not self.is_text_focus() else None)
        self.root.bind("<space>", lambda event: self.save_and_next() if not self.is_text_focus() else None)
        self.root.bind("<Return>", lambda event: self.save_and_next() if not self.is_text_focus() else None)
        self.root.bind("<Control-Return>", lambda _: self.save_and_next())
        self.root.bind("<Control-s>", lambda _: self.save_current())
        self.root.bind("b", lambda event: self.open_current_image() if not self.is_text_focus() else None)
        self.root.bind("B", lambda event: self.open_current_image() if not self.is_text_focus() else None)
        self.root.bind("o", lambda event: self.toggle_display_mode() if not self.is_text_focus() else None)
        self.root.bind("O", lambda event: self.toggle_display_mode() if not self.is_text_focus() else None)
        self.root.bind("/", lambda event: self.focus_notes() if not self.is_text_focus() else None)
        self.root.bind("<Escape>", lambda event: self.root.focus_set())

    def is_text_focus(self) -> bool:
        return self.root.focus_get() is self.notes

    def focus_notes(self) -> str:
        self.notes.focus_set()
        return "break"

    def select_hotkey(self, key: str) -> str:
        decision, issue, comment = HOTKEYS[key]
        self.review_decision_var.set(DECISION_DISPLAY_ZH[decision])
        self.issue_type_var.set(ISSUE_DISPLAY_ZH[issue])
        self.append_comment(comment)
        return "break"

    def decision_code_from_ui(self) -> str:
        value = self.review_decision_var.get().strip()
        return DECISION_CODE_BY_DISPLAY.get(value, value)

    def issue_code_from_ui(self) -> str:
        value = self.issue_type_var.get().strip()
        return ISSUE_CODE_BY_DISPLAY.get(value, value)

    def toggle_display_mode(self) -> str:
        modes = ["comparison", "original", "candidate"]
        current = self.display_mode_var.get()
        self.display_mode_var.set(modes[(modes.index(current) + 1) % len(modes)] if current in modes else "comparison")
        self.show_current()
        return "break"

    def append_comment(self, text: str) -> None:
        current = self.notes.get("1.0", "end-1c").strip()
        if text in current:
            return
        if current:
            self.notes.insert("end", "\n" + text)
        else:
            self.notes.insert("1.0", text)

    def refresh(self) -> None:
        mode = self.status_filter_var.get()
        if mode == "unreviewed":
            self.filtered = [item for item in self.store.items if item["review_status"] != "reviewed"]
        elif mode == "reviewed":
            self.filtered = [item for item in self.store.items if item["review_status"] == "reviewed"]
        else:
            self.filtered = list(self.store.items)
        self.index = min(self.index, max(0, len(self.filtered) - 1))
        self.update_summary()
        self.show_current()

    def update_summary(self) -> None:
        summary = self.store.compute_summary()
        ratio = summary["serious_issue_ratio"]
        ratio_text = "n/a" if ratio is None else f"{ratio:.4f}"
        self.summary_var.set(
            f"reviewed {summary['reviewed']}/{summary['total_second_review_items']}\n"
            f"gate {summary['cleaned408_v2_gate']} | serious ratio {ratio_text} | training_allowed={summary['training_allowed']}"
        )

    def current_item(self) -> dict[str, Any] | None:
        if not self.filtered:
            return None
        return self.filtered[self.index]

    def show_current(self) -> None:
        item = self.current_item()
        if not item:
            self.item_var.set("No items in current filter.")
            self.path_var.set("")
            self.preview_label.configure(image="", text="")
            return
        decision_code = item.get("decision_code") or item.get("review_decision", "")
        issue_code = item.get("issue_code") or item.get("second_review_issue_type", "")
        self.review_decision_var.set(DECISION_DISPLAY_ZH.get(decision_code, decision_code))
        self.issue_type_var.set(ISSUE_DISPLAY_ZH.get(issue_code, issue_code))
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", item.get("reviewer_notes", ""))
        self.item_var.set(
            f"{item['review_id']} | {self.index + 1}/{len(self.filtered)} | {item['image_name']} | {item['split']} | status={item['review_status']} | view={self.display_mode_var.get()}\n"
            f"source_issue={item['source_issue_type']} | original_bbox={item['original_bbox_count']} | cleaned_bbox={item['cleaned_bbox_count']} | reason={item['review_reason']}"
        )
        self.path_var.set(f"visual={item['visual_path']}")
        if not PILLOW_AVAILABLE:
            self.preview_label.configure(image="", text="Pillow unavailable")
            return
        image_path = self.store.visual_path_for(item)
        try:
            img = self.load_display_image(image_path)
        except OSError as exc:
            self.preview_label.configure(image="", text=f"Preview unavailable: {exc}")
            return
        img.thumbnail((1040, 820))
        self.preview_cache = ImageTk.PhotoImage(img)
        self.preview_label.configure(image=self.preview_cache, text="")

    def load_display_image(self, image_path: Path) -> Image.Image:
        img = Image.open(image_path).convert("RGB")
        mode = self.display_mode_var.get()
        if mode == "original":
            return img.crop((0, 0, img.width // 2, img.height))
        if mode == "candidate":
            return img.crop((img.width // 2, 0, img.width, img.height))
        return img

    def open_current_image(self) -> str:
        item = self.current_item()
        if not item:
            return "break"
        path = self.store.visual_path_for(item)
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Open image failed", str(exc))
        return "break"

    def prev_item(self) -> str:
        if self.filtered:
            self.index = (self.index - 1) % len(self.filtered)
            self.show_current()
        return "break"

    def next_item(self) -> str:
        if self.filtered:
            self.index = (self.index + 1) % len(self.filtered)
            self.show_current()
        return "break"

    def save_current(self) -> bool:
        item = self.current_item()
        if not item:
            return False
        try:
            self.store.save_decision(
                item["review_id"],
                self.decision_code_from_ui(),
                self.issue_code_from_ui(),
                self.notes.get("1.0", "end").strip(),
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Save refused", str(exc))
            return False
        self.update_summary()
        return True

    def save_and_next(self) -> str:
        if self.save_current():
            self.refresh()
            if self.filtered:
                self.index = min(self.index, len(self.filtered) - 1)
                self.show_current()
        return "break"

    def run(self) -> None:
        self.root.mainloop()


def build_selftest_payload() -> dict[str, Any]:
    store = SecondReviewStore()
    summary = store.compute_summary()
    visual_paths = [store.visual_path_for(item) for item in store.items]
    return {
        "generated_at": now_iso(),
        "script": rel(Path(__file__).resolve()),
        "queue_csv": QUEUE_CSV,
        "queue_items": len(store.items),
        "visual_paths_exist": all(path.exists() for path in visual_paths),
        "visual_paths_in_cleaned408_v2_overlay_dir": all(
            OVERLAY_SUBSTRING in item["visual_path"].replace("\\", "/") for item in store.items
        ),
        "decisions_output_csv": DECISIONS_CSV,
        "summary_output_json": SUMMARY_JSON,
        "gate_report": GATE_REPORT,
        "initial_gate": summary["cleaned408_v2_gate"],
        "initial_training_allowed": summary["training_allowed"],
        "chinese_options_enabled": True,
        "english_codes_preserved": True,
        "decision_fields_include_code_and_display": True,
        "issue_fields_include_code_and_display": True,
        "hotkey_1_to_8_chinese_mapping_enabled": True,
        "display_mode_o_enabled": True,
        "training_executed": False,
        "new_weights_generated": False,
        "original_images_modified": False,
        "original_yolo_labels_overwritten": False,
        "backend_modified": False,
        "env_modified": False,
    }


def write_selftest() -> None:
    payload = build_selftest_payload()
    atomic_write_json(resolve_path(SELFTEST_JSON), payload)
    lines = [
        "# UAV BLB cleaned408_v2 Second Review Launcher Self-test",
        "",
        f"- queue_items: `{payload['queue_items']}`",
        f"- visual_paths_exist: `{payload['visual_paths_exist']}`",
        f"- visual_paths_in_cleaned408_v2_overlay_dir: `{payload['visual_paths_in_cleaned408_v2_overlay_dir']}`",
        f"- initial_gate: `{payload['initial_gate']}`",
        f"- initial_training_allowed: `{payload['initial_training_allowed']}`",
        f"- chinese_options_enabled: `{payload['chinese_options_enabled']}`",
        f"- english_codes_preserved: `{payload['english_codes_preserved']}`",
        f"- decision_fields_include_code_and_display: `{payload['decision_fields_include_code_and_display']}`",
        f"- issue_fields_include_code_and_display: `{payload['issue_fields_include_code_and_display']}`",
        f"- hotkey_1_to_8_chinese_mapping_enabled: `{payload['hotkey_1_to_8_chinese_mapping_enabled']}`",
        f"- display_mode_o_enabled: `{payload['display_mode_o_enabled']}`",
        "- training_executed: `NO`",
        "- new_weights_generated: `NO`",
        "- original_images_modified: `NO`",
        "- original_yolo_labels_overwritten: `NO`",
        "- backend_modified: `NO`",
        "- env_modified: `NO`",
        "",
        "This self-test does not create second-review decisions.",
    ]
    atomic_write_text(resolve_path(SELFTEST_MD), "\n".join(lines) + "\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch cleaned408_v2 targeted second-review desktop UI.")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        write_selftest()
        return 0
    store = SecondReviewStore()
    app = SecondReviewApp(store)
    app.run()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        message = f"{type(exc).__name__}: {exc}"
        print(message, file=sys.stderr)
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(APP_TITLE, message)
            root.destroy()
        except Exception:
            pass
        raise
