from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


FarmAnalysisReportType = Literal["record_analysis", "plot_analysis", "daily_summary"]
FarmAnalysisStatus = Literal["success", "fallback", "failed"]


class FarmAnalysisReportRequest(BaseModel):
    plot_id: str = Field(default="plot_001", min_length=1, max_length=120)
    record_id: str | None = Field(default=None, max_length=120)
    crop: Literal["rice"] = "rice"
    include_weather: bool = True
    include_history_days: int = Field(default=7, ge=1, le=30)
    report_type: FarmAnalysisReportType = "record_analysis"


class FarmAnalysisReportResponse(BaseModel):
    success: bool = True
    report_id: str
    status: FarmAnalysisStatus
    summary: str
    pdf_url: str
    preview_url: str
    fallback_used: bool = False
    weather_available: bool = False
    rag_available: bool = False
    pdf_fallback_used: bool = False
    created_at: str


class FarmAnalysisReportHistoryItem(BaseModel):
    report_id: str
    plot_id: str
    record_id: str | None = None
    report_type: FarmAnalysisReportType
    crop: str
    summary: str
    pdf_url: str
    preview_url: str
    fallback_used: bool = False
    weather_available: bool = False
    rag_available: bool = False
    pdf_fallback_used: bool = False
    created_at: str


class FarmAnalysisReportHistoryResponse(BaseModel):
    items: list[FarmAnalysisReportHistoryItem] = Field(default_factory=list)
    total: int


class FarmAnalysisReportMetadata(BaseModel):
    report_id: str
    plot_id: str
    record_id: str | None = None
    report_type: FarmAnalysisReportType
    crop: str
    summary: str
    pdf_path: str
    html_path: str
    pdf_url: str
    preview_url: str
    weather_snapshot: dict[str, Any] = Field(default_factory=dict)
    record_snapshot: dict[str, Any] = Field(default_factory=dict)
    history_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    rag_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    chart_snapshot: dict[str, Any] = Field(default_factory=dict)
    llm_result_snapshot: dict[str, Any] = Field(default_factory=dict)
    llm_mode: str = "mock"
    fallback_used: bool = False
    api_error_type: str | None = None
    weather_available: bool = False
    rag_available: bool = False
    pdf_fallback_used: bool = False
    created_at: str
