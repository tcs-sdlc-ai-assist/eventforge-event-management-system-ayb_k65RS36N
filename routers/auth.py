import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from utils.dependencies import get_db, get_current_user
from utils.security import create_access_token, COOKIE_NAME
from services.auth_service import register_user, authenticate_user
from models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/register")
async def register_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse(
        request,
        "auth/register.html",
        context={
            "user": None,
            "error": None,
            "errors": None,
            "form_data": None,
            "messages": [],
        },
    )


@router.post("/register")
async def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    display_name: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    role: str = Form("Viewer"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard", status_code=302)

    form_data = {
        "username": username,
        "email": email,
        "display_name": display_name,
        "role": role,
    }
    errors: dict[str, str] = {}

    if len(username.strip()) < 3:
        errors["username"] = "Username must be at least 3 characters long"

    if not display_name.strip():
        errors["display_name"] = "Display name cannot be empty"

    if len(password) < 8:
        errors["password"] = "Password must be at least 8 characters long"

    if password != confirm_password:
        errors["confirm_password"] = "Passwords do not match"

    valid_roles = ["Super Admin", "Admin", "Project Manager", "Developer", "QA", "Viewer"]
    if role not in valid_roles:
        errors["role"] = f"Role must be one of: {', '.join(valid_roles)}"

    if errors:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "user": None,
                "error": None,
                "errors": errors,
                "form_data": form_data,
                "messages": [],
            },
            status_code=422,
        )

    try:
        user = await register_user(
            db=db,
            username=username.strip(),
            email=email.strip(),
            display_name=display_name.strip(),
            password=password,
            role=role,
        )
        await db.commit()
        logger.info("User registered successfully: %s", user.username)

        token = create_access_token(data={"sub": user.id})
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24,
        )
        return response

    except ValueError as e:
        error_msg = str(e)
        logger.warning("Registration failed: %s", error_msg)
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "user": None,
                "error": error_msg,
                "errors": None,
                "form_data": form_data,
                "messages": [],
            },
            status_code=400,
        )
    except Exception:
        logger.exception("Unexpected error during registration")
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "user": None,
                "error": "An unexpected error occurred. Please try again.",
                "errors": None,
                "form_data": form_data,
                "messages": [],
            },
            status_code=500,
        )


@router.get("/login")
async def login_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse(
        request,
        "auth/login.html",
        context={
            "user": None,
            "error": None,
            "username": "",
            "messages": [],
        },
    )


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard", status_code=302)

    if not username.strip():
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            context={
                "user": None,
                "error": "Username cannot be empty",
                "username": username,
                "messages": [],
            },
            status_code=422,
        )

    if not password:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            context={
                "user": None,
                "error": "Password cannot be empty",
                "username": username,
                "messages": [],
            },
            status_code=422,
        )

    try:
        user = await authenticate_user(
            db=db,
            username=username.strip(),
            password=password,
        )

        if user is None:
            logger.warning("Login failed for username: %s", username)
            return templates.TemplateResponse(
                request,
                "auth/login.html",
                context={
                    "user": None,
                    "error": "Invalid username or password",
                    "username": username,
                    "messages": [],
                },
                status_code=401,
            )

        token = create_access_token(data={"sub": user.id})
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24,
        )
        logger.info("User logged in: %s", user.username)
        return response

    except Exception:
        logger.exception("Unexpected error during login")
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            context={
                "user": None,
                "error": "An unexpected error occurred. Please try again.",
                "username": username,
                "messages": [],
            },
            status_code=500,
        )


@router.get("/logout")
async def logout_get(request: Request):
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie(key=COOKIE_NAME)
    logger.info("User logged out via GET")
    return response


@router.post("/logout")
async def logout_post(request: Request):
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie(key=COOKIE_NAME)
    logger.info("User logged out via POST")
    return response