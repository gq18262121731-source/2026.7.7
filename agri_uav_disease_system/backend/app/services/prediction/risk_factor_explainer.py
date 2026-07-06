from __future__ import annotations


FACTOR_TEXT = {
    "same_disease_30d": "最近 30 天出现同类病虫害识别记录",
    "medium_7d": "最近 7 天存在中风险识别记录",
    "high_7d": "最近 7 天存在高风险识别记录",
    "susceptible_stage": "当前处于易感生育期",
    "high_humidity_3d": "近 3 天平均湿度较高",
    "rainfall_3d": "近 3 天有明显降雨",
    "no_operation_7d": "最近 7 天无有效管护记录",
    "recent_operation_7d": "最近 7 天已有复查、排水或管护记录",
    "many_active_alerts": "当前 active 预警数量较多",
    "continuous_same_disease": "连续出现同一种病虫害",
}


class RiskFactorExplainer:
    def explain(self, factor_codes: list[str]) -> list[str]:
        return [FACTOR_TEXT.get(code, code) for code in factor_codes]


risk_factor_explainer = RiskFactorExplainer()
