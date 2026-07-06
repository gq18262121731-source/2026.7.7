from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.schemas.agent_schema import LLMReportSchema


PROMPT_VERSION = "kg_rag_agent_prompt_v1"

SYSTEM_PROMPT = """你是水稻病虫害识别系统中的知识解释助手。

你只能基于用户提供的以下材料生成辅助诊断解释：
1. 图像模型识别结果字段
2. 结构化病害知识 disease_profile
3. 知识图谱摘要 kg_summary
4. RAG 检索证据 rag_evidence
5. 系统响应安全规则 response_policy

你不得编造未提供的事实。
你不得把模型识别结果说成最终诊断。
你不得输出具体农药剂量、浓度、配比或强制施药方案。
你必须说明本结果仅作辅助判断，不替代农业专家现场诊断。
你必须说明具体药剂、浓度和施用时间应以当地农业技术部门建议和产品标签为准。
如果证据不足，请返回 insufficient_evidence=true。
输出必须是严格 JSON，不要输出 Markdown，不要输出解释性前后缀。
"""

REQUIRED_REPORT_FIELDS = {
    "suspected_disease",
    "model_result_summary",
    "knowledge_summary",
    "risk_level",
    "manual_check_questions",
    "management_suggestions",
    "uncertainty_notes",
    "evidence_sources",
    "insufficient_evidence",
}

REPORT_SCHEMA_FIELDS = sorted(
    REQUIRED_REPORT_FIELDS
    | {
        "llm_mode",
        "llm_provider",
        "llm_model",
        "prompt_version",
        "fallback_used",
        "fallback_level",
        "api_error_type",
        "repair_attempted",
        "schema_valid",
        "safety_passed",
    }
)

ALLOWED_RISK_LEVELS = {"low", "medium", "high", "unknown"}

REPAIR_SYSTEM_PROMPT = """You repair a rice disease auxiliary diagnosis JSON report.
Return only one valid JSON object. Do not return Markdown.
Use only the provided previous output and source context.
Do not add evidence beyond the provided disease profile, KG summary, and RAG evidence.
Do not provide pesticide dosage, concentration, ratio, or mandatory treatment instructions.
The output must match the target schema exactly enough for validation."""

FREE_QA_SYSTEM_PROMPT = """You are an auxiliary inspection Q&A agent for a rice disease UAV inspection system.
Answer the user's free question using only the provided inspection_context, disease_profile, kg_summary, and rag_evidence.
If context is missing, explicitly state which information is missing.
If RAG evidence is insufficient, say the local knowledge base evidence is insufficient.
Do not claim automatic diagnosis, do not guarantee accuracy, do not give pesticide prescriptions, and do not replace field inspection or agricultural experts.
Return only strict JSON with: answer, basis, uncertainty, next_steps, safety_notice."""

FREE_QA_REQUIRED_FIELDS = {"answer", "basis", "uncertainty", "next_steps", "safety_notice"}

REQUIRED_UNCERTAINTY_NOTES = [
    "当前结果仅作辅助判断，不替代农业专家现场诊断。",
    "当前模块处于 experimental 阶段，不应作为正式生产诊断依据。",
    "具体药剂、浓度和施用时间应以当地农业技术部门建议和产品标签为准。",
]

DOSAGE_PATTERN = re.compile(
    r"\d+(\.\d+)?\s*(毫升|mL|ml|升|L|克|g|千克|kg|斤|倍液|%|ppm|亩|公顷|小时|天)|"
    r"(每亩|每公顷|配比|浓度|兑水|稀释)"
)


@dataclass(frozen=True)
class LLMSettings:
    mode: str
    provider: str
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float
    max_tokens: int
    temperature: float
    enable_json_response_format: bool
    enable_mock_fallback: bool
    prompt_version: str


class LLMClientError(RuntimeError):
    def __init__(
        self,
        error_type: str,
        message: str,
        repair_attempted: bool = False,
        schema_valid: bool = False,
        safety_passed: bool = True,
    ) -> None:
        self.error_type = error_type
        self.repair_attempted = repair_attempted
        self.schema_valid = schema_valid
        self.safety_passed = safety_passed
        super().__init__(message)


def _env_bool(name: str, default: str = "false") -> bool:
    return _getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _dotenv_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def _load_dotenv_values() -> dict[str, str]:
    path = _dotenv_path()
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        value = value.strip().strip('"').strip("'")
        values[key.strip()] = value
    return values


