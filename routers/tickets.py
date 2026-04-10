import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from services import ticket_service
from utils.dependencies import get_db, get_current_user, require_auth

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/events/{event_id}/tickets")
async def claim_ticket_for_event(
    request: Request,
    event_id: str,
    ticket_type_id: str = Form(...),
    quantity: int = Form(1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Claim tickets for an event. Accepts form data from the event detail page."""
    if quantity < 1:
        logger.warning(
            "Invalid ticket quantity %d from user_id=%s for event_id=%s",
            quantity,
            current_user.id,
            event_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity must be at least 1",
        )

    try:
        ticket = await ticket_service.claim_ticket(
            db=db,
            event_id=event_id,
            ticket_type_id=ticket_type_id,
            attendee_id=current_user.id,
            quantity=quantity,
        )
        logger.info(
            "Ticket claimed: ticket_id=%s event_id=%s user_id=%s quantity=%d",
            ticket.id,
            event_id,
            current_user.id,
            quantity,
        )
    except ValueError as e:
        logger.warning(
            "Ticket claim failed for user_id=%s event_id=%s: %s",
            current_user.id,
            event_id,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception:
        logger.exception(
            "Unexpected error claiming ticket for user_id=%s event_id=%s",
            current_user.id,
            event_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while claiming the ticket",
        )

    return RedirectResponse(
        url=f"/events/{event_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/tickets/{ticket_id}/cancel")
async def cancel_ticket(
    request: Request,
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Cancel a ticket. Only the ticket owner can cancel."""
    try:
        ticket = await ticket_service.cancel_ticket(
            db=db,
            ticket_id=ticket_id,
            user_id=current_user.id,
        )
        logger.info(
            "Ticket cancelled: ticket_id=%s user_id=%s",
            ticket_id,
            current_user.id,
        )
    except ValueError as e:
        logger.warning(
            "Ticket cancel failed for user_id=%s ticket_id=%s: %s",
            current_user.id,
            ticket_id,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except PermissionError as e:
        logger.warning(
            "Permission denied cancelling ticket_id=%s for user_id=%s: %s",
            ticket_id,
            current_user.id,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except Exception:
        logger.exception(
            "Unexpected error cancelling ticket_id=%s for user_id=%s",
            ticket_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while cancelling the ticket",
        )

    return RedirectResponse(
        url="/my-tickets",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/my-tickets")
async def my_tickets(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """View all tickets for the current user."""
    from jinja2 import Environment
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(
        directory=str(Path(__file__).resolve().parent.parent / "templates")
    )

    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)

    try:
        tickets = await ticket_service.get_user_tickets(
            db=db,
            user_id=current_user.id,
        )
    except Exception:
        logger.exception(
            "Error fetching tickets for user_id=%s",
            current_user.id,
        )
        tickets = []

    return templates.TemplateResponse(
        request,
        "attendee/my_tickets.html",
        context={
            "user": current_user,
            "tickets": tickets,
        },
    )


@router.get("/api/tickets/{ticket_type_id}/availability")
async def get_ticket_availability(
    ticket_type_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get available ticket count for a ticket type. Returns JSON."""
    try:
        available = await ticket_service.get_ticket_availability(
            db=db,
            ticket_type_id=ticket_type_id,
        )
        return {"ticket_type_id": ticket_type_id, "available": available}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception:
        logger.exception(
            "Error fetching availability for ticket_type_id=%s",
            ticket_type_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )