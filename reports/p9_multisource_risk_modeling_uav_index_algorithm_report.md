# P9 多源数据融合风险建模与 UAV 指数异常算法增强报告

## 1. 本轮目标

在现有“UAV dry-run 异常发现 -> 手机复查 -> 巡检报告”闭环上，新增可解释的 UAV 指数异常分析和多源规则加权风险评分能力。P9 仅作为辅助识别、演示验证和后续机器学习实验的数据准备层，不声明生产级发病概率。

## 2. 新增算法模块

- `app/services/uav_index_analyzer.py`：计算 NDVI/NDRE 统计量、异常面积占比、指数异常分数和 UAV 异常等级。
- `app/services/risk_fusion_scorer.py`：融合 UAV、手机识别、天气、生育期、历史记录和治理反馈，输出综合风险分数。
- `app/database/risk_fusion_repositories.py`：保存 UAV 指数分析、风险特征快照和融合风险结果。
- `app/schemas/risk_fusion.py`：定义 P9 API 响应、风险快照和安全边界字段。

## 3. UAV 指数异常分析方法

当前 dry-run 阶段复用已有 `uav_index_results` 中的 NDVI/NDRE 均值、最小值、最大值和异常面积占比。标准差在缺少真实像素矩阵时按 `(max - min) / 6` 估算，并保留 `data_mode=dry_run`、`is_mock=true`。

异常等级采用经验规则：

- `normal`
- `mild_abnormal`
- `moderate_abnormal`
- `severe_abnormal`

UAV 风险分数封顶为 30，并在 NDVI 与 NDRE 同时异常、异常面积占比较高时增加规则贡献。

## 4. 多源风险评分公式

综合风险分数：

```text
TotalRiskScore =
UAVRiskScore
+ ImageRiskScore
+ EnvironmentRiskScore
+ GrowthStageRiskScore
+ HistoryRiskScore
+ TreatmentRiskScore
```

分数截断到 `0-100`，等级为：

- `low`: 0-39
- `medium`: 40-69
- `high`: 70-100

所有输出均包含 `model_type=rule_weighted_score`、`model_stage=experimental`、`probability_claim=false`。

## 5. 数据库变更

新增：

- `uav_index_analysis`
- `risk_feature_snapshots`

扩展：

- `risk_predictions` 增加各分项风险分、`factor_scores_json`、`model_stage`、`probability_claim`
- `inspection_reports` 增加 `risk_model_detail_json`

数据库初始化仍走现有 `init_db()`，使用 `CREATE TABLE IF NOT EXISTS` 和 `_ensure_column()` 保持增量兼容。

## 6. API 变更

新增 UAV 指数分析接口：

- `POST /api/uav/tasks/{uav_task_id}/analyze-indices`
- `GET /api/uav/tasks/{uav_task_id}/index-analysis`

新增多源风险融合接口：

- `POST /api/risk/fusion/evaluate`
- `GET /api/risk/fusion/{prediction_id}`
- `GET /api/risk/fusion/field/{field_id}`

## 7. 巡检报告集成

`InspectionReport` 新增顶层字段 `risk_model_detail`，报告生成时会尝试执行 P9 多源风险评分，并展示：

- 分项风险贡献
- 综合风险分
- 风险等级
- 主要风险因素
- 安全说明

若 P9 风险评分不可用，报告不会中断，会返回 `status=unavailable` 的风险详情占位。

## 8. 前端展示增强

本轮未改前端代码。后续可在巡田页和报告详情页展示：

- UAV 指数分析卡片
- 风险因子贡献条
- `main_factors` 风险解释
- 固定安全说明

## 9. 测试结果

已新增测试：

- `test_uav_index_analyzer_statistics_zscore_and_level`
- `test_risk_fusion_component_scores_are_bounded_and_safe`
- `test_risk_fusion_api_and_report_detail`

并扩展 P1-P4 巡检闭环测试，确认报告包含 `risk_model_detail`。

## 10. 能力边界

当前风险结果为规则加权评分与实验性机器学习数据准备能力，不代表正式发病概率，不替代农技人员现场诊断，不作为农药处方依据。

当前未接入真实无人机 SDK、真实地图 API、真实天气 API。UAV 指数分析仍支持 dry-run/mock 占位数据，机器学习实验接口本轮未进入正式主链路。

## 11. 未完成事项

- experimental ML 训练接口尚未实现。
- 前端报告详情页尚未展示 P9 风险因子贡献。
- 真实多光谱像素矩阵接入后，可替换当前 dry-run 标准差估算逻辑。

## 12. 下一阶段建议

- 增加 `risk_feature_snapshots` CSV 导出。
- 增加 experimental LogisticRegression / RandomForest 离线训练服务。
- 在前端报告详情页增加风险因子贡献可视化。
- 在真实 UAV 数据接入后，用像素矩阵计算真实 NDVI/NDRE 分布统计。
