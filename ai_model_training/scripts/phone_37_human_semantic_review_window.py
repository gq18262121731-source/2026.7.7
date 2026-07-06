from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import os
import sys
import threading
import traceback
import webbrowser
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "reports" / "phone_37_human_review_or_larger_eval_set"
OUTPUT_DIR = ROOT / "reports" / "phone_37_human_semantic_review_window"

INPUT_PACKET = INPUT_DIR / "human_review_packet.csv"
INPUT_REPORT = INPUT_DIR / "phone_37_human_review_or_larger_eval_set_report.md"
INPUT_CLOSURE = INPUT_DIR / "closure_decision.json"
INPUT_SWEEP = INPUT_DIR / "larger_eval_threshold_sweep.csv"
INPUT_FP_SWEEP = INPUT_DIR / "larger_eval_false_positive_sweep.csv"
INPUT_FAILURES = INPUT_DIR / "larger_eval_failure_cases.csv"

REPORT_MD = OUTPUT_DIR / "phone_37_human_semantic_review_window_report.md"
CONTEXT_JSON = OUTPUT_DIR / "review_window_context.json"
DECISIONS_CSV = OUTPUT_DIR / "human_semantic_review_decisions.csv"
DECISIONS_JSON = OUTPUT_DIR / "human_semantic_review_decisions.json"
SUMMARY_CSV = OUTPUT_DIR / "human_semantic_review_summary.csv"
GATE_JSON = OUTPUT_DIR / "human_semantic_review_gate.json"
PROGRESS_JSON = OUTPUT_DIR / "review_progress.json"
SESSION_LOG_CSV = OUTPUT_DIR / "review_session_log.csv"
EXPORT_CSV = OUTPUT_DIR / "review_export_latest.csv"

ALLOWED_PORTS = [8767, 8768, 8769, 8770]

DECISION_OPTIONS = [
    "TRUE_TUNGRO_WEAK_CONFIDENCE",
    "FALSE_TUNGRO_PREDICTION",
    "BAD_LOCALIZATION_LABEL_OK",
    "BAD_LOCALIZATION_LABEL_NEEDS_FIX",
    "LABEL_AMBIGUOUS",
    "IMAGE_QUALITY_TOO_WEAK",
    "MODEL_REGRESSION_CONFIRMED",
    "MODEL_REGRESSION_NOT_CONFIRMED",
    "EXCLUDE_FROM_EVAL",
    "NEEDS_EXPERT_REVIEW",
    "UNREVIEWED",
]

DECISION_LABELS = {
    "TRUE_TUNGRO_WEAK_CONFIDENCE": "是真 Tungro，只是置信度低",
    "FALSE_TUNGRO_PREDICTION": "不是 Tungro，是误检",
    "BAD_LOCALIZATION_LABEL_OK": "定位差，但标签没问题",
    "BAD_LOCALIZATION_LABEL_NEEDS_FIX": "定位差，标签需要修",
    "LABEL_AMBIGUOUS": "标签语义模糊",
    "IMAGE_QUALITY_TOO_WEAK": "图像质量太差",
    "MODEL_REGRESSION_CONFIRMED": "确认模型回退",
    "MODEL_REGRESSION_NOT_CONFIRMED": "不算模型回退",
    "EXCLUDE_FROM_EVAL": "排除出评测",
    "NEEDS_EXPERT_REVIEW": "需要专家复核",
    "UNREVIEWED": "暂不判断",
}

STATUS_LABELS = {
    "pending": "待审核",
    "reviewed": "已审核",
    "needs_expert": "专家复核",
    "excluded": "已排除",
}

SAVE_FIELDS = [
    "review_id",
    "case_type",
    "split",
    "image_name",
    "image_path",
    "label_path",
    "baseline_status",
    "retry_status_conf025",
    "retry_status_conf015",
    "retry_status_conf010",
    "retry_status_conf005",
    "max_tungro_conf",
    "suggested_question",
    "human_decision",
    "human_notes",
    "review_status",
    "reviewed_at",
    "reviewer",
    "visualization_path",
]


