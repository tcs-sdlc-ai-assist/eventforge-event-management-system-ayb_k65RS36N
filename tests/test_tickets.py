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
from services.ticket_service import (
    claim_ticket,
    cancel_ticket,
    get_ticket_availability,
    get_total_tickets_sold,
    get_total_revenue,
    get_user_tickets,
    toggle_checkin,
)
from utils.security import hash_password


@pytest.mark.asyncio
async def test_claim_ticket_success(db_session: AsyncSession, sample_event: Event, attendee_user: User):
    """Test that a valid ticket claim succeeds and updates sold count."""
    ticket_types = sample_event.ticket_types
    assert len(ticket_types) > 0

    general_tt = None
    for tt in ticket_types:
        if tt.name == "General Admission":
            general_tt = tt
            break
    assert general_tt is not None

    ticket = await claim_ticket(
        db=db_session,
        event_id=sample_event.id,
        ticket_type_id=general_tt.id,
        attendee_id=attendee_user.id,
        quantity=2,
    )

    assert ticket is not None
    assert ticket.event_id == sample_event.id
    assert ticket.ticket_type_id == general_tt.id
    assert ticket.attendee_id == attendee_user.id
    assert ticket.quantity == 2
    assert ticket.status == "confirmed"
    assert ticket.checked_in is False
    assert ticket.total_price == pytest.approx(49.99 * 2)


@pytest.mark.asyncio
async def test_claim_ticket_sold_out(db_session: AsyncSession, sample_event: Event, attendee_user: User):
    """Test that claiming more tickets than available raises ValueError."""
    ticket_types = sample_event.ticket_types
    vip_tt = None
    for tt in ticket_types:
        if tt.name == "VIP":
            vip_tt = tt
            break
    assert vip_tt is not None

    # VIP has quantity=100, try to claim 101
    with pytest.raises(ValueError, match="Not enough tickets available"):
        await claim_ticket(
            db=db_session,
            event_id=sample_event.id,
            ticket_type_id=vip_tt.id,
            attendee_id=attendee_user.id,
            quantity=101,
        )


@pytest.mark.asyncio
async def test_claim_ticket_quantity_zero_raises(db_session: AsyncSession, sample_event: Event, attendee_user: User):
    """Test that claiming zero tickets raises ValueError."""
    ticket_types = sample_event.ticket_types
    general_tt = ticket_types[0]

    with pytest.raises(ValueError, match="Quantity must be at least 1"):
        await claim_ticket(
            db=db_session,
            event_id=sample_event.id,
            ticket_type_id=general_tt.id,
            attendee_id=attendee_user.id,
            quantity=0,
        )


@pytest.mark.asyncio
async def test_claim_ticket_negative_quantity_raises(db_session: AsyncSession, sample_event: Event, attendee_user: User):
    """Test that claiming negative quantity raises ValueError."""
    ticket_types = sample_event.ticket_types
    general_tt = ticket_types[0]

    with pytest.raises(ValueError, match="Quantity must be at least 1"):
        await claim_ticket(
            db=db_session,
            event_id=sample_event.id,
            ticket_type_id=general_tt.id,
            attendee_id=attendee_user.id,
            quantity=-1,
        )


@pytest.mark.asyncio
async def test_claim_ticket_event_not_found(db_session: AsyncSession, attendee_user: User):
    """Test that claiming a ticket for a nonexistent event raises ValueError."""
    with pytest.raises(ValueError, match="Event not found"):
        await claim_ticket(
            db=db_session,
            event_id="nonexistent-event-id",
            ticket_type_id="nonexistent-tt-id",
            attendee_id=attendee_user.id,
            quantity=1,
        )


@pytest.mark.asyncio
async def test_claim_ticket_draft_event_raises(db_session: AsyncSession, draft_event: Event, attendee_user: User):
    """Test that claiming a ticket for a draft event raises ValueError."""
    # Create a ticket type for the draft event
    tt = TicketType(
        event_id=draft_event.id,
        name="Standard",
        price=10.0,
        quantity=50,
        sold=0,
    )
    db_session.add(tt)
    await db_session.flush()
    await db_session.refresh(tt)

    with pytest.raises(ValueError, match="Event is not published"):
        await claim_ticket(
            db=db_session,
            event_id=draft_event.id,
            ticket_type_id=tt.id,
            attendee_id=attendee_user.id,
            quantity=1,
        )


