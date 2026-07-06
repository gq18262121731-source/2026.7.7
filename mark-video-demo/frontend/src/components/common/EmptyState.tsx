import type { ReactNode } from "react";

import { Inbox } from "lucide-react";

interface EmptyStateProps {
  title?: string;
  description: string;
  action?: ReactNode;
}

export function EmptyState({ title = "暂无数据", description, action }: EmptyStateProps) {
  return (
    <div className="rounded-lg border border-dashed border-slate-600/80 bg-slate-950/30 p-5 text-sm text-slate-400">
      <div className="flex items-start gap-3">
        <Inbox className="mt-0.5 h-5 w-5 shrink-0 text-teal-200/70" />
        <div>
          <div className="font-medium text-slate-200">{title}</div>
          <p className="mt-1 leading-6">{description}</p>
          {action && <div className="mt-3">{action}</div>}
        </div>
      </div>
    </div>
  );
}
