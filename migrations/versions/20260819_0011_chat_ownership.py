"""Enforce chat query message ownership for M10."""

from typing import Sequence, Union

from alembic import op


revision: str = "20260819_0011"
down_revision: Union[str, Sequence[str], None] = "20260819_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_chat_messages_id_session",
        "chat_messages",
        ["id", "session_id"],
    )
    op.create_foreign_key(
        "fk_chat_queries_user_message_session",
        "chat_queries",
        "chat_messages",
        ["user_message_id", "session_id"],
        ["id", "session_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_chat_queries_assistant_message_session",
        "chat_queries",
        "chat_messages",
        ["assistant_message_id", "session_id"],
        ["id", "session_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_chat_queries_assistant_message_session", "chat_queries", type_="foreignkey")
    op.drop_constraint("fk_chat_queries_user_message_session", "chat_queries", type_="foreignkey")
    op.drop_constraint("uq_chat_messages_id_session", "chat_messages", type_="unique")