@pytest.mark.asyncio
async def test_claim_ticket_wrong_ticket_type_for_event(
    db_session: AsyncSession, sample_event: Event, attendee_user: User
):
    """Test that claiming a ticket with a ticket type from another event raises ValueError."""
    with pytest.raises(ValueError, match="Ticket type not found for this event"):
        await claim_ticket(
            db=db_session,
            event_id=sample_event.id,
            ticket_type_id="nonexistent-ticket-type-id",
            attendee_id=attendee_user.id,
            quantity=1,
        )


@pytest.mark.asyncio
async def test_claim_ticket_user_not_found(db_session: AsyncSession, sample_event: Event):
    """Test that claiming a ticket with a nonexistent user raises ValueError."""
    ticket_types = sample_event.ticket_types
    general_tt = ticket_types[0]

    with pytest.raises(ValueError, match="User not found"):
        await claim_ticket(
            db=db_session,
            event_id=sample_event.id,
            ticket_type_id=general_tt.id,
            attendee_id="nonexistent-user-id",
            quantity=1,
        )


@pytest.mark.asyncio
async def test_claim_ticket_exact_remaining_quantity(
    db_session: AsyncSession, sample_event: Event, attendee_user: User
):
    """Test claiming exactly the remaining available tickets succeeds."""
    vip_tt = None
    for tt in sample_event.ticket_types:
        if tt.name == "VIP":
            vip_tt = tt
            break
    assert vip_tt is not None

    # Claim all 100 VIP tickets
    ticket = await claim_ticket(
        db=db_session,
        event_id=sample_event.id,
        ticket_type_id=vip_tt.id,
        attendee_id=attendee_user.id,
        quantity=100,
    )
    assert ticket is not None
    assert ticket.quantity == 100
    assert ticket.status == "confirmed"


@pytest.mark.asyncio
async def test_claim_ticket_after_partial_sold(
    db_session: AsyncSession, sample_event: Event, attendee_user: User, organizer_user: User
):
    """Test that availability is correctly calculated after partial sales."""
    vip_tt = None
    for tt in sample_event.ticket_types:
        if tt.name == "VIP":
            vip_tt = tt
            break
    assert vip_tt is not None

    # First claim: 90 tickets
    await claim_ticket(
        db=db_session,
        event_id=sample_event.id,
        ticket_type_id=vip_tt.id,
        attendee_id=attendee_user.id,
        quantity=90,
    )

    # Second claim: 11 tickets should fail (only 10 remaining)
    with pytest.raises(ValueError, match="Not enough tickets available"):
        await claim_ticket(
            db=db_session,
            event_id=sample_event.id,
            ticket_type_id=vip_tt.id,
            attendee_id=organizer_user.id,
            quantity=11,
        )

    # Third claim: 10 tickets should succeed
    ticket = await claim_ticket(
        db=db_session,
        event_id=sample_event.id,
        ticket_type_id=vip_tt.id,
        attendee_id=organizer_user.id,
        quantity=10,
    )
    assert ticket is not None
    assert ticket.quantity == 10


@pytest.mark.asyncio
async def test_get_ticket_availability(db_session: AsyncSession, sample_event: Event, attendee_user: User):
    """Test ticket availability calculation before and after claims."""
    general_tt = None
    for tt in sample_event.ticket_types:
        if tt.name == "General Admission":
            general_tt = tt
            break
    assert general_tt is not None

    # Initially all available
    available = await get_ticket_availability(db=db_session, ticket_type_id=general_tt.id)
    assert available == 300

    # Claim 50
    await claim_ticket(
        db=db_session,
        event_id=sample_event.id,
        ticket_type_id=general_tt.id,
        attendee_id=attendee_user.id,
        quantity=50,
    )

    available_after = await get_ticket_availability(db=db_session, ticket_type_id=general_tt.id)
    assert available_after == 250


