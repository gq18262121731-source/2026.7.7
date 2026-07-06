import type { LucideIcon } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: string;
  detail: string;
  icon: LucideIcon;
  tone?: "green" | "cyan" | "amber" | "red" | "slate";
}

export function MetricCard({ label, value, detail, icon: Icon, tone = "green" }: MetricCardProps) {
  const tones = {
    green: "text-green-200 border-green-300/20 bg-green-300/10",
    cyan: "text-teal-100 border-teal-300/20 bg-teal-300/10",
    amber: "text-amber-100 border-amber-300/20 bg-amber-300/10",
    red: "text-red-100 border-red-300/20 bg-red-300/10",
    slate: "text-slate-200 border-slate-600/60 bg-slate-800/45"
  };

  return (
    <section className="metric-card rounded-lg p-5 transition hover:border-teal-300/30">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-400">{label}</span>
        <span className={`flex h-9 w-9 items-center justify-center rounded-lg border ${tones[tone]}`}>
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <div className="mt-4 text-3xl font-semibold text-white">{value}</div>
      <p className="mt-2 text-sm leading-5 text-slate-500">{detail}</p>
    </section>
  );
}

