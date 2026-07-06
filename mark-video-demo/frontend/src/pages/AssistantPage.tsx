import { BookOpenText, CheckCircle2, Loader2, Send, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { StatusPill } from "../components/StatusPill";
import { EmptyState, ErrorNotice, InfoRow, PagePanel, SectionHeader } from "../components/ui";
import { api } from "../services/api";
import type { DiagnosisReportResponse, DiseaseListItem } from "../types/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  report?: DiagnosisReportResponse;
}

const safetyText = "回答仅用于病虫害识别辅助复核，不替代农技人员现场诊断，不输出农药处方、剂量或强制性防治方案。";

const quickQuestions = [
  {
    title: "褐斑病复核",
    disease_id: "brown_spot",
    question: "褐斑病轻度发生时，现场复查应该重点看什么？",
    context: "适合手机近景识别后复查"
  },
  {
    title: "白叶枯病片区异常",
    disease_id: "bacterial_leaf_blight",
    question: "白叶枯病为什么可能出现片区化风险？",
    context: "适合 UAV 异常区域解释"
  },
  {
    title: "稻瘟病巡田",
    disease_id: "rice_blast",
    question: "稻瘟病风险偏高时，下一次巡田应该如何安排？",
    context: "适合生成报告前确认"
  }
];

export function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "你好，我是主后端 LLM/RAG 诊断助手。这里调用 /api/agent/diagnosis-report，并展示真实 llm_mode、fallback_used 和证据来源。"
    }
  ]);
  const [diseases, setDiseases] = useState<DiseaseListItem[]>([]);
  const [diseaseId, setDiseaseId] = useState("brown_spot");
  const [input, setInput] = useState(quickQuestions[0].question);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api
      .diseases()
      .then((res) => setDiseases(res.items))
      .catch(() => setDiseases([]));
  }, []);

  async function ask(question = input, selectedDiseaseId = diseaseId) {
    const normalized = question.trim();
    if (!normalized || loading) return;

    setLoading(true);
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: normalized }]);

    try {
      const report = await api.diagnosisReport({
        disease_id: selectedDiseaseId,
        model_class: selectedDiseaseId,
        confidence: 0.82,
        source_type: "frontend_rag_assistant",
        user_question: normalized
      });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: buildReportAnswer(report),
          report
        }
      ]);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "LLM/RAG 诊断报告请求失败，请稍后重试");
    } finally {
      setInput("");
      setLoading(false);
    }
  }

  const latestReport = [...messages].reverse().find((message) => message.report)?.report;

  return (
    <div className="grid grid-cols-[minmax(0,1fr)_380px] gap-5">
      <PagePanel
        className="flex h-[calc(100vh-150px)] flex-col"
        title="LLM/RAG 诊断助手"
        description="调用主后端 Agent 生成诊断解释报告，不再使用旧 demo assistant 接口。"
        status={<StatusPill label="主后端 Agent" tone="cyan" />}
      >
        <div className="rounded-lg border border-amber-300/30 bg-amber-300/10 p-3 text-sm leading-6 text-amber-50/90">
          {safetyText}
        </div>

        <div className="mt-4 flex-1 space-y-4 overflow-auto pr-2">
          {messages.map((message, index) => (
            <div key={`${message.role}-${index}`} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
              <article
                className={`max-w-[78%] rounded-lg border px-4 py-3 text-sm leading-6 ${
                  message.role === "user"
                    ? "border-cyan-300/30 bg-cyan-400/12 text-cyan-50"
                    : "border-slate-700/80 bg-white/[0.04] text-slate-200"
                }`}
              >
                <p className="whitespace-pre-wrap">{message.content}</p>
                {message.report && <ReportMeta report={message.report} />}
              </article>
            </div>
          ))}
          {loading && (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin text-cyan-300" />
              正在调用主后端 LLM/RAG...
            </div>
          )}
        </div>

        {error && <ErrorNotice title="LLM/RAG 不可用" message={error} />}

        <div className="mt-4 grid grid-cols-[220px_minmax(0,1fr)_112px] gap-3">
          <select
            value={diseaseId}
            onChange={(event) => setDiseaseId(event.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-3 text-sm text-slate-100 outline-none focus:border-cyan-300/60"
          >
            {(diseases.length ? diseases : quickQuestions.map((item) => ({ disease_id: item.disease_id, zh_name: item.title, en_name: item.title, authority_level: "A", model_supported: true }))).map((item) => (
              <option key={item.disease_id} value={item.disease_id}>
                {item.zh_name} / {item.disease_id}
              </option>
            ))}
          </select>
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void ask();
            }}
            placeholder="输入需要解释的病害、症状或复查问题"
            className="min-w-0 rounded-lg border border-slate-700 bg-slate-950/60 px-4 py-3 text-sm text-slate-100 outline-none focus:border-cyan-300/60"
          />
          <button onClick={() => void ask()} disabled={loading || !input.trim()} className="primary-button disabled:opacity-50">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            发送
          </button>
        </div>
      </PagePanel>

      <aside className="space-y-5">
        <PagePanel title="场景问题" description="选择问题时会同步 disease_id，便于 RAG 命中知识库。">
          <div className="space-y-3">
            {quickQuestions.map((item) => (
              <button
                key={item.title}
                onClick={() => {
                  setDiseaseId(item.disease_id);
                  void ask(item.question, item.disease_id);
                }}
                disabled={loading}
                className="w-full rounded-lg border border-slate-700/70 bg-white/[0.03] p-4 text-left transition hover:border-cyan-300/35 hover:bg-cyan-400/[0.06] disabled:opacity-60"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 font-medium text-white">
                    <BookOpenText className="h-4 w-4 text-cyan-300" />
                    {item.title}
                  </div>
                  <StatusPill label={item.disease_id} tone="slate" />
                </div>
                <p className="mt-2 text-sm leading-5 text-slate-400">{item.question}</p>
                <div className="mt-3 text-xs text-slate-500">{item.context}</div>
              </button>
            ))}
          </div>
        </PagePanel>

        <PagePanel
          title="LLM 状态"
          description="最近一次主后端 Agent 返回的真实状态。"
          status={latestReport ? <StatusPill label={latestReport.llm_mode} tone={latestReport.fallback_used ? "amber" : "green"} /> : <StatusPill label="等待提问" tone="slate" />}
        >
          {latestReport ? (
            <div className="space-y-1">
              <InfoRow label="llm_mode" value={latestReport.llm_mode} />
              <InfoRow label="provider" value={latestReport.llm_provider || "未返回"} />
              <InfoRow label="model" value={latestReport.llm_model || "未返回"} />
              <InfoRow label="fallback_used" value={latestReport.fallback_used ? "是" : "否"} />
              <InfoRow label="api_error_type" value={latestReport.api_error_type ?? "None"} />
              <InfoRow label="证据来源" value={`${latestReport.evidence_sources.length} 条`} />
            </div>
          ) : (
            <EmptyState description="发送问题后，这里会展示 LLM 调用模式、模型、fallback 和错误类型。" />
          )}
        </PagePanel>

        <section className="panel rounded-lg p-5">
          <SectionHeader title="安全边界" status={<ShieldCheck className="h-5 w-5 text-amber-200" />} />
          <div className="space-y-3 text-sm leading-6 text-slate-300">
            <SafetyItem text="用于解释识别结果和安排复查优先级。" />
            <SafetyItem text="不替代农技人员现场诊断。" />
            <SafetyItem text="不输出农药处方、剂量或强制性治疗方案。" />
          </div>
        </section>
      </aside>
    </div>
  );
}

