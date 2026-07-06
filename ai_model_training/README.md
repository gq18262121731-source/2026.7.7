# 基于 YOLO 的水稻病虫害检测模型训练第一轮交付

本目录用于“三下乡无人机水稻病虫害识别系统”的 AI 模型训练分支。第一轮只交付训练前规范、模板和样例配置，不启动训练，不生成或编造任何模型指标。

## 双模型策略

| 模型标识 | 适用输入 | 主要用途 |
| --- | --- | --- |
| `uav_rice_disease_yolo` | 无人机 RGB 航拍图、多光谱伪 RGB/指数图、视频抽帧、正射切片 | 地块普查、病害热力图、区域风险判断 |
| `phone_rice_disease_yolo` | 手机近距离 RGB 图片、农户上传图片、农技人员复核图片 | 移动端现场识别、农户自查、近景病斑或虫害检测 |

两个模型的数据、标注、实验、评估和交付物应独立管理。后端接入时通过 `source_type` 或 `view_type` 选择模型。

## 第一轮交付清单

1. 数据采集表模板  
   - [无人机数据采集表](docs/uav_collection_template.csv)
   - [手机数据采集表](docs/phone_collection_template.csv)
2. 类别体系建议  
   - [类别体系建议](docs/class_system.md)
3. 标注规范  
   - [标注规范](docs/labeling_rules.md)
4. 两个数据集目录结构  
   - [数据集结构说明](docs/dataset_structure.md)
5. YOLO `data.yaml` 示例  
   - [无人机 data.yaml](datasets/rice_uav_ms/data.yaml)
   - [手机 data.yaml](datasets/rice_phone_rgb/data.yaml)
6. 训练实验计划表  
   - [实验计划](docs/experiment_plan.md)
7. 验证指标表  
   - [验证指标](docs/validation_metrics.md)
8. 失败样例分析模板  
   - [失败样例分析模板](docs/error_analysis_template.md)
9. 模型交付包结构  
   - [模型交付包结构](docs/model_delivery_package.md)
10. 后端接入字段说明  
   - [后端接入字段说明](docs/backend_integration_fields.md)

## 当前边界

- 不训练模型。
- 不下载外部数据。
- 不承诺准确率、召回率或 mAP。
- 不把“正常”作为 YOLO 检测框类别。
- 不把轻度、中度、重度在第一阶段拆成独立 YOLO 检测类别。
- 不输出未经专家确认的农药剂量或强执行建议。

## 推荐下一步

确认本轮模板后，再进入第二轮：生成数据检查脚本、无人机切片脚本、标签转换脚本、训练脚本、验证脚本和推理测试脚本。
