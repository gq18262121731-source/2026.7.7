import type {
  BackendDetectionResult,
  AlertAction,
  AlertDetail,
  AlertPageResponse,
  BatchTaskStatus,
  DashboardSummary,
  DemoSafetyStatus,
  DetectionRecord,
  DiagnosisReportRequest,
  DiagnosisReportResponse,
  DiseaseListItem,
  FarmAnalysisReportHistoryResponse,
  FarmAnalysisReportRequest,
  FarmAnalysisReportResponse,
  LLMStatusResponse,
  ModelPathStatus,
  ModelsStatusResponse,
  PlatformModel,
  PredictionRiskMap,
  PredictionSummary,
  RecordListResponse,
  RiskPrediction,
  SceneType,
  SystemStatusResponse
} from "../types/api";

const DEFAULT_API_ORIGIN = "";
const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_ORIGIN).replace(/\/$/, "");
const API_PREFIX = "/api";

function runtimeOrigin() {
  if (API_ORIGIN) return API_ORIGIN;
  if (typeof window !== "undefined") return window.location.origin;
  return "http://localhost";
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_ORIGIN}${path}`, {
      headers: { "Content-Type": "application/json", ...init?.headers },
      ...init
    });
  } catch (exc) {
    throw new Error(buildNetworkError(path, exc));
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(buildHttpError("主后端接口", path, response.status, detail));
  }
  return response.json() as Promise<T>;
}

async function requestForm<T>(path: string, body: FormData): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_ORIGIN}${path}`, {
      method: "POST",
      body
    });
  } catch (exc) {
    throw new Error(buildNetworkError(path, exc));
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(buildHttpError("主后端上传接口", path, response.status, detail));
  }
  return response.json() as Promise<T>;
}

async function requestMultipart<T>(path: string, body: FormData): Promise<T> {
  return requestForm<T>(path, body);
}

function endpoint(path: string) {
  return `${API_PREFIX}${path}`;
}

function buildNetworkError(path: string, exc: unknown) {
  const reason = exc instanceof Error ? exc.message : "网络不可达";
  return `后端未连接或接口暂不可用：${path}。当前 API 为 ${API_ORIGIN}，页面会优先保留可用数据；请启动主后端或检查 VITE_API_BASE_URL。技术信息：${reason}`;
}

function buildHttpError(label: string, path: string, status: number, detail: string) {
  return `${label} ${path} 返回 ${status}。请确认后端接口已准备好；演示现场可继续使用已加载数据或示范流程。${detail ? `详情：${detail}` : ""}`;
}

function assetUrl(path?: string | null) {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return `${API_ORIGIN}${path}`;
}

function toSceneType(value: string): SceneType {
  return value.includes("uav") ? "uav_multispectral" : "phone_closeup";
}

function modelToPlatform(model: ModelPathStatus): PlatformModel {
  return {
    key: model.name,
    name: model.display_name ?? model.name,
    scene_type: model.source_types.some((item) => item.includes("uav")) ? "uav_multispectral" : "phone_closeup",
    labels: model.class_codes,
    status: model.ready || model.loaded ? "ready" : "unavailable",
    model_stage: model.model_stage,
    warning: model.warning,
    usage_scope: model.usage_scope,
    formal_metric_available: model.formal_metric_available,
    model_status: model.model_status,
    capability_level: model.capability_level,
    fallback_used: model.fallback_used,
    is_mock: model.is_mock,
    target_type: model.target_type ?? model.current_target_type,
    allow_dashboard_statistics: model.allow_dashboard_statistics,
    allow_latest_alerts: model.allow_latest_alerts,
    allow_backend_demo_claim: model.allow_backend_demo_claim,
    allow_candidate_claim: model.allow_candidate_claim,
    allow_official_metric_claim: model.allow_official_metric_claim
  };
}

