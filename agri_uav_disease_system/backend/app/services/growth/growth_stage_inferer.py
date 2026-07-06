from __future__ import annotations

from datetime import date, datetime, timezone


class GrowthStageInferer:
    def infer(self, sowing_date: str | None, transplanting_date: str | None, today: date | None = None) -> str | None:
        source = transplanting_date or sowing_date
        if not source:
            return None
        try:
            start = date.fromisoformat(source[:10])
        except ValueError:
            return None
        days = ((today or datetime.now(timezone.utc).date()) - start).days
        if days < 0:
            return None
        if days <= 20:
            return "苗期"
        if days <= 45:
            return "分蘖期"
        if days <= 70:
            return "拔节孕穗期"
        if days <= 95:
            return "抽穗扬花期"
        return "灌浆成熟期"


growth_stage_inferer = GrowthStageInferer()
