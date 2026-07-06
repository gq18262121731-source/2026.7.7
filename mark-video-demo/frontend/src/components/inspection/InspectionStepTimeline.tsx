import { CheckCircle2, Loader2 } from "lucide-react";

import { StatusBadge } from "../common";

export interface InspectionTimelineStep<T extends string> {
  key: T;
  label: string;
  description: string;
  completed: boolean;
  status?: "completed" | "active" | "pending" | "warning";
  target?: string;
}

interface InspectionStepTimelineProps<T extends string> {
  steps: ReadonlyArray<InspectionTimelineStep<T>>;
  loadingKey?: T | string | null;
  activeTarget?: string;
  onSelectTarget?: (target: string) => void;
}

function statusLabel(status: InspectionTimelineStep<string>["status"], completed: boolean, loading: boolean) {
  if (loading) return "进行中";
  if (completed || status === "completed") return "已完成";
  if (status === "warning") return "有异常";
  if (status === "active") return "进行中";
  return "待处理";
}

export function InspectionStepTimeline<T extends string>({ steps, loadingKey, activeTarget, onSelectTarget }: InspectionStepTimelineProps<T>) {
  return (
    <section className="panel rounded-lg p-4">
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        {steps.map((step, index) => {
          const loading = loadingKey === step.key;
          const selected = Boolean(step.target && activeTarget === step.target);
          const label = statusLabel(step.status, step.completed, loading);
          return (
            <button
              key={step.key}
              type="button"
              onClick={() => step.target && onSelectTarget?.(step.target)}
              className={`rounded-lg border p-3 text-left transition ${
                selected
                  ? "border-cyan-300/50 bg-cyan-400/14"
                  : step.completed
                    ? "border-cyan-300/35 bg-cyan-400/10"
                    : "border-slate-700/70 bg-white/[0.03] hover:bg-white/[0.06]"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-700 bg-slate-950 text-xs text-slate-400">
                  {loading ? <Loader2 className="h-4 w-4 animate-spin text-cyan-300" /> : step.completed ? <CheckCircle2 className="h-4 w-4 text-cyan-300" /> : index + 1}
                </span>
                <StatusBadge status={label === "有异常" ? "error" : label === "已完成" ? "stable" : label === "进行中" ? "preview" : "unknown"} label={label} />
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
