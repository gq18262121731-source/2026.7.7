# 错误响应与错误码

## 统一错误结构

所有对外接口建议统一使用：

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

当前演示环境部分 FastAPI 默认错误可能仍是 `detail` 结构。对外部署时建议统一转换为上面的结构。

## 错误码表

| 错误码 | HTTP 状态 | 含义 | 前端展示建议 |
|---|---:|---|---|
| `INVALID_IMAGE` | 400 | 图片格式不支持、损坏或无法解析 | “图片无法识别，请更换清晰图片后重试。” |
| `FILE_TOO_LARGE` | 413 | 上传文件超过大小限制 | “图片过大，请压缩后重新上传。” |
| `MODEL_ERROR` | 500 | 模型推理或 dry-run 分析失败 | “模型处理失败，请稍后重试或联系管理员。” |
| `STORAGE_ERROR` | 500 | 原图、结果图或静态目录写入失败 | “存储状态异常，请检查上传目录或静态资源配置。” |
| `RECORD_NOT_FOUND` | 404 | 记录、地块、任务、异常区或报告不存在 | “数据不存在或已被清理。” |
| `DISEASE_NOT_FOUND` | 404 | 病害 ID 不存在或未纳入知识库 | “暂未找到该病害知识，请更换问题或人工复核。” |
| `KNOWLEDGE_CONTEXT_NOT_FOUND` | 404 | 未检索到足够知识库或知识图谱依据 | “当前知识依据不足，请补充识别结果或人工复核。” |
| `KNOWLEDGE_DATA_ERROR` | 500 | 知识库、知识图谱文件读取或解析失败 | “知识库暂不可用，请稍后重试。” |
| `LLM_API_ERROR` | 502 | LLM 服务调用失败、超时或返回不可解析 | “AI 问答服务暂不可用，请稍后重试。” |
| `DATABASE_ERROR` | 500 | 数据库访问失败 | “数据库访问失败，请稍后重试。” |
| `VALIDATION_ERROR` | 422 | 请求参数校验失败 | “请求参数不完整或格式错误。” |
| `ALERT_NOT_FOUND` | 404 | 告警不存在 | “告警不存在或已被处理。” |
| `UNAUTHORIZED` | 401 | Token 缺失或无效 | “登录状态失效，请重新登录。” |
| `FORBIDDEN` | 403 | 权限不足 | “当前账号无权执行该操作。” |
| `INTERNAL_ERROR` | 500 | 服务端内部错误 | “服务端异常，请稍后重试。” |

## 前端处理原则

- 不要直接裸显示英文异常栈。
- 404 类错误展示空态或返回上一级。
- 上传错误要区分图片问题、大小问题、存储问题。
- `MODEL_ERROR` 不等于用户图片一定无效。
- `STORAGE_ERROR` 可能影响图片展示，但不必包装为模型失败。
- `KNOWLEDGE_CONTEXT_NOT_FOUND` 和 `KNOWLEDGE_DATA_ERROR` 只表示知识依据不可用，不等于识别结果无效。
- `LLM_API_ERROR` 发生时应保留已有识别结果和知识检索结果，不要伪装为真实 AI 回答。
- `mock`、`smoke`、`experimental` 不是错误码，是能力阶段，必须单独展示安全边界。

## 示例：参数错误

```json
{
  "success": false,
  "error_code": "VALIDATION_ERROR",
  "message": "请求参数校验失败",
  "detail": {
    "errors": [
      {
        "field": "file",
        "reason": "缺少上传文件"
      }
    ]
  }
}
```

## 示例：存储错误

```json
{
  "success": false,
  "error_code": "STORAGE_ERROR",
  "message": "结果图保存失败",
  "detail": {
    "path": "/static/results"
  }
}
```

## 示例：记录不存在

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
