from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.db.base import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    first_name: Mapped[str] = mapped_column(String(80), index=True)
    preferred_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    birth_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    phone_country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    phone_area_code: Mapped[str | None] = mapped_column(String(4), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cpf: Mapped[str | None] = mapped_column(String(30), nullable=True)
    rg: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address_complement: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reference_point: Mapped[str | None] = mapped_column(String(160), nullable=True)
    fixed_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    restrictions: Mapped[str | None] = mapped_column(Text, nullable=True)
    complaints: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    workspace = relationship("Workspace", back_populates="clients")
    conversations = relationship("Conversation", back_populates="client")
