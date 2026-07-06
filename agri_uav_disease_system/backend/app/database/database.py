from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from app.core.config import settings


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS detection_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT NOT NULL UNIQUE,
                image_id TEXT NOT NULL,
                plot_id TEXT,
                plot_name TEXT,
                region_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                image_url TEXT NOT NULL,
                result_image_url TEXT NOT NULL,
                image_width INTEGER NOT NULL,
                image_height INTEGER NOT NULL,
                source_type TEXT NOT NULL DEFAULT 'manual_upload',
                model_name TEXT NOT NULL DEFAULT 'mock_disease_detector',
                model_version TEXT NOT NULL DEFAULT 'mock-v1',
                detector_mode TEXT NOT NULL DEFAULT 'mock',
                is_smoke INTEGER NOT NULL DEFAULT 0,
                model_stage TEXT NOT NULL DEFAULT 'mock',
                formal_metric_available INTEGER NOT NULL DEFAULT 0,
                current_target_type TEXT,
                fallback_to_mock INTEGER NOT NULL DEFAULT 0,
                model_hint TEXT,
                target_type TEXT,
                model_display_name TEXT,
                model_warning TEXT,
                model_usage_scope TEXT,
                model_capability_level TEXT,
                lng REAL,
                lat REAL,
                detections_json TEXT NOT NULL,
                severity TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                main_disease TEXT,
                suggestion_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS batch_tasks (
                task_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                status TEXT NOT NULL,
                total_images INTEGER NOT NULL,
                processed_images INTEGER NOT NULL DEFAULT 0,
                failed_images INTEGER NOT NULL DEFAULT 0,
                progress REAL NOT NULL DEFAULT 0,
                record_ids_json TEXT NOT NULL DEFAULT '[]',
                failed_items_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id TEXT PRIMARY KEY,
                plot_id TEXT NOT NULL,
                plot_name TEXT,
                region_name TEXT NOT NULL,
                main_disease TEXT,
                severity TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL,
                suggestion_json TEXT NOT NULL,
                record_ids_json TEXT NOT NULL,
                first_record_id TEXT NOT NULL,
                latest_record_id TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                latest_seen_at TEXT NOT NULL,
                cooldown_until TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_actions (
                action_id TEXT PRIMARY KEY,
                alert_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                operator_id TEXT,
                operator_name TEXT,
                note TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS weather_observations (
                weather_id TEXT PRIMARY KEY,
                plot_id TEXT,
                region_name TEXT,
                observed_date TEXT,
                temperature_max REAL,
                temperature_min REAL,
                humidity_avg REAL,
                rainfall_mm REAL,
                wind_speed REAL,
                sunshine_hours REAL,
                weather_text TEXT,
                data_source TEXT,
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plot_growth_stages (
                growth_id TEXT PRIMARY KEY,
                plot_id TEXT,
                rice_variety TEXT,
                sowing_date TEXT,
                transplanting_date TEXT,
                growth_stage TEXT,
                manual_growth_stage TEXT,
                inferred_growth_stage TEXT,
                updated_at TEXT,
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS farm_operations (
                operation_id TEXT PRIMARY KEY,
                plot_id TEXT,
                operation_type TEXT,
                operation_time TEXT,
                target_disease TEXT,
                material_name TEXT,
                dosage_text TEXT,
                operator_id TEXT,
                operator_name TEXT,
                note TEXT,
                photo_url TEXT,
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS risk_predictions (
                prediction_id TEXT PRIMARY KEY,
                plot_id TEXT,
                prediction_time TEXT,
                prediction_window_days INTEGER,
                predicted_disease TEXT,
                risk_score INTEGER,
                risk_probability REAL,
                risk_level TEXT,
                main_factors_json TEXT,
                suggestion_json TEXT,
                model_type TEXT,
                model_version TEXT,
                input_snapshot_json TEXT,
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS field_info (
                field_id TEXT PRIMARY KEY,
                field_name TEXT NOT NULL,
                location_city TEXT NOT NULL DEFAULT '宿迁市',
                location_district TEXT,
                location_town TEXT,
                location_village TEXT,
                center_lat REAL,
                center_lng REAL,
                area_estimate_mu REAL,
                crop_type TEXT NOT NULL DEFAULT 'rice',
                current_growth_stage TEXT,
                field_status TEXT NOT NULL DEFAULT 'active',
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uav_tasks (
                uav_task_id TEXT PRIMARY KEY,
                field_id TEXT,
                task_name TEXT NOT NULL,
                flight_date TEXT,
                sensor_type TEXT NOT NULL DEFAULT 'multispectral',
                data_mode TEXT NOT NULL DEFAULT 'dry_run',
                growth_stage TEXT,
                weather_text TEXT,
                status TEXT NOT NULL DEFAULT 'created',
                summary TEXT,
                is_mock INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uav_images (
                uav_image_id TEXT PRIMARY KEY,
                uav_task_id TEXT NOT NULL,
                field_id TEXT,
                image_url TEXT NOT NULL,
                image_type TEXT NOT NULL,
                band_type TEXT,
                index_type TEXT,
                capture_time TEXT,
                lat REAL,
                lng REAL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uav_index_results (
                index_result_id TEXT PRIMARY KEY,
                uav_task_id TEXT NOT NULL,
                field_id TEXT,
                index_type TEXT NOT NULL,
                index_image_url TEXT NOT NULL,
                min_value REAL,
                max_value REAL,
                mean_value REAL,
                threshold_used REAL,
                abnormal_area_ratio REAL,
                data_mode TEXT NOT NULL DEFAULT 'dry_run',
                is_mock INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uav_index_analysis (
                analysis_id TEXT PRIMARY KEY,
                uav_task_id TEXT NOT NULL,
                field_id TEXT,
                index_type TEXT NOT NULL,
                mean_value REAL,
                std_value REAL,
                min_value REAL,
                max_value REAL,
                z_threshold REAL,
                abnormal_pixel_ratio REAL,
                abnormal_area_ratio REAL,
                index_anomaly_score INTEGER NOT NULL,
                abnormal_level TEXT NOT NULL,
                data_mode TEXT NOT NULL DEFAULT 'dry_run',
                is_mock INTEGER NOT NULL DEFAULT 1,
                main_reasons_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS abnormal_regions (
                region_id TEXT PRIMARY KEY,
                uav_task_id TEXT NOT NULL,
                field_id TEXT,
                region_name TEXT NOT NULL,
                region_image_url TEXT,
                region_polygon_json TEXT,
                center_lat REAL,
                center_lng REAL,
                abnormal_type TEXT NOT NULL,
                abnormal_level TEXT NOT NULL,
                abnormal_area_ratio REAL,
                source_index_type TEXT NOT NULL,
                confirm_status TEXT NOT NULL DEFAULT 'phone_followup_pending',
                linked_phone_image_id TEXT,
                linked_record_id TEXT,
                confirmed_disease_type TEXT,
                confirm_confidence REAL,
                confirm_source TEXT,
                confirmed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS risk_feature_snapshots (
                feature_id TEXT PRIMARY KEY,
                prediction_id TEXT,
                field_id TEXT NOT NULL,
                uav_task_id TEXT,
                abnormal_region_id TEXT,
                phone_image_id TEXT,
                disease_type TEXT,
                ndvi_mean REAL,
                ndvi_std REAL,
                ndvi_min REAL,
                ndvi_max REAL,
                ndre_mean REAL,
                ndre_std REAL,
                ndre_min REAL,
                ndre_max REAL,
                abnormal_area_ratio REAL,
                uav_risk_score INTEGER NOT NULL DEFAULT 0,
                phone_confidence REAL,
                image_risk_score INTEGER NOT NULL DEFAULT 0,
                severity_level TEXT,
                humidity_avg REAL,
                rainfall_3d REAL,
                rainfall_7d REAL,
                continuous_rain_days INTEGER NOT NULL DEFAULT 0,
                environment_risk_score INTEGER NOT NULL DEFAULT 0,
                growth_stage TEXT,
                growth_stage_risk_score INTEGER NOT NULL DEFAULT 0,
                historical_same_disease INTEGER NOT NULL DEFAULT 0,
                history_risk_score INTEGER NOT NULL DEFAULT 0,
                recent_treatment TEXT,
                treatment_effect TEXT,
                treatment_risk_score INTEGER NOT NULL DEFAULT 0,
                factor_scores_json TEXT NOT NULL DEFAULT '{}',
                main_factors_json TEXT NOT NULL DEFAULT '[]',
                total_risk_score INTEGER NOT NULL DEFAULT 0,
                risk_level TEXT NOT NULL,
                model_type TEXT NOT NULL DEFAULT 'rule_weighted_score',
                model_stage TEXT NOT NULL DEFAULT 'experimental',
                probability_claim INTEGER NOT NULL DEFAULT 0,
                feature_payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inspection_reports (
                report_id TEXT PRIMARY KEY,
                field_id TEXT NOT NULL,
                uav_task_id TEXT,
                report_title TEXT NOT NULL,
                report_date TEXT NOT NULL,
                summary TEXT NOT NULL,
                uav_summary_json TEXT NOT NULL,
                abnormal_region_summary_json TEXT NOT NULL,
                phone_followup_summary_json TEXT NOT NULL,
                risk_summary_json TEXT NOT NULL,
                risk_model_detail_json TEXT NOT NULL DEFAULT '{}',
                rag_suggestion TEXT NOT NULL,
                model_safety_note TEXT NOT NULL,
                report_status TEXT NOT NULL DEFAULT 'generated',
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        _ensure_column(conn, "detection_records", "field_id", "TEXT")
        _ensure_column(conn, "detection_records", "uav_task_id", "TEXT")
        _ensure_column(conn, "detection_records", "abnormal_region_id", "TEXT")
        _ensure_column(conn, "detection_records", "source_type", "TEXT NOT NULL DEFAULT 'manual_upload'")
        _ensure_column(conn, "detection_records", "model_name", "TEXT NOT NULL DEFAULT 'mock_disease_detector'")
        _ensure_column(conn, "detection_records", "model_version", "TEXT NOT NULL DEFAULT 'mock-v1'")
        _ensure_column(conn, "detection_records", "detector_mode", "TEXT NOT NULL DEFAULT 'mock'")
        _ensure_column(conn, "detection_records", "is_smoke", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "detection_records", "model_stage", "TEXT NOT NULL DEFAULT 'mock'")
        _ensure_column(conn, "detection_records", "formal_metric_available", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "detection_records", "current_target_type", "TEXT")
        _ensure_column(conn, "detection_records", "category_type", "TEXT")
        _ensure_column(conn, "detection_records", "fallback_to_mock", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "detection_records", "model_hint", "TEXT")
        _ensure_column(conn, "detection_records", "target_type", "TEXT")
        _ensure_column(conn, "detection_records", "model_display_name", "TEXT")
        _ensure_column(conn, "detection_records", "model_warning", "TEXT")
        _ensure_column(conn, "detection_records", "model_usage_scope", "TEXT")
        _ensure_column(conn, "detection_records", "model_capability_level", "TEXT")
        _ensure_column(conn, "detection_records", "task_type", "TEXT")
        _ensure_column(conn, "detection_records", "result_type", "TEXT")
        _ensure_column(conn, "detection_records", "disease_name", "TEXT")
        _ensure_column(conn, "detection_records", "model_sha256", "TEXT")
        _ensure_column(conn, "detection_records", "input_config", "TEXT")
        _ensure_column(conn, "detection_records", "threshold", "REAL")
        _ensure_column(conn, "detection_records", "min_area", "INTEGER")
        _ensure_column(conn, "detection_records", "disease_area_ratio", "REAL")
        _ensure_column(conn, "detection_records", "mask_url", "TEXT")
        _ensure_column(conn, "detection_records", "overlay_url", "TEXT")
        _ensure_column(conn, "detection_records", "probability_map_url", "TEXT")
        _ensure_column(conn, "detection_records", "production_scope", "TEXT")
        _ensure_column(conn, "detection_records", "human_review_required", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "detection_records", "human_review_status", "TEXT")
        _ensure_column(conn, "detection_records", "human_review_label", "TEXT")
        _ensure_column(conn, "detection_records", "issue_tags_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "detection_records", "reviewer_note", "TEXT")
        _ensure_column(conn, "detection_records", "alerting_enabled", "INTEGER")
        _ensure_column(conn, "detection_records", "latest_alerts_enabled", "INTEGER")
        _ensure_column(conn, "detection_records", "active_model_version", "TEXT")
        _ensure_column(conn, "alerts", "alert_source", "TEXT DEFAULT 'detection'")
        _ensure_column(conn, "alerts", "prediction_id", "TEXT")
        _ensure_column(conn, "alerts", "prediction_window_days", "INTEGER")
        _ensure_column(conn, "risk_predictions", "uav_risk_score", "INTEGER")
        _ensure_column(conn, "risk_predictions", "image_risk_score", "INTEGER")
        _ensure_column(conn, "risk_predictions", "environment_risk_score", "INTEGER")
        _ensure_column(conn, "risk_predictions", "growth_stage_risk_score", "INTEGER")
        _ensure_column(conn, "risk_predictions", "history_risk_score", "INTEGER")
        _ensure_column(conn, "risk_predictions", "treatment_risk_score", "INTEGER")
        _ensure_column(conn, "risk_predictions", "factor_scores_json", "TEXT")
        _ensure_column(conn, "risk_predictions", "probability_claim", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "risk_predictions", "model_stage", "TEXT DEFAULT 'experimental'")
        _ensure_column(conn, "inspection_reports", "risk_model_detail_json", "TEXT NOT NULL DEFAULT '{}'")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_records_plot_id ON detection_records(plot_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_records_risk_level ON detection_records(risk_level)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_records_severity ON detection_records(severity)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_records_created_at ON detection_records(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_batch_tasks_status ON batch_tasks(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_batch_tasks_created_at ON batch_tasks(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_plot_disease_risk ON alerts(plot_id, main_disease, risk_level)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_latest_seen_at ON alerts(latest_seen_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_actions_alert_id ON alert_actions(alert_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_actions_created_at ON alert_actions(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_weather_plot_date ON weather_observations(plot_id, observed_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_growth_plot ON plot_growth_stages(plot_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_operations_plot_time ON farm_operations(plot_id, operation_time)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_predictions_plot_time ON risk_predictions(plot_id, prediction_time)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_predictions_risk_level ON risk_predictions(risk_level)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_source ON alerts(alert_source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_records_field_id ON detection_records(field_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_records_abnormal_region_id ON detection_records(abnormal_region_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fields_status ON field_info(field_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_uav_tasks_field_id ON uav_tasks(field_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_uav_indices_task ON uav_index_results(uav_task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_uav_index_analysis_task ON uav_index_analysis(uav_task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_abnormal_regions_task ON abnormal_regions(uav_task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_abnormal_regions_field ON abnormal_regions(field_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_risk_features_field ON risk_feature_snapshots(field_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_risk_features_prediction ON risk_feature_snapshots(prediction_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_field ON inspection_reports(field_id)")
        conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def check_database() -> str:
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
        return "ok"
    except sqlite3.Error:
        return "error"


def connection_scope() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
