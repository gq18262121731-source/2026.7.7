# System Architecture

项目采用前后端分离、Mock 可替换、演示优先的工程结构。

## 总体链路

```text
Frontend
  -> API Client
  -> FastAPI
  -> Services
  -> Mock Data / Template AI / Mock Detection
  -> History
  -> Make Workflow
  -> Notification / Google Sheet / Email Mock
```

未来替换真实能力时，只替换 service 或 repository，不改前端页面。

## Frontend 结构

推荐结构：

```text
frontend/
  src/
    app/
    layout/
    pages/
    components/
    features/
    hooks/
    services/
    types/
    utils/
    assets/
```

职责说明：

- `app/`: 应用入口、路由、全局 Provider
- `layout/`: Sidebar、Header、Shell、页面容器
- `pages/`: 页面级组件，只负责组合模块
- `components/`: 通用 UI 组件
- `features/`: 业务功能模块
- `hooks/`: 可复用状态逻辑
- `services/`: API 调用和数据适配
- `types/`: TypeScript 类型
- `utils/`: 纯函数工具
- `assets/`: 图片、图标、纹理、演示素材

页面不得直接访问 Mock JSON。页面必须通过 `services/` 获取数据。

## Backend 结构

推荐结构：

```text
backend/
  app/
    main.py
    routers/
    schemas/
    services/
    repositories/
    mock_data/
    history/
    assistant/
    settings/
    make/
    static/
```

职责说明：

- `routers/`: FastAPI 路由
- `schemas/`: Pydantic 请求与响应模型
- `services/`: 业务逻辑
- `repositories/`: 数据访问抽象
- `mock_data/`: 演示数据
- `history/`: 检测历史与操作记录
- `assistant/`: 模板 AI、Ollama、RAG 适配
- `settings/`: 系统设置与模式切换
- `make/`: Make Webhook 和自动化流程
- `static/`: 演示文件、检测结果图片等静态资源

## 模块边界

Dashboard 不直接执行检测。

Detection Center 负责检测任务创建、上传、结果展示。

History 负责读取和管理历史记录。

AI Assistant 负责知识问答，不负责直接修改检测结果。

Settings 负责配置展示和模式切换。

Make Workflow 负责自动化触发和流程状态展示。

## 数据流

所有业务数据必须有明确来源：

- 检测任务来自 `/api/detect`
- 历史记录来自 `/api/history`
- 模型状态来自 `/api/models`
- AI 回复来自 `/api/assistant`
- 系统配置来自 `/api/settings`
- 自动化状态来自 `/api/make`

前端可以缓存数据，但不能绕开 API contract。
