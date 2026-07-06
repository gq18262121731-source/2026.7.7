# P11-0 开源数据集调研与落地审计报告

生成时间：2026-07-05

## 审计结论

本轮完成 P11-0 数据集调研、许可核验、下载可行性判断和训练适配审计。未下载数据，未修改后端主链路，未修改 `.env`，未替换现有模型，未进入 ML 训练，未声明正式发病概率，未生成农药处方或剂量建议。

总体建议：P11-1 可以进入“样例下载、source card、manifest、class mapping、split plan、完整性校验”的数据准备阶段；不建议直接进入正式训练。`risk_fusion` 的 tabular shadow model 仍应标记为 `BLOCKED_FOR_LABELS`，因为公共单图/单数据集无法提供本项目所需的同一田块闭环标签。

## 数据集总览

| 优先级 | 数据集 | 平台 | access_status | 许可 | 作物/场景 | 标注类型 | 建议 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HIGH | BLB UAV Dataset | PLOS One / Figshare / Google Drive | partially_accessible | 待核验数据集许可 | rice / UAV multispectral BLB | semantic segmentation | 第一批候选，但必须先确认数据许可和下载入口 |
| HIGH | A Dataset of Aligned RGB and Multispectral UAV Imagery for Semantic Segmentation of Weedy Rice | Mendeley Data | accessible | CC BY 4.0 | rice field / UAV RGB+MS | binary segmentation mask + metadata | 第一批样例下载，适合 index calculator / MS pipeline |
| MEDIUM | Indian Paddy UAV RGB + Multispectral Multi-stage Dataset | arXiv / IEEE DataPort | subscription_or_account_required | IEEE DataPort 侧待核验 | rice / UAV RGB+MS / growth stages | metadata / index maps; disease label unclear | 候选，不建议立即下载 |
| MEDIUM | msuav500k | Zenodo | accessible, very_large | CC BY 4.0 | multi-crop / UAV RGB+MS | foundation data, no rice disease label | 只做预训练/处理链路抽样，不做水稻病害主数据 |
| MEDIUM | UAV-Based Multispectral Maize Dataset for Water Stress and Common Rust | Zenodo | accessible | CC BY 4.0 | maize / UAV multispectral | semantic segmentation masks | 迁移学习和 MS segmentation smoke |
| HIGH | Paddy Doctor | 官方站点 | page_accessible, license_unclear | 未在页面明确 | paddy / phone RGB+IR close-up | classification + metadata | 适合手机复查，但许可未确认前不训练 |
| HIGH | Rice Leaf Bacterial and Fungal Disease Dataset | Mendeley Data | accessible | CC BY 4.0 | rice leaf close-up | classification | 第一批 phone RGB baseline 候选 |
| HIGH | RiceSeg-5932 | Mendeley Data | accessible | CC BY 4.0 | rice leaf close-up | segmentation masks only | 第一批 leaf lesion segmentation 候选，需配套原图 |
| MEDIUM | Rice Disease Dataset with Bounding Boxes | Dataset Ninja / Kaggle | accessible, Kaggle_download | CC0 1.0 | rice leaf close-up | bbox object detection | YOLO smoke/demo，不夸大效果 |

## A. UAV / 多光谱 / 水稻或近似场景

### 1. BLB UAV Dataset

- 来源平台：PLOS One 论文页面，数据入口指向 Figshare / Google Drive。
- 入口：<https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0314535>
- 下载入口是否可用：PLOS 页面可访问；Figshare/Google Drive 数据入口需单独人工确认。当前未下载。
- 许可协议：PLOS 论文为开放访问；数据集本身许可需以 Figshare/Google Drive 页面为准，不能只用论文许可替代数据许可。
- 数据规模：论文描述为自建 field-scale rice BLB UAV multispectral 数据集，使用 patch extraction 和 augmentation；具体原始文件规模需在数据页确认。
- 作物类型：rice。
- 采集视角：UAV / field-scale。
- 模态：multispectral，并比较 multispectral、multispectral+NDVI、multispectral+NDRE。
- 标注类型：BLB semantic segmentation mask / severity mapping 相关。
- 适合训练的模型类型：UAV BLB semantic segmentation，U-Net / DeepLabV3+ / SegFormer，NDVI/NDRE 多输入实验。
- 是否适合当前项目：高度适合当前 P11 的 UAV 病害分割方向。
- 风险：下载入口需确认；数据许可需确认；若只提供预处理 patch 而不含原始波段，需要限制为分割实验；不能把论文报告指标迁移为本项目模型指标。
- 建议优先级：HIGH，但设置 `LICENSE_AND_ACCESS_GATE`。

