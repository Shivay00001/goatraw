"""initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-03-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id",              postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email",           sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name",       sa.String(255)),
        sa.Column("api_key",         sa.String(128), unique=True),
        sa.Column("workspace_id",    sa.String(64)),
        sa.Column("plan",            sa.String(20),  nullable=False, server_default="free"),
        sa.Column("is_active",       sa.Boolean(),   nullable=False, server_default="true"),
        sa.Column("is_verified",     sa.Boolean(),   nullable=False, server_default="false"),
        sa.Column("usage_count",     sa.Integer(),   server_default="0"),
        sa.Column("metadata",        postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at",      sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_email",   "users", ["email"])
    op.create_index("ix_users_api_key", "users", ["api_key"])

    # ── tasks ──────────────────────────────────────────────────
    op.create_table(
        "tasks",
        sa.Column("id",           postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id",      postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.String(64)),
        sa.Column("goal",         sa.Text(), nullable=False),
        sa.Column("agent_type",   sa.String(50), server_default="general"),
        sa.Column("status",       sa.String(20), server_default="queued"),
        sa.Column("context",      postgresql.JSONB(), server_default="{}"),
        sa.Column("skill_id",     sa.String(64)),
        sa.Column("cron_job_id",  sa.String(64)),
        sa.Column("steps_taken",  sa.Integer(), server_default="0"),
        sa.Column("source",       sa.String(50), server_default="api"),
        sa.Column("created_at",   sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at",   sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_tasks_user_id",    "tasks", ["user_id"])
    op.create_index("ix_tasks_status",     "tasks", ["status"])
    op.create_index("ix_tasks_created_at", "tasks", ["created_at"])

    # ── outputs ────────────────────────────────────────────────
    op.create_table(
        "outputs",
        sa.Column("id",         postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id",    postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id",  ondelete="CASCADE"), nullable=False),
        sa.Column("user_id",    postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id",  ondelete="CASCADE"), nullable=False),
        sa.Column("summary",    sa.Text()),
        sa.Column("data",       postgresql.JSONB(), server_default="{}"),
        sa.Column("trace",      postgresql.JSONB(), server_default="{}"),
        sa.Column("status",     sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_outputs_task_id", "outputs", ["task_id"])
    op.create_index("ix_outputs_user_id", "outputs", ["user_id"])

    # ── agent_logs ────────────────────────────────────────────
    op.create_table(
        "agent_logs",
        sa.Column("id",          postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id",     postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_number", sa.Integer()),
        sa.Column("log_type",    sa.String(50)),
        sa.Column("content",     postgresql.JSONB()),
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_agent_logs_task_id", "agent_logs", ["task_id"])

    # ── api_usage ──────────────────────────────────────────────
    op.create_table(
        "api_usage",
        sa.Column("id",          postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id",     postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint",    sa.String(255)),
        sa.Column("method",      sa.String(10)),
        sa.Column("tokens_used", sa.Integer(), server_default="0"),
        sa.Column("cost_usd",    sa.String(20), server_default="0"),
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_api_usage_user_id",    "api_usage", ["user_id"])
    op.create_index("ix_api_usage_created_at", "api_usage", ["created_at"])


def downgrade() -> None:
    for tbl in ["api_usage", "agent_logs", "outputs", "tasks", "users"]:
        op.drop_table(tbl)
