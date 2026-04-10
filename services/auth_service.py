import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from utils.security import hash_password, verify_password

logger = logging.getLogger(__name__)


async def register_user(
    db: AsyncSession,
    username: str,
    email: str,
    display_name: str,
    password: str,
    role: str = "Viewer",
) -> User:
    result = await db.execute(
        select(User).where(User.username == username)
    )
    existing_user = result.scalars().first()
    if existing_user is not None:
        raise ValueError(f"Username '{username}' is already taken")

    result = await db.execute(
        select(User).where(User.email == email)
    )
    existing_email = result.scalars().first()
    if existing_email is not None:
        raise ValueError(f"Email '{email}' is already registered")

    hashed = hash_password(password)

    user = User(
        username=username,
        email=email,
        display_name=display_name,
        hashed_password=hashed,
        role=role,
        is_active=True,
    )

    db.add(user)
    await db.flush()
    await db.refresh(user)

    logger.info("Registered new user: %s (role=%s)", username, role)
    return user


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> Optional[User]:
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalars().first()

    if user is None:
        logger.warning("Authentication failed: user '%s' not found", username)
        return None

    if not user.is_active:
        logger.warning("Authentication failed: user '%s' is inactive", username)
        return None

    if not verify_password(password, user.hashed_password):
        logger.warning("Authentication failed: invalid password for user '%s'", username)
        return None

    logger.info("User '%s' authenticated successfully", username)
    return user


async def get_user_by_id(
    db: AsyncSession,
    user_id: str,
) -> Optional[User]:
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalars().first()


async def get_user_by_username(
    db: AsyncSession,
    username: str,
) -> Optional[User]:
    result = await db.execute(
        select(User).where(User.username == username)
    )
    return result.scalars().first()


async def get_user_by_email(
    db: AsyncSession,
    email: str,
) -> Optional[User]:
    result = await db.execute(
        select(User).where(User.email == email)
    )
    return result.scalars().first()