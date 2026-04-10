import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship

from database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid, nullable=False)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    hashed_password = Column(Text, nullable=False)
    role = Column(String(50), nullable=False, default="Viewer")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    events = relationship("Event", back_populates="organizer", lazy="selectin")
    tickets = relationship("Ticket", back_populates="user", lazy="selectin")
    rsvps = relationship("RSVP", back_populates="user", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"