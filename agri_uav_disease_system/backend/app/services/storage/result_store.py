from __future__ import annotations

from app.database.repositories import DetectionRecordRepository
from app.schemas.detection_result import DetectionResult


class ResultStore:
    def __init__(self, repository: DetectionRecordRepository | None = None) -> None:
        self.repository = repository or DetectionRecordRepository()

    def save(self, result: DetectionResult) -> None:
        self.repository.save(result)

    def get(self, record_id: str) -> DetectionResult | None:
        return self.repository.get_by_record_id(record_id)

    def list_records(
        self,
        plot_id: str | None = None,
        risk_level: str | None = None,
        severity: str | None = None,
        disease: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = "created_at_desc",
        limit: int | None = None,
    ) -> list[DetectionResult]:
        return self.repository.list_records(
            plot_id=plot_id,
            risk_level=risk_level,
            severity=severity,
            disease=disease,
            start_time=start_time,
            end_time=end_time,
            page=page,
            page_size=page_size,
            sort=sort,
            limit=limit,
        )

    def count_records(
        self,
        plot_id: str | None = None,
        risk_level: str | None = None,
        severity: str | None = None,
        disease: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> int:
        return self.repository.count_records(
            plot_id=plot_id,
            risk_level=risk_level,
            severity=severity,
            disease=disease,
            start_time=start_time,
            end_time=end_time,
        )


result_store = ResultStore()
