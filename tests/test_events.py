import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from models.event import Event
from models.event_category import EventCategory
from models.ticket import Ticket, TicketType
from models.rsvp import RSVP
from utils.security import hash_password, create_access_token, COOKIE_NAME


# ---------------------------------------------------------------------------
# Service-layer tests (EventService)
# ---------------------------------------------------------------------------


class TestEventServiceCreateEvent:
    """Tests for services.event_service.create_event"""

    async def test_create_event_success(self, db_session: AsyncSession, organizer_user: User, sample_category: EventCategory):
        from services.event_service import create_event

        now = datetime.now(timezone.utc)
        event = await create_event(
            db=db_session,
            organizer_id=organizer_user.id,
            title="Service Test Event",
            description="Created via service layer",
            category_id=sample_category.id,
            venue_name="Service Venue",
            address_line="100 Service St",
            city="Service City",
            state="SC",
            country="Service Country",
            start_datetime=now + timedelta(days=10),
            end_datetime=now + timedelta(days=10, hours=6),
            total_capacity=200,
            ticket_types_data=[
                {"name": "Early Bird", "price": 25.0, "quantity": 100},
                {"name": "Regular", "price": 50.0, "quantity": 100},
            ],
        )

        assert event is not None
        assert event.title == "Service Test Event"
        assert event.organizer_id == organizer_user.id
        assert event.status == "draft"
        assert event.total_capacity == 200

    async def test_create_event_start_after_end_raises(self, db_session: AsyncSession, organizer_user: User):
        from services.event_service import create_event

        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="start_datetime must be before end_datetime"):
            await create_event(
                db=db_session,
                organizer_id=organizer_user.id,
                title="Bad Dates Event",
                description=None,
                category_id=None,
                venue_name="V",
                address_line="A",
                city="C",
                state=None,
                country="CO",
                start_datetime=now + timedelta(days=10),
                end_datetime=now + timedelta(days=5),
                total_capacity=100,
            )

    async def test_create_event_capacity_less_than_one_raises(self, db_session: AsyncSession, organizer_user: User):
        from services.event_service import create_event

        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="total_capacity must be at least 1"):
            await create_event(
                db=db_session,
                organizer_id=organizer_user.id,
                title="Zero Cap",
                description=None,
                category_id=None,
                venue_name="V",
                address_line="A",
                city="C",
                state=None,
                country="CO",
                start_datetime=now + timedelta(days=10),
                end_datetime=now + timedelta(days=10, hours=2),
                total_capacity=0,
            )

    async def test_create_event_ticket_quantity_exceeds_capacity(self, db_session: AsyncSession, organizer_user: User):
        from services.event_service import create_event

        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="Sum of ticket quantities exceeds event capacity"):
            await create_event(
                db=db_session,
                organizer_id=organizer_user.id,
                title="Over Cap",
                description=None,
                category_id=None,
                venue_name="V",
                address_line="A",
                city="C",
                state=None,
                country="CO",
                start_datetime=now + timedelta(days=10),
                end_datetime=now + timedelta(days=10, hours=2),
                total_capacity=50,
                ticket_types_data=[
                    {"name": "A", "price": 0, "quantity": 30},
                    {"name": "B", "price": 0, "quantity": 30},
                ],
            )

    async def test_create_event_invalid_category_raises(self, db_session: AsyncSession, organizer_user: User):
        from services.event_service import create_event

        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="Category with id .* not found"):
            await create_event(
                db=db_session,
                organizer_id=organizer_user.id,
                title="Bad Cat",
                description=None,
                category_id="00000000-0000-0000-0000-000000000000",
                venue_name="V",
                address_line="A",
                city="C",
                state=None,
                country="CO",
                start_datetime=now + timedelta(days=10),
                end_datetime=now + timedelta(days=10, hours=2),
                total_capacity=100,
            )


