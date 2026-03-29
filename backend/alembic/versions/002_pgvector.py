"""pgvector — Add vector column to deep_memories table

Revision ID: 002_pgvector
Revises: 001_initial
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision      = "002_pgvector"
down_revision = "001_initial"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create deep_memories table for Tier 3 memory with vector embeddings
    op.create_table(
        "deep_memories",
        sa.Column("id",         sa.String(64),  primary_key=True),
        sa.Column("user_id",    postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("content",    sa.Text(),   nullable=False),
        sa.Column("category",   sa.String(50)),            # preference|identity|project|knowledge|contact|decision
        sa.Column("embedding",  sa.Text()),                # JSON-serialised 1536-dim vector (fallback)
        sa.Column("metadata",   postgresql.JSONB(),  server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_accessed", sa.DateTime(timezone=True)),
    )

    # Add native pgvector column (1536 dims = text-embedding-3-small)
    op.execute("ALTER TABLE deep_memories ADD COLUMN IF NOT EXISTS embedding_vec vector(1536)")

    # IVFFlat index for fast approximate nearest-neighbour search
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_deep_memories_embedding
        ON deep_memories
        USING ivfflat (embedding_vec vector_cosine_ops)
        WITH (lists = 100)
    """)

    op.create_index("idx_deep_memories_user_id",  "deep_memories", ["user_id"])
    op.create_index("idx_deep_memories_category", "deep_memories", ["category"])

    # Skill store — persist AI-generated skills to DB
    op.create_table(
        "workspace_skills",
        sa.Column("id",           sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False, index=True),
        sa.Column("name",         sa.String(255)),
        sa.Column("description",  sa.Text()),
        sa.Column("category",     sa.String(50)),
        sa.Column("author",       sa.String(255)),
        sa.Column("definition",   postgresql.JSONB(), server_default="{}"),  # full skill JSON
        sa.Column("is_public",    sa.Boolean(), server_default="false"),
        sa.Column("version",      sa.String(20)),
        sa.Column("run_count",    sa.Integer(),  server_default="0"),
        sa.Column("created_at",   sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Heartbeat history
    op.create_table(
        "heartbeat_history",
        sa.Column("id",         postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id",    postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status",     sa.String(20)),    # OK | ACTION_NEEDED | error
        sa.Column("message",    sa.Text()),
        sa.Column("actions",    postgresql.JSONB(), server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Cron job runs audit
    op.create_table(
        "cron_runs",
        sa.Column("id",         postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id",     sa.String(64), nullable=False, index=True),
        sa.Column("user_id",    postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id",    sa.String(64)),
        sa.Column("status",     sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for tbl in ["cron_runs", "heartbeat_history", "workspace_skills", "deep_memories"]:
        op.drop_table(tbl)
    op.execute("DROP EXTENSION IF EXISTS vector")
