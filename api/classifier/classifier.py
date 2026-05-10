import logging
import re
from typing import Dict, Any, Optional, Literal

from .models import ClassificationResult
from .rules import extract_features

logger = logging.getLogger(__name__)

def classify(prompt: str, context: Optional[Dict[str, Any]] = None) -> ClassificationResult:
    """
    Classifies a prompt into complexity tier 1, 2, or 3.
    Uses rule-based heuristics for fast (<50ms) execution.
    
    Args:
        prompt: The user's input text.
        context: Optional context dictionary (e.g., session history length).
        
    Returns:
        ClassificationResult containing the tier, confidence, and raw features.
    """
    try:
        if not prompt or prompt.isspace():
            # Edge case: empty or whitespace-only prompt
            return ClassificationResult(
                tier=1,
                confidence=1.0,
                features={"error": "empty_prompt"}
            )
            
        features = extract_features(prompt)
        
        # 1. Base scoring mechanism
        score = 0.0
        
        # Length contributions (longer -> more complex)
        if features["word_count"] > 200:
            score += 2.0
        elif features["word_count"] > 50:
            score += 1.0
            
        # Code presence (usually indicates at least tier 2, often tier 3 if complex)
        if features["has_code_block"]:
            score += 3.0
            # If it's a long code block, maybe tier 3
            if features["num_newlines"] > 10:
                score += 1.0
        elif features["has_inline_code"] or features["has_code_keywords"]:
            score += 1.5
            
        # Intent/Domain keywords
        if features["tier3_keywords_count"] > 0:
            score += 3.0 * features["tier3_keywords_count"]
        
        if features["tier2_keywords_count"] > 0:
            score += 1.5 * features["tier2_keywords_count"]
            
        # URL presence (summarization or web scraping tasks)
        if features["has_url"]:
            score += 1.0
            
        # Context modifiers (if available)
        if context:
            # If conversation history is long, tasks tend to get complex
            history_length = context.get("history_length", 0)
            if history_length > 5:
                score += 1.0

        # 3. Map score to tier
        tier: Literal[1, 2, 3] = 1
        confidence = 0.7 # Base confidence for rule-based
        
        if score >= 5.0:
            tier = 3
            # If extremely high score it's strongly tier 3
            confidence = min(0.95, 0.7 + (score - 5.0) * 0.05)
        elif score >= 2.0:
            tier = 2
            confidence = 0.8
        else:
            tier = 1
            confidence = 0.8
            
        # 4. Edge Cases and Overrides
        
        # Override: Very short prompt but has heavy keywords (mb ambiguous)
        if features["word_count"] < 10 and tier == 3:
            # Too short to be truly tier 3, but keywords triggered it
             tier = 2
             confidence = 0.6
        # Override: Very short prompt with no code/hard keywords is Tier 1
        elif features["word_count"] < 10 and score < 2.0:
             tier = 1
             confidence = 0.9
             
        # Max feature rule: If it has intense Tier 3 markers but scored low, err on safety
        if features["tier3_keywords_count"] >= 2 and tier == 1:
             tier = 2
             confidence = 0.6

        return ClassificationResult(
            tier=tier,
            confidence=confidence,
            features=features
        )

    except Exception as e:
        logger.exception(f"Error during classification: {e}")
        # Failure case: Fail open to Tier 2 (safe middle ground)
        return ClassificationResult(
            tier=2,
            confidence=0.1,
            features={"error": str(e)}
        )