class TestEventServiceEditEvent:
    """Tests for services.event_service.edit_event"""

    async def test_edit_event_by_owner(self, db_session: AsyncSession, organizer_user: User, sample_event: Event):
        from services.event_service import edit_event

        updated = await edit_event(
            db=db_session,
            event_id=sample_event.id,
            user_id=organizer_user.id,
            user_role=organizer_user.role,
            update_data={"title": "Updated Title"},
        )
        assert updated.title == "Updated Title"

    async def test_edit_event_by_admin(self, db_session: AsyncSession, admin_user: User, sample_event: Event):
        from services.event_service import edit_event

        updated = await edit_event(
            db=db_session,
            event_id=sample_event.id,
            user_id=admin_user.id,
            user_role=admin_user.role,
            update_data={"title": "Admin Updated"},
        )
        assert updated.title == "Admin Updated"

    async def test_edit_event_by_non_owner_raises(self, db_session: AsyncSession, attendee_user: User, sample_event: Event):
        from services.event_service import edit_event

        with pytest.raises(PermissionError, match="You do not have permission"):
            await edit_event(
                db=db_session,
                event_id=sample_event.id,
                user_id=attendee_user.id,
                user_role=attendee_user.role,
                update_data={"title": "Hacked"},
            )

    async def test_edit_nonexistent_event_raises(self, db_session: AsyncSession, organizer_user: User):
        from services.event_service import edit_event

        with pytest.raises(LookupError, match="Event with id .* not found"):
            await edit_event(
                db=db_session,
                event_id="nonexistent-id",
                user_id=organizer_user.id,
                user_role=organizer_user.role,
                update_data={"title": "Ghost"},
            )

    async def test_edit_event_invalid_dates_raises(self, db_session: AsyncSession, organizer_user: User, sample_event: Event):
        from services.event_service import edit_event

        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="start_datetime must be before end_datetime"):
            await edit_event(
                db=db_session,
                event_id=sample_event.id,
                user_id=organizer_user.id,
                user_role=organizer_user.role,
                update_data={
                    "start_datetime": now + timedelta(days=50),
                    "end_datetime": now + timedelta(days=40),
                },
            )


class TestEventServiceDeleteEvent:
    """Tests for services.event_service.delete_event"""

    async def test_delete_event_by_owner(self, db_session: AsyncSession, organizer_user: User, sample_event: Event):
        from services.event_service import delete_event, get_event

        event_id = sample_event.id
        await delete_event(
            db=db_session,
            event_id=event_id,
            user_id=organizer_user.id,
            user_role=organizer_user.role,
        )
        result = await get_event(db_session, event_id)
        assert result is None

    async def test_delete_event_by_non_owner_raises(self, db_session: AsyncSession, attendee_user: User, sample_event: Event):
        from services.event_service import delete_event

        with pytest.raises(PermissionError, match="You do not have permission"):
            await delete_event(
                db=db_session,
                event_id=sample_event.id,
                user_id=attendee_user.id,
                user_role=attendee_user.role,
            )

    async def test_delete_nonexistent_event_raises(self, db_session: AsyncSession, organizer_user: User):
        from services.event_service import delete_event

        with pytest.raises(LookupError, match="Event with id .* not found"):
            await delete_event(
                db=db_session,
                event_id="nonexistent-id",
                user_id=organizer_user.id,
                user_role=organizer_user.role,
            )


