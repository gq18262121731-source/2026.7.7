from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.core.constants import (
    DEFAULT_REGION_NAME,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_NORMAL,
    SEVERITY_HEAVY,
    SEVERITY_LIGHT,
    SEVERITY_MEDIUM,
    SEVERITY_NONE,
)
from app.database.repositories import DetectionRecordRepository
from app.schemas.dashboard import (
    DashboardSummary,
    DiseaseStatisticsResponse,
    DiseaseStatisticItem,
    DiseaseTypeCount,
    HeatmapPoint,
    HeatmapResponse,
    LatestAlertItem,
    LatestAlertsResponse,
    LatestRecordItem,
    LatestRecordsResponse,
    PlotStatisticItem,
    PlotDetailResponse,
    PlotStatisticsResponse,
)
from app.schemas.detection_result import DetectionResult
from app.services.inference.model_display import is_disease_like_record


RISK_ORDER = {
    RISK_NORMAL: 0,
    RISK_LOW: 1,
    RISK_MEDIUM: 2,
    RISK_HIGH: 3,
}

SEVERITY_ORDER = {
    SEVERITY_NONE: 0,
    SEVERITY_LIGHT: 1,
    SEVERITY_MEDIUM: 2,
    SEVERITY_HEAVY: 3,
}

HEATMAP_STYLE = {
    RISK_NORMAL: (0.1, "#22c55e"),
    RISK_LOW: (0.3, "#eab308"),
    RISK_MEDIUM: (0.6, "#f59e0b"),
    RISK_HIGH: (1.0, "#ef4444"),
}


