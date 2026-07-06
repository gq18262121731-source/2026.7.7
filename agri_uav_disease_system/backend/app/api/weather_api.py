from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.weather import WeatherObservation, WeatherObservationCreate, WeatherObservationListResponse
from app.services.weather.weather_service import weather_service

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.post("/observations", response_model=WeatherObservation)
async def create_weather_observation(request: WeatherObservationCreate) -> WeatherObservation:
    return weather_service.create(request)


@router.get("/observations", response_model=WeatherObservationListResponse)
async def list_weather_observations(
    plot_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> WeatherObservationListResponse:
    items = weather_service.list_observations(plot_id=plot_id, limit=limit)
    return WeatherObservationListResponse(items=items, total=len(items))
