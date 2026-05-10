from pydantic import BaseModel, Field
from typing import Dict, Any, Literal

class ClassificationResult(BaseModel):
    tier: Literal[1, 2, 3] = Field(..., description="Complexity tier: 1 (Simple), 2 (Medium), 3 (Complex)")
    confidence: float = Field(..., ge=0.0, le=1.0)
    features: Dict[str, Any] = Field(default_factory=dict, description="Raw features used for classification, for debugging/analytics")
