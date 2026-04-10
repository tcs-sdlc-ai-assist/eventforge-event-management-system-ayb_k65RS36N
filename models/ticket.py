import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TicketType(Base):
    __tablename__ = "ticket_types"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    event_id = Column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False, default=0.0)
    quantity = Column(Integer, nullable=False, default=0)
    sold = Column(Integer, nullable=False, default=0)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    event = relationship("Event", back_populates="ticket_types", lazy="selectin")
    tickets = relationship("Ticket", back_populates="ticket_type", lazy="selectin")

    @property
    def available_quantity(self) -> int:
        return max(0, self.quantity - self.sold)


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    event_id = Column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    ticket_type_id = Column(String(36), ForeignKey("ticket_types.id"), nullable=False, index=True)
    attendee_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    total_price = Column(Float, nullable=False, default=0.0)
    status = Column(String(20), nullable=False, default="confirmed")
    checked_in = Column(Boolean, nullable=False, default=False)
    checked_in_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    event = relationship("Event", back_populates="tickets", lazy="selectin")
    ticket_type = relationship("TicketType", back_populates="tickets", lazy="selectin")
    attendee = relationship("User", back_populates="tickets", lazy="selectin")