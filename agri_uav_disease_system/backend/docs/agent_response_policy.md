# Agent Response Policy

## Required Output Rules

The agent must not present image or model output as final diagnosis. It must state that the result is only for auxiliary judgment and does not replace field diagnosis by agricultural experts.

The agent must not output unsupported facts. Successful reports must include non-empty evidence sources from the local source catalog.

The agent must not output mandatory pesticide dosage, absolute medication plans, or production decisions. Management suggestions are directional and must defer specific product and dosage decisions to local agricultural technical departments and product labels.

The agent must include uncertainty notes in every report.

In mock, smoke, or experimental state, the agent must clearly say the report cannot be used as formal production diagnosis evidence.

## Real LLM API Mode

When `LLM_MODE=api`, the real LLM must only use the structured context built from disease JSON, KG summary, RAG evidence, model result fields, and response policy. It must not invent external facts, read images, call multimodal models, or bypass KG/RAG evidence.

The backend postprocesses API output before returning it. Missing uncertainty notes, missing experimental boundary notes, missing evidence source objects, and missing tungro risk warnings are repaired from local KG/RAG context where possible. Dosage, concentration, mixture ratio, or forced pesticide plans are removed or replaced with a local-authority/product-label safety reminder.

The API response may include `llm_mode`, `llm_provider`, `llm_model`, `prompt_version`, `fallback_used`, and `api_error_type`. It must never include API keys, authorization headers, or raw provider requests.

## Insufficient Evidence

Unknown `model_class`, unknown `disease_id`, missing KG evidence, or missing RAG chunks return `insufficient_evidence=true`. In that state, evidence sources may be empty and the agent should ask for additional field evidence or expert review.

## Tungro Boundary

Tungro is a high-risk v0.1 category. Its report must include a warning that it is not recommended for direct formal model statements or backend demo conclusions.
