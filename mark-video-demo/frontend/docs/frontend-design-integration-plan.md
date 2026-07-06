# 前端设计整合文档

本文档用于统一“水稻病虫害识别系统”前端后续改造方向。目标不是继续堆概念，而是把已有后端能力整理成用户能理解、能操作、能验证、能答辩展示的产品化工作台。

## 1. 产品定位

系统面向农业巡检、比赛答辩和小型示范场景，核心价值是展示一条多源协同证据链：

```text
田块建档
-> UAV 任务
-> UAV dry-run 指数分析
-> 异常区域
-> 手机近景复查
-> 检测结果回写
-> experimental 风险融合 / RAG 建议
-> 巡检报告闭环
```

前端应让用户清楚知道四件事：

```text
1. 当前巡检到哪一步了
2. 下一步该做什么
3. 当前选中的田块 / UAV 任务 / 异常区域 / 报告是什么
4. 最终是否形成了可信的闭环证据
```

## 2. 设计原则

### 2.1 不做普通后台模板

页面应有农业科技系统的气质，但不能做成花哨大屏。建议风格：

- 背景：浅灰绿或低饱和深色农业科技背景，避免纯黑和过重渐变。
- 卡片：白色或深色 surface，轻边框，8px 圆角，轻阴影。
- 主色：农业绿色。
- 辅色：cyan 用于信息和流程，amber 用于风险提示，red 用于高风险。
- 信息密度：面向真实操作，重点内容优先，不做营销页或展示页。

### 2.2 设计工具只做参考

Figma / Build Web / v0 / Builder 等工具只用于：

```text
设计参考
静态原型
布局方案
视觉样式
组件形态
```

不能直接替换真实前端业务代码。真实融合必须保留：

```text
现有 API
现有 state
field_id / uav_task_id / abnormal_region_id 绑定
UAV dry-run 逻辑
手机复查回写逻辑
报告生成与历史查询逻辑
smoke / experimental / dry-run 安全边界
TypeScript 类型安全
```

## 3. 页面总体信息架构

当前前端页面保持单页应用内切换方式，不新增路由库。

建议页面结构：

```text
AppShell
├─ DashboardPage 工作台
├─ SuqianInspectionDemo 协同巡检
├─ DetectPage 图像检测
├─ BatchDetectPage 批量检测
├─ HistoryPage 记录中心
├─ AlertsPage 预警中心
├─ PredictionPage 风险预测
├─ AssistantPage 知识助手
└─ SettingsPage 系统状态
```

页面职责：

| 页面 | 核心问题 | 设计重点 |
| --- | --- | --- |
| 工作台 | 系统现在整体怎么样 | 摘要、最近风险、系统状态、入口 |
| 协同巡检 | 如何完成一次巡检闭环 | 流程、Tab、上下文、证据链 |
| 图像检测 | 单张图识别结果是什么 | 上传、结果图、检测框、风险建议 |
| 批量检测 | 多图任务跑到哪了 | 文件队列、任务状态、成功失败 |
| 记录中心 | 历史识别如何追溯 | 表格、筛选、详情 |
| 预警中心 | 哪些风险需要处理 | 告警列表、处置、动作记录 |
| 风险预测 | 哪个地块风险较高 | 规则评分、风险地图、解释 |
| 知识助手 | 如何用知识库辅助复核 | 场景问题、RAG 来源、LLM 边界 |
| 系统状态 | 当前能力是否可用 | 模型状态、后端状态、安全边界 |

## 4. 协同巡检页面设计

协同巡检是系统主展示页，应从“纵向功能堆叠”改成“任务工作台”。

### 4.1 页面结构

```text
[顶部安全边界提示，可展开]

[5 步流程状态条]
田块建档 -> UAV 任务 -> 异常发现 -> 手机复查 -> 报告闭环

[Tab]
总览 | UAV 异常 | 手机复查 | 报告中心

[主体]
左/中：当前 Tab 的主要操作区
右侧：InspectionContextPanel 当前上下文详情
```

### 4.2 流程状态条

流程条只负责“进度感”和快速跳转，不承载复杂详情。

状态建议：

```text
未开始
进行中
已完成
有异常
跳过
```

当前 5 步：

```text
田块建档
UAV 任务
异常发现
手机复查
报告闭环
```

### 4.3 Tab 职责

| Tab | 回答的问题 | 内容边界 |
| --- | --- | --- |
| 总览 | 这次巡检现在怎么样 | 只展示摘要和下一步建议 |
| UAV 异常 | 哪里异常 | UAV 任务、指数摘要、异常区域列表 |
| 手机复查 | 异常是不是真的 | 选择异常区域、上传/模拟复查、识别结果、回写字段 |
| 报告中心 | 最终怎么归档 | 证据完整度、报告生成、最新报告、历史和详情 |

