from pydantic import BaseModel, Field
from typing import Optional, Literal
from ..providers.models import ProviderResponse

class VerificationResult(BaseModel):
    score: float = Field(..., ge=0.0, le=10.0)
    reasoning: str
    verdict: Literal["pass", "fail", "skipped"]

class EscalationResult(BaseModel):
    escalated: bool
    new_tier: Optional[int] = Field(None, description="Tier request was escalated to. Null if not escalated.")
    new_response: Optional[ProviderResponse] = Field(None, description="Response from the escalated model. Null if not escalated.")
    escalation_cost_usd: float = Field(0.0)
