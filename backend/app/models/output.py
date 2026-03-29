"""GoatRaw - Output and AgentLog ORM Models"""
from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from app.core.database import Base


class Output(Base):
    __tablename__ = "outputs"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id    = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    summary    = Column(Text)
    data       = Column(JSONB, default={})
    trace      = Column(JSONB, default={})
    status     = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id     = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    step_number = Column(Integer)
    log_type    = Column(String(50))   # plan|tool_call|tool_result|thought|output
    content     = Column(JSONB)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


class ApiUsage(Base):
    __tablename__ = "api_usage"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    endpoint    = Column(String(255))
    method      = Column(String(10))
    tokens_used = Column(Integer, default=0)
    cost_usd    = Column(String(20), default="0")
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
