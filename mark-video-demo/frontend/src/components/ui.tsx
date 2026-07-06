import type { ReactNode } from "react";

import { AlertTriangle, FileText, Inbox } from "lucide-react";

import { StatusPill } from "./StatusPill";

type Tone = "green" | "cyan" | "amber" | "slate" | "red";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  badges?: ReactNode;
  action?: ReactNode;
}

export function PageHeader({ eyebrow, title, description, badges, action }: PageHeaderProps) {
  return (
    <section className="panel rounded-lg px-5 py-4">
      <div className="flex items-start justify-between gap-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {eyebrow && <span className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-200/85">{eyebrow}</span>}
            {badges}
          </div>
          <h2 className="mt-2 text-2xl font-semibold text-white">{title}</h2>
          {description && <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-400">{description}</p>}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
    </section>
  );
}

interface SectionHeaderProps {
  title: string;
  description?: string;
  status?: ReactNode;
  action?: ReactNode;
}

export function SectionHeader({ title, description, status, action }: SectionHeaderProps) {
  return (
    <div className="mb-4 flex items-start justify-between gap-4">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          {status}
        </div>
        {description && <p className="mt-1 text-sm leading-6 text-slate-500">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

interface PagePanelProps extends SectionHeaderProps {
  children: ReactNode;
  className?: string;
}

export function PagePanel({ children, className = "", ...headerProps }: PagePanelProps) {
  return (
    <section className={`panel rounded-lg p-5 ${className}`}>
      <SectionHeader {...headerProps} />
      {children}
    </section>
  );
}

export function SectionCard(props: PagePanelProps) {
  return <PagePanel {...props} />;
}

interface InfoRowProps {
  label: string;
  value?: ReactNode;
  empty?: string;
}

export function InfoRow({ label, value, empty = "暂无数据" }: InfoRowProps) {
  const shown = value === undefined || value === null || value === "" ? empty : value;

  return (
    <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-3 border-b border-white/5 py-2.5 text-sm last:border-b-0">
      <span className="text-slate-500">{label}</span>
      <span className="min-w-0 break-words text-slate-200">{shown}</span>
    </div>
  );
}

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

interface ErrorNoticeProps {
  title?: string;
  message: string;
}

export function ErrorNotice({ title = "操作失败", message }: ErrorNoticeProps) {
  return (
    <div className="rounded-lg border border-red-400/30 bg-red-400/10 p-4 text-sm text-red-100">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-200" />
        <div>
          <div className="font-semibold">{title}</div>
          <p className="mt-1 leading-6 text-red-100/85">{message}</p>
        </div>
      </div>
    </div>
  );
}

interface RiskBadgeProps {
  level?: string | null;
}

export function RiskBadge({ level }: RiskBadgeProps) {
  const normalized = String(level ?? "unknown").toLowerCase();
  const tone: Tone =
    normalized.includes("high") || normalized.includes("severe") || normalized.includes("高")
      ? "red"
      : normalized.includes("moderate") || normalized.includes("中")
        ? "amber"
        : normalized.includes("mild") || normalized.includes("low") || normalized.includes("低") || normalized.includes("normal")
          ? "green"
          : "slate";

  return <StatusPill label={level || "暂无风险"} tone={tone} dot />;
}

interface EvidenceCardProps {
  title: string;
  meta?: string;
  children: ReactNode;
  action?: ReactNode;
}

export function EvidenceCard({ title, meta, children, action }: EvidenceCardProps) {
  return (
    <article className="rounded-lg border border-slate-700/70 bg-slate-950/30 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2">
          <FileText className="mt-0.5 h-4 w-4 shrink-0 text-teal-200" />
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-white">{title}</div>
            {meta && <div className="mt-1 text-xs text-slate-500">{meta}</div>}
          </div>
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      {children}
    </article>
  );
}

interface ContextPanelProps {
  title: string;
  description?: string;
  children: ReactNode;
  action?: ReactNode;
}

export function ContextPanel({ title, description, children, action }: ContextPanelProps) {
  return (
    <aside className="sticky top-5 self-start">
      <PagePanel title={title} description={description} action={action}>
        {children}
      </PagePanel>
    </aside>
  );
}

export interface DataTableColumn<T> {
  key: string;
  header: string;
  className?: string;
  render: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: Array<DataTableColumn<T>>;
  rows: T[];
  rowKey: (row: T) => string;
  loading?: boolean;
  emptyText: string;
  selectedKey?: string | null;
  onRowClick?: (row: T) => void;
}

export function DataTable<T>({ columns, rows, rowKey, loading = false, emptyText, selectedKey, onRowClick }: DataTableProps<T>) {
  return (
    <div className="overflow-hidden rounded-lg border border-slate-700/70">
      <table className="w-full table-fixed text-left text-sm">
        <thead className="bg-white/[0.035] text-slate-500">
          <tr>
            {columns.map((column) => (
              <th key={column.key} className={`px-4 py-3 font-medium ${column.className ?? ""}`}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading && (
            <tr>
              <td className="px-4 py-8 text-slate-400" colSpan={columns.length}>
                正在加载数据...
              </td>
            </tr>
          )}
          {!loading &&
            rows.map((row) => {
              const key = rowKey(row);
              const active = selectedKey === key;
              return (
                <tr
                  key={key}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={`border-t border-slate-800 transition ${
                    onRowClick ? "cursor-pointer " : ""
                  }${active ? "bg-cyan-400/10" : onRowClick ? "hover:bg-white/[0.04]" : ""}`}
                >
                  {columns.map((column) => (
                    <td key={column.key} className={`min-w-0 px-4 py-4 align-middle text-slate-300 ${column.className ?? ""}`}>
                      {column.render(row)}
                    </td>
                  ))}
                </tr>
              );
            })}
          {!loading && rows.length === 0 && (
            <tr>
              <td className="px-4 py-8 text-slate-400" colSpan={columns.length}>
                {emptyText}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
