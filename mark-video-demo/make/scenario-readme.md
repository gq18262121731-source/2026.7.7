# Make Scenario

Demo 阶段使用 Mock Make 状态。

推荐真实 Make 场景节点：

1. Custom Webhook
2. JSON Parse
3. Google Sheets Add Row
4. Email/Gmail Notification
5. AI Analysis Archive

Webhook payload 应包含：

- `task_id`
- `created_at`
- `model_key`
- `scene_type`
- `demo_image_id`
- `top_label`
- `top_confidence`
- `detection_count`
- `analysis_title`
- `video_run_tag`
