# 5 分钟快速联调

## 1. 设置环境变量

正式联调示例：

```bash
BASE_URL="https://test-api.example.com"
TOKEN="replace-with-your-token"
```

本机开发说明：

```bash
BASE_URL="http://127.0.0.1:8000"
TOKEN="replace-with-your-token"
```

## 2. 健康检查

稳定性：`stable`

```bash
curl -s "$BASE_URL/healthz" \
  -H "Authorization: Bearer $TOKEN"
```

期望响应：

```json
{
  "status": "ok"
}
```

## 3. 模型状态

稳定性：`preview`

```bash
curl -s "$BASE_URL/api/models/status" \
  -H "Authorization: Bearer $TOKEN"
```

前端处理建议：展示 `detector_mode`、`model_stage`、`fallback_to_mock`，遇到 `mock`、`smoke`、`experimental` 必须显示安全边界。

## 4. 单图识别

稳定性：`stable`

```bash
curl -s -X POST "$BASE_URL/api/detect/image" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample.jpg" \
  -F "source_type=phone_rgb" \
  -F "model_hint=phone" \
  -F "target_type=disease" \
  -F "plot_name=联调测试田块" \
  -F "region_name=人工上传"
```

注意：上传接口使用 `multipart/form-data`，图片字段名是 `file`，不是 JSON 字段。

## 5. LLM 状态

稳定性：`preview`

```bash
curl -s "$BASE_URL/api/agent/llm-status" \
  -H "Authorization: Bearer $TOKEN"
```

前端处理建议：展示当前是 OpenAI、mock fallback 还是未配置状态。LLM 不可用时，不要伪装成真实回答。

## 6. 知识库检索

稳定性：`preview`

```bash
curl -s -X POST "$BASE_URL/api/knowledge/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "白叶枯病的典型症状是什么？",
    "disease_id": "bacterial_leaf_blight",
    "top_k": 5
  }'
```

前端处理建议：该接口只返回知识依据，不生成 AI 回答。

## 7. LLM 知识上下文

稳定性：`preview`

```bash
curl -s -X POST "$BASE_URL/api/agent/knowledge-context" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "为什么识别结果提示可能是白叶枯？",
    "record_id": "rec_001",
    "model_class": "uav_blb",
    "confidence": 0.78,
    "source_type": "phone_rgb",
    "top_k": 5
  }'
```

前端处理建议：用于展示回答依据、知识图谱实体和三元组，始终展示 `safety_notice`。

## 8. LLM 自由问答

稳定性：`preview`

```bash
curl -s -X POST "$BASE_URL/api/agent/diagnosis-report" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "record_id": "rec_001",
    "model_class": "uav_blb",
    "confidence": 0.78,
    "source_type": "phone_rgb",
    "user_question": "这个结果能不能直接作为用药依据？"
  }'
```

前端处理建议：快捷问题只能填充输入框，不要写死答案；回答必须展示安全边界。

## 9. 大屏总览

稳定性：`stable`

```bash
curl -s "$BASE_URL/api/dashboard/summary" \
  -H "Authorization: Bearer $TOKEN"
```

前端处理建议：数值为空时展示 `0`，接口失败时显示错误态并允许重试。

## 10. WebSocket 连通性

```text
wss://test-api.example.com/ws/results
wss://test-api.example.com/ws/alerts
wss://test-api.example.com/ws/tasks
```

WebSocket 只推 JSON 事件，不推图片、base64 或视频帧。收到事件后，通过 HTTP 接口补拉详情。

## 11. 快速验收

| 项 | 通过标准 |
|---|---|
| healthz | 返回 `status=ok` |
| models/status | 能看到模型阶段和安全边界字段 |
| detect/image | 返回 `record_id`、`summary`、`image_url` 或 `result_image_url` |
| agent/llm-status | 返回 LLM 配置和 fallback 状态 |
| knowledge/search | 返回知识库片段 |
| agent/knowledge-context | 返回知识片段、图谱实体/关系/三元组和安全提示 |
| agent/diagnosis-report | 支持 `user_question` 自由提问并返回辅助回答 |
| dashboard/summary | 返回总览数字 |
| WebSocket | 可建立连接，收到事件后能 HTTP 补拉 |
