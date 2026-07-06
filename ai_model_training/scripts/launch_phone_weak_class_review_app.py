"""Launch a stable local weak-class review app for Phone RiceLeafDiseaseBD."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import mimetypes
import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from collections import Counter
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


APP_TITLE = "Phone RiceLeafDiseaseBD 弱类标签人工审核台"
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
]
SEVERE_ISSUES = {"wrong_class", "missing_box", "over_boxed", "under_boxed"}
WEAK_CLASSES = ("leaf_smut", "tungro", "sheath_blight")
STATUS_ALL = {"unreviewed", "reviewed"}
LOGGER_NAME = "phone_weak_review_app"
JSON_CONTENT_TYPE = "application/json; charset=utf-8"
TEXT_CONTENT_TYPE = "text/plain; charset=utf-8"
HTML_CONTENT_TYPE = "text/html; charset=utf-8"
NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, max-age=0",
    "Pragma": "no-cache",
}
KNOWN_ROUTES = [
    "/",
    "/app.js",
    "/style.css",
    "/styles.css",
    "/healthz",
    "/api/healthz",
    "/api/bootstrap",
    "/api/items",
    "/api/items/{review_id}",
    "/api/state",
    "/api/summary",
    "/api/debug/routes",
    "/api/preview/{review_id}",
    "/api/preview-status/{review_id}",
    "/media/preview/{review_id}",
    "/api/decision",
    "/api/reset",
    "/static/app.js",
    "/static/style.css",
    "/static/styles.css",
    "/favicon.ico",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the local weak-class review app.")
    parser.add_argument("--items-csv", default="reports/weak_class_review/phone_riceleafdiseasebd_weak_class_review_items.csv")
    parser.add_argument("--output-root", default="reports/weak_class_review")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--backend", choices=("auto", "fastapi", "stdlib"), default="auto")
    parser.add_argument("--open-browser", action="store_true")
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
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.INFO)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

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
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def choose_port(host: str, start_port: int, logger: logging.Logger) -> int:
    end_port = 8797 if start_port <= 8797 else start_port + 10
    for port in range(start_port, end_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
            except OSError as exc:
                logger.warning("Port %s unavailable: %s", port, exc)
                continue
        if port != start_port:
            logger.warning("Port %s occupied. Falling back to %s.", start_port, port)
        return port
    raise RuntimeError(f"No available port found in range {start_port}-{end_port}.")


def required_paths(items_csv: Path, output_root: Path) -> dict[str, Path]:
    static_root = output_root / "review_app"
    visual_root = output_root / "visual_samples"
    return {
        "review_items.csv": items_csv,
        "visual_samples/index.md": visual_root / "index.md",
        "visual_samples/summary.json": visual_root / "summary.json",
        "review_app/index.html": static_root / "index.html",
        "review_app/app.js": static_root / "app.js",
        "review_app/style.css": static_root / "style.css",
        "review_app/styles.css": static_root / "styles.css",
    }


def validate_required_paths(items_csv: Path, output_root: Path, logger: logging.Logger) -> tuple[bool, dict[str, Path]]:
    paths = required_paths(items_csv, output_root)
    missing: list[str] = []
    for label, path in paths.items():
        if not path.exists():
            missing.append(f"{label} -> {path}")
    if missing:
        logger.error("Missing required review app files:")
        for line in missing:
            logger.error("  %s", line)
        logger.error("Fix suggestion: regenerate weak-class review assets or restore the review_app static files, then retry.")
        return False, paths
    return True, paths


class ReviewStore:
    def __init__(self, items_csv: Path, output_root: Path, logger: logging.Logger) -> None:
        self.items_csv = items_csv
        self.output_root = output_root
        self.static_root = output_root / "review_app"
        self.preview_root = output_root / "visual_samples"
        self.decisions_csv = output_root / "phone_riceleafdiseasebd_weak_class_review_decisions.csv"
        self.decisions_json = output_root / "phone_riceleafdiseasebd_weak_class_review_decisions.json"
        self.summary_json = output_root / "phone_riceleafdiseasebd_weak_class_review_summary.json"
        self.gate_report_md = output_root / "phone_riceleafdiseasebd_weak_class_review_gate_report.md"
        self.logger = logger
        self.lock = threading.RLock()
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
                }
                item["visual_preview_path"] = self._find_preview_path(item)
                items.append(item)
        self.items = items
        self.item_by_id = {item["review_id"]: item for item in items}
        self._overlay_saved_decisions()
        self._bootstrap_outputs()

    def _find_preview_path(self, item: dict[str, Any]) -> str:
        review_id = item["review_id"]
        split = item["split"]
        class_name = item["class_name"]
        image_name = Path(item["image_path"]).name
        try:
            index = int(review_id.rsplit("_", 1)[-1])
        except ValueError:
            return ""
        class_dir = self.preview_root / class_name
        prefix = f"{index:03d}_{split}_"
        matches = sorted(class_dir.glob(prefix + "*"))
        if matches:
            return str(matches[0].resolve())
        fallback = class_dir / f"{index:03d}_{split}_{image_name}"
        return str(fallback.resolve()) if fallback.exists() else ""

    def _overlay_saved_decisions(self) -> None:
        if not self.decisions_csv.exists():
            return
        with self.decisions_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                item = self.item_by_id.get((row.get("review_id") or "").strip())
                if not item:
                    continue
                issue_type = normalize_issue(row.get("issue_type", ""))
                item["issue_type"] = issue_type
                item["review_status"] = normalize_status(row.get("review_status", ""), issue_type)
                item["reviewer_notes"] = (row.get("reviewer_notes") or "").strip()
                item["reviewed_at"] = (row.get("reviewed_at") or "").strip()
                preview_path = (row.get("visual_preview_path") or "").strip()
                if preview_path:
                    item["visual_preview_path"] = preview_path

    def _bootstrap_outputs(self) -> None:
        missing_outputs = [
            path
            for path in (self.decisions_csv, self.decisions_json, self.summary_json, self.gate_report_md)
            if not path.exists()
        ]
        if not missing_outputs:
            return
        try:
            self.persist(reason="startup_bootstrap")
        except Exception:
            self.logger.warning("Startup bootstrap write skipped: %s", traceback.format_exc().strip())

    def build_item_payload(self, item: dict[str, Any]) -> dict[str, Any]:
        payload = dict(item)
        payload["preview_url"] = f"/api/preview/{item['review_id']}"
        payload["preview_status_url"] = f"/api/preview-status/{item['review_id']}"
        payload["current_target_type"] = "disease"
        payload["category_type"] = "disease"
        return payload

    def list_items(self) -> list[dict[str, Any]]:
        with self.lock:
            return [self.build_item_payload(item) for item in self.items]

    def get_item(self, review_id: str) -> dict[str, Any]:
        with self.lock:
            item = self.item_by_id.get(review_id)
            if not item:
                raise KeyError(review_id)
            return self.build_item_payload(item)

    def get_preview_path(self, review_id: str) -> Path:
        with self.lock:
            item = self.item_by_id.get(review_id)
            if not item:
                raise KeyError(review_id)
            preview_raw = (item.get("visual_preview_path") or "").strip()
            if not preview_raw:
                raise FileNotFoundError(f"preview path is empty for {review_id}")
            preview_path = Path(preview_raw).resolve()
            preview_root = self.preview_root.resolve()
            preview_path.relative_to(preview_root)
            return preview_path

    def get_preview_status(self, review_id: str) -> dict[str, Any]:
        payload = self.get_item(review_id)
        preview_path = payload.get("visual_preview_path") or ""
        result = {
            "review_id": review_id,
            "visual_preview_path": preview_path,
            "served_url": f"/api/preview/{review_id}",
            "exists": False,
            "size_bytes": 0,
            "error": None,
        }
        try:
            preview_resolved = self.get_preview_path(review_id)
            result["exists"] = preview_resolved.exists() and preview_resolved.is_file()
            if result["exists"]:
                result["size_bytes"] = preview_resolved.stat().st_size
        except KeyError:
            raise
        except Exception as exc:
            result["error"] = str(exc)
        return result

    def health_summary(self, backend_name: str) -> dict[str, Any]:
        return {
            "ok": True,
            "items_loaded": len(self.items),
            "backend": backend_name,
            "review_items_exists": self.items_csv.exists(),
            "visual_samples_exists": self.preview_root.exists(),
        }

    def save_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        review_id = str(payload.get("review_id", "")).strip()
        issue_type = normalize_issue(str(payload.get("issue_type", "")).strip())
        reviewer_notes = str(payload.get("reviewer_notes", "")).strip()
        requested_status = str(payload.get("review_status", "")).strip().lower()
        with self.lock:
            item = self.item_by_id.get(review_id)
            if not item:
                raise KeyError(review_id)
            if not issue_type:
                raise ValueError("issue_type is required")
            previous = dict(item)
            item["issue_type"] = issue_type
            item["review_status"] = requested_status if requested_status in STATUS_ALL else "reviewed"
            item["reviewer_notes"] = reviewer_notes
            item["reviewed_at"] = now_iso()
            try:
                self.persist(reason=f"save_decision:{review_id}")
            except Exception:
                item.clear()
                item.update(previous)
                raise
            return self.build_item_payload(item)

    def clear_decisions(self) -> None:
        with self.lock:
            snapshot = [dict(item) for item in self.items]
            snapshot_map = {item["review_id"]: item for item in snapshot}
            for item in self.items:
                item["issue_type"] = ""
                item["review_status"] = "unreviewed"
                item["reviewer_notes"] = ""
                item["reviewed_at"] = ""
            try:
                self.persist(reason="reset")
            except Exception:
                self.items = snapshot
                self.item_by_id = snapshot_map
                raise

    def _systemic_flags(self, per_class: dict[str, dict[str, Any]]) -> list[str]:
        flags: list[str] = []
        for class_name, stats in per_class.items():
            reviewed = stats["reviewed"]
            if reviewed <= 0:
                continue
            threshold = max(10, math.ceil(reviewed * 0.10))
            issue_counts = stats["issue_counts"]
            for issue_name in ("wrong_class", "missing_box"):
                if issue_counts.get(issue_name, 0) >= threshold:
                    flags.append(f"{class_name}:{issue_name}")
            bbox_inconsistent = issue_counts.get("over_boxed", 0) + issue_counts.get("under_boxed", 0)
            if bbox_inconsistent >= threshold:
                flags.append(f"{class_name}:bbox_granularity_inconsistency")
        return sorted(set(flags))

    def compute_summary(self) -> dict[str, Any]:
        with self.lock:
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
            "- This round records manual decisions only. No training, no label edits, no formal metrics.",
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
            "| class_name | total | reviewed | ok_count | severe_issue_count | non_severe_issue_count | ok_ratio | severe_issue_ratio |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for class_name in WEAK_CLASSES:
            stats = summary["per_class"][class_name]
            lines.append(
                f"| {class_name} | {stats['total']} | {stats['reviewed']} | {stats['ok_count']} | "
                f"{stats['severe_issue_count']} | {stats['non_severe_issue_count']} | "
                f"{stats['ok_ratio']:.4f} | {stats['severe_issue_ratio']:.4f} |"
            )

        lines.extend(["", "## Issue Breakdown", ""])
        for class_name in WEAK_CLASSES:
            stats = summary["per_class"][class_name]
            lines.append(f"### {class_name}")
            lines.append("")
            if not stats["issue_counts"]:
                lines.append("- no reviewed issues yet")
            else:
                for issue_name, count in stats["issue_counts"].items():
                    lines.append(f"- {issue_name}: `{count}`")
            lines.append("")

        lines.extend(
            [
                "## Gate Rules",
                "",
                "- PASS: all 300 reviewed and every weak class has ok_ratio >= 0.80 plus severe_issue_ratio <= 0.15.",
                "- WARNING: all 300 reviewed and any weak class falls into ok_ratio [0.70, 0.80) or severe_issue_ratio (0.15, 0.20].",
                "- FAIL: any weak class has ok_ratio < 0.70 or severe_issue_ratio > 0.20, or a systemic annotation problem is detected.",
                "- PENDING: review is not complete yet.",
                "",
                "## Current Conclusion",
                "",
            ]
        )
        if summary["reasons"]:
            for reason in summary["reasons"]:
                lines.append(f"- {reason}")
        else:
            lines.append("- no blocking reason recorded")

        if summary["systemic_flags"]:
            lines.extend(["", "## Systemic Flags", ""])
            for flag in summary["systemic_flags"]:
                lines.append(f"- {flag}")

        lines.extend(
            [
                "",
                "## Boundary",
                "",
                "- not training",
                "- not a model metric report",
                "- not editing labels",
                "- manual review records and gate stats only",
                "",
            ]
        )
        return "\n".join(lines)

    def persist(self, reason: str) -> None:
        summary = self.compute_summary()
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

        fieldnames = [
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

        atomic_write_csv(self.decisions_csv, fieldnames, rows)
        atomic_write_json(
            self.decisions_json,
            {
                "generated_at": summary["generated_at"],
                "total_items": len(rows),
                "items": rows,
            },
        )
        atomic_write_json(self.summary_json, summary)
        atomic_write_text(self.gate_report_md, self.build_gate_report(summary) + "\n", encoding="utf-8")
        self.logger.info("Persisted review outputs (%s).", reason)


class ReviewApplication:
    def __init__(self, store: ReviewStore, backend_name: str, logger: logging.Logger) -> None:
        self.store = store
        self.backend_name = backend_name
        self.logger = logger
        self.static_root = store.static_root
        self.preview_root = store.preview_root.resolve()


class ReviewRequestHandler(BaseHTTPRequestHandler):
    server_version = "PhoneWeakReviewHTTP/1.2"

    @property
    def app(self) -> ReviewApplication:
        return self.server.app  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        self.app.logger.info("HTTP %s - %s", self.address_string(), format % args)

    def do_GET(self) -> None:  # noqa: N802
        started = time.perf_counter()
        route = urlparse(self.path).path
        route = route or "/"
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        error_message: str | None = None
        extra: dict[str, Any] = {}
        try:
            status_code, extra = self._do_get_impl(route)
        except (BrokenPipeError, ConnectionResetError) as exc:
            status_code = HTTPStatus.INTERNAL_SERVER_ERROR
            error_message = exc.__class__.__name__
            self.app.logger.warning("Client disconnected during GET %s: %s", route, exc)
            self.close_connection = True
        except Exception as exc:
            error_message = f"{exc.__class__.__name__}: {exc}"
            self.app.logger.exception("Unhandled GET error for %s", route)
            self._safe_json_response({"ok": False, "error": "internal_server_error"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        finally:
            self._log_request_summary("GET", route, status_code, started, error_message=error_message, extra=extra)

    def do_POST(self) -> None:  # noqa: N802
        started = time.perf_counter()
        route = urlparse(self.path).path
        route = route or "/"
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        error_message: str | None = None
        extra: dict[str, Any] = {}
        try:
            status_code, extra = self._do_post_impl(route)
        except (BrokenPipeError, ConnectionResetError) as exc:
            status_code = HTTPStatus.INTERNAL_SERVER_ERROR
            error_message = exc.__class__.__name__
            self.app.logger.warning("Client disconnected during POST %s: %s", route, exc)
            self.close_connection = True
        except Exception as exc:
            error_message = f"{exc.__class__.__name__}: {exc}"
            self.app.logger.exception("Unhandled POST error for %s", route)
            self._safe_json_response({"ok": False, "error": "internal_server_error"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        finally:
            self._log_request_summary("POST", route, status_code, started, error_message=error_message, extra=extra)

    def _do_get_impl(self, route: str) -> tuple[HTTPStatus, dict[str, Any]]:
        if route == "/":
            return self._safe_file_response(self.app.static_root / "index.html", content_type=HTML_CONTENT_TYPE)
        if route == "/app.js":
            return self._safe_file_response(self.app.static_root / "app.js")
        if route == "/style.css":
            return self._safe_file_response(self.app.static_root / "style.css")
        if route == "/styles.css":
            return self._safe_file_response(self.app.static_root / "styles.css")
        if route.startswith("/static/"):
            return self._safe_file_response(self.app.static_root / route.removeprefix("/static/"))
        if route == "/favicon.ico":
            return self._safe_empty_response(status=HTTPStatus.NO_CONTENT)
        if route in {"/healthz", "/api/healthz"}:
            return self._safe_json_response(self.app.store.health_summary(self.app.backend_name))
        if route == "/api/debug/routes":
            return self._safe_json_response({"ok": True, "routes": KNOWN_ROUTES})
        if route == "/api/bootstrap":
            return self._safe_json_response(
                {
                    "app_title": APP_TITLE,
                    "backend": self.app.backend_name,
                    "issue_types": ISSUE_TYPES,
                    "severe_issues": sorted(SEVERE_ISSUES),
                    "items": self.app.store.list_items(),
                    "state": self.app.store.compute_summary(),
                }
            )
        if route == "/api/items":
            return self._safe_json_response({"items": self.app.store.list_items()})
        if route.startswith("/api/items/"):
            review_id = self._extract_review_id(route)
            if not review_id:
                return self._safe_json_response({"ok": False, "error": "invalid_review_id"}, status=HTTPStatus.BAD_REQUEST)
            try:
                return self._safe_json_response(self.app.store.get_item(review_id))
            except KeyError:
                return self._safe_json_response({"ok": False, "error": "not_found"}, status=HTTPStatus.NOT_FOUND)
        if route in {"/api/state", "/api/summary"}:
            return self._safe_json_response(self.app.store.compute_summary())
        if route.startswith("/api/preview-status/"):
            review_id = self._extract_review_id(route)
            if not review_id:
                return self._safe_json_response({"ok": False, "error": "invalid_review_id"}, status=HTTPStatus.BAD_REQUEST)
            try:
                status_payload = self.app.store.get_preview_status(review_id)
            except KeyError:
                return self._safe_json_response({"ok": False, "error": "not_found"}, status=HTTPStatus.NOT_FOUND)
            http_status = HTTPStatus.OK if status_payload["exists"] else HTTPStatus.NOT_FOUND
            return self._safe_json_response(status_payload, status=http_status)
        if route.startswith("/api/preview/") or route.startswith("/media/preview/"):
            review_id = self._extract_review_id(route)
            if not review_id:
                return self._safe_json_response({"ok": False, "error": "invalid_review_id"}, status=HTTPStatus.BAD_REQUEST)
            return self._serve_preview(review_id)
        return self._safe_json_response({"ok": False, "error": "not_found"}, status=HTTPStatus.NOT_FOUND)

    def _do_post_impl(self, route: str) -> tuple[HTTPStatus, dict[str, Any]]:
        if route == "/api/decision":
            payload = self._read_json_body()
            if payload is None:
                return self._safe_json_response({"ok": False, "error": "invalid_json"}, status=HTTPStatus.BAD_REQUEST)
            try:
                item = self.app.store.save_decision(payload)
            except KeyError:
                return self._safe_json_response({"ok": False, "error": "not_found"}, status=HTTPStatus.NOT_FOUND)
            except ValueError as exc:
                return self._safe_json_response({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self.app.logger.exception("Save decision failed for payload=%s", payload)
                return self._safe_json_response(
                    {"ok": False, "error": "save_failed", "detail": str(exc)},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return self._safe_json_response({"ok": True, "saved": True, "item": item, "state": self.app.store.compute_summary()})

        if route == "/api/reset":
            try:
                self.app.store.clear_decisions()
            except Exception as exc:
                self.app.logger.exception("Reset decisions failed")
                return self._safe_json_response(
                    {"ok": False, "error": "reset_failed", "detail": str(exc)},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return self._safe_json_response({"ok": True, "reset": True, "state": self.app.store.compute_summary()})

        return self._safe_json_response({"ok": False, "error": "not_found"}, status=HTTPStatus.NOT_FOUND)

    def _extract_review_id(self, route: str) -> str:
        review_id = route.rsplit("/", 1)[-1].strip()
        return unquote(review_id)

    def _read_json_body(self) -> dict[str, Any] | None:
        length = parse_int(self.headers.get("Content-Length"), 0)
        try:
            raw = self.rfile.read(length) if length > 0 else b"{}"
        except (BrokenPipeError, ConnectionResetError):
            raise
        except Exception:
            self.app.logger.exception("Failed reading request body for %s", self.path)
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return None

    def _serve_preview(self, review_id: str) -> tuple[HTTPStatus, dict[str, Any]]:
        extra: dict[str, Any] = {"review_id": review_id}
        try:
            preview_path = self.app.store.get_preview_path(review_id)
            preview_status = self.app.store.get_preview_status(review_id)
            extra.update(
                {
                    "image_path": str(preview_path),
                    "exists": preview_status["exists"],
                    "size_bytes": preview_status["size_bytes"],
                }
            )
        except KeyError:
            return self._safe_json_response({"ok": False, "error": "not_found"}, status=HTTPStatus.NOT_FOUND, extra=extra)
        except ValueError as exc:
            extra["error"] = str(exc)
            return self._safe_json_response({"ok": False, "error": "forbidden"}, status=HTTPStatus.FORBIDDEN, extra=extra)
        except Exception as exc:
            extra["error"] = str(exc)
            return self._safe_json_response({"ok": False, "error": "preview_unavailable"}, status=HTTPStatus.NOT_FOUND, extra=extra)

        if not preview_path.exists() or not preview_path.is_file():
            return self._safe_json_response({"ok": False, "error": "preview_missing"}, status=HTTPStatus.NOT_FOUND, extra=extra)
        return self._safe_file_response(preview_path, extra=extra)

    def _safe_empty_response(self, status: HTTPStatus = HTTPStatus.NO_CONTENT) -> tuple[HTTPStatus, dict[str, Any]]:
        self.send_response(status)
        for header_name, header_value in NO_CACHE_HEADERS.items():
            self.send_header(header_name, header_value)
        self.send_header("Content-Length", "0")
        self.end_headers()
        return status, {}

    def _safe_json_response(
        self,
        payload: Any,
        status: HTTPStatus = HTTPStatus.OK,
        extra: dict[str, Any] | None = None,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", JSON_CONTENT_TYPE)
        self.send_header("Content-Length", str(len(raw)))
        for header_name, header_value in NO_CACHE_HEADERS.items():
            self.send_header(header_name, header_value)
        self.end_headers()
        self.wfile.write(raw)
        return status, extra or {}

    def _safe_text_response(self, text: str, status: HTTPStatus = HTTPStatus.OK) -> tuple[HTTPStatus, dict[str, Any]]:
        raw = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", TEXT_CONTENT_TYPE)
        self.send_header("Content-Length", str(len(raw)))
        for header_name, header_value in NO_CACHE_HEADERS.items():
            self.send_header(header_name, header_value)
        self.end_headers()
        self.wfile.write(raw)
        return status, {}

    def _safe_file_response(
        self,
        path: Path,
        content_type: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        if not path.exists() or not path.is_file():
            return self._safe_json_response({"ok": False, "error": "not_found"}, status=HTTPStatus.NOT_FOUND, extra=extra)
        body = path.read_bytes()
        mime = content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        for header_name, header_value in NO_CACHE_HEADERS.items():
            self.send_header(header_name, header_value)
        self.end_headers()
        self.wfile.write(body)
        return HTTPStatus.OK, extra or {}

    def _log_request_summary(
        self,
        method: str,
        route: str,
        status_code: HTTPStatus,
        started: float,
        error_message: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        suffix_parts = [f"duration_ms={duration_ms}"]
        if extra:
            for key, value in extra.items():
                suffix_parts.append(f"{key}={value}")
        if error_message:
            suffix_parts.append(f"error={error_message}")
        self.app.logger.info("%s %s -> %s | %s", method, route, int(status_code), " | ".join(suffix_parts))


class StdlibReviewServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], app: ReviewApplication) -> None:
        super().__init__(server_address, ReviewRequestHandler)
        self.app = app

    def handle_error(self, request: Any, client_address: Any) -> None:
        self.app.logger.exception("ThreadingHTTPServer handler error for client=%s", client_address)


def build_fastapi_app(store: ReviewStore, logger: logging.Logger) -> Any:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse, JSONResponse, Response
    from fastapi.staticfiles import StaticFiles

    app = FastAPI(title=APP_TITLE)
    app.mount("/static", StaticFiles(directory=str(store.static_root)), name="static")

    @app.get("/")
    def root() -> FileResponse:
        return FileResponse(store.static_root / "index.html", media_type=HTML_CONTENT_TYPE)

    @app.get("/app.js")
    def app_js() -> FileResponse:
        return FileResponse(store.static_root / "app.js", headers=NO_CACHE_HEADERS)

    @app.get("/style.css")
    def style_css() -> FileResponse:
        return FileResponse(store.static_root / "style.css", headers=NO_CACHE_HEADERS)

    @app.get("/styles.css")
    def styles_css() -> FileResponse:
        return FileResponse(store.static_root / "styles.css", headers=NO_CACHE_HEADERS)

    @app.get("/favicon.ico")
    def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/healthz")
    @app.get("/api/healthz")
    def healthz() -> dict[str, Any]:
        return store.health_summary("fastapi")

    @app.get("/api/debug/routes")
    def debug_routes() -> dict[str, Any]:
        return {"ok": True, "routes": KNOWN_ROUTES}

    @app.get("/api/bootstrap")
    def bootstrap() -> dict[str, Any]:
        return {
            "app_title": APP_TITLE,
            "backend": "fastapi",
            "issue_types": ISSUE_TYPES,
            "severe_issues": sorted(SEVERE_ISSUES),
            "items": store.list_items(),
            "state": store.compute_summary(),
        }

    @app.get("/api/items")
    def items() -> dict[str, Any]:
        return {"items": store.list_items()}

    @app.get("/api/items/{review_id}")
    def item(review_id: str) -> dict[str, Any]:
        try:
            return store.get_item(review_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="not_found") from exc

    @app.get("/api/state")
    @app.get("/api/summary")
    def state() -> dict[str, Any]:
        return store.compute_summary()

    @app.get("/api/preview-status/{review_id}")
    def preview_status(review_id: str) -> JSONResponse:
        try:
            payload = store.get_preview_status(review_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="not_found") from exc
        return JSONResponse(payload, status_code=200 if payload["exists"] else 404)

    def _preview_response(review_id: str) -> FileResponse:
        try:
            preview_path = store.get_preview_path(review_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="not_found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if not preview_path.exists():
            raise HTTPException(status_code=404, detail="preview_missing")
        return FileResponse(preview_path, headers=NO_CACHE_HEADERS)

    @app.get("/api/preview/{review_id}")
    def preview_api(review_id: str) -> FileResponse:
        return _preview_response(review_id)

    @app.get("/media/preview/{review_id}")
    def preview_media(review_id: str) -> FileResponse:
        return _preview_response(review_id)

    @app.post("/api/decision")
    def save_decision(payload: dict[str, Any]) -> JSONResponse:
        try:
            item = store.save_decision(payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="not_found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Save decision failed for payload=%s", payload)
            return JSONResponse({"ok": False, "error": "save_failed", "detail": str(exc)}, status_code=500)
        return JSONResponse({"ok": True, "saved": True, "item": item, "state": store.compute_summary()})

    @app.post("/api/reset")
    def reset() -> JSONResponse:
        try:
            store.clear_decisions()
        except Exception as exc:
            logger.exception("Reset decisions failed")
            return JSONResponse({"ok": False, "error": "reset_failed", "detail": str(exc)}, status_code=500)
        return JSONResponse({"ok": True, "reset": True, "state": store.compute_summary()})

    return app


def maybe_open_browser(url: str, logger: logging.Logger) -> None:
    try:
        opened = webbrowser.open(url)
        logger.info("Browser open requested for %s (opened=%s).", url, opened)
    except Exception:
        logger.exception("Browser open failed for %s", url)


def run_stdlib(store: ReviewStore, host: str, port: int, logger: logging.Logger, open_browser: bool) -> None:
    app = ReviewApplication(store=store, backend_name="stdlib", logger=logger)
    server = StdlibReviewServer((host, port), app)
    url = f"http://{host}:{port}"
    logger.info("Backend: stdlib fallback")
    logger.info("Listening on %s", url)
    print(f"Review app ready at {url}")
    if open_browser:
        maybe_open_browser(url, logger)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Stopping stdlib server.")
    finally:
        server.server_close()
        logger.info("Stdlib server stopped.")


def run_fastapi(store: ReviewStore, host: str, port: int, logger: logging.Logger, open_browser: bool) -> None:
    import uvicorn

    app = build_fastapi_app(store, logger)
    url = f"http://{host}:{port}"
    logger.info("Backend: fastapi")
    logger.info("Listening on %s", url)
    print(f"Review app ready at {url}")
    if open_browser:
        maybe_open_browser(url, logger)
    try:
        uvicorn.run(app, host=host, port=port, log_level="warning")
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Stopping fastapi server.")
    finally:
        logger.info("FastAPI server stopped.")


def main() -> int:
    args = parse_args()
    root = repo_root()
    output_root = resolve_path(args.output_root)
    items_csv = resolve_path(args.items_csv)
    log_path = output_root / "review_app" / "server.log"
    logger = configure_logger(log_path)
    logger.info("==== Review app startup ====")
    logger.info("start_time=%s", now_iso())
    logger.info("project_root=%s", root)
    logger.info("review_items=%s", items_csv)
    logger.info("visual_samples=%s", output_root / "visual_samples")
    logger.info("decisions_csv=%s", output_root / "phone_riceleafdiseasebd_weak_class_review_decisions.csv")
    logger.info("requested_backend=%s", args.backend)
    logger.info("requested_host=%s requested_port=%s", args.host, args.port)

    valid, paths = validate_required_paths(items_csv, output_root, logger)
    if not valid:
        return 1

    for label, path in paths.items():
        logger.info("verified %s -> %s", label, path)

    try:
        store = ReviewStore(items_csv=items_csv, output_root=output_root, logger=logger)

        if args.backend in {"auto", "fastapi"}:
            try:
                import fastapi  # noqa: F401
                import uvicorn  # noqa: F401

                selected_port = choose_port(args.host, args.port, logger)
                run_fastapi(store, args.host, selected_port, logger, args.open_browser)
                return 0
            except Exception as exc:
                if args.backend == "fastapi":
                    logger.exception("FastAPI startup failed.")
                    print(f"FastAPI startup failed: {exc}")
                    return 1
                logger.warning("FastAPI unavailable, falling back to stdlib: %s", exc)

        selected_port = choose_port(args.host, args.port, logger)
        run_stdlib(store, args.host, selected_port, logger, args.open_browser)
        return 0
    except Exception as exc:
        logger.exception("Review app startup failed.")
        print(f"Review app startup failed: {exc}")
        print(f"Check server log: {log_path}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
