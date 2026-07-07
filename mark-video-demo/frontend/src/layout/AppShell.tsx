import {
  Bell,
  Bot,
  ClipboardList,
  Gauge,
  History,
  Home,
  Images,
  Leaf,
  MapPinned,
  PlayCircle,
  Settings,
  TrendingUp
} from "lucide-react";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { StatusPill } from "../components/StatusPill";
import { api } from "../services/api";

interface AppShellProps {
  activePage: string;
  setActivePage: (page: string) => void;
  children: ReactNode;
}

const navItems = [
  { key: "dashboard", label: "工作台", icon: Home, description: "今日巡检入口" },
  { key: "suqian", label: "协同巡检", icon: MapPinned, description: "主演示流程" },
  { key: "detect", label: "图像检测", icon: Gauge, description: "备用单图入口" },
  { key: "history", label: "记录中心", icon: History, description: "报告与留痕" },
  { key: "assistant", label: "智能报告", icon: Bot, description: "诊断解释" }
];

const advancedNavItems = [
  { key: "batch", label: "批量检测", icon: Images, description: "后台任务" },
  { key: "alerts", label: "预警中心", icon: Bell, description: "治理闭环" },
  { key: "prediction", label: "风险预测", icon: TrendingUp, description: "规则评分" },
  { key: "settings", label: "系统状态", icon: Settings, description: "模型与安全" }
];

const pageMeta: Record<string, { title: string; subtitle: string }> = {
  dashboard: { title: "工作台", subtitle: "从今日巡检任务开始，按流程完成异常发现、手机复查和报告归档" },
  suqian: { title: "宿迁协同巡检", subtitle: "田块建档、无人机演示分析、手机复查与报告闭环" },
  detect: { title: "图像检测", subtitle: "上传真实图片或使用示范图片，调用主后端 /api/detect/image" },
  batch: { title: "批量检测", subtitle: "多图上传、后台任务进度和识别记录生成" },
  history: { title: "记录中心", subtitle: "追踪 /api/records 中的识别记录、模型阶段和安全边界" },
  alerts: { title: "预警中心", subtitle: "查询、查看和处理主后端真实 alert" },
  prediction: { title: "风险预测", subtitle: "规则风险评分，不展示为正式发病概率" },
  assistant: { title: "智能报告", subtitle: "调用诊断助手接口，解释识别依据、证据来源和不确定性" },
  settings: { title: "系统状态", subtitle: "检查主后端、模型路线、WebSocket 和安全边界" }
};

