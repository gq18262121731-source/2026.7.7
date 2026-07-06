import { Database, Leaf, ShieldCheck, SlidersHorizontal } from "lucide-react";
import { useEffect, useState } from "react";

import { MetricCard } from "../components/MetricCard";
import { StatusPill } from "../components/StatusPill";
import { ErrorState, LoadingState, ModelSafetyNotice, StatusBadge } from "../components/common";
import { EmptyState, InfoRow, PagePanel } from "../components/ui";
import { api } from "../services/api";
import type { DemoSafetyStatus, ModelsStatusResponse, PlatformModel, SystemStatusResponse } from "../types/api";

export function SettingsPage() {
  const [status, setStatus] = useState<SystemStatusResponse | null>(null);
  const [modelsStatus, setModelsStatus] = useState<ModelsStatusResponse | null>(null);
  const [demoSafety, setDemoSafety] = useState<DemoSafetyStatus | null>(null);
  const [models, setModels] = useState<PlatformModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([api.systemStatus(), api.platformModels(), api.demoSafety()])
      .then(([statusRes, modelRes, safetyRes]) => {
        setStatus(statusRes);
        setModelsStatus(modelRes.raw);
        setModels(modelRes.models);
        setDemoSafety(safetyRes);
      })
      .catch((exc) => setError(exc instanceof Error ? exc.message : "系统状态加载失败"))
      .finally(() => setLoading(false));
  }, []);

  const storageAbnormal = status?.storage_status && status.storage_status !== "ok";

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="服务状态" value={status?.service_status ?? "加载中"} detail="来自 /api/status" icon={Database} />
        <MetricCard label="模型数量" value={`${models.length}`} detail={loading ? "正在加载..." : "来自 /api/models/status"} icon={Leaf} />
        <MetricCard label="Detector mode" value={status?.detector_mode ?? "加载中"} detail="主后端当前识别模式" icon={SlidersHorizontal} />
        <MetricCard label="安全边界" value={demoSafety?.demo_safe ? "启用" : "未知"} detail="不替代现场诊断" icon={ShieldCheck} />
      </div>

      <PagePanel
        title="主后端状态"
        description="只读状态页，不提供没有后端支撑的假配置编辑。"
        status={<StatusBadge status={status?.database_status === "ok" ? "stable" : loading ? "unknown" : "error"} label={status?.database_status ?? "加载中"} />}
      >
        {status ? (
          <div className="space-y-4">
            {storageAbnormal && (
              <ErrorState
                title="存储状态异常"
                message="storage_status error: static_original_writable 或 static_result_writable 返回 false"
              />
            )}
            <div className="grid grid-cols-2 gap-4">
              <div className="surface rounded-lg p-4">
                <InfoRow label="service_status" value={status.service_status} />
                <InfoRow label="model_loaded" value={status.model_loaded ? "是" : "否"} />
                <InfoRow label="model_name" value={status.model_name} />
                <InfoRow label="model_version" value={status.model_version} />
                <InfoRow label="websocket_clients" value={`${status.websocket_clients}`} />
              </div>
              <div className="surface rounded-lg p-4">
                <InfoRow label="database_status" value={status.database_status} />
                <InfoRow label="storage_status" value={storageAbnormal ? "存储状态异常" : status.storage_status} />
                <InfoRow label="static_original" value={status.storage.static_original_writable ? "可写" : "不可写"} />
                <InfoRow label="static_result" value={status.storage.static_result_writable ? "可写" : "不可写"} />
                <InfoRow label="error_message" value={status.error_message ?? "None"} />
              </div>
            </div>
          </div>
        ) : loading ? (
          <LoadingState title="正在读取系统状态" description="正在请求 /api/status、/api/models/status 和 /api/models/demo-safety。" />
        ) : (
          <EmptyState description="正在读取主后端系统状态。" />
        )}
      </PagePanel>

      <PagePanel
        title="模型路线"
        description="展示 mock / smoke / experimental / fallback 边界，不展示正式精度指标。"
        status={<StatusBadge status={modelsStatus?.detector_mode ?? "unknown"} />}
      >
        <div className="grid grid-cols-2 gap-4">
          {models.map((model) => (
            <div key={model.key} className="surface rounded-lg p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="font-semibold text-white">{model.name}</div>
                  <div className="mt-1 text-sm text-slate-500">{model.key}</div>
                </div>
                <StatusBadge status={model.model_stage ?? model.status} />
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <InfoRow label="适用场景" value={model.scene_type === "phone_closeup" ? "手机近景" : "无人机巡田"} />
                <InfoRow label="正式指标" value={model.formal_metric_available ? "可用" : "未提供"} />
                <InfoRow label="类别" value={model.labels.length ? model.labels.join(" / ") : "暂无类别"} />
                <InfoRow label="用途边界" value={model.usage_scope ?? "未返回"} />
              </div>
              <div className="mt-3">
                <ModelSafetyNotice
                  mode={model.model_stage ?? model.status}
                  warning={model.warning}
                  usageScope={model.usage_scope}
                  formalMetricAvailable={model.formal_metric_available}
                  compact
                />
              </div>
            </div>
          ))}
          {!loading && models.length === 0 && <EmptyState description="暂无模型路线。" />}
        </div>
      </PagePanel>

      <div className="grid grid-cols-[1fr_1fr] gap-5">
        <PagePanel title="能力开关" description="由主后端 /api/status 返回，当前仅展示状态。" status={<Database className="h-5 w-5 text-cyan-300" />}>
          <div className="grid grid-cols-2 gap-3">
            {status &&
              Object.entries(status.capabilities).map(([key, value]) => (
                <div key={key} className="surface rounded-lg p-3">
                  <div className="text-xs text-slate-500">{key}</div>
                  <div className="mt-1">
                    <StatusPill label={value ? "启用" : "关闭"} tone={value ? "green" : "slate"} />
                  </div>
                </div>
              ))}
          </div>
          {!status && <EmptyState description="正在读取能力开关。" />}
        </PagePanel>

        <PagePanel title="诊断与安全边界" description="来自 /api/models/demo-safety，用于展示系统真实能力边界。" status={<ShieldCheck className="h-5 w-5 text-amber-200" />}>
          <div className="space-y-3">
            <InfoRow label="demo_safe" value={demoSafety?.demo_safe ? "true" : "false"} />
            <InfoRow label="has_smoke_models" value={demoSafety?.has_smoke_models ? "true" : "false"} />
            <InfoRow label="has_formal_models" value={demoSafety?.has_formal_models ? "true" : "false"} />
            <InfoRow label="formal_metric" value={demoSafety?.formal_metric_available ? "true" : "false"} />
          </div>
          <div className="mt-4">
            <ModelSafetyNotice mode={modelsStatus?.detector_mode ?? status?.detector_mode} compact />
          </div>
          {demoSafety && (
            <div className="mt-4 space-y-2 text-sm text-slate-400">
              {demoSafety.warnings.slice(0, 4).map((item) => (
                <div key={item} className="rounded border border-slate-700/70 bg-white/[0.03] p-2">
                  {item}
                </div>
              ))}
            </div>
          )}
        </PagePanel>
      </div>

      {error && <ErrorState title="状态加载失败" message={error} />}
    </div>
  );
}
