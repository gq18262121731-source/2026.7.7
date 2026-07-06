# Stage6 Prediction Date Boundary Fix Report

修复时间：2026-07-03  
修复范围：最小测试数据修复。未修改 kg-rag-agent 实验线，未修改检测主逻辑，未修改 `/api/detect/image`，未修改 dashboard 统计口径，未安装依赖。

## 问题现象

全量 pytest 在 `stage6_prediction` 相关测试中出现唯一失败：

```text
45 passed, 1 failed, 15 skipped
```

失败发生在风险评分被天气、生育期和历史高风险记录推高到 100 后，测试期望新增“最近 7 天管护记录”能降低分数，但实际降低前后均为 100。

## 失败测试名称

```text
app/tests/test_stage6_prediction.py::test_history_weather_growth_raise_risk_and_operation_lowers_score
```

## 失败断言摘要

```text
assert lowered["risk_score"] < raised["risk_score"]
E assert 100 < 100
```

## 根因判断

`app/services/prediction/feature_builder.py` 中 `FeatureBuilder.build()` 使用：

```python
now = datetime.now(timezone.utc)
recent_operations_7 = [item for item in operations if self._within_days(item.operation_time, now, 7)]
```

测试中固定写死：

```text
2026-06-26T00:00:00Z
```

在当前日期 `2026-07-03` 执行时，该固定时间已经落在“最近 7 天”窗口边界之外或极易受执行时刻影响，导致：

- `operation_7d_count` 未稳定计入。
- `helpful_operation_7d_count` 未稳定计入。
- `recent_operation_7d` 减分不触发。
- 风险分数保持封顶值 100。

判断：这是测试 fixture 的日期边界/时间依赖问题，不是风险评分业务语义错误。

## 是否与 kg-rag-agent 有关

NO。

该测试路径属于 stage6 prediction：

- `app/tests/test_stage6_prediction.py`
- `app/services/prediction/feature_builder.py`
- `app/services/prediction/risk_rule_model.py`

与 `app/api/knowledge.py`、`app/api/agent.py`、`app/services/knowledge_service.py`、`rag_service.py`、`agent_service.py`、`llm_client.py` 无调用交集。

## 是否与 v0.6 主检测链路有关

NO。

未修改检测服务、模型路由、mock detector、`/api/detect/image`、dashboard 统计服务或模型状态接口。

## 修改文件列表

- `app/tests/test_stage6_prediction.py`
- `reports/stage6_prediction_date_boundary_fix_report.md`
- `reports/kg_rag_agent_v0_1_acceptance_audit.md`

## 修改理由

原测试使用固定历史时间验证“最近 7 天已有管护记录”，会随真实日期漂移。测试意图是验证近期有效管护记录能触发风险降低，而不是验证固定日期本身。

## 修复策略

采用策略 B：测试数据改为相对时间。

仅将失败测试中的 `operation_time` 从固定值：

```text
2026-06-26T00:00:00Z
```

改为测试执行时刻：

```python
datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
```

这样保证该操作记录稳定落入 `FeatureBuilder._within_days(..., days=7)` 的窗口内，同时不改变业务评分逻辑。

## 测试结果

执行环境：`backend\.venv\Scripts\python.exe`

| 检查项 | 结果 |
| --- | --- |
| 单个失败测试 | PASS，`1 passed, 1 warning` |
| `app/tests/test_stage6_prediction.py` | PASS，`7 passed, 1 warning` |
| 全量 pytest | PASS，`46 passed, 15 skipped, 1 warning` |
| compileall | PASS |
| system_smoke_test | PASS |
| `/api/status detector_mode` | PASS，`mock` |
| `/api/models/status detector_mode` | PASS，`mock` |
| `ultralytics` | PASS，`None` |
| `torch` | PASS，`None` |
| `torchvision` | PASS，`None` |

system smoke 覆盖项均通过：

- FastAPI app import
- SQLite
- static dirs writable
- healthz
- api status
- detect image
- static original/result
- record detail
- dashboard summary
- mobile overview
- alerts
- websocket results/tasks/alerts

## 剩余风险

- 当前测试仍有 `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated`，属于测试依赖生态警告，不影响本轮 gate。
- 同一测试文件中仍存在其他固定 `2026-06-26` 数据，但当前只用于天气观测和接口记录存在性校验，未触发 7 天窗口漂移失败；如后续业务增加日期过滤，建议统一改为相对日期。
- 本修复不改变 kg-rag-agent 能力边界；该实验模块仍不能声明为正式农学诊断能力。

## 最终 Gate

Gate：PASS

最终状态：

```text
PASS_AFTER_STAGE6_DATE_BOUNDARY_FIX
```

说明：

- 全量 pytest 已恢复通过。
- v0.6 mock 冻结状态不变。
- kg-rag-agent 后端实验线可进入前端最小展示，但不得声明为正式农学诊断能力。
