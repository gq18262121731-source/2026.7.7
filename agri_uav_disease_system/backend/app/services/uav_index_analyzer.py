from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.core.exceptions import AppException
from app.database.risk_fusion_repositories import RiskFusionRepository, risk_fusion_repository as default_risk_repository
from app.database.uav_repositories import UavRepository, uav_repository as default_uav_repository
from app.schemas.risk_fusion import UavIndexAnalysis, UavIndexAnalysisResponse
from app.schemas.uav import UavIndexResult


LEVEL_ORDER = {
    "normal": 0,
    "mild_abnormal": 1,
    "moderate_abnormal": 2,
    "severe_abnormal": 3,
}


class UAVIndexAnalyzer:
    def __init__(
        self,
        uav_repository: UavRepository | None = None,
        risk_repository: RiskFusionRepository | None = None,
    ) -> None:
        self.uav_repository = uav_repository or default_uav_repository
        self.risk_repository = risk_repository or default_risk_repository

    def analyze_uav_indices(self, uav_task_id: str) -> UavIndexAnalysisResponse:
        task = self.uav_repository.get_task(uav_task_id)
        if not task:
            raise AppException("UAV_TASK_NOT_FOUND", "UAV task not found", {"uav_task_id": uav_task_id})
        indices = self.uav_repository.list_indices(uav_task_id)
        if not indices:
            raise AppException("UAV_INDEX_NOT_FOUND", "UAV index results not found", {"uav_task_id": uav_task_id})

        analysis = [self._analyze_index(item) for item in indices]
        for item in analysis:
            self.risk_repository.save_uav_index_analysis(item)
        return self._build_response(uav_task_id, task.field_id, analysis, task.data_mode, task.is_mock)

    def get_index_analysis(self, uav_task_id: str) -> UavIndexAnalysisResponse:
        task = self.uav_repository.get_task(uav_task_id)
        if not task:
            raise AppException("UAV_TASK_NOT_FOUND", "UAV task not found", {"uav_task_id": uav_task_id})
        analysis = self.risk_repository.list_uav_index_analysis(uav_task_id)
        if not analysis:
            return self.analyze_uav_indices(uav_task_id)
        return self._build_response(uav_task_id, task.field_id, analysis, task.data_mode, task.is_mock)

    def calculate_zscore_anomaly(self, values: list[float], z_threshold: float = -1.5) -> dict:
        if not values:
            return {"mean": None, "std": None, "min": None, "max": None, "abnormal_ratio": 0.0}
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        std = variance**0.5
        if std <= 0:
            abnormal_count = 0
        else:
            abnormal_count = sum(1 for value in values if (value - mean) / std < z_threshold)
        return {
            "mean": round(mean, 4),
            "std": round(std, 4),
            "min": min(values),
            "max": max(values),
            "abnormal_ratio": round(abnormal_count / len(values), 4),
        }

    def calculate_uav_risk_score(self, analysis: list[UavIndexAnalysis]) -> tuple[int, str, list[str]]:
        if not analysis:
            return 0, "normal", []
        score = max(item.index_anomaly_score for item in analysis)
        abnormal_items = [item for item in analysis if item.abnormal_level != "normal"]
        if len({item.index_type for item in abnormal_items}) >= 2:
            score += 3
        max_ratio = max(item.abnormal_area_ratio or 0 for item in analysis)
        if max_ratio > 0.2:
            score += 5
        elif max_ratio > 0.1:
            score += 3
        score = min(30, int(round(score)))
        level = self._score_to_uav_level(score)
        reasons: list[str] = []
        for item in analysis:
            reasons.extend(item.main_reasons)
        if len({item.index_type for item in abnormal_items}) >= 2:
            reasons.append("Both NDVI and NDRE suggest local vegetation stress.")
        return score, level, list(dict.fromkeys(reasons))

    def _analyze_index(self, item: UavIndexResult) -> UavIndexAnalysis:
        mean = item.mean_value
        min_value = item.min_value
        max_value = item.max_value
        std = self._estimate_std(item)
        ratio = float(item.abnormal_area_ratio or 0)
        threshold = item.threshold_used if item.threshold_used is not None else (mean - 1.5 * std if mean else None)
        z_value = ((threshold - mean) / std) if threshold is not None and mean is not None and std > 0 else 0.0
        level = self._level_from_signal(z_value, ratio)
        score = self._score_from_level(level)
        reasons = self._index_reasons(item.index_type, level, ratio, z_value)
        return UavIndexAnalysis(
            analysis_id=f"uav_analysis_{uuid4().hex[:12]}",
            uav_task_id=item.uav_task_id,
            field_id=item.field_id,
            index_type=item.index_type,
            mean_value=mean,
            std_value=std,
            min_value=min_value,
            max_value=max_value,
            z_threshold=-1.5,
            abnormal_pixel_ratio=ratio,
            abnormal_area_ratio=ratio,
            index_anomaly_score=score,
            abnormal_level=level,
            main_reasons=reasons,
            data_mode=item.data_mode,
            is_mock=item.is_mock,
            created_at=self._now(),
        )

    def _estimate_std(self, item: UavIndexResult) -> float:
        if item.min_value is None or item.max_value is None:
            return 0.05
        spread = max(0.0, float(item.max_value) - float(item.min_value))
        return round(max(spread / 6.0, 0.01), 4)

    def _level_from_signal(self, z_value: float, ratio: float) -> str:
        if z_value <= -2.5 or ratio >= 0.25:
            return "severe_abnormal"
        if z_value <= -2.0 or ratio >= 0.15:
            return "moderate_abnormal"
        if z_value <= -1.5 or ratio >= 0.05:
            return "mild_abnormal"
        return "normal"

    def _score_from_level(self, level: str) -> int:
        return {
            "normal": 0,
            "mild_abnormal": 8,
            "moderate_abnormal": 15,
            "severe_abnormal": 22,
        }.get(level, 0)

    def _score_to_uav_level(self, score: int) -> str:
        if score >= 23:
            return "severe_abnormal"
        if score >= 15:
            return "moderate_abnormal"
        if score >= 8:
            return "mild_abnormal"
        return "normal"

    def _index_reasons(self, index_type: str, level: str, ratio: float, z_value: float) -> list[str]:
        if level == "normal":
            return [f"{index_type.upper()} has no obvious low-value anomaly in the current rule check."]
        reasons = [f"{index_type.upper()} low-value anomaly is {level}."]
        if ratio > 0:
            reasons.append(f"{index_type.upper()} abnormal area ratio is about {ratio:.0%}.")
        if z_value < -1.5:
            reasons.append(f"{index_type.upper()} threshold z-score is {z_value:.2f}.")
        return reasons

    def _build_response(
        self,
        uav_task_id: str,
        field_id: str | None,
        analysis: list[UavIndexAnalysis],
        data_mode: str,
        is_mock: bool,
    ) -> UavIndexAnalysisResponse:
        score, level, reasons = self.calculate_uav_risk_score(analysis)
        return UavIndexAnalysisResponse(
            uav_task_id=uav_task_id,
            field_id=field_id,
            analysis=analysis,
            uav_risk_score=score,
            uav_abnormal_level=level,
            main_reasons=reasons,
            data_mode=data_mode,
            is_mock=is_mock,
        )

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


uav_index_analyzer = UAVIndexAnalyzer()
