"""
GoatRaw - User ORM Model
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid, enum
from app.core.database import Base


class PlanTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(Base):
    __tablename__ = "users"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name       = Column(String(255))
    api_key         = Column(String(128), unique=True, index=True)
    workspace_id    = Column(String(64), index=True)
    plan            = Column(SAEnum(PlanTier), default=PlanTier.FREE, nullable=False)
    is_active       = Column(Boolean, default=True)
    is_verified     = Column(Boolean, default=False)
    usage_count     = Column(Integer, default=0)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())
    meta            = Column("metadata", JSONB, default={})
