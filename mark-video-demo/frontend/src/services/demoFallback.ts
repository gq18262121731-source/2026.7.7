import type { DashboardSummary, DetectionRecord, PlatformModel } from "../types/api";

export const demoDashboardSummary: DashboardSummary = {
  today_detect_count: 6,
  total_record_count: 28,
  disease_record_count: 11,
  normal_record_count: 17,
  high_risk_plot_count: 2,
  medium_risk_plot_count: 4,
  low_risk_plot_count: 8,
  risk_level_counts: { high: 2, medium: 4, low: 8 },
  latest_records: [],
  latest_alerts: []
};

export const demoPlatformModels: PlatformModel[] = [
  {
    key: "phone-demo",
    name: "手机近景识别模型",
    scene_type: "phone_closeup",
    labels: ["稻瘟病", "纹枯病", "白叶枯病"],
    status: "demo_fallback",
    model_stage: "演示兜底"
  },
  {
    key: "uav-demo",
    name: "无人机巡检演示模型",
    scene_type: "uav_multispectral",
    labels: ["长势异常", "疑似病害区"],
    status: "demo_fallback",
    model_stage: "演示分析"
  }
];

export const demoDetectionRecords: DetectionRecord[] = [
  {
    task_id: "demo-suqian-001",
    status: "completed",
    created_at: new Date().toISOString(),
    operator: "demo_user",
    model: demoPlatformModels[0],
    image: {
      sample_key: "demo-leaf-001",
      source_type: "phone_closeup",
      source_name: "宿迁一号田 手机复查样例",
      original_url: "",
      width: 320,
      height: 240
    },
    detections: [],
    summary: {
      top_label: "疑似叶部病害",
      top_confidence: 0.78,
      detection_count: 1,
      process_ms: 0,
      risk_level: "中风险"
    },
    analysis: {
      mode: "demo_fallback",
      title: "演示复查提示",
      text: "当前为演示兜底记录，用于说明巡检闭环路径。实际结论需以后端识别和人工复核为准。",
      prevention: "不输出农事处置方案。"
    },
    processing_status: "演示兜底",
    model_stage: "演示兜底",
    fallback_to_mock: true,
    formal_metric_available: false
  }
];

export async function createDemoRiceLeafImageFile(filename = "rice-leaf-demo.png"): Promise<File> {
  const canvas = document.createElement("canvas");
  canvas.width = 640;
  canvas.height = 420;
  const ctx = canvas.getContext("2d");

  if (ctx) {
    const sky = ctx.createLinearGradient(0, 0, 0, canvas.height);
    sky.addColorStop(0, "#d9f4df");
    sky.addColorStop(1, "#7fb77e");
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = "#173f2a";
    ctx.fillRect(0, 320, canvas.width, 100);

    for (let i = 0; i < 18; i += 1) {
      const x = 24 + i * 36;
      ctx.strokeStyle = i % 3 === 0 ? "#f4ca55" : "#2e7d46";
      ctx.lineWidth = 10;
      ctx.beginPath();
      ctx.moveTo(x, 390);
      ctx.quadraticCurveTo(x + 20, 240 - (i % 5) * 18, x + 80, 72 + (i % 4) * 24);
      ctx.stroke();
    }

    ctx.fillStyle = "rgba(244, 202, 85, 0.84)";
    ctx.beginPath();
    ctx.ellipse(330, 165, 58, 28, -0.55, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(105, 62, 28, 0.58)";
    ctx.beginPath();
    ctx.ellipse(348, 164, 16, 9, -0.55, 0, Math.PI * 2);
    ctx.fill();
  }

  const blob = await new Promise<Blob>((resolve) => {
    canvas.toBlob((value) => resolve(value ?? new Blob()), "image/png");
  });
  return new File([blob], filename, { type: "image/png" });
}
