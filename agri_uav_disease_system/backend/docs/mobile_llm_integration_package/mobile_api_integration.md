# 移动端接口联调说明

移动端第一阶段建议先接“拍照识别 + LLM 知识问答”闭环，不强制接地块列表。

第一阶段核心链路：

```text
拍照上传 -> 获取识别结果 -> 基于识别结果提问 -> 获取知识库/知识图谱上下文 -> 返回辅助解释和安全提示
```

第一阶段优先接口：

```http
GET  /healthz
GET  /api/models/status
GET  /api/agent/llm-status
POST /api/detect/image
GET  /api/mobile/records/{record_id}
GET  /api/mobile/suggestions/{record_id}
POST /api/knowledge/search
POST /api/agent/knowledge-context
POST /api/agent/diagnosis-report
```

地块列表、地块详情、UAV 任务、异常区列表和巡检报告可作为第二阶段接入。

统一环境变量：

```bash
BASE_URL="https://test-api.example.com"
TOKEN="replace-with-your-token"
```

统一 Header：

```http
Authorization: Bearer <TOKEN>
```

## 1. 健康检查

### 接口

GET `/healthz`

### 稳定性

`stable`

### 用途

用于移动端启动页或联调脚本确认后端服务可连通。

### 请求 Header

```http
Authorization: Bearer <TOKEN>
```

### 成功响应示例

```json
{
  "status": "ok"
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "INTERNAL_ERROR",
  "message": "服务端内部错误",
  "detail": {}
}
```

### 前端处理建议

- 健康检查失败时展示“后端服务不可用，请稍后重试”。
- 不要在健康检查失败时清空本地已有识别记录缓存。

## 2. 获取 LLM 状态

### 接口

GET `/api/agent/llm-status`

### 稳定性

`preview`

### 用途

用于移动端判断自由问答当前是 LLM、mock fallback 还是未配置状态。

### 请求 Header

```http
Authorization: Bearer <TOKEN>
```

### 成功响应示例

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

### 失败响应示例

```json
{
  "success": false,
  "error_code": "INTERNAL_ERROR",
  "message": "服务端内部错误",
  "detail": {}
}
```

### 前端处理建议

- LLM 不可用时仍允许展示识别结果。
- 若进入 mock fallback，必须提示“当前为模拟或降级回答”。

## 3. 手机拍照上传识别

### 接口

POST `/api/detect/image`

### 稳定性

`stable`

### 用途

用于移动端拍照或相册图片上传识别。

### 请求 Header

```http
Authorization: Bearer <TOKEN>
Content-Type: multipart/form-data
```

### FormData 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file` | file | 是 | 图片文件 |
| `source_type` | string | 否 | 建议 `phone_rgb` |
| `model_hint` | string | 否 | 建议 `phone` |
| `target_type` | string | 否 | 建议 `disease` |
| `plot_name` | string | 否 | 地块名称，第一阶段可传“移动端拍照” |
| `region_name` | string | 否 | 区域名称，第一阶段可传“人工上传” |

### 成功响应示例

```json
{
  "record_id": "rec_001",
  "image_id": "img_001",
  "image_url": "/static/original/img_001.jpg",
  "result_image_url": "/static/results/rec_001.jpg",
  "detector_mode": "real",
  "model_stage": "real",
  "fallback_to_mock": false,
  "summary": {
    "disease_count": 1,
    "main_disease": "疑似白叶枯",
    "max_confidence": 0.82,
    "severity": "moderate",
    "risk_level": "medium"
  },
  "suggestion": {
    "title": "建议人工复核",
    "content": "请结合现场叶片症状与田间扩散情况复核。",
    "disclaimer": "结果仅供辅助巡检，不作为正式农艺诊断或用药依据。"
  }
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "INVALID_IMAGE",
  "message": "图片格式不支持或文件损坏",
  "detail": {}
}
```

### 前端处理建议

