# kg-rag-agent-v0.1-experimental Acceptance Audit

审计时间：2026-07-03  
审计性质：只读验收审计。除新增本报告外，未新增功能、未修改业务逻辑、未修改已有接口行为、未安装依赖。

## 审计范围

- `knowledge/diseases/` 四个病害 JSON。
- `knowledge/rag/source_catalog.json` 与 `rag_chunks.jsonl`。
- `knowledge/graph/kg_entities.json`、`kg_relations.json`、`kg_triples.json`。
- experimental API：
  - `GET /api/knowledge/diseases`
  - `GET /api/knowledge/diseases/{disease_id}`
  - `POST /api/knowledge/search`
  - `POST /api/agent/diagnosis-report`
- Agent 输出安全口径。
- v0.6 冻结链路回归项。

## 文件完整性检查

| 文件/目录 | 结果 |
| --- | --- |
| `knowledge/diseases/bacterial_leaf_blight.json` | PASS |
| `knowledge/diseases/rice_blast.json` | PASS |
| `knowledge/diseases/brown_spot.json` | PASS |
| `knowledge/diseases/tungro.json` | PASS |
| `knowledge/rag/source_catalog.json` | PASS，9 个来源 |
| `knowledge/rag/rag_chunks.jsonl` | PASS，20 个 chunk |
| `knowledge/graph/kg_entities.json` | PASS，55 个实体 |
| `knowledge/graph/kg_relations.json` | PASS，11 个关系 |
| `knowledge/graph/kg_triples.json` | PASS，48 条三元组 |

## 数据 Schema 检查

四个 disease JSON 均包含以下核心字段：

- `disease_id`
- `zh_name`
- `en_name`
- `aliases`
- `pathogen_type`
- `pathogen_name`
- `affected_crop`
- `affected_parts`
- `typical_symptoms`
- `early_symptoms`
- `late_symptoms`
- `similar_diseases`
- `favorable_conditions`
- `transmission`
- `risk_notes`
- `management_suggestions`
- `model_class_mapping`
- `evidence_sources`
- `authority_level`
- `last_updated`

| disease_id | 字段完整性 | evidence_sources | source_catalog 映射 | authority_level |
| --- | --- | ---: | --- | --- |
| `bacterial_leaf_blight` | PASS | 3 | PASS | A |
| `rice_blast` | PASS | 3 | PASS | A |
| `brown_spot` | PASS | 3 | PASS | A |
| `tungro` | PASS | 3 | PASS | A |

## KG 检查

- `kg_entities.json` 可读取：PASS。
- `kg_relations.json` 可读取：PASS。
- `kg_triples.json` 可读取：PASS。
- 每条 triple 的 `subject` 均存在于 entities：PASS。
- 每条 triple 的 `object` 均存在于 entities：PASS。
- 每条 triple 的 `predicate` 均存在于 relations：PASS。
- 每条 triple 的 `evidence_source_ids` 非空：PASS。
- triple 引用的 source_id 均存在于 source catalog：PASS。

| disease_id | 关联三元组数 | 要求 |
| --- | ---: | --- |
| `bacterial_leaf_blight` | 12 | PASS，>= 8 |
| `rice_blast` | 13 | PASS，>= 8 |
| `brown_spot` | 13 | PASS，>= 8 |
| `tungro` | 12 | PASS，>= 8 |

## RAG 检查

- `rag_chunks.jsonl` 可逐行解析：PASS。
- 每个 chunk 均有 `source_id`：PASS。
- 每个 `source_id` 均可在 `source_catalog.json` 中找到：PASS。
- 每个 `section_type` 均在允许范围内：PASS。

允许范围：`symptom`、`cause`、`condition`、`transmission`、`management`、`differential_diagnosis`、`model_boundary`、`demo_safety`、`risk_note`。

| disease_id | chunk 数 | 要求 |
| --- | ---: | --- |
| `bacterial_leaf_blight` | 5 | PASS，>= 5 |
| `rice_blast` | 5 | PASS，>= 5 |
| `brown_spot` | 5 | PASS，>= 5 |
| `tungro` | 5 | PASS，>= 5 |

section 分布：

- `symptom`: 4
- `cause`: 4
- `condition`: 3
- `management`: 4
- `model_boundary`: 2
- `differential_diagnosis`: 2
- `transmission`: 1

## API 检查

