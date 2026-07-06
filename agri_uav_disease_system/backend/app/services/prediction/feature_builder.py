from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from app.database.alert_repositories import AlertRepository
from app.database.farm_operation_repositories import FarmOperationRepository
from app.database.growth_stage_repositories import GrowthStageRepository
from app.database.repositories import DetectionRecordRepository
from app.database.weather_repositories import WeatherRepository
from app.services.inference.model_display import is_disease_like_record


class FeatureBuilder:
    def __init__(
        self,
        detection_repository: DetectionRecordRepository | None = None,
        weather_repository: WeatherRepository | None = None,
        growth_repository: GrowthStageRepository | None = None,
        operation_repository: FarmOperationRepository | None = None,
        alert_repository: AlertRepository | None = None,
    ) -> None:
        self.detection_repository = detection_repository or DetectionRecordRepository()
        self.weather_repository = weather_repository or WeatherRepository()
        self.growth_repository = growth_repository or GrowthStageRepository()
        self.operation_repository = operation_repository or FarmOperationRepository()
        self.alert_repository = alert_repository or AlertRepository()

    def build(self, plot_id: str, prediction_window_days: int, disease: str | None = None) -> dict:
        now = datetime.now(timezone.utc)
        records = [
            record
            for record in self.detection_repository.list_records(plot_id=plot_id, page=1, page_size=10000)
            if is_disease_like_record(record)
        ]
        weather = self.weather_repository.recent_for_plot(plot_id, limit=7)
        growth = self.growth_repository.latest_for_plot(plot_id)
        operations = self.operation_repository.recent_for_plot(plot_id, limit=20)
        alerts = self.alert_repository.list_alerts(status="active", plot_id=plot_id, page=1, page_size=100)

        disease_counter = Counter(record.summary.main_disease for record in records if record.summary.main_disease)
        predicted_disease = disease or (disease_counter.most_common(1)[0][0] if disease_counter else "稻瘟病")
        recent_30 = [record for record in records if self._within_days(record.timestamp, now, 30)]
        recent_7 = [record for record in records if self._within_days(record.timestamp, now, 7)]
        target_30 = [record for record in recent_30 if record.summary.main_disease == predicted_disease]
        same_recent_sequence = [record.summary.main_disease for record in sorted(recent_30, key=lambda item: item.timestamp, reverse=True)[:3]]

        weather_3 = weather[:3]
        humidity_values = [item.humidity_avg for item in weather_3 if item.humidity_avg is not None]
        rainfall_total = sum(item.rainfall_mm or 0 for item in weather_3)
        recent_operations_7 = [item for item in operations if self._within_days(item.operation_time, now, 7)]
        helpful_operations_7 = [
            item
            for item in recent_operations_7
            if any(keyword in item.operation_type for keyword in ["复查", "排水", "管护", "巡查"])
        ]

        return {
            "plot_id": plot_id,
            "prediction_window_days": prediction_window_days,
            "predicted_disease": predicted_disease,
            "records_30d_count": len(recent_30),
            "same_disease_30d_count": len(target_30),
            "medium_7d_count": sum(1 for record in recent_7 if record.summary.risk_level == "medium"),
            "high_7d_count": sum(1 for record in recent_7 if record.summary.risk_level == "high"),
            "growth_stage": growth.growth_stage if growth else None,
            "humidity_3d_avg": round(sum(humidity_values) / len(humidity_values), 2) if humidity_values else None,
            "rainfall_3d_total": round(rainfall_total, 2),
            "operation_7d_count": len(recent_operations_7),
            "helpful_operation_7d_count": len(helpful_operations_7),
            "active_alert_count": len(alerts),
            "continuous_same_disease": len(same_recent_sequence) >= 2 and len(set(same_recent_sequence[:2])) == 1,
        }

    def _within_days(self, value: str | None, now: datetime, days: int) -> bool:
        if not value:
            return False
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = datetime.fromisoformat(value[:10]).replace(tzinfo=timezone.utc)
            except ValueError:
                return False
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return now - timedelta(days=days) <= parsed <= now + timedelta(minutes=1)


feature_builder = FeatureBuilder()
