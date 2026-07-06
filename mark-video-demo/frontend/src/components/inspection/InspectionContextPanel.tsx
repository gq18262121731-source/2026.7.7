import type { ReactNode } from "react";

import { ArrowRight, Bot, CheckCircle2, Loader2 } from "lucide-react";

import { EmptyState, ErrorState, LoadingState, ModelSafetyNotice, RiskLevelBadge, StatusBadge } from "../common";
import { ContextPanel, InfoRow } from "../ui";
import type { DemoSafetyStatus } from "../../types/api";
import type { AbnormalRegion, DetectionResult, FieldInfo, InspectionReport, UavDryRunResponse, UavTask } from "../../types/suqianInspection";

type InspectionTab = "overview" | "uav" | "followup" | "reports";

interface InspectionContextPanelProps {
  activeTab: InspectionTab;
  field: FieldInfo | null;
  task: UavTask | null;
  dryRun: UavDryRunResponse | null;
  selectedRegion: AbnormalRegion | null;
  followup: DetectionResult | null;
  report: InspectionReport | null;
  regions: AbnormalRegion[];
  loadingStep: string | null;
  modelMode?: string | null;
  demoSafety?: DemoSafetyStatus | null;
  modelStatusError?: string | null;
  onSelectTab: (tab: InspectionTab) => void;
  onCreateTask: () => void;
  onRunDryRun: () => void;
  onRunPhoneFollowup: () => void;
  onGenerateReport: () => void;
}

function fallback(value?: string | number | null, empty = "暂无数据") {
  if (value === undefined || value === null || value === "") return empty;
  return String(value);
}

function formatPercent(value?: number | null) {
  if (value === undefined || value === null) return "暂无数据";
  return `${(value * 100).toFixed(1)}%`;
}

function buildNextAction(
  field: FieldInfo | null,
  task: UavTask | null,
  dryRun: UavDryRunResponse | null,
  selectedRegion: AbnormalRegion | null,
  followup: DetectionResult | null,
  report: InspectionReport | null
) {
  if (!field) return { text: "请先选择或创建巡检地块。", tab: "overview" as const, label: "查看总览" };
  if (!task) return { text: "请先创建或选择 UAV 巡检任务。", tab: "uav" as const, label: "创建 UAV 任务" };
  if (!dryRun) return { text: "请执行 UAV dry-run 指数分析，用于发现需要复查的异常区域。", tab: "uav" as const, label: "执行指数分析" };
  if (!selectedRegion) return { text: "请在 UAV 异常列表中选择一个异常区域。", tab: "uav" as const, label: "查看异常区" };
  if (!followup && selectedRegion.confirm_status !== "phone_confirmed") {
    return { text: "当前异常区尚未完成手机近景复查，建议先补充近景证据。", tab: "followup" as const, label: "进入手机复查" };
  }
  if (!report) return { text: "当前证据可用于生成实验性辅助巡检报告。", tab: "reports" as const, label: "生成报告" };
  if (!report.risk_model_detail) return { text: "已有报告但暂未包含风险融合详情，可在报告中心查看证据完整度。", tab: "reports" as const, label: "查看风险入口" };
  return { text: "当前巡检已有报告，可查看报告历史或导出巡检结论。", tab: "reports" as const, label: "查看报告" };
}

function getContextMode(dryRun: UavDryRunResponse | null, followup: DetectionResult | null, report: InspectionReport | null, modelMode?: string | null) {
  return report?.risk_model_detail?.model_stage ?? followup?.model_stage ?? dryRun?.data_mode ?? modelMode ?? "experimental";
}

function getRegionStatus(region: AbnormalRegion | null, followup: DetectionResult | null, report: InspectionReport | null) {
  if (report) return "已生成报告";
  if (followup || region?.confirm_status === "phone_confirmed") return "已复查";
  if (region) return "待复查";
  return "未选择";
}

function riskSources(task: UavTask | null, followup: DetectionResult | null, report: InspectionReport | null) {
  const sources = ["UAV dry-run"];
  if (followup) sources.push("手机近景");
  if (task?.weather_text) sources.push("天气描述");
  if (report?.risk_model_detail) sources.push("实验性规则融合");
  if (report?.rag_suggestion) sources.push("RAG 建议");
  return sources;
}

