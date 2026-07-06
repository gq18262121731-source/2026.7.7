from __future__ import annotations

from dataclasses import dataclass, field

from app.core.constants import RISK_HIGH, RISK_LOW, RISK_MEDIUM, RISK_NORMAL


@dataclass(frozen=True)
class RiskRuleConfig:
    base_score: int = 10
    same_disease_30d: int = 20
    medium_7d: int = 15
    high_7d: int = 25
    susceptible_stage: int = 15
    high_humidity_3d: int = 15
    rainfall_3d: int = 10
    no_operation_7d: int = 10
    recent_operation_7d: int = -10
    many_active_alerts: int = 10
    continuous_same_disease: int = 10
    high_humidity_threshold: float = 80.0
    rainfall_threshold_mm: float = 10.0
    active_alert_threshold: int = 2
    susceptible_stages: set[str] = field(default_factory=lambda: {"分蘖期", "拔节孕穗期", "抽穗扬花期"})


class RiskRuleModel:
    model_type = "rule_based"
    model_version = "risk-rule-v0.1"

    def __init__(self, config: RiskRuleConfig | None = None) -> None:
        self.config = config or RiskRuleConfig()

    def predict(self, features: dict) -> dict:
        score = self.config.base_score
        factors: list[str] = []

        score = self._add(score, factors, "same_disease_30d", features.get("same_disease_30d_count", 0) > 0)
        score = self._add(score, factors, "medium_7d", features.get("medium_7d_count", 0) > 0)
        score = self._add(score, factors, "high_7d", features.get("high_7d_count", 0) > 0)
        score = self._add(score, factors, "susceptible_stage", features.get("growth_stage") in self.config.susceptible_stages)
        humidity = features.get("humidity_3d_avg")
        score = self._add(score, factors, "high_humidity_3d", humidity is not None and humidity >= self.config.high_humidity_threshold)
        score = self._add(score, factors, "rainfall_3d", features.get("rainfall_3d_total", 0) >= self.config.rainfall_threshold_mm)
        score = self._add(score, factors, "no_operation_7d", features.get("operation_7d_count", 0) == 0)
        score = self._add(score, factors, "recent_operation_7d", features.get("helpful_operation_7d_count", 0) > 0)
        score = self._add(score, factors, "many_active_alerts", features.get("active_alert_count", 0) >= self.config.active_alert_threshold)
        score = self._add(score, factors, "continuous_same_disease", bool(features.get("continuous_same_disease")))

        score = max(0, min(100, score))
        return {
            "risk_score": score,
            "risk_probability": round(score / 100, 4),
            "risk_level": self._level(score),
            "factor_codes": factors,
        }

    def _add(self, score: int, factors: list[str], code: str, condition: bool) -> int:
        if not condition:
            return score
        factors.append(code)
        return score + int(getattr(self.config, code))

    def _level(self, score: int) -> str:
        if score <= 25:
            return RISK_NORMAL
        if score <= 50:
            return RISK_LOW
        if score <= 75:
            return RISK_MEDIUM
        return RISK_HIGH


risk_rule_model = RiskRuleModel()
