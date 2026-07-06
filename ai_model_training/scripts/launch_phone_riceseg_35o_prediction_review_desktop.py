from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import subprocess
import sys
import traceback
from collections import Counter
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


APP_TITLE = "Phone RiceSeg 35N 预测框人工复核台"
LOGGER_NAME = "phone_riceseg_35o_prediction_review"
ISSUE_TYPES = [
    "pred_ok",
    "pred_no_detection",
    "pred_partial_detection",
    "pred_overbox",
    "pred_underbox",
    "pred_wrong_class",
    "pred_background_fp",
    "pred_duplicate_boxes",
    "pred_too_many_boxes",
    "pred_low_conf_uncertain",
    "pred_gt_label_questionable",
    "pred_uncertain",
    "pred_other",
]
ISSUE_SHORTCUTS = {
    "1": "pred_ok",
    "2": "pred_no_detection",
    "3": "pred_partial_detection",
    "4": "pred_overbox",
    "5": "pred_underbox",
    "6": "pred_wrong_class",
    "7": "pred_background_fp",
    "8": "pred_duplicate_boxes",
    "9": "pred_too_many_boxes",
    "0": "pred_low_conf_uncertain",
}
ISSUE_LABELS = {
    "pred_ok": "预测正常",
    "pred_no_detection": "无检测",
    "pred_partial_detection": "部分检测",
    "pred_overbox": "框过大",
    "pred_underbox": "框过小",
    "pred_wrong_class": "类别错误",
    "pred_background_fp": "背景误检",
    "pred_duplicate_boxes": "重复框",
    "pred_too_many_boxes": "框过多",
    "pred_low_conf_uncertain": "低置信不确定",
    "pred_gt_label_questionable": "真值标签可疑",
    "pred_uncertain": "人工不确定",
    "pred_other": "其他",
}
SERIOUS_ISSUES = {
    "pred_no_detection",
    "pred_wrong_class",
    "pred_background_fp",
    "pred_too_many_boxes",
    "pred_duplicate_boxes",
    "pred_overbox",
}
STATUS_OPTIONS = [
    ("all", "全部状态"),
    ("unreviewed", "未审核"),
    ("reviewed", "已审核"),
    ("issue_only", "只看问题样本"),
]
STATUS_LABELS = {
    "unreviewed": "未审核",
    "reviewed": "已审核",
}
GATE_LABELS = {
    "PENDING": "待审核",
    "PASS": "通过",
    "WARNING": "警告",
    "FAIL": "不通过",
}
FIELD_LABELS = {
    "review_id": "审核编号",
    "source_split": "数据划分",
    "class_name": "真值类别",
    "image_name": "图片名",
    "predicted_box_count_conf025": "预测框数量",
    "predicted_classes_conf025": "预测类别",
    "max_confidence_conf025": "最高置信度",
    "avg_confidence_conf025": "平均置信度",
    "no_detection_conf025": "无检测",
    "selection_reason": "抽样原因",
    "risk_tags": "风险标签",
    "image_path": "原图路径",
    "label_path": "标签路径",
    "prediction_visual_path": "预测叠加图",
    "ground_truth_visual_path": "真值叠加图",
    "side_by_side_visual_path": "并排对比图",
    "review_status": "审核状态",
    "issue_type": "问题类型",
    "reviewer_notes": "审核备注",
    "reviewed_at": "审核时间",
}

REVIEW_ITEMS_CSV = "reports/phone_riceseg_35o_prediction_review_items.csv"
REVIEW_ITEMS_JSON = "reports/phone_riceseg_35o_prediction_review_items.json"
DECISIONS_CSV = "reports/phone_riceseg_35o_prediction_review_decisions.csv"
DECISIONS_JSON = "reports/phone_riceseg_35o_prediction_review_decisions.json"
SUMMARY_JSON = "reports/phone_riceseg_35o_prediction_review_summary.json"
GATE_REPORT_MD = "reports/phone_riceseg_35o_prediction_review_gate_report.md"
SELFTEST_JSON = "reports/phone_riceseg_35o_prediction_review_launcher_selftest.json"
SELFTEST_MD = "reports/phone_riceseg_35o_prediction_review_launcher_selftest.md"
LOG_PATH = "reports/phone_riceseg_35o_prediction_review_desktop.log"
REQUIRED_IMAGE_SUBSTRING = "phone_riceseg_v35m_holdout_applied"
REQUIRED_PREVIEW_SUBSTRING = "phone_riceseg_35o_prediction_visual_audit"
REQUIRED_OUTPUT_SUBSTRING = "reports/phone_riceseg_35o_prediction_review"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the guarded 35O prediction review desktop app.")
    parser.add_argument("--self-test", action="store_true")
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