@pytest.mark.asyncio
async def test_get_ticket_availability_nonexistent_type(db_session: AsyncSession):
    """Test that checking availability for a nonexistent ticket type raises ValueError."""
    with pytest.raises(ValueError, match="Ticket type not found"):
        await get_ticket_availability(db=db_session, ticket_type_id="nonexistent-id")


@pytest.mark.asyncio
async def test_cancel_ticket_success(db_session: AsyncSession, sample_event: Event, attendee_user: User):
    """Test that cancelling a confirmed ticket succeeds and updates sold count."""
    general_tt = None
    for tt in sample_event.ticket_types:
        if tt.name == "General Admission":
            general_tt = tt
            break
    assert general_tt is not None

    ticket = await claim_ticket(
        db=db_session,
        event_id=sample_event.id,
        ticket_type_id=general_tt.id,
        attendee_id=attendee_user.id,
        quantity=5,
    )

    # Verify sold count increased
    available_before_cancel = await get_ticket_availability(db=db_session, ticket_type_id=general_tt.id)
    assert available_before_cancel == 295

    cancelled_ticket = await cancel_ticket(
        db=db_session,
        ticket_id=ticket.id,
        user_id=attendee_user.id,
    )

    assert cancelled_ticket.status == "cancelled"

    # Verify sold count decreased
    available_after_cancel = await get_ticket_availability(db=db_session, ticket_type_id=general_tt.id)
    assert available_after_cancel == 300


@pytest.mark.asyncio
async def test_cancel_ticket_not_found(db_session: AsyncSession, attendee_user: User):
    """Test that cancelling a nonexistent ticket raises ValueError."""
    with pytest.raises(ValueError, match="Ticket not found"):
        await cancel_ticket(
            db=db_session,
            ticket_id="nonexistent-ticket-id",
            user_id=attendee_user.id,
        )


@pytest.mark.asyncio
async def test_cancel_ticket_wrong_user(
    db_session: AsyncSession, sample_event: Event, attendee_user: User, organizer_user: User
):
    """Test that a user cannot cancel another user's ticket."""
    general_tt = sample_event.ticket_types[0]

    ticket = await claim_ticket(
        db=db_session,
        event_id=sample_event.id,
        ticket_type_id=general_tt.id,
        attendee_id=attendee_user.id,
        quantity=1,
    )

    with pytest.raises(PermissionError, match="You can only cancel your own tickets"):
        await cancel_ticket(
            db=db_session,
            ticket_id=ticket.id,
            user_id=organizer_user.id,
        )


@pytest.mark.asyncio
async def test_cancel_ticket_already_cancelled(
    db_session: AsyncSession, sample_event: Event, attendee_user: User
):
    """Test that cancelling an already cancelled ticket raises ValueError."""
    general_tt = sample_event.ticket_types[0]

    ticket = await claim_ticket(
        db=db_session,
        event_id=sample_event.id,
        ticket_type_id=general_tt.id,
        attendee_id=attendee_user.id,
        quantity=1,
    )

    await cancel_ticket(db=db_session, ticket_id=ticket.id, user_id=attendee_user.id)

    with pytest.raises(ValueError, match="Ticket is already cancelled"):
        await cancel_ticket(db=db_session, ticket_id=ticket.id, user_id=attendee_user.id)


@pytest.mark.asyncio
async def test_cancel_ticket_checked_in(
    db_session: AsyncSession, sample_event: Event, attendee_user: User
):
    """Test that cancelling a checked-in ticket raises ValueError."""
    general_tt = sample_event.ticket_types[0]

    ticket = await claim_ticket(
        db=db_session,
        event_id=sample_event.id,
        ticket_type_id=general_tt.id,
        attendee_id=attendee_user.id,
        quantity=1,
    )

    # Check in the attendee
    await toggle_checkin(
        db=db_session,
        event_id=sample_event.id,
        attendee_id=attendee_user.id,
    )

    with pytest.raises(ValueError, match="Cannot cancel a ticket that has been checked in"):
        await cancel_ticket(db=db_session, ticket_id=ticket.id, user_id=attendee_user.id)


