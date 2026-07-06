from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from app.services.dataset_index_service import MODEL_INFO, build_samples, result_from_sample, source_status


HISTORY_FILE = Path("data/history/history.json")

_history: List[Dict] = []
_settings = {
    "assistant_status": "运行中",
    "knowledge_base_status": "已连接",
    "risk_rule_status": "已启用",
    "report_status": "可生成",
    "local_source_status": "已索引",
    "assistant_mode": "knowledge_base",
    "visual_effects": True,
    "api_base": "http://localhost:8000/api",
}
_make_status = {
    "webhook_status": "ready",
    "last_triggered_at": None,
    "success_count": 8,
    "failed_count": 0,
    "nodes": [
        {"name": "Receive Analysis Result", "status": "success"},
        {"name": "Validate Payload", "status": "success"},
        {"name": "Save Record", "status": "success"},
        {"name": "Sync Data Source", "status": "success"},
        {"name": "Send Alert", "status": "success"},
    ],
}


def get_models() -> dict:
    return {
        "models": MODEL_INFO,
        "active_model": MODEL_INFO[0]["key"],
        "status": "running",
        "last_updated": "2026-07-01T00:00:00+08:00",
    }


def detect_by_id(payload: dict) -> dict:
    sample_key = payload.get("sample_key")
    record = deepcopy(
        result_from_sample(
            model_key=payload["model_key"],
            sample_key=sample_key,
            source_type=payload.get("source_type"),
        )
    )
    now = datetime.now().isoformat(timespec="seconds")
    task_id = f"tsk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
    record.update(
        {
            "task_id": task_id,
            "status": "succeeded",
            "created_at": now,
            "operator": payload.get("operator", "system_user"),
            "processing_status": "已完成",
        }
    )
    _history.insert(0, record)
    _make_status["last_triggered_at"] = now
    return record


def list_history(keyword: Optional[str] = None, status: Optional[str] = None, type: Optional[str] = None) -> List[Dict]:
    records = _history or seed_history()
    filtered = records
    if keyword:
        term = keyword.lower()
        filtered = [
            item
            for item in filtered
            if term in item["summary"]["top_label"].lower()
            or term in item["analysis"]["title"].lower()
            or term in item["task_id"].lower()
        ]
    if status:
        filtered = [item for item in filtered if item["status"] == status]
    if type:
        filtered = [item for item in filtered if item["image"]["scene_type"] == type]
    return filtered


def get_history_record(task_id: str) -> Optional[Dict]:
    return next((item for item in list_history() if item["task_id"] == task_id), None)


def get_task(task_id: str) -> Optional[Dict]:
    record = get_history_record(task_id)
    if not record:
        return None
    return {"task_id": task_id, "status": record["status"], "progress": 100, "result": record, "error": None}


def assistant_reply(message: str, mode: str, context: dict) -> dict:
    lower = message.lower()
    if "褐斑" in message or "brown" in lower:
        answer = "褐斑病通常与高温高湿、肥水管理不均有关。轻度发生时建议先做田间复查，清理重病叶片，并结合当地植保建议进行点状防治。"
        source = "brown_spot.md"
    elif "白叶枯" in message or "blb" in lower:
        answer = "白叶枯病在航拍中常表现为片区化风险。建议优先核查水层管理、近期降雨与病斑边缘区域，避免盲目全田用药。"
        source = "blb_uav.md"
    elif "稻瘟" in message or "blast" in lower:
        answer = "稻瘟病需要结合品种抗性、湿度和田间密度判断。演示系统会优先给出风险等级、疑似区域和复查建议。"
        source = "blast.md"
    else:
        answer = "我可以结合水稻病虫害知识库解释检测结果、判断风险等级，并给出田间复查与防治建议。"
        source = "platform_faq.md"

    if context.get("top_label"):
        answer += f" 当前上下文显示主要风险为 {context['top_label']}，建议结合历史记录继续复盘。"

    return {"answer": answer, "sources": [{"source": source, "score": 0.92}], "mode": mode, "confidence": 0.91}


def get_settings() -> dict:
    return {**_settings, **source_status()}


def update_settings(payload: dict) -> dict:
    _settings.update(payload)
    return _settings


def get_make_status() -> dict:
    return _make_status


def trigger_make(task_id: Optional[str] = None) -> dict:
    _make_status["last_triggered_at"] = datetime.now().isoformat(timespec="seconds")
    _make_status["success_count"] += 1
    return {"status": "running", "task_id": task_id, "workflow": _make_status}


def seed_history() -> List[Dict]:
    if _history:
        return _history
    for sample in build_samples()[:2]:
        payload = {
            "sample_key": sample["sample_key"],
            "operator": "system",
            "model_key": sample["model_key"],
            "source_type": sample["source_type"],
        }
        detect_by_id(payload)
    return _history


def list_samples() -> dict:
    return {"samples": build_samples()}

