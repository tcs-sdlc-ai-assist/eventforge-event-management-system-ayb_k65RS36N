import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from typing import AsyncGenerator, Optional

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import SessionLocal
from models.user import User
from utils.security import COOKIE_NAME, decode_access_token

logger = logging.getLogger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    token: Optional[str] = request.cookies.get(COOKIE_NAME)
    if not token:
        return None

    payload = decode_access_token(token)
    if payload is None:
        return None

    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        return None

    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        if user is None:
            return None
        if not user.is_active:
            return None
        return user
    except Exception:
        logger.exception("Error fetching current user from database")
        return None


async def require_auth(
    current_user: Optional[User] = Depends(get_current_user),
) -> User:
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return current_user


def require_role(allowed_roles: list[str]):
    async def role_guard(
        current_user: User = Depends(require_auth),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )
        return current_user

    return role_guard


require_admin = require_role(["Super Admin", "Admin"])

require_organizer = require_role(["Super Admin", "Admin", "Project Manager"])

require_attendee = require_role(["Super Admin", "Admin", "Project Manager", "Developer", "QA", "Viewer"])