import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from models.event import Event
from models.event_category import EventCategory
from models.rsvp import RSVP
from services.rsvp_service import (
    delete_rsvp,
    get_event_rsvps,
    get_rsvp_counts,
    get_user_rsvp,
    set_rsvp,
)
from utils.security import COOKIE_NAME


# ---------------------------------------------------------------------------
# Service-layer tests
# ---------------------------------------------------------------------------


class TestSetRSVP:
    """Tests for the set_rsvp service function."""

    async def test_create_rsvp_going(
        self,
        db_session: AsyncSession,
        sample_event: Event,
        attendee_user: User,
    ):
        rsvp = await set_rsvp(
            db=db_session,
            event_id=sample_event.id,
            user_id=attendee_user.id,
            status="going",
        )

        assert rsvp is not None
        assert rsvp.event_id == sample_event.id
        assert rsvp.user_id == attendee_user.id
        assert rsvp.status == "going"

    async def test_create_rsvp_maybe(
        self,
        db_session: AsyncSession,
        sample_event: Event,
        attendee_user: User,
    ):
        rsvp = await set_rsvp(
            db=db_session,
            event_id=sample_event.id,
            user_id=attendee_user.id,
            status="maybe",
        )

        assert rsvp is not None
        assert rsvp.status == "maybe"

    async def test_create_rsvp_not_going(
        self,
        db_session: AsyncSession,
        sample_event: Event,
        attendee_user: User,
    ):
        rsvp = await set_rsvp(
            db=db_session,
            event_id=sample_event.id,
            user_id=attendee_user.id,
            status="not_going",
        )

        assert rsvp is not None
        assert rsvp.status == "not_going"

    async def test_update_existing_rsvp(
        self,
        db_session: AsyncSession,
        sample_event: Event,
        attendee_user: User,
    ):
        """Setting RSVP twice for the same user/event should update, not duplicate."""
        rsvp1 = await set_rsvp(
            db=db_session,
            event_id=sample_event.id,
            user_id=attendee_user.id,
            status="going",
        )
        rsvp1_id = rsvp1.id

        rsvp2 = await set_rsvp(
            db=db_session,
            event_id=sample_event.id,
            user_id=attendee_user.id,
            status="not_going",
        )

        # Should be the same row, updated in place
        assert rsvp2.id == rsvp1_id
        assert rsvp2.status == "not_going"

    async def test_set_rsvp_invalid_status_raises(
        self,
        db_session: AsyncSession,
        sample_event: Event,
        attendee_user: User,
    ):
        with pytest.raises(ValueError, match="Invalid RSVP status"):
            await set_rsvp(
                db=db_session,
                event_id=sample_event.id,
                user_id=attendee_user.id,
                status="invalid_status",
            )

    async def test_multiple_users_can_rsvp_same_event(
        self,
        db_session: AsyncSession,
        sample_event: Event,
        attendee_user: User,
        organizer_user: User,
    ):
        rsvp_a = await set_rsvp(
            db=db_session,
            event_id=sample_event.id,
            user_id=attendee_user.id,
            status="going",
        )
        rsvp_b = await set_rsvp(
            db=db_session,
            event_id=sample_event.id,
            user_id=organizer_user.id,
            status="maybe",
        )

        assert rsvp_a.id != rsvp_b.id
        assert rsvp_a.status == "going"
        assert rsvp_b.status == "maybe"


class TestGetRSVPCounts:
    """Tests for the get_rsvp_counts service function."""

    async def test_counts_empty_event(
        self,
        db_session: AsyncSession,
        sample_event: Event,
    ):
        counts = await get_rsvp_counts(db=db_session, event_id=sample_event.id)

        assert counts["going_count"] == 0
        assert counts["maybe_count"] == 0
        assert counts["not_going_count"] == 0
        assert counts["total_count"] == 0

    async def test_counts_with_rsvps(
        self,
        db_session: AsyncSession,
        sample_event: Event,
        attendee_user: User,
        organizer_user: User,
        admin_user: User,
    ):
        await set_rsvp(db=db_session, event_id=sample_event.id, user_id=attendee_user.id, status="going")
        await set_rsvp(db=db_session, event_id=sample_event.id, user_id=organizer_user.id, status="going")
        await set_rsvp(db=db_session, event_id=sample_event.id, user_id=admin_user.id, status="maybe")

        counts = await get_rsvp_counts(db=db_session, event_id=sample_event.id)

        assert counts["going_count"] == 2
        assert counts["maybe_count"] == 1
        assert counts["not_going_count"] == 0
        assert counts["total_count"] == 3

    async def test_counts_update_after_status_change(
        self,
        db_session: AsyncSession,
        sample_event: Event,
        attendee_user: User,
    ):
        await set_rsvp(db=db_session, event_id=sample_event.id, user_id=attendee_user.id, status="going")
        counts_before = await get_rsvp_counts(db=db_session, event_id=sample_event.id)
        assert counts_before["going_count"] == 1

        await set_rsvp(db=db_session, event_id=sample_event.id, user_id=attendee_user.id, status="not_going")
        counts_after = await get_rsvp_counts(db=db_session, event_id=sample_event.id)

        assert counts_after["going_count"] == 0
        assert counts_after["not_going_count"] == 1
        assert counts_after["total_count"] == 1


