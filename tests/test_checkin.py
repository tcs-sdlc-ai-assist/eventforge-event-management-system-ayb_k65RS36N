import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from models.event import Event
from models.event_category import EventCategory
from models.ticket import Ticket, TicketType
from utils.security import hash_password, create_access_token, COOKIE_NAME


@pytest_asyncio.fixture
async def checkin_setup(db_session: AsyncSession):
    """Create organizer, attendee, another user, event, ticket type, and confirmed ticket for check-in tests."""
    organizer = User(
        username="checkin_organizer",
        email="checkin_organizer@eventforge.com",
        display_name="Check-In Organizer",
        hashed_password=hash_password("organizerpass123"),
        role="Project Manager",
        is_active=True,
    )
    db_session.add(organizer)

    attendee = User(
        username="checkin_attendee",
        email="checkin_attendee@eventforge.com",
        display_name="Check-In Attendee",
        hashed_password=hash_password("attendeepass123"),
        role="Viewer",
        is_active=True,
    )
    db_session.add(attendee)

    other_user = User(
        username="checkin_other",
        email="checkin_other@eventforge.com",
        display_name="Other User",
        hashed_password=hash_password("otherpass123"),
        role="Project Manager",
        is_active=True,
    )
    db_session.add(other_user)

    await db_session.flush()

    category = EventCategory(
        name="Check-In Test Category",
        color="#22c55e",
        icon="✅",
    )
    db_session.add(category)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    event = Event(
        title="Check-In Test Event",
        description="An event for testing check-in functionality.",
        category_id=category.id,
        organizer_id=organizer.id,
        venue_name="Check-In Venue",
        address_line="789 Check-In Blvd",
        city="Check-In City",
        state="Check-In State",
        country="Check-In Country",
        start_datetime=now + timedelta(days=5),
        end_datetime=now + timedelta(days=5, hours=6),
        total_capacity=200,
        status="published",
    )
    db_session.add(event)
    await db_session.flush()

    ticket_type = TicketType(
        event_id=event.id,
        name="General Admission",
        price=25.00,
        quantity=100,
        sold=1,
        description="Standard entry",
    )
    db_session.add(ticket_type)
    await db_session.flush()

    ticket = Ticket(
        event_id=event.id,
        ticket_type_id=ticket_type.id,
        attendee_id=attendee.id,
        quantity=1,
        total_price=25.00,
        status="confirmed",
        checked_in=False,
    )
    db_session.add(ticket)
    await db_session.flush()

    await db_session.refresh(organizer)
    await db_session.refresh(attendee)
    await db_session.refresh(other_user)
    await db_session.refresh(event)
    await db_session.refresh(ticket_type)
    await db_session.refresh(ticket)

    return {
        "organizer": organizer,
        "attendee": attendee,
        "other_user": other_user,
        "event": event,
        "ticket_type": ticket_type,
        "ticket": ticket,
    }


