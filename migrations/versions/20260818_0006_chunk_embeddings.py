"""Add pgvector embeddings to persisted chunks for M7."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector


revision: str = "20260818_0006"
down_revision: Union[str, Sequence[str], None] = "20260818_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chunks", sa.Column("embedding", Vector(1024), nullable=True))


def downgrade() -> None:
    op.drop_column("chunks", "embedding")
