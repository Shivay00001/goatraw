"""
GoatRaw - Agent Log ORM Model
"""
from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from app.core.database import Base


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id     = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    step_number = Column(Integer)
    log_type    = Column(String(50))  # plan | tool_call | tool_result | thought | output
    content     = Column(JSONB)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
