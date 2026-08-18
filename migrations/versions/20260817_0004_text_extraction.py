"""Add extraction result columns for the M5 text-extraction milestone."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260817_0004"
down_revision: Union[str, Sequence[str], None] = "20260817_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("extracted_text", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("extraction_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "extraction_error")
    op.drop_column("documents", "extracted_text")
