from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class RSVPStatus(str, Enum):
    going = "going"
    maybe = "maybe"
    not_going = "not_going"


class RSVPCreate(BaseModel):
    status: RSVPStatus

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if isinstance(v, str) and v not in [s.value for s in RSVPStatus]:
            raise ValueError(f"Invalid RSVP status: {v}. Must be one of: going, maybe, not_going")
        return v


class RSVPUpdate(BaseModel):
    status: RSVPStatus

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if isinstance(v, str) and v not in [s.value for s in RSVPStatus]:
            raise ValueError(f"Invalid RSVP status: {v}. Must be one of: going, maybe, not_going")
        return v


class RSVPResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    user_id: UUID
    status: RSVPStatus
    created_at: datetime
    updated_at: Optional[datetime] = None


class RSVPCounts(BaseModel):
    going_count: int = 0
    maybe_count: int = 0
    not_going_count: int = 0
    total_count: int = 0