class TestToggleCheckIn:
    """Tests for toggling attendee check-in status."""

    @pytest.mark.asyncio
    async def test_organizer_can_check_in_attendee(self, client: AsyncClient, checkin_setup: dict):
        """Organizer should be able to check in an attendee for their event."""
        organizer = checkin_setup["organizer"]
        event = checkin_setup["event"]
        attendee = checkin_setup["attendee"]

        token = create_access_token(data={"sub": organizer.id})
        client.cookies.set(COOKIE_NAME, token)

        response = await client.post(
            f"/events/{event.id}/checkin/{attendee.id}",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert f"/events/{event.id}" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_check_in_sets_flash_message_success(self, client: AsyncClient, checkin_setup: dict):
        """Check-in should set a success flash message cookie."""
        organizer = checkin_setup["organizer"]
        event = checkin_setup["event"]
        attendee = checkin_setup["attendee"]

        token = create_access_token(data={"sub": organizer.id})
        client.cookies.set(COOKIE_NAME, token)

        response = await client.post(
            f"/events/{event.id}/checkin/{attendee.id}",
            follow_redirects=False,
        )

        assert response.status_code == 303
        cookies = {c.name: c.value for c in response.cookies.jar}
        assert "flash_type" in cookies
        assert cookies["flash_type"] == "success"

    @pytest.mark.asyncio
    async def test_toggle_check_in_twice_undoes_checkin(self, client: AsyncClient, checkin_setup: dict):
        """Toggling check-in twice should undo the check-in."""
        organizer = checkin_setup["organizer"]
        event = checkin_setup["event"]
        attendee = checkin_setup["attendee"]

        token = create_access_token(data={"sub": organizer.id})
        client.cookies.set(COOKIE_NAME, token)

        # First toggle: check in
        response1 = await client.post(
            f"/events/{event.id}/checkin/{attendee.id}",
            follow_redirects=False,
        )
        assert response1.status_code == 303
        cookies1 = {c.name: c.value for c in response1.cookies.jar}
        assert cookies1.get("flash_type") == "success"

        # Second toggle: undo check-in
        response2 = await client.post(
            f"/events/{event.id}/checkin/{attendee.id}",
            follow_redirects=False,
        )
        assert response2.status_code == 303
        cookies2 = {c.name: c.value for c in response2.cookies.jar}
        assert cookies2.get("flash_type") == "success"


class TestCheckInUnauthorized:
    """Tests for unauthorized check-in attempts."""

    @pytest.mark.asyncio
    async def test_non_owner_non_admin_cannot_check_in(self, client: AsyncClient, checkin_setup: dict):
        """A user who is not the organizer or admin should be redirected without performing check-in."""
        other_user = checkin_setup["other_user"]
        event = checkin_setup["event"]
        attendee = checkin_setup["attendee"]

        token = create_access_token(data={"sub": other_user.id})
        client.cookies.set(COOKIE_NAME, token)

        response = await client.post(
            f"/events/{event.id}/checkin/{attendee.id}",
            follow_redirects=False,
        )

        # Non-owner/non-admin gets redirected to event detail without check-in
        assert response.status_code == 303
        assert f"/events/{event.id}" in response.headers.get("location", "")
        # No flash message should be set for unauthorized redirect
        cookies = {c.name: c.value for c in response.cookies.jar}
        assert "flash_message" not in cookies

    @pytest.mark.asyncio
    async def test_unauthenticated_user_cannot_check_in(self, client: AsyncClient, checkin_setup: dict):
        """An unauthenticated user should receive a 401 error."""
        event = checkin_setup["event"]
        attendee = checkin_setup["attendee"]

        # Clear any existing cookies
        client.cookies.clear()

        response = await client.post(
            f"/events/{event.id}/checkin/{attendee.id}",
            follow_redirects=False,
        )

        # require_auth raises 401 for unauthenticated users
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_viewer_role_cannot_check_in_others_event(self, client: AsyncClient, checkin_setup: dict):
        """A viewer (attendee role) should not be able to check in attendees for events they don't organize."""
        attendee = checkin_setup["attendee"]
        event = checkin_setup["event"]

        token = create_access_token(data={"sub": attendee.id})
        client.cookies.set(COOKIE_NAME, token)

        response = await client.post(
            f"/events/{event.id}/checkin/{attendee.id}",
            follow_redirects=False,
        )

        # Viewer is not the organizer, so they get redirected
        assert response.status_code == 303
        assert f"/events/{event.id}" in response.headers.get("location", "")


class TestCheckInAdminAccess:
    """Tests for admin check-in access."""

    @pytest.mark.asyncio
    async def test_admin_can_check_in_any_event(self, client: AsyncClient, checkin_setup: dict, db_session: AsyncSession):
        """An admin user should be able to check in attendees for any event."""
        admin = User(
            username="checkin_admin",
            email="checkin_admin@eventforge.com",
            display_name="Check-In Admin",
            hashed_password=hash_password("adminpass123"),
            role="Super Admin",
            is_active=True,
        )
        db_session.add(admin)
        await db_session.flush()
        await db_session.refresh(admin)

        event = checkin_setup["event"]
        attendee = checkin_setup["attendee"]

        token = create_access_token(data={"sub": admin.id})
        client.cookies.set(COOKIE_NAME, token)

        response = await client.post(
            f"/events/{event.id}/checkin/{attendee.id}",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert f"/events/{event.id}" in response.headers.get("location", "")
        cookies = {c.name: c.value for c in response.cookies.jar}
        assert cookies.get("flash_type") == "success"


class TestCheckInNonExistentAttendee:
    """Tests for check-in with non-existent attendee or event."""

    @pytest.mark.asyncio
    async def test_checkin_nonexistent_attendee_returns_error(self, client: AsyncClient, checkin_setup: dict):
        """Attempting to check in a non-existent attendee should set an error flash message."""
        organizer = checkin_setup["organizer"]
        event = checkin_setup["event"]

        token = create_access_token(data={"sub": organizer.id})
        client.cookies.set(COOKIE_NAME, token)

        fake_attendee_id = "00000000-0000-0000-0000-000000000000"

        response = await client.post(
            f"/events/{event.id}/checkin/{fake_attendee_id}",
            follow_redirects=False,
        )

        assert response.status_code == 303
        cookies = {c.name: c.value for c in response.cookies.jar}
        assert cookies.get("flash_type") == "error"

    @pytest.mark.asyncio
    async def test_checkin_nonexistent_event_returns_404(self, client: AsyncClient, checkin_setup: dict):
        """Attempting to check in for a non-existent event should return 404."""
        organizer = checkin_setup["organizer"]
        attendee = checkin_setup["attendee"]

        token = create_access_token(data={"sub": organizer.id})
        client.cookies.set(COOKIE_NAME, token)

        fake_event_id = "00000000-0000-0000-0000-999999999999"

        response = await client.post(
            f"/events/{fake_event_id}/checkin/{attendee.id}",
            follow_redirects=False,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_checkin_attendee_without_ticket_returns_error(self, client: AsyncClient, checkin_setup: dict, db_session: AsyncSession):
        """Attempting to check in an attendee who has no confirmed ticket should set an error flash."""
        organizer = checkin_setup["organizer"]
        event = checkin_setup["event"]

        # Create a user with no ticket for this event
        no_ticket_user = User(
            username="no_ticket_user",
            email="noticket@eventforge.com",
            display_name="No Ticket User",
            hashed_password=hash_password("noticketpass123"),
            role="Viewer",
            is_active=True,
        )
        db_session.add(no_ticket_user)
        await db_session.flush()
        await db_session.refresh(no_ticket_user)

        token = create_access_token(data={"sub": organizer.id})
        client.cookies.set(COOKIE_NAME, token)

        response = await client.post(
            f"/events/{event.id}/checkin/{no_ticket_user.id}",
            follow_redirects=False,
        )

        assert response.status_code == 303
        cookies = {c.name: c.value for c in response.cookies.jar}
        assert cookies.get("flash_type") == "error"


class TestCheckInServiceDirectly:
    """Tests for the toggle_checkin service function directly."""

    @pytest.mark.asyncio
    async def test_toggle_checkin_checks_in_attendee(self, db_session: AsyncSession, checkin_setup: dict):
        """toggle_checkin should set checked_in to True on first call."""
        from services.ticket_service import toggle_checkin

        event = checkin_setup["event"]
        attendee = checkin_setup["attendee"]

        result = await toggle_checkin(
            db=db_session,
            event_id=event.id,
            attendee_id=attendee.id,
        )

        assert result["checked_in"] is True
        assert result["event_id"] == event.id
        assert result["attendee_id"] == attendee.id
        assert result["checked_in_at"] is not None

    @pytest.mark.asyncio
    async def test_toggle_checkin_undoes_checkin(self, db_session: AsyncSession, checkin_setup: dict):
        """toggle_checkin called twice should undo the check-in."""
        from services.ticket_service import toggle_checkin

        event = checkin_setup["event"]
        attendee = checkin_setup["attendee"]

        # First toggle: check in
        result1 = await toggle_checkin(
            db=db_session,
            event_id=event.id,
            attendee_id=attendee.id,
        )
        assert result1["checked_in"] is True

        # Second toggle: undo
        result2 = await toggle_checkin(
            db=db_session,
            event_id=event.id,
            attendee_id=attendee.id,
        )
        assert result2["checked_in"] is False
        assert result2["checked_in_at"] is None

    @pytest.mark.asyncio
    async def test_toggle_checkin_no_ticket_raises_value_error(self, db_session: AsyncSession, checkin_setup: dict):
        """toggle_checkin should raise ValueError when attendee has no confirmed ticket."""
        from services.ticket_service import toggle_checkin

        event = checkin_setup["event"]
        fake_attendee_id = "00000000-0000-0000-0000-000000000000"

        with pytest.raises(ValueError, match="No confirmed ticket found"):
            await toggle_checkin(
                db=db_session,
                event_id=event.id,
                attendee_id=fake_attendee_id,
            )

    @pytest.mark.asyncio
    async def test_toggle_checkin_cancelled_ticket_raises_value_error(self, db_session: AsyncSession, checkin_setup: dict):
        """toggle_checkin should raise ValueError when attendee's ticket is cancelled."""
        from services.ticket_service import toggle_checkin

        event = checkin_setup["event"]
        ticket = checkin_setup["ticket"]

        # Cancel the ticket
        ticket.status = "cancelled"
        await db_session.flush()

        with pytest.raises(ValueError, match="No confirmed ticket found"):
            await toggle_checkin(
                db=db_session,
                event_id=event.id,
                attendee_id=checkin_setup["attendee"].id,
            )