class TestEventServiceSearchEvents:
    """Tests for services.event_service.search_events"""

    async def test_search_returns_all_events(self, db_session: AsyncSession, sample_event: Event):
        from services.event_service import search_events

        result = await search_events(db=db_session)
        assert result["total"] >= 1
        assert len(result["items"]) >= 1

    async def test_search_by_keyword(self, db_session: AsyncSession, sample_event: Event):
        from services.event_service import search_events

        result = await search_events(db=db_session, keyword="Test Conference")
        assert result["total"] >= 1
        titles = [e.title for e in result["items"]]
        assert any("Test Conference" in t for t in titles)

    async def test_search_by_keyword_no_match(self, db_session: AsyncSession, sample_event: Event):
        from services.event_service import search_events

        result = await search_events(db=db_session, keyword="zzzznonexistentzzzz")
        assert result["total"] == 0
        assert len(result["items"]) == 0

    async def test_search_by_category(self, db_session: AsyncSession, sample_event: Event, sample_category: EventCategory):
        from services.event_service import search_events

        result = await search_events(db=db_session, category_id=sample_category.id)
        assert result["total"] >= 1
        for event in result["items"]:
            assert event.category_id == sample_category.id

    async def test_search_by_status(self, db_session: AsyncSession, sample_event: Event, draft_event: Event):
        from services.event_service import search_events

        published_result = await search_events(db=db_session, status="published")
        for event in published_result["items"]:
            assert event.status == "published"

        draft_result = await search_events(db=db_session, status="draft")
        for event in draft_result["items"]:
            assert event.status == "draft"

    async def test_search_by_date_range(self, db_session: AsyncSession, sample_event: Event):
        from services.event_service import search_events

        now = datetime.now(timezone.utc)
        result = await search_events(
            db=db_session,
            date_from=now,
            date_to=now + timedelta(days=365),
        )
        assert result["total"] >= 1

    async def test_search_pagination(self, db_session: AsyncSession, organizer_user: User, sample_category: EventCategory):
        from services.event_service import create_event, search_events

        now = datetime.now(timezone.utc)
        for i in range(5):
            await create_event(
                db=db_session,
                organizer_id=organizer_user.id,
                title=f"Paginated Event {i}",
                description=None,
                category_id=sample_category.id,
                venue_name="PV",
                address_line="PA",
                city="PC",
                state=None,
                country="PCO",
                start_datetime=now + timedelta(days=10 + i),
                end_datetime=now + timedelta(days=10 + i, hours=2),
                total_capacity=50,
            )

        page1 = await search_events(db=db_session, page=1, page_size=2)
        assert len(page1["items"]) == 2
        assert page1["page"] == 1
        assert page1["total_pages"] >= 3

        page2 = await search_events(db=db_session, page=2, page_size=2)
        assert len(page2["items"]) == 2
        page1_ids = {e.id for e in page1["items"]}
        page2_ids = {e.id for e in page2["items"]}
        assert page1_ids.isdisjoint(page2_ids)


class TestEventServiceGetEvent:
    """Tests for services.event_service.get_event"""

    async def test_get_existing_event(self, db_session: AsyncSession, sample_event: Event):
        from services.event_service import get_event

        event = await get_event(db_session, sample_event.id)
        assert event is not None
        assert event.id == sample_event.id
        assert event.title == sample_event.title

    async def test_get_nonexistent_event_returns_none(self, db_session: AsyncSession):
        from services.event_service import get_event

        event = await get_event(db_session, "nonexistent-id-12345")
        assert event is None


class TestEventServiceGetEventStats:
    """Tests for services.event_service.get_event_stats"""

    async def test_get_event_stats_empty(self, db_session: AsyncSession, sample_event: Event):
        from services.event_service import get_event_stats

        stats = await get_event_stats(db_session, sample_event.id)
        assert stats["total_tickets_sold"] == 0
        assert stats["total_revenue"] == 0
        assert stats["total_checked_in"] == 0
        assert stats["total_capacity"] == sample_event.total_capacity
        assert stats["rsvp_counts"]["total_count"] == 0

    async def test_get_event_stats_nonexistent_raises(self, db_session: AsyncSession):
        from services.event_service import get_event_stats

        with pytest.raises(LookupError, match="Event with id .* not found"):
            await get_event_stats(db_session, "nonexistent-id")


class TestEventServiceGetAllCategories:
    """Tests for services.event_service.get_all_categories"""

    async def test_get_all_categories(self, db_session: AsyncSession, sample_category: EventCategory):
        from services.event_service import get_all_categories

        categories = await get_all_categories(db_session)
        assert len(categories) >= 1
        names = [c.name for c in categories]
        assert sample_category.name in names


class TestEventServiceGetEventsByOrganizer:
    """Tests for services.event_service.get_events_by_organizer"""

    async def test_get_events_by_organizer(self, db_session: AsyncSession, organizer_user: User, sample_event: Event):
        from services.event_service import get_events_by_organizer

        events = await get_events_by_organizer(db_session, organizer_user.id)
        assert len(events) >= 1
        for event in events:
            assert event.organizer_id == organizer_user.id

    async def test_get_events_by_organizer_no_events(self, db_session: AsyncSession, attendee_user: User):
        from services.event_service import get_events_by_organizer

        events = await get_events_by_organizer(db_session, attendee_user.id)
        assert len(events) == 0