- 上传前检查文件类型和大小。
- 返回 `record_id` 后进入识别结果详情页。
- 返回 `fallback_to_mock=true`、`model_stage=smoke` 或 `model_stage=experimental` 时必须展示能力边界。
- 不要将识别结果写成“确诊”。

## 4. 获取识别记录详情

### 接口

GET `/api/mobile/records/{record_id}`

### 稳定性

`stable`

### 用途

用于展示一次识别记录的图片、结果图、检测摘要和建议。

### 成功响应示例

```json
{
  "record_id": "rec_001",
  "plot_name": "移动端拍照",
  "image_url": "/static/original/img_001.jpg",
  "result_image_url": "/static/results/rec_001.jpg",
  "summary": {
    "main_disease": "疑似白叶枯",
    "risk_level": "medium",
    "max_confidence": 0.82
  }
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "RECORD_NOT_FOUND",
  "message": "识别记录不存在",
  "detail": {
    "record_id": "rec_001"
  }
}
```

### 前端处理建议

- 图片展示优先使用 `result_image_url`。
- 图片 URL 相对路径需用 `BASE_URL` 拼接。

## 5. 获取记录建议

### 接口

GET `/api/mobile/suggestions/{record_id}`

### 稳定性

`stable`

### 用途

用于移动端单独获取某条记录的辅助建议。

### 成功响应示例

```json
{
  "title": "建议人工复核",
  "content": "建议结合叶片症状、田间扩散和历史记录复核。",
  "disclaimer": "建议仅供辅助巡检，不作为正式农艺诊断或用药依据。"
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "RECORD_NOT_FOUND",
  "message": "识别记录不存在",
  "detail": {}
}
```

### 前端处理建议

- 始终展示 `disclaimer`。
- 不展示农药处方、剂量或强制处置方案。

## 6. 知识库检索

### 接口

POST `/api/knowledge/search`

### 稳定性

`preview`

### 用途

用于按用户问题、病害 ID 或知识章节检索知识库片段。

### 请求体

```json
{
  "query": "白叶枯病的典型症状是什么？",
  "disease_id": "bacterial_leaf_blight",
  "section_type": "symptom",
  "top_k": 5
}
```

### 成功响应示例

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

### 失败响应示例

```json
{
  "success": false,
  "error_code": "DISEASE_NOT_FOUND",
  "message": "病害 ID 不存在",
  "detail": {}
}
```

### 前端处理建议

- 可用于“当前回答用了哪些知识依据”展示。
- 该接口只检索知识，不生成 AI 回答。

## 7. 获取 LLM 知识上下文

### 接口

POST `/api/agent/knowledge-context`

### 稳定性

`preview`

### 用途

根据用户问题、识别结果和病害类别，聚合返回 LLM 可使用的知识库片段和知识图谱实体、关系、三元组。

### 请求体

```json
{
  "question": "为什么识别结果提示可能是白叶枯？",
  "record_id": "rec_001",
  "disease_id": "bacterial_leaf_blight",
  "model_class": "uav_blb",
  "confidence": 0.78,
  "source_type": "phone_rgb",
  "top_k": 5,
  "include_knowledge_chunks": true,
  "include_graph": true,
  "include_relations": true
}
```

### 字段说明

| 字段 | 必填 | 类型 | 说明 |
|---|---:|---|---|
| `question` | 是 | string | 用户真实问题 |
| `record_id` | 否 | string | 识别记录 ID |
| `disease_id` | 否 | string | 病害 ID |
| `model_class` | 否 | string | 模型输出类别 |
| `confidence` | 否 | number | 模型置信度 |
| `source_type` | 否 | string | 来源类型，如 `phone_rgb` |
| `top_k` | 否 | integer | 返回知识片段数量，默认 5 |
| `include_knowledge_chunks` | 否 | boolean | 是否返回知识库片段 |
| `include_graph` | 否 | boolean | 是否返回知识图谱实体 |
| `include_relations` | 否 | boolean | 是否返回关系和三元组 |

### 成功响应示例

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

### 失败响应示例