export function InspectionContextPanel({
  activeTab,
  field,
  task,
  dryRun,
  selectedRegion,
  followup,
  report,
  regions,
  loadingStep,
  modelMode,
  demoSafety,
  modelStatusError,
  onSelectTab,
  onCreateTask,
  onRunDryRun,
  onRunPhoneFollowup,
  onGenerateReport
}: InspectionContextPanelProps) {
  const confirmedCount = regions.filter((item) => item.confirm_status === "phone_confirmed").length;
  const next = buildNextAction(field, task, dryRun, selectedRegion, followup, report);
  const contextMode = getContextMode(dryRun, followup, report, modelMode);
  const riskLevel = report?.risk_summary.risk_level ?? followup?.summary.risk_level ?? selectedRegion?.abnormal_level;
  const action = (() => {
    if (next.label === "创建 UAV 任务") return <ContextButton label={next.label} loading={loadingStep === "task"} disabled={!field} onClick={onCreateTask} />;
    if (next.label === "执行指数分析") return <ContextButton label={next.label} loading={loadingStep === "dry-run"} disabled={!task} onClick={onRunDryRun} />;
    if (next.label === "进入手机复查") {
      return <ContextButton label={next.label} loading={loadingStep === "followup"} disabled={!selectedRegion || !field || !task} onClick={onRunPhoneFollowup} />;
    }
    if (next.label === "生成报告") return <ContextButton label={next.label} loading={loadingStep === "report"} disabled={!field || !task} onClick={onGenerateReport} />;
    return <ContextButton label={next.label} onClick={() => onSelectTab(next.tab)} />;
  })();

  return (
    <ContextPanel title="当前上下文详情" description="解释当前选中对象、证据状态和下一步流程建议。" action={action}>
      <div className="space-y-4">
        {loadingStep && <LoadingState title="正在更新巡检上下文" description={`当前步骤：${loadingStep}`} />}
        {modelStatusError && <ErrorState title="模型状态加载失败" message={modelStatusError} />}

        <ContextSection title="当前巡检对象" status={<StatusBadge status={activeTab === "reports" ? "stable" : "preview"} label={activeTabLabel(activeTab)} />}>
          {field ? (
            <>
              <InfoRow label="田块名称" value={field.field_name} />
              <InfoRow label="田块 ID" value={field.field_id} />
              <InfoRow label="当前区域" value={selectedRegion?.region_name} />
              <InfoRow label="UAV 任务" value={task?.task_name ?? task?.uav_task_id} />
              <InfoRow label="异常区 ID" value={selectedRegion?.region_id} />
              <InfoRow label="数据来源" value={buildSourceText(task, followup)} />
            </>
          ) : (
            <EmptyState description="当前还没有可展示的巡检地块，请先加载或创建示范田块。" />
          )}
        </ContextSection>

        <ContextSection title="异常区状态" status={<StatusBadge status={getRegionStatus(selectedRegion, followup, report) === "待复查" ? "preview" : "stable"} label={getRegionStatus(selectedRegion, followup, report)} />}>
          {selectedRegion ? (
            <>
              <InfoRow label="风险等级" value={<RiskLevelBadge level={selectedRegion.abnormal_level} />} />
              <InfoRow label="异常类型" value={selectedRegion.abnormal_type} />
              <InfoRow label="异常指数" value={selectedRegion.source_index_type} />
              <InfoRow label="异常面积" value={formatPercent(selectedRegion.abnormal_area_ratio)} />
              <InfoRow label="严重程度" value={selectedRegion.abnormal_level} />
              <InfoRow label="位置" value={field?.center_lat && field.center_lng ? `${field.center_lat}, ${field.center_lng}` : null} />
            </>
          ) : (
            <EmptyState description="当前没有选中的异常区。执行 dry-run 后可在 UAV 异常中选择复查对象。" />
          )}
        </ContextSection>

        <ContextSection title="手机复查状态" status={<StatusBadge status={followup || selectedRegion?.confirm_status === "phone_confirmed" ? "stable" : "preview"} label={followup || selectedRegion?.confirm_status === "phone_confirmed" ? "已复查" : "待复查"} />}>
          {followup || selectedRegion?.linked_record_id ? (
            <>
              <InfoRow label="是否需要复查" value={selectedRegion?.confirm_status === "phone_confirmed" ? "已完成" : "建议复查"} />
              <InfoRow label="识别记录 ID" value={followup?.record_id ?? selectedRegion?.linked_record_id} />
              <InfoRow label="识别时间" value={selectedRegion?.confirmed_at} />
              <InfoRow label="检测结果" value={followup?.summary.main_disease ?? selectedRegion?.confirmed_disease_type} />
              <InfoRow label="置信度" value={formatPercent(followup?.summary.max_confidence ?? selectedRegion?.confirm_confidence)} />
              <InfoRow label="回写字段" value={selectedRegion?.linked_phone_image_id ? "linked_phone_image_id / linked_record_id 已回写" : "待回写"} />
            </>
          ) : (
            <EmptyState description="当前异常区尚未完成手机近景复查。" />
          )}
        </ContextSection>

        <ContextSection title="风险融合状态" status={<StatusBadge status={report?.risk_model_detail ? "experimental" : "preview"} label={report?.risk_model_detail ? "已融合" : "待风险融合"} />}>
          <InfoRow label="当前风险" value={riskLevel ? <RiskLevelBadge level={riskLevel} /> : null} />
          <InfoRow label="融合状态" value={report?.risk_model_detail ? "已生成实验性规则融合结果" : "待风险融合"} />
          <InfoRow label="数据源" value={riskSources(task, followup, report).join(" / ")} />
          <InfoRow label="规则评分" value={report?.risk_model_detail?.total_risk_score?.toString()} />
          <InfoRow label="概率声明" value={report?.risk_model_detail ? `probability_claim=${String(report.risk_model_detail.probability_claim === true)}` : "待生成"} />
          <p className="mt-2 text-xs leading-5 text-amber-100/90">风险融合仅用于巡检优先级辅助判断，不作为正式农艺诊断或用药依据。</p>
        </ContextSection>

        <ContextSection title="报告状态" status={<StatusBadge status={report ? "stable" : "preview"} label={report ? "已生成报告" : "待生成报告"} />}>
          <InfoRow label="报告编号" value={report?.report_id} />
          <InfoRow label="报告状态" value={report?.report_status} />
          <InfoRow label="复查数量" value={`${confirmedCount}/${regions.length || 0}`} />
          <InfoRow label="报告日期" value={report?.report_date} />
        </ContextSection>

        <ModelSafetyNotice mode={contextMode} warning={report?.model_safety_note ?? followup?.suggestion.disclaimer ?? dryRun?.mock_safety_note} compact />
        {demoSafety?.warnings?.length ? (
          <ContextSection title="安全提示">
            {demoSafety.warnings.slice(0, 2).map((item) => (
              <p key={item} className="rounded-lg border border-amber-300/20 bg-amber-300/10 p-2 text-xs leading-5 text-amber-50/85">
                {item}
              </p>
            ))}
          </ContextSection>
        ) : null}

        <ContextSection title="下一步建议" status={<StatusBadge status="preview" label="流程提示" />}>
          <p className="text-sm leading-6 text-slate-300">{next.text}</p>
          <button type="button" className="secondary-button mt-3 w-full justify-center py-2" onClick={() => onSelectTab(next.tab)}>
            前往相关工作区
            <ArrowRight className="h-4 w-4" />
          </button>
        </ContextSection>

        <ContextSection title="AI 自由问答入口" status={<StatusBadge status="preview" label="待接入" />}>
          <div className="flex items-start gap-3 rounded-lg border border-slate-700/70 bg-slate-950/30 p-3">
            <Bot className="mt-0.5 h-5 w-5 shrink-0 text-cyan-200" />
            <div className="min-w-0">
              <p className="text-sm leading-6 text-slate-300">AI 自由问答将在 P-LLM-1 接入。当前不展示预设答案，避免将模板问答误认为真实智能分析。</p>
              <input
                disabled
                placeholder="请输入你想问的问题。自由问答能力将在 P-LLM-1 接入后开放。"
                className="mt-3 w-full rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-500 outline-none"
              />
            </div>
          </div>
        </ContextSection>
      </div>
    </ContextPanel>
  );
}

function ContextSection({ title, status, children }: { title: string; status?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-700/70 bg-white/[0.03] p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-cyan-100">{title}</div>
        {status}
      </div>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function ContextButton({ label, loading, disabled, onClick }: { label: string; loading?: boolean; disabled?: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} disabled={loading || disabled} className="primary-button px-3 py-2 disabled:opacity-50">
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
      {label}
    </button>
  );
}

function activeTabLabel(tab: InspectionTab) {
  const labels: Record<InspectionTab, string> = {
    overview: "总览",
    uav: "UAV 异常",
    followup: "手机复查",
    reports: "报告中心"
  };
  return labels[tab];
}

function buildSourceText(task: UavTask | null, followup: DetectionResult | null) {
  const parts = [];
  if (task) parts.push(`UAV / ${task.sensor_type} / ${task.data_mode}`);
  if (followup) parts.push(`手机近景 / ${followup.source_type}`);
  return parts.length ? parts.join(" + ") : "暂无数据";
}
