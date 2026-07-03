"""add user profile status fields"""

from alembic import op
import sqlalchemy as sa

revision = "20260702_0003"
down_revision = "20260702_0002"
branch_labels = None
depends_on = None


def has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not has_column("users", "is_available"):
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.true()))
    if not has_column("users", "avatar_stored_name"):
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("avatar_stored_name", sa.String(255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("avatar_stored_name")
        batch.drop_column("is_available")
