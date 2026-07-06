from __future__ import annotations

from pydantic import BaseModel


class WeatherObservationCreate(BaseModel):
    plot_id: str | None = None
    region_name: str | None = None
    observed_date: str
    temperature_max: float | None = None
    temperature_min: float | None = None
    humidity_avg: float | None = None
    rainfall_mm: float | None = None
    wind_speed: float | None = None
    sunshine_hours: float | None = None
    weather_text: str | None = None
    data_source: str = "manual"


class WeatherObservation(WeatherObservationCreate):
    weather_id: str
    created_at: str


class WeatherObservationListResponse(BaseModel):
    items: list[WeatherObservation]
    total: int
