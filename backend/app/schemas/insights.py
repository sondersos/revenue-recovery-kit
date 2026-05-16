import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class GenerateInsightRequest(BaseModel):
    detection_run_id: uuid.UUID


class InsightResponse(BaseModel):
    id: uuid.UUID
    detection_run_id: uuid.UUID
    organization_id: uuid.UUID
    summary_text: str
    model: str
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    cost_usd: Optional[Decimal]
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CostSummary(BaseModel):
    total_cost_usd: float
    generation_count: int
    avg_cost_usd: float
    since: datetime | None
    by_model: dict[str, float]
