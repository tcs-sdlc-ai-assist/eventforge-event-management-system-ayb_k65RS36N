from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class TicketTypeCreate(BaseModel):
    name: str
    price: float
    quantity: int

    @field_validator("price")
    @classmethod
    def price_must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Price must be greater than or equal to 0")
        return v

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_at_least_one(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Quantity must be at least 1")
        return v

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name must not be empty")
        return v.strip()


class TicketTypeUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    quantity: Optional[int] = None

    @field_validator("price")
    @classmethod
    def price_must_be_non_negative(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("Price must be greater than or equal to 0")
        return v

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_at_least_one(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("Quantity must be at least 1")
        return v

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError("Name must not be empty")
            return v.strip()
        return v


class TicketClaim(BaseModel):
    ticket_type_id: UUID
    quantity: int

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_at_least_one(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Quantity must be at least 1")
        return v


class TicketTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    name: str
    price: float
    quantity: int
    sold: int
    created_at: datetime
    updated_at: datetime


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_type_id: UUID
    user_id: UUID
    event_id: UUID
    quantity: int
    total_price: float
    status: str
    created_at: datetime
    updated_at: datetime