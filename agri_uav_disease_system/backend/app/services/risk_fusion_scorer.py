from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.core.exceptions import AppException
from app.database.farm_operation_repositories import FarmOperationRepository
from app.database.field_repositories import FieldRepository, field_repository as default_field_repository
from app.database.repositories import DetectionRecordRepository
from app.database.risk_fusion_repositories import RiskFusionRepository, risk_fusion_repository as default_risk_repository
from app.database.uav_repositories import UavRepository, uav_repository as default_uav_repository
from app.database.weather_repositories import WeatherRepository
from app.schemas.detection_result import DetectionResult
from app.schemas.risk_fusion import (
    RiskFeatureSnapshot,
    RiskFusionEvaluateRequest,
    RiskFusionResponse,
)
from app.services.storage.result_store import result_store
from app.services.uav_index_analyzer import uav_index_analyzer


DISEASE_BASE_WEIGHTS = {
    "healthy": 0,
    "brown_spot": 12,
    "false_smut": 15,
    "bacterial_blight": 18,
    "bacterial_leaf_blight": 18,
    "sheath_blight": 20,
    "rice_blast": 22,
    "unknown_disease": 10,
    "planthopper_damage": 18,
    "leaf_folder_damage": 16,
    "stem_borer_damage": 18,
    "稻瘟病": 22,
    "纹枯病": 20,
    "稻曲病": 15,
    "细菌性条斑病": 18,
    "稻飞虱": 18,
    "稻纵卷叶螟": 16,
}

SEVERITY_BONUS = {
    "mild": 2,
    "light": 2,
    "medium": 5,
    "moderate": 5,
    "severe": 8,
    "轻度": 2,
    "中度": 5,
    "重度": 8,
}

GROWTH_STAGE_SCORES = {
    "seedling": 3,
    "tillering": 6,
    "jointing_booting": 8,
    "heading_flowering": 8,
    "filling": 6,
    "maturity": 4,
    "苗期": 3,
    "分蘖期": 6,
    "拔节孕穗期": 8,
    "拔节期": 8,
    "孕穗期": 8,
    "抽穗扬花期": 8,
    "灌浆期": 6,
    "成熟期": 4,
}


