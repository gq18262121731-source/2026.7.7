from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.config import settings
from app.core.constants import (
    ALERT_STATUS_ACTIVE,
    RISK_HIGH,
    RISK_MEDIUM,
    RISK_NORMAL,
    SEVERITY_HEAVY,
    SEVERITY_LIGHT,
    SEVERITY_MEDIUM,
    SEVERITY_NONE,
)
from app.database.alert_repositories import AlertRepository
from app.schemas.alert import AlertAction, AlertDetail, AlertEvent
from app.schemas.detection_result import DetectionResult
from app.services.inference.model_display import is_disease_like_record
from app.services.realtime.alert_publisher import alert_publisher


RISK_ORDER = {RISK_NORMAL: 0, "low": 1, RISK_MEDIUM: 2, RISK_HIGH: 3}
SEVERITY_ORDER = {SEVERITY_NONE: 0, SEVERITY_LIGHT: 1, SEVERITY_MEDIUM: 2, SEVERITY_HEAVY: 3}


class AlertService:
    def __init__(self, repository: AlertRepository | None = None) -> None:
        self.repository = repository or AlertRepository()

    async def handle_detection_result(self, result: DetectionResult) -> AlertDetail | None:
        if not is_disease_like_record(result):
            return None
        if result.summary.risk_level not in {RISK_MEDIUM, RISK_HIGH}:
            return None

        now = self._now()
        plot_id = result.plot_id or "unknown_plot"
        main_disease = result.summary.main_disease
        existing = self.repository.find_active_in_cooldown(plot_id, main_disease, now)
        if existing:
            previous_severity = existing.severity
            previous_risk_level = existing.risk_level
            alert = self._update_existing(existing, result, now)
            self.repository.update(alert)
            action_type = "upgraded" if self._is_upgraded(previous_severity, previous_risk_level, alert) else "updated"
            self._save_action(alert.alert_id, action_type, note=f"latest_record_id={result.record_id}", created_at=now)
        else:
            alert = self._create_alert(result, now)
            self.repository.save(alert)
            self._save_action(alert.alert_id, "created", note=f"first_record_id={result.record_id}", created_at=now)

        await alert_publisher.publish(self.to_event(alert))
        return alert

    def list_alerts(
        self,
        status: str | None = None,
        risk_level: str | None = None,
        plot_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AlertDetail], int]:
        return (
            self.repository.list_alerts(status=status, risk_level=risk_level, plot_id=plot_id, page=page, page_size=page_size),
            self.repository.count_alerts(status=status, risk_level=risk_level, plot_id=plot_id),
        )

    def get_alert(self, alert_id: str) -> AlertDetail | None:
        return self.repository.get(alert_id)

    def latest_for_plot(self, plot_id: str) -> AlertDetail | None:
        return self.repository.latest_for_plot(plot_id)

    def resolve(
        self,
        alert_id: str,
        operator_id: str | None = None,
        operator_name: str | None = None,
        note: str | None = None,
    ) -> AlertDetail | None:
        alert = self.repository.get(alert_id)
        if not alert:
            return None
        alert.status = "resolved"
        now = self._now()
        alert.updated_at = now
        self.repository.update(alert)
        self._save_action(
            alert.alert_id,
            "resolved",
            operator_id=operator_id,
            operator_name=operator_name,
            note=note,
            created_at=now,
        )
        return alert

    def list_actions(self, alert_id: str) -> list[AlertAction] | None:
        if not self.repository.get(alert_id):
            return None
        return self.repository.list_actions(alert_id)

    def to_event(self, alert: AlertDetail) -> AlertEvent:
        return AlertEvent(
            alert_source=alert.alert_source,
            alert_id=alert.alert_id,
            plot_id=alert.plot_id,
            plot_name=alert.plot_name,
            region_name=alert.region_name,
            main_disease=alert.main_disease,
            severity=alert.severity,
            risk_level=alert.risk_level,
            status=alert.status,
            message=alert.message,
            latest_record_id=alert.latest_record_id,
            prediction_id=alert.prediction_id,
            prediction_window_days=alert.prediction_window_days,
            timestamp=alert.latest_seen_at,
        )

    def _create_alert(self, result: DetectionResult, now: str) -> AlertDetail:
        cooldown_until = self._cooldown_until()
        return AlertDetail(
            alert_id=f"alert_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}",
            alert_source="detection",
            plot_id=result.plot_id or "unknown_plot",
            plot_name=result.plot_name,
            region_name=result.region_name,
            main_disease=result.summary.main_disease,
            severity=result.summary.severity,
            risk_level=result.summary.risk_level,
            status=ALERT_STATUS_ACTIVE,
            message=self._message(result),
            suggestion=result.suggestion,
            record_ids=[result.record_id],
            first_record_id=result.record_id,
            latest_record_id=result.record_id,
            prediction_id=None,
            prediction_window_days=None,
            first_seen_at=now,
            latest_seen_at=now,
            cooldown_until=cooldown_until,
            created_at=now,
            updated_at=now,
        )

    def _update_existing(self, alert: AlertDetail, result: DetectionResult, now: str) -> AlertDetail:
        if result.record_id not in alert.record_ids:
            alert.record_ids.append(result.record_id)
        alert.latest_record_id = result.record_id
        alert.latest_seen_at = now
        alert.cooldown_until = self._cooldown_until()
        alert.updated_at = now
        alert.plot_name = result.plot_name or alert.plot_name
        alert.region_name = result.region_name or alert.region_name
        if SEVERITY_ORDER.get(result.summary.severity, 0) > SEVERITY_ORDER.get(alert.severity, 0):
            alert.severity = result.summary.severity
        if RISK_ORDER.get(result.summary.risk_level, 0) > RISK_ORDER.get(alert.risk_level, 0):
            alert.risk_level = result.summary.risk_level
        alert.message = self._message_from_alert(alert)
        alert.suggestion = result.suggestion
        return alert

    def _is_upgraded(self, previous_severity: str, previous_risk_level: str, alert: AlertDetail) -> bool:
        return (
            SEVERITY_ORDER.get(alert.severity, 0) > SEVERITY_ORDER.get(previous_severity, 0)
            or RISK_ORDER.get(alert.risk_level, 0) > RISK_ORDER.get(previous_risk_level, 0)
        )

    def _save_action(
        self,
        alert_id: str,
        action_type: str,
        operator_id: str | None = None,
        operator_name: str | None = None,
        note: str | None = None,
        created_at: str | None = None,
    ) -> AlertAction:
        action = AlertAction(
            action_id=f"action_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}",
            alert_id=alert_id,
            action_type=action_type,
            operator_id=operator_id,
            operator_name=operator_name,
            note=note,
            created_at=created_at or self._now(),
        )
        self.repository.save_action(action)
        return action

    def _message(self, result: DetectionResult) -> str:
        plot_name = result.plot_name or result.plot_id or "\u672a\u6307\u5b9a\u5730\u5757"
        level = "\u9ad8\u98ce\u9669" if result.summary.risk_level == RISK_HIGH else "\u4e2d\u98ce\u9669"
        return f"{plot_name}\u68c0\u6d4b\u5230{level}\u75c5\u866b\u5bb3\uff0c\u8bf7\u53ca\u65f6\u590d\u6838\u3002"

    def _message_from_alert(self, alert: AlertDetail) -> str:
        plot_name = alert.plot_name or alert.plot_id or "\u672a\u6307\u5b9a\u5730\u5757"
        level = "\u9ad8\u98ce\u9669" if alert.risk_level == RISK_HIGH else "\u4e2d\u98ce\u9669"
        return f"{plot_name}\u68c0\u6d4b\u5230{level}\u75c5\u866b\u5bb3\uff0c\u8bf7\u53ca\u65f6\u590d\u6838\u3002"

    def _cooldown_until(self) -> str:
        return (datetime.now(timezone.utc) + timedelta(seconds=settings.alert_cooldown_seconds)).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


alert_service = AlertService()
