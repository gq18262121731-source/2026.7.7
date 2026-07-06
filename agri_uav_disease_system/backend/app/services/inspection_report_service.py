from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.core.exceptions import AppException
from app.database.field_repositories import FieldRepository, field_repository
from app.database.inspection_report_repositories import InspectionReportRepository, inspection_report_repository
from app.database.uav_repositories import UavRepository, uav_repository
from app.schemas.inspection_report import (
    MODEL_SAFETY_NOTE,
    InspectionReport,
    InspectionReportGenerateRequest,
    InspectionReportListResponse,
)
from app.services.knowledge_service import knowledge_service
from app.services.prediction.prediction_service import prediction_service
from app.schemas.risk_fusion import RULE_RISK_SAFETY_NOTE, RiskFusionEvaluateRequest
from app.services.risk_fusion_scorer import risk_fusion_scorer


class InspectionReportService:
    def __init__(
        self,
        repository: InspectionReportRepository | None = None,
        field_repo: FieldRepository | None = None,
        uav_repo: UavRepository | None = None,
    ) -> None:
        self.repository = repository or inspection_report_repository
        self.field_repo = field_repo or field_repository
        self.uav_repo = uav_repo or uav_repository

    async def generate(self, request: InspectionReportGenerateRequest) -> InspectionReport:
        field = self.field_repo.get(request.field_id)
        if not field:
            raise AppException("FIELD_NOT_FOUND", "田块不存在，无法生成巡检报告", {"field_id": request.field_id})
        task = self.uav_repo.get_task(request.uav_task_id) if request.uav_task_id else None
        if request.uav_task_id and not task:
            raise AppException("UAV_TASK_NOT_FOUND", "UAV 任务不存在，无法生成巡检报告", {"uav_task_id": request.uav_task_id})

        task_id = request.uav_task_id or (task.uav_task_id if task else None)
        indices = self.uav_repo.list_indices(task_id) if task_id else []
        regions = self.uav_repo.list_regions(uav_task_id=task_id, field_id=request.field_id if not task_id else None)
        phone_followups = [region for region in regions if region.linked_record_id]
        risk = (
            await prediction_service.predict_plot(
                plot_id=request.field_id,
                window_days=7,
                save=True,
                create_alert=False,
            )
            if request.include_risk
            else None
        )
        rag_suggestion = self._rag_suggestion(field.current_growth_stage, phone_followups, risk) if request.include_rag else ""
        if not rag_suggestion:
            rag_suggestion = "建议优先复查无人机提示的异常区域，并结合手机近景结果联系农技人员确认。"

        selected_region_id = phone_followups[0].region_id if phone_followups else (regions[0].region_id if regions else None)
        risk_model_detail = self._risk_model_detail(
            field_id=request.field_id,
            uav_task_id=task_id,
            abnormal_region_id=selected_region_id,
        )
        confirmed = [item for item in phone_followups if item.confirm_status == "phone_confirmed"]
        summary = (
            f"本次巡检覆盖 {field.field_name}，发现 {len(regions)} 处 UAV dry-run 异常区域，"
            f"其中 {len(phone_followups)} 处已完成手机近景复查，{len(confirmed)} 处由手机模型标记为疑似病虫害。"
        )
        now = self._now()
        report = InspectionReport(
            report_id=f"REPORT_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}",
            field_id=request.field_id,
            uav_task_id=task_id,
            report_title=f"{field.field_name}无人机-手机协同病虫害巡检报告",
            report_date=now[:10],
            summary=summary,
            uav_summary={
                "task": task.model_dump() if task else None,
                "indices": [item.model_dump() for item in indices],
                "data_mode": task.data_mode if task else "dry_run",
                "is_mock": task.is_mock if task else True,
            },
            abnormal_region_summary={
                "total": len(regions),
                "items": [item.model_dump() for item in regions],
            },
            phone_followup_summary={
                "total": len(phone_followups),
                "confirmed_count": len(confirmed),
                "items": [item.model_dump() for item in phone_followups],
            },
            risk_summary=(
                {
                    "risk_level": risk.risk_level,
                    "risk_score": risk.risk_score,
                    "risk_probability_note": risk.risk_probability_note,
                    "predicted_diseases": [item.model_dump() for item in risk.predicted_diseases],
                    "main_factors": risk.main_factors,
                    "suggestion": risk.suggestion.model_dump(),
                    "model": risk.model.model_dump(),
                }
                if risk
                else {}
            ),
            risk_model_detail=risk_model_detail,
            rag_suggestion=rag_suggestion,
            model_safety_note=MODEL_SAFETY_NOTE,
            report_status="generated",
            payload={
                "field": field.model_dump(),
                "model_boundary": {
                    "formal_metric_available": False,
                    "rule_weighted_risk_note": RULE_RISK_SAFETY_NOTE,
                    "note": "当前报告允许整合 mock/smoke/experimental 和 dry-run 结果，但不能展示为正式农业诊断或正式模型指标。",
                },
            },
            created_at=now,
            updated_at=now,
        )
        self.repository.save(report)
        return report

    def get(self, report_id: str) -> InspectionReport:
        report = self.repository.get(report_id)
        if not report:
            raise AppException("REPORT_NOT_FOUND", "巡检报告不存在", {"report_id": report_id})
        return report

    def list_reports(self, field_id: str | None = None) -> InspectionReportListResponse:
        items = self.repository.list_reports(field_id=field_id)
        return InspectionReportListResponse(items=items, total=len(items))

    def _rag_suggestion(self, growth_stage: str | None, regions: list, risk) -> str:
        disease = None
        for region in regions:
            if region.confirmed_disease_type:
                disease = region.confirmed_disease_type
                break
        if not disease and risk and risk.predicted_diseases:
            disease = risk.predicted_diseases[0].label
        query = " ".join(
            item
            for item in [
                "宿迁 水稻",
                disease or "病虫害",
                growth_stage or "",
                "无人机长势异常 手机近景识别 绿色防控 复查建议",
            ]
            if item
        )
        try:
            chunks = knowledge_service.search_knowledge(query=query, top_k=3)
        except Exception:
            chunks = []
        if not chunks:
            return ""
        points = [str(item.get("text", "")).strip() for item in chunks if item.get("text")]
        joined = "；".join(points[:2])
        return (
            f"知识库检索建议：{joined}。请结合田间复查结果判断，必要时联系当地农技人员确认，"
            "不得将本系统建议直接作为农药处方或剂量依据。"
        )

    def _risk_model_detail(
        self,
        field_id: str,
        uav_task_id: str | None,
        abnormal_region_id: str | None,
    ) -> dict:
        if not uav_task_id:
            return {
                "model_type": "rule_weighted_score",
                "model_stage": "experimental",
                "probability_claim": False,
                "safety_note": RULE_RISK_SAFETY_NOTE,
                "status": "skipped_no_uav_task",
            }
        try:
            result = risk_fusion_scorer.evaluate(
                RiskFusionEvaluateRequest(
                    field_id=field_id,
                    uav_task_id=uav_task_id,
                    abnormal_region_id=abnormal_region_id,
                    include_weather=True,
                    include_history=True,
                    include_treatment=True,
                )
            )
        except Exception as exc:
            return {
                "model_type": "rule_weighted_score",
                "model_stage": "experimental",
                "probability_claim": False,
                "safety_note": RULE_RISK_SAFETY_NOTE,
                "status": "unavailable",
                "reason": str(exc),
            }
        return result.model_dump()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


inspection_report_service = InspectionReportService()
