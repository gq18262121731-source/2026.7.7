import { useEffect, useMemo, useState } from "react";

import { ErrorState, StatusBadge } from "../../components/common";
import { InspectionWorkflowLayout } from "../../components/inspection";
import { PageHeader } from "../../components/ui";
import { api } from "../../services/api";
import { suqianInspectionApi } from "../../services/suqianInspection";
import type { AbnormalRegion, DetectionResult, FieldInfo, InspectionReport, UavDryRunResponse, UavTask } from "../../types/suqianInspection";
import { DEMO_FIELD } from "./constants";
import { makeDemoImageFile } from "./helpers";
import {
  FieldTaskPanel,
  IndexAndRegionPanel,
  PhoneFollowupPanel,
  ReportGenerationPanel,
  ReportWorkspace
} from "./SuqianInspectionPanels";
import { CurrentStepHero, InspectionStatusAside, StepProgress, type SuqianStepItem, type SuqianStepKey } from "./SuqianStepGuide";

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
  const [modelMode, setModelMode] = useState<string | null>(null);
  const [modelStatusError, setModelStatusError] = useState<string | null>(null);

  const selectedRegion = useMemo(
    () => regions.find((item) => item.region_id === selectedRegionId) ?? regions[0] ?? null,
    [regions, selectedRegionId]
  );

  useEffect(() => {
    void loadModelStatus();
  }, []);

  async function loadModelStatus() {
    setModelStatusError(null);
    try {
      const modelStatus = await api.modelStatus();
      setModelMode(modelStatus.detector_mode);
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
      setError(exc instanceof Error ? exc.message : "本步骤暂未接通后端，请检查主后端服务，或先使用页面中的示范流程说明。");
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
    }
  }

  async function generateReport() {
    if (!field || !task) return;
    const generated = await runStep("report", () => suqianInspectionApi.generateReport(field.field_id, task.uav_task_id));
    if (generated) {
      const detail = await suqianInspectionApi.getReport(generated.report_id);
      setReport(detail);
      await loadReportHistory(field.field_id);
    }
  }

  async function openReport(reportId: string) {
    const detail = await runStep("report-history", () => suqianInspectionApi.getReport(reportId));
    if (detail) setReport(detail);
  }

  const currentStepKey: SuqianStepKey = !field ? "field" : !task ? "task" : !dryRun ? "analysis" : !followup ? "followup" : "report";
  const currentStage = currentStepKey === "field" ? "第 1 步" : currentStepKey === "task" ? "第 2 步" : currentStepKey === "analysis" ? "第 3 步" : currentStepKey === "followup" ? "第 4 步" : report ? "报告已生成" : "第 5 步";
  const stepItems: SuqianStepItem[] = [
    {
      key: "field",
      number: 1,
      title: "选择巡检田块",
      shortTitle: "选择田块",
      description: "本流程将完成一次“无人机发现异常 -> 手机复查 -> 生成报告”的巡检闭环。请先加载示范田块，开始本次演示巡检。",
      completed: Boolean(field)
    },
    {
      key: "task",
      number: 2,
      title: "创建巡检任务",
      shortTitle: "创建任务",
      description: `田块已确认：${field?.field_name ?? "宿迁一号田"}。下一步创建本次无人机巡检任务。`,
      completed: Boolean(task)
    },
    {
      key: "analysis",
      number: 3,
      title: "无人机异常分析",
      shortTitle: "异常分析",
      description: "系统将基于演示巡检数据生成异常区域，供手机近景复查。",
      completed: Boolean(dryRun)
    },
    {
      key: "followup",
      number: 4,
      title: "手机近景复查",
      shortTitle: "手机复查",
      description: `无人机已发现 ${regions.length || 0} 个异常区域，请使用手机近景图进行复查，复查结果会回写到异常区域。`,
      completed: Boolean(followup)
    },
    {
      key: "report",
      number: 5,
      title: "生成巡检报告",
      shortTitle: "生成报告",
      description: "系统将基于田块、无人机异常、手机复查和报告中的智能建议生成实验性巡检报告。",
      completed: Boolean(report)
    }
  ];
  const currentStep = stepItems.find((item) => item.key === currentStepKey) ?? stepItems[0];
  const primaryAction: { label: string; run: () => void; loading: boolean; disabled?: boolean } = (() => {
    if (currentStepKey === "field") return { label: "加载示范田块", run: () => void ensureDemoField(), loading: loadingStep === "field" };
    if (currentStepKey === "task") return { label: "创建 UAV 任务", run: () => void createTask(), loading: loadingStep === "task", disabled: !field };
    if (currentStepKey === "analysis") return { label: "执行异常分析", run: () => void runDryRun(), loading: loadingStep === "dry-run", disabled: !field || !task };
    if (currentStepKey === "followup") return { label: "使用示范复查图", run: () => void runPhoneFollowup(), loading: loadingStep === "followup", disabled: !field || !task || !selectedRegion };
    return { label: report ? "重新生成巡检报告" : "生成巡检报告", run: () => void generateReport(), loading: loadingStep === "report", disabled: !field || !task };
  })();

  const mainContent = (() => {
    if (currentStepKey === "field" || currentStepKey === "task") {
      return <FieldTaskPanel field={field} task={task} loadingStep={loadingStep} onEnsureField={() => void ensureDemoField()} onCreateTask={() => void createTask()} />;
    }
    if (currentStepKey === "analysis") {
      return (
        <IndexAndRegionPanel
          dryRun={dryRun}
          regions={regions}
          selectedRegion={selectedRegion}
          loadingStep={loadingStep}
          onRunDryRun={() => void runDryRun()}
          onSelectRegion={setSelectedRegionId}
          disabled={!task || !field}
        />
      );
    }
    if (currentStepKey === "followup") {
      return (
        <PhoneFollowupPanel
          field={field}
          task={task}
          selectedRegion={selectedRegion}
          followup={followup}
          loadingStep={loadingStep}
          onRunPhoneFollowup={() => void runPhoneFollowup()}
        />
      );
    }
    return (
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
        {(report || reportHistory.length > 0) && (
          <ReportWorkspace
            field={field}
            report={report}
            reportHistory={reportHistory}
            loadingStep={loadingStep}
            onRefreshHistory={() => field && void loadReportHistory(field.field_id)}
            onOpenReport={(reportId) => void openReport(reportId)}
          />
        )}
      </>
    );
  })();

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="协同巡检工作台"
        title="宿迁一号田多源巡检闭环"
        description="按 5 步完成“无人机发现异常、手机近景复查、生成巡检报告”的演示闭环。"
        badges={
          <>
            <StatusBadge status="preview" label={currentStage} />
            <StatusBadge status="dry-run" label="无人机异常分析" />
            <StatusBadge status={modelMode ?? "experimental"} />
          </>
        }
      />

      <CurrentStepHero
        step={currentStep}
        statusLabel={report ? "报告已生成" : currentStep.completed ? "已完成" : "等待操作"}
        actionLabel={primaryAction.label}
        loading={primaryAction.loading}
        disabled={primaryAction.disabled}
        onAction={primaryAction.run}
      />

      <StepProgress steps={stepItems} currentKey={currentStepKey} loadingStep={loadingStep} />

      <InspectionWorkflowLayout
        footer={error ? <ErrorState title="当前步骤暂不可用" message={error} /> : null}
        context={
          <div className="space-y-5">
            {modelStatusError && <ErrorState title="模型状态加载失败" message={modelStatusError} />}
            <InspectionStatusAside
              field={field}
              task={task}
              dryRun={dryRun}
              selectedRegion={selectedRegion}
              followup={followup}
              report={report}
              regions={regions}
              modelMode={modelMode}
            />
          </div>
        }
      >
        {mainContent}
      </InspectionWorkflowLayout>
    </div>
  );
}
