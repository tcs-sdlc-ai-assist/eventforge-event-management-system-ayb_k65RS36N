import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from services.ticket_service import get_user_tickets
from utils.dependencies import get_db, require_auth

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/my-tickets", response_class=HTMLResponse)
async def my_tickets(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    try:
        tickets = await get_user_tickets(db=db, user_id=current_user.id)
    except Exception:
        logger.exception("Error fetching tickets for user_id=%s", current_user.id)
        tickets = []

    return templates.TemplateResponse(
        request,
        "attendee/my_tickets.html",
        context={
            "user": current_user,
            "tickets": tickets,
            "messages": [],
        },
    )