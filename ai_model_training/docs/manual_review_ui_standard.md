# 人工复核窗口 UI 标准

## 适用范围

本标准适用于项目内所有人工复核工具，包括但不限于以下类型：

- manual prediction review
- sample visual review
- class review
- label review
- hard case review
- holdout review

## 默认语言标准

- 所有人机交互层面的窗口 UI 默认使用中文。
- CSV / JSON 内部字段名和枚举值可以继续使用英文，以保证脚本、统计逻辑和历史结果的稳定性。
- UI 层必须提供中文显示映射，避免审核人员直接面对英文枚举。

## UI 文案标准

- 按钮必须中文化。
- 状态提示必须中文化。
- 字段标签必须中文化。
- 快捷键说明必须中文化。
- 保存成功 / 保存失败必须在 UI 中明确显示，不能只写日志。

## 枚举显示标准

- 下拉框显示格式统一为：`中文说明（ENGLISH_ENUM）`
- 保存到 CSV / JSON 时仍写入稳定英文枚举值。

示例：

- 确认是 Tungro（CONFIRMED_TUNGRO）
- 暂缓使用 / Holdout（TEMP_HOLDOUT）

## 保存链路标准

- 人工复核窗口必须有明确的“保存”按钮。
- 必须支持“保存并下一张”。
- 保存后必须更新 completed / pending 数量。
- 保存后必须在 UI 中显示成功提示。
- 保存失败必须显示失败原因。
- 写文件优先使用 `.tmp -> replace` 的原子替换。
- Windows 文件锁场景下应有短重试，避免因为 Excel 或预览软件短时占用导致误判失败。

## 统计显示标准

所有人工复核窗口必须显示：

- 总数
- 已完成
- 待完成
- Gate 状态
- 当前样本 ID
- 当前样本来源

如适用，还应显示：

- 可靠性
- 风险等级
- 当前类别
- 是否 holdout

## 模型错误类型记录标准

当人工复核窗口展示模型预测图、预测框或预测统计时，必须提供“模型预测问题”字段。

该字段至少包含：

- 模型漏检 / 没有检出（NO_DETECTION）
- 漏掉明显病斑（MISS_DISEASE）
- 只检出部分病斑（PARTIAL_DETECTION）
- 粗框，定位不精细（BROAD_COARSE_BOX）
- 碎片化密集小框（FRAGMENTED_DENSE_BOXES）
- 框数过多（TOO_MANY_BOXES）
- 背景误检（FALSE_POSITIVE_BACKGROUND）
- 叶片纹理误检（FALSE_POSITIVE_LEAF_TEXTURE）
- 边缘误检（FALSE_POSITIVE_EDGE）
- 低置信度噪声（LOW_CONFIDENCE_NOISE）
- 类别预测错误（WRONG_CLASS）
- 图像模糊影响判断（IMAGE_BLUR）
- 标注或视觉本身不明确（LABEL_OR_VISUAL_AMBIGUOUS）
- 其他问题（OTHER）

注意：

- 类别复核结论用于判断“样本类别是否成立”。
- 模型错误类型用于判断“模型预测哪里失败”。
- 两者必须分开记录，不能混用。

## 人工复核窗口禁止事项

- 不得自动修改 labels。
- 不得自动修改 images。
- 不得自动修改 data.yaml。
- 不得自动训练。
- 不得自动接入 backend。
- 不得自动覆盖权重。
- 不得把“看过图”当成“已保存审核结果”。

## 新增人工复核窗口检查清单

- [ ] UI 是否默认中文
- [ ] 按钮是否中文
- [ ] 字段标签是否中文
- [ ] 下拉框是否为中文说明 + 英文枚举
- [ ] 保存值是否仍为稳定英文枚举
- [ ] 是否有保存按钮
- [ ] 是否有保存并下一张按钮
- [ ] 保存后是否更新完成数量
- [ ] 是否有保存失败提示
- [ ] 是否使用 .tmp -> replace
- [ ] 是否避免重置已有人工结果
- [ ] 是否明确禁止自动改 labels / images / data.yaml
- [ ] 是否明确禁止训练
