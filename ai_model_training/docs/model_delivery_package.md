# 模型交付包结构

最终交付时建议整理为独立目录：

```text
model_delivery_package/
  weights/
    uav_rice_disease_yolo_best.pt
    phone_rice_disease_yolo_best.pt
  configs/
    uav_data.yaml
    phone_data.yaml
    uav_train_config.yaml
    phone_train_config.yaml
  reports/
    uav_ms_model_report.md
    phone_rgb_model_report.md
    comparison_report.md
    error_analysis.md
  samples/
    uav_success_cases/
    uav_failure_cases/
    phone_success_cases/
    phone_failure_cases/
  docs/
    dataset_description.md
    labeling_rules.md
    model_card_uav.md
    model_card_phone.md
    backend_integration.md
```

## 权重交付要求

| 文件 | 要求 |
| --- | --- |
| `best.pt` | 最佳验证结果权重 |
| `last.pt` | 最后一轮训练权重 |
| `model_card.md` | 记录数据版本、类别、训练配置、指标和限制 |

## 报告交付要求

- 指标必须来自验证集或测试集。
- 必须包含成功样例和失败样例。
- 必须说明数据版本、类别版本和训练配置。
- 必须说明模型已知限制，不得只给权重文件。
