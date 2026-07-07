export type SceneType = "phone_closeup" | "uav_multispectral";

export interface PlatformModel {
  key: string;
  name: string;
  scene_type: SceneType;
  labels: string[];
  status: string;
  last_called_at?: string;
  today_calls?: number;
  model_stage?: string | null;
  warning?: string | null;
  usage_scope?: string | null;
  formal_metric_available?: boolean | null;
  model_status?: string | null;
  capability_level?: string | null;
  fallback_used?: boolean | null;
  is_mock?: boolean | null;
  target_type?: string | null;
  allow_dashboard_statistics?: boolean | null;
  allow_latest_alerts?: boolean | null;
  allow_backend_demo_claim?: boolean | null;
  allow_candidate_claim?: boolean | null;
  allow_official_metric_claim?: boolean | null;
}

export interface DetectionBox {
  id: string;
  label: string;
  confidence: number;
  bbox_norm: { x: number; y: number; w: number; h: number };
  severity: string;
}

export interface DetectionRecord {
  task_id: string;
  status: string;
  created_at: string;
  operator: string;
  model: PlatformModel;
  image: {
    sample_key: string;
    source_type: SceneType;
    source_name: string;
    original_url: string;
    width: number;
    height: number;
  };
  detections: DetectionBox[];
  summary: {
    top_label: string;
    top_confidence: number;
    detection_count: number;
    process_ms: number;
    risk_level: string;
  };
  analysis: {
    mode: string;
    title: string;
    text: string;
    prevention?: string;
  };
  processing_status: string;
  backend_record_id?: string;
  field_id?: string | null;
  plot_id?: string | null;
  plot_name?: string | null;
  region_name?: string | null;
  source_type?: string | null;
  target_type?: string | null;
  lng?: number | null;
  lat?: number | null;
  model_name?: string | null;
  model_version?: string | null;
  result_image_url?: string;
  detector_mode?: string;
  model_stage?: string;
  fallback_to_mock?: boolean;
  formal_metric_available?: boolean;
  model_status?: string | null;
  allow_dashboard_statistics?: boolean | null;
  allow_latest_alerts?: boolean | null;
  allow_backend_demo_claim?: boolean | null;
  allow_candidate_claim?: boolean | null;
  allow_official_metric_claim?: boolean | null;
  dashboard_exclusion_reason?: string | null;
  latest_alerts_exclusion_reason?: string | null;
}

export interface BackendDetection {
  class_id: number;
  label: string;
  class_name?: string | null;
  class_code?: string | null;
  category_type?: string | null;
  confidence: number;
  bbox: [number, number, number, number];
  area_ratio: number;
}

export interface BackendDetectionResult {
  record_id: string;
  image_id: string;
  field_id?: string | null;
  plot_id?: string | null;
  plot_name?: string | null;
  region_name: string;
  timestamp: string;
  image_url: string;
  result_image_url: string;
  image_width: number;
  image_height: number;
  source_type: string;
  model_name: string;
  model_version: string;
  detector_mode: string;
  is_smoke: boolean;
  model_stage: string;
  formal_metric_available: boolean;
  current_target_type?: string | null;
  fallback_to_mock: boolean;
  model_hint?: string | null;
  target_type?: string | null;
  geo?: { lng?: number | null; lat?: number | null };
  model_display_name?: string | null;
  model_warning?: string | null;
  model_usage_scope?: string | null;
  model_capability_level?: string | null;
  model_status?: string | null;
  allow_dashboard_statistics?: boolean | null;
  allow_latest_alerts?: boolean | null;
  allow_backend_demo_claim?: boolean | null;
  allow_candidate_claim?: boolean | null;
  allow_official_metric_claim?: boolean | null;
  dashboard_exclusion_reason?: string | null;
  latest_alerts_exclusion_reason?: string | null;
  detections: BackendDetection[];
  summary: {
    disease_count: number;
    main_disease?: string | null;
    max_confidence: number;
    severity: string;
    risk_level: string;
  };
  suggestion: {
    title: string;
    content: string;
    disclaimer?: string | null;
  };
}

export interface RecordListResponse {
  items: BackendDetectionResult[];
  total: number;
  page: number;
  page_size: number;
}

