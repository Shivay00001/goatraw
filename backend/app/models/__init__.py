"""
GoatRaw - SQLAlchemy ORM Models
"""

# ── user.py ──────────────────────────────────────────────────────────────────
USER_MODEL = '''
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
import enum
from app.core.database import Base


class PlanTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    api_key = Column(String(64), unique=True, index=True)
    plan = Column(SAEnum(PlanTier), default=PlanTier.FREE, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    metadata_ = Column("metadata", JSONB, default={})
'''

# ── task.py ──────────────────────────────────────────────────────────────────
TASK_MODEL = '''
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
import enum
from app.core.database import Base


class TaskStatus(str, enum.Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, enum.Enum):
    GENERAL = "general"
    LEAD_GENERATION = "lead_generation"
    MARKET_RESEARCH = "market_research"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    DATA_EXTRACTION = "data_extraction"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    goal = Column(Text, nullable=False)
    agent_type = Column(SAEnum(TaskType), default=TaskType.GENERAL)
    status = Column(SAEnum(TaskStatus), default=TaskStatus.QUEUED, index=True)
    context = Column(JSONB, default={})
    steps_taken = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
'''

# ── output.py ────────────────────────────────────────────────────────────────
OUTPUT_MODEL = '''
from sqlalchemy import Column, String, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from app.core.database import Base


class Output(Base):
    __tablename__ = "outputs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    summary = Column(Text)
    data = Column(JSONB, default={})
    trace = Column(JSONB, default={})
    status = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
'''

# ── log.py ───────────────────────────────────────────────────────────────────
LOG_MODEL = '''
from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from app.core.database import Base


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    step_number = Column(Integer)
    log_type = Column(String(50))  # plan | tool_call | tool_result | thought | output
    content = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
'''

# Write each model to its own file programmatically
import os

models_dir = os.path.join(os.path.dirname(__file__), "../models")
os.makedirs(models_dir, exist_ok=True)

for fname, content in [
    ("user.py", USER_MODEL),
    ("task.py", TASK_MODEL),
    ("output.py", OUTPUT_MODEL),
    ("log.py", LOG_MODEL),
]:
    path = os.path.join(models_dir, fname)
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(content.strip())
