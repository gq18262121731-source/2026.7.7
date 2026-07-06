# 真实项目需求与前端融合审计报告

## 1. 真实项目产品需求总览

真实项目定位为 `AI 水稻病虫害智能分析平台`，核心目标不是演示，而是形成可闭环的业务系统。

### 产品模块
- 首页 Dashboard
- 智能检测
- 历史记录
- 模型状态与系统管理
- 预警中心
- 移动端/上传端接口
- AI 诊断建议
- 预测、天气、生育期、农事记录等扩展能力

### 必须遵守的模型边界
- `smoke` 只能作为工程验证
- `experimental` 只能作为实验模型
- `formal_metric_available=false` 时不能展示正式准确率
- `UAV default` 是 `crop_object`，不能说成病害检测
- `mock fallback` 不能包装成真实预测
- `Healthy` 不能作为检测类别返回

---

## 2. 真实后端已实现能力清单

### 2.1 首页 Dashboard
已实现接口：
- `GET /api/status`
- `GET /api/models/status`
- `GET /api/dashboard/summary`
- `GET /api/dashboard/latest-records`
- `GET /api/dashboard/latest-alerts`
- `GET /api/dashboard/plots`
- `GET /api/dashboard/heatmap`
- `GET /api/dashboard/disease-statistics`

已实现字段：
- 平台运行状态
- 模型加载状态
- 数据库状态
- 存储状态
- WebSocket 客户端数
- 今日检测数
- 总记录数
- 病害记录数
- 风险等级统计
- 严重程度统计
- 最新记录
- 最新预警

### 2.2 智能检测
已实现接口：
- `POST /api/detect/image`
- `POST /api/detect/batch`
- `GET /api/tasks/{task_id}`

已实现链路：
- 上传保存原图
- 自动选择模型路由
- 执行检测
- 后处理
- 风险评估
- 生成建议
- 生成结果图
- 写入 SQLite
- 推送 WebSocket
- 触发预警治理

### 2.3 历史记录
已实现接口：
- `GET /api/records`
- `GET /api/records/{record_id}`
- `GET /api/dashboard/plots/{plot_id}/records`

已实现数据：
- 原图 URL
- 结果图 URL
- 检测框
- summary
- suggestion
- model_name
- model_stage
- fallback_to_mock
- formal_metric_available

### 2.4 模型状态
已实现接口：
- `GET /api/models/status`
- `GET /api/models/demo-safety`

已实现内容：
- phone smoke
- phone experimental
- UAV crop_object smoke
- UAV BLB smoke
- UAV BLB experimental
- mock fallback
- 路由矩阵
- 安全说明

### 2.5 预警模块
已实现接口：
- `GET /api/alerts`
- `GET /api/alerts/{alert_id}`
- `POST /api/alerts/{alert_id}/resolve`
- `GET /api/alerts/{alert_id}/actions`
- `WS /ws/alerts`

### 2.6 移动端/上传端
已实现接口：
- `GET /api/mobile/overview`
- `GET /api/mobile/plots`
- `GET /api/mobile/plots/{plot_id}`
- `GET /api/mobile/records/{record_id}`
- `GET /api/mobile/alerts`
- `GET /api/mobile/suggestions/{record_id}`
- `GET /api/upload/capabilities`

### 2.7 AI 诊断建议
已实现：
- 检测结果内置 `suggestion`
- `GET /api/mobile/suggestions/{record_id}`

### 2.8 工程基础
已实现：
- SQLite 持久化
- Repository 层
- 文件存储
- WebSocket
- 批量任务
- 测试集
- 文档集

---

## 3. 真实后端未实现或不足清单

- 没有真实登录/权限体系
- 没有正式 UAV SDK 接入
- 没有真实生产级地图服务
- 没有正式模型指标展示
- 没有真实 RAG/LLM 诊断链路
- `smoke` 与 `experimental` 仍属于验证和实验，不是正式模型
- `UAV default` 仍是 crop_object 辅助链路，不是病害识别
- `mock` 仍是兜底，不是预测结果

---

## 4. 真实项目各需求模块审计

### 4.1 首页 Dashboard

已实现字段
- `service_status`
- `model_loaded`
- `model_name`
- `model_version`
- `detector_mode`
- `database_status`
- `storage_status`
- `websocket_clients`
- `capabilities`
- `models`
- `storage`
- `today_detect_count`
- `total_record_count`
- `disease_record_count`
- `normal_record_count`
- `high_risk_plot_count`
- `medium_risk_plot_count`
- `low_risk_plot_count`
- `risk_level_counts`
- `severity_counts`
- `top_diseases`
- `latest_alerts`
- `latest_records`

