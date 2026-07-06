# P9 只读式独立验收审计报告

审计时间：2026-07-05  
审计范围：P9 多源数据融合风险建模与 UAV 指数异常算法增强  
审计方式：只读代码审计 + API 抽查 + 验证命令复跑  

## 1. 总体结论

结论：PASS

P9 当前实现已形成可运行闭环：

- UAV 指数异常分析链路可从 dry-run UAV 指数结果生成分析结果，并写入 `uav_index_analysis`。
- 多源风险融合链路可生成 `rule_weighted_score` 风险结果，并写入 `risk_feature_snapshots` 与 `risk_predictions`。
- 巡检报告已包含 `risk_model_detail`，并保留 `experimental`、`probability_claim=false` 等安全边界。
- 指定验证命令全部通过。

允许冻结 P9：允许。  
允许进入 P10：允许，建议带着下方测试覆盖缺口进入 P10 或后续补测任务。  

本轮是否修改代码：未修改业务代码、未新增功能、未改 `.env`、未替换模型、未进入 experimental ML 训练。  
本轮唯一产出为本只读验收报告。验证命令会产生测试数据、静态测试图片和前端构建产物，这是命令运行副作用，不属于业务代码修改。

## 2. 已确认闭环项

### 2.1 UAV 指数异常分析链路

已确认文件与接口：

- `POST /api/uav/tasks/{uav_task_id}/analyze-indices`
- `GET /api/uav/tasks/{uav_task_id}/index-analysis`
- `app/services/uav_index_analyzer.py`
- `uav_index_analysis`

审计结论：

- `uav_api.py` 已注册 `analyze-indices` 和 `index-analysis` 两个接口。
- `UAVIndexAnalyzer.analyze_uav_indices()` 会校验 UAV task、读取 `uav_index_results`、生成 NDVI/NDRE 分析并保存到 `uav_index_analysis`。
- `GET index-analysis` 在已有分析时读取落库结果；无分析时自动触发分析，闭环可用。
- 输出包含 `data_mode`、`is_mock`、`model_stage=experimental`、`probability_claim=false` 和安全说明。
- API 抽查确认：POST 和 GET 均返回 200，`uav_index_analysis` 中写入 2 条分析记录。

### 2.2 多源风险融合链路

已确认文件与接口：

- `POST /api/risk/fusion/evaluate`
- `GET /api/risk/fusion/{prediction_id}`
- `GET /api/risk/fusion/field/{field_id}`
- `app/services/risk_fusion_scorer.py`
- `app/api/risk_fusion_api.py`
- `risk_feature_snapshots`
- `risk_predictions`

审计结论：

- `risk_fusion_api.py` 已注册 evaluate、detail、field history 三个接口。
- `RiskFusionScorer.evaluate()` 会构建特征、计算分项风险、保存特征快照、保存融合结果，并回填 `prediction_id`。
- 分项风险包括 UAV、image、environment、growth_stage、history、treatment。
- `RiskFusionResponse` 默认包含 `model_type=rule_weighted_score`、`model_stage=experimental`、`probability_claim=false`、`experimental_only=true`、`not_for_production=true`。
- API 抽查确认：融合评估返回 200，详情查询返回 200，field 聚合查询返回 200。
- 非法 `uav_task_id` 抽查返回 400，错误码为 `UAV_TASK_NOT_FOUND`。
- 数据库抽查确认：`risk_feature_snapshots` 和 `risk_predictions` 均有对应记录。

### 2.3 巡检报告 risk_model_detail

已确认文件：

- `app/services/inspection_report_service.py`
- `app/schemas/inspection_report.py`
- `app/database/inspection_report_repositories.py`

审计结论：

- `InspectionReport` schema 已新增 `risk_model_detail`。
- `inspection_reports` 表已新增 `risk_model_detail_json`。
- 生成报告时会尝试调用 P9 风险融合评分；失败时返回 `status=unavailable` 占位，不中断原巡检报告。
- 抽查报告返回 200，`risk_model_detail.model_type=rule_weighted_score`，`risk_model_detail.probability_claim=false`。
- 报告 payload 中保留 `formal_metric_available=false` 和 `rule_weighted_risk_note`。

## 3. 安全边界复核

已确认：

- 未进入正式 ML 训练。
- 未声明正式发病概率。
- 未生成农药处方。
- 未生成剂量建议。
- 未声明 Precision / Recall / mAP / AUC 等正式模型指标。
- 未接入真实 UAV SDK、真实地图 API、真实天气 API。

文本扫描结果：

- P9 相关代码和报告中出现的 `probability`、`发病概率`、`农药处方` 等词汇均用于否定性边界说明或 `probability_claim=false`。
- `risk_predictions` 兼容旧表结构仍写入 `risk_probability=0.0`，但 P9 API 响应不暴露正式概率，并明确 `probability_claim=false`。建议后续前端或下游读取 `risk_predictions` 时优先识别 `model_type=rule_weighted_score` 与 `probability_claim=false`，避免误读旧字段。

## 4. 测试覆盖审计

