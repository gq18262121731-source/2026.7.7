export interface FieldInfo {
  field_id: string;
  field_name: string;
  location_city: string;
  location_district?: string | null;
  location_town?: string | null;
  location_village?: string | null;
  center_lat?: number | null;
  center_lng?: number | null;
  area_estimate_mu?: number | null;
  crop_type: string;
  current_growth_stage?: string | null;
  field_status: string;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface FieldListResponse {
  items: FieldInfo[];
  total: number;
  page: number;
  page_size: number;
}

export interface UavTask {
  uav_task_id: string;
  field_id?: string | null;
  task_name: string;
  flight_date?: string | null;
  sensor_type: string;
  data_mode: string;
  growth_stage?: string | null;
  weather_text?: string | null;
  status: string;
  summary?: string | null;
  is_mock: boolean;
  created_at: string;
  updated_at: string;
}

export interface UavIndexResult {
  index_result_id: string;
  uav_task_id: string;
  field_id?: string | null;
  index_type: "ndvi" | "ndre" | string;
  index_image_url: string;
  min_value?: number | null;
  max_value?: number | null;
  mean_value?: number | null;
  threshold_used?: number | null;
  abnormal_area_ratio: number;
  data_mode: string;
  is_mock: boolean;
  created_at: string;
}

export interface PhoneInference {
  record_id: string;
  image_id: string;
  disease_type?: string | null;
  confidence?: number | null;
  severity_level?: string | null;
  risk_level?: string | null;
  result_image_url?: string | null;
}

export interface AbnormalRegion {
  region_id: string;
  uav_task_id: string;
  field_id?: string | null;
  region_name: string;
  region_image_url?: string | null;
  abnormal_type: string;
  abnormal_level: string;
  abnormal_area_ratio: number;
  source_index_type: string;
  confirm_status: string;
  linked_phone_image_id?: string | null;
  linked_record_id?: string | null;
  confirmed_disease_type?: string | null;
  confirm_confidence?: number | null;
  confirm_source?: string | null;
  confirmed_at?: string | null;
  phone_inference?: PhoneInference | null;
  created_at: string;
  updated_at: string;
}

export interface UavDryRunResponse {
  uav_task_id: string;
  field_id?: string | null;
  status: string;
  data_mode: string;
  is_mock: boolean;
  mock_safety_note: string;
  indices: UavIndexResult[];
  abnormal_regions: AbnormalRegion[];
}

export interface AbnormalRegionListResponse {
  items: AbnormalRegion[];
  total: number;
}

export interface DetectionResult {
  type: string;
  record_id: string;
  image_id: string;
  field_id?: string | null;
  plot_id?: string | null;
  source_type: string;
  model_name: string;
  model_stage: string;
  formal_metric_available: boolean;
  fallback_to_mock: boolean;
  uav_task_id?: string | null;
  abnormal_region_id?: string | null;
  result_image_url: string;
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

export interface InspectionReport {
  report_id: string;
  field_id: string;
  uav_task_id?: string | null;
  report_title: string;
  report_date: string;
  summary: string;
  uav_summary: {
    task?: UavTask | null;
    indices?: UavIndexResult[];
    data_mode?: string;
    is_mock?: boolean;
  };
  abnormal_region_summary: {
    total: number;
    items: AbnormalRegion[];
  };
  phone_followup_summary: {
    total: number;
    confirmed_count: number;
    items: AbnormalRegion[];
  };
  risk_summary: {
    risk_level?: string;
    risk_score?: number;
    risk_probability_note?: string;
    main_factors?: string[];
  };
  risk_model_detail?: {
    prediction_id?: string;
    field_id?: string;
    uav_task_id?: string | null;
    abnormal_region_id?: string | null;
    phone_image_id?: string | null;
    disease_type?: string | null;
    total_risk_score?: number;
    risk_level?: string;
    factor_scores?: Record<string, number>;
    main_factors?: string[];
    feature_snapshot_id?: string | null;
    model_type?: string;
    model_stage?: string;
    probability_claim?: boolean;
    experimental_only?: boolean;
    not_for_production?: boolean;
    safety_note?: string;
    created_at?: string;
    status?: string;
    reason?: string;
  };
  rag_suggestion: string;
  model_safety_note: string;
  report_status: string;
  payload: {
    field?: FieldInfo;
    model_boundary?: {
      formal_metric_available: boolean;
      note: string;
      rule_weighted_risk_note?: string;
    };
  };
  created_at: string;
  updated_at: string;
}

export interface InspectionReportListResponse {
  items: InspectionReport[];
  total: number;
}
