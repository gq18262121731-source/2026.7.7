from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.database.farm_operation_repositories import FarmOperationRepository
from app.schemas.farm_operation import FarmOperation, FarmOperationCreate


class FarmOperationService:
    def __init__(self, repository: FarmOperationRepository | None = None) -> None:
        self.repository = repository or FarmOperationRepository()

    def create(self, request: FarmOperationCreate) -> FarmOperation:
        now = self._now()
        item = FarmOperation(
            operation_id=f"op_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}",
            created_at=now,
            **request.model_dump(),
        )
        self.repository.save(item)
        return item

    def list_operations(self, plot_id: str | None = None, limit: int = 100) -> list[FarmOperation]:
        return self.repository.list_operations(plot_id=plot_id, limit=limit)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


farm_operation_service = FarmOperationService()