### 4.4 总览 Tab

总览不要成为第二个流水账。只放：

```text
当前巡检状态
田块摘要
UAV 任务摘要
异常区域摘要
手机复查摘要
最新报告摘要
下一步建议
```

示例文案：

```text
当前状态：已发现 3 个异常区域，1 个已完成手机复查，报告尚未生成。

下一步：请选择剩余异常区域进行手机复查，或基于当前证据生成实验性巡检报告。
```

### 4.5 UAV 异常 Tab

建议布局：

```text
左侧：田块 / UAV 任务卡片
中间：NDVI / NDRE 指数摘要
下方或右侧：异常区域列表
右侧固定：InspectionContextPanel
```

异常区域卡片字段：

```text
区域编号
风险等级
异常类型
NDVI / NDRE 异常摘要
异常面积占比
复查状态
选择复查按钮
```

状态：

```text
待复查
已复查
已回写
风险中
风险高
dry-run
```

### 4.6 手机复查 Tab

手机复查必须是独立任务流，而不是报告生成前的一个按钮。

任务流：

```text
选择异常区域
-> 上传 / 模拟手机近景复查图
-> 查看手机识别结果
-> 查看回写字段
-> 进入报告中心
```

结果展示：

```text
UAV 判断：指数异常
手机复查：疑似白叶枯 / 未发现明显病害 / 识别不确定
融合结论：风险升高 / 风险降低 / 需要人工确认
```

回写字段：

```text
linked_phone_image_id
linked_record_id
confirmed_disease_type
confirm_status
confirm_confidence
```

### 4.7 报告中心 Tab

报告中心分三块：

```text
最新报告
报告生成
报告历史 / 详情
```

报告生成区展示当前证据完整度：

```text
UAV 任务：已完成
指数分析：已完成
异常区域：3 个
手机复查：1 / 3
风险融合：experimental / rule-weighted
RAG 建议：辅助建议
```

按钮文案：

```text
生成实验性巡检报告
```

安全文案：

```text
该报告为辅助巡检报告，不代表最终现场诊断结论，不输出农事处置方案。
```

### 4.8 InspectionContextPanel

右侧上下文面板必须保留。它是用户理解当前操作对象的认知锚点。

根据当前选中对象展示：

```text
田块详情
UAV 任务详情
选中异常区域详情
手机复查状态
报告摘要
下一步建议
```

示例结构：

```text
当前上下文详情
├─ 田块详情
├─ UAV 任务详情
├─ 选中异常区
├─ 手机复查
├─ 报告闭环
└─ 下一步建议
```

## 5. 共享 UI 组件

建议逐步统一以下组件，避免每个页面各写一套样式：

```text
PagePanel
SectionHeader
InfoRow
DataTable
EmptyState
ErrorNotice
StatusPill
RiskBadge
EvidenceCard
ReportSummaryCard
NextActionCard
SafetyBoundaryBanner
InspectionStepProgress
InspectionTabs
InspectionContextPanel
```

P-Frontend-1 优先落地组件：

| 组件 | 用途 |
| --- | --- |
| `StatusBadge` | 统一展示 `mock` / `smoke` / `experimental` / `real` / `dry-run` 等模型和流程状态 |
| `RiskLevelBadge` | 统一展示 `normal` / `low` / `medium` / `high` 或中文风险等级 |
| `ModelSafetyNotice` | 统一展示模型能力、安全边界、辅助判断口径 |
| `LoadingState` | 统一接口加载中状态 |
| `ErrorState` | 统一接口失败、主后端未连接、存储不可写等错误态 |
| `EmptyState` | 统一无记录、无告警、无异常区等空态 |
| `InspectionContextPanel` | 协同巡检右侧上下文面板 |

组件设计要求：

- 卡片圆角不超过 8px。
- 状态标签不换行挤压。
- 表格列宽稳定，长文本截断或换行。
- 空态、错误态、加载态必须明确。
- 按钮只承载清晰动作，不放解释性长文案。
- 涉及模型、风险、诊断、报告的组件必须显示 `mock` / `smoke` / `experimental` / `real` / `dry-run` 等边界状态。

## 6. API 映射

前端通用接口位于：

```text
src/services/api.ts
```

协同巡检专用接口位于：

```text
src/services/suqianInspection.ts
```

关键映射：