export interface DashboardSummary {
  today_detect_count: number;
  total_record_count: number;
  disease_record_count: number;
  normal_record_count: number;
  high_risk_plot_count: number;
  medium_risk_plot_count: number;
  low_risk_plot_count: number;
  risk_level_counts: Record<string, number>;
  latest_records: Array<{
    record_id: string;
    plot_name?: string | null;
    main_disease?: string | null;
    severity: string;
    risk_level: string;
    result_image_url: string;
    timestamp: string;
    source_type?: string | null;
    model_name?: string | null;
    model_stage?: string | null;
    model_status?: string | null;
    fallback_to_mock?: boolean;
    allow_dashboard_statistics?: boolean | null;
    allow_latest_alerts?: boolean | null;
    dashboard_exclusion_reason?: string | null;
    latest_alerts_exclusion_reason?: string | null;
  }>;
  latest_alerts: Array<{
    alert_id: string;
    record_id: string;
    plot_name?: string | null;
    main_disease?: string | null;
    severity: string;
    risk_level: string;
    message: string;
    timestamp: string;
  }>;
}

export interface ModelPathStatus {
  name: string;
  display_name?: string | null;
  path_exists: boolean;
  ready: boolean;
  loaded?: boolean | null;
  model_stage?: string | null;
  is_smoke?: boolean | null;
  current_target_type?: string | null;
  formal_metric_available?: boolean | null;
  class_codes: string[];
  source_types: string[];
  warning?: string | null;
  usage_scope?: string | null;
  capability_level?: string | null;
  model_status?: string | null;
  fallback_used?: boolean | null;
  is_mock?: boolean | null;
  target_type?: string | null;
  allow_dashboard_statistics?: boolean | null;
  allow_latest_alerts?: boolean | null;
  allow_backend_demo_claim?: boolean | null;
  allow_candidate_claim?: boolean | null;
  allow_official_metric_claim?: boolean | null;
  dashboard_exclusion_reason?: string | null;
  latest_alerts_exclusion_reason?: string | null;
}

export interface ModelsStatusResponse {
  detector_mode: string;
  active_model_name: string;
  active_model_version: string;
  phone_model: ModelPathStatus;
  phone_experimental_model: ModelPathStatus;
  phone_tungro_experimental_policy?: ModelPathStatus;
  uav_crop_model: ModelPathStatus;
  uav_blb_model: ModelPathStatus;
  uav_blb_experimental_model: ModelPathStatus;
  mock_model: ModelPathStatus;
  fallback_to_mock: boolean;
  active_routing: Record<string, string>;
  demo_safety: DemoSafetyStatus;
}

export interface DemoSafetyStatus {
  demo_safe: boolean;
  has_smoke_models: boolean;
  has_formal_models: boolean;
  formal_metric_available: boolean;
  warnings: string[];
  display_rules: string[];
}

export interface SystemStatusResponse {
  service_status: string;
  model_loaded: boolean;
  model_name: string;
  model_version: string;
  detector_mode: string;
  database_status: string;
  storage_status: string;
  websocket_clients: number;
  capabilities: Record<string, boolean>;
  models: Record<string, string | boolean>;
  storage: Record<string, string | boolean>;
  error_message?: string | null;
}

export interface LLMStatusResponse {
  llm_mode: string;
  llm_provider: string;
  llm_model: string;
  json_response_format_enabled: boolean;
  mock_fallback_enabled: boolean;
  api_key_configured: boolean;
  prompt_version: string;
}

export interface DiagnosisReportRequest {
  record_id?: string | null;
  disease_id?: string | null;
  model_class?: string | null;
  confidence?: number | null;
  source_type?: string | null;
  user_question?: string | null;
  field_id?: string | null;
  plot_id?: string | null;
  uav_task_id?: string | null;
  abnormal_region_id?: string | null;
  risk_level?: string | null;
  severity?: string | null;
}

