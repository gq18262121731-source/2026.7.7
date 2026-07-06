import { StatusPill } from "../StatusPill";

export type RiskLevel = "normal" | "low" | "medium" | "high" | "unknown" | string;

interface RiskLevelBadgeProps {
  level?: RiskLevel | null;
}

export function normalizeRiskLevel(level?: RiskLevel | null) {
  const value = String(level ?? "unknown").toLowerCase();
  if (value.includes("high") || value.includes("severe") || value.includes("高")) return "high";
  if (value.includes("medium") || value.includes("moderate") || value.includes("中")) return "medium";
  if (value.includes("low") || value.includes("mild") || value.includes("低")) return "low";
  if (value.includes("normal") || value.includes("none") || value.includes("正常")) return "normal";
  return "unknown";
}

const riskMeta = {
  normal: { label: "正常", tone: "green" as const },
  low: { label: "低风险", tone: "green" as const },
  medium: { label: "中风险", tone: "amber" as const },
  high: { label: "高风险", tone: "red" as const },
  unknown: { label: "未知", tone: "slate" as const }
};

export function RiskLevelBadge({ level }: RiskLevelBadgeProps) {
  const key = normalizeRiskLevel(level);
  const meta = riskMeta[key];
  return <StatusPill label={meta.label} tone={meta.tone} dot />;
}
