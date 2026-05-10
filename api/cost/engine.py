import logging
from ..router.models import ModelConfig
from ..models.response import CostBreakdown

logger = logging.getLogger(__name__)

# System default baseline: GPT-4o ($2.50 / 1M input, $10.00 / 1M output)
# Equivalent to $0.0025 / 1K input, $0.01 / 1K output
BASELINE_COST_PER_1K_INPUT = 0.0025
BASELINE_COST_PER_1K_OUTPUT = 0.01

def compute_cost(prompt_tokens: int, completion_tokens: int, model_config: ModelConfig) -> CostBreakdown:
    """
    Computes absolute cost using the router config parameters, and calculates 
    the overall system savings against a GPT-4o control baseline.
    
    Args:
        prompt_tokens: Number of tokens in input
        completion_tokens: Number of tokens generated
        model_config: The routing configuration of the utilized model
        
    Returns:
        CostBreakdown with precision rounding.
    """
    try:
        # Prevent negative token anomalies scaling wildly
        p_tokens = max(0, prompt_tokens)
        c_tokens = max(0, completion_tokens)
        
        # Determine strict Actual Route Cost
        # (Ollama compute forces $0.00 USD inherently)
        if model_config.provider == "ollama":
            actual_cost_usd = 0.0
        else:
            in_cost = (p_tokens / 1000.0) * model_config.cost_per_1k_input
            out_cost = (c_tokens / 1000.0) * model_config.cost_per_1k_output
            actual_cost_usd = in_cost + out_cost
            
        # Determine Baseline Engine Cost (if user had defaulted everything to standard expensive GPT-4o)
        base_in_cost = (p_tokens / 1000.0) * BASELINE_COST_PER_1K_INPUT
        base_out_cost = (c_tokens / 1000.0) * BASELINE_COST_PER_1K_OUTPUT
        baseline_cost_usd = base_in_cost + base_out_cost
        
        # Net savings calculation
        savings_usd = max(0.0, baseline_cost_usd - actual_cost_usd)
        
        if baseline_cost_usd > 0.0:
            savings_pct = (savings_usd / baseline_cost_usd) * 100.0
        else:
            savings_pct = 0.0
            
        # Return properly rounded analytics metadata
        return CostBreakdown(
            actual_cost_usd=round(actual_cost_usd, 6),
            baseline_cost_usd=round(baseline_cost_usd, 6),
            savings_usd=round(savings_usd, 6),
            savings_pct=round(savings_pct, 2)
        )

    except Exception as e:
        logger.error(f"Cost engine calculation fault: {e}")
        # Failsafe cleanly back to 0.0 metrics rather than nuking the client endpoint stream
        return CostBreakdown(
            actual_cost_usd=0.0,
            baseline_cost_usd=0.0,
            savings_usd=0.0,
            savings_pct=0.0
        )
