from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TicketTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    price: float = Field(..., ge=0)
    quantity: int = Field(..., ge=1)
    description: Optional[str] = None


class TicketTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    price: float
    quantity: int
    available_quantity: int
    description: Optional[str] = None
    event_id: UUID
    created_at: datetime
    updated_at: datetime


class EventCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    venue_name: str = Field(..., min_length=1, max_length=200)
    venue_address: str = Field(..., min_length=1, max_length=500)
    venue_city: str = Field(..., min_length=1, max_length=100)
    venue_state: Optional[str] = Field(None, max_length=100)
    venue_country: str = Field(..., min_length=1, max_length=100)
    venue_zip_code: Optional[str] = Field(None, max_length=20)
    start_datetime: datetime
    end_datetime: datetime
    capacity: int = Field(..., ge=1)
    ticket_types: list[TicketTypeCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_start_before_end(self) -> "EventCreate":
        if self.start_datetime >= self.end_datetime:
            raise ValueError("start_datetime must be before end_datetime")
        return self

    @field_validator("capacity")
    @classmethod
    def validate_capacity(cls, v: int) -> int:
        if v < 1:
            raise ValueError("capacity must be at least 1")
        return v


class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    venue_name: Optional[str] = Field(None, min_length=1, max_length=200)
    venue_address: Optional[str] = Field(None, min_length=1, max_length=500)
    venue_city: Optional[str] = Field(None, min_length=1, max_length=100)
    venue_state: Optional[str] = Field(None, max_length=100)
    venue_country: Optional[str] = Field(None, min_length=1, max_length=100)
    venue_zip_code: Optional[str] = Field(None, max_length=20)
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    capacity: Optional[int] = Field(None, ge=1)
    status: Optional[str] = Field(None, pattern="^(draft|published|cancelled|completed)$")

    @model_validator(mode="after")
    def validate_start_before_end(self) -> "EventUpdate":
        if self.start_datetime is not None and self.end_datetime is not None:
            if self.start_datetime >= self.end_datetime:
                raise ValueError("start_datetime must be before end_datetime")
        return self

    @field_validator("capacity")
    @classmethod
    def validate_capacity(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("capacity must be at least 1")
        return v


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    organizer_id: UUID
    venue_name: str
    venue_address: str
    venue_city: str
    venue_state: Optional[str] = None
    venue_country: str
    venue_zip_code: Optional[str] = None
    start_datetime: datetime
    end_datetime: datetime
    capacity: int
    status: str
    ticket_types: list[TicketTypeResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class EventListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    organizer_id: UUID
    venue_name: str
    venue_city: str
    venue_country: str
    start_datetime: datetime
    end_datetime: datetime
    capacity: int
    status: str
    created_at: datetime
    updated_at: datetime


class EventSearchParams(BaseModel):
    keyword: Optional[str] = None
    category: Optional[UUID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    status: Optional[str] = Field(None, pattern="^(draft|published|cancelled|completed)$")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_date_range(self) -> "EventSearchParams":
        if self.date_from is not None and self.date_to is not None:
            if self.date_from >= self.date_to:
                raise ValueError("date_from must be before date_to")
        return self


class PaginatedEventResponse(BaseModel):
    items: list[EventListResponse]
    total: int
    page: int
    page_size: int
    total_pages: int