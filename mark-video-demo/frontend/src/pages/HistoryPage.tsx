import { AlertTriangle, CheckCircle2, Clock, Loader2, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { DetectionCanvas } from "../components/DetectionCanvas";
import { MetricCard } from "../components/MetricCard";
import { StatusPill } from "../components/StatusPill";
import { ErrorState, ModelSafetyNotice, RiskLevelBadge, StatusBadge } from "../components/common";
import { ReportGenerateButton } from "../components/reports/ReportGenerateButton";
import { DataTable, EmptyState, InfoRow, PagePanel } from "../components/ui";
import type { DataTableColumn } from "../components/ui";
import { api } from "../services/api";
import type { DetectionRecord, DiagnosisReportResponse } from "../types/api";

export function HistoryPage() {
  const [records, setRecords] = useState<DetectionRecord[]>([]);
  const [selected, setSelected] = useState<DetectionRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [aiReport, setAiReport] = useState<DiagnosisReportResponse | null>(null);

  useEffect(() => {
    void api
      .records(1, 50)
      .then((res) => {
        setRecords(res.records);
        setSelected(res.records[0] ?? null);
      })
      .catch((exc) => setError(exc instanceof Error ? exc.message : "识别记录加载失败"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    setAiReport(null);
    setAiError(null);
  }, [selected?.task_id]);

  const highRiskCount = useMemo(() => records.filter((item) => ["high", "critical", "高风险"].includes(item.summary.risk_level)).length, [records]);

  async function generateAiReport(question = "请基于本次检测记录生成诊断建议和现场复查要点。") {
    if (!selected || aiLoading) return;
    setAiLoading(true);
    setAiError(null);
    try {
      const detectedClasses = selected.detections.map((item) => `${item.label} ${(item.confidence * 100).toFixed(0)}%`).join("、") || selected.summary.top_label;
      const report = await api.diagnosisReport({
        record_id: selected.backend_record_id ?? selected.task_id,
        model_class: selected.summary.top_label,
        confidence: selected.summary.top_confidence,
        source_type: selected.source_type ?? selected.image.source_type,
        plot_id: selected.plot_id,
        risk_level: selected.summary.risk_level,
        severity: selected.detections[0]?.severity,
        user_question: `${question}
检测类别：${detectedClasses}
模型：${selected.model_name ?? selected.model.key} / ${selected.model_version ?? selected.model.model_stage ?? ""}
地块：${selected.plot_id ?? selected.plot_name ?? selected.image.source_name}
图片：${selected.image.original_url}`
      });
      setAiReport(report);
    } catch (exc) {
      setAiError(exc instanceof Error ? exc.message : "AI 诊断建议生成失败");
    } finally {
      setAiLoading(false);
    }
  }

  const columns: Array<DataTableColumn<DetectionRecord>> = [
    { key: "task", header: "记录编号", className: "w-[20%]", render: (item) => <span className="block truncate">{item.task_id}</span> },
    { key: "source", header: "来源", className: "w-[15%]", render: (item) => <span className="block truncate">{item.source_type ?? item.image.source_type}</span> },
    { key: "result", header: "识别结果", className: "w-[20%]", render: (item) => <span className="text-white">{item.summary.top_label}</span> },
    { key: "risk", header: "风险", className: "w-[14%]", render: (item) => <RiskLevelBadge level={item.summary.risk_level} /> },
    { key: "confidence", header: "置信度", className: "w-[12%]", render: (item) => `${(item.summary.top_confidence * 100).toFixed(0)}%` },
    { key: "stage", header: "阶段", className: "w-[19%]", render: (item) => <StatusBadge status={item.model_status ?? (item.fallback_to_mock ? "mock_fallback" : item.model_stage ?? "unknown")} /> }
  ];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-4">
        <MetricCard label="记录总数" value={`${records.length}`} detail={loading ? "正在加载..." : "来自 /api/records"} icon={Clock} />
        <MetricCard label="高风险" value={`${highRiskCount}`} detail="建议优先复查" icon={AlertTriangle} tone={highRiskCount ? "amber" : "green"} />
        <MetricCard label="已完成" value={`${records.filter((item) => item.status).length}`} detail="识别链路完成" icon={CheckCircle2} />
      </div>

      <div className="grid grid-cols-[minmax(0,1.45fr)_minmax(390px,0.85fr)] gap-5">
        <PagePanel
          title="识别记录"
          description="点击记录后查看摘要，并可基于本次检测生成农情 PDF。"
          status={
            <div className="flex items-center gap-2 rounded-lg border border-slate-700 bg-white/[0.03] px-3 py-2 text-sm text-slate-400">
              <Search className="h-4 w-4" />
              最近 50 条
            </div>
          }
        >
          <DataTable columns={columns} rows={records} rowKey={(item) => item.task_id} loading={loading} emptyText="暂无识别记录。" selectedKey={selected?.task_id} onRowClick={setSelected} />
          {error && (
            <div className="mt-3">
              <ErrorState title="识别记录加载失败" message={error} />
            </div>
          )}
        </PagePanel>

        <PagePanel title="记录详情" description="默认只保留核心信息，模型细节和安全边界收进折叠区。" status={<StatusPill label={selected ? "已选择" : "未选择"} tone={selected ? "green" : "amber"} />}>
          {selected ? (
            <div className="space-y-4">
              <DetectionCanvas record={selected} />
              <div className="grid grid-cols-2 gap-3">
                <InfoRow label="识别结果" value={selected.summary.top_label} />
                <InfoRow label="风险等级" value={selected.summary.risk_level} />
                <InfoRow label="置信度" value={`${(selected.summary.top_confidence * 100).toFixed(0)}%`} />
                <InfoRow label="检测框" value={`${selected.summary.detection_count}`} />
              </div>

              <ReportGenerateButton
                label="基于本次检测生成 PDF 报告"
                payload={{
                  plot_id: selected.plot_id ?? selected.field_id ?? "plot_001",
                  record_id: selected.backend_record_id ?? selected.task_id,
                  crop: "rice",
                  include_weather: true,
                  include_history_days: 7,
                  report_type: "record_analysis"
                }}
              />

              <details className="surface rounded-lg p-4">
                <summary className="cursor-pointer text-sm font-semibold text-white">查看完整分析结论</summary>
                <div className="mt-3 text-lg font-semibold text-cyan-100">{selected.analysis.title}</div>
                <p className="mt-2 text-sm leading-6 text-slate-300">{selected.analysis.text}</p>
              </details>

              <details className="surface rounded-lg p-4">
                <summary className="cursor-pointer text-sm font-semibold text-white">查看模型详情与原始字段</summary>
                <div className="mt-3 space-y-2">
                  <InfoRow label="record_id" value={selected.backend_record_id ?? selected.task_id} />
                  <InfoRow label="plot_id" value={selected.plot_id ?? "未返回"} />
                  <InfoRow label="source_type" value={selected.source_type ?? selected.image.source_type} />
                  <InfoRow label="target_type" value={selected.target_type ?? selected.model.target_type ?? "未返回"} />
                  <InfoRow label="模型" value={selected.model.name} />
                  <InfoRow label="模型版本" value={selected.model_version ?? "未返回"} />
                  <InfoRow label="detector_mode" value={selected.detector_mode} />
                  <InfoRow label="mock fallback" value={selected.fallback_to_mock ? "是" : "否"} />
                </div>
              </details>

              <details className="surface rounded-lg p-4">
                <summary className="cursor-pointer text-sm font-semibold text-white">查看安全边界</summary>
                <div className="mt-3">
                  <ModelSafetyNotice
                    mode={selected.model_status ?? (selected.fallback_to_mock ? "mock_fallback" : selected.model_stage ?? selected.detector_mode)}
                    warning={selected.model.warning}
                    usageScope={selected.model.usage_scope}
                    formalMetricAvailable={selected.formal_metric_available ?? selected.model.formal_metric_available}
                    allowDashboardStatistics={selected.allow_dashboard_statistics}
                    allowLatestAlerts={selected.allow_latest_alerts}
                    allowBackendDemoClaim={selected.allow_backend_demo_claim}
                    compact
                  />
                </div>
              </details>

              <details className="surface rounded-lg p-4">
                <summary className="cursor-pointer text-sm font-semibold text-white">继续问 AI</summary>
                <div className="mt-4 grid grid-cols-3 gap-2">
                  <button onClick={() => void generateAiReport()} disabled={aiLoading} className="primary-button min-h-9 px-3 py-1 text-xs disabled:opacity-60">
                    {aiLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                    生成诊断建议
                  </button>
                  <button onClick={() => void generateAiReport("请解释本次识别结果为什么需要复查，并列出现地要确认的证据。")} disabled={aiLoading} className="secondary-button min-h-9 px-3 py-1 text-xs disabled:opacity-60">
                    基于本次记录问 AI
                  </button>
                  <button onClick={() => void generateAiReport("请列出本次 AI 分析依据、知识来源和不确定性。")} disabled={aiLoading} className="secondary-button min-h-9 px-3 py-1 text-xs disabled:opacity-60">
                    查看 AI 分析依据
                  </button>
                </div>
                {aiError && <div className="mt-3"><ErrorState title="AI 闭环请求失败" message={aiError} /></div>}
                {aiReport && <AiReportPanel report={aiReport} />}
              </details>
            </div>
          ) : (
            <EmptyState description="选择左侧记录后查看详情。" />
          )}
        </PagePanel>
      </div>
    </div>
  );
}

function AiReportPanel({ report }: { report: DiagnosisReportResponse }) {
  return (
    <div className="mt-4 space-y-3 rounded-lg border border-cyan-300/20 bg-cyan-300/10 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill label={`llm_mode: ${report.llm_mode}`} tone={report.fallback_used ? "amber" : "green"} dot />
        <StatusPill label={`fallback: ${report.fallback_used ? "yes" : "no"}`} tone={report.fallback_used ? "amber" : "cyan"} />
        <RiskLevelBadge level={report.risk_level} />
      </div>
      <div>
        <div className="text-sm font-semibold text-white">诊断摘要</div>
        <p className="mt-1 text-sm leading-6 text-slate-300">{report.model_result_summary}</p>
        <p className="mt-2 text-sm leading-6 text-slate-300">{report.knowledge_summary}</p>
      </div>
      {report.management_suggestions.length > 0 && (
        <div>
          <div className="text-sm font-semibold text-white">建议</div>
          <ul className="mt-2 space-y-1 text-sm leading-6 text-slate-300">
            {report.management_suggestions.slice(0, 4).map((item) => <li key={item}>- {item}</li>)}
          </ul>
        </div>
      )}
      {report.evidence_sources.length > 0 && (
        <div>
          <div className="text-sm font-semibold text-white">依据来源</div>
          <div className="mt-2 space-y-2">
            {report.evidence_sources.slice(0, 3).map((source) => (
              <div key={source.source_id} className="rounded border border-white/10 bg-slate-950/30 p-2 text-xs text-slate-400">
                <div className="truncate text-cyan-100">{source.source_title}</div>
                <div className="mt-1">{source.authority_level} / {source.source_type}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
