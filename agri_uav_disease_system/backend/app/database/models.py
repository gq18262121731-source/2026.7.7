from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DetectionRecordRow:
    record_id: str
    image_id: str
    plot_id: str | None
    plot_name: str | None
    region_name: str
    timestamp: str
    image_url: str
    result_image_url: str
    image_width: int
    image_height: int
    lng: float | None
    lat: float | None
    detections_json: str
    severity: str
    risk_level: str
    main_disease: str | None
    suggestion_json: str
    created_at: str
