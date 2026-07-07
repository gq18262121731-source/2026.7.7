import { Download, ExternalLink } from "lucide-react";

import { StatusPill } from "../StatusPill";
import { api } from "../../services/api";
import type { FarmAnalysisReportResponse } from "../../types/api";

interface ReportDownloadCardProps {
  report: FarmAnalysisReportResponse;
}

export function ReportDownloadCard({ report }: ReportDownloadCardProps) {
  return (
    <div className="rounded-lg border border-teal-300/20 bg-teal-300/10 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm font-semibold text-white">报告已生成</div>
        <div className="flex flex-wrap gap-2">
          <StatusPill label={report.status} tone={report.status === "success" ? "green" : "amber"} dot />
          <StatusPill label={report.weather_available ? "含天气" : "天气兜底"} tone={report.weather_available ? "cyan" : "amber"} />
          <StatusPill label={report.rag_available ? "含 RAG" : "RAG 证据不足"} tone={report.rag_available ? "green" : "amber"} />
        </div>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-300">{report.summary}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <a href={api.getFarmAnalysisReportPreviewUrl(report.report_id)} target="_blank" rel="noreferrer" className="secondary-button min-h-8 px-3 py-1 text-xs">
          <ExternalLink className="h-4 w-4" />
          预览 PDF
        </a>
        <a href={api.getFarmAnalysisReportDownloadUrl(report.report_id)} download className="primary-button min-h-8 px-3 py-1 text-xs">
          <Download className="h-4 w-4" />
          下载 PDF
        </a>
      </div>
      {(report.fallback_used || report.pdf_fallback_used) && (
        <p className="mt-2 text-xs leading-5 text-amber-100/90">部分服务使用兜底生成，PDF 仍可下载；证据快照已保存在后端 metadata 中。</p>
      )}
    </div>
  );
}
