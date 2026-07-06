import { EmptyState, RiskLevelBadge, StatusBadge } from "../common";
import { InfoRow } from "../ui";
import type { AbnormalRegion } from "../../types/suqianInspection";

interface AbnormalRegionDetailProps {
  region: AbnormalRegion | null;
}

export function AbnormalRegionDetail({ region }: AbnormalRegionDetailProps) {
  if (!region) {
    return <EmptyState description="选择一个 UAV 异常区域后，这里会展示风险、复查和回写字段。" />;
  }

  return (
    <div className="rounded-lg border border-slate-700/70 bg-white/[0.03] p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="text-sm text-slate-500">当前异常区域</div>
          <div className="mt-1 font-semibold text-white">{region.region_name || region.region_id}</div>
        </div>
        <RiskLevelBadge level={region.abnormal_level} />
      </div>
      <div className="mb-3 flex flex-wrap gap-2">
        <StatusBadge status={region.source_index_type || "dry-run"} label={region.source_index_type || "dry-run"} />
        <StatusBadge status={region.confirm_status === "phone_confirmed" ? "stable" : "preview"} label={region.confirm_status === "phone_confirmed" ? "已复查" : "待复查"} />
      </div>
      <InfoRow label="区域编号" value={region.region_id} />
      <InfoRow label="异常类型" value={region.abnormal_type} />
      <InfoRow label="异常面积" value={`${(region.abnormal_area_ratio * 100).toFixed(1)}%`} />
      <InfoRow label="linked_phone_image_id" value={region.linked_phone_image_id} />
      <InfoRow label="linked_record_id" value={region.linked_record_id} />
      <InfoRow label="confirmed_disease_type" value={region.confirmed_disease_type} />
      <InfoRow label="confirm_status" value={region.confirm_status} />
    </div>
  );
}
