# P-Frontend-2 协同巡检页面骨架整理报告

## 1. 本轮目标

本轮目标是整理协同巡检主页面的信息架构和布局骨架，让用户进入页面后能明确看到：

- 当前田块；
- 当前 UAV dry-run 任务；
- UAV 指数分析与异常区域；
- 当前选中的异常区域；
- 手机近景复查入口与回写字段；
- experimental 风险融合 / RAG 建议入口；
- 巡检报告闭环与历史归档；
- smoke / mock / experimental / real / dry-run 等能力边界。

本轮不修改后端接口，不新增后端能力，不重写全站路由，也不强行重做完整手机复查、风险融合、报告生成闭环。

## 2. 修改文件列表

- `src/pages/suqian/SuqianInspectionWorkbench.tsx`
- `src/pages/suqian/SuqianInspectionPanels.tsx`
- `src/components/inspection/InspectionWorkflowLayout.tsx`
- `src/components/inspection/InspectionStepTimeline.tsx`
- `src/components/inspection/InspectionActionPanel.tsx`
- `src/components/inspection/AbnormalRegionList.tsx`
- `src/components/inspection/AbnormalRegionDetail.tsx`
- `src/components/inspection/index.ts`
- `docs/p_frontend_2_inspection_skeleton_report.md`

## 3. 新增组件列表

### `InspectionWorkflowLayout`

协同巡检页面的主布局容器。

用于固定：

- 左侧 / 中间主工作区；
- 右侧上下文详情面板；
- 页面底部错误态。

### `InspectionStepTimeline`

新的巡检流程状态条。

当前展示 6 个阶段：

- 田块；
- UAV 任务；
- 异常区；
- 手机复查；
- 风险融合；
- 巡检报告。

状态标签复用 `StatusBadge`，包含：

- 已完成；
- 进行中；
- 待处理；
- 有异常。

### `InspectionActionPanel`

协同巡检关键入口卡片。

当前包括：

- 手机近景复查；
- 风险融合 / RAG；
- 巡检报告闭环。

本轮只做入口与状态表达，不新增复杂流程。

### `AbnormalRegionList`

异常区域列表组件。

展示：

- 区域名称；
- 风险等级；
- 来源指数；
- 复查状态；
- 回写记录；
- 疑似病害。

风险等级复用 `RiskLevelBadge`，状态复用 `StatusBadge`。

### `AbnormalRegionDetail`

当前选中异常区详情组件。

展示：

- 区域编号；
- 异常类型；
- 异常面积；
- `linked_phone_image_id`；
- `linked_record_id`；
- `confirmed_disease_type`；
- `confirm_status`。

无选中区域时使用 P1 的 `EmptyState`。

## 4. 协同巡检页面入口说明

页面入口未改变。

仍通过现有 `activePage` 页面切换进入：

- `AppShell` 中的“协同巡检”；
- `DashboardPage` 中的“开始一次巡检”；
- `App.tsx` 中 `suqian: <SuqianInspectionDemo />`；
- `SuqianInspectionDemo` 继续渲染 `SuqianInspectionWorkbench`。

本轮没有新增路由库，也没有创建平行的新协同巡检页面。

## 5. 已接入 API

保留并继续使用现有协同巡检 API：

- `GET /api/fields?status=active&page=1&page_size=100`
- `POST /api/fields`
- `POST /api/uav/tasks`
- `POST /api/uav/tasks/{uav_task_id}/dry-run`
- `GET /api/uav/tasks/{uav_task_id}/abnormal-regions`
- `GET /api/uav/abnormal-regions/{region_id}`
- `POST /api/uav/abnormal-regions/{region_id}/phone-followup`
- `POST /api/inspection-reports/generate`
- `GET /api/inspection-reports/{report_id}`
- `GET /api/inspection-reports?field_id={field_id}`

本轮新增低风险只读状态接入：

- `GET /api/models/status`
- `GET /api/models/demo-safety`

这些只读接口用于在协同巡检页显示当前 detector mode 与 demo safety，不改变原业务链路。

## 6. EmptyState 使用情况

以下场景使用了 P1 的 `EmptyState` 或继续保持统一空态：

- 尚未执行 dry-run 时，指数区域为空；
- UAV dry-run 尚未生成异常区域时，异常区列表为空；
- 未选择异常区时，异常区详情为空；
- 手机复查尚未完成时，复查摘要为空；
- 报告尚未生成时，报告详情为空；
- 报告历史为空时，报告历史区域为空；
- 多源风险详情为空时，风险分析区为空。

## 7. ErrorState 使用情况

以下场景接入 P1 的 `ErrorState`：

- 主后端连接或协同巡检操作失败；
- `/api/models/status` 或 `/api/models/demo-safety` 加载失败；
- `storage_status` 等错误仍由 P1 的 `ErrorState` 做中文友好转换。

## 8. P-Frontend-1 组件复用情况

本轮复用了：

- `StatusBadge`
- `RiskLevelBadge`
- `ModelSafetyNotice`
- `EmptyState`
- `ErrorState`

协同巡检页不再为新增骨架重复编写新的状态 badge、风险 badge、错误态或安全边界组件。

## 9. 安全边界覆盖情况

页面顶部安全边界继续保留一行可展开结构。

展开后使用 `ModelSafetyNotice` 展示模型状态边界，并补充 `/api/models/demo-safety` 返回的 warnings。

当前覆盖：

- mock：模拟结果，仅用于界面演示和流程联调；
- smoke：烟测模型，仅用于验证识别链路；
- experimental：实验能力，需人工复核，不作为正式农艺诊断或用药依据；
- real：模型推理结果，仍建议结合人工巡检和田间情况复核；
- dry-run：流程验证，不代表真实遥感反演结论。

已扫描源码，未发现以下夸大表述：

- 精准诊断；
- 自动确诊；
- 直接给出处方；
- 保证识别准确；
- 完全替代人工巡检。

## 10. 构建结果

已在 `F:\学校\病虫害识别\mark-video-demo\frontend` 执行：

```bash
npm.cmd run build
```

结果：

```text
tsc -b && vite build
✓ built in 2.15s
```

构建通过。

## 11. Lint 结果

当前 `package.json` 未提供 `lint` 脚本。

本轮未新增 lint 配置，避免引入额外工程变更。

## 12. 未完成项

- `InspectionContextPanel` 仍主要沿用现有实现，P3 可继续深化为更智能的上下文切换面板；
- `FieldTaskSelector` 尚未独立抽出，当前田块与 UAV 任务仍由 `FieldTaskPanel` 承担；
- 风险融合入口已展示，但本轮没有新增复杂交互；
- 手机复查和报告生成沿用既有流程，本轮没有重做上传、融合、报告闭环逻辑；
- 未做浏览器自动化验收，按用户要求避免连接浏览器。

## 13. 下一步建议

进入 `P-Frontend-3：InspectionContextPanel 深化接入`。

建议重点：

- 将右侧上下文面板从“固定信息块”升级为“根据当前选中田块 / UAV 任务 / 异常区 / 复查记录 / 报告自动切换重点”；
- 增强上下文面板的下一步推荐；
- 把 `selectedFieldId`、`selectedUavTaskId`、`selectedAnomalyRegionId`、`selectedFollowupRecordId`、`selectedReportId` 的状态表达整理清楚；
- 继续保持 API 不变和安全边界文案一致。

## 14. 最终结论

`P-Frontend-2: PASS`
