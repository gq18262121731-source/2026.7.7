# 病虫害识别系统

这是一个私有项目仓库，用于管理病虫害识别系统的源码、训练脚本、接口文档和集成资料。

## 目录

- `agri_uav_disease_system/`：无人机水稻病虫害识别后端系统。
- `mark-video-demo/`：前后端演示平台。
- `ai_model_training/`：模型训练、数据处理、评估与交付脚本。
- `mobile_llm_integration_package/`：移动端与大模型接口集成资料。
- `reports/`：项目审计、计划和阶段报告。

## 未纳入 Git 的本地内容

为了让 GitHub 仓库保持轻量并避免误传敏感或大体积文件，以下内容已通过 `.gitignore` 排除：

- Python/Node 依赖目录和本地虚拟环境。
- 原始数据集、派生数据集、训练运行输出和模型权重。
- 本地实验目录 `code/` 和 `ai_model_training/experiments/`。
- 后端本地上传图片、识别结果图片、SQLite 数据库。
- 日志、缓存、压缩包、本地 token 和证书类文件。

如需共享数据集或模型权重，建议使用对象存储、Release 附件或 Git LFS，并单独记录版本与校验信息。
