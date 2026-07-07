import { CheckCircle2, FileText, Loader2, X } from "lucide-react";

interface ReportGenerationModalProps {
  open: boolean;
  loading: boolean;
  error?: string | null;
  onClose: () => void;
}

const steps = ["读取检测记录", "获取天气快照", "检索知识库", "生成结构化分析", "绘制图表数据", "生成 PDF"];

export function ReportGenerationModal({ open, loading, error, onClose }: ReportGenerationModalProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-lg border border-slate-700 bg-slate-950 p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-base font-semibold text-white">
              {loading ? <Loader2 className="h-5 w-5 animate-spin text-cyan-200" /> : <FileText className="h-5 w-5 text-cyan-200" />}
              农情分析报告
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-400">{error ? "报告生成遇到问题，请稍后重试。" : loading ? "正在整理证据链并生成 PDF。" : "报告已生成完成。"}</p>
          </div>
          <button onClick={onClose} className="secondary-button min-h-8 px-2 py-1" aria-label="关闭">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-2">
          {steps.map((step, index) => {
            const active = loading && index >= 3;
            const done = !loading && !error;
            return (
              <div key={step} className="flex items-center gap-2 rounded border border-slate-700 bg-slate-900/70 px-3 py-2 text-sm text-slate-300">
                {done ? <CheckCircle2 className="h-4 w-4 text-teal-200" /> : active ? <Loader2 className="h-4 w-4 animate-spin text-cyan-200" /> : <span className="h-2 w-2 rounded-full bg-slate-600" />}
                <span>{step}</span>
              </div>
            );
          })}
        </div>

        {error && <div className="mt-4 rounded-lg border border-amber-300/25 bg-amber-300/10 p-3 text-sm leading-6 text-amber-50">{error}</div>}
      </div>
    </div>
  );
}
