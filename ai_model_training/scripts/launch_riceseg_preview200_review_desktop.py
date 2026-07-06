"""Launch a Tkinter desktop review tool for RiceSeg preview_200 manual audit."""

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


APP_TITLE = "RiceSeg preview_200 病斑框人工审核台"
LOGGER_NAME = "riceseg_preview200_review"
ITEMS_CSV = "reports/riceseg_preview_200_manual_review_items.csv"
DECISIONS_CSV = "reports/riceseg_preview_200_manual_review_decisions.csv"
DECISIONS_JSON = "reports/riceseg_preview_200_manual_review_decisions.json"
SUMMARY_JSON = "reports/riceseg_preview_200_manual_review_summary.json"
GATE_REPORT_MD = "reports/riceseg_preview_200_manual_review_gate_report.md"
LOG_PATH = "reports/riceseg_preview_200_review_desktop.log"

ISSUES = [
    ("ok", "正常"),
    ("box_misaligned", "框位置错误"),
    ("whole_leaf_box", "整叶框"),
    ("irrelevant_box", "无关框"),
    ("over_fragmented", "过度碎片化"),
    ("missing_lesion", "漏病斑"),
    ("mask_noise", "mask 噪声"),
    ("image_mask_mismatch", "图像与 mask 不匹配"),
    ("other", "其他"),
]
ISSUE_LABELS = {code: label for code, label in ISSUES}
ISSUE_SHORTCUTS = {
    "1": "ok",
    "2": "box_misaligned",
    "3": "whole_leaf_box",
    "4": "irrelevant_box",
    "5": "over_fragmented",
    "6": "missing_lesion",
    "7": "mask_noise",
    "8": "image_mask_mismatch",
    "9": "other",
}
STATUS_LABELS = {
    "unreviewed": "未审核",
    "reviewed": "已审核",
}
CLASS_LABELS = {
    "all": "全部类别",
    "bacterial_blight": "白叶枯病 bacterial_blight",
    "blast": "稻瘟病 blast",
    "brown_spot": "褐斑病 brown_spot",
    "tungro": "东格鲁病 tungro",
}
GATE_LABELS = {
    "PENDING": "待审核",
    "PASS": "通过",
    "WARNING": "警告",
    "FAIL": "不通过",
}


@dataclass(frozen=True)
class ReviewGuardConfig:
    app_title: str
    dataset_version: str
    items_source: str
    output_prefix: str
    preview_field_order: tuple[str, ...]
    required_image_substring: str
    required_preview_substring: str
    required_output_substring: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the RiceSeg preview_200 desktop review app.")
    parser.add_argument("--items-csv", default=ITEMS_CSV)
    parser.add_argument("--decisions-csv", default=DECISIONS_CSV)
    parser.add_argument("--decisions-json", default=DECISIONS_JSON)
    parser.add_argument("--summary-json", default=SUMMARY_JSON)
    parser.add_argument("--gate-report", default=GATE_REPORT_MD)
    parser.add_argument("--log-path", default=LOG_PATH)
    parser.add_argument("--app-title", default=APP_TITLE)
    parser.add_argument("--dataset-version", default="rice_phone_rgb_riceseg_preview_200")
    parser.add_argument("--output-prefix", default="reports/riceseg_preview_200_manual_review")
    parser.add_argument("--preview-field-order", default="visual_preview_path,new_visual_preview_path,old_visual_preview_path")
    parser.add_argument("--required-image-substring", default="")
    parser.add_argument("--required-preview-substring", default="")
    parser.add_argument("--required-output-substring", default="")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


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
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tmp_path.open("w", encoding=encoding, newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            raise RuntimeError(f"Failed to write temp file: {tmp_path}")
        tmp_path.replace(path)
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"Failed to replace output file: {path}")
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def atomic_write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tmp_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in fieldnames})
            handle.flush()
            os.fsync(handle.fileno())
        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            raise RuntimeError(f"Failed to write temp CSV: {tmp_path}")
        tmp_path.replace(path)
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"Failed to replace CSV: {path}")
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


