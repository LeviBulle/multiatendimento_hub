"""portfolio schema with workspaces and collaboration fields"""

from alembic import op
import sqlalchemy as sa

revision = "20260702_0001"
down_revision = None
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


def has_fk(inspector, table_name: str, fk_name: str) -> bool:
    if not has_table(inspector, table_name):
        return False
    for fk in inspector.get_foreign_keys(table_name):
        if fk["name"] == fk_name:
            return True
        if fk.get("referred_table") == "workspaces" and fk.get("constrained_columns") == ["workspace_id"]:
            return True
    return False


def ensure_initial_workspace(bind) -> None:
    workspaces = sa.table(
        "workspaces",
        sa.column("id", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("slug", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime()),
    )
    exists = bind.execute(sa.select(workspaces.c.id).where(workspaces.c.slug == "ellub-demo")).first()
    if not exists:
        bind.execute(
            workspaces.insert().values(
                id=1,
                name="Ellub Demo",
                slug="ellub-demo",
                is_active=True,
                created_at=sa.func.now(),
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not has_table(inspector, "workspaces"):
        op.create_table(
            "workspaces",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("slug", sa.String(80), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_workspaces_slug", "workspaces", ["slug"], unique=True)

    if not has_table(inspector, "users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("hashed_password", sa.String(255), nullable=False),
            sa.Column("role", sa.String(30), nullable=False, server_default="agent"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    if not has_table(inspector, "clients"):
        op.create_table(
            "clients",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
            sa.Column("full_name", sa.String(160), nullable=False),
            sa.Column("first_name", sa.String(80), nullable=False),
            sa.Column("preferred_name", sa.String(120)),
            sa.Column("birth_date", sa.String(20)),
            sa.Column("gender", sa.String(20)),
            sa.Column("phone", sa.String(40)),
            sa.Column("phone_country_code", sa.String(8)),
            sa.Column("phone_area_code", sa.String(4)),
            sa.Column("phone_number", sa.String(20)),
            sa.Column("email", sa.String(255)),
            sa.Column("cpf", sa.String(30)),
            sa.Column("rg", sa.String(30)),
            sa.Column("address", sa.String(255)),
            sa.Column("zip_code", sa.String(20)),
            sa.Column("address_number", sa.String(30)),
            sa.Column("address_complement", sa.String(120)),
            sa.Column("reference_point", sa.String(160)),
            sa.Column("fixed_location", sa.String(255)),
            sa.Column("notes", sa.Text()),
            sa.Column("restrictions", sa.Text()),
            sa.Column("complaints", sa.Text()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    if not has_table(inspector, "channels"):
        op.create_table(
            "channels",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("type", sa.String(40), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    if not has_table(inspector, "conversations"):
        op.create_table(
            "conversations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
            sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("channel_id", sa.Integer(), sa.ForeignKey("channels.id"), nullable=False),
            sa.Column("agent_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("status", sa.String(30), nullable=False, server_default="aberta"),
            sa.Column("unread", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("last_message_at", sa.DateTime(timezone=True)),
            sa.Column("first_response_at", sa.DateTime(timezone=True)),
            sa.Column("closed_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("duration_minutes", sa.Integer()),
            sa.Column("first_response_minutes", sa.Integer()),
        )

    if not has_table(inspector, "messages"):
        op.create_table(
            "messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=False),
            sa.Column("author_user_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("sender", sa.String(30), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="enviada"),
            sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("scheduled_for", sa.DateTime(timezone=True)),
            sa.Column("attachment_original_name", sa.String(255)),
            sa.Column("attachment_stored_name", sa.String(255)),
            sa.Column("attachment_mime_type", sa.String(120)),
            sa.Column("attachment_size_bytes", sa.Integer()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    if not has_table(inspector, "quick_replies"):
        op.create_table(
            "quick_replies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
            sa.Column("title", sa.String(120), nullable=False),
            sa.Column("shortcut", sa.String(50), nullable=False, index=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("type", sa.String(30), nullable=False, server_default="global"),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    ensure_initial_workspace(bind)
    inspector = sa.inspect(bind)
    for table_name in ("users", "clients", "channels", "conversations", "quick_replies"):
        if has_table(inspector, table_name) and not has_column(inspector, table_name, "workspace_id"):
            with op.batch_alter_table(table_name) as batch:
                batch.add_column(sa.Column("workspace_id", sa.Integer(), nullable=True))
            bind.execute(sa.text(f"UPDATE {table_name} SET workspace_id = 1 WHERE workspace_id IS NULL"))
        if has_table(inspector, table_name) and has_column(sa.inspect(bind), table_name, "workspace_id"):
            bind.execute(sa.text(f"UPDATE {table_name} SET workspace_id = 1 WHERE workspace_id IS NULL"))
            inspector = sa.inspect(bind)
            index_name = f"ix_{table_name}_workspace_id"
            if not has_index(inspector, table_name, index_name):
                op.create_index(index_name, table_name, ["workspace_id"])
            fk_name = f"fk_{table_name}_workspace_id_workspaces"
            if not has_fk(inspector, table_name, fk_name):
                with op.batch_alter_table(table_name) as batch:
                    batch.alter_column("workspace_id", existing_type=sa.Integer(), nullable=False)
                    batch.create_foreign_key(fk_name, "workspaces", ["workspace_id"], ["id"])
    if has_table(inspector, "conversations") and not has_column(inspector, "conversations", "is_favorite"):
        with op.batch_alter_table("conversations") as batch:
            batch.add_column(sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.false()))
    for column, type_ in (
        ("author_user_id", sa.Integer()),
        ("attachment_original_name", sa.String(255)),
        ("attachment_stored_name", sa.String(255)),
        ("attachment_mime_type", sa.String(120)),
        ("attachment_size_bytes", sa.Integer()),
    ):
        inspector = sa.inspect(bind)
        if has_table(inspector, "messages") and not has_column(inspector, "messages", column):
            with op.batch_alter_table("messages") as batch:
                batch.add_column(sa.Column(column, type_, nullable=True))


def downgrade() -> None:
    pass
