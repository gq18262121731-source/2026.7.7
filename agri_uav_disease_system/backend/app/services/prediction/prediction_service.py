from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.constants import ALERT_STATUS_ACTIVE, DEFAULT_REGION_NAME, RISK_HIGH, RISK_MEDIUM, SEVERITY_MEDIUM
from app.database.alert_repositories import AlertRepository
from app.database.prediction_repositories import PredictionRepository
from app.schemas.alert import AlertDetail
from app.schemas.detection_result import Suggestion
from app.schemas.prediction import (
    PredictedDisease,
    PredictionModelInfo,
    PredictionRiskMapPoint,
    PredictionRiskMapResponse,
    PredictionSummaryResponse,
    RiskPredictionResponse,
)
from app.services.alert_service import alert_service
from app.services.dashboard.dashboard_service import dashboard_service
from app.services.prediction.feature_builder import FeatureBuilder
from app.services.prediction.risk_factor_explainer import risk_factor_explainer
from app.services.prediction.risk_rule_model import RiskRuleModel, risk_rule_model


ALLOWED_WINDOWS = {3, 7, 14}
RISK_MAP_STYLE = {
    "normal": (0.1, "#22c55e"),
    "low": (0.3, "#eab308"),
    "medium": (0.6, "#f59e0b"),
    "high": (1.0, "#ef4444"),
}


