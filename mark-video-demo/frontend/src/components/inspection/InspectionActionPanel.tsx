import type { ReactNode } from "react";

import { ArrowRight, CheckCircle2 } from "lucide-react";

import { StatusBadge } from "../common";

export interface InspectionActionItem {
  key: string;
  title: string;
  description: string;
  status: string;
  disabled?: boolean;
  actionLabel: string;
  onAction: () => void;
  icon?: ReactNode;
}

interface InspectionActionPanelProps {
  items: InspectionActionItem[];
}

export function InspectionActionPanel({ items }: InspectionActionPanelProps) {
  return (
    <section className="grid gap-3 xl:grid-cols-3">
      {items.map((item) => (
        <article key={item.key} className="rounded-lg border border-slate-700/70 bg-white/[0.03] p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-start gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-700 bg-slate-950 text-cyan-200">
                {item.icon ?? <CheckCircle2 className="h-4 w-4" />}
              </span>
              <div className="min-w-0">
                <div className="font-semibold text-white">{item.title}</div>
                <p className="mt-1 text-sm leading-5 text-slate-400">{item.description}</p>
              </div>
            </div>
            <StatusBadge status={item.status} />
          </div>
          <button type="button" onClick={item.onAction} disabled={item.disabled} className="secondary-button mt-4 w-full justify-center py-2 disabled:opacity-45">
            {item.actionLabel}
            <ArrowRight className="h-4 w-4" />
          </button>
        </article>
      ))}
    </section>
  );
}