def atomic_write_text(path: Path, content: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tmp.open("w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if not tmp.exists() or tmp.stat().st_size == 0:
            raise RuntimeError(f"temporary file write failed: {tmp}")
        tmp.replace(path)
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
    tmp = path.with_name(path.name + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tmp.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in fieldnames})
            handle.flush()
            os.fsync(handle.fileno())
        if not tmp.exists() or tmp.stat().st_size == 0:
            raise RuntimeError(f"temporary csv write failed: {tmp}")
        tmp.replace(path)
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"atomic replace failed: {path}")
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


class ReviewStore:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.items_csv = resolve_path(REVIEW_ITEMS_CSV)
        self.items_json = resolve_path(REVIEW_ITEMS_JSON)
        self.decisions_csv = resolve_path(DECISIONS_CSV)
        self.decisions_json = resolve_path(DECISIONS_JSON)
        self.summary_json = resolve_path(SUMMARY_JSON)
        self.gate_report_md = resolve_path(GATE_REPORT_MD)
        self.output_prefix = str(resolve_path("reports/phone_riceseg_35o_prediction_review")).replace("\\", "/")
        self.items: list[dict[str, Any]] = []
        self.item_by_id: dict[str, dict[str, Any]] = {}
        self._load()

    def _guard_input_paths(self, row: dict[str, str]) -> None:
        image_path = (row.get("image_path") or "").replace("\\", "/")
        pred_path = (row.get("prediction_visual_path") or "").replace("\\", "/")
        if REQUIRED_IMAGE_SUBSTRING not in image_path:
            raise RuntimeError(f"image path guard failed: {image_path}")
        if REQUIRED_PREVIEW_SUBSTRING not in pred_path:
            raise RuntimeError(f"visual path guard failed: {pred_path}")

    def _guard_output_paths(self) -> None:
        for path in (self.decisions_csv, self.decisions_json, self.summary_json, self.gate_report_md):
            path_text = str(path).replace("\\", "/")
            if REQUIRED_OUTPUT_SUBSTRING not in path_text:
                raise RuntimeError(f"output path guard failed: {path_text}")
            if "uav" in path_text.lower():
                raise RuntimeError(f"unexpected UAV output path: {path_text}")
            if "preview_500" in path_text.lower():
                raise RuntimeError(f"unexpected old preview_500 output path: {path_text}")

    def _load(self) -> None:
        with self.items_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                self._guard_input_paths(row)
                item = {key: (value or "").strip() for key, value in row.items()}
                item["review_status"] = item.get("review_status") or "unreviewed"
                item["issue_type"] = item.get("issue_type") or ""
                item["reviewer_notes"] = item.get("reviewer_notes") or ""
                item["reviewed_at"] = item.get("reviewed_at") or ""
                self.items.append(item)
        self.item_by_id = {item["review_id"]: item for item in self.items}
        self._overlay_existing_decisions()
        self._bootstrap_outputs_if_missing()

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
                if issue_type in ISSUE_TYPES:
                    item["issue_type"] = issue_type
                item["review_status"] = (row.get("review_status") or "unreviewed").strip() or "unreviewed"
                item["reviewer_notes"] = (row.get("reviewer_notes") or "").strip()
                item["reviewed_at"] = (row.get("reviewed_at") or "").strip()

    def _bootstrap_outputs_if_missing(self) -> None:
        if not self.decisions_csv.exists() or not self.decisions_json.exists() or not self.summary_json.exists() or not self.gate_report_md.exists():
            self.persist("startup_bootstrap")

    def list_items(self) -> list[dict[str, Any]]:
        return self.items

    def get_item(self, review_id: str) -> dict[str, Any]:
        return self.item_by_id[review_id]

    def get_preview_path(self, item: dict[str, Any]) -> Path | None:
        preview = (item.get("side_by_side_visual_path") or item.get("prediction_visual_path") or "").strip()
        if not preview:
            return None
        path = Path(preview)
        if not path.is_absolute():
            path = repo_root() / path
        path = path.resolve()
        return path if path.exists() else None

    def save_decision(self, review_id: str, issue_type: str, notes: str) -> None:
        if issue_type not in ISSUE_TYPES:
            raise ValueError("issue_type is required")
        item = self.get_item(review_id)
        item["issue_type"] = issue_type
        item["review_status"] = "reviewed"
        item["reviewer_notes"] = notes.strip()
        item["reviewed_at"] = now_iso()
        self.persist(f"save:{review_id}")

    def _compute_gate(self, issue_counts: Counter[str], reviewed_count: int, total_count: int, split_counts: dict[str, dict[str, int]]) -> tuple[str, float | None, str]:
        if reviewed_count < total_count:
            return "PENDING", None, "manual review not complete"
        serious_issue_count = sum(issue_counts.get(issue, 0) for issue in SERIOUS_ISSUES)
        serious_ratio = serious_issue_count / reviewed_count if reviewed_count else 0.0
        holdout_no_detection = split_counts["holdout"].get("pred_no_detection", 0)
        holdout_reviewed = split_counts["holdout"]["reviewed"]
        holdout_disaster = holdout_reviewed > 0 and holdout_no_detection / holdout_reviewed > 0.5
        if serious_ratio > 0.25 or holdout_disaster:
            return "FAIL", round(serious_ratio, 6), "serious issue ratio too high or holdout visual performance unstable"
        if serious_ratio > 0.10:
            return "WARNING", round(serious_ratio, 6), "serious issue ratio above warning threshold"
        return "PASS", round(serious_ratio, 6), "serious issue ratio acceptable"

    def compute_summary(self) -> dict[str, Any]:
        reviewed = [item for item in self.items if item["review_status"] == "reviewed"]
        reviewed_count = len(reviewed)
        issue_counts = Counter(item["issue_type"] for item in reviewed if item["issue_type"])
        split_counts: dict[str, dict[str, int]] = {
            "test": {"reviewed": 0},
            "holdout": {"reviewed": 0},
        }
        for item in reviewed:
            split = item.get("source_split", "test")
            split_counts.setdefault(split, {"reviewed": 0})
            split_counts[split]["reviewed"] = split_counts[split].get("reviewed", 0) + 1
            if item["issue_type"]:
                split_counts[split][item["issue_type"]] = split_counts[split].get(item["issue_type"], 0) + 1

        gate, serious_ratio, reason = self._compute_gate(issue_counts, reviewed_count, len(self.items), split_counts)
        if gate == "PASS":
            next_stage = "threshold_nms_calibration"
        elif gate == "WARNING":
            next_stage = "hard_case_analysis_or_threshold_calibration"
        elif gate == "FAIL":
            next_stage = "data_debug"
        else:
            next_stage = "pending"

        summary = {
            "generated_at": now_iso(),
            "dataset_version": "phone_riceseg_v35m_holdout_applied",
            "review_items_count": len(self.items),
            "reviewed_count": reviewed_count,
            "unreviewed_count": len(self.items) - reviewed_count,
            "issue_type_counts": dict(sorted(issue_counts.items())),
            "serious_issue_count": sum(issue_counts.get(issue, 0) for issue in SERIOUS_ISSUES),
            "serious_issue_ratio": serious_ratio,
            "split_issue_counts": split_counts,
            "gate": gate,
            "next_allowed_stage": next_stage,
            "reason": reason,
            "holdout_observation_warning_enabled": True,
        }
        return summary

    def render_gate_report(self, summary: dict[str, Any]) -> str:
        lines = [
            "# Phone RiceSeg 35O Prediction Review Gate Report",
            "",
            "- 当前审核对象：`35N 模型预测框`",
            "- 不是原始标签审核",
            "- 不是训练",
            "- 不是后端接入",
            "- holdout 样本只做 observation",
            "",
            f"- review_items_count: `{summary['review_items_count']}`",
            f"- reviewed_count: `{summary['reviewed_count']}`",
            f"- unreviewed_count: `{summary['unreviewed_count']}`",
            f"- gate: `{summary['gate']}` ({GATE_LABELS.get(summary['gate'], summary['gate'])})",
            f"- serious_issue_count: `{summary['serious_issue_count']}`",
            f"- serious_issue_ratio: `{summary['serious_issue_ratio']}`",
            f"- next_allowed_stage: `{summary['next_allowed_stage']}`",
            f"- reason: {summary['reason']}",
            "",
            "## issue_type_counts",
            "",
        ]
        if summary["issue_type_counts"]:
            for issue_type, count in summary["issue_type_counts"].items():
                lines.append(f"- `{issue_type}` ({ISSUE_LABELS.get(issue_type, issue_type)}): `{count}`")
        else:
            lines.append("- no reviewed issue counts yet")
        lines.append("")
        return "\n".join(lines)

    def persist(self, reason: str) -> None:
        self._guard_output_paths()
        fieldnames = list(self.items[0].keys()) if self.items else []
        atomic_write_csv(self.decisions_csv, fieldnames, self.items)
        atomic_write_json(self.decisions_json, {"generated_at": now_iso(), "reason": reason, "items": self.items})
        summary = self.compute_summary()
        atomic_write_json(self.summary_json, summary)
        atomic_write_text(self.gate_report_md, self.render_gate_report(summary))


