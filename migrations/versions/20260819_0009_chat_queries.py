"""Create persistent chat query records for M10."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260819_0009"
down_revision: Union[str, Sequence[str], None] = "20260819_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_queries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("user_message_id", sa.Integer(), nullable=False),
        sa.Column("assistant_message_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="chat_query_status_check",
        ),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assistant_message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_message_id"),
        sa.UniqueConstraint("assistant_message_id"),
    )
    op.create_index(op.f("ix_chat_queries_session_id"), "chat_queries", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chat_queries_session_id"), table_name="chat_queries")
    op.drop_table("chat_queries")