from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw

from app.core.config import settings
from app.core.constants import DEFAULT_REGION_NAME
from app.database.database import get_connection, init_db
from app.schemas.detection_result import DetectionResult
from app.services.alert_service import alert_service
from app.services.storage.result_store import result_store


DEMO_PREFIX = "demo_stage5_"
DISEASES = ["稻瘟病", "纹枯病", "稻飞虱", "稻曲病"]
SEVERITY_BY_RISK = {
    "normal": "无病",
    "low": "轻度",
    "medium": "中度",
    "high": "重度",
}


def _timestamp(offset_minutes: int = 0) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(minutes=offset_minutes)
    ).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _ensure_demo_image(path: Path, label: str, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (640, 420), color=color)
    draw = ImageDraw.Draw(image)
    draw.rectangle([40, 40, 600, 360], outline=(255, 255, 255), width=4)
    draw.text((58, 58), label, fill=(255, 255, 255))
    image.save(path, format="JPEG", quality=88)


def _build_record(index: int, run_id: str, plot: dict, risk_level: str) -> DetectionResult:
    disease = None if risk_level == "normal" else DISEASES[index % len(DISEASES)]
    suffix = f"{run_id}_{index:02d}"
    image_id = f"{DEMO_PREFIX}img_{suffix}"
    original_path = settings.original_dir / f"{image_id}.jpg"
    result_path = settings.result_dir / f"{image_id}_result.jpg"
    color = (92 + index * 5 % 90, 126 + index * 7 % 80, 86 + index * 11 % 90)
    _ensure_demo_image(original_path, f"demo original {index}", color)
    _ensure_demo_image(result_path, f"demo result {index}", (color[0], max(40, color[1] - 30), max(40, color[2] - 20)))

    detections = []
    if disease:
        detections = [
            {
                "class_id": index % len(DISEASES),
                "label": disease,
                "confidence": 0.72 + (index % 20) / 100,
                "bbox": [80, 70, 360, 260],
                "area_ratio": 0.02 if risk_level == "low" else 0.12 if risk_level == "medium" else 0.26,
            }
        ]

    severity = SEVERITY_BY_RISK[risk_level]
    return DetectionResult(
        record_id=f"{DEMO_PREFIX}rec_{suffix}",
        image_id=image_id,
        plot_id=plot["plot_id"],
        plot_name=plot["plot_name"],
        region_name=plot["region_name"],
        timestamp=_timestamp(index),
        image_url=f"/static/original/{original_path.name}",
        result_image_url=f"/static/result/{result_path.name}",
        image_width=640,
        image_height=420,
        source_type="manual_upload",
        model_name="mock_disease_detector",
        model_version="mock-v1",
        detector_mode="mock",
        current_target_type="disease" if disease else None,
        geo={"lng": plot["lng"], "lat": plot["lat"]},
        detections=detections,
        summary={
            "disease_count": len(detections),
            "main_disease": disease,
            "max_confidence": max((item["confidence"] for item in detections), default=0.0),
            "severity": severity,
            "risk_level": risk_level,
        },
        suggestion={
            "title": f"演示数据：{disease or '未见明显病害'}",
            "content": "该记录为第五阶段联调演示数据，仅用于接口展示和流程验收。",
            "need_expert_confirm": risk_level in {"medium", "high"},
            "actions": ["现场复核演示地块", "记录田间环境情况"],
            "knowledge_tags": ["演示数据", risk_level],
            "disclaimer": "本建议为辅助参考，具体用药和处置方案需由农技人员确认。",
        },
    )


def _demo_plots(run_id: str) -> list[dict]:
    base_lng = 118.12
    base_lat = 33.12
    return [
        {
            "plot_id": f"{DEMO_PREFIX}plot_{run_id}_{index:02d}",
            "plot_name": f"第五阶段演示地块 {index + 1}",
            "region_name": DEFAULT_REGION_NAME,
            "lng": base_lng + index * 0.006,
            "lat": base_lat + index * 0.004,
            "owner_user_id": "demo_user",
            "owner_name": "演示用户",
            "manager_user_id": "demo_manager",
            "manager_name": "演示管理员",
        }
        for index in range(5)
    ]


def reset_demo_data() -> None:
    with get_connection() as conn:
        alert_ids = [
            row["alert_id"]
            for row in conn.execute("SELECT alert_id FROM alerts WHERE alert_id LIKE ?", (f"{DEMO_PREFIX}%",)).fetchall()
        ]
        record_alert_ids = [
            row["alert_id"]
            for row in conn.execute(
                "SELECT alert_id FROM alerts WHERE first_record_id LIKE ? OR latest_record_id LIKE ?",
                (f"{DEMO_PREFIX}%", f"{DEMO_PREFIX}%"),
            ).fetchall()
        ]
        all_alert_ids = sorted(set(alert_ids + record_alert_ids))
        for alert_id in all_alert_ids:
            conn.execute("DELETE FROM alert_actions WHERE alert_id = ?", (alert_id,))
            conn.execute("DELETE FROM alerts WHERE alert_id = ?", (alert_id,))
        conn.execute("DELETE FROM detection_records WHERE record_id LIKE ?", (f"{DEMO_PREFIX}%",))
        conn.commit()


async def seed_demo_data(reset: bool = False) -> dict:
    init_db()
    settings.original_dir.mkdir(parents=True, exist_ok=True)
    settings.result_dir.mkdir(parents=True, exist_ok=True)
    if reset:
        reset_demo_data()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    plots = _demo_plots(run_id)
    risks = ["normal", "low", "medium", "high"] * 5
    records = [_build_record(index, run_id, plots[index % len(plots)], risks[index]) for index in range(20)]

    alerts_created = 0
    for record in records:
        result_store.save(record)
        alert = await alert_service.handle_detection_result(record)
        if alert and alert.first_record_id == record.record_id:
            alerts_created += 1

    return {
        "run_id": run_id,
        "demo_prefix": DEMO_PREFIX,
        "plots": len(plots),
        "records": len(records),
        "alerts_created_or_updated": alerts_created,
        "reset_demo_data": reset,
        "note": "seed 数据为演示数据，不代表真实模型指标。",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Stage 5 demo data without real model/UAV/GIS dependencies.")
    parser.add_argument("--reset-demo-data", action="store_true", help="Remove existing demo_stage5_ demo records before seeding.")
    args = parser.parse_args()
    result = asyncio.run(seed_demo_data(reset=args.reset_demo_data))
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
