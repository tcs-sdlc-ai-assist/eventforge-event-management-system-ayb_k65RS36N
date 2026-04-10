import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import Base
from models.user import User
from models.event import Event
from models.event_category import EventCategory
from models.ticket import Ticket, TicketType
from models.rsvp import RSVP
from utils.dependencies import get_db, require_admin

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/admin")
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # Gather platform stats
    total_events_result = await db.execute(select(func.count()).select_from(Event))
    total_events = total_events_result.scalar() or 0

    total_users_result = await db.execute(select(func.count()).select_from(User))
    total_users = total_users_result.scalar() or 0

    total_tickets_result = await db.execute(
        select(func.coalesce(func.sum(Ticket.quantity), 0)).where(Ticket.status == "confirmed")
    )
    total_tickets = total_tickets_result.scalar() or 0

    active_organizers_result = await db.execute(
        select(func.count(func.distinct(Event.organizer_id))).select_from(Event)
    )
    active_organizers = active_organizers_result.scalar() or 0

    stats = {
        "total_events": total_events,
        "total_users": total_users,
        "total_tickets": total_tickets,
        "active_organizers": active_organizers,
    }

    # Fetch all users
    users_result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    users = list(users_result.scalars().all())

    # Fetch recent events with organizer info
    events_result = await db.execute(
        select(Event)
        .options(selectinload(Event.organizer))
        .order_by(Event.created_at.desc())
        .limit(20)
    )
    events_raw = list(events_result.scalars().all())

    events = []
    for ev in events_raw:
        events.append({
            "id": ev.id,
            "title": ev.title,
            "organizer_name": ev.organizer.display_name if ev.organizer else "Unknown",
            "start_datetime": ev.start_datetime,
            "capacity": ev.total_capacity,
            "status": ev.status,
        })

    # Fetch categories with event counts
    categories_result = await db.execute(
        select(EventCategory).order_by(EventCategory.name)
    )
    categories_raw = list(categories_result.scalars().all())

    categories = []
    for cat in categories_raw:
        event_count_result = await db.execute(
            select(func.count()).select_from(Event).where(Event.category_id == cat.id)
        )
        event_count = event_count_result.scalar() or 0
        categories.append({
            "id": cat.id,
            "name": cat.name,
            "color": cat.color or "#6366f1",
            "icon": cat.icon or "",
            "event_count": event_count,
        })

    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        context={
            "user": current_user,
            "stats": stats,
            "users": users,
            "events": events,
            "categories": categories,
            "messages": [],
        },
    )


