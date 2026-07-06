# P11-0 数据集落地计划

生成时间：2026-07-05

## 总体原则

本计划只规划数据集落地，不下载数据，不修改业务代码，不修改 `.env`，不替换现有模型，不进入正式 ML 主链路，不声明正式发病概率，不生成农药处方或剂量建议。

所有外部数据必须进入 experimental 数据目录：

```text
F:/学校/病虫害识别/ai_model_training/datasets_external/p11_open_datasets/
```

任何数据集在训练前必须具备：

- `source_card.json`
- `license.txt` 或 `license_summary.md`
- `dataset_manifest.json`
- `class_mapping.json`
- `split_plan.json`
- `integrity_check.json`

## 第一批建议下载或样例核验

| 数据集 | 建议状态 | 目标目录 | 进入训练前置条件 |
| --- | --- | --- | --- |
| Aligned RGB + Multispectral UAV Weedy Rice | first_batch_sample | `weedy_rice_rgb_ms_mendeley/` | 保存 CC BY 4.0；核验 RGB/MS/mask/metadata/split |
| Rice Leaf Bacterial and Fungal Disease Dataset | first_batch_sample | `rice_leaf_bacterial_fungal_mendeley/` | original 与 augmented 分离；类别映射完成 |
| RiceSeg-5932 | first_batch_sample | `riceseg_5932_masks_mendeley/` | 配套 Sethy 原图；文件名一一匹配 |
| Rice Disease bbox dataset | first_batch_sample | `rice_disease_bbox_datasetninja_kaggle/` | 保存 CC0；检查 bbox 格式并转 YOLO smoke |
| BLB UAV Dataset | first_batch_after_gate | `blb_uav_figshare/` | 确认数据许可、下载入口、波段和 mask 结构 |

## 第二批候选，不立即下载

| 数据集 | 原因 | 目标目录 | next_action |
| --- | --- | --- | --- |
| Paddy Doctor | 许可和下载入口未明确 | `paddy_doctor_official/` | 人工确认 license 与 download URL |
| Indian Paddy UAV RGB+MS | IEEE DataPort 访问门槛，约 415GB | `indian_paddy_uav_rgb_ms_ieee_dataport/` | 确认账号/订阅/许可，先记录 metadata |
| msuav500k | 约 185GB，非水稻病害 | `msuav500k_zenodo/` | 只先下载 `msdata-repo.zip` 或 metadata，不全量 |
| Maize Rust MS dataset | 非水稻，但可迁移 | `maize_rust_ms_zenodo/` | 先下载 README/LICENSE/metadata，再决定 patch sample |

## 目录规划

```text
ai_model_training/
  datasets_external/
    p11_open_datasets/
      blb_uav_figshare/
      weedy_rice_rgb_ms_mendeley/
      indian_paddy_uav_rgb_ms_ieee_dataport/
      msuav500k_zenodo/
      maize_rust_ms_zenodo/
      paddy_doctor_official/
      rice_leaf_bacterial_fungal_mendeley/
      riceseg_5932_masks_mendeley/
      rice_disease_bbox_datasetninja_kaggle/
```

## 每个数据集的落地检查项

### BLB UAV Dataset

- 是否需要类别映射：是，BLB -> `bacterial_leaf_blight`。
- 是否需要格式转换：可能需要，将 UAV MS bands/masks 转为统一 patch manifest。
- 是否需要去重：需要，尤其是 patch extraction 和 augmentation 后。
- 是否需要 train/val/test：需要，不能按 patch 随机泄漏同一地块或同一航线。
- 是否需要 held-out test 冻结：需要。
- 数据泄漏风险：高，同一正射图切出的 patch 不能跨 split。
- 是否可进入训练：`BLOCKED_UNTIL_LICENSE_AND_STRUCTURE_CONFIRMED`。

### Weedy Rice RGB+MS

- 是否需要类别映射：不映射到 disease_id，标记为 `non_disease_weedy_rice`。
- 是否需要格式转换：需要，统一 RGB/MS/mask/metadata 路径。
- 是否需要去重：需要核验重复文件和 overlay 派生文件。
- 是否需要 train/val/test：页面说明有 sample split，需要保留并核验。
- 是否需要 held-out test 冻结：需要。
- 数据泄漏风险：中，RGB/MS/overlay/mask 同源文件不能跨 split。
- 是否可进入训练：可进入 MS pipeline smoke / segmentation pretraining，不进入病害模型效果声明。

### Indian Paddy UAV RGB+MS

- 是否需要类别映射：无病害标签时不映射。
- 是否需要格式转换：需要，正射图、原始图、index maps、metadata 分开。
- 是否需要去重：需要。
- 是否需要 train/val/test：若用于 growth-stage/index baseline，需要按日期/田块划分。
- 是否需要 held-out test 冻结：需要。
- 数据泄漏风险：高，同一航次/同一区域不能跨 split。
- 是否可进入训练：`BLOCKED_BY_ACCESS_AND_SIZE`，只能先做 metadata audit。

### msuav500k

- 是否需要类别映射：不映射到 disease_id。
- 是否需要格式转换：需要，统一 band naming 和 sensor metadata。
- 是否需要去重：需要。
- 是否需要 train/val/test：若用于预训练，需要按 source project 分组拆分。
- 是否需要 held-out test 冻结：建议。
- 数据泄漏风险：中，跨项目分组是关键。
- 是否可进入训练：只允许 foundation/pretraining 或处理链路抽样。

