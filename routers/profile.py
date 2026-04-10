import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.user import User
from models.event import Event
from models.ticket import Ticket
from models.rsvp import RSVP
from utils.dependencies import get_db, get_current_user, require_auth

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/profile")
async def profile_page(
    request: Request,
    current_user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    organizer_stats = None
    attendee_stats = None
    recent_events = []

    # Organizer stats: events created by this user
    events_result = await db.execute(
        select(Event)
        .where(Event.organizer_id == current_user.id)
        .options(
            selectinload(Event.tickets),
            selectinload(Event.ticket_types),
        )
        .order_by(Event.start_datetime.desc())
    )
    organizer_events = list(events_result.scalars().all())

    if organizer_events:
        total_events = len(organizer_events)
        total_tickets_sold = 0
        total_revenue = 0.0

        for event in organizer_events:
            for ticket in event.tickets:
                if ticket.status == "confirmed":
                    total_tickets_sold += ticket.quantity
                    total_revenue += ticket.total_price

        organizer_stats = {
            "total_events": total_events,
            "total_tickets_sold": total_tickets_sold,
            "total_revenue": total_revenue,
        }

        # Use organizer events as recent events
        for event in organizer_events[:5]:
            recent_events.append({
                "id": event.id,
                "title": event.title,
                "venue_city": event.city,
                "venue_country": event.country,
                "start_datetime": event.start_datetime,
                "status": event.status,
            })

    # Attendee stats: tickets purchased by this user
    tickets_result = await db.execute(
        select(Ticket)
        .where(Ticket.attendee_id == current_user.id)
        .options(
            selectinload(Ticket.event),
        )
    )
    user_tickets = list(tickets_result.scalars().all())

    if user_tickets:
        total_tickets = len(user_tickets)
        now = datetime.now(timezone.utc)
        upcoming_events = 0
        past_events = 0
        seen_event_ids_upcoming = set()
        seen_event_ids_past = set()

        for ticket in user_tickets:
            if ticket.status == "confirmed" and ticket.event:
                if ticket.event.start_datetime and ticket.event.start_datetime.replace(tzinfo=timezone.utc) > now:
                    if ticket.event_id not in seen_event_ids_upcoming:
                        upcoming_events += 1
                        seen_event_ids_upcoming.add(ticket.event_id)
                else:
                    if ticket.event_id not in seen_event_ids_past:
                        past_events += 1
                        seen_event_ids_past.add(ticket.event_id)

        attendee_stats = {
            "total_tickets": total_tickets,
            "upcoming_events": upcoming_events,
            "past_events": past_events,
        }

        # If no organizer events, use attended events as recent
        if not recent_events:
            seen_ids = set()
            for ticket in user_tickets[:5]:
                if ticket.event and ticket.event_id not in seen_ids:
                    seen_ids.add(ticket.event_id)
                    recent_events.append({
                        "id": ticket.event.id,
                        "title": ticket.event.title,
                        "venue_city": ticket.event.city,
                        "venue_country": ticket.event.country,
                        "start_datetime": ticket.event.start_datetime,
                        "status": ticket.event.status,
                    })

    return templates.TemplateResponse(
        request,
        "profile/index.html",
        context={
            "user": current_user,
            "organizer_stats": organizer_stats,
            "attendee_stats": attendee_stats,
            "recent_events": recent_events,
            "current_year": datetime.now(timezone.utc).year,
            "messages": [],
        },
    )