def _getenv(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value not in {None, ""}:
        return value
    return _load_dotenv_values().get(name, default)


def load_llm_settings() -> LLMSettings:
    return LLMSettings(
        mode=_getenv("LLM_MODE", "api").strip().lower(),
        provider=_getenv("LLM_PROVIDER", "custom_openai_compatible").strip() or "custom_openai_compatible",
        api_key=_getenv("LLM_API_KEY", "").strip(),
        base_url=_getenv("LLM_BASE_URL", "https://api.deepseek.com").strip().rstrip("/"),
        model=_getenv("LLM_MODEL", "deepseek-v4-flash").strip(),
        timeout_seconds=float(_getenv("LLM_TIMEOUT_SECONDS", "30") or 30),
        max_tokens=int(_getenv("LLM_MAX_TOKENS", "1200") or 1200),
        temperature=float(_getenv("LLM_TEMPERATURE", "0.2") or 0.2),
        enable_json_response_format=_env_bool("LLM_ENABLE_JSON_RESPONSE_FORMAT", "true"),
        enable_mock_fallback=_env_bool("LLM_ENABLE_MOCK_FALLBACK", "true"),
        prompt_version=_getenv("LLM_PROMPT_VERSION", PROMPT_VERSION).strip() or PROMPT_VERSION,
    )


def build_diagnosis_prompt_context(
    disease: dict[str, Any],
    kg_summary: dict[str, Any],
    rag_chunks: list[dict[str, Any]],
    model_class: str | None,
    confidence: float | None,
    source_type: str | None,
    user_question: str | None = None,
) -> tuple[str, dict[str, Any]]:
    disease_id = disease.get("disease_id", "")
    rag_evidence = [
        {
            "chunk_id": item.get("chunk_id"),
            "source_id": item.get("source_id"),
            "source_title": item.get("source_title"),
            "authority_level": item.get("authority_level"),
            "section_type": item.get("section_type"),
            "text": item.get("text"),
            "score": item.get("score"),
        }
        for item in rag_chunks
    ]
    user_context = {
        "model_result": {
            "disease_id": disease_id,
            "model_class": model_class or "",
            "confidence": confidence,
            "source_type": source_type or "",
            "is_mock_or_smoke_or_experimental": True,
        },
        "disease_profile": disease,
        "kg_summary": kg_summary,
        "rag_evidence": rag_evidence,
        "response_policy": {
            "not_final_diagnosis": True,
            "no_pesticide_dosage": True,
            "must_include_uncertainty_notes": True,
            "must_include_evidence_sources": True,
            "tungro_extra_warning": disease_id == "tungro",
        },
        "user_question": user_question or "请根据当前识别结果生成辅助诊断解释。",
        "required_output_schema": {
            "suspected_disease": {"disease_id": "", "zh_name": "", "en_name": ""},
            "model_result_summary": "",
            "knowledge_summary": "",
            "risk_level": "low|medium|high|unknown",
            "manual_check_questions": [],
            "management_suggestions": [],
            "uncertainty_notes": [],
            "evidence_sources": [],
            "insufficient_evidence": False,
            "llm_mode": "api",
            "llm_provider": "",
            "llm_model": "",
            "prompt_version": PROMPT_VERSION,
            "fallback_used": False,
        },
    }
    return SYSTEM_PROMPT, user_context


class MockLLMClient:
    def generate_report(
        self,
        disease: dict[str, Any],
        kg_summary: dict[str, Any],
        rag_chunks: list[dict[str, Any]],
        model_class: str | None,
        confidence: float | None,
        source_type: str | None,
        user_question: str | None = None,
    ) -> dict[str, Any]:
        settings = load_llm_settings()
        if settings.mode == "api":
            try:
                return self._generate_api_report(
                    settings,
                    disease,
                    kg_summary,
                    rag_chunks,
                    model_class,
                    confidence,
                    source_type,
                    user_question,
                )
            except LLMClientError as exc:
                if not settings.enable_mock_fallback:
                    raise
                report = self._generate_mock_report(
                    disease,
                    kg_summary,
                    model_class,
                    confidence,
                    source_type,
                    fallback_used=True,
                    fallback_level="mock_template",
                    api_error_type=exc.error_type,
                    repair_attempted=exc.repair_attempted,
                    schema_valid=True,
                    safety_passed=exc.safety_passed,
                    settings=settings,
                )
                return report

        return self._generate_mock_report(disease, kg_summary, model_class, confidence, source_type, settings=settings)

    def generate_free_qa(
        self,
        question: str,
        context: dict[str, Any],
        disease: dict[str, Any] | None,
        kg_summary: dict[str, Any],
        rag_chunks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        settings = load_llm_settings()
        if settings.mode == "api":
            try:
                return self._generate_api_free_qa(settings, question, context, disease, kg_summary, rag_chunks)
            except LLMClientError as exc:
                if not settings.enable_mock_fallback:
                    raise
                return self._generate_free_qa_fallback(
                    question=question,
                    context=context,
                    disease=disease,
                    kg_summary=kg_summary,
                    rag_chunks=rag_chunks,
                    settings=settings,
                    api_error_type=exc.error_type,
                )
        return self._generate_free_qa_fallback(
            question=question,
            context=context,
            disease=disease,
            kg_summary=kg_summary,
            rag_chunks=rag_chunks,
            settings=settings,
            api_error_type=None,
        )

    def _generate_api_free_qa(
        self,
        settings: LLMSettings,
        question: str,
        context: dict[str, Any],
        disease: dict[str, Any] | None,
        kg_summary: dict[str, Any],
        rag_chunks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self._validate_api_settings(settings)
        prompt_context = self._build_free_qa_context(question, context, disease, kg_summary, rag_chunks)
        payload = {
            "model": settings.model,
            "messages": [
                {"role": "system", "content": FREE_QA_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(prompt_context, ensure_ascii=False)},
            ],
            "temperature": settings.temperature,
            "max_tokens": settings.max_tokens,
        }
        if settings.enable_json_response_format:
            payload["response_format"] = {"type": "json_object"}
        response = self._post_chat_completion(settings, payload)
        parsed = self._parse_json_content(self._extract_message_content(response))
        repair_attempted = False
        try:
            self._validate_free_qa_json(parsed)
        except LLMClientError as exc:
            repair_attempted = True
            parsed = self._repair_free_qa_json(settings, prompt_context, parsed, str(exc))
            self._validate_free_qa_json(parsed)
        return self._postprocess_free_qa(
            parsed=parsed,
            question=question,
            context=context,
            disease=disease,
            kg_summary=kg_summary,
            rag_chunks=rag_chunks,
            settings=settings,
            fallback_used=False,
            fallback_level="none",
            api_error_type=None,
            repair_attempted=repair_attempted,
        )

    def _generate_api_report(
        self,
        settings: LLMSettings,
        disease: dict[str, Any],
        kg_summary: dict[str, Any],
        rag_chunks: list[dict[str, Any]],
        model_class: str | None,
        confidence: float | None,
        source_type: str | None,
        user_question: str | None = None,
    ) -> dict[str, Any]:
        self._validate_api_settings(settings)
        system_prompt, user_context = build_diagnosis_prompt_context(
            disease,
            kg_summary,
            rag_chunks,
            model_class,
            confidence,
            source_type,
            user_question,
        )
        payload = {
            "model": settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_context, ensure_ascii=False)},
            ],
            "temperature": settings.temperature,
            "max_tokens": settings.max_tokens,
        }
        if settings.enable_json_response_format:
            payload["response_format"] = {"type": "json_object"}
        response = self._post_chat_completion(settings, payload)
        content = self._extract_message_content(response)
        parsed = self._parse_json_content(content)
        repair_attempted = False
        try:
            self._validate_raw_llm_report(parsed)
        except LLMClientError as exc:
            repair_attempted = True
            try:
                parsed = self._repair_report_json(
                    settings=settings,
                    user_context=user_context,
                    previous_output=parsed,
                    validation_error=str(exc),
                )
                self._validate_raw_llm_report(parsed)
            except LLMClientError as repair_exc:
                raise LLMClientError(
                    "schema_validation_error",
                    str(repair_exc),
                    repair_attempted=True,
                    schema_valid=False,
                ) from repair_exc
        base_report = self._generate_mock_report(disease, kg_summary, model_class, confidence, source_type, settings=settings)
        return self._postprocess_report(
            parsed,
            base_report,
            disease,
            kg_summary,
            settings=settings,
            llm_mode="api",
            fallback_used=False,
            fallback_level="none",
            api_error_type=None,
            repair_attempted=repair_attempted,
        )

    def _validate_api_settings(self, settings: LLMSettings) -> None:
        if not settings.api_key:
            raise LLMClientError("missing_api_key", "LLM_API_KEY is required when LLM_MODE=api.")
        if not settings.base_url:
            raise LLMClientError("missing_base_url", "LLM_BASE_URL is required when LLM_MODE=api.")
        if not settings.model:
            raise LLMClientError("missing_model", "LLM_MODEL is required when LLM_MODE=api.")

    def _post_chat_completion(self, settings: LLMSettings, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = f"{settings.base_url}/chat/completions"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=settings.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise LLMClientError("auth_error", "LLM API authentication failed.") from exc
            raise LLMClientError("http_error", f"LLM API returned HTTP {exc.code}.") from exc
        except TimeoutError as exc:
            raise LLMClientError("timeout", "LLM API request timed out.") from exc
        except urllib.error.URLError as exc:
            raise LLMClientError("network_error", "LLM API network error.") from exc
        except json.JSONDecodeError as exc:
            raise LLMClientError("invalid_api_response", "LLM API response is not valid JSON.") from exc

    def _extract_message_content(self, response: dict[str, Any]) -> str:
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError("invalid_api_response", "LLM API response missing choices[0].message.content.") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMClientError("invalid_api_response", "LLM API content is empty.")
        return content.strip()

    def _parse_json_content(self, content: str) -> dict[str, Any]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            parsed = self._extract_embedded_json_object(cleaned)
            if parsed is None:
                raise LLMClientError("invalid_llm_json", "LLM output is not strict JSON.") from exc
        if not isinstance(parsed, dict):
            raise LLMClientError("invalid_llm_json", "LLM output JSON must be an object.")
        return parsed

    def _extract_embedded_json_object(self, content: str) -> dict[str, Any] | None:
        decoder = json.JSONDecoder()
        for match in re.finditer(r"\{", content):
            try:
                parsed, _ = decoder.raw_decode(content[match.start() :])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    def _validate_raw_llm_report(self, parsed: dict[str, Any]) -> None:
        missing = sorted(field for field in REQUIRED_REPORT_FIELDS if field not in parsed)
        if missing:
            raise LLMClientError("schema_validation_error", f"LLM output missing fields: {', '.join(missing)}")
        risk_level = parsed.get("risk_level")
        if risk_level not in ALLOWED_RISK_LEVELS:
            raise LLMClientError("schema_validation_error", f"Invalid risk_level: {risk_level}")

    def _repair_report_json(
        self,
        settings: LLMSettings,
        user_context: dict[str, Any],
        previous_output: dict[str, Any],
        validation_error: str,
    ) -> dict[str, Any]:
        repair_payload = {
            "model": settings.model,
            "messages": [
                {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "validation_error": validation_error,
                            "target_schema_fields": REPORT_SCHEMA_FIELDS,
                            "risk_level_allowed_values": sorted(ALLOWED_RISK_LEVELS),
                            "previous_output": previous_output,
                            "source_context": user_context,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0,
            "max_tokens": settings.max_tokens,
        }
        if settings.enable_json_response_format:
            repair_payload["response_format"] = {"type": "json_object"}
        response = self._post_chat_completion(settings, repair_payload)
        content = self._extract_message_content(response)
        return self._parse_json_content(content)

    def _build_free_qa_context(
        self,
        question: str,
        context: dict[str, Any],
        disease: dict[str, Any] | None,
        kg_summary: dict[str, Any],
        rag_chunks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "mode": "free_qa",
            "question": question,
            "inspection_context": context,
            "disease_profile": disease or {},
            "kg_summary": kg_summary,
            "rag_evidence": self._retrieved_knowledge(rag_chunks, include_text=True),
            "response_policy": {
                "not_final_diagnosis": True,
                "no_accuracy_guarantee": True,
                "no_pesticide_prescription": True,
                "must_include_manual_review": True,
                "must_state_missing_context": True,
                "must_state_insufficient_knowledge_when_no_rag": not bool(rag_chunks),
            },
        }

    def _validate_free_qa_json(self, parsed: dict[str, Any]) -> None:
        missing = sorted(field for field in FREE_QA_REQUIRED_FIELDS if field not in parsed)
        if missing:
            raise LLMClientError("free_qa_schema_error", f"Free QA output missing fields: {', '.join(missing)}")
        for key in ("basis", "uncertainty", "next_steps"):
            if not isinstance(parsed.get(key), (list, str)):
                raise LLMClientError("free_qa_schema_error", f"Free QA field must be a list or string: {key}")

    def _repair_free_qa_json(
        self,
        settings: LLMSettings,
        prompt_context: dict[str, Any],
        previous_output: dict[str, Any],
        validation_error: str,
    ) -> dict[str, Any]:
        payload = {
            "model": settings.model,
            "messages": [
                {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "validation_error": validation_error,
                            "target_schema_fields": sorted(FREE_QA_REQUIRED_FIELDS),
                            "previous_output": previous_output,
                            "source_context": prompt_context,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0,
            "max_tokens": settings.max_tokens,
        }
        if settings.enable_json_response_format:
            payload["response_format"] = {"type": "json_object"}
        response = self._post_chat_completion(settings, payload)
        return self._parse_json_content(self._extract_message_content(response))

    def _postprocess_free_qa(
        self,
        parsed: dict[str, Any],
        question: str,
        context: dict[str, Any],
        disease: dict[str, Any] | None,
        kg_summary: dict[str, Any],
        rag_chunks: list[dict[str, Any]],
        settings: LLMSettings,
        fallback_used: bool,
        fallback_level: str,
        api_error_type: str | None,
        repair_attempted: bool,
    ) -> dict[str, Any]:
        answer = self._sanitize_text(parsed.get("answer", ""))
        basis = [self._sanitize_text(item) for item in self._safe_list(parsed.get("basis"))]
        uncertainty = [self._sanitize_text(item) for item in self._safe_list(parsed.get("uncertainty"))]
        next_steps = [self._sanitize_text(item) for item in self._safe_list(parsed.get("next_steps"))]
        safety_notice = self._sanitize_text(
            parsed.get("safety_notice")
            or "该回答用于巡检辅助，不作为正式农艺诊断或用药处方，需人工复核。"
        )
        missing = context.get("missing_context") or []
        if missing and not any("缺少" in item or "missing" in item.lower() for item in uncertainty):
            uncertainty.append(f"当前缺少上下文信息：{', '.join(str(item) for item in missing)}。")
        if not rag_chunks and not any("知识库" in item or "knowledge" in item.lower() for item in uncertainty):
            uncertainty.append("当前本地知识库未检索到足够依据，回答可信度受限。")
        for note in REQUIRED_UNCERTAINTY_NOTES:
            if note not in uncertainty:
                uncertainty.append(note)
        if not any("人工" in item or "expert" in item.lower() for item in next_steps):
            next_steps.append("请结合田间复查、清晰近景图像和当地农技人员意见进行人工复核。")

        report = self._free_qa_compat_report(
            question=question,
            answer=answer,
            basis=basis,
            uncertainty=uncertainty,
            next_steps=next_steps,
            safety_notice=safety_notice,
            context=context,
            disease=disease,
            kg_summary=kg_summary,
            rag_chunks=rag_chunks,
            settings=settings,
            fallback_used=fallback_used,
            fallback_level=fallback_level,
            api_error_type=api_error_type,
            repair_attempted=repair_attempted,
        )
        LLMReportSchema(**report)
        return report

    def _generate_free_qa_fallback(
        self,
        question: str,
        context: dict[str, Any],
        disease: dict[str, Any] | None,
        kg_summary: dict[str, Any],
        rag_chunks: list[dict[str, Any]],
        settings: LLMSettings,
        api_error_type: str | None,
    ) -> dict[str, Any]:
        missing = context.get("missing_context") or []
        basis = self._context_basis(context)
        uncertainty = [
            "LLM 当前不可用或处于 mock fallback 状态，本回答不是模型自由推理结果。",
            "当前回答只汇总已知上下文，不应视为正式诊断。",
        ]
        if missing:
            uncertainty.append(f"当前缺少上下文信息：{', '.join(str(item) for item in missing)}。")
        if not rag_chunks:
            uncertainty.append("当前本地知识库未检索到足够依据。")
        parsed = {
            "answer": "AI 巡检问答暂时无法生成真实 LLM 回答。请检查 LLM API 状态，或补充记录、地块、UAV 任务、异常区和近景识别信息后重试。",
            "basis": basis,
            "uncertainty": uncertainty,
            "next_steps": ["优先补充缺失上下文，并请农技人员或巡检人员复核异常区。"],
            "safety_notice": "该回答用于巡检辅助，不作为正式农艺诊断或用药处方。",
        }
        return self._postprocess_free_qa(
            parsed=parsed,
            question=question,
            context=context,
            disease=disease,
            kg_summary=kg_summary,
            rag_chunks=rag_chunks,
            settings=settings,
            fallback_used=settings.mode == "api",
            fallback_level="mock_template" if settings.mode == "api" else "mock_mode",
            api_error_type=api_error_type,
            repair_attempted=False,
        )

    def _free_qa_compat_report(
        self,
        question: str,
        answer: str,
        basis: list[str],
        uncertainty: list[str],
        next_steps: list[str],
        safety_notice: str,
        context: dict[str, Any],
        disease: dict[str, Any] | None,
        kg_summary: dict[str, Any],
        rag_chunks: list[dict[str, Any]],
        settings: LLMSettings,
        fallback_used: bool,
        fallback_level: str,
        api_error_type: str | None,
        repair_attempted: bool,
    ) -> dict[str, Any]:
        risk_level = context.get("risk_level") if context.get("risk_level") in ALLOWED_RISK_LEVELS else None
        if not risk_level:
            confidence = context.get("confidence")
            risk_level = "medium" if isinstance(confidence, (int, float)) and confidence < 0.85 else "high" if confidence else "unknown"
        evidence_sources = self._normalize_evidence_sources([], kg_summary)
        suspected = (
            {
                "disease_id": disease.get("disease_id", ""),
                "zh_name": disease.get("zh_name", ""),
                "en_name": disease.get("en_name", ""),
            }
            if disease
            else {}
        )
        return {
            "mode": "free_qa",
            "question": question,
            "answer": answer,
            "basis": basis,
            "uncertainty": uncertainty,
            "next_steps": next_steps,
            "safety_notice": safety_notice,
            "used_context": self._public_context(context),
            "retrieved_knowledge": self._retrieved_knowledge(rag_chunks),
            "llm_status": {
                "enabled": settings.mode == "api",
                "provider": settings.provider,
                "model": settings.model,
                "fallback_used": fallback_used,
            },
            "suspected_disease": suspected,
            "model_result_summary": self._context_summary(context),
            "knowledge_summary": answer,
            "risk_level": risk_level,
            "manual_check_questions": [question],
            "management_suggestions": next_steps,
            "uncertainty_notes": uncertainty,
            "evidence_sources": evidence_sources,
            "insufficient_evidence": not bool(rag_chunks),
            "llm_mode": "mock" if fallback_used else settings.mode,
            "llm_provider": settings.provider,
            "llm_model": settings.model,
            "prompt_version": settings.prompt_version,
            "fallback_used": fallback_used,
            "fallback_level": fallback_level,
            "api_error_type": api_error_type,
            "repair_attempted": repair_attempted,
            "schema_valid": True,
            "safety_passed": True,
        }

    def _public_context(self, context: dict[str, Any]) -> dict[str, Any]:
        keys = [
            "record_id",
            "field_id",
            "plot_id",
            "uav_task_id",
            "abnormal_region_id",
            "disease_id",
            "model_class",
            "confidence",
            "source_type",
            "risk_level",
            "severity",
            "detector_mode",
            "is_smoke",
            "model_stage",
            "missing_context",
        ]
        return {key: context.get(key) for key in keys if context.get(key) is not None}

    def _retrieved_knowledge(self, rag_chunks: list[dict[str, Any]], include_text: bool = False) -> list[dict[str, Any]]:
        items = []
        for chunk in rag_chunks:
            item = {
                "title": chunk.get("source_title") or chunk.get("source_id") or chunk.get("chunk_id"),
                "disease_id": chunk.get("disease_id"),
                "section_type": chunk.get("section_type"),
                "source_id": chunk.get("source_id"),
            }
            if include_text:
                item["text"] = chunk.get("text")
            items.append(item)
        return items

    def _context_basis(self, context: dict[str, Any]) -> list[str]:
        basis = []
        for key in ("record_id", "field_id", "uav_task_id", "abnormal_region_id", "risk_level", "severity", "confidence"):
            value = context.get(key)
            if value is not None:
                basis.append(f"{key}: {value}")
        return basis or ["当前仅有用户问题，缺少可核查的巡检上下文。"]

    def _context_summary(self, context: dict[str, Any]) -> str:
        parts = self._context_basis(context)
        return "；".join(parts)

    def _generate_mock_report(
        self,
        disease: dict[str, Any],
        kg_summary: dict[str, Any],
        model_class: str | None,
        confidence: float | None,
        source_type: str | None,
        fallback_used: bool = False,
        fallback_level: str = "none",
        api_error_type: str | None = None,
        repair_attempted: bool = False,
        schema_valid: bool = True,
        safety_passed: bool = True,
        settings: LLMSettings | None = None,
    ) -> dict[str, Any]:
        settings = settings or load_llm_settings()
        disease_id = disease["disease_id"]
        confidence_text = "未提供" if confidence is None else f"{confidence:.2f}"
        model_class_text = model_class or "未提供"
        source_text = source_type or "未提供"
        symptoms = "、".join(kg_summary.get("symptoms") or disease.get("typical_symptoms", [])[:3])
        conditions = "、".join(kg_summary.get("conditions") or disease.get("favorable_conditions", [])[:3])
        risk_level = "high" if disease_id == "tungro" else ("medium" if confidence is None or confidence < 0.85 else "high")

        uncertainty_notes = [
            "当前结果仅作辅助判断，不替代农业专家现场诊断。",
            "当前模块处于 mock / smoke / experimental 知识增强状态，不能作为正式生产诊断依据。",
            "识别结论需要结合田间症状、发生时期、品种抗性和当地植保人员复核。",
        ]
        if disease_id == "tungro":
            uncertainty_notes.append("tungro 类别当前风险较高，不建议直接进入正式模型声明或后端演示结论。")

        manual_questions = [
            f"田间是否能观察到与{disease['zh_name']}一致的典型症状：{symptoms}？",
            f"近期是否存在有利条件：{conditions}？",
            "相邻田块或同一田块不同位置是否出现相似症状，且症状是否持续扩展？",
        ]
        if disease_id == "tungro":
            manual_questions.append("田间是否可见叶蝉活动或邻近区域存在 tungro 流行风险？")

        return {
            "suspected_disease": {
                "disease_id": disease_id,
                "zh_name": disease["zh_name"],
                "en_name": disease["en_name"],
            },
            "model_result_summary": (
                f"模型类别 {model_class_text} 输出疑似 {disease['zh_name']}，置信度为 {confidence_text}，"
                f"来源类型为 {source_text}。该结果不能作为诊断结论。"
            ),
            "knowledge_summary": (
                f"{disease['zh_name']}主要关联部位为{'、'.join(disease.get('affected_parts', []))}。"
                f"知识库提示需重点核查{symptoms}，并结合{conditions}等环境或田间条件判断。"
            ),
            "risk_level": risk_level,
            "manual_check_questions": manual_questions,
            "management_suggestions": disease.get("management_suggestions", [])
            + ["具体药剂和用量应以当地农业技术部门建议和产品标签为准。"],
            "uncertainty_notes": uncertainty_notes,
            "evidence_sources": kg_summary.get("evidence_sources", []),
            "insufficient_evidence": False,
            "llm_mode": "mock",
            "llm_provider": settings.provider,
            "llm_model": settings.model,
            "prompt_version": settings.prompt_version,
            "fallback_used": fallback_used,
            "fallback_level": fallback_level,
            "api_error_type": api_error_type,
            "repair_attempted": repair_attempted,
            "schema_valid": schema_valid,
            "safety_passed": safety_passed,
        }

    def _postprocess_report(
        self,
        parsed: dict[str, Any],
        base_report: dict[str, Any],
        disease: dict[str, Any],
        kg_summary: dict[str, Any],
        settings: LLMSettings,
        llm_mode: str,
        fallback_used: bool,
        fallback_level: str,
        api_error_type: str | None,
        repair_attempted: bool,
    ) -> dict[str, Any]:
        report = dict(base_report)
        for key in REQUIRED_REPORT_FIELDS:
            if key in parsed:
                report[key] = parsed[key]

        report["suspected_disease"] = self._normalize_suspected_disease(report.get("suspected_disease"), disease)
        report["risk_level"] = report.get("risk_level") if report.get("risk_level") in {"low", "medium", "high", "unknown"} else base_report["risk_level"]
        report["manual_check_questions"] = self._safe_list(report.get("manual_check_questions"))
        report["management_suggestions"] = self._safe_list(report.get("management_suggestions"))
        report["uncertainty_notes"] = self._safe_list(report.get("uncertainty_notes"))
        report["evidence_sources"] = self._normalize_evidence_sources(report.get("evidence_sources"), kg_summary)
        report["model_result_summary"] = self._sanitize_text(report.get("model_result_summary") or base_report["model_result_summary"])
        report["knowledge_summary"] = self._sanitize_text(report.get("knowledge_summary") or base_report["knowledge_summary"])
        report["manual_check_questions"] = [self._sanitize_text(item) for item in report["manual_check_questions"]]
        report["management_suggestions"] = [self._sanitize_text(item) for item in report["management_suggestions"]]
        report["uncertainty_notes"] = [self._sanitize_text(item) for item in report["uncertainty_notes"]]
        report["insufficient_evidence"] = bool(report.get("insufficient_evidence"))

        for note in REQUIRED_UNCERTAINTY_NOTES:
            if note not in report["uncertainty_notes"]:
                report["uncertainty_notes"].append(note)
        if disease.get("disease_id") == "tungro":
            warning = "tungro 类别当前风险较高，不建议直接进入正式模型声明或后端演示结论。"
            if not any("不建议直接进入正式模型声明" in item for item in report["uncertainty_notes"]):
                report["uncertainty_notes"].append(warning)

        if not report["evidence_sources"]:
            report["insufficient_evidence"] = True

        report["llm_mode"] = llm_mode
        report["llm_provider"] = settings.provider
        report["llm_model"] = settings.model
        report["prompt_version"] = settings.prompt_version
        report["fallback_used"] = fallback_used
        report["fallback_level"] = fallback_level
        report["api_error_type"] = api_error_type
        report["repair_attempted"] = repair_attempted
        report["schema_valid"] = False
        report["safety_passed"] = True
        self._validate_final_report(report)
        report["schema_valid"] = True
        return report

    def _validate_final_report(self, report: dict[str, Any]) -> None:
        try:
            LLMReportSchema(**report)
        except ValidationError as exc:
            raise LLMClientError("schema_validation_error", str(exc), schema_valid=False) from exc

    def _normalize_suspected_disease(self, value: Any, disease: dict[str, Any]) -> dict[str, str]:
        if not isinstance(value, dict):
            value = {}
        return {
            "disease_id": str(value.get("disease_id") or disease.get("disease_id", "")),
            "zh_name": str(value.get("zh_name") or disease.get("zh_name", "")),
            "en_name": str(value.get("en_name") or disease.get("en_name", "")),
        }

    def _safe_list(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    def _normalize_evidence_sources(self, value: Any, kg_summary: dict[str, Any]) -> list[dict[str, Any]]:
        required = {"source_id", "source_title", "source_type", "authority_level", "url_or_reference", "language"}
        if (
            isinstance(value, list)
            and value
            and all(isinstance(item, dict) and required.issubset(item.keys()) for item in value)
        ):
            return value
        sources = kg_summary.get("evidence_sources", [])
        return sources if isinstance(sources, list) else []

    def _sanitize_text(self, value: Any) -> str:
        text = str(value or "")
        text = text.replace("最终诊断", "辅助判断")
        if DOSAGE_PATTERN.search(text):
            text = DOSAGE_PATTERN.sub("具体用量", text)
            text += "；具体药剂、浓度和施用时间应以当地农业技术部门建议和产品标签为准。"
        return text


llm_client = MockLLMClient()


def get_llm_status() -> dict[str, Any]:
    settings = load_llm_settings()
    return {
        "llm_mode": settings.mode,
        "llm_provider": settings.provider,
        "llm_model": settings.model,
        "json_response_format_enabled": settings.enable_json_response_format,
        "mock_fallback_enabled": settings.enable_mock_fallback,
        "api_key_configured": bool(settings.api_key),
        "prompt_version": settings.prompt_version,
    }