class ReviewStore:
    def __init__(
        self,
        items_csv: Path,
        decisions_csv: Path,
        decisions_json: Path,
        summary_json: Path,
        gate_report_md: Path,
        logger: logging.Logger,
        guard: ReviewGuardConfig,
    ) -> None:
        self.items_csv = items_csv
        self.decisions_csv = decisions_csv
        self.decisions_json = decisions_json
        self.summary_json = summary_json
        self.gate_report_md = gate_report_md
        self.logger = logger
        self.guard = guard
        self.items: list[dict[str, Any]] = []
        self.item_by_id: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        items: list[dict[str, Any]] = []
        with self.items_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                item = {
                    "review_id": (row.get("review_id") or "").strip(),
                    "class_name": (row.get("class_name") or "").strip(),
                    "split": (row.get("split") or "").strip(),
                    "image_path": (row.get("image_path") or "").strip(),
                    "label_path": (row.get("label_path") or "").strip(),
                    "visual_preview_path": (row.get("visual_preview_path") or "").strip(),
                    "new_visual_preview_path": (row.get("new_visual_preview_path") or "").strip(),
                    "old_visual_preview_path": (row.get("old_visual_preview_path") or "").strip(),
                    "conversion_rule_version": (row.get("conversion_rule_version") or "").strip(),
                    "bbox_count": int(float(row.get("bbox_count") or 0)),
                    "selection_reason": (row.get("selection_reason") or "").strip(),
                    "review_status": "unreviewed",
                    "issue_type": "",
                    "reviewer_notes": "",
                    "reviewed_at": "",
                }
                items.append(item)
        self.items = items
        self.item_by_id = {item["review_id"]: item for item in items}
        self._validate_items_against_guard()
        self._overlay_existing_decisions()

    def _overlay_existing_decisions(self) -> None:
        if not self.decisions_csv.exists():
            return
        with self.decisions_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                review_id = (row.get("review_id") or "").strip()
                item = self.item_by_id.get(review_id)
                if not item:
                    continue
                issue_type = (row.get("issue_type") or "").strip()
                if issue_type in ISSUE_LABELS:
                    item["issue_type"] = issue_type
                item["review_status"] = (row.get("review_status") or "unreviewed").strip() or "unreviewed"
                item["reviewer_notes"] = (row.get("reviewer_notes") or "").strip()
                item["reviewed_at"] = (row.get("reviewed_at") or "").strip()

    def _validate_items_against_guard(self) -> None:
        errors: list[str] = []
        preview_fields = self.guard.preview_field_order
        for item in self.items:
            image_path = item.get("image_path", "")
            if self.guard.required_image_substring and self.guard.required_image_substring not in image_path:
                errors.append(
                    f"{item['review_id']}: image_path does not contain required substring "
                    f"'{self.guard.required_image_substring}'"
                )
            if self.guard.required_preview_substring:
                preview_candidates = [str(item.get(field, "")).strip() for field in preview_fields]
                if not any(self.guard.required_preview_substring in value for value in preview_candidates if value):
                    errors.append(
                        f"{item['review_id']}: preview paths do not contain required substring "
                        f"'{self.guard.required_preview_substring}'"
                    )
        if errors:
            raise RuntimeError("Guard validation failed for review items:\n" + "\n".join(errors[:10]))

    def _validate_output_paths(self) -> None:
        if not self.guard.required_output_substring:
            return
        output_paths = [
            str(self.decisions_csv).replace("\\", "/"),
            str(self.decisions_json).replace("\\", "/"),
            str(self.summary_json).replace("\\", "/"),
            str(self.gate_report_md).replace("\\", "/"),
        ]
        missing = [
            path for path in output_paths
            if self.guard.required_output_substring not in path
        ]
        if missing:
            raise RuntimeError(
                "Refusing to write review outputs because guarded output prefix was not matched: "
                + ", ".join(missing)
            )

    def list_items(self) -> list[dict[str, Any]]:
        return self.items

    def get_item(self, review_id: str) -> dict[str, Any]:
        item = self.item_by_id.get(review_id)
        if not item:
            raise KeyError(review_id)
        return item

    def get_preview_path(self, item: dict[str, Any]) -> Path | None:
        for field_name in self.guard.preview_field_order:
            preview_raw = (item.get(field_name) or "").strip()
            if not preview_raw:
                continue
            path = Path(preview_raw)
            if not path.is_absolute():
                path = repo_root() / path
            if path.exists():
                return path.resolve()
        return None

    def save_decision(self, review_id: str, issue_type: str, notes: str) -> None:
        if issue_type not in ISSUE_LABELS:
            raise ValueError("issue_type is required")
        self._validate_output_paths()
        item = self.get_item(review_id)
        item["issue_type"] = issue_type
        item["review_status"] = "reviewed"
        item["reviewer_notes"] = notes.strip()
        item["reviewed_at"] = now_iso()
        self.persist(f"save:{review_id}")

    def persist(self, reason: str) -> None:
        self._validate_output_paths()
        rows = []
        for item in self.items:
            rows.append(
                {
                    "review_id": item["review_id"],
                    "class_name": item["class_name"],
                    "split": item["split"],
                    "image_path": item["image_path"],
                    "label_path": item["label_path"],
                    "visual_preview_path": item["visual_preview_path"],
                    "new_visual_preview_path": item.get("new_visual_preview_path", ""),
                    "old_visual_preview_path": item.get("old_visual_preview_path", ""),
                    "conversion_rule_version": item.get("conversion_rule_version", ""),
                    "bbox_count": item["bbox_count"],
                    "selection_reason": item["selection_reason"],
                    "review_status": item["review_status"],
                    "issue_type": item["issue_type"],
                    "reviewer_notes": item["reviewer_notes"],
                    "reviewed_at": item["reviewed_at"],
                }
            )
        fieldnames = list(rows[0].keys()) if rows else [
            "review_id",
            "class_name",
            "split",
            "image_path",
            "label_path",
            "visual_preview_path",
            "new_visual_preview_path",
            "old_visual_preview_path",
            "conversion_rule_version",
            "bbox_count",
            "selection_reason",
            "review_status",
            "issue_type",
            "reviewer_notes",
            "reviewed_at",
        ]
        atomic_write_csv(self.decisions_csv, rows, fieldnames)
        atomic_write_json(self.decisions_json, {"generated_at": now_iso(), "reason": reason, "items": rows})
        summary = self.compute_summary()
        atomic_write_json(self.summary_json, summary)
        atomic_write_text(self.gate_report_md, self.render_gate_report(summary))

    def compute_summary(self) -> dict[str, Any]:
        reviewed = [item for item in self.items if item["review_status"] == "reviewed"]
        reviewed_count = len(reviewed)
        issue_items = [item for item in reviewed if item["issue_type"] and item["issue_type"] != "ok"]
        per_class = defaultdict(lambda: {"reviewed": 0, "ok": 0, "issue": 0, "issue_counts": Counter()})
        issue_counter: Counter[str] = Counter()
        for item in reviewed:
            stats = per_class[item["class_name"]]
            stats["reviewed"] += 1
            if item["issue_type"] == "ok":
                stats["ok"] += 1
            else:
                stats["issue"] += 1
                stats["issue_counts"][item["issue_type"]] += 1
                issue_counter[item["issue_type"]] += 1
        obvious_error_count = len(issue_items)
        ratio = (obvious_error_count / reviewed_count) if reviewed_count else None
        systemic_flags: list[str] = []
        for class_name, stats in per_class.items():
            threshold = max(2, int(round(stats["reviewed"] * 0.20)))
            for issue_name in ("whole_leaf_box", "irrelevant_box", "image_mask_mismatch", "box_misaligned"):
                if stats["issue_counts"].get(issue_name, 0) >= threshold and stats["reviewed"] > 0:
                    systemic_flags.append(f"{class_name}:{issue_name}")
        if reviewed_count < 80:
            gate = "PENDING"
            next_action = "Wait for at least 80 manual reviews across four classes before making a dataset expansion decision."
        elif ratio is not None and ratio > 0.20:
            gate = "FAIL"
            next_action = "Stop preview_500 expansion and analyze mask-to-bbox quality failures."
        elif ratio is not None and ratio <= 0.10 and not systemic_flags:
            gate = "PASS"
            next_action = "Manual quality looks acceptable; preview_500 expansion can be prepared behind a new gate."
        else:
            gate = "WARNING"
            next_action = "Adjust mask-to-bbox rules and regenerate a revised preview_200 before expansion."
        return {
            "generated_at": now_iso(),
            "dataset_version": self.guard.dataset_version,
            "review_items_source": self.guard.items_source,
            "output_prefix": self.guard.output_prefix,
            "total_review_items": len(self.items),
            "reviewed_count": reviewed_count,
            "unreviewed_count": len(self.items) - reviewed_count,
            "per_class_reviewed_count": {key: value["reviewed"] for key, value in per_class.items()},
            "per_class_ok_count": {key: value["ok"] for key, value in per_class.items()},
            "per_class_issue_count": {key: value["issue"] for key, value in per_class.items()},
            "issue_type_counts": dict(issue_counter),
            "obvious_error_count": obvious_error_count,
            "obvious_error_ratio": ratio,
            "systemic_flags": systemic_flags,
            "gate": gate,
            "next_action": next_action,
        }

    def render_gate_report(self, summary: dict[str, Any]) -> str:
        lines = [
            "# RiceSeg preview_200 Manual Review Gate Report",
            "",
            f"- dataset_version: `{summary['dataset_version']}`",
            f"- review_items_source: `{summary['review_items_source']}`",
            f"- output_prefix: `{summary['output_prefix']}`",
            f"- generated_at: `{summary['generated_at']}`",
            f"- total_review_items: `{summary['total_review_items']}`",
            f"- reviewed_count: `{summary['reviewed_count']}`",
            f"- unreviewed_count: `{summary['unreviewed_count']}`",
            f"- gate: `{summary['gate']}` ({GATE_LABELS.get(summary['gate'], summary['gate'])})",
            f"- obvious_error_count: `{summary['obvious_error_count']}`",
            f"- obvious_error_ratio: `{summary['obvious_error_ratio']}`",
            f"- systemic_flags: `{summary['systemic_flags']}`",
            f"- next_action: {summary['next_action']}",
            "",
            "## Issue Counts",
            "",
        ]
        issue_counts = summary.get("issue_type_counts", {})
        if issue_counts:
            for code, count in sorted(issue_counts.items()):
                lines.append(f"- `{code}` ({ISSUE_LABELS.get(code, code)}): `{count}`")
        else:
            lines.append("- No reviewed issue counts yet.")
        return "\n".join(lines) + "\n"


