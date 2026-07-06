import { ShieldCheck } from "lucide-react";

import { StatusBadge } from "./StatusBadge";

interface ModelSafetyNoticeProps {
  mode?: string | null;
  warning?: string | null;
  usageScope?: string | null;
  formalMetricAvailable?: boolean | null;
  compact?: boolean;
}

function safetyText(mode?: string | null) {
  const normalized = String(mode ?? "unknown").toLowerCase();
  if (normalized.includes("mock")) return "当前为模拟结果，仅用于界面演示和流程联调。";
  if (normalized.includes("smoke")) return "当前为烟测模型，仅用于验证识别链路，不代表正式识别效果。";
  if (normalized.includes("experimental")) return "当前为实验能力，结果需人工复核，不作为正式农艺诊断或用药依据。";
  if (normalized.includes("real")) return "当前为模型推理结果，仍建议结合人工巡检和田间情况复核。";
  if (normalized.includes("dry")) return "当前为 dry-run 演示结果，仅用于流程验证，不代表真实遥感反演结论。";
  return "当前结果仅用于辅助巡检和复核，不替代现场诊断，不输出农事处置方案。";
}

export function ModelSafetyNotice({ mode, warning, usageScope, formalMetricAvailable, compact = false }: ModelSafetyNoticeProps) {
  return (
    <div className={`rounded-lg border border-amber-300/30 bg-amber-300/10 ${compact ? "p-3" : "p-4"}`}>
      <div className="flex items-start gap-3">
        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-amber-200" />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-amber-50">模型与结果边界</span>
            <StatusBadge status={mode} />
          </div>
          <p className="mt-2 text-sm leading-6 text-amber-50/90">{warning || safetyText(mode)}</p>
          {!compact && (
            <div className="mt-2 space-y-1 text-xs leading-5 text-amber-50/75">
              {usageScope && <div>用途边界：{usageScope}</div>}
              <div>正式指标：{formalMetricAvailable ? "已提供，但仍需结合现场复核" : "未提供正式生产指标"}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
