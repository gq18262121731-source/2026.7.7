# Demo Q&A Guide

## Common Questions

### 1. Is this a formal disease diagnosis model?

No. The project currently has smoke and experimental routes, but no formal model.

### 2. Why are there smoke and experimental routes?

Smoke verifies the engineering chain with small samples. Experimental verifies a larger internal route without claiming formal performance.

### 3. Why does the default UAV route detect rice panicle?

Because the default UAV route is a crop-object smoke path used to verify UAV ingestion and inference wiring, not disease detection.

### 4. Why is UAV BLB experimental not formal?

Because it is based on an RGB preview render derived from multispectral TIF data, uses a constrained dataset, and has no formal validation protocol.

### 5. Why is phone experimental not formal?

Because it is a 3 epoch experimental run on RiceLeafDiseaseBD expanded data and still carries source class-id mapping risk.

### 6. What risk does the RiceLeafDiseaseBD dataset have?

The source class ids were not fully consistent with observed labels, so the conversion used `source_directory_based_remap` as a conservative strategy.

### 7. Why is Healthy not a detection class?

Healthy is a state label, not a disease target. Returning it as a disease class would confuse diagnosis and reporting.

### 8. What happens if a weight is missing?

The route falls back to Mock and returns `fallback_to_mock=true`.

### 9. Is Mock fallback fake?

Mock is a simulated output used only to keep the system available when a model or dependency is unavailable.

### 10. What has the system actually completed?

It has completed data ingestion, training support, route selection, inference adapter wiring, result rendering, SQLite persistence, dashboard/mobile/status APIs, WebSocket push, smoke routes, experimental routes, and pytest verification.

### 11. How do we move from experimental to formal?

By collecting larger datasets, defining a stable validation protocol, doing independent tests, and obtaining expert review.

### 12. Can we give real agronomic treatment advice now?

No. The current outputs are for engineering verification and demonstration only.

### 13. Why is `formal_metric_available=false`?

Because the current smoke and experimental artifacts do not represent a formal validated production model.

### 14. Why must the frontend show warnings?

Because the user must not mistake smoke or experimental routes for production diagnosis.

### 15. Which routes are best for a demo?

The safest demo order is: model status, demo safety, phone default smoke, phone experimental, UAV default crop_object, UAV BLB smoke, UAV BLB experimental, history records, WebSocket, and then Mock fallback if you want to show the safety path.
