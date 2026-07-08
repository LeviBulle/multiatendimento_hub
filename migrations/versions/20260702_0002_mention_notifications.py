"""add mention notifications"""

from alembic import op
import sqlalchemy as sa

revision = "20260702_0002"
down_revision = "20260702_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "mention_notifications" in inspector.get_table_names():
        return
    op.create_table(
        "mention_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("mentioned_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("mentioned_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_mention_notifications_workspace_id", "mention_notifications", ["workspace_id"])
    op.create_index("ix_mention_notifications_conversation_id", "mention_notifications", ["conversation_id"])
    op.create_index("ix_mention_notifications_message_id", "mention_notifications", ["message_id"])
    op.create_index("ix_mention_notifications_mentioned_user_id", "mention_notifications", ["mentioned_user_id"])
    op.create_index("ix_mention_notifications_mentioned_by_user_id", "mention_notifications", ["mentioned_by_user_id"])
    op.create_index("ix_mention_notifications_is_read", "mention_notifications", ["is_read"])


def downgrade() -> None:
    op.drop_table("mention_notifications")
