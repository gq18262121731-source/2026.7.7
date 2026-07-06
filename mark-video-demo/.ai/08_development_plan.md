# Development Plan

项目按阶段推进，禁止跳跃式到处修改。

## P0 基础框架

目标：建立完整工程骨架。

包含：

- Frontend 项目初始化
- Backend 项目初始化
- Layout
- Theme
- Sidebar
- Routing
- API Client
- FastAPI
- Mock Data
- 基础健康检查

完成后应能启动前后端，并显示基础页面。

## P1 核心页面

目标：完成平台主体功能。

包含：

- Dashboard
- Detection Center
- History
- AI Assistant
- Settings

所有页面必须接 API，不允许页面写死业务数据。

## P2 演示增强

目标：提升比赛视频观感。

包含：

- Make Workflow
- Charts
- 动画
- 检测流程演示
- Toast
- Skeleton
- 结果可视化
- 演示素材

## P3 智能能力预留

目标：为真实能力替换留接口。

包含：

- Ollama adapter
- RAG adapter
- YOLO service adapter
- 数据库 repository
- Make real webhook config

P3 可预留接口，不要求全部真实实现。

## P4 录屏准备

目标：保证视频演示稳定。

包含：

- Demo Mode
- 预设素材
- 预设历史
- 预设 AI 问答
- 预设 Make 流程
- 错误状态兜底
- 性能检查
- 桌面分辨率适配

## 阶段推进规则

每个阶段完成前，不应大规模进入下一阶段。

若用户要求插入新任务，应判断该任务属于哪个阶段，并尽量保持修改范围最小。
