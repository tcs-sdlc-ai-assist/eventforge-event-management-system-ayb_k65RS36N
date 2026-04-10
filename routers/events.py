import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from services.event_service import (
    create_event,
    delete_event,
    edit_event,
    get_all_categories,
    get_event,
    get_event_attendees,
    get_event_stats,
    search_events,
)
from services.rsvp_service import get_rsvp_counts, get_user_rsvp, set_rsvp
from services.ticket_service import claim_ticket, get_total_tickets_sold, toggle_checkin
from utils.dependencies import get_current_user, get_db, require_auth

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/events")
async def browse_events(
    request: Request,
    keyword: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    parsed_date_from = None
    parsed_date_to = None

    if date_from:
        try:
            parsed_date_from = datetime.fromisoformat(date_from)
        except (ValueError, TypeError):
            parsed_date_from = None

    if date_to:
        try:
            parsed_date_to = datetime.fromisoformat(date_to)
        except (ValueError, TypeError):
            parsed_date_to = None

    result = await search_events(
        db=db,
        keyword=keyword,
        category_id=category,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        status=status,
        page=page,
        page_size=page_size,
    )

    categories = await get_all_categories(db)

    events_list = []
    for event in result["items"]:
        tickets_sold = 0
        try:
            tickets_sold = await get_total_tickets_sold(db, event.id)
        except Exception:
            pass

        events_list.append(
            {
                "id": event.id,
                "title": event.title,
                "description": event.description,
                "category_id": event.category_id,
                "organizer_id": event.organizer_id,
                "venue_name": event.venue_name,
                "venue_city": event.city,
                "venue_country": event.country,
                "start_datetime": event.start_datetime,
                "end_datetime": event.end_datetime,
                "capacity": event.total_capacity,
                "status": event.status,
                "created_at": event.created_at,
                "updated_at": event.updated_at,
                "tickets_sold": tickets_sold,
            }
        )

    return templates.TemplateResponse(
        request,
        "events/browse.html",
        context={
            "user": current_user,
            "events": events_list,
            "categories": categories,
            "keyword": keyword or "",
            "category": category or "",
            "status": status or "",
            "date_from": date_from or "",
            "date_to": date_to or "",
            "page": result["page"],
            "page_size": result["page_size"],
            "total": result["total"],
            "total_pages": result["total_pages"],
            "messages": [],
        },
    )


@router.get("/events/create")
async def create_event_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    categories = await get_all_categories(db)

    return templates.TemplateResponse(
        request,
        "events/form.html",
        context={
            "user": current_user,
            "event": None,
            "ticket_types": None,
            "categories": categories,
            "messages": [],
        },
    )


@router.post("/events/create")
async def handle_create_event(
    request: Request,
    title: str = Form(...),
    venue_name: str = Form(...),
    venue_address: str = Form(...),
    venue_city: str = Form(...),
    venue_country: str = Form(...),
    start_datetime: str = Form(...),
    end_datetime: str = Form(...),
    capacity: int = Form(...),
    description: Optional[str] = Form(None),
    category_id: Optional[str] = Form(None),
    venue_state: Optional[str] = Form(None),
    venue_zip_code: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    try:
        parsed_start = datetime.fromisoformat(start_datetime)
        parsed_end = datetime.fromisoformat(end_datetime)
    except (ValueError, TypeError) as e:
        categories = await get_all_categories(db)
        return templates.TemplateResponse(
            request,
            "events/form.html",
            context={
                "user": current_user,
                "event": None,
                "ticket_types": None,
                "categories": categories,
                "messages": [{"type": "error", "text": f"Invalid date format: {e}"}],
            },
        )

    form_data = await request.form()
    ticket_types_data = _extract_ticket_types_from_form(form_data)

    cat_id = category_id if category_id and category_id.strip() else None

    try:
        event = await create_event(
            db=db,
            organizer_id=current_user.id,
            title=title.strip(),
            description=description.strip() if description else None,
            category_id=cat_id,
            venue_name=venue_name.strip(),
            address_line=venue_address.strip(),
            city=venue_city.strip(),
            state=venue_state.strip() if venue_state else None,
            country=venue_country.strip(),
            start_datetime=parsed_start,
            end_datetime=parsed_end,
            total_capacity=capacity,
            ticket_types_data=ticket_types_data,
        )
        return RedirectResponse(url=f"/events/{event.id}", status_code=303)
    except (ValueError, LookupError) as e:
        categories = await get_all_categories(db)
        return templates.TemplateResponse(
            request,
            "events/form.html",
            context={
                "user": current_user,
                "event": None,
                "ticket_types": None,
                "categories": categories,
                "messages": [{"type": "error", "text": str(e)}],
            },
        )


@router.get("/events/{event_id}")
async def event_detail(
    request: Request,
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    event = await get_event(db, event_id)
    if not event:
        return templates.TemplateResponse(
            request,
            "404.html",
            context={"user": current_user, "messages": []},
            status_code=404,
        )

    organizer_name = "Unknown"
    if event.organizer:
        organizer_name = event.organizer.display_name or event.organizer.username

    category_name = None
    if event.category:
        category_name = event.category.name

    ticket_types = []
    for tt in event.ticket_types:
        ticket_types.append(
            {
                "id": tt.id,
                "name": tt.name,
                "price": float(tt.price),
                "quantity": tt.quantity,
                "sold": tt.sold,
                "description": getattr(tt, "description", None),
            }
        )

    rsvp_counts = await get_rsvp_counts(db, event_id)

    current_rsvp = None
    if current_user:
        user_rsvp = await get_user_rsvp(db, event_id, current_user.id)
        if user_rsvp:
            current_rsvp = user_rsvp.status

    total_tickets_sold_count = await get_total_tickets_sold(db, event_id)

    attendees = []
    if current_user and (
        current_user.id == event.organizer_id
        or current_user.role in ("Admin", "Super Admin")
    ):
        attendees = await get_event_attendees(db, event_id)

    event_data = {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "category_id": event.category_id,
        "category_name": category_name,
        "organizer_id": event.organizer_id,
        "venue_name": event.venue_name,
        "venue_address": event.address_line,
        "venue_city": event.city,
        "venue_state": event.state,
        "venue_country": event.country,
        "venue_zip_code": None,
        "start_datetime": event.start_datetime,
        "end_datetime": event.end_datetime,
        "capacity": event.total_capacity,
        "total_capacity": event.total_capacity,
        "status": event.status,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }

    messages = []
    flash_msg = request.cookies.get("flash_message")
    flash_type = request.cookies.get("flash_type", "info")
    if flash_msg:
        messages.append({"type": flash_type, "text": flash_msg})

    response = templates.TemplateResponse(
        request,
        "events/detail.html",
        context={
            "user": current_user,
            "event": type("Event", (), event_data)(),
            "organizer_name": organizer_name,
            "ticket_types": ticket_types,
            "rsvp_counts": rsvp_counts,
            "current_rsvp": current_rsvp,
            "total_tickets_sold": total_tickets_sold_count,
            "attendees": attendees,
            "messages": messages,
        },
    )

    if flash_msg:
        response.delete_cookie("flash_message")
        response.delete_cookie("flash_type")

    return response


@router.get("/events/{event_id}/edit")
async def edit_event_form(
    request: Request,
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    event = await get_event(db, event_id)
    if not event:
        return templates.TemplateResponse(
            request,
            "404.html",
            context={"user": current_user, "messages": []},
            status_code=404,
        )

    if event.organizer_id != current_user.id and current_user.role not in (
        "Admin",
        "Super Admin",
    ):
        return RedirectResponse(url=f"/events/{event_id}", status_code=303)

    categories = await get_all_categories(db)

    ticket_types = []
    for tt in event.ticket_types:
        ticket_types.append(
            {
                "id": tt.id,
                "name": tt.name,
                "price": float(tt.price),
                "quantity": tt.quantity,
                "sold": tt.sold,
                "description": getattr(tt, "description", None),
            }
        )

    event_data = {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "category_id": event.category_id,
        "organizer_id": event.organizer_id,
        "venue_name": event.venue_name,
        "venue_address": event.address_line,
        "venue_city": event.city,
        "venue_state": event.state,
        "venue_country": event.country,
        "venue_zip_code": None,
        "start_datetime": event.start_datetime,
        "end_datetime": event.end_datetime,
        "capacity": event.total_capacity,
        "status": event.status,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }

    return templates.TemplateResponse(
        request,
        "events/form.html",
        context={
            "user": current_user,
            "event": type("Event", (), event_data)(),
            "ticket_types": ticket_types,
            "categories": categories,
            "messages": [],
        },
    )


@router.post("/events/{event_id}/edit")
async def handle_edit_event(
    request: Request,
    event_id: str,
    title: str = Form(...),
    venue_name: str = Form(...),
    venue_address: str = Form(...),
    venue_city: str = Form(...),
    venue_country: str = Form(...),
    start_datetime: str = Form(...),
    end_datetime: str = Form(...),
    capacity: int = Form(...),
    description: Optional[str] = Form(None),
    category_id: Optional[str] = Form(None),
    venue_state: Optional[str] = Form(None),
    venue_zip_code: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    try:
        parsed_start = datetime.fromisoformat(start_datetime)
        parsed_end = datetime.fromisoformat(end_datetime)
    except (ValueError, TypeError) as e:
        categories = await get_all_categories(db)
        return templates.TemplateResponse(
            request,
            "events/form.html",
            context={
                "user": current_user,
                "event": None,
                "ticket_types": None,
                "categories": categories,
                "messages": [{"type": "error", "text": f"Invalid date format: {e}"}],
            },
        )

    cat_id = category_id if category_id and category_id.strip() else None

    update_data = {
        "title": title.strip(),
        "description": description.strip() if description else None,
        "category_id": cat_id,
        "venue_name": venue_name.strip(),
        "address_line": venue_address.strip(),
        "city": venue_city.strip(),
        "state": venue_state.strip() if venue_state else None,
        "country": venue_country.strip(),
        "start_datetime": parsed_start,
        "end_datetime": parsed_end,
        "total_capacity": capacity,
    }

    if status and status.strip():
        update_data["status"] = status.strip()

    try:
        await edit_event(
            db=db,
            event_id=event_id,
            user_id=current_user.id,
            user_role=current_user.role,
            update_data=update_data,
        )
        return RedirectResponse(url=f"/events/{event_id}", status_code=303)
    except (ValueError, LookupError) as e:
        categories = await get_all_categories(db)
        event = await get_event(db, event_id)
        event_obj = None
        ticket_types_list = None
        if event:
            event_obj = type(
                "Event",
                (),
                {
                    "id": event.id,
                    "title": event.title,
                    "description": event.description,
                    "category_id": event.category_id,
                    "organizer_id": event.organizer_id,
                    "venue_name": event.venue_name,
                    "venue_address": event.address_line,
                    "venue_city": event.city,
                    "venue_state": event.state,
                    "venue_country": event.country,
                    "venue_zip_code": None,
                    "start_datetime": event.start_datetime,
                    "end_datetime": event.end_datetime,
                    "capacity": event.total_capacity,
                    "status": event.status,
                    "created_at": event.created_at,
                    "updated_at": event.updated_at,
                },
            )()
            ticket_types_list = [
                {
                    "id": tt.id,
                    "name": tt.name,
                    "price": float(tt.price),
                    "quantity": tt.quantity,
                    "sold": tt.sold,
                }
                for tt in event.ticket_types
            ]
        return templates.TemplateResponse(
            request,
            "events/form.html",
            context={
                "user": current_user,
                "event": event_obj,
                "ticket_types": ticket_types_list,
                "categories": categories,
                "messages": [{"type": "error", "text": str(e)}],
            },
        )
    except PermissionError as e:
        return RedirectResponse(url=f"/events/{event_id}", status_code=303)


@router.post("/events/{event_id}/delete")
async def handle_delete_event(
    request: Request,
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    try:
        await delete_event(
            db=db,
            event_id=event_id,
            user_id=current_user.id,
            user_role=current_user.role,
        )
        return RedirectResponse(url="/events", status_code=303)
    except LookupError:
        return templates.TemplateResponse(
            request,
            "404.html",
            context={"user": current_user, "messages": []},
            status_code=404,
        )
    except PermissionError:
        return RedirectResponse(url=f"/events/{event_id}", status_code=303)


@router.post("/events/{event_id}/rsvp")
async def handle_rsvp(
    request: Request,
    event_id: str,
    status: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    try:
        await set_rsvp(
            db=db,
            event_id=event_id,
            user_id=current_user.id,
            status=status,
        )
    except ValueError as e:
        logger.warning("RSVP error: %s", e)

    return RedirectResponse(url=f"/events/{event_id}", status_code=303)


@router.post("/events/{event_id}/tickets")
async def handle_claim_ticket(
    request: Request,
    event_id: str,
    ticket_type_id: str = Form(...),
    quantity: int = Form(1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    try:
        await claim_ticket(
            db=db,
            event_id=event_id,
            ticket_type_id=ticket_type_id,
            attendee_id=current_user.id,
            quantity=quantity,
        )
        response = RedirectResponse(url=f"/events/{event_id}", status_code=303)
        response.set_cookie("flash_message", "Ticket claimed successfully!", max_age=10)
        response.set_cookie("flash_type", "success", max_age=10)
        return response
    except ValueError as e:
        response = RedirectResponse(url=f"/events/{event_id}", status_code=303)
        response.set_cookie("flash_message", str(e), max_age=10)
        response.set_cookie("flash_type", "error", max_age=10)
        return response
    except PermissionError as e:
        response = RedirectResponse(url=f"/events/{event_id}", status_code=303)
        response.set_cookie("flash_message", str(e), max_age=10)
        response.set_cookie("flash_type", "error", max_age=10)
        return response


@router.post("/events/{event_id}/checkin/{attendee_id}")
async def handle_checkin(
    request: Request,
    event_id: str,
    attendee_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    event = await get_event(db, event_id)
    if not event:
        return templates.TemplateResponse(
            request,
            "404.html",
            context={"user": current_user, "messages": []},
            status_code=404,
        )

    if event.organizer_id != current_user.id and current_user.role not in (
        "Admin",
        "Super Admin",
    ):
        return RedirectResponse(url=f"/events/{event_id}", status_code=303)

    try:
        result = await toggle_checkin(
            db=db,
            event_id=event_id,
            attendee_id=attendee_id,
        )
        checked_in_status = result.get("checked_in", False)
        msg = "Attendee checked in successfully!" if checked_in_status else "Check-in undone."
        response = RedirectResponse(url=f"/events/{event_id}", status_code=303)
        response.set_cookie("flash_message", msg, max_age=10)
        response.set_cookie("flash_type", "success", max_age=10)
        return response
    except ValueError as e:
        response = RedirectResponse(url=f"/events/{event_id}", status_code=303)
        response.set_cookie("flash_message", str(e), max_age=10)
        response.set_cookie("flash_type", "error", max_age=10)
        return response


def _extract_ticket_types_from_form(form_data) -> list[dict]:
    ticket_types = []
    index = 0
    while True:
        name_key = f"ticket_type_name_{index}"
        price_key = f"ticket_type_price_{index}"
        quantity_key = f"ticket_type_quantity_{index}"

        name_val = form_data.get(name_key)
        if name_val is None:
            break

        name_str = str(name_val).strip()
        if not name_str:
            index += 1
            continue

        try:
            price_val = float(form_data.get(price_key, 0))
        except (ValueError, TypeError):
            price_val = 0.0

        try:
            quantity_val = int(form_data.get(quantity_key, 1))
        except (ValueError, TypeError):
            quantity_val = 1

        if quantity_val < 1:
            quantity_val = 1

        ticket_types.append(
            {
                "name": name_str,
                "price": price_val,
                "quantity": quantity_val,
            }
        )
        index += 1

    return ticket_types