class ReviewApp:
    def __init__(self, store: ReviewStore, logger: logging.Logger) -> None:
        self.store = store
        self.logger = logger
        self.root = tk.Tk()
        self.root.title(self.store.guard.app_title)
        self.root.geometry("1380x920")
        self.class_filter_var = tk.StringVar(value="all")
        self.status_filter_var = tk.StringVar(value="all")
        self.selected_issue_var = tk.StringVar(value="")
        self.current_index = 0
        self.filtered_items: list[dict[str, Any]] = []
        self.preview_cache: ImageTk.PhotoImage | None = None
        self.status_text_var = tk.StringVar(value="")
        self.summary_text_var = tk.StringVar(value="")
        self.item_text_var = tk.StringVar(value="")
        self.path_text_var = tk.StringVar(value="")
        self.notes_text: tk.Text
        self.preview_label: ttk.Label
        self._build_ui()
        self._bind_shortcuts()
        self.refresh_filtered_items()

    def _build_ui(self) -> None:
        root = self.root
        root.columnconfigure(0, weight=3)
        root.columnconfigure(1, weight=2)
        root.rowconfigure(1, weight=1)

        header = ttk.Frame(root, padding=12)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(6, weight=1)

        ttk.Label(header, text=self.store.guard.app_title, font=("Microsoft YaHei UI", 16, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="类别筛选").grid(row=1, column=0, padx=(0, 6), sticky="w")
        class_combo = ttk.Combobox(
            header,
            textvariable=self.class_filter_var,
            values=list(CLASS_LABELS.keys()),
            state="readonly",
            width=18,
        )
        class_combo.grid(row=1, column=1, sticky="w")
        class_combo.bind("<<ComboboxSelected>>", lambda _: self.refresh_filtered_items())

        ttk.Label(header, text="状态筛选").grid(row=1, column=2, padx=(12, 6), sticky="w")
        status_combo = ttk.Combobox(
            header,
            textvariable=self.status_filter_var,
            values=["all", "unreviewed", "reviewed", "issue_only"],
            state="readonly",
            width=18,
        )
        status_combo.grid(row=1, column=3, sticky="w")
        status_combo.bind("<<ComboboxSelected>>", lambda _: self.refresh_filtered_items())

        ttk.Button(header, text="上一张", command=self.prev_item).grid(row=1, column=4, padx=(12, 6))
        ttk.Button(header, text="下一张", command=self.next_item).grid(row=1, column=5, padx=(0, 12))
        ttk.Label(header, textvariable=self.summary_text_var, justify="left").grid(row=0, column=6, rowspan=2, sticky="e")

        preview_frame = ttk.Frame(root, padding=(12, 0, 12, 12))
        preview_frame.grid(row=1, column=0, sticky="nsew")
        preview_frame.rowconfigure(1, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        ttk.Label(preview_frame, textvariable=self.item_text_var, justify="left").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.preview_label = ttk.Label(preview_frame, anchor="center")
        self.preview_label.grid(row=1, column=0, sticky="nsew")
        ttk.Label(preview_frame, textvariable=self.path_text_var, justify="left", wraplength=820).grid(row=2, column=0, sticky="w", pady=(8, 0))

        side = ttk.Frame(root, padding=(0, 0, 12, 12))
        side.grid(row=1, column=1, sticky="nsew")
        side.columnconfigure(0, weight=1)
        side.rowconfigure(3, weight=1)

        ttk.Label(side, textvariable=self.status_text_var, justify="left").grid(row=0, column=0, sticky="w")

        issue_frame = ttk.LabelFrame(side, text="问题类型", padding=8)
        issue_frame.grid(row=1, column=0, sticky="ew", pady=(8, 8))
        for index, (code, label) in enumerate(ISSUES):
            button = ttk.Button(issue_frame, text=f"{label} ({self._shortcut_for(code)})", command=lambda value=code: self.select_issue(value))
            button.grid(row=index // 2, column=index % 2, sticky="ew", padx=4, pady=4)
        issue_frame.columnconfigure(0, weight=1)
        issue_frame.columnconfigure(1, weight=1)

        notes_frame = ttk.LabelFrame(side, text="审核备注", padding=8)
        notes_frame.grid(row=2, column=0, sticky="nsew")
        notes_frame.rowconfigure(0, weight=1)
        notes_frame.columnconfigure(0, weight=1)
        self.notes_text = tk.Text(notes_frame, width=42, height=12, wrap="word")
        self.notes_text.grid(row=0, column=0, sticky="nsew")

        action_frame = ttk.Frame(side)
        action_frame.grid(row=3, column=0, sticky="sew", pady=(8, 0))
        ttk.Button(action_frame, text="保存", command=self.save_current).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(action_frame, text="保存并下一张", command=self.save_and_next).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(action_frame, text="打开预览图", command=self.open_preview).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(action_frame, text="打开图片文件夹", command=self.open_image_folder).grid(row=0, column=3)

    def _bind_shortcuts(self) -> None:
        for key, issue_type in ISSUE_SHORTCUTS.items():
            self.root.bind(key, lambda _event, value=issue_type: self.select_issue(value))
        self.root.bind("<Control-s>", lambda _event: self.save_current())
        self.root.bind("<Return>", lambda _event: self.save_and_next())
        self.root.bind("a", lambda _event: self.prev_item())
        self.root.bind("d", lambda _event: self.next_item())
        self.root.bind("o", lambda _event: self.open_preview())

    def _shortcut_for(self, issue_type: str) -> str:
        for key, value in ISSUE_SHORTCUTS.items():
            if value == issue_type:
                return key
        return "-"

    def refresh_filtered_items(self) -> None:
        class_filter = self.class_filter_var.get()
        status_filter = self.status_filter_var.get()
        items = self.store.list_items()
        filtered = []
        for item in items:
            if class_filter != "all" and item["class_name"] != class_filter:
                continue
            if status_filter == "unreviewed" and item["review_status"] != "unreviewed":
                continue
            if status_filter == "reviewed" and item["review_status"] != "reviewed":
                continue
            if status_filter == "issue_only" and item["issue_type"] in ("", "ok"):
                continue
            filtered.append(item)
        self.filtered_items = filtered
        self.current_index = min(self.current_index, max(0, len(filtered) - 1))
        self._refresh_summary()
        self._refresh_item_view()

    def _refresh_summary(self) -> None:
        summary = self.store.compute_summary()
        self.summary_text_var.set(
            "\n".join(
                [
                    f"Gate: {GATE_LABELS.get(summary['gate'], summary['gate'])}",
                    f"总样本: {summary['total_review_items']}",
                    f"已审核: {summary['reviewed_count']}",
                    f"未审核: {summary['unreviewed_count']}",
                ]
            )
        )

    def _refresh_item_view(self) -> None:
        if not self.filtered_items:
            self.item_text_var.set("当前筛选结果为空。")
            self.status_text_var.set("请调整筛选项。")
            self.path_text_var.set("")
            self.preview_label.configure(image="", text="无可显示样本")
            self.notes_text.delete("1.0", tk.END)
            return
        item = self.filtered_items[self.current_index]
        self.item_text_var.set(
            "\n".join(
                [
                    f"审核编号: {item['review_id']}",
                    f"类别: {CLASS_LABELS.get(item['class_name'], item['class_name'])}",
                    f"数据划分: {item['split']}",
                    f"标注框数量: {item['bbox_count']}",
                    f"抽样原因: {item['selection_reason']}",
                ]
            )
        )
        self.status_text_var.set(
            "\n".join(
                [
                    f"当前状态: {STATUS_LABELS.get(item['review_status'], item['review_status'])}",
                    f"当前问题: {ISSUE_LABELS.get(item['issue_type'], '未选择') if item['issue_type'] else '未选择'}",
                    f"当前审核集: {self.store.guard.dataset_version}",
                    "快捷键: 1-9 选择问题类型, Ctrl+S 保存, Enter 保存并下一张, A/D 切换",
                ]
            )
        )
        self.path_text_var.set(
            "\n".join(
                [
                    f"预览图: {(item.get('new_visual_preview_path') or item.get('visual_preview_path') or '').strip()}",
                    f"原图: {item['image_path']}",
                    f"标签: {item['label_path']}",
                ]
            )
        )
        self.selected_issue_var.set(item["issue_type"])
        self.notes_text.delete("1.0", tk.END)
        self.notes_text.insert("1.0", item["reviewer_notes"])
        self._load_preview(item)

    def _load_preview(self, item: dict[str, Any]) -> None:
        preview_path = self.store.get_preview_path(item)
        if not preview_path or not PILLOW_AVAILABLE:
            reason = "缺少 Pillow" if not PILLOW_AVAILABLE else "预览图不存在"
            self.preview_label.configure(image="", text=reason)
            self.preview_cache = None
            return
        image = Image.open(preview_path)
        image.thumbnail((820, 740))
        self.preview_cache = ImageTk.PhotoImage(image)
        self.preview_label.configure(image=self.preview_cache, text="")

    def current_item(self) -> dict[str, Any] | None:
        if not self.filtered_items:
            return None
        return self.filtered_items[self.current_index]

    def select_issue(self, issue_type: str) -> None:
        if issue_type not in ISSUE_LABELS:
            return
        self.selected_issue_var.set(issue_type)
        current = self.current_item()
        if current:
            self.status_text_var.set(
                "\n".join(
                    [
                        f"当前状态: {STATUS_LABELS.get(current['review_status'], current['review_status'])}",
                        f"当前问题: {ISSUE_LABELS.get(issue_type, issue_type)}",
                        f"当前审核集: {self.store.guard.dataset_version}",
                        "快捷键: 1-9 选择问题类型, Ctrl+S 保存, Enter 保存并下一张, A/D 切换",
                    ]
                )
            )

    def save_current(self) -> None:
        current = self.current_item()
        if not current:
            return
        issue_type = self.selected_issue_var.get()
        if issue_type not in ISSUE_LABELS:
            messagebox.showwarning("未选择问题类型", "请先选择一个问题类型。")
            return
        notes = self.notes_text.get("1.0", tk.END).strip()
        self.store.save_decision(current["review_id"], issue_type, notes)
        self.logger.info("Saved review decision for %s -> %s", current["review_id"], issue_type)
        self.refresh_filtered_items()
        messagebox.showinfo("保存成功", f"{current['review_id']} 已保存。")

    def save_and_next(self) -> None:
        if not self.current_item():
            return
        current_review_id = self.current_item()["review_id"]
        self.save_current()
        for index, item in enumerate(self.filtered_items):
            if item["review_id"] == current_review_id:
                self.current_index = min(index + 1, max(0, len(self.filtered_items) - 1))
                break
        self._refresh_item_view()

    def prev_item(self) -> None:
        if not self.filtered_items:
            return
        self.current_index = max(0, self.current_index - 1)
        self._refresh_item_view()

    def next_item(self) -> None:
        if not self.filtered_items:
            return
        self.current_index = min(len(self.filtered_items) - 1, self.current_index + 1)
        self._refresh_item_view()

    def open_preview(self) -> None:
        current = self.current_item()
        if not current:
            return
        preview_path = self.store.get_preview_path(current)
        if preview_path and preview_path.exists():
            os.startfile(str(preview_path))  # type: ignore[attr-defined]
        else:
            messagebox.showwarning("预览图缺失", "当前样本没有可打开的预览图。")

    def open_image_folder(self) -> None:
        current = self.current_item()
        if not current:
            return
        image_path = Path(current["image_path"])
        if not image_path.is_absolute():
            image_path = repo_root() / image_path
        folder = image_path.resolve().parent
        if folder.exists():
            os.startfile(str(folder))  # type: ignore[attr-defined]
        else:
            messagebox.showwarning("目录缺失", "原图目录不存在。")

    def run(self) -> None:
        self.root.mainloop()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logger = configure_logger(resolve_path(args.log_path))
    logger.info("Launching RiceSeg preview_200 review desktop app.")
    logger.info("project_root=%s", repo_root())
    logger.info("items_csv=%s", resolve_path(args.items_csv))
    logger.info("decisions_csv=%s", resolve_path(args.decisions_csv))
    logger.info("summary_json=%s", resolve_path(args.summary_json))
    logger.info("gate_report=%s", resolve_path(args.gate_report))
    try:
        guard = ReviewGuardConfig(
            app_title=args.app_title,
            dataset_version=args.dataset_version,
            items_source=args.items_csv,
            output_prefix=args.output_prefix,
            preview_field_order=tuple(part.strip() for part in args.preview_field_order.split(",") if part.strip()),
            required_image_substring=args.required_image_substring,
            required_preview_substring=args.required_preview_substring,
            required_output_substring=args.required_output_substring,
        )
        store = ReviewStore(
            items_csv=resolve_path(args.items_csv),
            decisions_csv=resolve_path(args.decisions_csv),
            decisions_json=resolve_path(args.decisions_json),
            summary_json=resolve_path(args.summary_json),
            gate_report_md=resolve_path(args.gate_report),
            logger=logger,
            guard=guard,
        )
        if args.self_test:
            summary = store.compute_summary()
            logger.info("Self-test summary: %s", json.dumps(summary, ensure_ascii=False))
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0
        # Only refresh persisted outputs on startup when an existing decisions file is already present.
        # This avoids creating a misleading 0/80 summary just by opening the revised review app.
        if store.decisions_csv.exists():
            store.persist("startup_bootstrap")
        app = ReviewApp(store, logger)
        app.run()
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.error("Desktop review app failed: %s", exc)
        logger.error(traceback.format_exc())
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