class TestEventServiceGetEventAttendees:
    """Tests for services.event_service.get_event_attendees"""

    async def test_get_event_attendees_empty(self, db_session: AsyncSession, sample_event: Event):
        from services.event_service import get_event_attendees

        attendees = await get_event_attendees(db_session, sample_event.id)
        assert len(attendees) == 0

    async def test_get_event_attendees_with_ticket(
        self,
        db_session: AsyncSession,
        sample_event: Event,
        attendee_user: User,
    ):
        from services.event_service import get_event_attendees
        from services.ticket_service import claim_ticket

        ticket_types_result = await db_session.execute(
            select(TicketType).where(TicketType.event_id == sample_event.id)
        )
        tt = ticket_types_result.scalars().first()
        assert tt is not None

        await claim_ticket(
            db=db_session,
            event_id=sample_event.id,
            ticket_type_id=tt.id,
            attendee_id=attendee_user.id,
            quantity=1,
        )

        attendees = await get_event_attendees(db_session, sample_event.id)
        assert len(attendees) >= 1
        assert attendees[0]["attendee_id"] == attendee_user.id


# ---------------------------------------------------------------------------
# Router / HTTP tests
# ---------------------------------------------------------------------------


class TestBrowseEventsPage:
    """Tests for GET /events (browse page)"""

    async def test_browse_events_unauthenticated(self, client: AsyncClient, sample_event: Event):
        response = await client.get("/events", follow_redirects=False)
        assert response.status_code == 200
        assert "Browse Events" in response.text

    async def test_browse_events_authenticated(self, organizer_client: AsyncClient, sample_event: Event):
        response = await organizer_client.get("/events", follow_redirects=False)
        assert response.status_code == 200
        assert "Browse Events" in response.text

    async def test_browse_events_with_keyword_filter(self, client: AsyncClient, sample_event: Event):
        response = await client.get("/events?keyword=Test+Conference", follow_redirects=False)
        assert response.status_code == 200
        assert "Test Conference" in response.text

    async def test_browse_events_with_status_filter(self, client: AsyncClient, sample_event: Event):
        response = await client.get("/events?status=published", follow_redirects=False)
        assert response.status_code == 200

    async def test_browse_events_with_category_filter(self, client: AsyncClient, sample_event: Event, sample_category: EventCategory):
        response = await client.get(f"/events?category={sample_category.id}", follow_redirects=False)
        assert response.status_code == 200

    async def test_browse_events_no_results(self, client: AsyncClient):
        response = await client.get("/events?keyword=zzzznonexistentzzzz", follow_redirects=False)
        assert response.status_code == 200
        assert "No events found" in response.text

    async def test_browse_events_pagination_params(self, client: AsyncClient, sample_event: Event):
        response = await client.get("/events?page=1&page_size=5", follow_redirects=False)
        assert response.status_code == 200


class TestEventDetailPage:
    """Tests for GET /events/{event_id} (detail page)"""

    async def test_event_detail_unauthenticated(self, client: AsyncClient, sample_event: Event):
        response = await client.get(f"/events/{sample_event.id}", follow_redirects=False)
        assert response.status_code == 200
        assert sample_event.title in response.text
        assert "Event Details" in response.text

    async def test_event_detail_authenticated(self, attendee_client: AsyncClient, sample_event: Event):
        response = await attendee_client.get(f"/events/{sample_event.id}", follow_redirects=False)
        assert response.status_code == 200
        assert sample_event.title in response.text

    async def test_event_detail_shows_ticket_types(self, client: AsyncClient, sample_event: Event):
        response = await client.get(f"/events/{sample_event.id}", follow_redirects=False)
        assert response.status_code == 200
        assert "General Admission" in response.text
        assert "VIP" in response.text

    async def test_event_detail_shows_edit_button_for_owner(self, organizer_client: AsyncClient, sample_event: Event):
        response = await organizer_client.get(f"/events/{sample_event.id}", follow_redirects=False)
        assert response.status_code == 200
        assert "Edit" in response.text

    async def test_event_detail_shows_rsvp_for_authenticated(self, attendee_client: AsyncClient, sample_event: Event):
        response = await attendee_client.get(f"/events/{sample_event.id}", follow_redirects=False)
        assert response.status_code == 200
        assert "RSVP" in response.text

    async def test_event_detail_nonexistent_returns_404(self, client: AsyncClient):
        response = await client.get("/events/nonexistent-id-12345", follow_redirects=False)
        assert response.status_code == 404

    async def test_event_detail_shows_attendees_for_organizer(self, organizer_client: AsyncClient, sample_event: Event):
        response = await organizer_client.get(f"/events/{sample_event.id}", follow_redirects=False)
        assert response.status_code == 200
        assert "Attendees" in response.text

    async def test_event_detail_shows_attendees_for_admin(self, admin_client: AsyncClient, sample_event: Event):
        response = await admin_client.get(f"/events/{sample_event.id}", follow_redirects=False)
        assert response.status_code == 200
        assert "Attendees" in response.text