class ReviewApp:
    def __init__(self, store: ReviewStore, logger: logging.Logger) -> None:
        self.store = store
        self.logger = logger
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("1460x960")
        self.filtered_items: list[dict[str, Any]] = []
        self.current_index = 0
        self.current_image_ref = None

        self.status_filter = tk.StringVar(value="all")
        self.issue_choice = tk.StringVar(value="")
        self.summary_status = tk.StringVar(value="")
        self.gate_status = tk.StringVar(value="")
        self.preview_status = tk.StringVar(value="")
        self.save_status = tk.StringVar(value="")

        self.listbox: tk.Listbox
        self.preview_label: ttk.Label
        self.detail_text: tk.Text
        self.notes_text: tk.Text

        self._build_ui()
        self._bind_shortcuts()
        self.render_all()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=3)
        self.root.columnconfigure(2, weight=2)
        self.root.rowconfigure(1, weight=1)

        header = ttk.Frame(self.root, padding=12)
        header.grid(row=0, column=0, columnspan=3, sticky="ew")
        ttk.Label(header, text=APP_TITLE, font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            header,
            text="当前审核的是 35N 模型预测框，不是原始标签；不是训练；不是后端接入；holdout 样本只做 observation。",
            foreground="#475569",
        ).pack(anchor="w", pady=(6, 0))

        left = ttk.Frame(self.root, padding=(12, 0, 8, 12))
        left.grid(row=1, column=0, sticky="nsew")
        center = ttk.Frame(self.root, padding=(8, 0, 8, 12))
        center.grid(row=1, column=1, sticky="nsew")
        right = ttk.Frame(self.root, padding=(8, 0, 12, 12))
        right.grid(row=1, column=2, sticky="nsew")
        center.rowconfigure(1, weight=1)
        center.columnconfigure(0, weight=1)

        ttk.Label(left, text="状态筛选", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
        status_combo = ttk.Combobox(left, textvariable=self.status_filter, values=[label for _code, label in STATUS_OPTIONS], state="readonly", width=24)
        status_combo.pack(fill="x")
        status_combo.bind("<<ComboboxSelected>>", lambda _e: self.render_all())
        self.status_filter_map = {label: code for code, label in STATUS_OPTIONS}
        self.status_filter.set("全部状态")

        ttk.Label(left, text="样本列表", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", pady=(12, 4))
        self.listbox = tk.Listbox(left, exportselection=False)
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        ttk.Label(left, textvariable=self.summary_status, foreground="#475569", justify="left").pack(anchor="w", pady=(6, 0))

        toolbar = ttk.Frame(center)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="上一张", command=self.go_previous).pack(side="left")
        ttk.Button(toolbar, text="下一张", command=self.go_next).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="打开对比图", command=self.open_preview_image).pack(side="left", padx=(16, 0))
        ttk.Button(toolbar, text="打开图片文件夹", command=self.open_image_folder).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="导出 Gate 报告", command=self.export_gate_report).pack(side="left", padx=(8, 0))

        preview_card = ttk.Frame(center, relief="groove", padding=8)
        preview_card.grid(row=1, column=0, sticky="nsew")
        preview_card.rowconfigure(0, weight=1)
        preview_card.columnconfigure(0, weight=1)
        self.preview_label = ttk.Label(preview_card, anchor="center", justify="center", text="正在加载对比图...")
        self.preview_label.grid(row=0, column=0, sticky="nsew")
        ttk.Label(preview_card, textvariable=self.preview_status, foreground="#475569", justify="left").grid(row=1, column=0, sticky="ew", pady=(8, 0))

        self.detail_text = tk.Text(center, height=11, wrap="word")
        self.detail_text.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.detail_text.configure(state="disabled")

        ttk.Label(right, text="问题类型", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        for issue_type in ISSUE_TYPES:
            ttk.Button(right, text=ISSUE_LABELS[issue_type], command=lambda value=issue_type: self.set_issue(value)).pack(fill="x", pady=2)

        ttk.Label(right, text="审核备注", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", pady=(12, 4))
        self.notes_text = tk.Text(right, width=34, height=10, wrap="word")
        self.notes_text.pack(fill="x")

        ttk.Button(right, text="保存", command=self.save_current).pack(fill="x", pady=(12, 4))
        ttk.Button(right, text="保存并下一张", command=lambda: self.save_current(go_next=True)).pack(fill="x")
        ttk.Label(right, textvariable=self.save_status, foreground="#475569", justify="left").pack(anchor="w", pady=(8, 0))
        ttk.Separator(right).pack(fill="x", pady=10)
        ttk.Label(right, text="Gate / 统计", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        ttk.Label(right, textvariable=self.gate_status, foreground="#1d4ed8", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", pady=(6, 0))

    def _bind_shortcuts(self) -> None:
        for key, issue_type in ISSUE_SHORTCUTS.items():
            self.root.bind(key, lambda _e, value=issue_type: self.set_issue(value))
        self.root.bind("<Control-s>", lambda _e: self.save_current() or "break")
        self.root.bind("<Return>", lambda _e: self.save_current(go_next=True) or "break")
        self.root.bind("<a>", lambda _e: self.go_previous() or "break")
        self.root.bind("<A>", lambda _e: self.go_previous() or "break")
        self.root.bind("<d>", lambda _e: self.go_next() or "break")
        self.root.bind("<D>", lambda _e: self.go_next() or "break")
        self.root.bind("<o>", lambda _e: self.open_preview_image() or "break")
        self.root.bind("<O>", lambda _e: self.open_preview_image() or "break")

    def item_matches_filter(self, item: dict[str, Any]) -> bool:
        status_filter = self.status_filter_map.get(self.status_filter.get(), "all")
        if status_filter == "unreviewed":
            return item["review_status"] != "reviewed"
        if status_filter == "reviewed":
            return item["review_status"] == "reviewed"
        if status_filter == "issue_only":
            return item["review_status"] == "reviewed" and item["issue_type"] and item["issue_type"] != "pred_ok"
        return True

    def current_item(self) -> dict[str, Any] | None:
        if not self.filtered_items:
            return None
        return self.filtered_items[self.current_index]

    def render_all(self) -> None:
        current_id = self.current_item()["review_id"] if self.filtered_items else None
        self.filtered_items = [item for item in self.store.list_items() if self.item_matches_filter(item)]
        if current_id:
            for idx, item in enumerate(self.filtered_items):
                if item["review_id"] == current_id:
                    self.current_index = idx
                    break
        self.current_index = min(self.current_index, max(0, len(self.filtered_items) - 1))

        self.listbox.delete(0, tk.END)
        for item in self.filtered_items:
            issue_text = ISSUE_LABELS.get(item["issue_type"], "-") if item["issue_type"] else "-"
            self.listbox.insert(
                tk.END,
                f"{item['review_id']} | {item['source_split']} | {item['class_name']} | {STATUS_LABELS.get(item['review_status'], item['review_status'])} | {issue_text}",
            )
        if self.filtered_items:
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(self.current_index)
            self.listbox.see(self.current_index)
        self.summary_status.set(f"当前筛选：{len(self.filtered_items)} / 总计：{len(self.store.list_items())}")
        self.render_item_details()
        self.render_stats()

    def render_item_details(self) -> None:
        item = self.current_item()
        if not item:
            self.preview_label.configure(text="当前筛选下没有样本。", image="")
            self.preview_status.set("")
            self._set_detail_text("当前筛选下没有样本。")
            self.notes_text.delete("1.0", tk.END)
            self.issue_choice.set("")
            return

        self.notes_text.delete("1.0", tk.END)
        self.notes_text.insert("1.0", item.get("reviewer_notes", ""))
        self.issue_choice.set(item.get("issue_type", ""))

        preview_path = self.store.get_preview_path(item)
        info_lines = [
            f"{FIELD_LABELS['review_id']}：{item['review_id']}",
            f"{FIELD_LABELS['source_split']}：{item['source_split']}",
            f"{FIELD_LABELS['class_name']}：{item['class_name']}",
            f"{FIELD_LABELS['predicted_box_count_conf025']}：{item['predicted_box_count_conf025']}",
            f"{FIELD_LABELS['no_detection_conf025']}：{item['no_detection_conf025']}",
            f"{FIELD_LABELS['predicted_classes_conf025']}：{item['predicted_classes_conf025'] or '-'}",
            f"{FIELD_LABELS['max_confidence_conf025']}：{item['max_confidence_conf025'] or '-'}",
            f"holdout observation only：{item['holdout_observation_only']}",
        ]
        self.preview_status.set("\n".join(info_lines))
        self._render_preview(preview_path)

        detail_lines = [f"{FIELD_LABELS.get(key, key)}：{value or '-'}" for key, value in item.items()]
        detail_lines.extend(
            [
                "",
                "快捷键：",
                "1 = 预测正常",
                "2 = 无检测",
                "3 = 部分检测",
                "4 = 框过大",
                "5 = 框过小",
                "6 = 类别错误",
                "7 = 背景误检",
                "8 = 重复框",
                "9 = 框过多",
                "0 = 低置信不确定",
                "A = 上一张",
                "D = 下一张",
                "Ctrl+S = 保存",
                "Enter = 保存并下一张",
                "O = 打开对比图",
            ]
        )
        self._set_detail_text("\n".join(detail_lines))

    def _render_preview(self, preview_path: Path | None) -> None:
        if preview_path is None:
            self.current_image_ref = None
            self.preview_label.configure(text="Preview not found.\nUse Open Preview Image to inspect file.", image="")
            return
        if not PILLOW_AVAILABLE:
            self.current_image_ref = None
            self.preview_label.configure(text="Pillow unavailable.\nUse Open Preview Image to inspect file.", image="")
            return
        try:
            image = Image.open(preview_path)
            image.thumbnail((880, 620))
            self.current_image_ref = ImageTk.PhotoImage(image)
            self.preview_label.configure(image=self.current_image_ref, text="")
        except Exception as exc:
            self.current_image_ref = None
            self.preview_label.configure(text=f"预览图渲染失败：{exc}", image="")

    def _set_detail_text(self, text: str) -> None:
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", text)
        self.detail_text.configure(state="disabled")

    def render_stats(self) -> None:
        summary = self.store.compute_summary()
        self.gate_status.set(
            "\n".join(
                [
                    f"当前 Gate：{GATE_LABELS.get(summary['gate'], summary['gate'])}",
                    f"已审核：{summary['reviewed_count']} / {summary['review_items_count']}",
                    f"serious_issue_ratio：{summary['serious_issue_ratio']}",
                    f"下一步：{summary['next_allowed_stage']}",
                ]
            )
        )

    def _on_select(self, _event: Any) -> None:
        if not self.listbox.curselection():
            return
        self.current_index = self.listbox.curselection()[0]
        self.render_item_details()
        self.render_stats()

    def set_issue(self, issue_type: str) -> None:
        self.issue_choice.set(issue_type)
        self.save_status.set(f"已选择问题类型：{ISSUE_LABELS.get(issue_type, issue_type)}")

    def go_previous(self) -> None:
        if not self.filtered_items:
            return
        self.current_index = max(0, self.current_index - 1)
        self.render_item_details()
        self.render_stats()

    def go_next(self) -> None:
        if not self.filtered_items:
            return
        self.current_index = min(len(self.filtered_items) - 1, self.current_index + 1)
        self.render_item_details()
        self.render_stats()

    def save_current(self, go_next: bool = False) -> None:
        item = self.current_item()
        if not item:
            return
        issue_type = self.issue_choice.get().strip()
        if issue_type not in ISSUE_TYPES:
            messagebox.showwarning("未选择问题类型", "请先选择一个问题类型。")
            return
        notes = self.notes_text.get("1.0", tk.END).strip()
        try:
            self.store.save_decision(item["review_id"], issue_type, notes)
            self.save_status.set(f"已保存：{item['review_id']} @ {now_iso()}")
            self.render_all()
            if go_next:
                self.go_next()
        except Exception as exc:
            self.logger.exception("save failed")
            messagebox.showerror("保存失败", str(exc))

    def open_preview_image(self) -> None:
        item = self.current_item()
        if not item:
            return
        preview_path = self.store.get_preview_path(item)
        target = preview_path or resolve_path(item["image_path"])
        try:
            os.startfile(str(target))  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc))

    def open_image_folder(self) -> None:
        item = self.current_item()
        if not item:
            return
        image_path = resolve_path(item["image_path"])
        target = image_path.parent
        try:
            os.startfile(str(target))  # type: ignore[attr-defined]
        except Exception:
            try:
                subprocess.Popen(["explorer", str(target)])
            except Exception as exc:
                messagebox.showerror("打开失败", str(exc))

    def export_gate_report(self) -> None:
        try:
            self.store.persist("manual_export_gate_report")
            self.save_status.set("已导出 Gate 报告。")
            self.render_stats()
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))


