import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import Base, engine, SessionLocal
from utils.dependencies import get_current_user, get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up EventForge...")

    # Create all database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified.")

    # Run seed data
    try:
        from seed import run_seed
        await run_seed()
        logger.info("Seed data applied.")
    except Exception:
        logger.exception("Seed data failed (non-fatal, continuing startup).")

    yield

    logger.info("Shutting down EventForge...")
    await engine.dispose()


app = FastAPI(
    title="EventForge",
    description="A modern event management platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Include routers
from routers.auth import router as auth_router
from routers.events import router as events_router
from routers.tickets import router as tickets_router
from routers.organizer import router as organizer_router
from routers.attendee import router as attendee_router
from routers.admin import router as admin_router
from routers.profile import router as profile_router

app.include_router(auth_router)
app.include_router(events_router)
app.include_router(admin_router)
app.include_router(organizer_router)
app.include_router(attendee_router)
app.include_router(profile_router)
app.include_router(tickets_router)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception):
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        # Try to get current user for the template context
        current_user = None
        try:
            async with SessionLocal() as db:
                try:
                    from sqlalchemy import select
                    from models.user import User
                    from utils.security import COOKIE_NAME, decode_access_token

                    token = request.cookies.get(COOKIE_NAME)
                    if token:
                        payload = decode_access_token(token)
                        if payload:
                            user_id = payload.get("sub")
                            if user_id:
                                result = await db.execute(select(User).where(User.id == user_id))
                                current_user = result.scalars().first()
                except Exception:
                    pass
        except Exception:
            pass

        return templates.TemplateResponse(
            request,
            "404.html",
            context={
                "user": current_user,
                "messages": [],
            },
            status_code=404,
        )
    return HTMLResponse(content="Not Found", status_code=404)


@app.get("/")
async def home(request: Request):
    current_user = None
    try:
        async with SessionLocal() as db:
            try:
                from sqlalchemy import select
                from models.user import User
                from utils.security import COOKIE_NAME, decode_access_token

                token = request.cookies.get(COOKIE_NAME)
                if token:
                    payload = decode_access_token(token)
                    if payload:
                        user_id = payload.get("sub")
                        if user_id:
                            result = await db.execute(select(User).where(User.id == user_id))
                            current_user = result.scalars().first()
            except Exception:
                pass
    except Exception:
        pass

    if current_user is not None:
        return RedirectResponse(url="/events", status_code=302)

    return RedirectResponse(url="/events", status_code=302)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "eventforge"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)