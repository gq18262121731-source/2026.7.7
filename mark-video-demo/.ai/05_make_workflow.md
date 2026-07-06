# Make Workflow Specification

Make 自动化用于比赛演示中的“平台联动能力”展示。

## 目标

展示检测完成后，系统可以自动完成：

- 写入历史记录
- 触发 Webhook
- 同步 Google Sheet
- 发送通知
- 生成摘要
- 记录流程状态

Demo 阶段允许全部使用 Mock。

## 标准流程

```text
Detection Finished
  -> Save History
  -> Trigger Make Webhook
  -> Write Google Sheet
  -> Send Notification
  -> Update Workflow Status
```

## Make 页面必须展示

- Webhook URL
- Webhook 状态
- 最近触发时间
- 流程节点状态
- 成功次数
- 失败次数
- 最近错误
- 手动触发按钮
- 重试按钮

## 流程节点

节点建议：

1. Receive Detection Result
2. Validate Payload
3. Save History
4. Sync Google Sheet
5. Send Email / Notification
6. Generate Summary

## 异常处理

每个节点必须有状态：

- pending
- running
- success
- failed
- skipped

失败时必须记录：

- 错误原因
- 失败节点
- 重试次数
- 下次重试时间

## 演示模式

Demo Mode 下可以不真实调用 Make，而是模拟完整流程。

但前端必须通过 `/api/make/trigger` 和 `/api/make/status` 获取状态。