def build_selftest_payload(store: ReviewStore) -> dict[str, Any]:
    items = store.list_items()
    payload = {
        "dataset_version": "phone_riceseg_v35m_holdout_applied",
        "review_items_count": len(items),
        "output_prefix": "reports/phone_riceseg_35o_prediction_review",
        "visual_audit_prefix": "reports/phone_riceseg_35o_prediction_visual_audit",
        "no_uav_path_detected": all("uav" not in str(item.get("image_path", "")).lower() for item in items),
        "no_label_review_output_detected": all("preview_500" not in str(path).lower() for path in [DECISIONS_CSV, DECISIONS_JSON, SUMMARY_JSON, GATE_REPORT_MD]),
        "holdout_observation_warning_enabled": True,
        "gate": "PENDING",
        "guards_enabled": True,
    }
    return payload


def render_selftest_md(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Phone RiceSeg 35O Prediction Review Launcher Self-Test",
            "",
            f"- review_items_count: `{payload['review_items_count']}`",
            f"- output_prefix: `{payload['output_prefix']}`",
            f"- visual_audit_prefix: `{payload['visual_audit_prefix']}`",
            f"- no_uav_path_detected: `{payload['no_uav_path_detected']}`",
            f"- no_label_review_output_detected: `{payload['no_label_review_output_detected']}`",
            f"- holdout_observation_warning_enabled: `{payload['holdout_observation_warning_enabled']}`",
            f"- gate: `{payload['gate']}`",
            f"- guards_enabled: `{payload['guards_enabled']}`",
            "",
        ]
    )


