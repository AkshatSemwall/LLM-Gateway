import uuid
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import os
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from .models.request import CompletionRequest
from .models.response import CompletionResponse, CostBreakdown
from .router.config_manager import get_config_manager
from .classifier.classifier import classify
from .verifier.verifier import verify, _get_adapter
from .verifier.escalator import escalate
from .cost.engine import compute_cost
from .database.connection import init_db, get_session
from .database.repository import DatabaseRepository
from .providers.base import ProviderUnavailableError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    logger.info("Starting up API Router...")
    await init_db()
    get_config_manager().start_watcher()
    yield
    # Shutdown
    logger.info("Shutting down API Router...")
    await get_config_manager().stop_watcher()

app = FastAPI(title="AI Engineering Router", lifespan=lifespan)

# Setup CORS for production safety
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Configure this in production via env variables
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend build
app.mount("/dashboard", StaticFiles(directory="frontend/dist", html=True), name="frontend")

async def _async_verification_task(
    request_id: str,
    prompt: str,
    tier: int,
    response_text: str,
    db_session: AsyncSession
):
    try:
        repo = DatabaseRepository(db_session)
        config = get_config_manager().get_routing_table()
        
        # Run verification
        ver_result = await verify(prompt, response_text, tier, config.judge_model)
        await repo.insert_verification(request_id, config.judge_model.model_name, ver_result)
        
        # Escalate if needed
        if ver_result.verdict == "fail":
            logger.info(f"[{request_id}] Verification failed asynchronously. Logging escalation.")
            # We don't return the new response to user since this is async, but we can track it
            # To actually get the escalated result we would call escalate
            # For now, async verification just logs the failure and maybe triggers re-processing in a real system
            pass

    except Exception as e:
        logger.error(f"[{request_id}] Async verification task failed: {e}")
    finally:
        await db_session.close()

@app.get("/health")
async def health_check():
    """Production health check endpoint for Kubernetes / Docker / Load Balancers."""
    return {"status": "healthy", "version": "1.0.0"}

@app.post("/v1/completions", response_model=CompletionResponse)
async def create_completion(
    request: CompletionRequest,
    background_tasks: BackgroundTasks,
    db_session: AsyncSession = Depends(get_session)
):
    req_id = f"req_{uuid.uuid4().hex[:12]}"
    repo = DatabaseRepository(db_session)
    config_manager = get_config_manager()
    routing_table = config_manager.get_routing_table()

    # 1. Classification
    class_result = classify(request.prompt)
    target_tier = class_result.tier
    
    # Optional override based on quality_hint
    if request.quality_hint == "low":
        target_tier = 1
    elif request.quality_hint == "high":
        target_tier = 3

    # 2. Routing
    tier_config = routing_table.routing.get(f"tier{target_tier}")
    if not tier_config:
        raise HTTPException(status_code=500, detail="Invalid routing tier configuration")

    model_config = tier_config.primary
    
    # Pre-create tracking record
    await repo.create_request(
        request_id=req_id,
        session_id=request.session_id,
        prompt_hash=str(hash(request.prompt)), # Simple hash for demo
        prompt_length=len(request.prompt),
        tier=target_tier,
        model_used=model_config.model_name,
        provider=model_config.provider
    )

    # 3. Execution
    try:
        adapter = _get_adapter(model_config.provider)
        response = await adapter.send_request(request.prompt, model_config, req_id)
    except ProviderUnavailableError as e:
        # Here we could implement fallback logic to tier_config.fallback
        logger.error(f"[{req_id}] Primary provider failed: {e}")
        raise HTTPException(status_code=503, detail="Provider unavailable")

    # 4. Cost tracking
    cost_data = compute_cost(response.prompt_tokens, response.completion_tokens, model_config)

    # 5. Verification & Escalation (Sync)
    escalated = False
    verified_status = None
    final_response_text = response.text
    final_model = model_config.model_name
    final_provider = model_config.provider
    final_tier = target_tier
    
    if request.verification_mode == "sync" or request.verification_mode == "dual":
        ver_result = await verify(request.prompt, response.text, target_tier, routing_table.judge_model)
        await repo.insert_verification(req_id, routing_table.judge_model.model_name, ver_result)
        
        verified_status = (ver_result.verdict == "pass")

        if ver_result.verdict == "fail":
            esc_result = await escalate(req_id, request.prompt, target_tier, response, ver_result)
            if esc_result.escalated and esc_result.new_response:
                escalated = True
                final_response_text = esc_result.new_response.text
                final_tier = esc_result.new_tier or target_tier
                
                # We should really grab the actual escalated model/provider, but simplified here
                esc_model_config = routing_table.routing.get(f"tier{final_tier}").primary
                final_model = esc_model_config.model_name
                final_provider = esc_model_config.provider
                
                # Update cost
                esc_cost_data = compute_cost(esc_result.new_response.prompt_tokens, esc_result.new_response.completion_tokens, esc_model_config)
                cost_data.actual_cost_usd += esc_cost_data.actual_cost_usd
                
                await repo.insert_escalation(
                    req_id, target_tier, final_tier, model_config.model_name, final_model, esc_cost_data.actual_cost_usd
                )
    elif request.verification_mode == "async":
        # Launch background verification
        # We need a new session since the current one is tied to the request lifecycle
        from .database.connection import AsyncSessionFactory
        bg_session = AsyncSessionFactory()
        background_tasks.add_task(
            _async_verification_task, req_id, request.prompt, target_tier, response.text, bg_session
        )

    # Update final record
    await repo.update_request(req_id, response, cost_data)

    return CompletionResponse(
        request_id=req_id,
        output=final_response_text,
        tier=final_tier,
        model_used=final_model,
        provider=final_provider,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        latency_ms=response.latency_ms,
        cost_usd=cost_data.actual_cost_usd,
        savings_usd=cost_data.savings_usd,
        savings_pct=cost_data.savings_pct,
        escalated=escalated,
        verified=verified_status
    )
