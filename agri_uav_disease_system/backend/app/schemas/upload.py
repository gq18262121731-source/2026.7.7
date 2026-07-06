from __future__ import annotations

from pydantic import BaseModel

from app.core.config import settings
from app.core.constants import ALLOWED_SOURCE_TYPES, SOURCE_UNKNOWN


class DetectImageMetadata(BaseModel):
    field_id: str | None = None
    plot_id: str | None = None
    plot_name: str | None = None
    region_name: str | None = None
    lng: float | None = None
    lat: float | None = None
    source: str | None = None
    source_type: str | None = None
    model_hint: str | None = None
    target_type: str | None = None
    model_stage_hint: str | None = None
    uav_task_id: str | None = None
    abnormal_region_id: str | None = None

    def normalized_source_type(self) -> str:
        candidate = self.source_type or self.source or settings.default_source_type
        return candidate if candidate in ALLOWED_SOURCE_TYPES else SOURCE_UNKNOWN