export function AppShell({ activePage, setActivePage, children }: AppShellProps) {
  const current = pageMeta[activePage] ?? pageMeta.dashboard;
  const status = useSystemStatus();

  return (
    <div className="min-h-screen text-slate-100">
      <aside className="fixed inset-y-0 left-0 w-72 border-r border-slate-700/50 bg-[#07100c]/95 p-5">
        <div className="flex items-center gap-3 border-b border-slate-800 pb-5">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-teal-300/20 bg-teal-300/10 text-teal-200">
            <Leaf className="h-6 w-6" />
          </div>
          <div>
            <div className="text-xs font-medium uppercase tracking-[0.18em] text-teal-200/80">Rice AI</div>
            <h1 className="mt-1 text-base font-semibold text-white">水稻病虫害系统</h1>
          </div>
        </div>

        <nav className="mt-5 max-h-[calc(100vh-230px)] space-y-1.5 overflow-auto pr-1">
          {[...navItems, ...advancedNavItems].map((item, index) => {
            const Icon = item.icon;
            const active = activePage === item.key;
            return (
              <div key={item.key}>
                {index === navItems.length && <div className="px-3 pb-1 pt-4 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600">高级功能</div>}
                <button
                  onClick={() => setActivePage(item.key)}
                  className={`flex w-full items-center gap-3 rounded-lg border px-3 py-3 text-left transition ${
                    active ? "border-teal-300/30 bg-teal-300/10 text-teal-50" : "border-transparent text-slate-400 hover:bg-white/[0.04] hover:text-slate-100"
                  } ${index >= navItems.length ? "py-2.5 opacity-80" : ""}`}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium">{item.label}</span>
                    <span className="mt-0.5 block text-xs text-slate-500">{item.description}</span>
                  </span>
                </button>
              </div>
            );
          })}
        </nav>

        <div className="absolute bottom-5 left-5 right-5 space-y-3">
          <button onClick={() => setActivePage("suqian")} className="primary-button w-full">
            <ClipboardList className="h-4 w-4" />
            进入协同巡检
          </button>
          <div className="rounded-lg border border-slate-700/70 bg-slate-900/50 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-teal-100">
              <Leaf className="h-4 w-4" />
              辅助诊断模式
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-400">结果用于巡检辅助，不替代农技人员现场诊断。</p>
          </div>
        </div>
      </aside>

      <main className="ml-72 min-h-screen px-6 py-5">
        <header className="panel mb-5 rounded-lg px-5 py-4">
          <div className="flex items-center justify-between gap-5">
            <div>
              <p className="text-sm text-slate-400">{current.subtitle}</p>
              <h2 className="mt-1 text-xl font-semibold text-white">{current.title}</h2>
            </div>
            <div className="flex items-center gap-3">
              <StatusPill label={status.backend} tone={status.backend === "后端正常" ? "green" : status.backend.includes("演示") ? "amber" : "slate"} dot />
              <StatusPill label={status.model} tone={status.model.includes("演示") ? "amber" : "cyan"} dot />
              <button onClick={() => setActivePage("suqian")} className="primary-button">
                <PlayCircle className="h-4 w-4" />
                开始巡检
              </button>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <StatusPill label={`结果 WS：${status.ws.results}`} tone={status.ws.results === "已连接" ? "green" : "slate"} dot />
            <StatusPill label={`任务 WS：${status.ws.tasks}`} tone={status.ws.tasks === "已连接" ? "green" : "slate"} dot />
            <StatusPill label={`预警 WS：${status.ws.alerts}`} tone={status.ws.alerts === "已连接" ? "green" : "slate"} dot />
            <StatusPill label={`API：${api.apiOrigin}`} tone="slate" />
            <StatusPill label={`模式：${api.frontendMode === "demo" ? "演示兜底" : "真实接口优先"}`} tone="amber" />
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}

function useSystemStatus() {
  const [backend, setBackend] = useState("后端检查中");
  const [model, setModel] = useState("模型检查中");
  const [ws, setWs] = useState({ results: "未连接", tasks: "未连接", alerts: "未连接" });

  useEffect(() => {
    let mounted = true;
    void Promise.all([api.health(), api.modelStatus()])
      .then(([, modelStatus]) => {
        if (!mounted) return;
        setBackend("后端正常");
        setModel(modelStatus.fallback_to_mock ? "模型演示兜底" : modelStatus.detector_mode);
      })
      .catch(() => {
        if (!mounted) return;
        setBackend("后端未连接");
        setModel("演示兜底可用");
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    const sockets: Array<[keyof typeof ws, WebSocket]> = [
      ["results", new WebSocket(api.wsUrl("/ws/results"))],
      ["tasks", new WebSocket(api.wsUrl("/ws/tasks"))],
      ["alerts", new WebSocket(api.wsUrl("/ws/alerts"))]
    ];

    sockets.forEach(([key, socket]) => {
      socket.onopen = () => setWs((current) => ({ ...current, [key]: "已连接" }));
      socket.onerror = () => setWs((current) => ({ ...current, [key]: "未连接" }));
      socket.onclose = () => setWs((current) => ({ ...current, [key]: current[key] === "已连接" ? "已断开" : current[key] }));
    });

    return () => {
      sockets.forEach(([, socket]) => socket.close());
    };
  }, []);

  return { backend, model, ws };
}
