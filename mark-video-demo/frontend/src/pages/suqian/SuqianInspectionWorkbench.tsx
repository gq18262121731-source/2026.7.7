import { AlertTriangle, ClipboardList, FileText, GitBranch, ShieldCheck, Smartphone } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { ErrorState, ModelSafetyNotice, StatusBadge } from "../../components/common";
import { InspectionActionPanel, InspectionContextPanel, InspectionStepTimeline, InspectionWorkflowLayout } from "../../components/inspection";
import { PageHeader } from "../../components/ui";
import { api } from "../../services/api";
import { suqianInspectionApi } from "../../services/suqianInspection";
import type { DemoSafetyStatus } from "../../types/api";
import type { AbnormalRegion, DetectionResult, FieldInfo, InspectionReport, UavDryRunResponse, UavTask } from "../../types/suqianInspection";
import { DEMO_FIELD, safetyText } from "./constants";
import { makeDemoImageFile } from "./helpers";
import {
  FieldTaskPanel,
  IndexAndRegionPanel,
  InspectionOverviewPanel,
  type InspectionTab,
  PhoneFollowupPanel,
  ReportGenerationPanel,
  ReportWorkspace
} from "./SuqianInspectionPanels";

export function SuqianInspectionWorkbench() {
  const [field, setField] = useState<FieldInfo | null>(null);
  const [task, setTask] = useState<UavTask | null>(null);
  const [dryRun, setDryRun] = useState<UavDryRunResponse | null>(null);
  const [regions, setRegions] = useState<AbnormalRegion[]>([]);
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);
  const [followup, setFollowup] = useState<DetectionResult | null>(null);
  const [report, setReport] = useState<InspectionReport | null>(null);
  const [reportHistory, setReportHistory] = useState<InspectionReport[]>([]);
  const [loadingStep, setLoadingStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<InspectionTab>("overview");
  const [modelMode, setModelMode] = useState<string | null>(null);
  const [demoSafety, setDemoSafety] = useState<DemoSafetyStatus | null>(null);
  const [modelStatusError, setModelStatusError] = useState<string | null>(null);

  const selectedRegion = useMemo(
    () => regions.find((item) => item.region_id === selectedRegionId) ?? regions[0] ?? null,
    [regions, selectedRegionId]
  );

  useEffect(() => {
    void ensureDemoField();
    void loadModelStatus();
  }, []);

  async function loadModelStatus() {
    setModelStatusError(null);
    try {
      const [modelStatus, safety] = await Promise.all([api.modelStatus(), api.demoSafety()]);
      setModelMode(modelStatus.detector_mode);
      setDemoSafety(safety);
    } catch (exc) {
      setModelStatusError(exc instanceof Error ? exc.message : "模型状态加载失败");
    }
  }

  async function runStep<T>(step: string, action: () => Promise<T>): Promise<T | null> {
    setLoadingStep(step);
    setError(null);
    try {
      return await action();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "操作失败，请检查主后端服务状态");
      return null;
    } finally {
      setLoadingStep(null);
    }
  }

  async function ensureDemoField() {
    const result = await runStep("field", async () => {
      const fields = await suqianInspectionApi.listFields();
      const existing = fields.items.find((item) => item.field_id === DEMO_FIELD.field_id);
      if (existing) return existing;
      return suqianInspectionApi.createField(DEMO_FIELD);
    });
    if (result) {
      setField(result);
      await loadReportHistory(result.field_id);
    }
  }

  async function loadReportHistory(fieldId: string) {
    const history = await runStep("report-history", () => suqianInspectionApi.listReports(fieldId));
    if (history) {
      setReportHistory(history.items);
      setReport((current) => current ?? history.items[0] ?? null);
    }
  }

  async function createTask() {
    if (!field) return;
    const result = await runStep("task", () => suqianInspectionApi.createUavTask(field));
    if (result) {
      setTask(result);
      setDryRun(null);
      setRegions([]);
      setSelectedRegionId(null);
      setFollowup(null);
      setReport(null);
      setActiveTab("uav");
    }
  }

  async function runDryRun() {
    if (!field || !task) return;
    const result = await runStep("dry-run", () => suqianInspectionApi.runDryRun(task, field));
    if (result) {
      setDryRun(result);
      setRegions(result.abnormal_regions);
      setSelectedRegionId(result.abnormal_regions[0]?.region_id ?? null);
      const refreshed = await suqianInspectionApi.listAbnormalRegions(task.uav_task_id);
      setRegions(refreshed.items);
      setActiveTab("uav");
    }
  }

  async function runPhoneFollowup() {
    if (!field || !task || !selectedRegion) return;
    const file = await makeDemoImageFile();
    const result = await runStep("followup", () => suqianInspectionApi.phoneFollowup(selectedRegion, field, task, file));
    if (result) {
      setFollowup(result);
      const detail = await suqianInspectionApi.getAbnormalRegion(selectedRegion.region_id);
      setRegions((items) => items.map((item) => (item.region_id === detail.region_id ? detail : item)));
      setSelectedRegionId(detail.region_id);
      setActiveTab("followup");
    }
  }

  async function generateReport() {
    if (!field || !task) return;
    const generated = await runStep("report", () => suqianInspectionApi.generateReport(field.field_id, task.uav_task_id));
    if (generated) {
      const detail = await suqianInspectionApi.getReport(generated.report_id);
      setReport(detail);
      await loadReportHistory(field.field_id);
      setActiveTab("reports");
    }
  }

  async function openReport(reportId: string) {
    const detail = await runStep("report-history", () => suqianInspectionApi.getReport(reportId));
    if (detail) setReport(detail);
  }

  const currentStage = report ? "报告闭环" : followup ? "手机复查" : dryRun ? "异常发现" : task ? "UAV 任务" : field ? "田块建档" : "初始化";
  const primaryAction = (() => {
    if (!field) return { label: "加载示范田块", run: () => void ensureDemoField() };
    if (!task) return { label: "创建 UAV 任务", run: () => void createTask() };
    if (!dryRun) return { label: "执行指数分析", run: () => void runDryRun() };
    if (regions.length > 0 && !followup) return { label: "进入手机复查", run: () => setActiveTab("followup") };
    if (!report) return { label: "生成巡检报告", run: () => void generateReport() };
    return { label: "查看报告中心", run: () => setActiveTab("reports") };
  })();
  const tabItems: Array<{ key: InspectionTab; label: string; badge?: string }> = [
    { key: "overview", label: "总览", badge: currentStage },
    { key: "uav", label: "UAV 异常", badge: regions.length ? `${regions.length} 个` : "待分析" },
    { key: "followup", label: "手机复查", badge: followup ? "已回写" : "待复查" },
    { key: "reports", label: "报告中心", badge: report ? "已生成" : `${reportHistory.length} 份` }
  ];
  const timelineSteps = [
    { key: "field", label: "田块", description: "确认巡检对象", completed: Boolean(field), target: "overview" },
    { key: "task", label: "UAV 任务", description: "创建任务", completed: Boolean(task), target: "uav" },
    { key: "dry-run", label: "异常区", description: "dry-run 指数分析", completed: Boolean(dryRun), status: regions.length ? "warning" : undefined, target: "uav" },
    { key: "followup", label: "手机复查", description: "近景识别回写", completed: Boolean(followup), target: "followup" },
    {
      key: "risk",
      label: "风险融合",
      description: "experimental 辅助判断",
      completed: Boolean(report?.risk_model_detail),
      status: report?.risk_model_detail ? "completed" : "pending",
      target: "reports"
    },
    { key: "report", label: "巡检报告", description: "报告闭环归档", completed: Boolean(report), target: "reports" }
  ] as const;
  const actionItems = [
    {
      key: "followup",
      title: "手机近景复查",
      description: selectedRegion ? "围绕当前异常区域进行近景识别，并回写证据字段。" : "请先在 UAV 异常中选择一个异常区域。",
      status: followup ? "stable" : selectedRegion ? "preview" : "unknown",
      disabled: !selectedRegion,
      actionLabel: "进入手机复查",
      icon: <Smartphone className="h-4 w-4" />,
      onAction: () => setActiveTab("followup")
    },
    {
      key: "risk",
      title: "风险融合 / RAG",
      description: "查看报告中心中的实验性风险融合和 RAG 建议，不包装为正式诊断。",
      status: report?.risk_model_detail?.model_stage ?? (dryRun ? "experimental" : "unknown"),
      disabled: !dryRun,
      actionLabel: "查看风险入口",
      icon: <GitBranch className="h-4 w-4" />,
      onAction: () => setActiveTab("reports")
    },
    {
      key: "report",
      title: "巡检报告闭环",
      description: report ? "当前巡检已有报告，可查看详情或历史归档。" : "基于当前证据生成实验性辅助巡检报告。",
      status: report ? "stable" : "preview",
      disabled: !field || !task,
      actionLabel: report ? "查看报告中心" : "生成报告",
      icon: <FileText className="h-4 w-4" />,
      onAction: () => (report ? setActiveTab("reports") : void generateReport())
    }
  ];

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="协同巡检工作台"
        title="宿迁一号田多源巡检闭环"
        description="围绕田块、UAV dry-run、手机复查和实验性报告形成一条可复核的证据链。"
        badges={
          <>
            <StatusBadge status="preview" label={currentStage} />
            <StatusBadge status="dry-run" />
            <StatusBadge status={modelMode ?? "experimental"} />
          </>
        }
        action={
          <button onClick={primaryAction.run} className="primary-button">
            <ClipboardList className="h-4 w-4" />
            {primaryAction.label}
          </button>
        }
      />

      <section className="rounded-lg border border-amber-300/30 bg-amber-300/10 px-4 py-3">
        <details>
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-sm text-amber-50/90">
            <span className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-200" />
              安全边界：当前结果为实验性辅助巡检，不作为最终现场诊断依据，不提供农事处置方案。
            </span>
            <ShieldCheck className="h-4 w-4 shrink-0 text-amber-200" />
          </summary>
          <div className="mt-3 space-y-3 pl-6">
            <ModelSafetyNotice mode={modelMode ?? "experimental"} compact />
            <p className="text-sm leading-6 text-amber-50/80">{safetyText}</p>
            {demoSafety?.warnings.slice(0, 3).map((item) => (
              <p key={item} className="rounded-lg border border-amber-300/20 bg-amber-300/10 p-2 text-xs leading-5 text-amber-50/80">
                {item}
              </p>
            ))}
            {modelStatusError && <ErrorState title="模型状态加载失败" message={modelStatusError} />}
          </div>
        </details>
      </section>

      <InspectionStepTimeline
        steps={timelineSteps}
        loadingKey={loadingStep}
        activeTarget={activeTab}
        onSelectTarget={(target) => setActiveTab(target as InspectionTab)}
      />

      <nav className="flex flex-wrap gap-2 rounded-lg border border-slate-700/70 bg-slate-950/30 p-2">
        {tabItems.map((item) => (
          <button
            key={item.key}
            onClick={() => setActiveTab(item.key)}
            className={`flex min-h-10 items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition ${
              activeTab === item.key
                ? "border-teal-300/40 bg-teal-300/10 text-teal-50"
                : "border-transparent text-slate-400 hover:bg-white/[0.05] hover:text-slate-100"
            }`}
          >
            <span>{item.label}</span>
            <span className="rounded-full bg-white/[0.06] px-2 py-0.5 text-xs text-slate-400">{item.badge}</span>
          </button>
        ))}
      </nav>

      <InspectionActionPanel items={actionItems} />

      <InspectionWorkflowLayout
        footer={error ? <ErrorState title="主后端连接或操作失败" message={error} /> : null}
        context={
          <InspectionContextPanel
            activeTab={activeTab}
            field={field}
            task={task}
            dryRun={dryRun}
            selectedRegion={selectedRegion}
            followup={followup}
            report={report}
            regions={regions}
            loadingStep={loadingStep}
            modelMode={modelMode}
            demoSafety={demoSafety}
            modelStatusError={modelStatusError}
            onSelectTab={setActiveTab}
            onCreateTask={() => void createTask()}
            onRunDryRun={() => void runDryRun()}
            onRunPhoneFollowup={() => void runPhoneFollowup()}
            onGenerateReport={() => void generateReport()}
          />
        }
      >
          {activeTab === "overview" && (
            <InspectionOverviewPanel
              field={field}
              task={task}
              dryRun={dryRun}
              regions={regions}
              followup={followup}
              report={report}
              loadingStep={loadingStep}
              onSelectTab={setActiveTab}
              onEnsureField={() => void ensureDemoField()}
              onCreateTask={() => void createTask()}
              onRunDryRun={() => void runDryRun()}
              onRunPhoneFollowup={() => void runPhoneFollowup()}
              onGenerateReport={() => void generateReport()}
            />
          )}

          {activeTab === "uav" && (
            <>
              <FieldTaskPanel field={field} task={task} loadingStep={loadingStep} onEnsureField={() => void ensureDemoField()} onCreateTask={() => void createTask()} />
              <IndexAndRegionPanel
                dryRun={dryRun}
                regions={regions}
                selectedRegion={selectedRegion}
                loadingStep={loadingStep}
                onRunDryRun={() => void runDryRun()}
                onSelectRegion={setSelectedRegionId}
                disabled={!task || !field}
              />
            </>
          )}

          {activeTab === "followup" && (
            <PhoneFollowupPanel
              field={field}
              task={task}
              selectedRegion={selectedRegion}
              followup={followup}
              loadingStep={loadingStep}
              onRunPhoneFollowup={() => void runPhoneFollowup()}
            />
          )}

          {activeTab === "reports" && (
            <>
              <ReportGenerationPanel
                field={field}
                task={task}
                dryRun={dryRun}
                regions={regions}
                report={report}
                loadingStep={loadingStep}
                onGenerateReport={() => void generateReport()}
              />
              <ReportWorkspace
                field={field}
                report={report}
                reportHistory={reportHistory}
                loadingStep={loadingStep}
                onRefreshHistory={() => field && void loadReportHistory(field.field_id)}
                onOpenReport={(reportId) => void openReport(reportId)}
              />
            </>
          )}
      </InspectionWorkflowLayout>
    </div>
  );
}
