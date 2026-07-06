# Batch Queue Upgrade Plan

当前批量任务使用 FastAPI `BackgroundTasks`，适合 MVP 演示和小规模联调。本轮不引入 Celery、RQ 或其他队列系统，只记录后续升级计划。

## 当前边界

- 任务在当前 Web 进程内执行。
- 服务重启后，正在处理的任务不会自动恢复。
- 多进程部署时，任务状态和执行进程之间缺少统一调度。
- 失败重试策略较轻，只适合演示闭环。
- 长任务会受到 Web 进程生命周期影响。

## 为什么需要持久化队列

后续接真实模型和无人机采集后，批量图片数量、推理耗时和失败场景都会增加。持久化队列可以提供：

- 任务可恢复。
- worker 独立扩展。
- 失败重试。
- 超时控制。
- 任务优先级。
- 更稳定的进度上报。

可选方案：

- Celery + Redis/RabbitMQ
- RQ + Redis
- Dramatiq + Redis/RabbitMQ
- 数据库轮询 worker

## 任务表建议保留字段

当前 `batch_tasks` 表已有字段可继续保留：

- `task_id`
- `task_type`
- `status`
- `total_images`
- `processed_images`
- `failed_images`
- `progress`
- `record_ids_json`
- `failed_items_json`
- `created_at`
- `updated_at`

后续建议增加：

- `queue_name`
- `worker_id`
- `retry_count`
- `max_retries`
- `started_at`
- `finished_at`
- `last_error`
- `source_type`
- `operator_id`
- `priority`

## 失败图片重试

建议把每张图片拆成子任务或任务明细表：

- `item_id`
- `task_id`
- `filename`
- `status`
- `record_id`
- `error_code`
- `error_message`
- `retry_count`
- `created_at`
- `updated_at`

重试规则：

- 图片校验失败不重试。
- 存储临时失败可重试。
- 模型推理临时失败可重试。
- 达到最大重试次数后写入 `failed_items_json` 或明细表。

## 服务重启恢复

服务启动或 worker 启动时：

1. 查询 `pending` 任务并重新入队。
2. 查询长时间停留在 `processing` 的任务。
3. 根据 `updated_at` 判断是否为异常中断。
4. 将可恢复任务改回 `pending` 或 `retrying`。
5. 将不可恢复任务标记为 `failed` 并保留错误摘要。
6. 通过 `/ws/tasks` 推送最新状态；HTTP `GET /api/tasks/{task_id}` 仍作为兜底。

## 本轮不实现项

- 不引入 Celery/RQ。
- 不启动外部 Redis/RabbitMQ。
- 不改变现有批量接口契约。
- 不训练模型。
- 不接真实无人机或视频流。

第五阶段只把设计文档补齐，确保后续工程升级有清晰路径。
