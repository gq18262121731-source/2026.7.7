import { EmptyState, RiskLevelBadge, StatusBadge } from "../common";
import type { AbnormalRegion } from "../../types/suqianInspection";

interface AbnormalRegionListProps {
  regions: AbnormalRegion[];
  selectedRegionId?: string | null;
  onSelectRegion: (regionId: string) => void;
}

function confirmLabel(status?: string | null) {
  return status === "phone_confirmed" ? "已复查" : status === "report_written" ? "已回写" : "待复查";
}

export function AbnormalRegionList({ regions, selectedRegionId, onSelectRegion }: AbnormalRegionListProps) {
  if (regions.length === 0) {
    return <EmptyState description="执行 UAV dry-run 后，这里会展示需要复查的异常区域。" />;
  }

  return (
    <div className="space-y-3">
      {regions.map((region) => (
        <button
          key={region.region_id}
          type="button"
          onClick={() => onSelectRegion(region.region_id)}
          className={`w-full rounded-lg border p-3 text-left text-sm transition ${
            selectedRegionId === region.region_id ? "border-cyan-300 bg-cyan-400/10" : "border-slate-700/70 bg-white/[0.03] hover:bg-white/[0.06]"
          }`}
        >
          <div className="flex items-center justify-between gap-3">
            <span className="font-medium text-white">{region.region_name || region.region_id}</span>
            <StatusBadge status={region.confirm_status === "phone_confirmed" ? "stable" : "preview"} label={confirmLabel(region.confirm_status)} />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <RiskLevelBadge level={region.abnormal_level} />
            <StatusBadge status={region.source_index_type ?? "dry-run"} label={region.source_index_type || "dry-run"} />
          </div>
          <div className="mt-3 grid gap-2 text-slate-400 md:grid-cols-2">
            <span>类型：{region.abnormal_type || "暂无数据"}</span>
            <span>面积：{(region.abnormal_area_ratio * 100).toFixed(1)}%</span>
            <span>记录：{region.linked_record_id || "待回写"}</span>
            <span>病害：{region.confirmed_disease_type || "待复查"}</span>
          </div>
        </button>
      ))}
    </div>
  );
}
