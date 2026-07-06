import type {
  AbnormalRegion,
  AbnormalRegionListResponse,
  DetectionResult,
  FieldInfo,
  FieldListResponse,
  InspectionReport,
  InspectionReportListResponse,
  UavDryRunResponse,
  UavTask
} from "../types/suqianInspection";

const MAIN_API_BASE = (
  import.meta.env.VITE_MAIN_BACKEND_API_BASE ??
  `${(import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "")}/api`
).replace(/\/$/, "");

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${MAIN_API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...init?.headers },
      ...init
    });
  } catch (exc) {
    throw new Error(buildNetworkError(path, exc));
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`主后端接口 ${path} 返回 ${response.status}: ${detail || "无错误详情"}`);
  }
  return response.json() as Promise<T>;
}

async function formRequest<T>(path: string, body: FormData): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${MAIN_API_BASE}${path}`, {
      method: "POST",
      body
    });
  } catch (exc) {
    throw new Error(buildNetworkError(path, exc));
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`主后端上传接口 ${path} 返回 ${response.status}: ${detail || "无错误详情"}`);
  }
  return response.json() as Promise<T>;
}

function buildNetworkError(path: string, exc: unknown) {
  const reason = exc instanceof Error ? exc.message : "未知网络错误";
  return `无法连接主后端接口 ${path}：${reason}。请确认主后端正在运行，默认地址为 ${MAIN_API_BASE}，或通过 VITE_MAIN_BACKEND_API_BASE 指向正确服务。`;
}

export const suqianInspectionApi = {
  listFields: () => jsonRequest<FieldListResponse>("/fields?status=active&page=1&page_size=100"),
  createField: (field: {
    field_id: string;
    field_name: string;
    location_city: string;
    location_district: string;
    location_town: string;
    center_lat: number;
    center_lng: number;
    current_growth_stage: string;
    notes: string;
  }) =>
    jsonRequest<FieldInfo>("/fields", {
      method: "POST",
      body: JSON.stringify(field)
    }),
  updateField: (fieldId: string, payload: Partial<FieldInfo>) =>
    jsonRequest<FieldInfo>(`/fields/${fieldId}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  createUavTask: (field: FieldInfo) =>
    jsonRequest<UavTask>("/uav/tasks", {
      method: "POST",
      body: JSON.stringify({
        field_id: field.field_id,
        task_name: `${field.field_name} UAV dry-run 巡检`,
        sensor_type: "multispectral",
        data_mode: "dry_run",
        growth_stage: field.current_growth_stage ?? "分蘖期",
        weather_text: "演示天气：阴天，湿度较高"
      })
    }),
  runDryRun: (task: UavTask, field: FieldInfo) =>
    jsonRequest<UavDryRunResponse>(`/uav/tasks/${task.uav_task_id}/dry-run`, {
      method: "POST",
      body: JSON.stringify({
        field_id: field.field_id,
        task_name: task.task_name,
        sensor_type: "multispectral",
        growth_stage: field.current_growth_stage ?? "分蘖期",
        weather_text: "演示天气：阴天，湿度较高",
        dry_run_profile: "moderate_abnormal"
      })
    }),
  listAbnormalRegions: (taskId: string) =>
    jsonRequest<AbnormalRegionListResponse>(`/uav/tasks/${taskId}/abnormal-regions`),
  getAbnormalRegion: (regionId: string) => jsonRequest<AbnormalRegion>(`/uav/abnormal-regions/${regionId}`),
  phoneFollowup: (region: AbnormalRegion, field: FieldInfo, task: UavTask, file: File) => {
    const form = new FormData();
    form.append("file", file);
    form.append("field_id", field.field_id);
    form.append("uav_task_id", task.uav_task_id);
    form.append("source_type", "phone_followup");
    form.append("model_hint", "phone");
    form.append("target_type", "disease");
    form.append("region_name", region.region_name);
    return formRequest<DetectionResult>(`/uav/abnormal-regions/${region.region_id}/phone-followup`, form);
  },
  generateReport: (fieldId: string, taskId: string) =>
    jsonRequest<InspectionReport>("/inspection-reports/generate", {
      method: "POST",
      body: JSON.stringify({
        field_id: fieldId,
        uav_task_id: taskId,
        include_rag: true,
        include_risk: true
      })
    }),
  getReport: (reportId: string) => jsonRequest<InspectionReport>(`/inspection-reports/${reportId}`),
  listReports: (fieldId: string) => jsonRequest<InspectionReportListResponse>(`/inspection-reports?field_id=${encodeURIComponent(fieldId)}`)
};
