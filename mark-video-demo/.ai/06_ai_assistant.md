# AI Assistant Specification

AI 助手负责农业知识问答、检测结果解释和演示中的智能交互。

## 支持模式

必须设计为可切换模式：

- Template
- Ollama
- RAG

默认模式：

```text
Template
```

未来应能通过一行配置切换到 Ollama 或 RAG。

## Template 模式

Template 模式用于比赛演示稳定输出。

应支持：

- 常见病虫害问题
- 检测结果解释
- 防治建议
- 平台功能说明
- Make 自动化说明

回答必须专业、稳定、简洁。

## Ollama 模式

预留本地大模型接口。

要求：

- 与 Template 模式使用相同请求响应格式
- 失败时可回退到 Template 模式
- 不影响前端

## RAG 模式

预留本地知识库检索。

要求：

- 支持知识来源
- 支持引用片段
- 支持与检测结果上下文结合

## API Contract

前端只调用：

```text
POST /api/assistant
```

请求：

```json
{
  "message": "稻瘟病怎么防治？",
  "mode": "template",
  "context": {}
}
```

响应：

```json
{
  "answer": "建议...",
  "sources": [],
  "mode": "template",
  "confidence": 0.92
}
```

## UI 要求

AI 助手页面必须展示：

- 当前模式
- 用户消息
- 助手回复
- 快捷问题
- 加载状态
- 错误状态
- 知识来源

禁止让 AI 助手页面变成孤立聊天产品，它必须服务于农业平台。
