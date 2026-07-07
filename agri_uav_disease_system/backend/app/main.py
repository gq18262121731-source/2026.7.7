from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    agent,
    alerts_api,
    batch_task_api,
    dashboard_api,
    detection_api,
    experimental_uav_blb_segmentation_api,
    farm_analysis_report_api,
    field_api,
    farm_operation_api,
    growth_stage_api,
    inspection_report_api,
    mobile_api,
    prediction_api,
    reports,
    records_api,
    risk_fusion_api,
    status_api,
    upload_api,
    uav_api,
    weather_api,
    knowledge,
    ws_api,
)
from app.core.config import settings
from app.core.constants import ERROR_INTERNAL
from app.core.exceptions import AppException
from app.core.logger import logger, setup_logging
from app.database.database import init_db
from app.services.storage.file_storage import file_storage_service
from app.services.report_storage_service import report_storage_service


def create_app() -> FastAPI:
    setup_logging()
    file_storage_service.ensure_dirs()
    report_storage_service.ensure_dirs()
    init_db()

    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_allow_origin_regex,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )
    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

    app.include_router(status_api.router)
    app.include_router(detection_api.router)
    app.include_router(experimental_uav_blb_segmentation_api.router)
    app.include_router(field_api.router)
    app.include_router(uav_api.router)
    app.include_router(batch_task_api.router)
    app.include_router(alerts_api.router)
    app.include_router(upload_api.router)
    app.include_router(records_api.router)
    app.include_router(dashboard_api.router)
    app.include_router(mobile_api.router)
    app.include_router(prediction_api.router)
    app.include_router(farm_analysis_report_api.router)
    app.include_router(reports.router)
    app.include_router(risk_fusion_api.router)
    app.include_router(weather_api.router)
    app.include_router(growth_stage_api.router)
    app.include_router(farm_operation_api.router)
    app.include_router(inspection_report_api.router)
    app.include_router(knowledge.router)
    app.include_router(agent.router)
    app.include_router(ws_api.router)

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error_code": exc.error_code,
                "message": exc.message,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "message": "\u8bf7\u6c42\u53c2\u6570\u6821\u9a8c\u5931\u8d25",
                "detail": {"errors": jsonable_encoder(exc.errors())},
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled request error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error_code": ERROR_INTERNAL,
                "message": "\u670d\u52a1\u5185\u90e8\u9519\u8bef",
                "detail": {},
            },
        )

    return app


app = create_app()
