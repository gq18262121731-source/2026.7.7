# P10 当前公式与模型口径只读审计说明

审计对象：

- `F:/学校/病虫害识别/agri_uav_disease_system/backend/app/services/uav_index_analyzer.py`
- `F:/学校/病虫害识别/agri_uav_disease_system/backend/app/services/risk_fusion_scorer.py`
- 辅助核对：`F:/学校/病虫害识别/agri_uav_disease_system/backend/app/schemas/risk_fusion.py`

审计结论：当前 P9/P10 相关实现仍为规则型辅助分析链路，不属于正式机器学习风险预测链路；未进入 experimental ML 训练；未使用训练得到的正式概率；输出 schema 中继续保留 `experimental`、`rule_weighted_score`、`probability_claim=false` 等安全边界。

本轮动作说明：本轮仅阅读算法服务与 schema，并新增本说明文档；未修改业务代码，未修改 `.env`，未替换模型，未进入 ML 训练，未新增正式概率、处方或剂量建议。

## 1. 当前是否使用机器学习模型

未在本次审计的两份算法服务中发现新的机器学习模型训练、加载或推理逻辑。

- `uav_index_analyzer.py`：从 UAV 指数结果表读取已有 `mean_value`、`min_value`、`max_value`、`threshold_used`、`abnormal_area_ratio` 等字段，按规则计算指数异常等级和 UAV 风险分。
- `risk_fusion_scorer.py`：融合 UAV 指数、手机复查识别结果、天气、作物生育期、历史记录、近期处置反馈等特征，按规则累加得到 `rule_weighted_score`。

注意：`risk_fusion_scorer.py` 会读取手机复查识别记录中的 `main_disease`、`max_confidence`、`severity` 等结果字段，但当前多源融合算法本身没有训练模型，也没有把融合结果定义为正式模型推理结论。

## 2. 当前是否使用训练得到的概率

当前 UAV 指数异常分析不使用训练得到的概率。

当前多源风险融合不输出训练得到的正式概率。`phone_confidence` 仅作为手机复查识别结果中的置信度输入参与规则评分，计算方式是 `疾病基础权重 * phone_confidence + 严重度加分`，该值不应被前端展示或解释为正式发病概率。

schema 中的安全边界：

- `UavIndexAnalysisResponse.probability_claim = false`
- `RiskFeatureSnapshot.probability_claim = false`
- `RiskFusionResponse.probability_claim = false`
- `RiskFusionResponse.experimental_only = true`
- `RiskFusionResponse.not_for_production = true`
- `RiskFusionResponse.model_type = "rule_weighted_score"`
- `RiskFusionResponse.model_stage = "experimental"`

## 3. NDVI / NDRE 是否在代码中被直接计算

未在当前两份算法服务中发现 NDVI / NDRE 从波段值直接计算的实现。

也就是说，当前代码没有执行如下指数公式：

- NDVI：未在代码中计算 `(NIR - Red) / (NIR + Red)`
- NDRE：未在代码中计算 `(NIR - RedEdge) / (NIR + RedEdge)`

当前实现读取的是已有 UAV 指数结果字段，主要包括：

- `index_type`
- `mean_value`
- `min_value`
- `max_value`
- `threshold_used`
- `abnormal_area_ratio`
- `data_mode`
- `is_mock`

若缺少标准差字段，当前代码用最小值和最大值估算：

```text
std = max((max_value - min_value) / 6.0, 0.01)
```

若 `min_value` 或 `max_value` 缺失，则：

```text
std = 0.05
```

`calculate_zscore_anomaly(values)` 中存在对数值列表做 z-score 异常统计的通用方法，但它也不负责从光谱波段计算 NDVI / NDRE。

## 4. UAV index_analysis 的异常分数如何计算

单个指数的分析流程：

```text
mean = item.mean_value
std = estimate_std(item)
ratio = item.abnormal_area_ratio or 0
threshold = item.threshold_used if exists else mean - 1.5 * std
z_value = (threshold - mean) / std
```

单个指数异常等级：

| 条件 | abnormal_level |
| --- | --- |
| `z_value <= -2.5` 或 `ratio >= 0.25` | `severe_abnormal` |
| `z_value <= -2.0` 或 `ratio >= 0.15` | `moderate_abnormal` |
| `z_value <= -1.5` 或 `ratio >= 0.05` | `mild_abnormal` |
| 其他 | `normal` |

单个指数异常分：

| abnormal_level | index_anomaly_score |
| --- | ---: |
| `normal` | 0 |
| `mild_abnormal` | 8 |
| `moderate_abnormal` | 15 |
| `severe_abnormal` | 22 |

