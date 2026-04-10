import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class TicketType(Base):
    __tablename__ = "ticket_types"

    id = Column(String(36), primary_key=True, default=generate_uuid, nullable=False)
    event_id = Column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False, default=0.00)
    quantity = Column(Integer, nullable=False, default=0)
    available_quantity = Column(Integer, nullable=False, default=0)
    sold = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    event = relationship("Event", back_populates="ticket_types", lazy="selectin")
    tickets = relationship("Ticket", back_populates="ticket_type", lazy="selectin")