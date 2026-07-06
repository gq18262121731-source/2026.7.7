# P8 前端 API 对齐与功能真实性标注报告

## 目标

清理 `mark-video-demo/frontend` 中残留的旧 demo mock API 调用，将现有主页面对齐到 `agri_uav_disease_system/backend` 主后端真实接口，消除页面控制台中的 404。

## 已完成

| 页面/模块 | 原状态 | P8 处理 |
| --- | --- | --- |
| API client | 默认请求 Vite 本机 `/api/...` | 统一使用 `VITE_API_BASE_URL`，默认 `http://127.0.0.1:8000` |
| Dashboard | 调用旧 records/models mock 接口 | 改接 `/api/dashboard/summary`、`/api/records`、`/api/models/status` |
| 图像检测 | 请求不存在的样本接口 | 改为真实图片上传 `/api/detect/image` |
| 记录中心 | 调用旧 history 接口 | 改接 `/api/records`，展示 record_id、source_type、model_stage、fallback |
| AI 助手 | 调用旧 assistant 接口 | 改接 `/api/agent/diagnosis-report`，展示 LLM 状态和证据来源 |
| 系统配置 | 调用旧 settings/models 接口 | 改接 `/api/status`、`/api/models/status`、`/api/models/demo-safety` |
| 协同巡检 | 已接主后端 | 保持现有 `/api/fields`、`/api/uav`、`/api/inspection-reports` 链路，并统一 base URL 兼容 |
| 顶部状态 | 静态“知识库在线” | 改为更准确的“知识库模块” |
| favicon | 缺失导致 404 | 新增 `public/favicon.svg` |

## 已验证接口

- `GET /api/dashboard/summary`: 200
- `GET /api/records?page=1&page_size=3`: 200
- `GET /api/models/status`: 200
- `GET /api/models/demo-safety`: 200
- `GET /api/status`: 200
- `GET /api/knowledge/diseases`: 200
- `POST /api/agent/diagnosis-report`: 200
- `POST /api/detect/image`: 200
- `GET /favicon.svg`: 200

## 旧接口清理

命令行扫描 `src`，以下旧调用均无残留：

- `api.history`
- `api.models`
- `api.samples`
- `api.assistant`
- `api.settings`
- `"/history"`
- `"/samples"`
- `"/assistant"`
- `"/settings"`

## 当前仍需标注的边界

- UAV 多光谱仍是 dry-run 闭环，不是真实多光谱算法。
- 模型路线包含 mock / smoke / experimental / fallback，前端已展示阶段和安全说明。
- AI/RAG 已走真实 Agent 接口，但仍需用户选择或映射 disease_id 以获得更稳定证据命中。
- 暂未新增预警中心、风险预测、天气/生育期/农事、移动端预览页面；这些后端接口已存在，属于后续产品化范围。

## 验收

- `npm.cmd run build`: PASS
- 主后端关键接口命令行访问: PASS
- favicon 访问: PASS
- 未打开浏览器自动化测试，符合当前约束。