def validate_required_inputs(store: ReviewStore) -> None:
    required = [
        store.items_csv,
        store.items_json,
        resolve_path("reports/phone_riceseg_35o_prediction_visual_audit/index.md"),
        resolve_path("reports/phone_riceseg_35o_prediction_visual_audit_manifest.json"),
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required inputs:\n" + "\n".join(missing))


def run_self_test(store: ReviewStore) -> int:
    payload = build_selftest_payload(store)
    atomic_write_json(resolve_path(SELFTEST_JSON), payload)
    atomic_write_text(resolve_path(SELFTEST_MD), render_selftest_md(payload))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    args = parse_args()
    logger = configure_logger(resolve_path(LOG_PATH))
    logger.info("==== Phone 35O prediction review desktop startup ====")
    logger.info("project_root=%s", repo_root())
    logger.info("items_csv=%s", resolve_path(REVIEW_ITEMS_CSV))
    logger.info("output_prefix=%s", resolve_path("reports/phone_riceseg_35o_prediction_review"))
    logger.info("visual_audit_prefix=%s", resolve_path("reports/phone_riceseg_35o_prediction_visual_audit"))
    logger.info("pillow_available=%s", PILLOW_AVAILABLE)
    try:
        store = ReviewStore(logger)
        validate_required_inputs(store)
        if args.self_test:
            return run_self_test(store)

        root = tk.Tk()
        root.destroy()
        app = ReviewApp(store, logger)

        def report_callback_exception(exc: type[BaseException], value: BaseException, tb: Any) -> None:
            logger.error("Tkinter callback exception: %s", "".join(traceback.format_exception(exc, value, tb)))
            messagebox.showerror("程序异常", f"{value}\n\n请查看日志：\n{resolve_path(LOG_PATH)}")

        app.root.report_callback_exception = report_callback_exception  # type: ignore[assignment]
        app.root.mainloop()
        logger.info("prediction review app exited normally")
        return 0
    except Exception as exc:
        logger.exception("prediction review app failed")
        print(f"Prediction review app failed: {exc}")
        print(f"Check log: {resolve_path(LOG_PATH)}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
