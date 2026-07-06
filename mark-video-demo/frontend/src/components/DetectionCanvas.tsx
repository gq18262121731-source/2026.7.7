import type { DetectionRecord } from "../types/api";

interface DetectionCanvasProps {
  record: DetectionRecord | null;
}

export function DetectionCanvas({ record }: DetectionCanvasProps) {
  if (!record) {
    return (
      <div className="flex aspect-[4/3] items-center justify-center rounded-lg border border-dashed border-slate-600 bg-slate-950/50 text-slate-400">
        选择图像来源并开始分析后，识别图像与检测框会显示在这里
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden rounded-lg border border-green-300/20 bg-slate-950">
      <img className="block w-full" src={record.image.original_url} alt={record.image.source_name} />
      {record.detections.map((item) => (
        <div
          key={item.id}
          className="absolute border-2 border-lime-300 bg-lime-300/10 shadow-glow"
          style={{
            left: `${item.bbox_norm.x * 100}%`,
            top: `${item.bbox_norm.y * 100}%`,
            width: `${item.bbox_norm.w * 100}%`,
            height: `${item.bbox_norm.h * 100}%`
          }}
        >
          <span className="absolute -top-7 left-0 rounded bg-lime-300 px-2 py-1 text-xs font-semibold text-slate-950">
            {item.label} {(item.confidence * 100).toFixed(0)}%
          </span>
        </div>
      ))}
    </div>
  );
}

