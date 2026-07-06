import { CheckCircle2, ImageUp, Loader2, Play, ScanLine } from "lucide-react";
import { useMemo, useState } from "react";

import { DetectionCanvas } from "../components/DetectionCanvas";
import { StatusPill } from "../components/StatusPill";
import { EmptyState, ErrorNotice, InfoRow, PagePanel } from "../components/ui";
import { api } from "../services/api";
import type { DetectionRecord } from "../types/api";

const sourceOptions = [
  {
    source_type: "phone_rgb",
    label: "手机近景",
    model_hint: "phone",
    target_type: "disease",
    description: "真实上传手机近景图，调用主后端 /api/detect/image。"
  },
  {
    source_type: "uav_rgb",
    label: "无人机 RGB",
    model_hint: "uav_blb",
    target_type: "disease",
    description: "上传无人机场景图，按主后端 UAV BLB 路由识别。"
  },
  {
    source_type: "manual_upload",
    label: "人工上传",
    model_hint: "phone",
    target_type: "disease",
    description: "通用上传入口，适合临时测试和演示。"
  }
];

const pipelineSteps = ["上传图片", "主后端识别", "记录入库", "建议生成"];

export function DetectPage() {
  const [source, setSource] = useState(sourceOptions[0]);
  const [file, setFile] = useState<File | null>(null);
  const [record, setRecord] = useState<DetectionRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);

  async function runDetection() {
    if (!file) {
      setError("请先选择一张图片。");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await api.detectImage(file, {
        source_type: source.source_type,
        model_hint: source.model_hint,
        target_type: source.target_type,
        plot_name: "前端上传检测",
        region_name: source.label
      });
      setRecord(result);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "智能分析失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid grid-cols-[320px_minmax(0,1fr)_360px] gap-5">
      <PagePanel title="检测输入" description="已改为真实上传识别，不再请求旧 demo samples 接口。" status={<ScanLine className="h-5 w-5 text-cyan-300" />}>
        <div className="space-y-3">
          {sourceOptions.map((item) => (
            <button
              key={item.source_type}
              onClick={() => {
                setSource(item);
                setRecord(null);
              }}
              className={`w-full rounded-lg border p-4 text-left transition ${
                source.source_type === item.source_type ? "border-cyan-300/40 bg-cyan-400/10" : "border-slate-700/70 bg-white/[0.03] hover:bg-white/[0.06]"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 font-medium text-white">
                  <ImageUp className="h-4 w-4 text-cyan-300" />
                  {item.label}
                </div>
                <StatusPill label={item.model_hint} tone="cyan" />
              </div>
              <p className="mt-2 text-sm leading-5 text-slate-400">{item.description}</p>
            </button>
          ))}
        </div>

        <label className="mt-5 block rounded-lg border border-dashed border-slate-700 bg-slate-950/40 p-4 text-sm text-slate-300">
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setRecord(null);
            }}
          />
          <div className="flex items-center gap-3">
            <ImageUp className="h-5 w-5 text-cyan-300" />
            <div>
              <div className="font-medium text-white">{file ? file.name : "选择检测图片"}</div>
              <div className="mt-1 text-xs text-slate-500">本地文件不会经过旧 demo API，直接上传主后端。</div>
            </div>
          </div>
        </label>

        <button onClick={runDetection} disabled={loading || !file} className="primary-button mt-5 w-full disabled:opacity-50">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
          开始分析
        </button>
        {error && (
          <div className="mt-4">
            <ErrorNotice title="检测失败" message={error} />
          </div>
        )}
      </PagePanel>

      <PagePanel
        title="图像与识别框"
        description={record ? record.image.source_name : file ? "等待主后端返回识别结果" : "未选择图片"}
        status={<StatusPill label={record ? "已完成" : loading ? "分析中" : "待分析"} tone={record ? "green" : "amber"} />}
      >
        {record ? (
          <DetectionCanvas record={record} />
        ) : previewUrl ? (
          <div className="overflow-hidden rounded-lg border border-slate-700 bg-slate-950">
            <img className="block max-h-[540px] w-full object-contain" src={previewUrl} alt="待检测图片预览" />
          </div>
        ) : (
          <EmptyState description="选择图片并开始分析后，识别图像与检测框会显示在这里。" />
        )}
        <div className="mt-4 grid grid-cols-4 gap-3">
          {pipelineSteps.map((step, index) => {
            const done = Boolean(record) || (loading && index === 0);
            return (
              <div key={step} className={`rounded-lg border p-3 text-sm ${done ? "border-cyan-300/30 bg-cyan-400/10" : "border-slate-700/70 bg-white/[0.03]"}`}>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className={`h-4 w-4 ${done ? "text-cyan-300" : "text-slate-600"}`} />
                  <span className={done ? "text-cyan-100" : "text-slate-400"}>{step}</span>
                </div>
              </div>
            );
          })}
        </div>
      </PagePanel>

      <PagePanel title="分析结论" status={<StatusPill label={record?.processing_status ?? "待分析"} tone={record ? "green" : "amber"} />}>
        {record ? (
          <div className="space-y-4">
            <div className="surface rounded-lg p-4">
              <div className="text-sm text-slate-500">首要结果</div>
              <div className="mt-2 text-2xl font-semibold text-white">{record.summary.top_label}</div>
              <div className="mt-2 flex items-center gap-2">
                <StatusPill label={record.summary.risk_level} tone={record.summary.risk_level === "高风险" ? "amber" : "green"} />
                <span className="text-sm text-slate-400">{(record.summary.top_confidence * 100).toFixed(0)}% 置信度</span>
              </div>
            </div>

            <InfoRow label="模型名称" value={record.model.name} />
            <InfoRow label="模型阶段" value={record.model_stage} />
            <InfoRow label="Detector mode" value={record.detector_mode} />
            <InfoRow label="Mock fallback" value={record.fallback_to_mock ? "是" : "否"} />
            <InfoRow label="正式指标" value={record.formal_metric_available ? "可用" : "未提供正式指标"} />

            <InfoBlock label="诊断建议" title={record.analysis.title} text={record.analysis.text} />
            <InfoBlock label="安全边界" title="辅助参考" text={record.analysis.prevention ?? "建议结合田间复查结果进行分区处理，具体防治方案需由农技人员确认。"} />
          </div>
        ) : (
          <EmptyState description="完成真实上传识别后，这里会展示模型阶段、mock fallback、风险等级和辅助建议。" />
        )}
      </PagePanel>
    </div>
  );
}

function InfoBlock({ label, title, text }: { label: string; title: string; text: string }) {
  return (
    <div className="surface rounded-lg p-4">
      <div className="text-sm text-slate-500">{label}</div>
      <div className="mt-2 font-medium text-cyan-100">{title}</div>
      <p className="mt-2 text-sm leading-6 text-slate-300">{text}</p>
    </div>
  );
}
