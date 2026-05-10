from pydantic import BaseModel, Field
from typing import Optional, Literal

class CompletionRequest(BaseModel):
    prompt: str = Field(..., description="The input prompt text")
    session_id: Optional[str] = Field(None, description="Optional session/conversation ID")
    quality_hint: Literal["low", "medium", "high"] = Field("medium", description="Hint to influence routing tier")
    verification_mode: Literal["none", "async", "sync", "dual"] = Field("async", description="Required verification rigor")