@pytest.mark.asyncio
async def test_get_total_tickets_sold(db_session: AsyncSession, sample_event: Event, attendee_user: User):
    """Test total tickets sold calculation for an event."""
    total_before = await get_total_tickets_sold(db=db_session, event_id=sample_event.id)
    assert total_before == 0

    general_tt = sample_event.ticket_types[0]

    await claim_ticket(
        db=db_session,
        event_id=sample_event.id,
        ticket_type_id=general_tt.id,
        attendee_id=attendee_user.id,
        quantity=3,
    )

    total_after = await get_total_tickets_sold(db=db_session, event_id=sample_event.id)
    assert total_after == 3


@pytest.mark.asyncio
async def test_get_total_revenue(db_session: AsyncSession, sample_event: Event, attendee_user: User):
    """Test total revenue calculation for an event."""
    revenue_before = await get_total_revenue(db=db_session, event_id=sample_event.id)
    assert revenue_before == pytest.approx(0.0)

    general_tt = None
    for tt in sample_event.ticket_types:
        if tt.name == "General Admission":
            general_tt = tt
            break
    assert general_tt is not None

    await claim_ticket(
        db=db_session,
        event_id=sample_event.id,
        ticket_type_id=general_tt.id,
        attendee_id=attendee_user.id,
        quantity=2,
    )

    revenue_after = await get_total_revenue(db=db_session, event_id=sample_event.id)
    assert revenue_after == pytest.approx(49.99 * 2)


@pytest.mark.asyncio
async def test_get_user_tickets(db_session: AsyncSession, sample_event: Event, attendee_user: User):
    """Test fetching all tickets for a user."""
    tickets_before = await get_user_tickets(db=db_session, user_id=attendee_user.id)
    assert len(tickets_before) == 0

    general_tt = sample_event.ticket_types[0]

    await claim_ticket(
        db=db_session,
        event_id=sample_event.id,
        ticket_type_id=general_tt.id,
        attendee_id=attendee_user.id,
        quantity=1,
    )

    tickets_after = await get_user_tickets(db=db_session, user_id=attendee_user.id)
    assert len(tickets_after) == 1
    assert tickets_after[0]["event_id"] == sample_event.id
    assert tickets_after[0]["event_title"] == sample_event.title
    assert tickets_after[0]["quantity"] == 1
    assert tickets_after[0]["status"] == "confirmed"


@pytest.mark.asyncio
async def test_toggle_checkin(db_session: AsyncSession, sample_event: Event, attendee_user: User):
    """Test toggling check-in status for an attendee."""
    general_tt = sample_event.ticket_types[0]

    await claim_ticket(
        db=db_session,
        event_id=sample_event.id,
        ticket_type_id=general_tt.id,
        attendee_id=attendee_user.id,
        quantity=1,
    )

    # Check in
    result = await toggle_checkin(
        db=db_session,
        event_id=sample_event.id,
        attendee_id=attendee_user.id,
    )
    assert result["checked_in"] is True
    assert result["checked_in_at"] is not None

    # Undo check-in
    result2 = await toggle_checkin(
        db=db_session,
        event_id=sample_event.id,
        attendee_id=attendee_user.id,
    )
    assert result2["checked_in"] is False
    assert result2["checked_in_at"] is None


@pytest.mark.asyncio
async def test_toggle_checkin_no_ticket(db_session: AsyncSession, sample_event: Event, attendee_user: User):
    """Test that toggling check-in without a ticket raises ValueError."""
    with pytest.raises(ValueError, match="No confirmed ticket found"):
        await toggle_checkin(
            db=db_session,
            event_id=sample_event.id,
            attendee_id=attendee_user.id,
        )


@pytest.mark.asyncio
async def test_cancelled_tickets_not_counted_in_sold(
    db_session: AsyncSession, sample_event: Event, attendee_user: User
):
    """Test that cancelled tickets are not counted in total sold."""
    general_tt = sample_event.ticket_types[0]

    ticket = await claim_ticket(
        db=db_session,
        event_id=sample_event.id,
        ticket_type_id=general_tt.id,
        attendee_id=attendee_user.id,
        quantity=5,
    )

    total_sold = await get_total_tickets_sold(db=db_session, event_id=sample_event.id)
    assert total_sold == 5

    await cancel_ticket(db=db_session, ticket_id=ticket.id, user_id=attendee_user.id)

    total_sold_after = await get_total_tickets_sold(db=db_session, event_id=sample_event.id)
    assert total_sold_after == 0