class TestGetUserRSVP:
    """Tests for the get_user_rsvp service function."""

    async def test_returns_none_when_no_rsvp(
        self,
        db_session: AsyncSession,
        sample_event: Event,
        attendee_user: User,
    ):
        result = await get_user_rsvp(
            db=db_session,
            event_id=sample_event.id,
            user_id=attendee_user.id,
        )
        assert result is None

    async def test_returns_rsvp_when_exists(
        self,
        db_session: AsyncSession,
        sample_event: Event,
        attendee_user: User,
    ):
        await set_rsvp(
            db=db_session,
            event_id=sample_event.id,
            user_id=attendee_user.id,
            status="going",
        )

        result = await get_user_rsvp(
            db=db_session,
            event_id=sample_event.id,
            user_id=attendee_user.id,
        )

        assert result is not None
        assert result.status == "going"
        assert result.user_id == attendee_user.id
        assert result.event_id == sample_event.id


class TestDeleteRSVP:
    """Tests for the delete_rsvp service function."""

    async def test_delete_existing_rsvp(
        self,
        db_session: AsyncSession,
        sample_event: Event,
        attendee_user: User,
    ):
        await set_rsvp(
            db=db_session,
            event_id=sample_event.id,
            user_id=attendee_user.id,
            status="going",
        )

        deleted = await delete_rsvp(
            db=db_session,
            event_id=sample_event.id,
            user_id=attendee_user.id,
        )
        assert deleted is True

        # Verify it's gone
        result = await get_user_rsvp(
            db=db_session,
            event_id=sample_event.id,
            user_id=attendee_user.id,
        )
        assert result is None

    async def test_delete_nonexistent_rsvp_returns_false(
        self,
        db_session: AsyncSession,
        sample_event: Event,
        attendee_user: User,
    ):
        deleted = await delete_rsvp(
            db=db_session,
            event_id=sample_event.id,
            user_id=attendee_user.id,
        )
        assert deleted is False


class TestGetEventRSVPs:
    """Tests for the get_event_rsvps service function."""

    async def test_returns_all_rsvps_for_event(
        self,
        db_session: AsyncSession,
        sample_event: Event,
        attendee_user: User,
        organizer_user: User,
    ):
        await set_rsvp(db=db_session, event_id=sample_event.id, user_id=attendee_user.id, status="going")
        await set_rsvp(db=db_session, event_id=sample_event.id, user_id=organizer_user.id, status="maybe")

        rsvps = await get_event_rsvps(db=db_session, event_id=sample_event.id)

        assert len(rsvps) == 2

    async def test_filter_by_status(
        self,
        db_session: AsyncSession,
        sample_event: Event,
        attendee_user: User,
        organizer_user: User,
    ):
        await set_rsvp(db=db_session, event_id=sample_event.id, user_id=attendee_user.id, status="going")
        await set_rsvp(db=db_session, event_id=sample_event.id, user_id=organizer_user.id, status="maybe")

        going_rsvps = await get_event_rsvps(
            db=db_session,
            event_id=sample_event.id,
            status="going",
        )

        assert len(going_rsvps) == 1
        assert going_rsvps[0].status == "going"

    async def test_filter_invalid_status_raises(
        self,
        db_session: AsyncSession,
        sample_event: Event,
    ):
        with pytest.raises(ValueError, match="Invalid RSVP status filter"):
            await get_event_rsvps(
                db=db_session,
                event_id=sample_event.id,
                status="invalid",
            )

    async def test_returns_empty_list_for_no_rsvps(
        self,
        db_session: AsyncSession,
        sample_event: Event,
    ):
        rsvps = await get_event_rsvps(db=db_session, event_id=sample_event.id)
        assert rsvps == []


# ---------------------------------------------------------------------------
# Route / integration tests
# ---------------------------------------------------------------------------


