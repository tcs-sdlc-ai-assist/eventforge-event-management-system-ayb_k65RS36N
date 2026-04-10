import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.rsvp import RSVP

logger = logging.getLogger(__name__)


async def set_rsvp(
    db: AsyncSession,
    event_id: str,
    user_id: str,
    status: str,
) -> RSVP:
    """Create or update an RSVP for a user on an event.

    Enforces unique constraint on (event_id, user_id) by upserting.
    Valid statuses: going, maybe, not_going.
    """
    valid_statuses = {"going", "maybe", "not_going"}
    if status not in valid_statuses:
        raise ValueError(f"Invalid RSVP status: {status}. Must be one of: {', '.join(valid_statuses)}")

    result = await db.execute(
        select(RSVP).where(
            RSVP.event_id == event_id,
            RSVP.user_id == user_id,
        )
    )
    existing_rsvp = result.scalars().first()

    if existing_rsvp is not None:
        existing_rsvp.status = status
        logger.info(
            "Updated RSVP for user_id=%s on event_id=%s to status=%s",
            user_id,
            event_id,
            status,
        )
        await db.flush()
        await db.refresh(existing_rsvp)
        return existing_rsvp

    new_rsvp = RSVP(
        event_id=event_id,
        user_id=user_id,
        status=status,
    )
    db.add(new_rsvp)
    logger.info(
        "Created RSVP for user_id=%s on event_id=%s with status=%s",
        user_id,
        event_id,
        status,
    )
    await db.flush()
    await db.refresh(new_rsvp)
    return new_rsvp


async def get_rsvp_counts(
    db: AsyncSession,
    event_id: str,
) -> dict[str, int]:
    """Get RSVP counts for an event grouped by status.

    Returns a dict with keys: going_count, maybe_count, not_going_count, total_count.
    """
    result = await db.execute(
        select(RSVP.status, func.count(RSVP.id).label("count"))
        .where(RSVP.event_id == event_id)
        .group_by(RSVP.status)
    )
    rows = result.all()

    counts = {
        "going_count": 0,
        "maybe_count": 0,
        "not_going_count": 0,
        "total_count": 0,
    }

    for row in rows:
        status_value = row[0]
        count_value = row[1]
        if status_value == "going":
            counts["going_count"] = count_value
        elif status_value == "maybe":
            counts["maybe_count"] = count_value
        elif status_value == "not_going":
            counts["not_going_count"] = count_value

    counts["total_count"] = (
        counts["going_count"] + counts["maybe_count"] + counts["not_going_count"]
    )

    logger.debug(
        "RSVP counts for event_id=%s: %s",
        event_id,
        counts,
    )
    return counts


async def get_user_rsvp(
    db: AsyncSession,
    event_id: str,
    user_id: str,
) -> Optional[RSVP]:
    """Get the current user's RSVP for a specific event.

    Returns the RSVP object if found, otherwise None.
    """
    result = await db.execute(
        select(RSVP).where(
            RSVP.event_id == event_id,
            RSVP.user_id == user_id,
        )
    )
    rsvp = result.scalars().first()

    if rsvp is not None:
        logger.debug(
            "Found RSVP for user_id=%s on event_id=%s with status=%s",
            user_id,
            event_id,
            rsvp.status,
        )
    else:
        logger.debug(
            "No RSVP found for user_id=%s on event_id=%s",
            user_id,
            event_id,
        )

    return rsvp


async def delete_rsvp(
    db: AsyncSession,
    event_id: str,
    user_id: str,
) -> bool:
    """Delete a user's RSVP for a specific event.

    Returns True if an RSVP was deleted, False if none existed.
    """
    result = await db.execute(
        select(RSVP).where(
            RSVP.event_id == event_id,
            RSVP.user_id == user_id,
        )
    )
    existing_rsvp = result.scalars().first()

    if existing_rsvp is None:
        logger.debug(
            "No RSVP to delete for user_id=%s on event_id=%s",
            user_id,
            event_id,
        )
        return False

    await db.delete(existing_rsvp)
    await db.flush()
    logger.info(
        "Deleted RSVP for user_id=%s on event_id=%s",
        user_id,
        event_id,
    )
    return True


async def get_event_rsvps(
    db: AsyncSession,
    event_id: str,
    status: Optional[str] = None,
) -> list[RSVP]:
    """Get all RSVPs for an event, optionally filtered by status.

    Returns a list of RSVP objects.
    """
    stmt = select(RSVP).where(RSVP.event_id == event_id)

    if status is not None:
        valid_statuses = {"going", "maybe", "not_going"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid RSVP status filter: {status}. Must be one of: {', '.join(valid_statuses)}")
        stmt = stmt.where(RSVP.status == status)

    stmt = stmt.order_by(RSVP.created_at.desc())

    result = await db.execute(stmt)
    rsvps = list(result.scalars().all())

    logger.debug(
        "Found %d RSVPs for event_id=%s (status_filter=%s)",
        len(rsvps),
        event_id,
        status,
    )
    return rsvps