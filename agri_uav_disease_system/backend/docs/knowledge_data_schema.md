# Knowledge Data Schema

## Disease JSON

Required fields: `disease_id`, `zh_name`, `en_name`, `aliases`, `pathogen_type`, `pathogen_name`, `affected_crop`, `affected_parts`, `typical_symptoms`, `early_symptoms`, `late_symptoms`, `similar_diseases`, `favorable_conditions`, `transmission`, `risk_notes`, `management_suggestions`, `model_class_mapping`, `evidence_sources`, `authority_level`, and `last_updated`.

`authority_level` must be `A`, `B`, or `C`. v0.1 formal knowledge uses A/B sources only.

## Source Catalog

Each source has `source_id`, `source_title`, `source_type`, `authority_level`, `url_or_reference`, `language`, and `notes`.

## KG Entities

Each entity has `entity_id`, `type`, and `label`. Entity IDs must be unique.

## KG Relations

Each relation has `relation_id`, `label`, and `description`. Relation IDs must be unique.

## KG Triples

Each triple has `triple_id`, `subject`, `predicate`, `object`, `evidence_source_ids`, `confidence`, and `notes`. Subjects and objects must exist in `kg_entities.json`; predicates must exist in `kg_relations.json`; evidence sources must be non-empty.

## RAG Chunks

Each JSONL row has `chunk_id`, `source_id`, `source_title`, `source_type`, `authority_level`, `crop`, `disease_id`, `section_type`, `text`, `language`, and `retrieved_at`.

Allowed `section_type`: `symptom`, `cause`, `condition`, `transmission`, `management`, `differential_diagnosis`, `model_boundary`, `demo_safety`, and `risk_note`.
