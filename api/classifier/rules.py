import re
from typing import Dict, Any

# Pre-compile regex for performance (< 50ms requirement)
CODE_BLOCK_RE = re.compile(r"```.*?\n.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`]+`")
URL_RE = re.compile(r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+")

# Keywords indicating higher complexity or specific domains
COMPLEXITY_KEYWORDS_TIER2 = {
    "analyze", "compare", "explain", "summarize", "describe",
    "difference between", "how does", "why is"
}

COMPLEXITY_KEYWORDS_TIER3 = {
    "prove", "theorem", "legal", "clause", "contract", "medical",
    "diagnosis", "symptoms", "architecture", "system design", "refactor",
    "optimize", "vulnerability", "security"
}

def extract_features(prompt: str) -> Dict[str, Any]:
    """
    Extracts features from the prompt efficiently using rules.
    Designed to run in < 10ms.
    """
    features: Dict[str, Any] = {}
    
    # 1. Length features
    features["char_length"] = len(prompt)
    
    # Fast proxy for token count (split by whitespace)
    words = prompt.split()
    features["word_count"] = len(words)
    
    prompt_lower = prompt.lower()
    
    # 2. Code presence
    code_blocks = CODE_BLOCK_RE.findall(prompt)
    features["has_code_block"] = len(code_blocks) > 0
    
    features["has_inline_code"] = bool(INLINE_CODE_RE.search(prompt))
    
    # Count typical code keywords that might not be in blocks
    code_keywords = ["def ", "class ", "function(", "import ", "extends ", "public static"]
    features["has_code_keywords"] = any(kw in prompt for kw in code_keywords) # Note: case-sensitive search for these
    
    # 3. Keyword/Intent flags
    features["has_url"] = bool(URL_RE.search(prompt))
    
    # Check for complexity keywords
    features["tier2_keywords_count"] = sum(1 for kw in COMPLEXITY_KEYWORDS_TIER2 if kw in prompt_lower)
    features["tier3_keywords_count"] = sum(1 for kw in COMPLEXITY_KEYWORDS_TIER3 if kw in prompt_lower)
    
    # 4. Sentence structure proxy
    features["question_marks"] = prompt.count("?")
    
    # Nested clauses proxy (crude but fast)
    features["num_commas"] = prompt.count(",")
    features["num_newlines"] = prompt.count("\n")
    
    return features
