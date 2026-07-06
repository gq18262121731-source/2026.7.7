# AI 水稻病虫害智能分析平台现阶段报告

生成时间：2026-07-01  
项目路径：`F:\学校\病虫害识别\mark-video-demo`

## 1. 阶段结论

当前项目已完成 P0 阶段的工程骨架搭建，形成了一个可本地运行、可录制基础演示视频的比赛 Demo 平台雏形。

现阶段系统已经具备：

- React + Vite + TypeScript + Tailwind 前端
- FastAPI Mock 后端
- 多页面平台式布局
- 近距离检测与无人机检测两条 Mock 检测链路
- 历史记录页面
- Template AI 助手页面
- Make 自动化状态页面
- 系统设置页面
- API 调用链路
- 演示用静态素材
- 运行说明与录屏脚本

整体已经从“空项目”推进到“可启动、可访问、可演示基础闭环”的状态。

## 2. 当前项目结构

```text
mark-video-demo/
├─ .ai/                 # AI Coding 规范
├─ backend/             # FastAPI Mock 后端
├─ frontend/            # React/Vite 前端
├─ docs/                # 运行说明、录屏脚本、阶段报告
├─ make/                # Make 自动化说明
├─ assets/              # 预留素材目录
├─ outputs/             # 预留输出目录
├─ AGENTS.md            # Codex/AI 开发入口说明
└─ README.md            # 项目启动说明
```

## 3. 已完成内容

### 3.1 AI 开发规范

已建立 `.ai/` 规范目录，并在根目录添加 `AGENTS.md`。

规范覆盖：

- 项目目标
- 全局开发规则
- 系统架构
- 前端规范
- 后端规范
- Make 工作流
- AI 助手
- UI 设计
- 开发计划
- 完成标准
- 编码规则

这套规范用于约束后续开发，避免项目变成单页 Demo 或临时脚本。

### 3.2 后端

后端位于：

```text
backend/
```

当前采用 FastAPI，已经实现以下接口：

```text
GET  /api/health
GET  /api/models
POST /api/detect
POST /api/detect/upload
GET  /api/tasks/{task_id}
GET  /api/history
GET  /api/history/{record_id}
POST /api/assistant
GET  /api/make/status
POST /api/make/trigger
GET  /api/settings
POST /api/settings
```

核心文件：

- `backend/app/main.py`
- `backend/app/routers/`
- `backend/app/services/data_store.py`
- `backend/app/mock_data/demo_records.py`
- `backend/app/schemas/demo.py`

后端当前能力：

- 返回模型列表
- 按预设图片 ID 生成 Mock 检测结果
- 上传文件后按文件名匹配同名 Demo 结果
- 自动写入内存历史记录
- 返回历史列表与详情
- 返回模板 AI 回答
- 返回 Make 工作流状态
- 支持手动触发 Make Mock 流程
- 提供静态演示素材

### 3.3 前端

前端位于：

```text
frontend/
```

当前采用：

- React
- Vite
- TypeScript
- Tailwind CSS
- Lucide Icons

已实现页面：

- 首页 Dashboard
- 检测中心
- 历史管理
- AI 助手
- Make 自动化
- 系统设置

核心文件：