| 前端动作 | 后端接口 | 说明 |
| --- | --- | --- |
| 系统状态 | GET `/api/status` | 后端、模型、存储状态 |
| 模型状态 | GET `/api/models/status` | 模型路径、mock/fallback |
| 单图检测 | POST `/api/detect/image` | 手机或普通上传识别 |
| 批量检测 | POST `/api/detect/batch` | 后台批量任务 |
| 任务状态 | GET `/api/tasks/{task_id}` | 批量任务进度 |
| 记录列表 | GET `/api/records` | 历史识别记录 |
| 告警列表 | GET `/api/alerts` | 风险告警 |
| 处理告警 | POST `/api/alerts/{alert_id}/resolve` | 告警闭环 |
| 风险预测 | GET `/api/prediction/plots/{plot_id}` | 规则风险评分 |
| 知识助手 | POST `/api/agent/diagnosis-report` | LLM / RAG 辅助报告 |
| 田块列表 | GET `/api/fields` | 协同巡检田块 |
| 创建 UAV 任务 | POST `/api/uav/tasks` | 绑定 field_id |
| UAV dry-run | POST `/api/uav/tasks/{id}/dry-run` | 生成指数和异常区 |
| 异常区域 | GET `/api/uav/tasks/{id}/abnormal-regions` | 复查对象 |
| 手机复查 | POST `/api/uav/abnormal-regions/{id}/phone-followup` | 回写异常区域 |
| 生成报告 | POST `/api/inspection-reports/generate` | 巡检报告闭环 |
| 报告历史 | GET `/api/inspection-reports?field_id=...` | 报告留痕 |

## 7. 安全边界文案规范

所有相关页面必须保持一致的边界表达。

允许表达：

```text
辅助巡检
实验性
dry-run
experimental
rule-weighted
RAG / LLM 辅助建议
需要人工复核
不作为最终现场诊断依据
不输出农事处置方案
```

避免表达：

```text
正式诊断
正式发病概率
农药处方
剂量建议
真实遥感反演结论
自动给出处置结论
```

推荐统一文案：

```text
当前结果为辅助巡检结果。dry-run 指数、experimental 风险融合与 RAG / LLM 建议仅用于复核和演示，不代表最终现场诊断，不输出农事处置方案。
```

## 8. 当前已知问题

### 8.1 中文乱码

部分前端文件中存在中文文案乱码，主要影响：

```text
src/layout/AppShell.tsx
src/services/api.ts
src/services/suqianInspection.ts
```

处理原则：

```text
先修显示文案
不改接口路径
不改字段映射
不改业务逻辑
修完必须 npm run build
```

编码判断口径：

```text
源码、Markdown、接口文档统一使用 UTF-8。
PowerShell 若出现中文乱码，优先检查终端编码，不直接判断为文件损坏。
建议读取中文文件时使用：
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
Get-Content -Encoding UTF8
```

### 8.2 storage_status error

后端 `/api/status` 可能返回：

```text
storage_status: error
static_original_writable: false
static_result_writable: false
```

前端展示原则：

```text
清晰提示存储目录不可写
不阻断无关页面
上传/生成结果图失败时给出明确错误
不要把它解释为模型失败
```

后续排查方向：

```text
确认 settings.static_dir / original_dir / result_dir 是否存在
确认进程用户是否有写入权限
确认前端展示字段是否来自 /api/status.storage
确认上传失败时错误来自存储目录，而不是模型推理
```

### 8.3 原 `.venv` Python 路径失效

后端原 `.venv` 指向不存在的 Python 3.11。当前启动时可能需要临时 Python 环境。

这属于运行环境问题，不属于前端设计问题，但系统状态页可提示后端连接异常。

运行方式应固化到：

```text
frontend/docs/dev_startup_runbook.md
```

## 9. 分阶段落地计划

### P-Frontend-1：基础运行问题和组件地基

目标：先解决影响联调判断的基础问题，并准备可复用组件。

任务：

```text
修复前端中文乱码
明确 storage_status error 的展示口径
补充后端 venv 路径失效的启动说明
统一安全边界文案
统一状态标签文案
整理 AppShell 导航标题和副标题
新增或整理 StatusBadge / RiskLevelBadge / ModelSafetyNotice / LoadingState / ErrorState
```

验收：

```text
npm run build 通过
主要页面无乱码
安全边界不出现误导表达
不影响现有接口调用
```

### P-Frontend-2：共享 UI 组件和安全文案扩展

目标：让所有页面开始使用统一的状态、风险、空态、错误态和安全边界表达。

任务：

```text
统一 PagePanel / DataTable / EmptyState / ErrorNotice 的使用方式
为检测、记录、告警、预测、知识助手页面补充模型阶段和安全边界
明确 mock / smoke / experimental / real / dry-run 的视觉语义
保留现有 API 和页面结构
```