缺失字段
- 平台用户数
- 在线设备数
- 真实产线 SLA
- 业务级告警趋势图
- 按来源类型的完整统计卡

前端可展示内容
- 运行状态
- 今日检测
- 风险样本
- 最新记录
- 最新预警
- 模型服务状态

需要补充接口
- 暂无硬缺口，首页主链路已够用

### 4.2 智能检测

当前链路完整度
- 传图
- 检测
- 生成结果图
- 保存记录
- 返回建议
- 推送结果

可直接给前端使用的字段
- `record_id`
- `image_url`
- `result_image_url`
- `detections`
- `summary`
- `suggestion`
- `model_name`
- `model_stage`
- `detector_mode`
- `fallback_to_mock`
- `formal_metric_available`
- `current_target_type`
- `model_display_name`
- `model_warning`
- `model_usage_scope`

需要 adapter 的字段
- 前端当前使用的 `task_id`
- `image.original_url`
- `summary.top_label`
- `summary.top_confidence`
- `analysis.text`

前端检测页改造方向
- 增加上传文件而不是只选本地样本
- 增加 source_type / model_hint / target_type 选择
- 增加模型边界提示
- 增加结果图与原图双图展示
- 增加检测框明细、模型阶段、兜底状态

### 4.3 历史记录

当前字段完整度
- 完整，且比演示前端更规范

前端 HistoryPage 可复用程度
- 列表布局可复用
- 详情卡片布局可复用
- 但数据结构必须重接

建议新增
- 详情侧栏或详情抽屉
- 筛选器：时间、风险、疾病、模型阶段、来源类型
- 原图/结果图双视图
- 模型安全边界提示

### 4.4 模型状态

真实后端已有
- `phone_model`
- `phone_experimental_model`
- `uav_crop_model`
- `uav_blb_model`
- `uav_blb_experimental_model`
- `mock_model`
- `active_routing`
- `demo_safety`

前端必须展示
- `model_stage`
- `usage_scope`
- `warning`
- `formal_metric_available`
- `current_target_type`
- `fallback_to_mock`

不能包装成正式能力
- smoke 不能叫正式模型
- experimental 不能叫正式模型
- crop_object 不能叫病害检测
- mock 不能叫预测准确

### 4.5 预警模块

真实后端已具备
- `alerts api`
- `latest_alerts`
- `resolve`
- `actions`
- `ws/alerts`

结论
- 首页应该展示最新预警
- 建议单独加“预警中心”页面
- 现有演示前端缺这个模块

### 4.6 移动端/上传端

真实后端已具备
- `mobile api`
- `upload capabilities`
- `plot_id`
- `plot_name`
- `lng/lat`
- `source_type`

结论
- 检测页应体现这些参数
- 系统管理页可展示上传能力
- 作为 Phase 3/4 之外的后续增强模块更合适

### 4.7 AI 诊断助手

真实后端情况
- 没有正式 LLM/RAG 体系
- 但检测结果已有 `suggestion`
- 移动端也可按记录拉取建议

结论
- 可以先让前端直接展示后端 suggestion
- 当前演示的助手页可保留为独立前端增强模块
- 后续再接真实 RAG / Ollama / LLM

---

## 5. 演示前端可复用页面清单

### 可直接复用
- `DashboardPage`
- `HistoryPage`
- `SettingsPage`
- `AppShell`

### 可部分复用
- `DetectPage`
- `AssistantPage`

### 原因
- 现有页面布局和交互结构已经接近真实业务形态
- 但数据源和字段都偏演示，需要换成真实 API

---

## 6. 演示前端需要删除或改造的内容

### 必须改造
- `api.ts`
- `types/api.ts`
- `DashboardPage`
- `DetectPage`
- `HistoryPage`
- `SettingsPage`
- `AssistantPage`

### 必须删除或弱化的 Demo 痕迹
- 只读本地样本生成检测结果的逻辑
- `task_id / sample_key / analysis` 这套演示结构
- 任何暗示“本地索引即真实模型”的文案
- 对 `uav_multispectral` 的不准确包装
- 对 `smoke`、`experimental` 的正式模型表达

---

## 7. API 字段映射表

### 7.1 检测结果映射