- `frontend/src/app/App.tsx`
- `frontend/src/layout/AppShell.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/DetectPage.tsx`
- `frontend/src/pages/HistoryPage.tsx`
- `frontend/src/pages/AssistantPage.tsx`
- `frontend/src/pages/MakePage.tsx`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/services/api.ts`
- `frontend/src/types/api.ts`
- `frontend/src/styles/global.css`

前端当前能力：

- 平台式左侧导航与顶部状态栏
- Dashboard 展示 KPI、模型状态、历史记录和系统日志
- 检测中心可选择 4 个预设样本并调用后端检测
- 检测结果可显示图片、检测框、类别、置信度和分析文本
- 历史页可读取后端历史记录并查看详情
- AI 助手可调用后端模板问答
- Make 页面可查看和触发 Mock 自动化流程
- 设置页从 API 读取系统配置

### 3.4 演示数据

已准备 4 个演示样本：

```text
phone_bs_001
phone_blast_001
uav_blb_001
uav_stress_001
```

覆盖两类场景：

- 近距离拍摄水稻病害识别
- 无人机多光谱病害识别

静态素材位置：

```text
backend/app/static/demo/phone_closeup/
backend/app/static/demo/uav_multispectral/
```

当前素材为 SVG 占位演示图，优势是无需外部资源即可稳定显示。后续可替换为真实图片或比赛素材。

### 3.5 文档

已完成：

- `docs/runbook.md`
- `docs/demo-script.md`
- `make/scenario-readme.md`
- `docs/current-stage-report.md`

其中：

- `runbook.md` 说明本地启动方式
- `demo-script.md` 说明视频演示流程
- `scenario-readme.md` 说明 Make 场景设计
- 本报告说明当前阶段成果与后续计划

## 4. 当前运行状态

当前服务已启动并验证：

前端地址：

```text
http://127.0.0.1:5173/
```

后端地址：

```text
http://127.0.0.1:8000
```

后端健康检查：

```json
{
  "status": "ok",
  "version": "0.1.0",
  "mode": "competition_demo"
}
```

前端首页访问结果：

```text
HTTP/1.1 200 OK
```

前端代理 `/api/health` 也已验证可用。

## 5. 已验证项目

已完成以下验证：

- 后端依赖安装成功
- 后端 Python 编译检查通过
- 后端 FastAPI smoke test 通过
- 前端依赖安装成功
- 前端 `npm run build` 构建通过
- 后端服务可访问
- 前端服务可访问
- 前端代理后端 API 可访问

## 6. 当前限制

现阶段仍是 P0 可运行版本，存在以下限制：

- 检测结果为 Mock，不是真实 YOLO 推理
- AI 助手为模板模式，不是真实 LLM
- Make 为 Mock 状态，不是真实 Make Webhook
- 历史记录当前为内存缓存，重启后会重新 seed
- 演示图为 SVG 占位素材，后续需要替换为真实水稻图片或比赛素材
- 页面路由当前使用前端内部状态切换，尚未接入 React Router
- 视觉已具备基础农业科技风，但还不是最终录屏级精修版本

这些限制符合当前阶段目标，不影响基础演示链路。

## 7. 风险与注意事项

### 7.1 PowerShell npm 策略

PowerShell 当前禁止运行 `npm.ps1`，启动前端时应使用：

```powershell
npm.cmd run dev -- --host 127.0.0.1
```

不要直接使用：

```powershell
npm run dev
```

否则可能触发执行策略错误。

### 7.2 Python 版本

当前虚拟环境为 Python 3.9.13，因此后端代码已避免使用 Python 3.10 的 `str | None` 写法。

后续新增后端代码时应继续保持 Python 3.9 兼容。

### 7.3 录屏稳定性

录屏时建议优先使用预设样本，不要临场上传未知图片。

当前最稳流程：

1. 打开 Dashboard
2. 进入检测中心
3. 选择 `phone_bs_001`
4. 点击开始分析
5. 再选择 `uav_blb_001`
6. 查看历史
7. 打开 AI 助手
8. 打开 Make 自动化

## 8. 下一阶段建议

### P1：录屏观感增强

建议优先做：

- 替换真实水稻病害图片素材
- 检测框样式精修
- Dashboard 图表增强
- 历史详情页独立化
- 页面切换动画
- Toast 反馈
- Loading skeleton
- 检测流程时间线

### P2：自动化链路增强

建议继续做：

- 接入真实 Make Webhook URL 配置
- FastAPI 检测完成后异步 POST 到 Make
- Make 执行状态回写本地后端
- Google Sheets 表头模板
- 通知邮件模板

### P3：AI 能力增强

可选增强：

- Ollama adapter
- RAG 知识库
- Markdown 农业知识库结构化
- 检测结果上下文问答

### P4：演示交付打磨

最终录屏前需要：

- 固定演示数据
- 固定口播脚本
- 固定浏览器窗口尺寸
- 准备兜底截图
- 准备 Make 备用截图
- 检查无空白页、无报错、无控制台错误

## 9. 推荐下一步

建议下一步优先执行：

> 将 SVG 占位图替换为真实水稻病虫害演示图片，并精修检测中心页面。

原因：

- 对视频观感提升最大
- 能让评委第一眼相信这是农业场景
- 不影响现有 API 架构
- 可以继续保持 Mock 检测稳定性

## 10. 总结

当前项目已经完成从规范整理到 P0 工程骨架搭建的关键转变。

现阶段成果可以概括为：

> 一个本地可运行、前后端分离、具备 Mock 检测、历史、AI 助手、Make 自动化页面的 AI 水稻病虫害比赛演示平台雏形。

下一阶段重点不应急着追求真实模型，而应优先打磨演示素材、页面质感、录屏流程和自动化闭环可视化。
