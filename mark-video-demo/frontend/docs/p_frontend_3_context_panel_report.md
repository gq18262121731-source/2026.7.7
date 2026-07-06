# P-Frontend-3 InspectionContextPanel 深化接入报告

## 1. 本轮目标

本轮目标是将右侧 `InspectionContextPanel` 从普通信息栏深化为协同巡检页面的“当前情况解释器”。

它需要围绕当前田块、UAV 任务、异常区域、手机复查、风险融合、报告状态和模型安全边界，给用户一个稳定的上下文锚点。

本轮不修改后端接口，不重写路由，不伪造 LLM 问答，不强行打通新的业务闭环。

## 2. 修改文件列表

- `src/components/inspection/InspectionContextPanel.tsx`
- `src/components/inspection/index.ts`
- `src/pages/suqian/SuqianInspectionWorkbench.tsx`
- `src/pages/suqian/SuqianInspectionPanels.tsx`
- `docs/p_frontend_3_context_panel_report.md`

## 3. InspectionContextPanel 增强区域

新面板位于：

`src/components/inspection/InspectionContextPanel.tsx`

当前包含以下区域：

1. 当前巡检对象
   - 田块名称 / ID
   - 当前区域
   - UAV 任务
   - 异常区 ID
   - 数据来源

2. 异常区状态
   - 风险等级
   - 异常类型
   - 异常指数
   - 异常面积
   - 严重程度
   - 位置

3. 手机复查状态
   - 是否需要复查
   - 识别记录 ID
   - 识别时间
   - 检测结果
   - 置信度
   - 回写字段

4. 风险融合状态
   - 当前风险等级
   - 融合状态
   - 已使用数据源
   - 规则评分
   - 概率声明字段
   - 安全提示

5. 报告状态
   - 报告编号
   - 报告状态
   - 复查数量
   - 报告日期

6. 模型与安全边界
   - 使用 `ModelSafetyNotice`
   - 结合 `modelMode`、`dryRun.data_mode`、`followup.model_stage`、`report.risk_model_detail.model_stage`

7. 下一步建议
   - 基于当前流程状态做轻量规则提示
   - 不调用 LLM
   - 不输出农艺诊断结论

8. AI 自由问答入口
   - 仅保留禁用输入框和 P-LLM-1 接入提示
   - 不写死 FAQ 答案
   - 不展示模板问答

## 4. 当前支持的上下文字段

面板通过 props 接收上下文，不在组件内部发起业务请求。

当前支持：

- `activeTab`
- `field`
- `task`
- `dryRun`
- `selectedRegion`
- `followup`
- `report`
- `regions`
- `loadingStep`
- `modelMode`
- `demoSafety`
- `modelStatusError`

动作入口仍由页面传入：

- `onSelectTab`
- `onCreateTask`
- `onRunDryRun`
- `onRunPhoneFollowup`
- `onGenerateReport`

## 5. 无数据、加载中和错误处理

无数据：

- 无地块时展示 `EmptyState`
- 无异常区时展示 `EmptyState`
- 无手机复查记录时展示“当前异常区尚未完成手机近景复查”
- 无风险融合结果时展示“待风险融合”
- 无报告时展示“待生成报告”

加载中：

- `loadingStep` 存在时展示 `LoadingState`
- 标明当前正在更新的巡检步骤

错误：

- `modelStatusError` 使用 `ErrorState`
- 主后端操作错误仍由 Workbench 底部 `ErrorState` 展示

## 6. P1 共享组件复用情况

本轮继续复用：

- `StatusBadge`
- `RiskLevelBadge`
- `ModelSafetyNotice`
- `LoadingState`
- `ErrorState`
- `EmptyState`

没有重新实现新的状态标签、风险标签、错误态或空状态。

## 7. P2 主线保持情况

保留 P2 的协同巡检主线：

```text
田块 -> UAV 任务 -> 异常区 -> 手机复查 -> 风险融合 -> 巡检报告
```

Workbench 仍负责主流程状态和 API 调用，`InspectionContextPanel` 只负责解释当前上下文和提供下一步入口。

## 8. AI 自由问答入口

本轮已预留 AI 自由问答入口，但发送能力禁用。

显示文案：

> AI 自由问答将在 P-LLM-1 接入。当前不展示预设答案，避免将模板问答误认为真实智能分析。

没有写死 FAQ 答案，也没有伪造 LLM 结果。

## 9. 安全边界文案覆盖情况

右侧面板继续覆盖：

- mock：模拟结果，仅用于界面演示和流程联调；
- smoke：烟测能力，仅用于验证链路，不代表正式识别效果；
- experimental：实验能力，结果需人工复核，不作为正式农艺诊断或用药依据；
- real：模型推理结果，仍建议结合人工巡检和田间情况复核；
- preview / unknown：展示为待确认能力，不包装成生产能力。

已扫描源码，未发现以下禁止文案：

- 精准诊断
- 自动确诊
- 保证准确
- 直接给出处方
- 完全替代人工巡检
- AI 已确认病害
- 可直接用药

## 10. 构建结果

已在 `F:\学校\病虫害识别\mark-video-demo\frontend` 执行：

```bash
npm.cmd run build
```

结果：

```text
tsc -b && vite build
✓ built in 2.04s
```

构建通过。

## 11. Lint 结果

当前 `package.json` 未提供 `lint` 脚本。

本轮未新增 lint 配置，避免扩大工程变更。

## 12. 未完成项

- AI 自由问答尚未接入真实 LLM Agent；
- 右侧面板的“导出报告”仍未实现；
- 上下文面板暂未接入 `latestAlert`，后续可在 P-Frontend-4 或告警联动阶段补充；
- 风险融合详情仍依赖报告中的 `risk_model_detail`，本轮未新增独立融合 API。

## 13. 下一步建议

优先建议进入 `P-LLM-1`：

- 接入真实自由提问 Agent；
- 基于当前田块 / UAV 任务 / 异常区 / 复查记录 / 报告作为上下文；
- 禁止预设问答伪装成智能回答；
- 继续保持安全边界，不输出处方、剂量或正式诊断。

备选方向是 `P-Frontend-4`：

- 继续拆清总览 / UAV 异常 / 手机复查 / 报告中心的职责边界；
- 强化每个 Tab 内部的操作路线。

## 14. 最终结论

`P-Frontend-3: PASS`
