from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.db.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="aberta")
    unread: Mapped[bool] = mapped_column(Boolean, default=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_customer_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_response_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    workspace = relationship("Workspace", back_populates="conversations")
    client = relationship("Client", back_populates="conversations")
    channel = relationship("Channel", back_populates="conversations")
    agent = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")
