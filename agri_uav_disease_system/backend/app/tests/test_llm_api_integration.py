from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from app.services import llm_client as llm_client_module
from app.services.agent_service import agent_service


client = TestClient(app)


def _set_api_env(monkeypatch, fallback: bool = True) -> None:
    monkeypatch.setenv("LLM_MODE", "api")
    monkeypatch.setenv("LLM_PROVIDER", "custom_openai_compatible")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_ENABLE_JSON_RESPONSE_FORMAT", "true")
    monkeypatch.setenv("LLM_ENABLE_MOCK_FALLBACK", "true" if fallback else "false")
    monkeypatch.setenv("LLM_PROMPT_VERSION", "kg_rag_agent_prompt_v1")


def _fake_chat_response(payload: dict) -> dict:
    return {"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]}


def _valid_llm_payload(**overrides):
    payload = {
        "suspected_disease": {
            "disease_id": "bacterial_leaf_blight",
            "zh_name": "BLB",
            "en_name": "Bacterial leaf blight",
        },
        "model_result_summary": "The model suggests a possible BLB case; this is not a final diagnosis.",
        "knowledge_summary": "Evidence indicates leaf-margin water-soaked streaks should be checked.",
        "risk_level": "medium",
        "manual_check_questions": ["Are there leaf-margin water-soaked streaks?"],
        "management_suggestions": ["Perform field review first."],
        "uncertainty_notes": ["Auxiliary interpretation only; field expert review is required."],
        "evidence_sources": [{"source_id": "src_irri_blb", "source_title": "IRRI BLB"}],
        "insufficient_evidence": False,
    }
    payload.update(overrides)
    return payload


def _valid_free_qa_payload(**overrides):
    payload = {
        "answer": "Use the UAV region risk, phone confidence, and local knowledge together; this is only auxiliary.",
        "basis": ["user question", "inspection context", "RAG evidence"],
        "uncertainty": ["Missing field review can cause uncertainty."],
        "next_steps": ["Review the abnormal region manually before making decisions."],
        "safety_notice": "Auxiliary inspection answer only; not a diagnosis or pesticide prescription.",
    }
    payload.update(overrides)
    return payload


def test_deepseek_v4_flash_config_can_be_read(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "deepseek-v4-flash")
    assert llm_client_module.load_llm_settings().model == "deepseek-v4-flash"


def test_llm_mode_mock_keeps_existing_report(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "mock")
    report = agent_service.generate_diagnosis_report(
        disease_id="bacterial_leaf_blight",
        model_class="uav_blb",
        confidence=0.72,
        source_type="uav",
    )
    assert report["llm_mode"] == "mock"
    assert report["fallback_used"] is False
    assert report["fallback_level"] == "none"
    assert report["schema_valid"] is True
    assert report["safety_passed"] is True
    assert report["evidence_sources"]
    assert report["uncertainty_notes"]


def test_api_mode_missing_key_uses_mock_fallback(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "api")
    monkeypatch.setenv("LLM_API_KEY", " ")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_ENABLE_MOCK_FALLBACK", "true")

    report = agent_service.generate_diagnosis_report(
        disease_id="bacterial_leaf_blight",
        model_class="uav_blb",
        confidence=0.72,
        source_type="uav",
    )
    assert report["llm_mode"] == "mock"
    assert report["fallback_used"] is True
    assert report["fallback_level"] == "mock_template"
    assert report["api_error_type"] == "missing_api_key"


def test_api_mode_without_fallback_returns_clear_http_error(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "api")
    monkeypatch.setenv("LLM_API_KEY", " ")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_ENABLE_MOCK_FALLBACK", "false")

    response = client.post(
        "/api/agent/diagnosis-report",
        json={"disease_id": "bacterial_leaf_blight", "model_class": "uav_blb", "confidence": 0.72},
    )
    assert response.status_code == 502
    assert response.json()["detail"]["error_code"] == "LLM_API_ERROR"
    assert response.json()["detail"]["error_type"] == "missing_api_key"


def test_api_mode_success_returns_api_metadata(monkeypatch):
    _set_api_env(monkeypatch)

    def fake_post(self, settings, payload):
        return _fake_chat_response(_valid_llm_payload())

    monkeypatch.setattr(llm_client_module.MockLLMClient, "_post_chat_completion", fake_post)
    report = agent_service.generate_diagnosis_report(
        disease_id="bacterial_leaf_blight",
        model_class="uav_blb",
        confidence=0.72,
        source_type="uav",
    )
    assert report["llm_mode"] == "api"
    assert report["llm_provider"] == "custom_openai_compatible"
    assert report["llm_model"] == "test-model"
    assert report["prompt_version"] == "kg_rag_agent_prompt_v1"
    assert report["fallback_used"] is False
    assert report["fallback_level"] == "none"
    assert report["repair_attempted"] is False
    assert report["schema_valid"] is True
    assert report["safety_passed"] is True
    assert report["evidence_sources"]
    assert report["uncertainty_notes"]


def test_api_mode_invalid_json_triggers_fallback(monkeypatch):
    _set_api_env(monkeypatch)

    def fake_post(self, settings, payload):
        return {"choices": [{"message": {"content": "not json"}}]}

    monkeypatch.setattr(llm_client_module.MockLLMClient, "_post_chat_completion", fake_post)
    report = agent_service.generate_diagnosis_report(disease_id="bacterial_leaf_blight", model_class="uav_blb")
    assert report["llm_mode"] == "mock"
    assert report["fallback_used"] is True
    assert report["fallback_level"] == "mock_template"
    assert report["api_error_type"] == "invalid_llm_json"


def test_api_mode_accepts_embedded_json_object(monkeypatch):
    _set_api_env(monkeypatch)

    def fake_post(self, settings, payload):
        assert payload["response_format"] == {"type": "json_object"}
        content = "Here is JSON:\n```json\n" + json.dumps(_valid_llm_payload(), ensure_ascii=False) + "\n```"
        return {"choices": [{"message": {"content": content}}]}

    monkeypatch.setattr(llm_client_module.MockLLMClient, "_post_chat_completion", fake_post)
    report = agent_service.generate_diagnosis_report(disease_id="bacterial_leaf_blight", model_class="uav_blb")
    assert report["llm_mode"] == "api"
    assert report["fallback_used"] is False
    assert report["api_error_type"] is None


def test_api_mode_missing_field_triggers_repair_success(monkeypatch):
    _set_api_env(monkeypatch)
    calls = []

    def fake_post(self, settings, payload):
        calls.append(payload)
        if len(calls) == 1:
            invalid = _valid_llm_payload()
            invalid.pop("knowledge_summary")
            return _fake_chat_response(invalid)
        return _fake_chat_response(_valid_llm_payload(knowledge_summary="repair ok"))

    monkeypatch.setattr(llm_client_module.MockLLMClient, "_post_chat_completion", fake_post)
    report = agent_service.generate_diagnosis_report(disease_id="bacterial_leaf_blight", model_class="uav_blb")
    assert len(calls) == 2
    assert report["llm_mode"] == "api"
    assert report["fallback_used"] is False
    assert report["repair_attempted"] is True
    assert report["schema_valid"] is True
    assert report["fallback_level"] == "none"


def test_api_mode_repair_failure_triggers_mock_fallback(monkeypatch):
    _set_api_env(monkeypatch)

    def fake_post(self, settings, payload):
        invalid = _valid_llm_payload()
        invalid.pop("knowledge_summary")
        return _fake_chat_response(invalid)

    monkeypatch.setattr(llm_client_module.MockLLMClient, "_post_chat_completion", fake_post)
    report = agent_service.generate_diagnosis_report(disease_id="bacterial_leaf_blight", model_class="uav_blb")
    assert report["llm_mode"] == "mock"
    assert report["fallback_used"] is True
    assert report["fallback_level"] == "mock_template"
    assert report["repair_attempted"] is True
    assert report["schema_valid"] is True
    assert report["api_error_type"] == "schema_validation_error"


def test_api_mode_missing_evidence_is_backfilled(monkeypatch):
    _set_api_env(monkeypatch)

    def fake_post(self, settings, payload):
        return _fake_chat_response(_valid_llm_payload(evidence_sources=[]))

    monkeypatch.setattr(llm_client_module.MockLLMClient, "_post_chat_completion", fake_post)
    report = agent_service.generate_diagnosis_report(disease_id="bacterial_leaf_blight", model_class="uav_blb")
    assert report["llm_mode"] == "api"
    assert report["evidence_sources"]
    assert report["uncertainty_notes"]
    assert report["insufficient_evidence"] is False


def test_api_mode_pesticide_dosage_is_sanitized(monkeypatch):
    _set_api_env(monkeypatch)

    def fake_post(self, settings, payload):
        return _fake_chat_response(
            _valid_llm_payload(
                manual_check_questions=["Is the lesion expanding?"],
                management_suggestions=["Use 100 mL pesticide at 30% concentration."],
            )
        )

    monkeypatch.setattr(llm_client_module.MockLLMClient, "_post_chat_completion", fake_post)
    report = agent_service.generate_diagnosis_report(disease_id="bacterial_leaf_blight", model_class="uav_blb")
    joined = json.dumps(report, ensure_ascii=False)
    assert "100 mL" not in joined
    assert "30%" not in joined


def test_unknown_model_class_does_not_call_llm(monkeypatch):
    _set_api_env(monkeypatch)

    def fail_post(self, settings, payload):
        raise AssertionError("LLM should not be called for unknown mappings")

    monkeypatch.setattr(llm_client_module.MockLLMClient, "_post_chat_completion", fail_post)
    report = agent_service.generate_diagnosis_report(model_class="unknown_class")
    assert report["insufficient_evidence"] is True
    assert report["llm_mode"] == "none"
    assert report["fallback_level"] == "insufficient_evidence"


def test_api_mode_tungro_warning_is_enforced(monkeypatch):
    _set_api_env(monkeypatch)

    def fake_post(self, settings, payload):
        return _fake_chat_response(
            _valid_llm_payload(
                suspected_disease={"disease_id": "tungro", "zh_name": "Tungro", "en_name": "Rice tungro disease"},
                risk_level="high",
            )
        )

    monkeypatch.setattr(llm_client_module.MockLLMClient, "_post_chat_completion", fake_post)
    report = agent_service.generate_diagnosis_report(disease_id="tungro", model_class="phone_tungro")
    joined = json.dumps(report, ensure_ascii=False)
    assert report["llm_mode"] == "api"
    assert "tungro" in joined


def test_llm_status_does_not_leak_key_or_prompt(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "api")
    monkeypatch.setenv("LLM_PROVIDER", "custom_openai_compatible")
    monkeypatch.setenv("LLM_API_KEY", "secret-test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("LLM_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("LLM_ENABLE_JSON_RESPONSE_FORMAT", "true")
    monkeypatch.setenv("LLM_ENABLE_MOCK_FALLBACK", "true")

    response = client.get("/api/agent/llm-status")
    assert response.status_code == 200
    data = response.json()
    assert data["llm_model"] == "deepseek-v4-flash"
    assert data["json_response_format_enabled"] is True
    assert data["mock_fallback_enabled"] is True
    assert data["api_key_configured"] is True
    joined = json.dumps(data, ensure_ascii=False)
    assert "secret-test-key" not in joined
    assert "Authorization" not in joined
    assert "messages" not in joined
    assert "system prompt" not in joined


def test_user_question_enters_free_qa_and_is_sent_to_llm(monkeypatch):
    _set_api_env(monkeypatch)
    captured = {}

    def fake_post(self, settings, payload):
        captured["payload"] = payload
        return _fake_chat_response(_valid_free_qa_payload())

    monkeypatch.setattr(llm_client_module.MockLLMClient, "_post_chat_completion", fake_post)
    question = "为什么这个异常区 UAV 显示中风险，但手机近景识别置信度不高？"
    report = agent_service.generate_diagnosis_report(
        disease_id="bacterial_leaf_blight",
        model_class="uav_blb",
        confidence=0.42,
        source_type="uav",
        field_id="field_1",
        uav_task_id="task_1",
        abnormal_region_id="region_1",
        risk_level="medium",
        user_question=question,
    )
    assert report["mode"] == "free_qa"
    assert report["question"] == question
    assert report["answer"]
    assert report["basis"]
    assert report["uncertainty"]
    assert report["next_steps"]
    sent = json.loads(captured["payload"]["messages"][1]["content"])
    assert sent["question"] == question
    assert sent["inspection_context"]["uav_task_id"] == "task_1"
    assert sent["inspection_context"]["abnormal_region_id"] == "region_1"


def test_free_qa_uses_real_user_question_for_rag(monkeypatch):
    _set_api_env(monkeypatch)
    seen = {}

    def fake_search(query, disease_id=None, section_type=None, top_k=5):
        seen["query"] = query
        return []

    def fake_post(self, settings, payload):
        return _fake_chat_response(_valid_free_qa_payload())

    monkeypatch.setattr("app.services.agent_service.knowledge_service.search_knowledge", fake_search)
    monkeypatch.setattr(llm_client_module.MockLLMClient, "_post_chat_completion", fake_post)
    question = "当前回答用了哪些数据作为依据？"
    report = agent_service.generate_diagnosis_report(model_class="unknown_class", user_question=question)
    assert seen["query"] == question
    assert report["mode"] == "free_qa"


def test_free_qa_api_failure_returns_clear_fallback_not_fake_answer(monkeypatch):
    _set_api_env(monkeypatch)

    def fake_post(self, settings, payload):
        raise llm_client_module.LLMClientError("timeout", "simulated timeout")

    monkeypatch.setattr(llm_client_module.MockLLMClient, "_post_chat_completion", fake_post)
    report = agent_service.generate_diagnosis_report(
        disease_id="bacterial_leaf_blight",
        user_question="这个建议能不能直接作为用药依据？",
    )
    assert report["mode"] == "free_qa"
    assert report["fallback_used"] is True
    assert report["api_error_type"] == "timeout"
    assert "暂时无法生成真实 LLM 回答" in report["answer"]
    assert "不作为正式农艺诊断或用药处方" in report["safety_notice"]
