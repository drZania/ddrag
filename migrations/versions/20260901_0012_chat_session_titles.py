"""Add durable titles to chat sessions."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260901_0012"
down_revision: Union[str, Sequence[str], None] = "20260819_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column("title", sa.String(length=120), nullable=False, server_default="Untitled chat"),
    )
    op.add_column(
        "chat_sessions",
        sa.Column("title_is_manual", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("chat_sessions", "title", server_default=None)
    op.alter_column("chat_sessions", "title_is_manual", server_default=None)


def downgrade() -> None:
    op.drop_column("chat_sessions", "title_is_manual")
    op.drop_column("chat_sessions", "title")
