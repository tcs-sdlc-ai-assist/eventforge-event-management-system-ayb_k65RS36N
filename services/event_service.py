import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
import math
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.event import Event
from models.ticket import Ticket, TicketType
from models.rsvp import RSVP
from models.event_category import EventCategory
from models.user import User

logger = logging.getLogger(__name__)


async def create_event(
    db: AsyncSession,
    organizer_id: str,
    title: str,
    description: Optional[str],
    category_id: Optional[str],
    venue_name: str,
    address_line: str,
    city: str,
    state: Optional[str],
    country: str,
    start_datetime: datetime,
    end_datetime: datetime,
    total_capacity: int,
    ticket_types_data: Optional[list[dict[str, Any]]] = None,
) -> Event:
    if start_datetime >= end_datetime:
        raise ValueError("start_datetime must be before end_datetime")

    if total_capacity < 1:
        raise ValueError("total_capacity must be at least 1")

    if ticket_types_data:
        total_ticket_quantity = sum(tt.get("quantity", 0) for tt in ticket_types_data)
        if total_ticket_quantity > total_capacity:
            raise ValueError("Sum of ticket quantities exceeds event capacity.")

    if category_id:
        result = await db.execute(
            select(EventCategory).where(EventCategory.id == category_id)
        )
        category = result.scalars().first()
        if not category:
            raise ValueError(f"Category with id {category_id} not found")

    event = Event(
        title=title,
        description=description,
        category_id=category_id,
        organizer_id=organizer_id,
        venue_name=venue_name,
        address_line=address_line,
        city=city,
        state=state,
        country=country,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        total_capacity=total_capacity,
        status="draft",
    )
    db.add(event)
    await db.flush()

    if ticket_types_data:
        for tt_data in ticket_types_data:
            ticket_type = TicketType(
                event_id=event.id,
                name=tt_data["name"],
                price=float(tt_data.get("price", 0.0)),
                quantity=int(tt_data["quantity"]),
                sold=0,
                description=tt_data.get("description"),
            )
            db.add(ticket_type)

    await db.flush()
    await db.refresh(event)

    logger.info(
        "Event created: id=%s title=%s organizer_id=%s",
        event.id,
        event.title,
        organizer_id,
    )
    return event


async def edit_event(
    db: AsyncSession,
    event_id: str,
    user_id: str,
    user_role: str,
    update_data: dict[str, Any],
) -> Event:
    result = await db.execute(
        select(Event)
        .where(Event.id == event_id)
        .options(
            selectinload(Event.ticket_types),
            selectinload(Event.organizer),
            selectinload(Event.category),
        )
    )
    event = result.scalars().first()

    if not event:
        raise LookupError(f"Event with id {event_id} not found")

    if event.organizer_id != user_id and user_role not in ("Admin", "Super Admin"):
        raise PermissionError("You do not have permission to edit this event")

    allowed_fields = {
        "title",
        "description",
        "category_id",
        "venue_name",
        "address_line",
        "city",
        "state",
        "country",
        "start_datetime",
        "end_datetime",
        "total_capacity",
        "status",
    }

    for key, value in update_data.items():
        if key in allowed_fields and value is not None:
            setattr(event, key, value)

    new_start = update_data.get("start_datetime", event.start_datetime)
    new_end = update_data.get("end_datetime", event.end_datetime)
    if new_start and new_end and new_start >= new_end:
        raise ValueError("start_datetime must be before end_datetime")

    if "total_capacity" in update_data and update_data["total_capacity"] is not None:
        new_capacity = update_data["total_capacity"]
        if new_capacity < 1:
            raise ValueError("total_capacity must be at least 1")

        total_ticket_quantity = sum(tt.quantity for tt in event.ticket_types)
        if total_ticket_quantity > new_capacity:
            raise ValueError("Sum of ticket quantities exceeds new event capacity.")

    if "category_id" in update_data and update_data["category_id"] is not None:
        cat_result = await db.execute(
            select(EventCategory).where(
                EventCategory.id == update_data["category_id"]
            )
        )
        if not cat_result.scalars().first():
            raise ValueError(
                f"Category with id {update_data['category_id']} not found"
            )

    event.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(event)

    logger.info(
        "Event updated: id=%s by user_id=%s",
        event.id,
        user_id,
    )
    return event


async def delete_event(
    db: AsyncSession,
    event_id: str,
    user_id: str,
    user_role: str,
) -> None:
    result = await db.execute(
        select(Event)
        .where(Event.id == event_id)
        .options(
            selectinload(Event.ticket_types),
            selectinload(Event.tickets),
            selectinload(Event.rsvps),
        )
    )
    event = result.scalars().first()

    if not event:
        raise LookupError(f"Event with id {event_id} not found")

    if event.organizer_id != user_id and user_role not in ("Admin", "Super Admin"):
        raise PermissionError("You do not have permission to delete this event")

    for rsvp in event.rsvps:
        await db.delete(rsvp)

    for ticket in event.tickets:
        await db.delete(ticket)

    for ticket_type in event.ticket_types:
        await db.delete(ticket_type)

    await db.delete(event)
    await db.flush()

    logger.info(
        "Event deleted: id=%s by user_id=%s",
        event_id,
        user_id,
    )


async def get_event(
    db: AsyncSession,
    event_id: str,
) -> Optional[Event]:
    result = await db.execute(
        select(Event)
        .where(Event.id == event_id)
        .options(
            selectinload(Event.organizer),
            selectinload(Event.category),
            selectinload(Event.ticket_types),
            selectinload(Event.tickets),
            selectinload(Event.rsvps),
        )
    )
    event = result.scalars().first()
    return event


