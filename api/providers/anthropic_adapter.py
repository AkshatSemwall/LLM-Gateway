import os
import time
import httpx
import logging
from typing import Dict, Any

from ..router.models import ModelConfig
from .models import ProviderResponse, HealthStatus
from .base import BaseProvider, ProviderUnavailableError

logger = logging.getLogger(__name__)

class AnthropicAdapter(BaseProvider):
    """
    Adapter for Anthropic's Messages API.
    Handles API key management, payload mapping, and error translation.
    """

    def __init__(self):
        super().__init__()
        self.api_url = os.environ.get("ANTHROPIC_API_URL", "https://api.anthropic.com/v1/messages")
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    async def _execute_request(self, prompt: str, model_config: ModelConfig, request_id: str) -> ProviderResponse:
        if not self.api_key:
            raise ProviderUnavailableError("ANTHROPIC_API_KEY environment variable is not set.")

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        # System/User role mapping (Assuming no complex history context for base prompt)
        payload = {
            "model": model_config.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": model_config.max_tokens,
            "temperature": model_config.temperature
        }

        # Start timer for latency
        start_time = time.perf_counter()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.api_url, 
                headers=headers, 
                json=payload, 
                timeout=model_config.timeout_seconds
            )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if response.status_code in [401, 403]:
            # Permanent Auth Errors
            raise ProviderUnavailableError(f"Anthropic Auth Error ({response.status_code}): {response.text}")
        
        # Raise for other HTTP errors (5xx, 429) to trigger retries in base class
        response.raise_for_status()

        data = response.json()
        
        # Extract completions and tokens
        text_output = "".join([block["text"] for block in data.get("content", []) if block["type"] == "text"])
        usage = data.get("usage", {})
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)

        return ProviderResponse(
            text=text_output,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            raw_metadata=data
        )

    async def _check_health(self) -> HealthStatus:
        if not self.api_key:
            return HealthStatus(
                provider="anthropic",
                status="degraded",
                error_rate_1h=1.0,
                avg_latency_ms=0.0
            )
            
        # Ping a lightweight endpoint or send a minimal request if status API is not available
        # Anthropic doesn't have a canonical /health endpoint for API users, so we can make a dummy rejected call or assume healthy
        # Here we mock a generic healthy response since checking requires burning tokens normally, 
        # but in prod we'd measure 5xx rates over the last hour.
        
        return HealthStatus(
            provider="anthropic",
            status="healthy",
            error_rate_1h=0.0,
            avg_latency_ms=250.0  # Placeholder average
        )
