from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.database.uav_repositories import uav_repository
from app.services.knowledge_service import KnowledgeNotFoundError, knowledge_service
from app.services.llm_client import llm_client
from app.services.storage.result_store import result_store


class AgentService:
    def build_knowledge_context(
        self,
        question: str,
        record_id: str | None = None,
        disease_id: str | None = None,
        model_class: str | None = None,
        confidence: float | None = None,
        source_type: str | None = None,
        top_k: int = 5,
        include_knowledge_chunks: bool = True,
        include_graph: bool = True,
        include_relations: bool = True,
    ) -> dict[str, Any]:
        context = self._build_inspection_context(
            record_id=record_id,
            disease_id=disease_id,
            model_class=model_class,
            confidence=confidence,
            source_type=source_type,
            field_id=None,
            plot_id=None,
            uav_task_id=None,
            abnormal_region_id=None,
            risk_level=None,
            severity=None,
        )
        resolved_disease_id = str(context.get("disease_id") or "")
        if not resolved_disease_id:
            resolved_disease_id = self._resolve_disease_id(model_class) or ""

        disease: dict[str, Any] | None = None
        missing_context = list(context.get("missing_context", []))
        chunks: list[dict[str, Any]] = []
        graph = {"entities": [], "relations": [], "triples": []}

        if resolved_disease_id:
            try:
                disease = knowledge_service.get_disease(resolved_disease_id)
                if include_knowledge_chunks:
                    chunks = knowledge_service.search_knowledge(question, resolved_disease_id, None, top_k)
                graph = knowledge_service.get_kg_context(resolved_disease_id, include_graph, include_relations)
            except KnowledgeNotFoundError:
                missing_context.append("known disease profile for disease_id")
        else:
            missing_context.append("disease_id or model_class mapping")
            if include_knowledge_chunks:
                chunks = knowledge_service.search_knowledge(question, None, None, top_k)

        knowledge_chunks = [
            {
                "chunk_id": str(chunk.get("chunk_id", "")),
                "title": str(chunk.get("source_title") or chunk.get("chunk_id") or "知识片段"),
                "section_type": str(chunk.get("section_type", "unknown")),
                "content": str(chunk.get("text", "")),
                "source": str(chunk.get("source_type") or chunk.get("source_id") or "knowledge_base"),
                "score": float(chunk.get("score", 0.0)),
                "disease_id": str(chunk.get("disease_id", resolved_disease_id)),
                "authority_level": str(chunk.get("authority_level", "unknown")),
            }
            for chunk in chunks
        ]
        matched_disease = None
        if disease:
            matched_disease = {
                "disease_id": disease["disease_id"],
                "name": disease.get("zh_name") or disease.get("en_name") or disease["disease_id"],
                "aliases": disease.get("aliases", []),
            }

        insufficient = not matched_disease or (include_knowledge_chunks and not knowledge_chunks)
        disease_name = matched_disease["name"] if matched_disease else "未确定病害"
        context_summary = (
            f"当前问题与{disease_name}相关。已返回 {len(knowledge_chunks)} 条知识片段、"
            f"{len(graph.get('entities', []))} 个图谱实体和 {len(graph.get('triples', []))} 条三元组。"
            if matched_disease
            else "当前问题暂未匹配到明确病害，返回的上下文仅可用于继续检索和人工复核。"
        )

        return {
            "success": True,
            "mode": "knowledge_context",
            "question": question,
            "matched_disease": matched_disease,
            "knowledge_chunks": knowledge_chunks,
            "graph": graph,
            "context_summary": context_summary,
            "safety_notice": "该知识上下文仅用于辅助解释，不作为正式农艺诊断或用药依据。",
            "insufficient_evidence": insufficient,
            "missing_context": missing_context,
        }

    def generate_diagnosis_report(
        self,
        record_id: str | None = None,
        disease_id: str | None = None,
        model_class: str | None = None,
        confidence: float | None = None,
        source_type: str | None = None,
        field_id: str | None = None,
        plot_id: str | None = None,
        uav_task_id: str | None = None,
        abnormal_region_id: str | None = None,
        risk_level: str | None = None,
        severity: str | None = None,
        user_question: str | None = None,
    ) -> dict[str, Any]:
        normalized_question = (user_question or "").strip()
        if normalized_question:
            return self._generate_free_qa(
                question=normalized_question,
                record_id=record_id,
                disease_id=disease_id,
                model_class=model_class,
                confidence=confidence,
                source_type=source_type,
                field_id=field_id,
                plot_id=plot_id,
                uav_task_id=uav_task_id,
                abnormal_region_id=abnormal_region_id,
                risk_level=risk_level,
                severity=severity,
            )

        resolved_disease_id = disease_id
        if not resolved_disease_id and model_class:
            mapping = knowledge_service.map_model_class_to_disease(model_class)
            resolved_disease_id = mapping.get("disease_id")

        if not resolved_disease_id:
            return self._insufficient_report(model_class, "unknown_mapping")

        try:
            disease = knowledge_service.get_disease(resolved_disease_id)
        except KnowledgeNotFoundError:
            return self._insufficient_report(model_class, "unknown_disease_id")

        kg_summary = knowledge_service.get_kg_summary(resolved_disease_id)
        rag_query = user_question or f"{disease['zh_name']} 症状 防治 风险"
        rag_chunks = knowledge_service.search_knowledge(rag_query, resolved_disease_id, None, 5)
        if not kg_summary.get("evidence_sources") or not rag_chunks:
            return self._insufficient_report(model_class, "missing_evidence")

        report = llm_client.generate_report(
            disease,
            kg_summary,
            rag_chunks,
            model_class,
            confidence,
            source_type,
            user_question=user_question,
        )
        if not report.get("evidence_sources"):
            report["insufficient_evidence"] = True
        return report

    def _generate_free_qa(
        self,
        question: str,
        record_id: str | None,
        disease_id: str | None,
        model_class: str | None,
        confidence: float | None,
        source_type: str | None,
        field_id: str | None,
        plot_id: str | None,
        uav_task_id: str | None,
        abnormal_region_id: str | None,
        risk_level: str | None,
        severity: str | None,
    ) -> dict[str, Any]:
        context = self._build_inspection_context(
            record_id=record_id,
            disease_id=disease_id,
            model_class=model_class,
            confidence=confidence,
            source_type=source_type,
            field_id=field_id,
            plot_id=plot_id,
            uav_task_id=uav_task_id,
            abnormal_region_id=abnormal_region_id,
            risk_level=risk_level,
            severity=severity,
        )
        resolved_disease_id = context.get("disease_id")
        disease: dict[str, Any] | None = None
        kg_summary: dict[str, Any] = {"evidence_sources": []}
        if resolved_disease_id:
            try:
                disease = knowledge_service.get_disease(str(resolved_disease_id))
                kg_summary = knowledge_service.get_kg_summary(str(resolved_disease_id))
            except KnowledgeNotFoundError:
                context["missing_context"].append("known disease profile for disease_id")
        rag_chunks = knowledge_service.search_knowledge(question, str(resolved_disease_id) if resolved_disease_id else None, None, 5)
        return llm_client.generate_free_qa(
            question=question,
            context=context,
            disease=disease,
            kg_summary=kg_summary,
            rag_chunks=rag_chunks,
        )

    def _build_inspection_context(
        self,
        record_id: str | None,
        disease_id: str | None,
        model_class: str | None,
        confidence: float | None,
        source_type: str | None,
        field_id: str | None,
        plot_id: str | None,
        uav_task_id: str | None,
        abnormal_region_id: str | None,
        risk_level: str | None,
        severity: str | None,
    ) -> dict[str, Any]:
        record = result_store.get(record_id) if record_id else None
        if record:
            field_id = field_id or record.field_id
            plot_id = plot_id or record.plot_id
            uav_task_id = uav_task_id or record.uav_task_id
            abnormal_region_id = abnormal_region_id or record.abnormal_region_id
            source_type = source_type or record.source_type
            risk_level = risk_level or record.summary.risk_level
            severity = severity or record.summary.severity
            confidence = confidence if confidence is not None else record.summary.max_confidence
            model_class = model_class or self._record_model_class(record)
            disease_id = disease_id or self._resolve_disease_id(model_class)

        region = uav_repository.get_region(abnormal_region_id) if abnormal_region_id else None
        if region:
            field_id = field_id or region.field_id
            uav_task_id = uav_task_id or region.uav_task_id
            risk_level = risk_level or region.abnormal_level

        task = uav_repository.get_task(uav_task_id) if uav_task_id else None
        if task:
            field_id = field_id or task.field_id

        if not disease_id:
            disease_id = self._resolve_disease_id(model_class)

        record_summary = None
        suggestion = None
        if record:
            record_summary = {
                "main_disease": record.summary.main_disease,
                "max_confidence": record.summary.max_confidence,
                "severity": record.summary.severity,
                "risk_level": record.summary.risk_level,
                "detection_count": len(record.detections),
            }
            suggestion = record.suggestion.model_dump()

        context = {
            "record_id": record_id,
            "record_found": bool(record),
            "field_id": field_id,
            "plot_id": plot_id,
            "uav_task_id": uav_task_id,
            "abnormal_region_id": abnormal_region_id,
            "disease_id": disease_id,
            "model_class": model_class,
            "confidence": confidence,
            "source_type": source_type,
            "risk_level": risk_level,
            "severity": severity,
            "detector_mode": record.detector_mode if record else settings.detector_mode,
            "is_smoke": record.is_smoke if record else None,
            "model_stage": record.model_stage if record else "unknown",
            "record_summary": record_summary,
            "suggestion": suggestion,
            "uav_task": task.model_dump() if task else None,
            "abnormal_region": region.model_dump() if region else None,
            "missing_context": [],
        }
        required = [
            "record_id",
            "field_id",
            "plot_id",
            "uav_task_id",
            "abnormal_region_id",
            "risk_level",
            "severity",
            "disease_id",
        ]
        context["missing_context"] = [key for key in required if not context.get(key)]
        if record_id and not record:
            context["missing_context"].append("record detail for record_id")
        return context

    def _resolve_disease_id(self, model_class: str | None) -> str | None:
        if not model_class:
            return None
        return knowledge_service.map_model_class_to_disease(model_class).get("disease_id")

    def _record_model_class(self, record: Any) -> str | None:
        if record.model_hint:
            return record.model_hint
        if record.detections:
            first = record.detections[0]
            return first.class_code or first.class_name or first.label
        return record.summary.main_disease

    def _insufficient_report(self, model_class: str | None, reason: str) -> dict[str, Any]:
        return {
            "suspected_disease": {},
            "model_result_summary": f"无法根据 model_class={model_class or '未提供'} 建立可靠病害映射。",
            "knowledge_summary": "当前证据不足，系统不会猜测病害结论。",
            "risk_level": "unknown",
            "manual_check_questions": ["请补充 disease_id、清晰图像、田间症状或由植保人员复核。"],
            "management_suggestions": ["证据不足时不提供针对性处置方案，请咨询当地农业技术人员。"],
            "uncertainty_notes": [
                "当前结果仅作辅助判断，不替代农业专家现场诊断。",
                f"insufficient_evidence reason: {reason}",
            ],
            "evidence_sources": [],
            "insufficient_evidence": True,
            "llm_mode": "none",
            "llm_provider": "",
            "llm_model": "",
            "prompt_version": "kg_rag_agent_prompt_v1",
            "fallback_used": False,
            "fallback_level": "insufficient_evidence",
            "api_error_type": None,
            "repair_attempted": False,
            "schema_valid": True,
            "safety_passed": True,
        }


agent_service = AgentService()
