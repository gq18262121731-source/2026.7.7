# AI Development Guide

本目录是项目的 AI Coding 规范入口。任何开发、重构、调试、录屏准备任务开始前，都应先阅读本文件，再按顺序阅读对应规范。

## 阅读顺序

1. `00_project_goal.md`
2. `01_global_rules.md`
3. `02_system_architecture.md`
4. `10_coding_rules.md`
5. 根据任务类型阅读：
   - 前端任务：`03_frontend_spec.md`、`07_ui_design.md`
   - 后端任务：`04_backend_spec.md`
   - Make 自动化任务：`05_make_workflow.md`
   - AI 助手任务：`06_ai_assistant.md`
   - 排期或阶段推进：`08_development_plan.md`
   - 验收任务：`09_definition_of_done.md`

## 最高原则

本项目是一个可录制比赛演示视频的完整软件平台，不是单页 Demo，不是算法脚本，也不是论文展示页。

所有功能必须服务于：

- 页面完整
- 交互清晰
- 视觉统一
- API 链路完整
- Mock 可替换
- 工程结构可扩展
- 能稳定录制演示视频

## 冲突处理

当规范之间出现冲突时，优先级如下：

1. 用户当前明确要求
2. `01_global_rules.md`
3. `10_coding_rules.md`
4. `00_project_goal.md`
5. 具体模块规范
6. 既有代码风格

## 对 AI 助手的要求

开发前必须先确认当前任务属于哪个阶段、哪个模块、涉及哪些规范文件。不要一次性修改多个无关模块。不要为了视觉效果牺牲工程结构。
