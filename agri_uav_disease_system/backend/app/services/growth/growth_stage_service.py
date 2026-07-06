from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.database.growth_stage_repositories import GrowthStageRepository
from app.schemas.growth_stage import GrowthStage, GrowthStageCreate
from app.services.growth.growth_stage_inferer import growth_stage_inferer


class GrowthStageService:
    def __init__(self, repository: GrowthStageRepository | None = None) -> None:
        self.repository = repository or GrowthStageRepository()

    def create(self, request: GrowthStageCreate) -> GrowthStage:
        now = self._now()
        inferred = request.inferred_growth_stage or growth_stage_inferer.infer(request.sowing_date, request.transplanting_date)
        stage = request.manual_growth_stage or request.growth_stage or inferred
        item = GrowthStage(
            growth_id=f"growth_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}",
            updated_at=now,
            created_at=now,
            **request.model_dump(exclude={"inferred_growth_stage", "growth_stage"}),
            inferred_growth_stage=inferred,
            growth_stage=stage,
        )
        self.repository.save(item)
        return item

    def list_by_plot(self, plot_id: str) -> list[GrowthStage]:
        return self.repository.list_by_plot(plot_id)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


growth_stage_service = GrowthStageService()
