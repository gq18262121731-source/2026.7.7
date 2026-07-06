import { Activity, AlertTriangle, Archive, Bot, ClipboardList, Gauge, Leaf, MapPinned, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { MetricCard } from "../components/MetricCard";
import { StatusPill } from "../components/StatusPill";
import { ErrorState, ModelSafetyNotice, RiskLevelBadge, StatusBadge } from "../components/common";
import { DataTable, PageHeader, PagePanel } from "../components/ui";
import { api } from "../services/api";
import type { DataTableColumn } from "../components/ui";
import type { DashboardSummary, DetectionRecord, PlatformModel } from "../types/api";

interface DashboardPageProps {
  goTo: (page: string) => void;
}

const workflowItems = [
  {
    title: "协同巡检",
    description: "从宿迁田块建档开始，串起 UAV dry-run、手机复查和巡检报告。",
    page: "suqian",
    icon: MapPinned,
    tone: "green" as const
  },
  {
    title: "真实上传检测",
    description: "调用主后端 /detect/image，上传图片并展示识别记录、模型阶段和安全边界。",
    page: "detect",
    icon: Gauge,
    tone: "cyan" as const
  },
  {
    title: "LLM/RAG 报告",
    description: "调用主后端 Agent，展示 llm_mode、fallback_used、证据来源和不确定性说明。",
    page: "assistant",
    icon: Bot,
    tone: "amber" as const
  }
];

export function DashboardPage({ goTo }: DashboardPageProps) {
  const [records, setRecords] = useState<DetectionRecord[]>([]);
  const [models, setModels] = useState<PlatformModel[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([api.records(1, 5), api.platformModels(), api.dashboardSummary()])
      .then(([recordRes, modelRes, summaryRes]) => {
        setRecords(recordRes.records);
        setModels(modelRes.models);
        setSummary(summaryRes);
      })
      .catch((exc) => setError(exc instanceof Error ? exc.message : "工作台数据加载失败"))
      .finally(() => setLoading(false));
  }, []);

  const riskyRecords = useMemo(() => records.filter((item) => !["低风险", "normal", "low"].includes(item.summary.risk_level)), [records]);

  const columns: Array<DataTableColumn<DetectionRecord>> = [
    { key: "task", header: "记录", className: "w-[22%]", render: (item) => <span className="truncate">{item.task_id}</span> },
    { key: "source", header: "来源", className: "w-[18%]", render: (item) => item.image.source_name },
    { key: "result", header: "结果", className: "w-[22%]", render: (item) => <span className="text-white">{item.summary.top_label}</span> },
    {
      key: "risk",
      header: "风险",
      className: "w-[16%]",
      render: (item) => <RiskLevelBadge level={item.summary.risk_level} />
    },
    {
      key: "stage",
      header: "模型阶段",
      className: "w-[22%]",
      render: (item) => <StatusBadge status={item.fallback_to_mock ? "mock_fallback" : item.model_stage ?? item.processing_status} />
    }
  ];

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="今日工作台"
        title="农业病虫害识别与巡检总览"
        description="集中查看识别记录、模型路线、风险概览和协同巡检入口。识别和建议仅用于辅助复核，不替代农技人员现场诊断。"
        badges={
          <>
            <StatusPill label="主后端实时数据" tone="cyan" dot />
            <StatusPill label="非生产诊断" tone="amber" dot />
          </>
        }
        action={
          <button onClick={() => goTo("suqian")} className="primary-button shrink-0">
            <ClipboardList className="h-4 w-4" />
            开始一次巡检
          </button>
        }
      />

      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="今日检测" value={`${summary?.today_detect_count ?? records.length}`} detail={loading ? "正在加载..." : "来自 /api/dashboard/summary"} icon={Activity} tone="cyan" />
        <MetricCard label="高风险地块" value={`${summary?.high_risk_plot_count ?? riskyRecords.length}`} detail="用于复查优先级排序" icon={AlertTriangle} tone="amber" />
        <MetricCard label="模型路线" value={`${models.length}`} detail="主后端模型状态目录" icon={Leaf} tone="green" />
        <MetricCard label="记录总数" value={`${summary?.total_record_count ?? records.length}`} detail="来自主后端识别记录" icon={Archive} tone="slate" />
      </div>

      <section className="grid grid-cols-3 gap-4">
        {workflowItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.title}
              onClick={() => goTo(item.page)}
              className="panel rounded-lg p-5 text-left transition hover:border-cyan-300/30 hover:bg-cyan-400/[0.045]"
            >
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-700 bg-slate-900/70 text-cyan-300">
                  <Icon className="h-5 w-5" />
                </div>
                <StatusPill label="进入" tone={item.tone} />
              </div>
              <h3 className="mt-4 font-semibold text-white">{item.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-400">{item.description}</p>
            </button>
          );
        })}
      </section>

      <div className="grid grid-cols-[1.45fr_0.95fr] gap-4">
        <PagePanel
          title="近期识别记录"
          description="调用主后端 /api/records，不再使用旧 demo history 接口。"
          action={
            <button onClick={() => goTo("history")} className="secondary-button py-2">
              查看全部
            </button>
          }
        >
          <DataTable columns={columns} rows={records} rowKey={(item) => item.task_id} loading={loading} emptyText="暂无检测记录，可从图像检测或协同巡检开始。" />
          {error && (
            <div className="mt-3">
              <ErrorState title="工作台数据加载失败" message={error} />
            </div>
          )}
        </PagePanel>

        <PagePanel title="系统边界" description="页面明确区分真实主后端、dry-run 和 mock fallback。" status={<ShieldCheck className="h-5 w-5 text-amber-200" />}>
          <div className="space-y-3 text-sm leading-6 text-slate-300">
            <BoundaryItem title="主后端接口" text="Dashboard、记录、模型状态、LLM/RAG 均改为主后端 API。" />
            <BoundaryItem title="诊断口径" text="识别和建议仅作辅助参考，不作为农业生产级诊断结论。" />
            <BoundaryItem title="用药边界" text="不输出农药处方、剂量或强制性治疗方案。" />
            <BoundaryItem title="演示边界" text="UAV 多光谱仍是 dry-run 闭环，真实多光谱算法待开发。" />
          </div>
          <div className="mt-4">
            <ModelSafetyNotice mode={records[0]?.model_stage ?? records[0]?.detector_mode ?? "experimental"} compact />
          </div>
        </PagePanel>
      </div>
    </div>
  );
}

function BoundaryItem({ title, text }: { title: string; text: string }) {
  return (
    <div className="surface rounded-lg p-3">
      <div className="font-medium text-slate-100">{title}</div>
      <div className="mt-1 text-slate-400">{text}</div>
    </div>
  );
}
