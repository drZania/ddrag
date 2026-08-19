"""Create persistent retrieval sources for chat queries."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260819_0010"
down_revision: Union[str, Sequence[str], None] = "20260819_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "query_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("query_id", sa.Integer(), nullable=False),
        sa.Column("citation_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.Integer(), nullable=False),
        sa.Column("chunk_order", sa.Integer(), nullable=False),
        sa.Column("distance", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["query_id"], ["chat_queries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("query_id", "citation_id", name="uq_query_sources_query_citation"),
    )
    op.create_index(op.f("ix_query_sources_query_id"), "query_sources", ["query_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_query_sources_query_id"), table_name="query_sources")
    op.drop_table("query_sources")