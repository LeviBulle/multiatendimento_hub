from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.db.base import Base


class WhatsAppTemplate(Base):
    __tablename__ = "whatsapp_templates"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_whatsapp_templates_workspace_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), index=True)
    language: Mapped[str] = mapped_column(String(20), default="pt_BR")
    category: Mapped[str] = mapped_column(String(30), default="utility")
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    external_template_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    workspace = relationship("Workspace", back_populates="whatsapp_templates")
    messages = relationship("Message", back_populates="whatsapp_template")
