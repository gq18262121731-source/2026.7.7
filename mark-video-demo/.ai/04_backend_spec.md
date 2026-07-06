# Backend Specification

后端使用 FastAPI，默认提供 Mock Backend，保证前端有完整 API 链路。

## API 前缀

所有接口使用：

```text
/api
```

## 必须提供的接口

### GET /api/health

返回系统健康状态。

响应字段：

- `status`
- `version`
- `mode`
- `timestamp`

### GET /api/models

返回模型列表和当前模型状态。

响应字段：

- `models`
- `active_model`
- `status`
- `last_updated`

### POST /api/detect

创建检测任务。

请求支持：

- 图片文件
- 视频文件
- 示例素材 ID
- 参数配置

响应字段：

- `task_id`
- `status`
- `result`
- `suggestions`
- `confidence`
- `created_at`

Demo 阶段可直接返回 Mock 检测结果。

### GET /api/tasks/{task_id}

查询检测任务状态。

响应字段：

- `task_id`
- `status`
- `progress`
- `result`
- `error`

### GET /api/history

返回历史记录。

支持查询参数：

- `keyword`
- `status`
- `type`
- `date_from`
- `date_to`

### GET /api/history/{record_id}

返回单条历史详情。

### POST /api/assistant

AI 助手问答。

请求字段：

- `message`
- `mode`
- `context`

响应字段：

- `answer`
- `sources`
- `mode`
- `confidence`

### GET /api/settings

返回系统设置。

### POST /api/settings

保存系统设置。

### POST /api/make/trigger

触发 Make 自动化流程。

### GET /api/make/status

返回自动化流程状态。

## 错误格式

所有错误响应必须统一：

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "detail": {}
  }
}
```

## Mock 数据原则

Mock 数据集中放在后端 `mock_data/`。

禁止前端页面直接写死 Mock 数据。

后续替换真实 YOLO、数据库、LLM 时，应只修改后端 service 和 repository。
