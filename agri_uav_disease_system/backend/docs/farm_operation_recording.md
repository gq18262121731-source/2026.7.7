# Farm Operation Recording

Farm operation APIs record user actions only. They do not generate pesticide dosage or mandatory treatment plans.

Endpoints:
- `POST /api/farm-operations`
- `GET /api/farm-operations`
- `GET /api/farm-operations/plots/{plot_id}`

Stored fields:
- `operation_id`
- `plot_id`
- `operation_type`
- `operation_time`
- `target_disease`
- `material_name`
- `dosage_text`
- `operator_id`
- `operator_name`
- `note`
- `photo_url`
- `created_at`

The prediction feature builder treats recent review, drainage, patrol, or management operations as risk-reducing evidence. The final advice remains auxiliary and requires expert confirmation for concrete prevention plans and pesticide dosage.
