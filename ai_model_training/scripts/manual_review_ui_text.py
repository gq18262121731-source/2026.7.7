from __future__ import annotations

REVIEW_COMMON_TEXT = {
    "window_title_35t": "Phone-35T：Tungro 类别人工复核",
    "queue_title": "待复核样本",
    "preview_fallback": "预览图",
    "preview_missing": "预览图缺失：",
    "preview_render_failed": "预览图渲染失败：",
    "pillow_missing": "未检测到 Pillow，无法内嵌显示图片，请点击“打开预览图”。",
    "class_review_result": "类别复核结论",
    "review_decision": "处理决策",
    "model_error_type": "模型预测问题",
    "notes": "人工备注",
    "notes_hint": "请记录判断依据，例如：症状是否清晰、是否像 Tungro、是否需要暂缓、是否需要补样。",
    "save": "保存",
    "save_and_next": "保存并下一张",
    "previous": "上一张",
    "next": "下一张",
    "open_preview_image": "打开预览图",
    "open_image_folder": "打开图片文件夹",
    "loaded": "已加载：{item_id}",
    "saved": "已保存：{item_id}",
    "save_failed_title": "保存失败",
    "save_failed_message": "无法保存当前复核结果：\n{error}\n\n请检查结果文件是否被 Excel 占用。",
    "missing_path_title": "路径不存在",
    "missing_path_message": "以下路径不存在：\n{path}",
    "open_failed_title": "打开失败",
    "open_failed_message": "无法打开路径：\n{path}\n\n{error}",
    "summary_total": "总数：{value}",
    "summary_completed": "已完成：{value}",
    "summary_pending": "待完成：{value}",
    "summary_gate": "Gate 状态：{value}",
    "summary_reliability": "Tungro 可靠性：{value}",
    "current_item": "当前样本：{item_id}",
    "current_source": "当前来源：{source}",
    "shortcut_title": "快捷键：",
    "shortcut_lines": [
        "Ctrl + S：保存",
        "Ctrl + Enter：保存并下一张",
        "← / →：上一张 / 下一张",
        "双击左侧样本：跳转到该样本",
    ],
}

FIELD_LABELS_ZH = {
    "item_id": "样本 ID",
    "split_group": "数据分组",
    "is_holdout": "是否 holdout",
    "class_name": "原类别",
    "original_class_id": "原类别 ID",
    "review_priority": "复核优先级",
    "source_error_type": "来源错误类型",
    "source_reviewer_decision": "来源审核结论",
    "source_root_cause_type": "来源根因类型",
    "bbox_count": "标注框数量",
    "max_confidence": "最高置信度",
    "model_error_type": "模型预测问题",
    "needs_more_samples": "是否需要补样",
    "needs_temp_holdout": "是否需要暂缓",
    "needs_label_review": "是否需要标签复核",
    "needs_exclusion_from_claim": "是否排除出能力声明",
    "queue_reason": "入队原因",
    "image_path": "原图路径",
    "label_path": "标签路径",
    "prediction_image_path": "复核预览图路径",
}

CLASS_REVIEW_RESULT_DISPLAY = {
    "CONFIRMED_TUNGRO": "确认是 Tungro",
    "AMBIGUOUS_TUNGRO": "疑似 Tungro，但不稳定",
    "NOT_TUNGRO": "不是 Tungro",
    "LOW_QUALITY_UNUSABLE": "图像质量差，不可用",
    "NEEDS_MORE_EVIDENCE": "证据不足，需要更多样本",
    "TEMP_HOLDOUT": "暂缓使用 / Holdout",
}

REVIEW_DECISION_DISPLAY = {
    "KEEP_AS_TUNGRO": "保留为 Tungro 样本",
    "TEMP_HOLDOUT": "暂缓使用 / Holdout",
    "EXCLUDE_FROM_TUNGRO_CLAIM": "不进入 Tungro 能力声明",
    "CLASS_REVIEW_REQUIRED": "需要继续类别复核",
    "ADD_MORE_SAMPLES_REQUIRED": "需要补充 Tungro 样本",
    "UNUSABLE": "不可用样本",
}

MODEL_ERROR_TYPE_DISPLAY = {
    "OK": "预测基本可用",
    "NO_DETECTION": "模型漏检 / 没有检出",
    "MISS_DISEASE": "漏掉明显病斑",
    "PARTIAL_DETECTION": "只检出部分病斑",
    "BROAD_COARSE_BOX": "粗框，定位不精细",
    "FRAGMENTED_DENSE_BOXES": "碎片化密集小框",
    "TOO_MANY_BOXES": "框数过多",
    "FALSE_POSITIVE_BACKGROUND": "背景误检",
    "FALSE_POSITIVE_LEAF_TEXTURE": "叶片纹理误检",
    "FALSE_POSITIVE_EDGE": "边缘误检",
    "LOW_CONFIDENCE_NOISE": "低置信度噪声",
    "WRONG_CLASS": "类别预测错误",
    "IMAGE_BLUR": "图像模糊影响判断",
    "LABEL_OR_VISUAL_AMBIGUOUS": "标注或视觉本身不明确",
    "OTHER": "其他问题",
}


def format_enum_display(enum_value: str, display_map: dict[str, str]) -> str:
    label = display_map.get(enum_value, enum_value)
    return f"{label}（{enum_value}）"


def parse_enum_display(display_text: str, allowed_values: list[str]) -> str:
    cleaned = (display_text or "").strip()
    if not cleaned:
        return ""
    for enum_value in allowed_values:
        if cleaned == enum_value or f"（{enum_value}）" in cleaned or f"({enum_value})" in cleaned:
            return enum_value
    return cleaned


def humanize_value(field_name: str, value: str) -> str:
    if value is None:
        return ""
    cleaned = str(value).strip()
    if cleaned == "":
        return ""
    if field_name == "is_holdout":
        return "是" if cleaned.lower() == "true" else "否"
    if cleaned.upper() == "YES":
        return "是"
    if cleaned.upper() == "NO":
        return "否"
    return cleaned
