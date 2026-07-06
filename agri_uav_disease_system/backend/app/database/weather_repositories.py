from __future__ import annotations

import sqlite3

from app.core.constants import ERROR_DATABASE
from app.core.exceptions import AppException
from app.database.database import get_connection
from app.schemas.weather import WeatherObservation


class WeatherRepository:
    def save(self, item: WeatherObservation) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO weather_observations (
                        weather_id, plot_id, region_name, observed_date,
                        temperature_max, temperature_min, humidity_avg, rainfall_mm,
                        wind_speed, sunshine_hours, weather_text, data_source, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.weather_id,
                        item.plot_id,
                        item.region_name,
                        item.observed_date,
                        item.temperature_max,
                        item.temperature_min,
                        item.humidity_avg,
                        item.rainfall_mm,
                        item.wind_speed,
                        item.sunshine_hours,
                        item.weather_text,
                        item.data_source,
                        item.created_at,
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "天气记录保存失败", {"reason": str(exc)}) from exc

    def list_observations(self, plot_id: str | None = None, limit: int = 100) -> list[WeatherObservation]:
        clauses: list[str] = []
        params: list[object] = []
        if plot_id:
            clauses.append("plot_id = ?")
            params.append(plot_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    f"SELECT * FROM weather_observations {where_sql} ORDER BY observed_date DESC, created_at DESC LIMIT ?",
                    [*params, limit],
                ).fetchall()
            return [self._row_to_item(row) for row in rows]
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "天气记录查询失败", {"reason": str(exc)}) from exc

    def recent_for_plot(self, plot_id: str, limit: int = 7) -> list[WeatherObservation]:
        return self.list_observations(plot_id=plot_id, limit=limit)

    def _row_to_item(self, row: sqlite3.Row) -> WeatherObservation:
        return WeatherObservation(**dict(row))
