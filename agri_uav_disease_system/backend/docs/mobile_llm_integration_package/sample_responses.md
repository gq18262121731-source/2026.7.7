# 核心响应样例

本文件只给联调用最小字段样例。完整字段以 `openapi.json` 和 `api_contract_full.md` 为准。

## DetectionResult

```json
{
  "record_id": "rec_001",
  "image_id": "img_001",
  "field_id": "SQ_FIELD_001",
  "plot_name": "宿迁一号田",
  "region_name": "人工上传",
  "timestamp": "2026-07-06T10:30:00",
  "image_url": "/static/original/img_001.jpg",
  "result_image_url": "/static/results/rec_001.jpg",
  "source_type": "phone_rgb",
  "model_name": "phone-disease-detector",
  "model_version": "v1",
  "detector_mode": "real",
  "is_smoke": false,
  "model_stage": "real",
  "formal_metric_available": true,
  "fallback_to_mock": false,
  "detections": [
    {
      "class_id": 1,
      "label": "疑似白叶枯",
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
    "disclaimer": "结果仅供辅助巡检，不作为正式农艺诊断或用药依据。"
  }
}
```

## RecordListResponse

```json
{
  "items": [
    {
      "record_id": "rec_001",
      "plot_name": "宿迁一号田",
      "region_name": "人工上传",
      "result_image_url": "/static/results/rec_001.jpg",
      "model_stage": "real",
      "fallback_to_mock": false,
      "summary": {
        "main_disease": "疑似白叶枯",
        "risk_level": "medium",
        "max_confidence": 0.82
      }
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

## DashboardSummary

```json
{
  "today_detect_count": 12,
  "total_record_count": 236,
  "disease_record_count": 58,
  "normal_record_count": 178,
  "high_risk_plot_count": 2,
  "medium_risk_plot_count": 6,
  "low_risk_plot_count": 18,
  "risk_level_counts": {
    "high": 2,
    "medium": 6,
    "low": 18
  }
}
```

## LatestRecordsResponse

```json
{
  "items": [
    {
      "record_id": "rec_001",
      "plot_name": "宿迁一号田",
      "main_disease": "疑似白叶枯",
      "severity": "moderate",
      "risk_level": "medium",
      "result_image_url": "/static/results/rec_001.jpg",
      "timestamp": "2026-07-06T10:30:00",
      "model_stage": "real",
      "fallback_to_mock": false
    }
  ]
}
```

## LatestAlertsResponse

```json
{
  "items": [
    {
      "alert_id": "alert_001",
      "record_id": "rec_001",
      "plot_name": "宿迁一号田",
      "main_disease": "疑似白叶枯",
      "severity": "severe",
      "risk_level": "high",
      "message": "该地块出现高风险识别记录，建议复核。",
      "timestamp": "2026-07-06T10:31:00"
    }
  ]
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
    "模型输出类别与 bacterial_leaf_blight 存在映射",
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
  "safety_notice": "该回答用于巡检辅助，不作为正式农艺诊断或用药处方。"
}
```

## MobileOverview

```json
{
  "user_id": "demo_user",
  "today_detect_count": 8,
  "pending_alert_count": 2,
  "high_risk_plot_count": 1,
  "latest_records": [
    {
      "record_id": "rec_001",
      "plot_name": "宿迁一号田",
      "risk_level": "medium"
    }
  ]
}
```

## MobilePlotDetail

```json
{
  "plot_id": "plot_001",
  "plot_name": "宿迁一号田",
  "region_name": "宿城区示范镇",
  "risk_level": "medium",
  "latest_record": {
    "record_id": "rec_001",
    "main_disease": "疑似白叶枯",
    "result_image_url": "/static/results/rec_001.jpg"
  },
  "alerts": []
}
```

## UavTask

```json
{
  "uav_task_id": "uav_001",
  "field_id": "SQ_FIELD_001",
  "task_name": "宿迁一号田 UAV dry-run 巡检",
  "flight_date": "2026-07-06",
  "sensor_type": "multispectral",
  "data_mode": "dry_run",
  "growth_stage": "分蘖期",
  "weather_text": "阴天，湿度较高",
  "status": "created",
  "summary": "dry-run 任务已创建",
  "is_mock": true
}
```

## AbnormalRegion

```json
{
  "region_id": "region_001",
  "uav_task_id": "uav_001",
  "field_id": "SQ_FIELD_001",
  "region_name": "A-001",
  "abnormal_type": "ndvi_low",
  "abnormal_level": "medium",
  "abnormal_area_ratio": 0.12,
  "source_index_type": "ndvi",
  "confirm_status": "phone_confirmed",
  "linked_phone_image_id": "img_phone_001",
  "linked_record_id": "rec_followup_001",
  "confirmed_disease_type": "疑似白叶枯",
  "confirm_confidence": 0.79
}
```

## InspectionReport

```json
{
  "report_id": "report_001",
  "field_id": "SQ_FIELD_001",
  "uav_task_id": "uav_001",
  "report_title": "宿迁一号田巡检报告",
  "report_date": "2026-07-06",
  "summary": "本报告用于辅助巡检复核。",
  "abnormal_region_summary": {
    "total": 3,
    "items": []
  },
  "phone_followup_summary": {
    "total": 3,
    "confirmed_count": 1,
    "items": []
  },
  "risk_summary": {
    "risk_level": "medium",
    "risk_score": 68,
    "risk_probability_note": "规则评分不代表正式发病概率。",
    "main_factors": ["UAV 指数异常", "手机近景疑似病害"]
  },
  "risk_model_detail": {
    "prediction_id": "risk_001",
    "model_type": "rule_weighted",
    "model_stage": "experimental",
    "probability_claim": false,
    "experimental_only": true,
    "not_for_production": true,
    "safety_note": "规则评分仅用于巡检优先级辅助判断。"
  },
  "rag_suggestion": "建议结合田间情况人工复核。",
  "model_safety_note": "该报告不代表最终现场诊断结论，不输出农事处置方案。",
  "report_status": "generated"
}
```