@pytest.mark.asyncio
async def test_cancelled_tickets_not_counted_in_revenue(
    db_session: AsyncSession, sample_event: Event, attendee_user: User
):
    """Test that cancelled tickets are not counted in total revenue."""
    general_tt = None
    for tt in sample_event.ticket_types:
        if tt.name == "General Admission":
            general_tt = tt
            break
    assert general_tt is not None

    ticket = await claim_ticket(
        db=db_session,
        event_id=sample_event.id,
        ticket_type_id=general_tt.id,
        attendee_id=attendee_user.id,
        quantity=2,
    )

    revenue = await get_total_revenue(db=db_session, event_id=sample_event.id)
    assert revenue == pytest.approx(49.99 * 2)

    await cancel_ticket(db=db_session, ticket_id=ticket.id, user_id=attendee_user.id)

    revenue_after = await get_total_revenue(db=db_session, event_id=sample_event.id)
    assert revenue_after == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_multiple_users_claim_tickets(
    db_session: AsyncSession, sample_event: Event, attendee_user: User, organizer_user: User
):
    """Test that multiple users can claim tickets from the same ticket type."""
    general_tt = None
    for tt in sample_event.ticket_types:
        if tt.name == "General Admission":
            general_tt = tt
            break
    assert general_tt is not None

    ticket1 = await claim_ticket(
        db=db_session,
        event_id=sample_event.id,
        ticket_type_id=general_tt.id,
        attendee_id=attendee_user.id,
        quantity=10,
    )

    ticket2 = await claim_ticket(
        db=db_session,
        event_id=sample_event.id,
        ticket_type_id=general_tt.id,
        attendee_id=organizer_user.id,
        quantity=15,
    )

    assert ticket1.attendee_id == attendee_user.id
    assert ticket2.attendee_id == organizer_user.id

    total_sold = await get_total_tickets_sold(db=db_session, event_id=sample_event.id)
    assert total_sold == 25

    available = await get_ticket_availability(db=db_session, ticket_type_id=general_tt.id)
    assert available == 275


@pytest.mark.asyncio
async def test_claim_ticket_via_http_authenticated(
    organizer_client: AsyncClient,
    sample_event: Event,
    db_session: AsyncSession,
):
    """Test claiming a ticket via HTTP POST as an authenticated user."""
    general_tt = None
    for tt in sample_event.ticket_types:
        if tt.name == "General Admission":
            general_tt = tt
            break
    assert general_tt is not None

    response = await organizer_client.post(
        f"/events/{sample_event.id}/tickets",
        data={
            "ticket_type_id": general_tt.id,
            "quantity": "1",
        },
        follow_redirects=False,
    )

    # Should redirect back to event detail
    assert response.status_code in (303, 302)


@pytest.mark.asyncio
async def test_claim_ticket_via_http_unauthenticated(client: AsyncClient, sample_event: Event):
    """Test that claiming a ticket without authentication returns 401."""
    general_tt = sample_event.ticket_types[0]

    response = await client.post(
        f"/events/{sample_event.id}/tickets",
        data={
            "ticket_type_id": general_tt.id,
            "quantity": "1",
        },
        follow_redirects=False,
    )

    # Should get 401 since not authenticated
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_ticket_availability_api_endpoint(client: AsyncClient, sample_event: Event):
    """Test the ticket availability JSON API endpoint."""
    general_tt = None
    for tt in sample_event.ticket_types:
        if tt.name == "General Admission":
            general_tt = tt
            break
    assert general_tt is not None

    response = await client.get(f"/api/tickets/{general_tt.id}/availability")
    assert response.status_code == 200

    data = response.json()
    assert data["ticket_type_id"] == general_tt.id
    assert data["available"] == 300


@pytest.mark.asyncio
async def test_ticket_availability_api_not_found(client: AsyncClient):
    """Test the ticket availability API with a nonexistent ticket type."""
    response = await client.get("/api/tickets/nonexistent-id/availability")
    assert response.status_code == 404