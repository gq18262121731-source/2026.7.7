# 核心响应样例

本文件只给移动端第一阶段联调用字段样例。完整字段以 `openapi_mobile_llm_cn.json` 为准。

说明：以下示例保留接口字段名、枚举值和错误码英文，不翻译 JSON key。

## DetectionResult

```json
{
  "record_id": "rec_001",
  "image_id": "img_001",
  "plot_name": "移动端拍照",
  "region_name": "人工上传",
  "timestamp": "2026-07-06T10:30:00",
  "image_url": "/static/original/img_001.jpg",
  "result_image_url": "/static/results/rec_001.jpg",
  "image_width": 1280,
  "image_height": 720,
  "source_type": "phone_rgb",
  "model_name": "phone-disease-detector",
  "model_version": "v1",
  "detector_mode": "real",
  "is_smoke": false,
  "model_stage": "real",
  "fallback_to_mock": false,
  "geo": {
    "lng": null,
    "lat": null
  },
  "detections": [
    {
      "class_id": 1,
      "label": "疑似白叶枯",
      "class_name": "bacterial_leaf_blight",
      "class_code": "bacterial_leaf_blight",
      "confidence": 0.82,
      "bbox": [120, 80, 260, 210],
      "area_ratio": 0.08
    }
  ],
  "summary": {
    "disease_count": 1,
    "main_disease": "疑似白叶枯",
    "max_confidence": 0.82,
    "severity": "moderate",
    "risk_level": "medium"
  },
  "suggestion": {
    "title": "建议人工复核",
    "content": "请结合田间症状和历史记录复核。",
    "need_expert_confirm": true,
    "actions": ["补拍叶片正反面近景图", "结合田间扩散情况复核"],
    "knowledge_tags": ["bacterial_leaf_blight", "symptom"],
    "disclaimer": "结果仅供辅助巡检，不作为正式农艺诊断或用药依据。"
  }
}
```

## MobileRecordDetail

```json
{
  "record_id": "rec_001",
  "plot_name": "移动端拍照",
  "image_url": "/static/original/img_001.jpg",
  "result_image_url": "/static/results/rec_001.jpg",
  "main_disease": "疑似白叶枯",
  "severity": "moderate",
  "risk_level": "medium",
  "detections": [
    {
      "class_id": 1,
      "label": "疑似白叶枯",
      "class_name": "bacterial_leaf_blight",
      "class_code": "bacterial_leaf_blight",
      "confidence": 0.82,
      "bbox": [120, 80, 260, 210],
      "area_ratio": 0.08
    }
  ],
  "suggestion": {
    "title": "建议人工复核",
    "content": "建议结合叶片症状、田间扩散和历史记录复核。",
    "need_expert_confirm": true,
    "actions": ["补拍叶片正反面近景图"],
    "knowledge_tags": ["bacterial_leaf_blight"],
    "disclaimer": "建议仅供辅助巡检，不作为正式农艺诊断或用药依据。"
  },
  "timestamp": "2026-07-06T10:30:00",
  "source_type": "phone_rgb",
  "model_name": "phone-disease-detector",
  "model_version": "v1",
  "detector_mode": "real",
  "is_smoke": false,
  "model_stage": "real",
  "fallback_to_mock": false
}
```

## Suggestion

```json
{
  "title": "建议人工复核",
  "content": "建议结合叶片症状、田间扩散和历史记录复核。",
  "need_expert_confirm": true,
  "actions": ["补拍清晰近景图", "人工查看叶缘和叶尖症状"],
  "knowledge_tags": ["bacterial_leaf_blight"],
  "disclaimer": "建议仅供辅助巡检，不作为正式农艺诊断或用药依据。"
}
```

## LLMStatusResponse

```json
{
  "llm_mode": "openai",
  "llm_provider": "openai",
  "llm_model": "gpt-4.1-mini",
  "json_response_format_enabled": true,
  "mock_fallback_enabled": true,
  "api_key_configured": true,
  "prompt_version": "kg_rag_agent_prompt_v1"
}
```

## KnowledgeSearchResponse

```json
{
  "query": "白叶枯病的典型症状是什么？",
  "results": [
    {
      "chunk_id": "blb_symptom_001",
      "score": 12.0,
      "text": "白叶枯病常表现为叶缘水浸状条斑，并可能发展为黄化或灰白枯死。",
      "source_id": "src_irri_blb",
      "source_title": "IRRI BLB",
      "source_type": "knowledge_base",
      "authority_level": "A",
      "disease_id": "bacterial_leaf_blight",
      "section_type": "symptom"
    }
  ]
}
```

