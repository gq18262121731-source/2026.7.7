import { AlertTriangle, CheckCircle2, Clock, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { DetectionCanvas } from "../components/DetectionCanvas";
import { MetricCard } from "../components/MetricCard";
import { StatusPill } from "../components/StatusPill";
import { ErrorState, ModelSafetyNotice, RiskLevelBadge, StatusBadge } from "../components/common";
import { DataTable, EmptyState, InfoRow, PagePanel } from "../components/ui";
import type { DataTableColumn } from "../components/ui";
import { api } from "../services/api";
import type { DetectionRecord } from "../types/api";

export function HistoryPage() {
  const [records, setRecords] = useState<DetectionRecord[]>([]);
  const [selected, setSelected] = useState<DetectionRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api
      .records(1, 50)
      .then((res) => {
        setRecords(res.records);
        setSelected(res.records[0] ?? null);
      })
      .catch((exc) => setError(exc instanceof Error ? exc.message : "识别记录加载失败"))
      .finally(() => setLoading(false));
  }, []);

  const highRiskCount = useMemo(() => records.filter((item) => item.summary.risk_level === "高风险").length, [records]);

  const columns: Array<DataTableColumn<DetectionRecord>> = [
    { key: "task", header: "记录编号", className: "w-[20%]", render: (item) => <span className="truncate">{item.task_id}</span> },
    { key: "source", header: "来源", className: "w-[15%]", render: (item) => item.image.source_type },
    { key: "result", header: "识别结果", className: "w-[20%]", render: (item) => <span className="text-white">{item.summary.top_label}</span> },
    {
      key: "risk",
      header: "风险",
      className: "w-[14%]",
      render: (item) => <RiskLevelBadge level={item.summary.risk_level} />
    },
    { key: "confidence", header: "置信度", className: "w-[12%]", render: (item) => `${(item.summary.top_confidence * 100).toFixed(0)}%` },
    { key: "stage", header: "阶段", className: "w-[19%]", render: (item) => <StatusBadge status={item.fallback_to_mock ? "mock_fallback" : item.model_stage ?? "unknown"} /> }
  ];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-4">
        <MetricCard label="记录总数" value={`${records.length}`} detail={loading ? "正在加载..." : "来自 /api/records"} icon={Clock} />
        <MetricCard label="高风险" value={`${highRiskCount}`} detail="建议优先复查" icon={AlertTriangle} />
        <MetricCard label="已完成" value={`${records.filter((item) => item.status).length}`} detail="识别链路完成" icon={CheckCircle2} />
      </div>

      <div className="grid grid-cols-[minmax(0,1.45fr)_minmax(360px,0.85fr)] gap-5">
        <PagePanel
          title="识别记录"
          description="主后端记录列表，支持后续扩展筛选、分页和详情联动。"
          status={
            <div className="flex items-center gap-2 rounded-lg border border-slate-700 bg-white/[0.03] px-3 py-2 text-sm text-slate-400">
              <Search className="h-4 w-4" />
              当前展示最近 50 条
            </div>
          }
        >
          <DataTable
            columns={columns}
            rows={records}
            rowKey={(item) => item.task_id}
            loading={loading}
            emptyText="暂无主后端识别记录。"
            selectedKey={selected?.task_id}
            onRowClick={setSelected}
          />
          {error && (
            <div className="mt-3">
              <ErrorState title="识别记录加载失败" message={error} />
            </div>
          )}
        </PagePanel>

        <PagePanel
          title="记录详情"
          description="查看主后端保存的原图、检测框、模型状态和建议。"
          status={<StatusPill label={selected ? "已选择" : "未选择"} tone={selected ? "green" : "amber"} />}
        >
          {selected ? (
            <div className="space-y-4">
              <DetectionCanvas record={selected} />
              <div className="surface rounded-lg p-4">
                <div className="text-sm text-slate-500">分析结论</div>
                <div className="mt-1 text-lg font-semibold text-cyan-100">{selected.analysis.title}</div>
                <p className="mt-2 text-sm leading-6 text-slate-300">{selected.analysis.text}</p>
              </div>
              <InfoRow label="record_id" value={selected.backend_record_id ?? selected.task_id} />
              <InfoRow label="source_type" value={selected.image.source_type} />
              <InfoRow label="模型" value={selected.model.name} />
              <InfoRow label="模型阶段" value={selected.model_stage} />
              <InfoRow label="detector_mode" value={selected.detector_mode} />
              <InfoRow label="mock fallback" value={selected.fallback_to_mock ? "是" : "否"} />
              <InfoRow label="正式指标" value={selected.formal_metric_available ? "可用" : "未提供正式指标"} />
              <ModelSafetyNotice
                mode={selected.fallback_to_mock ? "mock_fallback" : selected.model_stage ?? selected.detector_mode}
                warning={selected.model.warning}
                usageScope={selected.model.usage_scope}
                formalMetricAvailable={selected.formal_metric_available ?? selected.model.formal_metric_available}
                compact
              />
            </div>
          ) : (
            <EmptyState description="选择左侧记录后查看详情。" />
          )}
        </PagePanel>
      </div>
    </div>
  );
}
