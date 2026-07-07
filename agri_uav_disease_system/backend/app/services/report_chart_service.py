from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from app.schemas.detection_result import DetectionResult


class ReportChartService:
    def build(self, record: DetectionResult | None, history_records: list[DetectionResult]) -> dict[str, Any]:
        history_count = len(history_records)
        confidence = [
            {
                "label": item.label,
                "value": item.confidence,
                "percent": round(float(item.confidence or 0) * 100, 1),
                "severity": item.scope_status or item.category_type or "",
            }
            for item in (record.detections if record else [])
        ]
        evidence_sources = self.evidence_sources(record, history_records, weather_available=False, rag_count=0, llm_mode="unknown")
        charts: dict[str, Any] = {
            "history_count": history_count,
            "history_sufficient": history_count >= 3,
            "insufficient_history_message": "当前历史检测记录不足，暂不生成长期趋势判断。",
            "confidence_chart": confidence,
            "evidence_source_chart": evidence_sources,
            "risk_distribution": self._risk_distribution(history_records) if history_count >= 3 else [],
            "attention_cards": self._attention_cards(record),
            "history_rows": self._history_rows(history_records) if history_count >= 3 else [],
        }
        return charts

    def evidence_sources(
        self,
        record: DetectionResult | None,
        history_records: list[DetectionResult],
        weather_available: bool,
        rag_count: int,
        llm_mode: str,
    ) -> list[dict[str, str]]:
        return [
            {"label": "检测记录", "status": "已采集" if record else "缺少记录"},
            {"label": "天气快照", "status": "已采集" if weather_available else "暂不可用"},
            {"label": "历史记录", "status": f"{len(history_records)} 条"},
            {"label": "RAG 知识库", "status": f"{rag_count} 条" if rag_count else "证据不足"},
            {"label": "LLM 结构化分析", "status": llm_mode or "unknown"},
        ]

    def _history_rows(self, history_records: list[DetectionResult]) -> list[dict[str, Any]]:
        daily = defaultdict(lambda: {"total": 0, "abnormal": 0})
        for item in history_records:
            day = self._date_key(item.timestamp)
            daily[day]["total"] += 1
            if self._is_abnormal(item):
                daily[day]["abnormal"] += 1
        return [
            {"date": day, "total": values["total"], "abnormal": values["abnormal"]}
            for day, values in sorted(daily.items())
        ]

    def _risk_distribution(self, history_records: list[DetectionResult]) -> list[dict[str, Any]]:
        risk_counts = Counter(item.summary.risk_level or "unknown" for item in history_records)
        return [{"label": key, "value": value} for key, value in sorted(risk_counts.items())]

    def _attention_cards(self, record: DetectionResult | None) -> list[dict[str, str]]:
        if not record:
            return [
                {"label": "关注等级", "value": "unknown", "note": "缺少检测记录"},
                {"label": "风险说明", "value": "待复核", "note": "仅保留基础报告"},
            ]
        return [
            {"label": "关注等级", "value": record.summary.risk_level or "unknown", "note": "来自检测记录"},
            {"label": "主要异常", "value": record.summary.main_disease or "暂无明确类别", "note": "来自模型输出"},
            {"label": "最高置信度", "value": f"{record.summary.max_confidence:.0%}", "note": "来自检测框"},
        ]

    def _is_abnormal(self, record: DetectionResult) -> bool:
        risk = (record.summary.risk_level or "").lower()
        severity = record.summary.severity or ""
        return risk in {"medium", "high", "critical"} or severity not in {"无病", "normal", "none", ""}

    def _date_key(self, value: str) -> str:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return value[:10] or "unknown"


report_chart_service = ReportChartService()
