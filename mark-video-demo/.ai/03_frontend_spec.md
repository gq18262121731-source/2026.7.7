# Frontend Specification

前端必须体现完整平台感，而不是单个工具页。

## 全局要求

所有页面必须包含：

- 统一 Shell
- Sidebar 导航
- 顶部 Header
- 页面标题区
- 内容主体
- Loading 状态
- Error 状态
- Empty 状态
- Toast 或反馈机制
- Responsive 布局

页面切换应平滑，但动画必须克制，不影响录屏稳定性。

## 页面列表

必须包含以下页面：

- Dashboard
- Detection Center
- History
- AI Assistant
- Make Workflow
- Settings

## Dashboard

Dashboard 是平台首页，展示整体能力，不是简单欢迎页。

必须包含：

- 平台概览 Hero
- KPI 卡片
- 最近检测记录
- 风险趋势图
- 模型状态
- 自动化状态
- 系统日志
- 快速入口
- AI 摘要

Dashboard 的按钮应跳转到对应模块：

- 开始检测 -> Detection Center
- 查看历史 -> History
- 咨询助手 -> AI Assistant
- 查看自动化 -> Make Workflow

## Detection Center

检测中心负责病虫害检测演示。

必须包含：

- 图片或视频上传区域
- 示例素材快捷选择
- 检测参数
- 模型状态提示
- 检测进度
- 结果可视化
- 置信度
- 病虫害类别
- 处理建议
- 保存到历史
- 触发 Make 自动化

检测结果必须来自 API，允许后端返回 Mock 结果。

## History

历史管理负责记录检索、筛选和复盘。

必须包含：

- 历史列表
- 搜索
- 状态筛选
- 类型筛选
- 时间筛选
- 详情弹窗或详情页
- 重新分析
- 导出或复制摘要

历史记录必须通过 API 获取。

## AI Assistant

AI 助手负责农业知识问答和检测结果解释。

必须包含：

- 对话区
- 快捷问题
- 知识来源提示
- 检测结果上下文引用
- 模板模式标识
- 加载状态
- 错误状态

默认使用 Template AI，不要求真实大模型。

## Make Workflow

Make Workflow 页面负责展示自动化链路。

必须包含：

- Webhook 状态
- 流程节点
- 最近触发记录
- Google Sheet Mock 状态
- 通知 Mock 状态
- 失败重试状态
- 手动触发按钮

## Settings

设置页负责系统配置和演示模式切换。

必须包含：

- 模型配置
- API 配置
- Assistant 模式
- Make Webhook 配置
- Demo Mode 开关
- Theme 配置
- 系统信息

## 交互规范

所有按钮必须有明确结果：

- 跳转
- 提交
- 打开弹窗
- 触发 API
- 显示 Toast

所有异步操作必须有：

- Loading
- Success
- Error
- Empty

禁止无反馈点击。

## 组件规范

页面组件只负责组合，不写复杂业务逻辑。

可复用 UI 组件应放入 `components/`。

业务组件应放入 `features/`。

API 请求应放入 `services/`。

类型定义应放入 `types/`。
