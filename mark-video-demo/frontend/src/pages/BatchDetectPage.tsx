import { Images, Loader2, Play, RefreshCw } from "lucide-react";
import { useState } from "react";

import { StatusPill } from "../components/StatusPill";
import { EmptyState, ErrorNotice, InfoRow, PagePanel } from "../components/ui";
import { api } from "../services/api";
import type { BatchTaskStatus } from "../types/api";

export function BatchDetectPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [task, setTask] = useState<BatchTaskStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function createTask() {
    if (files.length === 0) {
      setError("请先选择多张图片。");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const created = await api.batchDetect(files);
      setTask(created);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "批量检测任务创建失败");
    } finally {
      setLoading(false);
    }
  }

  async function refreshTask() {
    if (!task) return;
    setLoading(true);
    setError(null);
    try {
      setTask(await api.batchTask(task.task_id));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "批量任务状态刷新失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid grid-cols-[360px_minmax(0,1fr)] gap-5">
      <PagePanel
        title="批量检测输入"
        description="调用主后端 /api/detect/batch 创建真实后台任务。"
        status={<StatusPill label="真实任务接口" tone="cyan" />}
      >
        <label className="block rounded-lg border border-dashed border-slate-700 bg-slate-950/40 p-5 text-sm text-slate-300">
          <input
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
          />
          <div className="flex items-center gap-3">
            <Images className="h-5 w-5 text-cyan-300" />
            <div>
              <div className="font-medium text-white">{files.length ? `已选择 ${files.length} 张图片` : "选择批量检测图片"}</div>
              <div className="mt-1 text-xs text-slate-500">任务创建后可刷新查看 processed / failed / progress。</div>
            </div>
          </div>
        </label>

        <div className="mt-4 max-h-64 space-y-2 overflow-auto">
          {files.map((file) => (
            <div key={`${file.name}-${file.size}`} className="rounded border border-slate-700/70 bg-white/[0.03] px-3 py-2 text-sm text-slate-300">
              {file.name}
            </div>
          ))}
          {files.length === 0 && <EmptyState description="请选择两张或更多图片来展示批量任务能力。" />}
        </div>

        <button onClick={createTask} disabled={loading || files.length === 0} className="primary-button mt-5 w-full disabled:opacity-50">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
          创建批量任务
        </button>
        {error && (
          <div className="mt-4">
            <ErrorNotice title="批量检测错误" message={error} />
          </div>
        )}
      </PagePanel>

      <PagePanel
        title="批量任务状态"
        description="查询 /api/tasks/{task_id}，展示任务进度和识别记录 ID。"
        status={<StatusPill label={task?.status ?? "未创建"} tone={task?.status === "completed" ? "green" : "amber"} />}
        action={
          <button onClick={refreshTask} disabled={loading || !task} className="secondary-button disabled:opacity-50">
            <RefreshCw className="h-4 w-4" />
            刷新状态
          </button>
        }
      >
        {task ? (
          <div className="space-y-5">
            <div className="surface rounded-lg p-4">
              <InfoRow label="task_id" value={task.task_id} />
              <InfoRow label="task_type" value={task.task_type} />
              <InfoRow label="status" value={task.status} />
              <InfoRow label="created_at" value={task.created_at} />
              <InfoRow label="updated_at" value={task.updated_at} />
            </div>
            <div className="grid grid-cols-4 gap-3">
              <TaskStat label="总图片" value={task.total_images} />
              <TaskStat label="已处理" value={task.processed_images} />
              <TaskStat label="失败" value={task.failed_images} />
              <TaskStat label="进度" value={`${(task.progress * 100).toFixed(0)}%`} />
            </div>
            <div>
              <div className="mb-2 text-sm font-medium text-white">生成记录</div>
              <div className="space-y-2">
                {task.record_ids.map((recordId) => (
                  <div key={recordId} className="rounded border border-slate-700/70 bg-white/[0.03] px-3 py-2 text-sm text-slate-300">
                    {recordId}
                  </div>
                ))}
                {task.record_ids.length === 0 && <EmptyState description="任务完成后会显示识别记录 ID。" />}
              </div>
            </div>
          </div>
        ) : (
          <EmptyState description="创建批量检测任务后，这里会展示后台进度。" />
        )}
      </PagePanel>
    </div>
  );
}

function TaskStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="surface rounded-lg p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
    </div>
  );
}
