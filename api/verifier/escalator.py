import logging
from typing import Optional

from .models import VerificationResult, EscalationResult
from ..providers.models import ProviderResponse
from ..router.config_manager import get_config_manager
from ..verifier.verifier import _get_adapter
from ..cost.engine import compute_cost

logger = logging.getLogger(__name__)

async def escalate(
    request_id: str,
    prompt: str,
    original_tier: int,
    original_response: ProviderResponse,
    verification_result: VerificationResult
) -> EscalationResult:
    """
    Evaluates failed verification outcomes and triggers re-routing securely.
    
    Args:
        request_id: Base original UUID
        prompt: Initial prompt text required to run the new evaluation payload
        original_tier: Origin tier scale 1,2,3
        original_response: Base response parameter
        verification_result: Verdict JSON structure
        
    Returns:
        EscalationResult cleanly blocking max-tier recursion logic.
    """
    
    # 1. Escalate exclusively on confirmed qualitative failure
    if verification_result.verdict != "fail":
        return EscalationResult(
            escalated=False,
            new_tier=None,
            new_response=None,
            escalation_cost_usd=0.0
        )
        
    # 2. Hard constraints: prevent infinite loop recursion bounds
    if original_tier >= 3:
        logger.warning(
            f"[{request_id}] Verification failed at maximum constraint (Tier 3). "
            f"Escalation aborted manually. Marked 'max_tier_failed'."
        )
        return EscalationResult(
            escalated=False,
            new_tier=None,
            new_response=None,
            escalation_cost_usd=0.0
        )
        
    # Standard Step Up Map
    new_tier = original_tier + 1
    escalated_req_id = f"{request_id}_esc_t{new_tier}"
    
    logger.info(f"[{request_id}] Triggering escalation step up to Tier {new_tier}.")
    
    try:
        # Load active routing matrix securely using singleton
        config = get_config_manager().get_routing_table()
        tier_mapping = config.routing.get(f"tier{new_tier}")
        
        if not tier_mapping:
            logger.error(f"[{request_id}] Routing bounds failed. Missing tier{new_tier} in system YAML mapping.")
            return EscalationResult(escalated=False) 
            
        # Target primary model selection mapping (Router logic extension)
        new_model_config = tier_mapping.primary
        
        # Deploy instance securely
        adapter = _get_adapter(new_model_config.provider)
        
        # Await isolated provider stream
        escalated_response = await adapter.send_request(
            prompt=prompt,
            model_config=new_model_config,
            request_id=escalated_req_id
        )
        
        # Log absolute micro-finance mapping cost for delta analytics tracking
        cost_breakdown = compute_cost(
            prompt_tokens=escalated_response.prompt_tokens,
            completion_tokens=escalated_response.completion_tokens,
            model_config=new_model_config
        )
        
        logger.info(f"[{request_id}] Escalation to Tier {new_tier} succeeded. Added overhead: ${cost_breakdown.actual_cost_usd}")

        return EscalationResult(
            escalated=True,
            new_tier=new_tier,
            new_response=escalated_response,
            escalation_cost_usd=cost_breakdown.actual_cost_usd
        )
        
    except Exception as e:
         logger.error(f"[{request_id}] Escalation sequence failed critically: {e}")
         # Soft fail open: fallback cleanly without crashing background queue threads.
         # System merely maintains original response output.
         return EscalationResult(
             escalated=False,
             new_tier=None,
             new_response=None,
             escalation_cost_usd=0.0
         )