async def search_events(
    db: AsyncSession,
    keyword: Optional[str] = None,
    category_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    query = select(Event).options(
        selectinload(Event.organizer),
        selectinload(Event.category),
        selectinload(Event.ticket_types),
        selectinload(Event.tickets),
    )

    count_query = select(func.count()).select_from(Event)

    if keyword:
        keyword_filter = or_(
            Event.title.ilike(f"%{keyword}%"),
            Event.description.ilike(f"%{keyword}%"),
            Event.city.ilike(f"%{keyword}%"),
            Event.venue_name.ilike(f"%{keyword}%"),
        )
        query = query.where(keyword_filter)
        count_query = count_query.where(keyword_filter)

    if category_id:
        query = query.where(Event.category_id == category_id)
        count_query = count_query.where(Event.category_id == category_id)

    if date_from:
        query = query.where(Event.start_datetime >= date_from)
        count_query = count_query.where(Event.start_datetime >= date_from)

    if date_to:
        query = query.where(Event.start_datetime <= date_to)
        count_query = count_query.where(Event.start_datetime <= date_to)

    if status:
        query = query.where(Event.status == status)
        count_query = count_query.where(Event.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    total_pages = max(1, math.ceil(total / page_size))

    offset = (page - 1) * page_size
    query = query.order_by(Event.start_datetime.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    events = list(result.scalars().all())

    return {
        "items": events,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


async def get_events_by_organizer(
    db: AsyncSession,
    organizer_id: str,
) -> list[Event]:
    result = await db.execute(
        select(Event)
        .where(Event.organizer_id == organizer_id)
        .options(
            selectinload(Event.organizer),
            selectinload(Event.category),
            selectinload(Event.ticket_types),
            selectinload(Event.tickets),
            selectinload(Event.rsvps),
        )
        .order_by(Event.start_datetime.desc())
    )
    events = list(result.scalars().all())
    return events


async def update_event_status(
    db: AsyncSession,
    event_id: str,
    new_status: str,
    user_id: str,
    user_role: str,
) -> Event:
    valid_statuses = {"draft", "published", "cancelled", "completed"}
    if new_status not in valid_statuses:
        raise ValueError(
            f"Invalid status: {new_status}. Must be one of: {', '.join(valid_statuses)}"
        )

    result = await db.execute(
        select(Event)
        .where(Event.id == event_id)
        .options(
            selectinload(Event.organizer),
            selectinload(Event.category),
            selectinload(Event.ticket_types),
        )
    )
    event = result.scalars().first()

    if not event:
        raise LookupError(f"Event with id {event_id} not found")

    if event.organizer_id != user_id and user_role not in ("Admin", "Super Admin"):
        raise PermissionError("You do not have permission to update this event's status")

    event.status = new_status
    event.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(event)

    logger.info(
        "Event status updated: id=%s status=%s by user_id=%s",
        event.id,
        new_status,
        user_id,
    )
    return event


async def get_event_attendees(
    db: AsyncSession,
    event_id: str,
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(Ticket)
        .where(Ticket.event_id == event_id)
        .options(
            selectinload(Ticket.attendee),
            selectinload(Ticket.ticket_type),
        )
    )
    tickets = result.scalars().all()

    attendees = []
    for ticket in tickets:
        attendee_data: dict[str, Any] = {
            "attendee_id": ticket.attendee_id,
            "username": ticket.attendee.username if ticket.attendee else "Unknown",
            "display_name": ticket.attendee.display_name if ticket.attendee else "Unknown",
            "email": ticket.attendee.email if ticket.attendee else "",
            "ticket_type_name": ticket.ticket_type.name if ticket.ticket_type else "General",
            "quantity": ticket.quantity,
            "ticket_status": ticket.status,
            "checked_in": ticket.checked_in,
            "checked_in_at": ticket.checked_in_at,
            "ticket_id": ticket.id,
        }
        attendees.append(attendee_data)

    return attendees


async def get_event_stats(
    db: AsyncSession,
    event_id: str,
) -> dict[str, Any]:
    event = await get_event(db, event_id)
    if not event:
        raise LookupError(f"Event with id {event_id} not found")

    total_tickets_sold = sum(t.quantity for t in event.tickets if t.status == "confirmed")
    total_revenue = sum(t.total_price for t in event.tickets if t.status == "confirmed")
    total_checked_in = sum(1 for t in event.tickets if t.checked_in)

    going_count = sum(1 for r in event.rsvps if r.status == "going")
    maybe_count = sum(1 for r in event.rsvps if r.status == "maybe")
    not_going_count = sum(1 for r in event.rsvps if r.status == "not_going")

    return {
        "total_tickets_sold": total_tickets_sold,
        "total_revenue": total_revenue,
        "total_checked_in": total_checked_in,
        "total_capacity": event.total_capacity,
        "rsvp_counts": {
            "going_count": going_count,
            "maybe_count": maybe_count,
            "not_going_count": not_going_count,
            "total_count": going_count + maybe_count + not_going_count,
        },
    }


async def get_all_categories(
    db: AsyncSession,
) -> list[EventCategory]:
    result = await db.execute(
        select(EventCategory).order_by(EventCategory.name)
    )
    categories = list(result.scalars().all())
    return categories