### 2. A Dataset of Aligned RGB and Multispectral UAV Imagery for Semantic Segmentation of Weedy Rice

- 来源平台：Mendeley Data。
- 入口：<https://data.mendeley.com/datasets/vt4s83pxx6>
- 下载入口是否可用：页面可访问，Download All 按钮由页面加载；建议先小规模下载或使用 Mendeley 目录结构核验。
- 许可协议：CC BY 4.0。
- 数据规模：734 组 UAV RGB + aligned multispectral samples。
- 作物类型：cultivated rice field / weedy rice。
- 采集视角：UAV。
- 模态：RGB + four MS bands: Green / Red / RedEdge / NIR。
- 标注类型：binary segmentation mask、overlay、metadata、sample train/val/test split。
- 数据结构：RGB、Multispectral、Masks、Overlay、Metadata。
- 适合训练的模型类型：multi-modal semantic segmentation、UAV multispectral reader、NDVI/NDRE calculator smoke、band alignment pipeline。
- 是否适合当前项目：适合 P11 的指数计算、波段读取、NDVI/NDRE 验证和非病害预训练；不适合作为水稻病害标签数据。
- 风险：标签是 weedy rice，不是病虫害；不能用于声明病害模型效果。
- 建议优先级：HIGH。

### 3. Indian Paddy UAV RGB + Multispectral Multi-stage Dataset

- 来源平台：arXiv 论文，数据声称在 IEEE DataPort。
- 入口：<https://arxiv.org/abs/2601.01084>
- 下载入口是否可用：arXiv 页面可访问；IEEE DataPort 数据下载可能需要账号、订阅或机构权限。
- 许可协议：arXiv 论文页面显示 CC BY 4.0；数据集许可需以 IEEE DataPort 为准。
- 数据规模：42,430 raw images，约 415GB。
- 作物类型：Indian paddy。
- 采集视角：UAV / field。
- 模态：RGB + multispectral four bands: red / green / red-edge / NIR。
- 标注类型：metadata、orthomosaic maps、NDVI / NDRE maps；病害标签未明确。
- 适合训练的模型类型：growth-stage index modeling、NDVI/NDRE seasonal baseline、UAV MS preprocessing。
- 是否适合当前项目：适合做生育期指数研究和多光谱处理验证；不适合作为第一批病害监督训练主数据。
- 风险：数据量过大；下载受限；病害标签不清晰；不适合盲目全量下载。
- 建议优先级：MEDIUM。

### 4. msuav500k

- 来源平台：Zenodo / Wageningen University & Research。
- 入口：<https://zenodo.org/records/16743975>
- 下载入口是否可用：Zenodo API 显示 open access，可下载，但数据量很大。
- 许可协议：CC BY 4.0。
- 数据规模：598,300 curated UAV images，约 185GB processed data；包括 RGB.zip 约 45.7GB、RGBMS.zip 约 108.1GB、MS.zip 约 15.2GB、msdata-repo.zip 约 11MB。
- 作物类型：多作物/多场景，不是水稻病害专用。
- 采集视角：UAV。
- 模态：RGB、aligned RGB-MS、MS-only；bands 包括 Blue、Green、Red、RedEdge、NIR。
- 标注类型：foundation/pretraining data，未见水稻病害监督标签。
- 适合训练的模型类型：foundation/pretraining、radiometric calibration、band alignment、MS pipeline validation。
- 是否适合当前项目：适合抽样验证 MS 工具链，不适合当前水稻病害主训练。
- 风险：数据量过大；非水稻病害；不能直接产出病害分类/分割效果。
- 建议优先级：MEDIUM。

### 5. UAV-Based Multispectral Maize Dataset for Water Stress and Common Rust

