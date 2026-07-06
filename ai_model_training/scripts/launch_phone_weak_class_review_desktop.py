"""Launch a Tkinter desktop weak-class review tool for Phone RiceLeafDiseaseBD."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
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


APP_TITLE = "Phone RiceLeafDiseaseBD 弱类标签人工审核台"
LOGGER_NAME = "phone_weak_review_desktop"
ISSUE_TYPES = [
    "ok",
    "wrong_class",
    "missing_box",
    "over_boxed",
    "under_boxed",
    "too_tiny",
    "ambiguous_symptom",
    "image_quality_bad",
    "other",
    "box_misaligned",
]
SEVERE_ISSUES = {"wrong_class", "missing_box", "over_boxed", "under_boxed", "box_misaligned"}
WEAK_CLASSES = ("leaf_smut", "tungro", "sheath_blight")
STATUS_ALL = {"unreviewed", "reviewed"}
REVIEW_OUTPUTS = {
    "decisions_csv": "phone_riceleafdiseasebd_weak_class_review_decisions.csv",
    "decisions_json": "phone_riceleafdiseasebd_weak_class_review_decisions.json",
    "summary_json": "phone_riceleafdiseasebd_weak_class_review_summary.json",
    "gate_report_md": "phone_riceleafdiseasebd_weak_class_review_gate_report.md",
}
ISSUE_SHORTCUTS = {
    "1": "ok",
    "2": "wrong_class",
    "3": "missing_box",
    "4": "over_boxed",
    "5": "under_boxed",
    "6": "too_tiny",
    "7": "ambiguous_symptom",
    "8": "image_quality_bad",
    "9": "other",
    "0": "box_misaligned",
}

ISSUE_LABELS = {
    "ok": "正常",
    "wrong_class": "类别错误",
    "missing_box": "漏框",
    "over_boxed": "框太大",
    "under_boxed": "框太小",
    "too_tiny": "目标太小",
    "ambiguous_symptom": "症状不清楚",
    "image_quality_bad": "图像质量差",
    "other": "其他",
    "box_misaligned": "框位置错误",
}
CLASS_FILTER_OPTIONS = [
    ("all", "全部类别"),
    ("leaf_smut", "叶黑粉病 leaf_smut"),
    ("tungro", "东格鲁病 tungro"),
    ("sheath_blight", "纹枯病 sheath_blight"),
]
STATUS_FILTER_OPTIONS = [
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
    "class_name": "类别",
    "split": "数据划分",
    "review_status": "审核状态",
    "issue_type": "问题类型",
    "bbox_count": "标注框数量",
    "mean_bbox_area": "平均框面积",
    "median_bbox_area": "中位框面积",
    "selection_reason": "抽样原因",
    "infer_zero_detection": "推理零检测",
    "infer_low_conf_detection": "低置信度检测",
    "infer_max_confidence": "最高置信度",
    "image_path": "原图路径",
    "label_path": "标签路径",
    "source_original_path": "原始来源路径",
    "visual_preview_path": "预览图路径",
    "reviewer_notes": "审核备注",
}


def issue_label(issue_type: str) -> str:
    return ISSUE_LABELS.get(issue_type, issue_type)


def class_label(class_name: str) -> str:
    for code, label in CLASS_FILTER_OPTIONS:
        if code == class_name:
            return label
    return class_name


def status_label(status_value: str) -> str:
    return STATUS_LABELS.get(status_value, status_value)


def gate_label(gate_value: str) -> str:
    return GATE_LABELS.get(gate_value, gate_value)


def field_label(field_name: str) -> str:
    return FIELD_LABELS.get(field_name, field_name)



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the phone weak class desktop review app.")
    parser.add_argument("--items-csv", default="reports/weak_class_review/phone_riceleafdiseasebd_weak_class_review_items.csv")
    parser.add_argument("--output-root", default="reports/weak_class_review")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (repo_root() / path)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_issue(value: str) -> str:
    value = (value or "").strip()
    return value if value in ISSUE_TYPES else ""


def normalize_status(value: str, issue_type: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized == "pending":
        normalized = "unreviewed"
    if normalized == "needs_followup":
        normalized = "reviewed"
    if normalized not in STATUS_ALL:
        normalized = "reviewed" if issue_type else "unreviewed"
    return normalized


def configure_logger(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
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
            raise RuntimeError(f"Temporary file write failed: {tmp_path}")
        tmp_path.replace(path)
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"Atomic replace failed: {path}")
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def atomic_write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
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
            raise RuntimeError(f"Temporary CSV write failed: {tmp_path}")
        tmp_path.replace(path)
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"Atomic replace failed: {path}")
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


class ReviewStore:
    def __init__(self, items_csv: Path, output_root: Path, logger: logging.Logger) -> None:
        self.items_csv = items_csv
        self.output_root = output_root
        self.preview_root = (output_root / "visual_samples").resolve()
        self.decisions_csv = output_root / REVIEW_OUTPUTS["decisions_csv"]
        self.decisions_json = output_root / REVIEW_OUTPUTS["decisions_json"]
        self.summary_json = output_root / REVIEW_OUTPUTS["summary_json"]
        self.gate_report_md = output_root / REVIEW_OUTPUTS["gate_report_md"]
        self.logger = logger
        self.items: list[dict[str, Any]] = []
        self.item_by_id: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        items: list[dict[str, Any]] = []
        with self.items_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                issue_type = normalize_issue(row.get("issue_type", ""))
                item = {
                    "review_id": (row.get("review_id") or "").strip(),
                    "class_name": (row.get("class_name") or "").strip(),
                    "split": (row.get("split") or "").strip(),
                    "image_path": (row.get("image_path") or "").strip(),
                    "label_path": (row.get("label_path") or "").strip(),
                    "bbox_count": parse_int(row.get("bbox_count")),
                    "mean_bbox_area": parse_float(row.get("mean_bbox_area")),
                    "median_bbox_area": parse_float(row.get("median_bbox_area")),
                    "source_original_path": (row.get("source_original_path") or "").strip(),
                    "selection_reason": (row.get("selection_reason") or "").strip(),
                    "infer_zero_detection": str(row.get("infer_zero_detection", "")).strip().lower() == "true",
                    "infer_low_conf_detection": str(row.get("infer_low_conf_detection", "")).strip().lower() == "true",
                    "infer_max_confidence": parse_float(row.get("infer_max_confidence"), default=0.0),
                    "predicted_classes": (row.get("predicted_classes") or "").strip(),
                    "issue_type": issue_type,
                    "review_status": normalize_status(row.get("review_status", ""), issue_type),
                    "reviewer_notes": (row.get("reviewer_notes") or "").strip(),
                    "reviewed_at": (row.get("reviewed_at") or "").strip(),
                    "visual_preview_path": self._resolve_preview_path(row),
                }
                items.append(item)
        self.items = items
        self.item_by_id = {item["review_id"]: item for item in items}
        self._overlay_saved_decisions()
        self._bootstrap_outputs()

    def _resolve_preview_path(self, row: dict[str, str]) -> str:
        preview_raw = (row.get("visual_preview_path") or row.get("preview_path") or "").strip()
        if preview_raw:
            preview_path = Path(preview_raw)
            if not preview_path.is_absolute():
                preview_path = repo_root() / preview_path
            return str(preview_path.resolve())

        review_id = (row.get("review_id") or "").strip()
        class_name = (row.get("class_name") or "").strip()
        split = (row.get("split") or "").strip()
        image_path = Path((row.get("image_path") or "").strip())
        try:
            suffix = int(review_id.rsplit("_", 1)[-1])
        except (IndexError, ValueError):
            return ""
        candidate_dir = self.preview_root / class_name
        prefix = f"{suffix:03d}_{split}_"
        matches = sorted(candidate_dir.glob(prefix + "*"))
        if matches:
            return str(matches[0].resolve())
        fallback = candidate_dir / f"{suffix:03d}_{split}_{image_path.name}"
        return str(fallback.resolve()) if fallback.exists() else ""

    def _overlay_saved_decisions(self) -> None:
        if not self.decisions_csv.exists():
            return
        with self.decisions_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                review_id = (row.get("review_id") or "").strip()
                item = self.item_by_id.get(review_id)
                if not item:
                    continue
                issue_type = normalize_issue(row.get("issue_type", ""))
                item["issue_type"] = issue_type
                item["review_status"] = normalize_status(row.get("review_status", ""), issue_type)
                item["reviewer_notes"] = (row.get("reviewer_notes") or "").strip()
                item["reviewed_at"] = (row.get("reviewed_at") or "").strip()
                preview_raw = (row.get("visual_preview_path") or "").strip()
                if preview_raw:
                    item["visual_preview_path"] = preview_raw

    def _bootstrap_outputs(self) -> None:
        missing_outputs = [
            path
            for path in (self.decisions_csv, self.decisions_json, self.summary_json, self.gate_report_md)
            if not path.exists()
        ]
        if missing_outputs:
            self.persist(reason="startup_bootstrap")

    def list_items(self) -> list[dict[str, Any]]:
        return self.items

    def get_item(self, review_id: str) -> dict[str, Any]:
        item = self.item_by_id.get(review_id)
        if not item:
            raise KeyError(review_id)
        return item

    def get_preview_path(self, item: dict[str, Any]) -> Path | None:
        preview_raw = (item.get("visual_preview_path") or "").strip()
        if not preview_raw:
            return None
        path = Path(preview_raw)
        if not path.is_absolute():
            path = repo_root() / path
        path = path.resolve()
        try:
            path.relative_to(self.preview_root)
        except ValueError:
            self.logger.warning("Preview path outside visual_samples: %s", path)
            return None
        return path if path.exists() and path.is_file() else None

    def save_decision(self, review_id: str, issue_type: str, reviewer_notes: str) -> dict[str, Any]:
        item = self.get_item(review_id)
        issue_type = normalize_issue(issue_type)
        if not issue_type:
            raise ValueError("issue_type is required")
        item["issue_type"] = issue_type
        item["review_status"] = "reviewed"
        item["reviewer_notes"] = reviewer_notes.strip()
        item["reviewed_at"] = now_iso()
        self.persist(reason=f"save_decision:{review_id}")
        return item

    def _systemic_flags(self, per_class: dict[str, dict[str, Any]]) -> list[str]:
        flags: list[str] = []
        for class_name, stats in per_class.items():
            reviewed = stats["reviewed"]
            if reviewed <= 0:
                continue
            threshold = max(10, math.ceil(reviewed * 0.10))
            issue_counts = stats["issue_counts"]
            for issue_name in ("wrong_class", "missing_box", "box_misaligned"):
                if issue_counts.get(issue_name, 0) >= threshold:
                    flags.append(f"{class_name}:{issue_name}")
            bbox_inconsistent = issue_counts.get("over_boxed", 0) + issue_counts.get("under_boxed", 0) + issue_counts.get("box_misaligned", 0)
            if bbox_inconsistent >= threshold:
                flags.append(f"{class_name}:bbox_granularity_inconsistency")
        return sorted(set(flags))

    def compute_summary(self) -> dict[str, Any]:
        total = len(self.items)
        reviewed = 0
        per_class: dict[str, dict[str, Any]] = {}
        for class_name in WEAK_CLASSES:
            class_items = [item for item in self.items if item["class_name"] == class_name]
            issue_counts = Counter(item["issue_type"] for item in class_items if item["issue_type"])
            class_reviewed = sum(1 for item in class_items if item["review_status"] == "reviewed")
            class_ok = issue_counts.get("ok", 0)
            class_severe = sum(issue_counts.get(issue, 0) for issue in SEVERE_ISSUES)
            class_non_severe = max(0, class_reviewed - class_ok - class_severe)
            reviewed += class_reviewed
            per_class[class_name] = {
                "total": len(class_items),
                "reviewed": class_reviewed,
                "unreviewed": len(class_items) - class_reviewed,
                "ok_count": class_ok,
                "severe_issue_count": class_severe,
                "non_severe_issue_count": class_non_severe,
                "ok_ratio": round(class_ok / class_reviewed, 4) if class_reviewed else 0.0,
                "severe_issue_ratio": round(class_severe / class_reviewed, 4) if class_reviewed else 0.0,
                "issue_counts": dict(sorted(issue_counts.items())),
            }

        all_reviewed = total > 0 and reviewed == total
        systemic_flags = self._systemic_flags(per_class)
        reasons: list[str] = []
        gate = "PENDING"
        allow_next_stage = "conditional"

        if all_reviewed:
            has_fail = False
            has_warning = False
            for class_name, stats in per_class.items():
                if stats["ok_ratio"] < 0.70:
                    has_fail = True
                    reasons.append(f"{class_name} ok_ratio < 0.70")
                elif stats["ok_ratio"] < 0.80:
                    has_warning = True
                    reasons.append(f"{class_name} ok_ratio in [0.70, 0.80)")

                if stats["severe_issue_ratio"] > 0.20:
                    has_fail = True
                    reasons.append(f"{class_name} severe_issue_ratio > 0.20")
                elif stats["severe_issue_ratio"] > 0.15:
                    has_warning = True
                    reasons.append(f"{class_name} severe_issue_ratio in (0.15, 0.20]")

            if systemic_flags:
                has_fail = True
                reasons.append("systemic annotation error pattern detected")

            if has_fail:
                gate = "FAIL"
                allow_next_stage = "no"
            elif has_warning:
                gate = "WARNING"
                allow_next_stage = "conditional"
            else:
                gate = "PASS"
                allow_next_stage = "yes"
        else:
            reasons.append(f"{total - reviewed} samples still unreviewed")

        return {
            "app_title": APP_TITLE,
            "total": total,
            "reviewed": reviewed,
            "unreviewed": max(0, total - reviewed),
            "per_class": per_class,
            "gate": gate,
            "allow_next_stage": allow_next_stage,
            "systemic_flags": systemic_flags,
            "reasons": reasons,
            "generated_at": now_iso(),
            "issue_types": ISSUE_TYPES,
            "severe_issues": sorted(SEVERE_ISSUES),
        }

    def build_gate_report(self, summary: dict[str, Any]) -> str:
        lines = [
            "# Phone RiceLeafDiseaseBD Weak Class Review Gate Report",
            "",
            "## Goal",
            "",
            "- Review 300 weak-class samples for leaf_smut, tungro, and sheath_blight.",
            "- Desktop review only. No training, no label edits, no formal metrics.",
            "",
            "## Progress",
            "",
            f"- total_samples: `{summary['total']}`",
            f"- reviewed: `{summary['reviewed']}`",
            f"- unreviewed: `{summary['unreviewed']}`",
            f"- gate: `{summary['gate']}`",
            f"- allow_next_stage: `{summary['allow_next_stage']}`",
            f"- generated_at: `{summary['generated_at']}`",
            "",
            "## Per-class Stats",
            "",
            "| class_name | total | reviewed | ok_count | severe_issue_count | box_misaligned_count | non_severe_issue_count | ok_ratio | severe_issue_ratio |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for class_name in WEAK_CLASSES:
            stats = summary["per_class"][class_name]
            lines.append(
                f"| {class_name} | {stats['total']} | {stats['reviewed']} | {stats['ok_count']} | "
                f"{stats['severe_issue_count']} | {stats['issue_counts'].get('box_misaligned', 0)} | {stats['non_severe_issue_count']} | "
                f"{stats['ok_ratio']:.4f} | {stats['severe_issue_ratio']:.4f} |"
            )
        lines.extend(["", "## Current Conclusion", ""])
        if summary["reasons"]:
            for reason in summary["reasons"]:
                lines.append(f"- {reason}")
        else:
            lines.append("- no blocking reason recorded")
        if summary["systemic_flags"]:
            lines.extend(["", "## Systemic Flags", ""])
            for flag in summary["systemic_flags"]:
                lines.append(f"- {flag}")
        lines.extend(["", "## Boundary", "", "- not training", "- not editing labels", "- manual review records only", ""])
        return "\n".join(lines)

    def persist(self, reason: str) -> None:
        rows: list[dict[str, Any]] = []
        for item in self.items:
            rows.append(
                {
                    "review_id": item["review_id"],
                    "class_name": item["class_name"],
                    "split": item["split"],
                    "image_path": item["image_path"],
                    "label_path": item["label_path"],
                    "visual_preview_path": item["visual_preview_path"],
                    "bbox_count": item["bbox_count"],
                    "mean_bbox_area": f"{item['mean_bbox_area']:.10f}",
                    "median_bbox_area": f"{item['median_bbox_area']:.10f}",
                    "source_original_path": item["source_original_path"],
                    "selection_reason": item["selection_reason"],
                    "infer_zero_detection": str(item["infer_zero_detection"]).lower(),
                    "infer_low_conf_detection": str(item["infer_low_conf_detection"]).lower(),
                    "infer_max_confidence": f"{item['infer_max_confidence']:.6f}" if item["infer_max_confidence"] else "",
                    "predicted_classes": item["predicted_classes"],
                    "issue_type": item["issue_type"],
                    "review_status": item["review_status"],
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
            "bbox_count",
            "mean_bbox_area",
            "median_bbox_area",
            "source_original_path",
            "selection_reason",
            "infer_zero_detection",
            "infer_low_conf_detection",
            "infer_max_confidence",
            "predicted_classes",
            "issue_type",
            "review_status",
            "reviewer_notes",
            "reviewed_at",
        ]
        summary = self.compute_summary()
        atomic_write_csv(self.decisions_csv, fieldnames, rows)
        atomic_write_json(self.decisions_json, {"generated_at": summary["generated_at"], "total_items": len(rows), "items": rows})
        atomic_write_json(self.summary_json, summary)
        atomic_write_text(self.gate_report_md, self.build_gate_report(summary) + "\n")
        self.logger.info("Persisted review outputs (%s).", reason)


class ReviewDesktopApp:
    def __init__(self, root: tk.Tk, store: ReviewStore, logger: logging.Logger) -> None:
        self.root = root
        self.store = store
        self.logger = logger
        self.items = self.store.list_items()
        self.filtered_items = list(self.items)
        self.current_index = 0
        self.current_review_id = self.filtered_items[0]["review_id"] if self.filtered_items else None
        self.current_image_ref: Any = None
        self.selected_issue = tk.StringVar(value="")
        self.class_filter = tk.StringVar(value="全部类别")
        self.status_filter = tk.StringVar(value="全部状态")
        self.save_status = tk.StringVar(value="尚未保存")
        self.summary_status = tk.StringVar(value="")
        self.gate_status = tk.StringVar(value="PENDING")
        self.preview_status = tk.StringVar(value="")
        self.stats_status = tk.StringVar(value="")
        self.notes_var = tk.StringVar(value="")
        self._build_ui()
        self._bind_shortcuts()
        self.render_all()

    def _build_ui(self) -> None:
        self.root.title(APP_TITLE)
        self.root.geometry("1520x920")
        self.root.minsize(1280, 760)

        shell = ttk.Frame(self.root, padding=12)
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=0)
        shell.columnconfigure(1, weight=1)
        shell.columnconfigure(2, weight=0)
        shell.rowconfigure(0, weight=1)

        left = ttk.Frame(shell, padding=(0, 0, 12, 0))
        center = ttk.Frame(shell, padding=(0, 0, 12, 0))
        right = ttk.Frame(shell)
        left.grid(row=0, column=0, sticky="nsew")
        center.grid(row=0, column=1, sticky="nsew")
        right.grid(row=0, column=2, sticky="nsew")
        center.rowconfigure(1, weight=1)

        ttk.Label(left, text="筛选", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(left, text="类别", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 0))
        self.class_filter_map = {label: code for code, label in CLASS_FILTER_OPTIONS}
        self.class_filter_reverse_map = {code: label for code, label in CLASS_FILTER_OPTIONS}
        class_combo = ttk.Combobox(left, textvariable=self.class_filter, values=[label for _code, label in CLASS_FILTER_OPTIONS], state="readonly", width=24)
        class_combo.pack(fill="x")
        class_combo.bind("<<ComboboxSelected>>", lambda _e: self.render_all())
        ttk.Label(left, text="状态", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 0))
        self.status_filter_map = {label: code for code, label in STATUS_FILTER_OPTIONS}
        self.status_filter_reverse_map = {code: label for code, label in STATUS_FILTER_OPTIONS}
        status_combo = ttk.Combobox(left, textvariable=self.status_filter, values=[label for _code, label in STATUS_FILTER_OPTIONS], state="readonly", width=24)
        status_combo.pack(fill="x")
        status_combo.bind("<<ComboboxSelected>>", lambda _e: self.render_all())
        ttk.Label(left, text="样本列表", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(14, 4))

        self.listbox = tk.Listbox(left, width=38, exportselection=False)
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_select_item)
        ttk.Label(left, textvariable=self.summary_status, foreground="#475569").pack(anchor="w", pady=(6, 0))

        toolbar = ttk.Frame(center)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="上一张", command=self.go_previous).pack(side="left")
        ttk.Button(toolbar, text="下一张", command=self.go_next).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="打开预览图", command=self.open_preview_image).pack(side="left", padx=(16, 0))
        ttk.Button(toolbar, text="打开图片文件夹", command=self.open_image_folder).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="导出 Gate 报告", command=self.export_gate_report).pack(side="left", padx=(8, 0))

        preview_card = ttk.Frame(center, relief="groove", padding=10)
        preview_card.grid(row=1, column=0, sticky="nsew")
        preview_card.rowconfigure(0, weight=1)
        preview_card.columnconfigure(0, weight=1)
        self.preview_label = ttk.Label(preview_card, anchor="center", justify="center", text="正在加载预览图...")
        self.preview_label.grid(row=0, column=0, sticky="nsew")
        ttk.Label(preview_card, textvariable=self.preview_status, foreground="#475569", justify="left").grid(row=1, column=0, sticky="ew", pady=(10, 0))

        details = ttk.Frame(center, padding=(0, 10, 0, 0))
        details.grid(row=2, column=0, sticky="ew")
        self.detail_text = tk.Text(details, height=10, wrap="word")
        self.detail_text.pack(fill="both", expand=True)
        self.detail_text.configure(state="disabled")

        ttk.Label(right, text="问题类型", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.issue_buttons: dict[str, ttk.Button] = {}
        for issue in ISSUE_TYPES:
            button = ttk.Button(right, text=issue_label(issue), command=lambda issue_name=issue: self.set_issue(issue_name))
            button.pack(fill="x", pady=2)
            self.issue_buttons[issue] = button

        ttk.Label(right, text="审核备注", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(14, 4))
        self.notes_text = tk.Text(right, width=34, height=10, wrap="word")
        self.notes_text.pack(fill="x")

        actions = ttk.Frame(right)
        actions.pack(fill="x", pady=(12, 0))
        ttk.Button(actions, text="保存", command=self.save_current).pack(fill="x")
        ttk.Button(actions, text="保存并下一张", command=lambda: self.save_current(go_next=True)).pack(fill="x", pady=6)

        ttk.Label(right, textvariable=self.save_status, foreground="#475569", justify="left").pack(anchor="w", pady=(8, 0))
        ttk.Separator(right).pack(fill="x", pady=12)
        ttk.Label(right, text="Gate / 统计", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(right, textvariable=self.gate_status, foreground="#1d4ed8", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(6, 0))
        ttk.Label(right, textvariable=self.stats_status, justify="left").pack(anchor="w", pady=(6, 0))

    def _bind_shortcuts(self) -> None:
        for key, issue in ISSUE_SHORTCUTS.items():
            self.root.bind(key, lambda _e, issue_name=issue: self.set_issue(issue_name))
        self.root.bind("<Control-s>", lambda _e: self.save_current() or "break")
        self.root.bind("<Return>", lambda _e: self.save_current(go_next=True) or "break")
        self.root.bind("<a>", lambda _e: self.go_previous() or "break")
        self.root.bind("<A>", lambda _e: self.go_previous() or "break")
        self.root.bind("<d>", lambda _e: self.go_next() or "break")
        self.root.bind("<D>", lambda _e: self.go_next() or "break")
        self.root.bind("<o>", lambda _e: self.open_preview_image() or "break")
        self.root.bind("<O>", lambda _e: self.open_preview_image() or "break")

    def current_item(self) -> dict[str, Any] | None:
        if not self.filtered_items:
            return None
        return self.filtered_items[self.current_index]

    def item_matches_filter(self, item: dict[str, Any]) -> bool:
        class_filter = self.class_filter_map.get(self.class_filter.get(), "all")
        status_filter = self.status_filter_map.get(self.status_filter.get(), "all")
        if class_filter != "all" and item["class_name"] != class_filter:
            return False
        if status_filter == "unreviewed":
            return item["review_status"] != "reviewed"
        if status_filter == "reviewed":
            return item["review_status"] == "reviewed"
        if status_filter == "issue_only":
            return item["review_status"] == "reviewed" and item["issue_type"] and item["issue_type"] != "ok"
        return True

    def recompute_filtered_items(self) -> None:
        current_id = self.current_review_id
        self.filtered_items = [item for item in self.items if self.item_matches_filter(item)]
        next_index = next((idx for idx, item in enumerate(self.filtered_items) if item["review_id"] == current_id), -1)
        if next_index < 0:
            next_index = next((idx for idx, item in enumerate(self.filtered_items) if item["review_status"] != "reviewed"), 0)
        self.current_index = max(0, min(next_index, max(0, len(self.filtered_items) - 1)))
        self.current_review_id = self.filtered_items[self.current_index]["review_id"] if self.filtered_items else None

    def render_list(self) -> None:
        self.listbox.delete(0, tk.END)
        for item in self.filtered_items:
            issue_text = issue_label(item['issue_type']) if item['issue_type'] else "-"
            self.listbox.insert(tk.END, f"{item['review_id']} | {class_label(item['class_name'])} | {status_label(item['review_status'])} | {issue_text}")
        if self.filtered_items:
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(self.current_index)
            self.listbox.see(self.current_index)
        self.summary_status.set(f"当前筛选：{len(self.filtered_items)} / 总计：{len(self.items)}")

    def render_details(self, item: dict[str, Any] | None) -> None:
        if not item:
            self.preview_label.configure(text="当前筛选下没有样本。", image="")
            self.preview_status.set("")
            self._set_detail_text("当前筛选下没有样本。")
            self.notes_text.delete("1.0", tk.END)
            self.selected_issue.set("")
            return

        self.notes_text.delete("1.0", tk.END)
        self.notes_text.insert("1.0", item["reviewer_notes"])
        self.selected_issue.set(item["issue_type"])

        preview_lines = [
            f"{field_label('review_id')}：{item['review_id']}",
            f"{field_label('class_name')}：{class_label(item['class_name'])}",
            f"{field_label('split')}：{item['split']}",
            f"{field_label('bbox_count')}：{item['bbox_count']}",
            f"{field_label('visual_preview_path')}：{item['visual_preview_path'] or '-'}",
        ]
        self.preview_status.set("\n".join(preview_lines))
        self._render_preview(item)

        detail_lines = [
            f"{field_label('review_id')}：{item['review_id']}",
            f"{field_label('class_name')}：{class_label(item['class_name'])}",
            f"{field_label('split')}：{item['split']}",
            f"{field_label('review_status')}：{status_label(item['review_status'])}",
            f"{field_label('issue_type')}：{issue_label(item['issue_type']) if item['issue_type'] else '-'}",
            f"{field_label('bbox_count')}：{item['bbox_count']}",
            f"{field_label('mean_bbox_area')}：{item['mean_bbox_area']:.10f}",
            f"{field_label('median_bbox_area')}：{item['median_bbox_area']:.10f}",
            f"{field_label('selection_reason')}：{item['selection_reason'] or '-'}",
            f"{field_label('infer_zero_detection')}：{item['infer_zero_detection']}",
            f"{field_label('infer_low_conf_detection')}：{item['infer_low_conf_detection']}",
            f"{field_label('infer_max_confidence')}：{item['infer_max_confidence']}",
            f"{field_label('image_path')}：{item['image_path']}",
            f"{field_label('label_path')}：{item['label_path']}",
            f"{field_label('source_original_path')}：{item['source_original_path']}",
            f"{field_label('visual_preview_path')}：{item['visual_preview_path'] or '-'}",
            "",
            "快捷键说明：",
            "1 = 正常",
            "2 = 类别错误",
            "3 = 漏框",
            "4 = 框太大",
            "5 = 框太小",
            "6 = 目标太小",
            "7 = 症状不清楚",
            "8 = 图像质量差",
            "9 = 其他",
            "0 = 框位置错误",
            "A = 上一张",
            "D = 下一张",
            "Ctrl+S = 保存",
            "Enter = 保存并下一张",
            "O = 打开预览图",
        ]
        self._set_detail_text("\n".join(detail_lines))

    def _set_detail_text(self, text: str) -> None:
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", text)
        self.detail_text.configure(state="disabled")

    def _render_preview(self, item: dict[str, Any]) -> None:
        preview_path = self.store.get_preview_path(item)
        if preview_path is None:
            self.current_image_ref = None
            self.preview_label.configure(text="Preview not found.\nUse Open Preview Image to inspect source file.", image="")
            return

        if not PILLOW_AVAILABLE:
            self.current_image_ref = None
            self.preview_label.configure(text="Pillow unavailable.\nUse Open Preview Image to inspect preview JPG.", image="")
            return

        try:
            image = Image.open(preview_path)
            image.thumbnail((860, 560))
            photo = ImageTk.PhotoImage(image)
            self.current_image_ref = photo
            self.preview_label.configure(image=photo, text="")
        except Exception as exc:
            self.current_image_ref = None
            self.logger.exception("Preview render failed for %s", preview_path)
            self.preview_label.configure(text=f"预览图渲染失败：{exc}\n请点击“打开预览图”查看。", image="")

    def render_stats(self) -> None:
        summary = self.store.compute_summary()
        self.gate_status.set(f"当前 Gate：{gate_label(summary['gate'])}")
        lines = [
            f"总样本数：{summary['total']}",
            f"已审核：{summary['reviewed']}",
            f"未审核：{summary['unreviewed']}",
        ]
        for class_name in WEAK_CLASSES:
            stats = summary["per_class"][class_name]
            lines.append(
                f"{class_label(class_name)}：ok_ratio={stats['ok_ratio']:.4f} | severe_issue_ratio={stats['severe_issue_ratio']:.4f}"
            )
        self.stats_status.set("\n".join(lines))

    def render_all(self) -> None:
        self.recompute_filtered_items()
        self.render_list()
        self.render_details(self.current_item())
        self.render_stats()

    def _on_select_item(self, _event: Any) -> None:
        if not self.listbox.curselection():
            return
        self.current_index = self.listbox.curselection()[0]
        if self.filtered_items:
            self.current_review_id = self.filtered_items[self.current_index]["review_id"]
        self.render_details(self.current_item())

    def set_issue(self, issue_name: str) -> None:
        self.selected_issue.set(issue_name)
        self.save_status.set(f"已选择问题类型：{issue_label(issue_name)}")

    def go_previous(self) -> None:
        if not self.filtered_items:
            return
        self.current_index = max(0, self.current_index - 1)
        self.current_review_id = self.filtered_items[self.current_index]["review_id"]
        self.render_all()

    def go_next(self) -> None:
        if not self.filtered_items:
            return
        self.current_index = min(len(self.filtered_items) - 1, self.current_index + 1)
        self.current_review_id = self.filtered_items[self.current_index]["review_id"]
        self.render_all()

    def save_current(self, go_next: bool = False) -> None:
        item = self.current_item()
        if not item:
            return
        issue_type = self.selected_issue.get().strip()
        notes = self.notes_text.get("1.0", tk.END).strip()
        try:
            self.store.save_decision(item["review_id"], issue_type, notes)
            self.save_status.set(f"已保存：{item['review_id']} @ {item['reviewed_at'] or now_iso()}")
            self.render_all()
            if go_next:
                self.go_next()
        except Exception as exc:
            self.logger.exception("Save failed for %s", item["review_id"])
            messagebox.showerror("保存失败", f"无法保存审核结果。\n\n{exc}\n\n请先关闭占用输出文件的 Excel 或其他程序。")
            self.save_status.set(f"保存失败：{exc}")

    def open_preview_image(self) -> None:
        item = self.current_item()
        if not item:
            return
        preview_path = self.store.get_preview_path(item)
        target = preview_path or Path(item["image_path"])
        try:
            os.startfile(str(target))  # type: ignore[attr-defined]
        except Exception as exc:
            self.logger.exception("Open preview failed for %s", target)
            messagebox.showerror("打开预览图失败", str(exc))

    def open_image_folder(self) -> None:
        item = self.current_item()
        if not item:
            return
        target = Path(item["image_path"]).parent
        try:
            os.startfile(str(target))  # type: ignore[attr-defined]
        except Exception:
            try:
                subprocess.Popen(["explorer", str(target)])
            except Exception as exc:
                self.logger.exception("Open image folder failed for %s", target)
                messagebox.showerror("打开图片文件夹失败", str(exc))

    def export_gate_report(self) -> None:
        try:
            self.store.persist(reason="manual_export_gate_report")
            self.save_status.set("已导出 Gate 报告。")
            self.render_stats()
        except Exception as exc:
            self.logger.exception("Export gate report failed")
            messagebox.showerror("导出 Gate 报告失败", str(exc))


def validate_required_inputs(items_csv: Path, output_root: Path, logger: logging.Logger) -> None:
    required = [
        items_csv,
        output_root / "visual_samples" / "index.md",
        output_root / "visual_samples" / "summary.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        logger.error("Missing required input files: %s", missing)
        raise FileNotFoundError("Missing required review inputs:\n" + "\n".join(missing))


def run_self_test(store: ReviewStore, logger: logging.Logger) -> None:
    summary = store.compute_summary()
    if summary["total"] != 300:
        raise RuntimeError(f"Expected 300 review items, got {summary['total']}")
    item = store.get_item("leaf_smut_001")
    preview_path = store.get_preview_path(item)
    logger.info("Self-test item loaded: review_id=%s preview_exists=%s pillow_available=%s", item["review_id"], bool(preview_path), PILLOW_AVAILABLE)
    snapshot = {
        "issue_type": item["issue_type"],
        "review_status": item["review_status"],
        "reviewer_notes": item["reviewer_notes"],
        "reviewed_at": item["reviewed_at"],
    }
    store.save_decision(item["review_id"], "ok", "self-test")
    item["issue_type"] = snapshot["issue_type"]
    item["review_status"] = snapshot["review_status"]
    item["reviewer_notes"] = snapshot["reviewer_notes"]
    item["reviewed_at"] = snapshot["reviewed_at"]
    store.persist(reason="self_test_restore")


def main() -> int:
    args = parse_args()
    root_path = repo_root()
    items_csv = resolve_path(args.items_csv)
    output_root = resolve_path(args.output_root)
    log_path = output_root / "review_desktop.log"
    logger = configure_logger(log_path)
    logger.info("==== Desktop review app startup ====")
    logger.info("start_time=%s", now_iso())
    logger.info("project_root=%s", root_path)
    logger.info("items_csv=%s", items_csv)
    logger.info("output_root=%s", output_root)
    logger.info("pillow_available=%s", PILLOW_AVAILABLE)

    try:
        validate_required_inputs(items_csv, output_root, logger)
        store = ReviewStore(items_csv=items_csv, output_root=output_root, logger=logger)
        if args.self_test:
            run_self_test(store, logger)
            print(json.dumps({"ok": True, "self_test": True, "items_loaded": len(store.items)}, ensure_ascii=False, indent=2))
            return 0

        root = tk.Tk()
        app = ReviewDesktopApp(root, store, logger)

        def report_callback_exception(exc: type[BaseException], value: BaseException, tb: Any) -> None:
            logger.error("Tkinter callback exception: %s", "".join(traceback.format_exception(exc, value, tb)))
            messagebox.showerror("程序异常", f"{value}\n\n请查看日志：\n{log_path}")

        root.report_callback_exception = report_callback_exception  # type: ignore[assignment]
        root.mainloop()
        logger.info("Desktop review app exited normally.")
        return 0
    except Exception as exc:
        logger.exception("Desktop review app failed to start.")
        try:
            messagebox.showerror("桌面审核工具启动失败", f"{exc}\n\n请查看日志：\n{log_path}")
        except Exception:
            pass
        print(f"Desktop review app failed: {exc}")
        print(f"Check log: {log_path}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