class RiskFusionScorer:
    def __init__(
        self,
        risk_repository: RiskFusionRepository | None = None,
        uav_repository: UavRepository | None = None,
        field_repository: FieldRepository | None = None,
        weather_repository: WeatherRepository | None = None,
        operation_repository: FarmOperationRepository | None = None,
        detection_repository: DetectionRecordRepository | None = None,
    ) -> None:
        self.risk_repository = risk_repository or default_risk_repository
        self.uav_repository = uav_repository or default_uav_repository
        self.field_repository = field_repository or default_field_repository
        self.weather_repository = weather_repository or WeatherRepository()
        self.operation_repository = operation_repository or FarmOperationRepository()
        self.detection_repository = detection_repository or DetectionRecordRepository()

    def evaluate(self, request: RiskFusionEvaluateRequest) -> RiskFusionResponse:
        field = self.field_repository.get(request.field_id)
        if not field:
            raise AppException("FIELD_NOT_FOUND", "Field not found", {"field_id": request.field_id})
        features = self.build_risk_features(
            field_id=request.field_id,
            uav_task_id=request.uav_task_id,
            abnormal_region_id=request.abnormal_region_id,
            phone_image_id=request.phone_image_id,
            include_weather=request.include_weather,
            include_history=request.include_history,
            include_treatment=request.include_treatment,
        )
        result, snapshot = self.calculate_total_risk(features)
        self.risk_repository.save_feature_snapshot(snapshot)
        self.risk_repository.save_fusion_prediction(result, snapshot)
        snapshot.prediction_id = result.prediction_id
        self.risk_repository.save_feature_snapshot(snapshot)
        return result

    def get(self, prediction_id: str) -> RiskFusionResponse:
        item = self.risk_repository.get_fusion_prediction(prediction_id)
        if not item:
            raise AppException("RISK_FUSION_NOT_FOUND", "Risk fusion result not found", {"prediction_id": prediction_id})
        return item

    def list_for_field(self, field_id: str) -> list[RiskFusionResponse]:
        return self.risk_repository.list_fusion_predictions(field_id=field_id, limit=100)

    def build_risk_features(
        self,
        field_id: str,
        uav_task_id: str | None = None,
        abnormal_region_id: str | None = None,
        phone_image_id: str | None = None,
        include_weather: bool = True,
        include_history: bool = True,
        include_treatment: bool = True,
    ) -> dict:
        task = self.uav_repository.get_task(uav_task_id) if uav_task_id else None
        analyses = uav_index_analyzer.get_index_analysis(uav_task_id).analysis if uav_task_id else []
        uav_score, uav_level, uav_reasons = uav_index_analyzer.calculate_uav_risk_score(analyses)

        regions = self.uav_repository.list_regions(uav_task_id=uav_task_id, field_id=field_id)
        region = self._select_region(regions, abnormal_region_id)
        phone_record = self._phone_record(region, phone_image_id)
        weather = self.weather_repository.recent_for_plot(field_id, limit=7) if include_weather else []
        operations = self.operation_repository.recent_for_plot(field_id, limit=20) if include_treatment else []
        field = self.field_repository.get(field_id)

        disease_type = (
            phone_record.summary.main_disease
            if phone_record and phone_record.summary.main_disease
            else (region.confirmed_disease_type if region else None)
        )
        growth_stage = (
            field.current_growth_stage
            if field and field.current_growth_stage
            else (task.growth_stage if task and task.growth_stage else None)
        )
        return {
            "field_id": field_id,
            "uav_task_id": uav_task_id,
            "task": task,
            "uav_index_analysis": analyses,
            "uav_risk_score": uav_score,
            "uav_abnormal_level": uav_level,
            "uav_reasons": uav_reasons,
            "abnormal_region_id": region.region_id if region else abnormal_region_id,
            "region": region,
            "phone_image_id": phone_record.image_id if phone_record else phone_image_id,
            "phone_record": phone_record,
            "disease_type": disease_type,
            "phone_confidence": phone_record.summary.max_confidence if phone_record else (region.confirm_confidence if region else None),
            "severity_level": phone_record.summary.severity if phone_record else None,
            "weather": weather,
            "growth_stage": growth_stage,
            "history_records": self._history_records(field_id) if include_history else [],
            "operations": operations,
            "include_weather": include_weather,
            "include_history": include_history,
            "include_treatment": include_treatment,
        }

    def score_uav_risk(self, features: dict) -> int:
        return int(features.get("uav_risk_score") or 0)

    def score_image_risk(self, features: dict) -> int:
        disease = str(features.get("disease_type") or "unknown_disease")
        confidence = float(features.get("phone_confidence") or 0)
        base = DISEASE_BASE_WEIGHTS.get(disease, DISEASE_BASE_WEIGHTS.get(disease.lower(), 10 if disease else 0))
        severity = str(features.get("severity_level") or "").lower()
        score = base * confidence + SEVERITY_BONUS.get(severity, 0)
        return min(30, int(round(score)))

    def score_environment_risk(self, features: dict) -> int:
        weather = features.get("weather") or []
        if not weather:
            return 0
        humidity_values = [item.humidity_avg for item in weather if item.humidity_avg is not None]
        humidity_avg = sum(humidity_values) / len(humidity_values) if humidity_values else None
        rainfall_3d = sum(item.rainfall_mm or 0 for item in weather[:3])
        rainfall_7d = sum(item.rainfall_mm or 0 for item in weather[:7])
        continuous_rain_days = self._continuous_rain_days(weather)
        score = 0
        if humidity_avg is not None and humidity_avg > 90:
            score += 8
        elif humidity_avg is not None and humidity_avg > 85:
            score += 6
        if continuous_rain_days >= 3:
            score += 7
        elif continuous_rain_days >= 2:
            score += 4
        if rainfall_7d >= 30:
            score += 4
        temperature_values = [
            ((item.temperature_max + item.temperature_min) / 2)
            for item in weather
            if item.temperature_max is not None and item.temperature_min is not None
        ]
        temperature_avg = sum(temperature_values) / len(temperature_values) if temperature_values else None
        if humidity_avg is not None and temperature_avg is not None and humidity_avg > 85 and temperature_avg >= 25:
            score += 5
        features["environment_metrics"] = {
            "humidity_avg": round(humidity_avg, 2) if humidity_avg is not None else None,
            "rainfall_3d": round(rainfall_3d, 2),
            "rainfall_7d": round(rainfall_7d, 2),
            "continuous_rain_days": continuous_rain_days,
        }
        return min(20, int(score))

    def score_growth_stage_risk(self, features: dict) -> int:
        stage = str(features.get("growth_stage") or "")
        base = GROWTH_STAGE_SCORES.get(stage, GROWTH_STAGE_SCORES.get(stage.lower(), 3 if stage else 0))
        disease = str(features.get("disease_type") or "").lower()
        bonus = 0
        if disease in {"rice_blast", "稻瘟病"} and any(key in stage for key in ["分蘖", "抽穗", "tillering", "heading"]):
            bonus = 2
        if disease in {"sheath_blight", "纹枯病"} and any(key in stage for key in ["分蘖", "拔节", "tillering", "jointing"]):
            bonus = 2
        if disease in {"false_smut", "稻曲病"} and any(key in stage for key in ["抽穗", "扬花", "heading", "flowering"]):
            bonus = 2
        return min(10, int(base + bonus))

    def score_history_risk(self, features: dict) -> int:
        records = features.get("history_records") or []
        disease = features.get("disease_type")
        if not records:
            return 0
        same = [item for item in records if disease and item.summary.main_disease == disease]
        if len(same) >= 2:
            return 10
        if same:
            return 8
        return 4

    def score_treatment_risk(self, features: dict) -> int:
        operations = features.get("operations") or []
        if not operations:
            return 0
        latest = operations[0]
        text = " ".join(
            str(value or "")
            for value in [latest.operation_type, latest.note, latest.target_disease, latest.material_name]
        ).lower()
        features["recent_treatment"] = latest.operation_type
        if any(key in text for key in ["worse", "加重", "恶化"]):
            features["treatment_effect"] = "worse"
            return 8
        if any(key in text for key in ["improve", "effective", "好转", "有效", "复查"]):
            features["treatment_effect"] = "improved"
            return -8
        if any(key in text for key in ["treatment", "spray", "control", "治理", "防治", "用药", "管护", "排水"]):
            features["treatment_effect"] = "treated_no_clear_change"
            return -3
        return 0

    def calculate_total_risk(self, features: dict) -> tuple[RiskFusionResponse, RiskFeatureSnapshot]:
        factor_scores = {
            "uav": self.score_uav_risk(features),
            "image": self.score_image_risk(features),
            "environment": self.score_environment_risk(features),
            "growth_stage": self.score_growth_stage_risk(features),
            "history": self.score_history_risk(features),
            "treatment": self.score_treatment_risk(features),
        }
        total = max(0, min(100, sum(factor_scores.values())))
        level = self._risk_level(total)
        main_factors = self._main_factors(features, factor_scores)
        now = self._now()
        prediction_id = f"RISK_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        snapshot = self._snapshot(features, factor_scores, total, level, main_factors, now)
        snapshot.prediction_id = prediction_id
        response = RiskFusionResponse(
            prediction_id=prediction_id,
            field_id=features["field_id"],
            uav_task_id=features.get("uav_task_id"),
            abnormal_region_id=features.get("abnormal_region_id"),
            phone_image_id=features.get("phone_image_id"),
            disease_type=features.get("disease_type"),
            total_risk_score=total,
            risk_level=level,
            factor_scores=factor_scores,
            main_factors=main_factors,
            feature_snapshot_id=snapshot.feature_id,
            created_at=now,
        )
        return response, snapshot

    def _snapshot(
        self,
        features: dict,
        factor_scores: dict[str, int],
        total: int,
        level: str,
        main_factors: list[str],
        now: str,
    ) -> RiskFeatureSnapshot:
        index_map = {item.index_type.lower(): item for item in features.get("uav_index_analysis") or []}
        ndvi = index_map.get("ndvi")
        ndre = index_map.get("ndre")
        metrics = features.get("environment_metrics") or {}
        history_records = features.get("history_records") or []
        disease = features.get("disease_type")
        return RiskFeatureSnapshot(
            feature_id=f"risk_feature_{uuid4().hex[:12]}",
            field_id=features["field_id"],
            uav_task_id=features.get("uav_task_id"),
            abnormal_region_id=features.get("abnormal_region_id"),
            phone_image_id=features.get("phone_image_id"),
            disease_type=disease,
            ndvi_mean=ndvi.mean_value if ndvi else None,
            ndvi_std=ndvi.std_value if ndvi else None,
            ndvi_min=ndvi.min_value if ndvi else None,
            ndvi_max=ndvi.max_value if ndvi else None,
            ndre_mean=ndre.mean_value if ndre else None,
            ndre_std=ndre.std_value if ndre else None,
            ndre_min=ndre.min_value if ndre else None,
            ndre_max=ndre.max_value if ndre else None,
            abnormal_area_ratio=self._max_abnormal_ratio(features),
            uav_risk_score=factor_scores["uav"],
            phone_confidence=features.get("phone_confidence"),
            image_risk_score=factor_scores["image"],
            severity_level=features.get("severity_level"),
            humidity_avg=metrics.get("humidity_avg"),
            rainfall_3d=metrics.get("rainfall_3d"),
            rainfall_7d=metrics.get("rainfall_7d"),
            continuous_rain_days=metrics.get("continuous_rain_days") or 0,
            environment_risk_score=factor_scores["environment"],
            growth_stage=features.get("growth_stage"),
            growth_stage_risk_score=factor_scores["growth_stage"],
            historical_same_disease=any(item.summary.main_disease == disease for item in history_records if disease),
            history_risk_score=factor_scores["history"],
            recent_treatment=features.get("recent_treatment"),
            treatment_effect=features.get("treatment_effect"),
            treatment_risk_score=factor_scores["treatment"],
            factor_scores=factor_scores,
            main_factors=main_factors,
            total_risk_score=total,
            risk_level=level,
            feature_payload={
                "uav_abnormal_level": features.get("uav_abnormal_level"),
                "include_weather": features.get("include_weather"),
                "include_history": features.get("include_history"),
                "include_treatment": features.get("include_treatment"),
            },
            created_at=now,
        )

    def _main_factors(self, features: dict, scores: dict[str, int]) -> list[str]:
        factors: list[str] = []
        if scores["uav"] > 0:
            factors.append("UAV index analysis indicates local vegetation stress.")
        if scores["image"] > 0:
            disease = features.get("disease_type") or "unknown disease"
            confidence = features.get("phone_confidence")
            suffix = f" with confidence {confidence:.2f}" if confidence is not None else ""
            factors.append(f"Phone follow-up model suggests {disease}{suffix}.")
        if scores["environment"] > 0:
            factors.append("Recent weather humidity or rainfall raises disease pressure.")
        if scores["growth_stage"] >= 6:
            factors.append("Current growth stage is relatively sensitive.")
        if scores["history"] > 0:
            factors.append("Historical disease records exist for this field.")
        if scores["treatment"] < 0:
            factors.append("Recent treatment or follow-up record lowers the rule score.")
        elif scores["treatment"] > 0:
            factors.append("Recent treatment feedback suggests the issue may be worsening.")
        return factors or ["No dominant high-risk factor was found by the current rule set."]

    def _select_region(self, regions: list, abnormal_region_id: str | None):
        if abnormal_region_id:
            for region in regions:
                if region.region_id == abnormal_region_id:
                    return region
            return self.uav_repository.get_region(abnormal_region_id)
        if not regions:
            return None
        return sorted(regions, key=lambda item: item.abnormal_area_ratio or 0, reverse=True)[0]

    def _phone_record(self, region, phone_image_id: str | None) -> DetectionResult | None:
        if region and region.linked_record_id:
            record = result_store.get(region.linked_record_id)
            if record:
                return record
        if phone_image_id:
            return self._record_by_image_id(phone_image_id)
        return None

    def _record_by_image_id(self, image_id: str) -> DetectionResult | None:
        try:
            from app.database.database import get_connection

            with get_connection() as conn:
                row = conn.execute("SELECT record_id FROM detection_records WHERE image_id = ?", (image_id,)).fetchone()
            return result_store.get(row["record_id"]) if row else None
        except Exception:
            return None

    def _history_records(self, field_id: str) -> list[DetectionResult]:
        try:
            from app.database.database import get_connection

            with get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT record_id FROM detection_records
                    WHERE field_id = ? OR plot_id = ?
                    ORDER BY timestamp DESC LIMIT 100
                    """,
                    (field_id, field_id),
                ).fetchall()
            return [record for row in rows if (record := result_store.get(row["record_id"]))]
        except Exception:
            return []

    def _continuous_rain_days(self, weather: list) -> int:
        count = 0
        for item in weather:
            text = str(item.weather_text or "").lower()
            if (item.rainfall_mm or 0) > 0 or "rain" in text or "雨" in text:
                count += 1
            else:
                break
        return count

    def _max_abnormal_ratio(self, features: dict) -> float | None:
        ratios = [item.abnormal_area_ratio or 0 for item in features.get("uav_index_analysis") or []]
        region = features.get("region")
        if region:
            ratios.append(region.abnormal_area_ratio or 0)
        return max(ratios) if ratios else None

    def _risk_level(self, score: int) -> str:
        if score >= 70:
            return "high"
        if score >= 40:
            return "medium"
        return "low"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


risk_fusion_scorer = RiskFusionScorer()
