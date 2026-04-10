import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.ticket import Ticket, TicketType
from models.event import Event
from models.user import User

logger = logging.getLogger(__name__)


async def claim_ticket(
    db: AsyncSession,
    event_id: str,
    ticket_type_id: str,
    attendee_id: str,
    quantity: int,
) -> Ticket:
    """
    Claim tickets for an attendee. Validates availability via SQL COUNT,
    creates Ticket in transaction, prevents overselling.
    """
    if quantity < 1:
        raise ValueError("Quantity must be at least 1")

    # Verify event exists and is published
    event_result = await db.execute(
        select(Event).where(Event.id == event_id)
    )
    event = event_result.scalar_one_or_none()
    if event is None:
        raise ValueError("Event not found")
    if event.status != "published":
        raise ValueError("Event is not published")

    # Verify ticket type exists and belongs to this event
    tt_result = await db.execute(
        select(TicketType).where(
            TicketType.id == ticket_type_id,
            TicketType.event_id == event_id,
        )
    )
    ticket_type = tt_result.scalar_one_or_none()
    if ticket_type is None:
        raise ValueError("Ticket type not found for this event")

    # Verify attendee exists
    user_result = await db.execute(
        select(User).where(User.id == attendee_id)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise ValueError("User not found")

    # Calculate sold count via SQL SUM
    sold_result = await db.execute(
        select(func.coalesce(func.sum(Ticket.quantity), 0)).where(
            Ticket.ticket_type_id == ticket_type_id,
            Ticket.status == "confirmed",
        )
    )
    sold = sold_result.scalar() or 0

    available = ticket_type.quantity - sold
    if quantity > available:
        raise ValueError(
            f"Not enough tickets available. Requested: {quantity}, Available: {available}"
        )

    # Calculate total price
    total_price = float(ticket_type.price) * quantity

    # Create ticket
    ticket = Ticket(
        event_id=event_id,
        ticket_type_id=ticket_type_id,
        attendee_id=attendee_id,
        quantity=quantity,
        total_price=total_price,
        status="confirmed",
        checked_in=False,
    )
    db.add(ticket)

    # Update sold count on ticket type
    ticket_type.sold = sold + quantity
    ticket_type.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(ticket)

    logger.info(
        "Ticket claimed: ticket_id=%s, event_id=%s, attendee_id=%s, quantity=%d",
        ticket.id,
        event_id,
        attendee_id,
        quantity,
    )

    return ticket


async def get_ticket_availability(
    db: AsyncSession,
    ticket_type_id: str,
) -> int:
    """
    Returns available count for a ticket type.
    """
    tt_result = await db.execute(
        select(TicketType).where(TicketType.id == ticket_type_id)
    )
    ticket_type = tt_result.scalar_one_or_none()
    if ticket_type is None:
        raise ValueError("Ticket type not found")

    sold_result = await db.execute(
        select(func.coalesce(func.sum(Ticket.quantity), 0)).where(
            Ticket.ticket_type_id == ticket_type_id,
            Ticket.status == "confirmed",
        )
    )
    sold = sold_result.scalar() or 0

    available = max(0, ticket_type.quantity - sold)
    return available


async def get_user_tickets(
    db: AsyncSession,
    user_id: str,
) -> list[dict[str, Any]]:
    """
    Get all tickets for an attendee with event info.
    """
    result = await db.execute(
        select(Ticket)
        .where(Ticket.attendee_id == user_id)
        .options(
            selectinload(Ticket.event),
            selectinload(Ticket.ticket_type),
        )
        .order_by(Ticket.created_at.desc())
    )
    tickets = result.scalars().all()

    ticket_list: list[dict[str, Any]] = []
    for ticket in tickets:
        event = ticket.event
        ticket_type = ticket.ticket_type

        ticket_data: dict[str, Any] = {
            "id": ticket.id,
            "event_id": ticket.event_id,
            "ticket_type_id": ticket.ticket_type_id,
            "attendee_id": ticket.attendee_id,
            "quantity": ticket.quantity,
            "total_price": ticket.total_price,
            "status": ticket.status,
            "checked_in": ticket.checked_in,
            "checked_in_at": ticket.checked_in_at,
            "created_at": ticket.created_at,
            "updated_at": ticket.updated_at,
            "event_title": event.title if event else "Unknown Event",
            "event_start_datetime": event.start_datetime if event else None,
            "event_end_datetime": event.end_datetime if event else None,
            "event_venue_name": event.venue_name if event else None,
            "event_venue_city": event.city if event else None,
            "event_status": event.status if event else None,
            "ticket_type_name": ticket_type.name if ticket_type else "General",
            "ticket_type_price": float(ticket_type.price) if ticket_type else 0.0,
        }
        ticket_list.append(ticket_data)

    return ticket_list


async def cancel_ticket(
    db: AsyncSession,
    ticket_id: str,
    user_id: str,
) -> Ticket:
    """
    Cancel a ticket. Only the ticket owner can cancel.
    """
    result = await db.execute(
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .options(selectinload(Ticket.ticket_type))
    )
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise ValueError("Ticket not found")

    if ticket.attendee_id != user_id:
        raise PermissionError("You can only cancel your own tickets")

    if ticket.status == "cancelled":
        raise ValueError("Ticket is already cancelled")

    if ticket.checked_in:
        raise ValueError("Cannot cancel a ticket that has been checked in")

    # Update ticket status
    ticket.status = "cancelled"
    ticket.updated_at = datetime.now(timezone.utc)

    # Update sold count on ticket type
    if ticket.ticket_type is not None:
        new_sold = max(0, ticket.ticket_type.sold - ticket.quantity)
        ticket.ticket_type.sold = new_sold
        ticket.ticket_type.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(ticket)

    logger.info(
        "Ticket cancelled: ticket_id=%s, user_id=%s",
        ticket_id,
        user_id,
    )

    return ticket


async def get_ticket_by_id(
    db: AsyncSession,
    ticket_id: str,
) -> Optional[Ticket]:
    """
    Get a single ticket by ID.
    """
    result = await db.execute(
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .options(
            selectinload(Ticket.event),
            selectinload(Ticket.ticket_type),
            selectinload(Ticket.attendee),
        )
    )
    return result.scalar_one_or_none()


async def get_event_tickets(
    db: AsyncSession,
    event_id: str,
) -> list[dict[str, Any]]:
    """
    Get all tickets for an event with attendee info.
    Used by organizers to view attendee list.
    """
    result = await db.execute(
        select(Ticket)
        .where(Ticket.event_id == event_id)
        .options(
            selectinload(Ticket.attendee),
            selectinload(Ticket.ticket_type),
        )
        .order_by(Ticket.created_at.desc())
    )
    tickets = result.scalars().all()

    attendee_list: list[dict[str, Any]] = []
    for ticket in tickets:
        attendee = ticket.attendee
        ticket_type = ticket.ticket_type

        attendee_data: dict[str, Any] = {
            "ticket_id": ticket.id,
            "attendee_id": ticket.attendee_id,
            "username": attendee.username if attendee else "Unknown",
            "display_name": attendee.display_name if attendee else "Unknown",
            "email": attendee.email if attendee else "",
            "ticket_type_name": ticket_type.name if ticket_type else "General",
            "quantity": ticket.quantity,
            "total_price": ticket.total_price,
            "ticket_status": ticket.status,
            "checked_in": ticket.checked_in,
            "checked_in_at": ticket.checked_in_at,
            "created_at": ticket.created_at,
        }
        attendee_list.append(attendee_data)

    return attendee_list


async def get_total_tickets_sold(
    db: AsyncSession,
    event_id: str,
) -> int:
    """
    Get total number of confirmed tickets sold for an event.
    """
    result = await db.execute(
        select(func.coalesce(func.sum(Ticket.quantity), 0)).where(
            Ticket.event_id == event_id,
            Ticket.status == "confirmed",
        )
    )
    total = result.scalar() or 0
    return int(total)


async def get_total_revenue(
    db: AsyncSession,
    event_id: str,
) -> float:
    """
    Get total revenue for an event from confirmed tickets.
    """
    result = await db.execute(
        select(func.coalesce(func.sum(Ticket.total_price), 0.0)).where(
            Ticket.event_id == event_id,
            Ticket.status == "confirmed",
        )
    )
    total = result.scalar() or 0.0
    return float(total)


async def toggle_checkin(
    db: AsyncSession,
    event_id: str,
    attendee_id: str,
) -> dict[str, Any]:
    """
    Toggle check-in status for an attendee at an event.
    Returns updated check-in info.
    """
    result = await db.execute(
        select(Ticket).where(
            Ticket.event_id == event_id,
            Ticket.attendee_id == attendee_id,
            Ticket.status == "confirmed",
        )
    )
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise ValueError("No confirmed ticket found for this attendee at this event")

    now = datetime.now(timezone.utc)

    if ticket.checked_in:
        ticket.checked_in = False
        ticket.checked_in_at = None
        logger.info(
            "Check-in undone: event_id=%s, attendee_id=%s",
            event_id,
            attendee_id,
        )
    else:
        ticket.checked_in = True
        ticket.checked_in_at = now
        logger.info(
            "Checked in: event_id=%s, attendee_id=%s",
            event_id,
            attendee_id,
        )

    ticket.updated_at = now
    await db.flush()
    await db.refresh(ticket)

    return {
        "ticket_id": ticket.id,
        "attendee_id": attendee_id,
        "event_id": event_id,
        "checked_in": ticket.checked_in,
        "checked_in_at": ticket.checked_in_at,
    }