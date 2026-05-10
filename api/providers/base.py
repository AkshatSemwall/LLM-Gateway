from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Optional, Tuple
from ..router.models import ModelConfig
from .models import ProviderResponse, HealthStatus

logger = logging.getLogger(__name__)

class ProviderUnavailableError(Exception):
    """Raised when the provider is down, auth fails permanently, or retries are exhausted."""
    pass

class BaseProvider(ABC):
    """
    Abstract base class for LLM providers (OpenAI, Anthropic, Ollama, etc.).
    Implementations must define the `_execute_request` and `_check_health` logic.
    """

    def __init__(self):
        self.max_retries = 3
        self.base_backoff_seconds = 1.0

    @abstractmethod
    async def _execute_request(self, prompt: str, model_config: ModelConfig, request_id: str) -> ProviderResponse:
        """
        Implementation-specific logic to call the provider API.
        Must handle its own specific timeout/network timeouts returning cleanly if possible
        or raising HTTP status related exceptions that `send_request` can catch for retries.
        """
        pass

    @abstractmethod
    async def _check_health(self) -> HealthStatus:
        """
        Implementation-specific logic to ping the provider and assert it is up.
        """
        pass

    async def send_request(self, prompt: str, model_config: ModelConfig, request_id: str) -> ProviderResponse:
        """
        Resilient wrapper around `_execute_request` to enforce structured backoff, 
        timeout bounds, and extensive logging per architecture specification.
        """
        attempt = 0
        
        while attempt <= self.max_retries:
            try:
                # Wrap the underlying concrete call with an asyncio timeout
                # the architecture defaults to 30s but we take from model_config
                timeout_limit = model_config.timeout_seconds
                
                logger.debug(f"[Request {request_id}] Calling provider {model_config.provider} (attempt {attempt + 1}/{self.max_retries+1})")
                
                response = await asyncio.wait_for(
                    self._execute_request(prompt, model_config, request_id),
                    timeout=timeout_limit
                )
                
                logger.info(f"[Request {request_id}] Provider {model_config.provider} successful. Latency: {response.latency_ms}ms")
                return response
                
            except asyncio.TimeoutError:
                logger.warning(f"[Request {request_id}] Provider {model_config.provider} timed out after {timeout_limit}s.")
                # We want to retry timeouts
                
            except ProviderUnavailableError as e:
                # E.g. permanent 401 Auth error thrown by concrete implementation
                logger.error(f"[Request {request_id}] Provider {model_config.provider} reported permanent failure: {e}")
                raise
                
            except Exception as e:
                 logger.warning(f"[Request {request_id}] Provider {model_config.provider} encountered transient error: {e}")
                 # Other exceptions (5xx, rate limits) fall through to retry
                 
            # If we haven't returned or raised `ProviderUnavailableError` yet, and we haven't hit the limit, retry
            if attempt < self.max_retries:
                # Exponential backoff
                sleep_time = self.base_backoff_seconds * (2 ** attempt)
                # Adds a little bit of jitter
                import random
                jitter = random.uniform(0.1, 0.5)
                
                logger.info(f"[Request {request_id}] Retrying {model_config.provider} in {sleep_time + jitter:.2f}s...")
                await asyncio.sleep(sleep_time + jitter)
            
            attempt += 1

        logger.error(f"[Request {request_id}] Exhausted all {self.max_retries} retries for provider {model_config.provider}.")
        raise ProviderUnavailableError(f"Failed to communicate with {model_config.provider} after {self.max_retries} retries.")

    def estimate_cost(self, tokens_in: int, tokens_out: int, model_config: ModelConfig) -> float:
        """
        Calculates the estimated cost in USD based on input/output token counts
        and the rates specified in the ModelConfig.
        """
        # Costs are usually declared per 1000 tokens
        input_cost = (tokens_in / 1000.0) * model_config.cost_per_1k_input
        output_cost = (tokens_out / 1000.0) * model_config.cost_per_1k_output
        return input_cost + output_cost

    async def health_check(self) -> HealthStatus:
        """
        Wrapper around provider-specific health checks. Assures it never crashes the application loop.
        """
        try:
             # Fast timeout for health checks
             return await asyncio.wait_for(self._check_health(), timeout=5.0)
        except asyncio.TimeoutError:
             return HealthStatus(
                 provider=self.__class__.__name__.replace("Adapter", "").lower(), # e.g. "openai" # type: ignore
                 status="down",
                 error_rate_1h=0.0,
                 avg_latency_ms=5000.0
             )
        except Exception as e:
             logger.error(f"Health check failed for {self.__class__.__name__}: {e}")
             return HealthStatus(
                 provider=self.__class__.__name__.replace("Adapter", "").lower(), # type: ignore
                 status="degraded",
                 error_rate_1h=0.0,
                 avg_latency_ms=0.0
             )
