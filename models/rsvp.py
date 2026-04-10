import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RSVP(Base):
    __tablename__ = "rsvps"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_rsvp_event_user"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid, nullable=False)
    event_id = Column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="going")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    event = relationship("Event", back_populates="rsvps", lazy="selectin")
    user = relationship("User", back_populates="rsvps", lazy="selectin")

    def __repr__(self) -> str:
        return f"<RSVP(id={self.id}, event_id={self.event_id}, user_id={self.user_id}, status={self.status})>"