export interface DiagnosisReportResponse {
  suspected_disease: { disease_id?: string; zh_name?: string; en_name?: string } | Record<string, unknown>;
  model_result_summary: string;
  knowledge_summary: string;
  risk_level: string;
  manual_check_questions: string[];
  management_suggestions: string[];
  uncertainty_notes: string[];
  evidence_sources: Array<{
    source_id: string;
    source_title: string;
    source_type: string;
    authority_level: string;
    url_or_reference: string;
    language: string;
    notes?: string | null;
  }>;
  insufficient_evidence: boolean;
  llm_mode: string;
  llm_provider: string;
  llm_model: string;
  prompt_version: string;
  fallback_used: boolean;
  api_error_type?: string | null;
}

export type FarmAnalysisReportType = "record_analysis" | "plot_analysis" | "daily_summary";

export interface FarmAnalysisReportRequest {
  plot_id: string;
  record_id?: string | null;
  crop: "rice";
  include_weather: boolean;
  include_history_days: number;
  report_type: FarmAnalysisReportType;
}

export interface FarmAnalysisReportResponse {
  success: boolean;
  report_id: string;
  status: "success" | "fallback" | "failed";
  summary: string;
  pdf_url: string;
  preview_url: string;
  fallback_used: boolean;
  weather_available: boolean;
  rag_available: boolean;
  pdf_fallback_used: boolean;
  created_at: string;
}

export interface FarmAnalysisReportHistoryItem {
  report_id: string;
  plot_id: string;
  record_id?: string | null;
  report_type: FarmAnalysisReportType;
  crop: string;
  summary: string;
  pdf_url: string;
  preview_url: string;
  fallback_used: boolean;
  weather_available: boolean;
  rag_available: boolean;
  pdf_fallback_used: boolean;
  created_at: string;
}

export interface FarmAnalysisReportHistoryResponse {
  items: FarmAnalysisReportHistoryItem[];
  total: number;
}

export interface DiseaseListItem {
  disease_id: string;
  zh_name: string;
  en_name: string;
  authority_level: string;
  model_supported: boolean;
}

export interface AlertDetail {
  alert_id: string;
  alert_source: string;
  plot_id: string;
  plot_name?: string | null;
  region_name: string;
  main_disease?: string | null;
  severity: string;
  risk_level: string;
  status: string;
  message: string;
  record_ids: string[];
  first_record_id: string;
  latest_record_id: string;
  prediction_id?: string | null;
  prediction_window_days?: number | null;
  first_seen_at: string;
  latest_seen_at: string;
  cooldown_until: string;
  created_at: string;
  updated_at: string;
  suggestion: {
    title: string;
    content: string;
    disclaimer?: string | null;
  };
}

export interface AlertPageResponse {
  items: AlertDetail[];
  total: number;
  page: number;
  page_size: number;
}

export interface AlertAction {
  action_id: string;
  alert_id: string;
  action_type: string;
  operator_id?: string | null;
  operator_name?: string | null;
  note?: string | null;
  created_at: string;
}

export interface RiskPrediction {
  plot_id: string;
  prediction_window_days: number;
  prediction_time: string;
  risk_score: number;
  risk_probability: number;
  risk_probability_note: string;
  risk_level: string;
  predicted_diseases: Array<{ label: string; probability: number }>;
  main_factors: string[];
  prediction_id?: string | null;
  suggestion: {
    title: string;
    content: string;
    disclaimer?: string | null;
  };
  model: {
    type: string;
    version: string;
    metrics: Record<string, string>;
  };
}

export interface PredictionSummary {
  high_risk_plot_count: number;
  medium_risk_plot_count: number;
  top_risk_plots: Array<Record<string, unknown>>;
  top_predicted_diseases: Array<Record<string, unknown>>;
  risk_factor_counts: Record<string, number>;
}

export interface PredictionRiskMap {
  type: string;
  total: number;
  points: Array<{
    plot_id: string;
    plot_name?: string | null;
    lng?: number | null;
    lat?: number | null;
    predicted_risk_level: string;
    predicted_disease?: string | null;
    risk_score: number;
    intensity: number;
    color: string;
  }>;
}

export interface BatchTaskStatus {
  task_id: string;
  task_type: string;
  status: string;
  total_images: number;
  processed_images: number;
  failed_images: number;
  progress: number;
  record_ids: string[];
  failed_items: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
}
