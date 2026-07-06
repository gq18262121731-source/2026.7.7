import type { ReactNode } from "react";

import { AlertTriangle, CheckCircle2, FileText, ListChecks, Loader2, MapPin, Plane, Radar, Smartphone } from "lucide-react";

import { StatusPill } from "../../components/StatusPill";
import { EmptyState, ModelSafetyNotice, RiskLevelBadge, StatusBadge } from "../../components/common";
import { AbnormalRegionDetail, AbnormalRegionList } from "../../components/inspection";
import { EvidenceCard, InfoRow, PagePanel, RiskBadge } from "../../components/ui";
import type {
  AbnormalRegion,
  DetectionResult,
  FieldInfo,
  InspectionReport,
  UavDryRunResponse,
  UavIndexResult,
  UavTask
} from "../../types/suqianInspection";
import { safetyText } from "./constants";
import { absoluteAssetUrl, fallback, formatPercent } from "./helpers";

type StepKey = "field" | "task" | "dry-run" | "followup" | "report";
export type InspectionTab = "overview" | "uav" | "followup" | "reports";

interface WorkflowStepBarProps {
  field: FieldInfo | null;
  task: UavTask | null;
  dryRun: UavDryRunResponse | null;
  followup: DetectionResult | null;
  report: InspectionReport | null;
  loadingStep: string | null;
  activeTab?: InspectionTab;
  onSelectTab?: (tab: InspectionTab) => void;
}

const steps: Array<{ key: StepKey; label: string; description: string }> = [
  { key: "field", label: "田块建档", description: "确认巡检对象" },
  { key: "task", label: "UAV 任务", description: "创建 dry-run 任务" },
  { key: "dry-run", label: "异常发现", description: "生成指数与区域" },
  { key: "followup", label: "手机复查", description: "近景确认病害" },
  { key: "report", label: "报告闭环", description: "生成巡检结论" }
];

const stepTabs: Record<StepKey, InspectionTab> = {
  field: "overview",
  task: "uav",
  "dry-run": "uav",
  followup: "followup",
  report: "reports"
};