| 演示前端字段 | 真实后端字段 | 说明 | 是否需要 adapter |
|---|---|---|---|
| `task_id` | `record_id` | 真实检测记录主键 | 是 |
| `image.original_url` | `image_url` | 原图地址 | 是 |
| `detections` | `detections` | 可直接复用，但字段结构不同 | 是 |
| `summary.top_label` | `summary.main_disease` | 主病害/主类别 | 是 |
| `summary.top_confidence` | `summary.max_confidence` | 置信度 | 是 |
| `analysis.text` | `suggestion.content` | 诊断建议正文 | 是 |
| `analysis.title` | `suggestion.title` | 建议标题 | 是 |
| `processing_status` | `detector_mode / model_stage / fallback_to_mock` | 状态需拆开显示 | 是 |

### 7.2 历史记录映射

| 演示前端字段 | 真实后端字段 | 说明 |
|---|---|---|
| `task_id` | `record_id` | 记录主键 |
| `created_at` | `timestamp` / `created_at` | 真实端以时间戳为主 |
| `image.source_name` | `plot_name` / `source_type` | 需要拆分显示 |
| `summary.top_label` | `summary.main_disease` | 主结果 |
| `summary.risk_level` | `summary.risk_level` | 可直接用 |
| `summary.top_confidence` | `summary.max_confidence` | 可直接用 |
| `analysis.title/text` | `suggestion.title/content` | 建议信息 |
| `image.original_url` | `image_url` | 原图 |
| 无 | `result_image_url` | 需要新增展示 |
| 无 | `model_name` | 需要新增展示 |
| 无 | `model_stage` | 需要新增展示 |
| 无 | `fallback_to_mock` | 需要新增边界提示 |

### 7.3 模型状态映射

| 真实字段 | 前端建议命名 | 说明 |
|---|---|---|
| `name` | model key | 模型标识 |
| `display_name` | 模型名称 | 展示名 |
| `model_stage` | 阶段 | `mock/smoke/experimental` |
| `current_target_type` | 目标类型 | `disease/crop_object` |
| `usage_scope` | 使用范围 | 前端说明文案 |
| `warning` | 安全说明 | 必须展示 |
| `formal_metric_available` | 正式指标可用性 | false 时不可显示正式指标 |
| `loaded` / `ready` | 可用状态 | 需区分路径存在与实际加载 |
| `fallback_to_mock` | 兜底状态 | 需显式提示 |

---

## 8. 模型安全边界说明

- `phone default` 是 smoke，仅用于工程验证
- `phone experimental` 是 experimental，仅用于实验验证
- `uav default` 是 `crop_object`，不能当病害识别
- `uav_blb smoke` 才是 UAV 病害 smoke 链路
- `uav_blb experimental` 只能作为实验验证
- `mock fallback` 只能作为兜底
- `formal_metric_available=false` 时不能展示正式准确率
- `Healthy` 不能作为检测类别返回

---

## 9. 分阶段融合路线

### Phase 0：需求与现状审计
- 只读
- 建立字段映射
- 确定页面复用方案

### Phase 1：首页接真实后端
接入：
- `/api/status`
- `/api/models/status`
- `/api/dashboard/summary`
- `/api/dashboard/latest-records`
- `/api/dashboard/latest-alerts`

目标：
- 首页数据真实化

### Phase 2：历史记录接真实后端
接入：
- `/api/records`
- `/api/records/{id}`

目标：
- 历史记录从 SQLite 读取

### Phase 3：检测页接真实后端
接入：
- `/api/detect/image`

目标：
- 上传图片后走真实检测服务

### Phase 4：系统管理接真实模型状态
接入：
- `/api/models/status`

目标：
- 展示真实模型阶段和安全边界

### Phase 5：AI 助手与建议模块
- 优先展示后端 `suggestion`
- 后续再接 RAG / LLM

---

## 10. 推荐第一阶段开发任务

1. 为前端定义真实后端数据适配层。
2. 将首页从演示 history/models 数据切到 `/api/status` 与 `/api/dashboard/*`。
3. 把首页统计卡改成真实统计。
4. 把首页最新记录、最新预警替换成真实数据。
5. 统一显示模型边界提示，避免把 smoke/experimental 说成正式能力。

---

## 11. 风险与注意事项

- 不要把 smoke/experimental 包装成正式模型
- 不要把 `crop_object` 说成病害检测
- 不要把 mock fallback 说成真实预测
- 不要把没有的指标写成正式指标
- 不要先改后端再改前端，先做字段适配更稳
- 建议先做 adapter，不要直接让页面耦合后端内部字段

