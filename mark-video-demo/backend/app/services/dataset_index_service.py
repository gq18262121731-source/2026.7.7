from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from app.services.annotation_loader import fallback_detection, label_from_name, load_yolo_annotations
from app.services.local_image_service import dataset_status, image_size, pick_images, public_image_url


MODEL_INFO = [
    {
        "key": "phone-closeup-v1",
        "name": "近距离水稻病害识别模型",
        "scene_type": "phone_closeup",
        "labels": ["Brown Spot", "Blast", "Bacterial Blight", "Tungro"],
        "status": "running",
        "last_called_at": "2026-07-01T02:40:00+08:00",
        "today_calls": 16,
    },
    {
        "key": "uav-multispectral-v1",
        "name": "无人机水稻病害分析模型",
        "scene_type": "uav_multispectral",
        "labels": ["Bacterial Leaf Blight", "Stress Area"],
        "status": "running",
        "last_called_at": "2026-07-01T02:42:00+08:00",
        "today_calls": 9,
    },
]

_sample_registry: Dict[str, Path] = {}


def model_by_key(model_key: str) -> dict:
    return next((model for model in MODEL_INFO if model["key"] == model_key), MODEL_INFO[0])


def scene_for_model(model_key: str) -> str:
    return model_by_key(model_key)["scene_type"]


def sample_key_for(path: Path) -> str:
    key = f"sample_{abs(hash(str(path.resolve()).lower())):x}"
    _sample_registry[key] = path
    return key


def get_sample_path(sample_key: str) -> Optional[Path]:
    if sample_key in _sample_registry:
        return _sample_registry[sample_key]
    build_samples()
    return _sample_registry.get(sample_key)


def build_samples() -> List[dict]:
    samples: List[dict] = []
    for model in MODEL_INFO:
        for index, path in enumerate(pick_images(model["scene_type"], limit=4), start=1):
            samples.append(
                {
                    "sample_key": sample_key_for(path),
                    "source_type": model["scene_type"],
                    "model_key": model["key"],
                    "display_name": display_name(model["scene_type"], index),
                    "source_label": "近距离采集" if model["scene_type"] == "phone_closeup" else "无人机巡田",
                }
            )
    return samples


def display_name(scene_type: str, index: int) -> str:
    prefix = "近距离图像" if scene_type == "phone_closeup" else "巡田图像"
    return f"{prefix} {index:02d}"


def result_from_sample(model_key: str, sample_key: Optional[str] = None, source_type: Optional[str] = None) -> dict:
    if sample_key:
        image_path = get_sample_path(sample_key)
        if image_path is None:
            raise KeyError(sample_key)
        model = model_by_key(model_key)
    else:
        scene_type = source_type or scene_for_model(model_key)
        images = pick_images(scene_type, limit=1)
        if not images:
            raise KeyError(scene_type)
        image_path = images[0]
        model = model_by_key(model_key)

    scene_type = model["scene_type"]
    width, height = image_size(image_path)
    detections = load_yolo_annotations(image_path, scene_type) or fallback_detection(image_path, scene_type)
    top = max(detections, key=lambda item: item["confidence"])
    severity = severity_from_detections(detections)
    label = top["label"] or label_from_name(image_path, scene_type)

    return {
        "model": model,
        "image": {
            "sample_key": sample_key_for(image_path),
            "source_type": scene_type,
            "source_name": "近距离采集" if scene_type == "phone_closeup" else "无人机巡田",
            "original_url": public_image_url(image_path),
            "width": width,
            "height": height,
        },
        "detections": detections,
        "summary": {
            "top_label": label,
            "top_confidence": top["confidence"],
            "detection_count": len(detections),
            "process_ms": 760 + len(detections) * 68,
            "risk_level": risk_label(severity),
        },
        "analysis": analysis_for(label, severity, scene_type),
    }


def severity_from_detections(detections: List[dict]) -> str:
    if len(detections) >= 5 or any(item["severity"] == "severe" for item in detections):
        return "severe"
    if len(detections) >= 2 or any(item["severity"] == "moderate" for item in detections):
        return "moderate"
    return "mild"


def risk_label(severity: str) -> str:
    return {"mild": "低风险", "moderate": "中风险", "severe": "高风险"}.get(severity, "中风险")


def analysis_for(label: str, severity: str, scene_type: str) -> dict:
    scene_text = "近距离叶片图像" if scene_type == "phone_closeup" else "无人机巡田图像"
    if "Brown" in label:
        title = "疑似褐斑病风险"
        suggestion = "建议结合近期湿度和田间密度复核，优先对病斑集中区域进行点状治理。"
    elif "Blast" in label:
        title = "疑似稻瘟病风险"
        suggestion = "建议关注品种抗性、氮肥水平和叶面湿度，必要时进行分区复查。"
    elif "Blight" in label:
        title = "疑似白叶枯病风险"
        suggestion = "建议核查水层管理、近期降雨和病斑边缘扩展情况，避免扩散。"
    else:
        title = "疑似长势胁迫风险"
        suggestion = "建议结合灌溉、施肥和虫害巡查结果进行综合判断。"
    return {
        "mode": "knowledge_base",
        "title": title,
        "text": f"系统已完成{scene_text}分析，当前风险等级为{risk_label(severity)}。{suggestion}",
        "prevention": suggestion,
    }


def source_status() -> dict:
    return dataset_status()

