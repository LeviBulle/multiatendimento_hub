"""add whatsapp customer window and templates"""

from alembic import op
import sqlalchemy as sa

revision = "20260707_0004"
down_revision = "20260702_0003"
branch_labels = None
depends_on = None


def has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def has_column(inspector, table_name: str, column_name: str) -> bool:
    if not has_table(inspector, table_name):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def has_index(inspector, table_name: str, index_name: str) -> bool:
    if not has_table(inspector, table_name):
        return False
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not has_column(inspector, "conversations", "last_customer_message_at"):
        with op.batch_alter_table("conversations") as batch:
            batch.add_column(sa.Column("last_customer_message_at", sa.DateTime(timezone=True), nullable=True))
    inspector = sa.inspect(bind)
    if not has_index(inspector, "conversations", "ix_conversations_last_customer_message_at"):
        op.create_index("ix_conversations_last_customer_message_at", "conversations", ["last_customer_message_at"])

    if not has_table(inspector, "whatsapp_templates"):
        op.create_table(
            "whatsapp_templates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("slug", sa.String(120), nullable=False),
            sa.Column("language", sa.String(20), nullable=False, server_default="pt_BR"),
            sa.Column("category", sa.String(30), nullable=False, server_default="utility"),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
            sa.Column("external_template_id", sa.String(120), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("workspace_id", "name", name="uq_whatsapp_templates_workspace_name"),
        )
        op.create_index("ix_whatsapp_templates_workspace_id", "whatsapp_templates", ["workspace_id"])
        op.create_index("ix_whatsapp_templates_slug", "whatsapp_templates", ["slug"])
        op.create_index("ix_whatsapp_templates_status", "whatsapp_templates", ["status"])

    inspector = sa.inspect(bind)
    message_columns = [
        ("failure_reason", sa.String(255), None),
        ("message_kind", sa.String(30), "'text'"),
        ("whatsapp_template_id", sa.Integer(), None),
    ]
    for column_name, column_type, default_sql in message_columns:
        if not has_column(inspector, "messages", column_name):
            with op.batch_alter_table("messages") as batch:
                batch.add_column(sa.Column(column_name, column_type, nullable=True))
            if default_sql is not None:
                bind.execute(sa.text(f"UPDATE messages SET {column_name} = {default_sql} WHERE {column_name} IS NULL"))
            if column_name == "message_kind":
                with op.batch_alter_table("messages") as batch:
                    batch.alter_column("message_kind", existing_type=sa.String(30), nullable=False)
        inspector = sa.inspect(bind)

    inspector = sa.inspect(bind)
    if not has_index(inspector, "messages", "ix_messages_whatsapp_template_id"):
        op.create_index("ix_messages_whatsapp_template_id", "messages", ["whatsapp_template_id"])

    if has_column(sa.inspect(bind), "messages", "whatsapp_template_id"):
        with op.batch_alter_table("messages") as batch:
            batch.create_foreign_key(
                "fk_messages_whatsapp_template_id_whatsapp_templates",
                "whatsapp_templates",
                ["whatsapp_template_id"],
                ["id"],
            )

    bind.execute(
        sa.text(
            """
            UPDATE conversations
            SET last_customer_message_at = (
                SELECT MAX(messages.created_at)
                FROM messages
                WHERE messages.conversation_id = conversations.id
                  AND messages.sender = 'cliente'
            )
            WHERE conversations.last_customer_message_at IS NULL
              AND EXISTS (
                SELECT 1
                FROM channels
                WHERE channels.id = conversations.channel_id
                  AND LOWER(channels.type) = 'whatsapp'
              )
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("messages") as batch:
        batch.drop_constraint("fk_messages_whatsapp_template_id_whatsapp_templates", type_="foreignkey")
        batch.drop_column("whatsapp_template_id")
        batch.drop_column("message_kind")
        batch.drop_column("failure_reason")
    op.drop_table("whatsapp_templates")
    op.drop_index("ix_conversations_last_customer_message_at", table_name="conversations")
    with op.batch_alter_table("conversations") as batch:
        batch.drop_column("last_customer_message_at")