export function mapDetectionResult(item: BackendDetectionResult): DetectionRecord {
  const width = Math.max(item.image_width || 1, 1);
  const height = Math.max(item.image_height || 1, 1);

  return {
    task_id: item.record_id,
    backend_record_id: item.record_id,
    field_id: item.field_id,
    plot_id: item.plot_id,
    plot_name: item.plot_name,
    region_name: item.region_name,
    source_type: item.source_type,
    target_type: item.target_type ?? item.current_target_type,
    lng: item.geo?.lng ?? null,
    lat: item.geo?.lat ?? null,
    model_name: item.model_name,
    model_version: item.model_version,
    status: "completed",
    created_at: item.timestamp,
    operator: "system_user",
    detector_mode: item.detector_mode,
    model_stage: item.model_stage,
    fallback_to_mock: item.fallback_to_mock,
    formal_metric_available: item.formal_metric_available,
    model_status: item.model_status,
    allow_dashboard_statistics: item.allow_dashboard_statistics,
    allow_latest_alerts: item.allow_latest_alerts,
    allow_backend_demo_claim: item.allow_backend_demo_claim,
    allow_candidate_claim: item.allow_candidate_claim,
    allow_official_metric_claim: item.allow_official_metric_claim,
    dashboard_exclusion_reason: item.dashboard_exclusion_reason,
    latest_alerts_exclusion_reason: item.latest_alerts_exclusion_reason,
    result_image_url: assetUrl(item.result_image_url),
    model: {
      key: item.model_name,
      name: item.model_display_name ?? item.model_name,
      scene_type: toSceneType(item.source_type),
      labels: item.detections.map((detection) => detection.label),
      status: item.detector_mode,
      model_stage: item.model_stage,
      warning: item.model_warning,
      usage_scope: item.model_usage_scope,
      formal_metric_available: item.formal_metric_available,
      model_status: item.model_status,
      capability_level: item.model_capability_level,
      fallback_used: item.fallback_to_mock,
      target_type: item.target_type ?? item.current_target_type,
      allow_dashboard_statistics: item.allow_dashboard_statistics,
      allow_latest_alerts: item.allow_latest_alerts,
      allow_backend_demo_claim: item.allow_backend_demo_claim,
      allow_candidate_claim: item.allow_candidate_claim,
      allow_official_metric_claim: item.allow_official_metric_claim
    },
    image: {
      sample_key: item.image_id,
      source_type: toSceneType(item.source_type),
      source_name: item.plot_name ?? item.region_name ?? item.source_type,
      original_url: assetUrl(item.image_url),
      width,
      height
    },
    detections: item.detections.map((detection, index) => {
      const [x1, y1, x2, y2] = detection.bbox;
      return {
        id: `${item.record_id}-${index}`,
        label: detection.label,
        confidence: detection.confidence,
        severity: item.summary.severity,
        bbox_norm: {
          x: Math.max(0, x1 / width),
          y: Math.max(0, y1 / height),
          w: Math.max(0.01, (x2 - x1) / width),
          h: Math.max(0.01, (y2 - y1) / height)
        }
      };
    }),
    summary: {
      top_label: item.summary.main_disease ?? "未识别到明确病害",
      top_confidence: item.summary.max_confidence,
      detection_count: item.summary.disease_count,
      process_ms: 0,
      risk_level: item.summary.risk_level
    },
    analysis: {
      mode: item.detector_mode,
      title: item.suggestion.title,
      text: item.suggestion.content,
      prevention: item.suggestion.disclaimer ?? undefined
    },
    processing_status: item.fallback_to_mock ? "mock fallback" : item.model_stage
  };
}

