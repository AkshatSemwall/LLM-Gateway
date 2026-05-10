import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .models import RequestRecord, VerificationRecord, EscalationRecord
from ..models.response import CostBreakdown
from ..providers.models import ProviderResponse
from ..verifier.models import VerificationResult, EscalationResult

logger = logging.getLogger(__name__)

class DatabaseRepository:
    """Async wrapper grouping execution CRUD logic against the schema."""
    
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_request(
        self, request_id: str, session_id: str | None, prompt_hash: str, 
        prompt_length: int, tier: int, model_used: str, provider: str
    ) -> RequestRecord:
        """Instantiates the pending tracking instance synchronously as the HTTP request enters."""
        try:
            record = RequestRecord(
                request_id=request_id,
                session_id=session_id,
                prompt_hash=prompt_hash,
                prompt_length=prompt_length,
                tier=tier,
                model_used=model_used,
                provider=provider,
                status='pending'
            )
            self.session.add(record)
            await self.session.commit()
            return record
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create RequestRecord {request_id}: {e}")
            raise

    async def update_request(
        self, request_id: str, provider_response: ProviderResponse, 
        cost: CostBreakdown, status: str = 'complete'
    ) -> None:
        """Updates trailing state with provider latency outputs matching original UUID."""
        try:
            stmt = select(RequestRecord).where(RequestRecord.request_id == request_id)
            result = await self.session.execute(stmt)
            record = result.scalar_one_or_none()
            
            if record:
                record.prompt_tokens = provider_response.prompt_tokens
                record.completion_tokens = provider_response.completion_tokens
                record.latency_ms = provider_response.latency_ms
                record.cost_usd = cost.actual_cost_usd
                record.baseline_cost_usd = cost.baseline_cost_usd
                record.savings_usd = cost.savings_usd
                record.status = status
                
                # Assign completed ISO marker
                from datetime import datetime, timezone
                record.completed_at = datetime.now(timezone.utc).isoformat()
                
                await self.session.commit()
            else:
                logger.warning(f"Attempted to update non-existent RequestRecord: {request_id}")
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update RequestRecord {request_id}: {e}")

    async def insert_verification(
        self, request_id: str, judge_model: str, result: VerificationResult, escalated: bool = False
    ) -> VerificationRecord:
        """Pushes background async validation telemetry into relational tie."""
        try:
            ver_id = f"ver_{uuid.uuid4().hex[:12]}"
            record = VerificationRecord(
                verification_id=ver_id,
                request_id=request_id,
                judge_model=judge_model,
                quality_score=result.score,
                reasoning=result.reasoning,
                verdict=result.verdict,
                escalation_triggered=escalated
            )
            self.session.add(record)
            await self.session.commit()
            return record
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to insert VerificationRecord for {request_id}: {e}")
            raise

    async def insert_escalation(
        self, request_id: str, original_tier: int, escalated_tier: int, 
        original_model: str, escalated_model: str, cost: float
    ) -> EscalationRecord:
        """Marks tracking block linking boundary violations directly backward to initial prompt stream."""
        try:
            esc_id = f"esc_{uuid.uuid4().hex[:12]}"
            record = EscalationRecord(
                escalation_id=esc_id,
                request_id=request_id,
                original_tier=original_tier,
                escalated_tier=escalated_tier,
                original_model=original_model,
                escalated_model=escalated_model,
                escalation_cost_usd=cost
            )
            self.session.add(record)
            
            # Tag the core request mapping immediately to alert front-end dashboard mappings
            stmt = select(RequestRecord).where(RequestRecord.request_id == request_id)
            req_result = await self.session.execute(stmt)
            req_record = req_result.scalar_one_or_none()
            if req_record:
                req_record.escalated = True
                
            await self.session.commit()
            return record
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to insert EscalationRecord for {request_id}: {e}")
            raise
