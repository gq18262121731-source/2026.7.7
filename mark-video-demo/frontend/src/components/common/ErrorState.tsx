import type { ReactNode } from "react";

import { AlertTriangle } from "lucide-react";

interface ErrorStateProps {
  title?: string;
  message: string;
  action?: ReactNode;
  onRetry?: () => void;
}

function friendlyMessage(message: string) {
  const lower = message.toLowerCase();
  if (lower.includes("storage_status") || lower.includes("static_original") || lower.includes("static_result") || lower.includes("storage")) {
    return "存储状态异常，请检查后端静态资源目录或上传目录配置。该问题可能影响图片上传和结果图生成，但不代表模型推理能力失败。";
  }
  if (lower.includes("failed to fetch") || lower.includes("无法连接") || lower.includes("network")) {
    return "无法连接主后端，请确认后端服务已启动且前端 API 地址配置正确。";
  }
  return message;
}

export function ErrorState({ title = "操作失败", message, action, onRetry }: ErrorStateProps) {
  return (
    <div className="rounded-lg border border-red-400/30 bg-red-400/10 p-4 text-sm text-red-100">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-200" />
        <div className="min-w-0">
          <div className="font-semibold">{title}</div>
          <p className="mt-1 leading-6 text-red-100/85">{friendlyMessage(message)}</p>
          {(action || onRetry) && (
            <div className="mt-3">
              {action ?? (
                <button type="button" className="secondary-button py-2" onClick={onRetry}>
                  重试
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
