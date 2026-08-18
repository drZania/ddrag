"""Add chunk persistence tables for the M6 chunking milestone."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260818_0005"
down_revision: Union[str, Sequence[str], None] = "20260817_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_order", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("chunk_size_chars", sa.Integer(), nullable=False),
        sa.Column("chunk_overlap_chars", sa.Integer(), nullable=False),
        sa.Column("chunking_version", sa.String(length=64), nullable=False, server_default="ddrag-chunking-v1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_order", name="uq_chunks_document_order"),
        sa.CheckConstraint("chunk_size_chars > 0", name="chunk_size_positive"),
        sa.CheckConstraint("chunk_overlap_chars >= 0", name="chunk_overlap_non_negative"),
    )
    op.create_index(op.f("ix_chunks_document_id"), "chunks", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chunks_document_id"), table_name="chunks")
    op.drop_table("chunks")
