from __future__ import annotations

from app.core.constants import (
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_NORMAL,
    SEVERITY_HEAVY,
    SEVERITY_LIGHT,
    SEVERITY_MEDIUM,
    SEVERITY_NONE,
)


class RiskLevelEvaluator:
    mapping = {
        SEVERITY_NONE: RISK_NORMAL,
        SEVERITY_LIGHT: RISK_LOW,
        SEVERITY_MEDIUM: RISK_MEDIUM,
        SEVERITY_HEAVY: RISK_HIGH,
    }

    def evaluate(self, severity: str) -> str:
        return self.mapping.get(severity, RISK_NORMAL)
