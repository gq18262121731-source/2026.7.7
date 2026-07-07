from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.schemas.detection_result import DetectionResult
from app.schemas.farm_analysis_report import FarmAnalysisReportMetadata, FarmAnalysisReportRequest, FarmAnalysisReportResponse
from app.services.agent_service import agent_service
from app.services.knowledge_service import KnowledgeNotFoundError, knowledge_service
from app.services.report_chart_service import report_chart_service
from app.services.report_pdf_service import report_pdf_service
from app.services.report_storage_service import report_storage_service
from app.services.storage.result_store import result_store
from app.services.weather.weather_service import weather_service


class FarmAnalysisReportService:
    def generate_report(self, request: FarmAnalysisReportRequest) -> FarmAnalysisReportResponse:
        created_at = self._now()
        report_id = f"farm_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        record = self._select_record(request)
        history_records = self._history_records(request, record)
        weather = self._weather_snapshot(request, record)
        rag_chunks = self._rag_chunks(record)
        llm_result = self._llm_result(record, request)
        charts = report_chart_service.build(record, history_records)
        charts["evidence_source_chart"] = report_chart_service.evidence_sources(
            record,
            history_records,
            weather_available=bool(weather.get("available")),
            rag_count=len(rag_chunks),
            llm_mode=str(llm_result.get("llm_mode") or "fallback"),
        )

        data = self._report_data(
            report_id=report_id,
            created_at=created_at,
            request=request,
            record=record,
            history_records=history_records,
            weather=weather,
            rag_chunks=rag_chunks,
            llm_result=llm_result,
            charts=charts,
        )
        html_path = report_storage_service.report_dir / f"{report_id}.html"
        pdf_path = report_storage_service.report_dir / f"{report_id}.pdf"
        report_pdf_service.render_html(data, html_path)
        pdf_fallback_used = report_pdf_service.generate_pdf(html_path, pdf_path, data)
        data["pdf_fallback_used"] = pdf_fallback_used
        report_pdf_service.render_html(data, html_path)

        metadata = FarmAnalysisReportMetadata(
            report_id=report_id,
            plot_id=data["plot_id"],
            record_id=record.record_id if record else request.record_id,
            report_type=request.report_type,
            crop=request.crop,
            summary=data["summary"],
            pdf_path=str(pdf_path),
            html_path=str(html_path),
            pdf_url=f"/api/farm-analysis-reports/{report_id}/download",
            preview_url=f"/api/farm-analysis-reports/{report_id}/preview",
            weather_snapshot=weather,
            record_snapshot=record.model_dump(mode="json") if record else {},
            history_snapshot=[item.model_dump(mode="json") for item in history_records],
            rag_snapshot=rag_chunks,
            chart_snapshot=charts,
            llm_result_snapshot=llm_result,
            llm_mode=str(llm_result.get("llm_mode") or "fallback"),
            fallback_used=bool(llm_result.get("fallback_used")),
            api_error_type=llm_result.get("api_error_type"),
            weather_available=bool(weather.get("available")),
            rag_available=bool(rag_chunks),
            pdf_fallback_used=pdf_fallback_used,
            created_at=created_at,
        )
        report_storage_service.save(metadata)
        return FarmAnalysisReportResponse(
            report_id=report_id,
            status="fallback" if metadata.fallback_used or pdf_fallback_used else "success",
            summary=metadata.summary,
            pdf_url=metadata.pdf_url,
            preview_url=metadata.preview_url,
            fallback_used=metadata.fallback_used,
            weather_available=metadata.weather_available,
            rag_available=metadata.rag_available,
            pdf_fallback_used=metadata.pdf_fallback_used,
            created_at=created_at,
        )

    def _select_record(self, request: FarmAnalysisReportRequest) -> DetectionResult | None:
        if request.record_id:
            return result_store.get(request.record_id)
        records = result_store.list_records(plot_id=None if request.plot_id == "all" else request.plot_id, page=1, page_size=1)
        return records[0] if records else None

    def _history_records(self, request: FarmAnalysisReportRequest, record: DetectionResult | None) -> list[DetectionResult]:
        plot_id = None if request.plot_id == "all" else request.plot_id
        if record and record.plot_id:
            plot_id = record.plot_id
        start = (datetime.now(timezone.utc) - timedelta(days=request.include_history_days)).isoformat()
        return result_store.list_records(plot_id=plot_id, start_time=start, page=1, page_size=100, sort="timestamp_desc")

    def _weather_snapshot(self, request: FarmAnalysisReportRequest, record: DetectionResult | None) -> dict[str, Any]:
        if not request.include_weather:
            return {"available": False, "message": "未启用天气快照", "source": "local_weather_observations"}
        plot_id = record.plot_id if record and record.plot_id else (None if request.plot_id == "all" else request.plot_id)
        try:
            observations = weather_service.list_observations(plot_id=plot_id, limit=1)
        except Exception as exc:
            return {"available": False, "message": "天气数据暂不可用，不影响本次检测记录分析。", "source": "local_weather_observations", "error": type(exc).__name__}
        if not observations:
            return {"available": False, "message": "天气数据暂不可用，不影响本次检测记录分析。", "source": "local_weather_observations"}
        latest = observations[0]
        avg_temp = self._avg(latest.temperature_max, latest.temperature_min)
        return {
            "available": True,
            "city": "宿迁市",
            "district": latest.region_name or (record.region_name if record else ""),
            "temperature": f"{avg_temp:.1f} C" if avg_temp is not None else "暂无",
            "humidity": f"{latest.humidity_avg:.0f}%" if latest.humidity_avg is not None else "暂无",
            "weather": latest.weather_text or "暂无",
            "wind_direction": "暂无",
            "wind_power": f"{latest.wind_speed:.1f} m/s" if latest.wind_speed is not None else "暂无",
            "rainfall_mm": latest.rainfall_mm,
            "report_time": latest.observed_date,
            "source": latest.data_source,
        }

    def _rag_chunks(self, record: DetectionResult | None) -> list[dict[str, Any]]:
        if not record:
            return []
        disease_id = self._disease_id(record)
        query_parts = [
            record.summary.main_disease or "",
            record.detections[0].label if record.detections else "",
            record.summary.risk_level,
            record.source_type,
            "水稻 病虫害 图像识别 不确定性",
        ]
        try:
            return knowledge_service.search_knowledge(" ".join(query_parts), disease_id, None, 5)
        except (KnowledgeNotFoundError, Exception):
            return []

    def _llm_result(self, record: DetectionResult | None, request: FarmAnalysisReportRequest) -> dict[str, Any]:
        if not record:
            return self._fallback_llm_result("缺少可用检测记录，已生成基础模板报告。", request.plot_id, request.report_type)
        try:
            return agent_service.generate_diagnosis_report(
                record_id=record.record_id,
                model_class=self._model_class(record),
                confidence=record.summary.max_confidence,
                source_type=record.source_type,
                field_id=record.field_id,
                plot_id=record.plot_id,
                uav_task_id=record.uav_task_id,
                abnormal_region_id=record.abnormal_region_id,
                risk_level=record.summary.risk_level,
                severity=record.summary.severity,
                user_question=(
                    "请基于本次检测记录、历史记录、天气快照和知识库证据，生成水稻农情辅助分析 JSON 内容。"
                    "不要输出强制农事决策，不要给出农药剂量，必须明确不确定性和人工复核边界。"
                ),
            )
        except Exception as exc:
            fallback = self._fallback_llm_result("LLM 服务暂不可用，已生成基础模板报告。", request.plot_id, request.report_type)
            fallback["api_error_type"] = type(exc).__name__
            return fallback

    def _report_data(
        self,
        report_id: str,
        created_at: str,
        request: FarmAnalysisReportRequest,
        record: DetectionResult | None,
        history_records: list[DetectionResult],
        weather: dict[str, Any],
        rag_chunks: list[dict[str, Any]],
        llm_result: dict[str, Any],
        charts: dict[str, Any],
    ) -> dict[str, Any]:
        plot_id = record.plot_id if record and record.plot_id else request.plot_id
        plot_name = record.plot_name if record and record.plot_name else plot_id
        detection_rows = [
            {
                "label": item.label,
                "confidence": item.confidence,
                "severity": record.summary.severity if record else "",
                "risk_level": record.summary.risk_level if record else "",
            }
            for item in (record.detections if record else [])
        ]
        attention = llm_result.get("risk_level") or (record.summary.risk_level if record else "unknown")
        summary = str(
            llm_result.get("answer")
            or llm_result.get("model_result_summary")
            or "已生成农情辅助分析报告，当前结果仅用于复核参考。"
        )
        uncertainty = list(llm_result.get("uncertainty_notes") or llm_result.get("uncertainty") or [])
        if len(history_records) < 3:
            uncertainty.append("当前历史检测记录不足，暂不生成长期趋势判断。")
        if not rag_chunks:
            uncertainty.append("当前 RAG 知识库未检索到足够依据，报告不补写未提供的知识证据。")
        if not weather.get("available"):
            uncertainty.append("天气数据暂不可用，天气因素未作为本次报告主要依据。")
        uncertainty.append("本报告为辅助分析结果，不作为最终农事处置依据。")
        summary_cards = [
            {"label": "关注等级", "value": str(attention), "note": "来自 LLM/检测风险"},
            {"label": "主要异常", "value": record.summary.main_disease if record else "暂无记录", "note": "来自检测记录"},
            {"label": "最高置信度", "value": f"{record.summary.max_confidence:.0%}" if record else "暂无", "note": "来自 YOLO 输出"},
            {"label": "历史样本", "value": str(len(history_records)), "note": f"近 {request.include_history_days} 天"},
            {"label": "知识片段", "value": str(len(rag_chunks)), "note": "来自本地 RAG"},
            {"label": "报告边界", "value": "辅助分析", "note": "需要人工复核"},
        ]
        return {
            "title": "水稻农情分析报告",
            "report_id": report_id,
            "created_at": created_at,
            "report_type": request.report_type,
            "include_history_days": request.include_history_days,
            "record_id": record.record_id if record else request.record_id,
            "plot_id": plot_id,
            "plot_name": plot_name,
            "attention_level": attention,
            "summary": summary,
            "summary_cards": summary_cards,
            "weather": weather,
            "weather_cards": self._weather_cards(weather),
            "weather_analysis": self._weather_analysis(weather),
            "detection_rows": detection_rows,
            "history_rows": charts.get("history_rows", []),
            "history_sufficient": charts.get("history_sufficient", False),
            "history_analysis": self._history_analysis(history_records),
            "risk_distribution": charts.get("risk_distribution", []),
            "attention_cards": charts.get("attention_cards", []),
            "confidence_chart": charts.get("confidence_chart", []),
            "evidence_sources": charts.get("evidence_source_chart", []),
            "insufficient_history_message": charts.get("insufficient_history_message"),
            "rag_chunks": [
                {
                    "title": item.get("source_title") or item.get("chunk_id"),
                    "content": item.get("text") or item.get("content") or "",
                    "authority_level": item.get("authority_level", "unknown"),
                    "section_type": item.get("section_type", "unknown"),
                }
                for item in rag_chunks
            ],
            "uncertainty": self._unique(uncertainty),
            "conclusion": str(
                llm_result.get("answer")
                or llm_result.get("knowledge_summary")
                or "综合当前检测、历史与知识库信息，本次报告仅形成关注信号，不作最终处置依据。"
            ),
            "llm_mode": llm_result.get("llm_mode", "fallback"),
            "fallback_used": bool(llm_result.get("fallback_used")),
            "pdf_fallback_used": False,
        }

    def _weather_cards(self, weather: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {"label": "温度", "value": str(weather.get("temperature") or "暂无")},
            {"label": "湿度", "value": str(weather.get("humidity") or "暂无")},
            {"label": "天气", "value": str(weather.get("weather") or weather.get("message") or "暂无")},
            {"label": "风力", "value": str(weather.get("wind_power") or "暂无")},
            {"label": "更新时间", "value": str(weather.get("report_time") or "暂无")},
            {"label": "数据来源", "value": str(weather.get("source") or "local_weather_observations")},
        ]

    def _fallback_llm_result(self, message: str, plot_id: str, report_type: str) -> dict[str, Any]:
        return {
            "answer": message,
            "model_result_summary": f"{plot_id} 已生成 {report_type} 基础分析报告。",
            "knowledge_summary": "系统仅汇总已采集记录、历史趋势和知识库检索结果，不补写未提供的病害依据。",
            "risk_level": "unknown",
            "uncertainty_notes": ["证据不足时不确认具体病害，需要结合近景样本和人工复核。"],
            "evidence_sources": [],
            "insufficient_evidence": True,
            "llm_mode": "fallback",
            "fallback_used": True,
            "api_error_type": None,
        }

    def _disease_id(self, record: DetectionResult) -> str | None:
        mapped = knowledge_service.map_model_class_to_disease(self._model_class(record))
        disease_id = mapped.get("disease_id")
        return str(disease_id) if disease_id else None

    def _model_class(self, record: DetectionResult) -> str | None:
        if record.model_hint:
            return record.model_hint
        if record.detections:
            first = record.detections[0]
            return first.class_code or first.class_name or first.label
        return record.summary.main_disease

    def _history_analysis(self, records: list[DetectionResult]) -> str:
        if len(records) < 3:
            return "当前历史检测记录不足，暂不生成长期趋势判断。"
        abnormal = sum(1 for item in records if self._is_abnormal(item))
        return f"近 7 天共检索到 {len(records)} 条检测记录，其中 {abnormal} 条包含异常或中高风险信号；趋势仅用于辅助观察。"

    def _weather_analysis(self, weather: dict[str, Any]) -> str:
        if not weather.get("available"):
            return "天气数据暂不可用，本报告不将天气因素作为主要判断依据。"
        factors = []
        humidity = str(weather.get("humidity") or "")
        if humidity and humidity != "暂无":
            factors.append(f"当前湿度 {humidity}")
        if weather.get("rainfall_mm"):
            factors.append(f"降雨量 {weather['rainfall_mm']} mm")
        if weather.get("weather"):
            factors.append(f"天气现象 {weather['weather']}")
        return "，".join(factors) + "。天气因素仅作为环境背景，不单独确认病虫害。"

    def _is_abnormal(self, record: DetectionResult) -> bool:
        risk = (record.summary.risk_level or "").lower()
        severity = record.summary.severity or ""
        return risk in {"medium", "high", "critical"} or severity not in {"无病", "normal", "none", ""}

    def _avg(self, a: float | None, b: float | None) -> float | None:
        values = [item for item in (a, b) if item is not None]
        return sum(values) / len(values) if values else None

    def _unique(self, items: list[Any]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            text = str(item).strip()
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


farm_analysis_report_service = FarmAnalysisReportService()
