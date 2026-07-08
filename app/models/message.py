from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.db.base import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    author_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    sender: Mapped[str] = mapped_column(String(30))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="enviada")
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message_kind: Mapped[str] = mapped_column(String(30), default="text")
    whatsapp_template_id: Mapped[int | None] = mapped_column(ForeignKey("whatsapp_templates.id"), nullable=True, index=True)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attachment_original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attachment_stored_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attachment_mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    attachment_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    conversation = relationship("Conversation", back_populates="messages")
    author_user = relationship("User", back_populates="authored_messages")
    whatsapp_template = relationship("WhatsAppTemplate", back_populates="messages")
