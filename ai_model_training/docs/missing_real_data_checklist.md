# 缺失真实数据清单

当前 `datasets/rice_phone_rgb/` 和 `datasets/rice_uav_ms/` 目录下没有可用于训练冒烟测试的真实或脱敏图片与 YOLO 标签。本轮不会生成假数据冒充训练集。

请补充以下内容后再运行第三轮冒烟链路：

| 项目 | 要求 |
| --- | --- |
| 图片目录 | 将少量真实或脱敏图片放入 `images/train`、`images/val`，可选 `images/test` |
| YOLO 标签 | 每张有目标图片提供同名 `.txt` 标签，格式为 `class_id x_center y_center width height` |
| 类别映射确认 | 确认 `class_map.yaml` 与 `data.yaml` 的类别顺序完全一致 |
| 元数据 CSV | 补充真实 `image_metadata.csv`，至少能关联到图片名或 source_file |
| 冒烟样本许可 | 确认是否允许抽取 20 到 50 张真实/脱敏图片做 1 epoch smoke test |

## 放置示例

```text
datasets/rice_phone_rgb/
  images/train/example_001.jpg
  labels/train/example_001.txt
  images/val/example_002.jpg
  labels/val/example_002.txt

datasets/rice_uav_ms/
  images/train/uav_001.jpg
  labels/train/uav_001.txt
  images/val/uav_002.jpg
  labels/val/uav_002.txt
```

## 边界

- 不把 `normal` 作为 YOLO 检测框类别。
- 不把 `unknown` 或 `uncertain` 写入正式训练标签。
- 小样本冒烟测试只验证流程可运行，不代表模型效果。
