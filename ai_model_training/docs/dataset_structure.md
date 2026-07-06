# 数据集目录结构

两个模型分别建立数据集，避免无人机远距离视角和手机近距离视角直接混训。

```text
ai_model_training/
  datasets/
    rice_uav_ms/
      images/
        train/
        val/
        test/
      labels/
        train/
        val/
        test/
      metadata/
        image_metadata.csv
        class_map.yaml
        split_report.md
      data.yaml
      README.md

    rice_phone_rgb/
      images/
        train/
        val/
        test/
      labels/
        train/
        val/
        test/
      metadata/
        image_metadata.csv
        class_map.yaml
        split_report.md
      data.yaml
      README.md
```

## 划分原则

| 数据集 | 划分依据 | 避免的问题 |
| --- | --- | --- |
| `rice_uav_ms` | 飞行任务、地块、日期、正射图来源 | 相邻切片同时进入训练集和测试集导致虚高 |
| `rice_phone_rgb` | 地块、采集日期、设备、同一叶片或同一植株组 | 相似图片泄漏到测试集 |

建议比例可先采用 train 70%、val 20%、test 10%，但最终应按地块、日期和设备分组后再微调。