HTML_PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Phone-37 Tungro 人工语义复核窗口</title>
  <style>
    body { font-family: "Microsoft YaHei", Arial, sans-serif; margin: 0; background: #f4f6f8; color: #1f2937; }
    .topbar { background: #111827; color: #fff; padding: 14px 18px; }
    .topbar h1 { margin: 0; font-size: 20px; }
    .topbar .meta { margin-top: 6px; font-size: 13px; color: #d1d5db; }
    .wrap { display: grid; grid-template-columns: 320px 1fr; gap: 16px; padding: 16px; }
    .panel { background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.12); padding: 14px; }
    .filters label, .field label { display: block; font-size: 13px; margin-bottom: 6px; color: #374151; }
    select, textarea, input, button { font: inherit; }
    select, textarea, input[type="text"] { width: 100%; box-sizing: border-box; border: 1px solid #d1d5db; border-radius: 6px; padding: 8px; background: #fff; }
    textarea { min-height: 88px; resize: vertical; }
    button { border: 0; border-radius: 6px; padding: 9px 12px; cursor: pointer; }
    .btn-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
    .primary { background: #2563eb; color: #fff; }
    .secondary { background: #e5e7eb; color: #111827; }
    .danger { background: #dc2626; color: #fff; }
    .info-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 10px; }
    .info-item { background: #f9fafb; border-radius: 6px; padding: 8px; font-size: 13px; }
    .info-item strong { display: block; color: #111827; margin-bottom: 4px; }
    .stats { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 8px; margin-bottom: 12px; }
    .stat { background: #f9fafb; border-radius: 6px; padding: 10px; text-align: center; }
    .stat .value { font-size: 20px; font-weight: 700; }
    .image-wrap { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 14px; }
    .image-card { background: #f9fafb; border-radius: 6px; padding: 8px; }
    .image-card h3 { margin: 0 0 8px 0; font-size: 14px; }
    .image-card img { width: 100%; height: auto; border-radius: 4px; background: #e5e7eb; min-height: 260px; object-fit: contain; }
    .decision-buttons { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 8px; margin-top: 10px; }
    .decision-btn.active { outline: 3px solid #2563eb; background: #dbeafe; }
    .footer-note { margin-top: 10px; font-size: 12px; color: #6b7280; }
    .missing { color: #b91c1c; font-weight: 700; }
    .list-meta { font-size: 12px; color: #6b7280; margin-top: 8px; }
    @media (max-width: 1100px) {
      .wrap { grid-template-columns: 1fr; }
      .image-wrap { grid-template-columns: 1fr; }
      .stats { grid-template-columns: repeat(2, minmax(0,1fr)); }
    }
  </style>
</head>
<body>
  <div class="topbar">
    <h1>Phone-37 Tungro 人工语义复核窗口</h1>
    <div class="meta" id="topMeta">加载中...</div>
  </div>
  <div class="wrap">
    <div class="panel filters">
      <div class="stats" id="stats"></div>
      <label>按 case_type 筛选</label>
      <select id="caseFilter"></select>
      <label style="margin-top:10px;">按 review_status 筛选</label>
      <select id="statusFilter"></select>
      <label style="margin-top:10px;">只看重点项</label>
      <select id="priorityFilter">
        <option value="all">全部</option>
        <option value="priority">重点项</option>
      </select>
      <div class="btn-row">
        <button class="secondary" id="prevBtn">上一条</button>
        <button class="secondary" id="nextBtn">下一条</button>
        <button class="primary" id="saveBtn">保存</button>
        <button class="primary" id="saveNextBtn">保存并下一条</button>
        <button class="secondary" id="exportBtn">导出结果</button>
      </div>
      <div class="list-meta" id="listMeta"></div>
      <div class="footer-note">
        快捷键：1-9/0/U 选择，S 保存，N 下一条，P 上一条
      </div>
    </div>
    <div class="panel">
      <div class="info-grid" id="infoGrid"></div>
      <div class="field" style="margin-top:12px;">
        <label>建议问题</label>
        <div id="questionText"></div>
      </div>
      <div class="field" style="margin-top:12px;">
        <label>人工结论</label>
        <div class="decision-buttons" id="decisionButtons"></div>
      </div>
      <div class="field" style="margin-top:12px;">
        <label for="notes">人工备注</label>
        <textarea id="notes" placeholder="填写你的语义判断、疑点、后续建议"></textarea>
      </div>
      <div class="image-wrap">
        <div class="image-card">
          <h3>当前可视化图</h3>
          <img id="vizImage" alt="visualization">
          <div id="vizPath" class="footer-note"></div>
        </div>
        <div class="image-card">
          <h3>原始图</h3>
          <img id="srcImage" alt="source">
          <div id="srcPath" class="footer-note"></div>
        </div>
      </div>
    </div>
  </div>
  <script>
    const DECISION_LABELS = {
      TRUE_TUNGRO_WEAK_CONFIDENCE: "是真 Tungro，只是置信度低",
      FALSE_TUNGRO_PREDICTION: "不是 Tungro，是误检",
      BAD_LOCALIZATION_LABEL_OK: "定位差，但标签没问题",
      BAD_LOCALIZATION_LABEL_NEEDS_FIX: "定位差，标签需要修",
      LABEL_AMBIGUOUS: "标签语义模糊",
      IMAGE_QUALITY_TOO_WEAK: "图像质量太差",
      MODEL_REGRESSION_CONFIRMED: "确认模型回退",
      MODEL_REGRESSION_NOT_CONFIRMED: "不算模型回退",
      EXCLUDE_FROM_EVAL: "排除出评测",
      NEEDS_EXPERT_REVIEW: "需要专家复核",
      UNREVIEWED: "暂不判断"
    };
    const HOTKEY_MAP = {
      "1": "TRUE_TUNGRO_WEAK_CONFIDENCE",
      "2": "FALSE_TUNGRO_PREDICTION",
      "3": "BAD_LOCALIZATION_LABEL_OK",
      "4": "BAD_LOCALIZATION_LABEL_NEEDS_FIX",
      "5": "LABEL_AMBIGUOUS",
      "6": "IMAGE_QUALITY_TOO_WEAK",
      "7": "MODEL_REGRESSION_CONFIRMED",
      "8": "MODEL_REGRESSION_NOT_CONFIRMED",
      "9": "EXCLUDE_FROM_EVAL",
      "0": "NEEDS_EXPERT_REVIEW",
      "u": "UNREVIEWED",
      "U": "UNREVIEWED"
    };

    let state = null;
    let filteredItems = [];
    let currentIndex = 0;
    let currentDecision = "UNREVIEWED";

    function esc(text) {
      return String(text ?? "").replace(/[&<>"']/g, (m) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
    }

    async function fetchState() {
      const res = await fetch('/api/state');
      state = await res.json();
      renderFilters();
      applyFilters();
    }

    function renderFilters() {
      const caseSet = Array.from(new Set(state.items.map((x) => x.case_type))).sort();
      const caseFilter = document.getElementById('caseFilter');
      caseFilter.innerHTML = `<option value="all">全部 case_type</option>` + caseSet.map((v) => `<option value="${esc(v)}">${esc(v)}</option>`).join('');
      const statusFilter = document.getElementById('statusFilter');
      statusFilter.innerHTML = [
        ['all', '全部状态'],
        ['pending', '待审核'],
        ['reviewed', '已审核'],
        ['needs_expert', '专家复核'],
        ['excluded', '已排除']
      ].map(([v, t]) => `<option value="${v}">${t}</option>`).join('');
    }

    function applyFilters() {
      const caseFilter = document.getElementById('caseFilter').value || 'all';
      const statusFilter = document.getElementById('statusFilter').value || 'all';
      const priorityFilter = document.getElementById('priorityFilter').value || 'all';
      filteredItems = state.items.filter((item) => {
        if (caseFilter !== 'all' && item.case_type !== caseFilter) return false;
        if (statusFilter !== 'all' && item.review_status !== statusFilter) return false;
        if (priorityFilter === 'priority' && !item.priority) return false;
        return true;
      });
      if (currentIndex >= filteredItems.length) currentIndex = 0;
      renderStats();
      renderCurrent();
    }

    function renderStats() {
      const s = state.summary;
      document.getElementById('topMeta').textContent =
        `当前 gate: ${state.gate.phone_37_human_semantic_review_window_gate} | reviewed ${s.reviewed_count}/${s.total_count} | pending ${s.pending_count}`;
      document.getElementById('stats').innerHTML = `
        <div class="stat"><div class="value">${s.reviewed_count}/${s.total_count}</div><div>已审核</div></div>
        <div class="stat"><div class="value">${s.pending_count}</div><div>待审核</div></div>
        <div class="stat"><div class="value">${s.needs_expert_review_count}</div><div>专家复核</div></div>
        <div class="stat"><div class="value">${s.false_tungro_prediction_count}</div><div>误检数</div></div>
        <div class="stat"><div class="value">${s.true_tungro_weak_confidence_count}</div><div>真 Tungro 弱检出</div></div>
        <div class="stat"><div class="value">${s.bad_localization_label_needs_fix_count}</div><div>标签需修</div></div>
      `;
      document.getElementById('listMeta').textContent = `当前筛选后 ${filteredItems.length} 条`;
    }

    function renderCurrent() {
      if (!filteredItems.length) {
        document.getElementById('infoGrid').innerHTML = '<div class="missing">当前筛选条件下没有样本。</div>';
        return;
      }
      const item = filteredItems[currentIndex];
      currentDecision = item.human_decision || 'UNREVIEWED';
      document.getElementById('notes').value = item.human_notes || '';
      const pairs = [
        ['review_id', item.review_id],
        ['case_type', item.case_type],
        ['split', item.split],
        ['image_name', item.image_name],
        ['baseline_status', item.baseline_status],
        ['retry@0.25', item.retry_status_conf025],
        ['retry@0.15', item.retry_status_conf015],
        ['retry@0.10', item.retry_status_conf010],
        ['retry@0.05', item.retry_status_conf005],
        ['max_tungro_conf', item.max_tungro_conf],
        ['review_status', item.review_status_zh],
        ['reviewer', item.reviewer || '-'],
      ];
      document.getElementById('infoGrid').innerHTML = pairs.map(([k, v]) =>
        `<div class="info-item"><strong>${esc(k)}</strong><span>${esc(v || '-')}</span></div>`
      ).join('');
      document.getElementById('questionText').textContent = item.suggested_question || 'MISSING_INPUT';
      document.getElementById('vizImage').src = item.visualization_exists ? `/asset?path=${encodeURIComponent(item.visualization_path)}` : '';
      document.getElementById('srcImage').src = item.image_exists ? `/asset?path=${encodeURIComponent(item.image_path)}` : '';
      document.getElementById('vizPath').textContent = item.visualization_exists ? item.visualization_path : 'MISSING_INPUT';
      document.getElementById('srcPath').textContent = item.image_exists ? item.image_path : 'MISSING_INPUT';
      renderDecisionButtons();
    }

    function renderDecisionButtons() {
      const root = document.getElementById('decisionButtons');
      root.innerHTML = Object.entries(DECISION_LABELS).map(([value, label]) => {
        const active = value === currentDecision ? 'active' : '';
        return `<button class="secondary decision-btn ${active}" data-value="${value}">${esc(label)}</button>`;
      }).join('');
      root.querySelectorAll('button').forEach((btn) => {
        btn.addEventListener('click', () => {
          currentDecision = btn.dataset.value;
          renderDecisionButtons();
        });
      });
    }

    async function saveCurrent(moveNext) {
      if (!filteredItems.length) return;
      const item = filteredItems[currentIndex];
      const payload = {
        review_id: item.review_id,
        human_decision: currentDecision,
        human_notes: document.getElementById('notes').value,
      };
      const res = await fetch('/api/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      state = data;
      applyFilters();
      const idx = filteredItems.findIndex((x) => x.review_id === item.review_id);
      currentIndex = idx >= 0 ? idx : currentIndex;
      if (moveNext && filteredItems.length > 0) {
        currentIndex = Math.min(currentIndex + 1, filteredItems.length - 1);
      }
      renderCurrent();
    }

    async function exportResults() {
      const res = await fetch('/api/export', { method: 'POST' });
      state = await res.json();
      applyFilters();
      alert('结果已导出并刷新 summary / gate。');
    }

    document.addEventListener('change', (e) => {
      if (['caseFilter', 'statusFilter', 'priorityFilter'].includes(e.target.id)) applyFilters();
    });
    document.getElementById('prevBtn').addEventListener('click', () => {
      if (!filteredItems.length) return;
      currentIndex = Math.max(0, currentIndex - 1);
      renderCurrent();
    });
    document.getElementById('nextBtn').addEventListener('click', () => {
      if (!filteredItems.length) return;
      currentIndex = Math.min(filteredItems.length - 1, currentIndex + 1);
      renderCurrent();
    });
    document.getElementById('saveBtn').addEventListener('click', () => saveCurrent(false));
    document.getElementById('saveNextBtn').addEventListener('click', () => saveCurrent(true));
    document.getElementById('exportBtn').addEventListener('click', exportResults);

    document.addEventListener('keydown', (e) => {
      if (e.target && ['TEXTAREA', 'INPUT'].includes(e.target.tagName) && !(e.key === 's' && e.ctrlKey)) return;
      if (HOTKEY_MAP[e.key]) {
        e.preventDefault();
        currentDecision = HOTKEY_MAP[e.key];
        renderDecisionButtons();
        return;
      }
      if (e.key === 's' || (e.key === 'S') || (e.ctrlKey && e.key.toLowerCase() === 's')) {
        e.preventDefault();
        saveCurrent(false);
      } else if (e.key === 'n' || e.key === 'N') {
        e.preventDefault();
        if (filteredItems.length) { currentIndex = Math.min(filteredItems.length - 1, currentIndex + 1); renderCurrent(); }
      } else if (e.key === 'p' || e.key === 'P') {
        e.preventDefault();
        if (filteredItems.length) { currentIndex = Math.max(0, currentIndex - 1); renderCurrent(); }
      }
    });

    fetchState();
  </script>
</body>
</html>
"""


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding=encoding, newline="") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    if not tmp.exists() or tmp.stat().st_size == 0:
        raise RuntimeError(f"temp write failed: {tmp}")
    tmp.replace(path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"replace failed: {path}")


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
    if not tmp.exists() or tmp.stat().st_size == 0:
        raise RuntimeError(f"temp csv write failed: {tmp}")
    tmp.replace(path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"replace csv failed: {path}")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def derive_review_status(human_decision: str) -> str:
    if human_decision == "UNREVIEWED":
        return "pending"
    if human_decision == "NEEDS_EXPERT_REVIEW":
        return "needs_expert"
    if human_decision == "EXCLUDE_FROM_EVAL":
        return "excluded"
    return "reviewed"


class ReviewStore:
    def __init__(self, reviewer: str) -> None:
        self.reviewer = reviewer
        self.lock = threading.Lock()
        self.packet_exists = INPUT_PACKET.exists()
        self.input_files = {
            "human_review_packet.csv": INPUT_PACKET.exists(),
            "phone_37_human_review_or_larger_eval_set_report.md": INPUT_REPORT.exists(),
            "closure_decision.json": INPUT_CLOSURE.exists(),
            "larger_eval_threshold_sweep.csv": INPUT_SWEEP.exists(),
            "larger_eval_false_positive_sweep.csv": INPUT_FP_SWEEP.exists(),
            "larger_eval_failure_cases.csv": INPUT_FAILURES.exists(),
            "human_review_visuals": (INPUT_DIR / "human_review_visuals").exists(),
            "larger_eval_threshold_visuals_conf_010": (INPUT_DIR / "larger_eval_threshold_visuals_conf_010").exists(),
            "larger_eval_threshold_visuals_conf_015": (INPUT_DIR / "larger_eval_threshold_visuals_conf_015").exists(),
            "larger_eval_false_positive_visuals": (INPUT_DIR / "larger_eval_false_positive_visuals").exists(),
            "larger_eval_failure_visuals": (INPUT_DIR / "larger_eval_failure_visuals").exists(),
        }
        self.previous_closure = read_json(INPUT_CLOSURE) if INPUT_CLOSURE.exists() else {}
        self.items = self._load_items()
        self.persist_all()

    def _load_items(self) -> list[dict[str, Any]]:
        if not INPUT_PACKET.exists():
            return []
        packet_rows = read_csv_rows(INPUT_PACKET)
        existing_map: dict[str, dict[str, Any]] = {}
        if DECISIONS_CSV.exists():
            for row in read_csv_rows(DECISIONS_CSV):
                existing_map[row["review_id"]] = row
        items: list[dict[str, Any]] = []
        for row in packet_rows:
            review_id = row["review_id"]
            existing = existing_map.get(review_id, {})
            human_decision = existing.get("human_decision", row.get("human_decision", "UNREVIEWED")) or "UNREVIEWED"
            review_status = existing.get("review_status", derive_review_status(human_decision)) or derive_review_status(human_decision)
            item = {
                "review_id": review_id,
                "case_type": row.get("case_type", "MISSING_INPUT"),
                "split": row.get("split", "MISSING_INPUT"),
                "image_name": row.get("image_name", "MISSING_INPUT"),
                "image_path": row.get("image_path", "MISSING_INPUT"),
                "label_path": row.get("label_path", "MISSING_INPUT"),
                "baseline_status": row.get("baseline_status", "MISSING_INPUT"),
                "retry_status_conf025": row.get("retry_status_conf025", "MISSING_INPUT"),
                "retry_status_conf015": row.get("retry_status_conf015", "MISSING_INPUT"),
                "retry_status_conf010": row.get("retry_status_conf010", "MISSING_INPUT"),
                "retry_status_conf005": row.get("retry_status_conf005", "MISSING_INPUT"),
                "max_tungro_conf": row.get("max_tungro_conf", "MISSING_INPUT"),
                "suggested_question": row.get("suggested_question", "MISSING_INPUT"),
                "human_decision": human_decision,
                "human_notes": existing.get("human_notes", row.get("human_notes", "")),
                "review_status": review_status,
                "reviewed_at": existing.get("reviewed_at", ""),
                "reviewer": existing.get("reviewer", ""),
                "visualization_path": row.get("visualization_path", "MISSING_INPUT"),
            }
            items.append(item)
        return items

    def _session_log_row(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "timestamp": now_iso(),
            "review_id": item["review_id"],
            "human_decision": item["human_decision"],
            "review_status": item["review_status"],
            "reviewer": item["reviewer"],
        }

    def _append_session_log(self, row: dict[str, Any]) -> None:
        rows = read_csv_rows(SESSION_LOG_CSV) if SESSION_LOG_CSV.exists() else []
        rows.append(row)
        atomic_write_csv(SESSION_LOG_CSV, rows, ["timestamp", "review_id", "human_decision", "review_status", "reviewer"])

    def set_decision(self, review_id: str, human_decision: str, human_notes: str) -> None:
        with self.lock:
            for item in self.items:
                if item["review_id"] != review_id:
                    continue
                if human_decision not in DECISION_OPTIONS:
                    raise ValueError(f"invalid human_decision: {human_decision}")
                item["human_decision"] = human_decision
                item["human_notes"] = human_notes
                item["review_status"] = derive_review_status(human_decision)
                item["reviewed_at"] = now_iso()
                item["reviewer"] = self.reviewer
                self.persist_all()
                self._append_session_log(self._session_log_row(item))
                return
            raise KeyError(f"review_id not found: {review_id}")

    def build_summary(self) -> dict[str, Any]:
        counter = {key: 0 for key in [
            "total_count",
            "reviewed_count",
            "pending_count",
            "needs_expert_review_count",
            "excluded_count",
            "true_tungro_weak_confidence_count",
            "false_tungro_prediction_count",
            "bad_localization_label_ok_count",
            "bad_localization_label_needs_fix_count",
            "label_ambiguous_count",
            "image_quality_too_weak_count",
            "model_regression_confirmed_count",
            "model_regression_not_confirmed_count",
        ]}
        counter["total_count"] = len(self.items)
        for item in self.items:
            status = item["review_status"]
            decision = item["human_decision"]
            if status == "reviewed":
                counter["reviewed_count"] += 1
            elif status == "pending":
                counter["pending_count"] += 1
            elif status == "needs_expert":
                counter["needs_expert_review_count"] += 1
            elif status == "excluded":
                counter["excluded_count"] += 1
            mapping = {
                "TRUE_TUNGRO_WEAK_CONFIDENCE": "true_tungro_weak_confidence_count",
                "FALSE_TUNGRO_PREDICTION": "false_tungro_prediction_count",
                "BAD_LOCALIZATION_LABEL_OK": "bad_localization_label_ok_count",
                "BAD_LOCALIZATION_LABEL_NEEDS_FIX": "bad_localization_label_needs_fix_count",
                "LABEL_AMBIGUOUS": "label_ambiguous_count",
                "IMAGE_QUALITY_TOO_WEAK": "image_quality_too_weak_count",
                "MODEL_REGRESSION_CONFIRMED": "model_regression_confirmed_count",
                "MODEL_REGRESSION_NOT_CONFIRMED": "model_regression_not_confirmed_count",
            }
            target = mapping.get(decision)
            if target:
                counter[target] += 1
        return counter

    def build_gate(self) -> dict[str, Any]:
        summary = self.build_summary()
        pending_count = summary["pending_count"]
        reviewed_done = summary["reviewed_count"] + summary["excluded_count"] + summary["needs_expert_review_count"]
        if not self.packet_exists:
            gate = "BLOCKED"
            next_stage = "STAY_AT_PHONE_37_REVIEW_WINDOW"
        elif pending_count > 0:
            gate = "IN_PROGRESS"
            next_stage = "Phone-37Human-Semantic-Review-Window-Continue"
        elif summary["needs_expert_review_count"] > 0 or summary["bad_localization_label_needs_fix_count"] > 0 or summary["false_tungro_prediction_count"] > 0:
            gate = "WARNING"
            next_stage = "Phone-37Human-Semantic-Review-Closure"
        elif reviewed_done == summary["total_count"]:
            gate = "PASS"
            next_stage = "Phone-37Human-Semantic-Review-Closure"
        else:
            gate = "WARNING"
            next_stage = "Phone-37Human-Semantic-Review-Closure"
        return {
            "phone_37_human_semantic_review_window_gate": gate,
            "review_window_started": True,
            "total_review_items": summary["total_count"],
            "reviewed_count": summary["reviewed_count"],
            "pending_count": summary["pending_count"],
            "needs_expert_review_count": summary["needs_expert_review_count"],
            "excluded_count": summary["excluded_count"],
            "semantic_human_review_performed": summary["reviewed_count"] > 0 or summary["needs_expert_review_count"] > 0 or summary["excluded_count"] > 0,
            "manual_human_review_still_needed": summary["pending_count"] > 0,
            "allow_threshold_calibrated_experimental_eval": bool(self.previous_closure.get("allow_threshold_calibrated_experimental_eval", True)),
            "allow_next_full_training": False,
            "allow_backend_demo_claim": False,
            "allow_candidate_claim": False,
            "next_allowed_stage": next_stage,
            "forbidden_stage": ["full_training", "backend_demo_integration", "candidate_claim"],
            "atomic_write_used": True,
            "tmp_files_left": False,
        }

    def build_context(self) -> dict[str, Any]:
        return {
            "project_root": str(ROOT),
            "input_packet": str(INPUT_PACKET),
            "output_dir": str(OUTPUT_DIR),
            "input_files": self.input_files,
            "review_window_started": True,
            "total_items": len(self.items),
            "python_executable": sys.executable,
            "atomic_write_used": True,
            "tmp_files_left": False,
        }

    def build_report(self) -> str:
        summary = self.build_summary()
        gate = self.build_gate()
        return f"""# Phone-37 Human Semantic Review Window Report

## Scope

- Launch Tungro semantic human review window for `human_review_packet.csv`
- This round trained a model: `NO`
- Generated new weights: `NO`
- Overwrote existing weights: `NO`
- Modified backend: `NO`
- Modified frontend: `NO`
- Modified .env: `NO`
- Modified dataset / labels: `NO`
- Allow backend demo claim: `NO`
- Allow candidate claim: `NO`

## Input Files

- input packet exists: `{INPUT_PACKET.exists()}`
- larger eval report exists: `{INPUT_REPORT.exists()}`
- closure decision exists: `{INPUT_CLOSURE.exists()}`
- threshold sweep exists: `{INPUT_SWEEP.exists()}`
- false positive sweep exists: `{INPUT_FP_SWEEP.exists()}`
- failure cases exists: `{INPUT_FAILURES.exists()}`

## Review Window Status

- total review items: `{summary["total_count"]}`
- reviewed count: `{summary["reviewed_count"]}`
- pending count: `{summary["pending_count"]}`
- needs expert review count: `{summary["needs_expert_review_count"]}`
- excluded count: `{summary["excluded_count"]}`

## Output Files

- decisions csv: `{DECISIONS_CSV}`
- decisions json: `{DECISIONS_JSON}`
- summary csv: `{SUMMARY_CSV}`
- gate json: `{GATE_JSON}`
- progress json: `{PROGRESS_JSON}`

## Review Progress

- true_tungro_weak_confidence_count: `{summary["true_tungro_weak_confidence_count"]}`
- false_tungro_prediction_count: `{summary["false_tungro_prediction_count"]}`
- bad_localization_label_needs_fix_count: `{summary["bad_localization_label_needs_fix_count"]}`

## Gate

- phone_37_human_semantic_review_window_gate: `{gate["phone_37_human_semantic_review_window_gate"]}`
- next_allowed_stage: `{gate["next_allowed_stage"]}`
- atomic_write_used: `true`
- tmp_files_left: `false`

## How To Continue Review

1. Open the local review URL.
2. Choose a human decision for each row.
3. Save or save-and-next after each item.
4. Export results when you want a fresh summary/gate snapshot.
"""

    def persist_all(self) -> None:
        summary = self.build_summary()
        gate = self.build_gate()
        context = self.build_context()
        decisions_rows = []
        api_rows = []
        for item in self.items:
            decisions_rows.append({field: item.get(field, "") for field in SAVE_FIELDS})
            api_item = dict(item)
            api_item["decision_label_zh"] = DECISION_LABELS.get(item["human_decision"], item["human_decision"])
            api_item["review_status_zh"] = STATUS_LABELS.get(item["review_status"], item["review_status"])
            api_item["priority"] = item["case_type"] in {
                "LOW_CONFIDENCE_ONLY",
                "BAD_LOCALIZATION",
                "FALSE_TUNGRO_PREDICTION",
                "TEST_REGRESSION",
                "BASELINE_RETRY_DISAGREEMENT",
            }
            api_item["image_exists"] = Path(item["image_path"]).exists()
            api_item["visualization_exists"] = Path(item["visualization_path"]).exists()
            api_rows.append(api_item)
        atomic_write_csv(DECISIONS_CSV, decisions_rows, SAVE_FIELDS)
        atomic_write_json(DECISIONS_JSON, decisions_rows)
        atomic_write_csv(SUMMARY_CSV, [summary], list(summary.keys()))
        atomic_write_json(GATE_JSON, gate)
        atomic_write_json(PROGRESS_JSON, {
            "updated_at": now_iso(),
            "reviewed_count": summary["reviewed_count"],
            "pending_count": summary["pending_count"],
            "needs_expert_review_count": summary["needs_expert_review_count"],
            "excluded_count": summary["excluded_count"],
        })
        atomic_write_json(CONTEXT_JSON, context)
        atomic_write_csv(EXPORT_CSV, decisions_rows, SAVE_FIELDS)
        atomic_write_text(REPORT_MD, self.build_report())
        self.cached_state = {"items": api_rows, "summary": summary, "gate": gate, "context": context}

    def export_state(self) -> dict[str, Any]:
        with self.lock:
            self.persist_all()
            return self.cached_state

    def get_state(self) -> dict[str, Any]:
        with self.lock:
            return self.cached_state


class ReviewHandler(BaseHTTPRequestHandler):
    store: ReviewStore

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(404, "File not found")
            return
        mime, _ = mimetypes.guess_type(path.name)
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _resolve_asset(self, raw_path: str) -> Path | None:
        try:
            candidate = Path(raw_path).resolve()
        except Exception:
            return None
        try:
            candidate.relative_to(ROOT)
        except ValueError:
            return None
        return candidate

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(HTML_PAGE)
            return
        if parsed.path == "/api/state":
            self._send_json(self.store.get_state())
            return
        if parsed.path == "/asset":
            qs = parse_qs(parsed.query)
            raw = qs.get("path", [""])[0]
            resolved = self._resolve_asset(raw)
            if resolved is None:
                self.send_error(403, "Forbidden")
                return
            self._send_file(resolved)
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_json({"error": "invalid_json"}, status=400)
            return
        try:
            if parsed.path == "/api/save":
                self.store.set_decision(
                    review_id=str(payload.get("review_id", "")),
                    human_decision=str(payload.get("human_decision", "UNREVIEWED")),
                    human_notes=str(payload.get("human_notes", "")),
                )
                self._send_json(self.store.get_state())
                return
            if parsed.path == "/api/export":
                self._send_json(self.store.export_state())
                return
            self.send_error(404, "Not found")
        except Exception as exc:
            self._send_json({"error": str(exc), "traceback": traceback.format_exc()}, status=500)

    def log_message(self, format: str, *args: Any) -> None:
        return


def choose_port(host: str, requested_port: int) -> int:
    ordered = [requested_port] + [port for port in ALLOWED_PORTS if port != requested_port]
    last_error = None
    for port in ordered:
        try:
            server = ThreadingHTTPServer((host, port), ReviewHandler)
            server.server_close()
            return port
        except OSError as exc:
            last_error = exc
    raise OSError(f"no available port in {ordered}: {last_error}")


def launch_browser(url: str) -> None:
    try:
        webbrowser.open(url, new=1)
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--reviewer", default="human_reviewer")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    store = ReviewStore(reviewer=args.reviewer)
    ReviewHandler.store = store

    port = choose_port(args.host, args.port)
    server = ThreadingHTTPServer((args.host, port), ReviewHandler)
    url = f"http://{args.host}:{port}"

    if not args.no_browser:
        threading.Thread(target=launch_browser, args=(url,), daemon=True).start()

    print("Human semantic review window started.")
    print(f"URL: {url}")
    print(f"Input packet: {INPUT_PACKET}")
    print(f"Output decisions: {DECISIONS_CSV}")
    print(f"Progress file: {PROGRESS_JSON}")
    print(f"Total review items: {len(store.items)}")
    print(f"Current gate: {store.build_gate()['phone_37_human_semantic_review_window_gate']}")
    print("Training started: NO")
    print("Backend modified: NO")
    print("Dataset modified: NO")
    sys.stdout.flush()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