class DashboardService:
    def __init__(self, repository: DetectionRecordRepository | None = None) -> None:
        self.repository = repository or DetectionRecordRepository()
        self.mock_plots = self._load_mock_plots()

    def summary(self) -> DashboardSummary:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        all_records = self._all_records()
        disease_records = self._disease_records(all_records)
        risk_counts = self._risk_level_counts(disease_records)
        severity_counts = self._severity_counts(disease_records)
        plot_items = self.plot_statistics().items
        return DashboardSummary(
            today_detect_count=self.repository.count_today(today),
            total_record_count=len(all_records),
            disease_record_count=sum(1 for record in disease_records if record.summary.severity != SEVERITY_NONE),
            normal_record_count=risk_counts.get(RISK_NORMAL, 0),
            high_risk_plot_count=sum(1 for plot in plot_items if plot.risk_level == RISK_HIGH),
            medium_risk_plot_count=sum(1 for plot in plot_items if plot.risk_level == RISK_MEDIUM),
            low_risk_plot_count=sum(1 for plot in plot_items if plot.risk_level == RISK_LOW),
            risk_level_counts=risk_counts,
            severity_counts=severity_counts,
            top_diseases=self.disease_statistics().items,
            latest_alerts=self.latest_alerts(limit=10).items,
            latest_records=self.latest_records(limit=10).items,
        )

    def plot_statistics(
        self,
        region_name: str | None = None,
        risk_level: str | None = None,
        disease: str | None = None,
    ) -> PlotStatisticsResponse:
        grouped: dict[str, list[DetectionResult]] = defaultdict(list)
        for record in self._all_records():
            plot_id = record.plot_id or "unknown_plot"
            grouped[plot_id].append(record)

        items: list[PlotStatisticItem] = []
        for plot_id, records in grouped.items():
            latest = max(records, key=lambda item: item.timestamp)
            disease_records = self._disease_records(records)
            risk = self._max_risk(disease_records)
            severity = self._max_severity(disease_records)
            main_disease = self._main_disease(disease_records)
            geo = self._resolve_geo(latest)
            item = PlotStatisticItem(
                plot_id=plot_id,
                plot_name=latest.plot_name or self.mock_plots.get(plot_id, {}).get("plot_name"),
                region_name=latest.region_name or self.mock_plots.get(plot_id, {}).get("region_name") or DEFAULT_REGION_NAME,
                record_count=len(records),
                disease_record_count=sum(1 for record in disease_records if record.summary.severity != SEVERITY_NONE),
                main_disease=main_disease,
                max_severity=severity,
                risk_level=risk,
                latest_detect_time=latest.timestamp,
                geo=geo,
            )
            if region_name and item.region_name != region_name:
                continue
            if risk_level and item.risk_level != risk_level:
                continue
            if disease and item.main_disease != disease:
                continue
            items.append(item)
        items.sort(key=lambda item: item.latest_detect_time, reverse=True)
        return PlotStatisticsResponse(total=len(items), items=items)

    def heatmap(
        self,
        region_name: str | None = None,
        disease: str | None = None,
        risk_level: str | None = None,
    ) -> HeatmapResponse:
        points: list[HeatmapPoint] = []
        for plot in self.plot_statistics(region_name=region_name, disease=disease, risk_level=risk_level).items:
            if plot.geo.lng is None or plot.geo.lat is None:
                continue
            intensity, color = HEATMAP_STYLE.get(plot.risk_level, HEATMAP_STYLE[RISK_NORMAL])
            points.append(
                HeatmapPoint(
                    plot_id=plot.plot_id,
                    plot_name=plot.plot_name,
                    region_name=plot.region_name,
                    lng=plot.geo.lng,
                    lat=plot.geo.lat,
                    risk_level=plot.risk_level,
                    severity=plot.max_severity,
                    main_disease=plot.main_disease,
                    intensity=intensity,
                    color=color,
                    record_count=plot.record_count,
                )
            )
        return HeatmapResponse(total=len(points), points=points)

    def plot_detail(self, plot_id: str) -> PlotDetailResponse | None:
        records = self.repository.list_records(plot_id=plot_id, page=1, page_size=10000, sort="created_at_desc")
        if not records:
            return None
        latest = max(records, key=lambda item: item.timestamp)
        disease_records = self._disease_records(records)
        disease_counter = Counter(record.summary.main_disease for record in disease_records if record.summary.main_disease)
        latest_alert = None
        try:
            from app.services.alert_service import alert_service

            latest_alert = alert_service.latest_for_plot(plot_id)
        except Exception:
            latest_alert = None
        risk_level = self._max_risk(disease_records)
        max_severity = self._max_severity(disease_records)
        main_disease = disease_counter.most_common(1)[0][0] if disease_counter else None
        return PlotDetailResponse(
            plot_id=plot_id,
            plot_name=latest.plot_name or self.mock_plots.get(plot_id, {}).get("plot_name"),
            region_name=latest.region_name or self.mock_plots.get(plot_id, {}).get("region_name") or DEFAULT_REGION_NAME,
            geo=self._resolve_geo(latest),
            record_count=len(records),
            disease_record_count=sum(1 for record in disease_records if record.summary.severity != SEVERITY_NONE),
            normal_record_count=len(records) - sum(1 for record in disease_records if record.summary.severity != SEVERITY_NONE),
            main_disease=main_disease,
            disease_types=[DiseaseTypeCount(label=label, count=count) for label, count in disease_counter.most_common()],
            max_severity=max_severity,
            risk_level=risk_level,
            latest_detect_time=latest.timestamp,
            latest_record=latest,
            latest_alert=latest_alert,
            suggestion_summary=self._suggestion_summary(risk_level, max_severity),
        )

    def latest_records(self, limit: int = 10) -> LatestRecordsResponse:
        records = self.repository.list_records(limit=max(1, min(limit, 50)))
        return LatestRecordsResponse(items=[self._to_latest_record(record) for record in records])

    def latest_alerts(self, limit: int = 10) -> LatestAlertsResponse:
        high_records = [record for record in self.repository.list_records(risk_level=RISK_HIGH, limit=50) if is_disease_like_record(record)]
        medium_records = [record for record in self.repository.list_records(risk_level=RISK_MEDIUM, limit=50) if is_disease_like_record(record)]
        records = sorted([*high_records, *medium_records], key=lambda item: item.timestamp, reverse=True)[:limit]
        return LatestAlertsResponse(items=[self._to_alert(record) for record in records])

    def disease_statistics_response(self) -> list[DiseaseStatisticItem]:
        records = [record for record in self._all_records() if is_disease_like_record(record) and record.summary.main_disease]
        total = len(records)
        disease_counts = Counter(record.summary.main_disease for record in records if record.summary.main_disease)
        risk_max: dict[str, str] = {}
        for record in records:
            label = record.summary.main_disease
            if not label:
                continue
            current = risk_max.get(label, RISK_NORMAL)
            risk_max[label] = record.summary.risk_level if RISK_ORDER[record.summary.risk_level] > RISK_ORDER[current] else current
        return [
            DiseaseStatisticItem(
                label=label,
                count=count,
                ratio=round(count / total, 4) if total else 0.0,
                risk_level_max=risk_max.get(label),
            )
            for label, count in disease_counts.most_common()
        ]

    def disease_statistics(self) -> DiseaseStatisticsResponse:
        return DiseaseStatisticsResponse(items=self.disease_statistics_response())

    def _all_records(self) -> list[DetectionResult]:
        return self.repository.list_records(page=1, page_size=10000, sort="created_at_desc")

    def _disease_records(self, records: list[DetectionResult]) -> list[DetectionResult]:
        return [record for record in records if is_disease_like_record(record)]

    def _risk_level_counts(self, records: list[DetectionResult]) -> dict[str, int]:
        counts = Counter(record.summary.risk_level for record in records)
        return {risk: counts.get(risk, 0) for risk in [RISK_NORMAL, RISK_LOW, RISK_MEDIUM, RISK_HIGH]}

    def _severity_counts(self, records: list[DetectionResult]) -> dict[str, int]:
        counts = Counter(record.summary.severity for record in records)
        return {
            SEVERITY_NONE: counts.get(SEVERITY_NONE, 0),
            SEVERITY_LIGHT: counts.get(SEVERITY_LIGHT, 0),
            SEVERITY_MEDIUM: counts.get(SEVERITY_MEDIUM, 0),
            SEVERITY_HEAVY: counts.get(SEVERITY_HEAVY, 0),
        }

    def _max_risk(self, records: list[DetectionResult]) -> str:
        return max((record.summary.risk_level for record in records), key=lambda risk: RISK_ORDER.get(risk, 0), default=RISK_NORMAL)

    def _max_severity(self, records: list[DetectionResult]) -> str:
        return max((record.summary.severity for record in records), key=lambda severity: SEVERITY_ORDER.get(severity, 0), default=SEVERITY_NONE)

    def _main_disease(self, records: list[DetectionResult]) -> str | None:
        counter = Counter(record.summary.main_disease for record in records if record.summary.main_disease)
        return counter.most_common(1)[0][0] if counter else None

    def _resolve_geo(self, record: DetectionResult):
        if record.geo.lng is not None and record.geo.lat is not None:
            return record.geo
        plot = self.mock_plots.get(record.plot_id or "")
        if plot:
            return {"lng": plot.get("lng"), "lat": plot.get("lat")}
        return {"lng": None, "lat": None}

    def _to_latest_record(self, record: DetectionResult) -> LatestRecordItem:
        return LatestRecordItem(
            record_id=record.record_id,
            plot_name=record.plot_name,
            main_disease=record.summary.main_disease,
            severity=record.summary.severity,
            risk_level=record.summary.risk_level,
            result_image_url=record.result_image_url,
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

    def _to_alert(self, record: DetectionResult) -> LatestAlertItem:
        plot_name = record.plot_name or record.plot_id or "\u672a\u6307\u5b9a\u5730\u5757"
        level_text = "\u9ad8\u98ce\u9669" if record.summary.risk_level == RISK_HIGH else "\u4e2d\u98ce\u9669"
        return LatestAlertItem(
            alert_id=f"alert_{record.record_id}",
            record_id=record.record_id,
            plot_id=record.plot_id,
            plot_name=record.plot_name,
            main_disease=record.summary.main_disease,
            severity=record.summary.severity,
            risk_level=record.summary.risk_level,
            message=f"{plot_name}\u68c0\u6d4b\u5230{level_text}\u75c5\u866b\u5bb3\uff0c\u8bf7\u53ca\u65f6\u590d\u6838\u3002",
            timestamp=record.timestamp,
            is_smoke=record.is_smoke,
            model_stage=record.model_stage,
            current_target_type=record.current_target_type,
            model_name=record.model_name,
            fallback_to_mock=record.fallback_to_mock,
            model_warning=record.model_warning,
        )

    def _suggestion_summary(self, risk_level: str, severity: str) -> str:
        if risk_level == RISK_HIGH:
            return "\u8be5\u5730\u5757\u5b58\u5728\u9ad8\u98ce\u9669\u75c5\u866b\u5bb3\uff0c\u5efa\u8bae\u5c3d\u5feb\u4eba\u5de5\u590d\u6838\u3002"
        if risk_level == RISK_MEDIUM:
            return "\u8be5\u5730\u5757\u5b58\u5728\u4e2d\u5ea6\u75c5\u5bb3\u98ce\u9669\uff0c\u5efa\u8bae\u5c3d\u5feb\u8fdb\u884c\u4eba\u5de5\u590d\u6838\u3002"
        if risk_level == "low":
            return "\u8be5\u5730\u5757\u5b58\u5728\u8f7b\u5ea6\u98ce\u9669\uff0c\u5efa\u8bae\u6301\u7eed\u89c2\u5bdf\u3002"
        return "\u8be5\u5730\u5757\u6682\u672a\u53d1\u73b0\u660e\u663e\u75c5\u866b\u5bb3\u98ce\u9669\u3002"

    def _load_mock_plots(self) -> dict[str, dict]:
        path = Path(__file__).resolve().parents[2] / "mocks" / "mock_plots.json"
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return {item["plot_id"]: item for item in data if item.get("plot_id")}


dashboard_service = DashboardService()
