import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RunDetectionRequest(BaseModel):
    window_days: int = 30


class DetectionSummary(BaseModel):
    detection_run_id: uuid.UUID
    status: str
    counts: dict[str, int]
    total_at_risk_usd: float
    detection_count: int

    model_config = ConfigDict(from_attributes=True)


class DetectionItem(BaseModel):
    id: uuid.UUID
    rule_name: str
    severity: str
    subject_type: str
    subject_id: uuid.UUID
    amount_usd: Optional[float]
    days_outstanding: Optional[int]
    recommended_action: str

    model_config = ConfigDict(from_attributes=True)


class DetectionRunDetail(BaseModel):
    id: uuid.UUID
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    rule_count: int
    detection_count: int
    detections: dict[str, list[DetectionItem]]  # grouped by rule_name

    model_config = ConfigDict(from_attributes=True)