```json
{
  "success": false,
  "error_code": "KNOWLEDGE_DATA_ERROR",
  "message": "知识库文件读取失败",
  "detail": {}
}
```

### 前端处理建议

- 用于回答依据展示，不直接当作最终回答。
- 当 `insufficient_evidence=true` 时提示“知识依据不足，需要人工复核”。
- 始终展示 `safety_notice`。

## 8. LLM 自由问答

### 接口

POST `/api/agent/diagnosis-report`

### 稳定性

`preview`

### 用途

用于移动端提交用户真实问题，返回基于识别结果、知识库和知识图谱的辅助解释。

### 请求体

```json
{
  "record_id": "rec_001",
  "disease_id": "bacterial_leaf_blight",
  "model_class": "uav_blb",
  "confidence": 0.78,
  "source_type": "phone_rgb",
  "user_question": "为什么识别结果提示可能是白叶枯？"
}
```

### 成功响应示例

```json
{
  "mode": "free_qa",
  "question": "为什么识别结果提示可能是白叶枯？",
  "answer": "从当前识别类别和知识库依据看，白叶枯通常与叶缘病斑、高湿环境等因素相关。但仅凭图片识别结果不能确诊，仍需人工复核。",
  "basis": [
    "模型输出类别与 bacterial_leaf_blight 存在映射",
    "知识库中白叶枯病与叶缘水浸状条斑相关",
    "知识图谱中高湿多雨与白叶枯发生风险相关"
  ],
  "uncertainty": [
    "当前回答未结合完整田间调查",
    "图片角度、清晰度和光照可能影响识别结果"
  ],
  "next_steps": [
    "建议补拍叶片正反面近景图",
    "建议人工查看叶缘、叶尖和叶脉附近症状",
    "如需用药，应由农技人员结合田间情况判断"
  ],
  "safety_notice": "该回答用于巡检辅助，不作为正式农艺诊断或用药处方。"
}
```

### 失败响应示例

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

### 前端处理建议

- 快捷问题只能填充输入框，不允许写死答案。
- 用户输入非快捷问题时，也应调用该接口或明确展示降级状态。
- LLM 不可用时显示友好错误，不伪装成真实回答。

## 9. 可选：获取病害列表

### 接口

GET `/api/knowledge/diseases`

### 稳定性

`preview`

### 用途

用于移动端展示可解释病害类别，或给调试页选择 disease_id。

### 成功响应示例

```json
{
  "items": [
    {
      "disease_id": "bacterial_leaf_blight",
      "zh_name": "水稻白叶枯病",
      "en_name": "Bacterial leaf blight",
      "authority_level": "A",
      "model_supported": true
    }
  ],
  "count": 1
}
```

### 前端处理建议

- 第一版可不做病害选择页。
- 识别结果详情页优先使用模型返回类别和知识上下文接口。

## 10. 可选：获取病害详情

### 接口

GET `/api/knowledge/diseases/{disease_id}`

### 稳定性

`preview`

### 用途

用于展示病害百科详情。

### 前端处理建议

- 作为知识详情页可选能力。
- 页面必须展示“仅供辅助解释”的安全提示。

## 11. 第二阶段可选：获取移动端首页

### 接口

GET `/api/mobile/overview`

### 稳定性

`stable`

### 用途

用于移动端第二阶段展示待处理告警、最近识别、风险摘要和巡检入口。第一阶段可以不接入该接口。

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `user_id` | string | 否 | 当前用户 ID；演示环境可不传 |

