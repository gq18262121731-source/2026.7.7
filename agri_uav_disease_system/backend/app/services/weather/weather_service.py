from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.database.weather_repositories import WeatherRepository
from app.schemas.weather import WeatherObservation, WeatherObservationCreate


class WeatherService:
    def __init__(self, repository: WeatherRepository | None = None) -> None:
        self.repository = repository or WeatherRepository()

    def create(self, request: WeatherObservationCreate) -> WeatherObservation:
        now = self._now()
        item = WeatherObservation(
            weather_id=f"weather_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}",
            created_at=now,
            **request.model_dump(),
        )
        self.repository.save(item)
        return item

    def list_observations(self, plot_id: str | None = None, limit: int = 100) -> list[WeatherObservation]:
        return self.repository.list_observations(plot_id=plot_id, limit=limit)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


weather_service = WeatherService()