- 来源平台：Zenodo。
- 入口：<https://zenodo.org/records/20332029>
- 下载入口是否可用：Zenodo API 显示 open access，可下载；建议先下载 README/LICENSE 和 metadata，不先下载大包。
- 许可协议：CC BY 4.0。
- 数据规模：orthomosaics 约 816MB，processed patches 约 365MB，metadata 约 7KB，README/LICENSE 约 5KB。
- 作物类型：maize。
- 采集视角：UAV。
- 模态：six-channel multispectral GeoTIFF patches；记录说明 Band 2=Green、Band 3=Red、Band 4=NIR、Band 5=Red-edge。
- 标注类型：pixel-wise semantic segmentation masks、RGB previews、overlay、metadata。
- 适合训练的模型类型：UAV multispectral segmentation smoke、common rust 迁移学习、NDVI/NDRE calculator 验证。
- 是否适合当前项目：适合多光谱作物病害分割迁移实验；不能宣称为水稻病害模型效果。
- 风险：非水稻；class label 与当前 disease_id 不匹配；只能迁移学习或处理链路验证。
- 建议优先级：MEDIUM。

## B. 手机复查 / RGB 水稻病虫害识别

### 6. Paddy Doctor

- 来源平台：Paddy Doctor 官方站点。
- 入口：<https://paddydoc.github.io/dataset/>
- 下载入口是否可用：说明页面可访问；当前未发现明确下载文件和许可证文本。
- 许可协议：未在审计页面中明确显示，需人工确认。
- 数据规模：初始超过 30,000 images，清洗后 16,225 images。
- 作物类型：paddy。
- 采集视角：phone / leaf close-up / field leaf。
- 模态：RGB + infrared。
- 标注类型：classification + metadata。
- 类别：页面说明包含 Bacterial Leaf Blight、Bacterial Leaf Streak、Bacterial Panicle Blight、Black Stem Borer、Blast、Brown spot、Downy Mildew、Hispa、Leaf Roller、Tungro、White Stem Borer、Yellow Stem Borer、Normal leaf，并包含 crop age / variety metadata。
- 适合训练的模型类型：phone RGB / IR disease-pest classification。
- 是否适合当前项目：很适合手机复查方向和 pest/disease 类别扩展。
- 风险：许可不明确；下载入口不明确；pest/disease 类别混合，需要 class mapping 和 target_type 分离。
- 建议优先级：HIGH_FOR_REVIEW，许可确认前不得训练。

### 7. Rice Leaf Bacterial and Fungal Disease Dataset

- 来源平台：Mendeley Data。
- 入口：<https://data.mendeley.com/datasets/hx6f852hw4/2>
- 下载入口是否可用：页面可访问。
- 许可协议：CC BY 4.0。
- 数据规模：1,701 original images，5,188 augmented images。
- 作物类型：rice leaf。
- 采集视角：leaf close-up。
- 模态：RGB。
- 标注类型：classification。
- 类别：Bacterial Leaf Blight、Brown Spot、Leaf scald、Narrow Brown Leaf Spot、Rice Hispa、Sheath Blight、Leaf Blast、Healthy Rice Leaf。
- 适合训练的模型类型：phone RGB disease classification baseline。
- 是否适合当前项目：适合第一批 phone RGB baseline；需严格分离 original 和 augmented，避免数据泄漏。
- 风险：原图和增强图混用会造成泄漏；类别需映射到当前 disease_id；拍摄区域与宿迁小田块存在域差异。
- 建议优先级：HIGH。

### 8. RiceSeg-5932

- 来源平台：Mendeley Data。
- 入口：<https://data.mendeley.com/datasets/92jc6w6mcy>
- 下载入口是否可用：页面可访问。
- 许可协议：CC BY 4.0。
- 数据规模：5,932 rice leaf images 的 pixel-level masks；该数据集只包含 masks。
- 作物类型：rice leaf。
- 采集视角：leaf close-up。
- 模态：mask-only，需要配套原图。
- 标注类型：segmentation masks。
- 类别：Bacterial Blight、Leaf Blast、Brown Spot、Tungro。
- 适合训练的模型类型：leaf lesion segmentation，U-Net / DeepLabV3+ / SegFormer。
- 是否适合当前项目：适合病斑面积比例、severity 辅助估计、近距离复查分割。
- 风险：只含 masks；必须从 Sethy et al. Rice Leaf Disease Image Samples 另行下载原图，并核验文件名一一对应；不能强行映射缺失文件。
- 建议优先级：HIGH。

### 9. Rice Disease Dataset with Bounding Boxes

