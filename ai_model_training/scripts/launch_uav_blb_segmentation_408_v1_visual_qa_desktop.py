"""Desktop visual QA gate for UAV BLB segmentation 408 v1.

This app writes visual QA decisions only after real reviewer actions. It does
not train, create weights, or modify source images/YOLO labels/backend/.env.
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


APP_TITLE = "UAV BLB segmentation 408 v1 visual QA gate"
DATASET_VERSION = "uav_blb_segmentation_408_v1"
DATASET_ROOT = "datasets/rice_uav_ms_blb_segmentation_408_v1"
MASK_STATS_CSV = "reports/uav_blb_segmentation_408_v1_mask_stats.csv"
PAIR_MANIFEST_CSV = "reports/uav_blb_segmentation_408_v1_pair_manifest.csv"
DECISIONS_CSV = "reports/uav_blb_segmentation_408_v1_visual_qa_decisions.csv"
DECISIONS_JSON = "reports/uav_blb_segmentation_408_v1_visual_qa_decisions.json"
SUMMARY_JSON = "reports/uav_blb_segmentation_408_v1_visual_qa_summary.json"
GATE_REPORT = "reports/uav_blb_segmentation_408_v1_visual_qa_gate_report.md"
CLOSURE_REPORT = "reports/uav_blb_segmentation_408_v1_visual_qa_closure_report.md"
STATUS_YAML = "metadata/uav_blb_segmentation_route_status.yaml"
SELFTEST_JSON = "reports/uav_blb_segmentation_408_v1_visual_qa_launcher_selftest.json"
SELFTEST_MD = "reports/uav_blb_segmentation_408_v1_visual_qa_launcher_selftest.md"
OUTPUT_PREFIX = "reports/uav_blb_segmentation_408_v1_visual_qa"

DECISIONS = [
    "SEG_MASK_ACCEPT",
    "SEG_MASK_NEEDS_FIX",
    "SEG_MASK_UNSURE",
    "SEG_MASK_REJECT",
]
DECISION_DISPLAY_ZH = {
    "SEG_MASK_ACCEPT": "通过",
    "SEG_MASK_NEEDS_FIX": "需要修正",
    "SEG_MASK_UNSURE": "不确定",
    "SEG_MASK_REJECT": "剔除",
}
DECISION_CODE_BY_DISPLAY = {display: code for code, display in DECISION_DISPLAY_ZH.items()}

ISSUES = [
    "mask_ok",
    "mask_too_large",
    "mask_too_small",
    "lesion_missing",
    "noise_texture_included",
    "background_included",
    "mask_misaligned",
    "uncertain_multispectral_texture",
    "foreground_ratio_too_low",
    "foreground_ratio_too_high",
    "bad_image_quality",
]
ISSUE_DISPLAY_ZH = {
    "mask_ok": "mask 覆盖合理",
    "mask_too_large": "mask 明显过大",
    "mask_too_small": "mask 明显过小",
    "lesion_missing": "mask 漏标病斑",
    "noise_texture_included": "mask 包含噪声纹理",
    "background_included": "mask 覆盖背景/黑边/无关区域",
    "mask_misaligned": "mask 与图像疑似错位",
    "uncertain_multispectral_texture": "多光谱纹理不确定",
    "foreground_ratio_too_low": "前景比例过低",
    "foreground_ratio_too_high": "前景比例过高",
    "bad_image_quality": "图像质量差",
}
ISSUE_CODE_BY_DISPLAY = {display: code for code, display in ISSUE_DISPLAY_ZH.items()}

HOTKEYS = {
    "1": ("SEG_MASK_ACCEPT", "mask_ok", "通过：mask 基本合理，覆盖疑似 BLB 病害区域。"),
    "2": ("SEG_MASK_NEEDS_FIX", "mask_too_large", "需要修正：mask 明显过大，覆盖过多无关区域。"),
    "3": ("SEG_MASK_NEEDS_FIX", "mask_too_small", "需要修正：mask 明显过小。"),
    "4": ("SEG_MASK_NEEDS_FIX", "lesion_missing", "需要修正：mask 疑似漏标病斑区域。"),
    "5": ("SEG_MASK_NEEDS_FIX", "noise_texture_included", "需要修正：mask 包含噪声纹理或伪彩误检区域。"),
    "6": ("SEG_MASK_NEEDS_FIX", "background_included", "需要修正：mask 覆盖背景、黑边或无关区域。"),
    "7": ("SEG_MASK_UNSURE", "uncertain_multispectral_texture", "不确定：多光谱纹理或病斑边界难以判断。"),
    "8": ("SEG_MASK_REJECT", "bad_image_quality", "剔除：图像质量差或 mask 严重不可用。"),
}

SERIOUS_ISSUES = {
    "mask_too_large",
    "mask_too_small",
    "lesion_missing",
    "noise_texture_included",
    "background_included",
    "mask_misaligned",
    "foreground_ratio_too_low",
    "foreground_ratio_too_high",
    "bad_image_quality",
}

HELP_TEXT = (
    "快捷键：\n"
    "1 = 通过 / mask 覆盖合理\n"
    "2 = 需要修正 / mask 明显过大\n"
    "3 = 需要修正 / mask 明显过小\n"
    "4 = 需要修正 / mask 漏标病斑\n"
    "5 = 需要修正 / mask 包含噪声纹理\n"
    "6 = 需要修正 / mask 覆盖背景/黑边/无关区域\n"
    "7 = 不确定 / 多光谱纹理不确定\n"
    "8 = 剔除 / 图像质量差或 mask 严重不可用\n\n"
    "空格 = 保存并下一张\n"
    "← / → = 上一张 / 下一张\n"
    "B = 打开大图\n"
    "/ = 填写备注\n"
    "Esc = 退出备注输入"
)

GUIDE_TEXT = (
    "请检查 overlay 中红色 mask 是否合理覆盖疑似 BLB 病害区域。重点看图像-mask 对齐、"
    "mask 是否过大/过小、是否漏标、是否包含噪声纹理或背景黑边。多光谱伪彩颜色只作参考，"
    "不要把颜色本身直接当成类别。QA 通过前 segmentation_training_allowed 必须保持 false。"
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
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def atomic_write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
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
    accept_ratio_min: float = 0.85
    needs_fix_ratio_max: float = 0.10
    unsure_ratio_max: float = 0.05
    rejected_max: int = 2
    serious_issue_ratio_max: float = 0.12
    mask_misaligned_max: int = 2


class SegVisualQAStore:
    def __init__(self) -> None:
        self.mask_stats_csv = resolve_path(MASK_STATS_CSV)
        self.pair_manifest_csv = resolve_path(PAIR_MANIFEST_CSV)
        self.decisions_csv = resolve_path(DECISIONS_CSV)
        self.decisions_json = resolve_path(DECISIONS_JSON)
        self.summary_json = resolve_path(SUMMARY_JSON)
        self.gate_report = resolve_path(GATE_REPORT)
        self.closure_report = resolve_path(CLOSURE_REPORT)
        self.status_yaml = resolve_path(STATUS_YAML)
        self.thresholds = GateThresholds()
        self.items: list[dict[str, Any]] = []
        self.item_by_name: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        stats = {row["image_name"]: row for row in read_csv(self.mask_stats_csv)}
        pairs = {row["image_name"]: row for row in read_csv(self.pair_manifest_csv)}
        for image_name in sorted(stats):
            row = stats[image_name]
            pair = pairs.get(image_name, {})
            overlay_path = resolve_path(DATASET_ROOT) / "overlays_preview" / f"{Path(image_name).stem}_seg_overlay.jpg"
            item = {
                "image_name": image_name,
                "split": row.get("split", ""),
                "image_path": row.get("image_path", ""),
                "mask_path": row.get("mask_path", ""),
                "overlay_path": rel(overlay_path),
                "foreground_ratio": row.get("foreground_ratio", ""),
                "foreground_pixel_count": row.get("foreground_pixel_count", ""),
                "mask_unique_values": row.get("mask_unique_values", ""),
                "source_mask_unique_values": row.get("source_mask_unique_values", ""),
                "empty_mask": row.get("empty_mask", ""),
                "full_mask": row.get("full_mask", ""),
                "size_match": row.get("size_match", ""),
                "conversion_notes": row.get("notes", ""),
                "source_image_path": pair.get("source_image_path", ""),
                "source_mask_path": pair.get("source_mask_path", ""),
                "review_status": "unreviewed",
                "decision_code": "",
                "decision_display_zh": "",
                "issue_code": "",
                "issue_display_zh": "",
                "comment": "",
                "reviewer": "human_reviewer",
                "review_time": "",
            }
            self._validate_item(item)
            self.items.append(item)
            self.item_by_name[image_name] = item
        self._overlay_existing_decisions()

    def _validate_item(self, item: dict[str, Any]) -> None:
        overlay = resolve_path(item["overlay_path"])
        if not overlay.exists():
            raise FileNotFoundError(f"missing overlay preview: {overlay}")
        if DATASET_ROOT not in item["overlay_path"].replace("\\", "/"):
            raise RuntimeError(f"unexpected overlay path: {item['overlay_path']}")

    def _validate_output_paths(self) -> None:
        expected = (repo_root() / OUTPUT_PREFIX).as_posix()
        for path in (self.decisions_csv, self.decisions_json, self.summary_json, self.gate_report, self.closure_report):
            if expected not in path.as_posix():
                raise RuntimeError(f"refusing to write outside visual QA output prefix: {path}")

    def _overlay_existing_decisions(self) -> None:
        if not self.decisions_csv.exists():
            return
        for row in read_csv(self.decisions_csv):
            item = self.item_by_name.get(row.get("image_name", ""))
            if not item:
                continue
            for key in (
                "review_status",
                "decision_code",
                "decision_display_zh",
                "issue_code",
                "issue_display_zh",
                "comment",
                "reviewer",
                "review_time",
            ):
                item[key] = row.get(key, item.get(key, ""))

    def overlay_path_for(self, item: dict[str, Any]) -> Path:
        return resolve_path(item["overlay_path"])

    def save_decision(self, image_name: str, decision_code: str, issue_code: str, comment: str) -> None:
        if decision_code not in DECISIONS:
            raise ValueError("decision_code is required")
        if issue_code not in ISSUES:
            raise ValueError("issue_code is required")
        self._validate_output_paths()
        item = self.item_by_name[image_name]
        item["review_status"] = "reviewed"
        item["decision_code"] = decision_code
        item["decision_display_zh"] = DECISION_DISPLAY_ZH[decision_code]
        item["issue_code"] = issue_code
        item["issue_display_zh"] = ISSUE_DISPLAY_ZH[issue_code]
        item["comment"] = comment.strip()
        item["reviewer"] = item.get("reviewer") or "human_reviewer"
        item["review_time"] = now_iso()
        self.persist(f"save:{image_name}")

    def persist(self, reason: str) -> None:
        rows = [dict(item) for item in self.items]
        fieldnames = [
            "image_name",
            "split",
            "image_path",
            "mask_path",
            "overlay_path",
            "foreground_ratio",
            "foreground_pixel_count",
            "mask_unique_values",
            "source_mask_unique_values",
            "empty_mask",
            "full_mask",
            "size_match",
            "conversion_notes",
            "source_image_path",
            "source_mask_path",
            "review_status",
            "decision_code",
            "decision_display_zh",
            "issue_code",
            "issue_display_zh",
            "comment",
            "reviewer",
            "review_time",
        ]
        atomic_write_csv(self.decisions_csv, rows, fieldnames)
        atomic_write_json(self.decisions_json, {"generated_at": now_iso(), "reason": reason, "items": rows})
        summary = self.compute_summary()
        atomic_write_json(self.summary_json, summary)
        gate_text = self.render_gate_report(summary)
        atomic_write_text(self.gate_report, gate_text)
        atomic_write_text(self.closure_report, self.render_closure_report(summary))
        atomic_write_text(self.status_yaml, self.render_status_yaml(summary))

    def compute_summary(self) -> dict[str, Any]:
        reviewed = [item for item in self.items if item.get("review_status") == "reviewed"]
        total = len(self.items)
        reviewed_count = len(reviewed)
        decision_counts = Counter(item.get("decision_code", "") for item in reviewed)
        issue_counts = Counter(item.get("issue_code", "") for item in reviewed)
        serious_issue_count = sum(
            1
            for item in reviewed
            if item.get("decision_code") in {"SEG_MASK_NEEDS_FIX", "SEG_MASK_REJECT"}
            or item.get("issue_code") in SERIOUS_ISSUES
        )
        serious_issue_ratio = serious_issue_count / reviewed_count if reviewed_count else None
        accepted = decision_counts.get("SEG_MASK_ACCEPT", 0)
        needs_fix = decision_counts.get("SEG_MASK_NEEDS_FIX", 0)
        unsure = decision_counts.get("SEG_MASK_UNSURE", 0)
        rejected = decision_counts.get("SEG_MASK_REJECT", 0)
        accept_ratio = accepted / total if total else 0.0
        needs_fix_ratio = needs_fix / total if total else 0.0
        unsure_ratio = unsure / total if total else 0.0
        empty_mask_count = sum(1 for item in self.items if item.get("empty_mask") == "true")
        full_mask_count = sum(1 for item in self.items if item.get("full_mask") == "true")
        size_mismatch_count = sum(1 for item in self.items if item.get("size_match") != "true")
        if reviewed_count < total:
            gate = "PENDING"
            training_allowed = False
            next_action = "Continue visual QA. Training remains forbidden."
        elif (
            accept_ratio >= self.thresholds.accept_ratio_min
            and needs_fix_ratio <= self.thresholds.needs_fix_ratio_max
            and unsure_ratio <= self.thresholds.unsure_ratio_max
            and rejected <= self.thresholds.rejected_max
            and (serious_issue_ratio or 0.0) <= self.thresholds.serious_issue_ratio_max
            and issue_counts.get("mask_misaligned", 0) <= self.thresholds.mask_misaligned_max
            and empty_mask_count == 0
            and full_mask_count == 0
            and size_mismatch_count == 0
        ):
            gate = "PASS"
            training_allowed = True
            next_action = "May enter segmentation short-experiment training gate; actual training is a separate decision."
        else:
            gate = "FAIL"
            training_allowed = False
            next_action = "Do not train. Correct masks or conversion policy and rerun visual QA gate."
        return {
            "generated_at": now_iso(),
            "dataset_version": DATASET_VERSION,
            "total_items": total,
            "reviewed": reviewed_count,
            "unreviewed": total - reviewed_count,
            "accepted": accepted,
            "needs_fix": needs_fix,
            "unsure": unsure,
            "rejected": rejected,
            "mask_too_large_count": issue_counts.get("mask_too_large", 0),
            "mask_too_small_count": issue_counts.get("mask_too_small", 0),
            "lesion_missing_count": issue_counts.get("lesion_missing", 0),
            "noise_texture_included_count": issue_counts.get("noise_texture_included", 0),
            "background_included_count": issue_counts.get("background_included", 0),
            "mask_misaligned_count": issue_counts.get("mask_misaligned", 0),
            "foreground_ratio_too_low_count": issue_counts.get("foreground_ratio_too_low", 0),
            "foreground_ratio_too_high_count": issue_counts.get("foreground_ratio_too_high", 0),
            "serious_issue_count": serious_issue_count,
            "serious_issue_ratio": serious_issue_ratio,
            "empty_mask_count": empty_mask_count,
            "full_mask_count": full_mask_count,
            "size_mismatch_count": size_mismatch_count,
            "decision_counts": dict(decision_counts),
            "issue_counts": dict(issue_counts),
            "gate_thresholds": self.thresholds.__dict__,
            "visual_qa_gate": gate,
            "segmentation_training_allowed": training_allowed,
            "next_action": next_action,
            "boundaries": {
                "training_executed": False,
                "new_weights_generated": False,
                "original_images_modified": False,
                "original_yolo_labels_overwritten": False,
                "backend_modified": False,
                "env_modified": False,
                "bbox_issue_types_are_segmentation_classes": False,
            },
        }

    def render_gate_report(self, summary: dict[str, Any]) -> str:
        lines = [
            "# UAV BLB Segmentation 408 v1 Visual QA Gate Report",
            "",
            "## Boundary",
            "",
            "- training_executed: `NO`",
            "- new_weights_generated: `NO`",
            "- original_images_modified: `NO`",
            "- original_yolo_labels_overwritten: `NO`",
            "- backend_modified: `NO`",
            "- env_modified: `NO`",
            "",
            "## Summary",
            "",
        ]
        for key in (
            "total_items",
            "reviewed",
            "accepted",
            "needs_fix",
            "unsure",
            "rejected",
            "mask_too_large_count",
            "mask_too_small_count",
            "lesion_missing_count",
            "noise_texture_included_count",
            "background_included_count",
            "mask_misaligned_count",
            "foreground_ratio_too_low_count",
            "foreground_ratio_too_high_count",
            "serious_issue_count",
            "serious_issue_ratio",
            "visual_qa_gate",
            "segmentation_training_allowed",
        ):
            lines.append(f"- {key}: `{summary[key]}`")
        lines.extend(["", f"- next_action: {summary['next_action']}", "", "## Issue Counts", ""])
        if summary["issue_counts"]:
            for code, count in sorted(summary["issue_counts"].items()):
                lines.append(f"- `{code}`: `{count}`")
        else:
            lines.append("- No reviewed issue counts yet.")
        return "\n".join(lines) + "\n"

    def render_closure_report(self, summary: dict[str, Any]) -> str:
        return self.render_gate_report(summary).replace("Gate Report", "Closure Report")

    def render_status_yaml(self, summary: dict[str, Any]) -> str:
        stage = "VISUAL_QA_PASS" if summary["visual_qa_gate"] == "PASS" else "VISUAL_QA_IN_PROGRESS_OR_FAILED"
        return f"""segmentation_route_stage: {stage}