### Maize Rust MS dataset

- 是否需要类别映射：`common_rust` 标记为 `NEEDS_REVIEW_NON_RICE`，不得映射为水稻病害。
- 是否需要格式转换：需要，six-channel GeoTIFF + mask 转统一格式。
- 是否需要去重：需要。
- 是否需要 train/val/test：需要。
- 是否需要 held-out test 冻结：需要。
- 数据泄漏风险：中，同一 orthomosaic patch 不能跨 split。
- 是否可进入训练：可进入迁移学习 smoke，不能声明水稻病害效果。

### Paddy Doctor

- 是否需要类别映射：是，且 disease/pest/healthy 必须分 target_type。
- 是否需要格式转换：需要，RGB/IR 与 metadata 对齐。
- 是否需要去重：需要。
- 是否需要 train/val/test：需要，按采集批次或地块分组更稳。
- 是否需要 held-out test 冻结：需要。
- 数据泄漏风险：中，近似样本和同叶片 RGB/IR 不能跨 split。
- 是否可进入训练：`BLOCKED_UNTIL_LICENSE_CONFIRMED`。

### Rice Leaf Bacterial and Fungal Disease Dataset

- 是否需要类别映射：是。
- 是否需要格式转换：需要，目录类别转统一 label CSV。
- 是否需要去重：需要。
- 是否需要 train/val/test：必须；original 与 augmented 必须先分组，增强图不得跨 split。
- 是否需要 held-out test 冻结：需要。
- 数据泄漏风险：高，augmented images 可能来自 original。
- 是否可进入训练：可进入 phone RGB classification baseline，条件是先完成去重和 split。

### RiceSeg-5932

- 是否需要类别映射：是。
- 是否需要格式转换：需要，mask JPG + original image 转 paired manifest。
- 是否需要去重：需要。
- 是否需要 train/val/test：必须按 original image 分组。
- 是否需要 held-out test 冻结：需要。
- 数据泄漏风险：高，mask-only 数据必须和原图版本一致。
- 是否可进入训练：`YES_AFTER_IMAGE_MASK_PAIRING`。

### Rice Disease bbox dataset

- 是否需要类别映射：是。
- 是否需要格式转换：需要，将 bbox 转 YOLO 或 COCO。
- 是否需要去重：需要。
- 是否需要 train/val/test：页面声称有 split 时应保留；若没有则按 image 分层拆分。
- 是否需要 held-out test 冻结：建议。
- 数据泄漏风险：中，数据量小导致评估不稳定。
- 是否可进入训练：只允许 YOLO smoke / demo。

## risk_fusion shadow model 边界

公共图像数据集不能直接生成当前系统 `risk_fusion` 所需的真实田块级标签。`risk_fusion` ML 训练需要来自本项目闭环数据：

- UAV task
- index_analysis
- phone review
- weather
- growth_stage
- history
- treatment feedback
- inspection report final decision

当前建议状态：

```text
risk_fusion_tabular_shadow_model = BLOCKED_FOR_LABELS
```

允许工作：

- 设计 feature schema。
- 建立数据抽取清单。
- 建立 label readiness dashboard。
- 做不训练的 shadow dataset manifest。

不允许工作：

- 用公共单图数据硬凑 field-level label。
- 声明正式发病概率。
- 将 rule_weighted_score 替换为正式 ML 概率。

## P11-1 是否允许进入

结论：PARTIAL。

允许进入：

- 数据样例下载。
- manifest / license / integrity / class_mapping / split_plan 建立。
- MS pipeline smoke。
- phone RGB baseline smoke。
- leaf lesion segmentation smoke。
- YOLO bbox smoke。

暂不允许进入：

- 正式主链路模型替换。
- 正式发病概率输出。
- risk_fusion ML 训练。
- 农药处方或剂量建议。

## 本轮验证结果

本轮验证使用后端虚拟环境：

```text
F:/学校/病虫害识别/agri_uav_disease_system/backend/.venv/Scripts/python.exe
```

| 命令 | 结果 | 说明 |
| --- | --- | --- |
| `python -m compileall app app/scripts` | PASS | `.venv` 下通过 |
| `pytest -q` | PASS | 71 passed, 16 skipped, 1 warning |
| `python system_smoke_test.py` | PASS | 以模块方式执行 `python -m app.scripts.system_smoke_test`，全部 smoke 项通过 |
| `python verify_p5_frontend_backend_contract.py` | PASS | 使用 `mark-video-demo/scripts/verify_p5_frontend_backend_contract.py`，全部契约项通过 |

备注：首次用系统 Anaconda Python 直接执行 `pytest -q` 时，因缺少 `fastapi` / `pydantic` 依赖在收集阶段失败；该结果判定为错误解释器环境问题。改用后端 `.venv` 后验证通过。

## 验收标准

- 所有数据集保存在 experimental 外部数据目录。
- 每个数据集都有 source card、license、manifest、mapping、split、integrity。
- 许可不明确的数据集不得训练。
- 大数据集不得盲目全量下载。
- 所有训练输出默认 `experimental_only=true`。
- 不把任何实验结果声明为正式发病概率、正式诊断或处方。
