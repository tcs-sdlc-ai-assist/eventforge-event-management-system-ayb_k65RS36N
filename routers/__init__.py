import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from routers.auth import router as auth_router
from routers.events import router as events_router
from routers.tickets import router as tickets_router
from routers.organizer import router as organizer_router
from routers.attendee import router as attendee_router
from routers.admin import router as admin_router
from routers.profile import router as profile_router

__all__ = [
    "auth_router",
    "events_router",
    "tickets_router",
    "organizer_router",
    "attendee_router",
    "admin_router",
    "profile_router",
]