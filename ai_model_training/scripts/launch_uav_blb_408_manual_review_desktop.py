"""Guarded desktop launcher for UAV BLB 408 manual review."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import traceback
from collections import Counter, defaultdict
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


APP_TITLE = "UAV BLB 408 manual review"
DATASET_VERSION = "uav_blb_408"
ITEMS_CSV = "reports/uav_blb_408_manual_review_items.csv"
DECISIONS_CSV = "reports/uav_blb_408_manual_review_decisions.csv"
DECISIONS_JSON = "reports/uav_blb_408_manual_review_decisions.json"
SUMMARY_JSON = "reports/uav_blb_408_manual_review_summary.json"
GATE_REPORT = "reports/uav_blb_408_manual_review_gate_report.md"
LOG_PATH = "reports/uav_blb_408_manual_review_desktop.log"
SELFTEST_JSON = "reports/uav_blb_408_manual_review_launcher_selftest.json"
SELFTEST_MD = "reports/uav_blb_408_manual_review_launcher_selftest.md"
OUTPUT_PREFIX = "reports/uav_blb_408_manual_review"
VISUAL_AUDIT_PREFIX = "uav_blb_408_manual_gate_visual_audit"
DATASET_SUBSTRING = "rice_uav_ms_blb_preview_1000"
FORBIDDEN_SUBSTRINGS = ("rice_phone", "riceseg", "crop_object", "rice_panicle")
BBOX_COLOR_PALETTE = [
    ("red", "bbox 1, 5, 9..."),
    ("blue", "bbox 2, 6, 10..."),
    ("green", "bbox 3, 7, 11..."),
    ("yellow", "bbox 4, 8, 12..."),
]
COMPACT_MODE = True
BBOX_COLOR_HELP_SHORT = "框颜色仅用于区分 bbox 序号，不代表类别；当前类别统一为 BLB。"
REVIEW_HELP_SHORT = (
    "标准无错误多光谱 BLB：图像可读，bbox 紧贴连续稳定疑似 BLB 冠层区域；"
    "不大面积覆盖背景/纹理，不重复重叠，不主要落在边缘截断区。"
    "伪彩颜色只作参考，不能只因颜色强烈判断为 BLB。"
)

ISSUES = [
    ("OK_STANDARD", "标准无误，可接受"),
    ("LARGE_BBOX_AREA", "bbox 过大，覆盖过多背景或多块区域"),
    ("SMALL_OR_MISSING_BBOX", "bbox 过小、漏框、只框到局部"),
    ("FRAGMENTED_PATCH", "病斑/疑似区域碎片化，需要复核"),
    ("MULTISPECTRAL_NOISE_TEXTURE", "多光谱伪彩噪声、纹理、反光或背景误检"),
    ("EDGE_CUT_OR_BLUR", "图像边缘截断、遮挡、模糊"),
    ("OVERLAP_DUPLICATE_BBOX", "重叠框、重复框"),
    ("UNUSABLE_SAMPLE", "严重不可用样本"),
]
ISSUE_LABELS = {code: label for code, label in ISSUES}
ISSUE_SHORTCUTS = {str(idx): code for idx, (code, _) in enumerate(ISSUES, start=1)}
REVIEW_OUTCOMES = {
    "ACCEPT": "OK_STANDARD",
    "REVIEW": "FRAGMENTED_PATCH",
    "FIX": "LARGE_BBOX_AREA",
    "REJECT": "UNUSABLE_SAMPLE",
}
ISSUE_TO_OUTCOME = {
    "OK_STANDARD": "ACCEPT",
    "LARGE_BBOX_AREA": "FIX",
    "SMALL_OR_MISSING_BBOX": "FIX",
    "FRAGMENTED_PATCH": "REVIEW",
    "MULTISPECTRAL_NOISE_TEXTURE": "REJECT",
    "EDGE_CUT_OR_BLUR": "REVIEW",
    "OVERLAP_DUPLICATE_BBOX": "FIX",
    "UNUSABLE_SAMPLE": "REJECT",
}
KEYBOARD_HELP = (
    "1=标准无误 OK_STANDARD；2=大框异常 LARGE_BBOX_AREA；3=小框/漏框 SMALL_OR_MISSING_BBOX；"
    "4=碎片化 FRAGMENTED_PATCH；5=多光谱噪声 MULTISPECTRAL_NOISE_TEXTURE；"
    "6=边缘/模糊 EDGE_CUT_OR_BLUR；7=重叠重复 OVERLAP_DUPLICATE_BBOX；8=不可用 UNUSABLE_SAMPLE；"
    "Space/Ctrl+Enter=保存并下一张；←/→=上一张/下一张；O=overlay/原图；B=打开大图；Esc=退出备注。"
)
SERIOUS_ISSUES = {
    "LARGE_BBOX_AREA",
    "SMALL_OR_MISSING_BBOX",
    "MULTISPECTRAL_NOISE_TEXTURE",
    "EDGE_CUT_OR_BLUR",
    "OVERLAP_DUPLICATE_BBOX",
    "UNUSABLE_SAMPLE",
    "box_misaligned",
    "box_too_large",
    "missing_bbox",
    "wrong_target",
    "bad_image",
}
ATTENTION_ISSUES = {"FRAGMENTED_PATCH", "EDGE_CUT_OR_BLUR", "box_too_small", "unclear", "blur"}
HOTKEY_DECISIONS = {
    "1": (
        "ACCEPT",
        "OK_STANDARD",
        "ACCEPT：多光谱伪彩图可读，bbox 较紧密地覆盖连续疑似 BLB 病斑/病株冠层区域，未见明显大框异常、重复重叠、边缘截断或噪声纹理误检。",
    ),
    "2": ("FIX", "LARGE_BBOX_AREA", "FIX：bbox 过大，覆盖过多背景或多块区域，需要修订框范围。"),
    "3": ("FIX", "SMALL_OR_MISSING_BBOX", "FIX：bbox 过小、疑似漏框或只框到局部，需要补框或调整。"),
    "4": ("REVIEW", "FRAGMENTED_PATCH", "REVIEW：疑似病斑呈零散碎片状，无法确定 bbox 应合并、拆分还是保留，需要复核。"),
    "5": ("REJECT", "MULTISPECTRAL_NOISE_TEXTURE", "REJECT：框选区域主要来自伪彩颜色、叶片纹理、反光、阴影、背景或传感器噪声，缺少稳定病斑形态。"),
    "6": ("REVIEW", "EDGE_CUT_OR_BLUR", "REVIEW：图像边缘截断、遮挡或模糊，无法稳定判断，需要复核。"),
    "7": ("FIX", "OVERLAP_DUPLICATE_BBOX", "FIX：存在重叠框或重复框，同一区域被多次框选，需要去重或合并。"),
    "8": ("REJECT", "UNUSABLE_SAMPLE", "REJECT：样本严重不可用，缺少有效审核或训练价值。"),
}


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


def configure_logger(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("uav_blb_408_manual_review")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(stream)
    logger.addHandler(file_handler)
    return logger


@dataclass(frozen=True)
class GuardConfig:
    dataset_version: str
    output_prefix: str
    dataset_substring: str
    visual_prefix: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch UAV BLB 408 guarded manual review desktop app.")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def forbidden_path_detected(value: str) -> bool:
    lower = value.replace("\\", "/").lower()
    return any(token in lower for token in FORBIDDEN_SUBSTRINGS)


class ReviewStore:
    def __init__(self, logger: logging.Logger, guard: GuardConfig) -> None:
        self.logger = logger
        self.guard = guard
        self.items_csv = resolve_path(ITEMS_CSV)
        self.decisions_csv = resolve_path(DECISIONS_CSV)
        self.decisions_json = resolve_path(DECISIONS_JSON)
        self.summary_json = resolve_path(SUMMARY_JSON)
        self.gate_report = resolve_path(GATE_REPORT)
        self.items: list[dict[str, Any]] = []
        self.item_by_id: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        rows: list[dict[str, Any]] = []
        with self.items_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                item = {key: (value or "").strip() for key, value in row.items()}
                item["bbox_count"] = int(float(item.get("bbox_count") or 0))
                item["review_status"] = item.get("review_status") or "unreviewed"
                item["issue_type"] = item.get("issue_type") or ""
                item["reviewer_notes"] = item.get("reviewer_notes") or ""
                item["reviewed_at"] = item.get("reviewed_at") or ""
                rows.append(item)
        self.items = rows
        self.item_by_id = {item["review_id"]: item for item in rows}
        self._validate_items_against_guard()
        self._overlay_existing_decisions()

    def _validate_items_against_guard(self) -> None:
        errors: list[str] = []
        for item in self.items:
            dataset_name = item.get("dataset_name", "")
            image_path = item.get("image_path", "")
            preview_path = item.get("visual_preview_path", "")
            all_paths = " ".join([image_path, preview_path, item.get("label_path", "")])
            if dataset_name not in {"uav_blb_408", "rice_uav_ms_blb_preview_1000"}:
                errors.append(f"{item.get('review_id')}: invalid dataset_name={dataset_name}")
            if self.guard.dataset_substring not in image_path:
                errors.append(f"{item.get('review_id')}: image_path is not UAV BLB 408 dataset path")
            if self.guard.visual_prefix not in preview_path:
                errors.append(f"{item.get('review_id')}: visual_preview_path is not UAV BLB 408 audit path")
            if forbidden_path_detected(all_paths):
                errors.append(f"{item.get('review_id')}: forbidden Phone/crop-object/rice-panicle path detected")
        if errors:
            raise RuntimeError("Guard validation failed:\n" + "\n".join(errors[:20]))

    def _validate_output_paths(self) -> None:
        expected = (repo_root() / self.guard.output_prefix).as_posix()
        for path in (self.decisions_csv, self.decisions_json, self.summary_json, self.gate_report):
            normalized = path.as_posix()
            if expected not in normalized:
                raise RuntimeError(f"Refusing to write outside guarded output prefix: {normalized}")
            if forbidden_path_detected(normalized):
                raise RuntimeError(f"Refusing to write to forbidden old review path: {normalized}")

    def _overlay_existing_decisions(self) -> None:
        if not self.decisions_csv.exists():
            return
        with self.decisions_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                item = self.item_by_id.get((row.get("review_id") or "").strip())
                if not item:
                    continue
                issue_type = (row.get("issue_type") or "").strip()
                if issue_type:
                    item["issue_type"] = issue_type
                item["review_status"] = (row.get("review_status") or "unreviewed").strip() or "unreviewed"
                item["reviewer_notes"] = (row.get("reviewer_notes") or "").strip()
                item["reviewed_at"] = (row.get("reviewed_at") or "").strip()

    def get_preview_path(self, item: dict[str, Any]) -> Path | None:
        raw = item.get("visual_preview_path", "")
        if not raw:
            return None
        path = Path(raw)
        if not path.is_absolute():
            path = repo_root() / path
        return path if path.exists() else None

    def get_image_path(self, item: dict[str, Any]) -> Path | None:
        raw = item.get("image_path", "")
        if not raw:
            return None
        path = Path(raw)
        if not path.is_absolute():
            path = repo_root() / path
        return path if path.exists() else None

    def get_label_path(self, item: dict[str, Any]) -> Path | None:
        raw = item.get("label_path", "")
        if not raw:
            return None
        path = Path(raw)
        if not path.is_absolute():
            path = repo_root() / path
        return path if path.exists() else None

    def save_decision(self, review_id: str, issue_type: str, notes: str) -> None:
        if issue_type not in ISSUE_LABELS:
            raise ValueError("issue_type is required")
        self._validate_output_paths()
        item = self.item_by_id[review_id]
        item["review_status"] = "reviewed"
        item["issue_type"] = issue_type
        item["reviewer_notes"] = notes.strip()
        item["reviewed_at"] = now_iso()
        self.persist(f"save:{review_id}")

    def persist(self, reason: str) -> None:
        self._validate_output_paths()
        rows = [dict(item) for item in self.items]
        fieldnames = [
            "review_id",
            "dataset_name",
            "dataset_root",
            "split",
            "image_name",
            "image_path",
            "label_path",
            "visual_preview_path",
            "bbox_count",
            "image_width",
            "image_height",
            "class_name",
            "selection_reason",
            "risk_tags",
            "source_from_ab_eval",
            "old_candidate_status",
            "review_status",
            "issue_type",
            "reviewer_notes",
            "reviewed_at",
        ]
        atomic_write_csv(self.decisions_csv, rows, fieldnames)
        atomic_write_json(self.decisions_json, {"generated_at": now_iso(), "reason": reason, "items": rows})
        summary = self.compute_summary()
        atomic_write_json(self.summary_json, summary)
        atomic_write_text(self.gate_report, self.render_gate_report(summary))
        self.logger.info("saved review decision batch: %s", reason)

    def compute_summary(self) -> dict[str, Any]:
        reviewed = [item for item in self.items if item.get("review_status") == "reviewed"]
        reviewed_count = len(reviewed)
        review_items_count = len(self.items)
        issue_counts = Counter(item.get("issue_type", "") for item in reviewed if item.get("issue_type"))
        serious_count = sum(issue_counts.get(issue, 0) for issue in SERIOUS_ISSUES)
        serious_ratio = serious_count / reviewed_count if reviewed_count else None
        split_issue_counts: dict[str, Counter[str]] = defaultdict(Counter)
        no_det_reviewed = [item for item in reviewed if "no_detection" in item.get("risk_tags", "")]
        no_det_serious = sum(1 for item in no_det_reviewed if item.get("issue_type") in SERIOUS_ISSUES)
        for item in reviewed:
            split_issue_counts[item.get("split", "")][item.get("issue_type", "")] += 1
        concentration_flags = []
        for issue in ("FRAGMENTED_PATCH", "EDGE_CUT_OR_BLUR", "unclear", "blur", "box_too_small", "label_noise", "over_fragmented"):
            count = issue_counts.get(issue, 0)
            if reviewed_count and count / reviewed_count > 0.15:
                concentration_flags.append(issue)
        val_test_serious = sum(
            1 for item in reviewed
            if item.get("split") in {"val", "test"} and item.get("issue_type") in SERIOUS_ISSUES
        )
        image_mismatch_count = issue_counts.get("image_label_mismatch", 0)
        if reviewed_count < review_items_count:
            gate = "PENDING"
            next_action = "Continue guarded manual review; training remains forbidden."
        elif serious_ratio is not None and (
            serious_ratio > 0.20
            or image_mismatch_count >= 3
            or (issue_counts.get("LARGE_BBOX_AREA", 0) + issue_counts.get("box_too_large", 0) + issue_counts.get("whole_leaf_or_background_box", 0)) / reviewed_count > 0.15
            or (issue_counts.get("SMALL_OR_MISSING_BBOX", 0) + issue_counts.get("missing_bbox", 0) + issue_counts.get("missing_blight_region", 0)) / reviewed_count > 0.15
            or (issue_counts.get("MULTISPECTRAL_NOISE_TEXTURE", 0) + issue_counts.get("wrong_target", 0)) / reviewed_count > 0.15
            or issue_counts.get("UNUSABLE_SAMPLE", 0) / reviewed_count > 0.15
        ):
            gate = "FAIL"
            next_action = "Pause UAV BLB training upgrade and analyze dataset quality failures."
        elif serious_ratio is not None and serious_ratio <= 0.10 and not concentration_flags and image_mismatch_count == 0 and val_test_serious == 0:
            gate = "PASS"
            next_action = "May enter controlled training planning only; direct training remains a separate decision."
        else:
            gate = "WARNING"
            next_action = "Prepare cleaned408_v2 or hard-case adjustment plan; do not train."
        return {
            "generated_at": now_iso(),
            "dataset_version": DATASET_VERSION,
            "output_prefix": OUTPUT_PREFIX,
            "review_items_count": review_items_count,
            "reviewed_count": reviewed_count,
            "unreviewed_count": review_items_count - reviewed_count,
            "issue_type_counts": dict(issue_counts),
            "serious_issue_types": sorted(SERIOUS_ISSUES),
            "attention_issue_types": sorted(ATTENTION_ISSUES),
            "serious_issue_count": serious_count,
            "serious_issue_ratio": serious_ratio,
            "concentration_flags": concentration_flags,
            "val_test_serious_issue_count": val_test_serious,
            "no_detection_reviewed_count": len(no_det_reviewed),
            "no_detection_serious_issue_count": no_det_serious,
            "split_issue_counts": {split: dict(counter) for split, counter in split_issue_counts.items()},
            "dataset_version_written": DATASET_VERSION,
            "output_prefix_written": OUTPUT_PREFIX,
            "reviewed_count_written": reviewed_count,
            "gate": gate,
            "training_allowed": False,
            "next_action": next_action,
        }

    def render_gate_report(self, summary: dict[str, Any]) -> str:
        lines = [
            "# UAV BLB 408 Manual Review Gate Report",
            "",
            f"- dataset_version: `{summary['dataset_version']}`",
            f"- output_prefix: `{summary['output_prefix']}`",
            f"- reviewed_count: `{summary['reviewed_count']}` / `{summary['review_items_count']}`",
            f"- serious_issue_count: `{summary['serious_issue_count']}`",
            f"- serious_issue_ratio: `{summary['serious_issue_ratio']}`",
            f"- concentration_flags: `{summary['concentration_flags']}`",
            f"- val_test_serious_issue_count: `{summary['val_test_serious_issue_count']}`",
            f"- no_detection_reviewed_count: `{summary['no_detection_reviewed_count']}`",
            f"- no_detection_serious_issue_count: `{summary['no_detection_serious_issue_count']}`",
            f"- gate: `{summary['gate']}`",
            f"- training_allowed: `{summary['training_allowed']}`",
            f"- next_action: {summary['next_action']}",
            "",
            "## Issue Counts",
            "",
        ]
        if summary["issue_type_counts"]:
            for code, count in sorted(summary["issue_type_counts"].items()):
                lines.append(f"- `{code}` ({ISSUE_LABELS.get(code, code)}): `{count}`")
        else:
            lines.append("- No reviewed issue counts yet.")
        return "\n".join(lines) + "\n"


class ReviewApp:
    def __init__(self, store: ReviewStore) -> None:
        self.store = store
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self._place_window()
        self.status_filter_var = tk.StringVar(value="unreviewed")
        self.display_mode_var = tk.StringVar(value="overlay")
        self.issue_var = tk.StringVar(value="")
        self.issue_display_var = tk.StringVar(value="")
        self.outcome_var = tk.StringVar(value="")
        self.summary_var = tk.StringVar(value="")
        self.item_var = tk.StringVar(value="")
        self.path_var = tk.StringVar(value="")
        self.bbox_info_var = tk.StringVar(value="")
        self.advanced_visible = tk.BooleanVar(value=not COMPACT_MODE)
        self.advanced_frame: ttk.LabelFrame | None = None
        self.advanced_body: ttk.Frame | None = None
        self.preview_cache: ImageTk.PhotoImage | None = None
        self.filtered: list[dict[str, Any]] = []
        self.index = 0
        self.notes: tk.Text
        self.preview_label: ttk.Label
        self._build()
        self._bind()
        self.refresh()
        self._bring_to_front()

    def _place_window(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(1480, max(1180, screen_w - 80))
        height = min(920, max(760, screen_h - 80))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(1100, 720)

    def _bring_to_front(self) -> None:
        self.root.update_idletasks()
        self.root.lift()
        self.root.focus_force()
        self.root.attributes("-topmost", True)
        self.root.after(1200, lambda: self.root.attributes("-topmost", False))

    def _build(self) -> None:
        self.root.columnconfigure(0, weight=3)
        self.root.columnconfigure(1, weight=2)
        self.root.rowconfigure(1, weight=1)
        header = ttk.Frame(self.root, padding=12)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(7, weight=1)
        ttk.Label(header, text=APP_TITLE, font=("Microsoft YaHei UI", 16, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="状态").grid(row=1, column=0, sticky="w")
        combo = ttk.Combobox(header, textvariable=self.status_filter_var, values=["all", "unreviewed", "reviewed", "issue_only"], state="readonly", width=16)
        combo.grid(row=1, column=1, padx=(6, 12), sticky="w")
        combo.bind("<<ComboboxSelected>>", lambda _: self.refresh())
        ttk.Button(header, text="上一张", command=self.prev_item).grid(row=1, column=2, padx=4)
        ttk.Button(header, text="下一张", command=self.next_item).grid(row=1, column=3, padx=4)
        ttk.Radiobutton(header, text="标注图", variable=self.display_mode_var, value="overlay", command=self.show_current).grid(row=1, column=4, padx=(12, 4))
        ttk.Radiobutton(header, text="原图", variable=self.display_mode_var, value="original", command=self.show_current).grid(row=1, column=5, padx=4)
        ttk.Button(header, text="打开大图", command=self.open_current_image).grid(row=1, column=6, padx=(8, 12))
        ttk.Label(header, textvariable=self.summary_var, justify="right").grid(row=0, column=7, rowspan=2, sticky="e")

        left = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        left.grid(row=1, column=0, sticky="nsew")
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)
        ttk.Label(left, textvariable=self.item_var, justify="left").grid(row=0, column=0, sticky="ew")
        self.preview_label = ttk.Label(left, anchor="center")
        self.preview_label.grid(row=1, column=0, sticky="nsew")
        ttk.Label(left, textvariable=self.path_var, justify="left").grid(row=2, column=0, sticky="ew")

        right = ttk.Frame(self.root, padding=(0, 0, 12, 12))
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)

        action_frame = ttk.LabelFrame(right, text="审核操作", padding=10)
        action_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        action_frame.columnconfigure(0, weight=1)
        ttk.Label(action_frame, text="审核结论").grid(row=0, column=0, sticky="w")
        outcome_combo = ttk.Combobox(
            action_frame,
            textvariable=self.outcome_var,
            values=list(REVIEW_OUTCOMES.keys()),
            state="readonly",
            width=24,
        )
        outcome_combo.grid(row=1, column=0, sticky="ew", pady=(2, 8))
        outcome_combo.bind("<<ComboboxSelected>>", lambda _: self.sync_issue_from_outcome())
        ttk.Label(action_frame, text="Issue type").grid(row=2, column=0, sticky="w")
        issue_combo = ttk.Combobox(
            action_frame,
            textvariable=self.issue_display_var,
            values=self.issue_display_values(),
            state="readonly",
            width=38,
        )
        issue_combo.grid(row=3, column=0, sticky="ew", pady=(2, 8))
        issue_combo.bind("<<ComboboxSelected>>", lambda _: self.sync_issue_from_display())
        ttk.Label(action_frame, text="Comment / reason").grid(row=4, column=0, sticky="w")
        self.notes = tk.Text(action_frame, height=5, wrap="word")
        self.notes.grid(row=5, column=0, sticky="ew", pady=(2, 8))
        button_row = ttk.Frame(action_frame)
        button_row.grid(row=6, column=0, sticky="ew")
        button_row.columnconfigure(0, weight=1)
        button_row.columnconfigure(1, weight=1)
        ttk.Button(button_row, text="保存当前结果", command=self.save_current).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(button_row, text="保存并下一张", command=self.save_and_next).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ttk.Label(action_frame, text=KEYBOARD_HELP, wraplength=500, justify="left").grid(row=7, column=0, sticky="ew", pady=(8, 0))

        help_frame = ttk.LabelFrame(right, text="简短审核辅助", padding=8)
        help_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        help_frame.columnconfigure(0, weight=1)
        ttk.Label(help_frame, text=BBOX_COLOR_HELP_SHORT, wraplength=500, justify="left").grid(row=0, column=0, sticky="ew")
        ttk.Label(help_frame, text=REVIEW_HELP_SHORT, wraplength=500, justify="left").grid(row=1, column=0, sticky="ew", pady=(6, 0))

        self.advanced_frame = ttk.LabelFrame(right, text="高级信息 / 调试信息（默认隐藏）", padding=8)
        self.advanced_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.advanced_frame.columnconfigure(0, weight=1)
        ttk.Checkbutton(
            self.advanced_frame,
            text="显示 bbox legend、bbox 坐标、risk/reason/source 等高级信息",
            variable=self.advanced_visible,
            command=self.update_advanced_visibility,
        ).grid(row=0, column=0, sticky="w")
        self.advanced_body = ttk.Frame(self.advanced_frame)
        self.advanced_body.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.advanced_body.columnconfigure(0, weight=1)
        legend_text = " | ".join(f"{name}: {meaning}" for name, meaning in BBOX_COLOR_PALETTE)
        ttk.Label(
            self.advanced_body,
            text=f"{legend_text}\ncolors = bbox index only, not class; class = BLB",
            wraplength=500,
            justify="left",
        ).grid(row=0, column=0, sticky="ew")
        ttk.Label(self.advanced_body, textvariable=self.bbox_info_var, wraplength=500, justify="left").grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.update_advanced_visibility()

    def _bind(self) -> None:
        self.root.bind("<Left>", lambda event: self.prev_item() if not self.is_text_focus() else None)
        self.root.bind("<Right>", lambda event: self.next_item() if not self.is_text_focus() else None)
        self.root.bind("n", lambda event: self.next_item() if not self.is_text_focus() else None)
        self.root.bind("N", lambda event: self.next_item() if not self.is_text_focus() else None)
        self.root.bind("p", lambda event: self.prev_item() if not self.is_text_focus() else None)
        self.root.bind("P", lambda event: self.prev_item() if not self.is_text_focus() else None)
        for key in HOTKEY_DECISIONS:
            self.root.bind(key, lambda event, value=key: self.select_hotkey(value) if not self.is_text_focus() else None)
        self.root.bind("a", lambda event: self.quick_save_hotkey("1") if not self.is_text_focus() else None)
        self.root.bind("A", lambda event: self.quick_save_hotkey("1") if not self.is_text_focus() else None)
        self.root.bind("r", lambda event: self.quick_save_hotkey("4") if not self.is_text_focus() else None)
        self.root.bind("R", lambda event: self.quick_save_hotkey("4") if not self.is_text_focus() else None)
        self.root.bind("f", lambda event: self.quick_save_hotkey("2") if not self.is_text_focus() else None)
        self.root.bind("F", lambda event: self.quick_save_hotkey("2") if not self.is_text_focus() else None)
        self.root.bind("x", lambda event: self.quick_save_hotkey("8") if not self.is_text_focus() else None)
        self.root.bind("X", lambda event: self.quick_save_hotkey("8") if not self.is_text_focus() else None)
        self.root.bind("o", lambda event: self.toggle_overlay_original() if not self.is_text_focus() else None)
        self.root.bind("O", lambda event: self.toggle_overlay_original() if not self.is_text_focus() else None)
        self.root.bind("b", lambda event: self.open_current_image() if not self.is_text_focus() else None)
        self.root.bind("B", lambda event: self.open_current_image() if not self.is_text_focus() else None)
        self.root.bind("/", lambda event: self.focus_notes() if not self.is_text_focus() else None)
        self.root.bind("<Escape>", lambda event: self.root.focus_set())
        self.root.bind("<space>", lambda event: self.save_and_next() if not self.is_text_focus() else None)
        self.root.bind("<Return>", lambda event: self.save_and_next() if not self.is_text_focus() else None)
        self.root.bind("<Control-s>", lambda _: self.save_current())
        self.root.bind("<Control-Return>", lambda _: self.save_and_next())
        self.root.bind("<Control-o>", lambda _: self.open_current_image())

    def is_text_focus(self) -> bool:
        return self.root.focus_get() is self.notes

    def focus_notes(self) -> str:
        self.notes.focus_set()
        return "break"

    def issue_display_values(self) -> list[str]:
        return [f"{code} / {label}" for code, label in ISSUES]

    def issue_to_display(self, issue_code: str) -> str:
        return f"{issue_code} / {ISSUE_LABELS.get(issue_code, issue_code)}" if issue_code else ""

    def sync_issue_from_display(self) -> None:
        display = self.issue_display_var.get()
        code = display.split(" / ", 1)[0].strip()
        if code in ISSUE_LABELS:
            self.set_issue(code)

    def sync_issue_from_outcome(self) -> None:
        outcome = self.outcome_var.get()
        issue_code = REVIEW_OUTCOMES.get(outcome)
        if issue_code:
            self.set_issue(issue_code)

    def set_issue(self, issue_code: str) -> None:
        self.issue_var.set(issue_code)
        self.issue_display_var.set(self.issue_to_display(issue_code))
        self.outcome_var.set(ISSUE_TO_OUTCOME.get(issue_code, "NEEDS_FIX") if issue_code else "")

    def select_outcome(self, outcome: str) -> None:
        issue_code = REVIEW_OUTCOMES[outcome]
        self.set_issue(issue_code)

    def quick_save(self, outcome: str) -> None:
        self.select_outcome(outcome)
        self.save_and_next()

    def select_hotkey(self, key: str) -> None:
        outcome, issue_code, comment = HOTKEY_DECISIONS[key]
        self.outcome_var.set(outcome)
        self.set_issue(issue_code)
        self.append_comment(comment)

    def quick_save_hotkey(self, key: str) -> None:
        self.select_hotkey(key)
        self.save_and_next()

    def append_comment(self, text: str) -> None:
        current = self.notes.get("1.0", "end-1c").strip()
        if text in current:
            return
        if current:
            self.notes.insert("end", "\n" + text)
        else:
            self.notes.insert("1.0", text)

    def toggle_overlay_original(self) -> None:
        self.display_mode_var.set("original" if self.display_mode_var.get() == "overlay" else "overlay")
        self.show_current()

    def update_advanced_visibility(self) -> None:
        if not self.advanced_body:
            return
        if self.advanced_visible.get():
            self.advanced_body.grid()
        else:
            self.advanced_body.grid_remove()

    def refresh(self) -> None:
        mode = self.status_filter_var.get()
        items = self.store.items
        if mode == "unreviewed":
            self.filtered = [item for item in items if item["review_status"] != "reviewed"]
        elif mode == "reviewed":
            self.filtered = [item for item in items if item["review_status"] == "reviewed"]
        elif mode == "issue_only":
            self.filtered = [item for item in items if item["review_status"] == "reviewed" and item["issue_type"] != "ok"]
        else:
            self.filtered = list(items)
        self.index = min(self.index, max(0, len(self.filtered) - 1))
        self.update_summary()
        self.show_current()

    def update_summary(self) -> None:
        summary = self.store.compute_summary()
        self.summary_var.set(
            f"reviewed {summary['reviewed_count']}/{summary['review_items_count']}\n"
            f"gate {summary['gate']} | serious ratio {summary['serious_issue_ratio']}"
        )

    def current_item(self) -> dict[str, Any] | None:
        if not self.filtered:
            return None
        return self.filtered[self.index]

    def show_current(self) -> None:
        item = self.current_item()
        if not item:
            self.item_var.set("No items in current filter.")
            self.preview_label.configure(image="", text="")
            return
        self.set_issue(item.get("issue_type") or "")
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", item.get("reviewer_notes", ""))
        self.item_var.set(
            f"{item['review_id']} | {self.index + 1}/{len(self.filtered)} | {item['image_name']}\n"
            f"split={item['split']} | bbox_count={item['bbox_count']} | class=BLB | status={item['review_status']}"
        )
        self.path_var.set(f"image={item['image_path']}\npreview={item['visual_preview_path']}")
        self.bbox_info_var.set(self.render_bbox_info(item))
        image_path = self.store.get_preview_path(item) if self.display_mode_var.get() == "overlay" else self.store.get_image_path(item)
        if not image_path or not PILLOW_AVAILABLE:
            self.preview_label.configure(image="", text="Preview unavailable")
            return
        img = Image.open(image_path)
        img.thumbnail((960, 780))
        self.preview_cache = ImageTk.PhotoImage(img)
        self.preview_label.configure(image=self.preview_cache, text="")

    def render_bbox_info(self, item: dict[str, Any]) -> str:
        rows = self.load_label_boxes(item)
        val_test_priority = "val_test_priority" in item.get("risk_tags", "")
        lines = [
            f"image_name = {item['image_name']}",
            f"split = {item['split']} | bbox_count = {item['bbox_count']} | class = BLB",
            "colors = bbox index only, not class",
            f"source_from_ab_eval = {item.get('source_from_ab_eval', '')} | val/test priority = {val_test_priority}",
            f"risk = {item.get('risk_tags', '')}",
            f"reason = {item.get('selection_reason', '')}",
        ]
        if rows:
            lines.append("bbox list: id class x y w h area")
            for row in rows[:8]:
                lines.append(
                    f"{row['bbox_id']} {row['class_id']} {row['class_name']} "
                    f"{row['x']:.4f} {row['y']:.4f} {row['w']:.4f} {row['h']:.4f} {row['area']:.4f}"
                )
            if len(rows) > 8:
                lines.append(f"... {len(rows) - 8} more boxes")
        else:
            lines.append("bbox list unavailable: label file could not be read")
        return "\n".join(lines)

    def load_label_boxes(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        label_path = self.store.get_label_path(item)
        if not label_path:
            return []
        rows: list[dict[str, Any]] = []
        try:
            lines = label_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return rows
        for idx, line in enumerate(lines, start=1):
            parts = line.split()
            if len(parts) != 5:
                continue
            try:
                class_id = int(float(parts[0]))
                x, y, w, h = [float(value) for value in parts[1:]]
            except ValueError:
                continue
            rows.append(
                {
                    "bbox_id": idx,
                    "class_id": class_id,
                    "class_name": "bacterial_leaf_blight" if class_id == 0 else f"class_{class_id}",
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                    "area": w * h,
                }
            )
        return rows

    def open_current_image(self) -> None:
        item = self.current_item()
        if not item:
            return
        path = self.store.get_preview_path(item) if self.display_mode_var.get() == "overlay" else self.store.get_image_path(item)
        if not path:
            messagebox.showwarning("Open image", "Current image path is unavailable.")
            return
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Open image failed", str(exc))

    def prev_item(self) -> None:
        if self.filtered:
            self.index = (self.index - 1) % len(self.filtered)
            self.show_current()

    def next_item(self) -> None:
        if self.filtered:
            self.index = (self.index + 1) % len(self.filtered)
            self.show_current()

    def save_and_next(self) -> None:
        if self.save_current():
            self.refresh()
            if self.filtered:
                self.index = min(self.index, len(self.filtered) - 1)
                self.show_current()

    def save_current(self) -> bool:
        item = self.current_item()
        if not item:
            return False
        self.sync_issue_from_display()
        try:
            self.store.save_decision(item["review_id"], self.issue_var.get(), self.notes.get("1.0", "end").strip())
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Save refused", str(exc))
            return False
        self.update_summary()
        return True

    def run(self) -> None:
        self.root.mainloop()


def load_review_items() -> list[dict[str, Any]]:
    path = resolve_path(ITEMS_CSV)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_selftest_payload() -> dict[str, Any]:
    rows = load_review_items()
    all_path_blob = " ".join(" ".join(str(value) for value in row.values()) for row in rows)
    no_phone = not any(token in all_path_blob.lower() for token in ("rice_phone", "riceseg"))
    no_crop_object = not any(token in all_path_blob.lower() for token in ("crop_object", "rice_panicle"))
    visual_ok = all(VISUAL_AUDIT_PREFIX in (row.get("visual_preview_path") or "") for row in rows)
    output_prefix_ok = OUTPUT_PREFIX == "reports/uav_blb_408_manual_review"
    dataset_ok = all((row.get("dataset_name") or "") in {"uav_blb_408", "rice_uav_ms_blb_preview_1000"} for row in rows)
    payload = {
        "generated_at": now_iso(),
        "dataset_version": DATASET_VERSION,
        "review_items_count": len(rows),
        "visual_audit_prefix": "reports/uav_blb_408_manual_gate_visual_audit",
        "output_prefix": OUTPUT_PREFIX,
        "dataset_name_ok": dataset_ok,
        "no_phone_path_detected": no_phone,
        "no_crop_object_path_detected": no_crop_object,
        "visual_audit_prefix_ok": visual_ok,
        "gate": "PENDING",
        "guards_enabled": True,
        "ui_help_text_enabled": True,
        "bbox_color_legend_enabled": True,
        "compact_mode": COMPACT_MODE,
        "issue_type_visible_in_initial_view": True,
        "short_review_help_visible": True,
        "advanced_bbox_legend_default_hidden": COMPACT_MODE,
        "advanced_bbox_list_default_hidden": COMPACT_MODE,
        "keyboard_shortcuts_enabled": True,
        "hotkey_1_to_8_enabled": True,
        "fragmented_patch_issue_added": "FRAGMENTED_PATCH" in ISSUE_LABELS,
        "multispectral_noise_issue_added": "MULTISPECTRAL_NOISE_TEXTURE" in ISSUE_LABELS,
        "hotkey_issue_types_are_manual_review_only": True,
        "keyboard_shortcuts": {
            "select_only": {
                "1": "ACCEPT/OK_STANDARD",
                "2": "FIX/LARGE_BBOX_AREA",
                "3": "FIX/SMALL_OR_MISSING_BBOX",
                "4": "REVIEW/FRAGMENTED_PATCH",
                "5": "REJECT/MULTISPECTRAL_NOISE_TEXTURE",
                "6": "REVIEW/EDGE_CUT_OR_BLUR",
                "7": "FIX/OVERLAP_DUPLICATE_BBOX",
                "8": "REJECT/UNUSABLE_SAMPLE",
            },
            "save_next": ["Space", "Enter outside comment", "Ctrl+Enter"],
            "quick_save_next": {"A": "ACCEPT/OK_STANDARD", "R": "REVIEW/FRAGMENTED_PATCH", "F": "FIX/LARGE_BBOX_AREA", "X": "REJECT/UNUSABLE_SAMPLE"},
            "navigation": {"N or Right": "next", "P or Left": "previous"},
            "display": {"O": "toggle overlay/original", "B": "open large image", "/": "focus comment", "Esc": "leave comment"},
        },
        "comment_focus_guard_enabled": True,
        "ctrl_z_undo_enabled": False,
        "shortcut_save_reuses_existing_save_function": True,
        "original_overlay_toggle_enabled": True,
        "open_large_image_enabled": True,
        "single_class_dataset": len({row.get("class_name") for row in rows}) == 1,
        "color_represents_class": False,
        "bbox_number_represents_index": True,
        "all_required_checks_passed": all([rows, no_phone, no_crop_object, visual_ok, output_prefix_ok, dataset_ok]),
    }
    return payload


def render_selftest_md(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# UAV BLB 408 Manual Review Launcher Self-Test",
            "",
            f"- review_items_count: `{payload['review_items_count']}`",
            f"- visual_audit_prefix: `{payload['visual_audit_prefix']}`",
            f"- output_prefix: `{payload['output_prefix']}`",
            f"- no_phone_path_detected: `{payload['no_phone_path_detected']}`",
            f"- no_crop_object_path_detected: `{payload['no_crop_object_path_detected']}`",
            f"- gate: `{payload['gate']}`",
            f"- guards_enabled: `{payload['guards_enabled']}`",
            f"- ui_help_text_enabled: `{payload['ui_help_text_enabled']}`",
            f"- bbox_color_legend_enabled: `{payload['bbox_color_legend_enabled']}`",
            f"- compact_mode: `{payload['compact_mode']}`",
            f"- issue_type_visible_in_initial_view: `{payload['issue_type_visible_in_initial_view']}`",
            f"- short_review_help_visible: `{payload['short_review_help_visible']}`",
            f"- advanced_bbox_legend_default_hidden: `{payload['advanced_bbox_legend_default_hidden']}`",
            f"- advanced_bbox_list_default_hidden: `{payload['advanced_bbox_list_default_hidden']}`",
            f"- keyboard_shortcuts_enabled: `{payload['keyboard_shortcuts_enabled']}`",
            f"- hotkey_1_to_8_enabled: `{payload['hotkey_1_to_8_enabled']}`",
            f"- fragmented_patch_issue_added: `{payload['fragmented_patch_issue_added']}`",
            f"- multispectral_noise_issue_added: `{payload['multispectral_noise_issue_added']}`",
            f"- hotkey_issue_types_are_manual_review_only: `{payload['hotkey_issue_types_are_manual_review_only']}`",
            f"- comment_focus_guard_enabled: `{payload['comment_focus_guard_enabled']}`",
            f"- ctrl_z_undo_enabled: `{payload['ctrl_z_undo_enabled']}`",
            f"- shortcut_save_reuses_existing_save_function: `{payload['shortcut_save_reuses_existing_save_function']}`",
            f"- original_overlay_toggle_enabled: `{payload['original_overlay_toggle_enabled']}`",
            f"- open_large_image_enabled: `{payload['open_large_image_enabled']}`",
            f"- single_class_dataset: `{payload['single_class_dataset']}`",
            f"- color_represents_class: `{payload['color_represents_class']}`",
            f"- bbox_number_represents_index: `{payload['bbox_number_represents_index']}`",
            f"- all_required_checks_passed: `{payload['all_required_checks_passed']}`",
            "",
        ]
    )


def run_self_test() -> int:
    payload = build_selftest_payload()
    atomic_write_json(resolve_path(SELFTEST_JSON), payload)
    atomic_write_text(resolve_path(SELFTEST_MD), render_selftest_md(payload))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["all_required_checks_passed"] else 1


def main() -> int:
    args = parse_args()
    if args.self_test:
        return run_self_test()
    try:
        logger = configure_logger(resolve_path(LOG_PATH))
        guard = GuardConfig(DATASET_VERSION, OUTPUT_PREFIX, DATASET_SUBSTRING, VISUAL_AUDIT_PREFIX)
        store = ReviewStore(logger, guard)
        logger.info("Launching %s with %d review items", APP_TITLE, len(store.items))
        ReviewApp(store).run()
        return 0
    except Exception as exc:  # noqa: BLE001
        message = "".join(traceback.format_exception(exc))
        log_path = resolve_path(LOG_PATH)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("\n[LAUNCH_ERROR]\n")
            handle.write(message)
            handle.write("\n")
        print(message, file=sys.stderr)
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("UAV BLB 408 manual review failed to open", message)
            root.destroy()
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
