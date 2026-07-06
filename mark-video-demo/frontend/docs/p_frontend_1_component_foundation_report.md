# P-Frontend-1 基础文案与共享状态组件改造报告

## 1. 本轮目标

本轮目标是完成前端基础状态组件与安全边界文案的统一，不改后端接口、不重写路由、不重构协同巡检主链路。

重点覆盖：

- 中文文案与终端编码口径确认；
- mock / smoke / experimental / real / dry-run 等能力状态统一展示；
- normal / low / medium / high 等风险等级统一展示；
- 模型结果、风险结果、RAG/LLM 建议的安全边界统一表达；
- 加载、错误、空状态的基础组件沉淀；
- 对低风险页面进行轻量接入验证。

## 2. 修改文件列表

- `src/components/common/StatusBadge.tsx`
- `src/components/common/RiskLevelBadge.tsx`
- `src/components/common/ModelSafetyNotice.tsx`
- `src/components/common/LoadingState.tsx`
- `src/components/common/ErrorState.tsx`
- `src/components/common/EmptyState.tsx`
- `src/components/common/index.ts`
- `src/pages/SettingsPage.tsx`
- `src/pages/DashboardPage.tsx`
- `src/pages/HistoryPage.tsx`
- `src/pages/AlertsPage.tsx`
- `docs/frontend-design-integration-plan.md`
- `docs/dev_startup_runbook.md`
- `docs/p_frontend_1_component_foundation_report.md`

## 3. 新增组件列表

### `StatusBadge`

用于统一展示模型、接口和能力阶段状态。

当前支持并归一化：

- `real`
- `mock`
- `smoke`
- `experimental`
- `preview`
- `stable`
- `error`
- `unknown`
- `dry-run`
- `ready`
- `unavailable`
- `fallback`
- `mock_fallback`

### `RiskLevelBadge`

用于统一展示风险等级。

当前支持并归一化：

- `normal`：正常
- `low`：低风险
- `medium`：中风险
- `high`：高风险
- `unknown`：未知

同时兼容中文风险字段，如“高风险”“中风险”“低风险”“正常”。

### `ModelSafetyNotice`

用于统一展示模型与结果安全边界。

当前口径：

- mock：当前为模拟结果，仅用于界面演示和流程联调。
- smoke：当前为烟测模型，仅用于验证识别链路，不代表正式识别效果。
- experimental：当前为实验能力，结果需人工复核，不作为正式农艺诊断或用药依据。
- real：当前为模型推理结果，仍建议结合人工巡检和田间情况复核。
- dry-run：当前为 dry-run 演示结果，仅用于流程验证，不代表真实遥感反演结论。

### `LoadingState`

统一加载态，用于替代零散的“加载中”文本。

### `ErrorState`

统一错误态，用于接口失败、主后端未连接、存储状态异常等场景。

对 `storage_status error`、`static_original`、`static_result`、`storage` 等错误信息会转换为用户可理解的中文提示：

> 存储状态异常，请检查后端静态资源目录或上传目录配置。该问题可能影响图片上传和结果图生成，但不代表模型推理能力失败。

### `EmptyState`

统一空状态，用于无记录、无告警、无异常区、无报告等场景。

## 4. 已轻量接入页面

### 系统配置页 `SettingsPage`

- 主后端状态接入 `StatusBadge`；
- 系统状态加载中接入 `LoadingState`；
- 存储异常接入 `ErrorState`；
- 模型路线卡片接入 `StatusBadge` 和 `ModelSafetyNotice`；
- 诊断与安全边界区域接入 `ModelSafetyNotice`；
- 保留能力开关原展示方式，未改变接口字段。

### 工作台首页 `DashboardPage`

- 近期识别记录风险列接入 `RiskLevelBadge`；
- 模型阶段列接入 `StatusBadge`；
- 数据加载失败接入 `ErrorState`；
- 系统边界区域补充 `ModelSafetyNotice`；
- 页面导航、API 调用和业务入口未改变。

### 记录中心 `HistoryPage`

- 记录表格风险列接入 `RiskLevelBadge`；
- 模型阶段列接入 `StatusBadge`；
- 记录加载失败接入 `ErrorState`；
- 记录详情补充 `ModelSafetyNotice`；
- 记录选择、检测图展示、详情字段未改变。

### 预警中心 `AlertsPage`

- 预警风险列接入 `RiskLevelBadge`；
- 处理状态列接入 `StatusBadge`；
- 预警接口错误接入 `ErrorState`；
- 预警处理流程和接口未改变。

## 5. 中文文案修复情况

- 已确认 `src` 目录未发现典型 mojibake 乱码特征。
- 已确认源码按 UTF-8 读取时中文显示正常。
- 已在启动手册中记录：PowerShell 若出现中文乱码，优先检查终端编码，不直接判断为文件损坏。
- 本轮新增组件和页面接入文案均使用中文，并避免裸露英文错误给最终用户。

## 6. `storage_status error` 前端展示处理

本轮不修改后端存储逻辑，只统一前端展示口径。

处理方式：

- `SettingsPage` 中当 `storage_status !== "ok"` 时显示“存储状态异常”；
- `ErrorState` 会将 storage 相关英文/字段错误转换为中文说明；
- 保留原字段 `storage_status`、`static_original_writable`、`static_result_writable` 的只读展示，便于开发排查。

## 7. 构建结果

已在 `F:\学校\病虫害识别\mark-video-demo\frontend` 执行：

```bash
npm.cmd run build
```

结果：

```text
tsc -b && vite build
✓ built in 3.11s
```

构建通过。

## 8. Lint 结果

当前 `package.json` 未提供 `lint` 脚本。

本轮未新增 lint 配置，避免引入额外工程变更。

## 9. 未完成项

- 协同巡检页面尚未进行 Tab 化和 `InspectionContextPanel` 骨架整理；
- `DetectPage`、`AssistantPage`、`PredictionPage` 等页面仍可继续接入共享组件；
- 大屏和移动端未进入本轮范围；
- `storage_status error` 的后端根因仍需在后续联调中排查静态目录、上传目录或权限配置。

## 10. 下一步建议

进入 `P-Frontend-2：协同巡检页面骨架整理`。

建议只做页面结构拆分，不改业务链路：

- 新增 `activeTab`；
- 保留现有 state 和 API 调用；
- 将协同巡检页面改为“总览 / UAV 异常 / 手机复查 / 报告中心”四个工作区；
- 初步接入 `InspectionContextPanel`；
- 保持 dry-run、experimental、RAG/LLM 的安全边界文案。

## 11. 最终结论

`P-Frontend-1: PASS`
