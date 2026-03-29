"""GoatRaw - Task ORM Model"""
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid, enum
from app.core.database import Base


class TaskStatus(str, enum.Enum):
    QUEUED    = "queued"
    PLANNING  = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELLED = "cancelled"


class TaskType(str, enum.Enum):
    GENERAL             = "general"
    LEAD_GENERATION     = "lead_generation"
    MARKET_RESEARCH     = "market_research"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    DATA_EXTRACTION     = "data_extraction"
    OUTREACH_DRAFTING   = "outreach_drafting"
    WEBSITE_AUDIT       = "website_audit"
    MONITORING          = "monitoring"
    SKILL_RUN           = "skill_run"
    SCHEDULED           = "scheduled"


class Task(Base):
    __tablename__ = "tasks"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    workspace_id = Column(String(64), index=True)
    goal         = Column(Text, nullable=False)
    agent_type   = Column(SAEnum(TaskType), default=TaskType.GENERAL)
    status       = Column(SAEnum(TaskStatus), default=TaskStatus.QUEUED, index=True)
    context      = Column(JSONB, default={})
    skill_id     = Column(String(64), nullable=True)
    cron_job_id  = Column(String(64), nullable=True)
    steps_taken  = Column(Integer, default=0)
    source       = Column(String(50), default="api")   # api | telegram | slack | whatsapp | cron | heartbeat
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    started_at   = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
