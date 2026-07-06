import { Activity, AlertTriangle, MapPinned, TrendingUp } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { MetricCard } from "../components/MetricCard";
import { StatusPill } from "../components/StatusPill";
import { EmptyState, ErrorNotice, InfoRow, PagePanel } from "../components/ui";
import { api } from "../services/api";
import type { PredictionRiskMap, PredictionSummary, RiskPrediction } from "../types/api";

const windows = [3, 7, 14];

export function PredictionPage() {
  const [summary, setSummary] = useState<PredictionSummary | null>(null);
  const [riskMap, setRiskMap] = useState<PredictionRiskMap | null>(null);
  const [selectedPlotId, setSelectedPlotId] = useState("");
  const [predictions, setPredictions] = useState<RiskPrediction[]>([]);
  const [loading, setLoading] = useState(true);
  const [predicting, setPredicting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([api.predictionSummary(), api.predictionRiskMap()])
      .then(([summaryRes, mapRes]) => {
        setSummary(summaryRes);
        setRiskMap(mapRes);
        setSelectedPlotId(mapRes.points[0]?.plot_id ?? "");
      })
      .catch((exc) => setError(exc instanceof Error ? exc.message : "风险预测数据加载失败"))
      .finally(() => setLoading(false));
  }, []);

  async function runPrediction(plotId = selectedPlotId) {
    if (!plotId) {
      setError("请先选择一个地块。");
      return;
    }
    setPredicting(true);
    setError(null);
    try {
      const results = await Promise.all(windows.map((windowDays) => api.predictPlot(plotId, windowDays)));
      setPredictions(results);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "风险预测请求失败");
    } finally {
      setPredicting(false);
    }
  }

  const selectedPoint = useMemo(() => riskMap?.points.find((point) => point.plot_id === selectedPlotId), [riskMap, selectedPlotId]);

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-amber-300/30 bg-amber-300/10 p-4 text-sm leading-6 text-amber-50/90">
        当前为规则风险评分，不是正式发病概率预测；页面展示“综合风险评分”和风险等级，不展示“发病概率”。
      </section>

      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="高风险地块" value={`${summary?.high_risk_plot_count ?? 0}`} detail="来自 /api/prediction/dashboard/summary" icon={AlertTriangle} />
        <MetricCard label="中风险地块" value={`${summary?.medium_risk_plot_count ?? 0}`} detail="规则评分结果" icon={Activity} />
        <MetricCard label="风险点位" value={`${riskMap?.total ?? 0}`} detail="来自 /api/prediction/risk-map" icon={MapPinned} />
        <MetricCard label="预测窗口" value="3 / 7 / 14" detail="按窗口调用真实接口" icon={TrendingUp} />
      </div>

      <div className="grid grid-cols-[360px_minmax(0,1fr)] gap-5">
        <PagePanel
          title="地块选择"
          description="选择风险地图中的地块后，可生成 3/7/14 天规则评分。"
          action={
            <button onClick={() => void runPrediction()} disabled={predicting || !selectedPlotId} className="primary-button disabled:opacity-50">
              生成风险评分
            </button>
          }
        >
          <div className="space-y-3">
            {(riskMap?.points ?? []).map((point) => (
              <button
                key={point.plot_id}
                onClick={() => setSelectedPlotId(point.plot_id)}
                className={`w-full rounded-lg border p-3 text-left transition ${
                  selectedPlotId === point.plot_id ? "border-cyan-300 bg-cyan-400/10" : "border-slate-700/70 bg-white/[0.03] hover:bg-white/[0.06]"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium text-white">{point.plot_name ?? point.plot_id}</span>
                  <StatusPill label={point.predicted_risk_level} tone={point.predicted_risk_level === "high" ? "amber" : "cyan"} />
                </div>
                <div className="mt-2 text-sm text-slate-400">综合风险评分 {point.risk_score}</div>
                <div className="mt-1 text-xs text-slate-500">{point.predicted_disease ?? "未标注主要风险"}</div>
              </button>
            ))}
            {!loading && (riskMap?.points.length ?? 0) === 0 && <EmptyState description="暂无风险地图点位。" />}
          </div>
          {selectedPoint && (
            <div className="mt-4 surface rounded-lg p-3">
              <InfoRow label="plot_id" value={selectedPoint.plot_id} />
              <InfoRow label="经纬度" value={`${selectedPoint.lng ?? "无"}, ${selectedPoint.lat ?? "无"}`} />
              <InfoRow label="风险强度" value={selectedPoint.intensity.toFixed(2)} />
            </div>
          )}
          {error && (
            <div className="mt-3">
              <ErrorNotice title="风险预测错误" message={error} />
            </div>
          )}
        </PagePanel>

        <PagePanel title="规则风险评分" description="分别调用 /api/prediction/plots/{plot_id}，save=true 且 create_alert=true。">
          {predictions.length > 0 ? (
            <div className="grid grid-cols-3 gap-4">
              {predictions.map((prediction) => (
                <div key={`${prediction.plot_id}-${prediction.prediction_window_days}`} className="surface rounded-lg p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-lg font-semibold text-white">{prediction.prediction_window_days} 天</div>
                    <StatusPill label={prediction.risk_level} tone={prediction.risk_level === "high" ? "amber" : "cyan"} />
                  </div>
                  <div className="mt-4 text-3xl font-semibold text-white">{prediction.risk_score}</div>
                  <div className="mt-1 text-sm text-slate-500">综合风险评分</div>
                  <div className="mt-4 space-y-2 text-sm text-slate-300">
                    {prediction.main_factors.map((factor) => (
                      <div key={factor} className="rounded border border-slate-700/70 bg-slate-950/30 p-2">
                        {factor}
                      </div>
                    ))}
                  </div>
                  <p className="mt-4 text-sm leading-6 text-slate-300">{prediction.suggestion.content}</p>
                  <p className="mt-3 text-xs leading-5 text-amber-100/90">{prediction.risk_probability_note}</p>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState description="选择地块并点击生成风险评分后，这里会展示 3/7/14 天规则评分。" />
          )}
        </PagePanel>
      </div>
    </div>
  );
}
