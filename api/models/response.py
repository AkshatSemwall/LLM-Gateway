from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone

class CostBreakdown(BaseModel):
    actual_cost_usd: float
    baseline_cost_usd: float = Field(..., description="Cost if a baseline model (e.g., GPT-4) was used")
    savings_usd: float
    savings_pct: float

class CompletionResponse(BaseModel):
    request_id: str
    output: str
    tier: int
    model_used: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cost_usd: float
    savings_usd: float
    savings_pct: float
    escalated: bool = False
    verified: Optional[bool] = Field(None, description="Null if verification is pending or skipped")
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
