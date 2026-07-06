# Global Development Rules

所有开发必须遵循以下原则。

## 一、绝不破坏工程结构

禁止为了完成一个页面而破坏已有模块。

新增功能不得影响已有页面、已有 API、已有数据结构和已有演示流程。

所有代码必须模块化，避免：

- 超大组件
- 超长文件
- 重复代码
- 页面内写死业务逻辑
- Mock 数据散落在 UI 组件中

## 二、所有页面必须统一

所有页面必须使用统一的：

- Layout
- Sidebar
- Header
- Theme
- Animation
- Color System
- API Client
- Loading / Error / Empty 状态

不得出现：

- 一个页面像后台系统
- 一个页面像官网落地页
- 一个页面像聊天机器人
- 一个页面像临时脚本界面

## 三、所有数据来自 API

任何页面不得直接写死业务数据。

即使是 Demo，也必须保持完整调用链：

```text
Frontend
  -> API Client
  -> FastAPI
  -> Mock Service / Mock JSON
  -> Frontend
```

Mock 数据只能出现在后端 mock 数据层或前端明确的 mock service 层，不能散落在页面组件中。

## 四、面向未来替换

所有模块必须考虑未来替换：

- 真实 YOLO 检测模型
- 真实数据库
- 真实 LLM
- 真实 RAG
- 真实 Make Webhook
- 真实消息通知

因此禁止把 Mock、模板回复、假历史记录写死在组件里。

## 五、视觉风格统一

整体视觉必须保持：

- 农业科技风
- Glass
- Dark
- Green Accent
- Modern
- Professional
- Dashboard First

避免杂乱色彩、营销风首页、过度装饰、风格割裂。

## 六、小步开发

每次开发遵循：

- Small Feature
- Small Module
- Small Commit
- 一次只完成一个功能

开发完成后必须检查：

- 是否影响其他模块
- 是否破坏已有路由
- 是否破坏 API contract
- 是否仍可录屏演示
