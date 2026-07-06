import { StatusPill } from "../StatusPill";

export type StatusBadgeValue = "real" | "mock" | "smoke" | "experimental" | "preview" | "stable" | "error" | "unknown" | "dry-run" | string;

interface StatusBadgeProps {
  status?: StatusBadgeValue | null;
  label?: string;
}

const statusMeta: Record<string, { label: string; tone: "green" | "cyan" | "amber" | "slate" | "red" }> = {
  real: { label: "真实模型", tone: "green" },
  stable: { label: "稳定能力", tone: "green" },
  mock: { label: "模拟结果", tone: "amber" },
  smoke: { label: "烟测能力", tone: "amber" },
  experimental: { label: "实验能力", tone: "amber" },
  preview: { label: "预览能力", tone: "cyan" },
  "dry-run": { label: "dry-run", tone: "amber" },
  dry_run: { label: "dry-run", tone: "amber" },
  error: { label: "异常", tone: "red" },
  unknown: { label: "未知", tone: "slate" },
  ready: { label: "可用", tone: "green" },
  unavailable: { label: "不可用", tone: "red" },
  fallback: { label: "fallback", tone: "amber" },
  mock_fallback: { label: "mock fallback", tone: "amber" }
};

export function normalizeStatus(status?: StatusBadgeValue | null) {
  const raw = String(status ?? "unknown").trim();
  const key = raw.toLowerCase().replace(/\s+/g, "_");
  if (key.includes("dry")) return "dry-run";
  if (key.includes("experimental")) return "experimental";
  if (key.includes("smoke")) return "smoke";
  if (key.includes("mock") || key.includes("fallback")) return key.includes("fallback") ? "mock_fallback" : "mock";
  if (key.includes("real")) return "real";
  if (key.includes("error") || key.includes("异常")) return "error";
  if (key.includes("ready") || key.includes("启用") || key.includes("可用")) return "ready";
  if (key.includes("unavailable") || key.includes("不可用")) return "unavailable";
  return key || "unknown";
}

export function getStatusLabel(status?: StatusBadgeValue | null) {
  const key = normalizeStatus(status);
  return statusMeta[key]?.label ?? String(status ?? "未知");
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  const key = normalizeStatus(status);
  const meta = statusMeta[key] ?? { label: label ?? String(status ?? "未知"), tone: "slate" as const };
  return <StatusPill label={label ?? meta.label} tone={meta.tone} dot />;
}