验收：

```text
用户能在任意结果页看出当前模型阶段
不会把辅助判断写成最终诊断
npm run build 通过
```

### P-Frontend-3：协同巡检主页面改造

目标：将 Figma / 原型方向融合进现有 `SuqianInspectionWorkbench`。

任务：

```text
强化顶部流程条
优化 Tab 样式
完善总览摘要卡
增强 UAV 异常卡片
强化手机复查任务流
整理报告中心
完善右侧 InspectionContextPanel
```

保留：

```text
现有 API
现有 state
现有字段绑定
报告生成逻辑
手机复查回写逻辑
```

### P-Frontend-4：协同巡检四个 Tab 深化

目标：让总览、UAV 异常、手机复查、报告中心都形成独立且清晰的任务区。

任务：

```text
总览只保留摘要和下一步建议
UAV 异常强化异常区域选择和复查状态
手机复查独立成任务流
报告中心整理证据完整度、报告生成、历史和详情
错误和空态按当前 Tab 展示
```

验收：

```text
用户无需文档即可按 Tab 完成巡检闭环
报告历史不干扰当前操作主线
右侧上下文面板始终能解释当前选中对象
```

### P-Frontend-5：移动端和大屏联调前验收

目标：在扩展移动端和大屏之前，固定主系统业务口径。

大屏第一阶段只读接口：

```text
GET /api/dashboard/summary
GET /api/dashboard/plots
GET /api/dashboard/heatmap
GET /api/dashboard/latest-records
GET /api/dashboard/latest-alerts
WS /ws/results
WS /ws/alerts
```

移动端第一阶段接口：

```text
GET /api/mobile/overview
GET /api/mobile/plots
GET /api/mobile/plots/{plot_id}
POST /api/detect/image
GET /api/mobile/records/{record_id}
GET /api/mobile/suggestions/{record_id}
```

验收：

```text
大屏只展示态势、告警和最新识别，不做复杂操作
移动端聚焦手机近景复查闭环，不照搬 PC 全功能
主系统、移动端、大屏使用一致的安全口径
```

### P-Frontend-6：全站视觉统一

目标：所有页面看起来像同一个系统。

任务：

```text
统一 PagePanel / DataTable / EmptyState / ErrorNotice
统一 Dashboard / Detect / History / Alerts / Prediction / Assistant / Settings 的密度和状态表达
减少重复样式
统一按钮、标签、表格、详情面板
```

### P-Frontend-7：答辩演示路径

目标：形成稳定讲解路线。

建议演示顺序：

```text
工作台总览
-> 协同巡检总览
-> UAV 异常
-> 手机复查
-> 报告中心
-> 记录中心
-> 预警中心
-> 知识助手
-> 系统状态
```

## 10. 验收标准

设计验收：

```text
用户进入协同巡检 5 秒内能知道当前进度
用户能清楚知道下一步点哪里
用户选中异常区域后能看到 UAV 证据、手机复查状态、报告回写情况
报告历史不干扰当前巡检主线
页面不像普通后台模板，也不过度大屏化
```

工程验收：

```text
npm run build 通过
不新增 TypeScript 错误
不改后端 API
不破坏协同巡检主链路
接口失败有明确提示
空态和加载态完整
```

安全验收：

```text
dry-run 必须标注为演示 / 实验性质
experimental 风险融合必须标注为 rule-weighted / experimental
RAG / LLM 必须标注为辅助建议
不出现正式诊断、处方、剂量建议等误导表达
```

## 11. 后续给代码智能体的改造提示词

后续每次改造可使用以下任务边界：

```text
基于 frontend/docs/frontend-design-integration-plan.md 改造当前前端。

只允许改前端页面结构、组件拆分、样式、文案、空态和错误态。
不得修改后端 API、数据库、模型选择逻辑、报告生成逻辑、告警治理逻辑。

协同巡检必须保留：
field_id / uav_task_id / abnormal_region_id 绑定
UAV dry-run
手机复查 phone_followup
检测结果回写异常区域
报告生成与历史查询
smoke / experimental / dry-run 安全边界

每次修改后运行：
npm.cmd run build

输出：
修改文件清单
页面结构变化
保留的业务链路
构建结果
```

## 12. 当前阶段状态

```text
Frontend Design Integration Plan：DONE
External API Integration Package：DONE
Next：P-Frontend-1 基础组件与运行问题修复
```

当前不建议一次性全站大改。后续每轮只处理一个小阶段，确保可构建、可回退、可验收。
