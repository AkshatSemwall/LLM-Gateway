import os
import time
import httpx
import logging
from typing import Dict, Any

from ..router.models import ModelConfig
from .models import ProviderResponse, HealthStatus
from .base import BaseProvider, ProviderUnavailableError

logger = logging.getLogger(__name__)

class OllamaAdapter(BaseProvider):
    """
    Adapter for local Ollama HTTP API.
    Handles inference, local timeout bounding, and cost voiding (local compute).
    """

    def __init__(self, base_url: str = None):
        super().__init__()
        base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.base_url = base_url.rstrip("/")
        self.api_generate_url = f"{self.base_url}/api/generate"
        self.api_version_url = f"{self.base_url}/api/version"

    async def _execute_request(self, prompt: str, model_config: ModelConfig, request_id: str) -> ProviderResponse:
        payload = {
            "model": model_config.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": model_config.temperature,
                # Ollama uses num_predict instead of max_tokens in some versions, but 
                # num_predict is the safe standard in the options block.
                "num_predict": model_config.max_tokens
            }
        }

        start_time = time.perf_counter()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_generate_url, 
                    json=payload, 
                    timeout=model_config.timeout_seconds
                )
        except httpx.ConnectError as e:
             # If Ollama daemon is offline, it's a permanent failure for this router attempt
             raise ProviderUnavailableError(f"Failed to connect to local Ollama daemon: {e}")

        # Check for model not found (404) immediately
        if response.status_code == 404:
             raise ProviderUnavailableError(f"Ollama model '{model_config.model_name}' not pulled locally.")
             
        response.raise_for_status()

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        data = response.json()
        
        text_output = data.get("response", "")
        # Ollama provides eval_count for output and prompt_eval_count for input tokens
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        return ProviderResponse(
            text=text_output,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            raw_metadata=data
        )

    def estimate_cost(self, tokens_in: int, tokens_out: int, model_config: ModelConfig) -> float:
        """
        Ollama is local, so the API token cost is entirely overridden to $0 regardless of schema.
        Compute costs (electricity, hardware depreciation) are outside the scope.
        """
        return 0.0

    async def _check_health(self) -> HealthStatus:
        """Checks if the Ollama daemon is live and listening."""
        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient() as client:
                # 2 second strict timeout for daemon healthcheck
                response = await client.get(self.api_version_url, timeout=2.0)
                
            response.raise_for_status()
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            
            return HealthStatus(
                provider="ollama",
                status="healthy",
                error_rate_1h=0.0,
                avg_latency_ms=latency_ms
            )
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return HealthStatus(
                provider="ollama",
                status="down",
                error_rate_1h=1.0,
                avg_latency_ms=0.0
            )