- 来源平台：Dataset Ninja / Kaggle。
- 入口：<https://datasetninja.com/rice-disease>
- 下载入口是否可用：Dataset Ninja 页面可访问，原始格式下载指向 Kaggle。
- 许可协议：CC0 1.0。
- 数据规模：470 images，1,956 labeled objects。
- 作物类型：rice leaf。
- 采集视角：leaf close-up。
- 模态：RGB。
- 标注类型：bounding box object detection。
- 类别：BacterialBlight、BrownSpot、RiceBlast。
- 适合训练的模型类型：YOLO bbox smoke / demo / pipeline conversion。
- 是否适合当前项目：适合小样本检测链路 smoke，不适合作为正式模型能力证明。
- 风险：数据规模小；Kaggle 下载可能需要账号；类别少；不能夸大正式效果。
- 建议优先级：MEDIUM。

## 可用性分组

### 第一批建议进入样例核验

- Aligned RGB + Multispectral UAV Weedy Rice：许可清楚，结构清楚，适合 MS/NDVI/NDRE pipeline。
- Rice Leaf Bacterial and Fungal Disease Dataset：许可清楚，适合 phone RGB classification baseline。
- RiceSeg-5932：许可清楚，但必须配套原图并做文件名对齐。
- Rice Disease bbox dataset：许可清楚，适合 YOLO smoke。
- BLB UAV Dataset：方向最匹配，但先完成许可和入口核验。

### 候选但不建议立即全量下载

- Indian Paddy UAV RGB + Multispectral Multi-stage Dataset：IEEE DataPort 访问门槛和 415GB 数据量较高。
- msuav500k：185GB，适合抽样或只下载 repo/metadata，不适合盲目全量。
- Maize Rust MS dataset：可访问且规模可控，但非水稻，适合迁移 smoke。
- Paddy Doctor：数据价值高，但许可和下载入口需确认。

## 许可风险

- HIGH：Paddy Doctor 未在审计页面找到明确许可，不允许直接训练。
- MEDIUM：BLB UAV Dataset 数据许可需以 Figshare/Google Drive 页面为准，不能用 PLOS 论文许可替代。
- MEDIUM：Indian Paddy 数据在 IEEE DataPort，需确认账号、订阅和许可。
- LOW：Mendeley CC BY 4.0 数据集可用于实验，但需保留 attribution 和变更说明。
- LOW：Dataset Ninja / Kaggle bbox 页面显示 CC0 1.0，但下载时仍需保存 Kaggle 元信息。
- LOW：Zenodo CC BY 4.0 数据集可用于实验，但必须保留 DOI、citation、license。

## P11 训练方向建议

| 方向 | 可用数据集 | 是否允许进入训练 | 备注 |
| --- | --- | --- | --- |
| UAV BLB semantic segmentation | BLB UAV Dataset | PARTIAL | 先通过许可和入口 gate，再做样例训练 |
| UAV multispectral index calculation / anomaly detection | Weedy Rice RGB+MS, Indian Paddy, msuav500k, Maize MS | YES_FOR_PIPELINE_SMOKE | 只验证读取、波段、NDVI/NDRE、异常检测，不声明病害概率 |
| Phone RGB disease classification | Rice Leaf Bacterial and Fungal Disease Dataset, Paddy Doctor | PARTIAL | Rice Leaf 可先做 baseline；Paddy Doctor 待许可 |
| Leaf lesion segmentation | RiceSeg-5932 + Sethy 原图 | YES_AFTER_PAIRING | 必须先完成 mask-image 对齐审计 |
| YOLO bbox detection smoke | Rice Disease bbox dataset | YES_SMOKE_ONLY | 小样本演示，不宣称正式效果 |
| Risk fusion tabular shadow model | 本项目闭环数据 | BLOCKED_FOR_LABELS | 公共图像数据不能提供 field-level final decision 标签 |

## 参考来源

- PLOS One BLB UAV paper: <https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0314535>
- Mendeley Weedy Rice RGB+MS: <https://data.mendeley.com/datasets/vt4s83pxx6>
- arXiv Indian Paddy UAV RGB+MS: <https://arxiv.org/abs/2601.01084>
- Paddy Doctor: <https://paddydoc.github.io/dataset/>
- Mendeley Rice Leaf Bacterial and Fungal Disease: <https://data.mendeley.com/datasets/hx6f852hw4/2>
- Mendeley RiceSeg-5932: <https://data.mendeley.com/datasets/92jc6w6mcy>
- Dataset Ninja Rice Disease bbox: <https://datasetninja.com/rice-disease>
- Zenodo msuav500k: <https://zenodo.org/records/16743975>
- Zenodo Maize MS Rust: <https://zenodo.org/records/20332029>
