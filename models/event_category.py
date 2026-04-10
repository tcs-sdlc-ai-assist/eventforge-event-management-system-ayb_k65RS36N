import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import relationship

from database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EventCategory(Base):
    __tablename__ = "event_categories"

    id = Column(String(36), primary_key=True, default=generate_uuid, nullable=False)
    name = Column(String(100), nullable=False, unique=True, index=True)
    color = Column(String(7), nullable=True, default="#6366f1")
    icon = Column(String(50), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    events = relationship("Event", back_populates="category", lazy="selectin")

    def __repr__(self) -> str:
        return f"<EventCategory(id={self.id}, name={self.name})>"