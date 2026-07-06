# UI Design Specification

UI 必须体现农业科技平台，而不是普通后台或营销页面。

## Design Language

参考方向：

- Apple clarity
- Linear density
- Vercel polish
- Magic UI motion restraint
- Glass surface
- Agriculture technology
- Modern dashboard

## 主题

默认使用深色主题。

整体气质：

- 专业
- 克制
- 高级
- 科技感
- 农业语义明确

## 色彩

主色建议：

- 深色背景
- 绿色强调色
- 青色或蓝绿色辅助色
- 白色/灰色文字层级

避免：

- 大面积纯绿
- 过度荧光
- 多种高饱和色混用
- 营销风渐变堆叠

## 布局

使用稳定的 Dashboard 布局：

- Sidebar 固定导航
- Header 展示当前状态
- 内容区使用 Grid
- 卡片密度适中
- 重要信息首屏可见

不要做纯 Landing Page。

## 组件风格

卡片：

- Glass 或半透明暗色面板
- 边框轻微
- 阴影克制
- 圆角统一

按钮：

- 主按钮用于关键行动
- 次按钮用于辅助操作
- 危险操作必须明确
- 所有按钮要有 hover、disabled、loading 状态

图表：

- 色彩与主题统一
- 用于解释趋势，不做装饰
- 需要空状态

Icon：

- 使用统一图标库
- 图标语义明确
- 不混用多种风格

## 动画

动画应提升演示质感，但不能影响性能。

允许：

- 页面轻微过渡
- 卡片 hover
- 数字变化
- 检测进度
- 流程节点状态变化

避免：

- 过度弹跳
- 大面积无意义粒子
- 影响阅读的循环动画
- 录屏时闪烁

## 响应式

至少适配：

- 1366px 桌面
- 1920px 桌面
- 平板宽度

录屏优先保证桌面尺寸表现稳定。
