# 移动端第一阶段 LLM 联调包

包版本：mobile-llm-v1-rc  
生成日期：2026-07-07

本包只面向移动端第一阶段联调，不包含其他端或后续阶段接口文档。

当前版本为 RC 版，可开始对齐接口；正式联调前以 `openapi_mobile_llm_cn.json`、真实 `BASE_URL` 和真实 `TOKEN` 为准。

## 第一阶段范围

移动端第一阶段先完成：

```text
拍照识别 -> 识别详情 -> LLM 状态 -> 知识检索 -> 知识上下文 -> 自由问答
```

## 文件说明

| 文件 | 用途 |
|---|---|
| `README.md` | 本包入口说明 |
| `api_quick_start.md` | 5 分钟快速联调 |
| `mobile_api_integration.md` | 移动端第一阶段接口说明 |
| `mobile_api_phase2_optional.md` | 第二阶段可选接口附录，不属于第一阶段必接范围 |
| `sample_responses.md` | 核心响应样例 |
| `error_codes.md` | 错误结构与错误码 |
| `integration_acceptance_checklist.md` | 移动端验收清单 |
| `postman_mobile_llm_cn.json` | 移动端第一阶段 Postman 调试集合 |
| `openapi_mobile_llm_cn.json` | 移动端第一阶段机器可读 OpenAPI |
| `MOBILE_HANDOFF_MESSAGE.md` | 可直接发给移动端团队的说明 |

## 第一阶段重点接口

```http
GET  /healthz
GET  /api/models/status
GET  /api/agent/llm-status
POST /api/detect/image
GET  /api/mobile/records/{record_id}
GET  /api/mobile/suggestions/{record_id}
POST /api/knowledge/search
POST /api/agent/knowledge-context
POST /api/agent/diagnosis-report
```

## 环境变量

文档中的地址仅为占位：

```bash
BASE_URL="https://test-api.example.com"
TOKEN="replace-with-your-token"
```

正式联调前请单独提供真实 `BASE_URL` 和 `TOKEN`。不要把真实 token 写入文档包。

## 安全边界

LLM、RAG、知识图谱和模型识别结果均用于辅助解释，不作为正式农艺诊断或用药依据。
