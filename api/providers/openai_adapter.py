import os
import time
import httpx
import logging
from typing import Dict, Any

from ..router.models import ModelConfig
from .models import ProviderResponse, HealthStatus
from .base import BaseProvider, ProviderUnavailableError

logger = logging.getLogger(__name__)

class OpenAIAdapter(BaseProvider):
    """
    Adapter for OpenAI's Chat Completions API.
    Handles API key management, payload mapping, and error translation.
    """

    def __init__(self):
        super().__init__()
        self.api_url = os.environ.get("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
        self.api_key = os.environ.get("OPENAI_API_KEY", "")

    async def _execute_request(self, prompt: str, model_config: ModelConfig, request_id: str) -> ProviderResponse:
        if not self.api_key:
            raise ProviderUnavailableError("OPENAI_API_KEY environment variable is not set.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model_config.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": model_config.max_tokens,
            "temperature": model_config.temperature
        }

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
            raise ProviderUnavailableError(f"OpenAI Auth Error ({response.status_code}): {response.text}")
        
        response.raise_for_status()

        data = response.json()
        
        text_output = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

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
                provider="openai",
                status="degraded",
                error_rate_1h=1.0,
                avg_latency_ms=0.0
            )
            
        return HealthStatus(
            provider="openai",
            status="healthy",
            error_rate_1h=0.0,
            avg_latency_ms=150.0
        )