UAV 总风险分计算：

```text
score = max(index_anomaly_score)

if 异常指数类型数量 >= 2:
    score += 3

if max_abnormal_area_ratio > 0.2:
    score += 5
elif max_abnormal_area_ratio > 0.1:
    score += 3

uav_risk_score = min(30, round(score))
```

UAV 总异常等级：

| uav_risk_score | uav_abnormal_level |
| ---: | --- |
| `>= 23` | `severe_abnormal` |
| `>= 15` | `moderate_abnormal` |
| `>= 8` | `mild_abnormal` |
| `< 8` | `normal` |

## 5. risk_fusion 的 rule_weighted_score 如何计算

`risk_fusion_scorer.py` 中的总分计算逻辑为：

```text
factor_scores = {
    "uav": score_uav_risk(features),
    "image": score_image_risk(features),
    "environment": score_environment_risk(features),
    "growth_stage": score_growth_stage_risk(features),
    "history": score_history_risk(features),
    "treatment": score_treatment_risk(features),
}

total_risk_score = max(0, min(100, sum(factor_scores.values())))
risk_level = risk_level(total_risk_score)
```

因此当前融合模型不是百分比概率模型，而是多个规则因子的加权/加分结果，最终截断在 `0..100` 区间内。

## 6. factor_scores 的来源

| factor | 来源 | 说明 |
| --- | --- | --- |
| `uav` | UAV 指数异常分析 | 来自 `uav_index_analyzer.get_index_analysis()` 与 `calculate_uav_risk_score()` |
| `image` | 手机复查识别或异常区域确认结果 | 使用 `disease_type`、`phone_confidence`、`severity_level` |
| `environment` | 最近天气记录 | 使用湿度、降雨、连续降雨天数、温湿组合 |
| `growth_stage` | 地块当前生育期或 UAV 任务生育期 | 使用生育期基础分，并按病害类型给少量敏感期加分 |
| `history` | 同一 field/plot 的历史识别记录 | 判断是否存在同病害或其他历史记录 |
| `treatment` | 最近农事操作记录 | 根据近期反馈文本降低或提高规则分 |

## 7. 每个 factor 的权重与规则

当前不是固定百分比权重，而是各因子的规则加分上限或取值范围。

| factor | 当前范围/上限 | 计算口径 |
| --- | ---: | --- |
| `uav` | `0..30` | 直接采用 UAV 总风险分 |
| `image` | `0..30` | `疾病基础权重 * phone_confidence + severity_bonus`，再截断到 30 |
| `environment` | `0..20` | 湿度、连续降雨、7 日降雨、温湿组合加分，再截断到 20 |
| `growth_stage` | `0..10` | 生育期基础分 + 特定病害敏感期加分，再截断到 10 |
| `history` | `0/4/8/10` | 无历史为 0；有其他历史为 4；同病害一次为 8；同病害两次及以上为 10 |
| `treatment` | `-8/-3/0/+8` | 改善类反馈减 8；处置无明确变化减 3；恶化类反馈加 8 |

`image` 因子的疾病基础权重：

| disease_type | base_weight |
| --- | ---: |
| `healthy` | 0 |
| `brown_spot` | 12 |
| `false_smut` | 15 |
| `bacterial_blight` | 18 |
| `bacterial_leaf_blight` | 18 |
| `sheath_blight` | 20 |
| `rice_blast` | 22 |
| `unknown_disease` | 10 |
| `planthopper_damage` | 18 |
| `leaf_folder_damage` | 16 |
| `stem_borer_damage` | 18 |
| 其他未知非空 disease | 10 |

`image` 因子的严重度加分：

| severity_level | bonus |
| --- | ---: |
| `mild` / `light` | 2 |
| `medium` / `moderate` | 5 |
| `severe` | 8 |

`environment` 因子的规则：

| 条件 | 加分 |
| --- | ---: |
| 平均湿度 `> 90` | +8 |
| 平均湿度 `> 85` | +6 |
| 连续降雨天数 `>= 3` | +7 |
| 连续降雨天数 `>= 2` | +4 |
| 7 日降雨量 `>= 30mm` | +4 |
| 平均湿度 `> 85` 且平均温度 `>= 25` | +5 |

`growth_stage` 基础分：

| growth_stage | base_score |
| --- | ---: |
| `seedling` | 3 |
| `tillering` | 6 |
| `jointing_booting` | 8 |
| `heading_flowering` | 8 |
| `filling` | 6 |
| `maturity` | 4 |
| 未识别但非空 | 3 |