@router.post("/admin/categories/create")
async def admin_create_category(
    request: Request,
    name: str = Form(...),
    color: Optional[str] = Form(None),
    color_hex: Optional[str] = Form(None),
    icon: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # Use color_hex if color is not provided or use color
    final_color = color or color_hex or "#6366f1"

    # Check for duplicate name
    existing_result = await db.execute(
        select(EventCategory).where(EventCategory.name == name.strip())
    )
    existing = existing_result.scalars().first()
    if existing:
        logger.warning("Attempted to create duplicate category: %s", name)
        return RedirectResponse(url="/admin", status_code=303)

    category = EventCategory(
        name=name.strip(),
        color=final_color,
        icon=icon.strip() if icon else None,
    )
    db.add(category)
    await db.flush()

    logger.info("Category created: id=%s name=%s by user_id=%s", category.id, category.name, current_user.id)
    return RedirectResponse(url="/admin", status_code=303)


@router.get("/admin/categories/{category_id}/edit")
async def admin_edit_category_form(
    request: Request,
    category_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(
        select(EventCategory).where(EventCategory.id == category_id)
    )
    category = result.scalars().first()
    if not category:
        return RedirectResponse(url="/admin", status_code=303)

    return RedirectResponse(url="/admin", status_code=303)


@router.post("/admin/categories/{category_id}/edit")
async def admin_edit_category(
    request: Request,
    category_id: str,
    name: str = Form(...),
    color: Optional[str] = Form(None),
    color_hex: Optional[str] = Form(None),
    icon: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(
        select(EventCategory).where(EventCategory.id == category_id)
    )
    category = result.scalars().first()
    if not category:
        logger.warning("Category not found for edit: id=%s", category_id)
        return RedirectResponse(url="/admin", status_code=303)

    final_color = color or color_hex or category.color or "#6366f1"

    # Check for duplicate name (excluding current category)
    if name.strip() != category.name:
        dup_result = await db.execute(
            select(EventCategory).where(
                EventCategory.name == name.strip(),
                EventCategory.id != category_id,
            )
        )
        duplicate = dup_result.scalars().first()
        if duplicate:
            logger.warning("Duplicate category name on edit: %s", name)
            return RedirectResponse(url="/admin", status_code=303)

    category.name = name.strip()
    category.color = final_color
    category.icon = icon.strip() if icon else None

    await db.flush()

    logger.info("Category updated: id=%s name=%s by user_id=%s", category.id, category.name, current_user.id)
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/admin/categories/{category_id}/delete")
async def admin_delete_category(
    request: Request,
    category_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(
        select(EventCategory).where(EventCategory.id == category_id)
    )
    category = result.scalars().first()
    if not category:
        logger.warning("Category not found for delete: id=%s", category_id)
        return RedirectResponse(url="/admin", status_code=303)

    # Unlink events from this category
    events_result = await db.execute(
        select(Event).where(Event.category_id == category_id)
    )
    events = events_result.scalars().all()
    for ev in events:
        ev.category_id = None

    await db.flush()
    await db.delete(category)
    await db.flush()

    logger.info("Category deleted: id=%s name=%s by user_id=%s", category_id, category.name, current_user.id)
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/admin/users/{user_id}/delete")
async def admin_delete_user(
    request: Request,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalars().first()
    if not user:
        logger.warning("User not found for delete: id=%s", user_id)
        return RedirectResponse(url="/admin", status_code=303)

    # Protect admin users from deletion
    if user.role in ("Super Admin", "Admin"):
        logger.warning("Attempted to delete protected user: id=%s role=%s", user_id, user.role)
        return RedirectResponse(url="/admin", status_code=303)

    # Delete user's RSVPs
    rsvps_result = await db.execute(
        select(RSVP).where(RSVP.user_id == user_id)
    )
    for rsvp in rsvps_result.scalars().all():
        await db.delete(rsvp)

    # Delete user's tickets and update sold counts
    tickets_result = await db.execute(
        select(Ticket).where(Ticket.attendee_id == user_id).options(selectinload(Ticket.ticket_type))
    )
    for ticket in tickets_result.scalars().all():
        if ticket.ticket_type and ticket.status == "confirmed":
            ticket.ticket_type.sold = max(0, ticket.ticket_type.sold - ticket.quantity)
        await db.delete(ticket)

    # Delete user's events (and their related data)
    events_result = await db.execute(
        select(Event)
        .where(Event.organizer_id == user_id)
        .options(
            selectinload(Event.ticket_types),
            selectinload(Event.tickets),
            selectinload(Event.rsvps),
        )
    )
    for event in events_result.scalars().all():
        for rsvp in event.rsvps:
            await db.delete(rsvp)
        for ticket in event.tickets:
            await db.delete(ticket)
        for tt in event.ticket_types:
            await db.delete(tt)
        await db.delete(event)

    await db.flush()
    await db.delete(user)
    await db.flush()

    logger.info("User deleted: id=%s username=%s by admin user_id=%s", user_id, user.username, current_user.id)
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/admin/events/{event_id}/delete")
async def admin_delete_event(
    request: Request,
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
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
        logger.warning("Event not found for admin delete: id=%s", event_id)
        return RedirectResponse(url="/admin", status_code=303)

    for rsvp in event.rsvps:
        await db.delete(rsvp)
    for ticket in event.tickets:
        await db.delete(ticket)
    for tt in event.ticket_types:
        await db.delete(tt)

    await db.delete(event)
    await db.flush()

    logger.info("Event deleted by admin: id=%s by user_id=%s", event_id, current_user.id)
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/admin/events/{event_id}/publish")
async def admin_publish_event(
    request: Request,
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(
        select(Event).where(Event.id == event_id)
    )
    event = result.scalars().first()
    if not event:
        logger.warning("Event not found for publish: id=%s", event_id)
        return RedirectResponse(url="/admin", status_code=303)

    event.status = "published"
    await db.flush()

    logger.info("Event published by admin: id=%s by user_id=%s", event_id, current_user.id)
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/admin/events/{event_id}/cancel")
async def admin_cancel_event(
    request: Request,
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(
        select(Event).where(Event.id == event_id)
    )
    event = result.scalars().first()
    if not event:
        logger.warning("Event not found for cancel: id=%s", event_id)
        return RedirectResponse(url="/admin", status_code=303)

    event.status = "cancelled"
    await db.flush()

    logger.info("Event cancelled by admin: id=%s by user_id=%s", event_id, current_user.id)
    return RedirectResponse(url="/admin", status_code=303)