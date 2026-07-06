import { Loader2 } from "lucide-react";

interface LoadingStateProps {
  title?: string;
  description?: string;
}

export function LoadingState({ title = "正在加载", description = "正在从主后端读取数据，请稍候。" }: LoadingStateProps) {
  return (
    <div className="rounded-lg border border-slate-700/70 bg-white/[0.03] p-5 text-sm text-slate-300">
      <div className="flex items-start gap-3">
        <Loader2 className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-cyan-300" />
        <div>
          <div className="font-medium text-white">{title}</div>
          <p className="mt-1 leading-6 text-slate-400">{description}</p>
        </div>
      </div>
    </div>
  );
}