function buildReportAnswer(report: DiagnosisReportResponse) {
  return [
    `风险等级：${report.risk_level}`,
    "",
    report.model_result_summary,
    "",
    report.knowledge_summary,
    "",
    "复查问题：",
    ...report.manual_check_questions.map((item) => `- ${item}`),
    "",
    "管理建议：",
    ...report.management_suggestions.map((item) => `- ${item}`),
    "",
    "不确定性说明：",
    ...report.uncertainty_notes.map((item) => `- ${item}`)
  ].join("\n");
}

function ReportMeta({ report }: { report: DiagnosisReportResponse }) {
  return (
    <div className="mt-3 border-t border-white/10 pt-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <StatusPill label={`llm_mode: ${report.llm_mode}`} tone={report.fallback_used ? "amber" : "green"} />
        <StatusPill label={`fallback: ${report.fallback_used ? "yes" : "no"}`} tone={report.fallback_used ? "amber" : "cyan"} />
        <StatusPill label={`error: ${report.api_error_type ?? "None"}`} tone={report.api_error_type ? "red" : "slate"} />
      </div>
      {report.evidence_sources.length > 0 && (
        <div className="space-y-1 text-xs text-slate-400">
          {report.evidence_sources.slice(0, 3).map((source) => (
            <div key={source.source_id} className="rounded border border-white/10 bg-slate-950/30 px-2 py-1.5">
              <div className="truncate text-cyan-100">{source.source_title}</div>
              <div className="mt-0.5 text-slate-500">{source.authority_level} · {source.source_type}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SafetyItem({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-slate-700/70 bg-white/[0.03] p-3">
      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-amber-200" />
      <span>{text}</span>
    </div>
  );
}