已确认测试文件：

- `app/tests/test_p9_multisource_risk_fusion.py`
- `app/tests/test_p1_p4_inspection_loop.py`

已有覆盖：

- UAV 指数统计与 z-score 辅助函数。
- `POST analyze-indices` 正常输入。
- `GET index-analysis` 重复查询。
- `data_mode=dry_run`、`is_mock=true`、`probability_claim=false`。
- 风险融合分项打分边界。
- 空 weather 输入下 environment score 为 0。
- `POST /api/risk/fusion/evaluate` 正常输入。
- `GET /api/risk/fusion/{prediction_id}`。
- `GET /api/risk/fusion/field/{field_id}`。
- 巡检报告包含 `risk_model_detail`。

测试缺口：

- 未在测试文件中显式覆盖非法 `uav_task_id`，本次审计用 API 抽查确认该场景返回 `UAV_TASK_NOT_FOUND`。
- 未显式覆盖缺失 `field_id` 的请求体校验，即 422 场景。
- 未显式覆盖缺失 `prediction_id` 查询，即 `RISK_FUSION_NOT_FOUND` 场景。
- 未显式覆盖无 UAV task 的报告 `status=skipped_no_uav_task` 场景。
- 未直接断言数据库中 `uav_index_analysis`、`risk_feature_snapshots` 的行级字段完整性；本次审计用数据库抽查确认有落库记录。

以上缺口不阻塞 P9 冻结，但建议 P10 前后补充负例和持久化断言测试。

## 5. 阶段报告复核

复核文件：

- `F:/学校/病虫害识别/reports/p9_multisource_risk_modeling_uav_index_algorithm_report.md`

结论：

- 报告准确描述了当前已实现模块、API、数据库变更和巡检报告集成。
- 报告明确说明 experimental ML 训练接口尚未实现、未进入正式主链路。
- 报告明确说明当前结果不代表正式发病概率、不替代农技人员现场诊断、不作为农药处方依据。
- 未发现夸大模型能力的表述。

## 6. 验证命令结果

在当前环境中重新运行或确认：

- `python -m compileall app`：PASS
- `pytest -q`：PASS，`67 passed, 15 skipped`
- `python system_smoke_test.py`：PASS  
  实际命令使用 backend 根目录作为 `PYTHONPATH`：`$env:PYTHONPATH=(Get-Location).Path; python app/scripts/system_smoke_test.py`
- `python verify_p5_frontend_backend_contract.py`：PASS
- `cd mark-video-demo/frontend && npm.cmd run build`：PASS

API 抽查结果：

- `POST /api/uav/tasks/{uav_task_id}/analyze-indices`：200
- `GET /api/uav/tasks/{uav_task_id}/index-analysis`：200
- `POST /api/risk/fusion/evaluate`：200
- `GET /api/risk/fusion/{prediction_id}`：200
- `GET /api/risk/fusion/field/{field_id}`：200
- 非法 `uav_task_id` 风险融合请求：400，`UAV_TASK_NOT_FOUND`
- `POST /api/inspection-reports/generate`：200，包含 `risk_model_detail`

数据库抽查结果：

- `uav_index_analysis`：对应 UAV task 写入 2 条。
- `risk_feature_snapshots`：对应 field 写入记录。
- `risk_predictions`：对应 field 写入 `model_type=rule_weighted_score` 记录。

## 7. 风险与缺口

1. 测试负例覆盖不足：非法 task、缺失字段、缺失 prediction、无 UAV task 报告分支未正式纳入 pytest。
2. `risk_predictions.risk_probability=0.0` 是旧表兼容字段，虽然 P9 已用 `probability_claim=false` 约束，但下游展示仍需避免误读。
3. UAV 指数标准差在 dry-run 阶段按 `(max - min) / 6` 估算，真实像素矩阵接入后应替换为真实分布统计。
4. P9 阶段未实现 experimental ML 训练接口，这与阶段报告一致，不构成本轮验收阻塞。

## 8. 冻结与 P10 建议

是否允许冻结 P9：允许。

理由：

- 主链路闭环完整。
- 数据落库闭环完整。
- 巡检报告边界完整。
- 所有指定验证命令通过。
- 当前缺口主要是测试负例覆盖和后续实验能力，不影响 P9 已定义的规则评分闭环。

是否允许进入 P10：允许。

建议 P10 优先事项：

- 补充 P9 负例和数据库字段级断言测试。
- 明确前端展示时禁止把 `risk_probability` 旧字段作为发病概率展示。
- 若进入 ML 实验线，继续保持 `experimental_only=true`、`not_for_production=true`，不得进入正式诊断主链路。

## 9. 本轮只读承诺

本轮未修改业务代码。  
本轮未新增业务功能。  
本轮未修改 `.env`。  
本轮未替换模型。  
本轮未进入 experimental ML 训练。  
本轮未声明正式发病概率。  
本轮未生成农药处方或剂量建议。  

本轮仅新增本审计报告：`reports/p9_readonly_acceptance_audit_report.md`。
