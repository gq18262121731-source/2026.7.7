import { CheckCircle2, ChevronDown, Loader2, PlayCircle, ShieldCheck } from "lucide-react";

import { StatusPill } from "../../components/StatusPill";
import { InfoRow } from "../../components/ui";
import type { AbnormalRegion, DetectionResult, FieldInfo, InspectionReport, UavDryRunResponse, UavTask } from "../../types/suqianInspection";

export type SuqianStepKey = "field" | "task" | "analysis" | "followup" | "report";

export interface SuqianStepItem {
  key: SuqianStepKey;
  number: number;
  title: string;
  shortTitle: string;
  description: string;
  completed: boolean;
}

interface CurrentStepHeroProps {
  step: SuqianStepItem;
  statusLabel: string;
  actionLabel: string;
  loading: boolean;
  disabled?: boolean;
  onAction: () => void;
}

interface StepProgressProps {
  steps: SuqianStepItem[];
  currentKey: SuqianStepKey;
  loadingStep: string | null;
}

interface InspectionStatusAsideProps {
  field: FieldInfo | null;
  task: UavTask | null;
  dryRun: UavDryRunResponse | null;
  regions: AbnormalRegion[];
  selectedRegion: AbnormalRegion | null;
  followup: DetectionResult | null;
  report: InspectionReport | null;
  modelMode: string | null;
}

export function CurrentStepHero({ step, statusLabel, actionLabel, loading, disabled, onAction }: CurrentStepHeroProps) {
  return (
    <section className="panel rounded-lg border-teal-300/30 bg-teal-300/[0.06] p-5">
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_240px]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill label={`第 ${step.number} 步 / 共 5 步`} tone="cyan" />
            <StatusPill label={statusLabel} tone={step.completed ? "green" : "amber"} dot />
          </div>
          <h3 className="mt-4 text-2xl font-semibold text-white">{step.title}</h3>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">{step.description}</p>
        </div>
        <button onClick={onAction} disabled={loading || disabled} className="primary-button h-full min-h-24 w-full justify-center text-base disabled:opacity-50">
          {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <PlayCircle className="h-5 w-5" />}
          {actionLabel}
        </button>
      </div>
    </section>
  );
}

export function StepProgress({ steps, currentKey, loadingStep }: StepProgressProps) {
  return (
    <section className="rounded-lg border border-slate-700/70 bg-slate-950/30 p-3">
      <div className="grid gap-2 md:grid-cols-5">
        {steps.map((step) => {
          const isCurrent = step.key === currentKey;
          const loading = loadingStep === stepLoadingKey(step.key);
          return (
            <div
              key={step.key}
              className={`rounded-lg border px-3 py-3 transition ${
                isCurrent
                  ? "border-teal-300/45 bg-teal-300/10 text-teal-50"
                  : step.completed
                    ? "border-cyan-300/25 bg-cyan-300/10 text-cyan-50"
                    : "border-slate-700/70 bg-white/[0.03] text-slate-500"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-700 bg-slate-950 text-xs">
                  {loading ? <Loader2 className="h-4 w-4 animate-spin text-teal-200" /> : step.completed ? <CheckCircle2 className="h-4 w-4 text-cyan-200" /> : step.number}
                </span>
                <span className="text-xs">{isCurrent ? "当前" : step.completed ? "已完成" : "未开始"}</span>
              </div>
              <div className="mt-3 text-sm font-medium">{step.shortTitle}</div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function InspectionStatusAside({ field, task, dryRun, regions, selectedRegion, followup, report, modelMode }: InspectionStatusAsideProps) {
  const confirmedCount = regions.filter((item) => item.confirm_status === "phone_confirmed").length;

  return (
    <aside className="space-y-5">
      <section className="panel rounded-lg p-5">
        <div className="mb-3 text-sm font-semibold text-white">本次巡检状态</div>
        <div className="space-y-1">
          <StatusRow label="田块" value={field ? "已确认" : "待确认"} done={Boolean(field)} />
          <StatusRow label="巡检任务" value={task ? "已创建" : "待创建"} done={Boolean(task)} />
          <StatusRow label="异常区域" value={dryRun ? `${regions.length} 个` : "待分析"} done={Boolean(dryRun)} />
          <StatusRow label="手机复查" value={followup ? `已完成 ${confirmedCount}/${regions.length || 1}` : "待完成"} done={Boolean(followup)} />
          <StatusRow label="巡检报告" value={report ? "已生成" : "待生成"} done={Boolean(report)} />
        </div>
      </section>

      <section className="rounded-lg border border-amber-300/30 bg-amber-300/10 p-5">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber-50">
          <ShieldCheck className="h-4 w-4 text-amber-200" />
          演示边界
        </div>
        <div className="space-y-2 text-sm leading-6 text-amber-50/85">
          <p>当前为演示巡检流程。</p>
          <p>无人机异常分析为 dry-run / 演示分析。</p>
          <p>识别结果仅用于辅助复核，不替代农技人员现场诊断。</p>
          <p>报告中的智能建议不等同于农事处置方案。</p>
        </div>
      </section>

      <details className="rounded-lg border border-slate-700/70 bg-slate-950/40 p-5">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-semibold text-slate-200">
          技术详情
          <ChevronDown className="h-4 w-4 text-slate-500" />
        </summary>
        <div className="mt-4">
          <InfoRow label="field_id" value={field?.field_id} />
          <InfoRow label="uav_task_id" value={task?.uav_task_id} />
          <InfoRow label="region_id" value={selectedRegion?.region_id} />
          <InfoRow label="linked_record_id" value={selectedRegion?.linked_record_id} />
          <InfoRow label="model_mode" value={modelMode} />
          <InfoRow label="report_id" value={report?.report_id} />
        </div>
      </details>
    </aside>
  );
}

function StatusRow({ label, value, done }: { label: string; value: string; done: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-white/5 py-2.5 text-sm last:border-b-0">
      <span className="text-slate-400">{label}</span>
      <span className={done ? "text-teal-100" : "text-slate-500"}>{value}</span>
    </div>
  );
}

function stepLoadingKey(key: SuqianStepKey) {
  if (key === "analysis") return "dry-run";
  return key;
}
