import { Activity, AlertTriangle, Archive, Bot, CheckCircle2, ClipboardList, Gauge, Leaf, MapPinned, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { MetricCard } from "../components/MetricCard";
import { StatusPill } from "../components/StatusPill";
import { ModelSafetyNotice, RiskLevelBadge, StatusBadge } from "../components/common";
import { DataTable, PageHeader, PagePanel } from "../components/ui";
import { api } from "../services/api";
import { demoDashboardSummary, demoDetectionRecords, demoPlatformModels } from "../services/demoFallback";
import type { DataTableColumn } from "../components/ui";
import type { DashboardSummary, DetectionRecord, PlatformModel } from "../types/api";

interface DashboardPageProps {
  goTo: (page: string) => void;
}

const workflowItems = [
  {
    title: "协同巡检",
    description: "从宿迁田块建档开始，串起无人机演示分析、手机复查和巡检报告。",
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
    title: "智能报告",
    description: "调用诊断助手，展示证据来源、不确定性说明和报告解释。",
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
  const [loadNotes, setLoadNotes] = useState<string[]>([]);

  useEffect(() => {
    let mounted = true;
    void Promise.allSettled([api.records(1, 5), api.platformModels(), api.dashboardSummary()])
      .then(([recordRes, modelRes, summaryRes]) => {
        if (!mounted) return;
        const notes: string[] = [];

        if (recordRes.status === "fulfilled") {
          setRecords(recordRes.value.records);
        } else {
          setRecords(demoDetectionRecords);
          notes.push("识别记录接口暂不可用，已显示演示兜底记录。");
        }

        if (modelRes.status === "fulfilled") {
          setModels(modelRes.value.models);
        } else {
          setModels(demoPlatformModels);
          notes.push("模型状态接口暂不可用，已显示演示模型目录。");
        }

        if (summaryRes.status === "fulfilled") {
          setSummary(summaryRes.value);
        } else {
          setSummary(demoDashboardSummary);
          notes.push("概览接口暂不可用，已显示演示兜底指标。");
        }

        setLoadNotes(notes);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
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
        eyebrow="今日巡检流程"
        title="按三步完成一次田间巡检闭环"
        description="先创建巡检任务，再执行无人机异常分析，最后用手机近景复查并生成报告。识别和建议仅用于辅助复核，不替代农技人员现场诊断。"
        badges={
          <>
            <StatusPill label={loadNotes.length ? "真实接口优先 / 演示兜底" : "主后端实时数据"} tone={loadNotes.length ? "amber" : "cyan"} dot />
            <StatusPill label="非生产诊断" tone="amber" dot />
          </>
        }
        action={
          <button onClick={() => goTo("suqian")} className="primary-button shrink-0">
            <ClipboardList className="h-4 w-4" />
            开始协同巡检
          </button>
        }
      />

      <section className="panel rounded-lg p-5">
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_220px]">
          <div className="grid gap-3 md:grid-cols-3">
            {["创建巡检任务", "执行 UAV 异常分析", "手机复查并生成报告"].map((item, index) => (
              <div key={item} className="rounded-lg border border-teal-300/20 bg-teal-300/10 p-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-teal-200/30 bg-slate-950/40 text-sm font-semibold text-teal-100">{index + 1}</span>
                  <CheckCircle2 className="h-4 w-4 text-teal-200" />
                </div>
                <div className="mt-4 font-semibold text-white">{item}</div>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  {index === 0 ? "确认示范田块与本次巡检对象。" : index === 1 ? "生成异常区域，选择需要复查的位置。" : "回写手机证据，完成报告归档。"}
                </p>
              </div>
            ))}
          </div>
          <button onClick={() => goTo("suqian")} className="primary-button h-full min-h-28 w-full justify-center text-base">
            <ClipboardList className="h-5 w-5" />
            开始宿迁协同巡检
          </button>
        </div>
      </section>

      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="今日检测" value={`${summary?.today_detect_count ?? records.length}`} detail={loading ? "正在加载..." : loadNotes.length ? "演示兜底指标" : "来自 /api/dashboard/summary"} icon={Activity} tone="cyan" />
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
        </PagePanel>

        <PagePanel title="系统边界" description="页面明确区分真实接口、演示分析和兜底数据。" status={<ShieldCheck className="h-5 w-5 text-amber-200" />}>
          {loadNotes.length > 0 && (
            <div className="mb-4 rounded-lg border border-amber-300/30 bg-amber-300/10 p-3 text-sm leading-6 text-amber-50/90">
              {loadNotes.map((item) => (
                <div key={item}>{item}</div>
              ))}
            </div>
          )}
          <div className="space-y-3 text-sm leading-6 text-slate-300">
            <BoundaryItem title="主后端接口" text="Dashboard、记录、模型状态和智能报告均优先调用主后端 API。" />
            <BoundaryItem title="诊断口径" text="识别和建议仅作辅助参考，不作为农业生产级诊断结论。" />
            <BoundaryItem title="用药边界" text="不输出农药处方、剂量或强制性治疗方案。" />
            <BoundaryItem title="演示边界" text="无人机多光谱当前为演示分析闭环，真实多光谱算法待开发。" />
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