### 成功响应示例

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
      "main_disease": "疑似白叶枯",
      "risk_level": "medium",
      "timestamp": "2026-07-06T10:30:00"
    }
  ]
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "VALIDATION_ERROR",
  "message": "请求参数校验失败",
  "detail": {
    "errors": []
  }
}
```

### 前端处理建议

- 加载中显示骨架屏或 Loading。
- 数值为空显示 `0`。
- 接口失败时保留页面结构，展示中文错误提示。

## 12. 第二阶段可选：获取地块列表

### 接口

GET `/api/mobile/plots`

### 稳定性

`stable`

### 用途

用于移动端展示可巡检地块列表。第一阶段不强制接入。

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `risk_level` | string | 否 | 风险等级过滤 |
| `region_name` | string | 否 | 区域过滤 |
| `keyword` | string | 否 | 地块名称或编号关键词 |
| `user_id` | string | 否 | 用户 ID |

### 成功响应示例

```json
{
  "items": [
    {
      "plot_id": "plot_001",
      "plot_name": "宿迁一号田",
      "region_name": "宿城区示范镇",
      "risk_level": "medium",
      "latest_record_id": "rec_001"
    }
  ],
  "total": 1
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "VALIDATION_ERROR",
  "message": "请求参数校验失败",
  "detail": {
    "errors": []
  }
}
```

### 前端处理建议

- 空列表显示“暂无地块数据”。
- `risk_level` 使用统一风险标签，不要直接裸显示英文。

## 13. 第二阶段可选：获取地块详情

### 接口

GET `/api/mobile/plots/{plot_id}`

### 稳定性

`stable`

### 用途

用于移动端地块详情页展示地块摘要、最新记录、风险状态和告警。

### Path 参数

| 参数 | 类型 | 说明 |
|---|---|---|
| `plot_id` | string | 地块 ID |

### 成功响应示例

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

### 失败响应示例

```json
{
  "success": false,
  "error_code": "RECORD_NOT_FOUND",
  "message": "记录不存在",
  "detail": {
    "plot_id": "plot_001"
  }
}
```

### 前端处理建议

- `image_url` / `result_image_url` 若为相对路径，使用 `BASE_URL` 拼接。
- 地块不存在时返回列表页或展示空态。

## 14. 第二阶段可选：UAV 异常区手机复查

### 接口

POST `/api/uav/abnormal-regions/{region_id}/phone-followup`

### 稳定性

`preview`

### 用途

用于移动端围绕 UAV 异常区域上传近景图，形成多源协同证据并回写异常区。

### Path 参数

| 参数 | 类型 | 说明 |
|---|---|---|
| `region_id` | string | UAV 异常区域 ID |

### FormData 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file` | file | 是 | 手机近景图 |
| `field_id` | string | 是 | 田块 ID |
| `uav_task_id` | string | 是 | UAV 任务 ID |
| `source_type` | string | 否 | 建议 `phone_followup` |
| `model_hint` | string | 否 | 建议 `phone` |
| `target_type` | string | 否 | 建议 `disease` |
| `region_name` | string | 否 | 区域名称 |

### 成功响应示例

```json
{
  "record_id": "rec_followup_001",
  "image_id": "img_phone_001",
  "uav_task_id": "uav_001",
  "abnormal_region_id": "region_001",
  "model_stage": "real",
  "summary": {
    "main_disease": "疑似白叶枯",
    "max_confidence": 0.79,
    "risk_level": "medium"
  }
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "RECORD_NOT_FOUND",
  "message": "异常区域不存在",
  "detail": {
    "region_id": "region_001"
  }
}
```

### 前端处理建议

- 仅在选择异常区后开放复查按钮。
- 复查成功后刷新异常区详情，读取 `linked_phone_image_id`、`linked_record_id`、`confirmed_disease_type`、`confirm_status`。

## 15. 第二阶段可选：获取移动端告警

### 接口

GET `/api/mobile/alerts`

### 稳定性

`stable`

### 用途

用于移动端展示待处理风险告警。

### 成功响应示例

```json
{
  "items": [
    {
      "alert_id": "alert_001",
      "plot_id": "plot_001",
      "plot_name": "宿迁一号田",
      "risk_level": "high",
      "status": "active",
      "message": "该地块出现高风险识别记录，建议复核。"
    }
  ],
  "total": 1
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "DATABASE_ERROR",
  "message": "数据库访问失败",
  "detail": {}
}
```

### 前端处理建议

- 高风险告警置顶。
- 告警建议是巡检提示，不是最终诊断。
