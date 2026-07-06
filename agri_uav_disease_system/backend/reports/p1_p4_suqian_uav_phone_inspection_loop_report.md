# P1-P4 宿迁 UAV-手机协同巡检闭环实施报告

日期：2026-07-05

## 1. 阶段结论

已在现有主后端上增量补齐 P1-P4 最小业务闭环：

```text
宿迁田块建档
  -> UAV 多光谱 dry-run 任务
  -> NDVI / NDRE 占位指数结果
  -> 异常区域生成
  -> 手机近景复查绑定
  -> 异常区域回写
  -> 巡检报告 JSON 输出
```

本次实现未重建系统，未删除既有 Mock/smoke/experimental 安全口径，原有 `system_smoke_test` 和完整 pytest 均通过。

## 2. 新增能力

### P1 田块建档

新增表：

- `field_info`

新增接口：

- `POST /api/fields`
- `GET /api/fields`
- `GET /api/fields/{field_id}`
- `PUT /api/fields/{field_id}`
- `DELETE /api/fields/{field_id}`

说明：

- `DELETE` 当前为归档语义，将 `field_status` 更新为 `archived`。
- 检测接口新增可选 `field_id`。
- 若传入 `field_id` 但不传 `plot_id`，系统会将 `plot_id` 兼容设置为 `field_id`，保证大屏、移动端和预测模块仍能复用旧聚合逻辑。

### P2 UAV dry-run 与异常区域

新增表：

- `uav_tasks`
- `uav_images`
- `uav_index_results`
- `abnormal_regions`

新增接口：

- `POST /api/uav/tasks`
- `GET /api/uav/tasks`
- `GET /api/uav/tasks/{uav_task_id}`
- `POST /api/uav/tasks/{uav_task_id}/dry-run`
- `GET /api/uav/tasks/{uav_task_id}/indices`
- `GET /api/uav/tasks/{uav_task_id}/abnormal-regions`
- `GET /api/uav/abnormal-regions/{region_id}`

说明：

- dry-run 会生成 NDVI / NDRE 占位指数图。
- dry-run 会生成至少一个 `abnormal_region`。
- 返回中明确包含 `data_mode=dry_run`、`is_mock=true` 和安全说明。
- 当前不声称真实多光谱生产结果，不生成正式 IoU/mAP 指标。

### P3 手机复查绑定与回写

检测接口新增可选字段：

- `field_id`
- `uav_task_id`
- `abnormal_region_id`
- `source_type=phone_followup`

新增业务接口：

- `POST /api/uav/abnormal-regions/{region_id}/phone-followup`

说明：

- 手机复查接口复用现有检测服务。
- 检测完成后自动回写 `abnormal_regions`。
- 支持状态：`phone_confirmed`、`phone_uncertain`、`phone_rejected`。
- 异常区域详情会返回 `phone_inference` 摘要。
- 未绑定异常区域的普通手机识别仍保持原流程。

### P4 巡检报告

新增表：

- `inspection_reports`

新增接口：

- `POST /api/inspection-reports/generate`
- `GET /api/inspection-reports/{report_id}`
- `GET /api/inspection-reports?field_id=...`

报告内容：

- 田块信息。
- UAV 任务摘要。
- NDVI / NDRE 指数结果。
- 异常区域列表。
- 手机复查结果。
- 规则风险评分。
- RAG 检索建议。
- 模型安全说明。

固定安全说明：

```text
本报告由系统根据无人机图像、手机近景识别结果、规则风险评分和知识库检索结果自动生成，仅作为病虫害巡检与治理辅助参考，不替代农技人员现场诊断，不作为农药处方依据。
```

## 3. 验收结果

已新增测试：

- `test_detect_image_with_field_id_keeps_old_plot_compatibility`
- `test_p1_field_crud_and_p2_p3_p4_inspection_loop`
- `test_normal_phone_detect_still_works_without_abnormal_region`

验收命令：

```powershell
.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe -m pytest app\tests -q
.\.venv\Scripts\python.exe -m app.scripts.system_smoke_test
```

结果：

```text
compileall: PASS
pytest: 64 passed, 15 skipped, 1 warning
system_smoke_test: PASS
```

## 4. 明确边界

本阶段仍不做：

- 真实无人机 SDK。
- 正射影像拼接。
- 真实多光谱标定。
- 生产级多光谱分割模型。
- 正式 Precision / Recall / mAP / IoU。
- 专家签字报告。
- 农药处方或剂量建议。
- PDF 报告模板。

当前实现是工程闭环和答辩演示基线，不是正式农业诊断产品。