bbox_route_status: BLOCKED
derived_dataset_path: {DATASET_ROOT}
conversion_status: PASS
visual_qa_required: true
visual_qa_gate: {summary['visual_qa_gate']}
visual_qa_total: {summary['total_items']}
visual_qa_reviewed: {summary['reviewed']}
accepted: {summary['accepted']}
needs_fix: {summary['needs_fix']}
unsure: {summary['unsure']}
rejected: {summary['rejected']}
serious_issue_ratio: {summary['serious_issue_ratio']}
segmentation_training_allowed: {str(summary['segmentation_training_allowed']).lower()}
original_images_modified: false
original_labels_modified: false
weights_modified: false
backend_modified: false
env_modified: false
next_allowed_stage: {"SEGMENTATION_SHORT_EXPERIMENT_TRAINING_GATE" if summary['visual_qa_gate'] == "PASS" else "MASK_CORRECTION_OR_VISUAL_QA_CONTINUE"}
notes:
  - visual QA decisions must come from real human review
  - do not train until visual_qa_gate is PASS and a separate training gate is started
"""


class SegVisualQAApp:
    def __init__(self, store: SegVisualQAStore) -> None:
        self.store = store
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("1450x920+40+40")
        self.status_filter_var = tk.StringVar(value="unreviewed")
        self.decision_var = tk.StringVar(value="")
        self.issue_var = tk.StringVar(value="")
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
        header.columnconfigure(3, weight=1)
        ttk.Label(header, text=APP_TITLE, font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self.summary_var, justify="right").grid(row=0, column=3, sticky="e")
        ttk.Label(header, textvariable=self.item_var, justify="left").grid(row=1, column=0, columnspan=4, sticky="ew")
        self.preview_label = ttk.Label(left, anchor="center")
        self.preview_label.grid(row=1, column=0, sticky="nsew")
        ttk.Label(left, textvariable=self.path_var, foreground="#555", wraplength=980).grid(row=2, column=0, sticky="ew")

        right = ttk.Frame(self.root, padding=10, width=430)
        right.grid(row=0, column=1, sticky="ns")
        right.columnconfigure(0, weight=1)
        ttk.Label(right, text="Visual QA 操作", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(right, text="筛选").grid(row=1, column=0, sticky="w", pady=(10, 0))
        filter_combo = ttk.Combobox(right, textvariable=self.status_filter_var, values=["unreviewed", "reviewed", "all"], state="readonly")
        filter_combo.grid(row=2, column=0, sticky="ew")
        filter_combo.bind("<<ComboboxSelected>>", lambda _: self.refresh())
        ttk.Label(right, text="审核结论").grid(row=3, column=0, sticky="w", pady=(10, 0))
        ttk.Combobox(right, textvariable=self.decision_var, values=list(DECISION_CODE_BY_DISPLAY), state="readonly").grid(row=4, column=0, sticky="ew")
        ttk.Label(right, text="问题类型").grid(row=5, column=0, sticky="w", pady=(10, 0))
        ttk.Combobox(right, textvariable=self.issue_var, values=list(ISSUE_CODE_BY_DISPLAY), state="readonly").grid(row=6, column=0, sticky="ew")
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
        ttk.Label(right, text=GUIDE_TEXT, wraplength=400, justify="left").grid(row=14, column=0, sticky="ew")

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
        self.root.bind("/", lambda event: self.focus_notes() if not self.is_text_focus() else None)
        self.root.bind("<Escape>", lambda event: self.root.focus_set())

    def is_text_focus(self) -> bool:
        return self.root.focus_get() is self.notes

    def focus_notes(self) -> str:
        self.notes.focus_set()
        return "break"

    def decision_code_from_ui(self) -> str:
        value = self.decision_var.get().strip()
        return DECISION_CODE_BY_DISPLAY.get(value, value)

    def issue_code_from_ui(self) -> str:
        value = self.issue_var.get().strip()
        return ISSUE_CODE_BY_DISPLAY.get(value, value)

    def select_hotkey(self, key: str) -> str:
        decision, issue, comment = HOTKEYS[key]
        self.decision_var.set(DECISION_DISPLAY_ZH[decision])
        self.issue_var.set(ISSUE_DISPLAY_ZH[issue])
        self.append_comment(comment)
        return "break"

    def append_comment(self, text: str) -> None:
        current = self.notes.get("1.0", "end-1c").strip()
        if text in current:
            return
        self.notes.insert("end" if current else "1.0", ("\n" if current else "") + text)

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
            f"reviewed {summary['reviewed']}/{summary['total_items']}\n"
            f"gate {summary['visual_qa_gate']} | serious ratio {ratio_text} | training_allowed={summary['segmentation_training_allowed']}"
        )

    def current_item(self) -> dict[str, Any] | None:
        return self.filtered[self.index] if self.filtered else None

    def show_current(self) -> None:
        item = self.current_item()
        if not item:
            self.item_var.set("No items in current filter.")
            self.path_var.set("")
            self.preview_label.configure(image="", text="")
            return
        self.decision_var.set(DECISION_DISPLAY_ZH.get(item.get("decision_code", ""), item.get("decision_code", "")))
        self.issue_var.set(ISSUE_DISPLAY_ZH.get(item.get("issue_code", ""), item.get("issue_code", "")))
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", item.get("comment", ""))
        self.item_var.set(
            f"{self.index + 1}/{len(self.filtered)} | {item['image_name']} | split={item['split']} | status={item['review_status']}\n"
            f"fg_ratio={item['foreground_ratio']} | fg_pixels={item['foreground_pixel_count']} | values={item['mask_unique_values']} | notes={item['conversion_notes']}"
        )
        self.path_var.set(f"overlay={item['overlay_path']}\nimage={item['image_path']} | mask={item['mask_path']}")
        if not PILLOW_AVAILABLE:
            self.preview_label.configure(image="", text="Pillow unavailable")
            return
        try:
            img = Image.open(self.store.overlay_path_for(item)).convert("RGB")
        except OSError as exc:
            self.preview_label.configure(image="", text=f"Preview unavailable: {exc}")
            return
        img.thumbnail((1000, 820))
        self.preview_cache = ImageTk.PhotoImage(img)
        self.preview_label.configure(image=self.preview_cache, text="")

    def open_current_image(self) -> str:
        item = self.current_item()
        if item:
            try:
                os.startfile(self.store.overlay_path_for(item))  # type: ignore[attr-defined]
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
                item["image_name"],
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
    store = SegVisualQAStore()
    summary = store.compute_summary()
    return {
        "generated_at": now_iso(),
        "script": rel(Path(__file__).resolve()),
        "items": len(store.items),
        "overlays_exist": all(store.overlay_path_for(item).exists() for item in store.items),
        "decisions_output_csv": DECISIONS_CSV,
        "summary_output_json": SUMMARY_JSON,
        "gate_report": GATE_REPORT,
        "initial_gate": summary["visual_qa_gate"],
        "initial_segmentation_training_allowed": summary["segmentation_training_allowed"],
        "hotkey_1_to_8_enabled": True,
        "chinese_options_enabled": True,
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
    md = "\n".join(
        [
            "# UAV BLB Segmentation 408 v1 Visual QA Launcher Self-test",
            "",
            f"- items: `{payload['items']}`",
            f"- overlays_exist: `{payload['overlays_exist']}`",
            f"- initial_gate: `{payload['initial_gate']}`",
            f"- initial_segmentation_training_allowed: `{payload['initial_segmentation_training_allowed']}`",
            "- training_executed: `NO`",
            "- new_weights_generated: `NO`",
            "- original_images_modified: `NO`",
            "- original_yolo_labels_overwritten: `NO`",
            "- backend_modified: `NO`",
            "- env_modified: `NO`",
            "",
            "Self-test does not create visual QA decisions.",
        ]
    )
    atomic_write_text(resolve_path(SELFTEST_MD), md + "\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch UAV BLB segmentation visual QA gate UI.")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        write_selftest()
        return 0
    store = SegVisualQAStore()
    app = SegVisualQAApp(store)
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
