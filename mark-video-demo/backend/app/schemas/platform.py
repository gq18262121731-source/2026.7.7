from pydantic import BaseModel, Field
from typing import Optional


class ModelInfo(BaseModel):
    key: str
    name: str
    scene_type: str
    labels: list[str]
    status: str


class DetectionRequest(BaseModel):
    model_key: str
    sample_key: Optional[str] = None
    source_type: Optional[str] = None
    need_ai_analysis: bool = True
    operator: str = "system_user"


class AssistantRequest(BaseModel):
    message: str
    mode: str = "knowledge_base"
    context: dict = Field(default_factory=dict)


class SettingsPayload(BaseModel):
    assistant_mode: str = "knowledge_base"
    visual_effects: bool = True

