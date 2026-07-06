# 脚本使用说明

本目录下脚本用于第二轮工程骨架交付。当前边界：不启动真实训练、不下载外部数据、不生成虚构权重、不生成虚构 precision/recall/mAP/F1。

## check_dataset.py

用途：检查 YOLO 数据集结构、图片、标签、类别编号、空标签、坏图、重复文件、train/val/test 完整性。

输入：
- `--dataset-root`：数据集目录，例如 `ai_model_training/datasets/rice_phone_rgb`
- `--class-count`：类别数量
- `--metadata`：可选元数据 CSV
- `--check-duplicates`：可选，计算图片 hash 查重复

输出：
- 控制台 JSON 报告
- 可选 `--output` JSON 报告文件

示例：

```bash
python ai_model_training/scripts/check_dataset.py \
  --dataset-root ai_model_training/datasets/rice_phone_rgb \
  --class-count 5 \
  --metadata ai_model_training/datasets/rice_phone_rgb/metadata/image_metadata.csv \
  --output ai_model_training/reports/phone_dataset_check.json
```

当前边界：只做静态数据检查，不评估模型指标。

## split_dataset.py

用途：根据元数据生成 train/val/test 划分计划，支持固定随机种子，并通过 `group_key` 避免同一地块、飞行任务或设备泄漏到不同集合。

输入：
- `--metadata`：元数据 CSV
- `--group-key`：分组字段，例如 `plot_id`、`flight_task_id`、`phone_model`
- `--train-ratio`、`--val-ratio`、`--test-ratio`
- `--seed`
- `--output-plan`

输出：
- JSON 划分计划

示例：

```bash
python ai_model_training/scripts/split_dataset.py \
  --metadata ai_model_training/datasets/rice_uav_ms/metadata/image_metadata.csv \
  --group-key flight_task_id \
  --train-ratio 0.7 \
  --val-ratio 0.2 \
  --test-ratio 0.1 \
  --seed 2026 \
  --output-plan ai_model_training/reports/uav_split_plan.json \
  --dry-run
```

当前边界：只生成划分计划，不移动、不复制、不删除文件。

## tile_uav_images.py

用途：无人机大图切片脚本骨架，预留 tile size、overlap、最小目标保留比例等参数。

输入：
- `--input-dir`：无人机大图目录
- `--label-dir`：可选原始标签目录
- `--output-dir`：切片输出目录
- `--tile-size`
- `--overlap`
- `--min-object-keep-ratio`

输出：
- `tiling_plan.json`

示例：

```bash
python ai_model_training/scripts/tile_uav_images.py \
  --input-dir raw/uav_images \
  --label-dir raw/uav_labels \
  --output-dir ai_model_training/reports/uav_tiling_preview \
  --tile-size 1024 \
  --overlap 0.2 \
  --min-object-keep-ratio 0.5 \
  --dry-run
```

当前边界：只输出切片计划；真实裁剪、坐标回填和标签同步转换留到第三轮实装。

## convert_labels.py

用途：预留 LabelMe、COCO、VOC 到 YOLO 的转换接口。

输入：
- `--input`：标注文件或目录
- `--format`：`labelme`、`coco` 或 `voc`
- `--class-map`：类别映射文件
- `--output-label-dir`：YOLO 标签输出目录

输出：
- 当前仅输出 dry-run 文本，不写标签文件

示例：

```bash
python ai_model_training/scripts/convert_labels.py \
  --input raw/annotations \
  --format labelme \
  --class-map ai_model_training/datasets/rice_phone_rgb/metadata/class_map.yaml \
  --output-label-dir ai_model_training/datasets/rice_phone_rgb/labels/train
```

当前边界：真实转换需等拿到标注样例后确认类别映射和坐标规则。

## train_yolo.py

用途：训练入口骨架，读取配置并输出 YOLO 训练命令预览。

输入：
- `--config`：训练配置 YAML

输出：
- 命令预览 JSON

示例：

```bash
python ai_model_training/scripts/train_yolo.py \
  --config ai_model_training/configs/phone_yolo_train.yaml
```

当前边界：即使提供 `--execute` 也会阻止真实训练。

## validate_yolo.py

用途：验证入口骨架，生成应统计的指标字段模板。

输入：
- `--weights`：未来真实权重路径
- `--data-yaml`：数据配置
- `--output-report`：验证报告模板输出路径

输出：
- JSON 验证报告模板，指标值均为 `null`

示例：

```bash
python ai_model_training/scripts/validate_yolo.py \
  --weights ai_model_training/weights/phone_rice_disease_yolo/best.pt \
  --data-yaml ai_model_training/datasets/rice_phone_rgb/data.yaml \
  --output-report ai_model_training/reports/phone_validation_template.json
```

当前边界：不运行验证，不生成虚构指标。

## infer_demo.py

用途：单图或文件夹推理入口骨架，定义后端接入所需 JSON 结构。

输入：
- `--input`：图片或目录
- `--source-type`：例如 `phone_rgb`、`uav_rgb`
- `--weights`：未来真实权重路径
- `--output-json`

输出：
- detection_result JSON 结构示例

示例：

```bash
python ai_model_training/scripts/infer_demo.py \
  --input examples/not_for_training/phone_0001.jpg \
  --source-type phone_rgb \
  --output-json ai_model_training/reports/infer_schema_preview.json
```

当前边界：不加载模型，不生成虚构检测框。

## export_model.py

用途：模型导出骨架，预留 `.pt`、ONNX、TensorRT、NCNN 等导出位置。

输入：
- `--weights`：未来真实权重路径
- `--formats`：导出格式列表
- `--output-dir`

输出：
- `export_plan.json`

示例：

```bash
python ai_model_training/scripts/export_model.py \
  --weights ai_model_training/weights/uav_rice_disease_yolo/best.pt \
  --formats pt onnx \
  --output-dir ai_model_training/reports/uav_export_preview
```

当前边界：不生成真实导出文件。
