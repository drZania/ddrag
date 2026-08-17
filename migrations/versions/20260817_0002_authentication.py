"""Add password hashes for authentication."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260817_0002"
down_revision: Union[str, Sequence[str], None] = "20260817_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")