class TestCreateEventPage:
    """Tests for GET /events/create and POST /events/create"""

    async def test_create_event_form_requires_auth(self, client: AsyncClient):
        response = await client.get("/events/create", follow_redirects=False)
        assert response.status_code == 401

    async def test_create_event_form_renders(self, organizer_client: AsyncClient):
        response = await organizer_client.get("/events/create", follow_redirects=False)
        assert response.status_code == 200
        assert "Create Event" in response.text

    async def test_create_event_submit_success(self, organizer_client: AsyncClient, sample_category: EventCategory):
        now = datetime.now(timezone.utc)
        start = (now + timedelta(days=20)).strftime("%Y-%m-%dT%H:%M")
        end = (now + timedelta(days=20, hours=4)).strftime("%Y-%m-%dT%H:%M")

        response = await organizer_client.post(
            "/events/create",
            data={
                "title": "New Router Event",
                "description": "Created via router test",
                "category_id": sample_category.id,
                "venue_name": "Router Venue",
                "venue_address": "789 Router Rd",
                "venue_city": "Router City",
                "venue_country": "Router Country",
                "venue_state": "RS",
                "start_datetime": start,
                "end_datetime": end,
                "capacity": "300",
                "ticket_type_name_0": "Standard",
                "ticket_type_price_0": "25.00",
                "ticket_type_quantity_0": "200",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/events/" in response.headers.get("location", "")

    async def test_create_event_invalid_dates(self, organizer_client: AsyncClient):
        response = await organizer_client.post(
            "/events/create",
            data={
                "title": "Bad Date Event",
                "venue_name": "V",
                "venue_address": "A",
                "venue_city": "C",
                "venue_country": "CO",
                "start_datetime": "not-a-date",
                "end_datetime": "also-not-a-date",
                "capacity": "100",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "Invalid date format" in response.text


class TestEditEventPage:
    """Tests for GET /events/{id}/edit and POST /events/{id}/edit"""

    async def test_edit_event_form_requires_auth(self, client: AsyncClient, sample_event: Event):
        response = await client.get(f"/events/{sample_event.id}/edit", follow_redirects=False)
        assert response.status_code == 401

    async def test_edit_event_form_renders_for_owner(self, organizer_client: AsyncClient, sample_event: Event):
        response = await organizer_client.get(f"/events/{sample_event.id}/edit", follow_redirects=False)
        assert response.status_code == 200
        assert "Edit Event" in response.text
        assert sample_event.title in response.text

    async def test_edit_event_form_redirects_non_owner(self, attendee_client: AsyncClient, sample_event: Event):
        response = await attendee_client.get(f"/events/{sample_event.id}/edit", follow_redirects=False)
        assert response.status_code == 303

    async def test_edit_event_submit_success(self, organizer_client: AsyncClient, sample_event: Event):
        now = datetime.now(timezone.utc)
        start = (now + timedelta(days=40)).strftime("%Y-%m-%dT%H:%M")
        end = (now + timedelta(days=40, hours=6)).strftime("%Y-%m-%dT%H:%M")

        response = await organizer_client.post(
            f"/events/{sample_event.id}/edit",
            data={
                "title": "Edited Event Title",
                "description": "Edited description",
                "venue_name": "Edited Venue",
                "venue_address": "Edited Address",
                "venue_city": "Edited City",
                "venue_country": "Edited Country",
                "start_datetime": start,
                "end_datetime": end,
                "capacity": "600",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert f"/events/{sample_event.id}" in response.headers.get("location", "")

    async def test_edit_event_nonexistent_returns_404(self, organizer_client: AsyncClient):
        response = await organizer_client.get("/events/nonexistent-id/edit", follow_redirects=False)
        assert response.status_code == 404


class TestDeleteEvent:
    """Tests for POST /events/{id}/delete"""

    async def test_delete_event_requires_auth(self, client: AsyncClient, sample_event: Event):
        response = await client.post(f"/events/{sample_event.id}/delete", follow_redirects=False)
        assert response.status_code == 401

    async def test_delete_event_by_owner(self, organizer_client: AsyncClient, sample_event: Event):
        response = await organizer_client.post(
            f"/events/{sample_event.id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/events" in response.headers.get("location", "")

    async def test_delete_event_by_non_owner_redirects(self, attendee_client: AsyncClient, sample_event: Event):
        response = await attendee_client.post(
            f"/events/{sample_event.id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_delete_nonexistent_event_returns_404(self, organizer_client: AsyncClient):
        response = await organizer_client.post(
            "/events/nonexistent-id/delete",
            follow_redirects=False,
        )
        assert response.status_code == 404


class TestRSVPEndpoint:
    """Tests for POST /events/{id}/rsvp"""

    async def test_rsvp_requires_auth(self, client: AsyncClient, sample_event: Event):
        response = await client.post(
            f"/events/{sample_event.id}/rsvp",
            data={"status": "going"},
            follow_redirects=False,
        )
        assert response.status_code == 401

    async def test_rsvp_going(self, attendee_client: AsyncClient, sample_event: Event):
        response = await attendee_client.post(
            f"/events/{sample_event.id}/rsvp",
            data={"status": "going"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert f"/events/{sample_event.id}" in response.headers.get("location", "")

    async def test_rsvp_maybe(self, attendee_client: AsyncClient, sample_event: Event):
        response = await attendee_client.post(
            f"/events/{sample_event.id}/rsvp",
            data={"status": "maybe"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_rsvp_not_going(self, attendee_client: AsyncClient, sample_event: Event):
        response = await attendee_client.post(
            f"/events/{sample_event.id}/rsvp",
            data={"status": "not_going"},
            follow_redirects=False,
        )
        assert response.status_code == 303


class TestClaimTicketEndpoint:
    """Tests for POST /events/{id}/tickets"""

    async def test_claim_ticket_requires_auth(self, client: AsyncClient, sample_event: Event):
        response = await client.post(
            f"/events/{sample_event.id}/tickets",
            data={"ticket_type_id": "some-id", "quantity": "1"},
            follow_redirects=False,
        )
        assert response.status_code == 401

    async def test_claim_ticket_success(
        self,
        attendee_client: AsyncClient,
        db_session: AsyncSession,
        sample_event: Event,
    ):
        tt_result = await db_session.execute(
            select(TicketType).where(TicketType.event_id == sample_event.id)
        )
        tt = tt_result.scalars().first()
        assert tt is not None

        response = await attendee_client.post(
            f"/events/{sample_event.id}/tickets",
            data={"ticket_type_id": tt.id, "quantity": "2"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert f"/events/{sample_event.id}" in response.headers.get("location", "")


class TestCheckinEndpoint:
    """Tests for POST /events/{id}/checkin/{attendee_id}"""

    async def test_checkin_requires_auth(self, client: AsyncClient, sample_event: Event, attendee_user: User):
        response = await client.post(
            f"/events/{sample_event.id}/checkin/{attendee_user.id}",
            follow_redirects=False,
        )
        assert response.status_code == 401

    async def test_checkin_by_organizer(
        self,
        organizer_client: AsyncClient,
        db_session: AsyncSession,
        sample_event: Event,
        attendee_user: User,
    ):
        from services.ticket_service import claim_ticket

        tt_result = await db_session.execute(
            select(TicketType).where(TicketType.event_id == sample_event.id)
        )
        tt = tt_result.scalars().first()
        assert tt is not None

        await claim_ticket(
            db=db_session,
            event_id=sample_event.id,
            ticket_type_id=tt.id,
            attendee_id=attendee_user.id,
            quantity=1,
        )
        await db_session.commit()

        response = await organizer_client.post(
            f"/events/{sample_event.id}/checkin/{attendee_user.id}",
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_checkin_by_non_organizer_redirects(
        self,
        attendee_client: AsyncClient,
        sample_event: Event,
        attendee_user: User,
    ):
        response = await attendee_client.post(
            f"/events/{sample_event.id}/checkin/{attendee_user.id}",
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_checkin_nonexistent_event_returns_404(self, organizer_client: AsyncClient, attendee_user: User):
        response = await organizer_client.post(
            f"/events/nonexistent-id/checkin/{attendee_user.id}",
            follow_redirects=False,
        )
        assert response.status_code == 404