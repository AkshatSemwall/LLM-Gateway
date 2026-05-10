from pydantic import BaseModel, Field
from typing import Dict, Any, Literal
from datetime import datetime, timezone

class ProviderResponse(BaseModel):
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    raw_metadata: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific raw response for telemetry")

class HealthStatus(BaseModel):
    provider: Literal["openai", "anthropic", "ollama"]
    status: Literal["healthy", "degraded", "down"]
    last_check_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error_rate_1h: float
    avg_latency_ms: float
