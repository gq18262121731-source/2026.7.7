from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from app.schemas.detection_result import DetectionResult
from app.services.weather.weather_service import weather_service


AMAP_SUCHENG_ADCODE = "321302"
QWEATHER_SUQIAN_LOCATION = "118.275,33.963"


class ReportWeatherService:
    def snapshot(self, include_weather: bool, plot_id: str | None, record: DetectionResult | None) -> dict[str, Any]:
        if not include_weather:
            return {
                "available": False,
                "message": "未启用天气快照",
                "source": "unavailable",
                "provider_name": "暂不可用",
                "fallback_chain": ["weather_disabled"],
            }

        fallback_chain: list[str] = []

        qweather = self._qweather_live_weather()
        if qweather.get("available"):
            qweather["fallback_chain"] = ["qweather_success"]
            return qweather
        fallback_chain.append("qweather_failed")

        amap = self._amap_live_weather()
        if amap.get("available"):
            amap["fallback_chain"] = [*fallback_chain, "amap_success"]
            return amap
        fallback_chain.append("amap_failed")

        local = self._local_weather(plot_id, record)
        if local.get("available"):
            local["fallback_chain"] = [*fallback_chain, "local_success"]
            return local
        fallback_chain.append("local_failed")

        return {
            "available": False,
            "source": "unavailable",
            "provider_name": "暂不可用",
            "message": "天气数据暂不可用，不影响本次检测记录分析。",
            "fallback_chain": [*fallback_chain, "unavailable"],
            "fallback_detail": {"qweather": qweather, "amap": amap, "local": local},
        }

    def _qweather_live_weather(self) -> dict[str, Any]:
        key = os.getenv("QWEATHER_API_KEY") or os.getenv("VITE_QWEATHER_API_KEY")
        host = os.getenv("QWEATHER_API_HOST") or os.getenv("VITE_QWEATHER_API_HOST")
        if not key or not host:
            return {
                "available": False,
                "source": "qweather",
                "provider_name": "和风天气",
                "message": "未配置和风天气 API Key 或 Host",
            }
        location = os.getenv("QWEATHER_LOCATION") or os.getenv("VITE_QWEATHER_LOCATION") or QWEATHER_SUQIAN_LOCATION
        endpoint = host.rstrip("/")
        if not endpoint.endswith("/v7/weather/now"):
            endpoint = f"{endpoint}/v7/weather/now"
        query = urlencode({"key": key, "location": location, "lang": "zh"})
        try:
            with urlopen(f"{endpoint}?{query}", timeout=4) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return {
                "available": False,
                "source": "qweather",
                "provider_name": "和风天气",
                "message": "和风天气请求失败",
                "error": type(exc).__name__,
            }
        now = payload.get("now") or {}
        if str(payload.get("code")) != "200" or not now:
            return {
                "available": False,
                "source": "qweather",
                "provider_name": "和风天气",
                "message": str(payload.get("message") or payload.get("code") or "和风天气无实时数据"),
                "raw_code": payload.get("code"),
            }
        return {
            "available": True,
            "source": "qweather",
            "provider_name": "和风天气",
            "city": "宿迁市",
            "district": "宿城区",
            "temperature": f"{now.get('temp')} C" if now.get("temp") not in {None, ""} else "暂无",
            "humidity": f"{now.get('humidity')}%" if now.get("humidity") not in {None, ""} else "暂无",
            "weather": now.get("text") or "暂无",
            "wind_direction": now.get("windDir") or "暂无",
            "wind_power": now.get("windScale") or now.get("windSpeed") or "暂无",
            "rainfall_mm": None,
            "report_time": now.get("obsTime") or payload.get("updateTime") or "",
            "location": location,
        }

    def _amap_live_weather(self) -> dict[str, Any]:
        key = os.getenv("AMAP_WEATHER_KEY") or os.getenv("GAODE_WEATHER_KEY") or os.getenv("AMAP_WEB_SERVICE_KEY")
        if not key:
            return {
                "available": False,
                "source": "amap",
                "provider_name": "高德地图开放平台",
                "message": "未配置高德天气 Web 服务 Key",
            }
        query = urlencode({"key": key, "city": AMAP_SUCHENG_ADCODE, "extensions": "base", "output": "JSON"})
        url = f"https://restapi.amap.com/v3/weather/weatherInfo?{query}"
        try:
            with urlopen(url, timeout=4) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return {
                "available": False,
                "source": "amap",
                "provider_name": "高德地图开放平台",
                "message": "高德天气请求失败",
                "error": type(exc).__name__,
            }
        lives = payload.get("lives") or []
        if payload.get("status") != "1" or not lives:
            return {
                "available": False,
                "source": "amap",
                "provider_name": "高德地图开放平台",
                "message": str(payload.get("info") or "高德天气无实时数据"),
                "raw_status": payload.get("status"),
                "infocode": payload.get("infocode"),
            }
        live = lives[0]
        return {
            "available": True,
            "source": "amap",
            "provider_name": "高德地图开放平台",
            "city": live.get("city") or "宿迁市",
            "district": "宿城区",
            "temperature": f"{live.get('temperature')} C" if live.get("temperature") not in {None, ""} else "暂无",
            "humidity": f"{live.get('humidity')}%" if live.get("humidity") not in {None, ""} else "暂无",
            "weather": live.get("weather") or "暂无",
            "wind_direction": live.get("winddirection") or "暂无",
            "wind_power": live.get("windpower") or "暂无",
            "rainfall_mm": None,
            "report_time": live.get("reporttime") or "",
            "adcode": live.get("adcode") or AMAP_SUCHENG_ADCODE,
        }

    def _local_weather(self, plot_id: str | None, record: DetectionResult | None) -> dict[str, Any]:
        try:
            observations = weather_service.list_observations(plot_id=plot_id, limit=1)
        except Exception as exc:
            return {
                "available": False,
                "source": "local_weather_observations",
                "provider_name": "本地天气观测",
                "message": "本地天气观测读取失败",
                "error": type(exc).__name__,
            }
        if not observations:
            return {
                "available": False,
                "source": "local_weather_observations",
                "provider_name": "本地天气观测",
                "message": "本地天气观测为空",
            }
        latest = observations[0]
        avg_temp = self._avg(latest.temperature_max, latest.temperature_min)
        return {
            "available": True,
            "source": "local_weather_observations",
            "provider_name": "本地天气观测",
            "city": "宿迁市",
            "district": latest.region_name or (record.region_name if record else ""),
            "temperature": f"{avg_temp:.1f} C" if avg_temp is not None else "暂无",
            "humidity": f"{latest.humidity_avg:.0f}%" if latest.humidity_avg is not None else "暂无",
            "weather": latest.weather_text or "暂无",
            "wind_direction": "暂无",
            "wind_power": f"{latest.wind_speed:.1f} m/s" if latest.wind_speed is not None else "暂无",
            "rainfall_mm": latest.rainfall_mm,
            "report_time": latest.observed_date,
        }

    def _avg(self, a: float | None, b: float | None) -> float | None:
        values = [item for item in (a, b) if item is not None]
        return sum(values) / len(values) if values else None


report_weather_service = ReportWeatherService()
