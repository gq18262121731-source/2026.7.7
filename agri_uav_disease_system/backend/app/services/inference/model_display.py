from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelDisplayInfo:
    display_name: str
    warning: str
    usage_scope: str
    capability_level: str
    class_codes: list[str]
    source_types: list[str]
    route_condition: str
    current_target_type: str | None


MODEL_DISPLAY_REGISTRY: dict[str, ModelDisplayInfo] = {
    "phone_rice_disease_yolo": ModelDisplayInfo(
        display_name="近距离水稻病害 smoke 模型",
        warning="小样本 1 epoch 冒烟模型，仅验证链路，不代表正式识别效果。",
        usage_scope="phone_rgb/manual_upload",
        capability_level="smoke_only",
        class_codes=["bacterial_leaf_blight", "brown_spot", "rice_blast"],
        source_types=["phone_rgb", "manual_upload"],
        route_condition="source_type=phone_rgb or manual_upload",
        current_target_type="disease",
    ),
    "phone_rice_disease_yolo:experimental": ModelDisplayInfo(
        display_name="Phone RiceLeafDiseaseBD experimental model",
        warning=(
            "Experimental 3 epoch RiceLeafDiseaseBD phone RGB expanded weight; for experiment "
            "verification only and not formal model performance."
        ),
        usage_scope="phone_rgb/manual_upload + model_hint=phone_exp or model_stage_hint=experimental",
        capability_level="experimental_only",
        class_codes=["brown_spot", "rice_blast", "leaf_smut", "tungro", "sheath_blight"],
        source_types=["phone_rgb", "manual_upload"],
        route_condition="model_hint=phone_exp or model_stage_hint=experimental",
        current_target_type="disease",
    ),
    "uav_rice_disease_yolo": ModelDisplayInfo(
        display_name="UAV 稻穗辅助目标 smoke 模型",
        warning="当前识别对象为 rice_panicle，属于 crop_object，不是病害或虫害模型。",
        usage_scope="uav_rgb/uav_ms/uav_multispectral/uav_video_frame 默认路由",
        capability_level="auxiliary_smoke_only",
        class_codes=["rice_panicle"],
        source_types=["uav_rgb", "uav_ms", "uav_multispectral", "uav_video_frame"],
        route_condition="UAV source without model_hint/target_type disease",
        current_target_type="crop_object",
    ),
    "uav_blb_disease_yolo": ModelDisplayInfo(
        display_name="UAV 白叶枯病 smoke 模型",
        warning="基于 BLB UAV preview 数据的 1 epoch smoke 权重，仅验证 UAV 病害链路，不代表正式模型效果。",
        usage_scope="uav_multispectral + model_hint=uav_blb 或 target_type=disease",
        capability_level="smoke_only",
        class_codes=["bacterial_leaf_blight"],
        source_types=["uav_rgb", "uav_ms", "uav_multispectral", "uav_video_frame"],
        route_condition="UAV source with model_hint=uav_blb or target_type=disease",
        current_target_type="disease",
    ),
    "uav_blb_disease_yolo:experimental": ModelDisplayInfo(
        display_name="UAV BLB experimental model",
        warning=(
            "Experimental weight based on BLB UAV constrained-408 RGB preview renders; "
            "for experiment verification only and not formal model performance."
        ),
        usage_scope="uav_multispectral + model_hint=uav_blb_exp or model_stage_hint=experimental",
        capability_level="experimental_only",
        class_codes=["bacterial_leaf_blight"],
        source_types=["uav_multispectral", "uav_ms", "uav_video_frame"],
        route_condition="model_hint=uav_blb_exp or model_stage_hint=experimental",
        current_target_type="disease",
    ),
    "mock_disease_detector": ModelDisplayInfo(
        display_name="Mock 演示检测器",
        warning="模拟检测结果，仅用于系统联调和无模型兜底。",
        usage_scope="fallback/default",
        capability_level="mock_only",
        class_codes=[],
        source_types=["unknown", "fallback"],
        route_condition="fallback when source/model unavailable",
        current_target_type=None,
    ),
}


def get_model_display_info(model_name: str, model_stage: str | None = None) -> ModelDisplayInfo:
    if model_stage == "experimental":
        key = f"{model_name}:experimental"
        if key in MODEL_DISPLAY_REGISTRY:
            return MODEL_DISPLAY_REGISTRY[key]
    return MODEL_DISPLAY_REGISTRY.get(model_name, MODEL_DISPLAY_REGISTRY["mock_disease_detector"])


def is_disease_like_target(current_target_type: str | None) -> bool:
    return current_target_type in {"disease", "pest", "pest_damage"}


def is_disease_like_record(record) -> bool:
    return is_disease_like_target(getattr(record, "current_target_type", None))