## KnowledgeContextResponse

```json
{
  "success": true,
  "mode": "knowledge_context",
  "question": "为什么识别结果提示可能是白叶枯？",
  "matched_disease": {
    "disease_id": "bacterial_leaf_blight",
    "name": "水稻白叶枯病",
    "aliases": ["白叶枯", "细菌性白叶枯"]
  },
  "knowledge_chunks": [
    {
      "chunk_id": "blb_symptom_001",
      "title": "IRRI BLB",
      "section_type": "symptom",
      "content": "白叶枯病常表现为叶缘水浸状条斑。",
      "source": "knowledge_base",
      "score": 12.0,
      "disease_id": "bacterial_leaf_blight",
      "authority_level": "A"
    }
  ],
  "graph": {
    "entities": [
      {
        "entity_id": "disease:bacterial_leaf_blight",
        "entity_type": "Disease",
        "name": "水稻白叶枯病"
      }
    ],
    "relations": [
      {
        "source": "水稻白叶枯病",
        "relation": "has symptom",
        "target": "叶缘水浸状条斑"
      }
    ],
    "triples": [
      ["水稻白叶枯病", "has symptom", "叶缘水浸状条斑"]
    ]
  },
  "context_summary": "当前问题与水稻白叶枯病相关。已返回 5 条知识片段、12 个图谱实体和 12 条三元组。",
  "safety_notice": "该知识上下文仅用于辅助解释，不作为正式农艺诊断或用药依据。",
  "insufficient_evidence": false,
  "missing_context": []
}
```

## DiagnosisReportFreeQA

```json
{
  "mode": "free_qa",
  "question": "这个结果能不能直接作为用药依据？",
  "answer": "不能。当前回答只用于巡检辅助解释，需要结合田间症状和人工复核，不作为正式农艺诊断或用药处方。",
  "basis": [
    "识别结果与 bacterial_leaf_blight 存在知识库映射",
    "知识库中白叶枯病与叶缘水浸状条斑相关"
  ],
  "uncertainty": [
    "当前回答未结合完整田间调查",
    "图片角度、清晰度和光照可能影响识别结果"
  ],
  "next_steps": [
    "建议补拍叶片正反面近景图",
    "建议由农技人员结合田间情况复核"
  ],
  "safety_notice": "该回答用于巡检辅助，不作为正式农艺诊断或用药处方。",
  "suspected_disease": {
    "disease_id": "bacterial_leaf_blight",
    "zh_name": "水稻白叶枯病",
    "en_name": "Bacterial leaf blight"
  },
  "model_result_summary": "当前识别结果提示疑似白叶枯，置信度 0.82。",
  "knowledge_summary": "知识库依据包括典型症状、发生条件和人工复核建议。",
  "risk_level": "medium",
  "manual_check_questions": [
    "叶缘是否有水浸状条斑？",
    "病斑是否沿叶脉扩展？"
  ],
  "management_suggestions": [
    "建议人工复核叶片正反面症状。",
    "如需用药，应由农技人员结合田间情况判断。"
  ],
  "uncertainty_notes": [
    "单张图片不能替代现场诊断。",
    "模型结果可能受光照和拍摄角度影响。"
  ],
  "evidence_sources": [
    {
      "source_id": "src_irri_blb",
      "source_title": "IRRI BLB",
      "source_type": "knowledge_base",
      "authority_level": "A",
      "url_or_reference": "knowledge_base",
      "language": "zh",
      "notes": "用于辅助解释的知识片段"
    }
  ],
  "insufficient_evidence": false,
  "llm_mode": "openai",
  "llm_provider": "openai",
  "llm_model": "gpt-4.1-mini",
  "prompt_version": "kg_rag_agent_prompt_v1",
  "fallback_used": false,
  "fallback_level": "none",
  "api_error_type": null,
  "repair_attempted": false,
  "schema_valid": true,
  "safety_passed": true
}
```

## ErrorResponse

统一错误结构示例：

```json
{
  "success": false,
  "error_code": "LLM_API_ERROR",
  "message": "LLM 服务暂不可用",
  "detail": {
    "error_type": "provider_error"
  }
}
```

FastAPI 默认参数错误也可能返回：

```json
{
  "detail": [
    {
      "loc": ["body", "file"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```
