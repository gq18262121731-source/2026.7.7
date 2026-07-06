# P11-0 外部数据集类别映射建议

生成时间：2026-07-05

## 当前项目 disease_id 参考

从当前后端模型展示、知识库和测试口径看，已稳定出现或可被系统识别的 disease_id / class_code 包括：

- `bacterial_leaf_blight`
- `brown_spot`
- `rice_blast`
- `tungro`
- `sheath_blight`
- `leaf_smut`
- `healthy`
- `rice_panicle`，属于 crop object，不属于 disease

另有 pest / pest_damage 建议目标：

- `rice_hispa` 或 `pest_hispa`，需产品口径确认
- `leaf_folder_damage`
- `stem_borer_damage`

所有无法确定的类别必须标记为 `NEEDS_REVIEW`，不得强行映射。

## 标准映射表

| 外部类别写法 | 建议映射 | target_type | 状态 |
| --- | --- | --- | --- |
| bacterial leaf blight | `bacterial_leaf_blight` | disease | APPROVED |
| bacterial blight | `bacterial_leaf_blight` | disease | APPROVED |
| BLB | `bacterial_leaf_blight` | disease | APPROVED |
| BacterialBlight | `bacterial_leaf_blight` | disease | APPROVED |
| brown spot | `brown_spot` | disease | APPROVED |
| BrownSpot | `brown_spot` | disease | APPROVED |
| blast | `rice_blast` | disease | APPROVED |
| rice blast | `rice_blast` | disease | APPROVED |
| leaf blast | `rice_blast` | disease | APPROVED |
| RiceBlast | `rice_blast` | disease | APPROVED |
| sheath blight | `sheath_blight` | disease | APPROVED |
| tungro | `tungro` | disease | APPROVED |
| healthy | `healthy` | healthy | APPROVED |
| normal leaf | `healthy` | healthy | APPROVED |
| Healthy Rice Leaf | `healthy` | healthy | APPROVED |
| rice hispa | `rice_hispa` | pest | NEEDS_PRODUCT_CONFIRMATION |
| hispa | `rice_hispa` | pest | NEEDS_PRODUCT_CONFIRMATION |
| leaf folder | `leaf_folder_damage` | pest_damage | APPROVED_AFTER_NAME_CONFIRMATION |
| leaf roller | `leaf_folder_damage` | pest_damage | NEEDS_REVIEW |
| stem borer | `stem_borer_damage` | pest_damage | APPROVED_AFTER_NAME_CONFIRMATION |
| white stem borer | `stem_borer_damage` | pest_damage | APPROVED_AFTER_NAME_CONFIRMATION |
| yellow stem borer | `stem_borer_damage` | pest_damage | APPROVED_AFTER_NAME_CONFIRMATION |
| bacterial leaf streak | `NEEDS_REVIEW` | disease | 当前知识库未稳定覆盖 |
| bacterial panicle blight | `NEEDS_REVIEW` | disease | 当前知识库未稳定覆盖 |
| downy mildew | `NEEDS_REVIEW` | disease | 当前知识库未稳定覆盖 |
| leaf scald | `NEEDS_REVIEW` | disease | 当前知识库未稳定覆盖 |
| narrow brown leaf spot | `NEEDS_REVIEW` | disease | 不应直接合并 brown_spot，需专家确认 |
| common rust | `NEEDS_REVIEW_NON_RICE` | disease | 玉米病害，不映射为水稻病害 |
| weedy rice | `non_disease_weedy_rice` | non_disease_segmentation | 不进入 disease_id |
| low water stress | `non_disease_water_stress` | stress | 不进入 disease_id |
| high water stress | `non_disease_water_stress` | stress | 不进入 disease_id |
| rice panicle | `rice_panicle` | crop_object | 非 disease |

## 按数据集映射建议

### BLB UAV Dataset

| source_class | mapped_id | 说明 |
| --- | --- | --- |
| BLB / Bacterial Leaf Blight | `bacterial_leaf_blight` | 可映射 |
| healthy rice / non-BLB | `healthy` 或 `background` | 需看 mask label 定义 |
| severity classes | `NEEDS_REVIEW_SEVERITY` | severity 不等于 disease_id |

### Weedy Rice RGB+MS

| source_class | mapped_id | 说明 |
| --- | --- | --- |
| weedy rice | `non_disease_weedy_rice` | 不进入 disease_id |
| cultivated rice / background | `background` | segmentation 背景 |

该数据集只用于 MS 处理、NDVI/NDRE、分割预训练，不用于病害模型指标声明。

### Indian Paddy UAV RGB+MS

