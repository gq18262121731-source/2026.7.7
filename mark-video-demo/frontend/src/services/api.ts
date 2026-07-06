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

const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const API_PREFIX = "/api";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ORIGIN}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`主后端接口 ${path} 返回 ${response.status}: ${detail || "无错误详情"}`);
  }
  return response.json() as Promise<T>;
}

async function requestForm<T>(path: string, body: FormData): Promise<T> {
  const response = await fetch(`${API_ORIGIN}${path}`, {
    method: "POST",
    body
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`主后端上传接口 ${path} 返回 ${response.status}: ${detail || "无错误详情"}`);
  }
  return response.json() as Promise<T>;
}

async function requestMultipart<T>(path: string, body: FormData): Promise<T> {
  return requestForm<T>(path, body);
}

function endpoint(path: string) {
  return `${API_PREFIX}${path}`;
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
    formal_metric_available: model.formal_metric_available
  };
}

export function mapDetectionResult(item: BackendDetectionResult): DetectionRecord {
  const width = Math.max(item.image_width || 1, 1);
  const height = Math.max(item.image_height || 1, 1);

  return {
    task_id: item.record_id,
    backend_record_id: item.record_id,
    status: "completed",
    created_at: item.timestamp,
    operator: "system_user",
    detector_mode: item.detector_mode,
    model_stage: item.model_stage,
    fallback_to_mock: item.fallback_to_mock,
    formal_metric_available: item.formal_metric_available,
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
      formal_metric_available: item.formal_metric_available
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
  wsUrl: (path: "/ws/results" | "/ws/tasks" | "/ws/alerts") => {
    const url = new URL(API_ORIGIN);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = path;
    url.search = "";
    return url.toString();
  },
  health: () => requestJson<{ status: string }>("/healthz"),
  systemStatus: () => requestJson<SystemStatusResponse>(endpoint("/status")),
  modelStatus: () => requestJson<ModelsStatusResponse>(endpoint("/models/status")),
  demoSafety: () => requestJson<DemoSafetyStatus>(endpoint("/models/demo-safety")),
  dashboardSummary: () => requestJson<DashboardSummary>(endpoint("/dashboard/summary")),
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
