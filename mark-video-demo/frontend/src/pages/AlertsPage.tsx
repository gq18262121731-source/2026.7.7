import { AlertTriangle, CheckCircle2, ClipboardList, Loader2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { MetricCard } from "../components/MetricCard";
import { StatusPill } from "../components/StatusPill";
import { ErrorState, RiskLevelBadge, StatusBadge } from "../components/common";
import { DataTable, EmptyState, InfoRow, PagePanel } from "../components/ui";
import type { DataTableColumn } from "../components/ui";
import { api } from "../services/api";
import type { AlertAction, AlertDetail } from "../types/api";

export function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertDetail[]>([]);
  const [selected, setSelected] = useState<AlertDetail | null>(null);
  const [actions, setActions] = useState<AlertAction[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [resolveNote, setResolveNote] = useState("前端核查：已记录处理意见。");
  const [loading, setLoading] = useState(true);
  const [resolving, setResolving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadAlerts(statusFilter);
  }, [statusFilter]);

  useEffect(() => {
    if (!selected) {
      setActions([]);
      return;
    }
    void api
      .alertActions(selected.alert_id)
      .then((res) => setActions(res.items))
      .catch(() => setActions([]));
  }, [selected]);

  async function loadAlerts(status?: string) {
    setLoading(true);
    setError(null);
    try {
      const res = await api.alerts(1, 50, status || undefined);
      setAlerts(res.items);
      setSelected((current) => res.items.find((item) => item.alert_id === current?.alert_id) ?? res.items[0] ?? null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "预警列表加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function resolveSelected() {
    if (!selected) return;
    setResolving(true);
    setError(null);
    try {
      const resolved = await api.resolveAlert(selected.alert_id, resolveNote);
      setSelected(resolved);
      await loadAlerts(statusFilter);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "预警处理失败");
    } finally {
      setResolving(false);
    }
  }

  const highCount = useMemo(() => alerts.filter((item) => ["high", "critical", "高风险"].includes(item.risk_level)).length, [alerts]);
  const pendingCount = useMemo(() => alerts.filter((item) => item.status !== "resolved").length, [alerts]);

  const columns: Array<DataTableColumn<AlertDetail>> = [
    { key: "id", header: "预警编号", className: "w-[20%]", render: (item) => <span className="truncate">{item.alert_id}</span> },
    { key: "plot", header: "地块", className: "w-[18%]", render: (item) => item.plot_name ?? item.plot_id },
    { key: "disease", header: "病虫害", className: "w-[18%]", render: (item) => item.main_disease ?? "未标注" },
    { key: "risk", header: "风险", className: "w-[14%]", render: (item) => <RiskLevelBadge level={item.risk_level} /> },
    { key: "status", header: "状态", className: "w-[14%]", render: (item) => <StatusBadge status={item.status === "resolved" ? "stable" : "preview"} label={item.status === "resolved" ? "已处理" : "待处理"} /> },
    { key: "time", header: "更新时间", className: "w-[16%]", render: (item) => item.latest_seen_at }
  ];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-4">
        <MetricCard label="预警总数" value={`${alerts.length}`} detail="来自 /api/alerts" icon={AlertTriangle} />
        <MetricCard label="待处理" value={`${pendingCount}`} detail="status 非 resolved" icon={ClipboardList} />
        <MetricCard label="高风险" value={`${highCount}`} detail="建议优先复核" icon={CheckCircle2} />
      </div>

      <div className="grid grid-cols-[minmax(0,1.35fr)_minmax(390px,0.9fr)] gap-5">
        <PagePanel
          title="预警列表"
          description="真实查询主后端 alert，不再用 Dashboard 静态数字代替。"
          action={
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none"
            >
              <option value="">全部状态</option>
              <option value="active">active</option>
              <option value="resolved">resolved</option>
            </select>
          }
        >
          <DataTable
            columns={columns}
            rows={alerts}
            rowKey={(item) => item.alert_id}
            loading={loading}
            emptyText="暂无预警记录。可通过高风险检测或预测流程生成。"
            selectedKey={selected?.alert_id}
            onRowClick={setSelected}
          />
          {error && (
            <div className="mt-3">
              <ErrorState title="预警中心错误" message={error} />
            </div>
          )}
        </PagePanel>

        <PagePanel
          title="预警详情"
          description="支持查看来源记录、处理状态和处理动作。"
          status={<StatusPill label={selected ? selected.status : "未选择"} tone={selected?.status === "resolved" ? "green" : "amber"} />}
        >
          {selected ? (
            <div className="space-y-4">
              <div className="surface rounded-lg p-4">
                <div className="text-sm text-slate-500">预警信息</div>
                <p className="mt-2 text-sm leading-6 text-slate-200">{selected.message}</p>
              </div>
              <InfoRow label="alert_id" value={selected.alert_id} />
              <InfoRow label="alert_source" value={selected.alert_source} />
              <InfoRow label="plot_id" value={selected.plot_id} />
              <InfoRow label="latest_record_id" value={selected.latest_record_id} />
              <InfoRow label="prediction_id" value={selected.prediction_id ?? "无"} />
              <InfoRow label="first_seen_at" value={selected.first_seen_at} />
              <InfoRow label="latest_seen_at" value={selected.latest_seen_at} />

              <div className="surface rounded-lg p-4">
                <div className="font-medium text-cyan-100">{selected.suggestion.title}</div>
                <p className="mt-2 text-sm leading-6 text-slate-300">{selected.suggestion.content}</p>
                {selected.suggestion.disclaimer && <p className="mt-2 text-xs leading-5 text-amber-100">{selected.suggestion.disclaimer}</p>}
              </div>

              <textarea
                value={resolveNote}
                onChange={(event) => setResolveNote(event.target.value)}
                className="min-h-24 w-full rounded-lg border border-slate-700 bg-slate-950/60 p-3 text-sm text-slate-100 outline-none"
              />
              <button onClick={resolveSelected} disabled={resolving || selected.status === "resolved"} className="primary-button w-full disabled:opacity-50">
                {resolving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                标记已处理
              </button>

              <div className="space-y-2">
                <div className="text-sm font-medium text-white">处理动作</div>
                {actions.map((action) => (
                  <div key={action.action_id} className="rounded-lg border border-slate-700/70 bg-white/[0.03] p-3 text-sm text-slate-300">
                    <div className="flex items-center justify-between gap-3">
                      <span>{action.action_type}</span>
                      <span className="text-xs text-slate-500">{action.created_at}</span>
                    </div>
                    {action.note && <p className="mt-2 text-slate-400">{action.note}</p>}
                  </div>
                ))}
                {actions.length === 0 && <EmptyState description="当前预警暂无处理动作。" />}
              </div>
            </div>
          ) : (
            <EmptyState description="选择左侧预警后查看详情。" />
          )}
        </PagePanel>
      </div>
    </div>
  );
}