export const api = {
  apiOrigin: API_ORIGIN,
  frontendMode: import.meta.env.VITE_FRONTEND_MODE ?? "real-first",
  wsUrl: (path: "/ws/results" | "/ws/tasks" | "/ws/alerts") => {
    const url = new URL(runtimeOrigin());
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = path;
    url.search = "";
    return url.toString();
  },
  health: () => requestJson<{ status: string }>("/healthz"),
  systemStatus: () => requestJson<SystemStatusResponse>(endpoint("/status")),
  llmStatus: () => requestJson<LLMStatusResponse>(endpoint("/agent/llm-status")),
  modelStatus: () => requestJson<ModelsStatusResponse>(endpoint("/models/status")),
  demoSafety: () => requestJson<DemoSafetyStatus>(endpoint("/models/demo-safety")),
  dashboardSummary: () => requestJson<DashboardSummary>(endpoint("/dashboard/summary")),
  latestRecords: async (limit = 8) => {
    const res = await requestJson<RecordListResponse>(endpoint(`/records?page=1&page_size=${limit}`));
    return res.items.map(mapDetectionResult);
  },
  latestAlerts: (limit = 8) => requestJson<AlertPageResponse>(endpoint(`/alerts?page=1&page_size=${limit}`)),
  records: async (page = 1, pageSize = 20) => {
    const res = await requestJson<RecordListResponse>(endpoint(`/records?page=${page}&page_size=${pageSize}`));
    return {
      records: res.items.map(mapDetectionResult),
      total: res.total,
      page: res.page,
      page_size: res.page_size
    };
  },
  record: async (recordId: string) => mapDetectionResult(await requestJson<BackendDetectionResult>(endpoint(`/records/${recordId}`))),
  detectImage: async (
    file: File,
    metadata: {
      source_type?: string;
      model_hint?: string;
      target_type?: string;
      plot_name?: string;
      region_name?: string;
    } = {}
  ) => {
    const form = new FormData();
    form.append("file", file);
    form.append("source_type", metadata.source_type ?? "phone_rgb");
    form.append("model_hint", metadata.model_hint ?? "phone");
    form.append("target_type", metadata.target_type ?? "disease");
    form.append("plot_name", metadata.plot_name ?? "前端上传样本");
    form.append("region_name", metadata.region_name ?? "人工上传");
    return mapDetectionResult(await requestForm<BackendDetectionResult>(endpoint("/detect/image"), form));
  },
  platformModels: async () => {
    const status = await requestJson<ModelsStatusResponse>(endpoint("/models/status"));
    return {
      models: [
        status.phone_model,
        status.phone_experimental_model,
        ...(status.phone_tungro_experimental_policy ? [status.phone_tungro_experimental_policy] : []),
        status.uav_crop_model,
        status.uav_blb_model,
        status.uav_blb_experimental_model,
        status.mock_model
      ].map(modelToPlatform),
      active_model: status.active_model_name,
      status: status.detector_mode,
      raw: status
    };
  },
  diagnosisReport: (payload: DiagnosisReportRequest) =>
    requestJson<DiagnosisReportResponse>(endpoint("/agent/diagnosis-report"), {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  generateFarmAnalysisReport: (payload: FarmAnalysisReportRequest) =>
    requestJson<FarmAnalysisReportResponse>(endpoint("/farm-analysis-reports/generate"), {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getFarmAnalysisReportHistory: (params: { plot_id?: string } = {}) => {
    const query = new URLSearchParams();
    if (params.plot_id) query.set("plot_id", params.plot_id);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return requestJson<FarmAnalysisReportHistoryResponse>(endpoint(`/farm-analysis-reports${suffix}`));
  },
  getFarmAnalysisReportDownloadUrl: (reportId: string) => `${API_ORIGIN}${endpoint(`/farm-analysis-reports/${encodeURIComponent(reportId)}/download`)}`,
  getFarmAnalysisReportPreviewUrl: (reportId: string) => `${API_ORIGIN}${endpoint(`/farm-analysis-reports/${encodeURIComponent(reportId)}/preview`)}`,
  farmAnalysisReportHistory: (params: { plot_id?: string } = {}) => {
    const query = new URLSearchParams();
    if (params.plot_id) query.set("plot_id", params.plot_id);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return requestJson<FarmAnalysisReportHistoryResponse>(endpoint(`/farm-analysis-reports${suffix}`));
  },
  reportHistory: (params: { plot_id?: string } = {}) => {
    const query = new URLSearchParams();
    if (params.plot_id) query.set("plot_id", params.plot_id);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return requestJson<FarmAnalysisReportHistoryResponse>(endpoint(`/farm-analysis-reports${suffix}`));
  },
  reportDownloadUrl: (reportId: string) => `${API_ORIGIN}${endpoint(`/farm-analysis-reports/${encodeURIComponent(reportId)}/download`)}`,
  reportPreviewUrl: (reportId: string) => `${API_ORIGIN}${endpoint(`/farm-analysis-reports/${encodeURIComponent(reportId)}/preview`)}`,
  diseases: () => requestJson<{ items: DiseaseListItem[]; count: number }>(endpoint("/knowledge/diseases")),
  alerts: (page = 1, pageSize = 20, status?: string) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (status) params.set("status", status);
    return requestJson<AlertPageResponse>(endpoint(`/alerts?${params.toString()}`));
  },
  alertDetail: (alertId: string) => requestJson<AlertDetail>(endpoint(`/alerts/${encodeURIComponent(alertId)}`)),
  resolveAlert: (alertId: string, note: string) =>
    requestJson<AlertDetail>(endpoint(`/alerts/${encodeURIComponent(alertId)}/resolve`), {
      method: "POST",
      body: JSON.stringify({
        operator_name: "frontend_user",
        note
      })
    }),
  alertActions: (alertId: string) => requestJson<{ items: AlertAction[]; total: number }>(endpoint(`/alerts/${encodeURIComponent(alertId)}/actions`)),
  predictionSummary: () => requestJson<PredictionSummary>(endpoint("/prediction/dashboard/summary")),
  predictionRiskMap: () => requestJson<PredictionRiskMap>(endpoint("/prediction/risk-map")),
  predictPlot: (plotId: string, windowDays = 7) =>
    requestJson<RiskPrediction>(endpoint(`/prediction/plots/${encodeURIComponent(plotId)}?window_days=${windowDays}&save=true&create_alert=true`)),
  batchDetect: async (files: File[], metadata: { source_type?: string; plot_name?: string; region_name?: string } = {}) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    form.append("source_type", metadata.source_type ?? "manual_upload");
    form.append("plot_name", metadata.plot_name ?? "批量检测任务");
    form.append("region_name", metadata.region_name ?? "前端批量上传");
    return requestMultipart<BatchTaskStatus>(endpoint("/detect/batch"), form);
  },
  batchTask: (taskId: string) => requestJson<BatchTaskStatus>(endpoint(`/tasks/${encodeURIComponent(taskId)}`))
};