class TestRSVPRouteAuthenticated:
    """Tests for the POST /events/{event_id}/rsvp route with authentication."""

    async def test_rsvp_going_via_route(
        self,
        attendee_client: AsyncClient,
        sample_event: Event,
    ):
        response = await attendee_client.post(
            f"/events/{sample_event.id}/rsvp",
            data={"status": "going"},
            follow_redirects=False,
        )

        # Should redirect back to event detail
        assert response.status_code == 303
        assert f"/events/{sample_event.id}" in response.headers.get("location", "")

    async def test_rsvp_maybe_via_route(
        self,
        attendee_client: AsyncClient,
        sample_event: Event,
    ):
        response = await attendee_client.post(
            f"/events/{sample_event.id}/rsvp",
            data={"status": "maybe"},
            follow_redirects=False,
        )

        assert response.status_code == 303

    async def test_rsvp_not_going_via_route(
        self,
        attendee_client: AsyncClient,
        sample_event: Event,
    ):
        response = await attendee_client.post(
            f"/events/{sample_event.id}/rsvp",
            data={"status": "not_going"},
            follow_redirects=False,
        )

        assert response.status_code == 303

    async def test_rsvp_update_via_route(
        self,
        attendee_client: AsyncClient,
        sample_event: Event,
    ):
        # First RSVP
        await attendee_client.post(
            f"/events/{sample_event.id}/rsvp",
            data={"status": "going"},
            follow_redirects=False,
        )

        # Update RSVP
        response = await attendee_client.post(
            f"/events/{sample_event.id}/rsvp",
            data={"status": "not_going"},
            follow_redirects=False,
        )

        assert response.status_code == 303


class TestRSVPRouteUnauthenticated:
    """Tests for the POST /events/{event_id}/rsvp route without authentication."""

    async def test_unauthenticated_rsvp_returns_401(
        self,
        client: AsyncClient,
        sample_event: Event,
    ):
        response = await client.post(
            f"/events/{sample_event.id}/rsvp",
            data={"status": "going"},
            follow_redirects=False,
        )

        # Unauthenticated users should get 401
        assert response.status_code == 401


class TestRSVPDisplayOnEventDetail:
    """Tests that RSVP counts and current user RSVP appear on event detail page."""

    async def test_event_detail_shows_rsvp_section_for_authenticated_user(
        self,
        attendee_client: AsyncClient,
        sample_event: Event,
    ):
        response = await attendee_client.get(
            f"/events/{sample_event.id}",
            follow_redirects=False,
        )

        assert response.status_code == 200
        content = response.text
        # The RSVP section should be visible for authenticated users on published events
        assert "RSVP" in content
        assert "Going" in content
        assert "Maybe" in content
        assert "Not Going" in content

    async def test_event_detail_shows_current_rsvp_status(
        self,
        attendee_client: AsyncClient,
        sample_event: Event,
    ):
        # Set RSVP first
        await attendee_client.post(
            f"/events/{sample_event.id}/rsvp",
            data={"status": "going"},
            follow_redirects=False,
        )

        # Now view the event detail
        response = await attendee_client.get(
            f"/events/{sample_event.id}",
            follow_redirects=False,
        )

        assert response.status_code == 200
        content = response.text
        # Should show the current RSVP status
        assert "Going" in content

    async def test_event_detail_unauthenticated_no_rsvp_form(
        self,
        client: AsyncClient,
        sample_event: Event,
    ):
        response = await client.get(
            f"/events/{sample_event.id}",
            follow_redirects=False,
        )

        assert response.status_code == 200
        content = response.text
        # Unauthenticated users should not see the RSVP form action
        assert f'action="/events/{sample_event.id}/rsvp"' not in content


class TestRSVPUniqueConstraint:
    """Tests that the unique constraint on (event_id, user_id) is enforced."""

    async def test_unique_rsvp_per_user_per_event(
        self,
        db_session: AsyncSession,
        sample_event: Event,
        attendee_user: User,
    ):
        """Creating two RSVPs for the same user/event via set_rsvp should result in one row."""
        await set_rsvp(
            db=db_session,
            event_id=sample_event.id,
            user_id=attendee_user.id,
            status="going",
        )
        await set_rsvp(
            db=db_session,
            event_id=sample_event.id,
            user_id=attendee_user.id,
            status="maybe",
        )

        rsvps = await get_event_rsvps(db=db_session, event_id=sample_event.id)
        user_rsvps = [r for r in rsvps if r.user_id == attendee_user.id]

        assert len(user_rsvps) == 1
        assert user_rsvps[0].status == "maybe"

    async def test_different_events_same_user_separate_rsvps(
        self,
        db_session: AsyncSession,
        sample_event: Event,
        draft_event: Event,
        attendee_user: User,
    ):
        """A user can RSVP to different events independently."""
        rsvp1 = await set_rsvp(
            db=db_session,
            event_id=sample_event.id,
            user_id=attendee_user.id,
            status="going",
        )
        rsvp2 = await set_rsvp(
            db=db_session,
            event_id=draft_event.id,
            user_id=attendee_user.id,
            status="not_going",
        )

        assert rsvp1.id != rsvp2.id
        assert rsvp1.event_id == sample_event.id
        assert rsvp2.event_id == draft_event.id
        assert rsvp1.status == "going"
        assert rsvp2.status == "not_going"