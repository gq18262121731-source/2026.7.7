# 验证指标表

禁止在没有真实验证结果时填写数值。第一轮只定义指标、来源和记录方式。

| 指标 | 含义 | 数据来源 | 适用模型 | 记录位置 |
| --- | --- | --- | --- | --- |
| Precision | 检测为病虫害的结果中有多少是真实目标 | 验证集/测试集 | UAV / Phone | model_report |
| Recall | 真实目标中有多少被检测出来 | 验证集/测试集 | UAV / Phone | model_report |
| mAP50 | IoU 0.50 下的平均精度 | 验证集/测试集 | UAV / Phone | model_report |
| mAP50-95 | IoU 0.50 到 0.95 的平均精度 | 验证集/测试集 | UAV / Phone | model_report |
| F1-score | Precision 与 Recall 的综合指标 | 验证集/测试集 | UAV / Phone | model_report |
| per-class AP | 每个类别的 AP | 验证集/测试集 | UAV / Phone | model_report |
| Confusion Matrix | 类别混淆情况 | 验证集/测试集 | UAV / Phone | reports |
| PR Curve | 不同阈值下 Precision/Recall 曲线 | 验证集/测试集 | UAV / Phone | reports |
| inference_time_ms | 单张平均推理耗时 | 固定硬件测试 | UAV / Phone | model_card |
| model_size_mb | 权重文件大小 | 导出文件 | UAV / Phone | model_card |
| false_positive_cases | 正常区域误检 | 测试集与人工复核 | UAV / Phone | error_analysis |
| false_negative_cases | 真实病虫害漏检 | 测试集与人工复核 | UAV / Phone | error_analysis |

## 无人机专项验证

- 切片级检测效果
- 原始航拍图回填效果
- 地块级风险聚合效果
- 热力图位置合理性
- 正常地块误报率
- 不同飞行高度和光照下的稳定性
- RGB 与多光谱伪 RGB/指数输入对比

## 手机专项验证

- 清晰图片识别效果
- 模糊、弱光、逆光、遮挡图片识别效果
- 复杂背景下误检情况
- 不同手机设备泛化能力
- 不同拍摄距离下识别效果
- 早期轻微病斑漏检分析