| source_class | mapped_id | 说明 |
| --- | --- | --- |
| growth stage labels | `growth_stage:*` | 生育期 metadata，不是 disease_id |
| NDVI / NDRE maps | `index_feature` | 指数特征，不是 disease_id |
| disease labels | `NEEDS_REVIEW` | 若下载后发现病害标签再审 |

### msuav500k

| source_class | mapped_id | 说明 |
| --- | --- | --- |
| source project labels | `foundation_pretraining` | 不映射 disease_id |
| crop/scene metadata | `metadata_only` | 只做预训练/处理链路 |

### Maize Rust MS Dataset

| source_class | mapped_id | 说明 |
| --- | --- | --- |
| common rust | `NEEDS_REVIEW_NON_RICE` | 玉米锈病，不能映射为水稻病害 |
| healthy maize | `non_rice_healthy_crop` | 非水稻 |
| low/high water stress | `non_disease_water_stress` | 胁迫标签，不是病害 |
| soil/background | `background` | 背景 |

### Paddy Doctor

| source_class | mapped_id | 说明 |
| --- | --- | --- |
| Bacterial Leaf Blight | `bacterial_leaf_blight` | 可映射 |
| Bacterial Leaf Streak | `NEEDS_REVIEW` | 当前主知识库未稳定覆盖 |
| Bacterial Panicle Blight | `NEEDS_REVIEW` | 当前主知识库未稳定覆盖 |
| Black Stem Borer | `stem_borer_damage` | 需确认 pest/damage 口径 |
| Blast | `rice_blast` | 可映射 |
| Brown spot | `brown_spot` | 可映射 |
| Downy Mildew | `NEEDS_REVIEW` | 当前主知识库未稳定覆盖 |
| Hispa | `rice_hispa` | 需确认 target_type=pest |
| Leaf Roller | `leaf_folder_damage` | 需确认 leaf roller/folder 等价口径 |
| Tungro | `tungro` | 可映射 |
| White Stem Borer | `stem_borer_damage` | 需确认 |
| Yellow Stem Borer | `stem_borer_damage` | 需确认 |
| Normal leaf | `healthy` | 可映射 |

### Rice Leaf Bacterial and Fungal Disease Dataset

| source_class | mapped_id | 说明 |
| --- | --- | --- |
| Bacterial Leaf Blight | `bacterial_leaf_blight` | 可映射 |
| Brown Spot | `brown_spot` | 可映射 |
| Leaf scald | `NEEDS_REVIEW` | 当前主知识库未稳定覆盖 |
| Narrow Brown Leaf Spot | `NEEDS_REVIEW` | 不强行合并 |
| Rice Hispa | `rice_hispa` | 需确认 target_type=pest |
| Sheath Blight | `sheath_blight` | 可映射 |
| Leaf Blast | `rice_blast` | 可映射 |
| Healthy Rice Leaf | `healthy` | 可映射 |

### RiceSeg-5932

| source_class | mapped_id | 说明 |
| --- | --- | --- |
| Bacterial Blight | `bacterial_leaf_blight` | 可映射，但需确认是否等同 BLB |
| Leaf Blast | `rice_blast` | 可映射 |
| Brown Spot | `brown_spot` | 可映射 |
| Tungro | `tungro` | 可映射 |

### Rice Disease bbox dataset

| source_class | mapped_id | 说明 |
| --- | --- | --- |
| BacterialBlight | `bacterial_leaf_blight` | 可映射 |
| BrownSpot | `brown_spot` | 可映射 |
| RiceBlast | `rice_blast` | 可映射 |

## class_mapping.json 建议字段

```json
{
  "dataset_id": "example_dataset",
  "mapping_status": "draft",
  "rules": [
    {
      "source_label": "Bacterial Leaf Blight",
      "normalized_label": "bacterial leaf blight",
      "mapped_id": "bacterial_leaf_blight",
      "target_type": "disease",
      "status": "APPROVED",
      "notes": "BLB synonym"
    }
  ],
  "unmapped_labels": [
    {
      "source_label": "Narrow Brown Leaf Spot",
      "status": "NEEDS_REVIEW",
      "reason": "Do not force-map to brown_spot without expert confirmation."
    }
  ]
}
```

## 安全边界

- 类别映射只服务实验性数据准备，不代表正式诊断能力。
- `healthy` 不是 disease，不应在前端作为病害类别展示。
- pest 和 disease 必须分开建模或至少用 `target_type` 分离。
- severity label 不等于 disease_id，不得把严重度当成病害类别。
- 非水稻数据不得映射为水稻病害。
- 未确认类别必须保持 `NEEDS_REVIEW`。
