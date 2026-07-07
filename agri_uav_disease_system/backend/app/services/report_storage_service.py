from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.schemas.farm_analysis_report import FarmAnalysisReportMetadata


class ReportStorageService:
    def __init__(self) -> None:
        self.report_dir = settings.static_dir / "reports" / "generated"
        self.metadata_path = self.report_dir / "metadata.json"

    def ensure_dirs(self) -> None:
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def save(self, metadata: FarmAnalysisReportMetadata) -> None:
        self.ensure_dirs()
        items = self._read_all()
        items = [item for item in items if item.get("report_id") != metadata.report_id]
        items.insert(0, metadata.model_dump())
        self.metadata_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def list(self, plot_id: str | None = None) -> list[FarmAnalysisReportMetadata]:
        items = self._read_all()
        if plot_id:
            items = [item for item in items if item.get("plot_id") == plot_id]
        return [FarmAnalysisReportMetadata(**item) for item in items]

    def get(self, report_id: str) -> FarmAnalysisReportMetadata | None:
        for item in self._read_all():
            if item.get("report_id") == report_id:
                return FarmAnalysisReportMetadata(**item)
        return None

    def pdf_path(self, report_id: str) -> Path | None:
        metadata = self.get(report_id)
        if not metadata:
            return None
        return Path(metadata.pdf_path)

    def _read_all(self) -> list[dict]:
        if not self.metadata_path.exists():
            return []
        try:
            payload = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return payload if isinstance(payload, list) else []


report_storage_service = ReportStorageService()
