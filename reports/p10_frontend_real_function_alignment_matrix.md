# P10 前端真实功能补齐与功能矩阵对账报告

## 目标

把已有主后端能力尽可能变成前端可操作、可验证、可录屏、可答辩的真实功能；没有后端支撑的能力不再作为正式功能展示，dry-run / mock / smoke / experimental 均显式标注。

## 本轮新增/强化页面

| 功能 | 后端状态 | 前端状态 | 当前真实性 | 本轮处理 |
| --- | --- | --- | --- | --- |
| Dashboard | 已有 `/api/dashboard/summary` | 已接入 | 真实可用 | 展示真实统计、记录、模型状态 |
| 单图识别 | 已有 `/api/detect/image` | 已接入 | 真实可用 | 支持真实图片上传、模型阶段和 fallback 展示 |
| 历史记录 | 已有 `/api/records` | 已接入 | 真实可用 | 展示 record_id、source_type、模型阶段、安全边界 |
| 宿迁协同巡检 | 已有 fields/uav/reports | 已接入 | 真实可用 + dry-run | 保持主线入口，继续标注 UAV dry-run |
| RAG/LLM 诊断 | 已有 `/api/agent/diagnosis-report` | 已接入 | 真实可用 | 展示 llm_mode、provider、model、fallback、证据来源 |
| 系统状态 | 已有 `/api/status` `/api/models/status` | 已接入 | 真实可用 | 展示后端、模型、安全边界 |
| 预警中心 | 已有 `/api/alerts` | 新增页面 | 真实可用 | 支持列表、详情、处理动作、标记已处理 |
| 风险预测 | 已有 `/api/prediction/*` | 新增页面 | 规则评分可用 | 展示 3/7/14 天综合风险评分，不称为发病概率 |
| 批量检测 | 已有 `/api/detect/batch` `/api/tasks/{id}` | 新增页面 | 真实可用 | 多图上传、任务状态、进度和 record_ids |
| WebSocket 状态 | 已有 `/ws/results` `/ws/tasks` `/ws/alerts` | 顶部状态条 | 真实连接状态 | 展示结果/任务/预警 WS 连接状态 |

## 仍需后续开发

| 功能 | 当前状态 | 建议阶段 |
| --- | --- | --- |
| 田块详情中的天气/生育期/农事 Tab | 后端已有接口，前端未做独立页面 | P11 |
| 真实多光谱 NDVI/NDRE 算法 | 目前为 dry-run/占位结果 | P12 |
| 真实地图 API/田块 polygon | 未接入外部地图服务 | 暂不作为正式功能展示 |
| 真实天气 API 自动同步 | 当前为后端记录接口雏形 | P11 后续 |
| 农药处方剂量推荐 | 不做 | 保持禁用/不展示 |

## 已验证

- `npm.cmd run build`: PASS
- `python -m compileall app`: PASS
- `pytest app/tests -q`: 67 passed, 15 skipped
- `python -m app.scripts.system_smoke_test`: PASS
- `scripts/verify_p5_frontend_backend_contract.py`: PASS

## 命令行接口自检

- `GET /api/alerts?page=1&page_size=3`: 200
- `GET /api/prediction/dashboard/summary`: 200
- `GET /api/prediction/risk-map`: 200
- `POST /api/detect/batch`: 200
- `GET /api/status`: 200
- `GET /api/models/status`: 200

## 旧 demo API 清理

命令行扫描 `frontend/src`，以下旧调用无残留：

- `api.history`
- `api.models`
- `api.samples`
- `api.assistant`
- `api.settings`
- `"/history"`
- `"/samples"`
- `"/assistant"`
- `"/settings"`

## 结论

P10 已把主后端已有的预警、风险预测、批量检测、WebSocket 状态等能力补到前端主导航中。当前系统从“演示壳”进一步升级为可操作、可追溯、可解释、可验证的前后端一体系统。下一阶段建议继续做 P11：围绕 field_id 做田块详情、天气、生育期、农事、识别历史和报告历史聚合。
