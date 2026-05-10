from pydantic import BaseModel, Field
from typing import List, Literal, Dict

class ModelConfig(BaseModel):
    provider: Literal["openai", "anthropic", "ollama"]
    model_name: str
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(2048, gt=0)
    cost_per_1k_input: float = Field(..., ge=0.0)
    cost_per_1k_output: float = Field(..., ge=0.0)
    timeout_seconds: int = Field(30, gt=0)
    fallback_models: List[str] = Field(default_factory=list)

class TierModels(BaseModel):
    primary: ModelConfig
    fallback: List[ModelConfig] = Field(default_factory=list)

class QualityThresholds(BaseModel):
    tier1: float = Field(6.5, ge=0.0, le=10.0)
    tier2: float = Field(7.0, ge=0.0, le=10.0)
    tier3: float = Field(8.0, ge=0.0, le=10.0)

class RoutingTable(BaseModel):
    routing: Dict[str, TierModels]
    quality_thresholds: QualityThresholds
    judge_model: ModelConfig
