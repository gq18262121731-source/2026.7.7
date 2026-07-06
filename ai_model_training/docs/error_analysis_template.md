# 失败样例分析模板

每次训练或验证后复制本模板，生成对应实验的 `error_analysis.md`。

## 基本信息

| 字段 | 内容 |
| --- | --- |
| experiment_id | 待填写 |
| model_name | 待填写 |
| dataset_version | 待填写 |
| weights | 待填写 |
| evaluator | 待填写 |
| date | 待填写 |

## 失败样例记录

| sample_id | image_path | source_type | true_label | predicted_label | confidence | failure_type | suspected_reason | action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sample_001 | 待填写 | phone_rgb | 待填写 | 待填写 | 待填写 | 误检/漏检/混淆 | 待填写 | 补数据/修标注/调增强/调尺寸/待专家复核 |

## 失败类型

| failure_type | 说明 |
| --- | --- |
| false_positive | 正常区域被识别为病虫害 |
| false_negative | 真实病虫害未识别 |
| class_confusion | 类别识别错误 |
| small_object_miss | 小目标漏检 |
| low_light_fail | 低光照失败 |
| blur_fail | 模糊失败 |
| complex_background_fail | 复杂背景失败 |
| multi_disease_fail | 多病虫害同图失败 |
| mild_symptom_fail | 轻微早期症状失败 |
| domain_shift_fail | 新地块、新日期或新设备泛化失败 |

## 结论

- 是否需要补数据：待填写
- 是否需要修正标注：待填写
- 是否需要调整增强策略：待填写
- 是否需要调整输入尺寸：待填写
- 是否需要更换模型规模：待填写
- 下一轮优先级：待填写