特定病害和敏感生育期组合会额外加 2 分，最终仍截断到 10 分。

## 8. 风险等级阈值

当前 `risk_fusion` 只实现了 `low / medium / high` 三档，没有实现 `critical` 阈值。

| total_risk_score | risk_level |
| ---: | --- |
| `0..39` | `low` |
| `40..69` | `medium` |
| `70..100` | `high` |
| N/A | `critical` 当前未实现 |

因此 P10 前端不应展示 `critical` 作为当前后端已支持的融合风险等级，除非后续业务代码明确新增该等级。

## 9. probability_claim=false 是否贯穿输出

是。当前 schema 对 UAV 指数异常分析、多源风险特征快照、多源风险融合响应均设置了 `probability_claim=false`。

前端展示时应保留并显式使用以下安全字段：

- `model_type = "rule_weighted_score"`
- `model_stage = "experimental"`
- `probability_claim = false`
- `experimental_only = true`
- `not_for_production = true`
- `safety_note`

同时，不应把 `total_risk_score`、`uav_risk_score`、`index_anomaly_score` 或 `phone_confidence` 展示为正式发病概率。

## 10. 当前前端 P10 第三刀建议展示字段

### UAV 指数异常分析建议展示

建议展示：

- `uav_task_id`
- `field_id`
- `data_mode`
- `is_mock`
- `model_stage`
- `probability_claim`
- `safety_note`
- `uav_risk_score`
- `uav_abnormal_level`
- `main_reasons`
- `analysis[].index_type`
- `analysis[].mean_value`
- `analysis[].std_value`
- `analysis[].min_value`
- `analysis[].max_value`
- `analysis[].z_threshold`
- `analysis[].abnormal_area_ratio`
- `analysis[].index_anomaly_score`
- `analysis[].abnormal_level`
- `analysis[].main_reasons`

建议文案口径：

- 指数异常提示
- UAV 植被指数异常分
- 异常区域占比
- 实验性辅助分析
- 巡检优先级参考

### 多源风险融合建议展示

建议展示：

- `prediction_id`
- `field_id`
- `uav_task_id`
- `abnormal_region_id`
- `phone_image_id`
- `disease_type`
- `total_risk_score`
- `risk_level`
- `factor_scores`
- `main_factors`
- `feature_snapshot_id`
- `model_type`
- `model_stage`
- `probability_claim`
- `experimental_only`
- `not_for_production`
- `safety_note`
- `created_at`

建议将 `factor_scores` 拆成可读条目：

- UAV 指数异常分：`factor_scores.uav`
- 手机复查识别辅助分：`factor_scores.image`
- 天气环境压力分：`factor_scores.environment`
- 生育期敏感性分：`factor_scores.growth_stage`
- 历史记录分：`factor_scores.history`
- 近期处置反馈修正分：`factor_scores.treatment`

### 巡检报告 risk_model_detail 建议展示

建议展示：

- `rule_weighted_score`
- `risk_level`
- `factor_scores`
- `main_factors`
- `model_stage = experimental`
- `probability_claim = false`
- UAV 指数异常摘要
- 手机复查识别摘要
- 规则融合来源说明

建议说明：

```text
该结果仅用于实验性辅助分析和巡检优先级参考，不代表正式诊断结论。
```

## 11. 当前前端 P10 第三刀应避免展示的字段与文案

避免展示或避免解释为正式结论：

- 不展示“发病概率”
- 不展示“预测概率”
- 不展示“确诊”
- 不展示“处方”
- 不展示“建议用药剂量”
- 不展示“正式模型精度”
- 不展示 Precision / Recall / mAP / AUC 等未由当前链路验证的正式指标
- 不把 `phone_confidence` 解释为地块级发病概率
- 不把 `total_risk_score` 解释为发病概率
- 不把历史兼容字段中的概率类字段作为正式概率展示

推荐替代口径：

- 风险评分
- 异常提示
- 辅助判断
- 实验性分析
- 巡检优先级建议
- 规则加权分

## 12. 安全边界复核结论

当前算法口径可以概括为：

```text
P9/P10 当前链路 = UAV 指数异常规则分析 + 多源规则加权风险评分
```

不是：

```text
正式 ML 发病概率预测
正式诊断模型
正式防治处方系统
正式剂量建议系统
```

因此，P10 前端第三刀可以接入和展示当前字段，但必须保持“实验性辅助分析 / 风险评分 / 异常提示 / 巡检优先级参考”的产品口径，不应展示或暗示正式概率、正式确诊、处方或剂量建议。
