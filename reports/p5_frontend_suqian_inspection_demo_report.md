# P5 前端宿迁巡田演示联调报告

日期：2026-07-05

## 1. 本轮目标

在现有 `mark-video-demo` 前端中增量接入主后端 P1-P4 闭环，形成一个可演示的“宿迁小型水稻田无人机-手机协同巡检流程”页面。

本阶段不重建前端项目，不改造无关页面，不破坏主后端已有接口。

## 2. 修改文件列表

前端新增：

- `mark-video-demo/frontend/src/types/suqianInspection.ts`
- `mark-video-demo/frontend/src/services/suqianInspection.ts`
- `mark-video-demo/frontend/src/pages/SuqianInspectionDemo.tsx`
- `mark-video-demo/frontend/src/vite-env.d.ts`

前端修改：

- `mark-video-demo/frontend/src/app/App.tsx`
- `mark-video-demo/frontend/src/layout/AppShell.tsx`

验证脚本新增：

- `mark-video-demo/scripts/verify_p5_frontend_backend_contract.py`

报告新增：

- `reports/p5_frontend_suqian_inspection_demo_report.md`

## 3. 新增页面 / API Client

新增页面：

- 页面名：`SuqianInspectionDemo`
- 导航入口：`宿迁巡田`

页面按 6 个卡片展示：

1. 田块信息。
2. UAV dry-run 任务。
3. 多光谱指数。
4. 异常区域。
5. 手机复查。
6. 巡检报告。

新增 API client：

- `suqianInspectionApi`
- 默认主后端地址：`http://127.0.0.1:8000/api`
- 可通过 `VITE_MAIN_BACKEND_API_BASE` 覆盖。

原 `mark-video-demo` 的 `api.ts` 未改动，Dashboard、智能检测、历史记录、AI 助手、系统管理仍沿用原演示后端接口。

## 4. 对接的后端接口

实际使用接口：

Fields：

- `GET /api/fields`
- `POST /api/fields`
- `PUT /api/fields/{field_id}`

UAV：

- `POST /api/uav/tasks`
- `POST /api/uav/tasks/{uav_task_id}/dry-run`
- `GET /api/uav/tasks/{uav_task_id}/abnormal-regions`
- `GET /api/uav/abnormal-regions/{region_id}`

Phone follow-up：

- `POST /api/uav/abnormal-regions/{region_id}/phone-followup`

Inspection reports：

- `POST /api/inspection-reports/generate`
- `GET /api/inspection-reports/{report_id}`

## 5. 演示流程说明

页面支持从前端按顺序执行：

1. 获取或创建默认田块 `SQ_FIELD_001 / 宿迁一号田`。
2. 创建 UAV dry-run 任务。
3. 执行 dry-run，生成 NDVI / NDRE 占位指数和异常区域。
4. 选择异常区域。
5. 生成一张浏览器内存中的 PNG 演示图，并通过 phone-followup 接口上传。
6. 查询异常区域详情，展示 `linked_phone_image_id`、`confirmed_disease_type`、`confirm_status` 和 `phone_inference`。
7. 生成巡检报告。
8. 查询并展示报告摘要、风险评分、RAG 建议和模型安全说明。

页面包含醒目安全提示：

```text
当前系统处于 Mock / smoke / experimental 演示阶段，结果仅用于病虫害识别辅助与系统演示，不替代农技人员现场诊断，不作为农药处方依据。
```

## 6. 命令行验证方式

新增命令行验证脚本：

```powershell
cd F:\学校\病虫害识别\mark-video-demo
..\agri_uav_disease_system\backend\.venv\Scripts\python.exe .\scripts\verify_p5_frontend_backend_contract.py
```

脚本使用主后端 FastAPI `TestClient` 验证：

- 创建田块。
- 查询田块列表。
- 创建 UAV dry-run 任务。
- 生成 NDVI / NDRE 结果。
- 生成异常区域。
- 手机复查绑定 `abnormal_region`。
- `abnormal_region` 被回写。
- 生成 `inspection_report`。
- 查询报告详情。
- 校验安全说明存在。

验证结果：

```text
[PASS] create field
[PASS] list fields
[PASS] create uav task
[PASS] run uav dry-run
[PASS] list abnormal regions
[PASS] phone followup
[PASS] get abnormal region detail
[PASS] generate inspection report
[PASS] get inspection report detail
```

## 7. 构建结果

前端构建命令：

```powershell
cd F:\学校\病虫害识别\mark-video-demo\frontend
npm.cmd run build
```

结果：

```text
PASS
tsc -b: PASS
vite build: PASS
```

说明：

- `package.json` 当前没有 `lint` 脚本。
- `package.json` 当前没有 `test` 脚本。

## 8. 后端回归结果

主后端验证命令：

```powershell
cd F:\学校\病虫害识别\agri_uav_disease_system\backend
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

## 9. 未完成事项

本阶段仍未实现：

- 真实无人机 SDK。
- 真实地图 API。
- 真实天气 API。
- 真实多光谱生产级处理。
- 前端 PDF 导出。
- 前端自动化浏览器测试。
- 正式农业生产级模型验证。

## 10. 安全口径说明

本阶段未打开浏览器进行测试。

本阶段未使用 Selenium / Playwright / Chrome / Edge / Firefox 做测试。

本阶段通过命令行构建、接口自检、pytest 和 system_smoke_test 验证。

本阶段未接真实无人机 SDK。

本阶段未接真实地图 API。

本阶段未接真实天气 API。

本阶段不声明正式农业生产级诊断能力。

本阶段不生成农药处方、农药剂量或强制性治疗方案。

Mock / smoke / experimental 安全口径已保留。

## 11. 下一阶段建议

建议 P6 继续做：

1. 将宿迁巡田页面的报告展示拆成更适合答辩录屏的报告详情视图。
2. 增加报告历史列表入口。
3. 增加前端对主后端服务不可用时的更细分错误提示。
4. 在不使用浏览器自动化的前提下，为 API client 增加轻量单元测试或类型契约测试。
5. 等真实素材准备好后，替换 dry-run 占位指数图和手机复查演示图。