class PredictionService:
    def __init__(
        self,
        repository: PredictionRepository | None = None,
        feature_builder: FeatureBuilder | None = None,
        model: RiskRuleModel | None = None,
        alert_repository: AlertRepository | None = None,
    ) -> None:
        self.repository = repository or PredictionRepository()
        self.feature_builder = feature_builder or FeatureBuilder()
        self.model = model or risk_rule_model
        self.alert_repository = alert_repository or AlertRepository()

    async def predict_plot(
        self,
        plot_id: str,
        window_days: int = 7,
        disease: str | None = None,
        save: bool = True,
        create_alert: bool = True,
    ) -> RiskPredictionResponse:
        self._validate_window(window_days)
        now = self._now()
        features = self.feature_builder.build(plot_id, window_days, disease=disease)
        raw = self.model.predict(features)
        factors = risk_factor_explainer.explain(raw["factor_codes"])
        suggestion = self._suggestion(window_days, raw["risk_level"], features["predicted_disease"])
        prediction = RiskPredictionResponse(
            plot_id=plot_id,
            prediction_window_days=window_days,
            prediction_time=now,
            risk_score=raw["risk_score"],
            risk_probability=raw["risk_probability"],
            risk_level=raw["risk_level"],
            predicted_diseases=[
                PredictedDisease(label=features["predicted_disease"], probability=raw["risk_probability"])
            ],
            main_factors=factors,
            suggestion=suggestion,
            model=PredictionModelInfo(type=self.model.model_type, version=self.model.model_version),
            prediction_id=f"pred_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}" if save else None,
        )
        if save:
            self.repository.save(prediction, input_snapshot=features)
        if create_alert and save and prediction.risk_level in {RISK_MEDIUM, RISK_HIGH}:
            await self._create_prediction_alert(prediction)
        return prediction

    def summary(self) -> PredictionSummaryResponse:
        predictions = self.repository.list_predictions(limit=10000)
        latest_by_plot: dict[str, RiskPredictionResponse] = {}
        for item in predictions:
            latest_by_plot.setdefault(item.plot_id, item)
        latest = list(latest_by_plot.values())
        disease_counts = Counter(
            item.predicted_diseases[0].label for item in latest if item.predicted_diseases
        )
        factor_counts = Counter(factor for item in latest for factor in item.main_factors)
        top = sorted(latest, key=lambda item: item.risk_score, reverse=True)[:10]
        return PredictionSummaryResponse(
            high_risk_plot_count=sum(1 for item in latest if item.risk_level == RISK_HIGH),
            medium_risk_plot_count=sum(1 for item in latest if item.risk_level == RISK_MEDIUM),
            top_risk_plots=[
                {
                    "plot_id": item.plot_id,
                    "risk_level": item.risk_level,
                    "risk_score": item.risk_score,
                    "predicted_disease": item.predicted_diseases[0].label if item.predicted_diseases else None,
                }
                for item in top
            ],
            top_predicted_diseases=[
                {"label": label, "count": count} for label, count in disease_counts.most_common(10)
            ],
            risk_factor_counts=dict(factor_counts),
        )

    def risk_map(self) -> PredictionRiskMapResponse:
        predictions = self.repository.list_predictions(limit=10000)
        latest_by_plot: dict[str, RiskPredictionResponse] = {}
        for item in predictions:
            latest_by_plot.setdefault(item.plot_id, item)
        points: list[PredictionRiskMapPoint] = []
        for item in latest_by_plot.values():
            detail = dashboard_service.plot_detail(item.plot_id)
            geo = detail.geo if detail else None
            intensity, color = RISK_MAP_STYLE.get(item.risk_level, RISK_MAP_STYLE["normal"])
            points.append(
                PredictionRiskMapPoint(
                    plot_id=item.plot_id,
                    plot_name=detail.plot_name if detail else None,
                    lng=geo.lng if geo else None,
                    lat=geo.lat if geo else None,
                    predicted_risk_level=item.risk_level,
                    predicted_disease=item.predicted_diseases[0].label if item.predicted_diseases else None,
                    risk_score=item.risk_score,
                    intensity=intensity,
                    color=color,
                )
            )
        return PredictionRiskMapResponse(total=len(points), points=points)

    def mobile_predictions(self, limit: int = 50) -> list[RiskPredictionResponse]:
        order = {"high": 0, "medium": 1, "low": 2, "normal": 3}
        items = self.repository.list_predictions(limit=limit)
        return sorted(items, key=lambda item: (order.get(item.risk_level, 9), -item.risk_score))

    def latest_for_plot(self, plot_id: str) -> RiskPredictionResponse | None:
        return self.repository.latest_for_plot(plot_id)

    async def _create_prediction_alert(self, prediction: RiskPredictionResponse) -> AlertDetail:
        now = prediction.prediction_time
        disease = prediction.predicted_diseases[0].label if prediction.predicted_diseases else None
        level_text = "高" if prediction.risk_level == RISK_HIGH else "中"
        plot_detail = dashboard_service.plot_detail(prediction.plot_id)
        alert = AlertDetail(
            alert_id=f"alert_pred_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}",
            alert_source="prediction",
            plot_id=prediction.plot_id,
            plot_name=plot_detail.plot_name if plot_detail else prediction.plot_id,
            region_name=plot_detail.region_name if plot_detail else DEFAULT_REGION_NAME,
            main_disease=disease,
            severity=SEVERITY_MEDIUM,
            risk_level=prediction.risk_level,
            status=ALERT_STATUS_ACTIVE,
            message=f"预测未来 {prediction.prediction_window_days} 天存在{level_text}风险病虫害风险，请及时关注。",
            suggestion=prediction.suggestion,
            record_ids=[],
            first_record_id="",
            latest_record_id="",
            prediction_id=prediction.prediction_id,
            prediction_window_days=prediction.prediction_window_days,
            first_seen_at=now,
            latest_seen_at=now,
            cooldown_until=(datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            created_at=now,
            updated_at=now,
        )
        self.alert_repository.save(alert)
        from app.services.realtime.alert_publisher import alert_publisher

        await alert_publisher.publish(alert_service.to_event(alert))
        return alert

    def _suggestion(self, window_days: int, risk_level: str, disease: str) -> Suggestion:
        level_text = {"high": "较高", "medium": "中等", "low": "较低", "normal": "较低"}.get(risk_level, "未知")
        return Suggestion(
            title=f"未来 {window_days} 天存在{level_text}病虫害风险",
            content="建议加强田间巡查，关注湿度、通风和积水情况，具体防治方案需由农技人员确认。",
            need_expert_confirm=True,
            actions=["加强田间巡查", "关注田间湿度和积水情况", "必要时联系农技人员复核"],
            knowledge_tags=["风险预测", disease, "田间巡查"],
            disclaimer="本建议为辅助参考，具体防治方案和用药剂量需由农技人员确认。",
        )

    def _validate_window(self, window_days: int) -> None:
        if window_days not in ALLOWED_WINDOWS:
            from app.core.exceptions import AppException

            raise AppException("INVALID_PREDICTION_WINDOW", "window_days 仅支持 3、7、14", {"window_days": window_days})

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


prediction_service = PredictionService()
