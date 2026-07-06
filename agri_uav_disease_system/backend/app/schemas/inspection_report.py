from __future__ import annotations

from pydantic import BaseModel, Field


MODEL_SAFETY_NOTE = (
    "本报告由系统根据无人机图像、手机近景识别结果、规则风险评分和知识库检索结果自动生成，"
    "仅作为病虫害巡检与治理辅助参考，不替代农技人员现场诊断，不作为农药处方依据。"
)


class InspectionReportGenerateRequest(BaseModel):
    field_id: str
    uav_task_id: str | None = None
    include_rag: bool = True
    include_risk: bool = True


class InspectionReport(BaseModel):
    report_id: str
    field_id: str
    uav_task_id: str | None = None
    report_title: str
    report_date: str
    summary: str
    uav_summary: dict
    abnormal_region_summary: dict
    phone_followup_summary: dict
    risk_summary: dict
    risk_model_detail: dict = Field(default_factory=dict)
    rag_suggestion: str
    model_safety_note: str = MODEL_SAFETY_NOTE
    report_status: str = "generated"
    payload: dict
    created_at: str
    updated_at: str


class InspectionReportListResponse(BaseModel):
    items: list[InspectionReport]
    total: int