使用 `backend\.venv\Scripts\python.exe` 与 FastAPI `TestClient` 进行只读调用。

| 样例 | 结果 |
| --- | --- |
| `GET /api/knowledge/diseases` | PASS，200 |
| `GET /api/knowledge/diseases/bacterial_leaf_blight` | PASS，200 |
| `GET /api/knowledge/diseases/not_exist` | PASS，404 |
| `POST /api/knowledge/search` 查询“白叶枯病症状” | PASS，200，返回 5 条结果 |
| `POST /api/agent/diagnosis-report` 输入 `bacterial_leaf_blight + uav_blb + confidence=0.72` | PASS，200 |
| `POST /api/agent/diagnosis-report` 输入 unknown `model_class` | PASS，200，`insufficient_evidence=true` |
| `POST /api/agent/diagnosis-report` 输入 `tungro` | PASS，200 |

## Agent 输出安全检查

| 检查项 | 结果 |
| --- | --- |
| 不把模型结果说成最终诊断 | PASS；BLB 报告未出现“最终诊断”表述 |
| 包含 `uncertainty_notes` | PASS |
| 包含 `evidence_sources` | PASS；unknown evidence 不足场景除外 |
| 不输出绝对化农药用量 | PASS；未发现“每亩”等强制用量表达 |
| mock / smoke / experimental 状态下有边界说明 | PASS |
| unknown 输入返回 `insufficient_evidence` 或 `unknown_mapping` | PASS；返回 `insufficient_evidence=true` |
| tungro 有额外风险保护说明 | PASS；新增测试 `test_agent_unknown_mapping_and_tungro_boundary` 已覆盖并通过 |

备注：PowerShell 终端显示中文时存在编码乱码，但 UTF-8 pytest 断言已验证 tungro 风险保护短语存在。

## v0.6 冻结链路回归检查

| 回归项 | 结果 |
| --- | --- |
| `compileall` | PASS |
| `pytest` | PASS_AFTER_FIX；原始审计为 45 passed, 1 failed, 15 skipped, 1 warning；修复后为 46 passed, 15 skipped, 1 warning |
| `system_smoke_test` | PASS |
| `/api/status detector_mode` | PASS，`mock` |
| `/api/models/status detector_mode` | PASS，`mock` |
| `ultralytics` | PASS，`None` |
| `torch` | PASS，`None` |
| `torchvision` | PASS，`None` |

原始只读审计发现的 pytest 失败项：

- `app/tests/test_stage6_prediction.py::test_history_weather_growth_raise_risk_and_operation_lowers_score`
- 失败断言：`assert lowered["risk_score"] < raised["risk_score"]`，实际为 `100 < 100`。
- 初步判断：该失败与本实验线无直接调用路径交集；更像既有 stage6 prediction 测试在当前日期 `2026-07-03` 下对固定操作时间 `2026-06-26T00:00:00Z` 的“最近 7 天”边界敏感，导致风险分数到 100 后无法下降。
- 后续修复见 `reports/stage6_prediction_date_boundary_fix_report.md`，已采用相对时间测试数据消除日期边界漂移。

## Git 仓库状态说明

在 `F:\学校\病虫害识别` 执行：

```powershell
git status --short --branch
```

结果：

```text
fatal: not a git repository (or any of the parent directories): .git
```

因此本轮无法通过 Git 输出工作区 diff 或分支状态。此前实验线也已记录该本地 Git 识别异常。

## 结论 Gate

Gate：PASS_AFTER_STAGE6_DATE_BOUNDARY_FIX

理由：

- KG/RAG/Agent 实验线的数据完整性、API 可用性、证据来源、安全输出口径均通过验收。
- v0.6 运行链路关键项通过：`detector_mode=mock`、`system_smoke_test=PASS`、`/api/detect/image` 在 smoke test 中返回 200、dashboard smoke 覆盖通过。
- 冻结 Mock 环境未安装 `ultralytics`、`torch`、`torchvision`。
- 2026-07-03 已通过 `reports/stage6_prediction_date_boundary_fix_report.md` 完成 stage6 日期边界最小修复。
- 修复后全量 pytest 恢复为 `46 passed, 15 skipped, 1 warning`，v0.6 mock 冻结状态不变。

kg-rag-agent 后端实验线可进入前端最小展示；仍不得将 kg-rag-agent 模块声明为正式农学诊断能力。
