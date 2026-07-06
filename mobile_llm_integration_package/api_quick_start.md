# 5 分钟快速联调

本文件只覆盖移动端第一阶段闭环：

```text
拍照识别 -> 识别详情 -> LLM 状态 -> 知识检索 -> 知识上下文 -> 自由问答
```

## 1. 设置环境变量

正式联调前请使用单独提供的真实地址和 token。本文中的地址只是占位示例。

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

稳定性：`stable`（稳定）

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

稳定性：`preview`（预览）

```bash
curl -s "$BASE_URL/api/models/status" \
  -H "Authorization: Bearer $TOKEN"
```

前端处理建议：展示 `detector_mode`、`model_stage`、`fallback_to_mock`，遇到 `mock`、`smoke`、`experimental` 必须显示安全边界。

## 4. 单图识别

稳定性：`stable`（稳定）

```bash
curl -s -X POST "$BASE_URL/api/detect/image" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample.jpg" \
  -F "source_type=phone_rgb" \
  -F "model_hint=phone" \
  -F "target_type=disease" \
  -F "plot_name=移动端拍照" \
  -F "region_name=人工上传"
```

注意：

- 上传接口使用 `multipart/form-data`。
- 图片字段名是 `file`，不是 JSON 字段。
- 移动端代码使用 FormData 上传图片时，建议让 HTTP 客户端自动生成 `Content-Type` 和 boundary。
- 不要手动拼接 base64，也不要手动固定 boundary。
- 单图识别成功后，请把响应中的 `record_id` 写入 Postman 变量，再请求记录详情、记录建议、知识上下文和自由问答接口。
- `model_class` 不要写死为 UAV 类别；移动端应优先使用识别结果中的 `class_code` / `class_name` / `label`，或使用后端返回的 `disease_id` 映射结果。

## 5. LLM 问答能力状态

稳定性：`preview`（预览）

```bash
curl -s "$BASE_URL/api/agent/llm-status" \
  -H "Authorization: Bearer $TOKEN"
```

前端处理建议：该接口只判断智能问答能力，不生成回答。LLM 不可用时，识别结果仍应正常展示。

## 6. 知识库检索

稳定性：`preview`（预览）

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

## 7. 知识上下文

稳定性：`preview`（预览）

```bash
curl -s -X POST "$BASE_URL/api/agent/knowledge-context" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "为什么识别结果提示可能是白叶枯？",
    "record_id": "rec_001",
    "model_class": "bacterial_leaf_blight",
    "confidence": 0.78,
    "source_type": "phone_rgb",
    "top_k": 5
  }'
```

前端处理建议：用于展示回答依据、知识图谱实体和三元组，始终展示 `safety_notice`。

## 8. 自由问答

稳定性：`preview`（预览）

```bash
curl -s -X POST "$BASE_URL/api/agent/diagnosis-report" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "record_id": "rec_001",
    "model_class": "bacterial_leaf_blight",
    "confidence": 0.78,
    "source_type": "phone_rgb",
    "user_question": "这个结果能不能直接作为用药依据？"
  }'
```

前端处理建议：快捷问题只能填充输入框，不要写死答案；回答必须展示安全边界。

## 9. 快速验收

| 项 | 通过标准 |
|---|---|
| healthz | 返回 `status=ok` |
| models/status | 能看到模型阶段和安全边界字段 |
| detect/image | 返回 `record_id`、`summary`、`image_url` 或 `result_image_url` |
| agent/llm-status | 返回 LLM 配置和 fallback 状态 |
| knowledge/search | 返回知识库片段 |
| agent/knowledge-context | 返回知识片段、图谱实体/关系/三元组和安全提示 |
| agent/diagnosis-report | 支持 `user_question` 自由提问并返回辅助回答 |
