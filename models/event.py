import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _generate_uuid() -> str:
    return str(uuid.uuid4())


class Event(Base):
    __tablename__ = "events"

    id = Column(String(36), primary_key=True, default=_generate_uuid)
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category_id = Column(String(36), ForeignKey("categories.id"), nullable=True)
    organizer_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    venue_name = Column(String(200), nullable=False)
    address_line = Column(String(500), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=False)
    start_datetime = Column(DateTime, nullable=False, index=True)
    end_datetime = Column(DateTime, nullable=False)
    total_capacity = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="draft")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    organizer = relationship("User", back_populates="events", lazy="selectin")
    category = relationship("Category", back_populates="events", lazy="selectin")
    ticket_types = relationship("TicketType", back_populates="event", lazy="selectin", cascade="all, delete-orphan")
    tickets = relationship("Ticket", back_populates="event", lazy="selectin", cascade="all, delete-orphan")
    rsvps = relationship("RSVP", back_populates="event", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_events_title", "title"),
        Index("ix_events_city", "city"),
        Index("ix_events_start_datetime", "start_datetime"),
    )

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, title={self.title!r}, status={self.status!r})>"