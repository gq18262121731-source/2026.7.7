from __future__ import annotations

from app.core.constants import ERROR_RECORD_NOT_FOUND
from app.core.exceptions import AppException
from app.schemas.alert import AlertListResponse
from app.schemas.detection_result import Suggestion
from app.schemas.mobile import (
    MobileOverview,
    MobilePlotDetail,
    MobilePlotItem,
    MobilePlotListResponse,
    MobileRecordDetail,
)
from app.services.dashboard.dashboard_service import dashboard_service
from app.services.inference.model_display import is_disease_like_record
from app.services.storage.result_store import result_store


RISK_TEXT = {
    "normal": "\u6b63\u5e38",
    "low": "\u4f4e\u98ce\u9669",
    "medium": "\u4e2d\u98ce\u9669",
    "high": "\u9ad8\u98ce\u9669",
}


class MobileService:
    def alerts(self) -> AlertListResponse:
        records = [record for record in result_store.list_records(risk_level="high", limit=50) if is_disease_like_record(record)]
        records.extend(
            [
                record
                for record in result_store.list_records(risk_level="medium", limit=max(0, 50 - len(records)))
                if is_disease_like_record(record)
            ]
        )
        return AlertListResponse(total=len(records), alerts=records)

    def suggestion(self, record_id: str) -> Suggestion:
        record = result_store.get(record_id)
        if not record:
            raise AppException(ERROR_RECORD_NOT_FOUND, "\u8bc6\u522b\u8bb0\u5f55\u4e0d\u5b58\u5728", {"record_id": record_id})
        return record.suggestion

    def overview(self, user_id: str | None = None) -> MobileOverview:
        summary = dashboard_service.summary()
        return MobileOverview(
            today_detect_count=summary.today_detect_count,
            my_plot_count=len(dashboard_service.plot_statistics().items),
            high_risk_count=summary.high_risk_plot_count,
            medium_risk_count=summary.medium_risk_plot_count,
            latest_alerts=summary.latest_alerts,
            latest_records=summary.latest_records,
            summary_text=f"\u4eca\u65e5\u5df2\u5b8c\u6210 {summary.today_detect_count} \u6b21\u8bc6\u522b\uff0c\u5f53\u524d\u6709 {summary.high_risk_plot_count} \u4e2a\u9ad8\u98ce\u9669\u5730\u5757\u9700\u8981\u590d\u6838\u3002",
        )

    def plots(
        self,
        risk_level: str | None = None,
        region_name: str | None = None,
        keyword: str | None = None,
        user_id: str | None = None,
    ) -> MobilePlotListResponse:
        plots = dashboard_service.plot_statistics(region_name=region_name, risk_level=risk_level).items
        items: list[MobilePlotItem] = []
        for plot in plots:
            if keyword and keyword not in (plot.plot_name or "") and keyword not in plot.plot_id:
                continue
            items.append(
                MobilePlotItem(
                    plot_id=plot.plot_id,
                    plot_name=plot.plot_name,
                    region_name=plot.region_name,
                    risk_level=plot.risk_level,
                    max_severity=plot.max_severity,
                    main_disease=plot.main_disease,
                    latest_detect_time=plot.latest_detect_time,
                    suggestion_summary=dashboard_service._suggestion_summary(plot.risk_level, plot.max_severity),
                )
            )
        return MobilePlotListResponse(items=items, total=len(items))

    def plot_detail(self, plot_id: str) -> MobilePlotDetail:
        detail = dashboard_service.plot_detail(plot_id)
        if not detail:
            raise AppException(ERROR_RECORD_NOT_FOUND, "\u5730\u5757\u8bb0\u5f55\u4e0d\u5b58\u5728", {"plot_id": plot_id})
        recent = dashboard_service.latest_records(limit=50).items
        recent = [item for item in recent if result_store.get(item.record_id) and result_store.get(item.record_id).plot_id == plot_id][:5]
        return MobilePlotDetail(
            plot_id=detail.plot_id,
            plot_name=detail.plot_name,
            risk_level=detail.risk_level,
            risk_text=RISK_TEXT.get(detail.risk_level, detail.risk_level),
            main_disease=detail.main_disease,
            severity=detail.max_severity,
            latest_result_image_url=detail.latest_record.result_image_url,
            latest_detect_time=detail.latest_detect_time,
            suggestion=detail.latest_record.suggestion,
            recent_records=recent,
        )

    def record_detail(self, record_id: str) -> MobileRecordDetail:
        record = result_store.get(record_id)
        if not record:
            raise AppException(ERROR_RECORD_NOT_FOUND, "\u8bc6\u522b\u8bb0\u5f55\u4e0d\u5b58\u5728", {"record_id": record_id})
        return MobileRecordDetail(
            record_id=record.record_id,
            plot_id=record.plot_id,
            plot_name=record.plot_name,
            image_url=record.image_url,
            result_image_url=record.result_image_url,
            main_disease=record.summary.main_disease,
            severity=record.summary.severity,
            risk_level=record.summary.risk_level,
            detections=record.detections,
            suggestion=record.suggestion,
            timestamp=record.timestamp,
            source_type=record.source_type,
            model_name=record.model_name,
            model_version=record.model_version,
            detector_mode=record.detector_mode,
            is_smoke=record.is_smoke,
            model_stage=record.model_stage,
            formal_metric_available=record.formal_metric_available,
            current_target_type=record.current_target_type,
            fallback_to_mock=record.fallback_to_mock,
            model_hint=record.model_hint,
            target_type=record.target_type,
            model_display_name=record.model_display_name,
            model_warning=record.model_warning,
            model_usage_scope=record.model_usage_scope,
            model_capability_level=record.model_capability_level,
        )


mobile_service = MobileService()
