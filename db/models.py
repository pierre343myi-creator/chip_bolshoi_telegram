from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    scene: Mapped[str | None] = mapped_column(String(100), nullable=True)
    show_dates: Mapped[list | None] = mapped_column(JSON, nullable=True)
    program_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ticket_price: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sale_opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ticket_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str] = mapped_column(Text, unique=True, index=True)
    notified_advance: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_today: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Subscriber(Base):
    __tablename__ = "subscribers"

    max_user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subscribed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
