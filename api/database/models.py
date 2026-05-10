from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, Index
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone

Base = declarative_base()

class RequestRecord(Base):
    __tablename__ = 'requests'
    
    request_id = Column(String, primary_key=True) # UUID
    session_id = Column(String, nullable=True)
    prompt_hash = Column(String, nullable=False)  # SHA-256
    prompt_length = Column(Integer, nullable=False)
    tier = Column(Integer, nullable=False)        # 1|2|3
    model_used = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)
    cost_usd = Column(Float, nullable=True)
    baseline_cost_usd = Column(Float, nullable=True)
    savings_usd = Column(Float, nullable=True)
    escalated = Column(Boolean, default=False)
    status = Column(String, default='pending')    # pending|complete|failed
    created_at = Column(String, nullable=False, default=lambda: datetime.now(timezone.utc).isoformat())
    completed_at = Column(String, nullable=True)
    
    # Relationships for query access
    verifications = relationship('VerificationRecord', back_populates='request')
    escalations = relationship('EscalationRecord', back_populates='request')

Index('idx_requests_created_at', RequestRecord.created_at)
Index('idx_requests_tier', RequestRecord.tier)
Index('idx_requests_model', RequestRecord.model_used)
Index('idx_requests_session', RequestRecord.session_id)


class VerificationRecord(Base):
    __tablename__ = 'verifications'
    
    verification_id = Column(String, primary_key=True) # UUID
    request_id = Column(String, ForeignKey('requests.request_id'), nullable=False)
    judge_model = Column(String, nullable=False)
    quality_score = Column(Float, nullable=True) # 0.0 - 10.0
    reasoning = Column(String, nullable=True)
    verdict = Column(String, nullable=True) # pass|fail|skipped
    escalation_triggered = Column(Boolean, default=False)
    created_at = Column(String, nullable=False, default=lambda: datetime.now(timezone.utc).isoformat())
    
    request = relationship('RequestRecord', back_populates='verifications')

Index('idx_verifications_request', VerificationRecord.request_id)
Index('idx_verifications_verdict', VerificationRecord.verdict)


class EscalationRecord(Base):
    __tablename__ = 'escalations'
    
    escalation_id = Column(String, primary_key=True)
    request_id = Column(String, ForeignKey('requests.request_id'), nullable=False)
    original_tier = Column(Integer, nullable=False)
    escalated_tier = Column(Integer, nullable=False)
    original_model = Column(String, nullable=False)
    escalated_model = Column(String, nullable=False)
    escalation_cost_usd = Column(Float, nullable=True)
    created_at = Column(String, nullable=False, default=lambda: datetime.now(timezone.utc).isoformat())
    
    request = relationship('RequestRecord', back_populates='escalations')

Index('idx_escalations_request', EscalationRecord.request_id)


class RoutingConfigRecord(Base):
    __tablename__ = 'routing_config'
    
    config_id = Column(String, primary_key=True)
    tier = Column(Integer, nullable=False)
    provider = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2048)
    cost_per_1k_input = Column(Float, nullable=False)
    cost_per_1k_output = Column(Float, nullable=False)
    priority = Column(Integer, default=1)
    enabled = Column(Boolean, default=True)
    updated_at = Column(String, nullable=False, default=lambda: datetime.now(timezone.utc).isoformat())

Index('idx_routing_tier_priority', RoutingConfigRecord.tier, RoutingConfigRecord.priority, unique=True)


class ProviderHealthRecord(Base):
    __tablename__ = 'provider_health'
    
    provider = Column(String, primary_key=True)
    status = Column(String, default='healthy')
    last_check_utc = Column(String, nullable=True)
    error_rate_1h = Column(Float, nullable=True)
    avg_latency_ms = Column(Float, nullable=True)
    updated_at = Column(String, nullable=False, default=lambda: datetime.now(timezone.utc).isoformat())
