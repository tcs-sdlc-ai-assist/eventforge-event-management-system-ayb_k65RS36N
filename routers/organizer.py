import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from services import event_service, ticket_service
from utils.dependencies import get_db, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/dashboard", response_class=HTMLResponse)
async def organizer_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> Response:
    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=302)

    allowed_roles = ["Super Admin", "Admin", "Project Manager"]
    if current_user.role not in allowed_roles:
        return RedirectResponse(url="/events", status_code=302)

    organizer_events = await event_service.get_events_by_organizer(db, current_user.id)

    total_events = len(organizer_events)
    now = datetime.now(timezone.utc)
    upcoming_events = sum(
        1
        for e in organizer_events
        if e.status == "published" and e.start_datetime and e.start_datetime > now
    )

    total_attendees = 0
    total_revenue = 0.0

    events_with_details = []
    for event in organizer_events:
        event_tickets_sold = await ticket_service.get_total_tickets_sold(db, event.id)
        event_revenue = await ticket_service.get_total_revenue(db, event.id)
        event_attendees_data = await event_service.get_event_attendees(db, event.id)

        total_attendees += event_tickets_sold
        total_revenue += event_revenue

        checked_in_count = sum(
            1 for a in event_attendees_data if a.get("checked_in", False)
        )

        event_detail = {
            "id": event.id,
            "title": event.title,
            "description": event.description,
            "start_datetime": event.start_datetime,
            "end_datetime": event.end_datetime,
            "venue_name": event.venue_name,
            "venue_city": event.city,
            "venue_country": event.country,
            "status": event.status,
            "capacity": event.total_capacity,
            "attendee_count": event_tickets_sold,
            "revenue": event_revenue,
            "checked_in_count": checked_in_count,
            "attendees": [
                {
                    "username": a.get("username", "Unknown"),
                    "display_name": a.get("display_name", "Unknown"),
                    "email": a.get("email", ""),
                    "ticket_type": a.get("ticket_type_name", "General"),
                    "quantity": a.get("quantity", 1),
                    "checked_in": a.get("checked_in", False),
                    "checked_in_at": a.get("checked_in_at"),
                }
                for a in event_attendees_data
            ],
        }
        events_with_details.append(event_detail)

    stats = {
        "total_events": total_events,
        "upcoming_events": upcoming_events,
        "total_attendees": total_attendees,
        "total_revenue": total_revenue,
    }

    return templates.TemplateResponse(
        request,
        "organizer/dashboard.html",
        context={
            "user": current_user,
            "stats": stats,
            "events": events_with_details,
            "messages": [],
        },
    )