export function WorkflowStepBar({ field, task, dryRun, followup, report, loadingStep, activeTab, onSelectTab }: WorkflowStepBarProps) {
  const completed: Record<StepKey, boolean> = {
    field: Boolean(field),
    task: Boolean(task),
    "dry-run": Boolean(dryRun),
    followup: Boolean(followup),
    report: Boolean(report)
  };

  return (
    <section className="panel rounded-lg p-4">
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
        {steps.map((step, index) => {
          const done = completed[step.key];
          const loading = loadingStep === step.key;
          const selected = activeTab === stepTabs[step.key];
          return (
            <button
              key={step.key}
              onClick={() => onSelectTab?.(stepTabs[step.key])}
              className={`rounded-lg border p-3 text-left transition ${
                selected ? "border-cyan-300/50 bg-cyan-400/14" : done ? "border-cyan-300/35 bg-cyan-400/10" : "border-slate-700/70 bg-white/[0.03] hover:bg-white/[0.06]"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-700 bg-slate-950 text-xs text-slate-400">
                  {loading ? <Loader2 className="h-4 w-4 animate-spin text-cyan-300" /> : done ? <CheckCircle2 className="h-4 w-4 text-cyan-300" /> : index + 1}
                </span>
                <StatusPill label={done ? "完成" : loading ? "处理中" : "待处理"} tone={done ? "cyan" : loading ? "amber" : "slate"} />
              </div>
              <div className="mt-3 font-medium text-white">{step.label}</div>
              <div className="mt-1 text-xs text-slate-500">{step.description}</div>
            </button>
          );
        })}
      </div>
    </section>
  );
}

export function InspectionOverviewPanel({
  field,
  task,
  dryRun,
  regions,
  followup,
  report,
  onSelectTab,
  onEnsureField,
  onCreateTask,
  onRunDryRun,
  onRunPhoneFollowup,
  onGenerateReport,
  loadingStep
}: {
  field: FieldInfo | null;
  task: UavTask | null;
  dryRun: UavDryRunResponse | null;
  regions: AbnormalRegion[];
  followup: DetectionResult | null;
  report: InspectionReport | null;
  onSelectTab: (tab: InspectionTab) => void;
  onEnsureField: () => void;
  onCreateTask: () => void;
  onRunDryRun: () => void;
  onRunPhoneFollowup: () => void;
  onGenerateReport: () => void;
  loadingStep: string | null;
}) {
  const confirmedCount = regions.filter((item) => item.confirm_status === "phone_confirmed").length;
  const next = getNextAction(field, task, dryRun, regions, followup, report);

  const action = (() => {
    if (!field) return <ActionButton label="创建田块" loading={loadingStep === "field"} onClick={onEnsureField} />;
    if (!task) return <ActionButton label="创建 UAV 任务" loading={loadingStep === "task"} onClick={onCreateTask} />;
    if (!dryRun) return <ActionButton label="执行指数分析" loading={loadingStep === "dry-run"} onClick={onRunDryRun} />;
    if (regions.length > 0 && !followup) return <ActionButton label="进入手机复查" loading={loadingStep === "followup"} onClick={() => onSelectTab("followup")} />;
    if (!report) return <ActionButton label="生成报告" loading={loadingStep === "report"} onClick={onGenerateReport} />;
    return <ActionButton label="查看报告中心" onClick={() => onSelectTab("reports")} />;
  })();

  return (
    <div className="space-y-5">
      <PagePanel title="巡检总览" description="只展示当前闭环状态、最新摘要和下一步建议，避免变成第二个流水账。" action={action}>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <OverviewStat label="田块" value={field ? "已建档" : "待建档"} tone={field ? "green" : "amber"} />
          <OverviewStat label="UAV 任务" value={task ? "已创建" : "待创建"} tone={task ? "green" : "amber"} />
          <OverviewStat label="异常区域" value={`${regions.length} 个`} tone={regions.length ? "cyan" : "slate"} />
          <OverviewStat label="手机复查" value={`${confirmedCount}/${regions.length || 0}`} tone={confirmedCount ? "green" : "amber"} />
        </div>

        <div className="mt-5 rounded-lg border border-cyan-300/20 bg-cyan-400/10 p-4">
          <div className="text-sm font-medium text-cyan-100">下一步建议</div>
          <p className="mt-2 text-sm leading-6 text-slate-300">{next}</p>
        </div>
      </PagePanel>

      <div className="grid gap-4 xl:grid-cols-3">
        <SummaryCard title="最新异常摘要" actionLabel="查看 UAV 异常" onAction={() => onSelectTab("uav")}>
          {dryRun ? (
            <div className="space-y-2 text-sm text-slate-300">
              <div>指数结果：{dryRun.indices.length} 个</div>
              <div>异常区域：{regions.length} 个</div>
              <div>数据模式：{dryRun.data_mode}</div>
            </div>
          ) : (
            <EmptyState description="执行 dry-run 后显示异常摘要。" />
          )}
        </SummaryCard>
        <SummaryCard title="最新复查摘要" actionLabel="进入手机复查" onAction={() => onSelectTab("followup")}>
          {followup ? (
            <div className="space-y-2 text-sm text-slate-300">
              <div>主要病害：{fallback(followup.summary.main_disease)}</div>
              <div>置信度：{formatPercent(followup.summary.max_confidence)}</div>
              <div className="flex items-center gap-2">风险等级：<RiskLevelBadge level={followup.summary.risk_level} /></div>
            </div>
          ) : (
            <EmptyState description="完成手机复查后显示复查摘要。" />
          )}
        </SummaryCard>
        <SummaryCard title="报告闭环" actionLabel="报告中心" onAction={() => onSelectTab("reports")}>
          {report ? (
            <div className="space-y-2 text-sm text-slate-300">
              <div>报告编号：{report.report_id}</div>
              <div className="flex items-center gap-2">风险等级：<RiskLevelBadge level={report.risk_summary.risk_level} /></div>
              <div>规则评分：{fallback(report.risk_model_detail?.total_risk_score)}</div>
              <div>实验标识：{fallback(report.risk_model_detail?.model_stage)}</div>
              <div>报告状态：{report.report_status}</div>
            </div>
          ) : (
            <EmptyState description="生成报告后显示归档摘要。" />
          )}
        </SummaryCard>
      </div>
    </div>
  );
}

export function PhoneFollowupPanel({
  field,
  task,
  selectedRegion,
  followup,
  loadingStep,
  onRunPhoneFollowup
}: {
  field: FieldInfo | null;
  task: UavTask | null;
  selectedRegion: AbnormalRegion | null;
  followup: DetectionResult | null;
  loadingStep: string | null;
  onRunPhoneFollowup: () => void;
}) {
  const steps = [
    { label: "选择异常区域", done: Boolean(selectedRegion) },
    { label: "上传复查图", done: Boolean(followup) },
    { label: "识别完成", done: Boolean(followup) },
    { label: "证据回写", done: selectedRegion?.confirm_status === "phone_confirmed" }
  ];

  return (
    <div className="space-y-5">
      <PagePanel
        title="手机复查任务流"
        description="围绕选中的异常区域完成近景图像复核，并把复查证据回写到异常区域。"
        status={<StatusBadge status={followup ? "stable" : "preview"} label={followup ? "已完成复查" : "待复查"} />}
        action={
          <ActionButton
            label="模拟上传复查图"
            loading={loadingStep === "followup"}
            disabled={!selectedRegion || !field || !task}
            onClick={onRunPhoneFollowup}
          />
        }
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {steps.map((item, index) => (
            <div key={item.label} className={`rounded-lg border p-3 ${item.done ? "border-cyan-300/35 bg-cyan-400/10" : "border-slate-700/70 bg-white/[0.03]"}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-700 bg-slate-950 text-xs text-slate-400">
                  {item.done ? <CheckCircle2 className="h-4 w-4 text-cyan-300" /> : index + 1}
                </span>
                <StatusBadge status={item.done ? "stable" : "unknown"} label={item.done ? "已完成" : "待处理"} />
              </div>
              <div className="mt-3 text-sm font-medium text-white">{item.label}</div>
            </div>
          ))}
        </div>

        <div className="mt-5 grid gap-4 xl:grid-cols-2">
          <DetailBlock title="复查绑定">
            <InfoRow label="复查区域" value={selectedRegion?.region_id} />
            <InfoRow label="绑定田块" value={field?.field_id} />
            <InfoRow label="绑定任务" value={task?.uav_task_id} />
            <InfoRow label="接口字段" value="source_type=phone_followup, model_hint=phone, target_type=disease" />
          </DetailBlock>

          <DetailBlock title="协同判断">
            <InfoRow label="UAV 判断" value={selectedRegion ? `${fallback(selectedRegion.source_index_type)} 指数异常` : null} />
            <InfoRow label="手机复查" value={followup?.summary.main_disease} />
            <InfoRow label="融合结论" value={buildFusionConclusion(selectedRegion, followup)} />
            <InfoRow label="置信度" value={formatPercent(followup?.summary.max_confidence)} />
          </DetailBlock>
        </div>
      </PagePanel>

      <PagePanel
        title="异常区域回写"
        description="复查完成后，后端会把手机图像、识别记录和疑似病害写回当前异常区域。"
        status={<StatusBadge status={selectedRegion?.confirm_status === "phone_confirmed" ? "stable" : "preview"} label={selectedRegion?.confirm_status === "phone_confirmed" ? "已回写" : "待回写"} />}
      >
      <div className="grid gap-4 xl:grid-cols-3">
          <InfoRow label="linked_phone_image_id" value={selectedRegion?.linked_phone_image_id} />
          <InfoRow label="linked_record_id" value={selectedRegion?.linked_record_id} />
          <InfoRow label="confirmed_disease_type" value={selectedRegion?.confirmed_disease_type} />
        </div>
      </PagePanel>
    </div>
  );
}

export function ReportGenerationPanel({
  field,
  task,
  dryRun,
  regions,
  report,
  loadingStep,
  onGenerateReport
}: {
  field: FieldInfo | null;
  task: UavTask | null;
  dryRun: UavDryRunResponse | null;
  regions: AbnormalRegion[];
  report: InspectionReport | null;
  loadingStep: string | null;
  onGenerateReport: () => void;
}) {
  const confirmedCount = regions.filter((item) => item.confirm_status === "phone_confirmed").length;

  return (
    <PagePanel
      title="报告生成"
      description="基于当前田块、UAV 指数异常、手机复查和 RAG 建议生成实验性巡检报告。"
      status={<StatusBadge status={report ? "stable" : "preview"} label={report ? "已有报告" : "待生成"} />}
      action={<ActionButton label={report ? "重新生成报告" : "生成实验性巡检报告"} loading={loadingStep === "report"} disabled={!field || !task} onClick={onGenerateReport} />}
    >
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <OverviewStat label="UAV 任务" value={task ? "已完成" : "未创建"} tone={task ? "green" : "amber"} />
        <OverviewStat label="指数分析" value={dryRun ? "已完成" : "未执行"} tone={dryRun ? "green" : "amber"} />
        <OverviewStat label="异常区域" value={`${regions.length} 个`} tone={regions.length ? "cyan" : "slate"} />
        <OverviewStat label="手机复查" value={`${confirmedCount}/${regions.length || 0}`} tone={confirmedCount ? "green" : "amber"} />
      </div>
      <div className="mt-4">
        <ModelSafetyNotice mode="experimental" compact />
      </div>
    </PagePanel>
  );
}

function getNextAction(
  field: FieldInfo | null,
  task: UavTask | null,
  dryRun: UavDryRunResponse | null,
  regions: AbnormalRegion[],
  followup: DetectionResult | null,
  report: InspectionReport | null
) {
  if (!field) return "还没有确认巡检田块，请先创建或加载示范田块。";
  if (!task) return "田块已就绪，下一步创建本次 UAV dry-run 巡检任务。";
  if (!dryRun) return "UAV 任务已创建，下一步执行 NDVI / NDRE 指数分析，发现需要复查的异常区域。";
  if (regions.length > 0 && !followup) return "已发现异常区域，请选择一个区域进入手机近景复查，形成多源协同证据。";
  if (!report) return "已有巡检证据，下一步可生成实验性巡检报告，完成闭环归档。";
  return "本次巡检已形成报告闭环，可在报告中心查看详情或刷新历史记录。";
}

function buildFusionConclusion(region: AbnormalRegion | null, followup: DetectionResult | null) {
  if (!region) return "请先在 UAV 异常中选择区域";
  if (!followup) return "等待手机近景复查";
  if (followup.summary.risk_level === "high" || followup.summary.risk_level === "高") return "手机复查提示风险升高，建议人工复核";
  if (followup.summary.main_disease) return "UAV 异常已获得手机复查证据";
  return "手机复查未形成明确病害结论，建议人工确认";
}

function OverviewStat({ label, value, tone }: { label: string; value: string; tone: "green" | "cyan" | "amber" | "slate" }) {
  const tones = {
    green: "border-green-400/25 bg-green-400/10 text-green-100",
    cyan: "border-cyan-400/25 bg-cyan-400/10 text-cyan-100",
    amber: "border-amber-400/25 bg-amber-400/10 text-amber-100",
    slate: "border-slate-600/70 bg-white/[0.03] text-slate-200"
  };

  return (
    <div className={`rounded-lg border p-4 ${tones[tone]}`}>
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-2 text-lg font-semibold">{value}</div>
    </div>
  );
}

function SummaryCard({
  title,
  actionLabel,
  onAction,
  children
}: {
  title: string;
  actionLabel: string;
  onAction: () => void;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-slate-700/70 bg-white/[0.03] p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <button className="text-xs font-medium text-cyan-200 hover:text-cyan-100" onClick={onAction}>
          {actionLabel}
        </button>
      </div>
      {children}
    </section>
  );
}

interface FieldTaskPanelProps {
  field: FieldInfo | null;
  task: UavTask | null;
  loadingStep: string | null;
  onEnsureField: () => void;
  onCreateTask: () => void;
}

export function FieldTaskPanel({ field, task, loadingStep, onEnsureField, onCreateTask }: FieldTaskPanelProps) {
  return (
    <PagePanel
      title="巡检对象"
      description="先确认田块，再创建本次 UAV dry-run 巡检任务。"
      status={<StatusBadge status={field ? "stable" : "preview"} label={field ? "田块已就绪" : "待建档"} />}
    >
      <div className="grid gap-4 xl:grid-cols-2">
        <OperationBlock
          title="田块信息"
          icon={<MapPin className="h-5 w-5" />}
          actionLabel={field ? "刷新田块" : "创建田块"}
          loading={loadingStep === "field"}
          onAction={onEnsureField}
        >
          <InfoRow label="田块编号" value={field?.field_id} />
          <InfoRow label="田块名称" value={field?.field_name} />
          <InfoRow label="地区" value={field ? `${field.location_city} ${field.location_district ?? ""}` : null} />
          <InfoRow label="生育期" value={field?.current_growth_stage} />
          <InfoRow label="状态" value={field?.field_status} />
        </OperationBlock>

        <OperationBlock
          title="UAV dry-run 任务"
          icon={<Plane className="h-5 w-5" />}
          actionLabel={task ? "重新创建任务" : "创建任务"}
          loading={loadingStep === "task"}
          disabled={!field}
          onAction={onCreateTask}
        >
          <InfoRow label="任务编号" value={task?.uav_task_id} />
          <InfoRow label="数据模式" value={task?.data_mode} />
          <InfoRow label="传感器" value={task?.sensor_type} />
          <InfoRow label="状态" value={task?.status} />
          <InfoRow label="说明" value={task?.summary} />
        </OperationBlock>
      </div>
    </PagePanel>
  );
}

interface IndexAndRegionPanelProps {
  dryRun: UavDryRunResponse | null;
  regions: AbnormalRegion[];
  selectedRegion: AbnormalRegion | null;
  loadingStep: string | null;
  onRunDryRun: () => void;
  onSelectRegion: (regionId: string) => void;
  disabled: boolean;
}

export function IndexAndRegionPanel({ dryRun, regions, selectedRegion, loadingStep, onRunDryRun, onSelectRegion, disabled }: IndexAndRegionPanelProps) {
  return (
    <div className="grid gap-5 2xl:grid-cols-[minmax(0,1.1fr)_minmax(340px,0.9fr)]">
      <PagePanel
        title="多光谱异常发现"
        description="执行 dry-run 后展示 NDVI / NDRE 占位指数与异常面积占比。"
        status={<StatusBadge status={dryRun?.data_mode ?? "preview"} label={dryRun?.data_mode ?? "待执行"} />}
        action={
          <ActionButton label={dryRun ? "重新执行 dry-run" : "执行 dry-run"} loading={loadingStep === "dry-run"} disabled={disabled} onClick={onRunDryRun} />
        }
      >
        <div className="grid gap-3 xl:grid-cols-2">
          {(dryRun?.indices ?? []).map((item) => (
            <IndexPanel key={item.index_result_id} item={item} />
          ))}
          {!dryRun && <EmptyState description="创建 UAV 任务后执行 dry-run，这里会出现指数图、阈值和异常面积占比。" />}
        </div>
        {dryRun?.mock_safety_note && <p className="mt-3 text-xs leading-5 text-amber-100/80">{dryRun.mock_safety_note}</p>}
      </PagePanel>

      <PagePanel
        title="异常区域"
        description="选择一个异常区域后，可继续进行手机近景复查。"
        status={<StatusBadge status={regions.length ? "preview" : "unknown"} label={`${regions.length} 个区域`} />}
      >
        <div className="space-y-4">
          <AbnormalRegionList regions={regions} selectedRegionId={selectedRegion?.region_id} onSelectRegion={onSelectRegion} />
          <AbnormalRegionDetail region={selectedRegion} />
        </div>
      </PagePanel>
    </div>
  );
}

interface FollowupAndReportPanelProps {
  field: FieldInfo | null;
  task: UavTask | null;
  selectedRegion: AbnormalRegion | null;
  followup: DetectionResult | null;
  report: InspectionReport | null;
  loadingStep: string | null;
  onRunPhoneFollowup: () => void;
  onGenerateReport: () => void;
}

export function FollowupAndReportPanel({
  field,
  task,
  selectedRegion,
  followup,
  report,
  loadingStep,
  onRunPhoneFollowup,
  onGenerateReport
}: FollowupAndReportPanelProps) {
  return (
    <div className="grid gap-5 2xl:grid-cols-[0.9fr_1.1fr]">
      <PagePanel
        title="手机复查"
        description="将近景图像绑定到田块、UAV 任务和异常区域。"
        status={<StatusPill label={followup ? "已回写" : "待复查"} tone={followup ? "green" : "amber"} />}
        action={
          <ActionButton
            label="模拟上传复查图"
            loading={loadingStep === "followup"}
            disabled={!selectedRegion || !field || !task}
            onClick={onRunPhoneFollowup}
          />
        }
      >
        <InfoRow label="复查区域" value={selectedRegion?.region_id} />
        <InfoRow label="绑定田块" value={field?.field_id} />
        <InfoRow label="绑定任务" value={task?.uav_task_id} />
        <InfoRow label="接口字段" value="source_type=phone_followup, model_hint=phone, target_type=disease" />
        <div className="mt-4 rounded-lg border border-slate-700/70 bg-white/[0.03] p-3">
          <div className="text-sm text-slate-400">复查返回</div>
          <div className="mt-2 text-white">{fallback(followup?.summary.main_disease, "暂无复查结果")}</div>
          <div className="mt-1 text-sm text-slate-400">置信度：{formatPercent(followup?.summary.max_confidence)}</div>
        </div>
        <div className="mt-3 rounded-lg border border-slate-700/70 bg-white/[0.03] p-3">
          <div className="text-sm text-slate-400">异常区域回写</div>
          <InfoRow label="linked_phone_image_id" value={selectedRegion?.linked_phone_image_id} />
          <InfoRow label="confirmed_disease_type" value={selectedRegion?.confirmed_disease_type} />
          <InfoRow label="confirm_status" value={selectedRegion?.confirm_status} />
        </div>
      </PagePanel>

      <PagePanel
        title="巡检报告"
        description="汇总田块、UAV 异常、手机复查与 RAG 建议。"
        status={<StatusPill label={report ? "报告已生成" : "待生成"} tone={report ? "green" : "amber"} />}
        action={<ActionButton label={report ? "重新生成报告" : "生成报告"} loading={loadingStep === "report"} disabled={!field || !task} onClick={onGenerateReport} />}
      >
        <InfoRow label="报告编号" value={report?.report_id} />
        <InfoRow label="报告摘要" value={report?.summary} />
        <InfoRow label="风险等级" value={report?.risk_summary.risk_level ? <RiskBadge level={report.risk_summary.risk_level} /> : null} />
        <InfoRow label="风险分数" value={report?.risk_summary.risk_score?.toString()} />
        <RiskWorkbenchSummary report={report} />
        <div className="mt-4 rounded-lg border border-slate-700/70 bg-white/[0.03] p-3">
          <div className="text-sm font-medium text-cyan-100">主要风险因素</div>
          <ul className="mt-2 space-y-1 text-sm text-slate-300">
            {(report?.risk_summary.main_factors ?? ["暂无数据"]).map((item) => (
              <li key={item}>• {item}</li>
            ))}
          </ul>
        </div>
        <div className="mt-3 rounded-lg border border-slate-700/70 bg-white/[0.03] p-3">
          <div className="text-sm font-medium text-cyan-100">RAG 建议</div>
          <p className="mt-2 text-sm leading-6 text-slate-300">{fallback(report?.rag_suggestion)}</p>
        </div>
        <p className="mt-3 text-xs leading-5 text-amber-100/80">{fallback(report?.model_safety_note, safetyText)}</p>
      </PagePanel>
    </div>
  );
}

interface ReportWorkspaceProps {
  field: FieldInfo | null;
  report: InspectionReport | null;
  reportHistory: InspectionReport[];
  loadingStep: string | null;
  onRefreshHistory: () => void;
  onOpenReport: (reportId: string) => void;
}

export function ReportWorkspace({ field, report, reportHistory, loadingStep, onRefreshHistory, onOpenReport }: ReportWorkspaceProps) {
  return (
    <div className="grid gap-5 2xl:grid-cols-[0.78fr_1.22fr]">
      <PagePanel
        title="报告历史"
        description="当前田块的巡检报告留痕。"
        status={<StatusPill label={`${reportHistory.length} 份`} tone={reportHistory.length ? "cyan" : "slate"} />}
        action={<ActionButton label="刷新历史" loading={loadingStep === "report-history"} disabled={!field} onClick={onRefreshHistory} />}
      >
        <div className="space-y-3">
          {reportHistory.map((item) => (
            <button
              key={item.report_id}
              onClick={() => onOpenReport(item.report_id)}
              className={`w-full rounded-lg border p-3 text-left transition ${
                report?.report_id === item.report_id ? "border-cyan-300 bg-cyan-400/10" : "border-slate-700/70 bg-white/[0.03] hover:bg-white/[0.06]"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="truncate text-sm font-medium text-white">{item.report_id}</span>
                <StatusPill label={item.report_status} tone="cyan" />
              </div>
              <p className="mt-2 line-clamp-2 text-sm leading-5 text-slate-400">{item.summary}</p>
              <div className="mt-2 text-xs text-slate-500">{item.report_date}</div>
            </button>
          ))}
          {reportHistory.length === 0 && <EmptyState description="生成报告后，这里会保留当前田块的巡检报告历史。" />}
        </div>
      </PagePanel>

      <ReportDetailView report={report} />
    </div>
  );
}

function RiskWorkbenchSummary({ report }: { report: InspectionReport | null }) {
  const detail = report?.risk_model_detail;
  const factors = detail?.factor_scores ? Object.entries(detail.factor_scores) : [];

  if (!report) {
    return <EmptyState description="生成报告后显示实验性风险摘要。" />;
  }

  if (!detail || Object.keys(detail).length === 0) {
    return <EmptyState description="该报告暂未包含实验性多源风险摘要。" />;
  }

  return (
    <div className="mt-4 rounded-lg border border-cyan-300/20 bg-cyan-400/10 p-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-cyan-100">实验性风险摘要</div>
          <div className="mt-1 text-xs text-slate-400">规则评分仅用于巡检优先级辅助判断</div>
        </div>
        <StatusPill label={detail.model_stage ?? "experimental"} tone="cyan" />
      </div>

      <div className="grid gap-3 text-sm xl:grid-cols-3">
        <InfoRow label="规则评分" value={detail.total_risk_score?.toString()} />
        <InfoRow label="风险等级" value={detail.risk_level ? <RiskBadge level={detail.risk_level} /> : null} />
        <InfoRow label="安全标识" value={`claim=${String(detail.probability_claim === true)}`} />
      </div>

      {factors.length > 0 && (
        <div className="mt-3 space-y-2">
          {factors.map(([key, value]) => (
            <div key={key} className="grid grid-cols-[96px_minmax(0,1fr)_40px] items-center gap-3 text-xs text-slate-300">
              <span className="uppercase text-slate-400">{key}</span>
              <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                <div className="h-full rounded-full bg-cyan-300" style={{ width: `${Math.min(Math.abs(value), 30) * 3.333}%` }} />
              </div>
              <span className="text-right text-cyan-100">{value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function OperationBlock({
  title,
  icon,
  children,
  actionLabel,
  loading = false,
  disabled = false,
  onAction
}: {
  title: string;
  icon: ReactNode;
  children: ReactNode;
  actionLabel: string;
  loading?: boolean;
  disabled?: boolean;
  onAction: () => void;
}) {
  return (
    <div className="rounded-lg border border-slate-700/70 bg-white/[0.03] p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 font-semibold text-white">
          <span className="text-cyan-300">{icon}</span>
          {title}
        </div>
        <ActionButton label={actionLabel} loading={loading} disabled={disabled} onClick={onAction} compact />
      </div>
      {children}
    </div>
  );
}

function ActionButton({ label, loading, disabled, onClick, compact = false }: { label: string; loading?: boolean; disabled?: boolean; onClick: () => void; compact?: boolean }) {
  return (
    <button onClick={onClick} disabled={loading || disabled} className={`primary-button ${compact ? "px-3 py-2" : ""} disabled:opacity-50`}>
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
      {label}
    </button>
  );
}

function IndexPanel({ item }: { item: UavIndexResult }) {
  return (
    <div className="rounded-lg border border-slate-700/70 bg-white/[0.03] p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-semibold uppercase text-white">{item.index_type}</span>
        <StatusPill label={item.data_mode} tone="amber" />
      </div>
      <img src={absoluteAssetUrl(item.index_image_url)} alt={`${item.index_type} dry-run`} className="h-32 w-full rounded-lg object-cover" />
      <div className="mt-3 space-y-1 text-sm text-slate-400">
        <div>异常面积占比：{formatPercent(item.abnormal_area_ratio)}</div>
        <div>阈值：{fallback(item.threshold_used?.toString())}</div>
        <div>均值：{fallback(item.mean_value?.toString())}</div>
      </div>
    </div>
  );
}

function ReportDetailView({ report }: { report: InspectionReport | null }) {
  return (
    <PagePanel
      title="报告详情"
      description="面向用户复核的完整报告结构。"
      status={report ? <StatusPill label={report.report_status} tone="green" /> : <StatusPill label="未选择" tone="slate" />}
    >
      {!report ? (
        <EmptyState description="生成或选择一份巡检报告后，这里会展示田块、UAV、异常区域、手机复查和 RAG 建议。" />
      ) : (
        <div className="space-y-4">
          <div>
            <div className="text-sm text-slate-400">报告标题</div>
            <h3 className="mt-1 text-xl font-semibold text-white">{report.report_title}</h3>
            <p className="mt-2 text-sm leading-6 text-slate-300">{report.summary}</p>
          </div>

          <div className="grid gap-3 xl:grid-cols-2">
            <DetailBlock title="田块信息">
              <InfoRow label="田块编号" value={report.field_id} />
              <InfoRow label="田块名称" value={report.payload.field?.field_name} />
              <InfoRow label="地区" value={report.payload.field?.location_city} />
              <InfoRow label="生育期" value={report.payload.field?.current_growth_stage} />
            </DetailBlock>
            <DetailBlock title="UAV 任务">
              <InfoRow label="任务编号" value={report.uav_task_id} />
              <InfoRow label="数据模式" value={report.uav_summary.data_mode} />
              <InfoRow label="是否 mock" value={report.uav_summary.is_mock === undefined ? null : String(report.uav_summary.is_mock)} />
              <InfoRow label="指数数量" value={String(report.uav_summary.indices?.length ?? 0)} />
            </DetailBlock>
          </div>

          <DetailBlock title="NDVI / NDRE 指数结果">
            <div className="grid gap-3 xl:grid-cols-2">
              {(report.uav_summary.indices ?? []).map((item) => (
                <div key={item.index_result_id} className="rounded-lg border border-slate-700/70 bg-slate-950/30 p-3 text-sm">
                  <div className="font-semibold uppercase text-cyan-100">{item.index_type}</div>
                  <div className="mt-2 text-slate-400">异常面积占比：{formatPercent(item.abnormal_area_ratio)}</div>
                  <div className="text-slate-400">阈值：{fallback(item.threshold_used?.toString())}</div>
                  <div className="text-slate-400">数据模式：{fallback(item.data_mode)}</div>
                </div>
              ))}
            </div>
          </DetailBlock>

          <DetailBlock title="异常区域与手机复查">
            <div className="space-y-3">
              {report.abnormal_region_summary.items.map((region) => (
                <EvidenceCard
                  key={region.region_id}
                  title={region.region_id}
                  meta={fallback(region.abnormal_type)}
                  action={<StatusPill label={region.confirm_status} tone={region.confirm_status === "phone_confirmed" ? "green" : "amber"} dot />}
                >
                  <div className="mt-2 grid gap-2 text-slate-400 xl:grid-cols-3">
                    <span>异常类型：{fallback(region.abnormal_type)}</span>
                    <span>异常等级：{fallback(region.abnormal_level)}</span>
                    <span>复查病害：{fallback(region.confirmed_disease_type)}</span>
                    <span>手机图片：{fallback(region.linked_phone_image_id)}</span>
                    <span>记录：{fallback(region.linked_record_id)}</span>
                    <span>置信度：{formatPercent(region.confirm_confidence)}</span>
                  </div>
                </EvidenceCard>
              ))}
            </div>
          </DetailBlock>

          <DetailBlock title="风险评分与 RAG 建议">
            <InfoRow label="风险等级" value={<RiskBadge level={report.risk_summary.risk_level} />} />
            <InfoRow label="风险分数" value={report.risk_summary.risk_score?.toString()} />
            <InfoRow label="评分口径" value={report.risk_summary.risk_probability_note} />
            <div className="mt-3 text-sm text-slate-300">
              {(report.risk_summary.main_factors ?? []).map((item) => (
                <div key={item}>• {item}</div>
              ))}
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-300">{fallback(report.rag_suggestion)}</p>
          </DetailBlock>

          <RiskModelDetailSection report={report} />

          <div className="rounded-lg border border-amber-300/30 bg-amber-300/10 p-3 text-sm leading-6 text-amber-50/90">{report.model_safety_note}</div>
        </div>
      )}
    </PagePanel>
  );
}

function RiskModelDetailSection({ report }: { report: InspectionReport }) {
  const detail = report.risk_model_detail;
  const factors = detail?.factor_scores ? Object.entries(detail.factor_scores) : [];
  const boundaryNote = report.payload.model_boundary?.rule_weighted_risk_note ?? detail?.safety_note;

  return (
    <DetailBlock title="实验性多源风险分析">
      {!detail || Object.keys(detail).length === 0 ? (
        <EmptyState description="该历史报告暂未包含多源风险分析详情。" />
      ) : (
        <div className="space-y-4">
          <div className="grid gap-3 text-sm xl:grid-cols-2">
            <InfoRow label="模型类型" value={detail.model_type} />
            <InfoRow label="阶段标识" value={detail.model_stage} />
            <InfoRow label="风险等级" value={detail.risk_level ? <RiskBadge level={detail.risk_level} /> : null} />
            <InfoRow label="规则评分" value={detail.total_risk_score?.toString()} />
            <InfoRow label="probability_claim" value={String(detail.probability_claim === true)} />
            <InfoRow label="特征快照" value={detail.feature_snapshot_id} />
          </div>

          {factors.length > 0 ? (
            <div className="space-y-2">
              {factors.map(([key, value]) => (
                <div key={key} className="grid grid-cols-[110px_minmax(0,1fr)_44px] items-center gap-3 text-xs text-slate-300">
                  <span className="uppercase text-slate-400">{key}</span>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                    <div className="h-full rounded-full bg-cyan-300" style={{ width: `${Math.min(Math.abs(value), 30) * 3.333}%` }} />
                  </div>
                  <span className="text-right text-cyan-100">{value}</span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState description="该报告未返回风险因子贡献。" />
          )}

          <div className="rounded-lg border border-slate-700/70 bg-slate-950/30 p-3">
            <div className="text-sm font-medium text-cyan-100">辅助判断依据</div>
            <ul className="mt-2 space-y-1 text-sm leading-6 text-slate-300">
              {(detail.main_factors?.length ? detail.main_factors : ["暂无多源风险因素说明。"]).map((item) => (
                <li key={item}>- {item}</li>
              ))}
            </ul>
          </div>

          <p className="rounded-lg border border-amber-300/30 bg-amber-300/10 p-3 text-xs leading-5 text-amber-50/90">
            {fallback(boundaryNote, "该结果仅用于辅助巡检优先级判断，不作为现场诊断结论或农事处置依据。")}
          </p>
        </div>
      )}
    </DetailBlock>
  );
}

function DetailBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-700/70 bg-white/[0.03] p-4">
      <div className="mb-2 text-sm font-medium text-cyan-100">{title}</div>
      {children}
    </div>
  );
}
