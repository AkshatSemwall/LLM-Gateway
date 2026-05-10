import json
import logging
import uuid
from typing import Dict, Any, Type
import re

from ..router.models import ModelConfig
from .models import VerificationResult
from ..providers.base import BaseProvider, ProviderUnavailableError

logger = logging.getLogger(__name__)

# Defaults based on architecture thresholds
DEFAULT_THRESHOLDS = {
    1: 6.5,
    2: 7.0,
    3: 8.0
}

# Dynamic adapter cache to prevent recreating httpx clients unnecessarily
_adapter_cache: Dict[str, BaseProvider] = {}

def _get_adapter(provider_name: str) -> BaseProvider:
    """Dynamically instantiates provider adapters based on string routing."""
    if provider_name in _adapter_cache:
        return _adapter_cache[provider_name]
        
    if provider_name == "openai":
         # Assume OpenAIAdapter exists natively alongside Anthropic/Ollama
         from ..providers.openai_adapter import OpenAIAdapter
         adapter = OpenAIAdapter()
    elif provider_name == "anthropic":
         from ..providers.anthropic_adapter import AnthropicAdapter
         adapter = AnthropicAdapter()
    elif provider_name == "ollama":
         from ..providers.ollama_adapter import OllamaAdapter
         adapter = OllamaAdapter()
    else:
         raise ValueError(f"Unknown provider '{provider_name}'")
         
    _adapter_cache[provider_name] = adapter
    return adapter

def _build_judge_prompt(prompt: str, response_text: str, tier: int) -> str:
    """Builds the strict evaluation instruction set mapping to JSON."""
    return f"""SYSTEM: You are an objective quality evaluator. Score responses 1-10.

USER:
[ORIGINAL PROMPT]:
{prompt}

[MODEL RESPONSE]:
{response_text}

Evaluate on:
- Accuracy & factual correctness
- Completeness (does it answer the question?)
- Clarity and coherence
- Appropriateness for complexity level (tier {tier})

Return ONLY JSON: {{"score": <float>, "reasoning": "<1-2 sentences>"}}
"""

def extract_json_block(text: str) -> str:
    """Locates and unwraps JSON payload if the LLM output markdown quotes."""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
         return match.group(0)
    return text

async def verify(
    prompt: str, 
    response_text: str, 
    tier: int, 
    judge_model_config: ModelConfig,
    threshold: float | None = None
) -> VerificationResult:
    """
    Executes an LLM-as-a-judge payload against the given output.
    Returns skipped gracefully upon timeout or un-parsable error.
    """
    
    if threshold is None:
        threshold = DEFAULT_THRESHOLDS.get(tier, 7.0)
        
    judge_prompt = _build_judge_prompt(prompt, response_text, tier)
    req_id = f"verify_{uuid.uuid4().hex[:8]}"
    
    try:
        adapter = _get_adapter(judge_model_config.provider)
        
        # Fire request to provider using the BaseProvider retry/backoff constraints
        judge_response = await adapter.send_request(
            prompt=judge_prompt,
            model_config=judge_model_config,
            request_id=req_id
        )
        
    except ProviderUnavailableError as e:
        logger.warning(f"[Verification {req_id}] Judge provider offline/failed: {e}")
        return VerificationResult(
             score=0.0,
             reasoning="Judge API failed.",
             verdict="skipped"
        )
    except Exception as e:
        logger.error(f"[Verification {req_id}] Internal judge failure: {e}")
        return VerificationResult(
             score=0.0,
             reasoning="Internal evaluation fault.",
             verdict="skipped"
        )
        
    # Attempt parsing response -> Score mapping
    raw_text = extract_json_block(judge_response.text)
    
    try:
        data = json.loads(raw_text)
        score = float(data.get("score", 0.0))
        reasoning = str(data.get("reasoning", "No context provided by judge."))
        
        # Clamp bounds defensively
        score = max(0.0, min(10.0, score))
        
        verdict = "pass" if score >= threshold else "fail"
        
        return VerificationResult(
            score=score,
            reasoning=reasoning,
            verdict=verdict # type: ignore
        )
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"[Verification {req_id}] Malformed judge JSON output: {raw_text}. Error: {e}")
        # Could not extract -> skip verification and do not trigger infinite escalation recursion
        return VerificationResult(
             score=0.0,
             reasoning="Judge returned malformed JSON mapping.",
             verdict="skipped"
        )
