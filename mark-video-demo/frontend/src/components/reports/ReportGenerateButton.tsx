import { FileText, Loader2 } from "lucide-react";
import { useState } from "react";

import { ErrorState } from "../common";
import { ReportDownloadCard } from "./ReportDownloadCard";
import { ReportGenerationModal } from "./ReportGenerationModal";
import { api } from "../../services/api";
import type { FarmAnalysisReportRequest, FarmAnalysisReportResponse } from "../../types/api";

interface ReportGenerateButtonProps {
  payload: FarmAnalysisReportRequest;
  label: string;
  compact?: boolean;
}

export function ReportGenerateButton({ payload, label, compact = false }: ReportGenerateButtonProps) {
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<FarmAnalysisReportResponse | null>(null);

  async function generate() {
    if (loading) return;
    setLoading(true);
    setModalOpen(true);
    setError(null);
    try {
      const nextReport = await api.generateFarmAnalysisReport(payload);
      setReport(nextReport);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "报告生成失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={compact ? "space-y-3" : "surface rounded-lg p-4"}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button onClick={() => void generate()} disabled={loading} className="primary-button min-h-9 px-3 py-1 text-xs disabled:opacity-60">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
          {loading ? "正在生成报告" : label}
        </button>
      </div>

      <ReportGenerationModal open={modalOpen} loading={loading} error={error} onClose={() => setModalOpen(false)} />

      {error && <ErrorState title="农情分析报告生成失败" message={error} />}
      {report && <ReportDownloadCard report={report} />}
    </div>
  );
}
